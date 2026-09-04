# PROTACXtend Benchmark Infrastructure

**Infrastructure only.** No scientific benchmark has been executed and no
scientific conclusion is claimed from this directory. The six BRD4–VHL
PROTACs live under `protacxtend/case_study/` as a **prospective case study** —
never as benchmark ground truth.

## Layout

```
benchmark/
├── manifests/           auto-discovered live registries (written by
│   ├── tools.json           protacxtend.benchmark.manifest.write_manifests)
│   ├── agents.json
│   └── workflows.json
├── tasks/               one JSON file per benchmark task (BenchmarkTask schema)
├── ground_truth/        curated, outcome-derived ground truth (never inferred
│                        from prospective case-study inputs)
├── configs/             task configuration files
├── outputs/             raw task outputs (git-ignored after runs)
└── reports/             human + machine readable reports
```

## Manifests — auto-discovery

`benchmark/manifests/*.json` are generated from the **live** registries:

| Manifest | Registry source |
|----------|-----------------|
| `tools.json`    | `protacxtend.toolkit.registry.get_tools()` + skill catalogue + databases |
| `agents.json`   | `protacxtend.tui_bridge.events.AGENT_PIPELINE` |
| `workflows.json`| `protacxtend.tui_bridge.events.RESEARCH_WORKFLOWS` |

Counts are whatever the running registries report — never hard-coded.

```bash
python -c "from protacxtend.benchmark.manifest import write_manifests; print(write_manifests())"
```

## Task schema

`protacxtend.benchmark.task_schema.BenchmarkTask` supports three kinds:

- `tool`   — invoke one registered tool and check output/status
- `agent`  — run an agent-graph stage/objective and check state
- `system` — end-to-end KNOW → REASON → DESIGN → DISCOVER run + artefacts

Fields: `task_id, kind, name, manifest_ref, description, inputs, expected,
ground_truth_ref, uses_ground_truth, status, created_at, metadata`.

Tasks are stored as JSON under `benchmark/tasks/`.

## Ground truth policy

- `benchmark/ground_truth/` may only contain **measured/outcome-derived**
  values with citations.
- Prospective case-study predictions must never be written into ground truth.
- `uses_ground_truth: false` is the default and the only setting allowed for
  tasks whose inputs were authored before outcomes were known.

## Running a benchmark

Nothing here runs automatically. A runner that consumes `BenchmarkTask`
entries and writes into `outputs/` + `reports/` will be added when a task
set is approved.
