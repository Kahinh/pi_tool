"""V2.1: capture method selection + blank-frame rejection (real grabs: `win` marker)."""

import sys

import numpy as np
import pytest

from pi_tool.platform import capture


def test_usable():
    assert not capture.usable(None)
    assert not capture.usable(np.zeros((100, 100, 3), np.uint8))
    assert capture.usable(np.full((100, 100, 3), 60, np.uint8))


@pytest.fixture
def grabs(monkeypatch):
    calls = []
    frames = {
        "screen": np.full((4, 4, 3), 50, np.uint8),
        "window": np.full((4, 4, 3), 70, np.uint8),
    }

    def screen(rect):
        calls.append("screen")
        return frames["screen"]

    def window(hwnd, size):
        calls.append("window")
        return frames["window"]

    monkeypatch.setattr(capture, "grab_screen", screen)
    monkeypatch.setattr(capture, "grab_window", window)
    return calls, frames


def test_auto_never_screen_grabs_a_visible_unexcluded_overlay(grabs):
    calls, _ = grabs
    c = capture.Capturer("auto")
    assert c.grab(1, (0, 0, 4, 4), overlay_clean=False)[0, 0, 0] == 70
    assert calls == ["window"] and c.last_method == "window"


def test_auto_falls_back_when_screen_is_black(grabs):
    calls, frames = grabs
    frames["screen"] = np.zeros((4, 4, 3), np.uint8)
    c = capture.Capturer("auto")
    assert c.grab(1, (0, 0, 4, 4), overlay_clean=True) is not None
    assert calls == ["screen", "window"] and c.last_method == "window"


def test_failure_reported(grabs, monkeypatch):
    def boom(*_):
        raise OSError("denied")

    monkeypatch.setattr(capture, "grab_window", boom)
    c = capture.Capturer("window")
    assert c.grab(1, (0, 0, 4, 4), True) is None and "denied" in c.last_error
    assert capture.Capturer("bogus").method == "auto"


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows fallback")
def test_noop_off_windows():
    assert capture.grab_screen((0, 0, 10, 10)) is None
    assert capture.grab_window(1, (10, 10)) is None


@pytest.mark.win
def test_real_desktop_grab():
    assert capture.usable(capture.grab_screen((0, 0, 200, 200)))
