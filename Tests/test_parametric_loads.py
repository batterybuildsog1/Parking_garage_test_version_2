"""
Test parametric load inputs and tributary area calculations

This test verifies:
1. Dead load PSF and Live load PSF are parametric (user-adjustable)
2. Tributary areas are calculated correctly for uniform 31' grid
3. Footing sizes scale correctly with bearing capacity changes
4. Column loads respond to DL/LL PSF changes
"""

from src.garage import SplitLevelParkingGarage
from src.footing_calculator import FootingCalculator
from src.tributary_calculator import TributaryCalculator, calculate_tributary_area_simple

def test_parametric_loads():
    """Test that DL/LL PSF parameters work correctly"""

    print("=" * 70)
    print("TEST 1: Parametric Load Inputs")
    print("=" * 70)

    # Create garage with DEFAULT loads (115 DL, 50 LL)
    garage_default = SplitLevelParkingGarage(
        length=210,
        half_levels_above=10,
        half_levels_below=0,
        num_bays=2,
        soil_bearing_capacity=2000,
        dead_load_psf=115.0,
        live_load_psf=50.0
    )

    # Create garage with INCREASED loads (150 DL, 75 LL)
    garage_increased = SplitLevelParkingGarage(
        length=210,
        half_levels_above=10,
        half_levels_below=0,
        num_bays=2,
        soil_bearing_capacity=2000,
        dead_load_psf=150.0,
        live_load_psf=75.0
    )

    print(f"\nGarage 1 (default loads):")
    print(f"  DL = {garage_default.dead_load_psf} PSF")
    print(f"  LL = {garage_default.live_load_psf} PSF")
    print(f"  Spread footing count: {garage_default.spread_footing_count}")
    print(f"  Spread footing concrete: {garage_default.spread_footing_concrete_cy:.1f} CY")

    print(f"\nGarage 2 (increased loads):")
    print(f"  DL = {garage_increased.dead_load_psf} PSF")
    print(f"  LL = {garage_increased.live_load_psf} PSF")
    print(f"  Spread footing count: {garage_increased.spread_footing_count}")
    print(f"  Spread footing concrete: {garage_increased.spread_footing_concrete_cy:.1f} CY")

    # Higher loads should result in more concrete (larger footings)
    assert garage_increased.spread_footing_concrete_cy > garage_default.spread_footing_concrete_cy, \
        "Higher loads should result in larger footings!"

    increase_pct = (garage_increased.spread_footing_concrete_cy / garage_default.spread_footing_concrete_cy - 1) * 100
    print(f"\n✓ PASS: Increased loads resulted in {increase_pct:.1f}% more footing concrete")

    print("\n" + "=" * 70)
    print("TEST 2: Bearing Capacity Scaling")
    print("=" * 70)

    # Create garages with different bearing capacities
    garage_2000 = SplitLevelParkingGarage(
        length=210,
        half_levels_above=10,
        half_levels_below=0,
        num_bays=2,
        soil_bearing_capacity=2000
    )

    garage_4000 = SplitLevelParkingGarage(
        length=210,
        half_levels_above=10,
        half_levels_below=0,
        num_bays=2,
        soil_bearing_capacity=4000
    )

    garage_7000 = SplitLevelParkingGarage(
        length=210,
        half_levels_above=10,
        half_levels_below=0,
        num_bays=2,
        soil_bearing_capacity=7000
    )

    print(f"\nBearing 2000 PSF: {garage_2000.spread_footing_concrete_cy:.1f} CY")
    print(f"Bearing 4000 PSF: {garage_4000.spread_footing_concrete_cy:.1f} CY")
    print(f"Bearing 7000 PSF: {garage_7000.spread_footing_concrete_cy:.1f} CY")

    # Higher bearing capacity should result in LESS concrete (smaller footings)
    assert garage_4000.spread_footing_concrete_cy < garage_2000.spread_footing_concrete_cy, \
        "Higher bearing capacity should result in smaller footings!"
    assert garage_7000.spread_footing_concrete_cy < garage_4000.spread_footing_concrete_cy, \
        "Higher bearing capacity should result in smaller footings!"

    print("\n✓ PASS: Footing sizes decrease with higher bearing capacity")

    print("\n" + "=" * 70)
    print("TEST 3: Tributary Area Calculation (Uniform Grid)")
    print("=" * 70)

    calc = TributaryCalculator()
    spacing = 31.0  # Standard parking garage column spacing

    # Test uniform grid tributary areas
    corner_area = calc.calculate_uniform_grid_tributary(spacing, 'corner')
    edge_area = calc.calculate_uniform_grid_tributary(spacing, 'edge')
    interior_area = calc.calculate_uniform_grid_tributary(spacing, 'interior')

    print(f"\nUniform 31' grid:")
    print(f"  Corner column: {corner_area:.1f} SF (should be ~240 SF)")
    print(f"  Edge column: {edge_area:.1f} SF (should be ~480 SF)")
    print(f"  Interior column: {interior_area:.1f} SF (should be ~961 SF)")

    # Verify expected values
    assert abs(corner_area - 240.25) < 1, f"Corner area {corner_area} doesn't match expected ~240 SF"
    assert abs(edge_area - 480.5) < 1, f"Edge area {edge_area} doesn't match expected ~480 SF"
    assert abs(interior_area - 961) < 1, f"Interior area {interior_area} doesn't match expected ~961 SF"

    print("\n✓ PASS: Tributary areas match expected values for uniform grid")

    print("\n" + "=" * 70)
    print("TEST 4: Variable Spacing Tributary Areas")
    print("=" * 70)

    # Test midpoint method with variable spacing
    # Example: Column between 45' and 36' bays in one direction, 31' uniform in other
    variable_area = calculate_tributary_area_simple({
        'north': 45,
        'south': 36,
        'east': 31,
        'west': 31
    })

    # Expected: (45/2 + 36/2) * (31/2 + 31/2) = 40.5 * 31 = 1255.5 SF
    expected_variable = 1255.5

    print(f"\nVariable spacing (45' N, 36' S, 31' E/W):")
    print(f"  Tributary area: {variable_area:.1f} SF")
    print(f"  Expected: {expected_variable:.1f} SF")

    assert abs(variable_area - expected_variable) < 1, \
        f"Variable spacing area {variable_area} doesn't match expected {expected_variable}"

    print("\n✓ PASS: Variable spacing tributary calculation works correctly")

    print("\n" + "=" * 70)
    print("TEST 5: Column Spacing Exposure")
    print("=" * 70)

    garage = SplitLevelParkingGarage(
        length=210,
        half_levels_above=10,
        half_levels_below=0,
        num_bays=2
    )

    print(f"\nGarage column_spacing_ft: {garage.column_spacing_ft}")
    print(f"Expected: 31.0")

    assert garage.column_spacing_ft == 31.0, "Column spacing not properly exposed!"

    print("\n✓ PASS: Column spacing is properly exposed as attribute")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED!")
    print("=" * 70)
    print("\n✓ Parametric loads work correctly")
    print("✓ Bearing capacity scaling works correctly")
    print("✓ Tributary areas calculate correctly for uniform grids")
    print("✓ Variable spacing support is functional")
    print("✓ Column spacing is properly exposed")

    return True

if __name__ == "__main__":
    test_parametric_loads()
