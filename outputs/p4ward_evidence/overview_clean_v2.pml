# overview_clean_v2.pml
# Clean overview figure for HMGB2-CRBN P4ward evidence.
# Run from: /storage/saveena/protacpilot/outputs/p4ward_evidence

reinitialize
bg white
set ray_opaque_background, off
set orthoscopic, on
set antialias, 2
set depth_cue, 0
set specular, 0.15
set ambient, 0.45
set cartoon_fancy_helices, 1
set cartoon_smooth_loops, 1
set two_sided_lighting, on
set valence, 0
set stick_radius, 0.18

# Load closest reconstructed pose if present; otherwise fall back to prepared input structures.
python
from pymol import cmd
import os

def load_first(candidates, obj):
    for f in candidates:
        if os.path.exists(f):
            cmd.load(f, obj)
            print(f"Loaded {f} as {obj}")
            return f
    raise FileNotFoundError(f"None found for {obj}: {candidates}")

load_first(["hmgb2_pose_046.pdb", "hmgb2_pose_2615.pdb", "hmgb2_fixed_minim.pdb", "input_hmgb2_receptor.pdb"], "hmgb2")
load_first(["crbn_pose_046.pdb", "crbn_pose_2615.pdb", "crbn_fixed_minim.pdb", "input_crbn_ligase.pdb"], "crbn")
if os.path.exists("inflachromene_derivative.mol2"):
    cmd.load("inflachromene_derivative.mol2", "icm")
if os.path.exists("thalidomide_analog.mol2"):
    cmd.load("thalidomide_analog.mol2", "thal")
python end

hide everything
show cartoon, hmgb2
show cartoon, crbn
color marine, hmgb2
color lightpink, crbn

# Ligands: visible but not oversized.
show sticks, icm
show sticks, thal
color red, icm
color purple, thal
set stick_radius, 0.22, icm or thal

# De-emphasize clutter.
hide lines, hydro
hide sticks, solvent

# Keep the whole complex clean. No big in-image text; put title/caption in PPT.
orient hmgb2 or crbn
zoom hmgb2 or crbn, 14
clip slab, 180

# Save image and session.
png fig1_overview_clean_v2.png, dpi=300
save fig1_overview_clean_v2.pse
quit
