# skills

Portable agent skills. Each skill is a folder with a `SKILL.md` that any
harness supporting skill-style Markdown instructions can load (Claude Code,
OpenCode, Codex, and others).

## Skills

- [**humanizer**](humanizer/) — Rewrite Czech and English prose so it is
  precise, readable, and naturally human. Detects and removes 33 common
  AI-writing patterns and applies a controlled-language and Zinsser writing
  standard.

## Installation

Install with the skills CLI:

```bash
npx skills add lulz1337/skills
```

Or install a skill as a Claude Code plugin:

```
/plugin marketplace add lulz1337/skills
/plugin install humanizer@skills
```

Or copy a skill folder into the skill directory of your agent harness.

## License

MIT — see [LICENSE](LICENSE).
