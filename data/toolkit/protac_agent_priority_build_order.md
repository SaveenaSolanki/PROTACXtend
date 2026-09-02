# PROTAC Agent Priority Build Order

## Revised Audit Counts
- Workflow modules audited: 17
- Executable verified modules: 0
- Executable not tested modules: 4
- Heuristic stubs: 9
- Local-demo-data-only modules: 4
- Registered-only/planned primary modules: 0

## Top 10 Missing Components
1. Trained DC50 model wrapper with model/version/provenance.
2. Trained Dmax model wrapper with uncertainty.
3. Patent/IP novelty search wrapper.
4. BindingDB local/API binder mining source.
5. Validated ADME/Tox endpoint models for hERG/AMES/DILI/solubility.
6. Retrosynthesis route planner wrapper.
7. Ternary docking execution wrapper with explicit skipped/run status.
8. Structure preparation and ligand pose sourcing pipeline.
9. E3 tissue/cell-context expression source.
10. Applicability-domain and calibration layer for ranking.

## Top 10 P0 Truthfulness Fixes
1. Rename/report DC50 and Dmax as heuristic unless a trained model is loaded.
2. Add tool_status, evidence_type, and limitation per score in final reports.
3. Mark ternary feasibility as geometry proxy unless docking actually ran.
4. Mark novelty/IP as local similarity only unless patent search ran.
5. Mark ADME/Tox endpoint risks as descriptor/rule-based unless model/API used.
6. Add per-score provenance to candidate JSON/table exports.
7. Add per-score uncertainty/confidence source labels.
8. Prevent ranking from hiding heuristic upstream inputs.
9. Add report tests for forbidden overclaims.
10. Ensure executable_not_tested is never counted as executable_verified.

## Top 10 P1 Core Build Items
1. Unified schema for target provenance.
2. UniProt target loader with local fallback labeling.
3. ChEMBL binder mining wrapper.
4. BindingDB loader/API adapter.
5. PubChem compound resolution and similarity wrapper.
6. E3 ligand table schema and validation.
7. Exit-vector curated map loader.
8. RDKit assembly validation gate.
9. Basic novelty exact/similarity check.
10. Basic ADME descriptor output with RDKit-only claim language.

## Top 10 P2 Model Integrations
1. PROTAC-Degradation-Predictor wrapper.
2. DeepPROTACs/PROTAC-STAN adapter evaluation.
3. DC50 uncertainty wrapper.
4. Dmax uncertainty wrapper.
5. Applicability-domain estimator.
6. hERG model wrapper.
7. AMES model wrapper.
8. DILI model wrapper.
9. Solubility/permeability model wrapper.
10. Calibrated ranking confidence aggregation.

## Exact Next 5 Coding Tasks
1. Add report-level truthfulness fields: tool_status, evidence_type, limitation, provenance, and uncertainty_source for every score.
2. Split degradation outputs into heuristic_dc50_nM and heuristic_dmax_percent until a trained model backend is loaded.
3. Add local schema-validated loaders for target, E3 ligand, linker, PROTAC-DB/PROTACpedia, and known-PROTAC tables.
4. Implement core ChEMBL/PubChem/BindingDB wrappers behind safe structured result objects, with no silent fallback claims.
5. Add tests that fail if reports claim trained prediction, docking, patent safety, or ML ADME/Tox without executable evidence.

## Coding Phases

### Phase 0: Truthfulness and report-label corrections
- Add per-score tool_status, evidence_type, limitation, provenance, and uncertainty_source fields.
- Rename DC50/Dmax report columns or labels to heuristic until trained model backends are loaded.
- Add forbidden-claim tests and executable-count tests.

### Phase 1: Executable local data loaders and schemas
- Validate CSV schemas for targets, E3 ligands, linkers, known PROTACs, PROTAC-DB, and PROTACpedia local files.
- Require local_demo_data_only labels whenever only local seed/demo rows are used.
- Add candidate score provenance object to candidate JSON/table exports.

### Phase 2: Core wrappers for UniProt, ChEMBL, PubChem, local PROTAC databases, RDKit validation
- Connect source-labeled target, binder, chemistry, novelty, and assembly wrappers behind structured result objects.
- Mock external calls in tests; do not call APIs by default.
- Make wrapper failure modes explicit and non-silent.

### Phase 3: Validated prediction model wrappers for DC50, Dmax, ADME/Tox
- Load trained model artifacts only when explicitly configured.
- Record model version, training metadata pointer, uncertainty, and applicability domain.
- Keep heuristic and descriptor-rule fallbacks clearly labeled.

### Phase 4: Ternary feasibility and docking as optional heavy modules
- Keep docking/structure modules disabled/manual by default.
- Add wrapper contracts for protein prep, ligand prep, docking, ternary modeling, and interface scoring.
- Never report docking scores when docking did not run.

### Phase 5: Agent orchestration and ranking with uncertainty/provenance gates
- Block strong claims from heuristic/local-demo upstream scores.
- Aggregate score provenance into ranking confidence.
- Require human-review packet before any synthesis or experimental recommendation language.

## Forbidden-Claim Test Backlog
- Fail if heuristic DC50/Dmax is described as a trained model prediction.
- Fail if ternary feasibility is described as docking/modeling when docking_status is skipped or not run.
- Fail if novelty/IP is described as patent-safe when patent search did not run.
- Fail if ADME/Tox endpoint risk is described as ML/API-predicted when backend is descriptor/rule/heuristic.
- Fail if ranking confidence omits upstream heuristic/local-demo provenance.
- Fail if final reports omit tool_status, evidence_type, or limitation for any score.
- Fail if candidate JSON lacks per-score provenance fields.
- Fail if executable_not_tested is counted as executable_verified.
