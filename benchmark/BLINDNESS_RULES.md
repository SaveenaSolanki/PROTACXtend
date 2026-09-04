# Blindness Rules — data leakage & answer contamination (binding)

These rules apply from the moment a task leaves `cases/` until its final
score is locked.

## 1. Blinded inputs

- `supplied_inputs` in a task record are the **only** inputs a system may see.
- `hidden_information` is never placed in supplied inputs, prompts, tools, or
  system state.
- Anything derived from the expected answer (ground truth, rankings, potency
  values, "correct" labels) is **forbidden during inference**.

## 2. Answer contamination

- Expected answers and ground truth are stored only under `ground_truth/`
  with citations; no task runner may read them while the system is running.
- Systems must not be pre-fitted, few-shot warmed, or fine-tuned on
  ground-truth answers for tasks they are later scored on.
- No task may contain memorisable "tells" (e.g., gold answer embedded in a
  permitted database that the prompt also names).

## 3. Data leakage

- Live internet access is forbidden unless the task explicitly lists a
  permitted database in `permitted_tools_databases`.
- Retrieval provenance must be recorded per evidence item; uncited or
  unverifiable statements score as hallucinations (see rubric).
- The same task may appear across systems only after blindness lock; any
  public model output for a task that leaks into later prompts invalidates
  that task–system run and triggers re-blinding.

## 4. Lock-before-outcome

- Final (pre-agreed) answers/rankings are **locked before any wet-lab
  outcome is consulted**.
- Wet-lab or measured outcomes added later are appended to `ground_truth/`
  with citations and a timestamp; they are never back-fed into a finished
  blinded run.

## 5. Six-BRD4/VHL case study

- The six-BRD4/VHL workflow is a **controlled blinded case study outside the
  main benchmark** (see `protacxtend/case_study/`).
- Its measured potency is **never used during inference** and it is not
  promoted to benchmark ground truth.

## 6. Audit trail

- Every run writes: inputs hash, task file hash, provider/model/version,
  seed, repeat index, tool-call log, retrieval sources, and blindness log to
  `outputs/` + `reports/`.
- Any suspected contamination freezes that task–system result until review.
