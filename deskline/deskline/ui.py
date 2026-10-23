"""Shared dark widgets. The accent is Deskline's own red, not a copied brand asset."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

STYLESHEET = """
QWidget { color: #f4f4f5; font-family: "Segoe UI"; font-size: 13px; }
QMainWindow, #shell, #page, #pageHead, #pageBody { background: #0b0b0e; }
#sidebar, #navHost { background: #101014; }
#sidebar { border-right: 1px solid #23232a; }
#card {
    background: #16161b;
    border: 1px solid #2a2a32;
    border-radius: 18px;
}
#cardTitle { font-size: 14px; font-weight: 650; color: #fafafa; }
#pageTitle { font-size: 26px; font-weight: 700; color: #fafafa; }
#brand { font-size: 18px; font-weight: 700; color: #fafafa; }
#navGroup {
    color: #71717a;
    font-size: 11px;
    font-weight: 700;
    padding: 14px 12px 4px 12px;
}
#muted, QLabel#muted { color: #a1a1aa; }
#sliderValue {
    color: #fafafa;
    background: #23232a;
    border-radius: 8px;
    padding: 2px 8px;
    min-width: 52px;
}
#stat { font-size: 28px; font-weight: 700; }
#good { color: #34d399; }
#warn { color: #fbbf24; }
QPushButton {
    background: #23232a;
    color: #f4f4f5;
    border: 1px solid #2f2f38;
    border-radius: 12px;
    padding: 8px 14px;
}
QPushButton:hover { background: #2c2c34; }
QPushButton:checked { background: #ff3b5c; border-color: #ff3b5c; color: white; }
QPushButton[role="primary"] {
    background: white;
    color: #111111;
    border: none;
    border-radius: 18px;
    padding: 10px 18px;
    font-weight: 700;
}
QPushButton[role="primary"]:hover { background: #ffe4e8; }
QPushButton[role="nav"] {
    background: transparent;
    border: none;
    text-align: left;
    padding: 9px 12px;
    border-radius: 12px;
    color: #a1a1aa;
}
QPushButton[role="nav"]:hover { background: #1b1b21; color: #fafafa; }
QPushButton[role="nav"]:checked { background: #2a1520; color: white; }
QPushButton[role="choice"] {
    background: #1b1b21;
    border: 1px solid #2e2e36;
    border-radius: 14px;
    padding: 7px 12px;
    color: #e4e4e7;
}
QPushButton[role="choice"]:hover { background: #26262e; }
QPushButton[role="choice"]:checked {
    background: #ff3b5c;
    border-color: #ff3b5c;
    color: white;
}
QSlider::groove:horizontal { height: 6px; background: #2e2e36; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #ff3b5c; border-radius: 3px; }
QSlider::handle:horizontal {
    width: 18px; height: 18px; margin: -6px 0; background: white; border-radius: 9px;
}
QScrollArea, #pageScroll { background: #0b0b0e; border: none; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 6px 2px 6px 0; }
QScrollBar::handle:vertical { background: #3f3f46; border-radius: 6px; min-height: 36px; }
QScrollBar::handle:vertical:hover { background: #71717a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }
QLineEdit, QTableWidget {
    background: #101014;
    border: 1px solid #2e2e36;
    border-radius: 12px;
    padding: 8px 10px;
    color: #f4f4f5;
}
QLineEdit:focus { border-color: #ff3b5c; }
QHeaderView::section { background: #16161b; color: #a1a1aa; border: none; padding: 6px; }
"""


class AccentMark(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(12, 12)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ff3b5c"))
        painter.drawEllipse(0, 0, 12, 12)
        painter.end()


class _Slider(QSlider):
    """The page scroll owns the wheel. Dragging the handle still changes the value."""

    def wheelEvent(self, event):
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        if isinstance(parent, QScrollArea):
            bar = parent.verticalScrollBar()
            delta = event.angleDelta().y() or event.pixelDelta().y()
            bar.setValue(bar.value() - delta)
        event.accept()


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._spacing = spacing
        self._items: list = []

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        # Parent layouts must not ask for this. Doing so recurses through nested
        # scroll areas and overflows the stack while the window is opening.
        return False

    def heightForWidth(self, width: int) -> int:
        return self._flow(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._flow(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _flow(self, rect: QRect, test: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = area.x()
        y = area.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > area.right() and line_height > 0:
                x = area.x()
                y += line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class Switch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on = bool(checked)

    def isChecked(self) -> bool:
        return self._on

    def setChecked(self, checked: bool, emit: bool = True) -> None:
        checked = bool(checked)
        if checked == self._on:
            return
        self._on = checked
        self.update()
        if emit:
            self.toggled.emit(checked)

    def mousePressEvent(self, event):
        self.setChecked(not self._on)
        event.accept()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ff3b5c" if self._on else "#3f3f46"))
        painter.drawRoundedRect(0, 0, 46, 26, 13, 13)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(22 if self._on else 2, 2, 22, 22)
        painter.end()


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 14, 16, 14)
        self.layout.setSpacing(8)

    def add(self, widget: QWidget) -> QWidget:
        self.layout.addWidget(widget)
        return widget


def title_label(text: str, object_name: str = "cardTitle") -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)
    return label


def muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return muted_font(label)


def muted_font(label: QLabel) -> QLabel:
    return label


def header(title: str, subtitle: str, switch: Switch | None = None) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    text = QVBoxLayout()
    text.setSpacing(2)
    text.addWidget(title_label(title))
    text.addWidget(muted(subtitle))
    layout.addLayout(text, 1)
    if switch is not None:
        layout.addWidget(switch, 0, Qt.AlignmentFlag.AlignTop)
    return row


class LabeledSlider(QWidget):
    changed = Signal(int)

    def __init__(self, label: str, minimum: int, maximum: int, value: int = 0, formatter=None):
        super().__init__()
        self._formatter = formatter or (lambda number: str(number))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.caption = QLabel(label)
        self.caption.setMinimumWidth(108)
        self.slider = _Slider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.value_label = QLabel(self._formatter(value))
        self.value_label.setObjectName("sliderValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.caption)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_label)
        self.slider.valueChanged.connect(self._on_value)

    def _on_value(self, value: int) -> None:
        self.value_label.setText(self._formatter(value))
        self.changed.emit(value)

    def setValue(self, value: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self.value_label.setText(self._formatter(value))


class ChoiceRow(QWidget):
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], selected: str = ""):
        super().__init__()
        layout = FlowLayout(self, spacing=8)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for key, label in options:
            button = QPushButton(label)
            button.setProperty("role", "choice")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self.group.addButton(button)
            self._buttons[key] = button
            layout.addWidget(button)
            button.clicked.connect(lambda _checked=False, item=key: self.changed.emit(item))
        if selected in self._buttons:
            self._buttons[selected].setChecked(True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.apply_width(self.width())

    def apply_width(self, width: int) -> None:
        if width < 20:
            return
        needed = self.layout()._flow(QRect(0, 0, width, 0), True)
        if needed > 0 and self.minimumHeight() != needed:
            self.setMinimumHeight(needed)

    def setValue(self, key: str) -> None:
        button = self._buttons.get(key)
        if button is None:
            return
        self.group.blockSignals(True)
        button.setChecked(True)
        self.group.blockSignals(False)


def page_heading(title: str, subtitle: str) -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setSpacing(4)
    heading = title_label(title, "pageTitle")
    font = QFont("Segoe UI", 22)
    font.setWeight(QFont.Weight.Bold)
    heading.setFont(font)
    layout.addWidget(heading)
    layout.addWidget(muted(subtitle))
    return layout
