---
name: fixtures
description: Annotated real game screenshots (tests/fixtures/screens) - format, cheap viewing, and writing integration/eval tests for grid alignment, circle detection, player identification and HP OCR. Use when adding captures or testing anything in vision/.
---

Layout: `tests/fixtures/screens/<name>.png` + `<name>.json` sidecar (ground truth, written by the user or confirmed by them):
```json
{"resolution": [2560, 1080], "dpi_scale": 1.25, "mode": "windowed|borderless",
 "client_rect": [0, 0, 2560, 1080],
 "calib_points": [[cell, px, py], ...],
 "allies": [cell, ...], "enemies": [cell, ...], "player": cell, "hp_pct": 85,
 "hp_roi": [x, y, w, h], "notes": ""}
```
All keys optional except `resolution`; tests skip what's absent. Name files `<res>_<scenario>_<nn>` (e.g. `2560x1080_occlusion_01`).

Token rules: never Read a full-size capture. `./dev view IMG x y w h --max 600` then Read the output. Prefer numeric checks (tests printing per-cell diffs) over looking at images.

Tests: mark `@pytest.mark.fixtures`, iterate sidecars via a shared `conftest` loader, assert per field and print a compact diff table on failure (cell expected/got). Report precision/recall for detection in `docs/LIMITS.md`.
Captures may be large: keep PNGs ≤ ~1 MB (crop to the game client) to keep the repo light.
