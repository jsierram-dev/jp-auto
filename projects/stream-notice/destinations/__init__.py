"""Destinos de publicación.

Cada destino es un módulo de este paquete con una función:

    publish(image_path: Path, game_name: str, settings: dict) -> str

que devuelve un mensaje corto de resultado y lanza una excepción si falla.
Se activa en config.json, dentro de "destinations": {"<nombre_del_modulo>": {"enabled": true, ...}}.
"""
