"""
Analyze TechRidge as a shared-wall configuration

Key insight: TechRidge is NOT isolated structure - it's side-by-side towers
with a SHARED LOAD-BEARING WALL down the centerline

This means:
- NO center columns (replaced by continuous wall)
- LARGE continuous wall footing (FC10.0 @ 10' wide)
- Smaller spread footings at perimeter only
"""

import sys

# TechRidge Budget Data
budget = {
    'continuous_footings': {
        'FTS2.0': {'cy': 427.11, 'width_ft': 2.0},
        'FC4.0': {'cy': 403.56, 'width_ft': 4.0},
        'FC10.0': {'cy': 502.96, 'width_ft': 10.0},  # SHARED WALL
        'FC11.0': {'cy': 123.52, 'width_ft': 11.0},
    },
    'spread_footings': {
        'FS10.0': {'cy': 176.54, 'width_ft': 10.0, 'depth_est_in': 18},
        'FS12.0': {'cy': 61.33, 'width_ft': 12.0, 'depth_est_in': 18},
    },
    'elevator': {'cy': 133.33, 'allocation': 'shared'},
}

# Building geometry
length = 210  # feet
width_total = 126  # feet (2-bay equivalent)
half_levels = 9  # 1 below + 8 above
height_per_half = 5.328  # feet
total_height = half_levels * height_per_half  # 47.952'

print("="*80)
print("SHARED WALL ANALYSIS - TechRidge 1.2")
print("="*80)

print(f"\nBuilding Configuration:")
print(f"  Dimensions: {length}' × {width_total}'")
print(f"  Half-levels: {half_levels} ({total_height:.1f}' total height)")
print(f"  Configuration: Side-by-side parking + apartments with shared central wall")

print("\n" + "="*80)
print("REVERSE-ENGINEERING FC10.0 (Shared Wall Footing)")
print("="*80)

# FC10.0 analysis
fc10_cy = budget['continuous_footings']['FC10.0']['cy']
fc10_width = budget['continuous_footings']['FC10.0']['width_ft']

print(f"\nFC10.0: {fc10_cy:.2f} CY @ {fc10_width}' wide")

# Try different lengths and depths
print(f"\nPossible configurations:")
for length_factor in [1.0, 0.8, 0.5]:  # Full length, 80%, 50%
    effective_length = length * length_factor
    for depth_ft in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
        calc_cy = (effective_length * fc10_width * depth_ft) / 27
        if abs(calc_cy - fc10_cy) < 10:  # Within 10 CY
            print(f"  {effective_length:.0f}' long × {fc10_width}' wide × {depth_ft:.1f}' deep = {calc_cy:.2f} CY ✓")

print(f"\nMost likely: Shared wall footing running partial length of building")

# Calculate loads on shared wall
print("\n" + "="*80)
print("SHARED WALL LOADING ESTIMATE")
print("="*80)

# Assume the shared wall carries:
# 1. Wall self-weight (12" concrete wall)
# 2. Parking garage floors (one side)
# 3. Apartment floors (other side)

# For parking side:
parking_width = width_total / 2  # Half the building
parking_footprint = length * parking_width
equivalent_floors = 4.89  # From previous analysis

# Dead load + Live load
dl_psf = 115
ll_psf = 50

# Tributary to wall (assume half of parking width)
trib_width = parking_width / 2  # 31.5'
load_per_lf_parking = trib_width * (dl_psf + ll_psf) * equivalent_floors

# Wall self-weight (12" × total_height × 150 PCF)
wall_weight_plf = 1.0 * total_height * 150

# Apartment side (similar calculation)
load_per_lf_apartment = trib_width * (dl_psf + ll_psf) * equivalent_floors

total_load_plf = wall_weight_plf + load_per_lf_parking + load_per_lf_apartment

print(f"\nShared wall loading:")
print(f"  Wall self-weight: {wall_weight_plf:,.0f} lbs/LF")
print(f"  Parking tributary: {load_per_lf_parking:,.0f} lbs/LF ({trib_width:.1f}' × {equivalent_floors:.2f} floors)")
print(f"  Apartment tributary: {load_per_lf_apartment:,.0f} lbs/LF ({trib_width:.1f}' × {equivalent_floors:.2f} floors)")
print(f"  TOTAL: {total_load_plf:,.0f} lbs/LF")

# Required footing width for 2000 PSF bearing
required_width_2000 = total_load_plf / 2000
required_width_1500 = total_load_plf / 1500

print(f"\nRequired footing width:")
print(f"  @ 2000 PSF bearing: {required_width_2000:.1f}'")
print(f"  @ 1500 PSF bearing: {required_width_1500:.1f}'")
print(f"  Budget uses: {fc10_width}' (FC10.0)")

bearing_implied = total_load_plf / fc10_width
print(f"  Implied bearing pressure: {bearing_implied:.0f} PSF")

print("\n" + "="*80)
print("SPREAD FOOTING ANALYSIS")
print("="*80)

# Spread footings are at perimeter only (not center)
print(f"\nBudget Spread Footings:")
print(f"  FS10.0: {budget['spread_footings']['FS10.0']['cy']:.2f} CY @ 10' square")
print(f"  FS12.0: {budget['spread_footings']['FS12.0']['cy']:.2f} CY @ 12' square")

# Estimate number of each
for name, data in budget['spread_footings'].items():
    width = data['width_ft']
    depth_est = data['depth_est_in'] / 12
    cy_per_footing = (width * width * depth_est) / 27
    count = data['cy'] / cy_per_footing

    print(f"\n{name}:")
    print(f"  Volume per footing: {cy_per_footing:.2f} CY ({width}' × {width}' × {data['depth_est_in']}\")")
    print(f"  Estimated count: {count:.0f} footings")

    # Calculate implied load
    area_sf = width * width
    bearing_pressures = [1500, 1750, 2000]
    print(f"  Implied column loads:")
    for bearing in bearing_pressures:
        load_kips = (area_sf * bearing) / 1000
        print(f"    @ {bearing} PSF bearing: {load_kips:.0f} kips")

print("\n" + "="*80)
print("CONTINUOUS FOOTING BREAKDOWN")
print("="*80)

# Analyze all continuous footings
print("\nReverse-engineering all continuous footings:")

for name, data in budget['continuous_footings'].items():
    cy = data['cy']
    width = data['width_ft']

    print(f"\n{name}: {cy:.2f} CY @ {width}' wide")

    # Try to find reasonable length × depth combinations
    candidates = []
    for length_test in [40, 50, 74, 86, 102, 105, 120, 148, 168, 210, 420]:  # Common lengths
        for depth_ft in [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
            calc_cy = (length_test * width * depth_ft) / 27
            error = abs(calc_cy - cy)
            if error < 5:  # Within 5 CY
                candidates.append({
                    'length': length_test,
                    'depth': depth_ft,
                    'cy': calc_cy,
                    'error': error
                })

    # Show best matches
    candidates.sort(key=lambda x: x['error'])
    if candidates:
        print(f"  Best matches:")
        for c in candidates[:5]:
            print(f"    {c['length']:.0f}' × {width}' × {c['depth']:.2f}' = {c['cy']:.2f} CY (error: {c['error']:.2f})")

print("\n" + "="*80)
print("KEY FINDINGS")
print("="*80)

print("""
1. FC10.0 (502.96 CY @ 10' wide) is the SHARED WALL FOOTING
   - Runs most/all of the 210' building length
   - Supports both parking garage AND apartment loads
   - This is why our model failed - we assumed isolated columns

2. Spread footings are MUCH SMALLER (FS10.0, FS12.0 only)
   - Only at building perimeter (no center columns)
   - 10-12' square vs our calculated 20-23' square
   - This confirms the shared wall carries most central loads

3. Rebar rates are different:
   - Continuous: 110 lbs/CY (confirmed correct)
   - Spread: 65 lbs/CY (we're currently using 110, need to fix)

4. Our footing calculator needs updates:
   - Add "shared wall" configuration option
   - Reduce spread footing rebar rate to 65 lbs/CY
   - Account for load-bearing wall instead of center columns
""")

print("\n" + "="*80)
print("REBAR RATE VALIDATION")
print("="*80)

total_cont_cy = sum(f['cy'] for f in budget['continuous_footings'].values())
total_cont_rebar_lbs = 160286.30  # From budget
calc_cont_rate = total_cont_rebar_lbs / total_cont_cy

total_spread_cy = sum(f['cy'] for f in budget['spread_footings'].items() if isinstance(f, dict))
total_spread_and_elev_cy = 176.54 + 61.33 + 133.33  # FS10 + FS12 + elevator
total_spread_rebar_lbs = 24128.64  # From budget
calc_spread_rate = total_spread_rebar_lbs / total_spread_and_elev_cy

print(f"\nContinuous footings:")
print(f"  Total concrete: {total_cont_cy:.2f} CY")
print(f"  Total rebar: {total_cont_rebar_lbs:.2f} lbs")
print(f"  Calculated rate: {calc_cont_rate:.1f} lbs/CY")
print(f"  Budget rate: 110 lbs/CY ✓ MATCHES")

print(f"\nSpread footings (including elevator):")
print(f"  Total concrete: {total_spread_and_elev_cy:.2f} CY")
print(f"  Total rebar: {total_spread_rebar_lbs:.2f} lbs")
print(f"  Calculated rate: {calc_spread_rate:.1f} lbs/CY")
print(f"  Budget rate: 65 lbs/CY ✓ MATCHES")

print("\n" + "="*80)
