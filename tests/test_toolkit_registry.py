from synglue_agent.tools.toolkit_registry import get_toolkit_registry


def test_registry_contains_all_requested_tools():
    tools = {t["tool_name"] for t in get_toolkit_registry()}
    required = {
        "PyMOL", "UCSF ChimeraX", "UCSF Chimera", "VMD", "NGLView", "Mol*",
        "AutoDock Vina", "AutoDock-GPU", "AutoDock4", "Smina", "GNINA", "rDock", "DOCK6", "LeDock", "PLANTS", "GOLD", "Glide", "MOE Dock", "ICM-Pro",
        "PRosettaC", "RosettaDock", "RosettaLigand", "Rosetta InterfaceAnalyzer", "PyRosetta",
        "HADDOCK", "HADDOCK3", "ClusPro", "MEGADOCK", "ZDOCK", "PatchDock", "FireDock", "LightDock", "EquiDock", "AlphaFold-Multimer", "ColabFold",
        "GROMACS", "OpenMM", "AMBER / AmberTools", "NAMD", "CHARMM", "Desmond", "PLUMED",
        "gmx_MMPBSA", "MMPBSA.py",
        "Meeko", "MGLTools", "PDBFixer", "PropKa", "PDB2PQR", "OpenBabel",
        "RDKit ETKDG", "CREST", "xTB", "MOPAC", "ORCA", "Gaussian", "OpenEye OMEGA", "Schrodinger LigPrep", "Epik",
        "LinkInvent", "REINVENT", "DeLinker", "DiffLinker", "SyntaLinker", "CReM", "mmpdb", "BRICS", "RECAP", "MolDQN", "GuacaMol", "MOSES",
        "AiZynthFinder", "ASKCOS", "IBM RXN", "RXNMapper", "RDChiral", "RAscore", "SCScore", "ASKCOS Tree Builder",
        "SwissADME", "ADMETlab 3.0", "pkCSM", "ProTox-II", "DeepPurpose", "Therapeutics Data Commons", "OpenADMET",
        "DeepPROTACs", "PROTAC-STAN", "DegradeMaster",
        "Chemprop", "DeepChem", "GROVER", "ChemBERTa", "MolFormer", "Uni-Mol",
        "ESM-2", "ProtT5",
        "PubTator", "SciSpacy", "ChemDataExtractor", "OPSIN", "NameRxn", "SureChEMBL", "Lens.org", "Google Patents",
        "AlphaLISA/TR-FRET assay planner", "Proteome Discoverer / MaxQuant", "Perseus", "FragPipe", "CellProfiler",
        "KNIME", "Pipeline Pilot", "Galaxy",
    }
    missing = required - tools
    assert not missing, f"Missing tools in registry: {sorted(missing)}"


def test_registry_schema_complete():
    required_fields = {
        "tool_name", "category", "subcategory", "purpose", "executable_type", "install_hint",
        "executable_names", "python_imports", "api_required", "license_type", "commercial",
        "local_executable", "web_service", "agent_use_case", "expected_inputs", "expected_outputs",
        "status", "reliability_level", "notes",
    }
    for tool in get_toolkit_registry():
        assert required_fields.issubset(tool.keys()), f"Tool schema incomplete: {tool.get('tool_name')}"

