# A1_4COOH PROTAC: Complete Design and Analysis

## The Design

| Component | Molecule | MW | Exit Vector |
|-----------|----------|----|-------------|
| Warhead | A1_4COOH (4-carboxyphenyl-ICM) | 421 Da | COOH at N-phenyl para → **solvent-exposed** |
| Linker | C8-PEG4 | ~250 Da | Effective span: 13.6 Å |
| E3 ligand | Pomalidomide | 273 Da | NH2 at phthalimide 4-position |
| **Total** | **A1_4COOH–C8-PEG4–Pomalidomide** | **~944 Da** | |

## Geometric Screen Results

### Exit vector: A1_4COOH COOH (N-phenyl para) vs OH27 (original)

| Metric | OH27 (original, wrong) | A1_4COOH (this work, correct) |
|--------|----------------------|------------------------------|
| Exit vector position | OH at (2.57, 12.32, 0.29) | COOH at (-3.25, 14.01, 11.00) |
| Direction | Points INTO HMGB2 (105° away) | Points OUTWARD from HMGB2 |
| Closest gap to CRBN | 10.83 Å | **8.27 Å** |
| Improvement vs OH27 | — | **2.6 Å closer** |

### Passing poses by linker length

| Linker | Effective span | A1_4COOH passes | OH27 passes | Improvement |
|--------|---------------|-----------------|-------------|-------------|
| C8-PEG4 | 13.6 Å | **8/3600** (0.2%) | 0/3600 | ∞ |
| PEG8 | 15.7 Å | **12/3600** (0.3%) | 0/3600 | ∞ |
| C14-PEG5 | 18.9 Å | **16/3600** (0.4%) | 0/3600 | ∞ |

### Verdict

✅ **IMPROVED over OH27** — 8–16 passes vs 0
⚠️ **Still marginal** — <1% pass rate

The COOH at the N-phenyl para position IS the correct exit vector (Lee 2014 proven, our screen confirms improvement). But ICM's binding site on HMGB2 is fundamentally on the far side from CRBN's approach direction. Even the best exit vector still requires >13 Å linker span.

## Files Generated

| File | Description |
|------|-------------|
| `a1_4COOH.mol2` | A1_4COOH warhead in HMGB2 binding pocket |
| `pomalidomide.mol2` | Pomalidomide in CRBN binding pocket |
| `screen_results.json` | Full geometric screen data |
| `p4ward_run/` | P4ward input files ready for execution |
| `p4ward_run/config.ini` | P4ward configuration |
| `p4ward_run/run_p4ward.sh` | Bash script to launch P4ward |

## Next Step

Run P4ward with these inputs:
```bash
cd PROTAC_design/p4ward_run && bash run_p4ward.sh
```
