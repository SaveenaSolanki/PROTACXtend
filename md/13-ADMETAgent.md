# 13 · ADMETAgent

| | |
| --- | --- |
| **Node** | 13 — `predict_admet` |
| **Source** | `synglue_agent/agents/admet_agent.py` |
| **Size** | 20 lines agent → `admet_predictors.py` (343 lines) |
| **Status** | ✅ Built — RDKit + unit test |
| **NP-hard coverage** | Problem #8 (bRo5 permeability × potency) — *built* |

## Architecture brief

Computes developability. A 20-line agent over a 343-line predictor — one of the cleanest
delegation ratios in the codebase.

Two tiers of output, and the distinction matters:

- **Computed descriptors** — MW, logP, TPSA, HBD, HBA, RotB. These are RDKit calculations
  on the molecular graph. They are exact.
- **Proxy risk flags** — hERG, AMES, DILI, Caco-2 permeability, oral bioavailability.
  These are *proxies*, labelled as such in the source documentation. They are estimates.

The agent also scores bRo5 compliance, which is the scientifically correct framing:
PROTACs violate Lipinski's Rule of 5 by construction (MW 700–1200, TPSA 150–300, RotB
10–25), so applying conventional drug-likeness filters would reject every valid candidate.
The project's NP-hard analysis identifies permeability × potency as a genuine Pareto
frontier with no single optimum, and treats it accordingly.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.valid_candidates` | `list[CandidateRecord]` | node 11 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.admet_predictions` | `list[ADMETPrediction]` | MW, logP, TPSA, HBD, HBA, RotB, hERG, AMES, DILI, Caco-2, F<sub>oral</sub> |

Toolbox: `predict_admet`, `_risk_label`.

## What is solid

- **bRo5-aware rather than Ro5-aware.** This is the correct scientific framing for PROTACs
  and it is easy to get wrong. The project gets it right.
- **The descriptor half is exact.** MW, logP, TPSA, HBD, HBA and RotB are deterministic
  RDKit computations, not predictions — this is the most trustworthy numeric output
  anywhere in the pipeline.
- **Proxies are labelled as proxies** in the documentation rather than presented as
  predictions.
- **Excellent delegation ratio** — 20 lines of agent over 343 lines of predictor.
- **Cheap and deterministic**, so it can run on every candidate without a budget concern.
- **Addresses NP-hard problem #8** and is marked "built" rather than partial.

## What to improve

**1 · Separate exact descriptors from proxy estimates in the output schema.** They
currently sit side by side in one `ADMETPrediction`. A downstream consumer — or a reader
of the report — cannot tell that MW is a calculation and DILI risk is a guess. Tag each
field with its provenance, or split the model in two. This is the most important change
here and it is small.

**2 · Validate the proxies, or downgrade them.** hERG, AMES, DILI and Caco-2 proxies have
no stated basis, no training set and no reported accuracy. For PROTACs specifically, proxies
trained on conventional small molecules are outside their applicability domain by
construction — a 974 Da bRo5 molecule is not what a Caco-2 model saw in training. Either
benchmark them on known PROTACs or present them as unvalidated heuristics.

**3 · Wire in the established external predictors.** The Agent_Modules sheet names
SwissADME, ADMETlab and pkCSM as the intended tools for this agent. None appear in the
implemented tool list. These are free, well-validated, and would replace home-grown proxies
with citable numbers — a high-credibility, medium-effort win.

**4 · Model chameleonicity.** PROTACs achieve permeability through conformational
adaptation — collapsing to shield polar surface area in membrane environments. 2D TPSA
cannot see this, and the project's own analysis notes chameleon behaviour is "not
predictable from 2D". A 3D descriptor set would materially improve the permeability call.

**5 · Make bRo5 scoring a soft gradient, not a threshold.** Since PROTACs sit on a Pareto
frontier rather than a pass/fail line, the score fed to ranking should be continuous and
paired with the potency trade-off, not a compliance flag.

**6 · Report a per-candidate developability summary.** With 11 fields per candidate the
report needs one interpretable roll-up — a developability tier — or the reader cannot use
the table.

## Feasibility note

This is one of the strongest agents in the system, so the improvements are refinements
rather than repairs. Item 1 is small and should be done. Item 3 is the highest-value
change: swapping unvalidated in-house proxies for SwissADME/ADMETlab converts the weakest
half of this agent's output into something defensible, and both are free.
