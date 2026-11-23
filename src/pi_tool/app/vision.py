"""One capture -> one core.combat.Frame (V2.2 circles + V2.4 HP), with the raw OCR for debug."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from pi_tool.core.combat import Frame
from pi_tool.core.grid import CELL_COUNT, Calibration
from pi_tool.core.map_model import MapModel
from pi_tool.vision import hp_ocr
from pi_tool.vision.circles import CircleParams, detect_circles, split_teams


@dataclass
class Analyzer:
    game_map: MapModel
    templates: hp_ocr.Templates
    circles: CircleParams = field(default_factory=CircleParams)
    last_hp: hp_ocr.HpRead | None = None

    @classmethod
    def default(cls, game_map: MapModel) -> Analyzer:
        return cls(game_map, hp_ocr.load_templates())

    def analyze(self, img: np.ndarray | None, cal: Calibration, hp_roi, t: float) -> Frame:
        if img is None:
            self.last_hp = None
            return Frame(t, ok=False)
        cells = [c for c in range(CELL_COUNT) if self.game_map.walkable(c)]
        allies, enemies = split_teams(detect_circles(img, cal, cells, self.circles))
        hp = None
        if hp_roi:
            self.last_hp = hp_ocr.read_hp(hp_ocr.crop_roi(img, tuple(hp_roi)), self.templates)
            # Unvalidated templates: shown in debug only, never fed downstream.
            hp = self.last_hp.value if self.templates.validated else None
        else:
            self.last_hp = None
        return Frame(t, allies, enemies, hp_pct=hp)

    def hp_debug(self) -> str:
        r = self.last_hp
        if r is None:
            return "OCR PV : zone non calibrée (Ctrl+Alt+H)"
        txt = f"OCR PV : « {r.text} » " + (f"= {r.value}" if r.value is not None else r.reason)
        return txt + ("" if self.templates.validated else " (modèles non validés: ./dev digits)")
