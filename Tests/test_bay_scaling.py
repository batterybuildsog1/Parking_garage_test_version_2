"""
Test bay scaling: 2-bay vs 3-bay efficiency comparison
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.garage import SplitLevelParkingGarage

print("=" * 90)
print("BAY SCALING EFFICIENCY TEST")
print("=" * 90)

# Test configurations
configs = [
    {"name": "2-Bay", "bays": 2, "half_levels": 10, "length": 210},
    {"name": "3-Bay", "bays": 3, "half_levels": 10, "length": 210},
]

results = []

for config in configs:
    garage = SplitLevelParkingGarage(
        length=config["length"],
        half_levels_above=config["half_levels"],
        half_levels_below=0,
        num_bays=config["bays"]
    )

    results.append({
        "name": config["name"],
        "bays": config["bays"],
        "width": garage.width,
        "footprint_sf": garage.footprint_sf,
        "total_gsf": garage.total_gsf,
        "total_stalls": garage.total_stalls,
        "sf_per_stall": garage.sf_per_stall,
        "stalls_per_level": garage.total_stalls / garage.total_levels
    })

print(f"\n{'Config':<10} {'Bays':<6} {'Width':<8} {'Footprint':<15} {'Total GSF':<15} {'Stalls':<8} {'Stalls/Level':<14} {'SF/Stall':<12}")
print("-" * 90)

for r in results:
    print(f"{r['name']:<10} {r['bays']:<6} {r['width']:.0f}'   {r['footprint_sf']:>12,.0f} SF {r['total_gsf']:>12,.0f} SF {r['total_stalls']:>6} {r['stalls_per_level']:>10.1f}    {r['sf_per_stall']:>8.1f} SF")

print("-" * 90)

# Calculate scaling metrics
bay2 = results[0]
bay3 = results[1]

width_increase = (bay3["width"] - bay2["width"]) / bay2["width"] * 100
footprint_increase = (bay3["footprint_sf"] - bay2["footprint_sf"]) / bay2["footprint_sf"] * 100
stalls_increase = (bay3["total_stalls"] - bay2["total_stalls"]) / bay2["total_stalls"] * 100
sf_per_stall_change = ((bay3["sf_per_stall"] - bay2["sf_per_stall"]) / bay2["sf_per_stall"]) * 100

print(f"\n{'SCALING ANALYSIS':^90}")
print("-" * 90)
print(f"Width increase: {width_increase:+.1f}%")
print(f"Footprint increase: {footprint_increase:+.1f}%")
print(f"Stalls increase: {stalls_increase:+.1f}%")
print(f"SF/stall change: {sf_per_stall_change:+.1f}%")
print(f"\nEfficiency ratio (stalls/footprint): {stalls_increase / footprint_increase:.3f}")

print(f"\n{'TARGET VERIFICATION':^90}")
print("-" * 90)
print(f"User expectation: ±5-10% efficiency change")
print(f"Actual SF/stall change: {sf_per_stall_change:+.1f}%")

if abs(sf_per_stall_change) <= 10:
    print("✓ Within ±10% target!")
elif abs(sf_per_stall_change) <= 15:
    print("~ Close to target (within ±15%)")
else:
    print("✗ Outside target range")

print("=" * 90)
