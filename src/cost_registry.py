"""
Cost Registry - Abstraction Layer for Cost Database

Provides validated, typed access to unit costs while hiding database structure.
This prevents code from breaking when cost database is reorganized.

KEY PRINCIPLE: Code asks for WHAT it needs (semantic names), not WHERE it lives (database paths).
"""

from dataclasses import dataclass
from typing import Dict, Optional, List
from enum import Enum


class CostUnit(Enum):
    """Standard units for construction costs"""
    CY = "cubic yard"
    SF = "square foot"
    LF = "linear foot"
    EA = "each"
    LB = "pound"
    TON = "ton"
    LS = "lump sum"


class CostCategory(Enum):
    """Cost categories for organization"""
    FOUNDATION = "foundation"
    STRUCTURE = "structure"
    EXCAVATION = "excavation"
    MEP = "mep"
    EXTERIOR = "exterior"
    SITE = "site"
    VERTICAL_CIRC = "vertical_circulation"
    SOFT_COSTS = "soft_costs"


@dataclass
class UnitCost:
    """
    A single unit cost with metadata

    Attributes:
        semantic_name: What this cost is (e.g., 'rebar')
        value: Cost in dollars
        unit: Unit of measure
        category: Cost category
        description: Human-readable description
        source: Where in database this comes from (for debugging)
    """
    semantic_name: str
    value: float
    unit: CostUnit
    category: CostCategory
    description: str
    source: str  # e.g., "unit_costs.structure.suspended_slab_8in_sf"

    def __str__(self) -> str:
        return f"{self.description}: ${self.value:.2f}/{self.unit.value}"


class CostRegistry:
    """
    Registry of all unit costs with validation

    This is the SINGLE SOURCE OF TRUTH for cost lookups.
    All cost access should go through this registry.

    Example:
        registry = CostRegistry(cost_database)
        rebar_cost = registry.get('rebar')  # Returns UnitCost object
        price = rebar_cost.value  # Access actual price
    """

    def __init__(self, cost_database: Dict):
        """
        Initialize registry from cost database

        Args:
            cost_database: Raw cost database dict loaded from JSON
        """
        self._db = cost_database
        self._costs = self._build_registry()
        self._validate()

    def _build_registry(self) -> Dict[str, UnitCost]:
        """
        Build flat registry from nested cost database

        This is where we map semantic names to database locations.
        When database structure changes, only THIS method needs updating.
        """
        costs = {}

        # FOUNDATION
        costs['footing_spread'] = UnitCost(
            semantic_name='footing_spread',
            value=self._db['unit_costs']['foundation']['footings_spot_cy'],
            unit=CostUnit.CY,
            category=CostCategory.FOUNDATION,
            description='Spread footings - concrete',
            source='unit_costs.foundation.footings_spot_cy'
        )

        costs['footing_continuous'] = UnitCost(
            semantic_name='footing_continuous',
            value=self._db['unit_costs']['foundation']['footings_continuous_cy'],
            unit=CostUnit.CY,
            category=CostCategory.FOUNDATION,
            description='Continuous footings - concrete',
            source='unit_costs.foundation.footings_continuous_cy'
        )

        costs['footing_excavation'] = UnitCost(
            semantic_name='footing_excavation',
            value=self._db['unit_costs']['foundation']['excavation_footings_cy'],
            unit=CostUnit.CY,
            category=CostCategory.FOUNDATION,
            description='Footing excavation',
            source='unit_costs.foundation.excavation_footings_cy'
        )

        costs['sog_5in'] = UnitCost(
            semantic_name='sog_5in',
            value=self._db['unit_costs']['structure']['slab_on_grade_5in_sf'],
            unit=CostUnit.SF,
            category=CostCategory.FOUNDATION,
            description='Slab on grade (5" thick)',
            source='unit_costs.structure.slab_on_grade_5in_sf'
        )

        costs['vapor_barrier'] = UnitCost(
            semantic_name='vapor_barrier',
            value=self._db['unit_costs']['structure']['vapor_barrier_sf'],
            unit=CostUnit.SF,
            category=CostCategory.FOUNDATION,
            description='Under-slab vapor barrier',
            source='unit_costs.structure.vapor_barrier_sf'
        )

        costs['gravel_4in'] = UnitCost(
            semantic_name='gravel_4in',
            value=self._db['unit_costs']['structure']['under_slab_gravel_sf'],
            unit=CostUnit.SF,
            category=CostCategory.FOUNDATION,
            description='Under-slab gravel (4" thick)',
            source='unit_costs.structure.under_slab_gravel_sf'
        )

        # EXCAVATION
        costs['mass_excavation'] = UnitCost(
            semantic_name='mass_excavation',
            value=self._db['unit_costs']['below_grade_premiums']['mass_excavation_3_5ft_cy'],
            unit=CostUnit.CY,
            category=CostCategory.EXCAVATION,
            description='Mass excavation',
            source='unit_costs.below_grade_premiums.mass_excavation_3_5ft_cy'
        )

        costs['export'] = UnitCost(
            semantic_name='export',
            value=self._db['unit_costs']['foundation']['export_excess_cy'],
            unit=CostUnit.CY,
            category=CostCategory.EXCAVATION,
            description='Export/haul-off',
            source='unit_costs.foundation.export_excess_cy'
        )

        costs['structural_fill'] = UnitCost(
            semantic_name='structural_fill',
            value=self._db['unit_costs']['below_grade_premiums']['import_structural_fill_cy'],
            unit=CostUnit.CY,
            category=CostCategory.EXCAVATION,
            description='Structural fill (import)',
            source='unit_costs.below_grade_premiums.import_structural_fill_cy'
        )

        costs['retaining_wall'] = UnitCost(
            semantic_name='retaining_wall',
            value=self._db['unit_costs']['below_grade_premiums']['retaining_wall_cw12_sf'],
            unit=CostUnit.SF,
            category=CostCategory.EXCAVATION,
            description='Retaining walls (12" concrete)',
            source='unit_costs.below_grade_premiums.retaining_wall_cw12_sf'
        )

        # STRUCTURE
        costs['slab_pt_8in'] = UnitCost(
            semantic_name='slab_pt_8in',
            value=self._db['unit_costs']['structure']['suspended_slab_8in_sf'],
            unit=CostUnit.SF,
            category=CostCategory.STRUCTURE,
            description='Suspended PT slab (8" thick)',
            source='unit_costs.structure.suspended_slab_8in_sf'
        )

        costs['column_18x24'] = UnitCost(
            semantic_name='column_18x24',
            value=self._db['unit_costs']['structure']['columns_18x24_cy'],
            unit=CostUnit.CY,
            category=CostCategory.STRUCTURE,
            description='Columns (18" × 24")',
            source='unit_costs.structure.columns_18x24_cy'
        )

        costs['concrete_pumping'] = UnitCost(
            semantic_name='concrete_pumping',
            value=self._db['unit_costs']['structure']['concrete_pumping_cy'],
            unit=CostUnit.CY,
            category=CostCategory.STRUCTURE,
            description='Concrete pumping',
            source='unit_costs.structure.concrete_pumping_cy'
        )

        costs['core_wall_12in'] = UnitCost(
            semantic_name='core_wall_12in',
            value=self._db['component_specific_costs']['core_wall_12in_cost_per_sf'],
            unit=CostUnit.SF,
            category=CostCategory.STRUCTURE,
            description='Core walls (12" concrete, all-in)',
            source='component_specific_costs.core_wall_12in_cost_per_sf'
        )

        costs['curb_8x12'] = UnitCost(
            semantic_name='curb_8x12',
            value=self._db['component_specific_costs']['curb_8x12_cy'],
            unit=CostUnit.CY,
            category=CostCategory.STRUCTURE,
            description='Concrete curbs (8" × 12", placeholder)',
            source='component_specific_costs.curb_8x12_cy'
        )

        # REBAR
        costs['rebar'] = UnitCost(
            semantic_name='rebar',
            value=self._db['component_specific_costs']['rebar_cost_per_lb'],
            unit=CostUnit.LB,
            category=CostCategory.STRUCTURE,
            description='Reinforcing steel',
            source='component_specific_costs.rebar_cost_per_lb'
        )

        costs['post_tension'] = UnitCost(
            semantic_name='post_tension',
            value=self._db['unit_costs']['structure']['post_tension_cables_lbs'],
            unit=CostUnit.LB,
            category=CostCategory.STRUCTURE,
            description='Post-tensioning cables',
            source='unit_costs.structure.post_tension_cables_lbs'
        )

        # VERTICAL CIRCULATION
        costs['elevator'] = UnitCost(
            semantic_name='elevator',
            value=self._db['component_specific_costs']['elevator_cost_per_stop'],
            unit=CostUnit.EA,
            category=CostCategory.VERTICAL_CIRC,
            description='Elevator cost per stop',
            source='component_specific_costs.elevator_cost_per_stop'
        )

        costs['stair'] = UnitCost(
            semantic_name='stair',
            value=self._db['component_specific_costs']['stair_flight_cost'],
            unit=CostUnit.EA,
            category=CostCategory.VERTICAL_CIRC,
            description='Stair flight cost',
            source='component_specific_costs.stair_flight_cost'
        )

        # MEP
        costs['electrical'] = UnitCost(
            semantic_name='electrical',
            value=self._db['unit_costs']['mep']['electrical_parking_sf'],
            unit=CostUnit.SF,
            category=CostCategory.MEP,
            description='Electrical systems (parking)',
            source='unit_costs.mep.electrical_parking_sf'
        )

        costs['hvac'] = UnitCost(
            semantic_name='hvac',
            value=self._db['unit_costs']['mep']['hvac_parking_sf'],
            unit=CostUnit.SF,
            category=CostCategory.MEP,
            description='HVAC systems (parking)',
            source='unit_costs.mep.hvac_parking_sf'
        )

        costs['plumbing'] = UnitCost(
            semantic_name='plumbing',
            value=self._db['unit_costs']['mep']['plumbing_parking_sf'],
            unit=CostUnit.SF,
            category=CostCategory.MEP,
            description='Plumbing systems (parking)',
            source='unit_costs.mep.plumbing_parking_sf'
        )

        costs['fire_protection'] = UnitCost(
            semantic_name='fire_protection',
            value=self._db['unit_costs']['mep']['fire_protection_parking_sf'],
            unit=CostUnit.SF,
            category=CostCategory.MEP,
            description='Fire protection systems (parking)',
            source='unit_costs.mep.fire_protection_parking_sf'
        )

        # EXTERIOR
        costs['parking_screen'] = UnitCost(
            semantic_name='parking_screen',
            value=self._db['unit_costs']['exterior']['parking_screen_sf'],
            unit=CostUnit.SF,
            category=CostCategory.EXTERIOR,
            description='Parking screen (brake metal)',
            source='unit_costs.exterior.parking_screen_sf'
        )

        # SITE FINISHES
        costs['sealed_concrete'] = UnitCost(
            semantic_name='sealed_concrete',
            value=self._db['unit_costs']['site']['sealed_concrete_parking_sf'],
            unit=CostUnit.SF,
            category=CostCategory.SITE,
            description='Sealed concrete finish',
            source='unit_costs.site.sealed_concrete_parking_sf'
        )

        costs['pavement_markings'] = UnitCost(
            semantic_name='pavement_markings',
            value=self._db['unit_costs']['site']['pavement_markings_per_stall'],
            unit=CostUnit.EA,
            category=CostCategory.SITE,
            description='Pavement markings per stall',
            source='unit_costs.site.pavement_markings_per_stall'
        )

        costs['final_cleaning'] = UnitCost(
            semantic_name='final_cleaning',
            value=self._db['unit_costs']['site']['final_cleaning_parking_sf'],
            unit=CostUnit.SF,
            category=CostCategory.SITE,
            description='Final cleaning',
            source='unit_costs.site.final_cleaning_parking_sf'
        )

        # SOFT COSTS (percentages)
        costs['cm_fee_pct'] = UnitCost(
            semantic_name='cm_fee_pct',
            value=self._db['soft_costs_percentages']['cm_fee'],
            unit=CostUnit.LS,  # Percentage treated as lump sum fraction
            category=CostCategory.SOFT_COSTS,
            description='CM fee percentage',
            source='soft_costs_percentages.cm_fee'
        )

        costs['insurance_pct'] = UnitCost(
            semantic_name='insurance_pct',
            value=self._db['soft_costs_percentages']['insurance'],
            unit=CostUnit.LS,
            category=CostCategory.SOFT_COSTS,
            description='Insurance percentage',
            source='soft_costs_percentages.insurance'
        )

        costs['contingency_pct'] = UnitCost(
            semantic_name='contingency_pct',
            value=self._db['soft_costs_percentages']['contingency_cm'] +
                  self._db['soft_costs_percentages']['contingency_design'],
            unit=CostUnit.LS,
            category=CostCategory.SOFT_COSTS,
            description='Contingency percentage (CM + design)',
            source='soft_costs_percentages.contingency_cm + contingency_design'
        )

        # GENERAL CONDITIONS
        costs['gc_monthly_rate'] = UnitCost(
            semantic_name='gc_monthly_rate',
            value=self._db['component_specific_costs']['general_conditions_per_month'],
            unit=CostUnit.EA,
            category=CostCategory.SOFT_COSTS,
            description='General conditions monthly rate',
            source='component_specific_costs.general_conditions_per_month'
        )

        return costs

    def _validate(self):
        """Validate that all expected costs are present"""
        required = [
            'footing_spread', 'footing_continuous', 'sog_5in', 'vapor_barrier', 'gravel_4in',
            'mass_excavation', 'export', 'structural_fill', 'retaining_wall',
            'slab_pt_8in', 'column_18x24', 'concrete_pumping', 'core_wall_12in', 'curb_8x12',
            'rebar', 'post_tension',
            'elevator', 'stair',
            'electrical', 'hvac', 'plumbing', 'fire_protection',
            'parking_screen',
            'sealed_concrete', 'pavement_markings', 'final_cleaning',
            'cm_fee_pct', 'insurance_pct', 'contingency_pct', 'gc_monthly_rate'
        ]

        missing = [name for name in required if name not in self._costs]
        if missing:
            raise ValueError(f"Cost registry validation failed. Missing costs: {missing}")

    def get(self, semantic_name: str) -> UnitCost:
        """
        Get unit cost by semantic name

        Args:
            semantic_name: Semantic name (e.g., 'rebar', 'elevator')

        Returns:
            UnitCost object

        Raises:
            KeyError: If cost not found
        """
        if semantic_name not in self._costs:
            available = ', '.join(list(self._costs.keys())[:10])
            raise KeyError(
                f"Cost '{semantic_name}' not found in registry. "
                f"Available costs: {available}... (use list_costs() for full list)"
            )
        return self._costs[semantic_name]

    def list_costs(self, category: Optional[CostCategory] = None) -> List[UnitCost]:
        """
        List all costs, optionally filtered by category

        Args:
            category: Optional category filter

        Returns:
            List of UnitCost objects
        """
        costs = list(self._costs.values())
        if category:
            costs = [c for c in costs if c.category == category]
        return sorted(costs, key=lambda c: c.semantic_name)

    def __repr__(self) -> str:
        return f"CostRegistry({len(self._costs)} costs loaded)"
