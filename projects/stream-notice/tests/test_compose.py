from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from scipy import ndimage

import compose
from compose import ScreenNotFoundError, find_existing_story, save_story, slugify, story_date

TEMPLATE = Path(__file__).resolve().parents[1] / "story-notice.png"


@pytest.mark.parametrize("name, slug", [
    ("Fortnite", "fortnite"),
    ("Grand Theft Auto V", "grand-theft-auto-v"),
    ("Pokémon Legends: Z-A", "pokemon-legends-z-a"),
    ("EA SPORTS FC 25", "ea-sports-fc-25"),
    ("Tom Clancy's Rainbow Six Siege", "tom-clancy-s-rainbow-six-siege"),
    ("Café & Crème!", "cafe-creme"),
])
def test_slugify(name, slug):
    assert slugify(name) == slug


def test_detecta_la_pantalla_de_la_plantilla():
    box = compose.detect_screen_mask(Image.open(TEMPLATE)).getbbox()
    # Pantalla de la tele: aprox. x 204–498, y 629–881 (más la dilatación y el suavizado del borde)
    assert 198 <= box[0] <= 206 and 496 <= box[2] <= 505
    assert 623 <= box[1] <= 631 and 879 <= box[3] <= 888


def test_sin_zona_blanca_da_error_claro():
    with pytest.raises(ScreenNotFoundError, match="zona blanca"):
        compose.detect_screen_mask(Image.new("RGB", (100, 100), (20, 20, 20)))


@pytest.mark.parametrize("mode", ["cover", "contain"])
def test_compone_historia_1080x1920(mode):
    story = compose.compose(TEMPLATE, compose._test_game_image(), screen_fit=mode)
    assert story.size == (1080, 1920)


def test_encaje_por_defecto_es_cover():
    game = compose._test_game_image()
    default = np.asarray(compose.compose(TEMPLATE, game))
    assert np.array_equal(default, np.asarray(compose.compose(TEMPLATE, game, screen_fit="cover")))
    assert not np.array_equal(default, np.asarray(compose.compose(TEMPLATE, game, screen_fit="contain")))


def test_encaje_desconocido_da_error_claro():
    with pytest.raises(ValueError, match="screen_fit"):
        compose.compose(TEMPLATE, compose._test_game_image(), screen_fit="entera")


def test_cover_rellena_la_pantalla_con_imagen_muy_ancha():
    wide = Image.new("RGB", (2520, 1080), (200, 30, 30))  # 21:9
    story = compose.compose(TEMPLATE, wide, screen_fit="cover")
    # En la franja superior de la pantalla (donde "contain" pondría banda negra) tiene que haber imagen
    assert story.getpixel((400, 740))[0] > 150


def test_sin_borde_blanco_alrededor_de_la_pantalla():
    template = Image.open(TEMPLATE)
    mask = np.asarray(compose.detect_screen_mask(template)) > 0
    ring = ndimage.binary_dilation(mask, iterations=4) & ~ndimage.binary_erosion(mask, iterations=4)
    story = compose.compose(TEMPLATE, compose._test_game_image())
    # Deshacer el reescalado para comparar en coordenadas de la plantilla
    scale = min(1080 / template.width, 1920 / template.height)
    w, h = round(template.width * scale), round(template.height * scale)
    ox, oy = (1080 - w) // 2, (1920 - h) // 2
    back = np.asarray(story.crop((ox, oy, ox + w, oy + h)).resize(template.size)).astype(int)
    white = (back.min(axis=2) > 225) & (np.ptp(back, axis=2) < 25)
    assert int((white & ring).sum()) == 0


def test_save_story_deja_solo_la_ultima_del_juego(tmp_path):
    for name in ["20260101_1000_fortnite.jpg", "20260102_1000_fortnite.jpg", "20260101_1000_minecraft.jpg",
                 "comparar_fortnite.jpg", "20260101_1000_fortnite-battle.jpg"]:
        (tmp_path / name).write_bytes(b"x")
    path = save_story(Image.new("RGB", (10, 10)), tmp_path, "Fortnite")
    left = sorted(p.name for p in tmp_path.iterdir())
    assert [n for n in left if n[:8].isdigit() and n.endswith("_fortnite.jpg")] == [path.name]
    # Lo de otros juegos y los archivos de prueba no se tocan
    assert {"20260101_1000_minecraft.jpg", "comparar_fortnite.jpg", "20260101_1000_fortnite-battle.jpg"} <= set(left)


def test_find_existing_story(tmp_path):
    for name in ["20260924_1123_prueba-crt.jpg", "comparar_fortnite_entera.jpg", "20260923_2359_fortnite.jpg",
                 "20260924_0910_fortnite.jpg", "20260925_0800_fortnite-battle-royale.jpg", "fortnite.jpg",
                 "20260924_0910_fortnite.png"]:
        (tmp_path / name).write_bytes(b"x")
    found = find_existing_story(tmp_path, "Fortnite")
    assert found.name == "20260924_0910_fortnite.jpg"
    assert story_date(found) == "24/09 09:10"
    assert find_existing_story(tmp_path, "Minecraft") is None
    assert find_existing_story(tmp_path / "no-existe", "Fortnite") is None
