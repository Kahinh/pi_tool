"""Transparent, topmost, click-through overlay window (V1.2) drawing a core.scene.

Coordinates: shapes are in overlay-local PHYSICAL px (= game client px). Qt paints in
logical px, so the painter is scaled by 1/devicePixelRatio.
Input mode (calibration only, user-triggered): the window temporarily accepts mouse/keys.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from pi_tool.core.scene import RGBA, Shape
from pi_tool.platform import win32

_BASE_FLAGS = (
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
    | Qt.WindowType.NoDropShadowWindowHint
)
_PASSIVE_FLAGS = Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus


def _qcolor(c: RGBA) -> QColor:
    return QColor(c[0], c[1], c[2], c[3])


def paint_shapes(p: QPainter, shapes: list[Shape]) -> None:
    """Draw scene shapes with an already-configured painter (px = painter units)."""
    font = QFont()
    font.setPixelSize(10)
    p.setFont(font)
    for s in shapes:
        p.setBrush(QBrush(_qcolor(s.fill)) if s.fill else Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_qcolor(s.outline), s.width) if s.outline else Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in s.points]))
        if s.label and s.center:
            p.setPen(QColor(255, 255, 255, 220))
            r = QRect(round(s.center[0]) - 20, round(s.center[1]) - 8, 40, 16)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, s.label)


class OverlayWindow(QWidget):
    # Calibration-mode input, in physical px.
    dragged = Signal(float, float)  # dx, dy
    wheeled = Signal(int, float, float, bool)  # steps, x, y, shift
    nudged = Signal(int, int)  # arrow keys
    accepted = Signal()
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(None, _BASE_FLAGS | _PASSIVE_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setWindowTitle("pi_tool overlay")
        self._shapes: list[Shape] = []
        self._banner: str | None = None
        self._input = False
        self._drag_from: QPointF | None = None
        self._rect: win32.Rect | None = None

    # --- state -------------------------------------------------------------------------
    @property
    def input_enabled(self) -> bool:
        return self._input

    def set_shapes(self, shapes: list[Shape], banner: str | None = None) -> None:
        self._shapes, self._banner = shapes, banner
        self.update()

    def place(self, rect: win32.Rect) -> None:
        """Cover the game client rect (screen physical px)."""
        if rect == self._rect and self.isVisible():
            return
        self._rect = rect
        if win32.IS_WIN and self.isVisible():
            win32.place_topmost(int(self.winId()), rect)
        else:
            dpr = self._dpr()
            x, y, w, h = rect
            self.setGeometry(QRect(round(x / dpr), round(y / dpr), round(w / dpr), round(h / dpr)))

    def show_overlay(self) -> None:
        if self.isVisible():
            return
        self.show()
        hwnd = int(self.winId())
        win32.style_overlay(hwnd, click_through=not self._input)
        win32.exclude_from_capture(hwnd)
        if self._rect:
            win32.place_topmost(hwnd, self._rect)

    def set_input_enabled(self, on: bool) -> None:
        """Only for calibration mode: overlay captures mouse/keys while on."""
        if on == self._input:
            return
        self._input = on
        visible = self.isVisible()
        self.setWindowFlags(_BASE_FLAGS if on else _BASE_FLAGS | _PASSIVE_FLAGS)
        if visible:
            self.hide()
            self.show_overlay()
        if on:
            self.activateWindow()
            self.setFocus()

    def _dpr(self) -> float:
        return self.devicePixelRatioF() or 1.0

    # --- painting ----------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.scale(1 / self._dpr(), 1 / self._dpr())
        paint_shapes(p, self._shapes)
        if self._banner:
            font = QFont()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 170))
            box = QRect(10, 10, 900, 30)
            p.drawRect(box)
            p.setPen(QColor(255, 255, 255))
            font.setPixelSize(16)
            p.setFont(font)
            p.drawText(box.adjusted(8, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self._banner)
        p.end()

    # --- calibration input -------------------------------------------------------------
    def mousePressEvent(self, e) -> None:
        if self._input and e.button() == Qt.MouseButton.LeftButton:
            self._drag_from = e.position() * self._dpr()

    def mouseMoveEvent(self, e) -> None:
        if self._input and self._drag_from is not None:
            pos = e.position() * self._dpr()
            d = pos - self._drag_from
            self._drag_from = pos
            self.dragged.emit(d.x(), d.y())

    def mouseReleaseEvent(self, _e) -> None:
        self._drag_from = None

    def wheelEvent(self, e) -> None:
        if not self._input:
            return
        steps = round(e.angleDelta().y() / 120) or (1 if e.angleDelta().y() > 0 else -1)
        pos = e.position() * self._dpr()
        shift = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self.wheeled.emit(steps, pos.x(), pos.y(), shift)

    def keyPressEvent(self, e) -> None:
        if not self._input:
            return
        k = e.key()
        arrows = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1),
            Qt.Key.Key_Down: (0, 1),
        }
        if k in arrows:
            self.nudged.emit(*arrows[k])
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accepted.emit()
        elif k == Qt.Key.Key_Escape:
            self.cancelled.emit()
