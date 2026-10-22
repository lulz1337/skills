#!/usr/bin/env python3
"""Merge the orchestration guard into local Codex hooks without replacing other hooks."""

import json
import os
from pathlib import Path
import sys

COMMAND = 'python3 "$HOME/.agents/orchestrator-guard.py" --provider codex'
EVENTS = ("UserPromptSubmit", "PreToolUse")


def handler():
    """Return the managed handler for the current COMMAND.

    install.py replaces COMMAND for Claude settings after loading this module,
    so the handler is built on each call rather than once at import.
    """
    return {"type": "command", "command": COMMAND, "timeout": 10, "statusMessage": "Orchestrator tool boundary"}


def merge(data):
    result = json.loads(json.dumps(data))
    hooks = result.setdefault("hooks", {})
    for event in EVENTS:
        groups = hooks.setdefault(event, [])
        # Already installed once, in its own group: keep its position. Moving it
        # to the end on every run undoes an order that another hook manager
        # relies on, and that manager then moves its own handler back.
        ours = [g for g in groups if any(h.get("command") == COMMAND for h in g.get("hooks", []))]
        if ours == [{"hooks": [handler()]}]:
            continue
        # Retire only this managed handler. Preserve every unrelated handler,
        # including one that shares its matcher group.
        cleaned = []
        for group in groups:
            handlers = [h for h in group.get("hooks", []) if h.get("command") != COMMAND]
            if handlers:
                cleaned.append({**group, "hooks": handlers})
        cleaned.append({"hooks": [handler()]})
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
