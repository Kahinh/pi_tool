"""Overlay controller: follows the Dofus window, picks the calibration, rebuilds the scene.

Window access goes through a backend (Win32Backend in prod, fakes in tests).
All calibration math is client-relative physical px (window moves don't invalidate it).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pi_tool.app.settings import Settings, config_dir
from pi_tool.core import calibration as cb
from pi_tool.core.grid import Calibration
from pi_tool.core.map_model import MapModel
from pi_tool.core.scene import GridStyle, grid_scene
from pi_tool.platform import win32

WHEEL_STEP = 1.02  # zoom per wheel notch
CALIB_HELP = (
    "Calibration : glisser = déplacer · molette = taille · Maj+molette = aplatir · "
    "flèches = 1 px · Entrée = enregistrer · Échap = annuler"
)


class WindowBackend(Protocol):
    def find_game(self) -> int | None: ...
    def is_window(self, hwnd: int) -> bool: ...
    def is_minimized(self, hwnd: int) -> bool: ...
    def client_rect(self, hwnd: int) -> win32.Rect | None: ...
    def foreground(self) -> int | None: ...


class Win32Backend:
    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def find_game(self) -> int | None:
        return win32.find_window(self.s.window_title, self.s.window_class) or (
            win32.find_window(self.s.window_title) if self.s.window_class else None
        )

    is_window = staticmethod(win32.is_window)
    is_minimized = staticmethod(win32.is_minimized)
    client_rect = staticmethod(win32.client_rect)
    foreground = staticmethod(win32.foreground_window)


class Overlay(Protocol):  # what the controller needs from OverlayWindow
    input_enabled: bool

    def set_shapes(self, shapes, banner=None) -> None: ...
    def place(self, rect) -> None: ...
    def show_overlay(self) -> None: ...
    def hide(self) -> None: ...
    def isVisible(self) -> bool: ...
    def set_input_enabled(self, on: bool) -> None: ...
    def winId(self): ...


class Controller:
    def __init__(
        self,
        settings: Settings,
        backend: WindowBackend,
        overlay: Overlay,
        game_map: MapModel,
        profiles_path: Path | None = None,
    ) -> None:
        self.s, self.backend, self.overlay, self.map = settings, backend, overlay, game_map
        self.profiles_path = profiles_path or config_dir() / "calibration.json"
        self.profiles = cb.load_profiles(self.profiles_path)
        self.hwnd: int | None = None
        self.rect: win32.Rect | None = None  # client rect, screen px
        self.calib: Calibration | None = None  # client-relative
        self.calibrated = False
        self.calibrating = False
        self._backup: Calibration | None = None
        self.status = "démarrage"
        self.on_settings_changed = lambda: None

    # --- main loop -----------------------------------------------------------------------
    def tick(self) -> None:
        if not (self.hwnd and self.backend.is_window(self.hwnd)):
            self.hwnd = self.backend.find_game()
        if not self.hwnd:
            return self._hide("Dofus introuvable")
        if self.backend.is_minimized(self.hwnd):
            return self._hide("Dofus réduit")
        rect = self.backend.client_rect(self.hwnd)
        if not rect or rect[2] <= 0 or rect[3] <= 0:
            return self._hide("zone client indisponible")
        if not self.s.overlay_visible and not self.calibrating:
            return self._hide("overlay masqué")
        if self.s.hide_when_unfocused and not self.calibrating:
            fg = self.backend.foreground()
            if fg not in (self.hwnd, self._own_hwnd()):
                return self._hide("Dofus pas au premier plan")
        if rect[2:] != (self.rect or (0, 0, 0, 0))[2:] and not self.calibrating:
            self._pick_calibration(rect)
        self.rect = rect
        self.overlay.place(rect)
        if not self.overlay.isVisible():
            self.refresh()
            self.overlay.show_overlay()
        self.status = "actif" if self.calibrated else "actif (non calibré)"

    def _hide(self, why: str) -> None:
        self.status = why
        if self.overlay.isVisible():
            self.overlay.hide()

    def _own_hwnd(self) -> int | None:
        return int(self.overlay.winId()) if self.overlay.isVisible() else None

    def _pick_calibration(self, rect: win32.Rect) -> None:
        area = (0.0, 0.0, float(rect[2]), float(rect[3]))
        mode = self.s.scale_mode if self.s.scale_mode in cb.SCALE_MODES else "fit"
        picked = cb.pick(self.profiles, area, mode)  # type: ignore[arg-type]
        self.calibrated = picked is not None
        self.calib = picked or cb.default_calibration(area)
        self.refresh()

    def refresh(self) -> None:
        if self.calib is None:
            return
        show_grid = self.s.grid_visible or self.calibrating
        style = GridStyle(opacity=self.s.opacity, show_ids=self.s.show_ids)
        shapes = grid_scene(self.map, self.calib, style) if show_grid else []
        banner = None
        if self.calibrating:
            banner = CALIB_HELP
        elif show_grid and not self.calibrated:
            banner = "Non calibré — Ctrl+Alt+C pour caler la grille sur la carte"
        self.overlay.set_shapes(shapes, banner)

    # --- toggles (hotkeys / tray) --------------------------------------------------------
    def toggle(self, attr: str) -> None:
        setattr(self.s, attr, not getattr(self.s, attr))
        self.on_settings_changed()
        self.refresh()
        self.tick()

    def set_opacity(self, value: float) -> None:
        self.s.opacity = max(0.05, min(1.0, value))
        self.on_settings_changed()
        self.refresh()

    # --- calibration mode ----------------------------------------------------------------
    def start_calibration(self) -> None:
        if self.calibrating or self.calib is None or self.rect is None:
            return
        self.calibrating, self._backup = True, self.calib
        self.overlay.set_input_enabled(True)
        self.refresh()
        self.tick()

    def drag(self, dx: float, dy: float) -> None:
        self._edit(cb.translate(self.calib, dx, dy))

    def wheel(self, steps: int, x: float, y: float, shift: bool) -> None:
        f = WHEEL_STEP**steps
        op = cb.stretch_y if shift else cb.scale_about
        self._edit(op(self.calib, f, (x, y)))

    def nudge(self, dx: int, dy: int) -> None:
        self._edit(cb.translate(self.calib, dx, dy))

    def _edit(self, cal: Calibration) -> None:
        if self.calibrating:
            self.calib = cal
            self.refresh()

    def accept_calibration(self) -> None:
        if not self.calibrating or self.rect is None or self.calib is None:
            return
        area = (0.0, 0.0, float(self.rect[2]), float(self.rect[3]))
        self.profiles = cb.upsert(self.profiles, cb.Profile(area, self.calib))
        cb.save_profiles(self.profiles, self.profiles_path)
        self.calibrated = True
        self._end_calibration()

    def cancel_calibration(self) -> None:
        if self.calibrating:
            self.calib = self._backup
            self._end_calibration()

    def _end_calibration(self) -> None:
        self.calibrating = False
        self.overlay.set_input_enabled(False)
        self.refresh()
