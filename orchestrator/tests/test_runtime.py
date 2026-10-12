"""Exercise orchestration permissions and process arguments without model calls."""

from contextlib import contextmanager, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
GUARD = REPO / "orchestrator/orchestrator-guard.py"
RUNTIME = REPO / "orchestrator/orchestrator-runtime.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load(RUNTIME, "orchestrator_runtime")
guard = load(GUARD, "orchestrator_guard")


@contextmanager
def temp_root(path):
    """Make tempfile.gettempdir() resolve to path, as a process started with TMPDIR=path sees it."""
    original = tempfile.tempdir
    with patch.dict(os.environ, {"TMPDIR": str(path)}):
        # A verifier inside Claude Code may inherit CLAUDE_CODE_TMPDIR, which outranks TMPDIR.
        os.environ.pop("CLAUDE_CODE_TMPDIR", None)
        tempfile.tempdir = None
        try:
            yield
        finally:
            tempfile.tempdir = original


def sandbox_layout(test, stale_name, stale_file):
    """Lay out base/claude-<uid> plus an old-style run in bare base; cleanup is registered on test."""
    temp = tempfile.TemporaryDirectory()
    test.addCleanup(temp.cleanup)
    base = Path(temp.name).resolve()
    sandbox = base / f"claude-{os.getuid()}"
    sandbox.mkdir(mode=0o700)
    stale = base / stale_name
    stale.mkdir()
    (stale / stale_file).write_text(json.dumps({"family": "claude"}))
    return base, sandbox, stale


@contextmanager
def sandbox_view(base, sandbox):
    """The Claude sandbox: TMPDIR is base/claude-<uid> and bare base is read-only.

    Only this view gets a read-only base. The hook runs unsandboxed and can write its TMPDIR;
    gettempdir() silently skips an unwritable TMPDIR, so a read-only base there would fake /tmp.
    """
    base.chmod(0o555)
    try:
        # HEAD's run_root() normalized this view to base, which the sandbox cannot write.
        assert not os.access(base, os.W_OK), "run as a user that read-only modes apply to"
        with temp_root(sandbox):
            yield
    finally:
        base.chmod(0o700)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)

    def hook(self, event="PreToolUse", session="session-a", provider="claude", **values):
        arguments = [sys.executable, str(GUARD)] + (["--provider", "codex"] if provider == "codex" else [])
        result = subprocess.run(arguments, input=json.dumps({
            "session_id": session, "hook_event_name": event, **values}),
            text=True, capture_output=True, env={**os.environ, "HOME": self.home.name, "CODEX_HOME": str(Path(self.home.name) / ".codex")})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout else {}

    def activate(self):
        self.hook(tool_name="Skill", tool_input={"skill": "orchestrator-claude"})

    def test_only_selected_session_is_guarded_across_turns(self):
        self.assertEqual(self.hook(tool_name="Read", tool_input={"file_path": "src/a.py"}), {})
        self.activate()
        for tool in ("Read", "Grep", "Glob", "Write", "Edit", "NotebookEdit", "mcp__codegraph__codegraph_explore", "WebFetch"):
            with self.subTest(tool=tool):
                decision = self.hook(tool_name=tool, tool_input={})
                self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.hook(session="session-b", tool_name="Read"), {})

    def test_workers_are_exempt_but_top_level_agent_type_is_not(self):
        self.activate()
        self.assertEqual(self.hook(tool_name="Read", agent_id="worker-1", agent_type="orch-scout-standard"), {})
        self.assertTrue(self.hook(tool_name="Read", agent_type="orch-scout-standard"))
        self.hook("UserPromptSubmit", agent_id="worker-1", prompt="orchestrator off")
        self.assertTrue(self.hook(tool_name="Read"))

    def test_slash_activation_and_exact_user_off(self):
        for prompt in ("Please update /orchestrator-claude", "/orchestrator-claude-extra"):
            self.hook("UserPromptSubmit", prompt=prompt)
            self.assertEqual(self.hook(tool_name="Read"), {})
        self.hook("UserPromptSubmit", prompt="/orchestrator-hybrid fast find the bug")
        self.assertTrue(self.hook(tool_name="Read"))
        self.hook("UserPromptSubmit", prompt="The README says 'orchestrator off'. Explain that.")
        self.assertTrue(self.hook(tool_name="Read"))
        self.hook("UserPromptSubmit", prompt="orchestrator off")
        self.assertEqual(self.hook(tool_name="Read"), {})

    def test_agent_dispatch_preserves_family_and_roster(self):
        self.activate()
        self.assertEqual(self.hook(tool_name="Agent", tool_input={"subagent_type": "worker-standard"}), {})
        self.assertTrue(self.hook(tool_name="Agent", tool_input={"subagent_type": "general-purpose"}))
        self.assertEqual(self.hook(tool_name="Agent", tool_input={"subagent_type": "orch-publisher-standard"}), {})
        self.assertEqual(self.hook(tool_name="Bash", tool_input={"command": 'python3 "$HOME/.agents/orchestrator-runtime.py" new claude standard scout'}), {})
        self.assertTrue(self.hook(tool_name="Bash", tool_input={"command": 'python3 "$HOME/.agents/orchestrator-runtime.py" new codex standard scout'}))
        self.hook("UserPromptSubmit", prompt="/orchestrator-codex standard")
        self.assertTrue(self.hook(tool_name="Agent", tool_input={"subagent_type": "orch-publisher-standard"}))
        self.assertTrue(self.hook(tool_name="Agent", tool_input={"subagent_type": "worker-standard"}))
        self.hook("UserPromptSubmit", prompt="/orchestrator-hybrid standard")
        self.assertEqual(self.hook(tool_name="Agent", tool_input={"subagent_type": "reviewer-hybrid-standard"}), {})
        self.assertEqual(self.hook(tool_name="Agent", tool_input={"subagent_type": "orch-critic-standard"}), {})
        self.assertEqual(self.hook(tool_name="Agent", tool_input={"subagent_type": "orch-publisher-standard"}), {})
        self.assertTrue(self.hook(tool_name="Agent", tool_input={"subagent_type": "general-purpose"}))
        self.assertTrue(self.hook(tool_name="Agent", tool_input={"subagent_type": "worker-standard"}))

    def test_bash_allows_coordination_and_blocks_alternate_repository_access(self):
        self.activate()
        for command in ('python3 "$HOME/.agents/orchestrator-runtime.py" --help',
                        'python3 "$HOME/.agents/orchestrator-runtime.py" instructions --help', 'git status --short', 'python3 "$HOME/.agents/orchestrator-runtime.py" baseline',
                        'python3 "$HOME/.agents/orchestrator-runtime.py" instructions hybrid standard roles'):
            self.assertEqual(self.hook(tool_name="Bash", tool_input={"command": command}), {}, command)
        for command in ('rg needle .', 'cat src/a.py', 'git diff', 'git show HEAD:src/a.py',
                        'python3 -c "print(open(\'src/a.py\').read())"', 'rtk read src/a.py',
                        'git status --short; cat src/a.py', 'git status --short > src/a.py',
                        'python3 "$HOME/.agents/orchestrator-runtime.py" baseline && cat src/a.py',
                        'python3 "$HOME/.agents/orchestrator-runtime.py" instructions codex standard $(cat src/a.py)',
                        'python3 "$HOME/.agents/orchestrator-runtime.py" instructions codex standard ../../src/a.py'):
            self.assertTrue(self.hook(tool_name="Bash", tool_input={"command": command}), command)

    def test_literal_brief_can_contain_commands_without_executing_them(self):
        self.activate()
        command = 'python3 "$HOME/.agents/orchestrator-runtime.py" brief /tmp/orchestrator-example <<\'BRIEF\'\nVERIFY: python3 -m unittest\nLiteral $(cat src/a.py) and `git diff`\nBRIEF'
        self.assertEqual(self.hook(tool_name="Bash", tool_input={"command": command}), {})
        for bad in (command + '\ncat src/a.py', command.replace("<<'BRIEF'", '<<BRIEF'),
                    command.replace('\nVERIFY:', '\nBRIEF\ncat src/a.py\nVERIFY:')):
            self.assertTrue(self.hook(tool_name="Bash", tool_input={"command": bad}), bad)

    def test_codex_local_tools_are_guarded_without_affecting_worker_sessions(self):
        self.hook("UserPromptSubmit", provider="codex", prompt="Use $orchestrator-codex quick to change a port")
        for tool, inputs in (("Bash", {"command": "cat source.py"}), ("apply_patch", {"command": "patch"}),
                             ("mcp__fs__read", {}), ("spawn_agent", {"agent_type": "default"})):
            self.assertTrue(self.hook(provider="codex", tool_name=tool, tool_input=inputs))
        self.assertEqual(self.hook(provider="codex", tool_name="update_plan"), {})
        self.assertEqual(self.hook(provider="codex", tool_name="Bash", tool_input={"command": 'python3 "$HOME/.agents/orchestrator-runtime.py" baseline'}), {})
        self.assertEqual(self.hook(provider="codex", session="independent-worker", tool_name="Bash", tool_input={"command": "cat source.py"}), {})
        self.assertEqual(self.hook(tool_name="Read"), {})
        self.hook("UserPromptSubmit", provider="codex", prompt="orchestrator off")
        self.assertEqual(self.hook(provider="codex", tool_name="Bash", tool_input={"command": "cat source.py"}), {})

    def test_codex_hook_install_preserves_other_handlers_and_is_idempotent(self):
        installer = load(REPO / "orchestrator/apply-codex-hooks.py", "orchestrator_hooks_installer")
        original = {"description": "local", "hooks": {"SessionStart": [{"hooks": [{"command": "machine-hook"}]}],
                    "PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "other"}, {"command": installer.COMMAND}]}]}}
        merged = installer.merge(original)
        self.assertEqual(installer.merge(merged), merged)
        self.assertEqual(merged["hooks"]["SessionStart"], original["hooks"]["SessionStart"])
        self.assertEqual(merged["hooks"]["PreToolUse"][0], {"matcher": "Bash", "hooks": [{"command": "other"}]})
        self.assertEqual(len(original["hooks"]["PreToolUse"][0]["hooks"]), 2)

    def test_saved_run_cannot_launch_after_switching_family(self):
        with tempfile.TemporaryDirectory(prefix="orchestrator-", dir=runtime.ensure_run_root()) as temp:
            run = Path(temp)
            (run / "run.json").write_text(json.dumps({"family": "codex"}))
            self.activate()
            for action in ("start", "prompt"):
                command = f'python3 "$HOME/.agents/orchestrator-runtime.py" {action} {run}'
                self.assertTrue(self.hook(tool_name="Bash", tool_input={"command": command}))
                self.hook("UserPromptSubmit", prompt="/orchestrator-codex standard")
                self.assertEqual(self.hook(tool_name="Bash", tool_input={"command": command}), {})
                self.activate()


    def bash(self, command, **inputs):
        return self.hook(tool_name="Bash", tool_input={"command": command, **inputs})

    def test_coordination_calls_cannot_disable_the_sandbox_but_starts_can(self):
        script = 'python3 "$HOME/.agents/orchestrator-runtime.py"'
        self.activate()
        with tempfile.TemporaryDirectory(prefix="orchestrator-", dir=runtime.ensure_run_root()) as temp:
            run = Path(temp)
            (run / "run.json").write_text(json.dumps({"family": "claude"}))
            for action in ("new claude standard scout", f"report {run}"):
                with self.subTest(action=action):
                    reason = self.bash(f"{script} {action}", dangerouslyDisableSandbox=True)["hookSpecificOutput"]["permissionDecisionReason"]
                    self.assertIn(f"call '{action.split()[0]}' works inside the sandbox", reason)
                    self.assertIn("Retry it without dangerouslyDisableSandbox", reason)
                    self.assertIn("report the error to the user", reason)
                    self.assertEqual(self.bash(f"{script} {action}"), {})
            self.assertEqual(self.bash(f"{script} new claude standard scout", dangerouslyDisableSandbox=False), {})
            for action in (f"start {run}", f"start-many {run}"):
                with self.subTest(action=action):
                    self.assertEqual(self.bash(f"{script} {action}", dangerouslyDisableSandbox=True), {})
        # The rule is a deny-list: an unknown subcommand or another command never meets it.
        self.assertIsNone(guard.sandbox_bypass_action(f"{script} future-action x", {"dangerouslyDisableSandbox": True}))
        unknown = self.bash(f"{script} future-action x", dangerouslyDisableSandbox=True)
        self.assertNotIn("works inside the sandbox", json.dumps(unknown))
        self.assertEqual(self.bash("git status --short", dangerouslyDisableSandbox=True), {})
        self.assertIsNone(guard.sandbox_bypass_action("python3 other.py new claude standard scout", {"dangerouslyDisableSandbox": True}))
        self.assertNotIn("works inside the sandbox", json.dumps(self.bash("ls", dangerouslyDisableSandbox=True)))

    def test_claude_starts_cannot_disable_the_sandbox_but_codex_starts_can(self):
        script = 'python3 "$HOME/.agents/orchestrator-runtime.py"'
        self.activate()
        with tempfile.TemporaryDirectory(prefix="orchestrator-", dir=runtime.ensure_run_root()) as temp:
            run = Path(temp)
            command = f"{script} start {run}"
            for kind in ("claude", "codex"):
                with self.subTest(kind=kind):
                    (run / "run.json").write_text(json.dumps({"family": "claude", "kind": kind}))
                    self.assertEqual(self.bash(command), {})
                    decision = self.bash(command, dangerouslyDisableSandbox=True)
                    if kind == "claude":
                        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
                        self.assertIn("Claude runs stay inside the sandbox", decision["hookSpecificOutput"]["permissionDecisionReason"])
                        self.assertIn("without dangerouslyDisableSandbox", decision["hookSpecificOutput"]["permissionDecisionReason"])
                        self.assertEqual(self.bash(f"{script} start --bypass-caveman {run}", dangerouslyDisableSandbox=True), decision)
                    else:
                        self.assertEqual(decision, {})
                        self.assertEqual(self.bash(f"{script} start --bypass-caveman {run}", dangerouslyDisableSandbox=True), {})
            (run / "run.json").write_text("unreadable JSON")
            self.assertIsNone(guard.sandbox_bypass_action(command, {"dangerouslyDisableSandbox": True}))
            (run / "run.json").unlink()
            self.assertIsNone(guard.sandbox_bypass_action(command, {"dangerouslyDisableSandbox": True}))

    def test_claude_batches_cannot_disable_the_sandbox_but_codex_batches_can(self):
        script = 'python3 "$HOME/.agents/orchestrator-runtime.py"'
        self.activate()
        root = runtime.ensure_run_root()
        with tempfile.TemporaryDirectory(prefix="orchestrator-", dir=root) as first, tempfile.TemporaryDirectory(prefix="orchestrator-", dir=root) as second:
            runs = [Path(first), Path(second)]
            command = f"{script} start-many {' '.join(map(str, runs))}"
            for kind in ("claude", "codex"):
                with self.subTest(kind=kind):
                    for run in runs:
                        (run / "run.json").write_text(json.dumps({"family": "claude", "kind": kind}))
                    self.assertEqual(self.bash(command), {})
                    decision = self.bash(command, dangerouslyDisableSandbox=True)
                    if kind == "claude":
                        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
                        self.assertIn("Claude runs stay inside the sandbox", decision["hookSpecificOutput"]["permissionDecisionReason"])
                        self.assertIn("without dangerouslyDisableSandbox", decision["hookSpecificOutput"]["permissionDecisionReason"])
                    else:
                        self.assertEqual(decision, {})
                    self.assertEqual(self.bash(f"{command} --bypass-caveman --capacity 2", dangerouslyDisableSandbox=True), decision)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        models = [{"model": model, "supportedReasoningEfforts": [{"reasoningEffort": effort} for effort in ("low", "medium", "high", "xhigh")]}
                  for model in ("gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra")]
        self.catalog = patch.object(runtime, "available_models", return_value=(models, "live Codex model/list"))
        self.catalog.start()
        self.addCleanup(self.catalog.stop)

    def test_newest_model_stays_in_its_tier_and_never_downgrades(self):
        models = [{"model": model, "supportedReasoningEfforts": [{"reasoningEffort": "medium"}]}
                  for model in ("gpt-6-sol", "gpt-6.1-sol", "gpt-6.2-sol", "gpt-7-astra", "claude-opus-5-5", "gpt-6.2-sol-2026-10-01")]
        with patch.object(runtime, "available_models", return_value=(models, "live test")):
            self.assertEqual(runtime.latest_model("gpt-6.1-sol", "medium"), ("gpt-6.2-sol", "live test"))
            with self.assertRaises(ValueError):
                runtime.latest_model("gpt-6.1-sol", "high")
        with patch.object(runtime, "available_models", return_value=([{"model": "gpt-6-sol"}], "old cache")):
            self.assertEqual(runtime.latest_model("gpt-6.1-sol", "medium")[0], "gpt-6.1-sol")
            self.assertIn("unverified", runtime.latest_model("gpt-6.1-sol", "medium")[1])

    def test_live_catalog_failure_keeps_app_server_stderr(self):
        self.catalog.stop()
        runtime.MODEL_CATALOG = None
        self.addCleanup(setattr, runtime, "MODEL_CATALOG", None)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex = root / "codex"
            codex.write_text("#!/bin/sh\nprintf '%s\\n' 'Error: Read-only file system (os error 30)' >&2\nexit 1\n")
            codex.chmod(0o755)
            home = root / "home"
            home.mkdir()
            with patch.dict(os.environ, {"PATH": str(root) + os.pathsep + os.environ.get("PATH", ""), "CODEX_HOME": str(home)}):
                models, source = runtime.available_models()
                self.assertEqual(models, [])
                self.assertTrue(source.startswith("profile fallback; latest model unverified"))
                self.assertIn("Read-only file system", source)

    def test_codex_runners_use_current_sol_in_every_mode_after_state_report_failures(self):
        for family in ('codex','hybrid'):
            for mode in runtime.MODES:
                settings=runtime.role_settings(family,mode,'runner')
                self.assertEqual((settings['model'],settings['effort']),('gpt-6.1-sol','medium'))
                self.assertEqual(runtime.role_settings(family,mode,'scout')['model'],'gpt-6-luna')

    def new_run(self, family="codex", mode="standard", role="implementer"):
        output = io.StringIO()
        with redirect_stdout(output):
            runtime.main(["new", family, mode, role])
        run = Path(json.loads(output.getvalue())["run"])
        self.addCleanup(lambda: runtime.shutil.rmtree(run) if run.exists() else None)
        return run

    def test_every_mode_has_all_contracts_except_quick_review(self):
        for family in runtime.FAMILIES:
            for mode in runtime.MODES:
                for role in runtime.ROLES:
                    with self.subTest(family=family, mode=mode, role=role):
                        if mode == "quick" and role in {"reviewer", "critic"}:
                            with self.assertRaises(ValueError):
                                runtime.role_settings(family, mode, role)
                            continue
                        if family == "codex" and role == "publisher":
                            with self.assertRaisesRegex(ValueError, "publisher is a Claude role; the codex family cannot publish an Artifact"):
                                runtime.role_settings(family, mode, role)
                            continue
                        settings = runtime.role_settings(family, mode, role)
                        if role == "publisher":
                            self.assertEqual(settings["kind"], "claude")
                            self.assertEqual(settings["agent_type"], f"orch-publisher-{mode}")
                            self.assertIn("Artifact", settings["tools"].replace(" ", "").split(","))
                        self.assertTrue(settings["body"])
                        if settings["kind"] == "codex":
                            expected = "read-only" if role in runtime.READ_ONLY else "danger-full-access"
                            self.assertEqual(settings["sandbox"], expected)
                        elif role in runtime.READ_ONLY:
                            self.assertFalse({"Write", "Edit", "Agent", "Task"} & set(settings["tools"].replace(" ", "").split(",")))
        self.assertEqual(runtime.role_settings("hybrid", "standard", "critic")["kind"], "claude")
        self.assertEqual(runtime.role_settings("hybrid", "standard", "implementer")["kind"], "codex")

    def test_sandbox_tmpdir_and_hook_agree_on_run_root(self):
        original_tempdir = tempfile.tempdir
        try:
            with tempfile.TemporaryDirectory() as temp:
                sandbox = Path(temp) / f"claude-{os.getuid()}"
                sandbox.mkdir(mode=0o700)
                with temp_root(sandbox):
                    run = self.new_run("claude", "standard", "scout")
                    self.assertEqual(run.parent, sandbox.resolve())
                with temp_root(temp):
                    self.assertEqual(runtime.run_path(run), run)
                    self.assertTrue(guard.coordination_command(
                        f'python3 "$HOME/.agents/orchestrator-runtime.py" start {run}', "orchestrator-claude"))
                    nested = sandbox / "other" / "orchestrator-invalid"
                    nested.mkdir(parents=True)
                    with self.assertRaisesRegex(ValueError, "expected a runtime-created temporary run directory"):
                        runtime.run_path(nested)
                    runtime.shutil.rmtree(run)
        finally:
            tempfile.tempdir = original_tempdir

    def test_sandbox_creates_runs_under_its_own_tmpdir_and_hook_accepts_them(self):
        base, sandbox, stale = sandbox_layout(self, "orchestrator-old", "run.json")
        with sandbox_view(base, sandbox):
            run = self.new_run("claude", "standard", "scout")
        self.assertEqual(run.parent, sandbox)
        with temp_root(base):
            self.assertEqual(runtime.run_root(), sandbox)
            self.assertEqual(runtime.run_path(run), run)
            self.assertTrue(guard.coordination_command(
                f'python3 "$HOME/.agents/orchestrator-runtime.py" start {run}', "orchestrator-claude"))
            # Runs that older sessions left under bare /tmp no longer validate.
            with self.assertRaisesRegex(ValueError, "expected a runtime-created temporary run directory"):
                runtime.run_path(stale)
            self.assertFalse(guard.coordination_command(
                f'python3 "$HOME/.agents/orchestrator-runtime.py" start {stale}', "orchestrator-claude"))

    def test_creation_makes_a_private_root_and_refuses_a_shared_one(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root = base / f"claude-{os.getuid()}"
            with temp_root(base):
                run = self.new_run("claude", "standard", "scout")
                self.assertEqual(run.parent, root)
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)
                runtime.shutil.rmtree(run)
                for mode in (0o770, 0o707):
                    root.chmod(mode)
                    for arguments in (["new", "claude", "standard", "scout"], ["plan", "claude", "standard"]):
                        with self.subTest(mode=oct(mode), action=arguments[0]), \
                                patch.object(sys, "stdin", io.StringIO(json.dumps(GraphTests.DEFINITION))), \
                                redirect_stdout(io.StringIO()), \
                                self.assertRaisesRegex(ValueError, re.escape(f"run root {root} must be a directory owned by uid")):
                            runtime.main(arguments)
                    self.assertEqual(list(root.iterdir()), [])

    def assert_root_refused(self, root):
        for arguments in (["new", "claude", "standard", "scout"], ["plan", "claude", "standard"]):
            with self.subTest(action=arguments[0]), \
                    patch.object(sys, "stdin", io.StringIO(json.dumps(GraphTests.DEFINITION))), \
                    redirect_stdout(io.StringIO()), \
                    self.assertRaisesRegex(ValueError, re.escape(f"run root {root} must be a directory owned by uid")):
                runtime.main(arguments)

    def test_creation_refuses_a_symlinked_root_without_writing_through_it(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            target = base / "private"
            target.mkdir(mode=0o700)
            root = base / f"claude-{os.getuid()}"
            root.symlink_to(target)
            with temp_root(base):
                self.assert_root_refused(root)
            self.assertEqual(list(target.iterdir()), [])

    def test_creation_refuses_a_root_that_is_a_file(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root = base / f"claude-{os.getuid()}"
            root.write_text("")
            root.chmod(0o600)
            with temp_root(base):
                self.assert_root_refused(root)
            self.assertTrue(root.is_file())

    def test_creation_refuses_a_root_owned_by_another_uid(self):
        other = os.getuid() + 1
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            # The private directory is ours; under the patched uid it reads as another user's.
            root = base / f"claude-{other}"
            root.mkdir(mode=0o700)
            with temp_root(base), patch.object(runtime.os, "getuid", return_value=other):
                self.assertEqual(runtime.run_root(), root)
                self.assert_root_refused(root)
            self.assertEqual(list(root.iterdir()), [])

    def test_claude_code_tmpdir_sets_the_base_for_hook_and_sandbox(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as unrelated:
            base = Path(temp).resolve()
            root = base / f"claude-{os.getuid()}"
            for tmpdir in (unrelated, root):
                with self.subTest(tmpdir=str(tmpdir)), temp_root(tmpdir), \
                        patch.dict(os.environ, {"CLAUDE_CODE_TMPDIR": temp}):
                    self.assertEqual(runtime.run_root(), root)
            with temp_root(unrelated), patch.dict(os.environ, {"CLAUDE_CODE_TMPDIR": ""}):
                self.assertEqual(runtime.run_root(), Path(unrelated).resolve() / root.name)

    def test_instructions_skip_codex_publisher_and_include_hybrid_publisher(self):
        for family in ("codex", "hybrid"):
            with self.subTest(family=family), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(runtime.main(["instructions", family, "standard"]), 0)
            roles = [json.loads(line)["role"] for line in output.getvalue().splitlines() if line.startswith('{"role":')]
            self.assertEqual(roles.count("publisher"), 0 if family == "codex" else 1)

    def test_brief_is_literal_and_codex_process_has_resolved_settings(self):
        run = self.new_run()
        brief = "GOAL: Fix source\nVERIFY: pytest\nLiteral $(touch forbidden)"
        with patch.object(sys, "stdin", io.StringIO(brief)), redirect_stdout(io.StringIO()):
            runtime.main(["brief", str(run)])
        self.assertIn(brief, (run / "prompt.md").read_text())
        self.assertIn("command is still running", (run / "prompt.md").read_text())
        with patch.object(runtime.subprocess, "call", return_value=0) as call, redirect_stdout(io.StringIO()):
            self.assertEqual(runtime.main(["start", str(run)]), 0)
            cmd = call.call_args.args[0]
            self.assertEqual(cmd[:5], ["caveman", "run", "--", "codex", "exec"])
            self.assertIn("gpt-6.1-sol", cmd)
            self.assertIn("sandbox_mode=danger-full-access", cmd)
            self.assertIn("features.hooks=false", cmd)
            self.assertNotEqual(call.call_args.kwargs["env"]["CODEX_HOME"], os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
            self.assertFalse(Path(call.call_args.kwargs["env"]["CODEX_HOME"]).exists())
            self.assertEqual(cmd[-1], "-")
            self.assertNotIn("-a", cmd)
            self.assertEqual(call.call_args.kwargs["stdin"].name, str(run / "prompt.md"))

    def test_claude_read_only_start_records_stream_receipts_usage_and_final(self):
        run = self.new_run("claude", "quick", "scout")
        self.assertEqual(json.loads((run / "run.json").read_text())["kind"], "claude")
        with patch.object(sys, "stdin", io.StringIO("Locate source")), redirect_stdout(io.StringIO()):
            runtime.main(["brief", str(run)])
        self.assertEqual((run / "prompt.md").read_text(), "Locate source")
        # Relevant fields from item_9's nested stream in the real probe at
        # /tmp/claude-1000/orchestrator-iryjy9fj/events.jsonl; session IDs omitted.
        fixture = [
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "toolu_01K5RrK9Umjn4g31fTVzFkFf",
                "name": "Bash", "input": {"command": "echo probe-ok", "description": "Echo probe-ok to verify shell access"}}],
                "usage": {"input_tokens": 10, "cache_creation_input_tokens": 20259, "cache_read_input_tokens": 18433, "output_tokens": 5}}},
            {"type": "user", "message": {"role": "user", "content": [{"tool_use_id": "toolu_01K5RrK9Umjn4g31fTVzFkFf",
                "type": "tool_result", "content": "probe-ok", "is_error": False}]}},
            {"type": "result", "total_cost_usd": 0.0517235, "usage": {"input_tokens": 18,
                "cache_creation_input_tokens": 22344, "cache_read_input_tokens": 57125, "output_tokens": 261},
                "subtype": "success", "is_error": False, "result": "Done. Shell access verified."}]
        stream = "\n".join(map(json.dumps, fixture)) + "\n"
        def child(command, **kwargs):
            self.assertEqual(command, ["claude", "--print", "--output-format", "stream-json", "--verbose",
                "--no-session-persistence", "--strict-mcp-config", "--permission-mode", "bypassPermissions",
                "--agent", "orch-scout-quick", "--model", "sonnet", "--tools", "Bash,Read,Grep,Glob", "--effort", "medium"])
            self.assertEqual(kwargs["cwd"], json.loads((run / "run.json").read_text())["workspace"])
            self.assertEqual(kwargs["stdin"].read(), "Locate source")
            self.assertEqual(Path(kwargs["stdout"].name), run / "events.jsonl")
            self.assertEqual(Path(kwargs["stderr"].name), run / "stderr.log")
            self.assertEqual(kwargs["env"], {key: value for key, value in os.environ.items() if not key.startswith("HERDR_")})
            with self.assertRaisesRegex(ValueError, "already executing"):
                with runtime.unstarted_run(run):
                    pass
            kwargs["stdout"].write(stream)
            kwargs["stderr"].write("probe stderr")
            return 0
        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_PANE_ID": "child-pane", "HERDR_OTHER": "strip", "KEEP_CHILD_ENV": "keep"}), \
                patch.object(runtime.subprocess, "call", side_effect=child), redirect_stdout(io.StringIO()):
            self.assertEqual(runtime.main(["start", str(run)]), 0)
        self.assertEqual((run / "events.jsonl").read_text(), stream)
        self.assertEqual((run / "stderr.log").read_text(), "probe stderr")
        self.assertEqual((run / "final.md").read_text(), "Done. Shell access verified.")
        summary = runtime.execution_summary(run)
        self.assertEqual(summary["usage"], {"input_tokens": 79487, "cached_input_tokens": 57125,
            "cache_write_input_tokens": 22344, "output_tokens": 261, "reasoning_output_tokens": 0})
        self.assertEqual(summary["total_cost_usd"], 0.0517235)
        self.assertEqual(summary["completed_receipts"], 1)
        self.assertEqual(summary["pending_receipt_ids"], [])
        self.assertEqual(summary["evidence_issues"], [])
        receipt_id = "toolu_01K5RrK9Umjn4g31fTVzFkFf"
        (run / "final.md").write_text(f"Receipts: {receipt_id}\n")
        self.assertEqual(runtime.execution_summary(run)["evidence_issues"], [])
        (run / "final.md").write_text("Receipts: toolu_01ABC\n")
        self.assertIn("Report cites receipt IDs absent from completed execution events", runtime.execution_summary(run)["evidence_issues"])
        (run / "final.md").write_text(fixture[2]["result"])
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runtime.main(["report", str(run), "--receipt", receipt_id]), 0)
        self.assertEqual(json.loads(output.getvalue()), {"id": receipt_id, "type": "command_execution",
            "command": "echo probe-ok", "aggregated_output": "probe-ok", "is_error": False})
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runtime.main(["report", str(run)]), 0)
        receipt = next(json.loads(line) for line in output.getvalue().splitlines() if '"worker_command"' in line)
        self.assertFalse(receipt["is_error"])
        self.assertNotIn("exit_code", receipt)
        with redirect_stdout(io.StringIO()) as output:
            runtime.main(["summary", str(run), str(run)])
        self.assertEqual(json.loads(output.getvalue())["usage"], summary["usage"])
        with patch.object(runtime.subprocess, "call") as child:
            with self.assertRaisesRegex(ValueError, "already started"):
                runtime.main(["start", str(run)])
            for role in ("implementer", "runner", "verifier", "browser", "publisher"):
                blocked = self.new_run("claude", "quick", role)
                (blocked / "prompt.md").write_text("Brief")
                with self.assertRaisesRegex(ValueError, "dispatch this Claude agent with Agent"):
                    runtime.main(["start", str(blocked)])
            child.assert_not_called()
        # Exercise other tool names and content blocks, then a missing result.
        fixture[0]["message"]["content"][0].update(name="Read", input={"file_path": "README.md"})
        fixture[1]["message"]["content"][0].update(content=[{"type": "text", "text": "missing"}], is_error=True)
        (run / "events.jsonl").write_text("\n".join(map(json.dumps, fixture)))
        with redirect_stdout(io.StringIO()) as output:
            runtime.main(["report", str(run), "--receipt", receipt_id])
        self.assertEqual(json.loads(output.getvalue()), {"id": receipt_id, "type": "Read",
            "command": '{"file_path":"README.md"}', "aggregated_output": "missing", "is_error": True})
        (run / "events.jsonl").write_text(json.dumps(fixture[0]) + "\n" + json.dumps(fixture[2]))
        summary = runtime.execution_summary(run)
        self.assertEqual(summary["completed_receipts"], 0)
        self.assertEqual(summary["pending_receipt_ids"], [receipt_id])
        self.assertIn("lack completed execution receipts", summary["evidence_issues"][0])
        fixture[0]["message"]["content"][0].pop("id")
        (run / "events.jsonl").write_text(json.dumps(fixture[0]) + "\n" + json.dumps(fixture[2]))
        summary = runtime.execution_summary(run)
        self.assertEqual(summary["pending_receipt_ids"], [])
        self.assertIn('Malformed tool_use block lacks an ID:', summary["evidence_issues"][0])
        self.assertIn('"name": "Read"', summary["evidence_issues"][0])
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runtime.main(["report", str(run)]), 1)
        self.assertIn("Malformed tool_use block", output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            runtime.main(["summary", str(run)])
        self.assertEqual(json.loads(output.getvalue())["runs"][0]["evidence_issues"], summary["evidence_issues"])

    def test_claude_error_results_keep_final_and_exit_status_but_flag_evidence(self):
        for subtype, is_error, exit_code in (("error_max_turns", False, 0), ("success", True, 0), ("error_max_turns", True, 1)):
            with self.subTest(subtype=subtype, is_error=is_error, exit_code=exit_code):
                run = self.new_run("claude", "quick", "scout")
                (run / "prompt.md").write_text("Locate source")
                event = {"type": "result", "subtype": subtype, "is_error": is_error, "result": "Partial report"}
                def child(command, **kwargs):
                    kwargs["stdout"].write(json.dumps(event) + "\n")
                    return exit_code
                with patch.object(runtime.subprocess, "call", side_effect=child), redirect_stdout(io.StringIO()):
                    self.assertEqual(runtime.main(["start", str(run)]), exit_code)
                self.assertEqual((run / "final.md").read_text(), "Partial report")
                summary = runtime.execution_summary(run)
                self.assertEqual(summary["status"], "completed" if exit_code == 0 else "failed")
                self.assertEqual(summary["exit_code"], exit_code)
                self.assertEqual(summary["evidence_issues"], [f"Claude result reports subtype={subtype!r}, is_error={is_error!r}"])

    def test_dispatch_requires_live_freshness_but_reports_remain_available_offline(self):
        run = self.new_run()
        with patch.object(sys, "stdin", io.StringIO("GOAL: bounded edit")), redirect_stdout(io.StringIO()):
            runtime.main(["brief", str(run)])
        models, _ = runtime.available_models()
        with patch.object(runtime, "available_models", return_value=(models, "cached Codex catalog; live catalog unavailable")), patch.object(runtime.subprocess, "call") as call:
            with self.assertRaisesRegex(ValueError, "Cannot verify the newest model"):
                runtime.main(["start", str(run)])
            call.assert_not_called()
        (run / "final.md").write_text("Observed result")
        with patch.object(runtime, "available_models", side_effect=AssertionError("report must not query models")), redirect_stdout(io.StringIO()) as output:
            runtime.main(["report", str(run)])
        self.assertIn("Observed result", output.getvalue())

    def test_child_configuration_keeps_auth_without_inheriting_host_hooks(self):
        run = self.new_run(role="scout")
        (run / "prompt.md").write_text("Read README.md")
        homes = []
        with tempfile.TemporaryDirectory() as source:
            (Path(source) / "auth.json").write_text('{"fixture":"test-auth"}')
            (Path(source) / "config.toml").write_text('model_provider="host-only"')
            (Path(source) / "hooks.json").write_text('{"fixture":"host hook"}')
            def child(command, **kwargs):
                config = Path(kwargs["env"]["CODEX_HOME"]); homes.append(config)
                self.assertEqual((config / "auth.json").read_text(), '{"fixture":"test-auth"}')
                self.assertEqual((config / "auth.json").stat().st_mode & 0o777, 0o600)
                self.assertFalse((config / "config.toml").exists())
                self.assertFalse((config / "hooks.json").exists())
                self.assertNotIn("--ignore-user-config", command)  # Wrapper routing remains usable.
                return 0
            with patch.dict(os.environ, {"CODEX_HOME": source}), patch.object(runtime.subprocess, "call", side_effect=child), redirect_stdout(io.StringIO()):
                self.assertEqual(runtime.main(["start", str(run)]), 0)
        self.assertTrue(homes)
        self.assertTrue(all(not home.exists() for home in homes))

    def test_report_projects_codex_file_changes_and_tracks_terminal_receipts(self):
        # Shape observed in orchestrator-rap5bds7/events.jsonl, item_13.
        # Only the affected path is replaced with a test-owned path.
        for status in ("completed", "failed", None):
            with self.subTest(status=status):
                run = self.new_run(role="implementer")
                path = str(run / "orders" / "tax.py")
                started = {
                    "type": "item.started",
                    "item": {
                        "id": "item_13", "type": "file_change",
                        "changes": [{"path": path, "kind": "update"}],
                        "status": "in_progress",
                    },
                }
                events = [started]
                if status is not None:
                    events.append({
                        "type": "item.completed",
                        "item": {**started["item"], "status": status},
                    })
                (run / "events.jsonl").write_text(
                    "".join(json.dumps(event) + "\n" for event in events)
                )
                (run / "execution.json").write_text(
                    json.dumps({"status": "completed"})
                )
                with redirect_stdout(io.StringIO()) as output:
                    result = runtime.main(["report", str(run)])
                records = [
                    json.loads(line) for line in output.getvalue().splitlines()
                ]
                projected = [
                    record for record in records if "file_changes" in record
                ]
                expected = [{
                    "run": str(run), "role": "implementer",
                    "receipt_id": "item_13", "status": "completed",
                    "file_changes": [{"path": path, "kind": "update"}],
                }] if status == "completed" else []
                self.assertEqual(projected, expected)
                summary = records[-1]["execution_summary"]
                self.assertEqual(result, 1 if status is None else 0)
                self.assertEqual(
                    summary["completed_receipts"], 0 if status is None else 1,
                )
                self.assertEqual(
                    summary["pending_receipt_ids"],
                    ["item_13"] if status is None else [],
                )

    def test_reports_expose_commands_for_verifier_and_other_roles(self):
        for role, key in (("verifier", "verifier_command"), ("implementer", "worker_command")):
            with self.subTest(role=role):
                run = self.new_run(role=role)
                event = {"type": "item.completed", "item": {"type": "command_execution", "command": "python3 -m unittest -q", "exit_code": 1, "aggregated_output": "FAILED"}}
                (run / "events.jsonl").write_text(json.dumps(event) + "\n")
                with redirect_stdout(io.StringIO()) as output:
                    runtime.main(["report", str(run)])
                receipt = json.loads(output.getvalue().splitlines()[0])
                self.assertEqual(receipt[key], event["item"]["command"])
                self.assertEqual(receipt["role"], role)
                self.assertEqual(receipt["exit_code"], 1)
                self.assertEqual(receipt["output"], "FAILED")

    def test_artifacts_cannot_escape_run_directory_through_symlinks(self):
        run = self.new_run()
        with tempfile.TemporaryDirectory() as temp:
            victim = Path(temp) / "source.py"
            victim.write_text("keep me")
            (run / "prompt.md").symlink_to(victim)
            with patch.object(sys, "stdin", io.StringIO("overwrite")), self.assertRaises(ValueError):
                runtime.main(["brief", str(run)])
            self.assertEqual(victim.read_text(), "keep me")
            with self.assertRaises(ValueError):
                runtime.run_path(temp)

    def test_batch_executes_concurrently_and_collects_a_failed_child(self):
        runs = [self.new_run(role="scout") for _ in range(2)]
        for run in runs:
            (run / "prompt.md").write_text("Locate an owned file")
        barrier = threading.Barrier(2, timeout=3)
        def child(*args, **kwargs):
            barrier.wait()
            return 7 if kwargs["stdin"].name == str(runs[0] / "prompt.md") else 0
        with patch.object(runtime.subprocess, "call", side_effect=child), redirect_stdout(io.StringIO()):
            self.assertEqual(runtime.main(["start-many", *map(str, runs), "--capacity", "2"]), 1)
        with redirect_stdout(io.StringIO()) as output:
            runtime.main(["summary", *map(str, runs)])
        summary = json.loads(output.getvalue())
        self.assertEqual(summary["peak_concurrency"], 2)
        self.assertTrue(summary["finished"])
        self.assertEqual(sorted(item["exit_code"] for item in summary["runs"]), [0, 7])

    def test_batch_launches_read_only_claude_and_rejects_writable_roles(self):
        runs = [self.new_run("claude", "standard", role) for role in ("scout", "reviewer")]
        for run in runs:
            (run / "prompt.md").write_text("Read source")
        barrier = threading.Barrier(2, timeout=3)
        def child(command, **kwargs):
            self.assertEqual(command[0], "claude")
            self.assertIn("--print", command)
            self.assertIn(command[command.index("--agent") + 1], ("orch-scout-standard", "reviewer-standard"))
            barrier.wait()
            kwargs["stdout"].write(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                                               "result": "Read-only report", "usage": {}}) + "\n")
            return 0
        with patch.object(runtime.subprocess, "call", side_effect=child) as process, redirect_stdout(io.StringIO()):
            self.assertEqual(runtime.main(["start-many", *map(str, runs), "--capacity", "2"]), 0)
        self.assertEqual(process.call_count, 2)
        for run in runs:
            self.assertEqual((run / "final.md").read_text(), "Read-only report")
            self.assertEqual(runtime.execution_summary(run)["exit_code"], 0)
        for role in ("implementer", "verifier", "runner", "browser", "publisher"):
            with self.subTest(role=role):
                fresh = [self.new_run("claude", "standard", name) for name in ("scout", role)]
                for run in fresh:
                    (run / "prompt.md").write_text("Brief")
                with patch.object(runtime.subprocess, "call") as process:
                    with self.assertRaisesRegex(ValueError, "only read-only Claude roles"):
                        runtime.main(["start-many", *map(str, fresh)])
                    process.assert_not_called()

    def test_batch_rejects_mixed_kinds_before_launch(self):
        runs = [self.new_run("hybrid", "standard", role) for role in ("scout", "reviewer")]
        for run in runs:
            (run / "prompt.md").write_text("Read source")
        with patch.object(runtime.subprocess, "call") as process:
            with self.assertRaisesRegex(ValueError, "cannot mix claude and codex"):
                runtime.main(["start-many", *map(str, runs)])
            process.assert_not_called()

    def test_batch_rejects_invalid_ownership_or_family_before_launch(self):
        runs = [self.new_run(), self.new_run()]
        for run in runs:
            (run / "prompt.md").write_text("Edit owned source")
        with patch.object(runtime.subprocess, "call") as child:
            with self.assertRaisesRegex(ValueError, "claimed ownership"):
                runtime.main(["start-many", *map(str, runs)])
            with self.assertRaisesRegex(ValueError, "unique"):
                runtime.main(["start-many", str(runs[0]), str(runs[0])])
            meta = json.loads((runs[1] / "run.json").read_text())
            meta["family"] = "hybrid"
            (runs[1] / "run.json").write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError, "share family"):
                runtime.main(["start-many", *map(str, runs)])
            child.assert_not_called()
        self.assertFalse(guard.coordination_command(f'python3 "$HOME/.agents/orchestrator-runtime.py" start-many {runs[0]} {runs[1]}', "orchestrator-codex"))

    def test_started_run_cannot_overwrite_its_evidence(self):
        run = self.new_run(role="scout")
        (run / "prompt.md").write_text("Read source")
        with patch.object(runtime.subprocess, "call", return_value=0), redirect_stdout(io.StringIO()):
            runtime.main(["start", str(run)])
        (run / "events.jsonl").write_text("preserved evidence")
        with patch.object(runtime.subprocess, "call") as child, self.assertRaisesRegex(ValueError, "already started"):
            runtime.main(["start", str(run)])
        child.assert_not_called()
        self.assertEqual((run / "events.jsonl").read_text(), "preserved evidence")

    def test_rebrief_preserves_the_prompt_during_and_after_execution(self):
        run = self.new_run(role="scout")
        (run / "prompt.md").write_text("Original brief")
        with runtime.unstarted_run(run), patch.object(sys, "stdin", io.StringIO("Changed brief")):
            with self.assertRaisesRegex(ValueError, "already executing"):
                runtime.main(["brief", str(run)])
        (run / "execution.json").write_text(json.dumps({"status": "completed"}))
        with patch.object(sys, "stdin", io.StringIO("Changed brief")):
            with self.assertRaisesRegex(ValueError, "already started"):
                runtime.main(["brief", str(run)])
        self.assertEqual((run / "prompt.md").read_text(), "Original brief")

    def claimed_batch_plan(self, runs, workspace, scopes):
        definition = {"goal": "Independent owned changes", "capacity": 3, "tasks": [
            {"id": f"task-{index}", "title": "Change owned source", "scope": [scope],
             "acceptance": ["Requested change exists"], "verify": ["Inspect owned diff"]}
            for index, scope in enumerate(scopes)]}
        with patch.object(sys, "stdin", io.StringIO(json.dumps(definition))), redirect_stdout(io.StringIO()) as output:
            runtime.main(["plan", "codex", "standard", "--workspace", str(workspace)])
        plan = Path(json.loads(output.getvalue())["plan"])
        self.addCleanup(lambda: runtime.shutil.rmtree(plan))
        for index, run in enumerate(runs):
            meta = json.loads((run / "run.json").read_text())
            meta["workspace"] = str(workspace)
            (run / "run.json").write_text(json.dumps(meta))
            (run / "prompt.md").write_text("Edit only the claimed scope")
            with redirect_stdout(io.StringIO()):
                runtime.main(["claim", str(plan), f"task-{index}", "--owner", str(run)])
        return plan

    def test_writable_batch_accepts_disjoint_retained_claims(self):
        runs = [self.new_run(), self.new_run()]
        with tempfile.TemporaryDirectory() as workspace:
            plan = self.claimed_batch_plan(runs, Path(workspace), ["a.py", "b.py"])
            with patch.object(runtime.subprocess, "call", return_value=0) as child, redirect_stdout(io.StringIO()):
                self.assertEqual(runtime.main(["start-many", *map(str, runs), "--plan", str(plan)]), 0)
            self.assertEqual(child.call_count, 2)
            self.assertTrue(all(task["status"] == "running" for task in json.loads((plan / "plan.json").read_text())["tasks"].values()))

    def test_writable_batch_rejects_rebound_symlink_and_an_external_owner(self):
        runs = [self.new_run(), self.new_run()]
        scout = self.new_run(role="scout")
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            (root / "a").mkdir(); (root / "b").mkdir()
            (root / "link").symlink_to(root / "a", target_is_directory=True)
            plan = self.claimed_batch_plan(runs, root, ["link/file.py", "b/file.py"])
            meta = json.loads((scout / "run.json").read_text()); meta["workspace"] = workspace
            (scout / "run.json").write_text(json.dumps(meta)); (scout / "prompt.md").write_text("Read only")
            (root / "link").unlink(); (root / "link").symlink_to(root / "b", target_is_directory=True)
            with patch.object(runtime.subprocess, "call") as child:
                with self.assertRaisesRegex(ValueError, "changed since claim"):
                    runtime.main(["start-many", str(runs[0]), str(scout), "--plan", str(plan)])
                # The other active owner's current scope also protects this path.
                state = json.loads((plan / "plan.json").read_text())
                state["tasks"]["task-0"]["claimed_scope"] = [str(root / "b/file.py")]
                runtime.save_plan(plan, state)
                with self.assertRaisesRegex(ValueError, "another active owner"):
                    runtime.main(["start-many", str(runs[0]), str(scout), "--plan", str(plan)])
                child.assert_not_called()

    def test_report_flags_the_audited_false_empty_output_claims(self):
        run = self.new_run(role="scout")
        (run / "final.md").write_text("Directory listings returned no output. Shell commands did not return output.")
        event = {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution", "command": "cat AGENTS.md", "exit_code": 0, "aggregated_output": "Instructions"}}
        (run / "events.jsonl").write_text(json.dumps(event) + "\n")
        self.assertEqual(len(runtime.execution_summary(run)["evidence_issues"]), 2)
        (run / "final.md").write_text("Not attempted: directory listings.\nReceipts: item_1")
        self.assertEqual(runtime.execution_summary(run)["evidence_issues"], [])
        (run / "final.md").write_text("Receipts: item_invented")
        self.assertTrue(runtime.execution_summary(run)["evidence_issues"])

    def test_batch_rejects_missing_completed_receipts_despite_zero_exit(self):
        runs = [self.new_run(role="scout") for _ in range(2)]
        for run in runs:
            (run / "prompt.md").write_text("Locate source")
        def child(*args, **kwargs):
            kwargs["stdout"].write(json.dumps({"type": "item.started", "item": {
                "type": "command_execution", "id": "item_1", "command": "rg alpha README.md"}}) + "\n")
            kwargs["stdout"].write(json.dumps({"type": "turn.completed", "usage": {}}) + "\n")
            return 0
        with patch.object(runtime.subprocess, "call", side_effect=child), redirect_stdout(io.StringIO()):
            self.assertEqual(runtime.main(["start-many", *map(str, runs)]), 1)
        summary = runtime.execution_summary(runs[0])
        self.assertEqual(summary["exit_code"], 0)
        self.assertEqual(summary["pending_receipt_ids"], ["item_1"])
        self.assertIn("lack completed execution receipts", summary["evidence_issues"][0])

    def test_receipt_recovery_keeps_material_output_and_summary_counts_once(self):
        run = self.new_run(role="scout")
        content = "REQUIRED_FIRST_LINE\n" + "x" * 17000 + "\nREQUIRED_LAST_LINE"
        events = [{"type": "item.completed", "item": {"id": "item_1", "type": "command_execution", "command": "find docs", "exit_code": 0, "aggregated_output": content}},
                  {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 5}}]
        (run / "events.jsonl").write_text("\n".join(map(json.dumps, events)))
        with redirect_stdout(io.StringIO()) as output:
            runtime.main(["report", str(run), "--receipt", "item_1"])
        self.assertEqual(json.loads(output.getvalue())["aggregated_output"], content)
        with redirect_stdout(io.StringIO()) as output:
            runtime.main(["summary", str(run), str(run)])
        summary = json.loads(output.getvalue())
        self.assertEqual(summary["run_count"], 1)
        self.assertEqual(summary["usage"]["input_tokens"], 100)
        self.assertIsNone(summary["peak_concurrency"])
        self.assertFalse(summary["finished"])

    def test_visible_start_preserves_tools_and_read_only_report_delivery(self):
        run = self.new_run("hybrid", "standard", "reviewer")
        with patch.object(sys, "stdin", io.StringIO("GOAL: review")), redirect_stdout(io.StringIO()):
            runtime.main(["brief", str(run)])
        pane = subprocess.CompletedProcess([], 0, json.dumps({"result": {"pane": {"foreground_cwd": json.loads((run / "run.json").read_text())["workspace"]}}}))
        with patch.object(runtime, "visible_available", return_value=True), patch.object(runtime.subprocess, "run", return_value=pane), patch.object(runtime.subprocess, "call", return_value=0) as call, redirect_stdout(io.StringIO()):
            runtime.main(["start", str(run), "--pane", "w1:p4"])
            cmd = call.call_args.args[0]
            self.assertIn("claude", cmd)
            self.assertIn("Bash,Read,Glob,Grep", cmd)
            runtime.main(["prompt", str(run)])
            prompt = call.call_args.args[0]
            self.assertIn("Reply with your report; do not write a file.", prompt[4])
            self.assertNotIn("Write your report", prompt[4])
        with patch.object(runtime, "visible_available", return_value=False), self.assertRaises(ValueError):
            runtime.main(["start", str(run), "--pane", "w1:p4"])

    def test_visible_start_rejects_wrong_workspace_and_keeps_failed_launch_recoverable(self):
        run = self.new_run("claude", "fast", "scout")
        with patch.object(sys, "stdin", io.StringIO("GOAL: locate")), redirect_stdout(io.StringIO()):
            runtime.main(["brief", str(run)])
        wrong = subprocess.CompletedProcess([], 0, json.dumps({"result": {"pane": {"foreground_cwd": "/tmp"}}}))
        with patch.object(runtime, "visible_available", return_value=True), patch.object(runtime.subprocess, "run", return_value=wrong), patch.object(runtime.subprocess, "call") as call:
            with self.assertRaises(ValueError):
                runtime.main(["start", str(run), "--pane", "w1:p4"])
            call.assert_not_called()
        correct = subprocess.CompletedProcess([], 0, json.dumps({"result": {"pane": {"foreground_cwd": json.loads((run / "run.json").read_text())["workspace"]}}}))
        with patch.object(runtime, "visible_available", return_value=True), patch.object(runtime.subprocess, "run", return_value=correct), patch.object(runtime.subprocess, "call", return_value=1) as call:
            self.assertEqual(runtime.main(["start", str(run), "--pane", "w1:p4"]), 1)
            runtime.main(["read-pane", str(run)])
            self.assertEqual(call.call_args.args[0][:3], ["herdr", "agent", "read"])
            runtime.main(["stop", str(run)])
            self.assertEqual(call.call_args.args[0][-1], "ctrl+c")


if __name__ == "__main__":
    unittest.main()


class GraphTests(unittest.TestCase):
    DEFINITION = {"goal": "Two dependent slices", "capacity": 2, "tasks": [
        {"id": "tax", "title": "Add tax", "scope": ["orders/tax.py", "tests/test_tax.py"],
         "acceptance": ["Tax computes the requested rate"], "verify": ["python3 -m unittest -q"]},
        {"id": "pricing", "title": "Use tax", "scope": ["orders/pricing.py"], "blocked_by": ["tax"],
         "acceptance": ["Orders include tax"], "verify": ["python3 -m unittest -q"]}]}

    def setUp(self):
        self.definition = json.loads(json.dumps(self.DEFINITION))

    def invoke(self, arguments, data=None):
        if arguments[0] == "resolve" and isinstance(data, dict):
            state=json.loads((Path(arguments[1]) / "plan.json").read_text())["tasks"][arguments[2]]
            data={"owner":state["owner"],"attempt":state["attempt"],**data}
        output = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO(json.dumps(data))), redirect_stdout(output):
            runtime.main(arguments)
        return json.loads(output.getvalue())

    def plan(self, mode="standard", definition=None):
        result = self.invoke(["plan", "claude", mode], definition or self.definition)
        path = result["plan"]
        self.addCleanup(lambda: runtime.shutil.rmtree(path) if Path(path).exists() else None)
        return path

    def resolve(self, path, task, **fields):
        return self.invoke(["resolve", path, task], fields)

    def test_sandbox_creates_plans_under_its_own_tmpdir_and_hook_accepts_them(self):
        base, sandbox, stale = sandbox_layout(self, "orchestrator-plan-old", "plan.json")
        with sandbox_view(base, sandbox):
            path = Path(self.plan())
        self.assertEqual(path.parent, sandbox)
        script = 'python3 "$HOME/.agents/orchestrator-runtime.py"'
        with temp_root(base):
            self.assertEqual(runtime.run_path(path), path)
            self.assertTrue(guard.coordination_command(script + f" claim {path} tax --owner worker-a", "orchestrator-claude"))
            with self.assertRaisesRegex(ValueError, "expected a runtime-created temporary run directory"):
                runtime.run_path(stale)
            self.assertFalse(guard.coordination_command(script + f" claim {stale} tax --owner worker-a", "orchestrator-claude"))

    def test_dependencies_require_verified_reviewed_completion(self):
        path = self.plan()
        self.assertEqual(self.invoke(["graph", path])["frontier"], ["tax"])
        with self.assertRaisesRegex(ValueError, "unfinished dependency"):
            self.invoke(["claim", path, "pricing", "--owner", "worker-b"])
        self.invoke(["claim", path, "tax", "--owner", "worker-a"])
        for result in ({"status": "done", "evidence": "Implemented"},
                       {"status": "done", "evidence": "Implemented", "verification": "Passed"}):
            with self.assertRaises(ValueError):
                self.invoke(["resolve", path, "tax"], result)
        self.resolve(path, "tax", status="done", evidence="Actual tax behavior", verification="Verifier: exit 0", review="Accepted, no findings")
        self.assertEqual(self.invoke(["graph", path])["frontier"], ["pricing"])
        self.invoke(["claim", path, "pricing", "--owner", "worker-b"])
        self.resolve(path, "pricing", status="done", evidence="Order includes tax", verification="Verifier: exit 0", review="Accepted")
        self.assertTrue(self.invoke(["graph", path])["complete"])
        with self.assertRaisesRegex(ValueError, "status is done"):
            self.invoke(["claim", path, "tax", "--owner", "duplicate"])

    def test_implemented_handoff_releases_dependency_without_completing_graph(self):
        path = self.plan()
        self.invoke(["claim", path, "tax", "--owner", "worker-a"])
        self.resolve(path, "tax", status="implemented", evidence="Tax code and test are stable")
        graph = self.invoke(["graph", path])
        self.assertEqual(graph["frontier"], ["pricing"])
        self.assertFalse(graph["complete"])
        tax = next(task for task in graph["tasks"] if task["id"] == "tax")
        self.assertEqual((tax["status"], tax["owner"], tax["attempt"]), ("implemented", "worker-a", 1))
        self.invoke(["claim", path, "pricing", "--owner", "worker-b"])
        with self.assertRaisesRegex(ValueError, "every implementation"):
            self.resolve(path, "tax", status="done", evidence="Verified tax", verification="exit 0", review="Accepted")
        self.resolve(path, "pricing", status="implemented", evidence="Totals code and test are stable")
        self.resolve(path, "tax", status="done", evidence="Verified tax", verification="final verifier exit 0", review="Accepted")
        self.assertFalse(self.invoke(["graph", path])["complete"])
        self.resolve(path, "pricing", status="done", evidence="Verified totals", verification="final verifier exit 0", review="Accepted")
        self.assertTrue(self.invoke(["graph", path])["complete"])

    def test_pending_runner_does_not_block_implementation_readiness(self):
        self.definition["tasks"].append({
            "id": "publish", "title": "Publish", "role": "runner",
            "scope": ["NOTES.md"], "blocked_by": ["pricing"],
            "acceptance": ["Publication recorded"], "verify": ["Review result"],
        })
        path = self.plan()
        for task in ("tax", "pricing"):
            self.invoke(["claim", path, task, "--owner", task])
            self.resolve(path, task, status="implemented", evidence="Stable source")
        for task in ("tax", "pricing"):
            self.resolve(path, task, status="done", evidence="Accepted",
                         verification="Final verifier exit 0", review="Accepted")
        self.assertFalse(self.invoke(["graph", path])["complete"])
        self.invoke(["claim", path, "publish", "--owner", "publisher"])
        self.resolve(path, "publish", status="done", evidence="Published",
                     verification="Publication verified", review="Accepted")
        self.assertTrue(self.invoke(["graph", path])["complete"])

    def test_handoff_resolution_keeps_identity_evidence_and_retry_guards(self):
        path = self.plan()
        self.invoke(["claim", path, "tax", "--owner", "worker-a"])
        self.resolve(path, "tax", status="implemented", evidence="Stable tax")
        self.invoke(["claim", path, "pricing", "--owner", "worker-b"])
        self.resolve(path, "pricing", status="implemented", evidence="Stable totals")
        valid = dict(status="done", evidence="Accepted behavior",
                     verification="Final verifier exit 0", review="Accepted")
        for changed in (
            {"owner": "other"}, {"attempt": 2}, {"attempt": True},
            {"evidence": ""}, {"verification": ""}, {"review": ""},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.resolve(path, "tax", **{**valid, **changed})
        self.resolve(path, "tax", status="blocked", evidence="Final check failed")
        with self.assertRaises(ValueError):
            self.resolve(path, "tax", status="pending", evidence="Retry")
        self.resolve(path, "tax", status="pending", stopped=True, evidence="Owner stopped")
        claimed = self.invoke(["claim", path, "tax", "--owner", "repair"])
        self.assertEqual(claimed["attempt"], 2)
        self.resolve(path, "tax", status="implemented", evidence="Repair handed off")
        self.resolve(path, "tax", **valid)
        self.resolve(path, "pricing", **valid)
        self.assertTrue(self.invoke(["graph", path])["complete"])

    def test_quick_completion_needs_verifier_but_no_reviewer(self):
        path = self.plan("quick")
        self.invoke(["claim", path, "tax", "--owner", "worker-a"])
        self.resolve(path, "tax", status="done", evidence="Tax result", verification="Exit 0")
        self.assertEqual(self.invoke(["graph", path])["frontier"], ["pricing"])

    def test_independent_scopes_can_run_concurrently_but_parent_scopes_conflict(self):
        self.definition["tasks"][1]["blocked_by"] = []
        path = self.plan()
        self.invoke(["claim", path, "tax", "--owner", "worker-a"])
        self.invoke(["claim", path, "pricing", "--owner", "worker-b"])
        self.assertEqual(sum(task["status"] == "running" for task in self.invoke(["graph", path])["tasks"]), 2)
        self.definition["tasks"][1]["scope"] = ["orders"]
        path = self.plan()
        self.invoke(["claim", path, "tax", "--owner", "worker-a"])
        with self.assertRaisesRegex(ValueError, "scope owned by tax"):
            self.invoke(["claim", path, "pricing", "--owner", "worker-b"])

    def test_parallel_claims_are_atomic_at_capacity(self):
        self.definition["capacity"] = 1
        self.definition["tasks"][1]["blocked_by"] = []
        path = self.plan()
        processes = [subprocess.Popen([sys.executable, str(RUNTIME), "claim", path, task, "--owner", task],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for task in ("tax", "pricing")]
        for process in processes:
            process.communicate(timeout=10)
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1])
        self.assertEqual(sum(task["status"] == "running" for task in self.invoke(["graph", path])["tasks"]), 1)

    def test_recovery_retains_claims_and_completed_tasks_without_model_access(self):
        path = self.plan()
        self.invoke(["claim", path, "tax", "--owner", "old-session"])
        with patch.object(runtime, "available_models", side_effect=AssertionError("Coordination is offline")):
            result = subprocess.run([sys.executable, str(RUNTIME), "graph", path], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)["tasks"][0]["owner"], "old-session")
            with self.assertRaises(ValueError):
                self.resolve(path, "tax", status="pending", evidence="Interrupted")
            self.resolve(path, "tax", status="pending", stopped=True, evidence="Owner confirmed stopped; partial changes located")
            result = self.invoke(["claim", path, "tax", "--owner", "new-session"])
            self.assertEqual(result["attempt"], 2)
            self.resolve(path, "tax", status="done", evidence="Finished", verification="Exit 0", review="Accepted")
            with self.assertRaises(ValueError):
                self.resolve(path, "tax", status="pending", stopped=True, evidence="Retry completed work")
            state = json.loads((Path(path) / "plan.json").read_text())
            self.assertEqual(len(state["history"]), 4)

    def test_blocked_tasks_keep_dependents_blocked_until_explicit_retry(self):
        path = self.plan()
        self.invoke(["claim", path, "tax", "--owner", "worker-a"])
        self.resolve(path, "tax", status="blocked", evidence="Required rate policy is missing")
        self.assertEqual(self.invoke(["graph", path])["frontier"], [])
        with self.assertRaises(ValueError):
            self.invoke(["claim", path, "tax", "--owner", "worker-b"])
        self.resolve(path, "tax", status="pending", stopped=True, evidence="Policy supplied and previous worker ended")
        self.assertEqual(self.invoke(["graph", path])["frontier"], ["tax"])

    def test_worker_identity_survives_handoff_and_plan_cleanup_is_bounded(self):
        path = self.plan()
        with self.assertRaises(ValueError):
            self.invoke(["bind", path, "tax", "--owner", "agent-id", "--attempt", "1"])
        self.invoke(["claim", path, "tax", "--owner", "dispatch-label"])
        self.invoke(["bind", path, "tax", "--owner", "actual-agent-id", "--attempt", "1"])
        self.assertEqual(self.invoke(["graph", path])["tasks"][0]["owner"], "actual-agent-id")
        with redirect_stdout(io.StringIO()):
            runtime.main(["cleanup", path])
        self.assertFalse(Path(path).exists())

    def test_stale_results_and_bindings_cannot_complete_a_new_attempt(self):
        path = self.plan()
        self.invoke(["claim", path, "tax", "--owner", "old"])
        self.resolve(path, "tax", status="pending", stopped=True, evidence="Old owner stopped")
        self.invoke(["claim", path, "tax", "--owner", "new"])
        with self.assertRaisesRegex(ValueError, "current owner"):
            self.resolve(path, "tax", status="done", owner="old", attempt=1, evidence="Late result", verification="Passed", review="Accepted")
        with self.assertRaisesRegex(ValueError, "running attempt"):
            self.invoke(["bind", path, "tax", "--owner", "old-agent", "--attempt", "1"])
        self.assertEqual(self.invoke(["graph", path])["tasks"][0]["owner"], "new")
        self.assertEqual(self.invoke(["graph", path])["frontier"], [])

    def test_symlink_aliases_cannot_claim_the_same_source(self):
        with tempfile.TemporaryDirectory() as workspace:
            root=Path(workspace); (root/"orders").mkdir(); (root/"alias").symlink_to(root/"orders",target_is_directory=True)
            self.definition["tasks"][1].update(scope=["alias/tax.py"],blocked_by=[])
            result=self.invoke(["plan","claude","standard","--workspace",workspace],self.definition)
            path=result["plan"]; self.addCleanup(lambda: runtime.shutil.rmtree(path))
            self.invoke(["claim",path,"tax","--owner","a"])
            with self.assertRaisesRegex(ValueError,"scope owned"):
                self.invoke(["claim",path,"pricing","--owner","b"])

    def test_invalid_graphs_never_create_artifacts(self):
        import copy
        invalid = []
        for field, value in (("blocked_by", ["unknown"]), ("scope", ["../source"]),
                             ("scope", ["/source"]), ("scope", ["orders/*"]), ("acceptance", [])):
            definition = copy.deepcopy(self.definition)
            definition["tasks"][0][field] = value
            invalid.append(definition)
        cycle = copy.deepcopy(self.definition)
        cycle["tasks"][0]["blocked_by"] = ["pricing"]
        invalid.append(cycle)
        for definition in invalid:
            with patch.object(runtime.tempfile, "mkdtemp") as create, self.assertRaises(ValueError):
                self.invoke(["plan", "claude", "standard"], definition)
            create.assert_not_called()

    def test_symlinked_plan_cannot_expose_or_mutate_source(self):
        path = self.plan()
        victim = Path(path) / "victim.json"
        victim.write_text("{}")
        (Path(path) / "plan.json").unlink()
        (Path(path) / "plan.json").symlink_to(victim)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.invoke(["graph", path])
        self.assertEqual(victim.read_text(), "{}")

    def test_schedule_guard_accepts_literal_data_and_retains_family_boundary(self):
        path = self.plan()
        script = 'python3 "$HOME/.agents/orchestrator-runtime.py"'
        self.assertTrue(guard.coordination_command(script + " plan claude standard <<'PLAN'\n{}\nPLAN", "orchestrator-claude"))
        self.assertFalse(guard.coordination_command(script + " plan codex standard <<'PLAN'\n{}\nPLAN", "orchestrator-claude"))
        self.assertTrue(guard.coordination_command(script + f" claim {path} tax --owner worker-a", "orchestrator-claude"))
        self.assertFalse(guard.coordination_command(script + f" claim {path} tax --owner worker-a", "orchestrator-codex"))
        self.assertTrue(guard.coordination_command(script + f" resolve {path} tax <<'RESULT'\n{{}}\nRESULT", "orchestrator-claude"))
        self.assertFalse(guard.coordination_command(script + f" resolve {path} tax <<'RESULT'\n{{}}\nRESULT", "orchestrator-hybrid"))
