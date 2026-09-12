"""Evidence store: typed provenance and memory↔evidence stances."""

from __future__ import annotations

from typing import Any

from ..domain.protac.evidence import EvidenceBundle, EvidenceRef
from ..util import dumps, loads, new_id, now_iso
from .base import BaseStore


class EvidenceStore(BaseStore):
    def add_evidence(self, ref: EvidenceRef, project_id: str | None = None) -> str:
        evidence_id = new_id("EV")
        row = ref.to_row()
        self.db.execute(
            """
            INSERT INTO evidence_items
                (id, evidence_type, title, description, source_type, source_ref,
                 doi, pmid, url, pdb, accession, file_path, dataset_row_id,
                 experiment_id, notebook_id, model_name, model_version, timestamp,
                 quality, payload_json, project_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id, row["evidence_type"], row["title"], row["description"],
                row["source_type"], row["source_ref"], row["doi"], row["pmid"],
                row["url"], row["pdb"], row["accession"], row["file_path"],
                row["dataset_row_id"], row["experiment_id"], row["notebook_id"],
                row["model_name"], row["model_version"], row["timestamp"],
                row["quality"], dumps(row["payload_json"]), project_id, now_iso(),
            ),
        )
        return evidence_id

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM evidence_items WHERE id = ?", (evidence_id,))
        if row is None:
            return None
        return dict(row) | {"payload_json": loads(row["payload_json"], {})}

    def link(
        self,
        memory_id: str,
        evidence_id: str,
        stance: str = "supports",
        weight: float = 1.0,
        independent_group: str | None = None,
    ) -> None:
        self.db.execute(
            """
            INSERT OR REPLACE INTO memory_evidence
                (memory_id, evidence_id, stance, weight, independent_group, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (memory_id, evidence_id, stance, float(weight), independent_group, now_iso()),
        )

    def links_for_memory(self, memory_id: str) -> list[dict[str, Any]]:
        rows = self.db.query(
            """
            SELECT me.stance, me.weight, me.independent_group, e.*
            FROM memory_evidence me JOIN evidence_items e ON e.id = me.evidence_id
            WHERE me.memory_id = ?
            ORDER BY me.stance, e.created_at
            """,
            (memory_id,),
        )
        out = []
        for r in rows:
            d = dict(r)
            d["payload_json"] = loads(d.get("payload_json"), {})
            out.append(d)
        return out

    def bundle_for_memory(self, memory_id: str) -> EvidenceBundle:
        bundle = EvidenceBundle()
        for link in self.links_for_memory(memory_id):
            ref = EvidenceRef(
                evidence_type=link["evidence_type"],
                title=link.get("title"),
                description=link.get("description"),
                source_type=link.get("source_type"),
                source_ref=link.get("source_ref"),
                doi=link.get("doi"),
                pmid=link.get("pmid"),
                url=link.get("url"),
                pdb=link.get("pdb"),
                accession=link.get("accession"),
                file_path=link.get("file_path"),
                dataset_row_id=link.get("dataset_row_id"),
                experiment_id=link.get("experiment_id"),
                notebook_id=link.get("notebook_id"),
                model_name=link.get("model_name"),
                model_version=link.get("model_version"),
                timestamp=link.get("timestamp"),
                quality=link.get("quality"),
                payload=link.get("payload_json") or {},
            )
            if link["stance"] == "contradicts":
                bundle.contradicts.append(ref)
            elif link["stance"] == "context":
                bundle.context.append(ref)
            else:
                bundle.supports.append(ref)
        return bundle

    def evidence_for_memories(self, memory_ids: list[str]) -> dict[str, EvidenceBundle]:
        return {mid: self.bundle_for_memory(mid) for mid in memory_ids}

    def unlinked_evidence(self) -> list[dict[str, Any]]:
        rows = self.db.query(
            """
            SELECT e.id FROM evidence_items e
            LEFT JOIN memory_evidence me ON me.evidence_id = e.id
            WHERE me.evidence_id IS NULL
            """
        )
        return [dict(r) for r in rows]

    def evidence_count(self, memory_id: str, stance: str | None = None) -> int:
        if stance:
            return self.count("memory_evidence", "memory_id = ? AND stance = ?", (memory_id, stance))
        return self.count("memory_evidence", "memory_id = ?", (memory_id,))
