# Cost Calculation Cleanup Summary

**Date**: 2025-11-08
**Objective**: Remove all derived averages and multipliers; ensure 100% discrete component-based costing

---

## Changes Made

### 1. Fixed Wall Cost Calculations (Line 1509)

**Problem**: Barrier wall costs were using a broken method call `_get_wall_12in_cost_per_cy()` that attempted to convert $/SF to $/CY incorrectly.

**Root Cause**:
- Wall SF values already account for both faces (geometry multiplies by 2 for formwork on both sides)
- Converting to $/CY was mathematically incorrect and conceptually wrong
- The $28.50/SF rate applies to both-faces-already-counted SF

**Fix**:
```python
# BEFORE (BROKEN):
barrier_concrete_cost = barrier_cy * self._get_wall_12in_cost_per_cy()

# AFTER (FIXED):
# NOTE: barrier_sf already accounts for both faces (geometry module multiplies by 2)
# Cost at $28.50/SF applies to both-faces-already-counted SF
wall_cost_per_sf = self.component_costs['core_wall_12in_cost_per_sf']  # $28.50/SF
barrier_concrete_cost = barrier_sf * wall_cost_per_sf
```

**Files Changed**:
- `src/cost_engine.py` line 1509

---

### 2. Removed Below-Grade Multipliers

**Problem**: Code used legacy multipliers (1.83× first level, 1.27× subsequent) applied to $26/SF average cost for below-grade structure. This contradicted the discrete component approach used for above-grade.

**Key Insight**: Below-grade levels have the SAME geometry as above-grade:
- Split-level system: Half-levels with ~50% footprint continue below grade
- Single-ramp system: Full floors at 100% footprint continue below grade
- The `DiscreteLevelCalculator` already calculates this correctly

**Fix**: Consolidated ALL structure calculation into single method using discrete components:
```python
def _calculate_structure_above(self, garage: SplitLevelParkingGarage) -> float:
    """Calculate ALL structure costs (both above and below grade) using discrete components"""

    # Suspended PT slabs (8" thick) - ALL levels
    slab_cost_per_sf = self.costs['structure']['suspended_slab_8in_sf']  # $18/SF
    total_slab_cost = garage.suspended_levels_sf * slab_cost_per_sf

    # Columns (18" × 24" @ 31' grid) - ALL levels
    column_cost_per_cy = self.costs['structure']['columns_18x24_cy']  # $950/CY
    total_column_cost = garage.concrete_columns_cy * column_cost_per_cy

    return total_slab_cost + total_column_cost

def _calculate_structure_below(self, garage: SplitLevelParkingGarage) -> float:
    """DEPRECATED: Returns 0 (all structure calculated in _calculate_structure_above)"""
    return 0
```

**Rationale**: Since we use the same rates ($18/SF slabs, $950/CY columns) for both above and below grade, and the geometry properties (`suspended_levels_sf`, `concrete_columns_cy`) already include ALL levels with correct geometry, there's no need to split this calculation.

**Files Changed**:
- `src/cost_engine.py` lines 331-382

---

### 3. Deleted All Derived Unit Costs

**Problem**: The `derived_unit_costs` section in `cost_database.json` contained 4 legacy average values that were either unused or wrong:

```json
"derived_unit_costs": {
  "foundation_per_sf_footprint": 36.50,        // NOT USED - code uses discrete footings
  "mep_per_sf_parking": 7.00,                  // NOT USED + WRONG (we use $10/SF itemized)
  "exterior_per_lf_perimeter_per_ft_height": 12.00,  // NOT USED - we use $82/SF
  "ramp_system_fixed_cost": 0                  // Used but always 0
}
```

**Analysis**:
1. **`foundation_per_sf_footprint: 36.50`** - Never used. Code calculates from discrete components: slab on grade, vapor barrier, gravel, spread footings, continuous footings (all with individual rebar calculations)

2. **`mep_per_sf_parking: 7.00`** - Never used. Code uses itemized breakdown: $3.00 fire + $1.50 plumbing + $2.25 HVAC + $3.25 electrical = $10.00/SF

3. **`exterior_per_lf_perimeter_per_ft_height: 12.00`** - Never used. Code uses $82/SF parking screen applied to actual exterior wall SF

4. **`ramp_system_fixed_cost: 0`** - Used once but value is always 0 (ramp costs come from discrete components: walls, barriers, curbs)

**Fix**:
- Deleted entire `derived_unit_costs` section from `data/cost_database.json`
- Removed `self.derived = cost_database['derived_unit_costs']` from `cost_engine.py` line 106
- Hardcoded `costs['ramp_system'] = 0` at line 133 with comment explaining ramp costs come from discrete components

**Files Changed**:
- `data/cost_database.json` (deleted lines 114-119)
- `src/cost_engine.py` (removed line 106, updated line 133)

---

## Verification

### Test Results

**Test Suite**: `test_cost_validation.py`
- ✓ Footing rebar NOT double-counted
- ✓ Total cost within reasonable range (±20%)
- ✓ Cost components sum correctly
- ✓ Soft costs calculated correctly on (hard + GC)

**Comprehensive Audit**: `audit_tr_comparison.py`
- Our Total: $11,892,120
- TechRidge Total: $12,272,200
- **Variance: -$380,080 (-3.1%)** ✓ EXCELLENT

### Key Validations

1. **No Double-Counting**:
   - Footing rebar: $100,858 (in foundation only, NOT in rebar component)
   - Column/slab rebar: $659,064 (separate line item)
   - Unit costs include ONLY concrete + formwork + placement
   - Rebar, PT, pumping are all separate line items

2. **Discrete Components Only**:
   - Foundation: From discrete footing calculations (spread + continuous + rebar)
   - Structure: From discrete quantities (slab SF × $18, column CY × $950)
   - Walls: From SF × $28.50 (both faces already counted)
   - MEP: From itemized breakdown ($3+$1.50+$2.25+$3.25 = $10/SF)
   - No averages, no multipliers, no shortcuts

3. **Geometry Accuracy**:
   - Below-grade levels use same geometry as above-grade (split-level or single-ramp)
   - `DiscreteLevelCalculator` handles all levels correctly
   - Total GSF: 129,276 SF (vs TechRidge 127,325 SF = +1.5% variance due to different stall layouts)

---

## Summary

**Before**: Mixed approach with some discrete calculations, some derived averages, some multipliers, broken wall cost conversions, and inconsistent below-grade handling.

**After**: 100% discrete component-based costing. Every cost traces to:
1. Actual quantity from geometry engine (SF, CY, LBS, LF, EA)
2. Unit cost from `cost_database.json`
3. Simple multiplication (no conversions, no averages, no multipliers)

**Impact**:
- Cleaner, more maintainable code
- Easier to audit and validate against real budgets
- More accurate as building parameters change
- Eliminates conceptual errors (like wall SF → CY conversion)
- All tests passing with -3.1% variance vs TechRidge benchmark
