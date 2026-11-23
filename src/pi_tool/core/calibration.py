"""Calibration profiles (V1.3): save per game-area size, rescale to other sizes, manual tweaks.

A profile = Calibration measured on a reference rect (the useful game area, in client
physical px, black bars excluded when known). Other sizes are derived with a scale mode:
- "fit": uniform scale min(w/w0, h/h0), centered (letterboxed game view) — default
- "height" / "width": uniform scale on one axis, centered
- "stretch": independent x/y scale
Which mode Dofus Unity follows must be confirmed on captures (docs/LIMITS.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pi_tool.core.grid import MAP_ROWS, MAP_WIDTH, Calibration, Point

Rect = tuple[float, float, float, float]  # x, y, w, h
ScaleMode = Literal["fit", "height", "width", "stretch"]
SCALE_MODES: tuple[ScaleMode, ...] = ("fit", "height", "width", "stretch")


@dataclass(frozen=True, slots=True)
class Profile:
    rect: Rect  # reference game area the calibration was made on
    calib: Calibration

    @property
    def size_key(self) -> str:
        return f"{round(self.rect[2])}x{round(self.rect[3])}"


def rescale(profile: Profile, rect: Rect, mode: ScaleMode = "fit") -> Calibration:
    """Map a profile measured on profile.rect onto another game-area rect."""
    x0, y0, w0, h0 = profile.rect
    x, y, w, h = rect
    if mode == "stretch":
        sx, sy = w / w0, h / h0
    else:
        s = {"fit": min(w / w0, h / h0), "height": h / h0, "width": w / w0}[mode]
        sx = sy = s
    c0 = (x0 + w0 / 2, y0 + h0 / 2)
    c = (x + w / 2, y + h / 2)
    cal = profile.calib
    return Calibration(
        (c[0] + (cal.origin[0] - c0[0]) * sx, c[1] + (cal.origin[1] - c0[1]) * sy),
        (cal.u[0] * sx, cal.u[1] * sy),
        (cal.v[0] * sx, cal.v[1] * sy),
    )


def pick(profiles: list[Profile], rect: Rect, mode: ScaleMode = "fit") -> Calibration | None:
    """Exact-size profile if any, else the one with the closest aspect ratio, rescaled."""
    if not profiles:
        return None
    w, h = rect[2], rect[3]
    exact = [p for p in profiles if abs(p.rect[2] - w) < 1 and abs(p.rect[3] - h) < 1]
    if exact:
        p = exact[-1]
        dx, dy = rect[0] - p.rect[0], rect[1] - p.rect[1]
        return translate(p.calib, dx, dy)
    best = min(profiles, key=lambda p: abs(p.rect[2] / p.rect[3] - w / h))
    return rescale(best, rect, mode)


def upsert(profiles: list[Profile], new: Profile) -> list[Profile]:
    """Replace the profile of the same size, keep the others."""
    return [p for p in profiles if p.size_key != new.size_key] + [new]


def default_calibration(rect: Rect) -> Calibration:
    """Centered first guess (whole 560-cell grid fits the rect) before manual calibration."""
    x, y, w, h = rect
    # Grid extent: (MAP_WIDTH + .5) cell widths x (MAP_ROWS/2 + .5) cell heights, W = 2H.
    cell_h = 0.9 * min(h / (MAP_ROWS / 2 + 0.5), w / (2 * (MAP_WIDTH + 0.5)))
    cell_w = 2 * cell_h
    left = x + (w - (MAP_WIDTH + 0.5) * cell_w) / 2
    top = y + (h - (MAP_ROWS / 2 + 0.5) * cell_h) / 2
    return Calibration.from_cell_size((left + cell_w / 2, top + cell_h / 2), cell_w, cell_h)


# --- manual adjustments (calibration mode / map editor) ---------------------------------


def translate(cal: Calibration, dx: float, dy: float) -> Calibration:
    return Calibration((cal.origin[0] + dx, cal.origin[1] + dy), cal.u, cal.v)


def scale_about(cal: Calibration, factor: float, pivot: Point) -> Calibration:
    """Uniform zoom keeping `pivot` (screen px) fixed."""
    ox = pivot[0] + (cal.origin[0] - pivot[0]) * factor
    oy = pivot[1] + (cal.origin[1] - pivot[1]) * factor
    return Calibration(
        (ox, oy), (cal.u[0] * factor, cal.u[1] * factor), (cal.v[0] * factor, cal.v[1] * factor)
    )


def stretch_y(cal: Calibration, factor: float, pivot: Point) -> Calibration:
    """Vertical-only scale (iso flattening) keeping `pivot` fixed."""
    oy = pivot[1] + (cal.origin[1] - pivot[1]) * factor
    return Calibration(
        (cal.origin[0], oy), (cal.u[0], cal.u[1] * factor), (cal.v[0], cal.v[1] * factor)
    )


# --- persistence -------------------------------------------------------------------------


def _cal_to_dict(c: Calibration) -> dict:
    return {"origin": list(c.origin), "u": list(c.u), "v": list(c.v)}


def cal_from_dict(d: dict) -> Calibration:
    return Calibration(tuple(d["origin"]), tuple(d["u"]), tuple(d["v"]))  # type: ignore[arg-type]


def save_profiles(profiles: list[Profile], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [{"rect": list(p.rect), **_cal_to_dict(p.calib)} for p in profiles]
    path.write_text(json.dumps({"profiles": data}, indent=1), encoding="utf-8")


def load_profiles(path: Path) -> list[Profile]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Profile(tuple(d["rect"]), cal_from_dict(d)) for d in raw.get("profiles", [])]


# --- annotated captures (tests/fixtures/screens/*.json) ---------------------------------


def from_annotation(ann: dict) -> tuple[Calibration | None, float | None]:
    """Calibration of an annotated capture + max fit residual in px (None if not fitted).

    Uses `calib_points` [[cell, px, py], ...] (preferred: measurable) else `calibration`.
    """
    from pi_tool.core.grid import cell_to_xy

    pts = ann.get("calib_points") or []
    if len(pts) >= 3:
        pairs = [(cell_to_xy(int(c)), (float(px), float(py))) for c, px, py in pts]
        cal = Calibration.fit(pairs)
        res = max(
            ((sx - px) ** 2 + (sy - py) ** 2) ** 0.5
            for xy, (px, py) in pairs
            for sx, sy in [cal.to_screen(*xy)]
        )
        return cal, res
    if "calibration" in ann:
        return cal_from_dict(ann["calibration"]), None
    return None, None


def to_annotation(cal: Calibration) -> dict:
    return _cal_to_dict(cal)
