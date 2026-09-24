"""Icono junto al reloj: muestra si está conectado a OBS y deja probar, abrir carpetas y salir."""

import os
import subprocess
import threading
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image

LOGO = Path(__file__).parent / "assets" / "logo.png"


class TrayIcon:
    def __init__(self, is_connected: Callable[[], bool], on_test: Callable, on_quit: Callable,
                 output_folder: Path, log_path: Path):
        self.is_connected = is_connected
        self.on_test, self.on_quit = on_test, on_quit
        self.output_folder, self.log_path = output_folder, log_path
        self.icon = pystray.Icon("stream-notice", Image.open(LOGO).resize((64, 64)), self._title(), self._menu())

    def _title(self) -> str:
        return "Avisos de directo — " + ("conectado a OBS" if self.is_connected() else "esperando a OBS")

    def _menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(lambda item: "● Conectado a OBS" if self.is_connected() else "○ Esperando a OBS…",
                             None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Probar aviso", lambda: self.on_test()),
            pystray.MenuItem("Abrir carpeta de historias", lambda: self._open(self.output_folder)),
            pystray.MenuItem("Ver registro", lambda: self._open(self.log_path)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", lambda: self._quit()),
        )

    @staticmethod
    def _open(path: Path):
        if path.exists():
            os.startfile(path)
        else:
            subprocess.Popen(["explorer", str(path.parent)])

    def _quit(self):
        self.icon.stop()
        self.on_quit()

    def refresh(self):
        """Actualiza el texto del icono y del menú (p. ej. al conectar o desconectar de OBS)."""
        self.icon.title = self._title()
        self.icon.update_menu()

    def start(self):
        threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self):
        try:
            self.icon.stop()
        except Exception:
            pass
