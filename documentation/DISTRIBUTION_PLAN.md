# PROTACXtend Distribution & Toolkit Packaging Plan

_Status: implemented. Scripts, profiles and the version source-of-truth
described here exist in the repository._

This document is the authoritative plan for **packing, moving, running,
testing and distributing** the entire PROTACXtend platform — code, scientific
data, external toolkit and its version truth.

---

## 1. Objectives

1. One reproducible artifact that installs and runs on a clean machine.
2. Every shipped tool, dataset and dependency pinned to an exact version with
   a content hash, recorded in one XLSX + one Markdown file.
3. The external scientific toolkit is treated as a **multi-environment**
   concern: tools may live in the current interpreter, a project conda env, or
   a dedicated toolkit venv, and all of them are detected and callable.
4. Commercial, web-only and repo+weights tools are never faked — they are
   classified, documented and reported as unavailable with the exact reason.

---

## 2. What ships

| Payload | Location in repo | In wheel? | In release bundle? |
|---|---|---|---|
| Python code (CLI/API/UI/agents/tools) | `protacxtend/` | ✅ | ✅ |
| Scientific data (curated CSVs, TACK/Chemprop models, linker data, Agent_Toolkit.xlsx) | `protacxtend/data/` | ✅ (package data) | ✅ |
| Large research assets (retrosynthesis models, cloned repos) | `data/` | ❌ (too large) | via `scripts/bootstrap_assets.sh` |
| Toolkit registry + provisioning catalog | `protacxtend/tools/`, `protacxtend/toolkit/` | ✅ | ✅ |
| Version truth | `TOOLKIT_TRUTH.md`, `analysis/inventory/PROTACXtend_Toolkit_Truth.xlsx` | ❌ | ✅ |
| Capability inventory | `analysis/inventory/` | ❌ | ✅ |
| Audits | `analysis/audit/` | ❌ | ✅ |
| Install scripts | `scripts/install.sh`, `scripts/package_release.sh`, `scripts/distribution_smoke.sh` | ❌ | ✅ |
| Container | `Dockerfile`, `deploy/` | ❌ | ✅ |

Data that is too large for a wheel is restored by a versioned bootstrap script
that records SHA-256 checksums (`ASSET_MANIFEST.checksums.json`).

---

## 2b. Capability-first scientific backends

The default installation ships **no commercial, paid, web-only or
non-redistributable engine as a required capability**. The agent asks for a
capability (``ligand_docking``, ``molecular_dynamics``, ``admet``, …) and the
resolver in ``protacxtend/scientific_backends/`` picks the best locally
available, licence-compatible free backend. Commercial/academic/web engines are
registered only as optional adapters that return ``LICENSE_REQUIRED``.

```bash
protacxtend backends                 # readiness + capability matrix
protacxtend backends --action matrix --json
protacxtend doctor                   # LLM status + backend readiness
scripts/setup_scientific_envs.sh --execute   # modular chem/docking/md/ml envs
```

See [`SCIENTIFIC_BACKENDS.md`](SCIENTIFIC_BACKENDS.md) for the capability list,
backend contract, evidence tiers, result metadata, GPU fallbacks and model
registry.

---

## 3. Distribution artifacts

### 3.1 Python wheel + sdist
```bash
scripts/package_release.sh                 # wheel + sdist + truth + checksums
scripts/package_release.sh --tar           # additionally a .tar.gz bundle
```
Output: `dist/protacxtend-<version>-<UTC timestamp>/`
```
artifacts/   protacxtend-<version>-py3-none-any.whl, .tar.gz
docs/        TOOLKIT_TRUTH.md, PROTACXtend_Toolkit_Truth.xlsx,
             INVENTORY_AUDIT.md, ESCALATION_AUDIT.md
inventory/   PROTACXtend_Capability_Inventory.xlsx + all CSV sheets
repro/       requirements.txt, pyproject.toml, MANIFEST.in, pip-freeze.txt
RELEASE_MANIFEST.json   tool + dataset + dependency versions
SHA256SUMS              checksums for every file in the bundle
```

### 3.2 Offline bundle
`--tar` produces a single `protacxtend-<version>-<stamp>.tar.gz` containing the
release directory, suitable for `scp`/USB transfer to an air-gapped host.

### 3.3 Container
`Dockerfile` (API by default) and `deploy/docker-compose.yml` provide a
reproducible server image. The toolkit profile can be baked in:
```dockerfile
RUN pip install "protacxtend[toolkit]"
```

---

## 4. Install profiles

| Profile | Command | Contents |
|---|---|---|
| minimal | `pip install protacxtend` | CLI, registries, toolkit truth, deterministic core |
| ui | `pip install "protacxtend[ui]"` | + Streamlit workspace |
| api | `pip install "protacxtend[api]"` | + FastAPI/uvicorn |
| tui | `pip install "protacxtend[tui]"` | + Textual/Rich TUI |
| toolkit-chem | `pip install "protacxtend[toolkit-chem]"` | OpenBabel, Meeko, mmpdb, RDChiral, RXNMapper, CReM, GuacaMol, PyTDC |
| toolkit-structure | `pip install "protacxtend[toolkit-structure]"` | OpenMM, PDBFixer, PropKa, PDB2PQR |
| toolkit-retro | `pip install "protacxtend[toolkit-retro]"` | AiZynthFinder, OpenNMT-py |
| toolkit-ml | `pip install "protacxtend[toolkit-ml]"` | Chemprop, DeepChem, ESM-2 |
| toolkit-nlp | `pip install "protacxtend[toolkit-nlp]"` | SciSpacy |
| toolkit | `pip install "protacxtend[toolkit]"` | union of the pip-provisionable toolkit |
| full | `pip install "protacxtend[full]"` | UI + API + complete pip toolkit |
| scientific | `bash scripts/install.sh --profile scientific` | rdkit/chemprop/torch stack |
| full installer | `bash scripts/install.sh --profile full` | everything above |

> **Conflict note.** `guacamol` and `PyTDC` declare `rdkit-pypi`, which can
> shadow the conda/official `rdkit`. Install the toolkit into a dedicated venv
> (`protacxtend[toolkit]`) or reinstall `rdkit` afterwards. The provisioning
> engine installs into the `protacpilot` conda env by default and re-verifies
> `rdkit` afterwards.

---

## 5. Toolkit environment strategy

Tools are resolved across every registered interpreter:

```
current interpreter ─┐
protacpilot conda ───┼──► protacxtend.toolkit.environments
toolkit-venv ────────┤      (batched, cached index)
PROTACXTEND_TOOLKIT_ENVS ─┘
```

Register additional environments:
```bash
protacxtend toolkit --action envs
# or edit ~/.protacxtend/toolkit_envs.json
export PROTACXTEND_TOOLKIT_ENVS="myconda=/path/to/env/bin/python"
```

Cross-environment execution is provided by
`protacxtend.toolkit.bridge.call_first_available`, so an agent running in the
base interpreter can still run AiZynthFinder from the `protacpilot` env.

---

## 6. Version truth & reproducibility

Two files are generated together and must be regenerated on every release:

* `TOOLKIT_TRUTH.md` — human-readable, in-depth.
* `analysis/inventory/PROTACXtend_Toolkit_Truth.xlsx` — machine-readable,
  8 sheets: Summary, Tools, Tool_Versions, Agent_Tools, Datasets,
  Dependencies, Capabilities, Distribution_Matrix.

Dataset identity uses a **content fingerprint**:

| kind | meaning |
|---|---|
| `sha256:full` | full SHA-256 (files < 50 MB) |
| `sha256:partial` | first + last 1 MB + size (large files) |
| `sha256:tree` | relative path + size fingerprint (directories) |

Reproduce:
```bash
protacxtend toolkit --action truth          # XLSX + MD
protacxtend toolkit --action plan           # provisioning plan
protacxtend toolkit --action provision --mode install --categories molecular_ml
protacxtend toolkit --action verify         # functional smoke tests
protacxtend toolkit --action manifest       # append-only install/verify record
```

---

## 7. Move & run procedure (target machine)

```bash
# 1. transfer
scp protacxtend-<version>-<stamp>.tar.gz user@host:/opt/
# 2. unpack + verify checksums
tar -xzf protacxtend-<version>-<stamp>.tar.gz -C /opt/
cd /opt/protacxtend-<version>-<stamp> && sha256sum -c SHA256SUMS
# 3. install
python3 -m venv /opt/pxt-venv
/opt/pxt-venv/bin/pip install artifacts/protacxtend-*.whl
/opt/pxt-venv/bin/pip install "protacxtend[toolkit]"   # optional external toolkit
# 4. restore large assets (network required)
/opt/pxt-venv/bin/python -c "import protacxtend; print(protacxtend.__file__)"
bash scripts/bootstrap_assets.sh
# 5. verify
/opt/pxt-venv/bin/protacxtend doctor
/opt/pxt-venv/bin/protacxtend toolkit --action verify
bash scripts/distribution_smoke.sh artifacts/protacxtend-*.whl
```

---

## 8. Test matrix

| Layer | Command | What it proves |
|---|---|---|
| Unit/integration | `pytest -q` | internal modules + registries |
| CLI smoke | `scripts/ci_smoke.py` | CLI entry points load |
| Agentic E2E | `python scripts/e2e_agentic.py` | 7-layer runtime + tool dispatch |
| Toolkit plan | `protacxtend toolkit --action plan` | provisioning classification for 115 tools |
| Toolkit verify | `protacxtend toolkit --action verify` | functional smoke test per installed tool |
| Capability audit | `python analysis/generate_audit.py` | escalation readiness matrix |
| Inventory | `python analysis/generate_inventory.py` | sheets + 13 plots |
| Truth | `protacxtend toolkit --action truth` | XLSX + MD version pinning |
| Distribution | `scripts/distribution_smoke.sh` | clean-venv wheel install + package data |
| Network | `pytest -m network` | live API/tool reachability (opt-in) |

---

## 9. Known limits (honest, by construction)

* **Commercial/licensed (13):** GOLD, Glide, MOE Dock, ICM-Pro, Schrödinger
  LigPrep/Epik/Desmond, OpenEye OMEGA, Gaussian, CHARMM, NameRxn, Pipeline
  Pilot, Proteome Discoverer/MaxQuant, ICM.
* **Web-only (13):** Mol*, HADDOCK, ClusPro, PatchDock, SwissADME, ADMETlab,
  pkCSM, ProTox-II, SureChEMBL, Lens.org, Google Patents, PubTator, IBM RXN.
* **Repo + trained weights (21):** DeepPROTACs, PROTAC-STAN, DegradeMaster,
  EquiDock, DiffLinker, SyntaLinker, MolDQN, GROVER, ChemBERTa, MolFormer,
  Uni-Mol, ProtT5, PRosettaC, AlphaFold-Multimer, DeLinker, REINVENT,
  LinkInvent, RAscore, SCScore, ChemDataExtractor, DeepPurpose.
* **Capabilities with no local fallback:** `binding_energy` (gmx_MMPBSA /
  Rosetta InterfaceAnalyzer need GROMACS/AMBER or a Rosetta licence);
  `ternary_complex_modeling` requires external engines.
* **Framework ≠ method:** `torch`/`transformers` imports are demoted to
  `dependency_present_repo_required`; they are never reported as an installed
  method.

---

## 10. Scripts reference

| Script | Purpose |
|---|---|
| `scripts/package_release.sh` | build release bundle + truth + checksums |
| `scripts/distribution_smoke.sh` | clean-venv install + smoke tests |
| `scripts/install.sh` | universal one-command installer (minimal/scientific/full) |
| `scripts/bootstrap_assets.sh` | restore checksum-verified large assets |
| `protacxtend toolkit` | plan / provision / verify / truth / manifest |
| `analysis/generate_inventory.py` | inventory workbook + 13 plots |
| `analysis/generate_audit.py` | capability + escalation audits |
