"""
Table-driven cost engine.

Calculates cost components and records every quantity + cost line in the
normalized data tables.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .data_tables import DataTables


class CostEngine:
    def __init__(
        self,
        cost_database: Dict[str, Any],
        store: DataTables,
        project_id: str,
        element_ids: Dict[str, str],
    ):
        self.cost_database = cost_database
        self.store = store
        self.project_id = project_id
        self.element_ids = dict(element_ids)

        self.store.ensure_unit_costs(cost_database)

        self.costs = cost_database["unit_costs"]
        self.component_costs = cost_database["component_specific_costs"]
        self.soft_costs_pct = cost_database["soft_costs_percentages"]
        self.diagnostics: Dict[str, Any] = {"warnings": [], "errors": []}

        # Root element for uncategorized items
        self._ensure_element("cost_summary", "cost_summary")

    # ------------------------------------------------------------------ public
    def calculate(self, garage, gc_params: Dict[str, Any]) -> Dict[str, float]:
        summary: Dict[str, float] = {}

        summary["foundation"] = self._foundation_costs(garage)
        summary["excavation"] = self._excavation_costs(garage)
        summary["ramp_system"] = 0.0
        summary["structure_above"] = self._structure_concrete_costs(garage)
        summary["structure_below"] = 0.0
        summary["concrete_pumping"] = self._concrete_pumping(garage)
        summary["rebar"] = self._rebar_costs(garage)
        summary["post_tensioning"] = self._post_tensioning_costs(garage)
        summary["core_walls"] = self._core_wall_costs(garage)
        summary["retaining_walls"] = self._retaining_wall_costs(garage)
        summary["elevators"] = self._elevator_costs(garage)
        summary["stairs"] = self._stair_costs(garage)
        summary["structural_accessories"] = self._structural_accessories(garage)
        summary["mep"] = self._mep_costs(garage)
        summary["vdc_coordination"] = self._vdc_costs(garage)
        summary["exterior"] = self._exterior_costs(garage)
        summary["interior_finishes"] = 0.0
        summary["special_systems"] = 0.0
        summary["site_finishes"] = self._site_finishes_costs(garage)

        hard_cost_keys = [
            key
            for key in summary
            if key
            not in {
                "general_conditions",
                "cm_fee",
                "insurance",
                "contingency",
                "soft_cost_subtotal",
                "total",
                "cost_per_stall",
                "cost_per_sf",
                "hard_cost_subtotal",
            }
        ]
        hard_cost_total = sum(summary[key] for key in hard_cost_keys)
        summary["hard_cost_subtotal"] = hard_cost_total

        summary["general_conditions"] = self._general_conditions(hard_cost_total, gc_params)

        soft_base = hard_cost_total + summary["general_conditions"]
        summary["cm_fee"] = soft_base * self.soft_costs_pct["cm_fee"]
        summary["insurance"] = soft_base * self.soft_costs_pct["insurance"]
        summary["contingency"] = soft_base * (
            self.soft_costs_pct["contingency_cm"] + self.soft_costs_pct["contingency_design"]
        )

        summary["soft_cost_subtotal"] = (
            summary["general_conditions"]
            + summary["cm_fee"]
            + summary["insurance"]
            + summary["contingency"]
        )
        summary["total"] = hard_cost_total + summary["soft_cost_subtotal"]
        summary["cost_per_stall"] = summary["total"] / garage.total_stalls
        summary["cost_per_sf"] = summary["total"] / garage.total_gsf

        self._record_soft_costs(summary, garage)
        self._validate_cost_summary(summary)

        return summary

    # ---------------------------------------------------------------- utilities
    def _ensure_element(
        self,
        key: str,
        element_type: str,
        *,
        name: Optional[str] = None,
        parent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if key in self.element_ids:
            return self.element_ids[key]
        parent_id = self.element_ids.get(parent) if parent else None
        element_id = self.store.add_element(
            self.project_id,
            element_type,
            name=name or key,
            parent_element_id=parent_id,
            metadata=metadata or {},
        )
        self.element_ids[key] = element_id
        return element_id

    def _add_cost_line(
        self,
        *,
        element_key: str,
        element_type: str,
        parent: Optional[str],
        measure: str,
        quantity: float,
        unit: str,
        unit_cost_key: str,
        unit_cost_value: float,
        category: str,
        description: str,
        source_pass: str,
        notes: Optional[str] = None,
    ) -> float:
        if quantity <= 0:
            return 0.0

        element_id = self._ensure_element(element_key, element_type, parent=parent)
        quantity_id = self.store.add_quantity(
            self.project_id,
            element_id,
            measure,
            quantity,
            unit,
            source_pass=source_pass,
            notes=notes,
        )
        self.store.add_cost_item(
            self.project_id,
            quantity_id=quantity_id,
            element_id=element_id,
            unit_cost_key=unit_cost_key,
            category=category,
            description=description,
            unit=unit,
            quantity=quantity,
            unit_cost=unit_cost_value,
            source_pass=source_pass,
            notes=notes,
        )
        return unit_cost_value * quantity

    def _lookup(self, *path: str) -> float:
        node = self.cost_database
        for part in path:
            if part not in node:
                raise KeyError(f"Cost path {'/'.join(path)} not found")
            node = node[part]
        if isinstance(node, dict):
            raise ValueError(f"Cost path {'/'.join(path)} is not numeric")
        return float(node)

    def _warn(self, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        self.diagnostics["warnings"].append({"message": message, "detail": detail or {}})

    # ------------------------------------------------------------- cost helpers
    def _foundation_costs(self, garage) -> float:
        total = 0.0
        foundation_key = "foundation"
        self._ensure_element(foundation_key, "foundation_system")

        sog_area = garage.sog_levels_sf
        total += self._add_cost_line(
            element_key=f"{foundation_key}:sog",
            element_type="foundation_component",
            parent=foundation_key,
            measure="slab_on_grade_area",
            quantity=sog_area,
            unit="SF",
            unit_cost_key="structure.slab_on_grade_5in_sf",
            unit_cost_value=self.costs["structure"]["slab_on_grade_5in_sf"],
            category="foundation",
            description="Slab on Grade (5 in)",
            source_pass="foundation",
            notes="Concrete + placement",
        )

        total += self._add_cost_line(
            element_key=f"{foundation_key}:vapor_barrier",
            element_type="foundation_component",
            parent=foundation_key,
            measure="vapor_barrier_area",
            quantity=sog_area,
            unit="SF",
            unit_cost_key="structure.vapor_barrier_sf",
            unit_cost_value=self.costs["structure"]["vapor_barrier_sf"],
            category="foundation",
            description="Under-slab Vapor Barrier",
            source_pass="foundation",
        )

        total += self._add_cost_line(
            element_key=f"{foundation_key}:under_slab_gravel",
            element_type="foundation_component",
            parent=foundation_key,
            measure="under_slab_gravel_area",
            quantity=sog_area,
            unit="SF",
            unit_cost_key="structure.under_slab_gravel_sf",
            unit_cost_value=self.costs["structure"]["under_slab_gravel_sf"],
            category="foundation",
            description="Under-slab Gravel (4 in)",
            source_pass="foundation",
        )

        total += self._add_cost_line(
            element_key=f"{foundation_key}:subdrain",
            element_type="foundation_component",
            parent=foundation_key,
            measure="subdrain_area",
            quantity=garage.footprint_sf,
            unit="SF",
            unit_cost_key="foundation.subdrain_system_sf",
            unit_cost_value=self.costs["foundation"]["subdrain_system_sf"],
            category="foundation",
            description="Subdrain System",
            source_pass="foundation",
        )

        if garage.half_levels_below > 0:
            perimeter = 2 * (garage.width + garage.length)
            total += self._add_cost_line(
                element_key=f"{foundation_key}:footing_drain",
                element_type="foundation_component",
                parent=foundation_key,
                measure="footing_drain_length",
                quantity=perimeter,
                unit="LF",
                unit_cost_key="foundation.footing_drain_lf",
                unit_cost_value=self.costs["foundation"]["footing_drain_lf"],
                category="foundation",
                description="Footing Drain",
                source_pass="foundation",
            )

        total += self._add_cost_line(
            element_key=f"{foundation_key}:spread_footings_concrete",
            element_type="foundation_component",
            parent=foundation_key,
            measure="spread_footing_concrete",
            quantity=garage.spread_footing_concrete_cy,
            unit="CY",
            unit_cost_key="foundation.footings_spot_cy",
            unit_cost_value=self.costs["foundation"]["footings_spot_cy"],
            category="foundation",
            description="Spread Footing Concrete",
            source_pass="foundation",
        )
        total += self._add_cost_line(
            element_key=f"{foundation_key}:spread_footings_rebar",
            element_type="foundation_component",
            parent=foundation_key,
            measure="spread_footing_rebar",
            quantity=garage.spread_footing_rebar_lbs,
            unit="LB",
            unit_cost_key="foundation.rebar_footings_lbs",
            unit_cost_value=self.costs["foundation"]["rebar_footings_lbs"],
            category="foundation",
            description="Spread Footing Rebar",
            source_pass="foundation",
        )
        total += self._add_cost_line(
            element_key=f"{foundation_key}:spread_footings_excavation",
            element_type="foundation_component",
            parent=foundation_key,
            measure="spread_footing_excavation",
            quantity=garage.spread_footing_excavation_cy,
            unit="CY",
            unit_cost_key="foundation.excavation_footings_cy",
            unit_cost_value=self.costs["foundation"]["excavation_footings_cy"],
            category="foundation",
            description="Spread Footing Excavation",
            source_pass="foundation",
        )

        total += self._add_cost_line(
            element_key=f"{foundation_key}:continuous_footings_concrete",
            element_type="foundation_component",
            parent=foundation_key,
            measure="continuous_footing_concrete",
            quantity=garage.continuous_footing_concrete_cy,
            unit="CY",
            unit_cost_key="foundation.footings_continuous_cy",
            unit_cost_value=self.costs["foundation"]["footings_continuous_cy"],
            category="foundation",
            description="Continuous Footing Concrete",
            source_pass="foundation",
        )
        total += self._add_cost_line(
            element_key=f"{foundation_key}:continuous_footings_rebar",
            element_type="foundation_component",
            parent=foundation_key,
            measure="continuous_footing_rebar",
            quantity=garage.continuous_footing_rebar_lbs,
            unit="LB",
            unit_cost_key="foundation.rebar_footings_lbs",
            unit_cost_value=self.costs["foundation"]["rebar_footings_lbs"],
            category="foundation",
            description="Continuous Footing Rebar",
            source_pass="foundation",
        )
        total += self._add_cost_line(
            element_key=f"{foundation_key}:continuous_footings_excavation",
            element_type="foundation_component",
            parent=foundation_key,
            measure="continuous_footing_excavation",
            quantity=garage.continuous_footing_excavation_cy,
            unit="CY",
            unit_cost_key="foundation.excavation_footings_cy",
            unit_cost_value=self.costs["foundation"]["excavation_footings_cy"],
            category="foundation",
            description="Continuous Footing Excavation",
            source_pass="foundation",
        )

        total += self._add_cost_line(
            element_key=f"{foundation_key}:retaining_footings_concrete",
            element_type="foundation_component",
            parent=foundation_key,
            measure="retaining_footing_concrete",
            quantity=getattr(garage, "retaining_wall_footing_concrete_cy", 0.0),
            unit="CY",
            unit_cost_key="foundation.footings_continuous_cy",
            unit_cost_value=self.costs["foundation"]["footings_continuous_cy"],
            category="foundation",
            description="Retaining Wall Footing Concrete",
            source_pass="foundation",
        )
        total += self._add_cost_line(
            element_key=f"{foundation_key}:retaining_footings_rebar",
            element_type="foundation_component",
            parent=foundation_key,
            measure="retaining_footing_rebar",
            quantity=getattr(garage, "retaining_wall_footing_rebar_lbs", 0.0),
            unit="LB",
            unit_cost_key="foundation.rebar_footings_lbs",
            unit_cost_value=self.costs["foundation"]["rebar_footings_lbs"],
            category="foundation",
            description="Retaining Wall Footing Rebar",
            source_pass="foundation",
        )
        total += self._add_cost_line(
            element_key=f"{foundation_key}:retaining_footings_excavation",
            element_type="foundation_component",
            parent=foundation_key,
            measure="retaining_footing_excavation",
            quantity=getattr(garage, "retaining_wall_footing_excavation_cy", 0.0),
            unit="CY",
            unit_cost_key="foundation.excavation_footings_cy",
            unit_cost_value=self.costs["foundation"]["excavation_footings_cy"],
            category="foundation",
            description="Retaining Wall Footing Excavation",
            source_pass="foundation",
        )

        if hasattr(garage, "backfill_foundation_cy"):
            total += self._add_cost_line(
                element_key=f"{foundation_key}:backfill_foundation",
                element_type="foundation_component",
                parent=foundation_key,
                measure="backfill_foundation",
                quantity=garage.backfill_foundation_cy,
                unit="CY",
                unit_cost_key="foundation.backfill_cy",
                unit_cost_value=self.costs["foundation"]["backfill_cy"],
                category="foundation",
                description="Foundation Backfill",
                source_pass="foundation",
            )

        if hasattr(garage, "backfill_ramp_cy"):
            total += self._add_cost_line(
                element_key=f"{foundation_key}:backfill_ramp",
                element_type="foundation_component",
                parent=foundation_key,
                measure="backfill_ramp",
                quantity=garage.backfill_ramp_cy,
                unit="CY",
                unit_cost_key="foundation.backfill_cy",
                unit_cost_value=self.costs["foundation"]["backfill_cy"],
                category="foundation",
                description="Ramp Backfill",
                source_pass="foundation",
            )

        return total

    def _excavation_costs(self, garage) -> float:
        if garage.half_levels_below == 0:
            return 0.0

        total = 0.0
        excavation_key = "excavation"
        self._ensure_element(excavation_key, "excavation_scope")

        total += self._add_cost_line(
            element_key=f"{excavation_key}:mass_excavation",
            element_type="excavation_component",
            parent=excavation_key,
            measure="mass_excavation",
            quantity=garage.excavation_cy,
            unit="CY",
            unit_cost_key="below_grade_premiums.mass_excavation_3_5ft_cy",
            unit_cost_value=self.costs["below_grade_premiums"]["mass_excavation_3_5ft_cy"],
            category="excavation",
            description="Mass Excavation",
            source_pass="excavation",
        )
        total += self._add_cost_line(
            element_key=f"{excavation_key}:export",
            element_type="excavation_component",
            parent=excavation_key,
            measure="export_volume",
            quantity=garage.export_cy,
            unit="CY",
            unit_cost_key="foundation.export_excess_cy",
            unit_cost_value=self.costs["foundation"]["export_excess_cy"],
            category="excavation",
            description="Export / Haul-off",
            source_pass="excavation",
        )
        total += self._add_cost_line(
            element_key=f"{excavation_key}:structural_fill",
            element_type="excavation_component",
            parent=excavation_key,
            measure="structural_fill",
            quantity=garage.structural_fill_cy,
            unit="CY",
            unit_cost_key="below_grade_premiums.import_structural_fill_cy",
            unit_cost_value=self.costs["below_grade_premiums"]["import_structural_fill_cy"],
            category="excavation",
            description="Structural Fill Import",
            source_pass="excavation",
        )
        total += self._add_cost_line(
            element_key=f"{excavation_key}:retaining_walls",
            element_type="excavation_component",
            parent=excavation_key,
            measure="retaining_wall_area",
            quantity=garage.retaining_wall_sf,
            unit="SF",
            unit_cost_key="below_grade_premiums.retaining_wall_cw12_sf",
            unit_cost_value=self.costs["below_grade_premiums"]["retaining_wall_cw12_sf"],
            category="excavation",
            description="Retaining Wall Concrete (12 in)",
            source_pass="excavation",
        )
        total += self._add_cost_line(
            element_key=f"{excavation_key}:dampproofing",
            element_type="excavation_component",
            parent=excavation_key,
            measure="dampproofing_area",
            quantity=garage.retaining_wall_sf,
            unit="SF",
            unit_cost_key="foundation.dampproofing_sf",
            unit_cost_value=self.costs["foundation"]["dampproofing_sf"],
            category="excavation",
            description="Retaining Wall Dampproofing",
            source_pass="excavation",
        )
        total += self._add_cost_line(
            element_key=f"{excavation_key}:under_slab_drainage",
            element_type="excavation_component",
            parent=excavation_key,
            measure="under_slab_drainage_area",
            quantity=garage.footprint_sf,
            unit="SF",
            unit_cost_key="below_grade_premiums.under_slab_drainage_sf",
            unit_cost_value=self.costs["below_grade_premiums"]["under_slab_drainage_sf"],
            category="excavation",
            description="Under-slab Drainage Layer",
            source_pass="excavation",
        )
        if hasattr(garage, "elevator_pit_waterproofing_sf"):
            total += self._add_cost_line(
                element_key=f"{excavation_key}:elevator_pit_waterproofing",
                element_type="excavation_component",
                parent=excavation_key,
                measure="elevator_pit_waterproofing_area",
                quantity=garage.elevator_pit_waterproofing_sf,
                unit="SF",
                unit_cost_key="below_grade_premiums.waterproofing_elevator_pit_sf",
                unit_cost_value=self.costs["below_grade_premiums"]["waterproofing_elevator_pit_sf"],
                category="excavation",
                description="Elevator Pit Waterproofing",
                source_pass="excavation",
            )

        return total

    def _structure_concrete_costs(self, garage) -> float:
        total = 0.0
        structure_key = "structure"
        self._ensure_element(structure_key, "structural_system")

        total += self._add_cost_line(
            element_key=f"{structure_key}:suspended_slab",
            element_type="structural_component",
            parent=structure_key,
            measure="suspended_slab_area",
            quantity=garage.suspended_levels_sf,
            unit="SF",
            unit_cost_key="structure.suspended_slab_8in_sf",
            unit_cost_value=self.costs["structure"]["suspended_slab_8in_sf"],
            category="structure",
            description="Suspended PT Slabs (8 in)",
            source_pass="structure",
        )
        total += self._add_cost_line(
            element_key=f"{structure_key}:columns",
            element_type="structural_component",
            parent=structure_key,
            measure="column_concrete",
            quantity=garage.concrete_columns_cy,
            unit="CY",
            unit_cost_key="structure.columns_18x24_cy",
            unit_cost_value=self.costs["structure"]["columns_18x24_cy"],
            category="structure",
            description="Perimeter Columns (18x24)",
            source_pass="structure",
        )

        return total

    def _concrete_pumping(self, garage) -> float:
        return self._add_cost_line(
            element_key="structure:concrete_pumping",
            element_type="structural_component",
            parent="structure",
            measure="concrete_volume_for_pumping",
            quantity=garage.total_concrete_cy,
            unit="CY",
            unit_cost_key="structure.concrete_pumping_cy",
            unit_cost_value=self.costs["structure"]["concrete_pumping_cy"],
            category="structure",
            description="Concrete Pumping",
            source_pass="structure",
        )

    def _rebar_costs(self, garage) -> float:
        total = 0.0
        rebar_rate = self.component_costs["rebar_cost_per_lb"]

        total += self._add_cost_line(
            element_key="structure:rebar_slabs",
            element_type="structural_component",
            parent="structure",
            measure="slab_rebar_weight",
            quantity=garage.suspended_slab_sf
            * self.component_costs["rebar_pt_slab_lbs_per_sf"],
            unit="LB",
            unit_cost_key="component_specific_costs.rebar_cost_per_lb",
            unit_cost_value=rebar_rate,
            category="structure",
            description="Suspended Slab Rebar",
            source_pass="structure",
        )
        total += self._add_cost_line(
            element_key="structure:rebar_columns",
            element_type="structural_component",
            parent="structure",
            measure="column_rebar_weight",
            quantity=garage.concrete_columns_cy
            * self.component_costs["rebar_columns_lbs_per_cy_concrete"],
            unit="LB",
            unit_cost_key="component_specific_costs.rebar_cost_per_lb",
            unit_cost_value=rebar_rate,
            category="structure",
            description="Column Rebar",
            source_pass="structure",
        )
        return total

    def _post_tensioning_costs(self, garage) -> float:
        return self._add_cost_line(
            element_key="structure:post_tensioning",
            element_type="structural_component",
            parent="structure",
            measure="post_tension_weight",
            quantity=garage.post_tension_lbs,
            unit="LB",
            unit_cost_key="component_specific_costs.post_tension_cable_cost_per_lb",
            unit_cost_value=self.component_costs["post_tension_cable_cost_per_lb"],
            category="structure",
            description="Post-tension Cables",
            source_pass="structure",
        )

    def _core_wall_costs(self, garage) -> float:
        core_wall_sf = (
            getattr(garage, "center_core_wall_sf", 0.0)
            + garage.elevator_shaft_sf
            + garage.stair_enclosure_sf
            + garage.utility_closet_sf
            + garage.storage_closet_sf
        )
        if core_wall_sf == 0:
            return 0.0
        return self._add_cost_line(
            element_key="structure:core_walls",
            element_type="structural_component",
            parent="structure",
            measure="core_wall_area",
            quantity=core_wall_sf,
            unit="SF",
            unit_cost_key="component_specific_costs.core_wall_12in_cost_per_sf",
            unit_cost_value=self.component_costs["core_wall_12in_cost_per_sf"],
            category="structure",
            description="12 in Core Walls",
            source_pass="structure",
        )

    def _retaining_wall_costs(self, garage) -> float:
        retaining_sf = getattr(garage, "retaining_wall_sf", 0.0)
        if retaining_sf == 0:
            return 0.0
        return self._add_cost_line(
            element_key="structure:retaining_walls",
            element_type="structural_component",
            parent="structure",
            measure="retaining_wall_area",
            quantity=retaining_sf,
            unit="SF",
            unit_cost_key="below_grade_premiums.retaining_wall_cw12_sf",
            unit_cost_value=self.costs["below_grade_premiums"]["retaining_wall_cw12_sf"],
            category="structure",
            description="Retaining Wall Concrete",
            source_pass="structure",
        )

    def _elevator_costs(self, garage) -> float:
        return self._add_cost_line(
            element_key="vertical:elevator",
            element_type="vertical_transport_component",
            parent="cost_summary",
            measure="elevator_stops",
            quantity=garage.num_elevator_stops,
            unit="STOP",
            unit_cost_key="component_specific_costs.elevator_cost_per_stop",
            unit_cost_value=self.component_costs["elevator_cost_per_stop"],
            category="vertical_transportation",
            description="Elevator Stops",
            source_pass="vertical_transportation",
        )

    def _stair_costs(self, garage) -> float:
        total = 0.0
        total += self._add_cost_line(
            element_key="vertical:stair_flights",
            element_type="vertical_transport_component",
            parent="cost_summary",
            measure="stair_flights",
            quantity=garage.num_stair_flights,
            unit="FLIGHT",
            unit_cost_key="component_specific_costs.stair_flight_cost",
            unit_cost_value=self.component_costs["stair_flight_cost"],
            category="vertical_transportation",
            description="Stair Flights",
            source_pass="vertical_transportation",
        )
        total += self._add_cost_line(
            element_key="vertical:stair_railings",
            element_type="vertical_transport_component",
            parent="cost_summary",
            measure="stair_railings",
            quantity=garage.num_stair_flights,
            unit="FLIGHT",
            unit_cost_key="component_specific_costs.stair_railing_per_flight",
            unit_cost_value=self.component_costs["stair_railing_per_flight"],
            category="vertical_transportation",
            description="Stair Railings",
            source_pass="vertical_transportation",
        )
        return total

    def _structural_accessories(self, garage) -> float:
        # Use per-joint stud rails count if available; otherwise fall back to num_columns
        stud_count = getattr(garage, "stud_rail_required_joints", None)
        quantity = stud_count if isinstance(stud_count, (int, float)) and stud_count >= 0 else garage.num_columns
        return self._add_cost_line(
            element_key="structure:stud_rails",
            element_type="structural_component",
            parent="structure",
            measure="stud_rail_count",
            quantity=quantity,
            unit="EA",
            unit_cost_key="component_specific_costs.stud_rails_per_column",
            unit_cost_value=self.component_costs["stud_rails_per_column"],
            category="structure",
            description="Column Stud Rails",
            source_pass="structure",
        )

    def _mep_costs(self, garage) -> float:
        total = 0.0
        total += self._add_cost_line(
            element_key="mep:fire_protection",
            element_type="mep_component",
            parent="cost_summary",
            measure="fire_protection_area",
            quantity=garage.total_gsf,
            unit="SF",
            unit_cost_key="mep.fire_protection_parking_sf",
            unit_cost_value=self.costs["mep"]["fire_protection_parking_sf"],
            category="mep",
            description="Fire Protection",
            source_pass="mep",
        )
        total += self._add_cost_line(
            element_key="mep:plumbing",
            element_type="mep_component",
            parent="cost_summary",
            measure="plumbing_area",
            quantity=garage.total_gsf,
            unit="SF",
            unit_cost_key="mep.plumbing_parking_sf",
            unit_cost_value=self.costs["mep"]["plumbing_parking_sf"],
            category="mep",
            description="Plumbing",
            source_pass="mep",
        )
        total += self._add_cost_line(
            element_key="mep:hvac",
            element_type="mep_component",
            parent="cost_summary",
            measure="hvac_area",
            quantity=garage.total_gsf,
            unit="SF",
            unit_cost_key="mep.hvac_parking_sf",
            unit_cost_value=self.costs["mep"]["hvac_parking_sf"],
            category="mep",
            description="Mechanical Ventilation",
            source_pass="mep",
        )
        total += self._add_cost_line(
            element_key="mep:electrical",
            element_type="mep_component",
            parent="cost_summary",
            measure="electrical_area",
            quantity=garage.total_gsf,
            unit="SF",
            unit_cost_key="mep.electrical_parking_sf",
            unit_cost_value=self.costs["mep"]["electrical_parking_sf"],
            category="mep",
            description="Electrical Systems",
            source_pass="mep",
        )
        return total

    def _vdc_costs(self, garage) -> float:
        return self._add_cost_line(
            element_key="soft:vdc",
            element_type="soft_cost_component",
            parent="cost_summary",
            measure="vdc_area",
            quantity=garage.total_gsf,
            unit="SF",
            unit_cost_key="component_specific_costs.vdc_coordination_per_sf_building",
            unit_cost_value=self.component_costs["vdc_coordination_per_sf_building"],
            category="soft_costs",
            description="VDC Coordination",
            source_pass="soft_costs",
        )

    def _exterior_costs(self, garage) -> float:
        total = 0.0
        total += self._add_cost_line(
            element_key="exterior:screen",
            element_type="exterior_component",
            parent="cost_summary",
            measure="parking_screen_area",
            quantity=garage.exterior_wall_sf,
            unit="SF",
            unit_cost_key="exterior.parking_screen_sf",
            unit_cost_value=self.costs["exterior"]["parking_screen_sf"],
            category="exterior",
            description="Parking Screen",
            source_pass="exterior",
        )
        if hasattr(garage, "high_speed_overhead_door_ea"):
            total += self._add_cost_line(
                element_key="exterior:overhead_door",
                element_type="exterior_component",
                parent="cost_summary",
                measure="overhead_doors",
                quantity=garage.high_speed_overhead_door_ea,
                unit="EA",
                unit_cost_key="site.high_speed_overhead_door_ea",
                unit_cost_value=self.costs["site"]["high_speed_overhead_door_ea"],
                category="exterior",
                description="High-speed Overhead Door",
                source_pass="exterior",
            )
        return total

    def _site_finishes_costs(self, garage) -> float:
        total = 0.0
        total += self._add_cost_line(
            element_key="site:sealed_concrete",
            element_type="site_component",
            parent="cost_summary",
            measure="sealed_concrete_area",
            quantity=garage.total_gsf,
            unit="SF",
            unit_cost_key="site.sealed_concrete_parking_sf",
            unit_cost_value=self.costs["site"]["sealed_concrete_parking_sf"],
            category="site",
            description="Sealed Concrete",
            source_pass="site",
        )
        total += self._add_cost_line(
            element_key="site:pavement_markings",
            element_type="site_component",
            parent="cost_summary",
            measure="pavement_markings",
            quantity=garage.total_stalls,
            unit="EA",
            unit_cost_key="site.pavement_markings_per_stall",
            unit_cost_value=self.costs["site"]["pavement_markings_per_stall"],
            category="site",
            description="Pavement Markings",
            source_pass="site",
        )
        total += self._add_cost_line(
            element_key="site:final_cleaning",
            element_type="site_component",
            parent="cost_summary",
            measure="final_cleaning_area",
            quantity=garage.total_gsf,
            unit="SF",
            unit_cost_key="site.final_cleaning_parking_sf",
            unit_cost_value=self.costs["site"]["final_cleaning_parking_sf"],
            category="site",
            description="Final Cleaning",
            source_pass="site",
        )
        if hasattr(garage, "oil_water_separator_ea"):
            total += self._add_cost_line(
                element_key="site:oil_water_separator",
                element_type="site_component",
                parent="cost_summary",
                measure="oil_water_separator",
                quantity=garage.oil_water_separator_ea,
                unit="EA",
                unit_cost_key="site.oil_water_separator_ea",
                unit_cost_value=self.costs["site"]["oil_water_separator_ea"],
                category="site",
                description="Oil/Water Separator",
                source_pass="site",
            )
        if hasattr(garage, "storm_drain_48in_ads_ea"):
            total += self._add_cost_line(
                element_key="site:storm_drain_ads",
                element_type="site_component",
                parent="cost_summary",
                measure="storm_drain_ads",
                quantity=garage.storm_drain_48in_ads_ea,
                unit="EA",
                unit_cost_key="site.storm_drain_48in_ads_ea",
                unit_cost_value=self.costs["site"]["storm_drain_48in_ads_ea"],
                category="site",
                description="Storm Drain (48in ADS)",
                source_pass="site",
            )
        return total

    def _general_conditions(self, hard_cost_total: float, gc_params: Dict[str, Any]) -> float:
        method = gc_params.get("method", "percentage")
        if method == "monthly_rate":
            months = float(gc_params.get("value", 5.0))
            rate = self.component_costs["general_conditions_per_month"]
            return self._add_cost_line(
                element_key="soft:general_conditions_monthly",
                element_type="soft_cost_component",
                parent="cost_summary",
                measure="general_conditions_months",
                quantity=months,
                unit="MONTH",
                unit_cost_key="component_specific_costs.general_conditions_per_month",
                unit_cost_value=rate,
                category="soft_costs",
                description="General Conditions (Monthly)",
                source_pass="soft_costs",
            )

        percentage = float(gc_params.get("value", self.component_costs["general_conditions_percentage"]))
        factor = percentage / 100.0 if percentage > 1 else percentage
        base = hard_cost_total
        return self._add_cost_line(
            element_key="soft:general_conditions_percentage",
            element_type="soft_cost_component",
            parent="cost_summary",
            measure="general_conditions_base",
            quantity=base,
            unit="USD",
            unit_cost_key="component_specific_costs.general_conditions_percentage",
            unit_cost_value=factor,
            category="soft_costs",
            description="General Conditions (% of Hard Costs)",
            source_pass="soft_costs",
        )

    def _record_soft_costs(self, summary: Dict[str, float], garage) -> None:
        base = summary["hard_cost_subtotal"] + summary["general_conditions"]

        self._add_cost_line(
            element_key="soft:cm_fee",
            element_type="soft_cost_component",
            parent="cost_summary",
            measure="cm_fee_base",
            quantity=base,
            unit="USD",
            unit_cost_key="soft_costs_percentages.cm_fee",
            unit_cost_value=self.soft_costs_pct["cm_fee"],
            category="soft_costs",
            description="Construction Management Fee",
            source_pass="soft_costs",
        )

        self._add_cost_line(
            element_key="soft:insurance",
            element_type="soft_cost_component",
            parent="cost_summary",
            measure="insurance_base",
            quantity=base,
            unit="USD",
            unit_cost_key="soft_costs_percentages.insurance",
            unit_cost_value=self.soft_costs_pct["insurance"],
            category="soft_costs",
            description="Builders Risk Insurance",
            source_pass="soft_costs",
        )

        contingency_pct = (
            self.soft_costs_pct["contingency_cm"] + self.soft_costs_pct["contingency_design"]
        )
        self._add_cost_line(
            element_key="soft:contingency",
            element_type="soft_cost_component",
            parent="cost_summary",
            measure="contingency_base",
            quantity=base,
            unit="USD",
            unit_cost_key="soft_costs_percentages.contingency_cm",
            unit_cost_value=contingency_pct,
            category="soft_costs",
            description="Construction + Design Contingency",
            source_pass="soft_costs",
        )

    def _validate_cost_summary(self, summary: Dict[str, float]) -> None:
        if summary["total"] <= 0:
            self._warn("Total cost calculated as non-positive value.", {"total": summary["total"]})


def load_cost_database(path: Optional[Path] = None) -> Dict[str, Any]:
    base = path or Path(__file__).resolve().parent.parent / "data" / "cost_database.json"
    with open(base, "r", encoding="utf-8") as fp:
        return json.load(fp)

