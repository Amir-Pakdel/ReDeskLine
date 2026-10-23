"""Replace the arrow cursor with an original shape, then put Windows cursors back."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPen

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
SPI_SETCURSORS = 0x0057
OCR_NORMAL = 32512
DI_RGB_COLORS = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
gdi32.CreateBitmap.restype = wintypes.HBITMAP
gdi32.SetBitmapBits.argtypes = [wintypes.HBITMAP, wintypes.DWORD, ctypes.c_void_p]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.CreateIconIndirect.restype = wintypes.HANDLE
user32.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
user32.DestroyCursor.argtypes = [wintypes.HANDLE]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]


def restore_pointer() -> None:
    user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)


def _set_cursor(image: QImage, hotspot_x: int, hotspot_y: int) -> bool:
    image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    size = 32
    canvas = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawImage(0, 0, image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    painter.end()
    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = size
    header.biHeight = -size
    header.biPlanes = 1
    header.biBitCount = 32
    bits = ctypes.c_void_p()
    hdc = user32.GetDC(None)
    color = gdi32.CreateDIBSection(hdc, ctypes.byref(header), DI_RGB_COLORS, ctypes.byref(bits), None, 0)
    user32.ReleaseDC(None, hdc)
    if not color or not bits:
        return False
    raw = canvas.bits()
    if hasattr(raw, "setsize"):
        raw.setsize(canvas.sizeInBytes())
        payload = bytes(raw)
    else:
        payload = bytes(raw)
    ctypes.memmove(bits, payload, size * size * 4)
    mask_bytes = bytearray()
    for y in range(size):
        for byte_index in range(4):
            value = 0
            for bit in range(8):
                x = byte_index * 8 + bit
                pixel = canvas.pixelColor(x, y)
                if pixel.alpha() < 24:
                    value |= 0x80 >> bit
            mask_bytes.append(value)
    mask_buf = (ctypes.c_ubyte * len(mask_bytes)).from_buffer(mask_bytes)
    mask = gdi32.CreateBitmap(size, size, 1, 1, mask_buf)
    info = ICONINFO()
    info.fIcon = False
    info.xHotspot = max(0, min(size - 1, hotspot_x))
    info.yHotspot = max(0, min(size - 1, hotspot_y))
    info.hbmMask = mask
    info.hbmColor = color
    cursor = user32.CreateIconIndirect(ctypes.byref(info))
    gdi32.DeleteObject(mask)
    gdi32.DeleteObject(color)
    if not cursor:
        return False
    if not user32.SetSystemCursor(cursor, OCR_NORMAL):
        user32.DestroyCursor(cursor)
        return False
    return True


def _shape(style: str, color: str, phase: int) -> tuple[QImage, int, int]:
    image = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    paint = QColor(color)
    if not paint.isValid():
        paint = QColor("#ff3b5c")
    if style == "arrow":
        painter.setBrush(paint)
        painter.setPen(QPen(QColor("#111111"), 1))
        painter.drawPolygon([
            QPoint(4, 3), QPoint(4, 26), QPoint(10, 20), QPoint(16, 29),
            QPoint(20, 27), QPoint(14, 18), QPoint(22, 18),
        ])
        painter.end()
        return image, 4, 3
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(paint, 2))
    if style == "cross":
        painter.drawLine(16, 4, 16, 28)
        painter.drawLine(4, 16, 28, 16)
    elif style == "dot":
        painter.setBrush(paint)
        painter.drawEllipse(10, 10, 12, 12)
    else:
        radius = 8 + (phase % 5)
        painter.drawEllipse(16 - radius, 16 - radius, radius * 2, radius * 2)
        painter.setBrush(paint)
        painter.drawEllipse(14, 14, 4, 4)
    painter.end()
    return image, 16, 16


def _gif_frames(path: str) -> list[QImage]:
    reader = QImageReader(path)
    frames: list[QImage] = []
    while True:
        frame = reader.read()
        if frame.isNull():
            break
        frames.append(frame)
        if len(frames) >= 24:
            break
    return frames


class PointerDriver(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._style = "system"
        self._color = "#ff3b5c"
        self._gif = ""
        self._frames: list[QImage] = []
        self._phase = 0
        self._changed = False
        self._active = False

    def apply(self, settings: dict, active: bool) -> None:
        style = str(settings.get("pointer") or "system")
        color = str(settings.get("color") or "#ff3b5c")
        gif = str(settings.get("pointer_gif") or "")
        if not active or style == "system":
            self._timer.stop()
            self._active = False
            if self._changed:
                restore_pointer()
                self._changed = False
            return
        changed = (style, color, gif) != (self._style, self._color, self._gif) or not self._active
        self._style = style
        self._color = color
        self._gif = gif
        self._active = True
        if style == "gif":
            if changed:
                self._frames = _gif_frames(gif)
                self._phase = 0
            self._timer.start(100)
            self._paint()
            return
        if style == "ring":
            self._timer.start(120)
            if changed:
                self._paint()
            return
        self._timer.stop()
        if changed:
            self._paint()

    def _tick(self) -> None:
        self._phase += 1
        self._paint()

    def _paint(self) -> None:
        if self._style == "gif" and self._frames:
            image = self._frames[self._phase % len(self._frames)]
            ok = _set_cursor(image, 16, 16)
        else:
            image, hot_x, hot_y = _shape(self._style, self._color, self._phase)
            ok = _set_cursor(image, hot_x, hot_y)
        if ok:
            self._changed = True

    def shutdown(self) -> None:
        self._timer.stop()
        if self._changed:
            restore_pointer()
            self._changed = False
