#!/usr/bin/env python3
"""
Generate PDB-based structure views and site plots (publication quality).
3D structural visualizations from actual PDB coordinates.
"""
import os, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.spatial import cKDTree

H2 = "/storage/saveena/protacpilot/ICM_HMGB2_Hypothesis_Testing/02_H2_ring_modified_ICM_nanobinder"
DOCK = os.path.join(H2, "analog_HMGB2_docking")
INPUTS = "/storage/saveena/protacpilot/ICM_HMGB2_Hypothesis_Testing/00_inputs"
FIGS = os.path.join(H2, "proof")

# Load HMGB2 structure
atoms = []
with open(os.path.join(INPUTS, "HMGB2_structures", "hmgb2_fixed_minim.pdb")) as f:
    for line in f:
        if line.startswith("ATOM"):
            atoms.append({
                'coords': np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])]),
                'resname': line[17:20].strip(), 'resnum': int(line[22:26]),
                'atomname': line[12:16].strip(),
                'element': line[76:78].strip()
            })

# CA trace (for cartoon representation)
ca_coords = np.array([a['coords'] for a in atoms if a['atomname'] == 'CA'])
ca_resnums = [a['resnum'] for a in atoms if a['atomname'] == 'CA']

# All atom coords for surface-like view
all_coords = np.array([a['coords'] for a in atoms])

# Load A1_4COOH docked pose
lig = []
with open(os.path.join(DOCK, "a1_4COOH_top_pose1.pdb")) as f:
    for line in f:
        if line.startswith("ATOM") or line.startswith("HETATM"):
            lig.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
lig = np.array(lig)

# Load ICM pose
icm = []
import subprocess
icm_pdb = "/tmp/icm_top1_v.pdb"
subprocess.run(["obabel", os.path.join(DOCK, "icm_parent_vina_out.pdbqt"), "-O", icm_pdb, "-f", "1", "-l", "1"],
              capture_output=True, timeout=30)
with open(icm_pdb) as f:
    for line in f:
        if line.startswith("ATOM") or line.startswith("HETATM"):
            icm.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
icm = np.array(icm)

# Key site centers
site_icm = np.mean([a['coords'] for a in atoms if 78 <= a['resnum'] <= 86], axis=0)  # ICM site
site_crbn = np.mean([a['coords'] for a in atoms if 112 <= a['resnum'] <= 128], axis=0)  # CRBN interface
hmgb2_center = np.mean(all_coords, axis=0)

def color_by_domain(resnum):
    if resnum <= 79: return '#4682B4'   # Box A
    elif resnum <= 163: return '#2E8B57'  # Box B
    else: return '#9370DB'               # C-tail

# ======================================================================
# FIGURE 1: HMGB2 structure with binding sites (3D)
# ======================================================================
print("[1/5] HMGB2 3D structure with binding sites...")

fig = plt.figure(figsize=(14, 9))
ax = fig.add_subplot(111, projection='3d')

# Plot CA trace (cartoon-like)
for i in range(len(ca_coords) - 1):
    c1, c2 = color_by_domain(ca_resnums[i]), color_by_domain(ca_resnums[i+1])
    ax.plot([ca_coords[i,0], ca_coords[i+1,0]],
            [ca_coords[i,1], ca_coords[i+1,1]],
            [ca_coords[i,2], ca_coords[i+1,2]],
            color=c1, lw=1.5, alpha=0.7)

# Plot A1_4COOH ligand (sticks)
ax.plot(lig[:,0], lig[:,1], lig[:,2], color='#FF4500', lw=3, alpha=0.9, label='A1_4COOH')
ax.scatter(lig[:,0], lig[:,1], lig[:,2], s=20, color='#FF4500', alpha=0.8)
# COOH highlight
ax.scatter(lig[-1,0], lig[-1,1], lig[-1,2], s=150, marker='D', color='gold', edgecolors='black', zorder=5)

# ICM site sphere (residues 78-86)
u = np.linspace(0, 2*np.pi, 20); v = np.linspace(0, np.pi, 20)
x = site_icm[0] + 4*np.outer(np.cos(u), np.sin(v))
y = site_icm[1] + 4*np.outer(np.sin(u), np.sin(v))
z = site_icm[2] + 4*np.outer(np.ones(20), np.cos(v))
ax.plot_wireframe(x, y, z, color='#FFD700', alpha=0.5, label='ICM site (78-86)')

# CRBN interface sphere (residues 112-128)
x = site_crbn[0] + 4*np.outer(np.cos(u), np.sin(v))
y = site_crbn[1] + 4*np.outer(np.sin(u), np.sin(v))
z = site_crbn[2] + 4*np.outer(np.ones(20), np.cos(v))
ax.plot_wireframe(x, y, z, color='#32CD32', alpha=0.5, label='CRBN interface (112-128)')

# Connection line showing 96°
ax.plot([site_icm[0], site_crbn[0]], [site_icm[1], site_crbn[1]], [site_icm[2], site_crbn[2]],
       color='red', lw=2, ls='--', label='96° apart')

# Labels
ax.text(site_icm[0], site_icm[1], site_icm[2]+5, 'ICM site\n78-86', fontsize=9, color='#8B6914', fontweight='bold')
ax.text(site_crbn[0], site_crbn[1], site_crbn[2]+5, 'CRBN interface\n112-128', fontsize=9, color='darkgreen', fontweight='bold')
ax.text(lig[-1,0], lig[-1,1], lig[-1,2]+1, 'COOH', fontsize=8, color='gold', fontweight='bold')

ax.set_title('HMGB2 3D Structure (PDB: hmgb2_fixed_minim.pdb)\nA1_4COOH bound at residues 78-86 | CRBN interface at 112-128 | 96° apart',
           fontsize=12, fontweight='bold')
ax.legend(loc='upper left', fontsize=9)
ax.set_xlabel('X (Å)'); ax.set_ylabel('Y (Å)'); ax.set_zlabel('Z (Å)')

plt.tight_layout()
plt.savefig(os.path.join(FIGS, "pdb_hmgb2_sites_3d.png"), dpi=200, bbox_inches='tight')
plt.close()
print("   ✅ pdb_hmgb2_sites_3d.png")

# ======================================================================
# FIGURE 2: Binding pocket close-up with residues (3D)
# ======================================================================
print("[2/5] Binding pocket 3D close-up...")

fig = plt.figure(figsize=(14, 10))
ax = fig.add_subplot(111, projection='3d')

# Focus on binding site region (box around ligand)
lig_center = np.mean(lig, axis=0)
box_min = lig_center - 12; box_max = lig_center + 12

# Protein atoms within box (as small spheres)
pocket_atoms = [a for a in atoms if np.all(a['coords'] > box_min) and np.all(a['coords'] < box_max)]
pocket_coords = np.array([a['coords'] for a in pocket_atoms])

# Color by element
elem_colors = {'C': '#808080', 'N': '#4169E1', 'O': '#E74C3C', 'S': '#F3C623'}
for elem, color in elem_colors.items():
    mask = np.array([a['element'] == elem for a in pocket_atoms])
    if mask.any():
        ax.scatter(pocket_coords[mask,0], pocket_coords[mask,1], pocket_coords[mask,2],
                  s=15, color=color, alpha=0.25)

# Ligand as thick sticks
ax.plot(lig[:,0], lig[:,1], lig[:,2], color='#FF8C00', lw=4, alpha=0.95)
ax.scatter(lig[:,0], lig[:,1], lig[:,2], s=40, color='#FF8C00', alpha=0.9)
ax.scatter(lig[-1,0], lig[-1,1], lig[-1,2], s=250, marker='D', color='gold', edgecolors='black', zorder=6)
ax.text(lig[-1,0], lig[-1,1], lig[-1,2]+1.5, 'COOH', fontsize=10, color='gold', fontweight='bold')

# Label key residues
key_res = [(78,'TYR','H-bond'), (85,'LYS','Salt bridge'), (82,'LYS','Basic'), (86,'LYS','Basic'), (83,'GLY','H-bond')]
for rnum, rname, note in key_res:
    res_atoms = [a['coords'] for a in atoms if a['resnum'] == rnum]
    if res_atoms:
        rc = np.mean(res_atoms, axis=0)
        ax.scatter(rc[0], rc[1], rc[2], s=100, color='#FF69B4', edgecolors='black', zorder=5)
        ax.text(rc[0], rc[1]+2, rc[2], f'{rname}{rnum}\n({note})', fontsize=8, color='#FF69B4', fontweight='bold')

ax.set_title('A1_4COOH Binding Pocket 3D View\nProtein = colored spheres | Ligand = orange sticks | Key residues labeled',
           fontsize=12, fontweight='bold')
ax.set_xlabel('X (Å)'); ax.set_ylabel('Y (Å)'); ax.set_zlabel('Z (Å)')
ax.view_init(elev=25, azim=-60)

plt.tight_layout()
plt.savefig(os.path.join(FIGS, "pdb_pocket_3d.png"), dpi=200, bbox_inches='tight')
plt.close()
print("   ✅ pdb_pocket_3d.png")

# ======================================================================
# FIGURE 3: ICM vs A1_4COOH overlay (3D)
# ======================================================================
print("[3/5] ICM vs A1_4COOH pose overlay...")

fig = plt.figure(figsize=(13, 9))
ax = fig.add_subplot(111, projection='3d')

# Protein CA trace (light)
for i in range(len(ca_coords) - 1):
    ax.plot([ca_coords[i,0], ca_coords[i+1,0]],
            [ca_coords[i,1], ca_coords[i+1,1]],
            [ca_coords[i,2], ca_coords[i+1,2]],
            color='#B0C4DE', lw=1, alpha=0.4)

# ICM pose (red)
ax.plot(icm[:,0], icm[:,1], icm[:,2], color='#E74C3C', lw=3, alpha=0.9, label='ICM (parent, -5.75)')
ax.scatter(icm[:,0], icm[:,1], icm[:,2], s=25, color='#E74C3C', alpha=0.8)

# A1_4COOH pose (blue)
ax.plot(lig[:,0], lig[:,1], lig[:,2], color='#4169E1', lw=3, alpha=0.9, label='A1_4COOH (-11.22)')
ax.scatter(lig[:,0], lig[:,1], lig[:,2], s=25, color='#4169E1', alpha=0.8)

# COOH
ax.scatter(lig[-1,0], lig[-1,1], lig[-1,2], s=250, marker='D', color='gold', edgecolors='black', zorder=6)
ax.text(lig[-1,0], lig[-1,1], lig[-1,2]+1.5, 'COOH\n(new)', fontsize=9, color='gold', fontweight='bold')

ax.set_title('Pose Overlay: ICM (red) vs A1_4COOH (blue) in HMGB2\nSame binding site, A1_4COOH extends COOH toward solvent',
           fontsize=12, fontweight='bold')
ax.legend(fontsize=10)
ax.set_xlabel('X (Å)'); ax.set_ylabel('Y (Å)'); ax.set_zlabel('Z (Å)')
ax.view_init(elev=20, azim=-45)

plt.tight_layout()
plt.savefig(os.path.join(FIGS, "pdb_pose_overlay_3d.png"), dpi=200, bbox_inches='tight')
plt.close()
print("   ✅ pdb_pose_overlay_3d.png")

# ======================================================================
# FIGURE 4: Surface view (van der Waals-like projection)
# ======================================================================
print("[4/5] Protein surface + ligand view...")

# Use 2D projection with alpha-blended density for surface-like view
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.5))

# Panel 1: XZ view
ax1.set_title('HMGB2 Surface (XZ projection) + A1_4COOH\n(Cyan = protein surface, Orange = ligand)', fontsize=11, fontweight='bold')
# Sample protein atoms and plot with transparency (surface-like)
ax1.scatter(all_coords[::5, 0], all_coords[::5, 2], s=3, c='#87CEEB', alpha=0.15)
# CA trace
ax1.plot(ca_coords[:, 0], ca_coords[:, 2], color='#4682B4', lw=1.5, alpha=0.5)
# Ligand
ax1.plot(lig[:, 0], lig[:, 2], color='#FF8C00', lw=3, alpha=0.95)
ax1.scatter(lig[:, 0], lig[:, 2], s=30, color='#FF8C00')
ax1.scatter(lig[-1, 0], lig[-1, 2], s=150, marker='D', color='gold', edgecolors='black', zorder=6)
# Sites
ax1.scatter(site_icm[0], site_icm[2], s=300, marker='o', color='#FFD700', alpha=0.5, edgecolors='#8B6914')
ax1.scatter(site_crbn[0], site_crbn[2], s=300, marker='o', color='#32CD32', alpha=0.5, edgecolors='darkgreen')
ax1.text(site_icm[0]+1, site_icm[2]+2, 'ICM site 78-86', fontsize=9, color='#8B6914', fontweight='bold')
ax1.text(site_crbn[0]+1, site_crbn[2]+2, 'CRBN 112-128', fontsize=9, color='darkgreen', fontweight='bold')
ax1.text(lig[-1,0], lig[-1,2], 'COOH', fontsize=9, color='gold', fontweight='bold')
ax1.set_xlabel('X (Å)'); ax1.set_ylabel('Z (Å)')
ax1.grid(alpha=0.2)

# Panel 2: YZ view
ax2.set_title('HMGB2 Surface (YZ projection) + A1_4COOH', fontsize=11, fontweight='bold')
ax2.scatter(all_coords[::5, 1], all_coords[::5, 2], s=3, c='#87CEEB', alpha=0.15)
ax2.plot(ca_coords[:, 1], ca_coords[:, 2], color='#4682B4', lw=1.5, alpha=0.5)
ax2.plot(lig[:, 1], lig[:, 2], color='#FF8C00', lw=3, alpha=0.95)
ax2.scatter(lig[:, 1], lig[:, 2], s=30, color='#FF8C00')
ax2.scatter(lig[-1, 1], lig[-1, 2], s=150, marker='D', color='gold', edgecolors='black', zorder=6)
ax2.scatter(site_icm[1], site_icm[2], s=300, marker='o', color='#FFD700', alpha=0.5, edgecolors='#8B6914')
ax2.scatter(site_crbn[1], site_crbn[2], s=300, marker='o', color='#32CD32', alpha=0.5, edgecolors='darkgreen')
ax2.text(site_icm[1]+1, site_icm[2]+2, 'ICM site', fontsize=9, color='#8B6914', fontweight='bold')
ax2.text(site_crbn[1]+1, site_crbn[2]+2, 'CRBN interface', fontsize=9, color='darkgreen', fontweight='bold')
ax2.set_xlabel('Y (Å)'); ax2.set_ylabel('Z (Å)')
ax2.grid(alpha=0.2)

plt.tight_layout()
plt.savefig(os.path.join(FIGS, "pdb_surface_views.png"), dpi=200, bbox_inches='tight')
plt.close()
print("   ✅ pdb_surface_views.png")

# ======================================================================
# FIGURE 5: Site residue mapping (sequence map)
# ======================================================================
print("[5/5] Site residue sequence map...")

fig, ax = plt.subplots(figsize=(14, 4))

# Domain boundaries
domains = [(1, 79, 'Box A', '#4682B4'), (80, 94, 'Linker', '#D3D3D3'),
           (95, 163, 'Box B', '#2E8B57'), (164, 209, 'C-tail', '#9370DB')]

# Draw domain bars
y = 0.5
for start, end, name, color in domains:
    ax.barh(y, end-start+1, left=start-1, height=0.5, color=color, alpha=0.6, edgecolor='gray')
    ax.text((start+end)/2, y+0.1, name, ha='center', va='center', fontsize=8, fontweight='bold', color='white')

# Highlight sites
ax.barh(y+0.75, 86-78+1, left=77, height=0.35, color='#FFD700', alpha=0.8, edgecolor='#DAA520')
ax.text(82, y+0.95, 'ICM site (78-86)', ha='center', fontsize=9, fontweight='bold', color='#8B6914')
ax.barh(y+0.75, 128-112+1, left=111, height=0.35, color='#32CD32', alpha=0.8, edgecolor='darkgreen')
ax.text(120, y+0.95, 'CRBN interface (112-128)', ha='center', fontsize=9, fontweight='bold', color='darkgreen')

# Mark lysines
lys_res = sorted(set(a['resnum'] for a in atoms if a['resname'] == 'LYS'))
for k in lys_res:
    ax.plot(k, y+0.2, 'v', color='purple', markersize=5, alpha=0.7)
ax.text(2, y-0.15, '▼ = lysines (40 total)', fontsize=8, color='purple')

# Tag insertion points (S5)
ax.plot(1, y+1.6, '*', color='#8E44AD', markersize=18)
ax.text(5, y+1.75, 'S5: dTAG insert (N-term)', fontsize=8, color='#8E44AD', fontweight='bold')
ax.plot(209, y+1.6, '*', color='#E74C3C', markersize=18)
ax.text(180, y+1.75, 'or C-term', fontsize=8, color='#E74C3C')

ax.set_xlim(0, 215); ax.set_ylim(-0.5, 2.6)
ax.set_xlabel('HMGB2 residue position', fontsize=12)
ax.set_yticks([])
ax.set_title('HMGB2 Domain Map with Key Sites\n(ICM site 78-86 | CRBN interface 112-128 | 40 lysines | dTAG insertion points)',
           fontsize=12, fontweight='bold')
ax.grid(axis='x', alpha=0.2)

plt.tight_layout()
plt.savefig(os.path.join(FIGS, "pdb_site_residue_map.png"), dpi=200, bbox_inches='tight')
plt.close()
print("   ✅ pdb_site_residue_map.png")

print("\n" + "=" * 70)
print("ALL PDB STRUCTURE VIEWS GENERATED")
print("=" * 70)
print("Files in:", FIGS)
