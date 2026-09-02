# 11 · CandidateValidationAgent

| | |
| --- | --- |
| **Node** | 11 — `validate_protacs` |
| **Source** | not listed in the documented file tree — see improvement 5 |
| **Size** | 49 lines |
| **Status** | ✅ Built — RDKit + unit test |
| **Delegates to** | `toolbox.validate_candidates()`, `validate_smiles`, `canonicalize_smiles`, `compute_basic_properties`, `remove_duplicate_candidates` |

## Architecture brief

The quality gate between construction and prediction. Everything node 10 assembles passes
through here, and only what survives reaches the four prediction nodes.

Its position is what makes it valuable: prediction is the expensive half of the pipeline
(node 20 can cost hours), so rejecting a malformed molecule here rather than at node 20 is
the difference between a wasted second and a wasted afternoon. It is the cheapest filter in
the system and it protects the most expensive nodes.

Two checks: chemical validity via RDKit, and property-range filtering. Plus canonicalisation
and deduplication.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.assembled_candidates` | `list[...]` | node 10 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.valid_candidates` | `list[CandidateRecord]` | validated, canonicalised, deduplicated |

`valid_candidates` is the single most widely-read field in the state — nodes 12, 13, 14,
15, 16, 17 and 20 all consume it.

## What is solid

- **Real RDKit validation**, so a molecule that cannot be parsed cannot proceed.
- **Canonicalisation before deduplication**, which is the correct order — deduplicating raw
  SMILES strings would miss the same molecule written two ways.
- **Positioned to protect the expensive nodes.** Architecturally exactly right.
- **Deliberately thin** at 49 lines, delegating to shared toolbox methods so the same
  validation rules apply anywhere in the codebase.
- **Unit tested.**

## What to improve

**1 · Record rejections with reasons, and surface the count.** The agent emits survivors.
It does not appear to report how many candidates were rejected or why. That number is the
single most diagnostic statistic in the build phase: a run that assembles 200 candidates
and validates 12 has an upstream problem at node 8 or 10, and nothing currently makes that
visible.

**2 · Publish the property ranges.** "Property ranges" is undocumented. PROTACs are bRo5
by construction — MW 700–1200, TPSA 150–300, RotB 10–25 — so a filter tuned to
conventional small-molecule ranges would reject every legitimate candidate. The thresholds
must be explicit, PROTAC-appropriate, reviewable, and ideally configurable per run.

**3 · Distinguish hard failures from soft ones.** An unparseable SMILES is invalid. A
molecule 50 Da over an MW preference is not — it is disfavoured. Collapsing both into a
binary drop loses information that ranking could use. Prefer a validity flag plus a
property-penalty score over a hard cut.

**4 · Preserve stereochemistry through canonicalisation.** This is a correctness risk.
RDKit canonicalisation can normalise stereo notation, and the project's own guidance is
"never canonicalize away stereo". Since this node canonicalises *and* deduplicates, two
distinct stereoisomers with different predicted ternary behaviour could be silently merged
into one. **Verify explicitly** that `canonicalize_smiles` is stereo-preserving and that
`remove_duplicate_candidates` treats R and S as distinct.

**5 · Locate and document the source file.** The agent is not present in the documented
file tree in `ARCHITECTURE_SUMMARY.md` §11, which lists 21 agent files. Either it lives
inside another module or the tree is incomplete. For a node that every prediction depends
on, this should be resolved.

**6 · Add a synthesisability pre-check.** Validity is not feasibility. A chemically valid
PROTAC that no route can make should not consume node 20's compute budget.

## Feasibility note

Item 4 is a correctness question and should be checked before anything else here — a silent
stereoisomer merge would quietly invalidate downstream ternary results. Items 1, 2 and 5
are small and unblocked, and item 1 gives the build phase the diagnostic it currently lacks.
