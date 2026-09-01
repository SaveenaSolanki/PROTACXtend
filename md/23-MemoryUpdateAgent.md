# 23 · MemoryUpdateAgent

| | |
| --- | --- |
| **Node** | 23 — `update_memory` (terminal node) |
| **Source** | not listed in the documented file tree — see improvement 5 |
| **Size** | 21 lines agent → `memory_manager.py` (31 lines) |
| **Status** | ✅ Built |
| **Delegates to** | `toolbox.write_workflow_memory()` |
| **Documentation** | ❌ Absent from `AGENT_API.md` |

## Architecture brief

The terminal node. It persists a summary of the completed run to durable local storage so
that later runs, and later readers, can reference what has already been attempted.

It is the smallest component in the pipeline — 21 lines of agent over a 31-line manager,
52 lines in total — and it carries the project's only mechanism for accumulating knowledge
across runs. Everything else in the system is stateless between invocations: each run
resolves the same targets, re-queries the same APIs, and rediscovers the same candidates
from scratch.

That framing matters for a project whose central problem is search over a 150K+ candidate
space at $5K–$50K and 2–6 weeks per real evaluation. **Memory is the difference between
a tool that searches and a tool that learns**, and at 52 lines it is currently the former.

The Agent_Modules sheet lists Redis and Qdrant as intended supervisor infrastructure —
Qdrant being a vector database, which implies an intended semantic-retrieval memory well
beyond what is built.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| final `WorkflowState` | `WorkflowState` | all nodes |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| memory file path | `str` | location of the persisted run summary |

Written via `memory_manager.py` to local persistent storage.

## What is solid

- **It exists and it runs last**, so it captures the complete final state rather than a
  partial one.
- **Durable local persistence** with no external service dependency — appropriate for the
  project's current stage and consistent with its no-credentials design.
- **Returns the file path**, so the run's output location is discoverable
  programmatically.
- **Correctly minimal** for what it currently promises. The critique below is about
  ambition, not about defects in what was built.

## What to improve

**1 · Define what is actually stored.** "Workflow memory" is undocumented. A summary? The
full state? The ranked candidates? Without knowing, no future run can rely on it. This is
the prerequisite for everything else here.

**2 · Make it readable by node 1 or node 2, not just writable.** Memory that is written and
never read is a log, not a memory. The obvious use is deduplication across runs: if this
warhead–E3–linker combination was evaluated last week and scored poorly, the planner should
know before spending compute. **This is the change that converts the node from
record-keeping into capability.**

**3 · Store negative results deliberately.** The project's most valuable findings are
rejections — H1 and H3, 0/3,600 poses. Those are expensive to obtain and trivially easy to
repeat by accident. A memory that records "this exit vector does not work, and here is the
evidence" prevents rediscovering a known dead end.

**4 · Key it on canonical structure.** Memory keyed on target name or free text will miss
matches. Key on InChIKey plus target UniProt ID so lookups are exact — `_stable_id` and
`canonicalize_smiles` already exist in the toolbox.

**5 · Locate and document the source file.** The agent does not appear in the documented
file tree in `ARCHITECTURE_SUMMARY.md` §11, which lists 21 agent files, and it has no
`AGENT_API.md` entry (objective O-7). For the node that owns cross-run persistence, both
gaps should be closed.

**6 · Handle write failure explicitly.** As the terminal node, a silent failure here loses
the run's record after all the work is complete. It should raise, or at minimum warn into
the report.

**7 · Consider the vector-store path deliberately — or descope it.** Qdrant is named in the
intended architecture and would enable semantic retrieval over past runs. That is a real
capability, and also a substantial build. Worth an explicit decision rather than leaving it
as an implied gap.

## Feasibility note

Items 1, 4, 5 and 6 are small and unblocked. Items 2 and 3 are the valuable ones: making
memory readable and recording negative results is a modest amount of work that changes what
the system is capable of, and it directly serves a project whose core difficulty is
avoiding wasted evaluations in an intractably large search space.
