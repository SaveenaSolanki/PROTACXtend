# 15 · ApplicabilityDomainAgent

| | |
| --- | --- |
| **Node** | 15 — `assess_applicability_domain` |
| **Source** | `synglue_agent/agents/prediction_agent.py` (shared with node 12) |
| **Size** | **not recorded** — `applicability_domain.py` is 30 lines |
| **Status** | ✅ Built — but undocumented and untracked |
| **Documentation** | ❌ Absent from `AGENT_API.md` **and** from the Implementation_Status sheet |

## Architecture brief

Scores whether each candidate falls inside the region of chemical space the upstream models
were built on, and labels it in-domain or out-of-domain.

Conceptually this is one of the most valuable agents in the system, because it is the node
that is supposed to say *"do not trust the prediction you just made."* Given that node 12
is an unvalidated heuristic and node 13's tox flags are proxies, an honest applicability
domain is what separates a defensible output from an overclaim.

**It is also the least visible agent in the project.** It is missing from `AGENT_API.md`,
missing from the Implementation_Status sheet, and its line count is recorded as `—` in the
architecture summary. The underlying tool is 30 lines. For a node whose job is to bound the
credibility of everything around it, that is a striking mismatch between importance and
investment.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.valid_candidates` | `list[CandidateRecord]` | node 11 |
| upstream predictions | implied | nodes 12–14 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.applicability_domain` | `list[ApplicabilityDomainResult]` | domain score + in/out label |

Toolbox: `compute_applicability_domain`, `compute_applicability_domain_score`,
`assign_domain_status`.

## What is solid

- **The concept is exactly right**, and most pipelines of this kind omit it entirely.
  Including an applicability domain node at all shows genuine methodological awareness.
- **Emits both a continuous score and a categorical label**, so consumers can use either a
  threshold or a gradient.
- **Positioned after all three prediction nodes**, so it can in principle assess the domain
  of each.
- **Three dedicated toolbox methods**, so the logic is shared rather than inlined.

## What to improve

**1 · Establish what domain is actually being measured — this is the core question.** An
applicability domain is defined *relative to a training set*. Node 12 is a heuristic with
no training set; node 13's descriptors are exact calculations with no domain limit; node
13's tox proxies have an unstated one. So it is genuinely unclear what reference
distribution this node compares against. Until that is written down, the in/out label
cannot be interpreted. **Resolve this before improving anything else here.**

**2 · Make the label actually gate something.** A domain flag that no node acts on is
decoration. Out-of-domain candidates should either be suppressed from the final ranking or
carry a visible warning through to the report. Node 12 in particular should refuse to emit
a confident DC₅₀ for an out-of-domain molecule.

**3 · Compute per-prediction domains, not one global score.** A candidate can be well inside
the domain for ADMET descriptors and far outside it for degradation prediction. One label
for all three predictions loses the distinction that matters most.

**4 · Document it (objective O-7).** Add an `AGENT_API.md` entry with reads/sets, and add
the row to the Implementation_Status sheet. It is currently invisible in two of the three
places the project tracks its own agents.

**5 · Record the line count and locate the code.** The architecture summary lists `—`. The
agent appears to share `prediction_agent.py` with node 12 (39 lines total for both). If a
30-line tool and a shared agent are the whole implementation, that should be stated so the
component is not assumed to be more substantial than it is.

**6 · Use the 485K seed database as a reference distribution.** If a domain needs an
empirical chemical-space reference, the project already owns the largest one in the
pipeline. It is the obvious candidate and it is unused here.

## Feasibility note

Items 1 and 4 are small and unblocked and should be done together — the first makes the
output interpretable, the second makes the agent visible. Item 2 is what converts this from
a reported number into a working safeguard, and it is the change that most improves the
project's defensibility, because it is the mechanism by which the system declines to
overclaim.
