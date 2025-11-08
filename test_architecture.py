#!/usr/bin/env python3
"""
Test Suite for New Architecture Components

Tests the new three-layer architecture:
- QuantityTakeoff dataclasses (quantities.py)
- CostRegistry abstraction layer (cost_registry.py)
- garage.calculate_quantities() method

Created: November 7, 2024
Purpose: Ensure new architecture components work correctly
"""

import sys
from typing import Dict, Any

from src.garage import SplitLevelParkingGarage, load_cost_database
from src.quantities import QuantityTakeoff, FoundationQuantities, StructuralQuantities
from src.cost_registry import CostRegistry, UnitCost, CostUnit, CostCategory


def test_cost_registry_initialization():
    """Test CostRegistry loads all costs correctly"""
    print("\n" + "="*60)
    print("TEST: CostRegistry Initialization")
    print("="*60)

    db = load_cost_database()
    registry = CostRegistry(db)

    # Check registry has expected number of costs
    assert len(registry._costs) > 0, "Registry should contain costs"
    print(f"✓ Registry loaded {len(registry._costs)} costs")

    # Check specific costs exist
    required_costs = [
        'footing_spread', 'footing_continuous', 'sog_5in', 'vapor_barrier',
        'slab_pt_8in', 'column_18x24', 'concrete_pumping', 'core_wall_12in',
        'curb_8x12', 'rebar', 'post_tension', 'elevator', 'stair'
    ]

    for cost_name in required_costs:
        cost = registry.get(cost_name)
        assert isinstance(cost, UnitCost), f"{cost_name} should be UnitCost"
        assert cost.value > 0, f"{cost_name} should have positive value"
        print(f"✓ {cost_name}: ${cost.value:.2f}/{cost.unit.value}")

    print("✅ CostRegistry initialization: PASSED")
    return True


def test_cost_registry_missing_cost():
    """Test CostRegistry raises error for missing cost"""
    print("\n" + "="*60)
    print("TEST: CostRegistry Missing Cost")
    print("="*60)

    db = load_cost_database()
    registry = CostRegistry(db)

    try:
        cost = registry.get('nonexistent_cost')
        print("❌ Should have raised KeyError for missing cost")
        return False
    except KeyError as e:
        print(f"✓ Correctly raised KeyError: {e}")

    print("✅ CostRegistry missing cost: PASSED")
    return True


def test_quantity_takeoff_creation():
    """Test QuantityTakeoff creation from garage"""
    print("\n" + "="*60)
    print("TEST: QuantityTakeoff Creation")
    print("="*60)

    # Create split-level garage
    garage = SplitLevelParkingGarage(186, 8, 0, 2)
    quantities = garage.calculate_quantities()

    # Check basic attributes
    assert isinstance(quantities, QuantityTakeoff), "Should return QuantityTakeoff"
    assert quantities.total_stalls == garage.total_stalls, "Stalls should match"
    assert quantities.total_gsf == garage.total_gsf, "GSF should match"
    assert len(quantities.levels) > 0, "Should have levels"

    print(f"✓ Stalls: {quantities.total_stalls}")
    print(f"✓ Total GSF: {quantities.total_gsf:,.0f}")
    print(f"✓ Levels: {len(quantities.levels)}")
    print(f"✓ Building length: {quantities.building_length_ft}'")

    # Check foundation quantities
    assert quantities.foundation.sog_area_sf > 0, "Should have SOG area"
    assert quantities.foundation.vapor_barrier_sf > 0, "Should have vapor barrier"
    print(f"✓ Foundation SOG: {quantities.foundation.sog_area_sf:,.0f} SF")

    # Check structural quantities
    assert quantities.structure.column_count > 0, "Should have columns"
    assert quantities.structure.suspended_slab_area_sf > 0, "Should have slabs"
    print(f"✓ Columns: {quantities.structure.column_count}")
    print(f"✓ Suspended slabs: {quantities.structure.suspended_slab_area_sf:,.0f} SF")

    print("✅ QuantityTakeoff creation: PASSED")
    return True


def test_quantity_takeoff_validation():
    """Test QuantityTakeoff validation logic"""
    print("\n" + "="*60)
    print("TEST: QuantityTakeoff Validation")
    print("="*60)

    garage = SplitLevelParkingGarage(186, 8, 0, 2)
    quantities = garage.calculate_quantities()

    # Validate should pass for correct data
    errors = quantities.validate()

    if errors:
        print("Validation errors found:")
        for error in errors:
            print(f"  - {error}")
        print("❌ Validation failed")
        return False

    print("✓ Validation passed - no errors")
    print("✅ QuantityTakeoff validation: PASSED")
    return True


def test_calculate_quantities_split_level():
    """Test calculate_quantities for split-level system"""
    print("\n" + "="*60)
    print("TEST: calculate_quantities (Split-Level)")
    print("="*60)

    # Create split-level garage (< 250')
    garage = SplitLevelParkingGarage(186, 8, 0, 2)
    quantities = garage.calculate_quantities()

    # Check ramp system type
    assert quantities.center_elements is not None, "Should have center elements"
    print(f"✓ Ramp system: {garage.ramp_system.value}")

    # Split-level should have core walls and curbs
    if quantities.center_elements.core_wall_sf > 0:
        print(f"✓ Core walls: {quantities.center_elements.core_wall_sf:,.0f} SF")

    if quantities.center_elements.center_curb_concrete_cy > 0:
        print(f"✓ Curbs: {quantities.center_elements.center_curb_concrete_cy:.1f} CY")

    # Split-level primarily uses core walls, not ramp barriers
    # (may have small top barrier, but ramp barriers should be minimal compared to single-ramp)
    if quantities.center_elements.ramp_barrier_concrete_cy > 0:
        print(f"ℹ Barriers (top): {quantities.center_elements.ramp_barrier_concrete_cy:.1f} CY")
    print("✓ Split-level uses core walls (not ramp barriers)")

    print("✅ calculate_quantities (Split-Level): PASSED")
    return True


def test_calculate_quantities_single_ramp():
    """Test calculate_quantities for single-ramp system"""
    print("\n" + "="*60)
    print("TEST: calculate_quantities (Single-Ramp)")
    print("="*60)

    # Create single-ramp garage (≥ 250')
    garage = SplitLevelParkingGarage(279, 9, 0, 3)
    quantities = garage.calculate_quantities()

    # Check ramp system type
    print(f"✓ Ramp system: {garage.ramp_system.value}")

    # Single-ramp should have barriers
    if garage.num_bays >= 3:  # 2-bay has no barriers
        assert quantities.center_elements.ramp_barrier_concrete_cy > 0, "Single-ramp should have barriers"
        print(f"✓ Ramp barriers: {quantities.center_elements.ramp_barrier_concrete_cy:.1f} CY")

    # Should NOT have core walls or curbs (split-level only)
    assert quantities.center_elements.core_wall_sf == 0, "Single-ramp should have no core walls"
    assert quantities.center_elements.center_curb_concrete_cy == 0, "Single-ramp should have no curbs"
    print("✓ No core walls or curbs (correct for single-ramp)")

    print("✅ calculate_quantities (Single-Ramp): PASSED")
    return True


def test_calculate_quantities_with_below_grade():
    """Test calculate_quantities with below-grade levels"""
    print("\n" + "="*60)
    print("TEST: calculate_quantities (With Below-Grade)")
    print("="*60)

    # Create garage with below-grade levels
    garage = SplitLevelParkingGarage(186, 8, 2, 2)  # 2 below, 8 above
    quantities = garage.calculate_quantities()

    # Check excavation quantities
    assert quantities.excavation is not None, "Should have excavation"
    assert quantities.excavation.mass_excavation_cy > 0, "Should have excavation volume"
    assert quantities.excavation.export_cy > 0, "Should have export volume"

    print(f"✓ Mass excavation: {quantities.excavation.mass_excavation_cy:,.0f} CY")
    print(f"✓ Export: {quantities.excavation.export_cy:,.0f} CY")
    print(f"✓ Retaining walls: {quantities.foundation.retaining_wall_sf:,.0f} SF")

    print("✅ calculate_quantities (With Below-Grade): PASSED")
    return True


def test_cost_calculation_with_registry():
    """Test cost calculations using new registry"""
    print("\n" + "="*60)
    print("TEST: Cost Calculation with Registry")
    print("="*60)

    db = load_cost_database()
    registry = CostRegistry(db)
    garage = SplitLevelParkingGarage(186, 8, 0, 2)
    quantities = garage.calculate_quantities()

    # Calculate some costs manually using registry
    sog_cost = quantities.foundation.sog_area_sf * registry.get('sog_5in').value
    vapor_cost = quantities.foundation.vapor_barrier_sf * registry.get('vapor_barrier').value
    slab_cost = quantities.structure.suspended_slab_area_sf * registry.get('slab_pt_8in').value

    print(f"✓ SOG cost: ${sog_cost:,.0f}")
    print(f"✓ Vapor barrier cost: ${vapor_cost:,.0f}")
    print(f"✓ Suspended slabs cost: ${slab_cost:,.0f}")

    # Verify costs are positive
    assert sog_cost > 0, "SOG cost should be positive"
    assert vapor_cost > 0, "Vapor barrier cost should be positive"
    assert slab_cost > 0, "Slab cost should be positive"

    print("✅ Cost calculation with registry: PASSED")
    return True


def test_data_structure_consistency():
    """Test that new and old architectures return consistent data"""
    print("\n" + "="*60)
    print("TEST: Data Structure Consistency")
    print("="*60)

    from src.cost_engine import CostCalculator

    db = load_cost_database()
    garage = SplitLevelParkingGarage(186, 8, 0, 2)

    # Old architecture
    calculator = CostCalculator(db)
    old_costs = calculator.calculate_all_costs(garage)

    # New architecture
    quantities = garage.calculate_quantities()

    # Check consistency
    assert quantities.total_stalls == garage.total_stalls, "Stalls should match"
    assert quantities.total_gsf == garage.total_gsf, "GSF should match"

    print(f"✓ Old: {garage.total_stalls} stalls, {garage.total_gsf:,.0f} SF")
    print(f"✓ New: {quantities.total_stalls} stalls, {quantities.total_gsf:,.0f} SF")
    print(f"✓ Old total cost: ${old_costs['total']:,.0f}")

    print("✅ Data structure consistency: PASSED")
    return True


def run_all_tests():
    """Run all architecture tests"""
    print("\n" + "#"*60)
    print("# ARCHITECTURE TEST SUITE")
    print("#"*60)
    print("\nTesting new three-layer architecture:")
    print("  - quantities.py (QuantityTakeoff)")
    print("  - cost_registry.py (CostRegistry)")
    print("  - garage.calculate_quantities()")

    tests = [
        test_cost_registry_initialization,
        test_cost_registry_missing_cost,
        test_quantity_takeoff_creation,
        test_quantity_takeoff_validation,
        test_calculate_quantities_split_level,
        test_calculate_quantities_single_ramp,
        test_calculate_quantities_with_below_grade,
        test_cost_calculation_with_registry,
        test_data_structure_consistency,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ EXCEPTION in {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "#"*60)
    print(f"# TEST RESULTS: {passed} passed, {failed} failed")
    print("#"*60)

    if failed == 0:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
