---
minion_model: gpt-6-luna
minion_reasoning_effort: medium
reviewer_model: gpt-6-luna
reviewer_reasoning_effort: medium
---

`/orchestrator-codex quick`: the cheapest pair, for work whose shape is settled
and whose review can be shallow, such as a one-line config change.

`gpt-6-luna` is OpenAI's "most efficient model for focused, high-volume tasks"
($0.1 / $0.5 per 1M tokens). It reviews here too: the GPT-6 family has no
terra tier (https://developers.openai.com/api/docs/models/gpt-6-terra returns
404, checked 2026-09-29), so luna fills the mini slot the retired
`gpt-5.6-terra` held. Model card:
https://developers.openai.com/api/docs/models/gpt-6-luna (read 2026-09-23).
