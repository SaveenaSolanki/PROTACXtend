# Phase 3 Recommended Install Order

This is a manual, isolated-environment order. Do not run bulk installs. Every command template is also available, commented out, in `phase3_safe_commands.sh`.

## Final ranked install order

1. **PROTAC-Splitter** - `install_now_isolated`; risk `medium`; model or prediction utility; molecular processing utility; dataset/benchmark/reference; notebook-oriented workflow.
2. **PROTAC-RL** - `install_now_isolated`; risk `medium`; model or prediction utility; molecular processing utility; dataset/benchmark/reference; checkpoint/model-assets repository.
3. **TERNIFY** - `install_now_isolated`; risk `low`; ternary-complex/docking workflow; molecular processing utility; dataset/benchmark/reference.
4. **Bellerophon** - `install_later_manual_review`; risk `low`; molecular processing utility; dataset/benchmark/reference.
5. **SE3-protacs** - `install_later_manual_review`; risk `high`; model or prediction utility; molecular processing utility; dataset/benchmark/reference; checkpoint/model-assets repository.
6. **degradomap** - `install_later_manual_review`; risk `high`; ternary-complex/docking workflow; model or prediction utility; dataset/benchmark/reference; notebook-oriented workflow.
7. **MEGA-PROTAC** - `install_later_manual_review`; risk `high`; ternary-complex/docking workflow; model or prediction utility; dataset/benchmark/reference.
8. **PROTAC-Degradation-Predictor** - `docker_only_manual_review`; risk `medium`; model or prediction utility; molecular processing utility; dataset/benchmark/reference; notebook-oriented workflow.
9. **PROTACFold** - `docker_only_manual_review`; risk `high`; ternary-complex/docking workflow; model or prediction utility; molecular processing utility; dataset/benchmark/reference.

## Which repo should be installed first

Install **PROTAC-Splitter** first, manually and in isolation, because it has the safest Phase 3 score among `install_now_isolated` candidates.

Command template:

```bash
python -m venv .venvs/protac-splitter && source .venvs/protac-splitter/bin/activate && python -m pip install --upgrade pip && pip install -r data/protac_repos/repos/PROTAC-Splitter/requirements.txt
```

## Which repos are not installable yet

- **Bellerophon**: scripts found: 2; README detected; deferred because Phase 3 limits install_now_isolated to 3 safest repositories
- **SE3-protacs**: scripts found: 8; README detected; license file not detected at repository root; Phase 2 marked manual review required
- **degradomap**: notebooks found: 1; scripts found: 11; README detected; Phase 2 marked manual review required
- **MEGA-PROTAC**: scripts found: 28; README detected; license file not detected at repository root; Phase 2 marked manual review required

## Which repos should remain metadata-only for now

None.

## Which repos require Docker/manual review

- **PROTAC-Degradation-Predictor**: notebooks found: 11; scripts found: 23; README detected; README or metadata mentions Docker
- **PROTACFold**: scripts found: 23; README detected; Phase 2 marked manual review required; README or metadata mentions Docker; large dataset wording detected

## Which repos should be skipped for now

None.

## What to check before Phase 4

- Verify licenses and redistribution constraints.
- Create only one isolated environment at a time.
- Review dependency files before solving environments.
- Check README warnings for GPU, docking, AlphaFold, MEGADOCK, Rosetta, CCDC/CSD, OpenBabel, and large datasets.
- After installation, run only generic smoke tests first: `python --version`, `python -m pip list | head`, and `ls <repo_path>`.
- Do not import repository modules until a dedicated smoke-import phase approves a target module and expected behavior.
