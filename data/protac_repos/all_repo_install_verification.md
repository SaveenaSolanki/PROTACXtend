# All PROTAC Repo Install Verification

This verification inspected isolated environments only. It did not run repository workflows, notebooks, training, docking, AlphaFold, MEGADOCK, Rosetta, CLIs, or imports from cloned repository packages.

Checks performed: environment Python version, `python -m pip check`, RDKit import, PyTorch import, OpenBabel Python import, and external binary path lookup.

## TERNIFY

- Environment: `.venvs/protac-ternify` (venv)
- Resolved path: `.venvs/protac-ternify`
- Python version: `Python 3.10.20`
- Install log: `data/protac_repos/install_logs/ternify_install.log`
- Install appears successful: `True`
- Missing dependencies: none reported by pip check
- RDKit import status: ok: 2026.03.2
- PyTorch import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'torch'
- OpenBabel import status: missing/error: ModuleNotFoundError: No module named 'openbabel'
- OpenBabel/obabel availability: available
- External binary availability: found: obabel=/usr/local/bin/obabel, babel=/usr/local/bin/babel, vina=/usr/bin/vina
- Safe wrapper integration possible: `True`
- Recommended wrapper type: `python_function_adapter`
- Notes: log exists; success-like wording found near tail; repository code not imported or executed; yes; only after later repo-specific smoke import/API review

## PROTAC-Splitter

- Environment: `.venvs/protac-splitter` (venv)
- Resolved path: `.venvs/protac-splitter`
- Python version: `Python 3.13.5`
- Install log: `data/protac_repos/install_logs/protac_splitter_editable.log`
- Install appears successful: `True`
- Missing dependencies: none reported by pip check
- RDKit import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> import rdkit ModuleNotFoundError: No module named 'rdkit'
- PyTorch import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> import torch ModuleNotFoundError: No module named 'torch'
- OpenBabel import status: missing/error: ModuleNotFoundError: No module named 'openbabel'
- OpenBabel/obabel availability: available
- External binary availability: found: obabel=/usr/local/bin/obabel, babel=/usr/local/bin/babel, vina=/usr/bin/vina
- Safe wrapper integration possible: `True`
- Recommended wrapper type: `python_package_adapter_after_import_smoke_test`
- Notes: log exists; warning/error wording found near tail; repository code not imported or executed; yes; only after later repo-specific smoke import/API review

## Bellerophon

- Environment: `.venvs/protac-bellerophon` (venv)
- Resolved path: `.venvs/protac-bellerophon`
- Python version: `Python 3.10.20`
- Install log: `data/protac_repos/install_logs/bellerophon_install.log`
- Install appears successful: `True`
- Missing dependencies: none reported by pip check
- RDKit import status: ok: 2024.09.2
- PyTorch import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'torch'
- OpenBabel import status: missing/error: ModuleNotFoundError: No module named 'openbabel'
- OpenBabel/obabel availability: available
- External binary availability: found: obabel=/usr/local/bin/obabel, babel=/usr/local/bin/babel, vina=/usr/bin/vina
- Safe wrapper integration possible: `True`
- Recommended wrapper type: `python_script_adapter_after_manual_review`
- Notes: log exists; no clear success/failure marker in tail; repository code not imported or executed; yes; only after later repo-specific smoke import/API review

## degradomap

- Environment: `.venvs/protac-degradomap` (venv)
- Resolved path: `.venvs/protac-degradomap`
- Python version: `Python 3.10.20`
- Install log: `data/protac_repos/install_logs/degradomap_editable.log`
- Install appears successful: `True`
- Missing dependencies: none reported by pip check
- RDKit import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'rdkit'
- PyTorch import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'torch'
- OpenBabel import status: missing/error: ModuleNotFoundError: No module named 'openbabel'
- OpenBabel/obabel availability: available
- External binary availability: found: obabel=/usr/local/bin/obabel, babel=/usr/local/bin/babel, vina=/usr/bin/vina
- Safe wrapper integration possible: `True`
- Recommended wrapper type: `metadata_or_pipeline_adapter_after_manual_review`
- Notes: log exists; success-like wording found near tail; repository code not imported or executed; yes; only after later repo-specific smoke import/API review

## PROTACFold

- Environment: `.venvs/protac-protacfold` (venv)
- Resolved path: `.venvs/protac-protacfold`
- Python version: `Python 3.10.20`
- Install log: `data/protac_repos/install_logs/protacfold_install.log`
- Install appears successful: `True`
- Missing dependencies: none reported by pip check
- RDKit import status: ok: 2026.03.2
- PyTorch import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'torch'
- OpenBabel import status: missing/error: ModuleNotFoundError: No module named 'openbabel'
- OpenBabel/obabel availability: available
- External binary availability: found: obabel=/usr/local/bin/obabel, babel=/usr/local/bin/babel, vina=/usr/bin/vina
- Safe wrapper integration possible: `False`
- Recommended wrapper type: `manual_wrapper_only_due_alphafold_review`
- Notes: log exists; no clear success/failure marker in tail; repository code not imported or executed; not yet; requires manual review of heavy docking/AlphaFold/MEGADOCK style dependencies

## PROTAC-RL

- Environment: `protac-rl` (conda)
- Resolved path: `/home/saveenas/miniconda3/envs/pp/envs/protac-rl`
- Python version: `Python 3.6.10 :: Anaconda, Inc.`
- Install log: `data/protac_repos/install_logs/protac_rl_conda.log`
- Install appears successful: `False`
- Missing dependencies: WARNING: The directory '/home/saveenas/.cache/pip' or its parent directory is not owned or is not writable by the current user. The cache has been disabled. Check the permissions and owner of that directory. If executing pip with sudo, you may want sudo's -H flag. spyder 3.3.2 requires pyqt5, which is not installed. conda 4.8.3 requires ruamel-yaml, which is not installed. anaconda-project 0.8.2 requires ruamel-yaml, which is not installed. pylint 2.7.2 has requirement astroid<2.6,>=2.5.1, but you have astroid 2.5.
- RDKit import status: ok: 2019.09.2
- PyTorch import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'torch'
- OpenBabel import status: missing/error: ModuleNotFoundError: No module named 'openbabel'
- OpenBabel/obabel availability: available
- External binary availability: found: obabel=/usr/local/bin/obabel, babel=/usr/local/bin/babel, vina=/usr/bin/vina
- Safe wrapper integration possible: `False`
- Recommended wrapper type: `model_utility_adapter_after_import_smoke_test`
- Notes: log exists; warning/error wording found near tail; repository code not imported or executed; no; resolve environment or missing dependency issues first

## PROTAC-Degradation-Predictor

- Environment: `protac-degradation-predictor` (conda)
- Resolved path: `/home/saveenas/miniconda3/envs/pp/envs/protac-degradation-predictor`
- Python version: `Python 3.10.8`
- Install log: `data/protac_repos/install_logs/protac_degradation_predictor_conda.log`
- Install appears successful: `False`
- Missing dependencies: WARNING: The directory '/home/saveenas/.cache/pip' or its parent directory is not owned or is not writable by the current user. The cache has been disabled. Check the permissions and owner of that directory. If executing pip with sudo, you should use sudo's -H flag. triton 2.0.0 requires cmake, which is not installed. triton 2.0.0 requires lit, which is not installed.
- RDKit import status: ok: 2023.09.5
- PyTorch import status: ok: 2.0.1
- OpenBabel import status: missing/error: ModuleNotFoundError: No module named 'openbabel'
- OpenBabel/obabel availability: available
- External binary availability: found: obabel=/usr/local/bin/obabel, babel=/usr/local/bin/babel, vina=/usr/bin/vina
- Safe wrapper integration possible: `False`
- Recommended wrapper type: `python_package_adapter_after_import_smoke_test`
- Notes: log exists; warning/error wording found near tail; repository code not imported or executed; no; resolve environment or missing dependency issues first

## MEGA-PROTAC

- Environment: `protac-mega-protac` (conda)
- Resolved path: `/home/saveenas/miniconda3/envs/pp/envs/protac-mega-protac`
- Python version: `Python 3.10.12`
- Install log: `data/protac_repos/install_logs/mega_protac_conda.log`
- Install appears successful: `False`
- Missing dependencies: WARNING: The directory '/home/saveenas/.cache/pip' or its parent directory is not owned or is not writable by the current user. The cache has been disabled. Check the permissions and owner of that directory. If executing pip with sudo, you should use sudo's -H flag. pymol 3.1.0 has requirement numpy<2,>=1.26.4, but you have numpy 2.2.6.
- RDKit import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'rdkit'
- PyTorch import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'torch'
- OpenBabel import status: ok: openbabel package
- OpenBabel/obabel availability: available
- External binary availability: found: obabel=/home/saveenas/miniconda3/envs/pp/envs/protac-mega-protac/bin/obabel, babel=/usr/local/bin/babel, vina=/usr/bin/vina
- Safe wrapper integration possible: `False`
- Recommended wrapper type: `manual_wrapper_only_due_megadock_review`
- Notes: log exists; warning/error wording found near tail; repository code not imported or executed; no; resolve environment or missing dependency issues first

## SE3-protacs

- Environment: `protac-se3-protacs` (conda)
- Resolved path: `/home/saveenas/miniconda3/envs/pp/envs/protac-se3-protacs`
- Python version: `Python 3.10.18`
- Install log: `data/protac_repos/install_logs/se3_protacs_conda.log`
- Install appears successful: `True`
- Missing dependencies: none reported by pip check
- RDKit import status: missing/error: Traceback (most recent call last): File "<string>", line 1, in <module> ModuleNotFoundError: No module named 'rdkit'
- PyTorch import status: ok: 2.5.1
- OpenBabel import status: ok: openbabel package
- OpenBabel/obabel availability: available
- External binary availability: found: obabel=/home/saveenas/miniconda3/envs/pp/envs/protac-se3-protacs/bin/obabel, babel=/usr/local/bin/babel, vina=/usr/bin/vina
- Safe wrapper integration possible: `False`
- Recommended wrapper type: `manual_wrapper_only_due_docking_review`
- Notes: log exists; success-like wording found near tail; repository code not imported or executed; not yet; requires manual review of heavy docking/AlphaFold/MEGADOCK style dependencies
