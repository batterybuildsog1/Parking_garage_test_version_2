"""
Cost validation test - verifies double-count fix and TR comparison

This test confirms:
1. Footing rebar is NOT double-counted
2. Total costs are within reasonable range of TechRidge budget
3. All cost components sum correctly
"""

from src.garage import SplitLevelParkingGarage
from src.cost_engine import CostCalculator, load_cost_database


def test_footing_rebar_not_double_counted():
    """Verify footing rebar appears in foundation only, not in rebar component"""
    garage = SplitLevelParkingGarage(
        length=210.0,
        half_levels_above=8,
        half_levels_below=1,
        num_bays=2,
        building_type='standalone'
    )

    cost_db = load_cost_database()
    cost_calc = CostCalculator(cost_db)
    costs = cost_calc.calculate_all_costs(garage)

    # Calculate what footing rebar cost SHOULD be (from foundation only)
    expected_footing_rebar_lbs = (
        garage.spread_footing_rebar_lbs +
        garage.continuous_footing_rebar_lbs +
        garage.retaining_wall_footing_rebar_lbs
    )
    expected_footing_rebar_cost = (
        expected_footing_rebar_lbs *
        cost_db['unit_costs']['foundation']['rebar_footings_lbs']
    )

    # Foundation cost should include footing rebar
    assert costs['foundation'] > 0, "Foundation cost should be non-zero"

    # Rebar component cost should NOT include footing rebar
    # It should only include: column rebar + slab rebar
    expected_rebar_cost = (
        garage.concrete_columns_cy *
        cost_db['component_specific_costs']['rebar_columns_lbs_per_cy_concrete'] *
        cost_db['component_specific_costs']['rebar_cost_per_lb']
    ) + (
        garage.total_slab_sf *
        cost_db['component_specific_costs']['rebar_pt_slab_lbs_per_sf'] *
        cost_db['component_specific_costs']['rebar_cost_per_lb']
    )

    # Allow 1% tolerance for rounding
    assert abs(costs['rebar'] - expected_rebar_cost) / expected_rebar_cost < 0.01, \
        f"Rebar cost mismatch: {costs['rebar']:,.0f} vs expected {expected_rebar_cost:,.0f}"

    print("✓ Footing rebar NOT double-counted")
    print(f"  Foundation includes footing rebar: ${expected_footing_rebar_cost:,.0f}")
    print(f"  Rebar component (column + slab only): ${costs['rebar']:,.0f}")


def test_total_costs_reasonable():
    """Verify total costs are within 20% of TechRidge budget"""
    garage = SplitLevelParkingGarage(
        length=210.0,
        half_levels_above=8,
        half_levels_below=1,
        num_bays=2,
        building_type='standalone'
    )

    cost_db = load_cost_database()
    cost_calc = CostCalculator(cost_db)
    costs = cost_calc.calculate_all_costs(garage)

    # TechRidge parking budget
    tr_total = 12_272_200
    tr_cost_per_sf = 96.38
    tr_cost_per_stall = 38_471

    # Check total cost within 20%
    variance_pct = abs(costs['total'] - tr_total) / tr_total * 100

    print(f"\n{'='*80}")
    print("COST COMPARISON TO TECHRIDGE")
    print(f"{'='*80}")
    print(f"Our Total:       ${costs['total']:>12,.0f}")
    print(f"TR Total:        ${tr_total:>12,.0f}")
    print(f"Variance:        ${costs['total'] - tr_total:>+12,.0f} ({(costs['total']/tr_total - 1)*100:+.1f}%)")
    print()
    print(f"Our $/SF:        ${costs['cost_per_sf']:>12.2f}")
    print(f"TR $/SF:         ${tr_cost_per_sf:>12.2f}")
    print()
    print(f"Our $/stall:     ${costs['cost_per_stall']:>12,.0f}")
    print(f"TR $/stall:      ${tr_cost_per_stall:>12,.0f}")
    print(f"{'='*80}\n")

    # We expect some variance (different design), but should be within 20%
    assert variance_pct < 20, f"Total cost variance too high: {variance_pct:.1f}%"
    print(f"✓ Total cost within reasonable range (±20%)")


def test_cost_components_sum_correctly():
    """Verify hard costs + soft costs = total"""
    garage = SplitLevelParkingGarage(
        length=210.0,
        half_levels_above=8,
        half_levels_below=1,
        num_bays=2,
        building_type='standalone'
    )

    cost_db = load_cost_database()
    cost_calc = CostCalculator(cost_db)
    costs = cost_calc.calculate_all_costs(garage)

    # Verify subtotals
    assert costs['hard_cost_subtotal'] > 0, "Hard costs should be non-zero"
    assert costs['soft_cost_subtotal'] > 0, "Soft costs should be non-zero"

    # Verify total = hard + soft
    calculated_total = costs['hard_cost_subtotal'] + costs['soft_cost_subtotal']
    assert abs(costs['total'] - calculated_total) < 1, \
        f"Total mismatch: {costs['total']:.2f} vs {calculated_total:.2f}"

    print(f"✓ Cost components sum correctly")
    print(f"  Hard costs:  ${costs['hard_cost_subtotal']:,.0f}")
    print(f"  Soft costs:  ${costs['soft_cost_subtotal']:,.0f}")
    print(f"  Total:       ${costs['total']:,.0f}")


def test_soft_costs_base_calculation():
    """Verify soft costs are calculated on (hard + GC), not hard alone"""
    garage = SplitLevelParkingGarage(
        length=210.0,
        half_levels_above=8,
        half_levels_below=1,
        num_bays=2,
        building_type='standalone'
    )

    cost_db = load_cost_database()
    cost_calc = CostCalculator(cost_db)
    costs = cost_calc.calculate_all_costs(garage)

    # Soft cost base should be hard + GC
    soft_cost_base = costs['hard_cost_subtotal'] + costs['general_conditions']

    # Recalculate soft costs
    expected_cm_fee = soft_cost_base * cost_db['soft_costs_percentages']['cm_fee']
    expected_insurance = soft_cost_base * cost_db['soft_costs_percentages']['insurance']
    expected_contingency = soft_cost_base * (
        cost_db['soft_costs_percentages']['contingency_cm'] +
        cost_db['soft_costs_percentages']['contingency_design']
    )

    # Allow small rounding tolerance
    assert abs(costs['cm_fee'] - expected_cm_fee) < 1
    assert abs(costs['insurance'] - expected_insurance) < 1
    assert abs(costs['contingency'] - expected_contingency) < 1

    print(f"✓ Soft costs calculated correctly on (hard + GC)")
    print(f"  Base: ${soft_cost_base:,.0f}")
    print(f"  CM Fee: ${costs['cm_fee']:,.0f}")
    print(f"  Insurance: ${costs['insurance']:,.0f}")
    print(f"  Contingency: ${costs['contingency']:,.0f}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("COST VALIDATION TEST SUITE")
    print("="*80 + "\n")

    test_footing_rebar_not_double_counted()
    print()

    test_total_costs_reasonable()
    print()

    test_cost_components_sum_correctly()
    print()

    test_soft_costs_base_calculation()
    print()

    print("="*80)
    print("ALL TESTS PASSED ✓")
    print("="*80)
