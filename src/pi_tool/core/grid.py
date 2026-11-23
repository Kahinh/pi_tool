"""Dofus isometric grid: cell id <-> map coords (x, y) <-> screen pixels.

Conventions (see .claude/skills/grid/SKILL.md):
- 560 cells, 14 per row, 40 staggered rows; cell id = row * 14 + col.
- Map coords (x, y): integer axes along the two iso diagonals. A cell is a unit
  square in (x, y), so rotations/symmetries are exact integer ops there.
- Screen = affine(x, y): p = origin + x * u + y * v (set by calibration).
  Ideal Dofus basis: u = (W/2, H/2), v = (W/2, -H/2) with W/H = cell width/height.
"""

from __future__ import annotations

from dataclasses import dataclass

MAP_WIDTH = 14
MAP_ROWS = 40
CELL_COUNT = MAP_WIDTH * MAP_ROWS  # 560

Point = tuple[float, float]
Coord = tuple[int, int]


def cell_to_xy(cell: int) -> Coord:
    """Cell id -> map coords (x, y). Raises ValueError if out of range."""
    if not 0 <= cell < CELL_COUNT:
        raise ValueError(f"cell out of range: {cell}")
    row, col = divmod(cell, MAP_WIDTH)
    half, odd = divmod(row, 2)
    return half + odd + col, col - half


def xy_to_cell(x: int, y: int) -> int | None:
    """Map coords -> cell id, or None if (x, y) is outside the 560-cell map."""
    d = x - y
    if d < 0:
        return None
    col = y + d // 2
    if not 0 <= col < MAP_WIDTH:
        return None
    cell = d * MAP_WIDTH + col
    return cell if cell < CELL_COUNT else None


def cell_row_col(cell: int) -> Coord:
    """Cell id -> (row, col) in the staggered screen layout."""
    return divmod(cell, MAP_WIDTH)


def rotate90(point: Coord, center: Coord, quarter_turns: int) -> Coord:
    """Rotate `point` around `center` by k * 90 degrees in map coords.

    Positive k = (dx, dy) -> (-dy, dx) applied k times. Whether that is clockwise
    on screen depends on the y-axis direction: check against fixtures, never assume.
    """
    dx, dy = point[0] - center[0], point[1] - center[1]
    for _ in range(quarter_turns % 4):
        dx, dy = -dy, dx
    return center[0] + dx, center[1] + dy


def distance(a: Coord, b: Coord) -> int:
    """Dofus cell distance (Manhattan in map coords)."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass(frozen=True, slots=True)
class Calibration:
    """Affine map coords -> client-area pixels (physical pixels, DPI-aware)."""

    origin: Point
    u: Point  # screen delta for x + 1
    v: Point  # screen delta for y + 1

    @classmethod
    def from_cell_size(cls, origin: Point, width: float, height: float) -> Calibration:
        """Ideal iso grid; `origin` = screen center of map coords (0, 0) (cell 0)."""
        return cls(origin, (width / 2, height / 2), (width / 2, -height / 2))

    @classmethod
    def fit(cls, pairs: list[tuple[Coord, Point]]) -> Calibration:
        """Least-squares fit from >= 3 non-collinear ((x, y), (px, py)) pairs."""
        if len(pairs) < 3:
            raise ValueError("need >= 3 reference points")
        # Normal equations for p = o + x*u + y*v, solved per screen axis (3x3).
        rows = [(1.0, float(x), float(y)) for (x, y), _ in pairs]
        ata = [[sum(r[i] * r[j] for r in rows) for j in range(3)] for i in range(3)]
        sol = []
        for axis in range(2):
            atb = [
                sum(r[i] * p[axis] for r, (_, p) in zip(rows, pairs, strict=True)) for i in range(3)
            ]
            sol.append(_solve3(ata, atb))
        (ox, ux, vx), (oy, uy, vy) = sol
        return cls((ox, oy), (ux, uy), (vx, vy))

    def to_screen(self, x: float, y: float) -> Point:
        return (
            self.origin[0] + x * self.u[0] + y * self.v[0],
            self.origin[1] + x * self.u[1] + y * self.v[1],
        )

    def cell_center(self, cell: int) -> Point:
        return self.to_screen(*cell_to_xy(cell))

    def cell_diamond(self, cell: int) -> list[Point]:
        """4 screen corners (top, right, bottom, left for the ideal basis)."""
        x, y = cell_to_xy(cell)
        return [
            self.to_screen(x + dx, y + dy)
            for dx, dy in ((-0.5, 0.5), (0.5, 0.5), (0.5, -0.5), (-0.5, -0.5))
        ]

    def to_map(self, px: float, py: float) -> Point:
        """Inverse affine: screen -> fractional map coords."""
        det = self.u[0] * self.v[1] - self.v[0] * self.u[1]
        if det == 0:
            raise ValueError("degenerate calibration")
        dx, dy = px - self.origin[0], py - self.origin[1]
        return (
            (dx * self.v[1] - self.v[0] * dy) / det,
            (self.u[0] * dy - dx * self.u[1]) / det,
        )

    def cell_at(self, px: float, py: float) -> int | None:
        """Screen pixel -> cell id (None if outside the map). Exact: cells are unit squares."""
        fx, fy = self.to_map(px, py)
        return xy_to_cell(round(fx), round(fy))


def _solve3(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting for a 3x3 system."""
    m = [[*row, rhs] for row, rhs in zip(a, b, strict=True)]
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            raise ValueError("reference points are collinear")
        m[c], m[p] = m[p], m[c]
        for r in range(3):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [vr - f * vc for vr, vc in zip(m[r], m[c], strict=True)]
    return [m[i][3] / m[i][i] for i in range(3)]
