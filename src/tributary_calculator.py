"""
Tributary area calculator for variable column spacing

Implements the midpoint method (industry-standard approach used in CAD/structural software):
- Each column receives the area from midpoint to adjacent columns in both directions
- Preserves equilibrium (sum of tributary areas = total slab area)
- Works with non-uniform grids (variable spacing)

Example:
    Columns A—(45')—B—(36')—C in X-direction
    - Column A gets: 45'/2 = 22.5' in X
    - Column B gets: 45'/2 + 36'/2 = 40.5' in X
    - Column C gets: 36'/2 = 18' in X
"""

from typing import Dict, Tuple, Optional, List
import math


class TributaryCalculator:
    """
    Calculate tributary areas for columns and walls using midpoint method

    This is the same approach used by structural software (Revit, ETABS, RISA)
    for determining load distribution to columns with variable spacing.
    """

    def __init__(self):
        """Initialize tributary calculator"""
        pass

    def calculate_column_tributary(
        self,
        spacing_north: float,
        spacing_south: float,
        spacing_east: float,
        spacing_west: float,
        is_edge: bool = False,
        edge_direction: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Calculate tributary area for a column using midpoint method

        Args:
            spacing_north: Distance to next column north (feet)
            spacing_south: Distance to next column south (feet)
            spacing_east: Distance to next column east (feet)
            spacing_west: Distance to next column west (feet)
            is_edge: True if column is on building edge
            edge_direction: 'north', 'south', 'east', or 'west' if on edge

        Returns:
            dict with:
                - 'tributary_area_sf': Total tributary area (SF)
                - 'tributary_length_x': Tributary dimension in X-direction (feet)
                - 'tributary_width_y': Tributary dimension in Y-direction (feet)
                - 'column_type': 'corner', 'edge', or 'interior'
        """
        # Calculate tributary dimensions in each direction (midpoint to each side)
        trib_x = (spacing_north / 2.0) + (spacing_south / 2.0)
        trib_y = (spacing_east / 2.0) + (spacing_west / 2.0)

        # For edge columns, tributary extends to building edge (full half-bay)
        # This is already captured in spacing values if edge_spacing = full_spacing
        # No adjustment needed

        # Determine column type
        edges_on = []
        if spacing_north == 0 or (is_edge and edge_direction == 'north'):
            edges_on.append('north')
        if spacing_south == 0 or (is_edge and edge_direction == 'south'):
            edges_on.append('south')
        if spacing_east == 0 or (is_edge and edge_direction == 'east'):
            edges_on.append('east')
        if spacing_west == 0 or (is_edge and edge_direction == 'west'):
            edges_on.append('west')

        if len(edges_on) >= 2:
            column_type = 'corner'
        elif len(edges_on) == 1:
            column_type = 'edge'
        else:
            column_type = 'interior'

        tributary_area = trib_x * trib_y

        return {
            'tributary_area_sf': tributary_area,
            'tributary_length_x': trib_x,
            'tributary_width_y': trib_y,
            'column_type': column_type,
            'spacing_north': spacing_north,
            'spacing_south': spacing_south,
            'spacing_east': spacing_east,
            'spacing_west': spacing_west
        }

    def calculate_uniform_grid_tributary(
        self,
        spacing_ft: float,
        column_type: str
    ) -> float:
        """
        Calculate tributary area for uniform grid (legacy compatibility)

        Args:
            spacing_ft: Uniform column spacing (feet)
            column_type: 'corner', 'edge', or 'interior'

        Returns:
            tributary_area_sf: Tributary area (SF)
        """
        if column_type == 'corner':
            # Quarter bay
            return (spacing_ft / 2.0) * (spacing_ft / 2.0)
        elif column_type == 'edge':
            # Half bay
            return spacing_ft * (spacing_ft / 2.0)
        else:  # interior
            # Full bay
            return spacing_ft * spacing_ft

    def calculate_wall_tributary_strip(
        self,
        bay_width_a: float,
        bay_width_b: Optional[float] = None,
        is_exterior: bool = False
    ) -> float:
        """
        Calculate tributary strip width for continuous footing under wall

        Args:
            bay_width_a: Width of bay on one side of wall (feet)
            bay_width_b: Width of bay on other side (feet), or None if exterior
            is_exterior: True if wall is on building perimeter

        Returns:
            tributary_width_ft: Width of tributary strip (feet)
        """
        if is_exterior or bay_width_b is None:
            # Exterior wall: gets half of adjacent bay
            return bay_width_a / 2.0
        else:
            # Interior wall: gets half of bay on each side
            return (bay_width_a / 2.0) + (bay_width_b / 2.0)

    def calculate_grid_tributary_areas(
        self,
        column_positions: List[Tuple[float, float]],
        building_length: float,
        building_width: float,
        grid_spacing_x: float,
        grid_spacing_y: float,
        tolerance_ft: float = 1.0
    ) -> Dict[Tuple[float, float], Dict]:
        """
        Calculate tributary areas for all columns in a grid

        Args:
            column_positions: List of (x, y) column coordinates
            building_length: Building length (feet)
            building_width: Building width (feet)
            grid_spacing_x: Typical grid spacing in X-direction (feet)
            grid_spacing_y: Typical grid spacing in Y-direction (feet)
            tolerance_ft: Tolerance for finding adjacent columns (feet)

        Returns:
            dict mapping (x, y) -> tributary area dict
        """
        results = {}

        for x, y in column_positions:
            # Find spacing to adjacent columns in each direction
            spacing_north = self._find_spacing_to_next(
                x, y, column_positions, direction='north',
                default_spacing=grid_spacing_x, max_edge=building_length, tolerance=tolerance_ft
            )
            spacing_south = self._find_spacing_to_next(
                x, y, column_positions, direction='south',
                default_spacing=grid_spacing_x, max_edge=0, tolerance=tolerance_ft
            )
            spacing_east = self._find_spacing_to_next(
                x, y, column_positions, direction='east',
                default_spacing=grid_spacing_y, max_edge=building_width, tolerance=tolerance_ft
            )
            spacing_west = self._find_spacing_to_next(
                x, y, column_positions, direction='west',
                default_spacing=grid_spacing_y, max_edge=0, tolerance=tolerance_ft
            )

            # Check if on edge
            is_edge = (
                abs(x) < tolerance_ft or
                abs(x - building_length) < tolerance_ft or
                abs(y) < tolerance_ft or
                abs(y - building_width) < tolerance_ft
            )

            edge_direction = None
            if abs(x) < tolerance_ft:
                edge_direction = 'south'
            elif abs(x - building_length) < tolerance_ft:
                edge_direction = 'north'
            elif abs(y) < tolerance_ft:
                edge_direction = 'west'
            elif abs(y - building_width) < tolerance_ft:
                edge_direction = 'east'

            # Calculate tributary
            tributary_data = self.calculate_column_tributary(
                spacing_north, spacing_south, spacing_east, spacing_west,
                is_edge=is_edge, edge_direction=edge_direction
            )

            results[(x, y)] = tributary_data

        return results

    def _find_spacing_to_next(
        self,
        x: float,
        y: float,
        all_positions: List[Tuple[float, float]],
        direction: str,
        default_spacing: float,
        max_edge: float,
        tolerance: float
    ) -> float:
        """
        Find spacing from column at (x,y) to next column in specified direction

        Args:
            x, y: Column position
            all_positions: All column positions
            direction: 'north', 'south', 'east', 'west'
            default_spacing: Default if no column found
            max_edge: Building edge coordinate in this direction
            tolerance: Search tolerance

        Returns:
            spacing_ft: Distance to next column or edge (feet)
        """
        # Define search direction
        if direction == 'north':
            # Increasing X, same Y
            candidates = [pos for pos in all_positions
                         if abs(pos[1] - y) < tolerance and pos[0] > x]
            if candidates:
                next_col = min(candidates, key=lambda p: p[0])
                return next_col[0] - x
            else:
                # No column found - check if at edge
                return max_edge - x if max_edge > x else default_spacing / 2.0

        elif direction == 'south':
            # Decreasing X, same Y
            candidates = [pos for pos in all_positions
                         if abs(pos[1] - y) < tolerance and pos[0] < x]
            if candidates:
                next_col = max(candidates, key=lambda p: p[0])
                return x - next_col[0]
            else:
                return x - max_edge if x > max_edge else default_spacing / 2.0

        elif direction == 'east':
            # Increasing Y, same X
            candidates = [pos for pos in all_positions
                         if abs(pos[0] - x) < tolerance and pos[1] > y]
            if candidates:
                next_col = min(candidates, key=lambda p: p[1])
                return next_col[1] - y
            else:
                return max_edge - y if max_edge > y else default_spacing / 2.0

        elif direction == 'west':
            # Decreasing Y, same X
            candidates = [pos for pos in all_positions
                         if abs(pos[0] - x) < tolerance and pos[1] < y]
            if candidates:
                next_col = max(candidates, key=lambda p: p[1])
                return y - next_col[1]
            else:
                return y - max_edge if y > max_edge else default_spacing / 2.0

        return default_spacing / 2.0  # Fallback


def calculate_tributary_area_simple(
    spacing_to_neighbors: Dict[str, float]
) -> float:
    """
    Simple helper function for quick tributary area calculation

    Args:
        spacing_to_neighbors: dict with 'north', 'south', 'east', 'west' keys

    Returns:
        tributary_area_sf: Tributary area (SF)

    Example:
        >>> area = calculate_tributary_area_simple({
        ...     'north': 45, 'south': 31, 'east': 31, 'west': 31
        ... })
        >>> # Returns: (45/2 + 31/2) * (31/2 + 31/2) = 38 * 31 = 1178 SF
    """
    trib_x = (spacing_to_neighbors['north'] / 2.0) + (spacing_to_neighbors['south'] / 2.0)
    trib_y = (spacing_to_neighbors['east'] / 2.0) + (spacing_to_neighbors['west'] / 2.0)
    return trib_x * trib_y
