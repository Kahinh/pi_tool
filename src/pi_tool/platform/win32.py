"""Thin ctypes wrappers over Win32 (no pywin32). Every function is a safe no-op off Windows.

Only observes windows and styles our own overlay: never sends input to the game.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"
Rect = tuple[int, int, int, int]  # x, y, w, h (physical px, screen coords)

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WDA_EXCLUDEFROMCAPTURE = 0x11
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

if IS_WIN:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    _LONG_PTR = ctypes.c_ssize_t
    _get_ex = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    _set_ex = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    _get_ex.argtypes, _get_ex.restype = [wintypes.HWND, ctypes.c_int], _LONG_PTR
    _set_ex.argtypes, _set_ex.restype = [wintypes.HWND, ctypes.c_int, _LONG_PTR], _LONG_PTR
    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    for _name, _args in {
        "GetClientRect": [wintypes.HWND, ctypes.POINTER(wintypes.RECT)],
        "ClientToScreen": [wintypes.HWND, ctypes.POINTER(wintypes.POINT)],
        "IsIconic": [wintypes.HWND],
        "IsWindow": [wintypes.HWND],
        "IsWindowVisible": [wintypes.HWND],
        "GetWindowTextW": [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],
        "GetClassNameW": [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],
        "SetWindowDisplayAffinity": [wintypes.HWND, wintypes.DWORD],
        "SetWindowPos": [wintypes.HWND, wintypes.HWND] + [ctypes.c_int] * 4 + [wintypes.UINT],
        "RegisterHotKey": [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT],
        "UnregisterHotKey": [wintypes.HWND, ctypes.c_int],
        "EnumWindows": [_WNDENUMPROC, wintypes.LPARAM],
    }.items():
        getattr(user32, _name).argtypes = _args
    user32.GetForegroundWindow.restype = wintypes.HWND


def set_dpi_awareness() -> None:
    """Per-monitor v2: all Win32 coordinates in physical px. Call before QApplication."""
    if not IS_WIN:
        return
    try:
        user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        )
    except (AttributeError, OSError):
        ctypes.windll.shcore.SetProcessDpiAwareness(2)


def find_window(title_contains: str, class_name: str | None = None) -> int | None:
    """First visible top-level window whose title contains `title_contains` (case-insensitive)."""
    if not IS_WIN:
        return None
    found: list[int] = []
    needle = title_contains.lower()
    buf = ctypes.create_unicode_buffer(256)

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        if class_name:
            user32.GetClassNameW(hwnd, buf, 256)
            if buf.value != class_name:
                return True
        user32.GetWindowTextW(hwnd, buf, 256)
        if needle in buf.value.lower():
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(_WNDENUMPROC(cb), 0)
    return found[0] if found else None


def is_window(hwnd: int) -> bool:
    return bool(IS_WIN and hwnd and user32.IsWindow(hwnd))


def is_minimized(hwnd: int) -> bool:
    return bool(IS_WIN and user32.IsIconic(hwnd))


def foreground_window() -> int | None:
    return user32.GetForegroundWindow() if IS_WIN else None


def client_rect(hwnd: int) -> Rect | None:
    """Client area in screen physical px, or None if unavailable."""
    if not IS_WIN:
        return None
    r, p = wintypes.RECT(), wintypes.POINT(0, 0)
    if not user32.GetClientRect(hwnd, ctypes.byref(r)) or not user32.ClientToScreen(
        hwnd, ctypes.byref(p)
    ):
        return None
    return p.x, p.y, r.right - r.left, r.bottom - r.top


def style_overlay(hwnd: int, click_through: bool) -> None:
    """Layered, no-activate, hidden from Alt-Tab; WS_EX_TRANSPARENT = clicks go to the game."""
    if not IS_WIN:
        return
    ex = _get_ex(hwnd, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
    if click_through:
        ex |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
    else:
        ex &= ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
    _set_ex(hwnd, GWL_EXSTYLE, ex)


def exclude_from_capture(hwnd: int) -> bool:
    """Hide our overlay from screen captures (Win10 2004+), so V2 can capture the game clean."""
    return bool(IS_WIN and user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))


def place_topmost(hwnd: int, rect: Rect) -> None:
    """Move/resize in physical px without activating."""
    if IS_WIN:
        flags = SWP_NOACTIVATE | SWP_SHOWWINDOW
        user32.SetWindowPos(hwnd, HWND_TOPMOST, *rect, flags)


def register_hotkey(hk_id: int, mods: int, vk: int) -> bool:
    """Thread-level hotkey (WM_HOTKEY posted to the GUI thread). Observes keys only."""
    return bool(IS_WIN and user32.RegisterHotKey(None, hk_id, mods | MOD_NOREPEAT, vk))


def unregister_hotkey(hk_id: int) -> None:
    if IS_WIN:
        user32.UnregisterHotKey(None, hk_id)


def hotkey_id_from_msg(message_ptr: int) -> int | None:
    """WM_HOTKEY id from a native MSG*, else None."""
    if not IS_WIN:
        return None
    msg = wintypes.MSG.from_address(message_ptr)
    return int(msg.wParam) if msg.message == WM_HOTKEY else None


def parse_hotkey(spec: str) -> tuple[int, int]:
    """'Ctrl+Alt+G' -> (mods, vk). Letters, digits, F1-F12."""
    mods, vk = 0, 0
    for part in spec.replace(" ", "").split("+"):
        p = part.lower()
        if p in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif p == "alt":
            mods |= MOD_ALT
        elif p == "shift":
            mods |= MOD_SHIFT
        elif len(p) == 1 and p.isalnum():
            vk = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit() and 1 <= int(p[1:]) <= 12:
            vk = 0x70 + int(p[1:]) - 1
        else:
            raise ValueError(f"bad hotkey part: {part}")
    if not vk:
        raise ValueError(f"no key in hotkey: {spec}")
    return mods, vk
