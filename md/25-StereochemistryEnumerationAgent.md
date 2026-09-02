# StereochemistryEnumerationAgent

| Field | Value |
| --- | --- |
| **Node** | 12 - `expand_stereoisomers` |
| **Source** | `synglue_agent/agents/search_control_agent.py` |
| **Toolbox methods** | `expand_stereoisomers_controlled` |
| **Status** | Implemented |

## Purpose

Keeps stereoisomers explicitly represented without multiplying the candidate pool beyond the controlled construction budget.

## Reads

- `state.assembled_candidates`
- `state.search_policy.stereoisomer_budget_per_candidate`
- `state.search_policy.construction_budget`

## Writes

- `state.assembled_candidates`
- `state.warnings` when expansion changes the pool size

## Logic

- enumerates only capped undefined stereocenters;
- preserves separate candidate identifiers for stereoisomers;
- flags candidates that require separate stereochemical scoring.

## Caveat

This protects against silent stereochemistry loss. It still depends on upstream component SMILES preserving correct stereo marks.
