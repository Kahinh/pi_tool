import pytest

from pi_tool.app.controller import Controller
from pi_tool.app.settings import Settings
from pi_tool.core import calibration as cb
from pi_tool.core.map_model import empty_map

GAME = 42


class FakeBackend:
    def __init__(self):
        self.exists, self.minimized, self.fg = True, False, GAME
        self.rect = (100, 50, 1920, 1080)

    def find_game(self):
        return GAME if self.exists else None

    def is_window(self, hwnd):
        return self.exists and hwnd == GAME

    def is_minimized(self, hwnd):
        return self.minimized

    def client_rect(self, hwnd):
        return self.rect

    def foreground(self):
        return self.fg


class FakeOverlay:
    def __init__(self):
        self.visible, self.input_enabled, self.rect = False, False, None
        self.shapes, self.banner = [], None

    def set_shapes(self, shapes, banner=None):
        self.shapes, self.banner = shapes, banner

    def place(self, rect):
        self.rect = rect

    def show_overlay(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def isVisible(self):
        return self.visible

    def set_input_enabled(self, on):
        self.input_enabled = on

    def winId(self):
        return 7


@pytest.fixture
def env(tmp_path):
    b, o = FakeBackend(), FakeOverlay()
    c = Controller(Settings(), b, o, empty_map(), tmp_path / "calib.json")
    return c, b, o


def test_follows_game_window(env):
    c, b, o = env
    c.tick()
    assert o.visible and o.rect == b.rect and len(o.shapes) == 560
    assert "Non calibré" in o.banner
    b.rect = (300, 60, 1920, 1080)  # moved: same calibration, new position
    cal = c.calib
    c.tick()
    assert o.rect == b.rect and c.calib is cal


@pytest.mark.parametrize(
    ("change", "status"),
    [
        (lambda b: setattr(b, "exists", False), "introuvable"),
        (lambda b: setattr(b, "minimized", True), "réduit"),
        (lambda b: setattr(b, "fg", 999), "premier plan"),
    ],
)
def test_hides(env, change, status):
    c, b, o = env
    c.tick()
    change(b)
    c.tick()
    assert not o.visible and status in c.status


def test_overlay_click_owner_counts_as_focused(env):
    c, b, o = env
    c.tick()
    b.fg = 7  # our overlay hwnd
    c.tick()
    assert o.visible


def test_toggles(env):
    c, _, o = env
    c.tick()
    c.toggle("grid_visible")
    assert o.shapes == [] and o.visible
    c.toggle("overlay_visible")
    assert not o.visible


def test_calibration_accept_saves_and_resize_rescales(env):
    c, b, o = env
    c.tick()
    c.start_calibration()
    assert o.input_enabled and c.calibrating
    c.drag(10, 5)
    c.wheel(2, 500, 500, False)
    c.nudge(1, 0)
    edited = c.calib
    c.accept_calibration()
    assert not o.input_enabled and c.calibrated
    assert cb.load_profiles(c.profiles_path)[0].calib == edited
    b.rect = (0, 0, 3840, 2160)  # 4K: rescaled from the 1080p profile
    c.tick()
    assert c.calib.u == pytest.approx((edited.u[0] * 2, edited.u[1] * 2))
    assert o.banner is None


def test_calibration_cancel_restores(env):
    c, _, o = env
    c.tick()
    before = c.calib
    c.start_calibration()
    c.drag(50, 50)
    c.cancel_calibration()
    assert c.calib == before and not c.calibrating and not o.input_enabled


def test_calibrating_survives_focus_loss(env):
    c, b, o = env
    c.tick()
    c.start_calibration()
    b.fg = 999
    c.tick()
    assert o.visible
