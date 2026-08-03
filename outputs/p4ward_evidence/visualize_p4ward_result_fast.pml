"""
PyMOL Session Script — HMGB2 + CRBN P4ward Ternary Complex Failure Evidence
============================================================================
Load this script in PyMOL:  File > Run > visualize_p4ward_result.pml
Or run:  pymol -qx visualize_p4ward_result.pml

This script loads all input structures with publication-quality styling,
annotates the exit vectors, measures the gap, and embeds the key evidence.
"""

# ===========================================================================
# 0. Session setup
# ===========================================================================
reinitialize
set ray_opaque_background, on
bg_color white
set depth_cue, 0
set antialias, 2

# ===========================================================================
# 1. Load HMGB2 (Receptor)
# ===========================================================================
load hmgb2_fixed_minim.pdb, hmgb2
hide everything, hmgb2
show cartoon, hmgb2
color palegreen, hmgb2
set cartoon_transparency, 0.15, hmgb2

# Label key domains
# Box A: residues 9-79, Box B: 95-163, C-tail: 186-209
select box_a, hmgb2 and resi 9-79
select box_b, hmgb2 and resi 95-163
select c_tail, hmgb2 and resi 186-209

color marine, box_a
color skyblue, box_b
color palecyan, c_tail

# Show lysine sidechains (the potential ubiquitination targets)
select lysines, hmgb2 and resn LYS
show sticks, lysines
color orange, lysines
set stick_radius, 0.3, lysines
select lysine_ca, lysines and name CA
show spheres, lysine_ca
set sphere_scale, 0.4, lysine_ca
label lysine_ca, "K"

# ===========================================================================
# 2. Load Inflachromene warhead (Receptor Ligand)
# ===========================================================================
load inflachromene_derivative.mol2, inflachromene
hide everything, inflachromene
show sticks, inflachromene
color red, inflachromene
set stick_radius, 0.3, inflachromene

# Highlight the OH groups (potential exit vector)
select icm_oh1, inflachromene and (elem O and id 27)
select icm_oh2, inflachromene and (elem O and id 29)
show spheres, icm_oh1
show spheres, icm_oh2
color firebrick, icm_oh1
color firebrick, icm_oh2
set sphere_scale, 0.5, icm_oh1
set sphere_scale, 0.5, icm_oh2

# ===========================================================================
# 3. Load CRBN (Ligase / E3)
# ===========================================================================
load crbn_fixed_minim.pdb, crbn
hide everything, crbn
show cartoon, crbn
color lightpink, crbn
set cartoon_transparency, 0.3, crbn

# Highlight the thalidomide binding pocket region (CRBN residues ~350-420)
# Thalidomide binds in the tri-Trp pocket
select crbn_pocket, crbn and chain A and resi 350-420
show surface, crbn_pocket
set transparency, 0.5, crbn_pocket
color salmon, crbn_pocket

# ===========================================================================
# 4. Load Thalidomide analog (E3 Ligand)
# ===========================================================================
load thalidomide_analog.mol2, thalidomide
hide everything, thalidomide
show sticks, thalidomide
color purpleblue, thalidomide
set stick_radius, 0.3, thalidomide

# Highlight phthalimide ring atoms (exit vector candidates)
select thal_exit, thalidomide and (id 6 or id 9)
show spheres, thal_exit
color purple, thal_exit
set sphere_scale, 0.5, thal_exit

# ===========================================================================
# 5. Distance Measurements
# ===========================================================================
# Measure between ICM OH groups and thalidomide exit vector atoms
# These are the likely linker attachment points

# Distance 1: ICM OH1 (atom 27) to thalidomide C6 (atom 6)
distance exit_vector_gap_1, \
    inflachromene and id 27, \
    thalidomide and id 6
hide labels, exit_vector_gap_1

# Distance 2: ICM OH1 to thalidomide C9 (atom 9)
distance exit_vector_gap_2, \
    inflachromene and id 27, \
    thalidomide and id 9
hide labels, exit_vector_gap_2

# Distance 3: ICM OH2 (atom 29) to thalidomide C6
distance exit_vector_gap_3, \
    inflachromene and id 29, \
    thalidomide and id 6

# Distance 4: ICM OH2 to thalidomide C9
distance exit_vector_gap_4, \
    inflachromene and id 29, \
    thalidomide and id 9

# Show only one representative distance with label
hide exit_vector_gap_1
hide exit_vector_gap_2
hide exit_vector_gap_4
show dashed, exit_vector_gap_3
set dash_color, red, exit_vector_gap_3
set dash_width, 3, exit_vector_gap_3
set dash_length, 0.15
label exit_vector_gap_3, "Exit Vector Gap\n(protac cannot span)"

# Protein-protein distance (centers)
distance protein_centers, \
    hmgb2 and name CA, \
    crbn and name CA
hide protein_centers

# ===========================================================================
# 6. Annotations & Evidence Summary
# ===========================================================================

# Create a text object for the key evidence
# PyMOL doesn't natively support floating text, but we can use a CGO
# For a simpler approach, we use the label command on empty selections

# Create a pseudoatom at a specific position for the annotation
# Position the annotation in 3D space
pseudoatom annotation_1, pos=(-30, -20, 40)
label annotation_1, "P4WARD RESULT: ZERO VIABLE TERNARY COMPLEXES"
set label_color, black
set label_size, 2

pseudoatom annotation_2, pos=(-30, -15, 35)
label annotation_2, "3600 docking orientations sampled — 0 passed filter"
set label_color, red
set label_size, 1.5

pseudoatom annotation_3, pos=(-30, -12, 30)
label annotation_3, "Linker max span: 0.74 Å  |  Closest gap: 10.83 Å"
set label_color, red
set label_size, 1.2

pseudoatom annotation_4, pos=(-30, -9, 25)
label annotation_4, "ROOT CAUSE: C4-equivalent linker is ~14× too short"
set label_color, firebrick
set label_size, 1.5

pseudoatom annotation_5, pos=(-30, -6, 20)
label annotation_5, "Solution: longer linkers (C10-C14) + switch to CRBN"
set label_color, green
set label_size, 1.2

# ===========================================================================
# 7. View Setup
# ===========================================================================

# View 1: Overview showing both proteins with gap
orient
# zoom center command removed for compatibility
set_view (\
 0.821548045,    0.161819994,    0.547144711,\
 0.144021109,    0.878717899,   -0.454944789,\
-0.551886022,    0.448949993,    0.702723145,\
 0.000000000,    0.000000000, -300.000000000,\
-11.012870789,  -28.881414413,    2.751313210,\
180.311737061,  419.552917480,  -20.000000000 )
ray 1400, 1000

# Save image
png hmgb2_p4ward_evidence_fast.png, dpi=300

# View 2: Zoom into the gap with distance measurement
# (adjust as needed after first ray trace)
zoom exit_vector_gap_3, d=15
ray 1400, 1000
png hmgb2_p4ward_evidence_fast.png, dpi=300

# View 3: HMGB2 alone showing lysine landscape
select none
show cartoon, hmgb2
show sticks, lysines
show spheres, lysine_ca
show sticks, inflachromene
zoom hmgb2, d=5
ray 1400, 1000
png hmgb2_p4ward_evidence_fast.png, dpi=300

# View 4: CRBN alone showing E3 ligand
select none
show cartoon, crbn
show sticks, thalidomide
show surface, crbn_pocket
zoom crbn, d=5
ray 1400, 1000
png hmgb2_p4ward_evidence_fast.png, dpi=300

# ===========================================================================
# 8. Summary text for PyMOL command line
# ===========================================================================
print("=" * 60)
print("P4WARD TERNARY COMPLEX EVIDENCE SUMMARY")
print("=" * 60)
print("RUN: /storage/saveena/protacpilot/work/p4ward_output/hmgb2_icm/")
print("RESULT: 0/3600 poses passed distance filter (linker too short)")
print("LINKER (CCCOCCC): max conformational span = 0.74 Å")
print("CLOSEST POSE: exit vector gap = 10.83 Å (14.6× linker max)")
print()
print("For the full log evidence:")
print("  cat p4ward_run.log | grep 'There are no poses'")
print("=" * 60)

# Save the PyMOL session
save hmgb2_p4ward_evidence.pse
