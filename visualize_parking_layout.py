"""
2D Parking Layout Visualization Tool

Generates accurate 2D floor plans showing:
- Parking stalls (numbered and color-coded by zone)
- Aisles/ramps (25' wide circulation)
- Core walls (3' thick ramp dividers)
- Core blockages (4 corner cores)
- Turn zones (48' depth at ends)
- Entry opening (27' on west side)
- Ramp termination (30' at top level)
- Non-parkable zones

Creates both overview and per-half-level diagrams.

COORDINATE SYSTEM:
================================================================================
Geometry Engine (geometry.py):
- X-axis = building WIDTH (0 to 126' for 2-bay)
- Y-axis = building LENGTH (0 to 210')
- NORTH = y:0
- SOUTH = y:length (210')
- WEST = x:0
- EAST = x:width (126')

Matplotlib Visualization:
- X-axis = building LENGTH (0 to 210') - HORIZONTAL on screen
- Y-axis = building WIDTH (0 to 126') - VERTICAL on screen
- NORTH = x:0 (LEFT side of screen)
- SOUTH = x:length (RIGHT side of screen)
- WEST = y:0 (BOTTOM of screen)
- EAST = y:width (TOP of screen)

TRANSFORM: geo(x=width_pos, y=length_pos) → mpl(x=length_pos, y=width_pos)
================================================================================
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, Polygon
from matplotlib.collections import PatchCollection
import numpy as np

from src.garage import SplitLevelParkingGarage, ParkingLayout


# Color scheme
COLORS = {
    'north_turn': '#ADD8E6',  # Light blue
    'south_turn': '#87CEEB',  # Sky blue
    'west_row': '#90EE90',    # Light green
    'east_row': '#98FB98',    # Pale green
    'center': '#FFFFE0',      # Light yellow
    'aisle': '#D3D3D3',       # Light gray
    'core_wall': '#696969',   # Dim gray
    'core_blockage': '#FF6B6B',  # Red
    'exterior': '#333333',    # Dark gray
    'entry_opening': '#FFFFFF',  # White
}


def draw_building_outline(ax, width, length):
    """Draw exterior walls"""
    wall_thickness = 0.5

    # Exterior walls
    walls = [
        Rectangle((0, 0), length, wall_thickness, fc=COLORS['exterior'], ec='black', lw=1),  # South
        Rectangle((0, width - wall_thickness), length, wall_thickness, fc=COLORS['exterior'], ec='black', lw=1),  # North
        Rectangle((0, 0), wall_thickness, width, fc=COLORS['exterior'], ec='black', lw=1),  # West
        Rectangle((length - wall_thickness, 0), wall_thickness, width, fc=COLORS['exterior'], ec='black', lw=1),  # East
    ]

    for wall in walls:
        ax.add_patch(wall)


def draw_aisles(ax, width, length, num_bays):
    """Draw 25' wide aisles/ramps between parking strips"""
    # Aisle positions:
    # 0.5 + 18 (west row) = 18.5 → first aisle at 18.5 to 43.5
    # Then pattern: 18 (parking) + 3 (core) + 18 (parking) + 25 (aisle) repeats

    aisle_patches = []
    x_pos = 0.5 + 18  # After west row

    for bay in range(num_bays):
        # Aisle before this bay's center rows
        aisle = Rectangle((0, x_pos), length, 25, fc=COLORS['aisle'], ec='gray', lw=0.5, alpha=0.5)
        aisle_patches.append(aisle)

        # Move past aisle, parking, core, parking
        x_pos += 25 + 18 + 3 + 18

    for patch in aisle_patches:
        ax.add_patch(patch)


def draw_core_walls(ax, width, length, num_bays, turn_zone_depth=48):
    """Draw 3' thick core walls separating ramp bays"""
    # Core walls only extend through ramp section (not turn zones)
    wall_x_start = turn_zone_depth
    wall_x_end = length - turn_zone_depth

    num_core_walls = num_bays - 1
    core_wall_thickness = 3
    parking_module_width = 61

    for i in range(num_core_walls):
        # Calculate Y position
        core_y_center = (i + 1) * parking_module_width + i * core_wall_thickness + core_wall_thickness / 2
        core_y_start = core_y_center - core_wall_thickness / 2

        # Draw wall
        wall = Rectangle((wall_x_start, core_y_start), wall_x_end - wall_x_start, core_wall_thickness,
                        fc=COLORS['core_wall'], ec='black', lw=2, alpha=0.8)
        ax.add_patch(wall)

        # Label
        ax.text(length / 2, core_y_center, f'CORE WALL {i+1}\n(3\' thick)',
               ha='center', va='center', fontsize=7, fontweight='bold', color='white')


def draw_core_blockages(ax, width, length):
    """
    Draw 4 corner cores with hatching

    COORDINATE TRANSFORM:
    - Geometry: corners defined by position along width (x) and length (y)
    - Matplotlib: x-axis = length, y-axis = width
    - Transform: geo(x=width_pos, y=length_pos) → mpl(x=length_pos, y=width_pos)

    CORNER POSITIONS (geometry coordinates):
    - NW: x=0 (west), y=0 (north) → blocks y:[0-20']
    - NE: x=width (east), y=0 (north) → blocks y:[0-49']
    - SE: x=width (east), y=length (south) → blocks y:[length-28' to length]
    - SW: x=0 (west), y=length (south) → blocks y:[length-29' to length]
    """
    # Core definitions matching geometry.py
    cores = [
        {'corner': 'NW', 'type': 'Utility', 'y_block': 20, 'x_block': 19},
        {'corner': 'NE', 'type': 'Elev/Stair', 'y_block': 49, 'x_block': 37},  # L-shaped
        {'corner': 'SE', 'type': 'Stair', 'y_block': 28, 'x_block': 10},       # L-shaped
        {'corner': 'SW', 'type': 'Storage', 'y_block': 29, 'x_block': 18},
    ]

    for core in cores:
        y_blockage = core['y_block']  # Blockage along length axis
        x_blockage = core['x_block']  # Blockage along width axis

        # Calculate matplotlib (x, y) positions based on corner
        if core['corner'] == 'NW':
            # North (y=0) + West (x=0) → mpl: x=0, y=0
            mpl_x = 0
            mpl_y = 0
            mpl_width = y_blockage   # Along length axis
            mpl_height = x_blockage  # Along width axis
        elif core['corner'] == 'NE':
            # North (y=0) + East (x=width) → mpl: x=0, y=width-x_block
            mpl_x = 0
            mpl_y = width - x_blockage
            mpl_width = y_blockage
            mpl_height = x_blockage
        elif core['corner'] == 'SE':
            # South (y=length) + East (x=width) → mpl: x=length-y_block, y=width-x_block
            mpl_x = length - y_blockage
            mpl_y = width - x_blockage
            mpl_width = y_blockage
            mpl_height = x_blockage
        else:  # SW
            # South (y=length) + West (x=0) → mpl: x=length-y_block, y=0
            mpl_x = length - y_blockage
            mpl_y = 0
            mpl_width = y_blockage
            mpl_height = x_blockage

        # Draw core
        rect = Rectangle((mpl_x, mpl_y), mpl_width, mpl_height,
                       fc=COLORS['core_blockage'], ec='darkred', lw=2, hatch='///', alpha=0.6)
        ax.add_patch(rect)

        # Label at center
        ax.text(mpl_x + mpl_width/2, mpl_y + mpl_height/2,
               f"{core['corner']}\n{core['type']}", ha='center', va='center',
               fontsize=6, fontweight='bold', color='white')


def draw_turn_zones(ax, width, length, turn_zone_depth=48):
    """
    Draw turn zones at north and south ends

    COORDINATE SYSTEM:
    - Geometry engine: north = y:[0-48'], south = y:[162-210'] (length axis)
    - Matplotlib: x-axis = length, y-axis = width
    - Transform: geometry(x=width, y=length) → matplotlib(x=length, y=width)
    """
    # North turn zone: geometry y:[0-48'] → matplotlib x:[0-48']
    north_zone = Rectangle((0, 0), turn_zone_depth, width,
                          fc=COLORS['north_turn'], ec='blue', lw=1, alpha=0.3)
    ax.add_patch(north_zone)
    ax.text(turn_zone_depth/2, width/2, 'NORTH TURN ZONE\n(48\' depth)',
           ha='center', va='center', fontsize=8, style='italic', color='darkblue')

    # South turn zone: geometry y:[162-210'] → matplotlib x:[162-210']
    south_zone = Rectangle((length - turn_zone_depth, 0), turn_zone_depth, width,
                          fc=COLORS['south_turn'], ec='blue', lw=1, alpha=0.3)
    ax.add_patch(south_zone)
    ax.text(length - turn_zone_depth/2, width/2, 'SOUTH TURN ZONE\n(48\' depth)',
           ha='center', va='center', fontsize=8, style='italic', color='darkblue')


def draw_entry_opening(ax, width, length, entry_width=27):
    """Draw entry opening on west side at mid-length"""
    entry_center = length / 2
    entry_y_start = entry_center - entry_width / 2
    entry_y_end = entry_center + entry_width / 2

    # Draw opening (white rectangle)
    opening = Rectangle((entry_y_start, 0), entry_width, 18.5,
                       fc=COLORS['entry_opening'], ec='green', lw=3)
    ax.add_patch(opening)

    # Arrow pointing in
    ax.annotate('ENTRY', xy=(entry_center, 9), xytext=(entry_center - 30, 9),
               arrowprops=dict(arrowstyle='->', lw=2, color='green'),
               fontsize=9, fontweight='bold', color='green', ha='right', va='center')


def draw_ramp_termination(ax, width, length, termination_length=30):
    """Draw ramp termination zone at north end (top level only)"""
    # This is a non-parkable zone at top level
    term_zone = Rectangle((length - termination_length, 0), termination_length, width,
                         fc='white', ec='red', lw=2, ls='--', alpha=0.3)
    ax.add_patch(term_zone)
    ax.text(length - termination_length/2, width/2, 'RAMP\nTERMINATION\n(Top Level Only)',
           ha='center', va='center', fontsize=7, style='italic', color='darkred')


def calculate_turn_zone_stall_start(zone, width, num_stalls):
    """
    Calculate the starting Y-position for turn zone stalls to center them
    between the corner core blockages.

    Turn zone stalls run EAST-WEST along the building width.
    They must avoid overlapping the corner cores.

    Args:
        zone: 'north' or 'south'
        width: Building width (126' for 2-bay)
        num_stalls: Number of stalls to draw

    Returns:
        Y-coordinate (matplotlib) to start drawing stalls
    """
    # Core blockages (from geometry.py)
    if zone == 'north':
        west_core_width = 19  # NW utility core blocks 19' from west edge
        east_core_width = 37  # NE elevator core blocks 37' from east edge
    else:  # south
        west_core_width = 18  # SW storage core blocks 18' from west edge
        east_core_width = 10  # SE stair core blocks 10' from east edge

    # Calculate available width for parking
    wall_thickness = 0.5  # Each exterior wall
    available_width = width - (2 * wall_thickness) - west_core_width - east_core_width

    # Calculate total stall width
    stall_width = 9  # Each stall is 9' wide
    total_stall_width = num_stalls * stall_width

    # Calculate wasted space and center stalls
    wasted_space = available_width - total_stall_width
    offset = wasted_space / 2

    # Start position: after west wall + west core + half of wasted space
    start_y = wall_thickness + west_core_width + offset

    return start_y


def find_optimal_increment(width, length, num_bays, max_search=18):
    """
    DEPRECATED: Use ParkingLayout.calculate_length_optimization() instead.

    This function is kept for backward compatibility but will be removed in future versions.
    The optimization logic has been moved to geometry.py for better separation of concerns.

    Args:
        width: Building width in feet
        length: Current building length in feet
        num_bays: Number of parking bays (2-7)
        max_search: Maximum feet to search (default 18, covers up to 2 stalls/row)

    Returns:
        dict with optimization results (see ParkingLayout.calculate_length_optimization)
    """
    # Create base layout to get current state
    base_layout = ParkingLayout(width=width, length=length, num_bays=num_bays)
    base_layout.apply_core_blockages()

    # Get base stall counts and excess space
    base_stalls_by_row = {}
    excess_by_row = {}
    for section in base_layout.sections:
        if section.section_type in ['full_length', 'middle_only']:
            stalls, wasted = section.calculate_stalls()
            base_stalls_by_row[section.name] = stalls
            excess_by_row[section.name] = wasted

    # Simulate adding 1 to max_search feet
    results = []
    for add_ft in range(1, max_search + 1):
        new_layout = ParkingLayout(width=width, length=length + add_ft, num_bays=num_bays)
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
            results.append({
                'add_ft': add_ft,
                'total_gain': total_gain,
                'efficiency': efficiency,
                'gains_detail': gains_detail,
                'new_excess': new_excess
            })

    if not results:
        return None

    # Find the PEAK efficiency (highest stalls/ft ratio)
    peak = max(results, key=lambda x: x['efficiency'])

    # Find the dead zone: where peak's total_gain persists without improvement
    peak_gain = peak['total_gain']
    results_at_peak_gain = [r for r in results if r['total_gain'] == peak_gain]
    last_at_peak_gain = max(results_at_peak_gain, key=lambda x: x['add_ft'])

    dead_zone_start = None
    if last_at_peak_gain['add_ft'] > peak['add_ft']:
        dead_zone_start = peak['add_ft'] + 1

    # Find next meaningful threshold after dead zone
    next_threshold = None
    if dead_zone_start:
        future_gains = [r for r in results if r['add_ft'] > last_at_peak_gain['add_ft']
                       and r['total_gain'] > peak_gain]
        if future_gains:
            next_threshold = min(future_gains, key=lambda x: x['add_ft'])

    return {
        'optimal_ft': peak['add_ft'],
        'total_gain': peak['total_gain'],
        'efficiency': peak['efficiency'],
        'gains_detail': peak['gains_detail'],
        'excess_by_row': excess_by_row,
        'new_excess': peak['new_excess'],
        'dead_zone_start': dead_zone_start,
        'dead_zone_end': last_at_peak_gain['add_ft'] if dead_zone_start else None,
        'next_threshold': next_threshold,
        'all_results': results
    }


def draw_excess_dimension_line(ax, x_start, x_end, y_center, excess_ft, row_name):
    """
    Draw dimension line showing excess/wasted space at the east end of a parking row.

    Args:
        ax: Matplotlib axes
        x_start: X-coordinate where excess space starts (east end of last stall)
        x_end: X-coordinate where excess space ends (building interior edge)
        y_center: Y-coordinate for center of parking row
        excess_ft: Excess footage to display
        row_name: Name of the parking row (for label)
    """
    if excess_ft < 0.5:
        return  # Don't show dimension for tiny excess

    # Color code by severity
    if excess_ft < 3:
        color = 'green'  # Good efficiency
        alpha = 0.6
    elif excess_ft < 6:
        color = 'orange'  # Moderate waste
        alpha = 0.7
    else:
        color = 'red'  # Optimization opportunity
        alpha = 0.8

    # Draw horizontal dimension line
    line_y = y_center
    ax.plot([x_start, x_end], [line_y, line_y], color=color, lw=2, alpha=alpha, linestyle='--')

    # Draw arrows at both ends
    arrow_size = 1.5
    ax.plot([x_start, x_start + arrow_size], [line_y, line_y + arrow_size],
            color=color, lw=1.5, alpha=alpha)
    ax.plot([x_start, x_start + arrow_size], [line_y, line_y - arrow_size],
            color=color, lw=1.5, alpha=alpha)
    ax.plot([x_end, x_end - arrow_size], [line_y, line_y + arrow_size],
            color=color, lw=1.5, alpha=alpha)
    ax.plot([x_end, x_end - arrow_size], [line_y, line_y - arrow_size],
            color=color, lw=1.5, alpha=alpha)

    # Label with excess footage
    mid_x = (x_start + x_end) / 2
    label = f"{excess_ft:.1f}'"
    ax.text(mid_x, line_y + 2, label, ha='center', va='bottom',
            fontsize=8, fontweight='bold', color=color,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=color, alpha=0.9))


def draw_parking_stalls(ax, garage, layout, level_name=None):
    """
    Draw parking stalls with numbering

    If level_name is specified, only draw stalls for that level.
    Otherwise, draw all stalls.
    """
    stall_number = 1

    # Get level-specific data if filtering by level
    level_data = None
    if level_name:
        level_data = garage.stalls_by_level.get(level_name)
        if not level_data:
            print(f"Warning: No data found for level {level_name}")
            return

    # Draw stalls for each section
    for section in layout.sections:
        # Determine if this section belongs to current level
        if level_name and level_data:
            # Check if this section is active on this level
            section_active = False
            zones = level_data.get('zones', {})

            if section.section_type == 'turn_zone':
                # Turn zones alternate: north for even indices, south for odd
                zone_key = f"{level_data['turn_zone']}_turn"
                section_active = (section.name == f"{level_data['turn_zone']}_turn")

            elif section.name in ['west_row', 'east_row']:
                # Perimeter rows: only active if this is the ramp side for this level
                section_active = (section.name == f"{level_data.get('ramp_side')}_row")

            elif section.name.startswith('center_row_'):
                # Center rows: always get half (shared between levels)
                section_active = True

            if not section_active and section.section_type != 'turn_zone':
                continue

        # Get section color
        if section.section_type == 'turn_zone':
            color = COLORS['north_turn'] if 'north' in section.name else COLORS['south_turn']
        elif 'center' in section.name:
            color = COLORS['center']
        elif 'west' in section.name:
            color = COLORS['west_row']
        else:
            color = COLORS['east_row']

        # Calculate stalls for this section
        if section.section_type == 'turn_zone':
            zone = 'north' if section.y_start == 0 else 'south'

            # Skip if not active for this level
            if level_name and level_data and zone != level_data['turn_zone']:
                continue

            num_stalls = layout.calculate_turn_zone_stalls(zone)

            # Turn zone stalls run EAST-WEST along the WIDTH (perpendicular to building length)
            # In geometry: stalls positioned at y=0-48 (north) or y=162-210 (south)
            # In matplotlib: must transform to x-axis

            # Matplotlib x-position: transform geometry y-coordinate to matplotlib x
            if zone == 'north':
                # Geometry: y:[0-48] → Matplotlib x:[0-48]
                mpl_x_pos = section.y_start + 2  # 2' in from edge
            else:
                # Geometry: y:[162-210] → Matplotlib x:[162-210]
                mpl_x_pos = section.y_end - 20  # 20' in from edge

            # Stalls run along width (y-axis in matplotlib)
            # CENTER stalls between core blockages to avoid overlaps
            mpl_y_start = calculate_turn_zone_stall_start(zone, garage.width, num_stalls)

            for i in range(num_stalls):
                mpl_y = mpl_y_start + i * 9  # Each stall is 9' wide along width

                # Draw stall: 18' deep along length (x), 9' wide along width (y)
                stall_rect = Rectangle((mpl_x_pos, mpl_y), 18, 9, fc=color, ec='black', lw=0.5, alpha=0.7)
                ax.add_patch(stall_rect)

                # Number stall
                ax.text(mpl_x_pos + 9, mpl_y + 4.5, str(stall_number), ha='center', va='center',
                       fontsize=6, fontweight='bold')
                stall_number += 1

        else:
            # Perimeter and center rows: stalls run along LENGTH (y-direction)
            num_stalls, wasted = section.calculate_stalls()

            if num_stalls == 0:
                continue

            # Calculate available segments (avoiding blockages)
            available_segments = []
            current_y = section.y_start

            # Sort blockages by start position
            sorted_blockages = sorted(section.blockages, key=lambda b: b[0])

            for block_start, block_end in sorted_blockages:
                # Add segment before blockage
                if current_y < block_start:
                    available_segments.append((current_y, block_start))
                current_y = max(current_y, block_end)

            # Add final segment
            if current_y < section.y_end:
                available_segments.append((current_y, section.y_end))

            # Draw stalls in available segments
            stalls_drawn = 0
            for seg_start, seg_end in available_segments:
                seg_length = seg_end - seg_start
                seg_stalls = int(seg_length // 9)

                # Track where stalls end in this segment for dimension line
                last_stall_end = seg_start

                for i in range(seg_stalls):
                    if stalls_drawn >= num_stalls:
                        break

                    stall_y = seg_start + i * 9
                    last_stall_end = stall_y + 9  # Track end of last stall

                    # Draw stall (9' along length × 18' wide)
                    stall_rect = Rectangle((stall_y, section.x_start), 9, section.width,
                                          fc=color, ec='black', lw=0.5, alpha=0.7)
                    ax.add_patch(stall_rect)

                    # Number stall
                    ax.text(stall_y + 4.5, section.x_start + section.width/2, str(stall_number),
                           ha='center', va='center', fontsize=6, fontweight='bold')
                    stall_number += 1
                    stalls_drawn += 1

                # Draw excess dimension line for this segment (only if not filtering by level)
                # Only show for significant excess (>6') to reduce clutter
                if not level_name and seg_stalls > 0:
                    seg_excess = seg_end - last_stall_end
                    if seg_excess >= 6.0:  # Only show significant waste
                        y_center = section.x_start + section.width / 2
                        draw_excess_dimension_line(ax, last_stall_end, seg_end, y_center,
                                                   seg_excess, section.name)

                if stalls_drawn >= num_stalls:
                    break


def create_overview_diagram_figure(garage, layout, opt_result=None):
    """Create overview diagram with all stalls - returns matplotlib figure

    This is the Streamlit-compatible version that returns a figure object
    instead of saving to disk.

    Args:
        garage: SplitLevelParkingGarage instance
        layout: ParkingLayout instance
        opt_result: Pre-calculated optimization result (optional, will calculate if None)

    Returns:
        matplotlib.figure.Figure: The generated diagram figure
    """
    fig, ax = plt.subplots(figsize=(20, 12))

    # Draw in layers (bottom to top)
    draw_turn_zones(ax, garage.width, garage.length)
    draw_aisles(ax, garage.width, garage.length, garage.num_bays)
    draw_core_walls(ax, garage.width, garage.length, garage.num_bays)
    draw_building_outline(ax, garage.width, garage.length)
    draw_core_blockages(ax, garage.width, garage.length)
    draw_entry_opening(ax, garage.width, garage.length)
    draw_parking_stalls(ax, garage, layout)

    # Set axis properties
    ax.set_xlim(-5, garage.length + 5)
    ax.set_ylim(-5, garage.width + 5)
    ax.set_aspect('equal')
    ax.set_xlabel('Length (feet)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Width (feet)', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, ls=':', lw=0.5)
    ax.set_title(f'Parking Garage Layout - OVERVIEW\n{garage.num_bays} Bays × {garage.length:.0f}\' × {garage.width:.0f}\' - Total Stalls: {garage.total_stalls}',
                fontsize=14, fontweight='bold', pad=20)

    # Add legend
    legend_elements = [
        mpatches.Patch(facecolor=COLORS['north_turn'], edgecolor='blue', label='North Turn Zone'),
        mpatches.Patch(facecolor=COLORS['south_turn'], edgecolor='blue', label='South Turn Zone'),
        mpatches.Patch(facecolor=COLORS['west_row'], edgecolor='black', label='West Perimeter Row'),
        mpatches.Patch(facecolor=COLORS['east_row'], edgecolor='black', label='East Perimeter Row'),
        mpatches.Patch(facecolor=COLORS['center'], edgecolor='black', label='Center Rows'),
        mpatches.Patch(facecolor=COLORS['aisle'], edgecolor='gray', label='Aisles/Ramps'),
        mpatches.Patch(facecolor=COLORS['core_wall'], edgecolor='black', label='Core Walls'),
        mpatches.Patch(facecolor=COLORS['core_blockage'], edgecolor='darkred', hatch='///', label='Core Blockages'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

    # Add optimization analysis
    if opt_result is None:
        opt_result = layout.calculate_length_optimization()

    if opt_result:
        # Build optimization text
        opt_text = "OPTIMIZATION ANALYSIS:\n"
        opt_text += f"Current: {garage.length:.0f}' × {garage.width:.0f}' ({garage.num_bays} bays), {garage.total_stalls} stalls\n\n"

        # Show current excess by row
        opt_text += "Row Excess Space:\n"
        for row_name, excess_ft in sorted(opt_result['excess_by_row'].items()):
            # Shorten row names for display
            display_name = row_name.replace('_row', '').replace('center_row_', 'C').replace('west', 'W').replace('east', 'E')
            opt_text += f"  {display_name:8s}: {excess_ft:4.1f}'\n"

        # Show optimal increment (the peak efficiency point)
        opt_text += f"\nOPTIMAL: Add +{opt_result['optimal_ft']}' (→ {garage.length + opt_result['optimal_ft']:.0f}' total)\n"
        opt_text += f"  Gain: +{opt_result['total_gain']} stalls\n"
        opt_text += f"  Efficiency: {opt_result['efficiency']:.2f} stalls/ft ← PEAK\n"

        # Show which rows benefit
        row_gains = ', '.join([f"{name.replace('_row','').replace('center_row_','C').replace('west','W').replace('east','E')}:+{gain}"
                              for name, gain in opt_result['gains_detail']])
        opt_text += f"  Rows: {row_gains}\n"

        # Show new total
        new_total = garage.total_stalls + opt_result['total_gain']
        opt_text += f"  New total: {new_total} stalls\n"

        # Warn about plateau zone
        plateau_start = opt_result.get('plateau_zone_start', opt_result.get('dead_zone_start'))
        plateau_end = opt_result.get('plateau_zone_end', opt_result.get('dead_zone_end'))

        if plateau_start:
            opt_text += f"\nPlateau Zone (wasteful):\n"
            opt_text += f"  +{plateau_start}' to +{plateau_end}' yields same {opt_result['total_gain']} stalls\n"

            # Show next meaningful threshold
            if opt_result['next_threshold']:
                nt = opt_result['next_threshold']
                opt_text += f"  Next gain: +{nt['add_ft']}' for +{nt['total_gain']} total stalls"

        # Add text box in bottom-right corner
        ax.text(0.98, 0.02, opt_text, transform=ax.transAxes,
                fontsize=9, verticalalignment='bottom', horizontalalignment='right',
                family='monospace',
                bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow',
                         edgecolor='orange', linewidth=2, alpha=0.95))

    plt.tight_layout()
    return fig


def create_overview_diagram(garage, layout, output_path, opt_result=None):
    """Create overview diagram with all stalls - FILE-BASED (for standalone script)

    DEPRECATED: Use create_overview_diagram_figure() for Streamlit integration.
    This function is kept for backward compatibility with standalone script usage.

    Args:
        garage: SplitLevelParkingGarage instance
        layout: ParkingLayout instance
        output_path: Path to save diagram
        opt_result: Pre-calculated optimization result (optional, will calculate if None)
    """
    fig = create_overview_diagram_figure(garage, layout, opt_result)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved overview diagram: {output_path}")
    plt.close(fig)


def create_per_level_diagram_figure(garage, layout, level_name, opt_result=None):
    """Create diagram for a single level - returns matplotlib figure

    This is the Streamlit-compatible version that returns a figure object.

    Args:
        garage: SplitLevelParkingGarage instance
        layout: ParkingLayout instance
        level_name: Name of the level to visualize (e.g., 'P1', 'P2.5')
        opt_result: Pre-calculated optimization result (optional)

    Returns:
        matplotlib.figure.Figure: The generated level diagram figure
    """
    fig, ax = plt.subplots(figsize=(20, 12))

    # Get level data
    level_data = garage.stalls_by_level.get(level_name, {})
    if not level_data:
        # Return empty figure if level not found
        ax.text(0.5, 0.5, f"Level {level_name} not found",
                ha='center', va='center', fontsize=16)
        return fig

    level_stalls = level_data.get('stalls', 0)
    turn_zone = level_data.get('turn_zone', 'unknown')
    ramp_side = level_data.get('ramp_side', 'unknown')

    # Find level GSF and elevation
    level_gsf = 0
    elevation = 0
    for lvl_name, gsf, slab_type, elev in garage.levels:
        if lvl_name == level_name:
            level_gsf = gsf
            elevation = elev
            break

    # Draw base layers (lighter/transparent)
    draw_turn_zones(ax, garage.width, garage.length)
    draw_aisles(ax, garage.width, garage.length, garage.num_bays)
    draw_core_walls(ax, garage.width, garage.length, garage.num_bays)
    draw_building_outline(ax, garage.width, garage.length)
    draw_core_blockages(ax, garage.width, garage.length)

    # Highlight active zones for this level
    # Active turn zone
    if turn_zone == 'north':
        highlight = Rectangle((garage.length - 48, 0), 48, garage.width,
                             fc='yellow', ec='red', lw=3, alpha=0.2)
    else:
        highlight = Rectangle((0, 0), 48, garage.width,
                             fc='yellow', ec='red', lw=3, alpha=0.2)
    ax.add_patch(highlight)

    # Active ramp side
    if ramp_side == 'west':
        ramp_highlight = Rectangle((0, 0.5), garage.length, 18,
                                  fc='lightgreen', ec='green', lw=3, alpha=0.2)
    elif ramp_side == 'east':
        ramp_highlight = Rectangle((0, garage.width - 18.5), garage.length, 18,
                                  fc='lightgreen', ec='green', lw=3, alpha=0.2)
    else:
        ramp_highlight = None

    if ramp_highlight:
        ax.add_patch(ramp_highlight)

    # Draw only stalls for this level
    draw_parking_stalls(ax, garage, layout, level_name=level_name)

    # Set axis properties
    ax.set_xlim(-5, garage.length + 5)
    ax.set_ylim(-5, garage.width + 5)
    ax.set_aspect('equal')
    ax.set_xlabel('Length (feet)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Width (feet)', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, ls=':', lw=0.5)

    title = f'Parking Garage Layout - Level {level_name}\n'
    title += f'Elevation: {elevation:.2f}\' | GSF: {level_gsf:,.0f} SF | Stalls: {level_stalls} | '
    title += f'Turn Zone: {turn_zone.upper()} | Ramp Side: {ramp_side.upper()}'
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

    # Add zone breakdown
    zones_text = "Zone Breakdown:\n"
    for zone_name, zone_data in level_data.get('zones', {}).items():
        zones_text += f"  {zone_name}: {zone_data['stalls']} stalls\n"

    ax.text(0.02, 0.98, zones_text, transform=ax.transAxes, fontsize=9,
           verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    # Add optimization analysis (same as overview)
    if opt_result is None:
        opt_result = layout.calculate_length_optimization()

    if opt_result:
        # Build optimization text (compact version for per-level diagrams)
        opt_text = "OPTIMIZATION:\n"
        opt_text += f"Current: {garage.length:.0f}' length\n\n"

        # Show optimal increment
        opt_text += f"Add +{opt_result['optimal_ft']}' → +{opt_result['total_gain']} stalls\n"
        opt_text += f"Efficiency: {opt_result['efficiency']:.2f} stalls/ft\n"

        # Warn about plateau zone
        plateau_start = opt_result.get('plateau_zone_start', opt_result.get('dead_zone_start'))
        plateau_end = opt_result.get('plateau_zone_end', opt_result.get('dead_zone_end'))
        if plateau_start:
            opt_text += f"\nPlateau: +{plateau_start}'-{plateau_end}'"

        # Add text box in bottom-right corner
        ax.text(0.98, 0.02, opt_text, transform=ax.transAxes,
                fontsize=9, verticalalignment='bottom', horizontalalignment='right',
                family='monospace',
                bbox=dict(boxstyle='round,pad=0.6', facecolor='lightyellow',
                         edgecolor='orange', linewidth=1.5, alpha=0.9))

    plt.tight_layout()
    return fig


def create_per_level_diagrams(garage, layout, output_dir, opt_result=None):
    """Create separate diagram for each half-level - FILE-BASED (for standalone script)

    DEPRECATED: Use create_per_level_diagram_figure() for Streamlit integration.
    This function is kept for backward compatibility with standalone script usage.

    Args:
        garage: SplitLevelParkingGarage instance
        layout: ParkingLayout instance
        output_dir: Directory to save level diagrams
        opt_result: Pre-calculated optimization result (optional, will calculate if None)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    for level_name, level_gsf, slab_type, elevation in garage.levels:
        fig = create_per_level_diagram_figure(garage, layout, level_name, opt_result)
        output_path = output_dir / f'level_{level_name.replace(".", "_")}.png'
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Saved level diagram: {output_path}")
        plt.close(fig)


def main():
    """Generate all visualization diagrams"""
    print("=" * 80)
    print("2D PARKING LAYOUT VISUALIZATION")
    print("=" * 80)

    # Create test garage (126' × 210', 9 total half-levels including entry, 2 bays)
    # With 0 below grade and 9 above grade = 9 total levels (entry at index 0)
    print("\nCreating test garage geometry...")
    garage = SplitLevelParkingGarage(
        length=210,
        half_levels_above=9,
        half_levels_below=0,
        num_bays=2
    )

    # Create parking layout
    print("Creating parking layout...")
    layout = ParkingLayout(garage.width, garage.length, garage.num_bays)
    layout.apply_core_blockages()

    # Print summary
    print("\n" + "=" * 80)
    print("GEOMETRY SUMMARY")
    print("=" * 80)
    print(f"Building: {garage.width:.1f}' × {garage.length:.1f}'")
    print(f"Bays: {garage.num_bays}")
    print(f"Total stalls: {garage.total_stalls}")
    print(f"Total levels: {garage.total_levels}")
    print(f"Total GSF: {garage.total_gsf:,.0f} SF")
    print(f"SF/stall: {garage.sf_per_stall:.1f}")

    print("\n" + "=" * 80)
    print("STALLS BY LEVEL")
    print("=" * 80)
    for level_name, data in garage.stalls_by_level.items():
        print(f"{level_name}: {data['stalls']} stalls (Turn: {data['turn_zone']}, Ramp: {data.get('ramp_side', 'N/A')})")

    # Calculate optimization once (reused for all diagrams)
    print("\nCalculating length optimization...")
    opt_result = layout.calculate_length_optimization()

    # Generate diagrams
    print("\n" + "=" * 80)
    print("GENERATING DIAGRAMS")
    print("=" * 80)

    # Overview diagram
    overview_path = Path(__file__).parent / 'parking_layout_overview.png'
    create_overview_diagram(garage, layout, overview_path, opt_result)

    # Per-level diagrams
    per_level_dir = Path(__file__).parent / 'parking_layout_levels'
    create_per_level_diagrams(garage, layout, per_level_dir, opt_result)

    print("\n" + "=" * 80)
    print("COMPLETE!")
    print("=" * 80)
    print(f"Overview: {overview_path}")
    print(f"Per-level: {per_level_dir}/")
    print("=" * 80)


if __name__ == "__main__":
    main()
