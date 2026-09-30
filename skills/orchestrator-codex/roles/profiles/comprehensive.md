---
minion_model: gpt-6-sol
minion_reasoning_effort: medium
reviewer_model: gpt-6-astra
reviewer_reasoning_effort: medium
---

`/orchestrator-codex comprehensive`: the flagship reviews, for work where a
missed defect is expensive.

`gpt-6-sol` ($2 / $10 per 1M tokens) executes at `medium`; `gpt-6-astra`, the
GPT-6 flagship ($10 / $50), reviews at its default `medium`. `gpt-6-astra`
rejects `none`. Model cards:
https://developers.openai.com/api/docs/models/gpt-6-sol and
https://developers.openai.com/api/docs/models/gpt-6-astra (read 2026-09-23).
