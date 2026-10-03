#!/usr/bin/env node
/**
 * PROTACXtend — unified launcher.
 *
 * One command, both interfaces, from any directory:
 *
 *   protacxtend                      → Node terminal UI (default)
 *   protacxtend tui ["<request>"]    → Node terminal UI
 *   protacxtend py-tui ["<request>"] → Python (Textual) terminal UI
 *   protacxtend <subcommand> [...]   → Python CLI (toolkit, validate, doctor, …)
 *   protacxtend -p "Design …"        → Python CLI print/plan mode
 *   protacxtend "Design …"           → Node terminal UI (free-text objective)
 *
 * The full Python CLI is also available verbatim as `PROTACXtend`.
 */

import { spawnSync } from "node:child_process";
import { ProtacXtendApp } from "./app.js";

/**
 * Python CLI subcommands — kept in sync with the `command_names` gate in
 * `protacxtend/cli.py::main`. `tui` is intentionally excluded because the
 * Node TUI owns that verb; the Python TUI is reachable as `py-tui`.
 */
const PY_CLI_COMMANDS = new Set<string>([
  "run",
  "llm",
  "chat",
  "auth",
  "model",
  "setup",
  "provider",
  "case-study",
  "runtime",
  "doctor",
  "pilot",
  "design",
  "ask",
  "validate",
  "ternary",
  "contract",
  "external",
  "structure",
  "dose",
  "context",
  "proteome",
  "learn",
  "strategy",
  "controlled-run",
  "ui",
  "api",
  "status",
  "scenarios",
  "capabilities",
  "escalation",
  "toolkit",
  "backends",
  "install",
  "audit",
  "validate-complex",
]);

const PY_TUI_ALIASES = new Set<string>(["py-tui", "python-tui"]);

function pythonBin(): string {
  return process.env.PROTACXTEND_PYTHON?.trim() || "python3";
}

/** Run a Python module in the caller's working directory and mirror its exit. */
function delegate(moduleArgs: string[]): never {
  const result = spawnSync(pythonBin(), moduleArgs, { stdio: "inherit" });
  if (result.error) {
    console.error(
      `protacxtend: could not launch the Python runtime (${pythonBin()}): ${result.error.message}\n` +
        `            set PROTACXTEND_PYTHON to a Python ≥ 3.10 with 'protacxtend' installed.`,
    );
    process.exit(127);
  }
  process.exit(result.status ?? 0);
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const first = args[0];

  // Explicit Python (Textual) TUI.
  if (first !== undefined && PY_TUI_ALIASES.has(first)) {
    delegate(["-m", "protacxtend.tui.app", ...args.slice(1)]);
  }

  // Flags belong to the Python CLI (-p/--print, -h/--help, --version, …).
  if (first !== undefined && first.startsWith("-")) {
    delegate(["-m", "protacxtend.cli", ...args]);
  }

  // Python CLI subcommands (everything except the TUI verb, which is ours).
  if (first !== undefined && first !== "tui" && PY_CLI_COMMANDS.has(first)) {
    delegate(["-m", "protacxtend.cli", ...args]);
  }

  // Default: Node terminal UI (no args, `tui`, or a free-text design request).
  const app = new ProtacXtendApp();
  await app.start();
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exitCode = 1;
});
