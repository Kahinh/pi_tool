"""Renderer-agnostic scene: list of shapes in screen px. Drawn by Qt (overlay) and cv2 (debug).

V1.4 grid: one diamond per arena cell; fill encodes the cell category, optional ids.
"""

from __future__ import annotations

from dataclasses import dataclass

from pi_tool.core.grid import CELL_COUNT, Calibration, Point
from pi_tool.core.map_model import CellState, MapModel

RGBA = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class Shape:
    points: tuple[Point, ...]
    fill: RGBA | None = None
    outline: RGBA | None = None
    width: float = 1.0
    label: str | None = None
    center: Point | None = None


@dataclass(frozen=True, slots=True)
class GridStyle:
    opacity: float = 1.0  # multiplies every alpha
    show_ids: bool = False
    show_outside: bool = False  # editor: draw outside cells too


# Distinct, colour-blind-friendly categories (Okabe-Ito).
FILL: dict[CellState, RGBA | None] = {
    CellState.NORMAL: None,
    CellState.OBSTACLE: (213, 94, 0, 140),  # vermillion
    CellState.NON_WALKABLE: (0, 114, 178, 120),  # blue: hole, still targetable
    CellState.NON_TARGETABLE: (240, 228, 66, 120),  # yellow
    CellState.OUTSIDE: (60, 60, 60, 90),
}
OUTLINE: RGBA = (255, 255, 255, 110)
LOS_OUTLINE: RGBA = (0, 0, 0, 220)


def _a(c: RGBA | None, k: float) -> RGBA | None:
    return None if c is None else (c[0], c[1], c[2], round(c[3] * k))


def grid_scene(m: MapModel, cal: Calibration, style: GridStyle = GridStyle()) -> list[Shape]:
    shapes = []
    for cell in range(CELL_COUNT):
        st = m.state(cell)
        if st is CellState.OUTSIDE and not style.show_outside:
            continue
        los = cell in m.blocks_los
        shapes.append(
            Shape(
                points=tuple(cal.cell_diamond(cell)),
                fill=_a(FILL[st], style.opacity),
                outline=_a(LOS_OUTLINE if los else OUTLINE, style.opacity),
                width=2.0 if los else 1.0,
                label=str(cell) if style.show_ids else None,
                center=cal.cell_center(cell),
            )
        )
    return shapes
