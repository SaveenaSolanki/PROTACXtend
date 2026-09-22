#!/usr/bin/env python3
"""Generate machine-readable audit tables for the PROTACxtend next-version audit.

Every value here is either (a) read from the repository, (b) measured during the
audit run, or (c) explicitly labelled as a proposed/design value. No performance
number is invented.
"""
from __future__ import annotations

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parent / "csv"
OUT.mkdir(parents=True, exist_ok=True)


def write(name: str, header: list[str], rows: list[list]) -> None:
    with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {name}: {len(rows)} rows")


# ── 1. repository census (AST-measured) ─────────────────────────────────
write(
    "repo_census.csv",
    ["path", "py_files", "classes", "functions", "lines", "implementation_status", "major_concern"],
    [
        ["protacxtend/tools", 95, 66, 822, 23465, "IMPLEMENTED (mixed maturity)", "many thin wrappers; some demo/heuristic; no per-tool scientific validation"],
        ["protacxtend/modules", 82, 70, 439, 10427, "IMPLEMENTED (mixed)", "resistance_mechanisms is a 41-line heuristic with no tests; cooperativity data-gated"],
        ["protacxtend/tests", 63, 178, 737, 9239, "UNTESTED-IN-FULL", "suite does not complete <25 min; 2 failing tests"],
        ["protacxtend/agents", 39, 52, 241, 6567, "IMPLEMENTED (deterministic)", "planner is a static tool list; entity parser is BROKEN (target=DEGRADE)"],
        ["protacxtend/scientific_backends", 22, 13, 230, 5843, "IMPLEMENTED + VALIDATED (partial)", "ternary predicted DockQ NOT_VALIDATED; MM/GBSA NOT_VALIDATED"],
        ["protacxtend/validation", 18, 5, 133, 3897, "IMPLEMENTED", "claim table real; coverage limited to 12 capabilities"],
        ["protacxtend/research", 10, 19, 124, 3020, "IMPLEMENTED", "retrieval only; no evidence graph, no contradiction handling"],
        ["protacxtend/llm", 15, 21, 102, 2858, "IMPLEMENTED (optional)", "no provider configured by default; deterministic fallback used"],
        ["protacxtend/toolkit", 9, 1, 112, 2809, "IMPLEMENTED", "115 registered tools not executable; provisioning exists"],
        ["protacxtend/runtime", 8, 4, 86, 2496, "IMPLEMENTED", "34 agent tools run on canned fixtures when no real input"],
        ["protacxtend/agentic", 15, 22, 79, 2379, "PARTIAL", "7-layer wrapper; decision layer always runs one workflow; no iterative planning"],
        ["protacxtend/app", 3, 0, 47, 2315, "IMPLEMENTED", "Streamlit only; no investigation graph/decision UI as specified"],
        ["protacxtend/escalation", 11, 10, 77, 2116, "IMPLEMENTED", "auto-installer uses shell=True; injection surface"],
        ["protacxtend/workflows", 6, 1, 56, 1984, "IMPLEMENTED", "pilot/validation runners; not wired to benchmark"],
        ["protacxtend/backend", 12, 38, 64, 1601, "IMPLEMENTED", "13 API routes; no benchmark/temporal endpoints"],
        ["protacxtend/memory", 6, 6, 74, 1377, "IMPLEMENTED", "BM25 fallback; no temporal index; no citation-DOI graph"],
        ["protacxtend/tui_bridge", 3, 1, 29, 798, "IMPLEMENTED", "event bridge; 23 skills registered"],
        ["protacxtend/audit", 2, 1, 30, 539, "IMPLEMENTED", "self-audit harness"],
        ["protacxtend/tui", 2, 2, 21, 536, "IMPLEMENTED", "TypeScript/Node TUI"],
        ["protacxtend/structural", 3, 7, 28, 498, "IMPLEMENTED", ""],
        ["protacxtend/databases", 4, 1, 10, 400, "IMPLEMENTED", "registry/router; 49 DBs mostly registered_but_unavailable"],
        ["protacxtend/models", 2, 0, 11, 372, "IMPLEMENTED", "legacy pickle loader (unsafe deserialization)"],
        ["protacxtend/state", 3, 0, 27, 329, "IMPLEMENTED", "filesystem-JSON store, no DB"],
        ["protacxtend/schemas", 7, 11, 2, 327, "PARTIAL", "backend pydantic schemas; no typed TherapeuticStrategy schema"],
        ["protacxtend/results", 3, 3, 11, 259, "IMPLEMENTED", ""],
        ["protacxtend/case_study", 2, 0, 7, 218, "IMPLEMENTED", ""],
        ["protacxtend/queue", 1, 1, 12, 210, "IMPLEMENTED", ""],
        ["protacxtend/integrations", 2, 0, 6, 205, "IMPLEMENTED", ""],
        ["protacxtend/observability", 1, 1, 12, 147, "IMPLEMENTED", ""],
        ["protacxtend/benchmark", 3, 1, 9, 147, "PARTIAL", "task_schema + manifest only; no runner/scoring in-package"],
        ["protacxtend/learning", 2, 2, 4, 90, "PARTIAL", ""],
        ["protacxtend/root(*.py)", 11, 0, 0, 0, "IMPLEMENTED", "cli.py 1721 lines, scientific_contract.py 710 lines"],
        ["benchmark/ (repo root)", 0, 0, 0, 0, "PARTIAL", "48 cases with expected_answer=null; tasks/ and scoring/ empty"],
        ["benchmark_runner/", 3, 0, 0, 0, "IMPLEMENTED", "runner+scoring; adapters fail-closed; no full scored run"],
        ["sota/eval/eval500", 0, 0, 0, 0, "MOCK", "500 template tasks + 100 adversarial stubs; no graders"],
        ["tpdeval/", 21, 0, 0, 2072, "DESIGN ONLY", "16-domain/L1-L7 taxonomy; 500 tasks all REQUIRES_AUTHORING; 0 scorable"],
    ],
)

# ── 2. canonical tool inventory ─────────────────────────────────────────
# execution measured 2026-09-21: 28 ok / 6 partial / 0 hard-fail of 34 agent tools
TOOLS = [
    # tool_id, name, domain, executed, status_measured, inputs, external_dep, network, notes
    ("deep_research", "Multi-source literature search", "Literature/evidence", "yes", "ok(3.2s)", "query", "EuropePMC+PubMed+CrossRef", "yes", "real retrieval; no evidence typing"),
    ("search_europe_pmc", "Europe PMC search", "Literature/evidence", "yes", "ok", "query", "Europe PMC REST", "yes", ""),
    ("search_pubmed", "PubMed search", "Literature/evidence", "yes", "ok", "query", "NCBI E-utilities", "yes", ""),
    ("verify_crossref", "DOI verification", "Literature/evidence", "yes", "ok", "doi", "Crossref", "yes", ""),
    ("retrieve_fulltext", "Open full text fetch", "Literature/evidence", "yes", "ok", "pmcid", "Europe PMC OA", "yes", ""),
    ("search_web", "SearXNG web search", "Literature/evidence", "yes", "partial", "query", "self-hosted SearXNG", "yes", "disabled/degraded without SEARXNG_URL"),
    ("resolve_target", "Target resolution", "Protein sequence", "yes", "ok", "gene", "UniProt/local CSV", "yes", ""),
    ("search_uniprot", "UniProt free-text search", "Protein sequence", "yes", "ok", "query", "UniProt REST", "yes", ""),
    ("retrieve_target_binders", "Known binder retrieval", "Warhead discovery", "yes", "ok", "target", "ChEMBL online REST", "yes", "returned 0 binders in live BRD4 run"),
    ("select_e3_ligase", "E3 ligase selection", "E3 ligase biology", "yes", "ok", "target,e3", "local E3 catalog", "no", "validated retrospectively"),
    ("retrieve_e3_evidence", "E3 evidence rows", "E3 ligase biology", "yes", "ok", "e3", "local catalog", "no", ""),
    ("inspect_smiles", "SMILES validation/descriptors", "Cheminformatics", "yes", "ok", "smiles", "RDKit", "no", ""),
    ("search_pubchem", "PubChem search", "Cheminformatics", "yes", "ok", "name/smiles", "PubChem REST", "yes", ""),
    ("search_chembl", "ChEMBL molecule search", "Cheminformatics", "yes", "ok", "name", "ChEMBL REST", "yes", ""),
    ("search_bindingdb", "BindingDB lookup", "Cheminformatics", "yes", "partial", "target", "local BindingDB", "no", "needs BINDINGDB_API_KEY for REST"),
    ("detect_exit_vectors", "Exit-vector detection", "Warhead discovery", "yes", "ok", "smiles", "RDKit", "no", ""),
    ("generate_linkers", "Linker generation", "Linker/PROTAC design", "yes", "ok(19s)", "warhead,e3", "curated+rules+generative", "no", "generative models optional/guarded"),
    ("construct_protac", "PROTAC assembly", "Linker/PROTAC design", "yes", "partial", "3 components", "RDKit", "no", "default fixture; invalid combos rejected"),
    ("check_synthetic_feasibility", "Retrosynthesis feasibility", "Cheminformatics", "yes", "partial", "smiles", "AiZynthFinder optional", "no", "route often not_available"),
    ("diagnose_capability", "Capability diagnosis", "Failure analysis", "yes", "ok(5s)", "capability", "installation audit", "no", ""),
    ("list_capability_readiness", "Tool readiness matrix", "Failure analysis", "yes", "ok(68s)", "none", "toolkit registry", "no", "slow"),
    ("list_scientific_capabilities", "Capability list", "Metadata", "yes", "ok", "none", "backend registry", "no", ""),
    ("run_scientific_capability", "Generic backend runner", "Scientific compute", "yes", "ok", "capability,params", "RDKit/OpenMM/Vina/...", "no", "dispatches to real backends"),
    ("retrieve_pdb", "PDB retrieval", "Protein structure", "yes", "ok(8s)", "pdb id", "RCSB PDB", "yes", ""),
    ("model_ternary_complex", "Ternary feasibility", "Ternary modeling", "yes", "ok(0.3s)", "target,e3,linker", "P4ward/SE(3) surrogate", "no", "predicted DockQ NOT_VALIDATED"),
    ("score_lysine_ubiquitination", "Lysine ubiquitination feasibility", "Ternary modeling", "yes", "partial", "target,e3,pose", "structure geometry", "no", "runs on synthetic pose fixture"),
    ("predict_cooperativity", "Cooperativity alpha", "Ternary modeling", "yes", "ok(0.07s)", "3 components,pose", "surrogate model", "no", "data-gated; not experimental alpha"),
    ("simulate_hook_effect", "Hook-effect simulator", "Degradation", "yes", "ok", "Kds,conc", "mass-action model", "no", "equilibrium only; not kinetics"),
    ("predict_degradation", "DC50/Dmax prediction", "Degradation", "yes", "ok(20s)", "smiles,e3,cell", "ML models/joblib", "no", "trained on 64/32 labels; OOD risk"),
    ("predict_cell_context", "Cell-context pDC50", "Degradation", "yes", "ok", "smiles,cell,poi,e3", "cell-context model", "no", "transcriptomic only; no proteotype"),
    ("predict_admet", "ADMET flags", "ADMET", "yes", "ok", "smiles", "ADMET-AI+RDKit", "no", "no PK/clearance"),
    ("run_protacpilot_structural", "Structural pipeline", "Structure/Ternary", "yes", "partial(204s)", "target,e3,protac", "docking/MD stack", "no", "very slow; partial output"),
    ("rank_candidates", "Pareto ranking", "Statistics", "yes", "ok", "candidates", "local NSGA-II", "no", "heuristic composite"),
    ("build_candidate_dossier", "Candidate dossier", "Reporting", "yes", "ok", "candidate", "local", "no", "provenance labels"),
]
write(
    "tool_inventory.csv",
    ["tool_id", "name", "domain", "executable_now", "measured_status", "inputs", "external_dependency", "network_required", "notes"],
    TOOLS,
)

# ── 3. agent inventory (current 31-node graph + 7 agentic layers) ───────
AGENTS = [
    ("SupervisorAgent", "parse_user_request", "deterministic", "IMPLEMENTED", "BROKEN entity parser: 'degrade BRD4'->target=DEGRADE; 'Can BRD4...'->target=CAN"),
    ("DesignPlannerAgent", "create_design_plan", "deterministic", "PARTIAL", "emits a static 19-item tool list; no dynamic replanning"),
    ("ControlledSearchAgent", "control_np_hard_search", "deterministic", "IMPLEMENTED", "budget policy only"),
    ("SafetyAgent", "safety_precheck", "deterministic", "PARTIAL", "rule-based ADMET flags"),
    ("TargetResolverAgent", "resolve_target", "deterministic", "PARTIAL", "local table/ChEMBL; no omics/dependency"),
    ("TargetBinderRetrievalAgent", "retrieve_target_binders", "deterministic", "PARTIAL", "0 binders in live run without network"),
    ("WarheadSelectionAgent", "select_warheads", "deterministic", "PARTIAL", "falls back to DEMO warheads"),
    ("E3LigandSelectionAgent", "select_e3_ligands", "deterministic", "IMPLEMENTED", "curated CRBN/VHL/IAP/MDM2 handles"),
    ("ExitVectorDetectionAgent", "detect_exit_vectors", "deterministic", "IMPLEMENTED", "RDKit + curated markers"),
    ("LinkerGenerationAgent", "generate_linkers", "deterministic", "IMPLEMENTED", "curated + rules + optional generative"),
    ("MolecularConstructionAgent", "construct_protacs", "deterministic", "IMPLEMENTED", "RDKit assembly"),
    ("StereochemistryEnumerationAgent", "expand_stereoisomers", "deterministic", "IMPLEMENTED", "capped enumeration"),
    ("CandidateValidationAgent", "validate_protacs", "deterministic", "IMPLEMENTED", "RDKit sanitization"),
    ("CellContextAgent", "score_cell_context", "deterministic", "PARTIAL", "transcriptomic model; no proteotype"),
    ("ADMETAgent", "predict_admet", "deterministic", "PARTIAL", "ADMET-AI/RDKit; no PK"),
    ("NoveltyAgent", "check_novelty", "deterministic", "PARTIAL", "local known-PROTAC CSV similarity"),
    ("ApplicabilityDomainAgent", "assess_applicability_domain", "deterministic", "IMPLEMENTED", "descriptor-domain check"),
    ("CheapFilterAgent", "cheap_filter_candidates", "deterministic", "IMPLEMENTED", "rule filter"),
    ("DegradationPredictionAgent", "predict_degradation", "deterministic", "PARTIAL", "64/32-label model or heuristic fallback"),
    ("RankingAgent(initial)", "initial_ranking", "deterministic", "PARTIAL", "heuristic weighted score"),
    ("ProximityDiversityAgent", "diversity_clustering", "deterministic", "IMPLEMENTED", "fingerprint clustering"),
    ("ReflectionReviewAgent", "reflection_review", "deterministic", "PARTIAL", "rule critique; no independent verifier"),
    ("EvolutionRefinementAgent", "evolution_refinement", "deterministic", "IMPLEMENTED", "mutation/grafting loop"),
    ("ExpensiveModelingSelectionAgent", "select_expensive_modeling_finalists", "deterministic", "IMPLEMENTED", "budget gate"),
    ("TernaryFeasibilityAgent", "optional_ternary_feasibility", "deterministic", "PARTIAL", "geometry surrogate; predicted DockQ unvalidated"),
    ("CooperativityPredictionAgent", "predict_cooperativity", "deterministic", "PARTIAL", "surrogate, data-gated"),
    ("HookEffectPredictionAgent", "predict_hook_effect", "deterministic", "PARTIAL", "equilibrium proxy, not fitted"),
    ("RankingAgent(final)", "final_ranking", "deterministic", "PARTIAL", "heuristic composite"),
    ("ActiveLearningAgent", "active_learning_update", "deterministic", "PARTIAL", "synthetic benchmark only; no feedback loop"),
    ("ReportAgent", "generate_report", "deterministic", "IMPLEMENTED", "real markdown/csv/json artifact"),
    ("MemoryUpdateAgent", "update_memory", "deterministic", "IMPLEMENTED", "JSONL memory"),
    ("PerceptionAgent(agentic)", "perception", "deterministic", "IMPLEMENTED", "collects tools/models/memory; inherits parser bug"),
    ("ReasoningAgent(agentic)", "reasoning", "deterministic", "PARTIAL", "rule-based risk interpretation"),
    ("GoalSettingAgent(agentic)", "goal_setting", "deterministic", "IMPLEMENTED", "typed DesignGoal"),
    ("DecisionMakingAgent(agentic)", "decision_making", "deterministic", "PARTIAL", "always selects one workflow; no tool search"),
    ("ExecutionAgent(agentic)", "execution", "deterministic", "IMPLEMENTED", "single registry tool with error capture"),
    ("ScientificCriticAgent(agentic)", "scientific_critic", "deterministic", "PARTIAL", "rule checks; not adversarial verifier"),
    ("LearningAgent(agentic)", "learning", "deterministic", "PARTIAL", "memory writes; no learning"),
]
write(
    "agent_inventory.csv",
    ["agent", "action", "type", "status", "evidence_or_weakness"],
    AGENTS,
)

# ── 4. scientific capability matrix (16 domains x 10 axes) ──────────────
AXES = ["data_retrieval", "reasoning", "tool_support", "quantitative_analysis",
        "structure_support", "mechanistic_inference", "decision_support",
        "validation_support", "provenance", "benchmark_readiness"]
MATRIX = {
    "target_biology": ["PARTIAL","WEAK","PARTIAL","MISSING","MISSING","WEAK","WEAK","WEAK","PARTIAL","WEAK"],
    "target_validation": ["WEAK","MISSING","MISSING","WEAK","MISSING","MISSING","MISSING","MISSING","PARTIAL","MISSING"],
    "tpd_tractability": ["PARTIAL","PARTIAL","PARTIAL","WEAK","PARTIAL","PARTIAL","PARTIAL","WEAK","PARTIAL","WEAK"],
    "e3_selection": ["FULL","FULL","FULL","PARTIAL","WEAK","PARTIAL","PARTIAL","PARTIAL","FULL","PARTIAL"],
    "warhead_discovery": ["PARTIAL","WEAK","PARTIAL","WEAK","PARTIAL","WEAK","PARTIAL","MISSING","PARTIAL","WEAK"],
    "linker_protac_design": ["PARTIAL","PARTIAL","FULL","PARTIAL","PARTIAL","PARTIAL","PARTIAL","WEAK","FULL","PARTIAL"],
    "binary_structure": ["PARTIAL","PARTIAL","FULL","PARTIAL","FULL","PARTIAL","PARTIAL","PARTIAL","FULL","PARTIAL"],
    "ternary_complex": ["PARTIAL","PARTIAL","PARTIAL","WEAK","PARTIAL","PARTIAL","WEAK","WEAK","PARTIAL","WEAK"],
    "degradation": ["PARTIAL","PARTIAL","FULL","PARTIAL","WEAK","PARTIAL","PARTIAL","WEAK","FULL","PARTIAL"],
    "adme_pk": ["WEAK","WEAK","PARTIAL","PARTIAL","MISSING","WEAK","WEAK","MISSING","PARTIAL","WEAK"],
    "safety": ["WEAK","WEAK","PARTIAL","WEAK","MISSING","WEAK","WEAK","MISSING","PARTIAL","MISSING"],
    "resistance": ["MISSING","WEAK","WEAK","MISSING","MISSING","WEAK","WEAK","MISSING","WEAK","MISSING"],
    "biomarker": ["MISSING","MISSING","MISSING","MISSING","MISSING","MISSING","MISSING","MISSING","MISSING","MISSING"],
    "combination": ["MISSING","MISSING","MISSING","MISSING","MISSING","MISSING","MISSING","MISSING","MISSING","MISSING"],
    "experimental_design": ["WEAK","PARTIAL","PARTIAL","WEAK","MISSING","PARTIAL","PARTIAL","WEAK","PARTIAL","WEAK"],
    "failure_analysis": ["PARTIAL","PARTIAL","PARTIAL","WEAK","MISSING","PARTIAL","PARTIAL","PARTIAL","FULL","WEAK"],
}
EVIDENCE = {
    "target_biology": "resolve_target/search_uniprot/search_pubmed live; run.json target parser returns DEGRADE/CAN",
    "target_validation": "no DepMap/CRISPR dependency tool; only cell_context transcriptomics + demo expression",
    "tpd_tractability": "modules/lysine_ubiquitination_feasibility, cooperativity surrogate, e3_opportunity",
    "e3_selection": "modules/e3_opportunity (30-gene catalog, RF AUROC .98 easy/.93 unseen), 17 tests",
    "warhead_discovery": "retrieve_target_binders=0 in live BRD4 run; report says 'Included demo warheads'",
    "linker_protac_design": "linker_generator + construct_protac + RDKit validation; 180 candidates assembled",
    "binary_structure": "scientific_backends ligand_docking validated: Vina median RMSD 2.356A on 40 complexes",
    "ternary_complex": "validation/claims.py: ternary predicted DockQ NOT_VALIDATED; native geometry only n=12",
    "degradation": "modules/degradation_ml 64/32 labels; TACK/SynGlue models; hook model equilibrium-only",
    "adme_pk": "predict_admet real (ADMET-AI); no clearance/Cmax/PK model anywhere",
    "safety": "ADMET flags + neosubstrate_risk 28-line heuristic; no tox/toxicology benchmark",
    "resistance": "modules/resistance_mechanisms 41-line hardcoded mutation table, no tests, evaluator-only",
    "biomarker": "only a regex keyword in research/sources.py; no stratification code",
    "combination": "no synergy/combination code path; string 'combination' only in linker docs",
    "experimental_design": "dose_response_simulator + scientific_contract.build_experiment_dossier (template)",
    "failure_analysis": "escalation/*, diagnose_capability, RepairController; fallback benchmark success 0.556",
}
rows = []
for d, vals in MATRIX.items():
    rows.append([d] + vals + [EVIDENCE[d]])
write("capability_matrix.csv", ["domain"] + AXES + ["evidence"], rows)

# ── 5. benchmark artifacts comparison ───────────────────────────────────
write(
    "benchmark_artifacts.csv",
    ["artifact", "tasks", "domains", "difficulty", "ground_truth", "grader", "scored_runs", "verdict"],
    [
        ["benchmark/ (Sprint-2)", 48, "4 (KNOW/REASON/DESIGN/DISCOVER)", "easy/medium/hard", "all expected_answer=null; 29 rubric", "deterministic + rubric (no experts run)", 0, "GOVERNED SPEC, NOT A VALID INSTRUMENT"],
        ["sota/eval/ (legacy)", 624, "4 stages", "easy/medium/hard", "template constraints", "none shipped", 0, "SUPERSEDED, UNSCORED"],
        ["sota/eval/eval500", "600 (500+100)", "14 categories", "easy/medium/hard", "template constraint strings", "none shipped", 0, "MOCK/STUB"],
        ["tpdeval/ (design)", "500 (design)", "16 domains", "L1-L7", "all REQUIRES_AUTHORING; scorable=0", "framework only", 0, "DESIGN ONLY, 0 SCORABLE"],
        ["benchmark_results/", "4 tasks x 3 systems", "n/a", "n/a", "n/a", "acceptance only", 0, "SMOKE CAPTURE ONLY"],
    ],
)

# ── 6. benchmark readiness requirements ─────────────────────────────────
write(
    "benchmark_readiness.csv",
    ["requirement", "current_state", "evidence", "severity"],
    [
        ["500 authored tasks (300 controlled/150 E2E/50 temporal)", "MISSING", "tpdeval/config/allocation_500.json: 500 tasks, 0 scorable", "P0"],
        ["16-domain x L1-L7 taxonomy", "DESIGN ONLY", "tpdeval/taxonomy.py validates; no tasks populated", "P0"],
        ["Objectively scorable ground truth (>=80%)", "MISSING", "48 cases expected_answer=null; eval500 rubric strings", "P0"],
        ["Independent TPD comparator", "MISSING", "tpdeval/adapters.py: system C wired=False", "P0"],
        ["Tool-only baseline", "MISSING", "adapters.py system F not implemented", "P0"],
        ["Retrieval-only baseline", "MISSING", "adapters.py system E not implemented", "P0"],
        ["Matched-tool condition", "MISSING", "no matched environment runner", "P0"],
        ["Per-claim evidence grounding scorer", "MISSING", "tpdeval/evidence.py exists; no per-claim schema wired", "P0"],
        ["Causal-graph ground truth + matcher", "PARTIAL", "tpdeval/mechanism.py exists; no authored graphs", "P0"],
        ["Decision-trajectory ground truth + scorer", "PARTIAL", "tpdeval/trajectory.py exists; no authored trajectories", "P0"],
        ["Fault injection + recovery metrics", "PARTIAL", "tpdeval/failure.py 10 faults defined; not run vs systems", "P1"],
        ["Reproducibility repeat protocol", "PARTIAL", "run_records hash exists; replay determinism unverified", "P1"],
        ["Temporal T0/T1 challenge + leakage scanner", "PARTIAL", "tpdeval/temporal.py logic only; no frozen store", "P0"],
        ["Human adjudication + IRR", "PARTIAL", "benchmark_runner/rubric.py kappa; no experts run", "P1"],
        ["Paired statistics", "PARTIAL", "tpdeval/stats.py tested; no data to run on", "P1"],
        ["Ablation harness", "PARTIAL", "tpdeval/ablation.py defines arms; not executable without systems", "P1"],
        ["Result figures/tables", "PARTIAL", "tpdeval/reporting.py refuses non-measured data", "P1"],
    ],
)

# ── 7. L1-L7 capability audit ───────────────────────────────────────────
write(
    "l1_l7_audit.csv",
    ["level", "name", "retrieval", "calculation", "tool_execution", "integration", "mechanistic", "therapeutic", "adversarial", "verdict"],
    [
        ["L1", "Retrieval", "PARTIAL", "-", "-", "-", "-", "-", "-", "Live paper/UniProt/ChEMBL retrieval works; no source-date filtering, no per-claim citation binding"],
        ["L2", "Calculation", "-", "PARTIAL", "-", "-", "-", "-", "-", "RDKit descriptors/linker metrics real; unit handling not enforced across tools"],
        ["L3", "Tool execution", "-", "-", "PARTIAL", "-", "-", "-", "-", "34 agent tools execute; 6 partial; many default to canned fixtures; no required-tool precision/recall"],
        ["L4", "Integration", "-", "-", "-", "WEAK", "-", "-", "-", "Single deterministic pass; no conflict resolution/evidence ranking across sources"],
        ["L5", "Mechanistic inference", "-", "-", "-", "-", "WEAK", "-", "-", "Rule templates; no causal graph, no falsifiable hypothesis objects"],
        ["L6", "Therapeutic discovery", "-", "-", "-", "-", "-", "WEAK", "-", "No typed TherapeuticStrategy; report is narrative + table; no go/no-go gates"],
        ["L7", "Adversarial/OOD", "-", "-", "-", "-", "-", "-", "WEAK", "100 adversarial tasks are one-line stubs; no safe-abstention policy engine"],
    ],
)

# ── 8. failure handling audit ───────────────────────────────────────────
write(
    "failure_handling.csv",
    ["category", "detected_today", "mechanism", "retry_policy", "abstention_rule", "measured_behaviour"],
    [
        ["INVALID_INPUT", "yes", "backend validation.validate_smiles/PDB", "none", "reject", "REJECTED_INPUT observed in docking set (2/40)"],
        ["MISSING_DATA", "partial", "perception.missing_information", "none", "ask_user_for_clarification", "works (target missing)"],
        ["TOOL_NOT_INSTALLED", "yes", "escalation.diagnosis + toolkit status", "auto pip install attempt (shell=True)", "not_available", "installer present; injection surface"],
        ["TOOL_EXECUTION_ERROR", "yes", "ExecutionAgent try/except", "1 retry in graph for 5 steps", "structured failure", "6/34 agent tools partial"],
        ["NETWORK_ERROR", "partial", "raised by clients", "none deterministic", "degrade to local", "BindingDB/SEARXNG degrade"],
        ["DATABASE_UNAVAILABLE", "partial", "db registry status", "none", "not_available", "49 DBs registered_but_unavailable"],
        ["STRUCTURE_UNAVAILABLE", "partial", "retrieve_structure status", "none", "not_available", "protein_structure returned capability_unavailable in e2e audit"],
        ["MOLECULE_INVALID", "yes", "RDKit sanitization", "none", "reject", "invalid SMILES rejected"],
        ["CONFLICTING_EVIDENCE", "no", "-", "-", "-", "not modelled; sources merged silently"],
        ["LOW_CONFIDENCE", "partial", "applicability domain/AD", "none", "downgrade label", "AD wall added to reports"],
        ["TEMPORAL_LEAKAGE", "no", "tpdeval.temporal.leakage_flags only (unwired)", "none", "none", "no leakage scanner in runtime"],
        ["OUT_OF_DOMAIN", "partial", "applicability_domain", "none", "flag", "small model OOD risk"],
        ["UNSUPPORTED_CLAIM", "partial", "agentic.audit unsupported_claims", "none", "revise_report", "only checks phrase 'experimentally validated'"],
        ["NON_REPRODUCIBLE_RESULT", "no", "run_records hash only", "none", "none", "Vina deterministic=false"],
    ],
)

# ── 9. gap analysis ─────────────────────────────────────────────────────
write(
    "gap_analysis.csv",
    ["id", "priority", "problem", "evidence", "impact", "fix", "difficulty", "dependencies"],
    [
        ["G01", "P0", "Entity parser mis-identifies target", "SupervisorAgent: 'degrade BRD4'->DEGRADE, 'Can BRD4'->CAN", "every natural-language task resolves wrong target", "NER/gene-symbol resolver + question-intent parser + tests", "S", "none"],
        ["G02", "P0", "No authored 500-task benchmark", "tpdeval allocation: 0/500 scorable", "no benchmark can be run or published", "author tasks with citation-backed ground truth + expert review", "XL", "G03,G04"],
        ["G03", "P0", "Ground truth absent/unaudited", "48 cases expected_answer=null; 1 wrong UniProt caught by erratum", "scoring is not scientifically defensible", "GT authoring + independent verification protocol", "L", "G01"],
        ["G04", "P0", "No independent comparator/baselines", "tpdeval/adapters.py C/E/F/G/H not wired", "no claim of superiority possible", "wire Biomni + TPD agent + retrieval/tool-only + hybrids", "L", "G02"],
        ["G05", "P0", "No temporal freeze/leakage control", "tpdeval/temporal.py is unwired logic", "temporal benchmark invalid", "TemporalEvidenceStore/FrozenIndex/LeakageAuditor (S8)", "L", "G02"],
        ["G06", "P0", "Per-claim evidence grounding absent", "no claim->citation binding in run.json", "cannot measure hallucination/grounding", "claim schema + evidence graph + grounding scorer", "M", "G02"],
        ["G07", "P1", "No typed TherapeuticStrategy output", "reports are markdown; schemas lack decision schema", "decision quality unscorable", "TherapeuticStrategy schema + decision engine", "M", "G01"],
        ["G08", "P1", "Multi-agent reasoning is single-pass", "DecisionMakingAgent always picks one workflow", "no decomposition/iteration/self-correction", "hierarchical planner + specialists + critics", "L", "G07"],
        ["G09", "P1", "Tools execute on canned fixtures", "run_agent_tool defaults smiles='CCO', synthetic pose", "execution success != science", "require explicit validated inputs; fail closed", "M", "none"],
        ["G10", "P1", "Failure recovery rate 0.0", "results/audit/audit.json failure_recovery_rate=0.0", "L7 adversarial fails", "unified failure taxonomy + repair controller", "M", "G09"],
        ["G11", "P1", "Test suite does not complete <25 min; 3 failures", "tests/ 2 fail; protacxtend/tests timeouts + 2 fail", "CI cannot gate releases", "split fast/slow, mark heavy, fix failures", "M", "none"],
        ["G12", "P1", "Security: shell=True + pickle", "toolkit/provision.py:310; escalation/installer.py:293; models/degradation_model.py:93", "command injection / RCE via tool packages", "arg lists only; safe loaders; sandbox installs", "M", "none"],
        ["G13", "P2", "No biomarker/combination capability", "no code paths", "2 of 16 domains missing", "omics/biomarker + synergy modules", "L", "G07"],
        ["G14", "P2", "ADME/PK lacks PK", "predict_admet only", "developability claims weak", "PK/clearance model or explicit boundary", "M", "none"],
        ["G15", "P2", "Ternary predicted structure unvalidated", "claims.py ternary DockQ NOT_VALIDATED", "ternary claims overreach", "validate predicted-pose DockQ or restrict claim", "M", "G09"],
        ["G16", "P3", "UI lacks investigation graph/decision/benchmark screens", "Streamlit single app; 13 API routes", "product not matching spec", "new UI screens + API", "L", "G07,G02"],
    ],
)

# ── 10. final verdict table ─────────────────────────────────────────────
write(
    "verdict_table.csv",
    ["area", "current_state", "evidence", "blocker", "required_action"],
    [
        ["Core architecture", "IMPLEMENTED", "protacxtend/ 465 py files/91k LOC; CLI+API+TUI+Streamlit", "monolithic; two parallel agent stacks", "unify on one orchestrator"],
        ["Agent orchestration", "PARTIAL", "agents/graph.py deterministic state machine; agentic/ 7 layers", "static tool list; no dynamic planning", "hierarchical planner + specialists"],
        ["Tools", "PARTIAL", "34 agent tools: 28 ok/6 partial measured; 115 toolkit registered_but_not_executable", "fixtures as defaults; no required-tool scoring", "typed tool contracts + fail-closed"],
        ["Scientific reasoning", "WEAK", "rule templates; no causal graph", "no falsifiable hypothesis objects", "mechanism critic + causal graph"],
        ["Target biology", "PARTIAL", "resolve_target works; parser bug", "target misparse", "fix G01"],
        ["TPD tractability", "PARTIAL", "lysine/cooperativity/e3 modules", "surrogates data-gated", "real-PDB benchmark"],
        ["E3 selection", "PARTIAL-VALIDATED", "e3_opportunity RF AUROC .98/.93, 17 tests", "no prospective validation", "prospective E3 benchmark"],
        ["Warhead", "WEAK", "0 binders live; demo warheads", "no licensed/online binding source", "wire ChEMBL/BindingDB keys"],
        ["PROTAC design", "IMPLEMENTED", "linker/construct RDKit; 180 candidates", "no synthesizability closure", "retro integration"],
        ["Binary structure", "VALIDATED-PARTIAL", "Vina median RMSD 2.356A n=40", "success<2A only 0.375", "improve prep/consensus"],
        ["Ternary complex", "WEAK", "predicted DockQ NOT_VALIDATED", "no predicted-structure validation", "validate or restrict"],
        ["Degradation", "PARTIAL", "64/32 labels; TACK/SynGlue; hook equilibrium", "small labels; OOD", "expand curated labels"],
        ["ADMET", "PARTIAL", "ADMET-AI real; no PK", "no PK/clearance", "PK model or boundary"],
        ["Safety", "WEAK", "ADMET flags + neosubstrate heuristic", "no tox validation", "safety benchmark"],
        ["Biomarkers", "MISSING", "keyword only", "no code", "build module"],
        ["Resistance", "WEAK", "41-line hardcoded table", "no tests/wiring", "build + validate"],
        ["Experimental design", "WEAK", "dose sim + dossier template", "not typed/validated", "typed ExperimentPlan"],
        ["Evidence grounding", "MISSING", "no claim->citation binding", "no schema", "evidence engine"],
        ["Provenance", "PARTIAL", "run_records.py AgentRunRecord + hash; tool provenance", "no container/model/db version freeze", "RunManifest v2"],
        ["Reproducibility", "PARTIAL", "reproducibility_hash; replay 0.917 in audit", "Vina deterministic=false", "replay determinism tests"],
        ["Temporal benchmarking", "MISSING", "tpdeval logic only", "no frozen store", "TemporalBenchmarkEngine"],
        ["500-task benchmark", "MISSING", "0 scorable", "no authored GT", "author + verify"],
        ["Failure recovery", "WEAK", "failure_recovery_rate=0.0", "no taxonomy/repair", "failure engine"],
        ["Security", "HIGH RISK", "shell=True x3, pickle.load x5", "RCE/injection", "harden"],
        ["UI", "PARTIAL", "Streamlit + TUI + website", "no spec screens", "rebuild UI"],
        ["Deployment", "PARTIAL", "Dockerfile, docker-compose, deploy/", "env reproducibility unverified", "container lockfile"],
        ["Testing", "PARTIAL", "954 collected; 184/186 pass in tests/; 2 fail; suite >25min", "flaky/slow/failures", "fix + split"],
    ],
)

# ── 11. measured test results ───────────────────────────────────────────
write(
    "test_results.csv",
    ["scope", "collected", "passed", "failed", "skipped", "wall_time_s", "note"],
    [
        ["tests/ (root)", 186, 184, 2, 0, 504.7, "2 failures: CLI capabilities naming (TUI entry)"],
        ["protacxtend/modules", 126, 126, 0, 0, 55.0, "all pass"],
        ["protacxtend/tests (per-file)", 642, 638, 2, 11, ">1500 (incomplete)", "2 failures: launcher path, p4ward human-review gate; several files >120s"],
        ["tests/test_tpdeval.py", 22, 22, 0, 0, 1.0, "taxonomy/stats/temporal logic pass"],
        ["FULL SUITE", 954, "n/a", "n/a", "n/a", ">1700 (killed at 54%)", "cannot complete within 30 min on 32-core host"],
    ],
)

# ── 12. proposed multi-agent blueprint ──────────────────────────────────
write(
    "multi_agent_blueprint.csv",
    ["agent", "retain_or_new", "role", "own_state", "own_tools", "owns_decision"],
    [
        ["OrchestratorAgent", "MODIFY", "plan, route, aggregate, enforce gates", "yes", "planner, registry", "final go/no-go"],
        ["TargetBiologyAgent", "NEW", "target identity/biology/disease mechanism", "yes", "uniprot,pubmed,europepmc,openalex", "target dossier"],
        ["TargetValidationAgent", "NEW", "genetic/omics/dependency evidence", "yes", "depmap,omics,literature", "validation verdict"],
        ["TPDTractabilityAgent", "MODIFY(e3_opportunity)", "degradability, lysines, localization", "yes", "lysine,structure,e3", "tractability tier"],
        ["E3SelectionAgent", "RETAIN", "E3 choice + evidence tier", "yes", "e3_opportunity,e3_context", "E3 shortlist"],
        ["WarheadDiscoveryAgent", "MODIFY", "warhead mining/design", "yes", "chembl,pubchem,bindingdb", "warhead panel"],
        ["MedicinalChemistryAgent", "NEW", "linker/exit-vector/property optimisation", "yes", "rdkit,linker generators", "design hypotheses"],
        ["BinaryStructureAgent", "NEW(split from structure)", "binary complex modelling/docking", "yes", "vina,gnina,diffdock", "pose selection"],
        ["TernaryComplexAgent", "RETAIN", "ternary modelling/cooperativity", "yes", "p4ward,ternary_ensemble", "ternary verdict"],
        ["DegradationPredictionAgent", "RETAIN", "DC50/Dmax/cell context", "yes", "degradation_ml,cells", "degradation estimate"],
        ["ADMEAgent", "RETAIN", "ADME/PK/developability", "yes", "admet-ai,rdkit", "liability list"],
        ["SafetyAgent", "MODIFY", "tox/polypharmacology/neosubstrate", "yes", "admet,neosubstrate", "safety flags"],
        ["ResistanceAgent", "NEW", "resistance/escape mechanisms", "yes", "resistance module,literature", "resistance hypotheses"],
        ["BiomarkerAgent", "NEW", "stratification/biomarker", "yes", "omics,literature", "biomarker panel"],
        ["CombinationAgent", "NEW", "combination/synergy", "yes", "literature,pathway", "combination strategy"],
        ["ExperimentalDesignAgent", "NEW", "assay/controls/go-no-go", "yes", "dose sim,assay schemas", "experimental plan"],
        ["EvidenceCriticAgent", "NEW", "verify citations/support", "no", "evidence graph", "PASS/REVISE/ABSTAIN"],
        ["MechanismCriticAgent", "NEW", "verify causal chain", "no", "causal graph", "PASS/REVISE/ABSTAIN"],
        ["ReproducibilityAgent", "NEW", "manifest/replay/leakage", "no", "run manifest, temporal", "PASS/REVISE/ABSTAIN"],
    ],
)

# ── 13. temporal component contract ─────────────────────────────────────
write(
    "temporal_components.csv",
    ["component", "purpose", "input", "output", "storage", "failure_mode"],
    [
        ["TemporalEvidenceStore", "hold only pre-T0 evidence", "query,T0", "evidence items", "object store + vector index", "post-T0 item admitted"],
        ["TemporalSourceValidator", "check release/retrieval dates", "source records,T0", "accept/reject + flags", "metadata db", "missing release date"],
        ["TemporalToolRegistry", "pin tool versions at T0", "T0", "frozen tool manifest", "manifest json", "tool upgraded mid-run"],
        ["CutoffPolicy", "resolve T0 per task", "task,policy", "T0 date + rules", "task manifest", "ambiguous cutoff"],
        ["LeakageAuditor", "scan evidence/model/tool dates", "run + T0", "leakage events", "run manifest", "silent leakage"],
        ["FrozenRetrievalIndex", "immutable search index", "corpus dump", "read-only index", "object store", "reindex drift"],
        ["FrozenDatabaseManifest", "record DB release hashes", "DB snapshots", "hash manifest", "manifest json", "snapshot missing"],
        ["ToolVersionManifest", "record tool/image versions", "env probe", "version map", "manifest json", "container changed"],
        ["RunManifest", "full reproducibility record", "run", "signed manifest", "object store", "field omitted"],
        ["GroundTruthVault", "sealed post-T0 truth", "future evidence", "encrypted GT", "encrypted storage", "early unlock"],
        ["AdjudicationEngine", "compare prediction vs future", "pred + later evidence", "SUPPORTED/MIXED/CONTRADICTED/UNRESOLVED", "results db", "free-text inference"],
    ],
)

# ── 14. API blueprint ───────────────────────────────────────────────────
write(
    "api_blueprint.csv",
    ["method", "path", "purpose", "request", "response"],
    [
        ["POST", "/investigations", "create investigation", "{target,disease,question,cutoff}", "{id,status}"],
        ["POST", "/investigations/{id}/run", "execute", "{mode,tool_policy}", "{run_id,status}"],
        ["GET", "/investigations/{id}", "fetch state", "-", "{state,strategy,manifest}"],
        ["POST", "/agent/run", "generic agent run", "{question,cutoff,policy}", "{run_id}"],
        ["GET", "/tools", "tool registry", "?domain=", "[{id,status,schema}]"],
        ["POST", "/tools/{tool_id}/execute", "execute one tool", "{params}", "{status,data,provenance}"],
        ["GET", "/evidence/search", "evidence retrieval", "?q=&cutoff=", "[{claim,source,date}]"],
        ["POST", "/benchmark/run", "run benchmark", "{benchmark,split,systems}", "{benchmark_run_id}"],
        ["GET", "/benchmark/{id}/results", "benchmark results", "-", "{scores,per_task}"],
        ["POST", "/temporal/run", "blinded temporal run", "{T0,tasks}", "{run_id,manifest}"],
        ["POST", "/temporal/unlock", "unlock future truth", "{run_id,secret}", "{adjudication}"],
        ["GET", "/runs/{run_id}", "run record", "-", "{AgentRunRecord}"],
        ["GET", "/runs/{run_id}/manifest", "manifest", "-", "{RunManifest}"],
        ["GET", "/capabilities", "capabilities", "-", "[{id,maturity}]"],
    ],
)

# ── 15. storage blueprint ───────────────────────────────────────────────
write(
    "storage_blueprint.csv",
    ["object", "store", "rationale", "key_fields"],
    [
        ["Project", "PostgreSQL", "relational, shared", "id,name,owner,created"],
        ["Investigation", "PostgreSQL", "relational, queryable", "id,project_id,target,disease,cutoff"],
        ["Task/BenchmarkTask", "PostgreSQL", "relational + versioned", "id,domain,difficulty,partition,cutoff"],
        ["AgentRun/ToolRun", "PostgreSQL + object storage", "query + artifact blobs", "run_id,tool,version,status,runtime"],
        ["EvidenceItem", "PostgreSQL + vector DB", "structured + semantic search", "id,type,entity,date,strength,source"],
        ["Citation", "PostgreSQL", "relational, dedupe by DOI", "doi,pmid,accession,date"],
        ["Molecule/Protein/Structure", "PostgreSQL + object storage", "metadata + coordinate files", "id,smiles/seq,path,hash"],
        ["Prediction", "PostgreSQL", "queryable, per-model", "id,model,version,value,AD,evidence_tier"],
        ["TherapeuticStrategy", "PostgreSQL (JSONB)", "typed doc", "id,strategy,confidence,provenance"],
        ["ExperimentPlan", "PostgreSQL (JSONB)", "typed doc", "id,assays,controls,go_no_go"],
        ["EvidenceGraph", "Graph DB (only if needed)", "contradiction-preserving traversal", "nodes,edges,tier,contradicts"],
        ["TemporalSnapshot", "object storage (immutable)", "freeze at T0", "id,T0,corpus_hash,index_hash"],
        ["Manifest (Run/Tool/GT)", "object storage + PostgreSQL", "audit + replay", "hash,versions,seed"],
    ],
)

print("done")
