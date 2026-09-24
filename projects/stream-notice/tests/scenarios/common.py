"""Piezas comunes de los escenarios con la app real: OBS falso, captura de consola y ayudantes de la interfaz.

Cada escenario se ejecuta en su propio proceso (tkinter no admite varias raíces seguidas en el mismo),
imprime PASA/FALLA por comprobación y sale con código 1 si alguna falla.
"""

import base64
import hashlib
import io
import json
import logging
import os
import queue
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
os.chdir(PROJECT)

from websockets.sync.server import serve  # noqa: E402

import stream_notice as sn  # noqa: E402

OBS_PORT = 4466
OBS_PASSWORD = "secreto"


class FakeObs:
    """Servidor mínimo con el protocolo obs-websocket v5: saludo, contraseña y eventos de directo."""

    def __init__(self, password: str = OBS_PASSWORD):
        self.password = password
        self.clients = []
        self.server = None
        self.thread = None

    def _handler(self, ws):
        salt, challenge = "salt123", "chal456"
        ws.send(json.dumps({"op": 0, "d": {"obsWebSocketVersion": "5.0", "rpcVersion": 1,
                                           "authentication": {"salt": salt, "challenge": challenge}}}))
        identify = json.loads(ws.recv())
        secret = base64.b64encode(hashlib.sha256((self.password + salt).encode()).digest())
        expected = base64.b64encode(hashlib.sha256(secret + challenge.encode()).digest()).decode()
        if identify["d"].get("authentication") != expected:
            ws.close(4009, "Authentication failed.")
            return
        ws.send(json.dumps({"op": 2, "d": {"negotiatedRpcVersion": 1}}))
        self.clients.append(ws)
        try:
            for _ in ws:
                pass
        except Exception:
            pass

    def start(self):
        self.server = serve(self._handler, "localhost", OBS_PORT)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        for client in self.clients:
            try:
                client.close()
            except Exception:
                pass
        self.clients.clear()
        self.server.shutdown()
        self.thread.join()

    def emit(self, state: str):
        for client in list(self.clients):
            client.send(json.dumps({"op": 5, "d": {"eventType": "StreamStateChanged", "eventIntent": 64,
                                                   "eventData": {"outputActive": True, "outputState": state}}}))


class Harness:
    """Captura la consola, lleva la cuenta de comprobaciones y consulta la interfaz desde otro hilo."""

    def __init__(self):
        self.log = io.StringIO()
        self.results = []
        harness = self

        class Tee:
            def write(self, text):
                harness.log.write(text)
                sys.__stdout__.write(text)

            def flush(self):
                sys.__stdout__.flush()

        sys.stdout = Tee()
        sys.stderr = Tee()
        # Igual que main(): obsws-python imprime trazas en cada reintento
        logging.getLogger("obsws_python").setLevel(logging.CRITICAL + 1)
        sn.RETRY_SECONDS = 1
        self.app = None

    def check(self, name: str, condition, extra: str = ""):
        self.results.append(bool(condition))
        sys.__stdout__.write(f"{'PASA ' if condition else 'FALLA'} {name} {extra}\n")

    def ui(self, function):
        """Ejecuta function en el hilo de la interfaz y devuelve su resultado."""
        box = queue.Queue()
        self.app._in_ui(lambda: box.put(function()))
        return box.get(timeout=5)

    @staticmethod
    def wait_for(condition, timeout: float = 10) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if condition():
                return True
            time.sleep(0.12)
        return False

    def popups(self):
        return self.ui(lambda: [w for w in self.app.root.winfo_children()
                                if w.winfo_class() == "Toplevel" and w.winfo_exists()])

    def texts(self) -> list[str]:
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, sn.tk.Label) and child.cget("text"):
                    yield child.cget("text")
                yield from walk(child)
        return self.ui(lambda: list(walk(self.app.popup.body)) if self.app.popup and self.app.popup.exists() else [])

    def has(self, text: str) -> bool:
        return any(text in t for t in self.texts())

    def buttons(self) -> list[str]:
        return self.ui(lambda: [c.cget("text") for c in self.app.popup.footer.winfo_children()]
                       if self.app.popup and self.app.popup.exists() else [])

    def is_done(self) -> bool:
        return self.buttons() == ["Abrir carpeta", "Cerrar"]

    def size(self) -> tuple[int, int]:
        return self.ui(lambda: (self.app.popup.window.winfo_width(), self.app.popup.window.winfo_height()))

    def press(self, text: str):
        """Pulsa un botón del pie llamando a su acción (sin mover el ratón)."""
        def do():
            for child in self.app.popup.footer.winfo_children():
                if child.cget("text") == text:
                    child.command()
                    return True
            return False
        return self.ui(do)

    def run(self, scenario) -> int:
        """Lanza el escenario en otro hilo con la app en el principal. Devuelve el código de salida."""
        def wrapper():
            try:
                scenario()
            except Exception as error:
                import traceback
                traceback.print_exc(file=sys.__stdout__)
                self.check("excepción en el escenario", False, repr(error))
            finally:
                self.app.root.after(0, self.app.root.quit)

        threading.Thread(target=wrapper, daemon=True).start()
        self.app.run()
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        passed = sum(self.results)
        print(f"\n{passed}/{len(self.results)} pasan")
        return 0 if self.results and passed == len(self.results) else 1
