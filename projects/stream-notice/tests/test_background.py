"""Funcionamiento en segundo plano: registro, una sola copia, acceso directo de Inicio e icono junto al reloj."""

import io
import re
import subprocess
import sys
from pathlib import Path

import pytest

import autostart
import runtime

PROJECT = Path(__file__).resolve().parents[1]
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="solo Windows")


@pytest.fixture
def restore_streams():
    saved = sys.stdout, sys.stderr
    yield
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "file"):
            stream.file.close()
    sys.stdout, sys.stderr = saved


def test_registro_con_fecha_y_hora_y_consola(tmp_path, monkeypatch, restore_streams):
    console = io.StringIO()
    console.reconfigure = lambda **kwargs: None
    monkeypatch.setattr(sys, "stdout", console)
    runtime.setup_logging(tmp_path / "logs" / "x.log")
    print("Conectado a OBS.")
    print("línea 1\nlínea 2")
    sys.stdout.flush()
    lines = (tmp_path / "logs" / "x.log").read_text(encoding="utf-8").splitlines()
    assert all(re.match(r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\] ", line) for line in lines)
    assert [line[22:] for line in lines] == ["Conectado a OBS.", "línea 1", "línea 2"]
    assert console.getvalue() == "Conectado a OBS.\nlínea 1\nlínea 2\n"  # la consola, sin marcas


def test_registro_sin_consola_pythonw(tmp_path, monkeypatch, restore_streams):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    runtime.setup_logging(tmp_path / "x.log")
    print("sin consola")
    print("error", file=sys.stderr)
    text = (tmp_path / "x.log").read_text(encoding="utf-8")
    assert "sin consola" in text and "error" in text


def test_registro_rota_al_pasar_del_limite(tmp_path, monkeypatch, restore_streams):
    log = tmp_path / "x.log"
    log.write_text("x" * (runtime.MAX_LOG_BYTES + 10), encoding="utf-8")
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    runtime.setup_logging(log)
    assert (tmp_path / "x.log.1").stat().st_size > runtime.MAX_LOG_BYTES
    assert log.stat().st_size == 0


@windows_only
def test_una_sola_copia_a_la_vez():
    code = ("import sys, time; sys.path.insert(0, r'%s'); import runtime; "
            "print(runtime.acquire_single_instance(), flush=True); time.sleep(4)") % PROJECT
    first = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert first.stdout.readline().strip() == "True"
        second = subprocess.run([sys.executable, "-c", code.replace("time.sleep(4)", "")],
                                capture_output=True, text=True, timeout=30)
        assert second.stdout.strip() == "False"
    finally:
        first.kill()


@windows_only
def test_acceso_directo_de_inicio(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "PYTHONW", Path(sys.executable).with_name("pythonw.exe"))
    link = autostart.install(folder=tmp_path, start_now=False)
    assert link.is_file() and autostart.status(tmp_path)
    read = subprocess.run(["powershell", "-NoProfile", "-Command",
                           f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{link}'); "
                           "$s.TargetPath; $s.Arguments; $s.WorkingDirectory"],
                          capture_output=True, text=True, check=True).stdout.splitlines()
    assert read[0].lower().endswith("pythonw.exe")
    assert read[1].strip('"').endswith("stream_notice.py")
    assert Path(read[2]) == PROJECT
    assert autostart.uninstall(tmp_path) and not autostart.status(tmp_path)
    assert not autostart.uninstall(tmp_path)  # desinstalar dos veces no falla


def test_menu_del_icono(tmp_path):
    from tray import TrayIcon
    connected = {"on": False}
    calls = []
    tray = TrayIcon(is_connected=lambda: connected["on"], on_test=lambda: calls.append("test"),
                    on_quit=lambda: calls.append("quit"), output_folder=tmp_path, log_path=tmp_path / "x.log")
    items = list(tray.icon.menu.items)
    texts = [item.text for item in items if item is not tray.icon.menu.SEPARATOR and not item.text.startswith("- ")]
    assert texts == ["○ Esperando a OBS…", "Probar aviso", "Abrir carpeta de historias", "Ver registro", "Salir"]
    assert "esperando a OBS" in tray._title()
    connected["on"] = True
    assert items[0].text == "● Conectado a OBS" and "conectado a OBS" in tray._title()
    next(item for item in items if item.text == "Probar aviso")(tray.icon)
    assert calls == ["test"]
