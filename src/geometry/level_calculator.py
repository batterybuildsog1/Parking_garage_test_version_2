"""
Discrete Level Area Calculator

Calculates individual Gross Floor Area (GSF) for each level in a parking garage.

Supports two ramp systems:
1. SPLIT-LEVEL: Half-levels have ~50% of footprint due to helical ramp geometry
2. SINGLE-RAMP: Full floors have 100% of footprint (flat bays + one ramp bay)

KEY CONCEPTS:
- Split-level: At any half-level elevation (e.g., P1.5), only the ramping portions
  pass through that elevation - not the full footprint.
- Single-ramp: Each full floor includes all flat bays at elevation E, plus the ramp
  bay slice from (E-9') to E.
"""

from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .design_modes import RampSystemType


class DiscreteLevelCalculator:
    """
    Calculates discrete floor areas for parking garage

    Supports both split-level and single-ramp systems.
    Each level is calculated individually based on:
    - Position in the building (bottom, middle, top)
    - Ramp geometry (helical spiral or single ramp)
    - Entry and termination zones
    """

    # Constants (from original geometry.py)
    FLAT_ENTRY_LENGTH = 100  # feet (flat entry circulation zone)
    RAMP_TERMINATION_LENGTH = 48  # feet (ramp end termination at top)

    def __init__(self, footprint_sf: float, width: float, length: float,
                 half_levels_above: int, half_levels_below: int,
                 entry_elevation: float = 0.0,
                 ramp_system: 'RampSystemType' = None,
                 floor_to_floor: float = 10.656,
                 level_height: float = 5.328):
        """
        Initialize level calculator

        Args:
            footprint_sf: Total building footprint (SF)
            width: Building width (feet)
            length: Building length (feet)
            half_levels_above: Number of levels above entry
                              SPLIT_LEVEL: half-levels (10 = P0.5 to P5)
                              SINGLE_RAMP: full floors (5 = P1 to P5)
            half_levels_below: Number of levels below entry
            entry_elevation: Elevation of entry level (default 0' = grade)
            ramp_system: RampSystemType enum (SPLIT_LEVEL_DOUBLE or SINGLE_RAMP_FULL)
            floor_to_floor: Floor-to-floor height (system-dependent, passed from garage)
            level_height: Vertical spacing between levels (system-dependent)
        """
        self.footprint_sf = footprint_sf
        self.width = width
        self.length = length
        self.half_levels_above = half_levels_above
        self.half_levels_below = half_levels_below
        self.entry_elevation = entry_elevation

        # Ramp system configuration (passed from garage, system-dependent)
        self.ramp_system = ramp_system
        self.floor_to_floor = floor_to_floor
        self.level_height = level_height

        # Derived values
        self.total_levels = half_levels_below + 1 + half_levels_above  # +1 for entry
        self.entry_level_index = half_levels_below  # 0-based index of entry level

        # Determine if this is a half-level system (for naming and logic)
        if ramp_system is not None:
            from .design_modes import RampSystemType
            self.is_half_level_system = (ramp_system == RampSystemType.SPLIT_LEVEL_DOUBLE)
        else:
            # Legacy: assume split-level if not specified
            self.is_half_level_system = True

    def calculate_all_levels(self) -> Tuple[List[Tuple[str, float, str, float]], dict]:
        """
        Calculate discrete GSF for all levels

        Dispatches to system-specific calculation method.

        Returns:
            Tuple of:
            - List of (level_name, gsf, slab_type, elevation) tuples
            - Dict with summary: {total_gsf, sog_sf, suspended_sf, num_levels}
        """
        if self.is_half_level_system:
            return self._calculate_split_level_areas()
        else:
            return self._calculate_full_floor_areas()

    def _calculate_split_level_areas(self) -> Tuple[List[Tuple[str, float, str, float]], dict]:
        """
        Calculate discrete GSF for split-level (half-level) system

        Half-levels have ~50% of footprint due to helical ramp geometry.
        """
        levels = []

        # Standard half-level GSF (~50% of footprint)
        half_level_gsf = self.footprint_sf / 2

        # Calculate bottom elevation
        bottom_elevation = self.entry_elevation - (self.half_levels_below * self.level_height)

        # Generate all levels (bottom to top)
        for level_index in range(self.total_levels):
            # Calculate elevation
            elevation = bottom_elevation + (level_index * self.level_height)

            # Get level name
            level_name = self._get_level_name_split_level(level_index)

            # Determine slab type
            # Bottom 2 half-levels are SOG (slab on grade - poured on shaped dirt)
            # All others are suspended (elevated on columns)
            if level_index <= 1:
                slab_type = "sog"
            else:
                slab_type = "suspended"

            # Determine GSF
            if level_index == self.total_levels - 1:
                # Top level: reduced by ramp termination at north end
                # Physical structure terminates, so GSF is actually reduced
                top_effective_length = self.length - self.RAMP_TERMINATION_LENGTH
                level_gsf = self.width * top_effective_length / 2
            else:
                # All other levels: standard half-level (~50% of footprint)
                # Entry level is standard half-level (FLAT_ENTRY_LENGTH reduces stalls, not GSF)
                level_gsf = half_level_gsf

            # Add to levels list
            levels.append((level_name, level_gsf, slab_type, elevation))

        # Calculate summary
        total_gsf = sum(gsf for _, gsf, _, _ in levels)
        sog_sf = sum(gsf for _, gsf, slab_type, _ in levels if slab_type == "sog")
        suspended_sf = sum(gsf for _, gsf, slab_type, _ in levels if slab_type == "suspended")

        summary = {
            'total_gsf': total_gsf,
            'sog_sf': sog_sf,
            'suspended_sf': suspended_sf,
            'num_levels': len(levels)
        }

        return levels, summary

    def _calculate_full_floor_areas(self) -> Tuple[List[Tuple[str, float, str, float]], dict]:
        """
        Calculate discrete GSF for single-ramp (full floor) system

        Each full floor has 100% of footprint (all flat bays + ramp bay at same elevation).
        """
        levels = []

        # Full floor GSF = 100% of footprint
        full_floor_gsf = self.footprint_sf

        # Calculate bottom elevation
        bottom_elevation = self.entry_elevation - (self.half_levels_below * self.level_height)

        # Generate all levels (bottom to top)
        for level_index in range(self.total_levels):
            # Calculate elevation
            elevation = bottom_elevation + (level_index * self.level_height)

            # Get level name
            level_name = self._get_level_name_full_floor(level_index)

            # Determine slab type
            # Bottom level is SOG (slab on grade - poured on shaped dirt)
            # All others are suspended (elevated on columns)
            if level_index == 0:
                slab_type = "sog"
            else:
                slab_type = "suspended"

            # Determine GSF
            if level_index == self.total_levels - 1:
                # Top level: reduced by ramp termination at north end
                # Physical structure terminates, so GSF is actually reduced
                top_effective_length = self.length - self.RAMP_TERMINATION_LENGTH
                level_gsf = self.width * top_effective_length
            else:
                # All other levels: full floor (100% of footprint)
                level_gsf = full_floor_gsf

            # Add to levels list
            levels.append((level_name, level_gsf, slab_type, elevation))

        # Calculate summary
        total_gsf = sum(gsf for _, gsf, _, _ in levels)
        sog_sf = sum(gsf for _, gsf, slab_type, _ in levels if slab_type == "sog")
        suspended_sf = sum(gsf for _, gsf, slab_type, _ in levels if slab_type == "suspended")

        summary = {
            'total_gsf': total_gsf,
            'sog_sf': sog_sf,
            'suspended_sf': suspended_sf,
            'num_levels': len(levels)
        }

        return levels, summary

    def _get_level_name_split_level(self, level_index: int) -> str:
        """
        Generate level name for SPLIT-LEVEL system based on position relative to grade

        NAMING CONVENTION (Half-Levels):
        - Below grade: B-2, B-1.5, B-1, B-0.5 (counting up toward grade)
        - At grade (entry): Grade
        - Above grade: P0.5, P1, P1.5, P2, P2.5, P3, ...

        Args:
            level_index: 0-based index (0 = bottom level)

        Returns:
            Level name string

        Examples:
            half_levels_below=0, half_levels_above=9:
              Index 0: Grade (entry)
              Index 1: P0.5
              Index 2: P1
              Index 3: P1.5
              ...

            half_levels_below=3, half_levels_above=6:
              Index 0: B-1.5 (bottom)
              Index 1: B-1
              Index 2: B-0.5
              Index 3: Grade (entry)
              Index 4: P0.5
              Index 5: P1
              ...
        """
        if level_index < self.entry_level_index:
            # Below grade level
            levels_below_entry = self.entry_level_index - level_index

            # Convert to floor notation (2 half-levels per floor)
            if levels_below_entry % 2 == 1:
                # Odd: half-level
                floor_num = (levels_below_entry + 1) // 2
                return f"B-{floor_num - 1}.5"
            else:
                # Even: full level
                floor_num = levels_below_entry // 2
                return f"B-{floor_num}"

        elif level_index == self.entry_level_index:
            # Entry level at grade
            return "Grade"

        else:
            # Above grade level
            levels_above_entry = level_index - self.entry_level_index

            # Starting from entry, count up: 0.5, 1, 1.5, 2, 2.5, ...
            if levels_above_entry % 2 == 1:
                # Odd: full level
                floor_num = (levels_above_entry + 1) // 2
                return f"P{floor_num}"
            else:
                # Even: half-level
                floor_num = levels_above_entry // 2
                return f"P{floor_num}.5"

    def _get_level_name_full_floor(self, level_index: int) -> str:
        """
        Generate level name for SINGLE-RAMP (full floor) system based on position relative to grade

        NAMING CONVENTION (Full Floors):
        - Below grade: B-3, B-2, B-1 (counting up toward grade)
        - At grade (entry): Grade
        - Above grade: P1, P2, P3, P4, ... (NO half-level decimals)

        Args:
            level_index: 0-based index (0 = bottom level)

        Returns:
            Level name string

        Examples:
            half_levels_below=0, half_levels_above=5:
              Index 0: Grade (entry)
              Index 1: P1
              Index 2: P2
              Index 3: P3
              Index 4: P4
              Index 5: P5

            half_levels_below=2, half_levels_above=3:
              Index 0: B-2 (bottom)
              Index 1: B-1
              Index 2: Grade (entry)
              Index 3: P1
              Index 4: P2
              Index 5: P3
        """
        if level_index < self.entry_level_index:
            # Below grade level
            levels_below_entry = self.entry_level_index - level_index
            # For full floors, each level is a full floor (not half-level)
            floor_num = levels_below_entry
            return f"B-{floor_num}"

        elif level_index == self.entry_level_index:
            # Entry level at grade
            return "Grade"

        else:
            # Above grade level
            levels_above_entry = level_index - self.entry_level_index
            # For full floors, count up: 1, 2, 3, 4, ... (no decimals)
            floor_num = levels_above_entry
            return f"P{floor_num}"

    def print_level_breakdown(self, levels: List[Tuple[str, float, str, float]]):
        """
        Print formatted breakdown of discrete level areas

        Args:
            levels: List of (level_name, gsf, slab_type, elevation) tuples
        """
        print("\n" + "=" * 100)
        print(f"{'DISCRETE LEVEL BREAKDOWN':^100}")
        print("=" * 100)
        print(f"Geometry: {self.width:.1f}' × {self.length:.1f}' footprint = {self.footprint_sf:,.0f} SF")
        print(f"Configuration: {self.half_levels_above} half-levels above, {self.half_levels_below} half-levels below")
        print(f"Parameters: Entry zone={self.FLAT_ENTRY_LENGTH}', Top termination={self.RAMP_TERMINATION_LENGTH}'")
        print(f"Entry: Grade at elevation {self.entry_elevation:.2f}'")
        print("\n" + "-" * 100)
        print(f"{'Level':<12} {'Elevation':<12} {'GSF':<15} {'Slab Type':<15} {'% of Footprint':<20} {'Grade':<15}")
        print("-" * 100)

        for level_name, gsf, slab_type, elevation in levels:
            pct_footprint = (gsf / self.footprint_sf) * 100

            # Determine grade status
            if elevation == self.entry_elevation:
                grade_status = "Entry (at grade)"
            elif elevation < 0:
                grade_status = f"Below grade ({elevation:.1f}')"
            else:
                grade_status = f"Above grade (+{elevation:.1f}')"

            print(f"{level_name:<12} {elevation:>10.2f}'  {gsf:>12,.0f} SF  {slab_type.upper():<15} {pct_footprint:>16.1f}%    {grade_status:<15}")

        print("-" * 100)

        # Summary
        total_gsf = sum(gsf for _, gsf, _, _ in levels)
        sog_sf = sum(gsf for _, gsf, slab_type, _ in levels if slab_type == "sog")
        suspended_sf = sum(gsf for _, gsf, slab_type, _ in levels if slab_type == "suspended")

        print(f"{'TOTAL GSF':<12} {'':<12} {total_gsf:>12,.0f} SF")
        print(f"{'SOG':<12} {'':<12} {sog_sf:>12,.0f} SF  {'':<15} {(sog_sf/total_gsf*100):>16.1f}%")
        print(f"{'SUSPENDED':<12} {'':<12} {suspended_sf:>12,.0f} SF  {'':<15} {(suspended_sf/total_gsf*100):>16.1f}%")
        print("=" * 100)
