# Test Discipline

An agent skill that enforces test hygiene and test-pyramid discipline in any
language, framework, or runner. Every activation ends with a severity-graded
**Test Review** (BLOCKER/HIGH/MEDIUM/LOW) that marks each test **OK / FIX /
DELETE** and names the tests that are **MISSING**.

The rules are stack-agnostic on purpose — they are about behaviour and cost,
never about a particular runner or library:

- never assert on logs; never test a third-party dependency
- e2e stays unmocked; integration/functional tests supply every input
  (fixtures, fakes, fixed clock) and never reach real infrastructure
- type-only needs use type-only imports so suites stay fast
- no sleeps, no snapshots of structure, no implementation mirrors
- a red test is information: fix the right side, never weaken the test

## Installation

Install with the skills CLI:

```bash
npx skills add lulz1337/skills --skill test-discipline
```

Or install it as a Claude Code plugin:

```
/plugin marketplace add lulz1337/skills
/plugin install test-discipline@skills
```

Or copy this folder into the skill directory of your agent harness.

## Usage

The skill triggers whenever tests are written, edited, moved, fixed,
reviewed, or discussed. You can also invoke it directly:

```
Review the test hygiene in src/checkout/
```

```
Napiš testy pro calculateDiscount
```

For guaranteed activation, wire your harness to remind the agent on test
context — for Claude Code, a `UserPromptSubmit` + `PostToolUse` hook that
injects a one-line reminder when the prompt mentions tests or a test file is
touched.

## Structure

- `SKILL.md` — the entry point: the mandatory review contract, severity
  model, report format, and workflow.
- `rules/` — one file per rule area, loaded as needed: `layers.md`
  (TD01–TD04), `scope.md` (TD10–TD14), `isolation.md` (TD20–TD22),
  `speed.md` (TD30–TD32), `failures.md` (TD40–TD41).
- `scripts/review_tests.py` — dependency-free heuristic checker: scans test
  files, emits findings with severity + rule ID + file:line, provisional
  per-file verdicts, `--json` output, and gate-friendly exit codes
  (2 = BLOCKER present, 1 = HIGH).

## License

MIT
