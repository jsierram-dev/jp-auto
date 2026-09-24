"""Tokens que el programa renueva solo (Instagram, TikTok), guardados en tokens.json (ignorado por git).

Se guardan aparte para que el programa nunca reescriba config.json, que es del usuario.
"""

import json
import os
import threading
from pathlib import Path

PATH = Path(__file__).parent / "tokens.json"
_lock = threading.Lock()


def load(service: str) -> dict:
    with _lock:
        if not PATH.is_file():
            return {}
        try:
            return json.loads(PATH.read_text(encoding="utf-8")).get(service, {})
        except (json.JSONDecodeError, OSError):
            return {}


def save(service: str, data: dict):
    with _lock:
        everything = {}
        if PATH.is_file():
            try:
                everything = json.loads(PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                everything = {}
        everything[service] = data
        # Escritura atómica: primero a un temporal y luego se reemplaza
        temporary = PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(everything, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, PATH)
