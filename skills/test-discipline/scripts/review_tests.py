#!/usr/bin/env python3
"""Heuristic test-hygiene reviewer for the test-discipline skill.

Dependency-free static pre-pass over test files in any language. Emits
findings with severity + rule ID + file:line and a provisional per-file
verdict (OK / FIX). It cannot see semantics (wrong layer, duplication,
missing tests) — the agent's review adds those. Findings marked "verify"
are suspicions to confirm, not convictions.

Usage:
    python3 review_tests.py <files-or-dirs>... [--e2e-pattern REGEX] [--json]

Exit codes: 2 = BLOCKER finding present, 1 = HIGH present, 0 = clean/lower.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "out", "coverage", "vendor",
    ".venv", "venv", "__pycache__", ".next", ".svelte-kit", "target",
}

TEST_NAME = re.compile(
    r"(\.test\.|\.spec\.|_test\.[a-z0-9]+$|^test_[^.]+\.[a-z0-9]+$|Test\.[a-z0-9]+$|_spec\.[a-z0-9]+$)", re.IGNORECASE
)

DEFAULT_E2E = r"(^|/|\.)(e2e|end2end|end-to-end|acceptance|journeys?)(/|\.|$)"

COMMENT = re.compile(r"^\s*(//|#(?!\[)|\*|/\*)")

SEVERITY_ORDER = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

# --- line-level checks -------------------------------------------------------
# (rule, severity, verify?, regex, message)
LINE_CHECKS = [
    (
        "TD10", "BLOCKER", False,
        re.compile(
            r"(spy\w*\s*\(\s*(console|logg?er)\b"
            r"|\b(caplog|capsys|assertLogs?|assertLogged|expectLogs?)\b"
            r"|(expect|assert|verify|should)\w*\W.*\b(console|logg?er|stdout|stderr)\b"
            r"|\b(console|logg?er)\b.*\b(toHaveBeenCalled|called_with|was_called|received)\b)",
            re.IGNORECASE,
        ),
        "asserts on log/console output — test behaviour, not logging "
        "(exempt only when the task names the log line as a contract)",
    ),
    (
        "TD31", "MEDIUM", True,
        re.compile(
            r"(\btime\.sleep\b|\bThread\.sleep\b|\busleep\s*\(|\bsleep\s*\(\s*\d"
            r"|waitForTimeout\s*\(|setTimeout\s*\([^)]*,\s*\d{3,}"
            r"|\bdelay\s*\(\s*\d{3,})", re.IGNORECASE
        ),
        "hardcoded sleep/timeout — await the event or control the clock",
    ),
    (
        "TD41", "HIGH", False,
        re.compile(r"(\.only\s*\(|\bf(it|describe|test)\s*\()"),
        "focused test committed — it silently disables the rest of the suite",
    ),
    (
        "TD41", "HIGH", True,
        re.compile(
            r"(\.(skip|todo|fixme)\s*\(|\bx(it|describe|test)\s*\("
            r"|@\w*[sS]kip\b|@Ignore\b|markTestSkipped|pytest\.mark\.skip)"
        ),
        "skipped/deferred test — a silenced alarm; resolve it or report it",
    ),
    (
        "TD12", "MEDIUM", True,
        re.compile(
            r"(toHaveBeenCalled(With|Times)?\b|assert_(called|awaited)"
            r"|\.received\s*\(|\bverify\s*\(\s*\w+\s*[,)])"
        ),
        "call-verification on a double — legitimate only at a real boundary "
        "(TD22); on an internal collaborator it mirrors the implementation",
    ),
    (
        "TD13", "MEDIUM", True,
        re.compile(r"(toMatch(Inline)?Snapshot|MatchesSnapshot|assert_snapshot)"),
        "snapshot — allowed only for data contracts, pure-function output, "
        "error messages, or generated code",
    ),
    (
        "TD23", "HIGH", True,
        re.compile(
            r"(querySelector(All)?\s*\(|getElementsBy\w+\s*\(|getElementById\s*\("
            r"|\bxpath\s*[=(]|locator\s*\(\s*['\"](//|\.[a-zA-Z]|#[a-zA-Z])"
            r"|dispatchEvent\s*\()"
        ),
        "UI reached through structure (CSS/XPath/DOM selector or synthetic "
        "event) — locate by role/label/visible text and interact through "
        "user actions; pure-logic unit tests are exempt",
    ),
]

INFRA = re.compile(
    r"((postgres(ql)?|mysql|mariadb|mongodb(\+srv)?|redis|amqp|kafka|nats"
    r"|mssql|jdbc:[a-z]+)://|localhost:\d+|127\.0\.0\.1|0\.0\.0\.0)"
)

E2E_DOUBLE = re.compile(
    r"(\bmock\w*\s*[(.]|\bstub\w*\s*[(.]|\bspy\w*\s*[(.]|\bintercept\s*\("
    r"|\.route\s*\(|\bmonkeypatch\b|\bpatch\s*\(|\bfake\w*\s*\()",
    re.IGNORECASE,
)

IMPORT_JS = re.compile(r"^\s*import\s+(type\s+)?\{([^}]*)\}\s*from\s*['\"]([^'\"]+)['\"]")
IMPORT_ANY_JS = re.compile(r"^\s*(import\b|const\s+\w+\s*=\s*require\s*\()")
PROJECT_SPECIFIER = re.compile(r"^(\.|/|@/|~/|#|\$|src/)")

TYPE_PREFIX = re.compile(r"([:<|&]\s*|\b(as|extends|implements|satisfies|keyof|infer)\s+)$")


def is_test_file(path: str) -> bool:
    name = os.path.basename(path)
    return name.endswith("_test.go") or bool(TEST_NAME.search(name))


def discover(targets):
    files = []
    def raise_walk_error(error):
        raise error

    for target in targets:
        if os.path.isfile(target):
            if not is_test_file(target):
                raise ValueError(f"target is not a recognized test file: {target}")
            files.append(target)
            continue
        if not os.path.isdir(target):
            raise FileNotFoundError(f"target does not exist: {target}")
        for root, dirs, names in os.walk(target, onerror=raise_walk_error):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in names:
                path = os.path.join(root, name)
                if is_test_file(path):
                    files.append(path)
    return sorted(set(files))


def strip_strings(line: str) -> str:
    """Blank string literals so tokens inside test names don't trigger checks
    that target code (kept for checks where literals are noise)."""
    return re.sub(r"(['\"`])(?:\\.|(?!\1).)*\1", "''", line)


def check_type_only_imports(path: str, lines) -> list:
    findings = []
    if not path.endswith((".ts", ".tsx", ".mts", ".cts")):
        return findings
    imports = []  # (lineno, [symbols], specifier)
    for i, line in enumerate(lines, 1):
        m = IMPORT_JS.match(line)
        if not m or m.group(1):  # already `import type`
            continue
        symbols = []
        for raw in m.group(2).split(","):
            raw = raw.strip()
            if not raw or raw.startswith("type "):
                continue
            symbols.append(re.sub(r"\s+as\s+\w+$", "", raw).strip())
        if symbols:
            imports.append((i, symbols, m.group(3)))
    if not imports:
        return findings
    code = [
        (i, line) for i, line in enumerate(lines, 1)
        if not IMPORT_ANY_JS.match(line) and not COMMENT.match(line)
    ]
    for lineno, symbols, spec in imports:
        type_only = []
        for sym in symbols:
            pattern = re.compile(r"\b" + re.escape(sym) + r"\b")
            usages = []
            for _, line in code:
                for m in pattern.finditer(line):
                    usages.append(line[: m.start()])
            if usages and all(TYPE_PREFIX.search(prefix or "") for prefix in usages):
                type_only.append(sym)
        if type_only:
            findings.append((
                "TD30", "MEDIUM", False, lineno,
                f"{', '.join(type_only)} from '{spec}' used only in type "
                f"positions — use `import type` so the test does not load "
                f"the module's runtime graph",
            ))
    return findings


def check_third_party_only(path: str, lines) -> list:
    if not path.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".mts")):
        return []
    specifiers = []
    for line in lines:
        m = re.match(r"^\s*import\b.*from\s*['\"]([^'\"]+)['\"]", line)
        if not m:
            m = re.match(r".*require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", line)
        if m:
            specifiers.append(m.group(1))
    if not specifiers:
        return []
    project = [s for s in specifiers if PROJECT_SPECIFIER.match(s)]
    if project:
        return []
    return [(
        "TD11", "HIGH", True, 1,
        "no project code imported — the test's subject may be a third-party "
        "dependency; a test that would pass identically in the dependency's "
        "own repo does not belong here (monorepo self-imports by package "
        "name are the known false positive)",
    )]


def review_file(path: str, e2e_re) -> dict:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        return {"file": path, "error": str(exc), "findings": [], "verdict": "ERROR"}

    normalized = path.replace(os.sep, "/")
    basename = os.path.basename(normalized).lower()
    layer_header = re.compile(r"^\s*(?://|#|/\*)\s*test-layer:\s*(load|contract|unit|integration)\b", re.I)
    explicit_layer = None
    for line in lines[:10]:
        match = layer_header.match(line)
        if match:
            explicit_layer = match.group(1).lower()
            break
    is_e2e = bool(e2e_re.search(normalized))
    # k6 workload entry points are commonly plain .js files; .test.mjs files
    # in the same tree are runner tests and retain ordinary test heuristics.
    is_runner_test = basename.endswith(".test.mjs")
    is_load = explicit_layer == "load" or (not is_runner_test and bool(
        re.search(r"(^|/)(load|loads|performance|perf|benchmark)(/|\.)|\bk6\b", normalized, re.I)
    ))
    is_contract = explicit_layer == "contract" or bool(re.search(r"(^|/)(contract|contracts|provider|consumer)(/|\.)", normalized, re.I))
    is_unit = explicit_layer == "unit" or bool(re.search(r"(^|/)(unit|units)(/|\.)", normalized, re.I))
    findings = []

    for i, line in enumerate(lines, 1):
        if COMMENT.match(line):
            continue
        for rule, severity, verify, pattern, message in LINE_CHECKS:
            if is_load and rule in {"TD21", "TD31", "TD32"}:
                continue
            if pattern.search(line):
                findings.append((rule, severity, verify, i, message))
        if is_e2e:
            if E2E_DOUBLE.search(strip_strings(line)):
                findings.append((
                    "TD20", "BLOCKER", True, i,
                    "double inside an e2e spec — unmock it or reclassify the "
                    "spec as integration",
                ))
        elif is_unit:
            if INFRA.search(line):
                findings.append((
                    "TD21", "MEDIUM", True, i,
                    "unit-labelled test appears to reach infrastructure; verify the layer and whether isolated infrastructure semantics are the subject",
                ))

    if path.lower().endswith("_test.go"):
        for i, line in enumerate(lines, 1):
            if re.search(r"\bt\.(?:Skip|Skipf|SkipNow)\s*\(", line):
                findings.append(("TD41", "HIGH", True, i, "skipped Go test; resolve or report the deferred behavior"))

    findings.extend(check_type_only_imports(path, lines))
    if not is_e2e and not is_load and not is_contract:
        # e2e specs legitimately import only the test framework and drive
        # the application from outside, so TD11 does not apply there.
        findings.extend(check_third_party_only(path, lines))

    findings.sort(key=lambda f: (SEVERITY_ORDER[f[1]], f[3]))
    return {
        "file": path,
        "layer": "e2e" if is_e2e else "load" if is_load else "contract" if is_contract else "unit-labelled" if is_unit else "unit/integration",
        "findings": [
            {"rule": r, "severity": s, "verify": v, "line": ln, "message": m}
            for r, s, v, ln, m in findings
        ],
        "verdict": "FIX" if findings else "OK",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", help="test files or directories")
    parser.add_argument("--e2e-pattern", default=DEFAULT_E2E,
                        help="regex classifying a path as e2e")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--allow-empty", action="store_true", help="allow an empty directory when coverage is intentionally optional")
    args = parser.parse_args()

    e2e_re = re.compile(args.e2e_pattern)
    try:
        files = discover(args.targets)
    except (OSError, ValueError) as exc:
        print(f"review_tests: {exc}", file=sys.stderr)
        return 2
    if not files:
        print("no test files found", file=sys.stderr)
        return 0 if args.allow_empty else 2

    results = [review_file(path, e2e_re) for path in files]
    errors = [result for result in results if result.get("error")]
    if errors:
        for result in errors:
            print(f"review_tests: {result['file']}: {result['error']}", file=sys.stderr)
        return 2
    worst = min(
        (SEVERITY_ORDER[f["severity"]] for r in results for f in r["findings"]),
        default=99,
    )

    if args.as_json:
        print(json.dumps({"results": results}, indent=2))
    else:
        for r in results:
            print(f"{r['verdict']:>3}  {r['file']}  [{r.get('layer', '?')}]")
            for f in r["findings"]:
                tag = " (verify)" if f["verify"] else ""
                print(f"     {f['severity']:<7} {f['rule']} L{f['line']}{tag}: {f['message']}")
        total = sum(len(r["findings"]) for r in results)
        print(f"\n{len(files)} file(s), {total} finding(s). "
              "Verdicts are provisional: DELETE/CREATE need the semantic review.")

    return 2 if worst == 0 else 1 if worst == 1 else 0


if __name__ == "__main__":
    sys.exit(main())
