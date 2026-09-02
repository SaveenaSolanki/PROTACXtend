"""Target/POI string -> HGNC gene symbol mapping for expression lookup.

Maps the 'Target (Parsed)' vocabulary of PROTAC-Degradation-DB to the gene(s)
whose DepMap expression best represents that POI. Mutation/domain variants map
to the parent gene. Multi-gene or non-human entries map to NaN (no fabricated
expression). Manual entries are reviewed + documented; everything else is a
mechanical strip of variant suffixes.
"""

from __future__ import annotations

import re

# --- manual, non-mechanical entries --------------------------------------
MANUAL = {
    "BCL-xL": "BCL2L1", "Bcl-xL": "BCL2L1", "BCLXL": "BCL2L1",
    "ER": "ESR1", "ERalpha": "ESR1", "ERα": "ESR1", "ERRalpha": "ESRRA",
    "CD147": "BSG", "HADC6": "HDAC6",   # typo in source
    "Fak": "PTK2", "FAK": "PTK2",
    "MEK1": "MAP2K1", "MEK2": "MAP2K2",
    "RSK1": "RPS6KA1", "PYK2": "PTK2B", "SHP2": "PTPN11",
    "AKT": "AKT1", "HSP90": "HSP90AA1",
    "PDEdelta": "PDE6D", "TRKA": "NTRK1", "TrkC": "NTRK3",
    "NPM-ALK": "ALK", "EML4-ALK": "ALK", "TPM3-TRKA": "NTRK1",
    "GCN5": "KAT2A", "PCAF": "KAT2B", "ENL": "MLLT1",
    "Cdc20": "CDC20", "Rpn13": "ADRM1", "FKBP12": "FKBP1A",
    "tau/P-tau": "MAPT", "Tau5": "MAPT", "p-STAT3Y705": "STAT3",
    "pVHL30": "VHL", "BCR-ABL": "ABL1", "BCR-ABL T315I": "ABL1",
    "WT": None, "NS3": None,          # non-human / ambiguous
    "BRD2/3/4": None,                  # multi-gene (3 BET) -> no single expr
    "CRBN": "CRBN",                    # appears both as E3 and target
    "p38alpha": "MAPK14", "p38beta": "MAPK11", "p38delta": "MAPK13",
    "p38γ": "MAPK12", "p38gamma": "MAPK12",
}

# reversed-target forms: 'G1202R ALK' -> ALK etc. handled via gene-vocabulary
# selection when available; these are the hard-coded completions:
REVERSED = {"Exon 19 del": "EGFR", "Exon 20 Ins EGFR": "EGFR"}

# WDR5-HiBiT / HiBiT-BRD7 style suffixes (dash form not handled by space strip)
_HIBIT_DASH = re.compile(r"[-\s]HiBiT$", re.I)
_HIBIT_PRE = re.compile(r"^HiBiT[-\s]", re.I)

STRIP_VARIANT = re.compile(
    r"\s+(BD[12]|long|short|G1202R|C481\w|del\w*|T315I|R683G|V600E|G466V|"
    r"G469A|L858R|T790M|C797S|e19d|ITD|G12C|HiBiT)$", re.I)

MULTI_FAMILY = {"BRD2/3/4", "tau/P-tau"}


def _strip_hight(name: str) -> str:
    n = _HIBIT_PRE.sub("", name)
    n = _HIBIT_DASH.sub("", n)
    return n.strip()


def target_to_gene(target: str, gene_vocab: set | None = None) -> str | None:
    """Best-effort, documented mapping; None = no single gene (feature NaN).

    When a DepMap gene vocabulary is supplied, candidate tokens are selected
    only if they are real genes (kills variant tokens such as G1202R/Exon).
    """
    if target is None or (isinstance(target, float) and target != target):
        return None
    t = str(target).strip()
    if not t:
        return None
    if t in MANUAL:
        return MANUAL[t]
    if t in REVERSED:
        return REVERSED[t]
    t2 = _strip_hight(t)
    if t2 in MANUAL:
        return MANUAL[t2]
    # split on spaces/slashes/commas and consider each token as gene candidate
    tokens = [tok for tok in re.split(r"[\s/,;()]+", t2) if tok]
    if gene_vocab:
        for tok in tokens:
            if tok in gene_vocab:
                return tok
        # variant-first forms: 'G1202R ALK' -> the alpha token that is a real
        # gene but lacks strict caps (e.g. lowercase 'ALK' never happens) :
        return None
    head = tokens[0] if tokens else t2
    while "-" in head:
        pre, _, post = head.rpartition("-")
        if len(post) <= 4 and pre:
            head = pre
        else:
            break
    canon = {"p38alpha": "MAPK14", "p38beta": "MAPK11", "p38delta": "MAPK13"}
    if head.lower() in canon:
        return canon[head.lower()]
    return head if len(head) >= 2 else None
