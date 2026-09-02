# 02 · DesignPlannerAgent

| | |
| --- | --- |
| **Node** | 2 — `create_design_plan` |
| **Source** | `synglue_agent/agents/design_planner_agent.py` |
| **Size** | 152 lines — **second-largest agent in the system** |
| **Status** | ✅ Built |
| **Documentation** | ❌ Absent from `AGENT_API.md` |

## Architecture brief

The policy engine. It decides which tools the run will call, how many retries each gets,
and the conditions under which the workflow stops early. Every other agent executes;
this one decides what execution looks like.

At 152 lines it is second only to `TargetBinderRetrievalAgent` (300) and
`TernaryFeasibilityAgent` (597) among the agents, and unlike those two its size is pure
control logic rather than API or subprocess plumbing. It is the closest thing the system
has to a scheduler.

**It is undocumented.** `AGENT_API.md` covers 18 agents and this is not one of them —
which means the component that governs the whole graph's behaviour has no published
contract. That is the single most consequential documentation gap in the project.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.parsed_objective` | `ParsedObjective` | node 1 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.design_plan` | `dict` | `status`, `tools_to_call`, `stop_conditions`, retry policy |
| `state.traces` | `list[AgentTrace]` | planning decisions |

`design_plan` is a plain `dict`, not one of the 19 Pydantic models — see improvement 1.

## What is solid

- **The right thing exists at all.** Most agent pipelines hard-code their tool sequence.
  Having retry and stop conditions as first-class, inspectable data is a genuine strength.
- **Runs before any expensive work.** Positioned at node 2, so a plan that rules out the
  ternary backend saves hours rather than discovering the problem at node 20.
- **Separates policy from mechanism.** Agents stay thin because the decisions live here.

## What to improve

**1 · Give `design_plan` a Pydantic schema.** It is the only major state field that is an
untyped `dict` while 19 sibling models are typed. That means no validation, no IDE
support, and no guarantee that a stop condition the planner writes is one the graph knows
how to read. This is a contained, mechanical fix.

**2 · Document the contract (objective O-7).** Publish the tool vocabulary, the retry
semantics, and the full set of stop conditions in `AGENT_API.md`. Nobody outside the
original author can currently reason about what this agent will do.

**3 · Make the plan auditable against what actually ran.** Emit a plan-versus-actual
comparison into `pipeline_status`: which planned tools ran, which were skipped, which
stop condition fired. Right now the plan is written and never reconciled.

**4 · Add a cost model for the expensive branches.** The planner decides whether node 20
uses the geometric proxy (< 1 s) or P4ward (2–4 h). That is a four-order-of-magnitude
decision made without an explicit budget input. Let the caller pass a time or compute
budget and have the planner honour it.

**5 · Make stop conditions test-covered.** Retry and early-stop logic is exactly the code
that only executes on the unhappy path, so it is exactly the code most likely to be wrong
in production. Add tests that force each stop condition to fire.

**6 · Let the plan be overridden.** For the case study workflow it would be valuable to
pin a plan explicitly rather than have it inferred, so an experiment can be repeated
exactly. Accept an optional caller-supplied plan that bypasses inference.

## Feasibility note

Items 1, 2 and 3 are small and unblocked, and they raise the reliability of the whole
graph rather than one node — the best leverage available in the intake phase. Item 4
depends on nothing but is worth doing before any large P4ward campaign, since it is what
prevents an accidental multi-day run.
