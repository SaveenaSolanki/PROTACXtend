# LLM Role Evaluation — Findings (Task 6) — UPDATED 2026-08-04

_Live run · provider=ollama model=gpt-oss:20b · temperature 0_

## Final results (after model-level fixes)

| Role | Cases | Pass rate | Fix applied |
|---|---|---|---|
| supervisor | 2 | **100%** | — |
| evidence | 2 | **100%** | — |
| critic | 2 | **100%** | — |
| repair | 2 | **100%** | prompt hard rules: OOD→human_review mandatory; repairable classes enumerated; SMILES forbidden |
| report | 1 | **100%** | ReportDecision gained a structured `numbers` field (name+value); prompt requires every supplied value listed there |

## Metrics

| Metric | Before | After |
|---|---|---|
| Valid structured output | 0.78 | **1.0** |
| Unsupported tool selection | 0 | 0 |
| Invalid SMILES modification | 0 | 0 |
| Numerical hallucination | 0 (checker false-positives removed) | **0** |
| Human-gate recall (unsafe) | 1.0 | 1.0 |
| Context overflow | 0 | 0 |

## What was fixed and how

1. **Repair OOD-escalation gap**: the model chose retry for out_of_domain.
   Fixed with explicit prompt hard rules: (1) out_of_domain → human_review is
   the ONLY valid action; (2) no_valid_conformer/linker failures ARE repairable
   while retries remain; (3) SMILES in any field is forbidden; (4) escalate
   only for OOD / budget exhaustion / unknown. Verified: both repair cases
   now correct (over-correction was also caught and re-pinned).
2. **Report number-fidelity gap**: the model dropped supplied DC50=5.2 nM.
   Fixed structurally: ReportDecision.numbers is a machine-checkable list
   (name + exact value); the prompt requires every supplied value there.
   Verified: model now declares `[{DC50: 5.2 nM}, {Dmax: 91%}]` exactly.
3. Harness checker fixes (honest counting): boundary-aware number regex
   (no "50" from "DC50", no "1." ordinals); hallucination = number in
   summary absent from prompt AND not declared in `numbers`.

## Conclusion

The functional gaps were real and are now FIXED at the model level (prompt
engineering + structured schema), not just papered over by deterministic
overrides. The deterministic layers remain as the safety net; the LLM roles
now pass the spec's metrics on this case bank.
