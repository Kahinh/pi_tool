---
name: grid
description: Dofus isometric grid conventions (cell ids, map coords, screen affine calibration, rotations, diamonds). Use for any code touching cells, calibration, overlay drawing or PI geometry.
---

Implementation: `src/pi_tool/core/grid.py` (tested exhaustively on all 560 cells). Don't re-derive; reuse.

- 560 cells = 14 cols × 40 staggered rows. `cell = row*14 + col`; odd rows shifted right by half a cell.
- Map coords (x, y) (Dofus MapPoint convention): cell 0 = (0,0), cell 1 = (1,1), cell 14 = (1,0), cell 28 = (1,-1). Axes follow the iso diagonals; a cell is a unit square ⇒ rotations (`rotate90`), symmetries, distance (Manhattan) are exact integer ops. `xy_to_cell` returns None off-map.
- Screen: `Calibration` affine `p = origin + x·u + y·v`, in client-area **physical** pixels. Ideal basis `u=(W/2,H/2)`, `v=(W/2,-H/2)`. `Calibration.fit` (≥3 non-collinear reference cells, least squares) handles any resolution, black bars, ultrawide, zoom. `cell_at(px,py)` is exact (round fractional map coords).
- Calibration profile = origin/u/v relative to the game client rect, so window move/resize = re-anchor, not re-fit (check aspect changes against captures: Unity may letterbox).
- Open questions to validate on captures (record in docs/LIMITS.md): whether Unity keeps the 560-cell layout for Harebourg; screen direction of `rotate90(+1)` (y axis points up-right on screen).
