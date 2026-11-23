"""Harebourg map data (V1.1): which cells are walkable / targetable / block LoS.

Data lives in data/maps/harebourg.json. Walkable and targetable are DISTINCT (issue #4):
a hole is non-walkable but targetable; some cells are walkable but not targetable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from pi_tool.core.grid import CELL_COUNT

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "maps"
_SETS = ("outside", "non_walkable", "non_targetable", "blocks_los")


class CellState(Enum):
    """Editor-level category; maps onto the underlying sets."""

    NORMAL = "normal"
    OBSTACLE = "obstacle"  # non-walkable + non-targetable + blocks LoS (rock, pillar)
    NON_WALKABLE = "non_walkable"  # e.g. hole: can't walk, can target
    NON_TARGETABLE = "non_targetable"  # can walk, can't target
    OUTSIDE = "outside"  # not part of the arena


CYCLE = list(CellState)


@dataclass(frozen=True, slots=True)
class MapModel:
    name: str
    validated: bool  # True only once every cell was checked on a reference capture
    outside: frozenset[int]  # not part of the arena (void, borders)
    non_walkable: frozenset[int]
    non_targetable: frozenset[int]
    blocks_los: frozenset[int]
    reference_captures: tuple[str, ...] = ()

    def in_arena(self, cell: int) -> bool:
        return 0 <= cell < CELL_COUNT and cell not in self.outside

    def walkable(self, cell: int) -> bool:
        return self.in_arena(cell) and cell not in self.non_walkable

    def targetable(self, cell: int) -> bool:
        return self.in_arena(cell) and cell not in self.non_targetable

    def state(self, cell: int) -> CellState:
        if cell in self.outside:
            return CellState.OUTSIDE
        nw, nt = cell in self.non_walkable, cell in self.non_targetable
        if nw and nt:
            return CellState.OBSTACLE
        if nw:
            return CellState.NON_WALKABLE
        return CellState.NON_TARGETABLE if nt else CellState.NORMAL

    def with_state(self, cell: int, state: CellState) -> MapModel:
        """New model with `cell` set to `state` (LoS follows: obstacle blocks, others keep)."""
        sets = {k: set(getattr(self, k)) for k in _SETS}
        for k in ("outside", "non_walkable", "non_targetable"):
            sets[k].discard(cell)
        if state is CellState.OUTSIDE:
            sets["outside"].add(cell)
            sets["blocks_los"].discard(cell)
        if state in (CellState.OBSTACLE, CellState.NON_WALKABLE):
            sets["non_walkable"].add(cell)
        if state in (CellState.OBSTACLE, CellState.NON_TARGETABLE):
            sets["non_targetable"].add(cell)
        if state is CellState.OBSTACLE:
            sets["blocks_los"].add(cell)
        return replace(self, **{k: frozenset(v) for k, v in sets.items()})

    def toggle_los(self, cell: int) -> MapModel:
        return replace(self, blocks_los=self.blocks_los ^ {cell})


def empty_map(name: str = "harebourg") -> MapModel:
    e: frozenset[int] = frozenset()
    return MapModel(name, False, e, e, e, e)


def load_map(name: str = "harebourg", path: Path | None = None) -> MapModel:
    raw = json.loads((path or DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))
    sets = {k: frozenset(raw.get(k, ())) for k in _SETS}
    bad = {c for s in sets.values() for c in s if not 0 <= c < CELL_COUNT}
    if bad:
        raise ValueError(f"invalid cell ids in {name}: {sorted(bad)[:10]}")
    return MapModel(
        name=raw["name"],
        validated=bool(raw.get("validated")),
        reference_captures=tuple(raw.get("reference_captures", ())),
        **sets,
    )


def save_map(m: MapModel, path: Path | None = None) -> Path:
    path = path or DATA_DIR / f"{m.name}.json"
    data = {
        "name": m.name,
        "validated": m.validated,
        "reference_captures": list(m.reference_captures),
        **{k: sorted(getattr(m, k)) for k in _SETS},
    }
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return path
