# Baselines

Benchmark systems, defined once, used consistently across all 48 tasks
(where the task's `systems` list permits).

## Systems

| system id | description | notes |
|---|---|---|
| `PROTACXtend` | Candidate: PROTACXtend agent graph + tools under evaluation | Tools = permitted tools only |
| `Biomni` | External scientific-agent workflow | Run only when licensed/available; record version |
| `AI-Co-Scientist-compatible` | Hypothesis-generation/co-scientist style workflow (no external dependency needed for spec) | Compatible prompt/workflow shape, not a live external service |
| `Base-LLM-control` | Same model/provider as the candidate where technically possible | Isolates the *agent/tool* contribution from the *model* |
| `DeepSeek-Flash-control` | DeepSeek flash-class model control | Isolates model choice |
| `Local-Ollama-control` | Local Ollama control where appropriate | Offline runs, same host constraints |

## Control pairing policy

1. Every PROTACXtend task run should be paired with `Base-LLM-control` using
   the same provider/model/seed/temperature where technically possible.
2. `DeepSeek-Flash-control` and `Local-Ollama-control` are run on a
   representative subset (every capability × ≥3 tasks) to bound model-effect.
3. When a candidate uses tools, the base control receives the same
   permitted-tool list but no agent orchestration, isolating orchestration
   value.

## Reporting identity

Each run records in the result envelope:

`system`, `provider`, `model`, `provider_model_version`, `seed`, `repeat`,
`tool_calls`, `tokens_in/out`, `api_cost_usd`, `runtime_s`.

## Fair cost accounting

- Token/API cost recorded from provider usage when available; otherwise
  estimated from `tokens` × published per-1k rates at run time and labelled
  `estimated`.
- Local runs record wall time and hardware (host) fingerprint, cost = 0
  unless energy accounting is enabled.
- No system receives extra inference budget beyond the task's locked budget.

## Holdout

Ground truth and expected answers are never supplied to any baseline before
scoring; baselines are subject to `BLINDNESS_RULES.md` identically to
candidate systems.
