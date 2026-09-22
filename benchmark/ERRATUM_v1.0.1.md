# Benchmark Ground-Truth Erratum — v1.0.1 (pre-execution)

| Field | Value |
|---|---|
| Erratum version | **1.0.1** |
| Erratum id | `ERRATUM-2026-001` |
| Status | **Pre-execution** (applies before the definitive 48 × 3 benchmark run) |
| Recorded | 2026-09-07 (UTC) |
| Supersedes | Ground-truth freeze as authored at `2026-09-04T14:53:18.684630+00:00` (freeze manifest 2A.1) |
| Scope | `benchmark/ground_truth/KNOW-01.json` **only** |

## 1. Correction (single content fix)

**KNOW-01** ground truth — human BRD4 UniProt accession.

- `expected_answer`: `UniProt Q60885; ...` → `UniProt O60885; ...`
- `mandatory_answer_elements`: `"Q60885"` → `"O60885"`
- `evidence_sources[0].ref`: `https://www.uniprot.org/uniprotkb/Q60885` →
  `https://www.uniprot.org/uniprotkb/O60885`

## 2. Rationale

The canonical UniProtKB entry for **human** BRD4 is **O60885** (entry name
`BRD4_HUMAN`, "Bromodomain-containing protein 4", Homo sapiens). The accession
`Q60885` is not valid for human BRD4 and was an authoring error in the KNOW-01
ground-truth record. (Related non-human orthologs are distinct accessions,
e.g. mouse Brd4 = Q9ESU6; they are out of scope for this task.)

All three pilot systems already answered the correct accession `O60885` for
human BRD4 (PROTACXtend, Base-LLM-control and AI-Co-Scientist-compatible
KNOW-01 envelopes), confirming the supplied case (gene name `BRD4`, default
species human) targets the O60885 entry. Leaving the ground truth at `Q60885`
would have scored correct answers as wrong.

## 3. No other changes

- No other ground-truth content was changed (the remaining 47 ground-truth
  records are byte-identical to the frozen set).
- No case file (`benchmark/cases/*.json`) was changed.
- No protocol / blindness / rubric / manifest content was changed.
- Result schema, task schema and rubric weights are untouched.

## 4. Freeze regeneration

`benchmark/FREEZE_MANIFEST.json` was regenerated after this correction so the
fail-closed executor locks the corrected ground truth. Expected diff versus
the previous manifest: the SHA-256 of `ground_truth/KNOW-01.json` and the
`frozen_at` timestamp only.
