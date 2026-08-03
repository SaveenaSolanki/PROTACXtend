HMGB2–CRBN P4ward PDB evidence package

1. input_structures/
   These are the input/prepared structures used for P4ward:
   - hmgb2_fixed_minim.pdb
   - crbn_fixed_minim.pdb
   - inflachromene_derivative.mol2
   - thalidomide_analog.mol2

2. failed_docked_poses/
   These are reconstructed representative docked orientations that failed the ligand-distance filter.
   They should be described as "failed docked poses", not viable ternary complexes.

3. logs_and_config/
   These contain the raw computational evidence:
   - p4ward_run.log
   - p4ward_config.ini
   - megadock_scores.out
   - key_log_evidence.txt

Main result:
P4ward sampled 3600 HMGB2–CRBN docking orientations.
0 passed the ligand-distance filter.
Closest gap = 10.83 Å.
Current linker max span = 0.74 Å.
Therefore, the current linker is ~14.6x too short.

Interpretation:
This supports linker/geometry failure.
It does not prove HMGB2 is intrinsically non-degradable.
