# PROTACXtend Terminal UI (Node)

A dependency-free Node/TypeScript terminal command centre for PROTACXtend.
It talks to the Python runtime over a JSONL bridge
(`python -m protacxtend.tui_bridge.server`).

## Requirements

- Node.js ≥ 18
- Python ≥ 3.10 with `protacxtend` importable

## Quick start

```bash
# from the repository root
cd tui
npm install
npm run build
node dist/index.js
```

Or use the one-line launcher (clones/builds/installs automatically):

```bash
curl -fsSL https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/tui/launch.sh | bash
```

## Global install — one command, both interfaces

Install the global `protacxtend` dispatcher (works from any directory):

```bash
cd tui && npm install && npm run build && npm link
```

| Command | Runs |
| --- | --- |
| `protacxtend` | Node terminal UI (default) |
| `protacxtend tui ["<request>"]` | Node terminal UI |
| `protacxtend py-tui` | Python (Textual) terminal UI |
| `protacxtend toolkit …` / `validate …` / `doctor …` | Python CLI subcommands |
| `protacxtend -p "Design …"` | Python CLI print/plan mode |
| `protacxtend "Design …"` | Node terminal UI (free-text objective) |

The full Python CLI also remains available verbatim as `PROTACXtend`.
The dispatcher mirrors the subcommand gate in `protacxtend/cli.py::main`, so
any Python CLI verb is routed to the Python runtime; everything else opens the
Node TUI. `PROTACXTEND_PYTHON` selects the interpreter used for delegation and
for the JSONL bridge.

## Conversational answers (LLM-backed)

Free text and the reasoning verbs (`/ask`, `/explain`, `/reason`,
`/investigate`, `/evidence <query>`, `/plan <objective>`) are answered by the
conversational agent over the configured LLM — the Pi/Feynman-style path.
Explicit design verbs (`/design`, `/run`, …) still drive the deterministic
agent graph.

Configure a backend once (shared with the CLI):

```bash
protacxtend setup                       # interactive
protacxtend llm --provider ollama --model qwen2.5:7b
```

If no provider is configured the TUI header shows `not configured` and chat
returns a setup hint instead of guessing. The header also shows the live
`provider/model` read from the backend status.

## Development

```bash
npm run dev     # run from TypeScript sources (tsx)
npm test        # node:test suite
```

Set `PROTACXTEND_PYTHON` to select the interpreter used for the bridge, and
`PROTACXTEND_EXECUTION_MODE=demo|test|scientific` to control fixture policy.
