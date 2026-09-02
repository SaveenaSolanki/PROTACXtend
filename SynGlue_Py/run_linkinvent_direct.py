#!/usr/bin/env python3
"""
Standalone Link-INVENT runner — bypasses fragment database matching.
Runs INSIDE the synglue-api Docker container using the Magnet env.
"""

import sys, os, json, tempfile
from pathlib import Path

BASE_DIR = "/app"
sys.path.insert(0, BASE_DIR)

# Add all needed paths
for p in [BASE_DIR, os.path.join(BASE_DIR, "repos"), os.path.join(BASE_DIR, "repos", "reinvent"),
          os.path.join(BASE_DIR, "repos", "grover")]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ['PYTHONPATH'] = ':'.join(sys.path)

from savi_module_4 import run_link_invent

# === CONFIG ===
MODEL_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")
REPOS_DIR = os.path.join(BASE_DIR, "repos")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

def main():
    # Default: Hoechst 33258 + Pomalidomide
    warhead_smi = "CCN1CCN(CC1)C2=CC3=C(C=C2)C(=NN3)C4=CC5=C(C=C4)N=C(N5)C6=CC(=C(C=C6)O)OC"
    e3_smi = "NC1=CC=CC2=C1C(=O)N(C1CCC(=O)NC1=O)C2=O"
    out_dir = os.path.join(OUTPUT_DIR, "linkinvent_hoechst_pom")
    
    if len(sys.argv) > 1:
        warhead_smi = sys.argv[1]
    if len(sys.argv) > 2:
        e3_smi = sys.argv[2]
    if len(sys.argv) > 3:
        out_dir = sys.argv[3]
    
    os.makedirs(out_dir, exist_ok=True)
    
    config = {
        "reinvent_env": "/opt/conda/envs/reinvent",
        "reinvent_dir": os.path.join(REPOS_DIR, "reinvent"),
        "output_dir": out_dir,
        "batch_size": 32,
        "n_steps": 150,
        "grover_dir": os.path.join(REPOS_DIR, "grover"),
        "grover_checkpoint": os.path.join(MODEL_DIR, "grover_fixed.pt"),
        "pt_model": os.path.join(MODEL_DIR, "multitask_transformer.pt"),
        "rf_dc50_model": os.path.join(MODEL_DIR, "rf_dc50.joblib"),
        "rf_dmax_model": os.path.join(MODEL_DIR, "rf_dmax.joblib"),
        "warhead_csv": os.path.join(DATA_DIR, "grover_warhead.csv"),
        "e3_csv": os.path.join(DATA_DIR, "grover_e3.csv"),
        "admet_env_python": "/opt/conda/envs/admet/bin/python",
        "linker_class_model": os.path.join(MODEL_DIR, "linker_classifier.pkl"),
        "linkinvent_prior": os.path.join(MODEL_DIR, "linkinvent.prior"),
    }
    
    pair_string = f"{warhead_smi}|{e3_smi}"
    print(f"[Link-INVENT] Processing: {pair_string[:70]}...")
    
    generated_df, out_path = run_link_invent(pair_string, config, job_id="direct")
    
    if generated_df is None or generated_df.empty:
        print("[FAILED] No molecules generated.")
        return 1
    
    csv_path = os.path.join(out_dir, "generated_linkers.csv")
    generated_df.to_csv(csv_path, index=False)
    print(f"[SUCCESS] {len(generated_df)} PROTACs → {csv_path}")
    
    # Extract unique linkers
    if "Linker_SMILES" in generated_df.columns:
        linkers = generated_df["Linker_SMILES"].dropna().unique()
        linkers_path = os.path.join(out_dir, "linker_smiles_only.csv")
        with open(linkers_path, 'w') as f:
            f.write("smiles\n")
            for smi in linkers:
                f.write(f"{smi}\n")
        print(f"[INFO] {len(linkers)} unique linkers → {linkers_path}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
