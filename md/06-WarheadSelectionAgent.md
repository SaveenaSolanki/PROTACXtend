# 06 · WarheadSelectionAgent

| | |
| --- | --- |
| **Node** | 6 — `select_warheads` |
| **Source** | `synglue_agent/agents/warhead_agent.py` |
| **Size** | 85 lines |
| **Status** | ✅ Built |
| **Data** | `curated_warheads.csv` (7 rows) + `warhead_seed_metaboglue_gold.csv` (485,329 rows) |

## Architecture brief

Chooses the target-binding end of the PROTAC. It fuses three sources — the SMILES the user
supplied, the small curated library, and the retrieved binders from node 5 — and scores
each for potency before handing a ranked set to exit-vector detection.

The fusion is the interesting part. A user-specified warhead is honoured, but the agent
still surfaces alternatives, which is what allows the case study to discover that the
originally-specified ICM attachment points were unusable and a ring-modified analogue was
needed instead.

It sits on by far the largest data asset in the project: a 485,329-row warhead seed
database, against 7 curated rows.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.parsed_objective.warhead_smiles` | `str` | node 1 |
| `state.parsed_objective.target_name` | `str` | node 1 |
| `state.retrieved_binders` | `list[BinderRecord]` | node 5 |
| `curated_warheads.csv` | 7 rows | JQ1, foretinib, dasatinib, ICM, … |
| `warhead_seed_metaboglue_gold.csv` | 485,329 rows | large-scale seed |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.selected_warheads` | `list[WarheadRecord]` | `name`, `smiles`, `source`, `potency`, `validity` |

Toolbox methods: `select_warheads`, `score_warhead_potency`, `compute_p_activity`,
`_retrieve_external_seed_binders`, `mine_external_binders`.

## What is solid

- **Three-way fusion** (user + curated + retrieved) rather than a fixed library. This is
  the right design and it is what let the case study pivot warheads mid-investigation.
- **Potency scoring is present**, with `compute_p_activity` normalising activity so
  heterogeneous sources are at least nominally comparable.
- **Source is recorded on every record**, so a candidate can be traced to its origin.
- **Validity flag** carried per record, so an unparseable warhead is marked rather than
  silently dropped.

## What to improve

**1 · Document and exploit the 485K seed database.** It is the largest asset in the project
by three orders of magnitude and the least described — there is no schema documentation,
no provenance statement, and no stated relationship to the 7 curated rows. Establish what
is in it, where it came from, and whether it is filtered for quality. As it stands the
system cannot honestly claim to use it.

**2 · Annotate exit vectors at selection time, not after.** The Agent_Modules sheet is
explicit that the warhead agent "needs exit-vector annotation". Selecting a potent warhead
that has no usable attachment point wastes the whole downstream run — which is exactly what
happened with ICM in the case study (H1 rejected, 0/3,600 poses). Filtering for
attachability *here* would have caught it four nodes earlier.

**3 · Score promiscuity, not just potency.** Foretinib is in the curated library and binds
133 kinases. A promiscuous warhead is a selectivity liability that no downstream node
currently measures. Add an off-target count from ChEMBL and let ranking see it.

**4 · Make the fusion policy explicit.** When the user supplies a warhead and node 5
retrieves a better one, what happens? Document and test the precedence rule, and surface
it in the report — a silently substituted warhead is a serious provenance failure.

**5 · Deduplicate against retrieved binders by InChIKey.** The user's SMILES and a
retrieved record are frequently the same molecule written differently, producing duplicate
candidates that then propagate through assembly and inflate the candidate count.

**6 · Cap and rank explicitly.** With 485K seed rows available, the selection cut needs a
stated rule and a recorded count of what was considered versus returned.

## Feasibility note

Item 2 is the highest-value change in the whole build phase — it is a filter, not new
science, and it directly addresses the failure mode the case study actually hit. Item 1 is
a documentation task but blocks any honest claim about the project's headline data asset.
