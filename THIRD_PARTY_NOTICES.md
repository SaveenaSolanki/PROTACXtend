# Third-Party Notices

## Feynman

This project contains code derived from the **Feynman** AI research agent.

- **Copyright**: (c) 2026 Companion, Inc.
- **License**: MIT License
- **Repository**: https://github.com/companion-inc/feynman
- **License File**: See https://github.com/companion-inc/feynman/blob/main/LICENSE

### Derived Files

The following files in this project are derived from or inspired by Feynman's implementation:

| File | Derived From | Nature of Derivation |
|------|-------------|---------------------|
| `tui/src/theme.ts` | `extensions/research-tools/feynman.json` | Color palette (ink/paper/sage/teal/rose) |
| `tui/src/terminal.ts` | `src/ui/terminal.ts` | ANSI rendering helpers, box drawing, panel printing |
| `tui/src/header.ts` | `extensions/research-tools/header.ts` | Two-column header layout, responsive rendering |
| `tui/themes/protacxtend.json` | `.feynman/themes/feynman.json` | Theme structure and color variables |
| `docs/FEYNMAN_TUI_PORT_AUDIT.md` | Various Feynman source files | Architecture study |

### MIT License (Feynman)

```
MIT License

Copyright (c) 2026 Companion, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Attribution

PROTACXtend acknowledges and感谢 the Feynman project for inspiration on:
- Terminal color palette and theme system
- Responsive two-column header layout
- Box-drawing panel rendering
- Clean Unicode UI patterns (no emojis in core interface)
- Extension-based command architecture patterns

All scientific functionality (PROTAC design, chemistry, ML models) is original
to PROTACXtend and does not derive from Feynman.
