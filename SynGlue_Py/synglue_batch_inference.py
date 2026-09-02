import os
import time
import pickle
import argparse
import pandas as pd
from tqdm import tqdm
from rdkit import Chem
from rdkit.Chem import Draw, Recap, rdFMCS
from rdkit.Chem.rdmolops import DeleteSubstructs
from rdkit.Chem.Draw import rdDepictor
from rdkit import RDLogger

# Disable RDKit noise for clean terminal output
RDLogger.DisableLog('rdApp.*')

# =====================================================================
# 1. CORE CLASSES (Required for unpickling)
# =====================================================================
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.tag_ids = set() 

class LeanTrie:
    def __init__(self):
        self.root = TrieNode()
    def __getstate__(self): return self.root
    def __setstate__(self, state): self.root = state

# =====================================================================
# 2. DICTIONARIES & CONSTANTS
# =====================================================================
TYPE_NAMES = {
    "Type 1": "Type 1 (Monovalent Monotarget)", "Type 2": "Type 2 (Monovalent Multitarget)",
    "Type 3": "Type 3 (Multivalent Monotarget)", "Type 4": "Type 4 (Multivalent Multitarget)",
    "Type 5": "Type 5 (Unclassified)"
}

# =====================================================================
# 3. HELPER FUNCTIONS
# =====================================================================
def get_heavy_atom_count(smile):
    try:
        mol = Chem.MolFromSmiles(smile)
        if not mol: return 0
        return DeleteSubstructs(mol, Chem.MolFromSmarts('[#0]')).GetNumHeavyAtoms()
    except: return 0

def perform_type_analysis(df, parent_smiles):
    unique_queries = set(df['query_frag_smile'].unique())
    unique_target_count = df['Target_ID'].nunique()
    molecule = Chem.MolFromSmiles(parent_smiles)
    hierarchy = Recap.RecapDecompose(molecule)
    first_level_keys = sorted(hierarchy.children.keys())

    if len(first_level_keys) < 2:
        df['Polypharmacology_Type'] = "Type 1" if unique_target_count == 1 else "Type 2"
        return df

    def get_mcs_smile(q_mol, t_mol):
        if not q_mol or not t_mol: return None
        mcs = rdFMCS.FindMCS([q_mol, t_mol], timeout=2)
        if not mcs or not mcs.smartsString: return None
        return Chem.MolToSmiles(Chem.MolFromSmarts(mcs.smartsString), isomericSmiles=True)

    query_frag_mol = Chem.MolFromSmiles(Chem.MolToSmiles(hierarchy.children[first_level_keys[0]].mol, isomericSmiles=True))
    s1map, s2map = [Chem.MolToSmiles(query_frag_mol)], []

    for i in range(1, len(first_level_keys)):
        t_frag = Chem.MolToSmiles(hierarchy.children[first_level_keys[i]].mol, isomericSmiles=True)
        if get_mcs_smile(query_frag_mol, Chem.MolFromSmiles(t_frag)) == Chem.MolToSmiles(query_frag_mol, isomericSmiles=True):
            s1map.append(t_frag)
        else: s2map.append(t_frag)

    s1_match = any(get_mcs_smile(Chem.MolFromSmiles(f), Chem.MolFromSmiles(q)) == q for q in unique_queries for f in s1map)
    s2_match = any(get_mcs_smile(Chem.MolFromSmiles(f), Chem.MolFromSmiles(q)) == q for q in unique_queries for f in s2map)

    if len(unique_queries) <= 1: res = "Type 1" if unique_target_count == 1 else "Type 2"
    else: res = ("Type 1" if unique_target_count == 1 else "Type 2") if not s1_match and not s2_match else ("Type 3" if unique_target_count == 1 else "Type 4")

    df['Polypharmacology_Type'] = res
    return df

# =====================================================================
# 4. CORE SEARCH ENGINE (TURBO MODE)
# =====================================================================
def search_molecule(user_smiles, query_name, trie, metadata_hash, output_dir, min_q_cov=25.0, min_t_cov=75.0):
    mol = Chem.MolFromSmiles(user_smiles)
    if not mol: return pd.DataFrame()
        
    terminal_fragments = [smi for smi, node in Recap.RecapDecompose(mol).children.items() if smi.count('*') == 1]
    q_smile_atoms = mol.GetNumHeavyAtoms()
    results = []

    # --- STAGE 1: LIGHTNING FAST TRIE SEARCH ---
    for frag in terminal_fragments:
        node = trie.root
        match_found = True
        for char in (frag + "$")[::-1]:
            if char not in node.children: match_found = False; break
            node = node.children[char]
            
        if match_found and node.is_end_of_word:
            q_frag_atoms = get_heavy_atom_count(frag)
            for db_id in node.tag_ids:
                if db_id in metadata_hash:
                    meta = metadata_hash[db_id]
                    t_smile_atoms = meta["Target_Atom_Count"]
                    
                    # Fast Pre-score calculation
                    f_q_cov = (q_frag_atoms / q_smile_atoms) * 100
                    f_t_cov = (q_frag_atoms / t_smile_atoms) * 100
                    
                    if f_q_cov >= min_q_cov and f_t_cov >= 50.0:
                        results.append({
                            "Database_ID": db_id, "Target_ID": meta["Target_ID"],
                            "Target_Name": meta["Target_Name"], "Ligand_Name": meta["Ligand_Name"],
                            "Organism": meta["Organism"], "Assay": meta["Assay"],
                            "query_frag_smile": frag, "original_target_smile": meta["Original_SMILES"],
                            "fast_score": f_q_cov + f_t_cov
                        })

    df = pd.DataFrame(results)
    if df.empty: return df

    # --- TURBO FILTER: REDUCE 200k HITS TO TOP 500 ---
    # This prevents the "0% Hang"
    df = df.sort_values(by='fast_score', ascending=False).drop_duplicates(subset=['Database_ID'])
    df = df.head(500) 
    print(f"      -> Filtered to Top {len(df)} candidates. Running rigorous MCS...")

    # --- STAGE 2: RIGOROUS MCS VALIDATION ---
    def validate_mcs(row):
        t_mol = Chem.MolFromSmiles(row['original_target_smile'])
        if not t_mol: return pd.Series([0.0, 0.0])
        mcs = rdFMCS.FindMCS([mol, t_mol], timeout=1, ringMatchesRingOnly=True)
        if not mcs or not mcs.smartsString: mcs = rdFMCS.FindMCS([mol, t_mol], timeout=1)
        shared_atoms = Chem.MolFromSmarts(mcs.smartsString).GetNumHeavyAtoms() if (mcs and mcs.smartsString) else 0
        return pd.Series([(shared_atoms / q_smile_atoms) * 100, (shared_atoms / t_mol.GetNumHeavyAtoms()) * 100])

    df[['Query_Percentage', 'Target_Percentage']] = df.apply(validate_mcs, axis=1)
    df = df[(df["Query_Percentage"] >= min_q_cov) & (df["Target_Percentage"] >= min_t_cov)]
    
    if df.empty: return df

    # Clean up and sort by biological relevance
    df = perform_type_analysis(df, user_smiles)
    df = df.sort_values(by=['Target_Percentage', 'Query_Percentage'], ascending=[False, False])
    df.to_csv(os.path.join(output_dir, f"{query_name}_Mapped_Targets.csv"), index=False)

    # --- STAGE 3: GENERATE TOP 3 VISUALS ---
    rdDepictor.SetPreferCoordGen(True)
    dopts = Draw.rdMolDraw2D.MolDrawOptions()
    dopts.continuousHighlight = True               
    dopts.setHighlightColour((0.9, 0.4, 0.7, 0.5)) 
    
    top_hits = df.head(3)
    img_list, legends, hl_parent, hl_target = [], [], [], []
    
    for _, row in top_hits.iterrows():
        t_mol = Chem.MolFromSmiles(row['original_target_smile'])
        mcs = rdFMCS.FindMCS([mol, t_mol], timeout=3, ringMatchesRingOnly=True)
        mcs_mol = Chem.MolFromSmarts(mcs.smartsString) if (mcs and mcs.smartsString) else None
        
        hl_parent.append(list(mol.GetSubstructMatch(mcs_mol)) if mcs_mol else [])
        hl_target.append(list(t_mol.GetSubstructMatch(mcs_mol)) if mcs_mol else [])
        img_list.extend([mol, t_mol])
        
        q_cov, t_cov, db_id = float(row['Query_Percentage']), float(row['Target_Percentage']), str(row['Database_ID'])
        legends.extend([f"Query Molecule\nCov: {q_cov:.1f}%", f"Target: {db_id}\nCov: {t_cov:.1f}%"])

    if img_list:
        img = Draw.MolsToGridImage(img_list, highlightAtomLists=hl_parent + hl_target, legends=legends, molsPerRow=2, subImgSize=(400, 350), drawOptions=dopts)
        img.save(os.path.join(output_dir, f"{query_name}_Top3_Visuals.png"))

    return df

# =====================================================================
# 5. CONTINUOUS BATCH PROCESSOR
# =====================================================================
def run_continuous_engine(db_dir=".", output_dir="SynGlue_Outputs"):
    print(f"\n{'='*60}\n🚀 SYNGLUE CONTINUOUS ENGINE (TURBO MODE)\n{'='*60}")
    os.makedirs(output_dir, exist_ok=True)
    
    t0_load = time.time()
    try:
        print("⏳ Loading 5.6M entry database (Wait ~5-8 mins)...")
        with open(os.path.join(db_dir, "Lean_MagnetDB_Trie.pkl"), "rb") as f: trie = pickle.load(f)
        with open(os.path.join(db_dir, "Clean_Metadata_Hash_FINAL_GENE_FIXED.pkl"), "rb") as f: metadata_hash = pickle.load(f)
        print(f"✅ DATABASES LOCKED IN RAM ({time.time() - t0_load:.2f} sec). READY!")
    except FileNotFoundError:
        print(f"❌ Error: Database files not found in '{db_dir}'.")
        return

    while True:
        print("\n" + "="*60)
        csv_path = input("📁 Enter CSV path (or 'quit'): ").strip()
        if csv_path.lower() in ['quit', 'exit', 'q']: break
        if not os.path.exists(csv_path): continue

        try:
            input_df = pd.read_csv(csv_path)
            smiles_col = "SMILES" if "SMILES" in input_df.columns else input_df.columns[1]
            name_col = "Name" if "Name" in input_df.columns else input_df.columns[0]
            
            print(f"\n🔬 Processing {len(input_df)} molecules...")
            for idx, row in tqdm(input_df.iterrows(), total=len(input_df)):
                search_molecule(str(row[smiles_col]).strip(), str(row[name_col]).strip(), trie, metadata_hash, output_dir)
            print(f"\n🎉 Batch Complete! Results in {output_dir}/")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db_dir", type=str, default="data")
    parser.add_argument("--out_dir", type=str, default="outputs/SynGlue_Runs")
    args = parser.parse_args()
    run_continuous_engine(db_dir=args.db_dir, output_dir=args.out_dir)