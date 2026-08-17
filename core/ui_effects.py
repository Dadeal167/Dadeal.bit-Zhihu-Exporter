# -*- coding: utf-8 -*-
"""UI 动效组件: 动态光晕背景 / 按钮柔光。

(鼠标粒子特效已按需求移除, 仅保留轻量的背景光晕与按钮光效)
"""
import math

from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap, QRadialGradient, QBrush
from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect


class GlowBackground(QWidget):
    """非常淡的动态光晕背景：预渲染光斑贴图, 缓慢漂移绘制"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._t = 0.0
        self._blobs = []
        self._build_blobs()
        self._timer = QTimer(self)
        self._timer.setInterval(66)  # ~15fps, 呼吸感足够且省资源
        self._timer.timeout.connect(self._tick)

    def _build_blobs(self):
        """把光斑一次性渲染成小贴图, 之后每帧只做贴图漂移"""
        specs = [
            (0.20, 0.16, 240, QColor(150, 205, 245, 26)),
            (0.82, 0.24, 280, QColor(120, 185, 240, 22)),
            (0.30, 0.86, 250, QColor(170, 215, 248, 20)),
            (0.86, 0.82, 210, QColor(140, 195, 242, 18)),
        ]
        self._blobs = []
        for bx, by, radius, color in specs:
            pix = QPixmap(radius * 2, radius * 2)
            pix.fill(Qt.transparent)
            p = QPainter(pix)
            gradient = QRadialGradient(QPointF(radius, radius), radius)
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillRect(pix.rect(), QBrush(gradient))
            p.end()
            self._blobs.append((bx, by, radius, pix))

    def showEvent(self, event):
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self):
        self._t += 0.05
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        t = self._t
        for i, (bx, by, radius, pix) in enumerate(self._blobs):
            cx = (bx + 0.06 * math.sin(t * (0.5 + 0.2 * i) + i * 1.7)) * w
            cy = (by + 0.05 * math.cos(t * (0.4 + 0.15 * i) + i * 2.3)) * h
            painter.drawPixmap(int(cx - radius), int(cy - radius), pix)
        painter.end()


def apply_glow(widget, color=QColor(110, 190, 245, 130), blur_radius=20, dy=4):
    """给控件加柔和蓝色光晕"""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setColor(color)
    effect.setOffset(0, dy)
    widget.setGraphicsEffect(effect)
    return effect
