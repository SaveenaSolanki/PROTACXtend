reinitialize
bg white
set ray_opaque_background, off
set antialias, 2
set depth_cue, 0

load hmgb2_fixed_minim.pdb, hmgb2
load crbn_fixed_minim.pdb, crbn
load inflachromene_derivative.mol2, icm
load thalidomide_analog.mol2, thal

hide everything
show cartoon, hmgb2
show cartoon, crbn
color skyblue, hmgb2
color pink, crbn
set cartoon_transparency, 0.65

show sticks, icm
show sticks, thal
color red, icm
color purple, thal

# keep or remake your exit-vector atom selections
# select hmgb2_exit, icm and name O1
# select crbn_exit, thal and name C1
# show spheres, hmgb2_exit or crbn_exit
# color red, hmgb2_exit
# color purple, crbn_exit
# distance gap_line, hmgb2_exit, crbn_exit

set sphere_scale, 0.35
set dash_width, 4
set dash_color, black

zoom icm or thal, 10

pseudoatom txt1, pos=(0,0,0)
label txt1, "Closest gap = 10.83 Å"
set label_color, black, txt1
set label_size, 22, txt1
set label_font_id, 7

pseudoatom txt2, pos=(0,-3,0)
label txt2, "Linker max = 0.74 Å"
set label_color, red, txt2
set label_size, 20, txt2
set label_font_id, 7

pseudoatom txt3, pos=(0,-6,0)
label txt3, "~14.6x too short"
set label_color, firebrick, txt3
set label_size, 20, txt3
set label_font_id, 7

png fig2_gap_zoom_clean.png, dpi=300
quit