import sys
import types

import pytest

import publish
from stream_notice import _own_image_label


def _destination(monkeypatch, key, name=None, fail=None):
    module = types.ModuleType(f"destinations.{key}")
    if name:
        module.NAME = name

    def send(image_path, game_name, settings):
        if fail:
            raise RuntimeError(fail)
        return "ok"
    module.publish = send
    monkeypatch.setitem(sys.modules, f"destinations.{key}", module)


def test_un_destino_roto_no_para_a_los_demas(monkeypatch, tmp_path):
    _destination(monkeypatch, "fake_ig", "Instagram")
    _destination(monkeypatch, "fake_tt", "TikTok", fail="token caducado")
    _destination(monkeypatch, "fake_dc", "Discord")
    config = {"destinations": {"fake_ig": {"enabled": True}, "fake_tt": {"enabled": True},
                               "fake_dc": {"enabled": True}, "apagado": {"enabled": False}}}
    progress = []
    results = publish.publish(tmp_path / "x.jpg", "Fortnite", config, on_progress=progress.append)
    assert [(r.name, r.ok) for r in results] == [("Instagram", True), ("TikTok", False), ("Discord", True)]
    assert results[1].message == "token caducado"
    assert progress == ["Instagram", "TikTok", "Discord"]


def test_modulo_inexistente_falla_con_su_clave_como_nombre(tmp_path):
    results = publish.publish(tmp_path / "x.jpg", "Fortnite", {"destinations": {"no_existe": {"enabled": True}}})
    assert len(results) == 1 and not results[0].ok and results[0].name == "no_existe"


def test_sin_destinations_abre_la_imagen(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr("os.startfile", opened.append, raising=False)
    results = publish.publish(tmp_path / "x.jpg", "Fortnite", {})
    assert [(r.name, r.ok) for r in results] == [("Abrir en el PC", True)]
    assert opened == [tmp_path / "x.jpg"]


@pytest.mark.parametrize("path, label", [
    ("the-callisto-protocol.png", "Tuya"),
    ("the-callisto-protocol-jacob.jpg", "Tuya: jacob"),
    ("the-callisto-protocol/portada.jpg", "Tuya: portada"),
    ("The Callisto Protocol 2.PNG", "Tuya: 2"),
    ("mi-the-callisto-protocol.webp", "Tuya: mi"),
])
def test_etiquetas_del_selector(path, label):
    from pathlib import Path
    assert _own_image_label(Path(path), "The Callisto Protocol") == label
