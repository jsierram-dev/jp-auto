"""Regresión antes de mergear: clicks, rueda y teclas REALES del ratón/teclado; Twitch, IGDB y composición REALES.

El inicio de directo lo manda un OBS falso para no emitir en el canal de verdad. game_images/ y output/
son carpetas temporales: no se toca nada del usuario. Necesita config.json con credenciales de Twitch.
Mueve el cursor durante un par de minutos: no tocar el ratón mientras corre.
"""

import ctypes
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from common import FakeObs, Harness, OBS_PASSWORD, OBS_PORT, PROJECT, sn

from PIL import Image  # noqa: E402

import compose  # noqa: E402
import obs_monitor  # noqa: E402
import popup as pp  # noqa: E402

user32 = ctypes.windll.user32
VK_RETURN, VK_ESCAPE = 0x0D, 0x1B


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def main() -> int:
    if not (PROJECT / "config.json").is_file():
        print("Falta config.json con credenciales de Twitch: no se puede ejecutar la regresión real.")
        return 2
    h = Harness()
    config = sn.load_config()
    config["obs"] = {"host": "localhost", "port": OBS_PORT, "password": OBS_PASSWORD}
    real_channel = config["twitch"]["channel"]

    # Juego real de la categoría actual, para preparar sus imágenes propias y una historia existente
    game = sn.TwitchClient(config["twitch"]["client_id"], config["twitch"]["client_secret"]) \
        .get_current_game(real_channel).name
    slug = compose.slugify(game)
    tmp = Path(tempfile.mkdtemp())
    images, output = tmp / "game_images", tmp / "output"
    (images / slug).mkdir(parents=True)
    output.mkdir()
    own = {f"{slug}.png": (220, 30, 30), f"{slug}-jacob.jpg": (30, 180, 60), f"{slug}/portada.jpg": (30, 60, 220),
           f"{slug}-4.png": (200, 160, 40), f"{slug}-5.png": (140, 60, 180), f"{slug}-6.png": (40, 170, 170),
           "otro-juego-xyz.png": (255, 255, 255)}
    for name, color in own.items():
        Image.new("RGB", (1600, 900), color).save(images / name)
    old_story = compose.save_story(compose.compose(PROJECT / config["template"], compose._test_game_image()), output, game)
    config["game_images_folder"], config["output_folder"] = str(images), str(output)
    real_output = PROJECT / "output"
    before_files = set(real_output.iterdir()) if real_output.is_dir() else set()

    opened, explorer_calls, compose_calls = [], [], []
    os.startfile = lambda p: opened.append(Path(p))  # no llenar la pantalla de visores
    sn.subprocess.Popen = lambda args, **kw: explorer_calls.append(args)
    original_compose = sn.compose
    sn.compose = lambda *a, **k: (compose_calls.append(1), original_compose(*a, **k))[1]

    app = sn.App(config, test_mode=False)
    h.app = app
    obs = FakeObs()
    check, ui, wait_for, has, texts, buttons, size = h.check, h.ui, h.wait_for, h.has, h.texts, h.buttons, h.size
    log = h.log
    cursor = _Point()
    user32.GetCursorPos(ctypes.byref(cursor))

    def center_of(getter):
        def find():
            widget = getter()
            widget.update_idletasks()
            return widget.winfo_rootx() + widget.winfo_width() // 2, widget.winfo_rooty() + widget.winfo_height() // 2
        return ui(find)

    def real_click(x, y):
        user32.SetCursorPos(x, y)
        time.sleep(0.25)  # pasa por encima (hover) como una persona
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.06)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.4)

    def click_button(text):
        real_click(*center_of(lambda: next(c for c in app.popup.footer.winfo_children() if c.cget("text") == text)))

    def click_x():
        real_click(*center_of(lambda: app.popup.close_x))

    def key(vk):
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.4)

    def start_stream():
        obs.emit("OBS_WEBSOCKET_OUTPUT_STARTED")
        return wait_for(lambda: len(h.popups()) == 1, 5)

    def tiles():
        return app.popup.picker_canvas.winfo_children()[0].winfo_children()

    def tile_labels():
        return ui(lambda: [t.winfo_children()[1].cget("text") for t in tiles()])

    def click_tile(label):
        index = tile_labels().index(label)
        rows = (len(tile_labels()) + 1) // 2
        ui(lambda: app.popup.picker_canvas.yview_moveto(max(0, (index // 2 - 1) / max(1, rows))))
        time.sleep(0.3)
        real_click(*center_of(lambda: tiles()[index].winfo_children()[0]))

    def scenario():
        try:
            obs.start()
            check("conecta con OBS", wait_for(lambda: "Conectado a OBS" in log.getvalue(), 15))
            wait_for(lambda: obs.clients, 3)

            # Pregunta: posición, arrastre real, ✕, Esc y No reales
            check("inicio de directo → popup", start_stream())
            area = obs_monitor.obs_work_area() or (0, 0, app.root.winfo_screenwidth(), app.root.winfo_screenheight())
            pos = ui(lambda: (app.popup.window.winfo_rootx(), app.popup.window.winfo_rooty()))
            check("popup centrado en el monitor de OBS",
                  pos == (area[0] + (area[2] - area[0] - pp.WIDTH) // 2, area[1] + (area[3] - area[1] - pp.HEIGHT) // 2),
                  f"{pos} en {area}")
            tx, ty = pos[0] + 150, pos[1] + 17
            user32.SetCursorPos(tx, ty)
            time.sleep(0.2)
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            for i in range(1, 11):
                user32.SetCursorPos(tx - 8 * i, ty + 5 * i)
                time.sleep(0.03)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.3)
            moved = ui(lambda: (app.popup.window.winfo_rootx(), app.popup.window.winfo_rooty()))
            check("arrastrar la barra de título mueve el popup (si falla, ¿se movió el ratón?)",
                  moved == (pos[0] - 80, pos[1] + 50), f"{pos} → {moved}")
            click_x()
            check("✕ (click real) cierra en la pregunta", len(h.popups()) == 0)
            start_stream()
            key(VK_ESCAPE)
            check("Esc (tecla real) = No", len(h.popups()) == 0)
            start_stream()
            click_button("No")
            check("'No' (click real) cierra sin generar", len(h.popups()) == 0 and not compose_calls and not opened)

            # Sí → Twitch real → historia existente → vista previa → Generar nueva → selector → IGDB real
            start_stream()
            click_button("Sí, enviar")
            check("trabajando: paso de categoría en marcha", has("Leyendo la categoría de Twitch"), str(texts()))
            check("historia existente → vista previa", wait_for(lambda: has(f"Ya tienes una historia de {game}"), 30), str(texts()))
            top = ui(lambda: app.popup.window.winfo_rooty())
            check("vista previa 440×720 dentro del monitor", size() == (440, 720) and area[1] <= top <= area[3] - 720)
            click_button("Generar nueva")
            check("con imágenes propias → selector", wait_for(lambda: has("Elige la imagen de"), 40), str(texts()))
            labels = tile_labels()
            check("selector: 6 propias (sufijo y carpeta) + internet, sin otros juegos",
                  labels[:6] == ["Tuya", "Tuya: 4", "Tuya: 5", "Tuya: 6", "Tuya: jacob", "Tuya: portada"]
                  and len(labels) == 7 and labels[6] in ("IGDB", "Carátula de Twitch"), str(labels))
            check("selector 440×720 con 'Cancelar'", size() == (440, 720) and buttons() == ["Cancelar"])
            before = ui(lambda: app.popup.picker_canvas.yview()[0])
            user32.SetCursorPos(*center_of(lambda: app.popup.picker_canvas))
            time.sleep(0.2)
            for _ in range(5):
                user32.mouse_event(0x0800, 0, 0, ctypes.c_ulong(-120 & 0xFFFFFFFF).value, 0)
                time.sleep(0.05)
            time.sleep(0.3)
            after = ui(lambda: app.popup.picker_canvas.yview()[0])
            check("rueda real del ratón desplaza la lista", after > before, f"{before:.2f} → {after:.2f}")
            click_tile(labels[6])
            check("clic real en la imagen de internet → termina con historia nueva",
                  wait_for(h.is_done, 60) and len(compose_calls) == 1 and has("Historia creada y guardada"), str(texts()))
            check("título '¡Historia enviada!' y destino ✓", has("¡Historia enviada!") and has("Abrir en el PC"), str(texts()))
            new_story = opened[-1] if opened else None
            check("historia nueva 1080×1920", new_story and new_story.is_file() and Image.open(new_story).size == (1080, 1920))
            check("vuelve a 440×320", size() == (440, 320), str(size()))
            click_button("Abrir carpeta")
            check("'Abrir carpeta' (click real) → explorador con la historia seleccionada",
                  explorer_calls and explorer_calls[-1] == ["explorer", "/select,", str(new_story)], str(explorer_calls[-1:]))
            click_button("Cerrar")
            check("'Cerrar' (click real) cierra", len(h.popups()) == 0)
            check("en output/ solo queda la última historia del juego",
                  not old_story.exists() and [p.name for p in output.iterdir()] == [new_story.name])

            # Enter real = Sí, enviar → vista previa → Enter real = Enviar esta
            start_stream()
            key(VK_RETURN)
            check("Enter (tecla real) → vista previa", wait_for(lambda: has("Ya tienes una historia de"), 30), str(texts()))
            key(VK_RETURN)
            check("Enter = 'Enviar esta' → enviada sin componer",
                  wait_for(h.is_done, 30) and len(compose_calls) == 1 and opened[-1] == new_story, str(texts()))
            check("confirma 'Historia reutilizada'", has("Historia reutilizada") and has("historia del"))
            click_x()
            check("✕ (click real) cierra en listo", len(h.popups()) == 0)

            # Selector: clic real en una imagen propia
            start_stream()
            click_button("Sí, enviar")
            wait_for(lambda: has("Ya tienes una historia de"), 30)
            click_button("Generar nueva")
            wait_for(lambda: has("Elige la imagen de"), 40)
            click_tile("Tuya: jacob")
            check("clic real en 'Tuya: jacob' → historia con esa imagen",
                  wait_for(h.is_done, 60) and has(f"imagen propia ({slug}-jacob.jpg)"), str(texts()))
            pixel = Image.open(opened[-1]).convert("RGB").getpixel((400, 860))
            check("la tele lleva la imagen elegida (verde)", pixel[1] > 150 and pixel[0] < 80 and pixel[2] < 100, str(pixel))
            check("sigue quedando una sola historia del juego", len(list(output.iterdir())) == 1)
            click_button("Cerrar")
            start_stream()
            click_button("Sí, enviar")
            wait_for(lambda: has("Ya tienes una historia de"), 30)
            click_button("Generar nueva")
            wait_for(lambda: has("Elige la imagen de"), 40)
            n = len(compose_calls)
            click_button("Cancelar")
            check("'Cancelar' (click real) en el selector cierra sin generar", len(h.popups()) == 0 and len(compose_calls) == n)

            # Error real de Twitch (canal inexistente) → Reintentar → vista previa → Enviar esta
            config["twitch"]["channel"] = "jscorpiodv_canal_que_no_existe_987"
            start_stream()
            click_button("Sí, enviar")
            check("error real de Twitch → pantalla de error",
                  wait_for(lambda: has("No se pudo generar"), 30) and has("No existe el canal"), str(texts()))
            check("error: botones Cerrar / Reintentar", buttons() == ["Cerrar", "Reintentar"])
            config["twitch"]["channel"] = real_channel
            click_button("Reintentar")
            check("'Reintentar' (click real) → vista previa", wait_for(lambda: has("Ya tienes una historia de"), 30), str(texts()))
            click_button("Enviar esta")
            check("'Enviar esta' (click real) → enviada", wait_for(h.is_done, 30) and has("Historia reutilizada"))
            click_button("Cerrar")

            # OBS se cierra y vuelve
            obs.stop()
            check("OBS cerrado → lo detecta y reintenta",
                  wait_for(lambda: "Se ha perdido la conexión con OBS" in log.getvalue(), 10)
                  and wait_for(lambda: "OBS no está abierto" in log.getvalue(), 15))
            connections = log.getvalue().count("Conectado a OBS")
            obs.start()
            check("OBS vuelve → reconecta", wait_for(lambda: log.getvalue().count("Conectado a OBS") > connections, 15))
            obs.stop()
            check("consola sin errores ni trazas en todo el flujo",
                  "Traceback" not in log.getvalue() and "Error inesperado" not in log.getvalue())
            after_files = set(real_output.iterdir()) if real_output.is_dir() else set()
            check("output/ real del usuario sin cambios", after_files == before_files)
        finally:
            user32.SetCursorPos(cursor.x, cursor.y)

    code = h.run(scenario)
    shutil.rmtree(tmp, ignore_errors=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
