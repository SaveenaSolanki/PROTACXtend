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

## Development

```bash
npm run dev     # run from TypeScript sources (tsx)
npm test        # node:test suite
```

Set `PROTACXTEND_PYTHON` to select the interpreter used for the bridge, and
`PROTACXTEND_EXECUTION_MODE=demo|test|scientific` to control fixture policy.
