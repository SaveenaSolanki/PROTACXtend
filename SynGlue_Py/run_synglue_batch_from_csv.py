#!/usr/bin/env python3

import os
import argparse
import traceback
import pandas as pd
from rdkit import Chem

from savi_module_4 import SynGlueSelector

# Try module_4 first (symlinked), fall back to savi_module_4
try:
    from module_4 import (
        visualize_exit_vectors,
        run_link_invent,
        run_ai_predictions,
        run_linker_classification,
        visualize_top_protacs,
        run_admet_ai,
        calculate_adme_properties,
    )
except ImportError:
    from savi_module_4 import (
        visualize_exit_vectors,
        run_link_invent,
        run_ai_predictions,
        run_linker_classification,
        visualize_top_protacs,
        run_admet_ai,
        calculate_adme_properties,
    )

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.environ.get("SYNGLUE_BASE_DIR", "/app" if os.path.exists("/app/data") else "/storage/savi/saveenas/Projects/SynGlue_Py")
DATA_DIR = os.environ.get("SYNGLUE_DATA_DIR", os.path.join(BASE_DIR, "data"))
MODEL_DIR = os.environ.get("SYNGLUE_MODEL_DIR", os.path.join(BASE_DIR, "models"))
OUTPUT_DIR = os.environ.get("SYNGLUE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
REPOS_DIR = os.environ.get("SYNGLUE_REPOS_DIR", os.path.join(BASE_DIR, "repos"))

CONFIG = {
    "e3_db_path": os.path.join(DATA_DIR, "e3_ligand.csv"),
    "fragments_db_path": os.path.join(DATA_DIR, "warhead_fragments.pkl"),

    "reinvent_dir": os.path.join(REPOS_DIR, "reinvent"),
    "reinvent_env": os.environ.get("SYNGLUE_REINVENT_ENV", "/opt/conda/envs/reinvent" if os.path.exists("/opt/conda/envs/reinvent") else "/home/saveenas/miniconda3/envs/reinvent.v3.2"),

    "output_dir": OUTPUT_DIR,

    "batch_size": 16,
    "n_steps": 100,

    "grover_dir": os.path.join(REPOS_DIR, "grover"),
    "grover_checkpoint": os.path.join(MODEL_DIR, "grover_fixed.pt"),

    "pt_model": os.path.join(MODEL_DIR, "multitask_transformer.pt"),
    "rf_dc50_model": os.path.join(MODEL_DIR, "rf_dc50.joblib"),
    "rf_dmax_model": os.path.join(MODEL_DIR, "rf_dmax.joblib"),

    "warhead_csv": os.path.join(DATA_DIR, "grover_warhead.csv"),
    "e3_csv": os.path.join(DATA_DIR, "grover_e3.csv"),

    "admet_env_python": os.environ.get("SYNGLUE_ADMET_ENV_PYTHON", "/opt/conda/envs/admet/bin/python" if os.path.exists("/opt/conda/envs/admet/bin/python") else "/home/saveenas/miniconda3/envs/admet/bin/python"),

    "linker_class_model": os.path.join(MODEL_DIR, "linker_classifier.pkl"),
}


# ============================================================
# Utility functions
# ============================================================

def check_path(path, label):
    if not os.path.exists(path):
        raise FileNotFoundError(f"[MISSING] {label}: {path}")


def check_required_paths(config):
    required_files = {
        "E3 database": config["e3_db_path"],
        "GROVER checkpoint": config["grover_checkpoint"],
        "PyTorch multitask model": config["pt_model"],
        "RF DC50 model": config["rf_dc50_model"],
        "RF DMax model": config["rf_dmax_model"],
        "Warhead GROVER CSV": config["warhead_csv"],
        "E3 GROVER CSV": config["e3_csv"],
        "Linker classifier": config["linker_class_model"],
        "ADMET python": config["admet_env_python"],
    }

    for label, path in required_files.items():
        check_path(path, label)

    check_path(config["grover_dir"], "GROVER directory")
    check_path(config["reinvent_dir"], "REINVENT directory")
    check_path(config["reinvent_env"], "REINVENT conda env")

    os.makedirs(config["output_dir"], exist_ok=True)


def canonicalize_smiles(smiles):
    if not isinstance(smiles, str):
        return None

    smiles = smiles.strip()
    if smiles == "":
        return None

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    return Chem.MolToSmiles(mol, canonical=True)


def select_e3_for_warhead(warhead_smiles, selector, e3_archetype):
    warhead_smiles = canonicalize_smiles(warhead_smiles)

    if warhead_smiles is None:
        raise ValueError("Invalid warhead SMILES")

    adme = calculate_adme_properties(warhead_smiles)

    potential_e3s = selector.score_e3s(e3_archetype)

    if not potential_e3s:
        raise RuntimeError(f"No valid E3 ligand found for archetype: {e3_archetype}")

    best_e3 = potential_e3s[0]
    tagged_e3_smiles = selector.generate_e3_exit_vector(best_e3["Smiles"])

    return {
        "warhead_smiles": warhead_smiles,
        "warhead_MW": adme["MW"],
        "warhead_logP": adme["logP"],
        "warhead_TPSA": adme["TPSA"],
        "warhead_flexibility": adme["Flexibility"],
        "warhead_synthesizability": adme["Synthesizability"],
        "e3_target": best_e3.get("Target", "Unknown"),
        "e3_smiles": best_e3.get("Smiles", None),
        "e3_tagged_smiles": tagged_e3_smiles,
        "e3_score": best_e3.get("D_E3_Score", None),
    }


def run_one_warhead(row, selector, config, args):
    original_smiles = row[args.smiles_col]
    canonical_smiles = canonicalize_smiles(original_smiles)

    if canonical_smiles is None:
        summary = {
            "input_smiles": original_smiles,
            "status": "failed",
            "error": "Invalid SMILES",
        }
        for col in row.index:
            summary[f"input_{col}"] = row[col]
        return None, summary

    name = row[args.name_col] if args.name_col and args.name_col in row else canonical_smiles[:20]
    safe_name = str(name).replace("/", "_").replace(" ", "_")

    run_dir = os.path.join(config["output_dir"], f"batch_{safe_name}")
    os.makedirs(run_dir, exist_ok=True)

    local_config = dict(config)
    local_config["output_dir"] = run_dir

    try:
        selection = select_e3_for_warhead(
            warhead_smiles=canonical_smiles,
            selector=selector,
            e3_archetype=args.e3_archetype,
        )

        warhead_smiles = selection["warhead_smiles"]
        e3_tagged_smiles = selection["e3_tagged_smiles"]

        print("\n======================================================")
        print(f"Running: {name}")
        print(f"Warhead: {warhead_smiles}")
        print(f"E3 tagged: {e3_tagged_smiles}")
        print("======================================================")

        if not args.skip_images:
            visualize_exit_vectors(warhead_smiles, e3_tagged_smiles, run_dir)

        pair_string = f"{warhead_smiles}|{e3_tagged_smiles}"

        generated_df, out_path = run_link_invent(pair_string, local_config)

        if generated_df is None or out_path is None:
            raise RuntimeError("Link-INVENT failed or produced no scaffold_memory.csv")

        predicted_df = run_ai_predictions(generated_df, out_path, local_config)

        classified_df = run_linker_classification(
            predicted_df,
            warhead_smiles,
            e3_tagged_smiles,
            out_path,
            local_config,
        )

        classified_df["input_name"] = name
        classified_df["input_warhead_smiles"] = warhead_smiles
        classified_df["selected_e3_target"] = selection["e3_target"]
        classified_df["selected_e3_smiles"] = selection["e3_smiles"]
        classified_df["selected_e3_tagged_smiles"] = e3_tagged_smiles
        classified_df["warhead_MW"] = selection["warhead_MW"]
        classified_df["warhead_logP"] = selection["warhead_logP"]
        classified_df["warhead_TPSA"] = selection["warhead_TPSA"]

        # Keep original input CSV columns in every output row
        for col in row.index:
            classified_df[f"input_{col}"] = row[col]

        if not args.skip_images:
            visualize_top_protacs(classified_df, out_path, top_n=args.top_n_draw)

        if not args.skip_admet:
            admet_df = run_admet_ai(classified_df, out_path, local_config, top_n=args.top_n_admet)
        else:
            admet_df = None

        final_one_path = os.path.join(out_path, "Final_Predicted_PROTACs_with_Linker_Class.csv")
        classified_df.to_csv(final_one_path, index=False)

        summary = {
            "input_name": name,
            "input_smiles": original_smiles,
            "canonical_smiles": warhead_smiles,
            "status": "success",
            "n_generated_or_scored": len(classified_df),
            "selected_e3_target": selection["e3_target"],
            "selected_e3_smiles": selection["e3_smiles"],
            "run_output_dir": out_path,
            "final_csv": final_one_path,
            "error": "",
        }

        for col in row.index:
            summary[f"input_{col}"] = row[col]

        if "Predicted_DC50_nM" in classified_df.columns:
            best = classified_df.sort_values(
                by=["Predicted_DC50_nM", "Predicted_DMax_%"],
                ascending=[True, False],
            ).iloc[0]

            summary["best_predicted_dc50_nM"] = best.get("Predicted_DC50_nM", None)
            summary["best_predicted_dmax_percent"] = best.get("Predicted_DMax_%", None)
            summary["best_protac_smiles"] = best.get("SMILES", None)
            summary["best_linker_smiles"] = best.get("Linker_SMILES", None)
            summary["best_linker_class"] = best.get("Predicted_Linker_Class", None)
            summary["best_linker_class_prob"] = best.get("Linker_Class_Prob", None)

        return classified_df, summary

    except Exception as e:
        error_log = traceback.format_exc()

        error_file = os.path.join(run_dir, "ERROR.log")
        with open(error_file, "w") as f:
            f.write(error_log)

        summary = {
            "input_name": name,
            "input_smiles": original_smiles,
            "canonical_smiles": canonical_smiles,
            "status": "failed",
            "n_generated_or_scored": 0,
            "selected_e3_target": "",
            "selected_e3_smiles": "",
            "run_output_dir": run_dir,
            "final_csv": "",
            "error": str(e),
        }

        for col in row.index:
            summary[f"input_{col}"] = row[col]

        print(f"\n[FAILED] {name}: {e}")
        print(f"Full error saved to: {error_file}")

        return None, summary


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Batch SynGlue PROTAC generation from a CSV of warhead/fragment SMILES."
    )

    parser.add_argument(
        "--input_csv",
        required=True,
        help="Input CSV containing warhead/fragment SMILES."
    )

    parser.add_argument(
        "--smiles_col",
        default="smiles",
        help="Column name containing SMILES. Default: smiles"
    )

    parser.add_argument(
        "--name_col",
        default=None,
        help="Optional column name for molecule/fragment names."
    )

    parser.add_argument(
        "--e3_archetype",
        default="A_Workhorse",
        choices=["A_Workhorse", "B_GreaseSink", "C_Covalent", "D_Planar"],
        help="E3 archetype to use. Default: A_Workhorse"
    )

    parser.add_argument(
        "--top_n_draw",
        type=int,
        default=3,
        help="Number of top PROTACs to draw per input. Default: 3"
    )

    parser.add_argument(
        "--top_n_admet",
        type=int,
        default=20,
        help="Number of top PROTACs for ADMET-AI per input. Default: 20"
    )

    parser.add_argument(
        "--max_rows",
        type=int,
        default=None,
        help="Optional limit for testing. Example: --max_rows 2"
    )

    parser.add_argument(
        "--skip_admet",
        action="store_true",
        help="Skip ADMET-AI profiling."
    )

    parser.add_argument(
        "--skip_images",
        action="store_true",
        help="Skip molecule image generation."
    )

    args = parser.parse_args()

    print("\nChecking required paths...")
    check_required_paths(CONFIG)

    print("\nLoading input CSV...")
    # Flexible reader: handles comma CSV, tab TSV, and files with whitespace around tabs
    try:
        df = pd.read_csv(args.input_csv, sep=None, engine="python")
    except Exception:
        df = pd.read_csv(args.input_csv, sep="\\t", engine="python")

    # Clean column names like "ID \tname \tsmiles \ttype "
    df.columns = [str(c).strip() for c in df.columns]

    # If the whole header was read as one column, split manually by tab
    if len(df.columns) == 1 and "\\t" in df.columns[0]:
        df = pd.read_csv(args.input_csv, sep="\\t", engine="python")
        df.columns = [str(c).strip() for c in df.columns]

    print("Detected columns:", df.columns.tolist())

    if args.smiles_col not in df.columns:
        raise KeyError(
            f"SMILES column '{args.smiles_col}' not found. "
            f"Available columns: {df.columns.tolist()}"
        )

    if args.max_rows is not None:
        df = df.head(args.max_rows).copy()

    print(f"Input rows: {len(df)}")

    print("\nLoading E3 database...")
    e3_df = pd.read_csv(CONFIG["e3_db_path"])
    selector = SynGlueSelector(e3_df)

    all_results = []
    summaries = []

    for idx, row in df.iterrows():
        print(f"\n\n########## Processing row {idx + 1}/{len(df)} ##########")

        result_df, summary = run_one_warhead(
            row=row,
            selector=selector,
            config=CONFIG,
            args=args,
        )

        summaries.append(summary)

        if result_df is not None and len(result_df) > 0:
            all_results.append(result_df)

        summary_path = os.path.join(CONFIG["output_dir"], "batch_summary_progress.csv")
        pd.DataFrame(summaries).to_csv(summary_path, index=False)

    summary_df = pd.DataFrame(summaries)

    summary_final_path = os.path.join(CONFIG["output_dir"], "batch_summary_final.csv")
    summary_df.to_csv(summary_final_path, index=False)

    print("\nSaved batch summary:")
    print(summary_final_path)

    if all_results:
        combined_df = pd.concat(all_results, ignore_index=True)

        combined_path = os.path.join(CONFIG["output_dir"], "batch_all_predicted_PROTACs.csv")
        combined_df.to_csv(combined_path, index=False)

        print("\nSaved combined final PROTAC CSV:")
        print(combined_path)

        if "Predicted_DC50_nM" in combined_df.columns:
            top_path = os.path.join(CONFIG["output_dir"], "batch_best_PROTAC_per_input.csv")

            top_df = (
                combined_df.sort_values(
                    by=["input_name", "Predicted_DC50_nM", "Predicted_DMax_%"],
                    ascending=[True, True, False],
                )
                .groupby("input_name", as_index=False)
                .head(1)
            )

            top_df.to_csv(top_path, index=False)

            print("\nSaved best PROTAC per input:")
            print(top_path)

    else:
        print("\nNo successful PROTAC results were produced.")


if __name__ == "__main__":
    main()