#!/usr/bin/env python3

import os
import argparse
import pandas as pd
from rdkit import Chem

# ============================================================
# Import your original SynGlue functions/classes
# ============================================================
# IMPORTANT:
# Save your original pasted code as:
#     synglue_master.py
#
# Then this runner imports from it.
# ============================================================

from synglue_master import (
    SynGlueSelector,
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
# Change paths only if needed
# ============================================================

CONFIG = {
    "e3_db_path": "/storage/savi/saveenas/Projects/SynGlue_Py/data/e3_ligand.csv",
    "fragments_db_path": "/storage/savi/saveenas/Projects/SynGlue_Py/data/warhead_fragments.pkl",

    "reinvent_dir": "/storage/savi/saveenas/Projects/SynGlue_Py/repos/reinvent",
    "reinvent_env": "/home/saveenas/miniconda3/envs/reinvent.v3.2",

    "output_dir": "/storage/savi/saveenas/Projects/SynGlue_Py/outputs",

    "batch_size": 16,
    "n_steps": 100,

    "grover_dir": "/storage/savi/saveenas/Projects/SynGlue_Py/repos/grover",
    "grover_checkpoint": "/storage/savi/saveenas/Projects/SynGlue_Py/models/grover_fixed.pt",

    "pt_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/multitask_transformer.pt",
    "rf_dc50_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/rf_dc50.joblib",
    "rf_dmax_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/rf_dmax.joblib",

    "warhead_csv": "/storage/savi/saveenas/Projects/SynGlue_Py/data/grover_warhead.csv",
    "e3_csv": "/storage/savi/saveenas/Projects/SynGlue_Py/data/grover_e3.csv",

    "admet_env_python": "/home/saveenas/miniconda3/envs/admet/bin/python",

    "linker_class_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/linker_classifier.pkl",
}


# ============================================================
# Helper checks
# ============================================================

def check_file(path, name):
    if not os.path.exists(path):
        raise FileNotFoundError(f"[MISSING] {name}: {path}")


def validate_smiles(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles}")
    return Chem.MolToSmiles(mol)


def check_required_paths(config):
    required = {
        "E3 database": config["e3_db_path"],
        "Fragment database": config["fragments_db_path"],
        "GROVER checkpoint": config["grover_checkpoint"],
        "PyTorch multitask model": config["pt_model"],
        "RF DC50 model": config["rf_dc50_model"],
        "RF DMax model": config["rf_dmax_model"],
        "Warhead GROVER CSV": config["warhead_csv"],
        "E3 GROVER CSV": config["e3_csv"],
        "Linker classifier": config["linker_class_model"],
        "ADMET python": config["admet_env_python"],
    }

    for name, path in required.items():
        check_file(path, name)

    if not os.path.isdir(config["grover_dir"]):
        raise FileNotFoundError(f"[MISSING] GROVER directory: {config['grover_dir']}")

    if not os.path.isdir(config["reinvent_dir"]):
        raise FileNotFoundError(f"[MISSING] REINVENT directory: {config['reinvent_dir']}")

    if not os.path.isdir(config["reinvent_env"]):
        raise FileNotFoundError(f"[MISSING] REINVENT conda env: {config['reinvent_env']}")

    os.makedirs(config["output_dir"], exist_ok=True)


# ============================================================
# Mode 1: use target name to select warhead from fragment DB
# ============================================================

def get_warhead_from_target(target_name, threshold, selector, fragments_df):
    target_name = target_name.upper().strip()

    if "Protein" not in fragments_df.columns:
        raise KeyError("fragments_df must contain column: Protein")

    if "percentage" not in fragments_df.columns:
        raise KeyError("fragments_df must contain column: percentage")

    if "fragment" not in fragments_df.columns:
        raise KeyError("fragments_df must contain column: fragment")

    subset = fragments_df[
        (fragments_df["Protein"].astype(str).str.upper() == target_name)
        & (fragments_df["percentage"] >= threshold)
    ].copy()

    print(f"\nTarget: {target_name}")
    print(f"Threshold: >= {threshold}%")
    print(f"Fragments found: {len(subset)}")

    if subset.empty:
        raise ValueError(
            f"No fragments found for {target_name} above {threshold}%. "
            "Try lowering threshold or check target name spelling."
        )

    payload = selector.run_selection(target_name, subset)

    if "Error" in payload:
        raise RuntimeError(payload["Error"])

    return payload["Warhead_SMILES"], payload["E3_Tagged_SMILES"]


# ============================================================
# Mode 2: use direct warhead/fragment SMILES
# ============================================================

def get_warhead_from_smiles(warhead_smiles, selector, e3_archetype):
    warhead_smiles = validate_smiles(warhead_smiles)

    adme = calculate_adme_properties(warhead_smiles)

    print("\nUsing direct warhead / fragment SMILES")
    print(f"Canonical warhead SMILES: {warhead_smiles}")
    print(f"MW: {adme['MW']} | logP: {adme['logP']} | TPSA: {adme['TPSA']}")
    print(f"Flexibility: {adme['Flexibility']} | {adme['Synthesizability']}")

    potential_e3s = selector.score_e3s(e3_archetype)

    if not potential_e3s:
        raise RuntimeError(f"No valid E3 ligands found for archetype: {e3_archetype}")

    best_e3 = potential_e3s[0]
    tagged_e3_smiles = selector.generate_e3_exit_vector(best_e3["Smiles"])

    print("\nSelected E3 ligand")
    print(f"Target: {best_e3.get('Target', 'Unknown')}")
    print(f"SMILES: {best_e3.get('Smiles')}")
    print(f"Tagged E3 SMILES: {tagged_e3_smiles}")
    print(f"E3 score: {best_e3.get('D_E3_Score', 'NA')}")

    return warhead_smiles, tagged_e3_smiles


# ============================================================
# Main full pipeline
# ============================================================

def run_full_pipeline(warhead_smiles, e3_tagged_smiles, config, top_n_draw=3, top_n_admet=20):
    print("\n======================================================")
    print("Running full SynGlue PROTAC generation pipeline")
    print("======================================================")

    print("\nSelected pair:")
    print(f"Warhead: {warhead_smiles}")
    print(f"E3 tagged: {e3_tagged_smiles}")

    visualize_exit_vectors(
        warhead_smiles,
        e3_tagged_smiles,
        config["output_dir"]
    )

    pair_string = f"{warhead_smiles}|{e3_tagged_smiles}"

    generated_df, out_path = run_link_invent(pair_string, config)

    if generated_df is None or out_path is None:
        raise RuntimeError("Link-INVENT failed or produced no scaffold_memory.csv")

    print(f"\nGenerated candidates: {generated_df.shape}")
    print(f"Run output directory: {out_path}")

    predicted_df = run_ai_predictions(
        generated_df,
        out_path,
        config
    )

    classified_df = run_linker_classification(
        predicted_df,
        warhead_smiles,
        e3_tagged_smiles,
        out_path,
        config
    )

    visualize_top_protacs(
        classified_df,
        out_path,
        top_n=top_n_draw
    )

    admet_df = run_admet_ai(
        classified_df,
        out_path,
        config,
        top_n=top_n_admet
    )

    final_csv = os.path.join(out_path, "Final_Predicted_PROTACs_with_Linker_Class.csv")
    classified_df.to_csv(final_csv, index=False)

    print("\n======================================================")
    print("Pipeline complete")
    print("======================================================")
    print(f"Final predicted PROTAC file: {final_csv}")

    if admet_df is not None:
        admet_csv = os.path.join(out_path, f"ADMET_Predictions_Top_{top_n_admet}.csv")
        print(f"ADMET file: {admet_csv}")

    return classified_df, admet_df


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run SynGlue PROTAC generation from target name or direct warhead SMILES."
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)

    mode_group.add_argument(
        "--target",
        type=str,
        help="Target protein name, e.g. BRD4, EGFR, NOXO1"
    )

    mode_group.add_argument(
        "--warhead_smiles",
        type=str,
        help="Direct warhead / fragment SMILES"
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=75.0,
        help="Fragment percentage threshold for target mode. Default: 75"
    )

    parser.add_argument(
        "--e3_archetype",
        type=str,
        default="A_Workhorse",
        choices=["A_Workhorse", "B_GreaseSink", "C_Covalent", "D_Planar"],
        help="E3 archetype to use when direct warhead SMILES is provided. Default: A_Workhorse"
    )

    parser.add_argument(
        "--top_n_draw",
        type=int,
        default=3,
        help="Number of top PROTACs to draw. Default: 3"
    )

    parser.add_argument(
        "--top_n_admet",
        type=int,
        default=20,
        help="Number of top PROTACs for ADMET-AI. Default: 20"
    )

    args = parser.parse_args()

    print("\nChecking required paths...")
    check_required_paths(CONFIG)

    print("\nLoading E3 and fragment databases...")
    e3_df = pd.read_csv(CONFIG["e3_db_path"])
    fragments_df = pd.read_pickle(CONFIG["fragments_db_path"])

    selector = SynGlueSelector(e3_df)

    if args.target:
        warhead_smiles, e3_tagged_smiles = get_warhead_from_target(
            target_name=args.target,
            threshold=args.threshold,
            selector=selector,
            fragments_df=fragments_df
        )

    else:
        warhead_smiles, e3_tagged_smiles = get_warhead_from_smiles(
            warhead_smiles=args.warhead_smiles,
            selector=selector,
            e3_archetype=args.e3_archetype
        )

    run_full_pipeline(
        warhead_smiles=warhead_smiles,
        e3_tagged_smiles=e3_tagged_smiles,
        config=CONFIG,
        top_n_draw=args.top_n_draw,
        top_n_admet=args.top_n_admet
    )


if __name__ == "__main__":
    main()