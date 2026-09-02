"""Generate repository-audit artifacts (capability/backend/gap matrices).

Every row is validated to carry exactly the declared fields.
Run: python scripts/generate_audit_artifacts.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"

CAP_FIELDS = ["id", "area", "capability", "file", "entry_point", "agent",
              "toolbox", "backend", "runtime_integrated", "status", "tests",
              "benchmark", "claim", "limitation", "duplication", "action",
              "priority", "evidence"]

# (id, area, capability, file, entry, agent, toolbox, backend, runtime, status,
#  tests, benchmark, claim, limitation, duplication, action, priority, evidence)
C = [
("A1","Orchestration","Deterministic 31-node runtime graph","agents/graph.py","run_syn_glue_workflow()","31-agent chain","ProtacXtendToolbox","none","Y","FULL","root tests + e2e scenarios","e2e_final_20260902 ok 196s","software: deterministic workflow runs","agent-node breadth varies","two graphs (31 vs 17 nodes)","KEEP","P0","graph.py; outputs/runs/e2e_final_20260902"),
("A2","Orchestration","Agentic LangGraph path","agents/agentic_core.py; runtime.py","run_agentic_workflow()","real_nodes (17)","none","LangGraph/LLM gateway","Y","PARTIAL","architecture/e2e tests","e2e suite green (history)","agentic mode callable","dual-path divergence; exit_vector stub","same design in 2 graphs","CONNECT","P1","runtime.py modes; real_nodes()=17"),
("A3","Orchestration","Checkpoint/resume + thread limits","agents/checkpointer.py; tools/thread_limits.py","threaded run","runtime","-","Postgres/Redis","Y","FULL","thread tests","deterministic-hang fix (196s)","checkpointing supported","optional infra","-","KEEP","P1","TASK_LEDGER_20260902"),
("A4","Orchestration","Memory / learning store","memory/learnings/*; graph MemoryUpdateAgent","update_memory()","MemoryUpdateAgent","-","jsonl store","Y","PARTIAL","learning tests","-","callable","not scientifically validated","-","FREEZE","P2","agents/graph.py last node"),
("A5","Orchestration","Provenance + AgentRunRecord","agentic_core.py; outputs/runs/*","AgentRunRecord","runtime","-","-","Y","FULL","provenance tests","e2e traces","run records written","-","-","KEEP","P1","canonical AgentRunRecord commit"),
("B1","Target biology","POI resolution + aliases","tools/protac_toolbox.py; target_agent.py","resolve_target_package()","TargetResolverAgent","TargetBiologyToolbox","ProtacDB + maps","Y","FULL","target tests","e2e scenarios","resolves common POIs","registry-limited","-","KEEP","P0","real_nodes _target"),
("B2","Target biology","Tractability / disease context","tools/protac_toolbox.py","assess_degradation_tractability()","TargetResolverAgent","TargetBiologyToolbox","evidence lookups","Y","PARTIAL","component tests","-","EXPLORATORY","heuristic","-","UPGRADE","P1","toolbox method"),
("B3","Target biology","Sequence/structure retrieval (UniProt/AlphaFold/PDB)","uniprot_client.py; alphafold_client.py; rcsb_pdb_lookup.py","retrieve_*","binder/e3/ternary agents","-","UniProt, AlphaFold, RCSB","Y","WRAPPER","client tests (network-skip)","-","retrieval online","network + cache limits","client vs lookup dup","UPGRADE","P1","client files"),
("B4","Target biology","Subcellular localization","e3_opportunity/localization.py","compatibility()","E3 agent","-","UniProt cached (78 genes)","Y","PARTIAL","M6 tests","-","annotation-backed","small coverage; not measured","M6 table only","UPGRADE","P2","data/uniprot_localization.csv"),
("B5","Target biology","Expression context (cell/tissue)","cell_context_selector/*; e3 context.py","context_scores()","CellContextAgent","-","DepMap 24Q4","Y","FULL","M5/M6 tests","grouped A-G; retrieval","cell-context pDC50 (retro)","RNA only; DepMap lines","M5 & M6 both expose context","KEEP","P0","VALIDATION.md M5/M6"),
("C1","Warhead/binder","Binder retrieval (ChEMBL/BindingDB/PubChem/DrugBank)","tools/*client.py + *_lookup.py","retrieve_binders()","TargetBinderRetrievalAgent","ComponentToolbox","4 APIs","Y","WRAPPER","client tests (network-skip)","binder census (history)","retrieval online","network + keys","client/lookup dup per source","UPGRADE","P1","binder_agent.py"),
("C2","Warhead/binder","Affinity ranking of binders/warheads","warhead_selector.py; protac_toolbox.py","retrieve_and_rank_warheads()","WarheadSelectionAgent","ComponentToolbox","reported activity","Y","PARTIAL","component tests","-","EXPLORATORY","reported-activity ranking","-","UPGRADE","P2","toolbox methods"),
("C3","Warhead/binder","Exit-vector identification","exit_vector_detector.py; ExitVectorToolbox","enumerate_exit_vector_hypotheses()","ExitVectorDetectionAgent","ExitVectorToolbox","RDKit geometry","Y","PARTIAL","tests present","-","EXPLORATORY","heuristic; graph node stub","real_nodes node not_run","CONNECT","P1","real_nodes lambda exit_vector_detection"),
("C4","Warhead/binder","Warhead target-selectivity","-","-","-","-","-","N","MISSING","-","-","NOT SUPPORTED","no model","-","BUILD","P1","no files (K/KL gap)"),
("D1","E3 ligase","E3 opportunity ranking (30-gene x 8 axes)","modules/e3_opportunity/*","rank_e3_ligases()","e3 tool/agent","e3_opportunity_tool","DepMap+UniProt+ligand lib","Y","FULL","17 M6 tests","retrospective grouped RF .98/.93","retrieval of known/tractable E3","prospective novel-E3 not supported","older e3_selector/context engine","KEEP","P0","docs/CLAIMS.md M6"),
("D2","E3 ligase","Recruiter availability + cited library","protacxtend/data/curated_e3_ligands.csv","recruiter_info()","E3LigandSelectionAgent","ComponentToolbox","cited library (19 E3s)","Y","FULL","M6 tests","-","recruiter presence","library scope ~19 classes","-","KEEP","P0","dataset.py M6"),
("D3","E3 ligase","Legacy CRBN-vs-VHL context engine","tools/e3_context_engine.py; e3_selector.py","select_e3()","E3LigandSelectionAgent","-","curated tables","Y","EXPERIMENTAL","e3 tests (20 history)","scenario 6","EXPLORATORY","heuristic; superseded by M6","BAD DUP vs M6","FREEZE","P2","e3_context_engine.py"),
("E1","Linker","Generative linker (char-GRU)","tools/generative_linker.py; train script","generate_linkers_for_pair()","LinkerGenerationAgent","LinkerDesignToolbox","internal model","Y","FULL","15 linker tests (history)","54 regression; 18x batch","generation works","SMILES-level diversity","-","KEEP","P0","25f04b5"),
("E2","Linker","Link-INVENT-style scoring + optimizer","tools/linker_scoring.py; linker_optimizer.py","score/optimize","LinkerGenerationAgent","LinkerDesignToolbox","internal re-implementation","Y","FULL","15 linker tests (history)","rho 0.80 (internal)","scoring replicable","NOT official Link-INVENT","-","FREEZE","P1","e827862"),
("E3","Linker","Enumeration / classes / descriptors","linker_generator.py; linker_scanner.py; brics_recap_engine.py; known/matched","enumerate_linkers()","linker stage","LinkerDesignToolbox","RDKit/BRICS","Y","PARTIAL","tests present","-","enumeration works","PEG/alkyl/rigid partial","-","UPGRADE","P2","tool files"),
("F1","Construction","PROTAC assembly + validity (BRICS/RECAP)","molecular_constructor.py; protac_toolbox.py","construct_with_all_strategies()","MolecularConstructionAgent","ConstructionStrategyToolbox","RDKit","Y","FULL","construction tests","deterministic e2e","chemically valid assembly","no SA scoring","-","KEEP","P0","real_nodes _construction"),
("F2","Construction","Stereochemistry enumeration","search_control_agent.py (StereochemistryEnumerationAgent)","enumerate_stereoisomers()","agent","-","RDKit","Y","PARTIAL","agent tests","-","enumeration works","no downstream selectivity filter","-","UPGRADE","P2","stereochemistry_engine.py"),
("G1","Ternary","P4ward ternary modeling","p4ward_wrapper.py; ternary_agent.py","run_ternary_screening()","TernaryFeasibilityAgent","TernaryComplexToolbox","P4ward (docker)","Y","WRAPPER","gated tests (env)","checkpoint/benchmark wiring","callable with service","needs docker/local; not default CI","-","KEEP","P1","p4ward_wrapper.py"),
("G2","Ternary","Ternary proxy + pLDDT gate + ensemble","ternary_stage.py; ternary_feasibility.py; structural_scoring.py","run_ternary_ensemble(); plddt_gate()","TernaryFeasibilityAgent","TernaryComplexToolbox","AlphaFold pLDDT","Y","PARTIAL","architecture tests","12' revision (history)","EXPLORATORY","proxy geometry","-","UPGRADE","P1","ternary_stage.py"),
("G3","Ternary","Optional heavy backends (SE3-protacs etc.)","external_model_adapters.py; cloned repos","run_se3_*","-","-","SE3-protacs / PROTAC-Model clones","N","UNKNOWN","external smoke","-","UNKNOWN","no validated wrapper benchmark","clone census lacking","CONNECT","P2","data/protac_repos/repos"),
("H1","Ubiquitination","Lysine geometry (SASA/E2)","modules/lysine_ubiquitination_feasibility/*","score_lysine_ubiquitination()","structure CLI","lysine tool","Module-2 numeric SASA","Y","FULL","8 tests","synthetic fixtures","static-geometry surrogate","real-PDB benchmark pending","M6 lysines.py extra census","KEEP","P0","M2 VALIDATION.md"),
("I1","Degradation","pDC50/Dmax chemprop + conformal","chemprop_degradation.py; degradation_endpoint.py","predict_degradation_*","DegradationPredictionAgent","PredictionAndADMETToolbox","internal chemprop","Y","FULL","endpoint tests (15 history)","G6 81.6%/0.900; conformal","retrospective pDC50/Dmax","no prospective set","many degradation files","KEEP","P0","outputs/benchmark/chemprop*"),
("I2","Degradation","Modules M4 + M5 (small-data, cell-context)","modules/degradation_ml; modules/cell_context_selector","predict_degradation(); predict_cell_context()","module tools","degradation_ml_tool; cell_context_tool","internal joblib","Y","FULL","M4 9 + M5 16 tests","grouped splits; M5 A-G","M5 cell-context retro","M4 small n; M5 no proteomics","parallel chemprop pipeline","KEEP","P0","module VALIDATION docs"),
("I3","Degradation","Kinetics / hook / dose-response","tools/kinetics.py; dose_response_simulator.py; Module 1","simulate_hook_effect()","HookEffectPredictionAgent","dose CLI","analytic (M1)","Y","FULL","M1 24 tests","MC audit","equilibrium metrics (CALCULATED)","not kinetics","kinetics.py vs M1 overlap","FREEZE","P2","M1 VALIDATION"),
("J1","Cell context","Cell-line mapping + DepMap features","modules/cell_context_selector/{cellline,omics}.py","map_cell_lines(); ensure_curated_expression()","CellContextAgent","cell_context_tool","DepMap 24Q4","Y","FULL","M5/M6 tests","coverage 137/180","mapping/expression coverage","DepMap lines only","M6 reuses M5","KEEP","P0","M5 VALIDATION.md"),
("J2","Cell context","Transcriptomic context pDC50","modules/cell_context_selector","predict_cell_context()","CellContextAgent","cell_context_tool","DepMap TPM","Y","FULL","16 tests","A-G; unseen-PROTAC R2 .605","cell-context-aware (retro)","unseen-cell/proteotype NOT claimed","-","KEEP","P0","M5 VALIDATION/claims"),
("K1","Selectivity","Expression-restriction (M6 axis)","e3_opportunity/selectivity.py","selectivity_axis()","E3 tool","e3_opportunity_tool","DepMap lineage breadth","Y","PARTIAL","M6 tests","-","restriction supported","not degradome selectivity","-","KEEP","P2","selectivity.py"),
("K2","Selectivity","Proteome/cell-context heuristic","tools/proteome_selectivity.py","score_proteome_context()","proteome CLI","-","seed prior table","Y","SKELETON","tests present","-","NOT SUPPORTED","3-row seed atlas v0.1","superseded by M6 axis","FREEZE","P2","proteome_selectivity.py"),
("K3","Selectivity","Neosubstrate / off-target degradation risk","-","-","-","-","-","N","MISSING","-","-","NOT SUPPORTED","absent","-","BUILD","P1","no files"),
("L1","Permeability","bRo5 descriptors + rules","tools/admet_integration.py","predict_admet_properties()","ADMETAgent","PredictionAndADMETToolbox","RDKit descriptors","Y","PARTIAL","admet tests","-","rule descriptors only","no 3D PSA/IMHB/exposure","-","UPGRADE","P1","admet_integration.py"),
("M1","ADME","ADMET-AI endpoints (isolated venv)","admet_integration.py; scripts/run_admet_ai.py","_run_admet_ai()","ADMETAgent","PredictionAndADMETToolbox","ADMET-AI","Y","WRAPPER","venv-gated tests","-","endpoints when venv runs","rules fallback default","admet_integration vs admet_predictor(s)","KEEP","P1",".venvs/admet"),
("N1","Safety","hERG/Ames/DILI + PAINS/Brenk","admet_integration; rdkit filters","predict_admet_properties()","ADMETAgent","PredictionAndADMETToolbox","ADMET-AI + RDKit","Y","PARTIAL","tests","-","EXPLORATORY","rules default w/o venv","-","UPGRADE","P1","admet_integration.py"),
("O1","Synthesis","Retrosynthesis (ASKCOS/AiZynth optional)","retrosynthesis.py; retrosynthesis_engines.py; retrosynthesis_filter.py","run_retrosynthesis()","construction/validation agents","-","ASKCOS HTTPS / AiZynth","Y","WRAPPER","14 retrosynthesis tests","verified-synthesis briefs","routes when reachable","offline fallback default","two engine layers","KEEP","P1","retrosynthesis_engines.py"),
("O2","Synthesis","Building blocks / synthetic-accessibility","magnetdb_lookup.py; linker matching","sa/routes","-","-","MagnetDB + RDKit","Y","PARTIAL","-","-","EXPLORATORY","no SA score model","-","UPGRADE","P2","magnetdb_lookup.py"),
("P1","Novelty","Novelty vs known PROTACs + MagnetDB","tools/novelty_checker.py","check_novelty()","NoveltyAgent","ReviewAndEvolutionToolbox","MagnetDB + ProtacDB","Y","FULL","novelty tests","bounded evolution SeenSet","novelty filter callable","not IP/patent search","-","KEEP","P2","novelty_checker.py"),
("Q1","Ranking","Pareto NSGA-II + meta review + next-test suggestions","pareto_ranking.py; ranker.py; ranking_agent.py","run_meta_review(); propose_active_learning_next_tests()","RankingAgent","ReviewAndEvolutionToolbox","internal","Y","FULL","pareto 7 tests (history)","-","multiobjective ranking","thresholds heuristic","ranking across 3 files","KEEP","P1","pareto_ranking.py"),
("R1","PK/PD","PK / PBPK / exposure / in vivo","-","-","-","-","-","N","MISSING","-","-","NOT SUPPORTED","absent","-","DEFER","P3","no files"),
("S1","Active learning","Agent suggestions; scientific module absent","agents/active_learning_agent.py","ActiveLearningAgent.run()","ActiveLearningAgent","ReviewAndEvolutionToolbox","internal","Y","EXPERIMENTAL","agent tests","-","EXPLORATORY","no experiment-selection module","module M7 not built","BUILD (post-audit)","P1","active_learning_agent.py"),
("T1","Reporting","Report + provenance + per-module claims","agents/report_agent.py; tools/report_generator.py","generate_report()","ReportAgent","-","-","Y","FULL","report tests","-","deterministic reports","no single global registry","module CLAIMS.md only (M6)","UPGRADE","P1","report_agent.py; CLAIMS.md"),
("T2","Reporting","Deep research evidence","research/*; deep_research cli","deep_research","research agents","-","EuropePMC/PubMed/OpenAlex/Crossref/SEARX","Y","FULL","29 research tests","-","retrieval + claim grading","network/keys","-","KEEP","P1","research/"),
]

assert len(CAP_FIELDS) == 18
for row in C:
    assert len(row) == 18, f"row {row[0]} has {len(row)} fields"
C = [dict(zip(CAP_FIELDS, r)) for r in C]

with open(ART / "capability_matrix.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=CAP_FIELDS); w.writeheader(); w.writerows(C)

# ---------------------------------------------------------------- backends
BE_FIELDS = ["backend", "repo_found", "installed", "wrapper", "callable",
             "runtime_connected", "tested", "benchmarked", "production_ready",
             "files", "missing_work", "notes"]
BE = [
("RDKit","Y","Y","internal","Y","Y","Y","Y","Y","core modules/tools","-","chemistry backbone"),
("Chemprop (degradation ML)","Y","Y","chemprop_degradation.py","Y","Y","Y","Y (G6/conformal)","retrospective","outputs/benchmark/chemprop*","prospective validation","trained ensembles"),
("ADMET-AI","Y","venv .venvs/admet","admet_integration","Y (venv)","Y","venv-gated","partial","PARTIAL","admet_integration.py; scripts/run_admet_ai.py","endpoint breadth","rules fallback default"),
("TACK model","Y","Y","tack_degradation.py","Y","Y","Y","scaffold rho .80","PARTIAL","data/tack/*","opinion-only role","second opinion"),
("P4ward","Y","docker/local","p4ward_wrapper.py","Y (env-gated)","Y","gated","wiring","PARTIAL","p4ward_wrapper.py; deploy/p4ward_worker.py","default CI path","heavy external"),
("SE3-protacs / PROTAC-Model / PROTACFold / TERNIFY / SynGlue orig (30+ clones)","Y","isolated envs","external_model_adapters.py; repo wrappers","partial","N (core graph)","smoke","none","UNKNOWN","data/protac_repos/repos/*; .venvs/protac-*","runtime census + benchmark","clone inventory"),
("AlphaFold (DB)","Y","client","alphafold_client.py","Y (network)","Y","network-skip","pLDDT gate","PARTIAL","alphafold_client.py","local structure cache","monomer"),
("DepMap 24Q4","Y","cached raw","cell_context_selector/omics.py; e3 context.py","Y","Y","Y","M5 A-G; M6 retrieval","Y (transcriptomics)","outputs/omics_cache + module data","proteomics","raw not committed"),
("UniProt","Y","client + cache","uniprot_client.py; localization.py","Y","Y","Y","annotation refresh","PARTIAL","module data (78 genes)","coverage","-"),
("ChEMBL/BindingDB/PubChem/DrugBank","Y","clients","*_client.py + *_lookup.py","Y (network)","Y","network-skip","binder census","PARTIAL","tools/*client.py","offline cache; dup layers","keys"),
("ASKCOS","Y","HTTP client","retrosynthesis_engines.AskcosClient","Y (network)","Y","Y","verified-synthesis briefs","PARTIAL","retrosynthesis_engines.py","offline fallback default","-"),
("AiZynthFinder","Y","optional env/pkg","retrosynthesis_engines (aizynth)","optional","N default","fallback tests","none","UNKNOWN","data/synthesis_prediction envs","install+wiring","optional"),
("Link-INVENT (official)","N","N","internal style scorer","N (official)","N","internal tests","internal rho .80","NOT SUPPORTED","linker_scoring.py","official package optional","re-implementation"),
("Rosetta/PRosettaC/MegaDock/COMPASS/Boltz/OpenMM/GROMACS","N","N","-","N","N","N","N","UNKNOWN","work/boltz_output (attempt only)","-","not integrated"),
("Open Targets / HPA / SwissADME-like / admetSAR","N","N","-","N","N","N","N","UNKNOWN","-","-","absent"),
("LangGraph + LLM providers","Y","deps","agentic_core.py; gateway","Y","Y (agentic mode)","architecture tests","e2e deterministic","PARTIAL","agents/runtime.py","-","deterministic mode default"),
]
for row in BE:
    assert len(row) == len(BE_FIELDS), row[0]
BE = [dict(zip(BE_FIELDS, r)) for r in BE]
with open(ART / "backend_matrix.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=BE_FIELDS); w.writeheader(); w.writerows(BE)

# ---------------------------------------------------------------- gaps
GAP_FIELDS = ["id", "priority", "gap", "why_it_matters", "backend_exists",
              "action", "dependency", "complexity", "tests_required",
              "validation_required"]
GAP = [
("GAP01","P0","Prospective scientific validation of degradation/E3/cell-context predictions","all ML claims retrospective (absence-of-record negatives)","wet-lab/PDX/literature prospective sets","VALIDATE","n/a","M","-","prospective benchmark protocol"),
("GAP02","P0","Unified claims registry + config/scientific_status.yaml sync","config stale (M6=PLANNED); per-module CLAIMS only","internal","CONNECT","docs/config","S","verify script","claims cross-check"),
("GAP03","P0","Real ternary evidence inside design/ranking loop","M6 structural_feasibility=None for all pairs; no ternary in default CI","P4ward docker + SE3 clones","CONNECT","docker","M","integration tests","ternary retrieval benchmark"),
("GAP04","P1","Proteomics + wider cell context (M5 leg E)","proteotype unclaimable; unmapped lines None","DepMap proteomics/user data","UPGRADE","data curation","M","-","proteomics coverage + leg E"),
("GAP05","P1","Selectivity: neosubstrate / off-target degradation risk","K axes heuristic only","literature datasets","BUILD","-","L","unit tests","paralog + degradome validation"),
("GAP06","P1","Permeability / intracellular exposure (3D PSA, IMHB, P-gp)","only 2D rules","OpenADMET-style / ADMET-AI subset","INTEGRATE","external","M","-","PK assay correlation"),
("GAP07","P1","Metabolic stability / CYP breadth","ADME incomplete","ADMET-AI subset / admetSAR","INTEGRATE","external","M","-","stability benchmarks"),
("GAP08","P1","Active-learning scientific module (M7) + feedback loop","agent layer only","internal","BUILD","modules","L","module tests","retrospective selection benchmarks"),
("GAP09","P1","Dual-graph consistency (31-node vs 17-node)","divergent node sets; exit_vector stub","internal","CONNECT","agents","M","graph parity tests","e2e parity"),
("GAP10","P2","Synthetic-accessibility scoring in construction","no SA score at build","AiZynth/ASKCOS","INTEGRATE","network","M","-","route validation"),
("GAP11","P2","Official Link-INVENT optional backend","internal style scorer only","Link-INVENT package","INTEGRATE (optional)","external","M","-","linker parity benchmark"),
("GAP12","P2","Ternary/docking not in default CI","env-gated only","docker","CONNECT","CI infra","M","-","-"),
("GAP13","P2","Cloned external-repo runtime census","30+ clones not wired","-","CONNECT","repos","L","adapter smoke","per-repo benchmark"),
("GAP14","P3","PK/PBPK/exposure + in vivo translation","absent","OSP etc.","DEFER","external","L","-","in vivo correlation"),
("GAP15","P2","Client/lookup duplication + offline caching","two layers per source","internal","REMOVE_DUPLICATE","tools","M","-","-"),
]
for row in GAP:
    assert len(row) == len(GAP_FIELDS), row[0]
GAP = [dict(zip(GAP_FIELDS, r)) for r in GAP]
with open(ART / "gap_matrix.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=GAP_FIELDS); w.writeheader(); w.writerows(GAP)

inventory = {
    "generated": "2026-09-02 repository audit (no build performed)",
    "counts": {
        "sequential_modules": 6, "module_7_planned": True,
        "agent_files": len(list((ROOT / "protacxtend/agents").glob("*.py"))),
        "deterministic_graph_nodes": 31, "real_nodes_agents": 17,
        "tool_files": len(list((ROOT / "protacxtend/tools").glob("*.py"))),
        "toolbox_classes": 9,
        "cloned_external_repos": len(list((ROOT / "data/protac_repos/repos").glob("*"))),
        "tests_collected": {"modules": 95, "agent_tests": 414,
                            "root_tests": 122, "research": 29},
    },
    "capabilities": C, "backends": BE, "gaps": GAP,
}
(ART / "repository_inventory.json").write_text(
    json.dumps(inventory, indent=1, default=str))
from collections import Counter
print("wrote artifacts:", len(C), "caps /", len(BE), "backends /", len(GAP), "gaps")
print("status:", dict(Counter(c["status"] for c in C)))
print("action:", dict(Counter(c["action"] for c in C)))
