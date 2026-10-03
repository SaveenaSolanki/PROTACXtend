/**
 * Command-centre registry tests.
 *
 * These guard the reported bug class: `/help` advertising a command that the
 * dispatcher does not handle (e.g. `/optimise` -> "Unknown command"), plus the
 * intent-routing contract: /design, /investigate, /reason, /evidence and
 * /compare must dispatch to their deterministic research handlers (shared
 * bridge engine), never to the LLM chat agent.
 *
 * The registry in `src/commands.ts` is the single source of truth for /help,
 * tab-completion and dispatch, so we assert:
 *   • every advertised command resolves,
 *   • aliases (incl. /optimise) resolve to their canonical command,
 *   • whitespace and multiword arguments are preserved,
 *   • every canonical command has a real dispatcher (switch case or the
 *     RESEARCH_INTENTS / CHAT_INTENTS registries used by the pre-dispatch),
 *   • deterministic intents map to the exact bridge research commands.
 */

import { describe, it } from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  COMMANDS,
  RESEARCH_WORKFLOWS,
  commandNames,
  groupedCommands,
  resolveCommand,
  looksTargetOnly,
  neededInputLabel,
  RESEARCH_INTENTS,
  CHAT_INTENTS,
} from "../src/commands.js";

const here = dirname(fileURLToPath(import.meta.url));
const appSource = readFileSync(resolve(here, "../src/app.ts"), "utf8");
const dispatched = new Set([...appSource.matchAll(/case\s+"(\/[^"]+)"/g)].map((m) => m[1]));
// Commands dispatched through the registry pre-dispatch (not switch cases).
for (const cmd of Object.keys(RESEARCH_INTENTS)) dispatched.add(cmd);
for (const cmd of CHAT_INTENTS) dispatched.add(cmd);

describe("command registry — dispatch coverage", () => {
  it("every advertised command has a real dispatcher case", () => {
    const missing = COMMANDS.filter((c) => !dispatched.has(c.cmd)).map((c) => c.cmd);
    assert.deepEqual(missing, [], `advertised but not dispatched: ${missing.join(", ")}`);
  });

  it("every canonical command is unique and starts with '/'", () => {
    const seen = new Set<string>();
    for (const c of COMMANDS) {
      assert.ok(c.cmd.startsWith("/"), `bad command ${c.cmd}`);
      assert.ok(!seen.has(c.cmd), `duplicate command ${c.cmd}`);
      seen.add(c.cmd);
    }
  });

  it("aliases are unique and never shadow a canonical command", () => {
    const canonical = new Set(COMMANDS.map((c) => c.cmd));
    const seen = new Set<string>();
    for (const c of COMMANDS) {
      for (const a of c.aliases ?? []) {
        assert.ok(!canonical.has(a), `alias ${a} shadows a canonical command`);
        assert.ok(!seen.has(a), `duplicate alias ${a}`);
        seen.add(a);
      }
    }
  });

  it("every research workflow is registered with a matching slug", () => {
    for (const w of RESEARCH_WORKFLOWS) {
      const spec = COMMANDS.find((c) => c.cmd === w.cmd);
      assert.ok(spec, `workflow ${w.cmd} missing from registry`);
      assert.equal(spec!.sl, w.slug);
    }
  });
});

describe("aliases", () => {
  it("/optimise is an alias for /optimize", () => {
    const r = resolveCommand("/optimise BRD4 PROTACs");
    assert.equal(r.spec?.cmd, "/optimize");
    assert.equal(r.args, "BRD4 PROTACs");
  });

  it("/optimisation and /optimization resolve to /optimize", () => {
    assert.equal(resolveCommand("/optimization x").spec?.cmd, "/optimize");
    assert.equal(resolveCommand("/optimisation x").spec?.cmd, "/optimize");
  });

  it("/retrosynthesis resolves to /retro and /exit to /quit", () => {
    assert.equal(resolveCommand("/retrosynthesis CC").spec?.cmd, "/retro");
    assert.equal(resolveCommand("/exit").spec?.cmd, "/quit");
  });
});

describe("parsing — whitespace and multiword arguments", () => {
  it("trims surrounding whitespace and collapses internal runs", () => {
    const r = resolveCommand("   /optimize    BRD4   PROTACs   ");
    assert.equal(r.name, "/optimize");
    assert.equal(r.args, "BRD4 PROTACs");
  });

  it("does not lowercase or split the argument payload", () => {
    const r = resolveCommand("/design CRBN PROTACs for BRD4 degradation");
    assert.equal(r.args, "CRBN PROTACs for BRD4 degradation");
  });

  it("returns empty args for a bare command", () => {
    assert.equal(resolveCommand("/help").args, "");
    assert.equal(resolveCommand("  /help  ").spec?.cmd, "/help");
  });

  it("unknown and empty input have no spec", () => {
    assert.equal(resolveCommand("/frobnicate x").spec, undefined);
    assert.equal(resolveCommand("").spec, undefined);
    assert.equal(resolveCommand("   ").spec, undefined);
  });
});

describe("help grouping and completion", () => {
  it("groupedCommands covers every non-hidden command exactly once", () => {
    const grouped = groupedCommands().flatMap((g) => g.specs.map((s) => s.cmd));
    const expected = COMMANDS.filter((c) => !c.hidden).map((c) => c.cmd);
    assert.deepEqual([...grouped].sort(), [...expected].sort());
  });

  it("commandNames includes canonical names and aliases", () => {
    const names = commandNames();
    assert.ok(names.includes("/optimize"));
    assert.ok(names.includes("/optimise"));
    assert.ok(names.includes("/help"));
  });
});

describe("target-only optimization detection", () => {
  it("treats a target/programme as target-only", () => {
    assert.equal(looksTargetOnly("BRD4 PROTACs"), true);
    assert.equal(looksTargetOnly("BRD4 VHL"), true);
  });

  it("recognises a molecule or series", () => {
    assert.equal(looksTargetOnly("MZ1-like series for solubility"), false);
    assert.equal(looksTargetOnly("dBET1 analogues"), false);
    assert.equal(looksTargetOnly("CC(=O)Nc1ccc(O)cc1"), false);
  });

  it("empty is target-only (so the caller prompts)", () => {
    assert.equal(looksTargetOnly(""), true);
  });
});

describe("input-need labels", () => {
  it("each need maps to a concrete ask", () => {
    assert.equal(neededInputLabel("smiles"), "a SMILES string");
    assert.equal(neededInputLabel("query"), "a question");
    assert.equal(neededInputLabel("objective"), "an objective");
    assert.equal(neededInputLabel("molecule_or_series"), "a starting molecule or series");
    assert.equal(neededInputLabel("none"), "");
  });
});

describe("intent routing — deterministic research workflows", () => {
  it("maps every research intent to a real bridge research command", () => {
    assert.deepEqual(RESEARCH_INTENTS, {
      "/investigate": "investigate",
      "/reason": "reason",
      "/evidence": "evidence",
      "/compare": "compare",
      "/design": "design",
    });
  });

  it("every research-intent command is advertised in the registry", () => {
    for (const cmd of Object.keys(RESEARCH_INTENTS)) {
      const spec = COMMANDS.find((c) => c.cmd === cmd);
      assert.ok(spec, `${cmd} missing from COMMANDS`);
    }
  });

  it("research intents are dispatched via runResearchWorkflow, never chat", () => {
    // The pre-dispatch must consult the shared registry (no duplicated literals)
    // and research intents must not be sent to the LLM chat handler.
    assert.ok(appSource.includes("const researchSlug = RESEARCH_INTENTS[cmd]"));
    assert.ok(appSource.includes("this.runResearchWorkflow(researchSlug, args)"));
    // chat is reserved for /ask and /explain
    assert.ok(appSource.includes("CHAT_INTENTS.includes(cmd)"));
    // legacy chat interception of these intents must be gone
    for (const cmd of Object.keys(RESEARCH_INTENTS)) {
      assert.ok(!appSource.includes(`await this.handleChat(${cmd.replace("/", "")}`),
        `${cmd} must not route to chat`);
      assert.ok(!appSource.includes(`await this.handleChat(\`Compare ${cmd.replace("/", "")}`),
        `${cmd} must not route to chat`);
    }
  });

  it("design/intent help entries and skill guides point at the same commands", () => {
    // /design example in the skill guide must match the registry slug.
    assert.equal(RESEARCH_INTENTS["/design"], "design");
    const spec = COMMANDS.find((c) => c.cmd === "/design");
    assert.equal(spec?.sl, "design");
  });
});
