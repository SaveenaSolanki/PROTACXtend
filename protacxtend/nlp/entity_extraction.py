"""Entity extraction layer for the PROTACXtend natural-language front door.

The original front door guessed the target by scanning for ``for``/``of``/
``target`` followed by the first token matching ``[A-Z0-9]{3,8}``.  That is why
``"degrade BRD4"`` produced ``target = DEGRADE`` and ``"Can BRD4 ..."`` produced
``target = CAN``: the parser was doing positional pattern matching, not entity
recognition.

This module replaces that heuristic with a layered extractor:

1. **Span detection** -- cell lines, E3 ligases, disease contexts and known
   protein aliases are identified *first* and their character spans recorded.
2. **Gene-candidate generation** -- every remaining token is a candidate if it
   is a known gene symbol or matches a conservative gene-symbol shape.
3. **Disambiguation** -- candidates are excluded when they are verbs, modality
   words, disease acronyms, mutation codes or already-claimed spans, then ranked
   by lexical evidence (known symbol) and syntactic context ("degrade X",
   "PROTAC against X", ...).
4. **Intent / modality / constraint extraction** -- the full
   :class:`~protacxtend.backend.schemas.ExtractedEntities` record is populated.

The extractor is deterministic, offline and dependency-light.  It is validated
by :mod:`protacxtend.tests.test_entity_extraction` against the authored prompt
set in ``protacxtend/data/parser_validation_set.json``.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from protacxtend.backend.schemas import ExtractedEntities

ExtractionError = ValueError


# ---------------------------------------------------------------------------
# Lexicons
# ---------------------------------------------------------------------------

#: Canonical E3 ligase names keyed by lower-case alias.  Single source of truth
#: for E3 normalisation across the package.
E3_ALIASES: Dict[str, str] = {
    "crbn": "CRBN", "cereblon": "CRBN",
    "vhl": "VHL", "pvh1": "VHL", "vonhippellindau": "VHL",
    "ciap1": "cIAP1", "birc2": "cIAP1", "iap1": "cIAP1",
    "ciap2": "cIAP2", "birc3": "cIAP2",
    "xiap": "XIAP", "birc4": "XIAP", "iap": "IAP",
    "mdm2": "MDM2", "hdm2": "MDM2", "mdmx": "MDM4", "mdm4": "MDM4",
    "dcaf15": "DCAF15", "dcaf16": "DCAF16", "dcaf11": "DCAF11", "dcaf1": "DCAF1",
    "keap1": "KEAP1",
    "rnf114": "RNF114", "znf313": "RNF114", "rnf4": "RNF4", "rnf126": "RNF126",
    "klhl20": "KLHL20", "klhdc2": "KLHDC2",
    "fem1b": "FEM1B", "fbxo22": "FBXO22", "ahr": "AhR", "skp1": "SKP1",
    "ddb1": "DDB1", "cul2": "CUL2", "cul4": "CUL4", "rbx1": "RBX1",
    "eloc": "ELOC", "elob": "ELOB",
}

#: E3 canonical names that must never be mistaken for a target gene.
E3_CANONICAL: frozenset[str] = frozenset(E3_ALIASES.values()) | frozenset(
    {"DCAF", "CUL", "RNF", "FBXO", "TRIM", "CRL", "SCF", "UBA", "UBE"}
)

#: Seed HGNC symbols covering TPD, oncology and ubiquitin biology.  Additional
#: symbols are loaded from the curated target table at import time.  Unknown
#: symbols are still extractable via gene-shape + context scoring.
_SEED_GENES = """
ABL1 AKT1 AKT2 AKT3 ALK APC AR ARID1A ATM ATR AURKA AURKB BCL2 BCL6 BCR BRAF
BRCA1 BRCA2 BRD2 BRD3 BRD4 BRD7 BRD8 BRD9 BRDT BTK CCND1 CDK1 CDK2 CDK4 CDK6
CDK7 CDK8 CDK9 CDK12 CHEK1 CHEK2 CREBBP CTNNB1 CUL1 CUL2 CUL3 CUL4A CUL4B CUL5
DDB1 DNMT1 DNMT3A DOT1L EED EGFR EP300 ERBB2 ERBB3 ERBB4 ESR1 EZH2 FGFR1 FGFR2
FGFR3 FGFR4 GSPT1 HDAC1 HDAC2 HDAC3 HDAC6 HIF1A HRAS IDH1 IDH2 JAK1 JAK2 JAK3
KDM1A KDM5A KDM6A KEAP1 KIT KRAS MAP2K1 MAP2K2 MAPK1 MAPK3 MCL1 MDM2 MDM4 MET
MTOR MYC MYCN NFE2L2 NOTCH1 NRAS PARP1 PIK3CA PRMT5 PTEN RAF1 RET SMARCA2
SMARCA4 SMARCB1 SRC STAT1 STAT3 STAT5A STAT5B SUZ12 TP53 TYK2 VEGFA WRN XIAP
""".split()


def _load_gene_symbols() -> frozenset[str]:
    genes = {gene.upper() for gene in _SEED_GENES}
    path = Path(__file__).resolve().parents[1] / "data" / "curated_targets.csv"
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for key in ("gene_symbol", "target_name"):
                    value = (row.get(key) or "").strip().upper()
                    if value:
                        genes.add(value)
    except Exception:
        pass
    return frozenset(genes)


GENE_SYMBOLS: frozenset[str] = _load_gene_symbols()


#: Multi-word protein-name aliases mapped to their HGNC symbol.
PROTEIN_ALIASES: Dict[str, str] = {
    "p53": "TP53",
    "her2": "ERBB2",
    "vegf": "VEGFA",
    "nrf2": "NFE2L2",
    "androgen receptor": "AR",
    "estrogen receptor": "ESR1",
    "estrogen receptor alpha": "ESR1",
    "estrogen receptor beta": "ESR2",
    "epidermal growth factor receptor": "EGFR",
    "human epidermal growth factor receptor 2": "ERBB2",
    "bromodomain-containing protein 4": "BRD4",
    "bromodomain containing protein 4": "BRD4",
    "bromodomain-containing protein 9": "BRD9",
    "progesterone receptor": "PGR",
    "glucocorticoid receptor": "NR3C1",
    "signal transducer and activator of transcription 3": "STAT3",
    "signal transducer and activator of transcription 1": "STAT1",
    "signal transducer and activator of transcription 5a": "STAT5A",
    "signal transducer and activator of transcription 5b": "STAT5B",
    "mitogen-activated protein kinase kinase": "MAP2K1",
    "mammalian target of rapamycin": "MTOR",
    "mechanistic target of rapamycin": "MTOR",
    "vascular endothelial growth factor a": "VEGFA",
    "programmed cell death protein 1": "PDCD1",
    "programmed death-ligand 1": "CD274",
    "cytotoxic t-lymphocyte-associated protein 4": "CTLA4",
    "b-cell maturation antigen": "TNFRSF17",
    "tumor necrosis factor receptor superfamily member 17": "TNFRSF17",
    "g protein-coupled receptor class c group 5 member d": "GPRC5D",
    "nuclear factor erythroid 2-related factor 2": "NFE2L2",
    "hypoxia-inducible factor 1-alpha": "HIF1A",
    "hypoxia inducible factor 1 alpha": "HIF1A",
    "myeloid cell leukemia 1": "MCL1",
    "b-cell lymphoma 2": "BCL2",
    "b-cell lymphoma 6": "BCL6",
    "tumor protein p53": "TP53",
    "kirsten rat sarcoma": "KRAS",
    "bruton tyrosine kinase": "BTK",
    "bruton's tyrosine kinase": "BTK",
    "anaplastic lymphoma kinase": "ALK",
    "enhancer of zeste homolog 2": "EZH2",
    "lysine-specific histone demethylase 1a": "KDM1A",
    "protein arginine n-methyltransferase 5": "PRMT5",
    "janus kinase 2": "JAK2",
    "janus kinase 1": "JAK1",
    "histone deacetylase 6": "HDAC6",
    "dna methyltransferase 1": "DNMT1",
    "kelch-like ech-associated protein 1": "KEAP1",
    "cullin 2": "CUL2",
    "cullin 3": "CUL3",
    "cullin 4a": "CUL4A",
    "cullin 4b": "CUL4B",
    "cullin 5": "CUL5",
    "damage-specific dna-binding protein 1": "DDB1",
    "von hippel-lindau protein": "VHL",
    "x-linked inhibitor of apoptosis protein": "XIAP",
    "s-phase kinase-associated protein 1": "SKP1",
    "dna polymerase theta": "POLQ",
    "ataxia telangiectasia mutated": "ATM",
    "poly adp-ribose polymerase 1": "PARP1",
}

#: Stop / non-gene lexicons.  These are never target genes.
_STOPWORDS: frozenset[str] = frozenset(
    """
    A AN AND ARE AS AT BE BEEN BEING BUT BY CAN COULD DESIGN DESIGNS DESIGNED
    DEGRADE DEGRADES DEGRADED DEGRADING DEGRADATION DEGRADER DEGRADERS DID DO
    DOES DOING DONE EACH E3 FOR FROM GIVE GENERATE GENERATED GENERATING HAD HAS
    HAVE HOW IF IN INTO IS IT ITS LET MAKE MAKES MADE MAY ME MOLECULE MOLECULES
    NEED NOT OF ON OR OUR OUT PLEASE PROTAC PROTACS PROVIDE SELECT SELECTS
    SHOULD SO SOME SUCH TARGET TARGETS TARGETED TARGETING THAN THAT THE THEIR
    THEM THEN THERE THESE THIS THOSE TO USE USED USING US WE WHAT WHEN WHERE
    WHICH WHO WHY WILL WITH WOULD YOU YOUR CANNOT FIND FINDS FOUND DISCOVER
    DISCOVERS DISCOVERING DESIGNING NOVEL NOVELTY NEW BEST BETTER RATHER INSTEAD
    VERSUS VS COMPARE COMPARING COMPARISON BETWEEN OVER UNDER ABLE POSSIBLE
    FEASIBLE TRACTABLE TRACTABILITY DRUGGABLE DRUGGABILITY THERAPEUTIC
    THERAPEUTICALLY DEGRADABLE UBIQUITINATE UBIQUITINATION UBIQUITIN PROTEASOME
    MECHANISM MECHANISTIC EVIDENCE VALIDATE VALIDATION VALIDATED CLINICAL
    PRECLINICAL STUDY TRIAL PATIENT PATIENTS DISEASE CANCER TUMOR TUMOUR
    CARCINOMA MALIGNANCY METASTATIC RESISTANT RESISTANCE MUTANT MUTATION MUTATED
    WILDTYPE DEFICIENT DEFICIENCY POSITIVE NEGATIVE OVEREXPRESSING
    OVEREXPRESSION EXPRESSION AMPLIFIED AMPLIFICATION DELETED DELETION LOSS
    GAIN FUNCTION CELL CELLS LINE LINES PROTEIN PROTEINS GENE GENES KINASE
    KINASES RECEPTOR RECEPTORS LIGAND LIGANDS WARHEAD WARHEADS LINKER LINKERS
    COMPOUND COMPOUNDS SMALL INHIBITOR INHIBITORS INHIBIT INHIBITS INHIBITION
    BLOCKER BLOCKING BINDER BINDERS BINDING SELECTIVITY SELECTIVE POTENT POTENCY
    EFFICACY ACTIVE ACTIVITY ASSAY VITRO VIVO DC50 DMAX IC50 EC50 KD KI ADMET
    ADME PK HERG DILI AMES TPSA LOGRULE LIPINSKI SMILES CAS CANDIDATE CANDIDATES
    MOLECULAR GLUE GLUES CHIMERA CHIMERIC BIFUNCTIONAL HETEROBIFUNCTIONAL
    INDUCE INDUCED INDUCING RECRUIT RECRUITS RECRUITING RECRUITMENT HIJACK
    HIJACKING ENGAGE ENGAGING ENGAGEMENT TERNARY COMPLEX COOPERATIVITY
    COOPERATIVE HOOK EFFECT UBIQUITIN-PROTEASOME OLIGONUCLEOTIDE ANTIBODY
    PEPTIDE PEPTIDOMIMETIC MACROCYCLE ALLOSTERIC ORTHOSTERIC COVALENT REVERSIBLE
    IRREVERSIBLE FIRST SECOND THIRD GENERATION OPTIMIZE OPTIMIZATION IMPROVE
    IMPROVEMENT REDESIGN REPURPOSE REPOSITION SERIES BACKUP FOLLOWUP LEAD
    DEVELOPMENT CLINICALLY APPROVED FAIL FAILED FAILING FAILURE SUCCEED
    SUCCEEDED SUCCESS WHILE WHETHER ALREADY STILL YET ONLY JUST ALSO VERY MORE
    MOST LESS LEAST HIGH LOW MEDIUM STRONG WEAK GOOD BAD POOR EXCELLENT
    TISSUE TUMOR-AGNOSTIC AGNOSTIC PRECISION PERSONALIZED SUBTYPE SUBTYPES
    BIOMARKER BIOMARKERS SENSITIZING SYNTHETIC LETHAL LETHALITY COMBINATION
    COMBINATIONS SYNERGY SYNERGISTIC FEEDBACK REBOUND UPREGULATION
    DOWNREGULATION PHOSPHORYLATION METHYLATION ACETYLATION UBIQUITYLATION
    NEDDYLATION SUMOYLATION LIGASE LIGASES SUBSTRATE SUBSTRATES COMPLEX
    COMPLEXES STRUCTURE STRUCTURES POSE POSES DOCKING DOCK CRYO-EM CRYSTAL
    ALPHAFOLD COFOLDING TPD SBDD FBDD CADD AI ML DL QSAR SAR
    CAUSE CAUSED CAUSES CAUSING SWITCH SWITCHED SWITCHES SWITCHING
    RECRUITER RECRUITERS CHOICE CHOOSING CHOOSE CHOOSES PREFER PREFERRED
    PREFERRING PREFERENCE SWAP SWAPPED SWAPPING REPLACE REPLACED REPLACING
    ALTERNATIVE ALTERNATIVES OPTION OPTIONS REASON REASONS EXPLAIN EXPLAINED
    SPLICING BINDING EXPRESSION ACTIVITY FUNCTION PATHWAY MECHANISM PROCESS
    """.split()
)

#: Database / file-format identifiers that are never gene symbols. Without this
#: "use PDB 6HAX" parsed the target as "PDB".
_STOPWORDS = _STOPWORDS | frozenset(
    "PDB CIF EMDB DOI UNIPROT CHEMBL PUBCHEM BINDINGDB RCSB SDF MOL2 INCHI "
    "INTERPRO PFAM ENSEMBL ALPHAFOLD-DB".split()
)

_MODALITIES: Dict[str, str] = {
    "protac": "PROTAC",
    "protacs": "PROTAC",
    "degrader": "degrader",
    "degraders": "degrader",
    "molecular glue": "molecular_glue",
    "molecular glues": "molecular_glue",
    "glue": "molecular_glue",
    "glues": "molecular_glue",
    "inhibitor": "inhibitor",
    "inhibitors": "inhibitor",
    "antibody": "antibody",
    "antibody-drug conjugate": "ADC",
    "adc": "ADC",
    "sirna": "siRNA",
    "antisense": "ASO",
}

_DISEASE_ACRONYMS: frozenset[str] = frozenset(
    {
        "NSCLC", "TNBC", "SCLC", "AML", "ALL", "CLL", "CML", "DLBCL", "GBM",
        "CRC", "HCC", "RCC", "PDAC", "HNSCC", "MDS", "MPN", "MM", "CMML", "APL",
        "CUP", "MTC", "GIST", "NET", "NHL", "ESCC", "EAC", "CRPC", "NASH",
        "NAFLD", "MAFLD", "CKD", "COPD", "IBD", "RA", "SLE", "MS", "ALS", "DMD",
    }
)

_DISEASE_PHRASES: Tuple[str, ...] = (
    "triple-negative breast cancer",
    "triple negative breast cancer",
    "non-small cell lung cancer",
    "non small cell lung cancer",
    "small cell lung cancer",
    "head and neck cancer",
    "head and neck squamous cell carcinoma",
    "colorectal cancer",
    "colon cancer",
    "gastric cancer",
    "pancreatic cancer",
    "pancreatic ductal adenocarcinoma",
    "liver cancer",
    "hepatocellular carcinoma",
    "breast cancer",
    "lung cancer",
    "prostate cancer",
    "ovarian cancer",
    "cervical cancer",
    "endometrial cancer",
    "bladder cancer",
    "renal cell carcinoma",
    "kidney cancer",
    "thyroid cancer",
    "brain cancer",
    "glioblastoma",
    "melanoma",
    "multiple myeloma",
    "acute myeloid leukemia",
    "acute lymphoblastic leukemia",
    "chronic lymphocytic leukemia",
    "chronic myeloid leukemia",
    "myelodysplastic syndrome",
    "lymphoma",
    "leukemia",
    "leukaemia",
    "sarcoma",
    "osteosarcoma",
    "neuroblastoma",
    "medulloblastoma",
    "myelofibrosis",
    "sickle cell disease",
    "cystic fibrosis",
    "alzheimer's disease",
    "parkinson's disease",
    "huntington's disease",
    "amyotrophic lateral sclerosis",
    "inflammatory bowel disease",
    "rheumatoid arthritis",
    "systemic lupus erythematosus",
    "multiple sclerosis",
    "autoimmune disease",
    "inflammation",
    "fibrosis",
    "pulmonary fibrosis",
    "liver fibrosis",
    "nonalcoholic steatohepatitis",
    "nonalcoholic fatty liver disease",
    "metabolic dysfunction-associated steatohepatitis",
    "diabetes",
    "obesity",
    "sepsis",
    "viral infection",
    "bacterial infection",
)

#: Tokens that look like disease context and must be excluded from gene candidacy.
_DISEASE_TOKENS: frozenset[str] = frozenset(
    {
        "CANCER", "CARCINOMA", "TUMOR", "TUMOUR", "MALIGNANCY", "LYMPHOMA",
        "LEUKEMIA", "LEUKAEMIA", "SARCOMA", "GLIOMA", "GLIOBLASTOMA",
        "MELANOMA", "MYELOMA", "NEUROBLASTOMA", "MEDULLOBLASTOMA",
        "ADENOCARCINOMA", "SQUAMOUS", "METASTATIC", "METASTASIS", "RELAPSED",
        "REFRACTORY", "RESISTANT", "RESISTANCE", "DEFICIENT", "DEFICIENCY",
        "MUTANT", "MUTATION", "MUTATED", "POSITIVE", "NEGATIVE", "AMPLIFIED",
        "OVEREXPRESSING", "OVEREXPRESSION", "DELETED", "DELETION", "FUSION",
        "BREAST", "LUNG", "PROSTATE", "OVARIAN", "PANCREATIC", "COLORECTAL",
        "GASTRIC", "LIVER", "HEPATIC", "RENAL", "KIDNEY", "BLADDER", "THYROID",
        "CERVICAL", "ENDOMETRIAL", "BRAIN", "BONE", "SKIN", "BLOOD", "SOLID",
        "HEMATOLOGIC", "MYELOID", "LYMPHOID", "INFLAMMATION", "FIBROSIS",
        "DIABETES", "OBESITY", "SEPSIS", "INFECTION", "VIRAL", "BACTERIAL",
        "AUTOIMMUNE", "STEATOHEPATITIS", "CACHEXIA",
    }
)

#: Mutation-code shapes such as G12D, V600E, L858R, T790M, C797S, R175H.
_MUTATION_RE = re.compile(r"^[A-Z][0-9]{1,4}[A-Z]$")
_FRAMESHIFT_RE = re.compile(r"^(EXON|E)[0-9]{1,2}$|^FS[0-9]*$|^[A-Z][0-9]{1,4}(FS|X|\*)$")

#: PDB identifiers (4 chars, leading digit) such as 5T35, 1AVX, 6HAX. These are
#: structures, never gene symbols — without this guard "5T35" became target "T35".
_PDB_ID_RE = re.compile(r"(?<![A-Za-z0-9])[0-9][A-Za-z0-9]{3}(?![A-Za-z0-9])")

#: Known cell-line names (helps disambiguate e.g. "MOLT4" from a gene).
_KNOWN_CELL_LINES: frozenset[str] = frozenset(
    {
        "HEK293", "HEK293T", "HELA", "MCF7", "MCF10A", "MDAMB231", "MDAMB468",
        "MM1S", "MM1", "RPMI8226", "U266", "K562", "JURKAT", "MOLT4", "THP1",
        "U937", "HL60", "KG1", "MV411", "OCIAML3", "A549", "H1299", "H460",
        "H1975", "PC9", "HCC827", "H358", "HCT116", "SW480", "SW620", "HT29",
        "DLD1", "RKO", "CACO2", "PANC1", "MIAPACA2", "BXPC3", "ASPC1", "CAPAN1",
        "SKOV3", "OVCAR3", "OVCAR8", "A2780", "IGROV1", "PC3", "LNCAP", "DU145",
        "22RV1", "VCAP", "HEPG2", "HUH7", "HEP3B", "SNU449", "SKHEP1", "U87",
        "U251", "LN229", "A172", "T98G", "SH-SY5Y", "SKMEL28", "A375", "WM2664",
        "LOXIMVI", "BT474", "SKBR3", "T47D", "ZR751", "HCC1954", "EFM192A",
        "KPL4", "AU565", "U2OS", "SAOS2", "MG63", "143B", "HOS", "RD", "A673",
        "SKNMC", "NB4", "PL21", "SET2", "HEL", "DAMI", "UT7", "CMK", "MEG01",
        "KASUMI1", "RAW264", "RAW2647", "BMDM", "J774", "P388", "EL4", "EG7",
        "CT26", "4T1", "EO771", "B16", "B16F10", "LLC", "MC38", "PANC02",
    }
)

#: Context cues for gene disambiguation.
_PRE_CUES: Dict[str, float] = {
    "degrade": 4.0, "degrades": 4.0, "degrading": 4.0, "degradation": 4.0,
    "target": 3.0, "targets": 3.0, "targeting": 3.0, "against": 3.0,
    "for": 2.0, "of": 1.5, "inhibit": 2.5, "inhibits": 2.5, "inhibitor": 2.0,
    "selectivity": 2.0, "selectively": 2.0, "bind": 1.5, "binds": 1.5,
    "binder": 2.0, "recruit": 1.5, "recruits": 1.5, "protein": 1.0,
    "knockdown": 2.0, "knockout": 2.0, "silence": 2.0, "silencing": 2.0,
    "eliminate": 2.5, "eliminates": 2.5, "elimination": 2.5, "clear": 1.5,
    "clearance": 1.5, "tractable": 2.0, "druggable": 2.0, "degradable": 2.0,
    "ligand": 1.5, "warhead": 1.5,
}
_POST_CUES: Dict[str, float] = {
    "degrader": 3.0, "degraders": 3.0, "protac": 2.5, "protacs": 2.5,
    "inhibitor": 2.0, "kinase": 1.5, "protein": 1.0, "receptor": 1.5,
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_GENE_SHAPE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")
_GENE_HYPHEN_RE = re.compile(r"^[A-Z][A-Z0-9]{0,9}(?:-[A-Z0-9]{1,6})?$")


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    end: int

    @property
    def upper(self) -> str:
        return self.text.upper()


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    label: str
    value: str


def _tokenise(text: str) -> List[_Token]:
    return [_Token(m.group(0), m.start(), m.end()) for m in _WORD_RE.finditer(text)]


def _span_overlaps(start: int, end: int, spans: Sequence[_Span]) -> bool:
    return any(start < span.end and end > span.start for span in spans)


def _canonical_e3(token: str) -> Optional[str]:
    return E3_ALIASES.get(token.strip().lower())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def normalize_gene_symbol(value: str) -> str:
    return (value or "").strip().upper()


def _detect_e3(text: str) -> Tuple[Optional[str], List[_Span]]:
    """Return the preferred E3 ligase and the spans of every E3 mention."""
    spans: List[_Span] = []
    mentions: List[Tuple[int, str]] = []
    for alias in sorted(E3_ALIASES, key=len, reverse=True):
        for match in re.finditer(
            rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, re.IGNORECASE
        ):
            canonical = E3_ALIASES[alias]
            spans.append(_Span(match.start(), match.end(), "e3", canonical))
            mentions.append((match.start(), canonical))

    if not mentions:
        return None, spans

    mentions.sort()
    deduped: List[Tuple[int, str]] = []
    for pos, canon in mentions:
        if deduped and pos == deduped[-1][0]:
            continue
        deduped.append((pos, canon))

    lower = text.lower()
    for cue in ("instead of", "rather than", "as opposed to", "versus", " vs ", "over "):
        cue_pos = lower.find(cue)
        if cue_pos == -1:
            continue
        before = [canon for pos, canon in deduped if pos < cue_pos]
        after = [canon for pos, canon in deduped if pos >= cue_pos]
        if before:
            return before[-1], spans
        if after:
            return after[-1], spans

    for cue in ("use ", "prefer ", "using ", "with ", "employ ", "recruit "):
        cue_pos = lower.find(cue)
        if cue_pos == -1:
            continue
        after = [canon for pos, canon in deduped if pos >= cue_pos + len(cue) - 1]
        if after:
            return after[0], spans

    return deduped[0][1], spans


def _detect_cell_lines(text: str) -> Tuple[Optional[str], List[_Span]]:
    spans: List[_Span] = []
    cell_line: Optional[str] = None
    patterns = [
        re.compile(r"\bcell\s*lines?\s+([A-Za-z0-9_.\-]+)", re.IGNORECASE),
        re.compile(r"\b(?:in|using|with)\s+([A-Za-z0-9_.\-]+)\s+cells?\b", re.IGNORECASE),
        re.compile(r"\b([A-Za-z0-9_.\-]+)\s+cell\s+lines?\b", re.IGNORECASE),
        re.compile(r"\b([A-Za-z]{1,6}[A-Za-z0-9]*(?:[.\-][A-Za-z0-9]+)*)\s+cells?\b", re.IGNORECASE),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            value = match.group(1).strip(" .,:;")
            if not value:
                continue
            compact = re.sub(r"[^A-Za-z0-9]", "", value).upper()
            if compact in _KNOWN_CELL_LINES or value.upper() in _KNOWN_CELL_LINES:
                cell_line = value
                spans.append(_Span(match.start(1), match.end(1), "cell_line", value))
                return cell_line, spans
    return cell_line, spans


def _detect_disease(text: str) -> Tuple[Optional[str], List[_Span]]:
    spans: List[_Span] = []
    lower = text.lower()
    best: Optional[Tuple[int, int, str]] = None

    modifier_re = re.compile(
        r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9]{1,11})\s*-\s*"
        r"(deficient|mutant|mutated|positive|negative|amplified|overexpressing|deleted|fused)"
        r"(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    for match in modifier_re.finditer(text):
        start, end = match.start(), match.end()
        phrase = text[start:end].strip()
        tail = re.match(r"\s+([A-Za-z0-9\-]+(?:\s+[A-Za-z0-9\-]+)?)", text[end:])
        if tail:
            candidate_tail = tail.group(1).strip()
            head = candidate_tail.upper().split()[0]
            if head in _DISEASE_ACRONYMS or any(
                candidate_tail.lower().startswith(p) for p in _DISEASE_PHRASES
            ):
                end = end + tail.start(1) + len(candidate_tail)
                phrase = text[start:end].strip()
        spans.append(_Span(start, end, "disease", phrase))
        if best is None or (end - start) > (best[1] - best[0]):
            best = (start, end, phrase)

    for phrase in _DISEASE_PHRASES:
        for match in re.finditer(re.escape(phrase), lower):
            spans.append(_Span(match.start(), match.end(), "disease", text[match.start():match.end()]))
            if best is None or (match.end() - match.start()) > (best[1] - best[0]):
                best = (match.start(), match.end(), text[match.start():match.end()])

    for match in re.finditer(r"\b([A-Za-z0-9\-]{2,12})\b", text):
        token = match.group(1)
        base = re.split(r"[-/]", token)[0].upper()
        if base in _DISEASE_ACRONYMS and base not in _STOPWORDS:
            spans.append(_Span(match.start(), match.end(), "disease", token))
            if best is None or (match.end() - match.start()) > (best[1] - best[0]):
                best = (match.start(), match.end(), token)

    if best is None:
        return None, spans
    return best[2], spans


def _extract_modality(text: str) -> str:
    lower = text.lower()
    for phrase in sorted(_MODALITIES, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", lower):
            return _MODALITIES[phrase]
    return "unspecified"


def _extract_intent(text: str) -> Tuple[str, str]:
    lower = text.lower()
    if re.search(r"\b(why|what caused|explain).{0,30}\bfail|fail(ed|ure)?\b", lower):
        return "failure_analysis", "failure_diagnosis"
    if re.search(r"\b(instead of|rather than|versus|vs\.?|compare|comparison|better than|prefer)\b", lower):
        return "comparison", "comparative_assessment"
    if re.search(r"\b(find|identify|discover|select|choose|which|what)\b.{0,25}\be3\b", lower) or re.search(
        r"\be3\b.{0,20}\b(for|against|to)\b", lower
    ):
        return "e3_selection", "e3_selection"
    if re.search(r"\b(tractable|tractability|druggable|feasible|feasibility|possible|capable)\b", lower):
        return "tractability_assessment", "target_assessment"
    if re.search(r"\b(be|is|are|was|were|get|gets)\b.{0,25}\b(degraded|degradable|eliminated|cleared|ubiquitinated)\b", lower) or re.search(
        r"\bcan\b.{0,25}\b(degrade|degraded|be degraded|be eliminated)\b", lower
    ):
        return "degradation_query", "target_assessment"
    if re.search(r"\b(mechanism|mechanistic|how does|how do|why does|why do|pathway)\b", lower):
        return "mechanism_query", "mechanism_query"
    if re.search(r"\b(design|generate|create|make|build|propose|develop|optimize)\b", lower):
        return "design", "protac_design"
    if re.search(r"\b(degrade|degradation|degrader|protac)\b", lower):
        return "degradation_query", "target_assessment"
    return "general_query", "general_query"


def _candidate_genes(
    tokens: Sequence[_Token], excluded_spans: Sequence[_Span], text: str = ""
) -> List[Tuple[_Token, float, bool]]:
    candidates: List[Tuple[_Token, float, bool]] = []
    for index, token in enumerate(tokens):
        if _span_overlaps(token.start, token.end, excluded_spans):
            continue
        # Skip a token that is the tail of a digit-led identifier (e.g. the
        # "T35" inside a PDB id "5T35"), which the tokenizer split off.
        if token.start > 0 and text[token.start - 1].isdigit():
            continue
        upper = token.upper
        if len(upper) < 2 or len(upper) > 12:
            continue
        if upper in _STOPWORDS or upper in _DISEASE_TOKENS or upper in _DISEASE_ACRONYMS:
            continue
        if upper in E3_CANONICAL:
            continue
        if _MUTATION_RE.match(upper) or _FRAMESHIFT_RE.match(upper):
            continue

        is_known = upper in GENE_SYMBOLS
        is_gene_shape = bool(_GENE_SHAPE_RE.match(upper)) or bool(_GENE_HYPHEN_RE.match(upper))
        if not (is_known or is_gene_shape):
            continue

        score = 10.0 if is_known else 0.0
        if token.text.isupper():
            score += 1.5
        # Symbols containing a digit (RBM39, SF3B1, BRD4, KRAS G12D) are strong
        # gene indicators; common English verbs/adjectives are not.
        if re.search(r"[A-Za-z]\d|\d[A-Za-z]", upper):
            score += 3.0
        if not is_known and re.search(r"(ING|ED|TION|MENT|NESS|ANCE|ENCE|ERS?)$", upper):
            score -= 2.5
        prev_upper = tokens[index - 1].upper.lower() if index > 0 else ""
        next_upper = tokens[index + 1].upper.lower() if index + 1 < len(tokens) else ""
        score += _PRE_CUES.get(prev_upper, 0.0)
        score += _POST_CUES.get(next_upper, 0.0)
        if index >= 2:
            score += 0.25 * _PRE_CUES.get(tokens[index - 2].upper.lower(), 0.0)
        candidates.append((token, score, is_known))
    return candidates


def _extract_target_gene(
    text: str, tokens: Sequence[_Token], excluded_spans: Sequence[_Span]
) -> Tuple[str, List[str], float]:
    lower = text.lower()
    alias_hits: List[Tuple[int, int, str]] = []
    for phrase, gene in sorted(PROTEIN_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        for match in re.finditer(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", lower):
            alias_hits.append((match.start(), match.end(), gene))
    if alias_hits:
        usable = [hit for hit in alias_hits if not _span_overlaps(hit[0], hit[1], excluded_spans)]
        chosen = (usable or alias_hits)[0]
        return chosen[2], [], 1.0

    candidates = _candidate_genes(tokens, excluded_spans, text)
    if not candidates:
        return "", [], 0.0

    known = [(tok, score) for tok, score, is_known in candidates if is_known]
    pool = known if known else [(tok, score) for tok, score, _ in candidates]
    pool.sort(key=lambda item: (-item[1], item[0].start))
    chosen_token, chosen_score = pool[0]
    alternates = [tok.upper for tok, _ in pool[1:6]]
    confidence = min(1.0, 0.55 + 0.04 * chosen_score) if known else min(0.8, 0.25 + 0.06 * chosen_score)
    return chosen_token.upper, alternates, confidence


def _extract_constraints(text: str, upper: str) -> Dict[str, Any]:
    from protacxtend.backend.config import DEFAULT_LINKER_TYPES, DEFAULT_RANKING_WEIGHTS

    constraints: Dict[str, Any] = {}
    cell_line, _ = _detect_cell_lines(text)
    if cell_line:
        constraints["cell_line"] = cell_line

    smiles_candidates = re.findall(
        r"(?:(?:SMILES|smiles)\s*[:=]?\s*)([A-Za-z0-9@+\-\[\]\(\)=#$\\/%.:]+)", text
    )
    if smiles_candidates:
        constraints["warhead_smiles"] = smiles_candidates[0]

    linker_types = [
        lt for lt in ["PEG", "alkyl", "piperazine", "triazole", "amide", "rigid aromatic", "mixed polar"]
        if lt.upper() in upper
    ]
    constraints["preferred_linker_types"] = linker_types or list(DEFAULT_LINKER_TYPES)

    candidate_count = 50
    count_match = re.search(
        r"(\d+)(?:\s+[A-Za-z0-9\-]+){0,3}\s+(?:candidates|PROTACs|designs|molecules)",
        text, flags=re.IGNORECASE,
    )
    if count_match:
        candidate_count = max(1, min(500, int(count_match.group(1))))
    constraints["candidate_count"] = candidate_count

    admet: Dict[str, Any] = {}
    if "HERG" in upper:
        admet["avoid_hERG"] = True
    if "DILI" in upper:
        admet["avoid_DILI"] = True
    if "AMES" in upper:
        admet["avoid_AMES"] = True
    tpsa_match = re.search(r"TPSA\s*(?:<|LESS THAN|UNDER|BELOW)\s*(\d+)", upper)
    if tpsa_match:
        admet["max_tpsa"] = float(tpsa_match.group(1))
    if "LOW TPSA" in upper or "AVOID HIGH TPSA" in upper:
        admet.setdefault("max_tpsa", 190.0)
    constraints["admet_constraints"] = admet

    objective_terms: List[str] = []
    if "LOW DC50" in upper:
        objective_terms.append("low DC50")
    if "HIGH DMAX" in upper:
        objective_terms.append("high Dmax")
    if "NOVEL" in upper:
        objective_terms.append("novelty")
    if "HERG" in upper:
        objective_terms.append("low hERG risk")
    constraints["optimization_objective"] = ", ".join(objective_terms) if objective_terms else (
        "balanced degradation, ADME/Tox, novelty, and synthesis feasibility"
    )
    constraints["novelty_requirement"] = "high" if "NOVEL" in upper else "medium"
    constraints["use_structure_aware_ranking"] = any(term in upper for term in ["STRUCTURE", "TERNARY", "DOCK", "POSE"])
    constraints["use_retrosynthesis_filtering"] = any(
        term in upper for term in ["RETROSYNTHESIS", "SYNTHETICALLY FEASIBLE", "SYNTHESIS"]
    )
    constraints["desired_output_format"] = (
        "json" if "JSON" in upper else "csv" if "CSV" in upper else "table" if "TABLE" in upper else "markdown"
    )
    constraints["ranking_weights"] = dict(DEFAULT_RANKING_WEIGHTS)

    expression_overrides: Dict[str, float] = {}
    for e3_name, value in re.findall(
        r"\b(CRBN|VHL|MDM2|IAP|cIAP1)\s+expression\s*(?:=|:)\s*(0?\.\d+|1(?:\.0)?|high|medium|low)\b",
        text, flags=re.IGNORECASE,
    ):
        token = value.lower()
        expression_overrides[E3_ALIASES.get(e3_name.lower(), e3_name.upper())] = {
            "high": 1.0, "medium": 0.6, "low": 0.2,
        }.get(token, float(token) if token.replace(".", "", 1).isdigit() else 0.6)
    constraints["expression_overrides"] = expression_overrides

    instead = re.search(r"instead of\s+([A-Za-z0-9]+)", text, flags=re.IGNORECASE)
    if instead:
        fallback = _canonical_e3(instead.group(1))
        if fallback:
            constraints["e3_fallback"] = fallback
    return constraints


def extract_entities(user_request: str) -> ExtractedEntities:
    """Extract the canonical entity record from a free-text request."""
    text = (user_request or "").strip()
    if not text:
        return ExtractedEntities(
            intent="general_query", target_gene="", disease_context=None,
            requested_modality="unspecified", e3_preference=None,
            molecule_constraints={}, task_type="general_query", confidence=0.0,
        )

    upper = text.upper()
    tokens = _tokenise(text)

    e3_preference, e3_spans = _detect_e3(text)
    cell_line, cell_spans = _detect_cell_lines(text)
    disease_context, disease_spans = _detect_disease(text)

    excluded: List[_Span] = list(e3_spans) + list(cell_spans) + list(disease_spans)
    for match in _PDB_ID_RE.finditer(text):
        excluded.append(_Span(match.start(), match.end(), "pdb_id", match.group(0)))
    if cell_line:
        for match in re.finditer(re.escape(cell_line), text, re.IGNORECASE):
            excluded.append(_Span(match.start(), match.end(), "cell_line", cell_line))

    target_gene, alternates, gene_confidence = _extract_target_gene(text, tokens, excluded)

    intent, task_type = _extract_intent(text)
    modality = _extract_modality(text)
    constraints = _extract_constraints(text, upper)
    if alternates:
        constraints["alternate_target_candidates"] = alternates

    confidence = 0.15 + 0.55 * gene_confidence
    if target_gene:
        confidence += 0.15
    if intent != "general_query":
        confidence += 0.05
    if e3_preference:
        confidence += 0.05
    if not target_gene:
        confidence = min(confidence, 0.45)
    confidence = round(max(0.0, min(0.99, confidence)), 3)

    return ExtractedEntities(
        intent=intent,
        target_gene=target_gene,
        disease_context=disease_context,
        requested_modality=modality,
        e3_preference=e3_preference,
        molecule_constraints=constraints,
        task_type=task_type,
        confidence=confidence,
    )


__all__ = [
    "E3_ALIASES",
    "GENE_SYMBOLS",
    "PROTEIN_ALIASES",
    "ExtractionError",
    "extract_entities",
    "normalize_gene_symbol",
]
