from typing import List, Dict, Tuple, Optional

def _unique_sorted(vals: List[float]) -> List[float]:
    eps = 1e-6
    out: List[float] = []
    for v in sorted(vals):
        if not out or abs(v - out[-1]) > eps:
            out.append(float(v))
    return out


def _core_rectangles(garage) -> List[Tuple[float, float, float, float]]:
    length = float(garage.length)
    width = float(garage.width)
    rects: List[Tuple[float, float, float, float]] = []
    rects.append((0.0, 20.0, 0.0, 19.0))  # NW Utility
    rects.append((length - 29.0, length, 0.0, 18.0))  # SW Storage
    rects.append((length - 27.0, length, width - 18.0, width))  # SE Stair
    rects.append((length - 10.0, length, width - 10.0, width))  # NE Elevator
    rects.append((length - 18.0, length, width - 37.0, width - 10.0))  # NE Stair
    return rects


def _interval_midpoints(values: List[float], lo: float, hi: float) -> List[Tuple[float, float]]:
    """
    For sorted values v, return [(left_bound, right_bound)] intervals where:
    left = (prev + v)/2 with prev=lo for first; right = (v + next)/2 with next=hi for last.
    """
    n = len(values)
    ivals: List[Tuple[float, float]] = []
    for i, v in enumerate(values):
        left = (values[i - 1] + v) / 2.0 if i > 0 else (lo + v) / 2.0
        right = (v + values[i + 1]) / 2.0 if i < n - 1 else (v + hi) / 2.0
        # Clamp to [lo, hi]
        left = max(lo, min(left, hi))
        right = max(lo, min(right, hi))
        if right < left:
            left, right = right, left
        ivals.append((left, right))
    return ivals


def _interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    lo = max(a0, b0)
    hi = min(a1, b1)
    return max(0.0, hi - lo)


def compute_column_tributaries_and_loads(garage) -> Tuple[List[Dict], List[Dict]]:
    """
    Semi-full tributary calculator:
    - Y-interval from midpoints between Y-lines (columns grouped by Y)
    - X-interval from midpoints along each Y-line
    - Clip by cores and entry opening; ramp-center restricted to ramp section
    - Aggregate DL/LL and column self-weight loads
    Returns (column_tributary, column_loads) lists aligned to garage.columns order.
    """
    columns = getattr(garage, 'columns', [])
    if not columns:
        return [], []

    width = float(garage.width)
    length = float(garage.length)
    ramp_x0 = float(garage.TURN_ZONE_DEPTH)
    ramp_x1 = float(garage.length - garage.TURN_ZONE_DEPTH)
    entry_center = length / 2.0
    entry_half = getattr(garage, 'ENTRY_WIDTH', 27.0) / 2.0
    entry_x0 = entry_center - entry_half
    entry_x1 = entry_center + entry_half

    # Group columns by Y coordinate and type
    ys = _unique_sorted([c['y'] for c in columns])
    y_to_type: Dict[float, str] = {}
    for y in ys:
        # pick the first column at this y for type
        ytype = next((c.get('y_line_type') for c in columns if abs(c['y'] - y) <= 1e-6), 'interior')
        y_to_type[y] = ytype

    # Y-intervals via midpoints
    y_intervals = _interval_midpoints(ys, 0.0, width)
    y_bounds: Dict[float, Tuple[float, float]] = {ys[i]: y_intervals[i] for i in range(len(ys))}

    # Prepare X intervals per Y-line (midpoints along sorted x's)
    y_to_xvals: Dict[float, List[float]] = {}
    for y in ys:
        xvals = [c['x'] for c in columns if abs(c['y'] - y) <= 1e-6]
        y_to_xvals[y] = _unique_sorted(xvals)

    # Compute X intervals per column
    core_rects = _core_rectangles(garage)
    tribs: List[Dict] = []
    loads: List[Dict] = []

    # Live load reduction approximation: floors-supported ~ equivalent floors
    eq_floors = garage.total_gsf / garage.footprint_sf if getattr(garage, 'footprint_sf', 0.0) > 0 else 0.0
    ll_psf_eff = garage.live_load_psf
    if getattr(garage, 'allow_ll_reduction', True) and eq_floors >= 2.0:
        ll_psf_eff = 0.8 * garage.live_load_psf

    for c in columns:
        y = float(c['y'])
        x = float(c['x'])
        ytype = c.get('y_line_type', 'interior')
        y0, y1 = y_bounds.get(y, (0.0, width))
        # X neighbor interval on this Y
        xvals = y_to_xvals[y]
        x_intervals = _interval_midpoints(xvals, 0.0, length if ytype != 'ramp_center' else length)
        # Find this column index in xvals
        # (safe since we built xvals from columns)
        idx = next(i for i, xv in enumerate(xvals) if abs(xv - x) <= 1e-6)
        x0, x1 = x_intervals[idx]

        # Clamp to ramp section for ramp-center
        if ytype == 'ramp_center':
            x0 = max(x0, ramp_x0)
            x1 = min(x1, ramp_x1)
            if x1 < x0:
                x1 = x0

        # Base area
        base_area = max(0.0, (x1 - x0)) * max(0.0, (y1 - y0))

        # Entry opening subtraction for WEST perimeter only (approximation at aggregate level)
        entry_overlap_len = 0.0
        if ytype == 'perimeter':
            # Heuristic: west perimeter is the one near 18.5'
            west = abs(y - 18.5) <= 0.25
            if west:
                entry_overlap_len = _interval_overlap(x0, x1, entry_x0, entry_x1)

        entry_overlap_area = entry_overlap_len * max(0.0, (y1 - y0))

        # Core clipping (sum overlaps with rectangular cores)
        core_overlap_area = 0.0
        for (cx0, cx1, cy0, cy1) in core_rects:
            dx = _interval_overlap(x0, x1, cx0, cx1)
            dy = _interval_overlap(y0, y1, cy0, cy1)
            if dx > 0 and dy > 0:
                core_overlap_area += dx * dy

        area_net = max(0.0, base_area - entry_overlap_area - core_overlap_area)

        tribs.append({
            'x_left': x0,
            'x_right': x1,
            'y_bottom': y0,
            'y_top': y1,
            'area_sf': area_net,
            'y_line_type': ytype
        })

        # Loads aggregation: slab DL/LL + column self-weight
        col_area_sf = (c['width_in'] / 12.0) * (c['depth_in'] / 12.0)
        col_self_weight = col_area_sf * garage.total_height_ft * 150.0  # lbs
        dl_slab = area_net * garage.dead_load_psf * eq_floors
        ll_slab = area_net * ll_psf_eff * eq_floors
        service = dl_slab + ll_slab + col_self_weight
        factored = garage.load_factor_dl * (dl_slab + col_self_weight) + garage.load_factor_ll * ll_slab

        loads.append({
            'dl_slab_total': dl_slab,
            'll_slab_total': ll_slab,
            'column_self_weight': col_self_weight,
            'service_load': service,
            'factored_load': factored,
            'eq_floors': eq_floors,
            'll_psf_effective': ll_psf_eff
        })

    return tribs, loads


# ======================= Per-level coverage mapping (split-level) =======================

def _subtract_intervals(base: List[Tuple[float, float]], block: Tuple[float, float]) -> List[Tuple[float, float]]:
    """Subtract one [b0,b1] from base intervals list; returns non-overlapping positive-length intervals."""
    b0, b1 = block
    result: List[Tuple[float, float]] = []
    for a0, a1 in base:
        if b1 <= a0 or b0 >= a1:
            # no overlap
            result.append((a0, a1))
        else:
            # overlap cases: up to two segments remain
            if b0 > a0:
                result.append((a0, max(a0, min(b0, a1))))
            if b1 < a1:
                result.append((max(a0, min(b1, a1)), a1))
    # Drop zero-length
    result = [(x0, x1) for (x0, x1) in result if x1 - x0 > 1e-6]
    return result


def _coverage_after_blockages(y_start: float, y_end: float, blockages: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Return list of allowed intervals in [y_start,y_end] after subtracting blockages."""
    intervals: List[Tuple[float, float]] = [(y_start, y_end)]
    for b in blockages:
        intervals = _subtract_intervals(intervals, b)
        if not intervals:
            break
    return intervals


def _section_covers_y(section, y: float) -> bool:
    """Check if column y (width axis) lies within section x_range (width)."""
    return section.x_start - 1e-6 <= y <= section.x_end + 1e-6


def compute_per_level_column_areas_and_loads(garage) -> Tuple[List[List[Dict]], List[Dict]]:
    """
    Compute per-level coverage mapping for split-level:
    - For each level, determine active zones (turn zone + ramp side perimeter + adjacent center row)
    - For each column, compute union of coverage intervals across active sections that include its y (width)
    - Area_level = union_length * column_y_width
    - Loads per level use ASCE-7 reduction via floors_supported (computed from suspended area counts)
    Returns:
      - per_column_levels: list (per column) of list(dict) per level with area and loads
      - per_level_validation: list of dict {level_index, level_name, computed_area_sum, expected_gsf, variance_pct}
    """
    # Preconditions
    if not getattr(garage, 'is_half_level_system', True):
        # For now, handle split-level first; single-ramp in later phase
        return [[] for _ in getattr(garage, 'columns', [])], []

    from ..geometry.parking_layout import ParkingLayout
    layout = ParkingLayout(garage.width, garage.length, garage.num_bays, turn_zone_depth=garage.TURN_ZONE_DEPTH)
    layout.apply_core_blockages()
    sections = {s.name: s for s in layout.sections}

    # Helper to build coverage intervals for a section with extra blockages
    def build_coverage(name: str, extra_blocks: Optional[List[Tuple[float, float]]] = None) -> List[Tuple[float, float]]:
        sec = sections.get(name)
        if not sec:
            return []
        blocks = list(sec.blockages)
        if extra_blocks:
            blocks.extend(extra_blocks)
        return _coverage_after_blockages(sec.y_start, sec.y_end, blocks)

    # Column Y-intervals and width
    columns = getattr(garage, 'columns', [])
    tribs = getattr(garage, 'column_tributary', [])
    col_y_bounds: List[Tuple[float, float]] = []
    col_y_widths: List[float] = []
    for i, c in enumerate(columns):
        if i < len(tribs):
            y0 = tribs[i].get('y_bottom', 0.0)
            y1 = tribs[i].get('y_top', 0.0)
        else:
            # Fallback: no trib computed; approximate small band
            y0, y1 = c['y'] - 0.5, c['y'] + 0.5
        col_y_bounds.append((y0, y1))
        col_y_widths.append(max(0.0, y1 - y0))

    # Level list
    levels = list(garage.levels)
    per_column_levels: List[List[Dict]] = [[] for _ in columns]
    per_level_validation: List[Dict] = []

    RAMP_TERM = getattr(garage, 'RAMP_TERMINATION_LENGTH', 48.0)
    ENTRY_WIDTH = getattr(garage, 'ENTRY_WIDTH', 27.0)
    entry_center = garage.length / 2.0
    entry_half = ENTRY_WIDTH / 2.0
    entry_blockage = (entry_center - entry_half, entry_center + entry_half)

    for level_index, (level_name, level_gsf, slab_type, elevation) in enumerate(levels):
        is_entry = (level_index == garage.entry_level_index)
        is_top = (level_index == garage.total_levels - 1)

        # Active zones based on alternation
        turn_zone_name = 'north_turn' if (level_index % 2 == 0) else 'south_turn'
        ramp_side = 'west' if (level_index % 2 == 0) else 'east'
        perimeter_name = 'west_row' if ramp_side == 'west' else 'east_row'
        # Adjacent center row near perimeter (same pattern as stall calc)
        center_name = 'center_row_1_left' if ramp_side == 'west' else f'center_row_{garage.num_bays - 1}_right'

        # Build coverage intervals for active sections
        extra_blocks_perim: List[Tuple[float, float]] = []
        if is_entry and ramp_side == 'west':
            extra_blocks_perim.append(entry_blockage)
        if is_top:
            extra_blocks_perim.append((0.0, RAMP_TERM))

        cover_turn = build_coverage(turn_zone_name, [])  # turn zone blockages already in section if any
        cover_perim = build_coverage(perimeter_name, extra_blocks_perim)
        cover_center = build_coverage(center_name, extra_blocks_perim if is_top else None)

        # Build a union of intervals for a given set
        def union_length(intervals: List[Tuple[float, float]]) -> float:
            if not intervals:
                return 0.0
            ints = sorted(intervals)
            merged: List[Tuple[float, float]] = []
            cur_s, cur_e = ints[0]
            for s, e in ints[1:]:
                if s <= cur_e + 1e-6:
                    cur_e = max(cur_e, e)
                else:
                    merged.append((cur_s, cur_e))
                    cur_s, cur_e = s, e
            merged.append((cur_s, cur_e))
            return sum(e - s for s, e in merged)

        # For each column, decide if it's covered by active sections based on width
        # A column at y is covered by a section if y is within section.x_range
        # Note: turn zones cover full width – their x_range is (0,width)
        # The per-level strip is the union of intervals of matching sections for that column
        sec_turn = sections.get(turn_zone_name)
        sec_perim = sections.get(perimeter_name)
        sec_center = sections.get(center_name)

        # Precompute section containment per column
        turn_covers = [True] * len(columns) if sec_turn else [False] * len(columns)
        perim_covers = [(_section_covers_y(sec_perim, c['y']) if sec_perim else False) for c in columns]
        center_covers = [(_section_covers_y(sec_center, c['y']) if sec_center else False) for c in columns]

        level_area_sum = 0.0
        for ci, c in enumerate(columns):
            y0, y1 = col_y_bounds[ci]
            y_width = col_y_widths[ci]
            if y_width <= 0:
                per_column_levels[ci].append({'level_index': level_index, 'level_name': level_name, 'area_sf': 0.0,
                                              'dl_lb': 0.0, 'll_lb': 0.0, 'service_lb': 0.0, 'factored_lb': 0.0})
                continue

            # Collect intervals from active sections that cover this column's y
            active_ints: List[Tuple[float, float]] = []
            if sec_turn and turn_covers[ci]:
                active_ints += cover_turn
            if sec_perim and perim_covers[ci]:
                active_ints += cover_perim
            if sec_center and center_covers[ci]:
                active_ints += cover_center

            # Union length along building length
            length_covered = union_length(active_ints)
            area_level = max(0.0, length_covered * y_width)

            # Placeholder loads; will be updated after floors_supported computed
            per_column_levels[ci].append({'level_index': level_index, 'level_name': level_name, 'area_sf': area_level,
                                          'slab_type': slab_type})
            level_area_sum += area_level

        # Validation record for this level
        expected = float(level_gsf)
        variance_pct = ((level_area_sum / expected) - 1.0) * 100.0 if expected > 0 else 0.0
        per_level_validation.append({
            'level_index': level_index,
            'level_name': level_name,
            'computed_area_sum': level_area_sum,
            'expected_gsf': expected,
            'variance_pct': variance_pct
        })

    # Compute floors_supported per column and per-level loads with ASCE-7 reduction
    for ci, col_levels in enumerate(per_column_levels):
        # Count suspended areas
        floors_supported = sum(1 for e in col_levels if e.get('slab_type') == 'suspended' and e.get('area_sf', 0.0) > 0)
        # Live load reduction
        ll_psf = garage.live_load_psf
        if getattr(garage, 'allow_ll_reduction', True) and floors_supported >= 2:
            # Floors-supported method; area-based later
            ll_psf_eff = 0.8 * ll_psf
        else:
            ll_psf_eff = ll_psf
        for e in col_levels:
            area = e.get('area_sf', 0.0)
            dl_lb = area * garage.dead_load_psf
            ll_lb = area * ll_psf_eff if e.get('slab_type') == 'suspended' else 0.0
            # Column self-weight per level not allocated here; remains in aggregate
            service_lb = dl_lb + ll_lb
            factored_lb = garage.load_factor_dl * dl_lb + garage.load_factor_ll * ll_lb
            e.update({
                'dl_lb': dl_lb,
                'll_lb': ll_lb,
                'service_lb': service_lb,
                'factored_lb': factored_lb,
                'floors_supported': floors_supported,
                'll_psf_effective': ll_psf_eff
            })

    return per_column_levels, per_level_validation


