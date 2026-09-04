# Sprint 1 — Acceptance & Full Regression Evidence

Status: **ACCEPTED** · Implementation frozen at `e31314a`.

## Freeze boundary

- Freeze commit: `e31314a` (`feat: sprint 1 — provider manager, auth/model CLI,
  provider-aware doctor, frozen result schema, six-BRD4 smoke`)
- **No** scientific modules, benchmark logic, website changes, or refactors were
  added to the Sprint-1 branch after freeze.
- Result schema is frozen at **`1.0.0`**
  (`protacxtend/results/schema.py`, `SCHEMA_VERSION = "1.0.0"`) with stable
  fields: `schema_version, status, task_id, workflow, metadata, provider,
  model, summary, result, tools, artifacts, evidence, warnings, errors,
  provenance` (+ optional `confidence`, `uncertainty` only when a backend
  supplies them). `protacxtend/results/io.py` writes/reads `result.json` and
  renders a readable `human_summary` — users never need to open JSON by hand.

## Sprint-1 deliverables (final status)

| Deliverable | Status |
|---|---|
| Provider Manager (DeepSeek · Ollama · OpenAI · Anthropic · Gemini · OpenRouter · custom OpenAI-compatible) | PASS |
| `protacxtend auth login / status / logout` (keys never printed) | PASS |
| `protacxtend model list / set / status` | PASS |
| Provider-aware `/doctor` (provider, model, authentication, inference, structured-output/tool-call, READY/DEGRADED/NOT READY verdict) | PASS |
| Frozen result schema 1.0.0 + readable CLI presentation | PASS |
| Six-BRD4/VHL blinded smoke workflow (`case-study brd4-vhl`, potency hidden) | PASS |
| Full regression (baseline preserved) | PASS |

## Full regression evidence (recorded at freeze)

| Check | Result |
|---|---|
| Python test suite (`pytest tests`) | **153 passed · 0 failed** (baseline 144 preserved inside total; +9 focused Sprint-1 tests) |
| Node tests (`npm test`) | **40 passed · 0 failed** |
| TypeScript build (`npm run build`) | **clean** |
| CLI smoke — from repo | PASS (`/doctor` VERDICT, `/run brd4-vhl-case-study`) |
| CLI smoke — from /tmp | PASS (`/status`; CLI `auth login/status/logout`, `model list`, `case-study brd4-vhl`) |
| Provider tests (`tests/test_sprint1.py`) | **9 passed · 0 failed** (network-free) |
| Six-BRD4 workflow | PASS — blinded input, deterministic tools, result.json schema 1.0.0, measured=0 / missing=6, no ground truth |

Warnings during the Python run (6942) are pre-existing deprecation warnings
(NumPy shape deprecation in `tack_degradation.py`, one agentic-schema import
note) — informational only.

## Tags / branches

- Release tag: **`sprint-1`** → annotated at this commit (implementation `e31314a` + evidence).
- Development branch: **`sprint-2`** opened from this commit for the next sprint.
- Next sprint items are **not started** (per freeze: no Biomni/Co-Scientist
  benchmarking, no new scientific modules, no website work, no refactors).
