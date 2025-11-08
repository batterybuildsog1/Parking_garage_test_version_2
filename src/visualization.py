"""
3D Visualization engine for split-level parking garage

Generates interactive Plotly 3D models showing:
- Sloped floor slabs (THE slabs ARE the ramps at 5% slope)
- Discrete level geometry (half-levels at 50% footprint)
- Structural column grid
- Core walls (ramp bay dividers)
- Optional circulation path visualization

**CRITICAL UNDERSTANDING:**
In split-level parking, the FLOOR SLABS themselves form the ramping surface.
There is NO separate "ramp" structure - slabs continuously slope at 5%.
At any given elevation, multiple sloping slabs intersect creating discrete parking levels.

Optimized for performance with trace consolidation and caching.
Designed for Streamlit integration with interactive controls.
"""

import plotly.graph_objects as go
import numpy as np
from typing import Dict, List, Tuple, Optional
from .garage import SplitLevelParkingGarage


# ===== COLOR PALETTE =====
# Architectural color scheme for building elements

COLORS = {
    # Floor slabs (which ARE the ramps)
    'slab_sog': 'rgb(139, 90, 43)',  # Brown for slab-on-grade
    'slab_suspended': 'rgb(200, 200, 200)',  # Light gray for elevated slabs
    'slab_edge': 'rgb(100, 100, 100)',  # Dark gray for slab edges

    # Structure
    'column': 'rgb(80, 80, 80)',  # Dark gray for columns
    'core_wall': 'rgb(100, 120, 140)',  # Blue-gray for core walls
    'wall_edge': 'rgb(70, 90, 110)',  # Darker for wall edges

    # Circulation visualization (optional overlay)
    'circulation': 'rgba(255, 140, 0, 0.8)',  # Orange for circulation paths
    'circulation_edge': 'rgb(200, 100, 0)',  # Darker orange

    # Exterior
    'exterior_screen': 'rgba(220, 220, 220, 0.3)',  # Very transparent light gray

    # Gradients for floor level visualization
    'floor_gradient_low': 'rgb(180, 150, 120)',  # Warm brown (lower floors)
    'floor_gradient_high': 'rgb(150, 170, 190)',  # Cool blue-gray (upper floors)
}


# ===== CAMERA PRESETS =====
# Standard architectural viewing angles

CAMERA_PRESETS = {
    'isometric': dict(
        eye=dict(x=1.5, y=1.5, z=1.2),
        center=dict(x=0.5, y=0.5, z=0.3),
        up=dict(x=0, y=0, z=1),
        projection=dict(type='orthographic')
    ),
    'plan': dict(
        eye=dict(x=0.5, y=0.5, z=3.0),  # Top-down view
        center=dict(x=0.5, y=0.5, z=0),
        up=dict(x=0, y=1, z=0),  # Y is up in plan view
        projection=dict(type='orthographic')
    ),
    'elevation_front': dict(
        eye=dict(x=0.5, y=-2.0, z=0.3),  # Front elevation (looking from south)
        center=dict(x=0.5, y=0.5, z=0.3),
        up=dict(x=0, y=0, z=1),
        projection=dict(type='orthographic')
    ),
    'elevation_side': dict(
        eye=dict(x=-2.0, y=0.5, z=0.3),  # Side elevation (looking from west)
        center=dict(x=0.5, y=0.5, z=0.3),
        up=dict(x=0, y=0, z=1),
        projection=dict(type='orthographic')
    ),
    'perspective': dict(
        eye=dict(x=1.8, y=1.8, z=0.8),
        center=dict(x=0.5, y=0.5, z=0.3),
        up=dict(x=0, y=0, z=1),
        projection=dict(type='perspective')
    )
}


# ===== HELPER FUNCTIONS =====

def normalize_coordinates(garage: SplitLevelParkingGarage, x: float, y: float, z: float) -> Tuple[float, float, float]:
    """
    Normalize coordinates to 0-1 range for camera positioning

    Args:
        garage: Garage geometry object
        x, y, z: Coordinates in feet

    Returns:
        Normalized (x, y, z) tuple
    """
    x_norm = x / garage.length if garage.length > 0 else 0
    y_norm = y / garage.width if garage.width > 0 else 0

    # Z normalization: center around grade (0), scale by total height
    z_range = garage.total_height_ft + garage.depth_below_grade_ft
    z_norm = (z + garage.depth_below_grade_ft) / z_range if z_range > 0 else 0

    return x_norm, y_norm, z_norm


def create_sloped_surface_mesh(x_start: float, x_end: float,
                               y_start: float, y_end: float,
                               z_south: float, z_north: float,
                               color: str, name: str = '',
                               opacity: float = 0.7,
                               thickness: float = 0.67) -> go.Mesh3d:
    """
    Create a sloped rectangular surface (slab) that ramps from south to north

    **This represents the actual ramping floor slab in split-level parking.**
    The slab slopes continuously at 5% from one end to the other.

    Args:
        x_start, x_end: Length extent (south to north in building)
        y_start, y_end: Width extent
        z_south: Elevation at south end (x=x_start)
        z_north: Elevation at north end (x=x_end)
        color: RGB color string
        name: Trace name
        opacity: Transparency
        thickness: Slab thickness in feet

    Returns:
        Plotly Mesh3d trace representing sloped slab
    """
    # 8 vertices: 4 on bottom surface, 4 on top surface
    # Bottom surface slopes from z_south to z_north
    # Top surface is bottom + thickness

    # Bottom surface vertices (counterclockwise from south-west)
    x_bottom = [x_start, x_end, x_end, x_start]
    y_bottom = [y_start, y_start, y_end, y_end]
    z_bottom = [z_south, z_north, z_north, z_south]  # Slopes from south to north

    # Top surface (parallel to bottom, offset by thickness)
    x_top = [x_start, x_end, x_end, x_start]
    y_top = [y_start, y_start, y_end, y_end]
    z_top = [z_south + thickness, z_north + thickness, z_north + thickness, z_south + thickness]

    # Combine into single vertex list
    x = x_bottom + x_top
    y = y_bottom + y_top
    z = z_bottom + z_top

    # Define triangular faces (12 triangles for 6 faces)
    # Bottom face: 0,1,2,3
    # Top face: 4,5,6,7
    # Sides: connect bottom to top

    i = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 0, 0]
    j = [1, 3, 2, 5, 3, 6, 0, 7, 5, 7, 4, 1]
    k = [2, 2, 6, 6, 7, 7, 4, 4, 6, 6, 7, 5]

    return go.Mesh3d(
        x=x, y=y, z=z,
        i=i, j=j, k=k,
        color=color,
        opacity=opacity,
        name=name,
        showlegend=bool(name),
        hovertemplate=f"<b>{name}</b><br>X: %{{x:.1f}}'<br>Y: %{{y:.1f}}'<br>Z: %{{z:.1f}}'<extra></extra>" if name else None
    )


# ===== MAIN VISUALIZATION FUNCTIONS =====

def create_sloped_slabs(garage: SplitLevelParkingGarage,
                       show_half_levels: bool = True,
                       color_by_elevation: bool = True,
                       simplify: bool = False) -> List[go.Mesh3d]:
    """
    Create CONTINUOUS HELICAL SLOPED slabs that form the ramping parking surface

    **CRITICAL:** These slabs ARE the ramps. They slope continuously at 5% from
    south to north (along X/length axis) in the ramping sections.

    **Helical Geometry:**
    - West bay: slopes in one direction (e.g., up from south to north)
    - East bay: slopes in OPPOSITE direction (down from south to north, up from north to south)
    - Flat turn zones at north/south ends (first/last TURN_ZONE_DEPTH feet)
    - The slabs are CONTINUOUS and CONNECTED, forming a helical ramp system

    Args:
        garage: Garage geometry object
        show_half_levels: Whether to render half-level intersection planes
        color_by_elevation: Use gradient coloring by floor level
        simplify: If True, show simplified horizontal planes (legacy mode)

    Returns:
        List of Mesh3d traces for continuous helical sloped slabs
    """
    traces = []
    slab_thickness = 0.67  # 8" thick slabs = 0.67 feet

    # Get key dimensions
    turn_zone = garage.TURN_ZONE_DEPTH  # 48' flat zones at each end
    ramp_length = garage.length - (2 * turn_zone)  # Sloping section length
    slope = garage.RAMP_SLOPE  # 5% = 0.05
    floor_to_floor = garage.FLOOR_TO_FLOOR  # 10.656'

    # Calculate bay widths (each bay is one half of the total width minus core walls)
    # For 2 bays: each bay is approximately width/2
    bay_width = garage.width / garage.num_bays

    # SPECIAL CASE: P0.5 (Ground Floor) - Entirely FLAT with north entrance cutout
    # North entrance: 30' wide centered opening at X = garage.length (north edge)
    # No ramping occurs on P0.5 - it's all circulation at z = 0

    entrance_width = 30.0  # feet
    entrance_y_center = garage.width / 2
    entrance_y_start = entrance_y_center - (entrance_width / 2)
    entrance_y_end = entrance_y_center + (entrance_width / 2)

    # P0.5 ground floor (level_idx == 0)
    z_p05 = 0 if garage.half_levels_below == 0 else -garage.depth_below_grade_ft
    color_p05 = COLORS['slab_sog']  # Ground floor is slab-on-grade

    # Create P0.5 slabs with entrance cutout
    # North turn zone with entrance opening (X = length-turn_zone to X = length)
    # Split into west and east segments around entrance

    # North west of entrance
    trace_north_w = create_sloped_surface_mesh(
        garage.length - turn_zone, garage.length,
        0, entrance_y_start,  # West of entrance
        z_p05, z_p05,  # Flat
        color=color_p05,
        name='P0.5 North Turn (West)',
        opacity=0.7,
        thickness=slab_thickness
    )
    traces.append(trace_north_w)

    # North east of entrance
    trace_north_e = create_sloped_surface_mesh(
        garage.length - turn_zone, garage.length,
        entrance_y_end, garage.width,  # East of entrance
        z_p05, z_p05,  # Flat
        color=color_p05,
        name='P0.5 North Turn (East)',
        opacity=0.7,
        thickness=slab_thickness
    )
    traces.append(trace_north_e)

    # Middle sections - both bays FLAT on P0.5
    for bay_idx in range(garage.num_bays):
        y_start = bay_idx * bay_width
        y_end = (bay_idx + 1) * bay_width

        trace_middle = create_sloped_surface_mesh(
            turn_zone, garage.length - turn_zone,
            y_start, y_end,
            z_p05, z_p05,  # Flat
            color=color_p05,
            name=f'P0.5 Bay {bay_idx+1} (Flat Circulation)',
            opacity=0.7,
            thickness=slab_thickness
        )
        traces.append(trace_middle)

    # South turn zone - FLAT on P0.5
    trace_south_p05 = create_sloped_surface_mesh(
        0, turn_zone,
        0, garage.width,
        z_p05, z_p05,  # Flat
        color=color_p05,
        name='P0.5 South Turn',
        opacity=0.7,
        thickness=slab_thickness
    )
    traces.append(trace_south_p05)

    # NOW create helical ramp slabs for levels P1 and above
    # Starting from level_idx = 1 (NOT 0, since we handled P0.5 above)

    for bay_idx in range(garage.num_bays):
        # Calculate Y position for this bay
        y_start = bay_idx * bay_width
        y_end = (bay_idx + 1) * bay_width

        # Start from level 1 (P1) since P0.5 is handled above
        for level_idx in range(1, garage.total_levels + 1):
            # Calculate elevations for this segment
            z_start = level_idx * floor_to_floor - garage.depth_below_grade_ft
            z_end = (level_idx + 1) * floor_to_floor - garage.depth_below_grade_ft

            # Determine level name for this segment
            level_name = garage.get_level_name(level_idx)
            level_num = float(level_name.replace('P', ''))

            # Skip half-levels if not showing them
            if not show_half_levels and (level_num % 1.0) != 0:
                continue

            # Skip if this is beyond the top level
            if level_idx >= garage.total_levels:
                break

            # Determine color
            if color_by_elevation:
                total_levels = garage.total_levels
                ratio = level_idx / total_levels if total_levels > 1 else 0.5
                low_rgb = (180, 150, 120)
                high_rgb = (150, 170, 190)
                r = int(low_rgb[0] + (high_rgb[0] - low_rgb[0]) * ratio)
                g = int(low_rgb[1] + (high_rgb[1] - low_rgb[1]) * ratio)
                b = int(low_rgb[2] + (high_rgb[2] - low_rgb[2]) * ratio)
                color = f'rgb({r}, {g}, {b})'
            else:
                slab_type = 'suspended' if level_idx > 2 else 'sog'
                color = COLORS['slab_sog'] if slab_type == 'sog' else COLORS['slab_suspended']

            # Determine slope direction based on bay and level
            # The two bays slope in OPPOSITE directions
            # Bay 0 slopes UP south→north on even levels, DOWN on odd levels
            # Bay 1 slopes DOWN south→north on even levels, UP on odd levels
            if bay_idx == 0:
                slope_direction = 1 if (level_idx % 2) == 0 else -1
            else:
                slope_direction = -1 if (level_idx % 2) == 0 else 1

            # Create three sections for this level segment

            # 1. South turn zone (FLAT)
            if turn_zone > 0:
                trace_south = create_sloped_surface_mesh(
                    0, turn_zone,
                    y_start, y_end,
                    z_start, z_start,  # Flat
                    color=color,
                    name=f'{level_name} Bay {bay_idx+1} (South)',
                    opacity=0.7,
                    thickness=slab_thickness
                )
                traces.append(trace_south)

            # 2. Middle ramping section (SLOPED at 5%)
            # This section rises by half the floor-to-floor height
            rise = (floor_to_floor / 2) * slope_direction
            z_south_ramp = z_start
            z_north_ramp = z_start + rise

            trace_ramp = create_sloped_surface_mesh(
                turn_zone, garage.length - turn_zone,
                y_start, y_end,
                z_south_ramp, z_north_ramp,  # SLOPES 5%
                color=color,
                name=f'{level_name} Bay {bay_idx+1}',
                opacity=0.7,
                thickness=slab_thickness
            )
            traces.append(trace_ramp)

            # 3. North turn zone (FLAT)
            if turn_zone > 0:
                trace_north = create_sloped_surface_mesh(
                    garage.length - turn_zone, garage.length,
                    y_start, y_end,
                    z_north_ramp, z_north_ramp,  # Flat at end elevation
                    color=color,
                    name=f'{level_name} Bay {bay_idx+1} (North)',
                    opacity=0.7,
                    thickness=slab_thickness
                )
                traces.append(trace_north)

    return traces


def create_structural_columns(garage: SplitLevelParkingGarage,
                              consolidate: bool = True) -> go.Scatter3d:
    """
    Create structural column grid on 31' spacing

    Consolidates all columns into single Scatter3d trace for performance.
    Columns extend from bottom of excavation to top of structure.

    Args:
        garage: Garage geometry object
        consolidate: Combine all columns in one trace (recommended for performance)

    Returns:
        Single Scatter3d trace with all columns
    """
    # Get column positions from geometry
    geom_data = garage.get_3d_geometry()
    columns = geom_data['columns']

    if consolidate:
        # Combine all columns into single trace with None separators
        x_coords = []
        y_coords = []
        z_coords = []

        for col in columns:
            x_coords.extend([col['x'], col['x'], None])
            y_coords.extend([col['y'], col['y'], None])
            z_coords.extend([col['z_bottom'], col['z_top'], None])

        trace = go.Scatter3d(
            x=x_coords,
            y=y_coords,
            z=z_coords,
            mode='lines',
            line=dict(
                color=COLORS['column'],
                width=6
            ),
            name=f'Structural Columns ({len(columns)} total)',
            legendgroup='columns',
            hovertemplate="<b>Column</b><br>X: %{x:.1f}'<br>Y: %{y:.1f}'<extra></extra>"
        )

        return trace

    else:
        # Return list of individual traces (slower, but more flexibility)
        traces = []
        for col in columns:
            trace = go.Scatter3d(
                x=[col['x'], col['x']],
                y=[col['y'], col['y']],
                z=[col['z_bottom'], col['z_top']],
                mode='lines',
                line=dict(color=COLORS['column'], width=6),
                showlegend=False,
                hovertemplate=f"<b>Column</b><br>Grid: ({col['x']:.0f}', {col['y']:.0f}')<extra></extra>"
            )
            traces.append(trace)

        return traces


def create_core_walls(garage: SplitLevelParkingGarage) -> List[go.Mesh3d]:
    """
    Create center columns, spandrel beams, and curbs that divide ramp bays

    REPLACES old solid wall design with beam-on-column system:
    - 32" × 24" columns at 31' spacing (larger than perimeter 18" × 24")
    - 32" × 8" spandrel beams between columns (structural + vehicle barrier)
    - 12" × 12" curbs on west/east sides (wheel stops protect beams)

    CRITICAL: Center elements ONLY in RAMP sections (NOT through turn zones)
    Number of center lines = num_bays - 1 (one line between each bay pair)

    Args:
        garage: Garage geometry object

    Returns:
        List of Mesh3d traces for center columns, beams, and curbs
    """
    traces = []

    # Get center element data from geometry
    geom_data = garage.get_3d_geometry()
    center_columns = geom_data.get('center_columns', [])
    center_beams = geom_data.get('center_beams', [])
    center_curbs = geom_data.get('center_curbs', [])

    # === CENTER COLUMNS (32" × 24" - larger than perimeter) ===
    for col_idx, col_data in enumerate(center_columns):
        x = col_data['x']
        y = col_data['y']
        width = col_data['width']  # 2.67' (32")
        depth = col_data['depth']  # 2.0' (24")
        z_bottom = col_data['z_bottom']
        z_top = col_data['z_top']

        # Create column box (centered on x, y)
        trace_column = create_sloped_surface_mesh(
            x - depth/2, x + depth/2,  # X extent (24" depth)
            y - width/2, y + width/2,  # Y extent (32" width)
            z_bottom, z_bottom,  # Flat base
            color='rgb(100, 100, 120)',  # Darker gray/blue for center columns
            name=f'Center Column {col_idx+1}',
            opacity=0.9,
            thickness=z_top - z_bottom  # Full height
        )
        traces.append(trace_column)

    # === CENTER SPANDREL BEAMS (32" × 8") ===
    for beam_idx, beam_data in enumerate(center_beams):
        x_start = beam_data['x_start']
        x_end = beam_data['x_end']
        y_center = beam_data['y_center']
        beam_width = beam_data['width']  # 0.67' (8")
        beam_height = beam_data['height']  # 2.67' (32")
        z_bottom = beam_data['z_bottom']

        # Spandrel beam (horizontal beam between columns at floor level)
        trace_beam = create_sloped_surface_mesh(
            x_start, x_end,
            y_center - beam_width/2, y_center + beam_width/2,  # 8" wide beam
            z_bottom, z_bottom,  # At floor level
            color='rgb(140, 120, 100)',  # Tan/brown for structural beams
            name=f'Spandrel Beam {beam_idx+1}',
            opacity=0.85,
            thickness=beam_height  # 32" tall (above floor)
        )
        traces.append(trace_beam)

    # === CENTER CURBS (12" × 12" wheel stops) ===
    for curb_idx, curb_data in enumerate(center_curbs):
        x_start = curb_data['x_start']
        x_end = curb_data['x_end']
        y_west = curb_data['y_west']
        y_east = curb_data['y_east']
        curb_width = curb_data['curb_width']  # 1.0' (12")
        curb_height = curb_data['curb_height']  # 1.0' (12")
        z_bottom = curb_data['z_bottom']

        # WEST CURB (12" × 12")
        trace_curb_west = create_sloped_surface_mesh(
            x_start, x_end,
            y_west, y_west + curb_width,  # 1' wide
            z_bottom, z_bottom,  # At floor level
            color='rgb(160, 160, 160)',  # Light gray for curbs
            name=f'Center Curb {curb_idx+1} West',
            opacity=0.7,
            thickness=curb_height  # 12" tall
        )
        traces.append(trace_curb_west)

        # EAST CURB (12" × 12")
        trace_curb_east = create_sloped_surface_mesh(
            x_start, x_end,
            y_east, y_east + curb_width,  # 1' wide
            z_bottom, z_bottom,  # At floor level
            color='rgb(160, 160, 160)',  # Light gray for curbs
            name=f'Center Curb {curb_idx+1} East',
            opacity=0.7,
            thickness=curb_height  # 12" tall
        )
        traces.append(trace_curb_east)

    return traces


def create_north_entrance(garage: SplitLevelParkingGarage) -> List[go.Mesh3d]:
    """
    Create north entrance opening with DOWN ramp from street to P0.5

    Street level entrance: z = 0 (grade)
    P0.5 parking level: z = -depth_below_grade (typically -10.66')
    Ramp slopes DOWN from north (street) to parking level

    Args:
        garage: Garage geometry object

    Returns:
        List of Mesh3d traces for entrance ramp and walls
    """
    traces = []

    # Entrance parameters
    entrance_width = 30.0  # feet
    entrance_y_center = garage.width / 2
    entrance_y_start = entrance_y_center - (entrance_width / 2)
    entrance_y_end = entrance_y_center + (entrance_width / 2)

    # Elevations
    street_grade = 0.0  # Street level at grade
    p05_level = -garage.depth_below_grade_ft  # P0.5 below grade

    # Entrance ramp extends from street down to P0.5
    # 10% slope for entrance ramp (max per code)
    vertical_drop = abs(street_grade - p05_level)  # ~10.66'
    entrance_slope = 0.10  # 10%
    ramp_length = vertical_drop / entrance_slope  # ~107' for 10.66' drop

    # Ramp starts at building north edge and extends outward
    ramp_x_start = garage.length  # North edge of building
    ramp_x_end = garage.length + ramp_length  # Extends north from building

    # DOWN ramp surface (slopes from street grade down to P0.5)
    trace_ramp = create_sloped_surface_mesh(
        ramp_x_start, ramp_x_end,
        entrance_y_start, entrance_y_end,
        p05_level, street_grade,  # Slopes UP from building to street
        color='rgb(90, 90, 90)',  # Dark gray for entrance ramp
        name='Entrance Down Ramp',
        opacity=0.8,
        thickness=0.67  # 8" thick
    )
    traces.append(trace_ramp)

    # Side walls along entrance
    wall_height = 4.0  # 4' tall
    wall_thickness = 0.5  # 6" thick

    # West side wall
    trace_wall_w = create_sloped_surface_mesh(
        ramp_x_start, ramp_x_end,
        entrance_y_start - wall_thickness, entrance_y_start,
        p05_level, street_grade,  # Matches ramp slope
        color='rgb(110, 110, 110)',
        name='Entrance West Wall',
        opacity=0.7,
        thickness=wall_height
    )
    traces.append(trace_wall_w)

    # East side wall
    trace_wall_e = create_sloped_surface_mesh(
        ramp_x_start, ramp_x_end,
        entrance_y_end, entrance_y_end + wall_thickness,
        p05_level, street_grade,  # Matches ramp slope
        color='rgb(110, 110, 110)',
        name='Entrance East Wall',
        opacity=0.7,
        thickness=wall_height
    )
    traces.append(trace_wall_e)

    return traces


def create_corner_cores(garage: SplitLevelParkingGarage) -> List[go.Mesh3d]:
    """
    Create corner cores with proper distinction between:
    - Actual structural walls (elevator shaft, stair enclosures)
    - Buffer/clearance zones (blocked for parking but not walls)

    NE Core breakdown:
    - Elevator shaft: 10'×10' concrete walls (8' interior + 1' walls)
    - Stair enclosure: 18'×27' concrete walls
    - Buffer zones: Remaining L-shaped area (clearances, access)

    Args:
        garage: Garage geometry object

    Returns:
        List of Mesh3d traces for structural walls and buffer zones
    """
    traces = []

    # Standard heights
    z_bottom = -garage.depth_below_grade_ft
    z_top = garage.total_height_ft - garage.depth_below_grade_ft

    # === NW UTILITY CORE (Solid room) ===
    # 20' × 19' utility room at southwest corner (X=0, Y=0)
    trace_nw = create_sloped_surface_mesh(
        0, 20,  # X: 20' along length
        0, 19,  # Y: 19' along width
        z_bottom, z_bottom,
        color='rgb(100, 80, 60)',  # Brown (utility room)
        name='NW Utility Room',
        opacity=0.7,
        thickness=z_top - z_bottom
    )
    traces.append(trace_nw)

    # === SW STORAGE CORE (Solid room) ===
    # 29' × 18' storage at southeast corner (X=length-29, Y=0)
    trace_sw = create_sloped_surface_mesh(
        garage.length - 29, garage.length,  # X: 29' from south end
        0, 18,  # Y: 18' wide
        z_bottom, z_bottom,
        color='rgb(100, 80, 60)',  # Brown (storage)
        name='SW Storage',
        opacity=0.7,
        thickness=z_top - z_bottom
    )
    traces.append(trace_sw)

    # === SE STAIR CORE ===
    # 18' × 27' stair enclosure at northeast corner
    # Position: northeast corner = (length-27, width-18) to (length, width)
    trace_se_stair = create_sloped_surface_mesh(
        garage.length - 27, garage.length,  # X: 27' from north edge
        garage.width - 18, garage.width,  # Y: 18' from east edge
        z_bottom, z_bottom,
        color='rgb(80, 80, 100)',  # Dark blue-gray (concrete stair)
        name='SE Stair Enclosure',
        opacity=0.8,
        thickness=z_top - z_bottom
    )
    traces.append(trace_se_stair)

    # === NE ELEVATOR + STAIR CORE (Complex L-shaped) ===
    # This is the problematic one - needs to show actual walls vs buffer zones

    # NE Core total footprint is L-shaped:
    # Main leg: 48' along north edge × 18' deep
    # Side leg: 18' × 18' extending from main leg
    # Total area: (48×18) + (18×18) = 1,188 SF

    # Position at northeast corner (top-right in plan)
    # North edge starts at X = garage.length - 18 (18' from north)
    # East edge at Y = garage.width (full width)

    # Component 1: ELEVATOR SHAFT (10'×10' concrete box)
    # Position: at northeast corner
    elevator_shaft_size = 10  # 10' × 10' exterior (8' interior + 1' walls each side)
    z_elev_bot = z_bottom - 8  # 8' pit below
    z_elev_top = z_top + 12  # 12' penthouse above

    trace_elevator = create_sloped_surface_mesh(
        garage.length - elevator_shaft_size, garage.length,  # X: 10' from north edge
        garage.width - elevator_shaft_size, garage.width,  # Y: 10' from east edge
        z_elev_bot, z_elev_bot,
        color='rgb(60, 60, 80)',  # Dark gray (concrete shaft)
        name='Elevator Shaft',
        opacity=0.9,
        thickness=z_elev_top - z_elev_bot
    )
    traces.append(trace_elevator)

    # Component 2: STAIR ENCLOSURE (18'×27')
    # Position: Along north edge, west of elevator
    stair_width = 18  # feet (north-south)
    stair_length = 27  # feet (east-west)

    trace_ne_stair = create_sloped_surface_mesh(
        garage.length - stair_width, garage.length,  # X: 18' from north edge
        garage.width - (elevator_shaft_size + stair_length), garage.width - elevator_shaft_size,  # Y: 27' west of elevator
        z_bottom, z_bottom,
        color='rgb(80, 80, 100)',  # Blue-gray (concrete stair)
        name='NE Stair Enclosure',
        opacity=0.8,
        thickness=z_top - z_bottom
    )
    traces.append(trace_ne_stair)

    # Component 3: BUFFER/CLEARANCE ZONES (remaining L-shaped area)
    # This shows the blocked parking area (not actual walls)

    # Buffer zone 1: North edge buffer (west of stair, along north edge)
    buffer_north_length = 48 - stair_length - elevator_shaft_size  # Remaining north edge
    if buffer_north_length > 0:
        trace_buffer_n = create_sloped_surface_mesh(
            garage.length - 18, garage.length,  # X: 18' from north
            garage.width - (elevator_shaft_size + stair_length + buffer_north_length),
            garage.width - (elevator_shaft_size + stair_length),  # Y: west of stair
            z_bottom, z_bottom,
            color='rgba(200, 200, 120, 0.3)',  # Yellow transparent (buffer zone)
            name='NE Buffer Zone (North)',
            opacity=0.3,
            thickness=z_top - z_bottom
        )
        traces.append(trace_buffer_n)

    # Buffer zone 2: Clearance around stair/elevator (18'×18' leg)
    # This is access circulation, clearances, etc.
    trace_buffer_access = create_sloped_surface_mesh(
        garage.length - 18 - 18, garage.length - 18,  # X: 18' south of north buffer
        garage.width - (elevator_shaft_size + stair_length), garage.width - elevator_shaft_size,  # Y: aligned with stair
        z_bottom, z_bottom,
        color='rgba(200, 200, 120, 0.3)',  # Yellow transparent
        name='NE Buffer Zone (Access)',
        opacity=0.3,
        thickness=z_top - z_bottom
    )
    traces.append(trace_buffer_access)

    return traces


def create_safety_barriers(garage: SplitLevelParkingGarage) -> List[go.Mesh3d]:
    """
    Create perimeter safety barriers and edge protection

    Per IBC 406.4.3: Vehicle barriers ≥33" where drop >1'
    Creates 36" barriers around perimeter on all levels.

    Args:
        garage: Garage geometry object

    Returns:
        List of Mesh3d traces for barriers
    """
    traces = []

    barrier_height = 3.0  # 36" (exceeds 33" code min)
    barrier_thickness = 0.5  # 6"

    # Create barriers on all levels
    for level_idx in range(garage.total_levels + 1):
        z_base = level_idx * garage.FLOOR_TO_FLOOR - garage.depth_below_grade_ft

        # North barrier (full width)
        trace_n = create_sloped_surface_mesh(
            garage.length - barrier_thickness, garage.length,
            0, garage.width,
            z_base, z_base,
            color='rgb(180, 180, 180)',  # Light gray
            name=f'L{level_idx} North Barrier',
            opacity=0.5,
            thickness=barrier_height
        )
        traces.append(trace_n)

        # South barrier (full width)
        trace_s = create_sloped_surface_mesh(
            0, barrier_thickness,
            0, garage.width,
            z_base, z_base,
            color='rgb(180, 180, 180)',
            name=f'L{level_idx} South Barrier',
            opacity=0.5,
            thickness=barrier_height
        )
        traces.append(trace_s)

        # West barrier (full length)
        trace_w = create_sloped_surface_mesh(
            0, garage.length,
            0, barrier_thickness,
            z_base, z_base,
            color='rgb(180, 180, 180)',
            name=f'L{level_idx} West Barrier',
            opacity=0.5,
            thickness=barrier_height
        )
        traces.append(trace_w)

        # East barrier (full length)
        trace_e = create_sloped_surface_mesh(
            0, garage.length,
            garage.width - barrier_thickness, garage.width,
            z_base, z_base,
            color='rgb(180, 180, 180)',
            name=f'L{level_idx} East Barrier',
            opacity=0.5,
            thickness=barrier_height
        )
        traces.append(trace_e)

    return traces


def create_top_level_features(garage: SplitLevelParkingGarage) -> List[go.Mesh3d]:
    """
    Create top level ramp termination and closure walls

    Closure walls prevent vehicles from continuing past ramp end.

    Args:
        garage: Garage geometry object

    Returns:
        List of Mesh3d traces for top level features
    """
    traces = []

    # Top level elevation
    top_level = garage.total_levels
    z_top = top_level * garage.FLOOR_TO_FLOOR - garage.depth_below_grade_ft

    # Closure parameters
    closure_height = 6.0  # 6' tall
    closure_thickness = 1.0  # 12" thick
    bay_width = garage.width / garage.num_bays

    # Closure at north end where ramps terminate
    closure_x = garage.TURN_ZONE_DEPTH

    # Create closure across each bay
    for bay in range(garage.num_bays):
        y_start = bay * bay_width
        y_end = (bay + 1) * bay_width

        trace = create_sloped_surface_mesh(
            closure_x - closure_thickness, closure_x,
            y_start, y_end,
            z_top, z_top,
            color='rgb(100, 100, 100)',
            name=f'Top Closure Bay {bay+1}',
            opacity=0.85,
            thickness=closure_height
        )
        traces.append(trace)

    return traces


def create_circulation_paths(garage: SplitLevelParkingGarage,
                            resolution: int = 100) -> List[go.Scatter3d]:
    """
    Create OPTIONAL visualization of circulation paths through the garage

    **NOTE:** This is NOT separate structure - it's just a visual guide showing
    how vehicles circulate through the sloped slab system.

    Useful for understanding traffic flow but not required for structural visualization.

    Args:
        garage: Garage geometry object
        resolution: Number of points per path (higher = smoother)

    Returns:
        List of Scatter3d traces showing circulation centerlines
    """
    traces = []

    # Circulation parameters
    ramp_width = 25  # Drive aisle width

    # Number of circulation paths = num_bays (one per bay)
    num_bays = garage.num_bays

    # For each bay, create circulation centerline showing 5% slope
    for bay in range(num_bays):
        # Bay centerline Y position
        # Bay 0: 0.5' wall + 18' + 12.5' (half of 25' aisle) = 31'
        bay_y_center = 0.5 + 18 + 12.5 + bay * (61 + garage.CORE_WALL_THICKNESS)

        # Create path along length (straight sections)
        x_path = np.linspace(garage.TURN_ZONE_DEPTH,
                            garage.length - garage.TURN_ZONE_DEPTH,
                            resolution)

        # Z elevation climbs linearly at 5% slope
        straight_length = garage.length - 2 * garage.TURN_ZONE_DEPTH
        z_path = np.linspace(0, straight_length * garage.RAMP_SLOPE, resolution)

        # Y remains constant (centerline of bay)
        y_path = np.full(resolution, bay_y_center)

        # Create centerline trace
        trace = go.Scatter3d(
            x=x_path,
            y=y_path,
            z=z_path,
            mode='lines',
            line=dict(
                color=COLORS['circulation_edge'],
                width=4,
                dash='dash'
            ),
            name=f'Circulation Path {bay+1}',
            legendgroup='circulation',
            showlegend=(bay == 0),  # Only show first in legend
            hovertemplate=f"<b>Circulation Path {bay+1}</b><br>Slope: 5%<br>Elevation: %{{z:.1f}}'<extra></extra>"
        )

        traces.append(trace)

    return traces


def setup_camera(fig: go.Figure, preset: str = 'isometric',
                 aspect_mode: str = 'data') -> go.Figure:
    """
    Configure 3D camera and scene settings

    Args:
        fig: Plotly figure object
        preset: Camera preset name (isometric, plan, elevation_front, elevation_side, perspective)
        aspect_mode: 'data' (proportional), 'cube' (equal axes), or 'manual'

    Returns:
        Updated figure
    """
    camera = CAMERA_PRESETS.get(preset.lower(), CAMERA_PRESETS['isometric'])

    fig.update_layout(
        scene=dict(
            camera=camera,
            aspectmode=aspect_mode,
            xaxis=dict(
                title='Length (feet)',
                backgroundcolor='rgb(240, 240, 240)',
                gridcolor='white',
                showbackground=True,
                zeroline=True,
                zerolinecolor='rgb(150, 150, 150)',
            ),
            yaxis=dict(
                title='Width (feet)',
                backgroundcolor='rgb(240, 240, 240)',
                gridcolor='white',
                showbackground=True,
                zeroline=True,
                zerolinecolor='rgb(150, 150, 150)',
            ),
            zaxis=dict(
                title='Elevation (feet)',
                backgroundcolor='rgb(230, 230, 240)',
                gridcolor='white',
                showbackground=True,
                zeroline=True,
                zerolinecolor='rgb(200, 100, 100)',
                zerolinewidth=2,
            )
        ),
        showlegend=True,
        legend=dict(
            x=0.02,
            y=0.98,
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='rgb(150, 150, 150)',
            borderwidth=1
        ),
        margin=dict(l=0, r=0, t=30, b=0)
    )

    return fig


def create_3d_parking_garage(garage: SplitLevelParkingGarage,
                              show_slabs: bool = True,
                              show_columns: bool = True,
                              show_walls: bool = True,
                              show_circulation: bool = False,
                              show_half_levels: bool = True,
                              show_barriers: bool = True,
                              show_cores: bool = True,
                              show_entrance: bool = True,
                              floor_range: Optional[Tuple[float, float]] = None,
                              camera_preset: str = 'isometric') -> go.Figure:
    """
    Create complete 3D visualization of parking garage

    Main entry point for generating interactive 3D model.
    Combines all building elements with optimized rendering.

    Args:
        garage: Garage geometry object
        show_slabs: Render floor slabs (which ARE the ramping structure)
        show_columns: Render structural columns
        show_walls: Render core walls
        show_circulation: Show optional circulation path overlays
        show_half_levels: Include half-level floor plates
        show_barriers: Render safety barriers and edge protection
        show_cores: Render corner cores (elevator, stairs, utility, storage)
        show_entrance: Render north entrance with down ramp
        floor_range: Optional (min_level, max_level) to filter floors
        camera_preset: Camera view preset name

    Returns:
        Plotly Figure object ready for display
    """
    fig = go.Figure()

    # Add floor slabs (THE RAMPS)
    if show_slabs:
        slab_traces = create_sloped_slabs(garage, show_half_levels=show_half_levels)

        # Filter by floor range if specified
        if floor_range:
            min_level, max_level = floor_range
            filtered_slabs = []
            for trace in slab_traces:
                # Extract level number from trace name
                level_str = trace.name.split()[0]  # "P0.5" from "P0.5 (SOG, 13860 SF)"
                level_num = float(level_str.replace('P', ''))
                if min_level <= level_num <= max_level:
                    filtered_slabs.append(trace)
            slab_traces = filtered_slabs

        for trace in slab_traces:
            fig.add_trace(trace)

    # Add structural columns
    if show_columns:
        column_trace = create_structural_columns(garage, consolidate=True)
        fig.add_trace(column_trace)

    # Add core walls
    if show_walls:
        wall_traces = create_core_walls(garage)
        for trace in wall_traces:
            fig.add_trace(trace)

    # Add optional circulation path visualization
    if show_circulation:
        circ_traces = create_circulation_paths(garage)
        for trace in circ_traces:
            fig.add_trace(trace)

    # Add corner cores (elevator, stairs, utility, storage)
    if show_cores:
        core_traces = create_corner_cores(garage)
        for trace in core_traces:
            fig.add_trace(trace)

    # Add safety barriers and edge protection
    if show_barriers:
        barrier_traces = create_safety_barriers(garage)
        for trace in barrier_traces:
            fig.add_trace(trace)

        # Add top level termination features
        top_traces = create_top_level_features(garage)
        for trace in top_traces:
            fig.add_trace(trace)

    # Add north entrance with down ramp
    if show_entrance:
        entrance_traces = create_north_entrance(garage)
        for trace in entrance_traces:
            fig.add_trace(trace)

    # Configure camera and scene
    fig = setup_camera(fig, preset=camera_preset, aspect_mode='data')

    # Update layout
    fig.update_layout(
        title=dict(
            text=f'{garage.num_bays}-Bay Split-Level Parking Garage<br>' +
                 f'<sub>{garage.width:.0f}\' × {garage.length:.0f}\' | ' +
                 f'{garage.total_levels} Levels | {garage.total_stalls} Stalls</sub>',
            x=0.5,
            xanchor='center'
        ),
        height=700
    )

    return fig
