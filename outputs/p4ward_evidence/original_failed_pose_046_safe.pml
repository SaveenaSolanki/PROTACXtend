reinitialize

load hmgb2_pose_046.pdb, hmgb2
load crbn_pose_046.pdb, crbn
load inflachromene_derivative.mol2, icm
load thalidomide_analog.mol2, thal

hide everything, all

show cartoon, hmgb2
show cartoon, crbn
show sticks, icm
show sticks, thal

color marine, hmgb2
color lightpink, crbn
color red, icm
color purple, thal

set stick_radius, 0.18
bg_color white
set ray_opaque_background, off
set antialias, 2
set depth_cue, 0

orient hmgb2 or crbn
zoom hmgb2 or crbn, 8

png original_failed_pose_046_safe.png, dpi=300
save original_failed_pose_046_safe.pse

quit
