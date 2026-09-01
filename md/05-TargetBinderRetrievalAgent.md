# 05 · TargetBinderRetrievalAgent

| | |
| --- | --- |
| **Node** | 5 — `retrieve_target_binders` |
| **Source** | `synglue_agent/agents/binder_agent.py` |
| **Size** | 300 lines — largest non-structural agent |
| **Status** | ✅ Built — verified by live API calls |
| **Tools** | `chembl_lookup.py` (256), `pubchem_lookup.py` (212), `bindingdb_lookup.py` (152), `online_ligand_miner.py` (326) |

## Architecture brief

The evidence-gathering agent. It fans out across three bioactivity databases to find
molecules already known to bind the resolved target, and returns up to 100 of them with
activity values and source attribution.

This is where the system's warhead choices get their empirical grounding. Node 6 fuses
these retrieved binders with the curated library, so the quality of this retrieval sets a
ceiling on the quality of every candidate built downstream.

At 300 lines it is the largest agent outside the ternary branch, and the size is real
work: three different API shapes, three different activity conventions, deduplication
across sources, caching, rate limiting and exponential backoff.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.target_record.uniprot_id` | `str` | node 4 |
| `state.parsed_objective.target_name` | `str` | node 1 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.retrieved_binders` | `list[BinderRecord]` | SMILES, activity value, activity type, source database |
| `state.traces` | `list[AgentTrace]` | per-source query and hit counts |

**Cap: 100 records.** See improvement 1.

## What is solid

- **Three independent sources**, not one. ChEMBL, PubChem and BindingDB have different
  coverage and different curation, and querying all three is the correct call.
- **Source attribution on every record**, which is what makes the provenance claim real.
- **Serious network engineering** — 2 req/s, 30 s timeout, 5 retries with exponential
  backoff, caching. This is the part most projects get wrong and this one does not.
- **Verified against live APIs**, not fixtures.
- **`compute_p_activity` in the toolbox** normalises activity so heterogeneous sources can
  be compared at all.

## What to improve

**1 · Make the 100-record cap explicit and principled.** A silent truncation to 100 reads
downstream as "these are the known binders" when it may be "these are the first 100 of
4,000". Record the true hit count, state the selection rule (top by potency? by
confidence? arbitrary?), and surface both in the report. If the cut is arbitrary, make it
potency-ranked.

**2 · Normalise and record the activity type.** Ki, IC50, Kd and EC50 are not
interchangeable, and each source reports differently. `BinderRecord` should carry the
assay type and units explicitly, and node 6's potency scoring should refuse to compare
across incompatible types.

**3 · Filter on assay quality, not just presence.** ChEMBL carries confidence scores and
assay-type flags. Pulling a binder whose only evidence is a single low-confidence
high-throughput datapoint and treating it identically to a well-characterised inhibitor is
the kind of error that propagates all the way to the final ranking.

**4 · Deduplicate on structure, not string.** The same molecule appears across all three
sources with different SMILES spellings. Dedup must be InChIKey-based (the toolbox has
`canonicalize_smiles` and `chemistry_core.py` already) or the same compound is counted
three times and skews node 6.

**5 · Handle the zero-hit case as a first-class outcome.** A novel or poorly-studied target
returns nothing. The run should say so loudly and fall back to the 485K-row warhead seed
database rather than proceeding with an empty list.

**6 · Persist a per-target cache.** These queries are slow, rate-limited and highly
repeatable across runs. A disk cache keyed on UniProt ID would make iteration on
downstream nodes dramatically faster and make case-study reruns reproducible.

## Feasibility note

Items 1, 4 and 6 are small and unblocked, and item 1 in particular removes a silent
truncation that currently misrepresents the evidence base. Items 2 and 3 are the
scientifically important ones and are medium-sized — they require deciding a policy, not
building new capability.
