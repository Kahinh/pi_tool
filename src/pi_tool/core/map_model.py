"""Harebourg map data (V1.1): which cells are walkable / targetable / block LoS.

Data lives in data/maps/harebourg.json; this module only loads and queries it.
Walkable and targetable are DISTINCT properties (issue #4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pi_tool.core.grid import CELL_COUNT

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "maps"


@dataclass(frozen=True, slots=True)
class MapModel:
    name: str
    validated: bool  # True only once every cell was checked on a reference capture
    outside: frozenset[int]  # not part of the arena (void, borders)
    non_walkable: frozenset[int]
    non_targetable: frozenset[int]
    blocks_los: frozenset[int]

    def in_arena(self, cell: int) -> bool:
        return 0 <= cell < CELL_COUNT and cell not in self.outside

    def walkable(self, cell: int) -> bool:
        return self.in_arena(cell) and cell not in self.non_walkable

    def targetable(self, cell: int) -> bool:
        return self.in_arena(cell) and cell not in self.non_targetable


def load_map(name: str = "harebourg", path: Path | None = None) -> MapModel:
    raw = json.loads((path or DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))
    sets = {
        k: frozenset(raw.get(k, ()))
        for k in ("outside", "non_walkable", "non_targetable", "blocks_los")
    }
    bad = {c for s in sets.values() for c in s if not 0 <= c < CELL_COUNT}
    if bad:
        raise ValueError(f"invalid cell ids in {name}: {sorted(bad)[:10]}")
    return MapModel(name=raw["name"], validated=bool(raw.get("validated")), **sets)
