import os
import sys
import json
import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt
import seaborn as sns
import torch
import torch.nn as nn
import joblib
import subprocess
import logging
import warnings

from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen, rdMolDescriptors, Draw
from rdkit.Chem import RDConfig
from rdkit import RDLogger
from tqdm.auto import tqdm

# Suppress verbose RDKit warnings
RDLogger.DisableLog('rdApp.*')

# Setup Logging
logging.basicConfig(level=logging.INFO, format='INFO:SynGlueEngine:%(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# 1. GLOBAL CONFIGURATION (Docker & Host Environment Aware Paths)
# =============================================================================
# Resolve base paths from environment variables if present, otherwise auto-detect Docker vs. Host
BASE_DIR = os.environ.get("SYNGLUE_BASE_DIR", "/app" if os.path.exists("/app/data") else "/storage/savi/saveenas/Projects/SynGlue_Py")
DATA_DIR = os.environ.get("SYNGLUE_DATA_DIR", os.path.join(BASE_DIR, "data"))
MODEL_DIR = os.environ.get("SYNGLUE_MODEL_DIR", os.path.join(BASE_DIR, "models"))
OUTPUT_DIR = os.environ.get("SYNGLUE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
REPOS_DIR = os.environ.get("SYNGLUE_REPOS_DIR", os.path.join(BASE_DIR, "repos"))

CONFIG = {
    "e3_db_path": os.path.join(DATA_DIR, "e3_ligand.csv"),
    "fragments_db_path": os.path.join(DATA_DIR, "warhead_fragments.pkl"),
    "reinvent_env": os.environ.get("SYNGLUE_REINVENT_ENV", "/opt/conda/envs/reinvent" if os.path.exists("/opt/conda/envs/reinvent") else "/home/saveenas/miniconda3/envs/reinvent.v3.2"),
    "reinvent_dir": os.path.join(REPOS_DIR, "reinvent"),
    "output_dir": OUTPUT_DIR,
    "batch_size": 16,
    "n_steps": 100,
    "grover_dir": os.path.join(REPOS_DIR, "grover"),
    "grover_checkpoint": os.path.join(MODEL_DIR, "grover_fixed.pt"),
    "linkinvent_prior": os.path.join(MODEL_DIR, "linkinvent.prior"),
    "pt_model": os.path.join(MODEL_DIR, "multitask_transformer.pt"),
    "rf_dc50_model": os.path.join(MODEL_DIR, "rf_dc50.joblib"),
    "rf_dmax_model": os.path.join(MODEL_DIR, "rf_dmax.joblib"),
    "warhead_csv": os.path.join(DATA_DIR, "grover_warhead.csv"),
    "e3_csv": os.path.join(DATA_DIR, "grover_e3.csv"),
    "admet_env_python": os.environ.get("SYNGLUE_ADMET_ENV_PYTHON", "/opt/conda/envs/admet/bin/python" if os.path.exists("/opt/conda/envs/admet/bin/python") else "/home/saveenas/miniconda3/envs/admet/bin/python"),
    "linker_class_model": os.path.join(MODEL_DIR, "linker_classifier.pkl")
}

# Explicitly define Python binaries
REINVENT_PYTHON = os.path.join(CONFIG['reinvent_env'], "bin/python")
MAGNET_PYTHON = sys.executable  # Uses the healthy, current environment containing numpy/torch

# =============================================================================
# ENVIRONMENT SCRUBBER UTILITY (Crucial for Subprocess stability)
# =============================================================================
def _get_scrubbed_env(target_env_path, extra_pythonpath=None):
    """Removes Conda bleed-over to ensure subprocesses use correct libraries."""
    clean_env = os.environ.copy()
    keys_to_scrub = ['PYTHONHOME', 'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV', 'CONDA_PREFIX']
    for key in keys_to_scrub:
        clean_env.pop(key, None)
    
    clean_env['PATH'] = f"{target_env_path}/bin:{clean_env.get('PATH', '')}"
    clean_env['MPLBACKEND'] = 'Agg'
    
    if extra_pythonpath:
        clean_env['PYTHONPATH'] = f"{extra_pythonpath}:{clean_env.get('PYTHONPATH', '')}"
    return clean_env

# =============================================================================
# 2. PHYSICOCHEMICAL, ADME & SYNTHESIZABILITY CALCULATOR
# =============================================================================
try:
    sys.path.append(os.path.join(RDConfig.RDPaths['RDContribDir'], 'SA_Score'))
    import sascorer
    SA_AVAILABLE = True
except:
    SA_AVAILABLE = False

def get_synthesizability(mol):
    if SA_AVAILABLE:
        try:
            return f"SA Score: {round(sascorer.calculateScore(mol), 2)}"
        except: pass
    fsp3 = rdMolDescriptors.CalcFractionCSP3(mol)
    return f"Fsp3 (Complexity): {round(fsp3, 2)}"

def calculate_adme_properties(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol: return None
    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    tpsa = rdMolDescriptors.CalcTPSA(mol)
    rot_bonds = rdMolDescriptors.CalcNumRotatableBonds(mol)
    arom_rings = rdMolDescriptors.CalcNumAromaticRings(mol)
    heavy_atoms = mol.GetNumHeavyAtoms()
    arom_proportion = arom_rings / heavy_atoms if heavy_atoms > 0 else 0
    esol_logs = 0.16 - (0.63 * logp) - (0.0062 * mw) + (0.066 * rot_bonds) - (0.74 * arom_proportion)
    return {
        "MW": round(mw, 2), "logP": round(logp, 2), "TPSA": round(tpsa, 2),
        "Flexibility": rot_bonds, "Solubility_LogS": round(esol_logs, 2),
        "Synthesizability": get_synthesizability(mol)
    }

# =============================================================================
# 3. LINKER EXTRACTION & CLASSIFICATION ENGINE
# =============================================================================
def remove_dummy_atoms(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol: return None
    rwmol = Chem.RWMol(mol)
    dummy_indices = [atom.GetIdx() for atom in rwmol.GetAtoms() if atom.GetAtomicNum() == 0]
    for idx in sorted(dummy_indices, reverse=True):
        rwmol.RemoveAtom(idx)
    return rwmol.GetMol()

def extract_linker_smiles(protac_smiles, wh_smi, e3_smi):
    protac = Chem.MolFromSmiles(protac_smiles)
    wh_mol = remove_dummy_atoms(wh_smi)
    e3_mol = remove_dummy_atoms(e3_smi)
    
    if not protac or not wh_mol or not e3_mol: return None
    wh_match = protac.GetSubstructMatch(wh_mol)
    e3_match = protac.GetSubstructMatch(e3_mol)
    
    if not wh_match or not e3_match or set(wh_match).intersection(set(e3_match)): return None
    atoms_to_delete = list(set(wh_match + e3_match))
    rw_mol = Chem.RWMol(protac)
    for idx in sorted(atoms_to_delete, reverse=True): rw_mol.RemoveAtom(idx)
        
    try:
        Chem.SanitizeMol(rw_mol)
        linker_smiles = Chem.MolToSmiles(rw_mol)
        return linker_smiles if linker_smiles else None
    except: return None

def run_linker_classification(df_candidates, warhead_smi, e3_smi, output_dir, config_dict):
    logger.info("✂️ Extracting pure Linkers from PROTACs...")
    df_candidates['Linker_SMILES'] = df_candidates['SMILES'].apply(lambda x: extract_linker_smiles(x, warhead_smi, e3_smi))
    
    valid_df = df_candidates[df_candidates['Linker_SMILES'].notna()].copy()
    valid_linkers = valid_df['Linker_SMILES'].tolist()
    
    if not valid_linkers:
        logger.warning("❌ Failed to extract valid linkers.")
        return df_candidates
        
    logger.info(f"🚀 Processing {len(valid_linkers)} valid linkers for Class Prediction...")
    smiles_file = os.path.join(output_dir, "temp_linker_smiles.csv")
    features_file = os.path.join(output_dir, "temp_linker_features.npz")
    fingerprint_file = os.path.join(output_dir, "temp_linker_fps.npz")
    
    pd.DataFrame({'smiles': valid_linkers}).to_csv(smiles_file, index=False)
    
    # GROVER runs in the Magnet environment, just needs PYTHONPATH updated
    grover_env = os.environ.copy()
    grover_env['MPLBACKEND'] = 'Agg'
    grover_env['PYTHONPATH'] = f"{config_dict['grover_dir']}:{grover_env.get('PYTHONPATH', '')}"
    
    logger.info("⏳ Extracting Linker RDKit 2D features...")
    try:
        subprocess.run(
            f"{MAGNET_PYTHON} {config_dict['grover_dir']}/scripts/save_features.py "
            f"--data_path {smiles_file} --save_path {features_file} "
            f"--features_generator rdkit_2d_normalized --restart", 
            shell=True, check=True, env=grover_env, capture_output=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ GROVER Feature Extraction Failed! Log: {e.stderr.decode()[-1000:]}")
        return df_candidates
    
    logger.info("⏳ Extracting Linker GROVER embeddings...")
    try:
        subprocess.run(
            f"{MAGNET_PYTHON} {config_dict['grover_dir']}/main.py fingerprint "
            f"--data_path {smiles_file} --features_path {features_file} "
            f"--checkpoint_path {config_dict['grover_checkpoint']} "
            f"--fingerprint_source both --output {fingerprint_file}", 
            shell=True, check=True, env=grover_env, capture_output=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ GROVER Fingerprint Extraction Failed! Log: {e.stderr.decode()[-1000:]}")
        return df_candidates
    
    try:
        grover_fps = np.load(fingerprint_file, allow_pickle=True)['fps'][:, :4800]
        model = joblib.load(config_dict['linker_class_model'])
        X_test = pd.DataFrame(grover_fps, columns=model.feature_names_in_)
        
        y_pred = model.predict(X_test)
        y_proba = np.max(model.predict_proba(X_test), axis=1)
        
        df_candidates['Predicted_Linker_Class'] = df_candidates['Linker_SMILES'].map(dict(zip(valid_linkers, y_pred)))
        df_candidates['Linker_Class_Prob'] = df_candidates['Linker_SMILES'].map(dict(zip(valid_linkers, y_proba)))
    except Exception as e:
        logger.error(f"❌ Linker Classification Failed: {e}")

    for f in [smiles_file, features_file, fingerprint_file]:
        if os.path.exists(f): os.remove(f)
        
    logger.info("✅ Linker Classification complete!")
    return df_candidates

# =============================================================================
# 4. VISUALIZATION ENGINE 
# =============================================================================
def visualize_exit_vectors(warhead_smi, e3_smi, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    mols = [Chem.MolFromSmiles(s) for s in [warhead_smi, e3_smi] if Chem.MolFromSmiles(s)]
    if mols:
        draw_opts = Draw.MolDrawOptions()
        draw_opts.legendFontSize = 24 
        img = Draw.MolsToGridImage(mols, molsPerRow=2, subImgSize=(500, 500), legends=["Optimized Warhead", "Tagged E3 Ligase"], returnPNG=False, drawOptions=draw_opts)
        img.save(os.path.join(output_dir, "Exit_Vectors.png"))

def visualize_top_protacs(df, output_dir, top_n=3):
    if 'Predicted_DC50_nM' not in df.columns:
        logger.warning("Cannot draw top PROTACs: Predicted_DC50_nM missing.")
        return

    top_df = df.sort_values(by=['Predicted_DC50_nM', 'Predicted_DMax_%'], ascending=[True, False]).head(top_n).copy()
    top_df['ADME'] = top_df['SMILES'].apply(calculate_adme_properties)
    
    mols, legends = [], []
    for _, row in top_df.iterrows():
        mol = Chem.MolFromSmiles(row['SMILES'])
        if mol and row['ADME']:
            mols.append(mol)
            adme = row['ADME']
            l_info = f"\nClass: {row.get('Predicted_Linker_Class', 'Unknown')} ({row.get('Linker_Class_Prob', 0):.2f})" if 'Predicted_Linker_Class' in row else ""
            legends.append(f"DC50: {row['Predicted_DC50_nM']:.1f} nM | DMax: {row['Predicted_DMax_%']:.1f}%\nMW: {adme['MW']} | logP: {adme['logP']}\n{adme['Synthesizability']}{l_info}")
            
    if mols:
        draw_opts = Draw.MolDrawOptions()
        draw_opts.legendFontSize = 24 
        img = Draw.MolsToGridImage(mols, molsPerRow=min(top_n, 3), subImgSize=(650, 650), legends=legends, returnPNG=False, drawOptions=draw_opts)
        img.save(os.path.join(output_dir, f"Final_Top_{top_n}_Predicted_PROTACs.png"))

# =============================================================================
# 5. OPEN-ADMET AI PROFILER (ENVIRONMENT SCRUBBER BRIDGE)
# =============================================================================
def run_admet_ai(df, output_dir, config_dict, top_n=20):
    logger.info(f"🧪 --- Running ADMET-AI Profiling on Top {top_n} Candidates --- 🧪")
    if 'Predicted_DC50_nM' not in df.columns:
        logger.warning("Skipping ADMET AI: Predictions not found.")
        return None

    top_df = df.sort_values(by=['Predicted_DC50_nM', 'Predicted_DMax_%'], ascending=[True, False]).head(top_n).copy()
    top_df = pd.concat([top_df.reset_index(drop=True), pd.DataFrame(top_df['SMILES'].apply(calculate_adme_properties).tolist())], axis=1)
    
    input_csv = os.path.join(output_dir, "temp_admet_input.csv")
    output_csv = os.path.join(output_dir, f"ADMET_Predictions_Top_{top_n}.csv")
    script_path = os.path.join(output_dir, "run_admet_external.py")
    top_df.to_csv(input_csv, index=False)
    
    external_script = f"""import os
import pandas as pd
from admet_ai import ADMETModel
model = ADMETModel()
df = pd.read_csv('{input_csv}')
preds_df = model.predict(smiles=df['SMILES'].tolist())
pd.concat([df.reset_index(drop=True), preds_df.reset_index(drop=True)], axis=1).to_csv('{output_csv}', index=False)
"""
    with open(script_path, "w") as f: f.write(external_script)
        
    admet_env_path = os.path.dirname(os.path.dirname(config_dict["admet_env_python"]))
    clean_env = _get_scrubbed_env(admet_env_path)
    
    try:
        subprocess.run(f"{config_dict['admet_env_python']} {script_path}", shell=True, check=True, env=clean_env)
        if os.path.exists(output_csv):
            result_df = pd.read_csv(output_csv)
            for f in [input_csv, script_path]: 
                if os.path.exists(f): os.remove(f)
            logger.info("✅ ADMET Profiling Successful.")
            return result_df
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ ADMET-AI bridge failed: {e}")
    return None

# =============================================================================
# 6. LINK-INVENT GENERATIVE ENGINE
# =============================================================================
def run_link_invent(pair_string, config_dict, job_id="latest"):
    logger.info(f"[ Link-INVENT ] Processing pair constraints for: {pair_string} (Job: {job_id})")
    custom_env = os.environ.copy()
    custom_env["PYTHONPATH"] = f"{config_dict['reinvent_dir']}:{custom_env.get('PYTHONPATH', '')}"

    output_dir = os.path.join(config_dict["output_dir"], "Design_Runs", job_id, "link_invent_results")
    os.makedirs(output_dir, exist_ok=True)

    configuration = {
        "version": 3, "model_type": "link_invent", "run_type": "reinforcement_learning",
        "logging": { "sender": "", "recipient": "local", "logging_path": os.path.join(output_dir, "progress.log"), "result_folder": os.path.join(output_dir, "results"), "job_name": "SynGlue_Constrained_Run", "job_id": "N/A" },
        "parameters": {
            "actor": config_dict["linkinvent_prior"], "critic": config_dict["linkinvent_prior"], "warheads": [pair_string], "n_steps": config_dict["n_steps"], "learning_rate": 0.0001, "batch_size": config_dict["batch_size"], "randomize_warheads": True,
            "learning_strategy": {"name": "dap", "parameters": {"sigma": 120}},
            "scoring_strategy": {
                "name": "link_invent", "diversity_filter": {"bucket_size": 25, "minscore": 0, "minsimilarity": 0, "name": "IdenticalMurckoScaffold"},
                "scoring_function": {
                    "name": "custom_product", "parallel": False, "parameters": [
                        {"name": "LGL", "weight": 2, "component_type": "linker_graph_length", "specific_parameters": {"transformation": {"high": 12, "low": 4, "transformation_type": "reverse_sigmoid", "k": 0.5}}},
                        {"name": "LEL", "weight": 2, "component_type": "linker_effective_length", "specific_parameters": {"transformation": {"high": 8, "low": 4, "transformation_type": "reverse_sigmoid", "k": 0.5}}},
                        {"name": "Flex", "weight": 2, "component_type": "num_rotatable_bonds", "specific_parameters": {"transformation": {"high": 12, "low": 0, "transformation_type": "reverse_sigmoid", "k": 0.5}}},
                        {"name": "HBD", "weight": 1, "component_type": "linker_num_hbd", "specific_parameters": {"transformation": {"high": 6, "low": 0, "transformation_type": "reverse_sigmoid", "k": 0.15}}},
                        {"name": "MW", "weight": 2, "component_type": "molecular_weight", "specific_parameters": {"transformation": {"high": 1000, "low": 700, "transformation_type": "reverse_sigmoid", "k": 0.01}}},
                        {"name": "TPSA", "weight": 2, "component_type": "tpsa", "specific_parameters": {"transformation": {"high": 230, "low": 0, "transformation_type": "reverse_sigmoid", "k": 0.1}}}
                    ]
                }
            }
        }
    }

    config_json_path = os.path.join(output_dir, "LinkINVENT_Configuration.json")
    with open(config_json_path, 'w') as f: json.dump(configuration, f, indent=4)

    try:
        process = subprocess.Popen([REINVENT_PYTHON, os.path.join(config_dict['reinvent_dir'], "input.py"), config_json_path], env=custom_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout: print(line.strip(), flush=True)
        process.wait()

        if process.returncode == 0:
            scaffold_path = os.path.join(output_dir, 'results/scaffold_memory.csv')
            if os.path.exists(scaffold_path):
                df_res = pd.read_csv(scaffold_path)
                logger.info(f"✅ Success! {len(df_res)} tightly constrained PROTACs generated.")
                return df_res, output_dir
    except Exception as e: logger.error(f"❌ Subprocess execution failed: {e}")
    return None, None

# =============================================================================
# 7. PHASE 3 PREDICTION ENGINE (GROVER + PYTORCH)
# =============================================================================
class MultiTaskProtacModel(nn.Module):
    def __init__(self, input_dim=4800, hidden_dim=512, n_heads=4):
        super().__init__()
        self.proj = nn.Linear(input_dim, hidden_dim)
        encoder_layer = nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=n_heads, batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
        self.attn_pool = nn.Linear(hidden_dim, 1)
        self.head_dc50 = nn.Sequential(nn.Linear(hidden_dim, 256), nn.ReLU(), nn.Dropout(0.2), nn.Linear(256, 1))
        self.head_dmax = nn.Sequential(nn.Linear(hidden_dim, 256), nn.ReLU(), nn.Dropout(0.2), nn.Linear(256, 1))

    def forward(self, x):
        h = self.transformer(self.proj(x))           
        attn_weights = torch.softmax(self.attn_pool(h), dim=1)
        fused = (h * attn_weights).sum(dim=1) 
        return self.head_dc50(fused), self.head_dmax(fused), attn_weights

def run_ai_predictions(df_candidates, output_dir, config_dict):
    logger.info("🚀 INITIATING PHASE 3: DC50 & DMax PREDICTION PIPELINE...")
    
    smiles_file = os.path.join(output_dir, "temp_candidates.csv")
    features_file = os.path.join(output_dir, "temp_features.npz")
    fingerprint_file = os.path.join(output_dir, "temp_fingerprints.npz")
    
    df_candidates[['SMILES']].rename(columns={'SMILES': 'smiles'}).to_csv(smiles_file, index=False)
    
    # GROVER runs in the Magnet environment, just needs PYTHONPATH updated
    grover_env = os.environ.copy()
    grover_env['MPLBACKEND'] = 'Agg'
    grover_env['PYTHONPATH'] = f"{config_dict['grover_dir']}:{grover_env.get('PYTHONPATH', '')}"
    
    logger.info("⏳ Extracting GROVER Features... (Step 1/2)")
    try:
        subprocess.run(
            f"{MAGNET_PYTHON} {config_dict['grover_dir']}/scripts/save_features.py --data_path {smiles_file} "
            f"--save_path {features_file} --features_generator rdkit_2d_normalized --restart", 
            shell=True, check=True, env=grover_env, capture_output=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"GROVER Features failed: {e.stderr.decode()[-1000:]}")
        return df_candidates
    
    logger.info("⏳ Running GROVER Deep Learning Model... (Step 2/2)")
    try:
        subprocess.run(
            f"{MAGNET_PYTHON} {config_dict['grover_dir']}/main.py fingerprint --data_path {smiles_file} "
            f"--features_path {features_file} --checkpoint_path {config_dict['grover_checkpoint']} "
            f"--fingerprint_source both --output {fingerprint_file}", 
            shell=True, check=True, env=grover_env, capture_output=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"GROVER Fingerprints failed: {e.stderr.decode()[-1000:]}")
        return df_candidates
    
    try:
        new_fingerprints = np.load(fingerprint_file)['fps'][:, :4800]
        warhead_df = pd.read_csv(config_dict['warhead_csv'], low_memory=False)
        e3_df = pd.read_csv(config_dict['e3_csv'], low_memory=False)
        
        w_cols = [c for c in warhead_df.columns if c.startswith("Grover_")]
        e_cols = [c for c in e3_df.columns if c.startswith("Grover_")]
        
        c_wh = warhead_df[w_cols].iloc[0].values.astype(np.float32)
        c_e3 = e3_df[e_cols].iloc[0].values.astype(np.float32)
        
        num_cands = new_fingerprints.shape[0]
        X_new = np.zeros((num_cands, 3, 4800), dtype=np.float32)
        
        logger.info("⏳ Building Neural Tensor...")
        for i in tqdm(range(num_cands), desc="Assembling 3D Tensors"):
            X_new[i, 0, :], X_new[i, 1, :], X_new[i, 2, :] = c_wh, new_fingerprints[i, :], c_e3
            
        logger.info("🎯 Scoring Candidates with PyTorch and Random Forest...")
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        model = MultiTaskProtacModel(input_dim=4800).to(device)
        model.load_state_dict(torch.load(config_dict['pt_model'], map_location=device, weights_only=True))
        model.eval()
        
        X_tensor = torch.tensor(X_new, dtype=torch.float32).to(device)
        with torch.no_grad():
            h = model.transformer(model.proj(X_tensor))
            Z_new = (h * torch.softmax(model.attn_pool(h), dim=1)).sum(dim=1).cpu().numpy()

        df_candidates['Predicted_DC50_nM'] = 10 ** joblib.load(config_dict['rf_dc50_model']).predict(Z_new)
        df_candidates['Predicted_DMax_%'] = joblib.load(config_dict['rf_dmax_model']).predict(Z_new)
        
        for f in [smiles_file, features_file, fingerprint_file]:
            if os.path.exists(f): os.remove(f)
            
        df_candidates.to_csv(os.path.join(output_dir, "Final_Predicted_PROTACs.csv"), index=False)
    except Exception as e:
        logger.error(f"Prediction Pipeline Failed: {e}")
        
    return df_candidates

# =============================================================================
# 8. SYNGLUE PRIORITIZER ENGINE
# =============================================================================
class SynGlueSelector:
    def __init__(self, e3_df):
        self.e3_df = e3_df.copy()
        self.archetypes = {
            'A_Workhorse': ['CRBN', 'VHL', 'DCAF1'],
            'B_GreaseSink': ['cIAP1', 'cIAP2', 'XIAP', 'IAP', 'MDM2'],
            'C_Covalent': ['RNF4', 'RNF114', 'KEAP1', 'FEM1B', 'DCAF16', 'DCAF11'],
            'D_Planar': ['AhR', 'DCAF15', 'FBXO22', 'KLHL20', 'UBR box', 'KLHDC2']
        }
        for col in ['Molecular Weight', 'Topological Polar Surface Area', 'IC50 (nM)', 'Kd (nM)']:
            if col in self.e3_df.columns:
                self.e3_df[col] = pd.to_numeric(self.e3_df[col], errors='coerce')

    def _windowed_d(self, val, lower, upper, penalty):
        if val < lower: return math.exp(-penalty * ((lower - val) ** 2))
        elif val > upper: return math.exp(-penalty * ((val - upper) ** 2))
        return 1.0

    def score_warheads(self, fragments_df):
        scored_fragments = []
        for idx, row in tqdm(fragments_df.iterrows(), total=len(fragments_df), desc="Scoring Warheads"):
            frag_smiles = row.get('query_frag_smile', row.get('fragment', ''))
            mol = Chem.MolFromSmiles(frag_smiles)
            if not mol: continue
            adme = calculate_adme_properties(frag_smiles)
            w_mpo = (self._windowed_d(adme['MW'], 140, 300, 0.0001) * self._windowed_d(adme['logP'], 1.0, 3.0, 0.5) * self._windowed_d(adme['TPSA'], 0, 60, 0.001)) ** 0.33
            
            row_data = row.to_dict()
            row_data.update({'W_MPO_Score': w_mpo, 'ADME': adme})
            scored_fragments.append(row_data)
        
        scored_fragments.sort(key=lambda x: x['W_MPO_Score'], reverse=True)
        return scored_fragments

    def score_e3s(self, archetype_key):
        valid_targets = self.archetypes.get(archetype_key, [])
        filtered_e3 = self.e3_df[self.e3_df['Target'].isin(valid_targets)].copy()
        scored_e3s = []
        for idx, row in tqdm(filtered_e3.iterrows(), total=len(filtered_e3), desc=f"Scoring E3s ({archetype_key})", leave=False):
            mol = Chem.MolFromSmiles(row['Smiles'])
            if not mol: continue
            adme = calculate_adme_properties(row['Smiles'])
            d_mw = self._windowed_d(adme['MW'], 250, 500, 0.001)
            d_tpsa = self._windowed_d(adme['TPSA'], 50, 120, 0.001)
            affinity = row.get('Kd (nM)') if pd.notna(row.get('Kd (nM)')) else row.get('IC50 (nM)')
            d_aff = 0.1 if pd.isna(affinity) or affinity <= 0 else (1.0 if affinity <= 100.0 else math.exp(-0.000001 * ((affinity - 100.0) ** 2)))
            e3_score = (d_mw * d_tpsa * d_aff) ** (1/3)
            row_data = row.to_dict()
            row_data.update({'D_E3_Score': e3_score, 'ADME': adme})
            scored_e3s.append(row_data)
            
        scored_e3s.sort(key=lambda x: x['D_E3_Score'], reverse=True)
        return scored_e3s

    def generate_e3_exit_vector(self, smiles):
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return smiles
        pattern = Chem.MolFromSmarts('[$([NH2]),$([NH1]),$([OH]),$([CX3](=O)[OX2H1]),$([c][F,Cl,Br,I])]')
        matches = [m[0] for m in mol.GetSubstructMatches(pattern)]
        if not matches: return smiles 
        
        dist_matrix = Chem.GetDistanceMatrix(mol)
        centroid = np.argmin(dist_matrix.sum(axis=0))
        best_idx = max(matches, key=lambda idx: dist_matrix[centroid][idx])
        rw_mol = Chem.RWMol(mol)
        dummy_idx = rw_mol.AddAtom(Chem.Atom(0)) 
        rw_mol.AddBond(best_idx, dummy_idx, Chem.BondType.SINGLE)
        try:
            Chem.SanitizeMol(rw_mol)
            return Chem.MolToSmiles(rw_mol)
        except Exception: return smiles

    def run_selection(self, target_protein, fragments_df):
        logger.info(f"--- Running SynGlue Database Selection for Target: {target_protein} ---")
        scored_fragments = self.score_warheads(fragments_df)
        if not scored_fragments: return {"Error": "Failed to score warheads."}
        
        best_wh = scored_fragments[0]
        archetype = 'D_Planar' if best_wh['ADME']['Flexibility'] < 2 else 'A_Workhorse' 
        potential_e3s = self.score_e3s(archetype)
        best_e3 = potential_e3s[0]
        tagged_e3_smiles = self.generate_e3_exit_vector(best_e3['Smiles'])
        frag_smile = best_wh.get('query_frag_smile', best_wh.get('fragment', ''))

        return {
            "Warhead_SMILES": frag_smile, 
            "E3_Tagged_SMILES": tagged_e3_smiles,
        }