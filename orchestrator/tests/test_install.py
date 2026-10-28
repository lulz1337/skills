"""Verify portable installation and retirement of version 2 without model calls."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BUNDLE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("orchestrator_install", BUNDLE / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
GUARD_COMMAND = 'python3 "$HOME/.agents/orchestrator-guard.py"'


class InstallationTests(unittest.TestCase):
    def test_clean_install_is_idempotent_and_preserves_other_files(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            other = home / ".agents/skills/custom/SKILL.md"
            other.parent.mkdir(parents=True)
            other.write_text("Unrelated skill")
            self.assertGreater(installer.install(home), 0)
            self.assertEqual(installer.install(home), 0)
            self.assertEqual(other.read_text(), "Unrelated skill")
            for path in (".agents/skills/orchestrator/SKILL.md", ".claude/skills/orchestrator/SKILL.md",
                         ".claude/agents/reviewer-standard.md", ".agents/codex-agents/reviewer.md",
                         ".agents/codex-agents/profiles/standard.md"):
                with self.subTest(path=path):
                    self.assertTrue((home / path).is_file())
            self.assertFalse((home / ".claude/settings.json").exists())

    def test_installed_runtime_finds_its_codex_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            installer.install(home)
            runtime = home / ".agents/orchestrator-runtime.py"
            # No codex on PATH keeps the test offline; the runtime falls back to the profile model.
            result = subprocess.run([sys.executable, str(runtime), "instructions", "hybrid", "standard"],
                                    capture_output=True, text=True, env={"PATH": "", "HOME": str(home)})
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {row.get("role"): row for row in map(json.loads, result.stdout.splitlines())}
            # The sandbox comes from the installed role file, so it proves the runtime read it.
            self.assertEqual(rows["reviewer"]["sandbox"], "read-only")

    def test_version_2_guard_skills_and_roles_are_retired(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            settings = home / ".claude/settings.json"
            hooks = home / ".codex/hooks.json"
            for target, command in ((settings, GUARD_COMMAND), (hooks, GUARD_COMMAND + " --provider codex")):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({"custom": "preserve", "hooks": {
                    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": command}]}],
                    "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "keep"},
                                                                  {"type": "command", "command": command}]}]}}))
            old = [home / ".agents/orchestrator-guard.py", home / ".agents/skills/orchestrator-hybrid/SKILL.md",
                   home / ".claude/skills/orchestrator-claude/SKILL.md", home / ".claude/agents/orch-scout-fast.md",
                   home / ".claude/agents/worker-hybrid-quick.md", home / ".agents/codex-agents/worker.md"]
            for path in old:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("version 2")
            installer.install(home)
            for path in old:
                with self.subTest(path=path):
                    self.assertFalse(path.exists())
            self.assertFalse((home / ".agents/skills/orchestrator-hybrid").exists())
            for target in (settings, hooks):
                data = json.loads(target.read_text())
                self.assertEqual(data["custom"], "preserve")
                self.assertEqual(data["hooks"], {"PreToolUse": [{"matcher": "Bash", "hooks": [
                    {"type": "command", "command": "keep"}]}]})

    def test_symlink_owned_by_another_checkout_is_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            home = root / "home"
            source = root / "owned.py"
            source.write_text("Preserve source checkout")
            (home / ".agents").mkdir(parents=True)
            (home / ".agents/orchestrator-runtime.py").symlink_to(source)
            with self.assertRaisesRegex(ValueError, "owning repository"):
                installer.install(home)
            self.assertEqual(source.read_text(), "Preserve source checkout")
            self.assertFalse((home / ".claude/agents").exists())

    def test_custom_codex_home_is_cleaned_without_creating_the_default(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder) / "home"
            codex = Path(folder) / "custom-codex"
            codex.mkdir()
            (codex / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [
                {"hooks": [{"command": GUARD_COMMAND + " --provider codex"}]}]}}))
            installer.install(home, codex)
            self.assertEqual(json.loads((codex / "hooks.json").read_text()), {})
            self.assertFalse((home / ".codex").exists())


if __name__ == "__main__":
    unittest.main()
