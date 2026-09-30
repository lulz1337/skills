---
minion_model: gpt-6-sol
minion_reasoning_effort: medium
reviewer_model: gpt-6-sol
reviewer_reasoning_effort: high
---

`/orchestrator-codex standard`, the default: the coding model on both sides,
the reviewer at higher effort.

`gpt-6-sol` is OpenAI's GPT-6 model "built to power complex coding and agentic
workflows" ($2 / $10 per 1M tokens). It defaults to `medium` reasoning effort
and supports `low`–`max`. Model card:
https://developers.openai.com/api/docs/models/gpt-6-sol (read 2026-09-23).
