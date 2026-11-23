"""PI engine (V3.1/V3.2) — pure, no I/O besides loading the rule file.

The real rule is NOT known yet (issue #13). The engine refuses to compute until
data/pi_rules.json is marked validated with evidence (see skill `pi-rules`).
Never display a guessed target.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pi_tool.core.grid import Coord

RULES_PATH = Path(__file__).resolve().parents[3] / "data" / "pi_rules.json"


class RuleNotValidatedError(RuntimeError):
    """Raised when computing with rules that are not validated by evidence."""


class TargetStatus(Enum):
    OK = "ok"
    OFF_MAP = "off_map"  # inverse transform lands outside the map
    NOT_TARGETABLE = "not_targetable"  # geometric: obstacle / non-targetable cell
    SAME_AS_ENEMY = "same_as_enemy"
    # Range and line of sight are deliberately NOT evaluated (issue #16).


@dataclass(frozen=True, slots=True)
class TargetResult:
    enemy_cell: int
    target_cell: int | None
    status: TargetStatus


@dataclass(frozen=True, slots=True)
class Rules:
    validated: bool
    raw: dict

    @classmethod
    def load(cls, path: Path = RULES_PATH) -> Rules:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(validated=bool(raw.get("validated")), raw=raw)


def target_cell(player: Coord, enemy: Coord, hp_pct: int, rules: Rules) -> TargetResult:
    """Cell to aim at so that the PI-transformed hit lands on `enemy`. (V3.2)"""
    if not rules.validated:
        raise RuleNotValidatedError("PI rules not validated — see docs/research/pi_rules.md")
    if not 0 <= hp_pct <= 100:
        raise ValueError(f"hp_pct out of range: {hp_pct}")
    raise NotImplementedError("V3.2: implement from validated rules")
