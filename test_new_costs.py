"""
Test script to validate new cost components
- Backfill (foundation + ramp)
- Elevator pit waterproofing
- Parking equipment (doors, utilities, bicycle racks)
"""

from src.garage import SplitLevelParkingGarage
from src.cost_engine import CostCalculator, load_cost_database

# Create TR reference configuration
garage = SplitLevelParkingGarage(
    length=210.0,
    half_levels_above=8,
    half_levels_below=1,
    num_bays=2,
    building_type='standalone'
)

# Check new quantities exist
print('=' * 80)
print('NEW QUANTITIES VALIDATION')
print('=' * 80)
print(f'Backfill foundation: {garage.backfill_foundation_cy:.2f} CY')
print(f'Backfill ramp: {garage.backfill_ramp_cy:.2f} CY')
print(f'Elevator pit waterproofing: {garage.elevator_pit_waterproofing_sf:.2f} SF')
print(f'High-speed overhead door: {garage.high_speed_overhead_door_ea} EA')
print(f'Oil/water separator: {garage.oil_water_separator_ea} EA')
print(f'Storm drain 48" ADS: {garage.storm_drain_48in_ads_ea} EA')
print(f'Storm drain junction boxes: {garage.storm_drain_junction_box_6x6_ea} EA')
print(f'Bicycle racks: {garage.bicycle_rack_ea} EA')
print()

# TR expected values for comparison
print('=' * 80)
print('TR REFERENCE VALUES')
print('=' * 80)
print('Backfill foundation: 1,639.72 CY (TR)')
print('Backfill ramp: 2,397.33 CY (TR)')
print('Elevator pit waterproofing: 874 SF (TR allocation, includes shaft)')
print('High-speed overhead door: 1 EA (TR)')
print('Oil/water separator: 1 EA (TR)')
print('Storm drain 48" ADS: 1 EA (TR)')
print('Storm drain junction boxes: 2 EA (TR)')
print('Bicycle racks: 80 EA (TR, 319 stalls)')
print()

# Calculate costs
cost_db = load_cost_database()
cost_calc = CostCalculator(cost_db)
costs = cost_calc.calculate_all_costs(garage)

print('=' * 80)
print('COST BREAKDOWN')
print('=' * 80)
print(f'Foundation: ${costs["foundation"]:,.0f}')
print(f'Excavation: ${costs["excavation"]:,.0f}')
print(f'Exterior: ${costs["exterior"]:,.0f}')
print(f'Site Finishes: ${costs["site_finishes"]:,.0f}')
print(f'Special Systems: ${costs["special_systems"]:,.0f}')
print()
print(f'Total Cost: ${costs["total"]:,.0f}')
print(f'Cost per SF: ${costs["cost_per_sf"]:.2f}')
print(f'Cost per Stall: ${costs["cost_per_stall"]:,.0f}')
print()

# TR reference
tr_total = 12_272_200
print('=' * 80)
print('VARIANCE vs TR REFERENCE')
print('=' * 80)
print(f'Our Total: ${costs["total"]:,.0f}')
print(f'TR Total: ${tr_total:,.0f}')
variance = costs["total"] - tr_total
variance_pct = (variance / tr_total) * 100
print(f'Variance: ${variance:+,.0f} ({variance_pct:+.1f}%)')
print()

if abs(variance_pct) < 10:
    print('✓ EXCELLENT - Within 10% of TR reference')
elif abs(variance_pct) < 15:
    print('⚠️  GOOD - Within 15% of TR reference')
else:
    print('❌ NEEDS REVIEW - Variance > 15%')
