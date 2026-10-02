# skills

My portable agent skills. Each skill lives in its own folder under `skills/`
and has its own entry point. The three orchestrators share the
[runtime bundle](orchestrator/). Open a skill's folder for its README with
installation steps, usage, and everything else it needs.

## Skills

- [**humanizer**](skills/humanizer/) — Rewrite prose so it is precise,
  readable, and naturally human. English output by default; Czech, Slovak,
  Polish, German, and Ukrainian on request. Detects and removes 33 common
  AI-writing patterns and applies a controlled-language and Zinsser writing
  standard.
- [**test-discipline**](skills/test-discipline/) — Stack-agnostic test
  hygiene and test-pyramid discipline for changed `.spec` and `.test` files.
  Ends every activation with a severity-graded review that marks tests OK /
  FIX / DELETE and names the MISSING ones; ships a dependency-free checker
  script.
- [**diagram-design**](skills/diagram-design/) — Create branded diagrams as
  standalone HTML/SVG/PNG in 39 visual types, from architecture and
  flowcharts to Gantt and ER models. Onboards brand tokens from a website or
  design system and redraws draw.io and Mermaid sources.
- [**write-prompt**](skills/write-prompt/) — Write, improve, or translate a
  prompt instead of doing the task. Adds only the repository context that
  changes execution, adapts to a named target model using its official
  documentation, and requires an independent reviewer with no inherited
  conversation history.
- [**video-proof**](skills/video-proof/) — Record a short agent-browser
  video that proves a finished fix or story works. Ties the recording to the
  current worktree and build, validates the file frame by frame, and keeps it
  out of Git.
- [**orchestrator-claude**](skills/orchestrator-claude/) — Coordinate Claude
  workers with ten specialist roles, four modes and persistent tool boundaries.
- [**orchestrator-codex**](skills/orchestrator-codex/) — Coordinate Codex workers
  with current family models, joined batches, ownership claims and execution
  receipts.
- [**orchestrator-hybrid**](skills/orchestrator-hybrid/) — Coordinate Codex
  execution with Claude review and independent judgment.

Install all three with `python3 orchestrator/install.py` from this checkout.
See the [shared runtime guide](orchestrator/README.md) for setup and verification.

## License

MIT — see [LICENSE](LICENSE).
