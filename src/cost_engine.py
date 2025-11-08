"""
Cost calculation engine for split-level parking garage

Applies unit costs from cost_database.json to parametric geometry calculations.

KEY PRINCIPLE: Component-by-Component Takeoffs
All costs calculated using discrete quantity takeoffs - no formula-based extrapolation:
- Foundation: SOG area from discrete levels × unit costs
- Structure: Concrete CY, rebar LBS, PT cables LBS from geometry engine
- MEP & Finishes: Uses garage.total_gsf (sum of discrete level GSF)
- Vertical circulation: Elevator stops, stair flights from geometry
- Below-grade: Excavation CY, retaining walls SF, waterproofing

IMPORTANT: Uses discrete level GSF sum (garage.total_gsf), not footprint × levels
See DISCRETE_LEVELS_GUIDE.md for floor area calculation methodology.
"""

import json
from pathlib import Path
from typing import Dict
from .garage import SplitLevelParkingGarage


class CostCalculator:
    """
    Calculate total construction cost based on garage geometry and unit costs

    Cost categories:
    - Foundation (one-time, scales with footprint)
    - Structure above grade (per floor)
    - Structure below grade (per floor, with premium)
    - Excavation (volume-based)
    - MEP systems (area-based)
    - Exterior (perimeter × height)
    - Ramp system (fixed cost)
    - Soft costs (percentage of hard costs)
    """

    def __init__(self, cost_database: Dict):
        """Initialize with cost database"""
        self.costs = cost_database['unit_costs']
        self.derived = cost_database['derived_unit_costs']
        self.component_costs = cost_database['component_specific_costs']
        self.soft_costs_pct = cost_database['soft_costs_percentages']

    def _get_wall_12in_cost_per_cy(self) -> float:
        """
        Calculate cost per CY for 12" concrete walls

        TEMPORARY PLACEHOLDER - TODO: Extract actual cost from TechRidge 1.2 SD Budget 2025-5-8.pdf

        Calculation: Formed structural concrete walls
        - We have $/SF cost: $28.50/SF from component_costs['core_wall_12in_cost_per_sf']
        - Convert to $/CY: For 12" (1 ft) thick wall, 1 SF = 1/27 CY
        - Therefore: $28.50/SF ÷ (1/27 CY/SF) = $769.50/CY

        But this is ALL-IN (concrete + forming + rebar), not just concrete
        For barriers/walls where we calculate rebar separately, use concrete + forming only
        """
        # Use about 60% of all-in cost (concrete + forming, excluding rebar calculated separately)
        core_wall_sf = self.component_costs['core_wall_12in_cost_per_sf']
        return (core_wall_sf / (1/27)) * 0.6  # ~$460/CY - placeholder

    def calculate_all_costs(self, garage: SplitLevelParkingGarage, gc_params: dict = None) -> Dict:
        """
        Calculate complete cost breakdown for garage

        Args:
            garage: SplitLevelParkingGarage instance with geometry
            gc_params: General Conditions calculation parameters (optional)
                      {"method": "percentage", "value": 9.37} - GC as % of hard costs (default)
                      {"method": "monthly_rate", "value": 5.0} - duration in months × monthly rate

        Returns dict with:
        - Individual cost categories
        - Subtotals
        - Total cost
        - Cost per stall
        - Cost per SF
        """
        costs = {}

        # === ONE-TIME COSTS ===
        costs['foundation'] = self._calculate_foundation(garage)
        costs['excavation'] = self._calculate_excavation(garage)
        costs['ramp_system'] = self.derived['ramp_system_fixed_cost']

        # === STRUCTURE COSTS ===
        costs['structure_above'] = self._calculate_structure_above(garage)
        costs['structure_below'] = self._calculate_structure_below(garage)

        # === GRANULAR STRUCTURE COMPONENTS ===
        costs['concrete_pumping'] = self._calculate_concrete_pumping(garage)
        costs['rebar'] = self._calculate_rebar_by_component(garage)
        costs['post_tensioning'] = self._calculate_post_tensioning(garage)
        costs['core_walls'] = self._calculate_core_walls(garage)
        costs['retaining_walls'] = self._calculate_retaining_walls(garage)

        # === VERTICAL TRANSPORTATION ===
        costs['elevators'] = self._calculate_elevators(garage)
        costs['stairs'] = self._calculate_stairs(garage)

        # === STRUCTURAL ACCESSORIES ===
        costs['structural_accessories'] = self._calculate_structural_accessories(garage)

        # === MEP SYSTEMS ===
        costs['mep'] = self._calculate_mep(garage)

        # === VDC COORDINATION ===
        costs['vdc_coordination'] = self._calculate_vdc_coordination(garage)

        # === EXTERIOR ===
        costs['exterior'] = self._calculate_exterior(garage)

        # === INTERIOR FINISHES ===
        costs['interior_finishes'] = self._calculate_interior_finishes(garage)

        # === SPECIAL SYSTEMS ===
        costs['special_systems'] = self._calculate_special_systems(garage)

        # === SITE/FINISHES ===
        costs['site_finishes'] = self._calculate_site_finishes(garage)

        # === HARD COST SUBTOTAL ===
        hard_cost_total = sum(costs.values())
        costs['hard_cost_subtotal'] = hard_cost_total

        # === GENERAL CONDITIONS ===
        costs['general_conditions'] = self._calculate_general_conditions(hard_cost_total, gc_params)

        # === SOFT COSTS (as % of HARD COSTS + GENERAL CONDITIONS) ===
        # CRITICAL: Soft costs apply to (hard costs + GC), not hard costs alone
        # From TechRidge budget reverse calculation:
        # Parking hard costs: $10,228,102
        # Parking GC: $958,008
        # Base for soft costs: $11,186,110
        # Then: CM fee, insurance, contingencies applied to this base
        soft_cost_base = hard_cost_total + costs['general_conditions']

        costs['cm_fee'] = soft_cost_base * self.soft_costs_pct['cm_fee']
        costs['insurance'] = soft_cost_base * self.soft_costs_pct['insurance']
        costs['contingency'] = soft_cost_base * (
            self.soft_costs_pct['contingency_cm'] + self.soft_costs_pct['contingency_design']
        )

        # === TOTAL COST ===
        soft_cost_total = (costs['general_conditions'] + costs['cm_fee'] +
                          costs['insurance'] + costs['contingency'])
        costs['soft_cost_subtotal'] = soft_cost_total
        costs['total'] = hard_cost_total + soft_cost_total

        # === UNIT COSTS ===
        costs['cost_per_stall'] = costs['total'] / garage.total_stalls
        # Use total_gsf (sum of discrete level areas) instead of footprint for accuracy
        # This accounts for half-levels being ~50% of footprint area
        costs['cost_per_sf'] = costs['total'] / garage.total_gsf

        return costs

    def _calculate_foundation(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate foundation costs using discrete components

        DISCRETE COMPONENTS:
        - Slab on grade (5" thick concrete)
        - Under-slab vapor barrier
        - Under-slab gravel
        - Footings (continuous and spot)
        - Grade beams
        - Rebar for foundation (separate line item)
        """
        cost = 0

        # Slab on grade (5" thick)
        # SOG = full footprint (bottom 2 half-levels on shaped dirt)
        sog_sf = garage.sog_levels_sf
        sog_cost_per_sf = self.costs['structure']['slab_on_grade_5in_sf']
        cost += sog_sf * sog_cost_per_sf

        # Under-slab vapor barrier
        vapor_barrier_cost_per_sf = self.costs['structure']['vapor_barrier_sf']
        cost += sog_sf * vapor_barrier_cost_per_sf

        # Under-slab gravel (4" compacted)
        gravel_cost_per_sf = self.costs['structure']['under_slab_gravel_sf']
        cost += sog_sf * gravel_cost_per_sf

        # Sub-drain system (drainage layer/mat under entire slab)
        subdrain_cost_per_sf = self.costs['foundation']['subdrain_system_sf']
        cost += garage.footprint_sf * subdrain_cost_per_sf

        # Footing drain (perimeter drainage - only if below-grade construction)
        if garage.half_levels_below > 0:
            perimeter_lf = 2 * (garage.width + garage.length)
            footing_drain_cost = perimeter_lf * self.costs['foundation']['footing_drain_lf']
            cost += footing_drain_cost

        # Footings - Discrete calculation from FootingCalculator
        # Uses actual footing quantities calculated in geometry._calculate_footings()
        # Includes: spread footings, continuous footings, retaining wall footings

        # Spread footings (under columns)
        spread_concrete_cost = (garage.spread_footing_concrete_cy *
                               self.costs['foundation']['footings_spot_cy'])
        spread_rebar_cost = (garage.spread_footing_rebar_lbs *
                            self.costs['foundation']['rebar_footings_lbs'])
        spread_excavation_cost = (garage.spread_footing_excavation_cy *
                                 self.costs['foundation']['excavation_footings_cy'])

        # Continuous footings (under core walls)
        continuous_concrete_cost = (garage.continuous_footing_concrete_cy *
                                   self.costs['foundation']['footings_continuous_cy'])
        continuous_rebar_cost = (garage.continuous_footing_rebar_lbs *
                                self.costs['foundation']['rebar_footings_lbs'])
        continuous_excavation_cost = (garage.continuous_footing_excavation_cy *
                                     self.costs['foundation']['excavation_footings_cy'])

        # Retaining wall footings (if below-grade levels exist)
        retaining_concrete_cost = (garage.retaining_wall_footing_concrete_cy *
                                  self.costs['foundation']['footings_continuous_cy'])
        retaining_rebar_cost = (garage.retaining_wall_footing_rebar_lbs *
                               self.costs['foundation']['rebar_footings_lbs'])
        retaining_excavation_cost = (garage.retaining_wall_footing_excavation_cy *
                                    self.costs['foundation']['excavation_footings_cy'])

        # Total footing costs
        footing_cost = (
            spread_concrete_cost + spread_rebar_cost + spread_excavation_cost +
            continuous_concrete_cost + continuous_rebar_cost + continuous_excavation_cost +
            retaining_concrete_cost + retaining_rebar_cost + retaining_excavation_cost
        )

        cost += footing_cost

        return cost

    def _calculate_excavation(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate excavation costs (for below-grade construction)

        Includes:
        - Mass excavation
        - Export/haul-off
        - Structural fill import
        - Over-excavation
        - Retaining walls
        - Waterproofing
        - Under-slab drainage
        """
        if garage.half_levels_below == 0:
            return 0

        cost = 0

        # Excavation and export
        cost += garage.excavation_cy * self.costs['below_grade_premiums']['mass_excavation_3_5ft_cy']
        cost += garage.export_cy * self.costs['foundation']['export_excess_cy']

        # Structural fill
        cost += garage.structural_fill_cy * self.costs['below_grade_premiums']['import_structural_fill_cy']

        # Retaining walls
        cost += garage.retaining_wall_sf * self.costs['below_grade_premiums']['retaining_wall_cw12_sf']

        # Waterproofing (perimeter walls)
        cost += garage.retaining_wall_sf * self.costs['foundation']['dampproofing_sf']

        # Under-slab drainage
        cost += garage.footprint_sf * self.costs['below_grade_premiums']['under_slab_drainage_sf']

        return cost

    def _calculate_structure_above(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate structure costs for above-grade levels using discrete components

        DISCRETE COMPONENTS (calculated separately - NOT included here):
        - Rebar (see _calculate_rebar)
        - Post-tension cables (see _calculate_post_tensioning)
        - Core walls (see _calculate_core_walls)
        - Concrete pumping (see _calculate_concrete_pumping)

        THIS METHOD CALCULATES:
        - Suspended PT slabs (concrete + formwork + placement)
        - Columns (concrete + formwork + placement)
        """
        if garage.half_levels_above == 0:
            return 0

        cost = 0

        # Suspended PT slabs (8" thick)
        # Use discrete sum of suspended level areas (already calculated in geometry)
        suspended_slab_sf = garage.suspended_levels_sf
        slab_cost_per_sf = self.costs['structure']['suspended_slab_8in_sf']
        cost += suspended_slab_sf * slab_cost_per_sf

        # Columns (18" × 24" @ 31' grid)
        # Geometry provides column concrete in CY
        column_concrete_cy = garage.concrete_columns_cy
        column_cost_per_cy = self.costs['structure']['columns_18x24_cy']
        cost += column_concrete_cy * column_cost_per_cy

        return cost

    def _calculate_structure_below(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate structure costs for below-grade levels (with premiums)

        Below-grade multipliers:
        - First level (P0.5): 1.83× above-grade cost
        - Subsequent levels: 1.27× above-grade cost
        """
        if garage.half_levels_below == 0:
            return 0

        cost = 0
        base_cost_per_sf = self.derived['structure_above_per_sf_floor']

        # First 2 half-levels below-grade (e.g., B-0.5, B-1)
        cost += garage.footprint_sf * base_cost_per_sf * self.derived['structure_below_multiplier_first']

        # Additional below-grade half-levels beyond first 2 (if any)
        if garage.half_levels_below > 2:
            additional_half_levels = garage.half_levels_below - 2
            cost += (garage.footprint_sf * additional_half_levels *
                    base_cost_per_sf * self.derived['structure_below_multiplier_subsequent'])

        return cost

    def _calculate_mep(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate MEP systems cost

        Broken out by system per TechRidge budget:
        - Fire protection: $3.00/SF (sprinklers, standpipes, fire alarm)
        - Plumbing: $1.50/SF (hose bibs, floor drains, domestic water)
        - HVAC: $2.25/SF (ventilation - fans, ductwork, CO monitoring)
        - Electrical: $3.25/SF (lighting, power, EV charging rough-in)
        Total: $10.00/SF

        Uses discrete level GSF sum - NOT net area or footprint × levels
        """
        # Total parking area = sum of all discrete level GSF from geometry engine
        # Each level (P0.5, P1, P1.5, etc.) has individually calculated GSF
        # Half-levels ≈ 50% footprint, entry/top levels have reductions
        # This ensures MEP costs scale correctly with actual built area
        total_parking_sf = garage.total_gsf

        # Break out by system (updated from $7/SF blanket to $10/SF itemized)
        cost = 0
        cost += total_parking_sf * self.costs['mep']['fire_protection_parking_sf']  # $3.00/SF
        cost += total_parking_sf * self.costs['mep']['plumbing_parking_sf']  # $1.50/SF
        cost += total_parking_sf * self.costs['mep']['hvac_parking_sf']  # $2.25/SF
        cost += total_parking_sf * self.costs['mep']['electrical_parking_sf']  # $3.25/SF

        return cost

    def _calculate_vdc_coordination(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate VDC (Virtual Design & Construction) coordination costs

        VDC includes:
        - BIM model coordination across all trades
        - Clash detection and resolution
        - Shop drawing review
        - As-built documentation

        From TechRidge: ~$212K VDC for 127K SF = $0.17/SF blended rate
        Scales with building size as coordination effort increases with complexity
        """
        return garage.total_gsf * self.component_costs['vdc_coordination_per_sf_building']

    def _calculate_exterior(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate exterior wall/screening costs using discrete components

        Brake metal parking screen on perimeter
        """
        # Exterior surface area (perimeter × height)
        exterior_sf = garage.exterior_wall_sf

        # Parking screen unit cost ($82/SF from cost database)
        screen_cost_per_sf = self.costs['exterior']['parking_screen_sf']
        cost = exterior_sf * screen_cost_per_sf

        return cost

    def _calculate_site_finishes(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate site finishes cost

        Includes:
        - Sealed concrete floors (epoxy/urethane sealer)
        - Pavement markings (striping, stall numbers, directional arrows)
        - Signage (wayfinding, ADA compliance)
        - Post-construction cleaning

        Uses discrete level GSF sum - NOT net area or footprint × levels
        """
        cost = 0

        # Total parking floor area = sum of all discrete level GSF from geometry engine
        # Sealing and striping applied to all parking surfaces across all levels
        total_parking_sf = garage.total_gsf

        # Sealed concrete
        cost += total_parking_sf * self.costs['site']['sealed_concrete_parking_sf']

        # Pavement markings (per stall)
        cost += garage.total_stalls * self.costs['site']['pavement_markings_per_stall']

        # Final cleaning
        cost += total_parking_sf * self.costs['site']['final_cleaning_parking_sf']

        return cost

    def _calculate_concrete_pumping(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate concrete pumping costs

        Based on total concrete volume
        """
        total_concrete_cy = garage.total_concrete_cy
        cost_per_cy = self.component_costs['concrete_pumping_per_cy']

        return total_concrete_cy * cost_per_cy

    def _calculate_rebar_by_component(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate rebar costs by component (footings, columns, slabs, walls)

        Uses component-specific quantities from budget
        """
        cost = 0
        cost_per_lb = self.component_costs['rebar_cost_per_lb']

        # Footings rebar (lbs per CY of footing concrete)
        footing_rebar_lbs = garage.concrete_foundation_cy * self.component_costs['rebar_footings_lbs_per_cy_concrete']
        cost += footing_rebar_lbs * cost_per_lb

        # Column rebar (lbs per CY of column concrete)
        column_rebar_lbs = garage.concrete_columns_cy * self.component_costs['rebar_columns_lbs_per_cy_concrete']
        cost += column_rebar_lbs * cost_per_lb

        # PT slab rebar (lbs per SF of slab)
        slab_rebar_lbs = garage.total_slab_sf * self.component_costs['rebar_pt_slab_lbs_per_sf']
        cost += slab_rebar_lbs * cost_per_lb

        # NOTE: Center core wall and curb rebar calculated in _calculate_core_walls()
        # Split-level uses 12" solid core walls, single-ramp has no center elements

        return cost

    def _calculate_post_tensioning(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate post-tensioning cable costs

        Based on SF of suspended slabs (not SOG)
        """
        # Only suspended slabs get PT (not foundation SOG)
        suspended_slab_sf = garage.total_slab_sf

        # PT cable quantity (lbs per SF)
        pt_lbs_per_sf = self.component_costs['post_tension_cables_lbs_per_sf_8in']
        total_pt_lbs = suspended_slab_sf * pt_lbs_per_sf

        # Cost
        cost_per_lb = self.component_costs['post_tension_cable_cost_per_lb']

        return total_pt_lbs * cost_per_lb

    def _calculate_core_walls(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate all wall costs using discrete component takeoffs

        Wall types vary by ramp system:

        SPLIT-LEVEL DOUBLE-RAMP (2-bay):
        - CENTER CORE WALL (12" concrete) - traffic separation & structural support
        - CENTER CURBS (12" × 8" wheel stops) - protect core wall
        - BAY CAP BARRIER (36" × 6" concrete) - top level ramp termination

        SPLIT-LEVEL DOUBLE-RAMP (3+ bay):
        - RAMP EDGE BARRIERS (36" × 6" concrete) - at ramp/parking interfaces, full height
        - NO core wall or curbs (ramps separated by parking bays)

        SINGLE-RAMP FULL-FLOOR (2-bay):
        - NO ramp barriers (relies on existing structures)

        SINGLE-RAMP FULL-FLOOR (3+ bay):
        - RAMP BARRIERS (36" × 6" concrete) - both sides of center ramp bay, full height

        BOTH SYSTEMS:
        - Elevator shaft (12" concrete)
        - Stair enclosures (12" concrete)
        - Utility closet (12" concrete)
        - Storage closet (12" concrete)
        - Top-level perimeter barrier (36" concrete) - standalone garages only
        - Elevator pit (8" CMU) - below grade only

        Returns total wall cost
        """
        cost = 0

        # === SYSTEM-SPECIFIC CENTER ELEMENTS ===
        from .geometry.design_modes import RampSystemType

        # Validate ramp system type
        if not isinstance(garage.ramp_system, RampSystemType):
            raise TypeError(
                f"garage.ramp_system must be RampSystemType enum, got {type(garage.ramp_system).__name__}"
            )

        if garage.ramp_system == RampSystemType.SPLIT_LEVEL_DOUBLE:
            cost += self._calculate_split_level_center_costs(garage)
        elif garage.ramp_system == RampSystemType.SINGLE_RAMP_FULL:
            cost += self._calculate_single_ramp_barrier_costs(garage)
        else:
            raise ValueError(f"Unknown ramp system type: {garage.ramp_system}")

        # === PERIMETER BARRIERS (BOTH SYSTEMS) ===
        cost += self._calculate_perimeter_barrier_costs(garage)

        # === CORE STRUCTURES (BOTH SYSTEMS) ===
        cost += self._calculate_core_structure_costs(garage)

        return cost

    def _calculate_split_level_center_costs(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate center element costs for split-level double-ramp system

        2-bay configuration:
        - 12" concrete core wall (full height)
        - 8" × 12" curbs (both sides, all levels)
        - Bay cap barrier (36" × 6", top level only, spans building width)

        3+ bay configuration:
        - NO core wall or curbs
        - Ramp edge barriers (36" × 6", full height, at ramp/parking interfaces)

        Returns: Total cost for split-level center elements
        """
        cost = 0
        rebar_cost_per_lb = self.component_costs['rebar_cost_per_lb']

        # === CENTER CORE WALL ===
        # 12" thick concrete wall, full height
        # Cost at $28.50/SF (formed concrete wall rate from budget)
        core_wall_sf = garage.center_core_wall_sf
        core_wall_cost_per_sf = self.component_costs['core_wall_12in_cost_per_sf']  # $28.50/SF
        cost += core_wall_sf * core_wall_cost_per_sf

        # Core wall rebar (structural - use wall rebar rate)
        # Budget shows 3.0 lbs/SF for walls (conservative for 12" wall)
        core_wall_rebar_lbs = core_wall_sf * 3.0  # lbs/SF for walls
        cost += core_wall_rebar_lbs * rebar_cost_per_lb

        # === CENTER CURBS ===
        # 8" × 12" concrete curbs at base of core wall
        # Cost like foundation slabs (simpler forming than structural walls)
        curb_concrete_cy = garage.center_curb_concrete_cy
        curb_cost_per_cy = self.component_costs['curb_8x12_cy']  # $650/CY (placeholder)
        cost += curb_concrete_cy * curb_cost_per_cy

        # Curb rebar (minimal - just reinforcement, not structural)
        curb_rebar_lbs = garage.center_curb_sf * 0.5  # Reduced rate for curbs
        cost += curb_rebar_lbs * rebar_cost_per_lb

        return cost

    def _calculate_single_ramp_barrier_costs(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate ramp barrier costs for single-ramp full-floor system

        Ramp barriers (3+ bay only):
        - 36" tall × 6" thick concrete barriers
        - Located at both edges of ramp bay
        - Full building height (all floors)
        - Replaces center columns + beams + curbs from split-level

        2-bay single-ramp has NO barriers (relies on existing structures)

        Uses same cost rate as formed concrete walls: $28.50/SF
        Rebar: 4.0 lbs/SF (standard wall rate from cost database)

        Returns: Total cost for ramp barriers
        """
        cost = 0
        rebar_cost_per_lb = self.component_costs['rebar_cost_per_lb']

        # === RAMP BARRIERS ===
        # 36" × 6" concrete barriers at ramp bay edges
        # Cost at $28.50/SF (same as formed concrete walls)
        barrier_sf = garage.ramp_barrier_sf
        barrier_cost_per_sf = self.component_costs['core_wall_12in_cost_per_sf']  # $28.50/SF
        cost += barrier_sf * barrier_cost_per_sf

        # Rebar (4.0 lbs/SF - standard wall rate from cost database)
        # Note: garage.py already calculates ramp_barrier_rebar_lbs
        barrier_rebar_lbs = garage.ramp_barrier_rebar_lbs
        cost += barrier_rebar_lbs * rebar_cost_per_lb

        return cost

    def _calculate_perimeter_barrier_costs(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate perimeter barrier costs (used by both ramp systems)

        36" (3 ft) concrete walls around perimeter of all levels above entry

        Returns: Total cost for perimeter barriers
        """
        cost = 0
        rebar_cost_per_lb = self.component_costs['rebar_cost_per_lb']

        # === PERIMETER BARRIERS ===
        # 36" (3 ft) concrete walls around perimeter of all levels
        # Cost at $28.50/SF (same as formed concrete walls)
        barrier_sf = garage.perimeter_barrier_sf
        barrier_cost_per_sf = self.component_costs['core_wall_12in_cost_per_sf']
        cost += barrier_sf * barrier_cost_per_sf

        # Barrier rebar (similar to walls - 3.0 lbs/SF)
        barrier_rebar_lbs = barrier_sf * 3.0  # lbs/SF for barriers
        cost += barrier_rebar_lbs * rebar_cost_per_lb

        return cost

    def _calculate_core_structure_costs(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate core structure costs (used by both ramp systems)

        Includes:
        - Elevator shaft (12" concrete)
        - Stair enclosures (12" concrete)
        - Utility closet (NW corner, 20'×19', 12" concrete)
        - Storage closet (SW corner, 29'×18', 12" concrete)
        - Top-level perimeter barrier (3' tall, 12" concrete, categorized as shearwall)
        - Elevator pit (8" CMU) - below grade only

        Returns: Total cost for core structures
        """
        cost = 0
        rebar_cost_per_lb = self.component_costs['rebar_cost_per_lb']

        # === ELEVATOR & STAIR WALLS ===
        # Elevator shaft - 12" concrete
        elevator_shaft_sf = garage.elevator_shaft_sf
        cost += elevator_shaft_sf * self.component_costs['core_wall_12in_cost_per_sf']

        # Stair enclosures - 12" concrete
        stair_enclosure_sf = garage.stair_enclosure_sf
        cost += stair_enclosure_sf * self.component_costs['core_wall_12in_cost_per_sf']

        # === UTILITY & STORAGE CLOSET WALLS ===
        # Utility closet (NW corner) - 12" concrete, 20'×19'
        utility_closet_sf = garage.utility_closet_sf
        cost += utility_closet_sf * self.component_costs['core_wall_12in_cost_per_sf']

        # Storage closet (SW corner) - 12" concrete, 29'×18'
        storage_closet_sf = garage.storage_closet_sf
        cost += storage_closet_sf * self.component_costs['core_wall_12in_cost_per_sf']

        # === TOP-LEVEL PERIMETER BARRIER (12" SHEARWALL CATEGORY) ===
        # 3' tall concrete barrier around perimeter of top level
        # Categorized with 12" shearwalls (not parking barriers) per TechRidge budget
        # Both faces counted for forming cost
        top_barrier_sf = garage.top_level_barrier_12in_sf
        cost += top_barrier_sf * self.component_costs['core_wall_12in_cost_per_sf']

        # Rebar for top barrier (4.0 lbs/SF - same as walls)
        top_barrier_rebar_lbs = top_barrier_sf * 4.0
        cost += top_barrier_rebar_lbs * rebar_cost_per_lb

        # Elevator pit - 8" CMU (always - standard construction practice)
        # CMU pit below concrete shaft (cheaper and easier than formed concrete)
        elevator_pit_cmu_sf = garage.elevator_pit_cmu_sf
        # Use masonry_wall cost from unit_costs
        cost += elevator_pit_cmu_sf * self.costs['structure']['masonry_wall_8in_sf']

        return cost

    def _calculate_retaining_walls(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate retaining wall costs for below-grade perimeter

        Already included in excavation costs, so return 0 to avoid double-counting
        """
        # This is already accounted for in _calculate_excavation()
        # Returning 0 to avoid double-counting
        return 0

    def _calculate_elevators(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate elevator costs based on number of stops

        Includes:
        - Base elevator cost per stop
        - Elevator accessories (sump pits, ladders, upgrades, permits, warranties)

        Note: Current design assumes 1 elevator per building (standard for parking structures)
        """
        num_stops = garage.num_elevator_stops
        num_elevators = 1  # Fixed: 1 elevator per building in current design

        # Base elevator cost
        cost = num_stops * self.component_costs['elevator_cost_per_stop']

        # Elevator accessories (per elevator)
        cost += num_elevators * self.component_costs['elevator_sump_pit_ea']
        cost += num_elevators * self.component_costs['elevator_pit_ladder_ea']
        cost += num_elevators * self.component_costs['elevator_cab_upgrade_ea']
        cost += num_elevators * self.component_costs['elevator_construction_permit_ea']
        cost += num_elevators * self.component_costs['elevator_warranty_extension_ea']
        cost += num_elevators * self.component_costs['elevator_cab_protection_ea']
        cost += num_elevators * self.component_costs['elevator_cab_refurbish_ea']

        return cost

    def _calculate_stairs(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate stair costs based on number of flights

        Includes:
        - Metal stair pan with concrete infill ($10,400/flight)
        - Guardrails and handrails ($3,150/flight)
        """
        num_flights = garage.num_stair_flights

        # Metal stair pan cost
        cost = num_flights * self.component_costs['stair_flight_cost']

        # Guardrails and handrails (separate line item in TR budget)
        cost += num_flights * self.component_costs['stair_railing_per_flight']

        return cost

    def _calculate_structural_accessories(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate structural accessories and miscellaneous items

        Includes:
        - Stud rails (elevated deck anchors, 12 per column)
        - Expansion joints (seismic/thermal movement)
        - Embeds and anchor bolts (connections)
        - Miscellaneous metals (railings, supports, misc fabrications)
        - Beam allowance (complex situations, atypical spans)
        """
        cost = 0

        # Stud rails - post-tensioned slab anchors, 12 per column
        num_studs = garage.num_columns * self.component_costs['studs_per_column_count']
        cost += num_studs * self.component_costs['stud_rails_per_column']

        # Expansion joints - seismic/thermal movement control
        # From TechRidge: 678 LF for 126'×210' building perimeter = 672 LF
        # Expansion joints run approximately 1× building perimeter
        perimeter_lf = 2 * (garage.width + garage.length)
        expansion_joint_lf = perimeter_lf
        cost += expansion_joint_lf * self.component_costs['expansion_joint_cost_per_lf']

        # Embeds and anchor bolts - connections in suspended slabs
        embeds_cost = garage.suspended_slab_sf * self.component_costs['embeds_anchor_bolts_per_sf_suspended']
        cost += embeds_cost

        # Miscellaneous metals - railings, supports, misc fabrications
        misc_metals_lbs = garage.total_gsf * self.component_costs['misc_metals_lbs_per_sf_building']
        misc_metals_tons = misc_metals_lbs / 2000
        cost += misc_metals_tons * self.component_costs['misc_metals_cost_per_ton']

        # Beam allowance - complex situations, atypical spans
        # From TechRidge: $200K / 127K SF = $1.57/SF
        # Scales with building size independent of material costs
        cost += garage.total_gsf * self.component_costs['beam_allowance_per_sf_building']

        return cost

    def _calculate_interior_finishes(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate interior finishes for parking garage

        Includes:
        - Sealed concrete finish (parking areas)
        - Wall/ceiling painting (cores, stairs, lobbies)
        - Commercial doors with hardware (stairs, elevators, utility rooms)
        - Door frame painting
        - Final cleaning
        """
        cost = 0

        # Sealed concrete finish - parking surface sealer/hardener
        cost += garage.total_gsf * self.costs['site']['sealed_concrete_parking_sf']

        # Wall/ceiling painting - cores, stairs, elevator lobbies
        # Temporary proxy: $0.42/SF of building GSF (will be replaced with actual wall area calculation)
        cost += garage.total_gsf * self.component_costs['painting_walls_ceilings_per_sf_building']

        # Commercial doors - estimate based on building size and access points
        # Rule of thumb: 2 stair doors per level + 2 elevator doors per level + utility/storage access
        num_levels = garage.total_levels
        num_elevators = 1  # Fixed: 1 elevator per building in current design
        num_single_doors = (garage.num_stairs * 2 * num_levels +  # Stair doors (entry/exit each stair)
                           num_elevators * 2 * num_levels +  # Elevator lobby doors
                           4)  # Utility/storage/mechanical room doors
        cost += num_single_doors * self.component_costs['commercial_door_single_ea']

        # Door frame painting
        cost += num_single_doors * self.component_costs['door_frame_painting_ea']

        # Final cleaning
        cost += garage.total_gsf * self.costs['site']['final_cleaning_parking_sf']

        return cost

    def _calculate_special_systems(self, garage: SplitLevelParkingGarage) -> float:
        """
        Calculate special systems and equipment

        Includes:
        - Fire extinguishers with cabinets (code required)
        - Pavement markings (striping per stall)
        - Knox box (fire department access)
        """
        cost = 0

        # Fire extinguishers - code required spacing (typically 75' travel distance max)
        # Rule of thumb: 1 per 5,000 SF building area, minimum 1 per floor
        num_extinguishers = max(num_levels := garage.total_levels,
                               int(garage.total_gsf / 5000))
        cost += num_extinguishers * self.component_costs['fire_extinguisher_with_cabinet_ea']

        # Pavement markings - striping per stall
        cost += garage.total_stalls * self.costs['site']['pavement_markings_per_stall']

        # Knox box - fire department rapid entry (2 locations typical)
        cost += 2 * self.component_costs['knox_box_ea']

        return cost

    def _calculate_general_conditions(self, hard_cost_total: float, gc_params: dict = None) -> float:
        """
        Calculate general conditions using user-selected method

        Method 1 (DEFAULT): Percentage of hard costs
        - From TechRidge budget: $958,008 GC / $10,228,102 hard costs = 9.37%
        - Better for parametric scaling to different project sizes

        Method 2: Monthly rate × duration
        - From budget: $191,008/month (derived from $958,008 / 5 months)
        - Requires user-estimated duration (not CPM schedule)

        Args:
            hard_cost_total: Sum of all hard costs before GC
            gc_params: {"method": "percentage", "value": 9.37} or
                      {"method": "monthly_rate", "value": 5.0}

        Returns:
            General conditions cost
        """
        # Default to percentage method if not specified
        if gc_params is None:
            gc_params = {"method": "percentage", "value": 9.37}

        if gc_params["method"] == "percentage":
            # Percentage of hard costs (better for scaling)
            gc_percentage = gc_params["value"] / 100  # Convert % to decimal
            return hard_cost_total * gc_percentage

        elif gc_params["method"] == "monthly_rate":
            # Duration × monthly rate
            estimated_duration_months = max(3.0, gc_params["value"])  # Minimum 3 months
            cost_per_month = self.component_costs['general_conditions_per_month']
            return estimated_duration_months * cost_per_month

        else:
            raise ValueError(f"Unknown GC method: {gc_params['method']}")

    def get_cost_breakdown_table(self, garage: SplitLevelParkingGarage) -> Dict:
        """
        Return formatted cost breakdown for display

        Returns dict organized by category with subtotals
        """
        costs = self.calculate_all_costs(garage)

        breakdown = {
            'Hard Costs': {
                'Foundation': costs['foundation'],
                'Excavation & Site Prep': costs['excavation'],
                'Structure (Above Grade)': costs['structure_above'],
                'Structure (Below Grade)': costs['structure_below'],
                'Concrete Pumping': costs['concrete_pumping'],
                'Rebar (All Components)': costs['rebar'],
                'Post-Tensioning': costs['post_tensioning'],
                'Core Walls (12" Fire Walls)': costs['core_walls'],
                'Retaining Walls': costs['retaining_walls'],
                'Ramp System': costs['ramp_system'],
                'Elevators': costs['elevators'],
                'Stairs': costs['stairs'],
                'Structural Accessories': costs['structural_accessories'],
                'MEP Systems': costs['mep'],
                'VDC Coordination': costs['vdc_coordination'],
                'Exterior Walls/Screen': costs['exterior'],
                'Interior Finishes': costs['interior_finishes'],
                'Special Systems': costs['special_systems'],
                'Site Finishes': costs['site_finishes'],
                'Subtotal': costs['hard_cost_subtotal']
            },
            'Soft Costs': {
                'General Conditions': costs['general_conditions'],
                'CM Fee': costs['cm_fee'],
                'Insurance': costs['insurance'],
                'Contingency': costs['contingency'],
                'Subtotal': costs['soft_cost_subtotal']
            },
            'Total': costs['total'],
            'Unit Costs': {
                'Per Stall': costs['cost_per_stall'],
                'Per SF (total GSF)': costs['cost_per_sf']
            }
        }

        return breakdown

    def get_detailed_quantity_takeoffs(self, garage: SplitLevelParkingGarage) -> Dict:
        """
        Return comprehensive quantity takeoffs with cost attribution for detailed UI display

        Organizes all quantities into 9 major sections:
        1. Foundation
        2. Excavation & Earthwork
        3. Structure - Concrete
        4. Structure - Reinforcement (with component attribution)
        5. Structure - Walls & Cores
        6. Vertical Transportation
        7. MEP Systems
        8. Exterior & Finishes
        9. Level-by-Level Summary

        Each section contains detailed quantity breakdowns with:
        - Component name
        - Quantity value
        - Unit type
        - Unit cost
        - Component total cost
        - Description/notes

        Returns:
            Dict with structured data for accordion/table display
        """
        sections = {}

        # Get helper data
        wall_lf = garage.get_wall_linear_feet_breakdown()
        column_data = garage.get_column_breakdown()
        level_data = garage.get_level_breakdown()

        # ========== SECTION 1: FOUNDATION ==========
        foundation_items = []

        # Slab on grade
        sog_sf = garage.sog_levels_sf
        sog_unit_cost = self.costs['structure']['slab_on_grade_5in_sf']
        foundation_items.append({
            'component': 'Slab on Grade (5" thick)',
            'quantity': sog_sf,
            'unit': 'SF',
            'unit_cost': sog_unit_cost,
            'total': sog_sf * sog_unit_cost,
            'notes': f'{garage.footprint_sf:,.0f} SF footprint'
        })

        # Vapor barrier (moved to 'structure' section in cost database)
        vapor_sf = sog_sf
        vapor_unit_cost = self.costs['structure']['vapor_barrier_sf']
        foundation_items.append({
            'component': 'Under-Slab Vapor Barrier',
            'quantity': vapor_sf,
            'unit': 'SF',
            'unit_cost': vapor_unit_cost,
            'total': vapor_sf * vapor_unit_cost,
            'notes': 'Under SOG area'
        })

        # Gravel (moved to 'structure' section, renamed to 'under_slab_gravel_sf')
        gravel_sf = sog_sf
        gravel_unit_cost = self.costs['structure']['under_slab_gravel_sf']
        foundation_items.append({
            'component': 'Under-Slab Gravel (4" thick)',
            'quantity': gravel_sf,
            'unit': 'SF',
            'unit_cost': gravel_unit_cost,
            'total': gravel_sf * gravel_unit_cost,
            'notes': '4" compacted base'
        })

        # Spread footings (detailed breakdown by type)
        if hasattr(garage, 'spread_footing_concrete_cy') and garage.spread_footing_concrete_cy > 0:
            spread_concrete_cy = garage.spread_footing_concrete_cy
            spread_rebar_lbs = garage.spread_footing_rebar_lbs
            spread_excavation_cy = garage.spread_footing_excavation_cy

            footing_concrete_cost = self.costs['foundation']['footings_spot_cy']
            rebar_cost = self.component_costs['rebar_cost_per_lb']
            excavation_cost = self.costs['below_grade_premiums']['mass_excavation_3_5ft_cy']

            # Get footing details if available
            if hasattr(garage, 'footing_details') and garage.footing_details:
                spread_footings = garage.footing_details.get('spread_footings', {})
                count_by_type = spread_footings.get('count_by_type', {})

                for ftype, count in count_by_type.items():
                    if count > 0:
                        foundation_items.append({
                            'component': f'  Spread Footings - {ftype.replace("_", " ").title()}',
                            'quantity': count,
                            'unit': 'EA',
                            'unit_cost': None,
                            'total': None,
                            'notes': f'{count} footings'
                        })

            foundation_items.append({
                'component': 'Spread Footings - Concrete',
                'quantity': spread_concrete_cy,
                'unit': 'CY',
                'unit_cost': footing_concrete_cost,
                'total': spread_concrete_cy * footing_concrete_cost,
                'notes': f'Avg {spread_concrete_cy/max(1, garage.num_columns):.1f} CY per footing'
            })

            foundation_items.append({
                'component': 'Spread Footings - Rebar',
                'quantity': spread_rebar_lbs,
                'unit': 'LBS',
                'unit_cost': rebar_cost,
                'total': spread_rebar_lbs * rebar_cost,
                'notes': f'{spread_rebar_lbs/spread_concrete_cy:.0f} lbs/CY'
            })

            foundation_items.append({
                'component': 'Spread Footings - Excavation',
                'quantity': spread_excavation_cy,
                'unit': 'CY',
                'unit_cost': excavation_cost,
                'total': spread_excavation_cy * excavation_cost,
                'notes': 'Overdig for footings'
            })

        # Continuous footings
        if hasattr(garage, 'continuous_footing_concrete_cy') and garage.continuous_footing_concrete_cy > 0:
            cont_concrete_cy = garage.continuous_footing_concrete_cy
            cont_rebar_lbs = garage.continuous_footing_rebar_lbs
            cont_excavation_cy = garage.continuous_footing_excavation_cy

            footing_concrete_cost = self.costs['foundation']['footings_spot_cy']
            rebar_cost = self.component_costs['rebar_cost_per_lb']
            excavation_cost = self.costs['below_grade_premiums']['mass_excavation_3_5ft_cy']

            # Get detailed continuous footing info if available
            if hasattr(garage, 'footing_details') and garage.footing_details:
                cont_footings = garage.footing_details.get('continuous_footings', {})
                footings_list = cont_footings.get('footings', [])

                for ftg in footings_list:
                    wall_type = ftg.get('wall_type', 'unknown')
                    length_ft = ftg.get('length_ft', 0)
                    width_ft = ftg.get('width_ft', 0)
                    depth_ft = ftg.get('depth_ft', 0)

                    foundation_items.append({
                        'component': f'  Continuous Footing - {wall_type.replace("_", " ").title()}',
                        'quantity': length_ft,
                        'unit': 'LF',
                        'unit_cost': None,
                        'total': None,
                        'notes': f'{width_ft:.1f}\'W × {depth_ft:.1f}\'D'
                    })

            foundation_items.append({
                'component': 'Continuous Footings - Concrete',
                'quantity': cont_concrete_cy,
                'unit': 'CY',
                'unit_cost': footing_concrete_cost,
                'total': cont_concrete_cy * footing_concrete_cost,
                'notes': f'Under elevator, stairs, cores'
            })

            foundation_items.append({
                'component': 'Continuous Footings - Rebar',
                'quantity': cont_rebar_lbs,
                'unit': 'LBS',
                'unit_cost': rebar_cost,
                'total': cont_rebar_lbs * rebar_cost,
                'notes': f'{cont_rebar_lbs/cont_concrete_cy:.0f} lbs/CY'
            })

            foundation_items.append({
                'component': 'Continuous Footings - Excavation',
                'quantity': cont_excavation_cy,
                'unit': 'CY',
                'unit_cost': excavation_cost,
                'total': cont_excavation_cy * excavation_cost,
                'notes': 'Trench excavation'
            })

        # Retaining wall footings (if below grade)
        if hasattr(garage, 'retaining_wall_footing_concrete_cy') and garage.retaining_wall_footing_concrete_cy > 0:
            ret_concrete_cy = garage.retaining_wall_footing_concrete_cy
            ret_rebar_lbs = garage.retaining_wall_footing_rebar_lbs
            ret_excavation_cy = garage.retaining_wall_footing_excavation_cy

            footing_concrete_cost = self.costs['foundation']['footings_spot_cy']
            rebar_cost = self.component_costs['rebar_cost_per_lb']
            excavation_cost = self.costs['below_grade_premiums']['mass_excavation_3_5ft_cy']

            foundation_items.append({
                'component': 'Retaining Wall Footings - Concrete',
                'quantity': ret_concrete_cy,
                'unit': 'CY',
                'unit_cost': footing_concrete_cost,
                'total': ret_concrete_cy * footing_concrete_cost,
                'notes': 'Cantilever footing'
            })

            foundation_items.append({
                'component': 'Retaining Wall Footings - Rebar',
                'quantity': ret_rebar_lbs,
                'unit': 'LBS',
                'unit_cost': rebar_cost,
                'total': ret_rebar_lbs * rebar_cost,
                'notes': f'{ret_rebar_lbs/ret_concrete_cy:.0f} lbs/CY'
            })

        sections['01_foundation'] = {
            'title': '01 - FOUNDATION',
            'items': foundation_items,
            'total': sum(item['total'] for item in foundation_items if item['total'] is not None)
        }

        # ========== SECTION 2: EXCAVATION & EARTHWORK ==========
        excavation_items = []

        if garage.excavation_cy > 0:
            mass_ex_cost = self.costs['below_grade_premiums']['mass_excavation_3_5ft_cy']
            excavation_items.append({
                'component': 'Mass Excavation',
                'quantity': garage.excavation_cy,
                'unit': 'CY',
                'unit_cost': mass_ex_cost,
                'total': garage.excavation_cy * mass_ex_cost,
                'notes': f'{garage.half_levels_below} levels below grade'
            })

        if garage.export_cy > 0:
            export_cost = self.costs['foundation']['export_excess_cy']
            excavation_items.append({
                'component': 'Export/Haul-Off',
                'quantity': garage.export_cy,
                'unit': 'CY',
                'unit_cost': export_cost,
                'total': garage.export_cy * export_cost,
                'notes': 'Off-site disposal'
            })

        if garage.structural_fill_cy > 0:
            fill_cost = self.costs['below_grade_premiums']['import_structural_fill_cy']
            excavation_items.append({
                'component': 'Structural Fill',
                'quantity': garage.structural_fill_cy,
                'unit': 'CY',
                'unit_cost': fill_cost,
                'total': garage.structural_fill_cy * fill_cost,
                'notes': 'Compacted backfill'
            })

        if garage.retaining_wall_sf > 0:
            ret_wall_cost = self.costs['below_grade_premiums']['retaining_wall_cw12_sf']
            excavation_items.append({
                'component': 'Retaining Walls (12" concrete)',
                'quantity': garage.retaining_wall_sf,
                'unit': 'SF',
                'unit_cost': ret_wall_cost,
                'total': garage.retaining_wall_sf * ret_wall_cost,
                'notes': f'{garage.perimeter_lf:.0f} LF × {garage.depth_below_grade_ft:.1f}\' H'
            })

        if not excavation_items:
            excavation_items.append({
                'component': 'No below-grade construction',
                'quantity': 0,
                'unit': 'N/A',
                'unit_cost': 0,
                'total': 0,
                'notes': 'All levels above grade'
            })

        sections['02_excavation'] = {
            'title': '02 - EXCAVATION & EARTHWORK',
            'items': excavation_items,
            'total': sum(item['total'] for item in excavation_items if item['total'] is not None)
        }

        # ========== SECTION 3: STRUCTURE - CONCRETE ==========
        concrete_items = []

        # Suspended slabs
        suspended_sf = garage.suspended_levels_sf
        slab_cost_sf = self.costs['structure']['suspended_slab_8in_sf']
        concrete_items.append({
            'component': 'Suspended Slabs (8" PT)',
            'quantity': suspended_sf,
            'unit': 'SF',
            'unit_cost': slab_cost_sf,
            'total': suspended_sf * slab_cost_sf,
            'notes': f'{garage.concrete_slab_cy:.0f} CY ({suspended_sf * (8/12) / 27:.0f} calculated)'
        })

        # Columns
        column_cy = garage.concrete_columns_cy
        column_cost_cy = self.costs['structure']['columns_18x24_cy']
        concrete_items.append({
            'component': f'Columns ({column_data["column_size"]})',
            'quantity': column_cy,
            'unit': 'CY',
            'unit_cost': column_cost_cy,
            'total': column_cy * column_cost_cy,
            'notes': f'{column_data["total_count"]} columns × {column_data["average_height_ft"]:.1f}\' avg H = {column_data["total_linear_feet"]:.0f} LF'
        })

        # Concrete pumping
        total_concrete_cy = garage.total_concrete_cy
        pumping_cost = self.costs['structure']['concrete_pumping_cy']
        concrete_items.append({
            'component': 'Concrete Pumping',
            'quantity': total_concrete_cy,
            'unit': 'CY',
            'unit_cost': pumping_cost,
            'total': total_concrete_cy * pumping_cost,
            'notes': f'All suspended concrete ({total_concrete_cy:.0f} CY total)'
        })

        sections['03_concrete'] = {
            'title': '03 - STRUCTURE - CONCRETE',
            'items': concrete_items,
            'total': sum(item['total'] for item in concrete_items)
        }

        # ========== SECTION 4: STRUCTURE - REINFORCEMENT ==========
        reinforcement_items = []

        rebar_cost = self.component_costs['rebar_cost_per_lb']
        pt_cost = self.costs['structure']['post_tension_cables_lbs']

        # Footing rebar (already calculated above, consolidate here)
        footing_rebar_lbs = garage.concrete_foundation_cy * 110
        if hasattr(garage, 'spread_footing_rebar_lbs'):
            footing_rebar_lbs = (garage.spread_footing_rebar_lbs +
                               garage.continuous_footing_rebar_lbs)
            if hasattr(garage, 'retaining_wall_footing_rebar_lbs'):
                footing_rebar_lbs += garage.retaining_wall_footing_rebar_lbs

        reinforcement_items.append({
            'component': 'Footing Rebar',
            'quantity': footing_rebar_lbs,
            'unit': 'LBS',
            'unit_cost': rebar_cost,
            'total': footing_rebar_lbs * rebar_cost,
            'notes': f'110 lbs/CY avg × {garage.concrete_foundation_cy:.0f} CY footings'
        })

        # Column rebar
        column_rebar_lbs = column_cy * 1320
        reinforcement_items.append({
            'component': 'Column Rebar',
            'quantity': column_rebar_lbs,
            'unit': 'LBS',
            'unit_cost': rebar_cost,
            'total': column_rebar_lbs * rebar_cost,
            'notes': f'1320 lbs/CY × {column_cy:.0f} CY columns'
        })

        # Slab rebar
        slab_rebar_lbs = garage.total_slab_sf * 3.0
        reinforcement_items.append({
            'component': 'Slab Rebar',
            'quantity': slab_rebar_lbs,
            'unit': 'LBS',
            'unit_cost': rebar_cost,
            'total': slab_rebar_lbs * rebar_cost,
            'notes': f'3.0 lbs/SF × {garage.total_slab_sf:,.0f} SF suspended slabs'
        })

        # Wall rebar (cores, barriers, enclosures)
        wall_sf_total = (garage.elevator_shaft_sf + garage.stair_enclosure_sf +
                        garage.utility_closet_sf + garage.storage_closet_sf)

        if hasattr(garage, 'center_core_wall_sf') and garage.center_core_wall_sf > 0:
            wall_sf_total += garage.center_core_wall_sf

        if hasattr(garage, 'ramp_barrier_sf') and garage.ramp_barrier_sf > 0:
            # Barriers already have rebar calculated
            wall_sf_total += garage.ramp_barrier_sf

        wall_rebar_lbs = wall_sf_total * 4.0  # 4.0 lbs/SF for walls

        reinforcement_items.append({
            'component': 'Wall/Core Rebar',
            'quantity': wall_rebar_lbs,
            'unit': 'LBS',
            'unit_cost': rebar_cost,
            'total': wall_rebar_lbs * rebar_cost,
            'notes': f'4.0 lbs/SF × {wall_sf_total:,.0f} SF walls/cores'
        })

        # Post-tensioning cables
        pt_lbs = garage.post_tension_lbs
        reinforcement_items.append({
            'component': 'Post-Tensioning Cables',
            'quantity': pt_lbs,
            'unit': 'LBS',
            'unit_cost': pt_cost,
            'total': pt_lbs * pt_cost,
            'notes': f'1.25 lbs/SF × {garage.suspended_slab_sf:,.0f} SF suspended slabs'
        })

        sections['04_reinforcement'] = {
            'title': '04 - STRUCTURE - REINFORCEMENT',
            'items': reinforcement_items,
            'total': sum(item['total'] for item in reinforcement_items)
        }

        # ========== SECTION 5: STRUCTURE - WALLS & CORES ==========
        walls_items = []

        wall_cost_sf = self.component_costs['core_wall_12in_cost_per_sf']

        # Elevator shaft
        elev_sf = garage.elevator_shaft_sf
        elev_lf = wall_lf['elevator_shaft']['lf']
        elev_height = wall_lf['elevator_shaft']['height_ft']
        walls_items.append({
            'component': 'Elevator Shaft (12" concrete)',
            'quantity': elev_sf,
            'unit': 'SF',
            'unit_cost': wall_cost_sf,
            'total': elev_sf * wall_cost_sf,
            'notes': f'{elev_lf:.0f} LF × {elev_height:.1f}\' H'
        })

        # Stair enclosures
        stair_sf = garage.stair_enclosure_sf
        stair_lf = wall_lf['stair_enclosures']['total_lf']
        stair_height = wall_lf['stair_enclosures']['height_ft']
        walls_items.append({
            'component': f'Stair Enclosures (12" concrete)',
            'quantity': stair_sf,
            'unit': 'SF',
            'unit_cost': wall_cost_sf,
            'total': stair_sf * wall_cost_sf,
            'notes': f'{stair_lf:.0f} LF total × {stair_height:.1f}\' H ({garage.num_stairs} stairs)'
        })

        # Utility closet
        util_sf = garage.utility_closet_sf
        util_lf = wall_lf['utility_closet']['lf']
        util_height = wall_lf['utility_closet']['height_ft']
        walls_items.append({
            'component': 'Utility Closet (12" concrete)',
            'quantity': util_sf,
            'unit': 'SF',
            'unit_cost': wall_cost_sf,
            'total': util_sf * wall_cost_sf,
            'notes': f'{util_lf:.0f} LF × {util_height:.1f}\' H'
        })

        # Storage closet
        stor_sf = garage.storage_closet_sf
        stor_lf = wall_lf['storage_closet']['lf']
        stor_height = wall_lf['storage_closet']['height_ft']
        walls_items.append({
            'component': 'Storage Closet (12" concrete)',
            'quantity': stor_sf,
            'unit': 'SF',
            'unit_cost': wall_cost_sf,
            'total': stor_sf * wall_cost_sf,
            'notes': f'{stor_lf:.0f} LF × {stor_height:.1f}\' H'
        })

        # System-specific center elements
        if 'center_core_walls' in wall_lf:
            core_wall_sf = garage.center_core_wall_sf
            core_lf = wall_lf['center_core_walls']['lf']
            core_height = wall_lf['center_core_walls']['height_ft']
            walls_items.append({
                'component': 'Center Core Walls (12" concrete)',
                'quantity': core_wall_sf,
                'unit': 'SF',
                'unit_cost': wall_cost_sf,
                'total': core_wall_sf * wall_cost_sf,
                'notes': f'{core_lf:.0f} LF × {core_height:.1f}\' H (split-level 2-bay)'
            })

            # Center curbs
            curb_cost_cy = self.component_costs['curb_8x12_cy']  # $650/CY (placeholder)
            curb_cy = garage.center_curb_concrete_cy
            curb_lf = wall_lf['center_curbs']['total_lf']
            walls_items.append({
                'component': 'Center Curbs (8" × 12")',
                'quantity': curb_cy,
                'unit': 'CY',
                'unit_cost': curb_cost_cy,
                'total': curb_cy * curb_cost_cy,
                'notes': f'{curb_lf:.0f} LF total (both sides × {garage.total_levels} levels)'
            })

        if 'ramp_barriers' in wall_lf:
            barrier_sf = garage.ramp_barrier_sf
            barrier_lf = wall_lf['ramp_barriers']['total_lf']
            barrier_thickness = wall_lf['ramp_barriers']['thickness_in']
            barrier_height = wall_lf['ramp_barriers']['height_in']

            # Calculate barrier cost (concrete + rebar)
            barrier_cy = garage.ramp_barrier_concrete_cy
            barrier_rebar_lbs = garage.ramp_barrier_rebar_lbs
            barrier_concrete_cost = barrier_cy * self._get_wall_12in_cost_per_cy()  # Placeholder - TODO: Extract from PDF
            barrier_rebar_cost = barrier_rebar_lbs * rebar_cost
            barrier_total = barrier_concrete_cost + barrier_rebar_cost
            barrier_cost_sf = barrier_total / barrier_sf if barrier_sf > 0 else 0

            walls_items.append({
                'component': f'Ramp Barriers ({barrier_height}" × {barrier_thickness}")',
                'quantity': barrier_sf,
                'unit': 'SF',
                'unit_cost': barrier_cost_sf,
                'total': barrier_total,
                'notes': f'{barrier_lf:.0f} LF total (split-level 3+ bay or single-ramp)'
            })

        # Top level barriers
        if hasattr(garage, 'top_level_barrier_12in_sf') and garage.top_level_barrier_12in_sf > 0:
            top_barrier_sf = garage.top_level_barrier_12in_sf
            walls_items.append({
                'component': 'Top Level Closure Walls (12")',
                'quantity': top_barrier_sf,
                'unit': 'SF',
                'unit_cost': wall_cost_sf,
                'total': top_barrier_sf * wall_cost_sf,
                'notes': 'North end termination'
            })

        # Elevator pit CMU (always - standard construction practice)
        cmu_sf = garage.elevator_pit_cmu_sf
        cmu_cost = self.costs['structure']['masonry_wall_8in_sf']
        walls_items.append({
            'component': 'Elevator Pit (8" CMU)',
            'quantity': cmu_sf,
            'unit': 'SF',
            'unit_cost': cmu_cost,
            'total': cmu_sf * cmu_cost,
            'notes': f'{elev_lf:.0f} LF × 8\' pit depth (CMU below concrete shaft)'
        })

        sections['05_walls_cores'] = {
            'title': '05 - STRUCTURE - WALLS & CORES',
            'items': walls_items,
            'total': sum(item['total'] for item in walls_items)
        }

        # ========== SECTION 6: VERTICAL TRANSPORTATION ==========
        vertical_items = []

        # Elevators
        elevator_stops = garage.num_elevator_stops
        elevator_cost_per_stop = self.component_costs['elevator_cost_per_stop']
        vertical_items.append({
            'component': 'Elevator',
            'quantity': elevator_stops,
            'unit': 'Stops',
            'unit_cost': elevator_cost_per_stop,
            'total': elevator_stops * elevator_cost_per_stop,
            'notes': f'{elevator_stops} stops (1 per level)'
        })

        # Stairs
        stair_flights = garage.num_stair_flights
        stair_cost_per_flight = self.component_costs['stair_flight_cost']
        vertical_items.append({
            'component': 'Stairs (Metal Pan)',
            'quantity': stair_flights,
            'unit': 'Flights',
            'unit_cost': stair_cost_per_flight,
            'total': stair_flights * stair_cost_per_flight,
            'notes': f'{stair_flights} flights ({garage.num_stairs} stairs × {garage.total_levels} levels × 2 flights/level)'
        })

        sections['06_vertical'] = {
            'title': '06 - VERTICAL TRANSPORTATION',
            'items': vertical_items,
            'total': sum(item['total'] for item in vertical_items)
        }

        # ========== SECTION 7: MEP SYSTEMS ==========
        mep_items = []

        total_gsf = garage.total_gsf

        # Fire protection
        fire_cost_sf = self.costs['mep']['fire_protection_parking_sf']
        mep_items.append({
            'component': 'Fire Protection (Sprinklers)',
            'quantity': total_gsf,
            'unit': 'SF',
            'unit_cost': fire_cost_sf,
            'total': total_gsf * fire_cost_sf,
            'notes': f'{total_gsf:,.0f} SF total GSF'
        })

        # Plumbing
        plumbing_cost_sf = self.costs['mep']['plumbing_parking_sf']
        mep_items.append({
            'component': 'Plumbing',
            'quantity': total_gsf,
            'unit': 'SF',
            'unit_cost': plumbing_cost_sf,
            'total': total_gsf * plumbing_cost_sf,
            'notes': 'Drains, domestic water'
        })

        # HVAC/Ventilation
        hvac_cost_sf = self.costs['mep']['hvac_parking_sf']
        mep_items.append({
            'component': 'HVAC/Ventilation',
            'quantity': total_gsf,
            'unit': 'SF',
            'unit_cost': hvac_cost_sf,
            'total': total_gsf * hvac_cost_sf,
            'notes': 'Exhaust fans, ductwork'
        })

        # Electrical/Lighting
        electrical_cost_sf = self.costs['mep']['electrical_parking_sf']
        mep_items.append({
            'component': 'Electrical/Lighting',
            'quantity': total_gsf,
            'unit': 'SF',
            'unit_cost': electrical_cost_sf,
            'total': total_gsf * electrical_cost_sf,
            'notes': 'Service, distribution, lighting'
        })

        sections['07_mep'] = {
            'title': '07 - MEP SYSTEMS',
            'items': mep_items,
            'total': sum(item['total'] for item in mep_items)
        }

        # ========== SECTION 8: EXTERIOR & FINISHES ==========
        exterior_items = []

        # Parking screen
        screen_sf = garage.exterior_wall_sf
        screen_cost_sf = self.costs['exterior']['parking_screen_sf']
        exterior_items.append({
            'component': 'Parking Screen (Brake Metal)',
            'quantity': screen_sf,
            'unit': 'SF',
            'unit_cost': screen_cost_sf,
            'total': screen_sf * screen_cost_sf,
            'notes': f'{garage.perimeter_lf:.0f} LF × 15\' H'
        })

        # Sealed concrete
        sealed_cost_sf = self.costs['site']['sealed_concrete_parking_sf']
        exterior_items.append({
            'component': 'Sealed Concrete Finish',
            'quantity': total_gsf,
            'unit': 'SF',
            'unit_cost': sealed_cost_sf,
            'total': total_gsf * sealed_cost_sf,
            'notes': 'All parking surfaces'
        })

        # Pavement markings
        total_stalls = garage.total_stalls
        marking_cost_per_stall = self.costs['site']['pavement_markings_per_stall']
        exterior_items.append({
            'component': 'Pavement Markings/Striping',
            'quantity': total_stalls,
            'unit': 'Stalls',
            'unit_cost': marking_cost_per_stall,
            'total': total_stalls * marking_cost_per_stall,
            'notes': f'{total_stalls} stall striping'
        })

        # Final cleaning
        cleaning_cost_sf = self.costs['site']['final_cleaning_parking_sf']
        exterior_items.append({
            'component': 'Final Cleaning',
            'quantity': total_gsf,
            'unit': 'SF',
            'unit_cost': cleaning_cost_sf,
            'total': total_gsf * cleaning_cost_sf,
            'notes': 'Post-construction cleanup'
        })

        sections['08_exterior_finishes'] = {
            'title': '08 - EXTERIOR & FINISHES',
            'items': exterior_items,
            'total': sum(item['total'] for item in exterior_items)
        }

        # ========== SECTION 9: LEVEL-BY-LEVEL SUMMARY ==========
        # This section uses level_data directly
        sections['09_level_summary'] = {
            'title': '09 - LEVEL-BY-LEVEL SUMMARY',
            'levels': level_data,
            'total_gsf': total_gsf,
            'total_stalls': total_stalls
        }

        return sections


def load_cost_database() -> Dict:
    """Load cost database from JSON"""
    data_dir = Path(__file__).parent.parent / 'data'
    with open(data_dir / 'cost_database.json', 'r') as f:
        return json.load(f)


if __name__ == "__main__":
    # Test cost calculator
    print("Testing cost calculator with baseline design...")

    from .geometry import SplitLevelParkingGarage

    # Create baseline garage (126' × 210', 2 bays, 5 floors above, 0 below)
    garage = SplitLevelParkingGarage(210, 5, 0)

    # Load costs and calculate
    cost_db = load_cost_database()
    calculator = CostCalculator(cost_db)
    breakdown = calculator.get_cost_breakdown_table(garage)

    # Display
    print("\n=== COST BREAKDOWN ===")
    print(json.dumps(breakdown, indent=2))

    # Validation
    expected_total = cost_db['base_design']['total_cost']
    calculated_total = breakdown['Total']
    error_pct = abs(calculated_total - expected_total) / expected_total * 100

    print(f"\n=== VALIDATION ===")
    print(f"Expected total: ${expected_total:,.0f}")
    print(f"Calculated total: ${calculated_total:,.0f}")
    print(f"Error: {error_pct:.1f}%")
    print(f"Match: {'✓' if error_pct < 10 else '✗'}")
