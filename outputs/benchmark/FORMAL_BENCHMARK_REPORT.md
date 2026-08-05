# Formal Benchmark — ProtacPilot agentic platform (Task 8)

_Consolidated 2026-08-04 · release/v0.3-agentic-core_

## 1. Retrospective benchmark (B5/B1) — the scientific core

64 held-out PROTAC-DB 3.0 molecules (CRBN/VHL, DC50 available, excluded from training):

| Layer | Spearman ρ (log10 DC50) | hit<100nM | hit<1000nM | MAE (log10) |
|---|---|---|---|---|
| Heuristic (pre-B1) | 0.420 | — | 75% | — |
| SynGlue transformer (OOD) | 0.243 | 53% | 78% | 1.21 |
| **Chemprop D-MPNN (trained)** | **0.758** | **77%** | **94%** | **0.64** |
| Chemprop ensemble + conformal | **0.783** | — | — | 0.61 |

Calibrated uncertainty: **92.2% conformal coverage** (target 90%). AD detection:
8/8 OOD flagged, 0/8 in-domain misflagged (ICM warhead correctly out_of_domain).

## 2. Per-layer ablation (B6) — where the agent value comes from

| Ablation | Result |
|---|---|
| Degradation layer: heuristic → trained | ρ 0.42 → 0.78 (+0.36), hit 75% → 92% |
| Graph: repair loop on vs off | repair rescues candidates a pipeline discards (strained→clean re-scan) |
| Uncertainty: AD flagging on vs off | OOD predictions never ranked as confident (8/8 flagged) |

## 3. End-to-end challenge (Task 8a) — three cases

| Case | DC50 (pred) | Class | Best E3 | Runtime |
|---|---|---|---|---|
| A: known potent PROTAC | 6.9 nM | active ✓ | CRBN | 21s |
| B: known weak degrader | 334.5 nM | inactive ✓ | CRBN | 19s |
| C: HMGB2-ICM (new design) | 6.1 nM | active (chem) | CRBN | 18s |

**Cross-layer finding (documented)**: the degradation model (chemistry-trained)
calls the ICM PROTAC potent, but the SE3-PROTACs ternary model (structure-trained)
scores it ~0 ("bad degrader") → the ternary ensemble verdict is **AMBIGUOUS →
human gate**. The system correctly refuses to fabricate consensus across
independent methods.

Full run records: `outputs/e2e_challenge/*.json` (request, node path, tool
calls, model outputs, uncertainty, E3 explanation, Pareto ranking, runtime, GPU).

## 4. 8-system comparison (Task 8b) — COMPLETED

Task: rank 16 known PROTAC-DB molecules (8 potent <100nM + 8 weak ≥500nM).
Same scientific tools; systems differ in architecture components.

| System | ρ (DC50) | Enrichment | Synth-rate | Gates | Repairs | Runtime (s) |
|---|---|---|---|---|---|---|
| fixed_pipeline | 0.479 | 0.750 | 0.929 | 0 | 0 | 0.4 |
| adaptive_deterministic | 0.785 | 0.875 | 0.929 | 0 | 0 | 249 |
| llm_planner_only | 0.785 | 0.875 | 0.929 | 0 | 0 | 254 |
| full_agentic | 0.785 | 0.875 | 0.929 | 0 | 0 | 258 |
| full_minus_memory | 0.785 | 0.875 | 0.929 | 0 | 0 | 256 |
| full_minus_repair | 0.785 | 0.875 | 0.929 | 0 | 0 | 248 |
| full_minus_uncertainty | 0.785 | 0.875 | 0.929 | 0 | 0 | 248 |
| full_minus_context | 0.785 | 0.875 | 0.929 | 0 | 0 | 249 |

### Interpretation (honest)

1. **The degradation layer dominates this ranking task.** All non-heuristic
   systems reach ρ=0.785 because they share the trained Chemprop layer
   (+0.31 vs the heuristic fixed pipeline, enrichment 0.75→0.875). This is
   the layer ablation reproduced at the system level.
2. **The architecture components do NOT change ρ on this task** — and that
   is the correct, honest result: the 16 benchmark molecules are all
   in-domain (no OOD cases → no uncertainty gates fire, no repairs trigger,
   no context vetoes). The components' value is demonstrated on the
   FAILURE-INJECTED and SAFETY scenarios (per-layer ablation B6: repair
   rescues discarded candidates; AD prevents OOD being ranked confident;
   E3-context vetoes low-expression biology), not on a clean in-domain
   ranking.
3. **LLM planner adds cost, not accuracy, here** (254s vs 249s adaptive) —
   consistent with the LLM role findings (functional gaps in repair/report);
   the deterministic gates carry the correctness.
4. **Takeaway**: the benchmark task must include OOD + failure-injected
   candidates to discriminate the agentic components. That is exactly the
   B6 per-layer ablation design, and the numbers are consistent.

## 5. Safety metrics (Task 6 — LLM role validation, live gpt-oss:20b)

| Metric | Value |
|---|---|
| Unsupported tool selection | 0 |
| Invalid SMILES modification | 0 |
| Numerical hallucination | 0 |
| Human-gate recall (unsafe) | 1.0 |
| Context overflow | 0 |
| Functional pass (supervisor/evidence/critic) | 100% each |

Genuine findings, now FIXED at the model level (2026-08-04):
repair role now escalates OOD → human_review (prompt hard rules) and report
role preserves every supplied number via a machine-checkable `numbers` field.
All 5 roles pass at 100% on the case bank; deterministic layers remain the
safety net.

## 6. Production checklist status

- ✅ Real retrosynthesis (AiZynthFinder USPTO policy + ZINC stock)
- ✅ Real ternary ensemble (P4ward + SE3-PROTACs weights + geometric proxy)
- ✅ DC50 + Dmax prediction (multi-target Chemprop)
- ✅ Cell-context-aware degradation (E3-expression gate)
- ✅ E3-context engine (data-derived CRBN-vs-VHL explanation)
- ✅ Calibrated uncertainty (conformal 92.2%) + applicability domain
- ✅ Pareto ranking (NSGA-II)
- ✅ Provenance on every claim (tool/version per result)
- ✅ Dynamic plan + evidence-aware tool selection + conditional routing
- ✅ Bounded repair loops + learning retrieval + human interrupts
- ✅ Safe deterministic fallback; no unrestricted code; no LLM molecular editing
- ✅ One state schema / one runtime entry (agents/runtime.py)
- ✅ Persistent checkpointer (PostgresSaver, cross-process interrupt/resume verified)
- ✅ Dockerized services (docker-compose: api/worker/postgres/redis/ollama)
- ✅ Job queue (redis/sqlite) + worker (deploy/p4ward_worker.py)
- ✅ Central logging/tracing (outputs/runs/<run_id>/trace.jsonl per run)
