# Write Prompt

An agent skill that writes the prompt instead of doing the task. Give it a
request and it returns one ready-to-copy prompt, adapted to the target model
and checked by a reviewer that never saw the drafting conversation.

It runs only when you invoke it. It never fires on its own, because "write a
prompt for X" and "do X" are one word apart.

## Installation

Install with the skills CLI:

```bash
npx skills add lulz1337/skills --skill write-prompt
```

Or install it as a Claude Code plugin:

```
/plugin marketplace add lulz1337/skills
/plugin install write-prompt@skills
```

Or copy this folder into the skill directory of your agent harness.

## Usage

Invoke the skill explicitly and describe what the prompt must achieve:

```
$write-prompt a prompt for Codex that migrates our auth middleware to the new session API
```

```
$write-prompt přelož tenhle prompt do angličtiny pro Gemini 2.5 Pro
```

Name a target agent or model when you have one. The skill treats the
application and the model as separate facts and never substitutes a version
you did not ask for.

## What it does

1. **Scopes the context.** It decides whether the task actually concerns the
   current repository. The working directory alone is not evidence. A
   repository task gets verified paths, domain terms, and real constraints; an
   unrelated task gets no local paths at all.
2. **Adapts to the target.** A named model routes to its official
   documentation. No model named means the general baseline and no wasted
   documentation fetches.
3. **Drafts the smallest sufficient prompt.** No mandatory skeleton, no word
   count, no decorative role-play. Sections earn their place by changing
   execution.
4. **Requires an independent review.** A fresh reviewer with no inherited
   history checks the candidate as an artifact. If that reviewer cannot be
   spawned, the skill says so instead of quietly self-reviewing.

## Structure

- `SKILL.md` — the entry point: scoping, drafting, the mandatory review, and
  delivery rules.
- `models/claude.md`, `models/openai.md`, `models/gemini.md` — documentation
  routes for a named target. They are starting points to read, not cached
  claims about model behaviour.
- `models/general.md` — the baseline for an unnamed or unlisted model.

## License

MIT
