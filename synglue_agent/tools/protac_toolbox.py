"""Deterministic PROTAC design toolbox.

This module is the scientific tool layer. Agent classes call these methods, and
thin modules such as ``warhead_selector.py`` expose the same functions for users
who want a toolbox-style API without running the full workflow.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import logging
import re
import time
from collections import defaultdict

logger = logging.getLogger("protacpilot.toolbox")
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from synglue_agent.backend.config import (
    DATA_DIR,
    DEFAULT_E3_LIGASES,
    DEFAULT_LINKER_TYPES,
    DEFAULT_RANKING_WEIGHTS,
    WORKFLOW_LOG_DIR,
    ensure_directories,
)

E3_ALIASES = {
    "crbn": "CRBN", "cereblon": "CRBN",
    "vhl": "VHL", "pvh1": "VHL", "vonhippellindau": "VHL",
    "ciap1": "cIAP1", "birc2": "cIAP1", "iap1": "cIAP1",
    "ciap2": "cIAP2", "birc3": "cIAP2",
    "xiap": "XIAP", "birc4": "XIAP", "iap": "IAP",
    "mdm2": "MDM2", "hdm2": "MDM2",
    "dcaf15": "DCAF15", "dcaf16": "DCAF16", "dcaf11": "DCAF11", "dcaf1": "DCAF1",
    "keap1": "KEAP1",
    "rnf114": "RNF114", "znf313": "RNF114", "rnf4": "RNF4", "rnf126": "RNF126",
    "klhl20": "KLHL20", "klhdc2": "KLHDC2",
    "fem1b": "FEM1B", "fbxo22": "FBXO22", "ahr": "AhR", "skp1": "SKP1",
}

from synglue_agent.backend.schemas import (
    ADMETPrediction,
    AgentTrace,
    ActiveLearningUpdate,
    ApplicabilityDomainResult,
    AssayFeedbackRecord,
    BinderRecord,
    CandidateRecord,
    CooperativityPrediction,
    ConstructionAttempt,
    DegradationPrediction,
    DiversityCluster,
    E3ContextPrediction,
    E3LigandRecord,
    ExitVectorRecord,
    HookEffectPrediction,
    LinkerRecord,
    NoveltyResult,
    ParsedObjective,
    RankingResult,
    ReflectionReview,
    SearchPolicy,
    TargetRecord,
    TernaryFeasibilityResult,
    WarheadRecord,
    WorkflowState,
    model_to_dict,
)
from synglue_agent.tools.chemistry_core import (
    analyze_protac_like_properties,
    detect_attachment_points,
)
from synglue_agent.tools.chemistry_core import (
    compute_descriptors as compute_core_descriptors,
)
from synglue_agent.tools.structural_scoring import score_ternary_pose_for_candidate

try:  # pragma: no cover - optional scientific dependency.
    from rdkit import Chem, rdBase
    from rdkit.Chem import AllChem, Crippen, Descriptors, Lipinski, rdMolDescriptors

    RDKIT_AVAILABLE = True
    rdBase.DisableLog("rdApp.warning")
    rdBase.DisableLog("rdApp.error")
except Exception:  # pragma: no cover - default in this execution environment.
    Chem = None
    AllChem = None
    Crippen = None
    Descriptors = None
    Lipinski = None
    rdMolDescriptors = None
    RDKIT_AVAILABLE = False


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


_PROTACDB_EXACT_INDEX: Dict[int, Dict[str, Dict[str, Any]]] = {}


def _protacdb_exact_index() -> Dict[str, Dict[str, Any]]:
    """InChIKey -> first row index over the STABLE cached normalized table.

    ``load_normalized_protacdb()`` wraps the lru_cached tuple in a NEW list on
    every call, so id(list) changes each call; keying on the cached TUPLE
    object (protacdb_client._load_normalized_protacdb_all) is stable.
    Row keys prefer the normalized 'inchikey' field; a fallback RDKit
    InChIKey is computed only for rows that lack it (once, not per-candidate).
    """
    from synglue_agent.tools.protacdb_client import _load_normalized_protacdb_all

    rows = _load_normalized_protacdb_all()  # cached tuple, stable object
    key = id(rows)
    cached = _PROTACDB_EXACT_INDEX.get(key)
    if cached is not None:
        return cached
    index: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        row_key = row.get("inchikey") or chem_identity(row.get("smiles", ""))
        if row_key:
            index.setdefault(row_key, row)
    if len(_PROTACDB_EXACT_INDEX) > 4:
        _PROTACDB_EXACT_INDEX.clear()
    _PROTACDB_EXACT_INDEX[key] = index
    return index


def _numeric_tokens(value: Any) -> list[float]:
    if value in ("", None):
        return []
    return [float(item) for item in re.findall(r"\d+(?:\.\d+)?", str(value))]


def _best_nanomolar_score(value: Any, default: float = 0.55) -> float:
    values = _numeric_tokens(value)
    if not values:
        return default
    best = max(0.01, min(values))
    return _clamp(1.0 - math.log10(best + 1.0) / 5.0)


def _norm_name(value: str | None) -> str:
    return (value or "").strip().upper()


def _has_attachment(smiles: str) -> bool:
    return "[*" in smiles or "*" in smiles


def _remove_attachment_markers(smiles: str) -> str:
    cleaned = re.sub(r"\(\[\*:?\d*\]\)", "", smiles)
    cleaned = re.sub(r"\[\*:?\d*\]", "", cleaned).replace("*", "")
    return cleaned.replace("()", "")


def _annotate_hypothetical_attachment(smiles: str) -> str:
    if _has_attachment(smiles):
        return smiles
    return f"{smiles}[*:1]"


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"



def chem_identity(smiles: str) -> Optional[str]:
    """Full InChIKey (incl. stereo layer) for any molecule — the canonical
    identity key for dedup/seen-sets (AGENT_ARCHITECTURE_UPDATE §0.1)."""
    try:
        from rdkit import Chem
        from rdkit.Chem.inchi import MolToInchiKey
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return MolToInchiKey(mol)
    except Exception:  # noqa: BLE001
        return None

class ProtacDesignToolbox:
    """All deterministic PROTAC design tools used by SynGlue agents."""

    def __init__(self, data_dir: Path = DATA_DIR):
        ensure_directories()
        self.data_dir = Path(data_dir)
        self.rdkit_available = RDKIT_AVAILABLE

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def load_table(self, filename: str) -> list[dict[str, str]]:
        path = self.data_dir / filename
        if not path.exists():
            return []
        with path.open("r", newline="", encoding="utf-8") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    def load_curated_targets(self) -> list[dict[str, str]]:
        return self.load_table("curated_targets.csv")

    def load_curated_warheads(self) -> list[dict[str, str]]:
        return self.load_table("curated_warheads.csv")

    def load_external_warhead_seed(self) -> list[dict[str, str]]:
        return self.load_table("warhead_seed_metaboglue_gold.csv")

    def load_curated_e3_ligands(self) -> list[dict[str, str]]:
        return self.load_table("curated_e3_ligands.csv")

    def load_curated_linkers(self) -> list[dict[str, str]]:
        return self.load_table("curated_linkers.csv")

    def load_known_protacs(self) -> list[dict[str, str]]:
        rows = self.load_table("known_protac_smiles.csv")
        if rows:
            return rows
        return self.load_table("protacdb_local.csv")

    # ------------------------------------------------------------------
    # Request parsing and guardrails
    # ------------------------------------------------------------------
    def parse_user_request(self, user_request: str) -> ParsedObjective:
        text = user_request.strip()
        upper = text.upper()

        cell_line = None
        cell_patterns = [
            r"\bcell\s*line\s+([A-Za-z0-9_.-]+)",
            r"\bin\s+([A-Za-z0-9_.-]+)\s+cells\b",
            r"\b([A-Za-z0-9_.-]+)\s+cell\s+line\b",
        ]
        for pattern in cell_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                cell_line = match.group(1)
                break
        target_parse_text = text
        if cell_line:
            target_parse_text = re.sub(re.escape(cell_line), " ", target_parse_text, flags=re.IGNORECASE)

        e3 = None
        for ligase in ["CRBN", "VHL", "IAP", "MDM2", "DCAF", "DDB1"]:
            if ligase in upper:
                e3 = ligase
                break

        target_name = ""
        target_patterns = [
            r"\bfor\s+([A-Za-z0-9\-]+)",
            r"\bof\s+([A-Za-z0-9\-]+)",
            r"\btarget\s+([A-Za-z0-9\-]+)",
        ]
        for pattern in target_patterns:
            match = re.search(pattern, target_parse_text, flags=re.IGNORECASE)
            if match:
                candidate = match.group(1).strip(" .,:;")
                if candidate.upper() not in {"A", "THE", "LOW", "HIGH", "CRBN", "VHL"}:
                    target_name = candidate
                    break
        if not target_name:
            genes = re.findall(r"\b[A-Z0-9]{3,8}\b", target_parse_text.upper())
            stop_tokens = {"CRBN", "VHL", "PROTAC", "PROTACS", "SMILES", "DESIGN", "CANDIDATES", "CELLS"}
            genes = [gene for gene in genes if gene not in stop_tokens and not gene.startswith("MM")]
            target_name = genes[0] if genes else ""

        smiles_candidates = re.findall(r"(?:(?:SMILES|smiles)\s*[:=]?\s*)([A-Za-z0-9@+\-\[\]\(\)=#$\\/%.:]+)", text)
        warhead_smiles = smiles_candidates[0] if smiles_candidates else None

        linker_types = []
        for linker_type in ["PEG", "alkyl", "piperazine", "triazole", "amide", "rigid aromatic", "mixed polar"]:
            if linker_type.upper() in upper:
                linker_types.append(linker_type if linker_type.isupper() else linker_type)
        if not linker_types:
            linker_types = list(DEFAULT_LINKER_TYPES)

        candidate_count = 50
        count_match = re.search(r"(\d+)(?:\s+[A-Za-z0-9\-]+){0,3}\s+(?:candidates|PROTACs|designs|molecules)", text, flags=re.IGNORECASE)
        if count_match:
            candidate_count = max(1, min(500, int(count_match.group(1))))

        admet_constraints: dict[str, Any] = {}
        if "HERG" in upper:
            admet_constraints["avoid_hERG"] = True
        if "DILI" in upper:
            admet_constraints["avoid_DILI"] = True
        if "AMES" in upper:
            admet_constraints["avoid_AMES"] = True
        tpsa_match = re.search(r"TPSA\s*(?:<|LESS THAN|UNDER|BELOW)\s*(\d+)", upper)
        if tpsa_match:
            admet_constraints["max_tpsa"] = float(tpsa_match.group(1))
        if "LOW TPSA" in upper or "AVOID HIGH TPSA" in upper:
            admet_constraints.setdefault("max_tpsa", 190.0)

        expression_overrides: dict[str, float] = {}
        for e3_name, value in re.findall(r"\b(CRBN|VHL|MDM2|IAP|cIAP1)\s+expression\s*(?:=|:)\s*(0?\.\d+|1(?:\.0)?|high|medium|low)\b", text, flags=re.IGNORECASE):
            token = value.lower()
            expression_overrides[E3_ALIASES.get(e3_name.lower(), e3_name.upper())] = {
                "high": 1.0,
                "medium": 0.6,
                "low": 0.2,
            }.get(token, float(token) if token.replace(".", "", 1).isdigit() else 0.6)

        use_structure = any(term in upper for term in ["STRUCTURE", "TERNARY", "DOCK", "POSE"])
        use_retro = any(term in upper for term in ["RETROSYNTHESIS", "SYNTHETICALLY FEASIBLE", "SYNTHESIS"])
        output_format = "json" if "JSON" in upper else "csv" if "CSV" in upper else "table" if "TABLE" in upper else "markdown"

        objective_terms = []
        if "LOW DC50" in upper:
            objective_terms.append("low DC50")
        if "HIGH DMAX" in upper or "HIGH DMAX" in upper.replace("D_MAX", "DMAX"):
            objective_terms.append("high Dmax")
        if "NOVEL" in upper:
            objective_terms.append("novelty")
        if "HERG" in upper:
            objective_terms.append("low hERG risk")
        optimization = ", ".join(objective_terms) if objective_terms else "balanced degradation, ADME/Tox, novelty, and synthesis feasibility"

        return ParsedObjective(
            target_name=target_name,
            warhead_smiles=warhead_smiles,
            e3_ligase=e3,
            preferred_linker_types=linker_types,
            candidate_count=candidate_count,
            optimization_objective=optimization,
            admet_constraints=admet_constraints,
            novelty_requirement="high" if "NOVEL" in upper else "medium",
            use_structure_aware_ranking=use_structure,
            use_retrosynthesis_filtering=use_retro,
            desired_output_format=output_format,
            ranking_weights=dict(DEFAULT_RANKING_WEIGHTS),
            cell_line=cell_line,
            expression_overrides=expression_overrides,
        )

    def safety_precheck(self, state: WorkflowState) -> WorkflowState:
        unsafe_terms = ["scale-up", "human dosing", "in vivo dosing", "administer to humans"]
        if any(term in state.user_request.lower() for term in unsafe_terms):
            state.warnings.append(
                "Request includes experimental or dosing language. SynGlue-Agent will only provide computational prioritization and requires expert review."
            )
        return state

    # ------------------------------------------------------------------
    # Target and binder tools
    # ------------------------------------------------------------------
    def resolve_target(self, target_name: str, uniprot_id: str | None = None) -> TargetRecord:
        query = _norm_name(uniprot_id or target_name)
        targets = self.load_curated_targets()
        target_rows = []
        for row in targets:
            synonyms = [item.strip().upper() for item in row.get("synonyms", "").split("|")]
            values = {_norm_name(row.get("target_name")), _norm_name(row.get("gene_symbol")), _norm_name(row.get("uniprot_id")), *synonyms}
            if query in values:
                target_rows.append(row)

        uniprot_error = None
        if query:
            try:
                from synglue_agent.backend.uniprot_client import (
                    resolve_target_via_uniprot,
                )

                api_record, api_result = resolve_target_via_uniprot(target_name, uniprot_id, timeout=4.0)
                if api_record is not None:
                    if target_rows:
                        row = target_rows[0]
                        api_record.structures = [item for item in row.get("structures", "").split("|") if item]
                        api_record.known_binder_count = _safe_int(row.get("known_binder_count"), 0)
                        api_record.tractability_score = _safe_float(row.get("tractability_score"), api_record.tractability_score)
                        api_record.external_ids["local_curated_seed_matched"] = True
                    return api_record
                uniprot_error = api_result.get("error") if isinstance(api_result, dict) else "UniProt lookup returned no record."
            except Exception as exc:
                uniprot_error = f"UniProt executable lookup failed: {exc}"

        if not target_rows:
            try:
                from synglue_agent.tools.online_ligand_miner import (
                    resolve_target_from_chembl,
                    retrieve_gcoupler_biology_context,
                )

                online_record, online_warnings = resolve_target_from_chembl(target_name)
                if online_record is not None:
                    online_record.warnings.extend(online_warnings)
                    return online_record
                biology, biology_warnings = retrieve_gcoupler_biology_context(target_name)
                warnings = ["Target not found in local curated table or ChEMBL target search."]
                if uniprot_error:
                    warnings.append(f"UniProt REST lookup did not provide a real API record: {uniprot_error}")
                warnings.extend(online_warnings)
                warnings.extend(biology_warnings)
                return TargetRecord(
                    target_name=target_name or "unresolved",
                    gene_symbol=target_name.upper() if target_name else "",
                    uniprot_id=uniprot_id,
                    uniprot_confidence=0.0,
                    known_binder_count=0,
                    tractability_score=0.12 if biology else 0.05,
                    source="biology context fallback" if biology else "unresolved",
                    biology_context=biology,
                    warnings=warnings
                    + [
                        "No ligand-derived warhead can be built unless a chemical inhibitor/activator SMILES is found or provided by the user."
                    ],
                )
            except Exception as exc:
                fallback_warning = f"Online target fallback failed: {exc}"
            return TargetRecord(
                target_name=target_name or "unresolved",
                gene_symbol=target_name.upper() if target_name else "",
                uniprot_id=uniprot_id,
                uniprot_confidence=0.2 if target_name else 0.0,
                known_binder_count=0,
                tractability_score=0.15,
                source="local_curated_seed",
                warnings=[
                    "Target not found in local curated table.",
                    *([f"UniProt REST lookup did not provide a real API record: {uniprot_error}"] if uniprot_error else []),
                    fallback_warning,
                ],
            )

        row = target_rows[0]
        synonyms = [item for item in row.get("synonyms", "").split("|") if item]
        structures = [item for item in row.get("structures", "").split("|") if item]
        return TargetRecord(
            target_name=row.get("target_name", target_name),
            gene_symbol=row.get("gene_symbol", target_name.upper()),
            uniprot_id=row.get("uniprot_id") or uniprot_id,
            organism=row.get("organism", "human"),
            synonyms=synonyms,
            structures=structures,
            alphafold_id=row.get("alphafold_id") or None,
            uniprot_confidence=_safe_float(row.get("uniprot_confidence"), 0.9),
            known_binder_count=_safe_int(row.get("known_binder_count"), 0),
            tractability_score=_safe_float(row.get("tractability_score"), 0.5),
            source="local_curated_seed",
            warnings=([f"UniProt REST lookup did not provide a real API record: {uniprot_error}"] if uniprot_error else []),
        )

    def retrieve_known_binders(
        self,
        target_record: TargetRecord,
        potency_threshold_nM: float = 1000.0,
        activity_types: Sequence[str] = ("IC50", "Ki", "Kd", "EC50"),
    ) -> list[BinderRecord]:
        rows = self.load_curated_warheads()
        target_values = {_norm_name(target_record.target_name), _norm_name(target_record.gene_symbol), _norm_name(target_record.uniprot_id)}
        binders: list[BinderRecord] = []
        for row in rows:
            if _norm_name(row.get("target")) not in target_values:
                continue
            activity_type = row.get("activity_type", "IC50")
            activity = _safe_float(row.get("activity_nM"), 999999.0)
            if activity_type not in activity_types or activity > potency_threshold_nM:
                continue
            p_activity = self.compute_p_activity(activity)
            binders.append(
                BinderRecord(
                    name=row.get("name", ""),
                    target=row.get("target", ""),
                    smiles=row.get("smiles", ""),
                    activity_type=activity_type,
                    activity_nM=activity,
                    p_activity=p_activity,
                    assay_confidence=_safe_float(row.get("assay_confidence"), 0.75),
                    source=f"local_curated_seed:{row.get('source', 'curated_warheads.csv')}",
                    year=_safe_int(row.get("year"), 0) or None,
                    metadata={"exit_vector_confidence": row.get("exit_vector_confidence", ""), "real_output_generated": False},
                )
            )
        binders.sort(key=lambda item: (item.activity_nM if item.activity_nM is not None else 999999.0, -item.assay_confidence))
        binders.extend(self._retrieve_external_seed_binders(target_record, potency_threshold_nM, activity_types))
        binders.sort(key=lambda item: (item.activity_nM if item.activity_nM is not None else 999999.0, -item.assay_confidence))
        return binders

    def _retrieve_external_seed_binders(
        self,
        target_record: TargetRecord,
        potency_threshold_nM: float,
        activity_types: Sequence[str],
    ) -> list[BinderRecord]:
        rows = self.load_external_warhead_seed()
        if not rows:
            return []
        query_values = {_norm_name(target_record.uniprot_id), _norm_name(target_record.gene_symbol), _norm_name(target_record.target_name)}
        allowed_types = {item.upper() for item in activity_types}
        binders: list[BinderRecord] = []
        seen: set[str] = set()
        for row in rows:
            uniprot = _norm_name(row.get("uniprot_id"))
            if uniprot and uniprot not in query_values:
                continue
            activity_type = (row.get("gt_affinity_type") or "").strip().upper()
            if activity_type and activity_type not in allowed_types:
                continue
            activity = _safe_float(row.get("gt_affinity_nM"), 999999.0)
            if activity <= 0 or activity > potency_threshold_nM:
                continue
            smiles = row.get("SMILES", "")
            if not smiles or smiles in seen:
                continue
            seen.add(smiles)
            binders.append(
                BinderRecord(
                    name=row.get("ligand_name") or f"metaboglue_seed_{len(binders)+1}",
                    target=target_record.gene_symbol or target_record.target_name,
                    smiles=smiles,
                    activity_type=activity_type or "IC50",
                    activity_nM=activity,
                    p_activity=self.compute_p_activity(activity),
                    assay_confidence=0.65,
                    source="local_curated_seed:warhead_seed_metaboglue_gold.csv",
                    metadata={
                        "gt_activity_text": row.get("gt_activity_text"),
                        "gt_source_column": row.get("gt_source_column"),
                        "gt_training_reliability": row.get("gt_training_reliability"),
                        "real_output_generated": False,
                    },
                )
            )
        return binders

    def mine_external_binders(self, target_record: TargetRecord) -> tuple[list[BinderRecord], list[str]]:
        try:
            from synglue_agent.tools.online_ligand_miner import (
                load_local_drugbank_binders,
                retrieve_chembl_bioactive_ligands,
                retrieve_gcoupler_biology_context,
            )
        except Exception as exc:
            return [], [f"External binder-mining tools are unavailable: {exc}"]

        binders: list[BinderRecord] = []
        warnings: list[str] = []
        drugbank_binders, drugbank_warnings = load_local_drugbank_binders(target_record)
        chembl_binders, chembl_warnings = retrieve_chembl_bioactive_ligands(target_record)
        binders.extend(drugbank_binders)
        binders.extend(chembl_binders)
        warnings.extend(drugbank_warnings)
        warnings.extend(chembl_warnings)
        if not binders:
            biology, biology_warnings = retrieve_gcoupler_biology_context(target_record.gene_symbol or target_record.target_name)
            target_record.biology_context = biology
            warnings.extend(biology_warnings)
            warnings.append(
                "Biology context was retrieved, but no chemical inhibitor/activator SMILES was available for PROTAC construction."
            )
        else:
            target_record.known_binder_count = len(binders)
            target_record.tractability_score = max(target_record.tractability_score, min(0.72, 0.35 + 0.02 * len(binders)))
        return binders, warnings

    def compute_p_activity(self, activity_nM: float) -> float:
        if activity_nM <= 0:
            return 0.0
        return -math.log10(activity_nM * 1e-9)

    # ------------------------------------------------------------------
    # Component selection and exit vectors
    # ------------------------------------------------------------------
    def select_warheads(
        self,
        target_record: TargetRecord | None,
        binders: Sequence[BinderRecord],
        user_warhead_smiles: str | None = None,
        max_warheads: int = 6,
    ) -> list[WarheadRecord]:
        if user_warhead_smiles:
            validity = self.validate_smiles(user_warhead_smiles)
            return [
                WarheadRecord(
                    name="user_provided_warhead",
                    target=target_record.gene_symbol if target_record else "user_target",
                    smiles=user_warhead_smiles,
                    source="user provided",
                    potency_score=0.5,
                    derivatization_score=0.65 if _has_attachment(user_warhead_smiles) else 0.35,
                    exit_vector_confidence=0.9 if _has_attachment(user_warhead_smiles) else 0.35,
                    source_confidence=0.5,
                    chemical_validity=validity,
                    provenance={"note": "No potency assigned to user-provided warhead."},
                )
            ]

        rows_by_name = {row.get("name", ""): row for row in self.load_curated_warheads()}
        warheads: list[WarheadRecord] = []
        for binder in binders:
            row = rows_by_name.get(binder.name, {})
            needs_exit_vector_hypothesis = bool(binder.metadata.get("needs_exit_vector_hypothesis"))
            smiles = _annotate_hypothetical_attachment(binder.smiles) if needs_exit_vector_hypothesis else binder.smiles
            potency_score = self.score_warhead_potency(binder.activity_nM)
            deriv_score = _safe_float(row.get("derivatization_score"), 0.6)
            if needs_exit_vector_hypothesis:
                deriv_score = min(deriv_score, 0.42)
            exit_conf = _safe_float(row.get("exit_vector_confidence"), 0.7 if _has_attachment(smiles) else 0.35)
            if needs_exit_vector_hypothesis:
                exit_conf = min(exit_conf, 0.32)
            source_conf = 0.5 * binder.assay_confidence + 0.5 * _safe_float(row.get("source_confidence"), 0.7)
            provenance = {"activity_type": binder.activity_type, "activity_nM": binder.activity_nM}
            provenance.update(binder.metadata)
            if needs_exit_vector_hypothesis:
                provenance["exit_vector_warning"] = "Hypothetical attachment marker added by deterministic tool; chemist review required."
            warheads.append(
                WarheadRecord(
                    name=binder.name,
                    target=binder.target,
                    smiles=smiles,
                    source=binder.source,
                    potency_nM=binder.activity_nM,
                    potency_score=potency_score,
                    derivatization_score=deriv_score,
                    exit_vector_confidence=exit_conf,
                    source_confidence=source_conf,
                    chemical_validity=self.validate_smiles(smiles),
                    provenance=provenance,
                )
            )
        warheads.sort(key=lambda item: item.potency_score + item.derivatization_score + item.exit_vector_confidence, reverse=True)
        return warheads[:max_warheads]

    def score_warhead_potency(self, activity_nM: float | None) -> float:
        if activity_nM is None:
            return 0.45
        return _clamp((7.0 - math.log10(max(activity_nM, 1e-6))) / 4.0)

    def select_e3_ligands(
        self,
        e3_ligase: str | None = None,
        e3_ligand_smiles: str | None = None,
        max_ligands_per_e3: int = 3,
    ) -> list[E3LigandRecord]:
        if e3_ligand_smiles:
            ligase = e3_ligase or "user_specified"
            return [
                E3LigandRecord(
                    name="user_provided_e3_ligand",
                    e3_ligase=ligase,
                    smiles=e3_ligand_smiles,
                    ligand_class="user provided",
                    source="user provided",
                    exit_vector_confidence=0.9 if _has_attachment(e3_ligand_smiles) else 0.35,
                    source_confidence=0.5,
                    diversity_score=0.5,
                    provenance={"validation": self.validate_smiles(e3_ligand_smiles)},
                )
            ]

        requested = [_norm_name(e3_ligase)] if e3_ligase else DEFAULT_E3_LIGASES
        rows = [row for row in self.load_curated_e3_ligands() if _norm_name(row.get("e3_ligase")) in requested]
        grouped: dict[str, list[E3LigandRecord]] = defaultdict(list)
        for row in rows:
            ligand = E3LigandRecord(
                name=row.get("name", ""),
                e3_ligase=row.get("e3_ligase", ""),
                smiles=row.get("smiles", ""),
                ligand_class=row.get("ligand_class", ""),
                source=row.get("source", "local curated e3 ligands"),
                exit_vector_confidence=_safe_float(row.get("exit_vector_confidence"), 0.75),
                stereochemistry_valid=row.get("stereochemistry_valid", "true").lower() != "false",
                source_confidence=_safe_float(row.get("source_confidence"), 0.75),
                diversity_score=_safe_float(row.get("diversity_score"), 0.5),
                provenance={
                    "known_degrader_usage": row.get("known_degrader_usage", ""),
                    "article_doi": row.get("article_doi", ""),
                    "uniprot": row.get("uniprot", ""),
                    "activity_nM": row.get("activity_nM", ""),
                    "attachment_point": row.get("attachment_point", "baked-in marker"),
                },
            )
            grouped[_norm_name(ligand.e3_ligase)].append(ligand)

        selected: list[E3LigandRecord] = []
        for ligase in requested:
            ligands = grouped.get(ligase, [])
            ligands.sort(key=lambda item: item.exit_vector_confidence + item.source_confidence + item.diversity_score, reverse=True)
            selected.extend(ligands[:max_ligands_per_e3])
        return selected

    def detect_exit_vectors(self, molecules: Sequence[Any], role: str) -> list[ExitVectorRecord]:
        vectors: list[ExitVectorRecord] = []
        for molecule in molecules:
            smiles = getattr(molecule, "smiles", "")
            name = getattr(molecule, "name", "molecule")
            attachment = detect_attachment_points(smiles)
            if attachment["num_dummy_atoms"] > 0:
                confidence = min(0.95, getattr(molecule, "exit_vector_confidence", 0.8) or 0.8)
                mapped = attachment["atom_map_numbers"]
                vectors.append(
                    ExitVectorRecord(
                        molecule_name=name,
                        molecule_role=role,
                        smiles=smiles,
                        attachment_atom_index=attachment["dummy_atom_indices"][0] if attachment["dummy_atom_indices"] else 0,
                        attachment_smarts=f"[*:{mapped[0]}]" if mapped else "[*]",
                        confidence=confidence,
                        rationale="Explicit RDKit dummy attachment atom found in curated or user-provided SMILES.",
                        warning=attachment["warning"],
                    )
                )
            else:
                vectors.append(
                    ExitVectorRecord(
                        molecule_name=name,
                        molecule_role=role,
                        smiles=smiles,
                        confidence=0.25,
                        rationale="No explicit attachment marker found.",
                        warning="Attachment vector is ambiguous; curated map or user input is recommended.",
                        failure_reason="missing_attachment_marker",
                    )
                )
        return vectors

    # ------------------------------------------------------------------
    # Linkers and construction
    # ------------------------------------------------------------------
    def build_search_policy(self, objective: ParsedObjective) -> SearchPolicy:
        """Create bounded budgets for NP-hard PROTAC search.

        The policy deliberately overgenerates only a small multiple of the
        requested final count, then uses cheap filters before structural work.
        """
        requested = max(1, int(objective.candidate_count or 50))
        final_budget = min(500, requested)
        expensive_budget = max(10, min(50, final_budget, requested))
        cheap_budget = max(expensive_budget, min(250, max(final_budget * 3, 40)))
        construction_budget = max(cheap_budget, min(1000, max(final_budget * 6, 80)))
        linker_budget = max(12, min(64, final_budget * 2))
        e3_budget = 3 if objective.e3_ligase else 6
        return SearchPolicy(
            linker_budget=linker_budget,
            e3_ligand_budget=e3_budget,
            exit_vector_budget=max(8, min(24, e3_budget * 4)),
            stereoisomer_budget_per_candidate=4,
            construction_budget=construction_budget,
            cheap_filter_budget=cheap_budget,
            expensive_modeling_budget=expensive_budget,
            final_candidate_budget=final_budget,
        )

    def generate_linkers(
        self,
        linker_types: Sequence[str] | None = None,
        length_range: tuple[int, int] = (3, 14),
        max_linkers: int = 64,
    ) -> list[LinkerRecord]:
        requested = {_norm_name(item) for item in (linker_types or DEFAULT_LINKER_TYPES)}
        rows = self.load_curated_linkers()
        linkers: list[LinkerRecord] = []
        for row in rows:
            linker_class = row.get("linker_class", "")
            if requested and _norm_name(linker_class) not in requested:
                continue
            graph_length = _safe_int(row.get("graph_length"), 0)
            if graph_length and not (length_range[0] <= graph_length <= length_range[1]):
                continue
            linkers.append(
                LinkerRecord(
                    name=row.get("name", ""),
                    smiles=row.get("smiles", ""),
                    linker_class=linker_class,
                    source=row.get("source", "curated"),
                    graph_length=graph_length,
                    effective_length=_safe_float(row.get("effective_length"), graph_length),
                    rotatable_bonds=_safe_int(row.get("rotatable_bonds"), graph_length),
                    tpsa_contribution=_safe_float(row.get("tpsa_contribution"), 0.0),
                    hbd=_safe_int(row.get("hbd"), 0),
                    hba=_safe_int(row.get("hba"), 0),
                    synthetic_feasibility_proxy=_safe_float(row.get("synthetic_feasibility_proxy"), 0.6),
                    validity_status=self.validate_linker(row.get("smiles", "")),
                    provenance={"generation_method": row.get("generation_method", "curated_library")},
                )
            )
        if not linkers:
            linkers = self.generate_rule_based_linkers(linker_types or DEFAULT_LINKER_TYPES, max_linkers=max_linkers)
        # Generative layer: char-GRU linker model trained on PROTAC-DB linkers
        # (ADMET-scored + diversity-selected). Toggle: PROTACPILOT_GENERATIVE_LINKERS=0.
        import os as _os
        if _os.environ.get("PROTACPILOT_GENERATIVE_LINKERS", "1") != "0":
            try:
                from synglue_agent.tools.generative_linker import generate_generative_linkers
                gen = generate_generative_linkers(max_linkers=max(6, max_linkers // 2))
                existing = {l.smiles for l in linkers}
                linkers.extend([g for g in gen if g.smiles not in existing])
            except Exception as exc:  # noqa: BLE001
                logger.warning("generative linkers unavailable: %s", exc)
        # Link-INVENT-style ranking (reverse-sigmoid components x weights,
        # weighted product, batched ADMET penalty). Toggle: PROTACPILOT_LINKER_SCORING=0.
        import os as _os
        if _os.environ.get("PROTACPILOT_LINKER_SCORING", "1") != "0":
            try:
                from synglue_agent.tools.linker_scoring import rank_linkers
                linkers = rank_linkers(linkers)
            except Exception as exc:  # noqa: BLE001
                logger.warning("linker scoring unavailable: %s", exc)
                linkers.sort(key=lambda item: item.synthetic_feasibility_proxy, reverse=True)
        else:
            linkers.sort(key=lambda item: (item.synthetic_feasibility_proxy, -abs(item.graph_length - 7)), reverse=True)
        # RL-style optimization pass (Link-INVENT-like policy refinement).
        # PROTACPILOT_LINKER_OPTIMIZE=1 runs a bounded REINFORCE loop and adds
        # refined linkers; off by default for speed.
        if _os.environ.get("PROTACPILOT_LINKER_OPTIMIZE", "0") == "1":
            try:
                from synglue_agent.tools.linker_optimizer import optimize_linkers
                refined = optimize_linkers(rounds=2, batch=32, keep=max(6, max_linkers // 3))
                existing = {l.smiles for l in linkers}
                linkers.extend([r for r in refined if r.smiles not in existing])
            except Exception as exc:  # noqa: BLE001
                logger.warning("linker optimization unavailable: %s", exc)
        return linkers[:max_linkers]

    def generate_rule_based_linkers(self, linker_types: Sequence[str], max_linkers: int = 32) -> list[LinkerRecord]:
        patterns = {
            "PEG": ["[*:1]CCOCC[*:2]", "[*:1]CCOCCOCC[*:2]", "[*:1]CCOCCOCCOCC[*:2]"],
            "ALKYL": ["[*:1]CCC[*:2]", "[*:1]CCCC[*:2]", "[*:1]CCCCC[*:2]"],
            "PIPERAZINE": ["[*:1]CCN1CCN(CC1)CC[*:2]"],
            "TRIAZOLE": ["[*:1]CCn1nncc1CC[*:2]"],
            "AMIDE": ["[*:1]CCNC(=O)CC[*:2]"],
            "MIXED POLAR": ["[*:1]CCOCCNC(=O)CC[*:2]"],
        }
        linkers: list[LinkerRecord] = []
        for linker_type in linker_types:
            for idx, smiles in enumerate(patterns.get(_norm_name(linker_type), []), start=1):
                props = self.compute_basic_properties(smiles)
                linkers.append(
                    LinkerRecord(
                        name=f"rule_{linker_type}_{idx}",
                        smiles=smiles,
                        linker_class=linker_type,
                        source="rule_based",
                        graph_length=max(3, _remove_attachment_markers(smiles).count("C") + _remove_attachment_markers(smiles).count("O")),
                        effective_length=max(3, _remove_attachment_markers(smiles).count("C") + 0.7 * _remove_attachment_markers(smiles).count("O")),
                        rotatable_bonds=int(props.get("rotatable_bonds", 4)),
                        tpsa_contribution=float(props.get("tpsa", 0.0)),
                        hbd=int(props.get("hbd", 0)),
                        hba=int(props.get("hba", 0)),
                        synthetic_feasibility_proxy=0.62,
                        validity_status=self.validate_linker(smiles),
                        provenance={"generation_method": "rule_based_enumeration"},
                    )
                )
        return linkers[:max_linkers]

    def remove_duplicate_linkers(self, linkers: Sequence[LinkerRecord]) -> list[LinkerRecord]:
        seen = set()
        unique: list[LinkerRecord] = []
        for linker in linkers:
            key = self.canonicalize_smiles(linker.smiles)
            if key in seen:
                continue
            seen.add(key)
            unique.append(linker)
        return unique

    def expand_stereoisomers_controlled(
        self,
        candidates: Sequence[CandidateRecord],
        max_per_candidate: int = 4,
        max_total: int = 200,
    ) -> list[CandidateRecord]:
        """Enumerate undefined stereoisomers with hard caps.

        Candidates with explicit stereochemistry pass through unchanged. If a
        molecule has too many undefined centers, only the capped first variants
        are retained and the candidate is flagged for review.
        """
        expanded: list[CandidateRecord] = []
        for candidate in candidates:
            if len(expanded) >= max_total:
                break
            try:
                from synglue_agent.tools.stereochemistry_engine import enumerate_stereoisomers, get_stereochemistry_profile
                profile = get_stereochemistry_profile(candidate.full_protac_smiles)
                if not profile.has_undefined_stereo:
                    candidate.provenance["stereochemistry_status"] = "explicit_or_not_applicable"
                    expanded.append(candidate)
                    continue
                isomers = enumerate_stereoisomers(candidate.full_protac_smiles, max_isomers=max_per_candidate)
            except Exception as exc:  # noqa: BLE001
                candidate.warning_flags.append("stereochemistry_enumeration_unavailable")
                candidate.provenance["stereochemistry_error"] = str(exc)
                expanded.append(candidate)
                continue
            if not isomers:
                candidate.warning_flags.append("stereochemistry_unresolved")
                expanded.append(candidate)
                continue
            for idx, isomer in enumerate(isomers[:max_per_candidate], start=1):
                if len(expanded) >= max_total:
                    break
                child = candidate.model_copy(deep=True)
                child.candidate_id = f"{candidate.candidate_id}_st{idx}"
                child.parent_ids = list(dict.fromkeys(child.parent_ids + [candidate.candidate_id]))
                child.full_protac_smiles = isomer.get("smiles", candidate.full_protac_smiles)
                child.provenance["stereochemistry_status"] = "enumerated_controlled"
                child.provenance["stereochemistry_changes"] = isomer.get("changes", [])
                child.warning_flags.append("stereoisomer_requires_separate_scoring")
                expanded.append(child)
        return self.remove_duplicate_candidates(expanded)

    def state_of_the_art_tool_catalog(self) -> list[dict[str, str]]:
        from synglue_agent.tools.protac_autopilot_toolbox import ProtacXtendToolbox

        return ProtacXtendToolbox(self).catalog_as_rows()

    def construct_protac_candidates(
        self,
        warheads: Sequence[WarheadRecord],
        e3_ligands: Sequence[E3LigandRecord],
        linkers: Sequence[LinkerRecord],
        target_record: TargetRecord | None,
        candidate_count: int = 50,
        use_retrosynthesis_filtering: bool = False,
    ) -> tuple[list[ConstructionAttempt], list[CandidateRecord]]:
        strategies = [
            ("curated_template", "amide_or_ether_coupling"),
            ("reaction_smarts", "generic_single_bond_join"),
            ("known_linker_grafting", "known_linker_graft"),
            ("matched_linker_replacement", "component_matched_replacement"),
        ]
        attempts: list[ConstructionAttempt] = []
        candidates: list[CandidateRecord] = []
        seen_smiles = set()
        target = target_record.gene_symbol if target_record else "target"

        for warhead in warheads:
            for e3_ligand in e3_ligands:
                for linker in linkers:
                    if len(candidates) >= candidate_count:
                        return attempts, candidates
                    for strategy, reaction_class in strategies:
                        full_smiles, message = self.assemble_components(warhead.smiles, linker.smiles, e3_ligand.smiles)
                        success = bool(full_smiles)
                        candidate_id = None
                        if success:
                            canonical = self.canonicalize_smiles(full_smiles)
                            duplicate = canonical in seen_smiles
                            if not duplicate:
                                seen_smiles.add(canonical)
                                candidate_id = _stable_id("SGA", target, e3_ligand.e3_ligase, warhead.name, linker.name, canonical)
                                props = self.compute_basic_properties(canonical)
                                synth_score = _clamp(
                                    0.45 * linker.synthetic_feasibility_proxy
                                    + 0.20 * warhead.derivatization_score
                                    + 0.20 * e3_ligand.source_confidence
                                    + 0.15 * (0.8 if strategy in {"curated_template", "reaction_smarts"} else 0.6)
                                )
                                if use_retrosynthesis_filtering:
                                    synth_score *= 0.95
                                candidate = CandidateRecord(
                                    candidate_id=candidate_id,
                                    target=target,
                                    e3_ligase=e3_ligand.e3_ligase,
                                    warhead_name=warhead.name,
                                    warhead_smiles=warhead.smiles,
                                    warhead_source=warhead.source,
                                    e3_ligand_name=e3_ligand.name,
                                    e3_ligand_smiles=e3_ligand.smiles,
                                    linker_name=linker.name,
                                    linker_smiles=linker.smiles,
                                    linker_class=linker.linker_class,
                                    full_protac_smiles=canonical,
                                    assembly_strategy=strategy,
                                    reaction_class=reaction_class,
                                    validity_status=self.validate_smiles(canonical),
                                    synthetic_feasibility_score=round(synth_score, 3),
                                    provenance={
                                        "strategy": strategy,
                                        "reaction_class": reaction_class,
                                        "linker_source": linker.source,
                                        "rdkit_available": self.rdkit_available,
                                        "warhead_provenance": warhead.provenance,
                                    },
                                    warning_flags=(
                                        ([] if self.rdkit_available else ["rdkit_unavailable_unverified_smiles"])
                                        + (
                                            ["hypothetical_exit_vector_requires_chemist_review"]
                                            if warhead.provenance.get("exit_vector_warning")
                                            else []
                                        )
                                    ),
                                    mw=props.get("mw"),
                                    tpsa=props.get("tpsa"),
                                    logp=props.get("logp"),
                                    hbd=int(props.get("hbd", 0)),
                                    hba=int(props.get("hba", 0)),
                                    rotatable_bonds=int(props.get("rotatable_bonds", 0)),
                                )
                                candidates.append(candidate)
                            else:
                                message = "duplicate_canonical_smiles"
                                success = False
                        attempts.append(
                            ConstructionAttempt(
                                warhead_name=warhead.name,
                                e3_ligand_name=e3_ligand.name,
                                linker_name=linker.name,
                                strategy=strategy,
                                reaction_class=reaction_class,
                                success=success and candidate_id is not None,
                                failure_category=None if success and candidate_id is not None else message,
                                message=message,
                                candidate_id=candidate_id,
                            )
                        )
                        if success:
                            break
        return attempts, candidates

    def assemble_components(self, warhead_smiles: str, linker_smiles: str, e3_smiles: str) -> tuple[str | None, str]:
        if not all(_has_attachment(item) for item in [warhead_smiles, linker_smiles, e3_smiles]):
            return None, "missing_attachment_marker"
        if not self.rdkit_available:
            # Explicitly marked fallback. It keeps the workflow demonstrable but
            # downstream validators flag it as unverified until RDKit is installed.
            fallback = (
                _remove_attachment_markers(warhead_smiles)
                + _remove_attachment_markers(linker_smiles)
                + _remove_attachment_markers(e3_smiles)
            )
            return fallback, "assembled_with_string_fallback_rdkit_unavailable"
        try:
            left = self._join_on_dummy(warhead_smiles, linker_smiles, left_map=1, right_map=1)
            full = self._join_on_dummy(left, e3_smiles, left_map=2, right_map=1)
            return self.canonicalize_smiles(full), "assembled_with_rdkit_dummy_atom_join"
        except Exception as exc:  # pragma: no cover - depends on RDKit.
            return None, f"rdkit_assembly_failed:{exc}"

    def _find_dummy_idx(self, mol: Any, atom_map: int) -> int | None:  # pragma: no cover - depends on RDKit.
        for atom in mol.GetAtoms():
            if atom.GetAtomicNum() == 0 and atom.GetAtomMapNum() == atom_map:
                return atom.GetIdx()
        for atom in mol.GetAtoms():
            if atom.GetAtomicNum() == 0:
                return atom.GetIdx()
        return None

    def _join_on_dummy(self, smiles_a: str, smiles_b: str, left_map: int = 1, right_map: int = 1) -> str:  # pragma: no cover
        mol_a = Chem.MolFromSmiles(smiles_a)
        mol_b = Chem.MolFromSmiles(smiles_b)
        if mol_a is None or mol_b is None:
            raise ValueError("invalid component smiles")
        dummy_a = self._find_dummy_idx(mol_a, left_map)
        dummy_b = self._find_dummy_idx(mol_b, right_map)
        if dummy_a is None or dummy_b is None:
            raise ValueError("dummy atom not found")
        neigh_a = [atom.GetIdx() for atom in mol_a.GetAtomWithIdx(dummy_a).GetNeighbors()]
        neigh_b = [atom.GetIdx() for atom in mol_b.GetAtomWithIdx(dummy_b).GetNeighbors()]
        if not neigh_a or not neigh_b:
            raise ValueError("dummy atom has no attachment neighbor")
        combo = Chem.CombineMols(mol_a, mol_b)
        rw = Chem.RWMol(combo)
        offset = mol_a.GetNumAtoms()
        rw.AddBond(neigh_a[0], offset + neigh_b[0], Chem.BondType.SINGLE)
        for idx in sorted([dummy_a, offset + dummy_b], reverse=True):
            rw.RemoveAtom(idx)
        mol = rw.GetMol()
        Chem.SanitizeMol(mol)
        return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)

    # ------------------------------------------------------------------
    # Validation and descriptors
    # ------------------------------------------------------------------
    def validate_smiles(self, smiles: str) -> str:
        if not smiles:
            return "invalid_empty"
        if not self.rdkit_available:
            allowed = bool(re.match(r"^[A-Za-z0-9@+\-\[\]\(\)=#$\\/%.:*]+$", smiles))
            return "unverified_no_rdkit" if allowed else "invalid_syntax_no_rdkit"
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return "invalid_rdkit_parse"
        try:
            Chem.SanitizeMol(mol)
        except Exception:
            return "invalid_sanitization"
        return "valid"

    def validate_linker(self, smiles: str) -> str:
        if "[*:1]" not in smiles or "[*:2]" not in smiles:
            return "invalid_missing_two_attachment_points"
        return self.validate_smiles(smiles)

    def canonicalize_smiles(self, smiles: str) -> str:
        if not self.rdkit_available:
            return smiles
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return smiles
        return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)

    def compute_basic_properties(self, smiles: str) -> dict[str, Any]:
        descriptor = compute_core_descriptors(smiles)
        if descriptor.descriptor_status == "success":
            return {
                "mw": round(float(descriptor.mw), 2),
                "tpsa": round(float(descriptor.tpsa), 2),
                "logp": round(float(descriptor.logp), 2),
                "hbd": int(descriptor.hbd),
                "hba": int(descriptor.hba),
                "rotatable_bonds": int(descriptor.rotatable_bonds),
            }

        core = _remove_attachment_markers(smiles)
        atom_counts = {
            "C": len(re.findall(r"(?<![a-z])C(?![a-z])|c", core)),
            "N": len(re.findall(r"N|n", core)),
            "O": len(re.findall(r"O|o", core)),
            "S": len(re.findall(r"S|s", core)),
            "F": core.count("F"),
            "Cl": core.count("Cl"),
            "Br": core.count("Br"),
        }
        mw = (
            atom_counts["C"] * 12.01
            + atom_counts["N"] * 14.01
            + atom_counts["O"] * 16.00
            + atom_counts["S"] * 32.07
            + atom_counts["F"] * 19.00
            + atom_counts["Cl"] * 35.45
            + atom_counts["Br"] * 79.90
            + max(0, atom_counts["C"] * 1.4)
        )
        hba = atom_counts["N"] + atom_counts["O"] + atom_counts["S"]
        hbd = len(re.findall(r"NH|OH|N\]", core))
        rotors = max(0, core.count("C") + core.count("O") - core.count("1") * 2)
        tpsa = 12.0 * atom_counts["N"] + 17.0 * atom_counts["O"] + 25.0 * atom_counts["S"]
        logp = 0.035 * atom_counts["C"] + 0.3 * atom_counts["Cl"] + 0.5 * atom_counts["Br"] - 0.18 * hba
        return {
            "mw": round(mw, 2),
            "tpsa": round(tpsa, 2),
            "logp": round(logp, 2),
            "hbd": int(hbd),
            "hba": int(hba),
            "rotatable_bonds": int(rotors),
        }

    def validate_candidates(self, candidates: Sequence[CandidateRecord]) -> list[CandidateRecord]:
        valid: list[CandidateRecord] = []
        for candidate in candidates:
            status = self.validate_smiles(candidate.full_protac_smiles)
            candidate.validity_status = status
            if status.startswith("valid") or status == "unverified_no_rdkit":
                props = self.compute_basic_properties(candidate.full_protac_smiles)
                candidate.mw = props.get("mw")
                candidate.tpsa = props.get("tpsa")
                candidate.logp = props.get("logp")
                candidate.hbd = int(props.get("hbd", 0))
                candidate.hba = int(props.get("hba", 0))
                candidate.rotatable_bonds = int(props.get("rotatable_bonds", 0))
                analysis = analyze_protac_like_properties(candidate.full_protac_smiles)
                if analysis.valid:
                    warning_map = {
                        "protac_size_warning": analysis.protac_size_warning,
                        "high_tpsa_warning": analysis.high_tpsa_warning,
                        "high_logp_warning": analysis.high_logp_warning,
                        "excessive_rotatable_bonds_warning": analysis.excessive_rotatable_bonds_warning,
                    }
                    for warning, active in warning_map.items():
                        if active and warning not in candidate.warning_flags:
                            candidate.warning_flags.append(warning)
                if status == "unverified_no_rdkit":
                    candidate.warning_flags.append("install_rdkit_for_chemical_validation")
                valid.append(candidate)
        return self.remove_duplicate_candidates(valid)

    def remove_duplicate_candidates(self, candidates: Sequence[CandidateRecord]) -> list[CandidateRecord]:
        seen = set()
        unique: list[CandidateRecord] = []
        for candidate in candidates:
            key = candidate.full_protac_smiles
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    # ------------------------------------------------------------------
    # Prediction, ADME/Tox, novelty, and domain tools
    # ------------------------------------------------------------------
    def predict_degradation(
        self,
        candidates: Sequence[CandidateRecord],
        target_record: TargetRecord | None,
        cell_line: str | None = None,
        assay_context: str | None = None,
    ) -> list[DegradationPrediction]:
        """Degradation prediction through the TRAINED Chemprop ensemble.

        v0.3 fix: the agent previously used a pure MW/TPSA heuristic formula.
        Now calls predict_degradation_endpoint (single-target conformal ensemble
        for DC50/uncertainty + multi-target head for Dmax + AD + context gate);
        the heuristic remains ONLY as a labelled fallback when the model path
        fails (model_version starts with 'heuristic_proxy').
        """
        from synglue_agent.tools.degradation_endpoint import predict_degradation_batch
        smiles = [c.full_protac_smiles for c in candidates]
        ids = [c.candidate_id for c in candidates]
        try:
            rows = predict_degradation_batch(
                smiles, candidate_ids=ids,
                cell_line=cell_line or "default",
                target=(target_record.gene_symbol if target_record else ""),
                e3_ligase=(candidates[0].e3_ligase or "CRBN") if candidates else "CRBN",
            )
        except Exception as exc:  # noqa: BLE001
            rows = []
            logger.warning("degradation batch failed (%s); using heuristic fallback", exc)
        conf_map = {"high_confidence": 0.85, "medium_confidence": 0.55, "low_confidence": 0.25}
        prob_map = {"active": 0.85, "inactive": 0.20, "unknown": 0.40}
        predictions = []
        for ep in rows:
            warnings = []
            if ep["ad_status"] == "out_of_domain":
                warnings.append("candidate outside model applicability domain")
            if ep["context_gated"]:
                warnings.append(f"context gate: {ep['context_note']}")
            if ep.get("model", "").startswith("tack"):
                model_version = "tack-style-v1 (DC50/Dmax primary) + chemprop cross-check"
            else:
                model_version = "chemprop-ensemble-v0.3 (conformal, single+multi target)"
            predictions.append(
                DegradationPrediction(
                    candidate_id=ep["candidate_id"],
                    predicted_dc50_nM=ep["dc50_nM"],
                    predicted_logdc50=ep["log_dc50"],
                    predicted_dmax_percent=ep["dmax_pct"],
                    degradation_probability=prob_map.get(ep["activity_class"], 0.4),
                    model_confidence=conf_map.get(ep["verdict"], 0.25),
                    applicability_domain_score=ep["nn_tanimoto"] or 0.0,
                    model_version=model_version,
                    tack_dc50_nM=ep.get("tack_dc50_nM"),
                    tack_dmax_pct=ep.get("tack_dmax_pct"),
                    tack_active=ep.get("tack_active"),
                    tack_active_prob=ep.get("tack_active_prob"),
                    chemprop_dc50_nM=ep.get("chemprop_dc50_nM"),
                    chemprop_dmax_pct=ep.get("chemprop_dmax_pct"),
                    warning=("; ".join(warnings) if warnings else None),
                )
            )
        if not predictions and candidates:
            # full batch failure -> labelled heuristic fallback per candidate
            err_note = "chemprop unavailable; heuristic proxy"
            predictions = [
                self._predict_degradation_heuristic(c, target_record, cell_line)
                .model_copy(update={"warning": err_note})
                for c in candidates
            ]
        # TACK-model fallback vote: only fills tack_* fields when the endpoint
        # did not already provide them (does not overwrite the primary backend).
        if any(p.tack_dc50_nM is None for p in predictions):
            try:
                from synglue_agent.tools.tack_degradation import predict_tack_batch
                tack_entries = [
                    {"smiles": c.full_protac_smiles, "e3": c.e3_ligase or "CRBN",
                     "cell": cell_line or "default",
                     "poi": (target_record.gene_symbol if target_record else "")}
                    for c in candidates
                ]
                tack_rows = predict_tack_batch(tack_entries)
                for pred, tr in zip(predictions, tack_rows):
                    if not tr or pred.tack_dc50_nM is not None:
                        continue
                    pred.tack_dc50_nM = tr["dc50_nM"]
                    pred.tack_dmax_pct = tr["dmax_pct"]
                    pred.tack_active = tr["active"]
                    pred.tack_active_prob = tr["active_prob"]
                    compatibility_warning = (tr.get("provenance") or {}).get("compatibility_warning")
                    if compatibility_warning:
                        pred.warning = "; ".join(filter(None, [pred.warning, compatibility_warning]))
            except Exception as exc:  # noqa: BLE001
                logger.warning("TACK cross-check unavailable: %s", exc)
        return predictions

    def _predict_degradation_heuristic(
        self,
        candidate: CandidateRecord,
        target_record: TargetRecord | None,
        cell_line: str | None = None,
    ) -> DegradationPrediction:
        """Labelled heuristic fallback (only used when the trained model path fails)."""
        tractability = target_record.tractability_score if target_record else 0.35
        props = self.compute_basic_properties(candidate.full_protac_smiles)
        mw = float(props.get("mw", candidate.mw or 900.0))
        tpsa = float(props.get("tpsa", candidate.tpsa or 160.0))
        rotors = float(props.get("rotatable_bonds", candidate.rotatable_bonds or 12))
        linker_bonus = {"PEG": 0.05, "alkyl": -0.02, "piperazine": 0.04, "triazole": 0.02}.get(candidate.linker_class, 0.0)
        e3_bonus = {"CRBN": 0.08, "VHL": 0.04, "IAP": 0.02, "MDM2": 0.0}.get(candidate.e3_ligase.upper(), 0.0)
        size_penalty = _clamp((mw - 850.0) / 600.0)
        tpsa_penalty = _clamp((tpsa - 170.0) / 180.0)
        flexibility_penalty = _clamp((rotors - 18.0) / 18.0)
        activity_signal = _clamp(0.40 + 0.35 * tractability + linker_bonus + e3_bonus - 0.12 * size_penalty - 0.12 * tpsa_penalty)
        logdc50 = 3.0 - 1.8 * activity_signal + 0.25 * flexibility_penalty
        dc50 = round(10 ** logdc50, 2)
        dmax = round(_clamp(35.0 + 55.0 * activity_signal - 12.0 * tpsa_penalty - 8.0 * size_penalty, 5.0, 98.0), 1)
        domain = self.compute_applicability_domain_score(candidate)
        confidence = _clamp(0.45 + 0.30 * domain + 0.20 * tractability + (0.05 if self.rdkit_available else -0.08))
        return DegradationPrediction(
            candidate_id=candidate.candidate_id,
            predicted_dc50_nM=dc50,
            predicted_logdc50=logdc50,
            predicted_dmax_percent=dmax,
            degradation_probability=_clamp(0.35 + 0.35 * domain + 0.30 * tractability),
            model_confidence=confidence,
            applicability_domain_score=domain,
            model_version="heuristic_proxy-v0.1 (fallback)",
            warning="Exploratory prediction: candidate outside demo model applicability domain." if domain < 0.35 else None,
        )

    def predict_admet(self, candidates: Sequence[CandidateRecord]) -> list[ADMETPrediction]:
        from synglue_agent.tools.admet_predictors import (
            calculate_protac_admet_descriptors,
            predict_admet,
        )

        rows: list[ADMETPrediction] = []
        for candidate in candidates:
            admet = predict_admet(candidate.full_protac_smiles, backend="auto")
            descriptor_result = calculate_protac_admet_descriptors(candidate.full_protac_smiles)
            descriptor_map = descriptor_result.get("descriptors", {}) if descriptor_result.get("success") else {}
            mw = float(admet.get("MW", descriptor_map.get("MW", 0.0)) or 0.0)
            tpsa = float(admet.get("TPSA", descriptor_map.get("TPSA", 0.0)) or 0.0)
            logp = float(admet.get("LogP", descriptor_map.get("LogP", 0.0)) or 0.0)
            rotors = int(admet.get("rotatable_bonds", descriptor_map.get("rotatable_bonds", 0)) or 0)
            hbd = int(descriptor_map.get("HBD", 0) or 0)
            hba = int(descriptor_map.get("HBA", 0) or 0)
            sol = admet.get("solubility")
            if isinstance(sol, (int, float)):
                sol_risk = "high" if sol <= -6.0 else "medium" if sol <= -4.5 else "low"
            else:
                sol_risk = admet.get("solubility_risk", "unknown")
            risk_weights = {"low": 0.15, "medium": 0.50, "high": 0.85, "unknown": 0.6}
            hERG_risk = admet.get("hERG_risk", "unknown")
            AMES_risk = admet.get("AMES_risk", "unknown")
            DILI_risk = admet.get("DILI_risk", "unknown")
            CYP_risk = admet.get("CYP_risk", "unknown")
            Pgp_risk = admet.get("Pgp_risk", "unknown")
            penalty = _clamp(
                0.22 * risk_weights.get(hERG_risk, 0.6)
                + 0.18 * risk_weights.get(DILI_risk, 0.6)
                + 0.12 * risk_weights.get(AMES_risk, 0.6)
                + 0.18 * risk_weights.get(sol_risk, 0.6)
                + 0.16 * risk_weights.get(Pgp_risk, 0.6)
                + 0.14 * risk_weights.get(CYP_risk, 0.6)
            )
            backend = admet.get("backend_used", "unknown")
            status = admet.get("status", "unknown")
            rows.append(
                ADMETPrediction(
                    candidate_id=candidate.candidate_id,
                    mw=round(mw, 2),
                    tpsa=round(tpsa, 2),
                    logp=round(logp, 2),
                    hbd=hbd,
                    hba=hba,
                    rotatable_bonds=rotors,
                    qed=descriptor_map.get("QED"),
                    sa_score_proxy=round(_clamp(1.0 - candidate.synthetic_feasibility_score), 3),
                    hERG_risk=hERG_risk,
                    AMES_risk=AMES_risk,
                    DILI_risk=DILI_risk,
                    CYP_risk=CYP_risk,
                    Pgp_risk=Pgp_risk,
                    solubility_risk=sol_risk,
                    overall_admet_penalty=round(penalty, 3),
                    warning=f"backend={backend}; status={status}; limitations={admet.get('limitations')}",
                )
            )
        return rows

    def _risk_label(self, score: float) -> str:
        if score >= 0.67:
            return "high"
        if score >= 0.34:
            return "medium"
        return "low"

    def cheap_filter_candidates(
        self,
        candidates: Sequence[CandidateRecord],
        admet_predictions: Sequence[ADMETPrediction] | None = None,
        novelty_results: Sequence[NoveltyResult] | None = None,
        domain_results: Sequence[ApplicabilityDomainResult] | None = None,
        e3_context_results: Sequence[E3ContextPrediction] | None = None,
        max_candidates: int = 100,
    ) -> tuple[list[CandidateRecord], dict[str, Any]]:
        """Apply cheap first-pass filters before expensive modeling.

        Hard rejects are intentionally simple and transparent. Borderline
        candidates can survive but carry warning flags so diversity is not
        destroyed too early.
        """
        admet_by_id = {item.candidate_id: item for item in (admet_predictions or [])}
        novelty_by_id = {item.candidate_id: item for item in (novelty_results or [])}
        domain_by_id = {item.candidate_id: item for item in (domain_results or [])}
        e3_by_id = {item.candidate_id: item for item in (e3_context_results or [])}
        scored: list[tuple[float, CandidateRecord]] = []
        reject_reasons: dict[str, int] = defaultdict(int)
        for candidate in candidates:
            status = candidate.validity_status
            if not status or status == "unchecked":
                status = self.validate_smiles(candidate.full_protac_smiles)
                candidate.validity_status = status
            props = self.compute_basic_properties(candidate.full_protac_smiles)
            mw = float(candidate.mw if candidate.mw is not None else props.get("mw", 0.0) or 0.0)
            tpsa = float(candidate.tpsa if candidate.tpsa is not None else props.get("tpsa", 0.0) or 0.0)
            rotors = float(candidate.rotatable_bonds if candidate.rotatable_bonds is not None else props.get("rotatable_bonds", 0.0) or 0.0)
            admet = admet_by_id.get(candidate.candidate_id, ADMETPrediction(candidate_id=candidate.candidate_id))
            novelty = novelty_by_id.get(candidate.candidate_id, NoveltyResult(candidate_id=candidate.candidate_id, novelty_score=0.5))
            domain = domain_by_id.get(candidate.candidate_id, ApplicabilityDomainResult(candidate_id=candidate.candidate_id, similarity_to_training_set=0.5))
            e3_context = e3_by_id.get(candidate.candidate_id, E3ContextPrediction(candidate_id=candidate.candidate_id, total_context_score=0.6))
            reasons: list[str] = []
            if status not in {"valid", "unverified_no_rdkit"}:
                reasons.append("invalid_smiles")
            if mw > 1800:
                reasons.append("mw_above_1800")
            if tpsa > 360:
                reasons.append("tpsa_above_360")
            if rotors > 45:
                reasons.append("rotors_above_45")
            if candidate.synthetic_feasibility_score < 0.18:
                reasons.append("very_low_synthetic_feasibility")
            if admet.hERG_risk == "high" and admet.DILI_risk == "high":
                reasons.append("dual_high_toxicity_risk")
            if novelty.duplicate_flag:
                candidate.warning_flags.append("near_duplicate_removed_by_cheap_filter")
                reasons.append("duplicate_known_protac")
            if reasons:
                for reason in reasons:
                    reject_reasons[reason] += 1
                continue
            property_score = _clamp(
                0.30 * (1.0 - _clamp((mw - 900.0) / 900.0))
                + 0.25 * (1.0 - _clamp((tpsa - 160.0) / 220.0))
                + 0.20 * (1.0 - _clamp((rotors - 16.0) / 30.0))
                + 0.15 * candidate.synthetic_feasibility_score
                + 0.10 * _clamp(e3_context.total_context_score or 0.6)
            )
            admet_score = _clamp(1.0 - admet.overall_admet_penalty)
            novelty_score = _clamp(novelty.novelty_score or 0.5)
            domain_score = _clamp(domain.similarity_to_training_set or 0.5)
            total = _clamp(0.38 * property_score + 0.25 * admet_score + 0.17 * novelty_score + 0.12 * domain_score + 0.08 * _clamp(e3_context.total_context_score or 0.6))
            candidate.provenance["cheap_filter_score"] = round(total, 3)
            scored.append((total, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        kept = [candidate for _, candidate in scored[:max_candidates]]
        summary = {
            "policy_version": "cheap-filter-v0.1",
            "input_candidates": len(candidates),
            "kept_candidates": len(kept),
            "max_candidates": max_candidates,
            "rejected_candidates": len(candidates) - len(scored),
            "reject_reasons": dict(reject_reasons),
            "score_fields": ["validity", "MW", "TPSA", "rotatable_bonds", "synthetic_feasibility", "ADMET", "novelty", "applicability_domain", "E3_context"],
        }
        return kept, summary

    def filter_prediction_records(self, records: Sequence[Any], candidate_ids: set[str]) -> list[Any]:
        return [record for record in records if getattr(record, "candidate_id", None) in candidate_ids]

    def protacdb_evidence_prior(self, candidate: CandidateRecord) -> dict[str, Any]:
        """Return a capped PROTAC-DB evidence prior for one candidate.

        PROTAC-DB is treated as incomplete literature evidence. Exact chemical
        matches are strong priors; target/E3 neighborhood records are weaker
        priors. Missing evidence is neutral and must not reject novel designs.
        """
        try:
            from synglue_agent.tools.protacdb_client import load_normalized_protacdb, search_protacdb_evidence
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "source_scope": "unavailable", "score": 0.5, "warning": f"PROTAC-DB prior unavailable: {exc}"}

        candidate_key = candidate.provenance.get("inchikey") or chem_identity(candidate.full_protac_smiles)
        exact_match = None
        # O(1) exact-match lookup via an InChIKey index built once over the
        # stable cached table (previous linear scan + per-row InChIKey cost
        # made ranking ~2-5 s per candidate; measured: 96 s for 20 candidates
        # before the fix).
        exact_match = _protacdb_exact_index().get(candidate_key)

        if exact_match:
            records = [exact_match]
            source_scope = "exact_compound_match"
            influence = 1.0
        else:
            records = search_protacdb_evidence(
                target=candidate.target or None,
                e3_ligase=candidate.e3_ligase or None,
                min_evidence_families=1,
                limit=75,
            )
            source_scope = "target_e3_neighborhood" if records else "no_matching_protacdb_records"
            influence = 0.45 if records else 0.0

        family_counts: dict[str, int] = defaultdict(int)
        degradation_scores: list[float] = []
        ternary_scores: list[float] = []
        permeability_scores: list[float] = []
        for record in records:
            evidence = record.get("evidence", {})
            for family in evidence:
                family_counts[family] += 1
            degradation = evidence.get("degradation_capacity", {})
            if degradation:
                degradation_scores.extend([
                    _best_nanomolar_score(degradation.get("DC50 (nM)")),
                    _clamp((_safe_float(degradation.get("Dmax (%)"), 50.0)) / 100.0),
                    _clamp((_safe_float(degradation.get("Percent degradation (%)"), 50.0)) / 100.0),
                ])
            ternary = evidence.get("ternary_complex_affinity", {})
            if ternary:
                ternary_scores.extend([
                    _best_nanomolar_score(ternary.get("Kd (nM, Ternary complex)")),
                    _best_nanomolar_score(ternary.get("IC50 (nM, Ternary complex)")),
                    _best_nanomolar_score(ternary.get("EC50 (nM, Ternary complex)")),
                ])
            permeability = evidence.get("cell_permeability", {})
            if permeability:
                pampa = max(_numeric_tokens(permeability.get("PAMPA Papp (nm/s, Permeability)")) or [0.0])
                caco_a2b = max(_numeric_tokens(permeability.get("Caco-2 A2B Papp (nm/s, Permeability)")) or [0.0])
                permeability_scores.append(_clamp(max(pampa / 200.0, caco_a2b / 100.0)))

        degradation_prior = sum(degradation_scores) / len(degradation_scores) if degradation_scores else 0.5
        ternary_prior = sum(ternary_scores) / len(ternary_scores) if ternary_scores else 0.5
        permeability_prior = sum(permeability_scores) / len(permeability_scores) if permeability_scores else 0.5
        diversity_prior = _clamp(len(family_counts) / 8.0)
        score = _clamp(
            influence
            * (
                0.34 * degradation_prior
                + 0.30 * ternary_prior
                + 0.18 * permeability_prior
                + 0.18 * diversity_prior
            )
            + (1.0 - influence) * 0.5
        )
        return {
            "available": bool(records),
            "source": "PROTAC-DB 3.0",
            "source_scope": source_scope,
            "score": round(score, 3),
            "influence": influence,
            "record_count": len(records),
            "evidence_family_counts": dict(family_counts),
            "degradation_prior": round(degradation_prior, 3),
            "ternary_prior": round(ternary_prior, 3),
            "permeability_prior": round(permeability_prior, 3),
            "diversity_prior": round(diversity_prior, 3),
            "limitations": "PROTAC-DB is incomplete; absence from PROTAC-DB is neutral, not negative evidence.",
        }

    def _pubchem_patents(self, smiles: str) -> tuple[int, list[str]]:
        """Live patent cross-reference: SMILES -> PubChem CID -> PUG-View Patents.

        Returns (patent_count, patent_ids). Never raises; any failure -> (0, []).
        """
        import hashlib
        import json as _json
        import urllib.error
        import urllib.parse
        import urllib.request

        cache_key = "patents_" + hashlib.md5(smiles.encode()).hexdigest()
        if hasattr(self, "_patent_cache") and cache_key in self._patent_cache:
            return self._patent_cache[cache_key]
        if not hasattr(self, "_patent_cache"):
            self._patent_cache = {}

        try:
            cid_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{urllib.parse.quote(smiles)}/cids/JSON"
            with urllib.request.urlopen(urllib.request.Request(cid_url, headers={"User-Agent": "ProtacPilot/1.0"}), timeout=20) as resp:
                cid_data = _json.loads(resp.read().decode())
            cids = cid_data.get("IdentifierList", {}).get("CID", [])
            if not cids:
                self._patent_cache[cache_key] = (0, [])
                return 0, []
            cid = cids[0]
            view_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON?heading=Patents"
            with urllib.request.urlopen(urllib.request.Request(view_url, headers={"User-Agent": "ProtacPilot/1.0"}), timeout=30) as resp:
                view = _json.loads(resp.read().decode())
            patents: list[str] = []

            def walk(items):
                for it in items:
                    if "StringValue" in it and len(str(it["StringValue"])) < 40:
                        patents.append(str(it["StringValue"]))
                    for sub in it.get("Section", []):
                        walk(sub.get("Information", []))
                    v = it.get("Value")
                    if v and "StringWithMarkup" in v:
                        for m in v["StringWithMarkup"]:
                            st = m.get("String", "")
                            if st and len(st) < 40:
                                patents.append(st)

            for sec in view.get("Record", {}).get("Section", []):
                if sec.get("TOCHeading") == "Patents":
                    walk(sec.get("Information", []))
            patents = list(dict.fromkeys(patents))
            self._patent_cache[cache_key] = (len(patents), patents)
            return len(patents), patents
        except Exception:
            self._patent_cache[cache_key] = (0, [])
            return 0, []

    def check_novelty(self, candidates: Sequence[CandidateRecord]) -> list[NoveltyResult]:
        known = self.load_known_protacs()
        known_smiles = [(row.get("name", row.get("protac_id", "known")), row.get("smiles", "")) for row in known if row.get("smiles")]
        results: list[NoveltyResult] = []
        for candidate in candidates:
            nearest_name = None
            nearest_sim = 0.0
            for name, smiles in known_smiles:
                sim = self.calculate_similarity(candidate.full_protac_smiles, smiles)
                if sim > nearest_sim:
                    nearest_name = name
                    nearest_sim = sim
            duplicate = nearest_sim >= 0.98
            novelty = _clamp(1.0 - nearest_sim)
            component_novelty = _clamp(0.5 * novelty + 0.5 * (0.0 if "known" in candidate.warhead_source.lower() else 0.4))
            results.append(
                NoveltyResult(
                    candidate_id=candidate.candidate_id,
                    nearest_known_protac=nearest_name,
                    max_tanimoto_similarity=round(nearest_sim, 3),
                    duplicate_flag=duplicate,
                    novelty_score=round(novelty, 3),
                    scaffold_novelty=round(_clamp(novelty * 0.9 + 0.05), 3),
                    component_novelty=round(component_novelty, 3),
                    linker_novelty=0.35 if candidate.linker_name.lower().startswith("known") else 0.65,
                )
            )
        # Live patent cross-reference (PubChem PUG-View) — best-effort, bounded.
        for result in results[:10]:
            candidate = next((c for c in candidates if c.candidate_id == result.candidate_id), None)
            if candidate is None:
                continue
            n_pat, pat_ids = self._pubchem_patents(candidate.full_protac_smiles)
            result.patent_count = n_pat
            result.patent_ids = pat_ids[:8]
            result.patent_source = "pubchem_patents" if n_pat else "unavailable"
        return results

    def calculate_similarity(self, smiles_a: str, smiles_b: str) -> float:
        if self.rdkit_available:
            mol_a = Chem.MolFromSmiles(smiles_a)
            mol_b = Chem.MolFromSmiles(smiles_b)
            if mol_a is None or mol_b is None:
                return self._string_similarity(smiles_a, smiles_b)
            fp_a = AllChem.GetMorganFingerprintAsBitVect(mol_a, 2, nBits=2048)
            fp_b = AllChem.GetMorganFingerprintAsBitVect(mol_b, 2, nBits=2048)
            from rdkit.DataStructs import TanimotoSimilarity

            return float(TanimotoSimilarity(fp_a, fp_b))
        return self._string_similarity(smiles_a, smiles_b)

    def _string_similarity(self, value_a: str, value_b: str) -> float:
        def grams(value: str) -> set:
            clean = re.sub(r"\s+", "", value)
            return {clean[idx : idx + 3] for idx in range(max(1, len(clean) - 2))}

        grams_a = grams(value_a)
        grams_b = grams(value_b)
        if not grams_a or not grams_b:
            return 0.0
        return len(grams_a & grams_b) / len(grams_a | grams_b)

    def compute_applicability_domain(self, candidates: Sequence[CandidateRecord]) -> list[ApplicabilityDomainResult]:
        return [
            ApplicabilityDomainResult(
                candidate_id=candidate.candidate_id,
                similarity_to_training_set=round(self.compute_applicability_domain_score(candidate), 3),
                embedding_distance=round(1.0 - self.compute_applicability_domain_score(candidate), 3),
                domain_status=self.assign_domain_status(self.compute_applicability_domain_score(candidate)),
                warning=None
                if self.compute_applicability_domain_score(candidate) >= 0.35
                else "Outside local demo applicability domain; treat predictions as exploratory.",
            )
            for candidate in candidates
        ]

    def compute_applicability_domain_score(self, candidate: CandidateRecord) -> float:
        mw = candidate.mw if candidate.mw is not None else self.compute_basic_properties(candidate.full_protac_smiles).get("mw", 900.0)
        tpsa = candidate.tpsa if candidate.tpsa is not None else self.compute_basic_properties(candidate.full_protac_smiles).get("tpsa", 160.0)
        rotors = candidate.rotatable_bonds if candidate.rotatable_bonds is not None else 14
        mw_score = 1.0 - _clamp(abs(float(mw) - 900.0) / 700.0)
        tpsa_score = 1.0 - _clamp(abs(float(tpsa) - 160.0) / 220.0)
        rotor_score = 1.0 - _clamp(abs(float(rotors) - 14.0) / 20.0)
        return _clamp(0.42 * mw_score + 0.32 * tpsa_score + 0.26 * rotor_score)

    def assign_domain_status(self, score: float) -> str:
        if score >= 0.65:
            return "inside"
        if score >= 0.35:
            return "edge"
        return "outside"

    def score_e3_context(
        self,
        candidates: Sequence[CandidateRecord],
        target_record: TargetRecord | None,
        cell_line: str | None = None,
        expression_overrides: dict[str, float] | None = None,
    ) -> list[E3ContextPrediction]:
        """Score explicit cell-type/E3 compatibility for each candidate.

        ``expression_overrides`` accepts normalized 0-1 values keyed by E3
        ligase, e.g. {"CRBN": 0.9, "VHL": 0.2}. This lets assay-specific
        proteomics override curated defaults without changing the source table.
        """
        from synglue_agent.tools.e3_context_engine import score_e3

        context = cell_line or "default"
        localization = "nuclear"
        if target_record and target_record.biology_context:
            localization = str(target_record.biology_context.get("localization", localization) or localization)
        target = target_record.gene_symbol if target_record else ""
        overrides = {k.upper(): _clamp(v) for k, v in (expression_overrides or {}).items()}
        rows: list[E3ContextPrediction] = []
        for candidate in candidates:
            result = score_e3(candidate.e3_ligase or "CRBN", context, localization, target)
            expr = overrides.get((candidate.e3_ligase or "").upper(), result.expression_score)
            total = result.total_context_score
            if overrides:
                total = _clamp(total + 0.30 * (expr - result.expression_score))
            rows.append(
                E3ContextPrediction(
                    candidate_id=candidate.candidate_id,
                    e3_ligase=candidate.e3_ligase,
                    cell_line=context,
                    target_localization=localization,
                    expression_score=round(expr, 3),
                    colocalization_score=result.colocalization_score,
                    ligand_availability_score=result.ligand_availability_score,
                    structural_support_score=result.structural_support_score,
                    resistance_risk=result.resistance_risk,
                    total_context_score=round(total, 3),
                    confidence=result.confidence,
                    contraindications=result.contraindications,
                    evidence_refs=result.evidence_refs + (["expression_override:user"] if overrides else []),
                    explanation=result.explanation,
                )
            )
        return rows

    def _load_calibration_rows(self, filename: str) -> dict[str, dict[str, str]]:
        path = DATA_DIR / filename
        if not path.exists():
            return {}
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                return {
                    row.get("candidate_id", "").strip(): row
                    for row in csv.DictReader(handle)
                    if row.get("candidate_id", "").strip()
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Calibration table %s could not be loaded: %s", path, exc)
            return {}

    def predict_cooperativity(
        self,
        candidates: Sequence[CandidateRecord],
        ternary_results: Sequence[TernaryFeasibilityResult] | None = None,
    ) -> list[CooperativityPrediction]:
        """Predict ternary cooperativity alpha with an interpretable proxy.

        The proxy rewards feasible ternary geometry, moderate linker strain, and
        plausible lysine/interface presentation. It is intentionally labelled as
        a proxy because true alpha requires biophysical measurement or calibrated
        structure/ML data.
        """
        ternary_by_id = {item.candidate_id: item for item in (ternary_results or [])}
        measured_by_id = self._load_calibration_rows("cooperativity_calibration.csv")
        rows: list[CooperativityPrediction] = []
        for candidate in candidates:
            protacdb_prior = self.protacdb_evidence_prior(candidate)
            measured = measured_by_id.get(candidate.candidate_id)
            if measured:
                alpha = max(0.01, _safe_float(measured.get("predicted_alpha") or measured.get("measured_alpha"), 1.0))
                log_alpha = math.log10(alpha)
                score = _clamp((log_alpha + 1.0) / 3.0)
                rows.append(
                    CooperativityPrediction(
                        candidate_id=candidate.candidate_id,
                        predicted_alpha=round(alpha, 3),
                        log_alpha=round(log_alpha, 3),
                        cooperativity_score=round(score, 3),
                        interface_contact_score=_safe_float(measured.get("interface_contact_score"), score),
                        linker_strain_score=_safe_float(measured.get("linker_strain_score"), score),
                        lysine_geometry_score=_safe_float(measured.get("lysine_geometry_score"), score),
                        ternary_geometry_score=_safe_float(measured.get("ternary_geometry_score"), score),
                        confidence=round(_clamp(_safe_float(measured.get("confidence"), 0.9)), 3),
                        model_version=measured.get("source", "measured-alpha-calibration-v0.1") or "measured-alpha-calibration-v0.1",
                        warning=None,
                    )
                )
                continue
            ternary = ternary_by_id.get(
                candidate.candidate_id,
                TernaryFeasibilityResult(candidate_id=candidate.candidate_id, ternary_plausibility_score=0.45),
            )
            rotors = float(candidate.rotatable_bonds if candidate.rotatable_bonds is not None else 14.0)
            linker_len = float(len(candidate.linker_smiles or "")) / 6.0
            flexibility_fit = 1.0 - abs(rotors - 14.0) / 22.0
            length_fit = 1.0 - abs(linker_len - 7.0) / 12.0
            linker_strain_score = _clamp(0.55 * flexibility_fit + 0.45 * length_fit)
            interface_contact_score = _clamp(
                0.45 * ternary.ternary_plausibility_score
                + 0.25 * ternary.fast_geometry_feasibility_score
                + 0.20 * candidate.synthetic_feasibility_score
                + 0.10 * (1.0 if candidate.e3_ligase.upper() in {"CRBN", "VHL"} else 0.55)
            )
            lysine_geometry_score = _clamp(
                0.55 * ternary.linker_reachability_score
                + 0.25 * ternary.ternary_plausibility_score
                + 0.20 * (1.0 - abs(rotors - 16.0) / 26.0)
            )
            structural_evidence = ternary.real_structural_score is not None
            if ternary.interface_quality_score is not None:
                interface_contact_score = _clamp(float(ternary.interface_quality_score))
            if ternary.linker_strain_score is not None:
                linker_strain_score = _clamp(float(ternary.linker_strain_score))
            if ternary.lysine_geometry_score is not None:
                lysine_geometry_score = _clamp(float(ternary.lysine_geometry_score))
            coop_score = _clamp(
                0.38 * interface_contact_score
                + 0.27 * linker_strain_score
                + 0.22 * lysine_geometry_score
                + 0.13 * ternary.ternary_plausibility_score
            )
            if protacdb_prior.get("available") and protacdb_prior.get("ternary_prior", 0.5) != 0.5:
                prior_weight = 0.18 if protacdb_prior["source_scope"] == "exact_compound_match" else 0.08
                coop_score = _clamp((1.0 - prior_weight) * coop_score + prior_weight * protacdb_prior["ternary_prior"])
            log_alpha = -1.0 + 3.0 * coop_score
            alpha = 10 ** log_alpha
            warning = None
            if ternary.docking_status.startswith("not_run"):
                warning = "Cooperativity is proxy-only until ternary docking/P4ward evidence is available."
            elif structural_evidence:
                warning = "Cooperativity uses experimental pose-backed structural scoring; still not measured alpha."
            if protacdb_prior.get("available"):
                warning = "; ".join(
                    filter(
                        None,
                        [
                            warning,
                            f"PROTAC-DB {protacdb_prior['source_scope']} used as capped ternary-affinity prior; database is incomplete.",
                        ],
                    )
                )
            model_version = "cooperativity-proxy-v0.1"
            if structural_evidence:
                model_version += "+pose-structural-score"
            if protacdb_prior.get("available"):
                model_version += "+protacdb-prior"
            confidence_base = 0.35 + 0.45 * ternary.ternary_plausibility_score + 0.20 * linker_strain_score
            if structural_evidence:
                confidence_base = max(
                    confidence_base,
                    0.42
                    + 0.30 * float(ternary.structural_confidence or 0.0)
                    + 0.18 * interface_contact_score
                    + 0.10 * lysine_geometry_score,
                )
            rows.append(
                CooperativityPrediction(
                    candidate_id=candidate.candidate_id,
                    predicted_alpha=round(alpha, 3),
                    log_alpha=round(log_alpha, 3),
                    cooperativity_score=round(coop_score, 3),
                    interface_contact_score=round(interface_contact_score, 3),
                    linker_strain_score=round(linker_strain_score, 3),
                    lysine_geometry_score=round(lysine_geometry_score, 3),
                    ternary_geometry_score=round(ternary.ternary_plausibility_score, 3),
                    confidence=round(_clamp(confidence_base), 3),
                    model_version=model_version,
                    warning=warning,
                )
            )
        return rows

    def predict_hook_effect(
        self,
        candidates: Sequence[CandidateRecord],
        degradation_predictions: Sequence[DegradationPrediction],
        cooperativity_predictions: Sequence[CooperativityPrediction],
        e3_context_predictions: Sequence[E3ContextPrediction] | None = None,
    ) -> list[HookEffectPrediction]:
        """Model concentration-dependent ternary occupancy and hook risk."""
        deg_by_id = {item.candidate_id: item for item in degradation_predictions}
        coop_by_id = {item.candidate_id: item for item in cooperativity_predictions}
        e3_by_id = {item.candidate_id: item for item in (e3_context_predictions or [])}
        measured_by_id = self._load_calibration_rows("hook_effect_calibration.csv")
        concentrations = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0, 10000.0]
        rows: list[HookEffectPrediction] = []
        for candidate in candidates:
            measured = measured_by_id.get(candidate.candidate_id)
            if measured:
                max_fraction = _clamp(_safe_float(measured.get("max_ternary_fraction"), 0.0))
                high_fraction = _clamp(_safe_float(measured.get("high_concentration_fraction"), max_fraction))
                hook_conc = measured.get("hook_concentration_nM")
                rows.append(
                    HookEffectPrediction(
                        candidate_id=candidate.candidate_id,
                        concentration_nM=[],
                        ternary_fraction=[],
                        hook_concentration_nM=_safe_float(hook_conc, 0.0) if hook_conc not in ("", None) else None,
                        max_ternary_fraction=round(max_fraction, 4),
                        high_concentration_fraction=round(high_fraction, 4),
                        hook_risk=measured.get("hook_risk", "unknown") or "unknown",
                        therapeutic_window_score=round(_clamp(_safe_float(measured.get("therapeutic_window_score"), max_fraction)), 3),
                        model_version=measured.get("source", "measured-dose-response-calibration-v0.1") or "measured-dose-response-calibration-v0.1",
                        warning=None,
                    )
                )
                continue
            deg = deg_by_id.get(candidate.candidate_id, DegradationPrediction(candidate_id=candidate.candidate_id))
            coop = coop_by_id.get(candidate.candidate_id, CooperativityPrediction(candidate_id=candidate.candidate_id))
            e3 = e3_by_id.get(candidate.candidate_id, E3ContextPrediction(candidate_id=candidate.candidate_id, total_context_score=0.6))
            kd_poi = max(1.0, float(deg.predicted_dc50_nM or 100.0))
            kd_e3 = {"CRBN": 250.0, "VHL": 180.0, "MDM2": 500.0, "IAP": 420.0, "CIAP1": 420.0}.get(candidate.e3_ligase.upper(), 400.0)
            alpha = max(0.05, coop.predicted_alpha or 1.0)
            e3_scale = _clamp(e3.total_context_score or 0.6, 0.15, 1.0)
            fractions: list[float] = []
            for concentration in concentrations:
                poi_binary = concentration / (kd_poi + concentration)
                e3_binary = concentration / (kd_e3 + concentration)
                productive = alpha * poi_binary * e3_binary * e3_scale
                binary_sink = 1.0 + concentration / (12.0 * kd_poi) + concentration / (12.0 * kd_e3)
                fractions.append(round(_clamp(productive / binary_sink), 4))
            max_fraction = max(fractions) if fractions else 0.0
            max_idx = fractions.index(max_fraction) if fractions else 0
            high_fraction = fractions[-1] if fractions else 0.0
            drop = (max_fraction - high_fraction) / max(max_fraction, 1e-6)
            if drop >= 0.55:
                hook_risk = "high"
            elif drop >= 0.25:
                hook_risk = "medium"
            else:
                hook_risk = "low"
            window_score = _clamp(0.75 * max_fraction + 0.25 * (1.0 - drop))
            rows.append(
                HookEffectPrediction(
                    candidate_id=candidate.candidate_id,
                    concentration_nM=concentrations,
                    ternary_fraction=fractions,
                    hook_concentration_nM=concentrations[max_idx] if fractions else None,
                    max_ternary_fraction=round(max_fraction, 4),
                    high_concentration_fraction=round(high_fraction, 4),
                    hook_risk=hook_risk,
                    therapeutic_window_score=round(window_score, 3),
                    warning="High-dose degradation may decline from binary target/E3 saturation." if hook_risk == "high" else None,
                )
            )
        return rows

    def update_active_learning_from_feedback(
        self,
        feedback: Sequence[AssayFeedbackRecord | dict[str, Any]],
        candidates: Sequence[CandidateRecord] | None = None,
    ) -> ActiveLearningUpdate:
        """Append assay feedback to a training table and report retraining readiness.

        This does not claim a calibrated model has been trained. It creates the
        supervised rows and a recommendation gate so a real training job can run
        when enough feedback accumulates.
        """
        ensure_directories()
        path = DATA_DIR / "assay_feedback_training.csv"
        registry_dir = DATA_DIR / "active_learning"
        registry_dir.mkdir(parents=True, exist_ok=True)
        registry_path = registry_dir / "model_registry.json"
        active_model_version = "heuristic_proxy-v0.1+feedback_registry"
        rollback_artifact = ""
        candidate_by_id = {c.candidate_id: c for c in (candidates or [])}
        rows: list[dict[str, Any]] = []
        for item in feedback:
            fb = item if isinstance(item, AssayFeedbackRecord) else AssayFeedbackRecord(**item)
            candidate = candidate_by_id.get(fb.candidate_id)
            smiles = fb.smiles or (candidate.full_protac_smiles if candidate else "")
            rows.append({
                "candidate_id": fb.candidate_id,
                "target": fb.target or (candidate.target if candidate else ""),
                "e3_ligase": fb.e3_ligase or (candidate.e3_ligase if candidate else ""),
                "cell_line": fb.cell_line or "default",
                "smiles": smiles,
                "measured_dc50_nM": fb.measured_dc50_nM,
                "measured_dmax_percent": fb.measured_dmax_percent,
                "measured_hook_concentration_nM": fb.measured_hook_concentration_nM,
                "degradation_observed": fb.degradation_observed,
                "source": fb.source,
                "notes": fb.notes,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        if not rows:
            existing = 0
            if path.exists():
                with path.open(newline="", encoding="utf-8") as handle:
                    existing = max(0, sum(1 for _ in csv.DictReader(handle)))
            return ActiveLearningUpdate(
                status="no_feedback",
                feedback_count=0,
                training_rows=existing,
                dataset_path=str(path) if path.exists() else "",
                registry_path=str(registry_path) if registry_path.exists() else "",
                active_model_version=active_model_version,
                rollback_model_artifact_path=rollback_artifact,
                retraining_recommendation="collect_more_feedback_before_retraining",
                warnings=["No assay feedback records supplied."],
            )
        existing = 0
        if path.exists():
            with path.open(newline="", encoding="utf-8") as handle:
                existing = max(0, sum(1 for _ in csv.DictReader(handle)))
        fieldnames = [
            "candidate_id", "target", "e3_ligase", "cell_line", "smiles",
            "measured_dc50_nM", "measured_dmax_percent", "measured_hook_concentration_nM",
            "degradation_observed", "source", "notes", "created_at",
        ]
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if path.stat().st_size == 0:
                writer.writeheader()
            writer.writerows(rows)
        total = existing + len(rows)
        if total >= 200:
            recommendation = "ready_for_full_retraining"
            artifact = str(DATA_DIR / "active_learning" / "next_degradation_model.joblib")
        elif total >= 40:
            recommendation = "ready_for_calibration_or_fine_tuning"
            artifact = ""
        else:
            recommendation = "collect_more_feedback_before_retraining"
            artifact = ""
        registry = {
            "registry_version": "protacpilot-active-learning-registry-v0.1",
            "active_model_version": active_model_version,
            "active_dataset_path": str(path),
            "training_rows": total,
            "latest_feedback_count": len(rows),
            "latest_update_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "candidate_schema": "synglue_agent.backend.schemas.CandidateRecord",
            "feedback_schema": "synglue_agent.backend.schemas.AssayFeedbackRecord",
            "recommended_next_action": recommendation,
            "next_model_artifact_path": artifact,
            "rollback_model_artifact_path": rollback_artifact,
            "status": "registry_only_no_trained_model",
            "limitations": [
                "Feedback rows are appended for calibration/retraining readiness.",
                "No new degradation model is trained by this function.",
                "Promote a model only after a separate reproducible training job writes a validated artifact.",
            ],
        }
        registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        return ActiveLearningUpdate(
            status="updated" if rows else "no_feedback",
            feedback_count=len(rows),
            training_rows=total,
            dataset_path=str(path),
            registry_path=str(registry_path),
            active_model_version=active_model_version,
            model_artifact_path=artifact,
            rollback_model_artifact_path=rollback_artifact,
            retraining_recommendation=recommendation,
            warnings=[] if rows else ["No assay feedback records supplied."],
        )

    # ------------------------------------------------------------------
    # Ranking, reflection, evolution, diversity, ternary feasibility
    # ------------------------------------------------------------------
    def rank_candidates(
        self,
        candidates: Sequence[CandidateRecord],
        degradation_predictions: Sequence[DegradationPrediction],
        admet_predictions: Sequence[ADMETPrediction],
        novelty_results: Sequence[NoveltyResult],
        domain_results: Sequence[ApplicabilityDomainResult],
        ternary_results: Sequence[TernaryFeasibilityResult] | None = None,
        cooperativity_results: Sequence[CooperativityPrediction] | None = None,
        hook_results: Sequence[HookEffectPrediction] | None = None,
        e3_context_results: Sequence[E3ContextPrediction] | None = None,
        ranking_weights: dict[str, float] | None = None,
    ) -> list[RankingResult]:
        if ranking_weights is None and isinstance(cooperativity_results, dict):
            ranking_weights = cooperativity_results
            cooperativity_results = None
        weights = dict(DEFAULT_RANKING_WEIGHTS)
        if ranking_weights:
            weights.update(ranking_weights)
        degradation_by_id = {item.candidate_id: item for item in degradation_predictions}
        admet_by_id = {item.candidate_id: item for item in admet_predictions}
        novelty_by_id = {item.candidate_id: item for item in novelty_results}
        domain_by_id = {item.candidate_id: item for item in domain_results}
        ternary_by_id = {item.candidate_id: item for item in (ternary_results or [])}
        coop_by_id = {item.candidate_id: item for item in (cooperativity_results or [])}
        hook_by_id = {item.candidate_id: item for item in (hook_results or [])}
        e3_context_by_id = {item.candidate_id: item for item in (e3_context_results or [])}

        rows: list[RankingResult] = []
        for candidate in candidates:
            deg = degradation_by_id.get(candidate.candidate_id, DegradationPrediction(candidate_id=candidate.candidate_id))
            admet = admet_by_id.get(candidate.candidate_id, ADMETPrediction(candidate_id=candidate.candidate_id))
            novelty = novelty_by_id.get(candidate.candidate_id, NoveltyResult(candidate_id=candidate.candidate_id, novelty_score=0.5))
            domain = domain_by_id.get(candidate.candidate_id, ApplicabilityDomainResult(candidate_id=candidate.candidate_id))
            ternary = ternary_by_id.get(
                candidate.candidate_id,
                TernaryFeasibilityResult(candidate_id=candidate.candidate_id, ternary_plausibility_score=0.5),
            )
            coop = coop_by_id.get(candidate.candidate_id, CooperativityPrediction(candidate_id=candidate.candidate_id, cooperativity_score=0.5))
            hook = hook_by_id.get(candidate.candidate_id, HookEffectPrediction(candidate_id=candidate.candidate_id, therapeutic_window_score=0.5, hook_risk="unknown"))
            e3_context = e3_context_by_id.get(candidate.candidate_id, E3ContextPrediction(candidate_id=candidate.candidate_id, total_context_score=0.6))
            dc50_score = self.compute_dc50_score(deg.predicted_dc50_nM)
            dmax_score = self.compute_dmax_score(deg.predicted_dmax_percent)
            admet_score = _clamp(1.0 - admet.overall_admet_penalty)
            ternary_score = ternary.ternary_plausibility_score
            coop_score = coop.cooperativity_score
            hook_score = hook.therapeutic_window_score
            e3_context_score = e3_context.total_context_score
            novelty_score = novelty.novelty_score
            synthetic_score = candidate.synthetic_feasibility_score
            protacdb_prior = self.protacdb_evidence_prior(candidate)
            protacdb_bonus = 0.05 * protacdb_prior["influence"] * (protacdb_prior["score"] - 0.5)
            candidate.provenance["protacdb_evidence_prior"] = protacdb_prior
            score = (
                weights["dc50"] * dc50_score
                + weights["dmax"] * dmax_score
                + weights["admet"] * admet_score
                + weights["ternary"] * ternary_score
                + weights.get("cooperativity", 0.0) * coop_score
                + weights.get("hook", 0.0) * hook_score
                + weights.get("e3_context", 0.0) * e3_context_score
                + weights["novelty"] * novelty_score
                + weights["synthetic"] * synthetic_score
                + protacdb_bonus
            )
            confidence = _clamp(
                0.32 * deg.model_confidence
                + 0.24 * domain.similarity_to_training_set
                + 0.18 * coop.confidence
                + 0.14 * e3_context.confidence
                + 0.12 * candidate.synthetic_feasibility_score
                + 0.08 * protacdb_prior["influence"] * protacdb_prior["diversity_prior"]
            )
            uncertainty = []
            if deg.model_confidence < 0.45:
                uncertainty.append("low_degradation_model_confidence")
            if domain.domain_status == "outside":
                uncertainty.append("outside_applicability_domain")
            if admet.hERG_risk == "high" or admet.DILI_risk == "high":
                uncertainty.append("high_admet_toxicity_risk")
            if hook.hook_risk == "high":
                uncertainty.append("high_hook_effect_risk")
            if e3_context.total_context_score < 0.45:
                uncertainty.append("weak_cell_type_e3_context")
            if candidate.candidate_id not in ternary_by_id:
                uncertainty.append("not_selected_for_expensive_ternary_modeling")
            if coop.model_version.startswith("cooperativity-proxy-v0.1") and "pose-structural-score" not in coop.model_version:
                uncertainty.append("proxy_cooperativity_not_measured_alpha")
            if hook.model_version.endswith("v0.1"):
                uncertainty.append("proxy_hook_model_not_fitted_to_dose_response")
            if not protacdb_prior["available"]:
                uncertainty.append("no_protacdb_prior_available_not_negative_evidence")
            elif protacdb_prior["source_scope"] != "exact_compound_match":
                uncertainty.append("protacdb_prior_is_target_e3_neighborhood_not_exact_compound")
            if not self.rdkit_available:
                uncertainty.append("rdkit_not_installed")
            penalty_bits = []
            if admet.overall_admet_penalty > 0.45:
                penalty_bits.append(f"ADME/Tox penalty {admet.overall_admet_penalty:.2f}")
            if novelty.duplicate_flag:
                penalty_bits.append("near duplicate of local known PROTAC")
            if domain.domain_status != "inside":
                penalty_bits.append(f"domain status {domain.domain_status}")
            if hook.hook_risk in {"medium", "high"}:
                penalty_bits.append(f"hook risk {hook.hook_risk}")
            if e3_context.contraindications:
                penalty_bits.append("; ".join(e3_context.contraindications[:2]))
            if protacdb_prior["available"]:
                penalty_bits.append(f"PROTAC-DB prior scope {protacdb_prior['source_scope']}")
            rows.append(
                RankingResult(
                    candidate_id=candidate.candidate_id,
                    final_priority_score=round(score, 3),
                    confidence=round(confidence, 3),
                    reason_for_rank=(
                        f"DC50 score {dc50_score:.2f}, Dmax score {dmax_score:.2f}, "
                        f"ADME score {admet_score:.2f}, ternary {ternary_score:.2f}, "
                        f"cooperativity {coop_score:.2f}, hook-window {hook_score:.2f}, "
                        f"E3 context {e3_context_score:.2f}, novelty {novelty_score:.2f}, synthetic {synthetic_score:.2f}, "
                        f"PROTAC-DB prior {protacdb_prior['score']:.2f} ({protacdb_prior['source_scope']}, capped)."
                    ),
                    penalty_explanation="; ".join(penalty_bits) if penalty_bits else "No dominant penalty in demo scoring.",
                    uncertainty_flags=uncertainty,
                )
            )

        rows.sort(key=lambda item: (item.final_priority_score, item.confidence), reverse=True)
        for rank, row in enumerate(rows, start=1):
            row.rank = rank
            row.tier = self.assign_candidate_tier(row.final_priority_score, row.confidence)
        return rows

    def compute_dc50_score(self, dc50_nM: float | None) -> float:
        if dc50_nM is None or dc50_nM <= 0:
            return 0.0
        return _clamp((4.0 - math.log10(dc50_nM)) / 3.5)

    def compute_dmax_score(self, dmax_percent: float | None) -> float:
        if dmax_percent is None:
            return 0.0
        return _clamp(dmax_percent / 100.0)

    def assign_candidate_tier(self, score: float, confidence: float) -> str:
        if score >= 0.72 and confidence >= 0.55:
            return "Tier 1"
        if score >= 0.55:
            return "Tier 2"
        return "Tier 3"

    def select_expensive_modeling_finalists(
        self,
        candidates: Sequence[CandidateRecord],
        rankings: Sequence[RankingResult],
        max_finalists: int = 12,
        similarity_threshold: float = 0.82,
    ) -> list[CandidateRecord]:
        """Choose a ranked, diverse subset for docking/P4ward-like work."""
        ranking_by_id = {item.candidate_id: item for item in rankings}
        ordered = sorted(
            candidates,
            key=lambda item: (
                ranking_by_id.get(item.candidate_id, RankingResult()).final_priority_score,
                ranking_by_id.get(item.candidate_id, RankingResult()).confidence,
                item.provenance.get("cheap_filter_score", 0.0),
            ),
            reverse=True,
        )
        finalists: list[CandidateRecord] = []
        for candidate in ordered:
            if len(finalists) >= max_finalists:
                break
            too_similar = any(
                self.calculate_similarity(candidate.full_protac_smiles, kept.full_protac_smiles) >= similarity_threshold
                for kept in finalists
            )
            if too_similar:
                continue
            candidate.provenance["selected_for_expensive_modeling"] = True
            finalists.append(candidate)
        if len(finalists) < min(max_finalists, len(ordered)):
            for candidate in ordered:
                if len(finalists) >= max_finalists:
                    break
                if candidate not in finalists:
                    candidate.provenance["selected_for_expensive_modeling"] = True
                    finalists.append(candidate)
        return finalists

    def cluster_candidates(self, candidates: Sequence[CandidateRecord], threshold: float = 0.62) -> list[DiversityCluster]:
        clusters: list[list[CandidateRecord]] = []
        for candidate in candidates:
            placed = False
            for cluster in clusters:
                if self.calculate_similarity(candidate.full_protac_smiles, cluster[0].full_protac_smiles) >= threshold:
                    cluster.append(candidate)
                    placed = True
                    break
            if not placed:
                clusters.append([candidate])
        result: list[DiversityCluster] = []
        total = max(1, len(candidates))
        for idx, cluster in enumerate(clusters, start=1):
            redundancy = max(0.0, (len(cluster) - 1) / total)
            result.append(
                DiversityCluster(
                    cluster_id=f"cluster_{idx}",
                    candidate_ids=[item.candidate_id for item in cluster],
                    representative_id=cluster[0].candidate_id if cluster else None,
                    redundancy_score=round(redundancy, 3),
                    diversity_score=round(1.0 - redundancy, 3),
                )
            )
        return result

    def choose_diverse_representatives(
        self,
        candidates: Sequence[CandidateRecord],
        rankings: Sequence[RankingResult],
        max_count: int,
    ) -> list[CandidateRecord]:
        ranking_by_id = {item.candidate_id: item for item in rankings}
        ordered = sorted(candidates, key=lambda item: ranking_by_id.get(item.candidate_id, RankingResult()).final_priority_score, reverse=True)
        selected: list[CandidateRecord] = []
        for candidate in ordered:
            if len(selected) >= max_count:
                break
            if all(self.calculate_similarity(candidate.full_protac_smiles, other.full_protac_smiles) < 0.82 for other in selected):
                selected.append(candidate)
        if len(selected) < min(max_count, len(ordered)):
            for candidate in ordered:
                if candidate not in selected:
                    selected.append(candidate)
                if len(selected) >= max_count:
                    break
        return selected

    def critique_candidates(
        self,
        candidates: Sequence[CandidateRecord],
        rankings: Sequence[RankingResult],
        degradation_predictions: Sequence[DegradationPrediction],
        admet_predictions: Sequence[ADMETPrediction],
        novelty_results: Sequence[NoveltyResult],
    ) -> list[ReflectionReview]:
        ranking_by_id = {item.candidate_id: item for item in rankings}
        deg_by_id = {item.candidate_id: item for item in degradation_predictions}
        admet_by_id = {item.candidate_id: item for item in admet_predictions}
        novelty_by_id = {item.candidate_id: item for item in novelty_results}
        reviews: list[ReflectionReview] = []
        for candidate in candidates:
            ranking = ranking_by_id.get(candidate.candidate_id, RankingResult())
            deg = deg_by_id.get(candidate.candidate_id, DegradationPrediction())
            admet = admet_by_id.get(candidate.candidate_id, ADMETPrediction())
            novelty = novelty_by_id.get(candidate.candidate_id, NoveltyResult())
            recommendations = []
            risk = 0.0
            if admet.hERG_risk == "high":
                recommendations.append("Reduce lipophilicity or replace linker/E3 handle to reduce hERG risk.")
                risk += 0.25
            if admet.solubility_risk == "high":
                recommendations.append("Consider shorter polar linker or reduce aromatic burden.")
                risk += 0.18
            if novelty.max_tanimoto_similarity > 0.85:
                recommendations.append("Increase linker or component novelty; nearest known PROTAC is close.")
                risk += 0.12
            if deg.model_confidence < 0.45:
                recommendations.append("Treat degradation prediction as exploratory and request better model/domain data.")
                risk += 0.18
            if not recommendations:
                recommendations.append("Proceed only to expert medicinal chemistry review; predictions are not experimental evidence.")
            plausibility = _clamp(0.55 * ranking.final_priority_score + 0.25 * candidate.synthetic_feasibility_score + 0.20 * deg.model_confidence)
            evidence = _clamp(0.45 * deg.model_confidence + 0.35 * candidate.synthetic_feasibility_score + 0.20 * (1.0 - novelty.duplicate_flag))
            reviews.append(
                ReflectionReview(
                    candidate_id=candidate.candidate_id,
                    review_score=round(_clamp(0.5 * plausibility + 0.3 * evidence + 0.2 * (1.0 - risk)), 3),
                    plausibility_score=round(plausibility, 3),
                    evidence_score=round(evidence, 3),
                    risk_score=round(_clamp(risk), 3),
                    overclaiming_warning="Predicted degradation is computational only; no experimental validation is implied.",
                    factual_consistency_check="provenance_present" if candidate.warhead_source and candidate.e3_ligand_name else "missing_component_provenance",
                    recommendations=recommendations,
                )
            )
        return reviews

    def evolve_with_generations(
        self,
        candidates: Sequence[CandidateRecord],
        rankings: Sequence[RankingResult],
        admet_predictions: Sequence[ADMETPrediction],
        start_seen: set[str] | None = None,
        max_generations: int = 10,
        novelty_floor: float = 0.10,
        patience: int = 2,
    ) -> dict:
        """Bounded evolution loop WITH memory (AGENT_ARCHITECTURE_UPDATE §2)."""
        from synglue_agent.backend.schemas import GenerationRecord
        seen = set(start_seen or set())
        all_evolved: List[CandidateRecord] = []
        records: List[GenerationRecord] = []
        stop_reason = "max_generations"
        ranking_by_id = {item.candidate_id: item for item in rankings}

        def key(smi: str) -> str:
            return chem_identity(smi) or smi

        def score(c):
            r = ranking_by_id.get(c.candidate_id)
            return float(r.final_priority_score) if r else 0.5

        for generation in range(1, max_generations + 1):
            gen_out = self.evolve_candidates(
                candidates, rankings, admet_predictions, None,
                max_new=max(4, max_generations))
            produced = [c for c in gen_out if c.full_protac_smiles]
            n_novel = 0
            op_counts: dict = {}
            for c in produced:
                k = key(c.full_protac_smiles)
                if k not in seen:
                    seen.add(k)
                    n_novel += 1
                op = getattr(c, "operator_applied", None) or "evolve_candidates"
                op_counts[op] = op_counts.get(op, 0) + 1
                try:
                    c.parent_ids = [p_.candidate_id for p_ in candidates[:2]]
                    c.operator_applied = op
                    c.generation = generation
                except Exception:  # noqa: BLE001
                    pass
            scores = [score(c) for c in produced] or [0.0]
            ratio = n_novel / max(len(produced), 1)
            records.append(GenerationRecord(
                generation=generation, n_produced=len(produced), n_novel=n_novel,
                novelty_ratio=round(ratio, 3), best_score=round(max(scores), 3),
                mean_score=round(sum(scores) / len(scores), 3),
                operator_counts=op_counts, fitness_spec_id="fitness@v1"))
            all_evolved.extend(produced)
            recent = [r.novelty_ratio for r in records[-patience:]]
            if len(recent) >= patience and all(x < novelty_floor for x in recent):
                stop_reason = f"novelty_ratio<{novelty_floor} for {patience} gens"
                break
            if not produced:
                stop_reason = "no_valid_offspring"
                break
        return {"evolved": all_evolved, "records": records,
                "stop_reason": stop_reason, "seen": seen}

    def _smiles_mutate(self, smiles: str, rng=None) -> str | None:
        """Single-point SMILES mutation with retries.

        Only swaps aliphatic non-ring atoms (C<->N<->O) so sanitization holds;
        up to 10 attempts. Returns None when no valid mutant is found.
        """
        if not self.rdkit_available:
            return None
        import random as _random
        rng = rng or _random.Random()
        mol = Chem.MolFromSmiles(smiles)
        if mol is None or mol.GetNumAtoms() < 4:
            return None
        for _ in range(10):
            editable = Chem.RWMol(mol)
            candidates = [
                i for i in range(editable.GetNumAtoms())
                if not editable.GetAtomWithIdx(i).GetIsAromatic()
                and editable.GetAtomWithIdx(i).GetTotalDegree() <= 2
            ]
            if not candidates:
                return None
            atom_idx = rng.choice(candidates)
            atom = editable.GetAtomWithIdx(atom_idx)
            z = atom.GetAtomicNum()
            if z == 6:
                atom.SetAtomicNum(rng.choice([7, 8]))
            elif z == 7:
                atom.SetAtomicNum(rng.choice([6, 8]))
            elif z == 8:
                atom.SetAtomicNum(rng.choice([6, 7]))
            else:
                continue
            try:
                new_mol = editable.GetMol()
                Chem.SanitizeMol(new_mol)
                out = Chem.MolToSmiles(new_mol)
                if out and out != smiles:
                    return out
            except Exception:
                continue
        return None

    def _smiles_crossover(self, a: str, b: str, rng=None) -> str | None:
        """BRICS-fragment crossover: exchange one BRICS fragment between parents.

        Uses RDKit's BRICS decomposition (fragments carry dummy attachment
        atoms) and recombines via a single bond at the dummy positions.
        Returns None when the recombination fails to sanitize.
        """
        if not self.rdkit_available:
            return None
        import random as _random
        rng = rng or _random.Random()
        try:
            from rdkit.Chem import BRICS
            ma, mb = Chem.MolFromSmiles(a), Chem.MolFromSmiles(b)
            if ma is None or mb is None:
                return None
            fa = [frag for frag in BRICS.BRICSDecompose(ma) if "[*" in frag]
            fb = [frag for frag in BRICS.BRICSDecompose(mb) if "[*" in frag]
            if not fa or not fb:
                return None
            frag_a, frag_b = rng.choice(fa), rng.choice(fb)
            mol_a = Chem.MolFromSmiles(frag_a)
            mol_b = Chem.MolFromSmiles(frag_b)
            if mol_a is None or mol_b is None:
                return None
            da = [at for at in mol_a.GetAtoms() if at.GetAtomicNum() == 0]
            db = [at for at in mol_b.GetAtoms() if at.GetAtomicNum() == 0]
            if not da or not db:
                return None
            combo = Chem.CombineMols(mol_a, mol_b)
            rw = Chem.RWMol(combo)
            off = mol_a.GetNumAtoms()
            rw.AddBond(da[0].GetIdx(), off + db[0].GetIdx(), Chem.BondType.SINGLE)
            # remove the two dummy atoms (indices shift after first removal)
            hi = max(da[0].GetIdx(), off + db[0].GetIdx())
            lo = min(da[0].GetIdx(), off + db[0].GetIdx())
            rw.RemoveAtom(hi)
            rw.RemoveAtom(lo)
            mol = rw.GetMol()
            Chem.SanitizeMol(mol)
            out = Chem.MolToSmiles(mol)
            return out if out not in (a, b) else None
        except Exception:
            return None

    def evolve_candidates(
        self,
        candidates: Sequence[CandidateRecord],
        rankings: Sequence[RankingResult],
        admet_predictions: Sequence[ADMETPrediction],
        target_record: TargetRecord | None,
        max_new: int = 8,
    ) -> list[CandidateRecord]:
        if not candidates:
            return []
        admet_by_id = {item.candidate_id: item for item in admet_predictions}
        ranking_by_id = {item.candidate_id: item for item in rankings}
        parent_pool = sorted(
            candidates,
            key=lambda item: (
                admet_by_id.get(item.candidate_id, ADMETPrediction()).overall_admet_penalty,
                ranking_by_id.get(item.candidate_id, RankingResult()).final_priority_score,
            ),
            reverse=True,
        )[: max(3, max_new)]
        short_linkers = [item for item in self.generate_linkers(["alkyl", "PEG", "triazole"], max_linkers=12) if item.graph_length <= 7]
        evolved: list[CandidateRecord] = []
        seen = {item.full_protac_smiles for item in candidates}
        for parent in parent_pool:
            if len(evolved) >= max_new:
                break
            parent_admet = admet_by_id.get(parent.candidate_id, ADMETPrediction())
            if parent_admet.overall_admet_penalty < 0.25 and parent.rotatable_bonds and parent.rotatable_bonds < 18:
                continue
            warhead = WarheadRecord(
                name=parent.warhead_name,
                target=parent.target,
                smiles=parent.warhead_smiles,
                source=parent.warhead_source,
                potency_score=0.55,
                derivatization_score=0.65,
                exit_vector_confidence=0.8,
                source_confidence=0.7,
            )
            e3 = E3LigandRecord(
                name=parent.e3_ligand_name,
                e3_ligase=parent.e3_ligase,
                smiles=parent.e3_ligand_smiles,
                source="retained_parent_component",
                exit_vector_confidence=0.8,
                source_confidence=0.7,
                diversity_score=0.5,
            )
            for linker in short_linkers:
                if linker.name == parent.linker_name:
                    continue
                _, variants = self.construct_protac_candidates(
                    [warhead],
                    [e3],
                    [linker],
                    target_record,
                    candidate_count=1,
                    use_retrosynthesis_filtering=False,
                )
                if not variants:
                    continue
                variant = variants[0]
                if variant.full_protac_smiles in seen:
                    continue
                variant.provenance["evolution_parent"] = parent.candidate_id
                variant.provenance["evolution_action"] = "linker replacement to reduce size/flexibility/ADME penalty"
                variant.warning_flags.append("evolved_candidate_requires_revalidation")
                seen.add(variant.full_protac_smiles)
                evolved.append(variant)
                break
        # Genetic diversity pass (bounded): mutate/crossover the best parents.
        if len(evolved) < max_new:
            import random as _random
            rng = _random.Random(sum(ord(ch) for ch in parent_pool[0].candidate_id))
            for parent in parent_pool[:3]:
                for _ in range(4):
                    if len(evolved) >= max_new:
                        break
                    child_smiles = self._smiles_mutate(parent.full_protac_smiles, rng)
                    if not child_smiles or child_smiles in seen:
                        continue
                    child = parent.model_copy(deep=True)
                    child.candidate_id = f"{parent.candidate_id}_mut{len(evolved)}"
                    child.full_protac_smiles = child_smiles
                    child.evolution_generation = getattr(child, "evolution_generation", 0) + 1
                    evolved.append(child)
                    seen.add(child_smiles)
        return evolved

    def assess_ternary_feasibility(
        self,
        candidates: Sequence[CandidateRecord],
        target_record: TargetRecord | None,
        top_n: int = 12,
    ) -> list[TernaryFeasibilityResult]:
        results: list[TernaryFeasibilityResult] = []
        structure_available = bool(target_record and (target_record.structures or target_record.alphafold_id))
        for candidate in list(candidates)[:top_n]:
            length = max(1.0, float(candidate.rotatable_bonds or 10) + float(len(candidate.linker_smiles)) / 12.0)
            reachability = _clamp(1.0 - abs(length - 16.0) / 22.0)
            flexibility = _clamp((candidate.rotatable_bonds or 10) / 24.0)
            geometry = _clamp(0.55 * reachability + 0.25 * flexibility + 0.20 * (1.0 if structure_available else 0.45))
            plausibility = _clamp(0.65 * geometry + 0.20 * candidate.synthetic_feasibility_score + 0.15 * (1.0 if structure_available else 0.4))
            pose_pdb = (
                candidate.provenance.get("ternary_pose_pdb")
                or candidate.provenance.get("pose_pdb")
                or candidate.provenance.get("docked_ternary_pose_pdb")
            )
            structural_payload: dict[str, Any] = {
                "structural_backend": "geometry_proxy_stub",
                "structural_warnings": ["No ternary pose PDB supplied; structural backend not run."],
            }
            docking_status = "not_run_stub_available"
            structure_label = "target_structure_or_alphafold_available" if structure_available else "not_available_locally"
            interface_warning = None if structure_available else "No target structure available in local table; geometry score is lower confidence."
            if pose_pdb:
                smiles_for_strain = candidate.full_protac_smiles or candidate.linker_smiles
                structural = score_ternary_pose_for_candidate(
                    candidate_id=candidate.candidate_id,
                    pose_pdb=pose_pdb,
                    smiles=smiles_for_strain,
                    target_chain=str(candidate.provenance.get("target_chain") or ""),
                    e3_chain=str(candidate.provenance.get("e3_chain") or ""),
                )
                if structural.real_structural_score > 0 or not structural.warnings:
                    plausibility = _clamp(0.20 * plausibility + 0.80 * structural.real_structural_score)
                    geometry = _clamp(0.45 * geometry + 0.55 * structural.real_structural_score)
                    reachability = structural.lysine_geometry_score or reachability
                    docking_status = "pose_backed_structural_scoring"
                    structure_label = "ternary_pose_file"
                    interface_warning = "; ".join(structural.warnings) if structural.warnings else None
                else:
                    docking_status = "pose_file_unusable"
                    structure_label = "ternary_pose_file_unusable"
                    interface_warning = "; ".join(structural.warnings) if structural.warnings else interface_warning
                structural_payload = {
                    "structural_backend": structural.backend,
                    "pose_file": structural.pose_file,
                    "interface_quality_score": structural.interface_quality_score,
                    "interface_contact_count": structural.interface_contact_count,
                    "polar_contact_count": structural.polar_contact_count,
                    "clash_count": structural.clash_count,
                    "buried_sasa_proxy": structural.buried_sasa_proxy,
                    "nearest_lysine": structural.nearest_lysine,
                    "nearest_lysine_distance_A": structural.nearest_lysine_distance_A,
                    "accessible_lysine_count": structural.accessible_lysine_count,
                    "productive_lysine_count": structural.productive_lysine_count,
                    "lysine_geometry_score": structural.lysine_geometry_score,
                    "linker_strain_score": structural.linker_strain_score,
                    "linker_energy_spread": structural.linker_energy_spread,
                    "real_structural_score": structural.real_structural_score,
                    "structural_confidence": structural.confidence,
                    "structural_warnings": structural.warnings,
                }
            results.append(
                TernaryFeasibilityResult(
                    candidate_id=candidate.candidate_id,
                    fast_geometry_feasibility_score=round(geometry, 3),
                    linker_reachability_score=round(reachability, 3),
                    ternary_plausibility_score=round(plausibility, 3),
                    docking_status=docking_status,
                    interface_warning=interface_warning,
                    structure_availability=structure_label,
                    proceed_to_expensive_modeling=plausibility >= 0.58,
                    **structural_payload,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Reporting and memory
    # ------------------------------------------------------------------
    def generate_candidate_table(
        self,
        candidates: Sequence[CandidateRecord],
        rankings: Sequence[RankingResult],
        degradation_predictions: Sequence[DegradationPrediction],
        admet_predictions: Sequence[ADMETPrediction],
        novelty_results: Sequence[NoveltyResult],
        ternary_results: Sequence[TernaryFeasibilityResult],
        cooperativity_results: Sequence[CooperativityPrediction] | None = None,
        hook_results: Sequence[HookEffectPrediction] | None = None,
        e3_context_results: Sequence[E3ContextPrediction] | None = None,
    ) -> list[dict[str, Any]]:
        ranking_by_id = {item.candidate_id: item for item in rankings}
        deg_by_id = {item.candidate_id: item for item in degradation_predictions}
        admet_by_id = {item.candidate_id: item for item in admet_predictions}
        novelty_by_id = {item.candidate_id: item for item in novelty_results}
        ternary_by_id = {item.candidate_id: item for item in ternary_results}
        coop_by_id = {item.candidate_id: item for item in (cooperativity_results or [])}
        hook_by_id = {item.candidate_id: item for item in (hook_results or [])}
        e3_context_by_id = {item.candidate_id: item for item in (e3_context_results or [])}
        ordered = sorted(candidates, key=lambda item: ranking_by_id.get(item.candidate_id, RankingResult()).rank or 999999)
        rows: list[dict[str, Any]] = []
        for candidate in ordered:
            ranking = ranking_by_id.get(candidate.candidate_id, RankingResult(candidate_id=candidate.candidate_id))
            deg = deg_by_id.get(candidate.candidate_id, DegradationPrediction(candidate_id=candidate.candidate_id))
            admet = admet_by_id.get(candidate.candidate_id, ADMETPrediction(candidate_id=candidate.candidate_id))
            novelty = novelty_by_id.get(candidate.candidate_id, NoveltyResult(candidate_id=candidate.candidate_id))
            ternary = ternary_by_id.get(candidate.candidate_id, TernaryFeasibilityResult(candidate_id=candidate.candidate_id))
            coop = coop_by_id.get(candidate.candidate_id, CooperativityPrediction(candidate_id=candidate.candidate_id))
            hook = hook_by_id.get(candidate.candidate_id, HookEffectPrediction(candidate_id=candidate.candidate_id))
            e3_context = e3_context_by_id.get(candidate.candidate_id, E3ContextPrediction(candidate_id=candidate.candidate_id))
            protacdb_prior = candidate.provenance.get("protacdb_evidence_prior") or self.protacdb_evidence_prior(candidate)
            rows.append(
                {
                    "Rank": ranking.rank,
                    "Tier": ranking.tier,
                    "Target": candidate.target,
                    "E3 ligase": candidate.e3_ligase,
                    "Warhead name": candidate.warhead_name,
                    "Warhead SMILES": candidate.warhead_smiles,
                    "Warhead source": candidate.warhead_source,
                    "E3 ligand name": candidate.e3_ligand_name,
                    "E3 ligand SMILES": candidate.e3_ligand_smiles,
                    "Linker SMILES": candidate.linker_smiles,
                    "Linker class": candidate.linker_class,
                    "Full PROTAC SMILES": candidate.full_protac_smiles,
                    "Assembly strategy": candidate.assembly_strategy,
                    "Reaction class": candidate.reaction_class,
                    "Validity status": candidate.validity_status,
                    "MW": admet.mw,
                    "TPSA": admet.tpsa,
                    "logP": admet.logp,
                    "HBD": admet.hbd,
                    "HBA": admet.hba,
                    "Rotatable bonds": admet.rotatable_bonds,
                    "Predicted DC50 nM": deg.predicted_dc50_nM,
                    "Predicted Dmax %": deg.predicted_dmax_percent,
                    "Degradation confidence": deg.model_confidence,
                    "Applicability domain": deg.applicability_domain_score,
                    "hERG risk": admet.hERG_risk,
                    "AMES risk": admet.AMES_risk,
                    "DILI risk": admet.DILI_risk,
                    "Solubility risk": admet.solubility_risk,
                    "Novelty score": novelty.novelty_score,
                    "Nearest known PROTAC similarity": novelty.max_tanimoto_similarity,
                    "Ternary feasibility score": ternary.ternary_plausibility_score,
                    "Structural backend": ternary.structural_backend,
                    "Pose file": ternary.pose_file,
                    "Real structural score": ternary.real_structural_score,
                    "Structural confidence": ternary.structural_confidence,
                    "Interface score": ternary.interface_quality_score,
                    "Interface contacts": ternary.interface_contact_count,
                    "Polar contacts": ternary.polar_contact_count,
                    "Clashes": ternary.clash_count,
                    "Buried SASA proxy": ternary.buried_sasa_proxy,
                    "Nearest lysine": ternary.nearest_lysine,
                    "Nearest lysine distance A": ternary.nearest_lysine_distance_A,
                    "Accessible lysines": ternary.accessible_lysine_count,
                    "Productive lysines": ternary.productive_lysine_count,
                    "Lysine geometry score": ternary.lysine_geometry_score,
                    "Linker strain score": ternary.linker_strain_score,
                    "Linker energy spread": ternary.linker_energy_spread,
                    "Predicted cooperativity alpha": coop.predicted_alpha,
                    "Cooperativity score": coop.cooperativity_score,
                    "Cooperativity model": coop.model_version,
                    "Hook concentration nM": hook.hook_concentration_nM,
                    "Hook risk": hook.hook_risk,
                    "Therapeutic window score": hook.therapeutic_window_score,
                    "Hook model": hook.model_version,
                    "Cell line": e3_context.cell_line,
                    "E3 context score": e3_context.total_context_score,
                    "E3 expression score": e3_context.expression_score,
                    "PROTAC-DB prior score": protacdb_prior.get("score"),
                    "PROTAC-DB prior scope": protacdb_prior.get("source_scope"),
                    "PROTAC-DB evidence families": ";".join(sorted((protacdb_prior.get("evidence_family_counts") or {}).keys())),
                    "Synthetic feasibility score": candidate.synthetic_feasibility_score,
                    "Final priority score": ranking.final_priority_score,
                    "Warning flags": ";".join(candidate.warning_flags + ranking.uncertainty_flags),
                    "Reason for ranking": ranking.reason_for_rank,
                }
            )
        return rows

    def generate_agent_workflow_table(self, state: WorkflowState) -> list[dict[str, Any]]:
        target = state.target_record.gene_symbol if state.target_record else state.parsed_objective.target_name
        from synglue_agent.toolkit.registry import get_tool_status

        def status_label(tool_name: str) -> str:
            status = get_tool_status(tool_name)
            if status["executable"]:
                return "executable"
            if status["available"]:
                return "available"
            if status["registered"]:
                return "registered"
            return "unregistered"

        def row(
            agent_type: str,
            selected_tool: str,
            data_sources: str,
            query: str,
            outputs: str,
            processing_time: str,
            real_output: str,
            integration_note: str = "",
        ) -> dict[str, Any]:
            tool_status = status_label(selected_tool)
            if not integration_note and tool_status != "executable":
                integration_note = "planned integration"
            return {
                "Agent type": agent_type,
                "Selected tool": selected_tool,
                "Tool status": tool_status,
                "Real output generated": real_output,
                "Integration note": integration_note,
                "Data sources/tools": data_sources,
                "Query parameters": query,
                "Quantitative outputs": outputs,
                "Processing time": processing_time,
            }

        return [
            row(
                "Controlled Search Agent",
                "Search policy",
                "bounded deterministic budget policy",
                f"requested_candidates={state.parsed_objective.candidate_count}",
                f"linker_budget={state.search_policy.linker_budget}, construction_budget={state.search_policy.construction_budget}, expensive_budget={state.search_policy.expensive_modeling_budget}",
                "milliseconds locally",
                "yes - explicit NP-hard search budgets",
            ),
            row(
                "Target Resolver Agent",
                "Target assessment",
                "local curated target table; ChEMBL target fallback if network is available; no PDB/AlphaFold fetch is run here",
                f"target={target}, organism=human",
                f"UniProt={getattr(state.target_record, 'uniprot_id', None)}, structures={len(getattr(state.target_record, 'structures', []) or [])}, tractability={getattr(state.target_record, 'tractability_score', 0)}",
                "milliseconds locally; seconds only if online ChEMBL fallback is reached",
                "yes - local/ChEMBL target metadata" if state.target_record else "no - unresolved target",
            ),
            row(
                "Binder Retrieval Agent",
                "Warhead mining",
                "local curated binders; optional ChEMBL online fallback; PubChem name lookup only as ChEMBL helper; BindingDB is planned, not run",
                "activity IC50/Ki/Kd/EC50 <= 1000 nM; assay confidence threshold",
                f"binders={len(state.retrieved_binders)}, unique_smiles={len({item.smiles for item in state.retrieved_binders})}",
                "milliseconds locally; minutes only with online APIs",
                "yes - binder records returned" if state.retrieved_binders else "no - no binder records",
                "PubChem and BindingDB remain planned integrations unless their specific callables are invoked.",
            ),
            row(
                "Warhead Selection Agent",
                "Warhead mining",
                "selected binders, local scoring, optional RDKit validation; curated exit-vector markers only",
                "activity IC50/Ki/Kd <= 1000 nM; derivatization feasible",
                f"binders={len(state.retrieved_binders)}, warheads={len(state.selected_warheads)}",
                "milliseconds locally",
                "yes - selected warhead records" if state.selected_warheads else "no - no warheads selected",
            ),
            row(
                "E3 Ligand Agent",
                "E3 ligase selection",
                "local curated CRBN/VHL/IAP/MDM2 handles plus optional explicit expression context",
                f"requested_e3={state.parsed_objective.e3_ligase or 'CRBN/VHL comparison'}, cell_line={state.parsed_objective.cell_line or 'default'}",
                f"e3_ligands={len(state.selected_e3_ligands)}, ligases={len({item.e3_ligase for item in state.selected_e3_ligands})}",
                "milliseconds locally",
                "yes - local E3 ligand records" if state.selected_e3_ligands else "no - no E3 ligands selected",
                "External HPA/DepMap/ProteomicsDB/E3Net expression queries remain planned integrations.",
            ),
            row(
                "Cell Context Agent",
                "E3-context compatibility",
                "curated E3 expression evidence, target localization rules, optional user expression overrides",
                f"cell_line={state.parsed_objective.cell_line or 'default'}, overrides={bool(state.parsed_objective.expression_overrides)}",
                f"e3_context_records={len(state.e3_context_predictions)}",
                "milliseconds locally",
                "yes - deterministic cell/E3 context scores" if state.e3_context_predictions else "no - no context records",
            ),
            row(
                "Exit Vector Agent",
                "Warhead Agent",
                "explicit attachment markers and local confidence rules; no structural exit-vector modeling is run",
                "warhead and E3 ligand component SMILES",
                f"vectors={len(state.exit_vectors)}, ambiguous={sum(1 for item in state.exit_vectors if item.failure_reason)}",
                "milliseconds locally",
                "yes - local exit-vector annotations" if state.exit_vectors else "no - no exit-vector annotations",
            ),
            row(
                "Linker Generation Agent",
                "Linker design",
                "curated linker CSV plus rule-based enumeration; LinkInvent/DiffLinker/DeLinker are planned, not run",
                f"linker_types={','.join(state.parsed_objective.preferred_linker_types)}",
                f"linkers={len(state.generated_linkers)}, classes={len({item.linker_class for item in state.generated_linkers})}",
                "milliseconds locally; model generation not run",
                "yes - curated/rule-based linker records" if state.generated_linkers else "no - no linkers generated",
                "Generative linker models remain planned integrations.",
            ),
            row(
                "Construction Agent",
                "Assembly Agent",
                "local dummy-atom assembly with RDKit when installed; named strategies currently share the same assembler",
                "warhead + linker + E3 with valid exit vectors",
                f"attempts={len(state.construction_attempts)}, valid={len(state.valid_candidates)}",
                "seconds locally",
                "yes - assembled candidate records" if state.valid_candidates else "no - no valid candidates",
                "Retrosynthesis-aware route planning is planned integration.",
            ),
            row(
                "Cheap Filter Agent",
                "Cheap molecular filter",
                "RDKit validity, MW, TPSA, rotatable bonds, synthetic feasibility, novelty, ADMET, applicability domain, E3 context",
                f"max_keep={state.search_policy.cheap_filter_budget}",
                f"kept={state.cheap_filter_summary.get('kept_candidates', 0)}, rejected={state.cheap_filter_summary.get('rejected_candidates', 0)}",
                "milliseconds to seconds locally",
                "yes - pre-ternary filtered candidate set" if state.cheap_filter_summary else "no - filter not run",
            ),
            row(
                "Prediction Agent",
                "DC50/Dmax prediction",
                "heuristic demo predictor in codebase; no trained SynGlue/DeepPROTACs/PROTAC-STAN model is loaded",
                "cheap-filter survivors, components, target, E3 ligase, optional cell context",
                f"degradation_predictions={len(state.degradation_predictions)}",
                "seconds locally",
                "no - heuristic demo predictions only" if state.degradation_predictions else "no - no predictions",
                "Trained DC50/Dmax prediction is planned integration.",
            ),
            row(
                "ADME/Tox Agent",
                "ADME/Tox skill",
                "RDKit descriptors when available plus heuristic risk triage; SwissADME/ADMETlab/pkCSM/ProTox-II are not run",
                "PROTAC-aware thresholds; no strict Lipinski rejection",
                f"admet_records={len(state.admet_predictions)}",
                "seconds locally",
                "no - heuristic/local ADME-Tox triage only" if state.admet_predictions else "no - no ADME/Tox records",
                "External ADME/Tox predictors remain planned integrations.",
            ),
            row(
                "Novelty Agent",
                "Novelty/IP check",
                "local known-PROTAC set; RDKit Morgan similarity when available; patent/PubChem/ChEMBL novelty search is not run",
                "candidate SMILES and similarity thresholds",
                f"novelty_records={len(state.novelty_results)}",
                "seconds locally",
                "yes - local similarity/duplicate records" if state.novelty_results else "no - no novelty records",
                "SureChEMBL/Lens/Google Patents/PubChem novelty search is planned integration.",
            ),
            row(
                "Ternary Feasibility Agent",
                "Ternary complex modeling",
                "finalist-only geometry proxy; docking/P4ward only when structure-aware ranking is requested and tools are available",
                f"finalist_ids={len(state.expensive_modeling_candidate_ids)}",
                f"ternary_records={len(state.ternary_feasibility_results)}",
                "seconds locally; docking not run",
                "no - geometry proxy only" if state.ternary_feasibility_results else "no - skipped or no ternary records",
                "Docking/ternary modeling is planned integration.",
            ),
            row(
                "Cooperativity Agent",
                "Cooperativity proxy",
                "ternary geometry, linker strain, interface-contact proxy, and lysine-geometry proxy",
                "valid candidates plus ternary feasibility records",
                f"cooperativity_records={len(state.cooperativity_predictions)}",
                "milliseconds locally",
                "yes - proxy alpha estimates" if state.cooperativity_predictions else "no - no cooperativity records",
                "Measured alpha or calibrated structure/ML cooperativity model is still needed for validation.",
            ),
            row(
                "Hook Effect Agent",
                "Concentration occupancy model",
                "DC50/Dmax predictions, E3 affinity priors, cooperativity alpha, and cell-context E3 score",
                "0.1-10000 nM concentration grid",
                f"hook_records={len(state.hook_effect_predictions)}, high_risk={sum(1 for item in state.hook_effect_predictions if item.hook_risk == 'high')}",
                "milliseconds locally",
                "yes - concentration-dependent hook-risk curves" if state.hook_effect_predictions else "no - no hook records",
                "Occupancy parameters are priors until fitted to cellular dose-response data.",
            ),
            row(
                "Ranking Agent",
                "Ranking skill",
                "weighted deterministic ranking over available local/heuristic outputs",
                state.parsed_objective.optimization_objective,
                f"ranked={len(state.ranking_results)}, final={len(state.final_ranked_candidates)}",
                "seconds",
                "yes - ranking records over current outputs" if state.ranking_results else "no - no ranking records",
            ),
            row(
                "Reflection/Evolution Agent",
                "Mini-PROTAC optimization",
                "deterministic critique and linker replacement over current candidate records",
                "top candidates and weaknesses",
                f"reviews={len(state.reflection_reviews)}, evolved={len(state.evolved_candidates)}",
                "seconds to minutes",
                "yes - local deterministic review/evolution records" if state.reflection_reviews or state.evolved_candidates else "no - no review/evolution records",
                "Full generative mini-PROTAC optimization is planned integration.",
            ),
            row(
                "Safety/Human Review Agent",
                "Assay planning skill",
                "local guardrail rules and warning aggregation",
                "final candidates and requested use",
                f"warnings={len(state.warnings)}, errors={len(state.errors)}, human_review_required=True",
                "milliseconds locally",
                "no - assay/human-review plan not generated; local guardrail status only",
                "Expert assay planning and human-review packet generation are planned integrations.",
            ),
        ]

    def generate_pipeline_status_table(self, state: WorkflowState) -> list[dict[str, Any]]:
        from synglue_agent.toolkit.status import get_tool_status

        def status_for(name: str) -> dict[str, Any]:
            return get_tool_status(name)

        def label(name: str, override: str | None = None) -> str:
            status = status_for(name)
            if override:
                return f"{name}: {override}"
            if status["executable"]:
                return f"{name}: executable"
            if status["classification"] == "stub":
                return f"{name}: heuristic_stub"
            if status["registered"]:
                return f"{name}: registered but not executable"
            return f"{name}: not connected"

        def evidence(name: str, extra: str = "") -> str:
            status = status_for(name)
            parts = [
                f"source={status.get('source_sheet')} row={status.get('source_row')}",
                f"availability={status.get('evidence', {}).get('availability')}",
                f"implementation={status.get('evidence', {}).get('implementation')}",
            ]
            if extra:
                parts.append(extra)
            return "; ".join(str(part) for part in parts if part)

        docking_status = status_for("GNINA")
        pubchem_status = status_for("PubChem")
        admet_backends = []
        for item in state.admet_predictions:
            warning = item.warning or ""
            if "backend=" in warning:
                value = warning.split("backend=", 1)[1].split(";", 1)[0].strip()
                if value:
                    admet_backends.append(value)
        admet_backend = admet_backends[0] if admet_backends else "unknown"
        admet_real = bool(state.admet_predictions) and admet_backend not in {"heuristic_stub", "unknown"}
        rows = [
            {
                "step_name": "target resolution",
                "selected_tool_or_method": "Target assessment; optional UniProt executable lookup available separately",
                "tool_status": f"{label('Target assessment')}; {label('UniProt')}",
                "output_type": "TargetRecord",
                "real_output_generated": bool(state.target_record),
                "stub_or_heuristic": "local_demo_or_api_wrapper" if state.target_record else "not_connected",
                "evidence": evidence("Target assessment", f"target_record_present={bool(state.target_record)}"),
                "limitation": "Workflow still primarily uses local curated target records unless explicit executable wrappers are called.",
                "next_integration_needed": "Route target resolution through UniProt/Open Targets/RCSB executable wrappers with no silent local fallback.",
            },
            {
                "step_name": "warhead/binder retrieval",
                "selected_tool_or_method": "Warhead mining; local curated binders; PubChem lookup wrapper available separately",
                "tool_status": f"{label('Warhead mining')}; PubChem lookup: {'executable only if wrapper exists and succeeds' if pubchem_status['executable'] else 'registered but not executable'}",
                "output_type": "list[BinderRecord]",
                "real_output_generated": bool(state.retrieved_binders),
                "stub_or_heuristic": "local_demo" if state.retrieved_binders else "not_connected",
                "evidence": evidence("Warhead mining", f"binders={len(state.retrieved_binders)}"),
                "limitation": "BindingDB is not connected; PubChem is not claimed unless its wrapper is explicitly called and succeeds.",
                "next_integration_needed": "Connect ChEMBL/BindingDB executable mining and provenance filtering.",
            },
            {
                "step_name": "E3 ligand selection",
                "selected_tool_or_method": "E3 ligase selection from local curated E3 ligand table",
                "tool_status": label("E3 ligase selection"),
                "output_type": "list[E3LigandRecord]",
                "real_output_generated": bool(state.selected_e3_ligands),
                "stub_or_heuristic": "local_demo" if state.selected_e3_ligands else "not_connected",
                "evidence": evidence("E3 ligase selection", f"e3_ligands={len(state.selected_e3_ligands)}"),
                "limitation": "No HPA/DepMap/ProteomicsDB/E3Net expression or context query is run.",
                "next_integration_needed": "Add tissue/cell-line-aware E3 expression and ligand source checks.",
            },
            {
                "step_name": "linker generation",
                "selected_tool_or_method": "Linker design using curated CSV plus rule-based enumeration",
                "tool_status": label("Linker design"),
                "output_type": "list[LinkerRecord]",
                "real_output_generated": bool(state.generated_linkers),
                "stub_or_heuristic": "local_demo" if state.generated_linkers else "not_connected",
                "evidence": evidence("Linker design", f"linkers={len(state.generated_linkers)}"),
                "limitation": "LinkInvent/DiffLinker/DeLinker are registered but not executed.",
                "next_integration_needed": "Connect generative linker tools and 3D constraints.",
            },
            {
                "step_name": "assembly",
                "selected_tool_or_method": "Assembly Agent using local dummy-atom/RDKit join when possible",
                "tool_status": f"{label('Assembly Agent')}; {label('RDKit')}",
                "output_type": "list[CandidateRecord]",
                "real_output_generated": bool(state.valid_candidates),
                "stub_or_heuristic": "local_demo" if state.valid_candidates else "not_connected",
                "evidence": evidence("Assembly Agent", f"valid_candidates={len(state.valid_candidates)}"),
                "limitation": "Named assembly strategies still share scaffold logic; no retrosynthetic route proof.",
                "next_integration_needed": "Use validated RDKit/RDChiral reactions with atom mapping and route checks.",
            },
            {
                "step_name": "DC50/Dmax prediction",
                "selected_tool_or_method": "Heuristic SynGlue-demo degradation predictor",
                "tool_status": label("DC50/Dmax prediction"),
                "output_type": "list[DegradationPrediction]",
                "real_output_generated": False,
                "stub_or_heuristic": "heuristic_stub",
                "evidence": evidence("DC50/Dmax prediction", f"degradation_predictions={len(state.degradation_predictions)}"),
                "limitation": "Predicted DC50/Dmax values are heuristic demo outputs, not trained model outputs.",
                "next_integration_needed": "Load validated SynGlue/DeepPROTACs/PROTAC-STAN/Chemprop models with uncertainty.",
            },
            {
                "step_name": "ADME/Tox prediction",
                "selected_tool_or_method": "ADMET backend orchestrator (local_model/api/descriptor_rule_based/heuristic_stub)",
                "tool_status": f"RDKit descriptors: {'executable' if status_for('RDKit')['executable'] else 'not executable'}; ADME/Tox backend={admet_backend}",
                "output_type": "list[ADMETPrediction]",
                "real_output_generated": admet_real,
                "stub_or_heuristic": admet_backend if admet_backends else "not_connected",
                "evidence": evidence("ADME/Tox skill", f"admet_records={len(state.admet_predictions)} backend={admet_backend}"),
                "limitation": "Descriptor-rule output is not ML endpoint prediction; API/model paths depend on config.",
                "next_integration_needed": "Add validated local ADMET models and configured external endpoints for full endpoint coverage.",
            },
            {
                "step_name": "novelty/IP",
                "selected_tool_or_method": "Novelty/IP check against local known-PROTAC set",
                "tool_status": label("Novelty/IP check"),
                "output_type": "list[NoveltyResult]",
                "real_output_generated": bool(state.novelty_results),
                "stub_or_heuristic": "local_demo" if state.novelty_results else "not_connected",
                "evidence": evidence("Novelty/IP check", f"novelty_records={len(state.novelty_results)}"),
                "limitation": "Patent/PubChem/ChEMBL/SureChEMBL/Lens novelty searches are not run.",
                "next_integration_needed": "Add exact/similarity/substructure searches across public and patent databases.",
            },
            {
                "step_name": "retrosynthesis",
                "selected_tool_or_method": "Synthesis planning / retrosynthesis feasibility filter",
                "tool_status": label("Synthesis planning"),
                "output_type": "synthetic_feasibility_score",
                "real_output_generated": False,
                "stub_or_heuristic": "heuristic_stub",
                "evidence": evidence("Synthesis planning", "route_planner_run=False"),
                "limitation": "AiZynthFinder/ASKCOS/IBM RXN/RAscore are not run.",
                "next_integration_needed": "Connect route planning and purchasable building-block checks.",
            },
            {
                "step_name": "ternary feasibility",
                "selected_tool_or_method": "Ternary complex modeling; GNINA docking registered but not run",
                "tool_status": f"{label('Ternary complex modeling')}; GNINA docking: {'executable' if docking_status['executable'] else 'registered but not executable'}",
                "output_type": "list[TernaryFeasibilityResult]",
                "real_output_generated": False,
                "stub_or_heuristic": "heuristic_stub" if state.ternary_feasibility_results else "not_connected",
                "evidence": evidence("Ternary complex modeling", f"ternary_records={len(state.ternary_feasibility_results)}; docking_run=False"),
                "limitation": "No docking engine, PRosettaC/HADDOCK/GNINA, or MD refinement is run.",
                "next_integration_needed": "Connect protein prep, docking/ternary modeling, and interface scoring.",
            },
            {
                "step_name": "ranking",
                "selected_tool_or_method": "Ranking skill using weighted deterministic score over current outputs",
                "tool_status": label("Ranking skill"),
                "output_type": "list[RankingResult]",
                "real_output_generated": bool(state.ranking_results),
                "stub_or_heuristic": "heuristic" if state.ranking_results else "not_connected",
                "evidence": evidence("Ranking skill", f"ranked={len(state.ranking_results)}"),
                "limitation": "Ranking inherits limitations of heuristic/local upstream outputs.",
                "next_integration_needed": "Add calibrated gates, uncertainty-aware ranking, and real model/tool provenance.",
            },
            {
                "step_name": "final report",
                "selected_tool_or_method": "Report generation from current WorkflowState",
                "tool_status": label("Report generation"),
                "output_type": "markdown/json/csv report artifacts",
                "real_output_generated": bool(state.report),
                "stub_or_heuristic": "real_report_over_mixed_quality_inputs" if state.report else "not_connected",
                "evidence": evidence("Report generation", f"report_chars={len(state.report)}"),
                "limitation": "Report is real as an artifact, but scientific claims remain limited by upstream status labels.",
                "next_integration_needed": "Keep report labels synchronized with executable tool provenance.",
            },
        ]
        return rows

    def generate_markdown_report(self, state: WorkflowState, top_n: int = 10) -> str:
        from synglue_agent.scientific_contract import (
            build_scientific_state,
            critique_scientific_state,
            select_next_actions,
        )

        state.pipeline_status = self.generate_pipeline_status_table(state)
        scientific_state = build_scientific_state(state)
        scientific_critique = critique_scientific_state(scientific_state)
        scientific_actions = select_next_actions(scientific_state)
        table = self.generate_candidate_table(
            state.final_ranked_candidates or state.valid_candidates[:top_n],
            state.ranking_results,
            state.degradation_predictions,
            state.admet_predictions,
            state.novelty_results,
            state.ternary_feasibility_results,
            state.cooperativity_predictions,
            state.hook_effect_predictions,
            state.e3_context_predictions,
        )
        lines = [
            "# SynGlue-Agent PROTAC Design Report",
            "",
            "SynGlue-Agent is a tool-augmented, memory-enabled, workflow-orchestrated agentic AI framework for component-aware PROTAC design.",
            "",
            "## Objective",
            f"- User request: {state.user_request}",
            f"- Target: {state.parsed_objective.target_name or 'unresolved'}",
            f"- E3 ligase: {state.parsed_objective.e3_ligase or 'CRBN and VHL comparison'}",
            f"- Candidate target count: {state.parsed_objective.candidate_count}",
            "",
            "## Workflow Summary",
            f"- Binders retrieved: {len(state.retrieved_binders)}",
            f"- Warheads selected: {len(state.selected_warheads)}",
            f"- E3 ligands selected: {len(state.selected_e3_ligands)}",
            f"- Linkers generated: {len(state.generated_linkers)}",
            f"- Construction attempts: {len(state.construction_attempts)}",
            f"- Valid or unverified candidates: {len(state.valid_candidates)}",
            f"- Cheap-filter survivors: {state.cheap_filter_summary.get('kept_candidates', len(state.valid_candidates))}/{state.cheap_filter_summary.get('input_candidates', len(state.valid_candidates))}",
            f"- Expensive-modeling finalists: {len(state.expensive_modeling_candidate_ids)}",
            f"- Evolved candidates: {len(state.evolved_candidates)}",
            "",
            "## Scientific Guardrails",
            "- Values are computational predictions, not experimental validation.",
            "- Model version is reported for degradation predictions.",
            "- Cooperativity alpha is an exploratory proxy unless backed by measured ternary binding or a calibrated alpha model.",
            "- Hook-effect risk is a concentration-occupancy proxy unless fitted to measured dose-response data.",
            "- Expensive ternary modeling is restricted to the selected finalist subset, not the full generated space.",
            "- PROTAC-DB evidence is used as a capped prior only; it is incomplete and absence from PROTAC-DB is not negative evidence.",
            "- Human medicinal chemistry and safety review is required before synthesis or wet-lab testing.",
        ]
        lines.extend([
            "",
            "## KNOW -> REASON -> DESIGN -> DISCOVER Contract",
            f"- Stopping state: {scientific_state.decision.stopping_state}",
            f"- Selected option: {scientific_state.decision.selected_option or 'none'}",
            f"- Next action: {scientific_state.decision.next_action}",
            f"- Critique status: {scientific_critique.status}",
            f"- Decision-critical missing data: {', '.join(scientific_state.unknown.get('decision_critical_questions', [])) or 'none recorded'}",
            f"- Selected dynamic action: {next((action.action_id for action in scientific_actions if action.selected), 'none')}",
            "- Evidence labels enforced: measured, curated, reported, computed, predicted, inferred, hypothetical, contradicted.",
        ])
        if state.active_learning_update.status != "not_run":
            lines.extend([
                "",
                "## Active Learning",
                f"- Feedback records added: {state.active_learning_update.feedback_count}",
                f"- Training rows available: {state.active_learning_update.training_rows}",
                f"- Retraining recommendation: {state.active_learning_update.retraining_recommendation or 'not available'}",
            ])
        if state.warnings:
            lines.extend(["", "## Warnings"])
            lines.extend(f"- {warning}" for warning in state.warnings)
        if table:
            lines.extend(["", "## Top Ranked Candidates", ""])
            headers = [
                "Rank",
                "Tier",
                "Target",
                "E3 ligase",
                "Warhead name",
                "Linker class",
                "Predicted DC50 nM",
                "Predicted Dmax %",
                "Predicted cooperativity alpha",
                "Hook risk",
                "E3 context score",
                "PROTAC-DB prior score",
                "PROTAC-DB prior scope",
                "hERG risk",
                "Novelty score",
                "Final priority score",
                "Warning flags",
            ]
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
            for row in table[:top_n]:
                lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
        lines.extend(["", "## Agent Workflow Table", ""])
        workflow_rows = self.generate_agent_workflow_table(state)
        headers = [
            "Agent type",
            "Selected tool",
            "Tool status",
            "Real output generated",
            "Integration note",
            "Data sources/tools",
            "Query parameters",
            "Quantitative outputs",
            "Processing time",
        ]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in workflow_rows:
            lines.append("| " + " | ".join(str(row.get(header, "")).replace("|", "/") for header in headers) + " |")
        lines.extend(["", "## Pipeline Status Labels", ""])
        status_headers = [
            "step_name",
            "selected_tool_or_method",
            "tool_status",
            "output_type",
            "real_output_generated",
            "stub_or_heuristic",
            "limitation",
            "next_integration_needed",
        ]
        lines.append("| " + " | ".join(status_headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(status_headers)) + " |")
        for row in state.pipeline_status:
            lines.append("| " + " | ".join(str(row.get(header, "")).replace("|", "/") for header in status_headers) + " |")
        return "\n".join(lines)

    def export_csv(self, rows: Sequence[dict[str, Any]], path: Path) -> Path:
        if not rows:
            path.write_text("", encoding="utf-8")
            return path
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def export_json(self, payload: Any, path: Path) -> Path:
        path.write_text(json.dumps(model_to_dict(payload), indent=2), encoding="utf-8")
        return path

    def write_workflow_memory(self, state: WorkflowState) -> dict[str, Any]:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        run_id = _stable_id("run", state.user_request, timestamp)
        path = WORKFLOW_LOG_DIR / f"{run_id}.json"
        payload = {
            "run_id": run_id,
            "timestamp": timestamp,
            "user_request": state.user_request,
            "target": state.parsed_objective.target_name,
            "final_candidate_ids": [candidate.candidate_id for candidate in state.final_ranked_candidates],
            "warnings": state.warnings,
            "errors": state.errors,
            "cell_line": state.parsed_objective.cell_line,
            "expression_overrides": state.parsed_objective.expression_overrides,
            "e3_context_predictions": model_to_dict(state.e3_context_predictions),
            "cooperativity_predictions": model_to_dict(state.cooperativity_predictions),
            "hook_effect_predictions": model_to_dict(state.hook_effect_predictions),
            "active_learning_update": model_to_dict(state.active_learning_update),
            "workflow_log": model_to_dict(state.workflow_log),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"run_id": run_id, "path": str(path)}

    def add_trace(self, state: WorkflowState, agent: str, thought: str, action: str, observation: str, elapsed: float) -> None:
        state.workflow_log.append(
            AgentTrace(
                agent=agent,
                thought=thought,
                action=action,
                observation=observation,
                processing_time_s=round(elapsed, 4),
            )
        )
