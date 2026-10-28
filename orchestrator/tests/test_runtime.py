"""Exercise Codex reviewer and critic dispatch and its process arguments without model calls."""

from contextlib import contextmanager, redirect_stderr, redirect_stdout
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

BUNDLE = Path(__file__).resolve().parents[1]
RUNTIME = BUNDLE / "orchestrator-runtime.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load(RUNTIME, "orchestrator_runtime")


@contextmanager
def temp_root(path):
    """Make tempfile.gettempdir() resolve to path, as a process started with TMPDIR=path sees it."""
    original = tempfile.tempdir
    with patch.dict(os.environ, {"TMPDIR": str(path)}):
        # A test run inside Claude Code may inherit CLAUDE_CODE_TMPDIR, which outranks TMPDIR.
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
    (stale / stale_file).write_text(json.dumps({"family": "hybrid"}))
    return base, sandbox, stale


@contextmanager
def sandbox_view(base, sandbox):
    """The Claude sandbox: TMPDIR is base/claude-<uid> and bare base is read-only.

    Only this view gets a read-only base. An unsandboxed start can write its TMPDIR;
    gettempdir() silently skips an unwritable TMPDIR, so a read-only base there would fake /tmp.
    """
    base.chmod(0o555)
    try:
        # An older run_root() normalized this view to base, which the sandbox cannot write.
        assert not os.access(base, os.W_OK), "run as a user that read-only modes apply to"
        with temp_root(sandbox):
            yield
    finally:
        base.chmod(0o700)


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

    def new_run(self, family="hybrid", mode="standard", role="reviewer"):
        output = io.StringIO()
        with redirect_stdout(output):
            runtime.main(["new", family, mode, role])
        run = Path(json.loads(output.getvalue())["run"])
        self.addCleanup(lambda: runtime.shutil.rmtree(run) if run.exists() else None)
        return run

    def test_reviewer_and_critic_are_read_only_sol_runs_in_both_family_names(self):
        for family in runtime.FAMILIES:
            for mode in runtime.MODES:
                for role in runtime.ROLES:
                    with self.subTest(family=family, mode=mode, role=role):
                        if mode == "quick":
                            with self.assertRaisesRegex(ValueError, "quick has no review"):
                                runtime.role_settings(family, mode, role)
                            continue
                        settings = runtime.role_settings(family, mode, role)
                        self.assertEqual((settings["kind"], settings["agent_type"], settings["model"],
                                          settings["effort"], settings["sandbox"]),
                                         ("codex", role, "gpt-6.1-sol", "high", "read-only"))
                        self.assertTrue(settings["body"])
                        # `codex` is an alias of `hybrid`, not a second policy.
                        self.assertEqual(settings, runtime.role_settings("hybrid", mode, role))

    def test_abolished_roles_families_and_scheduling_commands_are_rejected(self):
        for arguments in (["new", "hybrid", "standard", "scout"], ["new", "hybrid", "standard", "implementer"],
                          ["new", "claude", "standard", "reviewer"], ["plan", "hybrid", "standard"],
                          ["graph", "/tmp/x"], ["instructions", "hybrid", "standard", "roles"]):
            with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runtime.main(arguments)
        with self.assertRaisesRegex(ValueError, "only reviewer and critic"):
            runtime.role_settings("hybrid", "standard", "verifier")

    def test_sandbox_tmpdir_and_unsandboxed_start_agree_on_run_root(self):
        original_tempdir = tempfile.tempdir
        try:
            with tempfile.TemporaryDirectory() as temp:
                sandbox = Path(temp) / f"claude-{os.getuid()}"
                sandbox.mkdir(mode=0o700)
                with temp_root(sandbox):
                    run = self.new_run()
                    self.assertEqual(run.parent, sandbox.resolve())
                with temp_root(temp):
                    self.assertEqual(runtime.run_path(run), run)
                    nested = sandbox / "other" / "orchestrator-invalid"
                    nested.mkdir(parents=True)
                    with self.assertRaisesRegex(ValueError, "expected a runtime-created temporary run directory"):
                        runtime.run_path(nested)
                    runtime.shutil.rmtree(run)
        finally:
            tempfile.tempdir = original_tempdir

    def test_sandbox_creates_runs_under_its_own_tmpdir_and_rejects_stale_runs(self):
        base, sandbox, stale = sandbox_layout(self, "orchestrator-old", "run.json")
        with sandbox_view(base, sandbox):
            run = self.new_run()
        self.assertEqual(run.parent, sandbox)
        with temp_root(base):
            self.assertEqual(runtime.run_root(), sandbox)
            self.assertEqual(runtime.run_path(run), run)
            # Runs that older sessions left under bare /tmp no longer validate.
            with self.assertRaisesRegex(ValueError, "expected a runtime-created temporary run directory"):
                runtime.run_path(stale)

    def test_creation_makes_a_private_root_and_refuses_a_shared_one(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root = base / f"claude-{os.getuid()}"
            with temp_root(base):
                run = self.new_run()
                self.assertEqual(run.parent, root)
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)
                runtime.shutil.rmtree(run)
                for mode in (0o770, 0o707):
                    root.chmod(mode)
                    with self.subTest(mode=oct(mode)):
                        self.assert_root_refused(root)
                    self.assertEqual(list(root.iterdir()), [])

    def assert_root_refused(self, root):
        with redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(ValueError, re.escape(f"run root {root} must be a directory owned by uid")):
            runtime.main(["new", "hybrid", "standard", "reviewer"])

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

    def test_claude_code_tmpdir_sets_the_base_for_both_views(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as unrelated:
            base = Path(temp).resolve()
            root = base / f"claude-{os.getuid()}"
            for tmpdir in (unrelated, root):
                with self.subTest(tmpdir=str(tmpdir)), temp_root(tmpdir), \
                        patch.dict(os.environ, {"CLAUDE_CODE_TMPDIR": temp}):
                    self.assertEqual(runtime.run_root(), root)
            with temp_root(unrelated), patch.dict(os.environ, {"CLAUDE_CODE_TMPDIR": ""}):
                self.assertEqual(runtime.run_root(), Path(unrelated).resolve() / root.name)

    def test_instructions_print_the_resolved_reviewer_and_critic(self):
        printed = {}
        for family in runtime.FAMILIES:
            with self.subTest(family=family), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(runtime.main(["instructions", family, "standard"]), 0)
            lines = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertIn("one family", lines[0]["note"])
            printed[family] = [line for line in lines if "role" in line]
            self.assertEqual([line["role"] for line in printed[family]], ["reviewer", "critic"])
            self.assertTrue(all(line["model"] == "gpt-6.1-sol" and "body" not in line for line in printed[family]))
        self.assertEqual(printed["hybrid"], printed["codex"])
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runtime.main(["instructions", "hybrid", "quick"]), 0)
        self.assertNotIn('"role"', output.getvalue())
        self.assertIn("quick has no review", output.getvalue())

    def test_brief_is_literal_and_codex_process_has_resolved_settings(self):
        run = self.new_run()
        brief = "GOAL: Review source\nEVIDENCE: pytest exit 0\nLiteral $(touch forbidden)"
        with patch.object(sys, "stdin", io.StringIO(brief)), redirect_stdout(io.StringIO()):
            runtime.main(["brief", str(run)])
        prompt = (run / "prompt.md").read_text()
        self.assertIn(brief, prompt)
        self.assertIn("You are reviewer, a read-only review subagent.", prompt)
        self.assertIn("command is still running", prompt)
        with patch.object(runtime.subprocess, "call", return_value=0) as call, redirect_stdout(io.StringIO()):
            self.assertEqual(runtime.main(["start", str(run)]), 0)
            cmd = call.call_args.args[0]
            self.assertEqual(cmd[:2], ["codex", "exec"])
            self.assertIn("gpt-6.1-sol", cmd)
            self.assertIn("model_reasoning_effort=high", cmd)
            self.assertIn("sandbox_mode=read-only", cmd)
            self.assertIn("features.hooks=false", cmd)
            self.assertNotEqual(call.call_args.kwargs["env"]["CODEX_HOME"], os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
            self.assertFalse(Path(call.call_args.kwargs["env"]["CODEX_HOME"]).exists())
            self.assertEqual(cmd[-1], "-")
            self.assertNotIn("-a", cmd)
            self.assertEqual(call.call_args.kwargs["stdin"].name, str(run / "prompt.md"))

    def test_dispatch_requires_live_freshness_but_reports_remain_available_offline(self):
        run = self.new_run()
        with patch.object(sys, "stdin", io.StringIO("GOAL: bounded review")), redirect_stdout(io.StringIO()):
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

    def test_sandboxed_catalog_failure_names_the_fix_for_the_host(self):
        run = self.new_run(role="critic")
        with patch.object(sys, "stdin", io.StringIO("GOAL: critique")), redirect_stdout(io.StringIO()):
            runtime.main(["brief", str(run)])
        source = ("cached Codex catalog; live catalog unavailable: codex app-server exited before a catalog response "
                  "(exit code 1); stderr: Error: Read-only file system (os error 30)")
        models, _ = runtime.available_models()
        for host, expected, absent in (({"CLAUDECODE": "1"}, "dangerouslyDisableSandbox", "/permissions"),
                                       ({}, "/permissions", "dangerouslyDisableSandbox")):
            with self.subTest(host=host), patch.dict(os.environ, host), \
                    patch.object(runtime, "available_models", return_value=(models, source)):
                if not host:
                    os.environ.pop("CLAUDECODE", None)
                with self.assertRaises(ValueError) as error:
                    runtime.main(["start", str(run)])
                self.assertIn(expected, str(error.exception))
                self.assertNotIn(absent, str(error.exception))

    def test_child_configuration_keeps_auth_without_inheriting_host_hooks(self):
        run = self.new_run()
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
                run = self.new_run()
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
                    "run": str(run), "role": "reviewer",
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

    def test_reports_expose_commands_for_reviewer_and_critic(self):
        for role in runtime.ROLES:
            with self.subTest(role=role):
                run = self.new_run(role=role)
                event = {"type": "item.completed", "item": {"type": "command_execution", "command": "git diff --stat", "exit_code": 1, "aggregated_output": "FAILED"}}
                (run / "events.jsonl").write_text(json.dumps(event) + "\n")
                with redirect_stdout(io.StringIO()) as output:
                    runtime.main(["report", str(run)])
                receipt = json.loads(output.getvalue().splitlines()[0])
                self.assertEqual(receipt["worker_command"], event["item"]["command"])
                self.assertEqual(receipt["role"], role)
                self.assertEqual(receipt["exit_code"], 1)
                self.assertEqual(receipt["output"], "FAILED")

    def test_final_report_truncates_long_commands_and_shows_stderr_only_when_flagged(self):
        run = self.new_run()
        command = "rg " + "x" * 600
        event = {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution", "command": command, "exit_code": 0, "aggregated_output": "match"}}
        (run / "events.jsonl").write_text(json.dumps(event) + "\n")
        (run / "final.md").write_text("No findings.\nReceipts: item_1")
        (run / "stderr.log").write_text("warning: noisy")
        (run / "execution.json").write_text(json.dumps({"status": "completed"}))
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runtime.main(["report", str(run), "--final"]), 0)
        receipt = next(json.loads(line) for line in output.getvalue().splitlines() if "worker_command" in line)
        self.assertEqual(len(receipt["worker_command"]), runtime.COMMAND_LIMIT)
        self.assertTrue(receipt["command_truncated"])
        self.assertNotIn("output", receipt)
        self.assertNotIn("stderr.log", output.getvalue())
        (run / "execution.json").write_text(json.dumps({"status": "failed"}))
        with redirect_stdout(io.StringIO()) as output:
            runtime.main(["report", str(run), "--final"])
        self.assertIn("warning: noisy", output.getvalue())

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
        runs = [self.new_run(role=role) for role in runtime.ROLES]
        for run in runs:
            (run / "prompt.md").write_text("Review the owned diff")
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

    def test_batch_rejects_duplicate_runs_mixed_families_and_stale_catalogs_before_launch(self):
        runs = [self.new_run(), self.new_run(role="critic")]
        for run in runs:
            (run / "prompt.md").write_text("Review source")
        with patch.object(runtime.subprocess, "call") as child:
            with self.assertRaisesRegex(ValueError, "unique"):
                runtime.main(["start-many", str(runs[0]), str(runs[0])])
            models, _ = runtime.available_models()
            with patch.object(runtime, "available_models", return_value=(models, "cached Codex catalog")), \
                    self.assertRaisesRegex(ValueError, "Cannot verify the newest model"):
                runtime.main(["start-many", *map(str, runs)])
            meta = json.loads((runs[1] / "run.json").read_text())
            meta["family"] = "codex"
            (runs[1] / "run.json").write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError, "share family"):
                runtime.main(["start-many", *map(str, runs)])
            child.assert_not_called()

    def test_started_run_cannot_overwrite_its_evidence(self):
        run = self.new_run()
        (run / "prompt.md").write_text("Read source")
        with patch.object(runtime.subprocess, "call", return_value=0), redirect_stdout(io.StringIO()):
            runtime.main(["start", str(run)])
        (run / "events.jsonl").write_text("preserved evidence")
        with patch.object(runtime.subprocess, "call") as child, self.assertRaisesRegex(ValueError, "already started"):
            runtime.main(["start", str(run)])
        child.assert_not_called()
        self.assertEqual((run / "events.jsonl").read_text(), "preserved evidence")

    def test_rebrief_preserves_the_prompt_during_and_after_execution(self):
        run = self.new_run()
        (run / "prompt.md").write_text("Original brief")
        with runtime.unstarted_run(run), patch.object(sys, "stdin", io.StringIO("Changed brief")):
            with self.assertRaisesRegex(ValueError, "already executing"):
                runtime.main(["brief", str(run)])
        (run / "execution.json").write_text(json.dumps({"status": "completed"}))
        with patch.object(sys, "stdin", io.StringIO("Changed brief")):
            with self.assertRaisesRegex(ValueError, "already started"):
                runtime.main(["brief", str(run)])
        self.assertEqual((run / "prompt.md").read_text(), "Original brief")

    def test_report_flags_the_audited_false_empty_output_claims(self):
        run = self.new_run()
        (run / "final.md").write_text("Directory listings returned no output. Shell commands did not return output.")
        event = {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution", "command": "cat AGENTS.md", "exit_code": 0, "aggregated_output": "Instructions"}}
        (run / "events.jsonl").write_text(json.dumps(event) + "\n")
        self.assertEqual(len(runtime.execution_summary(run)["evidence_issues"]), 2)
        (run / "final.md").write_text("Not attempted: directory listings.\nReceipts: item_1")
        self.assertEqual(runtime.execution_summary(run)["evidence_issues"], [])
        (run / "final.md").write_text("Receipts: item_invented")
        self.assertTrue(runtime.execution_summary(run)["evidence_issues"])

    def test_batch_rejects_missing_completed_receipts_despite_zero_exit(self):
        runs = [self.new_run() for _ in range(2)]
        for run in runs:
            (run / "prompt.md").write_text("Review source")
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
        run = self.new_run()
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

    def test_cleanup_removes_only_runtime_runs(self):
        run = self.new_run()
        runtime.main(["cleanup", str(run)])
        self.assertFalse(run.exists())
        with tempfile.TemporaryDirectory() as temp, temp_root(temp):
            bare = runtime.ensure_run_root() / "orchestrator-bare"
            bare.mkdir()
            with self.assertRaisesRegex(ValueError, "cleanup requires runtime run metadata"):
                runtime.main(["cleanup", str(bare)])
            self.assertTrue(bare.exists())

    def test_visible_start_hosts_codex_read_only_and_keeps_report_delivery_in_the_reply(self):
        run = self.new_run()
        with patch.object(sys, "stdin", io.StringIO("GOAL: review")), redirect_stdout(io.StringIO()):
            runtime.main(["brief", str(run)])
        pane = subprocess.CompletedProcess([], 0, json.dumps({"result": {"pane": {"foreground_cwd": json.loads((run / "run.json").read_text())["workspace"]}}}))
        with patch.object(runtime, "visible_available", return_value=True), patch.object(runtime.subprocess, "run", return_value=pane), patch.object(runtime.subprocess, "call", return_value=0) as call, redirect_stdout(io.StringIO()):
            runtime.main(["start", str(run), "--pane", "w1:p4"])
            cmd = call.call_args.args[0]
            self.assertEqual(cmd[cmd.index("--kind") + 1], "codex")
            self.assertIn("sandbox_mode=read-only", cmd)
            self.assertIn("gpt-6.1-sol", cmd)
            runtime.main(["prompt", str(run)])
            prompt = call.call_args.args[0]
            self.assertIn("Reply with your report; do not write a file.", prompt[4])
        with patch.object(runtime, "visible_available", return_value=False), self.assertRaises(ValueError):
            runtime.main(["start", str(run), "--pane", "w1:p4"])

    def test_visible_start_rejects_wrong_workspace_and_keeps_failed_launch_recoverable(self):
        run = self.new_run(mode="fast")
        with patch.object(sys, "stdin", io.StringIO("GOAL: review")), redirect_stdout(io.StringIO()):
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
