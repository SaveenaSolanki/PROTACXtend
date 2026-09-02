# Module 2 — Lysine Ubiquitination Feasibility Scorer

**Entry point:** `score_lysine_ubiquitination(structure_paths, poi_chain, e2_catalytic={...}, ...)`

Scores whether POI lysines in PROTAC ternary-complex structures are geometrically
competent for E2-mediated ubiquitination — the "is the lysine where the E2 can
reach it?" gate between ternary geometry (Module 1 inputs) and degradation
outcome (Modules 4–5).

## Inputs
* `structure_paths` — one or more ternary-pose PDB files (≥2 ⇒ ensemble consistency)
* `poi_chain` — POI chain evaluated
* `e2_catalytic` — `{chain, residue_number, residue_name="CYS"}` E2 catalytic
  cysteine (thioester/active-site proxy). **Required**: if absent the scorer
  returns REJECT rather than guessing geometry.
* cutoffs — `distance_cutoff_angstrom` (15), `orientation_cutoff_deg` (75),
  `sasa_cutoff_angstrom2` (10), `clash_cutoff_angstrom` (2.4),
  `n_sasa_dots` (92), `probe_radius_angstrom` (1.4)

## Features (per lysine, per pose)
* **distance** — NZ(ε-amine) … E2 catalytic Sy (Å)
* **SASA** — numeric **Shrake–Rupley** (1973) dot-surface solvent accessibility of
  NZ and the lysine side chain (real burial/occlusion, not a sequence proxy)
* **orientation** — approach angle at NZ between the side-chain anchor (CB→NZ)
  and the attack vector (NZ→Sy)
* **steric** — non-bonded contacts below a vdW clash cutoff
* **ensemble** — productive-pose fraction & mean score across poses

**Productive** geometry: distance ≤ cutoff AND NZ-SASA ≥ cutoff AND angle ≤ cutoff
AND no clash.

## Outputs
`LysineUbiquitinationResult`: `ranked_lysines[]` (residue, mean score,
productive-pose fraction, per-pose geometries), `productive_pose_fraction`,
`ubiquitination_feasibility_score` (0–1) + `feasibility_label`
(`feasible|marginal|infeasible`), `n_poses`, `n_lysines`, warnings, feature
metadata; versioned `model` id.

## Agent integration
`synglue_agent.tools.lysine_ubiquitination_tool.run_lysine_ubiquitination(payload)` —
JSON in/out, graph-safe.

See LIMITATIONS.md, VALIDATION.md, REFERENCES.md.
