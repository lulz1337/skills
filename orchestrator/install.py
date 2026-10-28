#!/usr/bin/env python3
"""Install the orchestrator skill, its agents and runtime from this checkout."""

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

BUNDLE = Path(__file__).resolve().parent
SKILL = BUNDLE.parent / "skills" / "orchestrator"
MODES = ("quick", "fast", "standard", "comprehensive")

# Version 2 shipped three orchestrators, eleven roles, workers and a session guard. A
# machine that installed it keeps them until this installer removes them; the
# guard hooks then fail on every prompt once their script is gone.
RETIRED_SKILLS = ("orchestrator-claude", "orchestrator-codex", "orchestrator-hybrid")
RETIRED_CLAUDE_AGENTS = tuple(
    [f"orch-{role}-{mode}.md" for role in ("browser", "oracle", "publisher", "researcher",
                                           "runner", "sage", "scout", "verifier") for mode in MODES]
    + [f"{name}-{mode}.md" for name in ("orch-critic", "worker", "worker-hybrid") for mode in MODES])
RETIRED_CODEX_ROLES = tuple(f"{name}.md" for name in ("browser", "oracle", "researcher", "runner", "sage",
                                                      "scout", "verifier", "worker") + MODES)
GUARD = "orchestrator-guard"


def owned_elsewhere(path):
    return path.is_symlink() or any(parent.is_symlink() for parent in path.parents)


def without_guard(data):
    """The hook configuration with every orchestrator guard handler removed."""
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return data
    cleaned = {}
    for event, groups in hooks.items():
        kept = []
        for group in groups if isinstance(groups, list) else []:
            handlers = [h for h in group.get("hooks", []) if GUARD not in str(h.get("command", ""))]
            if handlers:
                kept.append({**group, "hooks": handlers})
        if kept:
            cleaned[event] = kept
    result = {**data, "hooks": cleaned}
    if not cleaned:
        del result["hooks"]
    return result


def planned_files(home):
    agents = home / ".agents"
    files = {agents / "orchestrator-runtime.py": (BUNDLE / "orchestrator-runtime.py").read_bytes()}
    for source in (SKILL / "roles").rglob("*.md"):
        files[agents / "codex-agents" / source.relative_to(SKILL / "roles")] = source.read_bytes()
    for source in (SKILL / "agents").glob("*.md"):
        files[home / ".claude/agents" / source.name] = source.read_bytes()
    for source in SKILL.rglob("*"):
        if source.is_file():
            relative = source.relative_to(SKILL)
            for root in (agents / "skills", home / ".claude/skills"):
                files[root / "orchestrator" / relative] = source.read_bytes()
    return files


def retired_paths(home):
    agents = home / ".agents"
    paths = [agents / f"{GUARD}.py"]
    for name in RETIRED_SKILLS:
        paths += [agents / "skills" / name, home / ".claude/skills" / name]
    for name in RETIRED_CLAUDE_AGENTS:
        paths += [home / ".claude/agents" / name, agents / "claude-agents" / name]
    paths += [agents / "codex-agents" / name for name in RETIRED_CODEX_ROLES]
    return [path for path in paths if path.exists() or path.is_symlink()]


def write(target, content):
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o600 if target.suffix == ".json" else 0o644
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".orchestrator-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.chmod(temporary, mode)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


def install(home, codex_home=None):
    home = Path(home).resolve()
    codex_home = Path(codex_home).resolve() if codex_home else home / ".codex"
    files = planned_files(home)
    for target in (home / ".claude/settings.json", codex_home / "hooks.json"):
        if target.is_file():
            original = json.loads(target.read_text())
            cleaned = without_guard(original)
            if cleaned != original:
                files[target] = (json.dumps(cleaned, indent=2) + "\n").encode()

    changed = {target: content for target, content in files.items()
               if not target.is_file() or target.read_bytes() != content}
    removed = retired_paths(home)
    # A managed symlink belongs to its source repository. Reject the whole
    # installation before changing anything rather than writing through it.
    for target in list(changed) + removed:
        if owned_elsewhere(target):
            raise ValueError(f"{target} is managed through a symlink; update its owning repository")
    for target, content in changed.items():
        write(target, content)
    for path in removed:
        shutil.rmtree(path) if path.is_dir() else path.unlink()
    return len(changed) + len(removed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, help="Installation home; defaults to the current user's home")
    parser.add_argument("--codex-home", type=Path, help="Codex configuration directory")
    args = parser.parse_args()
    codex_home = args.codex_home
    if codex_home is None and args.home is None and os.environ.get("CODEX_HOME"):
        codex_home = Path(os.environ["CODEX_HOME"])
    count = install(args.home or Path.home(), codex_home)
    print(f"Orchestrator files changed: {count}. Restart Claude Code to load the skill and agents.")


if __name__ == "__main__":
    main()
