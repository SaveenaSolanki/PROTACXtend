from protacxtend.workflows.resource_audit import build_resource_registry, shortlist_resources


def test_registry_separates_counts_and_categories_without_single_tool_count():
    registry = build_resource_registry()
    assert registry["schema_version"] == "resource-registry.v1"
    assert "counts" in registry and registry["counts"]
    assert "commands" in registry["categories"]
    assert "workflow_nodes" in registry["categories"]
    assert "tpd_capabilities" in registry["categories"]
    assert registry["counts"].get("commands", 0) >= 14
    assert registry["counts"].get("workflow_nodes", 0) >= 20
    flat = [item for rows in registry["categories"].values() for item in rows]
    assert any(item["status"] == "unavailable" for item in flat)
    assert all("category" in item and "status" in item and "evidence" in item for item in flat)


def test_shortlist_for_brd4_design_selects_only_eligible_available_resources():
    registry = build_resource_registry()
    out = shortlist_resources("Design CRBN PROTAC for BRD4", registry=registry, offline=True)
    selected = out["selected"]
    rejected = out["rejected"]
    assert out["resolved_target"]["symbol"] == "BRD4"
    assert out["intent"] == "design"
    names = {r["name"] for r in selected}
    assert any("target" in n.lower() or "resolver" in n.lower() for n in names)
    assert any("degradation" in n.lower() for n in names)
    assert not any(r["status"] == "unavailable" for r in selected)
    assert rejected and all(r.get("reason") for r in rejected)


def test_shortlist_for_kras_g12c_preserves_mutation_and_different_route():
    registry = build_resource_registry()
    out = shortlist_resources("Investigate allele-specific degradation options for KRAS G12C", registry=registry, offline=True)
    assert out["resolved_target"]["symbol"] == "KRAS"
    assert out["mutation"] == "G12C"
    assert out["intent"] in {"investigate", "plan"}
    selected_caps = {r.get("capability") for r in out["selected"]}
    assert "target_resolver" in selected_caps or "evidence_retrieval" in selected_caps
    assert out["resource_log"]["considered"] >= len(out["selected"])


def test_shortlist_exposes_tui_display_reasons_for_selected_and_rejected_resources():
    registry = build_resource_registry()
    out = shortlist_resources("/run Design a CRBN-recruiting PROTAC for BRD4", registry=registry, offline=True)
    summary = out["resource_reason_summary"]
    assert summary["schema_version"] == "resource-reason-summary.v1"
    assert summary["selected"]
    assert summary["rejected"]
    assert all(r.get("reason") for r in summary["selected"])
    assert all(r.get("reason") for r in summary["rejected"])
    assert any("selected:" in r["reason"] for r in summary["selected"])


def test_know_and_reason_cases_do_not_select_design_construction_resources():
    registry = build_resource_registry()
    cases = [
        "Which dimethylisoxazole-family warheads are documented BET bromodomain ligands for the supplied pocket context?",
        "Assess whether the supplied VHL ligand retains critical VH032 pharmacophore motifs.",
        "Explain mechanistic liabilities of replacing the amide junction with a protonatable secondary amine.",
    ]
    for text in cases:
        out = shortlist_resources(text, registry=registry, offline=True)
        caps = " ".join(str(r.get("capability", "")) for r in out["selected"]).lower()
        assert "construction" not in caps
        assert "linker_generation" not in caps
        assert "warhead_selection" not in caps
        assert out["resource_reason_summary"]["selected"]
