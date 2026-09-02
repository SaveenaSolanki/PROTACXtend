# lysines_clean_v2.pml
# Clean HMGB2 lysine landscape figure. No CRBN, no large text labels.
# Run from: /storage/saveena/protacpilot/outputs/p4ward_evidence

reinitialize
bg white
set ray_opaque_background, off
set orthoscopic, on
set antialias, 2
set depth_cue, 0
set specular, 0.12
set ambient, 0.55
set cartoon_fancy_helices, 1
set cartoon_smooth_loops, 1
set two_sided_lighting, on
set valence, 0
set stick_radius, 0.16
set sphere_scale, 0.24
set label_size, 12
set label_font_id, 7

python
from pymol import cmd
import os
for f in ["hmgb2_pose_046.pdb", "hmgb2_pose_2615.pdb", "hmgb2_fixed_minim.pdb", "input_hmgb2_receptor.pdb"]:
    if os.path.exists(f):
        cmd.load(f, "hmgb2")
        print(f"Loaded {f} as hmgb2")
        break
else:
    raise FileNotFoundError("No HMGB2 PDB found.")
python end

hide everything
show cartoon, hmgb2
color skyblue, hmgb2
set cartoon_transparency, 0.05, hmgb2

select hmgb2_lys, hmgb2 and resn LYS
show sticks, hmgb2_lys
color orange, hmgb2_lys
hide sticks, hydro

# Label only a few lysines to avoid clutter: every 5th lysine CA atom.
python
from pymol import cmd
model = cmd.get_model("hmgb2_lys and name CA")
resis = []
seen = set()
for a in model.atom:
    key = (a.chain, a.resi)
    if key not in seen:
        seen.add(key)
        resis.append((a.chain, a.resi))
for i, (chain, resi) in enumerate(resis):
    if i % 5 == 0:
        sel = f"hmgb2 and resn LYS and chain {chain} and resi {resi} and name CA"
        cmd.label(sel, f'"K{resi}"')
cmd.set("label_color", "black")
cmd.set("label_size", 10)
python end

orient hmgb2
zoom hmgb2, 9
clip slab, 120

png fig3_hmgb2_lysines_clean_v2.png, dpi=300
save fig3_hmgb2_lysines_clean_v2.pse
quit
