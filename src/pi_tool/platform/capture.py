"""Game capture without our overlay (V2.1). Reads pixels only; never touches the game.

Two methods, both returning the game CLIENT area as a BGR uint8 array (physical px):
- "screen": mss grab of the client rect. Our overlay is invisible to it thanks to
  WDA_EXCLUDEFROMCAPTURE (Win10 2004+). Fast, works with DirectX/Unity.
- "window": PrintWindow(PW_CLIENTONLY | PW_RENDERFULLCONTENT) on the game HWND: our
  overlay is never in it, even without capture exclusion; slower, may be black on some
  GPU/driver setups.
"auto" = screen when the overlay is excluded from captures (or hidden), else window.
A frame that is (almost) uniformly black is treated as a failed capture.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

import numpy as np

from pi_tool.platform import win32

METHODS = ("auto", "screen", "window")
PW_CLIENTONLY, PW_RENDERFULLCONTENT = 0x1, 0x2


def usable(frame: np.ndarray | None) -> bool:
    """Reject empty / black frames (minimised, occluded DWM surface, failed PrintWindow)."""
    return frame is not None and frame.size > 0 and int(frame[::8, ::8].max()) > 8


def grab_screen(rect: win32.Rect) -> np.ndarray | None:
    if not win32.IS_WIN or rect[2] <= 0 or rect[3] <= 0:
        return None
    import mss  # win extra

    x, y, w, h = rect
    with mss.mss() as sct:
        shot = sct.grab({"left": x, "top": y, "width": w, "height": h})
    return np.ascontiguousarray(np.asarray(shot)[..., :3])


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def grab_window(hwnd: int, size: tuple[int, int]) -> np.ndarray | None:
    if not win32.IS_WIN or size[0] <= 0 or size[1] <= 0:
        return None
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    for fn in (user32.GetDC, gdi32.CreateCompatibleDC, gdi32.CreateCompatibleBitmap):
        fn.restype = wintypes.HANDLE
    w, h = size
    hdc = user32.GetDC(wintypes.HWND(hwnd))
    mem = gdi32.CreateCompatibleDC(wintypes.HANDLE(hdc))
    bmp = gdi32.CreateCompatibleBitmap(wintypes.HANDLE(hdc), w, h)
    try:
        gdi32.SelectObject(wintypes.HANDLE(mem), wintypes.HANDLE(bmp))
        flags = PW_CLIENTONLY | PW_RENDERFULLCONTENT
        if not user32.PrintWindow(wintypes.HWND(hwnd), wintypes.HANDLE(mem), flags):
            return None
        bih = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER), w, -h, 1, 32, 0)
        buf = np.empty((h, w, 4), np.uint8)
        lines = gdi32.GetDIBits(
            wintypes.HANDLE(mem),
            wintypes.HANDLE(bmp),
            0,
            h,
            ctypes.c_void_p(buf.ctypes.data),
            ctypes.byref(bih),
            0,
        )
        return np.ascontiguousarray(buf[..., :3]) if lines == h else None
    finally:
        gdi32.DeleteObject(wintypes.HANDLE(bmp))
        gdi32.DeleteDC(wintypes.HANDLE(mem))
        user32.ReleaseDC(wintypes.HWND(hwnd), wintypes.HANDLE(hdc))


class Capturer:
    """Picks the method; `last_method` / `last_error` feed the debug banner."""

    def __init__(self, method: str = "auto") -> None:
        self.method = method if method in METHODS else "auto"
        self.last_method: str | None = None
        self.last_error: str | None = None

    def grab(self, hwnd: int, rect: win32.Rect, overlay_clean: bool) -> np.ndarray | None:
        """`overlay_clean`: our overlay is hidden or excluded from screen captures."""
        order = {
            "screen": ("screen",),
            "window": ("window",),
            "auto": ("screen", "window") if overlay_clean else ("window",),
        }[self.method]
        self.last_error = None
        for m in order:
            try:
                frame = grab_screen(rect) if m == "screen" else grab_window(hwnd, rect[2:])
            except Exception as e:  # capture backends fail in many OS-specific ways
                self.last_error = f"{m}: {e}"
                continue
            if usable(frame):
                self.last_method = m
                return frame
            self.last_error = f"{m}: image vide"
        self.last_method = None
        return None
