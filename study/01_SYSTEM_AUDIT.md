# 01 — System Audit (ProtacXtend, as implemented)

**Artifact:** Phase 0 system audit. Read-only. No file modified.
**Frozen revision:** `82a0e4d` on `sprint-2` (dirty tree — see `00_REPOSITORY_FREEZE.md`).
**Audit rule:** *intended ≠ implemented ≠ exercised ≠ validated.* Each capability
is tagged **[IMPLEMENTED]**, **[IMPLEMENTED-PARTIAL]**, **[DECLARED-ONLY]** or
**[ABSENT]**, with the file that proves it.

---

## 0. One-paragraph verdict

ProtacXtend is a large, genuinely implemented TPD agent system: a deterministic
23–34-node capability-routed state machine over ~15 specialist agents, a
LLM-callable tool registry of ~30 `exec_*` functions backed by 100 tool modules,
27 TPD capability classes, 19 scientific backends, live literature retrieval
(EuropePMC/PubMed/OpenAlex/Crossref), an evidence-traced ledger, persistent run
memory, and a fault-injection harness. It is **not** a scaffold with stubs. Its
weaknesses for a publication-grade claim are equally concrete: the "agentic"
orchestrator and the deterministic graph coexist and the routing between them is
not contract-tested end-to-end; several narrative capabilities (generative linker
design, retrosynthesis, protein LMs) are **BLOCKED** backends; and there is **no
existing scored execution of the full system against adjudicated gold** anywhere
in the repository (`tpdeval/docs/03_VERDICT.md` confirms every performance cell is
`NOT YET MEASURED`).

---

## 1. Request front door

| Function | Location | Status |
|---|---|---|
| Free-text parse / intent | `protacxtend/agents/supervisor_agent.py` (`parse_user_request`) | IMPLEMENTED |
| Capability detection | `protacxtend/agents/runtime.py::_detect_capability` | IMPLEMENTED |
| Entity extraction (gene/target/E3) | `protacxtend/nlp/entity_extraction.py` | IMPLEMENTED |
| Entity resolution / identity gate | `protacxtend/agents/entity_resolution.py`, `protacxtend/identity_gate.py` | IMPLEMENTED |
| Answer contracts | `protacxtend/answer_contracts.py` | IMPLEMENTED |
| Conversational agent | `protacxtend/agentic/chat_agent.py` | IMPLEMENTED |

**Audit note:** the parser and the capability detector are two independent
implementations. `_detect_capability` and the `KNOW/REASON/DESIGN/DISCOVER`
routing in `agents/graph.py` are the actual dispatch; `chat_agent.py` is a
parallel natural-language path. Whether both paths agree on the same question is
**not** covered by a test — this is a first-class risk for H1/H2 because it
controls which branch a question takes.

---

## 2. Planner

| Component | Location | Status |
|---|---|---|
| Design planner | `protacxtend/agents/design_planner_agent.py` | IMPLEMENTED |
| Controlled search / NP-hard search control | `protacxtend/agents/search_control_agent.py` | IMPLEMENTED |
| Static routing / DAG | `protacxtend/agents/routing.py`, `protacxtend/planning/` (8 modules) | IMPLEMENTED |
| Canonical task graph | `protacxtend/canonical/task_graph.py` | IMPLEMENTED |
| Goal setting | `protacxtend/agentic/goal_setting.py` | IMPLEMENTED |
| Checkpointing | `protacxtend/agents/checkpointer.py` | IMPLEMENTED |

---

## 3. Workflow graph

| Field | Value |
|---|---|
| Class | `LocalSynGlueWorkflowGraph` in `protacxtend/agents/graph.py` |
| Node count | **34** registered nodes (`parse_user_request` … `update_memory`) |
| Routing | `CAPABILITY_NODES` dict: explicit node subsets per capability |
| Execution | deterministic sequential walk; optional `route=` override; `capability=` selects subset |
| Retry | `_should_retry` / `_step_output_missing` (per-node retry budget) |
| Persisted plan | `create_design_plan` node |

**Actual capability routes (from `CAPABILITY_NODES`):**

- **KNOW** (11 nodes): parse → plan → np_hard_search → safety → resolve_target →
  retrieve_binders → select_warheads → select_e3 → capability_answer → report → memory
- **REASON** (15): adds exit_vectors → ternary_feasibility → cooperativity → hook_effect → reasoning_answer
- **DESIGN** (28): full design pipeline incl. linkers, construction, stereoisomers,
  validation, cell_context, ADMET, novelty, applicability, cheap_filter,
  degradation, ranking, diversity, reflection, ternary, cooperativity, hook, final_ranking
- **DISCOVER** (16): target → e3 → applicability → degradation → ranking → … → final_ranking

**Audit note (critical for H5).** `evolution_refinement` (the dominant wall-clock
step) is excluded from all routine routes. Therefore "end-to-end" as actually
executed is a bounded deterministic pipeline, not an open-ended search. This is
good for reproducibility and bad for the claim that the system performs deep
iterative discovery. The e2e experiment must state which route was used.

---

## 4. Specialist agents (15 substantive + supporting)

| Agent | File | TPD stage |
|---|---|---|
| TargetResolverAgent | `target_agent.py` | G0 target resolution |
| TargetBinderRetrievalAgent | `binder_agent.py` | G2 binder/warhead retrieval |
| WarheadSelectionAgent | `warhead_agent.py` | G2 warhead |
| E3LigandSelectionAgent | `e3_agent.py` | G3/G4 E3 + ligand |
| ExitVectorDetectionAgent | `exit_vector_agent.py` | G5 exit vector |
| LinkerGenerationAgent | `linker_agent.py`, `linker_stage.py` | G5 linker |
| MolecularConstructionAgent | `construction_agent.py` | G6 candidate construction |
| TernaryFeasibilityAgent | `ternary_agent.py`, `ternary_stage.py` | G7 ternary |
| CooperativityPredictionAgent | `cooperativity_agent.py` | G7/G8 cooperativity |
| HookEffectPredictionAgent | `proximity_agent.py` (hook) | G8 hook |
| DegradationPredictionAgent | `degradation_node.py`, `prediction_agent.py` | G8 degradation |
| ADMETAgent | `admet_agent.py` | G9 ADME |
| CandidateValidationAgent | `design_gates.py` | G6/G9 validation |
| RankingAgent | `ranking_agent.py` | G11 prioritisation |
| NoveltyAgent | `novelty_agent.py` | G11/IP |
| ReflectionReviewAgent | `reflection_agent.py` | cross-cutting critic |
| EvolutionRefinementAgent | `evolution_agent.py` | optional refinement |
| KnowledgeAnswerAgent / ReasoningAnswerAgent | `answer_agent.py` | G12 synthesis |
| ReportAgent | `report_agent.py` | final report |

Supporting: `safety_agent.py`, `admet_agent.py`, `cell_context`, `applicability_domain`,
`active_learning_agent.py`, `learning_integration.py`, `context_agent.py`,
`evidence_cards.py`, `design_gates.py`, `scientific_states.py`, `state.py`, `stream.py`.

**Status: IMPLEMENTED.** This is the agent decomposition that H2/H3 ablate.

---

## 5. LLM-callable tool registry

| Field | Value |
|---|---|
| Interface | `protacxtend/agentic/registry.py` — `ToolResult`, `execute_tool(name, params)` |
| Registry specs | `_spec(name, kind, purpose, inputs, evidence, limitations, readiness)` |
| **LLM-callable `exec_*` functions** | **~30** (see below) |
| Tool modules on disk | **100** `.py` files under `protacxtend/tools/` |
| Execution wrapper | `protacxtend/runtime/agent_tools.py::run_agent_tool`; `runtime/executor.py` |
| Mode gating | `protacxtend/runtime/modes.py` (`DEMO` / `TEST` / `SCIENTIFIC`) |

**LLM-callable tools (actual names):** `exec_europe_pmc`, `exec_pubmed`,
`exec_crossref`, `exec_retrieve_fulltext`, `exec_deep_research`, `exec_resolve_target`,
`exec_chembl_molecules`, `exec_validate_smiles`, `exec_ligase_evidence`,
`exec_diagnose_capability`, `exec_list_capability_readiness`, `exec_search_web`,
`exec_search_pubchem`, `exec_retrieve_pdb`, `exec_check_synthetic_feasibility`,
`exec_predict_degradation`, `exec_predict_cell_context`, `exec_rank_candidates`,
`exec_build_candidate_dossier`, `exec_search_bindingdb`, `exec_detect_exit_vectors`,
`exec_generate_linkers`, `exec_construct_protac`, `exec_model_ternary_complex`,
`exec_score_lysine_ubiquitination`, `exec_predict_cooperativity`,
`exec_simulate_hook_effect`, `exec_predict_admet`, `exec_run_scientific_capability`,
`exec_list_scientific_capabilities`, `exec_run_protacpilot_structural`.

**Audit note (critical for H4 / Secondary endpoint 5).** A `ToolResult` carries a
status, but there is no enforced contract that a *successful* tool result is
*consumed* by the next node or the final answer. "Tool execution success" is
therefore measurable from logs, but "tool utilization" (result changed the
decision) must be instrumented explicitly in the evaluation pipeline, not assumed.
See design doc Secondary endpoint 5.

---

## 6. TPD capability classes & scientific backends

| Field | Value |
|---|---|
| Capability taxonomy | 27 classes — `protacxtend/escalation/capabilities.py` |
| Backend registry | 19 capability-first backends — `protacxtend/scientific_backends/registry.py` |
| Crosswalk | `config/capability_backend_crosswalk.yaml` |
| Readiness | READY 10 / EXECUTABLE 6 / **BLOCKED 11** |
| Dispatch / fallback classes | `scientific_backends/dispatch.py`, `consensus.py`, `validation.py` |
| Backend modules | 22 files under `protacxtend/scientific_backends/` |

**BLOCKED capabilities (must be scored as reasoning, not execution):**
ligand_preparation, linker_generation, de_novo_generation, reaction_prediction,
protein_language_models, patent_mining, proteomics, image_analysis.

**Audit note:** fallback classes (`EXACT/APPROXIMATE/SURROGATE/INFORMATIONAL_ONLY/INVALID`)
exist as config. Whether the runtime honours "never silent SURROGATE" is asserted
by config, not proven by an end-to-end test. This is exactly what the
failure-injection experiment must falsify or confirm.

---

## 7. Retrieval / RAG

| Component | Location | Status |
|---|---|---|
| EuropePMC / PubMed / OpenAlex / Crossref | `protacxtend/research/sources.py` | IMPLEMENTED (live API) |
| Full-text crawl | `literature/` + `research/` | PARTIAL (robots-aware; `SEARXNG_URL` needed for SearxNG) |
| Literature RAG | `protacxtend/memory/literature_rag.py` | IMPLEMENTED |
| Vector store | `protacxtend/memory/vector_store.py`, `memory/vector_store/` | IMPLEMENTED |
| Literature store | `protacxtend/memory/literature_store/` | present, size unknown |
| Chemical identity checks | `protacxtend/literature/chemical_identity.py` | IMPLEMENTED |
| Retrieval fallback | `protacxtend/agents/evidence_cards.py`, `runtime/agent_tools.py` | IMPLEMENTED |

**Leakage probe (Phase 0):** benchmark case-question substrings were searched
against `protacxtend/memory/literature_store` → **0 hits**. This is a first pass
only; full leakage audit is specified in the design doc §Part XXIII.

---

## 8. Evidence ledger & traceability

| Component | Location | Status |
|---|---|---|
| Evidence trace | `protacxtend/evidence/trace.py` | IMPLEMENTED |
| Evidence evaluation | `protacxtend/evidence/evaluate.py` | IMPLEMENTED |
| Evidence graph | `protacxtend/evidence/graph.py` | IMPLEMENTED |
| Evidence snapshot | `protacxtend/evidence/snapshot.py` | IMPLEMENTED |
| Evidence cards | `protacxtend/agents/evidence_cards.py` | IMPLEMENTED |
| Claim boundary | `tpdeval/scoring.py::claim_boundary`, `tpdeval/evidence.py` | IMPLEMENTED |

**Audit note (critical for H3).** Claim-level support requires (a) extracting
*material* claims from a free-text answer, and (b) matching each claim to a
retrieved evidence span. `tpdeval/evidence.py` provides citation
precision/coverage/contradiction primitives, but there is **no evidence that
claim extraction has been run on real system output**. Claim extraction is the
single highest-risk measurement component; it must be validated in the pilot.

---

## 9. State, memory, persistence

| Component | Location | Status |
|---|---|---|
| Workflow state object | `protacxtend/agents/state.py` (`WorkflowState`) | IMPLEMENTED |
| Scientific states | `protacxtend/agents/scientific_states.py` | IMPLEMENTED |
| Run memory | `protacxtend/memory/run_memory.py`, `run_state/` | IMPLEMENTED |
| Relational store | `protacxtend/memory/relational_store/`, `stores.py` | IMPLEMENTED |
| Cognitive bridge | `protacxtend/memory/cognitive_bridge.py` | IMPLEMENTED |
| Chat history | `protacxtend/memory/chat_history.sqlite3` | IMPLEMENTED |
| Run records | `protacxtend/run_records.py` | IMPLEMENTED |
| Run artifacts | `outputs/runs/<run_id>/{run.json,summary.json,trace.jsonl,evidence.jsonl,candidates.parquet,decisions.jsonl,report.md}` | IMPLEMENTED |

**Audit note (critical for H6 / leakage).** Persistent memory is active across
runs. If memory is not reset between replicate 1 and replicate 2 of the *same*
question, the replicates are **not independent** and reproducibility is inflated.
The design mandates `memory_mode ∈ {frozen, reset}` recorded per run; H6 uses
`reset` for the independence arm and `frozen` only for the persistence ablation.

---

## 10. Fallback / retry / failure handling

| Component | Location | Status |
|---|---|---|
| Node retry policy | `agents/graph.py::_should_retry` | IMPLEMENTED |
| Tool-level retry & fallback | `runtime/agent_tools.py`, `runtime/executor.py` | IMPLEMENTED |
| Fault injection (retrieval) | `runtime/fault_injection.py` — 8 scenarios (delay, timeout, 429, 500, malformed JSON, truncated, empty, recovery) | IMPLEMENTED |
| Escalation | `protacxtend/escalation/` (11 modules) | IMPLEMENTED |
| Run quarantine | `protacxtend/run_quarantine.py` | IMPLEMENTED |
| Identity gate (fail closed) | `protacxtend/identity_gate.py` | IMPLEMENTED |
| Prediction governance | `protacxtend/prediction_governance.py` | IMPLEMENTED |
| Run verdict | `protacxtend/run_verdict.py` | IMPLEMENTED |

**Audit note (critical for H4).** The fault-injection harness exists and covers 8
retrieval faults, but it is wired to the *retrieval path only* and has, per the
repository's own audits, not been run as a scored experiment across systems. The
design extends it to the 15 perturbation classes required in Part VIII and makes
`hallucinated continuation` the headline safety endpoint.

---

## 11. Final synthesis

| Component | Location | Status |
|---|---|---|
| Knowledge answer agent | `answer_agent.py::KnowledgeAnswerAgent` | IMPLEMENTED |
| Reasoning answer agent | `answer_agent.py::ReasoningAnswerAgent` | IMPLEMENTED |
| Report agent | `report_agent.py` | IMPLEMENTED |
| Answer contracts | `answer_contracts.py` | IMPLEMENTED |
| Canonical critic / decision | `canonical/critic.py`, `canonical/decision.py` | IMPLEMENTED |

---

## 12. Runnable entry points (for the harness)

| Entry | Path |
|---|---|
| Programmatic run | `protacxtend.agents.runtime.run_protacpilot(...)` |
| Deterministic vs agentic | `_run_deterministic` / `_run_agentic` in `agents/runtime.py` |
| Agent tool call | `protacxtend.runtime.agent_tools.run_agent_tool(tool, params, ...)` |
| Tool execute | `protacxtend.agentic.registry.execute_tool(name, params)` |
| E2E capability sweep | `protacxtend.runtime.e2e.run_e2e(n)` |
| Benchmark adapters | `benchmark_runner/live.py`, `benchmark_runner/baselines.py` |
| CLI | `protacxtend/cli.py`, `./PROTACXtend` |
| TUI | `tui/`, `protacxtend/tui_bridge/` |
| API | `protacxtend/backend/main.py` (FastAPI) |

---

## 13. Component → hypothesis (ablation) map

| Component | Code surface | Ablatable? | Hypothesis |
|---|---|---|---|
| Planner | `design_planner_agent.py`, `search_control_agent.py` | yes (route override) | H2 |
| Specialist agents | `agents/*_agent.py` | yes (route subset) | H2 |
| Workflow graph | `graph.py::CAPABILITY_NODES` | yes | H2/H5 |
| Persistent state | `memory/run_state`, `WorkflowState` | yes (reset) | H6 |
| Evidence gating | `evidence/*`, `design_gates.py` | yes | H3/H4 |
| Scientific backends | `scientific_backends/*` | yes (dispatch off) | H1/H5 |
| Structural reasoning | `ternary_agent`, `structural/`, docking | yes | H5 |
| Degradation prediction | `models/degradation_model.py` | yes | H5 |
| Fallback/retry | `graph._should_retry`, `escalation/` | yes | H4 |
| TPD planning | `CAPABILITY_NODES` | yes | H2 |
| RAG/retrieval | `memory/literature_rag.py`, `research/` | yes | H3 |

**Conclusion of system audit:** the architecture is real and ablatable. The
scientific claim is not yet evidenced anywhere in the repository. All six
hypotheses are currently `NOT TESTED`, and the measurement instruments required to
test them exist in `tpdeval/` and `benchmark_runner/` but have not been bound to
adjudicated gold.
