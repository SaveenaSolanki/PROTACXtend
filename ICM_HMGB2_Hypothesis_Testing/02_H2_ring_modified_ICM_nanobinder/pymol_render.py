"""
PyMOL visualization script: HMGB2 + A1_4COOH structure views.
Renders publication-quality images of the binding site.
"""
import os
import pymol
from pymol import cmd

H2 = "/storage/saveena/protacpilot/ICM_HMGB2_Hypothesis_Testing/02_H2_ring_modified_ICM_nanobinder"
DOCK = os.path.join(H2, "analog_HMGB2_docking")
INPUTS = "/storage/saveena/protacpilot/ICM_HMGB2_Hypothesis_Testing/00_inputs"
FIGS = os.path.join(H2, "proof")

hmgb2_pdb = os.path.join(INPUTS, "HMGB2_structures", "hmgb2_fixed_minim.pdb")
a1_pose = os.path.join(DOCK, "a1_4COOH_top_pose1.pdb")
icm_pose = "/tmp/icm_top1_pymol.pdb"

# Convert ICM pose
import subprocess
subprocess.run(["obabel", os.path.join(DOCK, "icm_parent_vina_out.pdbqt"), "-O", icm_pose, "-f", "1", "-l", "1"],
              capture_output=True, timeout=30)

# Launch PyMOL headless
pymol.finish_launching(['pymol', '-cq'])

# ======================================================================
# FIGURE 1: HMGB2 cartoon + A1_4COOH sticks (binding site overview)
# ======================================================================
cmd.reinitialize()
cmd.load(hmgb2_pdb, "hmgb2")
cmd.load(a1_pose, "a1")

# Style protein
cmd.hide("everything", "hmgb2")
cmd.show("cartoon", "hmgb2")
cmd.color("skyblue", "hmgb2 and ss s")
cmd.color("palecyan", "hmgb2 and ss h")
cmd.color("palecyan", "hmgb2 and ss l")
cmd.cartoon("loop", "hmgb2")

# Color by domain
cmd.color("blue", "hmgb2 and resi 1-79")
cmd.color("green", "hmgb2 and resi 95-163")
cmd.color("purple", "hmgb2 and resi 164-209")

# Style ligand
cmd.hide("everything", "a1")
cmd.show("sticks", "a1")
cmd.color("orange", "a1 and elem C")
cmd.color("red", "a1 and elem O")
cmd.color("blue", "a1 and elem N")
cmd.util.cnc("a1")

# Highlight COOH
cmd.select("cooh", "a1 and elem O and resi 1")
cmd.show("spheres", "cooh")
cmd.color("yellow", "cooh")
cmd.set("sphere_scale", 0.4, "cooh")

# Highlight binding site residues 78-86
cmd.select("icm_site", "hmgb2 and resi 78-86")
cmd.show("sticks", "icm_site")
cmd.color("gold", "icm_site and elem C")
cmd.color("red", "icm_site and elem O")
cmd.color("blue", "icm_site and elem N")

# Highlight CRBN interface 112-128
cmd.select("crbn_site", "hmgb2 and resi 112-128")
cmd.show("sticks", "crbn_site")
cmd.color("lime", "crbn_site and elem C")

# View
cmd.orient("a1")
cmd.zoom("a1", 8)
cmd.bg_color("white")
cmd.set("ray_opaque_background", 1)
cmd.set("ray_shadows", 0)
cmd.set("cartoon_fancy_helices", 1)
cmd.set("stick_radius", 0.15)
cmd.ray(1200, 1000)
cmd.png(os.path.join(FIGS, "pymol_hmgb2_a1_overview.png"), dpi=300)
print("✅ pymol_hmgb2_a1_overview.png")

# ======================================================================
# FIGURE 2: Binding pocket close-up with residues
# ======================================================================
cmd.reinitialize()
cmd.load(hmgb2_pdb, "hmgb2")
cmd.load(a1_pose, "a1")

# Protein as surface near pocket
cmd.hide("everything", "hmgb2")
cmd.show("cartoon", "hmgb2")
cmd.color("gray80", "hmgb2")
cmd.show("surface", "hmgb2 and resi 70-95")
cmd.color("gray60", "hmgb2 and resi 70-95")
cmd.set("surface_color", "gray70", "hmgb2 and resi 70-95")

# Ligand sticks
cmd.hide("everything", "a1")
cmd.show("sticks", "a1")
cmd.color("orange", "a1 and elem C")
cmd.color("red", "a1 and elem O")
cmd.color("blue", "a1 and elem N")
cmd.util.cnc("a1")

# COOH spheres
cmd.select("cooh", "a1 and elem O and resi 1")
cmd.show("spheres", "cooh")
cmd.color("yellow", "cooh")
cmd.set("sphere_scale", 0.4, "cooh")

# Key residues
cmd.select("lys85", "hmgb2 and resi 85")
cmd.show("sticks", "lys85")
cmd.color("magenta", "lys85 and elem C")
cmd.color("blue", "lys85 and elem N")
cmd.label("lys85 and name NZ", '"LYS85"')

cmd.select("tyr78", "hmgb2 and resi 78")
cmd.show("sticks", "tyr78")
cmd.color("magenta", "tyr78 and elem C")

cmd.select("gly83", "hmgb2 and resi 83")
cmd.show("sticks", "gly83")
cmd.color("magenta", "gly83 and elem C")

# Distance between COOH O and LYS85 NZ
cmd.distance("saltbridge", "a1 and elem O", "lys85 and name NZ")
cmd.color("yellow", "saltbridge")
cmd.set("dash_width", 3)

# H-bonds
cmd.distance("hbond1", "a1 and elem O", "tyr78 and elem O")
cmd.color("cyan", "hbond1")
cmd.set("dash_width", 2)

cmd.bg_color("white")
cmd.set("ray_opaque_background", 1)
cmd.set("ray_shadows", 0)
cmd.set("stick_radius", 0.15)
cmd.orient("a1")
cmd.zoom("a1", 6)
cmd.ray(1200, 1000)
cmd.png(os.path.join(FIGS, "pymol_pocket_residues.png"), dpi=300)
print("✅ pymol_pocket_residues.png")

# ======================================================================
# FIGURE 3: Surface representation - A1_4COOH in pocket
# ======================================================================
cmd.reinitialize()
cmd.load(hmgb2_pdb, "hmgb2")
cmd.load(a1_pose, "a1")

# Protein surface (transparent)
cmd.hide("everything", "hmgb2")
cmd.show("surface", "hmgb2")
cmd.set("transparency", 0.5, "hmgb2")
cmd.color("skyblue", "hmgb2")

# Ligand
cmd.show("sticks", "a1")
cmd.color("orange", "a1 and elem C")
cmd.color("red", "a1 and elem O")
cmd.color("blue", "a1 and elem N")

# COOH
cmd.select("cooh", "a1 and elem O and resi 1")
cmd.show("spheres", "cooh")
cmd.color("yellow", "cooh")
cmd.set("sphere_scale", 0.5, "cooh")

# Binding site colored on surface
cmd.select("site_surf", "hmgb2 and resi 78-86")
cmd.color("gold", "site_surf")
cmd.set("transparency", 0.2, "site_surf")

cmd.bg_color("white")
cmd.set("ray_opaque_background", 1)
cmd.set("ray_shadows", 1)
cmd.orient("a1")
cmd.zoom("a1", 7)
cmd.ray(1200, 1000)
cmd.png(os.path.join(FIGS, "pymol_surface_a1.png"), dpi=300)
print("✅ pymol_surface_a1.png")

# ======================================================================
# FIGURE 4: ICM vs A1_4COOH overlay
# ======================================================================
cmd.reinitialize()
cmd.load(hmgb2_pdb, "hmgb2")
cmd.load(icm_pose, "icm")
cmd.load(a1_pose, "a1")

# Protein cartoon light
cmd.hide("everything", "hmgb2")
cmd.show("cartoon", "hmgb2")
cmd.color("gray80", "hmgb2")

# ICM red
cmd.hide("everything", "icm")
cmd.show("sticks", "icm")
cmd.color("red", "icm and elem C")
cmd.color("firebrick", "icm and elem O")
cmd.color("blue", "icm and elem N")

# A1_4COOH blue
cmd.hide("everything", "a1")
cmd.show("sticks", "a1")
cmd.color("blue", "a1 and elem C")
cmd.color("red", "a1 and elem O")
cmd.color("blue", "a1 and elem N")

# COOH
cmd.select("cooh", "a1 and elem O and resi 1")
cmd.show("spheres", "cooh")
cmd.color("yellow", "cooh")
cmd.set("sphere_scale", 0.4, "cooh")

cmd.bg_color("white")
cmd.set("ray_opaque_background", 1)
cmd.set("ray_shadows", 0)
cmd.set("stick_radius", 0.15)
cmd.orient("a1")
cmd.zoom("a1", 7)
cmd.ray(1200, 1000)
cmd.png(os.path.join(FIGS, "pymol_overlay_icm_a1.png"), dpi=300)
print("✅ pymol_overlay_icm_a1.png")

# ======================================================================
# FIGURE 5: The 96-degree problem - both sites visible
# ======================================================================
cmd.reinitialize()
cmd.load(hmgb2_pdb, "hmgb2")
cmd.load(a1_pose, "a1")

cmd.hide("everything", "hmgb2")
cmd.show("cartoon", "hmgb2")
cmd.color("gray80", "hmgb2")

# ICM site (78-86) - gold surface
cmd.select("icm_site", "hmgb2 and resi 78-86")
cmd.show("surface", "icm_site")
cmd.color("gold", "icm_site")

# CRBN interface (112-128) - green surface
cmd.select("crbn_site", "hmgb2 and resi 112-128")
cmd.show("surface", "crbn_site")
cmd.color("limegreen", "crbn_site")

# Ligand
cmd.show("sticks", "a1")
cmd.color("orange", "a1 and elem C")
cmd.color("red", "a1 and elem O")
cmd.color("blue", "a1 and elem N")

# Distance between the two sites
cmd.select("icm_ca", "hmgb2 and resi 82 and name CA")
cmd.select("crbn_ca", "hmgb2 and resi 120 and name CA")
cmd.distance("site_gap", "icm_ca", "crbn_ca")
cmd.color("red", "site_gap")
cmd.set("dash_width", 3)

cmd.bg_color("white")
cmd.set("ray_opaque_background", 1)
cmd.set("ray_shadows", 1)
cmd.orient("hmgb2")
cmd.zoom("hmgb2", 2)
cmd.ray(1200, 1000)
cmd.png(os.path.join(FIGS, "pymol_96deg_problem.png"), dpi=300)
print("✅ pymol_96deg_problem.png")

# ======================================================================
# FIGURE 6: Lysines on HMGB2
# ======================================================================
cmd.reinitialize()
cmd.load(hmgb2_pdb, "hmgb2")
cmd.load(a1_pose, "a1")

cmd.hide("everything", "hmgb2")
cmd.show("cartoon", "hmgb2")
cmd.color("gray80", "hmgb2")

# All lysines as spheres
cmd.select("lysines", "hmgb2 and resn LYS")
cmd.show("spheres", "lysines")
cmd.color("purple", "lysines")
cmd.set("sphere_scale", 0.3, "lysines")

# Ligand
cmd.show("sticks", "a1")
cmd.color("orange", "a1 and elem C")
cmd.color("red", "a1 and elem O")
cmd.color("blue", "a1 and elem N")

cmd.bg_color("white")
cmd.set("ray_opaque_background", 1)
cmd.orient("hmgb2")
cmd.zoom("hmgb2", 1)
cmd.ray(1200, 1000)
cmd.png(os.path.join(FIGS, "pymol_lysines_hmgb2.png"), dpi=300)
print("✅ pymol_lysines_hmgb2.png")

cmd.quit()
print("\n" + "=" * 60)
print("ALL PYMOL RENDERINGS COMPLETE")
print("=" * 60)
