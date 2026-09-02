"""Central registry for SynGlue knowledge databases."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ALLOWED_ACCESS_MODES = {
    "api_live",
    "download_local",
    "api_and_download",
    "restricted_api",
    "restricted_download",
    "web_only",
    "manual_curation",
    "disabled",
}


@dataclass
class DatabaseEntry:
    name: str
    category: str
    access_mode: str
    has_public_api: bool
    has_bulk_download: bool
    requires_api_key: bool
    requires_license: bool
    recommended_backend: str
    base_url: str
    api_doc_url: str
    local_file_expected: list[str]
    environment_variables: list[str]
    agent_use_case: str
    expected_inputs: list[str]
    expected_outputs: list[str]
    refresh_frequency: str
    status: str
    notes: str


def _db(
    name: str,
    category: str,
    access_mode: str,
    has_public_api: bool,
    has_bulk_download: bool,
    requires_api_key: bool,
    requires_license: bool,
    recommended_backend: str,
    base_url: str,
    api_doc_url: str,
    local_file_expected: list[str] | None = None,
    environment_variables: list[str] | None = None,
    agent_use_case: str = "",
    expected_inputs: list[str] | None = None,
    expected_outputs: list[str] | None = None,
    refresh_frequency: str = "monthly",
    status: str = "registered_but_unavailable",
    notes: str = "",
) -> dict[str, Any]:
    if access_mode not in ALLOWED_ACCESS_MODES:
        raise ValueError(f"Invalid access_mode: {access_mode}")
    entry = DatabaseEntry(
        name=name,
        category=category,
        access_mode=access_mode,
        has_public_api=has_public_api,
        has_bulk_download=has_bulk_download,
        requires_api_key=requires_api_key,
        requires_license=requires_license,
        recommended_backend=recommended_backend,
        base_url=base_url,
        api_doc_url=api_doc_url,
        local_file_expected=local_file_expected or [],
        environment_variables=environment_variables or [],
        agent_use_case=agent_use_case or category,
        expected_inputs=expected_inputs or ["query"],
        expected_outputs=expected_outputs or ["records"],
        refresh_frequency=refresh_frequency,
        status=status,
        notes=notes,
    )
    return asdict(entry)


DATABASE_REGISTRY: list[dict[str, Any]] = [
    # PROTAC / glue
    _db("MagnetDB / MGDB / MolGlueDB", "protac_glue", "download_local", False, True, False, False, "local_file", "", "", notes="Local curated/source-specific export expected."),
    _db(
        "PROTAC-DB 3.0",
        "protac_glue",
        "download_local",
        False,
        True,
        False,
        False,
        "local_file",
        "http://cadd.zju.edu.cn/protacdb/",
        "",
        local_file_expected=["data/benchmark/PROTAC-DB_3.0_protacs.xlsx"],
        agent_use_case="PROTAC degradation, binary/ternary affinity, cellular activity, permeability, PK, physicochemical, warhead, and E3 ligand evidence",
        expected_inputs=["target", "e3_ligase", "compound_id", "smiles", "evidence_family"],
        expected_outputs=[
            "DC50",
            "Dmax",
            "percent_degradation",
            "target_binding_affinity",
            "e3_binding_affinity",
            "ternary_complex_affinity",
            "cellular_activity",
            "PAMPA",
            "Caco-2",
            "pharmacokinetic_parameters",
            "physicochemical_properties",
            "warhead_bioactivity",
            "e3_ligand_bioactivity",
        ],
        notes="Public web database; local workbook parser normalizes rich evidence families when the XLSX is present.",
    ),
    _db("PROTACpedia", "protac_glue", "download_local", False, True, False, False, "local_file", "https://protacpedia.com/", "", notes="Bulk/local copy preferred."),
    _db("TPDdb", "protac_glue", "download_local", False, True, False, False, "local_file", "https://db.idrblab.net/ttd/", "", notes="Dataset/source integration varies."),
    _db("PROTAC-PatentDB", "protac_glue", "download_local", False, True, False, False, "local_file", "", "", notes="Local index expected."),
    _db("PROTAC-8K", "protac_glue", "download_local", False, True, False, False, "local_file", "", "", notes="Local curated dataset."),
    # Compound / bioactivity
    _db("ChEMBL", "compound_bioactivity", "api_and_download", True, True, False, False, "api", "https://www.ebi.ac.uk/chembl/", "https://www.ebi.ac.uk/chembl/api/data/docs"),
    _db("BindingDB", "compound_bioactivity", "api_and_download", True, True, False, False, "api", "https://www.bindingdb.org/", "https://www.bindingdb.org/rwd/bind/index.jsp"),
    _db("PubChem", "compound_bioactivity", "api_and_download", True, True, False, False, "api", "https://pubchem.ncbi.nlm.nih.gov/", "https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest"),
    _db("DrugBank", "compound_bioactivity", "restricted_download", False, True, False, True, "local_file", "https://go.drugbank.com/", "https://dev.drugbank.com/", environment_variables=["DRUGBANK_API_KEY"], notes="License-restricted content."),
    _db("IUPHAR/BPS Guide to Pharmacology", "compound_bioactivity", "api_live", True, False, False, False, "api", "https://www.guidetopharmacology.org/", "https://www.guidetopharmacology.org/webServices.jsp"),
    # Structure
    _db("RCSB PDB", "structure", "api_and_download", True, True, False, False, "api", "https://www.rcsb.org/", "https://search.rcsb.org/"),
    _db("AlphaFold DB", "structure", "api_live", True, True, False, False, "api", "https://alphafold.ebi.ac.uk/", "https://alphafold.ebi.ac.uk/api-docs"),
    _db("PDBbind", "structure", "download_local", False, True, False, False, "local_file", "http://www.pdbbind.org.cn/", "", notes="Bulk dataset distribution."),
    _db("Binding MOAD", "structure", "download_local", False, True, False, False, "local_file", "https://www.bindingmoad.org/", "", notes="Bulk/local files."),
    _db("UniProt", "structure", "api_and_download", True, True, False, False, "api", "https://www.uniprot.org/", "https://rest.uniprot.org/"),
    # Biology / omics
    _db("Open Targets", "target_biology", "api_live", True, True, False, False, "api", "https://platform.opentargets.org/", "https://api.platform.opentargets.org/api/v4/graphql"),
    _db("DepMap", "target_biology", "download_local", False, True, False, False, "local_file", "https://depmap.org/portal/", "", notes="Public portal; bulk downloads."),
    _db("Human Protein Atlas", "target_biology", "download_local", False, True, False, False, "local_file", "https://www.proteinatlas.org/", "", notes="Bulk files preferred."),
    _db("ProteomicsDB", "target_biology", "api_live", True, True, False, False, "api", "https://www.proteomicsdb.org/", "https://www.proteomicsdb.org/proteomicsdb/#api"),
    _db("PRIDE", "target_biology", "api_live", True, True, False, False, "api", "https://www.ebi.ac.uk/pride/", "https://www.ebi.ac.uk/pride/ws/archive/"),
    _db("CPTAC / Proteomic Data Commons", "target_biology", "api_live", True, True, False, False, "api", "https://proteomic.datacommons.cancer.gov/pdc/", "https://pdc.cancer.gov/pdc/beta/swagger-ui.html"),
    # PPI / E3
    _db("STRING", "ppi_e3", "api_live", True, True, False, False, "api", "https://string-db.org/", "https://string-db.org/help/api/"),
    _db("BioGRID", "ppi_e3", "api_live", True, True, False, False, "api", "https://thebiogrid.org/", "https://wiki.thebiogrid.org/doku.php/biogridrest"),
    _db("IntAct", "ppi_e3", "api_live", True, True, False, False, "api", "https://www.ebi.ac.uk/intact/", "https://www.ebi.ac.uk/intact/ws/"),
    _db("Complex Portal", "ppi_e3", "api_live", True, True, False, False, "api", "https://www.ebi.ac.uk/complexportal/", "https://www.ebi.ac.uk/complexportal/api/"),
    _db("E3Net", "ppi_e3", "download_local", False, True, False, False, "local_file", "", "", notes="Typically integrated as local network table."),
    _db("UbiBrowser", "ppi_e3", "api_live", True, False, False, False, "api", "http://ubibrowser.ncpsb.org/", ""),
    _db("UbiNet", "ppi_e3", "download_local", False, True, False, False, "local_file", "", "", notes="Local table/network expected."),
    _db("PhosphoSitePlus", "ppi_e3", "download_local", False, True, False, False, "local_file", "https://www.phosphosite.org/", "", notes="Bulk file download mode."),
    # Vendors
    _db("ZINC", "vendor_libraries", "download_local", False, True, False, False, "local_file", "https://zinc20.docking.org/", "", notes="Library downloads."),
    _db("Enamine REAL", "vendor_libraries", "download_local", False, True, False, False, "local_file", "https://enamine.net/", "", notes="Catalog/local files."),
    _db("Enamine TPD libraries", "vendor_libraries", "download_local", False, True, False, False, "local_file", "https://enamine.net/", ""),
    _db("ChemDiv", "vendor_libraries", "download_local", False, True, False, False, "local_file", "https://www.chemdiv.com/", "", notes="Catalog/local data."),
    _db("MolPort", "vendor_libraries", "restricted_api", True, False, True, False, "api", "https://www.molport.com/", "", environment_variables=["MOLPORT_API_KEY"]),
    _db("eMolecules", "vendor_libraries", "restricted_api", True, False, True, False, "api", "https://www.emolecules.com/", "", environment_variables=["EMOLECULES_API_KEY"]),
    # Literature / patent
    _db("SureChEMBL", "literature_patent", "restricted_api", True, True, True, False, "api", "https://www.surechembl.org/", "", environment_variables=["SURECHEMBL_API_KEY"]),
    _db("Lens.org", "literature_patent", "restricted_api", True, False, True, False, "api", "https://www.lens.org/", "", environment_variables=["LENS_API_KEY"]),
    _db("PubMed", "literature_patent", "api_live", True, True, False, False, "api", "https://pubmed.ncbi.nlm.nih.gov/", "https://www.ncbi.nlm.nih.gov/books/NBK25501/"),
    _db("Europe PMC", "literature_patent", "api_live", True, True, False, False, "api", "https://europepmc.org/", "https://europepmc.org/RestfulWebService"),
    _db("Semantic Scholar", "literature_patent", "restricted_api", True, False, True, False, "api", "https://www.semanticscholar.org/", "https://api.semanticscholar.org/api-docs/graph", environment_variables=["SEMANTIC_SCHOLAR_API_KEY"]),
    _db("OpenAlex", "literature_patent", "api_live", True, True, False, False, "api", "https://openalex.org/", "https://docs.openalex.org/"),
    # Clinical / disease / genomics
    _db("ClinicalTrials.gov", "clinical_genomics", "api_live", True, True, False, False, "api", "https://clinicaltrials.gov/", "https://clinicaltrials.gov/data-api/api"),
    _db("cBioPortal", "clinical_genomics", "api_live", True, True, False, False, "api", "https://www.cbioportal.org/", "https://www.cbioportal.org/api/swagger-ui/index.html"),
    _db("TCGA / GDC", "clinical_genomics", "api_live", True, True, False, False, "api", "https://portal.gdc.cancer.gov/", "https://api.gdc.cancer.gov/"),
    _db("GTEx", "clinical_genomics", "api_live", True, True, False, False, "api", "https://gtexportal.org/", "https://gtexportal.org/api/v2/redoc"),
    _db("COSMIC", "clinical_genomics", "restricted_download", False, True, False, True, "local_file", "https://cancer.sanger.ac.uk/cosmic", "", environment_variables=["COSMIC_USERNAME", "COSMIC_PASSWORD"]),
    _db("OMIM", "clinical_genomics", "restricted_api", True, False, True, True, "api", "https://www.omim.org/", "https://api.omim.org/", environment_variables=["OMIM_API_KEY"]),
    _db("DisGeNET", "clinical_genomics", "restricted_api", True, True, True, False, "api", "https://www.disgenet.org/", "https://www.disgenet.org/api/", environment_variables=["DISGENET_API_KEY"]),
]


def get_database_registry() -> list[dict[str, Any]]:
    return list(DATABASE_REGISTRY)


def get_database_entry(name: str) -> dict[str, Any] | None:
    q = name.strip().lower()
    for row in DATABASE_REGISTRY:
        if row["name"].strip().lower() == q:
            return dict(row)
    return None
