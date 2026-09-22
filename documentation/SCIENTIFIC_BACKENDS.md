# Scientific Backends — Capability First, Implementation Second

PROTACXtend's default installation contains **no commercial, paid, web-only or
non-redistributable scientific engine as a required capability**. The agent asks
for a *capability*, and a resolver selects the best **locally available,
licence-compatible** implementation.

- Package: `protacxtend/scientific_backends/`
- Entry points: `protacxtend backends`, `protacxtend backends --action matrix`
- Facade: `from protacxtend.scientific_backends import ligand_docking, run_molecular_dynamics, …`

---

## 1. Capability list

| Capability | Primary free backend | Fallbacks |
|---|---|---|
| `chemistry` | RDKit | Open Babel (GPL, local) |
| `conformer_generation` | RDKit ETKDG | OpenEye OMEGA *(licence)* |
| `protein_preparation` | PDBFixer/OpenMM | Biopython clean-up |
| `protein_structure` | local PDB → RCSB/AlphaFold (free, network-gated) | — |
| `pocket_detection` | fpocket if installed, else grid-burial geometry | — |
| `ligand_docking` | **consensus**: Vina + optional GNINA/DiffDock | geometric placement |
| `ppi_docking` | **LightDock** | geometric orientation search |
| `ternary_docking` | local orientation sampling + OpenMM | — |
| `molecular_dynamics` | **OpenMM** (CPU/CUDA/OpenCL) | minimization-only |
| `md_analysis` | **MDAnalysis** | numpy single-structure geometry |
| `interaction_energy` | OpenMM NonbondedForce decomposition | structural surrogate |
| `binding_energy` | gmx_MMPBSA → OpenMM interaction → surrogate | — |
| `admet` | RDKit descriptors (+ local ML if present) | — |
| `interaction_fingerprint` | geometry fingerprint (H-bond/salt/π/clash/metal) | — |
| `linker_analysis` | RDKit conformers (contour, E2E, strain, dihedrals) | — |
| `protac_scoring` | local linker + interface + anchor tracking | — |
| `molecular_glue_scoring` | apo-vs-bound interface delta | — |
| `metabolite_ppi_scoring` | `evaluate_metabolite_assisted_ppi` | — |
| `candidate_ranking` | Pareto/NSGA-II | — |

### Hardened local stack (verified in this environment)

* **Ligand parameterization** — OpenFF (SMIRNOFF + MMFF94/Gasteiger charges) → GAFF
  (`openmmforcefields`) → generic, with provenance on every MD result. A dedicated
  `md-openff` environment (`openff-2.2.0` + OpenMM) is preferred when registered;
  otherwise GAFF in the main scientific env is used.
* **MD platform fallback** — CUDA → OpenCL → CPU is attempted at context creation,
  so a driver/CUDA mismatch degrades gracefully instead of failing.
* **Docking** — Vina (CPU), **GNINA** (CNN scores, CUDA libs auto-resolved),
  **DiffDock** (GPU diffusion, repo + weights), combined with **Borda rank
  consensus** (raw scores are reported per engine and never averaged).
* **PPI docking** — **LightDock** swarm docking (inputs sanitized to heavy atoms,
  no OXT) with restraint support; geometric fallback is restraint-aware.
* **MD** — OpenMM with minimization, NVT/NPT, restrained/unrestrained, implicit/
  explicit, CPU/CUDA/OpenCL, DCD/PDB writers, periodic checkpoint/restart, replicas.
* **MD analysis** — per-frame SASA + buried SASA (mdtraj) and explicit
  target–ligand / ligand–partner / target–partner interface series; blocked
  convergence diagnostics and thermodynamic QC.
* **Optional MD extensions** — GROMACS (`gmx 2026.3`) + `gmx_MMPBSA 1.7.0`
  (AmberTools 23.6) for MM/PBSA; alchemical FEP and enhanced sampling are opt-in
  and refuse to run until the standard pipeline is validated.
* **Safe failure** — system validation rejects unsupported metals/cofactors and
  membrane-like structures before simulation unless explicitly overridden.

## 2. Backend contract

Every backend declares (see `registry.py`):

```
name · capabilities · licence · redistributable · requires_gpu ·
requires_external_binary · requires_network · academic_only ·
commercial_use_restricted · priority · health_check · version · citation
```

The resolver filters by `LicensePolicy` (default: permissive + copyleft, local
only), sorts by priority, and degrades to the next backend on failure.

## 3. Licence gate

Default policy (`licenses.DEFAULT_POLICY`) allows permissive open source and,
locally, copyleft; it rejects commercial, academic-only, web-service and unknown
licences. Restricted backends are registered under
`protacxtend/scientific_backends/optional_backends/` and, if explicitly invoked,
return `LICENSE_REQUIRED` — never a silent failure.

Opt-in flags (still never auto-bundled):

```bash
PROTACXTEND_ALLOW_COMMERCIAL=1
PROTACXTEND_ALLOW_ACADEMIC=1
PROTACXTEND_ALLOW_WEB=1
PROTACXTEND_ALLOW_NETWORK=1
```

## 4. Evidence tiers

`TIER_0_GEOMETRY` → `TIER_1_MINIMIZED` → `TIER_2_DOCKED` → `TIER_3_SHORT_MD` →
`TIER_4_REPLICATE_MD` → `TIER_5_ENDPOINT_FREE_ENERGY`.

Every result exposes its tier; a complex is never called "stable" from a single
minimized structure (the ternary verdict is `tentative_*` below TIER_3).

## 5. Result metadata

```json
{
  "capability": "molecular_dynamics",
  "backend": "openmm",
  "backend_version": "8.6.1",
  "evidence_tier": "TIER_4_REPLICATE_MD",
  "approximation": false,
  "gpu_used": true,
  "runtime_seconds": 0.0,
  "license_class": "open_source_permissive",
  "citations": [],
  "warnings": [],
  "status": "success",
  "method_label": "OPENMM_MD"
}
```

## 6. GPU fallback

| GPU backend | CPU / lower-compute fallback |
|---|---|
| DiffDock (GPU) | AutoDock Vina (CPU) |
| GNINA (GPU/CPU) | AutoDock Vina |
| OpenMM CUDA | OpenMM OpenCL → OpenMM CPU → minimization |
| long MD | short MD → minimization |
| gmx_MMPBSA | OpenMM interaction energy → structural surrogate |

## 7. Model weights

`models.py` registers name, version, URL, SHA-256, licence, size and VRAM.
Weights are lazy-downloaded, checksum-verified and cached; a model whose licence
the policy rejects is never downloaded. Local committed models (TACK) resolve
directly from package data.

## 8. Installation strategy (modular envs)

```bash
scripts/setup_scientific_envs.sh              # dry-run plan + health
scripts/setup_scientific_envs.sh --execute    # create chem/docking/ppi/md/analysis/ml
```

Small envs (`core`, `chem`, `docking`, `ppi`, `md`, `analysis`, `ml`; optional
`gromacs`, `mmpbsa`) are registered via `PROTACXTEND_TOOLKIT_ENVS` and resolved
across by the toolkit detector.

## 9. Health checks

```bash
protacxtend doctor      # LLM status + scientific backend readiness
protacxtend backends    # readiness + capability matrix
protacxtend backends --action matrix --json
```

Example readiness output:

```
RDKit               READY  2026.03.4
Open Babel          READY
PDBFixer/OpenMM     READY  1.12.0
OpenMM              READY GPU  8.6.1
MDAnalysis          READY  2.10.0
MDTraj              READY
DiffDock            READY
AutoDock Vina       READY
GNINA               READY
LightDock           READY
Pocket geometry     READY
GROMACS             READY
gmx_MMPBSA          READY
Commercial engines  DISABLED
Web-only engines    DISABLED
Academic-only engines DISABLED
```

### Environment registration

Binary-only environments (e.g. fpocket + GNINA in one conda prefix) are
supported via a `"bin"` entry in `~/.protacxtend/toolkit_envs.json`; Python
environments use `"python"`. The detector probes imports across all of them and
executables across every `bin/` directory.
