"""Integración: la app real contra un OBS falso, con Twitch/IGDB simulados y carpetas temporales.

Cubre conexión y reconexión con OBS, contraseña, eventos duplicados, todos los estados del popup,
vista previa de historia existente, selector de imagen, una historia por juego y destinos que fallan.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

from common import FakeObs, Harness, OBS_PASSWORD, OBS_PORT, sn  # noqa: F401 (common prepara el sys.path)

from PIL import Image  # noqa: E402

import compose  # noqa: E402
import obs_monitor  # noqa: E402
import popup as pp  # noqa: E402
import twitch_api as ta  # noqa: E402


class FakeTwitch:
    def __init__(self):
        self.no_category = False

    def get_current_game(self, channel):
        time.sleep(1.5)  # red lenta, para comprobar que la ventana no se congela
        if self.no_category:
            raise ta.NoCategoryError("El canal no tiene ninguna categoría puesta. Ponla en Twitch y vuelve a intentarlo.")
        return ta.Game("33214", "Fortnite", "1905", "")


def main() -> int:
    h = Harness()
    tmp = Path(tempfile.mkdtemp())
    images, output = tmp / "game_images", tmp / "output"
    images.mkdir()
    output.mkdir()

    online_fail = {"on": False}

    def fake_online(client, game):
        if online_fail["on"]:
            raise sn.TwitchError("IGDB caído (simulado)")
        return compose._test_game_image(), "IGDB (falso)"

    opened, explorer_calls, compose_calls = [], [], []
    sn.get_online_image = fake_online
    os.startfile = lambda p: opened.append(p)
    sn.subprocess.Popen = lambda args, **kw: explorer_calls.append(args)
    original_compose = sn.compose
    sn.compose = lambda *a, **k: (compose_calls.append(1), original_compose(*a, **k))[1]

    config = {
        "obs": {"host": "localhost", "port": OBS_PORT, "password": OBS_PASSWORD},
        "twitch": {"channel": "jscorpiodv", "client_id": "x", "client_secret": "x"},
        "template": "story-notice.png", "output_folder": str(output), "game_images_folder": str(images),
        "crt_effect": True, "category_delay_seconds": 1,
        "destinations": {"open_image": {"enabled": True}, "no_existe": {"enabled": True},
                         "desactivado": {"enabled": False}},
    }
    app = sn.App(config, test_mode=False)
    app.twitch = FakeTwitch()
    h.app = app
    obs = FakeObs()
    check, ui, wait_for, has, texts, buttons, size = h.check, h.ui, h.wait_for, h.has, h.texts, h.buttons, h.size
    log = h.log

    def scenario():
        check("OBS cerrado: mensaje de reintento", wait_for(lambda: "OBS no está abierto" in log.getvalue(), 5))
        obs.start()
        check("conecta cuando OBS se abre", wait_for(lambda: "Conectado a OBS" in log.getvalue()))
        wait_for(lambda: obs.clients, 3)
        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTING")
        time.sleep(1)
        check("STARTING no abre popup", len(h.popups()) == 0)
        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTED")
        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTED")
        time.sleep(1.2)
        check("STARTED abre exactamente 1 popup (evento duplicado)", len(h.popups()) == 1)
        check("sin marco y siempre encima",
              ui(lambda: (bool(app.popup.window.overrideredirect()), bool(app.popup.window.attributes("-topmost")))) == (True, True))
        area = obs_monitor.obs_work_area() or (0, 0, app.root.winfo_screenwidth(), app.root.winfo_screenheight())
        pos = ui(lambda: (app.popup.window.winfo_rootx(), app.popup.window.winfo_rooty()))
        check("se abre centrado en el monitor de OBS",
              pos == (area[0] + (area[2] - area[0] - pp.WIDTH) // 2, area[1] + (area[3] - area[1] - pp.HEIGHT) // 2),
              f"{pos} en {area}")
        sizes = {size()}
        check("pregunta: textos y botones", has("¡Directo iniciado!") and has("¿Quieres enviar los avisos?")
              and buttons() == ["No", "Sí, enviar"], str(buttons()))

        ticks = []

        def tick():
            ticks.append(time.time())
            if len(ticks) < 40:
                app.root.after(100, tick)
        ui(lambda: (app.root.after(100, tick), app.popup._enter()))  # Enter = Sí, enviar
        time.sleep(0.3)
        sizes.add(size())
        check("trabajando: pasos visibles, sin botones", has("Leyendo la categoría de Twitch") and buttons() == [], str(texts()))
        ui(lambda: app.popup.close())
        ui(lambda: app.popup._escape())
        check("no se cierra a mitad del trabajo (✕ ni Esc)", len(h.popups()) == 1)
        check("paso 1 hecho → 'Categoría: Fortnite'", wait_for(lambda: has("Categoría: Fortnite")), str(texts()))
        sizes.add(size())
        check("termina", wait_for(h.is_done), str(texts()))
        sizes.add(size())
        gaps = [b - a for a, b in zip(ticks, ticks[1:])]
        check("ventana nunca congelada (máx. hueco < 0.5 s)", gaps and max(gaps) < 0.5, f"({max(gaps):.2f}s)")
        check("un destino roto no rompe los demás", len(opened) == 1 and has("no_existe:") and has("Abrir en el PC"), str(texts()))
        check("confirma historia creada y resumen del envío", has("Historia creada y guardada") and has("Enviada con errores"))
        check("listo: miniatura + 'Abrir carpeta' / 'Cerrar'", ui(lambda: app.popup.thumb is not None) and h.is_done())
        out = Path(opened[0]) if opened else None
        check("imagen guardada 1080×1920", out and out.is_file() and Image.open(out).size == (1080, 1920), str(out))
        h.press("Abrir carpeta")
        check("'Abrir carpeta' abre el explorador con la historia seleccionada",
              explorer_calls and explorer_calls[-1] == ["explorer", "/select,", str(out)], str(explorer_calls[-1:]))
        h.press("Cerrar")
        check("Cerrar cierra el popup", len(h.popups()) == 0)

        n = len(opened)
        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTED")
        time.sleep(1)
        check("nuevo directo → popup nuevo", len(h.popups()) == 1)
        ui(lambda: app.popup._escape())
        time.sleep(0.3)
        check("Esc en la pregunta = No (cierra sin generar)", len(h.popups()) == 0 and len(opened) == n)

        app.twitch.no_category = True
        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTED")
        time.sleep(1)
        h.press("Sí, enviar")
        check("sin categoría → estado de error", wait_for(lambda: has("No se pudo generar") and has("no tiene ninguna categoría")))
        sizes.add(size())
        check("error: botones 'Cerrar' / 'Reintentar'", buttons() == ["Cerrar", "Reintentar"])
        app.twitch.no_category = False
        h.press("Reintentar")

        # Ya existe una historia de Fortnite (la del primer directo): se enseña antes de enviar
        check("con historia existente → vista previa", wait_for(lambda: has("Ya tienes una historia de Fortnite")), str(texts()))
        check("vista previa: 'Generar nueva' / 'Enviar esta' y nada enviado aún",
              buttons() == ["Generar nueva", "Enviar esta"] and len(opened) == n)
        check("vista previa crece a 440×720", size() == (pp.WIDTH, pp.PREVIEW_HEIGHT), str(size()))
        top = ui(lambda: app.popup.window.winfo_rooty())
        check("vista previa dentro del monitor", area[1] <= top and top + pp.PREVIEW_HEIGHT <= area[3], f"y={top} en {area}")
        check("imagen de la vista previa grande (≥ 500 px de alto)", ui(lambda: app.popup.thumb.height()) >= 500)
        n_compose = len(compose_calls)
        h.press("Generar nueva")
        check("'Generar nueva' sin imágenes propias → genera y envía",
              wait_for(h.is_done) and len(opened) == n + 1 and len(compose_calls) == n_compose + 1, str(texts()))
        sizes.add(size())
        check("tras la vista previa vuelve a 440×320", size() == (pp.WIDTH, pp.HEIGHT), str(size()))
        h.press("Cerrar")

        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTED")
        time.sleep(1)
        h.press("Sí, enviar")
        wait_for(lambda: has("Ya tienes una historia de Fortnite"))
        latest = compose.find_existing_story(output, "Fortnite")
        n_compose = len(compose_calls)
        ui(lambda: app.popup._enter())  # Enter = "Enviar esta"
        check("'Enviar esta' envía la existente sin componer",
              wait_for(h.is_done) and Path(opened[-1]) == latest and len(compose_calls) == n_compose)
        check("listo tras reutilizar: fecha y 'Historia reutilizada'", has("historia del") and has("Historia reutilizada"))
        check("tamaño fijo 440×320 en todos los estados salvo vista previa y selector", sizes == {(pp.WIDTH, pp.HEIGHT)}, str(sizes))
        h.press("Cerrar")

        config["reuse_existing_story"] = False
        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTED")
        time.sleep(1)
        n_compose = len(compose_calls)
        h.press("Sí, enviar")
        check("reuse_existing_story=false → genera sin vista previa", wait_for(h.is_done) and len(compose_calls) == n_compose + 1)
        h.press("Cerrar")
        config["reuse_existing_story"] = True
        check("en output/ solo queda la última historia del juego", len(list(output.glob("*_fortnite.jpg"))) == 1,
              str(sorted(p.name for p in output.iterdir())))

        # Selector de imagen: 2 propias (sufijo + carpeta) + la de internet; la de otro juego no sale
        (images / "fortnite").mkdir()
        Image.new("RGB", (800, 450), (255, 0, 0)).save(images / "fortnite-roja.png")
        Image.new("RGB", (800, 450), (0, 0, 255)).save(images / "fortnite" / "azul.png")
        Image.new("RGB", (800, 450), (0, 255, 0)).save(images / "minecraft.png")
        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTED")
        time.sleep(1)
        h.press("Sí, enviar")
        wait_for(lambda: has("Ya tienes una historia de Fortnite"))
        h.press("Generar nueva")
        check("con imágenes propias → selector", wait_for(lambda: has("Elige la imagen de Fortnite")), str(texts()))
        labels = [t for t in texts() if t.startswith("Tuya") or "IGDB" in t]
        check("selector: propias (sufijo y carpeta) + internet, sin otros juegos",
              labels == ["Tuya: roja", "Tuya: azul", "IGDB (falso)"], str(labels))
        check("selector 440×720 con botón Cancelar", size() == (pp.WIDTH, pp.PREVIEW_HEIGHT) and buttons() == ["Cancelar"])
        n_compose = len(compose_calls)
        ui(lambda: app._pick_image(0))  # "Tuya: roja"
        check("elegir una propia → genera con ella", wait_for(h.is_done) and has("imagen propia (fortnite-roja.png)")
              and len(compose_calls) == n_compose + 1, str(texts()))
        story = sorted(output.glob("*_fortnite.jpg"))[-1]
        pixel = Image.open(story).convert("RGB").getpixel((400, 860))
        check("la tele lleva la imagen elegida (roja)", pixel[0] > 200 and pixel[1] < 60 and pixel[2] < 60, str(pixel))
        check("sigue quedando una sola historia del juego", len(list(output.glob("*_fortnite.jpg"))) == 1)
        h.press("Cerrar")

        online_fail["on"] = True
        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTED")
        time.sleep(1)
        h.press("Sí, enviar")
        wait_for(lambda: has("Ya tienes una historia de Fortnite"))
        h.press("Generar nueva")
        wait_for(lambda: has("Elige la imagen de Fortnite"))
        labels = [t for t in texts() if t.startswith("Tuya") or "IGDB" in t]
        check("sin internet → selector solo con las propias", labels == ["Tuya: roja", "Tuya: azul"], str(labels))
        h.press("Cancelar")
        check("'Cancelar' cierra sin generar", len(h.popups()) == 0)
        online_fail["on"] = False

        obs.stop()
        check("detecta que OBS se cerró", wait_for(lambda: "Se ha perdido la conexión con OBS" in log.getvalue()))
        before = log.getvalue().count("OBS no está abierto")
        check("vuelve al bucle de reintentos", wait_for(lambda: log.getvalue().count("OBS no está abierto") > before))
        connections = log.getvalue().count("Conectado a OBS")
        obs.start()
        check("reconecta al volver OBS", wait_for(lambda: log.getvalue().count("Conectado a OBS") > connections))
        wait_for(lambda: obs.clients, 3)
        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTED")
        check("tras reconectar sigue recibiendo eventos", wait_for(lambda: len(h.popups()) == 1, 4))
        h.press("No")
        obs.stop()
        config["obs"]["password"] = "mala"
        mark = len(log.getvalue())
        obs.start()
        check("contraseña incorrecta → mensaje claro", wait_for(lambda: "revisa la contraseña" in log.getvalue()[mark:]))
        check("sin trazas en consola", "Traceback" not in log.getvalue())
        obs.stop()

    return h.run(scenario)


if __name__ == "__main__":
    sys.exit(main())
