"""Avisos de directo: al empezar a transmitir en OBS pregunta si enviar los avisos y genera la historia.

Uso:
    python stream_notice.py          # espera a que OBS empiece a transmitir
    python stream_notice.py --test   # simula un inicio de directo sin OBS
"""

import argparse
import json
import logging
import queue
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path

import obsws_python as obs
from PIL import Image
from obsws_python.error import OBSSDKError

from compose import ScreenNotFoundError, compose, find_existing_story, save_story, slugify, story_date
from obs_monitor import obs_work_area
from popup import NoticePopup
from publish import publish
from twitch_api import TwitchClient, TwitchError, find_own_images, get_online_image

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "config.json"
RETRY_SECONDS = 5
POLL_MS = 300
STREAM_STARTED = "OBS_WEBSOCKET_OUTPUT_STARTED"

def _own_image_label(path: Path, game_name: str) -> str:
    """Etiqueta corta para el selector: el nombre sin la parte del juego.

    the-callisto-protocol-jacob.jpg → "Tuya: jacob"; the-callisto-protocol.png → "Tuya";
    the-callisto-protocol/portada.jpg → "Tuya: portada".
    """
    rest = slugify(path.stem).replace(slugify(game_name), "").strip("-")
    return f"Tuya: {rest}" if rest else "Tuya"


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        sys.exit(
            "Falta config.json.\n"
            "Cópialo desde config.example.json (copy config.example.json config.json) "
            "y rellena la contraseña del WebSocket de OBS y las credenciales de Twitch."
        )
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        sys.exit(f"config.json no es un JSON válido: {error}")


class App:
    def __init__(self, config: dict, test_mode: bool):
        self.config = config
        self.test_mode = test_mode
        self.twitch = TwitchClient(config["twitch"]["client_id"], config["twitch"]["client_secret"])

        # tkinter vive en el hilo principal; la ventana raíz queda oculta
        self.root = tk.Tk()
        self.root.withdraw()
        # Cola de funciones que los otros hilos quieren ejecutar en el hilo de la interfaz
        self.ui_queue: queue.Queue = queue.Queue()
        self.popup: NoticePopup | None = None
        self.last_story: Path | None = None
        # (juego, ruta) de la historia existente que se está enseñando en la vista previa
        self.pending_existing = None
        # (juego, [(etiqueta, imagen, origen)]) de las imágenes que se están enseñando en el selector
        self.pending_choice = None

        self.root.after(POLL_MS, self._poll_queue)
        # Ctrl+C en consola cierra el programa (el manejador corre en cada revisión de la cola)
        signal.signal(signal.SIGINT, lambda *_: self.root.quit())

    def run(self):
        if self.test_mode:
            print("Modo prueba: simulando inicio de directo...")
            self.stream_started()
        else:
            threading.Thread(target=self._obs_loop, daemon=True).start()
        self.root.mainloop()
        print("Saliendo.")

    # --- Comunicación entre hilos ---

    def _poll_queue(self):
        while True:
            try:
                action = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            action()
        self.root.after(POLL_MS, self._poll_queue)

    def _in_ui(self, action):
        self.ui_queue.put(action)

    def stream_started(self):
        """Se puede llamar desde cualquier hilo."""
        self._in_ui(self._show_popup)

    # --- OBS ---

    def _obs_loop(self):
        settings = self.config["obs"]
        address = f"{settings['host']}:{settings['port']}"
        while True:
            attempt_started = time.monotonic()
            try:
                client = obs.EventClient(
                    host=settings["host"], port=settings["port"], password=settings["password"], timeout=3
                )
            except (ConnectionRefusedError, TimeoutError, OSError):
                print(f"OBS no está abierto o no responde en {address}. Reintentando en {RETRY_SECONDS} s...")
            except OBSSDKError:
                print(f"OBS ha rechazado la conexión: revisa la contraseña del WebSocket en config.json. "
                      f"Reintentando en {RETRY_SECONDS} s...")
            except Exception as error:
                print(f"No se pudo conectar con OBS ({type(error).__name__}: {error}). "
                      f"¿Contraseña incorrecta? Reintentando en {RETRY_SECONDS} s...")
            else:
                print("Conectado a OBS. Esperando a que empiece el directo...")
                client.callback.register(self.on_stream_state_changed)
                # El hilo de eventos de obsws-python termina cuando OBS se cierra
                client.worker.join()
                print("Se ha perdido la conexión con OBS.")
                attempt_started = time.monotonic()
            # En Windows, fallar contra un puerto cerrado ya tarda unos segundos: se descuentan de la espera
            time.sleep(max(0.0, RETRY_SECONDS - (time.monotonic() - attempt_started)))

    def on_stream_state_changed(self, data):
        # obsws-python enlaza el evento StreamStateChanged por el nombre de esta función
        if data.output_state == STREAM_STARTED:
            print("¡Directo iniciado!")
            self.stream_started()

    # --- Popup ---

    def _popup_area(self) -> tuple[int, int, int, int]:
        """Área útil del monitor donde está OBS; si no lo encuentra, el monitor principal."""
        return obs_work_area() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def _show_popup(self):
        # Un solo popup por inicio de directo
        if self.popup is not None and self.popup.exists():
            return
        self.popup = NoticePopup(self.root, self._popup_area(), on_accept=self._start_generation,
                                 on_close=self._popup_closed, on_retry=self._start_generation,
                                 on_open_folder=self._open_folder, on_send_existing=self._send_existing,
                                 on_generate_new=lambda: self._start_generation(force_new=True))

    def _popup_closed(self):
        self.popup = None
        if self.test_mode:
            self.root.quit()

    def _start_generation(self, force_new: bool = False):
        self.popup.show_working()
        # Red + imagen en otro hilo para que la ventana nunca se congele
        threading.Thread(target=self._generate, args=(force_new,), daemon=True).start()

    def _send_existing(self):
        """El usuario acepta la historia existente que se le ha enseñado."""
        game, path = self.pending_existing
        self.popup.show_working()
        threading.Thread(target=self._publish_existing, args=(game, path), daemon=True).start()

    def _open_folder(self):
        # Abre la carpeta de salida con la historia seleccionada
        if self.last_story and self.last_story.is_file():
            subprocess.Popen(["explorer", "/select,", str(self.last_story)])
        else:
            subprocess.Popen(["explorer", str(BASE / self.config["output_folder"])])

    def _ui_popup(self, method: str, *args):
        """Llama a un método del popup desde el hilo de la interfaz, si sigue abierto."""
        def action():
            if self.popup is not None and self.popup.exists():
                getattr(self.popup, method)(*args)
        self._in_ui(action)

    # --- Trabajo pesado (hilos aparte: solo hablan con la interfaz a través de la cola) ---

    def _generate(self, force_new: bool = False):
        """force_new: generar una historia nueva aunque ya exista una (el usuario rechazó la existente)."""
        config = self.config
        output_folder = BASE / config["output_folder"]
        try:
            # Margen para que Twitch refleje una categoría cambiada justo al empezar
            # (al pedir una nueva, la categoría se acaba de leer y no hace falta esperar)
            if not force_new:
                time.sleep(max(0, config.get("category_delay_seconds", 0)))
            game = self.twitch.get_current_game(config["twitch"]["channel"])
            print(f"Juego actual: {game.name}")
            self._ui_popup("set_step", 1, f"Categoría: {game.name}")

            if config.get("reuse_existing_story", True) and not force_new:
                existing = find_existing_story(output_folder, game.name)
                if existing:
                    # Ya hay una historia de este juego: se enseña en grande y el usuario decide
                    print(f"Hay una historia existente: {existing.name}. Esperando confirmación...")
                    self.pending_existing = (game, existing)
                    self._ui_popup("show_preview", existing, game.name, story_date(existing))
                    return

            images_folder = BASE / config["game_images_folder"]
            own = find_own_images(game.name, images_folder)
            if not own:
                print(f"Sin imágenes propias. Para usar una, guárdala en {images_folder.name}/ "
                      f"con «{slugify(game.name)}» en el nombre.")
                game_image, source = get_online_image(self.twitch, game)
                self._compose_and_publish(game, game_image, source)
                return

            # Hay imágenes propias: se enseñan junto a la de internet y el usuario elige
            options = []
            for path in sorted(own, key=lambda p: _own_image_label(p, game.name) != "Tuya"):
                try:
                    name = path.relative_to(images_folder).as_posix()
                    options.append((_own_image_label(path, game.name), Image.open(path).convert("RGB"),
                                    f"imagen propia ({name})"))
                except OSError as error:
                    print(f"Aviso: no se pudo abrir {path.name}: {error}")
            try:
                online_image, online_source = get_online_image(self.twitch, game)
                options.append((online_source[0].upper() + online_source[1:], online_image, online_source))
            except TwitchError as error:
                print(f"Aviso: sin imagen de internet, solo las propias. {error}")
            if not options:
                raise TwitchError(f"No se ha podido abrir ninguna imagen para «{game.name}».")
            print(f"Imágenes para elegir: {[label for label, _, _ in options]}")
            self.pending_choice = (game, options)
            self._ui_popup("show_picker", game.name, [(label, image) for label, image, _ in options], self._pick_image)
        except Exception as error:
            self._report_error(error)

    def _pick_image(self, index: int):
        """El usuario ha elegido una imagen en el selector (hilo de la interfaz)."""
        game, options = self.pending_choice
        _, image, source = options[index]
        self.popup.show_working()
        threading.Thread(target=self._compose_chosen, args=(game, image, source), daemon=True).start()

    def _compose_chosen(self, game, image, source: str):
        try:
            self._ui_popup("set_step", 1, f"Categoría: {game.name}")
            self._compose_and_publish(game, image, source)
        except Exception as error:
            self._report_error(error)

    def _compose_and_publish(self, game, game_image, source: str):
        print(f"Imagen del juego: {source}")
        self._ui_popup("set_step", 2, f"Imagen del juego: {source}")
        config = self.config
        story = compose(BASE / config["template"], game_image, config.get("crt_effect", False),
                        config.get("screen_fit", "contain"))
        path = save_story(story, BASE / config["output_folder"], game.name)
        self._ui_popup("set_step", 3, "Historia creada y guardada")
        self._publish(game, path, source)

    def _publish_existing(self, game, path: Path):
        try:
            self._ui_popup("set_step", 1, f"Categoría: {game.name}")
            self._ui_popup("set_step", 2, f"Historia existente del {story_date(path)}")
            self._ui_popup("set_step", 3, "Historia reutilizada")
            print(f"Se envía la historia existente: {path.name}")
            self._publish(game, path, f"historia del {story_date(path)}", reused=True)
        except Exception as error:
            self._report_error(error)

    def _publish(self, game, path: Path, source: str, reused: bool = False):
        self.last_story = path
        results = publish(path, game.name, self.config,
                          on_progress=lambda name: self._ui_popup("set_step_text", 3, f"Enviando a {name}…"))
        failed = [r.name for r in results if not r.ok]
        print("¡Aviso enviado!" if not failed else f"Aviso enviado con errores en: {', '.join(failed)}")
        self._ui_popup("show_done", path, game.name, source, results, reused)

    def _report_error(self, error: Exception):
        if isinstance(error, (TwitchError, ScreenNotFoundError, ValueError)):
            message = str(error)
        else:
            traceback.print_exc()
            message = f"Error inesperado: {error}"
        print(f"Error: {message}")
        self._ui_popup("show_error", message)


def main():
    # Evita errores de codificación al imprimir tildes o emojis en consolas antiguas
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # obsws-python imprime la traza completa en cada intento fallido; los mensajes propios bastan
    logging.getLogger("obsws_python").setLevel(logging.CRITICAL + 1)

    parser = argparse.ArgumentParser(description="Avisos de directo para OBS + Twitch.")
    parser.add_argument("--test", action="store_true", help="simula un inicio de directo sin OBS")
    args = parser.parse_args()

    App(load_config(), args.test).run()


if __name__ == "__main__":
    main()
