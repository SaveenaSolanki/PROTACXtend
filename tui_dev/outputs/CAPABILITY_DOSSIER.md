# CAPABILITY DOSSIER — closed BRD4 × CRBN vertical slice (real-TUI → engine → evidence)

Date: 2026-09-25 · Workspace: `tui_dev/` · Repo: `/storage/saveena/protacxtend`
Contract for every claimed capability: **one real input · executed tool trace ·
intermediate artifact · scientific decision · final output · failure behavior**.
Nothing in this dossier is mocked; every trace is on disk and re-runnable.

Verification commands (all reproduced for this dossier):
```
python tui_dev/scripts/drive_bridge.py            # 24/24 real-protocol checks (226 s)
python -m pytest tests/test_tui_slice_routing.py tests/test_protacxtend_tui.py   # 26 passed
python -m pytest tests/test_bridge_regression.py tests/test_run_quarantine.py \
                  tests/test_design_tui_workflow_bridge.py                        # 49 passed / 1 skipped
python -m pytest tests/test_plan_dialogue.py tests/test_explanation_pipeline.py  # 44 passed
(cd tui && npm test)                                  # 61 passed / 0 failed
python tui_dev/scripts/validate_candidates.py     # structure validation
python tui_dev/scripts/adjudicate_slice.py        # matched-case adjudication
```

---

## C1. Real-TUI target/intent routing (Node TUI + bridge)

- **Real input**: `/design Design a CRBN-recruiting PROTAC for BRD4`, `/investigate BRD4
  cereblon degraders and ligands`, `/reason why do VHL PROTACs degrade BRD4 faster than CRBN?`,
  `/evidence BRD4 degraders`, `/bogus`.
- **Executed tool trace**: `tui/src/commands.ts` (`RESEARCH_INTENTS`/`CHAT_INTENTS` registries,
  single source used by dispatcher and tests) → `tui/src/app.ts` pre-dispatch →
  `tui_bridge/server.py handle_command` (investigate now routes to the research contract;
  plan-task executor stays behind explicit task ids) → bridge handlers. Real protocol run:
  `outputs/brd4_crbn_vslice/traces/bridge_trace.jsonl` (24/24 checks PASS, 18 events, 226 s).
- **Intermediate artifact**: `bridge_trace.jsonl` + `bridge_summary.json`; node tests
  `tui/tests/commands.test.ts` (4 intent-routing tests); `tests/test_tui_slice_routing.py`.
- **Scientific decision**: command intents select deterministic handlers; chat is reserved for
  `/ask`, `/explain`, and free text. Unknown targets clarify; E3 never blocks.
- **Final output**: `research_answer` (design: executed_design=True, 150 rows) /
  `plan_answer` / `diagnosis_answer` / `chat_answer` target_card; `/bogus` → typed `error`.
- **Failure behavior**: unknown command → `{"type":"error","message":"Unknown command: bogus"}`;
  unresolved target in /design → `clarification_needed` (verified: "design a PROTAC for ZZZZ9");
  chat with blocked network → bounded-timeout state recorded (chat_start seen; external tool
  call with default 300 s timeout — registered issue, see G1).

## C2. Textual TUI engine routing (previously a fake simulation)

- **Real input**: `/design Design a CRBN-recruiting PROTAC for BRD4` typed into the input bar.
- **Executed tool trace**: `protacxtend/tui/engine.py parse_input → execute_command` →
  `handle_command` (in-process capture via new `events.capture_events` sink; cwd pinned to
  repo; `server.emit` pinned/restored for monkeypatch immunity) → same bridge handlers as the
  Node TUI. `protacxtend/tui/app.py` renders real stage statuses; the 0.3 s-per-node sleep
  simulation was **removed**.
- **Intermediate artifact**: `tests/test_tui_slice_routing.py` (11 tests incl. one REAL design
  run: executed_design=True, assembly counts, unevaluated gates); `outputs/workflows/design/…`.
- **Scientific decision**: stage statuses come from the backend (`executed`/`unevaluated`/
  `failed`); no pipeline node is marked done without backend evidence.
- **Final output**: RichLog lines: "design executed · 180 assembled → 150 valid", "gate
  ternary_coordinates: unevaluated", "unevaluated stages: ternary_coordinates,
  synthesis_route".
- **Failure behavior**: backend exception → `✗ <cmd> failed: <error>`; zero events → typed
  error; unknown verb falls back to chat (LLM answers or says no provider).

## C3. Target resolution (BRD4 → O60885)

- **Real input**: `/investigate BRD4 cereblon degraders and ligands`.
- **Trace**: `handle_research("investigate") → run_command("investigate") →
  RequestController.understand` (offline resolver: curated table → exact_symbol).
- **Artifact**: `outputs/workflows/investigate/investigate_*_evidence.json`.
- **Scientific decision**: canonical identity only (O60885, Homo sapiens, curated_table,
  match=exact_symbol); no BD1/BD2 domain statements are fabricated.
- **Final output**: `findings.target=BRD4, uniprot=O60885, known_binder_count=120,
  measured_precedent_rows=65, e3_precedent={CRBN:26, VHL:32, FEM1B:7}`.
- **Failure behavior**: unresolvable symbol → `clarification_needed` with exact-symbol
  question (ZZZZ9 verified); mouse organism → ortholog path (prior work, unchanged).

## C4. Binder retrieval (100 binders)

- **Real input**: the design request above (engine step `binder_retrieval`).
- **Trace**: `run_protacpilot(capability=DESIGN)` → TargetBinderRetrievalAgent; run warnings
  show live sources unavailable → **replayed real cached live-API records** (PubChem URLs +
  `fetched_at` in run.json warnings) — never invented.
- **Artifact**: `outputs/runs/brd4_crbn_vslice_v1/run.json` (warnings), `trace.jsonl`.
- **Scientific decision**: 100 binders enter the warhead step; 609 raw hits reported; 100
  placeholder records rejected before scoring (evidence.jsonl row: binder_rejected,
  empty_placeholder_no_name_or_smiles, count=100).
- **Final output**: `binders_retrieved: 100` (verdict.json counts).
- **Failure behavior**: live API unavailable → cache replay + demo fallback, all flagged in
  warnings; verdict drops `candidates_verified` to 0 (no fabrication).

## C5. Warhead selection (9 warheads)

- **Real input**: design request (engine step `warhead_selection`).
- **Trace**: warhead agent curated-library path; names: `BRD4_demo_quinazoline_like`,
  `BRD4_demo_triazolobenzodiazepine_like` (source=local_demo_*).
- **Artifact**: `stage_timeline.json` ("9 warheads"), `candidate_evidence.json` component rows.
- **Scientific decision**: warheads are assembly-building blocks, NOT measured binders —
  provenance census: 150/150 curated_template, **0 verified warhead provenance**.
- **Final output**: 9 warheads selected; top-ranked candidate uses
  `BRD4_demo_quinazoline_like`.
- **Failure behavior**: no source-backed BRD4 identifiers exist in the packaged library
  (curated_warheads.csv BRD4 row is `BRD4_demo_JQ1_like`, source=local_demo_jq1_like_warhead)
  → KNOW-02 adjudication abstains with recorded reason.

## C6. E3 ligand selection (CRBN)

- **Real input**: design request with explicit E3 (CRBN).
- **Trace**: `e3_agent` curated-library selection → 3 ligands;
  explicit-E3 honoring verified: "design a PROTAC for BRD4 using VHL" → **100 % VHL
  candidates** (VHL_demo_hydroxyproline_like ×59, VHL_demo_vh032_like ×32, VHL_ligand_4 ×44 —
  the last is DOI-backed, source=e3_ligand.csv (DOI 10.1021/jacs.8b05807)).
- **Artifact**: `outputs/runs/e3probe_vhl` + candidate_evidence tables.
- **Scientific decision**: explicit E3 honored through assembly; unspecified E3 → engine
  evaluates (never blocks).
- **Final output**: CRBN run → `CRBN_demo_lenalidomide_like` etc.; VHL run → VHL ligands.
- **Failure behavior**: multi-E3 panels not supported ("both VHL and CRBN" → one E3 family
  selected, CRBN in the tested run) — registered limitation surfaced by DESIGN-04
  adjudication (0.0 rubric, expert review).

## C7. Linker generation (17 linkers; classes)

- **Real input**: design request (engine step `linker_generation`).
- **Trace**: generative linker model + rule templates: ALKYL6, TRIAZOLE_ETHYL, gen_N, …
- **Artifact**: `candidate_evidence.csv` linker column; stage timeline ("17 linkers").
- **Scientific decision**: linker classes differ (alkyl/triazole/generative); stereoisomer
  expansion increased pool 162 → 180 (capped policy, warning recorded).
- **Final output**: 17 linkers; structure validation confirms linker CORE present in all 150
  assembled candidates.
- **Failure behavior**: stochastic char-GRU sampling yields run-to-run hash variation in
  assembled counts (prior audit: DESIGN-01/02/05 vary 17/18/20) — all hypothetical, 0 verified.

## C8. Molecular construction (180 assembled)

- **Real input**: design request (engine step `construction`).
- **Trace**: curated-template amide/ether couplings → 1377 attempts → 180 assembled.
- **Artifact**: `candidates.parquet` → `candidates.csv` (150×26), `candidate_evidence.json`.
- **Scientific decision**: assembly is deterministic-template; all products are hypothetical
  PROTACs pending chemist review (warning flag
  `stereoisomer_requires_separate_scoring` etc.).
- **Final output**: `assembly_counts: {assembled:180, valid:150, rejected_before_scoring:30}`.
- **Failure behavior**: live-source variance previously demonstrated (BindingDB monomers →
  0 assemblies on a rerun) — recorded in project audit, not re-fabricated here.

## C9. Candidate-structure validation (independent RDKit layer)

- **Real input**: `python tui_dev/scripts/validate_candidates.py` over the 150 candidates.
- **Trace**: fresh RDKit pass — parse → canonical → InChIKey → formula/MW → component-core
  substructure census (attachment dummies stripped) → dedup.
- **Artifact**: `outputs/brd4_crbn_vslice/run/brd4_crbn_vslice_v1/structure_validation.json/.csv`.
- **Scientific decision**: chemical validity, uniqueness, and component-core presence are
  structural facts; they are NOT biological activity or potency.
- **Final output**: 150/150 parse OK · 150/150 round-trip · **150 unique InChIKeys (0 dups)** ·
  150/150 warhead/E3-ligand/linker cores present · 34 candidates with stereocenters ·
  0 full-fragment matches (evidence-table fragments carry attachment dummies).
- **Failure behavior**: fragment-with-dummy substructure matching reports False by design
  (R-group representation), and canonicalization failures are classified separately from
  parse failures; both are visible in the JSON (earlier bug: `CalcInchiKey` API moved in
  RDKit 2026.03 — fixed to `rdkit.Chem.inchi.MolToInchiKey`, regression-caught).

## C10. Degradation prediction (predicted, never measured)

- **Real input**: candidates from the design run (engine step `degradation_prediction`).
- **Trace**: TACK-style DC50/Dmax model (`tack-style-v1 (DC50/Dmax primary) + chemprop
  cross-check`), model_confidence 0.25 per row.
- **Artifact**: `candidate_evidence.json` degradation blocks; `evidence_graph.json` (claims
  kind=computed).
- **Scientific decision**: pDC50/Dmax are ML predictions; `evidence_gates.degradation.status=
  predicted` — never labelled measured; no in-run assay evidence exists.
- **Final output**: top candidate SGA-214601f354c0 predicted pDC50 21.64 nM, Dmax 97.4 %
  (both flags: low_degradation_model_confidence, high_hook_effect_risk).
- **Failure behavior**: absent model → gate `not_assessable`; OOD flagged; published measured
  values stay literature-labelled in the explanation pipeline (MZ1 example suite).

## C11. ADMET / physicochemical (calculated)

- **Real input**: candidates from the design run (engine step `admet_prediction`).
- **Trace**: RDKit descriptors + risk proxies.
- **Artifact**: `candidate_evidence.json` admet blocks (MW/TPSA/logP/penalty).
- **Scientific decision**: `evidence_kind=calculated`; scope = physicochemical flags only,
  no PK model (per admet contract note).
- **Final output**: 150 ADMET records; top candidates carry high ADMET toxicity-risk flags.
- **Failure behavior**: unparsable SMILES → tool_failed with honest error (admet contract).

## C12. Ranking + verdict (honest negatives)

- **Real input**: 150 scored candidates (engine step `ranking`).
- **Trace**: composite score → tier → rank; run verdict via `run_verdict.compute_verdict`.
- **Artifact**: `verdict.json`, `pareto_front.csv`, `therapeutic_strategy.json`.
- **Scientific decision**: **DESIGN BRIEF ONLY** — `scientific_result=false`, reason
  "candidates lack verified component/attachment provenance", counts
  {target_resolved:true, candidates_valid:150, **candidates_verified:0**, ranked:150}.
- **Final output**: rank #1 SGA-214601f354c0, score 0.771, tier Tier 1 — a hypothesis for
  review, explicitly NOT a validated degrader.
- **Failure behavior**: zero-verified candidates do not crash the pipeline; the verdict
  downgrades the run to design-brief status and gates nomination.

## C13. Persistent evidence bundle

- **Real input**: the canonical run `brd4_crbn_vslice_v1` (fixed run_id).
- **Trace**: `run_protacpilot(config={run_id, record_run:true, capability:DESIGN})` + workflow
  adapter `_write_artifacts` — 17 files.
- **Artifact**: `outputs/brd4_crbn_vslice/run/brd4_crbn_vslice_v1/` (run.json, summary.json,
  trace.jsonl, evidence.jsonl, decisions.jsonl, report.md, verdict.json,
  therapeutic_strategy.json, pareto_front.csv, candidates.csv, stage_timeline.json,
  candidate_evidence.json/.csv, evidence_graph.json, resume_state.json,
  structure_validation.json/.csv) + `MANIFEST.md`.
- **Scientific decision**: one run id binds engine record ↔ workflow artifacts ↔ TUI payload;
  reproducibility hash `751598fdbcc453e…` recorded.
- **Final output**: report.md + verdict; `/explain brd4_crbn_vslice_v1` → render ok,
  scientific_outcome=**unassessed** (no verified candidate); `/report` → ok.
- **Failure behavior**: persistence failure → `persisted=false` surfaced in TUI payloads
  ("run artifacts were NOT persisted — nothing claimed as saved").

## C14. /plan (goal-driven, never executes design)

- **Real input**: `/plan Design a BRD4 degrader using CRBN`.
- **Trace**: bridge plan → planner → request controller (target resolved first).
- **Artifact**: `plan_answer` payload; outputs/plans/… when tasks execute.
- **Scientific decision**: plan is an executable task graph; `executed_design` stays False.
- **Final output**: interpretation "Target: BRD4 [O60885]; objective: PROTAC strategy;
  E3: CRBN." (plan_ready).
- **Failure behavior**: ambiguous target (BRD) → clarification listing candidates; unknown
  (ZZZZ9) → one exact-symbol question; correction (BRD4→HER1) → latest explicit wins.

## C15. Matched-case adjudication (machinery, provisional)

- **Real input**: `python tui_dev/scripts/adjudicate_slice.py` (6 real executions + 9
  documented abstentions).
- **Trace**: real handlers (investigate/chat-card/validate/RDKit/cell-atlas/design engine) →
  `benchmark_runner.grader.grade_answer` (LLM-free, frozen GT) → Wilson CI.
- **Artifact**: `outputs/brd4_crbn_vslice/ADJUDICATION.md`, `adjudication.json`,
  `answers.jsonl`.
- **Scientific decision**: KNOW-09 exact 1.0; KNOW-01 0.5 (O60885 ✓, architecture absent);
  KNOW-07 0.0 (5T35 listed but machinery wants ternary identification); KNOW-10 0.33;
  DISCOVER-06/DESIGN-04 0.0 rubric → expert review; abstentions excluded per protocol.
- **Final output**: mean 0.306 (provisional), correct 2/6, Wilson95 [0.097, 0.70],
  empty-answer baselines all 0.0.
- **Failure behavior**: missing data → abstention with reason (9 cases); rubric cases
  `requires_expert_review`; gold stays 48×AWAITING_EXPERT_REVIEW — machinery never signs.

---

## Cross-cutting failure matrix

| Failure mode | Where demonstrated | Honest state emitted |
|---|---|---|
| Unknown command | bridge trace `/bogus` | `error` event |
| Unresolvable target | run_command(design, ZZZZ9) | clarification_needed |
| Live API unavailable | design run warnings | cache-replay note; verified=0 |
| No ternary backend | gate ternary_coordinates | unevaluated |
| No synthesis execution | gate synthesis_route | unevaluated |
| ML-only degradation | gate degradation | predicted (never measured) |
| No verified components | verdict.json | DESIGN BRIEF ONLY, verified=0 |
| Rubric case (no expert) | adjudication | requires_expert_review |
| LLM slow / network blocked | bridge chat turn | bounded budget; registered G1 |
| Stale contract tests | bridge_regression design E3 tests | updated to executed contract |

## Registered issues (new evidence, not fixed here)
1. **G1** chat can hang on external tool calls (default 300 s timeout) when the network is
   blocked — bridge emits chat_start + system events, then stalls; TUI driver now bounds the
   wait and records the state.
2. **G2** registry `retrieve_pdb(target=BRD4, e3=VHL)` misses 5T35 (24 keyword hits, none) —
   the curated target card does list 5T35; the two surfaces disagree (source: adjudication).
3. **G3** `select_e3_ligase` ranks demo-named ligands above DOI-backed ones
   (higher exit_vector_confidence) — a ranking-quality defect with evidence.
4. **G4** multi-E3 panels unsupported (design contract is single-E3 assembly).
5. **G5** cell_context_atlas = 3 local_seed_prior rows only — not a permitted source.

## Provenance rules honored
- Every number above traces to a file: bundle, trace JSONL, validation JSON, adjudication
  JSON, or test output.
- No experimental result is claimed; predicted/calculated/unevaluated labels are preserved
  end-to-end; gold adjudication remains PENDING_HUMAN.