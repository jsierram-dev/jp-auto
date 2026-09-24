"""Juego actual del canal (Twitch Helix) e imágenes del juego (IGDB)."""

import json
import sys
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import requests
import truststore
from PIL import Image

from compose import slugify

# Usar el almacén de certificados de Windows (como el navegador) y no solo el de certifi:
# los antivirus que analizan HTTPS (p. ej. Avast) firman con su propia raíz, que solo está en Windows
truststore.inject_into_ssl()

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
HELIX_URL = "https://api.twitch.tv/helix"
IGDB_URL = "https://api.igdb.com/v4/games"
IGDB_IMAGE_URL = "https://images.igdb.com/igdb/image/upload/t_1080p/{}.jpg"
BOX_ART_SIZE = "600x800"
TIMEOUT = 10
# Margen para renovar el token antes de que caduque de verdad
TOKEN_MARGIN_SECONDS = 60
OWN_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


class TwitchError(Exception):
    """Error con un mensaje claro para mostrar en el popup."""


class NoCategoryError(TwitchError):
    """El canal no tiene ninguna categoría puesta."""


@dataclass
class Game:
    id: str
    name: str
    igdb_id: str
    box_art_url: str


class TwitchClient:
    def __init__(self, client_id: str, client_secret: str, session: requests.Session | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = session or requests.Session()
        self._token: str | None = None
        self._token_expires_at = 0.0

    # --- Token de aplicación (client credentials) ---

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token
        try:
            response = self.session.post(TOKEN_URL, timeout=TIMEOUT, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            })
        except requests.RequestException as error:
            raise TwitchError(f"No se pudo conectar con Twitch para pedir el token: {error}") from error
        if response.status_code in (400, 401, 403):
            raise TwitchError("Twitch ha rechazado las credenciales: revisa client_id y client_secret en config.json.")
        if not response.ok:
            raise TwitchError(f"Error al pedir el token a Twitch (HTTP {response.status_code}).")

        data = response.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 0) - TOKEN_MARGIN_SECONDS
        return self._token

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Petición autenticada; si devuelve 401 renueva el token y reintenta una vez."""
        for attempt in range(2):
            headers = {"Client-ID": self.client_id, "Authorization": f"Bearer {self._get_token()}"}
            try:
                response = self.session.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
            except requests.Timeout as error:
                raise TwitchError(f"Twitch no ha respondido a tiempo ({url}).") from error
            except requests.RequestException as error:
                raise TwitchError(f"No se pudo conectar con Twitch: {error}") from error
            if response.status_code == 401 and attempt == 0:
                self._token = None
                continue
            if not response.ok:
                raise TwitchError(f"Error de la API de Twitch (HTTP {response.status_code}) en {url}.")
            return response
        raise TwitchError("Twitch sigue rechazando el token después de renovarlo.")

    def _helix(self, path: str, **params) -> list[dict]:
        return self._request("GET", f"{HELIX_URL}/{path}", params=params).json().get("data", [])

    # --- Helix ---

    def get_current_game(self, channel: str) -> Game:
        users = self._helix("users", login=channel)
        if not users:
            raise TwitchError(f"No existe el canal de Twitch '{channel}'.")

        channels = self._helix("channels", broadcaster_id=users[0]["id"])
        if not channels or not channels[0].get("game_id"):
            raise NoCategoryError("El canal no tiene ninguna categoría puesta. Ponla en Twitch y vuelve a intentarlo.")
        game_id = channels[0]["game_id"]
        game_name = channels[0].get("game_name", "")

        games = self._helix("games", id=game_id)
        info = games[0] if games else {}
        return Game(
            id=game_id,
            name=game_name or info.get("name", ""),
            igdb_id=info.get("igdb_id", ""),
            box_art_url=info.get("box_art_url", "").replace("{width}x{height}", BOX_ART_SIZE),
        )

    # --- IGDB ---

    def get_igdb_image_urls(self, game: Game) -> list[str]:
        """Artworks primero (arte promocional horizontal) y, si no hay, screenshots."""
        fields = "fields artworks.image_id, screenshots.image_id, name;"
        if game.igdb_id:
            query = f"{fields} where id = {int(game.igdb_id)};"
        else:
            name = game.name.replace('"', '\\"')
            query = f'search "{name}"; {fields} limit 1;'

        results = self._request("POST", IGDB_URL, data=query.encode("utf-8")).json()
        if not results:
            return []
        artworks = [a["image_id"] for a in results[0].get("artworks", []) if "image_id" in a]
        screenshots = [s["image_id"] for s in results[0].get("screenshots", []) if "image_id" in s]
        return [IGDB_IMAGE_URL.format(image_id) for image_id in artworks or screenshots]

    def download_image(self, url: str) -> Image.Image:
        try:
            response = self.session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGB")
        except (requests.RequestException, OSError) as error:
            raise TwitchError(f"No se pudo descargar la imagen {url}: {error}") from error


def find_own_image(game_name: str, folder: Path) -> Path | None:
    """Imagen propia en game_images/<slug>.(png|jpg|jpeg|webp), si existe."""
    for extension in OWN_IMAGE_EXTENSIONS:
        path = folder / f"{slugify(game_name)}{extension}"
        if path.is_file():
            return path
    return None


def get_game_image(client: TwitchClient, game: Game, own_images_folder: Path) -> tuple[Image.Image, str]:
    """Elige la imagen del juego: propia → IGDB → carátula de Twitch. Devuelve (imagen, origen)."""
    own = find_own_image(game.name, own_images_folder)
    if own:
        return Image.open(own).convert("RGB"), f"imagen propia ({own.name})"
    print(f"Sin imagen propia. Para usar una, guárdala como {own_images_folder.name}/{slugify(game.name)}.png")

    try:
        for url in client.get_igdb_image_urls(game):
            try:
                return client.download_image(url), "IGDB"
            except TwitchError as error:
                print(f"Aviso: {error}")
    except TwitchError as error:
        # Si IGDB falla, la carátula de Twitch sigue sirviendo
        print(f"Aviso: IGDB no disponible, se usa la carátula de Twitch. {error}")

    if not game.box_art_url:
        raise TwitchError(f"No se ha encontrado ninguna imagen para «{game.name}».")
    return client.download_image(game.box_art_url), "carátula de Twitch"


if __name__ == "__main__":
    # Prueba con credenciales reales: python twitch_api.py
    base = Path(__file__).parent
    config_path = base / "config.json"
    if not config_path.is_file():
        sys.exit("Falta config.json: cópialo desde config.example.json y rellena tus credenciales.")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    client = TwitchClient(config["twitch"]["client_id"], config["twitch"]["client_secret"])
    try:
        game = client.get_current_game(config["twitch"]["channel"])
        print(f"Juego actual: {game.name} (igdb_id={game.igdb_id or 'ninguno'})")
        image, source = get_game_image(client, game, base / config["game_images_folder"])
        print(f"Imagen elegida: {source}, {image.width}×{image.height}")
    except TwitchError as error:
        sys.exit(f"Error: {error}")
