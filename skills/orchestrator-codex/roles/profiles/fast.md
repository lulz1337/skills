---
minion_model: gpt-6-luna
minion_reasoning_effort: medium
reviewer_model: gpt-6-sol
reviewer_reasoning_effort: high
---

`/orchestrator-codex fast`: a cheap minion checked by a stronger reviewer, for
a mechanical refactor or a focused test change.

`gpt-6-luna` ($0.1 / $0.5 per 1M tokens) executes; the GPT-6 family has no
terra tier, so luna is the mini model here. `gpt-6-sol` ($2 / $10) reviews at
`high`. Model cards:
https://developers.openai.com/api/docs/models/gpt-6-luna and
https://developers.openai.com/api/docs/models/gpt-6-sol (read 2026-09-23).
