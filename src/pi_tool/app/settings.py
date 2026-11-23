"""User settings + config paths (JSON in %APPDATA%/pi_tool, override with PI_TOOL_CONFIG)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

DEFAULT_HOTKEYS = {
    "toggle_overlay": "Ctrl+Alt+O",
    "toggle_grid": "Ctrl+Alt+G",
    "toggle_ids": "Ctrl+Alt+I",
    "calibrate": "Ctrl+Alt+C",
    "quit": "Ctrl+Alt+Q",
}


def config_dir() -> Path:
    if env := os.environ.get("PI_TOOL_CONFIG"):
        return Path(env)
    base = os.environ.get("APPDATA") or Path.home() / ".config"
    return Path(base) / "pi_tool"


@dataclass
class Settings:
    overlay_visible: bool = True
    grid_visible: bool = True  # V1: the grid is the only content; V3.3 hides it by default
    show_ids: bool = False
    opacity: float = 0.6
    hide_when_unfocused: bool = True
    window_title: str = "Dofus"  # substring of the game window title
    window_class: str | None = "UnityWndClass"
    scale_mode: str = "fit"  # see core.calibration.ScaleMode
    poll_ms: int = 100
    hotkeys: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HOTKEYS))

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        path = path or config_dir() / "settings.json"
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        s = cls(**{k: v for k, v in raw.items() if k in known})
        s.hotkeys = {**DEFAULT_HOTKEYS, **s.hotkeys}
        return s

    def save(self, path: Path | None = None) -> None:
        path = path or config_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")
