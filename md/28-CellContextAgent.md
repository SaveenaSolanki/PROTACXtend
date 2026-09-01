# CellContextAgent

| Field | Value |
| --- | --- |
| **Node** | 14 - `score_cell_context` |
| **Source** | `synglue_agent/agents/context_agent.py` |
| **Toolbox methods** | `score_e3_context` |
| **Status** | Implemented with curated/default priors |

## Purpose

Makes cell-type dependence explicit instead of treating every target/E3 pair as equally available in every cell.

## Reads

- `state.valid_candidates`
- `state.target_record`
- `state.parsed_objective.cell_line`
- `state.parsed_objective.expression_overrides`

## Writes

- `state.e3_context_predictions`

## Logic

Scores E3 expression, target/E3 localization fit, curated ligand availability, structural support, and resistance/contraindication risk. User-provided expression overrides are accepted and marked as user-supplied context.

## Caveat

The current implementation uses curated defaults and explicit overrides. It does not yet query DepMap, Human Protein Atlas, GTEx, ProteomicsDB, or cell-line proteomics live.
