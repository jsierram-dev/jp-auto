import tkinter as tk

import pytest
from PIL import Image

import popup
from publish import PublishResult

LONG_ERROR = ("WhatsApp no ha aceptado el aviso (server returned error 403): comprueba que eres propietario "
              "o administrador del canal y el channel_id.")
NAMES = [("open_image", "Abrir imagen"), ("instagram", "Instagram"), ("tiktok", "TikTok"),
         ("whatsapp", "Canal de WhatsApp")]


pytestmark = pytest.mark.gui


# Un solo Tk por módulo: crear varios seguidos en Windows falla a veces al iniciar Tcl
@pytest.fixture(scope="module")
def window(tmp_path_factory):
    root = tk.Tk()
    root.withdraw()
    noop = lambda *args: None
    notice = popup.NoticePopup(root, (0, 0, 1920, 1080), noop, noop, noop, noop, noop, noop)
    image = tmp_path_factory.mktemp("popup") / "story.jpg"
    Image.new("RGB", (1080, 1920), "gray").save(image)
    yield root, notice, image
    root.destroy()


def _show(root, notice, image, failed: int):
    results = [PublishResult(key, name, i < len(NAMES) - failed, "ok" if i < len(NAMES) - failed else LONG_ERROR)
               for i, (key, name) in enumerate(NAMES)]
    notice.show_done(image, "The Callisto Protocol", "IGDB", results)
    root.update()
    content = sum(child.winfo_reqheight() for child in notice.body.winfo_children()) + 8
    return content, notice.body.winfo_height(), notice.window.winfo_height()


@pytest.mark.parametrize("failed", [0, 1, 3])
def test_resultados_de_los_cuatro_destinos_caben_enteros(window, failed):
    content, available, _ = _show(*window, failed)
    assert content <= available


def _texts(widget):
    for child in widget.winfo_children():
        if isinstance(child, tk.Label) and child.cget("text"):
            yield child.cget("text")
        yield from _texts(child)


def test_el_error_largo_se_muestra_entero(window):
    _show(*window, 1)
    assert any(text.endswith(LONG_ERROR) for text in _texts(window[1].body))


def test_la_ventana_solo_crece_con_errores_y_vuelve_al_alto_normal(window):
    assert _show(*window, 0)[2] == popup.HEIGHT
    assert _show(*window, 3)[2] > popup.HEIGHT
    assert _show(*window, 0)[2] == popup.HEIGHT
