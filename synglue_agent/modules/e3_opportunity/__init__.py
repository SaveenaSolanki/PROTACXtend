"""Module 6 — Novel E3 Ligase Opportunity Engine.

rank_e3_ligases(poi, cell_line, tissue, disease, warhead, poi_structure,
top_k) ranks catalog E3 ligases for PROTAC development across independent,
evidence-gated axes: cell-context expression (Module 5 DepMap reuse),
subcellular compatibility (UniProt), recruiter tractability (DOI-cited
ligand library), biological precedent (real PROTAC rows), structural
availability, surface-lysine opportunity (provided structures only),
selectivity opportunity, and uncertainty/OOD flags. Structural feasibility
and any axis without evidence are reported UNKNOWN — never fabricated.
Verdicts: SUPPORTED / PROMISING / EXPLORATORY / INSUFFICIENT EVIDENCE.
"""

from synglue_agent.modules.e3_opportunity.e3_catalog import (
    candidate_universe,
    load_catalog,
)
from synglue_agent.modules.e3_opportunity.predict import rank_e3_ligases
from synglue_agent.modules.e3_opportunity.schemas import (
    MODEL_VERSION,
    CandidateResult,
    E3OpportunityInput,
)

__all__ = ["rank_e3_ligases", "candidate_universe", "load_catalog",
           "E3OpportunityInput", "CandidateResult", "MODEL_VERSION"]
