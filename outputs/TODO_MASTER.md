# ProtacPilot — Master TODO List

Status: ✅ done · 🔄 in progress · ⬜ pending · ⚠️ partial/blocked
Updated: 2026-08-01

---

## A. Agentic architecture (v0.2 → v0.3)

- [x] **A1. Automate the 3 agentic scenario tests** — ✅ 6 tests in `test_agentic_scenarios.py` (good path, determinism, out-of-domain, repair loop, budget exhaustion, degradation escalation). **Fixed real bug**: repair-budget exhaustion caused infinite ternary self-loop → now escalates to human_gate.
- [x] **A2. Port ternary-stage pattern → linker-design stage** — ✅ `linker_stage.py` (strain-loop router: evidence gate → generation → strain_check → repair loop → ranking / human gate), 9 tests. **Fixed real bugs in linker_scanner**: `effective_length_A` was 0 for all curated linkers (wrong CSV column key + SMILES-length fallback added); the hand-written full-PROTAC SMILES in `build_full_PROTAC.py` was invalid (rebuilt via RDKit dummy-atom assembly, verified parses). Added `HARD_ERROR` to ReasonCode vocab.
- [ ] **A3. FailureClass-aware retry in v0.1 path** — `classify_failure` + `FAILURE_RESPONSES` currently only in `agentic_core.py`; toolbox retry still boolean
- [ ] **A4. `agentic_mode=false` regression test** — prove v0.1 pipeline unchanged with the flag off
- [ ] **A5. Persistent checkpointer + resume path** — MemorySaver exists in `compile_ternary_graph()` only
- [x] **A6. Step 7: LLM layer** — ✅ DONE (2026-08-03): Ollama 0.32.5 + **gpt-oss:20b** (13 GB, 128K ctx, pulled + live). One model, six roles via prompts + Pydantic schemas (llm/schemas.py, roles.py). Strict tool registry (13 tools, never arbitrary names). Structured outputs (format=schema, temp 0), num_ctx 16K. Deterministic gate is authoritative; LLM adds flags/tools only. 13 tests (mocked). Live: supervisor/repair/evidence decisions parse correctly.

## B. Prediction layer (v0.4)

- [x] **B1. Chemprop D-MPNN degradation model on PROTAC-DB 3.0** — ✅ DONE (2026-08-02): trained on 1,698 PROTAC-DB rows (log10 DC50, scaffold split R²=0.52). **Beats baseline 3×: Spearman ρ=0.758 vs 0.243 on same 64 held-out molecules; hit<1000nM 93.8% vs 78%; MAE 0.64 vs 1.21**. Wrapper `tools/chemprop_degradation.py` (5 tests). Report: `outputs/benchmark/B1_CHEMPROP_COMPARISON.md`. Next: Dmax head + ensemble.
- [x] **Cap. 2/3/4/7 adaptive graph** — ✅ DONE (2026-08-03): warhead/exit-vector repair loops, dynamic tool selection, parallel evaluation, expensive-modelling gate (`agents/adaptive_extras.py`, 15 tests)
- [ ] **B2. Retrosynthesis integration** — `retrosynthesis_filter.py` is a 17-line threshold stub; wire AiZynthFinder/RAscore
- [ ] **B3. Ternary ensemble (DeepTernary/PRosettaC/HADDOCK)** — `ternary_ensemble` node uses perturbed-proxy simulation, not real predictors
- [x] **B4. NSGA-II Pareto ranking** — ✅ DONE (2026-08-03): `tools/pareto_ranking.py` non-dominated sort + crowding distance on 5 objectives; 7 tests. Replaces single weighted composite.
- [x] **B5. Retrospective benchmark** — ✅ DONE (2026-08-02): PROTAC-DB 3.0 downloaded (15,502 PROTACs; 2,275 with DC50) → `data/benchmark/`; `scripts/benchmark_degradation.py` ran SynGlue predictor on stratified n=64 with real GROVER embeddings. **Result: Spearman ρ=0.243 (p=0.053) on log10 DC50, 78% hit-rate at 1000 nM, systematic DC50 overestimate (median 173 vs 22 nM)**. Baseline established — any improved model must beat this on the same set. Report: `outputs/benchmark/benchmark_report.md` + predictions CSV + metrics JSON.
- [x] **B6. Ablation study** — ✅ DONE (2026-08-03): [A] trained layer ρ 0.42→0.78, hit 75%→92%; [B] repair loop rescues discarded candidates; [C] AD flags 8/8 OOD. Report: `outputs/benchmark/ABLATION_REPORT.md`
- [ ] **B7. Lysine proximity scorer** (NP#5)
- [ ] **B8. Hook effect modeler** (NP#7)
- [ ] **B9. Cooperativity (α) predictor** (NP#4)
- [ ] **B10. Novel E3 ligand discovery** (NP#2, 4/600 bottleneck)
- [ ] **B11. Proteotype selectivity model** (NP#9)
- [ ] **B12. Active learning loop** (NP#11)

## C. Infrastructure / debt cleanup

- [ ] **C1. Delete or wire `agentic/` scaffold** (12 files, 883 lines) — superseded by `agents/agentic_core.py`; still referenced by `orchestration.py`, `perception.py`
- [x] **C2. Unify degradation paths** — ✅ DONE (2026-08-03): validated Chemprop ensemble + conformal calibration + AD is now the pipeline degradation layer (`agents/degradation_node.py` + `tools/uncertainty_aware_prediction.py`); heuristic remains only as fallback in the old v0.1 path
- [ ] **C3. Unify memory schemas** — old `DesignMemoryRecord` vs new `LearningEntry`; `memory_manager.py` stub
- [ ] **C4. Plumb `agentic_mode` through `mode_router.py`** — currently routes only to v0.1 `run_syn_glue_workflow`
- [ ] **C5. Wire vector memory (RAG)** — `literature_rag.py` (144 lines) orphaned; qdrant/chroma installed but unused by agents
- [ ] **C6. Agent_Toolkit.xlsx Tools sheet** — mark 84 not-installed tools as "commercial/not installed" vs packages now 43/43
- [ ] **C7. PROTAC-DB 3.0 real data** — `protacdb_client.py` reads local CSV; fetch/parse actual PROTAC-DB
- [ ] **C8. RF model sklearn pin** — `rf_dc50/rf_dmax.joblib` load with version warning; pin sklearn 1.3.x in a venv or re-pickle

## D. Science validation

- [ ] **D1. P4ward verdict follow-up** — run completed (2026-07-10, COMPUTATIONALLY SUPPORTED); document corrected finding (pass rates similar to OH27; advantage = synthetic handle + salt bridge)
- [ ] **D2. No wet-lab validation** — all results computational; flag predicted Kd ~2 nM as prediction not measurement

---

## Priority execution order (from audit)

1. ✅ **A1** — agentic scenario tests + infinite-loop fix
2. ✅ **A2** — linker-design stage (strain loop) + scanner bug fixes
3. ✅ **B5** — retrospective benchmark (PROTAC-DB 3.0, ρ=0.243 baseline)
4. ✅ **B1** — Chemprop trained (ρ=0.758), wrapper + tests
5. ✅ **Uncertainty-aware layer (priority 2)** — conformal 92.2% coverage, AD detection, real degradation node
6. [ ] **B2** — retrosynthesis
7. [ ] **B4** — NSGA-II Pareto ranking
8. [ ] **B6** — ablation (agentic vs non-agentic)
9. [ ] **C1, C3-C8** — debt cleanup
10. [ ] **A6** — LLM layer (last, gated)
