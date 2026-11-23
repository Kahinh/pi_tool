"""Overlay controller: follows the Dofus window, picks the calibration, runs vision, draws.

Window access + capture go through a backend (Win32Backend in prod, fakes in tests).
All calibration math is client-relative physical px (window moves don't invalidate it).
Input modes (the only times the overlay takes the mouse, user-triggered by hotkey):
"calib" grid calibration, "hp_roi" HP zone, "pick" choose the controlled character.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from pi_tool.app.settings import Settings, config_dir
from pi_tool.core import calibration as cb
from pi_tool.core.combat import CombatTracker, Frame, status_line
from pi_tool.core.grid import Calibration
from pi_tool.core.map_model import MapModel
from pi_tool.core.scene import GridStyle, combat_scene, grid_scene, roi_shape
from pi_tool.platform import win32

WHEEL_STEP = 1.02  # zoom per wheel notch
CALIB_HELP = (
    "Calibration : glisser = déplacer · molette = taille · Maj+molette = aplatir · "
    "flèches = 1 px · Entrée = enregistrer · Échap = annuler"
)
HP_HELP = (
    "Zone PV : encadrer le pourcentage du cœur · glisser = déplacer · molette = taille · "
    "Maj+molette = largeur · Entrée = enregistrer · Échap = annuler"
)
PICK_HELP = "Cliquer sur la case de VOTRE personnage · Échap = annuler"
DEFAULT_ROI = (0.47, 0.86, 0.06, 0.06)


class Analyzer(Protocol):  # app.vision.Analyzer
    def analyze(self, img: Any, cal: Calibration, hp_roi: Any, t: float) -> Frame: ...
    def hp_debug(self) -> str: ...


class WindowBackend(Protocol):
    def find_game(self) -> int | None: ...
    def is_window(self, hwnd: int) -> bool: ...
    def is_minimized(self, hwnd: int) -> bool: ...
    def client_rect(self, hwnd: int) -> win32.Rect | None: ...
    def foreground(self) -> int | None: ...
    def capture(self, hwnd: int, rect: win32.Rect, overlay_clean: bool) -> Any: ...


class Win32Backend:
    def __init__(self, settings: Settings) -> None:
        from pi_tool.platform.capture import Capturer

        self.s = settings
        self.capturer = Capturer(settings.capture_method)

    def find_game(self) -> int | None:
        return win32.find_window(self.s.window_title, self.s.window_class) or (
            win32.find_window(self.s.window_title) if self.s.window_class else None
        )

    is_window = staticmethod(win32.is_window)
    is_minimized = staticmethod(win32.is_minimized)
    client_rect = staticmethod(win32.client_rect)
    foreground = staticmethod(win32.foreground_window)

    def capture(self, hwnd: int, rect: win32.Rect, overlay_clean: bool):
        return self.capturer.grab(hwnd, rect, overlay_clean)


class Overlay(Protocol):  # what the controller needs from OverlayWindow
    input_enabled: bool
    capture_excluded: bool

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
        analyzer: Analyzer | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.s, self.backend, self.overlay, self.map = settings, backend, overlay, game_map
        self.profiles_path = profiles_path or config_dir() / "calibration.json"
        self.profiles = cb.load_profiles(self.profiles_path)
        self.hwnd: int | None = None
        self.rect: win32.Rect | None = None  # client rect, screen px
        self.calib: Calibration | None = None  # client-relative
        self.calibrated = False
        self.mode: str | None = None  # None | "calib" | "hp_roi" | "pick"
        self._backup: Calibration | None = None
        self._roi_backup: list[float] | None = None
        self.analyzer, self.clock = analyzer, clock
        self.tracker = CombatTracker()
        self.status = "démarrage"
        self.on_settings_changed = lambda: None

    @property
    def calibrating(self) -> bool:
        return self.mode == "calib"

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
        if not self.s.overlay_visible and not self.mode:
            return self._hide("overlay masqué")
        if self.s.hide_when_unfocused and not self.mode:
            fg = self.backend.foreground()
            if fg not in (self.hwnd, self._own_hwnd()):
                return self._hide("Dofus pas au premier plan")
        if rect[2:] != (self.rect or (0, 0, 0, 0))[2:] and not self.mode:
            if self.rect is not None:
                self.tracker.reset()  # cells moved on screen: old detections are void
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
        now = self.clock()
        st = self.tracker.state(now)
        if self.s.debug_vision or self.mode == "pick":
            shapes += combat_scene(st, self.calib)
        if self.rect and (self.mode == "hp_roi" or (self.s.debug_vision and self.s.hp_roi)):
            shapes.append(roi_shape(tuple(self.s.hp_roi or DEFAULT_ROI), *self.rect[2:]))
        banner = None
        if self.calibrating:
            banner = CALIB_HELP
        elif self.mode == "pick":
            banner = PICK_HELP
        elif self.mode == "hp_roi":
            banner = HP_HELP + (f" — {self.analyzer.hp_debug()}" if self.analyzer else "")
        elif show_grid and not self.calibrated:
            banner = "Non calibré — Ctrl+Alt+C pour caler la grille sur la carte"
        elif self.s.debug_vision:
            banner = status_line(st, now)
            if self.analyzer:
                banner += " | " + self.analyzer.hp_debug()
        self.overlay.set_shapes(shapes, banner)

    # --- vision (V2) -----------------------------------------------------------------------
    def vision_tick(self) -> None:
        """Capture + analyse one frame. Only while the overlay is up and calibrated."""
        if (
            self.analyzer is None
            or not self.s.vision_enabled
            or self.mode == "calib"
            or not self.calibrated
            or self.calib is None
            or self.hwnd is None
            or self.rect is None
            or not self.overlay.isVisible()
        ):
            return
        clean = bool(getattr(self.overlay, "capture_excluded", False))
        img = self.backend.capture(self.hwnd, self.rect, clean)
        if img is not None and tuple(img.shape[:2]) != (self.rect[3], self.rect[2]):
            img = None  # size changed under us (resize/DPI): skip this frame
        frame = self.analyzer.analyze(img, self.calib, self.s.hp_roi, self.clock())
        self.tracker.update(frame)
        if self.s.debug_vision or self.mode:
            self.refresh()

    def state(self):
        """Current combat state (stale/uncertain parts hidden) for V3."""
        return self.tracker.state(self.clock())

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
    def _enter(self, mode: str) -> bool:
        if self.mode or self.calib is None or self.rect is None:
            return False
        self.mode = mode
        self.overlay.set_input_enabled(True)
        self.refresh()
        self.tick()
        return True

    def start_calibration(self) -> None:
        if self._enter("calib"):
            self._backup = self.calib

    def drag(self, dx: float, dy: float) -> None:
        if self.mode == "hp_roi":
            return self._move_roi(dx, dy)
        self._edit(cb.translate(self.calib, dx, dy))

    def wheel(self, steps: int, x: float, y: float, shift: bool) -> None:
        f = WHEEL_STEP**steps
        if self.mode == "hp_roi":
            return self._scale_roi(f, shift)
        op = cb.stretch_y if shift else cb.scale_about
        self._edit(op(self.calib, f, (x, y)))

    def nudge(self, dx: int, dy: int) -> None:
        self.drag(dx, dy)

    def click(self, x: float, y: float) -> None:
        """Pick mode: the clicked cell becomes the controlled character (manual fallback)."""
        if self.mode != "pick" or self.calib is None:
            return
        self.tracker.set_manual_player(self.calib.cell_at(x, y))
        self._end_mode()

    def _edit(self, cal: Calibration) -> None:
        if self.calibrating:
            self.calib = cal
            self.refresh()

    def accept_calibration(self) -> None:
        if self.mode == "hp_roi":
            self.on_settings_changed()
            return self._end_mode()
        if not self.calibrating or self.rect is None or self.calib is None:
            return
        area = (0.0, 0.0, float(self.rect[2]), float(self.rect[3]))
        self.profiles = cb.upsert(self.profiles, cb.Profile(area, self.calib))
        cb.save_profiles(self.profiles, self.profiles_path)
        self.calibrated = True
        self.tracker.reset()
        self._end_mode()

    def cancel_calibration(self) -> None:
        if self.calibrating:
            self.calib = self._backup
        elif self.mode == "hp_roi":
            self.s.hp_roi = self._roi_backup
        self._end_mode()

    def _end_mode(self) -> None:
        if self.mode is None:
            return
        self.mode = None
        self.overlay.set_input_enabled(False)
        self.refresh()

    # --- HP zone (V2.4) and manual player (V2.3) ---------------------------------------------
    def start_hp_roi(self) -> None:
        backup = list(self.s.hp_roi) if self.s.hp_roi else None
        if self._enter("hp_roi"):
            self._roi_backup = backup
            self.s.hp_roi = list(self.s.hp_roi or DEFAULT_ROI)
            self.refresh()

    def start_pick_player(self) -> None:
        self._enter("pick")

    def _move_roi(self, dx: float, dy: float) -> None:
        if self.s.hp_roi and self.rect:
            x, y, w, h = self.s.hp_roi
            self.s.hp_roi = [x + dx / self.rect[2], y + dy / self.rect[3], w, h]
            self.refresh()

    def _scale_roi(self, f: float, width_only: bool) -> None:
        if self.s.hp_roi:
            x, y, w, h = self.s.hp_roi
            nw, nh = w * f, h if width_only else h * f
            self.s.hp_roi = [x + (w - nw) / 2, y + (h - nh) / 2, nw, nh]
            self.refresh()
