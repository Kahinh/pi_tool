#!/usr/bin/env bash
# SessionStart: install deps in cloud sessions (Linux: core + vision only). Silent.
[[ "$CLAUDE_CODE_REMOTE" == "true" ]] || exit 0
# Qt offscreen tests need these system libs
ldconfig -p 2>/dev/null | grep -q libEGL.so.1 || apt-get install -y -qq libegl1 libxkbcommon0 >/dev/null 2>&1
cd "$CLAUDE_PROJECT_DIR" && uv sync --quiet --extra vision --extra win >/dev/null 2>&1
exit 0
