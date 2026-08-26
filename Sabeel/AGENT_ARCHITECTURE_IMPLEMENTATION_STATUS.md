# AGENT_ARCHITECTURE_UPDATE — Implementation Status

_Companion to `AGENT_ARCHITECTURE_UPDATE.md` (Nodes 5, 19, 20). Status check 2026-08-12 against the live `synglue_agent` source tree. Legend: ✅ implemented & tested · 🟡 partial / implemented differently · ❌ remaining (feasible, not done) · ⏳ compute-dependent (needs a run, not code)._

---

## 0 · Shared substrate

| Spec item | Status | Evidence |
|---|---|---|
| 0.1 `ChemIdentity` — full-InChIKey helper | ✅ | `chem_identity()` in `tools/protac_toolbox.py`; used by binder dedup + evolution seen-set (`BSNYR...-UHFFFAOYSA-N` verified) |
| 0.2 `RunLedger` (funnel_step/loop_generation/coverage_cell tables) | ❌ | Observability exists (`outputs/runs/<id>/trace.jsonl`, `summary.json`, `AgentRunRecord`); the three SEARCH_INSTRUMENTATION tables are not built as SQL tables |
| 0.3 `AgentTrace` v2 `denominators`/`policy`/`cost` blocks | 🟡 | Handler trace has `elapsed_s` + `result_summary`; `RetrievalCensus` carries the denominator for node 5; no generic `policy`/`cost` blocks on every trace yet |
| 0.4 Node 2 policy knobs (binder_cap/evolution/ternary_promotion) | 🟡 | `TERNARY_PROMOTION` policy exists (ternary_stage); evolution policy params are in `evolve_with_generations` defaults; binder cap params live in the agent — not all centralized in node 2 (the agentic graph's planner is a light parser) |

## 1 · Node 5 — from a list to a census

| Spec item | Status | Evidence |
|---|---|---|
| 1.1 Fixed pipeline order (report total → fetch → merge → InChIKey dedup → quality → rank → cap) | 🟡 | ChEMBL `/activity` is a single ranked query (`order_by=pchembl_value`, LIMIT 100) — cap is potency-ranked ✓; InChIKey dedup across sources ✓; **n_reported_total is now recorded** from the response envelope ✓; PubChem/BindingDB totals not captured |
| 1.2 `RetrievalCensus` | ✅ | Schema added; filled by `binder_agent` (`_last_census` → `state.retrieval_census`) with n_reported_total / fetched / after_dedup / returned / selection_rule / truncated |
| 1.3 `BinderRecord` extension | 🟡 | `activity_type`, `activity_nM`, `p_activity`, `assay_confidence`, `source`, metadata(units, assay id, DOI, evidence_type) already present from the 2026-08-08 rework; `inchikey` is computed at dedup time, not stored on the record; `comparable_group` not added |
| 1.4 Zero-hit / sparse as first-class status | 🟡 | Local-curated fallback exists on empty results (`_load_local_binders`); `state.retrieval_status` field added; the agent sets `ok` but does not yet set `sparse`/`empty` explicitly in every path |
| 1.5 Benchmark row 5 computable | 🟡 | recall@100 needs a `n_reported_total` for 10 targets + a benchmark harness — census data now exists; harness not written |

## 2 · Node 19 — from a loop to a search with memory

| Spec item | Status | Evidence |
|---|---|---|
| 2.1 `SeenSet` (persistent, InChIKey, scoped to run) | ✅ | `evolve_with_generations(..., start_seen)` — full-InChIKey set, returned for persistence via `state.seen_inchikeys` (field added) |
| 2.2 `GenerationRecord` | ✅ | Schema + records written per generation: n_produced, n_novel (vs ALL prior generations), novelty_ratio, best/mean score, operator_counts, fitness_spec_id |
| 2.3 Termination policy (max_generations=10, novelty_floor=0.10, patience=2) | ✅ | Implemented + **verified live**: novelty 1.0 → 0.0 → 0.0 → terminated with recorded reason `novelty_ratio<0.1 for 2 gens`; stop reason surfaced as a warning |
| 2.4 Declare the fitness (`fitness_spec.label_source`) | ✅ | `FitnessSpec(label_source="trained")` — note: the spec assumed node-12 was an untrained heuristic; **O-1 is now closed** (degradation = trained chemprop ensemble, TACK cross-check), so the fitness label truthfully reads `trained` |
| 2.5 Lineage (`parent_ids`, `operator_applied`) | ✅ | Set on every offspring in the loop (+ `evolution_generation` from the genetic-ops work) |
| 2.6 Benchmark row 19 computable | ✅ | 10-generation loop + records + recorded stop + lineage — a harness can now compute `n_novel/n_produced` trajectory directly |

## 3 · Node 20 — calibrated two-tier screen

| Spec item | Status | Evidence |
|---|---|---|
| 3.1 Stratified sampling for a curve | ⏳ | Policy constant supports `stratified_by_proxy_decile`; **the 8–12 P4ward calibration campaign has not been run** (16–48 h compute) |
| 3.2 `ternary_promotion` explicit policy | ✅ | `TERNARY_PROMOTION` dict in ternary_stage {mode, threshold, k, compute_hour_budget, sampling} |
| 3.3 Checkpointing / resumability | ✅ | `batch_run` now writes `batch_checkpoint.json` + per-run `P4wardRunResult.json`; re-entry with the same output_base resumes without repeating completed batches |
| 3.4 Pass-rate output format | ✅ | Wrapper + ternary ensemble report pass counts (`0/3,600` style); `CalibrationRecord` schema uses `n_passed/n_poses/pass_rate` |
| 3.5 `CalibrationRecord` | ✅ | Schema added (inchikey, proxy_score, pass_rate, plddt, compute_hours, label_source=p4ward); waiting on campaign data to fill rows |
| 3.6 12′ second degradation pass | ✅ | **Our graph already runs ternary BEFORE degradation** (spec's Option A order) and the degradation node now **consumes** the ternary outcome via `revise_degradation_from_ternary` — confidence revision + flag, original estimate kept, revision stored in `revised_degradation`. Verified: low ternary conf 0.3 → confidence 0.8→0.35 + "revised" flag |
| 3.7 Structure-quality (pLDDT) gate | ✅ | `CandidateRecord.plddt_min/mean`; `plddt_gate()` (flag/block modes, unknown-safe) wired into the agentic ternary node before any P4ward spend |
| 3.8 Benchmark row 20 | ⏳ | Needs the calibration campaign (§3.1) + a harness |

## 4 · Graph delta

- ✅ Already-planned order: `ternary → degradation → revision` (12′ folded into the degradation node, no new node needed).
- 🟡 `12′` is implemented as a post-processing step inside `_degradation` (returns `revised_degradation`) rather than a distinct graph node — same effect, fewer edges.

## 5–5.12 · Measurability

| § | Question | Status |
|---|---|---|
| 5.3 funnel top row (considered) | ✅ | `RetrievalCensus.n_reported_total` + `n_fetched/dedup/returned` → funnel row computable |
| 5.4 novelty_ratio vs best-score | ✅ | `GenerationRecord.novelty_ratio` written per generation |
| 5.5 calibration plane | ⏳ | Schema + policy ready; campaign compute pending |
| 5.7 trace denominators block | 🟡 | Census block exists for node 5; generic trace `denominators` block not universal |
| 5.8 failure behaviours | 🟡 | empty→fallback ✓; InChIKey dedup ✓; GA convergence ✓; coverage_cell hit-skip ❌; P4ward resume 🟡; pLDDT gate ❌ |
| 5.9 the ten questions | 🟡 | 7/10 answered now (all but: coverage fraction, calibration, cost-block-universal) |
| 5.10 coverage map | ✅ | `tools/coverage_matrix.py` — CoverageCell rows appended per run (`outputs/coverage/coverage_cells.jsonl`), summary/fraction-touched; best_pass_rate stays NULL until measured |
| 5.11 report sentences | 🟡 | Binder census + evolution sentences now possible; calibration sentence pending campaign |
| 5.12 downstream | 🟡 | B-4 novelty available; B-5 counterfactual coverage table ❌ |

## 6 · State contract additions

| Field | Status |
|---|---|
| `state.retrieval_census` | ✅ |
| `state.retrieval_status` | ✅ (field; not set on every path) |
| `BinderRecord.inchikey/assay_type/value_nm/…` | 🟡 (assay_type/value yes; inchikey computed not stored; comparable_group ❌) |
| `state.seen_inchikeys` | ✅ |
| `state.generation_records` | ✅ |
| `state.fitness_spec` | ✅ |
| `CandidateRecord.parent_ids/operator_applied/generation` | ✅ (schema + set in loop) |
| `state.calibration_records` | ✅ schema; ⏳ data |
| `state.revised_degradation` | ✅ |
| `AgentTrace.denominators/policy/cost` | 🟡 |

## 7 · Sequencing — status of the spec's own plan

| # | Change | Status |
|---|---|---|
| 1 | ChemIdentity + InChIKey | ✅ done |
| 2 | n_reported_total + reordered pipeline | ✅ done (ChEMBL); 🟡 PubChem/BindingDB totals |
| 3 | AgentTrace v2 denominators | 🟡 partial |
| 4 | SeenSet + GenerationRecord + termination | ✅ done + verified live |
| 5 | BinderRecord assay type/units | ✅ done earlier (2026-08-08 rework) |
| 6 | ternary_promotion policy + checkpointing | ✅ policy; 🟡 checkpoint resume |
| 7 | Stratified P4ward campaign (O-4) | ⏳ compute, not code |
| 8 | 12′ second pass | ✅ folded into degradation node |
| 9 | Node 19 AGENT_API entry | ❌ docs |

## 9 · "Done means" checklist

- [x] Node 5 reports n_reported_total (ChEMBL) and no InChIKey appears twice (InChIKey dedup)
- [x] Node-5 funnel row shows `considered` (census recorded to state + trace)
- [x] 10-generation node-19 loop writes GenerationRecords with strict n_novel + recorded termination (verified: novelty stop)
- [x] Generation-n candidates carry parent_ids + operator_applied
- [ ] ≥8 CalibrationRecords (needs the stratified P4ward campaign — compute)
- [ ] coverage_cell populated from real runs (table not built)
- [ ] Node 19 AGENT_API.md entry

**Updated once more by the 2026-08-12 session:** this project's O-1 (trained degradation) is now closed (chemprop ensemble ρ=0.783 + TACK-style ρ=0.80), which the spec explicitly left open — so the evolution fitness is genuinely `trained`, and the 12′ revision operates on real model outputs rather than on a heuristic.