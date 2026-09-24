"""Arranque automático con Windows: acceso directo en la carpeta de Inicio del usuario.

Uso (o con doble clic en install_autostart.bat / uninstall_autostart.bat):
    python autostart.py install     # crea el acceso directo y arranca el programa ya
    python autostart.py uninstall   # lo quita (y no para el programa si está en marcha)
    python autostart.py status

No necesita permisos de administrador. Lanza el programa con pythonw.exe (sin consola): se controla desde
el icono junto al reloj y todo queda en logs/stream-notice.log.
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
PYTHONW = PROJECT / ".venv" / "Scripts" / "pythonw.exe"
ICON = PROJECT / "assets" / "logo.ico"
SHORTCUT_NAME = "Avisos de directo (stream-notice).lnk"


def startup_folder() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def shortcut_path(folder: Path | None = None) -> Path:
    return (folder or startup_folder()) / SHORTCUT_NAME


def _powershell_quote(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def install(folder: Path | None = None, start_now: bool = True) -> Path:
    if not PYTHONW.is_file():
        raise SystemExit(f"No existe {PYTHONW}. Crea antes el entorno virtual (ver README: python -m venv .venv).")
    if not (PROJECT / "config.json").is_file():
        raise SystemExit("Falta config.json: créalo antes de activar el arranque automático (ver README).")
    link = shortcut_path(folder)
    link.parent.mkdir(parents=True, exist_ok=True)
    # Accesos directos .lnk: se crean con el objeto COM WScript.Shell desde PowerShell
    script = "; ".join([
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut(" + _powershell_quote(link) + ")",
        "$s.TargetPath = " + _powershell_quote(PYTHONW),
        "$s.Arguments = " + _powershell_quote('"' + str(PROJECT / "stream_notice.py") + '"'),
        "$s.WorkingDirectory = " + _powershell_quote(PROJECT),
        "$s.IconLocation = " + _powershell_quote(ICON),
        "$s.Description = 'Avisos de directo: OBS -> historia en Instagram y TikTok'",
        "$s.Save()",
    ])
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, capture_output=True)
    print(f"Arranque automático activado: {link}")
    if start_now:
        # Arrancarlo ya, igual que lo hará Windows al iniciar sesión
        subprocess.Popen([str(PYTHONW), str(PROJECT / "stream_notice.py")], cwd=PROJECT,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        print("Programa arrancado: busca el icono junto al reloj.")
    return link


def uninstall(folder: Path | None = None) -> bool:
    link = shortcut_path(folder)
    if link.is_file():
        link.unlink()
        print("Arranque automático desactivado. Si está en marcha, ciérralo desde el icono junto al reloj → Salir.")
        return True
    print("El arranque automático no estaba activado.")
    return False


def status(folder: Path | None = None) -> bool:
    active = shortcut_path(folder).is_file()
    print("Arranque automático: " + ("ACTIVADO" if active else "desactivado"))
    return active


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"install": install, "uninstall": uninstall, "status": status}.get(action, lambda: sys.exit(__doc__))()
