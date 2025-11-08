"""
Parking Layout Module - 2D Spatial Parking Analysis

This module handles the 2D parking layout for split-level garages, calculating
stall counts based on discrete spatial geometry.

CRITICAL DISTINCTION - Two Separate Concepts:
==========================================

1. PHYSICAL CORE WALLS (calculated elsewhere in garage.py):
   - Actual concrete structures (elevator shafts, stair enclosures, closets)
   - Example: Elevator shaft is 8'×8' interior with 12" concrete walls
   - Used for: Cost calculations, concrete quantities, rebar, 3D visualization
   - Cost component: Forms, concrete, rebar at $28.50/SF

2. BLOCKAGE ZONES (handled by CoreBlockage in this module):
   - Non-parkable buffer areas around cores (NOT physical walls)
   - Example: Elevator blockage is 49'×37' including shaft + access + circulation
   - Includes: Door swing clearances, code-required access paths, ADA space, circulation
   - Used for: Reducing available parking length in stall calculations
   - Not a cost component: Only affects how many stalls fit

Architecture:
    ParkingLayout creates 6 distinct parking sections and applies blockage zones
    from the 4 corner cores. These blockages reduce available parking length but
    do NOT represent the physical structures themselves.
"""

from typing import Dict, Tuple, List
from .core_elements import CoreBlockage, ParkingSection


class ParkingLayout:
    """
    Complete 2D spatial layout for split-level parking garage

    Models 6 distinct parking sections:
    1. North turn zone
    2. West perimeter row (full length)
    3-N. Center rows (middle section only, pairs flanking core walls)
    N+1. East perimeter row (full length)
    N+2. South turn zone

    Applies 4 corner blockage zones (buffer areas, NOT physical walls):
    - NW: Utility closet blockage (20'×19' buffer)
    - NE: Elevator + stair blockage (49'×37' L-shaped buffer)
    - SE: Stair blockage (28'×10' L-shaped buffer)
    - SW: Storage closet blockage (29'×18' buffer)

    These blockages represent non-parkable areas (access paths, clearances),
    NOT the physical core wall structures themselves.
    """

    def __init__(self, width: float, length: float, num_bays: int):
        """
        Initialize parking layout

        Args:
            width: Building width (feet)
            length: Building length (feet)
            num_bays: Number of ramp bays
        """
        self.width = width
        self.length = length
        self.num_bays = num_bays
        self.sections = []
        self.cores = []
        self.turn_zone_depth = 48  # feet (30' turn + 18' end parking)

        self._initialize_cores()
        self._create_sections()

    def _initialize_cores(self):
        """
        Define the 4 corner core blockage zones

        IMPORTANT: These represent non-parkable buffer areas around the physical cores,
        NOT the physical core walls themselves.

        Example - NE Elevator:
        - Physical structure: 8'×8' elevator shaft (costed separately in garage.py)
        - Blockage zone: 49'×37' buffer area (defined here)
        - Blockage includes: shaft + door swing + waiting area + circulation + stair access

        These blockages are used ONLY to reduce available parking length in stall
        calculations. The actual core wall structures (concrete, forming, rebar) are
        calculated separately in SplitLevelParkingGarage._calculate_structural_components().
        """
        self.cores = [
            # NW Corner: Utility closet buffer zone
            CoreBlockage('NW', 'utility', {'length': 20, 'width': 19}),

            # NE Corner: Elevator + stair buffer zone (L-shaped)
            CoreBlockage('NE', 'elevator_stair', {'y_leg': 49, 'x_leg': 37}),

            # SE Corner: Stair buffer zone (L-shaped)
            CoreBlockage('SE', 'stair', {'y_leg': 28, 'x_leg': 10}),

            # SW Corner: Storage closet buffer zone
            CoreBlockage('SW', 'storage', {'length': 29, 'width': 18})
        ]

    def _create_sections(self):
        """
        Create 6 parking sections based on building geometry

        Section types:
        - 'turn_zone': North and south turn zones (stalls perpendicular to length)
        - 'full_length': West and east perimeter rows (full building length)
        - 'middle_only': Center rows (middle section only, excludes turn zones)

        Width structure (2-bay example = 126'):
        0.5' wall + 18' west + 25' aisle + 18' center_L + 3' core + 18' center_R + 25' aisle + 18' east + 0.5' wall
        """
        middle_start = self.turn_zone_depth
        middle_end = self.length - self.turn_zone_depth

        # Section 1: North turn zone
        self.sections.append(ParkingSection(
            'north_turn',
            (0, self.width),
            (0, self.turn_zone_depth),
            'turn_zone'
        ))

        # Section 2: West row (full length)
        # From exterior wall inward: 0.5' wall + 18' parking
        self.sections.append(ParkingSection(
            'west_row',
            (0.5, 18.5),
            (0, self.length),
            'full_length'
        ))

        # Section 3-N: Center rows (middle section only)
        # STRUCTURE: west_perimeter | aisle | center_row_1 | CORE | center_row_2 | aisle | east_perimeter
        # For 2-bay: 2 center rows flanking the single core wall
        # For 3-bay: 4 center rows (2 pairs flanking 2 core walls)
        # Formula: total_center_rows = 2 × (num_bays - 1)

        # Create center rows - one pair on each side of each core wall
        for core_index in range(self.num_bays - 1):  # num cores = num_bays - 1
            # Left center row (before the core wall)
            # Position: 0.5 + 18(west) + 25(aisle) + (core_index × (18+3+18+25))
            x_left_start = 0.5 + 18 + 25 + (core_index * (18 + 3 + 18 + 25))
            x_left_end = x_left_start + 18

            self.sections.append(ParkingSection(
                f'center_row_{core_index + 1}_left',
                (x_left_start, x_left_end),
                (middle_start, middle_end),
                'middle_only'
            ))

            # Right center row (after the core wall)
            # Position: left_start + 18(center1) + 3(core)
            x_right_start = x_left_start + 18 + 3
            x_right_end = x_right_start + 18

            self.sections.append(ParkingSection(
                f'center_row_{core_index + 1}_right',
                (x_right_start, x_right_end),
                (middle_start, middle_end),
                'middle_only'
            ))

        # Section N+1: East row (full length)
        # From interior: 18' parking + 0.5' wall
        self.sections.append(ParkingSection(
            'east_row',
            (self.width - 18.5, self.width - 0.5),
            (0, self.length),
            'full_length'
        ))

        # Section N+2: South turn zone
        self.sections.append(ParkingSection(
            'south_turn',
            (0, self.width),
            (self.length - self.turn_zone_depth, self.length),
            'turn_zone'
        ))

    def apply_core_blockages(self):
        """
        Apply core blockage zones to all affected parking sections

        This method applies non-parkable buffer areas around the 4 corner cores.
        These blockages reduce available parking length but do NOT represent
        the physical core wall structures.

        The blockages include access paths, door swing clearances, code-required
        circulation space, and ADA clearances around each core.
        """
        for section in self.sections:
            for core in self.cores:
                section.add_core_blockage(core, self.length, self.width)

    def calculate_turn_zone_stalls(self, zone: str) -> int:
        """
        Calculate stalls along north or south wall based on actual geometry

        Stalls run east-west along the wall (perpendicular to building length)
        The 48' turn zone depth doesn't affect stall count - stalls run along the WIDTH

        Formula: (Building width - exterior walls - corner cores) ÷ 9' stall width

        Example for 2-bay (126' wide):
        - North: (126 - 1 - 19 - 37) ÷ 9 = 7 stalls
        - South: (126 - 1 - 18 - 10) ÷ 9 = 10 stalls

        Scales with building width (more bays = wider = more turn zone stalls)

        Args:
            zone: 'north' or 'south'

        Returns:
            Number of stalls that fit in the turn zone
        """
        net_width = self.width
        net_width -= 1.0  # Exterior walls (0.5' each side)

        if zone == 'north':
            # Subtract NW and NE corner blockages
            for core in self.cores:
                if core.corner == 'NW':
                    net_width -= core.dimensions.get('width', 0)
                elif core.corner == 'NE':
                    # NE is L-shaped, use x_leg dimension for width blockage
                    net_width -= core.dimensions.get('x_leg', core.dimensions.get('width', 0))
        else:  # south
            # Subtract SW and SE corner blockages
            for core in self.cores:
                if core.corner == 'SW':
                    net_width -= core.dimensions.get('width', 0)
                elif core.corner == 'SE':
                    # SE is L-shaped, use x_leg dimension for width blockage
                    net_width -= core.dimensions.get('x_leg', core.dimensions.get('width', 0))

        # Floor division to get whole stalls
        stalls = int(net_width // 9)
        return stalls

    def calculate_total_stalls(self) -> Tuple[int, Dict]:
        """
        Calculate total stalls across all parking sections

        Returns:
            Tuple of:
            - Total stall count (int)
            - Stalls by section (dict) with keys:
                - stalls: Number of stalls in this section
                - wasted: Excess space (feet) less than one stall
                - available_length: Parking-available length after blockages
                - base_length: Original section length before blockages
        """
        stalls_by_section = {}

        for section in self.sections:
            if section.section_type == 'turn_zone':
                # Turn zones: geometric calculation along width
                zone = 'north' if section.y_start == 0 else 'south'
                stalls = self.calculate_turn_zone_stalls(zone)
                wasted = 0
                available = section.base_length
            else:
                # Regular sections: geometric calculation along length
                stalls, wasted = section.calculate_stalls()
                available = section.calculate_available_length()

            stalls_by_section[section.name] = {
                'stalls': stalls,
                'wasted': wasted,
                'available_length': available,
                'base_length': section.base_length
            }

        total = sum(s['stalls'] for s in stalls_by_section.values())

        return total, stalls_by_section

    def calculate_length_optimization(self, max_search: int = 18, structural_grid: bool = False) -> dict:
        """
        Calculate optimal length increment to maximize parking stall efficiency

        This method finds the "sweet spot" - the length addition that maximizes total
        stalls gained before entering a plateau zone where no additional stalls are added.

        Args:
            max_search: Maximum feet to search (default 18, covers ~2 stalls per row)
            structural_grid: If True, only consider 31' structural bay increments

        Returns:
            dict with:
                - optimal_ft: Optimal feet to add
                - total_gain: Total stalls gained at optimal point
                - efficiency: Stalls per foot added
                - gains_detail: List of (row_name, stall_gain) tuples
                - excess_by_row: Current excess space per row
                - new_excess: Excess after adding optimal length
                - plateau_zone_start: Where adding more length yields no additional stalls
                - plateau_zone_end: End of plateau zone
                - next_threshold: Next meaningful stall gain after plateau
                - all_thresholds: All meaningful length additions (for display)
                - structural_grid_mode: Whether structural grid mode was used

            Returns None if no improvement possible
        """
        # Get current excess space for all longitudinal rows
        base_stalls_by_row = {}
        excess_by_row = {}

        for section in self.sections:
            if section.section_type in ['full_length', 'middle_only']:
                stalls, wasted = section.calculate_stalls()
                base_stalls_by_row[section.name] = stalls
                excess_by_row[section.name] = wasted

        # Determine search increments
        if structural_grid:
            # Search in 31' structural bay increments
            increments = [31, 62, 93]  # 1, 2, 3 structural bays
        else:
            # Search 1' to max_search feet
            increments = list(range(1, max_search + 1))

        # Simulate adding length
        thresholds = []
        for add_ft in increments:
            new_layout = ParkingLayout(self.width, self.length + add_ft, self.num_bays)
            new_layout.apply_core_blockages()

            total_gain = 0
            gains_detail = []
            new_excess = {}

            for section in new_layout.sections:
                if section.section_type in ['full_length', 'middle_only']:
                    new_stalls, new_wasted = section.calculate_stalls()
                    gain = new_stalls - base_stalls_by_row[section.name]
                    new_excess[section.name] = new_wasted

                    if gain > 0:
                        total_gain += gain
                        gains_detail.append((section.name, gain))

            if total_gain > 0:
                efficiency = total_gain / add_ft
                thresholds.append({
                    'add_ft': add_ft,
                    'total_gain': total_gain,
                    'efficiency': efficiency,
                    'gains_detail': gains_detail,
                    'new_excess': new_excess
                })

        if not thresholds:
            return None

        # Find optimal: Maximum efficiency (stalls per foot added)
        # This finds the "sweet spot" - best return before entering plateau zone
        # User wants minimal investment for maximum marginal return
        optimal = max(thresholds, key=lambda x: x['efficiency'])

        # Find plateau zone: where optimal's total_gain persists without improvement
        optimal_gain = optimal['total_gain']
        plateau_thresholds = [t for t in thresholds if t['total_gain'] == optimal_gain]
        last_in_plateau = max(plateau_thresholds, key=lambda x: x['add_ft'])

        plateau_zone_start = None
        plateau_zone_end = None
        if last_in_plateau['add_ft'] > optimal['add_ft']:
            plateau_zone_start = optimal['add_ft'] + 1
            plateau_zone_end = last_in_plateau['add_ft']

        # Find next meaningful threshold after plateau
        next_threshold = None
        if plateau_zone_end:
            future_gains = [t for t in thresholds
                          if t['add_ft'] > plateau_zone_end and t['total_gain'] > optimal_gain]
            if future_gains:
                next_threshold = min(future_gains, key=lambda x: x['add_ft'])

        return {
            'optimal_ft': optimal['add_ft'],
            'total_gain': optimal['total_gain'],
            'efficiency': optimal['efficiency'],
            'gains_detail': optimal['gains_detail'],
            'excess_by_row': excess_by_row,
            'new_excess': optimal['new_excess'],
            'plateau_zone_start': plateau_zone_start,
            'plateau_zone_end': plateau_zone_end,
            'next_threshold': next_threshold,
            'all_thresholds': thresholds,
            'structural_grid_mode': structural_grid
        }

    def get_summary(self) -> Dict:
        """
        Return summary of parking layout

        Returns:
            Dict with section details and blockage information
        """
        return {
            'sections': [
                {
                    'name': s.name,
                    'type': s.section_type,
                    'x_range': (s.x_start, s.x_end),
                    'y_range': (s.y_start, s.y_end),
                    'width': s.width,
                    'base_length': s.base_length,
                    'blockages': s.blockages
                }
                for s in self.sections
            ],
            'cores': [
                {
                    'corner': c.corner,
                    'type': c.core_type,
                    'dimensions': c.dimensions,
                    'y_blockage': c.get_y_blockage()
                }
                for c in self.cores
            ]
        }
