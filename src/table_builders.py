"""
Helpers to populate the normalized data tables from geometry and structural
calculations.
"""

from __future__ import annotations

from typing import Dict

from .data_tables import DataTables


def populate_geometry_tables(store: DataTables, project_id: str, garage) -> Dict[str, str]:
    """
    Insert high-level geometry, level, and structural quantities into the tables.

    Returns a dictionary mapping descriptive keys to element IDs for downstream
    cost attribution.
    """
    element_ids: Dict[str, str] = {}

    building_id = store.add_element(
        project_id,
        "building",
        name="parking_garage",
        metadata={
            "length_ft": garage.length,
            "width_ft": garage.width,
            "num_bays": garage.num_bays,
            "half_levels_above": garage.half_levels_above,
            "half_levels_below": garage.half_levels_below,
            "ramp_system": getattr(garage.ramp_system, "name", str(garage.ramp_system)),
        },
    )
    element_ids["building"] = building_id
    store.add_quantity(
        project_id,
        building_id,
        "footprint_area",
        garage.footprint_sf,
        "SF",
        source_pass="geometry",
    )
    store.add_quantity(
        project_id,
        building_id,
        "total_gsf",
        garage.total_gsf,
        "SF",
        source_pass="geometry",
    )
    store.add_quantity(
        project_id,
        building_id,
        "total_stalls",
        garage.total_stalls,
        "EA",
        source_pass="geometry",
    )

    # Levels
    for index, (level_name, gsf, slab_type, elevation) in enumerate(garage.levels):
        level_element_id = store.add_element(
            project_id,
            "level",
            name=level_name,
            level_index=index,
            parent_element_id=building_id,
            metadata={
                "elevation_ft": elevation,
                "slab_type": slab_type,
                "is_entry": index == garage.entry_level_index,
                "is_top": index == garage.total_levels - 1,
                "is_below_grade": index < garage.half_levels_below,
            },
        )
        element_ids[f"level:{level_name}"] = level_element_id
        store.add_quantity(
            project_id,
            level_element_id,
            "gross_floor_area",
            gsf,
            "SF",
            source_pass="geometry",
        )
        stalls = garage.stalls_by_level.get(level_name, {}).get("stalls", 0)
        store.add_quantity(
            project_id,
            level_element_id,
            "stall_count",
            stalls,
            "EA",
            source_pass="geometry",
        )

    # Foundation aggregates
    foundation_element = store.add_element(
        project_id,
        "foundation_system",
        metadata={
            "sog_thickness_in": 5.0,
            "has_retaining_walls": garage.half_levels_below > 0,
        },
    )
    element_ids["foundation"] = foundation_element
    store.add_quantity(
        project_id,
        foundation_element,
        "sog_area",
        garage.sog_levels_sf,
        "SF",
        source_pass="geometry",
    )
    store.add_quantity(
        project_id,
        foundation_element,
        "spread_footing_concrete",
        garage.spread_footing_concrete_cy,
        "CY",
        source_pass="structure",
    )
    store.add_quantity(
        project_id,
        foundation_element,
        "continuous_footing_concrete",
        garage.continuous_footing_concrete_cy,
        "CY",
        source_pass="structure",
    )
    store.add_quantity(
        project_id,
        foundation_element,
        "retaining_wall_footing_concrete",
        getattr(garage, "retaining_wall_footing_concrete_cy", 0.0),
        "CY",
        source_pass="structure",
    )

    # Structural summary
    structure_element = store.add_element(
        project_id,
        "structural_system",
        metadata={
            "primary_bay_spacing_ft": garage.PRIMARY_BAY_SPACING,
            "column_size_in": (18, 24),
            "total_height_ft": garage.total_height_ft,
        },
    )
    element_ids["structure"] = structure_element
    store.add_quantity(
        project_id,
        structure_element,
        "suspended_slab_area",
        garage.suspended_levels_sf,
        "SF",
        source_pass="structure",
    )
    store.add_quantity(
        project_id,
        structure_element,
        "column_concrete",
        garage.concrete_columns_cy,
        "CY",
        source_pass="structure",
    )
    store.add_quantity(
        project_id,
        structure_element,
        "total_rebar",
        garage.total_rebar_lbs,
        "LB",
        source_pass="structure",
    )
    store.add_quantity(
        project_id,
        structure_element,
        "post_tension_cables",
        garage.post_tension_lbs,
        "LB",
        source_pass="structure",
    )

    # Per-column elements (authoritative list)
    columns = getattr(garage, 'columns', [])
    col_el_ids = []
    for idx, col in enumerate(columns):
        col_el = store.add_element(
            project_id,
            "column",
            name=f"column_{idx+1}",
            parent_element_id=structure_element,
            metadata={
                "x_ft": float(col['x']),
                "y_ft": float(col['y']),
                "y_line_type": col.get('y_line_type'),
                "width_in": col.get('width_in'),
                "depth_in": col.get('depth_in')
            },
        )
        col_el_ids.append(col_el)
        # Column height and cross-section
        store.add_quantity(
            project_id,
            col_el,
            "column_height",
            garage.total_height_ft,
            "FT",
            source_pass="structure",
        )
        cross_section_sf = (col.get('width_in', 0.0) / 12.0) * (col.get('depth_in', 0.0) / 12.0)
        store.add_quantity(
            project_id,
            col_el,
            "column_cross_section",
            cross_section_sf,
            "SF",
            source_pass="structure",
        )
        # Column concrete per element (volume = area × height)
        store.add_quantity(
            project_id,
            col_el,
            "column_concrete",
            (cross_section_sf * garage.total_height_ft) / 27.0,
            "CY",
            source_pass="structure",
        )

    # Persist tributary rectangles and loads if available
    tribs = getattr(garage, 'column_tributary', [])
    loads = getattr(garage, 'column_loads', [])
    for idx, col_el in enumerate(col_el_ids):
        if idx < len(tribs):
            t = tribs[idx]
            store.add_quantity(project_id, col_el, "tributary_x_left", t.get('x_left', 0.0), "FT", source_pass="loads")
            store.add_quantity(project_id, col_el, "tributary_x_right", t.get('x_right', 0.0), "FT", source_pass="loads")
            store.add_quantity(project_id, col_el, "tributary_y_bottom", t.get('y_bottom', 0.0), "FT", source_pass="loads")
            store.add_quantity(project_id, col_el, "tributary_y_top", t.get('y_top', 0.0), "FT", source_pass="loads")
            store.add_quantity(project_id, col_el, "tributary_area", t.get('area_sf', 0.0), "SF", source_pass="loads")
        if idx < len(loads):
            l = loads[idx]
            store.add_quantity(project_id, col_el, "dl_slab_total", l.get('dl_slab_total', 0.0), "LB", source_pass="loads")
            store.add_quantity(project_id, col_el, "ll_slab_total", l.get('ll_slab_total', 0.0), "LB", source_pass="loads")
            store.add_quantity(project_id, col_el, "column_self_weight", l.get('column_self_weight', 0.0), "LB", source_pass="loads")
            store.add_quantity(project_id, col_el, "service_load", l.get('service_load', 0.0), "LB", source_pass="loads")
            store.add_quantity(project_id, col_el, "factored_load", l.get('factored_load', 0.0), "LB", source_pass="loads")

    # Per-footing elements (spread footings under columns)
    spread_footings = getattr(garage, 'spread_footings_by_type', {})
    for ftype, flist in spread_footings.items():
        for fidx, f in enumerate(flist):
            ft_el = store.add_element(
                project_id,
                "footing",
                name=f"{f.get('designation', ftype)}_{fidx+1}",
                parent_element_id=foundation_element,
                metadata={
                    "designation": f.get('designation'),
                    "x_ft": f.get('x'),
                    "y_ft": f.get('y'),
                    "width_ft": f.get('width_ft'),
                    "depth_ft": f.get('depth_ft', f.get('outer_thickness_ft')),
                    "two_depth": f.get('two_depth', False)
                },
            )
            store.add_quantity(
                project_id,
                ft_el,
                "footing_concrete",
                f.get('concrete_cy', 0.0),
                "CY",
                source_pass="structure",
            )
            store.add_quantity(
                project_id,
                ft_el,
                "footing_rebar",
                f.get('rebar_lbs', 0.0),
                "LB",
                source_pass="structure",
            )
            store.add_quantity(
                project_id,
                ft_el,
                "footing_excavation",
                f.get('excavation_cy', 0.0),
                "CY",
                source_pass="structure",
            )

    # Exterior
    exterior_element = store.add_element(
        project_id,
        "exterior_enclosure",
        metadata={"perimeter_lf": garage.perimeter_lf},
    )
    element_ids["exterior"] = exterior_element
    store.add_quantity(
        project_id,
        exterior_element,
        "parking_screen_area",
        garage.exterior_wall_sf,
        "SF",
        source_pass="geometry",
    )

    # Persist per-level column areas/loads and diagnostics (if available)
    per_col_levels = getattr(garage, 'per_level_column_data', [])
    if per_col_levels:
        for col_idx, col_el in enumerate(col_el_ids):
            levels = per_col_levels[col_idx] if col_idx < len(per_col_levels) else []
            for entry in levels:
                li = entry.get('level_index')
                lname = entry.get('level_name', '')
                area = entry.get('area_sf', 0.0)
                dl = entry.get('dl_lb', 0.0)
                ll = entry.get('ll_lb', 0.0)
                svc = entry.get('service_lb', 0.0)
                fact = entry.get('factored_lb', 0.0)
                util = entry.get('punch_utilization', None)
                sr_req = entry.get('stud_rails_required', None)
                # Area
                store.add_quantity(project_id, col_el, "level_area", area, "SF", source_pass="per_level", notes=f"level={li}:{lname}")
                # Loads
                store.add_quantity(project_id, col_el, "dl_level", dl, "LB", source_pass="per_level", notes=f"level={li}:{lname}")
                store.add_quantity(project_id, col_el, "ll_level", ll, "LB", source_pass="per_level", notes=f"level={li}:{lname}")
                store.add_quantity(project_id, col_el, "service_level", svc, "LB", source_pass="per_level", notes=f"level={li}:{lname}")
                store.add_quantity(project_id, col_el, "factored_level", fact, "LB", source_pass="per_level", notes=f"level={li}:{lname}")
                # Punching
                if util is not None:
                    store.add_quantity(project_id, col_el, "punching_utilization", util, "FACTOR", source_pass="per_level", notes=f"level={li}:{lname}")
                if sr_req is not None:
                    store.add_quantity(project_id, col_el, "stud_rails_required", 1 if sr_req else 0, "EA", source_pass="per_level", notes=f"level={li}:{lname}")
            # Floors supported (from any entry)
            if levels:
                fs = levels[0].get('floors_supported', 0)
                store.add_quantity(project_id, col_el, "floors_supported", fs, "EA", source_pass="per_level")

    # Validation diagnostics for per-level area conservation
    lvl_val = getattr(garage, 'per_level_area_validation', [])
    for v in lvl_val:
        variance = abs(v.get('variance_pct', 0.0))
        level_str = "info" if variance < 2.0 else ("warning" if variance < 5.0 else "error")
        store.add_diagnostic(
            project_id,
            scope="per_level_area_check",
            level=level_str,
            message=f"Level {v.get('level_index')} {v.get('level_name')}: columns sum={v.get('computed_area_sum'):,.1f} SF, expected GSF={v.get('expected_gsf'):,.1f} SF, variance={v.get('variance_pct'):.2f}%",
            detail=v
        )

    return element_ids

