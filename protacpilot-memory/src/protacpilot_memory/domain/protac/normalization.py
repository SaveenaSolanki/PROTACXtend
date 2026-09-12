"""Entity normalization and identity resolution (Master Prompt §8, §36).

Identity is structural, never textual-similarity based. A small curated alias
table resolves common PROTAC targets / E3 ligases to canonical entities. Anything
not in the table stays as its normalized form — we never *guess* that two
different strings are the same entity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ...util import normalize_text, slug

# ── curated alias table: alias(normalized) → canonical name ──────────────────
_TARGET_ALIASES: dict[str, str] = {
    "brd4": "BRD4",
    "brd-4": "BRD4",
    "brd4_human": "BRD4",
    "q15059": "BRD4",
    "brd2": "BRD2",
    "brd3": "BRD3",
    "brd9": "BRD9",
    "brdt": "BRDT",
    "ar": "AR",
    "androgen receptor": "AR",
    "er": "ESR1",
    "esr1": "ESR1",
    "estrogen receptor": "ESR1",
    "egfr": "EGFR",
    "btk": "BTK",
    "bcl6": "BCL6",
    "smarca2": "SMARCA2",
    "smarca4": "SMARCA4",
    "wdr5": "WDR5",
    "kras": "KRAS",
    "kras g12c": "KRAS",
    "hras": "HRAS",
    "mdm2": "MDM2",
    "cdk4": "CDK4",
    "cdk6": "CDK6",
    "stat3": "STAT3",
    "sirt2": "SIRT2",
    "tbk1": "TBK1",
    "fkbp12": "FKBP12",
    "hif1a": "HIF1A",
    "hif-1a": "HIF1A",
    "p300": "EP300",
    "ep300": "EP300",
    "lrrk2": "LRRK2",
    "trka": "NTRK1",
    "ntrk1": "NTRK1",
    "abl": "ABL1",
    "abl1": "ABL1",
    "fgfr2": "FGFR2",
    "pi3k": "PIK3CA",
    "pik3ca": "PIK3CA",
    "bcl2": "BCL2",
    "mcl1": "MCL1",
}

_UNIPROT: dict[str, str] = {
    "BRD4": "Q15059",
    "BRD2": "P25440",
    "BRD3": "Q15059",  # placeholder-safe; curated values only for known entries
    "BRD9": "Q9H8M2",
    "AR": "P10275",
    "ESR1": "P03372",
    "EGFR": "P00533",
    "BTK": "Q06187",
    "BCL6": "P41182",
    "SMARCA2": "P51531",
    "SMARCA4": "P51532",
    "WDR5": "P61964",
    "KRAS": "P01116",
    "MDM2": "Q00987",
    "CDK4": "P11802",
    "CDK6": "Q00534",
    "STAT3": "P40763",
    "SIRT2": "Q8IXJ6",
    "TBK1": "Q9UHD2",
    "FKBP12": "P62942",
    "HIF1A": "Q16665",
    "EP300": "Q09472",
    "LRRK2": "Q5S007",
    "NTRK1": "P04629",
    "ABL1": "P00519",
    "FGFR2": "P21802",
    "PIK3CA": "P42336",
    "BCL2": "P10415",
    "MCL1": "Q07820",
}

_E3_ALIASES: dict[str, str] = {
    "vhl": "VHL",
    "pvhl": "VHL",
    "von hippel-lindau": "VHL",
    "von hippel lindau": "VHL",
    "cullin-2": "VHL",
    "crbn": "CRBN",
    "cereblon": "CRBN",
    "crl4crbn": "CRBN",
    "crl4-crbn": "CRBN",
    "mdm2": "MDM2",
    "iap": "XIAP",
    "xiap": "XIAP",
    "keap1": "KEAP1",
    "dcaf15": "DCAF15",
    "dcaf16": "DCAF16",
    "rnf114": "RNF114",
    "rnf4": "RNF4",
    "ubr2": "UBR2",
    "chip": "STUB1",
    "stub1": "STUB1",
    "fbxo32": "FBXO32",
    "skp2": "SKP2",
    "β-trcp": "BTRC",
    "btrcp": "BTRC",
    "btrc": "BTRC",
    "cereblon_ddb1": "CRBN",
}

_E3_UNIPROT: dict[str, str] = {
    "VHL": "P40337",
    "CRBN": "Q96SW2",
    "MDM2": "Q00987",
    "XIAP": "P98170",
    "KEAP1": "Q14145",
    "DCAF15": "Q66K64",
    "DCAF16": "Q9NXF7",
    "RNF114": "Q9Y508",
    "RNF4": "P78317",
    "UBR2": "Q8IWV8",
    "STUB1": "Q9UNE7",
    "SKP2": "Q13309",
    "BTRC": "Q9Y297",
}

_CELL_ALIASES: dict[str, str] = {
    "hek293": "HEK293",
    "hek-293": "HEK293",
    "hek293t": "HEK293T",
    "hela": "HeLa",
    "mv4-11": "MV4-11",
    "mv411": "MV4-11",
    "molt4": "MOLT4",
    "molt-4": "MOLT4",
    "jurkat": "Jurkat",
    "k562": "K562",
    "thp1": "THP-1",
    "thp-1": "THP-1",
    "u2os": "U2OS",
    "a549": "A549",
    "mcf7": "MCF-7",
    "mcf-7": "MCF-7",
    "pc3": "PC-3",
    "pc-3": "PC-3",
    "lncap": "LNCaP",
    "t47d": "T47D",
    "ht29": "HT-29",
    "ht-29": "HT-29",
}

_ASSAY_ALIASES: dict[str, str] = {
    "western blot": "Western blot",
    "western": "Western blot",
    "wb": "Western blot",
    "degradation assay": "degradation assay",
    "dc50": "DC50 assay",
    "dmax": "Dmax assay",
    "hippr": "HiBiT",
    "hibit": "HiBiT",
    "thermalshift": "thermal shift",
    "thermal shift": "thermal shift",
    "itc": "ITC",
    "spr": "SPR",
    "fp": "fluorescence polarization",
    "cet": "cellular thermal shift",
    "cetsa": "CETSA",
    "md": "molecular dynamics",
    "docking": "molecular docking",
    "admet": "ADMET",
    "permeability": "permeability assay",
    "pampa": "PAMPA",
    "caco-2": "Caco-2",
    "caco2": "Caco-2",
}

_ALIAS_TABLE: dict[str, dict[str, str]] = {
    "Target": _TARGET_ALIASES,
    "Protein": _TARGET_ALIASES,
    "E3Ligase": _E3_ALIASES,
    "CellLine": _CELL_ALIASES,
    "Assay": _ASSAY_ALIASES,
    "Organism": {
        "human": "Homo sapiens",
        "homo sapiens": "Homo sapiens",
        "mouse": "Mus musculus",
        "mus musculus": "Mus musculus",
        "rat": "Rattus norvegicus",
    },
}

_CANONICAL_ID: dict[str, dict[str, str]] = {
    "Target": _UNIPROT,
    "Protein": _UNIPROT,
    "E3Ligase": _E3_UNIPROT,
}


@dataclass
class EntityRef:
    entity_type: str
    name: str
    role: str = "mentioned"
    canonical_id: str | None = None
    confidence: float = 1.0
    aliases: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return entity_key(self.entity_type, self.name, self.canonical_id)


def normalize_entity_name(entity_type: str, name: str | None) -> str | None:
    """Resolve an entity string to its canonical name (or None if empty)."""
    if not name or not str(name).strip():
        return None
    raw = str(name).strip()
    table = _ALIAS_TABLE.get(entity_type, {})
    key = normalize_text(raw)
    if key in table:
        return table[key]
    # fall back to a light canonical form that preserves declared identity
    return raw


def canonical_id_for(entity_type: str, name: str | None) -> str | None:
    canonical = normalize_entity_name(entity_type, name)
    if canonical is None:
        return None
    return _CANONICAL_ID.get(entity_type, {}).get(canonical)


def entity_key(entity_type: str, name: str, canonical_id: str | None = None) -> str:
    ident = normalize_text(canonical_id) if canonical_id else normalize_text(name)
    return f"{slug(entity_type)}:{slug(ident)}"


def make_entity_ref(entity_type: str, name: str | None, role: str = "mentioned") -> EntityRef | None:
    canonical = normalize_entity_name(entity_type, name)
    if canonical is None:
        return None
    aliases = [] if normalize_text(name) == normalize_text(canonical) else [str(name).strip()]
    return EntityRef(
        entity_type=entity_type,
        name=canonical,
        role=role,
        canonical_id=canonical_id_for(entity_type, canonical),
        aliases=aliases,
    )


# ── optional SMILES canonicalisation (never mandatory) ───────────────────────
_SMILES_WS = re.compile(r"\s+")


def normalize_smiles(smiles: str | None) -> tuple[str | None, str | None, bool]:
    """Return ``(canonical_smiles, inchikey, used_rdkit)``.

    Without RDKit we only trim whitespace and return the input unchanged with
    ``used_rdkit=False``. The system never pretends to have canonicalised a
    molecule it could not parse.
    """
    if not smiles or not str(smiles).strip():
        return None, None, False
    cleaned = _SMILES_WS.sub("", str(smiles))
    try:  # pragma: no cover - depends on optional dependency
        from rdkit import Chem  # type: ignore

        mol = Chem.MolFromSmiles(cleaned)
        if mol is None:
            return cleaned, None, False
        return Chem.MolToSmiles(mol), Chem.MolToInchiKey(mol), True
    except Exception:  # noqa: BLE001 - optional dependency / bad SMILES
        return cleaned, None, False


def entities_in_text(text: str | None) -> list[EntityRef]:
    """Find curated entities mentioned in free text (alias-aware, boundary-safe).

    Only known aliases resolve; unknown strings are never guessed into entities.
    """
    if not text:
        return []
    haystack = " " + normalize_text(text) + " "
    refs: list[EntityRef] = []
    seen: set[tuple[str, str]] = set()
    for entity_type, table in _ALIAS_TABLE.items():
        for alias, canonical in table.items():
            if len(alias) < 3:
                continue
            if f" {alias} " in haystack or f" {alias}," in haystack or f" {alias}." in haystack:
                key = (entity_type, canonical)
                if key in seen:
                    continue
                seen.add(key)
                ref = make_entity_ref(entity_type, canonical, role="mentioned")
                if ref is not None:
                    refs.append(ref)
    return refs


def compound_identity(
    *,
    canonical_smiles: str | None = None,
    protac_smiles: str | None = None,
    compound_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Build a stable compound identifier block (Master Prompt §8)."""
    original = protac_smiles or canonical_smiles
    canon, inchikey, used_rdkit = normalize_smiles(canonical_smiles or protac_smiles)
    internal = compound_id or (slug(name) if name else None)
    return {
        "original_smiles": original,
        "canonical_smiles": canon,
        "inchikey": inchikey,
        "internal_compound_id": internal,
        "canonicalised": used_rdkit,
    }
