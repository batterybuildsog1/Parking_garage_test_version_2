"""
Core building elements for parking garage layout

Contains classes representing physical building components that affect parking layout:
- CoreBlockage: Corner cores (elevator, stairs, utility, storage) that block parking
- ParkingSection: Individual parking rows/strips where stalls can be placed
"""

from typing import Dict, Tuple


class CoreBlockage:
    """
    Represents a corner core (elevator, stair, storage, utility) that blocks parking space

    Corner cores are functional spaces (elevator shafts, stair enclosures, mechanical rooms,
    storage rooms) located at building corners. They block parking stalls in adjacent zones.
    """

    def __init__(self, corner: str, core_type: str, dimensions: Dict):
        """
        Initialize a core blockage

        Args:
            corner: Corner location - 'NW', 'NE', 'SW', 'SE'
            core_type: Type of core - 'elevator', 'stair', 'utility', 'storage'
            dimensions: Dict with dimensions:
                - For rectangular: {'length': float, 'width': float}
                - For L-shaped: {'x_leg': float, 'y_leg': float, 'width': float}
        """
        self.corner = corner
        self.core_type = core_type
        self.dimensions = dimensions

    def get_y_blockage(self) -> float:
        """
        Return length blocked along Y-axis (building length direction)

        Returns:
            Blockage length in feet
        """
        if 'y_leg' in self.dimensions:
            # L-shaped core: use longer leg
            return self.dimensions['y_leg']
        else:
            # Rectangular core
            return self.dimensions['length']


class ParkingSection:
    """
    Represents one parking row/strip (18' wide) where stalls can be placed

    Parking sections are the fundamental unit of parking layout. Each section is an
    18'-wide strip where vehicles can park perpendicular or parallel to the aisle.

    Sections can be:
    - Full length: Runs entire building length
    - Middle only: Only in middle section (excludes turn zones)
    - Turn zone: Only in turn zone area
    """

    def __init__(self, name: str, x_range: Tuple[float, float],
                 y_range: Tuple[float, float], section_type: str):
        """
        Initialize a parking section

        Args:
            name: Section name (e.g., 'west_row', 'center_row_0', 'north_turn')
            x_range: (x_start, x_end) in feet (width direction)
            y_range: (y_start, y_end) in feet (length direction)
            section_type: 'full_length', 'middle_only', or 'turn_zone'
        """
        self.name = name
        self.x_start, self.x_end = x_range
        self.y_start, self.y_end = y_range
        self.section_type = section_type
        self.width = self.x_end - self.x_start
        self.base_length = self.y_end - self.y_start
        self.blockages = []  # List of (start_y, end_y) tuples

    def add_core_blockage(self, core: CoreBlockage, building_length: float, building_width: float):
        """
        Add blockage from a corner core if it affects this section

        Cores only affect sections in their quadrant of the building. Uses dynamic
        thresholds (25% of building width) to determine if core affects this section.

        Args:
            core: CoreBlockage instance
            building_length: Total building length (feet)
            building_width: Total building width (feet)
        """
        if self.section_type == 'turn_zone':
            return  # Turn zones calculated separately

        blockage_length = core.get_y_blockage()

        # Determine if this core affects this section based on X-position
        # Use dynamic thresholds based on building width
        affects_west = self.x_start < building_width * 0.25  # West 25% of building
        affects_east = self.x_start > building_width * 0.75  # East 25% of building

        if core.corner == 'NW' and affects_west:
            # Blocks from north end
            self.blockages.append((0, blockage_length))
        elif core.corner == 'SW' and affects_west:
            # Blocks from south end
            self.blockages.append((building_length - blockage_length, building_length))
        elif core.corner == 'NE' and affects_east:
            # Blocks from north end
            self.blockages.append((0, blockage_length))
        elif core.corner == 'SE' and affects_east:
            # Blocks from south end
            self.blockages.append((building_length - blockage_length, building_length))

    def calculate_available_length(self) -> float:
        """
        Calculate parking-available length after all blockages

        Returns:
            Available parking length in feet
        """
        available = self.base_length

        for start_y, end_y in self.blockages:
            # Calculate overlap between blockage and this section's Y-range
            overlap_start = max(start_y, self.y_start)
            overlap_end = min(end_y, self.y_end)

            if overlap_end > overlap_start:
                available -= (overlap_end - overlap_start)

        return available

    def calculate_stalls(self) -> Tuple[int, float]:
        """
        Calculate stall count in 9' increments and wasted space

        Stalls are placed in 9' increments along the available length.
        Remaining space less than 9' is considered "wasted" (excess).

        Returns:
            Tuple of (stall_count, wasted_space_ft)
        """
        available = self.calculate_available_length()
        stalls = int(available // 9)
        wasted = available % 9
        return stalls, wasted
