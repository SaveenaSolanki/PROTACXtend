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

## 2026-08-03 — Roadmap execution: Tasks 1-3 (immediate actions)
- **Task 1 — Architecture freeze/unify** (release/v0.3-agentic-core branch):
  git initialized, `.gitignore` (6GB repos excluded), branch created.
  ONE entry point `agents/runtime.run_protacpilot(mode=deterministic|agentic)`;
  mode_router + backend API route both modes through it; unified degradation
  interface (chemprop→synglue→heuristic, provenance + labelled fallback);
  DesignMemoryRecord deprecated (Pydantic alias); agentic/ scaffold marked
  LEGACY; agentic_mode=False regression + agentic_mode=True e2e tests pass
  (10 unification tests).
- **Task 2 — Real retrosynthesis**: RAscore prescreen (SAScore proxy fallback,
  clearly labelled) + **AiZynthFinder real route search** (pretrained USPTO
  ONNX policy + templates + ZINC stock downloaded: 447 MB). RetrosynthesisResult
  schema (exact spec), routing (feasible→pareto, repairable→linker, no-route→
  human, tool-fail→RAscore-only downgrade), provenance, tool-failure safety.
  13 tests (12 fast + 1 slow real). Verified LIVE: acetamide → 24 routes,
  1-step, feasible; real PROTACs → honest human_required. Fixed 4.4.1 API
  differences (Configuration→configdict, RouteCollection dicts, select_all).
- **Task 3 — Real ternary ensemble**: P4ward + geometric proxy + **SE3-PROTACs
  with real pretrained weights** (loaded, ESM embeddings, live score) — two
  genuinely independent methods. Staged escalation (reject<0.30, p4ward<0.60,
  top→p4ward+se3), consensus on RAW scores (agreement+uncertainty),
  disagreement→human gate. Live: HMGB2-ICM candidate → geometric 1.0 vs SE3
  ~0 → AMBIGUOUS → human gate (real scientific disagreement surfaced). 12 tests.
- **Env fix**: aizynthfinder downgraded rdkit→2023.9.6 breaking chemprop;
  restored rdkit 2026.3.5 and relinked cuik_molmaker's 158 hash-named RDKit
  libs to the current rdkit.libs (predictions verified correct).
- Full suite: 247 passed (11 skipped, slow deselected).

## 2026-08-04 — Roadmap: Tasks 4-8 (endpoint, E3-context, LLM validation, memory, e2e+benchmark)
- **Task 4 — Degradation endpoint**: multi-target Chemprop (logDC50 + Dmax, 1,126
  rows, scaffold split), active/inactive classification (DC50≤100nM & Dmax≥50%),
  cellular-context gate (E3 expression veto: VHL-low in MM1.S → chemistry score
  downgraded to low_confidence with explanation), uncertainty + AD retained.
  10 tests.
- **Task 5 — E3-context engine**: deterministic evidence-based scoring
  (expression/colocalization/ligand/structural/resistance with per-component
  evidence refs). Headline requirement verified verbatim: "CRBN preferred over
  VHL because CRBN has higher expression (1.00 vs 0.20) ... despite VHL having
  better structural availability (1.00 vs 0.90)". 8 tests.
- **Task 6 — LLM role validation harness**: scripts/eval_llm_roles.py — 6 roles
  × metrics (valid output, unsupported tools=0, SMILES edits=0, hallucination=0,
  human-gate recall, context overflow). Live gpt-oss:20b: safety metrics all
  perfect; GENUINE findings: repair chose retry for OOD (deterministic layer
  overrides), report dropped a number (templates insert numbers). CI-safe
  deterministic tests. 8 tests + findings doc.
- **Task 7 — Memory unification**: three separate stores (RunStateStore,
  EvidenceStore, LearningStore) in memory/stores.py + MemoryHub. Learning
  retrieval sequence (failure signature → validated match → suggestion →
  deterministic validation → outcome recording); failed repairs reduce
  priority; human corrections separate from model decisions; memory cannot
  override validators (tested). 10 tests.
- **Task 8 — e2e challenge + formal benchmark**: scripts/e2e_challenge.py ran
  A (known potent → active), B (known weak → inactive), C (HMGB2-ICM → active
  chem vs SE3 ternary ~0 → AMBIGUOUS → human gate; cross-layer disagreement
  documented). Full records in outputs/e2e_challenge/. 8-system benchmark
  harness (scripts/agentic_benchmark.py) running; formal report scaffold at
  outputs/benchmark/FORMAL_BENCHMARK_REPORT.md.

## 2026-08-04 — Production wiring (checkpointer / queue / tracing / docker / benchmark table)
- **Persistent LangGraph checkpointer**: agents/checkpointer.py — postgres
  (checkpoint-4.x-native; verified CROSS-PROCESS interrupt/resume with
  dockerized postgres) → sqlite → memory fallback. run_agentic_workflow
  accepts thread_id; runtime.run_protacpilot surfaces __interrupt__ and
  runtime.resume_agentic_run resumes the same thread. Discovered: sqlite
  backend 3.1.1 is incompatible with langgraph 1.2.10's checkpoint 4.x
  serialization; postgres is the production path; invoke returns
  {'__interrupt__': [...]} rather than raising in langgraph 1.2.10.
- **Job queue**: synglue_agent/queue/job_queue.py — redis (if available) /
  sqlite fallback; submit/claim/complete/fail/needs_human lifecycle;
  deploy/p4ward_worker.py consumes jobs (retrosynthesis/degradation done,
  p4ward → needs_human budget gate). Verified end-to-end (2 jobs → done).
- **Central logging/tracing**: observability/tracing.py — per-run trace.jsonl
  (node_start/end, tool_call, decision, error, run_end) + summary.json;
  wired into runtime so EVERY run is auditable (outputs/runs/<run_id>/).
- **Dockerized services**: deploy/docker-compose.yml (api/worker/postgres/
  redis/ollama) + Dockerfile.api; compose validated.
- **8-system benchmark COMPLETED + interpreted**: fixed_pipeline ρ=0.479 vs
  all chemprop-based systems ρ=0.785 (enrichment 0.75→0.875). Honest
  interpretation: the degradation layer dominates in-domain ranking; the
  agentic components' value shows on failure/safety scenarios (per-layer
  ablation B6), not on clean in-domain ranking. Report table filled.
- 10 production-wiring tests; full suite 293 passed.

## 2026-08-04 — Close-out: model volumes, stack boot-test, LLM role gaps fixed
- **docker-compose model volumes**: data/ + outputs/ + SynGlue_Py mounted (bind)
  into api + worker services (models are 500MB+, never baked into the image);
  `docker compose config` validated.
- **Stack boot-tests passed**: (A) FastAPI /agentic-design against dockerized
  postgres → 20 checkpoints persisted for the run's thread (queried via psycopg);
  (B) redis-backed JobQueue lifecycle through dockerized redis (queued→running→
  done). Postgres container had stopped (17h) — restarted and re-verified.
- **LLM role gaps FIXED at the model level** (not just deterministic overrides):
  - repair role: prompt hard rules (OOD→human_review ONLY; repairable classes
    enumerated; SMILES forbidden; escalate only for OOD/budget/unknown) —
    both cases now pass (caught and re-pinned an over-correction).
  - report role: ReportDecision gained a machine-checkable `numbers` field;
    prompt requires every supplied value listed there — model now declares
    [{DC50: 5.2 nM}, {Dmax: 91%}] exactly.
  - harness checker fixes (boundary-aware regex: no "50" from "DC50", no
    ordinal "1."; hallucination = in summary, absent from prompt AND numbers).
  - **All 5 roles pass at 100%; metrics: 1.0 valid output, 0 tools, 0 SMILES
    edits, 0 hallucinations, 1.0 human-gate recall, 0 context overflow.**
- Findings doc + formal benchmark report updated to reflect the fixes.

## 2026-08-04 — LLM case bank expanded 9 → 17 + full compose build attempt
- **Case bank expanded per spec** (supervisor 4, evidence 4, critic 3, repair 4,
  report 2): bounded-plan + mandatory-validation, contradictory evidence, source
  routing, low-confidence claim, budget exhaustion, prediction-labelling,
  evidence-refs. SupervisorDecision gained plan_steps/selected_tools/
  includes_validation; ReportDecision gained evidence_refs.
- **Live model now passes 17/17 (100%)** with all safety metrics perfect. The
  expansion surfaced and fixed: 4 checker bugs (validation inferred from plan
  content not just the boolean; hallucination regex boundary-aware + uses the
  actual prompt; prediction-labelling accepts standard verbs; repair expected
  action matched to the deterministic controller's actual linker-regeneration
  policy), plus prompt hardening (plan_steps required, evidence_refs filling).
- **Docker compose build in progress** (requirements.txt expanded to full
  runtime set: torch/chemprop/aizynthfinder/psycopg/redis/LLM clients) —
  full-stack boot test pending build completion.

## 2026-08-06 — Full compose stack boot-tested end-to-end + LLM case bank at 17
- **Full stack boots and works**: api (host 8001) + worker + postgres + redis +
  ollama all healthy via docker compose. Containerized verification passed:
  /health, /llm/status, /agentic-design (20 checkpoints persisted to the
  COMPOSE postgres for the run's thread), /mode validate (RDKit chemistry),
  queue job through compose redis → worker → done.
- **Real degradation quality in the container**: chemprop_multitarget model
  (DC50=33.9 nM, Dmax=80%, class=active) with AD correctly flagging
  out_of_domain — fixed the GPU assumption (auto accelerator: container has
  no CUDA → cpu) that silently fell back to heuristics.
- **Container build fixes** (each surfaced by the real boot test): psycopg-binary
  (PostgresSaver), openpyxl (PROTAC-DB xlsx), libexpat1 (cuik_molmaker; needed
  a dedicated apt RUN + separate worker image rebuild), aizynthfinder omitted
  (numpy<2 conflict → RAscore-only retrosynthesis degradation per spec),
  rdkit pinned 2026.3.4 (cuik-molmaker-pin match), ABI fix as script
  (heredoc needs syntax directive).
- **LLM case bank expanded 9 → 17 cases** (supervisor 4, evidence 4, critic 3,
  repair 4, report 2): live gpt-oss:20b now passes 17/17 (100%) with all
  safety metrics perfect; 4 checker fixes + prompt hardening + 1 genuine
  supervisor gap fixed (plan validation inference).

## 2026-08-06 — RELEASE v0.3.0-agentic-core
- Tag `v0.3.0-agentic-core` created on `release/v0.3-agentic-core` (commit 66c42849; rewritten as 1c02183 after 7.93 GiB → 100.79 MiB filter-repo hygiene for GitHub publication).
- `RELEASE_CLOSURE_REPORT.md` — definitive closure report (architecture, 293
  tests, benchmark tables, container boot-test, LLM validation 17/17, e2e
  cases, model versions, commit, limitations, reproduction, PASS/FAIL).
- `RELEASE_NOTES_v0.3.0.md` — added features / scientific models / safety /
  infrastructure / validation / known limitations.
- Statement: SynGlue v0.3-agentic-core satisfies the predefined functional,
  scientific-safety, persistence, deployment and observability requirements
  for a research-grade agentic PROTAC design platform.

## 2026-08-07 — PUBLISHED to GitHub (controlled)
- Repo: github.com/SaveenaSolanki/Protac_Pilot (private).
- History hygiene: filter-repo purge (7.93 GiB → 100.79 MiB); virtualenvs,
  cloned deps, big data dumps, runtime DBs removed from history + gitignored.
- Git identity fixed: Saveena Solanki <113490997+SaveenaSolanki@users.noreply.github.com>.
- Branches: `main` + `release/v0.3-agentic-core` @ 7d1dc18 (release history
  + MIT LICENSE adopted + uploaded v0.3 snapshot preserved as ancestor).
- Tag `v0.3.0-agentic-core` → 7d1dc18; GitHub Release created from RELEASE_NOTES.
- Branch protection on both branches: 1 required review, linear history,
  force-push/deletion disabled, admins enforced.
