# 00_inputs — Starting Structures and Reference Data

## HMGB2_structures/
| File | Source | Notes |
|------|--------|-------|
| `hmgb2_fixed_minim.pdb` | AlphaFold + P4ward minimization | Full-length HMGB2 (1-209 aa), Box A (9-79), Box B (95-163), C-tail (164-209) |
| `hmgb2_pose_1655.pdb` | Reference frame (Pose #1655) | Same structure, kept in same coordinate frame as CRBN Pose #1655 |

## CRBN_DDB1_structures/
| File | Source | Notes |
|------|--------|-------|
| `crbn_fixed_minim.pdb` | Crystal structure + P4ward minimization | CRBN with DDB1 (chains A+B), includes CRL4 complex components |
| `crbn_pose_1655.pdb` | Transformed by MegaDock rotation | CRBN in the Pose #1655 orientation relative to HMGB2 |

## ICM_and_analogs/
| File | Source | Notes |
|------|--------|-------|
| `inflachromene_derivative.mol2` | From docking prep | ICM with MOL2 atom types and Gasteiger charges. 30 atoms, 2 OH groups (atoms 27, 29) |
| `icm_structure.png` | RDKit 2D depiction | ICM structure with atom numbering |

**ICM SMILES:** `CC1(C2=CCN3C(=O)N(C(=O)N3C2C4=C(C=CC(=C4O)C1)O)C5=CC=CC5)`  
**MW:** 365.4 Da, **Formula:** C₂₀H₁₉N₃O₄

## known_CRBN_glue_controls/
| File | Source | Notes |
|------|--------|-------|
| `thalidomide_analog.mol2` | PDB 4CI1-derived | Thalidomide in CRBN tri-Trp binding pocket. Used as positive control for CRBN binding pose |
