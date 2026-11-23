"""V2.3 / V2.5: combat tracker transitions (flicker, move, death, HP, staleness, player)."""

import pytest

from pi_tool.core.combat import CombatTracker, Frame, TrackerConfig, status_line


def F(t, allies=(), enemies=(), hp=None, cue=None, ok=True):
    return Frame(t, frozenset(allies), frozenset(enemies), hp, cue, ok)


def feed(tr, frames):
    for f in frames:
        tr.update(f)
    return tr.state(frames[-1].t)


def test_k_of_n_filters_flicker_and_false_positives():
    tr = CombatTracker()
    st = feed(tr, [F(0, [10], [50]), F(0.25, [10], [50, 99]), F(0.5, [10], [50])])
    assert st.allies == {10} and st.enemies == {50}  # 99 seen once: rejected
    st = feed(tr, [F(0.75, [10], [])])  # enemy occluded for one frame: kept
    assert st.enemies == {50}


def test_move_and_death_after_confirmation():
    tr = CombatTracker()
    feed(tr, [F(t, [10], [50, 60]) for t in (0, 0.25, 0.5)])
    st = feed(tr, [F(0.75, [11], [50])])
    assert st.allies == {10} and 60 in st.enemies  # one frame isn't enough
    st = feed(tr, [F(1.0, [11], [50])])
    assert st.allies == {11} and st.enemies == {50}


def test_stale_state_is_hidden():
    tr = CombatTracker(TrackerConfig(max_age=1.0))
    feed(tr, [F(t, [10], [50], hp=80) for t in (0, 0.25)])
    assert tr.state(0.5).enemies == {50}
    tr.update(F(0.5, ok=False))  # capture failure: no refresh
    st = tr.state(1.6)
    assert not st.allies and not st.enemies and st.hp_pct is None and not st.reliable
    assert "périmées" in status_line(st, 1.6)


def test_hp_needs_confirmation_and_expires():
    tr = CombatTracker(TrackerConfig(max_age=1.0))
    st = feed(tr, [F(0, [10], hp=85)])
    assert st.hp_pct is None  # single read not trusted
    st = feed(tr, [F(0.25, [10], hp=85)])
    assert st.hp_pct == 85 and st.hp_t == 0.25
    st = feed(tr, [F(0.5, [10], hp=58)])  # one odd read: unchanged
    assert st.hp_pct == 85
    st = feed(tr, [F(0.75, [10], hp=58)])
    assert st.hp_pct == 58
    st = feed(tr, [F(t, [10], hp=None) for t in (1.0, 1.5, 2.0)])  # unreadable since 0.75
    assert st.hp_pct is None


def test_confidence_drops_when_unstable():
    tr = CombatTracker()
    st = feed(tr, [F(t, [10], [50]) for t in (0, 0.25, 0.5)])
    assert st.confidence == pytest.approx(1.0) and st.reliable
    st = feed(tr, [F(0.75, [10], [51]), F(1.0, [10], [52])])
    assert st.confidence < 0.6 and not st.reliable


def test_single_ally_is_player_and_followed():
    tr = CombatTracker()
    st = feed(tr, [F(t, [10], [50]) for t in (0, 0.25)])
    assert (st.player, st.player_source) == (10, "single")
    st = feed(tr, [F(t, [12], [50]) for t in (0.5, 0.75)])
    assert st.player == 12


def test_manual_player_tracked_through_moves():
    tr = CombatTracker()
    feed(tr, [F(t, [10, 20, 30], [50]) for t in (0, 0.25)])
    assert tr.state(0.25).player is None  # several allies, no cue: unknown
    tr.set_manual_player(20)
    st = feed(tr, [F(0.5, [10, 20, 30])])
    assert (st.player, st.player_source) == (20, "manual")
    st = feed(tr, [F(t, [10, 21, 30]) for t in (0.75, 1.0)])  # only the player moved
    assert st.player == 21


def test_ambiguous_change_hides_player():
    tr = CombatTracker()
    feed(tr, [F(t, [10, 20, 30]) for t in (0, 0.25)])
    tr.set_manual_player(20)
    st = feed(tr, [F(t, [11, 21, 30]) for t in (0.5, 0.75)])  # two allies moved at once
    assert st.player is None
    st = feed(tr, [F(t, [11, 20, 30]) for t in (1.0, 1.25)])  # back on the anchor
    assert st.player == 20


def test_validated_cue_wins():
    tr = CombatTracker()
    st = feed(tr, [F(t, [10, 20], cue=20) for t in (0, 0.25)])
    assert (st.player, st.player_source) == (20, "cue")


def test_ally_and_enemy_on_same_cell_counts_as_ally():
    tr = CombatTracker()
    st = feed(tr, [F(t, [10], [10, 50]) for t in (0, 0.25)])
    assert st.allies == {10} and st.enemies == {50}
