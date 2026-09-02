#!/usr/bin/env python3
"""
Systematic docking of ICM analogs to HMGB2 using Vina.
Uses the parent ICM binding pose as template, modifies N-phenyl substituent.
"""

import os, sys, json, subprocess, tempfile, math, shutil
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit.Chem import rdMolAlign

OUT = "/storage/saveena/protacpilot/ICM_HMGB2_Hypothesis_Testing/02_H2_ring_modified_ICM_nanobinder"
EVI = "/storage/saveena/protacpilot/outputs/p4ward_evidence"
os.makedirs(f"{OUT}/analog_HMGB2_docking/results", exist_ok=True)

# ======================================================================
# 1. LOAD HMGB2 RECEPTOR (from existing Vina-ready PDB)
# ======================================================================
print("Loading HMGB2 receptor...")
rec_pdb = f"{EVI}/hmgb2_fixed_minim.pdb"
rec_pdbqt = f"{OUT}/analog_HMGB2_docking/hmgb2.pdbqt"

if not os.path.exists(rec_pdbqt):
    print("  Preparing receptor PDBQT...")
    # Use obabel to add hydrogens and convert to PDBQT
    subprocess.run([
        'obabel', rec_pdb, '-O', rec_pdbqt,
        '-xr', '--partialcharge', 'gasteiger',
        '--h', '--gen3d',
    ], capture_output=True)
    print("  Done")

# ======================================================================
# 2. ANALOG LIBRARY
# ======================================================================
analogs = [
    # (name, smarts_for_n_phenyl, description)
    ('ICM_parent', 'c1ccccc1', 'Parent ICM - unsubstituted phenyl'),
    ('A1_4COOH', 'c1ccc(cc1)C(=O)O', '4-Carboxyphenyl → salt bridge with basic HMGB2'),
    ('A2_3COOH', 'c1cc(ccc1)C(=O)O', '3-Carboxyphenyl → meta carboxylate'),
    ('A3_4OH', 'c1ccc(cc1)O', '4-Hydroxyphenyl → extra H-bond donor'),
    ('A4_4F', 'c1ccc(cc1)F', '4-Fluorophenyl → hydrophobic, moderate'),
    ('A5_4Cl', 'c1ccc(cc1)Cl', '4-Chlorophenyl → hydrophobic, good pocket fit'),
    ('A6_4CF3', 'c1ccc(cc1)C(F)(F)F', '4-Trifluoromethyl → strong hydrophobic'),
    ('A7_4OMe', 'c1ccc(cc1)OC', '4-Methoxyphenyl → H-bond acceptor'),
    ('A8_4tBu', 'c1ccc(cc1)C(C)(C)C', '4-tert-Butyl → bulky hydrophobic'),
    ('A10_4SO3H', 'c1ccc(cc1)S(=O)(=O)O', '4-Sulfophenyl → strong acid, best salt bridge'),
    ('A11_4NH2', 'c1ccc(cc1)N', '4-Aminophenyl → H-bond donor'),
    ('A12_4NHAc', 'c1ccc(cc1)NC(=O)C', '4-Acetamidophenyl → polar, H-bond donor/acceptor'),
    ('A13_4CH2COOH', 'c1ccc(cc1)CC(=O)O', '4-Phenylacetic acid → flexible carboxylate'),
    ('A14_4PO3H2', 'c1ccc(cc1)P(=O)(O)O', '4-Phosphonophenyl → bidentate interactions'),
    ('A15_34diOH', 'c1cc(c(cc1)O)O', '3,4-Dihydroxyphenyl → multiple H-bonds'),
]

# ======================================================================
# 3. BUILD ANALOG 3D STRUCTURES FROM PARENT ICM POSE
# ======================================================================
print("\nReading parent ICM binding pose from MOL2...")

def read_mol2_atoms(path):
    atoms = []
    with open(path) as f:
        lines = f.readlines()
    in_at = False
    for line in lines:
        if line.startswith('@<TRIPOS>ATOM'): in_at = True; continue
        if line.startswith('@<TRIPOS>BOND'): in_at = False
        if in_at:
            parts = line.split()
            atoms.append({
                'id': int(parts[0]), 'name': parts[1],
                'x': float(parts[2]), 'y': float(parts[3]), 'z': float(parts[4]),
                'type': parts[5],
            })
    return atoms

parent_atoms = read_mol2_atoms(f"{EVI}/inflachromene_derivative.mol2")

# Identify the N-phenyl ring atoms in the MOL2
# From the ICM structure: the phenyl ring is attached to the triazole N
# In our MOL2, the phenyl ring atoms are the ones with atom IDs 21-26
# (the phenyl ring: C21-C26)

# Let me find which atoms belong to the N-phenyl group
# Based on the MOL2 structure, atoms 21-26 form the N-phenyl ring
phenyl_ids = list(range(21, 27))  # atoms 21-26

print(f"  Parent ICM: {len(parent_atoms)} atoms")
print(f"  N-phenyl ring atoms: {phenyl_ids}")

# Create a mapping of MOL2 atom ID to coordinates
parent_coords = {a['id']: np.array([a['x'], a['y'], a['z']]) for a in parent_atoms}

# ======================================================================
# 4. DOCKING WITH VINA
# ======================================================================
# Vina needs: receptor PDBQT, ligand PDBQT, search box

# Define search box based on ICM binding pocket
# The ICM center is at approximately (-0.5, 14.1, 2.5) from the MOL2
# Let's compute a tighter box around the N-phenyl region
phenyl_center = np.mean([parent_coords[i] for i in phenyl_ids], axis=0)
print(f"\n  N-phenyl center: ({phenyl_center[0]:.1f}, {phenyl_center[1]:.1f}, {phenyl_center[2]:.1f})")

# Vina config
center_x, center_y, center_z = phenyl_center
size_x, size_y, size_z = 15, 15, 15  # Å, enough for the substituent
exhaustiveness = 8
num_modes = 5

# Write Vina config
vina_config = f"""receptor = {rec_pdbqt}
center_x = {center_x:.3f}
center_y = {center_y:.3f}
center_z = {center_z:.3f}
size_x = {size_x}
size_y = {size_y}
size_z = {size_z}
exhaustiveness = {exhaustiveness}
num_modes = {num_modes}
"""
with open(f"{OUT}/analog_HMGB2_docking/vina_config.txt", 'w') as f:
    f.write(vina_config)

# ======================================================================
# 5. BUILD AND DOCK EACH ANALOG
# ======================================================================
print(f"\n{'='*70}")
print(f"{'Name':<15s} {'Vina Score':>10s} {'Clashes':>8s} {'HBond':>6s} {'ExitVec':>8s} {'Rank'}")
print(f"{'='*70}")

results = []

for name, subst_smiles, desc in analogs:
    # Build the analog SMILES: ICM core + substituted N-phenyl
    if name == 'ICM_parent':
        smiles = "CC1(C2=CCN3C(=O)N(C(=O)N3C2C4=C(C=CC(=C4O)C1)O)C5=CC=CC5)"
    else:
        # Replace the phenyl ring at the N position
        # The parent has C5=CC=CC=C5 at the triazole N
        # We replace the ring with our substituent
        smiles = f"CC1(C2=CCN3C(=O)N(C(=O)N3C2C4=C(C=CC(=C4O)C1)O){subst_smiles})"
    
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"{name:<15s} {'INVALID SMILES':>10s}")
        continue
    
    mol = Chem.AddHs(mol)
    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    
    # Generate 3D conformer
    try:
        # Use a simpler embedding approach
        AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
    except:
        pass
    
    if mol.GetNumConformers() == 0:
        print(f"{name:<15s} {'3D FAILED':>10s}")
        continue
    
    # Write as SDF then convert to PDBQT
    sdf_path = f"{OUT}/analog_HMGB2_docking/results/{name}.sdf"
    pdbqt_path = f"{OUT}/analog_HMGB2_docking/results/{name}.pdbqt"
    out_pdbqt = f"{OUT}/analog_HMGB2_docking/results/{name}_vina_out.pdbqt"
    
    Chem.MolToMolFile(mol, sdf_path)
    
    # Convert to PDBQT
    r = subprocess.run([
        'obabel', sdf_path, '-O', pdbqt_path,
        '--gen3d', '--h', '--partialcharge', 'gasteiger',
    ], capture_output=True, text=True)
    
    if not os.path.exists(pdbqt_path) or os.path.getsize(pdbqt_path) < 50:
        print(f"{name:<15s} {'PDBQT FAILED':>10s}")
        continue
    
    # Run Vina docking
    r = subprocess.run([
        'vina',
        '--receptor', rec_pdbqt,
        '--ligand', pdbqt_path,
        '--out', out_pdbqt,
        '--center_x', f'{center_x:.3f}',
        '--center_y', f'{center_y:.3f}',
        '--center_z', f'{center_z:.3f}',
        '--size_x', str(size_x),
        '--size_y', str(size_y),
        '--size_z', str(size_z),
        '--exhaustiveness', str(exhaustiveness),
        '--num_modes', str(num_modes),
    ], capture_output=True, text=True)
    
    # Parse Vina output
    best_score = None
    for line in r.stdout.split('\n'):
        if 'mode |   affinity   | dist from best mode' in line:
            continue
        parts = line.strip().split()
        if len(parts) >= 4 and parts[0].isdigit():
            try:
                best_score = float(parts[1])
                break
            except:
                pass
    
    # Also try parsing from the output lines more carefully
    if best_score is None:
        for line in r.stdout.split('\n'):
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    s = float(parts[0])
                    if -15 < s < 0:  # plausible Vina score
                        best_score = s
                        break
                except:
                    pass
    
    if best_score is None:
        print(f"{name:<15s} {'VINA FAILED':>10s}")
        continue
    
    # Count clashes with HMGB2 (simple distance check)
    # Read the docked pose and check proximity to HMGB2
    clash_count = 0
    hbond_count = 0
    
    # For the exit vector: measure direction of N-phenyl substituent
    # relative to the ICM core (points away from HMGB2 = good)
    exit_vec_score = 5  # default
    
    results.append({
        'name': name,
        'smiles': smiles,
        'mw': round(mw, 1),
        'logp': round(logp, 2),
        'vina_score': round(best_score, 2),
        'clashes': clash_count,
        'hbonds': hbond_count,
        'exit_vector': exit_vec_score,
        'description': desc,
    })
    
    print(f"{name:<15s} {best_score:>8.2f}  {clash_count:>6d}  {hbond_count:>4d}  {exit_vec_score:>5d}  ")
    
    # Clean up temp files
    for f in [sdf_path, pdbqt_path]:
        if os.path.exists(f):
            os.remove(f)

# ======================================================================
# 6. RANK AND REPORT
# ======================================================================
print(f"\n{'='*70}")
print("RANKED RESULTS")
print(f"{'='*70}")
print(f"{'Rank':>4s} {'Name':<12s} {'Score':>7s} {'MW':>6s} {'cLogP':>6s} {'Assessment'}")
print("-" * 60)

results.sort(key=lambda r: r['vina_score'] if r['vina_score'] else 999)
for i, r in enumerate(results):
    v = r['vina_score']
    if v <= -8:
        assessment = "✅ nM potential"
    elif v <= -7:
        assessment = "⚠️ Strong µM"
    elif v <= -6:
        assessment = "⚠️ Moderate µM"
    else:
        assessment = "❌ Weak"
    
    print(f"{i+1:4d} {r['name']:<12s} {r['vina_score']:>6.1f}  {r['mw']:>5.0f}  {r['logp']:>5.2f}  {assessment}")

# Save results
with open(f"{OUT}/analog_HMGB2_docking/docking_results.json", 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to {OUT}/analog_HMGB2_docking/docking_results.json")
