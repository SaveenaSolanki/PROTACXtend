# Technical Details Left — Audit (2026-08-01)

Honest inventory of what is built, what is stubbed, and what is not started.
Updated from the Agent_Toolkit.xlsx Implementation_Status sheet + direct
code inspection.

---

## 0. Status corrections (recent findings)

| Item | Old status | Corrected status | Evidence |
|------|-----------|-----------------|----------|
| **P4ward A1_4COOH run** | "Not executed (2-4h compute)" | ✅ **COMPLETED 2026-07-10** — verdict `COMPUTATIONALLY SUPPORTED` | `p4ward_run/p4ward_verdict.json`, `p4ward_analysis_results.json` |
| Degradation prediction | "Heuristic only (no ML)" | ✅ **Trained SynGlue transformer wired** (9M params) + RF heads + GROVER embeddings | `protacxtend/tools/synglue_degradation.py` (742 lines), 17 tests |

### P4ward verdict detail (the honest version)
- A1_4COOH COOH min distance to CRBN: **8.3 Å** (vs OH27 9.7 Å) — 1.4 Å closer
- Best linker **C8-PEG4**: 8/3600 passing poses (0.22%); **C14-PEG5**: 16/3600
- **Corrected finding**: A1_4COOH COOH and OH27 show *similar* pass rates at
  moderate/long linkers. The primary advantage of A1_4COOH is:
  1. synthetically accessible COOH handle for linker attachment
  2. predicted nM affinity via the COO⁻···LYS8 NH₃⁺ salt bridge (3.8 Å)
- Caution: predicted Kd ~2 nM (from salt-bridge energetics) is a **prediction,
  not a measurement** — no wet-lab validation exists for any candidate.

---

## 1. Agentic architecture (v0.2 → v0.3) — partial

| Item | Status | Where | Gap |
|------|--------|-------|-----|
| TypedDict state + reducers (append-only decision_log, sum retry_counts, merge evidence) | ✅ Built | `agents/state.py` | — |
| Ternary stage with repair loop + ensemble + human gate | ✅ Built + 7 tests | `agents/ternary_stage.py` | — |
| 23-node adaptive graph, gates, FailureClass dispatch | ✅ Built | `agents/agentic_core.py` | — |
| **Automated tests for the 3 agentic scenarios** (good / out-of-domain / repair loop) | ⚠️ Manual only | session logs | The scenarios were demonstrated, not asserted. `test_learning_integration.py` runs the graph via stubs (18-node good path) but does not assert the out-of-domain and repair-loop paths. |
| **v0.1 `graph.py` still uses old state** | ❌ Not migrated | `agents/graph.py` | Still `zip(ordered, ordered[1:])` sequential edges; `schemas.py` WorkflowState still has free-text `thought` field (line 103); planner uses static retry allow-list (`repeat_policy.retryable_steps`, max 1) |
| **FailureClass-aware retry in v0.1 path** | ❌ Not migrated | `tools/protac_toolbox.py` | `classify_failure` exists only in `agentic_core.py`; toolbox retry logic is still boolean "output populated" |
| **Step 7: LLM layer** | ❌ Deferred by design | `agents/supervisor_agent.py` | `AgnoSupervisorAdapter`, `LangChainToolAdapter` are empty stubs |
| **Port ternary-stage pattern to other stages** (linker design, ADMET, ranking) | ❌ Not started | — | Only ternary_stage exists as a full stage |
| Checkpointer in production wiring | ⚠️ Partial | `compile_ternary_graph()` | MemorySaver exists but no persistent checkpointer / resume path in the app |
| `agentic_mode=false` regression guarantee | ⚠️ Unverified | — | No test asserts the v0.1 pipeline is byte-identical when the flag is off |

## 2. Prediction layer (v0.4) — mostly not started

| Item | Status | Detail |
|------|--------|--------|
| **Chemprop D-MPNN degradation model trained on PROTAC-DB 3.0** | ❌ | chemprop 2.3.0 installed (CLI works); **zero training done**; `models/degradation_model.py` is a 370-line scaffold with `_heuristic_stub_prediction` |
| **Retrosynthesis integration** | ❌ | `retrosynthesis_filter.py` is a 17-line threshold stub; no AiZynthFinder/ASKCOS/RAscore/SCScore |
| **Ternary ensemble** (P4ward + DeepTernary + PRosettaC/HADDOCK) | ❌ | `ternary_ensemble` node in ternary_stage uses a perturbed-proxy simulation, not real second/third predictors |
| **NSGA-II Pareto ranking** | ❌ | Nothing found in codebase; ranking is weighted composite only |
| **Retrospective benchmark** (gold-standard PROTAC test set) | ❌ | Only `literature_benchmark.png` for the ICM proof; no pipeline benchmark |
| **Ablation study** | ❌ | None |
| **Lysine proximity scorer** (NP#5) | ❌ | Not built |
| **Hook effect modeler** (NP#7) | ❌ | Not built |
| **Cooperativity α predictor** (NP#4) | ❌ | Not built |
| **Novel E3 ligand discovery** (NP#2) | ❌ | Not built (4/600 bottleneck) |
| **Proteotype selectivity model** (NP#9) | ❌ | Not built |
| **Active learning loop** (NP#11) | ❌ | Not built |

## 3. Duplication / technical debt

| Item | Detail |
|------|--------|
| `agentic/` scaffold (12 files, 883 lines) | Superseded by `agents/agentic_core.py`; still referenced by `agentic/orchestration.py`, `agentic/perception.py` — either wire or delete |
| `memory_manager.py` (31-line stub) + `agentic/learning.py` (old LearningAgent) | Superseded by `tools/learning_memory.py` + `agents/learning_integration.py` — schema duplication (`memory_schema.DesignMemoryRecord` vs `LearningEntry`) |
| `mode_router.py` | Routes to the v0.1 `run_syn_glue_workflow` graph, not the agentic core — `agentic_mode` flag not actually plumbed |
| `degradation_predictor.py` (heuristic) vs `synglue_degradation.py` (trained) | Two parallel degradation paths; heuristic still the default in `tools/degradation_predictor.py` |
| `protacdb_client.py` | "Local PROTAC-DB style accessors" reads `protacdb_local.csv` — no actual PROTAC-DB 3.0 download/parse |

## 4. Infrastructure / external

| Item | Status | Detail |
|------|--------|--------|
| DrugBank API | ⚠️ Licensed | Client exists, needs paid key |
| Vector memory (qdrant/chroma) | ⚠️ Installed, not wired | `literature_rag.py` (144 lines) not called by any agent |
| SynGlue Docker (ADMET-AI, REINVENT, GROVER) | ✅ Running | `synglue-api` container up 16h; used via subprocess for GROVER locally instead |
| RF models sklearn version | ⚠️ Warning | `rf_dc50/rf_dmax.joblib` trained on sklearn 1.2.2, loads with `InconsistentVersionWarning` on 1.9.0 — works but untested for drift |
| GROVER patch | ✅ | `weights_only=False` in `SynGlue_Py/repos/grover/grover/util/utils.py` (local patch, not upstream) |

## 5. What is DONE (so the list is fair)

- Science: H1 (OH27 exit vector failure, 0/3600), H2 (A1_4COOH design + P4ward
  verdict), H3 (molecular glue REJECTED), full hypothesis folder, meeting PPTX
- Agentic foundation: state.py, ternary_stage.py, agentic_core.py, 7 tests
- Learning memory: learning_memory.py (590 lines), learning_integration.py,
  28 tests, end-to-end loop demonstrated
- SynGlue degradation: synglue_degradation.py (742 lines), 17 tests
- Stereochemistry engine (417 lines), linker scanner (632 lines)
- Env: `protacpilot` (py3.11, 43/43 packages), `torchdrug310`, GROVER patched
- xlsx updated: Packages 43/43, Implementation_Status 53 rows, Tools sheet corrected

---

## Priority order for remaining work

1. **Automate the 3 agentic scenario tests** (low effort, locks in the v0.2 claim)
2. **Port ternary-stage pattern to linker-design stage** (the conformational-strain
   loop — most interesting router)
3. **Retrospective benchmark** — compile a gold-standard set of ~50-100 published
   PROTACs (PROTAC-DB 3.0 / PROTACpedia) with DC50/Dmax; run the pipeline;
   measure rank correlation. This is the precondition for any performance claim.
4. **Train Chemprop D-MPNN on PROTAC-DB 3.0** — compare against SynGlue transformer
   + heuristic; pick ensemble.
5. **Retrosynthesis**: wire AiZynthFinder (or RAscore) into `retrosynthesis_filter.py`
6. **NSGA-II Pareto ranking** for multi-objective candidate selection
7. **Ablation study** after benchmark exists (removes each stage → Δ performance)
8. **Cleanup debt**: delete/wire `agentic/` scaffold, unify degradation paths,
   unify memory schemas, plumb `agentic_mode` through `mode_router.py`
9. **Step 7 LLM layer** (only after 1-8; deterministic validators must gate it)
