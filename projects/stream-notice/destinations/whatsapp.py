"""Publica la historia en un canal de WhatsApp con neonize (el protocolo de WhatsApp Web, sin navegador ni terceros).

WhatsApp no tiene API oficial para canales: el programa se vincula a tu número como un dispositivo más
(igual que WhatsApp Web). Configuración única:
    python -m destinations.whatsapp --login
enseña un QR para escanearlo desde el móvil (WhatsApp → Dispositivos vinculados) y lista los canales en los
que puedes publicar, con su id. En config.json (destinations.whatsapp):
  - channel_id: el id del canal, con la forma 1234567890@newsletter.
  - caption / link: pie de foto; {game} se cambia por el juego y {link} por el enlace al directo.

La sesión se guarda en whatsapp_session.sqlite3 (git la ignora). Caduca si el móvil pasa ~14 días sin conexión
o si se cierra desde el móvil: entonces hay que volver a vincular. Es un cliente no oficial: un aviso por
directo está bien, pero nunca envíos masivos.
"""

import hashlib
import logging
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from neonize.client import NewClient
from neonize.events import ConnectedEv, ConnectFailureEv, LoggedOutEv, TemporaryBanEv
from neonize.proto.Neonize_pb2 import NewsletterRole
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import ImageMessage, Message
from neonize.utils.enum import MediaType
from neonize.utils.jid import build_jid

# neonize configura el logging raíz a INFO al importarse y vuelca los mensajes internos de WhatsApp. Se callan:
# al desconectar justo tras enviar, whatsmeow registra como ERROR la sincronización que deja a medias, y los
# fallos reales ya llegan como eventos con un mensaje propio
logging.getLogger().setLevel(logging.WARNING)
for _name in ("neonize", "neonize.utils.log", "whatsmeow", "Whatsmeow"):
    logging.getLogger(_name).setLevel(logging.CRITICAL)

NAME = "Canal de WhatsApp"
SESSION_PATH = Path(__file__).resolve().parents[1] / "whatsapp_session.sqlite3"
CONNECT_TIMEOUT = 30
LOGIN_TIMEOUT = 300
DEFAULT_CAPTION = "🔴 ¡En directo! Hoy toca {game}\n{link}"
DEFAULT_LINK = "https://twitch.tv/jscorpiodv"
LOGIN_HELP = "Vincula WhatsApp con: python -m destinations.whatsapp --login"


class WhatsAppError(Exception):
    pass


@contextmanager
def _connect(session_path: Path, timeout: float = CONNECT_TIMEOUT, on_qr=None):
    """Conecta con la sesión guardada y la cierra al salir.

    Sin on_qr (publicar en segundo plano) nunca se enseña un QR: si la sesión no vale, falla con LOGIN_HELP.
    """
    client = NewClient(str(session_path))
    ready = threading.Event()
    failure = {}

    def fail(message):
        failure.setdefault("message", message)
        ready.set()

    @client.event.qr
    def _qr(_, data: bytes):
        if on_qr:
            on_qr(data)
        else:
            fail(f"La sesión de WhatsApp ya no es válida. {LOGIN_HELP}")

    client.event(ConnectedEv)(lambda *_: ready.set())
    client.event(LoggedOutEv)(lambda *_: fail(f"Se ha cerrado la sesión de WhatsApp desde el móvil. {LOGIN_HELP}"))
    client.event(TemporaryBanEv)(lambda *_: fail("WhatsApp ha bloqueado temporalmente este número; no se ha publicado."))
    client.event(ConnectFailureEv)(lambda _, ev: fail(f"WhatsApp rechazó la conexión ({ev.Message or ev.Reason}). {LOGIN_HELP}"))

    # connect() bloquea hasta que se llama a stop(): va en su propio hilo
    worker = threading.Thread(target=client.connect, daemon=True)
    worker.start()
    try:
        if not ready.wait(timeout):
            raise WhatsAppError("WhatsApp no responde; comprueba la conexión a internet.")
        if failure:
            raise WhatsAppError(failure["message"])
        yield client
    finally:
        client.stop()
        worker.join(10)
        # neonize vuelve a parar el cliente al recolectarlo: se adelanta aquí para que no pare uno posterior
        # con la misma sesión (el siguiente directo)
        client._stop_finalizer()


def _caption(settings: dict, game_name: str) -> str:
    # replace() y no format(): un pie de foto propio con llaves sueltas (":-{ }") no debe romper el aviso
    caption = settings.get("caption")
    link = settings.get("link")
    caption = DEFAULT_CAPTION if caption is None else str(caption)
    link = DEFAULT_LINK if link is None else str(link)
    return caption.replace("{game}", game_name).replace("{link}", link)


def _channel(settings: dict) -> str:
    channel_id = settings.get("channel_id")
    channel_id = "" if channel_id is None else str(channel_id).strip()
    if not channel_id or channel_id.startswith("TU_"):
        raise WhatsAppError(f"Falta destinations.whatsapp.channel_id en config.json. {LOGIN_HELP} para ver el id.")
    if not channel_id.endswith("@newsletter") or not channel_id.split("@")[0].isdigit():
        raise WhatsAppError("destinations.whatsapp.channel_id debe tener la forma 1234567890@newsletter.")
    return channel_id


def publish(image_path: Path, game_name: str, settings: dict, connect=_connect) -> str:
    channel_id = _channel(settings)
    if not SESSION_PATH.is_file():
        raise WhatsAppError(f"WhatsApp no está vinculado todavía. {LOGIN_HELP}")
    data = Path(image_path).read_bytes()
    with connect(SESSION_PATH) as client:
        try:
            # En los canales la imagen va sin cifrar: se sube con upload_newsletter, no con upload
            upload = client.upload_newsletter(data, MediaType.MediaImage)
            message = Message(imageMessage=ImageMessage(
                URL=upload.url, directPath=upload.DirectPath, fileSHA256=hashlib.sha256(data).digest(),
                fileLength=len(data), mimetype="image/jpeg", caption=_caption(settings, game_name)))
            user, server = channel_id.split("@")
            client.send_message(build_jid(user, server), message)
        except Exception as error:
            raise WhatsAppError(f"WhatsApp no ha aceptado el aviso ({error or type(error).__name__}): "
                                "comprueba que eres propietario o administrador del canal y el channel_id.") from error
    return "aviso publicado en el canal"


# --- Vinculación única (python -m destinations.whatsapp --login) ---

def _show_qr(data: bytes):
    import segno  # viene con neonize
    path = SESSION_PATH.with_name("whatsapp_qr.png")
    segno.make_qr(data).save(path, scale=10)
    print("Escanea el QR desde el móvil: WhatsApp → Dispositivos vinculados → Vincular un dispositivo.")
    print(f"(Si no se abre solo, está en {path}. Caduca en unos segundos y se genera otro.)")
    if hasattr(os, "startfile"):
        os.startfile(path)


def login():
    """Vincula el número (QR si hace falta) y lista los canales en los que se puede publicar."""
    with _connect(SESSION_PATH, LOGIN_TIMEOUT, on_qr=_show_qr) as client:
        channels = [n for n in client.get_subscribed_newletters()
                    if n.ViewerMeta.Role in (NewsletterRole.OWNER, NewsletterRole.ADMIN)]
    SESSION_PATH.with_name("whatsapp_qr.png").unlink(missing_ok=True)
    print("WhatsApp vinculado. La sesión queda guardada en whatsapp_session.sqlite3.")
    if not channels:
        print("No eres propietario ni administrador de ningún canal: crea uno en WhatsApp → Novedades.")
        return
    print("Canales en los que puedes publicar (copia el id a destinations.whatsapp.channel_id en config.json):")
    for n in channels:
        print(f"  - {n.ThreadMeta.Name.Text}: {n.ID.User}@{n.ID.Server}")


if __name__ == "__main__":
    if "--login" not in sys.argv:
        sys.exit(__doc__)
    try:
        login()
    except WhatsAppError as error:
        sys.exit(f"Error: {error}")
