# Sprint 2B — Runner & Scoring Infrastructure Audit

Scope: infrastructure only. **No benchmark task was executed** (PROTACXtend,
Biomni, AI-Co-Scientist-compatible, base-LLM, DeepSeek Flash, Ollama).
Frozen cases/ground truth untouched.

| Area | Status |
|---|---|
| Freeze provenance (SHA-256 of 48 cases + 48 GT + manifest/protocol/blindness/rubric), FREEZE_MANIFEST.json, SPRINT2A_ACCEPTANCE.md, fail-closed | READY |
| Provider-independent BenchmarkRunner + result envelope + raw preservation + run capture (provider/model/version, seed, temperature, timestamps, latency, tool calls, tokens, cost, status/errors, artifacts) | READY |
| Adapters/interfaces: PROTACXtend, Biomni, AI-Co-Scientist-compatible, base LLM, DeepSeek Flash, Ollama (+ DEV) | READY (all real adapters fail closed) |
| Deterministic scoring: exact, categorical, ranked (rank correlation + top-k) — never LLM-judged | READY |
| Rubric scoring: mechanistic/design schemas, 0–4 anchors, blind ids, randomized presentation, two reviewers, disagreement resolution, IRR | READY |
| Dev fixtures (perfect/partial/incorrect/hallucinated/missing/malformed/timeout/tool_failure) — no overlap with the 48 tasks | READY |
| Tests on dev fixtures only (parsing, scoring, retries, timeout, provenance, schema compliance, raw preservation, cost/token logging, expert-review export) | READY (17/17) |
| Real 48-task execution | NOT STARTED (by design) |

Not implemented yet (future sprint): live adapters for Biomni/AI-Co-Scientist
(no external services wired), production LLM providers, benchmark runs.
