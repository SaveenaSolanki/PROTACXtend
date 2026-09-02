#!/usr/bin/env python3
"""Comprehensive PROTAC design: docking → DC50 → E3 selection → PROTAC design for top HMGB2 warheads."""

import sys, os, csv, logging
sys.path.insert(0, '/storage/saveena/protacpilot')
for mod in list(sys.modules.keys()):
    if 'synglue' in mod or 'docking' in mod:
        del sys.modules[mod]
logging.basicConfig(level=logging.INFO, format='%(message)s')

from protacxtend.tools.docking_pipeline import prepare_receptor_for_docking, dock_and_prepare_for_p4ward
from protacxtend.tools.admet_integration import protac_admet_summary
from protacxtend.tools.synglue_integration import SynGlueAPIClient

WORK_DIR = "/storage/saveena/protacpilot/work/protac_design"
RECEPTOR_PDB = "/storage/saveena/protacpilot/pdb/hmgb2_full.pdb"
os.makedirs(WORK_DIR, exist_ok=True)

CANDIDATES = [
    {"name": "Hoechst 33258", "smiles": "CCN1CCN(CC1)C2=CC3=C(C=C2)C(=NN3)C4=CC5=C(C=C4)N=C(N5)C6=CC(=C(C=C6)O)OC", "e3": "CRBN"},
    {"name": "PDS (Pyridostatin)", "smiles": "CC1=CC=C(C=C1)C2=NC3=C(N2)C=C(C=C3)C4=NC5=C(N4)C=C(C=C5)N", "e3": "CRBN"},
]

E3_LIGANDS = {
    "CRBN": {"pdb": "/storage/saveena/protacpilot/pdb/rcsb/4CI3.pdb", "nuclear": 1.0,
        "ligands": [("Pomalidomide","NC1=CC=CC2=C1C(=O)N(C1CCC(=O)NC1=O)C2=O",157),
                    ("Lenalidomide","NC1=CC=CC2=C1CN(C1CCC(=O)NC1=O)C2=O",178)]},
    "VHL": {"pdb": "/storage/saveena/protacpilot/pdb/rcsb/4W9H.pdb", "nuclear": 0.2,
        "ligands": [("VH032","CC(=O)N[C@H](C(=O)N1C[C@H](O)C[C@H]1C(=O)NCC1=CC=C(C2=C(C)N=CS2)C=C1)C(C)(C)C",185),
                    ("AHPC","CC(C)[C@H](NC(=O)C1=CC=C([*:1])C=C1)C(=O)N2CCC[C@H]2O",300)]},
}

LINKERS = [("PEG4","[*:1]CCOCCOCCOCC[*:2]",11.2),("PEG6","[*:1]CCOCCOCCOCCOCCOCC[*:2]",16.8),
           ("PEG8","[*:1]CCOCCOCCOCCOCCOCCOCCOCC[*:2]",22.4),("C10-alkyl","[*:1]CCCCCCCCCC[*:2]",10.5),
           ("C12-alkyl","[*:1]CCCCCCCCCCCC[*:2]",12.6),("C6-PEG4","[*:1]CCCCCCOCCOCCOCCOCC[*:2]",15.0),
           ("C8-PEG4","[*:1]CCCCCCCCOCCOCCOCCOCC[*:2]",17.2)]

print("="*70)
print("  PROTAC DESIGN: HMGB2 TARGETED DEGRADATION")
print("="*70)

# E3 selection with subcellular logic
print("\n--- E3 LIGASE SELECTION (Target:nuclear) ---")
for e3, info in E3_LIGANDS.items():
    score = info["nuclear"] * 0.5 + 0.3 + 0.2  # colocalization + ligand + prior
    print(f"  {e3:<8} nuclear_access={info['nuclear']:.1f}  →  composite={score:.2f}")
best_e3 = max(E3_LIGANDS, key=lambda k: E3_LIGANDS[k]["nuclear"] * 0.5 + 0.5)
print(f"  🏆 Recommended: {best_e3}")

# Dock warheads
rec = prepare_receptor_for_docking(RECEPTOR_PDB, os.path.join(WORK_DIR,"receptor"), remove_water=True)
results = []
for c in CANDIDATES:
    print(f"\n{'='*60}\n  {c['name']}\n{'='*60}")
    d = dock_and_prepare_for_p4ward(receptor_pdb=RECEPTOR_PDB, warhead_smiles=c["smiles"],
        e3_name=c["e3"], protac_smiles_list=[c["smiles"]],
        output_dir=os.path.join(WORK_DIR, c["name"].replace(" ","_")), fast=True)
    dr = d.get("docking_result",{})
    if dr.get("status")!="completed":
        print(f"  ❌ {dr.get('error')}"); continue
    bp = dr.get("best_pose"); ev = dr.get("exit_vector")
    print(f"  ✅ Affinity: {bp.affinity_kcal_mol:.2f} kcal/mol")
    adm = protac_admet_summary(c["smiles"], c["name"])
    r = {"name":c["name"],"smiles":c["smiles"],"affinity":bp.affinity_kcal_mol,
         "admet":adm,"dc50":None,"dmax":None}
    if ev:
        r["exit_vector"] = {"atom":ev.atom_index,"elem":ev.atom_symbol,
            "solvent":round(ev.solvent_accessibility,3),"dist":round(ev.distance_to_protein_surface,2)}
        print(f"  ✅ Exit vector: atom {ev.atom_index}({ev.atom_symbol}) solv={ev.solvent_accessibility:.3f}")
    results.append(r)

# DC50/Dmax prediction
if results:
    try:
        client = SynGlueAPIClient("http://localhost:8000")
        if client.health_check().get("status")=="online":
            preds = client.predict_dc50_dmax([r["smiles"] for r in results])
            for i,r in enumerate(results):
                if i<len(preds) and preds[i].get("dc50_nM"):
                    r["dc50"]=preds[i]["dc50_nM"]; r["dmax"]=preds[i]["dmax_pct"]
                    print(f"  ✅ {r['name']}: DC50={r['dc50']}nM Dmax={r['dmax']}%")
    except Exception as e:
        print(f"  ⚠️ API: {e}")

# Design PROTACs
print(f"\n{'='*60}\n  PROTAC DESIGNS\n{'='*60}")
all_designs = []
for r in results:
    ev_dist = r.get("exit_vector",{}).get("dist",6.0)
    req_len = ev_dist + 5.0 + 8.0
    print(f"\n  {r['name']}: EV dist={ev_dist:.1f}Å, required linker≈{req_len:.0f}Å")
    for e3_name in ["CRBN","VHL"]:
        e3i = E3_LIGANDS.get(e3_name)
        if not e3i: continue
        for lig_name, lig_smi, eff_len in LINKERS:
            if eff_len < req_len*0.7: continue
            for e3_lig_name, e3_lig_smi, e3_kd in e3i["ligands"][:2]:
                protac = f"{r['smiles']}{lig_smi.replace('[*:1]','').replace('[*:2]','')}{e3_lig_smi}"
                suff = eff_len >= req_len*0.8
                all_designs.append({"warhead":r["name"],"linker":lig_name,
                    "len_angstrom":eff_len,"e3":e3_name,"e3_ligand":e3_lig_name,
                    "sufficient":suff,"protac_smi":protac[:60]+"..."})

# Report
csv_path = os.path.join(WORK_DIR,"protac_designs.csv")
with open(csv_path,'w',newline='') as f:
    w = csv.writer(f)
    w.writerow(["Warhead","Linker","Len(Å)","E3","Ligand","Sufficient"])
    for d in all_designs:
        w.writerow([d["warhead"],d["linker"],d["len_angstrom"],d["e3"],d["e3_ligand"],d["sufficient"]])

print(f"\n{'='*60}\n  RECOMMENDED PROTACs\n{'='*60}")
print(f"  {'Warhead':<22} {'Linker':<12} {'E3':<8} {'Ligand':<16} {'Len':>4}")
print(f"  {'-'*66}")
seen=set()
for d in all_designs:
    if d["sufficient"] and d["warhead"] not in seen:
        print(f"  {d['warhead']:<22} {d['linker']:<12} {d['e3']:<8} {d['e3_ligand']:<16} {d['len_angstrom']:>4.0f}Å ✅")
        seen.add(d["warhead"])

print(f"\n  📊 WARHEAD COMPARISON:")
print(f"  {'Warhead':<22} {'Affinity':>8} {'EV':>6} {'DC50':>8} {'Dmax':>6} {'Perm'}")
print(f"  {'-'*66}")
for r in results:
    dc = f"{r.get('dc50','N/A')}nM" if r.get('dc50') else "N/A"
    dm = f"{r.get('dmax','N/A')}%" if r.get('dmax') else "N/A"
    ev_s = r.get("exit_vector",{}).get("solvent","N/A")
    print(f"  {r['name']:<22} {r.get('affinity','N/A'):>8} {str(ev_s):>6} {dc:>8} {dm:>6} {r.get('admet',{}).get('PROTAC_permeability','N/A')}")

print(f"\n✅ {csv_path}")
