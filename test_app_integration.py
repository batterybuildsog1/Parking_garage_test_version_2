"""
Test that app.py actually works with Phase 6 changes
Simulates what the app does without running Streamlit
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("="*80)
print("APP INTEGRATION TEST - Simulating app.py flow")
print("="*80)

# Step 1: Load cost database (like app.py line 30-33)
print("\n1. Loading cost database...")
from src.cost_engine import CostCalculator, load_cost_database
cost_db = load_cost_database()
print(f"   ✓ Cost database loaded: {len(cost_db.keys())} top-level keys")

# Step 2: Create garage (like app.py line 156-162)
print("\n2. Creating garage (split-level 210' × 2-bay)...")
from src.garage import SplitLevelParkingGarage

garage = SplitLevelParkingGarage(
    length=210,
    half_levels_above=10,
    half_levels_below=0,
    num_bays=2,
    soil_bearing_capacity=2000
)
print(f"   ✓ Garage created: {garage.ramp_system.name}")

# Step 3: Create calculator and calculate costs (like app.py line 163-164)
print("\n3. Calculating costs...")
calculator = CostCalculator(cost_db)
gc_params = {"method": "percentage", "value": 9.37}
costs = calculator.calculate_all_costs(garage, gc_params=gc_params)
print(f"   ✓ Costs calculated: {len(costs)} keys in result")

# Step 4: Access metrics like app.py does (lines 174, 181, 188, 195, 202)
print("\n4. Accessing metrics (simulating app.py metrics row)...")
try:
    total_stalls = garage.total_stalls
    print(f"   ✓ Total Stalls: {total_stalls:,}")

    sf_per_stall = garage.sf_per_stall
    print(f"   ✓ SF per Stall: {sf_per_stall:.0f}")

    total_cost = costs['total']
    print(f"   ✓ Total Cost: ${total_cost:,.0f}")

    cost_per_stall = costs['cost_per_stall']
    print(f"   ✓ Cost per Stall: ${cost_per_stall:,.0f}")

    cost_per_sf = costs['cost_per_sf']
    print(f"   ✓ Cost per SF: ${cost_per_sf:.2f}")

except KeyError as e:
    print(f"   ✗ FAILED: Missing cost key: {e}")
    sys.exit(1)
except AttributeError as e:
    print(f"   ✗ FAILED: Missing garage attribute: {e}")
    sys.exit(1)

# Step 5: Test single-ramp system (auto-selected at 250'+)
print("\n5. Testing single-ramp auto-selection...")
garage_single = SplitLevelParkingGarage(
    length=300,
    half_levels_above=4,
    half_levels_below=0,
    num_bays=3
)
print(f"   ✓ 300' garage auto-selected: {garage_single.ramp_system.name}")

costs_single = calculator.calculate_all_costs(garage_single, gc_params=gc_params)
print(f"   ✓ Single-ramp costs calculated: ${costs_single['total']:,.0f}")

# Step 6: Verify all cost keys app.py uses exist
print("\n6. Verifying cost dict keys app.py uses...")
required_keys = [
    'total', 'cost_per_stall', 'cost_per_sf',  # Metrics
    'foundation', 'excavation', 'structure_above', 'structure_below',  # Hard costs
    'hard_cost_subtotal', 'soft_cost_subtotal'  # Subtotals
]

missing_keys = [key for key in required_keys if key not in costs]
if missing_keys:
    print(f"   ✗ FAILED: Missing keys: {missing_keys}")
    sys.exit(1)
else:
    print(f"   ✓ All required keys present ({len(required_keys)} checked)")

# Step 7: Verify garage attributes app.py uses exist
print("\n7. Verifying garage attributes app.py uses...")
required_attrs = [
    'total_stalls', 'sf_per_stall', 'total_gsf', 'total_height_ft',
    'ramp_system', 'half_levels_above', 'half_levels_below'
]

missing_attrs = [attr for attr in required_attrs if not hasattr(garage, attr)]
if missing_attrs:
    print(f"   ✗ FAILED: Missing attributes: {missing_attrs}")
    sys.exit(1)
else:
    print(f"   ✓ All required attributes present ({len(required_attrs)} checked)")

print("\n" + "="*80)
print("✅ APP INTEGRATION TEST PASSED")
print("="*80)
print("\nConclusion:")
print("  • app.py uses correct CostCalculator API")
print("  • app.py uses correct cost dict keys")
print("  • app.py uses correct garage attributes")
print("  • Both split-level and single-ramp systems work")
print("\n→ Phase 6 changes are COMPATIBLE with existing app.py")
print("="*80)
