# Feynman TUI Port Audit

**Date**: 2026-09-02
**Reference**: https://github.com/companion-inc/feynman (MIT, Copyright 2026 Companion, Inc.)

## Files Studied

| File | Purpose |
|------|---------|
| `package.json` | Dependencies: `@earendil-works/pi-coding-agent`, `@earendil-works/pi-tui`, `@earendil-works/pi-ai` |
| `src/index.ts` | Entry: patches Node modules, calls `cli.ts:main()` |
| `src/cli.ts` | CLI dispatch: parses args, handles commands, launches Pi chat |
| `src/ui/terminal.ts` | ANSI terminal helpers: `printPanel`, `printAsciiHeader`, `printSection`, colors |
| `logo.mjs` | ASCII art logo for Feynman |
| `extensions/research-tools/header.ts` | **Core header**: uses `ctx.ui.setHeader()` with `render(width)` returning string[] |
| `extensions/research-tools/help.ts` | Help command: builds sections from prompt specs + extension commands |
| `.feynman/themes/feynman.json` | Theme: ink/paper/sage/teal/rose palette, color aliases |
| `src/pi/launch.ts` | Pi chat launcher: creates agent session, starts TUI |
| `src/model/commands.ts` | Model set/list/login/logout commands |

## Architecture Discovery

### How Feynman Initializes
1. `index.ts` → patches Node modules → calls `cli.ts:main()`
2. `cli.ts:main()` → parses args → handles setup/model/etc → falls through to `launchPiChat()`
3. `launchPiChat()` → creates `AgentSession` with Pi coding agent → TUI renders

### How the Header Works
The header is NOT a standalone component — it's a **Pi extension** using `ctx.ui.setHeader()`:

```typescript
ctx.ui.setHeader((_tui, theme) => ({
    render(width: number): string[] {
        // Returns array of strings, one per line
        // Uses theme.fg("accent", text) for coloring
        // Uses theme.bold(text) for bold
        // Adapts layout based on contentW (width - 2)
        // Two-column when contentW >= 70
        // Single column when narrow
    },
    invalidate() {},
}));
```

### How Commands Are Registered
Extensions use `pi.registerCommand()`:
```typescript
pi.registerCommand("help", {
    description: "...",
    handler: async (args, ctx) => { ... }
});
```

### How Theme Works
Theme is a JSON file with:
- `vars`: color hex values (ink, paper, sage, teal, rose, etc.)
- `colors`: semantic aliases (accent, border, error, success, etc.)
- `export`: colors for workbench web export

### How pi-tui Works
`@earendil-works/pi-tui` provides:
- Terminal rendering primitives
- Theme-aware coloring (`theme.fg("accent", text)`)
- Width-aware truncation (`truncateToWidth`, `visibleWidth`)
- Selection UI (`ctx.ui.select()`)
- Notifications (`ctx.ui.notify()`)
- Header registration

### Key Feynman Design Patterns
1. **Extension-based**: All customization via Pi extension API
2. **Theme-driven**: Colors from JSON theme, not hardcoded
3. **Responsive**: Two-column when wide, single when narrow
4. **Logo header**: ASCII art with subtitle lines
5. **Information card**: Model, directory, session, system, agents, workflows
6. **Clean Unicode**: Box drawing, no emojis in core UI

## PROTACXtend Port Strategy

### Approach: Standalone TypeScript TUI + Python JSONL Bridge

Since PROTACXtend is a Python scientific tool (not a Pi coding agent extension), we build:

1. **TypeScript TUI** (`tui/`): Standalone Node CLI using raw ANSI escape codes
2. **Python Bridge** (`protacxtend/tui_bridge/`): JSONL subprocess communication
3. **Theme** (`tui/themes/protacxtend.json`): Feynman-derived palette

### What We Reuse from Feynman
- Color palette (ink/paper/sage/teal/rose)
- Terminal rendering patterns (printPanel, printSection, printAsciiHeader)
- Responsive layout logic (two-column vs single column)
- Box-drawing character style
- Clean Unicode (no emojis in core UI)
- Information card layout (model/system/workflows/agents)

### What We Do NOT Reuse
- Pi coding agent dependency (we're standalone)
- Extension API (we have our own bridge)
- Workbench/server functionality
- AlphaXiv integration

### Python Backend Communication
JSONL over subprocess stdin/stdout:
```
Node TUI → stdin → {"type":"run","request":"Design CRBN PROTACs for BRD4"}
Python   → stdout → {"type":"run_start","run_id":"run_abc123"}
Python   → stdout → {"type":"agent_start","agent":"target_resolver"}
Python   → stdout → {"type":"tool_call","tool":"uniprot_lookup","args":{"target":"BRD4"}}
Python   → stdout → {"type":"evidence","tool":"uniprot_lookup","result":{"uniprot_id":"O60885"}}
Python   → stdout → {"type":"run_complete","status":"ok","candidates":5}
```

## Acceptance Criteria
- [x] Feynman files studied (not guessed)
- [ ] Theme derived from Feynman's actual palette
- [ ] Responsive at 80-160 columns
- [ ] Python backend communicates via JSONL
- [ ] No hard-coded scientific results
- [ ] Attribution included
