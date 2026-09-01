# 04 · TargetResolverAgent

| | |
| --- | --- |
| **Node** | 4 — `resolve_target` |
| **Source** | `synglue_agent/agents/target_agent.py` |
| **Size** | 83 lines |
| **Status** | ✅ Built — verified by live API call |
| **Tools** | `uniprot_lookup.py` (233 lines), `alphafold_client.py` (14 lines) |

## Architecture brief

The first agent that leaves the machine. It turns a human target name ("HMGB2") into a
database identity — UniProt accession, gene symbol, organism — and attaches a predicted
structure from AlphaFold.

This is the node where the run stops being about text and starts being about a specific
protein. Everything structural downstream (exit vectors at node 8, ternary feasibility at
node 20) traces back to the structure this agent selects.

Both APIs are free and unauthenticated, rate-limited to 2 req/s with a 30 s timeout and 5
retries with exponential backoff.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.parsed_objective.target_name` | `str` | node 1 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.target_record` | `TargetRecord` | `uniprot_id`, `gene_symbol`, `alphafold_id`, `organism` |
| `state.traces` | `list[AgentTrace]` | queries and hits |

Consumed by node 5 (binder retrieval keys off `uniprot_id`) and by node 20.

## What is solid

- **Live, verified integration.** Not a mock — the case study resolved HMGB2 against the
  real UniProt REST API.
- **Free and unauthenticated**, so the pipeline has no credential dependency and no cost
  per run at this step.
- **Proper rate limiting and backoff**, which is why a 100-record binder sweep at node 5
  does not get the project blocked.
- **AlphaFold coverage** means a target without an experimental structure still gets one,
  which is what makes the geometric ternary proxy runnable for most targets.

## What to improve

**1 · Record structure provenance and quality, not just an ID.** `alphafold_id` says
nothing about whether the region that matters is well-predicted. AlphaFold pLDDT is
per-residue and freely available — a low-confidence binding site should be visible to node
20 and to the reader, because a ternary feasibility score computed on a disordered region
is not meaningful. This is the highest-value change here.

**2 · Prefer experimental structure when one exists.** `rcsb_pdb_lookup.py` (266 lines)
already exists in the toolbox but this agent goes to AlphaFold. For a target with a good
PDB entry the experimental structure is strictly better. Query RCSB first, fall back to
AlphaFold, and record which was used.

**3 · Handle ambiguous and non-human hits explicitly.** A gene symbol can resolve to
multiple accessions across organisms. The record has an `organism` field but no documented
disambiguation policy. Make the choice explicit and surface it as a warning when more than
one plausible hit existed.

**4 · Carry isoform and mutation context.** The Agent_Modules sheet specifies that the
target agent "includes isoform/mutation context"; `TargetRecord` as documented does not
carry it. For a degradation target this matters — isoforms differ in the surface lysines
node 20 cares about.

**5 · Cache resolutions to disk.** Target resolution is deterministic and the same targets
recur across runs. A local cache removes network dependence from the most-repeated step
and makes offline reruns of the case study possible.

**6 · Degrade gracefully when both APIs are down.** Define what the run does with no
structure — proceed with sequence-only reasoning and a warning, or stop. Currently
undocumented.

## Feasibility note

Items 1 and 2 are small, unblocked, and directly improve the credibility of node 20's
output — the pLDDT check in particular is a few lines against an API already being called.
Item 4 is the only one that may require a schema change.
