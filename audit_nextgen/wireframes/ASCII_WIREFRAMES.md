# PROTACXtend vNext — Low-Fidelity ASCII Wireframes

Twelve screens. Each screen lists **purpose / panels / controls / information
hierarchy / primary CTA / secondary CTA / state changes / error state** below
its wireframe. `▸` = primary CTA, `·` = secondary. Status tokens are
`PENDING RUNNING PASSED WARN FAILED SKIPPED ABSTAINED`.

---

## 1. Home Dashboard

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ ⚗ PROTACXtend   [Project: TNBC-BRD4 ▾]      cutoff: 2024-12-31 ▾   mode: AGENTIC ▾   ▶ RUN   │
├───────────────┬──────────────────────────────────────────────────────────────┬───────────────┤
│ NEW INVEST.   │  RECENT INVESTIGATIONS                                       │  SYSTEM       │
│ Projects      │  ┌────────────────────────────────────────────────────────┐  │  Tools 34 ok  │
│ Terapeutic D. │  │ BRD4 · TNBC        target_biology→…→experiment 29% ●   │  │  DBs 7 live   │
│ Target Anal.  │  │ KRAS G12C · PDAC   …                           42% ●   │  │  Models 7     │
│ PROTAC Design │  │ SMARCA2 · AML      …                           71% ●   │  │  SciValid 1   │
│ Structure     │  └────────────────────────────────────────────────────────┘  │  Backends 19  │
│ Benchmark     │                                                              │  READY        │
│ Temporal Ch.  ├──────────────────────────────────────────────────────────────┤               │
│ Tool Registry │  QUICK ASK (grounded)                                        │  ───────────  │
│ Run History   │  ┌────────────────────────────────────────────────────────┐  │  DIAGNOSTICS  │
│ Settings      │  │ "Can BRD4 be therapeutically degraded in TNBC?"    [↵] │  │  doctor ⚠     │
│               │  └────────────────────────────────────────────────────────┘  │  provenance ✓ │
└───────────────┴──────────────────────────────────────────────────────────────┴───────────────┘
```
- **Purpose:** entry point; live system truth; recent work.
- **Panels:** project selector, recent investigations, grounded quick-ask, system readiness, diagnostics.
- **Controls:** project dropdown, cutoff dropdown, agent-mode dropdown, RUN, quick-ask box.
- **Hierarchy:** question → investigation → evidence → system truth.
- **Primary CTA:** `▶ RUN` / quick-ask. **Secondary:** open history, doctor.
- **States:** empty (no projects → "New Investigation"), loading, offline banner.
- **Error:** red banner "no LLM provider / provider error · retry" with offline mode.

---

## 2. New Therapeutic Investigation

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ ← Home      NEW INVESTIGATION                                        [draft]   ▸ CREATE+RUN   │
├─────────────────────────────────────────────┬────────────────────────────────────────────────┤
│ 1 QUESTION / HYPOTHESIS                      │  LIVE PARSED ENTITIES                          │
│ ┌─────────────────────────────────────────┐ │  Target       BRD4            (O60885) ✓       │
│ │ Can BRD4 be therapeutically degraded in │ │  Disease      triple-negative breast cancer ✓  │
│ │ triple-negative breast cancer?          │ │  E3 context   VHL (explicit) ✓                 │
│ └─────────────────────────────────────────┘ │  Warhead      JQ1-like (from question?) ⚠       │
│ 2 CONTEXT                                    │  Missing      assay, cell line, potency target │
│  Target [BRD4____] Disease [TNBC_______]     │  ── parser confidence 0.74 ──                  │
│  Cell line [______] Species [human ▾]        │                                                │
│  E3 [auto ▾]  Modality [PROTAC ▾]            │  EVIDENCE CUTOFF                               │
│ 3 SCOPE                                      │  ( ) none  (•) 2024-12-31  ( ) custom [____]   │
│  ☑ target biology  ☑ tractability            │  ⚠ temporal mode locks later evidence          │
│  ☑ warhead  ☑ linker  ☑ ternary              │                                                │
│  ☑ degradation  ☑ ADME  ☑ safety             │  TOOL POLICY                                   │
│  ☐ resistance  ☐ biomarker  ☐ combination    │  (•) capability-first free/local               │
│  ☑ experimental design  ☐ failure analysis   │  ( ) native    ( ) matched-tool                │
│                                              │  Tool budget [1800 s]  Max candidates [50]     │
├─────────────────────────────────────────────┴────────────────────────────────────────────────┤
│ ▸ CREATE + RUN      · save draft   · validate question   · import prior run                    │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** turn a biological problem into a typed, gated investigation.
- **Panels:** question, context, scope, parsed entities, cutoff, tool policy.
- **Controls:** all inputs above; CTA.
- **Hierarchy:** question → parsed entities (must be confirmed) → scope → policy.
- **Primary:** `CREATE + RUN`. **Secondary:** draft/validate/import.
- **States:** parser low-confidence → entity chips highlighted for confirmation.
- **Error:** "target not resolved" blocks RUN and asks a specific question.

---

## 3. Target Analysis

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Investigation: BRD4·TNBC     TARGET ANALYSIS                    node: 2/16  ●●●●●○○○○○○○○○○○  │
├──────────────┬───────────────────────────────────────────────┬───────────────────────────────┤
│ EVIDENCE     │ TARGET DOSSIER — BRD4 (O60885)                │ VALIDATION AXES               │
│ FILTERS      │ identity ✓ two bromodomains + ET domain       │ genetics      WEAK  (no hits) │
│ type ▾ all   │ expression: DepMap TNBC lines (transcript)    │ omics         PARTIAL          │
│ year ▾        │ dependency: ⚠ no CRISPR dataset connected     │ dependency    MISSING          │
│ strength ▾    │ disease link: literature n=… (grounded)       │ biochemical   PARTIAL          │
│ ──────────── │ localization: nucleus ✓                       │ animal        MISSING          │
│ □ primary    │                                              │ clinical      MISSING          │
│ □ genetic    │ ┌─ TPD TRACTABILITY ────────────────────────┐ │ ── overall: INSUFFICIENT ──   │
│ □ omics      │ │ structured?  ✓ (BD1/BD2)                  │                               │
│ □ dependency │ │ accessible lysines: not computed          │ CONTRADICTIONS                │
│ □ clinical   │ │ known degraders: DB match (n=…)           │ none recorded                 │
│              │ └───────────────────────────────────────────┘ │                               │
│ ──────────── │                                               │ PROVENANCE                    │
│ ☑ only pre-  │ EVIDENCE CARDS                                │ uniprot@… pubmed@… · dates ✓  │
│   cutoff     │ ┌───────────────────────────────────────────┐ │                               │
│              │ │ genetic | dependency | SUPPORTED/…        │ │                               │
│              │ │ "…excerpt…" DOI/PMID · date · strength    │ │                               │
│              │ └───────────────────────────────────────────┘ │                               │
├──────────────┴───────────────────────────────────────────────┴───────────────────────────────┤
│ ▸ ADVANCE TO VALIDATION    · add target   · export dossier   · flag missing dependency data    │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** establish target identity, biology, and validation evidence.
- **Panels:** evidence filters, dossier, validation axes, evidence cards, provenance.
- **Controls:** filters, cutoff lock, add target, export, advance.
- **Hierarchy:** identity → validation axes → tractability → evidence → provenance.
- **Primary:** `ADVANCE TO VALIDATION`. **Secondary:** export/flag.
- **States:** axis colour by tier; node progress.
- **Error:** "no dependency dataset connected" → WEAK, not fabricated.

---

## 4. PROTAC Design Workspace

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ BRD4·TNBC   PROTAC DESIGN                                     node: 6/16  ●●●●●●○○○○○○○○○○○○  │
├─────────────────────────────────────┬────────────────────────────────────────────────────────┤
│ WARHEADS                            │ E3 LIGANDS                                             │
│ ┌────────────┬──────┬──────┬──────┐ │ ┌────────────┬──────┬──────────┬──────┬────────────┐ │
│ │ SMILES     │ MW   │ logP │ tier │ │ │ handle     │ E3   │ evidence │ MW   │ tier       │ │
│ │ JQ1-like…  │ 457  │ 3.1  │  ★★  │ │ │ VHL-H032…  │ VHL  │ precedent│ 341  │ SUPPORTED  │ │
│ └────────────┴──────┴──────┴──────┘ │ └────────────┴──────┴──────────┴──────┴────────────┘ │
│ EXIT VECTORS  · detected (RDKit) ✓  │ LINKER PANEL                                           │
├─────────────────────────────────────┤ ┌──────────────────────────┬───────┬────────┬────────┐ │
│ CANDIDATES (ranked)                 │ │ linker SMILES            │ class │ n_rot  │ strain │ │
│ ┌──┬───────────────┬─────┬───┬────┐ │ │ [*]CCc1cnnn1CC[*]        │ PEG2  │ 6      │ 12.4   │ │
│ │# │ PROTAC        │ DC50│Dm │AD │ │ │ [*]CCn1nncc1CC[*]        │ triaz │ 5      │ 9.1    │ │
│ │1 │ COc1ccc(…)    │14.4 │91 │0.26│ │ └──────────────────────────┴───────┴────────┴────────┘ │
│ │2 │ COc1ccc(…)    │14.4 │83 │0.25│ │ MODEL / EVIDENCE TIER                                  │
│ └──┴───────────────┴─────┴───┴────┘ │ degradation  model vX · LEARNED PREDICTION · AD ✓/⚠     │
│                                     │ ternary      surrogate · STRUCTURAL SURROGATE            │
├─────────────────────────────────────┴────────────────────────────────────────────────────────┤
│ ▸ RUN TERNARY FEASIBILITY   · generate linkers   · 2D/3D view   · export SDF   · ★ shortlist   │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** component-aware design and candidate triage.
- **Panels:** warheads, E3 ligands, exit vectors, linker panel, ranked candidates, model/evidence tier.
- **Controls:** filter, regenerate, shortlist, export SDF, advance.
- **Hierarchy:** components → assembled candidates → tiered predictions.
- **Primary:** `RUN TERNARY FEASIBILITY`. **Secondary:** regenerate/export.
- **States:** candidate validity, AD warning chips, evidence-tier badges.
- **Error:** invalid SMILES → row flagged, excluded from ranking, never silently kept.

---

## 5. Structure / Ternary Modeling

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ BRD4·TNBC   STRUCTURE / TERNARY                               node: 7-8/16  ●●●●●●●●○○○○○○○○  │
├──────────────────────┬───────────────────────────────┬───────────────────────────────────────┤
│ TARGET STRUCTURE     │ BINARY POSES                  │ TERNARY MODEL                          │
│ source: PDB 6BOY ✓   │ ┌──────┬───────┬───────────┐ │ ┌───────────────────────────────────┐ │
│ resolution 1.9 Å     │ │ rank │ score │ RMSD ref  │ │ │ assembly: P4ward / SE(3) surrogate │ │
│ [load] [fetch]       │ │ 1    │ -6.20 │ 2.35 Å    │ │ │ contacts 257 · bridging 0.0 ⚠      │ │
│ [prep: pdbfixer]     │ │ 2    │ -6.10 │ 2.88 Å    │ │ │ predicted DockQ: NOT_VALIDATED     │ │
│ pocket: detected ✓   │ └──────┴───────┴───────────┘ │ └───────────────────────────────────┘ │
│ (Vina+GNINA+DiffDock)│ engine consensus · evidence  │ INTERFACE METRICS                     │
│                      │ tier MEASURED-on-benchmark    │ buried SASA · polar contacts · clash  │
│                      │                               │ nearest lysine d=… Å · E2 geometry     │
│                      │ LYSINE FEASIBILITY            │ COOPERATIVITY α 42.2 (surrogate) ⚠    │
│                      │ reachable / productive        │                                       │
├──────────────────────┴───────────────────────────────┴───────────────────────────────────────┤
│ ▸ ADVANCE TO DEGRADATION   · refine pose   · run MD   · download complex   · compare models    │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** binary + ternary structure evidence with honest validation tier.
- **Panels:** target structure, binary poses, ternary model, interface metrics, lysine feasibility, cooperativity.
- **Controls:** load/fetch/prep, refine, MD, download, advance.
- **Hierarchy:** target → binary → ternary → interface → uncertainty.
- **Primary:** `ADVANCE TO DEGRADATION`. **Secondary:** refine/MD/compare.
- **States:** engine availability chips; NOT_VALIDATED badge colour.
- **Error:** docking backend missing → shows capability resolver + fallback, never a fake pose.

---

## 6. Evidence Explorer

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ EVIDENCE EXPLORER     [graph ▾]  [table ▾]        cutoff 2024-12-31   □ cut-off enforced      │
├───────────────────────────────────┬──────────────────────────────────────────────────────────┤
│ EVIDENCE GRAPH                    │ CLAIM  « BRD4 degradation is feasible in TNBC »          │
│                                   │ ┌──────────────────────────────────────────────────────┐ │
│   TARGET ── disease ── pathway    │ │ direction SUPPORTS   strength MODERATE  tier MEASURED │ │
│     │        │            │       │ │ evidence: genetic | dependency | expression | …      │ │
│   WARHEAD ─ E3 ─ PROTAC ─ STR     │ │ source: PMID 12345678 · 2021-06 · excerpt "…"        │ │
│     │         │         │         │ │ ── conflicts with ── PMID 87654321 (2023, CONTRADICTS)│ │
│  TERNARY ─ DEGRADATION ─ PHENO    │ └──────────────────────────────────────────────────────┘ │
│     │         │           │       │ CLAIM  « VHL is expressed in TNBC »                       │
│    PK ──── SAFETY ──── BIOMARKER  │ ┌──────────────────────────────────────────────────────┐ │
│                                   │ │ expression-only · strength WEAK · does NOT support    │ │
│ ● supports  ● contradicts  ○ none │ │ E3 recommendation alone                              │ │
│                                   │ └──────────────────────────────────────────────────────┘ │
│ FILTERS: type▾ year▾ strength▾    │ ⚠ contradictions are PRESERVED, never averaged away      │
│ [search evidence…]                │                                                          │
├───────────────────────────────────┴──────────────────────────────────────────────────────────┤
│ ▸ SEND TO DECISION ENGINE   · export evidence graph   · add manual evidence   · flag missing   │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** inspect typed evidence and contradictions per claim.
- **Panels:** graph, filters, claim cards with conflicts, contradiction warning.
- **Controls:** view toggle, cutoff, filters, search, send/export.
- **Hierarchy:** claim → evidence items → conflicts → provenance.
- **Primary:** `SEND TO DECISION ENGINE`. **Secondary:** export/flag.
- **States:** graph node colour by evidence direction; cutoff-locked items greyed.
- **Error:** source unreachable → "evidence incomplete" card, not silent omission.

---

## 7. Experimental Plan

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ BRD4·TNBC   EXPERIMENTAL PLAN                                  node: 15/16  ●●●●●●●●●●●●●●●○  │
├───────────────────────────────────────────────┬──────────────────────────────────────────────┤
│ HYPOTHESIS / GOAL                             │ GO / NO-GO CRITERIA                          │
│ Degrade BRD4 in TNBC lines; measure DC50/Dmax │ GO   : Dmax ≥ 80% in ≥1 line, DC50 <100 nM   │
│                                               │ NO-GO : Dmax <50% or no ternary evidence      │
│ ASSAY MATRIX                                  │ COND : proteasome-dependence confirmed        │
│ ┌──────────┬──────────┬─────────┬──────┬───┐  │                                              │
│ │ cell line│ assay    │ readout │ dose │ t │  │ CONTROLS                                     │
│ │ MDA-MB231│ Western  │ BRD4    │ 10×  │24h│  │ • CRBN/VHL ligase mutant rescue              │
│ │ MDA-MB468│ HiBiT    │ Dmax    │ 12pt │6h │  │ • proteasome inhibitor (MG132)               │
│ └──────────┴──────────┴─────────┴──────┴───┘  │ • inactive epimer (negative)                 │
│                                               │ • parental (non-target) line                 │
│ REAGENTS / OPEN QUESTIONS                     │                                              │
│ warhead availability ⚠ · ternary tool ⚠       │ RISK & MITIGATION                            │
│                                               │ hook effect → dose-range design              │
├───────────────────────────────────────────────┴──────────────────────────────────────────────┤
│ ▸ APPROVE PLAN + WRITE MANIFEST   · edit   · send to lab   · export protocol (PDF/CSV)         │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** convert strategy into a falsifiable, controlled experimental plan.
- **Panels:** hypothesis, assay matrix, go/no-go, controls, risks.
- **Controls:** edit, approve, export.
- **Hierarchy:** hypothesis → assay → criteria → controls → risk.
- **Primary:** `APPROVE PLAN + WRITE MANIFEST`. **Secondary:** edit/export.
- **States:** unapproved/approved; criteria editable.
- **Error:** missing reagent → plan flagged incomplete, not filled with invented availability.

---

## 8. Benchmark Dashboard

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ BENCHMARK DASHBOARD                                                                          │
├──────────────┬─────────────────────────────────────────────┬─────────────────────────────────┤
│ BENCHMARKS   │ TPD-HEADTOHEAD/1.0.0                         │ SYSTEMS                         │
│ • TPD-500    │ domains 16 · L1–L7 · 300/150/50 · stress 100 │ A PROTACXtend     EXECUTABLE    │
│ • eval500    │ scorable tasks: 0 / 500  ⛔ AUTHORING NEEDED │ B Biomni          SMOKE ONLY     │
│ • 48-case    │ ───────────────────────────────────────────  │ C TPD-agent       MISSING       │
│ • temporal   │ COVERAGE                                     │ D General LLM     EXECUTABLE    │
│              │ ┌──────────────┬──────┬──────┬──────┐        │ E Retrieval-only  MISSING       │
│ RUNS         │ │ domain       │ ctrl │ e2e  │ temp │        │ F Tool-only       MISSING       │
│ none scored  │ │ target_biol. │ 16   │ 6    │ 0    │        │ G LLM+tools       MISSING       │
│              │ │ …            │ …    │ …    │ …    │        │ H planner+tools   MISSING       │
│              │ └──────────────┴──────┴──────┴──────┘        │                                 │
│              │ METRICS (separate, no composite by default) │ CONDITION                       │
│              │ correctness · grounding · tool-sel · exec   │ (•) native  ( ) matched-tool    │
│              │ mechanistic · quantitative · calibration    │                                 │
│              │ failure-recovery · reproducibility · time   │ ▸ START BENCHMARK RUN           │
├──────────────┴─────────────────────────────────────────────┴─────────────────────────────────┤
│ FIGURES: coverage · accuracy by domain/difficulty · tool precision/recall · calibration        │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** manage benchmarks, systems, conditions, metrics.
- **Panels:** benchmark list, coverage table, systems, condition, metrics, figures.
- **Controls:** select benchmark/system/condition, start run.
- **Hierarchy:** benchmark → coverage → systems → metrics.
- **Primary:** `START BENCHMARK RUN`. **Secondary:** export/figures.
- **States:** "0 scorable" gate blocks run with explicit authoring checklist.
- **Error:** unwired system shown MISSING/BLOCKED, never silently skipped.

---

## 9. 500-task Benchmark Runner

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ BENCHMARK: TPD-HEADTOHEAD 500   Mode: [Standard ▾]   Agent: PROTACXtend vX   Baseline: [D ▾]  │
├───────────────────────────────────────────────┬──────────────────────────────────────────────┤
│ TASK 173 / 500                                │ ALLOWED TOOLS                                │
│ Domain     ternary_complex                    │ required: ternary_model, pdb                 │
│ Difficulty L5 mechanistic inference           │ optional: rdkit, literature                  │
│ Partition  controlled                         │ forbidden: (native leakage / web)            │
│ Cutoff     2022-12-31                         │                                              │
│ Target     BRD4      E3 VHL                   │ ALLOWED EVIDENCE                             │
│ ┌───────────────────────────────────────────┐ │ frozen snapshot 2022-12-31 · sealed future   │
│ │ QUESTION                                  │ │ CUTOFF POLICY                                │
│ │ Assess ternary-complex feasibility …      │ │ release_date ≤ T0, retrieved ≤ T0            │
│ └───────────────────────────────────────────┘ │                                              │
│ ▸ START RUN    · repeat ×5   · seed 0         │ EST. 180 s · tokens — · cost —               │
├───────────────────────────────────────────────┴──────────────────────────────────────────────┤
│ AFTER COMPLETION — twelve separate scores (no single opaque number)                          │
│ scientific_correctness ▓▓▓░ · temporal_compliance ▓▓▓▓ · tool_selection ▓▓░░ · tool_exec ▓▓▓▓  │
│ evidence_grounding ▓▓░░ · mechanistic ▓░░░ · quantitative ▓▓░░ · calibration ▓▓▓░ · repro ▓▓▓▓ │
│ decision_quality ▓▓░░ · future_outcome_match n/a · failure_recovery ▓▓░░                     │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** run one task under frozen, blinded conditions.
- **Panels:** task card, allowed tools/evidence, cutoff policy, post-run scores.
- **Controls:** mode, systems, repeat, seed, start.
- **Hierarchy:** task → constraints → run → separate scores.
- **Primary:** `START RUN`. **Secondary:** repeat/seed.
- **States:** pending/running/scored/abstained; leakage flag badge.
- **Error:** tool unavailable → task recorded with recovery, not skipped.

---

## 10. Blinded Temporal Challenge

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ BLINDED TEMPORAL CHALLENGE                                                                   │
├───────────────────┬──────────────────────────────────────────────────────────────────────────┤
│ HISTORICAL DATE   │              WORLD FROZEN AT: 31 Dec 2021                                 │
│ ( ) 2019          │  ┌────────────────────────────────────────────────────────────────────┐  │
│ ( ) 2020          │  │ evidence available   12,531 papers · 3 DB snapshots · 2 struct repos│  │
│ (•) 2021          │  │                      14 approved tools                              │  │
│ ( ) 2022          │  │ evidence after cutoff: ███████ LOCKED ███████                       │  │
│ ( ) 2023          │  └────────────────────────────────────────────────────────────────────┘  │
│ ( ) 2024          │                                                                          │
│                   │  ▸ RUN BLINDED CHALLENGE                                                 │
│ SNAPSHOT MANIFEST │                                                                          │
│ papers hash ✓     │  ── AGENT ANSWER (sealed until unlock) ────────────────────────────────  │
│ db hash ✓         │  prediction · mechanism · recommended strategy · experiment · confidence │
│ tool hash ✓       │                                                                          │
│ model hash ✓      │  ▸ UNLOCK FUTURE EVIDENCE                                                │
│                   │                                                                          │
│ LEAKAGE AUDIT     │  FUTURE EVIDENCE TIMELINE                                                │
│ leaks: 0 ✓        │  T+6mo  ● SUPPORTED      T+12mo ● MIXED       T+18mo ● CONTRADICTED       │
│                   │  T+24mo ○ UNRESOLVED                                                      │
│                   │  per-aspect verdict: target · E3 · warhead · mechanism · ternary · exp.  │
└───────────────────┴──────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** freeze the world at T0, run blind, unlock future truth, adjudicate.
- **Panels:** date selector, world snapshot, snapshot manifest, leakage audit, agent answer, unlock, timeline.
- **Controls:** year, run, unlock.
- **Hierarchy:** T0 → frozen resources → blind answer → leakage → future adjudication.
- **Primary:** `RUN BLINDED CHALLENGE`; then `UNLOCK FUTURE EVIDENCE`.
- **States:** sealed (answer hidden), unlocked (verdicts shown).
- **Error:** leakage detected → run marked CONTAMINATED, excluded from scoring.

---

## 11. Tool Registry

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ TOOL REGISTRY         search [________]   domain [all ▾]   status [executable ▾]   ▸ verify   │
├──────┬──────────────────────┬──────────────┬──────────┬───────┬──────┬───────┬───────────────┤
│ id   │ name                 │ domain       │ backend  │ ver   │ net  │ exec  │ validation    │
│ 001  │ ligand_docking       │ structure    │ consensus│ vina… │ no   │ ✓     │ externally_b. │
│ 002  │ predict_degradation  │ degradation  │ joblib   │ vX    │ no   │ ✓     │ internally_b. │
│ 003  │ search_bindingdb     │ warhead      │ local    │ —     │ key  │ ~     │ unvalidated   │
│ 004  │ model_ternary_complex│ ternary      │ surrogate│ v0.1  │ no   │ ✓     │ NOT_VALIDATED │
│ …    │ …                    │ …            │ …        │ …     │ …    │ …     │ …             │
├──────┴──────────────────────┴──────────────┴──────────┴───────┴──────┴───────┴───────────────┤
│ SELECTED: model_ternary_complex                                                              │
│ purpose · input schema · output schema · dependency · install recipe · timeout · license      │
│ healthcheck · smoke test · error behaviour · QC gate · provenance fields                      │
│ ▸ EXECUTE (with validated inputs)   · install recipe   · open latest run   · view evidence     │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** single source of truth for tools and their true maturity.
- **Panels:** table, filters, search, detail pane, execute.
- **Controls:** filters, verify, execute, install.
- **Hierarchy:** status → schema → dependency → validation.
- **Primary:** `EXECUTE`. **Secondary:** verify/install.
- **States:** executable / registered-not-executable / unavailable; validation badge.
- **Error:** execute with empty/invalid input → REJECTED_INPUT, never fixture substitution.

---

## 12. Run / Provenance Inspector

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ RUN INSPECTOR    run_id run_0b45…   [timeline ▾]   [manifest ▾]          ▸ replay   ⤓ manifest │
├───────────────────────────────┬──────────────────────────────────────────────────────────────┤
│ TIMELINE                      │ RUN MANIFEST                                                 │
│ 10:02:03 supervisor parse  ⚠ │ run_id · task_id · agent_version · git_commit                │
│ 10:02:04 planner        ✓     │ tool{id,version,container_hash} ×N                           │
│ 10:02:05 target resolve ✓     │ model{name,version} · database{release,hash}                 │
│ 10:02:31 binder retr.   ⚠ 0   │ seed · temperature · timeout · policy · cutoff               │
│ …                             │ inputs_sha256 · params · raw_output · parsed_output          │
│ 10:06:12 degradation    ✓     │ qc_result · error · retry_count · source_provenance          │
│ 10:06:20 critic         REVISE│ reproducibility_hash · replay_verdict                        │
│                               │                                                              │
│ TOOL CALLS (34)               │ EVIDENCE / CITATIONS                                         │
│ ✓28 ~6 ✗0                     │ DOI/PMID · pub_date · db_release · retrieved_at · claim      │
│ avg latency … · retries …     │ ── temporal leakage: 0 ──                                    │
├───────────────────────────────┴──────────────────────────────────────────────────────────────┤
│ ▸ REPLAY RUN   · export manifest JSON   · diff vs another run   · open in benchmark scorer      │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Purpose:** audit exactly what ran, with what versions, and whether it replays.
- **Panels:** timeline, manifest, tool-call stats, evidence/citations, leakage.
- **Controls:** replay, export, diff, open scorer.
- **Hierarchy:** timeline → manifest → citations → replay verdict.
- **Primary:** `REPLAY RUN`. **Secondary:** export/diff.
- **States:** replay PASS/FAIL; leakage count.
- **Error:** version missing → manifest flagged INCOMPLETE, run marked non-reproducible.
