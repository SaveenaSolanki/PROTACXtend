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
color marine, hmgb2
color lightpink, crbn

show sticks, icm
show sticks, thal
color red, icm
color purple, thal

# if you already know the exit-vector atoms, keep your existing selections here
# example placeholders:
# select hmgb2_exit, icm and name O1
# select crbn_exit, thal and name C1
# distance gap_line, hmgb2_exit, crbn_exit

set dash_color, black
set dash_width, 3

orient hmgb2 or crbn
zoom hmgb2 or crbn, 8

pseudoatom title1, pos=(0,0,0)
label title1, "HMGB2-CRBN tested orientation"
set label_color, black, title1
set label_size, 24, title1
set label_font_id, 7

png fig1_overview_clean.png, dpi=300
quit