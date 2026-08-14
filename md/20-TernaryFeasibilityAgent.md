# 20 · TernaryFeasibilityAgent

| | |
| --- | --- |
| **Node** | 20 — `optional_ternary_feasibility` |
| **Source** | `synglue_agent/agents/ternary_agent.py` |
| **Size** | **597 lines — largest agent in the system** |
| **Status** | ✅ **Built and executed (v0.3)** — proxy+P4ward+SE3 ensemble; run in container boot-test and e2e (HMGB2 AMBIGUOUS → human gate) |
| **Tools** | `p4ward_wrapper.py` (1,200 lines), `ternary_feasibility.py` (332 lines) |
| **Objective** | **O-4** |

## Architecture brief

The structural-reality check, and the most substantial component in the project. It asks
whether the assembled PROTAC can physically hold the target protein and the E3 ligase
together in a productive geometry — the question that, per Bondeson 2018, predicts
degradation far better than binary affinity does.

It is the only optional node and the only one with two backends separated by four orders
of magnitude in cost:

| Backend | Cost | What it computes |
| --- | --- | --- |
| `ternary_feasibility.py` — geometric proxy | **< 1 s**, no Docker | exit-vector angle, linker reachability, lysine proximity filtering → score 0–1 |
| `p4ward_wrapper.py` — full P4ward | **2–4 h**, 4.7 GB image | 3,600 poses + minimisation, ternary interface scores, lysine distances, CRL models |

P4ward (Jofily & Kalyaanamoorthy, *JCIM* 2025) runs in Docker as `paulajlr/p4ward:latest`.
Inputs: `receptor.pdb`, `ligase.pdb`, `receptor_ligand.mol2`, `ligase_ligand.mol2`,
`protac.smiles`, `config.ini`.

This node addresses NP-hard problem #3 — the ternary complex 3-body problem. A full linker
scan at P4ward fidelity would take 60–120 CPU-years, which is precisely why the fast proxy
exists.

**The gap is operational, not architectural.** The Docker image is pulled, the input files
are staged, and no production P4ward run has been executed for A1_4COOH. The 597-line
agent and the 1,200-line wrapper have never delivered a completed high-fidelity result.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.valid_candidates` | `list[CandidateRecord]` | node 11 |
| `state.parsed_objective` | `ParsedObjective` | node 1 |
| target / ligase structures | PDB, AlphaFold | node 4 |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.ternary_feasibility_results` | `list[TernaryFeasibilityResult]` | feasibility score, interface scores, lysine distances |

Consumed by node 21 for the final re-ranking.

## What is solid

- **The two-tier design is the correct answer to a 60–120 CPU-year problem.** Screen
  everything cheaply, confirm survivors expensively. This is the best architectural
  decision in the project.
- **Real integration with published, peer-reviewed software** rather than a home-grown
  approximation.
- **The proxy is validated and fast** — 192 warhead × attachment × linker combinations in
  under a second in the case study.
- **It produced the project's most credible result.** H1 rejected on 0/3,600 poses; the
  redesigned A1_4COOH reaching 8–16/3,600. A pipeline that can generate a clean negative
  is worth more than one that always finds a winner.
- **Correctly optional**, so a run is never forced into a multi-hour branch.

## What to improve

**1 · Execute the P4ward run (objective O-4). This is the top priority.** It is 2–4 hours
of compute and zero lines of code. Until it completes, the 1,200-line wrapper is unproven
in production and the proxy has never been calibrated against the backend it approximates.

**2 · Calibrate the proxy against P4ward output.** The proxy returns 0–1. Nobody knows how
that maps onto real pose pass rates. Once item 1 completes, fit the proxy against P4ward on
a set of candidates and report the correlation. Without this, the fast path's score is
uncalibrated and the two-tier design cannot be trusted to select correctly.

**3 · Define the screening cut explicitly.** Which candidates graduate from proxy to
P4ward, and on what threshold? With a 2–4 h cost per molecule this is the most expensive
decision in the pipeline and it should be an explicit, budgeted policy set by node 2, not
an implicit one.

**4 · Report pass rates, not just scores.** The most interpretable numbers the project has
produced are pass rates — 0/3,600, 8–16/3,600, 0.8% for C14-PEG5. Make that the standard
output format; it is far more legible than an abstract 0–1 score.

**5 · Feed ternary results back into degradation prediction.** Bondeson 2018 — cited in the
project's own analysis — says ternary formation predicts degradation better than binary
affinity. Node 12 runs *before* this node and never sees the result. Node 21 re-ranks, but
the DC₅₀ estimate itself is never revised. Either reorder or add a second prediction pass.

**6 · Add checkpointing and resumability.** A 2–4 h Docker run that fails at hour 3 with no
recovery is an expensive failure. Persist intermediate state and make partial results
usable.

**7 · Handle structure quality explicitly.** A ternary result computed on a low-confidence
AlphaFold region is not meaningful. Carry pLDDT through from node 4 and refuse or flag runs
on poorly-predicted binding sites.

## Feasibility note

Item 1 costs an afternoon of compute and unblocks items 2 and 4. It is the highest
value-per-effort action available anywhere in the project: it converts the largest component
in the codebase from *built but unproven* into *validated*, and it is the one improvement
that requires no code at all.
