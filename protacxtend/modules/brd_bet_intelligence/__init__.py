"""BRD/BET domain-aware intelligence (Module 7).

Evidence-gated, domain-aware knowledge for the four BET bromodomains
(BRD2/BRD3/BRD4/BRDT). It answers:

  * which ligands are measured on which target/domain (BD1 vs BD2);
  * how potent and how domain-/family-selective a warhead is;
  * whether the evidence is measured for the query molecule or only a
    target-level proxy prior.

Curated from in-repo, DOI-cited PROTAC-DB-derived tables (warheads + PROTAC
binary target affinities) with an optional cached ChEMBL BRDT supplement.
See ``data/brd_bet_provenance.json``. Nothing is imputed.
"""
from protacxtend.modules.brd_bet_intelligence.data import (
    BET_GENES,
    canonical_gene,
    is_bet_target,
    load_evidence,
    load_pairs,
    load_summary,
    provenance,
)
from protacxtend.modules.brd_bet_intelligence.selectivity import (
    bet_ligand_table,
    classify_domain_selectivity,
    domain_landscape,
    ligand_selectivity_profile,
    score_brd_bet,
    target_prior,
)

__all__ = [
    "BET_GENES", "canonical_gene", "is_bet_target", "load_evidence",
    "load_pairs", "load_summary", "provenance", "score_brd_bet",
    "ligand_selectivity_profile", "domain_landscape", "target_prior",
    "bet_ligand_table", "classify_domain_selectivity",
]
