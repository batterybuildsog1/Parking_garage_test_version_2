"""
Test script to verify discrete level calculations match architectural plans
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.garage import SplitLevelParkingGarage

# Create reference design geometry
# TechRidge: 210' length, 10 half-levels above, 0 below, 2 bays
# Should create 126' × 210' = 26,460 SF footprint

garage = SplitLevelParkingGarage(
    length=210,
    half_levels_above=10,
    half_levels_below=0,
    num_bays=2
)

print("=" * 70)
print("DISCRETE LEVEL VERIFICATION")
print("=" * 70)
print(f"\nFootprint: {garage.width}' × {garage.length}' = {garage.footprint_sf:,.0f} SF")
print(f"Half-level GSF: {garage.footprint_sf / 2:,.0f} SF")
print(f"\n{'Level':<8} {'GSF':<12} {'Slab Type':<12}")
print("-" * 35)

total_check = 0
for level_name, gsf, slab_type, elevation in garage.levels:
    print(f"{level_name:<8} {gsf:>10,.0f} SF {slab_type:<12}")
    total_check += gsf

print("-" * 35)
print(f"{'TOTAL':<8} {total_check:>10,.0f} SF")
print(f"\nCalculated total_gsf: {garage.total_gsf:,.0f} SF")
print(f"Sum verification: {total_check:,.0f} SF")
print(f"Match: {'✓' if abs(total_check - garage.total_gsf) < 1 else '✗'}")

print(f"\n{' SOG vs SUSPENDED ':-^70}")
print(f"SOG levels: {garage.sog_levels_sf:,.0f} SF")
print(f"Suspended levels: {garage.suspended_levels_sf:,.0f} SF")
print(f"Sum: {garage.sog_levels_sf + garage.suspended_levels_sf:,.0f} SF")
print(f"Match total: {'✓' if abs((garage.sog_levels_sf + garage.suspended_levels_sf) - garage.total_gsf) < 1 else '✗'}")

print(f"\n{' ARCHITECTURAL PLAN COMPARISON ':-^70}")
print("Expected from plans:")
print("  P0.5:  15,073 SF")
print("  P1-4.5: 8 × 13,230 = 105,840 SF")
print("  P5:    6,412 SF")
print("  TOTAL: 127,325 SF")

print(f"\nCalculated:")
print(f"  P0.5:  {garage.levels[0][1]:,.0f} SF")
print(f"  Total: {garage.total_gsf:,.0f} SF")

# Check individual levels
entry_diff = abs(garage.levels[0][1] - 15073)
total_diff = abs(garage.total_gsf - 127325)

print(f"\n{' ACCURACY CHECK ':-^70}")
print(f"Entry level difference: {entry_diff:,.0f} SF ({entry_diff/15073*100:.1f}%)")
print(f"Total GSF difference: {total_diff:,.0f} SF ({total_diff/127325*100:.1f}%)")
print(f"\nAccuracy: {'✓ PASS' if total_diff < 500 else '✗ FAIL - needs adjustment'}")

print("=" * 70)
