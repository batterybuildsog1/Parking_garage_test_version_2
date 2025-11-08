from src.garage import SplitLevelParkingGarage
from src.cost_engine import CostCalculator, load_cost_database
from src.footing_calculator import FootingCalculator
import json

# Configuration from TechRidge budget: 126x210, 1 below + 8 above half-levels
# 126' width = 2 bays: 1' + (2 * 61') + (1 * 3') = 1 + 122 + 3 = 126'
num_bays = 2
length = 210.0
half_levels_above = 8  # P0.5, P1, P1.5, P2, P2.5, P3, P3.5, P4
half_levels_below = 2  # One below-grade level as B-0.5 and B-1 (1 full level = 2 half-levels)

garage = SplitLevelParkingGarage(
    length=length,
    half_levels_above=half_levels_above,
    half_levels_below=half_levels_below,
    num_bays=num_bays,
    building_type='standalone'
)

# Load cost database
cost_db = load_cost_database()

# Calculate costs
cost_calc = CostCalculator(cost_db)

print("=" * 80)
print("GEOMETRY COMPARISON")
print("=" * 80)
print(f"Dimensions: {garage.width}' x {garage.length}'")
print(f"Footprint: {garage.footprint_sf:,.0f} SF")
print(f"Total GSF: {garage.total_gsf:,.0f} SF")
print(f"Total Stalls: {garage.total_stalls}")
print(f"Levels above: {half_levels_above} half-levels")
print(f"Levels below: {half_levels_below} half-levels")
print(f"Ramp system: {garage.ramp_system}")
print()

print("TechRidge Budget (from PDF):")
print("  - Parking GSF: 127,325 SF")
print("  - Total Stalls: 319 stalls")
print("  - Parking levels: P0.5, P1-P5")
print()

# Get detailed costs
costs = cost_calc.calculate_all_costs(garage)

print("=" * 80)
print("COST BREAKDOWN COMPARISON")
print("=" * 80)
print()

# Foundation
print("FOUNDATION & BELOW-GRADE")
print("-" * 80)
foundation = costs["foundation"]
print(f"Our Total Foundation: ${foundation['total']:,.0f}")
print(f"  - Slab on Grade: ${foundation['slab_on_grade']:,.0f}")
print(f"  - Vapor Barrier: ${foundation['vapor_barrier']:,.0f}")
print(f"  - Gravel: ${foundation['gravel']:,.0f}")
print(f"  - Spread Footings: ${foundation['spread_footings']:,.0f}")
print(f"  - Continuous Footings: ${foundation['continuous_footings']:,.0f}")
print()

print("TechRidge Budget - Foundation (Parking portion):")
print("  - Slab on Grade 5\": $158,760 (26,460 SF @ $6.00)")
print("  - Vapor Barrier: Included in apartments")
print("  - Gravel 4\": $25,140 (from line 78)")
print("  - Footings excavation: $14,979")
print("  - Backfill foundation: $29,265")
print("  - Backfill at ramp: $42,787")
print("  - Continuous footings: ~$947,146")
print("  - Spot footings: ~$154,620")
print("  - Foundation walls (12\" core walls below grade): $163,354")
print()

# Structure
print("SUPERSTRUCTURE")
print("-" * 80)
structure = costs["structure"]
print(f"Our Total Structure: ${structure['total']:,.0f}")
print(f"  - PT Slabs: ${structure['pt_slabs']:,.0f}")
print(f"  - Columns: ${structure['columns']:,.0f}")
print(f"  - Center Elements (walls/curbs/columns): ${structure['center_elements']:,.0f}")
print(f"  - Spandrel Beams: ${structure['spandrel_beams']:,.0f}")
print()

print("TechRidge Budget - Structure (Parking portion):")
print("  - Suspended slabs 8\" PT: $1,489,960 (85,792 SF @ $18)")
print("  - Columns CC18A (18x24): $186,200 (196 CY @ $950)")
print("  - Shear walls 12\" (core walls): $1,632,558 (55,440 SF @ $28.50)")
print("  - Parking barrier walls: $23,100 (840 SF @ $27.50)")
print("  - Post-tension cables: $188,742 (171,584 lbs @ $1.10)")
print("  - Reinforcing steel (various): ~$1,070,000")
print("  - Additional beam allowance: $200,000")
print()

# Excavation
print("EXCAVATION & EARTHWORK")
print("-" * 80)
excavation = costs["excavation"]
print(f"Our Total Excavation: ${excavation['total']:,.0f}")
print(f"  - Excavation: ${excavation['excavation']:,.0f}")
print(f"  - Export: ${excavation['export']:,.0f}")
print(f"  - Structural Fill: ${excavation['structural_fill']:,.0f}")
print(f"  - Retaining Walls: ${excavation['retaining_walls']:,.0f}")
print(f"  - Waterproofing: ${excavation['waterproofing']:,.0f}")
print()

print("TechRidge Budget - Below-Grade (Parking portion):")
print("  - Mass excavation 3.5': $30,672 (9,327 CY @ $8)")
print("  - Import and place fill: $48,132 (3,346 CY @ $35)")
print("  - Over excavation 6': $216,586")
print("  - Waterproofing: $15,420 (fluid applied)")
print()

# MEP
print("MEP SYSTEMS")
print("-" * 80)
mep = costs["mep"]
print(f"Our Total MEP: ${mep['total']:,.0f}")
print(f"  Applied to: {garage.total_gsf:,.0f} SF")
print()

print("TechRidge Budget - MEP (Parking portion):")
print("  - Fire Protection: $381,975 (127,325 SF @ $3.00)")
print("  - Plumbing: $190,988 (127,325 SF @ $1.50)")
print("  - HVAC: $286,481 (127,325 SF @ $2.25)")
print("  - Electrical: $413,806 (127,325 SF @ $3.25)")
print("  - Total MEP: $1,273,250 (~$10.00/SF)")
print()

# General Conditions
print("GENERAL CONDITIONS")
print("-" * 80)
gc = costs["general_conditions"]
print(f"Our General Conditions: ${gc:,.0f}")
print()

print("TechRidge Budget - General Conditions (Parking portion):")
print("  - General Conditions: $958,008 (26 months @ $191,008/mo * parking %)")
print()

# Soft Costs
print("SOFT COSTS")
print("-" * 80)
soft = costs["soft_costs"]
print(f"Our Total Soft Costs: ${soft['total']:,.0f}")
print(f"  - CM Fee: ${soft['cm_fee']:,.0f}")
print(f"  - Insurance: ${soft['insurance']:,.0f}")
print(f"  - Contingency: ${soft['contingency']:,.0f}")
print()

print("TechRidge Budget - Soft Costs (Parking portion):")
print("  - General Liability Insurance (1.10%): $134,994")
print("  - Contractor Fee (4.00%): $490,888")
print("  - CM/GC Contingency (2.25%): $276,125")
print("  - Design Completion Contingency (1.50%): $184,083")
print("  - Total Soft Costs: $1,086,090")
print()

# Grand Total
print("=" * 80)
print("GRAND TOTAL COMPARISON")
print("=" * 80)
print(f"Our Total: ${costs['total_cost']:,.0f}")
print(f"Our Cost/SF: ${costs['total_cost']/garage.total_gsf:.2f}")
print(f"Our Cost/Stall: ${costs['total_cost']/garage.total_stalls:,.0f}")
print()
print(f"TechRidge Budget Total (Parking): $12,272,200")
print(f"TechRidge Cost/SF: $96.38")
print(f"TechRidge Cost/Stall: $38,471")
print()

print("=" * 80)
print("KEY DISCREPANCIES TO INVESTIGATE")
print("=" * 80)

# Calculate discrepancies
gsf_diff = garage.total_gsf - 127325
stall_diff = garage.total_stalls - 319
cost_diff = costs['total_cost'] - 12272200

print(f"1. Total GSF: Our {garage.total_gsf:,.0f} SF vs Budget 127,325 SF (Δ {gsf_diff:+,.0f} SF)")
print(f"2. Total Stalls: Our {garage.total_stalls} stalls vs Budget 319 stalls (Δ {stall_diff:+d} stalls)")
print(f"3. Total Cost: Our ${costs['total_cost']:,.0f} vs Budget $12,272,200 (Δ ${cost_diff:+,.0f})")
print()

# Identify specific gaps
print("SPECIFIC LINE ITEMS TO AUDIT:")
print()
print("1. SITE WORK")
print("   - Budget includes: $403,382 for parking portion")
print("   - Our app: Site work not currently included")
print()
print("2. CONVEYING SYSTEMS")
print("   - Budget includes: $347,017 for parking portion (elevators, hoist)")
print("   - Our app: Elevator costs not currently included")
print()
print("3. EXTERIOR CLOSURE")
print("   - Budget includes: $829,840 for parking screen (10,120 SF @ $82)")
print("   - Our app: Exterior screen calculation needs verification")
print()
print("4. INTERIOR FINISHES")
print("   - Budget includes: $313,766 parking portion")
print("   - Our app: Finishes calculation needs verification")
print()
print("5. SPECIAL SYSTEMS")
print("   - Budget includes: $50,200 parking portion (fire extinguishers, pavement markings, etc.)")
print("   - Our app: Special systems not currently included")
print()
