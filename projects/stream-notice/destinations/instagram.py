"""Publica la historia en Instagram con la API oficial (Instagram API with Instagram Login).

Configuración única: cuenta profesional + app en Meta for Developers → "API setup with Instagram login"
→ "Generate token", y ese token en config.json (destinations.instagram.access_token).
El programa lo renueva solo (dura 60 días) y guarda el vigente en tokens.json.
"""

import time
from pathlib import Path

import requests

import token_store
import tls  # noqa: F401 (certificados de Windows, por los antivirus que analizan HTTPS)

NAME = "Instagram"
API = "https://graph.instagram.com"
TIMEOUT = 20
REFRESH_AFTER_SECONDS = 24 * 3600      # la API solo deja renovar tokens con más de 24 h
PROCESSING_TIMEOUT = 90
EXPIRED_HELP = ("El token de Instagram ha caducado o no es válido. Genera uno nuevo en Meta for Developers "
                "(tu app → Instagram → API setup with Instagram login → Generate token) y ponlo en config.json.")


class InstagramError(Exception):
    pass


def _call(session: requests.Session, method: str, path: str, **params) -> dict:
    try:
        response = session.request(method, f"{API}/{path}", params=params if method == "GET" else None,
                                   data=params if method != "GET" else None, timeout=TIMEOUT)
    except requests.RequestException as error:
        raise InstagramError(f"No se pudo conectar con Instagram: {error}") from error
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not response.ok or "error" in body:
        error = body.get("error", {})
        if error.get("code") == 190 or response.status_code == 401:
            raise InstagramError(EXPIRED_HELP)
        raise InstagramError(f"Instagram: {error.get('message') or f'HTTP {response.status_code}'}")
    return body


def _token(settings: dict, session: requests.Session) -> dict:
    """Token vigente (renovado si hace falta) y el id de la cuenta."""
    configured = settings.get("access_token", "")
    if not configured or configured.startswith("TU_"):
        raise InstagramError("Falta destinations.instagram.access_token en config.json.")
    stored = token_store.load("instagram")
    # Si el usuario ha puesto un token nuevo en config.json, manda ese
    if stored.get("seed") != configured:
        stored = {"seed": configured, "access_token": configured, "obtained_at": time.time()}

    if time.time() - stored.get("obtained_at", 0) > REFRESH_AFTER_SECONDS:
        refreshed = _call(session, "GET", "refresh_access_token", grant_type="ig_refresh_token",
                          access_token=stored["access_token"])
        stored.update(access_token=refreshed["access_token"], obtained_at=time.time())
        print("  Token de Instagram renovado (vale 60 días más).")

    if not stored.get("user_id"):
        me = _call(session, "GET", "me", fields="user_id,username", access_token=stored["access_token"])
        stored.update(user_id=me["user_id"], username=me.get("username", ""))
    token_store.save("instagram", stored)
    return stored


def publish(image_path: Path, game_name: str, settings: dict, context, session: requests.Session | None = None) -> str:
    session = session or requests.Session()
    account = _token(settings, session)
    token, user_id = account["access_token"], account["user_id"]

    container = _call(session, "POST", f"{user_id}/media", media_type="STORIES",
                      image_url=context.public_url(), access_token=token)["id"]

    # Instagram descarga y procesa la imagen: esperar a que esté lista antes de publicar
    end = time.time() + PROCESSING_TIMEOUT
    while True:
        status = _call(session, "GET", container, fields="status_code", access_token=token).get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise InstagramError(f"Instagram no pudo procesar la imagen (estado {status}).")
        if time.time() > end:
            raise InstagramError("Instagram tarda demasiado en procesar la imagen; no se ha publicado.")
        time.sleep(3)

    _call(session, "POST", f"{user_id}/media_publish", creation_id=container, access_token=token)
    who = f" en @{account['username']}" if account.get("username") else ""
    return f"historia publicada{who}"
