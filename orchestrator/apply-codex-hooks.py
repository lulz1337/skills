#!/usr/bin/env python3
"""Merge the orchestration guard into local Codex hooks without replacing other hooks."""

import json
import os
from pathlib import Path
import sys

COMMAND = 'python3 "$HOME/.agents/orchestrator-guard.py" --provider codex'
EVENTS = ("UserPromptSubmit", "PreToolUse")


def merge(data):
    result = json.loads(json.dumps(data))
    hooks = result.setdefault("hooks", {})
    for event in EVENTS:
        groups = hooks.setdefault(event, [])
        # Retire only this managed handler. Preserve every unrelated handler,
        # including one that shares its matcher group.
        cleaned = []
        for group in groups:
            handlers = [h for h in group.get("hooks", []) if h.get("command") != COMMAND]
            if handlers:
                cleaned.append({**group, "hooks": handlers})
        cleaned.append({"hooks": [{"type": "command", "command": COMMAND,
                                   "timeout": 10, "statusMessage": "Orchestrator tool boundary"}]})
        hooks[event] = cleaned
    return result


def main():
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    target = codex_home / "hooks.json"
    data = json.loads(target.read_text()) if target.exists() else {}
    result = merge(data)
    if sys.argv[1:] == ["--check"]:
        return 0 if result == data else 1
    if result != data:
        codex_home.mkdir(parents=True, exist_ok=True)
        # Keep the file's mode and a pre-existing symlink, if another tool owns it.
        target.write_text(json.dumps(result, indent=2) + "\n")
        print("Codex orchestrator hooks installed; review new hooks with /hooks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
