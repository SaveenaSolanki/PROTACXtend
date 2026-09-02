#!/usr/bin/env python3
"""
PyMOL rendering script for HMGB2 PROTAC meeting images.
Run with:  /home/saveenas/miniconda3/envs/pymol_vis/bin/python3 -m pymol -c -q pymol_render.py
"""

import pymol
from pymol import cmd, cgo

# ============================================================
# 0. SETUP
# ============================================================
cmd.reinitialize()
cmd.set('ray_opaque_background', 'on')
cmd.bg_color('white')
cmd.set('depth_cue', '0')
cmd.set('antialias', '2')
cmd.viewport(2400, 1800)

OUT = '/storage/saveena/protacpilot/outputs/p4ward_evidence'

# ============================================================
# 1. LOAD HMGB2 (Receptor)
# ============================================================
cmd.load(f'{OUT}/hmgb2_fixed_minim.pdb', 'hmgb2')
cmd.hide('everything', 'hmgb2')
cmd.show('cartoon', 'hmgb2')
cmd.color('palegreen', 'hmgb2')
cmd.set('cartoon_transparency', 0.15, 'hmgb2')

# Domain coloring
cmd.select('box_a', 'hmgb2 and resi 9-79')
cmd.select('box_b', 'hmgb2 and resi 95-163')
cmd.select('c_tail', 'hmgb2 and resi 186-209')
cmd.color('marine', 'box_a')
cmd.color('skyblue', 'box_b')
cmd.color('palecyan', 'c_tail')

# Lysines
cmd.select('lysines', 'hmgb2 and resn LYS')
cmd.show('sticks', 'lysines')
cmd.color('orange', 'lysines')
cmd.set('stick_radius', 0.3, 'lysines')
cmd.select('lysine_ca', 'lysines and name CA')
cmd.show('spheres', 'lysine_ca')
cmd.set('sphere_scale', 0.4, 'lysine_ca')
cmd.label('lysine_ca', '"K"')
cmd.set('label_color', 'orange', 'lysine_ca')
cmd.set('label_size', 14, 'lysine_ca')

# ============================================================
# 2. LOAD ICM WARHEAD
# ============================================================
cmd.load(f'{OUT}/inflachromene_derivative.mol2', 'inflachromene')
cmd.hide('everything', 'inflachromene')
cmd.show('sticks', 'inflachromene')
cmd.color('red', 'inflachromene')
cmd.set('stick_radius', 0.3, 'inflachromene')

# Exit vector OH groups
cmd.select('icm_oh1', 'inflachromene and (elem O and id 27)')
cmd.select('icm_oh2', 'inflachromene and (elem O and id 29)')
cmd.show('spheres', 'icm_oh1')
cmd.show('spheres', 'icm_oh2')
cmd.color('firebrick', 'icm_oh1')
cmd.color('firebrick', 'icm_oh2')
cmd.set('sphere_scale', 0.6, 'icm_oh1')
cmd.set('sphere_scale', 0.6, 'icm_oh2')

# ============================================================
# 3. LOAD CRBN (Ligase)
# ============================================================
cmd.load(f'{OUT}/crbn_fixed_minim.pdb', 'crbn')
cmd.hide('everything', 'crbn')
cmd.show('cartoon', 'crbn')
cmd.color('lightpink', 'crbn')
cmd.set('cartoon_transparency', 0.3, 'crbn')

cmd.select('crbn_pocket', 'crbn and chain A and resi 350-420')
cmd.show('surface', 'crbn_pocket')
cmd.set('transparency', 0.5, 'crbn_pocket')
cmd.color('salmon', 'crbn_pocket')

# ============================================================
# 4. LOAD THALIDOMIDE
# ============================================================
cmd.load(f'{OUT}/thalidomide_analog.mol2', 'thalidomide')
cmd.hide('everything', 'thalidomide')
cmd.show('sticks', 'thalidomide')
cmd.color('purpleblue', 'thalidomide')
cmd.set('stick_radius', 0.3, 'thalidomide')

cmd.select('thal_exit', 'thalidomide and (id 6 or id 9)')
cmd.show('spheres', 'thal_exit')
cmd.color('purple', 'thal_exit')
cmd.set('sphere_scale', 0.6, 'thal_exit')

# ============================================================
# 5. DISTANCE MEASUREMENTS
# ============================================================
cmd.distance('exit_vector_gap', 'inflachromene and id 27', 'thalidomide and id 6')
cmd.set('dash_color', 'red', 'exit_vector_gap')
cmd.set('dash_width', 3, 'exit_vector_gap')
cmd.set('dash_length', 0.15)

cmd.distance('exit_vector_gap_2', 'inflachromene and id 29', 'thalidomide and id 9')
cmd.set('dash_color', 'red', 'exit_vector_gap_2')
cmd.set('dash_width', 3, 'exit_vector_gap_2')
cmd.set('dash_length', 0.15)

# Label the distance on the distance object
cmd.set('label_color', 'red', 'exit_vector_gap')
cmd.set('label_color', 'red', 'exit_vector_gap_2')

# ============================================================
# 6. EVIDENCE ANNOTATIONS
# ============================================================
# Use CGO text for permanent annotations
txt_pos = [-30, -25, 35]

# If CGO text doesn't work, use pseudoatom labels as fallback
# Create annotation labels using pseudoatoms
cmd.pseudoatom('anno1', pos=[-30, -20, 40])
cmd.label('anno1', '"P4WARD RESULT: ZERO VIABLE TERNARY COMPLEXES"')
cmd.set('label_color', 'black', 'anno1')
cmd.set('label_size', 24, 'anno1')

cmd.pseudoatom('anno2', pos=[-30, -15, 35])
cmd.label('anno2', '"3600 docking orientations sampled -- 0 passed filter"')
cmd.set('label_color', 'red', 'anno2')
cmd.set('label_size', 18, 'anno2')

cmd.pseudoatom('anno3', pos=[-30, -12, 30])
cmd.label('anno3', '"Linker max span: 0.74 A  |  Closest gap: 10.83 A"')
cmd.set('label_color', 'red', 'anno3')
cmd.set('label_size', 16, 'anno3')

cmd.pseudoatom('anno4', pos=[-30, -9, 25])
cmd.label('anno4', '"ROOT CAUSE: C4-equivalent linker is ~14x too short"')
cmd.set('label_color', 'firebrick', 'anno4')
cmd.set('label_size', 18, 'anno4')

# ============================================================
# 7. RENDER VIEW 1: Overview
# ============================================================
cmd.orient()
cmd.zoom('hmgb2 or crbn')
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/pymol_overview.png')

# ============================================================
# 8. RENDER VIEW 2: Zoom on exit vector gap
# ============================================================
cmd.zoom('inflachromene or thalidomide')
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/pymol_gap_zoom.png')

# ============================================================
# 9. RENDER VIEW 3: HMGB2 lysine landscape
# ============================================================
cmd.select('none')
cmd.show('cartoon', 'hmgb2')
cmd.show('sticks', 'lysines')
cmd.show('spheres', 'lysine_ca')
cmd.show('sticks', 'inflachromene')
cmd.zoom('hmgb2')
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/pymol_hmgb2_lysines.png')
cmd.deselect()

# ============================================================
# 10. RENDER VIEW 4: CRBN + surface
# ============================================================
cmd.select('none')
cmd.show('cartoon', 'crbn')
cmd.show('sticks', 'thalidomide')
cmd.show('surface', 'crbn_pocket')
cmd.zoom('crbn')
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/pymol_crbn_surface.png')

# ============================================================
# 11. RENDER VIEW 5: Closest failed pose - CRBN rotated (using pose 2615 approx)
# ============================================================
cmd.load(f'{OUT}/hmgb2_pose_2615.pdb', 'hmgb2_pose')
cmd.load(f'{OUT}/crbn_pose_2615.pdb', 'crbn_pose')
cmd.hide('everything', 'hmgb2_pose')
cmd.hide('everything', 'crbn_pose')
cmd.show('cartoon', 'hmgb2_pose')
cmd.show('cartoon', 'crbn_pose')
cmd.color('green', 'hmgb2_pose')
cmd.color('pink', 'crbn_pose')
cmd.zoom('hmgb2_pose or crbn_pose')
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/pymol_pose_2615_overview.png')

# Label
cmd.pseudoatom('poselabel', pos=[0, 0, 30])
cmd.label('poselabel', '"CLOSEST POSE (#2615): Exit vectors 10.83 A apart"')
cmd.set('label_color', 'red', 'poselabel')
cmd.set('label_size', 20, 'poselabel')
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/pymol_pose_2615_labeled.png')

# ============================================================
# DONE
# ============================================================
cmd.quit()
