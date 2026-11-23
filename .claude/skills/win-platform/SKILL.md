---
name: win-platform
description: Windows overlay, game-window capture, window tracking and DPI for pi_tool (issues #5, #6, #7, #8, #15). Use when writing src/pi_tool/platform or app code.
---

Can't run in the Linux cloud: keep platform code thin, push logic into core/vision, guard imports (`sys.platform == "win32"`), mark tests `win`, and give the user a manual test checklist.

Overlay (PySide6): frameless `Qt.Tool | WindowStaysOnTopHint | WindowTransparentForInput | WindowDoesNotAcceptFocus`, `WA_TranslucentBackground`, `WA_ShowWithoutActivating`. Belt-and-braces via win32: ex-style `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW`. Draw diamonds with QPainter from `Calibration.cell_diamond`.

Capture without overlay: `SetWindowDisplayAffinity(overlay_hwnd, WDA_EXCLUDEFROMCAPTURE=0x11)` (Win10 2004+), then capture the game client rect (mss / DXGI). Verify on capture that the overlay is absent; fallback = Windows Graphics Capture of the game HWND.

Tracking: find Dofus HWND (title/class, confirm on user machine), poll `GetClientRect` + `ClientToScreen` (~10 Hz) or `SetWinEventHook(EVENT_OBJECT_LOCATIONCHANGE)`; hide overlay when minimized / not foreground (option).

DPI: call `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)` before creating Qt app; work in physical pixels end-to-end; convert to Qt logical px only at draw time (`devicePixelRatio`).

Hotkeys (toggle overlay / grid / debug): `RegisterHotKey` — observing keys only, never sending input.
