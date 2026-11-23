"""Qt widgets rendered offscreen (no display needed)."""

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6 import QtWidgets
except ImportError as e:  # PySide6 missing or system libs (libEGL) absent
    pytest.skip(f"Qt unavailable: {e}", allow_module_level=True)

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent

from pi_tool.core.grid import Calibration
from pi_tool.core.map_model import CellState, empty_map, load_map
from pi_tool.core.scene import grid_scene


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_overlay_paints_scene(qapp):
    from pi_tool.platform.overlay import OverlayWindow

    w = OverlayWindow()
    w.place((0, 0, 800, 600))
    cal = Calibration.from_cell_size((40.0, 200.0), 40, 20)
    m = empty_map().with_state(30, CellState.OBSTACLE)
    w.set_shapes(grid_scene(m, cal), banner="test")
    img = w.grab().toImage()
    x, y = map(round, cal.cell_center(30))
    c = img.pixelColor(x, y)
    assert c.red() > c.blue() and c.alpha() > 0
    corner = img.pixelColor(799, 599)
    assert corner.alpha() == 0  # transparent outside shapes


def test_overlay_input_mode_signals(qapp):
    from pi_tool.platform.overlay import OverlayWindow

    w = OverlayWindow()
    got = []
    w.dragged.connect(lambda dx, dy: got.append((dx, dy)))
    w.set_input_enabled(True)
    assert w.input_enabled
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(10, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(15, 12),
        QPointF(15, 12),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    w.mousePressEvent(press)
    w.mouseMoveEvent(move)
    assert got == [(5.0, 2.0)]
    w.set_input_enabled(False)
    w.mousePressEvent(press)
    w.mouseMoveEvent(move)
    assert len(got) == 1  # click-through mode ignores input


def test_map_editor_click_and_save(qapp, tmp_path):
    from pi_tool.app.map_editor import MapEditor

    png = tmp_path / "cap.png"
    img = QImage(800, 600, QImage.Format.Format_RGB32)
    img.fill(QColor(40, 40, 40))
    img.save(str(png))
    map_path = tmp_path / "map.json"
    ed = MapEditor(png, empty_map("t"), map_path)
    ed.resize(800, 630)  # 1:1 view
    cell = 200
    x, y = ed.calib.cell_center(cell)
    s, ox, oy = ed._view()
    pos = QPointF(x * s + ox, y * s + oy)
    ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        pos,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ed.mousePressEvent(ev)
    assert ed.map.state(cell) is CellState.OBSTACLE
    ed.save()
    saved = load_map(path=map_path)
    assert saved.state(cell) is CellState.OBSTACLE and saved.reference_captures == ("cap.png",)
    ann = json.loads(png.with_suffix(".json").read_text())
    assert ann["resolution"] == [800, 600] and "calibration" in ann
    ed.grab()  # paints without error
