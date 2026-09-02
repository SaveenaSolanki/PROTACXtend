# 09 · LinkerGenerationAgent

| | |
| --- | --- |
| **Node** | 9 — `generate_linkers` |
| **Source** | `synglue_agent/agents/linker_agent.py` |
| **Size** | 28 lines — thinnest agent in the system |
| **Status** | ✅ Built |
| **Data** | `curated_linkers.csv` (13 rows) |
| **Delegates to** | `toolbox.generate_linkers`, `generate_rule_based_linkers`, `linker_scanner.py` (632 lines) |

## Architecture brief

Generates the middle third of the molecule. At 28 lines it is the thinnest agent in the
graph and delegates essentially everything to the 73-method toolbox and to
`linker_scanner.py`, which does the real work: scanning N linkers × M attachment points and
ranking the combinations on geometry, ADMET and synthesisability.

The thinness is appropriate. What sits behind it is not thin — the scanner ran 192
combinations (2 warhead points × 8 E3 points × 12 linkers) in under a second in the case
study, and the stereochemistry engine can preserve chirality through the join.

**This node owns the project's hardest problem.** NP-hard problem #1 is linker
optimisation: the same warhead and the same E3 ligase, with only the linker changed,
produce completely different degradation outcomes. SJFα (13-atom alkyl, amide attachment)
degrades p38α at DC₅₀ 7 nM; SJFδ (10-atom, phenyl attachment) degrades p38δ at 46 nM. Same
foretinib warhead, same VHL ligase. Three atoms of difference switch the target.

The design space is Length × Composition × Rigidity × Attachment × 2 ends, with 150K+
plausible candidates per warhead–E3 pair, and each real evaluation costs $5K–$50K and 2–6
weeks. The agent addresses this by enumerate-and-score, which is the honest available
approach — but it is search, not prediction.

## Data it works on

| Input | Type | Source |
| --- | --- | --- |
| `state.parsed_objective.preferred_linker_types` | `list[str]` | node 1 |
| `state.exit_vectors` | `list[ExitVectorRecord]` | node 8 |
| `curated_linkers.csv` | 13 rows | PEG, alkyl, semi-rigid, with lengths |

## Data it generates

| Output | Type | Contents |
| --- | --- | --- |
| `state.generated_linkers` | `list[LinkerRecord]` | `name`, `smiles`, `class`, `length`, properties |

12+ linker types. Deduplicated via `remove_duplicate_linkers`.

## What is solid

- **Correct delegation.** A 28-line agent over a 632-line scanner is the right split.
- **The scanner is genuinely good** — N×M enumeration with composite scoring across
  geometry, ADMET and synthesis, and it is fast (192 combos, < 1 s in 2D mode).
- **Stereochemistry-aware assembly** is available through
  `assemble_with_stereo_preservation`, which matters because linker attachment at a chiral
  centre changes the exit geometry.
- **Deduplication is built in**, so the candidate explosion is at least not inflated by
  duplicates.
- **The project has correctly identified this as its hardest problem** and documented why.

## What to improve

**1 · Widen the library — 13 curated linkers against a 150K+ space.** The published
corpus is heavily biased (85%+ of known PROTACs use PEG or alkyl), so a 13-row library
inherits that bias and cannot propose anything outside it. Ingesting PROTAC-DB's linker
set is data work, not science, and it is the cheapest real expansion available.

**2 · Wire in a generative linker method.** The Agent_Modules sheet names DiffLinker,
LinkInvent, CReM and BRICS/RECAP as intended tools; none appear in the implemented tool
list. Enumeration over a fixed library can only recombine what is already known. This is
the difference between searching and designing.

**3 · Scan in 3D, not 2D.** The sub-second timing is explicitly "2D mode". Linker
conformational reachability is a 3D property, and the geometric proxy at node 20 already
computes exit-vector angles. Feeding 3D reachability back into scanning would cut the
candidate set before assembly rather than after.

**4 · Record what was searched, not just what was returned.** With a 150K+ space and a
13-row library, the report must state the coverage honestly. A ranked list of 12 linkers
reads as thorough unless the denominator is visible.

**5 · Exploit the length-sensitivity finding explicitly.** The project's own analysis shows
single-atom length changes flip selectivity. The scanner should therefore always sample a
length *series* around any promising linker rather than treating each as an independent
point — the case study's 16 linker variants (best 0.8% pass rate, C14-PEG5) is exactly the
right shape of experiment and should be automated.

## Feasibility note

Item 1 is small and unblocked and should happen first. Item 5 is a scanning-policy change,
also small, and directly encodes the project's most important scientific finding into the
search. Items 2 and 3 are medium and are where this node stops being a lookup and starts
being a design tool.

## 2026-08-12 — Link-INVENT-style scoring + optimization added
- `tools/linker_scoring.py`: faithful Link-INVENT recipe — reverse-sigmoid
  components (LGL, LEL, Flex, HBD, MW, TPSA) × weights [2,2,2,1,2,2], weighted
  product, + batched ADMET-AI penalty (AMES/DILI/hERG). `rank_linkers` scores
  & ranks any linker library (curated/rules/fragment/generative).
- `tools/linker_optimizer.py`: REINFORCE-style policy refinement of the char-GRU
  linker policy (reward = Link-INVENT score × (1−ADMET risk), baseline-subtracted
  gradient, bounded rounds). Persist via linker_generator.optimized.pt.
- Wired: `toolbox.generate_linkers` ranks with `rank_linkers` (default on);
  optimizer behind PROTACPILOT_LINKER_OPTIMIZE=1.
- Effective length = attachment-point bond-path distance (fixes rigid-linker
  zeroing). MW/TPSA bands adapted to isolated linkers (documented deviation:
  Link-INVENT scores these on the full PROTAC).
