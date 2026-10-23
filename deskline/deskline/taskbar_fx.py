"""Taskbar tint, rounded shape, and dock width. The original bar is restored on exit."""

from __future__ import annotations

import ctypes

from deskline import winutil

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
user32.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
user32.SetWindowRgn.restype = ctypes.c_int

_STATES = {
    "normal": 0,
    "opaque": 1,
    "clear": 2,
    "blur": 3,
    "acrylic": 4,
}

_dock_saved: tuple[int, int, int, int] | None = None
_shape_key: tuple | None = None
_shaped = False


def apply(section: dict, active: bool, maximized: bool) -> None:
    hwnd = winutil.find_window("Shell_TrayWnd")
    if not hwnd or not active:
        restore()
        return
    _apply_accent(hwnd, _choice(section, maximized), section)
    _apply_dock(hwnd, bool(section.get("dock")), int(section.get("dock_width") or 60))
    _apply_shape(hwnd, int(section.get("shape_margin") or 0), int(section.get("shape_radius") or 0))


def restore() -> None:
    hwnd = winutil.find_window("Shell_TrayWnd")
    if not hwnd:
        return
    _apply_accent(hwnd, "normal", {})
    _apply_shape(hwnd, 0, 0)
    _restore_dock(hwnd)


def _choice(section: dict, maximized: bool) -> str:
    if not section.get("clear", True):
        return "normal"
    dynamic = str(section.get("dynamic_maximized") or "same")
    if maximized and dynamic not in {"", "same"}:
        return dynamic if dynamic in _STATES else "clear"
    accent = str(section.get("accent") or "clear")
    return accent if accent in _STATES else "clear"


def _color(section: dict, opaque: bool) -> int:
    text = str(section.get("accent_color") or "#000000").removeprefix("#")
    if len(text) != 6:
        text = "000000"
    try:
        red = int(text[0:2], 16)
        green = int(text[2:4], 16)
        blue = int(text[4:6], 16)
    except ValueError:
        red = green = blue = 0
    opacity = 100 if opaque else max(0, min(100, int(section.get("accent_opacity") or 40)))
    alpha = int(opacity * 255 / 100)
    return (alpha << 24) | (blue << 16) | (green << 8) | red


def _apply_accent(hwnd: int, name: str, section: dict) -> None:
    state = _STATES.get(name, 0)
    policy = winutil.ACCENTPOLICY()
    policy.AccentState = state
    policy.AccentFlags = 2 if state else 0
    policy.GradientColor = _color(section, name == "opaque") if state else 0
    data = winutil.WINCOMPATTRDATA()
    data.Attribute = winutil.WCA_ACCENT_POLICY
    data.Data = ctypes.addressof(policy)
    data.SizeOfData = ctypes.sizeof(policy)
    try:
        user32.SetWindowCompositionAttribute.argtypes = [ctypes.c_void_p, ctypes.POINTER(winutil.WINCOMPATTRDATA)]
        user32.SetWindowCompositionAttribute.restype = ctypes.c_int
        user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
    except Exception:
        return


def _apply_shape(hwnd: int, margin: int, radius: int) -> None:
    global _shape_key, _shaped
    rect = winutil.window_rect(hwnd)
    if rect is None:
        return
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if margin <= 0 and radius <= 0:
        if _shaped:
            user32.SetWindowRgn(hwnd, None, True)
            _shaped = False
        _shape_key = None
        return
    key = (margin, radius, width, height)
    if key == _shape_key:
        return
    region = gdi32.CreateRoundRectRgn(
        margin,
        margin,
        max(margin + 2, width - margin),
        max(margin + 2, height - margin),
        max(0, radius) * 2,
        max(0, radius) * 2,
    )
    if not region:
        return
    if user32.SetWindowRgn(hwnd, region, True):
        _shaped = True
        _shape_key = key
        return
    gdi32.DeleteObject(region)


def _apply_dock(hwnd: int, enabled: bool, percent: int) -> None:
    global _dock_saved
    rect = winutil.window_rect(hwnd)
    monitor = winutil._monitor_from(hwnd)
    if rect is None or monitor is None:
        return
    if not enabled:
        _restore_dock(hwnd)
        return
    if _dock_saved is None:
        _dock_saved = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    full_width = monitor.right - monitor.left
    width = max(120, int(full_width * max(20, min(100, percent)) / 100))
    left = monitor.left + max(0, (full_width - width) // 2)
    user32.SetWindowPos(
        hwnd, None, left, _dock_saved[1], width, _dock_saved[3],
        winutil.SWP_NOZORDER | winutil.SWP_NOACTIVATE,
    )


def _restore_dock(hwnd: int) -> None:
    global _dock_saved
    saved = _dock_saved
    _dock_saved = None
    if saved is None:
        return
    user32.SetWindowPos(
        hwnd, None, saved[0], saved[1], saved[2], saved[3],
        winutil.SWP_NOZORDER | winutil.SWP_NOACTIVATE,
    )
