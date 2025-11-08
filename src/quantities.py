"""
Quantity Takeoff Data Structures

Separates pure geometric/structural quantities from costing logic.
All quantities are calculated by the garage geometry engine.

KEY PRINCIPLE: Quantities are DESCRIPTIVE (what exists), not PRESCRIPTIVE (what it costs).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from enum import Enum


class SlabType(Enum):
    """Slab construction type"""
    SOG = "slab_on_grade"
    SUSPENDED_PT = "suspended_pt"


@dataclass
class LevelQuantities:
    """Quantities for a single parking level"""
    level_name: str
    level_index: int
    elevation_ft: float
    gross_floor_area_sf: float
    slab_type: SlabType
    stall_count: int
    is_below_grade: bool
    is_entry_level: bool
    is_top_level: bool


@dataclass
class FoundationQuantities:
    """Foundation and below-grade quantities"""
    # All required fields first (no defaults)
    sog_area_sf: float
    vapor_barrier_sf: float
    gravel_4in_sf: float
    spread_footing_count: int
    spread_footing_concrete_cy: float
    spread_footing_rebar_lbs: float
    spread_footing_excavation_cy: float
    continuous_footing_length_ft: float
    continuous_footing_concrete_cy: float
    continuous_footing_rebar_lbs: float
    continuous_footing_excavation_cy: float
    has_retaining_walls: bool
    retaining_wall_sf: float
    retaining_wall_footing_concrete_cy: float
    retaining_wall_footing_rebar_lbs: float

    # Optional fields with defaults last
    sog_thickness_in: float = 5.0
    spread_footings_by_type: Dict[str, int] = field(default_factory=dict)
    continuous_footings_by_location: List[Dict] = field(default_factory=list)


@dataclass
class ExcavationQuantities:
    """Earthwork and excavation quantities"""
    has_below_grade: bool
    depth_below_grade_ft: float
    mass_excavation_cy: float
    over_excavation_cy: float
    export_cy: float
    structural_fill_cy: float


@dataclass
class StructuralQuantities:
    """Structural concrete and reinforcement quantities"""
    # All required fields first
    suspended_slab_area_sf: float
    suspended_slab_concrete_cy: float
    column_count: int
    column_size_in: Tuple[int, int]
    column_grid_spacing_ft: int
    column_total_height_ft: float
    column_concrete_cy: float
    elevator_shaft_sf: float
    elevator_shaft_concrete_cy: float
    stair_enclosure_count: int
    stair_enclosure_sf: float
    stair_enclosure_concrete_cy: float
    utility_closet_sf: float
    utility_closet_concrete_cy: float
    storage_closet_sf: float
    storage_closet_concrete_cy: float
    rebar_slabs_lbs: float
    rebar_columns_lbs: float
    rebar_walls_lbs: float
    rebar_footings_lbs: float
    total_rebar_lbs: float
    post_tension_lbs: float
    concrete_pumping_cy: float

    # Optional fields with defaults
    suspended_slab_thickness_in: float = 8.0
    elevator_pit_cmu_sf: float = 0.0
    elevator_pit_cmu_cy: float = 0.0


@dataclass
class CenterElementQuantities:
    """Center elements (ramp system dependent)"""
    # All required fields first
    has_core_walls: bool
    has_center_curbs: bool
    has_ramp_barriers: bool
    has_top_barrier: bool

    # Optional fields with defaults
    core_wall_sf: float = 0.0
    core_wall_concrete_cy: float = 0.0
    core_wall_length_ft: float = 0.0
    center_curb_concrete_cy: float = 0.0
    center_curb_sf: float = 0.0
    center_curb_total_lf: float = 0.0
    ramp_barrier_sf: float = 0.0
    ramp_barrier_concrete_cy: float = 0.0
    ramp_barrier_rebar_lbs: float = 0.0
    ramp_barrier_total_lf: float = 0.0
    top_barrier_sf: float = 0.0
    top_barrier_concrete_cy: float = 0.0


@dataclass
class VerticalCirculationQuantities:
    """Elevators and stairs"""
    elevator_stop_count: int
    stair_count: int
    stair_flight_count: int


@dataclass
class ExteriorQuantities:
    """Exterior enclosure"""
    parking_screen_sf: float
    perimeter_lf: float
    screen_height_ft: float


@dataclass
class MEPQuantities:
    """MEP systems (area-based)"""
    total_gsf: float
    electrical_sf: float
    hvac_sf: float
    plumbing_sf: float
    fire_protection_sf: float


@dataclass
class SiteFinishesQuantities:
    """Site and finish work"""
    sealed_concrete_sf: float
    pavement_marking_stall_count: int
    final_cleaning_sf: float


@dataclass
class QuantityTakeoff:
    """
    Complete quantity takeoff for parking garage

    This is the PRIMARY data structure for geometric quantities.
    All quantities are calculated by the garage geometry engine.
    Costing logic operates on THIS structure, not on garage internals.
    """
    # Project metadata
    building_length_ft: float
    building_width_ft: float
    footprint_sf: float
    num_bays: int
    total_height_ft: float
    ramp_system_name: str
    building_type: str

    # Parking metrics
    total_stalls: int
    total_gsf: float
    sf_per_stall: float

    # Level-by-level breakdown
    levels: List[LevelQuantities]

    # Component quantities
    foundation: FoundationQuantities
    excavation: ExcavationQuantities
    structure: StructuralQuantities
    center_elements: CenterElementQuantities
    vertical_circulation: VerticalCirculationQuantities
    exterior: ExteriorQuantities
    mep: MEPQuantities
    site_finishes: SiteFinishesQuantities

    def validate(self) -> List[str]:
        """
        Validate quantity takeoff for consistency

        Returns:
            List of validation warnings/errors (empty if valid)
        """
        issues = []

        # Check stall efficiency
        if self.sf_per_stall < 300:
            issues.append(f"SF/stall very low ({self.sf_per_stall:.0f}), expected 350-450")
        elif self.sf_per_stall > 500:
            issues.append(f"SF/stall very high ({self.sf_per_stall:.0f}), expected 350-450")

        # Check level count
        if len(self.levels) == 0:
            issues.append("No levels defined")

        # Check GSF consistency
        level_gsf_sum = sum(level.gross_floor_area_sf for level in self.levels)
        if abs(level_gsf_sum - self.total_gsf) > 1.0:
            issues.append(f"Level GSF sum ({level_gsf_sum:.0f}) != total_gsf ({self.total_gsf:.0f})")

        # Check stall count consistency
        level_stalls_sum = sum(level.stall_count for level in self.levels)
        if level_stalls_sum != self.total_stalls:
            issues.append(f"Level stalls sum ({level_stalls_sum}) != total_stalls ({self.total_stalls})")

        return issues

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        from dataclasses import asdict
        return asdict(self)
