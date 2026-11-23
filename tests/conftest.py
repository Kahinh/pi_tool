import json
import sys
from pathlib import Path

import pytest

SCREENS = Path(__file__).parent / "fixtures" / "screens"


def screen_fixtures() -> list[tuple[Path, dict]]:
    """(png, annotation) pairs; see skill `fixtures` for the sidecar format."""
    return [
        (p.with_suffix(".png"), json.loads(p.read_text(encoding="utf-8")))
        for p in sorted(SCREENS.glob("*.json"))
        if p.with_suffix(".png").exists()
    ]


def pytest_collection_modifyitems(config, items):
    skip_win = pytest.mark.skip(reason="Windows + display only")
    for item in items:
        if "win" in item.keywords and sys.platform != "win32":
            item.add_marker(skip_win)
