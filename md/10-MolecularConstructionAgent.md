# 10 · MolecularConstructionAgent

| | |
| --- | --- |
| **Node** | 10 — `construct_protacs` |
| **Source** | `synglue_agent/agents/construction_agent.py` |
| **Size** | 49 lines |
| **Status** | ✅ Built |
| **Delegates to** | `toolbox.construct_protac_candidates()`, `assemble_components()`, `_join_on_dummy()` |
| **Special** | **Target of the only feedback edge in the graph** (from node 19) |

## Architecture brief

Assembles the three components into a complete PROTAC SMILES. Three strategies are
available — direct concatenation, reaction SMARTS, and fragment joining on dummy atoms —
which matters because the components come from heterogeneous sources with inconsistent
attachment-point notation.

Architecturally this node is distinctive: it is the **only node with an inbound edge from
later in the graph**. Node 19 (`EvolutionRefinementAgent`) feeds refined candidates back
here for re-assembly, making nodes 10 → 19 the system's optimisation loop. Everything else
is a straight line.

That loop is the reason this agent's idempotency and determinism matter more than its line
count suggests.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.selected_warheads` | `list[WarheadRecord]` | node 6 |
| `state.selected_e3_ligands` | `list[E3LigandRecord]` | node 7 |
| `state.generated_linkers` | `list[LinkerRecord]` | node 9 |
| refined candidates | feedback | **node 19** |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.construction_attempts` | `list[ConstructionAttempt]` | every attempt, including failures |
| `state.assembled_candidates` | `list[...]` | successfully joined PROTAC SMILES |

Recording *attempts* rather than only successes is a good design decision — see below.

## What is solid

- **Three assembly strategies** with fallback, which is what makes heterogeneous component
  sources joinable at all.
- **Failed attempts are retained** in `construction_attempts`, not discarded. This is
  genuinely well designed: a systematic assembly failure is diagnosable rather than
  invisible.
- **Stereo-preserving assembly exists** via `assemble_with_stereo_preservation(wh, lk, e3)`
  in the 417-line stereochemistry engine, tested on ICM (4 isomers) and VH032 (R/S).
- **Attachment-marker handling** is explicit in the toolbox
  (`_has_attachment`, `_remove_attachment_markers`, `_annotate_hypothetical_attachment`),
  so speculative attachment points are labelled as such.
- **Validated immediately downstream** at node 11, so bad output does not travel far.

## What to improve

**1 · Guarantee stereo preservation is always on.** The engine exists and is tested, but
the default assembly path is `construct_protac_candidates()` and it is not documented
whether that path routes through `assemble_with_stereo_preservation`. The Agent_Modules
sheet's instruction for the isomeric agent is emphatic: *"never canonicalize away stereo"*.
Silently dropping chirality during assembly would invalidate downstream ternary
predictions, since R and S configure the exit vector differently. **Verify and pin this.**

**2 · Record which strategy produced each candidate.** Three strategies with fallback means
candidates are not equivalent in confidence — a reaction-SMARTS join is chemically better
grounded than a naive concatenation. Ranking cannot currently distinguish them.

**3 · Make the feedback loop convergent and bounded.** Nodes 10 ↔ 19 form a cycle. There is
no documented iteration cap, convergence criterion, or duplicate-suppression across
generations. A GA loop without those can churn indefinitely or rediscover the same
molecules each round. Node 2's stop conditions should govern this explicitly.

**4 · Deduplicate across generations, not just within a batch.** The toolbox has
`remove_duplicate_candidates` and `_stable_id`. The loop needs a persistent seen-set keyed
on canonical InChIKey so evolution explores rather than revisits.

**5 · Report the assembly failure rate.** `construction_attempts` holds the data;
nothing surfaces the ratio. A 90% failure rate on a given warhead is a strong signal that
its exit vectors are wrong — the same signal node 8 should have caught earlier.

**6 · Validate chemical sanity of the join itself.** A concatenation can produce a
syntactically valid SMILES that is chemically absurd. Node 11 checks validity and property
ranges; a synthesisability gate (AiZynthFinder / RAscore are named in the Agent_Modules
sheet, neither implemented) is the missing hard filter before wet-lab claims.

## Feasibility note

Item 1 is small, unblocked, and a correctness issue rather than an enhancement — it should
be verified first. Items 3 and 4 are small and prevent the optimisation loop from
misbehaving under longer runs. Item 6 is medium and is the real gate on wet-lab readiness.
