"""Publica la historia en un canal de WhatsApp a través de Whapi.cloud (plan gratuito, Developer Sandbox).

WhatsApp no tiene API oficial para canales: Whapi vincula tu número como un dispositivo más (como WhatsApp Web)
escaneando un QR en su panel. Configuración única en config.json (destinations.whatsapp):
  - token: el token del canal de Whapi (panel → tu canal → API token).
  - channel_id: el id del canal de WhatsApp, con la forma 1234567890@newsletter (GET /newsletters en su panel).
  - caption / link: pie de foto; {game} se cambia por el juego y {link} por el enlace al directo.

La imagen se envía directamente (multipart): no hace falta la URL pública de GitHub.
Cada aviso gasta una sola petición, muy por debajo de los límites del plan gratuito.
"""

import mimetypes
from pathlib import Path

import requests

import tls  # noqa: F401 (certificados de Windows, por los antivirus que analizan HTTPS)

NAME = "Canal de WhatsApp"
API = "https://gate.whapi.cloud"
TIMEOUT = 30
DEFAULT_CAPTION = "🔴 ¡En directo! Hoy toca {game}\n{link}"
DEFAULT_LINK = "https://twitch.tv/jscorpiodv"

ERRORS = {
    401: "La sesión de WhatsApp en Whapi se ha desvinculado o el token no es válido: "
         "vuelve a escanear el QR en el panel de Whapi y revisa destinations.whatsapp.token.",
    402: "Se ha alcanzado el límite del plan gratuito de Whapi; no se ha publicado (no se usa el plan de pago).",
    403: "WhatsApp no deja publicar en ese canal: comprueba que tu número es administrador y el channel_id.",
    413: "La imagen es demasiado grande para WhatsApp.",
    429: "Whapi ha limitado las peticiones; inténtalo de nuevo en un rato.",
}


class WhatsAppError(Exception):
    pass


def _setting(settings: dict, key: str) -> str:
    value = settings.get(key)
    value = "" if value is None else str(value).strip()
    if not value or value.startswith("TU_"):
        raise WhatsAppError(f"Falta destinations.whatsapp.{key} en config.json.")
    return value


def publish(image_path: Path, game_name: str, settings: dict, session: requests.Session | None = None) -> str:
    token = _setting(settings, "token")
    channel_id = _setting(settings, "channel_id")
    if not channel_id.endswith("@newsletter"):
        raise WhatsAppError("destinations.whatsapp.channel_id debe tener la forma 1234567890@newsletter.")
    # replace() y no format(): un pie de foto propio con llaves sueltas (":-{ }") no debe romper el aviso
    caption = settings.get("caption")
    link = settings.get("link")
    caption = DEFAULT_CAPTION if caption is None else str(caption)
    link = DEFAULT_LINK if link is None else str(link)
    caption = caption.replace("{game}", game_name).replace("{link}", link)

    session = session or requests.Session()
    mime = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    try:
        with open(image_path, "rb") as image:
            response = session.post(f"{API}/messages/image", headers={"Authorization": f"Bearer {token}"},
                                    data={"to": channel_id, "caption": caption},
                                    files={"media": (image_path.name, image, mime)}, timeout=TIMEOUT)
    except requests.RequestException as error:
        raise WhatsAppError(f"No se pudo conectar con Whapi: {error}") from error

    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    if not response.ok or not body.get("sent", False):
        if response.status_code in ERRORS:
            raise WhatsAppError(ERRORS[response.status_code])
        error = body.get("error")
        detail = (error.get("message") if isinstance(error, dict) else error) or f"HTTP {response.status_code}"
        raise WhatsAppError(f"Whapi: {detail}")
    return "aviso publicado en el canal"
