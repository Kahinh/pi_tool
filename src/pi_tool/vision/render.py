"""Draw a core.scene onto a BGR image (debug renders, comparison with real captures)."""

from __future__ import annotations

import cv2
import numpy as np

from pi_tool.core.scene import Shape


def draw_scene(img: np.ndarray, shapes: list[Shape]) -> np.ndarray:
    """Alpha-blend shapes onto a copy of `img` (BGR uint8)."""
    out = img.copy()
    for s in shapes:
        pts = np.round(np.array(s.points, dtype=np.float64)).astype(np.int32)
        for color, thick in ((s.fill, -1), (s.outline, max(1, round(s.width)))):
            if color is None or color[3] == 0:
                continue
            layer = out.copy()
            bgr = (color[2], color[1], color[0])
            if thick < 0:
                cv2.fillConvexPoly(layer, pts, bgr, lineType=cv2.LINE_AA)
            else:
                cv2.polylines(layer, [pts], True, bgr, thick, lineType=cv2.LINE_AA)
            a = color[3] / 255
            cv2.addWeighted(layer, a, out, 1 - a, 0, dst=out)
        if s.label and s.center:
            org = (round(s.center[0]) - 4 * len(s.label), round(s.center[1]) + 4)
            cv2.putText(out, s.label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
    return out


def content_rect(img: np.ndarray, threshold: int = 12) -> tuple[int, int, int, int]:
    """Bounding rect (x, y, w, h) of the non-black area: strips letterbox/pillarbox bars."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    rows = np.where(gray.max(axis=1) > threshold)[0]
    cols = np.where(gray.max(axis=0) > threshold)[0]
    if rows.size == 0 or cols.size == 0:
        return 0, 0, gray.shape[1], gray.shape[0]
    return int(cols[0]), int(rows[0]), int(cols[-1] - cols[0] + 1), int(rows[-1] - rows[0] + 1)
