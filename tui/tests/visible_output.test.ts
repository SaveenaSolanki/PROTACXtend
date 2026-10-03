/**
 * Real TUI visible-output tests.
 *
 * Spawns the ACTUAL Node TUI (src/index.ts) in a fresh process with a real
 * Python bridge, feeds real commands, and asserts the VISIBLE text the user
 * would see — not backend events and not exit status.
 *
 * Run with: npm test  (or: node --import tsx --test tests/visible_output.test.ts)
 */

import { describe, it, before } from "node:test";
import assert from "node:assert";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";

const ANSI_RE = /\x1b\[[0-9;]*m/g;
const PROMPT_RE = /PROTACXtend.*>?\s*$/m;

function stripAnsi(s: string): string {
  return s.replace(ANSI_RE, "").replace(/\r/g, "").replace(PROMPT_RE, "").replace(/\u0000/g, "");
}

/** Find a python interpreter that can import the repo's protacxtend. */
function findPython(): string {
  for (const bin of [process.env.PROTACXTEND_PYTHON, "python3", "python"].filter(Boolean) as string[]) {
    const r = spawnSync(bin, ["-c", "import protacxtend, sys; print(protacxtend.__file__)"], { encoding: "utf8" });
    if (r.status === 0) return bin;
  }
  throw new Error("no python interpreter with importable protacxtend found (set PROTACXTEND_PYTHON)");
}

async function runTui(inputs: string[], timeoutMs = 200_000): Promise<string> {
  const exe = findPython();
  const proc: ChildProcess = spawn(
    process.execPath,
    ["--import", "tsx", "src/index.ts"],
    {
      cwd: new URL("..", import.meta.url).pathname,
      env: {
        ...process.env,
        PROTACXTEND_PYTHON: exe,
        PROTACXTEND_PLANNER_OFFLINE: "1",
        TERM: "dumb",
        NO_COLOR: "1",
      },
      stdio: ["pipe", "pipe", "pipe"],
    },
  );

  let out = "";
  let err = "";
  proc.stdout?.on("data", (d: Buffer) => (out += d.toString()));
  proc.stderr?.on("data", (d: Buffer) => (err += d.toString()));

  const closed = new Promise<number>((resolve, reject) => {
    const timer = setTimeout(() => {
      proc.kill("SIGKILL");
      reject(new Error(`TUI did not exit within ${timeoutMs}ms; stderr: ${err.slice(-400)}; stdout: ${out.slice(-800)}`));
    }, timeoutMs);
    proc.on("close", (code) => {
      clearTimeout(timer);
      resolve(code ?? -1);
    });
    proc.on("error", (e) => reject(e));
  });

  const promptCount = () => (stripAnsi(out).match(/PROTACXtend>/g) ?? []).length;
  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
  const waitForPrompt = async (after: number, waitMs = 100_000): Promise<void> => {
    const t0 = Date.now();
    while (promptCount() <= after) {
      if (Date.now() - t0 > waitMs) {
        throw new Error(`prompt not reached after ${waitMs}ms; stdout tail: ${out.slice(-500)}`);
      }
      await sleep(500);
    }
  };

  // Handlers are async; readline does not await them. Feed each command and
  // wait for the next prompt so a command is never cancelled by the next one.
  let n = promptCount();
  for (const line of inputs) {
    proc.stdin?.write(line + "\n");
    if (line !== "/quit") {
      await waitForPrompt(n);
      n = promptCount();
    }
  }
  proc.stdin?.end();

  await closed;
  if (err && err.length > 2000) err = err.slice(-2000);
  return `${out}\n__STDERR__\n${err}`;
}

describe("Real TUI visible output (fresh process, real bridge)", () => {
  let transcript = "";
  let visible = "";

  before(async () => {
    transcript = await runTui([
      "/plan HMGB2 protac",
      "/investigate AR protac",
      "/reason which protac work for EGFR",
      "/quit",
    ]);
    visible = stripAnsi(transcript);
  }, 260_000);

  it("/plan HMGB2 protac renders tasks, stages and artifacts as visible text", () => {
    assert.match(visible, /HMGB2/i, "plan interpretation must name HMGB2");
    assert.match(visible, /P26583/, "resolved UniProt id must be visible");
    assert.match(visible, /PLAN TASKS/, "task section must be rendered");
    assert.match(visible, /T0_confirm_target/i, "first task id must be visible");
    assert.match(visible, /T1b_therapeutic_assessment/i, "therapeutics pre-design task must be visible");
    assert.match(visible, /STAGE STATUS/, "stage statuses must be rendered alongside the result");
    assert.match(visible, /PERSISTED ARTIFACTS/, "artifacts must be rendered alongside the result");
  });

  it("/investigate AR protac renders findings and artifacts, not empty panels", () => {
    assert.match(visible, /INVESTIGATION/, "investigation header must be visible");
    assert.match(visible, /P10275/, "androgen receptor UniProt id must be visible");
    assert.match(visible, /Measured precedent rows in packaged context set: 87/, "row census must be visible");
    assert.match(visible, /PERSISTED ARTIFACTS/, "evidence graph should be shown as an artifact");
  });

  it("/reason which protac work for EGFR renders intent-driven sections with row-level evidence", () => {
    assert.match(visible, /MECHANISTIC REASONING/, "reasoning header must be visible");
    assert.match(visible, /WHY_WORKS|EVIDENCE_SYNTHESIS/, "reasoning intent must be visible");
    assert.match(visible, /A-431/, "row-level evidence (cell line) must be visible");
    assert.match(visible, /10.1016/, "DOI-backed evidence must be visible");
    assert.match(visible, /CONCLUSION/, "conclusion must be visible");
  });

  it("never renders 'H ?' or resource-selection logs as the scientific answer", () => {
    assert.ok(!visible.includes("H ?"), "H ? placeholder must never be visible");
    assert.ok(!visible.includes("RESOURCE REASONS"), "resource-selection logs must not be rendered as the answer");
    assert.ok(!/resource[- ]?reason selection/.test(visible), "resource-reason log language must not be visible");
  });
});