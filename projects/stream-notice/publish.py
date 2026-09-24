"""Publicación de la historia en los destinos activados en config.json."""

import importlib
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import hosting

# Si config.json no tiene "destinations", al menos se abre la imagen
DEFAULT_DESTINATIONS = {"open_image": {"enabled": True}}


@dataclass
class PublishResult:
    destination: str  # nombre del módulo (clave en config.json)
    name: str         # nombre visible (NAME del módulo, p. ej. "Instagram")
    ok: bool
    message: str


class PublishContext:
    """Lo que comparten los destinos en una publicación: la URL pública se sube una sola vez y solo si hace falta."""

    def __init__(self, image_path: Path, config: dict, on_progress: Callable[[str], None]):
        self.image_path = Path(image_path)
        self.config = config
        self.on_progress = on_progress
        self.current_step = ""  # lo que se está haciendo, para volver a mostrarlo tras la subida
        self._public_url: str | None = None

    def public_url(self) -> str:
        if self._public_url is None:
            self.on_progress("Subiendo la historia a internet…")
            self._public_url = hosting.upload(self.image_path, self.config.get("hosting", {}))
            print(f"  Historia pública en {self._public_url}")
            self.on_progress(self.current_step)
        return self._public_url


def publish(image_path: Path, game_name: str, config: dict,
            on_progress: Callable[[str], None] | None = None) -> list[PublishResult]:
    """Publica en cada destino activado; si uno falla, los demás siguen.

    on_progress(texto) recibe lo que se está haciendo, p. ej. "Enviando a Instagram…".
    """
    print(f"Publicando historia: {image_path}")
    progress = on_progress or (lambda text: None)
    context = PublishContext(image_path, config, progress)
    results = []
    for destination, settings in config.get("destinations", DEFAULT_DESTINATIONS).items():
        if not settings.get("enabled", False):
            continue
        name = destination
        try:
            module = importlib.import_module(f"destinations.{destination}")
            name = getattr(module, "NAME", destination)
            context.current_step = f"Enviando a {name}…"
            progress(context.current_step)
            # Los destinos que necesitan la URL pública la piden al contexto
            if "context" in inspect.signature(module.publish).parameters:
                message = module.publish(Path(image_path), game_name, settings, context=context)
            else:
                message = module.publish(Path(image_path), game_name, settings)
            results.append(PublishResult(destination, name, True, message))
            print(f"  ✔ {name}: {message}")
        except Exception as error:
            results.append(PublishResult(destination, name, False, str(error)))
            print(f"  ✘ {name}: {error}")
    return results
