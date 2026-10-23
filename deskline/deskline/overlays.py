"""Desktop overlays that stay in the main process: cursor, clock, monitor, taskbar strip."""

from __future__ import annotations

import ctypes
import math
import os
import random

from PySide6.QtCore import QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QMovie, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QApplication, QWidget

from deskline import winutil

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02


def _user32_key(vk: int) -> bool:
    return bool(winutil.user32.GetAsyncKeyState(vk) & 0x8000)


def _color(hex_color: str) -> QColor:
    color = QColor(hex_color)
    return color if color.isValid() else QColor("#ff3b5c")


class EffectState:
    def __init__(self) -> None:
        self.particles: list[dict] = []
        self.waves: list[dict] = []
        self.last = QPoint()
        self.ready = False
        self.left_down = False
        self.right_down = False
        self.hue = 0.0

    def reset(self) -> None:
        self.particles.clear()
        self.waves.clear()
        self.ready = False


def _particle_color(settings: dict, life_ratio: float, index: int, hue_base: float) -> QColor:
    mode = settings.get("mode", "single")
    if mode == "rainbow":
        color = QColor.fromHsv(int((hue_base + index * 18) % 360), 220, 255)
    elif mode == "gradient":
        color = _color(settings.get("color", "#ff3b5c"))
        color = QColor(
            int(color.red() + (255 - color.red()) * (1 - life_ratio)),
            int(color.green() + (255 - color.green()) * (1 - life_ratio)),
            int(color.blue() + (255 - color.blue()) * (1 - life_ratio)),
        )
    else:
        color = _color(settings.get("color", "#ff3b5c"))
    color.setAlpha(max(0, min(255, int(255 * life_ratio))))
    return color


def cursor_widget_point(
    cursor_x: int,
    cursor_y: int,
    left: int,
    top: int,
    right: int,
    bottom: int,
    widget_w: int,
    widget_h: int,
) -> tuple[float, float] | None:
    """Map a physical cursor into one monitor's widget.

    Mixed DPI means one desktop-wide window does not share a scale with every
    monitor. The cursor is kept in physical pixels and scaled into the widget
    that exactly covers this monitor.
    """
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0 or widget_w <= 0 or widget_h <= 0:
        return None
    if cursor_x < left or cursor_x >= right or cursor_y < top or cursor_y >= bottom:
        return None
    return ((cursor_x - left) * widget_w / width, (cursor_y - top) * widget_h / height)


def _monitor_pixels(screen) -> tuple[int, int, int, int] | None:
    native = screen.nativeInterface()
    if native is None or not hasattr(native, "handle"):
        return None
    info = winutil.MONITORINFO()
    info.cbSize = ctypes.sizeof(info)
    if not winutil.user32.GetMonitorInfoW(int(native.handle()), ctypes.byref(info)):
        return None
    rect = info.rcMonitor
    return rect.left, rect.top, rect.right, rect.bottom


def _cursor_pixels() -> tuple[int, int] | None:
    point = winutil.POINT()
    if not winutil.user32.GetCursorPos(ctypes.byref(point)):
        return None
    return int(point.x), int(point.y)


def advance_effects(state: EffectState, dt: float) -> None:
    for particle in state.particles:
        particle["x"] += particle["vx"]
        particle["y"] += particle["vy"]
        particle["life"] -= dt
        particle["vy"] += 8 * dt
    state.particles = [particle for particle in state.particles if particle["life"] > 0]
    for wave in state.waves:
        wave["age"] += dt
    state.waves = [wave for wave in state.waves if wave["age"] < wave["duration"]]


def step_effects(state: EffectState, settings: dict, x: float, y: float, dt: float) -> None:
    amount = int(settings.get("amount", 50))
    size = int(settings.get("size", 50))
    length = int(settings.get("length", 50))
    spread = int(settings.get("spread", 50))
    move = settings.get("move", "classic")
    max_particles = int(12 + amount * 1.7)
    lifetime = 0.18 + length / 100 * 1.2
    state.hue = (state.hue + dt * 40) % 360

    if not state.ready:
        state.last = QPoint(int(x), int(y))
        state.ready = True
    dx = x - state.last.x()
    dy = y - state.last.y()
    distance = math.hypot(dx, dy)
    if move != "none" and distance > 1.5:
        spawn = 1 + min(6, int(distance / 12))
        spawn = int(spawn * (0.4 + amount / 100))
        for _ in range(spawn):
            if len(state.particles) >= max_particles:
                break
            jitter = spread / 8
            state.particles.append({
                "x": x + random.uniform(-jitter, jitter),
                "y": y + random.uniform(-jitter, jitter),
                "vx": dx * 0.02 + random.uniform(-spread, spread) / 40,
                "vy": dy * 0.02 + random.uniform(-spread, spread) / 40,
                "life": lifetime,
                "max": lifetime,
                "size": 1.5 + size / 18,
                "kind": move,
            })
    state.last = QPoint(int(x), int(y))
    advance_effects(state, dt)

    _click(state, settings, x, y, VK_LBUTTON, "left_down", settings.get("left_click", "shockwave"))
    right = settings.get("right_click", "same")
    if right == "same":
        right = settings.get("left_click", "shockwave")
    _click(state, settings, x, y, VK_RBUTTON, "right_down", right)


def _click(state: EffectState, settings: dict, x: float, y: float, vk: int, attr: str, mode: str) -> None:
    down = _user32_key(vk)
    was = getattr(state, attr)
    setattr(state, attr, down)
    if not down or was or mode == "none":
        return
    state.waves.append({
        "x": x,
        "y": y,
        "age": 0.0,
        "duration": 0.45 if mode == "shockwave" else 0.55,
        "mode": mode,
        "color": settings.get("color", "#ff3b5c"),
    })
    if mode == "burst":
        for index in range(16):
            angle = index / 16 * math.tau
            state.particles.append({
                "x": x,
                "y": y,
                "vx": math.cos(angle) * 180,
                "vy": math.sin(angle) * 180,
                "life": 0.4,
                "max": 0.4,
                "size": 3,
                "kind": "sparks",
            })


def paint_effects(painter: QPainter, state: EffectState, settings: dict) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    glow = int(settings.get("glow", 55))
    for index, particle in enumerate(state.particles):
        ratio = particle["life"] / particle["max"]
        color = _particle_color(settings, ratio, index, state.hue)
        radius = particle["size"] * (0.6 + ratio)
        if particle["kind"] == "glow":
            gradient = QRadialGradient(particle["x"], particle["y"], radius * (1.4 + glow / 80))
            soft = QColor(color)
            soft.setAlpha(color.alpha())
            gradient.setColorAt(0, soft)
            soft.setAlpha(0)
            gradient.setColorAt(1, soft)
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(int(particle["x"]), int(particle["y"])), int(radius * 2), int(radius * 2))
        elif particle["kind"] == "sparks":
            painter.setPen(QPen(color, 1.6))
            painter.drawLine(
                int(particle["x"]),
                int(particle["y"]),
                int(particle["x"] - particle["vx"] * 0.04),
                int(particle["y"] - particle["vy"] * 0.04),
            )
        elif particle["kind"] == "stardust":
            painter.setPen(QPen(color, 1.2))
            arm = radius + 2
            cx, cy = int(particle["x"]), int(particle["y"])
            painter.drawLine(cx - arm, cy, cx + arm, cy)
            painter.drawLine(cx, cy - arm, cx, cy + arm)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPoint(int(particle["x"]), int(particle["y"])), max(1, int(radius)), max(1, int(radius)))

    for wave in state.waves:
        progress = wave["age"] / wave["duration"]
        color = _color(wave["color"])
        color.setAlpha(int(220 * (1 - progress)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if wave["mode"] == "ripple":
            for ring in range(3):
                radius = 8 + progress * 90 + ring * 14
                painter.setPen(QPen(color, 1.4))
                painter.drawEllipse(QPoint(int(wave["x"]), int(wave["y"])), int(radius), int(radius))
        else:
            radius = 6 + progress * 70
            painter.setPen(QPen(color, 2.0))
            painter.drawEllipse(QPoint(int(wave["x"]), int(wave["y"])), int(radius), int(radius))


class _CursorPane(QWidget):
    """Click-through effect layer for a single monitor."""

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.setWindowTitle("Deskline Cursor")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.settings: dict = {}
        self.state = EffectState()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._clock = None
        self._anchored = None
        screen.geometryChanged.connect(self._place)

    def apply(self, settings: dict, active: bool) -> None:
        self.settings = dict(settings)
        if not active:
            self._timer.stop()
            self.hide()
            self.state.reset()
            return
        self._place()
        if not self.isVisible():
            self.show()
            winutil.make_click_through(int(self.winId()))
            self._place()
        if not self._timer.isActive():
            self._timer.start(16)

    def _place(self, *_args) -> None:
        self.setScreen(self.screen)
        self.setGeometry(self.screen.geometry())
        if not self.isVisible():
            return
        bounds = _monitor_pixels(self.screen)
        if bounds is None:
            return
        left, top, right, bottom = bounds
        if self._anchored == bounds and winutil.window_rect(int(self.winId())) is not None:
            rect = winutil.window_rect(int(self.winId()))
            if rect and (rect.left, rect.top, rect.right, rect.bottom) == bounds:
                return
        winutil.user32.SetWindowPos(
            int(self.winId()),
            winutil.HWND_TOPMOST,
            left,
            top,
            right - left,
            bottom - top,
            winutil.SWP_NOACTIVATE,
        )
        self._anchored = bounds

    def _local(self) -> tuple[float, float] | None:
        cursor = _cursor_pixels()
        bounds = _monitor_pixels(self.screen)
        if cursor is None or bounds is None:
            pos = QCursor.pos()
            if not self.screen.geometry().contains(pos):
                return None
            local = self.mapFromGlobal(pos)
            return float(local.x()), float(local.y())
        return cursor_widget_point(cursor[0], cursor[1], *bounds, self.width(), self.height())

    def _tick(self) -> None:
        if not self.isVisible():
            return
        import time
        now = time.perf_counter()
        dt = 0.016 if self._clock is None else min(0.05, now - self._clock)
        self._clock = now
        local = self._local()
        if local is None:
            self.state.ready = False
            advance_effects(self.state, dt)
        else:
            step_effects(self.state, self.settings, local[0], local[1], dt)
        if self.state.particles or self.state.waves:
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        paint_effects(painter, self.state, self.settings)
        painter.end()


class CursorOverlay(QObject):
    """One effect layer per monitor, so a different size or scale stays aligned."""

    def __init__(self):
        super().__init__()
        self._panes: list[_CursorPane] = []
        self._settings: dict = {}
        self._active = False
        app = QApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._screens_changed)
            app.screenRemoved.connect(self._screens_changed)

    def apply(self, settings: dict, active: bool) -> None:
        self._settings = dict(settings)
        self._active = bool(active)
        if not self._active:
            for pane in self._panes:
                pane.apply(self._settings, False)
            return
        self._rebuild()
        for pane in self._panes:
            pane.apply(self._settings, True)

    def hide(self) -> None:
        self._active = False
        for pane in self._panes:
            pane.apply(self._settings, False)

    def _screens_changed(self, _screen=None) -> None:
        if not self._active:
            return
        self._rebuild()
        for pane in self._panes:
            pane.apply(self._settings, True)

    def _rebuild(self) -> None:
        screens = list(QApplication.screens())
        if [pane.screen for pane in self._panes] == screens:
            return
        for pane in self._panes:
            try:
                pane.screen.geometryChanged.disconnect(pane._place)
            except (RuntimeError, TypeError):
                pass
            pane.apply({}, False)
            pane.deleteLater()
        self._panes = [_CursorPane(screen) for screen in screens]


class CursorPreview(QWidget):
    """A small looping preview so the effect can be judged before it covers the desktop."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(180)
        self.settings: dict = {"move": "classic", "enabled": True}
        self.state = EffectState()
        self._t = 0.0
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(16)

    def set_settings(self, settings: dict) -> None:
        self.settings = dict(settings)
        self.settings["move"] = settings.get("move", "classic")

    def _tick(self) -> None:
        self._t += 0.016
        x = self.width() * 0.5 + math.sin(self._t * 1.4) * self.width() * 0.28
        y = self.height() * 0.55 + math.cos(self._t * 1.1) * self.height() * 0.22
        step_effects(self.state, self.settings, x, y, 0.016)
        if int(self._t * 2) % 7 == 0 and int(self._t * 60) % 60 == 0:
            self.state.waves.append({
                "x": x, "y": y, "age": 0.0, "duration": 0.45,
                "mode": self.settings.get("left_click", "shockwave"),
                "color": self.settings.get("color", "#ff3b5c"),
            })
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#101014"))
        painter.drawRoundedRect(self.rect(), 12, 12)
        if self.settings.get("move") == "none" and self.settings.get("left_click") == "none":
            painter.setPen(QColor("#a1a1aa"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Effects are turned off")
        paint_effects(painter, self.state, self.settings)
        painter.end()


def paint_taskbar(painter: QPainter, width: int, height: int, settings: dict, phase: float, frame: QPixmap | None = None) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    band_h = max(4, int(height * int(settings.get("height", 100)) / 100))
    gap = int(width * int(settings.get("side_gap", 0)) / 200)
    top = height - band_h
    radius = int(settings.get("corners", 0)) / 100 * (band_h / 2)
    design = str(settings.get("design") or "wave")
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#1c1c22"))
    painter.drawRoundedRect(gap, top, max(1, width - gap * 2), band_h, radius, radius)
    painter.setClipRect(int(gap), top, max(1, width - gap * 2), band_h)
    if design == "gif" and frame is not None and not frame.isNull():
        painter.drawPixmap(int(gap), top, max(1, width - gap * 2), band_h, frame)
    elif design == "pulse":
        alpha = 90 + int(110 * (0.5 + 0.5 * math.sin(phase * 6)))
        painter.setBrush(QColor(255, 59, 92, alpha))
        painter.drawRect(gap, top, width, band_h)
        painter.setBrush(QColor(124, 58, 237, 200 - alpha // 2))
        inset = int((0.5 + 0.5 * math.sin(phase * 4)) * width * 0.25)
        painter.drawRect(gap + inset, top, max(1, width - inset * 2), band_h)
    elif design == "aurora":
        for index, color in enumerate((QColor("#22d3ee"), QColor("#a78bfa"), QColor("#34d399"), QColor("#f472b6"))):
            color.setAlpha(150)
            painter.setBrush(color)
            offset = math.sin(phase * 3 + index) * 48
            painter.drawRoundedRect(int(index * (width / 5) + offset), top, int(width / 3), band_h, radius, radius)
    elif design == "ember":
        painter.setBrush(QColor("#3f1d12"))
        painter.drawRect(gap, top, width, band_h)
        for index in range(22):
            x = (index * 97 + phase * width) % max(1, width)
            y = top + ((index * 53 + int(phase * 90)) % max(1, band_h))
            painter.setBrush(QColor(255, 120 + (index * 5) % 100, 32, 210))
            painter.drawEllipse(int(x), int(y), 5, 5)
    elif design == "glass":
        painter.setBrush(QColor(255, 255, 255, 42))
        painter.drawRect(gap, top, width, band_h)
        painter.setBrush(QColor(255, 255, 255, 90))
        painter.drawRect(gap, top, width, max(2, band_h // 5))
    else:
        shift = (phase % 1) * (width + 200)
        for index, color in enumerate((QColor("#ff3b5c"), QColor("#7c3aed"), QColor("#f59e0b"), QColor("#ff3b5c"))):
            painter.setBrush(color)
            painter.drawRoundedRect(int(-200 + shift + index * 180), top, 160, band_h, radius, radius)
    dim = abs(int(settings.get("brightness", 0))) / 100
    if dim:
        painter.setBrush(QColor(0, 0, 0, int(180 * dim)))
        painter.drawRect(0, top, width, band_h)
    painter.setClipping(False)
    _paint_center_bar(painter, width, top, band_h, settings)


def _paint_center_bar(painter: QPainter, width: int, top: int, band_h: int, settings: dict) -> None:
    if not settings.get("show_bar"):
        return
    bar_w = max(8, int(width * int(settings.get("bar_width", 40)) / 100))
    bar_h = max(4, int(band_h * int(settings.get("bar_height", 100)) / 100))
    bar_top = top + (band_h - bar_h) / 2
    radius = int(settings.get("bar_radius") or 0) / 100 * (bar_h / 2)
    opacity = max(0, min(100, int(settings.get("bar_opacity") or 55)))
    alpha = int(255 * opacity / 100)
    white = str(settings.get("bar_color") or "black") == "white"
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, alpha) if white else QColor(0, 0, 0, alpha))
    left = (width - bar_w) / 2
    if str(settings.get("bar_mode") or "cover") == "invert":
        painter.drawRoundedRect(0, bar_top, max(0, left), bar_h, radius, radius)
        painter.drawRoundedRect(left + bar_w, bar_top, max(0, width - left - bar_w), bar_h, radius, radius)
        return
    painter.drawRoundedRect(left, bar_top, bar_w, bar_h, radius, radius)


def _sync_movie(owner, settings: dict) -> None:
    path = str(settings.get("gif") or "")
    want = str(settings.get("design") or "") == "gif" and os.path.isfile(path)
    movie = getattr(owner, "_movie", None)
    if not want:
        if movie is not None:
            movie.stop()
        owner._movie = None
        return
    if movie is None or os.path.normcase(movie.fileName()) != os.path.normcase(path):
        movie = QMovie(path)
        movie.start()
        owner._movie = movie


def _movie_frame(owner) -> QPixmap | None:
    movie = getattr(owner, "_movie", None)
    if movie is None:
        return None
    frame = movie.currentPixmap()
    return frame if not frame.isNull() else None


class TaskbarPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(72)
        self.settings: dict = {}
        self.phase = 0.0
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(32)

    def set_settings(self, settings: dict) -> None:
        self.settings = dict(settings)
        _sync_movie(self, self.settings)

    def _tick(self) -> None:
        self.phase += 0.01
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#09090b"))
        paint_taskbar(painter, self.width(), self.height(), self.settings, self.phase, _movie_frame(self))
        painter.end()


class TaskbarOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Deskline Taskbar")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.settings: dict = {}
        self.phase = 0.0
        self._active = False
        self._clear_applied = False
        self._last_rect = None
        self._movie = None
        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(16)

    def apply(self, settings: dict, active: bool) -> None:
        self.settings = dict(settings)
        self._active = bool(active)
        _sync_movie(self, self.settings)
        if not self._active:
            self.hide()
            return
        self._present(force=True)

    def _present(self, force: bool = False) -> None:
        hwnd = winutil.find_window("Shell_TrayWnd")
        if not hwnd or winutil.window_cloaked(hwnd):
            if self.isVisible():
                self.hide()
            return
        self._follow(force=force)
        if not self.isVisible():
            self.show()
            winutil.make_click_through(int(self.winId()), topmost=False)

    def clear_was_applied(self) -> bool:
        return self._clear_applied

    def _follow(self, force: bool = False) -> None:
        hwnd = winutil.find_window("Shell_TrayWnd")
        rect = winutil.window_rect(hwnd)
        if rect is None:
            return
        key = (rect.left, rect.top, rect.right, rect.bottom)
        if force or key != self._last_rect:
            self._last_rect = key
            scale = QApplication.primaryScreen().devicePixelRatio() or 1
            self.setGeometry(
                int(rect.left / scale),
                int(rect.top / scale),
                max(1, int((rect.right - rect.left) / scale)),
                max(1, int((rect.bottom - rect.top) / scale)),
            )
        winutil.place_behind(int(self.winId()), hwnd)

    def _tick(self) -> None:
        if not self._active:
            return
        self._present()
        if not self.isVisible():
            return
        self.phase += 0.008
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        paint_taskbar(painter, self.width(), self.height(), self.settings, self.phase, _movie_frame(self))
        painter.end()


class _Float(QWidget):
    def __init__(self, title: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._drag = None
        self.locked = False
        self.moved = None

    def apply_lock(self, locked: bool) -> None:
        self.locked = locked
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, locked)
        if self.isVisible():
            self.show()
            if locked:
                winutil.make_click_through(int(self.winId()))

    def mousePressEvent(self, event):
        if self.locked or event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag is None or self.locked:
            return
        self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _event):
        self._drag = None
        if self.moved is not None:
            self.moved(self.x(), self.y())


class ClockOverlay(_Float):
    def __init__(self):
        super().__init__("Deskline Clock")
        self.settings: dict = {}
        self.resize(360, 160)
        timer = QTimer(self)
        timer.timeout.connect(self.update)
        timer.start(200)

    def apply(self, settings: dict, active: bool) -> None:
        self.settings = dict(settings)
        if not active:
            self.hide()
            return
        self.move(int(settings.get("clock_x", 80)), int(settings.get("clock_y", 80)))
        self.apply_lock(bool(settings.get("locked")))
        self.show()

    def paintEvent(self, _event):
        from datetime import datetime
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        now = datetime.now()
        hour24 = bool(self.settings.get("hour24", True))
        text = now.strftime("%H:%M" if hour24 else "%I:%M")
        if self.settings.get("seconds", True):
            text += now.strftime(":%S")
        day = now.strftime("%A")
        if self.settings.get("uppercase", True):
            day = day.upper()
        painter.setPen(QColor(255, 255, 255, 230))
        if self.settings.get("weekday", True):
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
            painter.drawText(0, 8, self.width(), 28, Qt.AlignmentFlag.AlignHCenter, day)
        painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Light))
        painter.drawText(0, 36, self.width(), 70, Qt.AlignmentFlag.AlignHCenter, text)
        if self.settings.get("show_date", True):
            painter.setFont(QFont("Segoe UI", 13))
            painter.setPen(QColor(255, 255, 255, 180))
            painter.drawText(0, 112, self.width(), 28, Qt.AlignmentFlag.AlignHCenter, now.strftime("%d %B %Y"))
        painter.end()


class MonitorOverlay(_Float):
    def __init__(self):
        super().__init__("Deskline Monitor")
        self.resize(220, 88)
        self.cpu = 0.0
        self.ram = 0.0
        import psutil
        self._psutil = psutil
        psutil.cpu_percent(None)
        timer = QTimer(self)
        timer.timeout.connect(self._sample)
        timer.start(1000)

    def apply(self, settings: dict, active: bool) -> None:
        if not active:
            self.hide()
            return
        self.move(int(settings.get("monitor_x", 80)), int(settings.get("monitor_y", 220)))
        self.apply_lock(bool(settings.get("locked")))
        self.show()

    def _sample(self) -> None:
        if not self.isVisible():
            return
        self.cpu = self._psutil.cpu_percent(None)
        self.ram = self._psutil.virtual_memory().percent
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(16, 16, 20, 170))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        painter.setPen(QColor("#f4f4f5"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        painter.drawText(16, 28, f"CPU  {self.cpu:.0f}%")
        painter.drawText(16, 56, f"RAM  {self.ram:.0f}%")
        painter.end()


class MusicOverlay(_Float):
    def __init__(self):
        super().__init__("Deskline Music")
        self.resize(300, 96)
        self.title = ""
        self.artist = ""
        self.detail = "Play something to see it here."
        timer = QTimer(self)
        timer.timeout.connect(self._sample)
        timer.start(2000)

    def apply(self, settings: dict, active: bool) -> None:
        if not active:
            self.hide()
            return
        self.move(int(settings.get("music_x", 80)), int(settings.get("music_y", 340)))
        self.apply_lock(bool(settings.get("locked")))
        self.show()
        self._sample()

    def _sample(self) -> None:
        if not self.isVisible():
            return
        from deskline.nowplaying import refresh, snapshot
        refresh()
        current = snapshot()
        self.title = str(current.get("title") or "")
        self.artist = str(current.get("artist") or "")
        self.detail = str(current.get("detail") or "")
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(16, 16, 20, 180))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        painter.setPen(QColor("#f4f4f5"))
        painter.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        painter.drawText(16, 28, self.width() - 32, 24, Qt.AlignmentFlag.AlignLeft, self.title or "Now playing")
        painter.setFont(QFont("Segoe UI", 11))
        painter.setPen(QColor("#a1a1aa"))
        painter.drawText(16, 56, self.width() - 32, 24, Qt.AlignmentFlag.AlignLeft, self.artist or self.detail)
        painter.end()


class GamesOverlay(_Float):
    def __init__(self):
        super().__init__("Deskline Games")
        self.resize(260, 220)
        self.games: list[dict] = []
        self._ticks = 0
        timer = QTimer(self)
        timer.timeout.connect(self._sample)
        timer.start(1000)

    def apply(self, settings: dict, active: bool) -> None:
        if not active:
            self.hide()
            return
        self.move(int(settings.get("games_x", 420)), int(settings.get("games_y", 80)))
        self.apply_lock(bool(settings.get("locked")))
        self.show()
        self._sample()

    def _sample(self) -> None:
        if not self.isVisible():
            return
        self._ticks += 1
        if self.games and self._ticks % 8 != 1:
            return
        from deskline.steamlib import installed_games
        self.games = installed_games()[:8]
        self.update()

    def mousePressEvent(self, event):
        self._press = event.position()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        press = getattr(self, "_press", None)
        super().mouseReleaseEvent(event)
        if self.locked or press is None:
            return
        if (event.position() - press).manhattanLength() > 8:
            return
        index = int((event.position().y() - 36) // 22)
        if 0 <= index < len(self.games):
            os.startfile(f"steam://rungameid/{self.games[index]['appid']}")

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(16, 16, 20, 185))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        painter.setPen(QColor("#f4f4f5"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        painter.drawText(16, 24, "Game library")
        painter.setFont(QFont("Segoe UI", 11))
        if not self.games:
            painter.setPen(QColor("#a1a1aa"))
            painter.drawText(16, 56, self.width() - 32, 40, Qt.AlignmentFlag.AlignLeft, "No installed Steam games found.")
            painter.end()
            return
        for index, game in enumerate(self.games):
            painter.setPen(QColor("#e4e4e7"))
            painter.drawText(16, 48 + index * 22, self.width() - 28, 20, Qt.AlignmentFlag.AlignLeft, str(game["name"]))
        painter.end()
