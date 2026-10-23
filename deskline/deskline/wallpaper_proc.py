"""Live wallpaper process. Direct3D output is enabled before Qt starts when the frame is painted."""

from __future__ import annotations

import os
import sys
import time

from deskline.config import read_session
from deskline.paths import CONFIG_PATH, WALLPAPER_STATUS, ensure_data_dir
from deskline.winutil import (
    attach_wallpaper,
    detach_wallpaper,
    enable_dpi_awareness,
    ensure_wallpaper_attached,
    erase_background_handled,
    foreground_fullscreen,
)

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _read_config() -> dict:
    import json
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    section = raw.get("wallpaper", {})
    return section if isinstance(section, dict) else {}


def _paint_mode(section: dict) -> bool:
    from deskline.wallpaper_prep import needs_paint
    return needs_paint(section)


def _write_status(state: str, message: str) -> None:
    import json
    ensure_data_dir()
    temporary = WALLPAPER_STATUS.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"state": state, "message": message}), encoding="utf-8")
    temporary.replace(WALLPAPER_STATUS)


def _cover_source(image_w: int, image_h: int, target_w: int, target_h: int):
    from PySide6.QtCore import QRectF
    if image_w <= 0 or image_h <= 0 or target_w <= 0 or target_h <= 0:
        return QRectF(0, 0, max(0, image_w), max(0, image_h))
    target_aspect = target_w / target_h
    image_aspect = image_w / image_h
    if image_aspect > target_aspect:
        crop_w = min(image_w, round(image_h * target_aspect))
        return QRectF((image_w - crop_w) // 2, 0, crop_w, image_h)
    crop_h = min(image_h, round(image_w / target_aspect))
    return QRectF(0, (image_h - crop_h) // 2, image_w, crop_h)


def _screen_box(span: bool) -> tuple[int, int, int, int]:
    from PySide6.QtWidgets import QApplication

    screens = [screen for screen in QApplication.screens() if screen is not None]
    if not screens:
        return 0, 0, 1920, 1079
    if not span:
        screen = QApplication.primaryScreen().geometry()
        return screen.x(), screen.y(), screen.width(), max(1, screen.height() - 1)
    left = min(screen.geometry().x() for screen in screens)
    top = min(screen.geometry().y() for screen in screens)
    right = max(screen.geometry().x() + screen.geometry().width() for screen in screens)
    bottom = max(screen.geometry().y() + screen.geometry().height() for screen in screens)
    return left, top, max(1, right - left), max(1, bottom - top - 1)


def _prepare_window(window, span: bool = False) -> None:
    from PySide6.QtCore import Qt

    window.setWindowTitle("DesklineWallpaper")
    window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Tool
        | Qt.WindowType.WindowDoesNotAcceptFocus
    )
    # One logical pixel short of the panel so Windows does not treat it as an exclusive fullscreen app.
    window.setGeometry(*_screen_box(span))


def _foreground_exe() -> str:
    import ctypes
    from ctypes import wintypes

    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    try:
        import psutil
        return psutil.Process(int(pid.value)).name()
    except Exception:
        return ""


def playback_should_pause(section: dict) -> bool:
    from deskline.ambient import ac_line

    if read_session().get("pause_effects") or foreground_fullscreen() is not None:
        return True
    if section.get("pause_battery") and ac_line() == 0:
        return True
    names = {part.strip().lower() for part in str(section.get("pause_apps") or "").split(",") if part.strip()}
    if not names:
        return False
    return _foreground_exe().lower() in names


def update_screensaver(window, state: dict, section: dict) -> None:
    from PySide6.QtCore import Qt
    from deskline.winutil import idle_seconds

    limit = max(1, int(section.get("idle_minutes") or 5)) * 60
    want = bool(section.get("idle_screensaver")) and idle_seconds() >= limit
    if want and not state.get("saver"):
        detach_wallpaper(int(window.winId()))
        window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        window.setGeometry(*_screen_box(True))
        window.show()
        state["saver"] = True
        return
    if state.get("saver") and idle_seconds() < 2:
        window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        window.setGeometry(*_screen_box(bool(section.get("all_monitors"))))
        window.show()
        attach_wallpaper(int(window.winId()))
        state["saver"] = False


class WallpaperBase:
    def setup_player(self, window, section: dict, painted: bool) -> None:
        from PySide6.QtCore import QUrl, QTimer
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        self.window = window
        self.section = dict(section)
        self.painted = painted
        self.player = QMediaPlayer(window)
        self.audio = QAudioOutput(window)
        self.player.setAudioOutput(self.audio)
        self.player.setLoops(QMediaPlayer.Loops.Infinite)
        self.player.errorOccurred.connect(self._on_error)
        self._paused = False
        self._layer = {"saver": False}
        self._playing = ""
        self._slide_path = ""
        self._slide_name = ""
        self._slide_left = 0.0
        self._load(section)
        self._attach_timer = QTimer(window)
        self._attach_timer.timeout.connect(self._reattach)
        self._attach_timer.start(1000)
        self._poll = QTimer(window)
        self._poll.timeout.connect(self._poll_settings)
        self._poll.start(400)
        self._cover = QTimer(window)
        self._cover.timeout.connect(self._pause_if_covered)
        self._cover.start(1000)

    def _chosen_media(self, section: dict) -> tuple[str, str]:
        from deskline.wallpaper_prep import playlist, resolve
        if section.get("slideshow"):
            rows = playlist(section)
            if rows and (not self._slide_path or self._slide_left <= 0):
                current = [index for index, row in enumerate(rows) if row[2] == self._slide_path]
                nxt = rows[(current[0] + 1) % len(rows)] if current else rows[0]
                self._slide_path = nxt[2]
                self._slide_name = nxt[1]
                self._slide_left = max(60, int(section.get("slideshow_minutes") or 10) * 60)
            if self._slide_path:
                return self._slide_path, self._slide_name or "Slideshow"
        else:
            self._slide_path = ""
        _kind, path, name = resolve(section)
        return path, name

    def _load(self, section: dict) -> None:
        from PySide6.QtCore import QUrl
        from pathlib import Path

        path, name = self._chosen_media(section)
        self.section = dict(section)
        self.audio.setMuted(bool(section.get("muted", True)))
        self.audio.setVolume(0.0 if section.get("muted", True) else 0.35)
        if not path or not Path(path).is_file():
            _write_status("error", "Import a video first.")
            return
        if path == self._playing:
            return
        self._playing = path
        self.player.setSource(QUrl.fromLocalFile(path))
        if not self._paused:
            self.player.play()
        _write_status("playing", name)

    def _on_error(self, _error, message: str) -> None:
        _write_status("error", message or "Windows could not play this video.")

    def attach(self) -> None:
        hwnd = int(self.window.winId())
        if attach_wallpaper(hwnd):
            name = self.section.get("path") or ""
            _write_status("attached", f"Behind the desktop icons. {name}")
        else:
            _write_status("error", "The desktop wallpaper layer was not found. The video stays in a normal window.")

    def _reattach(self) -> None:
        ensure_wallpaper_attached(int(self.window.winId()))

    def _poll_settings(self) -> None:
        from PySide6.QtWidgets import QApplication

        session = read_session()
        if session.get("stop_wallpaper"):
            QApplication.quit()
            return
        section = _read_config()
        source = str(section.get("source") or "media")
        if not section.get("enabled") or source not in {"", "media"} or _paint_mode(section) != self.painted:
            QApplication.quit()
            return
        update_screensaver(self.window, self._layer, section)
        self.audio.setMuted(bool(section.get("muted", True)))
        if section.get("slideshow"):
            self._slide_left -= 0.4
        self._load(section)
        self._apply_pause(bool(session.get("pause_effects")))

    def _pause_if_covered(self) -> None:
        self._apply_pause(playback_should_pause(_read_config()))

    def _apply_pause(self, pause: bool) -> None:
        if pause == self._paused:
            return
        self._paused = pause
        if pause:
            self.player.pause()
        else:
            self.player.play()

    def detach(self) -> None:
        try:
            detach_wallpaper(int(self.window.winId()))
        except Exception:
            return


class VideoWallpaper:
    """Hardware video window. Qt paints this with Direct3D, which the new desktop can show."""

    def __init__(self, section: dict):
        from PySide6.QtCore import Qt
        from PySide6.QtMultimediaWidgets import QVideoWidget

        class Window(QVideoWidget):
            def nativeEvent(self, event_type, message):
                if event_type == b"windows_generic_MSG" and erase_background_handled(message):
                    return True, 1
                return super().nativeEvent(event_type, message)

        self.window = Window()
        _prepare_window(self.window, bool(section.get("all_monitors")))
        self.window.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        self.logic = WallpaperBase()
        self.logic.setup_player(self.window, section, painted=False)
        self.logic.player.setVideoOutput(self.window)

    def show(self) -> None:
        self.window.show()
        self.logic.attach()

    def detach(self) -> None:
        self.logic.detach()


class PaintedWallpaper:
    """Used when blur or brightness is on. Frames are drawn, then presented through Direct3D."""

    def __init__(self, section: dict):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPainter
        from PySide6.QtMultimedia import QVideoSink
        from PySide6.QtWidgets import QWidget

        owner = self

        class Window(QWidget):
            def nativeEvent(self, event_type, message):
                if event_type == b"windows_generic_MSG" and erase_background_handled(message):
                    return True, 1
                return super().nativeEvent(event_type, message)

            def paintEvent(self, _event):
                owner._paint(QPainter, Qt)

        self.window = Window()
        self.window.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.window.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        _prepare_window(self.window, bool(section.get("all_monitors")))
        self.sink = QVideoSink(self.window)
        self.sink.videoFrameChanged.connect(self._on_frame)
        from deskline.wallpaper_fx import OverlayField
        self.field = OverlayField()
        self.frame = None
        self._last_paint = 0.0
        self.logic = WallpaperBase()
        self.logic.setup_player(self.window, section, painted=True)
        self.logic.player.setVideoOutput(self.sink)
        from PySide6.QtCore import QTimer
        self._draw = QTimer(self.window)
        self._draw.timeout.connect(self.window.update)
        self._draw.start(33)

    def _on_frame(self, frame) -> None:
        if frame.isValid():
            self.frame = frame

    def _paint(self, painter_cls, qt) -> None:
        painter = painter_cls(self.window)
        painter.fillRect(self.window.rect(), qt.GlobalColor.black)
        image = None
        if self.frame is not None:
            image = self.frame.toImage()
            self.frame = None
            if not image.isNull():
                self._image = image
        image = getattr(self, "_image", None)
        if image is not None and not image.isNull():
            source = _cover_source(image.width(), image.height(), self.window.width(), self.window.height())
            blur = int(self.logic.section.get("blur") or 0)
            if blur > 0:
                factor = max(0.08, 1 - blur / 140)
                small_w = max(1, int(self.window.width() * factor))
                small_h = max(1, int(self.window.height() * factor))
                image = image.scaled(small_w, small_h)
            from PySide6.QtCore import QRectF
            painter.drawImage(QRectF(self.window.rect()), image, source if blur <= 0 else QRectF(image.rect()))
            brightness = int(self.logic.section.get("brightness") or 0)
            if brightness < 0:
                from PySide6.QtGui import QColor
                painter.fillRect(self.window.rect(), QColor(0, 0, 0, int(200 * abs(brightness) / 100)))
            from deskline.wallpaper_fx import paint_overlay
            paint_overlay(
                painter, self.field, str(self.logic.section.get("overlay") or "none"),
                self.window.width(), self.window.height(), 0.033,
                color=str(self.logic.section.get("overlay_color") or "#ffffff"),
                amount=int(self.logic.section.get("overlay_amount") or 50),
            )
        painter.end()

    def show(self) -> None:
        self.window.show()
        self.logic.attach()

    def detach(self) -> None:
        self.logic.detach()


class WebWallpaper:
    def __init__(self, section: dict, view_cls):
        from PySide6.QtCore import QTimer, QUrl

        self.window = view_cls()
        self.window.setWindowTitle("DesklineWallpaper")
        _prepare_window(self.window, bool(section.get("all_monitors")))
        self._url = ""
        self._layer = {"saver": False}
        self._load(section)
        timer = QTimer(self.window)
        timer.timeout.connect(self._poll)
        timer.start(500)

    def _load(self, section: dict) -> None:
        from PySide6.QtCore import QUrl

        url = str(section.get("url") or "")
        if url == self._url:
            return
        self._url = url
        if url.startswith("http://") or url.startswith("https://"):
            self.window.setUrl(QUrl(url))
            _write_status("playing", url)
            return
        _write_status("error", "Use an http or https address.")

    def _poll(self) -> None:
        from PySide6.QtWidgets import QApplication

        if read_session().get("stop_wallpaper"):
            QApplication.quit()
            return
        section = _read_config()
        if not section.get("enabled") or str(section.get("source") or "") != "web":
            QApplication.quit()
            return
        self._load(section)
        update_screensaver(self.window, self._layer, section)
        if playback_should_pause(section) and not self._layer.get("saver"):
            self.window.hide()
        elif not self._layer.get("saver") and not self.window.isVisible():
            self.window.show()

    def show(self) -> None:
        self.window.show()
        if attach_wallpaper(int(self.window.winId())):
            _write_status("attached", f"Web page behind the icons. {self._url}")
        else:
            _write_status("error", "The desktop wallpaper layer was not found. The page stays in a normal window.")

    def detach(self) -> None:
        detach_wallpaper(int(self.window.winId()))


class ShaderWallpaper:
    def __init__(self, section: dict):
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QPainter
        from PySide6.QtWidgets import QWidget

        owner = self

        class Window(QWidget):
            def nativeEvent(self, event_type, message):
                if event_type == b"windows_generic_MSG" and erase_background_handled(message):
                    return True, 1
                return super().nativeEvent(event_type, message)

            def paintEvent(self, _event):
                painter = QPainter(self)
                from deskline.wallpaper_fx import paint_shader
                paint_shader(painter, owner.kind, self.width(), self.height(), owner.phase)
                painter.end()

        self.kind = str(section.get("shader") or "plasma")
        self.phase = 0.0
        self._layer = {"saver": False}
        self.window = Window()
        self.window.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.window.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        _prepare_window(self.window, bool(section.get("all_monitors")))
        timer = QTimer(self.window)
        timer.timeout.connect(self._tick)
        timer.start(33)

    def _tick(self) -> None:
        from PySide6.QtWidgets import QApplication

        if read_session().get("stop_wallpaper"):
            QApplication.quit()
            return
        section = _read_config()
        if not section.get("enabled") or str(section.get("source") or "") != "shader":
            QApplication.quit()
            return
        self.kind = str(section.get("shader") or "plasma")
        update_screensaver(self.window, self._layer, section)
        if playback_should_pause(section) and not self._layer.get("saver"):
            return
        self.phase += 0.03
        self.window.update()

    def show(self) -> None:
        self.window.show()
        if attach_wallpaper(int(self.window.winId())):
            _write_status("attached", f"Pattern behind the icons. {self.kind}")
        else:
            _write_status("error", "The desktop wallpaper layer was not found. The pattern stays in a normal window.")

    def detach(self) -> None:
        detach_wallpaper(int(self.window.winId()))


def main() -> None:
    from deskline.wallpaper_prep import resolve
    section = _read_config()
    source = str(section.get("source") or "media")
    if source == "web":
        enable_dpi_awareness()
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            _write_status("error", "The web wallpaper component is not installed in this Python environment.")
            return
        from PySide6.QtWidgets import QApplication

        app = QApplication(sys.argv)
        host = WebWallpaper(section, QWebEngineView)
        app.aboutToQuit.connect(host.detach)
        host.show()
        sys.exit(app.exec())
    if source == "shader":
        os.environ["QT_WIDGETS_RHI"] = "1"
        os.environ["QT_WIDGETS_RHI_BACKEND"] = "d3d11"
        enable_dpi_awareness()
        from PySide6.QtWidgets import QApplication

        app = QApplication(sys.argv)
        host = ShaderWallpaper(section)
        app.aboutToQuit.connect(host.detach)
        host.show()
        sys.exit(app.exec())
    kind, path, _name = resolve(section)
    if kind == "image":
        _write_status("error", "Still images use the normal Windows wallpaper.")
        return
    if not path:
        _write_status("error", "Import a video first.")
        return
    if _paint_mode(section):
        os.environ["QT_WIDGETS_RHI"] = "1"
        os.environ["QT_WIDGETS_RHI_BACKEND"] = "d3d11"
    enable_dpi_awareness()
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    host = PaintedWallpaper(section) if _paint_mode(section) else VideoWallpaper(section)
    app.aboutToQuit.connect(host.detach)
    host.show()
    started = time.perf_counter()
    code = app.exec()
    host.detach()
    if time.perf_counter() - started < 1:
        _write_status("error", "The wallpaper window closed immediately.")
    sys.exit(code)


if __name__ == "__main__":
    main()
