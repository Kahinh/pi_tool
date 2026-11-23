---
name: issue
description: Implement a roadmap GitHub issue (V1.x/V2.x/V3.x, #1-#17) of kahinh/pi_tool end to end with minimal tokens. Use when asked to work on an issue number or a Vx.y item.
---

1. Fetch only what's needed: `mcp__github__issue_read` method `get` (owner `kahinh`, repo `pi_tool`). Parent issue (#1/#2/#3) only if the sub-issue body is ambiguous. Skip comments unless the body says "see comments".
2. Locate code in `CODEGRAPH.md`; pick the lowest layer that can hold the logic (core > vision > platform > app). Pure logic in `core` even if it serves the overlay.
3. Write the test first in `tests/test_<module>.py`. Real-capture tests: marker `fixtures` (skill `fixtures`). Windows-only: marker `win`, plus a manual checklist in `docs/LIMITS.md`.
4. Loop with `./dev affected`; finish with `./dev check`.
5. Append to `docs/LIMITS.md` under `## Vx.y (#n)`: what is validated, how (tests / captures / manual), known limits. 3–8 bullets.
6. Commit `Vx.y: <summary> (#n)`. Don't close issues or tick boxes unless the user asks: "validated" needs real-game checks the user does.

Data-dependent issues (#4 map, #13 PI rules, #10 player cue): if evidence (captures / observations) is missing, build the tooling + schema + tests, keep `validated: false`, and list precisely which captures the user must provide.
