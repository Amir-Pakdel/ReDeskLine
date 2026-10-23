"""Wallpaper overlays drawn on top of a video frame."""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

_COUNTS = {
    "dust": 50,
    "snow": 80,
    "stars": 60,
    "embers": 40,
    "mist": 6,
    "rain": 90,
    "sparks": 36,
    "fog": 8,
}


class OverlayField:
    def __init__(self) -> None:
        self.kind = "none"
        self.particles: list[dict] = []
        self.width = 0
        self.height = 0
        self.amount = 50
        self.color = "#ffffff"

    def ensure(self, kind: str, width: int, height: int, amount: int, color: str) -> None:
        amount = max(0, min(100, int(amount)))
        if (
            kind == self.kind
            and width == self.width
            and height == self.height
            and amount == self.amount
            and color == self.color
            and self.particles
        ):
            return
        self.kind = kind
        self.width = width
        self.height = height
        self.amount = amount
        self.color = color
        count = int(_COUNTS.get(kind, 0) * amount / 50)
        self.particles = [_spawn(kind, width, height, anywhere=True) for _ in range(max(0, count))]

    def step(self, dt: float) -> None:
        for particle in self.particles:
            particle["x"] += particle["vx"] * dt
            particle["y"] += particle["vy"] * dt
            particle["phase"] += dt
            if particle["y"] > self.height + 40 or particle["y"] < -40 or particle["x"] < -40 or particle["x"] > self.width + 40:
                particle.update(_spawn(self.kind, self.width, self.height, anywhere=False))


def _spawn(kind: str, width: int, height: int, anywhere: bool) -> dict:
    x = random.uniform(0, max(1, width))
    y = random.uniform(0, height) if anywhere else -12
    if kind == "snow":
        return {"x": x, "y": y, "vx": random.uniform(-12, 12), "vy": random.uniform(30, 80), "r": random.uniform(1.2, 3.2), "phase": random.random()}
    if kind == "stars":
        return {"x": x, "y": y if anywhere else random.uniform(0, height), "vx": 0, "vy": 0, "r": random.uniform(0.8, 2.2), "phase": random.uniform(0, 6)}
    if kind == "embers":
        return {"x": x, "y": height + 10 if not anywhere else y, "vx": random.uniform(-8, 8), "vy": random.uniform(-50, -20), "r": random.uniform(1.4, 3.0), "phase": random.random()}
    if kind == "mist":
        return {"x": x, "y": random.uniform(0, height), "vx": random.uniform(-18, 18), "vy": random.uniform(-6, 6), "r": random.uniform(80, 180), "phase": random.random()}
    if kind == "rain":
        return {"x": x, "y": y, "vx": random.uniform(-30, -8), "vy": random.uniform(520, 860), "r": random.uniform(10, 18), "phase": random.random()}
    if kind == "sparks":
        return {"x": x, "y": height + 8 if not anywhere else y, "vx": random.uniform(-16, 16), "vy": random.uniform(-140, -40), "r": random.uniform(1.2, 2.6), "phase": random.random()}
    if kind == "fog":
        return {"x": x, "y": random.uniform(0, height), "vx": random.uniform(-12, 12), "vy": random.uniform(-4, 4), "r": random.uniform(120, 260), "phase": random.random()}
    return {"x": x, "y": y if anywhere else random.uniform(0, height), "vx": random.uniform(-10, 10), "vy": random.uniform(-8, 8), "r": random.uniform(1.0, 2.4), "phase": random.random()}


def _brush(kind: str, particle: dict, tint: QColor) -> QColor:
    if kind == "snow":
        color = QColor(255, 255, 255, 190)
    elif kind == "stars":
        twinkle = 120 + int(100 * (0.5 + 0.5 * math.sin(particle["phase"] * 3)))
        color = QColor(255, 255, 230, twinkle)
    elif kind == "embers":
        color = QColor(255, 140, 40, 200)
    elif kind == "mist":
        color = QColor(210, 220, 235, 28)
    elif kind == "rain":
        color = QColor(186, 210, 255, 160)
    elif kind == "sparks":
        color = QColor(255, 220, 120, 210)
    elif kind == "fog":
        color = QColor(200, 206, 214, 34)
    else:
        color = QColor(230, 220, 190, 140)
    if tint.isValid() and tint.name().lower() not in {"#ffffff", "#fff"}:
        color = QColor(tint.red(), tint.green(), tint.blue(), color.alpha())
    return color


def paint_shader(painter: QPainter, kind: str, width: int, height: int, phase: float) -> None:
    """Original desktop patterns. These are not copied shader-library sources."""
    painter.setPen(Qt.PenStyle.NoPen)
    kind = kind if kind in {"plasma", "waves", "grid", "bars"} else "plasma"
    if kind == "waves":
        painter.fillRect(0, 0, width, height, QColor("#07111f"))
        for band in range(8):
            color = QColor("#38bdf8")
            color.setAlpha(40 + band * 12)
            painter.setBrush(color)
            y = int(height * (0.2 + 0.08 * band) + math.sin(phase * 2 + band) * 24)
            painter.drawRoundedRect(-20, y, width + 40, 18, 9, 9)
        return
    if kind == "grid":
        painter.fillRect(0, 0, width, height, QColor("#09090b"))
        painter.setPen(QPen(QColor(255, 59, 92, 90), 1))
        step = 48
        shift = int(phase * 20) % step
        for x in range(-step, width + step, step):
            painter.drawLine(x + shift, 0, x + shift, height)
        for y in range(-step, height + step, step):
            painter.drawLine(0, y + shift, width, y + shift)
        return
    if kind == "bars":
        painter.fillRect(0, 0, width, height, QColor("#12080c"))
        for index in range(24):
            level = 0.25 + 0.75 * abs(math.sin(phase * 3 + index * 0.45))
            bar_h = int(height * 0.7 * level)
            painter.setBrush(QColor(255, 59 + (index * 7) % 120, 92, 210))
            painter.drawRect(int(index * width / 24) + 4, height - bar_h - 20, max(4, int(width / 24) - 8), bar_h)
        return
    painter.fillRect(0, 0, width, height, QColor("#140818"))
    for index in range(6):
        color = (QColor("#ff3b5c"), QColor("#7c3aed"), QColor("#38bdf8"), QColor("#f59e0b"), QColor("#22c55e"), QColor("#e879f9"))[index]
        color.setAlpha(70)
        painter.setBrush(color)
        cx = width * (0.2 + 0.12 * index) + math.sin(phase + index) * width * 0.08
        cy = height * (0.3 + 0.08 * (index % 3)) + math.cos(phase * 0.8 + index) * height * 0.1
        radius = 80 + 40 * (0.5 + 0.5 * math.sin(phase * 1.4 + index))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)


def paint_overlay(
    painter: QPainter,
    field: OverlayField,
    kind: str,
    width: int,
    height: int,
    dt: float,
    color: str = "#ffffff",
    amount: int = 50,
) -> None:
    if kind in {"", "none"}:
        return
    field.ensure(kind, width, height, amount, color)
    field.step(dt)
    tint = QColor(color)
    painter.setPen(Qt.PenStyle.NoPen)
    for particle in field.particles:
        brush = _brush(kind, particle, tint)
        if kind == "rain":
            painter.setPen(QPen(brush, 1.4))
            painter.drawLine(
                QPointF(particle["x"], particle["y"]),
                QPointF(particle["x"] + particle["vx"] * 0.02, particle["y"] + particle["r"]),
            )
            painter.setPen(Qt.PenStyle.NoPen)
            continue
        painter.setBrush(brush)
        painter.drawEllipse(QPointF(particle["x"], particle["y"]), particle["r"], particle["r"])
