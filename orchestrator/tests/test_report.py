"""Exercise the compact runtime report and the guard's coordination tools without model calls."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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


runtime = load(RUNTIME, "orchestrator_runtime_report")


def command_receipt(index, output, command=None, exit_code=0):
    return {"type": "item.completed", "item": {
        "id": f"item_{index}", "type": "command_execution", "command": command or f"echo step-{index}",
        "exit_code": exit_code, "aggregated_output": output}}


def file_change_receipt(index, path):
    return {"type": "item.completed", "item": {
        "id": f"item_{index}", "type": "file_change", "status": "completed",
        "changes": [{"path": path, "kind": "update", "diff": "@@ -1 +1 @@\n-old\n+new\n"}]}}


def receipt_lines(output):
    """Every JSON line that carries a receipt_id, in printed order."""
    lines = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and "receipt_id" in value:
            lines.append(value)
    return lines


class FinalReportTests(unittest.TestCase):
    def setUp(self):
        models = [{"model": model, "supportedReasoningEfforts": [{"reasoningEffort": effort} for effort in ("low", "medium", "high", "xhigh")]}
                  for model in ("gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra")]
        catalog = patch.object(runtime, "available_models", return_value=(models, "live Codex model/list"))
        catalog.start()
        self.addCleanup(catalog.stop)

    def new_run(self, role="implementer"):
        with redirect_stdout(io.StringIO()) as output:
            runtime.main(["new", "codex", "standard", role])
        run = Path(json.loads(output.getvalue())["run"])
        self.addCleanup(lambda: runtime.shutil.rmtree(run) if run.exists() else None)
        return run

    def write_run(self, run, *, status, exit_code, final, stderr, receipts=3, extra=()):
        events = [command_receipt(index, "receipt-output-" + "x" * 900) for index in range(1, receipts + 1)]
        events += list(extra)
        events.append({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 4}})
        (run / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
        (run / "execution.json").write_text(json.dumps({"status": status, "exit_code": exit_code}))
        (run / "final.md").write_text(final)
        (run / "stderr.log").write_text(stderr)

    def report(self, run, *options):
        with redirect_stdout(io.StringIO()) as output:
            result = runtime.main(["report", str(run), "--final", *options])
        return result, output.getvalue()

    def default_report(self, run):
        with redirect_stdout(io.StringIO()) as output:
            runtime.main(["report", str(run)])
        return output.getvalue()

    def test_completed_run_prints_final_receipts_without_output_and_summary(self):
        run = self.new_run()
        path = str(run / "orders" / "tax.py")
        self.write_run(run, status="completed", exit_code=0, final="Changed orders/tax.py.",
                       stderr="proxy chatter", extra=[file_change_receipt(4, path)])
        result, output = self.report(run)
        self.assertEqual(result, 0)
        self.assertTrue(output.startswith("final.md:\nChanged orders/tax.py.\n"))
        self.assertNotIn("receipt-output-", output)
        self.assertNotIn("@@", output)
        self.assertNotIn("proxy chatter", output)
        expected = receipt_lines(self.default_report(run))
        for line in expected:
            line.pop("output", None)
        self.assertEqual(len(expected), 4)
        self.assertEqual(receipt_lines(output), expected)
        self.assertEqual(receipt_lines(output)[-1]["file_changes"], [{"path": path, "kind": "update"}])
        summary = json.loads(output.splitlines()[-1])["execution_summary"]
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["exit_code"], 0)
        self.assertEqual(summary["receipt_ids"], ["item_1", "item_2", "item_3", "item_4"])
        self.assertEqual(summary["pending_receipt_ids"], [])
        self.assertEqual(summary["evidence_issues"], [])
        self.assertEqual(summary["usage"], {"input_tokens": 10, "output_tokens": 4})

    def test_failing_verifier_command_stays_visible_when_the_report_claims_success(self):
        run = self.new_run(role="verifier")
        self.write_run(run, status="completed", exit_code=0, final="All checks passed.", stderr="", receipts=0,
                       extra=[command_receipt(1, "FAILED (failures=1)", command="python3 -m unittest -q", exit_code=1)])
        _, output = self.report(run)
        self.assertEqual(receipt_lines(output), [{
            "run": str(run), "role": "verifier", "verifier_command": "python3 -m unittest -q",
            "exit_code": 1, "receipt_id": "item_1", "output_truncated": False}])

    def test_command_over_500_characters_is_truncated_and_marked(self):
        # 21 long `python3 -c` receipts at a 2000-character cap overflowed the host output limit.
        run = self.new_run()
        exact = "echo " + "e" * 495
        long_command = "echo " + "z" * 600
        self.write_run(run, status="completed", exit_code=0, final="Done.", stderr="", receipts=0,
                       extra=[command_receipt(1, "ok", command=exact), command_receipt(2, "ok", command=long_command)])
        _, output = self.report(run)
        kept, cut = receipt_lines(output)
        self.assertEqual(kept["worker_command"], exact)
        self.assertNotIn("command_truncated", kept)
        self.assertEqual(cut["worker_command"], long_command[:500])
        self.assertIs(cut["command_truncated"], True)
        default = [line for line in receipt_lines(self.default_report(run)) if line["receipt_id"] == "item_2"]
        self.assertEqual(default[0]["worker_command"], long_command)

    def test_final_report_stays_smaller_than_the_default_report(self):
        run = self.new_run()
        self.write_run(run, status="completed", exit_code=0, final="Done.", stderr="", receipts=20)
        _, compact = self.report(run)
        default = self.default_report(run)
        self.assertLess(len(compact) * 3, len(default))

    def test_failed_run_adds_only_the_stderr_tail(self):
        run = self.new_run()
        stderr = "HEAD-" + "y" * (runtime.STDERR_EXCERPT + 500) + "-TAIL"
        self.write_run(run, status="failed", exit_code=1, final="Partial.", stderr=stderr)
        result, output = self.report(run)
        self.assertEqual(result, 0)
        self.assertIn(stderr[-runtime.STDERR_EXCERPT:], output)
        self.assertNotIn("HEAD-", output)
        self.assertIn(f"[truncated; recover with report {run} --full]", output)
        self.assertNotIn("receipt-output-", output)

    def test_evidence_issues_add_the_stderr_tail_and_exit_one(self):
        run = self.new_run()
        self.write_run(run, status="completed", exit_code=0, final="Receipts: item_99\n", stderr="caveman: launching direct")
        result, output = self.report(run)
        self.assertEqual(result, 1)
        self.assertIn("caveman: launching direct", output)
        summary = json.loads(output.splitlines()[-1])["execution_summary"]
        self.assertIn("Report cites receipt IDs absent from completed execution events", summary["evidence_issues"])

    def test_final_excludes_full_and_receipt(self):
        run = self.new_run()
        self.write_run(run, status="completed", exit_code=0, final="Done.", stderr="")
        for options in (["--full"], ["--receipt", "item_1"]):
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, "excludes --full and --receipt"):
                self.report(run, *options)


class GuardCoordinationTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)

    def hook(self, **values):
        result = subprocess.run([sys.executable, str(GUARD)], input=json.dumps({
            "session_id": "session-report", "hook_event_name": "PreToolUse", **values}),
            text=True, capture_output=True, env={**os.environ, "HOME": self.home.name})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout else {}

    def test_orchestrator_may_read_notifications_and_the_compact_report(self):
        self.hook(tool_name="Skill", tool_input={"skill": "orchestrator-claude"})
        self.assertEqual(self.hook(tool_name="ReadNotifications", tool_input={}), {})
        command = 'python3 "$HOME/.agents/orchestrator-runtime.py" report /tmp/orchestrator-run --final'
        self.assertEqual(self.hook(tool_name="Bash", tool_input={"command": command}), {})
        for tool in ("Read", "ReadMcpResourceTool", "WebFetch"):
            with self.subTest(tool=tool):
                decision = self.hook(tool_name=tool, tool_input={})
                self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
