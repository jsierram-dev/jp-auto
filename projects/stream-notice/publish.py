"""Publicación de la historia en los destinos activados en config.json."""

import importlib
from dataclasses import dataclass
from pathlib import Path

# Si config.json no tiene "destinations", al menos se abre la imagen
DEFAULT_DESTINATIONS = {"open_image": {"enabled": True}}


@dataclass
class PublishResult:
    destination: str
    ok: bool
    message: str


def publish(image_path: Path, game_name: str, config: dict) -> list[PublishResult]:
    """Publica en cada destino activado; si uno falla, los demás siguen."""
    print(f"Publicando historia: {image_path}")
    results = []
    for name, settings in config.get("destinations", DEFAULT_DESTINATIONS).items():
        if not settings.get("enabled", False):
            continue
        try:
            module = importlib.import_module(f"destinations.{name}")
            message = module.publish(Path(image_path), game_name, settings)
            results.append(PublishResult(name, True, message))
            print(f"  ✔ {name}: {message}")
        except Exception as error:
            results.append(PublishResult(name, False, str(error)))
            print(f"  ✘ {name}: {error}")
    return results
