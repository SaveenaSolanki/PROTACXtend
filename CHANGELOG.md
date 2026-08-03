# ProtacPilot Changelog

## 2026-07-06 — HMGB2 Linker Optimization Campaign

### Summary
Completed a systematic linker optimization for HMGB2-ICM-CRBN/pomalidomide PROTACs.
16 linker variants (PEG, alkyl-PEG, alkyl, semi-rigid; 8–30 Å) were designed and
geometrically screened against 3600 MegaDock poses.

### Key Findings
- **All linkers <17 Å extended length: 0% pass rate** — not a single viable orientation
- **Best linker (C14-PEG5, 27 Å): 30/3600 passes (0.8%)** — still marginal
- **Root cause identified:** ICM exit vectors point AWAY from CRBN (100°–105° angle)
- The ICM binding site is on the far side of HMGB2 from where CRBN can dock

### Deliverables
- `outputs/p4ward_evidence/linker_optimization/` — full pipeline with 5 P4ward run dirs
- `outputs/p4ward_evidence/LINKER_OPTIMIZATION_REPORT.md` — comprehensive report
- `outputs/p4ward_evidence/plot_linker_passrate.png` — pass rate vs length plot
- `outputs/p4ward_evidence/linker_optimization_pipeline.py` — full pipeline script
- P4ward running for C14-PEG5 (best candidate) in background

### Next Steps
1. Test Hoechst 33258 as alternative warhead (better docking score + favorable exit vector)
2. Test alternative ICM exit vector (OH29 instead of OH27)
3. Wait for P4ward C14-PEG5 results

## 2026-08-01 — Proper conda env + completed Packages layer
- Created **`protacpilot`** env (Python 3.11.15): all 17 previously-missing packages installed & verified
  (openbabel, datamol, mordred→mordredcommunity, padelpy, deepchem, molfeat, dgl, torchdrug→own env,
  fair-esm, mdtraj, prody, py3Dmol, nglview, catboost, mlflow, wandb, chemprop).
- Created **`torchdrug310`** env (Python 3.10.20 + torch 2.1.2+cu121 + torchdrug 0.2.1) — torchdrug
  hard-requires py<3.11; resolved setuptools<81, numpy<2, ninja-lexicographic-version patch via sitecustomize.
- Version pins that fixed dependency hell: torch 2.6.0+cu126 (dgl 2.5.0 graphbolt), transformers<5
  (deepchem HuggingFaceModel), huggingface-hub<1.0 (transformers), torchdata==0.9.0 (dgl datapipes),
  numpy>=2 (mdtraj), mordredcommunity (numpy-2 compatible descriptors).
- Completed the rest of the Packages layer: gradio, llama-index, qdrant-client, chromadb, duckdb,
  psycopg, redis, celery, prefect, snakemake, nextflow (bioconda). **Packages sheet now 43/43 ✅.**
- **24/24 project tests pass in the new env** (ternary_stage 7 + synglue_degradation 17).
- Docs: `PROTACPILOT_ENVS.md` + reproducible `scripts/setup_protacpilot_env.sh`.
- Updated `Agent_Toolkit.xlsx`: Packages sheet status column (43/43 installed), fixed stale
  "heuristic-only" degradation row (now trained SynGlue model), added env + new module rows to
  Implementation_Status.

## 2026-08-01 — Structured Learning Memory (agents learn across runs)
- **`synglue_agent/tools/learning_memory.py`** (590 lines): validated, structured learning DB.
  - Controlled vocab: ProblemType (14), Outcome, LearningSource (direct_synthesis | human_feedback),
    ValidationStatus (candidate→validated/rejected/superseded), KNOWN_FAILURE_REASONS (aligned with FailureClass).
  - Every learning: problem_type, approach, outcome, human_correction, failure_reason, confidence,
    source, validation, provenance (run_id, target, E3, tool_versions, decision_refs), reuse_count.
  - Validation: human confirmation OR independent reuse (≥2 runs) auto-validates.
  - Safe reuse gate: only VALIDATED + confidence ≥ 0.7 returned by validated search.
  - Outliers: entries whose outcome contradicts their (problem_type, approach) cluster majority → flagged.
  - Pattern extraction: success rates per approach, top failure reasons, top human corrections,
    deterministic why-statements; rendered to patterns.md.
  - Per-process **learnings.md** written to memory/learnings/runs/<run_id>/learnings.md.
- **`synglue_agent/agents/learning_integration.py`** (240 lines): persist_run_learnings (auto-distills
  decision_log on every run), advise_repair (reuses validated learnings incl. human corrections),
  record_human_feedback (auto-validated ground truth, conf≥0.85 to pass reuse gate),
  attach_learning_persistence_to_run decorator.
- Fixed pre-existing agentic_core bugs surfaced by integration tests:
  - conditional-edge maps now filtered to registered nodes (graph compiled with stubs only)
  - default stub agents populate all stage fields → skeleton graph runs 18 nodes, no recursion loop
  - evidence gate defensive against non-dict evidence values
- 28 new tests (22 memory + 6 integration); full suite 52 passed.

## 2026-08-02 — TODO execution: A1, A2, B5 (in progress)
- **A1 done**: `test_agentic_scenarios.py` — 6 automated tests for good path /
  out-of-domain / repair loop / budget exhaustion / degradation escalation /
  determinism. Fixed real bug: repair-budget exhaustion → infinite ternary
  self-loop (route_after_ternary returned "ternary_ensemble" mapped to a
  self-loop); now escalates to human_gate.
- **A2 done**: `agents/linker_stage.py` — linker-design stage with
  conformational-strain loop router (evidence gate → scan → strain_check →
  repair loop bounded by MAX_LINKER_RETRY → ranking / human gate), 9 tests.
  Fixed real bugs: linker_scanner `effective_length_A` was 0.0 for all
  curated linkers (loader looked for wrong CSV column; added
  `effective_length` key + SMILES-topological fallback); invalid hand-written
  full-PROTAC SMILES in build_full_PROTAC.py rebuilt via RDKit dummy-atom
  assembly (C51H59N5O13, MW 950.1, verified parses, zero dummies).
  Added HARD_ERROR to ReasonCode controlled vocabulary in state.py.
- **B5 started**: PROTAC-DB 3.0 downloaded (15,502 PROTACs; 2,275 with DC50;
  1,311 with DC50+Dmax) → data/benchmark/PROTAC-DB_3.0_protacs.xlsx.
  scripts/benchmark_degradation.py runs the SynGlue predictor (real GROVER
  embeddings, family-matched E3, constant-warhead inference design) on a
  stratified 64-molecule sample; metrics: Spearman/Kendall on log10 DC50,
  threshold hit rates, MAE, Dmax rank correlation.

## 2026-08-02 — B1 done: Chemprop D-MPNN trained on PROTAC-DB 3.0
- PROTAC-DB 3.0 (15,502 PROTACs; 2,275 with DC50) downloaded → data/benchmark/.
- Trained Chemprop D-MPNN (log10 DC50 regression, 1,698 rows, scaffold split
  80/10/10, 60 epochs): test RMSE 0.875, R2 0.517.
- Same 64-molecule held-out benchmark: **Spearman rho 0.758 (p<0.001)** vs
  SynGlue baseline 0.243; hit<100nM 76.6% (was 53%), hit<1000nM 93.8% (was 78%),
  MAE 0.64 log10 (was 1.21). Training on domain data is decisive.
- `tools/chemprop_degradation.py` wrapper (CLI-backed; chemprop 2.3.0 MPNN has
  no public predict API; `python -m chemprop.cli.main` silently no-ops → use the
  console script). 5 tests pass.
- Comparison report: outputs/benchmark/B1_CHEMPROP_COMPARISON.md.

## 2026-08-03 — Uncertainty-aware predictive layer + AD detection (priority 2)
- **applicability_domain.py** (rewritten from stub): Morgan nn-Tanimoto vs the
  1,698-molecule training set, cached fingerprints. Fixed real bug: numpy bool
  matmul (`B @ a`) does not AND-count → explicit logical ops. Verified: self-sim
  1.0, aspirin OOD, pomalidomide in-domain, ICM warhead correctly out_of_domain.
- **Chemprop 3-member ensemble + conformal-regression calibration** (cal set
  n=200 held out; retrained 1,498): **92.2% interval coverage vs 90% target**,
  Spearman ρ=0.783, MAE 0.61 log10. Measured: raw ensemble std is NOT
  calibrated (ρ=0.086 vs error); AD similarity is the strongest trust signal
  (far bin RMSE 0.88 vs near 0.50).
- **uncertainty_aware_prediction.py**: verdicts high/medium/low_confidence
  composed from AD + conformal interval; wires ensemble + conformal + AD.
- **degradation_node.py**: real agentic-graph degradation node using the
  validated layer; low-confidence (OOD) candidates → bounded repair → human.
- **state.py**: added DecisionLog.to_dict() to the shared foundation.
- Tests: 5 (coverage, OOD flagging, in-domain, AD math regression guard).
- Report: outputs/benchmark/UNCERTAINTY_CALIBRATION.md.

## 2026-08-03 — Capabilities 2,3,4,7,8,10 completed
- **B4 NSGA-II Pareto ranking** (`tools/pareto_ranking.py`): non-dominated
  sort + crowding distance on [logDC50, dmax_inv, admet, synthesis, ternary];
  7 tests. No weights in dominance — replaces single composite score.
- **adaptive_extras.py** (cap. 2,3,4,7): warhead + exit-vector bounded repair
  loops (MAX_SELECTION_RETRY → human gate); dynamic tool selection
  (evidence → P4ward vs geometric proxy vs blocked); parallel candidate
  evaluation (ThreadPool, order-preserving, failure-isolated); expensive-
  modelling human gate (pauses before P4ward hours). 15 tests.
- **B6 Ablation** (`scripts/ablation_agentic_vs_pipeline.py` + report):
  [A] trained layer beats heuristic ρ 0.42→0.78, hit 75%→92%;
  [B] repair loop rescues candidates a pipeline discards;
  [C] AD flags 8/8 OOD, 0/8 in-domain misflagged.

## 2026-08-03 — A6 LLM layer: Ollama + gpt-oss:20b (single-model multi-role)
- Ollama updated to 0.32.5 (user-space binary at ~/ollama-bin, server on
  port 11435; system 0.11.10 on 11434 lacks gpt-oss support). Pulling
  gpt-oss:20b (~14 GB, 128K ctx, tools+reasoning, Apache-2.0).
- **llm/schemas.py**: Pydantic schemas per role — EvidenceDecision (Route:
  search_more/design/human_review/terminate), DesignDecision, RepairDecision
  (RepairAction enum), CritiqueDecision, SupervisorDecision, ReportDecision.
  No free-text reasoning stored — only decision + codes + tools + refs +
  confidence + rejected alternatives.
- **llm/tool_registry.py**: ALLOWED_TOOLS (13) — model may select but never
  construct arbitrary names; validate_selected_tools raises on anything else;
  EXPENSIVE_TOOLS (run_p4ward, run_retrosynthesis) force human approval.
- **llm/roles.py**: one model, six roles via prompts (supervisor, evidence-
  assessment, design-strategy, critic, repair, report) — NOT six models.
- **llm/ollama_client.py**: structured_chat with format=schema, temperature 0,
  num_ctx default 16K (cap 32K); model routing gpt-oss:20b → qwen2.5:7b
  fallback; structured_chat_with_fallback never lets model outage break the
  graph.
- **llm/context.py**: evidence summarization (truncate lists, counts),
  compact state for LLM — never dump full ChEMBL records.
- **llm/decision_layer.py**: LLM-gated nodes with deterministic validators —
  invalid tools stripped, p4ward selection → human_review, bounded evidence-
  search loop (MAX_EVIDENCE_SEARCH_ROUNDS=2 → human gate).
- **llm/graph.py**: LangGraph wiring; **fixed StateGraph(dict) replace-vs-
  merge bug** (retry_counts needs Annotated[sum_counts] reducer).
- 13 tests (mocked LLM — no GPU needed); 85 total green.
- **Live verification with gpt-oss:20b**: model pulled (13 GB, 128K ctx),
  structured chat works (EvidenceDecision/RepairDecision/SupervisorDecision
  all parse; cold start 63s, then 2-5s). Learned: gpt-oss:20b is conservative
  on evidence sufficiency — flipped the wiring so the DETERMINISTIC gate is
  authoritative (it has the numbers); the LLM may only add missing-evidence
  flags/tools, never veto sufficiency without naming a blocker. Matches the
  "deterministic validators gate LLM" principle.
- Server: user-space ollama 0.32.5 on port 11435; model resident on RTX 5000
  (13 GB); num_ctx capped 16K per request (Ollama default would be 262K).

## 2026-08-03 — Provider-agnostic LLM layer (any API in backend + frontend)
- **llm/providers.py**: 6 providers (ollama, openai, openrouter, anthropic,
  google, openai_compatible) behind one Protocol; env-config (PROTACPILOT_LLM_*)
  with runtime override (set_runtime_config). Provider-agnostic chat_raw; the
  gateway owns validation.
- **llm/gateway.py**: structured_chat across providers — raw text → json_repair
  → Pydantic validation → 1 retry with JSON-only instruction → fallback.
  gateway_status()/switch_provider() power the API + frontend.
- **llm/json_repair.py**: fence/prose stripping, balanced-block extraction,
  trailing-comma + unterminated-string repair (fixed over-aggressive quote
  repair that corrupted valid JSON).
- **backend/llm_routes.py**: GET /llm/status, /llm/providers, /llm/models;
  POST /llm/switch, /llm/test, /llm/reset — wired into api_routes.get_app().
- **app/streamlit_app.py**: sidebar "LLM backend" widget (provider/model/
  base_url/key + Apply + Test).
- Verified LIVE: ollama/gpt-oss:20b through the gateway — supervisor
  (BRD4/VHL/protac), repair (alternate_linker), evidence decisions parse;
  /llm/test returns schema-valid decision; status health ok.
- 14 new tests (gateway + repair + provider registry + switch) — 99 total green.
- Docs: PROTACPILOT_LLM.md (switch any provider 3 ways).
