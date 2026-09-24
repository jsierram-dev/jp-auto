"""Localiza el monitor donde está la ventana de OBS (Windows), para abrir el popup ahí."""

import sys

OBS_EXECUTABLES = ("obs64.exe", "obs32.exe", "obs.exe")

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _GW_OWNER = 4
    _MONITOR_DEFAULTTONEAREST = 2

    class _MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    _EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _process_name(pid: int) -> str:
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return buffer.value.rsplit("\\", 1)[-1].lower()
    finally:
        _kernel32.CloseHandle(handle)


def _find_obs_window():
    """Ventana principal visible de OBS (sin ventana propietaria), o None."""
    found = []

    def callback(hwnd, _):
        if _user32.IsWindowVisible(hwnd) and not _user32.GetWindow(hwnd, _GW_OWNER):
            pid = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if _process_name(pid.value) in OBS_EXECUTABLES:
                found.append(hwnd)
                return False  # basta con la primera
        return True

    _user32.EnumWindows(_EnumWindowsProc(callback), 0)
    return found[0] if found else None


def obs_work_area() -> tuple[int, int, int, int] | None:
    """Área útil (sin barra de tareas) del monitor de OBS: (izquierda, arriba, derecha, abajo).

    Si OBS está minimizado, Windows usa la posición que tenía antes de minimizarse.
    Devuelve None si no es Windows o no encuentra OBS.
    """
    if sys.platform != "win32":
        return None
    try:
        hwnd = _find_obs_window()
        if not hwnd:
            return None
        monitor = _user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONEAREST)
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        if not _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        work = info.rcWork
        return work.left, work.top, work.right, work.bottom
    except OSError:
        return None


if __name__ == "__main__":
    area = obs_work_area()
    print(f"Monitor de OBS (área útil): {area}" if area else "No se ha encontrado la ventana de OBS.")
