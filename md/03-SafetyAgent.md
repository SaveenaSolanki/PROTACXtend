# 03 · SafetyAgent

| | |
| --- | --- |
| **Node** | 3 — `safety_precheck` |
| **Source** | `synglue_agent/agents/safety_agent.py` |
| **Size** | 55 lines |
| **Status** | ✅ Built |
| **Delegates to** | `toolbox.safety_precheck`, RDKit, pattern matching |

## Architecture brief

The gate between intake and chemistry. It runs after parsing and before any structure is
resolved or any molecule is built, and its job is to catch three classes of problem early:
hazardous structural patterns, SMILES that RDKit cannot parse, and targets that do not
make sense as degradation objectives.

Architecturally it is a *soft* gate — it writes to `state.warnings` rather than halting the
run. That is a defensible choice for a research tool (a warning that stops an exploratory
run is worse than one that annotates it), but it means the warnings must actually reach
the reader, which depends entirely on node 22 surfacing them.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.user_request` | `str` | caller |
| `state.parsed_objective.warhead_smiles` | `str` | node 1 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.warnings` | `list[str]` | hazard patterns, invalid SMILES, unreasonable targets |
| `state.traces` | `list[AgentTrace]` | checks performed |

## What is solid

- **Correct position in the graph.** Fails cheap, before API calls and before assembly.
- **RDKit-backed SMILES validation** is real validation, not a regex — an unparseable
  warhead is caught here rather than surfacing as a confusing failure at node 10.
- **Non-blocking by design**, which suits an exploratory research workflow.
- **Cheap.** Adds no measurable time to a run.

## What to improve

**1 · Give warnings a severity and a code.** `list[str]` cannot be filtered, counted or
acted on. A `SafetyWarning` model with `severity` (info / warn / block), a stable `code`,
and the offending value would let node 22 rank them and let node 2 define a stop condition
on "any blocking warning". Today a critical warning and a cosmetic one are the same type.

**2 · Decide what is genuinely blocking.** An unparseable warhead SMILES cannot produce a
valid PROTAC — every downstream node will fail or silently drop it. That case should halt
the run rather than warn, or the run wastes 20 nodes producing nothing.

**3 · Validate the E3 ligand SMILES too.** The agent reads
`parsed_objective.warhead_smiles` but not `e3_ligand_smiles`. A user-supplied E3 ligand
gets no validation until node 10 tries to assemble with it. Symmetrical treatment is a
few lines.

**4 · Publish the hazard pattern list.** The patterns are embedded in 55 lines of code with
no documentation of what is screened for. For a tool that makes safety claims, the
screened set should be an explicit, reviewable, versioned list — and ideally cite its
source (PAINS, structural alerts, reactive-group filters).

**5 · Add PROTAC-appropriate checks.** The current screen appears to be generic small-molecule
safety. PROTACs are bRo5 by construction, so generic alerts will both over- and under-fire.
Worth screening explicitly for reactive linker chemistry and for warheads with known
promiscuity (the foretinib/133-kinase case from the NP-hard analysis is exactly the risk
this node should flag).

**6 · Test the negative path.** Confirm that a known-bad SMILES and a known hazard pattern
actually produce warnings. Gate code that has never been observed failing is gate code
that may not work.

## Feasibility note

All six are small and unblocked. Items 1 and 2 matter most: they convert a warning channel
nobody can act on into one the planner and the report can both consume.
