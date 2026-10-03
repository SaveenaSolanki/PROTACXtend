# Scoring rubric (reviewer-facing)

Applied per case. Reviewers fill `verdict`, `confidence`, `acceptable_answer`,
`mandatory_answer_elements`, `acceptable_alternatives`, `evidence_spans`,
`answerability`, `reviewer_name`.

## Verdict vocabulary

| verdict | meaning |
|---|---|
| `approve` | proposed answer is scientifically correct, complete, and evidence-supported |
| `revise` | usable but requires the noted correction before use as gold |
| `unanswerable` | the case cannot be answered from permitted resources as written |
| `unscorable` | the question/gold cannot be scored by an objective rubric |

## Answerability

`answerable` · `unanswerable` · `insufficient` (inputs missing) — recorded
independently of the verdict; `insufficient` is the correct response when the
case's `supplied_inputs` omit a required fact (e.g. DESIGN-12 has no E3 ligand,
DISCOVER-08 has no candidate list, REASON-02 has no pose).

## Objective elements (all capabilities)

1. **Correctness** — matches the source-backed fact / valid structure.
2. **Evidence grounding** — each mandatory claim carries a resolvable source span.
3. **Completeness** — every `mandatory_answer_elements` item present.
4. **No fabrication** — identifiers, accession numbers and SMILES must resolve.
5. **Abstention honesty** — an unanswerable/insufficient case should abstain or
   request the missing input, not guess.

## Design-rubric extras (DESIGN-*)

- Valid RDKit structure; components present; attachment atoms supported by the
  source (a binding citation alone does not validate an exit vector).
- Ternary geometry, synthesis route, degradation activity and DC50 are **not**
  scored from a reconstruction control.

## Agreement

Compute raw agreement and Cohen's κ on the categorical `verdict` before
adjudication. Target κ ≥ 0.7 is a **gate to report**, never a value to tune;
if undefined or below threshold, report honestly and version a rubric revision
while preserving earlier reviews.
