/**
 * Single source of truth for the PROTACXtend command centre.
 *
 * `/help`, tab-completion and dispatch all read from `COMMANDS`; an advertised
 * command can therefore never drift from a dispatchable one. Aliases are
 * declared on the spec (e.g. `/optimise` -> `/optimize`).
 */

export interface WorkflowInfo {
  cmd: string;
  slug: string;
  phase: "KNOW" | "REASON" | "DESIGN" | "DISCOVER";
  desc: string;
  def: string;
  example: string;
  agents: string;
}

export const RESEARCH_WORKFLOWS: WorkflowInfo[] = [
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

export const WORKFLOW_INDEX: Record<string, WorkflowInfo> =
  Object.fromEntries(RESEARCH_WORKFLOWS.map((w) => [w.slug, w]));

export type CommandGroup =
  | "RESEARCH WORKFLOWS"
  | "ASK & EXPLAIN"
  | "SKILL TOOLS"
  | "CATALOGUE & SYSTEM";

/** What input a command needs before it can produce a result. */
export type Needs = "objective" | "query" | "smiles" | "molecule_or_series" | "none";

export interface CommandSpec {
  cmd: string;
  aliases?: string[];
  group: CommandGroup;
  desc: string;
  usage?: string;
  needs: Needs;
  sl?: string; // workflow slug (research workflows only)
  hidden?: boolean;
}

const WF_NEEDS: Record<string, Needs> = {
  plan: "objective",
  investigate: "query",
  reason: "query",
  compare: "query",
  design: "objective",
  optimize: "molecule_or_series",
  structure: "objective",
  selectivity: "objective",
  degradation: "objective",
  admet: "smiles",
  synthesis: "smiles",
  experiment: "objective",
  evidence: "query",
  run: "objective",
};

const WF_ALIASES: Record<string, string[]> = {
  optimize: ["/optimise", "/optimization", "/optimisation"],
  investigate: [],
  reason: ["/reasoning"],
  compare: ["/cmp"],
};

const usageFor = (slug: string): string => {
  const n = WF_NEEDS[slug];
  if (n === "smiles") return "<SMILES>";
  if (n === "query") return "<question>";
  if (n === "molecule_or_series") return "<starting molecule or series>";
  return "<objective>";
};

const workflowSpecs: CommandSpec[] = RESEARCH_WORKFLOWS.map((w) => ({
  cmd: w.cmd,
  aliases: WF_ALIASES[w.slug] ?? [],
  group: "RESEARCH WORKFLOWS",
  desc: w.desc,
  usage: usageFor(w.slug),
  needs: WF_NEEDS[w.slug] ?? "objective",
  sl: w.slug,
}));

export const COMMANDS: CommandSpec[] = [
  ...workflowSpecs,
  { cmd: "/ask", group: "ASK & EXPLAIN", desc: "Explicit conversational question", usage: "<question>", needs: "query" },
  { cmd: "/explain", group: "ASK & EXPLAIN", desc: "Explain a concept, result or mechanism", usage: "<topic>", needs: "query" },
  { cmd: "/validate", group: "SKILL TOOLS", desc: "RDKit validation + ADMET proxies, one line", usage: "<SMILES>", needs: "smiles" },
  { cmd: "/retro", aliases: ["/retrosynthesis"], group: "SKILL TOOLS", desc: "Retrosynthesis (ASKCOS + AiZynthFinder)", usage: "<SMILES>", needs: "smiles" },
  { cmd: "/docking", group: "SKILL TOOLS", desc: "AutoDock Vina docking", usage: "<SMILES> [target.pdb]", needs: "smiles" },
  { cmd: "/stereo", group: "SKILL TOOLS", desc: "Stereochemistry + isomer enumeration", usage: "<SMILES>", needs: "smiles" },
  { cmd: "/generator", group: "SKILL TOOLS", desc: "Linker engine (PEG, alkyl, rigid, triazole…)", usage: "<request>", needs: "objective" },
  { cmd: "/skill", group: "SKILL TOOLS", desc: "Skill profile — and run it with args", usage: "<id> [args]", needs: "none" },
  { cmd: "/cellctx", group: "SKILL TOOLS", desc: "Cell-line context score (legacy)", usage: "<target/E3>", needs: "objective" },
  { cmd: "/rank", group: "SKILL TOOLS", desc: "Ranking pass (legacy)", usage: "<objective>", needs: "objective" },
  { cmd: "/learn", group: "SKILL TOOLS", desc: "Active-learning feedback (legacy)", usage: "<feedback>", needs: "objective" },
  { cmd: "/report", group: "SKILL TOOLS", desc: "Report generation (legacy)", usage: "<objective>", needs: "objective" },
  { cmd: "/doctor", group: "CATALOGUE & SYSTEM", desc: "Run system diagnostics (bridge, package, deps, llm)", needs: "none" },
  { cmd: "/status", aliases: ["/models"], group: "CATALOGUE & SYSTEM", desc: "System, model and dependency health", needs: "none" },
  { cmd: "/agents", group: "CATALOGUE & SYSTEM", desc: "23-node agent pipeline view", needs: "none" },
  { cmd: "/skills", group: "CATALOGUE & SYSTEM", desc: "Full skill catalogue — 18 scientific categories", needs: "none" },
  { cmd: "/databases", group: "CATALOGUE & SYSTEM", desc: "API databases & data sources", needs: "none" },
  { cmd: "/workflows", group: "CATALOGUE & SYSTEM", desc: "The primary research workflows", needs: "none" },
  { cmd: "/contract", group: "CATALOGUE & SYSTEM", desc: "KNOW → REASON → DESIGN → DISCOVER", needs: "none" },
  { cmd: "/about", group: "CATALOGUE & SYSTEM", desc: "Project, architecture, validation, launch", needs: "none" },
  { cmd: "/launch", group: "CATALOGUE & SYSTEM", desc: "Launch recipes", needs: "none" },
  { cmd: "/help", aliases: ["/?"], group: "CATALOGUE & SYSTEM", desc: "This command reference", needs: "none" },
  { cmd: "/clear", group: "CATALOGUE & SYSTEM", desc: "Clear screen + redraw header", needs: "none" },
  { cmd: "/quit", aliases: ["/exit"], group: "CATALOGUE & SYSTEM", desc: "Exit PROTACXtend", needs: "none" },
];

const NAME_MAP: Map<string, CommandSpec> = (() => {
  const m = new Map<string, CommandSpec>();
  for (const spec of COMMANDS) {
    m.set(spec.cmd.toLowerCase(), spec);
    for (const a of spec.aliases ?? []) m.set(a.toLowerCase(), spec);
  }
  return m;
})();

export interface ResolvedCommand {
  name: string;
  spec?: CommandSpec;
  args: string;
}

/** Normalize whitespace, look the command up (aliases included). */
export function resolveCommand(input: string): ResolvedCommand {
  const clean = input.trim().replace(/\s+/g, " ");
  const parts = clean.length ? clean.split(" ") : [""];
  const name = (parts[0] ?? "").toLowerCase();
  const args = parts.slice(1).join(" ").trim();
  return { name, spec: NAME_MAP.get(name), args };
}

/** Every dispatchable name (canonical + aliases) — used by tab completion. */
export function commandNames(): string[] {
  const out: string[] = [];
  for (const spec of COMMANDS) {
    out.push(spec.cmd);
    for (const a of spec.aliases ?? []) out.push(a);
  }
  return out;
}

/**
 * Deterministic research-workflow intents: slash command -> bridge command.
 * These run through protacxtend.workflows.api.run_command (the shared engine)
 * and are NEVER routed to the LLM chat agent. Single source used by both the
 * dispatcher and the routing tests — an advertised command can never drift
 * from its dispatchable intent.
 */
export const RESEARCH_INTENTS: Record<string, string> = {
  "/investigate": "investigate",
  "/reason": "reason",
  "/evidence": "evidence",
  "/compare": "compare",
  "/design": "design",
};

/** Conversational intents — routed to the LLM chat agent on purpose. */
export const CHAT_INTENTS: string[] = ["/ask", "/explain"];

export interface CommandGroupView {
  group: CommandGroup;
  specs: CommandSpec[];
}

/** Groups for /help, in a fixed display order. */
export function groupedCommands(): CommandGroupView[] {
  const order: CommandGroup[] = ["RESEARCH WORKFLOWS", "ASK & EXPLAIN", "SKILL TOOLS", "CATALOGUE & SYSTEM"];
  return order
    .map((group) => ({ group, specs: COMMANDS.filter((s) => s.group === group && !s.hidden) }))
    .filter((g) => g.specs.length > 0);
}

/**
 * True when an /optimize argument names only a target/programme with no
 * starting molecule or series. Such a request cannot be optimized directly;
 * the caller routes it to /design instead.
 */
export function looksTargetOnly(args: string): boolean {
  const t = args.trim();
  if (!t) return true;
  if (/[=()\[\]@#%+\\]/.test(t)) return false;                 // SMILES-like
  if (/\b(MZ1|dBET\d*|ARV-\d+|PROTAC-?\d+|candidate|series|analog(?:ue)?)\b/i.test(t)) return false;
  return !t.split(/\s+/).some(
    (tok) => tok.length >= 6 && /[A-Za-z]/.test(tok) && /\d/.test(tok) && !/^[A-Z]{2,}\d*$/.test(tok),
  );
}

/** Human label for what a command still needs from the user. */
export function neededInputLabel(needs: Needs): string {
  switch (needs) {
    case "smiles": return "a SMILES string";
    case "query": return "a question";
    case "objective": return "an objective";
    case "molecule_or_series": return "a starting molecule or series";
    default: return "";
  }
}
