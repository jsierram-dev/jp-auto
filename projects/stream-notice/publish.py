"""Publicación de la historia en los destinos activados en config.json."""

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Si config.json no tiene "destinations", al menos se abre la imagen
DEFAULT_DESTINATIONS = {"open_image": {"enabled": True}}


@dataclass
class PublishResult:
    destination: str  # nombre del módulo (clave en config.json)
    name: str         # nombre visible (NAME del módulo, p. ej. "Instagram")
    ok: bool
    message: str


def publish(image_path: Path, game_name: str, config: dict,
            on_progress: Callable[[str], None] | None = None) -> list[PublishResult]:
    """Publica en cada destino activado; si uno falla, los demás siguen.

    on_progress(nombre_visible) se llama justo antes de enviar a cada destino.
    """
    print(f"Publicando historia: {image_path}")
    results = []
    for destination, settings in config.get("destinations", DEFAULT_DESTINATIONS).items():
        if not settings.get("enabled", False):
            continue
        name = destination
        try:
            module = importlib.import_module(f"destinations.{destination}")
            name = getattr(module, "NAME", destination)
            if on_progress:
                on_progress(name)
            message = module.publish(Path(image_path), game_name, settings)
            results.append(PublishResult(destination, name, True, message))
            print(f"  ✔ {name}: {message}")
        except Exception as error:
            results.append(PublishResult(destination, name, False, str(error)))
            print(f"  ✘ {name}: {error}")
    return results
