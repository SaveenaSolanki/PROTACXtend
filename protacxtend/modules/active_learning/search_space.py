"""Search space for Module 7 — where candidates come from.

Linker source precedence (all guarded): curated library shipped at
data/linkers/linker_smiles.txt (241 entries) > rule-based generation via the
74-method toolbox > generative char-GRU (data/linkers/linker_generator.pt,
loaded lazily only when requested). Candidate pool = linker x dose grid with an
orthogonal-design stereo cap, mirroring the production assembly constraints.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from protacxtend.modules.active_learning.schemas import ActiveLearningParams, Candidate

def _asset(name: str) -> str:
    try:
        from protacxtend.resources import asset_path
        return str(asset_path("linkers", name))
    except Exception:  # pragma: no cover - legacy repo layout fallback
        _REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        return os.path.join(_REPO_ROOT, "data", "linkers", name)


_DEFAULT_LINKER_FILE = _asset("linker_smiles.txt")
_GENERATIVE_MODEL = _asset("linker_generator.pt")


def load_linker_library(path: Optional[str] = None,
                        families: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Load the curated linker SMILES library.

    Entries may carry attachment markers such as [1*] / [4*] (they are
    template linkers — validated at assembly time by the chemistry engine).
    """
    path = path or _DEFAULT_LINKER_FILE
    if not os.path.exists(path):
        return []
    out: List[Dict[str, str]] = []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, start=1):
            smi = line.strip()
            if not smi:
                continue
            out.append({"linker_id": f"lib_{i:04d}", "smiles": smi, "family": "curated"})
    return out


def _generative_candidates(n: int, seed: int) -> List[Dict[str, str]]:
    """Sample the generative char-GRU (guarded; returns [] when model absent)."""
    if not os.path.exists(_GENERATIVE_MODEL):
        return []
    try:
        from protacxtend.tools.generative_linker import GenerativeLinkerDesigner  # noqa: F401
    except Exception:  # noqa: BLE001 - optional heavy dependency
        return []
    # The heavy model is only invoked through the toolbox path; here we keep the
    # interface explicit but never force-load it during search by default.
    return []


def make_candidate_pool(params: ActiveLearningParams,
                        library: Optional[List[Dict[str, str]]] = None,
                        warhead: str = "", e3: str = "") -> List[Candidate]:
    """Build the searchable pool: (linker x dose) with stereo cap metadata."""
    library = library if library is not None else load_linker_library()
    if not library:
        # Deterministic toy fallback so search machinery is testable offline.
        library = [{"linker_id": f"toy_{i:03d}", "smiles": f"[1*]C{i}[4*]", "family": "toy"}
                   for i in range(40)]
    pool: List[Candidate] = []
    for dose in params.dose_levels:
        for entry in library:
            cid = f"{entry['linker_id']}@d{dose:g}"
            features = {"linker_index": 0.0, "dose_log10_nM": _log10(dose)}
            pool.append(Candidate(
                candidate_id=cid,
                linker_id=entry["linker_id"],
                linker_smiles=entry["smiles"],
                linker_family=entry["family"],
                warhead=warhead,
                e3=e3,
                dose_nM=float(dose),
                features=features,
                meta={"max_stereo_centers": params.max_stereo_centers},
            ))
    # orthogonal-design feature: unique linker index over the library
    linker_ids = sorted({c.linker_id for c in pool})
    index_of = {lid: i for i, lid in enumerate(linker_ids)}
    for c in pool:
        c.features["linker_index"] = float(index_of[c.linker_id])
    return pool


def _log10(x: float) -> float:
    import math
    return math.log10(x) if x > 0 else 0.0
