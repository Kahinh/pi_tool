"""V2.2: circle detection on synthetic frames (+ real annotated captures when present)."""

import cv2
import numpy as np
import pytest

from conftest import screen_fixtures
from pi_tool.core.calibration import from_annotation
from pi_tool.core.grid import CELL_COUNT
from pi_tool.core.map_model import load_map
from pi_tool.vision.circles import detect_circles, split_teams
from synth import BLUE, RED, cal_for, floor, ring, sprite

ALL = range(CELL_COUNT)


def scene(w, h, allies, enemies, occlude=True, seed=0):
    img, cal = floor(w, h, seed), cal_for(w, h)
    for cells, col in ((allies, BLUE), (enemies, RED)):
        for c in cells:
            ring(img, cal, c, col)
            if occlude:
                sprite(img, cal, c, seed=c)
    return img, cal


@pytest.mark.parametrize(("w", "h"), [(1280, 720), (1920, 1080), (2560, 1080), (3840, 2160)])
def test_detects_occluded_rings_at_several_resolutions(w, h):
    allies, enemies = {242, 245, 300}, {216, 217, 330, 400}  # 216/217 adjacent
    img, cal = scene(w, h, allies, enemies)
    a, e = split_teams(detect_circles(img, cal, ALL))
    assert (a, e) == (allies, enemies)


def test_rejects_distractors():
    img, cal = scene(1920, 1080, {242}, {330})
    cv2.circle(img, (300, 300), 8, RED, -1)  # small blob
    cv2.line(img, (100, 900), (1800, 950), BLUE, 3)  # long line (UI / effect)
    cx, cy = map(round, cal.cell_center(480))
    cv2.ellipse(img, (cx, cy), (260, 130), 0, 0, 360, RED, -1)  # large spell zone
    a, e = split_teams(detect_circles(img, cal, ALL))
    assert (a, e) == ({242}, {330})


def test_empty_frame_and_out_of_image_cells():
    img, cal = scene(800, 450, set(), set())
    assert detect_circles(img, cal, ALL) == []
    assert detect_circles(np.zeros((10, 10, 3), np.uint8), cal, ALL) == []


@pytest.mark.fixtures
@pytest.mark.parametrize(
    ("png", "ann"),
    [f for f in screen_fixtures() if "allies" in f[1] or "enemies" in f[1]] or [(None, None)],
)
def test_real_captures(png, ann):
    if png is None:
        pytest.skip("no annotated capture with allies/enemies yet")
    cal, _ = from_annotation(ann)
    if cal is None:
        pytest.skip("capture not calibrated")
    m = load_map()
    a, e = split_teams(detect_circles(cv2.imread(str(png)), cal, filter(m.walkable, ALL)))
    want_a, want_e = set(ann.get("allies", [])), set(ann.get("enemies", []))
    diff = {"allies": (sorted(want_a), sorted(a)), "enemies": (sorted(want_e), sorted(e))}
    assert a == want_a and e == want_e, f"{png.name} expected/got {diff}"
