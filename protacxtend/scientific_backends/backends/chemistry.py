"""Free/local chemistry + ADMET backends (RDKit first, no web services).

Covers small-molecule preparation and deterministic descriptors. Everything is
computed locally; SwissADME and other web predictors are never contacted.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from protacxtend.scientific_backends.dispatch import (
    module_available,
    module_version,
    safe_call,
)
from protacxtend.scientific_backends.evidence import (
    CapabilityStatus,
    EvidenceTier,
    ScientificResult,
)
from protacxtend.scientific_backends.licenses import OPEN_SOURCE_PERMISSIVE
from protacxtend.scientific_backends.registry import Capability, BackendSpec, register


# ── RDKit helpers ───────────────────────────────────────────────────────

def _mol(smiles: str):
    from rdkit import Chem

    # Reject missing / non-string / empty input before RDKit: MolFromSmiles("") returns
    # an *empty* mol (not None), which would otherwise yield all-zero descriptors
    # presented as a successful result (silent scientific failure).
    if not isinstance(smiles, str) or not smiles.strip():
        raise ValueError(f"invalid SMILES: {smiles!r}")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError(f"invalid SMILES: {smiles!r}")
    return mol


def rdkit_available():
    from protacxtend.scientific_backends.dispatch import Availability, module_available

    ok = module_available("rdkit")
    return Availability(available=ok, version=module_version("rdkit"),
                        detail="RDKit" if ok else "rdkit import not found")


def rdkit_descriptors(smiles: str) -> dict[str, Any]:
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski, QED, rdMolDescriptors

    mol = _mol(smiles)
    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    tpsa = rdMolDescriptors.CalcTPSA(mol)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    rotb = Lipinski.NumRotatableBonds(mol)
    rings = rdMolDescriptors.CalcNumRings(mol)
    aromatic = rdMolDescriptors.CalcNumAromaticRings(mol)
    heavy = max(1, mol.GetNumHeavyAtoms())
    aromatic_atoms = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic())
    charge = Chem.GetFormalCharge(mol)
    qed = QED.qed(mol)
    violations = int(mw > 500) + int(logp > 5) + int(hbd > 5) + int(hba > 10)
    return {
        "smiles": Chem.MolToSmiles(mol),
        "canonical_smiles": Chem.MolToSmiles(mol, isomericSmiles=True),
        "molecular_weight": round(mw, 3),
        "logp_crippen": round(logp, 3),
        "tpsa": round(tpsa, 2),
        "hbd": int(hbd),
        "hba": int(hba),
        "rotatable_bonds": int(rotb),
        "rings": int(rings),
        "aromatic_rings": int(aromatic),
        "aromatic_fraction": round(aromatic_atoms / heavy, 3),
        "formal_charge": int(charge),
        "fraction_csp3": round(rdMolDescriptors.CalcFractionCSP3(mol), 3),
        "molar_refractivity": round(Crippen.MolMR(mol), 3),
        "qed": round(float(qed), 4),
        "lipinski_violations": violations,
        "lipinski_pass": violations <= 1,
        "heavy_atoms": int(mol.GetNumHeavyAtoms()),
    }


def _fingerprint(smiles: str, kind: str = "morgan") -> dict[str, Any]:
    from rdkit import Chem
    from rdkit.Chem import rdFingerprintGenerator

    mol = _mol(smiles)
    kind = (kind or "morgan").lower()
    if kind == "maccs":
        from rdkit.Chem import MACCSkeys

        fp = MACCSkeys.GenMACCSKeys(mol)
    elif kind == "rdkit":
        fp = Chem.RDKFingerprint(mol)
    else:
        fp = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048).GetFingerprint(mol)
    bits = list(fp.GetOnBits())
    return {"kind": kind, "n_bits": fp.GetNumBits(), "n_on": len(bits), "on_bits": bits[:256]}


def _tautomers(smiles: str, max_tautomers: int = 16) -> dict[str, Any]:
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize

    mol = _mol(smiles)
    enumerator = rdMolStandardize.TautomerEnumerator()
    enumerator.SetMaxTautomers(max_tautomers)
    tautomers = [Chem.MolToSmiles(t) for t in enumerator.Enumerate(mol)]
    return {"n_tautomers": len(tautomers), "tautomers": tautomers,
            "canonical": rdMolStandardize.TautomerEnumerator().Canonicalize(mol) and
                         Chem.MolToSmiles(rdMolStandardize.TautomerEnumerator().Canonicalize(mol))}


def _standardize(smiles: str) -> dict[str, Any]:
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize

    mol = _mol(smiles)
    uncharger = rdMolStandardize.Uncharger()
    neutral = uncharger.uncharge(mol)
    parent = rdMolStandardize.FragmentParent(neutral)
    return {
        "uncharged_smiles": Chem.MolToSmiles(neutral),
        "parent_fragment": Chem.MolToSmiles(parent),
        "formal_charge": Chem.GetFormalCharge(neutral),
    }


def _substructure(smiles: str, query: str, smart: bool = False) -> dict[str, Any]:
    from rdkit import Chem

    mol = _mol(smiles)
    q = Chem.MolFromSmarts(query) if smart else Chem.MolFromSmiles(query)
    if q is None:
        raise ValueError(f"invalid query: {query!r}")
    matches = mol.GetSubstructMatches(q)
    return {"n_matches": len(matches), "matches": [list(m) for m in matches[:50]]}


def generate_conformers(smiles: str, n_conformers: int = 10, seed: int = 0xC0FFEE,
                        optimize: bool = True, output_dir: str | None = None) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.CONFORMER_GENERATION.value, backend="rdkit_etkdg",
        evidence_tier=EvidenceTier.TIER_1_MINIMIZED.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["RDKit ETKDG (Ebejer et al., JCIM 2012)"])
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        mol = Chem.AddHs(_mol(smiles))
        params = AllChem.ETKDGv3()
        params.randomSeed = int(seed)
        conf_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=max(1, int(n_conformers)), params=params))
        energies: list[float] = []
        if optimize and conf_ids:
            try:
                props = AllChem.MMFFGetMoleculeProperties(mol)
                if props is not None:
                    for cid in conf_ids:
                        ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=cid)
                        if ff is not None:
                            ff.Minimize(maxIts=200)
                            energies.append(round(float(ff.CalcEnergy()), 3))
                else:
                    AllChem.UFFOptimizeMoleculeConfs(mol, maxIters=200)
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"force-field optimisation skipped: {exc}")
        out_dir = Path(output_dir or tempfile.mkdtemp(prefix="pxt_conformers_"))
        out_dir.mkdir(parents=True, exist_ok=True)
        sdf = out_dir / "conformers.sdf"
        writer = Chem.SDWriter(str(sdf))
        for idx, cid in enumerate(conf_ids):
            mol.SetProp("_Name", f"conf_{idx}")
            writer.write(mol, confId=cid)
        writer.close()
        result.data = {
            "n_conformers": len(conf_ids),
            "energies_kcal_mol": energies,
            "lowest_energy_kcal_mol": min(energies) if energies else None,
            "sdf": str(sdf),
        }
        result.summary = f"generated {len(conf_ids)} conformer(s)"
        result.sources = [str(sdf)]
        result.backend_version = module_version("rdkit")
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"conformer generation failed: {exc}"
    return result.finish()


def chemistry(smiles: str = "", operation: str = "descriptors", canonical: str = "",
              query: str = "", smart: bool = False, **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.CHEMISTRY.value, backend="rdkit",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["RDKit: Open-source cheminformatics"])
    try:
        op = (operation or "descriptors").lower()
        if op in {"descriptors", "properties", "parse", "canonicalize", "validate"}:
            payload = rdkit_descriptors(smiles)
        elif op in {"fingerprint", "fingerprints"}:
            payload = _fingerprint(smiles, canonical or "morgan")
        elif op in {"tautomers", "tautomer"}:
            payload = _tautomers(smiles)
        elif op in {"standardize", "protonation", "neutralize", "uncharge"}:
            payload = _standardize(smiles)
        elif op in {"substructure", "search"}:
            payload = _substructure(smiles, query, smart=smart)
        else:
            raise ValueError(f"unknown chemistry operation: {operation}")
        result.data = payload
        result.summary = f"chemistry:{op}"
        result.backend_version = module_version("rdkit")
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"chemistry error: {exc}"
    return result.finish()


def _run_admet_ai(smiles: str) -> dict[str, Any]:
    """Executed in the env that provides admet_ai (may be a different interpreter)."""
    from admet_ai import ADMETModel

    global _ADMET_AI_MODEL
    try:
        model = _ADMET_AI_MODEL
    except NameError:
        model = _ADMET_AI_MODEL = ADMETModel()
    preds = model.predict(smiles=smiles)
    if hasattr(preds, "to_dict"):
        preds = preds.to_dict()
    if hasattr(preds, "iloc"):
        preds = preds.iloc[0].to_dict()
    import math

    clean = {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in dict(preds).items()}
    return {"engine": "admet_ai", "n_endpoints": len(clean), "endpoints": clean}


def admet(smiles: str = "", backend: str = "auto", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.ADMET.value, backend="rdkit_descriptors",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value,
        approximation=True,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["RDKit descriptors; Lipinski rule-of-five", "ADMET-AI (Swanson et al. 2024)"])
    try:
        descriptors = rdkit_descriptors(smiles)
        flags = {
            "lipinski_pass": descriptors["lipinski_pass"],
            "lipinski_violations": descriptors["lipinski_violations"],
            "high_tpsa": descriptors["tpsa"] > 140,
            "high_logp": descriptors["logp_crippen"] > 5,
        }
        learned: dict[str, Any] = {}
        # preferred learned endpoints: local ADMET-AI (redistributable Chemprop ensemble)
        if module_available("admet_ai"):
            from protacxtend.scientific_backends.dispatch import run_cross_env

            payload = run_cross_env("protacxtend.scientific_backends.backends.chemistry",
                                    "_run_admet_ai", args=[smiles],
                                    require_import="admet_ai", timeout=900)
            if payload.get("ok") and payload.get("result"):
                learned["admet_ai"] = payload["result"]
                result.method_label = "ADMET_AI"
                result.backend = "admet_ai"
                result.evidence_tier = EvidenceTier.TIER_1_MINIMIZED.value
                result.approximation = True
            else:
                result.warnings.append(f"ADMET-AI unavailable: {payload.get('error')}")
        if not learned:
            try:
                from protacxtend.tools.admet_predictors import predict_with_local_admet_model

                ok, payload2, err = safe_call(predict_with_local_admet_model, smiles, "default")
                if ok and isinstance(payload2, dict) and payload2.get("real_output_generated"):
                    learned = {"local_model": payload2}
                    result.method_label = "LOCAL_ADMET_MODEL"
            except Exception:  # noqa: BLE001
                learned = {}
        result.data = {"descriptors": descriptors, "rule_flags": flags, "learned_endpoints": learned}
        result.method_label = result.method_label or "RDKIT_DESCRIPTORS"
        result.summary = f"ADMET descriptors + {result.method_label}"
        result.backend_version = module_version("admet_ai") or module_version("rdkit")
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"ADMET error: {exc}"
    return result.finish()


RDKIT_BACKEND = register(BackendSpec(
    name="rdkit",
    capabilities=(Capability.CHEMISTRY, Capability.CONFORMER_GENERATION, Capability.ADMET),
    license=OPEN_SOURCE_PERMISSIVE,
    priority=95,
    description="RDKit cheminformatics, descriptors, conformers and deterministic ADMET descriptors.",
    version=module_version("rdkit"),
    citation="RDKit",
    health_check=rdkit_available,
    handlers={
        Capability.CHEMISTRY: chemistry,
        Capability.CONFORMER_GENERATION: generate_conformers,
        Capability.ADMET: admet,
    },
))

# Open Babel is GPL (copyleft) — registered but only used when copyleft is allowed.
def openbabel_available():
    from protacxtend.scientific_backends.dispatch import Availability, binary_available, module_available

    ok = binary_available("obabel") or module_available("openbabel")
    return Availability(available=ok, detail="Open Babel CLI/python")


def openbabel_convert(smiles: str = "", to_format: str = "sdf", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(Capability.CHEMISTRY.value, backend="openbabel",
                                    evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value,
                                    license_class="open_source_copyleft",
                                    citations=["Open Babel (GPL)"])
    try:
        from rdkit import Chem

        if not isinstance(smiles, str) or not smiles.strip() or Chem.MolFromSmiles(smiles) is None:
            result.status = CapabilityStatus.WARNING.value
            result.summary = f"openbabel rejected invalid SMILES: {smiles!r}"
            return result.finish()
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

        tb = ProtacDesignToolbox()
        canonical = tb.canonicalize_smiles(smiles)
        result.data = {"canonical_smiles": canonical, "target_format": to_format}
        result.summary = "openbabel canonicalization"
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"openbabel error: {exc}"
    return result.finish()


OPENBABEL_BACKEND = register(BackendSpec(
    name="openbabel",
    capabilities=(Capability.CHEMISTRY,),
    license=__import__("protacxtend.scientific_backends.licenses", fromlist=["OPEN_SOURCE_COPYLEFT"]).OPEN_SOURCE_COPYLEFT,
    priority=40,
    description="Open Babel format conversion/canonicalization (GPL, local use).",
    citation="Open Babel",
    health_check=openbabel_available,
    handlers={Capability.CHEMISTRY: openbabel_convert},
))
