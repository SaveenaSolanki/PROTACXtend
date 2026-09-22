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

const theme = createTheme();

// ── Version & identity ───────────────────────────────────────────

const VERSION = "0.3.0";
const REPO_URL = "https://github.com/the-ahuja-lab/PROTACXtend";
const SITE_URL = "https://the-ahuja-lab.github.io/PROTACXtend";
const LAUNCH_URL = "https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/tui/launch.sh";

// ── Primary research workflows ───────────────────────────────────

interface WorkflowInfo {
  cmd: string;
  slug: string;
  phase: "KNOW" | "REASON" | "DESIGN" | "DISCOVER";
  desc: string;
  def: string;
  example: string;
  agents: string;
}

const RESEARCH_WORKFLOWS: WorkflowInfo[] = [
  {
    cmd: "/plan", slug: "plan", phase: "KNOW",
    desc: "Evidence-grounded TPD research strategy",
    def: "Build an evidence-grounded research strategy and determine which PROTACXtend workflows, agents and tools are required.",
    example: "/plan BRD4 degradation programme",
    agents: "Supervisor · Design Planner · Evidence Sufficiency",
  },
  {
    cmd: "/investigate", slug: "investigate", phase: "KNOW",
    desc: "Target, E3, degrader & literature intelligence",
    def: "Retrieve and synthesise target biology, E3 biology, existing degraders, ligands, structures, literature and experimental evidence.",
    example: "/investigate BRD4 cereblon degraders and ligands",
    agents: "Target Resolver · Binder Retrieval · Safety Precheck",
  },
  {
    cmd: "/reason", slug: "reason", phase: "REASON",
    desc: "Mechanistic reasoning across evidence",
    def: "Perform mechanistic reasoning across target, warhead, E3, linker, ternary-complex, ubiquitination, degradation and cellular evidence.",
    example: "/reason why VHL PROTACs degrade BRD4 faster than CRBN",
    agents: "Warhead Selection · E3 Ligand Selection · Exit Vector · Repair Controller",
  },
  {
    cmd: "/compare", slug: "compare", phase: "DISCOVER",
    desc: "Compare & explain PROTAC candidates",
    def: "Compare existing PROTAC candidates and explain mechanistically why their behaviour differs.",
    example: "/compare MZ1 dBET1 dBET6 potency and selectivity",
    agents: "Binder Retrieval · Novelty Check · Ranking · Reflection",
  },
  {
    cmd: "/design", slug: "design", phase: "DESIGN",
    desc: "Generate & prioritise degrader candidates",
    def: "Generate and prioritise new degrader candidates.",
    example: "/design CRBN PROTACs for BRD4 degradation",
    agents: "Linker Generation · Molecular Construction · Validation · Ternary Feasibility",
  },
  {
    cmd: "/optimize", slug: "optimize", phase: "DESIGN",
    desc: "Improve a degrader or design series",
    def: "Diagnose limitations of an existing PROTAC and propose rational warhead/E3/linker/whole-molecule improvements.",
    example: "/optimize MZ1-like series for solubility",
    agents: "Reflection · Evolution Refinement · Diversity · Ranking",
  },
  {
    cmd: "/structure", slug: "structure", phase: "DESIGN",
    desc: "Ternary, interface & ubiquitination geometry",
    def: "Perform ternary feasibility, docking, interface analysis, cooperativity, lysine accessibility and ubiquitination-geometry reasoning.",
    example: "/structure BRD4 CRBN ternary feasibility",
    agents: "Ternary Feasibility · Exit Vector Detection · Applicability Domain",
  },
  {
    cmd: "/selectivity", slug: "selectivity", phase: "DISCOVER",
    desc: "Target, E3, proteome & cell-context selectivity",
    def: "Evaluate target, isoform, E3, proteome and cellular-context selectivity.",
    example: "/selectivity BET family selectivity of BRD4 degraders",
    agents: "Proteome Selectivity · Cellular Context (DepMap) · Ranking",
  },
  {
    cmd: "/degradation", slug: "degradation", phase: "DESIGN",
    desc: "Predict & interpret degradation behaviour",
    def: "Predict and interpret degradation potency, Dmax, DC50, kinetics, hook-effect and degradation mechanism.",
    example: "/degradation CC(=O)Nc1ccc(O)cc1 predict DC50 Dmax",
    agents: "Degradation Prediction · Hook Effect Modeler · ADMET",
  },
  {
    cmd: "/admet", slug: "admet", phase: "DESIGN",
    desc: "Molecular properties & developability",
    def: "Assess molecular properties, permeability, solubility, stability and developability.",
    example: "/admet CC(=O)Nc1ccc(O)cc1",
    agents: "ADMET Prediction · Candidate Validation",
  },
  {
    cmd: "/synthesis", slug: "synthesis", phase: "DISCOVER",
    desc: "Synthetic accessibility & retrosynthesis",
    def: "Assess synthetic accessibility, retrosynthesis and building-block routes.",
    example: "/synthesis CC(=O)Nc1ccc(O)cc1",
    agents: "Retrosynthesis (ASKCOS · AiZynthFinder) · Novelty Check",
  },
  {
    cmd: "/experiment", slug: "experiment", phase: "DISCOVER",
    desc: "Assays & next experiments",
    def: "Recommend assays, controls and next experiments to test the current scientific hypothesis.",
    example: "/experiment validate predicted hook effect in H1299",
    agents: "Active Learning · Memory · Report",
  },
  {
    cmd: "/evidence", slug: "evidence", phase: "KNOW",
    desc: "Citations, confidence & provenance",
    def: "Expose citations, database records, model provenance, confidence, uncertainty and supporting/contradictory evidence.",
    example: "/evidence DC50 values reported for dBET1",
    agents: "Evidence Sufficiency · Retrieval agents · Novelty Check",
  },
  {
    cmd: "/run", slug: "run", phase: "KNOW",
    desc: "Execute KNOW → REASON → DESIGN → DISCOVER",
    def: "Autonomously execute the complete KNOW → REASON → DESIGN → DISCOVER workflow.",
    example: "/run BRD4 degraders via CRBN with PEG linkers",
    agents: "all 23 agent nodes (governed graph)",
  },
];

const WORKFLOW_INDEX: Record<string, WorkflowInfo> = Object.fromEntries(RESEARCH_WORKFLOWS.map((w) => [w.slug, w]));

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

const COMMAND_GROUPS: { title: string; rows: [string, string][] }[] = [
  {
    title: "RESEARCH WORKFLOWS",
    rows: RESEARCH_WORKFLOWS.map((w) => [w.cmd, w.desc]),
  },
  {
    title: "LOW-LEVEL SKILL TOOLS",
    rows: [
      ["/validate <SMILES>", "RDKit validation + ADMET proxies, one line"],
      ["/retro <SMILES>", "Retrosynthesis (ASKCOS + AiZynthFinder)"],
      ["/docking <SMILES> [pdb]", "AutoDock Vina docking"],
      ["/stereo <SMILES>", "Stereochemistry + isomer enumeration"],
      ["/generator <request>", "Linker engine (PEG, alkyl, rigid, triazole…)"],
      ["/skill <id> [args]", "Skill profile — and run it with args"],
      ["/cellctx <q>", "Cell-line context score (legacy)"],
      ["/rank <q>", "Ranking pass (legacy)"],
      ["/learn <feedback>", "Active-learning feedback (legacy)"],
      ["/report <q>", "Report generation (legacy)"],
    ],
  },
  {
    title: "CATALOGUE & SYSTEM",
    rows: [
      ["/skills", "Full skill catalogue, 18 scientific categories"],
      ["/databases", "API databases & data sources"],
      ["/workflows", "The 14 primary research workflows"],
      ["/contract", "KNOW → REASON → DESIGN → DISCOVER"],
      ["/status", "System · model · dependencies health"],
      ["/agents", "23-node agent pipeline view"],
      ["/about", "Project, architecture, validation, launch"],
      ["/launch", "Launch recipes"],
      ["/help", "This command reference"],
      ["/clear", "Clear screen + redraw header"],
      ["/quit", "Exit PROTACXtend"],
    ],
  },
];

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
               extra: Record<string, unknown> = {}): Promise<Record<string, unknown> | undefined> {
    return new Promise((resolve) => {
      const onEvent = (event: BridgeEvent) => {
        if (event.type === want.find((w) => w === event.type)) {
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
      model: process.env.PROTACXTEND_MODEL || "ollama/gpt-oss:20b (auto)",
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
    const list = new Set<string>();
    for (const g of COMMAND_GROUPS) for (const [cmd] of g.rows) list.add(cmd);
    for (const k of Object.keys(SKILL_GUIDE)) list.add(`/skill ${k}`);
    list.add("/retrosynthesis");
    list.add("/doctor");
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
    if (input.startsWith("/")) {
      await this.handleCommand(input);
    } else {
      await this.handleDesignRequest(input);
    }
  }

  // ── Commands ───────────────────────────────────────────────────

  private async handleCommand(input: string): Promise<void> {
    const parts = input.split(/\s+/);
    let cmd = parts[0].toLowerCase();
    const args = parts.slice(1).join(" ").trim();

    // aliases
    if (cmd === "/retrosynthesis") cmd = "/retro";

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
      case "/plan":
        this.showPlan();
        break;
      case "/investigate":
        await this.runWorkflow("investigate", args);
        break;
      case "/reason":
        await this.runWorkflow("reason", args);
        break;
      case "/compare":
        await this.runCompare(args || "");
        break;
      case "/design":
        await this.runWorkflow("design", args);
        break;
      case "/optimize":
        await this.runWorkflow("optimize", args);
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
      case "/evidence":
        if (args) {
          await this.runWorkflow("evidence", args);
        } else {
          this.showEvidenceProvenance();
        }
        break;
      case "/run":
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
        if (args) await this.handleDesignRequest(`Generate report: ${args}`);
        else this.showUsage(cmd, "a completed design", "report on the BRD4 run");
        break;
      case "/contract":
        this.showContract();
        break;

      case "/clear":
        process.stdout.write("\x1b[2J\x1b[H");
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
        await this.handleDesignRequest(`Investigate: ${argsText}`);
        break;
      case "/compare":
        await this.handleDesignRequest(`Compare candidates: ${argsText}`);
        break;
      case "/learn":
        printSection("ACTIVE LEARNING");
        printLine(`  ${theme.dim("feedback")}  ${theme.semantic("text", argsText || "improve next run")}`);
        break;
      case "/report":
        await this.handleDesignRequest(`Generate report: ${argsText}`);
        break;
      case "/design":
      case "/run":
      default:
        await this.handleDesignRequest(argsText || "general design objective");
    }
  }

  // ── Design request execution ───────────────────────────────────

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

    // 1 ── Primary Research Workflows
    printSection("PRIMARY RESEARCH WORKFLOWS");
    for (const w of RESEARCH_WORKFLOWS) {
      printLine(`  ${col(w.cmd)} ${dim(w.desc)}`);
    }
    printLine(`  ${theme.dim("Tip: a workflow with no arguments opens its definition card; add an objective to execute it.")}`);
    printLine("");

    // 2 ── System / Utility Commands
    printSection("SYSTEM / UTILITY COMMANDS");
    const sysRows: [string, string][] = [
      ["/doctor", "Run system diagnostics (bridge, package, deps, llm)"],
      ["/status", "System, model and dependency health"],
      ["/agents", "23-node agent pipeline view"],
      ["/skills", "Full skill catalogue \u2014 18 scientific categories"],
      ["/skill <id> [args]", "Skill profile \u2014 and run it with args"],
      ["/databases", "API databases & data sources"],
      ["/workflows", "The 14 primary research workflows"],
      ["/contract", "KNOW \u2192 REASON \u2192 DESIGN \u2192 DISCOVER"],
      ["/about", "Project, architecture, validation, launch"],
      ["/launch", "Launch recipes"],
      ["/clear", "Clear screen + redraw header"],
      ["/quit", "Exit PROTACXtend"],
    ];
    for (const [c, d] of sysRows) printLine(`  ${col(c)} ${dim(d)}`);
    printLine(`  ${theme.dim("Advanced skill tools (low-level): /validate <SMILES> \u00b7 /retro \u00b7 /docking \u00b7 /stereo \u00b7 /generator")}`);
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
