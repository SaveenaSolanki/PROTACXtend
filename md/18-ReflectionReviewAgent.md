# 18 · ReflectionReviewAgent

| | |
| --- | --- |
| **Node** | 18 — `reflection_review` |
| **Source** | `synglue_agent/agents/reflection_agent.py` |
| **Size** | 48 lines |
| **Status** | ✅ Built — unit tested |
| **Delegates to** | `toolbox.critique_candidates()` |

## Architecture brief

The system's self-critic. It reviews the ranked candidates for evidence strength and flags
overclaims, emitting plausibility, evidence and risk scores.

This agent exists because the project understands its own weakness. Node 12 is an
unvalidated heuristic, node 13's tox flags are proxies, node 14 compares against four
molecules — and node 18 is the architectural response: a dedicated stage whose job is to
say "the confidence in this result is not supported by the evidence behind it."

That is an unusually mature thing to build into a pipeline, and it is the reason the case
study could report H1 and H3 as **rejected**. A system that only ranks will always produce
a top candidate; a system with a critic can produce a negative result. The project's most
credible output — 0 of 3,600 poses passed, therefore ICM's hydroxyls do not work — is the
kind of conclusion this node makes reportable.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.ranking_results` | `list[RankingResult]` | node 16 |
| `state.valid_candidates` | `list[CandidateRecord]` | node 11 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.reflection_reviews` | `list[ReflectionReview]` | plausibility, evidence, risk scores |

Also consumed by node 19, which uses the critique to steer refinement.

## What is solid

- **Its existence.** A dedicated overclaim-detection stage is rare and is the correct
  response to a pipeline with known-weak predictors.
- **Three separate axes** — plausibility, evidence, risk — rather than one blended
  "quality" number. These fail independently and should be scored independently.
- **Feeds the evolution loop**, so critique is not merely reported; it changes what gets
  built next.
- **Positioned after ranking**, so it critiques the actual shortlist rather than the raw set.
- **The Agent_Modules sheet's instruction for the supervisor** — "should enforce no
  hallucinated wet-lab claims" — is operationalised here.

## What to improve

**1 · Ground the critique in the known provenance of each input.** The agent should not have
to infer that degradation numbers are weak — the system already *knows* node 12 is
`SynGlue-demo-heuristic-v0.1`, that tox flags are proxies, and that novelty used 4
reference molecules. Feed that provenance in explicitly so the critique is derived from
recorded fact rather than re-estimated. This is the change that would make the critic
rigorous instead of advisory.

**2 · Give it authority to suppress, not just annotate.** A critique that produces a low
evidence score but leaves the candidate ranked first has not prevented the overclaim. Let
node 18 demote or gate candidates, or have node 21 consume the review scores directly.

**3 · Define what an "overclaim" is.** The detection criteria are undocumented in 48 lines
of code. For a component whose entire purpose is epistemic discipline, its own rules should
be the best-documented in the project.

**4 · Critique the run, not only the candidates.** The most important overclaims are
run-level: "12 candidates from a 150K space", "novelty vs 4 molecules", "4 of 600 E3
ligases", "structure was a low-confidence AlphaFold prediction". Those are the caveats a
reader needs, and no node currently produces them. This agent is the natural owner.

**5 · Report the negative result as a first-class outcome.** When the evidence does not
support any candidate, the correct output is "no viable candidate found, here is why" —
which is exactly what the H1/H3 rejections demonstrated. Make that a supported terminal
state rather than an interpretation of low scores.

**6 · Check it is not simply agreeing with the ranking.** A critic that scores highly-ranked
candidates as highly-plausible adds nothing. Test it against a deliberately weak candidate
set and confirm the scores actually diverge from rank order.

## Feasibility note

Items 1 and 4 are small, unblocked, and would sharply increase the value of the report —
item 4 in particular addresses caveats that currently appear nowhere in the system's
output. Item 2 is a design decision about how much authority the critic should hold, and it
is worth settling deliberately: it is the difference between a pipeline that notes its own
weaknesses and one that acts on them.
