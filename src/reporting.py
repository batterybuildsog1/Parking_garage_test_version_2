"""
Reporting utilities for presenting cost/quantity data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd


TR_CATEGORY_NAMES = [
    "Foundation",
    "Excavation & Below-Grade",
    "Structure",
    "Exterior Closure",
    "Mechanical/Electrical",
    "Site Work",
    "Conveying",
    "General Conditions",
]


def _map_row_to_tr_category(row: pd.Series) -> str:
    """
    Map our cost_items row to TechRidge top-level category for apples-to-apples reporting.
    Policy is applied here without mutating the underlying ledger.
    """
    base = (row.get("category") or "").lower()
    desc = (row.get("description") or "").lower()
    unit_key = (row.get("unit_cost_key") or "").lower()

    # Base mapping
    base_map = {
        "foundation": "Foundation",
        "excavation": "Excavation & Below-Grade",
        "structure": "Structure",
        "exterior": "Exterior Closure",
        "mep": "Mechanical/Electrical",
        "site": "Site Work",
        "vertical_transportation": "Conveying",
        "soft_costs": "General Conditions",
    }
    mapped = base_map.get(base, "Structure")

    # Policy-based rebucketing
    # Retaining wall (concrete/dampproofing) belongs to Below-Grade for TR comparison
    if "retaining wall" in desc or "retaining_wall" in unit_key:
        return "Excavation & Below-Grade"

    # Concrete pumping is a structural operation (keep in Structure)
    if "pumping" in desc or "pumping" in unit_key:
        return "Structure"

    # Overhead door typically lives in Site Work in TR budgets
    if "overhead door" in desc or "overhead_door" in unit_key:
        return "Site Work"

    # Elevator-related entries are Conveying
    if "elevator" in desc or "elevator" in unit_key:
        return "Conveying"

    # Stud rails, rebar, PT cables → Structure
    if any(t in desc for t in ["stud rail", "rebar", "post-tension"]):
        return "Structure"

    return mapped


def build_tr_aligned_breakdown(cost_items_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Produce a TR-aligned category breakdown of our ledger:
    - Adds a 'tr_category' column according to policy mapping
    - Computes totals per TR category
    - Returns a normalized rows list for easy UI rendering
    """
    if cost_items_df.empty:
        return {"rows": [], "totals_by_tr": {name: 0.0 for name in TR_CATEGORY_NAMES}}

    df = cost_items_df.copy()
    df["tr_category"] = df.apply(_map_row_to_tr_category, axis=1)

    # Normalized rows (keep high-signal columns)
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "tr_category": r["tr_category"],
            "our_category": r.get("category"),
            "element_id": r.get("element_id"),
            "description": r.get("description"),
            "measure": r.get("measure"),
            "unit": r.get("unit"),
            "quantity": float(r.get("quantity", 0.0)),
            "unit_cost": float(r.get("unit_cost", 0.0)),
            "total": float(r.get("total_cost", 0.0)),
            "source_pass": r.get("source_pass"),
        })

    # Totals by TR category in canonical order
    totals_series = df.groupby("tr_category")["total_cost"].sum()
    totals_by_tr = {name: float(totals_series.get(name, 0.0)) for name in TR_CATEGORY_NAMES}

    return {"rows": rows, "totals_by_tr": totals_by_tr}


def _build_section(items_df: pd.DataFrame) -> Dict[str, Any]:
    if items_df.empty:
        return {"total": 0.0, "items": []}
    records = []
    total = 0.0
    for _, row in items_df.iterrows():
        records.append(
            {
                "component": row["description"],
                "quantity": row["quantity"],
                "unit": row["unit"],
                "unit_cost": row["unit_cost"],
                "total": row["total_cost"],
                "notes": row.get("notes", ""),
            }
        )
        total += row["total_cost"]
    return {"total": total, "items": records}


def build_detailed_takeoffs(cost_items_df: pd.DataFrame, garage) -> Dict[str, Any]:
    if cost_items_df.empty:
        return {
            "01_foundation": _build_section(cost_items_df),
            "02_excavation": _build_section(cost_items_df),
            "03_concrete": _build_section(cost_items_df),
            "04_reinforcement": _build_section(cost_items_df),
            "05_walls_cores": _build_section(cost_items_df),
            "06_vertical": _build_section(cost_items_df),
            "07_mep": _build_section(cost_items_df),
            "08_exterior": _build_section(cost_items_df),
            "09_level_summary": {
                "total_gsf": garage.total_gsf,
                "total_stalls": garage.total_stalls,
                "levels": [],
            },
        }

    def filter_items(predicate):
        return cost_items_df[cost_items_df.apply(predicate, axis=1)]

    detailed = {
        "01_foundation": _build_section(cost_items_df[cost_items_df["category"] == "foundation"]),
        "02_excavation": _build_section(cost_items_df[cost_items_df["category"] == "excavation"]),
        "03_concrete": _build_section(
            filter_items(
                lambda r: r["category"] == "structure"
                and any(token in r["description"].lower() for token in ("slab", "column"))
            )
        ),
        "04_reinforcement": _build_section(
            filter_items(
                lambda r: r["category"] == "structure"
                and any(token in r["description"].lower() for token in ("rebar", "post-tension"))
            )
        ),
        "05_walls_cores": _build_section(
            filter_items(
                lambda r: r["category"] == "structure"
                and any(token in r["description"].lower() for token in ("wall", "core"))
            )
        ),
        "06_vertical": _build_section(cost_items_df[cost_items_df["category"] == "vertical_transportation"]),
        "07_mep": _build_section(cost_items_df[cost_items_df["category"] == "mep"]),
        "08_exterior": _build_section(
            cost_items_df[cost_items_df["category"].isin(["exterior", "site"])]
        ),
    }

    level_records = []
    for level_name, gsf, slab_type, elevation in garage.levels:
        level_records.append(
            {
                "level_name": level_name,
                "elevation_ft": elevation,
                "gsf": gsf,
                "stalls": garage.stalls_by_level.get(level_name, {}).get("stalls", 0),
                "level_size": "half" if slab_type == "half_level" else "full",
                "level_type": "below_grade" if elevation < 0 else "above_grade",
                "slab_type": slab_type,
            }
        )

    detailed["09_level_summary"] = {
        "total_gsf": garage.total_gsf,
        "total_stalls": garage.total_stalls,
        "levels": level_records,
    }
    return detailed


def build_min_diagnostics(garage, cost_db: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal, float-based diagnostics for quick verification in the app.
    - Component counts and per-level breakdowns (columns, floors, retaining walls)
    - Rebar totals for footings and slabs (SOG + suspended) using cost DB rates
    - Imposed load reconciliation (modeled vs expected, slab-only on levels)
    """
    # Columns
    columns = getattr(garage, "columns", []) or []
    columns_total = len(columns)
    # Per-level column counts based on per-level column areas
    per_level_column_data: List[List[Dict[str, Any]]] = getattr(garage, "per_level_column_data", [])
    level_defs: List[Tuple[str, float, str, float]] = list(getattr(garage, "levels", []))
    columns_per_level: List[Dict[str, Any]] = []
    if level_defs and per_level_column_data:
        num_levels = len(level_defs)
        counts = [0 for _ in range(num_levels)]
        for col_levels in per_level_column_data:
            for e in col_levels:
                li = int(e.get("level_index", -1))
                if 0 <= li < num_levels and float(e.get("area_sf", 0.0)) > 0.0:
                    counts[li] += 1
        for i, (name, _, _, _) in enumerate(level_defs):
            columns_per_level.append({"level_name": name, "count": counts[i]})

    # Floors (levels) summary
    floors_total = getattr(garage, "total_levels", len(level_defs))
    levels_summary: List[Dict[str, Any]] = []
    total_gsf = float(getattr(garage, "total_gsf", 0.0))
    for (level_name, gsf, slab_type, elevation) in level_defs:
        levels_summary.append({
            "level_name": level_name,
            "gsf": float(gsf),
            "slab_type": slab_type,
            "elevation_ft": float(elevation),
        })

    # Retaining walls: sqft per below-grade level (perimeter × level_height per level)
    # Keep simple and deterministic; do not attempt segmenting by side.
    perimeter_lf = float(getattr(garage, "perimeter_lf", 2.0 * (getattr(garage, "length", 0.0) + getattr(garage, "width", 0.0))))
    level_height_ft = float(getattr(garage, "level_height", getattr(garage, "floor_to_floor", 10.0) / 2.0))
    retaining_by_level: List[Dict[str, Any]] = []
    retaining_total_sf = 0.0
    for (level_name, _, _, elevation) in level_defs:
        if float(elevation) < 0.0:
            area_sf = perimeter_lf * level_height_ft
            retaining_by_level.append({"level_name": level_name, "area_sf": area_sf})
            retaining_total_sf += area_sf
    # Also expose the aggregate tracked elsewhere (if any)
    retaining_wall_sf = float(getattr(garage, "retaining_wall_sf", retaining_total_sf))

    # Rebar totals from footings (if available)
    # Slab rebar (temporary default): use cost DB lbs/SF until detailed calculator exists
    comp = (cost_db or {}).get("component_specific_costs", {})
    unit_struct = (cost_db or {}).get("unit_costs", {}).get("structure", {})
    # Defaults if missing in DB
    sog_lbs_per_sf = float(comp.get("rebar_sog_lbs_per_sf", unit_struct.get("rebar_slab_lbs", 1.1)))
    suspended_lbs_per_sf = float(comp.get("rebar_pt_slab_lbs_per_sf", unit_struct.get("rebar_slab_lbs", 1.25)))
    sog_sf = float(getattr(garage, "sog_levels_sf", 0.0))
    suspended_sf = float(getattr(garage, "suspended_levels_sf", 0.0))
    sog_rebar_lbs = sog_sf * sog_lbs_per_sf
    suspended_rebar_lbs = suspended_sf * suspended_lbs_per_sf

    rebar_totals = {
        "total_footing_rebar_lbs": float(getattr(garage, "total_footing_rebar_lbs", 0.0)),
        "spread_footing_rebar_lbs": float(getattr(garage, "spread_footing_rebar_lbs", 0.0)),
        "continuous_footing_rebar_lbs": float(getattr(garage, "continuous_footing_rebar_lbs", 0.0)),
        "retaining_wall_footing_rebar_lbs": float(getattr(garage, "retaining_wall_footing_rebar_lbs", 0.0)),
        # Slabs
        "sog_sf": sog_sf,
        "suspended_slab_sf": suspended_sf,
        "sog_rebar_rate_lbs_per_sf": sog_lbs_per_sf,
        "suspended_rebar_rate_lbs_per_sf": suspended_lbs_per_sf,
        "sog_rebar_lbs": sog_rebar_lbs,
        "suspended_slab_rebar_lbs": suspended_rebar_lbs,
        "total_slabs_rebar_lbs": sog_rebar_lbs + suspended_rebar_lbs,
        "total_rebar_lbs_all": float(getattr(garage, "total_footing_rebar_lbs", 0.0)) + sog_rebar_lbs + suspended_rebar_lbs,
    }

    # Imposed load reconciliation
    # Modeled (sum of per-level column loads; slab-only at level granularity)
    modeled_dl_lb_total = 0.0
    modeled_ll_lb_total = 0.0
    for col_levels in per_level_column_data:
        for e in col_levels:
            modeled_dl_lb_total += float(e.get("dl_lb", 0.0))
            modeled_ll_lb_total += float(e.get("ll_lb", 0.0))

    # Expected (deterministic building totals)
    dead_load_psf = float(getattr(garage, "dead_load_psf", 0.0))
    live_load_psf = float(getattr(garage, "live_load_psf", 0.0))
    allow_ll_reduction = bool(getattr(garage, "allow_ll_reduction", True))
    # DL expected on all levels
    expected_dl_lb_total = total_gsf * dead_load_psf
    # LL expected on suspended levels only; optional floors-supported reduction (approx)
    suspended_gsf = sum(float(gsf) for (_, gsf, slab_type, _) in level_defs if slab_type == "suspended")
    suspended_levels_count = sum(1 for (_, _, slab_type, _) in level_defs if slab_type == "suspended")
    ll_factor = 0.8 if (allow_ll_reduction and suspended_levels_count >= 2) else 1.0
    expected_ll_lb_total = suspended_gsf * live_load_psf * ll_factor

    def _delta_pct(modeled: float, expected: float) -> float:
        if expected <= 0.0:
            return 0.0
        return ((modeled / expected) - 1.0) * 100.0

    # Pass/fail tolerance (percent of expected totals)
    tolerance_pct = 3.0
    delta_dl = _delta_pct(modeled_dl_lb_total, expected_dl_lb_total)
    delta_ll = _delta_pct(modeled_ll_lb_total, expected_ll_lb_total)
    delta_total = _delta_pct(
        modeled_dl_lb_total + modeled_ll_lb_total,
        expected_dl_lb_total + expected_ll_lb_total,
    )
    imposed_load_check = {
        "modeled": {
            "dl_lb_total": modeled_dl_lb_total,
            "ll_lb_total": modeled_ll_lb_total,
            "total_lb": modeled_dl_lb_total + modeled_ll_lb_total,
        },
        "expected": {
            "dl_lb_total": expected_dl_lb_total,
            "ll_lb_total": expected_ll_lb_total,
            "total_lb": expected_dl_lb_total + expected_ll_lb_total,
        },
        "deltas_pct": {
            "dl": delta_dl,
            "ll": delta_ll,
            "total": delta_total,
        },
        "tolerance_pct": tolerance_pct,
        "passes": {
            "dl": abs(delta_dl) <= tolerance_pct,
            "ll": abs(delta_ll) <= tolerance_pct,
            "total": abs(delta_total) <= tolerance_pct,
        }
    }
    imposed_load_check["passes"]["all"] = all(imposed_load_check["passes"].values())

    return {
        "components": {
            "columns": {
                "total_count": columns_total,
                "per_level": columns_per_level,
            },
            "floors": {
                "total_levels": floors_total,
                "levels": levels_summary,
            },
            "cores": {
                "num_stairs": int(getattr(garage, "num_stairs", 0)),
                "num_stair_flights": int(getattr(garage, "num_stair_flights", 0)),
                "num_elevator_stops": int(getattr(garage, "num_elevator_stops", 0)),
            },
            "retaining_walls": {
                "perimeter_lf": perimeter_lf,
                "area_sf_by_level": retaining_by_level,
                "total_area_sf": retaining_total_sf,
                "tracked_total_area_sf": retaining_wall_sf,
            },
            "rebar": rebar_totals,
        },
        "imposed_load_check": imposed_load_check,
    }

def build_tr_comparison(costs: Dict[str, float], cost_db: Dict[str, Any], garage) -> Dict[str, Any]:
    baseline = cost_db.get("system_costs_from_budget", {})
    baseline_total = baseline.get("total", 12_272_200)

    # Our buckets remapped to TechRidge top-level categories
    our_buckets = {
        "Foundation": float(costs.get("foundation", 0.0)),
        # TR lumps below-grade premiums (retaining walls, dampproofing, etc.) here; we keep a separate "excavation" bucket
        "Excavation & Below-Grade": float(costs.get("excavation", 0.0)) + float(costs.get("retaining_walls", 0.0)),
        # TR "superstructure_parking" includes concrete, rebar, PT, pumping, core walls, accessories
        "Structure": float(costs.get("structure_above", 0.0))
        + float(costs.get("structure_below", 0.0))
        + float(costs.get("rebar", 0.0))
        + float(costs.get("post_tensioning", 0.0))
        + float(costs.get("concrete_pumping", 0.0))
        + float(costs.get("core_walls", 0.0))
        + float(costs.get("structural_accessories", 0.0))
        + float(costs.get("ramp_system", 0.0)),
        "Exterior Closure": float(costs.get("exterior", 0.0)),
        "Mechanical/Electrical": float(costs.get("mep", 0.0)),
        # TR site work typically includes doors, OWS, drains; our engine classifies some of these under 'exterior'/'site'
        "Site Work": float(costs.get("site_finishes", 0.0)),
        "Conveying": float(costs.get("elevators", 0.0)),
        "General Conditions": float(costs.get("general_conditions", 0.0)),
    }

    # Baseline buckets from TechRidge PDF extract
    baseline_buckets = {
        "Foundation": float(baseline.get("foundation_total", 0.0)),
        # PDF didn't provide an explicit excavation subtotal; treat as missing (N/A) unless provided
        "Excavation & Below-Grade": float(baseline.get("excavation_total", 0.0)),
        "Structure": float(baseline.get("superstructure_parking", 0.0)),
        "Exterior Closure": float(baseline.get("exterior_closure_parking", 0.0)),
        # Fix: use 'mep_parking' instead of mechanical+electrical which aren't present in system_costs_from_budget
        "Mechanical/Electrical": float(baseline.get("mep_parking", 0.0)),
        "Site Work": float(baseline.get("site_work_parking", 0.0)),
        "Conveying": float(baseline.get("conveying_parking", 0.0)),
        "General Conditions": float(baseline.get("general_conditions_parking", 0.0)),
    }

    # Totals and unit KPIs (from overall)
    totals = {
        "our_total": float(costs.get("total", 0.0)),
        "tr_total": baseline_total,
        "variance": float(costs.get("total", 0.0)) - baseline_total,
        "variance_pct": ((float(costs.get("total", 0.0)) / baseline_total) - 1) * 100 if baseline_total else 0.0,
    }
    unit_costs = {
        "our_cost_per_sf": float(costs.get("cost_per_sf", 0.0)),
        "tr_cost_per_sf": baseline_total / float(garage.total_gsf) if getattr(garage, "total_gsf", 0.0) else 0.0,
        "our_cost_per_stall": float(costs.get("cost_per_stall", 0.0)),
        "tr_cost_per_stall": baseline_total / float(garage.total_stalls) if getattr(garage, "total_stalls", 0) else 0.0,
    }
    geometry = {
        "our_gsf": float(getattr(garage, "total_gsf", 0.0)),
        "our_stalls": int(getattr(garage, "total_stalls", 0)),
        "tr_gsf": float(baseline.get("parking_gsf", 0.0)),
        "tr_stalls": int(baseline.get("parking_stalls", 0)),
    }

    # Category breakdown with improved status and notes
    categories = []
    for cat in [
        "Foundation",
        "Excavation & Below-Grade",
        "Structure",
        "Exterior Closure",
        "Mechanical/Electrical",
        "Site Work",
        "Conveying",
        "General Conditions",
    ]:
        our_val = our_buckets.get(cat, 0.0)
        tr_val = baseline_buckets.get(cat, 0.0)
        variance = our_val - tr_val
        if tr_val == 0.0:
            variance_pct = None
            status = "N/A"
            note = "No baseline value provided in TechRidge extract"
        else:
            variance_pct = (variance / tr_val * 100.0)
            if abs(variance_pct) <= 10:
                status = "✓"
            elif abs(variance_pct) <= 20:
                status = "⚠️"
            else:
                status = "❌"
            note = ""
        categories.append(
            {
                "category": cat,
                "tr_cost": tr_val,
                "our_cost": our_val,
                "variance": variance,
                "variance_pct": variance_pct if variance_pct is not None else 0.0,
                "status": status,
                "notes": note,
            }
        )

    return {
        "totals": totals,
        "unit_costs": unit_costs,
        "geometry": geometry,
        "categories": categories,
    }

