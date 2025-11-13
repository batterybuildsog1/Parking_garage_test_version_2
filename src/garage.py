"""
Geometry engine for parking garages (split-level and single-ramp)

Handles parametric calculations for:
- Building dimensions and footprint
- Discrete floor area calculations (GSF per level)
- Parking stall counts using 2D spatial layout
- Structural quantities (concrete, rebar, PT cables)
- Excavation and foundation requirements

KEY FEATURE: Discrete Level Floor Areas
Each level (P0.5, P1, P1.5, etc.) has individually calculated Gross Floor Area (GSF):
- Half-levels (P1.5, P2.5, etc.): ~50% of footprint due to helical ramp geometry
- Entry level (P0.5): Reduced by flat entry circulation (FLAT_ENTRY_LENGTH parameter)
- Top level (P5+): Reduced by ramp termination zones (RAMP_TERMINATION_LENGTH parameter)
- Full levels (P1, P2, etc.): 100% footprint

See DISCRETE_LEVELS_GUIDE.md for comprehensive documentation.

AUTHORITATIVE COLUMNS (updated):
- Columns are generated along stall/aisle boundaries and ramp centerlines with
  maximum 31' spans along length. This replaces any legacy uniform-grid logic.
- Center column synthesis for 3D has been removed; all columns come from the
  authoritative generator. Ramp edge barriers remain for visualization only.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import math

# Import from geometry package
from .geometry.parking_layout import ParkingLayout
from .geometry.level_calculator import DiscreteLevelCalculator
from .structure.column_generator import generate_columns
from .loads.tributary import compute_column_tributaries_and_loads
from .loads.tributary import compute_per_level_column_areas_and_loads
from .checks.punching import compute_slab_punching_for_level

# Explicit exports for external use
__all__ = [
    'SplitLevelParkingGarage',
    'ParkingLayout',
    'load_cost_database',
    'compute_width_ft',
    'ParkingGarage',
    'create_parking_garage'
]


class SplitLevelParkingGarage:
    """
    Parametric model of a split-level parking garage with variable width and length/height

    Key constraints:
    - Width varies by number of bays (2-7 bays supported)
    - Length can vary in 31' increments (structural bays) or 9' increments (stall optimization)
    - Split-level design with 5' vertical rise per half-level
    - Continuous ramping with parking on ramp sides
    - Core walls separate each ramp bay pair
    """

    # Fixed dimensions from TechRidge reference design
    # Width formula: 1' + 61'n + 3'(n-1) where n = num_bays
    STALL_WIDTH = 9  # feet (perpendicular to aisle)
    STALL_DEPTH = 18  # feet (parallel to aisle)
    DRIVE_AISLE_WIDTH = 25  # feet
    PARKING_MODULE_WIDTH = 61  # feet (18 + 25 + 18)
    CENTER_SPACING = 2  # feet (center divider = two 12" parking barriers, no curbs)
    # NOTE: Both systems use ramp edge barriers + center columns; no center walls
    EXTERIOR_WALL_THICKNESS = 1.0  # feet (12" exterior parking barrier thickness used in width)

    # Turn zone geometry at ramp ends
    # Physical layout at north/south ends where ramps reverse direction:
    #
    #  ┌─────────────────────────────────────────────┐
    #  │         30' Turning Radius                   │  ← Cars make 180° turn
    #  │    (circular path for direction reversal)    │
    #  ├─────────────────────────────────────────────┤
    #  │         18' End Parking                      │  ← Angled stalls in turn zone
    #  │    (parking stalls within turn area)         │
    #  └─────────────────────────────────────────────┘
    #       Total: 48' depth per turn zone
    #
    # USER ADJUSTABLE: Site constraints may require different turning radii
    TURN_ZONE_DEPTH_TOTAL = 48  # feet (total depth at each ramp end)
    TURN_ZONE_TURNING_RADIUS = 30  # feet (minimum for 180° turn at 5% slope)
    TURN_ZONE_PARKING_DEPTH = 18  # feet (end parking stalls within turn zone)
    TURN_ZONE_DEPTH = TURN_ZONE_DEPTH_TOTAL  # feet (legacy compatibility)

    # Vertical
    FLOOR_TO_FLOOR = 10.656  # feet per level (10' 7-7/8" from drawings)
    RAMP_SLOPE = 0.05  # 5% slope

    # Cores (fixed layout: elevator+stair, stair, storage, utility)
    CORE_STALL_LOSS_PER_LEVEL = 7  # stalls lost to vertical cores per level

    # Structural grid
    PRIMARY_BAY_SPACING = 31  # feet

    # Height constraints
    DEFAULT_MAX_HEIGHT = 55  # feet (typical maximum for parking garage)
    LEVEL_HEIGHT = 10.5  # feet per level (5% ramp over typical 210' length)

    # Entry/exit ramp dimensions
    # Entry level (P0.5) has reduced usable area due to flat entry/exit circulation
    # Ramps must stay flat near street access before beginning climb
    # Typical reductions: entry vestibule, elevator lobby, stair access, traffic queuing
    #
    # USER ADJUSTABLE based on:
    # - Site access constraints (street connection, curb cuts)
    # - Building program (lobby size, elevator count, amenity access)
    # - Traffic flow requirements (entry lanes, payment systems)
    ENTRY_WIDTH = 27  # feet (entry opening width on west side)
    FLAT_ENTRY_LENGTH = 100  # feet (flat circulation before ramp begins - DEFAULT)

    # Top floor ramp termination
    # Ramps must terminate with flat zones for safety and code compliance
    # Top level (P5, P6, etc.) has reduced area due to ramp demise zones
    # Typical constraints: mechanical equipment, roof access, solar panels, parapet edge
    #
    # USER ADJUSTABLE based on:
    # - Rooftop equipment placement (HVAC, generators, transformers)
    # - Architectural requirements (roof access, maintenance areas)
    # - Structural design (ramp termination details)
    #
    # NOTE: Reference design shows ~54' per side; default 30' is conservative
    RAMP_TERMINATION_LENGTH = 48  # feet (flat zone where ramps end - aligned with turn zone depth)

    # Excavation design parameters (for below-grade construction)
    # These are design parameters, not site-specific. Actual depths should be verified by geotechnical engineer.
    OVER_EXCAVATION_DEPTH = 3.5  # feet - additional depth below foundation bottom for working room and drainage
    STRUCTURAL_FILL_DEPTH = 1.5  # feet - compacted engineered fill to restore grade and provide stable base

    def __init__(self, length: float, half_levels_above: int, half_levels_below: int, num_bays: int = 2,
                 max_height_ft: float = None,
                 soil_bearing_capacity: float = 3500,
                 fc: int = 4000,
                 load_factor_dl: float = 1.2,
                 load_factor_ll: float = 1.6,
                 allow_ll_reduction: bool = True,
                 continuous_footing_rebar_rate: float = 110.0,
                 spread_footing_rebar_rate: float = 65.0,
                 dead_load_psf: float = 115.0,
                 live_load_psf: float = 50.0,
                 ramp_system = None,
                 ramp_termination_length: float = None,
                 building_type: str = 'standalone'):
        """
        Initialize parking garage with given dimensions

        Args:
            length: Building length in feet (recommend 31' increments)
            half_levels_above: Number of parking levels above grade
                              SPLIT_LEVEL: half-levels (10 = P0.5 to P5)
                              SINGLE_RAMP: full floors (5 = P1 to P5)
            half_levels_below: Number of parking levels below grade
                              SPLIT_LEVEL: half-levels (4 = B-0.5, B-1, B-1.5, B-2)
                              SINGLE_RAMP: full floors (2 = B-1, B-2)
            num_bays: Number of ramp bays (2-7)
            max_height_ft: Maximum building height in feet (default: 55')
            soil_bearing_capacity: Allowable bearing pressure (PSF), default 2000
            fc: Concrete compressive strength (PSI), default 4000
            load_factor_dl: Dead load factor (ACI 318-19), default 1.2
            load_factor_ll: Live load factor (ACI 318-19), default 1.6
            allow_ll_reduction: Enable live load reduction, default False
            continuous_footing_rebar_rate: Reinforcement rate for continuous footings (lbs/CY), default 110
            spread_footing_rebar_rate: Reinforcement rate for spread footings (lbs/CY), default 65
            dead_load_psf: Dead load per square foot (PSF), default 115 (100 slab + 15 superimposed)
            live_load_psf: Live load per square foot (PSF), default 50 (parking per IBC 2021)
            ramp_system: RampSystemType (auto-detected if None based on length)
                        SPLIT_LEVEL_DOUBLE: two interleaved ramps (current)
                        SINGLE_RAMP_FULL: one ramp bay (new, requires length ≥250')
            building_type: 'standalone' or 'podium' (affects top-level barrier)
                        standalone: 3' perimeter barrier on top level (stand-alone garage)
                        podium: No top barrier (apartments/building sits on top)
        """
        from .geometry.design_modes import RampSystemType, get_ramp_config

        self.length = length
        self.num_bays = num_bays
        self.max_height_ft = max_height_ft if max_height_ft is not None else self.DEFAULT_MAX_HEIGHT

        # Auto-determine ramp system if not specified
        if ramp_system is None:
            self.ramp_system = RampSystemType.determine_optimal(length, num_bays)
        else:
            self.ramp_system = ramp_system

        # Get ramp configuration for this system
        ramp_config = get_ramp_config(self.ramp_system)
        self.floor_to_floor = ramp_config['floor_to_floor']
        self.level_height = ramp_config['level_height']
        self.ramp_slope = ramp_config['ramp_slope']
        self.is_half_level_system = ramp_config['is_half_level']
        # Centralized geometry parameters (instance overrides for consistency)
        self.TURN_ZONE_DEPTH = ramp_config.get('turn_zone_depth', getattr(self, 'TURN_ZONE_DEPTH', 48))
        self.ENTRY_WIDTH = ramp_config.get('entry_width', getattr(self, 'ENTRY_WIDTH', 27))
        self.FLAT_ENTRY_LENGTH = ramp_config.get('flat_entry_length', getattr(self, 'FLAT_ENTRY_LENGTH', 100))
        self.RAMP_TERMINATION_LENGTH = ramp_config.get('ramp_termination_length', getattr(self, 'RAMP_TERMINATION_LENGTH', 48))
        # Allow explicit override from caller
        if ramp_termination_length is not None:
            self.RAMP_TERMINATION_LENGTH = float(ramp_termination_length)

        # Store level counts (interpretation depends on ramp system)
        self.half_levels_above = half_levels_above
        self.half_levels_below = half_levels_below

        # Legacy aliases for backward compatibility
        self.levels_above = half_levels_above
        self.levels_below = half_levels_below

        # Store structural parameters for footing design
        self.soil_bearing_capacity = soil_bearing_capacity
        self.fc = fc
        self.load_factor_dl = load_factor_dl
        self.load_factor_ll = load_factor_ll
        self.allow_ll_reduction = allow_ll_reduction
        self.continuous_footing_rebar_rate = continuous_footing_rebar_rate
        self.spread_footing_rebar_rate = spread_footing_rebar_rate

        # Store load assumptions (PSF) - user-adjustable
        self.dead_load_psf = dead_load_psf
        self.live_load_psf = live_load_psf

        # Building type (affects top-level barrier)
        self.building_type = building_type

        # Calculate width: 1' + 61'n + 3'(n-1)
        # 2 bays: 1 + 122 + 3 = 126' ✓
        # 3 bays: 1 + 183 + 6 = 190'
        self.width = 1.0 + (num_bays * self.PARKING_MODULE_WIDTH) + ((num_bays - 1) * self.CENTER_SPACING)

        # Expose column spacing for tributary area calculations
        self.column_spacing_ft = self.PRIMARY_BAY_SPACING

        # Number of center lines = num_bays - 1 (now columns + beams, not solid walls)
        self.num_center_lines = num_bays - 1

        # Validate inputs
        self._validate_inputs()

        # Calculate derived properties
        self._calculate_geometry()
        self._calculate_stalls()
        self._calculate_structure()
        # Semi-full tributary rectangles and aggregate loads (before footings)
        self._calculate_tributaries()
        self._calculate_excavation()
        self._calculate_footings()
        self._calculate_backfill()
        self._calculate_elevator_pit_waterproofing()
        self._calculate_parking_equipment()

    def _validate_inputs(self):
        """Validate input parameters against design constraints"""
        if self.length < 150:
            raise ValueError(f"Length must be at least 150' (got {self.length}')")
        if self.length > 360:
            raise ValueError(f"Length should not exceed 360' (got {self.length}')")
        if self.half_levels_above < 2 or self.half_levels_above > 12:
            raise ValueError(f"Levels above must be 2-12 (got {self.half_levels_above})")
        if self.half_levels_below < 0 or self.half_levels_below > 6:
            raise ValueError(f"Levels below must be 0-6 (got {self.half_levels_below})")
        if self.num_bays < 2 or self.num_bays > 7:
            raise ValueError(f"Number of bays must be 2-7 (got {self.num_bays})")

        # Check height constraints (above-grade only for zoning/code)
        height_above = self.half_levels_above * self.level_height
        if height_above > self.max_height_ft:
            level_type = "half-levels" if self.is_half_level_system else "full floors"
            print(f"WARNING: Above-grade height {height_above:.1f}' exceeds maximum {self.max_height_ft}' "
                  f"({self.half_levels_above} {level_type} × {self.level_height:.2f}' = {height_above:.1f}')")

        # Warn if length is not on structural grid
        if self.length % self.PRIMARY_BAY_SPACING != 0:
            print(f"Warning: Length {self.length}' is not on 31' structural grid. " +
                  f"Recommend: {int(self.length / 31) * 31}' or {(int(self.length / 31) + 1) * 31}'")

    def _calculate_geometry(self):
        """Calculate basic geometric properties"""
        # Footprint
        self.footprint_sf = self.width * self.length

        # Building perimeter (for exterior screen/walls)
        # Full perimeter regardless of level geometry - screen wraps entire building
        self.perimeter_lf = 2 * (self.width + self.length)

        # Total levels for split-level ramp system:
        #
        # The half-levels (P2.5, P3.5, P4.5) are part of the ramp circulation system
        # but not counted as separate parking levels.
        #
        # Reference design (from TechRidge budget):
        # - "5 Parking Levels" = P0.5 (at-grade entry), P1, P2, P3, P4, P5
        # - This is: floors_above=5, floors_below=0
        # - Total parking levels = 6 named levels (P0.5, P1, P2, P3, P4, P5)
        #
        # For parametric scaling:
        # === GRADE AND ENTRY CONFIGURATION ===
        # CORRECT ARCHITECTURE:
        # - Entry is AT GRADE (elevation z=0) - vehicles drive in at street level
        # - From entry: turn LEFT to descend to below-grade half-levels
        # - From entry: turn RIGHT to ascend to above-grade half-levels
        # - Below-grade levels are ALSO half-levels (not full floors)
        #
        # Example (floors_below=2, floors_above=3):
        #   Below: B-1.5, B-1, B-0.5 (each ~50% of footprint)
        #   Entry: P0.5 at z=0' ← AT GRADE
        #   Above: P1, P1.5, P2, P2.5, P3 (each ~50% of footprint)
        #
        # Level indexing in self.levels list:
        #   Index 0: B-1.5 (bottom, if floors_below=2)
        #   Index 1: B-1
        #   Index 2: B-0.5
        #   Index 3: P0.5 ← ENTRY (at floors_below index)
        #   Index 4: P1
        #   ...

        # Street/grade elevation (reference point)
        self.street_elevation = 0.0

        # Half-level configuration:
        # Below-grade: half_levels_below (direct count)
        # Above-grade: half_levels_above (direct count)
        # IMPORTANT: Entry level is ONE OF the half-levels (not additional)

        # Total levels = count of functional parking elevations (half-levels)
        # In split-level architecture, each "level" represents an elevation where
        # a horizontal plane intersects the continuous helical ramps.
        # At any given level, approximately 50% of footprint has parking.
        # Example: 10 levels = P0.5, P1, P1.5, P2, P2.5, P3, P3.5, P4, P4.5, P5
        self.total_levels = self.half_levels_below + self.half_levels_above

        # Entry is at grade level (index = half_levels_below)
        # This is the transition point between below-grade and above-grade levels
        self.entry_level_index = self.half_levels_below

        # Grade level index (same as entry)
        self.grade_level_index = self.entry_level_index

        # Entry elevation is at street grade
        self.entry_elevation = self.street_elevation  # 0.0

        # Depth below grade (for excavation) = deepest level elevation
        # Use ramp-system-dependent level_height (not class constant)
        self.half_level_height = self.level_height
        self.depth_below_grade_ft = self.half_levels_below * self.half_level_height

        # Height above grade (for zoning and structural calculations)
        # This is the building height ABOVE street level
        self.height_above_grade_ft = self.half_levels_above * self.half_level_height

        # Total height (from bottom to top) - legacy compatibility
        # Note: This represents ABOVE-GRADE height for building code purposes
        # Below-grade depth is tracked separately in depth_below_grade_ft
        self.total_height_ft = self.height_above_grade_ft

        # === DISCRETE LEVEL AREA CALCULATION ===
        # CRITICAL: This replaces the old "net_area_per_level_sf" approach
        #
        # Split-level parking creates discrete parking decks at half-level increments.
        # Each half-level has approximately 50% of the footprint area (not 100%).
        #
        # Calculates GROSS floor area (GSF) per level - used for:
        # - MEP cost calculations (sum of all level GSF)
        # - Exterior cost calculations (sum of all level GSF)
        # - SF/stall and cost/SF metrics
        #
        # DOES NOT subtract core walls or circulation - uses full footprint proportions.
        # This is parametric and scales correctly for ANY geometry (2-7 bays, any length).
        #
        # Creates: self.levels (list), self.total_gsf, self.sog_levels_sf, self.suspended_levels_sf

        # Use DiscreteLevelCalculator instead of duplicated method
        # Pass ramp system configuration for proper level area calculations
        self.level_calculator = DiscreteLevelCalculator(
            footprint_sf=self.footprint_sf,
            width=self.width,
            length=self.length,
            half_levels_above=self.half_levels_above,
            half_levels_below=self.half_levels_below,
            entry_elevation=self.entry_elevation,
            ramp_system=self.ramp_system,
            floor_to_floor=self.floor_to_floor,
            level_height=self.level_height,
            ramp_termination_length=self.RAMP_TERMINATION_LENGTH
        )

        # Calculate all level areas
        self.levels, level_details = self.level_calculator.calculate_all_levels()

        # Extract calculated values for backward compatibility
        self.total_gsf = level_details['total_gsf']
        self.sog_levels_sf = level_details['sog_sf']
        self.suspended_levels_sf = level_details['suspended_sf']
        self.num_discrete_levels = level_details['num_levels']
        self.total_levels = self.num_discrete_levels

        # Straight section length (usable for parking along ramp sides)
        self.straight_section_length = self.length - (2 * self.TURN_ZONE_DEPTH)

        # === STRUCTURAL COLUMNS (authoritative generator) ===
        # Generate columns aligned to stall/aisle boundaries and ramp centerlines
        # with maximum spans of 31' along length; fixed sizes for now (changeable later).
        self.columns = generate_columns(self)

    def _calculate_tributaries(self):
        """
        Compute semi-full tributary rectangles, clip by cores/entry, and aggregate loads.
        Stores:
            - self.column_tributary: list of {x_left,x_right,y_bottom,y_top,area_sf,y_line_type}
            - self.column_loads: list of {dl_slab_total,ll_slab_total,column_self_weight,service_load,factored_load,eq_floors,ll_psf_effective}
        """
        tribs, loads = compute_column_tributaries_and_loads(self)
        self.column_tributary = tribs
        self.column_loads = loads
        # Per-level mapping (split-level first); single-ramp handled later
        per_col_levels, level_validation = compute_per_level_column_areas_and_loads(self)
        self.per_level_column_data = per_col_levels
        self.per_level_area_validation = level_validation
        # Slab punching per suspended level per column (stud rails only for slabs)
        slab_t_in = 8.0  # suspended slab thickness (inches)
        fc_psi = float(getattr(self, 'fc', 4000))
        stud_required_joints = 0
        for ci, col_levels in enumerate(self.per_level_column_data):
            col = self.columns[ci]
            ytype = col.get('y_line_type', 'interior')
            col_w_in = float(col.get('width_in', 18.0))
            col_d_in = float(col.get('depth_in', 24.0))
            for e in col_levels:
                if e.get('slab_type') != 'suspended':
                    continue
                factored = float(e.get('factored_lb', 0.0))
                res = compute_slab_punching_for_level(
                    fc_psi=fc_psi,
                    slab_thickness_in=slab_t_in,
                    column_width_in=col_w_in,
                    column_depth_in=col_d_in,
                    y_line_type=ytype,
                    column_x_ft=float(col['x']),
                    column_y_ft=float(col['y']),
                    building_length_ft=float(self.length),
                    building_width_ft=float(self.width),
                    factored_reaction_lb=factored
                )
                e.update({'punch_phi_vc_lb': res['phi_vc_lb'],
                          'punch_vu_lb': res['vu_lb'],
                          'punch_utilization': res['utilization'],
                          'stud_rails_required': res['requires_stud_rails']})
                if res['requires_stud_rails']:
                    stud_required_joints += 1
        self.stud_rail_required_joints = stud_required_joints

    def print_discrete_level_breakdown(self):
        """
        Print formatted breakdown of discrete level areas
        Delegates to DiscreteLevelCalculator for actual printing
        """
        # Delegate to the level calculator's print method
        self.level_calculator.print_level_breakdown(self.levels)

    def _calculate_stalls(self):
        """
        Calculate parking stalls - dispatch by ramp system

        Split-level: Zone attribution per half-level
        Single-ramp: Full floor attribution per level
        """
        if self.is_half_level_system:
            return self._calculate_stalls_split_level()
        else:
            return self._calculate_stalls_single_ramp()

    def _calculate_stalls_split_level(self):
        """
        Calculate parking stalls geometrically for EACH discrete half-level

        ZONE ATTRIBUTION APPROACH:
        Each half-level in the helical ramp gets specific portions of the parking zones:
        - 1 turn zone (alternating north/south as you ascend)
        - 1 ramp bay (full building length × half building width = 210' × 63')
          This includes: west or east perimeter row + 1 center row
        - Half of the center core parking (split between adjacent half-levels)

        This approach is robust because:
        - Works correctly for partial floors (entry has blockage, top has termination)
        - Adapts to geometry changes (more bays, longer length, smaller cores)
        - Reflects physical reality of split-level helical ramps
        - No brittle "divide by 2" logic needed

        Each level (P0.5, P1, P1.5, P2, ... P5.5) is calculated independently
        based on which physical zones exist at that elevation.
        """

        total_stalls = 0
        stalls_by_level = {}

        # Create a full-building layout for zone calculations
        # Use actual building dimensions (not effective_length from GSF)
        full_layout = ParkingLayout(self.width, self.length, self.num_bays, turn_zone_depth=self.TURN_ZONE_DEPTH)
        full_layout.apply_core_blockages()

        # Calculate stalls for each discrete half-level
        for level_index, (level_name, level_gsf, slab_type, elevation) in enumerate(self.levels):
            level_stalls = 0
            breakdown = {}

            # Determine level-specific blockages
            is_entry = (level_index == self.entry_level_index)
            is_top = (level_index == self.total_levels - 1)

            # === ZONE 1: Turn zone (alternating north/south) ===
            # Even-indexed levels get north turn, odd-indexed get south turn
            # This mimics the helical ramp ascending through the building
            turn_zone = 'north' if level_index % 2 == 0 else 'south'
            turn_stalls = full_layout.calculate_turn_zone_stalls(turn_zone)
            level_stalls += turn_stalls
            breakdown[f'{turn_zone}_turn'] = {'stalls': turn_stalls}

            # === ZONE 2: Ramp bay (one side of building - full length) ===
            # Alternating west/east bay as you ascend
            # Each bay includes: perimeter row (18' stall strip) + center row (18' stall strip)
            ramp_side = 'west' if level_index % 2 == 0 else 'east'

            # Get the perimeter row for this side
            perimeter_section = None
            for section in full_layout.sections:
                if section.name == f'{ramp_side}_row':
                    perimeter_section = section
                    break

            if perimeter_section:
                # Apply level-specific blockages to a copy
                temp_blockages = perimeter_section.blockages.copy()

                if is_entry and ramp_side == 'west':
                    # Entry opening on west side at mid-length
                    entry_center = self.length / 2
                    entry_half_width = self.ENTRY_WIDTH / 2
                    temp_blockages.append((entry_center - entry_half_width, entry_center + entry_half_width))

                if is_top:
                    # Ramp termination at north end
                    temp_blockages.append((0, self.RAMP_TERMINATION_LENGTH))

                # Calculate perimeter stalls with blockages
                available_length = perimeter_section.base_length
                for start_y, end_y in temp_blockages:
                    overlap_start = max(start_y, perimeter_section.y_start)
                    overlap_end = min(end_y, perimeter_section.y_end)
                    if overlap_end > overlap_start:
                        available_length -= (overlap_end - overlap_start)

                perimeter_stalls = int(available_length // 9)
                level_stalls += perimeter_stalls
                breakdown[f'{ramp_side}_row'] = {'stalls': perimeter_stalls}

            # === ZONE 3: Adjacent center row only (robust for ≥3 bays) ===
            if ramp_side == 'west':
                target_center = 'center_row_1_left'
            else:
                target_center = f'center_row_{self.num_bays - 1}_right'
            center_stalls = next(
                (section.calculate_stalls()[0] for section in full_layout.sections
                 if section.name == target_center),
                0
            )
            level_stalls += center_stalls
            breakdown[target_center] = {'stalls': center_stalls}

            # Store results for this level
            stalls_by_level[level_name] = {
                'stalls': int(level_stalls),
                'gsf': level_gsf,
                'zones': breakdown,
                'turn_zone': turn_zone,
                'ramp_side': ramp_side if 'ramp_side' in locals() else None
            }
            total_stalls += level_stalls

        # Store results
        self.total_stalls = int(total_stalls)
        self.stalls_by_level = stalls_by_level
        self.sf_per_stall = self.total_gsf / self.total_stalls if self.total_stalls > 0 else 0

    def _calculate_stalls_single_ramp(self):
        """
        Calculate parking stalls for single-ramp full-floor system

        FULL FLOOR ATTRIBUTION:
        Each full floor gets ALL parking zones at that elevation:
        - Both turn zones (north + south)
        - All flat bays (perimeter rows + center rows)
        - Ramp bay (parking on 6.67% slope with end barriers)

        Ramp bay configuration:
        - 18' parking + 25' aisle + 18' parking (all on slope)
        - 135' ramp length - 2×2.5' end barriers = 130' effective
        - 130' / 9' stall width × 2 sides = ~28 stalls per floor
        """

        total_stalls = 0
        stalls_by_level = {}

        # Create full-building layout (same as split-level)
        full_layout = ParkingLayout(self.width, self.length, self.num_bays, turn_zone_depth=self.TURN_ZONE_DEPTH)
        full_layout.apply_core_blockages()

        # Determine which bay is the ramp bay
        ramp_bay_index = self._determine_ramp_bay_index()

        # Calculate ramp geometry
        ramp_length = self.length - (2 * self.TURN_ZONE_DEPTH)  # Exclude turn zones
        ramp_end_barrier = 2.5  # feet per end (safety barrier at top/bottom of ramp)
        effective_ramp_length = ramp_length - (2 * ramp_end_barrier)

        # Calculate stalls for each full floor
        for level_index, (level_name, level_gsf, slab_type, elevation) in enumerate(self.levels):
            level_stalls = 0
            breakdown = {}

            # Determine level-specific blockages
            is_entry = (level_index == self.entry_level_index)
            is_top = (level_index == self.total_levels - 1)

            # === ZONE 1: Both turn zones (north AND south) ===
            # Full floors get both turn zones at same elevation
            north_stalls = full_layout.calculate_turn_zone_stalls('north')
            south_stalls = full_layout.calculate_turn_zone_stalls('south')
            level_stalls += north_stalls + south_stalls
            breakdown['north_turn'] = {'stalls': north_stalls}
            breakdown['south_turn'] = {'stalls': south_stalls}

            # === ZONE 2: Flat bays (all perimeter and center rows EXCEPT ramp bay) ===
            for section in full_layout.sections:
                # Skip turn zones (already counted) and ramp bay sections
                if section.section_type == 'turn_zone':
                    continue

                # Identify if this section is in the ramp bay
                is_ramp_bay_section = self._is_section_in_ramp_bay(section, ramp_bay_index)
                if is_ramp_bay_section:
                    continue  # Ramp bay calculated separately below

                # Calculate stalls for this flat section
                temp_blockages = section.blockages.copy()

                # Apply entry blockage (27' opening on west side at mid-length)
                if is_entry and section.name == 'west_row':
                    entry_center = self.length / 2
                    entry_half_width = self.ENTRY_WIDTH / 2
                    temp_blockages.append((entry_center - entry_half_width, entry_center + entry_half_width))

                # Apply top level ramp termination (north end)
                if is_top:
                    temp_blockages.append((0, self.RAMP_TERMINATION_LENGTH))

                # Calculate available length after blockages
                available_length = section.base_length
                for start_y, end_y in temp_blockages:
                    overlap_start = max(start_y, section.y_start)
                    overlap_end = min(end_y, section.y_end)
                    if overlap_end > overlap_start:
                        available_length -= (overlap_end - overlap_start)

                section_stalls = int(available_length // 9)
                level_stalls += section_stalls
                breakdown[section.name] = {'stalls': section_stalls}

            # === ZONE 3: Ramp bay (parking on slope) ===
            # Ramp bay has 2 sides of parking (18' + 25' aisle + 18')
            # Stalls run along the 130' effective ramp length
            ramp_stalls_per_side = int(effective_ramp_length // 9)
            ramp_stalls_total = ramp_stalls_per_side * 2
            level_stalls += ramp_stalls_total
            breakdown['ramp_bay'] = {
                'stalls': ramp_stalls_total,
                'per_side': ramp_stalls_per_side,
                'effective_length': effective_ramp_length
            }

            # Store results for this level
            stalls_by_level[level_name] = {
                'stalls': int(level_stalls),
                'gsf': level_gsf,
                'zones': breakdown,
                'ramp_bay_index': ramp_bay_index
            }
            total_stalls += level_stalls

        # Store results
        self.total_stalls = int(total_stalls)
        self.stalls_by_level = stalls_by_level
        self.sf_per_stall = self.total_gsf / self.total_stalls if self.total_stalls > 0 else 0

    def _determine_ramp_bay_index(self) -> int:
        """
        Determine which bay (1-indexed) contains the ramp

        Logic:
        - 2-bay: Bay 2 (east)
        - 3-bay: Bay 2 (center)
        - 4-bay: Bay 3 (east-of-center)
        - 5-bay: Bay 3 (center)
        - 6-bay: Bay 4 (east-of-center)
        - 7-bay: Bay 4 (center)

        Pattern: Prefer center bay, or east-of-center for even counts
        """
        if self.num_bays == 2:
            return 2  # East bay
        else:
            # For odd bays: true center = (n+1)/2
            # For even bays: east-of-center = n/2 + 1
            return (self.num_bays + 1) // 2 + (self.num_bays % 2 == 0)

    def _is_section_in_ramp_bay(self, section, ramp_bay_index: int) -> bool:
        """
        Determine if a parking section is within the ramp bay

        Args:
            section: ParkingSection instance
            ramp_bay_index: 1-indexed bay number containing ramp

        Returns:
            True if section is in ramp bay, False otherwise
        """
        # Ramp bay contains:
        # - For Bay N: Perimeter rows don't exist for interior bays
        # - Center rows flanking the ramp bay ARE in the ramp (on slope)

        # West and east perimeter rows are never in the ramp bay
        # (ramp bay is always an interior bay for 3+ bays, or east for 2-bay)
        if section.name in ['west_row', 'east_row']:
            # Special case: 2-bay system, ramp is in Bay 2 (east)
            if self.num_bays == 2 and ramp_bay_index == 2 and section.name == 'east_row':
                return True
            return False

        # Center rows: determine if they flank the ramp bay
        # Center rows are named: center_row_1_left, center_row_1_right, center_row_2_left, etc.
        # Each pair (left+right) corresponds to a divider between bays
        # For 3-bay: divider 1 is between Bay 1 and Bay 2, divider 2 is between Bay 2 and Bay 3
        #
        # Bay structure:
        # Bay N consists of: center_row_{N-1}_right + aisle + center_row_{N}_left
        #
        # For ramp in Bay 2 (3-bay):
        #   Bay 2 = center_row_1_right + aisle + center_row_2_left
        #   So we want divider 1 RIGHT and divider 2 LEFT

        if section.name.startswith('center_row_'):
            # Extract which divider and which side
            parts = section.name.split('_')
            if len(parts) >= 4:
                divider_index = int(parts[2])  # center_row_X_left/right
                side = parts[3]  # 'left' or 'right'

                # Ramp bay N contains:
                # - RIGHT side of divider (N-1)
                # - LEFT side of divider N
                if side == 'right' and divider_index == ramp_bay_index - 1:
                    return True
                if side == 'left' and divider_index == ramp_bay_index:
                    return True

        return False

    def _calculate_structure(self):
        """Calculate structural quantities using discrete component takeoffs"""
        # === COLUMNS (new authoritative model) ===
        # Columns generated at stall/aisle boundaries and ramp centerlines (≤31' spans)
        self.num_columns = len(getattr(self, 'columns', []))
        self.num_center_columns = sum(1 for c in self.columns if c.get('y_line_type') == 'ramp_center')
        self.num_perimeter_columns = sum(1 for c in self.columns if c.get('y_line_type') != 'ramp_center')

        # Column concrete volume (sum individual cross-sections × height)
        total_column_volume_cf = 0.0
        for c in self.columns:
            area_sf = (c['width_in'] / 12.0) * (c['depth_in'] / 12.0)
            total_column_volume_cf += area_sf * self.total_height_ft
        self.concrete_columns_cy = total_column_volume_cf / 27.0

        # Center column concrete (subset for potential reporting)
        center_column_volume_cf = 0.0
        for c in self.columns:
            if c.get('y_line_type') == 'ramp_center':
                area_sf = (c['width_in'] / 12.0) * (c['depth_in'] / 12.0)
                center_column_volume_cf += area_sf * self.total_height_ft
        self.center_column_concrete_cy = center_column_volume_cf / 27.0

        # === SLABS ===
        # Foundation slab on grade (5" thick)
        # CRITICAL: concrete_foundation_cy is ONLY the SOG (slab on grade), NOT footings!
        # Footings are calculated separately by FootingCalculator and stored in:
        #   - self.spread_footing_concrete_cy (under columns)
        #   - self.continuous_footing_concrete_cy (under core walls)
        #   - self.retaining_wall_footing_concrete_cy (perimeter, if below-grade)
        # This property should NEVER be used for footing rebar calculations.
        self.foundation_slab_sf = self.footprint_sf
        self.concrete_foundation_cy = (self.foundation_slab_sf * (5/12)) / 27  # SOG ONLY

        # Suspended PT slabs (8" thick)
        # Use discrete sum from actual level areas (not footprint × levels)
        self.suspended_slab_sf = self.suspended_levels_sf  # Already calculated in discrete levels
        self.concrete_slab_cy = (self.suspended_slab_sf * (8/12)) / 27

        # Total slab area (for PT cables)
        self.total_slab_sf = self.suspended_slab_sf

        # === VERTICAL CIRCULATION (Calculate before walls) ===
        # Stairs - calculate required count based on travel distance
        # Each level has 2 stair flights per stair (up and down)
        self.num_stairs = self._calculate_required_stair_count()
        self.num_stair_flights = self.total_levels * 2 * self.num_stairs  # 2 flights per level per stair

        # Elevator - one stop at each level
        self.num_elevator_stops = self.total_levels

        # === WALLS (Discrete Takeoffs) ===
        self._calculate_walls()

        # === TOTAL CONCRETE ===
        # Defensive: Use getattr for system-dependent variables
        center_core_wall_cy = getattr(self, 'center_core_wall_concrete_cy', 0)
        center_curb_cy = getattr(self, 'center_curb_concrete_cy', 0)
        perimeter_barrier_cy = getattr(self, 'perimeter_barrier_concrete_cy', 0)
        ramp_barrier_cy = getattr(self, 'ramp_barrier_concrete_cy', 0)

        self.total_concrete_cy = (self.concrete_slab_cy + self.concrete_foundation_cy +
                                  self.concrete_columns_cy +
                                  center_core_wall_cy + center_curb_cy +
                                  perimeter_barrier_cy + ramp_barrier_cy +
                                  self.elevator_shaft_concrete_cy + self.stair_enclosure_concrete_cy +
                                  self.utility_closet_concrete_cy + self.storage_closet_concrete_cy +
                                  self.elevator_pit_cmu_cy)

        # === REBAR ===
        # Will be calculated component-by-component in cost engine
        # Placeholder total for legacy compatibility
        self.total_rebar_lbs = self.total_concrete_cy * 65

        # === POST-TENSIONING ===
        # PT cables only on suspended slabs (not SOG)
        self.post_tension_lbs = self.suspended_slab_sf * 1.25

        # === EXTERIOR SCREEN ===
        # Brake metal parking screen (NOT structural walls)
        # Screen height from budget: 10,120 SF / 672 LF perimeter = 15 ft
        screen_height_ft = 15.0  # From budget calculation - brake metal coverage
        self.exterior_wall_sf = self.perimeter_lf * screen_height_ft

    def _calculate_walls(self):
        """
        Calculate structural elements - dispatch by ramp system

        Common elements (both systems):
        - Elevator shaft, stair enclosures, utility/storage closets

        System-specific elements:
        - Split-level: Ramp edge barriers (visual and safety separation at ramp bay centerlines)
        - Single-ramp: Ramp barriers on ramp-bay long edges (3+ bay)
        """
        # Calculate common core structures first
        self._calculate_core_structures()

        # Calculate system-specific center elements
        if self.is_half_level_system:
            self._calculate_split_level_center_elements()
        else:
            self._calculate_single_ramp_barriers()

    def _calculate_core_structures(self):
        """
        Calculate core building structures (common to both ramp systems)

        Core types:
        - Elevator shaft (12" concrete) - extends one level above top parking for mechanical
        - Stair enclosures (12" concrete) - extends one level above top parking for roof access
        - Utility closet (12" concrete) - only to top parking surface
        - Storage closet (12" concrete) - only to top parking surface
        - Elevator pit (8" CMU) - below grade only

        All wall SF calculations count BOTH FACES for forming costs.
        """

        # === ELEVATOR SHAFT ===
        # 12" concrete walls around shaft
        # Interior: 8' × 8' square
        # Pit: 8' below lowest parking level (CMU - calculated separately below)
        # Overhead: One FULL FLOOR above top parking level for mechanical equipment room
        # Note: In split-level, floor_to_floor = 10.656' (full floor), level_height = 5.328' (half-level)
        elevator_perimeter = 4 * 8  # 32 LF interior

        # Total height of CONCRETE shaft (pit is CMU, not concrete):
        # = (distance from bottom parking to top parking) + full_floor overhead
        # = (total_levels × level_height) + floor_to_floor
        # NOTE: Does NOT include 8' pit (that's CMU below)
        elevator_total_height = (self.total_levels * self.level_height) + self.floor_to_floor

        # Surface area (BOTH FACES for forming cost)
        # Interior and exterior surfaces must both be formed
        self.elevator_shaft_sf = elevator_perimeter * elevator_total_height * 2

        # Concrete volume (12" thick)
        self.elevator_shaft_concrete_cy = (self.elevator_shaft_sf * 1.0) / 27

        # === STAIR ENCLOSURES ===
        # 12" concrete walls around stair shafts
        # Footprint: 24' × 12' per stair
        # Perimeter: 2(24 + 12) = 72 LF per stair (4 sides enclosed)
        stair_perimeter_each = 72  # LF

        # Height from lowest parking level to roof access:
        # = (distance from bottom parking to top parking) + full_floor overhead
        # = (total_levels × level_height) + floor_to_floor
        # No pit for stairs (they sit on the slab)
        stair_height = (self.total_levels * self.level_height) + self.floor_to_floor

        # Surface area (BOTH FACES for forming cost, all stairs)
        # Interior and exterior surfaces must both be formed
        self.stair_enclosure_sf = self.num_stairs * stair_perimeter_each * stair_height * 2

        # Concrete volume (12" thick)
        self.stair_enclosure_concrete_cy = (self.stair_enclosure_sf * 1.0) / 27

        # === UTILITY CLOSET (NW Corner) ===
        # 20' × 19' with 4 concrete walls (12" thick)
        # Height: From lowest parking level to top parking surface (does not extend above)
        # = total_levels × level_height (bottom parking to top parking)
        utility_perimeter = 2 * (20 + 19)  # 78 LF
        utility_height = self.total_levels * self.level_height

        # Surface area (BOTH FACES for forming cost)
        self.utility_closet_sf = utility_perimeter * utility_height * 2
        self.utility_closet_concrete_cy = (self.utility_closet_sf * 1.0) / 27

        # === STORAGE CLOSET (SW Corner) ===
        # 29' × 18' with 4 concrete walls (12" thick)
        # Height: From lowest parking level to top parking surface (does not extend above)
        # = total_levels × level_height (bottom parking to top parking)
        storage_perimeter = 2 * (29 + 18)  # 94 LF
        storage_height = self.total_levels * self.level_height

        # Surface area (BOTH FACES for forming cost)
        self.storage_closet_sf = storage_perimeter * storage_height * 2
        self.storage_closet_concrete_cy = (self.storage_closet_sf * 1.0) / 27

        # === ELEVATOR PIT (ALWAYS CMU) ===
        # 8" CMU blocks for elevator pit walls
        # Standard construction practice: CMU pit below concrete shaft
        # Cheaper and easier than formed concrete for pit construction
        pit_perimeter = 32  # LF (same as shaft interior)
        pit_depth = 8  # feet

        # Surface area (CMU laid up, one face exposed)
        self.elevator_pit_cmu_sf = pit_perimeter * pit_depth

        # CMU volume (8" = 0.67 ft thick)
        self.elevator_pit_cmu_cy = (self.elevator_pit_cmu_sf * 0.67) / 27

    def _calculate_split_level_center_elements(self):
        """
        Calculate center elements for split-level double-ramp system
        
        UPDATED ARCHITECTURE:
        - No center core walls
        - No curbs
        - Use ramp edge barriers as the center divider:
          two 6" (0.5') thick barriers with a 1.0' clear gap = 2.0' total core width
        """

        # NO center core walls or curbs in updated model
        self.center_core_wall_sf = 0
        self.center_core_wall_concrete_cy = 0
        self.center_curb_concrete_cy = 0
        self.center_curb_sf = 0

        # === CENTER RAMP EDGE BARRIERS ===
        # Barriers run the full height of the parking structure as vertical separation.
        # Each barrier is 6" (0.5') thick with a 1.0' clear gap between them.
        barrier_height_ft = self.total_height_ft
        barrier_thickness_ft = 0.5  # 6" thick barriers
        barrier_length_per_edge = self.length
        num_ramp_edges = 2  # two barriers forming the 2.0' center divider

        # Surface area (both faces for forming cost)
        total_barrier_length = barrier_length_per_edge * num_ramp_edges
        self.ramp_barrier_sf = total_barrier_length * barrier_height_ft * 2

        # Concrete volume
        total_volume_cf = total_barrier_length * barrier_height_ft * barrier_thickness_ft
        self.ramp_barrier_concrete_cy = total_volume_cf / 27

        # Rebar (4.0 lbs/SF - standard wall rate)
        self.ramp_barrier_rebar_lbs = self.ramp_barrier_sf * 4.0

        # Primary variable names (for export and cost calculations)
        self.core_wall_area_sf = self.center_core_wall_sf
        self.concrete_core_wall_cy = self.center_core_wall_concrete_cy

        # NOTE: Core structures (elevator, stairs, utility, storage) calculated in _calculate_core_structures()

        # === TOP-LEVEL PERIMETER BARRIER (12" SHEARWALL CATEGORY) ===
        # 36" (3') concrete barrier around perimeter of TOP LEVEL ONLY
        # Per IBC 406.4.3: Vehicle barriers ≥33" where vertical drop >1'
        #
        # Protection strategy by level:
        # - Below-grade: Retaining walls serve as barriers
        # - Mid-levels: Parking screen (metal) serves as primary barrier
        # - Top level: Depends on building type:
        #   * Standalone garage: 3' concrete barrier (categorized as 12" shearwall)
        #   * Podium-style: No barrier (apartments/building sits on top)
        #
        # Cost: Categorized with 12" shearwalls at $28.50/SF
        # Counted on both faces for forming cost (consistent with all concrete walls)

        barrier_height_ft = 3.0  # 36" (exceeds 33" IBC minimum)
        barrier_thickness_ft = 0.5  # 6" typical

        # Only standalone garages need top-level concrete barrier
        if self.half_levels_above > 0 and self.building_type == 'standalone':
            # Full building perimeter: 2(L + W)
            full_perimeter_lf = 2 * (self.length + self.width)

            # Both faces for forming cost (consistent with all walls)
            self.top_level_barrier_12in_sf = full_perimeter_lf * barrier_height_ft * 2

            # Concrete volume
            self.top_level_barrier_concrete_cy = (
                full_perimeter_lf * barrier_height_ft * barrier_thickness_ft / 27
            )
        else:
            # Podium-style or no levels above grade
            self.top_level_barrier_12in_sf = 0
            self.top_level_barrier_concrete_cy = 0

        # No mid-level perimeter barriers (parking screen provides protection)
        self.perimeter_barrier_lf = 0
        self.perimeter_barrier_sf = 0
        self.perimeter_barrier_concrete_cy = 0

    def _calculate_single_ramp_barriers(self):
        """
        Calculate ramp barriers for single-ramp full-floor system

        CONFIGURATION-DEPENDENT LOGIC:

        2-BAY DESIGN:
        - Single ramp bay with parking on both sides of sloped aisle
        - Core wall on one long edge (separates from adjacent bay)
        - Exterior screen on other long edge
        - NO ramp edge barriers needed (core wall + screen handle both sides)

        3+ BAY DESIGN:
        - Single sloped ramp bay among multiple flat parking bays
        - Need barriers on BOTH long edges (parallel to building length)
        - Separate sloped ramp parking from flat parking in adjacent bays
        - Barriers run full building length × full height
        """

        # === SET SPLIT-LEVEL ELEMENTS TO ZERO ===
        # Single-ramp has NO center columns, core walls, or curbs (regardless of bay count)
        self.num_center_columns = 0
        self.center_column_concrete_cy = 0
        self.center_curb_concrete_cy = 0
        self.center_curb_sf = 0
        self.center_core_wall_sf = 0
        self.center_core_wall_concrete_cy = 0

        # Generic names for export (matches split-level pattern)
        self.core_wall_area_sf = self.center_core_wall_sf
        self.concrete_core_wall_cy = self.center_core_wall_concrete_cy

        # === RAMP EDGE BARRIERS (3+ BAY ONLY) ===
        if self.num_bays >= 3:
            # Need barriers on both long edges of ramp bay
            # Separate sloped ramp from flat parking bays

            barrier_height_ft = 3.0  # 36" (IBC minimum 33" - Section 406.4.3)
            barrier_thickness_ft = 0.5  # 6"
            barrier_length_per_edge = self.length  # Full building length
            num_barriers = 2  # Both long edges (west + east sides of ramp bay)

            # Surface area (both faces - counted for forming cost)
            total_barrier_length = barrier_length_per_edge * num_barriers
            self.ramp_barrier_sf = total_barrier_length * self.total_height_ft * 2  # Both faces

            # Concrete volume
            total_volume_cf = total_barrier_length * self.total_height_ft * barrier_thickness_ft
            self.ramp_barrier_concrete_cy = total_volume_cf / 27

            # Rebar (4.0 lbs/SF from cost database for walls)
            self.ramp_barrier_rebar_lbs = self.ramp_barrier_sf * 4.0

        else:  # 2-bay design
            # No ramp edge barriers - core wall + screen handle both edges
            self.ramp_barrier_sf = 0
            self.ramp_barrier_concrete_cy = 0
            self.ramp_barrier_rebar_lbs = 0

        # === TOP-LEVEL PERIMETER BARRIER (12" SHEARWALL CATEGORY) ===
        # Same as split-level: 3' barrier on top level only (standalone garages only)
        # Mid-levels protected by parking screen, not concrete barriers
        barrier_height_ft = 3.0  # 36"
        barrier_thickness_ft = 0.5  # 6"

        # Only standalone garages need top-level concrete barrier
        if len(self.levels) > 0 and self.building_type == 'standalone':
            # Full building perimeter: 2(L + W)
            full_perimeter_lf = 2 * (self.length + self.width)

            # Both faces for forming cost (consistent with all walls)
            self.top_level_barrier_12in_sf = full_perimeter_lf * barrier_height_ft * 2

            # Concrete volume
            self.top_level_barrier_concrete_cy = (
                full_perimeter_lf * barrier_height_ft * barrier_thickness_ft / 27
            )
        else:
            # Podium-style or no levels
            self.top_level_barrier_12in_sf = 0
            self.top_level_barrier_concrete_cy = 0

        # No mid-level perimeter barriers (parking screen provides protection)
        self.perimeter_barrier_lf = 0
        self.perimeter_barrier_sf = 0
        self.perimeter_barrier_concrete_cy = 0

    def _calculate_required_stair_count(self):
        """
        Calculate number of stairs for cost estimation

        Note: Stair count for CODE COMPLIANCE requires detailed egress analysis
        including actual stair placement, walking paths, and IBC Table 1017.2
        (S-2 open parking: 100' common path, 300' max travel, sprinklered).

        This method provides a COST ESTIMATE only, assuming 2 stairs minimum
        (typical for parking structures of this type).

        For actual code compliance, consult architect/code official.
        """
        # Default: 2 stairs (typical for parking podiums)
        # This is a placeholder for cost estimation, not code compliance calculation
        return 2

    def _calculate_excavation(self):
        """Calculate excavation quantities for below-grade construction"""
        if self.half_levels_below == 0:
            self.excavation_cy = 0
            self.export_cy = 0
            self.structural_fill_cy = 0
            self.retaining_wall_sf = 0
            return

        # Volume to excavate (footprint × depth)
        self.excavation_cy = (self.footprint_sf * self.depth_below_grade_ft) / 27

        # Over-excavation (using design parameter from class constants)
        self.over_excavation_cy = (self.footprint_sf * self.OVER_EXCAVATION_DEPTH) / 27

        # Export (assume all excavated material is hauled off)
        self.export_cy = self.excavation_cy + self.over_excavation_cy

        # Structural fill (import engineered fill material to restore grade)
        self.structural_fill_cy = (self.footprint_sf * self.STRUCTURAL_FILL_DEPTH) / 27

        # Retaining wall area (perimeter × depth)
        self.retaining_wall_sf = self.perimeter_lf * self.depth_below_grade_ft

    def _calculate_footings(self):
        """Calculate footing quantities and costs using FootingCalculator"""
        from .footing_calculator import FootingCalculator

        # Create footing calculator with structural parameters
        calc = FootingCalculator(
            self,
            soil_bearing_capacity=self.soil_bearing_capacity,
            fc=self.fc,
            load_factor_dl=self.load_factor_dl,
            load_factor_ll=self.load_factor_ll,
            allow_ll_reduction=self.allow_ll_reduction,
            continuous_footing_rebar_rate=self.continuous_footing_rebar_rate,
            spread_footing_rebar_rate=self.spread_footing_rebar_rate,
            dead_load_psf=self.dead_load_psf,
            live_load_psf=self.live_load_psf
        )

        # Calculate all footings
        results = calc.calculate_all_footings()

        # Store spread footing results
        spread = results['spread_footings']
        self.spread_footing_count = spread['total_count']
        self.spread_footing_count_by_type = spread['count_by_type']
        self.spread_footing_concrete_cy = spread['total_concrete_cy']
        # COST FLOW: spread_footing_rebar_lbs → cost_engine._calculate_foundation()
        # Calculated by FootingCalculator using ACI 318-19 flexure/shear design
        # Rate: 65 lbs/CY per TechRidge budget (different from continuous footings)
        self.spread_footing_rebar_lbs = spread['total_rebar_lbs']
        self.spread_footing_excavation_cy = spread['total_excavation_cy']
        self.spread_footings_by_type = spread['footings_by_type']

        # Store continuous footing results
        continuous = results['continuous_footings']
        self.continuous_footing_length_ft = continuous['total_length_ft']
        self.continuous_footing_concrete_cy = continuous['total_concrete_cy']
        # COST FLOW: continuous_footing_rebar_lbs → cost_engine._calculate_foundation()
        # Calculated by FootingCalculator using ACI 318-19 design for wall loads
        # Rate: 110 lbs/CY per TechRidge budget (higher than spread due to wall loads)
        self.continuous_footing_rebar_lbs = continuous['total_rebar_lbs']
        self.continuous_footing_excavation_cy = continuous['total_excavation_cy']
        self.continuous_footings = continuous['footings']

        # Store retaining wall footing results
        retaining = results['retaining_wall_footings']
        self.has_retaining_wall_footings = retaining['has_retaining_walls']
        self.retaining_wall_footing_concrete_cy = retaining['total_concrete_cy']
        # COST FLOW: retaining_wall_footing_rebar_lbs → cost_engine._calculate_foundation()
        # Calculated by FootingCalculator for cantilever retaining wall footings
        # Rate: 110 lbs/CY (same as continuous footings)
        # Only present if below-grade levels exist
        self.retaining_wall_footing_rebar_lbs = retaining['total_rebar_lbs']
        self.retaining_wall_footing_excavation_cy = retaining['total_excavation_cy']

        # Store totals
        totals = results['totals']
        self.total_footing_concrete_cy = totals['concrete_cy']
        self.total_footing_rebar_lbs = totals['rebar_lbs']
        self.total_footing_excavation_cy = totals['excavation_cy']

        # Prepare footings for visualization (outer + optional drop panel)
        self.footings_for_visualization = []
        for foot_list in self.spread_footings_by_type.values():
            for f in foot_list:
                entry = {
                    'x_center': f['x'],
                    'y_center': f['y'],
                    'outer_width_ft': f['width_ft'],
                    'outer_thickness_ft': f.get('depth_ft', f.get('outer_thickness_ft', 1.0)),
                    'two_depth': f.get('two_depth', False)
                }
                if f.get('two_depth', False):
                    entry.update({
                        'drop_width_x_ft': f['drop_width_x_ft'],
                        'drop_width_y_ft': f['drop_width_y_ft'],
                        'inner_thickness_ft': f['inner_thickness_ft']
                    })
                self.footings_for_visualization.append(entry)

        # Provide detailed footing data to cost engine for reporting
        self.footing_details = {
            'spread_footings': spread,
            'continuous_footings': continuous,
            'retaining_wall_footings': retaining
        }

    def _calculate_backfill(self):
        """
        Calculate backfill quantities for foundation and ramp

        FOUNDATION BACKFILL (Per-SF Temporary Proxy):
        - Backfill around footings after concrete placement
        - TODO: Replace with discrete per-footing calculation when TR provides:
          * Footing count by type (FS10.0, FS12.0, FC2.0, etc.)
          * Backfill volume per footing type
        - Current: 0.062 CY/SF empirical rate from TR budget
          (TR: 1,639.72 CY ÷ 26,460 SF parking footprint = 0.062)

        RAMP BACKFILL (Fixed Cost):
        - Entry ramp backfill (on compacted earth, not suspended)
        - Fixed at TR value: 2,397.33 CY per garage
        - NOTE: Ramps are generally same size, 1 per garage in current model
        - Will need adjustment if multiple ramps added or geometry changes
        """
        # Foundation backfill (per-SF proxy - will replace with discrete calc)
        BACKFILL_FOUNDATION_RATE_CY_PER_SF = 0.062  # CY per SF of SOG (from TR)
        self.backfill_foundation_cy = self.sog_levels_sf * BACKFILL_FOUNDATION_RATE_CY_PER_SF

        # Ramp backfill (fixed cost per garage)
        BACKFILL_RAMP_CY_PER_GARAGE = 2397.33  # From TR budget (1 ramp per garage)
        self.backfill_ramp_cy = BACKFILL_RAMP_CY_PER_GARAGE

    def _calculate_elevator_pit_waterproofing(self):
        """
        Calculate waterproofing SF for elevator pit surfaces touching earth

        SCOPE:
        - Pit floor (sits in earth below lowest level)
        - Pit exterior walls (8' deep into earth)
        - Uses EXTERIOR dimensions (interior + wall thickness)

        GEOMETRY:
        - Interior: 8' × 8' square (from line 811)
        - CMU thickness: 8" = 0.67'
        - Pit depth: 8' (from line 876)

        TR REFERENCE vs CALCULATED:
        - TR parking allocation: $9,614 ÷ $11/SF = 874 SF
        - Our geometric calc: ~386 SF (pit floor + walls only)
        - DISCREPANCY: 874 - 386 = 488 SF (~56% gap)
        - Likely includes: shaft walls below grade, approach slab, over-excavation
        - Using geometric calculation per component methodology
        """
        # Elevator interior dimensions (from _calculate_core_structure line 811)
        ELEVATOR_INTERIOR_FT = 8.0
        CMU_THICKNESS_FT = 0.67  # 8" CMU
        PIT_DEPTH_FT = 8.0

        # Exterior dimensions (for waterproofing on earth-facing side)
        exterior_dim_ft = ELEVATOR_INTERIOR_FT + 2 * CMU_THICKNESS_FT  # 9.34'
        exterior_perimeter_lf = 4 * exterior_dim_ft  # 37.36 LF

        # Waterproofing surfaces (pit only, not shaft above)
        pit_floor_sf = exterior_dim_ft * exterior_dim_ft  # 87 SF
        pit_walls_sf = exterior_perimeter_lf * PIT_DEPTH_FT  # 299 SF

        # Total (1 elevator for parking garage)
        self.elevator_pit_waterproofing_sf = pit_floor_sf + pit_walls_sf  # 386 SF

    def _calculate_parking_equipment(self):
        """
        Calculate parking equipment and site utilities

        FIXED ITEMS (1 per garage):
        - High-speed overhead door: Main entry gate (1 EA)
        - Oil/water separator: Stormwater treatment (1 EA)
        - Storm drain 48" ADS: Main collection (1 EA)

        SCALED ITEMS:
        - Storm drain junction boxes: 2 EA per garage (standard TR count)
        - Bicycle racks: 1 per 4 stalls (TR: 80 EA ÷ 319 stalls = 0.25)

        OPTIONAL ITEMS (not included by default, user toggle):
        - Parking canopies: Would be 12 EA for TR reference (amenity)

        TR REFERENCE:
        - High-speed overhead door: $36,000 (1 EA)
        - Oil/water separator: $13,500 (1 EA)
        - Storm drain 48" ADS: $5,960 parking allocation (1 EA)
        - Junction boxes 6'×6': $10,277 parking allocation (2 EA @ $12,500)
        - Bicycle racks: $42,000 (80 EA @ $525)
        """
        # Fixed items (1 per garage)
        self.high_speed_overhead_door_ea = 1  # Main entry gate
        self.oil_water_separator_ea = 1       # Stormwater treatment
        self.storm_drain_48in_ads_ea = 1      # Main drain collection

        # Scaled items
        self.storm_drain_junction_box_6x6_ea = 2  # Standard for parking garage

        # Bicycle racks: 1 per 4 stalls (TR ratio: 80 EA ÷ 319 stalls ≈ 0.25)
        BICYCLE_RACK_RATIO = 0.25  # 1 rack per 4 stalls
        self.bicycle_rack_ea = int(self.total_stalls * BICYCLE_RACK_RATIO)

        # Optional amenities (not included by default)
        # User can toggle these on via UI parameters in future
        # self.parking_canopy_ea = 0  # Would be 12 for TR reference size

    def get_level_name(self, level_index: int) -> str:
        """
        Get level name for given level index

        Delegates to level calculator's system-specific naming methods.

        Args:
            level_index: Level index (0 = deepest below-grade level)

        Returns:
            Level name (e.g., "Grade", "P1", "P1.5", "B-1", etc.)
        """
        if self.is_half_level_system:
            return self.level_calculator._get_level_name_split_level(level_index)
        else:
            return self.level_calculator._get_level_name_full_floor(level_index)

    def get_summary(self) -> Dict:
        """Return summary of garage characteristics"""
        self._calculate_excavation()  # Ensure excavation is calculated

        return {
            'dimensions': {
                'width_ft': self.width,
                'length_ft': self.length,
                'num_bays': self.num_bays,
                'num_center_lines': self.num_center_lines,
                'num_core_walls': self.num_center_lines,  # Legacy compatibility
                'footprint_sf': self.footprint_sf,
                'perimeter_lf': self.perimeter_lf,
                'total_height_ft': self.total_height_ft,
                'depth_below_grade_ft': self.depth_below_grade_ft
            },
            'levels': {
                'total_levels': self.total_levels,
                'half_levels_above': self.half_levels_above,
                'half_levels_below': self.half_levels_below,
                'num_discrete_levels': len(self.levels),
                'deepest_level': self.levels[0][0],
                'highest_level': self.levels[self.total_levels - 1][0],
                'entry_level': self.levels[self.entry_level_index][0]
            },
            'parking': {
                'total_stalls': self.total_stalls,
                'avg_stalls_per_level': round(self.total_stalls / self.total_levels, 1) if self.total_levels > 0 else 0,
                'sf_per_stall': round(self.sf_per_stall, 1),
                'stalls_by_level': self.stalls_by_level
            },
            'structure': {
                'num_columns': self.num_columns,
                'num_perimeter_columns': self.num_perimeter_columns,
                'num_center_columns': self.num_center_columns,
                'num_stair_flights': self.num_stair_flights,
                'num_elevator_stops': self.num_elevator_stops,
                'total_slab_sf': int(self.total_slab_sf),
                'total_concrete_cy': int(self.total_concrete_cy),
                'concrete_slabs_cy': int(self.concrete_slab_cy),
                'concrete_foundation_cy': int(self.concrete_foundation_cy),
                'concrete_columns_cy': int(self.concrete_columns_cy),
                'center_core_wall_sf': int(self.center_core_wall_sf),
                'center_core_wall_concrete_cy': int(self.center_core_wall_concrete_cy),
                'center_curb_concrete_cy': int(self.center_curb_concrete_cy),
                'center_curb_sf': int(self.center_curb_sf),
                'perimeter_barrier_lf': int(self.perimeter_barrier_lf),
                'perimeter_barrier_sf': int(self.perimeter_barrier_sf),
                'perimeter_barrier_concrete_cy': int(self.perimeter_barrier_concrete_cy),
                'concrete_core_wall_cy': int(self.concrete_core_wall_cy),
                'core_wall_area_sf': int(self.core_wall_area_sf),
                'elevator_shaft_sf': int(self.elevator_shaft_sf),
                'elevator_shaft_concrete_cy': int(self.elevator_shaft_concrete_cy),
                'stair_enclosure_sf': int(self.stair_enclosure_sf),
                'stair_enclosure_concrete_cy': int(self.stair_enclosure_concrete_cy),
                'utility_closet_sf': int(self.utility_closet_sf),
                'utility_closet_concrete_cy': int(self.utility_closet_concrete_cy),
                'storage_closet_sf': int(self.storage_closet_sf),
                'storage_closet_concrete_cy': int(self.storage_closet_concrete_cy),
                'rebar_lbs': int(self.total_rebar_lbs),
                'post_tension_lbs': int(self.post_tension_lbs),
                'exterior_wall_sf': int(self.exterior_wall_sf)
            },
            'excavation': {
                'excavation_cy': int(self.excavation_cy),
                'export_cy': int(self.export_cy),
                'structural_fill_cy': int(self.structural_fill_cy),
                'retaining_wall_sf': int(self.retaining_wall_sf) if self.half_levels_below > 0 else 0
            }
        }

    def get_wall_linear_feet_breakdown(self) -> Dict:
        """
        Return detailed linear feet breakdown for all walls and cores

        Returns:
            Dict with LF for each wall/core type and totals
        """
        breakdown = {}

        # Elevator shaft (8' × 8' = 32 LF perimeter)
        # Extends one FULL FLOOR above top parking for mechanical equipment room
        # NOTE: Pit (8' CMU) is calculated separately, not included in concrete shaft
        elevator_shaft_lf = 32.0
        parking_height = self.total_levels * self.level_height
        elevator_height = parking_height + self.floor_to_floor  # No pit in concrete height
        breakdown['elevator_shaft'] = {
            'lf': elevator_shaft_lf,
            'height_ft': elevator_height,
            'description': f'8\' × 8\' shaft (32 LF), {parking_height:.1f}\' parking ({self.total_levels} levels) + {self.floor_to_floor:.1f}\' mechanical (pit is CMU)'
        }

        # Stairs (12' × 24' footprint = 72 LF perimeter, 4-sided)
        # Extends one FULL FLOOR above top parking for roof access
        stair_lf_per_stair = 72.0  # LF per stair enclosure
        total_stair_lf = stair_lf_per_stair * self.num_stairs
        stair_height = parking_height + self.floor_to_floor
        breakdown['stair_enclosures'] = {
            'lf_per_stair': stair_lf_per_stair,
            'num_stairs': self.num_stairs,
            'total_lf': total_stair_lf,
            'height_ft': stair_height,
            'description': f'{self.num_stairs} stair enclosures @ 72 LF each, {parking_height:.1f}\' parking ({self.total_levels} levels) + {self.floor_to_floor:.1f}\' roof access'
        }

        # Utility closet (20' × 19' = 78 LF perimeter)
        # Only extends to top parking surface (does not extend above)
        utility_lf = 78.0
        utility_height = parking_height  # Same as parking: total_levels × level_height
        breakdown['utility_closet'] = {
            'lf': utility_lf,
            'height_ft': utility_height,
            'description': f'20\' × 19\' closet (78 LF), {parking_height:.1f}\' ({self.total_levels} levels to top parking surface)'
        }

        # Storage closet (29' × 18' = 94 LF perimeter)
        # Only extends to top parking surface (does not extend above)
        storage_lf = 94.0
        storage_height = parking_height  # Same as parking: total_levels × level_height
        breakdown['storage_closet'] = {
            'lf': storage_lf,
            'height_ft': storage_height,
            'description': f'29\' × 18\' closet (94 LF), {parking_height:.1f}\' ({self.total_levels} levels to top parking surface)'
        }

        # System-specific center elements
        from .geometry.design_modes import RampSystemType
        if hasattr(self, 'ramp_barrier_sf') and self.ramp_barrier_sf > 0:
            # Ramp barriers (36" × 6" or 12" thick depending on system)
            # Split-level center divide uses two 6" barriers with 1.0' gap
            barrier_lf_per_level = self.length * 2  # Both sides of ramp bay(s)
            total_barrier_lf = barrier_lf_per_level * self.total_levels
            barrier_thickness = 6  # 6" for split-level center divide
            breakdown['ramp_barriers'] = {
                'lf_per_level': barrier_lf_per_level,
                'num_levels': self.total_levels,
                'total_lf': total_barrier_lf,
                'thickness_in': barrier_thickness,
                'height_in': 36,
                'description': f'36" × {barrier_thickness}" barriers, {barrier_lf_per_level:.0f}\' × {self.total_levels} levels'
            }

        # Calculate totals
        total_lf = elevator_shaft_lf + total_stair_lf + utility_lf + storage_lf
        if 'ramp_barriers' in breakdown:
            total_lf += breakdown['ramp_barriers']['total_lf']

        breakdown['total_wall_lf'] = total_lf

        # === 12" WALL SUBCATEGORIES (SF and LF) ===
        # Provide clear subcategories to avoid confusion with TR budget groupings
        twelve_inch = {}

        # Elevator shaft
        twelve_inch['elevator_shaft'] = {
            'lf': elevator_shaft_lf,
            'sf': getattr(self, 'elevator_shaft_sf', 0.0)
        }

        # Stairs
        twelve_inch['stair_enclosures'] = {
            'lf': total_stair_lf,
            'sf': getattr(self, 'stair_enclosure_sf', 0.0)
        }

        # Utility and storage
        twelve_inch['utility_closet'] = {
            'lf': utility_lf,
            'sf': getattr(self, 'utility_closet_sf', 0.0)
        }
        twelve_inch['storage_closet'] = {
            'lf': storage_lf,
            'sf': getattr(self, 'storage_closet_sf', 0.0)
        }

        # Center core walls (none in updated architecture)
        twelve_inch['center_core_walls'] = {
            'lf': 0.0,
            'sf': 0.0
        }

        # Ramp edge barriers (6" thick per updated spec for split-level)
        ramp_barrier_lf = 0.0
        if 'ramp_barriers' in breakdown:
            ramp_barrier_lf = breakdown['ramp_barriers'].get('total_lf', 0.0)
        twelve_inch['ramp_edge_barriers'] = {
            'lf': ramp_barrier_lf,
            'sf': getattr(self, 'ramp_barrier_sf', 0.0)
        }

        # Top-level perimeter barrier (standalone only)
        top_barrier_sf = getattr(self, 'top_level_barrier_12in_sf', 0.0)
        if top_barrier_sf > 0:
            full_perimeter_lf = 2 * (self.length + self.width)
        else:
            full_perimeter_lf = 0.0
        twelve_inch['top_level_perimeter_barrier'] = {
            'lf': full_perimeter_lf,
            'sf': top_barrier_sf
        }

        # Totals across subcategories
        total_sf_12in = sum(item['sf'] for item in twelve_inch.values())
        total_lf_12in = sum(item['lf'] for item in twelve_inch.values())
        twelve_inch['totals'] = {
            'lf': total_lf_12in,
            'sf': total_sf_12in
        }

        breakdown['twelve_inch_wall_subtotals'] = twelve_inch

        return breakdown

    def get_column_breakdown(self) -> Dict:
        """
        Return detailed column count and dimensional breakdown

        Returns:
            Dict with column counts, heights, grid spacing
        """
        columns_width = int(self.width / self.PRIMARY_BAY_SPACING) + 1
        columns_length = int(self.length / self.PRIMARY_BAY_SPACING) + 1

        return {
            'total_count': self.num_columns,
            'perimeter_count': self.num_perimeter_columns,
            'center_count': self.num_center_columns,
            'columns_width_direction': columns_width,
            'columns_length_direction': columns_length,
            'grid_spacing_ft': self.PRIMARY_BAY_SPACING,
            'column_size': '18" × 24"',
            'column_cross_section_sf': 3.0,
            'average_height_ft': self.total_height_ft,
            'total_linear_feet': self.num_columns * self.total_height_ft,
            'description': f'{self.num_columns} columns from authoritative generator (stall/aisle boundaries and ramp centerlines, ≤ {self.PRIMARY_BAY_SPACING}\')'
        }

    def get_level_breakdown(self) -> list:
        """
        Return level-by-level breakdown of GSF and stalls

        Returns:
            List of dicts, one per level with name, elevation, GSF, stalls, type
        """
        level_data = []

        # Correctly unpack 4-tuple: (level_name, gsf, slab_type, elevation)
        # Stalls are stored separately in self.stalls_by_level dictionary
        for i, (level_name, gsf, slab_type, elevation) in enumerate(self.levels):
            # Look up stalls for this level from stalls_by_level dictionary
            stalls = self.stalls_by_level.get(level_name, {}).get('stalls', 0)

            # Determine level type based on elevation
            if i < self.half_levels_below:
                level_type = 'Below Grade'
            elif i == self.half_levels_below:
                level_type = 'Grade Level'
            else:
                level_type = 'Above Grade'

            # Determine if full or half level (split-level specific)
            from .geometry.design_modes import RampSystemType
            if self.ramp_system == RampSystemType.SPLIT_LEVEL_DOUBLE:
                # In split-level, check if this is a full intersection level
                # Full levels occur at even indices (0, 2, 4, ...) where both ramps meet
                is_full_level = (i % 2 == 0)
                level_size = 'Full Level' if is_full_level else 'Half Level'
            else:
                # Single-ramp: all levels are full
                level_size = 'Full Level'

            level_data.append({
                'level_name': level_name,
                'level_index': i,
                'elevation_ft': elevation,
                'gsf': gsf,
                'stalls': stalls,
                'level_type': level_type,
                'slab_type': slab_type,
                'level_size': level_size
            })

        return level_data

    def get_3d_geometry(self) -> Dict:
        """
        Generate 3D coordinate data for visualization
        Returns vertex data for floors, columns, core wall, and ramps
        """
        geometry = {
            'floors': [],
            'columns': [],
            'core_wall': [],
            'ramps': [],
            'footings': []
        }

        # Floor plates at each parking level elevation
        # Split-level garages have floor slabs at half-level spacing (5.33')
        for i in range(self.total_levels):
            z = i * self.half_level_height - self.depth_below_grade_ft
            level_name = self.levels[i][0]
            is_below_grade = z < 0

            geometry['floors'].append({
                'level': i,
                'name': level_name,
                'z': z,
                'is_below_grade': is_below_grade,
                'vertices': [
                    [0, 0, z],
                    [self.length, 0, z],
                    [self.length, self.width, z],
                    [0, self.width, z]
                ]
            })

        # Add roof slab at top
        roof_z = self.total_height_ft - self.depth_below_grade_ft
        geometry['floors'].append({
            'level': self.total_levels,
            'name': 'Roof',
            'z': roof_z,
            'is_below_grade': False,
            'vertices': [
                [0, 0, roof_z],
                [self.length, 0, roof_z],
                [self.length, self.width, roof_z],
                [0, self.width, roof_z]
            ]
        })

        # Columns on 31' grid
        # Columns extend from bottom to top parking level
        top_parking_level_height = self.total_height_ft

        # Use authoritative columns list
        z_bottom = -self.depth_below_grade_ft
        z_top = top_parking_level_height - self.depth_below_grade_ft
        for c in getattr(self, 'columns', []):
            geometry['columns'].append({
                'x': c['x'],
                'y': c['y'],
                'z_bottom': z_bottom,
                'z_top': z_top
            })

        # Center elements: columns + ramp edge barriers (no core walls/curbs)
        geometry['center_core_walls'] = []  # legacy key (not used)
        geometry['center_curbs'] = []       # legacy key (not used)
        geometry['center_columns'] = []     # legacy key (not used)
        geometry['ramp_edge_barriers'] = []

        # Calculate ramp section extent (for center columns run)
        ramp_x_start = self.TURN_ZONE_DEPTH
        ramp_x_end = self.length - self.TURN_ZONE_DEPTH

        # Generate ramp edge barriers (visual separator for ramp bay centerlines)
        for i in range(self.num_center_lines):
            center_y = (i + 1) * self.PARKING_MODULE_WIDTH + (i + 0.5) * self.CENTER_SPACING + self.EXTERIOR_WALL_THICKNESS
            # Two ramp edge barriers forming 2.0' center divider (6" each) with 1.0' clear gap, full length
            geometry['ramp_edge_barriers'].append({
                'x_start': 0,
                'x_end': self.length,
                'y_start': center_y - 1.0,
                'y_end': center_y - 0.5,  # 6" band below the 1.0' clear gap
                'z_bottom': -self.depth_below_grade_ft,
                'z_top': top_parking_level_height - self.depth_below_grade_ft
            })
            geometry['ramp_edge_barriers'].append({
                'x_start': 0,
                'x_end': self.length,
                'y_start': center_y + 0.5,
                'y_end': center_y + 1.0,  # 6" band above the 1.0' clear gap
                'z_bottom': -self.depth_below_grade_ft,
                'z_top': top_parking_level_height - self.depth_below_grade_ft
            })

        # Ramp paths (simplified helical paths for up/down)
        ramp_points_up = []
        ramp_points_down = []

        for i in range(self.total_levels * 10):  # 10 points per level
            t = i / (self.total_levels * 10)
            z = t * self.total_height_ft - self.depth_below_grade_ft

            # Up ramp (west side)
            x_up = (t * self.length) % self.length
            y_up = 31  # West ramp bay center
            ramp_points_up.append([x_up, y_up, z])

            # Down ramp (east side)
            x_down = self.length - (t * self.length) % self.length
            y_down = 95  # East ramp bay center
            ramp_points_down.append([x_down, y_down, z])

        geometry['ramps'] = {
            'up': ramp_points_up,
            'down': ramp_points_down
        }

        # Footings (if calculated)
        if hasattr(self, 'footings_for_visualization'):
            z_top_footing = -self.depth_below_grade_ft  # Top at bottom of grade
            for f in self.footings_for_visualization:
                outer_half = f['outer_width_ft'] / 2.0
                x0 = max(0.0, f['x_center'] - outer_half)
                x1 = min(self.length, f['x_center'] + outer_half)
                y0 = max(0.0, f['y_center'] - outer_half)
                y1 = min(self.width, f['y_center'] + outer_half)
                geometry['footings'].append({
                    'type': 'outer',
                    'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1,
                    'z_top': z_top_footing,
                    'thickness_ft': f['outer_thickness_ft']
                })
                if f.get('two_depth', False):
                    dp_x_half = f['drop_width_x_ft'] / 2.0
                    dp_y_half = f['drop_width_y_ft'] / 2.0
                    dx0 = max(0.0, f['x_center'] - dp_x_half)
                    dx1 = min(self.length, f['x_center'] + dp_x_half)
                    dy0 = max(0.0, f['y_center'] - dp_y_half)
                    dy1 = min(self.width, f['y_center'] + dp_y_half)
                    geometry['footings'].append({
                        'type': 'drop',
                        'x0': dx0, 'x1': dx1, 'y0': dy0, 'y1': dy1,
                        'z_top': z_top_footing,
                        'thickness_ft': f['inner_thickness_ft']
                    })

        return geometry


def compute_width_ft(num_bays: int) -> float:
    """
    Compute building width in feet from number of bays using geometry constants.
    Uses the same formula as SplitLevelParkingGarage to ensure a single source of truth.

    Args:
        num_bays: Number of parking bays (2-7)

    Returns:
        Building width in feet
    """
    return 1.0 + (num_bays * SplitLevelParkingGarage.PARKING_MODULE_WIDTH) + ((num_bays - 1) * SplitLevelParkingGarage.CENTER_SPACING)

# Neutral alias for clarity at call sites
ParkingGarage = SplitLevelParkingGarage

def create_parking_garage(
    length: float,
    half_levels_above: int,
    half_levels_below: int,
    num_bays: int,
    *,
    ramp_system: Optional[object] = None,
    **kwargs
) -> ParkingGarage:
    """
    Factory to create a ParkingGarage with centralized ramp system selection.
    If ramp_system is None, selects based on geometry; otherwise honors override.
    """
    from .geometry.design_modes import RampSystemType
    selected_system = ramp_system or RampSystemType.determine_optimal(length, num_bays)
    return SplitLevelParkingGarage(
        length=length,
        half_levels_above=half_levels_above,
        half_levels_below=half_levels_below,
        num_bays=num_bays,
        ramp_system=selected_system,
        **kwargs
    )


if __name__ == "__main__":
    # Example usage: 2-bay garage, 210' length, 8 half-levels above grade
    print("Example configuration (126' × 210', 8 above, 0 below, 2 bays)...")
    garage = SplitLevelParkingGarage(210, 8, 0, 2)
    garage.print_discrete_level_breakdown()
