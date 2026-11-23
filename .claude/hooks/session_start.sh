#!/usr/bin/env bash
# SessionStart: install deps in cloud sessions (Linux: core + vision only). Silent.
[[ "$CLAUDE_CODE_REMOTE" == "true" ]] || exit 0
cd "$CLAUDE_PROJECT_DIR" && uv sync --quiet --extra vision >/dev/null 2>&1
exit 0
