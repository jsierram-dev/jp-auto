"""Aloja la historia en una URL pública (la necesitan Instagram y TikTok): rama `media` de un repo público de GitHub.

En cada publicación la rama se sustituye por un único commit, sin padres, con la historia actual y los archivos
fijos (p. ej. el de verificación de TikTok). Así la rama nunca acumula imágenes antiguas ni toca `main`.
"""

import base64
import time
from pathlib import Path

import requests

import tls  # noqa: F401 (certificados de Windows, por los antivirus que analizan HTTPS)

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
TIMEOUT = 20
# raw.githubusercontent.com tarda unos segundos en servir un commit nuevo
AVAILABILITY_TIMEOUT = 60


class HostingError(Exception):
    """Error con mensaje claro para el popup."""


def _request(session: requests.Session, method: str, url: str, token: str, **kwargs) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    try:
        response = session.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as error:
        raise HostingError(f"No se pudo conectar con GitHub: {error}") from error
    if response.status_code == 401:
        raise HostingError("GitHub ha rechazado el token: revisa hosting.github_token en config.json (¿ha caducado?).")
    if response.status_code == 403:
        raise HostingError("El token de GitHub no tiene permiso para escribir en el repo (Contents: Read and write).")
    if response.status_code == 404 and "/git/refs/heads/" not in url:
        raise HostingError("GitHub no encuentra el repo: revisa hosting.repo en config.json y que el token tenga acceso.")
    return response


def upload(image_path: Path, settings: dict, session: requests.Session | None = None) -> str:
    """Sube la historia y devuelve su URL pública, esperando a que ya se pueda descargar."""
    session = session or requests.Session()
    token, repo = settings.get("github_token", ""), settings.get("repo", "")
    branch = settings.get("branch", "media")
    if not token or not repo:
        raise HostingError("Falta hosting.github_token o hosting.repo en config.json.")

    # Nombre único: raw.githubusercontent.com cachea cada ruta unos minutos
    name = f"stories/{int(time.time())}_{Path(image_path).name}"
    files = {name: Path(image_path).read_bytes()}
    files.update({path: content.encode("utf-8") for path, content in settings.get("static_files", {}).items()})

    tree = []
    for path, content in files.items():
        blob = _request(session, "POST", f"{API}/repos/{repo}/git/blobs", token,
                        json={"content": base64.b64encode(content).decode(), "encoding": "base64"})
        if not blob.ok:
            raise HostingError(f"GitHub no aceptó el archivo {path} (HTTP {blob.status_code}).")
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob.json()["sha"]})

    new_tree = _request(session, "POST", f"{API}/repos/{repo}/git/trees", token, json={"tree": tree})
    if not new_tree.ok:
        raise HostingError(f"GitHub no dejó crear el árbol del commit (HTTP {new_tree.status_code}).")
    commit = _request(session, "POST", f"{API}/repos/{repo}/git/commits", token,
                      json={"message": f"Historia {Path(image_path).name}", "tree": new_tree.json()["sha"], "parents": []})
    if not commit.ok:
        raise HostingError(f"GitHub no dejó crear el commit con la historia (HTTP {commit.status_code}).")
    sha = commit.json()["sha"]

    # Sustituir la rama (force) o crearla si todavía no existe
    ref = _request(session, "PATCH", f"{API}/repos/{repo}/git/refs/heads/{branch}", token, json={"sha": sha, "force": True})
    if ref.status_code in (404, 422):
        ref = _request(session, "POST", f"{API}/repos/{repo}/git/refs", token, json={"ref": f"refs/heads/{branch}", "sha": sha})
    if not ref.ok:
        raise HostingError(f"GitHub no dejó actualizar la rama {branch} (HTTP {ref.status_code}).")

    url = f"{RAW}/{repo}/{branch}/{name}"
    end = time.time() + AVAILABILITY_TIMEOUT
    while time.time() < end:
        try:
            if session.head(url, timeout=TIMEOUT).status_code == 200:
                return url
        except requests.RequestException:
            pass
        time.sleep(2)
    raise HostingError("La historia se subió a GitHub pero no está disponible públicamente (¿el repo es privado?).")
