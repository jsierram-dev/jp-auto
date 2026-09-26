"""Publicación en redes con las APIs simuladas: alojamiento en GitHub, Instagram y TikTok."""

import sys
import time
import types

import pytest

import hosting
import publish
import token_store
from destinations import instagram, tiktok, whatsapp


class _Response:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body if body is not None else {}

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def tokens_file(tmp_path, monkeypatch):
    # Nunca tocar el tokens.json real
    monkeypatch.setattr(token_store, "PATH", tmp_path / "tokens.json")
    monkeypatch.setattr(time, "sleep", lambda s: None)


@pytest.fixture
def story(tmp_path):
    path = tmp_path / "20260924_1421_fortnite.jpg"
    path.write_bytes(b"jpeg")
    return path


class _Context:
    def __init__(self, url="https://raw.githubusercontent.com/u/r/media/stories/1_x.jpg"):
        self.url, self.calls = url, 0

    def public_url(self):
        self.calls += 1
        return self.url


# --- Alojamiento en GitHub ---

class GitHubSession:
    def __init__(self, ref_exists=True, token_ok=True, raw_ready_after=1):
        self.ref_exists, self.token_ok, self.raw_ready_after = ref_exists, token_ok, raw_ready_after
        self.requests, self.heads = [], 0
        self.blobs = []

    def request(self, method, url, headers=None, json=None, **kwargs):
        self.requests.append((method, url.split("/repos/u/r/")[-1], json))
        if not self.token_ok:
            return _Response(401)
        if url.endswith("/git/blobs"):
            self.blobs.append(json)
            return _Response(201, {"sha": f"blob{len(self.blobs)}"})
        if url.endswith("/git/trees"):
            return _Response(201, {"sha": "tree1"})
        if url.endswith("/git/commits"):
            return _Response(201, {"sha": "commit1"})
        if method == "PATCH":
            return _Response(200) if self.ref_exists else _Response(422, {"message": "Reference does not exist"})
        if method == "POST" and url.endswith("/git/refs"):
            return _Response(201)
        return _Response(404)

    def head(self, url, **kwargs):
        self.heads += 1
        return _Response(200 if self.heads >= self.raw_ready_after else 404)


SETTINGS = {"github_token": "ghp_x", "repo": "u/r", "branch": "media",
            "static_files": {"tiktokABC.txt": "tiktok-developers-site-verification=ABC"}}


def test_hosting_sube_un_commit_huerfano_con_la_historia_y_los_fijos(story):
    session = GitHubSession(raw_ready_after=3)
    url = hosting.upload(story, SETTINGS, session)
    assert url.startswith("https://raw.githubusercontent.com/u/r/media/stories/") and url.endswith("_20260924_1421_fortnite.jpg")
    tree = next(body for method, path, body in session.requests if path == "git/trees")["tree"]
    assert sorted(entry["path"].split("/")[0] for entry in tree) == ["stories", "tiktokABC.txt"]
    commit = next(body for method, path, body in session.requests if path == "git/commits")
    assert commit["parents"] == []  # la rama nunca acumula historias antiguas
    patch = next(body for method, path, body in session.requests if method == "PATCH")
    assert patch == {"sha": "commit1", "force": True}
    assert session.heads == 3  # esperó a que la URL pública respondiera


def test_hosting_incluye_archivos_del_proyecto(story):
    session = GitHubSession()
    hosting.upload(story, {**SETTINGS, "project_files": {"legal/terms.md": "legal/terms.md"}}, session)
    tree = next(body for method, path, body in session.requests if path == "git/trees")["tree"]
    assert "legal/terms.md" in [entry["path"] for entry in tree]
    import base64
    assert any(base64.b64decode(blob["content"]).startswith(b"# Terms of Service") for blob in session.blobs)


def test_hosting_archivo_del_proyecto_inexistente(story):
    with pytest.raises(hosting.HostingError, match="no-existe.md"):
        hosting.upload(story, {**SETTINGS, "project_files": {"x.md": "no-existe.md"}}, GitHubSession())


def test_hosting_crea_la_rama_si_no_existe(story):
    session = GitHubSession(ref_exists=False)
    hosting.upload(story, SETTINGS, session)
    assert ("POST", "git/refs", {"ref": "refs/heads/media", "sha": "commit1"}) in session.requests


def test_hosting_token_rechazado(story):
    with pytest.raises(hosting.HostingError, match="token"):
        hosting.upload(story, SETTINGS, GitHubSession(token_ok=False))


def test_hosting_sin_configurar(story):
    with pytest.raises(hosting.HostingError, match="github_token"):
        hosting.upload(story, {}, GitHubSession())


def test_la_url_publica_se_sube_una_sola_vez_y_solo_si_hace_falta(monkeypatch, story):
    uploads = []
    monkeypatch.setattr(hosting, "upload", lambda path, settings: uploads.append(path) or "https://x/y.jpg")
    for key in ("fake_a", "fake_b"):
        module = types.ModuleType(f"destinations.{key}")
        module.publish = lambda image_path, game_name, settings, context: context.public_url()
        monkeypatch.setitem(sys.modules, f"destinations.{key}", module)
    local = types.ModuleType("destinations.fake_local")
    local.publish = lambda image_path, game_name, settings: "ok"
    monkeypatch.setitem(sys.modules, "destinations.fake_local", local)

    publish.publish(story, "Fortnite", {"destinations": {"fake_local": {"enabled": True}}})
    assert uploads == []
    progress = []
    results = publish.publish(story, "Fortnite", {"destinations": {"fake_a": {"enabled": True}, "fake_b": {"enabled": True}}},
                              on_progress=progress.append)
    assert uploads == [story] and all(r.ok for r in results)
    # Tras subir, vuelve a mostrar el destino en curso
    assert progress == ["Enviando a fake_a…", "Subiendo la historia a internet…", "Enviando a fake_a…", "Enviando a fake_b…"]


# --- Instagram ---

class InstagramSession:
    def __init__(self, statuses=("IN_PROGRESS", "FINISHED"), expired=False):
        self.statuses, self.expired = list(statuses), expired
        self.calls = []

    def request(self, method, url, params=None, data=None, **kwargs):
        path = url.split("graph.instagram.com/")[-1]
        args = params or data or {}
        self.calls.append((method, path, dict(args)))
        if self.expired:
            return _Response(400, {"error": {"code": 190, "message": "Error validating access token"}})
        if path == "refresh_access_token":
            return _Response(200, {"access_token": "renovado", "expires_in": 5184000})
        if path == "me":
            return _Response(200, {"user_id": "178", "username": "jscorpiodv"})
        if path == "178/media":
            return _Response(200, {"id": "container1"})
        if path == "container1":
            return _Response(200, {"status_code": self.statuses.pop(0)})
        if path == "178/media_publish":
            return _Response(200, {"id": "media1"})
        return _Response(404)


def test_instagram_publica_una_historia(story):
    session, context = InstagramSession(), _Context()
    message = instagram.publish(story, "Fortnite", {"access_token": "tok"}, context, session)
    assert message == "historia publicada en @jscorpiodv"
    create = next(args for method, path, args in session.calls if path == "178/media")
    assert create["media_type"] == "STORIES" and create["image_url"] == context.url
    assert ("POST", "178/media_publish", {"creation_id": "container1", "access_token": "tok"}) in session.calls
    assert token_store.load("instagram")["user_id"] == "178"


def test_instagram_renueva_el_token_con_mas_de_24_horas(story):
    token_store.save("instagram", {"seed": "tok", "access_token": "viejo", "obtained_at": time.time() - 25 * 3600,
                                   "user_id": "178", "username": "jscorpiodv"})
    session = InstagramSession()
    instagram.publish(story, "Fortnite", {"access_token": "tok"}, _Context(), session)
    assert session.calls[0][1] == "refresh_access_token"
    assert token_store.load("instagram")["access_token"] == "renovado"
    create = next(args for method, path, args in session.calls if path == "178/media")
    assert create["access_token"] == "renovado"


def test_instagram_un_token_nuevo_en_config_sustituye_al_guardado(story):
    token_store.save("instagram", {"seed": "antiguo", "access_token": "antiguo-renovado", "obtained_at": time.time(),
                                   "user_id": "178"})
    session = InstagramSession()
    instagram.publish(story, "Fortnite", {"access_token": "nuevo"}, _Context(), session)
    assert token_store.load("instagram")["access_token"] == "nuevo"


def test_instagram_token_caducado_explica_que_hacer(story):
    with pytest.raises(instagram.InstagramError, match="Generate token"):
        instagram.publish(story, "Fortnite", {"access_token": "tok"}, _Context(), InstagramSession(expired=True))


def test_instagram_imagen_con_error_no_se_publica(story):
    session = InstagramSession(statuses=("ERROR",))
    with pytest.raises(instagram.InstagramError, match="no pudo procesar"):
        instagram.publish(story, "Fortnite", {"access_token": "tok"}, _Context(), session)
    assert not any(path == "178/media_publish" for method, path, args in session.calls)


def test_instagram_sin_token_configurado(story):
    with pytest.raises(instagram.InstagramError, match="access_token"):
        instagram.publish(story, "Fortnite", {"access_token": "TU_TOKEN_DE_INSTAGRAM"}, _Context(), InstagramSession())


# --- TikTok ---

class TikTokSession:
    def __init__(self, statuses=("PROCESSING_DOWNLOAD", "SEND_TO_USER_INBOX"), init_error=None):
        self.statuses, self.init_error = list(statuses), init_error
        self.posts = []

    def post(self, url, json=None, data=None, headers=None, **kwargs):
        path = url.split("open.tiktokapis.com/v2/")[-1]
        self.posts.append((path, json or data, headers))
        if path == "oauth/token/":
            return _Response(200, {"access_token": "acc2", "expires_in": 86400, "refresh_token": "ref2",
                                   "refresh_expires_in": 31536000, "open_id": "o1", "scope": "user.info.basic,video.upload"})
        if path == "post/publish/content/init/":
            if self.init_error:
                return _Response(403, {"error": {"code": self.init_error, "message": "x"}})
            return _Response(200, {"data": {"publish_id": "p1"}, "error": {"code": "ok"}})
        if path == "post/publish/status/fetch/":
            return _Response(200, {"data": {"status": self.statuses.pop(0)}, "error": {"code": "ok"}})
        return _Response(404)


TT = {"client_key": "ck", "client_secret": "cs", "title": "¡En directo! {game}"}


def _authorized(expired=False):
    now = time.time()
    token_store.save("tiktok", {"access_token": "acc1", "expires_at": now - 10 if expired else now + 3600,
                                "refresh_token": "ref1", "refresh_expires_at": now + 3600 * 24 * 300, "open_id": "o1"})


def test_tiktok_envia_la_foto_como_borrador(story):
    _authorized()
    session, context = TikTokSession(), _Context()
    message = tiktok.publish(story, "Fortnite", TT, context, session)
    assert "borrador" in message
    path, body, headers = session.posts[0]
    assert path == "post/publish/content/init/" and headers["Authorization"] == "Bearer acc1"
    assert body["post_mode"] == "MEDIA_UPLOAD" and body["media_type"] == "PHOTO"
    assert body["source_info"] == {"source": "PULL_FROM_URL", "photo_cover_index": 0, "photo_images": [context.url]}
    assert body["post_info"]["title"] == "¡En directo! Fortnite"


def test_tiktok_renueva_el_token_de_24_horas_y_guarda_el_nuevo_de_renovacion(story):
    _authorized(expired=True)
    session = TikTokSession()
    tiktok.publish(story, "Fortnite", TT, _Context(), session)
    path, body, _ = session.posts[0]
    assert path == "oauth/token/" and body["grant_type"] == "refresh_token" and body["refresh_token"] == "ref1"
    stored = token_store.load("tiktok")
    assert (stored["access_token"], stored["refresh_token"]) == ("acc2", "ref2")


def test_tiktok_sin_autorizar_explica_el_comando(story):
    with pytest.raises(tiktok.TikTokError, match="--login"):
        tiktok.publish(story, "Fortnite", TT, _Context(), TikTokSession())


def test_tiktok_url_sin_verificar(story):
    _authorized()
    with pytest.raises(tiktok.TikTokError, match="prefijo de URL"):
        tiktok.publish(story, "Fortnite", TT, _Context(), TikTokSession(init_error="url_ownership_unverified"))


def test_tiktok_fallo_al_procesar(story):
    _authorized()
    with pytest.raises(tiktok.TikTokError, match="no pudo procesar"):
        tiktok.publish(story, "Fortnite", TT, _Context(), TikTokSession(statuses=("FAILED",)))


# --- Canal de WhatsApp (Whapi) ---

WA = {"token": "tok", "channel_id": "120363000000000000@newsletter", "link": "https://twitch.tv/jscorpiodv"}


class WhapiSession:
    def __init__(self, status=200, body=None, fail=False):
        self.status, self.body, self.fail = status, body, fail
        self.calls = []

    def post(self, url, headers=None, data=None, files=None, **kwargs):
        if self.fail:
            raise whatsapp.requests.ConnectionError("sin red")
        name, handle, mime = files["media"]
        self.calls.append((url, headers, data, name, handle.read(), mime))
        body = self.body if self.body is not None else {"sent": True, "message": {"id": "m1"}}
        return _Response(self.status, body)


def test_whatsapp_envia_la_imagen_con_pie_y_enlace_al_canal(story):
    session = WhapiSession()
    assert whatsapp.publish(story, "Fortnite", WA, session) == "aviso publicado en el canal"
    url, headers, data, name, content, mime = session.calls[0]
    assert url == "https://gate.whapi.cloud/messages/image"
    assert headers == {"Authorization": "Bearer tok"}
    assert data["to"] == WA["channel_id"]
    assert data["caption"] == "🔴 ¡En directo! Hoy toca Fortnite\nhttps://twitch.tv/jscorpiodv"
    assert (name, content, mime) == (story.name, b"jpeg", "image/jpeg")


def test_whatsapp_pie_personalizado(story):
    session = WhapiSession()
    whatsapp.publish(story, "Tetris", {**WA, "caption": "{game} ya → {link}", "link": "https://x.tv/y"}, session)
    assert session.calls[0][2]["caption"] == "Tetris ya → https://x.tv/y"


def test_whatsapp_no_necesita_la_url_publica():
    import inspect
    assert "context" not in inspect.signature(whatsapp.publish).parameters


@pytest.mark.parametrize("settings, match", [
    ({**WA, "token": "TU_TOKEN_DE_WHAPI"}, "whatsapp.token"),
    ({**WA, "channel_id": ""}, "whatsapp.channel_id"),
    ({**WA, "channel_id": "34600000000"}, "@newsletter"),
])
def test_whatsapp_configuracion_incompleta_no_llama_a_la_api(story, settings, match):
    session = WhapiSession()
    with pytest.raises(whatsapp.WhatsAppError, match=match):
        whatsapp.publish(story, "Fortnite", settings, session)
    assert session.calls == []


@pytest.mark.parametrize("status, match", [
    (401, "vuelve a escanear el QR"),
    (402, "límite del plan gratuito"),
    (403, "administrador"),
    (429, "limitado"),
])
def test_whatsapp_errores_conocidos_explican_que_hacer(story, status, match):
    with pytest.raises(whatsapp.WhatsAppError, match=match):
        whatsapp.publish(story, "Fortnite", WA, WhapiSession(status, {"error": {"code": status}}))


def test_whatsapp_error_desconocido_muestra_el_mensaje_de_whapi(story):
    with pytest.raises(whatsapp.WhatsAppError, match="Whapi: algo raro"):
        whatsapp.publish(story, "Fortnite", WA, WhapiSession(500, {"error": {"message": "algo raro"}}))


@pytest.mark.parametrize("game, caption, expected", [
    ("Tetris", "Hoy {game} :-{ }", "Hoy Tetris :-{ }"),
    ("Tetris {Remix}", "{game} {link}", "Tetris {Remix} https://twitch.tv/jscorpiodv"),
    ("Tetris", "🔴 {game}", "🔴 Tetris"),
])
def test_whatsapp_pie_con_llaves_o_emoji_no_rompe(story, game, caption, expected):
    session = WhapiSession()
    whatsapp.publish(story, game, {**WA, "caption": caption, "link": "https://twitch.tv/jscorpiodv"}, session)
    assert session.calls[0][2]["caption"] == expected


@pytest.mark.parametrize("body", [{"error": "texto suelto"}, ["raro"], "raro"])
def test_whatsapp_error_con_formato_inesperado_da_mensaje_claro(story, body):
    with pytest.raises(whatsapp.WhatsAppError, match="Whapi"):
        whatsapp.publish(story, "Fortnite", WA, WhapiSession(500, body))


def test_whatsapp_respuesta_sin_enviar(story):
    with pytest.raises(whatsapp.WhatsAppError, match="Whapi"):
        whatsapp.publish(story, "Fortnite", WA, WhapiSession(200, {"sent": False}))


def test_whatsapp_sin_conexion(story):
    with pytest.raises(whatsapp.WhatsAppError, match="No se pudo conectar"):
        whatsapp.publish(story, "Fortnite", WA, WhapiSession(fail=True))


def test_whatsapp_falla_y_los_demas_destinos_siguen(monkeypatch, story):
    monkeypatch.setattr(whatsapp, "requests", types.SimpleNamespace(
        Session=lambda: WhapiSession(401, {}), RequestException=Exception, ConnectionError=Exception))
    opened = []
    monkeypatch.setattr(publish.importlib, "import_module", lambda name: {
        "destinations.whatsapp": whatsapp,
        "destinations.open_image": types.SimpleNamespace(
            NAME="Abrir en el PC", publish=lambda p, g, s: opened.append(p) or "imagen abierta"),
    }[name])
    config = {"destinations": {"whatsapp": {**WA, "enabled": True}, "open_image": {"enabled": True}}}
    results = publish.publish(story, "Fortnite", config)
    assert [(r.name, r.ok) for r in results] == [("Canal de WhatsApp", False), ("Abrir en el PC", True)]
    assert "QR" in results[0].message and opened == [story]
