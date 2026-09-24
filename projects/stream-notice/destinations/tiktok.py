"""Envía la historia como BORRADOR a la bandeja de TikTok (Content Posting API, modo MEDIA_UPLOAD).

TikTok no permite publicar en público de forma automática a una app personal sin auditar (y su auditoría no
admite herramientas para la propia cuenta), así que la foto llega a la bandeja y se termina en el móvil.

Configuración única: app en TikTok for Developers (Login Kit + Content Posting API, sandbox) con
client_key/client_secret en config.json, y autorizarla una vez con:
    python -m destinations.tiktok --login
Los tokens se guardan en tokens.json y se renuevan solos (el de renovación dura 365 días).
"""

import hashlib
import http.server
import json
import secrets
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests

import token_store

NAME = "TikTok (borrador)"
AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,video.upload"
REDIRECT_PORT = 3455
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback/"
TIMEOUT = 20
STATUS_TIMEOUT = 90
LOGIN_HELP = "Autoriza TikTok una vez con: python -m destinations.tiktok --login"


class TikTokError(Exception):
    pass


def _token_request(session: requests.Session, settings: dict, **data) -> dict:
    try:
        response = session.post(f"{API}/oauth/token/", timeout=TIMEOUT,
                                data={"client_key": settings["client_key"], "client_secret": settings["client_secret"], **data},
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
        body = response.json()
    except (requests.RequestException, ValueError) as error:
        raise TikTokError(f"No se pudo conectar con TikTok: {error}") from error
    if "access_token" not in body:
        raise TikTokError(f"TikTok rechazó el token: {body.get('error_description') or body.get('error') or body}. {LOGIN_HELP}")
    return body


def _store(body: dict):
    now = time.time()
    token_store.save("tiktok", {
        "access_token": body["access_token"], "expires_at": now + body.get("expires_in", 0),
        "refresh_token": body["refresh_token"], "refresh_expires_at": now + body.get("refresh_expires_in", 0),
        "open_id": body.get("open_id", ""), "scope": body.get("scope", "")})


def _access_token(settings: dict, session: requests.Session) -> str:
    stored = token_store.load("tiktok")
    if not stored.get("refresh_token"):
        raise TikTokError(f"TikTok no está autorizado todavía. {LOGIN_HELP}")
    if time.time() < stored.get("expires_at", 0) - 60:
        return stored["access_token"]
    if time.time() > stored.get("refresh_expires_at", 0):
        raise TikTokError(f"La autorización de TikTok ha caducado (dura 365 días). {LOGIN_HELP}")
    # El token de acceso dura 24 h: se renueva con el de renovación (que puede cambiar y hay que guardar)
    body = _token_request(session, settings, grant_type="refresh_token", refresh_token=stored["refresh_token"])
    _store(body)
    return body["access_token"]


def _api(session: requests.Session, token: str, path: str, payload: dict) -> dict:
    try:
        response = session.post(f"{API}/{path}", json=payload, timeout=TIMEOUT,
                                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"})
        body = response.json()
    except (requests.RequestException, ValueError) as error:
        raise TikTokError(f"No se pudo conectar con TikTok: {error}") from error
    error = body.get("error", {})
    if error.get("code", "ok") != "ok":
        if error.get("code") in ("access_token_invalid", "scope_not_authorized"):
            raise TikTokError(f"TikTok: {error.get('message') or error['code']}. {LOGIN_HELP}")
        if error.get("code") == "url_ownership_unverified":
            raise TikTokError("TikTok no reconoce la URL de la imagen: verifica el prefijo de URL en tu app de TikTok.")
        raise TikTokError(f"TikTok: {error.get('message') or error.get('code')}")
    return body.get("data", {})


def publish(image_path: Path, game_name: str, settings: dict, context, session: requests.Session | None = None) -> str:
    session = session or requests.Session()
    token = _access_token(settings, session)
    title = settings.get("title", "¡En directo! {game}").format(game=game_name)[:90]
    data = _api(session, token, "post/publish/content/init/", {
        "post_info": {"title": title, "description": settings.get("description", "").format(game=game_name)[:4000]},
        "source_info": {"source": "PULL_FROM_URL", "photo_cover_index": 0, "photo_images": [context.public_url()]},
        "post_mode": "MEDIA_UPLOAD",
        "media_type": "PHOTO",
    })
    publish_id = data["publish_id"]

    # TikTok descarga la foto y la manda a la bandeja; el estado se consulta con calma (30 peticiones/min)
    end = time.time() + STATUS_TIMEOUT
    while time.time() < end:
        time.sleep(4)
        status = _api(session, token, "post/publish/status/fetch/", {"publish_id": publish_id})
        if status.get("status") in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            return "borrador en tu bandeja de TikTok: termínalo en el móvil"
        if status.get("status") == "FAILED":
            raise TikTokError(f"TikTok no pudo procesar la foto ({status.get('fail_reason', 'sin motivo')}).")
    raise TikTokError("TikTok tarda demasiado en procesar la foto; revisa la bandeja más tarde.")


# --- Autorización única (python -m destinations.tiktok --login) ---

def login(settings: dict):
    """Abre el navegador para autorizar la app y guarda los tokens (PKCE para apps de escritorio)."""
    verifier = secrets.token_urlsafe(64)[:64]
    challenge = hashlib.sha256(verifier.encode()).hexdigest()  # TikTok escritorio: SHA256 en hexadecimal
    state = secrets.token_urlsafe(16)
    received = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            received.update({k: v[0] for k, v in query.items()})
            ok = "code" in received and received.get("state") == state
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            text = "TikTok autorizado. Ya puedes cerrar esta pestaña." if ok else "No se pudo autorizar TikTok."
            self.wfile.write(f"<h2 style='font-family:sans-serif'>{text}</h2>".encode("utf-8"))

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), Callback)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    url = AUTHORIZE_URL + "?" + urllib.parse.urlencode({
        "client_key": settings["client_key"], "response_type": "code", "scope": SCOPES,
        "redirect_uri": REDIRECT_URI, "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
    print("Abriendo el navegador para autorizar TikTok…")
    webbrowser.open(url)
    thread.join(timeout=300)
    server.server_close()
    if received.get("state") != state or "code" not in received:
        raise TikTokError(f"No llegó la autorización de TikTok: {received.get('error_description') or received.get('error') or 'sin respuesta'}")
    body = _token_request(requests.Session(), settings, code=received["code"], grant_type="authorization_code",
                          redirect_uri=REDIRECT_URI, code_verifier=verifier)
    _store(body)
    print(f"TikTok autorizado (permisos: {body.get('scope', '?')}). Los tokens se renuevan solos.")


if __name__ == "__main__":
    if "--login" not in sys.argv:
        sys.exit(__doc__)
    config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
    try:
        login(config["destinations"]["tiktok"])
    except (TikTokError, KeyError) as error:
        sys.exit(f"Error: {error}")
