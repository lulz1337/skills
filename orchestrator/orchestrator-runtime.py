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
import stat
import subprocess
import sys
import tempfile
import time

AGENTS = Path(__file__).resolve().parent
FAMILIES = ("claude", "codex", "hybrid")
MODES = ("quick", "fast", "standard", "comprehensive")
ROLES = ("scout", "verifier", "runner", "researcher", "browser", "implementer",
         "reviewer", "oracle", "sage", "critic", "publisher")
READ_ONLY = {"scout", "researcher", "reviewer", "oracle", "sage", "critic"}
REFERENCES = ("procedure", "examples", "pitfalls", "herdr", "roles", "tools", "workflow", "enforcement", "scheduling")
MODEL_VERSION = re.compile(r"^gpt-(\d+(?:\.\d+)*)-(luna|terra|sol|astra)$")
# Minimum Sol version and effort of the hybrid reviewer and critic, in every reviewed mode.
HYBRID_REVIEWER = ("gpt-6.1-sol", "high")
MODEL_CATALOG = None
# Characters of final.md and stderr.log that a truncated report prints.
REPORT_LIMIT = 16000
# Characters at the end of stderr.log that `report --final` prints for a failed or flagged run.
STDERR_EXCERPT = 2000
# Characters of a receipt's command that `report --final` prints before it sets command_truncated.
COMMAND_LIMIT = 500


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
    receipts = {}
    mapped = []
    for event in events:
        mapped.append(event)
        message = event.get("message")
        content = message.get("content", []) if isinstance(message, dict) else []
        if event.get("type") in {"assistant", "user"} and isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if event["type"] == "assistant" and block.get("type") == "tool_use":
                    receipt_id = block.get("id")
                    if not receipt_id:
                        continue
                    inputs = block.get("input") or {}
                    receipt = {"id": receipt_id,
                               "type": "command_execution" if block.get("name") == "Bash" else block.get("name"),
                               "command": inputs.get("command", "") if block.get("name") == "Bash" else json.dumps(inputs, separators=(",", ":"))}
                    receipts[receipt_id] = receipt
                    mapped.append({"type": "item.started", "item": receipt})
                elif event["type"] == "user" and block.get("type") == "tool_result":
                    receipt = receipts.get(block.get("tool_use_id"))
                    if receipt is not None:
                        output = block.get("content", "")
                        if isinstance(output, list):
                            output = "\n".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in output)
                        mapped.append({"type": "item.completed", "item": {
                            **receipt, "aggregated_output": str(output), "is_error": bool(block.get("is_error"))}})
        if event.get("type") == "result":
            usage = event.get("usage") or {}
            cached = usage.get("cache_read_input_tokens", 0)
            written = usage.get("cache_creation_input_tokens", 0)
            mapped.append({"type": "turn.completed", "usage": {
                "input_tokens": usage.get("input_tokens", 0) + cached + written,
                "cached_input_tokens": cached, "cache_write_input_tokens": written,
                "output_tokens": usage.get("output_tokens", 0), "reasoning_output_tokens": 0}})
    return mapped


def execution_summary(run):
    events = execution_events(run)
    receipts = [event["item"] for event in events if event.get("type") == "item.completed"
                and (event.get("item", {}).get("type") in {"command_execution", "mcp_tool_call", "web_search", "file_change"}
                     or "is_error" in event.get("item", {}))]
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
    for event in events:
        if event.get("type") == "assistant" and isinstance(event.get("message"), dict):
            content = event["message"].get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use" and not block.get("id"):
                        issues.append("Malformed tool_use block lacks an ID: " + json.dumps(block))
        if event.get("type") == "result" and (event.get("is_error") or event.get("subtype") != "success"):
            issues.append(f"Claude result reports subtype={event.get('subtype')!r}, is_error={event.get('is_error')!r}")
    claude_started = {block.get("id") for event in events
                      if event.get("type") == "assistant" and isinstance(event.get("message"), dict)
                      and isinstance(event["message"].get("content"), list)
                      for block in event["message"]["content"]
                      if isinstance(block, dict) and block.get("type") == "tool_use"}
    completed = {event.get("item", {}).get("id") for event in events if event.get("type") == "item.completed"}
    pending = [event["item"].get("id") for event in events if event.get("type") == "item.started"
               and (event.get("item", {}).get("type") in {"command_execution", "mcp_tool_call", "web_search", "file_change"}
                    or event.get("item", {}).get("id") in claude_started)
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
        cited = re.findall(r"\b(?:item_[A-Za-z0-9_-]+|toolu_[A-Za-z0-9]+)\b", report.split("Receipts:", 1)[1].splitlines()[0])
        known = {item.get("id") for item in receipts}
        if set(cited) - known:
            issues.append("Report cites receipt IDs absent from completed execution events")
    meta = json.loads(artifact(run, "run.json").read_text())
    cost = {"total_cost_usd": event["total_cost_usd"] for event in events
            if event.get("type") == "result" and "total_cost_usd" in event}
    return {"run": str(run), "family": meta["family"], "role": meta["role"], **state, **cost, "usage": usage,
            "completed_receipts": len(receipts), "receipt_ids": [item.get("id") for item in receipts],
            "report_present": final.exists(), "pending_receipt_ids": pending, "evidence_issues": issues}


def receipt_record(run, role, event, full):
    """Project one completed tool receipt into the report's receipt line, or return None."""
    item = event.get("item") or {}
    if event.get("type") != "item.completed":
        return None
    if item.get("type") == "file_change":
        changes = item.get("changes")
        if (item.get("status") == "completed"
                and isinstance(item.get("id"), str) and item["id"]
                and isinstance(changes, list) and changes
                and all(
                    isinstance(change, dict)
                    and isinstance(change.get("path"), str)
                    and change["path"].strip()
                    and isinstance(change.get("kind"), str)
                    and change["kind"].strip()
                    for change in changes
                )):
            return {
                "run": str(run), "role": role,
                "receipt_id": item["id"], "status": item["status"],
                "file_changes": [
                    {"path": change["path"], "kind": change["kind"]}
                    for change in changes
                ],
            }
        return None
    if item.get("type") == "command_execution" or "is_error" in item:
        key = "verifier_command" if role == "verifier" else "worker_command"
        output = str(item.get("aggregated_output", ""))
        outcome = {"is_error": item["is_error"]} if "is_error" in item and "exit_code" not in item else {"exit_code": item.get("exit_code")}
        return {"run": str(run), "role": role, key: item.get("command"), **outcome,
                "receipt_id": item.get("id"), "output_truncated": not full and len(output) > 1000,
                "output": output if full else output[:1000]}
    return None


def final_report(run, role):
    """Print final.md, one receipt line per completed tool action and the execution summary.

    A receipt line is the default report's line without `output`; file changes
    carry paths and kinds only. A stderr.log tail is added only when the run
    failed, was interrupted or has evidence issues. `report --receipt <id>` and
    `report --full` recover the rest.
    """
    final = artifact(run, "final.md")
    if final.exists():
        content = final.read_text()
        print(f"final.md:\n{content[:REPORT_LIMIT]}")
        if len(content) > REPORT_LIMIT:
            print(f"[truncated; recover with report {run} --full]")
    for event in execution_events(run):
        record = receipt_record(run, role, event, full=False)
        if record is None:
            continue
        record.pop("output", None)
        key = "verifier_command" if "verifier_command" in record else "worker_command"
        if isinstance(record.get(key), str) and len(record[key]) > COMMAND_LIMIT:
            record[key] = record[key][:COMMAND_LIMIT]
            record["command_truncated"] = True
        print(json.dumps(record))
    summary = execution_summary(run)
    stderr = artifact(run, "stderr.log")
    if (summary.get("status") in {"failed", "interrupted"} or summary["evidence_issues"]) and stderr.exists():
        content = stderr.read_text()
        if content.strip():
            print(f"stderr.log (last {STDERR_EXCERPT} characters):\n{content[-STDERR_EXCERPT:]}")
            if len(content) > STDERR_EXCERPT:
                print(f"[truncated; recover with report {run} --full]")
    print(json.dumps({"execution_summary": summary}))
    return 1 if summary["evidence_issues"] else 0


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
            # Shared compress proxy runs with recovery on (run state: recovery_via_mcp=true).
            # Caveman 2.0.1's proxyRuntimeGateMatches refuses differing desired recovery_via_mcp;
            # pass-through (--off) always fell back to "launching this agent direct", unmetered.
            # Compress with Caveman's ephemeral recovery MCP matches the gate.
            cmd = ["caveman", "run", "--", *cmd]
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


def execute_claude(run, meta, fields):
    """Record a read-only Claude role's stream and final result under the run lock."""
    with unstarted_run(run):
        state = {"model": fields["model"], "started_at": time.time(), "status": "running"}
        artifact(run, "execution.json").write_text(json.dumps(state))
        print(json.dumps({"orchestrator_run": {**meta, **{k: v for k, v in fields.items() if k != "body"},
                                                "run": str(run)}}), flush=True)
        cmd = ["claude", "--print", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
               "--strict-mcp-config", "--permission-mode", "bypassPermissions", "--agent", fields["agent_type"],
               "--model", fields["model"], "--tools", fields["tools"].replace(" ", ""), "--effort", fields["effort"]]
        try:
            env = {key: value for key, value in os.environ.items() if not key.startswith("HERDR_")}
            with artifact(run, "prompt.md").open() as prompt, artifact(run, "events.jsonl").open("w") as events, artifact(run, "stderr.log").open("w") as errors:
                rc = subprocess.call(cmd, stdin=prompt, stdout=events, stderr=errors, cwd=meta["workspace"], env=env)
            for event in execution_events(run):
                if event.get("type") == "result":
                    artifact(run, "final.md").write_text(str(event.get("result", "")))
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
    kinds = {fields["kind"] for _, _, fields in runs}
    if len(kinds) != 1:
        raise ValueError("batch runs must share one kind; cannot mix " + " and ".join(sorted(kinds)))
    for run, meta, fields in runs:
        artifact(run, "prompt.md").resolve(strict=True)
        if fields["kind"] == "claude":
            if meta["role"] not in READ_ONLY:
                raise ValueError("dispatch this Claude agent with Agent; batch accepts only read-only Claude roles")
        elif fields["kind"] != "codex":
            raise ValueError("batch requires Codex roles with fresh live model settings")
        elif fields["model_source"] != "live Codex model/list":
            raise ValueError(catalog_dispatch_error(fields["model_source"]))
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
            rc = execute_claude(run, meta, fields) if fields["kind"] == "claude" else execute_codex(run, meta, fields, args.bypass_caveman)
            return {**execution_summary(run), "exit_code": rc}
        except Exception as error:
            return {"run": str(run), "exit_code": 1, "error": str(error)}
    with ThreadPoolExecutor(max_workers=args.capacity) as pool:
        results = list(pool.map(launch, runs))
    print(json.dumps({"batch_results": results}), flush=True)
    return 1 if any(result["exit_code"] != 0 or result.get("evidence_issues") for result in results) else 0


def catalog_dispatch_error(source):
    return ("Cannot verify the newest model from the live Codex catalog; dispatch stopped. "
            f"{source}. Cached/profile metadata is available for inspection only. "
            "If the reason mentions a read-only file system, no writable temp directory or a blocked network, the host session is sandboxed. "
            "Codex workers run as child codex processes and need a host with full access "
            "(no sandbox, network on); switch the host session to Full access "
            "(IDE: the permissions control beneath the composer; CLI: /permissions) and retry, "
            "instead of retrying in the same session.")


def available_models():
    """Read the account's live Codex catalog without starting an inference turn."""
    global MODEL_CATALOG
    if MODEL_CATALOG is not None:
        return MODEL_CATALOG
    errors = None
    try:
        try:
            errors = tempfile.TemporaryFile()
        except OSError:
            pass
        proc = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=errors if errors is not None else subprocess.DEVNULL)
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
                            code = proc.poll()
                            raise ValueError("codex app-server exited before a catalog response" +
                                             (f" (exit code {code})" if code is not None else ""))
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
            proc.stdout.close()
            proc.stdin.close()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        reason = str(error)
        if errors is not None:
            errors.seek(0)
            last_line = ""
            for line in errors:
                if line.strip():
                    last_line = line.decode("utf-8", errors="replace").strip()
            if last_line:
                reason += "; stderr: " + last_line
        else:
            reason += "; stderr not captured: no writable temp directory"
        reason = re.sub(r"[A-Za-z0-9_\-.]{32,}", "[redacted]", reason)
        reason = " ".join(reason.split())[:300]
        cache = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "models_cache.json"
        try:
            data = json.loads(cache.read_text())
            models = [{"model": m["slug"], "hidden": m.get("visibility") == "hide",
                       "supportedReasoningEfforts": [{"reasoningEffort": e["effort"]} for e in m.get("supported_reasoning_levels", [])]}
                      for m in data["models"]]
            MODEL_CATALOG = (models, "cached Codex catalog; live catalog unavailable: " + reason)
        except (OSError, ValueError, KeyError, TypeError):
            MODEL_CATALOG = ([], "profile fallback; latest model unverified: " + reason)
    finally:
        if errors is not None:
            errors.close()
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
        label = "profile fallback; latest available model unverified"
        if source == "live Codex model/list":
            return fallback, label
        elif source.startswith("profile fallback"):
            return fallback, source
        else:
            return fallback, label + ": " + source
    _, model, supported = max(candidates, key=lambda item: item[0])
    if supported and effort not in supported:
        raise ValueError(f"newest {match[2]} model {model} does not support configured effort {effort}")
    return model, source


def definition(path):
    _, front, body = path.read_text().split("---", 2)
    fields = dict(line.split(":", 1) for line in front.strip().splitlines() if ":" in line)
    return {key: value.strip() for key, value in fields.items()}, body.strip()


def role_settings(family, mode, role):
    if family == "codex" and role == "publisher":
        raise ValueError("publisher is a Claude role; the codex family cannot publish an Artifact")
    if mode == "quick" and role in {"reviewer", "critic"}:
        raise ValueError("quick has no review; choose fast, standard or comprehensive")
    # Hybrid: one frontier implements (Claude), the other confirms (Codex reviewer,
    # critic, verifier, oracle). Sage advises, runner executes closed command
    # lists on Opus, and publisher is Claude-only.
    kind = "claude" if family == "claude" or family == "hybrid" and role in {"implementer", "runner", "sage", "publisher"} else "codex"
    if kind == "claude":
        name = f"worker-{'hybrid-' if family == 'hybrid' else ''}{mode}" if role == "implementer" else f"reviewer-{mode}" if role == "reviewer" else f"orch-{role}-{mode}"
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
    if family == "hybrid" and role in {"reviewer", "critic"}:
        # Hybrid pairs a Claude implementer with Sol review and critique in every
        # mode; the profile's reviewer half belongs to the codex family.
        model, effort = HYBRID_REVIEWER
    model, source = latest_model(model, effort)
    # Read-only Codex sandboxes cannot write the verifier's normal build output.
    return {"kind": kind, "agent_type": name, "model": model, "effort": effort,
            "sandbox": fields["sandbox"], "body": body, "model_source": source}


def run_root():
    # Claude Code's sandbox TMPDIR is join(CLAUDE_CODE_TMPDIR or the system temp dir, claude-<uid>),
    # and the sandbox mounts that base read-only; the hook runs with TMPDIR unset, so both views
    # must land on that same per-uid directory.
    temp = Path(os.environ.get("CLAUDE_CODE_TMPDIR") or tempfile.gettempdir()).resolve()
    name = f"claude-{os.getuid()}"
    return temp if temp.name == name else temp / name


def ensure_run_root():
    root = run_root()
    # Outside the sandbox nothing has created the root yet, and in a shared temp dir another user could.
    try:
        root.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError(f"run root {root} must be a directory owned by uid {os.getuid()} "
                         "that is not group- or other-writable")
    return root


def run_path(value):
    path = Path(value).resolve(strict=True)
    temp = run_root()
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
    blockers = [name for name in task["blocked_by"] if plan["tasks"][name]["status"] not in {"implemented", "done"}]
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
        run = Path(tempfile.mkdtemp(prefix="orchestrator-plan-", dir=ensure_run_root()))
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
            if not isinstance(result, dict) or result.get("status") not in {"implemented", "done", "blocked", "pending"}:
                raise ValueError("resolution status must be implemented, done, blocked or pending")
            nonempty(result.get("evidence"), "resolution evidence")
            if result.get("owner") != task["owner"] or type(result.get("attempt")) is not int or result["attempt"] != task["attempt"]:
                raise ValueError(f"resolution must match current owner {task['owner']} and attempt {task['attempt']}")
            if result["status"] == "pending":
                if task["status"] not in {"running", "blocked", "implemented"} or result.get("stopped") is not True:
                    raise ValueError("retry requires an interrupted/blocked task and confirmation that its owner stopped")
                task["owner"] = None
            else:
                allowed = {"running"}
                if result["status"] in {"done", "blocked"}:
                    allowed.add("implemented")
                if task["status"] not in allowed:
                    raise ValueError("only a claimed task can be resolved")
                if result["status"] == "done":
                    # Legacy plans may complete each slice as they go. Once a
                    # plan uses task-wide verification, however, every writer
                    # must hand off before any task can become verified done.
                    implementations = [
                        other for other in plan["tasks"].values()
                        if other.get("role", "implementer") == "implementer"
                    ]
                    if any(other["status"] == "implemented" for other in implementations) and any(
                        other["status"] in {"pending", "running", "blocked"}
                        for other in implementations
                    ):
                        raise ValueError("task-wide verification requires every implementation to be handed off first")
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
            command.add_argument("--final", action="store_true",
                                 help="print only final.md and the execution summary")
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
                if args.family == "codex" and role == "publisher":
                    continue
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
        run = Path(tempfile.mkdtemp(prefix="orchestrator-", dir=ensure_run_root()))
        artifact(run, "run.json").write_text(json.dumps({"family": args.family, "mode": args.mode,
            "role": args.role, "kind": fields["kind"], "workspace": str(Path(args.workspace).resolve()),
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
            artifact(run, "prompt.md").write_text(brief if fields["kind"] == "claude" else fields["body"] + "\n\n" + brief)
        print(artifact(run, "prompt.md"))
    elif args.action == "report":
        if args.final:
            if args.full or args.receipt:
                raise ValueError("report --final excludes --full and --receipt")
            return final_report(run, meta["role"])
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
                print(f"{name}:\n{content if args.full else content[:REPORT_LIMIT]}")
                if not args.full and len(content) > REPORT_LIMIT:
                    print(f"[truncated; recover with report {run} --full]")
        if events:
            for event in events:
                if event.get("type") in {"thread.started", "turn.completed", "turn.failed", "error"}:
                    print(json.dumps(event))
                record = receipt_record(run, meta["role"], event, args.full)
                if record is not None:
                    print(json.dumps(record))
        summary = execution_summary(run)
        print(json.dumps({"execution_summary": summary}))
        return 1 if summary["evidence_issues"] else 0
    elif args.action == "start":
        artifact(run, "prompt.md").resolve(strict=True)
        if fields["kind"] == "codex" and fields["model_source"] != "live Codex model/list":
            raise ValueError(catalog_dispatch_error(fields["model_source"]))
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
            if fields["kind"] == "claude" and meta["role"] in READ_ONLY:
                return execute_claude(run, meta, fields)
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
