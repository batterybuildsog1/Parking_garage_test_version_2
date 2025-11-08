"""
Detailed cost audit comparing TechRidge budget to our model
"""

from src.garage import SplitLevelParkingGarage
from src.cost_engine import CostCalculator, load_cost_database
import json

# Configuration matching TechRidge: 126x210, 1 below + 8 above
garage = SplitLevelParkingGarage(
    length=210.0,
    half_levels_above=8,
    half_levels_below=1,
    num_bays=2,
    building_type='standalone'
)

# Load cost database
cost_db = load_cost_database()

# Calculate costs
cost_calc = CostCalculator(cost_db)
costs = cost_calc.calculate_all_costs(garage)

print("=" * 100)
print("DETAILED COST AUDIT - TechRidge vs Our Model")
print("=" * 100)
print()

print("GEOMETRY SUMMARY:")
print("-" * 100)
print(f"Dimensions: {garage.width}' x {garage.length}'")
print(f"Footprint: {garage.footprint_sf:,.0f} SF")
print(f"Total GSF: {garage.total_gsf:,.0f} SF (TechRidge: 127,325 SF)")
print(f"Total Stalls: {garage.total_stalls} (TechRidge: 319)")
print(f"Configuration: {1} below + {8} above = {9} half-levels")
print()

print("=" * 100)
print("COST BREAKDOWN - OUR MODEL")
print("=" * 100)
print()

# Display all cost categories from our model
print("FOUNDATION:")
print(f"  Total: ${costs['foundation']:,.0f}")
print()

print("EXCAVATION:")
print(f"  Total: ${costs['excavation']:,.0f}")
print()

print("STRUCTURE ABOVE GRADE:")
print(f"  Total: ${costs['structure_above']:,.0f}")
print()

print("STRUCTURE BELOW GRADE:")
print(f"  Total: ${costs['structure_below']:,.0f}")
print()

print("CONCRETE PUMPING:")
print(f"  Total: ${costs['concrete_pumping']:,.0f}")
print()

print("REBAR (by component):")
print(f"  Total: ${costs['rebar']:,.0f}")
print()

print("POST-TENSIONING:")
print(f"  Total: ${costs['post_tensioning']:,.0f}")
print()

print("CORE WALLS:")
print(f"  Total: ${costs['core_walls']:,.0f}")
print()

print("RETAINING WALLS:")
print(f"  Total: ${costs['retaining_walls']:,.0f}")
print()

print("ELEVATORS:")
print(f"  Total: ${costs['elevators']:,.0f}")
print()

print("STAIRS:")
print(f"  Total: ${costs['stairs']:,.0f}")
print()

print("MEP SYSTEMS:")
print(f"  Total: ${costs['mep']:,.0f}")
if hasattr(costs['mep'], '__getitem__'):
    if 'fire_protection' in costs['mep']:
        print(f"    Fire Protection: ${costs['mep']['fire_protection']:,.0f}")
    if 'plumbing' in costs['mep']:
        print(f"    Plumbing: ${costs['mep']['plumbing']:,.0f}")
    if 'hvac' in costs['mep']:
        print(f"    HVAC: ${costs['mep']['hvac']:,.0f}")
    if 'electrical' in costs['mep']:
        print(f"    Electrical: ${costs['mep']['electrical']:,.0f}")
print()

print("EXTERIOR:")
print(f"  Total: ${costs['exterior']:,.0f}")
print()

print("SITE/FINISHES:")
print(f"  Total: ${costs['site_finishes']:,.0f}")
print()

print("RAMP SYSTEM:")
print(f"  Total: ${costs['ramp_system']:,.0f}")
print()

print("-" * 100)
print(f"HARD COST SUBTOTAL: ${costs['hard_cost_subtotal']:,.0f}")
print()

print("GENERAL CONDITIONS:")
print(f"  Total: ${costs['general_conditions']:,.0f}")
print()

print("SOFT COSTS:")
print(f"  CM Fee: ${costs['cm_fee']:,.0f}")
print(f"  Insurance: ${costs['insurance']:,.0f}")
print(f"  Contingency: ${costs['contingency']:,.0f}")
print(f"  Soft Cost Subtotal: ${costs['soft_cost_subtotal']:,.0f}")
print()

print("=" * 100)
print(f"TOTAL COST: ${costs['total']:,.0f}")
print(f"Cost per SF: ${costs['cost_per_sf']:.2f}")
print(f"Cost per Stall: ${costs['cost_per_stall']:,.0f}")
print("=" * 100)
print()

print("=" * 100)
print("COMPARISON TO TECHRIDGE BUDGET (Parking Portion)")
print("=" * 100)
print()

# TechRidge parking costs from PDF
tr_costs = {
    "Foundation & Below-Grade": 965_907,
    "Superstructure": 6_044_740,
    "Exterior Closure": 829_840,
    "Roofing": 0,
    "Interior Finishes": 313_766,
    "Special Systems": 50_200,
    "Conveying Systems": 347_017,
    "Mechanical": 859_444,
    "Electrical": 413_806,
    "Site Work": 403_382,
    "General Conditions": 958_008,
    "CM Fee & Insurance": 625_882,
    "Contingency": 460_208,
}

tr_total = 12_272_200
tr_cost_per_sf = 96.38
tr_cost_per_stall = 38_471

print("TECHRIDGE BUDGET:")
print("-" * 100)
for category, cost in tr_costs.items():
    print(f"{category:.<50} ${cost:>12,.0f}")
print("-" * 100)
print(f"{'TOTAL':.<50} ${tr_total:>12,.0f}")
print(f"{'Cost per SF':.<50} ${tr_cost_per_sf:>12.2f}")
print(f"{'Cost per Stall':.<50} ${tr_cost_per_stall:>12,.0f}")
print()

print("=" * 100)
print("VARIANCE ANALYSIS")
print("=" * 100)
print()

# Calculate variance
total_variance = costs['total'] - tr_total
pct_variance = (costs['total'] / tr_total - 1) * 100

print(f"Our Total Cost: ${costs['total']:,.0f}")
print(f"TechRidge Total: ${tr_total:,.0f}")
print(f"Difference: ${total_variance:+,.0f} ({pct_variance:+.1f}%)")
print()

print("KEY COST CATEGORIES TO INVESTIGATE:")
print("-" * 100)
print()

# Map our categories to TechRidge
mapping = {
    "Foundation": ("Foundation & Below-Grade", costs['foundation'], 965_907),
    "Excavation": ("Foundation & Below-Grade (part)", costs['excavation'], "included above"),
    "Structure": ("Superstructure", costs['structure_above'] + costs['structure_below'], 6_044_740),
    "Rebar": ("Superstructure (part)", costs['rebar'], "included above"),
    "Post-Tensioning": ("Superstructure (part)", costs['post_tensioning'], "included above"),
    "Core Walls": ("Superstructure (part)", costs['core_walls'], "included above"),
    "Retaining Walls": ("Foundation (part)", costs['retaining_walls'], "included above"),
    "MEP": ("Mechanical + Electrical", costs['mep'], 859_444 + 413_806),
    "Exterior": ("Exterior Closure", costs['exterior'], 829_840),
    "Elevators": ("Conveying Systems", costs['elevators'], 347_017),
    "Stairs": ("Superstructure (part)", costs['stairs'], "included above"),
    "Site/Finishes": ("Site Work + Interior Finishes", costs['site_finishes'], 403_382 + 313_766),
}

for our_name, (tr_name, our_cost, tr_cost) in mapping.items():
    if isinstance(tr_cost, str):
        print(f"{our_name:.<30} ${our_cost:>12,.0f}  ->  {tr_name} ({tr_cost})")
    else:
        variance = our_cost - tr_cost if isinstance(tr_cost, (int, float)) else 0
        pct = (our_cost / tr_cost - 1) * 100 if tr_cost > 0 else 0
        status = "✓" if abs(pct) < 15 else "⚠️" if abs(pct) < 30 else "❌"
        print(f"{our_name:.<30} ${our_cost:>12,.0f}  vs  ${tr_cost:>12,.0f}  ({pct:+6.1f}%) {status}")

print()
print("=" * 100)
print("MISSING LINE ITEMS (PRELIMINARY)")
print("=" * 100)
print()
print("Categories that appear in TechRidge but may not be fully captured in our model:")
print()
print("1. Conveying Systems ($347,017 in TR)")
print(f"   Our model: ${costs['elevators']:,.0f}")
print("   - Check if includes: hoist, elevator finishes, permits, warranties")
print()
print("2. Site Work Details ($403,382 in TR)")
print(f"   Our model: ${costs['site_finishes']:,.0f}")
print("   - Check if includes: utilities, drainage, fencing, erosion control, surveying")
print()
print("3. Interior Finishes ($313,766 in TR)")
print("   - Check if includes: sealed concrete, painting, cleaning, doors")
print()
print("4. Special Systems ($50,200 in TR)")
print("   - Check if includes: fire extinguishers, bike racks, pavement markings")
print()

print("NEXT STEPS:")
print("-" * 100)
print("1. Deep dive into each cost category to identify specific missing line items")
print("2. Compare unit rates ($/SF, $/CY, $/LF) where quantities match")
print("3. Create detailed spreadsheet with ALL TechRidge line items vs our model")
print("4. Flag every missing incidental/tertiary cost")
