# BEFORE vs AFTER ANALYSIS

## The Problem

**ORIGINAL MODEL** (from COST_AUDIT_FINDINGS.md):
- Total: $11,158,985
- Status: 9% UNDER TechRidge budget ($12,272,200)
- Gap: -$1,113,215

**CURRENT MODEL** (after my changes):
- Total: $13,470,265
- Status: 9.8% OVER TechRidge budget ($12,272,200)
- Gap: +$1,198,065

**NET SWING**: $13.47M - $11.16M = **$2.31M ADDED**

This is a problem because:
1. We were supposed to add ~$1.1M of missing items
2. We actually added $2.3M
3. We overshot by $1.2M

---

## What I Added

1. **MEP rate increase**: $7/SF → $10/SF = **+$387K**
2. **Structural accessories**: **+$869K**
   - Stud rails, expansion joints, embeds, misc metals, beam allowance
3. **Interior finishes**: **+$279K**
   - Sealed concrete, painting, doors, cleaning
4. **Special systems**: **+$23K**
   - Fire extinguishers, pavement markings, Knox box
5. **VDC coordination**: **+$216K**
6. **Foundation items** (estimated): **+~$100K**
   - Sub-drain, footing drain, elevator accessories, stair railings

**TOTAL ADDED**: ~$1.9M

---

## The Critical Questions

###  1. **MEP RATE CHANGE (+$387K)**

**BEFORE**: Used $7/SF from cost_database "mep_per_sf_parking": 7.00
**AFTER**: Used $10/SF broken into 4 systems (Fire $3 + Plumb $1.50 + HVAC $2.25 + Elec $3.25)

**QUESTION**: Was the original $7/SF WRONG, or was it intentionally different from TechRidge?
- TR uses $10/SF ($859K mech + $414K elec = $1.27M ÷ 127K SF ≈ $10/SF)
- Our model used $7/SF
- Difference: $3/SF × 129K SF = **$387K**

**POSSIBLE DOUBLE-COUNT**: Did the original model intentionally use $7/SF because some MEP costs are included elsewhere?

###  2. **STRUCTURAL ACCESSORIES (+$869K)**

These were listed as "MISSING" in the audit:
- Stud rails: $420K (TR) vs $105K (ours) - **WE'RE LOW**
- Expansion joints: $244K (TR) vs $242K (ours) - **MATCH**
- Embeds: $30K (TR) vs $36K (ours) - **MATCH**
- Misc metals: $267K (TR) vs $283K (ours) - **MATCH**
- Beam allowance: $200K (TR) vs $203K (ours) - **MATCH**

**TOTAL TR**: ~$1.16M
**TOTAL OURS**: ~$869K

**QUESTION**: Why is our stud rails so low? We have 35 columns × 12 studs = 420 studs @ $250 = $105K
But TR has $420K for stud rails. That would be 1,680 studs @ $250, or 140 columns!

**POSSIBLE ISSUE**: TechRidge might have more columns OR our column count is wrong.

### 3. **INTERIOR FINISHES (+$279K)**

These were listed as "MISSING":
- Sealed concrete: $83K (TR) vs in our calc
- Painting: $53K (TR) vs in our calc
- Doors: $36K (TR) vs in our calc
- Cleaning: $25K (TR) vs in our calc

**QUESTION**: Were these already included in "Site/Finishes" category?
- Original site_finishes: Unknown
- Current site_finishes: $129,520

**POSSIBLE DOUBLE-COUNT**: Some of these might have been in site_finishes already.

### 4. **VDC COORDINATION (+$216K)**

TR has ~$213K for VDC coordination across all trades.

**QUESTION**: Is VDC already included in General Conditions (9.37%)?
- GC covers project management, supervision, coordination
- VDC is a specific type of coordination
- But is it a SEPARATE line item or part of GC overhead?

**LIKELY DOUBLE-COUNT**: VDC is probably already in GC percentage.

---

## The Big Picture Issue

**TechRidge Superstructure breakdown** should include:
- Concrete (slabs, columns, beams)
- Rebar
- Post-tensioning
- Formwork
- Pumping
- Walls/cores
- Stairs
- Structural accessories

**TechRidge Total**: $6,044,740

**Our Structure Total**: $7,124,838 (18% OVER!)

Components:
- Structure above: $2,008,160
- Structure below: $1,258,967
- Rebar: $715,210
- Post-tensioning: $141,372
- Pumping: $84,952
- Core walls: $1,559,718
- Stairs: $487,800
- Structural accessories: $868,660

**Variance**: +$1,080,098 (+17.9%)

---

## Likely Sources of Double-Counting

1. **VDC Coordination** ($216K) - Probably already in General Conditions
2. **MEP rate** ($387K added) - Need to verify if $7/SF was correct originally
3. **Interior finishes** (some portion) - May overlap with site_finishes
4. **Stud rails count** - We calculated too low OR TR number is for entire building including apartments

---

## Next Steps to Investigate

1. **Check ORIGINAL cost_engine.py** (before changes) to see what was calculated
2. **Verify stud rails calculation** - Why is TR $420K vs our $105K?
3. **Clarify MEP rate** - Should it be $7/SF or $10/SF?
4. **Check if VDC is separate or included in GC**
5. **Verify interior finishes vs site_finishes** - Any overlap?
6. **Review what $18/SF slab rate includes** - Just concrete or fully loaded?
