#!/usr/bin/env python3
"""
Test to verify the single-ramp mode fix for center_core_wall_concrete_cy attribute.

This test ensures that buildings with length >= 250' (single-ramp mode) can
successfully instantiate and call get_summary() without AttributeError.
"""

import sys
from src.garage import SplitLevelParkingGarage

def test_single_ramp_mode():
    """Test single-ramp mode at various lengths and bay configurations"""

    test_cases = [
        {"length": 250, "bays": 2, "desc": "250' boundary, 2-bay"},
        {"length": 250, "bays": 3, "desc": "250' boundary, 3-bay"},
        {"length": 280, "bays": 2, "desc": "280' mid-range, 2-bay"},
        {"length": 280, "bays": 3, "desc": "280' mid-range, 3-bay"},
        {"length": 360, "bays": 2, "desc": "360' maximum, 2-bay"},
        {"length": 360, "bays": 7, "desc": "360' maximum, 7-bay"},
    ]

    print("=" * 70)
    print("SINGLE-RAMP MODE FIX VERIFICATION TEST")
    print("=" * 70)
    print()

    all_passed = True

    for case in test_cases:
        length = case["length"]
        num_bays = case["bays"]
        desc = case["desc"]

        try:
            print(f"Testing: {desc}")
            print(f"  Length: {length}', Bays: {num_bays}")

            # Instantiate garage (should not raise AttributeError)
            garage = SplitLevelParkingGarage(
                length=length,
                num_bays=num_bays,
                half_levels_above=6,
                half_levels_below=0
            )

            # Verify it's in single-ramp mode
            assert not garage.is_half_level_system, f"Expected single-ramp mode for {length}'"

            # Call get_summary() (this was failing before the fix)
            summary = garage.get_summary()

            # Verify the attribute exists and is 0
            assert hasattr(garage, 'center_core_wall_concrete_cy'), \
                "Missing center_core_wall_concrete_cy attribute"
            assert garage.center_core_wall_concrete_cy == 0, \
                f"Expected 0, got {garage.center_core_wall_concrete_cy}"

            # Verify summary contains the key
            assert 'center_core_wall_concrete_cy' in summary['structure'], \
                "Missing center_core_wall_concrete_cy in summary"

            print(f"  ✓ PASS - center_core_wall_concrete_cy = {garage.center_core_wall_concrete_cy}")
            print(f"  ✓ Total stalls: {garage.total_stalls}")
            print()

        except AssertionError as e:
            print(f"  ✗ FAIL - Assertion: {e}")
            print()
            all_passed = False

        except AttributeError as e:
            print(f"  ✗ FAIL - AttributeError: {e}")
            print()
            all_passed = False

        except Exception as e:
            print(f"  ✗ FAIL - Unexpected error: {type(e).__name__}: {e}")
            print()
            all_passed = False

    print("=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("Single-ramp mode correctly sets center_core_wall_concrete_cy = 0")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(test_single_ramp_mode())
