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

## 4. 8-system comparison (Task 8b) — running

See `outputs/benchmark/formal_benchmark_results.json` + the table below
(populated on completion). Systems share scientific tools; differ in
architecture components (repair/uncertainty/memory/context/LLM).

| System | ρ (DC50) | Enrichment | Synth-rate | Gates | Repairs | Runtime |
|---|---|---|---|---|---|---|
| fixed_pipeline | … | … | … | … | … | … |
| adaptive_deterministic | … | … | … | … | … | … |
| llm_planner_only | … | … | … | … | … | … |
| full_agentic | … | … | … | … | … | … |
| full_minus_memory | … | … | … | … | … | … |
| full_minus_repair | … | … | … | … | … | … |
| full_minus_uncertainty | … | … | … | … | … | … |
| full_minus_context | … | … | … | … | … | … |

## 5. Safety metrics (Task 6 — LLM role validation, live gpt-oss:20b)

| Metric | Value |
|---|---|
| Unsupported tool selection | 0 |
| Invalid SMILES modification | 0 |
| Numerical hallucination | 0 |
| Human-gate recall (unsafe) | 1.0 |
| Context overflow | 0 |
| Functional pass (supervisor/evidence/critic) | 100% each |

Genuine findings: repair role chose retry for OOD (deterministic layer
overrides → human gate); report role dropped a number (templates insert
numbers; LLM prose only). Both enforced by the deterministic architecture.

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
- ⏳ One state schema / one runtime entry: DONE (agents/runtime.py)
- ⏳ Persistent checkpointer / Dockerized services / queue: partial
