# DEVELOPMENT ROADMAP (2026-09-02 audit)

Decision hierarchy: 1 CONNECT existing → 2 UPGRADE weak → 3 VALIDATE complete-
but-unvalidated → 4 BUILD only if absent → 5 defer final case studies to
platform freeze. Final case studies are NOT current build tasks.

## NEXT IMMEDIATE TASK
**GAP02 + GAP09 — claims/status sync + single node registry (CONNECT).**
Wire `config/scientific_status.yaml` to the module tracker (it currently marks
M6 as PLANNED) with a verify script, and reconcile the 17-node `real_nodes`
map with the 31-node agent chain (restore the exit-vector node from stub).
Low risk, unblocks trustworthy reporting and consistent audit.

## NEXT 3 TASKS (after immediate)
1. **GAP03 — ternary evidence in the design/ranking loop (CONNECT/P0).**
   Add a cached P4ward (docker) ternary benchmark that default CI can run, and
   let M6 `structural_feasibility`/M5 degradation revision consume real ternary
   outputs when present (keeping the honest None when absent).
2. **GAP01 — prospective validation protocol (VALIDATE/P0).**
   Define the prospective evaluation set (newly published PROTAC pairs / held-
   out literature since dataset freeze) and re-run M4-v2-vs-M5-vs-chemprop +
   M6 retrieval against it. This is the scientific gate before any stronger
   wording in claims.
3. **GAP08 — Active-learning scientific module (M7) (BUILD/post-audit).**
   Only after GAP01/03: build `select_next_experiments()`/`update_models()`
   reusing M4–M6 scorers + uncertainty; keep the existing agent as the caller.

## WHAT NOT TO BUILD (exists already)
- Another linker generator (char-GRU + scorer + optimizer exist).
- Another PROTAC assembler (BRICS/RECAP + validation exist).
- Another degradation predictor (chemprop + M4 + M5 exist — consolidate).
- Another E3 ranker (M6 exists; connect, don't rebuild) and freeze
  `e3_context_engine`/`proteome_selectivity` heuristics after parity.
- Another CRBN/VHL "engine" or another DepMap context extractor.
- A parallel retrosynthesis stack (ASKCOS/AiZynth optional wrappers exist).
- Any new ML module until M4/M5/M6 claims are prospectively gated.

## WHAT TO DEFER TO FINAL CASE STUDIES (platform freeze gate)
1. Public matched-linker potency analysis (linker potency correlation).
2. BRD4–VHL six-compound blinded ranking.
3. Prospective wet-lab design challenge.
4. Manuscript case-study figures.
5. Final wet-lab validation.
(Existing dirs `casestudy/`, `robust/`, `ICM_HMGB2_Hypothesis_Testing/`,
`website/SCIENTIFIC_CLAIM_AUDIT.md` and `work/boltz_output` belong to this
post-platform lane, not to module building.)

## FREEZE CONDITIONS (proposed, for human approval)
Software/platform freeze requires: claims registry synced to
config/scientific_status.yaml (GAP02), single node registry (GAP09), ternary
default-CI path (GAP03), and full test-suite green run recorded
(631 collected; remainder of agent 414 suite run + recorded).
Scientific freeze requires GAP01 prospective protocol results.
