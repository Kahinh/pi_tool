"""HP percentage read in the life heart (V2.4). Reads ONLY the "85 %" text, never absolute HP.

Template OCR, no external engine: the text (bright, unsaturated) is isolated from the red
heart, split into glyphs, each scaled to a fixed height (=> independent of UI size) and
matched against glyph templates learnt from the user's own annotated captures
(`./dev digits`). Every doubt => no value (`HpRead.value is None` + reason):
unknown glyph, low score, ambiguous match, malformed text, value outside 0..100.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

GLYPHS = "0123456789%"
SIDE = 24  # normalised glyph box (px)
DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "hp_digits"

Roi = tuple[float, float, float, float]  # x, y, w, h as fractions of the client area


@dataclass(frozen=True)
class OcrParams:
    v_min: int = 170  # text = bright...
    s_max: int = 90  # ...and unsaturated (the heart is saturated red)
    min_height: float = 0.3  # glyph height >= 30 % of the tallest one
    min_score: float = 0.7  # normalised correlation
    min_margin: float = 0.06  # best - second best


@dataclass(frozen=True)
class Templates:
    glyphs: dict[str, np.ndarray]  # label -> SIDE x SIDE float32
    validated: bool = False  # True only after `./dev digits` reproduced every fixture

    @property
    def complete(self) -> bool:
        return all(d in self.glyphs for d in "0123456789")


@dataclass(frozen=True, slots=True)
class HpRead:
    value: int | None
    text: str = ""
    score: float = 0.0
    reason: str | None = None  # why value is None


def crop_roi(img: np.ndarray, roi: Roi) -> np.ndarray | None:
    h, w = img.shape[:2]
    x0, y0 = round(roi[0] * w), round(roi[1] * h)
    x1, y1 = round((roi[0] + roi[2]) * w), round((roi[1] + roi[3]) * h)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    return img[y0:y1, x0:x1] if x1 - x0 >= 4 and y1 - y0 >= 4 else None


def text_mask(roi: np.ndarray, p: OcrParams = OcrParams()) -> np.ndarray:
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    return ((hsv[..., 2] >= p.v_min) & (hsv[..., 1] <= p.s_max)).astype(np.uint8)


def _normalise(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    s = SIDE / max(h, w)
    g = cv2.resize(mask.astype(np.float32), (max(1, round(w * s)), max(1, round(h * s))))
    out = np.zeros((SIDE, SIDE), np.float32)
    gh, gw = g.shape
    y, x = (SIDE - gh) // 2, (SIDE - gw) // 2
    out[y : y + gh, x : x + gw] = g
    return out


def segment(roi: np.ndarray, p: OcrParams = OcrParams()) -> list[np.ndarray]:
    """Glyphs left to right, normalised. Parts overlapping in x (e.g. '%') are merged."""
    mask = text_mask(roi, p)
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes = [tuple(int(v) for v in stats[i, :4]) for i in range(1, n) if stats[i, 4] >= 3]
    if not boxes:
        return []
    tallest = max(b[3] for b in boxes)
    groups: list[list[int]] = []  # [x0, y0, x1, y1]
    for x, y, w, h in sorted(boxes):
        if groups and x < groups[-1][2] - 1:  # overlaps the previous glyph in x
            g = groups[-1]
            g[:] = [min(g[0], x), min(g[1], y), max(g[2], x + w), max(g[3], y + h)]
        else:
            groups.append([x, y, x + w, y + h])
    return [
        _normalise(mask[y0:y1, x0:x1])
        for x0, y0, x1, y1 in groups
        if y1 - y0 >= p.min_height * tallest
    ]


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a - a.mean(), b - b.mean()
    den = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / den) if den > 1e-9 else 0.0


def classify(glyph: np.ndarray, t: Templates) -> tuple[str, float, float]:
    """(label, score, margin to the second best label)."""
    scores = sorted(((_corr(glyph, tpl), lab) for lab, tpl in t.glyphs.items()), reverse=True)
    if not scores:
        return "?", 0.0, 0.0
    second = scores[1][0] if len(scores) > 1 else -1.0
    return scores[0][1], scores[0][0], scores[0][0] - second


def read_hp(roi: np.ndarray | None, t: Templates, p: OcrParams = OcrParams()) -> HpRead:
    if roi is None or roi.size == 0:
        return HpRead(None, reason="zone PV hors image")
    if not t.complete:
        return HpRead(None, reason="modèles de chiffres incomplets")
    glyphs = segment(roi, p)
    if not glyphs:
        return HpRead(None, reason="aucun texte")
    labels, worst = [], 1.0
    for g in glyphs:
        lab, score, margin = classify(g, t)
        worst = min(worst, score)
        if score < p.min_score or margin < p.min_margin:
            return HpRead(None, "".join(labels) + "?", worst, "lecture incertaine")
        labels.append(lab)
    text = "".join(labels)
    digits = text[:-1] if text.endswith("%") else text
    if not digits or not digits.isdigit() or len(digits) > 3:
        return HpRead(None, text, worst, "texte mal formé")
    if len(digits) > 1 and digits[0] == "0":
        return HpRead(None, text, worst, "zéro initial")
    value = int(digits)
    if value > 100:
        return HpRead(None, text, worst, "hors 0–100")
    return HpRead(value, text, worst)


# --- templates (learnt from annotated captures) ----------------------------------------
def learn(roi: np.ndarray, text: str, p: OcrParams = OcrParams()) -> dict[str, np.ndarray]:
    """Glyph samples from a ROI whose content is known (e.g. '85%'). Raises on mismatch."""
    text = text.replace(" ", "")
    glyphs = segment(roi, p)
    if len(glyphs) != len(text):
        raise ValueError(f"{len(glyphs)} glyphes trouvés pour « {text} »")
    return dict(zip(text, glyphs, strict=True))


def merge(samples: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    """Average the samples of each glyph."""
    acc: dict[str, list[np.ndarray]] = {}
    for s in samples:
        for k, g in s.items():
            acc.setdefault(k, []).append(g)
    return {k: np.mean(v, axis=0).astype(np.float32) for k, v in acc.items()}


def save_templates(t: Templates, d: Path = DATA_DIR) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for k, g in t.glyphs.items():
        name = "pct" if k == "%" else k
        cv2.imwrite(str(d / f"{name}.png"), np.clip(g * 255, 0, 255).astype(np.uint8))
    meta = {"validated": t.validated, "glyphs": sorted(t.glyphs), "side": SIDE}
    (d / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def load_templates(d: Path = DATA_DIR) -> Templates:
    meta_p = d / "meta.json"
    if not meta_p.exists():
        return Templates({})
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    glyphs = {}
    for k in meta.get("glyphs", []):
        img = cv2.imread(str(d / f"{'pct' if k == '%' else k}.png"), cv2.IMREAD_GRAYSCALE)
        if img is not None and img.shape == (SIDE, SIDE):
            glyphs[k] = img.astype(np.float32) / 255
    return Templates(glyphs, bool(meta.get("validated", False)))
