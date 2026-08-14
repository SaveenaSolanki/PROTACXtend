# 07 · E3LigandSelectionAgent

| | |
| --- | --- |
| **Node** | 7 — `select_e3_ligands` |
| **Source** | `synglue_agent/agents/e3_agent.py` |
| **Size** | 91 lines |
| **Status** | ✅ **Built (2026-08-12)** — 19 E3 groups / 114 cited ligands; arbitrary-E3 prompt parsing; DOI/UniProt provenance |
| **Data** | `curated_e3_ligands.csv` (8 rows) |
| **Objective** | **O-2** |

## Architecture brief

Chooses which E3 ligase the PROTAC will recruit, and which ligand will recruit it. The
selection logic is subcellular colocalization scoring: CRBN is nuclear, VHL is
cytoplasmic, and a target's localisation should determine which ligase can reach it.

The logic is sound. The problem is the search space it operates over.

**The human genome encodes 600+ E3 ligases. Four have usable ligands** — CRBN, VHL, cIAP
and MDM2 — so 99.3% of E3 space is inaccessible to this agent, and to the field. The
curated library holds 8 ligands across those 4 ligases. This is NP-hard problem #2 in the
project's own analysis, and it is a field-wide constraint rather than an implementation
defect: no amount of engineering here creates ligands that do not exist.

What *is* an implementation gap is that the scoring is nominal — a rule table rather than a
model — and there is no novel-ligand discovery path.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.parsed_objective.e3_ligase` | `str` | node 1 |
| `state.parsed_objective.e3_ligand_smiles` | `str` | node 1 |
| target localisation | derived | node 4 |
| `curated_e3_ligands.csv` | 8 rows | pomalidomide, VH032, lenalidomide, … |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.selected_e3_ligands` | `list[E3LigandRecord]` | `name`, `e3_ligase`, `smiles`, `exit_vector_confidence` |

Note that `exit_vector_confidence` is carried here, ahead of node 8 — the E3 side has
known, curated attachment points (`curated_exit_vector_map.csv`, 6 rows) where the warhead
side does not.

## What is solid

- **Colocalization scoring is the scientifically correct selection criterion.** Recruiting
  a cytoplasmic ligase to a nuclear target cannot work, and the agent encodes that.
- **Curated exit-vector map** for the E3 ligands means the attachment chemistry on this
  side is known rather than inferred — a real advantage over the warhead side.
- **All four accessible ligases are covered**, so the agent is not the binding constraint;
  the chemistry is.
- **Honestly labelled** as partial in the project's own status tracking.

## What to improve

**1 · Replace nominal scoring with evidence-backed selection.** Colocalization is
currently a rule table. E3 ligase expression varies enormously by cell type and is
available from HPA and DepMap (both named in the Agent_Modules sheet as intended sources
and neither wired in). Selecting CRBN for a cell line with low CRBN expression is a known
resistance mechanism and the agent cannot currently see it.

**2 · Report the constraint rather than hiding it.** Every run should state plainly that
selection was made from 4 of 600+ ligases. A user reading a ranked candidate list has no
way to know how narrow the search actually was.

**3 · Widen the ligand library within the 4 accessible ligases.** There are considerably
more than 8 published CRBN and VHL binders. This is data-entry work, not discovery, and it
meaningfully widens the accessible space at low cost.

**4 · Carry `exit_vector_confidence` through to ranking.** The field exists here but there
is no evidence it influences the final score. An E3 ligand with a well-characterised
attachment point should outrank one with a speculative attachment point.

**5 · Add degradation-outcome evidence per ligase–target pair.** PROTAC-DB and PROTACpedia
record which ligase actually worked for which target class. That is directly usable prior
knowledge and it is not consulted.

**6 · Novel E3 ligand discovery (objective O-5e) — very large, and out of scope for the
current project.** It requires covalent fragment screening and structural biology, not
code. Worth stating explicitly as out of scope so it stops reading as a to-do.

## Feasibility note

Items 2, 3 and 4 are small and unblocked and should be done. Item 1 is medium and depends
on wiring HPA/DepMap. Item 6 should be formally descoped — the project cannot solve a
field-wide chemistry bottleneck, and saying so improves the credibility of everything else.
