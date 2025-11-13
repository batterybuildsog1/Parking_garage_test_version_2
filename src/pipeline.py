"""
End-to-end scenario pipeline:

1. Normalize inputs and create a project record.
2. Run geometry/structural calculations via SplitLevelParkingGarage.
3. Populate normalized tables (elements, quantities).
4. Execute cost engine to append cost items.
5. Run validation checks and return summary metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .data_tables import DataTables
from .garage import create_parking_garage
from .table_builders import populate_geometry_tables
from .reporting import build_min_diagnostics


@dataclass
class ScenarioResult:
    project_id: str
    store: DataTables
    garage: Any
    cost_summary: Dict[str, float]
    diagnostics: Dict[str, Any]

    def table(self, name: str):
        return self.store.fetch_dataframe(name)


def run_scenario(
    *,
    inputs: Dict[str, Any],
    cost_database: Dict[str, Any],
    gc_params: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> ScenarioResult:
    """
    Execute the full calculation pipeline and return a ScenarioResult.
    """
    store = DataTables(db_path=db_path)
    project_record = store.create_project(inputs)

    # Geometry + structural calculations
    garage = create_parking_garage(
        length=inputs["length"],
        half_levels_above=inputs["half_levels_above"],
        half_levels_below=inputs["half_levels_below"],
        num_bays=inputs["num_bays"],
        ramp_system=inputs.get("ramp_system"),
        soil_bearing_capacity=inputs.get("soil_bearing_capacity", 3500),
        allow_ll_reduction=inputs.get("allow_ll_reduction", True),
        dead_load_psf=inputs.get("dead_load_psf", 115.0),
        live_load_psf=inputs.get("live_load_psf", 50.0),
    )

    element_ids = populate_geometry_tables(store, project_record.project_id, garage)

    # Cost engine (new table-driven implementation)
    from .cost_engine import CostEngine

    engine = CostEngine(cost_database, store, project_record.project_id, element_ids)
    cost_summary = engine.calculate(garage, gc_params or {"method": "percentage", "value": 9.37})

    # Minimal geometry/loads diagnostics for application verification
    geometry_diagnostics = build_min_diagnostics(garage, cost_database)
    diagnostics = {
        "geometry": geometry_diagnostics,
        "cost": engine.diagnostics,
    }

    return ScenarioResult(
        project_id=project_record.project_id,
        store=store,
        garage=garage,
        cost_summary=cost_summary,
        diagnostics=diagnostics,
    )

