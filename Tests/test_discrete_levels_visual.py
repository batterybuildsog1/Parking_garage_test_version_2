"""
Visual test showing discrete level calculations with parametric flexibility
Demonstrates how users can adjust parameters to match their specific design
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.garage import SplitLevelParkingGarage

print("\n" + "=" * 80)
print(" PARAMETRIC SPLIT-LEVEL PARKING ANALYZER ".center(80, "="))
print("=" * 80)

# Create reference design with DEFAULT parameters
print("\nScenario 1: DEFAULT PARAMETERS (Conservative assumptions)")
print("-" * 80)

garage_default = SplitLevelParkingGarage(
    length=210,
    half_levels_above=10,
    half_levels_below=0,
    num_bays=2
)

garage_default.print_discrete_level_breakdown()

# Show comparison to architectural reference
print("\nREFERENCE DESIGN COMPARISON (TechRidge Architectural Plans)")
print("=" * 80)
print(f"{'Level':<10} {'Calculated':<15} {'Reference':<15} {'Difference':<15}")
print("-" * 80)

reference_data = {
    "P0.5": 15073,
    "P1": 13230,
    "P1.5": 13230,
    "P2": 13230,
    "P2.5": 13230,
    "P3": 13230,
    "P3.5": 13230,
    "P4": 13230,
    "P4.5": 13230,
    "P5": 6412
}

total_calc = 0
total_ref = 0

for level_name, gsf, _ in garage_default.levels:
    ref_gsf = reference_data.get(level_name, 0)
    diff = gsf - ref_gsf
    diff_pct = (diff / ref_gsf * 100) if ref_gsf > 0 else 0

    print(f"{level_name:<10} {gsf:>12,.0f} SF  {ref_gsf:>12,.0f} SF  {diff:>+8,.0f} SF ({diff_pct:>+5.1f}%)")

    total_calc += gsf
    total_ref += ref_gsf

print("-" * 80)
print(f"{'TOTAL':<10} {total_calc:>12,.0f} SF  {total_ref:>12,.0f} SF  {total_calc - total_ref:>+8,.0f} SF")
print("=" * 80)

# Show parameter adjustment guidance
print("\nPARAMETER ADJUSTMENT GUIDE")
print("=" * 80)
print("To match specific architectural plans, adjust these parameters:")
print()
print(f"1. Entry Level Reduction:")
print(f"   Current: FLAT_ENTRY_LENGTH = {garage_default.FLAT_ENTRY_LENGTH}' → Entry GSF = {garage_default.levels[0][1]:,.0f} SF")
print(f"   To match 15,073 SF: Need ~90' flat entry length")
print()
print(f"2. Top Level Reduction:")
print(f"   Current: RAMP_TERMINATION_LENGTH = {garage_default.RAMP_TERMINATION_LENGTH}' → Top GSF = {garage_default.levels[-1][1]:,.0f} SF")
print(f"   To match 6,412 SF: Need ~54' termination per side")
print()
print("These parameters are USER ADJUSTABLE based on actual design constraints:")
print("  - Entry zone influenced by: site access, circulation, elevator lobbies")
print("  - Top termination influenced by: mechanical equipment, roof access, solar panels")
print()
print("The PARAMETRIC ENGINE ensures costs scale correctly for ANY geometry!")
print("=" * 80)

# Test with different geometry to show parametric scaling
print("\n\nScenario 2: LARGER GEOMETRY (3-bay system)")
print("-" * 80)

garage_3bay = SplitLevelParkingGarage(
    length=240,
    half_levels_above=12,
    half_levels_below=0,
    num_bays=3
)

garage_3bay.print_discrete_level_breakdown()

print("\nNOTE: Total GSF scales with footprint × levels, NOT hardcoded!")
print("=" * 80)
