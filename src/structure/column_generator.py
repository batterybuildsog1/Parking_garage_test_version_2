from typing import List, Dict, Tuple
import math

# We derive width boundaries from ParkingLayout to stay aligned with stall/aisle geometry.
from ..geometry.parking_layout import ParkingLayout


def _unique_sorted(values: List[Tuple[float, str]]) -> List[Tuple[float, str]]:
    """Deduplicate by coordinate with small tolerance; keep first type seen; return sorted by coordinate."""
    eps = 1e-6
    values_sorted = sorted(values, key=lambda v: v[0])
    result: List[Tuple[float, str]] = []
    for y_val, y_type in values_sorted:
        if not result:
            result.append((y_val, y_type))
            continue
        if abs(y_val - result[-1][0]) <= eps:
            # Keep existing entry (first occurrence); skip duplicates
            continue
        result.append((y_val, y_type))
    return result


def _compute_y_lines(garage) -> List[Tuple[float, str]]:
    """
    Build critical Y-lines across building width:
    - Perimeter stall boundaries (west/east)
    - Aisle/stall boundaries flanking center rows
    - Ramp centerlines between center rows
    Returns list of (y, y_line_type)
    """
    layout = ParkingLayout(garage.width, garage.length, garage.num_bays, turn_zone_depth=garage.TURN_ZONE_DEPTH)
    layout.apply_core_blockages()

    # Index sections for easy lookup
    sections = {s.name: s for s in layout.sections}

    y_lines: List[Tuple[float, str]] = []

    # West perimeter stall boundary: use west_row x_end
    west_row = sections.get('west_row')
    if west_row:
        y_lines.append((west_row.x_end, 'perimeter'))

    # For each core divider, add aisle/stall boundaries and ramp centerline
    for idx in range(garage.num_bays - 1):
        left_name = f'center_row_{idx + 1}_left'
        right_name = f'center_row_{idx + 1}_right'
        left_row = sections.get(left_name)
        right_row = sections.get(right_name)
        if not left_row or not right_row:
            continue

        # Preceding aisle boundary before left_row (25' aisle)
        y_before_left = left_row.x_start - 25.0
        y_lines.append((y_before_left, 'aisle_boundary'))

        # Stall → core boundary at left_row end
        y_lines.append((left_row.x_end, 'stall_boundary'))

        # Core width between left_row.x_end and right_row.x_start
        core_width = max(right_row.x_start - left_row.x_end, 0.0)
        if core_width > 0:
            ramp_center = left_row.x_end + core_width / 2.0
            y_lines.append((ramp_center, 'ramp_center'))

        # Core → stall boundary at right_row start
        y_lines.append((right_row.x_start, 'stall_boundary'))

        # Following aisle boundary after right_row (25' aisle)
        y_after_right = right_row.x_end + 25.0
        y_lines.append((y_after_right, 'aisle_boundary'))

    # East perimeter stall boundary: use east_row x_start
    east_row = sections.get('east_row')
    if east_row:
        y_lines.append((east_row.x_start, 'perimeter'))

    # Deduplicate and sort
    return _unique_sorted(y_lines)


def _generate_x_positions(x_start: float, x_end: float, spacing: float) -> List[float]:
    """
    Generate symmetric grid of X positions within [x_start, x_end] with max span <= spacing.
    """
    usable = max(x_end - x_start, 0.0)
    if usable <= 0.0:
        return []
    if usable <= spacing:
        # Single centered position
        return [x_start + usable / 2.0]
    num_spans = int(math.floor(usable / spacing))
    leftover = usable - num_spans * spacing
    offset = x_start + (leftover / 2.0)
    xs: List[float] = []
    for k in range(num_spans + 1):
        val = offset + k * spacing
        if val < x_start - 1e-6 or val > x_end + 1e-6:
            continue
        xs.append(val)
    return xs


def generate_columns(garage) -> List[Dict]:
    """
    Create minimal, non-obstructing column grid:
    - Y-lines at stall/aisle boundaries and ramp centerlines
    - X-grid anchored per line with spans <= 31'
    - Ramp-center columns restricted to ramp section only
    - West perimeter avoids entry opening along x (length) at mid-building
    - Columns omitted inside physical core rectangles (elevator/stairs/utility/storage)
    Returns list of column dicts: {x, y, width_in, depth_in, y_line_type}
    """
    y_lines = _compute_y_lines(garage)
    columns: List[Dict] = []

    # Length constraints
    full_x_start, full_x_end = 0.0, float(garage.length)
    ramp_x_start = float(garage.TURN_ZONE_DEPTH)
    ramp_x_end = float(garage.length - garage.TURN_ZONE_DEPTH)
    spacing = float(getattr(garage, 'PRIMARY_BAY_SPACING', 31.0))

    # Entry opening (west side) along length, centered
    entry_center = garage.length / 2.0
    entry_half = getattr(garage, 'ENTRY_WIDTH', 27.0) / 2.0
    entry_x0 = entry_center - entry_half
    entry_x1 = entry_center + entry_half

    # Physical core rectangles to omit columns within
    core_rects = _core_rectangles(garage)

    for y_val, y_type in y_lines:
        # Determine X-range for this y-line
        if y_type == 'ramp_center':
            x0, x1 = ramp_x_start, ramp_x_end
        else:
            x0, x1 = full_x_start, full_x_end

        xs = _generate_x_positions(x0, x1, spacing)

        for xv in xs:
            # Skip columns within entry opening on the WEST perimeter boundary only
            if y_type == 'perimeter' and west_perimeter(y_val, garage):
                if entry_x0 <= xv <= entry_x1:
                    continue

            # Omit if inside any core rectangle
            if _inside_any_core(xv, y_val, core_rects):
                continue

            # Size mapping (fixed for now; parameterize later)
            if y_type == 'ramp_center':
                width_in, depth_in = 32.0, 24.0
            else:
                width_in, depth_in = 18.0, 24.0

            columns.append({
                'x': float(xv),
                'y': float(y_val),
                'width_in': width_in,
                'depth_in': depth_in,
                'y_line_type': y_type
            })

    return columns


def west_perimeter(y_val: float, garage) -> bool:
    """
    Heuristic to detect WEST perimeter line: near the west stall boundary.
    """
    # West stall boundary per ParkingLayout is at ~18.5' from exterior edge
    # Derive it approximately from module constants
    try:
        # Prefer reading from ParkingLayout for accuracy
        layout = ParkingLayout(garage.width, garage.length, garage.num_bays, turn_zone_depth=garage.TURN_ZONE_DEPTH)
        sections = {s.name: s for s in layout.sections}
        west_row = sections.get('west_row')
        if west_row:
            return abs(y_val - west_row.x_end) <= 1e-4
    except Exception:
        pass
    # Fallback threshold near 18.5'
    return abs(y_val - 18.5) <= 0.25


def _core_rectangles(garage) -> List[Tuple[float, float, float, float]]:
    """
    Return list of core rectangles as (x0, x1, y0, y1) in feet where columns should be omitted.
    Coordinates follow the same axes used in visualization helpers:
    - x: along building length (south 0 -> north length)
    - y: along building width  (west 0 -> east width)
    """
    rects: List[Tuple[float, float, float, float]] = []
    length = float(garage.length)
    width = float(garage.width)

    # NW Utility: 20' × 19' at southwest corner (x: 0..20, y: 0..19)
    rects.append((0.0, 20.0, 0.0, 19.0))

    # SW Storage: 29' × 18' at southeast corner (x: length-29..length, y: 0..18)
    rects.append((length - 29.0, length, 0.0, 18.0))

    # SE Stair: 18' × 27' at northeast edge (x: length-27..length, y: width-18..width)
    rects.append((length - 27.0, length, width - 18.0, width))

    # NE Elevator: 10' × 10' at extreme northeast (x: length-10..length, y: width-10..width)
    rects.append((length - 10.0, length, width - 10.0, width))

    # NE Stair: 18' × 27' west of elevator along north edge
    # y range: width - (10 + 27) .. width - 10  => width - 37 .. width - 10
    rects.append((length - 18.0, length, width - 37.0, width - 10.0))

    return rects


def _inside_any_core(x: float, y: float, rects: List[Tuple[float, float, float, float]]) -> bool:
    for x0, x1, y0, y1 in rects:
        if x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6:
            return True
    return False


