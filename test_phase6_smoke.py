"""
Phase 6 Smoke Test - Quick validation that critical fixes work
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.garage import SplitLevelParkingGarage
from src.cost_engine import CostCalculator

# Load cost database
def load_cost_database():
    cost_db_path = Path(__file__).parent / 'data' / 'cost_database.json'
    with open(cost_db_path, 'r') as f:
        return json.load(f)

print("Phase 6 Smoke Test")
print("=" * 60)

# Test 1: Split-level system
print("\n1. Testing split-level system (210' x 2-bay)...")
try:
    garage_split = SplitLevelParkingGarage(
        num_bays=2,
        length=210,
        half_levels_above=4,
        half_levels_below=0
    )
    print(f"   ✓ Garage created: {garage_split.ramp_system.name}")

    cost_db = load_cost_database()
    calc = CostCalculator(cost_db)
    costs = calc.calculate_all_costs(garage_split)
    print(f"   ✓ Costs calculated: ${costs['total']:,.0f}")
except Exception as e:
    print(f"   ✗ FAILED: {e}")
    sys.exit(1)

# Test 2: Single-ramp system
print("\n2. Testing single-ramp system (300' x 3-bay)...")
try:
    garage_single = SplitLevelParkingGarage(
        num_bays=3,
        length=300,
        half_levels_above=4,
        half_levels_below=0
    )
    print(f"   ✓ Garage created: {garage_single.ramp_system.name}")

    costs = calc.calculate_all_costs(garage_single)
    print(f"   ✓ Costs calculated: ${costs['total']:,.0f}")
except Exception as e:
    print(f"   ✗ FAILED: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ SMOKE TEST PASSED - All critical fixes working!")
print("=" * 60)
