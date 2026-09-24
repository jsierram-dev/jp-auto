"""Lo necesario para funcionar en segundo plano (arranque con Windows, sin consola).

- Registro en logs/stream-notice.log con fecha y hora, también cuando no hay consola (pythonw).
- Una sola copia en marcha a la vez (mutex con nombre de Windows).
- Avisos en una ventanita de Windows cuando no hay consola donde escribirlos.
"""

import ctypes
import sys
from datetime import datetime
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logs" / "stream-notice.log"
MAX_LOG_BYTES = 1_000_000  # al pasar de ~1 MB se guarda como .log.1 y se empieza otro
MUTEX_NAME = "Local\\jp-auto-stream-notice"
_ERROR_ALREADY_EXISTS = 183
_mutex_handle = None


class _TimestampedLog:
    """Escribe en el archivo de registro (con fecha y hora al principio de cada línea) y en la consola si la hay."""

    def __init__(self, file, console):
        self.file, self.console = file, console
        self.at_line_start = True

    def write(self, text: str) -> int:
        if self.console is not None:
            try:
                self.console.write(text)
            except (OSError, ValueError):
                pass
        stamped = []
        for piece in text.splitlines(keepends=True):
            if self.at_line_start and piece.strip():
                stamped.append(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ")
            stamped.append(piece)
            self.at_line_start = piece.endswith("\n")
        self.file.write("".join(stamped))
        self.file.flush()
        return len(text)

    def flush(self):
        self.file.flush()
        if self.console is not None:
            try:
                self.console.flush()
            except (OSError, ValueError):
                pass


def setup_logging(path: Path = LOG_PATH):
    """Manda print() y los errores al registro (y a la consola, si existe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size > MAX_LOG_BYTES:
        path.replace(path.with_suffix(".log.1"))
    file = open(path, "a", encoding="utf-8", buffering=1)
    consoles = []
    for stream in (sys.stdout, sys.stderr):
        # Con pythonw no hay consola: sys.stdout y sys.stderr son None
        if stream is not None:
            stream.reconfigure(encoding="utf-8", errors="replace")
        consoles.append(stream)
    sys.stdout = _TimestampedLog(file, consoles[0])
    sys.stderr = _TimestampedLog(file, consoles[1])


def has_console() -> bool:
    return sys.__stdout__ is not None


def acquire_single_instance(name: str = MUTEX_NAME) -> bool:
    """True si esta es la única copia en marcha; False si ya había otra."""
    global _mutex_handle
    if sys.platform != "win32":
        return True
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, name)
    return ctypes.windll.kernel32.GetLastError() != _ERROR_ALREADY_EXISTS


def show_message(text: str, title: str = "Avisos de directo"):
    """Aviso visible aunque no haya consola (ventana de Windows)."""
    print(text)
    if sys.platform == "win32" and not has_console():
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)  # MB_ICONINFORMATION
