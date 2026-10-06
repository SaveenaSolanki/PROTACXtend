"""Target/E3-agnostic PROTAC component identity and assembly gates."""
from __future__ import annotations

from typing import Any

from protacxtend.backend.schemas import (
    BaseModel,
    CandidateRecord,
    E3LigandRecord,
    Field,
    LinkerRecord,
    WarheadRecord,
)

try:  # pragma: no cover - dependency availability is environment-specific.
    from rdkit import Chem
except Exception:  # pragma: no cover
    Chem = None


class SourceComponentRecord(BaseModel):
    component_id: str = ""
    role: str = ""
    name: str = ""
    smiles: str = ""
    target: str = ""
    e3_ligase: str = ""
    source_id: str = ""
    binding_evidence: list[dict[str, Any]] = Field(default_factory=list)
    exit_vector_atoms: list[int] = Field(default_factory=list)
    evidence_level: str = "missing"
    metadata: dict[str, Any] = Field(default_factory=dict)


class GateCheck(BaseModel):
    name: str = ""
    passed: bool = False
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)


class CandidateIdentityGateResult(BaseModel):
    candidate_id: str = ""
    all_required_passed: bool = False
    gates: dict[str, GateCheck] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    atom_mappings: dict[str, Any] = Field(default_factory=dict)
    evidence_level: str = "unverified"

    @property
    def by_gate(self) -> dict[str, GateCheck]:
        return self.gates


def _dump(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump())
    return dict(getattr(value, "__dict__", {}) or {})


def _norm(value: str | None) -> str:
    return (value or "").strip().upper()


def _is_placeholder_source(value: str | None) -> bool:
    text = (value or "").lower()
    return any(bit in text for bit in ("local_demo", "demo", "placeholder", "hypothetical", "user provided", "user_provided"))


def _mol(smiles: str | None):
    if Chem is None or not smiles:
        return None
    return Chem.MolFromSmiles(smiles)


def _canonical(smiles: str | None, *, dummy_to_h: bool = False, isomeric: bool = True) -> str:
    mol = _mol(smiles)
    if mol is None:
        return (smiles or "").strip()
    if dummy_to_h:
        rw = Chem.RWMol(mol)
        for atom in rw.GetAtoms():
            if atom.GetAtomicNum() == 0:
                atom.SetAtomicNum(1)
                atom.SetAtomMapNum(0)
                atom.SetIsotope(0)
        try:
            mol = rw.GetMol()
            Chem.SanitizeMol(mol)
        except Exception:
            return ""
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=isomeric)


def _dummy_maps(smiles: str | None) -> list[int]:
    mol = _mol(smiles)
    if mol is None:
        return []
    return sorted(a.GetAtomMapNum() for a in mol.GetAtoms() if a.GetAtomicNum() == 0)


def _has_exact_component_identity(candidate_smiles: str, source: SourceComponentRecord) -> bool:
    candidate = _canonical(candidate_smiles, dummy_to_h=True)
    source_smiles = _canonical(source.smiles, dummy_to_h=True)
    return bool(candidate and candidate == source_smiles)


def _substructure_match(product_smiles: str, component_smiles: str) -> list[int]:
    product = _mol(product_smiles)
    component = _mol(_canonical(component_smiles, dummy_to_h=True))
    if product is None or component is None:
        return []
    return list(product.GetSubstructMatch(component))


def _join_on_dummy(smiles_a: str, smiles_b: str, left_map: int, right_map: int) -> str | None:
    if Chem is None:
        return None
    mol_a = _mol(smiles_a)
    mol_b = _mol(smiles_b)
    if mol_a is None or mol_b is None:
        return None

    def find_dummy(mol, amap: int):
        for atom in mol.GetAtoms():
            if atom.GetAtomicNum() == 0 and atom.GetAtomMapNum() == amap:
                return atom.GetIdx()
        return None

    da = find_dummy(mol_a, left_map)
    db = find_dummy(mol_b, right_map)
    if da is None or db is None:
        return None
    na = [a.GetIdx() for a in mol_a.GetAtomWithIdx(da).GetNeighbors()]
    nb = [a.GetIdx() for a in mol_b.GetAtomWithIdx(db).GetNeighbors()]
    if not na or not nb:
        return None
    combo = Chem.CombineMols(mol_a, mol_b)
    rw = Chem.RWMol(combo)
    offset = mol_a.GetNumAtoms()
    rw.AddBond(na[0], offset + nb[0], Chem.BondType.SINGLE)
    for idx in sorted([da, offset + db], reverse=True):
        rw.RemoveAtom(idx)
    out = rw.GetMol()
    Chem.SanitizeMol(out)
    return Chem.MolToSmiles(out, canonical=True, isomericSmiles=True)


def _assemble(warhead: str, linker: str, e3: str) -> str | None:
    left = _join_on_dummy(warhead, linker, 1, 1)
    if not left:
        return None
    return _join_on_dummy(left, e3, 2, 1)


def _source_record(raw: Any) -> SourceComponentRecord | None:
    if raw is None:
        return None
    if isinstance(raw, SourceComponentRecord):
        return raw
    data = _dump(raw)
    if not data:
        return None
    return SourceComponentRecord(**data)


def source_record_from_warhead(warhead: WarheadRecord) -> SourceComponentRecord:
    prov = dict(warhead.provenance or {})
    source_id = prov.get("source_id") or prov.get("doi") or prov.get("article_doi") or warhead.source or ""
    evidence = []
    if not _is_placeholder_source(source_id) and (warhead.potency_nM is not None or prov.get("activity_nM") or prov.get("verified")):
        evidence.append({"source_id": source_id, "assay": prov.get("activity_type") or "binding", "value_nM": warhead.potency_nM or prov.get("activity_nM")})
    return SourceComponentRecord(
        component_id=prov.get("component_id") or warhead.name,
        role=prov.get("role") or "target_binder",
        name=warhead.name,
        smiles=warhead.smiles,
        target=warhead.target,
        source_id=source_id,
        binding_evidence=prov.get("binding_evidence") or evidence,
        exit_vector_atoms=[prov.get("attachment_atom_map") or 1] if "[*" in (warhead.smiles or "") else [],
        evidence_level="binding_assay" if (prov.get("binding_evidence") or evidence) else "missing",
        metadata=prov,
    )


def source_record_from_e3_ligand(ligand: E3LigandRecord) -> SourceComponentRecord:
    prov = dict(ligand.provenance or {})
    source_id = prov.get("source_id") or prov.get("article_doi") or ligand.source or ""
    evidence = []
    if not _is_placeholder_source(source_id) and (prov.get("activity_nM") or prov.get("verified") or prov.get("binding_evidence")):
        evidence.append({"source_id": source_id, "assay": "E3 binding", "value_nM": prov.get("activity_nM")})
    return SourceComponentRecord(
        component_id=prov.get("component_id") or ligand.name,
        role=prov.get("role") or "e3_ligand",
        name=ligand.name,
        smiles=ligand.smiles,
        e3_ligase=ligand.e3_ligase,
        source_id=source_id,
        binding_evidence=prov.get("binding_evidence") or evidence,
        exit_vector_atoms=[prov.get("attachment_atom_map") or 1] if "[*" in (ligand.smiles or "") else [],
        evidence_level="binding_assay" if (prov.get("binding_evidence") or evidence) else "missing",
        metadata=prov,
    )


def source_record_from_linker(linker: LinkerRecord) -> SourceComponentRecord:
    prov = dict(linker.provenance or {})
    return SourceComponentRecord(
        component_id=prov.get("component_id") or linker.name,
        role="linker",
        name=linker.name,
        smiles=linker.smiles,
        source_id=prov.get("source_id") or linker.source or linker.name,
        exit_vector_atoms=[1, 2] if {1, 2} <= set(_dummy_maps(linker.smiles)) else [],
        evidence_level="curated_exit_vector" if {1, 2} <= set(_dummy_maps(linker.smiles)) else "missing",
        metadata=prov,
    )


class CandidateIdentityAndAssemblyGate:
    """Fail-closed identity/provenance gate shared by design and scoring paths."""

    REQUIRED = (
        "parse_valid",
        "source_backed_target_binder",
        "source_backed_e3_ligand",
        "supported_exit_vectors",
        "component_retention",
        "whole_molecule_connectivity",
        "evidence_level",
    )

    def evaluate(self, candidate: CandidateRecord) -> CandidateIdentityGateResult:
        cprov = dict(candidate.provenance or {})
        sources = cprov.get("source_components") or {}
        target_src = _source_record(sources.get("target_binder") or sources.get("warhead"))
        e3_src = _source_record(sources.get("e3_ligand"))
        linker_src = _source_record(sources.get("linker"))
        gates: dict[str, GateCheck] = {}

        def add(name: str, passed: bool, reason: str, *, evidence_ids: list[str] | None = None, detail: dict[str, Any] | None = None):
            gates[name] = GateCheck(name=name, passed=bool(passed), reason=reason, evidence_ids=evidence_ids or [], detail=detail or {})

        product_mol = _mol(candidate.full_protac_smiles)
        add("parse_valid", product_mol is not None, "RDKit parsed whole molecule" if product_mol is not None else "whole-molecule SMILES did not parse")

        self._target_gate(candidate, target_src, add)
        self._e3_gate(candidate, e3_src, add)

        wh_maps = _dummy_maps(candidate.warhead_smiles)
        e3_maps = _dummy_maps(candidate.e3_ligand_smiles)
        linker_maps = _dummy_maps(candidate.linker_smiles)
        supported_vectors = (
            1 in wh_maps
            and 1 in e3_maps
            and {1, 2} <= set(linker_maps)
            and bool(target_src and target_src.exit_vector_atoms)
            and bool(e3_src and e3_src.exit_vector_atoms)
            and bool(linker_src and {1, 2} <= set(linker_src.exit_vector_atoms or []))
        )
        add(
            "supported_exit_vectors",
            supported_vectors,
            "component/linker atom maps are source-supported" if supported_vectors else "missing or unsupported attachment atom maps",
            detail={"warhead_maps": wh_maps, "e3_maps": e3_maps, "linker_maps": linker_maps},
        )

        target_match = _substructure_match(candidate.full_protac_smiles, candidate.warhead_smiles)
        e3_match = _substructure_match(candidate.full_protac_smiles, candidate.e3_ligand_smiles)
        retention = bool(target_match and e3_match)
        add(
            "component_retention",
            retention,
            "source components retained in whole molecule" if retention else "one or more source components are not retained in product",
            detail={"target_binder_product_atoms": target_match, "e3_ligand_product_atoms": e3_match},
        )

        assembled = _assemble(candidate.warhead_smiles, candidate.linker_smiles, candidate.e3_ligand_smiles)
        connectivity = bool(assembled and _canonical(assembled, isomeric=False) == _canonical(candidate.full_protac_smiles, isomeric=False))
        add(
            "whole_molecule_connectivity",
            connectivity,
            "assembled components reproduce whole molecule" if connectivity else "recorded whole molecule does not match atom-mapped assembly",
            detail={"assembled_smiles": assembled or ""},
        )

        evidence_ok = all(gates[name].passed for name in ("source_backed_target_binder", "source_backed_e3_ligand", "supported_exit_vectors"))
        add(
            "evidence_level",
            evidence_ok,
            "exact component binding evidence and exit-vector evidence present" if evidence_ok else "identity or exit-vector evidence is missing/contradictory",
        )

        reasons = [f"{name}: {gate.reason}" for name, gate in gates.items() if not gate.passed]
        all_passed = all(gates.get(name, GateCheck()).passed for name in self.REQUIRED)
        return CandidateIdentityGateResult(
            candidate_id=candidate.candidate_id,
            all_required_passed=all_passed,
            gates=gates,
            reasons=reasons,
            atom_mappings={
                "target_binder_product_atoms": target_match,
                "e3_ligand_product_atoms": e3_match,
                "attachment_maps": {"target_binder": wh_maps, "e3_ligand": e3_maps, "linker": linker_maps},
            },
            evidence_level="source_backed_identity" if all_passed else "binding_unverified",
        )

    def _target_gate(self, candidate: CandidateRecord, source: SourceComponentRecord | None, add) -> None:
        if source is None:
            add("source_backed_target_binder", False, "missing source component record")
            return
        if source.role not in {"target_binder", "warhead"}:
            add("source_backed_target_binder", False, f"source component role {source.role!r} is not target_binder/warhead")
            return
        if source.target and _norm(source.target) != _norm(candidate.target):
            add("source_backed_target_binder", False, f"target mismatch: source={source.target} candidate={candidate.target}")
            return
        if not _has_exact_component_identity(candidate.warhead_smiles, source):
            add("source_backed_target_binder", False, "candidate warhead is not exact source target-binder structure")
            return
        if not source.source_id or not source.binding_evidence or _is_placeholder_source(source.source_id):
            add("source_backed_target_binder", False, "missing explicit target-binding source evidence")
            return
        add("source_backed_target_binder", True, "exact source-backed target binder", evidence_ids=[source.source_id])

    def _e3_gate(self, candidate: CandidateRecord, source: SourceComponentRecord | None, add) -> None:
        if source is None:
            add("source_backed_e3_ligand", False, "missing source E3 ligand record")
            return
        if source.role != "e3_ligand":
            add("source_backed_e3_ligand", False, f"source component role {source.role!r} is not e3_ligand")
            return
        if source.e3_ligase and _norm(source.e3_ligase) != _norm(candidate.e3_ligase):
            add("source_backed_e3_ligand", False, f"E3 mismatch: source={source.e3_ligase} candidate={candidate.e3_ligase}")
            return
        if not _has_exact_component_identity(candidate.e3_ligand_smiles, source):
            add("source_backed_e3_ligand", False, "candidate E3 ligand is not exact source E3-binding structure")
            return
        if not source.source_id or not source.binding_evidence or _is_placeholder_source(source.source_id):
            add("source_backed_e3_ligand", False, "missing explicit E3-ligand binding source evidence")
            return
        add("source_backed_e3_ligand", True, "exact source-backed E3 ligand", evidence_ids=[source.source_id])


def evaluate_candidate_identity(candidate: CandidateRecord) -> CandidateIdentityGateResult:
    return CandidateIdentityAndAssemblyGate().evaluate(candidate)


def gate_payload(result: CandidateIdentityGateResult) -> dict[str, Any]:
    return {
        "schema": "candidate_identity_and_assembly_gate.v1",
        "candidate_id": result.candidate_id,
        "all_required_passed": result.all_required_passed,
        "evidence_level": result.evidence_level,
        "reasons": list(result.reasons),
        "atom_mappings": result.atom_mappings,
        "gates": {name: check.model_dump() for name, check in result.gates.items()},
    }


def candidate_passes_identity_gate(candidate: CandidateRecord) -> bool:
    gate = (candidate.provenance or {}).get("identity_assembly_gate") or {}
    return bool(gate.get("all_required_passed"))
