# TechRidge 1.2 Reference Design vs. Our Model: Discrepancy Analysis

**Date:** 2025-11-10
**Comparison:** Our model (1 below + 8 above half-levels) vs. TechRidge 1.2 SD Budget (127,325 SF parking)

## Executive Summary

Overall, our model is **3.1% under budget** ($380k lower cost), which is within acceptable tolerance for SD-level estimating. However, there are **offsetting variances** that cancel out:

### Over-Estimated Categories (Total: +$473k)
- **Foundation & Below-Grade: +49.0%** (+$473k) ❌

###Under-Estimated Categories (Total: -$854k)
- **Site Work: -67.9%** (-$274k) ❌
- **Exterior Closure: -50.2%** (-$417k) ❌
- **Special Systems: -53.6%** (-$27k) ❌
- **Interior Finishes: -11.2%** (-$35k) ⚠️
- **Conveying Systems: -11.4%** (-$40k) ⚠️
- **Electrical: -6.3%** (-$26k) ✓
- **Superstructure: -3.9%** (-$235k) ✓

### Aligned Categories (Within ±10%)
- Superstructure: -3.9% ✓
- Mechanical: +5.3% ✓
- Electrical: -6.3% ✓
- All soft costs (GC, CM Fee, Insurance, Contingency): -2.8% to -3.1% ✓

## Critical Discrepancies Requiring Investigation

---

## 1. STALL COUNT DISCREPANCY (+11.9%, 38 more stalls)

**Our Model:** 357 stalls
**TR Reference:** 319 stalls
**Variance:** +38 stalls (+11.9%)

### Analysis
This is a **fundamental geometry discrepancy**. We're calculating 38 more parking stalls than the reference design with approximately the same GSF.

### Possible Causes
1. **Different stall layout methodology**
   - Our zone attribution approach vs. TR's actual architectural layout
   - TR may have more core blockages, wider aisles, or circulation inefficiencies

2. **Different stall dimensions**
   - Our model uses 9' × 18' stalls (162 SF per stall)
   - TR may use larger stalls (9' × 19' or 9.5' × 18')

3. **Different turn zone efficiency**
   - Our model may overestimate parking capacity in turn zones
   - TR may have geometric constraints we're not modeling (column interference, clearances)

4. **Entry/exit circulation losses**
   - TR has 27' wide entry opening on west side at mid-length
   - Our model may not fully account for this blockage

### Recommended Actions
- [ ] Review stall count calculation in `garage.py` zone attribution logic
- [ ] Compare our stall layout with TR architectural plans (if available)
- [ ] Verify turn zone capacity assumptions
- [ ] Check entry level blockage calculation (27' opening)
- [ ] Consider adding "inefficiency factor" for real-world layouts

### Impact
- **Cost impact:** Minimal (stall count doesn't drive costs directly)
- **Business impact:** CRITICAL - overpromising parking capacity
- **Priority:** **HIGH**

---

## 2. FOUNDATION & BELOW-GRADE (+49.0%, $473k over)

**Our Model:** $1,439,396
**TR Reference:** $965,907
**Variance:** +$473,489 (+49.0%)

### Analysis
We are **significantly over-estimating** foundation costs by nearly 50%. This is the largest absolute variance.

### Breakdown from TR PDF (Page 2-3)
| Component | TR Cost | Notes |
|-----------|---------|-------|
| Footings (continuous + spot) | $1,161,855 | All footing types |
| Foundation walls below grade | $157,235 | CW-10A&B + CW-12A |
| Excavation & backfill | $222,963 | Mass ex, backfill, export |
| Misc (drains, waterproofing, VDC) | $423,854 | |
| **TOTAL** | **$965,907** | |

### Our Model Components
| Component | Our Cost | Notes |
|-----------|----------|-------|
| Footings (spread + continuous) | ~$1,200,000 | ESTIMATED (need to break out) |
| Retaining walls | ~$100,000 | For 1 half-level below (5' height) |
| Excavation | ~$140,000 | |
| **TOTAL** | **$1,439,396** | |

### Possible Causes
1. **Over-designed footings**
   - Our ACI 318-19 iterative solver may be too conservative
   - TR may use simpler/less conservative assumptions
   - We may be using lower soil bearing capacity

2. **Rebar rates too high**
   - We use 110 lbs/CY for continuous footings (from TR)
   - We use 65 lbs/CY for spread footings (from TR)
   - But actual TR quantities may be lower

3. **Footing count/size mismatch**
   - Our column grid may generate more footings
   - Our load calculations may require larger footings

4. **Below-grade walls**
   - 1 half-level below = 5' retaining walls
   - TR P0.5 level (15,073 SF) may not require full-perimeter retaining walls
   - TR may have P0.5 as "grade level" not "below grade"

### Recommended Actions
- [ ] Print detailed footing breakdown from `footing_calculator.py`
- [ ] Compare footing sizes/counts with TR line items (FS10.0, FS12.0, FC4.0, FC10.0, etc.)
- [ ] Review soil bearing capacity assumption (default 2000 PSF)
- [ ] Check if P0.5 interpretation is correct (below vs. at grade)
- [ ] Validate retaining wall necessity for 1 half-level below

### Impact
- **Cost impact:** $473k over-budget on foundation
- **Business impact:** CRITICAL - could price us out of bids
- **Priority:** **CRITICAL**

---

## 3. SITE WORK (-67.9%, $274k under)

**Our Model:** $129,520
**TR Reference:** $403,382
**Variance:** -$273,862 (-67.9%)

### Analysis
We are **severely under-estimating** site work by missing major components.

### TR PDF Components (Page 14-17)
| Component | TR Cost | Notes |
|-----------|---------|-------|
| Demolition | $14,027 | Tree/utility removal |
| Mass excavation (3.5' depth) | $74,617 | Under building footprint |
| Structural fill import | $117,093 | Building pads |
| Over-excavation (6' deep) | $526,894 | Soil improvement |
| Utilities (storm, sewer, water) | $91,000 | Site connections |
| Erosion control | $34,397 | Temp fencing, silt fence, etc. |
| Parking lot (surface parking) | $483,621 | **WAIT - this is separate!** |
| **TOTAL** | **$403,382** | Parking structure sitework only |

### Our Model Missing Components
1. **Over-excavation ($527k in TR)** - We don't model 6' deep soil improvement
2. **Utilities ($91k in TR)** - We have minimal utility connections
3. **Erosion control ($34k in TR)** - We have partial coverage
4. **Mass excavation methodology** - We may calculate differently

### Possible Causes
1. **No over-excavation modeling**
   - TR assumes 6' deep over-ex for poor soils (Option 1 in PDF)
   - This is $527k alone - **MORE than our entire sitework**
   - Our model doesn't include this soil improvement option

2. **Simplified utility connections**
   - We model basic connections (oil/water separator, storm drains)
   - TR includes extensive site utility work

3. **Missing surface parking costs**
   - TR line 683: "On Grade Allowance" $1,378,908
   - This may include surface lot, but it's listed separately

### Recommended Actions
- [ ] Add over-excavation as optional parameter (6' depth standard)
- [ ] Expand utility connection modeling (sewer, water, storm laterals)
- [ ] Review erosion control comprehensiveness
- [ ] Clarify if surface parking lot is in/out of scope

### Impact
- **Cost impact:** $274k under-budget
- **Business impact:** HIGH - missing major site costs
- **Priority:** **HIGH**

---

## 4. EXTERIOR CLOSURE (-50.2%, $417k under)

**Our Model:** $413,280
**TR Reference:** $829,840
**Variance:** -$416,560 (-50.2%)

### Analysis
We are **severely under-estimating** exterior closure costs by exactly 50%.

### TR PDF Components (Page 4-5)
| Component | TR Cost | Notes |
|-----------|---------|-------|
| Parking screen (10,120 SF @ $82/SF) | $829,840 | **ENTIRE category** |
| **TOTAL** | **$829,840** | |

### Our Model Components
| Component | Our Cost | Calculation |
|-----------|----------|-------------|
| Parking screen | $413,280 | ~5,040 SF @ $82/SF |

### Discrepancy Analysis
**We are calculating EXACTLY HALF the parking screen area!**

TR has **10,120 SF** of parking screen
Our model has **~5,040 SF** of parking screen

### Possible Causes
1. **Missing levels**
   - TR may include parking screen on multiple levels
   - We may only be counting one perimeter

2. **Missing sides**
   - We may be calculating only east/west perimeters
   - TR likely includes north/south end walls too

3. **Height calculation error**
   - We may be using single-level height instead of multi-level
   - TR may have screening on P1-P5 (5 levels worth)

4. **Geometry model incomplete**
   - Our `exterior` cost calculation may not properly scale with levels

### Recommended Actions
- [ ] Review parking screen calculation in `cost_engine.py`
- [ ] Verify which levels require screening (P1-P5 in TR)
- [ ] Check if we're calculating all four perimeter sides
- [ ] Compare perimeter length × height × levels vs TR 10,120 SF

### Impact
- **Cost impact:** $417k under-budget
- **Business impact:** CRITICAL - major cost miss
- **Priority:** **CRITICAL**

---

## 5. SPECIAL SYSTEMS (-53.6%, $27k under)

**Our Model:** $23,310
**TR Reference:** $50,200
**Variance:** -$26,890 (-53.6%)

### Analysis
We are **significantly under-estimating** special systems.

### TR PDF Components (Page 11-13)
| Component | TR Cost | Parking Portion |
|-----------|---------|----------------|
| Fire extinguishers & cabinets (110 EA) | $45,100 | $8,200 |
| Bicycle racks (80 EA @ $525) | $42,000 | $42,000 |
| Knox box (2 EA @ $900) | $1,800 | $1,800 |
| Pavement markings (319 stalls @ $55) | $17,545 | $17,545 |
| **TOTAL** | **$106,445** | **$50,200** |

### Our Model Components
Missing detailed breakdown - need to extract from code

### Possible Causes
1. **Missing bicycle racks** ($42k in TR) - largest component
2. **Incomplete pavement markings** - we may have simpler approach
3. **Missing fire extinguishers** - spread across parking + apartments in TR

### Recommended Actions
- [ ] Add bicycle rack quantity calculation (1 per X stalls standard)
- [ ] Verify pavement marking calculation ($55/stall from TR)
- [ ] Check fire extinguisher coverage

### Impact
- **Cost impact:** $27k under-budget (relatively small)
- **Business impact:** MEDIUM
- **Priority:** **MEDIUM**

---

## Summary of Recommended Actions

### CRITICAL PRIORITY
1. **Foundation Over-Estimation (+$473k)**
   - Review footing design methodology
   - Validate soil bearing capacity assumptions
   - Check below-grade level interpretation

2. **Exterior Closure Under-Estimation (-$417k)**
   - Fix parking screen area calculation (we're exactly 50% low)
   - Verify multi-level screening coverage

3. **Stall Count Over-Estimation (+38 stalls, +11.9%)**
   - Validate zone attribution logic
   - Add inefficiency factors for real layouts

### HIGH PRIORITY
4. **Site Work Under-Estimation (-$274k)**
   - Add over-excavation option (6' depth)
   - Expand utility connection modeling

### MEDIUM PRIORITY
5. **Special Systems Under-Estimation (-$27k)**
   - Add bicycle racks
   - Verify pavement markings

---

## Validation Methodology

To validate fixes:

```bash
# After each fix, re-run comparison
cd "test version 2"
python3 test_tr_comparison.py

# Target metrics:
# - Total cost variance: ±5% ($614k tolerance)
# - Individual category variance: ±15%
# - Stall count variance: ±5% (16 stalls)
# - GSF variance: ±5% (6,366 SF)
```

---

## Conclusion

Our model is reasonably accurate at the **total cost level** (-3.1%), but has **significant offsetting errors**:

**Over-estimates:**
- Foundation: +$473k (too conservative)

**Under-estimates:**
- Exterior: -$417k (calculation error)
- Site Work: -$274k (missing components)

These errors happen to cancel out, giving a false sense of accuracy. **All critical discrepancies must be fixed** to ensure reliable cost estimates across different building configurations.
