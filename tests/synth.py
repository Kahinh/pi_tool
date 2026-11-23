"""Synthetic game-like frames for vision tests (no real captures needed).

Not a model of Dofus art: textured floor + iso team rings + occluders + distractors,
enough to exercise the geometry and the rejection logic.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from pi_tool.core.calibration import default_calibration
from pi_tool.core.grid import Calibration

BLUE = (220, 120, 30)  # BGR
RED = (40, 40, 220)


def floor(w: int, h: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = np.zeros((h, w, 3), np.uint8)
    base[:] = (70, 95, 85)
    noise = rng.integers(-25, 25, (h // 8 + 1, w // 8 + 1, 3))
    noise = cv2.resize(noise.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    return np.clip(base + noise, 0, 255).astype(np.uint8)


def cal_for(w: int, h: int) -> Calibration:
    """Whole grid centred in a w x h client (same first guess as the app)."""
    return default_calibration((0.0, 0.0, float(w), float(h)))


def ring(img, cal: Calibration, cell: int, color, r: float = 0.42, thick: float = 0.07):
    cx, cy = cal.cell_center(cell)
    ax = (r * abs(cal.u[0]) * math.sqrt(2), r * abs(cal.u[1]) * math.sqrt(2))
    t = max(2, round(thick * abs(cal.u[0]) * 2))
    cv2.ellipse(img, (round(cx), round(cy)), (round(ax[0]), round(ax[1])), 0, 0, 360, color, t)


def sprite(img, cal: Calibration, cell: int, seed: int = 1):
    """Character body standing on the cell: hides the back half of its ring."""
    cx, cy = cal.cell_center(cell)
    cw = abs(cal.u[0]) * 2
    rng = np.random.default_rng(seed)
    x0, x1 = round(cx - cw * 0.25), round(cx + cw * 0.25)
    y0, y1 = round(cy - cw * 1.2), round(cy)
    patch = rng.integers(30, 140, (max(1, y1 - y0), max(1, x1 - x0), 3)).astype(np.uint8)
    img[y0:y1, x0:x1] = cv2.blur(patch, (5, 5))[: img[y0:y1, x0:x1].shape[0]]


def heart(text: str, scale: float = 1.0, seed: int = 0) -> np.ndarray:
    """Red heart with white outlined text, like the HP heart (any UI scale)."""
    s = round(70 * scale)
    img = floor(s * 2, s * 2, seed)
    c = s
    cv2.circle(img, (c - s // 3, c - s // 5), s // 2, (30, 30, 200), -1)
    cv2.circle(img, (c + s // 3, c - s // 5), s // 2, (30, 30, 200), -1)
    pts = np.array([[c - s, c - s // 6], [c + s, c - s // 6], [c, c + s - 4]], np.int32)
    cv2.fillConvexPoly(img, pts, (30, 30, 200))
    fs = 0.9 * scale
    th = max(1, round(2 * scale))
    (tw, tht), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, th)
    org = (c - tw // 2, c + tht // 2)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, fs, (0, 0, 0), th + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, fs, (245, 245, 245), th, cv2.LINE_AA)
    return img
