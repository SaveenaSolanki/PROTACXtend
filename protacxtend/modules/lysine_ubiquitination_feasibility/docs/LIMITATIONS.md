# Limitations — Lysine Ubiquitination Feasibility Scorer

1. Static geometry baseline: no E2~Ub thioester dynamics, E3/E2 reorientation,
   processivity or catalytic rate modelling.
2. E2 position must be present in the input structure (ternary + E2/E3 machinery
   or a positioned E2~Ub proxy); the scorer refuses to guess otherwise.
3. Approach-angle is an approximate vector proxy (side-chain anchor vs attack
   vector); real donor–acceptor geometry and ubiquitin positioning are richer.
4. SASA is numeric Shrake–Rupley on heavy atoms (no explicit H); protonation,
   ions and crystal contacts are ignored.
5. Ensemble consistency assumes poses are comparable (same lysine numbering);
   no clustering/free-energy ranking of poses is performed.
6. No ML: an advanced learned model is deferred until a curated dataset of
   ternary complexes with validated ubiquitination outcomes is assembled
   (spec Step 4/5 policy — no model where no data).
7. Synthesised validation fixtures, not measured biological structures; real-PDB
   benchmarking pending.
