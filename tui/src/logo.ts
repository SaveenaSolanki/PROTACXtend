/**
 * PROTACXtend Logo — exact-case block wordmark.
 *
 * Renders the true product name `PROTACXtend` (capital PROTACX + lowercase
 * `tend`) as a solid-block banner, matching the width profile of the
 * earlier all-caps art so it stays a one-piece header wordmark.
 */

// ── Glyph set (5 wide × 5 tall) ──────────────────────────────────
// Height model (from the PROTACXtend header reference): caps are full
// height; lowercase e/n sit at x-height (top row empty, baseline aligned);
// lowercase t/d keep visible ascenders. Bottom rows are baseline-aligned.

type Glyph = [string, string, string, string, string];

const GLYPHS: Record<string, Glyph> = {
  P: ["█████", "██  █", "█████", "██   ", "██   "],
  R: ["█████", "██  █", "████ ", "██ █ ", "██  █"],
  O: ["█████", "█   █", "█   █", "█   █", "█████"],
  T: ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
  A: ["  █  ", " █ █ ", "█████", "█   █", "█   █"],
  C: ["█████", "█    ", "█    ", "█    ", "█████"],
  X: ["█   █", " █ █ ", "  █  ", " █ █ ", "█   █"],
  // lowercase tail of the exact brand name (PROTAC**Xtend**)
  t: ["  █  ", " ███ ", "  █  ", "  █  ", "  ███"],
  e: ["     ", " ███ ", "█   █", "█████", " ████"],
  n: ["     ", "█████", "█   █", "█   █", "█   █"],
  d: ["    █", " ██ █", "█  ██", "█  ██", " ██ █"],
};

/** Inter-character gap in the wordmark (keeps adjacent glyphs apart). */
const GLYPH_GAP = 2;

/** Assemble a glyph-string wordmark from per-letter rows. */
export function renderWordmark(text: string): string[] {
  const rows = ["", "", "", "", ""];
  for (let i = 0; i < text.length; i++) {
    const glyph = GLYPHS[text[i]];
    if (!glyph) continue;
    if (i > 0) {
      for (let r = 0; r < 5; r++) rows[r] += " ".repeat(GLYPH_GAP);
    }
    for (let r = 0; r < 5; r++) rows[r] += glyph[r];
  }
  return rows.map((r) => r.replace(/\s+$/, ""));
}

/** The exact tool name, spelled in the wordmark (exported for reuse). */
export const BRAND_NAME = "PROTACXtend";

// Art rows (kept as the `PROTACXTEND_LOGO` export for header compatibility).
export const PROTACXTEND_LOGO: string[] = renderWordmark(BRAND_NAME);

export const SUBTITLE = "Evidence-grounded targeted protein degradation research";
export const TAGLINE = "An autonomous research system for degrader science · Ahuja Lab, IIIT Delhi";
export const CONTRACT = "KNOW  →  REASON  →  DESIGN  →  DISCOVER";
export const PHASES = ["KNOW", "REASON", "DESIGN", "DISCOVER"];
