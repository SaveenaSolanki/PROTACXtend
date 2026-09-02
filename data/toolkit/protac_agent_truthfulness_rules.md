# PROTAC Agent Truthfulness Rules

## Hard Rules
- Never call heuristic DC50/Dmax values “predicted by trained model”.
- Never report ternary feasibility as real if docking/model was skipped.
- Never report novelty/IP as patent-safe unless patent search actually ran.
- Never report ADME/Tox endpoint as ML-predicted unless a model/API was used.
- Every candidate must carry provenance fields for each score.
- Every final report must include `tool_status`, `evidence_type`, and `limitation` per score.
- `executable_not_tested` must never be counted as `executable_verified`.

## Required Candidate Score Provenance Fields
- `score_name`
- `score_value`
- `evidence_type`
- `tool_status`
- `source_tool_or_database`
- `source_file_or_url`
- `model_version`
- `run_timestamp`
- `input_hash`
- `limitations`
- `confidence`
- `uncertainty`
- `applicability_domain`
- `claim_allowed`

## Evidence Labels
- `trained_model`: versioned model artifact loaded and used.
- `external_api`: source API called successfully and response provenance recorded.
- `local_database`: local curated or licensed data source used.
- `rdkit_descriptor`: RDKit descriptor or fingerprint computation used.
- `heuristic_proxy`: deterministic/rule/demo score only.
- `not_run`: component intentionally skipped.
- `missing`: required component unavailable.

## Forbidden-Claim Tests To Implement
- Fail if heuristic DC50/Dmax is described as a trained model prediction.
- Fail if ternary feasibility is described as docking/modeling when docking_status is skipped or not run.
- Fail if novelty/IP is described as patent-safe when patent search did not run.
- Fail if ADME/Tox endpoint risk is described as ML/API-predicted when backend is descriptor/rule/heuristic.
- Fail if ranking confidence omits upstream heuristic/local-demo provenance.
- Fail if final reports omit tool_status, evidence_type, or limitation for any score.
- Fail if candidate JSON lacks per-score provenance fields.
- Fail if executable_not_tested is counted as executable_verified.

## Claim Language Defaults
- Use “heuristic proxy” for current DC50, Dmax, ADME/Tox endpoint risks, ternary feasibility, retrosynthesis, ranking confidence, and evolution outputs unless stronger evidence is recorded.
- Use “local similarity check” for current novelty/IP output unless patent and public chemistry searches run.
- Use “local curated/demo data” for binders, E3 ligands, and linkers unless source wrappers produce successful records.
