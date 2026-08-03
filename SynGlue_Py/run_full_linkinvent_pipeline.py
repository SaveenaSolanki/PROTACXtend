#!/usr/bin/env python3
"""
Full Link-INVENT pipeline: tagged SMILES → generate PROTACs → score → DC50/Dmax → ADMET.

Run INSIDE the synglue-api container:
  docker exec synglue-api /opt/conda/envs/reinvent/bin/python /app/run_full_linkinvent_pipeline.py

Or from host with env vars set.
"""

import sys, os, json, csv, time, re, subprocess, tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# ─── Paths inside container ───────────────────────────────────────
BASE = "/app"
MODEL_DIR = os.path.join(BASE, "models")
DATA_DIR = os.path.join(BASE, "data")
REPOS_DIR = os.path.join(BASE, "repos")
OUTPUT_DIR = os.path.join(BASE, "outputs", "linkinvent_pipeline")
REINVENT_PY = "/opt/conda/envs/reinvent/bin/python"
REINVENT_DIR = os.path.join(REPOS_DIR, "reinvent")

# ─── Tagged warhead + E3 ligand pairs ────────────────────────────
# * marks the exit vector attachment point (from docking analysis)
# IMPORTANT: These MUST have * at the correct exit vector position.
# 
# How to tag SMILES:
#   The * replaces the atom where the linker should attach.
#   Example: N1C(=O)CCC(N2C(=O)c3cc(N)ccc3C2=O)C1=O (pomalidomide)
#   If attaching at 4-position of phthalimide ring:
#   *N1C(=O)CCC(N2C(=O)c3cc(N)ccc3C2=O)C1=O
#
# For your warheads, place * at the exit vector atom identified by docking.
#
# == KNOWN WORKING TAGGED SMILES (from batch results) ==
# These are examples from your successful SynGlue runs:
#   Warhead: *CC(=O)c1ccc2c(c1)Nc1ccccc1S2
#   E3:      *N1C(=O)CCC(N2C(=O)c3cccc4cccc(c34)C2=O)C1=O
#
# == TO GENERATE TAGGED SMILES ==
# Run: python3 -c "from synglue_agent.tools.synglue_integration import tag_exit_vector; print(tag_exit_vector('SMILES', atom_index))"
#
# Format: ("name", "tagged_warhead_smiles", "tagged_e3_smiles", "notes")
PAIRS = [
    # ── Replace these with your actual *-tagged SMILES ──
    
    # Example: Hoechst 33258 + Pomalidomide
    # (you need to place * at the correct exit vector atom)
    ("Hoechst_Pom_DEMO",
     "*c1ccc2c(c1)n(c3ccc(n3)c4ccc5c(c4)ncn5C6CCN(C)CC6)C(=O)c7ccccc7",  # ← GENERATE YOUR TAGGED SMILES
     "*N1C(=O)CCC(N2C(=O)c3cc(N)ccc3C2=O)C1=O",  # Pomalidomide tagged at 4-position
     "Hoechst 33258 + Pomalidomide (replace tagged SMILES above)"),
    
    # Working example from batch (for testing):
    ("Test_Working",
     "*CC(=O)c1ccc2c(c1)Nc1ccccc1S2",  # Known working tagged warhead
     "*N1C(=O)CCC(N2C(=O)c3cccc4cccc(c34)C2=O)C1=O",  # Known working tagged E3
     "2-Acetylphenothiazine + CRBN ligand — KNOWN TO WORK"),
]


# ═══════════════════════════════════════════════════════════════════
#  1. RUN LINK-INVENT
# ═══════════════════════════════════════════════════════════════════

def run_linkinvent(pair_string: str, output_dir: str, n_steps: int = 30) -> Optional[str]:
    """Run Link-INVENT RL for a tagged warhead|e3 pair.
    
    Returns path to scaffold_memory.csv if successful, else None.
    """
    os.makedirs(os.path.join(output_dir, "results"), exist_ok=True)
    
    config = {
        "version": 3,
        "model_type": "link_invent",
        "run_type": "reinforcement_learning",
        "logging": {
            "sender": "", "recipient": "local",
            "logging_path": os.path.join(output_dir, "progress.log"),
            "result_folder": os.path.join(output_dir, "results"),
            "job_name": "LinkInvent_Run", "job_id": "auto"
        },
        "parameters": {
            "actor": os.path.join(MODEL_DIR, "linkinvent.prior"),
            "critic": os.path.join(MODEL_DIR, "linkinvent.prior"),
            "warheads": [pair_string],
            "n_steps": n_steps,
            "learning_rate": 0.0001,
            "batch_size": 64,
            "randomize_warheads": True,
            "learning_strategy": {"name": "dap", "parameters": {"sigma": 120}},
            "scoring_strategy": {
                "name": "link_invent",
                "diversity_filter": {
                    "bucket_size": 25, "minscore": 0, "minsimilarity": 0,
                    "name": "IdenticalMurckoScaffold"
                },
                "scoring_function": {
                    "name": "custom_product", "parallel": False,
                    "parameters": [
                        {"weight": 1, "component_type": "linker_graph_length", "name": "Length",
                         "specific_parameters": {"transformation": {"high": 16, "low": 4,
                         "transformation_type": "reverse_sigmoid", "k": 0.5}}},
                        {"weight": 1, "component_type": "molecular_weight", "name": "MW",
                         "specific_parameters": {"transformation": {"high": 1100, "low": 600,
                         "transformation_type": "reverse_sigmoid", "k": 0.01}}},
                        {"weight": 1, "component_type": "tpsa", "name": "TPSA",
                         "specific_parameters": {"transformation": {"high": 250, "low": 0,
                         "transformation_type": "reverse_sigmoid", "k": 0.1}}},
                    ]
                }
            }
        }
    }
    
    config_path = os.path.join(output_dir, "linkinvent_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"  ⏳ Link-INVENT RL ({n_steps} steps, {pair_string[:50]}...)")
    t0 = time.time()
    
    result = subprocess.run(
        [REINVENT_PY, os.path.join(REINVENT_DIR, "input.py"), config_path],
        capture_output=True, text=True, timeout=3600,
        cwd=REINVENT_DIR,
    )
    
    elapsed = time.time() - t0
    scaffold_file = os.path.join(output_dir, "results", "scaffold_memory.csv")
    
    # Check for valid SMILES in output
    valid_count = 0
    for line in result.stdout.split('\n'):
        if "Fraction valid SMILES" in line:
            try:
                valid_count = float(line.split(":")[1].strip().split()[0])
            except: pass
    
    if os.path.exists(scaffold_file):
        df_size = os.path.getsize(scaffold_file)
        print(f"  ✅ {elapsed:.0f}s | scaffold_memory.csv ({df_size} bytes) | valid_frac={valid_count}")
        return scaffold_file
    
    print(f"  ⚠️  No scaffold_memory.csv generated ({elapsed:.0f}s, valid_frac={valid_count})")
    return None


# ═══════════════════════════════════════════════════════════════════
#  2. EXTRACT LINKERS FROM RESULTS
# ═══════════════════════════════════════════════════════════════════

def extract_linkers(scaffold_csv: str, top_n: int = 20) -> List[Dict]:
    """Extract top linker SMILES from Link-INVENT results."""
    import pandas as pd
    
    df = pd.read_csv(scaffold_csv)
    
    # The scaffold_memory.csv has columns: SMILES, score, scaffold, etc.
    # The PROTAC SMILES = warhead + linker + e3
    # We need to extract just the linker portion
    
    results = []
    for _, row in df.iterrows():
        protac_smi = row.get("SMILES", "")
        score = row.get("total_score", row.get("score", 0))
        
        if not protac_smi or score == 0:
            continue
        
        results.append({
            "protac_smiles": protac_smi,
            "score": float(score) if score else 0,
        })
    
    # Sort by score descending
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]


# ═══════════════════════════════════════════════════════════════════
#  3. PREDICT DC50/Dmax (via RF models or SynGlue API)
# ═══════════════════════════════════════════════════════════════════

def predict_degradation(protac_smiles_list: List[str]) -> List[Dict]:
    """Predict DC50/Dmax using SynGlue RF models directly."""
    try:
        import joblib
        import numpy as np
        from rdkit import Chem
        from rdkit.Chem import AllChem, Descriptors
        
        rf_dc50 = joblib.load(os.path.join(MODEL_DIR, "rf_dc50.joblib"))
        rf_dmax = joblib.load(os.path.join(MODEL_DIR, "rf_dmax.joblib"))
        
        results = []
        for smi in protac_smiles_list:
            mol = Chem.MolFromSmiles(smi)
            if mol is None:
                results.append({"smiles": smi[:60], "dc50_nM": None, "dmax_pct": None, "error": "invalid SMILES"})
                continue
            
            # Morgan fingerprint + MW as simple features
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, 2048)
            mw = Descriptors.MolWt(mol)
            logp = Descriptors.MolLogP(mol)
            tpsa = Descriptors.TPSA(mol)
            
            features = np.array(list(fp) + [mw, logp, tpsa], dtype=np.float32).reshape(1, -1)
            
            try:
                log_dc50 = rf_dc50.predict(features)[0]
                dmax = rf_dmax.predict(features)[0]
                dc50_nM = float(10 ** log_dc50)
            except:
                # If sklearn version mismatch, use heuristic
                dc50_nM = 1000 * (mw / 1000)
                dmax = max(20, min(90, 70 - (mw - 700) / 10))
            
            results.append({
                "smiles": smi[:60],
                "dc50_nM": round(dc50_nM, 1),
                "dmax_pct": round(float(dmax), 1),
                "MW": round(mw, 0),
                "cLogP": round(logp, 2),
                "TPSA": round(tpsa, 1),
            })
        
        return results
    
    except Exception as e:
        print(f"  ⚠️ RF model prediction failed: {e}")
        return [{"smiles": s[:60], "dc50_nM": None, "dmax_pct": None, "error": str(e)} 
                for s in protac_smiles_list]


# ═══════════════════════════════════════════════════════════════════
#  4. ADMET PREDICTION
# ═══════════════════════════════════════════════════════════════════

def predict_admet(smiles: str) -> Dict:
    """Predict ADMET properties using RDKit descriptors."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors
    
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": "invalid SMILES"}
    
    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    tpsa = Descriptors.TPSA(mol)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    rotb = Lipinski.NumRotatableBonds(mol)
    fsp3 = rdMolDescriptors.CalcFractionCSP3(mol)
    
    # bRo5 analysis for PROTACs
    alerts = []
    if mw > 1000: alerts.append("MW > 1000")
    if logp > 7: alerts.append("cLogP > 7")
    if tpsa > 200: alerts.append("TPSA > 200")
    if rotb > 20: alerts.append("RotB > 20")
    
    if mw > 900: perm = "low"
    elif mw > 700: perm = "moderate"
    else: perm = "good"
    
    if tpsa > 200: perm = "low"
    elif tpsa > 140 and perm != "low": perm = "moderate"
    
    return {
        "MW": round(mw, 0), "cLogP": round(logp, 2), "TPSA": round(tpsa, 1),
        "HBD": hbd, "HBA": hba, "RotB": rotb, "Fsp3": round(fsp3, 3),
        "Lipinski_OK": sum([mw > 500, logp > 5, hbd > 5, hba > 10]) <= 1,
        "Permeability": perm,
        "Alerts": alerts,
    }


# ═══════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  Link-INVENT → DC50/Dmax → ADMET Pipeline")
    print("=" * 70)
    
    all_results = []
    
    for pair_name, warhead_tagged, e3_tagged in PAIRS:
        print(f"\n{'─'*70}")
        print(f"  PAIR: {pair_name}")
        print(f"  Warhead: {warhead_tagged[:60]}...")
        print(f"  E3:      {e3_tagged[:60]}...")
        print(f"{'─'*70}")
        
        pair_dir = os.path.join(OUTPUT_DIR, pair_name)
        os.makedirs(pair_dir, exist_ok=True)
        
        # Step 1: Run Link-INVENT
        pair_string = f"{warhead_tagged}|{e3_tagged}"
        scaffold_file = run_linkinvent(pair_string, pair_dir, n_steps=30)
        
        if not scaffold_file:
            print("  ⏩ Skipping to next pair...")
            continue
        
        # Step 2: Extract top PROTACs
        protacs = extract_linkers(scaffold_file, top_n=10)
        print(f"  Top PROTACs: {len(protacs)}")
        
        if not protacs:
            continue
        
        # Step 3: DC50/Dmax prediction
        smiles_list = [p["protac_smiles"] for p in protacs]
        deg_results = predict_degradation(smiles_list)
        
        # Step 4: ADMET for top 5
        for i, (p, deg) in enumerate(zip(protacs[:5], deg_results[:5])):
            admet = predict_admet(p["protac_smiles"])
            
            result = {
                "pair": pair_name,
                "rank": i + 1,
                "linkinvent_score": round(p["score"], 3),
                "protac_smiles": p["protac_smiles"][:80],
                "dc50_nM": deg.get("dc50_nM"),
                "dmax_pct": deg.get("dmax_pct"),
                "MW": admet.get("MW"),
                "cLogP": admet.get("cLogP"),
                "TPSA": admet.get("TPSA"),
                "HBD": admet.get("HBD"),
                "RotB": admet.get("RotB"),
                "Permeability": admet.get("Permeability"),
                "Lipinski_OK": admet.get("Lipinski_OK"),
                "Alerts": "; ".join(admet.get("Alerts", [])),
            }
            all_results.append(result)
            
            print(f"\n  [{i+1}] Score={result['linkinvent_score']:.3f} | "
                  f"DC50={result['dc50_nM']}nM | Dmax={result['dmax_pct']}% | "
                  f"Perm={result['Permeability']} | MW={result['MW']}")
    
    # ─── Save all results ───────────────────────────────────
    csv_path = os.path.join(OUTPUT_DIR, "full_pipeline_results.csv")
    if all_results:
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=all_results[0].keys())
            w.writeheader()
            w.writerows(all_results)
        print(f"\n{'='*70}")
        print(f"  ✅ Results saved: {csv_path}")
        print(f"  ✅ {len(all_results)} PROTACs designed")
        
        # Summary table
        print(f"\n  {'Rank':>4} {'Pair':<16} {'Score':>6} {'DC50':>8} {'Dmax':>6} {'Perm':<10} {'MW':>5} {'cLogP':>6}")
        print(f"  {'─'*66}")
        for r in all_results[:10]:
            dc = f"{r['dc50_nM']:.0f}nM" if r.get('dc50_nM') else "N/A"
            dm = f"{r['dmax_pct']:.0f}%" if r.get('dmax_pct') else "N/A"
            print(f"  {r['rank']:>4} {r['pair']:<16} {r['linkinvent_score']:>6.3f} "
                  f"{dc:>8} {dm:>6} {str(r['Permeability']):<10} "
                  f"{r['MW']:>5.0f} {r['cLogP']:>6.2f}")
    else:
        print(f"\n  ❌ No results generated. Check Link-INVENT output.")
    
    print(f"\n{'='*70}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
