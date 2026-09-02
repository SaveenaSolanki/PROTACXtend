# 12 · DegradationPredictionAgent

| | |
| --- | --- |
| **Node** | 12 — `predict_degradation` |
| **Source** | `synglue_agent/agents/prediction_agent.py` (shared with node 15) |
| **Size** | 39 lines agent + `degradation_predictor.py` (56 lines) |
| **Status** | ✅ **Built (v0.3)** — trained Chemprop D-MPNN ensemble (ρ=0.783, conformal 92.2%) + SynGlue transformer fallback |
| **Model ID** | `SynGlue-demo-heuristic-v0.1` |
| **Objective** | **O-1** |

## Architecture brief

This agent answers the question the entire system exists to answer: *will this molecule
actually degrade the target, and at what concentration?* It predicts DC₅₀, D<sub>max</sub>
and a degradation probability.

It answers it with rules.

The model identifier is candid — `SynGlue-demo-heuristic-v0.1` — and the underlying
predictor is 56 lines. There is no trained model, no featurisation pipeline and no
validation set. Every other node in the pipeline is doing real work: real API calls, real
RDKit chemistry, real geometric computation. This node is a placeholder sitting in the
most important position in the graph.

**The consequence is systemic, not local.** Node 16 ranks on this output and node 21
re-ranks on it. Node 18 critiques evidence strength using it. The final ranked candidate
list — the system's actual deliverable — is ordered primarily by a heuristic. A pipeline
that is 18/23 rigorous produces an output whose ordering rests on its weakest component.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.valid_candidates` | `list[CandidateRecord]` | node 11 |
| `state.target_record` | `TargetRecord` | node 4 |
| `state.parsed_objective` | `ParsedObjective` | node 1 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.degradation_predictions` | `list[DegradationPrediction]` | DC₅₀, D<sub>max</sub>, degradation probability |

Toolbox methods: `predict_degradation`, and downstream `compute_dc50_score`,
`compute_dmax_score` in ranking.

## What is solid

- **Honestly labelled.** The model ID says "demo-heuristic-v0.1" and the project's status
  tracking marks it ⚠️ everywhere. Nothing here is overclaimed, and that matters.
- **Correct interface.** It emits the same `DegradationPrediction` shape a trained model
  would, so replacing the internals requires no changes to nodes 16, 18 or 21.
- **Correctly positioned** — after validation, before ranking, with access to target and
  objective context as well as the molecule.
- **Node 18 exists to catch its overclaims**, which is a thoughtful architectural response
  to a known-weak component.

## What to improve

**1 · Train a real model (objective O-1) — the project's single largest gap.** Requires
500+ PROTACs with measured DC₅₀/D<sub>max</sub>, a featurisation scheme, and a held-out
validation set. **Blocked on data that does not exist in the project.** Realistically this
means assembling from PROTAC-DB 3.0 and PROTACpedia (~2,000 published PROTACs, of which a
minority carry usable quantitative degradation data) and accepting narrow applicability.

**2 · Emit calibrated uncertainty, and make ranking respect it.** This is the highest-value
change that is *not* blocked on data. A heuristic that returns a bare DC₅₀ number is
indistinguishable, downstream, from a measurement. Returning a wide, explicit confidence
interval would let node 16 stop ranking on false precision and would honestly represent
what the system knows.

**3 · Publish the heuristic's rules.** 56 lines of undocumented scoring drives the final
ordering. Whatever the rules are — linker length terms, property windows, E3-specific
factors — they should be written down and reviewable. A reader currently cannot tell
whether the ranking encodes chemistry or an arbitrary weighting.

**4 · Sanity-check against the known cases the project already has.** `known_protac_smiles.csv`
holds MZ1, ARV-825 and others with published DC₅₀ values, and the NP-hard analysis
documents SJFα (7 nM, p38α) and SJFδ (46 nM, p38δ). Running the heuristic against these
and reporting the error is cheap, immediate, and would establish whether it has any
predictive value at all. **Do this before anything else** — it is a day of work and it
determines whether O-1 is a priority or an emergency.

**5 · Fail loudly outside the applicability domain.** Node 15 computes a domain score.
This agent should refuse to emit a confident number for a candidate flagged out-of-domain,
rather than extrapolating silently.

**6 · Consume the ternary results.** Bondeson 2018 establishes that ternary complex
formation predicts degradation far better than binary affinity. Node 20 computes ternary
feasibility — but it runs *after* this node, so the prediction cannot use it. Node 21
re-ranks with ternary data, but the DC₅₀ estimate itself never sees it. Either move
prediction after ternary or add a second prediction pass.

## Feasibility note

Item 4 is a day of work and should happen first — it converts an unknown into a measured
one. Items 2, 3 and 5 are small, unblocked, and together they stop the system presenting
heuristic output as if it were quantitative. Item 1 is large and data-blocked. Item 6 is a
graph-ordering question worth raising explicitly, since the current order contradicts the
project's own cited literature.
