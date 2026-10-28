# skills

My portable agent skills. Each skill lives in its own folder under `skills/`
and has its own entry point. The orchestrator also uses the
[runtime bundle](orchestrator/). Open a skill's folder for its README with
installation steps, usage, and everything else it needs.

## Skills

- [**humanizer**](skills/humanizer/) — Rewrite prose so it is precise,
  readable, and naturally human. English output by default; Czech, Slovak,
  Polish, German, and Ukrainian on request. Detects and removes 33 common
  AI-writing patterns and applies a controlled-language and Zinsser writing
  standard.
- [**test-discipline**](skills/test-discipline/) — Stack-agnostic test
  hygiene and test-pyramid discipline for changed test files: `.spec`/`.test`,
  Go, Python, Java and similar runner conventions.
  Ends every activation with a severity-graded review that marks tests OK /
  FIX / DELETE and names the MISSING ones; ships a dependency-free checker
  script.
- [**diagram-design**](skills/diagram-design/) — Create branded diagrams as
  standalone HTML/SVG/PNG in 45 visual types, from architecture and
  flowcharts to Gantt and ER models. Onboards brand tokens from a website or
  design system and redraws draw.io, Mermaid and Excalidraw sources.
- [**animated-diagram**](skills/animated-diagram/) — Animate service requests,
  API calls, data pipelines and agent workflows as looping diagrams with
  markers on the connectors, in the diagram-design theme.
- [**write-prompt**](skills/write-prompt/) — Write, improve, or translate a
  prompt instead of doing the task. Adds only the repository context that
  changes execution, adapts to a named target model using its official
  documentation, and requires an independent reviewer with no inherited
  conversation history.
- [**video-proof**](skills/video-proof/) — Present completed features with a
  female English voice, small bottom subtitles, changed-field highlights, and
  visible clicks. Covers the complete user scenario, verifies the real build
  and final video, and keeps media out of Git.
- [**orchestrator**](skills/orchestrator/) — Run a task in one main agent loop:
  the main thread scopes, implements and verifies, and from fast up a Codex or
  Claude reviewer reviews the final diff. Replaces orchestrator-claude,
  orchestrator-codex and orchestrator-hybrid.

Install the orchestrator with `python3 orchestrator/install.py` from this
checkout. It also removes the three old orchestrators. See the
[runtime guide](orchestrator/README.md) for setup and verification.

## License

MIT — see [LICENSE](LICENSE).
