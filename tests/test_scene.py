import numpy as np
import pytest

from pi_tool.core.grid import CELL_COUNT, Calibration
from pi_tool.core.map_model import CellState, empty_map
from pi_tool.core.scene import FILL, GridStyle, grid_scene

CAL = Calibration.from_cell_size((60.0, 300.0), 40, 20)


def test_grid_scene_skips_outside_and_labels():
    m = empty_map().with_state(0, CellState.OUTSIDE).with_state(5, CellState.OBSTACLE)
    shapes = grid_scene(m, CAL, GridStyle(show_ids=True))
    assert len(shapes) == CELL_COUNT - 1
    by_label = {s.label: s for s in shapes}
    assert "0" not in by_label
    assert by_label["5"].fill[:3] == FILL[CellState.OBSTACLE][:3]
    assert by_label["6"].fill is None
    assert len(grid_scene(m, CAL, GridStyle(show_outside=True))) == CELL_COUNT


def test_opacity_scales_alpha():
    m = empty_map().with_state(5, CellState.OBSTACLE)
    s = grid_scene(m, CAL, GridStyle(opacity=0.5))
    fill = next(x.fill for x in s if x.fill)
    assert fill[3] == round(FILL[CellState.OBSTACLE][3] * 0.5)


def test_cv2_render_and_content_rect():
    render = pytest.importorskip("pi_tool.vision.render")
    img = np.zeros((500, 700, 3), np.uint8)
    img[50:450, 100:600] = 40  # game area inside black bars
    assert render.content_rect(img) == (100, 50, 500, 400)
    m = empty_map().with_state(100, CellState.OBSTACLE)
    out = render.draw_scene(img, grid_scene(m, CAL))
    x, y = map(round, CAL.cell_center(100))
    b, _g, r = out[y, x]
    assert r > b and r > 60  # vermillion blended at the obstacle center
