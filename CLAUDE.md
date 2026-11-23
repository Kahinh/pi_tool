# pi_tool

Windows overlay for Dofus Unity, Comte Harebourg fight: shows, per enemy, the cell to aim at so the PI-transformed spell lands on it. Roadmap = GitHub issues #1–#17 (V1 overlay/grid → V2 vision → V3 PI engine).

## Hard rules
- Visual analysis only: screen capture + overlay. NO input automation, NO memory reading, NO packet sniffing. Overlay must be click-through and never take focus.
- Never invent the PI formula or map data. Unvalidated data stays `"validated": false`; code must refuse/hide output rather than show a guess (skill `pi-rules`).
- Uncertain/stale detection ⇒ hide the indication, don't show it.

## Navigate cheaply
1. Read `CODEGRAPH.md` (auto-generated symbol map, `path:line`) before opening any file. Open only the lines you need.
2. `python3 tools/codegraph.py find X | deps M | rdeps M | tests PATH`.
3. Don't Read screenshots full-size: `./dev view IMG [x y w h]` → downscaled crop in `.cache/view/`.

## Layers (enforced by `./dev check`)
`core` (pure Python, no numpy/cv2/Qt/OS) ← `vision` (numpy/cv2 on BGR arrays) ; `platform` (Windows: Qt overlay, capture, window/DPI) ← `app` (wiring, state loop). `vision` and `platform` never import each other. Everything except `platform`/`app` must be testable on Linux.

## Commands
- `./dev check` — lint+format, graph/layer check, tests. One line when green. Run before every commit.
- `./dev render IMG` — calibrated grid drawn on a capture (needs sidecar .json).
- `./dev affected` — only tests touched by current diff (fast loop). `./dev test ARGS` — pytest passthrough.
- `./dev eval` — circles precision/recall + HP reads on annotated captures. `./dev digits` — learn HP digit templates (sets `validated` only if every capture reads back).
- Vision tests without captures use `tests/synth.py` (synthetic floor/rings/heart).
- Windows: `dev.cmd …`. Qt tests run offscreen on Linux (needs libegl1).
- Entry points: `pi-tool` (app/main.py), `pi-tool-map CAPTURE` (map editor).
- A hook auto-formats edited .py files and refreshes CODEGRAPH.md; it only speaks on errors.

## Workflow
Issue work → skill `issue`. Geometry → `grid`. PI rules → `pi-rules`. Screenshots/annotations/eval → `fixtures`. Overlay/capture/DPI → `win-platform`.
Results & limits per issue go in `docs/LIMITS.md` (French, terse). Commit: `V1.1: <what> (#4)`.
