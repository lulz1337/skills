# Diagram Design

An agent skill that creates branded diagrams as standalone HTML files with
inline SVG and CSS, following an opinionated editorial design system. It can
also export SVG/PNG and redraw existing `.drawio`, `.drawio.png`,
`.drawio.svg`, or Mermaid `.mmd` sources at a chosen size and detail.

It covers 27 visual types: architecture, IT current-state, flowchart,
sequence, state machine, ER/data model, timeline, swimlane, quadrant,
radar/spider, loop/flywheel, nested, tree, org chart, layer stack, Venn,
pyramid/funnel, bar, line, Gantt, scatter, high-level, process, medallion,
data flow, DP integration, and DP security matrix. On top of the types it
adds semantic patterns, callouts, accessible motion, and an optional
sketchy/hand-drawn style.

## Installation

Install with the skills CLI:

```bash
npx skills add lulz1337/skills --skill diagram-design
```

Or install it as a Claude Code plugin:

```
/plugin marketplace add lulz1337/skills
/plugin install diagram-design@skills
```

Or copy this folder into the skill directory of your agent harness.

## Usage

Ask your agent for a diagram and name the type when you have one in mind:

```
Draw an architecture diagram of our ingestion pipeline.
```

```
Redraw docs/flow.drawio as a flowchart, medium detail.
```

Before the first diagram in a new project, the skill checks whether the
style guide still has the default tokens and offers to onboard your brand:
from a website URL, a design-system folder, pasted tokens, or a saved client
profile. A `.diagram-design` marker file in the project root can pin a saved
profile so the question never comes up again.

## Structure

- `SKILL.md` — the skill entry point: type selection, the style-guide gate,
  and the generation workflow.
- `references/` — one file per diagram type plus shared primitives (icons,
  annotations, sketchy style, animation, export, brand onboarding,
  profiles). The agent loads only the files the current diagram needs.
- `assets/` — worked example outputs for every type, in light, dark, and
  full variants.
- `scripts/` — helpers for extracting draw.io and Mermaid sources and a
  self-check.

## License

MIT. Icon sets bundled in `references/primitive-icons.md` keep their own
licenses (Tabler Icons, Simple Icons, Devicon, log-z/logos); see the license
attribution section in that file.
