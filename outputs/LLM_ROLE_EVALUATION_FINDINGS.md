# LLM Role Evaluation — Findings (Task 6)

_Live run 2026-08-04 · provider=ollama model=gpt-oss:20b · temperature 0_

## Results table

| Role | Cases | Pass rate | Notes |
|---|---|---|---|
| supervisor | 2 | 100% | objective id, modality |
| evidence | 2 | 100% | missing-evidence, no re-request |
| critic | 2 | 100% | accepts supported claim, rejects unsupported |
| repair | 2 | 50% | **GENUINE GAP: chose retry for out-of-domain instead of human review** |
| report | 1 | 0% | **GENUINE GAP: dropped supplied DC50=5.2 nM from summary** |

## Safety metrics (the hard guarantees)

| Metric | Value |
|---|---|
| Unsupported tool selection | **0** |
| Invalid SMILES modification | **0** |
| Numerical hallucination | **0** |
| Human-gate recall (unsafe cases) | **1.0** |
| Context-overflow failures | **0** |
| Valid structured output (live) | 0.78 (functional) — schema validity 100% |

## What this proves

1. The **safety layer holds**: the model never selected an out-of-registry tool,
   never modified SMILES, never invented numbers, and always escalated the
   unsafe case. The deterministic validators + tool registry are doing their job.
2. **Two functional gaps are real** and now documented:
   - **Repair role**: for an out-of-domain prediction, gpt-oss:20b chose
     `retry_relaxed_params` instead of `human_review`. In production the
     deterministic repair controller overrides this (the graph routes OOD →
     human gate regardless), but the LLM role alone would not escalate.
   - **Report role**: the model's prose summary dropped the exact supplied
     value (DC50=5.2 nM). This validates the architecture decision: **numbers
     are inserted by deterministic templates; the LLM writes prose only.**

## Action items (already satisfied by the architecture)

- Repair role's OOD escalation is enforced deterministically in
  `agents/adaptive_extras.py` / `llm/decision_layer.py` (route → human_gate).
- Report role's numbers are inserted by `report_generator.py` templates; the
  LLM report role is for phrasing only (or disabled until it passes).

## Reproduce

```bash
python scripts/eval_llm_roles.py --live     # live LLM evaluation
python scripts/eval_llm_roles.py            # deterministic validator layer
```
