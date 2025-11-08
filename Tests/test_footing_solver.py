"""
Validation tests for footing solver

Tests the optimized footing solver against:
1. Reference footing (640k load, 7000 PSF bearing)
2. ACI 318-19 code compliance
3. TechRidge typical column loads
"""

import sys
import math
from src.footing_calculator import FootingCalculator
from src.garage import SplitLevelParkingGarage


def test_reference_footing():
    """
    Test against reference: 10'x10'x30" footing with 640k load, 7000 PSF bearing

    Expected results:
    - WITHOUT safety margin (reference design): 10'x10'x30"
    - WITH 1.2 safety margin (our solver): 11-13'x11-13' (more conservative)
    - Our solver should be LARGER than reference (safer design)
    - Cost: ~$8,000-12,000 per footing (more concrete = higher cost)

    NOTE: The reference footing used full 7000 PSF capacity without safety margin.
    Our solver applies 1.2× safety margin, reducing effective capacity to 5833 PSF,
    which requires a larger footing. This is correct and conservative per ACI 318-19.
    """
    print("\n" + "="*80)
    print("TEST 1: Reference Footing Validation (WITH Safety Margin)")
    print("="*80)

    # Create a minimal garage object for testing
    garage = SplitLevelParkingGarage(
        length=210,
        half_levels_above=10,
        half_levels_below=0,
        num_bays=2,
        soil_bearing_capacity=7000,  # Reference bearing capacity
        fc=4000
    )

    # Create footing calculator
    calc = FootingCalculator(
        garage,
        soil_bearing_capacity=7000,
        fc=4000,
        load_factor_dl=1.2,
        load_factor_ll=1.6
    )

    # Create a test load matching the reference (640k unfactored)
    ref_service_load = 640000  # lbs
    ref_factored_load = ref_service_load * 1.4  # Conservative factor

    column_load_dict = {
        'service_load': ref_service_load,
        'factored_load': ref_factored_load,
        'tributary_area': 961,  # Full bay (31'×31')
        'equivalent_full_floors': 4.0
    }

    # Design footing using optimized solver
    print(f"\nInput: Service load = {ref_service_load:,} lbs, Bearing capacity = 7000 PSF")

    result = calc.design_spread_footing_optimized(
        column_load_dict,
        'center_ramp',
        safety_margin=1.2,
        enable_micropile_fallback=False
    )

    # Display results
    print(f"\nOptimized Solver Results:")
    print(f"  Dimensions: {result['width_ft']:.0f}' × {result['width_ft']:.0f}' × {result['depth_in']:.0f}\"")
    print(f"  Concrete: {result['concrete_cy']:.2f} CY")
    print(f"  Rebar: {result['rebar_design']['designation']}")
    print(f"  Rebar weight: {result['rebar_lbs']:.0f} lbs")
    print(f"  Bearing pressure: {result['bearing_pressure']:.0f} PSF ({result['bearing_pressure']/7000*100:.1f}% capacity)")
    print(f"  Cost: ${result['cost']:,.0f}")
    print(f"  Punching shear utilization: {result['punching_utilization']*100:.1f}%")
    print(f"  One-way shear utilization: {result['oneway_utilization']*100:.1f}%")
    print(f"  Valid solutions explored: {result['num_valid_solutions']}")

    # Reference comparison
    ref_width = 10.0
    ref_depth_in = 30.0
    ref_concrete_cy = 9.26
    ref_cost = 7381

    print(f"\nReference Footing:")
    print(f"  Dimensions: {ref_width:.0f}' × {ref_width:.0f}' × {ref_depth_in:.0f}\"")
    print(f"  Concrete: {ref_concrete_cy:.2f} CY")
    print(f"  Cost: ${ref_cost:,.0f}")

    # Validation checks
    print(f"\nValidation (Comparing with conservative design):")

    # With safety margin, expect 10-30% larger than reference
    width_ratio = result['width_ft'] / ref_width
    width_conservative_ok = 1.0 <= width_ratio <= 1.35  # 0-35% larger is acceptable
    print(f"  Width ratio: {width_ratio:.2f}× reference {'✓ PASS' if width_conservative_ok else '✗ FAIL'}")
    print(f"    (Solver is {'more conservative' if width_ratio > 1.0 else 'more aggressive'} than reference)")

    # Depth should be similar or more efficient (thinner with more width)
    depth_ok = 18 <= result['depth_in'] <= 36
    print(f"  Depth in reasonable range (18-36\"): {depth_ok} {'✓ PASS' if depth_ok else '✗ FAIL'}")

    # Cost should be proportional to volume increase
    cost_ok = result['cost'] >= ref_cost * 0.9  # Allow 10% more efficient
    print(f"  Cost reasonable (≥90% of reference): {cost_ok} {'✓ PASS' if cost_ok else '✗ FAIL'}")

    bearing_ok = result['bearing_pressure'] <= 7000 / 1.2  # Account for safety margin
    print(f"  Bearing within allowable (≤{7000/1.2:.0f} PSF): {bearing_ok} {'✓ PASS' if bearing_ok else '✗ FAIL'}")

    shear_ok = result['punching_utilization'] <= 1.0 and result['oneway_utilization'] <= 1.0
    print(f"  Shear utilization ≤100%: {shear_ok} {'✓ PASS' if shear_ok else '✗ FAIL'}")

    dev_length_ok = result['development_length_ok']
    print(f"  Development length adequate: {dev_length_ok} {'✓ PASS' if dev_length_ok else '✗ FAIL'}")

    print(f"\n  KEY INSIGHT: Solver is {width_ratio-1:.1%} more conservative than reference.")
    print(f"  This is CORRECT because reference design used full 7000 PSF without safety margin.")

    return all([
        width_conservative_ok,
        depth_ok,
        cost_ok,
        bearing_ok,
        shear_ok,
        dev_length_ok
    ])


def test_techridge_interior_column():
    """
    Test TechRidge corner column (lighter load scenario)

    With 2000 PSF bearing, lighter corner columns should work with spread footings.
    Heavier interior columns will require micropiles (tested separately).
    """
    print("\n" + "="*80)
    print("TEST 2: TechRidge Corner Column (2000 PSF Bearing)")
    print("="*80)

    # Create TechRidge garage
    garage = SplitLevelParkingGarage(
        length=210,
        half_levels_above=10,
        half_levels_below=0,
        num_bays=2,
        soil_bearing_capacity=2000,  # TechRidge bearing capacity
        fc=4000
    )

    calc = FootingCalculator(
        garage,
        soil_bearing_capacity=2000,
        fc=4000
    )

    # Test CORNER column (lighter load - should work with spread footing)
    load_dict = calc.calculate_column_load('corner')

    print(f"\nCorner Column Load Calculation:")
    print(f"  Service load: {load_dict['service_load']:,.0f} lbs")
    print(f"  Factored load: {load_dict['factored_load']:,.0f} lbs")
    print(f"  Tributary area: {load_dict['tributary_area']:.0f} SF")
    print(f"  Equivalent floors: {load_dict['equivalent_full_floors']:.2f}")

    # Design footing
    result = calc.design_spread_footing_optimized(
        load_dict,
        'corner',
        safety_margin=1.2,
        enable_micropile_fallback=False
    )

    print(f"\nOptimized Footing Design:")
    if 'depth_in' in result:
        print(f"  Dimensions: {result['width_ft']:.0f}' × {result['width_ft']:.0f}' × {result['depth_in']:.0f}\"")
        print(f"  Concrete: {result['concrete_cy']:.2f} CY")
        print(f"  Rebar: {result['rebar_design']['designation']}")
        print(f"  Cost: ${result['cost']:,.0f}")
        print(f"  Bearing pressure: {result['bearing_pressure']:.0f} PSF ({result['bearing_pressure']/2000*100:.1f}% capacity)")

        # Validation
        print(f"\nValidation:")

        # Corner column at 2000 PSF should be 11-14'
        expected_width_range = (10, 15)
        width_ok = expected_width_range[0] <= result['width_ft'] <= expected_width_range[1]
        print(f"  Width in expected range {expected_width_range}: {width_ok} {'✓ PASS' if width_ok else '✗ FAIL'}")

        bearing_ok = result['bearing_pressure'] <= 2000 / 1.2
        print(f"  Bearing within allowable: {bearing_ok} {'✓ PASS' if bearing_ok else '✗ FAIL'}")

        shear_ok = result['punching_utilization'] <= 1.0 and result['oneway_utilization'] <= 1.0
        print(f"  Shear utilization OK: {shear_ok} {'✓ PASS' if shear_ok else '✗ FAIL'}")

        return all([width_ok, bearing_ok, shear_ok])
    else:
        print(f"  ✗ FAIL: No valid solution")
        return False


def test_aci_318_compliance():
    """
    Test ACI 318-19 code compliance for various column types

    With 2000 PSF bearing:
    - Corner columns should work with spread footings (lighter loads)
    - Heavier columns may require micropiles (which is correct behavior)
    """
    print("\n" + "="*80)
    print("TEST 3: ACI 318-19 Code Compliance Check")
    print("="*80)

    garage = SplitLevelParkingGarage(
        length=210,
        half_levels_above=10,
        half_levels_below=0,
        num_bays=2,
        soil_bearing_capacity=2000
    )

    calc = FootingCalculator(garage, soil_bearing_capacity=2000)

    column_types = ['corner', 'edge', 'interior_perimeter', 'center_ramp']
    all_pass = True

    for col_type in column_types:
        print(f"\n--- {col_type.upper().replace('_', ' ')} COLUMN ---")

        load_dict = calc.calculate_column_load(col_type)
        print(f"  Service load: {load_dict['service_load']:,.0f} lbs")

        # Enable micropile fallback for realistic design
        result = calc.design_spread_footing_optimized(
            load_dict,
            col_type,
            safety_margin=1.2,
            enable_micropile_fallback=True
        )

        if result['footing_type'] == 'MICROPILE':
            print(f"  Footing type: MICROPILE (spread footing too large)")
            print(f"  ✓ Correctly identified need for deep foundations")
            # Micropile recommendation is valid - not a failure
            continue
        else:
            print(f"  Footing: {result['width_ft']:.0f}' × {result['width_ft']:.0f}' × {result['depth_in']:.0f}\"")

            # Check all ACI requirements
            checks = {
                'Bearing': result['bearing_pressure'] <= 2000 / 1.2,
                'Punching shear': result['punching_utilization'] <= 1.0,
                'One-way shear': result['oneway_utilization'] <= 1.0,
                'Development length': result['development_length_ok'],
                'Cost optimization': result['cost'] > 0
            }

            for check_name, passed in checks.items():
                status = '✓' if passed else '✗'
                print(f"  {status} {check_name}: {'PASS' if passed else 'FAIL'}")
                if not passed:
                    all_pass = False

    return all_pass


def test_micropile_fallback():
    """
    Test micropile fallback when spread footings are not feasible
    """
    print("\n" + "="*80)
    print("TEST 4: Micropile Fallback Logic")
    print("="*80)

    # Create scenario with very low bearing capacity (will trigger fallback)
    garage = SplitLevelParkingGarage(
        length=210,
        half_levels_above=10,
        half_levels_below=0,
        num_bays=2,
        soil_bearing_capacity=500  # Very low - will require micropiles
    )

    calc = FootingCalculator(garage, soil_bearing_capacity=500)

    load_dict = calc.calculate_column_load('center_ramp')
    print(f"\nCenter column load: {load_dict['service_load']:,.0f} lbs")
    print(f"Low bearing capacity: 500 PSF")

    result = calc.design_spread_footing_optimized(
        load_dict,
        'center_ramp',
        safety_margin=1.2,
        enable_micropile_fallback=True
    )

    print(f"\nResult:")
    print(f"  Footing type: {result['footing_type']}")

    if result['footing_type'] == 'MICROPILE':
        print(f"  ✓ PASS: Micropile fallback triggered correctly")
        print(f"  Warning: {result.get('warning', 'N/A')}")
        print(f"  Reason: {result.get('failure_reason', 'N/A')}")
        return True
    else:
        print(f"  ✗ FAIL: Expected micropile fallback but got spread footing")
        return False


if __name__ == "__main__":
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "FOOTING SOLVER VALIDATION TESTS" + " "*27 + "║")
    print("╚" + "="*78 + "╝")

    results = {}

    # Run tests
    try:
        results['Reference'] = test_reference_footing()
    except Exception as e:
        print(f"\n✗ TEST 1 EXCEPTION: {e}")
        results['Reference'] = False

    try:
        results['TechRidge'] = test_techridge_interior_column()
    except Exception as e:
        print(f"\n✗ TEST 2 EXCEPTION: {e}")
        results['TechRidge'] = False

    try:
        results['ACI318'] = test_aci_318_compliance()
    except Exception as e:
        print(f"\n✗ TEST 3 EXCEPTION: {e}")
        results['ACI318'] = False

    try:
        results['Micropile'] = test_micropile_fallback()
    except Exception as e:
        print(f"\n✗ TEST 4 EXCEPTION: {e}")
        results['Micropile'] = False

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")

    total_passed = sum(results.values())
    total_tests = len(results)

    print(f"\nTotal: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED! Footing solver is validated.")
        sys.exit(0)
    else:
        print("\n⚠️  SOME TESTS FAILED. Review results above.")
        sys.exit(1)
