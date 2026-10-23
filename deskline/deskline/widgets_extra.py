"""Disk, network, notes, and a start-menu list. They sit on the desktop and can be dragged."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout

from deskline.overlays import _Float


class DiskOverlay(_Float):
    def __init__(self):
        super().__init__("Deskline Disk")
        self.resize(220, 72)
        self.detail = "Disk"
        import psutil
        self._psutil = psutil
        timer = QTimer(self)
        timer.timeout.connect(self._sample)
        timer.start(2000)

    def apply(self, settings: dict, active: bool) -> None:
        if not active:
            self.hide()
            return
        self.move(int(settings.get("disk_x", 80)), int(settings.get("disk_y", 460)))
        self.apply_lock(bool(settings.get("locked")))
        self.show()

    def _sample(self) -> None:
        if not self.isVisible():
            return
        usage = self._psutil.disk_usage("C:\\")
        free = usage.free / (1024 ** 3)
        self.detail = f"C:  {usage.percent:.0f}% used\n{free:.1f} GB free"
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(16, 16, 20, 180))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        painter.setPen(QColor("#f4f4f5"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        painter.drawText(16, 28, self.width() - 28, 36, Qt.AlignmentFlag.AlignLeft, self.detail)
        painter.end()


class NetOverlay(_Float):
    def __init__(self):
        super().__init__("Deskline Network")
        self.resize(220, 72)
        self.detail = "Network"
        import psutil
        self._psutil = psutil
        counters = psutil.net_io_counters()
        self._last = (counters.bytes_recv, counters.bytes_sent)
        timer = QTimer(self)
        timer.timeout.connect(self._sample)
        timer.start(1000)

    def apply(self, settings: dict, active: bool) -> None:
        if not active:
            self.hide()
            return
        self.move(int(settings.get("net_x", 320)), int(settings.get("net_y", 460)))
        self.apply_lock(bool(settings.get("locked")))
        self.show()

    def _sample(self) -> None:
        if not self.isVisible():
            return
        counters = self._psutil.net_io_counters()
        down = max(0, counters.bytes_recv - self._last[0]) / 1024
        up = max(0, counters.bytes_sent - self._last[1]) / 1024
        self._last = (counters.bytes_recv, counters.bytes_sent)
        self.detail = f"Down  {down:.0f} KB/s\nUp    {up:.0f} KB/s"
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(16, 16, 20, 180))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        painter.setPen(QColor("#f4f4f5"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        painter.drawText(16, 26, self.width() - 28, 40, Qt.AlignmentFlag.AlignLeft, self.detail)
        painter.end()


class NotesOverlay(_Float):
    def __init__(self):
        super().__init__("Deskline Notes")
        self.resize(280, 180)
        self.on_text = None
        self._ready = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Notes")
        layout.addWidget(self.edit)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save)
        self.edit.textChanged.connect(lambda: self._save_timer.start(400))

    def apply(self, settings: dict, active: bool) -> None:
        if not active:
            self.hide()
            return
        self.move(int(settings.get("notes_x", 80)), int(settings.get("notes_y", 560)))
        self.apply_lock(bool(settings.get("locked")))
        text = str(settings.get("notes_text") or "")
        if not self.edit.hasFocus() and self.edit.toPlainText() != text:
            self._ready = False
            self.edit.setPlainText(text)
            self._ready = True
        else:
            self._ready = True
        self.edit.setReadOnly(bool(settings.get("locked")))
        self.show()

    def _save(self) -> None:
        if self._ready and self.on_text is not None:
            self.on_text(self.edit.toPlainText())


class LaunchOverlay(_Float):
    def __init__(self):
        super().__init__("Deskline Start")
        self.resize(260, 240)
        self.apps: list[dict] = []
        self._query = ""

    def apply(self, settings: dict, active: bool) -> None:
        if not active:
            self.hide()
            return
        self.move(int(settings.get("launch_x", 560)), int(settings.get("launch_y", 80)))
        self.apply_lock(bool(settings.get("locked")))
        query = str(settings.get("launch_query") or "").strip().lower()
        if query != self._query or not self.apps:
            from deskline.launchers import start_menu_apps
            self._query = query
            apps = start_menu_apps()
            if query:
                apps = [item for item in apps if query in item["name"].lower()]
            self.apps = apps[:10]
        self.show()
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
        index = int((event.position().y() - 36) // 20)
        if 0 <= index < len(self.apps):
            os.startfile(self.apps[index]["path"])

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(16, 16, 20, 190))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)
        painter.setPen(QColor("#f4f4f5"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        painter.drawText(16, 24, "Start")
        painter.setFont(QFont("Segoe UI", 11))
        if not self.apps:
            painter.setPen(QColor("#a1a1aa"))
            painter.drawText(16, 56, self.width() - 24, 30, Qt.AlignmentFlag.AlignLeft, "No matching shortcuts.")
            painter.end()
            return
        for index, app in enumerate(self.apps):
            painter.setPen(QColor("#e4e4e7"))
            painter.drawText(16, 48 + index * 20, self.width() - 24, 18, Qt.AlignmentFlag.AlignLeft, app["name"])
        painter.end()
