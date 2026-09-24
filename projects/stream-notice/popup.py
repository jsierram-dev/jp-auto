"""Popup de avisos con estilo Twitch Dark: tamaño fijo y estados pregunta → trabajando → listo / error."""

import sys
import tkinter as tk
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageTk

WIDTH, HEIGHT = 440, 320
PADDING = 24
MAX_MESSAGE_CHARS = 200

# Paleta de Twitch
BG = "#18181b"
BORDER = "#2f2f35"
TEXT = "#efeff1"
MUTED = "#adadb8"
PURPLE = "#9146ff"
PURPLE_HOVER = "#772ce8"
PURPLE_LIGHT = "#bf94ff"
RED = "#eb0400"
BUTTON = "#2f2f35"
BUTTON_HOVER = "#3a3a3d"
ERROR_BG = "#2a1618"
ERROR_TEXT = "#f5b8b8"
TODO_RING = "#3a3a41"

FONT = "Segoe UI"
SPINNER_FRAMES = 12
SPINNER_MS = 70

STEPS = ("Leyendo la categoría de Twitch", "Buscando imagen del juego", "Generando historia")


def _shorten(text: str) -> str:
    return text if len(text) <= MAX_MESSAGE_CHARS else text[:MAX_MESSAGE_CHARS - 1] + "…"


# --- Iconos dibujados con Pillow (a 4× y reducidos, para bordes suaves) ---

def _icon(size: int, draw: Callable[[ImageDraw.ImageDraw, int], None]) -> ImageTk.PhotoImage:
    scale = 4
    big = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw(ImageDraw.Draw(big), size * scale)
    return ImageTk.PhotoImage(big.resize((size, size), Image.LANCZOS))


def _done_icon(size=16):
    def draw(d, s):
        d.ellipse((0, 0, s - 1, s - 1), fill=PURPLE)
        d.line([(s * .28, s * .52), (s * .44, s * .68), (s * .74, s * .34)], fill="white", width=int(s * .12), joint="curve")
    return _icon(size, draw)


def _todo_icon(size=16):
    return _icon(size, lambda d, s: d.ellipse((s * .06, s * .06, s * .94, s * .94), outline=TODO_RING, width=int(s * .12)))


def _spinner_frames(size=16):
    frames = []
    for i in range(SPINNER_FRAMES):
        start = i * 360 / SPINNER_FRAMES
        frames.append(_icon(size, lambda d, s, a=start: d.arc(
            (s * .08, s * .08, s * .92, s * .92), a, a + 270, fill=PURPLE_LIGHT, width=int(s * .12))))
    return frames


def _white_dot(size=7):
    return _icon(size, lambda d, s: d.ellipse((0, 0, s - 1, s - 1), fill="white"))


def _thumbnail(path: Path, height=128) -> ImageTk.PhotoImage:
    image = Image.open(path).convert("RGB")
    width = round(image.width * height / image.height)
    image = image.resize((width, height), Image.LANCZOS)
    mask = Image.new("L", (width * 4, height * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width * 4 - 1, height * 4 - 1), radius=24, fill=255)
    image.putalpha(mask.resize((width, height), Image.LANCZOS))
    return ImageTk.PhotoImage(image)


def _round_corners(window: tk.Toplevel):
    """Esquinas redondeadas nativas de Windows 11 (en Windows 10 se quedan rectas)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        preference = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference))
    except (OSError, AttributeError):
        pass


class FlatButton(tk.Label):
    """Botón plano con hover, al estilo Twitch (tk.Button no permite este aspecto en Windows)."""

    def __init__(self, parent, text: str, command: Callable, primary=False):
        self.normal, self.hover = (PURPLE, PURPLE_HOVER) if primary else (BUTTON, BUTTON_HOVER)
        super().__init__(parent, text=text, bg=self.normal, fg="white" if primary else TEXT,
                         font=(FONT, 10, "bold"), pady=8, cursor="hand2")
        self.command = command
        self.bind("<Enter>", lambda _: self.config(bg=self.hover))
        self.bind("<Leave>", lambda _: self.config(bg=self.normal))
        self.bind("<ButtonRelease-1>", lambda _: self.command())


class NoticePopup:
    """Ventana sin marco, siempre encima, de tamaño fijo. Solo se usa desde el hilo de la interfaz."""

    def __init__(self, root: tk.Tk, position: tuple[int, int], on_accept: Callable, on_close: Callable,
                 on_retry: Callable, on_open_folder: Callable):
        self.on_accept, self.on_close = on_accept, on_close
        self.on_retry, self.on_open_folder = on_retry, on_open_folder
        self.working = False
        self._spinner_job = None
        self._progress_job = None
        self._progress = 0.0

        # Imágenes: hay que guardar referencia o tkinter las borra
        self.icons = {"done": _done_icon(), "todo": _todo_icon(), "dot": _white_dot()}
        self.spinner = _spinner_frames()
        self.thumb = None

        self.window = tk.Toplevel(root, bg=BORDER)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.geometry(f"{WIDTH}x{HEIGHT}+{position[0]}+{position[1]}")
        self.window.bind("<Escape>", lambda _: self._escape())
        self.window.bind("<Return>", lambda _: self._enter())

        # Borde de 1 px alrededor del contenido
        frame = tk.Frame(self.window, bg=BG)
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        # Barra de título propia (arrastrable)
        bar = tk.Frame(frame, bg=BG, height=34)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        title = tk.Label(bar, text="Avisos de directo", bg=BG, fg=MUTED, font=(FONT, 9))
        title.pack(side="left", padx=12)
        self.close_x = tk.Label(bar, text="✕", bg=BG, fg=MUTED, font=(FONT, 11), cursor="hand2", padx=12)
        self.close_x.pack(side="right", fill="y")
        self.close_x.bind("<Enter>", lambda _: self.close_x.config(bg=RED if not self.working else BG, fg=TEXT if not self.working else MUTED))
        self.close_x.bind("<Leave>", lambda _: self.close_x.config(bg=BG, fg=MUTED))
        self.close_x.bind("<ButtonRelease-1>", lambda _: self.close())
        for widget in (bar, title):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)

        # Pie fijo con los botones: siempre en el mismo sitio, para que nada salte entre estados
        self.footer = tk.Frame(frame, bg=BG, height=40)
        self.footer.pack(side="bottom", fill="x", padx=PADDING, pady=(0, PADDING))
        self.footer.pack_propagate(False)
        self.footer.columnconfigure((0, 1), weight=1, uniform="buttons")
        self.footer.rowconfigure(0, weight=1)

        self.body = tk.Frame(frame, bg=BG)
        self.body.pack(fill="both", expand=True, padx=PADDING, pady=(4, 12))

        self.show_question()
        # El redondeo necesita la ventana ya creada por Windows (antes no tiene hwnd)
        self.window.update_idletasks()
        _round_corners(self.window)
        self.window.lift()
        self.window.focus_force()

    # --- Utilidades ---

    def exists(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def close(self):
        if self.working:
            return  # no se cierra a mitad de generar la imagen
        self._stop_animations()
        self.window.destroy()
        self.on_close()

    def _start_drag(self, event):
        self._drag_offset = (event.x_root - self.window.winfo_x(), event.y_root - self.window.winfo_y())

    def _drag(self, event):
        x, y = event.x_root - self._drag_offset[0], event.y_root - self._drag_offset[1]
        self.window.geometry(f"+{x}+{y}")

    def _clear(self):
        self._stop_animations()
        for container in (self.body, self.footer):
            for child in container.winfo_children():
                child.destroy()
        self._buttons = []

    def _stop_animations(self):
        for job in (self._spinner_job, self._progress_job):
            if job:
                self.window.after_cancel(job)
        self._spinner_job = self._progress_job = None

    def _set_buttons(self, *buttons: tuple[str, Callable, bool]):
        """Botones del pie: (texto, acción, principal). El principal va a la derecha."""
        self._buttons = list(buttons)
        for column, (text, command, primary) in enumerate(buttons, start=2 - len(buttons)):
            button = FlatButton(self.footer, text, command, primary)
            button.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 4, 4 if column == 0 else 0))

    def _enter(self):
        primary = [command for _, command, is_primary in self._buttons if is_primary]
        if primary:
            primary[0]()

    def _escape(self):
        if not self.working:
            self.close()

    def _live_pill(self):
        pill = tk.Label(self.body, text=" EN DIRECTO", image=self.icons["dot"], compound="left", bg=RED, fg="white",
                        font=(FONT, 8, "bold"), padx=8, pady=2)
        pill.pack(anchor="w", pady=(8, 0))

    def _heading(self, text: str, subtitle: str | None = None):
        tk.Label(self.body, text=text, bg=BG, fg=TEXT, font=(FONT, 17, "bold")).pack(anchor="w", pady=(10, 0))
        if subtitle:
            tk.Label(self.body, text=subtitle, bg=BG, fg=MUTED, font=(FONT, 11)).pack(anchor="w", pady=(2, 0))

    # --- Estados ---

    def show_question(self):
        self._clear()
        self._live_pill()
        self._heading("¡Directo iniciado!", "¿Quieres enviar los avisos?")
        self._set_buttons(("No", self.close, False), ("Sí, enviar", self.on_accept, True))

    def show_working(self):
        self._clear()
        self.working = True
        self.close_x.config(fg=BORDER, cursor="arrow")
        self._live_pill()
        self._heading("Preparando aviso…")

        steps = tk.Frame(self.body, bg=BG)
        steps.pack(anchor="w", fill="x", pady=(10, 0))
        self.step_rows = []
        for text in STEPS:
            row = tk.Frame(steps, bg=BG)
            row.pack(anchor="w", pady=2)
            icon = tk.Label(row, image=self.icons["todo"], bg=BG)
            icon.pack(side="left")
            label = tk.Label(row, text=text, bg=BG, fg=TEXT, font=(FONT, 10))
            label.pack(side="left", padx=(8, 0))
            self.step_rows.append((icon, label))

        self.progress = tk.Canvas(self.body, height=4, bg=BUTTON, highlightthickness=0)
        self.progress.pack(fill="x", pady=(14, 0))
        self.progress_bar = self.progress.create_rectangle(0, 0, 0, 4, fill=PURPLE, width=0)
        self._progress = 0.0
        self.set_step(0)

    def set_step(self, index: int, done_text: str | None = None):
        """Marca como hechos los pasos anteriores a index y anima el actual. done_text renombra el paso anterior."""
        if not self.exists() or not self.working:
            return
        if done_text and index > 0:
            self.step_rows[index - 1][1].config(text=done_text)
        for i, (icon, label) in enumerate(self.step_rows):
            if i < index:
                icon.config(image=self.icons["done"])
                label.config(fg=TEXT)
            elif i == index:
                label.config(fg=PURPLE_LIGHT)
            else:
                icon.config(image=self.icons["todo"])
                label.config(fg=MUTED)
        # Parar las animaciones del paso anterior antes de empezar las nuevas
        self._stop_animations()
        if index < len(self.step_rows):
            self._spin(self.step_rows[index][0], 0)
        self._animate_progress((index + 0.5) / len(STEPS))

    def _spin(self, icon: tk.Label, frame: int):
        icon.config(image=self.spinner[frame % SPINNER_FRAMES])
        self._spinner_job = self.window.after(SPINNER_MS, self._spin, icon, frame + 1)

    def _animate_progress(self, target: float):
        # Avanza suavemente hacia el objetivo
        self._progress += (target - self._progress) * 0.2
        width = self.progress.winfo_width()
        self.progress.coords(self.progress_bar, 0, 0, width * self._progress, 4)
        if abs(target - self._progress) > 0.002:
            self._progress_job = self.window.after(16, self._animate_progress, target)

    def show_done(self, image_path: Path, game_name: str, source: str, warning: str | None = None):
        self._clear()
        self.working = False
        self.close_x.config(fg=MUTED, cursor="hand2")
        result = tk.Frame(self.body, bg=BG)
        result.pack(anchor="w", fill="x", pady=(8, 0))
        try:
            self.thumb = _thumbnail(image_path)
            tk.Label(result, image=self.thumb, bg=BG).pack(side="left")
        except OSError:
            pass
        text = tk.Frame(result, bg=BG)
        text.pack(side="left", padx=(16, 0), anchor="center", fill="x", expand=True)
        tk.Label(text, text="¡Aviso generado!", bg=BG, fg=TEXT, font=(FONT, 15, "bold")).pack(anchor="w")
        tk.Label(text, text=f"{game_name} · {source}", bg=BG, fg=MUTED, font=(FONT, 10),
                 wraplength=WIDTH - 2 * PADDING - 110, justify="left").pack(anchor="w", pady=(2, 0))
        if warning:
            tk.Label(text, text=_shorten(warning), bg=BG, fg=ERROR_TEXT, font=(FONT, 9),
                     wraplength=WIDTH - 2 * PADDING - 110, justify="left").pack(anchor="w", pady=(6, 0))
        self._set_buttons(("Abrir carpeta", self.on_open_folder, False), ("Cerrar", self.close, True))

    def show_error(self, message: str):
        self._clear()
        self.working = False
        self.close_x.config(fg=MUTED, cursor="hand2")
        self._heading("No se pudo generar")
        box = tk.Frame(self.body, bg=RED)
        box.pack(fill="x", pady=(12, 0))
        tk.Label(box, text=_shorten(message), bg=ERROR_BG, fg=ERROR_TEXT, font=(FONT, 10), justify="left",
                 anchor="w", wraplength=WIDTH - 2 * PADDING - 30, padx=12, pady=10).pack(fill="x", padx=(3, 0))
        self._set_buttons(("Cerrar", self.close, False), ("Reintentar", self.on_retry, True))
