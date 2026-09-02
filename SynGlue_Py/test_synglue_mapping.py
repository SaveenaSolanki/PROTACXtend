import os
import pandas as pd
import multiprocess_synglue as synglue

# --- CONFIGURATION ---
DB_DIR = "/storage/savi/saveenas/Projects/SynGlue_Py/data"
OUT_DIR = "/storage/savi/saveenas/Projects/SynGlue_Py/outputs/Test_Runs"
QUERY_CSV = "/storage/savi/saveenas/Projects/SynGlue_Py/query.csv"

def verify_and_test():
    print("🔍 STEP 1: Verifying Database Patching...")
    
    # Load the database using the new patcher logic
    dict_path = os.path.join(DB_DIR, "Clean_Metadata_Hash.pkl")
    csv_path = os.path.join(DB_DIR, "Targets_for_magnetdb.csv")
    
    try:
        patched_db = synglue.load_and_patch_database(dict_path, csv_path)
        
        # Look for a specific BioSnap ID to confirm the "3917:" numbers are gone
        found_test_case = False
        for k, v in patched_db.items():
            tid = str(v.get('Target_ID', '')).strip()
            if "BioSnap_T_01" in tid:
                print(f"✅ FOUND TEST ID: {tid}")
                print(f"✅ CLEAN NAME: {v.get('Target_Name')}")
                print(f"✅ GENE: {v.get('Gene_Name')} | UNIPROT: {v.get('UniProt_ID')}")
                found_test_case = True
                break
        
        if not found_test_case:
            print("⚠️ WARNING: BioSnap_T_01 not found in the current hash map. Check Target ID keys.")

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        return

    print("\n🚀 STEP 2: Running Small-Scale Hybrid Mapping Test...")
    # Run the engine with 4 workers for a quick test
    result_file = synglue.run_hybrid_engine(
        db_dir=DB_DIR, 
        output_dir=OUT_DIR, 
        num_workers=4, 
        csv_path=QUERY_CSV
    )

    if result_file and os.path.exists(result_file):
        print(f"\n🎉 TEST SUCCESSFUL!")
        print(f"Results located at: {result_file}")
        # Show a preview of the clean columns
        df = pd.read_csv(result_file)
        print("\n--- Result Preview ---")
        print(df[['Query_Name', 'Target_Name', 'Target_Coverage', 'Gene_Name']].head())
    else:
        print("\n❌ TEST FAILED: No results generated. Check SMILES similarity thresholds.")

if __name__ == "__main__":
    verify_and_test()
























"""
import os
import pickle
import pandas as pd
import argparse
from tqdm import tqdm
from pathos.multiprocessing import ProcessPool
from rdkit import Chem
from rdkit.Chem import Recap, rdFMCS
from rdkit.Chem.rdmolops import DeleteSubstructs
from rdkit import RDLogger

# Silence RDKit warnings
RDLogger.DisableLog("rdApp.*")

# =====================================================================
# 1. CORE CLASSES & GLOBALS
# =====================================================================
class TrieNode:
    def __init__(self):
        self.children = {}
        self.tag_ids = set()

GLOBAL_TRIE = None
GLOBAL_HASH = None

def safe_mol(smiles):
    if pd.isna(smiles) or not smiles: return None
    try: return Chem.MolFromSmiles(str(smiles))
    except: return None

# =====================================================================
# 2. THE DATABASE PATCHER (Instant Load)
# =====================================================================
def load_and_patch_database(dict_path, clean_csv_path):
    print(f"⏳ Loading Hash Map from {dict_path}...")
    with open(dict_path, "rb") as f:
        raw_db = pickle.load(f)

    print(f"⏳ Applying Clean Target Names from {clean_csv_path}...")
    clean_df = pd.read_csv(clean_csv_path)
    
    lookup = {}
    for _, row in clean_df.iterrows():
        tid = str(row.get('New IDs', '')).strip()
        lookup[tid] = {
            "Name": str(row.get('Target Names', 'Unknown Target')),
            "Gene": str(row.get('Gene Name', 'N/A')),
            "UniProt": str(row.get('UniProt ID', 'N/A'))
        }

    patched_db = {}
    for k, v in raw_db.items():
        tid = str(v.get('Target ID') or v.get('Target_ID', '')).strip()
        
        if tid in lookup:
            v["Target_Name"] = lookup[tid]["Name"]
            v["Gene_Name"] = lookup[tid]["Gene"]
            v["UniProt_ID"] = lookup[tid]["UniProt"]
        else:
            raw_name = str(v.get("Target_Name", "Unknown"))
            v["Target_Name"] = raw_name.split(":", 1)[-1].strip() if ":" in raw_name else raw_name
            v["Gene_Name"] = "N/A"
            v["UniProt_ID"] = "N/A"
            
        smi = v.get("Original_SMILES") or v.get("SMILE") or v.get("SMILES")
        v["Clean_SMILES"] = smi
        v["Target_Atom_Count"] = v.get("Target_Atom_Count", 0) 
        if v["Target_Atom_Count"] == 0 and smi:
            mol = safe_mol(smi)
            if mol: v["Target_Atom_Count"] = mol.GetNumHeavyAtoms()

        patched_db[k] = v
        
    print(f"✅ Database Patched! {len(patched_db)} targets ready for mapping.")
    return patched_db

# =====================================================================
# 3. THE HYBRID WORKER
# =====================================================================
def hybrid_worker(task):
    global GLOBAL_TRIE, GLOBAL_HASH
    try:
        q_smiles, q_name = task
        mol = safe_mol(q_smiles)
        if not mol: return None
        q_atoms = mol.GetNumHeavyAtoms()
        
        hier = Recap.RecapDecompose(mol)
        frags = [s for s in hier.children.keys() if s.count("*") == 1] if hier else []
        hits = []

        for frag in frags:
            frag_mol = safe_mol(frag)
            if not frag_mol: continue
            
            clean_frag = DeleteSubstructs(frag_mol, Chem.MolFromSmarts('[#0]'))
            frag_atoms = clean_frag.GetNumHeavyAtoms()
            if frag_atoms == 0: continue

            search_str = (frag + "$")[::-1]
            node = GLOBAL_TRIE.root
            found = True
            for ch in search_str:
                if ch not in node.children:
                    found = False; break
                node = node.children[ch]

            if found:
                for db_id in node.tag_ids:
                    meta = GLOBAL_HASH.get(db_id)
                    if not meta: continue

                    t_atoms = meta.get("Target_Atom_Count", 0)
                    t_smiles = meta.get("Clean_SMILES")
                    if t_atoms == 0 or not t_smiles: continue

                    f_q = (frag_atoms / q_atoms) * 100
                    f_t = (frag_atoms / t_atoms) * 100

                    if f_q >= 15.0 and f_t >= 30.0:
                        hits.append({
                            "Query_Name": q_name,
                            "Target_ID": meta.get("Target ID", "N/A"),
                            "Target_Name": meta.get("Target_Name"),
                            "Gene_Name": meta.get("Gene_Name"),
                            "UniProt_ID": meta.get("UniProt_ID"),
                            "original_target_smile": t_smiles,
                            "query_frag_smile": frag,
                            "fast_score": f_q + f_t
                        })
        
        if not hits: return None
        
        df = pd.DataFrame(hits).sort_values("fast_score", ascending=False).drop_duplicates("Target_Name").head(200)
        
        def validate(row):
            t_mol = safe_mol(row["original_target_smile"])
            if not t_mol: return pd.Series([0.0, 0.0])
            t_atoms_heavy = t_mol.GetNumHeavyAtoms()
            try:
                mcs = rdFMCS.FindMCS([mol, t_mol], timeout=1, ringMatchesRingOnly=True)
                shared = Chem.MolFromSmarts(mcs.smartsString).GetNumHeavyAtoms() if mcs else 0
            except: 
                shared = 0
            return pd.Series([round((shared / q_atoms) * 100, 2), round((shared / t_atoms_heavy) * 100, 2)])

        df[["Query_Coverage", "Target_Coverage"]] = df.apply(validate, axis=1)
        df = df[df["Target_Coverage"] >= 50.0]
        
        if df.empty: return None
        
        cols = ['Query_Name', 'Target_Coverage', 'Query_Coverage', 'Target_Name', 'Gene_Name', 'UniProt_ID', 'Target_ID', 'original_target_smile', 'query_frag_smile']
        return df[[c for c in cols if c in df.columns]]
        
    except Exception as e: 
        return None

# =====================================================================
# 4. MASTER ENGINE
# =====================================================================
def run_hybrid_engine(db_dir, output_dir, num_workers=10, csv_path=None):
    global GLOBAL_TRIE, GLOBAL_HASH
    
    print(f"\n{'='*60}\n🚀 SYNGLUE HYBRID ENGINE - PACKAGE RUN\n{'='*60}")
    os.makedirs(output_dir, exist_ok=True)
    
    trie_p = os.path.join(db_dir, "Lean_MagnetDB_Trie.pkl")
    hash_p = os.path.join(db_dir, "Clean_Metadata_Hash.pkl")
    csv_p = os.path.join(db_dir, "Targets_for_magnetdb.csv")

    print("⏳ Loading Lean Trie...")
    with open(trie_p, "rb") as f: 
        GLOBAL_TRIE = pickle.load(f)
        
    GLOBAL_HASH = load_and_patch_database(hash_p, csv_p)

    print(f"⏳ Reading Queries from {csv_path}...")
    input_df = pd.read_csv(csv_path)
    
    tasks = [(str(row.iloc[1]), str(row.iloc[0])) for _, row in input_df.iterrows()]
    
    print(f"⚡ Starting multiprocess pool with {num_workers} workers...")
    pool = ProcessPool(nodes=num_workers)
    
    results = [r for r in tqdm(pool.imap(hybrid_worker, tasks), total=len(tasks), desc="Mapping") if r is not None]

    if results:
        final_df = pd.concat(results).sort_values("Target_Coverage", ascending=False)
        out = os.path.join(output_dir, "Hybrid_Mapping_Results.csv")
        final_df.to_csv(out, index=False)
        print(f"\n🎉 SUCCESS! Found {len(final_df)} highly matched targets.")
        print(f"📁 Results saved to: {out}")
        return out
    else:
        print("\n❌ No matches found above 50% Target Coverage threshold.")
        return None

# =====================================================================
# CLI ENTRY POINT (Dynamic Paths for Package Usage)
# =====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SynGlue Hybrid Target Mapping Engine")
    parser.add_argument("--db_dir", required=True, help="Path to the directory containing Trie and Hash .pkl files")
    parser.add_argument("--query", required=True, help="Path to the input query CSV file")
    parser.add_argument("--out_dir", required=True, help="Path to the output directory to save results")
    parser.add_argument("--workers", type=int, default=10, help="Number of CPU cores to use (default: 10)")

    args = parser.parse_args()

    run_hybrid_engine(
        db_dir=args.db_dir,
        output_dir=args.out_dir,
        num_workers=args.workers,
        csv_path=args.query
    )

    
    
"""