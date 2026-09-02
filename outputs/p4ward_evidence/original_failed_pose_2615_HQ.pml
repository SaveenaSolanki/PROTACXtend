reinitialize

load hmgb2_pose_2615.pdb, hmgb2
load crbn_pose_2615.pdb, crbn
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

set stick_radius, 0.22
set cartoon_transparency, 0.10, crbn
set ray_opaque_background, off
set antialias, 2
set depth_cue, 0
bg_color white

orient hmgb2 or crbn
zoom hmgb2 or crbn, 8

viewport 2000, 1500
ray 2000, 1500
png original_failed_pose_2615_HQ.png, dpi=300
save original_failed_pose_2615_HQ.pse

quit
