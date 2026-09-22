"""Allocation generator for TPD-HEADTOHEAD/1.0.0 (Sections 5, 6, 7).

Produces the **design manifest** for 500 tasks: task ids, domain, difficulty,
partition, the 100-task TPD stress tag, and required/optional/irrelevant tool
declarations. It intentionally does **not** author scientific ground truth —
every task is emitted with ``ground_truth.status = REQUIRES_AUTHORING`` so the
benchmark cannot be mistaken for a validated instrument.

Run:  python -m tpdeval.allocation
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

from tpdeval.taxonomy import (
    BENCHMARK_ID, BENCHMARK_DATE, DOMAINS, DIFFICULTIES, DIFFICULTY_DOMAIN_OK,
    PARTITIONS, CONTROLLED_DOMAIN_WEIGHTS, E2E_DOMAIN_WEIGHTS,
    TEMPORAL_DOMAIN_WEIGHTS, TPD_STRESS_SUBSET, validate_taxonomy,
)
from tpdeval.taskmodel import GroundTruth, TaskRecord, ToolSpec

OUT_DIR = Path(__file__).resolve().parent / "config"
DOMAIN_CODE: Dict[str, str] = {d: "".join(w[:2] for w in d.split("_"))[:4].upper()
                               for d in DOMAINS}

# ---------------------------------------------------------------------------
# Curated TPD system catalogue used to give tasks concrete targets/E3s.
# Accessions are curated public identifiers and are flagged PROVISIONAL: the
# authored ground truth for each task must re-verify them at T0.
# ---------------------------------------------------------------------------
TARGETS = [
    ("BRD4", "O60885"), ("BRD9", "Q9H8M2"), ("SMARCA2", "P51531"),
    ("SMARCA4", "P51532"), ("BTK", "Q06187"), ("AR", "P10275"),
    ("ESR1", "P03372"), ("KRAS", "P01116"), ("EGFR", "P00533"),
    ("BCL6", "P41182"), ("IRAK4", "Q9NWZ3"), ("TBK1", "Q9UHD2"),
    ("SHP2", "Q06124"), ("STAT3", "P40763"), ("MDM2", "Q00987"),
    ("CDK4", "P11802"), ("CDK6", "Q00534"), ("PIK3CA", "P42336"),
    ("BCL2", "P10415"), ("MCL1", "Q07820"), ("WEE1", "P30291"),
    ("AURKA", "O14965"), ("PLK1", "P53350"), ("TRIM24", "O15164"),
    ("GSPT1", "P15170"), ("PTPN11", "Q06124"), ("NRAS", "P01111"),
    ("CDK9", "P50750"), ("LRRK2", "Q5S007"), ("HPK1", "Q92918"),
]
E3S = [
    ("CRBN", "Q96SW2"), ("VHL", "P40337"), ("MDM2", "Q00987"),
    ("cIAP1", "Q13490"), ("XIAP", "P98170"), ("DCAF1", "Q9Y4B6"),
    ("DCAF15", "Q66K64"), ("DCAF16", "Q9NXF7"), ("FBXO32", "Q969P5"),
    ("SKP2", "Q13309"), ("KEAP1", "Q14145"), ("RNF114", "Q9Y508"),
    ("RNF4", "P78317"), ("TRIM21", "P19474"), ("PARKIN", "O60260"),
    ("UBR5", "O95071"), ("ARIH1", "Q9Y4X5"), ("CUL5", "Q93034"),
]
FRAMEWORKS = ["CRBN-lenalidomide", "VHL-VH032", "MDM2-nutlin", "IAP-SMAC-mimetic",
              "DCAF15-sulfonamide", "KEAP1-NRF2", "RNF114-nimbolide", "TRIM21-antibody-mimetic"]

# Matched-tool catalog: the *same* tools offered to every system in Condition B.
MATCHED_TOOLS = [
    "uniprot", "chembl", "pubchem", "bindingdb", "rcsb_pdb", "protacdb",
    "europepmc", "pubmed", "openalex", "crossref", "hpa", "depmap",
    "rdkit_descriptors", "rdkit_smiles", "docking_vina", "ternary_model",
    "cooperativity_model", "hook_model", "lysine_ubiquitination",
    "degradation_model", "admet_tool", "retrosynthesis", "cell_context",
    "e3_expression", "safety_signals",
]

# Required tools per domain (Section 8). Optional = 2x required, irrelevant = rest.
DOMAIN_REQUIRED_TOOLS: Dict[str, List[str]] = {
    "target_biology": ["uniprot", "europepmc"],
    "target_validation": ["uniprot", "depmap", "europepmc"],
    "tpd_tractability": ["uniprot", "depmap", "e3_expression"],
    "e3_selection": ["e3_expression", "uniprot", "europepmc"],
    "warhead_discovery": ["chembl", "bindingdb", "rcsb_pdb"],
    "linker_protac_design": ["rdkit_smiles", "rdkit_descriptors", "protacdb"],
    "binary_structure": ["rcsb_pdb", "docking_vina"],
    "ternary_complex": ["ternary_model", "rcsb_pdb", "lysine_ubiquitination"],
    "degradation": ["degradation_model", "cooperativity_model", "hook_model"],
    "adme_pk": ["admet_tool", "rdkit_descriptors"],
    "safety": ["safety_signals", "uniprot"],
    "resistance": ["e3_expression", "degradation_model", "europepmc"],
    "biomarker": ["depmap", "hpa", "europepmc"],
    "combination": ["chembl", "depmap", "europepmc"],
    "experimental_design": ["rdkit_descriptors", "degradation_model"],
    "failure_analysis": ["degradation_model", "cooperativity_model", "hook_model"],
}

PARTITION_PREFIX = {"controlled": "C", "end_to_end": "E", "temporal": "T"}


def _difficulty_plan(domain: str, n: int) -> List[str]:
    """Deterministically assign L1..L7 with L1/L6 emphasis by partition slot."""
    ok = DIFFICULTY_DOMAIN_OK
    allowed = [d for d in DIFFICULTIES if domain in ok[d]]
    if not allowed:
        allowed = list(DIFFICULTIES)
    plan: List[str] = []
    # Prefer a spread weighted toward the harder mechanistic levels.
    weights = {"L1": 1, "L2": 1, "L3": 2, "L4": 2, "L5": 3, "L6": 3, "L7": 1}
    pool = [d for d in allowed for _ in range(weights.get(d, 1))]
    for i in range(n):
        plan.append(pool[i % len(pool)])
    return plan


def _tool_spec(domain: str, gi: int) -> ToolSpec:
    required = list(DOMAIN_REQUIRED_TOOLS.get(domain, []))
    optional = [t for t in MATCHED_TOOLS
                if t not in required and ((hash((domain, t)) >> (gi % 8)) & 1)]
    optional = optional[: max(2, len(required))]
    irrelevant = [t for t in MATCHED_TOOLS
                  if t not in required and t not in optional]
    return ToolSpec(required=required, optional=optional, irrelevant=irrelevant)


def _make_task(domain: str, difficulty: str, partition: str, seq: int,
               stress: bool) -> TaskRecord:
    gi = seq
    gene, _up = TARGETS[gi % len(TARGETS)]
    e3, _e3up = E3S[gi % len(E3S)]
    fw = FRAMEWORKS[gi % len(FRAMEWORKS)]
    code = DOMAIN_CODE[domain]
    part = PARTITION_PREFIX[partition]
    task_id = f"TD-{part}-{code}-{difficulty}-{seq:03d}"
    is_tpd = domain in ("e3_selection", "ternary_complex", "degradation",
                        "linker_protac_design", "failure_analysis")
    q = {
        "controlled": (
            f"[{domain} | {difficulty}] Controlled capability task for target {gene} "
            f"(PROVISIONAL UniProt {_up}): produce the objectively scorable "
            f"deliverable defined by this task's authored ground truth."),
        "end_to_end": (
            f"[{domain} | {difficulty}] End-to-end discovery: develop a targeted "
            f"protein degradation strategy for {gene} without being given the E3, "
            f"warhead, linker, structure, tools or experiment."),
        "temporal": (
            f"[{domain} | {difficulty}] Blinded temporal challenge for {gene}: at "
            f"T0={BENCHMARK_DATE} produce a prospective prediction to be compared "
            f"against evidence emerging after T0."),
    }[partition]
    tr = TaskRecord(
        task_id=task_id,
        benchmark_domain=domain,
        difficulty=difficulty,
        partition=partition,
        title=f"{domain} {difficulty} #{seq:03d} ({gene})",
        target=gene,
        disease_context="REQUIRES_AUTHORING",
        e3_context=(e3 if is_tpd or domain in ("e3_selection", "ternary_complex") else None),
        question=q,
        available_evidence=[],
        structures=[],
        molecules=[],
        permitted_tools=list(MATCHED_TOOLS),
        tool_spec=_tool_spec(domain, gi),
        expected_conclusion=None,
        accepted_alternatives=[],
        required_evidence=[],
        reference_provenance=[{
            "target_accession": "PROVISIONAL",
            "framework": fw,
            "note": "must be re-verified at authoring time; never used as ground truth",
        }],
        tpd_stress_subset=bool(stress),
        temporal_cutoff=(BENCHMARK_DATE if partition == "temporal" else None),
        ground_truth=GroundTruth(status="REQUIRES_AUTHORING"),
    )
    return tr


def build_allocation() -> List[TaskRecord]:
    tasks: List[TaskRecord] = []
    # stress membership: first N controlled tasks of each stress domain by seq
    stress_seen: Dict[str, int] = defaultdict(int)
    seq = 0
    for partition, weights in (
        ("controlled", CONTROLLED_DOMAIN_WEIGHTS),
        ("end_to_end", E2E_DOMAIN_WEIGHTS),
        ("temporal", TEMPORAL_DOMAIN_WEIGHTS),
    ):
        for domain in DOMAINS:
            n = weights.get(domain, 0)
            plan = _difficulty_plan(domain, n)
            for i in range(n):
                stress = False
                if partition == "controlled" and domain in TPD_STRESS_SUBSET:
                    if stress_seen[domain] < TPD_STRESS_SUBSET[domain]:
                        stress = True
                        stress_seen[domain] += 1
                tasks.append(_make_task(domain, plan[i], partition, seq, stress))
                seq += 1
    return tasks


def manifest_summary(tasks: List[TaskRecord]) -> Dict[str, object]:
    return {
        "benchmark": BENCHMARK_ID,
        "generated": BENCHMARK_DATE,
        "total": len(tasks),
        "by_partition": dict(Counter(t.partition for t in tasks)),
        "by_domain": dict(Counter(t.benchmark_domain for t in tasks)),
        "by_difficulty": dict(Counter(t.difficulty for t in tasks)),
        "by_domain_difficulty": {
            f"{d}|{diff}": c for (d, diff), c in
            sorted(Counter((t.benchmark_domain, t.difficulty) for t in tasks).items())
        },
        "tpd_stress_subset": sum(1 for t in tasks if t.tpd_stress_subset),
        "scorable_tasks": sum(1 for t in tasks if t.ground_truth.is_scorable()),
        "ground_truth_status": dict(Counter(t.ground_truth.status for t in tasks)),
        "taxonomy": validate_taxonomy(),
    }


def write_manifest(path: Path | None = None) -> Dict[str, object]:
    tasks = build_allocation()
    summary = manifest_summary(tasks)
    payload = {
        "summary": summary,
        "tasks": [t.to_dict() for t in tasks],
    }
    out = path or (OUT_DIR / "allocation_500.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    return summary


if __name__ == "__main__":
    s = write_manifest()
    print(json.dumps(s, indent=2))
    print("\nWROTE", OUT_DIR / "allocation_500.json")
