# TechRidge Parking Garage Analyzer

Interactive parametric cost and geometry analysis tool for podium-style parking structures with dual ramp system support.

## Overview

This tool models the TechRidge parking garage design with **two alternative ramp systems** that auto-select based on building length. It provides real-time cost analysis, 2D floor plans, 3D visualization, and ACI 318-19 compliant structural design.

### Auto-Selected Ramp Systems

**Split-Level Double-Ramp** (< 250' length):
- Two interleaved helical ramps
- Half-levels at 5.328' vertical spacing (10.656' floor-to-floor)
- Each half-level ≈ 50% of footprint
- 5% ramp slope
- 12" solid concrete core walls + 8"×12" curbs

**Single-Ramp Full-Floor** (≥ 250' length):
- One ramp bay with parking on slope
- Full floors at 9.0' vertical spacing
- Each floor = 100% of footprint
- 6.67% ramp slope (IBC maximum)
- 36"×6" ramp barriers (no center walls/curbs)
- **15-20% cost reduction** vs equivalent split-level capacity

**Auto-Selection:** System automatically selected based on building length (250' threshold)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Opens at: `http://localhost:8501`

## Usage

### Parameters (Sidebar)

**Dimensions:**
- **Number of Bays**: 2-7 bays (width auto-calculated)
- **Length**: 150'-360' (ramp system auto-selected at 250')
- **Levels Above**: 2-12 levels above grade
- **Levels Below**: 0-6 levels below grade

**General Conditions:**
- Percentage: 9.37% of hard costs (default)
- Monthly rate: Duration × $191,008/month

**Soil Parameters:**
- Bearing capacity (affects footing sizes)
- Advanced: Unit weight, friction angle

### Interface (5 Tabs)

**📊 Cost Breakdown**
- Detailed hard costs by component
- Soft costs (GC, CM fee, insurance, contingency)
- Pie chart visualization
- All costs from discrete takeoffs (no averages)

**📐 Geometry**
- Dimensions and footprint
- Parking metrics (stalls, SF/stall)
- Structural quantities (columns, concrete, rebar, PT)
- Excavation volumes (if below-grade)

**🏗️ 3D Model**
- Interactive Plotly visualization
- Layer controls: slabs, columns, center elements, cores, barriers
- Camera views: isometric, plan, elevation, perspective
- Floor range filter

**📋 2D Plans**
- Overview: All levels combined with color-coded zones
- Individual levels: Single-level stall layout
- Core blockages, excess space, optimization tips

**📈 Comparison**
- Compare current vs baseline design

## Design Features

### Parametric Width

```
Width = 1' + (num_bays × 61') + ((num_bays - 1) × 3')

Components:
- 0.5' exterior wall
- 61' parking module (18' stall + 25' aisle + 18' stall)
- 3' center spacing (1' curb + 1' wall/barrier + 1' curb)
- 0.5' exterior wall

Examples:
- 2 bays: 126'
- 3 bays: 190'
```

### Variable Length

- Recommended: **31' increments** (structural bay spacing)
- Range: 150' to 360'
- Scales stall count proportionally

### Discrete Level Floor Areas

Each level has individually calculated **Gross Floor Area (GSF)**:

**Split-Level System:**
- **Half-levels** (P0.5, P1.5, P2.5): ~50% of footprint (helical ramp geometry)
- **Full levels** (P1, P2, P3): 100% of footprint (ramp intersections)
- **Entry** ("Grade" at z=0): Half-level with flat entry opening
- **Top level**: Reduced by ramp termination at north end

**Single-Ramp System:**
- **All floors** (P1, P2, P3): 100% of footprint
- **Top level**: Reduced by ramp termination

**Why 50% at split-level half-levels?** At any half-level elevation (e.g., P1.5), only the ramping portions pass through that elevation - not the full footprint.

**This is NOT `footprint × levels`** - each level is modeled discretely based on actual ramp geometry.

### Ramp System Comparison

| Feature | Split-Level | Single-Ramp |
|---------|------------|-------------|
| **Availability** | All lengths ≥ 150' | Lengths ≥ 250' only |
| **Floor Height** | 10.656' floor-to-floor | 9.0' floor-to-floor |
| **Level Spacing** | 5.328' half-levels | 9.0' full floors |
| **Ramp Slope** | 5% | 6.67% (IBC max) |
| **Floor Area** | 50% at half-levels | 100% all floors |
| **Level Names** | Grade, P1, P1.5, P2... | Grade, P1, P2, P3... |
| **Center Elements** | 12" walls + curbs | 36"×6" barriers only |
| **Center Columns** | 32"×24" every 31' | None (barriers only) |
| **Height (same capacity)** | Higher (+15%) | Lower |
| **Cost (same capacity)** | Higher (+15-20%) | Lower |

### Center Element Architecture

**Split-Level Double-Ramp:**
- **12" solid concrete core walls** - full height, full length
  - Separate ascending/descending ramp bays
  - Structural support + lateral stability
  - Fire separation between bays
- **8" × 12" curbs** (wheel stops) - both sides of walls
  - Ramp sections only (not turn zones)
  - Protect wall from vehicle impact
  - 2 curbs per center line per level
- **32" × 24" center columns** - support wall loads at 31' spacing

**Single-Ramp Full-Floor:**
- **36" × 6" ramp barriers** - full height
  - Both edges of ramp bay
  - No center walls, curbs, or columns
  - 70% cost reduction vs split-level center elements

### Stall Count Methodology

**Split-Level (Zone Attribution):**
Each half-level receives:
1. One turn zone (alternating north/south)
2. One ramp bay (alternating west/east) + perimeter row
3. Half of center core parking (split between adjacent half-levels)

**Single-Ramp (Full Floor Attribution):**
Each full floor receives:
1. Both turn zones (north + south)
2. All flat bays (full-length parking)
3. Ramp bay (~28 stalls on slope)

This spatial modeling automatically handles:
- Entry level blockages (27' opening on west side)
- Top level blockages (ramp termination)
- Multi-bay scaling
- Corner core blockages (elevator, stairs, utility, storage)

## Cost Calculation

All costs use **discrete component takeoffs** from TechRidge 1.2 SD Budget (May 2025).

### Foundation

- **Slab on Grade**: 5" thick × footprint
- **Vapor Barrier**: Under entire slab
- **Under-Slab Gravel**: 4" compacted
- **Spread Footings**: ACI 318-19 design under each column
- **Continuous Footings**: Elevator shaft, stairs, utility, storage
- **Equipment Loads**: Elevator machinery, stair pans, HVAC equipment

### Structure (Above Grade)

**Split-Level System:**
- **Slabs**: 8" PT suspended (discrete area per level)
- **Perimeter Columns**: 18"×24" on 31' × 31' grid
- **Center Columns**: 32"×24" supporting core walls (ramp sections)
- **Core Walls**: 12" solid concrete (full height, full length)
- **Curbs**: 8" × 12" wheel stops (both sides, ramp sections only)
- **Rebar**: 110 lbs/CY footings, 1320 lbs/CY columns, 3.0 lbs/SF slabs, 4.0 lbs/SF walls
- **Post-Tensioning**: 1.25 lbs/SF suspended slab area
- **Concrete Pumping**: $18/CY

**Single-Ramp System:**
- **Slabs**: 8" PT suspended (100% footprint per floor)
- **Perimeter Columns**: 18"×24" on 31' × 31' grid
- **Ramp Barriers**: 36" × 6" concrete (full height, both edges)
- **NO center columns, core walls, or curbs** (70% savings on center elements)
- **Rebar**: Same rates as split-level (barriers use 4.0 lbs/SF)
- **Post-Tensioning**: 1.25 lbs/SF suspended slab area
- **Concrete Pumping**: $18/CY

### Structure (Below Grade)

- **Excavation**: Footprint × depth + 3.5' over-excavation
- **Export/Haul-Off**: All excavated material removed
- **Structural Fill**: 1.5' to level building pad
- **Retaining Walls**: 12" perimeter walls with cantilever footings
- **Waterproofing**: Applied to wall exterior
- **Drainage**: Under-slab system

### MEP, Exterior, Finishes

- **MEP Systems**: `total_gsf` × $7/SF
- **Exterior Screen**: Perimeter × height × $82/SF
- **Sealed Concrete**: `total_gsf` × cost/SF
- **Pavement Markings**: $55 per stall
- **Elevators**: $32,500 per stop
- **Stairs**: $10,400 per flight

**Critical:** MEP/finishes use `garage.total_gsf` (sum of all discrete level areas), NOT `footprint × levels`. This accounts for split-level half-levels being ~50% of footprint.

### General Conditions & Soft Costs

- **General Conditions**: 9.37% of hard costs OR duration × $191,008/month
- **CM Fee**: 4.39% of (hard costs + GC)
- **Insurance**: 1.21% of (hard costs + GC)
- **Contingency**: 4.12% of (hard costs + GC) [CM 2.47% + Design 1.65%]

## File Structure

```
test version 2/
├── app.py                          # Streamlit UI (5-tab interface)
├── visualize_parking_layout.py     # 2D floor plans (matplotlib)
├── requirements.txt                # Dependencies
├── README.md                       # This file
├── IMPLEMENTATION.md               # Development log (Phases 1-7 complete)
├── test_phase6_costs.py            # Cost engine integration tests
├── test_phase6_smoke.py            # Quick validation tests
├── test_phase6_final.py            # Comprehensive Phase 6 tests
├── test_app_integration.py         # App compatibility tests
├── test_discrete_levels.py         # Level area validation
├── test_discrete_levels_visual.py  # Visual verification
├── test_bay_scaling.py             # Multi-bay efficiency
├── test_footing_validation.py      # Structural footing tests
├── test_footing_solver.py          # Footing algorithm tests
├── data/
│   ├── cost_database.json          # Unit costs from PDF budget
│   └── parking_schedule.json       # Baseline parking reference
└── src/
    ├── __init__.py
    ├── garage.py                   # Parametric geometry engine
    ├── cost_engine.py              # Cost calculations
    ├── footing_calculator.py       # ACI 318-19 structural design
    ├── visualization.py            # 3D models (Plotly)
    └── geometry/
        ├── __init__.py
        ├── design_modes.py         # Ramp system types & configs
        └── level_calculator.py     # Discrete level areas
```

## Technical Details

### Structural Quantities

- **Perimeter columns**: 18" × 24" on 31' × 31' grid
- **Center columns**: 32" × 24" on 31' spacing (split-level only, ramp sections)
- **Core walls**: 12" thick concrete (split-level only, full height/length)
- **Ramp barriers**: 36" × 6" concrete (single-ramp only, full height)
- **Slabs**: 8" PT suspended, 5" SOG
- **Post-tensioning**: ~1.25 lbs cables per SF
- **Rebar**: 110-1320 lbs/CY (varies by component)

### Footing Design (ACI 318-19)

- **Spread footings**: Square under columns (punching shear, one-way shear, flexure checks)
- **Continuous footings**: Elevator (40 LF), stairs (74 LF each), utility (86 LF), storage (102 LF)
- **Equipment loads**: Elevator machinery, stair pans, HVAC/electrical
- **Specialized live loads**: Stairs 100 PSF, storage 125 PSF (not 50 PSF parking)
- **Equivalent full floors**: Used for split-level loads (total_gsf / footprint)
- **Retaining wall footings**: Cantilever with overturning/sliding checks

### Excavation

- Mass excavation: Footprint × depth below grade
- Over-excavation: +3.5' for foundation work
- Export: All material hauled off
- Structural fill: 1.5' to level pad

## Testing

```bash
# Verify discrete level area calculations
python test_discrete_levels.py

# Visual verification (generates charts)
python test_discrete_levels_visual.py

# Test multi-bay efficiency scaling
python test_bay_scaling.py

# Validate structural footing design
python test_footing_validation.py

# Test footing calculator algorithm
python test_footing_solver.py

# Validate cost engine integration (Phase 6)
python test_phase6_costs.py
python test_phase6_smoke.py
python test_phase6_final.py

# Verify app compatibility
python test_app_integration.py
```

## 2D Floor Plan Visualization

The 2D visualization system (`visualize_parking_layout.py`) generates stall-by-stall layout diagrams:

### Overview Mode (All Levels)

Combines all levels showing:
- **Color-coded zones**: North turn (blue), west row (green), center rows (yellow/orange), east row (cyan), south turn (red)
- **Stall counts**: Total stalls per zone
- **Core blockages**: Red hatched areas (elevator, stairs, utility, storage)
- **Excess space**: Dimensions shown if length not optimal (not 31' multiple)
- **Optimization tips**: Recommends length adjustments for better efficiency

### Individual Level Mode

Shows single-level detail:
- **Stall-by-stall layout**: Each parking space numbered
- **Zone breakdown**: Which zones belong to this level
- **Attribution**: Turn zone, ramp bay, center percentage
- **Entry blockages**: 27' opening on west side (Grade level only)
- **Top blockages**: Ramp termination at north end (top level only)

### Usage in App

In the **📋 2D Plans** tab:
1. Select mode: "Overview (All Levels)" or specific level
2. View generated diagram with metrics
3. See optimization recommendations
4. Use for design communication and presentations

## Architecture

This application supports **two architectural patterns**:

### 1. Legacy Flow (Default)

All-in-one cost calculations via `CostCalculator`. Used by app.py.

```python
from src.garage import SplitLevelParkingGarage, load_cost_database
from src.cost_engine import CostCalculator

garage = SplitLevelParkingGarage(210, 8, 0, 2)
calculator = CostCalculator(load_cost_database())
costs = calculator.calculate_all_costs(garage)
```

### 2. New Architecture (Recommended for Extensions)

Separated quantity takeoff + cost abstraction. Type-safe, validated.

```python
from src.garage import SplitLevelParkingGarage, load_cost_database
from src.cost_registry import CostRegistry

garage = SplitLevelParkingGarage(210, 8, 0, 2)
quantities = garage.calculate_quantities()  # Structured data
quantities.validate()  # Built-in checks

registry = CostRegistry(load_cost_database())  # Semantic cost names
cost = quantities.foundation.sog_area_sf * registry.get('sog_5in').value
```

**Benefits:** Separated concerns, validation, type safety, future-proof against database changes

**See:** [ARCHITECTURE.md](ARCHITECTURE.md) | [FIXES_SUMMARY.md](FIXES_SUMMARY.md)

---

## Implementation Status

### Phase 1-7: Dual Ramp System - COMPLETE ✅

1. **Design Mode Infrastructure**: RampSystemType enum, auto-detection at 250'
2. **Core Geometry**: System-dependent heights, backward compatibility
3. **Discrete Level Areas**: 50% vs 100% footprint calculations
4. **Stall Calculations**: Zone attribution vs full floor attribution
5. **Structural Elements**: 12" walls + curbs vs 36" barriers
6. **Cost Engine Integration**: System-specific cost dispatch logic
7. **UI Integration**: Ramp system indicator, metrics, warnings

All tests passing. App fully functional with both ramp systems.

### Phase 8: Architecture Refactoring & Bug Fixes - COMPLETE ✅

**Date:** November 7, 2024

**Fixed:** Data structure mismatch + cost database reorganization (32 fixes total)

**Created:**
- `src/quantities.py` - QuantityTakeoff dataclass
- `src/cost_registry.py` - Cost abstraction layer
- `garage.calculate_quantities()` method

Both architectures working simultaneously. See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Known Limitations

1. **3D visualization**: Single-ramp barriers not yet rendered in 3D model (shows warning)
2. **Footings not in 3D**: Foundation elements below grade not visualized (fully costed)
3. **Rebar not visualized**: Reinforcement patterns not shown
4. **PT cables not shown**: Post-tensioning system not visualized
5. **MEP not modeled**: Mechanical/electrical/plumbing not in 3D

## Future Enhancements

- [ ] Add single-ramp barriers to 3D visualization
- [ ] Scenario save/load functionality
- [ ] Export reports to PDF
- [ ] Sensitivity analysis tools
- [ ] ROI calculator (with parking revenue)
- [ ] Multi-configuration comparison charts
- [ ] Wind/seismic lateral load analysis
- [ ] Podium slab upgrade for residential above
- [ ] Add footings/rebar/PT to 3D model (optional layers)

## Contact

TechRidge Development Team
