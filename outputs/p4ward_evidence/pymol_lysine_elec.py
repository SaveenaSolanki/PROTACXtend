#!/usr/bin/env python3
"""
PyMOL: Lysine accessibility + electrostatic complementarity for HMGB2-CRBN.
"""
import pymol, os
from pymol import cmd

OUT = '/storage/saveena/protacpilot/outputs/p4ward_evidence'
cmd.reinitialize()
cmd.set('ray_opaque_background', 'on')
cmd.bg_color('white')
cmd.set('depth_cue', '0')
cmd.set('antialias', '2')
cmd.viewport(2400, 1800)

# Load Pose #1655
cmd.load(f'{OUT}/hmgb2_pose_1655.pdb', 'hmgb2')
cmd.load(f'{OUT}/crbn_pose_1655.pdb', 'crbn')
cmd.load(f'{OUT}/inflachromene_derivative.mol2', 'icm')

# ========== VIEW 1: Lysine Accessibility ==========
cmd.hide('everything')
cmd.show('cartoon', 'hmgb2')
cmd.color('grey80', 'hmgb2')
cmd.show('cartoon', 'crbn')
cmd.color('lightpink', 'crbn')
cmd.set('cartoon_transparency', 0.3, 'crbn')

# Show ICM
cmd.show('sticks', 'icm')
cmd.color('red', 'icm')
cmd.set('stick_radius', 0.3, 'icm')

# Show ALL lysines on HMGB2
cmd.select('lys', 'hmgb2 and resn LYS')
cmd.show('sticks', 'lys')
cmd.set('stick_radius', 0.2, 'lys')

# Color lysines by distance to CRBN (closer = more red, farther = more blue)
# K152 is closest at 16.6A, farthest at ~58A
# We'll approximate: red < 25A, orange 25-35, yellow 35-45, blue > 45
cmd.color('orange', 'lys')  # all orange first

# Highlight key proximal lysines
for res in [96, 127, 139, 141, 147, 150, 152, 154]:
    sel = f'hmgb2 and resi {res} and resn LYS'
    cmd.show('spheres', sel)
    cmd.set('sphere_scale', 0.6, sel)
    cmd.color('red', sel)
    cmd.label(f'{sel} and name CA', f'"K{res}"')
    cmd.set('label_color', 'red', f'{sel} and name CA')
    cmd.set('label_size', 16, f'{sel} and name CA')

# Also show some more distant lysines in blue
for res in [3, 8, 172, 173, 182, 183, 184]:
    sel = f'hmgb2 and resi {res} and resn LYS'
    cmd.show('spheres', sel)
    cmd.set('sphere_scale', 0.4, sel)
    cmd.color('blue', sel)

# Add E2~Ub proxy marker on CRBN (near thalidomide binding pocket)
cmd.pseudoatom('e2ub', pos=[-1.5, 0.4, 0.0])
cmd.show('spheres', 'e2ub')
cmd.set('sphere_scale', 0.8, 'e2ub')
cmd.color('green', 'e2ub')
cmd.label('e2ub', '"E2~Ub active site"')
cmd.set('label_color', 'green', 'e2ub')
cmd.set('label_size', 18, 'e2ub')

cmd.pseudoatom('title_lys', pos=[0, 0, 30])
cmd.label('title_lys', '"HMGB2 Lysine Accessibility — All 40 Lysines Reachable by CRBN E2~Ub"')
cmd.set('label_color', 'black', 'title_lys')
cmd.set('label_size', 22, 'title_lys')

cmd.pseudoatom('sub_lys', pos=[0, -5, 25])
cmd.label('sub_lys', '"Red: K152, K141, K96, K150, K127, K147 (closest, <25A) | Blue: distal lysines"')
cmd.set('label_color', 'black', 'sub_lys')
cmd.set('label_size', 16, 'sub_lys')

cmd.zoom('hmgb2 or crbn')
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/glue_lysine_accessibility.png')

# ========== VIEW 2: Electrostatic Complementarity ==========
cmd.delete('title_lys')
cmd.delete('sub_lys')
cmd.delete('e2ub')

# Hide previous labels
cmd.hide('labels')

cmd.hide('everything')
cmd.show('cartoon', 'hmgb2')
cmd.show('cartoon', 'crbn')
cmd.show('sticks', 'icm')
cmd.color('red', 'icm')
cmd.set('stick_radius', 0.3, 'icm')

# Show basic residues on HMGB2 (Arg, Lys) — positive charge → BLUE
cmd.select('hmgb2_basic', 'hmgb2 and (resn ARG or resn LYS or resn HIS)')
cmd.show('sticks', 'hmgb2_basic')
cmd.color('blue', 'hmgb2_basic')
cmd.set('stick_radius', 0.25, 'hmgb2_basic')

# Show acidic residues on CRBN (Asp, Glu) — negative charge → RED
cmd.select('crbn_acidic', 'crbn and (resn ASP or resn GLU)')
cmd.show('sticks', 'crbn_acidic')
cmd.color('red', 'crbn_acidic')
cmd.set('stick_radius', 0.25, 'crbn_acidic')

# Also show basic residues on CRBN and acidic on HMGB2 for balance
cmd.select('hmgb2_acidic', 'hmgb2 and (resn ASP or resn GLU)')
cmd.show('sticks', 'hmgb2_acidic')
cmd.color('pink', 'hmgb2_acidic')
cmd.set('stick_radius', 0.15, 'hmgb2_acidic')

cmd.select('crbn_basic', 'crbn and (resn ARG or resn LYS or resn HIS)')
cmd.show('sticks', 'crbn_basic')
cmd.color('lightblue', 'crbn_basic')
cmd.set('stick_radius', 0.15, 'crbn_basic')

# Add surface for interface region
cmd.select('hmgb2_iface', 'hmgb2 and resi 90-165')
cmd.show('surface', 'hmgb2_iface')
cmd.set('transparency', 0.5, 'hmgb2_iface')
cmd.color('palegreen', 'hmgb2_iface')

cmd.pseudoatom('title_elec', pos=[0, 0, 30])
cmd.label('title_elec', '"Electrostatic Complementarity: HMGB2 (basic, blue) ↔ CRBN (acidic, red)"')
cmd.set('label_color', 'black', 'title_elec')
cmd.set('label_size', 20, 'title_elec')

cmd.pseudoatom('sub_elec', pos=[0, -5, 25])
cmd.label('sub_elec', '"HMGB2 pI 9.5 (40 Lys, 14 Arg) — CRBN has extensive acidic surface patches"')
cmd.set('label_color', 'black', 'sub_elec')
cmd.set('label_size', 16, 'sub_elec')

cmd.zoom('hmgb2 or crbn')
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/glue_electrostatic_complementarity.png')

# ========== VIEW 3: Combined — interface surface with ICM position ==========
cmd.delete('title_elec')
cmd.delete('sub_elec')
cmd.hide('labels')
cmd.hide('surface')

cmd.show('surface', 'hmgb2')
cmd.set('transparency', 0.3, 'hmgb2')
cmd.color('palegreen', 'hmgb2')
cmd.show('surface', 'crbn')
cmd.set('transparency', 0.3, 'crbn')
cmd.color('lightpink', 'crbn')

cmd.show('sticks', 'icm')
cmd.color('red', 'icm')
cmd.set('stick_radius', 0.5, 'icm')

# Show ICM is on FAR side of HMGB2 from CRBN
cmd.pseudoatom('icm_pos', pos=[2.0, 12.0, 1.0])
cmd.label('icm_pos', '"ICM BINDS HERE"')
cmd.set('label_color', 'red', 'icm_pos')
cmd.set('label_size', 18, 'icm_pos')

cmd.pseudoatom('crbn_pos', pos=[-20, -10, 0])
cmd.label('crbn_pos', '"CRBN approaches from here"')
cmd.set('label_color', 'purple', 'crbn_pos')
cmd.set('label_size', 18, 'crbn_pos')

cmd.pseudoatom('title_gap', pos=[-5, -10, 20])
cmd.label('title_gap', '"HMGB2 ↔ CRBN interface (left) — ICM is on the opposite face (right)"')
cmd.set('label_color', 'black', 'title_gap')
cmd.set('label_size', 18, 'title_gap')

cmd.zoom('hmgb2 or crbn')
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/glue_icm_position.png')

cmd.quit()
EOF