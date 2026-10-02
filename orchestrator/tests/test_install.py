"""Verify portable installation and tool boundaries without model calls."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BUNDLE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("orchestrator_install", BUNDLE / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallationTests(unittest.TestCase):
    def test_clean_install_is_idempotent_and_preserves_other_hooks_and_skills(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            settings = home / ".claude/settings.json"
            settings.parent.mkdir()
            settings.write_text(json.dumps({"custom": "preserve", "hooks": {"SessionStart": [{"hooks": [{"command": "machine-hook"}]}]}}))
            other = home / ".agents/skills/custom/SKILL.md"
            other.parent.mkdir(parents=True); other.write_text("Unrelated skill")
            self.assertGreater(installer.install(home), 0)
            self.assertEqual(installer.install(home), 0)
            self.assertEqual(other.read_text(), "Unrelated skill")
            data = json.loads(settings.read_text())
            self.assertEqual(data["custom"], "preserve")
            self.assertEqual(data["hooks"]["SessionStart"][0]["hooks"][0]["command"], "machine-hook")
            runtime = home / ".agents/orchestrator-runtime.py"
            result = subprocess.run([sys.executable, str(runtime), "instructions", "claude", "standard"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"agent_type": "orch-runner-standard"', result.stdout)
            guard = home / ".agents/orchestrator-guard.py"
            env = {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}
            for event in ({"hook_event_name": "UserPromptSubmit", "prompt": "/orchestrator-claude standard"},
                          {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "source.py"}}):
                result = subprocess.run([sys.executable, str(guard)], input=json.dumps({"session_id": "portable", **event}), env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_symlink_owned_by_another_checkout_is_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); home = root / "home"; source = root / "owned.py"
            source.write_text("Preserve source checkout")
            (home / ".agents").mkdir(parents=True)
            (home / ".agents/orchestrator-guard.py").symlink_to(source)
            with self.assertRaisesRegex(ValueError, "owning repository"):
                installer.install(home)
            self.assertEqual(source.read_text(), "Preserve source checkout")
            self.assertFalse((home / ".agents/orchestrator-runtime.py").exists())

    def test_custom_codex_home_receives_hooks_without_changing_default(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder) / "home"; codex = Path(folder) / "custom-codex"
            installer.install(home, codex)
            self.assertTrue((codex / "hooks.json").is_file())
            self.assertFalse((home / ".codex/hooks.json").exists())
