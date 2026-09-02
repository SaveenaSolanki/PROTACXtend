/**
 * PROTACXtend Header — Feynman-style two-column information card.
 *
 * Derived from Feynman extensions/research-tools/header.ts
 * (MIT, Copyright 2026 Companion, Inc.)
 *
 * Adapted for PROTACXtend scientific workflow.
 */

import { PROTACXTEND_LOGO, SUBTITLE, CONTRACT } from "./logo.js";
import {
  visibleWidth,
  truncateToWidth,
  padRight,
  boxTop,
  boxBottom,
  boxSep,
  boxRow,
  boxRowTwoCol,
} from "./terminal.js";
import { createTheme, type Theme } from "./theme.js";

const theme = createTheme();

// ── Types ────────────────────────────────────────────────────────

export interface HeaderData {
  model: string;
  directory: string;
  session: string;
  system: string;
  agentCount: number;
  toolCount: number;
  agents: string[];
  workflows: { cmd: string; desc: string }[];
  lastActivity?: string;
}

// ── Header renderer ──────────────────────────────────────────────

export function renderHeader(data: HeaderData, terminalWidth: number): string[] {
  const cardW = Math.min(terminalWidth, 120);
  const innerW = cardW - 2;
  const contentW = innerW - 2;
  const outerPad = " ".repeat(Math.max(0, Math.floor((terminalWidth - cardW) / 2)));

  const lines: string[] = [];
  const push = (line: string) => lines.push(outerPad + line);

  const useWideLayout = contentW >= 70;
  const leftW = useWideLayout ? Math.min(38, Math.floor(contentW * 0.38)) : 0;
  const divColW = useWideLayout ? 3 : 0;
  const rightW = useWideLayout ? contentW - leftW - divColW : contentW;

  // ── Logo ──
  if (cardW >= 70) {
    const maxLogoW = Math.max(...PROTACXTEND_LOGO.map((l) => visibleWidth(l)));
    const logoOffset = " ".repeat(Math.max(0, Math.floor((cardW - maxLogoW) / 2)));
    for (const logoLine of PROTACXTEND_LOGO) {
      push(theme.accent(logoOffset + truncateToWidth(logoLine, cardW)));
    }
    push("");
    // Subtitle
    const subOffset = " ".repeat(Math.max(0, Math.floor((cardW - visibleWidth(SUBTITLE)) / 2)));
    push(theme.muted(subOffset + SUBTITLE));
    push("");
  }

  // ── Version tag ──
  const versionTag = " v0.1.0 ";
  const gap = Math.max(0, innerW - visibleWidth(versionTag));
  const gapL = Math.floor(gap / 2);
  push(
    theme.dim("╭" + "─".repeat(gapL)) +
    theme.muted(versionTag) +
    theme.dim("─".repeat(gap - gapL) + "╮"),
  );

  if (useWideLayout) {
    // ── Two-column layout ──
    const cmdNameW = 16;
    const descW = Math.max(10, rightW - cmdNameW - 2);

    const leftLines: string[] = [""];

    const pushLabeled = (label: string, value: string, color: "text" | "dim") => {
      const valueW = Math.max(1, leftW - 12);
      leftLines.push(
        theme.dim(label.padEnd(10)) + " " + theme.semantic(color, truncateToWidth(value, valueW)),
      );
    };

    pushLabeled("model", data.model, "text");
    pushLabeled("directory", data.directory, "text");
    pushLabeled("session", data.session, "dim");
    leftLines.push("");
    pushLabeled("system", data.system, "dim");
    leftLines.push("");
    leftLines.push(theme.dim(`${data.agentCount} agents · ${data.toolCount} tools`));

    // Agents
    if (data.agents.length > 0) {
      leftLines.push("");
      leftLines.push(theme.accent("Agents"));
      const agentText = data.agents.join(" · ");
      leftLines.push(theme.dim(truncateToWidth(agentText, leftW * 2)));
    }

    // Last activity
    if (data.lastActivity) {
      leftLines.push("");
      leftLines.push(theme.accent("Last Activity"));
      leftLines.push(theme.dim(truncateToWidth(data.lastActivity, leftW * 2)));
    }

    // Right column: workflows
    const rightLines: string[] = ["", theme.accent("Research Workflows")];

    for (const wf of data.workflows) {
      const desc = truncateToWidth(wf.desc, descW);
      rightLines.push(
        theme.accent(padRight(wf.cmd, cmdNameW)) + " " + theme.dim(desc),
      );
    }

    const maxRows = Math.max(leftLines.length, rightLines.length);
    for (let i = 0; i < maxRows; i++) {
      const left = leftLines[i] ?? "";
      const right = rightLines[i] ?? "";
      push(
        `│ ${padRight(left, leftW)}${theme.dim(" │ ")}${padRight(right, rightW)} │`,
      );
    }
  } else {
    // ── Single-column layout ──
    const narrowValW = Math.max(1, contentW - 12);
    push(boxRow("", cardW));
    push(boxRow(`${theme.dim("model".padEnd(10))} ${theme.semantic("text", truncateToWidth(data.model, narrowValW))}`, cardW));
    push(boxRow(`${theme.dim("directory".padEnd(10))} ${theme.semantic("text", truncateToWidth(data.directory, narrowValW))}`, cardW));
    push(boxRow(`${theme.dim("session".padEnd(10))} ${theme.dim(truncateToWidth(data.session, narrowValW))}`, cardW));
    push(boxRow(theme.dim(truncateToWidth(data.system, contentW)), cardW));
    push(boxRow(theme.dim(truncateToWidth(`${data.agentCount} agents · ${data.toolCount} tools`, contentW)), cardW));
    push(boxRow("", cardW));
    push(boxSep(cardW));
    push(boxRow(theme.accent("Research Workflows"), cardW));
    const narrowDescW = Math.max(1, contentW - 18);
    for (const wf of data.workflows) {
      push(boxRow(
        `${theme.accent(padRight(wf.cmd, 16))} ${theme.dim(truncateToWidth(wf.desc, narrowDescW))}`,
        cardW,
      ));
    }
  }

  push(theme.dim(boxBottom(cardW)));
  push("");
  push("");

  return lines;
}

// ── Simple info header (for non-TTY / quick output) ──────────────

export function renderSimpleHeader(): string[] {
  const lines: string[] = [];
  lines.push("");
  for (const line of PROTACXTEND_LOGO) {
    lines.push(`  ${line}`);
  }
  lines.push(`  ${SUBTITLE}`);
  lines.push(`  ${CONTRACT}`);
  lines.push("");
  return lines;
}
