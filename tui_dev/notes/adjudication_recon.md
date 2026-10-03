# PROTACXtend Benchmark / Adjudication Machinery — Recon Memo

Read-only recon of `/storage/saveena/protacxtend`. All statements below were
verified directly against on-disk files on 2026-09-25. Nothing was modified.
Files that do not exist are called out explicitly.

---

## 1. `benchmark_runner/grader.py` (read fully, 295 lines)

Deterministic, LLM-free scoring engine. **No abstention logic lives here** —
an answer that is empty string `""` is graded as a normal (wrong) answer
except where callers explicitly abstain before calling it.

### 1.1 Public API / signatures

| Function | Signature | Notes |
|---|---|---|
| `load_ground_truth` | `(task_id: str, gt_dir=None) -> Dict` | default dir `ROOT/benchmark/ground_truth`; `FileNotFoundError` if missing |
| `gt_type` | `(gt: Mapping) -> str` | reads `"type"` or `"gt_type"` |
| `required_fields_for` | `(gtype: str) -> List[str]` | per-type required GT fields |
| `scorable_status` | `(gt, *, task_id="", scoring_dir=None) -> Dict` | returns `{scorable, gtype, mode, reason, missing_fields}`; modes: `deterministic`, `checklist`, `rubric_checklist`, `structured`, `unscorable` (no gt type / unknown type) |
| `grade_answer` | `(task_id, answer, *, gt=None, gt_dir=None, use_overlay=True) -> Dict` | the core entry point |
| `_checklist_score` | `(answer_text, elements) -> Dict` | private; normalized substring containment + token-level fallback for multi-word elements |

Type sets (module constants):
```python
DETERMINISTIC_TYPES = {"exact","categorical","ranked","numeric","set","constraint"}
RUBRIC_TYPES = {"design_rubric","mechanistic_rubric"}
STRUCTURED_TYPES = {"causal_graph","trajectory"}
SCORE_SCHEMA_VERSION = "1.0.0"
```

### 1.2 ScoreRecord shape (returned by `grade_answer`)

```json
{"schema_version": "1.0.0", "task_id", "gt_type", "method", "scorable",
 "score": float|null, "dimensions": {}, "evidence": [],
 "requires_expert_review": bool, "warnings": [], "errors": [],
 "status": "scored" | "requires_expert_review" | "unscorable_missing_fields"}
```

### 1.3 Scoring semantics per rubric type

- **exact** → `scoring.exact_score` (normalized string equality → 1.0/0.0); if only `mandatory_answer_elements` exist, falls back to `_checklist_score` (this is what produced the "method": "checklist" rows in the B1 pilots).
- **categorical / set / constraint** → `scoring.categorical_score`: coverage = present_mandatory / len(mandatory); `acceptable_alternatives` are exempted from "missing". Docstring claims a fabrication penalty ("no fabricated element appears") but the implementation only computes coverage — no fabrication term is actually applied (verified: no loop over extra tokens).
- **ranked** → string answers split on `[,\n;]`; `scoring.rank_score` = Spearman rank correlation transformed as `(ρ+1)/2` (so an empty-vs-empty mismatch yields floor 0.5 — see §6).
- **numeric** → float stripped of non-numeric chars, `|pred−exp| <= tolerance → 1.0`.
- **design_rubric / mechanistic_rubric** → `_checklist_score` on `mandatory_answer_elements`; **score is computed but status is `requires_expert_review`** and warning is appended: `"checklist coverage is automatic; rubric dimensions require blind expert review"`. `requires_expert_review=True`. Never silently treated as complete.
- **causal_graph** → `0.5*node_overlap + 0.5*edge_overlap` on sets.
- **trajectory** → `scoring.topk_agreement` on step ids.
- Unsupported/missing fields → `status="unscorable_missing_fields"`, `score=None` (never faked).

### 1.4 Overlays

`grade_answer` merges the authored GT with a self-derived overlay from
`benchmark/scoring/<task_id>.json` (`_load_overlay` / `_merge_overlay`), unless
`use_overlay=False` (used by `score_closed_48.py` to grade against reviewer-approved gold only). Overlay fills `mandatory_answer_elements`, `expected_value/set/ranking`, `tolerance`, `constraints`, `causal_graph`, `decision_trajectory` when the authored GT lacks them.

### 1.5 Deterministic sub-scoring (`benchmark_runner/scoring.py`, read fully)

- `exact_score(predicted, expected)`, `_norm(v)` (whitespace-collapse + lower)
- `categorical_score(predicted, expected_set, mandatory=None, alternatives=None)` → `{score, present, missing_mandatory, method:"categorical"}`
- `_rank(values)` competition (averaged) ranking; `rank_correlation` (Spearman, 4-decimal); `topk_agreement`; `rank_score` → `{spearman, score=(ρ+1)/2}`
- `score(gt_type, predicted, expected, **kw)` dispatch for exact/categorical/ranked; raises `ValueError` for rubric types.

---

## 2. `benchmark_runner/runner.py` (read fully, 260 lines)

Provider-independent adapters + `BenchmarkRunner`. **Fail-closed infrastructure**: production adapters raise unless `allow_real=True` (and even then only after freeze verification).

### 2.1 API

- `SYSTEM_IDS` = PROTACXtend, Biomni, AI-Co-Scientist-compatible, Base-LLM-control, DeepSeek-Flash-control, Local-Ollama-control, TPD-comparator.
- Exceptions: `AdapterError`, `AdapterTimeout`, `AdapterToolFailure`.
- `@dataclass TaskInput` — 15 fields; `TaskInput.from_case(case_path)` maps: `question` ← case `"scientific_question"`, `permitted_tools` ← `"permitted_tools_databases"`, `forbidden` ← `"forbidden_information"`, etc.; `to_run_dict()`.
- `SystemAdapter` (interface) / `_StubAdapter` (refuses real execution) / `DevFixtureAdapter` (only `DEV-*` tasks; refusals under SCIENTIFIC mode via `modes.FixtureUsageError`).
- `build_adapter(system_id, allow_real=False)` — `"DEV"` → fixture adapter; live systems (`_LIVE_SYSTEMS`) → `benchmark_runner.live.PROTACXtendLiveAdapter` / `AICoScientistLiveAdapter` / `BaseLLMLiveAdapter`, and `benchmark_runner.external.BiomniAdapter` / `TPDComparatorAdapter`; others → stub.
- `@dataclass RunConfig` — provider/model/version/seed/temperature/timeout_s/retries/`allow_real`/system_id/`mode` (default `ExecutionMode.SCIENTIFIC`).
- `BenchmarkRunner(config, benchmark_root, check_freeze=True)` — `run(task)`, `_execute_once(adapter, task, attempt)` (wall-clock timeout), `_envelope(...)`. Constructor calls `freeze.assert_frozen(root)` (fail closed on drift; freeze manifest `benchmark/FREEZE_MANIFEST.json`, version 2A.1, SHA-256 per frozen case/GT/protocol file — `benchmark_runner/freeze.py`).
- `run()` guards: `DEV` fixture adapter cannot run in SCIENTIFIC mode.
- `parse_case(path)`.
- **Result envelope** keys: `benchmark_envelope_version "1.0.0"`, `base_schema_version`, `status` (`ok`/`partial`/`failed`), `task_id`, `capability`, `system`, `workflow "KNOW-REASON-DESIGN-DISCOVER"`, `metadata` (run_id, attempts, fixture_only, execution_mode, frozen_at), provider/model/`provider_model_version`, **`answer`**, `summary`, `evidence`, `tools`, `artifacts`, `warnings`, `errors`, `provenance`, `run` (seed, temperature, repeat, tool_calls, runtime_s, tokens, api_cost_usd, blinded=True, timestamps), `raw_response` (always preserved), `scoring` (stub, None).

**The runner itself never persists files** — it returns a dict; persistence and per-case answer capture are done by orchestrator scripts (§5). The runner also has **no abstention concept**; abstention is implemented at the pilot/worker level.

---

## 3. B1 gold protocol files (repo root)

### 3.1 `gold_answers_v1.jsonl` — **48 records, exactly 48 lines** (`wc -l` = 48)

Note: the task brief said "72 lines seen" — the file is 48 logical JSONL records; the higher count was almost certainly an editor line-wrap artifact. 48 is also the count asserted by `benchmark/SCORABLE_MANIFEST.json` (`n_cases == n_ground_truth == 48`) and `tests/test_benchmark_grader.py::test_scorable_manifest_matches_ground_truth_count`.

Per-record schema (verified on every record):

| Field | Type | Notes |
|---|---|---|
| `case_id` | str | `DESIGN-01` … `REASON-12` |
| `capability` | str | DESIGN / DISCOVER / KNOW / REASON (12 each) |
| `split` | str | `development` (16) / `validation` (3) / `blind` (29) |
| `required_entities` | list[str] | e.g. `["component:warhead"]`, `["target:BRD4"]`, `["e3:CRBN","e3:VHL","target:BRD4"]`, `["none_declared"]` |
| `gold_answer_type` | str | `design_rubric` (20) / `categorical` (10) / `mechanistic_rubric` (9) / `exact` (5) / `ranked` (4) |
| `acceptable_answer` | str | empty (`""`) for all 48 |
| `proposed_answer_from_frozen_gt` | str | frozen expected-answer summary (see §4) |
| `mandatory_facts` | list[str] | e.g. `["5 valid SMILES","components preserved"]` (often empty) |
| `prohibited_claims` | list[str] | 8 canned honesty-claim strings (varies slightly by capability) |
| `expected_route` | list[str] | canonical node route (28 nodes for DESIGN-*; shorter for KNOW/REASON) |
| `expected_route_rationale` | str | `"Minimal dependency route: component retrieval is included only when the question/inputs require it; KNOW/REASON never run DESIGN/DISCOVER nodes."` |
| `expected_stop_state` | str | `valid_candidate (source-backed) OR design_brief OR justified_no_go` (DESIGN) / `conditional_hypothesis OR justified_no_go` (DISCOVER/REASON) / `supported_answer OR conditional_hypothesis OR justified_no_go` (KNOW) |
| `minimum_evidence` | dict | `{min_evidence_items, required_sources[], requires_chemical_validity}` |
| `acceptable_alternatives` | list | e.g. `["aliases: BRD4, HUNK1"]` for KNOW-01; otherwise empty |
| `expert_labels` | dict | `reviewer_1`, `reviewer_2` = `{decision, notes, reviewed_at}`; `adjudicator` = `{decision, notes, decided_at}` — **all empty for all 48** |
| `consensus_notes` / `status` | str | `AWAITING_EXPERT_REVIEW` for all 48 |
| `provenance` | dict | `{frozen_ground_truth: benchmark/ground_truth/<id>.json, case_file: benchmark/cases/<id>.json, schema: "gold_answers.v1", note: "Mechanical fields derived from inputs/router; scientific answer requires expert adjudication."}` |

### 3.2 `gold_adjudication_template.csv` — header + 48 rows

Flattened CSV mirror of the JSONL with `;`-joined `required_entities`, `>`-joined `expected_route`, `|`-joined `mandatory_facts`/`prohibited_claims`, and a `minimum_evidence` JSON-in-CSV cell. Adjudication columns (all **empty/PENDING** for every row):

```
reviewer_1_decision, reviewer_2_decision, adjudicator_decision,
consensus_notes, status
```
All rows: `consensus_notes=AWAITING_EXPERT_REVIEW`, `status=AWAITING_EXPERT_REVIEW`.

### 3.3 Reviewer/adjudicator fields — where they live

- `gold_answers_v1.jsonl` → `expert_labels.{reviewer_1,reviewer_2,adjudicator}` (per-case, empty).
- `gold_adjudication_template.csv` → flat `reviewer_1_decision`/`reviewer_2_decision`/`adjudicator_decision`.
- `benchmark/gateC/gold_review.tsv` (48 rows) → columns `reviewer_1, reviewer_2, verdict_1, verdict_2, adjudication_status, adjudicator, adjudication_date, notes`; **all `PENDING` / `PENDING_ADJUDICATION`**, adjudicator/date empty.
- `benchmark/gateC/REVIEWER_DECISIONS.json` → `status: "PENDING_ALL"`, `n_decisions: 29` (29 expert-review cases' slots, none filled).
- `benchmark/gateC/reviewed_gold/` → contains only `consensus.template.json` + `README.md`; **`consensus.json` does NOT exist** (so `scripts/score_closed_48.py` will currently write a `pending_adjudication` record).
- The adjudication packet mirrors the same fields: `docs/architecture/adjudication_packet/sheets/<ID>_BLINDED.md` has `reviewer_1/reviewer_2/adjudication` blanks; `docs/architecture/adjudication_packet/key/<ID>_KEY.json` has `"status": "PENDING_ADJUDICATION"`.

### 3.4 What "matched case" means

A gold case is **"matched" to a BRD4×CRBN vertical slice** when its
`required_entities` (machine-visible, from `gold_answers_v1.jsonl`) reference
BRD4 (`target:BRD4`), CRBN (`e3:CRBN`), PROTAC-component inputs
(`component:warhead` / `component:e3_ligand`), or when the case supplies
candidate/feature-table design inputs (`supplied_inputs` in
`benchmark/cases/<id>.json`). Per the task brief, `DESIGN-*` and `KNOW-09`
count regardless. Note that in the gold file, DISCOVER-* all declare
`required_entities=["none_declared"]`, so their "matched" status rests on the
supplied-table inputs (see §4 table; DISCOVER-01..12 all receive a candidate /
feature CSV or metrics table in `supplied_inputs`).

### 3.5 Full 48-case table (extracted via python from `gold_answers_v1.jsonl`)

```
case_id|capability|split|required_entities|gold_answer_type
DESIGN-01|DESIGN|development|component:e3_ligand;component:warhead|design_rubric
DESIGN-02|DESIGN|development|component:e3_ligand;component:warhead|design_rubric
DESIGN-03|DESIGN|validation|component:warhead|design_rubric
DESIGN-04|DESIGN|blind|e3:CRBN;e3:VHL;target:BRD4|design_rubric
DESIGN-05|DESIGN|blind|component:e3_ligand;component:warhead|design_rubric
DESIGN-06|DESIGN|development|component:warhead|design_rubric
DESIGN-07|DESIGN|blind|none_declared|design_rubric
DESIGN-08|DESIGN|development|target:BRD4|design_rubric
DESIGN-09|DESIGN|blind|none_declared|design_rubric
DESIGN-10|DESIGN|validation|target:BRD4|design_rubric
DESIGN-11|DESIGN|development|none_declared|design_rubric
DESIGN-12|DESIGN|development|component:warhead|design_rubric
DISCOVER-01|DISCOVER|blind|none_declared|ranked
DISCOVER-02|DISCOVER|blind|none_declared|design_rubric
DISCOVER-03|DISCOVER|blind|none_declared|design_rubric
DISCOVER-04|DISCOVER|blind|none_declared|ranked
DISCOVER-05|DISCOVER|blind|none_declared|design_rubric
DISCOVER-06|DISCOVER|blind|none_declared|design_rubric
DISCOVER-07|DISCOVER|blind|none_declared|design_rubric
DISCOVER-08|DISCOVER|blind|none_declared|ranked
DISCOVER-09|DISCOVER|blind|none_declared|design_rubric
DISCOVER-10|DISCOVER|blind|none_declared|design_rubric
DISCOVER-11|DISCOVER|blind|none_declared|ranked
DISCOVER-12|DISCOVER|blind|none_declared|design_rubric
KNOW-01|KNOW|blind|target:BRD4|exact
KNOW-02|KNOW|blind|component:warhead;target:BRD4|categorical
KNOW-03|KNOW|blind|none_declared|exact
KNOW-04|KNOW|development|target:BRD4|categorical
KNOW-05|KNOW|blind|target:BRD4|categorical
KNOW-06|KNOW|blind|component:warhead|categorical
KNOW-07|KNOW|validation|e3:VHL;target:BRD4|exact
KNOW-08|KNOW|blind|none_declared|categorical
KNOW-09|KNOW|blind|none_declared|exact
KNOW-10|KNOW|blind|e3:CRBN;target:BRD4|categorical
KNOW-11|KNOW|development|none_declared|exact
KNOW-12|KNOW|blind|none_declared|categorical
REASON-01|REASON|blind|none_declared|mechanistic_rubric
REASON-02|REASON|blind|none_declared|mechanistic_rubric
REASON-03|REASON|development|none_declared|categorical
REASON-04|REASON|development|none_declared|mechanistic_rubric
REASON-05|REASON|development|none_declared|categorical
REASON-06|REASON|development|e3:VHL|mechanistic_rubric
REASON-07|REASON|blind|none_declared|categorical
REASON-08|REASON|development|none_declared|mechanistic_rubric
REASON-09|REASON|development|target:BRD4|mechanistic_rubric
REASON-10|REASON|development|none_declared|mechanistic_rubric
REASON-11|REASON|blind|none_declared|mechanistic_rubric
REASON-12|REASON|development|none_declared|mechanistic_rubric
```
Counts: 48 total · 12/capability · blind 29 / development 16 / validation 3 ·
design_rubric 20 / categorical 10 / mechanistic_rubric 9 / exact 5 / ranked 4 ·
status 48×AWAITING_EXPERT_REVIEW.

---

## 4. Matched BRD4×CRBN vertical-slice cases — questions + frozen GT answers

Question text read from `benchmark/cases/<id>.json` field `scientific_question`;
GT summary from `gold_answers_v1.jsonl.proposed_answer_from_frozen_gt`.

### 4.1 Strict matched list (32 cases)

By the brief's rule: `required_entities` contains BRD4/CRBN/component/candidate
OR supplied-table design input, plus KNOW-09 and all DESIGN-*:

**DESIGN (12, all matched):**

| id | Question (verbatim from case file) | Frozen GT answer summary |
|---|---|---|
| DESIGN-01 | "Design 5 linkers bridging the supplied warhead and VHL ligand at a defined exit vector." | "Rubric + exact checks: 5 candidates, each RDKit-parseable PROTAC SMILES containing warhead+VHL motifs; none reuses the six-BRD4 measured potency." |
| DESIGN-02 | "Construct and validate a full PROTAC SMILES from the supplied components." | "At least one RDKit-valid full SMILES containing both components; report MW/logP/TPSA from the validator." |
| DESIGN-03 | "Propose 2 scaffolds replacing the supplied warhead while keeping the dimethylisoxazole acetyl-lysine mimic." | "Two distinct core scaffolds each containing a dimethylisoxazole-type mimic; rationale for preserved contacts; no measured potency claims." |
| DESIGN-04 | "Design a panel exploring E3-ligand variation for the supplied target context." | "Panel covering both E3s with >=2 ligand variants each; identity of E3 per arm explicit." |
| DESIGN-05 | "Design 3 candidates satisfying supplied property constraints (MW<=700, logP<=6, TPSA<=160, HBD<=4)." | "3 candidates each passing ALL constraints as computed by the permitted RDKit validator." |
| DESIGN-06 | "Design a series of 3 PROTACs varying ONLY at the solvent-exposed vector of the warhead." | "3 molecules sharing identical binding pharmacophore; variation confined to the vector region." |
| DESIGN-07 | "Design a dilution series plus controls to expose a suspected hook effect." | "Rubric: broad log dilution range, no-treatment + vehicle + positive controls, replicates; states endpoint and analysis." |
| DESIGN-08 | "Design a library biased toward ternary-feasible linkers for BRD4-VHL." | "Library with linker length/rigidity ranges consistent with 5T35 span; feasibility rationale per linker class." |
| DESIGN-09 | "Design 3 candidates passing a Tanimoto novelty cutoff vs the supplied reference set." | "3 valid candidates each with Tanimoto <0.6 to the reference (computed via permitted fingerprint tool)." |
| DESIGN-10 | "Design a BET-family selective series given BRD4 vs BRD2 as off-target context." | "Series with rationale addressing BRD4 vs BRD2 selectivity; explicitly flags that selectivity claims need assay data." |
| DESIGN-11 | "Design molecules whose predicted Dmax band is high under the supplied degradation model." | "Candidates with reported predicted Dmax band from the model; separates predicted from measured." |
| DESIGN-12 | "Design a negative-control PROTAC sharing the scaffold but with an inactive warhead." | "One control: same linker+E3 ligand, warhead pharmacophore ablated (e.g., remove dimethylisoxazole methyls or block pocket contact); explicit ablation rationale." |

**DISCOVER (12, all matched via supplied-table inputs; `required_entities=none_declared`):**

| id | Question | Frozen GT answer summary |
|---|---|---|
| DISCOVER-01 | "Rank the supplied 6 blinded candidates using the supplied numeric feature table and a locked rule." | "Deterministic ranking produced by applying the locked rule to the supplied table; ranking recorded before outcome access." |
| DISCOVER-02 | "Triage supplied candidates by stated uncertainty before committing experiments." | "Rubric: candidates with high uncertainty routed to confirmatory assays first; confidence never invented beyond supplied values." |
| DISCOVER-03 | "Recommend assays and controls to test the top hypothesis, with cost estimate." | "Rubric: concrete assay list with controls (vehicle, no-treatment, positive control) and cost band; no fabricated results." |
| DISCOVER-04 | "Select a 2-candidate portfolio balancing predicted degradation, ADMET, novelty from supplied metrics." | "Portfolio on Pareto front of supplied metrics; ties resolved by locked rule (prefer admet_pass)." |
| DISCOVER-05 | "Plan dose-response experiments to estimate hook-effect parameters for the top candidate." | "Rubric: log-dilution grid, replicates, controls, parameter-fit plan (hill + hook term); no fabricated constants." |
| DISCOVER-06 | "Recommend a cell line plus rationale for the supplied target/E3 context." (inputs: BRD4/CRBN degrader evaluation; MM1.S/H1299/HEK293T) | "Rubric: rationale based on expression + assay tractability; explicitly flags that per-line expression should be verified." |
| DISCOVER-07 | "Design an experiment that would falsify the supplied mechanistic claim." (CRBN-dependent degradation) | "Rubric: CRBN-knockout/competition (pomalidomide rescue) + vehicle/control design that yields a clear falsification criterion." |
| DISCOVER-08 | "Prioritise 3 candidates under a fixed experiment budget from supplied per-candidate assay costs." | "Priority set by locked rule (max value within budget, greedy by value/cost); no hidden data." |
| DISCOVER-09 | "State replication and controls for a supplied wet-lab result claim." (candidate degrades BRD4 …) | "Rubric: biological replicates, independent repeats, orthogonal readout, controls; identifies what would confirm/refute." |
| DISCOVER-10 | "Report what evidence is missing before a design decision is safe." | "Rubric: lists missing evidence (measured degradation, ternary, permeability, viability) and ranks their importance." |
| DISCOVER-11 | "Lock ranking protocol and criteria before outcome access for a supplied blinded set." | "A pre-registration record: rule string, criteria, seed, sign-off; ranking is locked, not run." |
| DISCOVER-12 | "Resolve two supplied model disagreements with a decision rule plus a test." | "Rubric: states tie-break rule based on applicability/confidence fields (only supplied), and an experiment that discriminates." |

**KNOW (7):**

| id | Question | Frozen GT answer summary |
|---|---|---|
| KNOW-01 | "Which UniProt ID and bromodomain architecture correspond to the supplied gene name BRD4?" | "UniProt O60885; bromodomain-containing protein 4; two bromodomains (BD1, BD2) + extraterminal (ET) domain" |
| KNOW-02 | "List the top experimentally validated BRD4 bromodomain binders for the supplied warhead context with source identifiers." | "At least two canonical BET inhibitors from {JQ1, I-BET762 (GSK525762), OTX015} each with a resolvable DB identifier/citation; no fabricated affinity values." |
| KNOW-04 | "Identify documented BRD4 degraders and the E3 ligase each recruits, using permitted databases." | "At least {dBET1, dBET6, ARV-825 (CRBN); MZ1, AT1 (VHL)} with correct E3 assignments and citations." |
| KNOW-05 | "Summarize which E3 ligases recur among documented BRD4 degraders and which ligands are used." | "CRBN (pomalidomide/lenalidomide-type ligands: dBET1/dBET6/ARV-825) and VHL (VH032-type: MZ1, AT1) both recur." |
| KNOW-07 | "Find structural evidence of a BRD4-VHL ternary complex and report the PDB identifier." | "PDB 5T35 (BRD4 BD2-MZ1-VHL ternary complex)." |
| KNOW-09 | "Map the supplied SMILES to its canonical SMILES, InChIKey, and molecular formula/MW." (SMILES CC(=O)Nc1ccc(O)cc1) | "Canonical SMILES CC(=O)Nc1ccc(O)cc1; InChIKey RZVAJINKPMORJF-UHFFFAOYSA-N; MW 151.16 Da (formula C8H9NO2)." |
| KNOW-10 | "Which of the supplied cell lines express the supplied target-E3 pair according to permitted sources?" (BRD4/CRBN) | "BRD4 and CRBN are broadly expressed; report per-line abundance evidence if a permitted source provides it, otherwise state 'no per-line quantitative evidence found' rather than guessing." |

**REASON (1):**

| id | Question | Frozen GT answer summary |
|---|---|---|
| REASON-09 | "Assess which BRD4 lysines are plausibly ubiquitination-accessible in a ternary complex." (5T35) | "Rubric: reason from structure about solvent-exposed lysines on the BRD4 surface; mark as hypothesis needing experimental ubiquitination assay; never assert measured ubiquitination sites." |

### 4.2 Near-matched / borderline (BRD4-flavoured but not BRD4/CRBN in `required_entities`)

| id | Why near-matched (from `supplied_inputs`) | Frozen GT answer summary |
|---|---|---|
| REASON-02 | pair BRD4 BD2 + VHL, PEG3 (MZ1-like) | "Rubric: uses known cooperative ternary evidence (5T35) without asserting alpha>1 from memory; states needed measured alpha and how to obtain it." |
| REASON-06 | VHL ligand (VH032 family, MZ1-derived); e3:VHL entity | "Rubric: ligand->VHL->ternary->ubiquitination geometry chain; notes structural uncertainty; no fabrication." |
| REASON-07 | compound A JQ1 (BET inhibitor) vs B MZ1 (BET degrader) | "Rubric: A inhibits (no E3 ligand); B recruits VHL and targets BRD4 for degradation; distinguishes claimed mechanism from potency." |
| REASON-08 | pose: MZ1 ternary (5T35) as structural reference | "Rubric: attachment must point into solvent from the acetyl-lysine binding face; uses 5T35-derived reasoning; no unsupported vectors." |
| KNOW-11 | claim: dBET1 promotes ubiquitination/degradation of BRD4 via CRBN | "DOI 10.1126/science.aab1433 (Winter et al., Science 2015)." |
| KNOW-06 | BET bromodomain acetyl-lysine pocket, dimethylisoxazole warhead family | "JQ1, I-BET762, OTX015, I-BET151 are documented dimethylisoxazole-family BET ligands (BD-selective differences may be noted)." |

Strict matched = 32 (DESIGN 12 + DISCOVER 12 + KNOW 7 {01,02,04,05,07,09,10} + REASON 1 {09}); strict + near-matched = 38; the remaining 10 cases are non-BRD4 slices (statement audits, generic ligands, linker/ADMET reasoning, VH032 SAR without a target): KNOW-03, KNOW-08, KNOW-12, REASON-01 (hook-effect equilibria), REASON-03, REASON-04, REASON-05, REASON-10, REASON-11, REASON-12.

---

## 5. Existing adjudication runs / results and recorded commands

### 5.1 `outputs/benchmark_run_b1/` (B1 artifacts, all present)

- `run.log` — ends with `tasks=13 scored=13 mean_score=0.1923` and `report: outputs/benchmark_run_b1/pilot_deterministic_20260924T185544Z.json`. (That stdout line format belongs to `scripts/run_benchmark_pilot.py` — so the 18:55:44 pilot was produced by that script; the exact argv is not recorded anywhere.)
- `summary.json` — `{"files":5,"n_executed":12,"mean":0.1875,"correct":4,"wilson95":[0.138,0.609],"per_capability":{"DISCOVER":{"n":2,"mean":0.5},"KNOW":{"n":8,"mean":0.156},"REASON":{"n":2,"mean":0.0}},"abstained":["KNOW-09","KNOW-10","KNOW-11","KNOW-12","REASON-07","DISCOVER-08","DISCOVER-11"]}`
  - Abstained (7) + executed rows (12) = 19 ⇒ this summary corresponds to the **19-task objective-gold B1 run** described in CHANGELOG (below), NOT to either retained pilot JSON (4 and 13 tasks). The aggregator script that built `summary.json` / `results_aggregate.csv` / `figures/fig_b1_*` is **not present in the repo** (grep for `results_aggregate`, `fig_b1`, `wilson95` finds only CHANGELOG + artifacts).
- `results_aggregate.csv` — header `task,capability,score,status,latency_s,file`; 12 rows: DISCOVER-01 (0.5), DISCOVER-04 (0.5), KNOW-01 (0.5), KNOW-02 (0.0), KNOW-03 (0.75), KNOW-04 (0.0), KNOW-05 (0.0), KNOW-06 (0.0), KNOW-07 (0.0), KNOW-08 (0.0), REASON-03 (0.0), REASON-05 (0.0). All tagged `file=pilot_deterministic_20260924T183508Z.json`.
  - ⚠ Provenance loose: that referenced pilot file contains only the **4-case** before-repair run (see below), so the CSV's `file` column does not actually reproduce its own 12 rows. Manual/one-off assembly.
- `pilot_deterministic_20260924T183845Z.json` — 4 tasks (KNOW-06, REASON-03, REASON-05, …), n=4, n_scored=4, mean=0.0 → the **before-repair** four-case numbers.
- `pilot_deterministic_20260924T185544Z.json` — 13 tasks, n_scored=13, mean=0.1923 (includes DISCOVER-04/08/11, KNOW-06..12, REASON-03/05 …); per-row `score.status` records show the checklist-based grading, e.g. KNOW-09 scored 1.0 here while listed as "abstained" in summary.json (different run composition).
- `figures/fig_b1_per_task.png/svg`, `fig_b1_by_capability.*`, `fig_b1_funnel.*`.

### 5.2 CHANGELOG (line 1138, 2026-09-24) — the authoritative B1 narrative

> "B1 benchmark (frozen 19-task objective gold): 12 tasks executed end-to-end via the real bridge/planner routing (KNOW-01..08, REASON-03/05, DISCOVER-01/04; latest-run dedup), 7 abstained (protocol: excluded from mean). Results: mean 0.188; correct(>=0.5) 4/12 Wilson95 [0.138,0.609]; per-capability KNOW 0.156 (n=8), REASON 0.000 (n=2), DISCOVER 0.500 (n=2). Honest negative: the deterministic engine is design-oriented and under-scores KNOW/REASON (LLM path required). Gold remains PENDING_HUMAN; machinery-only. Artifacts: outputs/benchmark_run_b1/{results_aggregate.csv, summary.json, figures/fig_b1_*}."

Also CHANGELOG (same day): "Ran this session: freeze integrity OK; fresh deterministic pilot KNOW-06/REASON-03/REASON-05/DISCOVER-04 → 0.0/0.0/0.0/0.5 (mean 0.125, real execution, machinery-graded)".

### 5.3 `docs/architecture/` — repair report, traces, adjudication packet

- `docs/architecture/BENCHMARK_REPAIR_REPORT.md` — four-case before/after table (KNOW-06 0.0→abstained; REASON-03 0.0→0.0 grounded rubric-incomplete; REASON-05 0.0→abstained; DISCOVER-04 0.5 unchanged), baselines table (empty answer 0.0/0.0/0.0/**0.5** — the ranked checklist floor, see §6), 6 hash-unstable DESIGN cases audit, per-case failure table, and **verbatim reproduction commands** (§7 of that report):
  ```
  python scripts/trace_four_case_pilot.py before node && python scripts/trace_four_case_pilot.py before pilot
  python scripts/trace_four_case_pilot.py after  node && python scripts/trace_four_case_pilot.py after  pilot
  # after-repair single run:
  python scripts/run_benchmark_pilot.py --engine deterministic --tasks KNOW-06,REASON-03,REASON-05,DISCOVER-04 \
    --out-dir docs/architecture/benchmark_run_after
  ```
- `docs/architecture/benchmark_run/pilot_deterministic_20260924T183508Z.json` — the 4-case BEFORE pilot (KNOW-06 0.0, REASON-03 0.0, REASON-05 0.0, DISCOVER-04 0.5; mean 0.125).
- `docs/architecture/benchmark_traces/four_case_{before,after}.json` — node+pilot traces.
- `docs/architecture/adjudication_packet/` — `README.md`, `INDEX.json` (48 items, all `status: PENDING_ADJUDICATION`; `machine_after`/`abstained` populated only for DISCOVER-04 (0.5/False), REASON-03 (0.0/False), KNOW-06 (null/True), REASON-05 (null/True)), `sheets/<TASK>_BLINDED.md` (48; no GT inside; reviewer blanks), `key/<TASK>_KEY.json` (48; expected_answer + mandatory_answer_elements + evidence_sources + `"status": "PENDING_ADJUDICATION"`).
- `docs/architecture/BENCHMARK_VERIFICATION.md` — counts table (48 cases/48 GT; SCORABLE_MANIFEST 48/48 auto + 29 expert + 0 not-scorable; gateC gold 48×PENDING_ADJUDICATION) + "the KNOW/REASON route requires the matched retrieval/LLM path (`todo/` P1, `tpdeval` P0.4)".

### 5.4 Scripts that call `benchmark_runner.grader` (all read/listed)

- `scripts/run_benchmark_pilot.py` — `grade_answer(case["task_id"], answer)` per case; `--offline-smoke` grades authored GT answers; outputs `benchmark_results/pilots/pilot_<engine>_<stamp>.json`.
- `scripts/run_baseline_comparison.py` — grades `baseline.run(...).to_dict()["answer"]`; usage `python scripts/run_baseline_comparison.py --limit 8`, `--systems retrieval-only,tool-only`, `--include-protacxtend --tasks DESIGN-01,KNOW-01`; outputs `benchmark_results/baselines/baseline_comparison_<stamp>.{json,md}`.
- `scripts/trace_four_case_pilot.py` — modes `node|pilot`, `--tag before|after`.
- `scripts/run_matched_benchmark.py` — per-task engine matrix; abstention semantics: "only system abstention is excluded from correctness means under the frozen protocol".
- `scripts/run_closed_48.py` — orchestrator; **header usage**: `python scripts/run_closed_48.py --workers 12`, `--arms direct_tool,fixed_workflow`, `--arms protacxtend --timeout-protacxtend 120`; per-arm timeouts `{"protacxtend":180,"direct_tool":60,"fixed_workflow":120}`; spawns `scripts/closed48_worker.py`.
- `scripts/closed48_worker.py` — writes one JSON per (case, arm) to `--out`; arms protacxtend / direct_tool / fixed_workflow; outcome `abstained` when stopping state is INSUFFICIENT EVIDENCE (seen in `benchmark_results/closed48/…/predictions.jsonl`: `REASON-06/protacxtend → outcome "abstained", stopping_state "INSUFFICIENT EVIDENCE"`).
- `scripts/score_closed_48.py` — grades `predictions.jsonl` (`case_id, capability, arm, answer, outcome`) against reviewer-approved gold `benchmark/gateC/reviewed_gold/consensus.json`; **without approval writes a `pending_adjudication` scores.json and exits 0**; input format documented in its docstring (`{"approved":true,"approved_by":[…],"adjudicator":"…","approved_at":"…","gold":{<case_id>:{"type","expected_answer","mandatory_answer_elements","acceptable_alternatives","answerability"}}}`). Abstention-correctness: for `answerability` ∈ {unanswerable,no_go,insufficient}, credit 1.0 iff observed outcome ∈ {abstained, refused, timeout}.
- `scripts/freeze_closed48.py`, `scripts/build_scorable_manifest.py` — freeze and manifest tooling using grader/scorable_status.
- `tests/test_benchmark_grader.py` — 9 tests; asserts rubric → `status=="requires_expert_review"` even at checklist score 1.0; `unscorable_missing_fields` not faked; 48 GT scorable via overlay; manifest 48/48.

### 5.5 Closed-48 execution artifacts

- `benchmark_results/closed48_v3/` — `results.jsonl` (144 run records: 48 cases × 3 seeds; includes `scientific_answer`, `answer`, `stopping_state`, `attachment_hypothesis`), `results_table.csv` (case_id, capability, n_seeds, states, verified counts, route_nodes, scientific_state_median), `reproducibility_results.csv` (state_stable 48, output_stable 42), `summary.json` (`states` distribution, `state_stable_cases: 48`, `output_stable_cases: 42`, `verified_candidates_total: 4`).
- `benchmark_results/closed48/closed48_locked/predictions.jsonl` — per-(case,arm,seed) rows with `score: null`, `scientific_conclusion: PENDING_INDEPENDENT_REVIEW`.
- `benchmark_results/gateC_pilot/…/predictions.jsonl` — pilot matches for 4 tool cases (PILOT-DISCOVER-08 etc.) with `matched_tool` fields.

---

## 6. Answer capture for grading + CI computation notes

### 6.1 Does grader accept an answer JSON per case?

Yes: `grade_answer(task_id, answer)` where `answer` may be any JSON-serializable value (str, dict, list). Non-str answers are flattened with `json.dumps(answer, default=str)` before scoring; for `ranked`, a list is used directly (string inputs are split on `[,\n;]`); for `causal_graph`/`trajectory`, `json.loads(answer_text)` is attempted.

There is **no grader-level file convention** — each orchestrator defines capture:
- `run_benchmark_pilot.py`: builds the answer string inline from the run result (`therapeutic_strategy` JSON + `scientific_answer` fields), grades immediately, writes `pilot_*.json`.
- `BenchmarkRunner._envelope`: the standardized run record carries `"answer"` + always-preserved `"raw_response"`; the `"scoring"` field is a None stub for callers to fill.
- `run_closed_48/score_closed_48`: `predictions.jsonl` rows with `answer` + `outcome` keys.
- B1 artifacts: `pilot_deterministic_*.json` (full ScoreRecords per task) + `results_aggregate.csv` (`task,capability,score,status,latency_s,file`) + `summary.json`.

### 6.2 Reproducible invocation surface (exact, from docs/scripts)

```bash
# pilot (documented in scripts/run_benchmark_pilot.py docstring):
python scripts/run_benchmark_pilot.py --offline-smoke
python scripts/run_benchmark_pilot.py --limit 3 --capability DESIGN
python scripts/run_benchmark_pilot.py --tasks DESIGN-01,KNOW-01
# four-case trace (documented in BENCHMARK_REPAIR_REPORT.md §7) — see §5.3
# baseline comparison (docstring): 
python scripts/run_baseline_comparison.py --limit 8
python scripts/run_baseline_comparison.py --include-protacxtend --tasks DESIGN-01,KNOW-01
# closed-48 (docstring of scripts/run_closed_48.py):
python scripts/run_closed_48.py --workers 12
python scripts/run_closed_48.py --arms protacxtend --timeout-protacxtend 120
# scoring behind approved gold (docstring of scripts/score_closed_48.py):
python scripts/score_closed_48.py --run-dir <run_dir> --gold benchmark/gateC/reviewed_gold/consensus.json
```
The exact argv that produced `outputs/benchmark_run_b1/pilot_*` is **not recorded**; only the stdout format (`tasks=N scored=N mean_score=…`, `report: …`) ties them to `scripts/run_benchmark_pilot.py`.

### 6.3 CI computation

- **Wilson interval function** (the only one in the repo): `protacxtend-memory/evaluation/analysis.py:37`
  ```python
  def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
      if n == 0:
          return 0.0, 0.0
      p = successes / n
      denom = 1 + z * z / n
      centre = (p + z * z / (2 * n)) / denom
      half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
      return max(0.0, centre - half), min(1.0, centre + half)
  ```
  Used by `system_aggregate()` for `decision_correct/repeated_error/provenance/contradiction_resolved` CIs (binomial success counts, no continuity correction).
- **B1 wilson95 verified**: `summary.json` `wilson95=[0.138, 0.609]` with `correct=4, n=12` matches exactly the formula above at z=1.96 (no continuity correction): computed [0.1381, 0.6093]. The B1 aggregator used the same Wilson math (per CHANGELOG "correct(>=0.5) 4/12 Wilson95").
- **Empty-answer baseline caveat (important)**: `BENCHMARK_REPAIR_REPORT.md §3` shows empty answer → KNOW-06 0.0, REASON-03 0.0, REASON-05 0.0, **DISCOVER-04 0.5**. The 0.5 floor is structural: `rank_score` maps an empty/mismatched predicted ranking to Spearman 0 → `(0+1)/2 = 0.5`. Any ranked case can therefore *pass* at 0.5 with an empty answer; this is the "ranked checklist floor" the report names. Categorical/exact/rubric empty answers score 0.0.
- **Closed-48 CI is NOT Wilson**: `scripts/score_closed_48.py::bootstrap_diff` uses a **paired bootstrap** (10,000 resamples, seed=42) over per-case score differences vs the baseline arm, grouped by capability, reporting `mean_diff` + `ci95` percentiles.
- Abstention handling in aggregates: abstained cases get `score=None` and are **excluded from means** (run_benchmark_pilot `n_abstained`, CHANGELOG "protocol: excluded from mean"); `score_closed_48` additionally rewards correct abstention on unanswerable gold.

---

## Coverage Status

**Checked directly (read in full):** `benchmark_runner/grader.py`, `benchmark_runner/runner.py`, `benchmark_runner/scoring.py`, `benchmark_runner/freeze.py` (first 80 lines), `benchmark_runner/matched_tools.py` (first 60 lines), `gold_answers_v1.jsonl` (all 48 records, also parsed programmatically), `gold_adjudication_template.csv` (all 49 lines), `outputs/benchmark_run_b1/*` (all artifacts), `docs/architecture/BENCHMARK_REPAIR_REPORT.md`, `docs/architecture/adjudication_packet/{README.md,INDEX.json}` + one sheet + one key, `docs/architecture/benchmark_run/pilot_deterministic_20260924T183508Z.json`, `scripts/run_benchmark_pilot.py`, `scripts/run_baseline_comparison.py`, `scripts/score_closed_48.py`, `scripts/trace_four_case_pilot.py` (head), `scripts/run_matched_benchmark.py` (head), `scripts/run_closed_48.py` (head), `scripts/closed48_worker.py` (head), `scripts/verify_report_traceability.py`, `tests/test_benchmark_grader.py`, `benchmark/gateC/gold_review.tsv` (head), `benchmark/gateC/REVIEWER_DECISIONS.json` (head), `benchmark_results/closed48_v3/*` (headers + summary), `benchmark_results/closed48/closed48_locked/predictions.jsonl` (sample rows), CHANGELOG entry 1138, all 48 `benchmark/cases/*.json` question/supplied_inputs fields.

**Interpreted, not directly recorded:** (a) the exact argv of the B1 pilot runs (stdout format in run.log implies `scripts/run_benchmark_pilot.py`; not verbatim anywhere); (b) the "matched case" criterion is my consolidation of the brief's rule applied to the gold schema — the repo does not contain an explicit "matched" flag; (c) why DISCOVER-08/DISCOVER-11 appear in summary.json's abstained list is not explained in any doc (KNOW/REASON relevance-gate abstention is documented; DISCOVER abstention is not).

**Explicitly absent:** `benchmark/gateC/reviewed_gold/consensus.json` (approved gold — does NOT exist); any committed generator for `results_aggregate.csv` / `summary.json` / `fig_b1_*` (not in repo); `gold_answers_v1.jsonl` is 48 lines, not 72.

**Not modified:** no files were written inside the repo tree; this memo lives in the subagent artifacts path.

---

## Evidence table

| # | Source | URL/path | Key claim | Type | Confidence |
|---|--------|----------|-----------|------|------------|
| 1 | benchmark_runner/grader.py | /storage/saveena/protacxtend/benchmark_runner/grader.py | Deterministic LLM-free scorer; 9 gt types; rubric types → checklist score + status requires_expert_review; unscorable never faked | primary | high |
| 2 | benchmark_runner/scoring.py | /storage/saveena/protacxtend/benchmark_runner/scoring.py | exact/categorical/ranked/numeric scoring math; rank_score=(ρ+1)/2 → empty-answer floor 0.5 | primary | high |
| 3 | benchmark_runner/runner.py | /storage/saveena/protacxtend/benchmark_runner/runner.py | TaskInput from case JSON; fail-closed adapters; BenchmarkRunner envelope (answer+raw_response); freeze assert | primary | high |
| 4 | benchmark_runner/freeze.py | /storage/saveena/protacxtend/benchmark_runner/freeze.py | SHA-256 freeze manifest v2A.1; fail-closed checks | primary | high |
| 5 | gold_answers_v1.jsonl | /storage/saveena/protacxtend/gold_answers_v1.jsonl | 48 records; schema incl. expert_labels/AWAITING_EXPERT_REVIEW; 48 lines (not 72) | primary | high |
| 6 | gold_adjudication_template.csv | /storage/saveena/protacxtend/gold_adjudication_template.csv | 48 rows; reviewer_1/2/adjudicator decision columns all empty | primary | high |
| 7 | outputs/benchmark_run_b1/summary.json | /storage/saveena/protacxtend/outputs/benchmark_run_b1/summary.json | B1 mean 0.1875, correct 4/12, wilson95 [0.138,0.609], 7 abstained | primary | high |
| 8 | outputs/benchmark_run_b1/results_aggregate.csv | /storage/saveena/protacxtend/outputs/benchmark_run_b1/results_aggregate.csv | 12 scored rows; file column references a 4-case pilot (loose provenance) | primary | medium |
| 9 | CHANGELOG.md:1138 | /storage/saveena/protacxtend/CHANGELOG.md | B1 narrative: 12 executed (KNOW-01..08, REASON-03/05, DISCOVER-01/04), 7 abstained, gold PENDING_HUMAN | secondary | high |
| 10 | docs/architecture/BENCHMARK_REPAIR_REPORT.md | /storage/saveena/protacxtend/docs/architecture/BENCHMARK_REPAIR_REPORT.md | before/after four-case pilot; empty-answer baseline 0.5 floor on ranked; verbatim repro commands | primary | high |
| 11 | docs/architecture/adjudication_packet/INDEX.json | /storage/saveena/protacxtend/docs/architecture/adjudication_packet/INDEX.json | 48 sheets PENDING_ADJUDICATION; machine_after only DISCOVER-04/REASON-03; abstained KNOW-06/REASON-05 | primary | high |
| 12 | docs/architecture/adjudication_packet/sheets/KNOW-09_BLINDED.md + key/KNOW-09_KEY.json | /storage/saveena/protacxtend/docs/architecture/adjudication_packet/ | blinded sheet w/ reviewer blanks; key w/ expected answer + evidence_sources, PENDING | primary | high |
| 13 | benchmark/gateC/gold_review.tsv | /storage/saveena/protacxtend/benchmark/gateC/gold_review.tsv | 48 rows all PENDING / PENDING_ADJUDICATION | primary | high |
| 14 | benchmark/gateC/reviewed_gold/ | /storage/saveena/protacxtend/benchmark/gateC/reviewed_gold/ | consensus.json ABSENT (only template+README) | primary | high |
| 15 | scripts/run_benchmark_pilot.py | /storage/saveena/protacxtend/scripts/run_benchmark_pilot.py | KNOW/REASON relevance-gate abstention; pilot JSON output format | primary | high |
| 16 | scripts/score_closed_48.py | /storage/saveena/protacxtend/scripts/score_closed_48.py | predictions.jsonl schema; needs approved gold; paired bootstrap seed 42 | primary | high |
| 17 | scripts/run_closed_48.py + closed48_worker.py | /storage/saveena/protacxtend/scripts/ | closed-48 orchestration; per-arm timeouts; abstained outcome on INSUFFICIENT EVIDENCE | primary | high |
| 18 | scripts/verify_report_traceability.py | /storage/saveena/protacxtend/scripts/verify_report_traceability.py | report/run/strategy traceability checks; unassessed-never-scored principle | primary | high |
| 19 | protacxtend-memory/evaluation/analysis.py | /storage/saveena/protacxtend/protacxtend-memory/evaluation/analysis.py | wilson_interval(successes,n,z=1.96); n=0 → (0,0) | primary | high |
| 20 | benchmark/cases/*.json (48) | /storage/saveena/protacxtend/benchmark/cases/ | per-case scientific_question + supplied_inputs (basis of matched-case table) | primary | high |
| 21 | benchmark_results/closed48_v3/* | /storage/saveena/protacxtend/benchmark_results/closed48_v3/ | 144 runs; state-stable 48/48, output-stable 42/48; scientific_answer shape | primary | high |
| 22 | tests/test_benchmark_grader.py | /storage/saveena/protacxtend/tests/test_benchmark_grader.py | grader contract tests incl. rubric-never-silent, manifest 48/48 | primary | high |
| 23 | docs/architecture/benchmark_run/pilot_deterministic_20260924T183508Z.json | /storage/saveena/protacxtend/docs/architecture/benchmark_run/ | 4-case before-repair pilot (mean 0.125) — referenced by results_aggregate.csv | primary | high |

## Sources (numbered, same as table)

1. `benchmark_runner/grader.py` — /storage/saveena/protacxtend/benchmark_runner/grader.py
2. `benchmark_runner/scoring.py` — /storage/saveena/protacxtend/benchmark_runner/scoring.py
3. `benchmark_runner/runner.py` — /storage/saveena/protacxtend/benchmark_runner/runner.py
4. `benchmark_runner/freeze.py` — /storage/saveena/protacxtend/benchmark_runner/freeze.py
5. `gold_answers_v1.jsonl` — /storage/saveena/protacxtend/gold_answers_v1.jsonl
6. `gold_adjudication_template.csv` — /storage/saveena/protacxtend/gold_adjudication_template.csv
7. `outputs/benchmark_run_b1/summary.json` — /storage/saveena/protacxtend/outputs/benchmark_run_b1/summary.json
8. `outputs/benchmark_run_b1/results_aggregate.csv` — /storage/saveena/protacxtend/outputs/benchmark_run_b1/results_aggregate.csv
9. `CHANGELOG.md` (line 1138) — /storage/saveena/protacxtend/CHANGELOG.md
10. `docs/architecture/BENCHMARK_REPAIR_REPORT.md` — /storage/saveena/protacxtend/docs/architecture/BENCHMARK_REPAIR_REPORT.md
11. `docs/architecture/adjudication_packet/INDEX.json` — /storage/saveena/protacxtend/docs/architecture/adjudication_packet/INDEX.json
12. `docs/architecture/adjudication_packet/sheets/KNOW-09_BLINDED.md`, `docs/architecture/adjudication_packet/key/KNOW-09_KEY.json` — /storage/saveena/protacxtend/docs/architecture/adjudication_packet/
13. `benchmark/gateC/gold_review.tsv` — /storage/saveena/protacxtend/benchmark/gateC/gold_review.tsv
14. `benchmark/gateC/reviewed_gold/` — /storage/saveena/protacxtend/benchmark/gateC/reviewed_gold/ (consensus.json absent)
15. `scripts/run_benchmark_pilot.py` — /storage/saveena/protacxtend/scripts/run_benchmark_pilot.py
16. `scripts/score_closed_48.py` — /storage/saveena/protacxtend/scripts/score_closed_48.py
17. `scripts/run_closed_48.py`, `scripts/closed48_worker.py` — /storage/saveena/protacxtend/scripts/
18. `scripts/verify_report_traceability.py` — /storage/saveena/protacxtend/scripts/verify_report_traceability.py
19. `protacxtend-memory/evaluation/analysis.py` — /storage/saveena/protacxtend/protacxtend-memory/evaluation/analysis.py
20. `benchmark/cases/*.json` — /storage/saveena/protacxtend/benchmark/cases/
21. `benchmark_results/closed48_v3/` — /storage/saveena/protacxtend/benchmark_results/closed48_v3/
22. `tests/test_benchmark_grader.py` — /storage/saveena/protacxtend/tests/test_benchmark_grader.py
23. `docs/architecture/benchmark_run/pilot_deterministic_20260924T183508Z.json` — /storage/saveena/protacxtend/docs/architecture/benchmark_run/