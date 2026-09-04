/**
 * PROTACXtend Header v2 — brand "command center" card.
 *
 * A dark-navy dashboard that mirrors the project's visual identity
 * (the-ahuja-lab.github.io/PROTACXtend):
 *
 *   • PROTACXtend ASCII wordmark in a violet → cyan gradient beam
 *   • two-column glass card: MODEL / SYSTEM (left) + WORKFLOWS (right)
 *   • phase contract footer:  KNOW → REASON → DESIGN → DISCOVER
 *
 * Legacy Feynman-derived layout lineage preserved in structure; styling is
 * the upgraded "Laboratory Night" theme.
 */

import { PROTACXTEND_LOGO, BRAND_NAME, SUBTITLE, TAGLINE, CONTRACT, PHASES } from "./logo.js";
import {
  visibleWidth,
  truncateToWidth,
  padRight,
  centerText,
  boxTop,
  boxBottom,
  boxSep,
  boxRow,
  gradientBand,
} from "./terminal.js";
import { createTheme } from "./theme.js";

const theme = createTheme();

// ── Types ────────────────────────────────────────────────────────

export interface HeaderData {
  model: string;
  directory: string;
  session: string;
  system: string;
  agentCount: number;
  toolCount: number;
  skillsCount?: number;
  agents: string[];
  workflows: { cmd: string; desc: string }[];
  lastActivity?: string;
}

const PHASE_COLORS: Record<string, "violet" | "purple" | "cyan" | "mint"> = {
  KNOW: "violet",
  REASON: "purple",
  DESIGN: "cyan",
  DISCOVER: "mint",
};

/** Render a phase word with its accent color. */
export function phaseWord(stage: string): string {
  const key = (stage || "").toUpperCase();
  const color = PHASE_COLORS[key] ?? "violet";
  return theme.fg(color, key);
}

/** Gradient-styled KNOW → REASON → DESIGN → DISCOVER contract row. */
export function renderContract(width: number): string {
  const arrow = theme.dim(" → ");
  const words = PHASES.map((p) => theme.fg(PHASE_COLORS[p.toUpperCase()] ?? "violet", p)).join(arrow);
  return centerText(words, Math.max(width, visibleWidth(words)));
}

// ── Header renderer ──────────────────────────────────────────────

export function renderHeader(data: HeaderData, terminalWidth: number): string[] {
  const cardW = Math.min(terminalWidth - 2, 122);
  const innerW = cardW - 2;
  const contentW = innerW - 2; // │ padded │
  const outerPad = " ".repeat(Math.max(0, Math.floor((terminalWidth - cardW) / 2)));

  const lines: string[] = [];
  const push = (line: string) => lines.push(outerPad + line);

  const useWide = contentW >= 72;
  const gap = 3;
  const leftW = useWide ? Math.floor(contentW * 0.42) : contentW;
  const rightW = useWide ? contentW - leftW - gap : 0;

  // ── Wordmark (block when it fits, simple textual gradient below) ──
  // Rendered above the card, centered; both the block art (≈75 cols) and the
  // fallback text are exact-case PROTACXtend.
  const WORDMARK_MIN_WIDTH = 78; // block art width (75) + comfortable margins
  const NAME_STOPS = ["#8E86E8", "#6B7FDB", "#5AB9CD"]; // violet → blue → cyan
  const useBlockWordmark = terminalWidth >= WORDMARK_MIN_WIDTH;
  if (useBlockWordmark) {
    const logoRows = PROTACXTEND_LOGO.filter((l) => visibleWidth(l.trim()) > 0);
    const logoW = Math.max(...logoRows.map((l) => visibleWidth(l)));
    const pad = Math.max(0, Math.floor((cardW - logoW) / 2));
    for (const row of logoRows) {
      push(" ".repeat(pad) + theme.grad(row, undefined, undefined, { stops: NAME_STOPS, span: logoW, offset: 0 }));
    }
  } else {
    // Simple textual wordmark — never clipped or corrupted on narrow terminals.
    push(" ".repeat(Math.max(0, Math.floor((cardW - visibleWidth(BRAND_NAME)) / 2))) +
      theme.grad(BRAND_NAME, undefined, undefined, { stops: NAME_STOPS }));
  }

  // ── Subtitle + tagline — always rendered fully and centered ──
  push("");
  const centerPad = (textWidth: number) => Math.max(0, Math.floor((cardW - textWidth) / 2));
  const sub = theme.semantic("borderAccent", SUBTITLE);
  push(" ".repeat(centerPad(visibleWidth(SUBTITLE))) + sub);
  push(" ".repeat(centerPad(visibleWidth(TAGLINE))) + theme.dim(TAGLINE));
  push("");

  // ── Card ───────────────────────────────────────────────────────
  push(theme.raw("violet") + boxTop(cardW) + theme.reset);
  // gradient cap band (1 row) inside the card
  push(`│ ${gradientBand(contentW)} │`);

  const leftLines: string[] = [];
  const rightLines: string[] = [];

  // Left column — model / system
  leftLines.push(theme.accent("MODEL / SYSTEM"));
  leftLines.push("");
  leftLines.push(`${theme.dim("model".padEnd(11))} ${theme.semantic("text", truncateToWidth(data.model, Math.max(12, leftW - 13)))}`);
  leftLines.push(`${theme.dim("directory".padEnd(11))} ${theme.semantic("text", truncateToWidth(data.directory, Math.max(12, leftW - 13)))}`);
  leftLines.push(`${theme.dim("session".padEnd(11))} ${theme.dim(truncateToWidth(data.session, Math.max(12, leftW - 13)))}`);
  leftLines.push("");
  leftLines.push(`${theme.dim("system".padEnd(11))} ${theme.dim(truncateToWidth(data.system, Math.max(12, leftW - 13)))}`);
  if (typeof data.skillsCount === "number" && data.skillsCount > 0) {
    leftLines.push(`${theme.dim("skills".padEnd(11))} ${theme.fg("cyan", String(data.skillsCount))}${theme.dim(" available")}`);
  }
  leftLines.push("");
  leftLines.push(`${theme.fg("mint", `${data.agentCount} agents`)} ${theme.dim("·")} ${theme.fg("mint", `${data.toolCount} tools`)}`);
  if (data.agents.length > 0) {
    leftLines.push("");
    leftLines.push(theme.accent("Agents"));
    const visible = data.agents.slice(0, 6).join(" · ");
    const extra = data.agents.length > 6 ? ` ${theme.dim(`+${data.agents.length - 6} more`)}` : "";
    leftLines.push(theme.dim(truncateToWidth(visible + extra, leftW)));
  }
  if (data.lastActivity) {
    leftLines.push("");
    leftLines.push(theme.accent("Last Activity"));
    leftLines.push(theme.dim(truncateToWidth(data.lastActivity, leftW)));
  }

  // Right column — research workflows (the 14 primary user workflows)
  rightLines.push(theme.accent("RESEARCH WORKFLOWS"));
  rightLines.push("");
  const visibleWf = data.workflows.slice(0, 14);
  for (const wf of visibleWf) {
    const cmd = theme.fg("mint", wf.cmd);
    const desc = theme.dim(truncateToWidth(wf.desc, Math.max(8, rightW - 16)));
    rightLines.push(`${padRight(cmd, 15)} ${desc}`);
  }

  const maxRows = Math.max(leftLines.length, rightLines.length);
  if (useWide) {
    for (let i = 0; i < maxRows; i++) {
      const left = padRight(leftLines[i] ?? "", leftW);
      const right = padRight(rightLines[i] ?? "", rightW);
      push(`│ ${left} │ ${right} │`);
    }
  } else {
    // narrow fallback: single column
    push(boxRow(theme.accent("MODEL / SYSTEM"), cardW));
    push(boxRow("", cardW));
    for (const row of leftLines.slice(1)) {
      push(boxRow(row, cardW));
    }
    push(boxSep(cardW));
    push(boxRow(theme.accent("RESEARCH WORKFLOWS"), cardW));
    for (const row of rightLines.slice(1)) {
      push(boxRow(row, cardW));
    }
  }

  // Footer — phase contract inside a gradient band
  push(`│ ${gradientBand(contentW)} │`);
  push(`│ ${centerText(renderContract(contentW), contentW)} │`);
  push(theme.raw("violet") + boxBottom(cardW) + theme.reset);
  push("");

  return lines;
}

// ── Simple header (for non-TTY / quick output) ───────────────────

export function renderSimpleHeader(): string[] {
  const lines: string[] = [];
  lines.push("");
  for (const row of PROTACXTEND_LOGO.filter((l) => visibleWidth(l.trim()) > 0)) {
    lines.push(`  ${theme.grad(row, undefined, undefined, { stops: ["#8E86E8", "#6B7FDB", "#5AB9CD"], span: 64, offset: 0 })}`);
  }
  lines.push("");
  lines.push(`  ${theme.semantic("borderAccent", SUBTITLE)}`);
  lines.push(`  ${theme.dim(TAGLINE)}`);
  lines.push("");
  lines.push(`  ${renderContract(64)}`);
  lines.push("");
  return lines;
}
