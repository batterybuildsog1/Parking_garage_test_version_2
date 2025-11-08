"""
Check structure cost breakdown
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

print('OUR STRUCTURE BREAKDOWN:')
print(f'  Structure Above:        ${costs["structure_above"]:>12,.0f}')
print(f'  Structure Below:        ${costs["structure_below"]:>12,.0f}')
print(f'  Rebar (separate):       ${costs["rebar"]:>12,.0f}')
print(f'  Post-Tensioning (sep):  ${costs["post_tensioning"]:>12,.0f}')
print(f'  Concrete Pumping (sep): ${costs["concrete_pumping"]:>12,.0f}')
print(f'  Core Walls (sep):       ${costs["core_walls"]:>12,.0f}')
print(f'  Stairs (sep):           ${costs["stairs"]:>12,.0f}')
print(f'  Struct Accessories:     ${costs["structural_accessories"]:>12,.0f}')
print(f'  ------------------------')
total_structure = (costs["structure_above"] + costs["structure_below"] + costs["rebar"] +
                  costs["post_tensioning"] + costs["concrete_pumping"] + costs["core_walls"] +
                  costs["stairs"] + costs["structural_accessories"])
print(f'  TOTAL STRUCTURE:        ${total_structure:>12,.0f}')
print()
print(f'TechRidge Superstructure: ${6_044_740:>12,.0f}')
print()
print(f'Variance: ${total_structure - 6_044_740:+12,.0f} ({(total_structure/6_044_740 - 1)*100:+.1f}%)')
