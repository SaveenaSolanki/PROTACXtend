# 17 · ProximityDiversityAgent

| | |
| --- | --- |
| **Node** | 17 — `diversity_clustering` |
| **Source** | `synglue_agent/agents/proximity_agent.py` |
| **Size** | 31 lines |
| **Status** | ✅ Built — unit tested |
| **Threshold** | Tanimoto ≥ 0.62 |

## Architecture brief

Prevents the shortlist from being eight versions of the same molecule. It clusters
chemically similar candidates at a Tanimoto threshold of 0.62 and selects a representative
from each cluster.

The scientific motivation is specific to PROTACs and stronger than it first appears. The
project's own NP-hard analysis establishes that a three-atom linker change flips the
degraded target from p38α to p38δ. A candidate list dominated by near-identical linkers is
therefore not just redundant — it is a *fragile* portfolio, because those candidates share
the same failure modes. Diversity here is risk management, not tidiness.

Positioned after initial ranking, so it diversifies an already-prioritised list rather than
an unordered one.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.valid_candidates` | `list[CandidateRecord]` | node 11 |
| `state.ranking_results` | implied | node 16 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.diversity_clusters` | `list[DiversityCluster]` | `cluster_id`, `representative_id`, `diversity_score` |

Toolbox: `cluster_candidates`, `choose_diverse_representatives`.

## What is solid

- **The right problem to solve**, for a well-articulated reason specific to this chemistry.
- **A stated, specific threshold** (0.62) rather than a vague "similar" — reproducible and
  arguable, which is what a threshold should be.
- **Representative selection is separate from clustering** (`choose_diverse_representatives`
  is its own method), so the selection policy can be changed independently.
- **Runs after ranking**, so representatives can be chosen by rank rather than arbitrarily.
- **Cheap and deterministic**, unit tested.

## What to improve

**1 · Justify 0.62, or make it adaptive.** The threshold is precise but unexplained. It is
also fixed regardless of how many candidates exist — clustering 12 candidates and clustering
2,000 want different granularity. Either cite the basis for 0.62 or derive the cut from the
similarity distribution of the actual candidate set.

**2 · Cluster on the linker, not just the whole molecule.** This is the most valuable change
here. Whole-molecule fingerprints are dominated by the warhead and E3 ligand, which are
identical across most candidates in a run — so whole-molecule Tanimoto will make everything
look similar and will *under*-resolve exactly the dimension that determines the outcome.
Given that the linker is the variable that flips selectivity, clustering should weight or
isolate the linker region.

**3 · State the fingerprint, and align it with node 14.** Tanimoto is meaningless without
knowing the fingerprint type and radius, and node 14 (novelty) uses Tanimoto too. If the
two nodes use different fingerprints, their numbers are silently incomparable.

**4 · Make representative selection explicit.** Is the representative the highest-ranked
member, the cluster centroid, or the most synthesisable? Each is defensible; the choice
should be documented, and highest-ranked is probably right given the position after node 16.

**5 · Do not discard non-representatives silently.** A cluster's other members are the
natural backup candidates if the representative fails synthesis or wet-lab validation.
Retain them in the report as a ranked within-cluster list.

**6 · Report cluster structure as a result in its own right.** If 200 candidates collapse
into 3 clusters, that is a finding — it means the search explored far less chemical space
than the candidate count suggests. That number belongs in the report.

## Feasibility note

Item 2 is the highest-value change and is a scoring-region choice rather than new
capability. Items 3, 4 and 6 are small. Together they turn a tidy-up step into a genuine
portfolio-diversity control, which is what the chemistry actually requires.
