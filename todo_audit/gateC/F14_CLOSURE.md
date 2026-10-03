# F-14 closure — `protacpilot-memory` → `protacxtend-memory` rename

Status: **CLOSED** · commit `82a0e4d` · 2026-09-23

## Finding

`todo_audit/FINDINGS.md` F-14: the working tree was dirty — 104 `D`
(`protacpilot-memory/*` removed from disk) plus untracked `protacxtend-memory/`
(338 files). HEAD's message claimed a clean tree. The content of the two trees
looked identical for the old files.

## Pre-commit verification (no data loss)

| check | result |
|---|---|
| tracked files in `protacpilot-memory` at HEAD | 104 |
| of those, byte-identical at `protacxtend-memory/<same path>` | **104 / 104** |
| files present only in the old tree | **0** |
| total files on disk under `protacxtend-memory` | 338 |
| new files beyond the 104 | 234 |
| recursive SHA-256 of all 338 on-disk files | `F14_memory_provenance.json` |

Because every tracked file was byte-identical at the new path, git detected the
change as **104 pure renames** (100% similarity), not delete+add.

## Commit

```
82a0e4d chore(memory): commit protacpilot-memory -> protacxtend-memory rename (F-14)
 .gitignore                                              | 3 +++
 {protacpilot-memory => protacxtend-memory}/...          | 104 renames
```

`.gitignore` now also excludes the generated
`protacxtend-memory/evaluation/`, `/paper/` and `/benchmarks/results/` paths,
mirroring the old `/protacpilot-memory/...` rules. The 74 generated files under
those paths remain on disk, untracked — exactly as before the rename. No memory
data was deleted from the filesystem or the repository.

## Evidence

* `git show --stat 82a0e4d`
* `git diff --cached --find-renames --summary` → 104 rename lines
* `todo_audit/gateC/F14_memory_provenance.json` — full recursive hash of all 338
  files (including ignored/generated ones) taken before the commit.

## Residual

The broader worktree is still dirty with the Gate B source edits and the
untracked `todo/`, `todo_audit/`, `benchmark500/` and `benchmark/gateC/` trees;
those are separate from F-14 and are not part of the rename commit.
