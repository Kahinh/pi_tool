import pytest

from pi_tool.core.grid import (
    CELL_COUNT,
    Calibration,
    cell_to_xy,
    distance,
    rotate90,
    xy_to_cell,
)


def test_roundtrip_all_cells():
    seen = set()
    for c in range(CELL_COUNT):
        xy = cell_to_xy(c)
        assert xy_to_cell(*xy) == c
        seen.add(xy)
    assert len(seen) == CELL_COUNT


@pytest.mark.parametrize(
    ("cell", "xy"), [(0, (0, 0)), (1, (1, 1)), (14, (1, 0)), (28, (1, -1)), (15, (2, 1))]
)
def test_known_coords(cell, xy):
    assert cell_to_xy(cell) == xy


@pytest.mark.parametrize("xy", [(0, 1), (-1, 0), (14, 14), (40, -20), (100, 0)])
def test_outside(xy):
    assert xy_to_cell(*xy) is None


def test_rotate_full_turn_and_distance():
    c, p = (10, -3), (13, 1)
    assert rotate90(p, c, 4) == p
    assert rotate90(rotate90(p, c, 1), c, -1) == p
    for k in range(4):
        assert distance(rotate90(p, c, k), c) == distance(p, c)


def test_calibration_inverse_every_cell():
    cal = Calibration.from_cell_size((100.0, 500.0), 86, 43)
    for c in range(CELL_COUNT):
        px, py = cal.cell_center(c)
        assert cal.cell_at(px, py) == c
        assert cal.cell_at(px + 20, py + 5) == c  # inside the diamond


def test_staggered_layout_matches_ideal_basis():
    cal = Calibration.from_cell_size((0.0, 0.0), 86, 43)
    assert cal.cell_center(1) == pytest.approx((86, 0))  # same row, next col
    assert cal.cell_center(14) == pytest.approx((43, 21.5))  # next row, half offset


def test_fit_recovers_affine():
    truth = Calibration((12.5, 300.0), (40.0, 20.5), (40.0, -20.5))
    pairs = [((x, y), truth.to_screen(x, y)) for x, y in [(0, 0), (5, 2), (20, -7), (33, 0)]]
    fit = Calibration.fit(pairs)
    for a, b in [(fit.origin, truth.origin), (fit.u, truth.u), (fit.v, truth.v)]:
        assert a == pytest.approx(b)


def test_fit_rejects_collinear():
    with pytest.raises(ValueError):
        Calibration.fit([((0, 0), (0, 0)), ((1, 1), (1, 1)), ((2, 2), (2, 2))])
