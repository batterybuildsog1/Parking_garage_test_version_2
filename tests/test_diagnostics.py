import json
from pathlib import Path

from src.pipeline import run_scenario
from src.cost_engine import load_cost_database


def test_min_diagnostics_schema_smoke():
    cost_db = load_cost_database(Path(__file__).resolve().parents[2] / "data" / "cost_database.json")
    inputs = {
        "length": 210,
        "half_levels_above": 10,
        "half_levels_below": 0,
        "num_bays": 2,
        "dead_load_psf": 115.0,
        "live_load_psf": 50.0,
        "allow_ll_reduction": True,
    }
    result = run_scenario(inputs=inputs, cost_database=cost_db, gc_params={"method": "percentage", "value": 9.37})
    diag = result.diagnostics["geometry"]

    # Basic keys exist
    assert "components" in diag
    assert "imposed_load_check" in diag

    comps = diag["components"]
    assert "columns" in comps and "floors" in comps and "retaining_walls" in comps and "rebar" in comps

    # Columns
    assert isinstance(comps["columns"].get("total_count", 0), (int, float))

    # Rebar totals computed from SF and rates
    rebar = comps["rebar"]
    sog_sf = float(rebar.get("sog_sf", 0.0))
    susp_sf = float(rebar.get("suspended_slab_sf", 0.0))
    sog_rate = float(rebar.get("sog_rebar_rate_lbs_per_sf", 0.0))
    susp_rate = float(rebar.get("suspended_rebar_rate_lbs_per_sf", 0.0))
    assert abs(rebar.get("sog_rebar_lbs", 0.0) - sog_sf * sog_rate) < 1e-6
    assert abs(rebar.get("suspended_slab_rebar_lbs", 0.0) - susp_sf * susp_rate) < 1e-6

    # Load reconciliation has pass flags and tolerance
    il = diag["imposed_load_check"]
    assert "tolerance_pct" in il
    assert "passes" in il and "all" in il["passes"]


