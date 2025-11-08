"""
Compare our footing calculator output to TechRidge 1.2 SD Budget

TechRidge Configuration:
- Side-by-side towers (NOT podium)
- 210' × 126' (2 bays)
- 9 half-levels total: 1 below + 8 above
- 2000 PSF soil bearing capacity
"""

import sys
from src.garage import SplitLevelParkingGarage
from src.footing_calculator import FootingCalculator

# TechRidge configuration
config = {
    'length': 210,  # feet
    'num_bays': 2,  # (126' = 1 + 61 + 3 + 61 + 1 = 127', close enough)
    'half_levels_below': 1,
    'half_levels_above': 8,
    'soil_bearing_capacity': 2000,  # PSF
}

print("="*80)
print("FOOTING CALCULATOR COMPARISON: Our Model vs TechRidge 1.2 SD Budget")
print("="*80)
print(f"\nConfiguration:")
print(f"  Length: {config['length']}' × Width: calculated from {config['num_bays']} bays")
print(f"  Half-levels: {config['half_levels_below']} below + {config['half_levels_above']} above = {config['half_levels_below'] + config['half_levels_above']} total")
print(f"  Soil bearing: {config['soil_bearing_capacity']} PSF")

# Create garage instance
garage = SplitLevelParkingGarage(
    length=config['length'],
    num_bays=config['num_bays'],
    half_levels_below=config['half_levels_below'],
    half_levels_above=config['half_levels_above']
)

print(f"\nCalculated Dimensions:")
print(f"  Footprint: {garage.length}' × {garage.width}'")
print(f"  Total Height: {garage.total_height_ft}' ({garage.total_gsf / garage.footprint_sf:.2f} equivalent full floors)")
print(f"  Total GSF: {garage.total_gsf:,.0f} SF")

# Create footing calculator
calc = FootingCalculator(
    garage=garage,
    soil_bearing_capacity=config['soil_bearing_capacity'],
    fc=4000,
    allow_ll_reduction=False,
    footing_rebar_rate=110.0  # Will update this based on findings
)

print("\n" + "="*80)
print("COLUMN LOAD ANALYSIS")
print("="*80)

# Calculate loads for each column type
column_types = ['corner', 'edge', 'interior_perimeter', 'center_ramp']
load_data = {}

for col_type in column_types:
    load_dict = calc.calculate_column_load(col_type)
    load_data[col_type] = load_dict

    print(f"\n{col_type.upper().replace('_', ' ')} COLUMN:")
    print(f"  Tributary Area: {load_dict['tributary_area']:.0f} SF")
    print(f"  Equivalent Full Floors: {load_dict['equivalent_full_floors']:.2f}")
    print(f"  Service Load: {load_dict['service_load']:,.0f} lbs ({load_dict['service_load']/1000:.1f} kips)")
    print(f"  Factored Load: {load_dict['factored_load']:,.0f} lbs ({load_dict['factored_load']/1000:.1f} kips)")
    print(f"  Components:")
    print(f"    - Slab DL: {load_dict['slab_dl']:,.0f} lbs")
    print(f"    - Column Weight: {load_dict['column_weight']:,.0f} lbs")
    if col_type == 'center_ramp':
        print(f"    - Core Wall: {load_dict['core_wall_weight']:,.0f} lbs")
        print(f"    - Curbs: {load_dict['curb_weight']:,.0f} lbs")

print("\n" + "="*80)
print("SPREAD FOOTING DESIGN")
print("="*80)

spread_footings = {}
for col_type in column_types:
    footing = calc.design_spread_footing(load_data[col_type], col_type)
    spread_footings[col_type] = footing

    service_kips = footing['service_load'] / 1000
    pounds_per_sqft = footing['service_load'] / footing['area_sf']

    print(f"\n{col_type.upper().replace('_', ' ')}:")
    print(f"  Designation: {footing['designation']}")
    print(f"  Size: {footing['width_ft']}' × {footing['width_ft']}' × {footing['depth_in']}\"")
    print(f"  Service Load: {service_kips:.1f} kips")
    print(f"  Load per SF: {pounds_per_sqft:.0f} PSF")
    print(f"  Concrete: {footing['concrete_cy']:.2f} CY")
    print(f"  Rebar: {footing['rebar_lbs']:.0f} lbs ({footing['rebar_lbs']/footing['concrete_cy']:.1f} lbs/CY)")
    print(f"  Bearing Pressure: {footing['bearing_pressure']:.0f} PSF (util: {footing['bearing_pressure']/config['soil_bearing_capacity']*100:.1f}%)")

print("\n" + "="*80)
print("CONTINUOUS FOOTING DESIGN")
print("="*80)

# Design continuous footings
cont_result = calc.calculate_continuous_footings()

for footing in cont_result['footings']:
    wall_type = footing['wall_type']
    load_plf = footing['load_plf']
    width = footing['width_ft']
    length = footing['length_ft']

    pounds_per_lf_per_foot = load_plf / width  # Load per LF per foot of width

    print(f"\n{wall_type.upper()}:")
    print(f"  Designation: {footing['designation']}")
    print(f"  Size: {width}' wide × {footing['depth_ft']:.2f}' deep × {length}' long")
    print(f"  Total Load: {load_plf:.0f} lbs/LF")
    print(f"  Components:")
    print(f"    - Wall weight: {footing['wall_weight_plf']:.0f} lbs/LF")
    print(f"    - Slab load: {footing['slab_load_plf']:.0f} lbs/LF")
    print(f"    - Equipment: {footing['equipment_load_plf']:.0f} lbs/LF")
    print(f"    - Special LL: {footing['specialized_ll_plf']:.0f} lbs/LF")
    print(f"  Load per LF per foot width: {pounds_per_lf_per_foot:.0f} PSF")
    print(f"  Concrete: {footing['concrete_cy']:.2f} CY")
    print(f"  Rebar: {footing['rebar_lbs']:.0f} lbs ({footing['rebar_lbs']/footing['concrete_cy']:.1f} lbs/CY)")

print("\n" + "="*80)
print("TECHRIDGE BUDGET COMPARISON")
print("="*80)

# TechRidge Budget data
budget_data = {
    'continuous': {
        'FTS2.0': {'cy': 427.11, 'width': 2.0, 'likely': 'Unknown'},
        'FC4.0': {'cy': 403.56, 'width': 4.0, 'likely': 'Stairs?'},
        'FC10.0': {'cy': 502.96, 'width': 10.0, 'likely': 'Perimeter wall?'},
        'FC11.0': {'cy': 123.52, 'width': 11.0, 'likely': 'Storage?'},
    },
    'spread': {
        'FS10.0': {'cy': 176.54, 'width': 10.0, 'count_est': 'Multiple'},
        'FS12.0': {'cy': 61.33, 'width': 12.0, 'count_est': 'Few'},
    },
    'continuous_rebar_rate': 110.0,  # lbs/CY
    'spread_rebar_rate': 65.0,  # lbs/CY
}

print("\nBudget Continuous Footings:")
total_budget_cont_cy = sum(f['cy'] for f in budget_data['continuous'].values())
print(f"  Total: {total_budget_cont_cy:.2f} CY")
for name, data in budget_data['continuous'].items():
    print(f"  {name}: {data['cy']:.2f} CY @ {data['width']}' wide - {data['likely']}")

print(f"\nBudget Spread Footings:")
total_budget_spread_cy = sum(f['cy'] for f in budget_data['spread'].values())
print(f"  Total: {total_budget_spread_cy:.2f} CY")
for name, data in budget_data['spread'].items():
    print(f"  {name}: {data['cy']:.2f} CY @ {data['width']}' square")

print(f"\nBudget Rebar Rates:")
print(f"  Continuous: {budget_data['continuous_rebar_rate']} lbs/CY")
print(f"  Spread: {budget_data['spread_rebar_rate']} lbs/CY")

# Calculate our totals
spread_result = calc.calculate_spread_footings()
our_cont_cy = cont_result['total_concrete_cy']
our_spread_cy = spread_result['total_concrete_cy']

print(f"\nOur Model Totals:")
print(f"  Continuous: {our_cont_cy:.2f} CY")
print(f"  Spread: {our_spread_cy:.2f} CY")
print(f"  Total: {our_cont_cy + our_spread_cy:.2f} CY")

print(f"\nDifferences:")
print(f"  Continuous: {our_cont_cy - total_budget_cont_cy:+.2f} CY ({(our_cont_cy/total_budget_cont_cy - 1)*100:+.1f}%)")
print(f"  Spread: {our_spread_cy - total_budget_spread_cy:+.2f} CY ({(our_spread_cy/total_budget_spread_cy - 1)*100:+.1f}%)")

print("\n" + "="*80)
print("LOAD NORMALIZED ANALYSIS")
print("="*80)
print("\nSpread Footings - Concrete per Kip of Service Load:")

for col_type, footing in spread_footings.items():
    service_kips = footing['service_load'] / 1000
    cy_per_kip = footing['concrete_cy'] / service_kips
    print(f"  {col_type}: {cy_per_kip:.4f} CY/kip ({service_kips:.1f} kips, {footing['designation']})")

# Estimate budget footings
print("\nTechRidge Budget - Estimated Concrete per Kip:")
# Assuming center columns use FS12.0, interior use FS10.0
if 'center_ramp' in spread_footings:
    center_kips = spread_footings['center_ramp']['service_load'] / 1000
    budget_cy_12 = (12 * 12 * (18/12)) / 27  # 12' x 12' x 18" deep estimate
    print(f"  FS12.0 (center_ramp est): {budget_cy_12/center_kips:.4f} CY/kip ({budget_cy_12:.2f} CY / {center_kips:.1f} kips)")

if 'interior_perimeter' in spread_footings:
    int_kips = spread_footings['interior_perimeter']['service_load'] / 1000
    budget_cy_10 = (10 * 10 * (18/12)) / 27  # 10' x 10' x 18" deep estimate
    print(f"  FS10.0 (interior est): {budget_cy_10/int_kips:.4f} CY/kip ({budget_cy_10:.2f} CY / {int_kips:.1f} kips)")

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)

# Calculate what bearing capacity would give us similar footing sizes
print("\nIf budget uses larger footings, possible reasons:")
print("  1. Lower effective bearing capacity (after safety factors)")
print("  2. Additional loads not modeled (apartment floors above?)")
print("  3. Different structural system (shared wall between towers)")
print("  4. More conservative design criteria")

# Check if updating rebar rate makes sense
current_spread_rebar_rate = 110.0
budget_spread_rebar_rate = 65.0
print(f"\nRebar Rate Update:")
print(f"  Current spread footing: {current_spread_rebar_rate} lbs/CY")
print(f"  Budget spread footing: {budget_spread_rebar_rate} lbs/CY")
print(f"  Recommendation: UPDATE to {budget_spread_rebar_rate} lbs/CY for spread footings")
print(f"  This is {(current_spread_rebar_rate/budget_spread_rebar_rate - 1)*100:.1f}% overestimate currently")

print("\n" + "="*80)
