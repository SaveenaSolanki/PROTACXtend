from synglue_agent.databases.database_registry import get_database_registry
from synglue_agent.databases.database_status import check_all_database_statuses


def test_every_requested_database_registered():
    names = {d["name"] for d in get_database_registry()}
    required = {
        "MagnetDB / MGDB / MolGlueDB", "PROTAC-DB 3.0", "PROTACpedia", "TPDdb", "PROTAC-PatentDB", "PROTAC-8K",
        "ChEMBL", "BindingDB", "PubChem", "DrugBank", "IUPHAR/BPS Guide to Pharmacology",
        "RCSB PDB", "AlphaFold DB", "PDBbind", "Binding MOAD", "UniProt",
        "Open Targets", "DepMap", "Human Protein Atlas", "ProteomicsDB", "PRIDE", "CPTAC / Proteomic Data Commons",
        "STRING", "BioGRID", "IntAct", "Complex Portal", "E3Net", "UbiBrowser", "UbiNet", "PhosphoSitePlus",
        "ZINC", "Enamine REAL", "Enamine TPD libraries", "ChemDiv", "MolPort", "eMolecules",
        "SureChEMBL", "Lens.org", "PubMed", "Europe PMC", "Semantic Scholar", "OpenAlex",
        "ClinicalTrials.gov", "cBioPortal", "TCGA / GDC", "GTEx", "COSMIC", "OMIM", "DisGeNET",
    }
    missing = required - names
    assert not missing, f"Missing databases: {sorted(missing)}"


def test_database_schema_complete():
    required_fields = {
        "name", "category", "access_mode", "has_public_api", "has_bulk_download", "requires_api_key",
        "requires_license", "recommended_backend", "base_url", "api_doc_url", "local_file_expected",
        "environment_variables", "agent_use_case", "expected_inputs", "expected_outputs",
        "refresh_frequency", "status", "notes",
    }
    for row in get_database_registry():
        assert required_fields.issubset(row.keys()), row["name"]


def test_status_checker_never_crashes():
    statuses = check_all_database_statuses()
    assert isinstance(statuses, dict)
    assert len(statuses) > 0


def test_restricted_db_not_available_without_config():
    statuses = check_all_database_statuses()
    for name in ["DrugBank", "OMIM", "DisGeNET", "Lens.org", "MolPort", "eMolecules", "SureChEMBL", "COSMIC"]:
        status = statuses[name]["status"]
        assert status in {"restricted_api", "restricted_download", "registered_but_unavailable", "download_local"}

