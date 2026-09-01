# PROTACXtend LLM Provider Layer — use ANY API, swap anytime

The decision layer talks to ONE interface (`llm/gateway.py`). The provider is
configurable at boot (env) or at runtime (backend API / frontend sidebar).
Swapping Ollama/gpt-oss:20b for any API changes **nothing** in the decision
layer, schemas, or validators — only the raw chat call differs.

## Providers (llm/providers.py)

| Provider | Use | Config |
|---|---|---|
| `ollama` | local default (gpt-oss:20b) | base_url `http://127.0.0.1:11435` |
| `openai` | OpenAI API | api_key, model |
| `openrouter` | aggregator (Claude/GPT/DeepSeek/...) | api_key, model |
| `anthropic` | Claude | api_key, model |
| `google` | Gemini | api_key, model |
| `openai_compatible` | vLLM, LM Studio, Groq, Together, DeepSeek... | base_url + api_key + model |

## How to switch (3 ways)

### 1. Environment (boot default)
```bash
export PROTACPILOT_LLM_PROVIDER=openai            # ollama | openai | openrouter | anthropic | google | openai_compatible
export PROTACPILOT_LLM_MODEL=gpt-4o-mini
export PROTACPILOT_LLM_API_KEY=sk-...
# optional:
export PROTACPILOT_LLM_BASE_URL=https://api.openai.com/v1
export PROTACPILOT_LLM_NUM_CTX=16384
export PROTACPILOT_LLM_TEMPERATURE=0
```

### 2. Backend API (runtime, any client)
```bash
curl -X POST http://127.0.0.1:8000/llm/switch \
  -H "Content-Type: application/json" \
  -d '{"provider": "openrouter", "model": "deepseek/deepseek-chat", "api_key": "sk-or-..."}'

curl http://127.0.0.1:8000/llm/status        # active provider + health
curl http://127.0.0.1:8000/llm/providers     # available providers
curl "http://127.0.0.1:8000/llm/models?provider=ollama"
curl -X POST http://127.0.0.1:8000/llm/test -H "Content-Type: application/json" \
  -d '{"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-..."}'
curl -X POST http://127.0.0.1:8000/llm/reset  # back to env config
```

### 3. Frontend (Streamlit sidebar)
The sidebar has an **LLM backend** widget: pick provider, model, base URL,
API key → Apply (switch) / Test (live schema-validated call).

## Guarantees (identical for every provider)

1. **Structured output**: every decision validates against a Pydantic schema
   (`llm/schemas.py`). Provider format hints are best-effort; our JSON
   extractor + repair (`llm/json_repair.py`) + one retry handle malformed
   replies; then Pydantic.
2. **Strict tool registry**: the model may select from 13 allowed tools, never
   construct names; `run_p4ward`/`run_retrosynthesis` force human approval.
3. **Deterministic validators gate the LLM**: evidence sufficiency is decided
   by the deterministic gate (it has the numbers); the LLM only adds flags.
4. **No raw chain-of-thought stored**: decisions only.
5. **Graceful degradation**: provider outage → deterministic fallback router;
   the agentic graph never depends on the LLM being reachable.
6. **Context control**: evidence summarized, lists truncated, num_ctx 16K.

## Tested

- Live: ollama/gpt-oss:20b via the gateway — supervisor (`BRD4/VHL/protac`),
  repair (`alternate_linker` for strain), evidence decisions all parse.
- Mocked: all six provider paths, JSON repair (fences/prose/trailing commas),
  retry-then-succeed, transport failure → fallback, runtime switch + validation.
  27 LLM tests + 99 total green.

## Files

- `llm/providers.py` — provider implementations + registry + config
- `llm/gateway.py` — provider-agnostic structured_chat + status/switch API
- `llm/json_repair.py` — robust JSON extraction/repair
- `llm/schemas.py`, `llm/roles.py`, `llm/context.py`, `llm/decision_layer.py`
- `backend/llm_routes.py` — /llm/* endpoints
- `app/streamlit_app.py` — sidebar LLM widget
