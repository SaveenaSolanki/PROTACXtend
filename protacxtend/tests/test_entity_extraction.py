"""Validation tests for the natural-language entity-extraction front door.

These tests enforce the P0-A acceptance criterion: target-gene extraction must
reach at least 98% on the authored parser validation set (>=100 prompts).  They
also pin the required :class:`ExtractedEntities` output schema and the
integration with :meth:`ProtacDesignToolbox.parse_user_request`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from protacxtend.backend.schemas import ExtractedEntities, ParsedObjective
from protacxtend.nlp.entity_extraction import (
    GENE_SYMBOLS,
    extract_entities,
    normalize_gene_symbol,
)
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

VALIDATION_SET = (
    Path(__file__).resolve().parents[1] / "data" / "parser_validation_set.json"
)

REQUIRED_SCHEMA_KEYS = {
    "intent",
    "target_gene",
    "disease_context",
    "requested_modality",
    "e3_preference",
    "molecule_constraints",
    "task_type",
    "confidence",
}

TARGET_ACCURACY_THRESHOLD = 0.98


def _load_validation_prompts() -> list[dict]:
    data = json.loads(VALIDATION_SET.read_text(encoding="utf-8"))
    return data["prompts"]


def test_validation_set_has_at_least_100_prompts() -> None:
    assert len(_load_validation_prompts()) >= 100


def test_target_extraction_accuracy_at_least_98_percent() -> None:
    """P0-A exit criterion: >=98% correct target extraction."""
    rows = _load_validation_prompts()
    correct = 0
    failures: list[str] = []
    for row in rows:
        result = extract_entities(row["prompt"])
        if result.target_gene == row["target_gene"]:
            correct += 1
        else:
            failures.append(
                f"{row['id']}: {row['prompt']!r} expected "
                f"{row['target_gene']!r} got {result.target_gene!r}"
            )
    accuracy = correct / len(rows)
    assert accuracy >= TARGET_ACCURACY_THRESHOLD, (
        f"target extraction accuracy {accuracy:.3f} < "
        f"{TARGET_ACCURACY_THRESHOLD:.2f}; failures:\n" + "\n".join(failures)
    )


def test_secondary_fields_where_specified() -> None:
    """E3 preference, disease context and task type must match when annotated."""
    rows = _load_validation_prompts()
    for row in rows:
        result = extract_entities(row["prompt"])
        if "e3_preference" in row:
            assert result.e3_preference == row["e3_preference"], row["id"]
        if "disease_context" in row:
            assert result.disease_context == row["disease_context"], row["id"]
        if "task_type" in row:
            assert result.task_type == row["task_type"], row["id"]


def test_extracted_entities_schema_is_complete() -> None:
    record = extract_entities("Design a VHL PROTAC against BRD4")
    dumped = record.model_dump()
    assert REQUIRED_SCHEMA_KEYS.issubset(dumped.keys())
    assert isinstance(dumped["target_gene"], str)
    assert isinstance(dumped["molecule_constraints"], dict)
    assert 0.0 <= dumped["confidence"] <= 1.0


def test_parsed_objective_exposes_entity_schema() -> None:
    objective = ParsedObjective(target_name="BRD4")
    dumped = objective.model_dump()
    for key in ("intent", "requested_modality", "task_type", "molecule_constraints"):
        assert key in dumped
    assert isinstance(objective.entities, (ExtractedEntities, type(None)))


@pytest.mark.parametrize(
    "prompt, target, e3",
    [
        ("degrade BRD4", "BRD4", None),
        ("Can BRD4 be degraded?", "BRD4", None),
        ("Design a VHL PROTAC against BRD4", "BRD4", "VHL"),
        ("Is SMARCA2 tractable in SMARCA4-deficient NSCLC?", "SMARCA2", None),
        ("Find an E3 for STAT3", "STAT3", None),
        ("Why did this CRBN degrader fail?", "", "CRBN"),
        ("Can we use VHL instead of CRBN?", "", "VHL"),
        ("Design a PROTAC for mutant KRAS G12D", "KRAS", None),
    ],
)
def test_acceptance_prompts(prompt: str, target: str, e3: str | None) -> None:
    result = extract_entities(prompt)
    assert result.target_gene == target
    assert result.e3_preference == e3


def test_positional_regression_verbs_are_never_targets() -> None:
    """The original bug: verbs were returned as targets."""
    for prompt in ["degrade BRD4", "Can BRD4 be degraded?", "design SMARCA2 degraders"]:
        assert extract_entities(prompt).target_gene not in {"DEGRADE", "CAN", "DESIGN"}


def test_mutation_codes_are_not_targets() -> None:
    result = extract_entities("Design a PROTAC for mutant KRAS G12D")
    assert result.target_gene == "KRAS"
    assert "G12D" not in result.molecule_constraints.get("alternate_target_candidates", [])


def test_pdb_ids_are_not_targets() -> None:
    """Regression: "5T35" was parsed as target "T35"; "PDB" as a gene."""
    assert extract_entities("what is the structure of 5T35").target_gene == ""
    assert extract_entities("use PDB 6HAX for the ternary complex").target_gene == ""
    # a real target in the same sentence is still found
    assert extract_entities("degrade BRD4 with the 5T35 structure").target_gene == "BRD4"
    assert extract_entities("use PDB 6HAX to degrade SMARCA2").target_gene == "SMARCA2"


def test_unknown_gene_symbol_is_extracted_by_context() -> None:
    result = extract_entities("degrade FOXP1 in lymphoma")
    assert result.target_gene == "FOXP1"


def test_protein_alias_resolution() -> None:
    assert extract_entities("degrade the androgen receptor").target_gene == "AR"
    assert extract_entities("degrade p53").target_gene == "TP53"
    assert extract_entities("degrade HER2").target_gene == "ERBB2"


def test_toolbox_integration_populates_parsed_objective() -> None:
    toolbox = ProtacDesignToolbox()
    objective = toolbox.parse_user_request(
        "Design a VHL PROTAC against BRD4 with low hERG risk."
    )
    assert objective.target_name == "BRD4"
    assert objective.e3_ligase == "VHL"
    assert objective.intent == "design"
    assert objective.task_type == "protac_design"
    assert objective.requested_modality == "PROTAC"
    assert objective.extraction_confidence > 0.5
    assert objective.entities is not None
    assert objective.entities.target_gene == "BRD4"
    assert objective.admet_constraints["avoid_hERG"] is True


def test_gene_vocabulary_is_non_trivial() -> None:
    assert "BRD4" in GENE_SYMBOLS
    assert "KRAS" in GENE_SYMBOLS
    assert normalize_gene_symbol(" brd4 ") == "BRD4"
