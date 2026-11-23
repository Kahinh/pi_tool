import pytest

from pi_tool.core import calibration as cb
from pi_tool.core.grid import CELL_COUNT, Calibration, cell_to_xy

BASE = Calibration.from_cell_size((300.0, 100.0), 80, 40)
P = cb.Profile((0.0, 0.0, 1920.0, 1080.0), BASE)


def approx_cal(a, b):
    for x, y in [(a.origin, b.origin), (a.u, b.u), (a.v, b.v)]:
        assert x == pytest.approx(y)


def test_rescale_identity():
    approx_cal(cb.rescale(P, P.rect), BASE)


def test_rescale_fit_letterbox_keeps_cell_ratio():
    cal = cb.rescale(P, (0, 0, 2560, 1080), "fit")  # ultrawide: same height -> same size
    assert cal.u == pytest.approx(BASE.u)
    assert cal.origin[0] == pytest.approx(BASE.origin[0] + 320)  # centered pillarbox


def test_rescale_stretch_independent_axes():
    cal = cb.rescale(P, (0, 0, 960, 1080), "stretch")
    assert cal.u == pytest.approx((20, 20))


def test_pick_exact_then_nearest_aspect():
    other = cb.Profile((0.0, 0.0, 1280.0, 1024.0), Calibration((1, 1), (2, 2), (2, -2)))
    profiles = [P, other]
    approx_cal(cb.pick(profiles, (0, 0, 1920, 1080)), BASE)
    approx_cal(cb.pick(profiles, (0, 0, 1280, 720)), cb.rescale(P, (0, 0, 1280, 720)))
    assert cb.pick([], (0, 0, 1, 1)) is None


def test_upsert_replaces_same_size():
    new = cb.Profile(P.rect, Calibration((0, 0), (1, 1), (1, -1)))
    assert cb.upsert([P], new) == [new]


@pytest.mark.parametrize("rect", [(0, 0, 1920, 1080), (0, 0, 2560, 1080), (0, 0, 1024, 768)])
def test_default_calibration_fits_inside(rect):
    cal = cb.default_calibration(rect)
    for c in range(CELL_COUNT):
        for x, y in cal.cell_diamond(c):
            assert rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]


def test_manual_ops_keep_pivot():
    pivot = (500.0, 400.0)
    for op in (cb.scale_about, cb.stretch_y):
        cal = op(BASE, 1.3, pivot)
        fx, fy = BASE.to_map(*pivot)
        assert cal.to_screen(fx, fy) == pytest.approx(pivot)
    assert cb.translate(BASE, 5, -2).origin == (305.0, 98.0)


def test_profiles_roundtrip(tmp_path):
    path = tmp_path / "c.json"
    cb.save_profiles([P], path)
    assert cb.load_profiles(path) == [P]
    assert cb.load_profiles(tmp_path / "missing.json") == []


def test_from_annotation_fit_and_residual():
    pts = [[c, *BASE.to_screen(*cell_to_xy(c))] for c in (0, 13, 280, 559)]
    cal, res = cb.from_annotation({"calib_points": pts})
    approx_cal(cal, BASE)
    assert res < 1e-6
    cal2, res2 = cb.from_annotation({"calibration": cb.to_annotation(BASE)})
    assert cal2 == BASE and res2 is None
    assert cb.from_annotation({}) == (None, None)
