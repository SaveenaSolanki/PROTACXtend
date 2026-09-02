#!/usr/bin/env python3
"""
Clean, presentation-quality molecular glue images.
Minimal labels, clear views, publication-ready.
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

cmd.load(f'{OUT}/hmgb2_pose_1655.pdb', 'hmgb2')
cmd.load(f'{OUT}/crbn_pose_1655.pdb', 'crbn')
cmd.load(f'{OUT}/inflachromene_derivative.mol2', 'icm')

# ====== IMAGE 1: Lysine Accessibility — CLEAN ======
cmd.hide('everything')
cmd.show('cartoon', 'hmgb2')
cmd.color('grey70', 'hmgb2')
cmd.show('cartoon', 'crbn')
cmd.color('lightpink', 'crbn')
cmd.set('cartoon_transparency', 0.2, 'crbn')

# Show ICM
cmd.show('sticks', 'icm')
cmd.color('red', 'icm')
cmd.set('stick_radius', 0.3, 'icm')

# Show all lysines as spheres
cmd.select('all_lys', 'hmgb2 and resn LYS and name CA')
cmd.show('spheres', 'all_lys')
cmd.color('orange', 'all_lys')
cmd.set('sphere_scale', 0.35, 'all_lys')

# Red highlight for closest lysines
for res in [152, 141, 96, 150, 147, 127]:
    cmd.select(f'k{res}', f'hmgb2 and resi {res} and name CA')
    cmd.show('spheres', f'k{res}')
    cmd.color('red', f'k{res}')
    cmd.set('sphere_scale', 0.5, f'k{res}')

# One simple label: K152
cmd.select('k152_label', 'hmgb2 and resi 152 and name CA')
cmd.label('k152_label', '"K152 (16.6 A)"')
cmd.set('label_color', 'red', 'k152_label')
cmd.set('label_size', 18, 'k152_label')

# Single title
cmd.pseudoatom('title1', pos=[0, 5, 25])
cmd.label('title1', '"HMGB2 Lysines"')
cmd.set('label_color', 'black', 'title1')
cmd.set('label_size', 22, 'title1')

cmd.orient('hmgb2')
cmd.zoom('hmgb2', 5)
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/glue_clean_lysine.png')

# ====== IMAGE 2: Electrostatic Complementarity — CLEAN ======
cmd.delete('title1')
cmd.delete('k152_label')
cmd.hide('labels')
cmd.hide('everything')

cmd.show('cartoon', 'hmgb2')
cmd.color('white', 'hmgb2')
cmd.show('cartoon', 'crbn')
cmd.color('white', 'crbn')

# Basic residues on HMGB2 (positive) — BLUE
cmd.select('hmgb2_pos', 'hmgb2 and (resn ARG or resn LYS) and name CA')
cmd.show('spheres', 'hmgb2_pos')
cmd.color('blue', 'hmgb2_pos')
cmd.set('sphere_scale', 0.5, 'hmgb2_pos')

# Acidic residues on CRBN (negative) — RED
cmd.select('crbn_neg', 'crbn and (resn ASP or resn GLU) and name CA')
cmd.show('spheres', 'crbn_neg')
cmd.color('red', 'crbn_neg')
cmd.set('sphere_scale', 0.3, 'crbn_neg')

# Show ICM
cmd.show('sticks', 'icm')
cmd.color('green', 'icm')
cmd.set('stick_radius', 0.4, 'icm')

# Minimal labels
cmd.pseudoatom('lpos', pos=[5, 10, 15])
cmd.label('lpos', '"HMGB2 basic (Lys/Arg)"')
cmd.set('label_color', 'blue', 'lpos')
cmd.set('label_size', 16, 'lpos')

cmd.pseudoatom('lneg', pos=[-10, -5, -5])
cmd.label('lneg', '"CRBN acidic (Asp/Glu)"')
cmd.set('label_color', 'red', 'lneg')
cmd.set('label_size', 16, 'lneg')

cmd.pseudoatom('licm', pos=[0, 0, 20])
cmd.label('licm', '"ICM"')
cmd.set('label_color', 'green', 'licm')
cmd.set('label_size', 16, 'licm')

cmd.orient('hmgb2 or crbn')
cmd.zoom('hmgb2 or crbn', 3)
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/glue_clean_electrostatic.png')

# ====== IMAGE 3: ICM Position relative to CRBN — CLEAN ======
cmd.delete('lpos')
cmd.delete('lneg')
cmd.delete('licm')
cmd.hide('labels')
cmd.hide('everything')

# Side view showing both proteins with ICM on far side
cmd.show('surface', 'hmgb2')
cmd.set('transparency', 0.4, 'hmgb2')
cmd.color('palegreen', 'hmgb2')
cmd.show('surface', 'crbn')
cmd.set('transparency', 0.3, 'crbn')
cmd.color('lightpink', 'crbn')

# ICM in sticks
cmd.show('sticks', 'icm')
cmd.color('red', 'icm')
cmd.set('stick_radius', 0.5, 'icm')

# Labels
cmd.pseudoatom('pi', pos=[0, 5, 15])
cmd.label('pi', '"ICM"')
cmd.set('label_color', 'red', 'pi')
cmd.set('label_size', 20, 'pi')

# Orient to show ICM is on opposite face from CRBN
cmd.orient('icm')
cmd.zoom('icm', 8)
cmd.ray(2400, 1800)
cmd.png(f'{OUT}/glue_clean_position.png')

cmd.quit()
EOF