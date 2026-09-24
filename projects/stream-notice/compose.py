"""Detección de la pantalla de la tele en la plantilla y composición de la historia."""

import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from scipy import ndimage

STORY_SIZE = (1080, 1920)
JPEG_QUALITY = 95

# Umbrales para considerar un píxel "casi blanco"
WHITE_MIN = 225
WHITE_MAX_SPREAD = 25
DILATE_PX = 2

# Efecto CRT: sutil, acorde al estilo de dibujo
SCANLINE_STEP = 3
SCANLINE_OPACITY = 0.12
VIGNETTE_STRENGTH = 0.35


class ScreenNotFoundError(Exception):
    """La plantilla no tiene ninguna zona blanca que usar como pantalla."""


def slugify(name: str) -> str:
    """'Fortnite' → 'fortnite', 'Grand Theft Auto V' → 'grand-theft-auto-v', 'Pokémon' → 'pokemon'."""
    # Quitar tildes antes, para que "é" quede como "e" y no como guion
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def detect_screen_mask(template: Image.Image) -> Image.Image:
    """Devuelve una máscara (modo L, tamaño de la plantilla) con la pantalla de la tele."""
    rgb = np.asarray(template.convert("RGB")).astype(np.int16)
    white = (rgb.min(axis=2) > WHITE_MIN) & (np.ptp(rgb, axis=2) < WHITE_MAX_SPREAD)

    labels, count = ndimage.label(white)
    if count == 0:
        raise ScreenNotFoundError(
            "No se ha encontrado ninguna zona blanca en la plantilla para usar como pantalla."
        )

    # La pantalla es el componente blanco más grande (los guantes o la camiseta son menores)
    sizes = ndimage.sum(white, labels, range(1, count + 1))
    screen = labels == (int(np.argmax(sizes)) + 1)
    screen = ndimage.binary_fill_holes(screen)
    # Dilatar para tapar el borde antialiasado entre la pantalla y el marco
    screen = ndimage.binary_dilation(screen, iterations=DILATE_PX)

    mask = Image.fromarray((screen * 255).astype(np.uint8), mode="L")
    return mask.filter(ImageFilter.GaussianBlur(1))


def apply_crt(image: Image.Image) -> Image.Image:
    """Scanlines oscuras cada pocos píxeles y una viñeta suave en los bordes."""
    pixels = np.asarray(image.convert("RGB")).astype(np.float32)
    height, width = pixels.shape[:2]

    factor = np.ones((height, width), dtype=np.float32)
    factor[::SCANLINE_STEP, :] *= 1 - SCANLINE_OPACITY

    # Viñeta: 1 en el centro, baja hacia las esquinas
    ys = np.linspace(-1, 1, height)[:, None]
    xs = np.linspace(-1, 1, width)[None, :]
    distance = np.sqrt(xs**2 + ys**2) / np.sqrt(2)
    factor *= 1 - VIGNETTE_STRENGTH * distance**2

    result = np.clip(pixels * factor[:, :, None], 0, 255).astype(np.uint8)
    return Image.fromarray(result, mode="RGB")


def fit_to_story(image: Image.Image) -> Image.Image:
    """Reescala a 1080×1920 manteniendo la proporción y rellena el hueco con el color del borde."""
    if image.size == STORY_SIZE:
        return image

    scale = min(STORY_SIZE[0] / image.width, STORY_SIZE[1] / image.height)
    new_size = (round(image.width * scale), round(image.height * scale))
    resized = image.resize(new_size, Image.LANCZOS)

    # Color medio del contorno de la imagen, para que el relleno pase desapercibido
    edges = np.asarray(resized)
    border = np.concatenate([edges[0], edges[-1], edges[:, 0], edges[:, -1]])
    fill = tuple(int(c) for c in border.mean(axis=0))

    canvas = Image.new("RGB", STORY_SIZE, fill)
    offset = ((STORY_SIZE[0] - new_size[0]) // 2, (STORY_SIZE[1] - new_size[1]) // 2)
    canvas.paste(resized, offset)
    return canvas


def compose(template_path: Path, game_image: Image.Image, crt_effect: bool = True) -> Image.Image:
    """Mete la imagen del juego en la pantalla de la plantilla y devuelve la historia 1080×1920."""
    template = Image.open(template_path).convert("RGB")
    mask = detect_screen_mask(template)
    box = mask.getbbox()
    box_size = (box[2] - box[0], box[3] - box[1])

    # Tipo "cover": rellena la pantalla entera y recorta lo que sobre
    fitted = ImageOps.fit(game_image.convert("RGB"), box_size, Image.LANCZOS, centering=(0.5, 0.45))
    if crt_effect:
        fitted = apply_crt(fitted)

    # Pegar con la máscara recortada respeta las esquinas redondeadas de la tele
    template.paste(fitted, box[:2], mask.crop(box))
    return fit_to_story(template)


def save_story(image: Image.Image, output_folder: Path, game_name: str) -> Path:
    """Guarda como output/AAAAMMDD_HHMM_<slug>.jpg y devuelve la ruta."""
    output_folder.mkdir(parents=True, exist_ok=True)
    path = output_folder / f"{datetime.now():%Y%m%d_%H%M}_{slugify(game_name)}.jpg"
    image.save(path, "JPEG", quality=JPEG_QUALITY)
    return path


def _test_game_image() -> Image.Image:
    """Imagen horizontal de prueba: degradado, rejilla y texto centrado para ver el encuadre."""
    width, height = 1920, 1080
    xs = np.linspace(0, 1, width)[None, :]
    ys = np.linspace(0, 1, height)[:, None]
    pixels = np.stack(
        [255 * xs + 0 * ys, 80 + 120 * ys + 0 * xs, 255 * (1 - xs) + 0 * ys], axis=2
    ).astype(np.uint8)
    image = Image.fromarray(pixels, mode="RGB")

    draw = ImageDraw.Draw(image)
    for x in range(0, width, 120):
        draw.line([(x, 0), (x, height)], fill=(255, 255, 255), width=2)
    for y in range(0, height, 120):
        draw.line([(0, y), (width, y)], fill=(255, 255, 255), width=2)
    font = ImageFont.load_default(size=140)
    draw.text((width / 2, height * 0.45), "JUEGO DE PRUEBA", font=font, fill=(255, 255, 0),
              anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))
    return image


if __name__ == "__main__":
    # Prueba sin credenciales: python compose.py [imagen_del_juego]
    base = Path(__file__).parent
    if len(sys.argv) > 1:
        game = Image.open(sys.argv[1])
        name = Path(sys.argv[1]).stem
    else:
        game = _test_game_image()
        name = "prueba"

    for crt in (True, False):
        story = compose(base / "story-notice.png", game, crt_effect=crt)
        path = save_story(story, base / "output", f"{name}-{'crt' if crt else 'sin-crt'}")
        print(f"Imagen generada: {path} ({story.width}×{story.height})")
