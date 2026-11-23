"""Combat state from successive vision frames (V2.3 player, V2.5 refresh + reliability).

Pure logic: a `Frame` is what vision saw in one capture; `CombatTracker` filters flicker
(k-of-n confirmation), follows the controlled player across moves, confirms HP reads,
timestamps everything and hides what is stale or uncertain.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

PLAYER_SOURCES = ("manual", "tracked", "single", "cue")


@dataclass(frozen=True, slots=True)
class Frame:
    """One analysed capture. `ok=False` = capture failed/unusable (counts as no data)."""

    t: float
    allies: frozenset[int] = frozenset()
    enemies: frozenset[int] = frozenset()
    hp_pct: int | None = None  # validated 0..100 read, None if rejected/absent
    player_cue: int | None = None  # validated visual cue only (V2.3); None otherwise
    ok: bool = True


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    window: int = 3  # frames kept
    confirm: int = 2  # a cell must be seen in >= confirm of the last `window` frames
    hp_confirm: int = 2  # identical consecutive reads before a new HP value is accepted
    max_age: float = 1.5  # s without a usable frame/read => stale => hidden
    min_confidence: float = 0.6  # below => `reliable` is False


@dataclass(frozen=True, slots=True)
class CombatState:
    t: float | None = None  # time of the last usable frame
    allies: frozenset[int] = frozenset()
    enemies: frozenset[int] = frozenset()
    player: int | None = None
    player_source: str | None = None
    hp_pct: int | None = None
    hp_t: float | None = None
    confidence: float = 0.0  # 0..1, stability of the confirmed sets over the window
    reliable: bool = False

    def age(self, now: float) -> float | None:
        return None if self.t is None else now - self.t


EMPTY = CombatState()


@dataclass
class CombatTracker:
    cfg: TrackerConfig = field(default_factory=TrackerConfig)

    def __post_init__(self) -> None:
        self._frames: deque[Frame] = deque(maxlen=self.cfg.window)
        self._allies: frozenset[int] = frozenset()
        self._enemies: frozenset[int] = frozenset()
        self._player: int | None = None
        self._player_src: str | None = None
        self._hp: int | None = None
        self._hp_t: float | None = None
        self._hp_run: tuple[int | None, int] = (None, 0)  # (value, consecutive count)
        self._t: float | None = None

    # --- input ---------------------------------------------------------------------------
    def set_manual_player(self, cell: int | None) -> None:
        """Fallback selection by the user (overlay pick mode). None = clear."""
        self._player = cell
        self._player_src = "manual" if cell is not None else None

    def reset(self) -> None:
        self.__post_init__()

    def update(self, f: Frame) -> None:
        if not f.ok:
            return  # no new information; staleness handles the rest
        self._frames.append(f)
        self._t = f.t
        prev_allies = self._allies
        self._allies = self._confirmed("allies")
        self._enemies = self._confirmed("enemies") - self._allies
        self._update_player(prev_allies, f.player_cue)
        self._update_hp(f)

    def _confirmed(self, team: str) -> frozenset[int]:
        counts: dict[int, int] = {}
        for fr in self._frames:
            for c in getattr(fr, team):
                counts[c] = counts.get(c, 0) + 1
        need = min(self.cfg.confirm, len(self._frames))
        return frozenset(c for c, n in counts.items() if n >= need)

    def _update_player(self, prev: frozenset[int], cue: int | None) -> None:
        allies, p = self._allies, self._player
        if cue is not None and cue in allies:
            self._player, self._player_src = cue, "cue"
            return
        if p is not None and (p in allies or not allies):
            return  # still there, or nothing visible (state() hides it meanwhile)
        if p is not None:
            appeared, vanished = allies - prev, prev - allies
            if vanished == {p} and len(appeared) == 1:  # unambiguous move
                self._player = next(iter(appeared))
                if self._player_src != "manual":
                    self._player_src = "tracked"
                return
            if self._player_src != "manual":  # ambiguous: drop guesses, keep manual anchor
                self._player = self._player_src = None
        if len(allies) == 1:
            self._player, self._player_src = next(iter(allies)), "single"

    def _update_hp(self, f: Frame) -> None:
        v = f.hp_pct
        if v is None or not 0 <= v <= 100:
            self._hp_run = (None, 0)
            return
        run_v, n = self._hp_run
        n = n + 1 if v == run_v else 1
        self._hp_run = (v, n)
        if v == self._hp:
            self._hp_t = f.t
        elif n >= self.cfg.hp_confirm:
            self._hp, self._hp_t = v, f.t

    # --- output --------------------------------------------------------------------------
    def confidence(self) -> float:
        if not self._frames:
            return 0.0
        fill = len(self._frames) / self.cfg.window
        same = sum(
            1 for fr in self._frames if fr.allies == self._allies and fr.enemies == self._enemies
        )
        return fill * same / len(self._frames)

    def state(self, now: float) -> CombatState:
        """Current state; anything stale (older than max_age) is hidden."""
        if self._t is None or now - self._t > self.cfg.max_age:
            return CombatState(t=self._t)
        hp_fresh = self._hp_t is not None and now - self._hp_t <= self.cfg.max_age
        player = self._player if self._player in self._allies else None
        conf = self.confidence()
        return CombatState(
            t=self._t,
            allies=self._allies,
            enemies=self._enemies,
            player=player,
            player_source=self._player_src if player is not None else None,
            hp_pct=self._hp if hp_fresh else None,
            hp_t=self._hp_t if hp_fresh else None,
            confidence=conf,
            reliable=conf >= self.cfg.min_confidence,
        )


def status_line(st: CombatState, now: float) -> str:
    """Debug banner (V2.5): positions summary, HP read, confidence, age."""
    if st.t is None:
        return "Vision : aucune capture exploitable"
    age = now - st.t
    if not st.allies and not st.enemies and st.hp_pct is None and st.confidence == 0:
        return f"Vision : données périmées ({age:.1f} s) — masquées"
    hp = f"{st.hp_pct} %" if st.hp_pct is not None else "?"
    who = f"{st.player} ({st.player_source})" if st.player is not None else "?"
    flag = "" if st.reliable else " · INCERTAIN"
    return (
        f"PV {hp} · joueur {who} · alliés {len(st.allies)} · ennemis {len(st.enemies)}"
        f" · confiance {st.confidence:.0%} · {age:.1f} s{flag}"
    )
