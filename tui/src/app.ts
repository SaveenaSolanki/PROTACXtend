/**
 * PROTACXtend TUI Application v2 — "Laboratory Night" command centre.
 *
 * A complete targeted-protein-degradation research workflow system:
 *
 *   /plan · /investigate · /reason · /compare · /design · /optimize ·
 *   /structure · /selectivity · /degradation · /admet · /synthesis ·
 *   /experiment · /evidence · /run        ← primary research workflows
 *
 * Backend capabilities are preserved and routed through these
 * higher-level workflows (the low-level skill catalogue lives under
 * /skills and /skill). No runtime dependencies: pure Node + ANSI.
 */

import * as readline from "node:readline";
import { cpus, totalmem } from "node:os";
import { PythonBridge, type BridgeEvent } from "./bridge.js";
import { renderHeader, renderSimpleHeader, renderContract, type HeaderData } from "./header.js";
import { renderEvent, renderSkillsList } from "./events.js";
import { createTheme } from "./theme.js";
import {
  printLine,
  printInfo,
  printSuccess,
  printWarning,
  printError,
  printSection,
  printPanel,
  printKv,
  printRuleHeader,
  visibleWidth,
  truncateToWidth,
  padRight,
  centerText,
} from "./terminal.js";
import {
  RESEARCH_WORKFLOWS,
  WORKFLOW_INDEX,
  COMMANDS,
  commandNames,
  groupedCommands,
  resolveCommand,
  looksTargetOnly,
  neededInputLabel,
  RESEARCH_INTENTS,
  CHAT_INTENTS,
  type CommandSpec,
  type WorkflowInfo,
} from "./commands.js";

const theme = createTheme();

/** Phase chip for a stage name (KNOW/REASON/DESIGN/DISCOVER colouring). */
function typeChip(label: string): string {
  const t = (label || "").toLowerCase();
  const col =
    /(target|binder|warhead|evidence|investigate|resolve)/.test(t) ? "violet"
      : /(e3|linker|exit|reason|diagnos|mechanis)/.test(t) ? "purple"
        : /(construct|valid|degrad|admet|ternary|synthes|design|assemble)/.test(t) ? "cyan"
          : "mint";
  return theme.fg(col as "violet" | "purple" | "cyan" | "mint", `[${label}]`);
}

// ── Version & identity ───────────────────────────────────────────

const VERSION = "0.3.0";
const REPO_URL = "https://github.com/the-ahuja-lab/PROTACXtend";
const SITE_URL = "https://the-ahuja-lab.github.io/PROTACXtend";
const LAUNCH_URL = "https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/tui/launch.sh";

// ── Primary research workflows ───────────────────────────────────

// ── Primary research workflows (shared registry: ./commands.ts) ──

/** Objective prefix routed into the agent graph for each workflow. */
const WORKFLOW_PROMPT: Record<string, string> = {
  investigate: "Investigate",
  reason: "Reason mechanistically",
  compare: "Compare candidates",
  design: "Design",
  optimize: "Optimize",
  structure: "Structure / ternary analysis",
  selectivity: "Selectivity analysis",
  degradation: "Degradation prediction",
  admet: "ADMET assessment",
  synthesis: "Synthetic accessibility",
  experiment: "Design experiments",
  evidence: "Evidence synthesis",
  run: "Execute full workflow",
};

// ── Skill → recommended route (ids follow protacxtend/tui_bridge/events.py) ──

const SKILL_GUIDE: Record<string, { cmd: string; example: string }> = {
  target_resolution: { cmd: "/investigate", example: "/investigate BRD4 — target biology, structures, binders" },
  binder_search: { cmd: "/investigate", example: "/investigate BRD4 — binders, ligands, PROTAC-DB records" },
  warhead_selection: { cmd: "/design", example: "/design CRBN PROTACs for BRD4" },
  e3_ligand_selection: { cmd: "/design", example: "/design VHL PROTAC for EGFR" },
  exit_vector: { cmd: "/design", example: "/design a cereblon PROTAC for BRD4" },
  linker_generation: { cmd: "/generator", example: "/generator PEG linkers for BRD4 PROTAC" },
  molecular_construction: { cmd: "/design", example: "/design build PROTAC from pomalidomide" },
  stereochemistry: { cmd: "/stereo", example: "/stereo CC(=O)Nc1ccc(O)cc1" },
  degradation_prediction: { cmd: "/degradation", example: "/degradation predict DC50 for BRD4 PROTAC" },
  admet_prediction: { cmd: "/admet", example: "/admet CC(=O)Nc1ccc(O)cc1" },
  ternary_feasibility: { cmd: "/structure", example: "/structure BRD4 CRBN ternary feasibility" },
  docking: { cmd: "/docking", example: "/docking CC(=O)Nc1ccc(O)cc1 [target.pdb]" },
  retrosynthesis: { cmd: "/synthesis", example: "/synthesis CC(=O)Nc1ccc(O)cc1" },
  novelty_check: { cmd: "/design", example: "/design novelty-scored PROTAC BRD4" },
  ranker: { cmd: "/optimize", example: "/optimize rank the BRD4 design series" },
  diversity: { cmd: "/optimize", example: "/optimize diversify the BRD4 design series" },
  reporting: { cmd: "/report", example: "/report on the BRD4 run" },
  memory: { cmd: "/learn", example: "/learn keep logP < 3 for next designs" },
  linker_scanner: { cmd: "/generator", example: "/generator scan linkers x attachment points" },
  hook_effect: { cmd: "/degradation", example: "/degradation hook-effect aware dosing" },
  cooperativity: { cmd: "/structure", example: "/structure BRD4 CRBN cooperativity" },
  proteome_selectivity: { cmd: "/selectivity", example: "/selectivity cell-context aware BRD4" },
  p4ward: { cmd: "/structure", example: "/structure full P4ward ternary simulation" },
};

// ── Help catalogue ───────────────────────────────────────────────

// ── Main App ─────────────────────────────────────────────────────

export class ProtacXtendApp {
  private bridge: PythonBridge;
  private rl: readline.Interface | null = null;
  private running = false;
  private prompt = "PROTACXtend> ";
  private agentCount = 23;
  private toolCount = 73;
  private skillsCount = 0;
  private databaseCount = 0;
  private agents: string[] = [];
  private workflows: { cmd: string; desc: string }[] = [];
  private lastActivity = "";
  private skillsCache: Record<string, unknown>[] | null = null;
  private latestSchema: Record<string, unknown> | null = null;
  private llmLabel = "";
  private pendingPlanClarification = false;
  private conversationId = "tui-default";

  constructor() {
    this.bridge = new PythonBridge();
    this.setupBridgeHandlers();
  }

  private setupBridgeHandlers(): void {
    this.bridge.on("event", (event: BridgeEvent) => {
      renderEvent(event as Record<string, unknown>);
      this.onBridgeEvent(event);
    });

    this.bridge.on("stderr", (msg: string) => {
      if (msg.includes("Error") || msg.includes("Traceback")) {
        printWarning(`backend: ${truncateToWidth(msg, 58)}`);
      }
    });

    this.bridge.on("error", (err: Error) => {
      printError(`Bridge error: ${err.message}`);
    });

    this.bridge.on("exit", (code: number | null) => {
      if (code !== 0 && code !== null) {
        printWarning(`Python backend exited with code ${code}`);
      }
    });
  }

  /** Route non-rendered events to app-level panels. */
  private onBridgeEvent(event: BridgeEvent): void {
    switch (event.type) {
      case "agents": {
        const list = (event.agents as Array<Record<string, unknown>>) || [];
        this.agents = list.map((a) => String(a.name ?? a.id ?? "")).filter(Boolean);
        if (list.length) this.agentCount = list.length;
        break;
      }
      case "workflows": {
        const list = (event.workflows as Array<{ cmd: string; desc: string }>) || [];
        if (list.length) this.workflows = list;
        break;
      }
      case "results":
        this.showResults(event as Record<string, unknown>);
        break;
      case "skills_list":
        this.skillsCache = (event.skills as Record<string, unknown>[]) || [];
        this.skillsCount = this.skillsCache.length;
        break;
      case "tool_result": {
        const payload = event.result as Record<string, unknown> | undefined;
        if (payload && typeof payload.workflow === "string" && typeof payload.summary === "string") {
          this.latestSchema = payload;
        }
        break;
      }
      case "scientific_result": {
        const sr = event.result as Record<string, unknown> | undefined;
        if (sr && sr.workflow) this.latestSchema = sr;
        break;
      }
      case "compare_result":
        this.renderComparePanel((event.payload as Record<string, unknown>) || {});
        break;
      case "databases_list":
        this.databaseCount = ((event.databases as Record<string, unknown>[]) || []).length;
        break;
      default:
        break;
    }
  }

  /** Ask backend for a payload and resolve when the matching event arrives. */
  private ask(type: string, want: string[], timeoutMs = 10_000,
               extra: Record<string, unknown> = {},
               match?: (event: BridgeEvent) => boolean): Promise<Record<string, unknown> | undefined> {
    return new Promise((resolve) => {
      const onEvent = (event: BridgeEvent) => {
        const wanted = want.includes(event.type as string);
        if (wanted && (match ? match(event) : true)) {
          cleanup();
          resolve(event as Record<string, unknown>);
        }
      };
      const cleanup = () => {
        clearTimeout(timer);
        this.bridge.removeListener("event", onEvent);
      };
      const timer = setTimeout(() => {
        cleanup();
        resolve(undefined);
      }, timeoutMs);
      this.bridge.on("event", onEvent);
      try {
        this.bridge.send(type, extra);
      } catch {
        cleanup();
        resolve(undefined);
      }
    });
  }

  async start(): Promise<void> {
    printInfo("Starting PROTACXtend backend…");
    try {
      await this.bridge.start();
    } catch (err) {
      printError(`Failed to start backend: ${err instanceof Error ? err.message : err}`);
      printInfo("Falling back to simple mode.");
      this.runSimpleMode();
      return;
    }

    // Prime the header with real backend data (no panels — drawn after header)
    const status = await this.ask("status", ["status"], 12_000);
    if (status) {
      this.agentCount = Number(status.agents ?? this.agentCount);
      this.skillsCount = Number(status.skills ?? 0);
      this.databaseCount = Number(status.databases ?? 0);
      const llm = status.llm as Record<string, unknown> | undefined;
      if (llm) {
        const provider = String(llm.provider ?? "").trim();
        const model = String(llm.model ?? "").trim();
        if (provider && provider !== "(none)") {
          this.llmLabel = `${provider}${model ? `/${model}` : ""}${llm.healthy ? "" : " (unreachable)"}`;
        } else {
          this.llmLabel = "not configured \u2014 run: protacxtend setup";
        }
      }
    }
    await this.ask("agents", ["agents"]);
    await this.ask("workflows", ["workflows"]);

    await this.printHeader();
    this.runInteractive();
  }

  private async printHeader(): Promise<void> {
    const termWidth = this.termWidth();
    const session = new Date().toISOString().slice(0, 19).replace("T", " · ");
    const mem = Math.round(totalmem() / 1024 ** 3);
    const data: HeaderData = {
      model: process.env.PROTACXTEND_MODEL || this.llmLabel || "not configured \u2014 run: protacxtend setup",
      directory: process.cwd(),
      session,
      system: `${cpus().length} cores · ${mem} GB RAM${process.env.PROTACXTEND_GPU ? ` · ${process.env.PROTACXTEND_GPU}` : ""}`,
      agentCount: this.agentCount,
      toolCount: this.toolCount,
      skillsCount: this.skillsCount || undefined,
      agents: this.agents.length > 0 ? this.agents : [
        "Supervisor", "Planner", "Target Resolver", "Binder Retrieval",
        "Warhead Selection", "E3 Ligand", "Linker", "Construction",
        "Ranking", "Report",
      ],
      workflows: this.workflows.length > 0
        ? this.workflows
        : RESEARCH_WORKFLOWS.map((w) => ({ cmd: w.cmd, desc: w.desc })),
      lastActivity: this.lastActivity || undefined,
    };

    const lines = renderHeader(data, termWidth);
    for (const line of lines) printLine(line);
  }


  /** Safe terminal width (guard against 0/undefined reported by non-real ttys). */
  private termWidth(): number {
    const w = process.stdout.columns ?? 0;
    return w >= 30 ? w : 100;
  }

  // ── REPL ───────────────────────────────────────────────────────

  private commandHints(): string[] {
    const list = new Set<string>(commandNames());
    for (const k of Object.keys(SKILL_GUIDE)) list.add(`/skill ${k}`);
    return [...list];
  }

  private runInteractive(): void {
    const hints = this.commandHints();
    this.rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      prompt: this.prompt,
      completer: (line: string) => {
        const hits = hints.filter((c) => c.startsWith(line.trim()));
        return [hits.length ? hits : hints.slice(0, 8), line];
      },
    });

    this.running = true;
    this.rl.prompt();

    this.rl.on("line", async (input: string) => {
      const trimmed = input.trim();
      if (!trimmed) {
        this.rl?.prompt();
        return;
      }
      await this.handleInput(trimmed);
      if (this.running) this.rl?.prompt();
    });

    this.rl.on("close", () => {
      this.running = false;
      this.bridge.stop();
    });

    process.on("SIGINT", () => {
      printLine("");
      printInfo("Use /quit to exit.");
      this.rl?.prompt();
    });
  }

  private async handleInput(input: string): Promise<void> {
    // Context update: "actually use VHL" or "use VHL" changes E3 only (spec §13).
    const e3Update = input.match(/^(?:actually\s+)?use\s+([A-Za-z][A-Za-z0-9]*)\s*$/i);
    if (e3Update) {
      const e3 = e3Update[1].toUpperCase();
      const ev = await this.ask("context", ["context_answer"], 12_000,
        { action: "set_e3", e3, conversation_id: this.conversationId ?? "tui-default" });
      if (ev) {
        printInfo(`E3 context updated: ${String(ev.old_e3 ?? "(none)")} → ${String(ev.new_e3 ?? e3)}`);
        const c = ev.context as Record<string, unknown> | undefined;
        if (c?.target_symbol) printInfo(`Context: target ${String(c.target_symbol)} · E3 ${String(c.e3)}`);
      } else printWarning("Context backend did not answer.");
      return;
    }
    if (input.startsWith("/")) {
      await this.handleCommand(input);
    } else {
      // While a plan is waiting for a correction (e.g. "EFRG" -> "EGFR"),
      // the very next free-text message is an answer to the plan, not general
      // chat. The plan backend applies "latest explicit correction wins".
      if (this.pendingPlanClarification) {
        this.pendingPlanClarification = false;
        const plan = await this.ask("plan", ["plan_answer", "plan_complete"], 60000,
          { request: input, conversation_id: this.conversationId });
        if (plan) this.renderPlanAnswer(plan as Record<string, unknown>);
        return;
      }
      // Free text is conversational — answered by the LLM agent, exactly like
      // Pi/Feynman. Explicit workflow verbs (/design, /run, …) still drive the
      // deterministic agent graph.
      await this.handleChat(input);
    }
  }

  // ── Commands ───────────────────────────────────────────────────

  private async handleCommand(input: string): Promise<void> {
    // ONE registry drives normalization, aliases and dispatch (./commands.ts).
    const { name, spec, args } = resolveCommand(input);
    if (!spec) {
      printWarning(`Unknown command: ${name || "(empty)"}`);
      printInfo("Type /help for the command centre.");
      return;
    }
    const cmd = spec.cmd;

    // Argument gate: a command that needs input must ask for it (or offer a
    // target-only workflow) rather than silently no-op.
    if (spec.needs !== "none" && !args) {
      this.promptForInput(spec);
      return;
    }

    // ── intent routing (single registry, used by the routing tests too) ──
    // Deterministic research workflows route to their bridge handlers
    // (design|investigate|reason|evidence|compare) — the shared engine, never
    // the chat agent. Conversational intents (/ask, /explain) use chat.
    const researchSlug = RESEARCH_INTENTS[cmd];
    if (researchSlug) {
      if (cmd === "/compare" && (!args || /case-study|benchmark|\.csv$/i.test(args))) {
        await this.runCompare(args || "");
        return;
      }
      if (args) {
        await this.runResearchWorkflow(researchSlug, args);
        return;
      }
      return; // no-args case was handled by the needs gate above
    }
    if (CHAT_INTENTS.includes(cmd)) {
      if (cmd === "/explain" && /^run_[A-Za-z0-9_-]+$/i.test(args)) {
        // Typed explanation for a persisted run: bridge handle_explain reads
        // outputs/runs/<run_id> and emits an "explain" payload.
        printInfo(`Reading persisted run ${args} …`);
        const ev = await this.ask("explain", ["explain"], 60_000, { run: args });
        if (ev) this.renderExplanation(ev as Record<string, unknown>);
        else printWarning("Explanation backend did not answer in time.");
        return;
      }
      if (args) await this.handleChat(args);
      else this.showUsage(cmd, "a scientific question", `${cmd} what is BRD4 and why is it a PROTAC target?`);
      return;
    }

    switch (cmd) {
      case "/help":
        this.showHelp();
        break;
      case "/about":
        this.showAbout();
        break;
      case "/launch":
        this.showLaunch();
        break;
      case "/status":
      case "/models": {
        printInfo("Requesting system status…");
        const ev = await this.ask("status", ["status"]);
        if (ev) this.renderStatusPanel(ev);
        else printWarning("No status payload received from backend.");
        break;
      }
      case "/agents": {
        printInfo("Requesting agent pipeline…");
        const ev = await this.ask("agents", ["agents"]);
        if (ev) this.renderAgentsPanel(ev);
        else printWarning("No agents payload received.");
        break;
      }
      case "/doctor":
        await this.runDoctor(args.toLowerCase().includes("json"));
        break;
      case "/workflows": {
        printInfo("Requesting workflow catalogue…");
        const ev = await this.ask("workflows", ["workflows"]);
        if (ev) this.renderWorkflowsPanel(ev);
        else {
          this.renderWorkflowsPanel({ workflows: RESEARCH_WORKFLOWS.map((w) => ({ cmd: w.cmd, desc: w.desc })) });
        }
        break;
      }
      case "/skills": {
        printInfo("Opening the scientific skill catalogue…");
        const ev = await this.ask("skills", ["skills_list"]);
        if (!ev) {
          if (this.skillsCache && this.skillsCache.length) {
            renderSkillsList(this.skillsCache);
          } else {
            printWarning("Skill catalogue not received from backend.");
          }
        }
        break;
      }
      case "/databases": {
        printInfo("Opening data sources…");
        const ev = await this.ask("databases", ["databases_list"]);
        if (!ev) printWarning("Database list not received from backend.");
        break;
      }
      case "/skill": {
        const tokens = input.split(/\s+/).slice(1);
        const id = tokens[0] ?? "";
        const skillArgs = tokens.slice(1).join(" ");
        await this.runSkill(id, skillArgs);
        break;
      }

      // ── primary research workflows ──
      case "/therapeutics": {
        const tokens = (args || "").split(/\s+/).filter(Boolean);
        // /therapeutics KRAS G12C  -> target=KRAS, variant=G12C
        const target = tokens[0] || "";
        const rest = tokens.slice(1).join(" ");
        const ev = await this.ask("therapeutics", ["therapeutics_answer"], 30000,
          { target: rest ? `${target} ${rest}` : target });
        if (ev && ev.verdict) {
          printInfo(`assessment ${ev.verdict} — gates: ${JSON.stringify(ev.gates)}`);
          if (ev.rationale) printInfo(String(ev.rationale).slice(0, 200));
        } else printWarning("No assessment answer from backend.");
        break;
      }
      case "/plan":
        if (args) {
          this.pendingPlanClarification = true;
          const plan = await this.ask("plan", ["plan_answer", "plan_complete"], 60000,
            { request: args, conversation_id: this.conversationId ?? "tui-default" });
          if (plan) {
            this.renderPlanAnswer(plan as Record<string, unknown>);
          } else {
            printWarning("Plan backend did not answer in time.");
          }
        } else this.showPlan();
        break;
      // Intent routing (/investigate /reason /explain /ask /compare /design
      // /evidence) is handled by RESEARCH_INTENTS / CHAT_INTENTS above the
      // switch — single registry shared with the routing tests.
      case "/optimize":
        // Target-only optimization has no starting molecule: route to the
        // target-only design workflow and say so explicitly.
        if (looksTargetOnly(args)) {
          printWarning("Optimize needs a starting molecule or series; only a target/programme was given.");
          printInfo(`Routing to the design workflow instead: /design ${args}`);
          await this.runResearchWorkflow("design", args);
        } else {
          await this.runWorkflow("optimize", args);
        }
        break;
      case "/structure":
        await this.runWorkflow("structure", args);
        break;
      case "/selectivity":
        await this.runWorkflow("selectivity", args);
        break;
      case "/degradation":
        await this.runWorkflow("degradation", args);
        break;
      case "/admet":
        await this.runWorkflow("admet", args);
        break;
      case "/synthesis":
        await this.runWorkflow("synthesis", args);
        break;
      case "/experiment":
        await this.runWorkflow("experiment", args);
        break;
      case "/run":
        if (/^plan_[A-Za-z0-9_-]+$/.test(args || "")) {
          printInfo(`Executing persisted plan ${args} …`);
          const ev = await this.ask("run", ["run_answer"], 120_000, { request: args });
          if (ev) {
            printInfo(`Plan ${String(args)} — ${String(ev.conclusion ?? "")}`);
            const stages = (ev.executed_stages as Array<Record<string, unknown>>) || [];
            for (const st of stages.slice(0, 12)) {
              printLine(`  ${theme.dim(String(st.stage))}  ${theme.semantic("text", String(st.status ?? ""))}`);
            }
          } else printWarning("run backend did not answer in time.");
          return;
        }
        if (/brd4-vhl-(case-study|benchmark)/i.test(args)) {
          await this.runCompare("");
        } else {
          await this.runWorkflow("run", args);
        }
        break;

      // ── low-level skill tools (kept for direct access) ──
      case "/validate":
        if (args) this.bridge.send("validate", { smiles: args });
        else this.showUsage(cmd, "<SMILES>", "/validate CC(=O)Nc1ccc(O)cc1");
        break;
      case "/retro":
        if (args) this.bridge.send("retrosynthesis", { smiles: args });
        else this.showUsage(cmd, "<SMILES>", "/retro CC(=O)Nc1ccc(O)cc1");
        break;
      case "/docking":
        if (args) {
          const [smiles, target] = args.split(/\s+/);
          this.bridge.send("docking", { smiles, target: target || "" });
        } else {
          this.showUsage(cmd, "<SMILES> [target.pdb]", "/docking CC(=O)Nc1ccc(O)cc1 7q1c.pdb");
        }
        break;
      case "/stereo":
        if (args) this.bridge.send("stereo", { smiles: args });
        else this.showUsage(cmd, "<SMILES>", "/stereo CC(=O)Nc1ccc(O)cc1");
        break;
      case "/generator":
        if (args) this.bridge.send("generator", { request: args });
        else this.showUsage(cmd, "<request>", "/generator rigid triazole linkers");
        break;
      case "/cellctx":
        if (args) await this.handleDesignRequest(`Cell-context scoring: ${args}`);
        else this.showUsage(cmd, "a target/E3 pair", "BRD4 CRBN in MDA-MB-231");
        break;
      case "/rank":
        if (args) await this.handleDesignRequest(`Rank candidates: ${args}`);
        else this.showUsage(cmd, "a ranking objective", "rank top BRD4 PROTACs by DC50 + ADMET");
        break;
      case "/learn":
        this.showLearn(args);
        break;
      case "/report":
        // `/report run_xxxx` reads the persisted run; a free-text objective still
        // generates a report through the graph.
        if (!args) {
          printInfo("Opening the latest persisted run\u2026");
          this.bridge.send("report", { run_id: "" });
        } else if (/^run_[A-Za-z0-9_-]+$/i.test(args) || args.includes("/")) {
          printInfo(`Opening persisted run ${args}\u2026`);
          this.bridge.send("report", { run_id: args.trim() });
        } else {
          await this.handleDesignRequest(`Generate report: ${args}`);
        }
        break;
      case "/contract":
        this.showContract();
        break;

      case "/clear":
        process.stdout.write("\x1b[2J\x1b[H");
        this.bridge.send("chat_reset", {});
        await this.printHeader();
        break;
      case "/quit":
      case "/exit":
        this.running = false;
        this.bridge.stop();
        printSuccess("Goodbye — evidence over everything.");
        process.exit(0);
        break;
      default:
        printWarning(`Unknown command: ${cmd}`);
        printInfo("Type /help for the command centre.");
    }
  }

  private showUsage(cmd: string, what: string, example: string): void {
    printInfo(`Usage: ${cmd} ${what}`);
    printLine(`  ${theme.dim("example")}  ${theme.semantic("text", example)}`);
  }

  /** Ask for the specific missing input; never silently no-op. */
  private promptForInput(spec: CommandSpec): void {
    const label = neededInputLabel(spec.needs);
    const usage = spec.usage ? ` ${spec.usage}` : "";
    printLine("");
    printWarning(`${spec.cmd} needs ${label}.`);
    printInfo(`Usage: ${spec.cmd}${usage}`);
    const example = spec.sl ? WORKFLOW_INDEX[spec.sl]?.example : undefined;
    if (example) printLine(`  ${theme.dim("example")}  ${theme.semantic("text", example)}`);
    if (spec.needs === "smiles") {
      printInfo(`Provide a molecule, e.g. ${spec.cmd} CC(=O)Nc1ccc(O)cc1`);
    } else if (spec.needs === "molecule_or_series") {
      printInfo("Give a starting molecule or series, e.g. /optimize MZ1-like series for solubility.");
      printInfo("Target-only option: /design <target> [E3] generates candidates instead.");
    } else if (spec.sl) {
      printInfo("Target-only option: /design <target> [E3] runs the design workflow.");
    }
    printLine("");
  }

  /** /evidence — expose provenance + evidence from the last schema result. */
  private showEvidenceProvenance(): void {
    const sr = this.latestSchema;
    printLine("");
    printLine(`  ${theme.grad("EVIDENCE & PROVENANCE", "#9B94F0", "#5AB9CD")}`);
    if (!sr) {
      printLine(`  ${theme.dim("No result captured yet in this session.")}`);
      printInfo("Run /design <objective>, a tool (/validate, /admet …) or /evidence <query> first.");
      printLine("");
      return;
    }
    const evidence = (sr.evidence as Array<Record<string, unknown>>) || [];
    const provenance = (sr.provenance as Array<Record<string, unknown>>) || [];
    const warnings = (sr.warnings as string[]) || [];

    printKv("workflow", theme.semantic("text", String(sr.workflow ?? "")), 14);
    printKv("status", String(sr.status ?? ""), 14);
    printKv("summary", theme.semantic("text", truncateToWidth(String(sr.summary ?? ""), 66)), 14);
    if (sr.confidence !== undefined && sr.confidence !== null) {
      printKv("confidence", `${((Number(sr.confidence)) * 100).toFixed(0)}% (reported by model)`, 14);
    }
    if (Array.isArray(sr.uncertainty) && sr.uncertainty.length) {
      printKv("uncertainty", theme.dim((sr.uncertainty as string[]).join(" · ")), 14);
    }

    if (evidence.length) {
      printSection("EVIDENCE");
      const kinds: Record<string, string> = {
        measured: "mint", retrieved: "cyan", calculated: "violet", predicted: "purple", missing: "amber",
      };
      for (const e of evidence) {
        const kind = String(e.kind ?? "retrieved");
        const chip = theme.fg((kinds[kind] as "mint" | "cyan" | "violet" | "purple" | "amber") ?? "cyan", `[${kind}]`);
        printLine(`  ${chip} ${theme.semantic("text", String(e.summary ?? ""))}`);
        const src = String(e.source ?? "");
        if (src) printLine(`      ${theme.dim("source")} ${src}`);
        const ref = String(e.reference ?? "");
        if (ref) printLine(`      ${theme.dim("ref")} ${ref}`);
      }
    } else {
      printLine(`  ${theme.muted("no evidence items attached to this result")}`);
    }

    if (warnings.length) {
      printSection("WARNINGS");
      for (const w of warnings) printLine(`  ${theme.warning("\u26a0")} ${theme.dim(String(w))}`);
    }
    if (provenance.length) {
      printSection("PROVENANCE");
      for (const p of provenance) {
        const tool = String(p.tool ?? "");
        const source = String(p.source ?? "");
        printLine(`  ${theme.fg("mint", tool)}${source ? theme.dim(`  ·  ${source}`) : ""}`);
      }
    } else {
      printLine(`  ${theme.muted("no provenance recorded (nothing was invented here)")}`);
    }
    printLine("");
  }

  /** /compare <six-protac-file> · /run brd4-vhl-case-study (alias: brd4-vhl-benchmark) */
  private async runCompare(path: string): Promise<void> {
    printInfo(`Running BRD4\u2013VHL prospective case study${path ? ` \u2190 ${path}` : " (bundled blinded dataset)"}…`);
    const ev = await this.ask("compare", ["compare_result"], 60_000, { path });
    if (!ev) {
      printWarning("Benchmark did not return a result — check the dataset path.");
      return;
    }
    // renderComparePanel runs via onBridgeEvent when the payload arrives;
    // ask resolves on the same event so nothing else is needed here.
  }

  private renderComparePanel(payload: Record<string, unknown>): void {
    const ranking = (payload.ranking as Array<Record<string, unknown>>) || [];
    const stages = (payload.stages as Array<Record<string, unknown>>) || [];
    const cls = (payload.classification as Record<string, unknown>) || {};
    const unc = (payload.uncertainty as string[]) || [];
    const winner = (payload.winner as Record<string, unknown>) || {};

    printLine("");
    printLine(`  ${theme.grad("BRD4 \u2013 VHL SIX-PROTAC PROSPECTIVE CASE STUDY", "#9B94F0", "#5AB9CD")}  ${theme.dim("· NOT a benchmark · no ground truth")}`);
    printLine(`  ${theme.dim("dataset")}  ${theme.semantic("text", truncateToWidth(String(payload.dataset ?? ""), 70))}`);
    printRuleHeader("EVIDENCE TYPE ACCOUNTING");
    const label: Record<string, string> = {
      measured: theme.success("measured"), retrieved: theme.fg("cyan", "retrieved"),
      calculated: theme.fg("violet", "calculated"), predicted: theme.fg("purple", "predicted"),
      missing: theme.warning("missing"),
    };
    printLine(`  ${Object.entries(label).map(([k, v]) => `${v} ${String(cls[k] ?? 0)}`).join("   ")}`);
    printLine("");
    for (const st of stages) {
      const ph = String(st.phase ?? "");
      const pc = ph === "KNOW" ? "violet" : ph === "REASON" ? "purple" : ph === "DESIGN" ? "cyan" : "mint";
      printLine(`  ${theme.fg(pc, `[${ph}]`)} ${theme.dim(String(st.note ?? ""))}`);
    }
    printLine("");

    printRuleHeader("PREDICTED RANKING — LOCK BEFORE WET-LAB OUTCOME ACCESS");
    const headW = 70;
    for (const row of ranking) {
      const rank = theme.accent(`#${String(row.rank)}`);
      const id = theme.semantic("text", padRight(String(row.id ?? ""), 7));
      const score = theme.fg("cyan", String(row.score));
      const band = theme.dim(truncateToWidth(String(row.band ?? ""), 26));
      const vhl = String(row.vhl_ligand_status ?? "") === "modified"
        ? theme.error("[VHL modified]") : theme.success("[VHL intact]");
      printLine(`  ${rank}  ${id} ${score}  ${band}  ${vhl}`);
      const adv = String(row.advantage ?? "");
      const liab = String(row.liability ?? "");
      if (adv && adv !== "None") printLine(`      ${theme.dim("strength")} ${truncateToWidth(adv, headW)}`);
      if (liab && liab !== "None") printLine(`      ${theme.dim("liability")} ${truncateToWidth(liab, headW)}`);
    }
    printLine("");
    printLine(`  ${theme.accent("TOP")}  ${theme.semantic("text", String(winner.name ?? winner.id ?? "?"))}  ${theme.fg("cyan", String(winner.score ?? ""))}  ${theme.dim(String(winner.band ?? ""))}`);
    printLine(`  ${theme.dim("Lock: this predicted ranking is provisional and will be frozen before any wet-lab outcome is accessed.")}`);
    printSection("UNCERTAINTY & NEXT EXPERIMENTS");
    for (const u of unc) printLine(`  ${theme.warning("\u26a0")} ${theme.dim(truncateToWidth(u, 78))}`);
    printLine(`  ${theme.dim("Next: measure DC50/Dmax in a VHL-proficient line (e.g. H1299) with DMSO controls to convert these predictions into measured evidence.")}`);
    printLine("");
  }

  // ── Research workflow dispatcher (deterministic handlers) ──────────

  /**
   * Route a research-workflow command to its deterministic bridge handler
   * (design|investigate|reason|compare|evidence|…), waiting for the typed
   * research_answer event. These handlers run through
   * protacxtend.workflows.api.run_command — the SAME engine the CLI and API
   * use — and persist artifacts + evidence graphs; this is intent routing,
   * never a second implementation (and never chat).
   */
  private async runResearchWorkflow(slug: string, args: string): Promise<void> {
    const wf = WORKFLOW_INDEX[slug];
    const label = wf ? `${wf.cmd}` : `/${slug}`;
    printInfo(`${label} → deterministic engine · ${truncateToWidth(args, 64)}`);
    // Terminal events per bridge handler: handle_research emits
    // research_answer; handle_diagnose (reason) emits diagnosis_answer.
    const terminal: Record<string, string[]> = {
      design: ["research_answer"],
      investigate: ["research_answer", "investigate_answer"],
      reason: ["diagnosis_answer", "research_answer"],
      evidence: ["research_answer"],
      compare: ["research_answer"],
    };
    const ev = await this.ask(slug, terminal[slug] ?? ["research_answer"], 300_000, {
      request: args,
      conversation_id: this.conversationId ?? "tui-default",
    }, (event) => {
      // Correlation: research_answer events carry the command slug; never
      // let a concurrent workflow's response resolve another workflow's ask.
      if (event.type !== "research_answer") return true;
      return String(event.command) === slug;
    });
    if (!ev) {
      printWarning(`${label} did not return a research_answer in time.`);
      return;
    }
    this.latestSchema = ev;
    if (ev.type === "diagnosis_answer") {
      this.renderDiagnosisAnswer(ev as Record<string, unknown>);
    } else {
      this.renderResearchAnswer(ev as Record<string, unknown>);
    }
  }

  /**
   * Full plan rendering: interpretation, task list, open questions/blockers,
   * stage statuses and persisted artifacts. Resource-selection logs
   * (resource_reason_summary) are never rendered as the scientific answer.
   */
  private renderPlanAnswer(ev: Record<string, unknown>): void {
    const interp = String(ev.interpretation ?? "").replace(/\n/g, " · ").trim();
    if (interp) printInfo(interp);
    const tasks = (ev.tasks as Array<Record<string, unknown>>) || [];
    const blockers = ((ev.open_questions as Array<unknown>) || []).map(String);
    const stages: Record<string, string> = {};
    for (const s of ((ev.stage_timeline as Array<Record<string, unknown>>) || [])) {
      if (s && s.stage) stages[String(s.stage)] = String(s.status ?? "");
    }
    const artifactMap = (ev.artifact_paths as Record<string, unknown>) || {};
    const artifacts = Object.values(artifactMap).map(String).filter(Boolean);

    if (tasks.length) {
      printSection("PLAN TASKS");
      for (const t of tasks.slice(0, 12)) {
        const tid = String(t.id ?? "?");
        const title = truncateToWidth(String(t.title ?? ""), 50);
        const ex = String(t.executor ?? "");
        printLine(`  ${theme.accent(tid)}  ${theme.semantic("text", title)}  ${theme.dim(ex)}`);
      }
      if (tasks.length > 12) printLine(`  ${theme.dim(`… and ${tasks.length - 12} more; full plan: plan.json`)}`);
    }
    if (blockers.length) {
      printSection("OPEN QUESTIONS / BLOCKERS");
      for (const q of blockers.slice(0, 6)) {
        printLine(`  ${theme.warning("?")} ${theme.semantic("text", truncateToWidth(q, 74))}`);
      }
    }
    if (Object.keys(stages).length) {
      printSection("STAGE STATUS");
      for (const [st, sts] of Object.entries(stages)) {
        printLine(`  ${typeChip(st)}  ${theme.dim(sts)}`);
      }
    }
    if (artifacts.length) {
      printSection("PERSISTED ARTIFACTS");
      for (const v of artifacts.slice(0, 6)) printLine(`  ${theme.fg("mint", "✓")} ${theme.dim(truncateToWidth(v, 74))}`);
    }
    const planSecs = (ev.plan_sections as Record<string, unknown>) || {};
    const planStages = (planSecs.workflow_stages as Array<Record<string, unknown>>) || [];
    if (planStages.length) {
      printSection("PLAN STAGES (ORDERED)");
      for (const st of planStages) {
        const ex = st.expensive_to_execute ? theme.warning(" [run-only]") : "";
        printLine(`  ${theme.accent(String(st.stage))}${ex}`);
        if (st.gate) printLine(`      ${theme.dim("gate:".padEnd(6))} ${theme.semantic("text", String(st.gate))}`);
        const tasks = (st.tasks as string[]) || [];
        if (tasks.length) printLine(`      ${theme.dim("tasks:".padEnd(6))} ${theme.dim(tasks.join(", "))}`);
      }
      const exp = (planSecs.expensive_stages_require_run as string[]) || [];
      if (exp.length) printLine(`  ${theme.warning("expensive stages require /run or /design:")} ${theme.dim(exp.join("; "))}`);
      if (ev.plan_object_path) printLine(`  ${theme.fg("mint", "✓")} ${theme.dim(`plan persisted: ${String(ev.plan_object_path)}`)}`);
    }
  }

  /** diagnosis_answer renderer (reason handler payload). */
  private renderDiagnosisAnswer(ev: Record<string, unknown>): void {
    const command = String(ev.command ?? "reason");
    printLine("");
    const intent = String(ev.intent ?? "");
    printLine(`  ${theme.grad("MECHANISTIC REASONING", "#9B94F0", "#5AB9CD")}  ${theme.dim(command)}  ${theme.dim(intent)}`);
    if (ev.case) printLine(`  ${theme.dim("case".padEnd(10))} ${theme.semantic("text", String(ev.case))}`);

    // ── semantic sections (intent-driven) take precedence over legacy template ──
    const sections = (ev.sections as Array<Record<string, unknown>>) || [];
    if (sections.length) {
      this.renderSections(sections);
      if (ev.conclusion && typeof ev.conclusion === "object") {
        const c = ev.conclusion as Record<string, unknown>;
        printSection("CONCLUSION");
        printLine(`  ${theme.accent("→")} ${theme.semantic("text", truncateToWidth(String(c.rationale ?? ""), 76))}`);
        if (c.confidence) printLine(`  ${theme.dim("confidence".padEnd(10))} ${theme.semantic("text", String(c.confidence))}`);
      }
      printLine("");
      return;
    }

    // ── row-level direct evidence (answers "which PROTAC works for X") ──
    const direct = (ev.scientific_direct_answer as string[]) || [];
    if (direct.length) {
      printSection("DIRECT EVIDENCE ROWS");
      for (const d of direct.slice(0, 7)) printLine(`  ${theme.fg("mint", "·")} ${theme.semantic("text", truncateToWidth(String(d), 78))}`);
    }
    const gap = String(ev.evidence_gap_conclusion ?? "").trim();
    if (gap) {
      printSection("EVIDENCE GAP");
      printLine(`  ${theme.fg("mint", "·")} ${theme.semantic("text", truncateToWidth(gap, 78))}`);
    }
    if (ev.case_source) printLine(`  ${theme.dim(`case source: ${String(ev.case_source)}`)}`);

    const hypotheses = (ev.hypotheses as Array<Record<string, unknown>>) || [];
    const tests = (ev.tests as Array<Record<string, unknown>>) || [];
    if (hypotheses.length) {
      printSection("HYPOTHESES");
      for (const h of hypotheses.slice(0, 6)) {
        const axis = String(h.axis ?? "");
        const label = String(h.label ?? h.title ?? h.statement ?? "").trim();
        if (!label) continue; // never render the "H ?" placeholder
        printLine(`  ${theme.fg("purple", "H")} ${theme.semantic("text", truncateToWidth(label, 60))} ${theme.dim(axis)}`);
        const rationale = String(h.rationale ?? "").trim();
        if (rationale) printLine(`      ${theme.dim("rationale")} ${theme.semantic("text", truncateToWidth(rationale, 66))}`);
        const htests = (h.discriminating_tests as Array<unknown>) || [];
        if (htests.length) printLine(`      ${theme.dim("test")} ${theme.semantic("text", truncateToWidth(String(htests[0]), 72))}`);
      }
    }
    if (tests.length) {
      printSection("DISCRIMINATING TESTS");
      for (const t of tests.slice(0, 5)) {
        const txt = String(t.test ?? t.name ?? "").trim();
        if (!txt) continue;
        printLine(`  ${theme.fg("mint", "→")} ${theme.semantic("text", truncateToWidth(txt, 72))}`);
      }
    }
    if (ev.recommended_action) {
      printSection("RECOMMENDED ACTION");
      printLine(`  ${theme.accent("→")} ${theme.semantic("text", truncateToWidth(String(ev.recommended_action), 78))}`);
    }
    const gated = ((ev.gated as Array<unknown>) || []).map(String).filter(Boolean);
    if (gated.length) printLine(`  ${theme.dim("gated".padEnd(10))} ${theme.warning(gated.join(" · "))}`);
    if (ev.summary && typeof ev.summary === "object") {
      const s = ev.summary as Record<string, unknown>;
      if (s.note) printLine(`  ${theme.dim(String(s.note))}`);
    }
    const diagTimeline = (ev.stage_timeline as Array<Record<string, unknown>>) || [];
    if (diagTimeline.length) {
      printSection("STAGE STATUS");
      for (const s of diagTimeline) {
        printLine(`  ${typeChip(String(s.stage ?? ""))}  ${theme.dim(String(s.status ?? ""))}`);
      }
    }
    const diagArtifactMap = (ev.artifact_paths as Record<string, unknown>) || {};
    const diagArtifacts = Object.values(diagArtifactMap).map(String).filter(Boolean);
    if (ev.evidence_graph) diagArtifacts.push(String(ev.evidence_graph));
    if (diagArtifacts.length) {
      printSection("PERSISTED ARTIFACTS");
      for (const v of diagArtifacts.slice(0, 6)) printLine(`  ${theme.fg("mint", "✓")} ${theme.dim(truncateToWidth(v, 74))}`);
    }
    printLine("");
  }

  /** Typed explanation renderer (bridge handle_explain payload). */
  private renderExplanation(ev: Record<string, unknown>): void {
    const runId = String(ev.run_id ?? "");
    const outcome = String(ev.scientific_outcome ?? ev.status ?? "?");
    printLine("");
    printLine(`  ${theme.grad("EXPLANATION", "#9B94F0", "#5AB9CD")}  ${theme.dim(`run ${runId}`)}`);
    printLine(`  ${theme.dim("outcome".padEnd(10))} ${theme.semantic("text", truncateToWidth(outcome, 60))}`);
    const concise = String(ev.concise ?? "");
    for (const line of concise.split("\n").slice(0, 8)) {
      if (line.trim()) printLine(`  ${theme.semantic("text", truncateToWidth(line, 74))}`);
    }
    printLine(`  ${theme.dim("sections")}  ${theme.dim(String(Array.isArray(ev.sections) ? (ev.sections as string[]).join(" · ") : ""))}`);
    if (String(ev.status) === "error") printWarning(String(ev.error ?? "explanation failed"));
    printLine("");
  }

  /** Compact honest rendering of a research_answer payload (per command). */
  /** Scientific sections renderer with tier glyphs (§11: ✓ ◆ ~ ? ! ×). */
  private renderSections(sections: Array<Record<string, unknown>>): void {
    const GLYPH: Record<string, string> = {
      verified: "✓", computed: "◆", approximation: "~", inferred: "?", limitation: "!", failed_gate: "×",
    };
    for (const sec of sections) {
      printSection(String(sec.title ?? "SECTION"));
      const stmts = (sec.statements as Array<Record<string, unknown>>) || [];
      for (const st of stmts.slice(0, 6)) {
        const g = GLYPH[String(st.tier ?? "inferred")] ?? "·";
        printLine(`  ${g} ${theme.semantic("text", truncateToWidth(String(st.text ?? ""), 76))}`);
      }
      const evs = (sec.evidence as Array<Record<string, unknown>>) || [];
      for (const e of evs.slice(0, 5)) {
        printLine(`      · ${theme.dim(truncateToWidth(String(e.text ?? ""), 60))} [${String(e.tier ?? "?")}] ${theme.dim(String(e.source ?? ""))}`);
      }
    }
  }

  private renderResearchAnswer(ev: Record<string, unknown>): void {
    const command = String(ev.command ?? "research");
    const status = String(ev.status ?? "ok");
    const runId = String(ev.run_id ?? "");
    const title = command === "design" ? "DESIGN RESULT"
      : command === "investigate" ? "INVESTIGATION"
        : command === "reason" ? "MECHANISTIC REASONING"
          : command === "evidence" ? "EVIDENCE GRAPH"
            : command.toUpperCase();
    printLine("");
    printLine(`  ${theme.grad(`${title} · ${command}`, "#9B94F0", "#5AB9CD")}  ${status === "ok" ? theme.success(status) : theme.error(status)}`);
    if (runId) printLine(`  ${theme.dim("run".padEnd(10))} ${theme.semantic("text", runId)}`);
    if (ev.executed_design === true) printLine(`  ${theme.dim("design".padEnd(10))} ${theme.success("executed_design=true")}  ${theme.dim(`engine ${String(ev.engine ?? "")}`)}`);

    // ── stage timeline — executed vs honestly-unevaluated ──
    const timeline = (ev.stage_timeline as Array<Record<string, unknown>>) || [];
    if (timeline.length) {
      printSection("STAGE TIMELINE");
      for (const s of timeline) {
        const stage = String(s.stage ?? "");
        const st = String(s.status ?? "");
        const chip = st === "executed" ? theme.success("executed")
          : st === "unevaluated" ? theme.warning("unevaluated")
            : st === "failed" ? theme.error("failed")
              : theme.muted(st || "?");
        printLine(`  ${typeChip(stage)} ${chip}  ${theme.dim(truncateToWidth(String(s.detail ?? ""), 56))}`);
      }
    }

    // ── scientific findings (shared contract field) — never logs ──
    const findings = (ev.scientific_findings as string[]) || [];
    const gap = String(ev.evidence_gap_conclusion ?? "").trim();
    if (findings.length) {
      printSection("FINDINGS");
      for (const f of findings.slice(0, 8)) printLine(`  ${theme.fg("mint", "·")} ${theme.semantic("text", truncateToWidth(String(f), 78))}`);
    } else if (gap) {
      printSection("EVIDENCE GAP");
      printLine(`  ${theme.fg("mint", "·")} ${theme.semantic("text", truncateToWidth(gap, 78))}`);
    } else {
      printWarning("No substantive scientific result in this payload (contract: findings or evidence-gap conclusion required).");
    }

    // ── scientific sections (semantics layer): tiered statements + evidence ──
    const sections = (ev.sections as Array<Record<string, unknown>>) || [];
    if (sections.length) this.renderSections(sections);

    // ── resource selection reasons: debug-only, NEVER the scientific answer ──
    if (process.env.PROTACXTEND_DEBUG_RESOURCE_REASONS === "1") {
      const resourceReasons = (ev.resource_reason_summary as Record<string, unknown>) || {};
      printSection("RESOURCE REASONS (debug)");
      printLine(`  ${theme.dim(String(resourceReasons.status ?? ""))} ${theme.dim(String(resourceReasons.limitation ?? ""))}`);
    }

    // ── candidates (design / run) ──
    const rows = (ev.candidate_evidence_table as Array<Record<string, unknown>>) || [];
    if (rows.length) {
      const counts = (ev.assembly_counts as Record<string, unknown>) || {};
      printSection("CANDIDATES");
      if (Object.keys(counts).length) {
        printLine(`  ${theme.dim("assembled")} ${String(counts.assembled ?? "?")}  ${theme.dim("valid")} ${String(counts.valid ?? "?")}  ${theme.dim("rejected_before_scoring")} ${String(counts.rejected_before_scoring ?? "?")}`);
      }
      for (const r of rows.slice(0, 5)) {
        const rank = (r.ranking as Record<string, unknown>) || {};
        const deg = (r.degradation as Record<string, unknown>) || {};
        const id = String(r.candidate_id ?? "?");
        const score = rank.final_priority_score !== undefined && rank.final_priority_score !== null
          ? theme.fg("cyan", Number(rank.final_priority_score).toFixed(3)) : theme.dim("no score");
        const dc50 = deg.predicted_dc50_nM !== undefined && deg.predicted_dc50_nM !== null
          ? `${theme.dim("pDC50")} ${String(deg.predicted_dc50_nM)} nM` : "";
        const flags = (r.warning_flags as string[]) || [];
        printLine(`  ${theme.accent(`#${String(rank.rank ?? "?")}`)}  ${theme.semantic("text", truncateToWidth(id, 34))}  ${score}  ${dc50}`);
        if (flags.length) printLine(`      ${theme.warning("!")} ${theme.dim(truncateToWidth(flags.join("; "), 68))}`);
      }
      if (rows.length > 5) printLine(`  ${theme.dim(`… and ${rows.length - 5} more; full table: candidate_evidence.csv`)}`);
    }

    // ── evidence gates ──
    const gates = (ev.evidence_gates as Record<string, unknown>) || {};
    if (Object.keys(gates).length) {
      printSection("EVIDENCE GATES");
      for (const [name, g] of Object.entries(gates)) {
        const info = (g as Record<string, unknown>) || {};
        const gs = String(info.status ?? "?");
        const chip = gs === "passed" || gs === "predicted" ? theme.success(gs)
          : gs === "unevaluated" || gs === "not_assessable" ? theme.warning(gs)
            : theme.muted(gs);
        printLine(`  ${theme.dim(padRight(name, 22))} ${chip}`);
        const lim = String(info.limitation ?? "");
        if (lim) printLine(`      ${theme.dim(truncateToWidth(lim, 70))}`);
      }
    }

    // ── persistence ──
    const files = (ev.intermediate_files as Record<string, unknown>) || {};
    const artifactPaths = (ev.artifact_paths as Record<string, unknown>) || {};
    const vals = Object.values({ ...artifactPaths, ...files }).map(String).filter(Boolean);
    if (ev.evidence_graph) vals.push(String(ev.evidence_graph));
    const uniqueVals = Array.from(new Set(vals));
    if (uniqueVals.length) {
      printSection("PERSISTED ARTIFACTS");
      for (const v of uniqueVals.slice(0, 6)) printLine(`  ${theme.fg("mint", "✓")} ${theme.dim(truncateToWidth(v, 74))}`);
    }
    const resume = (ev.resume_state as Record<string, unknown>) || {};
    if (resume.resume_command) printLine(`  ${theme.dim("resume")}  ${theme.dim(String(resume.resume_command))}`);
    printLine("");
  }

  // ── Primary workflow dispatcher ────────────────────────────────

  /**
   * A research workflow with no argument opens its evidence-grounded
   * definition card; with an argument it is routed into the existing
   * backend capabilities (agent graph / focused tools), never duplicated.
   */
  private async runWorkflow(slug: string, args: string): Promise<void> {
    const wf = WORKFLOW_INDEX[slug];
    if (!wf) {
      printWarning(`Unknown workflow: ${slug}`);
      return;
    }
    if (!args) {
      this.showWorkflowCard(wf);
      return;
    }

    // admet/synthesis accept a bare SMILES → direct lightweight tool route
    if (slug === "admet" || slug === "synthesis") {
      const single = !/\s/.test(args);
      if (single) {
        printInfo(`${wf.cmd} → tool route (${slug === "admet" ? "RDKit properties" : "retrosynthesis"})`);
        this.bridge.send(slug === "admet" ? "validate" : "retrosynthesis", { smiles: args });
        return;
      }
    }

    const prompt = WORKFLOW_PROMPT[slug] ?? wf.desc;
    printInfo(`${wf.cmd} → agent graph · ${truncateToWidth(`${prompt}: ${args}`, 68)}`);
    await this.handleDesignRequest(`${prompt}: ${args}`);
  }

  private showWorkflowCard(wf: WorkflowInfo): void {
    const phaseColor = wf.phase === "KNOW" ? "violet" : wf.phase === "REASON" ? "purple" : wf.phase === "DESIGN" ? "cyan" : "mint";
    const title = `${wf.cmd}  ${theme.fg(phaseColor, `[${wf.phase}]`)}`;
    const defLines = this.wrap(wf.def, 58);
    const rows: string[] = [
      `${theme.dim("role".padEnd(12))} ${theme.semantic("text", truncateToWidth(wf.desc, 58))}`,
      "",
      `${theme.dim("def".padEnd(12))} ${theme.semantic("text", defLines[0] ?? "")}`,
      ...defLines.slice(1).map((l) => `  ${theme.dim("".padEnd(12))}  ${theme.semantic("text", l)}`),
      "",
      `${theme.dim("agents".padEnd(12))} ${theme.dim(truncateToWidth(wf.agents, 52))}`,
    ];
    printPanel(title, rows, 74);
    printLine(`  ${theme.dim("run")}  ${theme.fg("mint", wf.example)}`);
    printLine("");
  }

  // ── Skill execution ────────────────────────────────────────────

  /** `/skill <id>` shows the profile · `/skill <id> <args>` also runs it. */
  private async runSkill(query: string, skillArgs: string): Promise<void> {
    if (!query) {
      printInfo("Usage: /skill <id|partial> [args]");
      printInfo("       e.g.  /skill stereochemistry CC(=O)Nc1ccc(O)cc1   (profile + run)");
      printInfo("             /skill linker_generation                    (profile only)");
      printInfo("See /skills for the full catalogue (18 categories).");
      return;
    }
    let skills = this.skillsCache;
    if (!skills) {
      const ev = await this.ask("skills", ["skills_list"]);
      skills = (ev?.skills as Record<string, unknown>[]) || null;
      if (!skills) {
        printWarning("Skill catalogue not available (backend offline).");
        return;
      }
    }
    const q = query.toLowerCase();
    const hit =
      skills.find((s) => String(s.id ?? "").toLowerCase() === q || String(s.name ?? "").toLowerCase() === q) ||
      skills.find((s) => String(s.id ?? "").toLowerCase().includes(q) || String(s.name ?? "").toLowerCase().includes(q));
    if (!hit) {
      printWarning(`No skill matches "${query}". Try /skills.`);
      return;
    }
    const id = String(hit.id ?? "");
    const category = String(hit.category ?? "General");
    const guide = SKILL_GUIDE[id];
    const rows: string[] = [
      `${theme.dim("category".padEnd(12))} ${theme.fg("cyan", category)}`,
      `${theme.dim("name".padEnd(12))} ${theme.semantic("text", String(hit.name ?? id))}`,
      `${theme.dim("api".padEnd(12))} ${theme.fg("cyan", String(hit.api ?? ""))}`,
      "",
      `  ${theme.dim(String(hit.desc ?? ""))}`,
    ];
    if (guide) {
      rows.push("", `${theme.dim("run via".padEnd(12))} ${theme.fg("mint", guide.cmd)} ${theme.dim(`— ${guide.example}`)}`);
    } else {
      rows.push("", `${theme.dim("run via".padEnd(12))} ${theme.fg("mint", "/run <objective>")}  ${theme.dim("(routed through the agent graph)")}`);
    }
    printPanel(`SKILL PROFILE · ${id}`, rows, 76);

    if (skillArgs && guide) {
      printInfo(`Running skill ${id} with: ${skillArgs}`);
      await this.executeGuided(guide.cmd, skillArgs);
    } else if (skillArgs && !guide) {
      printInfo(`No direct CLI route for ${id} — running through the agent graph…`);
      await this.handleDesignRequest(`${id}: ${skillArgs}`);
    }
  }

  /** Translate a skill's recommended command into an actual execution. */
  private async executeGuided(cmd: string, argsText: string): Promise<void> {
    switch (cmd) {
      case "/validate":
      case "/retro":
      case "/stereo":
        if (!argsText) break;
        this.bridge.send(cmd === "/retro" ? "retrosynthesis" : cmd === "/stereo" ? "stereo" : "validate", { smiles: argsText });
        break;
      case "/docking": {
        const [smiles, target] = argsText.split(/\s+/);
        if (!smiles) break;
        this.bridge.send("docking", { smiles, target: target || "" });
        break;
      }
      case "/generator":
        if (!argsText) break;
        this.bridge.send("generator", { request: argsText });
        break;
      case "/admet":
      case "/synthesis": {
        const single = !/\s/.test(argsText);
        if (single) {
          this.bridge.send(cmd === "/admet" ? "validate" : "retrosynthesis", { smiles: argsText });
        } else {
          await this.handleDesignRequest(`${cmd.slice(1)}: ${argsText}`);
        }
        break;
      }
      case "/degradation":
        await this.handleDesignRequest(`Degradation prediction: ${argsText}`);
        break;
      case "/selectivity":
        await this.handleDesignRequest(`Selectivity analysis: ${argsText}`);
        break;
      case "/investigate":
        await this.runResearchWorkflow("investigate", argsText);
        break;
      case "/compare":
        await this.runResearchWorkflow("compare", argsText);
        break;
      case "/learn":
        printSection("ACTIVE LEARNING");
        printLine(`  ${theme.dim("feedback")}  ${theme.semantic("text", argsText || "improve next run")}`);
        break;
      case "/report":
        if (/^run_[A-Za-z0-9_-]+$/i.test(argsText)) {
          this.bridge.send("report", { run_id: argsText.trim() });
        } else {
          await this.handleDesignRequest(`Generate report: ${argsText}`);
        }
        break;
      case "/design":
      case "/run":
      default:
        await this.handleDesignRequest(argsText || "general design objective");
    }
  }

  // ── Design request execution ───────────────────────────────────

  /** Conversational (LLM) turn — renders chat_answer from the bridge. */
  private async handleChat(request: string): Promise<void> {
    const text = request.trim();
    if (!text) {
      printInfo("Ask a question, e.g. “What is BRD4 and why is it a PROTAC target?”");
      return;
    }
    printLine("");
    this.bridge.send("chat", { request: text });
    await new Promise<void>((resolve) => {
      const handler = (event: BridgeEvent) => {
        if (event.type === "chat_complete") {
          this.bridge.removeListener("event", handler);
          resolve();
        }
      };
      this.bridge.on("event", handler);
    });
  }

  private async handleDesignRequest(request: string): Promise<void> {
    printLine("");
    this.bridge.send("run", { request });
    await new Promise<void>((resolve) => {
      const handler = (event: BridgeEvent) => {
        if (event.type === "run_complete") {
          this.bridge.removeListener("event", handler);
          resolve();
        }
      };
      this.bridge.on("event", handler);
    });
  }

  // ── Results rendering (one-line-first) ─────────────────────────

  private showResults(event: Record<string, unknown>): void {
    printLine("");
    printLine(`  ${theme.grad("─".repeat(58), "#9B94F0", "#5AB9CD")}`);
    printLine(`  ${theme.accent("WORKFLOW RESULT")}  ${theme.dim("· run summary · persisted artifacts below")}`);

    // RUN / STATUS / SUMMARY / OUTPUT / WARNINGS — minimal result presentation.
    const runId = String(event.run_id ?? "");
    const statusRaw = String(event.status ?? "ok");
    const warnings = (event.warnings as string[]) || [];
    const status =
      statusRaw !== "ok" ? statusRaw
        : warnings.length > 0 ? "Complete with warnings"
          : "Complete";
    if (runId) printLine(`  ${theme.dim("RUN".padEnd(10))} ${theme.semantic("text", runId)}`);
    printLine(`  ${theme.dim("STATUS".padEnd(10))} ${status === "Complete" ? theme.success(status) : status === "Complete with warnings" ? theme.muted(status) : theme.error(status)}`);

    const metric = (label: string, value: unknown) =>
      Number(value) > 0 ? `${theme.dim(label + " ")}${theme.fg("mint", String(value))}` : null;

    const metrics = [
      metric("candidates", event.candidates_generated),
      metric("ranked", event.candidates_ranked),
      metric("binders", event.binders_found),
      metric("warheads", event.warheads_selected),
      metric("E3", event.e3_ligands_selected),
      metric("linkers", event.linkers_generated),
    ].filter(Boolean) as string[];

    printLine(`  ${theme.dim("SUMMARY".padEnd(10))} ${metrics.length ? metrics.join(theme.dim("  ·  ")) : theme.muted("pipeline produced no countable outputs for this objective")}`);
    printLine(`  ${theme.grad("─".repeat(58), "#9B94F0", "#5AB9CD")}`);

    if (warnings.length > 0) {
      printLine("");
      printSection("WARNINGS");
      for (const w of warnings.slice(0, 5)) {
        printLine(`  ${theme.fg("amber", "!")} ${theme.dim(truncateToWidth(String(w), 74))}`);
      }
    }

    const candidates = event.top_candidates as Array<Record<string, unknown>> | undefined;
    if (candidates && candidates.length > 0) {
      printLine("");
      printSection("TOP CANDIDATES");
      for (let i = 0; i < Math.min(candidates.length, 5); i++) {
        const c = candidates[i];
        const score = typeof c.score === "number" ? c.score.toFixed(3) : String(c.score ?? "?");
        const tier = c.tier ? ` ${theme.fg("cyan", `[${c.tier}]`)}` : "";
        const scoreColored = typeof c.score === "number"
          ? (c.score > 0.7 ? theme.success(score) : c.score > 0.4 ? theme.muted(score) : theme.error(score))
          : theme.semantic("text", score);
        const comps = [c.warhead ? `war ${c.warhead}` : "", c.e3 ? `e3 ${c.e3}` : "", c.linker ? `linker ${c.linker}` : ""]
          .filter(Boolean).join(" · ");
        printLine(`  ${theme.accent(`#${i + 1}`)}  ${theme.semantic("text", String(c.candidate_id ?? "?"))}  ${scoreColored}${tier}`);
        if (c.smiles) printLine(`      ${theme.dim(truncateToWidth(String(c.smiles), 72))}`);
        if (comps) printLine(`      ${theme.dim(comps)}`);
      }
    }

    if (event.report_preview) {
      printLine("");
      printSection("REPORT PREVIEW");
      const preview = String(event.report_preview);
      for (const line of preview.split("\n").slice(0, 6)) {
        if (line.trim()) printLine(`  ${theme.dim(truncateToWidth(line, 74))}`);
      }
    }
    // “saved” is claimed ONLY when the backend confirmed the production run
    // record on disk (persisted flag + exact outputs/runs/<run_id>/ path).
    const savedDir = String(event.saved_dir ?? "").trim();
    const persisted = event.persisted === true || savedDir.length > 0;
    printLine("");
    printSection("OUTPUT");
    if (persisted) {
      printLine(`  ${theme.dim("Results saved:")}`);
      printLine(`  ${theme.fg("mint", `${savedDir}/`)}`);
    } else {
      printLine(`  ${theme.fg("amber", "!")} run artifacts were NOT persisted — review the errors above; nothing was claimed as saved.`);
    }
    printLine("");
  }

  // ── Panels ─────────────────────────────────────────────────────

  private renderStatusPanel(ev: Record<string, unknown>): void {
    const llm = (ev.llm as Record<string, unknown>) || {};
    const deps = (ev.dependencies as Record<string, unknown>) || {};
    printLine("");
    printLine(`  ${theme.grad("═══ SYSTEM STATUS ═══", "#9B94F0", "#5AB9CD")}`);
    printRuleHeader("RUNTIME");
    printKv("project root", theme.dim(String(ev.project_root ?? "")), 16);
    printKv("software", theme.fg("mint", `v${ev.version ?? VERSION}`), 16);
    printKv("llm", `${theme.semantic("text", `${String(llm.provider ?? "—")}/${String(llm.model ?? "—")}`)}  ${llm.healthy ? theme.success("healthy") : theme.error("unhealthy")}`, 16);
    printKv("node graph", `${theme.fg("mint", String(ev.agents ?? this.agentCount))} agents · ${theme.fg("mint", String(ev.workflows ?? RESEARCH_WORKFLOWS.length))} research workflows · ${theme.fg("mint", String(ev.skills ?? this.skillsCount))} skills · ${theme.fg("mint", String(ev.databases ?? this.databaseCount))} databases`, 16);

    const depNames = Object.keys(deps);
    if (depNames.length) {
      printRuleHeader("DEPENDENCIES");
      const chips = depNames.map((d) => {
        const v = String(deps[d]);
        return v === "missing" ? `${theme.dim(d)} ${theme.error("✗")}` : `${theme.semantic("text", d)} ${theme.dim(v)}`;
      });
      let line = "  ";
      for (const chip of chips) {
        if (visibleWidth(line) + visibleWidth(chip) + 4 > 74) {
          printLine(line);
          line = "  ";
        }
        line += chip + theme.dim("  ·  ");
      }
      if (line.trim()) printLine(line.replace(/  ·\s*$/, ""));
    }
    printLine("");
    printSuccess("status refreshed");
    printLine("");
  }

  private renderAgentsPanel(ev: Record<string, unknown>): void {
    const agents = (ev.agents as Array<Record<string, unknown>>) || [];
    printLine("");
    printLine(`  ${theme.grad("═══ AGENT PIPELINE ═══", "#9B94F0", "#5AB9CD")}  ${theme.dim(`(${agents.length} nodes)`)}`);
    printLine("");
    const rows: string[] = [];
    for (const a of agents) {
      const stage = String(a.stage ?? "KNOW");
      const stageChip = theme.fg(
        stage === "KNOW" ? "violet" : stage === "REASON" ? "purple" : stage === "DESIGN" ? "cyan" : "mint",
        `[${stage}]`,
      );
      const id = String(a.id ?? "");
      const name = String(a.name ?? id);
      rows.push(`  ${stageChip}  ${theme.semantic("text", padRight(name, 30))} ${theme.dim(id)}`);
    }
    const width = this.termWidth();
    if (width >= 96) {
      const col = Math.ceil(rows.length / 2);
      for (let i = 0; i < col; i++) {
        printLine(`${rows[i] ?? ""}${rows[i + col] ? " " + rows[i + col] : ""}`);
      }
    } else {
      for (const row of rows) printLine(row);
    }
    printLine("");
    printLine(`  ${theme.dim("KNOW")}  retrieval & verification   ${theme.dim("REASON")}  warhead/E3/exit-vector choice`);
    printLine(`  ${theme.dim("DESIGN")}  build, validate, predict    ${theme.dim("DISCOVER")}  rank, diversify, reflect, report`);
    printLine("");
  }

  private renderWorkflowsPanel(ev: Record<string, unknown>): void {
    const wfs = (ev.workflows as Array<{ cmd: string; desc: string }>) || [];
    printLine("");
    printLine(`  ${theme.grad("═══ PRIMARY RESEARCH WORKFLOWS ═══", "#9B94F0", "#5AB9CD")}  ${theme.dim(`(${wfs.length})`)}`);
    printLine("");
    const width = this.termWidth();
    const descW = width >= 100 ? 60 : 42;
    for (const wf of wfs) {
      const info = RESEARCH_WORKFLOWS.find((w) => w.cmd === wf.cmd);
      const phase = info ? ` ${theme.fg(info.phase === "KNOW" ? "violet" : info.phase === "REASON" ? "purple" : info.phase === "DESIGN" ? "cyan" : "mint", `[${info.phase}]`)}` : "";
      const cmd = theme.fg("mint", padRight(wf.cmd, 16));
      printLine(`  ${cmd}${phase}${phase ? " " : ""}${theme.dim(truncateToWidth(wf.desc, descW))}`);
    }
    printLine("");
    printLine(`  ${theme.dim("Type a workflow without arguments to see its definition card and example.")}`);
    printLine(`  ${theme.dim("Low-level skills: /skills · /skill <id> · direct tools stay available (see /help).")}`);
    printLine("");
  }

  // ── /doctor ─────────────────────────────────────────────────────

  /**
   * /doctor — real diagnostics from the Python backend plus a local
   * node/path check. `json` argument prints machine-readable output.
   */
  private async runDoctor(jsonOut: boolean): Promise<void> {
    printLine("");
    if (jsonOut) {
      printLine(`  ${theme.dim("Requesting machine-readable diagnostics…")}`);
    } else {
      printLine(`  ${theme.grad("═══ PROTACXtend /doctor ═══", "#9B94F0", "#5AB9CD")}`);
      printRuleHeader("SYSTEM CHECKS");
    }

    const ev = await this.ask("doctor", ["doctor"], 30_000);
    const report = ((ev?.report ?? {}) as Record<string, unknown>);
    const checks = ((report.checks ?? []) as Array<Record<string, unknown>>);

    if (!ev || !checks.length) {
      if (jsonOut) printLine(JSON.stringify({ error: "doctor report unavailable" }));
      else printWarning("No /doctor report received from backend.");
      return;
    }

    // local node/path check (TUI side, always accurate here)
    const nodeInfo = { name: "node (TUI)", level: "required", status: "ok", ok: true,
      detail: `v${process.versions.node} · ${process.execPath}` };
    const all = [nodeInfo, ...checks];

    if (jsonOut) {
      const merged = {
        system: report.system ?? "ready",
        required_ok: report.required_ok ?? false,
        optional_warnings: report.optional_warnings ?? 0,
        summary: report.summary ?? {},
        required_failures: report.required_failures ?? [],
        checks: all,
      };
      printLine(JSON.stringify(merged, null, 2));
      printLine("");
      printSuccess(merged.required_ok ? "required checks ready" : "required checks FAILED");
      return;
    }

    for (const c of all) {
      const name = String(c.name ?? "");
      const detail = String(c.detail ?? "");
      const level = String(c.level ?? "optional");
      const ok = Boolean(c.ok);
      const statusTxt = level === "required"
        ? (ok ? theme.success("✓ ready") : theme.error("✗ required failure"))
        : (ok ? theme.success("✓ ready") : theme.warning("⚠ optional/unconfigured"));
      printKv(name, statusTxt, 34);
      if (!ok && level === "required") printInfo(`  ${truncateToWidth(detail, 74)}`);
      if (ok && detail && !detail.startsWith("v")) printInfo(`  ${theme.dim(truncateToWidth(detail, 74))}`);
    }

    const llmInfo = (report.llm ?? {}) as Record<string, unknown>;
    const llmVerdict = String(report.llm_verdict ?? "");
    if (llmInfo.provider || llmVerdict) {
      printRuleHeader("LLM PROVIDER");
      if (llmInfo.provider) printKv("provider", theme.semantic("text", `${String(llmInfo.provider)}/${String(llmInfo.model ?? "?")}`), 16);
      const auth = (llmInfo.authentication ?? {}) as Record<string, unknown>;
      if (auth.ok !== undefined) printKv("authentication", Boolean(auth.ok) ? theme.success("authenticated") : theme.warning("not authenticated"), 16);
      const inf = (llmInfo.inference ?? {}) as Record<string, unknown>;
      if (inf.ok !== undefined) printKv("inference", Boolean(inf.ok) ? theme.success("available") : theme.warning(String(inf.reason ?? "unavailable")), 16);
      const so = (llmInfo.structured_output ?? {}) as Record<string, unknown>;
      const tc = (llmInfo.tool_calling ?? {}) as Record<string, unknown>;
      if (so.supported !== undefined) printKv("structured-output", Boolean(so.supported) ? theme.success("yes") : theme.error("no"), 16);
      if (tc.supported !== undefined) printKv("tool calling", Boolean(tc.supported) ? theme.success("yes") : theme.error("no"), 16);
      if (llmVerdict) {
        const vc = llmVerdict === "READY" ? theme.success(llmVerdict) : llmVerdict === "DEGRADED" ? theme.warning(llmVerdict) : theme.error(llmVerdict);
        printKv("llm verdict", vc, 16);
      }
    }
    printRuleHeader("VERDICT");
    const fails = (report.required_failures as string[]) || [];
    const warnCount = Number(report.optional_warnings ?? 0);
    const summary = (report.summary ?? {}) as Record<string, unknown>;
    const system = String(report.system ?? (fails.length ? "REQUIRED_FAILURE" : warnCount ? "WARNING" : "READY"));
    if (system === "REQUIRED_FAILURE") {
      printError(`REQUIRED FAILURE — ${fails.join(", ")}`);
      printInfo("Optional warnings never block the system, required failures do.");
    } else if (system === "WARNING") {
      printWarning(`WARNING — ${String(summary.ok ?? "?")} ok · ${warnCount} optional ⚠ (non-blocking)`);
    } else {
      printSuccess(`READY — ${String(summary.ok ?? "?")} checks ok`);
    }
    printLine("");
  }

  // ── Help ───────────────────────────────────────────────────────

  private showHelp(): void {
    const width = Math.min(this.termWidth(), 112);
    const lineW = width - 6;
    const cmdW = 24;
    const col = (c: string) => theme.fg("mint", padRight(c, cmdW));
    const dim = (t: string, max = lineW - cmdW - 2) => theme.dim(truncateToWidth(t, Math.max(20, max)));

    printLine("");
    printLine(`  ${theme.grad("PROTACXtend \u2014 COMMAND CENTRE", "#9B94F0", "#5AB9CD")}`);
    printLine(`  ${theme.dim("\u2500".repeat(Math.min(lineW, 80)))}`);
    printLine("");

    // Every advertised line comes from the SAME registry that dispatches it.
    for (const { group, specs } of groupedCommands()) {
      printSection(group);
      for (const spec of specs) {
        const usage = spec.usage ? ` ${spec.usage}` : "";
        printLine(`  ${col(spec.cmd + usage)} ${dim(spec.desc)}`);
        if (spec.aliases?.length) {
          printLine(`  ${theme.dim("".padEnd(cmdW))} ${theme.dim(`aliases: ${spec.aliases.join(", ")}`)}`);
        }
      }
      printLine("");
    }
    printLine(`  ${theme.dim("A workflow with no arguments asks for the input it needs; add an objective to execute it.")}`);
    printLine("");

    // 3 ── Common examples
    printSection("TRY THESE");
    const examples: [string, string][] = [
      ["/plan", "Design a BRD4 degrader using VHL"],
      ["/investigate", "BRD4"],
      ["/compare", "examples/brd4_vhl_6.csv"],
      ["/design", "BRD4 VHL"],
      ["/structure", "<SMILES>"],
      ["/admet", "<SMILES>"],
      ["/run", "<objective>  (full KNOW \u2192 REASON \u2192 DESIGN \u2192 DISCOVER)"],
    ];
    for (const [c, rest] of examples) {
      printLine(`  ${theme.fg("cyan", padRight(c, cmdW))} ${theme.dim(rest)}`);
    }
    printLine("");

    // 4 ── Launch / usage
    printSection("LAUNCH / USAGE");
    const launchRows: [string, string][] = [
      ["protacxtend", "Global launch \u2014 from any directory (npm link / install)"],
      ["cd tui && node dist/index.js", "Local development launch"],
      ["npm link", "Development symlink (run once)"],
      ["PROTACXTEND_MODEL=ollama/gpt-oss:20b", "Model override (or your provider/model)"],
      ["PROTACXTEND_PYTHON=python3", "Python interpreter override"],
    ];
    for (const [c, d] of launchRows) {
      const cc = theme.fg("mint", padRight(c, 36));
      const dd = theme.dim(truncateToWidth(d, Math.max(20, lineW - 38)));
      printLine(`  ${cc} ${dd}`);
    }
    printLine("");
    printLine(`  ${theme.dim("You can also type a natural-language objective without a slash \u2014 it runs /design autonomously.")}`);
    printLine("");
    printLine(`  ${centerText(renderContract(lineW), lineW)}`);
    printLine("");
  }

  // ── About ──────────────────────────────────────────────────────

  private wrap(text: string, width: number): string[] {
    const words = text.split(/\s+/);
    const out: string[] = [];
    let cur = "";
    for (const w of words) {
      if (visibleWidth(cur) + w.length + 1 > width) {
        out.push(cur);
        cur = w;
      } else {
        cur = cur ? cur + " " + w : w;
      }
    }
    if (cur) out.push(cur);
    return out;
  }

  private para(text: string, width = 74): void {
    for (const l of this.wrap(text, width)) printLine(`  ${theme.semantic("text", l)}`);
    printLine("");
  }

  private showAbout(): void {
    const width = Math.min(this.termWidth(), 112);
    printLine("");
    printLine(`  ${theme.grad("PROTACXtend", "#9B94F0", "#5AB9CD")} ${theme.fg("cyan", `v${VERSION}`)}  ${theme.dim("· Targeted Protein Degradation Research Console")}`);
    printLine(`  ${theme.dim("─".repeat(Math.min(width - 4, 88)))}`);
    printLine("");

    printSection("WHAT IT IS");
    this.para("An evidence-grounded, tool-augmented AI agent platform for component-aware PROTAC design. Fourteen primary research workflows (plan → investigate → reason → compare → design → optimize → structure → selectivity → degradation → admet → synthesis → experiment → evidence → run) route into one governed agent graph. Every step — evidence retrieval, molecular construction, ternary feasibility, degradation and cell-context prediction, ranking — is recorded with its input, output, evidence source, model version and limitation. Designed by Saveena Solanki & Ahuja Lab, IIIT Delhi.");
    printSection("THE SCIENTIFIC CONTRACT");
    this.para("PROTAC design is a coupled biological, structural and chemical optimization problem. PROTACXtend decomposes it into independently inspectable layers and walks a governed agent graph:");
    printLine(`  ${centerText(renderContract(Math.min(width - 6, 80)), Math.min(width - 6, 80))}`);
    printLine("");
    printKv("KNOW", "evidence retrieval & verification · targets · binders", 28);
    printKv("REASON", "warhead · E3 ligand · exit vector · applicability", 28);
    printKv("DESIGN", "linkers · assembly · validation · ADMET · feasibility", 28);
    printKv("DISCOVER", "ranking · hook effect · cooperativity · cell context", 28);
    printLine("");

    printSection("CAPABILITIES");
    const caps = [
      "Retrieval & verification — PubMed, Europe PMC, OpenAlex, Crossref, PROTAC-DB",
      "Component-aware design — warhead, E3 recruiter, exit-vector and linker search",
      "Ternary & ubiquitination feasibility — P4ward simulation, geometry proxies",
      "Hook-effect equilibrium, cooperativity (α) and DC50/Dmax prediction",
      "Cell-context conditioning on DepMap transcriptomics (cell-type selectivity)",
      "Multi-objective ranking with novelty, diversity and uncertainty control",
      "Reproducible outputs — Markdown report, CSV and JSON candidate dossiers",
    ];
    for (const c of caps) {
      printLine(`  ${theme.fg("mint", "•")} ${theme.dim(truncateToWidth(c, Math.min(width - 8, 88)))}`);
    }
    printLine("");

    printSection("UNDER THE HOOD");
    printKv("architecture", `${this.agentCount}-node core graph + 8 controlled-search extensions`, 16);
    printKv("workflows", "14 primary research workflows (see /workflows)", 16);
    printKv("engines", "RDKit · Chemprop · AutoDock Vina · ASKCOS · AiZynthFinder · P4ward", 16);
    printKv("catalog", `${this.skillsCount || 23} skills across 18 categories · ${this.databaseCount || 14} API databases · ${this.toolCount} tools`, 16);
    printKv("model", process.env.PROTACXTEND_MODEL || "ollama/gpt-oss:20b (configurable, local)", 16);
    printKv("schemas", "typed Pydantic state + JSONL bridge protocol", 16);
    printLine("");

    printSection("VALIDATION & DOCS");
    printKv("status of truth", "config/scientific_status.yaml (machine readable)", 16);
    printKv("quick start", "documentation/GETTING_STARTED.md", 16);
    printKv("workflows", "documentation/WORKFLOWS.md", 16);
    printKv("web app", "site/index.html — static simulator + docs hub", 16);
    printLine("");

    printSection("PROJECT");
    printKv("website", theme.fg("cyan", SITE_URL), 16);
    printKv("repository", theme.fg("cyan", REPO_URL), 16);
    printKv("maintained by", "Saveena Solanki & Ahuja Lab (IIIT Delhi)", 16);
    printKv("license", "MIT", 16);
    printLine("");

    printSection("LAUNCH ANYWHERE");
    printLine(`  ${theme.dim("global")}   ${theme.fg("mint", "protacxtend")}`);
    printLine(`  ${theme.dim("local")}    ${theme.fg("mint", "cd tui && node dist/index.js")}`);
    printLine(`  ${theme.dim("dev")}     ${theme.fg("amber", "npm link && protacxtend")}`);
    printLine("");
    printLine(`  ${centerText(renderContract(Math.min(width - 6, 80)), Math.min(width - 6, 80))}`);
    printLine("");
  }

  private showLaunch(): void {
    const row = (label: string, code: string) => {
      printLine(`  ${theme.fg("mint", label.padEnd(9))} ${theme.semantic("text", code)}`);
    };
    printLine("");
    printSection("ONE-COMMAND LAUNCH");
    printLine("");
    row("global", "npm link && protacxtend");
    row("local", "cd tui && node dist/index.js");
    printLine("");
    printSection("REQUIREMENTS");
    printLine(`  ${theme.semantic("text", "Node.js ≥ 18   ·   Python ≥ 3.10   ·   PROTACXtend python package (pip install -e .)")}`);
    printLine(`  ${theme.dim("Set PROTACXTEND_PYTHON to pick the python interpreter; PROTACXTEND_MODEL to pick the LLM.")}`);
    printLine("");
  }

  private showContract(): void {
    const width = this.termWidth();
    printPanel("THE SCIENTIFIC CONTRACT", [
      renderContract(Math.min(width - 10, 66)),
      "",
      `${theme.dim("KNOW".padEnd(10))} scientific search, target resolution, binder evidence`,
      `${theme.dim("REASON".padEnd(10))} warhead decision, E3 selection, applicability`,
      `${theme.dim("DESIGN".padEnd(10))} linker generation, assembly, validation, ADMET`,
      `${theme.dim("DISCOVER".padEnd(10))} ranking, hook effect, cooperativity, cell context`,
    ], Math.min(width - 4, 76));
  }

  /** /plan — evidence-grounded research strategy builder (local, no backend). */
  private showPlan(): void {
    const wf = WORKFLOW_INDEX.plan;
    const width = Math.min(this.termWidth(), 96);
    printLine("");
    printLine(`  ${theme.grad("RESEARCH STRATEGY — KNOW → REASON → DESIGN → DISCOVER", "#9B94F0", "#5AB9CD")}`);
    printLine(`  ${theme.dim("─".repeat(Math.min(width - 6, 72)))}`);
    printLine("");
    this.para(wf.def, Math.min(width - 8, 70));
    printSection("STRATEGY MAP");
    const rows: [string, string, string][] = [
      ["KNOW", "Frame + gather", "/plan · /investigate · /reason · /evidence"],
      ["REASON", "Choose mechanism", "/reason · /compare · /structure"],
      ["DESIGN", "Build + predict", "/design · /optimize · /structure · /admet · /synthesis"],
      ["DISCOVER", "Prioritise + test", "/selectivity · /degradation · /experiment · /evidence"],
    ];
    for (const [phase, label, cmds] of rows) {
      const pcol = phase === "KNOW" ? "violet" : phase === "REASON" ? "purple" : phase === "DESIGN" ? "cyan" : "mint";
      printLine(`  ${theme.fg(pcol, `[${phase}]`)} ${theme.dim(padRight(label, 20))} ${theme.semantic("text", cmds)}`);
    }
    printLine("");
    printSection("DECISION ROUTE");
    const steps = [
      "If the question is about a specific target → /investigate <target>",
      "If candidates already exist → /compare or /optimize <series>",
      "If you need new molecules → /design <objective> (full autonomy: /run)",
      "If the design is set → /structure + /degradation + /admet + /synthesis",
      "If you need to test the hypothesis → /experiment",
    ];
    for (const s of steps) printLine(`  ${theme.fg("mint", "▸")} ${theme.dim(truncateToWidth(s, Math.min(width - 8, 74)))}`);
    printLine("");
    printKv("agents", wf.agents, 12);
    printKv("execute", `${theme.fg("mint", wf.example)}   (add arguments to route into the agent graph)`, 12);
    printLine("");
  }

  private showLearn(args: string): void {
    printSection("ACTIVE LEARNING");
    if (args) printLine(`  ${theme.dim("feedback")}  ${theme.semantic("text", args)}`);
    printLine(`  ${theme.dim("Feedback from past runs informs the next candidate generation.")}`);
    printLine(`  ${theme.dim("Add what to improve — e.g. “favour lower logP, penalise hERG alerts.”")}`);
  }

  // ── Simple mode (no backend) ───────────────────────────────────

  private runSimpleMode(): void {
    for (const line of renderSimpleHeader()) printLine(line);
    printLine("");
    printWarning("Python backend not available — running in simple mode.");
    printInfo("Type /help for commands; /about for project info; /quit to exit.");
    printLine("");

    this.rl = readline.createInterface({ input: process.stdin, output: process.stdout, prompt: this.prompt });
    this.running = true;
    this.rl.prompt();

    this.rl.on("line", async (input: string) => {
      const trimmed = input.trim();
      if (!trimmed) {
        this.rl?.prompt();
        return;
      }
      const parts = trimmed.split(/\s+/);
      let cmd = parts[0].toLowerCase();
      const rest = parts.slice(1).join(" ").trim();
      if (cmd === "/quit" || cmd === "/exit") {
        this.running = false;
        this.rl?.close();
        return;
      }
      if (cmd === "/help") this.showHelp();
      else if (cmd === "/about") this.showAbout();
      else if (cmd === "/launch") this.showLaunch();
      else if (cmd === "/contract") this.showContract();
      else if (cmd === "/plan") this.showPlan();
      else if (cmd.startsWith("/") && WORKFLOW_INDEX[cmd.slice(1)] && !rest) {
        this.showWorkflowCard(WORKFLOW_INDEX[cmd.slice(1)]);
      } else if (cmd === "/workflows") {
        this.renderWorkflowsPanel({ workflows: RESEARCH_WORKFLOWS.map((w) => ({ cmd: w.cmd, desc: w.desc })) });
      } else if (cmd === "/clear") {
        process.stdout.write("\x1b[2J\x1b[H");
        for (const l of renderSimpleHeader()) printLine(l);
      } else {
        printWarning(`Backend offline — "${trimmed.slice(0, 60)}" not executed.`);
        printInfo("Install Python deps, then run from the repo: node dist/index.js");
      }
      this.rl?.prompt();
    });

    this.rl.on("close", () => {
      this.running = false;
    });
  }
}
