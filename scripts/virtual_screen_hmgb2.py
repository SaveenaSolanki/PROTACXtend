#!/usr/bin/env python3
"""Virtual screen: dock all warheads against HMGB2 and rank by affinity + exit vector quality."""

import sys, os, csv, json, time, logging
sys.path.insert(0, '/storage/saveena/protacpilot')
for mod in list(sys.modules.keys()):
    if 'synglue' in mod or 'docking' in mod:
        del sys.modules[mod]

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')
logger = logging.getLogger('virtual_screen')

from synglue_agent.tools.docking_pipeline import (
    prepare_receptor_for_docking,
    prepare_warhead_for_docking,
    run_vina_docking,
    analyze_exit_vectors,
)

# --- Config ---
RECEPTOR_PDB = "/storage/saveena/protacpilot/pdb/hmgb2_full.pdb"
OUTPUT_DIR = "/storage/saveena/protacpilot/work/virtual_screen"
LIBRARY_CSV = "/storage/saveena/protacpilot/data/warheads/hmgb2_warhead_library.csv"
RESULTS_CSV = os.path.join(OUTPUT_DIR, "hmgb2_virtual_screen_results.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Prepare receptor once ---
print("=" * 70)
print("HMGB2 VIRTUAL SCREEN — Docking 15 warheads")
print("=" * 70)

rec = prepare_receptor_for_docking(
    RECEPTOR_PDB,
    os.path.join(OUTPUT_DIR, "receptor_prep"),
    remove_water=True, add_hydrogens=False,
)
if not rec.get("success"):
    raise RuntimeError(f"Receptor prep failed: {rec.get('error')}")

print(f"\nReceptor: {os.path.basename(rec['pdb_file'])} ({os.path.getsize(rec['pdb_file'])} bytes)")
print(f"Docking box: auto-center on receptor (30 Å cube)")

# --- Read warhead library ---
warheads = []
with open(LIBRARY_CSV) as f:
    reader = csv.DictReader(f)
    for row in reader:
        warheads.append(row)

print(f"\nWarheads to dock: {len(warheads)}")
print("-" * 70)

# --- Dock each warhead ---
results = []
for i, wh in enumerate(warheads):
    name = wh['name']
    smiles = wh['smiles']
    wh_class = wh['class']
    
    print(f"\n[{i+1}/{len(warheads)}] {name} ({wh_class})")
    
    try:
        # 1. Prep warhead
        war_result = prepare_warhead_for_docking(
            smiles, os.path.join(OUTPUT_DIR, "warheads", name.replace("/", "_")),
        )
        if not war_result.get("success"):
            print(f"  ❌ Warhead prep failed: {war_result.get('error')}")
            results.append({
                "name": name, "smiles": smiles, "class": wh_class,
                "affinity_kcal_mol": "", "num_poses": 0,
                "exit_vector_atom": "", "exit_vector_element": "",
                "solvent_accessibility": "", "distance_to_surface": "",
                "status": "failed_warhead_prep", "error": war_result.get("error", ""),
            })
            continue
        
        # 2. Dock (fast mode)
        t0 = time.time()
        vina = run_vina_docking(
            receptor_pdbqt=rec['pdb_file'],
            warhead_pdbqt=war_result['pdbqt_file'],
            output_dir=os.path.join(OUTPUT_DIR, "docking", name.replace("/", "_")),
            center_x=0, center_y=0, center_z=0,
            size_x=30, size_y=30, size_z=30,
            exhaustiveness=4, num_modes=5, cpu=4,
        )
        t1 = time.time()
        
        if not vina.get("success") or not vina.get("poses"):
            print(f"  ⚠️  No poses: {vina.get('error', 'unknown')}")
            results.append({
                "name": name, "smiles": smiles, "class": wh_class,
                "affinity_kcal_mol": "", "num_poses": 0,
                "exit_vector_atom": "", "exit_vector_element": "",
                "solvent_accessibility": "", "distance_to_surface": "",
                "status": "no_poses", "error": vina.get("error", ""),
            })
            continue
        
        # 3. Analyze best pose
        best_pose = vina['poses'][0]
        ev = analyze_exit_vectors(
            best_pose, smiles, rec['pdb_file'],
        )
        
        ev_atom = ev.atom_index if ev else ""
        ev_elem = ev.atom_symbol if ev else ""
        ev_solv = f"{ev.solvent_accessibility:.3f}" if ev else ""
        ev_dist = f"{ev.distance_to_protein_surface:.2f}" if ev else ""
        
        # 4. Compute composite score
        # Weight: 60% binding affinity + 40% exit vector quality
        aff_score = max(0, min(1, (best_pose.affinity_kcal_mol + 12) / 10)) if best_pose.affinity_kcal_mol < 0 else 0
        ev_score = ev.solvent_accessibility if ev else 0
        composite = 0.6 * aff_score + 0.4 * ev_score
        
        print(f"  ✅ {len(vina['poses'])} poses | best={best_pose.affinity_kcal_mol:.2f} kcal/mol | "
              f"EV={ev_elem}{ev_atom} solv={ev_solv} | composite={composite:.3f}")
        
        results.append({
            "name": name, "smiles": smiles, "class": wh_class,
            "affinity_kcal_mol": f"{best_pose.affinity_kcal_mol:.2f}",
            "num_poses": len(vina['poses']),
            "exit_vector_atom": ev_atom,
            "exit_vector_element": ev_elem,
            "solvent_accessibility": ev_solv,
            "distance_to_surface": ev_dist,
            "status": "completed",
            "error": "",
            "composite_score": f"{composite:.3f}",
            "runtime_s": f"{t1-t0:.1f}",
        })
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "name": name, "smiles": smiles, "class": wh_class,
            "affinity_kcal_mol": "", "num_poses": 0,
            "exit_vector_atom": "", "exit_vector_element": "",
            "solvent_accessibility": "", "distance_to_surface": "",
            "status": "error", "error": str(e),
        })

# --- Sort by composite score ---
results.sort(key=lambda r: float(r.get('composite_score', 0) or 0), reverse=True)

# --- Write results ---
with open(RESULTS_CSV, 'w', newline='') as f:
    fieldnames = ["rank", "name", "class", "affinity_kcal_mol", "composite_score",
                  "num_poses", "exit_vector_element", "exit_vector_atom",
                  "solvent_accessibility", "distance_to_surface", "status"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for i, r in enumerate(results):
        r["rank"] = i + 1
        writer.writerow({k: r.get(k, "") for k in fieldnames})

# --- Print ranking ---
print("\n" + "=" * 70)
print("RANKING")
print("=" * 70)
print(f"{'Rank':>4} {'Name':<25} {'Class':<22} {'Affinity':>8} {'EV Solv':>7} {'Comp':>5}")
print("-" * 70)
for i, r in enumerate(results[:10]):
    aff = r.get('affinity_kcal_mol', '')
    solv = r.get('solvent_accessibility', '')
    comp = r.get('composite_score', '')
    name = r['name'][:25]
    cl = r['class'][:22]
    print(f"{i+1:>4} {name:<25} {cl:<22} {aff:>8} {solv:>7} {comp:>5}")

# --- Print worst performers ---
print("\n" + "-" * 70)
print("BOTTOM OF RANKING")
for i, r in enumerate(results[-3:]):
    print(f"  {r['name']:<30} {r['affinity_kcal_mol']:>8} kcal/mol | {r.get('status', '')}")

print(f"\n✅ Results saved to {RESULTS_CSV}")
print(f"   {len(results)} warheads screened")
