"""Central PROTAC toolkit registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from protacxtend.tools.toolkit_categories import CATEGORIES


ALLOWED_STATUS = {
    "available",
    "installed",
    "missing",
    "registered_but_not_executable",
    "commercial_not_available",
    "api_key_required",
    "web_only",
    "python_package_missing",
    "binary_missing",
    "stub_only",
    "disabled",
}

ALLOWED_RELIABILITY = {"production", "research", "experimental", "wrapper_only", "metadata_only"}


@dataclass
class ToolkitTool:
    tool_name: str
    category: str
    subcategory: str
    purpose: str
    executable_type: str
    install_hint: str
    executable_names: list[str]
    python_imports: list[str]
    api_required: bool
    license_type: str
    commercial: bool
    local_executable: bool
    web_service: bool
    agent_use_case: str
    expected_inputs: list[str]
    expected_outputs: list[str]
    status: str
    reliability_level: str
    notes: str


def _tool(
    tool_name: str,
    category: str,
    subcategory: str,
    purpose: str,
    executable_type: str = "cli",
    install_hint: str = "",
    executable_names: list[str] | None = None,
    python_imports: list[str] | None = None,
    api_required: bool = False,
    license_type: str = "open-source",
    commercial: bool = False,
    local_executable: bool = True,
    web_service: bool = False,
    agent_use_case: str = "",
    expected_inputs: list[str] | None = None,
    expected_outputs: list[str] | None = None,
    status: str = "registered_but_not_executable",
    reliability_level: str = "research",
    notes: str = "",
) -> dict[str, Any]:
    item = ToolkitTool(
        tool_name=tool_name,
        category=category,
        subcategory=subcategory,
        purpose=purpose,
        executable_type=executable_type,
        install_hint=install_hint,
        executable_names=executable_names or [],
        python_imports=python_imports or [],
        api_required=api_required,
        license_type=license_type,
        commercial=commercial,
        local_executable=local_executable,
        web_service=web_service,
        agent_use_case=agent_use_case or purpose,
        expected_inputs=expected_inputs or ["task-specific inputs"],
        expected_outputs=expected_outputs or ["task-specific outputs"],
        status=status,
        reliability_level=reliability_level,
        notes=notes,
    )
    data = asdict(item)
    if data["category"] not in CATEGORIES:
        raise ValueError(f"Unknown category: {data['category']}")
    if data["status"] not in ALLOWED_STATUS:
        raise ValueError(f"Invalid status: {data['status']}")
    if data["reliability_level"] not in ALLOWED_RELIABILITY:
        raise ValueError(f"Invalid reliability_level: {data['reliability_level']}")
    return data


TOOLKIT_REGISTRY: list[dict[str, Any]] = [
    # molecular_visualization
    _tool("PyMOL", "molecular_visualization", "desktop_viewer", "3D molecular visualization", executable_names=["pymol"]),
    _tool("UCSF ChimeraX", "molecular_visualization", "desktop_viewer", "3D molecular visualization", executable_names=["chimerax"]),
    _tool("UCSF Chimera", "molecular_visualization", "desktop_viewer", "3D molecular visualization", executable_names=["chimera"]),
    _tool("VMD", "molecular_visualization", "desktop_viewer", "Trajectory and structure visualization", executable_names=["vmd"]),
    _tool("NGLView", "molecular_visualization", "python_widget", "Notebook visualization", executable_type="python_package", python_imports=["nglview"], local_executable=False),
    _tool("Mol*", "molecular_visualization", "web_viewer", "Web molecular visualization", executable_type="web", web_service=True, local_executable=False, reliability_level="metadata_only"),
    # ligand_docking
    _tool("AutoDock Vina", "ligand_docking", "docking_engine", "Protein-ligand docking", executable_names=["vina"], reliability_level="production"),
    _tool("AutoDock-GPU", "ligand_docking", "docking_engine", "GPU docking", executable_names=["autodock_gpu"], reliability_level="research"),
    _tool("AutoDock4", "ligand_docking", "docking_engine", "AutoDock4 docking", executable_names=["autodock4", "autodock4.exe"]),
    _tool("Smina", "ligand_docking", "docking_engine", "Vina-like docking and scoring", executable_names=["smina"]),
    _tool("GNINA", "ligand_docking", "docking_engine", "CNN-augmented docking", executable_names=["gnina"]),
    _tool("rDock", "ligand_docking", "docking_engine", "Docking for proteins and nucleic acids", executable_names=["rbdock", "rDock"]),
    _tool("DOCK6", "ligand_docking", "docking_engine", "UCSF DOCK6 docking", executable_names=["dock6"]),
    _tool("LeDock", "ligand_docking", "docking_engine", "Fast docking engine", executable_names=["ledock"]),
    _tool("PLANTS", "ligand_docking", "docking_engine", "Ant colony docking", executable_names=["plants"]),
    _tool("GOLD", "ligand_docking", "docking_engine", "CCDC docking", executable_names=["gold_auto"], commercial=True, license_type="proprietary"),
    _tool("Glide", "ligand_docking", "docking_engine", "Schrodinger docking", executable_names=["glide"], commercial=True, license_type="proprietary"),
    _tool("MOE Dock", "ligand_docking", "docking_engine", "MOE docking", executable_names=["moebatch"], commercial=True, license_type="proprietary"),
    _tool("ICM-Pro", "ligand_docking", "docking_engine", "ICM docking", executable_names=["icm"], commercial=True, license_type="proprietary"),
    # Rosetta / interface
    _tool("PRosettaC", "ternary_complex_modeling", "protac_modeling", "PROTAC ternary modeling with Rosetta", executable_names=["python"], python_imports=["rosetta"], local_executable=False, reliability_level="research"),
    _tool("RosettaDock", "protein_protein_docking", "rosetta", "Protein-protein docking", executable_names=["docking_protocol"]),
    _tool("RosettaLigand", "ligand_docking", "rosetta", "Rosetta ligand docking", executable_names=["rosetta_scripts"]),
    _tool("Rosetta InterfaceAnalyzer", "binding_energy", "rosetta", "Interface scoring", executable_names=["InterfaceAnalyzer"]),
    _tool("PyRosetta", "protein_protein_docking", "python_binding", "Rosetta Python interface", executable_type="python_package", python_imports=["pyrosetta"], local_executable=False),
    # protein-protein / ternary docking
    _tool("HADDOCK", "protein_protein_docking", "web_docking", "Protein-protein docking", executable_type="web", web_service=True, local_executable=False),
    _tool("HADDOCK3", "protein_protein_docking", "cli_docking", "HADDOCK3 local docking", executable_names=["haddock3"]),
    _tool("ClusPro", "protein_protein_docking", "web_docking", "Protein-protein docking", executable_type="web", web_service=True, local_executable=False),
    _tool("MEGADOCK", "protein_protein_docking", "cli_docking", "FFT protein docking", executable_names=["megadock"]),
    _tool("ZDOCK", "protein_protein_docking", "cli_docking", "Rigid-body docking", executable_names=["zdock"]),
    _tool("PatchDock", "protein_protein_docking", "cli_or_web", "Shape complementarity docking", executable_names=["patch_dock"], web_service=True),
    _tool("FireDock", "protein_protein_docking", "refinement", "Docking refinement", executable_names=["firedock"]),
    _tool("LightDock", "protein_protein_docking", "cli_docking", "Swarm docking", executable_names=["lightdock3.py", "lightdock"]),
    _tool("EquiDock", "protein_protein_docking", "ml_docking", "Equivariant docking", executable_type="python_package", python_imports=["torch"], local_executable=False, reliability_level="experimental"),
    _tool("AlphaFold-Multimer", "ternary_complex_modeling", "structure_prediction", "Multimer structure prediction", executable_names=["alphafold"], python_imports=["jax"], local_executable=False),
    _tool("ColabFold", "ternary_complex_modeling", "structure_prediction", "Fast structure prediction", executable_names=["colabfold_batch"]),
    # molecular_dynamics
    _tool("GROMACS", "molecular_dynamics", "md_engine", "MD simulation", executable_names=["gmx"], reliability_level="production"),
    _tool("OpenMM", "molecular_dynamics", "md_engine", "GPU MD simulation", executable_type="python_package", python_imports=["openmm"], local_executable=False),
    _tool("AMBER / AmberTools", "molecular_dynamics", "md_engine", "AMBER MD and prep", executable_names=["pmemd", "sander", "ante-MMPBSA"]),
    _tool("NAMD", "molecular_dynamics", "md_engine", "Scalable MD", executable_names=["namd2", "namd3"]),
    _tool("CHARMM", "molecular_dynamics", "md_engine", "Force-field MD suite", executable_names=["charmm"], commercial=True, license_type="mixed"),
    _tool("Desmond", "molecular_dynamics", "md_engine", "Schrodinger MD", executable_names=["desmond"], commercial=True, license_type="proprietary"),
    _tool("PLUMED", "molecular_dynamics", "enhanced_sampling", "Enhanced sampling plugin", executable_names=["plumed"]),
    # binding_energy
    _tool("gmx_MMPBSA", "binding_energy", "mmgbsa", "GROMACS MM/PBSA", executable_names=["gmx_MMPBSA"]),
    _tool("MMPBSA.py", "binding_energy", "mmgbsa", "AMBER MMPBSA", executable_names=["MMPBSA.py"]),
    # ligand/structure prep
    _tool("Meeko", "ligand_preparation", "pdbqt_prep", "Ligand prep for AutoDock", executable_type="python_package", python_imports=["meeko"], local_executable=False),
    _tool("MGLTools", "ligand_preparation", "pdbqt_prep", "AutoDockTools preparation", executable_names=["prepare_ligand4.py", "prepare_receptor4.py"]),
    _tool("PDBFixer", "structure_preparation", "protein_cleanup", "Fix missing atoms/residues", executable_type="python_package", python_imports=["pdbfixer"], local_executable=False),
    _tool("PropKa", "structure_preparation", "protonation", "pKa/protonation estimation", executable_names=["propka3"]),
    _tool("PDB2PQR", "structure_preparation", "protonation", "PDB to PQR conversion", executable_names=["pdb2pqr"]),
    _tool("OpenBabel", "ligand_preparation", "format_conversion", "Molecule format conversion", executable_names=["obabel", "babel"], python_imports=["openbabel"], executable_type="cli_or_python"),
    # conformer/quantum
    _tool("RDKit ETKDG", "conformer_generation", "rdkit_conformers", "Conformer generation", executable_type="python_package", python_imports=["rdkit"], local_executable=False, reliability_level="production"),
    _tool("CREST", "conformer_generation", "qm_conformers", "Conformer ensemble search", executable_names=["crest"]),
    _tool("xTB", "quantum_chemistry", "semi_empirical", "Semi-empirical QM", executable_names=["xtb"]),
    _tool("MOPAC", "quantum_chemistry", "semi_empirical", "Semi-empirical QM", executable_names=["mopac"]),
    _tool("ORCA", "quantum_chemistry", "dft", "DFT calculations", executable_names=["orca"]),
    _tool("Gaussian", "quantum_chemistry", "dft", "Commercial quantum chemistry", executable_names=["g16", "g09"], commercial=True, license_type="proprietary"),
    _tool("OpenEye OMEGA", "conformer_generation", "commercial_conformers", "Commercial conformer generation", executable_names=["omega2"], commercial=True, license_type="proprietary"),
    _tool("Schrodinger LigPrep", "ligand_preparation", "commercial_prep", "Schrodinger ligand prep", executable_names=["ligprep"], commercial=True, license_type="proprietary"),
    _tool("Epik", "ligand_preparation", "commercial_prep", "Schrodinger protonation/tautomer", executable_names=["epik"], commercial=True, license_type="proprietary"),
    # linker / generation
    _tool("LinkInvent", "linker_generation", "generative_model", "Linker generation", executable_type="python_package", python_imports=["reinvent"], local_executable=False),
    _tool("REINVENT", "de_novo_generation", "generative_model", "Molecule generation/RL", executable_type="python_package", python_imports=["reinvent"], local_executable=False),
    _tool("DeLinker", "linker_generation", "generative_model", "Graph linker generation", executable_type="python_package", python_imports=["delinker"], local_executable=False),
    _tool("DiffLinker", "linker_generation", "diffusion_model", "Diffusion linker generation", executable_type="python_package", python_imports=["torch"], local_executable=False),
    _tool("SyntaLinker", "linker_generation", "seq2seq_model", "Transformer linker generation", executable_type="python_package", python_imports=["torch"], local_executable=False),
    _tool("CReM", "de_novo_generation", "fragment_replacement", "Chemically reasonable mutations", executable_type="python_package", python_imports=["crem"], local_executable=False),
    _tool("mmpdb", "fragmentation", "matched_pairs", "Matched molecular pairs", executable_names=["mmpdb"]),
    _tool("BRICS", "fragmentation", "rdkit_fragmentation", "BRICS fragmentation", executable_type="python_package", python_imports=["rdkit"], local_executable=False),
    _tool("RECAP", "fragmentation", "rdkit_fragmentation", "RECAP fragmentation", executable_type="python_package", python_imports=["rdkit"], local_executable=False),
    _tool("MolDQN", "de_novo_generation", "rl_generation", "RL molecular optimization", executable_type="python_package", python_imports=["tensorflow"], local_executable=False),
    _tool("GuacaMol", "de_novo_generation", "benchmarking", "Molecule generation benchmark", executable_type="python_package", python_imports=["guacamol"], local_executable=False),
    _tool("MOSES", "de_novo_generation", "benchmarking", "Generative model benchmark", executable_type="python_package", python_imports=["moses"], local_executable=False),
    # retrosynthesis / synthesis
    _tool(
        "AiZynthFinder", "retrosynthesis", "route_planning",
        "MCTS + neural-policy retrosynthetic tree search (AstraZeneca/MolecularAI)",
        executable_type="python_package", python_imports=["aizynthfinder"], local_executable=True,
        license_type="MIT", install_hint="pip install aizynthfinder; run scripts/bootstrap_assets.sh --aizynth",
        reliability_level="production",
        agent_use_case="Full retrosynthetic route search for PROTAC linkers/warheads (bounded MCTS)",
        expected_inputs=["SMILES"], expected_outputs=["route trees", "building blocks", "route count"],
        notes="Working adapter: protacxtend.tools.retrosynthesis_engines.run_aizynth_engine. "
              "Pretrained USPTO policy + ZINC stock under data/retrosynthesis/models/aizynth.",
    ),
    _tool(
        "ASKCOS", "retrosynthesis", "route_planning",
        "MIT open-source retrosynthesis suite (web portal + Docker deployment): one-step "
        "predictions, template enumeration, Retro* tree search, building-block prices",
        executable_type="api_or_docker", web_service=True, local_executable=True,
        license_type="MIT", install_hint="Public portal default; local Docker deployment via ASKCOS_API_URL",
        reliability_level="research",
        agent_use_case="One-step precursor prediction and full Retro* routes against vendor catalogs",
        expected_inputs=["SMILES"], expected_outputs=["precursor SMILES + scores", "route trees", "buyable prices"],
        notes="Working adapter: protacxtend.tools.retrosynthesis_engines.AskcosClient "
              "(verified live MIT API: retro/controller/call-sync, tree-search/retro-star, buyables/search).",
    ),
    _tool(
        "Molecular Transformer", "retrosynthesis", "seq2seq_model",
        "Sequence-to-sequence retrosynthesis (OpenNMT transformer neural translation)",
        executable_type="python_package", python_imports=["onmt"], local_executable=True,
        license_type="open-source", reliability_level="experimental",
        install_hint="pip install OpenNMT-py; drop a retrosynthesis checkpoint at "
                    "data/retrosynthesis/models/openmt/retro_model.pt (or export OPENMT_MODEL)",
        agent_use_case="Local SMILES->precursors transformer inference (custom in-house pipeline)",
        expected_inputs=["SMILES"], expected_outputs=["predicted precursor SMILES"],
        notes="Model weights research-use (Segler et al.); token grammar implemented in "
              "retrosynthesis_engines.tokenize_smiles (Molecular Transformer tokenizer).",
    ),
    _tool(
        "RDKit + OpenNMT workflow", "retrosynthesis", "seq2seq_pipeline",
        "Custom RDKit + transformer (OpenNMT) seq2seq retrosynthesis workflow",
        executable_type="python_pipeline", python_imports=["rdkit", "onmt"], local_executable=True,
        license_type="open-source", reliability_level="experimental",
        install_hint="RDKit bundled; add OpenNMT-py + checkpoint (see Molecular Transformer row)",
        agent_use_case="Fully local RDKit-preprocess -> OpenNMT translate -> RDKit-validate pipeline",
        expected_inputs=["SMILES"], expected_outputs=["validated precursor SMILES"],
        notes="Working adapter: protacxtend.tools.retrosynthesis_engines.run_openmt_engine; "
              "RDKit preprocess/validation always available, translation honest-gated on checkpoint.",
    ),
    _tool("IBM RXN", "reaction_prediction", "web_api", "Reaction prediction and retrosynthesis", executable_type="api", api_required=True, web_service=True, local_executable=False),
    _tool("RXNMapper", "reaction_prediction", "atom_mapping", "Atom mapping", executable_type="python_package", python_imports=["rxnmapper"], local_executable=False),
    _tool("RDChiral", "reaction_prediction", "reaction_engine", "Template reaction application", executable_type="python_package", python_imports=["rdchiral"], local_executable=False),
    _tool("RAscore", "synthetic_accessibility", "sa_scoring", "Retrosynthetic accessibility score", executable_type="python_package", python_imports=["rascore"], local_executable=False),
    _tool("SCScore", "synthetic_accessibility", "sa_scoring", "Synthetic complexity score", executable_type="python_package", python_imports=["scscore"], local_executable=False),
    _tool(
        "ASKCOS Tree Builder", "retrosynthesis", "route_planning",
        "ASKCOS Retro* route-tree generation",
        executable_type="api_or_docker", web_service=True, local_executable=True,
        license_type="MIT", reliability_level="research",
        install_hint="Local Docker deployment via ASKCOS_API_URL (public MIT portal otherwise)",
        agent_use_case="Full Retro* tree search (call-sync-without-token endpoint)",
        expected_inputs=["SMILES"], expected_outputs=["route trees", "purchasable terminals"],
        notes="Client: AskcosClient.tree_search (retrosynthesis_engines) — returns routes + "
              "terminal purchasability from the nodelink graph.",
    ),
    # ADME/Tox
    _tool("SwissADME", "admet_toxicity", "web_predictor", "ADME property prediction", executable_type="web", web_service=True, local_executable=False),
    _tool("ADMETlab 3.0", "admet_toxicity", "web_predictor", "ADMET prediction web platform", executable_type="web", web_service=True, local_executable=False),
    _tool("pkCSM", "admet_toxicity", "web_predictor", "ADMET prediction web platform", executable_type="web", web_service=True, local_executable=False),
    _tool("ProTox-II", "admet_toxicity", "web_predictor", "Toxicity prediction platform", executable_type="web", web_service=True, local_executable=False),
    _tool("DeepPurpose", "admet_toxicity", "python_model", "Drug-target and ADMET ML", executable_type="python_package", python_imports=["DeepPurpose"], local_executable=False),
    _tool("Therapeutics Data Commons", "admet_toxicity", "python_dataset", "ADMET datasets/tasks", executable_type="python_package", python_imports=["tdc"], local_executable=False),
    _tool("OpenADMET", "admet_toxicity", "api_or_local", "OpenADMET prediction backend", executable_type="api", api_required=True, web_service=True, local_executable=False),
    # PROTAC/degradation ML
    _tool("DeepPROTACs", "protac_degradation_prediction", "ml_model", "PROTAC degradation prediction", executable_type="python_package", python_imports=["torch"], local_executable=False),
    _tool("PROTAC-STAN", "protac_degradation_prediction", "ml_model", "PROTAC degradation prediction", executable_type="python_package", python_imports=["torch"], local_executable=False),
    _tool("DegradeMaster", "protac_degradation_prediction", "ml_model", "PROTAC degradation prediction", executable_type="python_package", python_imports=["torch"], local_executable=False),
    # molecular ML / foundation
    _tool("Chemprop", "molecular_ml", "gnn_model", "Property prediction", executable_type="python_package", python_imports=["chemprop"], local_executable=False),
    _tool("DeepChem", "molecular_ml", "ml_toolkit", "Molecular ML toolkit", executable_type="python_package", python_imports=["deepchem"], local_executable=False),
    _tool("GROVER", "molecular_ml", "foundation_model", "Graph transformer representation learning", executable_type="python_package", python_imports=["torch"], local_executable=False),
    _tool("ChemBERTa", "molecular_ml", "foundation_model", "SMILES transformer embeddings", executable_type="python_package", python_imports=["transformers"], local_executable=False),
    _tool("MolFormer", "molecular_ml", "foundation_model", "Molecular language model", executable_type="python_package", python_imports=["transformers"], local_executable=False),
    _tool("Uni-Mol", "molecular_ml", "3d_foundation_model", "3D molecular foundation model", executable_type="python_package", python_imports=["torch"], local_executable=False),
    # protein language models
    _tool("ESM-2", "protein_language_models", "protein_fm", "Protein language model embeddings", executable_type="python_package", python_imports=["esm", "transformers"], local_executable=False),
    _tool("ProtT5", "protein_language_models", "protein_fm", "Protein language model embeddings", executable_type="python_package", python_imports=["transformers"], local_executable=False),
    # literature / patents
    _tool("PubTator", "literature_mining", "ner_service", "Biomedical entity extraction", executable_type="web", web_service=True, local_executable=False),
    _tool("SciSpacy", "literature_mining", "nlp_package", "Scientific NER and parsing", executable_type="python_package", python_imports=["scispacy"], local_executable=False),
    _tool("ChemDataExtractor", "literature_mining", "nlp_package", "Chemical information extraction", executable_type="python_package", python_imports=["chemdataextractor"], local_executable=False),
    _tool("OPSIN", "literature_mining", "name_to_structure", "Chemical name to structure conversion", executable_type="web_or_jar", executable_names=["opsin"], web_service=True, local_executable=False),
    _tool("NameRxn", "literature_mining", "reaction_naming", "Commercial reaction classification", executable_names=["namerxn"], commercial=True, license_type="proprietary"),
    _tool("SureChEMBL", "patent_mining", "web_search", "Patent chemistry search", executable_type="web", web_service=True, local_executable=False),
    _tool("Lens.org", "patent_mining", "web_search", "Patent search and analytics", executable_type="web", web_service=True, local_executable=False),
    _tool("Google Patents", "patent_mining", "web_search", "Patent search", executable_type="web", web_service=True, local_executable=False),
    # wet-lab / omics
    _tool("AlphaLISA/TR-FRET assay planner", "assay_planning", "experimental_design", "Assay strategy planning", executable_type="metadata", local_executable=False, web_service=False, reliability_level="metadata_only"),
    _tool("Proteome Discoverer / MaxQuant", "proteomics", "omics_processing", "Proteomics data processing", executable_names=["ProteomeDiscoverer", "maxquant"], commercial=True, license_type="mixed"),
    _tool("Perseus", "proteomics", "omics_analysis", "Proteomics downstream analysis", executable_names=["Perseus"]),
    _tool("FragPipe", "proteomics", "omics_pipeline", "Proteomics workflow pipeline", executable_names=["fragpipe"]),
    _tool("CellProfiler", "image_analysis", "cell_image_quant", "Cell image analysis", executable_names=["cellprofiler"], python_imports=["cellprofiler"], executable_type="cli_or_python"),
    # workflow platforms
    _tool("KNIME", "workflow_platforms", "orchestration", "Workflow automation", executable_names=["knime"]),
    _tool("Pipeline Pilot", "workflow_platforms", "orchestration", "Commercial workflow platform", executable_names=["pipelinepilot"], commercial=True, license_type="proprietary"),
    _tool("Galaxy", "workflow_platforms", "orchestration", "Open workflow platform", executable_names=["galaxy", "run.sh"], web_service=True),
]


def get_toolkit_registry() -> list[dict[str, Any]]:
    return list(TOOLKIT_REGISTRY)


def get_tool_by_name(tool_name: str) -> dict[str, Any] | None:
    name = tool_name.strip().lower()
    for tool in TOOLKIT_REGISTRY:
        if tool["tool_name"].strip().lower() == name:
            return dict(tool)
    return None

