"""
Test detailed quantity takeoffs for 210x126, 1 below, 9 above scenario
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from garage import SplitLevelParkingGarage, load_cost_database
from cost_engine import CostCalculator

def test_210x126_1below_9above():
    """
    Test scenario: 210'x126', 1 below, 9 above

    This creates:
    - 210' length (split-level double ramp, < 250')
    - 126' width (2 bays)
    - 9 half-levels above ground (P0.5 through P4.5)
    - 1 half-level below ground (B-0.5)
    - Total: 10 half-levels
    """
    print("=" * 80)
    print("TEST: 210'x126' Garage, 1 Below, 9 Above")
    print("=" * 80)

    # Create garage
    garage = SplitLevelParkingGarage(
        length_ft=210,
        half_levels_above=9,
        half_levels_below=1,
        num_bays=2
    )

    # Load cost database and create calculator
    cost_db = load_cost_database()
    calculator = CostCalculator(cost_db)

    # Get basic metrics
    print(f"\n{'='*80}")
    print("BASIC METRICS")
    print(f"{'='*80}")
    print(f"Dimensions: {garage.length:.0f}' L × {garage.width:.0f}' W")
    print(f"Footprint: {garage.footprint_sf:,} SF")
    print(f"Total Levels: {garage.total_levels} half-levels")
    print(f"Total Height: {garage.total_height_ft:.2f} ft")
    print(f"Depth Below Grade: {garage.depth_below_grade_ft:.2f} ft")
    print(f"Ramp System: {garage.ramp_system.value}")
    print(f"Floor-to-Floor: {garage.floor_to_floor:.3f} ft")
    print(f"\nTotal GSF: {garage.total_gsf:,} SF")
    print(f"Total Stalls: {garage.total_stalls:,}")
    print(f"SF per Stall: {garage.total_gsf / garage.total_stalls:.1f} SF")

    # Get costs
    costs = calculator.calculate_all_costs(garage)
    print(f"\n{'='*80}")
    print("COST SUMMARY")
    print(f"{'='*80}")
    print(f"Total Cost: ${costs['total']:,.0f}")
    print(f"Cost per Stall: ${costs['cost_per_stall']:,.0f}")
    print(f"Cost per SF: ${costs['cost_per_sf']:.2f}")

    # Get detailed quantities
    detailed = calculator.get_detailed_quantity_takeoffs(garage)

    # Print each section summary
    print(f"\n{'='*80}")
    print("DETAILED QUANTITY SECTIONS")
    print(f"{'='*80}")

    for section_key, section_data in detailed.items():
        if section_key == '09_level_summary':
            # Special handling for level summary
            print(f"\n{section_data['title']}")
            print(f"  Total GSF: {section_data['total_gsf']:,} SF")
            print(f"  Total Stalls: {section_data['total_stalls']:,}")
            print(f"  Number of Levels: {len(section_data['levels'])}")

            # Show first few levels as example
            print(f"\n  Sample Levels:")
            for level in section_data['levels'][:5]:
                print(f"    {level['level_name']:8s} @ {level['elevation_ft']:7.2f}': " +
                      f"{level['gsf']:6,} SF, {level['stalls']:3.0f} stalls " +
                      f"({level['level_size']}, {level['level_type']})")
            if len(section_data['levels']) > 5:
                print(f"    ... ({len(section_data['levels']) - 5} more levels)")
        else:
            # Regular sections with items and totals
            print(f"\n{section_data['title']}")
            print(f"  Total: ${section_data['total']:,.0f}")
            print(f"  Items: {len(section_data['items'])}")

            # Show top 3 cost items
            sorted_items = sorted(
                section_data['items'],
                key=lambda x: x['total'] if x['total'] is not None else 0,
                reverse=True
            )
            print(f"  Top Components:")
            for item in sorted_items[:3]:
                if item['total'] is not None and item['total'] > 0:
                    print(f"    {item['component']:40s}: ${item['total']:12,.0f} " +
                          f"({item['quantity']:8,.1f} {item['unit']})")

    # Test helper methods directly
    print(f"\n{'='*80}")
    print("HELPER METHOD OUTPUTS")
    print(f"{'='*80}")

    # Wall linear feet
    wall_lf = garage.get_wall_linear_feet_breakdown()
    print(f"\nWall Linear Feet Breakdown:")
    for wall_type, data in wall_lf.items():
        if wall_type != 'total_wall_lf':
            if 'total_lf' in data:
                print(f"  {wall_type:25s}: {data['total_lf']:8,.0f} LF - {data['description']}")
            else:
                print(f"  {wall_type:25s}: {data['lf']:8,.0f} LF - {data['description']}")
    print(f"  {'TOTAL':25s}: {wall_lf['total_wall_lf']:8,.0f} LF")

    # Column breakdown
    column_data = garage.get_column_breakdown()
    print(f"\nColumn Breakdown:")
    print(f"  Total Count: {column_data['total_count']}")
    print(f"  Grid: {column_data['columns_width_direction']} × {column_data['columns_length_direction']} " +
          f"@ {column_data['grid_spacing_ft']}' spacing")
    print(f"  Size: {column_data['column_size']}")
    print(f"  Total Linear Feet: {column_data['total_linear_feet']:,.0f} LF")
    print(f"  {column_data['description']}")

    print(f"\n{'='*80}")
    print("TEST COMPLETE - All systems operational!")
    print(f"{'='*80}\n")

    return garage, costs, detailed


if __name__ == "__main__":
    garage, costs, detailed = test_210x126_1below_9above()
