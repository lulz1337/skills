---
worker_model: gpt-6-luna
worker_reasoning_effort: medium
reviewer_model: gpt-6.1-sol
reviewer_reasoning_effort: high
model_selection: latest-in-tier
---

Use the newest account-visible model in each configured tier from Codex
model/list. The versioned IDs above are minimum versions, not pins.
Runtime output reports the resolved model and catalog source. Cached and fallback
metadata are for inspection only; dispatch requires a fresh live catalog and
stops when the newest eligible model cannot be verified.
