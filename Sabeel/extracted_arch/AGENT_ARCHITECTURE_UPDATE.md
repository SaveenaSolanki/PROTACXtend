# Agent Architecture Update — Nodes 5, 19, 20

Companion to [`AGENT_REASONING_AND_BENCHMARKS.md`](AGENT_REASONING_AND_BENCHMARKS.md) §2.2 and
[`SEARCH_INSTRUMENTATION.md`](SEARCH_INSTRUMENTATION.md). This document specifies the
architecture changes required by the three benchmark rows that are **not runnable today**.

| Row | Agent | Mode | Benchmark task | Blocker |
| --- | --- | --- | --- | --- |
| **5** | [TargetBinderRetrieval](05-TargetBinderRetrievalAgent.md) | C · retrieval | 10 targets with known chemotypes → recall @100, **true hit count before the cap** | ⚠️ needs the cap fix |
| **19** | [EvolutionRefinement](19-EvolutionRefinementAgent.md) | G · meta | 10 generations → `n_novel / n_produced`, best-score trajectory | ⚠️ needs the seen-set |
| **20** | [TernaryFeasibility](20-TernaryFeasibilityAgent.md) | E · geometry | proxy vs P4ward on the same 3,600 poses → calibration curve, AUC, rank agreement | ❌ blocked on **O-4** |

Eighteen of twenty-three nodes are gradeable this week. These three are the remainder, and
each is blocked by a *different* missing faculty — which is why they need an architecture
update rather than a test harness.

---

## Why these three, and what "more intelligent" means here

The agents do not deliberate; they apply deterministic rules ([`AGENT_REASONING_AND_BENCHMARKS.md`](AGENT_REASONING_AND_BENCHMARKS.md) §1.1).
So intelligence at this layer is not "better reasoning" — it is **an agent knowing three
things about its own work that it currently does not**:

| Faculty | The question it answers | Missing at |
| --- | --- | --- |
| **Evidence accounting** | *How much did I not look at?* | Node 5 — silently returns 100 of an unknown total |
| **Episodic memory** | *Where have I already been?* | Node 19 — no cross-generation seen-set, so it may revisit while appearing to explore |
| **Calibration** | *How wrong is my cheap answer?* | Node 20 — proxy has never been checked against the backend it approximates |

Each is also, exactly, the thing that makes the corresponding benchmark computable. This is
the recurring theme in [`00-INDEX.md`](00-INDEX.md): **the data exists, the reporting does
not.** Two of these three fixes are surfacing what the system already computes. The third
is running a job.

**Scope boundary.** Nothing here attempts objective **O-1** (a trained degradation model).
Node 19 will still optimise a heuristic fitness after this update — but it will *declare*
that it is doing so, which is the difference between a known limitation and a hidden one.

---

## 0 · Shared substrate — build once, all three consume

Three pieces belong in the toolbox layer, not in the agents. Agents stay thin (20–91 lines,
by design); the work lives in the toolbox it delegates to.

### 0.1 `ChemIdentity` — one canonical key

A single helper wrapping the existing `canonicalize_smiles` and `_stable_id`, returning a
canonical **InChIKey** for any molecule or component.

```
chem_identity(smiles) -> InChIKey        # full-molecule key
component_key(warhead, e3, linker, attach_pts) -> str   # coverage_cell key
```

Consumed by node 5 (structure-level dedup), node 19 (seen-set), node 20 (`coverage_cell`
primary key). Three agents currently need the same key and none of them share one.

**Correctness constraint:** the standard InChIKey first block collapses stereoisomers.
Nodes 10 and 11 already carry a stereo-preservation risk ([`00-INDEX.md`](00-INDEX.md),
cross-cutting observations); the seen-set and dedup must use the **full** InChIKey including
the stereo layer, or the GA will treat R and S as the same molecule and mark a genuinely new
candidate as revisited.

### 0.2 `RunLedger` — one writer for the observability tables

`funnel_step`, `loop_generation`, `coverage_cell` (schemas in
[`SEARCH_INSTRUMENTATION.md`](SEARCH_INSTRUMENTATION.md)) and `benchmark_result` (schema in
[`AGENT_REASONING_AND_BENCHMARKS.md`](AGENT_REASONING_AND_BENCHMARKS.md) §2.7) are written
from a single module, keyed on `run_id` + `config_hash`. Rejection reasons canonicalise
against the closed `failure_reason` enum at write time.

### 0.3 `AgentTrace` v2 — record the denominators

Today's trace is `thought / action / observation`: it records the path taken. Benchmarking
needs the paths not taken. Add three optional blocks, populated by any node that has them:

| Block | Fields | Why |
| --- | --- | --- |
| `denominators` | `n_considered`, `n_returned`, `n_truncated`, `truncation_rule` | Turns "100 binders" into "100 of 4,120, potency-ranked" |
| `policy` | `policy_id`, `source_node`, `params` | Makes node 2's decisions auditable — plan-vs-actual (benchmark row 2) |
| `cost` | `wall_ms`, `api_calls`, `compute_hours` | Rule 2 of §2.0 — no benchmark number without its cost |

### 0.4 Node 2 owns the new knobs

Every policy introduced below is **set by [DesignPlanner](02-DesignPlannerAgent.md) (node 2)
and read by the agent**, never hardcoded in the agent. Node 2 is already the policy engine
for the graph; adding these knobs there keeps them in one auditable place and closes part of
**O-7** in passing.

| Policy | Owner | Consumed by |
| --- | --- | --- |
| `binder_cap_policy` — `{cap, rank_by, min_assay_confidence}` | node 2 | node 5 |
| `evolution_policy` — `{max_generations, novelty_floor, patience, budget}` | node 2 | node 19 |
| `ternary_promotion` — `{mode, threshold, k, compute_hour_budget, sampling}` | node 2 | node 20 |

---

## 1 · Node 5 — from *a list* to *a census*

**Now.** Fan-out to ChEMBL, PubChem and BindingDB; dedup; return **up to 100**
`BinderRecord`s. The truncation is silent, dedup is string-level, and assay type is not
carried, so node 6 compares Ki against IC₅₀ against EC₅₀ as if they were one quantity.

**The architectural problem is ordering, not capping.** A cap is fine; a cap applied before
dedup and quality filtering is not, because the 100 records that survive are then "the first
100 the APIs happened to return".

### 1.1 Fixed pipeline order

```
per source: query ──▶ n_reported_total  (API's own total, recorded BEFORE any fetch)
                 ──▶ fetch (paged, rate-limited, cached)
merge all sources
  ──▶ dedup on full InChIKey            (ChemIdentity §0.1)     ──▶ n_after_dedup
  ──▶ assay-quality filter              (confidence, assay type) ──▶ n_after_quality
  ──▶ rank by declared rule             (potency within compatible assay type)
  ──▶ apply cap                         (from binder_cap_policy)  ──▶ n_returned
```

`n_reported_total` is the number the whole benchmark row turns on, and every one of the
three APIs returns it in the response envelope before the records themselves. It is
available today and discarded today.

### 1.2 New `RetrievalCensus` (one per source + one merged)

| Field | Type | Meaning |
| --- | --- | --- |
| `source` | `str` | `chembl` / `pubchem` / `bindingdb` |
| `query` | `str` | the exact query issued |
| `n_reported_total` | `int \| None` | API-reported hit count — `None` only if the source genuinely does not report one |
| `n_fetched` | `int` | records actually pulled |
| `n_after_dedup` | `int` | post-InChIKey merge |
| `n_after_quality` | `int` | post assay-confidence filter |
| `n_returned` | `int` | after the cap |
| `truncated` | `bool` | `n_returned < n_after_quality` |
| `selection_rule` | `str` | e.g. `potency_desc_within_assay_type` |
| `cache_hit` | `bool` | disk cache keyed on `uniprot_id + query_version` |

Written to `state.retrieval_census` **and** to `funnel_step` (node 5 row: `n_considered =
n_reported_total`, `n_in = n_fetched`, `n_out = n_returned`), which fills the top row of the
funnel that is currently blank.

### 1.3 `BinderRecord` extension

| Field | Why it is needed |
| --- | --- |
| `inchikey` | dedup key and the join key to every other table |
| `assay_type` | `Ki` / `IC50` / `Kd` / `EC50` — **not interchangeable** |
| `value`, `units`, `value_nm` | one normalised numeric column so ranking is possible at all |
| `p_activity` | from the existing `compute_p_activity` |
| `assay_confidence` | ChEMBL confidence score / source equivalent |
| `source`, `source_id` | provenance, already present — now paired with the identity key |
| `comparable_group` | assay types the potency rank may mix; node 6 refuses cross-group comparison |

### 1.4 Zero-hit and sparse-hit as first-class outcomes

`state.retrieval_status ∈ {ok, sparse, empty}`. On `empty`, the run does not proceed with a
silent empty list — it falls back to the 485K-row warhead seed database, records the
fallback in the trace, and node 22 reports it. `sparse` (below a configurable floor) carries
the same flag without changing behaviour.

### 1.5 What this unblocks

Benchmark row 5 becomes computable exactly as specified: **recall @100 against ChEMBL
chemotypes, reported beside the true hit count.** Without `n_reported_total` the recall
denominator does not exist, which is why the row is currently marked ⚠️.

**Acceptance:** for 10 targets, the census reports a non-null `n_reported_total` for at
least ChEMBL and BindingDB; `n_returned ≤ cap`; no InChIKey appears twice; every returned
record carries `assay_type` and `value_nm`; the node-5 `funnel_step` row is populated.

---

## 2 · Node 19 — from *a loop* to *a search with memory*

**Now.** 61 lines delegating to `toolbox.evolve_candidates()`. It owns the only cycle in the
graph (19 → 10). Population size, mutation rate, selection method, generation cap and
convergence criterion are undocumented, and no cross-generation deduplication is known to
exist. A GA with no memory and no stopping condition can rediscover the same molecules every
round while its best-score curve looks healthy.

### 2.1 `SeenSet` — the prerequisite everything else needs

Persistent, keyed on full InChIKey (§0.1), scoped to the `run_id` and optionally promoted
across runs by node 23 (`MemoryUpdateAgent`). Two operations, both O(1):

```
seen.contains(inchikey) -> bool
seen.add(inchikey, generation, parents, operator)
```

The toolbox already has `_stable_id` and `remove_duplicate_candidates`; the missing piece is
that neither *persists across generations*. That single change converts "novelty" from an
unmeasurable property into a counted one.

### 2.2 `GenerationRecord` — one row per generation

Maps 1:1 onto the `loop_generation` table already specified in
[`SEARCH_INSTRUMENTATION.md`](SEARCH_INSTRUMENTATION.md) Instrument 3:

| Field | Notes |
| --- | --- |
| `generation` | 1-indexed |
| `n_produced`, `n_novel` | `n_novel` = unseen InChIKey vs **all** prior generations, not just the previous one |
| `novelty_ratio` | `n_novel / n_produced` — the metric *and* the stop condition |
| `best_score`, `mean_score` | trajectory |
| `operator_counts` | `{mutation: n, recombination: n, linker_mutation: n, …}` |
| `fitness_spec_id` | which fitness was optimised — see §2.4 |

### 2.3 Termination policy — a correctness fix, not a refinement

Read from `evolution_policy` (node 2), enforced in node 19, recorded in the trace:

| Condition | Default | Rationale |
| --- | --- | --- |
| `max_generations` | 10 | Hard bound. Matches the benchmark's 10-generation run |
| `novelty_floor` | 0.10 | Stop when `novelty_ratio < floor` … |
| `patience` | 2 | … for this many consecutive generations |
| `budget` | wall-clock + candidate count | Backstop independent of the science |
| `plateau_delta` | best score improvement < ε | Optional early exit |

The novelty ratio being both the reported metric and the convergence criterion is the point:
the benchmark and the stop condition are the same number, so running the benchmark exercises
the mechanism it measures.

### 2.4 Declare the fitness

Add a `fitness_spec` — `{score_field, weights, config_hash, label_source}` — carried on every
`GenerationRecord`. Today the GA optimises `final_priority_score` from node 16, whose
dominant term is node 12's untrained `SynGlue-demo-heuristic-v0.1`. With `label_source =
'heuristic'` recorded, §2.0 Rule 1 becomes mechanically enforceable: a query filtering to
`label_source IN ('published','p4ward','rdkit')` will correctly exclude every
evolution-derived score from the admissible-evidence view.

This does not fix **O-1**. It stops the system from quietly presenting an O-1-dependent
number as a result.

### 2.5 Lineage and operator weighting

- **Lineage.** Each refined candidate carries `parent_ids` and `operator_applied`. Without
  it the report cannot explain where a top candidate came from, which undercuts the
  provenance claim the whole pipeline rests on.
- **Linker-biased mutation.** The project's own headline result is that three linker atoms
  flip the degraded target from p38α to p38δ. Uniform mutation across warhead / E3 / linker
  spends most of the budget on the axes that matter least. Make the operator weights explicit
  in `evolution_policy` and default them toward the linker.

### 2.6 What this unblocks

Benchmark row 19 exactly as specified: **10 generations, `n_novel / n_produced` per
generation, best-score trajectory.** A curve decaying toward zero then reads as convergence
rather than as an unanswerable question.

**Acceptance:** a 10-generation run writes 10 `loop_generation` rows; `n_novel` is strictly
computed against all prior generations; the loop terminates by a *recorded* condition;
every candidate in generation *n* > 1 carries parents and an operator.

---

## 3 · Node 20 — from *two backends* to *a calibrated two-tier screen*

**Now.** 597-line agent, 1,200-line wrapper, both **never executed in production**. The
geometric proxy (< 1 s) and P4ward (2–4 h) differ by four orders of magnitude in cost, and
nobody knows how the proxy's 0–1 score maps onto real pose pass rates.

**The blocker is execution, not code** — that is objective **O-4** and it costs an afternoon
of compute. The architecture work below is what makes that afternoon produce a *reusable
calibration* rather than a single anecdote.

### 3.1 Sample for a curve, not for a winner

This is the most consequential item in this document and the easiest one to get wrong.

Running P4ward on the single best candidate (A1_4COOH) proves the wrapper works and yields
**one** calibration point. One point cannot produce a calibration curve, an AUC, or a rank
agreement — which is to say it does not satisfy benchmark row 20.

| Goal | Candidates | Compute | Produces |
| --- | --- | --- | --- |
| Prove the wrapper runs end to end | 1 (A1_4COOH) | 2–4 h | O-4 closed; wrapper validated |
| Fit a calibration curve | **8–12, stratified across the proxy-score range** | 16–48 h | Curve, Spearman ρ, AUC |
| Rank agreement | same 8–12 | — | Whether the cheap tier orders the same as the expensive one |

Set `ternary_promotion.sampling = 'stratified_by_proxy_decile'` for the calibration run,
**not** `top_k`. A top-k sample has no low-proxy examples in it, so it cannot tell you
whether a low proxy score means a low pass rate — which is the only question the two-tier
design depends on. The case study already supplies two free anchor points at opposite ends:
ICM OH27 at **0/3,600** and A1_4COOH at **8–16/3,600**.

### 3.2 Explicit promotion policy

Which candidates graduate from the < 1 s tier to the 2–4 h tier is the most expensive
decision in the pipeline and is currently implicit. `ternary_promotion` makes it a budgeted
policy set by node 2: `{mode: threshold|top_k|stratified, threshold, k, compute_hour_budget,
sampling}` — recorded in the trace's `policy` block, so plan-vs-actual replay can check that
the run did what the plan said.

### 3.3 Checkpointing and resumability

A 2–4 h Docker run that dies at hour three with nothing on disk is an expensive failure, and
a 16–48 h calibration campaign makes it a likely one. `p4ward_wrapper.py` persists per-batch
pose results and a resume token; a partial run yields a partial pass rate (`n_passed /
n_poses_completed`) that is still usable and still honest.

### 3.4 Pass rates are the output format

`0/3,600`, `8–16/3,600`, `0.8% for C14-PEG5` are the most interpretable numbers the project
has produced. Standardise on `{n_passed, n_poses, pass_rate}` as the primary result, with the
proxy's 0–1 score as a secondary field, and write both into `coverage_cell.best_pass_rate` /
`best_proxy_score` so the coverage heatmap fills in from real runs.

### 3.5 `CalibrationRecord` — the artifact the run exists to produce

| Field | Source |
| --- | --- |
| `candidate_inchikey` | node 11 |
| `proxy_score` | `ternary_feasibility.py` |
| `p4ward_pass_rate`, `n_passed`, `n_poses` | `p4ward_wrapper.py` |
| `plddt_min`, `plddt_mean` | node 4 — see §3.7 |
| `compute_hours`, `wall_ms` | Rule 2 |
| `label_source` | `'p4ward'` — admissible evidence under §2.0 Rule 1 |

Persisted as `benchmark_result` rows. Once ≥ 8 exist, the calibration curve, Spearman ρ and
AUC are a query rather than a project.

### 3.6 The one new edge in the graph: 20 → 12′

Node 12 predicts degradation **before** node 20 computes whether a ternary complex can form
at all, and never sees the result. Bondeson 2018 — cited in the project's own analysis — says
ternary formation predicts degradation better than binary affinity does. Node 21 re-ranks
with ternary data, but the DC₅₀ estimate itself is never revised.

Two options, and the second is the recommendation:

| Option | Change | Cost |
| --- | --- | --- |
| A · Reorder | Move node 12 after node 20 | Forces every run through the ternary branch, which is optional by design. **Rejected.** |
| B · Second pass | Add `12′` after node 20, consuming `ternary_feasibility_results`, writing a revised estimate that node 21 consumes | One conditional node; the graph stays linear when ternary is skipped. **Recommended.** |

Under option B the original node-12 estimate is retained alongside the revised one, so the
delta between them is itself a measurement of how much ternary data moves the prediction —
which is a free ablation of exactly the kind §2.4 of the benchmark doc asks for.

### 3.7 Structure-quality gate

A ternary result computed on a low-confidence AlphaFold region is not meaningful. Carry
pLDDT through from node 4 onto the candidate, and have node 20 refuse or flag runs whose
binding site falls below a threshold. Spending 2–4 hours of compute on a poorly-predicted
pocket is the most expensive avoidable error in the system.

### 3.8 What this unblocks

Benchmark row 20 becomes computable once the stratified campaign completes: **calibration
curve, AUC, rank agreement** — and item 10 of the benchmark implementation order (proxy-vs-
P4ward calibration) stops being blocked.

**Acceptance:** ≥ 8 `CalibrationRecord`s spanning the proxy-score range; every one carries
compute-hours and pLDDT; a run killed mid-flight resumes without repeating completed batches;
`coverage_cell` rows exist for every evaluated combination.

---

## 4 · Graph delta

```
BEFORE
  4 ──▶ 5 ──▶ 6 … 10 ──▶ 11 ──▶ 12 ──▶ … ──▶ 16 ──▶ 18 ──▶ 19 ──┐
                                                                 │
       (silent 100-cap)          (unvalidated heuristic)          │
                    10 ◀────────────────────────────────────────┘
                                     (no memory, no bound)
       11 ──▶ 20 (optional, never run) ──▶ 21

AFTER
  4 ──▶ 5 ──▶ … ──▶ 19 ──┐        5  emits RetrievalCensus  ──▶ funnel_step
       │                  │        19 emits GenerationRecord ──▶ loop_generation
       │      10 ◀────────┘        19 bounded by evolution_policy + SeenSet
       │           (bounded)
       11 ──▶ 20 ──▶ 12′ ──▶ 21    20 emits CalibrationRecord ──▶ benchmark_result
                                   20 gated by ternary_promotion + pLDDT
```

One new node (`12′`, conditional on the ternary branch running). No renumbering. No node
becomes non-deterministic.

---

## 5 · Before → after

**What is being compared.** No accuracy figure appears below, and none can until the
benchmarks run — that is the point of the update. What changes is *what the agent can be
graded on at all*: a denominator that exists, a novelty count that exists, a calibration
axis that exists. An agent that cannot be measured cannot be improved, and cannot be
defended to a reviewer.

### 5.1 Benchmark rows runnable

```
                    0        5        10       15       20   23
before  18 / 23     ████████████████████████████████████░░░░░░
                                                        ▲ 5  ▲ 19  ▲ 20
after   21 / 23     ██████████████████████████████████████████░
```

The three rows this document addresses are the whole gap between the two bars.

### 5.2 Per-node scoreboard

| | **Before** | **After** | **Downstream effect** |
| --- | --- | --- | --- |
| **5** Binders | "100 binders retrieved" | "100 of *N*, potency-ranked within assay type, InChIKey-unique" | Node 6 stops comparing Ki against IC₅₀; recall @100 acquires a denominator |
| | dedup on SMILES string | dedup on full InChIKey | The same molecule from 3 sources stops counting as 3 |
| | cap applied first | cap applied last | The 100 kept are the best 100, not the first 100 |
| | empty result → silent | `retrieval_status = empty` → seed-DB fallback, reported | A novel target no longer produces a confident-looking empty run |
| **19** Evolution | unbounded | terminates on a *recorded* condition | The only cycle in the graph can no longer run away |
| | novelty unmeasurable | `n_novel / n_produced` per generation | Convergence becomes a number instead of a hope |
| | no lineage | `parent_ids` + `operator_applied` | The report can say where a top candidate came from |
| | fitness undeclared | `fitness_spec.label_source = 'heuristic'` | Rule 1 filtering becomes mechanical, not remembered |
| **20** Ternary | proxy score 0–1, uncalibrated | pass rate + fitted curve vs P4ward | The promotion threshold becomes evidence-based |
| | 1,800 lines unproven | wrapper validated, resumable | A 48 h campaign survives a crash at hour 40 |
| | node 12 never sees ternary | `12′` revises the estimate | Bondeson 2018 finally reaches the DC₅₀ number |

### 5.3 Node 5 — the funnel's top row

```
node                     considered      in     out   truncated   selection rule
─────────────────────────────────────────────────────────────────────────────────────
05  get binders  before           —       —     100   unknown     unstated
    (same query) after        4,120     400     100   yes         potency_desc_within_assay_type
─────────────────────────────────────────────────────────────────────────────────────
```

`4,120` is illustrative; the number itself is what the fix recovers. Today the entire top
row of the run funnel reads `—`, so every count below it is a fraction of an unknown.

### 5.4 Node 19 — why the best-score curve cannot tell you the loop is working

Two hypothetical 10-generation runs. **A** explores; **B** rediscovers the same molecules
under different names.

```
best_score              A  ▁▃▅▆▇▇████    ← the only signal the system emits today
(observable now)        B  ▁▃▅▆▇▇████    ← identical. Both read as steady progress.

novelty_ratio           A  █████▇▆▅▅▄    0.95 → 0.38   exploring; keep going
(observable after)      B  ████▄▂▁▁▁▁    0.95 → 0.04   revisiting; should have stopped at gen 4
                           └┬─┬─┬─┬─┬┘
                            1 3 5 7 9  generation
```

The top panel is what a reviewer is shown today, and A and B are indistinguishable in it.
The bottom panel is one persisted set of InChIKeys away, and it is simultaneously the
benchmark metric and the missing convergence criterion.

### 5.5 Node 20 — the calibration plane

```
BEFORE                                      AFTER  (8–12 stratified runs)

p4ward pass rate                            p4ward pass rate
  /3,600                                      /3,600
   16 ┤   ?    ?    ?    ?                      16 ┤              ●
      │                                            │         ●
    8 ┤   ?    ?    ?    ●  A1_4COOH             8 ┤      ●  ●
      │                                            │   ●
    0 ┤   ●    ?    ?    ?  ICM OH27             0 ┤●  ●
      └───┬────┬────┬────┬                        └───┬────┬────┬────┬
        0.25 0.50 0.75 1.0                          0.25 0.50 0.75 1.0
              proxy score                                 proxy score

 2 anchor points, neither run through            curve ⇒ Spearman ρ, AUC,
 the wrapper, both at the extremes               an evidence-based promotion threshold
```

The left panel is why `top_k` sampling fails: it would add points only on the right-hand
side, and the question the two-tier design rests on — *does a low proxy score really mean a
low pass rate?* — lives on the left.

### 5.6 The one thing that does not improve

Node 19's fitness is still node 12's untrained heuristic after this update, so the GA still
climbs the same hill. What changes is that the hill is now *labelled* — and §5.4 makes it
visible whether the climb is real. Fixing the hill itself is **O-1**, and it is out of
scope here.

### 5.7 One trace, before and after

The trace is what a reviewer, a benchmark and the learning store all read. Node 5, same
query, same 100 records returned:

```jsonc
// BEFORE
{ "node": 5,
  "thought":     "retrieve known binders for HMGB2",
  "action":      "chembl_lookup + pubchem_lookup + bindingdb_lookup",
  "observation": "retrieved 100 binders" }

// AFTER
{ "node": 5,
  "thought":     "retrieve known binders for HMGB2 (UniProt P26583)",
  "action":      "chembl_lookup + pubchem_lookup + bindingdb_lookup",
  "observation": "returned 100 binders",
  "denominators": { "n_considered": 4120, "n_fetched": 400, "n_after_dedup": 337,
                    "n_after_quality": 288, "n_returned": 100, "n_truncated": 188,
                    "truncation_rule": "potency_desc_within_assay_type" },
  "policy":       { "policy_id": "binder_cap_policy@v1", "source_node": 2,
                    "params": { "cap": 100, "rank_by": "p_activity",
                                "min_assay_confidence": 7 } },
  "cost":         { "wall_ms": 8412, "api_calls": 14, "compute_hours": 0.0 } }
```

Same work, same output, same runtime. The `observation` line is the only part that exists
today, and it is the one part that cannot be graded, replayed or budgeted against.

### 5.8 Failure behaviour — what the agent does when reality is awkward

The dominant failure mode across the system is that **nothing raises when a rule is simply
wrong for the input**. This is where "more intelligent" is most visible: the after column is
not a better answer, it is a *refusal to give a confident wrong one*.

| Situation | Before | After |
| --- | --- | --- |
| Novel target, 0 binders in all 3 databases | Empty list flows on; node 6 selects from curated only; report reads normally | `retrieval_status = empty` → seed-DB fallback, flagged in trace and report |
| ChEMBL reports 4,120 hits | First 100 kept; report says "100 binders" | 288 survive quality filtering, best 100 kept by potency, `n_truncated = 188` recorded |
| Same compound in ChEMBL, PubChem and BindingDB under 3 SMILES spellings | Counted 3×; skews node 6's potency fusion | Merged on full InChIKey; source list preserved on one record |
| GA converges at generation 3 | Runs to whatever bound exists; generations 4–10 re-emit known molecules as "refined candidates" | `novelty_ratio < 0.10` for 2 generations → terminates, reason recorded |
| GA proposes a combination already evaluated in a prior run | No memory; re-evaluated | `coverage_cell` hit → skipped or deprioritised (a $5K–$50K, 2–6 week evaluation avoided) |
| P4ward crashes at hour 40 of a 48 h campaign | Nothing on disk; start over | Resume token + per-batch results; partial pass rate still usable |
| Binding site sits in a pLDDT ≈ 55 AlphaFold region | 2–4 h of docking on an unreliable pocket, result reported at face value | pLDDT gate refuses or flags before the compute is spent |

### 5.9 Questions the system can answer about its own run

| Question | Before | After | Answered by |
| --- | --- | --- | --- |
| How many known binders exist for this target? | ✗ | ✓ | `RetrievalCensus.n_reported_total` |
| Are these the *best* 100 or the *first* 100? | ✗ | ✓ | `selection_rule` |
| Did the search explore, or churn? | ✗ | ✓ | `loop_generation.novelty_ratio` |
| Where did the top candidate come from? | ✗ | ✓ | `parent_ids` + `operator_applied` |
| Have we already tried this warhead × E3 × linker? | ✗ | ✓ | `coverage_cell` lookup |
| What fraction of the design space did we touch? | ✗ | ✓ | coverage matrix — 192 / ~11,600 = **1.6%** |
| Does a low proxy score mean a low pass rate? | ✗ | ✓ | calibration curve (§5.5) |
| What did this number cost to produce? | ✗ | ✓ | `trace.cost` |
| Is the DC₅₀ estimate trained or heuristic? | ✗ | ✓ | `fitness_spec.label_source` |
| Is the degradation model right? | ✗ | ✗ | **O-1** — still open |

Nine of ten move. The tenth is the one this update explicitly does not touch, and saying so
plainly is worth more than a tenth ✓ that is not earned.

### 5.10 The coverage map

```
BEFORE — what the ranked candidate table implies      AFTER — what coverage_cell shows

  E3 →   CRBN  VHL  cIAP MDM2                          E3 →   CRBN  VHL  cIAP MDM2
 W ┌────┬────┬────┬────┐                              W ┌────┬────┬────┬────┐
 A │    │    │    │    │   "the pipeline searched      A │▓▓▓▓│    │    │    │   192 evaluated
 R │    │    │    │    │    warhead × E3 × linker      R │    │    │    │    │   in ONE cell;
 H │    │    │    │    │    space and ranked the       H │    │    │    │    │   55 cells never
 E │    │    │    │    │    output"                    E │    │    │    │    │   touched
 A │    │    │    │    │                              A │    │    │    │    │
 D └────┴────┴────┴────┘   (no denominator anywhere)  D └────┴────┴────┴────┘   1.6% of curated
                                                                                  ~0.13% of real
```

Dense in one cell, empty in the other fifty-five — **that is the finding**, and a ranked
candidate list conceals it. Note the discipline carried over from
[`SEARCH_INSTRUMENTATION.md`](SEARCH_INSTRUMENTATION.md): until **O-4** lands, populate
`best_proxy_score` and leave `best_pass_rate` **NULL** rather than filling it from an
uncalibrated number. A coverage map built on the proxy would be a record of what the
placeholder believes.

### 5.11 What the report is able to say

Node 22 reads the entire state and is the system's whole user interface: a caveat that does
not reach it does not exist as far as the reader is concerned. These three sentences are
unavailable today for the same reason — the field they would quote is never written.

| Before (what the report can say) | After (what it can say instead) |
| --- | --- |
| "100 known binders were retrieved for the target." | "100 of 4,120 reported binders were retained — deduplicated on InChIKey, filtered to assay confidence ≥ 7, ranked by potency within comparable assay types. 188 qualifying binders were not evaluated." |
| "The evolution loop refined the candidate set." | "The loop ran 6 of a maximum 10 generations and terminated on the novelty criterion (ratio 0.04 for 2 consecutive generations). Candidate 3 descends from generation-2 candidate 11 by linker mutation." |
| "Ternary feasibility score: 0.72." | "Proxy score 0.72 → predicted pass rate 6–11 / 3,600 (calibration n = 10, ρ = —). Measured: 9 / 3,600. Compute: 3.1 h." |

The third row is the shape of the claim that objective **O-4** exists to make possible; the
first two need no new data at all.

### 5.12 What becomes measurable downstream

The three fixes are prerequisites for work that is currently specified but not interpretable:

| Downstream item | Blocked before because… | Enabled after by |
| --- | --- | --- |
| **B-4 ablation: one-shot vs evolution loop** | "The loop helped" is unfalsifiable if you cannot tell exploration from revisiting | `novelty_ratio` + `loop_generation` |
| **B-4 ablation: node 12 → constant** | Rank churn is readable, but not *why* the ranking moved | Lineage + `fitness_spec` |
| **B-5 counterfactual sweep** (Instrument 4) | Sweep results have nowhere to accumulate | `coverage_cell` keyed on InChIKey |
| **Exhaustive-scan baseline at equal compute** | "Equal compute" is unmeasurable without cost accounting | `trace.cost` (Rule 2) |
| **Learning store records** | Observations are self-reported and unvalidated | A `funnel_step` row with a dominant `failure_reason`, and a `benchmark_result` with `passed = false`, are records with `validation_status = 'validated'`, `validated_by = 'benchmark'` |
| **O-5g active learning** | A surrogate model needs a training set of measured outcomes | Sweep response curves + calibrated pass rates |

**The through-line.** None of the three agents gets a new capability in this update. Node 5
runs the same three queries, node 19 runs the same operators, node 20 runs the same two
backends. What changes is that each one stops discarding the record of what it did — and
that record is simultaneously the benchmark, the stop condition, the caveat in the report
and the training data for what comes next.

---

## 6 · State contract additions

| Field | Type | Writer | Readers |
| --- | --- | --- | --- |
| `state.retrieval_census` | `list[RetrievalCensus]` | 5 | 22, RunLedger |
| `state.retrieval_status` | `enum{ok,sparse,empty}` | 5 | 6, 22 |
| `BinderRecord.inchikey / assay_type / value_nm / assay_confidence / comparable_group` | — | 5 | 6, 14 |
| `state.seen_inchikeys` | `set[str]` (persisted) | 19 | 19, 23 |
| `state.generation_records` | `list[GenerationRecord]` | 19 | 22, RunLedger |
| `state.fitness_spec` | `FitnessSpec` | 2 / 16 | 19, 22 |
| `CandidateRecord.parent_ids / operator_applied / generation` | — | 19 | 22 |
| `state.calibration_records` | `list[CalibrationRecord]` | 20 | 12′, 21, 22 |
| `state.revised_degradation` | `list[DegradationPrediction]` | 12′ | 21, 22 |
| `AgentTrace.denominators / policy / cost` | — | all | 22, RunLedger |

Every field is append-only, consistent with the existing `WorkflowState` model.

---

## 7 · Sequencing

Ranked by value per unit of effort, consistent with the orders in
[`00-INDEX.md`](00-INDEX.md) and [`SEARCH_INSTRUMENTATION.md`](SEARCH_INSTRUMENTATION.md).

| # | Change | Node | Effort | Unblocks |
| --- | --- | --- | --- | --- |
| 1 | `ChemIdentity` + full-InChIKey helper | toolbox | Small | Nodes 5, 19, 20 all need it |
| 2 | Record `n_reported_total`; reorder dedup → filter → rank → cap | 5 | Small | **Benchmark row 5** |
| 3 | `AgentTrace` v2 `denominators` block | base | Small | Funnel top row; row 2 plan-vs-actual |
| 4 | `SeenSet` + `GenerationRecord` + termination policy | 19 | Medium | **Benchmark row 19**, Instrument 3 |
| 5 | Extend `BinderRecord` with assay type and units | 5 | Medium | Node 6 potency comparison correctness |
| 6 | `ternary_promotion` policy + checkpointing | 20 | Medium | Makes the O-4 campaign survivable |
| 7 | **Run the stratified P4ward campaign (O-4)** | 20 | 16–48 h compute, no code | **Benchmark row 20** |
| 8 | `12′` second degradation pass | new | Medium | Bondeson feedback; free ablation |
| 9 | Publish node 19 in `AGENT_API.md` | docs | Small | **O-7** |

Items 1–4 are a week and convert two ⚠️ rows to ✅. Item 7 is the long pole and is compute,
not engineering — but item 6 should land first, because a 48-hour campaign without
checkpointing is one crash away from starting over.

---

## 8 · What deliberately does not change

- **No deliberation loop.** Determinism is the project's strongest evaluation property
  (§1.1). Nothing here adds a model call to a node that does not have one.
- **Agents stay thin.** All new machinery lands in the toolbox; the agents gain fields and
  policy reads, not logic.
- **No new predictive science.** O-1, O-2 and the O-5 series are out of scope. Node 19 will
  still climb a heuristic hill after this update — it will simply say so in a field that
  Rule 1 can filter on.
- **No renumbering.** Node 12′ is additive and conditional.

---

## 9 · Done means

- [ ] Node 5 reports `n_reported_total` for ≥ 2 of 3 sources on all 10 benchmark targets, and no InChIKey appears twice in `retrieved_binders`.
- [ ] The node-5 row of the run funnel shows `considered` instead of `—`.
- [ ] A 10-generation node-19 run writes 10 `loop_generation` rows with a strictly computed `n_novel`, and terminates by a recorded condition.
- [ ] Every generation-*n* candidate carries `parent_ids` and `operator_applied`.
- [ ] ≥ 8 `CalibrationRecord`s exist, stratified across the proxy-score range, each with compute-hours and pLDDT.
- [ ] `coverage_cell` is populated from real runs, not backfilled estimates.
- [ ] Node 19 has an `AGENT_API.md` entry stating its reads, writes and loop contract.

---

## Provenance note

Field, method and file names above are taken from the agent documents in this directory
(`05-`, `19-`, `20-`, `SEARCH_INSTRUMENTATION.md`, `AGENT_REASONING_AND_BENCHMARKS.md`,
`../MY_Objectives.md`) — this workspace contains documentation only, not the
`synglue_agent` source tree. Reconcile the exact names against the source before
implementation; the architecture and the ordering constraints hold regardless of naming.
