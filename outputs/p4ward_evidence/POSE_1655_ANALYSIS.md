# Pose #1655 — Structural Data and Honest Assessment

**Regenerated:** 2026-07-06
**Files:** `hmgb2_pose_1655.pdb`, `crbn_pose_1655.pdb`

---

## What Pose #1655 Actually Represents

Pose #1655 is one of 3600 MegaDock orientations of CRBN around HMGB2. It was selected from the closest 100 poses for having:
- 167 atom contacts between HMGB2 and CRBN (moderate interface)
- 4 steric clashes (acceptable)
- HMGB2 lysine K152 at 16.6 Å from CRBN active site (accessible for ubiquitination)

## What This Data Can and Cannot Say

### ✅ Valid findings from this pose:

1. **HMGB2 and CRBN surfaces are complementary** — they can form 167 atom contacts without major clashes. This is a real protein-protein interface finding.

2. **HMGB2 lysines are all accessible** — all 40 lysines are within 60 Å of CRBN's E2~Ub machinery. K152 is the closest at 16.6 Å.

3. **The interface geometry exists** — the PDB coordinates are real and can be loaded into PyMOL for inspection.

### ❌ What I incorrectly claimed:

1. **"ICM acts as a molecular glue"** — Cross-check proved ICM contributes ZERO contacts to this interface. ICM is on the far side of HMGB2 (105° away from CRBN).

2. **"ICM enhances HMGB2-CRBN binding"** — With-ICM vs without-ICM comparison shows no difference. Interface forms between the proteins themselves, independent of ICM.

## Cross-Check Evidence

```
Pose #1655 interface contacts:
  WITH    ICM: 167 atom contacts between HMGB2+ICM and CRBN
  WITHOUT ICM: 167 atom contacts between HMGB2 and CRBN
  ICM contribution: 0 contacts
  ICM-CRBN direct contact: NONE
```

## How to Use This Data in Your Presentation

The slide deck (`HMGB2_PROTAC_Meeting.pptx`) and all PROTAC analysis is **unaffected** — those conclusions are solid.

The molecular glue claim was mine alone and I retract it. Use the PDB files for structural inspection, but the data does NOT support ICM as a molecular glue.

## Key Takeaway for Your PI

> HMGB2 and CRBN do have complementary surfaces and can approach each other. But ICM does NOT participate in or enhance this interface. ICM has no role as a molecular glue. The data that is robust: PROTAC design failed because ICM is buried with no exit vector; 16 longer linkers tested all fail (<1% pass rate); HMGB2 needs a different warhead.
