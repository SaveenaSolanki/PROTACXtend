"""Linker generation functions."""

from __future__ import annotations

from typing import Sequence

from protacxtend.backend.schemas import LinkerRecord
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def generate_rule_based_linkers(linker_types: Sequence[str], max_linkers: int = 32) -> list[LinkerRecord]:
    return _TOOLBOX.generate_rule_based_linkers(linker_types, max_linkers)


def load_curated_linkers() -> list[dict[str, str]]:
    return _TOOLBOX.load_curated_linkers()


def generate_brics_recap_linkers(linker_types: Sequence[str] | None = None) -> list[LinkerRecord]:
    return _TOOLBOX.generate_linkers(linker_types or ["PEG", "alkyl", "amide"], max_linkers=24)


def generate_known_protac_linkers(linker_types: Sequence[str] | None = None) -> list[LinkerRecord]:
    return _TOOLBOX.generate_linkers(linker_types, max_linkers=24)


def generate_linkers_for_pair(linker_types: Sequence[str] | None = None, max_linkers: int = 64) -> list[LinkerRecord]:
    return _TOOLBOX.generate_linkers(linker_types, max_linkers=max_linkers)


def score_linker_properties(linker: LinkerRecord) -> float:
    return linker.synthetic_feasibility_proxy


# ── Fragment-combination linkers (diversity beyond the curated panel) ──
# Bounded combinatorial enumeration over a small fragment vocabulary,
# followed by RDKit validation + Butina diversity selection.

_FRAG_CORES = [
    "c1ccccc1",           # benzene
    "c1ccncc1",           # pyridine
    "c1nccnc1",           # pyrimidine
    "N1CCNCC1",           # piperazine
    "N1CCOCC1",           # morpholine
    "c1nnc[nH]1",         # triazole
    "c1cc[nH]c1",         # pyrrole
    "C1CCCCC1",           # cyclohexane
]
_FRAG_SPACERS = ["C", "CC", "CCC", "O", "NC", "C(=O)NC", "S", "S(=O)(=O)"]
_ATTACH = "[*:1]", "[*:2]"


def _assemble_fragment_linker(core: str, left: str, right: str) -> str:
    """Compose [*:1]-left-core-right-[*:2] and sanitize attachment dummies."""
    return f"{_ATTACH[0]}{left}{core}{right}{_ATTACH[1]}"


def generate_fragment_combination_linkers(
    max_linkers: int = 64,
    max_heavy: int = 16,
    max_rotatable: int = 8,
) -> list[LinkerRecord]:
    """Enumerate bounded fragment-combination linkers with diversity selection.

    Vocabulary: 8 aromatic/aliphatic cores × (1-2 spacers per side) → up to
    ~8*8*8*2 = 1024 raw combos, filtered by validity/size/flexibility, then
    Butina-clustered to `max_linkers` representatives.
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
    from rdkit.Chem import DataStructs
    from rdkit.Chem.rdMolDescriptors import GetMorganFingerprintAsBitVect

    seen: dict[str, str] = {}
    for core in _FRAG_CORES:
        for left in ["", *_FRAG_SPACERS]:
            for right in ["", *_FRAG_SPACERS]:
                if not left and not right:
                    continue
                smi = _assemble_fragment_linker(core, left, right)
                # Validate with attachment dummies via SMARTS trick: replace dummies
                mol = Chem.MolFromSmiles(smi.replace("[*:1]", "[*]").replace("[*:2]", "[*]"))
                if mol is None:
                    continue
                ha = mol.GetNumHeavyAtoms()
                if not (5 <= ha <= max_heavy):
                    continue
                rot = rdMolDescriptors.CalcNumRotatableBonds(mol)
                if rot > max_rotatable:
                    continue
                clean = smi.replace("[*:1]", "").replace("[*:2]", "")
                seen.setdefault(clean, smi)

    raw = list(seen.values())
    if len(raw) <= max_linkers:
        selected = raw
    else:
        fps = [GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(s.replace("[*:1]", "[*]").replace("[*:2]", "[*]")), 2, 2048) for s in raw]
        # Greedy farthest-point selection for diversity
        selected = [raw[0]]
        rest = list(range(1, len(raw)))
        while len(selected) < max_linkers and rest:
            best_idx, best_min = None, -1.0
            for i in rest:
                fp = fps[i]
                min_d = min(1.0 - DataStructs.TanimotoSimilarity(fp, fps[raw.index(s)]) for s in selected)
                if min_d > best_min:
                    best_min, best_idx = min_d, i
            selected.append(raw[best_idx])
            rest.remove(best_idx)

    def _ha(smi: str) -> int:
        m = Chem.MolFromSmiles(smi)
        return m.GetNumHeavyAtoms() if m else 0

    records: list[LinkerRecord] = []
    for smi in selected:
        full = smi
        props = _TOOLBOX.compute_basic_properties(full.replace("[*:1]", "").replace("[*:2]", ""))
        records.append(
            LinkerRecord(
                name=f"frag_{len(records)}",
                smiles=full,
                linker_class="mixed",
                source="fragment_combination",
                graph_length=max(3, _ha(full.replace("[*:1]", "").replace("[*:2]", ""))),
                effective_length=max(3.0, _ha(full.replace("[*:1]", "").replace("[*:2]", "")) * 0.7),
                rotatable_bonds=int(props.get("rotatable_bonds", 4)),
                tpsa_contribution=float(props.get("tpsa", 0.0)),
                hbd=int(props.get("hbd", 0)),
                hba=int(props.get("hba", 0)),
                synthetic_feasibility_proxy=0.55,
                validity_status=_TOOLBOX.validate_linker(full),
                provenance={"generation_method": "fragment_combination", "vocabulary_size": len(_FRAG_CORES) * len(_FRAG_SPACERS)},
            )
        )
    return records
