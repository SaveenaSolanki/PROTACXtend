# PROTACXtend — Agent Files

One file per agent class. Each contains: architecture brief, data consumed, data
generated, what is solid, and what to improve for reliability and feasibility.

Compiled from `ARCHITECTURE_SUMMARY.md`, `AGENT_API.md` and `Agent_details.xlsx`
(Agent_Modules, Implementation_Status, NP_Hard_Problems sheets).
Architecture live-verified 2026-07-31.

> **22 files for 23 nodes.** `RankingAgent` runs twice — node 16 (`final=False`) and
> node 21 (`final=True`) — and is documented once, in `16-RankingAgent.md`.

## ▶ Animated walkthrough

**[PIPELINE_ANIMATION.html](PIPELINE_ANIMATION.html)** — open in any browser. Plays one run
end to end: each node activating in turn, the shared `WorkflowState` filling field by field,
the evolution loop firing back into assembly, and the two-backend ternary branch.

Play / pause / step / scrub, three speeds. Space = play/pause, ← → = step. Self-contained,
no dependencies, works offline.

## Search instrumentation

**[SEARCH_INSTRUMENTATION.md](SEARCH_INSTRUMENTATION.md)** — four instruments for seeing
what the agents actually explore, rather than only what they returned: the run funnel, the
coverage matrix, loop trajectory, and counterfactual sweeps. Includes schemas, data-source
audit (~70% derivable today), and a ranked implementation order.

## Index

| # | Agent | Phase | Lines | Status |
| --- | --- | --- | --- | --- |
| [01](01-SupervisorAgent.md) | SupervisorAgent | Intake | 59 | ✅ |
| [02](02-DesignPlannerAgent.md) | DesignPlannerAgent | Intake | 152 | ✅ · undocumented |
| [03](03-SafetyAgent.md) | SafetyAgent | Intake | 55 | ✅ |
| [04](04-TargetResolverAgent.md) | TargetResolverAgent | Resolve | 83 | ✅ |
| [05](05-TargetBinderRetrievalAgent.md) | TargetBinderRetrievalAgent | Resolve | 300 | ✅ |
| [06](06-WarheadSelectionAgent.md) | WarheadSelectionAgent | Select | 85 | ✅ |
| [07](07-E3LigandSelectionAgent.md) | E3LigandSelectionAgent | Select | 91 | ⚠️ **O-2** |
| [08](08-ExitVectorDetectionAgent.md) | ExitVectorDetectionAgent | Select | 74 | ✅ |
| [09](09-LinkerGenerationAgent.md) | LinkerGenerationAgent | Build | 28 | ✅ |
| [10](10-MolecularConstructionAgent.md) | MolecularConstructionAgent | Build | 49 | ✅ |
| [11](11-CandidateValidationAgent.md) | CandidateValidationAgent | Build | 49 | ✅ |
| [12](12-DegradationPredictionAgent.md) | DegradationPredictionAgent | Predict | 39 | ⚠️ **O-1** |
| [13](13-ADMETAgent.md) | ADMETAgent | Predict | 20 → 343 | ✅ |
| [14](14-NoveltyAgent.md) | NoveltyAgent | Predict | 20 → 57 | ⚠️ **O-3** |
| [15](15-ApplicabilityDomainAgent.md) | ApplicabilityDomainAgent | Predict | — | ✅ · undocumented |
| [16](16-RankingAgent.md) | RankingAgent *(nodes 16 + 21)* | Rank | 41 | ✅ |
| [17](17-ProximityDiversityAgent.md) | ProximityDiversityAgent | Rank | 31 | ✅ |
| [18](18-ReflectionReviewAgent.md) | ReflectionReviewAgent | Rank | 48 | ✅ |
| [19](19-EvolutionRefinementAgent.md) | EvolutionRefinementAgent | Rank | 61 | ✅ · undocumented |
| [20](20-TernaryFeasibilityAgent.md) | TernaryFeasibilityAgent | Rank | 597 | ✅ · **O-4** unexecuted |
| [22](22-ReportAgent.md) | ReportAgent | Emit | 20 → 58 | ✅ |
| [23](23-MemoryUpdateAgent.md) | MemoryUpdateAgent | Emit | 21 → 31 | ✅ · undocumented |

## NP-hard funnel extension agents

These files document the controlled-search implementation added after the attached agent packet was written. They are intentionally budget-setting, filtering, proxy-scoring, and feedback-loop agents; they do not exhaustively enumerate the PROTAC design space.

| # | Agent | Phase | Status |
| --- | --- | --- | --- |
| [24](24-ControlledSearchAgent.md) | ControlledSearchAgent | Control | ✅ implemented |
| [25](25-StereochemistryEnumerationAgent.md) | StereochemistryEnumerationAgent | Build | ✅ implemented |
| [26](26-CheapFilterAgent.md) | CheapFilterAgent | Filter | ✅ implemented |
| [27](27-ExpensiveModelingSelectionAgent.md) | ExpensiveModelingSelectionAgent | Select | ✅ implemented |
| [28](28-CellContextAgent.md) | CellContextAgent | Context | ✅ implemented with curated/default priors |
| [29](29-CooperativityPredictionAgent.md) | CooperativityPredictionAgent | Predict | ⚠️ proxy implemented |
| [30](30-HookEffectPredictionAgent.md) | HookEffectPredictionAgent | Predict | ⚠️ proxy implemented |
| [31](31-ActiveLearningAgent.md) | ActiveLearningAgent | Learn | ✅ feedback ingestion implemented; retraining gate only |

## Highest-value improvements across all agents

Ordered by value per unit of effort. None of the top five are blocked on data or new science.

| # | Agent | Change | Effort |
| --- | --- | --- | --- |
| 1 | [20 Ternary](20-TernaryFeasibilityAgent.md) | **Execute the P4ward run.** 2–4 h of compute, zero code. Proves a 1,800-line component and lets the fast proxy finally be calibrated. | Afternoon |
| 2 | [22 Report](22-ReportAgent.md) | **Auto-generate the limitations block.** Every caveat is already in the state and none reach the reader. Largest single credibility gain in the project. | Small |
| 3 | [14 Novelty](14-NoveltyAgent.md) | **Ingest PROTAC-DB / PROTACpedia.** 4 → ~2,000 reference molecules. The API clients already exist. Moves the agent ⚠️ → ✅ alone. | Small |
| 4 | [12 Degradation](12-DegradationPredictionAgent.md) | **Benchmark the heuristic against known DC₅₀ values** (MZ1, ARV-825, SJFα/δ). One day, and it tells you whether O-1 is a priority or an emergency. | 1 day |
| 5 | [08 Exit vectors](08-ExitVectorDetectionAgent.md) | **Add solvent accessibility.** Turns the case study's 3,600-pose disproof of ICM's hydroxyls into a sub-second upfront filter. | Small |
| 6 | [16 Ranking](16-RankingAgent.md) | **Publish the weights and propagate input uncertainty** into `confidence`. | Small |
| 7 | [10 Construction](10-MolecularConstructionAgent.md) | **Verify stereo preservation is always on.** Correctness risk, not enhancement. | Small |
| 8 | [11 Validation](11-CandidateValidationAgent.md) | **Verify canonicalisation does not merge stereoisomers.** Same correctness risk, other end. | Small |

## Cross-cutting observations

**Documentation gap (objective O-7).** Four of the 22 agent classes have no `AGENT_API.md`
entry: DesignPlanner (node 2, the 152-line policy engine governing the whole graph),
ApplicabilityDomain (node 15, also missing from the Implementation_Status sheet),
EvolutionRefinement (node 19, owner of the only feedback edge) and MemoryUpdate (node 23).

**Two source files are unlocated.** `CandidateValidationAgent` and `MemoryUpdateAgent` do
not appear in the file tree in `ARCHITECTURE_SUMMARY.md` §11, which lists 21 agent files.

**The strength/weakness split is consistent.** Every agent that *builds or filters
molecules* is solid — real RDKit chemistry, real API integration, real geometry. Every
agent that *predicts biological outcome* is a heuristic or a proxy. The pipeline searches
well and predicts poorly, and all four remaining NP-hard problems are prediction problems.

**Recurring theme: the data exists, the reporting does not.** Uncertainty, coverage
denominators, rejection counts, domain labels and provenance are computed at nearly every
node and then discarded before the report. A large share of the improvements above are not
new capability — they are surfacing what the system already knows.

**Two unvalidated defaults worth checking early.** Stereochemistry may be silently lost at
assembly (node 10) or merged at canonicalisation (node 11); both would quietly invalidate
downstream ternary predictions, since R and S configure the exit vector differently.
