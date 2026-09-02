"""Time the post-degradation v0.1 stages on 150 synthetic candidates."""
from __future__ import annotations

import time

from synglue_agent.backend.schemas import (
    ADMETPrediction,
    CandidateRecord,
    DegradationPrediction,
    NoveltyResult,
    RankingResult,
)
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox

N = 150
SMILES = "CC(=O)Oc1ccccc1C(=O)O"
t = ProtacDesignToolbox()

cands = [CandidateRecord(candidate_id=f"c{i}", full_protac_smiles=SMILES,
                         warhead_smiles="CC(=O)Oc1ccccc1C(=O)O",
                         e3_ligand_smiles="O=C1N(C2CCCCC2)C(=O)c2ccccc21",
                         e3_ligase="CRBN", linker_class="PEG")
         for i in range(N)]
degs = [DegradationPrediction(candidate_id=f"c{i}", predicted_dc50_nM=100.0 + i,
                              predicted_dmax_percent=50 + (i % 40),
                              degradation_probability=0.4 + 0.3 * (i % 3) / 2,
                              model_confidence=0.55, applicability_domain_score=0.5,
                              model_version="tack-style-v1 (DC50/Dmax primary) + chemprop cross-check")
        for i in range(N)]
admet = [ADMETPrediction(candidate_id=f"c{i}") for i in range(N)]
nov = [NoveltyResult(candidate_id=f"c{i}") for i in range(N)]

t0 = time.time()
rankings = t.rank_candidates(cands, degs, admet, nov, [], [], [], [], [], {})
print(f"rank_candidates: {time.time()-t0:.1f}s -> {len(rankings)} rows", flush=True)

t0 = time.time()
diverse = t.choose_diverse_representatives(cands, rankings, max_count=16)
print(f"choose_diverse_representatives: {time.time()-t0:.1f}s -> {len(diverse)}", flush=True)

t0 = time.time()
ev = t.evolve_with_generations(cands, rankings, admet, max_generations=10,
                               novelty_floor=0.10, patience=2)
print(f"evolve_with_generations: {time.time()-t0:.1f}s -> stop={ev.get('stop_reason')}", flush=True)