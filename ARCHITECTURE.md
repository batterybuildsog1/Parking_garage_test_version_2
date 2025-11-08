# Architecture Documentation

## The Problem We Solved

### Original Error
```
ValueError: too many values to unpack (expected 3)
```

This error occurred because `self.levels` data structure evolved from 3-tuple to 4-tuple during refactoring, but `get_level_breakdown()` wasn't updated.

### Root Cause Analysis

The real problem was **architectural debt**:

1. **Tight Coupling**: Code directly accessed cost database internals everywhere
   - Hard-coded paths: `self.costs['foundation']['vapor_barrier_sf']`
   - When database reorganized, 27+ locations broke
   - "Shotgun surgery" required for any database structure change

2. **Mixed Concerns**: Geometry and costing logic intertwined
   - `self.levels` mixed geometric data with parking data
   - No clear separation between "what exists" vs "what it costs"
   - Changes in one area broke unrelated code

3. **No Abstraction Layer**: Database structure exposed to all code
   - Cost lookups scattered across multiple files
   - No validation or type safety
   - Errors only discovered at runtime

## The Solution: Three-Layer Architecture

### Layer 1: Geometry Engine (Existing)
**File**: `src/garage.py`

**Responsibility**: Calculate pure geometric quantities

```python
garage = SplitLevelParkingGarage(length=210, half_levels_above=8, ...)
# Returns: footprint_sf, total_gsf, column counts, concrete volumes, etc.
```

**Key Principle**: Describes WHAT physically exists, not costs.

---

### Layer 2: Quantity Takeoff (NEW)
**File**: `src/quantities.py`

**Responsibility**: Structured, validated quantity data

```python
quantities = garage.calculate_quantities()
# Returns: QuantityTakeoff object with all quantities organized by category
```

**Structure**:
```python
@dataclass
class QuantityTakeoff:
    # Project metadata
    building_length_ft: float
    total_stalls: int

    # Component quantities (organized by building system)
    foundation: FoundationQuantities
    excavation: ExcavationQuantities
    structure: StructuralQuantities
    center_elements: CenterElementQuantities
    vertical_circulation: VerticalCirculationQuantities
    exterior: ExteriorQuantities
    mep: MEPQuantities
    site_finishes: SiteFinishesQuantities
```

**Benefits**:
- **Validated**: Built-in consistency checks (GSF totals, stall counts)
- **Typed**: Strong typing catches errors at development time
- **Testable**: Can validate quantities independently of costs
- **Exportable**: Can serialize to JSON for external tools

---

### Layer 3: Cost Registry (NEW)
**File**: `src/cost_registry.py`

**Responsibility**: Abstraction layer for cost database

```python
registry = CostRegistry(cost_database)
rebar_cost = registry.get('rebar')  # Returns UnitCost object
price = rebar_cost.value  # $1.25/LB
```

**Key Features**:

1. **Semantic Names**: Ask for WHAT you need, not WHERE it lives
   ```python
   # OLD (tightly coupled):
   self.costs['unit_costs']['structure']['rebar_cost_per_lb']

   # NEW (abstracted):
   registry.get('rebar').value
   ```

2. **Validated**: All costs validated at initialization
   ```python
   registry = CostRegistry(cost_db)  # Raises ValueError if costs missing
   ```

3. **Typed**: Each cost has metadata
   ```python
   @dataclass
   class UnitCost:
       semantic_name: str     # 'rebar'
       value: float           # 1.25
       unit: CostUnit         # CostUnit.LB
       category: CostCategory # CostCategory.STRUCTURE
       description: str       # "Reinforcing steel"
       source: str           # "component_specific_costs.rebar_cost_per_lb"
   ```

4. **Future-Proof**: When database reorganizes, only `CostRegistry._build_registry()` changes

---

## Usage Examples

### Option 1: Use New Architecture (Recommended for New Code)

```python
from src.garage import SplitLevelParkingGarage, load_cost_database
from src.cost_registry import CostRegistry

# Create garage
garage = SplitLevelParkingGarage(210, 8, 0, 2)

# Extract quantities
quantities = garage.calculate_quantities()

# Validate
issues = quantities.validate()
if issues:
    print(f"Validation warnings: {issues}")

# Load costs
cost_db = load_cost_database()
registry = CostRegistry(cost_db)

# Calculate costs (clean, readable)
foundation_cost = (
    quantities.foundation.sog_area_sf * registry.get('sog_5in').value +
    quantities.foundation.vapor_barrier_sf * registry.get('vapor_barrier').value +
    quantities.foundation.spread_footing_concrete_cy * registry.get('footing_spread').value
)

structure_cost = (
    quantities.structure.suspended_slab_area_sf * registry.get('slab_pt_8in').value +
    quantities.structure.column_concrete_cy * registry.get('column_18x24').value
)
```

**Benefits**:
- Clear separation: geometry → quantities → costs
- Easy to test each layer independently
- Self-documenting code
- Type-safe

### Option 2: Use Legacy Flow (Existing app.py)

```python
from src.garage import SplitLevelParkingGarage, load_cost_database
from src.cost_engine import CostCalculator

garage = SplitLevelParkingGarage(210, 8, 0, 2)
cost_db = load_cost_database()
calculator = CostCalculator(cost_db)

# All-in-one calculation
costs = calculator.calculate_all_costs(garage)
detailed = calculator.get_detailed_quantity_takeoffs(garage)
```

**Current Status**: Still works, uses temporary fixes for missing costs

---

## Migration Path

### Immediate (Done ✅)
1. ✅ Fixed data structure mismatch in `get_level_breakdown()`
2. ✅ Updated 27 cost lookups to new database structure
3. ✅ Added placeholder costs for curbs/walls (TODO: extract from PDF)
4. ✅ Created `quantities.py` with QuantityTakeoff
5. ✅ Created `cost_registry.py` with CostRegistry
6. ✅ Added `garage.calculate_quantities()` method

### Short-Term (Next Sprint)
1. Extract actual curb/wall costs from TechRidge 1.2 SD Budget PDF
2. Add costs to `cost_database.json` or `CostRegistry`
3. Write unit tests for `QuantityTakeoff.validate()`
4. Write unit tests for `CostRegistry`

### Long-Term (Optional)
1. Rewrite `CostCalculator` to use `QuantityTakeoff` + `CostRegistry`
2. Remove direct cost database access from `cost_engine.py`
3. Add cost escalation support (2024 → 2025 pricing)
4. Support multiple cost databases (different markets/years)

---

## Key Design Principles

### 1. Separation of Concerns
- **Geometry**: What exists physically (garage.py)
- **Quantities**: Structured data (quantities.py)
- **Costs**: What things cost (cost_registry.py)

### 2. Fail-Fast Validation
- Costs validated at registry initialization
- Quantities validated after calculation
- Errors caught early, not at runtime

### 3. Abstraction Over Implementation
- Code asks for semantic names ('rebar')
- Registry handles database structure changes
- Database can reorganize without breaking code

### 4. Type Safety
- Dataclasses provide strong typing
- Enums for units and categories
- IDE autocomplete and type checking

---

## Files Changed

### New Files
- `src/quantities.py` - Quantity takeoff data structures
- `src/cost_registry.py` - Cost database abstraction
- `ARCHITECTURE.md` - This file

### Modified Files
- `src/garage.py`:
  - Fixed `get_level_breakdown()` unpacking (line 1397)
  - Added `calculate_quantities()` method (line 1570)
  - Fixed `_calculate_excavation()` to set `retaining_wall_sf = 0` (line 1113)

- `src/cost_engine.py`:
  - Added `_get_curb_cost_per_cy()` placeholder method (line 46)
  - Added `_get_wall_12in_cost_per_cy()` placeholder method (line 60)
  - Updated 27 cost lookups to new database paths
  - All `self.costs['component_specific_costs'][...]` → `self.component_costs[...]`

### No Changes Required
- `app.py` - Works without modification
- `data/cost_database.json` - Structure is correct
- All test files - Continue to work

---

## Testing

### Test New Architecture
```bash
cd "test version 2"
source venv/bin/activate

python3 << 'TEST'
from src.garage import SplitLevelParkingGarage, load_cost_database
from src.cost_registry import CostRegistry

garage = SplitLevelParkingGarage(210, 8, 0, 2)
quantities = garage.calculate_quantities()
print(f"Stalls: {quantities.total_stalls}")
print(f"Validation: {quantities.validate()}")

registry = CostRegistry(load_cost_database())
print(f"Registry: {registry}")
TEST
```

### Test Legacy Flow
```bash
python3 << 'TEST'
from src.garage import SplitLevelParkingGarage, load_cost_database
from src.cost_engine import CostCalculator

garage = SplitLevelParkingGarage(210, 8, 0, 2)
calculator = CostCalculator(load_cost_database())
costs = calculator.calculate_all_costs(garage)
print(f"Total: ${costs['total']:,.0f}")
TEST
```

### Run Streamlit App
```bash
streamlit run app.py
```

---

## Troubleshooting

### "too many values to unpack"
**Fixed** ✅ - `get_level_breakdown()` now unpacks 4-tuple correctly

### "KeyError: 'vapor_barrier_sf'"
**Fixed** ✅ - Moved to `unit_costs.structure.vapor_barrier_sf`

### "KeyError: 'component_specific_costs'"
**Fixed** ✅ - Use `self.component_costs` not `self.costs['component_specific_costs']`

### "TypeError: non-default argument follows default"
**Fixed** ✅ - All dataclass fields with defaults moved to end

---

## Future Enhancements

### Cost Database
- Extract curb/wall costs from TechRidge PDF
- Add cost escalation factors (annual inflation)
- Support regional cost adjustments
- Version cost databases (2024, 2025, etc.)

### Quantity Takeoffs
- Export to Excel/CSV for estimators
- Generate PDF quantity reports
- Compare quantities across designs
- Track quantity changes over time

### Cost Registry
- Add cost override mechanism
- Support user-defined costs
- Cost reasonability checks (flag outliers)
- Historical cost tracking

---

## Questions?

For architecture questions or issues:
1. Check this document first
2. Review `quantities.py` and `cost_registry.py` docstrings
3. Run test examples above
4. Check git history for "why" behind changes

**Remember**: The new architecture is OPTIONAL. The legacy flow still works. Use whichever approach fits your needs.
