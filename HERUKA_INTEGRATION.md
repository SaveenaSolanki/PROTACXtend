# HERUKA.AI Integration — channel PROTACXtend to your frontend

`synglue_agent/integrations/heruka.py` exports every PROTACXtend run as an
**auditable bundle** and pushes it to a configurable HERUKA webhook, so your
heruka.ai frontend (or any endpoint you host) receives full run provenance.

## Principles this integration upholds (HERUKA-aligned)

- **Explainability**: the bundle contains decisions, reason codes, tool calls,
  uncertainty notes, evidence refs and human-gate outcomes — never raw
  chain-of-thought.
- **No hallucination by construction**: every numeric claim carries
  tool/version provenance from the deterministic layers; the LLM never
  produces numbers in this channel.
- **Human agency**: human-gate decisions are recorded verbatim; the bundle
  never infers them.
- **Governance/sovereignty**: runs stay on YOUR infra; the webhook is
  push-only and optional. No data leaves the machine unless you configure it.

## Bundle format (`protacpilot-bundle-v1`)

```
{
  schema, produced_by, run_id, mode, status, runtime_s,
  n_decisions, n_tool_calls,
  decisions:      [{node, decision_type, reason_codes, confidence, next_node, elapsed_s}]
  tool_calls:     [{tool, args, result_summary, elapsed_s}]
  human_gate_events,
  uncertainty_notes,
  evidence_refs,
  report (optional)
}
```

## Configure

```bash
export HERUKA_WEBHOOK_URL=https://your-heruka-endpoint.example/api/protacpilot
export HERUKA_API_TOKEN=your-token          # optional Bearer auth
```

## CLI (Feynman-style)

```bash
python -m synglue_agent.integrations.heruka status                 # integration state
python -m synglue_agent.integrations.heruka export --run <run_id>  # write bundle JSON
python -m synglue_agent.integrations.heruka push --run <run_id>    # POST to webhook
```

Bundles are always also saved to `outputs/heruka/<run_id>.json` — a failed
push never loses the run.

## Frontend

- **Streamlit**: the sidebar now has a "HERUKA.AI channel" widget — export or
  push the latest run with one click.
- **Any HERUKA-hosted UI**: receive the POST body and render the bundle
  (decisions table, tool-call timeline, human-gate markers, uncertainty
  flags, evidence refs). The schema is versioned (`protacpilot-bundle-v1`)
  so you can build against it stably.

## Verified

- Export round-trip (real run → bundle JSON) ✅
- POST round-trip to a local webhook (HTTP 200, body received) ✅
- Non-fatal on missing endpoint (bundle saved locally) ✅
- 6 tests in `tests/test_heruka_integration.py` ✅
