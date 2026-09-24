from io import BytesIO

import pytest
import requests
from PIL import Image

import twitch_api as ta


def _jpeg(color):
    buffer = BytesIO()
    Image.new("RGB", (40, 30), color).save(buffer, "JPEG")
    return buffer.getvalue()


class _Response:
    def __init__(self, code=200, js=None, content=b""):
        self.status_code, self._js, self.content = code, js, content

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._js

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    """Simula Twitch (token + Helix), IGDB y las descargas de imágenes."""

    def __init__(self, channel_game="33214", igdb=None, igdb_fail=False, first_401=False, art_fail=False):
        self.channel_game, self.igdb, self.igdb_fail = channel_game, igdb, igdb_fail
        self.first_401, self.art_fail = first_401, art_fail
        self.calls, self.tokens, self.igdb_query = [], 0, None

    def post(self, url, **kwargs):
        self.tokens += 1
        self.calls.append("token")
        return _Response(js={"access_token": f"tok{self.tokens}", "expires_in": 3600})

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append(url.rsplit("/", 1)[-1])
        if self.first_401 and headers["Authorization"] == "Bearer tok1":
            return _Response(401)
        if url.endswith("users"):
            return _Response(js={"data": [{"id": "99"}] if kwargs["params"]["login"] == "jscorpiodv" else []})
        if url.endswith("channels"):
            return _Response(js={"data": [{"game_id": self.channel_game, "game_name": "Fortnite"}]})
        if url.endswith("helix/games"):
            return _Response(js={"data": [{"name": "Fortnite", "igdb_id": "1905",
                                           "box_art_url": "https://box/{width}x{height}.jpg"}]})
        if url == ta.IGDB_URL:
            self.igdb_query = kwargs["data"].decode()
            if self.igdb_fail:
                raise requests.ConnectionError("caído")
            default = [{"artworks": [{"image_id": "art1"}], "screenshots": [{"image_id": "sc1"}]}]
            return _Response(js=self.igdb if self.igdb is not None else default)

    def get(self, url, **kwargs):
        self.calls.append(url)
        if "art1" in url and self.art_fail:
            return _Response(404)
        color = (255, 0, 0) if "art" in url else (0, 255, 0) if "sc" in url else (0, 0, 255)
        return _Response(content=_jpeg(color))


def _client(**kwargs):
    session = FakeSession(**kwargs)
    return ta.TwitchClient("id", "secret", session), session


# --- Helix ---

def test_juego_actual_y_caratula_600x800():
    client, _ = _client()
    game = client.get_current_game("jscorpiodv")
    assert (game.name, game.igdb_id, game.box_art_url) == ("Fortnite", "1905", "https://box/600x800.jpg")


def test_sin_categoria():
    client, _ = _client(channel_game="")
    with pytest.raises(ta.NoCategoryError, match="ninguna categoría"):
        client.get_current_game("jscorpiodv")


def test_canal_inexistente():
    client, _ = _client()
    with pytest.raises(ta.TwitchError, match="No existe el canal"):
        client.get_current_game("noexiste")


# --- Token ---

def test_token_cacheado():
    client, session = _client()
    client.get_current_game("jscorpiodv")
    client.get_current_game("jscorpiodv")
    assert session.tokens == 1


def test_401_renueva_el_token_y_reintenta():
    client, session = _client(first_401=True)
    client.get_current_game("jscorpiodv")
    assert session.tokens == 2


def test_token_caducado_se_renueva():
    client, session = _client()
    client.get_current_game("jscorpiodv")
    client._token_expires_at = 0
    client.get_current_game("jscorpiodv")
    assert session.tokens == 2


# --- Imagen de internet (IGDB → carátula) ---

def test_prefiere_artwork_de_igdb():
    client, session = _client()
    image, source = ta.get_online_image(client, client.get_current_game("jscorpiodv"))
    assert source == "IGDB" and image.getpixel((5, 5))[0] > 200
    assert "where id = 1905" in session.igdb_query


def test_sin_artworks_usa_captura():
    client, _ = _client(igdb=[{"screenshots": [{"image_id": "sc1"}]}])
    image, source = ta.get_online_image(client, client.get_current_game("jscorpiodv"))
    assert source == "IGDB" and image.getpixel((5, 5))[1] > 200


@pytest.mark.parametrize("kwargs", [{"igdb": []}, {"igdb_fail": True}, {"art_fail": True}])
def test_si_igdb_no_sirve_usa_la_caratula(kwargs):
    client, _ = _client(**kwargs)
    _, source = ta.get_online_image(client, client.get_current_game("jscorpiodv"))
    assert source == "carátula de Twitch"


def test_sin_igdb_id_busca_por_nombre_con_comillas_escapadas():
    client, session = _client()
    client.get_igdb_image_urls(ta.Game("1", 'Juego "Raro"', "", ""))
    assert session.igdb_query.startswith('search "Juego \\"Raro\\"";') and "limit 1;" in session.igdb_query


def test_get_game_image_prioriza_la_propia(tmp_path):
    Image.new("RGB", (10, 10), (1, 2, 3)).save(tmp_path / "fortnite.webp", lossless=True)
    client, session = _client()
    image, source = ta.get_game_image(client, client.get_current_game("jscorpiodv"), tmp_path)
    assert source.startswith("imagen propia") and image.getpixel((5, 5)) == (1, 2, 3)
    assert session.igdb_query is None and not any(c.startswith("http") for c in session.calls)


# --- Imágenes propias ---

@pytest.fixture
def own_images(tmp_path):
    files = ["the-callisto-protocol.png", "the-callisto-protocol-2.png", "The Callisto Protocol JACOB.jpg",
             "mi-the-callisto-protocol.webp", "the-callisto-protocol/portada.jpg",
             "The Callisto Protocol (fan art)/nieve.jpeg", "otros/the-callisto-protocol-final.png",
             "callisto.png", "the-callisto-protocol.txt", "fortnite.png", "Pokémon Legends Z-A.png",
             "portal.png", "portal-2.png"]
    for name in files:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b"x")
    return tmp_path


def _found(game, folder):
    return {p.relative_to(folder).as_posix() for p in ta.find_own_images(game, folder)}


def test_imagenes_propias_por_sufijo_prefijo_y_carpeta(own_images):
    assert _found("The Callisto Protocol", own_images) == {
        "the-callisto-protocol.png", "the-callisto-protocol-2.png", "The Callisto Protocol JACOB.jpg",
        "mi-the-callisto-protocol.webp", "the-callisto-protocol/portada.jpg",
        "The Callisto Protocol (fan art)/nieve.jpeg", "otros/the-callisto-protocol-final.png"}


def test_imagenes_propias_con_tildes_y_sin_mezclar_juegos(own_images):
    assert _found("Pokémon Legends: Z-A", own_images) == {"Pokémon Legends Z-A.png"}
    assert _found("Fortnite", own_images) == {"fortnite.png"}
    assert _found("Minecraft", own_images) == set()
    assert ta.find_own_images("Fortnite", own_images / "no-existe") == []


def test_limitacion_conocida_portal_coge_portal_2(own_images):
    # Aceptado a propósito: el selector enseña las imágenes antes de generar
    assert _found("Portal", own_images) == {"portal.png", "portal-2.png"}
