# System Overview

This document captures the entire parking garage analyzer in one place. It is written from a data-first perspective, in line with Casey Muratori’s guidance: *let the data be the system, keep code immediate, and surface invariants explicitly.*

## Guiding Principles

- **Data tables are the source of truth.** Geometry, quantities, and costs live in SQLite tables; every other representation (UI, audits, docs) is a projection.
- **Immediate-mode execution.** Scripts create scenarios, read tables, and exit. No hidden state or cached deltas.
- **Explicit invariants.** Each pipeline pass records diagnostics so inconsistencies surface immediately.
- **Small surface area.** Engineers land on this document plus `README.md` and `docs/OPERATIONS.md`.

## Pipeline

```
Inputs → Geometry (SplitLevelParkingGarage) → DataTables → CostEngine → ScenarioResult
```

| Layer | Purpose | Key Artifacts |
|-------|---------|---------------|
| Inputs | Scenario parameters and soil assumptions | Streamlit sidebar, CLI scripts |
| Geometry | Computes discrete levels, stalls, structural elements, footings | `src/garage.py`, `src/geometry/*` |
| DataTables | Normalized ledger of projects, elements, quantities, costs, diagnostics | `src/data_tables.py` |
| CostEngine | Adds unit costs, writes cost lines, records diagnostics | `src/cost_engine.py` |
| ScenarioResult | Facade exposing tables + summary metrics | `src/pipeline.py` |

Diagnostics live beside the tables (`diagnostics` table + `ScenarioResult.diagnostics`). Streamlit and CLI tools show them without re-computing anything.

## Components (One Layer Each)

- **Geometry Core (`src/garage.py`)**  
  Split-level and single-ramp systems share the same façade. Helpers in `src/geometry/` compute areas, stall counts, and tributary loads.

- **Ledger Builder (`src/table_builders.py`)**  
  Converts the geometry object into `elements` and `quantities`. Returns stable IDs so costing remains decoupled.

- **Ledger Store (`src/data_tables.py`)**  
  Thin wrapper around SQLite with insert helpers and DataFrame accessors (`get_cost_items_df`, `get_quantities_df`, etc.).

- **Cost Engine (`src/cost_engine.py`)**  
  Normalises unit costs, writes priced line items with `_add_cost_line`, and collects warnings/errors.

- **Pipeline (`src/pipeline.py`)**  
  `run_scenario()` orchestrates the full pass and returns a `ScenarioResult` containing the geometry object, summary metrics, DataFrames, and diagnostics.

- **Reporting Helpers (`src/reporting.py`)**  
  Immediate-mode transformations for the UI and CLI tools (detailed takeoffs, TechRidge comparisons). Nothing stores state.

- **Streamlit UI (`app.py`)**  
  Builds the scenario through `run_scenario()` and visualises the resulting ledger.

## Implementation History (Condensed)

| Phase | Focus | Highlights |
|-------|-------|------------|
| 1–7 (2024) | Single-ramp system | Added design modes, full-floor geometry, cost dispatching, UI exposure. |
| 8 (2025) | Table-driven architecture | Introduced `DataTables`, rewrote cost engine, removed `CostCalculator` & `QuantityTakeoff`. |
| 9A (2025) | Legacy cleanup | Consolidated docs/scripts, migrated audits to `run_scenario`, added reporting helpers. |
| Upcoming | Regression + diagnostics | Snapshot tests, invariant suite, diagnostic surfacing in UI. |

## Roadmap

1. **Phase 9B – Regression Tests**  
   - Golden snapshots for `cost_items` / `quantities`.  
   - Hypothesis sweeps for range/efficiency invariants.  
   - Pipeline smoke tests exercising both ramp systems.

2. **Phase 10 – Diagnostics & Validation**  
   - Enforce ledger invariants (no negative quantities, stall efficiency bounds).  
   - Diagnostics tab in Streamlit built from `diagnostics`.  
   - Scenario diff tool for comparing ledger snapshots.

3. **Phase 11 – External Persistence (Optional)**  
   - Swap SQLite for Neon/Postgres through `DataTables(db_path=...)`.  
   - Harden migrations + seed scripts.

## Invariants & Checks

- **Quantities** must be strictly positive except for explicitly flagged placeholders.
- **Cost Items** must reference a valid quantity ID; `_add_cost_line` enforces this.
- **Totals** in `cost_summary` must equal sums of the ledger (checked in tests).
- **Stall efficiency** (`total_gsf / total_stalls`) stays within design bounds; future diagnostics will enforce this automatically.

## Current Authoritative Geometry Rules (2025-11)

- **Width formula unchanged**: 1' exterior walls and 2' center spacing (two 6" barriers with a 1' gap). Do not switch to 6" exterior walls or 3' cores.
- **Center elements**: No center walls or curbs. Use center columns on a 31' grid (ramp section only) and two 6" ramp-edge barriers with a 1' clear gap. Show the gap on plan sets.
- **Entry**: Entry happens at grade. On the lowest level, the west-side aisle is flat; after the first turn, ramping begins. Apply a 27' west opening as a stall reduction on the entry (grade) level.
- **SOG classification**: SOG is the bottom-most footprint of the building:
  - Split-level: the lowest two half-levels are SOG (100% footprint, including ramps). All higher half-levels are suspended.
  - Single-ramp: floor 1 is SOG; higher floors are suspended.
- **Ramp termination (split-level only)**: Default 40' (user-editable). Affects the top-most level only; reduces top-level plan length from the north.
- **Single-ramp termination**: No top-level reduction is applied in current model; will be considered in the single-ramp rewrite.

## Related References

- Cost database mapping: `data/cost_database.json`, `data/reference_budget_map.json`.
- TechRidge baseline PDFs: `TechRidge 1.2 SD Budget 2025-5-8.pdf`, `TECH RIDGE FOUNDATION COORDINATION (1).pdf`.
- CLI tools and usage examples: see `docs/OPERATIONS.md`.


