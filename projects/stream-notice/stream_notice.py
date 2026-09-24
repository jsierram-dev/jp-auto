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
from obsws_python.error import OBSSDKError

from compose import ScreenNotFoundError, compose, save_story
from obs_monitor import obs_work_area
from popup import HEIGHT, WIDTH, NoticePopup
from publish import publish
from twitch_api import NoCategoryError, TwitchClient, TwitchError, get_game_image

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "config.json"
RETRY_SECONDS = 5
POLL_MS = 300
STREAM_STARTED = "OBS_WEBSOCKET_OUTPUT_STARTED"

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

    def _popup_position(self) -> tuple[int, int]:
        """Centro del monitor donde está OBS; si no lo encuentra, el monitor principal."""
        area = obs_work_area()
        if area is None:
            area = (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        left, top, right, bottom = area
        return left + (right - left - WIDTH) // 2, top + (bottom - top - HEIGHT) // 2

    def _show_popup(self):
        # Un solo popup por inicio de directo
        if self.popup is not None and self.popup.exists():
            return
        self.popup = NoticePopup(self.root, self._popup_position(), on_accept=self._start_generation,
                                 on_close=self._popup_closed, on_retry=self._start_generation,
                                 on_open_folder=self._open_folder)

    def _popup_closed(self):
        self.popup = None
        if self.test_mode:
            self.root.quit()

    def _start_generation(self):
        self.popup.show_working()
        # Red + imagen en otro hilo para que la ventana nunca se congele
        threading.Thread(target=self._generate, daemon=True).start()

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

    # --- Trabajo pesado (hilo aparte: solo habla con la interfaz a través de la cola) ---

    def _generate(self):
        config = self.config
        try:
            # Margen para que Twitch refleje una categoría cambiada justo al empezar
            time.sleep(max(0, config.get("category_delay_seconds", 0)))
            game = self.twitch.get_current_game(config["twitch"]["channel"])
            print(f"Juego actual: {game.name}")
            self._ui_popup("set_step", 1, f"Categoría: {game.name}")

            game_image, source = get_game_image(self.twitch, game, BASE / config["game_images_folder"])
            print(f"Imagen del juego: {source}")
            self._ui_popup("set_step", 2, f"Imagen del juego: {source}")

            story = compose(BASE / config["template"], game_image, config.get("crt_effect", False),
                            config.get("screen_fit", "contain"))
            path = save_story(story, BASE / config["output_folder"], game.name)
            self.last_story = path

            failed = [result for result in publish(path, game.name, config) if not result.ok]
            warning = ("Falló: " + ", ".join(f"{r.destination} ({r.message})" for r in failed)) if failed else None
            print("¡Aviso generado!" + (f" {warning}" if warning else ""))
            self._ui_popup("show_done", path, game.name, source, warning)
            return
        except NoCategoryError as error:
            message = str(error)
        except (TwitchError, ScreenNotFoundError, ValueError) as error:
            message = str(error)
        except Exception as error:
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
