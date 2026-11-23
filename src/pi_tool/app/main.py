"""Entry point `pi-tool`: overlay + window tracking + hotkeys + tray menu."""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap, QPolygon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from pi_tool.app.controller import Controller, Win32Backend
from pi_tool.app.settings import Settings
from pi_tool.core.map_model import load_map
from pi_tool.platform import win32
from pi_tool.platform.hotkeys import HotkeyManager
from pi_tool.platform.overlay import OverlayWindow

OPACITIES = (0.2, 0.35, 0.5, 0.6, 0.8, 1.0)


def _icon() -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(0, 158, 115))
    p.setPen(QColor(255, 255, 255))
    p.drawPolygon(QPolygon([QPoint(16, 4), QPoint(30, 16), QPoint(16, 28), QPoint(2, 16)]))
    p.end()
    return QIcon(pm)


def build_tray(app: QApplication, ctrl: Controller) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(_icon(), app)
    menu = QMenu()
    toggles = {}
    for attr, label in (
        ("overlay_visible", "Overlay"),
        ("grid_visible", "Quadrillage"),
        ("show_ids", "Identifiants de cellules"),
        ("hide_when_unfocused", "Masquer si Dofus inactif"),
    ):
        a = QAction(label, menu, checkable=True)
        a.triggered.connect(lambda _=False, at=attr: ctrl.toggle(at))
        menu.addAction(a)
        toggles[attr] = a
    op_menu = menu.addMenu("Opacité")
    group = QActionGroup(op_menu)
    for v in OPACITIES:
        a = QAction(f"{round(v * 100)} %", op_menu, checkable=True)
        a.setData(v)
        a.triggered.connect(lambda _=False, val=v: ctrl.set_opacity(val))
        group.addAction(a)
        op_menu.addAction(a)
    menu.addSeparator()
    menu.addAction("Calibrer…", ctrl.start_calibration)
    menu.addSeparator()
    menu.addAction("Quitter", app.quit)

    def sync() -> None:
        for attr, a in toggles.items():
            a.setChecked(bool(getattr(ctrl.s, attr)))
        for a in group.actions():
            a.setChecked(abs(a.data() - ctrl.s.opacity) < 1e-6)
        tray.setToolTip(f"pi_tool — {ctrl.status}")

    menu.aboutToShow.connect(sync)
    tray.setContextMenu(menu)
    sync()
    tray.show()
    return tray


def main() -> int:
    win32.set_dpi_awareness()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    settings = Settings.load()
    overlay = OverlayWindow()
    ctrl = Controller(settings, Win32Backend(settings), overlay, load_map())
    ctrl.on_settings_changed = settings.save

    overlay.dragged.connect(ctrl.drag)
    overlay.wheeled.connect(ctrl.wheel)
    overlay.nudged.connect(ctrl.nudge)
    overlay.accepted.connect(ctrl.accept_calibration)
    overlay.cancelled.connect(ctrl.cancel_calibration)

    actions = {
        "toggle_overlay": lambda: ctrl.toggle("overlay_visible"),
        "toggle_grid": lambda: ctrl.toggle("grid_visible"),
        "toggle_ids": lambda: ctrl.toggle("show_ids"),
        "calibrate": ctrl.start_calibration,
        "quit": app.quit,
    }
    hotkeys = HotkeyManager()
    failed = [
        spec
        for name, spec in settings.hotkeys.items()
        if name in actions and not hotkeys.register(spec, actions[name])
    ]
    tray = build_tray(app, ctrl)
    if not win32.IS_WIN:
        print("pi_tool: Windows requis pour suivre Dofus (overlay inactif).", file=sys.stderr)
    elif failed:
        tray.showMessage("pi_tool", f"Raccourcis indisponibles : {', '.join(failed)}")

    timer = QTimer()
    timer.timeout.connect(ctrl.tick)
    timer.start(settings.poll_ms)
    app.aboutToQuit.connect(hotkeys.unregister_all)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
