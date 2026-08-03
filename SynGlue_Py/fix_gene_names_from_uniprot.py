import re
import time
import pickle
import requests
import pandas as pd
from tqdm import tqdm

DATA_DIR = "/storage/savi/saveenas/Projects/SynGlue_Py/data"

IN_HASH = f"{DATA_DIR}/Clean_Metadata_Hash_PATCHED_FROM_TARGET_MAP.pkl"
OUT_HASH = f"{DATA_DIR}/Clean_Metadata_Hash_FINAL_GENE_FIXED.pkl"

IN_QC = f"{DATA_DIR}/Clean_Metadata_Hash_PATCHED_FROM_TARGET_MAP_QC.csv.gz"
OUT_QC = f"{DATA_DIR}/Clean_Metadata_Hash_FINAL_GENE_FIXED_QC.csv.gz"
OUT_UNIPROT_MAP = f"{DATA_DIR}/UniProt_to_GeneSymbol_Map.csv.gz"


def clean(x):
    if x is None:
        return ""
    x = str(x).strip()
    if x.lower() in ["", "nan", "none", "null", "unknown"]:
        return ""
    return x


def looks_like_chembl_id(x):
    x = clean(x)
    return bool(re.fullmatch(r"CHEMBL\d+", x, flags=re.IGNORECASE))


def looks_like_uniprot_id(x):
    x = clean(x)
    if not x:
        return False

    # Covers common UniProt accessions like P05453, Q8IUX4, A0A...
    return bool(
        re.fullmatch(r"[OPQ][0-9][A-Z0-9]{3}[0-9]", x)
        or re.fullmatch(r"[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9]", x)
        or re.fullmatch(r"A0A[A-Z0-9]+", x)
    )


def query_uniprot_gene(uniprot_id, sleep_sec=0.05):
    """
    Query UniProt REST API for primary gene symbol.
    Returns dict with Gene_Symbol, Protein_Name, Organism.
    """
    uniprot_id = clean(uniprot_id)

    if not looks_like_uniprot_id(uniprot_id):
        return {
            "UniProt_ID": uniprot_id,
            "Gene_Symbol": "",
            "Protein_Name_UniProt": "",
            "Organism_UniProt": "",
            "UniProt_Query_Status": "INVALID_UNIPROT_ID",
        }

    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"

    try:
        r = requests.get(url, timeout=20)
        time.sleep(sleep_sec)

        if r.status_code != 200:
            return {
                "UniProt_ID": uniprot_id,
                "Gene_Symbol": "",
                "Protein_Name_UniProt": "",
                "Organism_UniProt": "",
                "UniProt_Query_Status": f"HTTP_{r.status_code}",
            }

        js = r.json()

        # Gene symbol
        gene_symbol = ""
        genes = js.get("genes", [])
        if genes:
            gene_name = genes[0].get("geneName", {})
            gene_symbol = clean(gene_name.get("value"))

        # Protein name
        protein_name = ""
        protein_desc = js.get("proteinDescription", {})
        rec_name = protein_desc.get("recommendedName", {})
        full_name = rec_name.get("fullName", {})
        protein_name = clean(full_name.get("value"))

        # Organism
        organism = ""
        org = js.get("organism", {})
        organism = clean(org.get("scientificName"))

        return {
            "UniProt_ID": uniprot_id,
            "Gene_Symbol": gene_symbol,
            "Protein_Name_UniProt": protein_name,
            "Organism_UniProt": organism,
            "UniProt_Query_Status": "OK" if gene_symbol else "NO_GENE_SYMBOL",
        }

    except Exception as e:
        return {
            "UniProt_ID": uniprot_id,
            "Gene_Symbol": "",
            "Protein_Name_UniProt": "",
            "Organism_UniProt": "",
            "UniProt_Query_Status": f"ERROR_{type(e).__name__}",
        }


print("Loading patched hash...")
with open(IN_HASH, "rb") as f:
    metadata_hash = pickle.load(f)

print("Loading QC table...")
qc = pd.read_csv(IN_QC)

print("QC shape:", qc.shape)

# Only query unique valid UniProt IDs
unique_uniprots = sorted({
    clean(x)
    for x in qc["UniProt_ID"].dropna().unique()
    if looks_like_uniprot_id(x)
})

print("Unique valid UniProt IDs:", len(unique_uniprots))

# Query UniProt
records = []
for uid in tqdm(unique_uniprots, desc="Querying UniProt for gene symbols"):
    records.append(query_uniprot_gene(uid))

uniprot_map = pd.DataFrame(records)
uniprot_map.to_csv(OUT_UNIPROT_MAP, index=False, compression="gzip")

print("UniProt map saved:", OUT_UNIPROT_MAP)
print(uniprot_map["UniProt_Query_Status"].value_counts(dropna=False))

uid_to_gene = (
    uniprot_map
    .dropna(subset=["UniProt_ID"])
    .set_index("UniProt_ID")["Gene_Symbol"]
    .to_dict()
)

uid_to_protein = (
    uniprot_map
    .dropna(subset=["UniProt_ID"])
    .set_index("UniProt_ID")["Protein_Name_UniProt"]
    .to_dict()
)

uid_to_org = (
    uniprot_map
    .dropna(subset=["UniProt_ID"])
    .set_index("UniProt_ID")["Organism_UniProt"]
    .to_dict()
)

print("Fixing gene names in metadata hash...")

fixed_hash = {}

for db_id, meta in tqdm(metadata_hash.items(), desc="Fixing Gene_Name"):
    meta = dict(meta)

    old_gene = clean(meta.get("Gene_Name"))
    uniprot = clean(meta.get("UniProt_ID"))

    real_gene = clean(uid_to_gene.get(uniprot))
    protein_name = clean(uid_to_protein.get(uniprot))
    uniprot_org = clean(uid_to_org.get(uniprot))

    # Replace only if old gene is blank/Unknown/CHEMBL ID and UniProt gives a real gene symbol
    if real_gene and (not old_gene or looks_like_chembl_id(old_gene)):
        meta["Original_Gene_Name_Field"] = old_gene
        meta["Gene_Name"] = real_gene
        meta["Gene_Name_Source"] = "UniProt_ID"
    else:
        meta["Original_Gene_Name_Field"] = old_gene
        meta["Gene_Name"] = old_gene if old_gene else "Unknown"
        meta["Gene_Name_Source"] = meta.get("Resolution_Source", "Existing")

    if protein_name:
        meta["Protein_Name_UniProt"] = protein_name

    if uniprot_org:
        meta["Organism_UniProt"] = uniprot_org

    fixed_hash[db_id] = meta

print("Saving final fixed hash...")
with open(OUT_HASH, "wb") as f:
    pickle.dump(fixed_hash, f, protocol=pickle.HIGHEST_PROTOCOL)

final_qc = pd.DataFrame([
    {
        "Database_ID": db_id,
        "Target_ID": meta.get("Target_ID"),
        "Target_Name": meta.get("Target_Name"),
        "Original_Gene_Name_Field": meta.get("Original_Gene_Name_Field"),
        "Gene_Name": meta.get("Gene_Name"),
        "Gene_Name_Source": meta.get("Gene_Name_Source"),
        "UniProt_ID": meta.get("UniProt_ID"),
        "Protein_Name_UniProt": meta.get("Protein_Name_UniProt"),
        "Organism": meta.get("Organism"),
        "Organism_UniProt": meta.get("Organism_UniProt"),
        "Resolution_Source": meta.get("Resolution_Source"),
        "Resolution_Status": meta.get("Resolution_Status"),
    }
    for db_id, meta in fixed_hash.items()
])

final_qc.to_csv(OUT_QC, index=False, compression="gzip")

print("\nDone.")
print("Final fixed hash:", OUT_HASH)
print("Final QC:", OUT_QC)

print("\nQC:")
print("Total records:", len(final_qc))
print("Gene unknown:", final_qc["Gene_Name"].astype(str).str.lower().isin(["", "nan", "unknown"]).sum())
print("Gene still CHEMBL-like:", final_qc["Gene_Name"].astype(str).str.match(r"^CHEMBL\d+$", na=False).sum())
print("UniProt unknown:", final_qc["UniProt_ID"].astype(str).str.lower().isin(["", "nan", "unknown"]).sum())
print("Target name unknown:", final_qc["Target_Name"].astype(str).str.lower().isin(["", "nan", "unknown"]).sum())

print("\nGene name source:")
print(final_qc["Gene_Name_Source"].value_counts(dropna=False).head(20))

print("\nSample:")
print(
    final_qc[
        [
            "Database_ID",
            "Target_ID",
            "Target_Name",
            "Original_Gene_Name_Field",
            "Gene_Name",
            "Gene_Name_Source",
            "UniProt_ID",
            "Protein_Name_UniProt",
            "Organism",
        ]
    ].head(30).to_string(index=False)
)