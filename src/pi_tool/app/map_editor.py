"""`pi-tool-map CAPTURE.png` — survey the Harebourg map on a real capture (V1.1 / V1.4).

Left click: cycle cell type · Shift+click: toggle line-of-sight blocker ·
Right-drag: move grid · wheel: size · Shift+wheel: flatten · arrows: 1 px ·
I: ids · Ctrl+S: save map (data/maps) + calibration (capture sidecar .json).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget

from pi_tool.core import calibration as cb
from pi_tool.core.grid import cell_to_xy
from pi_tool.core.map_model import CYCLE, MapModel, empty_map, load_map, save_map
from pi_tool.core.scene import GridStyle, grid_scene
from pi_tool.platform.overlay import paint_shapes

HELP = (
    "Clic : type · Maj+clic : ligne de vue · clic droit glissé : déplacer · molette : taille · "
    "Maj+molette : aplatir · flèches : 1 px · I : ids · Ctrl+S : enregistrer"
)


class MapEditor(QWidget):
    def __init__(self, image_path: Path, game_map: MapModel, map_path: Path | None = None):
        super().__init__()
        self.image_path, self.map, self.map_path = image_path, game_map, map_path
        self.img = QImage(str(image_path))
        if self.img.isNull():
            raise FileNotFoundError(image_path)
        self.sidecar = image_path.with_suffix(".json")
        self.ann = json.loads(self.sidecar.read_text("utf-8")) if self.sidecar.exists() else {}
        cal, _ = cb.from_annotation(self.ann)
        self.calib = cal or cb.default_calibration((0, 0, self.img.width(), self.img.height()))
        self.show_ids = False
        self.hover: int | None = None
        self.dirty = False
        self._drag: QPointF | None = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.resize(min(1600, self.img.width()), min(900, self.img.height()) + 30)
        self._title()

    # --- view transform: image px <-> widget px ------------------------------------------
    def _view(self) -> tuple[float, float, float]:
        h = self.height() - 30
        s = min(self.width() / self.img.width(), h / self.img.height())
        return s, (self.width() - self.img.width() * s) / 2, (h - self.img.height() * s) / 2

    def _to_img(self, p: QPointF) -> tuple[float, float]:
        s, ox, oy = self._view()
        return (p.x() - ox) / s, (p.y() - oy) / s

    def _title(self) -> None:
        star = " *" if self.dirty else ""
        self.setWindowTitle(f"pi_tool — carte {self.map.name}{star} — {self.image_path.name}")

    # --- painting --------------------------------------------------------------------------
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(30, 30, 30))
        s, ox, oy = self._view()
        p.save()
        p.translate(ox, oy)
        p.scale(s, s)
        p.drawImage(0, 0, self.img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        style = GridStyle(opacity=1.0, show_ids=self.show_ids, show_outside=True)
        paint_shapes(p, grid_scene(self.map, self.calib, style))
        if self.hover is not None:
            p.setPen(QPen(QColor(0, 255, 120), 3 / s))
            p.setBrush(Qt.BrushStyle.NoBrush)
            pts = self.calib.cell_diamond(self.hover)
            p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
        p.restore()
        p.setPen(QColor(230, 230, 230))
        f = QFont()
        f.setPixelSize(13)
        p.setFont(f)
        info = ""
        if self.hover is not None:
            st = self.map.state(self.hover).value
            info = f"cellule {self.hover} {cell_to_xy(self.hover)} — {st}"
            if self.hover in self.map.blocks_los:
                info += " + bloque LdV"
            info += "   |   "
        bar = QRectF(8, self.height() - 26, self.width() - 16, 22)
        p.drawText(bar, Qt.AlignmentFlag.AlignVCenter, info + HELP)
        p.end()

    # --- input -----------------------------------------------------------------------------
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.RightButton:
            self._drag = e.position()
            return
        if e.button() != Qt.MouseButton.LeftButton:
            return
        cell = self.calib.cell_at(*self._to_img(e.position()))
        if cell is None:
            return
        if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.map = self.map.toggle_los(cell)
        else:
            nxt = CYCLE[(CYCLE.index(self.map.state(cell)) + 1) % len(CYCLE)]
            self.map = self.map.with_state(cell, nxt)
        self._changed()

    def mouseMoveEvent(self, e) -> None:
        if self._drag is not None:
            s = self._view()[0]
            d = e.position() - self._drag
            self._drag = e.position()
            self.calib = cb.translate(self.calib, d.x() / s, d.y() / s)
            self._changed()
        hover = self.calib.cell_at(*self._to_img(e.position()))
        if hover != self.hover:
            self.hover = hover
            self.update()

    def mouseReleaseEvent(self, _e) -> None:
        self._drag = None

    def wheelEvent(self, e) -> None:
        steps = e.angleDelta().y() / 120
        pivot = self._to_img(e.position())
        op = cb.stretch_y if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else cb.scale_about
        self.calib = op(self.calib, 1.02**steps, pivot)
        self._changed()

    def keyPressEvent(self, e) -> None:
        k = e.key()
        arrows = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1),
            Qt.Key.Key_Down: (0, 1),
        }
        if k in arrows:
            self.calib = cb.translate(self.calib, *arrows[k])
            self._changed()
        elif k == Qt.Key.Key_I:
            self.show_ids = not self.show_ids
            self.update()
        elif k == Qt.Key.Key_S and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.save()

    def _changed(self) -> None:
        self.dirty = True
        self._title()
        self.update()

    def save(self) -> None:
        name = self.image_path.name
        if name not in self.map.reference_captures:
            refs = (*self.map.reference_captures, name)
            self.map = replace(self.map, reference_captures=refs)
        save_map(self.map, self.map_path)
        self.ann["calibration"] = cb.to_annotation(self.calib)
        self.ann.setdefault("resolution", [self.img.width(), self.img.height()])
        self.sidecar.write_text(json.dumps(self.ann, indent=1) + "\n", encoding="utf-8")
        self.dirty = False
        self._title()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pi-tool-map", description=__doc__)
    ap.add_argument("capture", type=Path, help="capture PNG of the Harebourg fight")
    ap.add_argument("--map", type=Path, default=None, help="map JSON (default data/maps)")
    args = ap.parse_args(argv)
    app = QApplication(sys.argv[:1])
    try:
        m = load_map(path=args.map)
    except FileNotFoundError:
        m = empty_map()
    w = MapEditor(args.capture, m, args.map)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
