# 19 · EvolutionRefinementAgent

| | |
| --- | --- |
| **Node** | 19 — `evolution_refinement` |
| **Source** | `synglue_agent/agents/evolution_agent.py` |
| **Size** | 61 lines |
| **Status** | ✅ Built |
| **Delegates to** | `toolbox.evolve_candidates()` |
| **Special** | **Owns the only feedback edge in the graph** (node 19 → node 10) |
| **Documentation** | ❌ Absent from `AGENT_API.md` |

## Architecture brief

The optimisation loop. It takes ranked and critiqued candidates and produces an improved
generation by GA-style mutation and recombination, feeding them back into node 10 for
re-assembly.

This is the only cycle in an otherwise linear 23-node graph. Every other node moves the
state forward exactly once; this one makes the pipeline iterative, and turns it from a
one-shot generator into a search.

It is also the node with the largest gap between architectural importance and documented
detail. It is missing from `AGENT_API.md` entirely, and the parameters that define any
genetic algorithm — population size, mutation operators, selection pressure, generation
count, convergence criterion — are not documented anywhere in the source material.

**A GA whose stopping condition is unspecified is a correctness risk**, not just a
documentation gap: without a bound it can loop indefinitely, and without cross-generation
deduplication it can rediscover the same molecules every round while appearing to make
progress.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.ranking_results` | `list[RankingResult]` | node 16 |
| `state.reflection_reviews` | `list[ReflectionReview]` | node 18 |
| `state.valid_candidates` | `list[CandidateRecord]` | node 11 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| refined candidate list | fed back to **node 10** | mutated + recombined candidates |

## What is solid

- **The loop exists**, and it is placed correctly — after ranking *and* after critique, so
  refinement is steered by both the score and the critique of that score.
- **Consuming reflection output** is a genuinely good design choice. Most GA
  implementations optimise the fitness function alone; this one can act on "the evidence
  here is weak" as well as "the score here is low".
- **Mutation and recombination on molecular components** is the right operator set for a
  three-part molecule where the linker is the dominant variable.
- **Re-enters at assembly** rather than at prediction, so refined candidates are properly
  rebuilt and re-validated rather than patched.

## What to improve

**1 · Bound and document the loop.** Specify and enforce maximum generations, a convergence
criterion, and an overall wall-clock or compute budget, governed by node 2's stop
conditions. This is the most important item here and it is a correctness fix, not a
refinement.

**2 · Deduplicate across generations.** Maintain a persistent seen-set keyed on canonical
InChIKey (the toolbox has `_stable_id` and `remove_duplicate_candidates`). Without it the
search revisits rather than explores — the classic failure mode of an unbounded GA.

**3 · Publish the GA parameters.** Population size, selection method, mutation rate and
operator set. A genetic algorithm is fully specified by these, and none are documented.

**4 · Define what the fitness function is.** Presumably `final_priority_score` from node 16
— which means the GA is optimising against a heuristic DC₅₀ (node 12). **The system is
therefore evolving candidates toward a proxy that has never been validated**, which will
amplify whatever bias the heuristic contains. This is the most consequential scientific
issue at this node, and it argues for validating node 12 (objective O-1, item 4) before
running long evolution campaigns.

**5 · Mutate the linker preferentially.** The project's own analysis shows the linker
dominates the outcome — three atoms flip the target. A GA mutating all three components
uniformly spends most of its budget on the axis that matters least.

**6 · Record generation lineage.** Each refined candidate should carry its parents and the
operator applied. Without lineage the final report cannot explain where a top candidate
came from, which undercuts the provenance claim.

**7 · Document it (objective O-7).** Add an `AGENT_API.md` entry with reads/sets and the
loop contract.

## Feasibility note

Items 1, 2 and 6 are small, unblocked, and prevent the loop from misbehaving or becoming
unexplainable under longer runs — worth doing before any extended campaign. Item 4 is the
one to think hardest about: an optimiser is only as good as its objective, and this one is
currently optimising toward an unvalidated heuristic.
