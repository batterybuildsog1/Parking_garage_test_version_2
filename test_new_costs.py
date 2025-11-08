"""
Quick test to see new cost categories
"""

from src.garage import SplitLevelParkingGarage
from src.cost_engine import CostCalculator, load_cost_database

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
print("NEW COST CATEGORIES")
print("=" * 100)
print()

print(f"Structural Accessories:    ${costs.get('structural_accessories', 0):>12,.0f}")
print(f"Interior Finishes:         ${costs.get('interior_finishes', 0):>12,.0f}")
print(f"Special Systems:           ${costs.get('special_systems', 0):>12,.0f}")
print(f"VDC Coordination:          ${costs.get('vdc_coordination', 0):>12,.0f}")
print()

print(f"MEP (updated to $10/SF):   ${costs['mep']:>12,.0f}")
print(f"  (was $7/SF, now broken out into 4 systems @ $3+$1.50+$2.25+$3.25)")
print()

print("=" * 100)
print(f"TOTAL COST:                ${costs['total']:>12,.0f}")
print(f"TechRidge Budget:          ${12_272_200:>12,.0f}")
print(f"Variance:                  ${costs['total'] - 12_272_200:>+12,.0f} ({(costs['total'] / 12_272_200 - 1) * 100:+.1f}%)")
print("=" * 100)
