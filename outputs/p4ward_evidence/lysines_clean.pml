reinitialize
bg white
set ray_opaque_background, off
set antialias, 2
set depth_cue, 0

load hmgb2_fixed_minim.pdb, hmgb2

hide everything
show cartoon, hmgb2
color lightblue, hmgb2

select lysines, hmgb2 and resn LYS
show sticks, lysines
color orange, lysines

# optional: label only a few if needed
# label hmgb2 and resi 55 and name CA, "Lys55"
# label hmgb2 and resi 82 and name CA, "Lys82"

orient hmgb2
zoom hmgb2, 6

pseudoatom t1, pos=(0,0,0)
label t1, "HMGB2 has surface lysines"
set label_color, black, t1
set label_size, 22, t1
set label_font_id, 7

pseudoatom t2, pos=(0,-3,0)
label t2, "Supports degradability potential"
set label_color, darkgreen, t2
set label_size, 18, t2
set label_font_id, 7

png fig3_hmgb2_lysines_clean.png, dpi=300
quit