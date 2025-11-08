"""
DOUBLE-COUNTING AUDIT
Check where we might be counting costs twice
"""

from src.garage import SplitLevelParkingGarage
from src.cost_engine import CostCalculator, load_cost_database

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

print("=" * 100)
print("DOUBLE-COUNTING AUDIT")
print("=" * 100)
print()

print("QUESTION 1: Does $18/SF suspended slab rate INCLUDE rebar, PT, pumping?")
print("-" * 100)
print(f"Structure Above (slabs + columns):  ${costs['structure_above']:>12,.0f}")
print(f"  Uses: suspended_slab_sf × $18/SF + column_cy × $950/CY")
print()
print(f"Rebar (separate line item):         ${costs['rebar']:>12,.0f}")
print(f"Post-Tensioning (separate):         ${costs['post_tensioning']:>12,.0f}")
print(f"Concrete Pumping (separate):        ${costs['concrete_pumping']:>12,.0f}")
print()
print("If $18/SF already includes these, we're DOUBLE-COUNTING $941K!")
print()

print("QUESTION 2: Does Structure Below rate include rebar?")
print("-" * 100)
print(f"Structure Below uses $26/SF × 1.83 multiplier")
print(f"Structure Below cost:                ${costs['structure_below']:>12,.0f}")
print(f"Does this include rebar for below-grade elements?")
print()

print("QUESTION 3: Are MEP rates being applied correctly?")
print("-" * 100)
print(f"Old MEP rate: $7/SF × {garage.total_gsf:,.0f} SF = ${7 * garage.total_gsf:,.0f}")
print(f"New MEP rate: $10/SF × {garage.total_gsf:,.0f} SF = ${10 * garage.total_gsf:,.0f}")
print(f"Difference: ${(10-7) * garage.total_gsf:,.0f} MORE")
print(f"Our MEP cost: ${costs['mep']:>12,.0f}")
print()

print("QUESTION 4: Are Interior Finishes new or already in Site/Finishes?")
print("-" * 100)
print(f"Interior Finishes (new category):    ${costs['interior_finishes']:>12,.0f}")
print(f"  Includes: sealed concrete, painting, doors, cleaning")
print(f"Site/Finishes (existing):            ${costs['site_finishes']:>12,.0f}")
print(f"Could there be overlap?")
print()

print("QUESTION 5: Is VDC already included in General Conditions?")
print("-" * 100)
print(f"VDC Coordination (new):              ${costs['vdc_coordination']:>12,.0f}")
print(f"General Conditions:                  ${costs['general_conditions']:>12,.0f}")
print(f"GC is {costs['general_conditions'] / costs['hard_cost_subtotal'] * 100:.1f}% of hard costs")
print(f"Does GC already include coordination/management?")
print()

print("QUESTION 6: Compare our TOTAL STRUCTURE vs TechRidge")
print("-" * 100)
structure_items = [
    'structure_above',
    'structure_below',
    'rebar',
    'post_tensioning',
    'concrete_pumping',
    'core_walls',
    'stairs',
    'structural_accessories'
]
our_total_structure = sum(costs[item] for item in structure_items)
tr_superstructure = 6_044_740

print(f"Our total structure:                 ${our_total_structure:>12,.0f}")
print(f"TechRidge Superstructure:            ${tr_superstructure:>12,.0f}")
print(f"Variance:                            ${our_total_structure - tr_superstructure:>+12,.0f} ({(our_total_structure/tr_superstructure - 1)*100:+.1f}%)")
print()

print("BREAKDOWN OF OUR STRUCTURE:")
for item in structure_items:
    print(f"  {item:.<35} ${costs[item]:>12,.0f}")
print()

print("=" * 100)
print("KEY QUESTIONS TO INVESTIGATE:")
print("=" * 100)
print()
print("1. What does the $18/SF suspended slab rate include?")
print("   - Just concrete + formwork?")
print("   - Or concrete + formwork + rebar + PT + pumping?")
print()
print("2. What does the $26/SF structure rate (used for below-grade) include?")
print("   - Is it a fully-loaded rate?")
print()
print("3. Should rebar, PT, and pumping be SEPARATE line items or INCLUDED in slab rates?")
print()
print("4. Did we INCREASE MEP from $7/SF to $10/SF correctly?")
print("   - TechRidge uses $10/SF breakdown")
print("   - We were using $7/SF")
print("   - This adds ~$387K - is that intentional?")
print()
print("5. Is VDC coordination already part of General Conditions overhead?")
print()
