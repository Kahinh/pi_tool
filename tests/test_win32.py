import sys

import pytest

from pi_tool.platform import win32


def test_parse_hotkey():
    assert win32.parse_hotkey("Ctrl+Alt+G") == (win32.MOD_CONTROL | win32.MOD_ALT, ord("G"))
    assert win32.parse_hotkey("shift+F2") == (win32.MOD_SHIFT, 0x71)
    with pytest.raises(ValueError):
        win32.parse_hotkey("Ctrl+Alt")
    with pytest.raises(ValueError):
        win32.parse_hotkey("Ctrl+Space")


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows fallback")
def test_noop_off_windows():
    assert win32.find_window("Dofus") is None
    assert win32.client_rect(1) is None
    assert not win32.register_hotkey(1, 0, 65)
