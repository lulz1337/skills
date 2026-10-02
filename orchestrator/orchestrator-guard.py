#!/usr/bin/env python3
"""Keep explicitly selected orchestration sessions out of repository tools."""

import hashlib
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import shlex
import sys

SKILLS = {f"orchestrator-{family}" for family in ("claude", "codex", "hybrid")}
COORDINATION = {"Agent", "Task", "TaskOutput", "TaskStop", "TaskCreate", "TaskGet",
                "TaskList", "TaskUpdate", "TodoWrite", "AskUserQuestion", "Skill",
                "ToolSearch", "SendMessage", "EnterPlanMode", "ExitPlanMode"}
DENIED = {"Read", "Edit", "Write", "NotebookEdit", "MultiEdit", "Glob", "Grep"}
ACTIVATE = re.compile(r"^[/$](orchestrator-(?:claude|codex|hybrid))(?=\s|$)")
NATIVE_ACTIVATE = re.compile(r"(?<![\w$])\$(orchestrator-(?:claude|codex|hybrid))(?=\s|$)")
RUNTIME = Path(__file__).resolve().parent / "orchestrator-runtime.py"


def coordination_command(command, skill=None):
    """Allow a single runtime call, optionally with a literal brief on stdin."""
    header, sep, rest = command.strip().partition("\n")
    heredoc = re.search(r"\s+<<\s*'([A-Za-z_][A-Za-z_0-9]*)'\s*$", header)
    if heredoc:
        marker = heredoc[1]
        lines = rest.splitlines()
        if not sep or not lines or lines[-1] != marker or marker in lines[:-1]:
            return False
        header = header[:heredoc.start()]
    elif sep:
        return False
    # No substitutions, command lists, pipes, redirects or arbitrary interpreters.
    if re.search(r"[`;&|<>\n\r]|\$\(", header):
        return False
    try:
        args = shlex.split(header)
    except ValueError:
        return False
    if args == ["git", "status", "--short"] and not heredoc:
        return True
    if len(args) < 3 or args[0] != "python3":
        return False
    script = args[1]
    allowed_paths = {str(RUNTIME), str(Path.home() / ".agents/orchestrator-runtime.py"),
                     "$HOME/.agents/orchestrator-runtime.py", "${HOME}/.agents/orchestrator-runtime.py",
                     "~/.agents/orchestrator-runtime.py"}
    if script not in allowed_paths:
        return False
    if "$" in " ".join(args[2:]) or args[2].startswith("-") and args[2] != "--help":
        return False
    stdin_actions = {"brief", "plan", "resolve"}
    if heredoc and args[2] not in stdin_actions:
        return False
    if not heredoc and args[2] in stdin_actions:
        return False
    if skill and args[2] in {"new", "plan"} and (len(args) < 4 or args[3] != skill.removeprefix("orchestrator-")):
        return False
    # Parse exactly the runtime's public CLI without executing an operation.
    import importlib.util
    spec = importlib.util.spec_from_file_location("orchestrator_runtime", RUNTIME)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            parsed = runtime.parser().parse_args(args[2:])
    except SystemExit as exc:
        return exc.code == 0
    if skill and parsed.action in {"start", "prompt", "start-many", "summary"}:
        try:
            for value in parsed.runs if hasattr(parsed, "runs") else [parsed.run]:
                run = runtime.run_path(value)
                meta = json.loads(runtime.artifact(run, "run.json").read_text())
                if meta.get("family") != skill.removeprefix("orchestrator-"):
                    return False
            if getattr(parsed, "plan", None):
                run = runtime.run_path(parsed.plan)
                meta = json.loads(runtime.artifact(run, "plan.json").read_text())
                if meta.get("family") != skill.removeprefix("orchestrator-"):
                    return False
        except (OSError, ValueError, KeyError):
            return False
    if skill and parsed.action in {"claim", "bind", "resolve"}:
        try:
            run = runtime.run_path(parsed.plan)
            meta = json.loads(runtime.artifact(run, "plan.json").read_text())
            if meta.get("family") != skill.removeprefix("orchestrator-"):
                return False
        except (OSError, ValueError, KeyError):
            return False
    return True


def denied_tool(tool, inputs, skill=None):
    if tool == "Bash":
        return not coordination_command(str(inputs.get("command", "")), skill)
    return tool in DENIED or tool not in COORDINATION


def routed_agent(skill, agent_type):
    mode = r"(?:quick|fast|standard|comprehensive)"
    reviewed = r"(?:fast|standard|comprehensive)"
    if skill == "orchestrator-codex":
        return False  # Codex roles start through the runtime, never Claude Agent.
    if skill == "orchestrator-hybrid":
        return bool(re.fullmatch(rf"reviewer-hybrid-{reviewed}|orch-sage-{mode}|orch-critic-{reviewed}", agent_type))
    return bool(re.fullmatch(rf"worker-{mode}|reviewer-{reviewed}|orch-(?:scout|verifier|runner|researcher|browser|oracle|sage)-{mode}|orch-critic-{reviewed}", agent_type))


def main(provider="claude"):
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    # agent_type also exists for a top-level --agent, so it is not proof of delegation.
    if data.get("agent_id"):
        return 0
    session = data.get("session_id")
    if not session:
        return 0
    state_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) if provider == "codex" else Path.home() / ".claude"
    state_dir = state_home / "orchestrator-state"
    state = state_dir / (hashlib.sha256(str(session).encode()).hexdigest() + ".json")
    event = data.get("hook_event_name")
    inputs = data.get("tool_input") or {}
    selected = None
    if event == "UserPromptSubmit":
        prompt = str(data.get("prompt", "")).strip()
        if prompt.lower() == "orchestrator off":
            state.unlink(missing_ok=True)
            return 0
        match = (NATIVE_ACTIVATE.search(prompt) if provider == "codex" else None) or ACTIVATE.search(prompt)
        if match:
            selected = match[1]
    elif event == "PreToolUse" and data.get("tool_name") == "Skill":
        skill = str(inputs.get("skill", "")).split(":")[-1]
        if skill in SKILLS:
            selected = skill
    if selected:
        state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        state.write_text(json.dumps({"skill": selected}))
    if event != "PreToolUse" or not state.exists():
        return 0
    tool = data.get("tool_name", "")
    policy = json.loads(state.read_text())
    if provider == "codex" and tool in {"update_plan", "request_user_input"}:
        return 0
    wrong_family = tool in {"Agent", "Task"} and not routed_agent(policy["skill"], str(inputs.get("subagent_type", "")))
    if denied_tool(tool, inputs, policy["skill"]) or wrong_family:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "Orchestrator mode delegates repository reads, searches, changes, checks, web and browser work to workers. Use only the selected family's Agent roster or runtime roles for coordination. Only the user's exact message 'orchestrator off' ends this mode."
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main("codex" if sys.argv[1:] == ["--provider", "codex"] else "claude"))
