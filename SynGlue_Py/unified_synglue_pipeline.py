import os
import sys
import pickle
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from pathos.multiprocessing import ProcessPool
from IPython.display import display

from rdkit import Chem
from rdkit.Chem import Draw, Recap, rdFMCS
from rdkit.Chem.Draw import rdDepictor
from rdkit.Chem.rdmolops import DeleteSubstructs
from rdkit import RDLogger

# =====================================================================
# 1. INITIALIZATION & STYLING
# =====================================================================
RDLogger.DisableLog('rdApp.*') # Mutes strict RDKit SMARTS warnings

custom_params = {"axes.spines.right": False, "axes.spines.top": False}
sns.set_theme(style="ticks", rc=custom_params)
plt.rcParams.update({
    "font.family": "Arial", "font.size": 8, "svg.fonttype": "none",
    "pdf.fonttype": 42, "axes.linewidth": 1.0, "xtick.major.width": 0.8,
    "ytick.major.width": 0.8, "xtick.direction": "out", "ytick.direction": "out"
})

# =====================================================================
# 2. CORE CLASSES & GLOBALS (For Unpickling)
# =====================================================================
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.tag_ids = set()

# CRITICAL: Named 'Trie' to properly unpickle the old memory files
class Trie:
    def __init__(self):
        self.root = TrieNode()
    def __getstate__(self): return self.root
    def __setstate__(self, state): self.root = state

GLOBAL_TRIE = None
GLOBAL_HASH = None

def safe_mol(smiles):
    if pd.isna(smiles) or not smiles: return None
    try: return Chem.MolFromSmiles(str(smiles))
    except: return None

# =====================================================================
# 3. DICTIONARIES (Chemical Groups & Polypharmacology)
# =====================================================================
MASTER_CHEMICAL_GROUPS = {
    'cation': {'smarts': '[+]'}, 'anion': {'smarts': '[-]'},
    'carbonyl compound': {'smarts': 'C=O'}, 'ketone': {'smarts': 'C(=O)C'},
    'amide': {'smarts': 'C(=O)N'}, 'primary amine': {'smarts': '[NX3H2]'}, 
    'secondary amine': {'smarts': '[NX3H1]'}, 'tertiary amine': {'smarts': '[NX3H0]'}, 
    'alcohol': {'smarts': '[OX2H]'}, 'phenol': {'smarts': 'c1ccccc1[OH]'}, 
    'halogen': {'smarts': '[F,Cl,Br,I]'}, 'cyanide / nitrile': {'smarts': 'C#N'}, 
    'pyridine': {'smarts': 'c1ccncc1'}, 'pyrimidine': {'smarts': 'c1cncnc1'},
    'imidazole': {'smarts': 'c1c[nH]cn1'}, 'pyrazole': {'smarts': 'c1c[nH]nc1'}
}

TYPE_NAMES = {
    "Type 1": "Type 1 (Monovalent Monotarget)",
    "Type 2": "Type 2 (Monovalent Multitarget)",
    "Type 3": "Type 3 (Multivalent Monotarget)",
    "Type 4": "Type 4 (Multivalent Multitarget)",
    "Type 5": "Type 5 (Unclassified)"
}

def identify_functional_groups(mol):
    detected = []
    for name, props in MASTER_CHEMICAL_GROUPS.items():
        pat = Chem.MolFromSmarts(props['smarts'])
        if pat and mol.GetSubstructMatches(pat):
            detected.append(f"{name} ({len(mol.GetSubstructMatches(pat))})")
    return ", ".join(detected) if detected else "None"

# =====================================================================
# 4. DATABASE PATCHER (Injects Gene & UniProt perfectly)
# =====================================================================
def load_and_patch_database(dict_path, clean_csv_path):
    print(f"⏳ Loading Hash Map from {dict_path}...")
    with open(dict_path, "rb") as f: raw_db = pickle.load(f)

    print(f"⏳ Applying Metadata from {clean_csv_path}...")
    clean_df = pd.read_csv(clean_csv_path)
    
    lookup = {}
    for _, row in clean_df.iterrows():
        tid = str(row.get('New IDs', '')).strip()
        lookup[tid] = {
            "Name": str(row.get('Target Names', 'Unknown')),
            "Gene": str(row.get('Gene Name', 'Unknown')),
            "UniProt": str(row.get('UniProt ID', 'Unknown'))
        }

    patched_db = {}
    for k, v in raw_db.items():
        tid = str(v.get('Target ID') or v.get('Target_ID') or k).strip()
        v["Target_ID"] = tid
        v["Database_ID"] = k
        
        if tid in lookup:
            v["Target_Name"] = lookup[tid]["Name"]
            v["Gene_Name"] = lookup[tid]["Gene"]
            v["UniProt_ID"] = lookup[tid]["UniProt"]
        else:
            r_name = str(v.get("Target_Name", v.get("Target", "Unknown")))
            v["Target_Name"] = r_name.split(":", 1)[-1].strip() if ":" in r_name else r_name
            v["Gene_Name"] = "Unknown"
            v["UniProt_ID"] = "Unknown"
            
        smi = v.get("Original_SMILES") or v.get("SMILE") or v.get("SMILES")
        v["Clean_SMILES"] = smi
        v["Target_Atom_Count"] = v.get("Target_Atom_Count", 0) 
        if v["Target_Atom_Count"] == 0 and smi:
            mol = safe_mol(smi)
            if mol: v["Target_Atom_Count"] = mol.GetNumHeavyAtoms()

        patched_db[k] = v
    print(f"✅ Database Patched! {len(patched_db)} targets ready.")
    return patched_db

# =====================================================================
# 5. MULTIPROCESSING WORKER (True MCS Validation)
# =====================================================================
def hybrid_worker(task):
    global GLOBAL_TRIE, GLOBAL_HASH
    try:
        q_smiles, q_name = task
        mol = safe_mol(q_smiles)
        if not mol: return None
        q_atoms = mol.GetNumHeavyAtoms()
        if q_atoms < 10: return None # Drop junk queries early
        
        hier = Recap.RecapDecompose(mol)
        frags = [s for s in hier.children.keys() if s.count("*") == 1] if hier else []
        hits = []

        for frag in frags:
            frag_mol = safe_mol(frag)
            if not frag_mol: continue
            
            clean_frag_mol = DeleteSubstructs(frag_mol, Chem.MolFromSmarts('[#0]'))
            frag_atoms = clean_frag_mol.GetNumHeavyAtoms()
            if frag_atoms == 0: continue

            # THE CRITICAL FIX: Strip the '*' from the string before searching the Trie
            clean_search_frag = frag.replace('*', '')
            search_str = (clean_search_frag + "$")[::-1]
            
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
                            "Query_SMILES": q_smiles,
                            "Database_ID": meta.get("Database_ID", "Unknown"),
                            "Target_ID": meta.get("Target_ID", "Unknown"),
                            "Target_Name": meta.get("Target_Name", "Unknown"),
                            "Gene_Name": meta.get("Gene_Name", "Unknown"),
                            "UniProt_ID": meta.get("UniProt_ID", "Unknown"),
                            "Ligand_Name": meta.get("Ligand_Name", "Unknown"),
                            "Organism": meta.get("Organism", "Unknown"),
                            "original_target_smile": t_smiles,
                            "query_frag_smile": frag,
                            "fast_score": f_q + f_t
                        })
        
        if not hits: return None
        df = pd.DataFrame(hits).sort_values("fast_score", ascending=False).drop_duplicates("Target_Name").head(150)
        
        # Rigorous MCS Validation
        def validate(row):
            t_mol = safe_mol(row["original_target_smile"])
            if not t_mol: return pd.Series([0.0, 0.0])
            t_atoms_heavy = t_mol.GetNumHeavyAtoms()
            try:
                mcs = rdFMCS.FindMCS([mol, t_mol], timeout=2, ringMatchesRingOnly=True, completeRingsOnly=True)
                if not mcs or not mcs.smartsString: mcs = rdFMCS.FindMCS([mol, t_mol], timeout=2)
                shared = Chem.MolFromSmarts(mcs.smartsString).GetNumHeavyAtoms() if mcs else 0
            except: shared = 0
            return pd.Series([round((shared / q_atoms) * 100, 2), round((shared / t_atoms_heavy) * 100, 2)])

        df[["Query_Percentage", "Target_Percentage"]] = df.apply(validate, axis=1)
        
        # Strict Final Cutoff
        df = df[(df["Query_Percentage"] >= 25.0) & (df["Target_Percentage"] >= 75.0) & (df["Target_Percentage"] <= 100.0)]
        return df if not df.empty else None
        
    except Exception as e: 
        return None

# =====================================================================
# 6. POLYPHARMACOLOGY CLASSIFIER
# =====================================================================
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
        return Chem.MolToSmiles(Chem.MolFromSmarts(mcs.smartsString), isomericSmiles=True) if mcs and mcs.smartsString else None

    query_frag_mol = Chem.MolFromSmiles(Chem.MolToSmiles(hierarchy.children[first_level_keys[0]].mol, isomericSmiles=True))
    s1map_list = [Chem.MolToSmiles(query_frag_mol, isomericSmiles=True)]
    s2map_list = []

    for i in range(1, len(first_level_keys)):
        target_frag = Chem.MolToSmiles(hierarchy.children[first_level_keys[i]].mol, isomericSmiles=True)
        mcs_smile = get_mcs_smile(query_frag_mol, Chem.MolFromSmiles(target_frag))
        if mcs_smile == Chem.MolToSmiles(query_frag_mol, isomericSmiles=True): s1map_list.append(target_frag)
        else: s2map_list.append(target_frag)

    s1_match = s2_match = False
    for query in unique_queries:
        for s1 in s1map_list:
            if get_mcs_smile(Chem.MolFromSmiles(s1), Chem.MolFromSmiles(query)) == query: s1_match = True
        for s2 in s2map_list:
            if get_mcs_smile(Chem.MolFromSmiles(s2), Chem.MolFromSmiles(query)) == query: s2_match = True

    if len(unique_queries) < 1: res = "Type 5"
    elif len(unique_queries) == 1: res = "Type 1" if unique_target_count == 1 else "Type 2"
    else: res = ("Type 1" if unique_target_count == 1 else "Type 2") if not s1_match and not s2_match else ("Type 3" if unique_target_count == 1 else "Type 4")

    df['Polypharmacology_Type'] = res
    return df

# =====================================================================
# 7. MASTER PIPELINE ORCHESTRATOR
# =====================================================================
def run_unified_pipeline(db_dir, output_dir, csv_path, num_workers=10):
    global GLOBAL_TRIE, GLOBAL_HASH
    print(f"\n{'='*70}\n🚀 SYNGLUE UNIFIED ENGINE (Map -> Classify -> Visualize)\n{'='*70}")
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. LOAD DATABASES
    # Now specifically locked to the Lean Trie we verified earlier
    trie_p = os.path.join(db_dir, "Lean_MagnetDB_Trie.pkl")
    hash_p = os.path.join(db_dir, "Clean_Metadata_Hash_FINAL_GENE_FIXED.pkl")
    meta_p = os.path.join(db_dir, "Targets_for_magnetdb.csv")

    with open(trie_p, "rb") as f: GLOBAL_TRIE = pickle.load(f)
    GLOBAL_HASH = load_and_patch_database(hash_p, meta_p)

    # 2. RUN MULTIPROCESSING
    input_df = pd.read_csv(csv_path)
    smile_col = next((c for c in input_df.columns if c.lower() in ['smiles', 'smile']), input_df.columns[1])
    name_col = next((c for c in input_df.columns if c.lower() in ['name', 'id']), input_df.columns[0])
    
    tasks = [(str(row[smile_col]), str(row[name_col])) for _, row in input_df.iterrows()]
    print(f"\n⚡ Starting Pool ({num_workers} workers) for {len(tasks)} queries...")
    
    pool = ProcessPool(nodes=num_workers)
    results = [r for r in tqdm(pool.imap(hybrid_worker, tasks), total=len(tasks), desc="Mapping & MCS") if r is not None]

    if not results:
        print("\n❌ No valid matches survived the true MCS validation thresholds.")
        return

    # 3. STRUCTURE FINAL DATAFRAME & CLASSIFY
    print("\n🧬 Classifying Polypharmacology Types...")
    final_dfs = []
    for query_df in results:
        parent_smi = query_df['Query_SMILES'].iloc[0]
        classified_df = perform_type_analysis(query_df, parent_smi)
        final_dfs.append(classified_df)

    master_df = pd.concat(final_dfs)
    
    # Formatting perfect column order
    cols_order = ['Query_Name', 'Database_ID', 'Target_ID', 'Target_Name', 'Gene_Name', 'UniProt_ID', 
                  'Query_Percentage', 'Target_Percentage', 'Polypharmacology_Type', 
                  'Ligand_Name', 'Organism', 'original_target_smile', 'query_frag_smile', 'Query_SMILES']
    master_df = master_df[[c for c in cols_order if c in master_df.columns]]
    
    out_csv = os.path.join(output_dir, "Final_Validated_Results.csv")
    master_df.to_csv(out_csv, index=False)
    print(f"💾 Saved strictly validated results to {out_csv}")

    # 4. VISUALIZATION LOOP
    print("\n🎨 Generating RDKit Visualizations for Top 3 Hits per Query...")
    rdDepictor.SetPreferCoordGen(True)
    dopts = Draw.rdMolDraw2D.MolDrawOptions()
    dopts.continuousHighlight = True               
    dopts.setHighlightColour((0.9, 0.4, 0.7, 0.5))

    for q_name, group_df in master_df.groupby("Query_Name"):
        print(f"\n\n🔥 Query: {q_name.upper()} 🔥")
        parent_smi = group_df['Query_SMILES'].iloc[0]
        parent_mol = Chem.MolFromSmiles(parent_smi)
        
        vis_df = group_df.sort_values(by=['Target_Percentage', 'Query_Percentage'], ascending=[False, False]).head(3)

        for _, row in vis_df.iterrows():
            desc_type = TYPE_NAMES.get(row['Polypharmacology_Type'], row['Polypharmacology_Type'])
            
            print("-" * 80)
            print(f"🎯 Target ID:           {row.get('Target_ID', 'Unknown')}")
            print(f"📝 Full Protein Name:   {row.get('Target_Name', 'Unknown')}")
            print(f"🧬 Gene Name:           {row.get('Gene_Name', 'Unknown')}")
            print(f"🔗 UniProt ID:          {row.get('UniProt_ID', 'Unknown')}")
            print(f"   • Database ID:       {row.get('Database_ID', 'N/A')}")
            print(f"   • Query Coverage:    {row['Query_Percentage']:.1f}%")
            print(f"   • Target Coverage:   {row['Target_Percentage']:.1f}%")
            print(f"   • Class:             {desc_type}")
            
            t_mol = Chem.MolFromSmiles(row['original_target_smile'])
            if not parent_mol or not t_mol: continue

            mcs = rdFMCS.FindMCS([parent_mol, t_mol], timeout=5, ringMatchesRingOnly=True, completeRingsOnly=True)
            if not mcs or not mcs.smartsString: mcs = rdFMCS.FindMCS([parent_mol, t_mol], timeout=5)
                
            if mcs and mcs.smartsString:
                mcs_mol = Chem.MolFromSmarts(mcs.smartsString)
                match_parent = parent_mol.GetSubstructMatch(mcs_mol)
                match_target = t_mol.GetSubstructMatch(mcs_mol)
            else:
                match_parent, match_target = (), ()

            print(f"\nQuery Func Groups:  {identify_functional_groups(parent_mol)}")
            print(f"Target Func Groups: {identify_functional_groups(t_mol)}")

            img = Draw.MolsToGridImage(
                [parent_mol, t_mol], highlightAtomLists=[list(match_parent), list(match_target)],
                legends=[f"Query Molecule\nCov: {row['Query_Percentage']:.1f}%", f"Target ({row.get('Database_ID', 'Unknown')})\nCov: {row['Target_Percentage']:.1f}%"],
                molsPerRow=2, subImgSize=(450, 400), useSVG=True, drawOptions=dopts
            )
            display(img)

# =====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db_dir", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()
    
    run_unified_pipeline(args.db_dir, args.out_dir, args.query, args.workers)