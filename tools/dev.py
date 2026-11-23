"""Single dev entry point with terse output (token-cheap).

./dev check            lint + layer/graph check + all tests; prints 1 line when green
./dev test [ARGS]      pytest passthrough (e.g. ./dev test tests/test_grid.py -k fit)
./dev affected         run only tests affected by uncommitted changes (vs HEAD)
./dev graph            rebuild CODEGRAPH.md
./dev view IMG [x y w h] [--max 800]   crop+downscale an image to .cache/view/ for cheap viewing
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
    if cmd == "view":
        return view(args)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
