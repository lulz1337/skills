#!/usr/bin/env python3
"""Install the shared runtime, roles and session guards from this checkout."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile

BUNDLE = Path(__file__).resolve().parent
FAMILIES = ("claude", "codex", "hybrid")


def hook_merge(data, provider):
    spec = importlib.util.spec_from_file_location("orchestrator_hooks", BUNDLE / "apply-codex-hooks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if provider == "claude":
        module.COMMAND = 'python3 "$HOME/.agents/orchestrator-guard.py"'
    return module.merge(data)


def install(home, codex_home=None):
    home = Path(home).resolve()
    codex_home = Path(codex_home).resolve() if codex_home else home / ".codex"
    agents = home / ".agents"
    files = {}
    for name in ("orchestrator-runtime.py", "orchestrator-guard.py"):
        files[agents / name] = (BUNDLE / name).read_bytes()
    for name in ("claude-agents", "codex-agents"):
        for source in (BUNDLE / name).rglob("*.md"):
            files[agents / name / source.relative_to(BUNDLE / name)] = source.read_bytes()
            if name == "claude-agents":
                files[home / ".claude/agents" / source.name] = source.read_bytes()
    for family in FAMILIES:
        root = BUNDLE / "skills" / f"orchestrator-{family}"
        for source in root.rglob("*"):
            if source.is_file():
                relative = source.relative_to(root)
                files[agents / "skills" / root.name / relative] = source.read_bytes()
                files[home / ".claude/skills" / root.name / relative] = source.read_bytes()
    for provider, target in (("claude", home / ".claude/settings.json"), ("codex", codex_home / "hooks.json")):
        original = json.loads(target.read_text()) if target.exists() else {}
        files[target] = (json.dumps(hook_merge(original, provider), indent=2) + "\n").encode()

    changed = {target: content for target, content in files.items()
               if not target.is_file() or target.read_bytes() != content}
    # A managed symlink belongs to its source repository. Reject the whole
    # installation before changing anything rather than writing through it.
    for target in changed:
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
            raise ValueError(f"{target} is managed through a symlink; update its owning repository")
    for target, content in changed.items():
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
    return len(changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, help="Installation home; defaults to the current user's home")
    parser.add_argument("--codex-home", type=Path, help="Codex configuration directory")
    args = parser.parse_args()
    codex_home = args.codex_home
    if codex_home is None and args.home is None and os.environ.get("CODEX_HOME"):
        codex_home = Path(os.environ["CODEX_HOME"])
    count = install(args.home or Path.home(), codex_home)
    print(f"Orchestrator files updated: {count}. Restart Claude Code; enable and trust native Codex hooks in /hooks.")


if __name__ == "__main__":
    main()
