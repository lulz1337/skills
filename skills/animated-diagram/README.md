# Animated Diagram

An agent skill that draws looping animated diagrams: service requests, API
calls, data pipelines and agent workflows, with small markers that travel along
the connectors on one shared clock. The result is one HTML file with inline
SVG, CSS and playback controls.

It reuses the [diagram-design](../diagram-design/) theme for colors, typography
and connector rules, and adds its own motion contract: 3–6 events per story, a
6–12 second loop, markers that follow the drawn routes, and reduced-motion
support.

## Installation

Install it together with diagram-design, so both land in the same skills
directory:

```bash
npx skills add lulz1337/skills --skill animated-diagram --skill diagram-design
```

Or install both as Claude Code plugins:

```
/plugin marketplace add lulz1337/skills
/plugin install diagram-design@skills
/plugin install animated-diagram@skills
```

As plugins the two skills live in separate folders. Pass diagram-design's
style guide to the starter script with `--style-guide`, or the skill reports
the dependency as missing instead of claiming the theme.

## Usage

```
/animated-diagram animate a checkout request through the API, the payment provider and the queue
```

The starter renders a working example with the live theme tokens:

```bash
python3 scripts/start.py diagrams/request-flow.html --theme dark
```

## Structure

- `SKILL.md` — theme resolution, the story rules, the motion contract and the
  browser checks.
- `assets/template.html` — the working example the starter fills.
- `scripts/start.py` — renders the starter from diagram-design's style guide.

## License

MIT
