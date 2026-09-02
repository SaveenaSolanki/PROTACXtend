# 22 · ReportAgent

| | |
| --- | --- |
| **Node** | 22 — `generate_report` |
| **Source** | `synglue_agent/agents/report_agent.py` |
| **Size** | 20 lines agent → `report_generator.py` (58 lines) |
| **Status** | ✅ Built — unit tested |
| **Delegates to** | `toolbox.generate_markdown_report()`, `export_csv()`, `export_json()` |

## Architecture brief

The only agent that reads the entire state. Every other node consumes a few named fields;
this one takes all 24 and produces the artefacts a human actually receives — a markdown
report, a CSV and a JSON export.

That makes it the system's whole user interface. Twenty-two nodes of careful chemistry are
worth exactly as much as this node manages to communicate. If a caveat is not surfaced
here, it does not exist as far as the reader is concerned — and this pipeline has a lot of
caveats that need surfacing: a heuristic DC₅₀, proxy tox flags, a 4-molecule novelty
comparison, 4 of 600 E3 ligases, and an unexecuted P4ward backend.

At 20 lines over a 58-line generator, it is the thinnest treatment of the most
communication-critical job in the project.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| **all state fields** | `WorkflowState` | every node |

Including `warnings` (node 3), `reflection_reviews` (node 18), `applicability_domain`
(node 15), `traces` and `pipeline_status` (every node).

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.report` | `str` | markdown report |
| `state.pipeline_status` | `list[dict]` | step-by-step execution table |
| CSV export | file | candidate table |
| JSON export | file | full structured results |

Toolbox: `generate_candidate_table`, `generate_agent_workflow_table`,
`generate_pipeline_status_table`, `generate_markdown_report`, `export_csv`, `export_json`.

## What is solid

- **Three formats** — markdown to read, CSV for a spreadsheet, JSON for a downstream
  program. Correct, and it costs nothing to do all three.
- **The pipeline status table** is genuinely valuable: a step-by-step record of what ran,
  which is rare and directly supports the provenance claim.
- **It reads everything**, so nothing in the state is structurally unreportable.
- **Dedicated table generators** for candidates, workflow and status, so formatting is
  consistent and reusable.
- **Thin agent over shared toolbox methods**, consistent with the rest of the codebase.

## What to improve

**1 · Surface the caveats, prominently and automatically.** This is the most important
change in the entire agent set for the project's credibility. The report should lead with
a limitations block generated from recorded fact, not from an author's memory:

> Degradation predicted by `SynGlue-demo-heuristic-v0.1` (no trained model, unvalidated).
> Novelty assessed against 4 reference molecules. E3 selection drawn from 4 of 600+
> ligases. hERG/AMES/DILI are proxy estimates. Ternary result from geometric proxy;
> P4ward not run. Structure from AlphaFold (mean pLDDT nn).

Every one of those facts is already in the state. None of them appear to reach the reader.
A ranked table of PROTAC candidates with DC₅₀ values, presented without that block, reads
as far more authoritative than the pipeline can support.

**2 · Report the negative result properly.** The case study's best output was a rejection —
H1 and H3 disproved. The report format is candidate-table-shaped, which biases toward
presenting *something*. "No viable candidate, and here is the evidence" must be a
first-class report type.

**3 · Include the denominators.** 12 candidates from a 150K+ linker space; 192 combinations
scanned; 4 of 600 ligases; 100 of *n* binders retrieved. Coverage numbers are what let a
reader calibrate the result, and they are currently absent.

**4 · Propagate warnings and reviews into the output.** `warnings` (node 3),
`reflection_reviews` (node 18) and `applicability_domain` (node 15) all exist in state.
Confirm each actually reaches the markdown — an out-of-domain candidate presented without
its flag is precisely the overclaim node 18 was built to prevent.

**5 · Version and timestamp every report.** Record the toolbox version, the heuristic model
ID, the data-file versions and the run timestamp, so a result can be reproduced and dated.

**6 · Add the visual output the project already expects.** The Agent_Modules sheet specifies
"PyMOL images, spreadsheet export" and a "wet-lab ready summary"; the outputs directory
already holds PyMOL renderings from the case study. Ternary poses are far easier to
evaluate visually than numerically.

**7 · Grow the agent to match its importance.** 20 lines over a 58-line generator is thin
for the component that determines how the entire system is perceived and used.

## Feasibility note

Item 1 is small, entirely unblocked, and is the single highest-value change available
anywhere in the project for scientific credibility — all the required facts are already in
the state object and simply need to be printed. Items 2, 3 and 4 are also small and follow
naturally from the same work.
