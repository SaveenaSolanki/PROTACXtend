# 16 · RankingAgent

| | |
| --- | --- |
| **Nodes** | **16** — `initial_ranking` (`final=False`) and **21** — `final_ranking` (`final=True`) |
| **Source** | `synglue_agent/agents/ranking_agent.py` |
| **Size** | 41 lines |
| **Status** | ✅ Built |
| **Special** | **The only agent class instantiated twice in the graph** |

## Architecture brief

Produces the system's actual deliverable: the ordered candidate list. It is the only agent
that runs twice, and the two runs bracket the expensive part of the pipeline.

- **Node 16 (`final=False`)** ranks on degradation, ADMET and novelty. Its output tells
  node 20 which candidates are worth spending hours of ternary compute on.
- **Node 21 (`final=True`)** re-ranks once ternary results exist, and writes
  `final_ranked_candidates`.

This two-pass design is the architectural reason `WorkflowState` is append-only: the second
ranking must see everything the first saw, plus the ternary data that arrived afterwards.
It is a genuinely good design decision — rank cheaply, spend expensively on the leaders,
then re-rank with better information.

Scoring is a multi-parameter weighted composite with hard gates and tier assignment.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.valid_candidates` | `list[CandidateRecord]` | node 11 |
| `state.degradation_predictions` | ⚠️ heuristic | node 12 |
| `state.admet_predictions` | mixed exact/proxy | node 13 |
| `state.novelty_results` | ⚠️ 4-molecule reference | node 14 |
| `state.ternary_feasibility_results` | node 21 pass only | node 20 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.ranking_results` | `list[RankingResult]` | `rank`, `tier`, `final_priority_score`, `confidence` |
| `state.final_ranked_candidates` | `list[RankingResult]` | node 21 only |

Toolbox: `rank_candidates`, `compute_dc50_score`, `compute_dmax_score`,
`assign_candidate_tier`.

## What is solid

- **The two-pass design is excellent** and is the right answer to an expensive optional
  stage. Rank cheap, spend on leaders, re-rank with the result.
- **One class, two configurations** — no duplicated scoring logic, so the two passes cannot
  drift apart.
- **Emits `confidence` alongside `rank`**, which is the correct shape for an output built
  on uncertain inputs.
- **Tier assignment** gives the reader a coarse grouping rather than forcing them to trust
  a fine-grained ordering that the input quality does not support.
- **Hard gates** mean a candidate failing a critical criterion cannot be rescued by scoring
  well elsewhere.

## What to improve

**1 · Publish the weights.** A weighted composite whose weights are undocumented is not
reproducible and not reviewable. The weights encode the project's scientific priorities —
how much degradation potency is worth against permeability against novelty — and they are
currently invisible. Make them explicit, versioned, and ideally configurable per run. This
is the most important change here.

**2 · Propagate input uncertainty into `confidence`.** The agent emits a confidence, but
its inputs are a heuristic (node 12), unvalidated proxies (node 13) and a 4-molecule
novelty comparison (node 14). Unless confidence is derived from those weaknesses, it
describes the arithmetic rather than the evidence. **This is the node where the system's
accumulated uncertainty either becomes visible or disappears.**

**3 · Do not rank on false precision.** Ordering candidates by a DC₅₀ produced by
`SynGlue-demo-heuristic-v0.1` implies a resolution the input does not have. Consider
ranking into tiers only, or widening ties, until node 12 is replaced.

**4 · Respect the applicability domain.** Node 15 labels out-of-domain candidates and there
is no evidence ranking consumes that label. An out-of-domain candidate should not top the
list on the strength of an extrapolated prediction.

**5 · Report score decomposition per candidate.** For each ranked molecule, show the
contribution of each term. A reviewer needs to see *why* something ranked first — and
whether it ranked first for a good reason or because one weak term dominated.

**6 · Explain rank changes between the two passes.** When node 21 reorders the list, the
report should say what moved and why. A candidate demoted by ternary infeasibility is one
of the most informative results the pipeline can produce, and it is currently invisible.

**7 · Document the hard gates.** Which criteria are absolute, and at what thresholds, is
unstated.

## Feasibility note

Items 1, 5, 6 and 7 are small, unblocked documentation-and-reporting changes that
substantially improve reviewability. Item 2 is the scientifically important one: it is what
determines whether the final output honestly represents the quality of its inputs, and it
requires no new data — only a decision to carry uncertainty forward rather than discard it.
