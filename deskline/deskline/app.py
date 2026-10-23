"""Deskline window and pages."""

from __future__ import annotations

import os

from PySide6.QtCore import QEvent, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from deskline import retro, services, tweaks, wallpaper_prep, winutil
from deskline.config import Config
from deskline.overlays import CursorPreview, TaskbarPreview
from deskline.runtime import IMAGE_EXT, Runtime
from deskline.ui import STYLESHEET, AccentMark, Card, ChoiceRow, LabeledSlider, Switch, header, muted, page_heading, title_label


class Worker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.succeeded.emit(self._fn())
        except Exception as exc:
            self.failed.emit(str(exc))


class PageScroll(QWidget):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.setObjectName("page")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head = QWidget()
        head.setObjectName("pageHead")
        head_layout = QVBoxLayout(head)
        head_layout.setContentsMargins(32, 22, 32, 6)
        head_layout.setSpacing(4)
        head_layout.addLayout(page_heading(title, subtitle))
        root.addWidget(head)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("pageScroll")
        self.scroll.setWidgetResizable(False)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.content = QWidget()
        self.content.setObjectName("pageBody")
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(32, 10, 22, 28)
        self.body.setSpacing(14)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)
        self.scroll.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._fit()
        return super().eventFilter(watched, event)

    def _fit(self) -> None:
        if getattr(self, "_fitting", False):
            return
        width = self.scroll.viewport().width()
        if width < 40:
            return
        self._fitting = True
        try:
            from deskline.ui import ChoiceRow
            self.content.setFixedWidth(width)
            inner = max(40, width - self.body.contentsMargins().left() - self.body.contentsMargins().right() - 32)
            for choice in self.content.findChildren(ChoiceRow):
                choice.apply_width(inner)
            self.body.activate()
            height = self.body.sizeHint().height()
            self.content.setFixedHeight(max(1, height))
        finally:
            self._fitting = False

    def finish(self) -> None:
        self.body.addStretch(1)
        self._fit()


def _button(text: str, role: str = "") -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if role:
        button.setProperty("role", role)
    return button


def _off(value: int) -> str:
    return "Off" if value <= 0 else str(value)


class Shell(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Deskline")
        self.resize(1180, 780)
        self.config = Config()
        self.runtime = Runtime(self.config)
        root = QWidget()
        root.setObjectName("shell")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QVBoxLayout()
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(228)
        side.setLayout(sidebar)
        sidebar.setContentsMargins(14, 18, 10, 16)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        brand_row.addWidget(AccentMark(), 0, Qt.AlignmentFlag.AlignVCenter)
        brand_row.addWidget(title_label("Deskline", "brand"), 1)
        brand_host = QWidget()
        brand_host.setLayout(brand_row)
        sidebar.addWidget(brand_host)
        sidebar.addWidget(muted("Desktop studio"))
        self.stack = QStackedWidget()
        self.nav_buttons = []
        self.page_names = []
        built = {
            "Home": HomePage(self),
            "PC Check": PcCheckPage(self),
            "Wallpaper": WallpaperPage(self),
            "Taskbar": TaskbarPage(self),
            "Cursor": CursorPage(self),
            "Widgets": WidgetsPage(self),
            "Windows": WindowsPage(self),
            "Retro": RetroPage(self),
            "Audio": AudioPage(self),
            "Network": NetworkPage(self),
            "Drivers": DriversPage(self),
            "Cleanup": CleanupPage(self),
            "Game Boost": GamePage(self),
            "Tools": ToolsPage(self),
        }
        groups = [
            ("Desktop", ["Home", "Wallpaper", "Taskbar", "Cursor", "Widgets"]),
            ("Windows", ["Windows", "Retro", "Audio"]),
            ("PC", ["PC Check", "Network", "Drivers", "Cleanup", "Game Boost", "Tools"]),
        ]
        nav_host = QWidget()
        nav_host.setObjectName("navHost")
        nav_layout = QVBoxLayout(nav_host)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(2)
        for group, names in groups:
            label = QLabel(group.upper())
            label.setObjectName("navGroup")
            nav_layout.addWidget(label)
            for name in names:
                index = len(self.page_names)
                button = _button(name, "nav")
                button.setCheckable(True)
                button.clicked.connect(lambda _checked=False, item=index: self.show_page(item))
                nav_layout.addWidget(button)
                self.nav_buttons.append(button)
                self.page_names.append(name)
                self.stack.addWidget(built[name])
        nav_layout.addStretch(1)
        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setWidget(nav_host)
        sidebar.addWidget(nav_scroll, 1)
        layout.addWidget(side)
        layout.addWidget(self.stack, 1)
        self.show_page(0)

    def showEvent(self, event):
        super().showEvent(event)
        self.runtime.attach_window(int(self.winId()))

    def show_named(self, name: str) -> None:
        if name in self.page_names:
            self.show_page(self.page_names.index(name))

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)

    def closeEvent(self, event):
        self.runtime.shutdown()
        for thread in self.findChildren(QThread):
            if thread.isRunning():
                thread.wait(8000)
        event.accept()

    def nativeEvent(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            from deskline.winutil import WM_HOTKEY, _MSG
            try:
                msg = _MSG.from_address(int(message))
            except (TypeError, ValueError):
                msg = None
            if msg is not None and msg.message == WM_HOTKEY:
                self.runtime.toggle_topmost()
                return True, 0
        return super().nativeEvent(event_type, message)


class HomePage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("Deskline", "Live wallpaper, cursor, taskbar, widgets, and a few honest PC tools.")
        self.shell = shell
        card = Card()
        self.status = muted("Loading status…")
        card.add(self.status)
        row = QHBoxLayout()
        for label in ("Wallpaper", "Cursor", "Cleanup", "Game Boost"):
            button = _button(label, "primary" if label == "Wallpaper" else "")
            button.clicked.connect(lambda _checked=False, name=label: shell.show_named(name))
            row.addWidget(button)
        row.addStretch(1)
        holder = QWidget()
        holder.setLayout(row)
        card.add(holder)
        self.body.addWidget(card)
        note = Card()
        note.add(title_label("What this changes"))
        note.add(muted(
            "Nothing runs until you turn it on. Wallpaper sits behind the desktop icons. "
            "Cleanup only removes the categories you select, and it asks before emptying the Recycle Bin. "
            "Game Boost switches the Windows power plan while a fullscreen app is open, then puts the old plan back."
        ))
        self.body.addWidget(note)
        self.finish()
        timer = QTimer(self)
        timer.timeout.connect(self._refresh)
        timer.start(1000)
        self._refresh()

    def _refresh(self) -> None:
        config = self.shell.config
        wallpaper = "on" if config.section("wallpaper").get("enabled") else "off"
        cursor = "on" if config.section("cursor").get("enabled") else "off"
        taskbar = "on" if config.section("taskbar").get("enabled") else "off"
        game = self.shell.runtime.game_status()
        self.status.setText(f"Wallpaper {wallpaper}  ·  Cursor {cursor}  ·  Taskbar {taskbar}\n{game}")


class PcCheckPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("PC Check", "A short sample of this PC. Run it before and after a change to see what moved.")
        self.shell = shell
        top = QHBoxLayout()
        self.run_button = _button("RUN CHECK", "primary")
        self.run_button.clicked.connect(self._run)
        top.addStretch(1)
        top.addWidget(self.run_button)
        holder = QWidget()
        holder.setLayout(top)
        self.body.addWidget(holder)
        stats = QHBoxLayout()
        self.cpu1 = self._stat("CPU · ONE CORE")
        self.cpu_all = self._stat("CPU · ALL CORES")
        self.memory = self._stat("MEMORY")
        self.drive = self._stat("DRIVE")
        for card in (self.cpu1, self.cpu_all, self.memory, self.drive):
            stats.addWidget(card[0])
        stats_holder = QWidget()
        stats_holder.setLayout(stats)
        self.body.addWidget(stats_holder)
        columns = QHBoxLayout()
        self.facts = Card()
        self.facts_label = muted("Reading this PC…")
        self.facts.add(title_label("Your PC"))
        self.facts.add(self.facts_label)
        self.slow = Card()
        self.slow_label = muted("Run a check to see which apps are using the machine.")
        self.slow.add(title_label("What slows it down"))
        self.slow.add(self.slow_label)
        columns.addWidget(self.facts, 1)
        columns.addWidget(self.slow, 1)
        columns_holder = QWidget()
        columns_holder.setLayout(columns)
        self.body.addWidget(columns_holder)
        history_card = Card()
        history_header = QHBoxLayout()
        history_header.addWidget(title_label("Previous checks"))
        history_header.addStretch(1)
        clear = _button("Clear")
        clear.clicked.connect(self._clear)
        history_header.addWidget(clear)
        header_widget = QWidget()
        header_widget.setLayout(history_header)
        history_card.add(header_widget)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["When", "CPU 1", "CPU all", "Memory", "Read", "Write"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        history_card.add(self.table)
        self.body.addWidget(history_card)
        self.finish()
        self._facts = {}
        self._load_facts()
        self._show_history()

    def _stat(self, caption: str):
        card = Card()
        card.add(muted(caption))
        value = title_label("—", "stat")
        card.add(value)
        detail = muted("")
        card.add(detail)
        return card, value, detail

    def _load_facts(self) -> None:
        self._worker = Worker(self._collect, self)
        self._worker.succeeded.connect(self._show_facts)
        self._worker.start()

    @staticmethod
    def _collect() -> dict:
        facts = services.machine_facts()
        facts.update(services.hardware_names())
        return facts

    def _show_facts(self, facts: dict) -> None:
        self._facts = facts
        self.facts_label.setText(
            f"{facts['cpu']}\n"
            f"{facts['cores']} cores / {facts['threads']} threads\n"
            f"{services.format_bytes(facts['memory_total'])} memory ({facts['memory_percent']:.0f}% in use)\n"
            f"{facts['gpu']}\n"
            f"Drive C: {services.format_bytes(facts['disk_free'])} free of {services.format_bytes(facts['disk_total'])}\n"
            f"{facts['os']}\n"
            f"Running for {services.format_duration(facts['uptime'])} · Power plan: {facts['power']}"
        )
        startup = facts.get("startup") or []
        self.slow_label.setText(
            f"{len(startup)} apps start with Windows.\n"
            + ("\n".join(startup[:8]) if startup else "No startup entries were found in the usual places.")
        )

    def _run(self) -> None:
        self.run_button.setEnabled(False)
        self.run_button.setText("MEASURING…")
        self._bench = Worker(services.run_benchmark, self)
        self._bench.succeeded.connect(self._show_result)
        self._bench.failed.connect(self._bench_failed)
        self._bench.start()

    def _bench_failed(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.run_button.setText("RUN CHECK")
        self.slow_label.setText(message)

    def _show_result(self, result: dict) -> None:
        self.run_button.setEnabled(True)
        self.run_button.setText("RUN CHECK")
        previous = (self.shell.config.data.get("checks") or [None])[0]
        self._set_stat(self.cpu1, f"{result['cpu1']}", "MB/s", _delta(result["cpu1"], None if not previous else previous.get("cpu1")))
        self._set_stat(self.cpu_all, f"{result['cpu_all']}", "MB/s", _delta(result["cpu_all"], None if not previous else previous.get("cpu_all")))
        self._set_stat(self.memory, f"{result['memory']}", "GB/s", _delta(result["memory"], None if not previous else previous.get("memory")))
        self._set_stat(self.drive, f"{result['read']}", "MB/s read", _delta(result["read"], None if not previous else previous.get("read")))
        lines = []
        memory_pct = self._facts.get("memory_percent")
        if memory_pct is not None:
            lines.append("Enough free memory." if memory_pct < 85 else f"Memory is {memory_pct:.0f}% full.")
        free_pct = 100 - float(self._facts.get("disk_percent") or 0)
        lines.append("Drive C: has plenty of free space." if free_pct > 15 else "Drive C: is getting full.")
        startup = self._facts.get("startup") or []
        lines.append(f"{len(startup)} apps start with Windows.")
        for item in result.get("busiest") or []:
            lines.append(f"{item['name']} · CPU {item['cpu']}% · {services.format_bytes(item['memory'])}")
        self.slow_label.setText("\n".join(lines))
        entry = {key: result[key] for key in ("at", "cpu1", "cpu_all", "memory", "read", "write")}
        checks = [entry, *(self.shell.config.data.get("checks") or [])]
        self.shell.config.data["checks"] = checks[:8]
        self.shell.config.save()
        self._show_history()

    def _set_stat(self, stat, value: str, unit: str, detail: str) -> None:
        stat[1].setText(f"{value}")
        stat[2].setText(f"{unit} · {detail}")

    def _show_history(self) -> None:
        checks = self.shell.config.data.get("checks") or []
        self.table.setRowCount(len(checks))
        for row, item in enumerate(checks):
            values = [item.get("at"), item.get("cpu1"), item.get("cpu_all"), item.get("memory"), item.get("read"), item.get("write")]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))

    def _clear(self) -> None:
        self.shell.config.data["checks"] = []
        self.shell.config.save()
        self._show_history()


def _delta(new, old) -> str:
    if old in (None, 0):
        return "first check"
    pct = (float(new) - float(old)) / float(old) * 100
    if abs(pct) < 4:
        return "same as last time"
    word = "faster" if pct > 0 else "slower"
    return f"{abs(pct):.0f}% {word}"


class WallpaperPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__(
            "Wallpaper",
            "Import a video and Deskline builds a seamless loop, a screen-sized copy, a lighter 1080p copy, and a preview.",
        )
        self.shell = shell
        section = shell.config.section("wallpaper")
        self.enabled = Switch(bool(section.get("enabled")))
        self.enabled.toggled.connect(lambda on: self._save(enabled=on))
        card = Card()
        card.add(header("Play on the desktop", "The processed video sits behind the icons. A still image replaces the Windows wallpaper.", self.enabled))
        self.gallery_host = QWidget()
        self.gallery_layout = QHBoxLayout(self.gallery_host)
        self.gallery_layout.setContentsMargins(0, 0, 0, 0)
        gallery_scroll = QScrollArea()
        gallery_scroll.setWidgetResizable(True)
        gallery_scroll.setFixedHeight(150)
        gallery_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        gallery_scroll.setWidget(self.gallery_host)
        card.add(gallery_scroll)
        actions = QHBoxLayout()
        import_button = _button("Import", "primary")
        import_button.clicked.connect(self._import)
        remove_button = _button("Remove")
        remove_button.clicked.connect(self._remove)
        actions.addWidget(import_button)
        actions.addWidget(remove_button)
        actions.addStretch(1)
        actions_host = QWidget()
        actions_host.setLayout(actions)
        card.add(actions_host)
        self.progress = muted("")
        card.add(self.progress)
        self.slideshow = Switch(bool(section.get("slideshow")))
        self.slideshow.toggled.connect(lambda on: self._save(slideshow=on))
        card.add(header("Slideshow", "Plays every processed video in the library, then starts again.", self.slideshow))
        self.interval = ChoiceRow([("1", "1 min"), ("5", "5 min"), ("10", "10 min"), ("30", "30 min")], str(int(section.get("slideshow_minutes") or 10)))
        self.interval.changed.connect(lambda value: self._save(slideshow_minutes=int(value)))
        card.add(self.interval)
        self.muted_audio = Switch(bool(section.get("muted", True)))
        self.muted_audio.toggled.connect(lambda on: self._save(muted=on))
        card.add(header("Mute", "On keeps the wallpaper silent.", self.muted_audio))
        self.hide_icons = Switch(bool(section.get("hide_icons")))
        self.hide_icons.toggled.connect(self._icons)
        card.add(header("Desktop icons", "Hides or shows the icons. Nothing is deleted.", self.hide_icons))
        self.body.addWidget(card)
        sources = Card()
        sources.add(title_label("Source"))
        self.source = ChoiceRow(
            [("media", "Video"), ("web", "Web page"), ("shader", "Pattern")],
            str(section.get("source") or "media"),
        )
        self.source.changed.connect(lambda value: self._save(source=value))
        sources.add(self.source)
        self.url = QLineEdit(str(section.get("url") or ""))
        self.url.setPlaceholderText("https://")
        self.url.editingFinished.connect(lambda: self._save(url=self.url.text().strip(), source="web", enabled=True))
        sources.add(self.url)
        self.shader = ChoiceRow(
            [("plasma", "Plasma"), ("waves", "Waves"), ("grid", "Grid"), ("bars", "Bars")],
            str(section.get("shader") or "plasma"),
        )
        self.shader.changed.connect(lambda value: self._save(shader=value, source="shader", enabled=True))
        sources.add(self.shader)
        self.span = Switch(bool(section.get("all_monitors")))
        self.span.toggled.connect(lambda on: self._save(all_monitors=on))
        sources.add(header("Span monitors", "One wallpaper covers the whole desktop, including a second screen.", self.span))
        self.battery = Switch(bool(section.get("pause_battery")))
        self.battery.toggled.connect(lambda on: self._save(pause_battery=on))
        sources.add(header("Pause on battery", "The video or pattern stops while the laptop is unplugged.", self.battery))
        self.pause_apps = QLineEdit(str(section.get("pause_apps") or ""))
        self.pause_apps.setPlaceholderText("game.exe, another.exe")
        self.pause_apps.editingFinished.connect(lambda: self._save(pause_apps=self.pause_apps.text().strip()))
        sources.add(muted("Pause while these programs are in front. Separate names with commas."))
        sources.add(self.pause_apps)
        self.idle = Switch(bool(section.get("idle_screensaver")))
        self.idle.toggled.connect(lambda on: self._save(idle_screensaver=on))
        sources.add(header("Idle screensaver", "After you stop using the PC, the wallpaper covers the screen until the next input.", self.idle))
        self.idle_minutes = LabeledSlider("Idle minutes", 1, 30, int(section.get("idle_minutes") or 5), lambda value: f"{value} min")
        self.idle_minutes.changed.connect(lambda value: self._save(idle_minutes=value))
        sources.add(self.idle_minutes)
        self.body.addWidget(sources)
        adjust = Card()
        adjust.add(title_label("Adjust"))
        adjust.add(muted("Blur, brightness, and overlays are drawn on the video. Brightness only darkens."))
        self.blur = LabeledSlider("Blur", 0, 100, int(section.get("blur") or 0), _off)
        self.brightness = LabeledSlider("Brightness", -100, 0, int(section.get("brightness") or 0))
        self.blur.changed.connect(lambda value: self._save(blur=value))
        self.brightness.changed.connect(lambda value: self._save(brightness=value))
        adjust.add(self.blur)
        adjust.add(self.brightness)
        adjust.add(muted("Overlay"))
        self.overlay = ChoiceRow(
            [
                ("none", "None"), ("dust", "Dust"), ("snow", "Snow"), ("stars", "Stars"),
                ("embers", "Embers"), ("mist", "Mist"), ("rain", "Rain"), ("sparks", "Sparks"), ("fog", "Fog"),
            ],
            str(section.get("overlay") or "none"),
        )
        self.overlay.changed.connect(lambda value: self._save(overlay=value))
        adjust.add(self.overlay)
        self.overlay_amount = LabeledSlider("Amount", 0, 100, int(section.get("overlay_amount") or 50))
        self.overlay_amount.changed.connect(lambda value: self._save(overlay_amount=value))
        adjust.add(self.overlay_amount)
        tint = QHBoxLayout()
        for hex_color, label in (("#ffffff", "Own color"), ("#ff3b5c", "Red"), ("#38bdf8", "Blue"), ("#f8fafc", "White")):
            button = _button(label)
            button.clicked.connect(lambda _checked=False, color=hex_color: self._save(overlay_color=color))
            tint.addWidget(button)
        tint.addStretch(1)
        tint_host = QWidget()
        tint_host.setLayout(tint)
        adjust.add(muted("Tint. Own color keeps each effect's colors."))
        adjust.add(tint_host)
        self.status = muted("Wallpaper is off.")
        adjust.add(self.status)
        self.body.addWidget(adjust)
        self.finish()
        self._rebuild_gallery()
        timer = QTimer(self)
        timer.timeout.connect(lambda: self.status.setText(shell.runtime.wallpaper_status()) if not self.progress.text().endswith("%") else None)
        timer.start(1000)

    def _rebuild_gallery(self) -> None:
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        active = str(self.shell.config.section("wallpaper").get("active_id") or "")
        items = wallpaper_prep.list_library()
        if not items:
            self.gallery_layout.addWidget(muted("No wallpapers yet."))
            return
        for entry in items:
            button = QPushButton(str(entry.get("name") or "Wallpaper"))
            button.setCheckable(True)
            button.setChecked(str(entry.get("id")) == active)
            preview = str(entry.get("preview") or "")
            if os.path.isfile(preview):
                button.setIcon(QIcon(QPixmap(preview)))
                button.setIconSize(QPixmap(120, 68).size())
            button.setMinimumHeight(110)
            button.setMinimumWidth(140)
            button.clicked.connect(lambda _checked=False, item=entry: self._select(item))
            self.gallery_layout.addWidget(button)
        self.gallery_layout.addStretch(1)

    def _select(self, entry: dict) -> None:
        kind, path = wallpaper_prep.media_for(entry, wallpaper_prep.screen_pixels()[1])
        self._save(active_id=entry.get("id"), path=path, enabled=True)
        self.enabled.setChecked(True, emit=False)
        self._rebuild_gallery()

    def _import(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Import wallpaper", "",
            "Media (*.mp4 *.webm *.mkv *.mov *.avi *.wmv *.m4v *.gif *.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path:
            return
        self.progress.setText("Starting…")
        self._prep = PrepThread(path, self)
        self._prep.progress.connect(self.progress.setText)
        self._prep.succeeded.connect(self._imported)
        self._prep.failed.connect(self.progress.setText)
        self._prep.start()

    def _imported(self, entry: dict) -> None:
        self.progress.setText(
            f"Ready · {entry.get('width')}×{entry.get('height')}"
            + (" · ping-pong loop" if entry.get("ping_pong") else "")
            + (" · 1080p copy" if entry.get("has_1080") else "")
        )
        self._select(entry)

    def _remove(self) -> None:
        active = str(self.shell.config.section("wallpaper").get("active_id") or "")
        if not active:
            return
        wallpaper_prep.delete_entry(active)
        self._save(active_id="", path="", enabled=False)
        self.enabled.setChecked(False, emit=False)
        self._rebuild_gallery()

    def _save(self, **values) -> None:
        self.shell.runtime.note_user_edit()
        self.shell.config.update_section("wallpaper", **values)
        self.shell.runtime.apply()

    def _icons(self, _on: bool) -> None:
        winutil.toggle_desktop_icons()
        self.shell.config.update_section("wallpaper", hide_icons=self.hide_icons.isChecked())


class PrepThread(QThread):
    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self) -> None:
        try:
            self.succeeded.emit(wallpaper_prep.prepare(self._path, self.progress.emit))
        except Exception as exc:
            self.failed.emit(str(exc))


class TaskbarPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("Taskbar", "An animated strip behind the taskbar. Windows 11 may ignore a request to make the bar clear.")
        self.shell = shell
        section = shell.config.section("taskbar")
        self.enabled = Switch(bool(section.get("enabled")))
        self.enabled.toggled.connect(lambda on: self._save(enabled=on))
        card = Card()
        card.add(header("Animated taskbar", "Drawn behind the real taskbar. Clicks still land on Windows.", self.enabled))
        self.clear = Switch(bool(section.get("clear", True)))
        self.clear.toggled.connect(lambda on: self._save(clear=on))
        card.add(header("Clear taskbar", "Asks Windows to draw the bar transparent so the animation can show through.", self.clear))
        self.preview = TaskbarPreview()
        self.preview.set_settings(section)
        card.add(self.preview)
        card.add(muted("Design"))
        self.design = ChoiceRow(
            [("wave", "Wave"), ("pulse", "Pulse"), ("aurora", "Aurora"), ("ember", "Ember"), ("glass", "Glass"), ("gif", "GIF")],
            str(section.get("design") or "wave"),
        )
        self.design.changed.connect(lambda value: self._save(design=value))
        card.add(self.design)
        gif_button = _button("Import GIF")
        gif_button.clicked.connect(self._gif)
        card.add(gif_button)
        self.height = LabeledSlider("Height", 20, 100, int(section.get("height") or 100), lambda value: f"{value}%")
        self.gap = LabeledSlider("Side gap", 0, 40, int(section.get("side_gap") or 0), lambda value: f"{value}%")
        self.corners = LabeledSlider("Corners", 0, 100, int(section.get("corners") or 0), _off)
        self.brightness = LabeledSlider("Brightness", -100, 0, int(section.get("brightness") or 0))
        for slider, key in ((self.height, "height"), (self.gap, "side_gap"), (self.corners, "corners"), (self.brightness, "brightness")):
            slider.changed.connect(lambda value, name=key: self._save(**{name: value}))
            card.add(slider)
        self.bar = Switch(bool(section.get("show_bar")))
        self.bar.toggled.connect(lambda on: self._save(show_bar=on))
        card.add(header("Center bar", "Cover paints the middle. Invert paints the sides and leaves the middle open.", self.bar))
        self.bar_mode = ChoiceRow([("cover", "Cover"), ("invert", "Invert")], str(section.get("bar_mode") or "cover"))
        self.bar_color = ChoiceRow([("black", "Black"), ("white", "White")], str(section.get("bar_color") or "black"))
        self.bar_mode.changed.connect(lambda value: self._save(bar_mode=value))
        self.bar_color.changed.connect(lambda value: self._save(bar_color=value))
        card.add(self.bar_mode)
        card.add(self.bar_color)
        self.bar_width = LabeledSlider("Bar width", 5, 100, int(section.get("bar_width") or 40), lambda value: f"{value}%")
        self.bar_height = LabeledSlider("Bar height", 10, 100, int(section.get("bar_height") or 100), lambda value: f"{value}%")
        self.bar_radius = LabeledSlider("Bar corners", 0, 100, int(section.get("bar_radius") or 0), _off)
        self.bar_opacity = LabeledSlider("Bar opacity", 0, 100, int(section.get("bar_opacity") or 55), lambda value: f"{value}%")
        for slider, key in (
            (self.bar_width, "bar_width"), (self.bar_height, "bar_height"),
            (self.bar_radius, "bar_radius"), (self.bar_opacity, "bar_opacity"),
        ):
            slider.changed.connect(lambda value, name=key: self._save(**{name: value}))
            card.add(slider)
        self.body.addWidget(card)
        style = Card()
        style.add(title_label("Windows taskbar"))
        style.add(muted("Clear, blur, and acrylic are requests. Windows 11 often keeps its own taskbar material."))
        self.accent = ChoiceRow(
            [("clear", "Clear"), ("blur", "Blur"), ("acrylic", "Acrylic"), ("opaque", "Opaque")],
            str(section.get("accent") or "clear"),
        )
        self.accent.changed.connect(lambda value: self._save(accent=value, clear=True))
        style.add(self.accent)
        self.dynamic = ChoiceRow(
            [("same", "Same"), ("normal", "Normal"), ("clear", "Clear"), ("blur", "Blur"), ("acrylic", "Acrylic")],
            str(section.get("dynamic_maximized") or "same"),
        )
        self.dynamic.changed.connect(lambda value: self._save(dynamic_maximized=value))
        style.add(muted("When a window is maximized"))
        style.add(self.dynamic)
        tint = QHBoxLayout()
        for hex_color, label in (("#000000", "Black"), ("#ffffff", "White"), ("#ff3b5c", "Red")):
            button = _button(label)
            button.clicked.connect(lambda _checked=False, color=hex_color: self._save(accent_color=color))
            tint.addWidget(button)
        tint.addStretch(1)
        tint_host = QWidget()
        tint_host.setLayout(tint)
        style.add(tint_host)
        self.accent_opacity = LabeledSlider("Tint", 0, 100, int(section.get("accent_opacity") or 40), lambda value: f"{value}%")
        self.accent_opacity.changed.connect(lambda value: self._save(accent_opacity=value))
        style.add(self.accent_opacity)
        self.shape_margin = LabeledSlider("Edge margin", 0, 40, int(section.get("shape_margin") or 0), lambda value: f"{value}px")
        self.shape_radius = LabeledSlider("Real corners", 0, 24, int(section.get("shape_radius") or 0), lambda value: f"{value}px")
        self.shape_margin.changed.connect(lambda value: self._save(shape_margin=value))
        self.shape_radius.changed.connect(lambda value: self._save(shape_radius=value))
        style.add(self.shape_margin)
        style.add(self.shape_radius)
        self.dock = Switch(bool(section.get("dock")))
        self.dock.toggled.connect(lambda on: self._save(dock=on))
        style.add(header("Dock", "Narrows the real taskbar and centers it. Quitting Deskline puts the width back.", self.dock))
        self.dock_width = LabeledSlider("Dock width", 20, 100, int(section.get("dock_width") or 60), lambda value: f"{value}%")
        self.dock_width.changed.connect(lambda value: self._save(dock_width=value))
        style.add(self.dock_width)
        self.body.addWidget(style)
        behavior = Card()
        self.scroll_volume = Switch(bool(section.get("scroll_volume")))
        self.scroll_volume.toggled.connect(lambda on: self._save(scroll_volume=on))
        behavior.add(header("Scroll for volume", "Turn the wheel over the taskbar. The clock area is left to Windows.", self.scroll_volume))
        self.notch = ChoiceRow([("1", "1%"), ("2", "2%"), ("5", "5%"), ("10", "10%")], str(int(section.get("scroll_percent") or 2)))
        self.notch.changed.connect(lambda value: self._save(scroll_percent=int(value)))
        behavior.add(self.notch)
        self.hide_max = Switch(bool(section.get("hide_maximized")))
        self.hide_max.toggled.connect(lambda on: self._save(hide_maximized=on))
        behavior.add(header("Hide when maximized", "The taskbar auto-hides while a window is maximized or covers the screen. Move the pointer to the edge to see it. Quitting Deskline puts the old behavior back.", self.hide_max))
        self.body.addWidget(behavior)
        self.finish()

    def _save(self, **values) -> None:
        self.shell.config.update_section("taskbar", **values)
        section = self.shell.config.section("taskbar")
        self.preview.set_settings(section)
        self.shell.runtime.apply()

    def _gif(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Taskbar GIF", "", "GIF (*.gif)")
        if path:
            self._save(design="gif", gif=path)
            self.design.setValue("gif")


class CursorPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("Cursor", "A click-through trail that follows the pointer. Turn it off here if you want the normal cursor only.")
        self.shell = shell
        section = shell.config.section("cursor")
        self.enabled = Switch(bool(section.get("enabled")))
        self.enabled.toggled.connect(lambda on: self._save(enabled=on))
        card = Card()
        card.add(header("Enable effects", "The overlay ignores clicks, so buttons underneath still work.", self.enabled))
        self.preview = CursorPreview()
        self.preview.set_settings(section)
        card.add(self.preview)
        self.body.addWidget(card)
        settings = Card()
        settings.add(title_label("Settings"))
        settings.add(muted("Color"))
        row = QHBoxLayout()
        for hex_color, label in (("#ff3b5c", "Red"), ("#38bdf8", "Blue"), ("#f8fafc", "White"), ("#a3e635", "Lime")):
            button = _button(label)
            button.clicked.connect(lambda _checked=False, color=hex_color: self._save(color=color))
            row.addWidget(button)
        custom = _button("Custom")
        custom.clicked.connect(self._custom_color)
        row.addWidget(custom)
        row.addStretch(1)
        holder = QWidget()
        holder.setLayout(row)
        settings.add(holder)
        self.mode = ChoiceRow([("single", "Single"), ("gradient", "Gradient"), ("rainbow", "Rainbow")], section.get("mode", "single"))
        self.move = ChoiceRow(
            [("none", "None"), ("classic", "Classic"), ("glow", "Glow"), ("sparks", "Sparks"), ("stardust", "Stardust")],
            section.get("move", "classic"),
        )
        self.left = ChoiceRow(
            [("none", "None"), ("shockwave", "Shockwave"), ("burst", "Burst"), ("ripple", "Ripple")],
            section.get("left_click", "shockwave"),
        )
        self.right = ChoiceRow(
            [("same", "Same"), ("none", "None"), ("shockwave", "Shockwave"), ("burst", "Burst"), ("ripple", "Ripple")],
            section.get("right_click", "same"),
        )
        settings.add(muted("Pointer"))
        self.pointer = ChoiceRow(
            [("system", "System"), ("ring", "Ring"), ("cross", "Cross"), ("dot", "Dot"), ("arrow", "Arrow"), ("gif", "GIF")],
            str(section.get("pointer") or "system"),
        )
        self.pointer.changed.connect(lambda value: self._save(pointer=value))
        settings.add(self.pointer)
        pointer_gif = _button("Import pointer GIF")
        pointer_gif.clicked.connect(self._pointer_gif)
        settings.add(pointer_gif)
        settings.add(muted("The pointer styles replace the arrow and are put back when you quit or choose System. Trails stay on the overlay."))
        settings.add(muted("Color style"))
        settings.add(self.mode)
        settings.add(muted("Move"))
        settings.add(self.move)
        settings.add(muted("Left click"))
        settings.add(self.left)
        settings.add(muted("Right click"))
        settings.add(self.right)
        self.mode.changed.connect(lambda value: self._save(mode=value))
        self.move.changed.connect(lambda value: self._save(move=value))
        self.left.changed.connect(lambda value: self._save(left_click=value))
        self.right.changed.connect(lambda value: self._save(right_click=value))
        self.amount = LabeledSlider("Amount", 0, 100, int(section.get("amount") or 50))
        self.size = LabeledSlider("Size", 0, 100, int(section.get("size") or 50))
        self.length = LabeledSlider("Length", 0, 100, int(section.get("length") or 50))
        self.glow = LabeledSlider("Glow", 0, 100, int(section.get("glow") or 55))
        self.spread = LabeledSlider("Spread", 0, 100, int(section.get("spread") or 50))
        for slider, key in (
            (self.amount, "amount"), (self.size, "size"), (self.length, "length"),
            (self.glow, "glow"), (self.spread, "spread"),
        ):
            slider.changed.connect(lambda value, name=key: self._save(**{name: value}))
            settings.add(slider)
        self.body.addWidget(settings)
        self.finish()

    def _save(self, **values) -> None:
        self.shell.config.update_section("cursor", **values)
        section = self.shell.config.section("cursor")
        self.preview.set_settings(section)
        self.shell.runtime.apply()

    def _pointer_gif(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Pointer GIF", "", "Image (*.gif *.png *.webp)")
        if path:
            self._save(pointer="gif", pointer_gif=path)
            self.pointer.setValue("gif")

    def _custom_color(self) -> None:
        current = QColor(self.shell.config.section("cursor").get("color") or "#ff3b5c")
        chosen = QColorDialog.getColor(current, self, "Cursor color")
        if chosen.isValid():
            self._save(color=chosen.name())


class WidgetsPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("Widgets", "Clock, meters, notes, now playing, games, and a start list. Drag them while they are unlocked.")
        self.shell = shell
        section = shell.config.section("widgets")
        self.clock = Switch(bool(section.get("clock")))
        self.monitor = Switch(bool(section.get("monitor")))
        self.music = Switch(bool(section.get("music")))
        self.games = Switch(bool(section.get("games")))
        self.disk = Switch(bool(section.get("disk")))
        self.net = Switch(bool(section.get("net")))
        self.notes = Switch(bool(section.get("notes")))
        self.launch = Switch(bool(section.get("launch")))
        self.locked = Switch(bool(section.get("locked")))
        self.clock.toggled.connect(lambda on: self._save(clock=on))
        self.monitor.toggled.connect(lambda on: self._save(monitor=on))
        self.music.toggled.connect(lambda on: self._save(music=on))
        self.games.toggled.connect(lambda on: self._save(games=on))
        self.disk.toggled.connect(lambda on: self._save(disk=on))
        self.net.toggled.connect(lambda on: self._save(net=on))
        self.notes.toggled.connect(lambda on: self._save(notes=on))
        self.launch.toggled.connect(lambda on: self._save(launch=on))
        self.locked.toggled.connect(lambda on: self._save(locked=on))
        card = Card()
        card.add(header("Clock", "Day, time, and date on the desktop.", self.clock))
        card.add(header("System monitor", "CPU and memory, updated once a second.", self.monitor))
        card.add(header("Music", "Title and artist from the Windows media session, when a player is active.", self.music))
        card.add(header("Game library", "Installed Steam games. Click a name while the widget is unlocked to launch it.", self.games))
        card.add(header("Disk", "How full C: is, and how much space is free.", self.disk))
        card.add(header("Network", "Download and upload for the last second.", self.net))
        card.add(header("Notes", "A small note you can type on the desktop.", self.notes))
        card.add(header("Start list", "Shortcuts from the Windows Start menu. The real Start menu stays as it is.", self.launch))
        self.launch_query = QLineEdit(str(section.get("launch_query") or ""))
        self.launch_query.setPlaceholderText("Filter shortcuts")
        self.launch_query.editingFinished.connect(lambda: self._save(launch_query=self.launch_query.text().strip()))
        card.add(self.launch_query)
        card.add(header("Lock", "Locked widgets ignore the mouse, so you can click through them.", self.locked))
        self.hour = Switch(bool(section.get("hour24", True)))
        self.seconds = Switch(bool(section.get("seconds", True)))
        self.weekday = Switch(bool(section.get("weekday", True)))
        self.upper = Switch(bool(section.get("uppercase", True)))
        self.date = Switch(bool(section.get("show_date", True)))
        for switch, key in (
            (self.hour, "hour24"), (self.seconds, "seconds"), (self.weekday, "weekday"),
            (self.upper, "uppercase"), (self.date, "show_date"),
        ):
            switch.toggled.connect(lambda on, name=key: self._save(**{name: on}))
        card.add(header("24-hour format", "Off uses a 12-hour clock.", self.hour))
        card.add(header("Seconds", "", self.seconds))
        card.add(header("Day of week", "", self.weekday))
        card.add(header("Uppercase day", "", self.upper))
        card.add(header("Date", "", self.date))
        self.body.addWidget(card)
        self.finish()

    def _save(self, **values) -> None:
        self.shell.config.update_section("widgets", **values)
        self.shell.runtime.apply()


class WindowsPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("Windows", "Appearance changes Deskline can put back. Some of them show up after Explorer restarts.")
        self.shell = shell
        section = shell.config.section("windows")
        accent = Card()
        self.sample = Switch(bool(section.get("accent_from_wallpaper")))
        self.sample.toggled.connect(self._sample_toggled)
        accent.add(header("Accent color from wallpaper", "Picks the strongest color in the wallpaper file.", self.sample))
        self.color_label = muted(f"Color {section.get('accent', '#ff3b5c')}")
        accent.add(self.color_label)
        pick = _button("Pick a color")
        pick.clicked.connect(self._pick)
        accent.add(pick)
        self.body.addWidget(accent)
        schedule = Card()
        self.schedule = Switch(bool(section.get("schedule")))
        self.schedule.toggled.connect(self._schedule)
        schedule.add(header("Light and dark by time of day", "Windows and apps follow the clock while this is on.", self.schedule))
        times = QHBoxLayout()
        self.light = QLineEdit(str(section.get("light_from") or "07:00"))
        self.dark = QLineEdit(str(section.get("dark_from") or "19:00"))
        self.light.setMaximumWidth(90)
        self.dark.setMaximumWidth(90)
        self.light.editingFinished.connect(self._times)
        self.dark.editingFinished.connect(self._times)
        times.addWidget(muted("Light from"))
        times.addWidget(self.light)
        times.addWidget(muted("Dark from"))
        times.addWidget(self.dark)
        times.addStretch(1)
        times_widget = QWidget()
        times_widget.setLayout(times)
        schedule.add(times_widget)
        self.body.addWidget(schedule)
        classic = Card()
        enabled = tweaks.classic_menu_enabled()
        self.classic = Switch(enabled)
        self.classic.toggled.connect(self._classic)
        classic.add(header("Classic right-click menu", "The full menu, instead of “Show more options”.", self.classic))
        restart = _button("Restart Explorer")
        restart.clicked.connect(self._restart)
        classic.add(muted("This shows up after Explorer restarts or you sign in again."))
        classic.add(restart)
        self.body.addWidget(classic)
        self.finish()

    def _pick(self) -> None:
        current = QColor(self.shell.config.section("windows").get("accent") or "#ff3b5c")
        chosen = QColorDialog.getColor(current, self, "Accent color")
        if chosen.isValid():
            self._set_accent(chosen.name())

    def _set_accent(self, color: str) -> None:
        tweaks.set_accent(color)
        self.shell.config.update_section("windows", accent=color)
        self.color_label.setText(f"Color {color}")

    def _sample_toggled(self, on: bool) -> None:
        self.shell.config.update_section("windows", accent_from_wallpaper=on)
        if on:
            self._sample_file()

    def _sample_file(self) -> None:
        path = str(self.shell.config.section("wallpaper").get("path") or "")
        if not path or not os.path.isfile(path):
            self.color_label.setText("Choose a wallpaper file first.")
            return
        if os.path.splitext(path)[1].lower() in IMAGE_EXT:
            self._use_image(QImage(path))
            return
        self._player = QMediaPlayer(self)
        self._sink = QVideoSink(self)
        self._player.setVideoOutput(self._sink)
        self._sink.videoFrameChanged.connect(self._on_frame)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    def _on_frame(self, frame) -> None:
        if not frame.isValid():
            return
        image = frame.toImage()
        self._player.stop()
        try:
            self._sink.videoFrameChanged.disconnect(self._on_frame)
        except (RuntimeError, TypeError):
            pass
        self._use_image(image)

    def _use_image(self, image: QImage) -> None:
        if image.isNull():
            self.color_label.setText("Could not read a color from that file.")
            return
        scaled = image.scaled(24, 24, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        best = QColor("#ff3b5c")
        best_score = -1
        for y in range(scaled.height()):
            for x in range(scaled.width()):
                color = scaled.pixelColor(x, y)
                score = color.hslSaturation()
                if score > best_score:
                    best_score = score
                    best = color
        self._set_accent(best.name())

    def _schedule(self, on: bool) -> None:
        if on:
            apps, system = tweaks.read_theme_light()
            self.shell.config.update_section("windows", schedule=True, saved_apps_light=apps, saved_system_light=system)
            self.shell.runtime._sync_theme()
            return
        section = self.shell.config.section("windows")
        tweaks.restore_theme(section.get("saved_apps_light"), section.get("saved_system_light"))
        self.shell.config.update_section("windows", schedule=False, saved_apps_light=None, saved_system_light=None)

    def _times(self) -> None:
        light = self.light.text().strip() or "07:00"
        dark = self.dark.text().strip() or "19:00"
        hour, minute = tweaks.parse_hhmm(light)
        light = f"{hour:02d}:{minute:02d}"
        hour, minute = tweaks.parse_hhmm(dark)
        dark = f"{hour:02d}:{minute:02d}"
        self.light.setText(light)
        self.dark.setText(dark)
        self.shell.config.update_section("windows", light_from=light, dark_from=dark)

    def _classic(self, on: bool) -> None:
        tweaks.set_classic_menu(on)
        self.shell.config.update_section("windows", classic_menu=on)

    def _restart(self) -> None:
        if QMessageBox.question(self, "Restart Explorer", "Open File Explorer windows will close.") != QMessageBox.StandardButton.Yes:
            return
        winutil.restart_explorer()


class CleanupPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("Cleanup", "Frees space without touching documents. Files that are in use are skipped.")
        self.shell = shell
        top = QHBoxLayout()
        self.summary = muted("Scanning…")
        self.clean_button = _button("CLEAN SELECTED", "primary")
        self.clean_button.clicked.connect(self._clean)
        top.addWidget(self.summary, 1)
        top.addWidget(self.clean_button)
        holder = QWidget()
        holder.setLayout(top)
        self.body.addWidget(holder)
        self.card = Card()
        self.body.addWidget(self.card)
        sense = _button("Storage Sense")
        sense.clicked.connect(lambda: winutil.open_settings("storagesense"))
        self.body.addWidget(sense)
        self.finish()
        self._categories = []
        self._switches: dict[str, Switch] = {}
        self._scan()

    def _scan(self) -> None:
        self._worker = Worker(services.scan_cleanup, self)
        self._worker.succeeded.connect(self._show)
        self._worker.failed.connect(lambda message: self.summary.setText(message))
        self._worker.start()

    def _show(self, categories: list) -> None:
        self._categories = categories
        while self.card.layout.count():
            item = self.card.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._switches.clear()
        selected = 0
        defaults = {"temp": True, "dumps": True, "reports": True, "thumbs": False, "recycle": False}
        for category in categories:
            switch = Switch(defaults.get(category["id"], False))
            switch.toggled.connect(lambda _on: self._update_summary())
            self._switches[category["id"]] = switch
            self.card.add(header(
                f"{category['title']} · {services.format_bytes(category['bytes'])}",
                category["detail"],
                switch,
            ))
            if switch.isChecked():
                selected += category["bytes"]
        self.summary.setText(f"Selected: {services.format_bytes(selected)}")

    def _update_summary(self) -> None:
        total = 0
        for category in self._categories:
            if self._switches[category["id"]].isChecked():
                total += category["bytes"]
        self.summary.setText(f"Selected: {services.format_bytes(total)}")

    def _clean(self) -> None:
        chosen = [item for item in self._categories if self._switches[item["id"]].isChecked() and item["bytes"] > 0]
        if not chosen:
            self.summary.setText("Nothing selected.")
            return
        if any(item.get("recycle") for item in chosen):
            answer = QMessageBox.question(self, "Recycle Bin", "Empty the Recycle Bin? This cannot be undone.")
            if answer != QMessageBox.StandardButton.Yes:
                chosen = [item for item in chosen if not item.get("recycle")]
        if not chosen:
            return
        self.clean_button.setEnabled(False)
        self._cleaner = Worker(lambda: self._delete(chosen), self)
        self._cleaner.succeeded.connect(self._cleaned)
        self._cleaner.start()

    @staticmethod
    def _delete(categories: list) -> tuple[int, int]:
        removed = 0
        skipped = 0
        for category in categories:
            gone, missed = services.delete_category(category)
            removed += gone
            skipped += missed
        return removed, skipped

    def _cleaned(self, result: tuple[int, int]) -> None:
        removed, skipped = result
        self.clean_button.setEnabled(True)
        self.summary.setText(f"Removed {services.format_bytes(removed)}. Skipped {skipped} files that were in use.")
        self._scan()


class GamePage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__(
            "Game Boost",
            "When a fullscreen app is in front, Deskline can switch on the high-performance power plan and put the previous plan back afterwards.",
        )
        self.shell = shell
        section = shell.config.section("game")
        self.enabled = Switch(bool(section.get("enabled")))
        self.perf = Switch(bool(section.get("max_performance", True)))
        self.priority = Switch(bool(section.get("priority")))
        self.pause = Switch(bool(section.get("pause_effects", True)))
        self.enabled.toggled.connect(lambda on: self._save(enabled=on))
        self.perf.toggled.connect(lambda on: self._save(max_performance=on))
        self.priority.toggled.connect(lambda on: self._save(priority=on))
        self.pause.toggled.connect(lambda on: self._save(pause_effects=on))
        card = Card()
        card.add(header("Enable", "Watches for a window that covers the whole screen.", self.enabled))
        card.add(header("Maximum performance", "Switches to the Windows high-performance plan, if that plan exists.", self.perf))
        card.add(header("Game gets priority", "Asks Windows for above-normal priority. Some games ignore this.", self.priority))
        card.add(header("Pause Deskline animations", "Stops the wallpaper, cursor, taskbar strip, and widgets while the fullscreen app is open.", self.pause))
        self.status = muted(shell.runtime.game_status())
        card.add(self.status)
        install = _button("Add high-performance plan")
        install.clicked.connect(self._install_plan)
        card.add(install)
        card.add(muted("On a desktop that already runs at full speed, the difference is small. Laptops notice it more."))
        self.body.addWidget(card)
        self.finish()
        self.shell.runtime.changed.connect(lambda: self.status.setText(self.shell.runtime.game_status()))

    def _save(self, **values) -> None:
        self.shell.config.update_section("game", **values)
        self.shell.runtime.apply()

    def _install_plan(self) -> None:
        if services.duplicate_high_performance():
            self.status.setText("High-performance plan added. It will be used the next time a fullscreen app is detected.")
        else:
            self.status.setText("Windows did not add the plan. It may already exist, or this account cannot change power plans.")


class ToolsPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("Tools", "Small helpers. They keep running while this window is open, and they stop when you quit Deskline.")
        self.shell = shell
        section = shell.config.section("tools")
        self.awake = Switch(bool(section.get("awake")))
        self.screen = Switch(bool(section.get("awake_screen", True)))
        self.hotkey = Switch(bool(section.get("hotkey", True)))
        self.awake.toggled.connect(lambda on: self._save(awake=on))
        self.screen.toggled.connect(lambda on: self._save(awake_screen=on))
        self.hotkey.toggled.connect(lambda on: self._save(hotkey=on))
        card = Card()
        card.add(header("Keep the PC awake", "No sleep while this is on.", self.awake))
        self.duration = ChoiceRow(
            [("30", "30 min"), ("60", "1 hour"), ("120", "2 hours"), ("0", "Until I turn it off")],
            str(int(section.get("awake_minutes") or 0)),
        )
        self.duration.changed.connect(lambda value: self._save(awake_minutes=int(value), awake=True))
        card.add(self.duration)
        card.add(header("Keep the screen on too", "Off: only the PC stays awake. The screen can still turn off.", self.screen))
        card.add(header("Always on top", "Win + Ctrl + T keeps the active window above others. Press it again to release.", self.hotkey))
        restart = _button("Restart Explorer")
        restart.clicked.connect(self._restart)
        card.add(header("Restart Explorer", "Use this when the taskbar or Start menu is stuck. Explorer windows close.", None))
        card.add(restart)
        startup = _button("Startup apps")
        startup.clicked.connect(lambda: winutil.open_settings("startupapps"))
        card.add(startup)
        self.body.addWidget(card)
        self.finish()
        self.shell.runtime.changed.connect(self._reload_awake)

    def _save(self, **values) -> None:
        if "awake_minutes" in values or values.get("awake") is False:
            self.shell.runtime._awake_deadline = None
        self.shell.config.update_section("tools", **values)
        self.shell.runtime.apply()

    def _reload_awake(self) -> None:
        awake = bool(self.shell.config.section("tools").get("awake"))
        self.awake.setChecked(awake, emit=False)

    def _restart(self) -> None:
        if QMessageBox.question(self, "Restart Explorer", "Open File Explorer windows will close.") != QMessageBox.StandardButton.Yes:
            return
        winutil.restart_explorer()


class AudioPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("Audio", "Clicks for the keyboard and mouse, plus a soft loop. They pause while a fullscreen app is in front.")
        self.shell = shell
        section = shell.config.section("audio")
        self.keys = Switch(bool(section.get("keyboard")))
        self.mouse = Switch(bool(section.get("mouse")))
        self.scape = Switch(bool(section.get("scape")))
        self.keys.toggled.connect(lambda on: self._save(keyboard=on))
        self.mouse.toggled.connect(lambda on: self._save(mouse=on))
        self.scape.toggled.connect(lambda on: self._save(scape=on))
        keys = Card()
        keys.add(header("Keyboard", "A short click on press and release.", self.keys))
        self.key_volume = LabeledSlider("Volume", 0, 100, int(section.get("key_volume") or 70), lambda value: f"{value}%")
        self.key_volume.changed.connect(lambda value: self._save(key_volume=value))
        keys.add(self.key_volume)
        mouse = Card()
        mouse.add(header("Mouse", "A click for each mouse button.", self.mouse))
        self.mouse_volume = LabeledSlider("Volume", 0, 100, int(section.get("mouse_volume") or 50), lambda value: f"{value}%")
        self.mouse_volume.changed.connect(lambda value: self._save(mouse_volume=value))
        mouse.add(self.mouse_volume)
        row = QHBoxLayout()
        row.addWidget(keys, 1)
        row.addWidget(mouse, 1)
        host = QWidget()
        host.setLayout(row)
        self.body.addWidget(host)
        scape = Card()
        scape.add(header("Soundscape", "A quiet generated loop.", self.scape))
        self.scape_volume = LabeledSlider("Volume", 0, 100, int(section.get("scape_volume") or 40), lambda value: f"{value}%")
        self.scape_volume.changed.connect(lambda value: self._save(scape_volume=value))
        scape.add(self.scape_volume)
        system = _button("System sounds")
        system.clicked.connect(lambda: __import__("subprocess").Popen(["mmsys.cpl"]))
        scape.add(system)
        upload_key = _button("Upload keyboard sound")
        upload_mouse = _button("Upload mouse sound")
        upload_key.clicked.connect(lambda: self._upload("key"))
        upload_mouse.clicked.connect(lambda: self._upload("mouse"))
        scape.add(upload_key)
        scape.add(upload_mouse)
        pack = _button("Sound pack folder")
        pack.clicked.connect(self._pack)
        scape.add(pack)
        scape.add(muted("A folder of wav files named 65.wav for a key, or left.wav, right.wav, and middle.wav. default.wav covers the rest."))
        self.body.addWidget(scape)
        mix = Card()
        mix.add(title_label("Ambience"))
        mix.add(muted("Each layer is a generated loop. Set a volume above zero to hear it. Fullscreen Game Boost pauses them."))
        for name, label in (("rain", "Rain"), ("wind", "Wind"), ("birds", "Birds"), ("city", "City"), ("thunder", "Thunder")):
            slider = LabeledSlider(label, 0, 100, int(section.get(name) or 0), lambda value: f"{value}%")
            slider.changed.connect(lambda value, key=name: self._save(**{key: value}))
            mix.add(slider)
        self.chime = Switch(bool(section.get("plug_chime")))
        self.chime.toggled.connect(lambda on: self._save(plug_chime=on))
        mix.add(header("Plug and unplug", "A short chime when a laptop charger connects or disconnects.", self.chime))
        self.body.addWidget(mix)
        eq = Card()
        self.eq = Switch(bool(section.get("eq")))
        self.eq.toggled.connect(lambda on: self._save(eq=on))
        eq.add(header("System EQ", "Writes a marked block into Equalizer APO if it is already installed.", self.eq))
        for name, label in (("eq_bass", "Bass"), ("eq_mid", "Mid"), ("eq_treble", "Treble")):
            slider = LabeledSlider(label, -12, 12, int(section.get(name) or 0), lambda value: f"{value} dB")
            slider.changed.connect(lambda value, key=name: self._save(**{key: value}))
            eq.add(slider)
        bands = list(section.get("eq_bands") or [0] * 10)
        frequencies = ("31 Hz", "62 Hz", "125 Hz", "250 Hz", "500 Hz", "1 kHz", "2 kHz", "4 kHz", "8 kHz", "16 kHz")
        for index, label in enumerate(frequencies):
            current = int(bands[index]) if index < len(bands) else 0
            slider = LabeledSlider(label, -12, 12, current, lambda value: f"{value} dB")
            slider.changed.connect(lambda value, band=index: self._band(band, value))
            eq.add(slider)
        self.eq_status = muted(shell.runtime.eq_status())
        eq.add(self.eq_status)
        self.body.addWidget(eq)
        self.finish()

    def _pack(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Sound pack folder")
        if path:
            self._save(sound_pack=path)

    def _band(self, index: int, value: int) -> None:
        bands = list(self.shell.config.section("audio").get("eq_bands") or [0] * 10)
        while len(bands) < 10:
            bands.append(0)
        bands[index] = int(value)
        self._save(eq_bands=bands[:10])

    def _upload(self, slot: str) -> None:
        from deskline.sounds import install_upload
        path, _filter = QFileDialog.getOpenFileName(self, "Click sound", "", "Audio (*.wav *.mp3 *.ogg *.flac)")
        if not path:
            return
        try:
            dest = install_upload(path, slot)
        except Exception as exc:
            QMessageBox.warning(self, "Deskline", str(exc))
            return
        self._save(**{f"{slot}_file": dest})

    def _save(self, **values) -> None:
        self.shell.config.update_section("audio", **values)
        self.shell.runtime.apply()
        self.eq_status.setText(self.shell.runtime.eq_status())


class NetworkPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("Network", "Ping to your router and two public servers. This does not change Windows network settings.")
        self.shell = shell
        top = QHBoxLayout()
        self.summary = muted("Not tested yet.")
        self.button = _button("TEST CONNECTION", "primary")
        self.button.clicked.connect(self._test)
        top.addWidget(self.summary, 1)
        top.addWidget(self.button)
        host = QWidget()
        host.setLayout(top)
        self.body.addWidget(host)
        stats = QHBoxLayout()
        self.router = self._card("Your router")
        self.cloud = self._card("Cloudflare")
        self.google = self._card("Google")
        for card, _value, _detail in (self.router, self.cloud, self.google):
            stats.addWidget(card)
        stats_host = QWidget()
        stats_host.setLayout(stats)
        self.body.addWidget(stats_host)
        note = Card()
        note.add(title_label("What helps"))
        self.help = muted("Run a test to see the numbers.")
        note.add(self.help)
        note.add(muted("Ping depends on the path to that server. There is no registry switch that makes a game’s UDP connection faster."))
        self.body.addWidget(note)
        self.finish()

    def _card(self, caption: str):
        card = Card()
        card.add(muted(caption))
        value = title_label("—", "stat")
        detail = muted("")
        card.add(value)
        card.add(detail)
        return card, value, detail

    def _test(self) -> None:
        self.button.setEnabled(False)
        self.button.setText("TESTING…")
        self._worker = Worker(services.network_report, self)
        self._worker.succeeded.connect(self._show)
        self._worker.failed.connect(lambda message: self._done(message))
        self._worker.start()

    def _show(self, report: dict) -> None:
        self._fill(self.router, report["router"])
        self._fill(self.cloud, report["cloudflare"])
        self._fill(self.google, report["google"])
        cloud = report["cloudflare"]["ms"]
        loss = report["cloudflare"]["loss"]
        label = "Good" if cloud is not None and cloud < 40 and loss == 0 else "Check"
        self.summary.setText(f"{label} · {report['link']} · router {report['gateway']}")
        notes = []
        if cloud is not None and cloud < 50 and loss == 0:
            notes.append("The path to Cloudflare looks fine for online games.")
        elif loss:
            notes.append(f"Cloudflare lost {loss}% of the test packets.")
        else:
            notes.append("The public ping is high. That can be the route, not your PC.")
        notes.append("A download in the background can raise ping while you play.")
        self.help.setText("\n".join(notes))
        self._done()

    def _fill(self, card, sample: dict) -> None:
        ms = sample.get("ms")
        card[1].setText("—" if ms is None else f"{ms} ms")
        card[2].setText(f"±{sample.get('jitter', 0)} ms · {sample.get('loss', 0)}% lost")

    def _done(self, message: str = "") -> None:
        self.button.setEnabled(True)
        self.button.setText("TEST CONNECTION")
        if message:
            self.summary.setText(message)


class DriversPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__("Drivers", "Reads the graphics driver Windows already installed. New drivers come from Windows Update or the card maker.")
        self.shell = shell
        top = QHBoxLayout()
        self.summary = muted("Scanning…")
        scan = _button("Scan again")
        scan.clicked.connect(self._scan)
        top.addWidget(self.summary, 1)
        top.addWidget(scan)
        host = QWidget()
        host.setLayout(top)
        self.body.addWidget(host)
        self.card = Card()
        self.body.addWidget(self.card)
        self.problems = muted("")
        problem_card = Card()
        problem_card.add(title_label("Devices with problems"))
        problem_card.add(self.problems)
        manager = _button("Device Manager")
        manager.clicked.connect(lambda: __import__("subprocess").Popen(["mmc", "devmgmt.msc"]))
        problem_card.add(manager)
        self.body.addWidget(problem_card)
        self.finish()
        self._scan()

    def _scan(self) -> None:
        self.summary.setText("Scanning…")
        self._worker = Worker(services.driver_report, self)
        self._worker.succeeded.connect(self._show)
        self._worker.failed.connect(self.summary.setText)
        self._worker.start()

    def _show(self, report: dict) -> None:
        while self.card.layout.count():
            item = self.card.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        months = report.get("months")
        age = "age unknown" if months is None else f"about {months} months old"
        self.summary.setText("A newer graphics driver is worth a look." if (months or 0) >= 8 else "Nothing here looks urgent.")
        self.card.add(title_label(report["name"]))
        self.card.add(muted(f"Driver {report['version']} · {age}"))
        row = QHBoxLayout()
        windows = _button("Windows Update")
        windows.clicked.connect(lambda: winutil.open_settings("windowsupdate"))
        row.addWidget(windows)
        vendor = report.get("vendor")
        if vendor == "nvidia":
            site = _button("NVIDIA downloads")
            site.clicked.connect(lambda: winutil.os_start("https://www.nvidia.com/Download/index.aspx"))
            row.addWidget(site)
        elif vendor == "amd":
            site = _button("AMD downloads")
            site.clicked.connect(lambda: winutil.os_start("https://www.amd.com/en/support"))
            row.addWidget(site)
        elif vendor == "intel":
            site = _button("Intel downloads")
            site.clicked.connect(lambda: winutil.os_start("https://www.intel.com/content/www/us/en/download-center/home.html"))
            row.addWidget(site)
        row.addStretch(1)
        host = QWidget()
        host.setLayout(row)
        self.card.add(host)
        problems = report.get("problems") or []
        self.problems.setText("No device problems found." if not problems else "\n".join(problems[:8]))


class RetroPage(PageScroll):
    def __init__(self, shell: Shell):
        super().__init__(
            "Retro",
            "Left or compact taskbar, see-through Windows transparency, and the classic right-click menu. These are Windows settings, and each one can be turned back off.",
        )
        self.shell = shell
        section = shell.config.section("retro")
        card = Card()
        self.left = Switch(bool(section.get("left_taskbar")))
        self.compact = Switch(bool(section.get("compact_taskbar")))
        self.glass = Switch(bool(section.get("glass")))
        self.left.toggled.connect(self._left)
        self.compact.toggled.connect(self._compact)
        self.glass.toggled.connect(self._glass)
        card.add(header("Left taskbar", "Windows 11 icons move to the left. The alignment you had is saved.", self.left))
        card.add(header("Compact taskbar", "Uses the smaller taskbar. The size you had is saved.", self.compact))
        card.add(header("Glass", "Turns on Windows transparency so windows can look see-through.", self.glass))
        restart = _button("Restart Explorer")
        restart.clicked.connect(winutil.restart_explorer)
        card.add(restart)
        card.add(muted("Alignment and size show up after Explorer restarts. Your windows stay open."))
        self.body.addWidget(card)
        classic = Card()
        self.classic = Switch(tweaks.classic_menu_enabled())
        self.classic.toggled.connect(self._classic)
        classic.add(header("Classic right-click menu", "Off brings back the compact Windows 11 menu. Explorer may need a restart.", self.classic))
        self.body.addWidget(classic)
        self.finish()

    def _left(self, on: bool) -> None:
        section = self.shell.config.section("retro")
        saved = retro.set_left_taskbar(on, section.get("saved_align"))
        self.shell.config.update_section("retro", left_taskbar=on, saved_align=saved)

    def _compact(self, on: bool) -> None:
        section = self.shell.config.section("retro")
        saved = retro.set_compact_taskbar(on, section.get("saved_size"))
        self.shell.config.update_section("retro", compact_taskbar=on, saved_size=saved)

    def _glass(self, on: bool) -> None:
        section = self.shell.config.section("retro")
        saved = retro.set_glass(on, section.get("saved_transparency"))
        self.shell.config.update_section("retro", glass=on, saved_transparency=saved)

    def _classic(self, on: bool) -> None:
        tweaks.set_classic_menu(on)
        self.shell.config.update_section("windows", classic_menu=on)


def main() -> None:
    enable = winutil.enable_dpi_awareness
    enable()
    if not winutil.acquire_single_instance():
        return
    app = QApplication([])
    app.setStyleSheet(STYLESHEET)
    window = Shell()
    window.show()
    app.exec()
