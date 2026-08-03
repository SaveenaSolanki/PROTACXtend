import os
import pickle
import pandas as pd
from tqdm import tqdm

DATA_DIR = "/storage/savi/saveenas/Projects/SynGlue_Py/data"

OLD_HASH = f"{DATA_DIR}/Clean_Metadata_Hash.pkl"
TARGET_MAP = f"{DATA_DIR}/Direct_Binders_Target_Map.pkl"

OUT_HASH = f"{DATA_DIR}/Clean_Metadata_Hash_PATCHED_FROM_TARGET_MAP.pkl"
OUT_QC = f"{DATA_DIR}/Clean_Metadata_Hash_PATCHED_FROM_TARGET_MAP_QC.csv.gz"


def clean(x):
    if x is None:
        return ""
    x = str(x).strip()
    if x.lower() in ["", "nan", "none", "null", "unknown"]:
        return ""
    return x


print("Loading old Clean_Metadata_Hash.pkl...")
with open(OLD_HASH, "rb") as f:
    old_hash = pickle.load(f)

print("Loading clean Direct_Binders_Target_Map.pkl...")
target_map = pd.read_pickle(TARGET_MAP)

print("Target map shape:", target_map.shape)
print("Target map columns:", target_map.columns.tolist())

tm = target_map.copy()

tm["has_gene"] = tm["Gene_Name"].apply(lambda x: clean(x) != "")
tm["has_uniprot"] = tm["UniProt_ID"].apply(lambda x: clean(x) != "")
tm["is_resolved"] = tm["Resolution_Status"].astype(str).str.upper().eq("RESOLVED")

tm = tm.sort_values(
    ["Target_ID", "is_resolved", "has_gene", "has_uniprot"],
    ascending=[True, False, False, False],
)

tm = tm.drop_duplicates("Target_ID", keep="first").copy()

target_lookup = tm.set_index("Target_ID").to_dict(orient="index")

print("Unique target lookup size:", len(target_lookup))

patched = {}

for db_id, meta in tqdm(old_hash.items(), desc="Patching hash from clean target map"):
    meta = dict(meta)

    target_id = clean(
        meta.get("Target_ID")
        or meta.get("Target ID")
        or meta.get("Target")
        or db_id
    )

    meta["Database_ID"] = db_id
    meta["Target_ID"] = target_id if target_id else "Unknown"

    hit = target_lookup.get(target_id)

    if hit is not None:
        meta["Target_Name"] = (
            clean(hit.get("Target_Clean_Name"))
            or clean(hit.get("Target_Full_Name"))
            or clean(meta.get("Target_Name"))
            or "Unknown"
        )
        meta["Gene_Name"] = clean(hit.get("Gene_Name")) or "Unknown"
        meta["UniProt_ID"] = clean(hit.get("UniProt_ID")) or "Unknown"
        meta["Organism"] = clean(hit.get("Organism")) or clean(meta.get("Organism")) or "Unknown"
        meta["Resolution_Source"] = clean(hit.get("Resolution_Source")) or "Direct_Binders_Target_Map"
        meta["Resolution_Status"] = clean(hit.get("Resolution_Status")) or "Unknown"
        meta["Needs_Manual_Curation"] = bool(hit.get("Needs_Manual_Curation", False))
    else:
        meta["Target_Name"] = clean(meta.get("Target_Name")) or clean(meta.get("Target")) or "Unknown"
        meta["Gene_Name"] = clean(meta.get("Gene_Name")) or "Unknown"
        meta["UniProt_ID"] = clean(meta.get("UniProt_ID")) or "Unknown"
        meta["Organism"] = clean(meta.get("Organism")) or "Unknown"
        meta["Resolution_Source"] = "NOT_FOUND_IN_DIRECT_BINDERS_TARGET_MAP"
        meta["Resolution_Status"] = "UNRESOLVED"
        meta["Needs_Manual_Curation"] = True

    patched[db_id] = meta

print("Saving patched hash...")
with open(OUT_HASH, "wb") as f:
    pickle.dump(patched, f, protocol=pickle.HIGHEST_PROTOCOL)

qc = pd.DataFrame([
    {
        "Database_ID": db_id,
        "Target_ID": meta.get("Target_ID"),
        "Target_Name": meta.get("Target_Name"),
        "Gene_Name": meta.get("Gene_Name"),
        "UniProt_ID": meta.get("UniProt_ID"),
        "Organism": meta.get("Organism"),
        "Resolution_Source": meta.get("Resolution_Source"),
        "Resolution_Status": meta.get("Resolution_Status"),
        "Needs_Manual_Curation": meta.get("Needs_Manual_Curation"),
    }
    for db_id, meta in patched.items()
])

qc.to_csv(OUT_QC, index=False, compression="gzip")

print("\nDone.")
print("Patched hash:", OUT_HASH)
print("QC file:", OUT_QC)

print("\nQC:")
print("Total metadata records:", len(qc))
print("Gene unknown:", qc["Gene_Name"].astype(str).str.lower().isin(["", "nan", "unknown"]).sum())
print("UniProt unknown:", qc["UniProt_ID"].astype(str).str.lower().isin(["", "nan", "unknown"]).sum())
print("Target name unknown:", qc["Target_Name"].astype(str).str.lower().isin(["", "nan", "unknown"]).sum())

print("\nResolution status:")
print(qc["Resolution_Status"].value_counts(dropna=False).head(20))

print("\nSample:")
print(qc.head(20).to_string(index=False))