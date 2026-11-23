---
name: pi-rules
description: Protocol for researching, recording and validating the Harebourg PI rule (HP thresholds, rotations, rounding) and implementing the PI engine. Use for issues #13, #14, #16, #17 or any question about how the PI transforms a target.
---

Status lives in `data/pi_rules.json` (`validated`). The engine (`core/pi_engine.py`) raises `RuleNotValidatedError` while false — keep it that way until evidence exists.

Evidence = rows in `docs/research/pi_observations.csv`: player cell, HP % (heart), clicked cell, observed impact cell, capture filename (in `tests/fixtures/screens/`). Derive the rule from rows; never from memory or forum claims alone (cite sources in `docs/research/pi_rules.md` as hypotheses).

Validation bar before `validated: true`:
- ≥2 observations per HP band and per rotation, including values exactly on each threshold (rounding!).
- Every observation reproduced by `pi_engine` in a parametrized test reading the CSV.
- Unknowns (center of rotation = player? map? dependence on spell/orientation?) explicitly resolved or listed.

Engine design: forward `apply_pi(player, clicked, hp) -> impact` from rules; `target_cell` = inverse (for rotations: rotate by −k). Test `apply_pi(target_cell(...)) == enemy` for all cells. Status codes in `TargetStatus`; range/LoS are NOT evaluated — say so in UI.
