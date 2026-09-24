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
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path

import obsws_python as obs
from PIL import Image, ImageDraw, ImageTk
from obsws_python.error import OBSSDKError

from compose import ScreenNotFoundError, compose, save_story
from publish import publish
from twitch_api import NoCategoryError, TwitchClient, TwitchError, get_game_image

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "config.json"
RETRY_SECONDS = 5
POLL_MS = 300
STREAM_STARTED = "OBS_WEBSOCKET_OUTPUT_STARTED"

FONT = ("Segoe UI", 11)
FONT_TITLE = ("Segoe UI", 14, "bold")


def _red_dot_image(size: int = 20) -> ImageTk.PhotoImage:
    """Círculo rojo con bordes suavizados (dibujado a 4× y reducido), como el emoji 🔴."""
    big = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse((4, 4, size * 4 - 4, size * 4 - 4), fill=(229, 57, 53, 255))
    return ImageTk.PhotoImage(big.resize((size, size), Image.LANCZOS))


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
        self.popup: tk.Toplevel | None = None
        self.red_dot: ImageTk.PhotoImage | None = None
        self.working = False

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

    def _show_popup(self):
        # Un solo popup por inicio de directo
        if self.popup is not None and self.popup.winfo_exists():
            return

        popup = tk.Toplevel(self.root)
        popup.title("¡Directo iniciado!")
        popup.attributes("-topmost", True)
        popup.resizable(False, False)
        popup.protocol("WM_DELETE_WINDOW", self._close_popup)
        self.popup = popup

        frame = tk.Frame(popup, padx=24, pady=20)
        frame.pack()
        # Tk 8.6 no pinta emojis en color: el 🔴 se dibuja como imagen junto al texto
        self.red_dot = self.red_dot or _red_dot_image()
        tk.Label(frame, text=" ¡Directo iniciado!", image=self.red_dot, compound="left",
                 font=FONT_TITLE).pack(pady=(0, 6))
        tk.Label(frame, text="¿Quieres enviar los avisos?", font=FONT).pack(pady=(0, 12))
        self.status = tk.Label(frame, text="", font=FONT, wraplength=340, justify="center")

        self.buttons = tk.Frame(frame)
        self.buttons.pack()
        tk.Button(self.buttons, text="Sí, enviar", font=FONT, width=12, command=self._accept).pack(side="left", padx=6)
        tk.Button(self.buttons, text="No", font=FONT, width=12, command=self._close_popup).pack(side="left", padx=6)
        self.close_button = tk.Button(frame, text="Cerrar", font=FONT, width=12, command=self._close_popup)

        # Centrado en pantalla y con el foco
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() - popup.winfo_width()) // 2
        y = (popup.winfo_screenheight() - popup.winfo_height()) // 3
        popup.geometry(f"+{x}+{y}")
        popup.lift()
        popup.focus_force()

    def _close_popup(self):
        if self.working:
            return  # no se cierra a mitad de generar la imagen
        if self.popup is not None:
            self.popup.destroy()
            self.popup = None
        if self.test_mode:
            self.root.quit()

    def _accept(self):
        self.working = True
        self.buttons.pack_forget()
        self.status.pack()
        self._set_status("Leyendo la categoría de Twitch...")
        # Red + imagen en otro hilo para que la ventana nunca se congele
        threading.Thread(target=self._generate, daemon=True).start()

    def _set_status(self, text: str):
        if self.popup is not None and self.popup.winfo_exists():
            self.status.config(text=text)

    def _finish(self, text: str):
        self.working = False
        self._set_status(text)
        if self.popup is not None and self.popup.winfo_exists():
            self.close_button.pack(pady=(14, 0))

    # --- Trabajo pesado (hilo aparte: solo habla con la interfaz a través de la cola) ---

    def _generate(self):
        config = self.config
        try:
            # Margen para que Twitch refleje una categoría cambiada justo al empezar
            time.sleep(max(0, config.get("category_delay_seconds", 0)))
            game = self.twitch.get_current_game(config["twitch"]["channel"])
            print(f"Juego actual: {game.name}")
            self._in_ui(lambda: self._set_status(f"Preparando imagen de {game.name}..."))

            game_image, source = get_game_image(self.twitch, game, BASE / config["game_images_folder"])
            print(f"Imagen del juego: {source}")
            story = compose(BASE / config["template"], game_image, config.get("crt_effect", True))
            path = save_story(story, BASE / config["output_folder"], game.name)

            failed = [result for result in publish(path, game.name, config) if not result.ok]
            message = "¡Aviso generado!"
            if failed:
                message += "\nFalló: " + ", ".join(f"{r.destination} ({r.message})" for r in failed)
        except NoCategoryError as error:
            message = str(error)
        except (TwitchError, ScreenNotFoundError) as error:
            message = f"Error: {error}"
        except Exception as error:
            traceback.print_exc()
            message = f"Error inesperado: {error}"
        print(message)
        self._in_ui(lambda: self._finish(message))


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
