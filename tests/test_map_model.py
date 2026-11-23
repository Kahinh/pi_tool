from pi_tool.core.map_model import CYCLE, CellState, empty_map, load_map, save_map


def test_states_are_distinct_properties():
    m = empty_map()
    m = m.with_state(1, CellState.OBSTACLE)
    m = m.with_state(2, CellState.NON_WALKABLE)
    m = m.with_state(3, CellState.NON_TARGETABLE)
    m = m.with_state(4, CellState.OUTSIDE)
    assert (m.walkable(1), m.targetable(1), 1 in m.blocks_los) == (False, False, True)
    assert (m.walkable(2), m.targetable(2)) == (False, True)
    assert (m.walkable(3), m.targetable(3)) == (True, False)
    assert not m.in_arena(4) and not m.walkable(4) and not m.targetable(4)
    assert m.walkable(5) and m.targetable(5)


def test_cycle_roundtrips_every_state():
    m = empty_map()
    for st in CYCLE:
        m = m.with_state(7, st)
        assert m.state(7) is st
    m = m.with_state(7, CellState.NORMAL)
    assert 7 not in m.blocks_los


def test_toggle_los():
    m = empty_map().toggle_los(9)
    assert 9 in m.blocks_los and m.state(9) is CellState.NORMAL
    assert 9 not in m.toggle_los(9).blocks_los


def test_save_load_roundtrip(tmp_path):
    m = empty_map("t").with_state(3, CellState.OBSTACLE).with_state(10, CellState.OUTSIDE)
    path = save_map(m, tmp_path / "t.json")
    assert load_map(path=path) == m
