"""Local file manifest helpers for SynGlue database layer."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "synglue_agent" / "data"


LOCAL_FILE_HINTS = {
    "MagnetDB / MGDB / MolGlueDB": [
        DATA_DIR / "Lean_MagnetDB_Trie.pkl",
        DATA_DIR / "Clean_Metadata_Hash.pkl",
    ],
    "PROTAC-DB 3.0": [DATA_DIR / "protacdb_local.csv"],
    "PROTACpedia": [DATA_DIR / "protacpedia_local.csv"],
    "PROTAC-8K": [DATA_DIR / "known_protac_smiles.csv"],
    "PROTAC-PatentDB": [DATA_DIR / "protac_patentdb.csv"],
    "TPDdb": [DATA_DIR / "tpddb.csv"],
    "BindingDB": [DATA_DIR / "bindingdb.tsv"],
    "DrugBank": [DATA_DIR / "drugbank_local.csv"],
    "PDBbind": [DATA_DIR / "pdbbind_index.csv"],
    "Binding MOAD": [DATA_DIR / "binding_moad.csv"],
    "Human Protein Atlas": [DATA_DIR / "hpa_expression.tsv"],
    "ZINC": [DATA_DIR / "zinc_fragments.smi"],
    "Enamine REAL": [DATA_DIR / "enamine_real.smi"],
    "Enamine TPD libraries": [DATA_DIR / "enamine_tpd.smi"],
    "ChemDiv": [DATA_DIR / "chemdiv.sdf"],
    "PhosphoSitePlus": [DATA_DIR / "phosphositeplus.tsv"],
    "UbiNet": [DATA_DIR / "ubinet.tsv"],
    "E3Net": [DATA_DIR / "e3net.tsv"],
}


def expected_local_files(database_name: str) -> list[Path]:
    return LOCAL_FILE_HINTS.get(database_name, [])

