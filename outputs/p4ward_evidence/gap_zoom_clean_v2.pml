# gap_zoom_clean_v2.pml
# Clean local gap figure: ligands + distance proxy, with proteins faded.
# Run from: /storage/saveena/protacpilot/outputs/p4ward_evidence

reinitialize
bg white
set ray_opaque_background, off
set orthoscopic, on
set antialias, 2
set depth_cue, 0
set specular, 0.15
set ambient, 0.55
set cartoon_fancy_helices, 1
set cartoon_smooth_loops, 1
set two_sided_lighting, on
set valence, 0
set stick_radius, 0.20
set sphere_scale, 0.35
set dash_width, 4
set dash_gap, 0.25
set dash_color, black
set label_color, black
set label_size, 16
set label_font_id, 7

python
from pymol import cmd
import os, math

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

# Fade proteins so the ligand geometry is the visual focus.
show cartoon, hmgb2
show cartoon, crbn
color skyblue, hmgb2
color lightpink, crbn
set cartoon_transparency, 0.72, hmgb2
set cartoon_transparency, 0.72, crbn

show sticks, icm
show sticks, thal
color red, icm
color purple, thal
set stick_radius, 0.28, icm or thal
hide lines, hydro

# Automatically create a visual distance proxy between the nearest heavy atoms of ICM and thalidomide.
# The quantitative value used in the PPT should remain the P4ward value: closest exit-vector gap = 10.83 A.
python
from pymol import cmd
import math

m1 = cmd.get_model("icm and not hydro")
m2 = cmd.get_model("thal and not hydro")
if len(m1.atom) and len(m2.atom):
    best = None
    for a in m1.atom:
        for b in m2.atom:
            d = math.sqrt(sum((a.coord[i]-b.coord[i])**2 for i in range(3)))
            if best is None or d < best[0]:
                best = (d, a.coord, b.coord)
    d, ca, cb = best
    mid = [(ca[i]+cb[i])/2.0 for i in range(3)]
    # offset label gently above the line to avoid overlap
    label_pos = [mid[0], mid[1]+2.5, mid[2]+1.5]
    cmd.pseudoatom("icm_exit_marker", pos=ca)
    cmd.pseudoatom("crbn_exit_marker", pos=cb)
    cmd.show("spheres", "icm_exit_marker or crbn_exit_marker")
    cmd.color("red", "icm_exit_marker")
    cmd.color("purple", "crbn_exit_marker")
    cmd.distance("gap_line", "icm_exit_marker", "crbn_exit_marker")
    cmd.hide("labels", "gap_line")
    cmd.pseudoatom("gap_text", pos=label_pos)
    cmd.label("gap_text", '"P4ward closest gap = 10.83 A"')
    cmd.set("label_color", "black", "gap_text")
    cmd.set("label_size", 15, "gap_text")
else:
    print("WARNING: icm/thal atoms not found; gap line was not created.")
python end

orient icm or thal or gap_line
zoom icm or thal or gap_line, 7
clip slab, 90

png fig2_gap_zoom_clean_v2.png, dpi=300
save fig2_gap_zoom_clean_v2.pse
quit
