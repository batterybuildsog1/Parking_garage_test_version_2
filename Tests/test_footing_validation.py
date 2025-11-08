"""
Footing Calculation Validation Test

This test validates that our footing calculations comply with ACI 318-19 and
properly adjust footing dimensions based on bearing capacity and loads.

Key validations:
1. Spread footings correctly sized for bearing capacity
2. Punching shear and one-way shear checks per ACI 318-19
3. Depth adjusts appropriately as bearing capacity changes
4. Baseline validation: 640 kips @ 7000 PSF → ~10' × 24-30"
"""

from src.footing_calculator import FootingCalculator
from src.garage import SplitLevelParkingGarage
import math


def test_spread_footing_bearing_capacity():
    """Test that footing width is correctly determined by bearing capacity"""
    print("=" * 80)
    print("TEST 1: Footing Width vs. Bearing Capacity")
    print("=" * 80)

    garage = SplitLevelParkingGarage(
        length=210,
        half_levels_above=6,
        half_levels_below=2,
        num_bays=2
    )

    # Interior column load should be ~642 kips service
    service_load = 642000  # lbs

    test_cases = [
        (2000, 18),  # 642k/2000 = 321 SF → 18' × 18' = 324 SF
        (4000, 13),  # 642k/4000 = 160 SF → 13' × 13' = 169 SF
        (7000, 10),  # 642k/7000 = 92 SF → 10' × 10' = 100 SF
    ]

    all_passed = True
    for bearing_psf, expected_width in test_cases:
        calc = FootingCalculator(garage, soil_bearing_capacity=bearing_psf, fc=4000)
        load_dict = calc.calculate_column_load('interior_perimeter')
        footing = calc.design_spread_footing(load_dict, 'interior_perimeter')

        req_area = service_load / bearing_psf
        calc_width = math.ceil(math.sqrt(req_area))

        passed = footing['width_ft'] == expected_width
        all_passed = all_passed and passed

        print(f"\nBearing {bearing_psf} PSF:")
        print(f"  Required area: {req_area:.1f} SF → {calc_width}' × {calc_width}'")
        print(f"  Expected: {expected_width}' × {expected_width}'")
        print(f"  Actual: {footing['width_ft']}' × {footing['width_ft']}'")
        print(f"  Status: {'✓ PASS' if passed else '✗ FAIL'}")

    print(f"\n{'='*80}")
    print(f"Test 1 Result: {'✓ ALL PASSED' if all_passed else '✗ SOME FAILED'}")
    print(f"{'='*80}\n")
    return all_passed


def test_punching_shear_governs():
    """Test that punching shear correctly governs footing depth"""
    print("=" * 80)
    print("TEST 2: Punching Shear Governance")
    print("=" * 80)

    garage = SplitLevelParkingGarage(
        length=210,
        half_levels_above=6,
        half_levels_below=2,
        num_bays=2
    )

    print("\nTesting across bearing capacities (640 kips load):")
    print(f"{'Bearing (PSF)':<15} {'Width':<10} {'Depth':<10} {'Punch Ratio':<15} {'1-Way Ratio':<15}")
    print("-" * 70)

    all_passed = True
    for bearing_psf in [2000, 4000, 7000]:
        calc = FootingCalculator(garage, soil_bearing_capacity=bearing_psf, fc=4000)
        load_dict = calc.calculate_column_load('interior_perimeter')
        footing = calc.design_spread_footing(load_dict, 'interior_perimeter')

        # Get shear ratios
        width_ft = footing['width_ft']
        d_inches = footing['depth_ft'] * 12 - 3  # Effective depth
        factored_load = load_dict['factored_load']

        # Calculate actual shear capacities and demands
        qu_psf = factored_load / (width_ft * width_ft)

        # Punching shear
        d_ft = d_inches / 12.0
        col_w_ft = 18 / 12.0
        col_d_ft = 24 / 12.0
        bo_ft = 2 * (col_w_ft + d_ft) + 2 * (col_d_ft + d_ft)
        bo_in = bo_ft * 12
        punch_area_sf = (col_w_ft + d_ft) * (col_d_ft + d_ft)
        Vu_punch = factored_load - (qu_psf * punch_area_sf)

        lambda_s = math.sqrt(2.0 / (1.0 + 0.004 * d_inches))
        beta = 24 / 18  # Column aspect ratio
        vc_psi = min(
            (2 + 4/beta) * lambda_s * math.sqrt(4000),
            (40 * d_inches / bo_in + 2) * lambda_s * math.sqrt(4000),
            4 * lambda_s * math.sqrt(4000)
        )
        phi_Vc_punch = 0.75 * vc_psi * bo_in * d_inches
        punch_ratio = phi_Vc_punch / Vu_punch

        # One-way shear
        cantilever_ft = (width_ft - col_w_ft) / 2.0 - d_ft
        Vu_oneway = qu_psf * width_ft * cantilever_ft
        vc_oneway_psi = 2 * lambda_s * math.sqrt(4000)
        phi_Vc_oneway = 0.75 * vc_oneway_psi * width_ft * 12 * d_inches
        oneway_ratio = phi_Vc_oneway / Vu_oneway

        # Punching should govern (have lower ratio)
        punching_governs = punch_ratio < oneway_ratio
        both_adequate = punch_ratio >= 1.0 and oneway_ratio >= 1.0

        passed = punching_governs and both_adequate
        all_passed = all_passed and passed

        print(f"{bearing_psf:<15} {width_ft}' × {width_ft}'   {footing['depth_ft']*12:.0f}\"      {punch_ratio:<15.2f} {oneway_ratio:<15.2f}")

    print(f"\n{'='*80}")
    print("Expected behavior: Punching shear governs (lower ratio) across all bearings")
    print(f"Test 2 Result: {'✓ ALL PASSED' if all_passed else '✗ SOME FAILED'}")
    print(f"{'='*80}\n")
    return all_passed


def test_baseline_validation():
    """Test against known baseline: 640 kips @ 7000 PSF → 10' × 30\" """
    print("=" * 80)
    print("TEST 3: Baseline Validation (TechRidge Reference)")
    print("=" * 80)

    garage = SplitLevelParkingGarage(
        length=210,
        half_levels_above=6,
        half_levels_below=2,
        num_bays=2
    )

    calc = FootingCalculator(garage, soil_bearing_capacity=7000, fc=4000)
    load_dict = calc.calculate_column_load('interior_perimeter')
    footing = calc.design_spread_footing(load_dict, 'interior_perimeter')

    print(f"\nLoad: {load_dict['service_load']/1000:.0f} kips service, {load_dict['factored_load']/1000:.0f} kips factored")
    print(f"Bearing Capacity: 7000 PSF")
    print(f"f'c: 4000 PSI")
    print()
    print(f"TechRidge Baseline: 10' × 10' × 30\"")
    print(f"Our Calculation:    {footing['width_ft']}' × {footing['width_ft']}' × {footing['depth_ft']*12:.0f}\"")
    print()

    width_matches = footing['width_ft'] == 10
    depth_close = abs(footing['depth_ft'] * 12 - 30) <= 6  # Within 6"

    print(f"Width matches: {'✓' if width_matches else '✗'}")
    print(f"Depth within 6\": {'✓' if depth_close else '✗'} (difference: {abs(footing['depth_ft']*12 - 30):.0f}\")")

    passed = width_matches and depth_close

    print(f"\n{'='*80}")
    print(f"Test 3 Result: {'✓ PASSED' if passed else '✗ FAILED'}")
    print(f"{'='*80}\n")
    return passed


def test_depth_adjusts_with_bearing():
    """Test that depth appropriately adjusts as bearing capacity changes"""
    print("=" * 80)
    print("TEST 4: Depth Adjustment with Bearing Capacity")
    print("=" * 80)

    garage = SplitLevelParkingGarage(
        length=210,
        half_levels_above=6,
        half_levels_below=2,
        num_bays=2
    )

    print("\nDepth behavior across bearing capacities:")
    print(f"{'Bearing (PSF)':<15} {'Width (ft)':<12} {'Depth (in)':<12} {'Soil Pressure (PSF)'}")
    print("-" * 60)

    depths = []
    for bearing_psf in [2000, 3000, 4000, 5000, 6000, 7000]:
        calc = FootingCalculator(garage, soil_bearing_capacity=bearing_psf, fc=4000)
        load_dict = calc.calculate_column_load('interior_perimeter')
        footing = calc.design_spread_footing(load_dict, 'interior_perimeter')

        depth_in = footing['depth_ft'] * 12
        depths.append(depth_in)

        qu_psf = load_dict['factored_load'] / (footing['width_ft'] ** 2)

        print(f"{bearing_psf:<15} {footing['width_ft']:<12} {depth_in:<12.0f} {qu_psf:.0f}")

    # Depth should decrease or stay similar (within 6") as bearing increases
    # But NOT increase significantly due to punching shear effects
    max_depth = max(depths)
    min_depth = min(depths)
    depth_variation = max_depth - min_depth

    print(f"\nDepth range: {min_depth:.0f}\" to {max_depth:.0f}\" (variation: {depth_variation:.0f}\")")
    print(f"Expected: Depth stays relatively constant or decreases slightly")
    print(f"  (Punching shear governs, offsetting width reduction)")

    # Test passes if depth variation is reasonable (not extreme changes)
    passed = depth_variation <= 12  # Within 12" is reasonable

    print(f"\n{'='*80}")
    print(f"Test 4 Result: {'✓ PASSED' if passed else '✗ FAILED'}")
    print(f"{'='*80}\n")
    return passed


if __name__ == "__main__":
    print("\n")
    print("#" * 80)
    print("# FOOTING CALCULATION VALIDATION TESTS")
    print("# ACI 318-19 Compliance Verification")
    print("#" * 80)
    print()

    results = []

    results.append(("Bearing Capacity → Width", test_spread_footing_bearing_capacity()))
    results.append(("Punching Shear Governance", test_punching_shear_governs()))
    results.append(("Baseline Validation", test_baseline_validation()))
    results.append(("Depth Adjustment", test_depth_adjusts_with_bearing()))

    print("\n")
    print("#" * 80)
    print("# FINAL RESULTS")
    print("#" * 80)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:<40} {status}")

    print()
    all_passed = all(result[1] for result in results)
    if all_passed:
        print("=" * 80)
        print("✓ ALL TESTS PASSED - Footing calculations are ACI 318-19 compliant")
        print("=" * 80)
    else:
        print("=" * 80)
        print("✗ SOME TESTS FAILED - Review footing calculations")
        print("=" * 80)
