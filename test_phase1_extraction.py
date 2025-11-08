"""
Test Phase 1: Verify DiscreteLevelCalculator produces same results as original

This test verifies that the extracted DiscreteLevelCalculator produces identical
results to the original _calculate_discrete_level_areas() method in geometry.py.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import from the src.garage module
import src.garage as geom_module
from src.geometry.level_calculator import DiscreteLevelCalculator

SplitLevelParkingGarage = geom_module.SplitLevelParkingGarage

print("=" * 100)
print("PHASE 1 EXTRACTION VALIDATION TEST")
print("=" * 100)

# Test configuration: 2-bay, 210' length, 10 half-levels above, 0 below
length = 210
half_levels_above = 10
half_levels_below = 0
num_bays = 2

print(f"\nTest Configuration: {num_bays}-bay, {length}' length, {half_levels_above} above, {half_levels_below} below")
print("-" * 100)

# Create original garage (uses old integrated method)
print("\n1. Creating garage using ORIGINAL integrated method...")
garage_original = SplitLevelParkingGarage(length, half_levels_above, half_levels_below, num_bays)

# Extract data from original
original_levels = garage_original.levels
original_total_gsf = garage_original.total_gsf
original_sog_sf = garage_original.sog_levels_sf
original_suspended_sf = garage_original.suspended_levels_sf

print(f"   ✓ Original total GSF: {original_total_gsf:,.0f} SF")
print(f"   ✓ Original SOG: {original_sog_sf:,.0f} SF")
print(f"   ✓ Original suspended: {original_suspended_sf:,.0f} SF")
print(f"   ✓ Original levels: {len(original_levels)}")

# Create extracted level calculator
print("\n2. Creating garage using NEW extracted DiscreteLevelCalculator...")
footprint_sf = garage_original.footprint_sf
width = garage_original.width

level_calc = DiscreteLevelCalculator(
    footprint_sf=footprint_sf,
    width=width,
    length=length,
    half_levels_above=half_levels_above,
    half_levels_below=half_levels_below,
    entry_elevation=0.0
)

new_levels, summary = level_calc.calculate_all_levels()

print(f"   ✓ New total GSF: {summary['total_gsf']:,.0f} SF")
print(f"   ✓ New SOG: {summary['sog_sf']:,.0f} SF")
print(f"   ✓ New suspended: {summary['suspended_sf']:,.0f} SF")
print(f"   ✓ New levels: {summary['num_levels']}")

# Compare results
print("\n3. Comparing results...")
print("-" * 100)

passed = True

# Check totals
if abs(original_total_gsf - summary['total_gsf']) < 0.01:
    print(f"   ✓ Total GSF matches: {original_total_gsf:,.2f} SF")
else:
    print(f"   ✗ Total GSF MISMATCH: {original_total_gsf:,.2f} vs {summary['total_gsf']:,.2f}")
    passed = False

if abs(original_sog_sf - summary['sog_sf']) < 0.01:
    print(f"   ✓ SOG SF matches: {original_sog_sf:,.2f} SF")
else:
    print(f"   ✗ SOG SF MISMATCH: {original_sog_sf:,.2f} vs {summary['sog_sf']:,.2f}")
    passed = False

if abs(original_suspended_sf - summary['suspended_sf']) < 0.01:
    print(f"   ✓ Suspended SF matches: {original_suspended_sf:,.2f} SF")
else:
    print(f"   ✗ Suspended SF MISMATCH: {original_suspended_sf:,.2f} vs {summary['suspended_sf']:,.2f}")
    passed = False

# Check individual levels
if len(original_levels) == len(new_levels):
    print(f"   ✓ Level count matches: {len(original_levels)}")
else:
    print(f"   ✗ Level count MISMATCH: {len(original_levels)} vs {len(new_levels)}")
    passed = False

# Check each level in detail
all_levels_match = True
for i, (orig, new) in enumerate(zip(original_levels, new_levels)):
    orig_name, orig_gsf, orig_type, orig_elev = orig
    new_name, new_gsf, new_type, new_elev = new

    if (orig_name == new_name and
        abs(orig_gsf - new_gsf) < 0.01 and
        orig_type == new_type and
        abs(orig_elev - new_elev) < 0.01):
        # Match - silent
        pass
    else:
        print(f"   ✗ Level {i} MISMATCH:")
        print(f"      Original: {orig_name}, {orig_gsf:.2f} SF, {orig_type}, {orig_elev:.2f}'")
        print(f"      New:      {new_name}, {new_gsf:.2f} SF, {new_type}, {new_elev:.2f}'")
        all_levels_match = False
        passed = False

if all_levels_match:
    print(f"   ✓ All individual levels match")

# Final result
print("\n" + "=" * 100)
if passed:
    print("✓✓✓ PHASE 1 EXTRACTION: SUCCESS ✓✓✓")
    print("DiscreteLevelCalculator produces IDENTICAL results to original method")
else:
    print("✗✗✗ PHASE 1 EXTRACTION: FAILED ✗✗✗")
    print("Discrepancies found - review above")

print("=" * 100)

# Optionally print detailed breakdown
print("\n4. Detailed level-by-level comparison:")
print("-" * 100)
print(f"{'Index':<6} {'Original Name':<12} {'New Name':<12} {'Original GSF':<15} {'New GSF':<15} {'Match':<10}")
print("-" * 100)
for i, (orig, new) in enumerate(zip(original_levels, new_levels)):
    orig_name, orig_gsf, _, _ = orig
    new_name, new_gsf, _, _ = new
    match = "✓" if orig_name == new_name and abs(orig_gsf - new_gsf) < 0.01 else "✗"
    print(f"{i:<6} {orig_name:<12} {new_name:<12} {orig_gsf:>12,.0f} SF  {new_gsf:>12,.0f} SF  {match:<10}")

print("=" * 100)
