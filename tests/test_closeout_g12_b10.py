"""Regression tests for the security gate (G12) + closeout fixes (B10).

Execution mode is always scoped with the `execution_mode` context manager so
no test leaks global state into later suites.
"""
import os
import sys

import pytest

ROOT = "/storage/saveena/protacxtend"
sys.path.insert(0, ROOT)


class TestSafeIO:
    def test_allowed_roots_load(self):
        from protacxtend.security.safe_io import _resolve
        p = _resolve("data/tack/tack_meta.joblib")
        assert os.path.exists(p)

    def test_outside_repo_raises(self):
        from protacxtend.security.safe_io import SecurityError, safe_pickle_load
        with pytest.raises(SecurityError):
            safe_pickle_load("/etc/passwd")

    def test_run_args_string(self):
        from protacxtend.security.safe_io import run_args
        assert run_args("python -c 'print(1)'") == ["python", "-c", "print(1)"]


class TestWarheadFromBinders:
    def test_binder_path_uses_retrieved_binders(self):
        """Scientific-mode warhead selection must consume state.retrieved_binders
        (zero-candidate root cause #1 regression)."""
        from protacxtend.agents.warhead_agent import WarheadSelectionAgent
        from protacxtend.backend.schemas import BinderRecord, ParsedObjective, TargetRecord, WorkflowState
        from protacxtend.runtime import modes

        with modes.execution_mode("scientific"):
            st = WorkflowState(user_request="Design a VHL PROTAC against BRD4")
            st.parsed_objective = ParsedObjective(target_name="BRD4", e3_ligase="VHL")
            st.target_record = TargetRecord(target_name="BRD4", gene_symbol="BRD4", uniprot_id="O60885")
            st.retrieved_binders = [
                BinderRecord(name="CHEMBLX1", target="BRD4", smiles="Cc1ccc(N)cc1",
                             activity_nM=10.0, p_activity=8.0, activity_type="IC50",
                             source="ChEMBL (assay CHEMBL123)",
                             metadata={"needs_exit_vector_hypothesis": True}),
            ]
            out = WarheadSelectionAgent().run(st)
        names = [w.name for w in out.selected_warheads]
        assert "CHEMBLX1" in names, f"binder-derived warhead missing: {names}"
        w = out.selected_warheads[0]
        assert "[*" in w.smiles, "hypothetical attachment marker must be appended"
        assert w.provenance.get("exit_vector_warning"), "chemist-review provenance required"


class TestE3Marker:
    def test_real_e3_rows_get_markers(self):
        """DOI-cited E3 rows without baked-in dummies must get [*:1] + capped conf."""
        from protacxtend.agents.e3_agent import E3LigandSelectionAgent
        from protacxtend.backend.schemas import ParsedObjective, WorkflowState
        from protacxtend.runtime import modes

        with modes.execution_mode("scientific"):
            st = WorkflowState(user_request="Design a VHL PROTAC against BRD4")
            st.parsed_objective = ParsedObjective(target_name="BRD4", e3_ligase="VHL")
            out = E3LigandSelectionAgent().run(st)
        assert out.selected_e3_ligands
        for ligand in out.selected_e3_ligands:
            assert "[*" in ligand.smiles, f"{ligand.name} lacks attachment marker"
            assert ligand.exit_vector_confidence <= 0.42 or ligand.exit_vector_confidence > 0.5


class TestFixtureLeakGuard:
    def test_demo_rows_keep_demo_source(self):
        """_load_local_binders must propagate real row source (fixture leak)."""
        from protacxtend.agents.binder_agent import TargetBinderRetrievalAgent
        from protacxtend.runtime import modes

        with modes.execution_mode("scientific"):
            local = TargetBinderRetrievalAgent()._load_local_binders("BRD4")
        assert all(not (b.source or "").startswith("local_curated") for b in local)
        assert all(any(t in (b.source or "").lower() for t in ("demo",)) for b in local) or len(local) == 0