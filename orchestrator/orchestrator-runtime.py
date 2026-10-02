#!/usr/bin/env python3
"""Coordination operations that do not expose repository content to the main thread."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

AGENTS = Path(__file__).resolve().parent
FAMILIES = ("claude", "codex", "hybrid")
MODES = ("quick", "fast", "standard", "comprehensive")
ROLES = ("scout", "verifier", "runner", "researcher", "browser", "implementer",
         "reviewer", "oracle", "sage", "critic")
READ_ONLY = {"scout", "researcher", "reviewer", "oracle", "sage", "critic"}
REFERENCES = ("procedure", "examples", "pitfalls", "herdr", "roles", "tools", "workflow", "enforcement", "scheduling")
MODEL_VERSION = re.compile(r"^gpt-(\d+(?:\.\d+)*)-(luna|terra|sol|astra)$")
MODEL_CATALOG = None


def execution_events(run):
    path = artifact(run, "events.jsonl")
    if not path.exists():
        return []
    events = []
    for line in path.read_text().splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def execution_summary(run):
    events = execution_events(run)
    receipts = [event["item"] for event in events if event.get("type") == "item.completed"
                and event.get("item", {}).get("type") in {"command_execution", "mcp_tool_call", "web_search"}]
    usage = {}
    for event in events:
        if event.get("type") == "turn.completed":
            for key, value in event.get("usage", {}).items():
                if type(value) is int:
                    usage[key] = usage.get(key, 0) + value
    execution = artifact(run, "execution.json")
    state = json.loads(execution.read_text()) if execution.exists() else {}
    final = artifact(run, "final.md")
    report = final.read_text() if final.exists() else ""
    issues = []
    completed = {event.get("item", {}).get("id") for event in events if event.get("type") == "item.completed"}
    pending = [event["item"].get("id") for event in events if event.get("type") == "item.started"
               and event.get("item", {}).get("type") in {"command_execution", "mcp_tool_call", "web_search"}
               and event["item"].get("id") not in completed]
    if pending and (state.get("status") in {"completed", "failed", "interrupted"}
                    or any(event.get("type") in {"turn.completed", "turn.failed"} for event in events)):
        issues.append("Started tool actions lack completed execution receipts: " + ", ".join(map(str, pending)))
    # Flag only the concrete unsupported execution claims observed in the audit.
    # This is not semantic validation of arbitrary prose or source citations.
    if re.search(r"(?:directory listings|requested listings).{0,80}(?:returned no output|did not return output)", report, re.I):
        listing = False
        for receipt in receipts:
            command = receipt.get("command", "")
            try:
                words = shlex.split(command)
                if len(words) == 3 and Path(words[0]).name in {"sh", "bash", "zsh"}:
                    command = words[2]
            except ValueError:
                pass
            listing |= bool(re.search(r"(?:^|[;&|])\s*(?:timeout\s+\S+\s+)?(?:ls|find)\s", command))
        if not listing:
            issues.append("Report claims empty directory listings, but no listing execution receipt exists")
    if re.search(r"shell commands.{0,40}(?:returned no output|did not return output)", report, re.I):
        commands = [item for item in receipts if item.get("type") == "command_execution"]
        if not commands or all(item.get("aggregated_output", "").strip() for item in commands):
            issues.append("Report claims empty shell output without a matching empty-output receipt")
    if re.search(r"^Receipts:\s*", report, re.M):
        cited = re.findall(r"\bitem_[A-Za-z0-9_-]+\b", report.split("Receipts:", 1)[1].splitlines()[0])
        known = {item.get("id") for item in receipts}
        if set(cited) - known:
            issues.append("Report cites receipt IDs absent from completed execution events")
    meta = json.loads(artifact(run, "run.json").read_text())
    return {"run": str(run), "family": meta["family"], "role": meta["role"], **state, "usage": usage,
            "completed_receipts": len(receipts), "receipt_ids": [item.get("id") for item in receipts],
            "report_present": final.exists(), "pending_receipt_ids": pending, "evidence_issues": issues}


@contextmanager
def unstarted_run(run):
    """Serialize briefing and execution so a started run keeps its evidence."""
    lock = artifact(run, "execution.lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("run is already executing") from None
        if artifact(run, "execution.json").exists() or artifact(run, "events.jsonl").exists():
            raise ValueError("run was already started; create a new run for a retry")
        yield


def execute_codex(run, meta, fields, bypass=False):
    """Keep one execution receipt and never overwrite an earlier run's evidence."""
    with unstarted_run(run):
        state = {"model": fields["model"], "started_at": time.time(), "status": "running"}
        artifact(run, "execution.json").write_text(json.dumps(state))
        print(json.dumps({"orchestrator_run": {**meta, **{k: v for k, v in fields.items() if k != "body"},
                                                "run": str(run), "metering_requested": not bypass}}), flush=True)
        cmd = ["codex", "exec", "--skip-git-repo-check", "--json", "--output-last-message", str(artifact(run, "final.md")),
               "--cd", meta["workspace"], "--model", fields["model"], "--config", f'model_reasoning_effort={fields["effort"]}',
               "--config", f'sandbox_mode={fields["sandbox"]}', "--config", "features.hooks=false",
               "--config", "features.plugins=false", "--config", "features.skip_host_skill_discovery=true"]
        if bypass:
            cmd += ["--ignore-user-config", "--config", "model_provider=openai"]
        else:
            cmd = ["caveman", "run", "--off", "--", *cmd]
        cmd += ["-"]
        try:
            # Preserve account auth and wrapper routing without inheriting the
            # controller's hooks, MCP servers, provider or global instructions.
            with tempfile.TemporaryDirectory(prefix="orchestrator-auth-") as config:
                auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
                if auth.is_file():
                    shutil.copy2(auth, Path(config) / "auth.json")
                    os.chmod(Path(config) / "auth.json", 0o600)
                env = {**os.environ, "CODEX_HOME": config}
                with artifact(run, "prompt.md").open() as prompt, artifact(run, "events.jsonl").open("w") as events, artifact(run, "stderr.log").open("w") as errors:
                    rc = subprocess.call(cmd, stdin=prompt, stdout=events, stderr=errors, env=env)
            state.update(exit_code=rc, status="completed" if rc == 0 else "failed")
            return rc
        except BaseException:
            state.update(status="interrupted")
            raise
        finally:
            state["finished_at"] = time.time()
            artifact(run, "execution.json").write_text(json.dumps(state))


def start_many(args):
    """Preflight the entire independent batch, then join every execution."""
    if not 1 <= args.capacity <= 9 or not 2 <= len(args.runs) <= 9:
        raise ValueError("batch needs 2 to 9 runs and capacity from 1 to 9")
    runs = [load_run(value) for value in args.runs]
    if len({str(run) for run, _, _ in runs}) != len(runs):
        raise ValueError("batch run paths must be unique")
    if len({(meta["family"], meta["workspace"]) for _, meta, _ in runs}) != 1:
        raise ValueError("batch runs must share family and workspace")
    for run, meta, fields in runs:
        artifact(run, "prompt.md").resolve(strict=True)
        if fields["kind"] != "codex" or fields["model_source"] != "live Codex model/list":
            raise ValueError("batch requires Codex roles with fresh live model settings")
        if artifact(run, "execution.json").exists() or artifact(run, "events.jsonl").exists():
            raise ValueError("batch contains a previously started run")
    writers = [(run, meta) for run, meta, _ in runs if meta["role"] in {"implementer", "runner"}]
    if writers:
        if not args.plan:
            raise ValueError("writable batch requires claimed ownership in --plan")
        with locked_plan(args.plan) as (_, plan):
            if (plan["family"], plan["workspace"]) != (runs[0][1]["family"], runs[0][1]["workspace"]):
                raise ValueError("batch plan has a different family or workspace")
            if args.capacity > plan["capacity"]:
                raise ValueError("batch capacity exceeds plan capacity")
            active = [task for task in plan["tasks"].values() if task["status"] == "running"]
            for run, meta in writers:
                tasks = [task for task in plan["tasks"].values() if task["status"] == "running" and task["owner"] == str(run)
                         and task["role"] == meta["role"]]
                if len(tasks) != 1:
                    raise ValueError("each writable run needs one matching active claim")
                scope = ownership_scope(plan, tasks[0])
                if scope != tasks[0].get("claimed_scope"):
                    raise ValueError("writable scope changed since claim; stop and reclaim it")
                if any(scopes_intersect(scope, ownership_scope(plan, other) + other.get("claimed_scope", []))
                       for other in active if other is not tasks[0]):
                    raise ValueError("writable batch scope overlaps another active owner")
    def launch(values):
        run, meta, fields = values
        try:
            rc = execute_codex(run, meta, fields, args.bypass_caveman)
            return {**execution_summary(run), "exit_code": rc}
        except Exception as error:
            return {"run": str(run), "exit_code": 1, "error": str(error)}
    with ThreadPoolExecutor(max_workers=args.capacity) as pool:
        results = list(pool.map(launch, runs))
    print(json.dumps({"batch_results": results}), flush=True)
    return 1 if any(result["exit_code"] != 0 or result.get("evidence_issues") for result in results) else 0


def available_models():
    """Read the account's live Codex catalog without starting an inference turn."""
    global MODEL_CATALOG
    if MODEL_CATALOG is not None:
        return MODEL_CATALOG
    try:
        proc = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                buffered = b""
                deadline = time.monotonic() + 15

                def rpc(request):
                    nonlocal buffered
                    proc.stdin.write((json.dumps(request) + "\n").encode())
                    proc.stdin.flush()
                    while time.monotonic() < deadline:
                        while b"\n" in buffered:
                            line, buffered = buffered.split(b"\n", 1)
                            response = json.loads(line)
                            if response.get("id") == request["id"]:
                                if "error" in response:
                                    raise ValueError("Codex model catalog request failed")
                                return response["result"]
                        if not selector.select(max(0, deadline - time.monotonic())):
                            break
                        chunk = os.read(proc.stdout.fileno(), 65536)
                        if not chunk:
                            break
                        buffered += chunk
                    raise ValueError("Codex model catalog timed out")

                rpc({"id": 0, "method": "initialize", "params": {"clientInfo": {
                    "name": "dotfiles_orchestrator", "title": "Orchestrator model routing", "version": "1"}}})
                proc.stdin.write(b'{"method":"initialized","params":{}}\n')
                proc.stdin.flush()
                models, cursor, request_id = [], None, 1
                while True:
                    page = rpc({"id": request_id, "method": "model/list", "params": {
                        "limit": 100, "includeHidden": False, "cursor": cursor}})
                    models.extend(page["data"])
                    cursor = page.get("nextCursor")
                    if not cursor:
                        break
                    request_id += 1
                MODEL_CATALOG = (models, "live Codex model/list")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            proc.stdin.close()
            proc.stdout.close()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        cache = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "models_cache.json"
        try:
            data = json.loads(cache.read_text())
            models = [{"model": m["slug"], "hidden": m.get("visibility") == "hide",
                       "supportedReasoningEfforts": [{"reasoningEffort": e["effort"]} for e in m.get("supported_reasoning_levels", [])]}
                      for m in data["models"]]
            MODEL_CATALOG = (models, "cached Codex catalog; live catalog unavailable")
        except (OSError, ValueError, KeyError, TypeError):
            MODEL_CATALOG = ([], "profile fallback; latest model unverified")
    return MODEL_CATALOG


def latest_model(fallback, effort):
    match = MODEL_VERSION.fullmatch(fallback)
    if not match:
        raise ValueError("expected a GPT model tier for automatic model selection")
    version = lambda value: tuple(int(part) for part in value.split("."))
    minimum = version(match[1])
    models, source = available_models()
    candidates = []
    for model in models:
        slug = model.get("model", "")
        candidate = MODEL_VERSION.fullmatch(slug)
        if model.get("hidden") or not candidate or candidate[2] != match[2] or version(candidate[1]) < minimum:
            continue
        supported = {item.get("reasoningEffort") for item in model.get("supportedReasoningEfforts", [])}
        candidates.append((version(candidate[1]), slug, supported))
    if not candidates:
        return fallback, "profile fallback; latest available model unverified"
    _, model, supported = max(candidates, key=lambda item: item[0])
    if supported and effort not in supported:
        raise ValueError(f"newest {match[2]} model {model} does not support configured effort {effort}")
    return model, source


def definition(path):
    _, front, body = path.read_text().split("---", 2)
    fields = dict(line.split(":", 1) for line in front.strip().splitlines() if ":" in line)
    return {key: value.strip() for key, value in fields.items()}, body.strip()


def role_settings(family, mode, role):
    if mode == "quick" and role in {"reviewer", "critic"}:
        raise ValueError("quick has no review; choose fast, standard or comprehensive")
    kind = "claude" if family == "claude" or family == "hybrid" and role in {"reviewer", "sage", "critic"} else "codex"
    if kind == "claude":
        name = f"worker-{mode}" if role == "implementer" else f"reviewer-{'hybrid-' if family == 'hybrid' else ''}{mode}" if role == "reviewer" else f"orch-{role}-{mode}"
        fields, body = definition(AGENTS / "claude-agents" / f"{name}.md")
        return {"kind": kind, "agent_type": name, "model": fields["model"],
                "effort": fields["effort"], "tools": fields["tools"], "body": body,
                "model_source": "Claude latest-family alias"}
    profile, _ = definition(AGENTS / "codex-agents" / "profiles" / f"{mode}.md")
    name = "worker" if role == "implementer" else role
    fields, body = definition(AGENTS / "codex-agents" / f"{name}.md")
    prefix = "reviewer" if role == "reviewer" else "worker"
    model, effort = profile[f"{prefix}_model"], profile[f"{prefix}_reasoning_effort"]
    if role in {"scout", "verifier"}:
        cheap, _ = definition(AGENTS / "codex-agents" / "profiles" / "quick.md")
        model, effort = cheap["worker_model"], cheap["worker_reasoning_effort"]
    if role == 'runner':
        # Closed commands still require correct ordering and observed-state
        # reporting. Luna trials repeatedly treated printed state as unobserved.
        runner_profile, _ = definition(AGENTS / 'codex-agents' / 'profiles' / 'standard.md')
        model, effort = runner_profile['worker_model'], runner_profile['worker_reasoning_effort']
    if role in {"oracle", "sage", "critic"}:
        strong, _ = definition(AGENTS / "codex-agents" / "profiles" / "comprehensive.md")
        model, effort = strong["reviewer_model"], strong["reviewer_reasoning_effort"]
    model, source = latest_model(model, effort)
    # Read-only Codex sandboxes cannot write the verifier's normal build output.
    return {"kind": kind, "agent_type": name, "model": model, "effort": effort,
            "sandbox": fields["sandbox"], "body": body, "model_source": source}


def run_path(value):
    path = Path(value).resolve(strict=True)
    temp = Path(tempfile.gettempdir()).resolve()
    if path.parent != temp or not path.name.startswith("orchestrator-") or not path.is_dir():
        raise ValueError("expected a runtime-created temporary run directory")
    if path.stat().st_uid != os.getuid():
        raise ValueError("run directory belongs to another user")
    return path


def artifact(run, name):
    path = run / name
    if path.is_symlink():
        raise ValueError("run artifacts must not be symlinks")
    return path


def load_run(value, resolve_settings=True):
    run = run_path(value)
    meta = json.loads(artifact(run, "run.json").read_text())
    settings = role_settings(meta["family"], meta["mode"], meta["role"]) if resolve_settings else None
    return run, meta, settings


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value.strip()


def plan_definition(data, family, mode, workspace):
    """Validate a finite task graph before creating coordination state."""
    if not isinstance(data, dict):
        raise ValueError("plan must be a JSON object")
    goal = nonempty(data.get("goal"), "goal")
    capacity = data.get("capacity", 3)
    if type(capacity) is not int or not 1 <= capacity <= 9:
        raise ValueError("capacity must be an integer from 1 to 9, within host capacity")
    source = data.get("tasks")
    if not isinstance(source, list) or not 1 <= len(source) <= 128:
        raise ValueError("tasks must contain 1 to 128 tasks")
    tasks = {}
    for item in source:
        if not isinstance(item, dict):
            raise ValueError("each task must be an object")
        name = nonempty(item.get("id"), "task id")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name) or name in tasks:
            raise ValueError("task IDs must be unique lowercase names")
        role = item.get("role", "implementer")
        if role not in {"implementer", "runner"}:
            raise ValueError("task owner must be implementer or runner")
        lists = {}
        for field in ("scope", "acceptance", "verify", "blocked_by"):
            values = item.get(field, [] if field == "blocked_by" else None)
            if not isinstance(values, list) or (field != "blocked_by" and not values):
                raise ValueError(f"{name}.{field} must be a list" + ("" if field == "blocked_by" else " with at least one item"))
            lists[field] = [nonempty(value, f"{name}.{field}") for value in values]
        for scope in lists["scope"]:
            if scope.startswith("/") or ".." in scope.split("/") or re.search(r"[*?\[\\]", scope):
                raise ValueError("scope must name relative files or directories, without globs")
        lists["scope"] = [str(Path(scope)) for scope in lists["scope"]]
        tasks[name] = {"id": name, "title": nonempty(item.get("title"), "task title"),
                       "role": role, **lists, "status": "pending", "owner": None, "attempt": 0}
    visited, visiting = set(), set()

    def visit(name):
        if name not in tasks:
            raise ValueError(f"unknown blocker: {name}")
        if name in visiting:
            raise ValueError("task graph contains a cycle")
        if name in visited:
            return
        visiting.add(name)
        for blocker in tasks[name]["blocked_by"]:
            visit(blocker)
        visiting.remove(name)
        visited.add(name)

    for name in tasks:
        visit(name)
    return {"family": family, "mode": mode, "workspace": str(Path(workspace).resolve()),
            "goal": goal, "capacity": capacity, "tasks": tasks, "history": []}


def save_plan(run, plan):
    temporary = artifact(run, "plan.pending.json")
    temporary.write_text(json.dumps(plan, indent=2) + "\n")
    os.replace(temporary, artifact(run, "plan.json"))


@contextmanager
def locked_plan(value):
    run = run_path(value)
    lock = artifact(run, "plan.lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        plan = json.loads(artifact(run, "plan.json").read_text())
        yield run, plan


def scopes_intersect(left, right):
    return any(a == "." or b == "." or a == b or Path(a) in Path(b).parents or Path(b) in Path(a).parents
               for a in left for b in right)


def ownership_scope(plan, task):
    """Resolve named scope metadata, without reading source contents."""
    workspace = Path(plan["workspace"]).resolve()
    paths = []
    for scope in task["scope"]:
        path = (workspace / scope).resolve()
        if not path.is_relative_to(workspace):
            raise ValueError("scope resolves outside the assigned workspace")
        paths.append(str(path))
    return paths


def claim_blockers(plan, task):
    if task["status"] != "pending":
        return [f"status is {task['status']}"]
    blockers = [name for name in task["blocked_by"] if plan["tasks"][name]["status"] != "done"]
    running = [other for other in plan["tasks"].values() if other["status"] == "running"]
    reasons = [f"unfinished dependency: {name}" for name in blockers]
    if len(running) >= plan["capacity"]:
        reasons.append("host capacity reached")
    try:
        scope = ownership_scope(plan, task)
        reasons.extend(f"scope owned by {other['id']}" for other in running
                       if scopes_intersect(scope, ownership_scope(plan, other) + other.get("claimed_scope", [])))
    except (ValueError, OSError) as error:
        reasons.append(str(error))
    return reasons


def graph_summary(plan):
    frontier = [name for name, task in plan["tasks"].items() if not claim_blockers(plan, task)]
    return {"goal": plan["goal"], "family": plan["family"], "mode": plan["mode"],
            "workspace": plan["workspace"], "frontier": frontier,
            "complete": all(task["status"] == "done" for task in plan["tasks"].values()),
            "tasks": [{key: task[key] for key in ("id", "title", "status", "owner", "attempt", "blocked_by", "scope")}
                      | {"waits_on": claim_blockers(plan, task), "result": task.get("result")}
                      for task in plan["tasks"].values()]}


def graph_action(args):
    if args.action == "plan":
        plan = plan_definition(json.load(sys.stdin), args.family, args.mode, args.workspace)
        run = Path(tempfile.mkdtemp(prefix="orchestrator-plan-"))
        save_plan(run, plan)
        print(json.dumps({"plan": str(run), **graph_summary(plan)}))
        return 0
    with locked_plan(args.plan) as (run, plan):
        if args.action == "graph":
            print(json.dumps(graph_summary(plan)))
            return 0
        task = plan["tasks"].get(args.task)
        if task is None:
            raise ValueError("unknown task ID")
        if args.action == "claim":
            reasons = claim_blockers(plan, task)
            if reasons:
                raise ValueError("claim blocked: " + "; ".join(reasons))
            task.update(status="running", owner=nonempty(args.owner, "owner"), attempt=task["attempt"] + 1)
            task["claimed_scope"] = ownership_scope(plan, task)
            result = {"family": plan["family"], "mode": plan["mode"], "workspace": plan["workspace"], **task}
        elif args.action == "bind":
            if task["status"] != "running" or args.attempt != task["attempt"]:
                raise ValueError("bind must match the running attempt")
            task["owner"] = nonempty(args.owner, "owner")
            result = {"task": task["id"], "owner": task["owner"], "attempt": task["attempt"]}
        else:
            result = json.load(sys.stdin)
            if not isinstance(result, dict) or result.get("status") not in {"done", "blocked", "pending"}:
                raise ValueError("resolution status must be done, blocked or pending")
            nonempty(result.get("evidence"), "resolution evidence")
            if result.get("owner") != task["owner"] or type(result.get("attempt")) is not int or result["attempt"] != task["attempt"]:
                raise ValueError(f"resolution must match current owner {task['owner']} and attempt {task['attempt']}")
            if result["status"] == "pending":
                if task["status"] not in {"running", "blocked"} or result.get("stopped") is not True:
                    raise ValueError("retry requires an interrupted/blocked task and confirmation that its owner stopped")
                task["owner"] = None
            else:
                if task["status"] != "running":
                    raise ValueError("only a claimed task can be resolved")
                if result["status"] == "done":
                    nonempty(result.get("verification"), "verifier evidence")
                    if plan["mode"] != "quick":
                        nonempty(result.get("review"), "review disposition")
            task.update(status=result["status"], result=result)
        plan["history"].append({"time": time.time(), "action": args.action, "task": args.task,
                                "owner": task["owner"], "attempt": task["attempt"], "result": result})
        save_plan(run, plan)
        print(json.dumps(result))
    return 0


def visible_available():
    return os.environ.get("HERDR_ENV") == "1" and shutil.which("herdr") is not None and subprocess.run(
        ["herdr", "status"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    instructions = sub.add_parser("instructions")
    instructions.add_argument("family", choices=FAMILIES)
    instructions.add_argument("mode", choices=MODES)
    instructions.add_argument("reference", nargs="?", choices=REFERENCES)
    new = sub.add_parser("new")
    new.add_argument("family", choices=FAMILIES)
    new.add_argument("mode", choices=MODES)
    new.add_argument("role", choices=ROLES)
    new.add_argument("--workspace", default=os.getcwd())
    plan = sub.add_parser("plan")
    plan.add_argument("family", choices=FAMILIES)
    plan.add_argument("mode", choices=MODES)
    plan.add_argument("--workspace", default=os.getcwd())
    for name in ("graph", "claim", "bind", "resolve"):
        command = sub.add_parser(name)
        command.add_argument("plan")
        if name != "graph":
            command.add_argument("task")
        if name in {"claim", "bind"}:
            command.add_argument("--owner", required=True)
        if name == "bind":
            command.add_argument("--attempt", required=True, type=int)
    sub.add_parser("baseline")
    sub.add_parser("visible")
    batch = sub.add_parser("start-many")
    batch.add_argument("runs", nargs="+")
    batch.add_argument("--capacity", type=int, default=2)
    batch.add_argument("--plan")
    batch.add_argument("--bypass-caveman", action="store_true")
    summary = sub.add_parser("summary")
    summary.add_argument("runs", nargs="+")
    for name in ("brief", "report", "start", "prompt", "read-pane", "wait", "stop", "cleanup"):
        command = sub.add_parser(name)
        command.add_argument("run")
        if name == "report":
            command.add_argument("--full", action="store_true")
            command.add_argument("--receipt")
        if name == "start":
            command.add_argument("--pane")
            command.add_argument("--bypass-caveman", action="store_true")
    pane = sub.add_parser("pane")
    pane.add_argument("operation", choices=("layout", "split"))
    pane.add_argument("--pane", default="--current")
    pane.add_argument("--direction", choices=("right", "down"), default="right")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.action == "start-many":
        return start_many(args)
    if args.action == "summary":
        runs = list(dict.fromkeys(str(run_path(value)) for value in args.runs))
        summaries = [execution_summary(Path(run)) for run in runs]
        usage = {}
        for item in summaries:
            for key, value in item["usage"].items():
                usage[key] = usage.get(key, 0) + value
        intervals = [(item["started_at"], item["finished_at"]) for item in summaries
                     if "started_at" in item and "finished_at" in item]
        points = sorted([(start, 1) for start, end in intervals] + [(end, -1) for start, end in intervals])
        active = peak = 0
        for _, delta in points:
            active += delta
            peak = max(peak, active)
        print(json.dumps({"runs": summaries, "run_count": len(runs), "usage": usage,
                          "peak_concurrency": peak if len(intervals) == len(runs) else None,
                          "finished": all(item.get("status") in {"completed", "failed", "interrupted"} for item in summaries)}))
        return 0
    if args.action in {"plan", "graph", "claim", "bind", "resolve"}:
        return graph_action(args)
    if args.action == "cleanup":
        run = run_path(args.run)
        if not any(artifact(run, name).is_file() for name in ("run.json", "plan.json")):
            raise ValueError("cleanup requires runtime run or plan metadata")
        shutil.rmtree(run)
        return 0
    if args.action == "instructions":
        folder = AGENTS / "skills" / f"orchestrator-{args.family}"
        if args.reference:
            print((folder / "references" / f"{args.reference}.md").read_text())
        else:
            print((folder / "references" / "tools.md").read_text())
            print((folder / "references" / "roles.md").read_text())
            for role in ROLES:
                if args.mode == "quick" and role in {"reviewer", "critic"}:
                    continue
                fields = role_settings(args.family, args.mode, role)
                print(json.dumps({"role": role, **{k: v for k, v in fields.items() if k != "body"}}))
        return 0
    if args.action == "baseline":
        status = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
        print(status.stdout.strip() or ("Baseline: clean" if status.returncode == 0 else "Baseline unavailable"))
        if status.stderr:
            print(status.stderr.strip(), file=sys.stderr)
        return status.returncode
    if args.action == "visible":
        available = visible_available()
        print("Herdr path available" if available else "Herdr path unavailable; use host path")
        return 0 if available else 1
    if args.action == "pane":
        if not visible_available():
            raise ValueError("Herdr is not hosting this session")
        cmd = ["herdr", "pane", args.operation, args.pane]
        if args.operation == "split":
            cmd += ["--direction", args.direction, "--cwd", os.getcwd(), "--no-focus"]
        return subprocess.call(cmd)
    if args.action == "new":
        fields = role_settings(args.family, args.mode, args.role)
        run = Path(tempfile.mkdtemp(prefix="orchestrator-"))
        artifact(run, "run.json").write_text(json.dumps({"family": args.family, "mode": args.mode,
            "role": args.role, "workspace": str(Path(args.workspace).resolve()),
            "name": f"{args.role}-{run.name.removeprefix('orchestrator-')}"}))
        print(json.dumps({"run": str(run), **{k: v for k, v in fields.items() if k != "body"}}))
        return 0
    run, meta, fields = load_run(args.run, args.action in {"brief", "start"})
    if args.action == "brief":
        # stdin carries literal text; no shell interpolation and no repository writes.
        brief = sys.stdin.read()
        with unstarted_run(run):
            if fields["kind"] == "codex":
                brief += ("\n\nExecution protocol: inspect each tool result's exit_code and session_id. "
                          "If exec_command returns a session_id without an exit_code, the command is still running; "
                          "use write_stdin to collect its completion and output before reporting. "
                          "Never discard a live session handle or describe a yielded command as empty output. "
                          "Return your report only after your tool executions have completed.\n")
            artifact(run, "prompt.md").write_text(fields["body"] + "\n\n" + brief)
        print(artifact(run, "prompt.md"))
    elif args.action == "report":
        events = execution_events(run)
        if args.receipt:
            receipts = [event["item"] for event in events if event.get("type") == "item.completed"
                        and event.get("item", {}).get("id") == args.receipt]
            if not receipts:
                raise ValueError("no completed execution receipt with that ID")
            for receipt in receipts:
                print(json.dumps(receipt))
            return 0
        for name in ("final.md", "stderr.log"):
            path = artifact(run, name)
            if path.exists():
                content = path.read_text()
                print(f"{name}:\n{content if args.full else content[:16000]}")
                if not args.full and len(content) > 16000:
                    print(f"[truncated; recover with report {run} --full]")
        if events:
            for event in events:
                if event.get("type") in {"thread.started", "turn.completed", "turn.failed", "error"}:
                    print(json.dumps(event))
                item = event.get("item") or {}
                if event.get("type") == "item.completed" and item.get("type") == "command_execution":
                    key = "verifier_command" if meta["role"] == "verifier" else "worker_command"
                    output = str(item.get("aggregated_output", ""))
                    print(json.dumps({"run": str(run), "role": meta["role"], key: item.get("command"), "exit_code": item.get("exit_code"),
                                      "receipt_id": item.get("id"), "output_truncated": not args.full and len(output) > 1000,
                                      "output": output if args.full else output[:1000]}))
        summary = execution_summary(run)
        print(json.dumps({"execution_summary": summary}))
        return 1 if summary["evidence_issues"] else 0
    elif args.action == "start":
        artifact(run, "prompt.md").resolve(strict=True)
        if fields["kind"] == "codex" and fields["model_source"] != "live Codex model/list":
            raise ValueError("Cannot verify the newest model from the live Codex catalog; dispatch stopped. Cached/profile metadata is available for inspection only.")
        if args.pane:
            if not visible_available():
                raise ValueError("Herdr is not hosting this session")
            pane = subprocess.run(["herdr", "pane", "get", args.pane], capture_output=True, text=True, check=True)
            info = json.loads(pane.stdout)["result"]["pane"]
            cwd = info.get("foreground_cwd") or info.get("cwd")
            if not cwd or Path(cwd).resolve() != Path(meta["workspace"]).resolve():
                raise ValueError("target Herdr pane is in a different workspace; create a pane in the assigned workspace")
            cmd = ["herdr", "agent", "start", meta["name"], "--kind", fields["kind"], "--pane", args.pane, "--"]
            if fields["kind"] == "claude":
                cmd += ["--model", fields["model"], "--effort", fields["effort"], "--permission-mode", "bypassPermissions",
                        "--tools", fields["tools"].replace(" ", "")]
            else:
                cmd += ["--model", fields["model"], "--config", f'model_reasoning_effort={fields["effort"]}',
                        "--config", f'sandbox_mode={fields["sandbox"]}', "-a", "never"]
            # A startup timeout may leave a registered agent awaiting user input.
            # Keep read/wait/stop available even when start does not return zero.
            meta["visible"] = True
            artifact(run, "run.json").write_text(json.dumps(meta))
            rc = subprocess.call(cmd, cwd=meta["workspace"])
            if rc == 0:
                print("Usage: unmeasured, herdr-hosted")
            return rc
        if fields["kind"] != "codex":
            raise ValueError("dispatch this Claude agent with Agent; --pane selects visible hosting")
        return execute_codex(run, meta, fields, args.bypass_caveman)
    elif args.action in {"prompt", "read-pane", "wait", "stop"}:
        if not meta.get("visible"):
            raise ValueError("run is not hosted in Herdr")
        if not visible_available():
            raise ValueError("Herdr is not hosting this session")
        if args.action == "prompt":
            report = "Reply with your report; do not write a file." if meta["role"] in READ_ONLY else f"Write your report to {run}/final.md and reply with that path."
            return subprocess.call(["herdr", "agent", "prompt", meta["name"], f"Read {run}/prompt.md and carry it out. {report}", "--wait", "--timeout", "1800000"])
        if args.action == "read-pane":
            return subprocess.call(["herdr", "agent", "read", meta["name"], "--source", "recent-unwrapped", "--lines", "300"])
        if args.action == "wait":
            return subprocess.call(["herdr", "agent", "wait", meta["name"], "--until", "idle", "--until", "done", "--timeout", "1800000"])
        return subprocess.call(["herdr", "agent", "send-keys", meta["name"], "ctrl+c"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
