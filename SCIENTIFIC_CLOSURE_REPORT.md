# SCIENTIFIC CLOSURE REPORT

Status: engineering-closure work complete; **scientific correctness remains
blocked by independent gold adjudication** (0/48). No new decorative agents, UI
features or unsupported prediction claims were added.

## 0. Claim boundaries (enforced throughout)

* entity correctness is **not** answer correctness;
* execution success is **not** scientific validation;
* a conditional hypothesis is **not** a computed mechanism;
* chemical validity is **not** biological activity;
* a source-backed reference is **not** a newly discovered candidate;
* model predictions are **not** experimental measurements.

Every result carries a typed `scientific_state` and, where relevant, explicit
`missing_prerequisites`, `uncertainty` and `next_experiment`.

## 1. Deliverables index

| deliverable | path |
|---|---|
| this report | `SCIENTIFIC_CLOSURE_REPORT.md` |
| gold schema | `gold_answers_v1.jsonl` |
| adjudication template | `gold_adjudication_template.csv` |
| v3 results (144 runs) | `benchmark_results/closed48_v3/results.jsonl` |
| v3 per-case table | `benchmark_results/closed48_v3/results_table.csv` |
| fault injection | `benchmark_results/closed48_v3/fault_injection_results.csv` |
| reproducibility | `benchmark_results/closed48_v3/reproducibility_results.csv` |
| claim/evidence matrix | `benchmark_results/closed48_v3/claim_evidence_matrix.csv` |
| v3 summary | `benchmark_results/closed48_v3/summary.json` |
| verified components | `protacxtend/data/verified_components.json` |
| provenance-preserving tests | `tests/test_scientific_closure.py`, `tests/test_fault_injection.py` |

## 2. BindingDB REST warning — resolved

The warning “BindingDB REST needs an API key (BINDINGDB_API_KEY)” was **false**.
The public REST API documented at
<https://www.bindingdb.org/rwd/bind/BindingDBRESTfulAPI.jsp> requires no key:

```
getLigandsByUniprot?uniprot={UNIPROT};{cutoff}&response=application/json
getLigandsByUniprots?uniprot={UNIPROTS}&cutoff={cutoff}&response=application/json
getLigandsByPDBs?pdb={PDBS}&cutoff={cutoff}&identity={identity}&response=application/json
```

Changes:
* `protacxtend/tools/bindingdb_lookup.py` now has `build_bindingdb_uniprot_url`,
  `build_bindingdb_uniprots_url`, `build_bindingdb_pdb_url`,
  `parse_bindingdb_rest_json` (handles both `getLindsByUniprotResponse` and
  `getLindsByUniprotsResponse` shapes, ranges, and empty/truncated payloads) and
  `fetch_bindingdb_rest`.
* `binder_agent._search_bindingdb` uses the documented endpoint with no key,
  parses both shapes, dedupes by canonical SMILES and keeps the most potent
  measurement. `_bindingdb_needs_key()` is retained as a deprecated shim that
  returns `False`.
* The warning was replaced by an honest provenance note when the query simply
  returns no records.

Live verification against `O60885` returned the real JSON payload (thousands of
measurements); the parser returned the expected records. Tests:
`test_bindingdb_rest_parses_both_documented_shapes`,
`test_bindingdb_rest_requires_no_api_key`.

## 3. Task 1 — gold schema and adjudication workflow

`scripts/build_gold_v1.py` writes 48 records and the reviewer template.

* `gold_answers_v1.jsonl`: `case_id`, `required_entities`, `gold_answer_type`,
  `acceptable_answer` (**blank**), `proposed_answer_from_frozen_gt`,
  `mandatory_facts`, `prohibited_claims`, `expected_route`, `expected_stop_state`,
  `minimum_evidence`, `acceptable_alternatives`, `expert_labels`,
  `consensus_notes`, `status`.
* `gold_adjudication_template.csv`: the same fields plus
  `reviewer_1_decision`, `reviewer_2_decision`, `adjudicator_decision`, `status`.
* Every record is `AWAITING_EXPERT_REVIEW`; `acceptable_answer` is empty. No
  scientific gold answer was invented. The frozen pre-existing ground truth is
  carried only as `proposed_answer_from_frozen_gt` for the reviewer.

Scoring is unlocked only when the adjudicator column is filled and the status
changes from `AWAITING_EXPERT_REVIEW`.

## 4. Task 2 — KNOW-12 deterministic list-vs-database comparison

`protacxtend/agents/identifier_comparison.py`:
normalisation (accessions, gene symbols, names, SMILES→canonical),
alias resolution from curated tables + verified references, duplicate removal,
and `shared` / `only_in_supplied_missing_from_database` / `only_in_database_added`
/ `unresolved` sets with provenance. Wired into `KnowledgeAnswerAgent`; the
result is stored at `scientific_answer.identifier_comparison`.

Example: `compare_identifier_lists(["JQ1","OTX015","JQ1","brd4"], ["BRD4","JQ1","MZ1"])`
→ shared 2 (`JQ1`, `brd4→BRD4`), missing `OTX015`, added `MZ1`, duplicate `JQ1`
removed. Offline KNOW-12 reports that the available curated tables do not contain
`JQ1`/`OTX015` and flags that a live permitted-database query is required.

## 5. Task 3 — fault injection

`protacxtend/runtime/fault_injection.py` + `tests/test_fault_injection.py`.
Scenarios and measured outcomes (`closed48_v3/fault_injection_results.csv`):

| scenario | detected | recovered | fallback | abstained | hallucinated continuation |
|---|---|---|---|---|---|
| delay | yes | yes | yes | no | no |
| timeout | yes | yes | yes | no | no |
| HTTP 429 | yes | yes | yes | no | no |
| HTTP 500 | yes | yes | yes | no | no |
| malformed JSON | yes | yes | yes | no | no |
| truncated payload | yes | yes | yes | no | no |
| empty result | yes | yes | yes | no | no |
| fallback recovery | yes | yes | yes | no | no |
| abstention, no fallback | yes | yes | no | **yes** | no |

Detection means the fault produced no fabricated live data; fallback uses the
cited/curated tier; abstention is the typed `empty` status with zero binders when
no fallback exists. Hallucinated continuation is zero in every scenario.

## 6. Task 4 — verified component coverage

`scripts/build_verified_components.py` now decomposes three real PROTAC-DB
entries — **MZ1 (BRD4–VHL)**, **dBET1 (BRD4–CRBN)**, **MT-802 (BTK–CRBN)** — by
locating each linker with a per-PROTAC SMARTS, cutting the two junctions, and
**re-zipping with RDKit `molzip` to reproduce the source InChIKey**. A build that
fails the identity check is refused.

Each of the 9 components carries canonical + isomeric SMILES, capped-fragment
InChIKey, mapped attachment atom(s), source (PROTAC/DOI/PDB), target/E3,
applicability limits and the identity-check method. Verified paths:
`BRD4–VHL`, `BRD4–CRBN`, `BTK–CRBN` (non-BRD4). The design path now uses the
**same source PROTAC's** warhead + linker + E3 ligand for the reference, so the
non-BRD4 path reproduces the actual MT-802 structure.
Tests: `test_split_reassembly_identity_holds[MZ1|dBET1|MT-802]`,
`test_crbn_and_non_brd4_paths_exist`, `test_every_verified_component_has_full_provenance_and_identity`.

## 7. Task 5 — MZ1 experimental assay fields

The reference records in `verified_components.json` now carry source-linked
assay fields: `dc50_nM`, `dmax_percent`, `cell_line`, `treatment_time_h`,
`assay`, `article_doi`, `database`, `pdb`, `molecular_formula`, `source_inchikey`.
Missing measurements are the literal string `not_reported` and are never filled
by predictions (e.g. dBET1 `dmax_percent = not_reported`).
Test: `test_mz1_assay_fields_report_not_reported_when_missing`.

## 8. Task 6 — REASON evidence cards

`protacxtend/agents/evidence_cards.py` computes four cards — **target
degradability**, **E3 suitability**, **safety**, **resistance** — each exposing
`inputs`, `sources`, `scoring_terms`, `missing_evidence`, `uncertainty`,
`next_experiment` and a `status`. Cards are labelled `conditional` or
`insufficient`; a card never asserts a measured mechanism. Attached to
`scientific_answer.evidence_cards` by `ReasoningAnswerAgent`.
Test: `test_reason_evidence_cards_expose_required_fields`.

## 9. Task 7 — DESIGN gates

`protacxtend/agents/design_gates.py` evaluates seven gates:
chemical validity, component fidelity, attachment validity, conformer
feasibility, evidence status, applicability domain, uncertainty.

* **Hard gates** (required for `valid_candidate`): chemical validity, component
  fidelity, attachment validity, source-backed evidence status.
* **Soft gates** (recorded as caveats): conformer feasibility, applicability
  domain, uncertainty.

`evaluate_design_gates` returns `valid_candidate`, `design_brief` or
`justified_no_go`. A hypothetical-marker product can never be `valid_candidate`
(the evidence gate fails); an empty post-filter set is zero candidates.
Test: `test_design_gates_reject_hypothetical_attachment`,
`test_design_gate_state_is_valid_candidate_for_verified`.

## 10. Task 8 — frozen v3 benchmark, reproducibility and container

Run: `python scripts/run_closed48_v3.py --seeds 0,1,2 --workers 10 --budget 150`
(48 cases × 3 seeds = 144 runs, separate from `closed48_locked`,
`repaired_frozen` and `closed48_v2_structured`).

| metric | value |
|---|---|
| latency median | 1.46 s |
| latency IQR | 1.99 s |
| latency p95 | 110.84 s |
| latency max | 122.24 s |
| state-stable cases | 48/48 |
| output-hash-stable cases | 42/48 |
| evidence-complete cases | 26/48 |
| boundary violations | 0 |
| verified-candidate runs | 9 (DESIGN-04, -08, -10 × 3 seeds) |

Answer states: `supported_answer` 36, `conditional_hypothesis` 54,
`valid_candidate` 9, `design_brief` 18, `justified_no_go` 27. All 27 no-go
records have `abstention_justified = true`.

**Reproducibility caveat (measured, not hidden).** The scientific *state* is
stable across all three seeds for all 48 cases. The *output hash* is stable for
42/48; the six varying cases are `design_brief` cases whose stochastic linker
generation yields a different number of hypothetical candidates per seed
(DESIGN-03 32/34/40; DESIGN-06 and DESIGN-12 36/36/38; DESIGN-01/02/05 vary
only in the assembled-count text). The three source-backed `valid_candidate`
cases are seed-stable. This is why the report separates *state stability* from
*candidate-set stability*.

Per-stage timing (median / p95 / max over the runs that reached each node):

| stage | n | median | p95 | max |
|---|---|---|---|---|
| generate_linkers | 27 | 34.86 s | 38.17 s | 40.26 s |
| predict_degradation | 27 | 30.46 s | 38.30 s | 39.93 s |
| validate_protacs | 27 | 0.30 s | 0.90 s | 1.28 s |
| construct_protacs | 27 | 0.21 s | 0.78 s | 0.80 s |
| cheap_filter_candidates | 27 | 0.12 s | 0.35 s | 0.45 s |
| detect_exit_vectors | 30 | 0.003 s | 0.033 s | 0.089 s |
| capability_answer | 36 | 0.00 s | 3.30 s | 3.53 s |
| reasoning_answer | 36 | 0.00 s | 1.64 s | 1.67 s |

The two dominant costs are linker generation and degradation prediction; both
only run on the three target/E3 paths that have a verified component set.

### Clean-container run

`Dockerfile.closure` builds a clean `python:3.11-slim` image with the light
scientific stack (RDKit/numpy/pandas/scipy/scikit-learn) and the repo.

```
docker build -f Dockerfile.closure -t protacxtend-closure .
docker run --rm -e PROTACXTEND_EXECUTION_MODE=scientific \
  -v /storage/saveena/protacxtend/data:/app/data:ro \
  protacxtend-closure \
  python -m pytest tests/test_scientific_closure.py tests/test_fault_injection.py \
    tests/test_gate_c_input_contract.py -q
# 29 passed
```

## 11. Answers to the additional questions

**How many E3 ligases do we have?** The curated E3-ligand library contains
**19 distinct E3 ligases** (CRBN, VHL, DCAF1/11/15/16, FEM1B, MDM2, XIAP, cIAP1,
IAP, KEAP1, RNF114, RNF4, KLHDC2, KLHL20, FBXO22, AhR, UBR box). Only **3**
currently have a source-backed, atom-mapped recruiter in the verified registry
(VHL via MZ1, CRBN via dBET1/MT-802). The rest are literature-cited ligands
without a validated exit vector and are treated as unverified handles.

**Target vs E3 disambiguation.** `entity_resolution.resolve_entities` resolves
once from explicit keys. A combined `target/e3` or `target-e3 pair` key is split
into the first entity (target) and the remainder (E3, validated against the
known-E3 set). Word-boundary matching prevents `AR` inside `warhead`.
`TargetResolverAgent` then verifies the UniProt hit against the requested symbol
and **rejects mismatches** (the BTK→PTK6 rejection is this guard). Adding BTK
(Q06187) and other targets to `curated_targets.csv` gives direct resolution
instead of relying on a raw search.

**UniProt + PubChem evidence.** Target evidence is carried as a `TargetRecord`
(accession, organism, structures, source tier: curated → reviewed UniProt →
raw search). PubChem is parsed in `protacxtend/tools/pubchem_lookup.py`
(`PropertyTable.Properties` → CanonicalSMILES, IsomericSMILES, IUPACName,
MolecularFormula, MolecularWeight) and the binder agent enriches retrieved
binders with PubChem InChIKey/formula/MW. Remaining gap: use CID-based batched
property lookups and PubChem synonyms for alias resolution.

**PPI / two-target complexes / other modalities.** The current engine is a
bifunctional-degrader (PROTAC/molecular-glue) engine. A PPI interface is handled
only as a **target context** plus a ternary-feasibility proxy; it does not model
a second protein as a co-target. It **cannot** produce an antibody-drug
conjugate: there is no antibody, payload-conjugation or linker-cleavage
representation. Adding ADC/molecular-glue modalities would require new
component types and gates; this is out of scope and is listed as a blocker.

**Cellular context.** `predict_cell_context` and `CellContextAgent` score
target/E3 compatibility for a supplied cell line; the benchmark only carries
MM1.S/H1299/HEK293T. Better resolution needs a real expression resource
(DepMap/CCLE/HPA) wired as an operative adapter with a source URL — currently a
documented blocker, not a fabricated signal.

## 12. Before/after examples

| case | before (locked) | after (v3) |
|---|---|---|
| KNOW-01 | timeout in `retrieve_target_binders` (120 s), 0 evidence | `supported_answer`, route without binder retrieval, `BRD4 = UniProt O60885`, ~1.3 s |
| REASON-07 | abstained at `select_warheads` | `conditional_hypothesis`: JQ1 inhibits, MZ1 degrades; next experiment = CRBN/VHL-dependence + proteasome control |
| DESIGN-04 | timeout, 0 candidates | `valid_candidate`: source-backed BRD4–CRBN (dBET1) reference passes the hard gates; 2 verified candidates; `design_brief` for hypothetical components |
| DISCOVER-01 | abstained on a bogus target | `justified_no_go`: "supplied table describes the schema but contains no candidate rows" |

## 13. Exact test commands and outputs

```
python scripts/build_verified_components.py
# wrote protacxtend/data/verified_components.json
# MZ1 PTAMRJLIOCHJMQ-PYNGZGNASA-N; dBET1 LKEGXJXRNBALBV-PMCHYTPCSA-N; MT-802 AJTLGUJXIKEZCQ-UHFFFAOYSA-N

python scripts/build_gold_v1.py
# wrote gold_answers_v1.jsonl (48 records); wrote gold_adjudication_template.csv

python scripts/run_fault_injection.py
# 9 scenarios, detection/recovery/fallback/hallucination recorded

python scripts/run_closed48_v3.py --seeds 0,1,2 --workers 10 --budget 150
# 144 records; see summary.json

python3 -m pytest tests/test_scientific_closure.py -q         # 11 passed
python3 -m pytest tests/test_fault_injection.py -q            # 14 passed
python3 -m pytest tests/test_structured_run.py -q             # 16 passed
python3 -m pytest tests/test_structured_run.py tests/test_scientific_closure.py -q  # 27 passed
docker run ... pytest tests/test_scientific_closure.py tests/test_fault_injection.py \
    tests/test_gate_c_input_contract.py -q                    # 29 passed
```

Broader affected-suite run (18 files: structured run, closure, fault injection,
Gate C, execution modes, P1 governance/baselines, agentic reasoning/execution/
orchestration, scientific contract, benchmark runner, binder live, PubChem,
warhead mining, component wrappers):

```
python3 -m pytest -m "not network" -q \
  tests/test_structured_run.py tests/test_scientific_closure.py tests/test_fault_injection.py \
  tests/test_gate_c_input_contract.py tests/test_execution_modes.py tests/test_p1_governance.py \
  tests/test_p1_baselines.py tests/test_agentic_reasoning.py tests/test_agentic_execution.py \
  tests/test_agentic_orchestration.py tests/test_scientific_contract.py tests/test_benchmark_runner.py \
  protacxtend/tests/test_binder_live.py protacxtend/tests/test_pubchem_lookup.py \
  protacxtend/tests/test_warhead_mining.py protacxtend/tests/test_protac_component_wrappers.py
# 157 passed, 1 deselected (after fixing the two stale assertions below)
```

Two initial failures were resolved during this run: one was a stale test
expectation (`n_verified_candidates` is now 2 for DESIGN-04 because both the
BRD4–CRBN and BRD4–VHL references are assembled), and one
(`test_benchmark_runner.py::test_adapters_exist_and_real_systems_are_locked`)
passes in isolation and only failed in the serial run due to an execution-mode
context leak between tests (a test-isolation issue, not a code defect).

**Full-suite status.** The complete suite is 1089 tests and includes long
scientific/docking tests; a `-m "not network"` run was started and reached ~6%
in the available window, so the representative affected-suite run above is
reported instead of a completed 1089-test pass. No claim of a full green suite
is made.

## 14. Remaining scientific blockers

1. **Gold adjudication 0/48.** No accuracy claim is possible; the schema and
   template are ready for two reviewers + adjudicator.
2. **Verified components cover 3 paths.** CRBN/VHL only; 16 other curated E3
   ligases lack validated exit vectors.
3. **No measured activity anywhere.** DC50/Dmax in the reference records are
   `not_reported` or literature values, never model output.
4. **REASON cards are evidence summaries**, not computed mechanisms.
5. **Modality boundary.** PROTAC/molecular-glue only; no ADC or co-target PPI
   representation.
6. **Cellular context** needs an operative DepMap/CCLE/HPA adapter.
7. **Live-network validation** of the deadline/cache path in the configured
   environment remains pending (fault injection is deterministic and offline).

## 15. Stale invalid-run remediation (`run_e4e21ccd`)

A persisted demo run `outputs/runs/run_e4e21ccd/` (request “Reason
mechanistically: BRD$-VHL”) carried four defects: the malformed token `BRD$`
resolved to **RLBP1 / P12271**, candidates were mislabelled with that target,
empty binder placeholders were counted, and it emitted the false “BindingDB REST
needs an API key” warning. It was already marked `INVALID_RUN.md` and is kept
only as a regression fixture.

Re-running the identical request on the current code:

| check | invalid run | current code |
|---|---|---|
| resolved target | RLBP1 / P12271 | `''` / `None` (`validation_status: unresolved`) |
| BindingDB API-key warning | present | **absent** |
| fabricated candidates | 128, mislabelled | 0 |
| target-mismatch guard | absent | rejects RLBP1 hit |

Actions taken:
* deleted the untracked stale `build/` artifact (56 MB) that still contained the
  old BindingDB warning and old exit-vector code;
* `tui_bridge/server.py::handle_report` now excludes any directory containing
  `INVALID_RUN.md` from run listing and refuses to serve it by name (status
  `invalid`);
* wrote `outputs/runs/run_e4e21ccd/{CORRECTED_RUN.md,corrected_run.json,corrected_therapeutic_strategy.json}`
  (comparison only; not citeable);
* added regression tests `test_malformed_target_token_is_never_resolved_to_rlbp1`,
  `test_no_false_bindingdb_api_key_warning_in_retrieval_path`,
  `test_invalid_run_is_quarantined_by_marker`.

## 12. Addendum (2026-09-24) — comparison-only enforcement, SYNTHESIS, next experiment

- **Precise citation claims replace the broad `citeable` boolean.**
  `protacxtend/run_quarantine.py::citation_claim()` returns one of:
  `not citeable (quarantined)`, `citeable as a reference reconstruction
  (comparison_only); not scientific evidence`, or `citeable as a computational
  run record, subject to module-level claim gating`. `run_status()` classifies
  each persisted run as INVALID / COMPARISON_ONLY / OK; `serve_payload()` is the
  single source every surface (TUI, API, search, reports, ENGRAM) bases its
  response on.
- **Corrected replay is visibly comparison_only on every surface.**
  `run_e4e21ccd_corrected_v1` (manifest `role: corrected_replay_comparison_only`,
  `scientific_evidence: false`) is served by the TUI with
  `status: comparison_only` plus a `>>> COMPARISON-ONLY REPLAY <<<` banner, by
  `GET /runs/{run_id}` with the same status, flagged `comparison_only` in run
  search, labelled by the `report` CLI via `citation_claim`, and refused by the
  ENGRAM gateway (`CognitiveMemoryBridge.ingest_run_dir` → `comparison_only:
  true`, `n_predictions: 0`). The TUI/API responses are checked against the
  run record fields (`scientific_evidence`, `role`), not merely report.md text
  (tests `test_tui_marks_corrected_replay_comparison_only_against_record`,
  `test_api_marks_corrected_replay_comparison_only`).
- **SYNTHESIS + stage-by-stage audit**: `outputs/runs/run_e4e21ccd_corrected_v1/SYNTHESIS.md`
  with per-stage evidence keys into `manifest.json`, `corrected_run.json`,
  `corrected_therapeutic_strategy.json`, `CORRECTED_RUN.md`, and the historical
  `INVALID_RUN.md`; citation boundary stated (no novelty / predicted-degradation
  / experimental-mechanism claims).
- **Next experiment verified and kept pending**:
  `outputs/runs/run_brd4_vhl_scientific_v1/NEXT_EXPERIMENT_VERIFIED.md`
  upgrades the proposed assay to distinguish degradation from VHL dependence:
  measured dose–response (≥8 points incl. hook regime), time response
  (0.5/2/6/24 h), VHL-dependence controls (VHL-null and VH032 competition),
  proteasome control (MG-132/bortezomib), dose-matched epimer + DMSO, and
  pre-specified outcome definitions. Status: **PENDING** — no measurements
  performed; literature MZ1 DC50/Dmax (8 nM / 98%, HeLa 24 h) remain labelled
  measured-with-source and are not results of this protocol.
- **Tests**: `tests/test_run_quarantine.py` now 15 tests (quarantine + five
  surface checks); combined with closure and fault-injection suites: 43 passed.
