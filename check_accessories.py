"""
Check structural accessories breakdown
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

print(f'Garage columns: {garage.num_columns}')
print(f'Total GSF: {garage.total_gsf:,.0f} SF')
print(f'Footprint: {garage.footprint_sf:,.0f} SF')
print(f'Suspended slab SF: {garage.suspended_slab_sf:,.0f} SF')
print()

# Manually calculate each component
studs_per_column = cost_calc.component_costs['studs_per_column_count']
stud_cost = cost_calc.component_costs['stud_rails_per_column']
num_studs = garage.num_columns * studs_per_column
stud_rails_cost = num_studs * stud_cost

expansion_joint_lf = garage.footprint_sf * 0.047
expansion_joint_cost_lf = cost_calc.component_costs['expansion_joint_cost_per_lf']
expansion_joint_cost = expansion_joint_lf * expansion_joint_cost_lf

embeds_cost_sf = cost_calc.component_costs['embeds_anchor_bolts_per_sf_suspended']
embeds_cost = garage.suspended_slab_sf * embeds_cost_sf

misc_metals_lbs_sf = cost_calc.component_costs['misc_metals_lbs_per_sf_building']
misc_metals_lbs = garage.total_gsf * misc_metals_lbs_sf
misc_metals_tons = misc_metals_lbs / 2000
misc_metals_cost_ton = cost_calc.component_costs['misc_metals_cost_per_ton']
misc_metals_cost = misc_metals_tons * misc_metals_cost_ton

beam_allowance_sf = cost_calc.component_costs['beam_allowance_per_sf_building']
beam_allowance_cost = garage.total_gsf * beam_allowance_sf

print('STRUCTURAL ACCESSORIES BREAKDOWN:')
print(f'  Stud rails:            ${stud_rails_cost:>12,.0f}  ({num_studs} studs @ ${stud_cost}/ea)')
print(f'  Expansion joints:      ${expansion_joint_cost:>12,.0f}  ({expansion_joint_lf:.0f} LF @ ${expansion_joint_cost_lf}/LF)')
print(f'  Embeds/anchor bolts:   ${embeds_cost:>12,.0f}  ({garage.suspended_slab_sf:,.0f} SF @ ${embeds_cost_sf}/SF)')
print(f'  Misc metals:           ${misc_metals_cost:>12,.0f}  ({misc_metals_tons:.1f} tons @ ${misc_metals_cost_ton}/ton)')
print(f'  Beam allowance:        ${beam_allowance_cost:>12,.0f}  ({garage.total_gsf:,.0f} SF @ ${beam_allowance_sf}/SF)')
print(f'  ------------------------')
total_accessories = stud_rails_cost + expansion_joint_cost + embeds_cost + misc_metals_cost + beam_allowance_cost
print(f'  TOTAL:                 ${total_accessories:>12,.0f}')
print()
print('TECHRIDGE COMPARISON:')
print(f'  Stud rails (TR):       $    420,000')
print(f'  Expansion joints (TR): $    244,080')
print(f'  Embeds (TR):           $     30,027')
print(f'  Misc metals (TR):      $    266,892')
print(f'  Beam allowance (TR):   $    200,000')
print(f'  ------------------------')
print(f'  TR TOTAL:              $  1,161,000')
