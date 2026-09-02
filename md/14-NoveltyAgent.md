# 14 · NoveltyAgent

| | |
| --- | --- |
| **Node** | 14 — `check_novelty` |
| **Source** | `synglue_agent/agents/novelty_agent.py` |
| **Size** | 20 lines agent → `novelty_checker.py` (57 lines) |
| **Status** | ✅ **Built (2026-08-08)** — local Morgan similarity + live PubChem patent cross-reference |
| **Data** | `known_protac_smiles.csv` (**4 rows**) |
| **Objective** | **O-3** |

## Architecture brief

Asks whether a generated candidate is actually new. It computes Tanimoto similarity
between each candidate and a set of known PROTACs, returning the nearest known molecule,
the similarity value, and a novelty score.

The method is standard and correctly implemented. **The reference set has four molecules
in it** — MZ1, ARV-825 and two others.

Roughly 2,000 PROTACs have been published. A novelty score computed against 0.2% of them
is not a novelty score; it is a similarity measurement against an arbitrary quartet. Every
candidate will look novel, because almost everything is dissimilar to four specific
molecules. The agent therefore reports high novelty regardless of whether the candidate is
genuinely new or a rediscovery of a well-known degrader.

This is the cheapest significant fix in the entire project: the gap is data entry, not
science.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.valid_candidates` | `list[CandidateRecord]` | node 11 |
| `known_protac_smiles.csv` | **4 rows** | MZ1, ARV-825, … |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.novelty_results` | `list[NoveltyResult]` | `nearest_known`, `tanimoto`, `novelty_score` |

Toolbox: `check_novelty`, `calculate_similarity`.

## What is solid

- **The method is right.** Tanimoto over molecular fingerprints is the standard approach
  and RDKit implements it correctly.
- **Returns the nearest known molecule, not just a number.** This is good design — a
  reviewer can inspect *what* the candidate resembles rather than trusting a score.
- **Clean delegation** — 20-line agent over a 57-line checker.
- **The limitation is documented** in the project's own status tracking rather than hidden.
- **Feeds ranking**, so novelty genuinely influences the shortlist.

## What to improve

**1 · Ingest PROTAC-DB 3.0 and PROTACpedia (objective O-3). Do this first.** It takes the
reference set from 4 to roughly 2,000 molecules and is pure data integration — no new
science, no new architecture, no blocked dependency. Both `protacdb_client.py` (43 lines)
and `protacpedia_client.py` (22 lines) **already exist in the toolbox** and are already
wired to free sources. This is the highest value-per-hour change identified anywhere in the
agent set.

**2 · Check components, not just the whole molecule.** The Agent_Modules sheet is explicit:
novelty "must check components and full molecule". A PROTAC built from a known warhead and
a known E3 ligand joined by a slightly different linker is not novel in any meaningful
sense, but whole-molecule Tanimoto will score it as such. Check warhead, linker and E3
ligand separately, then the assembly.

**3 · Add IP screening.** The intended tools per the Agent_Modules sheet are SureChEMBL,
Lens and Google Patents; none are wired in. Chemical novelty and freedom to operate are
different questions, and for a project heading toward wet-lab work the patent question is
the one that matters commercially.

**4 · Report the denominator.** Every novelty claim should carry the size and identity of
the set it was checked against. "Novel vs 4 reference molecules" and "novel vs 2,000" are
different statements and the report currently cannot distinguish them.

**5 · State the fingerprint and threshold.** Tanimoto values are not comparable across
fingerprint types (ECFP4 vs MACCS vs RDKit) or radii. Node 17 uses a Tanimoto ≥ 0.62
clustering threshold; whether the two nodes use the same fingerprint is undocumented.

**6 · Acknowledge the sparse-sampling limit.** NP-hard problem #11: published PROTACs
cover < 0.1% of linker space and 90%+ use CRBN or VHL. Even a complete reference set makes
novelty a statement about a heavily biased corpus, and the report should say so.

## Feasibility note

Item 1 is small, unblocked, uses clients that already exist, and moves this agent from
⚠️ to ✅ on its own. Items 2, 4 and 5 are also small. Together they are perhaps two days of
work and they remove the least defensible claim the system currently makes.
