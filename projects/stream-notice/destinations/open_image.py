"""Destino básico: abre la imagen generada con el visor predeterminado."""

import os
import subprocess
import sys
from pathlib import Path

NAME = "Abrir en el PC"


def publish(image_path: Path, game_name: str, settings: dict) -> str:
    if sys.platform == "win32":
        os.startfile(image_path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(image_path)])
    return "imagen abierta"
