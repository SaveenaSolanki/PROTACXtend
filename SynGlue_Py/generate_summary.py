#!/usr/bin/env python3

import os
import re
import gc
import pickle
import argparse
import pandas as pd
from tqdm import tqdm


# -----------------------------
# Regex patterns
# -----------------------------

UNIPROT_RE = re.compile(r"\b[A-NR-Z][0-9][A-Z0-9]{3}[0-9]\b|\b[A-Z0-9]{6,10}\b")

PATTERN_GENE_UNIPROT_PARENTHESES = re.compile(
    r"\(Gene:\s*([^,\)]+),\s*UniProt:\s*([A-Za-z0-9_\-]+)\)",
    flags=re.IGNORECASE,
)

PATTERN_GENE_ONLY = re.compile(
    r"\(Gene:\s*([^,\)]+)\)",
    flags=re.IGNORECASE,
)

# Example rough pattern:
# "Target name: GENE: , P12345, TYPE, ID"
PATTERN_COLON_SUFFIX = re.compile(
    r":\s*([A-Za-z0-9_\-]+)\s*:\s*,\s*([A-Za-z0-9_\-]+)",
    flags=re.IGNORECASE,
)


def clean_text(x):
    if x is None or pd.isna(x):
        return ""
    return str(x).strip()


def normalize_name(x):
    x = clean_text(x)
    x = re.sub(r"\(Gene:.*?\)", "", x, flags=re.IGNORECASE)
    x = re.sub(r"\s+", " ", x)
    x = x.strip(" :;,")
    return x


def parse_gene_uniprot_from_text(text):
    """
    Returns:
        gene, uniprot, source
    """
    text = clean_text(text)

    # Stage 1: (Gene: ABC, UniProt: P12345)
    m = PATTERN_GENE_UNIPROT_PARENTHESES.search(text)
    if m:
        return clean_text(m.group(1)), clean_text(m.group(2)), "REGEX_GENE_UNIPROT_PARENTHESES"

    # Stage 2: colon-delimited suffix
    m = PATTERN_COLON_SUFFIX.search(text)
    if m:
        return clean_text(m.group(1)), clean_text(m.group(2)), "REGEX_COLON_SUFFIX"

    # Stage 3: (Gene: ABC)
    m = PATTERN_GENE_ONLY.search(text)
    if m:
        return clean_text(m.group(1)), "", "REGEX_GENE_ONLY"

    return "", "", "NO_REGEX_MATCH"


def load_targets_csv(targets_csv):
    """
    Loads Targets_for_magnetdb.csv and builds lookup dictionaries.
    Expected columns based on current SynGlue code:
        New IDs
        Target Names
        Gene Name
        UniProt ID
    """
    df = pd.read_csv(targets_csv)

    required = ["New IDs", "Target Names", "Gene Name", "UniProt ID"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Targets CSV missing columns: {missing}")

    df = df.copy()
    df["Target_ID_key"] = df["New IDs"].astype(str).str.strip()
    df["Target_Name_key"] = df["Target Names"].astype(str).map(normalize_name).str.lower()

    by_id = {}
    by_name = {}

    for _, row in df.iterrows():
        record = {
            "Target_ID": clean_text(row.get("New IDs")),
            "Target_Full_Name": clean_text(row.get("Target Names")),
            "Target_Clean_Name": normalize_name(row.get("Target Names")),
            "Gene_Name": clean_text(row.get("Gene Name")),
            "UniProt_ID": clean_text(row.get("UniProt ID")),
            "Resolution_Source": "TARGETS_CSV",
        }

        if record["Target_ID"]:
            by_id[record["Target_ID"]] = record

        name_key = record["Target_Clean_Name"].lower()
        if name_key:
            by_name[name_key] = record

    return df, by_id, by_name


def extract_rows_from_direct_binders(obj):
    """
    Converts Direct_Binders_Dictionary_Enriched.pkl into row dictionaries.

    This function is intentionally defensive because the exact pickle schema
    may vary. It handles common dictionary-of-records structures.

    You should inspect 2-3 entries first and adjust field names if needed.
    """
    rows = []

    if not isinstance(obj, dict):
        raise TypeError(f"Expected pickle to be dict-like, got: {type(obj)}")

    for ligand_key, value in tqdm(obj.items(), desc="Extracting direct binders"):
        # Case 1: value is a list of target/binder records
        if isinstance(value, list):
            records = value

        # Case 2: value is a dict with records under a known key
        elif isinstance(value, dict):
            if "Targets" in value and isinstance(value["Targets"], list):
                records = value["Targets"]
            elif "Binders" in value and isinstance(value["Binders"], list):
                records = value["Binders"]
            elif "Direct_Binders" in value and isinstance(value["Direct_Binders"], list):
                records = value["Direct_Binders"]
            else:
                records = [value]
        else:
            continue

        for rec in records:
            if not isinstance(rec, dict):
                continue

            # Flexible field extraction
            ligand_chembl = (
                rec.get("Ligand_ChEMBL_ID")
                or rec.get("ChEMBL_ID")
                or rec.get("Molecule_ChEMBL_ID")
                or ligand_key
            )

            target_id = (
                rec.get("Target_ID")
                or rec.get("Target ID")
                or rec.get("New IDs")
                or rec.get("target_id")
                or ""
            )

            target_name = (
                rec.get("Target_Full_Name")
                or rec.get("Target_Name")
                or rec.get("Target Names")
                or rec.get("Target")
                or rec.get("target_name")
                or ""
            )

            row = {
                "Ligand_ChEMBL_ID": clean_text(ligand_chembl),
                "Target_ID": clean_text(target_id),
                "Target_Full_Name": clean_text(target_name),
                "Ligand_Name": clean_text(rec.get("Ligand_Name") or rec.get("Molecule_Name") or rec.get("Name")),
                "SMILES": clean_text(rec.get("SMILES") or rec.get("SMILE") or rec.get("Original_SMILES")),
                "Organism": clean_text(rec.get("Organism") or rec.get("Target_Organism")),
                "Assay_ID": clean_text(rec.get("Assay_ID") or rec.get("Assay ChEMBL ID")),
                "Assay_Description": clean_text(rec.get("Assay_Description") or rec.get("Description")),
                "Target_Atom_Count": rec.get("Target_Atom_Count", None),
            }

            rows.append(row)

    return pd.DataFrame(rows)


def resolve_targets(summary_df, targets_by_id, targets_by_name):
    resolved_rows = []

    unique_targets = (
        summary_df[
            ["Target_ID", "Target_Full_Name", "Organism", "Ligand_ChEMBL_ID", "SMILES", "Assay_ID"]
        ]
        .drop_duplicates()
        .copy()
    )

    for _, row in tqdm(unique_targets.iterrows(), total=len(unique_targets), desc="Resolving targets"):
        target_id = clean_text(row["Target_ID"])
        full_name = clean_text(row["Target_Full_Name"])
        clean_name = normalize_name(full_name)
        name_key = clean_name.lower()

        gene = ""
        uniprot = ""
        source = ""
        status = "UNRESOLVED"

        # Stage 1: curated CSV by Target_ID
        if target_id and target_id in targets_by_id:
            hit = targets_by_id[target_id]
            gene = hit["Gene_Name"]
            uniprot = hit["UniProt_ID"]
            clean_name = hit["Target_Clean_Name"] or clean_name
            full_name = hit["Target_Full_Name"] or full_name
            source = "CSV_BY_TARGET_ID"
            status = "RESOLVED"

        # Stage 2: curated CSV by clean name
        elif name_key and name_key in targets_by_name:
            hit = targets_by_name[name_key]
            gene = hit["Gene_Name"]
            uniprot = hit["UniProt_ID"]
            clean_name = hit["Target_Clean_Name"] or clean_name
            source = "CSV_BY_TARGET_NAME"
            status = "RESOLVED"

        # Stage 3: regex fallback
        else:
            gene_r, uniprot_r, regex_source = parse_gene_uniprot_from_text(full_name)
            gene = gene_r
            uniprot = uniprot_r
            source = regex_source
            if gene or uniprot:
                status = "PARTIALLY_RESOLVED" if not (gene and uniprot) else "RESOLVED"

        resolved_rows.append(
            {
                "Target_ID": target_id,
                "Target_Full_Name": full_name,
                "Target_Clean_Name": clean_name,
                "Gene_Name": gene,
                "UniProt_ID": uniprot,
                "Organism": clean_text(row["Organism"]),
                "Resolution_Source": source,
                "Resolution_Status": status,
                "Needs_Manual_Curation": status != "RESOLVED",
                "Example_Ligand_ChEMBL_ID": clean_text(row["Ligand_ChEMBL_ID"]),
                "Example_SMILES": clean_text(row["SMILES"]),
                "Example_Assay_ID": clean_text(row["Assay_ID"]),
            }
        )

    target_map = pd.DataFrame(resolved_rows)

    # Collapse to one row per Target_ID / Target_Clean_Name
    target_map["Target_Key"] = target_map["Target_ID"]
    target_map.loc[target_map["Target_Key"].eq(""), "Target_Key"] = target_map["Target_Clean_Name"]

    target_map = (
        target_map.sort_values(
            ["Resolution_Status", "Resolution_Source"],
            ascending=[True, True]
        )
        .drop_duplicates("Target_Key")
        .drop(columns=["Target_Key"])
        .reset_index(drop=True)
    )

    return target_map


def attach_resolved_metadata(summary_df, target_map):
    target_map_small = target_map[
        [
            "Target_ID",
            "Target_Clean_Name",
            "Gene_Name",
            "UniProt_ID",
            "Resolution_Source",
            "Resolution_Status",
            "Needs_Manual_Curation",
        ]
    ].copy()

    # Prefer Target_ID merge
    merged = summary_df.merge(
        target_map_small,
        on="Target_ID",
        how="left",
        suffixes=("", "_resolved"),
    )

    # Fill clean target name
    merged["Target_Clean_Name"] = merged["Target_Clean_Name"].fillna(
        merged["Target_Full_Name"].map(normalize_name)
    )

    return merged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--direct_binders_pkl",
        default="/storage/savi/saveenas/Projects/SynGlue_Py/data/Direct_Binders_Dictionary_Enriched.pkl",
    )
    parser.add_argument(
        "--targets_csv",
        default="/storage/savi/saveenas/Projects/SynGlue_Py/data/Targets_for_magnetdb.csv",
    )
    parser.add_argument(
        "--out_dir",
        default="/storage/savi/saveenas/Projects/SynGlue_Py/data",
    )
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    out_summary_pkl = os.path.join(args.out_dir, "Direct_Binders_Clean_Summary.pkl")
    out_summary_csv = os.path.join(args.out_dir, "Direct_Binders_Clean_Summary.csv.gz")

    out_target_pkl = os.path.join(args.out_dir, "Direct_Binders_Target_Map.pkl")
    out_target_csv = os.path.join(args.out_dir, "Direct_Binders_Target_Map.csv.gz")

    print("Loading Targets_for_magnetdb.csv...")
    targets_df, targets_by_id, targets_by_name = load_targets_csv(args.targets_csv)
    print(f"Loaded {len(targets_df):,} target metadata rows from CSV")

    print("Loading Direct_Binders_Dictionary_Enriched.pkl...")
    with open(args.direct_binders_pkl, "rb") as f:
        direct_binders = pickle.load(f)

    print("Extracting ligand-target rows...")
    summary_df = extract_rows_from_direct_binders(direct_binders)

    print(f"Extracted {len(summary_df):,} ligand-target rows")
    print("Columns:", list(summary_df.columns))

    # Reduce memory
    del direct_binders
    gc.collect()

    print("Resolving target-level gene and UniProt metadata...")
    target_map = resolve_targets(summary_df, targets_by_id, targets_by_name)

    # Add counts
    counts = (
        summary_df.groupby("Target_ID")
        .agg(
            N_Ligands=("Ligand_ChEMBL_ID", "nunique"),
            N_Assays=("Assay_ID", "nunique"),
        )
        .reset_index()
    )

    target_map = target_map.merge(counts, on="Target_ID", how="left")

    print("Attaching resolved target metadata to full ligand-target summary...")
    summary_df = attach_resolved_metadata(summary_df, target_map)

    # Compact dtypes
    for col in summary_df.select_dtypes(include="object").columns:
        summary_df[col] = summary_df[col].astype("string")

    for col in target_map.select_dtypes(include="object").columns:
        target_map[col] = target_map[col].astype("string")

    print("Saving target map...")
    target_map.to_pickle(out_target_pkl)
    target_map.to_csv(out_target_csv, index=False, compression="gzip")

    print("Saving full ligand-target summary...")
    summary_df.to_pickle(out_summary_pkl)
    summary_df.to_csv(out_summary_csv, index=False, compression="gzip")

    print("\nDone.")
    print(f"Full summary PKL: {out_summary_pkl}")
    print(f"Full summary CSV: {out_summary_csv}")
    print(f"Target map PKL:    {out_target_pkl}")
    print(f"Target map CSV:    {out_target_csv}")

    print("\nValidation summary:")
    print(f"Total ligand-target records: {len(summary_df):,}")
    print(f"Unique targets: {len(target_map):,}")
    print("Target resolution status:")
    print(target_map["Resolution_Status"].value_counts(dropna=False))
    print("\nGene missing count:", target_map["Gene_Name"].isna().sum() + target_map["Gene_Name"].eq("").sum())
    print("UniProt missing count:", target_map["UniProt_ID"].isna().sum() + target_map["UniProt_ID"].eq("").sum())

    print("\nSample target map:")
    print(target_map.head(10).to_string(index=False))


if __name__ == "__main__":
    main()