/**
 * PROTACXtend Theme — Derived from Feynman theme (MIT, Companion Inc).
 *
 * Original palette by Companion, Inc. Adapted for PROTACXtend branding.
 * See THIRD_PARTY_NOTICES.md for attribution.
 */

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── Feynman-derived palette ──────────────────────────────────────

const VARS = {
  ink:      "#d3c6aa",
  paper:    "#2d353b",
  paper2:   "#343f44",
  paper3:   "#3a464c",
  panel:    "#374247",
  stone:    "#9da9a0",
  ash:      "#859289",
  darkAsh:  "#5c6a72",
  sage:     "#a7c080",
  teal:     "#7fbbb3",
  rose:     "#e67e80",
  violet:   "#d699b6",
  orange:   "#e69878",
  selection: "#425047",
  successBg: "#2f3b32",
  errorBg:  "#3b3135",
} as const;

type ColorName = keyof typeof VARS;

const SEMANTIC = {
  accent:       "sage" as ColorName,
  border:       "stone" as ColorName,
  borderAccent: "teal" as ColorName,
  borderMuted:  "darkAsh" as ColorName,
  success:      "sage" as ColorName,
  error:        "rose" as ColorName,
  warning:      "stone" as ColorName,
  dim:          "ash" as ColorName,
  text:         "ink" as ColorName,
  muted:        "stone" as ColorName,
  // PROTACXtend-specific (used sparingly)
  protacOrange: "orange" as ColorName,
} as const;

type SemanticName = keyof typeof SEMANTIC;

// ── ANSI escape helpers ──────────────────────────────────────────

const RESET = "\x1b[0m";
const BOLD  = "\x1b[1m";
const DIM   = "\x1b[2m";

function rgb(hex: string): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `\x1b[38;2;${r};${g};${b}m`;
}

function bgRgb(hex: string): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `\x1b[48;2;${r};${g};${b}m`;
}

// ── Theme object ─────────────────────────────────────────────────

export interface Theme {
  /** Get raw ANSI color code for a palette variable */
  raw(name: ColorName): string;
  /** Get raw ANSI color code for a semantic color */
  rawSemantic(name: SemanticName): string;
  /** Colorize text with a palette variable */
  fg(name: ColorName, text: string): string;
  /** Colorize text with a semantic color */
  semantic(name: SemanticName, text: string): string;
  /** Bold text */
  bold(text: string): string;
  /** Dim text */
  dim(text: string): string;
  /** Reset */
  reset: string;
  /** Combined: bold + semantic color */
  accent(text: string): string;
  /** Combined: bold + error color */
  error(text: string): string;
  /** Combined: bold + success color */
  success(text: string): string;
  /** Combined: dim */
  muted(text: string): string;
  /** Get hex value for a semantic color */
  hex(name: SemanticName): string;
}

function createTheme(overrides?: Record<string, string>): Theme {
  const vars = { ...VARS, ...overrides };

  return {
    raw: (name) => rgb(vars[name] ?? vars.ink),
    rawSemantic: (name) => rgb(vars[SEMANTIC[name]] ?? vars.ink),
    fg: (name, text) => `${rgb(vars[name] ?? vars.ink)}${text}${RESET}`,
    semantic: (name, text) => `${rgb(vars[SEMANTIC[name]] ?? vars.ink)}${text}${RESET}`,
    bold: (text) => `${BOLD}${text}${RESET}`,
    dim: (text) => `${DIM}${text}${RESET}`,
    reset: RESET,
    accent: (text) => `${BOLD}${rgb(vars[SEMANTIC.accent])}${text}${RESET}`,
    error: (text) => `${BOLD}${rgb(vars[SEMANTIC.error])}${text}${RESET}`,
    success: (text) => `${BOLD}${rgb(vars[SEMANTIC.success])}${text}${RESET}`,
    muted: (text) => `${DIM}${rgb(vars[SEMANTIC.muted])}${text}${RESET}`,
    hex: (name) => vars[SEMANTIC[name]] ?? vars.ink,
  };
}

export { createTheme, RESET, BOLD, DIM, rgb, bgRgb };
export type { ColorName, SemanticName };
