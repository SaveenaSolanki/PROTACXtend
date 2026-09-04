/**
 * PROTACXtend TUI — global CLI invocation tests.
 *
 * Verifies that `protacxtend` (npm bin) is wired correctly:
 *   • package.json bin mapping
 *   • #!/usr/bin/env node shebang in source and compiled entry
 *   • the compiled TUI boots from ANY directory and talks to the
 *     Python backend (path resolution must not depend on cwd)
 *
 * Live-backend tests are skipped automatically when the Python package
 * or the compiled dist/ is unavailable (e.g. pre-build CI steps).
 */

import { describe, it } from "node:test";
import assert from "node:assert";
import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync } from "node:child_process";
import { tmpdir } from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const TUI_ROOT = resolve(__dirname, "..");

const python = process.env.PROTACXTEND_PYTHON ?? "python3";
const REPO_ROOT = resolve(TUI_ROOT, "..");
const backendAvailable = (() => {
  try {
    const r = spawnSync(python, ["-c", "import protacxtend"], { cwd: REPO_ROOT, timeout: 20_000 });
    return r.status === 0;
  } catch {
    return false;
  }
})();

describe("Global CLI wiring", () => {
  it("package.json maps `protacxtend` to the compiled entry", () => {
    const pkg = JSON.parse(readFileSync(resolve(TUI_ROOT, "package.json"), "utf8"));
    assert.strictEqual(pkg.bin.protacxtend, "dist/index.js");
  });

  it("source entry point begins with #!/usr/bin/env node", () => {
    const src = readFileSync(resolve(TUI_ROOT, "src", "index.ts"), "utf8");
    assert.ok(src.startsWith("#!/usr/bin/env node"));
  });

  it("compiled dist/index.js carries the shebang (skip if not built)", (t) => {
    const entry = resolve(TUI_ROOT, "dist", "index.js");
    if (!existsSync(entry)) {
      t.skip("dist not built — run npm run build first");
      return;
    }
    const head = readFileSync(entry, "utf8").split("\n")[0];
    assert.strictEqual(head, "#!/usr/bin/env node");
  });
});

describe("Global launch from any directory", () => {
  const entry = resolve(TUI_ROOT, "dist", "index.js");

  it("displayed product name stays exactly PROTACXtend", () => {
    const logo = readFileSync(resolve(TUI_ROOT, "src", "logo.ts"), "utf8");
    assert.match(logo, /BRAND_NAME = "PROTACXtend"/);
  });

  it("launches from /tmp, reaches the Python backend, and quits cleanly", { timeout: 90_000 }, async (t) => {
    if (!existsSync(entry)) {
      t.skip("dist not built — run npm run build first");
      return;
    }
    if (!backendAvailable) {
      t.skip(`python backend unavailable (${python} cannot import protacxtend)`);
      return;
    }

    const cwd = tmpdir(); // deliberately NOT the repo
    const child = spawn(process.execPath, [entry], { cwd, stdio: ["pipe", "pipe", "pipe"] });
    let buf = "";
    let stderr = "";
    const onOut = (d: Buffer) => { buf += d.toString(); };
    const onErr = (d: Buffer) => { stderr += d.toString(); };
    child.stdout?.on("data", onOut);
    child.stderr?.on("data", onErr);

    const waitFor = (needle: string, ms: number): Promise<boolean> =>
      new Promise((resolveWait) => {
        const started = Date.now();
        const tick = setInterval(() => {
          if (buf.includes(needle)) {
            clearInterval(tick);
            resolveWait(true);
          } else if (Date.now() - started > ms) {
            clearInterval(tick);
            resolveWait(false);
          }
        }, 150);
      });

    try {
      // Wait for the interactive prompt (header rendered, backend primed)
      const ready = await waitFor("PROTACXtend> ", 50_000);
      assert.ok(ready, `TUI did not reach the prompt. stderr so far: ${stderr.slice(0, 500)}`);

      // Wordmark must be present in the header
      assert.ok(buf.includes("█"), "block wordmark missing from output");

      // Exercise the backend through the bridge
      child.stdin?.write("/status\n");
      const gotStatus = await waitFor("project root", 20_000);
      assert.ok(gotStatus, `backend /status did not answer. stderr: ${stderr.slice(0, 500)}`);

      // status must report the repo root (backend resolved independent of cwd)
      assert.match(buf, /project root\s+\S*protacpilot|PROTACXtend/i);

      child.stdin?.write("/quit\n");
      const code = await new Promise<number | null>((resolveExit) => {
        child.on("exit", (c) => resolveExit(c));
        setTimeout(() => resolveExit(null), 10_000);
      });
      assert.strictEqual(code, 0, `expected clean exit 0, got ${code}. stderr tail: ${stderr.slice(-400)}`);
    } finally {
      child.removeListener("exit", () => undefined);
      child.stdout?.removeListener("data", onOut);
      child.stderr?.removeListener("data", onErr);
      if (child.exitCode === null) {
        child.kill("SIGKILL");
      }
    }
  });
});
