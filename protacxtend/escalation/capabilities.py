"""Capability taxonomy + external fallback map for the escalation subsystem.

The map answers one question: *if capability X fails internally, which
registered external tools can legitimately stand in for it?*  The order in each
fallback list is a preference order (cheapest/local/most-validated first).
"""

from __future__ import annotations

from typing import Dict, List

# ── human-readable capability descriptions ─────────────────────────────
CAPABILITY_DESCRIPTIONS: dict[str, str] = {
    "smiles_validation": "Parse, sanitize and validate a SMILES string.",
    "cheminformatics": "Descriptors, substructure search and molecular standardisation.",
    "conformer_generation": "Generate 3D conformers/ensembles from a 2D molecule.",
    "ligand_preparation": "Prepare ligands for docking (protonation, PDBQT/SDF).",
    "structure_preparation": "Clean/repair protein structures for modelling.",
    "ligand_docking": "Dock a small molecule into a protein binding site.",
    "protein_protein_docking": "Dock two protein partners.",
    "ternary_complex_modeling": "Model a target–PROTAC–E3 ternary complex.",
    "binding_energy": "Score/refine a protein–ligand or protein–protein interface.",
    "molecular_dynamics": "Run molecular dynamics / enhanced sampling.",
    "linker_generation": "Generate or optimise PROTAC linkers.",
    "de_novo_generation": "Generate novel molecular structures.",
    "fragmentation": "Fragment molecules / matched molecular pairs.",
    "retrosynthesis": "Plan or predict synthetic routes.",
    "reaction_prediction": "Predict reaction products / atom mapping.",
    "synthetic_accessibility": "Score synthetic accessibility / complexity.",
    "admet_toxicity": "Predict ADME and toxicity endpoints.",
    "degradation_prediction": "Predict DC50/Dmax or degradation probability.",
    "molecular_ml": "General molecular property prediction models.",
    "protein_language_models": "Protein sequence embeddings / foundation models.",
    "literature_mining": "Extract entities/relations from scientific text.",
    "patent_mining": "Search chemistry patents.",
    "proteomics": "Process / analyse mass-spectrometry proteomics data.",
    "image_analysis": "Quantify cell/tissue images.",
    "molecular_visualization": "Render / inspect molecular structures.",
    "quantum_chemistry": "Semi-empirical or DFT calculations.",
    "workflow_platforms": "External workflow orchestration platforms.",
}

# ── internal module / tool id → capability ─────────────────────────────
INTERNAL_TOOL_CAPABILITY: dict[str, str] = {
    # fully-qualified module paths
    "protacxtend.tools.rdkit_chemistry": "cheminformatics",
    "protacxtend.tools.chemistry_core": "smiles_validation",
    "protacxtend.tools.rdkit_validator": "smiles_validation",
    "protacxtend.tools.stereochemistry_engine": "cheminformatics",
    "protacxtend.tools.docking_pipeline": "ligand_docking",
    "protacxtend.tools.structural_scoring": "binding_energy",
    "protacxtend.tools.ternary_feasibility": "ternary_complex_modeling",
    "protacxtend.tools.ternary_ensemble": "ternary_complex_modeling",
    "protacxtend.tools.p4ward_wrapper": "ternary_complex_modeling",
    "protacxtend.tools.synglue_degradation": "degradation_prediction",
    "protacxtend.tools.tack_degradation": "degradation_prediction",
    "protacxtend.tools.degradation_endpoint": "degradation_prediction",
    "protacxtend.tools.chemprop_degradation": "degradation_prediction",
    "protacxtend.tools.admet_predictors": "admet_toxicity",
    "protacxtend.tools.admet_integration": "admet_toxicity",
    "protacxtend.tools.linker_generator": "linker_generation",
    "protacxtend.tools.generative_linker": "linker_generation",
    "protacxtend.tools.linker_optimizer": "linker_generation",
    "protacxtend.tools.retrosynthesis": "retrosynthesis",
    "protacxtend.tools.retrosynthesis_engines": "retrosynthesis",
    "protacxtend.tools.retrosynthesis_filter": "synthetic_accessibility",
    "protacxtend.tools.kinetics": "molecular_dynamics",
    "protacxtend.tools.online_ligand_miner": "literature_mining",
    # short aliases (accept bare module/tool names too)
    "rdkit_chemistry": "cheminformatics",
    "chemistry_core": "smiles_validation",
    "docking_pipeline": "ligand_docking",
    "ternary_feasibility": "ternary_complex_modeling",
    "synglue_degradation": "degradation_prediction",
    "tack_degradation": "degradation_prediction",
    "admet_predictors": "admet_toxicity",
    "linker_generator": "linker_generation",
    "retrosynthesis": "retrosynthesis",
    "retrosynthesis_engines": "retrosynthesis",
    # agentic tool-surface names (protacxtend/agentic/registry.py)
    "predict_degradation": "degradation_prediction",
    "predict_cell_context": "degradation_prediction",
    "predict_admet": "admet_toxicity",
    "generate_linkers": "linker_generation",
    "construct_protac": "cheminformatics",
    "check_synthetic_feasibility": "synthetic_accessibility",
    "model_ternary_complex": "ternary_complex_modeling",
    "score_lysine_ubiquitination": "ternary_complex_modeling",
    "simulate_hook_effect": "cheminformatics",
    "predict_cooperativity": "cheminformatics",
    "retrieve_pdb": "structure_preparation",
    "rank_candidates": "cheminformatics",
    "inspect_smiles": "smiles_validation",
    "detect_exit_vectors": "cheminformatics",
    "deep_research": "literature_mining",
    "search_europe_pmc": "literature_mining",
    "search_pubmed": "literature_mining",
    "verify_crossref": "literature_mining",
    "retrieve_fulltext": "literature_mining",
    "resolve_target": "literature_mining",
    "search_uniprot": "literature_mining",
    "retrieve_target_binders": "literature_mining",
    "search_bindingdb": "literature_mining",
}

# ── capability → ordered external fallbacks (exact toolkit-registry names) ─
CAPABILITY_FALLBACKS: dict[str, list[str]] = {
    "smiles_validation": ["RDKit ETKDG", "OpenBabel"],
    "cheminformatics": ["RDKit ETKDG", "OpenBabel", "mmpdb"],
    "conformer_generation": ["RDKit ETKDG", "CREST", "OpenEye OMEGA"],
    "ligand_preparation": ["Meeko", "MGLTools", "OpenBabel", "Schrodinger LigPrep", "Epik"],
    "structure_preparation": ["PDBFixer", "PDB2PQR", "PropKa", "OpenBabel"],
    "ligand_docking": [
        "AutoDock Vina", "Smina", "GNINA", "AutoDock-GPU", "AutoDock4",
        "rDock", "DOCK6", "LeDock", "PLANTS", "Glide", "GOLD",
    ],
    "protein_protein_docking": [
        "HADDOCK3", "LightDock", "MEGADOCK", "ZDOCK", "RosettaDock",
        "ClusPro", "HADDOCK", "PatchDock", "FireDock",
    ],
    "ternary_complex_modeling": [
        "PRosettaC", "HADDOCK3", "AlphaFold-Multimer",
        "ColabFold", "HADDOCK", "ClusPro",
    ],
    "binding_energy": ["gmx_MMPBSA", "MMPBSA.py", "Rosetta InterfaceAnalyzer", "FireDock"],
    "molecular_dynamics": ["OpenMM", "GROMACS", "NAMD", "AMBER / AmberTools", "PLUMED"],
    "linker_generation": ["DeLinker", "DiffLinker", "LinkInvent", "SyntaLinker", "CReM", "REINVENT"],
    "de_novo_generation": ["REINVENT", "CReM", "MolDQN", "GuacaMol", "MOSES"],
    "fragmentation": ["mmpdb", "BRICS", "RECAP"],
    "retrosynthesis": ["AiZynthFinder", "ASKCOS", "ASKCOS Tree Builder", "Molecular Transformer", "RDKit + OpenNMT workflow"],
    "reaction_prediction": ["RXNMapper", "RDChiral", "IBM RXN"],
    "synthetic_accessibility": ["RAscore", "SCScore"],
    "admet_toxicity": ["DeepPurpose", "Therapeutics Data Commons", "OpenADMET", "ADMETlab 3.0", "SwissADME", "pkCSM", "ProTox-II"],
    "degradation_prediction": ["Chemprop", "DeepPROTACs", "PROTAC-STAN", "DegradeMaster"],
    "molecular_ml": ["Chemprop", "DeepChem", "Uni-Mol", "GROVER", "ChemBERTa", "MolFormer"],
    "protein_language_models": ["ESM-2", "ProtT5"],
    "literature_mining": ["SciSpacy", "ChemDataExtractor", "PubTator", "OPSIN"],
    "patent_mining": ["SureChEMBL", "Lens.org", "Google Patents"],
    "proteomics": ["FragPipe", "Perseus", "Proteome Discoverer / MaxQuant"],
    "image_analysis": ["CellProfiler"],
    "molecular_visualization": ["PyMOL", "NGLView", "UCSF ChimeraX", "VMD", "Mol*"],
    "quantum_chemistry": ["xTB", "MOPAC", "ORCA", "CREST", "Gaussian"],
    "workflow_platforms": ["KNIME", "Galaxy", "Pipeline Pilot"],
}


def capability_for(internal_tool: str) -> str:
    """Resolve an internal module/tool id to a capability key.

    Accepts a fully-qualified module path, a bare module name, or a capability
    key already. Falls back to ``cheminformatics`` when unknown so escalation
    always has somewhere to look.
    """
    if not internal_tool:
        return "cheminformatics"
    key = internal_tool.strip()
    if key in CAPABILITY_DESCRIPTIONS:
        return key
    if key in INTERNAL_TOOL_CAPABILITY:
        return INTERNAL_TOOL_CAPABILITY[key]
    short = key.rsplit(".", 1)[-1]
    if short in CAPABILITY_DESCRIPTIONS:
        return short
    if short in INTERNAL_TOOL_CAPABILITY:
        return INTERNAL_TOOL_CAPABILITY[short]
    # heuristic suffix matching
    lowered = short.lower()
    for cap in CAPABILITY_DESCRIPTIONS:
        if cap in lowered or lowered in cap:
            return cap
    return "cheminformatics"


def fallbacks_for(capability: str) -> list[str]:
    """Ordered external tool names registered for a capability."""
    return list(CAPABILITY_FALLBACKS.get(capability, []))


def all_capabilities() -> list[str]:
    return sorted(CAPABILITY_DESCRIPTIONS)
