# 01 · SupervisorAgent

| | |
| --- | --- |
| **Node** | 1 — `parse_user_request` |
| **Source** | `synglue_agent/agents/supervisor_agent.py` |
| **Size** | 59 lines |
| **Status** | ✅ Built — verified by unit test |
| **Delegates to** | `toolbox.parse_user_request` |

## Architecture brief

The entry agent. It converts one line of free English into the structured object every
downstream node reads. Nothing in the graph runs until this succeeds, and every later
node's behaviour is a function of what this agent decided the user asked for.

It is deliberately thin — 59 lines — because the parsing logic lives in the 73-method
toolbox. The agent's own job is state mutation: read `user_request`, write
`parsed_objective`, append a trace.

This is the widest failure surface in the system relative to its size. A misparse here
does not raise an error; it silently designs the wrong molecule for the wrong target.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.user_request` | `str` — free natural language | caller |

Example: `"Design a PROTAC for HMGB2 with ICM warhead and CRBN E3"`

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.parsed_objective` | `ParsedObjective` | `target_name`, `warhead_smiles`, `e3_ligase`, `e3_ligand_smiles`, `preferred_linker_types` |
| `state.traces` | `list[AgentTrace]` | thought / action / observation for this step |

All fields are optional in practice — an unspecified E3 or warhead flows downstream as a
blank that nodes 6 and 7 fill from the curated libraries.

## What is solid

- **Correct architectural position.** One parse, one structured object, no re-parsing
  downstream. No later node touches the raw string.
- **Thin by design.** Parsing logic is centralised in the toolbox, so it can be improved
  without touching the graph.
- **Traced.** Every parse writes an `AgentTrace`, so a wrong run can be diagnosed from the
  report rather than re-run.
- **Unit tested**, and the HMGB2/ICM/CRBN case study exercises it end to end.

## What to improve

**1 · Return a confidence and an echo, not just a parse.** The agent currently emits a
`ParsedObjective` with no indication of how much of it was inferred versus stated. Add a
per-field confidence and a human-readable restatement ("target HMGB2; warhead from user
SMILES; E3 CRBN; linker unspecified → library default") that the report can surface. A
silent misparse becomes a visible one.

**2 · Validate the target name before committing to it.** Node 4 resolves the name against
UniProt. If that resolution fails or returns an ambiguous hit, the run has already spent
five nodes. Have the supervisor do a cheap existence check, or have node 4 be allowed to
push a correction back into `parsed_objective`.

**3 · Handle the multi-target and multi-warhead case explicitly.** The schema assumes one
target and one warhead. A request naming two candidate warheads either drops one or fails
opaquely. Either widen the schema to lists or reject the request with a clear message.

**4 · Separate "not specified" from "specified as empty".** Downstream nodes cannot
currently distinguish a user who said nothing about the linker from one who asked for no
preference. Use explicit sentinels so node 9 can behave differently in the two cases.

**5 · Pin the parse to a versioned prompt or ruleset.** If parsing is LLM-mediated, record
the model and prompt version in the trace so an old run can be reproduced. This is
required for the provenance claim the project makes.

## Feasibility note

All five improvements are small and unblocked — no new data, no new science. Items 1 and 2
are the highest value per hour of work, because they convert the system's most dangerous
silent failure into a loud one.
