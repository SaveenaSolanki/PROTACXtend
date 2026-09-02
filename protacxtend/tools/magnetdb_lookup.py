"""Lean MagnetDB local-file inference adapter.

This adapter executes target inference only when both local pickle artifacts are
present and loadable. It never fabricates matches.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from protacxtend.backend.config import DATA_DIR


SOURCE = "Lean MagnetDB local inference"
DEFAULT_TRIE_PATH = DATA_DIR / "Lean_MagnetDB_Trie.pkl"
DEFAULT_METADATA_PATH = DATA_DIR / "Clean_Metadata_Hash.pkl"


class TrieNode:
    def __init__(self) -> None:
        self.children: dict[str, "TrieNode"] = {}
        self.is_end_of_word = False
        self.tag_ids: set[str] = set()


class LeanTrie:
    def __init__(self) -> None:
        self.root = TrieNode()

    def __getstate__(self):
        return self.root

    def __setstate__(self, state) -> None:
        self.root = state


def _failure(query: dict[str, Any], error: str, trie_path: Path, metadata_path: Path) -> dict[str, Any]:
    return {
        "source": SOURCE,
        "query": query,
        "success": False,
        "error": error,
        "records": [],
        "source_url": f"local:{trie_path}|{metadata_path}",
    }


def _heavy_atom_count(smiles: str) -> int:
    try:
        from rdkit import Chem
        from rdkit.Chem.rdmolops import DeleteSubstructs
    except Exception:
        return 0
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return 0
        dummy = Chem.MolFromSmarts("[#0]")
        cleaned = DeleteSubstructs(mol, dummy)
        return int(cleaned.GetNumHeavyAtoms())
    except Exception:
        return 0


def _terminal_fragments(smiles: str) -> list[str]:
    try:
        from rdkit import Chem
        from rdkit.Chem import Recap
    except Exception:
        return []
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return []
    hierarchy = Recap.RecapDecompose(mol)
    return [frag for frag, _node in hierarchy.children.items() if frag.count("*") == 1]


def _trie_lookup(root: Any, fragment: str) -> Any | None:
    node = root
    for char in (fragment + "$")[::-1]:
        if char not in node.children:
            return None
        node = node.children[char]
    if not getattr(node, "is_end_of_word", False):
        return None
    return node


def magnetdb_inference_status(
    trie_path: str | Path | None = None,
    metadata_path: str | Path | None = None,
) -> dict[str, Any]:
    trie = Path(trie_path) if trie_path else DEFAULT_TRIE_PATH
    meta = Path(metadata_path) if metadata_path else DEFAULT_METADATA_PATH
    return {
        "available": trie.exists() and meta.exists(),
        "trie_path": str(trie),
        "metadata_path": str(meta),
        "note": "Both pickle files must be present for executable MagnetDB local inference.",
    }


def run_lean_magnetdb_inference(
    user_smiles: str,
    query_name: str = "User_Molecule",
    min_query_cov: float = 25.0,
    min_target_cov: float = 75.0,
    top_k: int = 200,
    trie_path: str | Path | None = None,
    metadata_path: str | Path | None = None,
) -> dict[str, Any]:
    query = {
        "user_smiles": user_smiles,
        "query_name": query_name,
        "min_query_cov": min_query_cov,
        "min_target_cov": min_target_cov,
        "top_k": top_k,
    }
    if not user_smiles or not str(user_smiles).strip():
        return _failure(query, "SMILES is required.", DEFAULT_TRIE_PATH, DEFAULT_METADATA_PATH)

    trie_file = Path(trie_path) if trie_path else DEFAULT_TRIE_PATH
    metadata_file = Path(metadata_path) if metadata_path else DEFAULT_METADATA_PATH
    if not trie_file.exists() or not metadata_file.exists():
        return _failure(query, "Lean MagnetDB pickle files are not present.", trie_file, metadata_file)

    try:
        with trie_file.open("rb") as handle:
            trie = pickle.load(handle)
        with metadata_file.open("rb") as handle:
            metadata_hash = pickle.load(handle)
    except Exception as exc:
        return _failure(query, f"Lean MagnetDB files could not be loaded: {exc}", trie_file, metadata_file)

    query_atoms = _heavy_atom_count(user_smiles)
    if query_atoms <= 0:
        return _failure(query, "SMILES could not be parsed for atom counting.", trie_file, metadata_file)

    fragments = _terminal_fragments(user_smiles)
    if not fragments:
        return _failure(query, "No terminal RECAP fragments were generated.", trie_file, metadata_file)

    records = []
    seen = set()
    for fragment in fragments:
        node = _trie_lookup(trie.root, fragment)
        if node is None:
            continue
        fragment_atoms = _heavy_atom_count(fragment)
        for db_id in sorted(node.tag_ids):
            meta = metadata_hash.get(db_id)
            if not isinstance(meta, dict):
                continue
            target_atoms = int(meta.get("Target_Atom_Count") or 0)
            if target_atoms <= 0:
                continue
            q_cov = (fragment_atoms / query_atoms) * 100.0
            t_cov = (fragment_atoms / target_atoms) * 100.0
            if q_cov < min_query_cov or t_cov < min_target_cov or t_cov > 100.0:
                continue
            key = (db_id, fragment)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "database_id": db_id,
                    "target_id": meta.get("Target_ID"),
                    "target_name": meta.get("Target_Name"),
                    "molecule_name": meta.get("Ligand_Name"),
                    "smiles": meta.get("Original_SMILES"),
                    "activity_type": None,
                    "activity_value": None,
                    "activity_unit": None,
                    "pchembl_value": None,
                    "assay_description": meta.get("Assay"),
                    "confidence_score": None,
                    "fragment_smiles": fragment,
                    "query_coverage_percent": round(q_cov, 2),
                    "target_coverage_percent": round(t_cov, 2),
                    "source_url": f"local:{trie_file}|{metadata_file}",
                    "success": True,
                    "error": None,
                }
            )

    records.sort(key=lambda item: (-item["target_coverage_percent"], -item["query_coverage_percent"]))
    sliced = records[: max(int(top_k), 1)]
    return {
        "source": SOURCE,
        "query": query,
        "success": bool(sliced),
        "error": None if sliced else "no_hits",
        "status": "ok" if sliced else "no_hits",
        "records": sliced,
        "source_url": f"local:{trie_file}|{metadata_file}",
    }

