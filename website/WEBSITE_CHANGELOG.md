# WEBSITE_CHANGELOG.md

Log of website changes with the scientific-coherence overhaul.

## v2.0 — scientific-coherence rewrite (2026-09-02)

Positioning and messaging
- Hero rewritten to: **"An evidence-grounded autonomous research system for targeted protein degradation"**; kicker now *AHUJA LAB · IIIT DELHI · TARGETED PROTEIN DEGRADATION*.
- Macro-framework **KNOW → REASON → DESIGN → DISCOVER** added as the primary scientific architecture (hero strip + dedicated capability section), replacing the software-centric "six scientific engines" framing.
- Removed marketing language: "Every invisible interaction, made visible by agents", "Feynman-grade", "zero black boxes", "AI magic", "final build".
- Release chip changed from "v0.3 · final" / "Final build" to **"v0.3 core release · active research development"**; About now separates software release status from scientific validation status.
- About section rewritten around: *PROTAC design is a coupled biological, structural and chemical optimization problem* (copy supplied by the lead developer), with author/affiliation cards and CI/status card.
- Figure caption no longer uses the "Fig 1" label; the hero visual is presented as a *system map* with evidence-type badges and a plain descriptive caption.

Architecture honesty
- Node accounting is now explicit and code-traceable: **23-node core scientific workflow + 8 controlled-search/feedback extensions = 31 documented agent nodes** (`agents/graph.py`), replacing ambiguous "31-node pipeline" phrasing.
- "Feynman contract" renamed to **The scientific contract** (auditable evidence/model gates).

Science-first sections added
- **Mechanistic layers** — "From ternary formation to cellular degradation": hook-effect modeler (equilibrium-only), lysine-ubiquitination feasibility (structural surrogate, real-PDB pending), cooperativity (feasibility, data-gated), degradation + cell-context (trained, transcriptomic; proteotype not claimed).
- **Model panel** — Module 4, Module 5, TACK (DC50/Dmax/binary), SynGlue (DC50/Dmax) kept independent with provenance + validation columns; unified engine explicitly **UNDER EVALUATION**.
- **Validation matrix** — per-capability statuses (VALIDATED BASELINE / TRAINED / PARTIAL / STRUCTURAL SURROGATE / DATA-GATED / UNDER EVALUATION / PLANNED) with evidence type, data source, validation, limitation and public-claim columns; driven by `config/scientific_status.yaml`.
- **Evidence-type badge system** — MEASURED / RETRIEVED / CALCULATED / LEARNED PREDICTION / STRUCTURAL SURROGATE / HEURISTIC / ILLUSTRATIVE / NOT AVAILABLE across cards, tables and captions.

Simulator honesty (credibility fix)
- "Live agent pipeline simulator" → **"Interactive pipeline walkthrough"**.
- Prominent **ILLUSTRATIVE DEMO — NOT A LIVE SCIENTIFIC PREDICTION** banner and per-row badges.
- Explicit disclaimer: browser-only, precomputed illustrative values; run the CLI/API for model-backed predictions.
- Walkthrough stages expanded to mirror the real system: KNOW retrieval & grading → REASON resolution → DESIGN (linkers, **retrosynthesis**, assembly, ADMET) → mechanistic layers (ternary, ubiquitination, cooperativity, hook effect) → DISCOVER (Module 4, Module 5, Pareto dossier).
- Candidate table relabelled "Illustrative Pareto-ranked candidates"; example DC50/ternary values now carry ILLUSTRATIVE badges and are described as examples.

Installation truth
- Removed `pip install protacxtend` and the curl installer (PyPI 404, no install.sh) — install tabs are now **git clone** and **docker** (`docker build -t protacxtend <repo-url>`), with a note "PyPI publishing on the roadmap".
- Workflows rewritten to the actual CLI subcommands (`design`, `structure`, `dose`, `context`, `validate`, `ask`/`learn`/`api`, `contract`).

Documentation hub (rebuilt)
- Six tabs: Getting started · **Technical assets** (databases, live APIs, tools, models, xlsx/csv assets, how to read them) · Modules & models (M1–M7 statuses + artifact paths) · Workflows & CLI · API & data · GitHub & collaborators.
- Repository links updated to the working repo; canonical organization repo (the-ahuja-lab/PROTACXtend) listed with status.

Branding / assets
- PROTACXtend logo (`code/logo.png`, now `website/assets/logo.png`) used in navbar, hero and footer; square favicon variant added (`logo-square.png`).
- Hero uses the logo card + framework strip; visual language kept (PROTACXtend palette, `#8683DD → #706BD6` signature gradient).

Related files touched in the same change: `config/scientific_status.yaml` (new source of truth), `SCIENTIFIC_CLAIM_AUDIT.md`, `SITE_COHERENCE_AUDIT.md`, `AGENTS.md`/`AGENT_WORKFRAME.md` ("Feynman" → audit/scientific-contract language), module tracker de-duplication (stale Module-3 row removed), README badge/install reconciliation, `documentation/WORKFLOWS.md` and `documentation/ARCHITECTURE.md` reconciled with the current CLI/modules.

## v2.1 — canonical hosting on the Ahuja Lab organization (2026-09-02)

- Final code mirrored to **the-ahuja-lab/PROTACXtend** (full history) after the org granted
  push access; the organization repository is now canonical for code, CI and Pages.
- All site links, install commands (git clone / docker), README badges (live site, CI) and
  the docs "GitHub & collaborators" pane now point to **the-ahuja-lab/PROTACXtend** and
  **https://the-ahuja-lab.github.io/PROTACXtend/**; SaveenaSolanki/PROTACXtend is listed as
  the development mirror.
- GitHub Pages on the org repository is enabled by the repository admin (Pages → Source:
  GitHub Actions); the deploy workflow is already in the repo and deploys `website/`.
