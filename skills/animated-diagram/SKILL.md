---
name: animated-diagram
description: Create looping animated diagrams of service requests, API calls, data pipelines, and agent workflows, with small markers traveling along connectors. Use for animated flow explainers or comparisons like the Claude five-layers-versus-one-loop animation. Inherit the diagram-design theme. Use diagram-design for static diagrams.
---

# Animated Diagram

Create a complete, readable diagram with small markers that show where a request
goes next. Keep nodes, labels, and connectors still. Motion explains the order.
Default deliverable: one HTML file with inline SVG, CSS, and playback controls.

## Theme and scope

Resolve this skill directory, then its sibling `../diagram-design/`. In the
skills installation both live in the same skills directory, such as
`~/.agents/skills/` or `~/.claude/skills/`. Read its `references/style-guide.md` before drawing:
it owns the colors and typography. Read `references/primitives-core.md` for
connectors and node treatments, and the matching `references/type-*.md` when its
layout is useful.

The user chose the default diagram-design theme for this skill. Use the current
light tokens without a first-use customization question. Honor an explicit theme
or project profile instead; resolve `.diagram-design` markers using
`references/profiles.md`. Do not change diagram-design's files. If the dependency
is missing, report it instead of claiming the result inherits its theme.

This skill owns the motion contract below. diagram-design's optional motion
controller targets a different use case; its one-token limit and restrictions on
repeating semantic sequences do not apply here. Retain its static design rules.
Its `scripts/self_check.py` and motion verifier require its canonical controller
and do not validate this skill's controller. Use the browser checks below for
animated-diagram output.

## Build the story

1. Extract the cast and the ordered events from the user's description or code.
   State reversible assumptions and proceed. For real systems, verify call order,
   concurrency, retries, and response paths in the source. Mark conceptual examples
   as illustrative. Animation speed does not imply measured latency.
2. Choose one story per figure, normally 3–6 events and a 6–12 second loop with
   at least 10% idle time. Target at most 9 nodes and 12 connectors. Split larger
   stories into overview and detail. For comparisons, use two aligned panels with
   independent event schedules; match time scales only when the evidence supports it.
3. Draw the complete static figure first. Use short readable labels, numbered
   events, and explicit arrowheads. Match diagram-design's 4px grid, orthogonal
   routes, distinct attach points, label masks, and typography. Allow local
   horizontal scrolling on narrow screens instead of shrinking text.
4. Add markers along those exact routes on one shared clock. Use one accent hue;
   show response direction with arrows and words. A marker reaches its destination
   before the dependent event starts. Simultaneous markers mean actual concurrency.
   A repeated loop illustrates the same trace again, not retries or extra requests.

Start with the bundled working example, rendered using the live theme:

```sh
python3 <skill-dir>/scripts/start.py diagrams/request-flow.html
# Optional: --theme dark, --offline, --style-guide /path/to/resolved/style-guide.md
```

Then replace the example's nodes, paths, event text, accessibility description,
and keyframes together. Update the duration and each marker's percentages on the
shared clock; leave markers invisible outside their event windows. The template
is a request → API → agent → tool → result example, not a universal architecture.
Use the current theme's typography; preserve generic font fallbacks. `--offline`
omits the web font link, so installed fonts or system fallbacks determine metrics.

## Motion contract

- Keep the full semantic diagram visible before JavaScript and without motion.
  Only decorative markers and optional active outlines animate. Mark overlays
  `aria-hidden="true"`; keep every semantic label in the accessibility tree once.
- Use CSS transforms and opacity on a deterministic shared timeline. Fixed route
  coordinates belong to the authored SVG. Keep event timing proportional to path
  length unless a deliberately slower segment conveys a documented wait.
- Offer native Pause/Play and Replay buttons. Pause must freeze every marker at
  the same time; Replay resets all animations to zero. Pause when the page hides;
  resuming requires Play. Do not add global keyboard shortcuts.
- Reduced motion, printing, no JavaScript, and `?motion=static` show the complete
  figure with markers and controls hidden. React to preference changes during
  playback. Enable movement only after controls bind successfully.
- Preserve the template's `?time=SECONDS` paused capture mode for deterministic
  inspection. Keep one duration for all marker animations. Avoid flashing,
  pulsing backgrounds, layout shifts, and gratuitous glow.

## Verify and deliver

Open the output with the environment's browser tool. Inspect the beginning,
every arrival, a return trip, and the idle gap using exact `?time=` frames.
Check marker alignment, direction, label collisions, and the loop boundary.
Exercise Pause, Play, and Replay twice; check browser errors. Verify static,
reduced-motion, print, and no-JavaScript states, plus a narrow viewport. Pause
must stop movement and reduced motion must show every node and relationship.

Deliver a link to the HTML and a short explanation of its story, timing, and any
assumptions. A screenshot is a preview, not an animated deliverable. Keep HTML
unless the user requests another format. For GIF or MP4, capture deterministic
frames with the installed browser and encode them with an available encoder;
verify the exported duration, dimensions, and loop. GIF cannot preserve controls
or reduced-motion behavior. Never rename HTML or a static SVG to `.gif`.

Visual reference: [Claude comparison animation](https://assets.claude.com/a7cb2cf08bfcef461166310c0c55f28b72c33b0d.gif).
Its relevant features are stationary panels, quiet neutral surfaces, a restrained
accent, and small moving request markers. Reuse that motion language, not its
specific architecture claims.
