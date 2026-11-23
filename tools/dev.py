"""Single dev entry point with terse output (token-cheap).

./dev check            lint + layer/graph check + all tests; prints 1 line when green
./dev test [ARGS]      pytest passthrough (e.g. ./dev test tests/test_grid.py -k fit)
./dev affected         run only tests affected by uncommitted changes (vs HEAD)
./dev graph            rebuild CODEGRAPH.md
./dev view IMG [x y w h] [--max 800]   crop+downscale an image to .cache/view/ for cheap viewing
./dev render IMG [--ids]  calibrated grid drawn on a capture (needs sidecar .json)
./dev digits           V2.4: learn HP digit templates from annotated captures, then validate
./dev eval             V2.2/V2.4: precision/recall of circles + HP reads on annotated captures
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(cmd: list[str], quiet: bool = True) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=quiet, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def tail(text: str, n: int = 60) -> str:
    lines = text.strip().splitlines()
    return "\n".join((["…"] if len(lines) > n else []) + lines[-n:])


def check() -> int:
    run(["ruff", "check", "--fix", "-q", "."])
    run(["ruff", "format", "-q", "."])
    run([PY, "tools/codegraph.py", "build"])
    for name, cmd in [
        ("ruff", ["ruff", "check", "-q", "."]),
        ("graph", [PY, "tools/codegraph.py", "check"]),
    ]:
        code, out = run(cmd)
        if code:
            print(f"FAIL {name}\n{tail(out)}")
            return 1
    code, out = run([PY, "-m", "pytest", "-q", "-x"])
    if code:
        print(f"FAIL tests\n{tail(out)}")
        return 1
    print("OK " + (out.strip().splitlines() or ["(no tests)"])[-1])
    return 0


def affected() -> int:
    _, diff = run(["git", "diff", "--name-only", "HEAD"])
    _, new = run(["git", "ls-files", "--others", "--exclude-standard"])
    paths = [p for p in (diff + new).split() if p.endswith(".py")]
    _, tests = run([PY, "tools/codegraph.py", "tests", *paths])
    tests = tests.split()
    if not tests:
        print("no affected tests")
        return 0
    code, out = run([PY, "-m", "pytest", "-q", *tests])
    print(tail(out, 40))
    return code


def view(args: list[str]) -> int:
    import cv2  # vision extra

    max_side = 800
    if "--max" in args:
        i = args.index("--max")
        max_side = int(args[i + 1])
        del args[i : i + 2]
    img = cv2.imread(args[0])
    if img is None:
        print(f"cannot read {args[0]}")
        return 1
    if len(args) == 5:
        x, y, w, h = map(int, args[1:])
        img = img[y : y + h, x : x + w]
    s = min(1.0, max_side / max(img.shape[:2]))
    if s < 1:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    out = ROOT / ".cache" / "view" / (Path(args[0]).stem + ".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img)
    print(f"{out} {img.shape[1]}x{img.shape[0]} scale={s:.3f}")
    return 0


def render(args: list[str]) -> int:
    """V1.4: compare the grid to a real capture; prints the calibration fit residual."""
    import json

    import cv2

    from pi_tool.core.calibration import from_annotation
    from pi_tool.core.map_model import load_map
    from pi_tool.core.scene import GridStyle, grid_scene
    from pi_tool.vision.render import draw_scene

    img_path = Path(args[0])
    side = img_path.with_suffix(".json")
    if not side.exists():
        print(f"no sidecar {side} (calibrate it with: uv run pi-tool-map {img_path})")
        return 1
    cal, residual = from_annotation(json.loads(side.read_text(encoding="utf-8")))
    if cal is None:
        print("sidecar has no calib_points/calibration")
        return 1
    img = cv2.imread(str(img_path))
    style = GridStyle(show_ids="--ids" in args, show_outside=True)
    out = ROOT / ".cache" / "view" / f"{img_path.stem}_grid.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), draw_scene(img, grid_scene(load_map(), cal, style)))
    res = f" fit_residual_max={residual:.2f}px" if residual is not None else ""
    print(f"{out}{res} cell_w={2 * abs(cal.u[0]):.1f}px")
    return 0


def _fixtures() -> list[tuple[Path, dict]]:
    import json

    screens = ROOT / "tests" / "fixtures" / "screens"
    return [
        (p.with_suffix(".png"), json.loads(p.read_text(encoding="utf-8")))
        for p in sorted(screens.glob("*.json"))
        if p.with_suffix(".png").exists()
    ]


def _hp_roi(img, ann):
    x, y, w, h = ann["hp_roi"]
    return img[y : y + h, x : x + w]


def digits() -> int:
    """Learn glyph templates from every capture with hp_pct + hp_roi; validated only if the
    merged templates read back every capture correctly and cover all ten digits."""
    import cv2

    from pi_tool.vision import hp_ocr

    caps = [(p, a) for p, a in _fixtures() if "hp_pct" in a and "hp_roi" in a]
    samples = []
    for p, a in caps:
        try:
            samples.append(hp_ocr.learn(_hp_roi(cv2.imread(str(p)), a), f"{a['hp_pct']}%"))
        except ValueError as e:
            print(f"skip {p.name}: {e}")
    if not samples:
        print("aucune capture avec hp_pct + hp_roi dans tests/fixtures/screens")
        return 1
    t = hp_ocr.Templates(hp_ocr.merge(samples))
    if not t.complete:
        missing = sorted(set("0123456789") - set(t.glyphs))
        print(f"{len(samples)} captures; chiffres manquants : {' '.join(missing)}")
    bad = [
        (p.name, a["hp_pct"], r.value, r.reason)
        for p, a in caps
        if (r := hp_ocr.read_hp(_hp_roi(cv2.imread(str(p)), a), t)).value != a["hp_pct"]
    ]
    for row in bad:
        print("FAIL {} expected={} got={} ({})".format(*row))
    t = hp_ocr.Templates(t.glyphs, validated=t.complete and not bad and len(caps) >= 5)
    hp_ocr.save_templates(t)
    print(f"{len(t.glyphs)} glyphes -> {hp_ocr.DATA_DIR} validated={t.validated}")
    return 0 if t.validated else 1


def evaluate() -> int:
    """Per-capture diff + overall precision/recall (write the numbers in docs/LIMITS.md)."""
    import cv2

    from pi_tool.core.calibration import from_annotation
    from pi_tool.core.grid import CELL_COUNT
    from pi_tool.core.map_model import load_map
    from pi_tool.vision import hp_ocr
    from pi_tool.vision.circles import detect_circles, split_teams

    m, t = load_map(), hp_ocr.load_templates()
    tp = fp = fn = hp_ok = hp_n = hp_none = 0
    for p, a in _fixtures():
        img = cv2.imread(str(p))
        cal, _ = from_annotation(a)
        line = [p.name]
        if cal is not None and ("allies" in a or "enemies" in a):
            got_a, got_e = split_teams(
                detect_circles(img, cal, filter(m.walkable, range(CELL_COUNT)))
            )
            for want, got, tag in (
                (set(a.get("allies", [])), got_a, "A"),
                (set(a.get("enemies", [])), got_e, "E"),
            ):
                tp, fp, fn = tp + len(want & got), fp + len(got - want), fn + len(want - got)
                if want != got:
                    line.append(f"{tag} miss={sorted(want - got)} extra={sorted(got - want)}")
        if "hp_pct" in a and "hp_roi" in a:
            r = hp_ocr.read_hp(_hp_roi(img, a), t)
            hp_n += 1
            hp_ok += r.value == a["hp_pct"]
            hp_none += r.value is None
            if r.value != a["hp_pct"]:
                line.append(f"HP {a['hp_pct']}->{r.value} ({r.reason})")
        if len(line) > 1:
            print(" ".join(line))
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    print(f"circles: precision={prec:.3f} recall={rec:.3f} (tp={tp} fp={fp} fn={fn})")
    wrong = hp_n - hp_ok - hp_none
    print(f"hp: {hp_ok}/{hp_n} exact, {hp_none} refused, {wrong} WRONG (must be 0)")
    return 0


def main(argv: list[str]) -> int:
    cmd, args = (argv[0], argv[1:]) if argv else ("check", [])
    if cmd == "check":
        return check()
    if cmd == "test":
        return subprocess.call([PY, "-m", "pytest", *args], cwd=ROOT)
    if cmd == "affected":
        return affected()
    if cmd == "graph":
        return subprocess.call([PY, "tools/codegraph.py", "build"], cwd=ROOT)
    if cmd == "render":
        return render(args)
    if cmd == "digits":
        return digits()
    if cmd == "eval":
        return evaluate()
    if cmd == "view":
        return view(args)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
