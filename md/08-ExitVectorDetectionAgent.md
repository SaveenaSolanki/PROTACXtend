# 08 · ExitVectorDetectionAgent

| | |
| --- | --- |
| **Node** | 8 — `detect_exit_vectors` |
| **Source** | `synglue_agent/agents/exit_vector_agent.py` |
| **Size** | 74 lines |
| **Status** | ✅ Built — RDKit + unit test |
| **Tool** | `rdkit_chemistry.py` → `detect_exit_vector_atoms()` (380 lines) |

## Architecture brief

Finds the atoms where a linker can be attached to the warhead and to the E3 ligand. This
is the hinge between component selection and molecular construction: node 9 generates
linkers, node 10 joins them, but neither can act without knowing *where* to join.

It is also, in the case study, the node whose answer decided the entire investigation.
Hypothesis H1 asked whether ICM's hydroxyl groups could serve as exit vectors. The answer
was no — both OH groups point into the protein rather than into solvent — and 0 of 3,600
P4ward poses passed. The project then moved to the N-phenyl position and a ring-modified
analogue, which worked.

That history is the strongest argument for improvement 1 below: the geometric reality that
killed H1 was discoverable at this node, but was only established at node 20, thousands of
poses later.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.selected_warheads` | `list[WarheadRecord]` | node 6 |
| `state.selected_e3_ligands` | `list[E3LigandRecord]` | node 7 |
| `curated_exit_vector_map.csv` | 6 rows | known E3 attachment points |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.exit_vectors` | `list[ExitVectorRecord]` | `atom_index`, `confidence`, `role`, `rationale` |

Detected chemistry types (via `linker_scanner.detect_attachment_points`): OH, NH, COOH,
aromatic C–H, aliphatic C–H.

## What is solid

- **Real cheminformatics, not heuristics.** RDKit atom-level detection over actual
  molecular graphs.
- **`rationale` on every record.** The agent explains *why* an atom was selected, which is
  rare in this codebase and exactly right for a scientific tool.
- **Confidence scores** are carried, so downstream consumers can prefer strong sites.
- **Role-aware** — warhead-side and E3-side detection are distinguished, and the E3 side
  can draw on a curated map rather than pure inference.
- **`linker_scanner.py` scores attachment points** by distance to molecular centre and
  stereochemical impact — genuinely more sophisticated than simple functional-group matching.

## What to improve

**1 · Add solvent accessibility. This is the most valuable single improvement available in
the pipeline.** Detection is currently 2D/topological: it finds chemically attachable
atoms. It does not check whether those atoms are *reachable* when the warhead is bound in
its pocket. ICM's OH27 and OH29 are perfectly good chemistry and completely unusable
geometry. With the AlphaFold or PDB structure already retrieved at node 4, an SASA
calculation on the bound pose would have rejected them immediately — turning a 3,600-pose,
multi-hour disproof into a sub-second filter.

**2 · Propagate confidence into ranking.** Exit vectors carry a confidence that appears to
stop at this node. A candidate built on a speculative attachment point should not rank
alongside one built on a curated, literature-backed vector.

**3 · Use the literature map more aggressively.** The case study's correct answer —
N-phenyl — came from a published ICM-BP probe (Lee et al. 2014), not from the detector.
`curated_exit_vector_map.csv` holds only 6 rows and covers the E3 side. Extending it to
warheads, sourced from PROTAC-DB, would let known-good vectors outrank inferred ones.

**4 · Flag stereochemical consequences at detection time.** `stereochemistry_engine.py`
(417 lines) knows that attaching at a chiral centre changes the exit geometry. Surfacing
that here, rather than after assembly, prevents building isomers that were never viable.

**5 · Report the count of rejected sites, with reasons.** Node 20 gets a pass rate; this
node reports only what it found. Knowing that 8 candidate atoms were considered and 6
rejected — and why — is diagnostic information the report should carry.

## Feasibility note

Improvement 1 is the highest-leverage unblocked change identified anywhere in this agent
set. The structure is already fetched at node 4, RDKit and the geometric proxy already
exist, and the payoff is converting the exact failure the project spent its case study
discovering into a cheap upfront filter. Items 2, 3 and 5 are small.
