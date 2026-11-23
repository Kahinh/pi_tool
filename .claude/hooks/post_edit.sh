#!/usr/bin/env bash
# PostToolUse(Edit|Write): auto-format + lint the edited .py file, refresh CODEGRAPH.md.
# Silent on success (zero tokens). On lint errors: exit 2 so Claude sees only the errors.
f=$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("tool_input",{}).get("file_path",""))')
[[ "$f" == *.py ]] || exit 0
cd "$CLAUDE_PROJECT_DIR" || exit 0
R="uv run --quiet ruff"
$R format -q "$f" 2>/dev/null
$R check --fix -q "$f" >/dev/null 2>&1
out=$($R check -q --output-format concise "$f" 2>&1)
[[ "$f" == */src/* ]] && python3 tools/codegraph.py build >/dev/null 2>/tmp/cg_err
err=$(cat /tmp/cg_err 2>/dev/null); rm -f /tmp/cg_err
if [[ -n "$out$err" ]]; then echo "$out$err" | head -20 >&2; exit 2; fi
exit 0
