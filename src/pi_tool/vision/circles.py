"""Team circles under fighters (V2.2): blue = allies, red = enemies.

Calibration-driven: instead of searching blobs anywhere, every candidate cell is tested
against the ring we expect there (the circle inscribed in the cell, seen in iso). We
sample pixels along a few radii and count the fraction of angles hitting the team colour:
- robust to occlusion by the character sprite (half a ring is still ~50 % coverage);
- projection to a cell is exact by construction (no centre estimate to round);
- false positives: small blobs/lines hit few angles; large coloured areas (spell zones,
  UI) are rejected because they also cover a control ring just outside the circle.
Colour ranges / radii are first guesses until checked on real captures (docs/LIMITS.md).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import cv2
import numpy as np

from pi_tool.core.grid import Calibration, cell_to_xy

HsvRange = tuple[tuple[int, int, int], tuple[int, int, int]]  # OpenCV HSV, H in 0..179
TEAMS = ("ally", "enemy")


def _default_hsv() -> dict[str, tuple[HsvRange, ...]]:
    return {
        "ally": (((95, 110, 90), (130, 255, 255)),),
        "enemy": (((0, 120, 90), (8, 255, 255)), ((170, 120, 90), (179, 255, 255))),
    }


@dataclass(frozen=True)
class CircleParams:
    radii: tuple[float, ...] = (0.34, 0.42, 0.5)  # map units: a cell is a 1x1 square
    n_angles: int = 48
    min_coverage: float = 0.42  # fraction of angles hitting the colour
    outer_radius: float = 0.72  # control ring between the circle and the neighbours' circles
    max_outer: float = 0.35  # above => large coloured area, not a ring
    min_contrast: float = 0.3  # ring coverage - control coverage (zone edges have ~0)
    neighbour_ratio: float = 0.6  # adjacent weaker candidate below ratio*best is dropped
    hsv: dict[str, tuple[HsvRange, ...]] = field(default_factory=_default_hsv)


@dataclass(frozen=True, slots=True)
class Detection:
    cell: int
    team: str  # "ally" | "enemy"
    score: float  # ring coverage 0..1


def _sample_hsv(img: np.ndarray, cal: Calibration, xy: np.ndarray, radii, unit):
    """HSV values at map points xy[c] + r*unit[a] -> (C, R, A, 3) uint8 + validity mask."""
    r = np.asarray(radii, dtype=np.float64)
    pts = xy[:, None, None, :] + r[None, :, None, None] * unit[None, None, :, :]
    px = cal.origin[0] + pts[..., 0] * cal.u[0] + pts[..., 1] * cal.v[0]
    py = cal.origin[1] + pts[..., 0] * cal.u[1] + pts[..., 1] * cal.v[1]
    ix, iy = np.rint(px).astype(np.int64), np.rint(py).astype(np.int64)
    h, w = img.shape[:2]
    valid = (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
    vals = img[np.clip(iy, 0, h - 1), np.clip(ix, 0, w - 1)]
    hsv = cv2.cvtColor(vals.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(vals.shape)
    return hsv, valid


def _hits(hsv: np.ndarray, valid: np.ndarray, ranges: tuple[HsvRange, ...]) -> np.ndarray:
    hit = np.zeros(hsv.shape[:-1], dtype=bool)
    for lo, hi in ranges:
        hit |= np.all((hsv >= np.array(lo)) & (hsv <= np.array(hi)), axis=-1)
    return hit & valid


def ring_scores(
    img: np.ndarray, cal: Calibration, cells: Iterable[int], p: CircleParams = CircleParams()
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Per team: (cells, ring coverage, outer coverage) arrays. Exposed for debug/eval."""
    cell_arr = np.fromiter(cells, dtype=np.int64)
    if cell_arr.size == 0:
        return {t: (cell_arr, np.zeros(0), np.zeros(0)) for t in TEAMS}
    xy = np.array([cell_to_xy(int(c)) for c in cell_arr], dtype=np.float64)
    ang = np.linspace(0.0, 2 * np.pi, p.n_angles, endpoint=False)
    unit = np.stack([np.cos(ang), np.sin(ang)], axis=1)
    ring_hsv, ring_ok = _sample_hsv(img, cal, xy, p.radii, unit)
    out_hsv, out_ok = _sample_hsv(img, cal, xy, (p.outer_radius,), unit)
    res = {}
    for team in TEAMS:
        ranges = p.hsv[team]
        cov = _hits(ring_hsv, ring_ok, ranges).any(axis=1).mean(axis=1)
        outer = _hits(out_hsv, out_ok, ranges)[:, 0, :].mean(axis=1)
        res[team] = (cell_arr, cov, outer)
    return res


def detect_circles(
    img: np.ndarray, cal: Calibration, cells: Iterable[int], p: CircleParams = CircleParams()
) -> list[Detection]:
    """Fighters standing on `cells` (typically the walkable arena cells), best first."""
    best: dict[int, Detection] = {}
    for team, (cell_arr, cov, outer) in ring_scores(img, cal, cells, p).items():
        ok = (cov >= p.min_coverage) & (outer <= p.max_outer) & (cov - outer >= p.min_contrast)
        for c, s in zip(cell_arr[ok].tolist(), cov[ok].tolist(), strict=True):
            if c not in best or s > best[c].score:
                best[c] = Detection(c, team, float(s))
    kept: list[Detection] = []
    for d in sorted(best.values(), key=lambda d: -d.score):
        x, y = cell_to_xy(d.cell)
        if any(
            max(abs(x - kx), abs(y - ky)) <= 1 and d.score < p.neighbour_ratio * k.score
            for k in kept
            for kx, ky in [cell_to_xy(k.cell)]
        ):
            continue  # bleed of a stronger neighbouring ring
        kept.append(d)
    return kept


def split_teams(dets: list[Detection]) -> tuple[frozenset[int], frozenset[int]]:
    return (
        frozenset(d.cell for d in dets if d.team == "ally"),
        frozenset(d.cell for d in dets if d.team == "enemy"),
    )
