"""
Test script to compare our model against TechRidge 1.2 SD Budget reference design

Reference Design (from PDF):
- Building: 126' wide × 210' long (2 bays)
- Parking levels: "5 Parking Levels" (P0.5, P1, P2, P3, P4, P5)
- Total parking GSF: 127,325 SF
- Total stalls: 319 stalls
- Total parking cost: $12,272,200

Our Model Configuration:
- 1 below grade half-level (P-0.5)
- 8 above grade half-levels (P0.5 through P4)
- This gives 9 total half-levels = 4.5 equivalent full floors
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.garage import SplitLevelParkingGarage
from src.cost_engine import CostCalculator, load_cost_database

def main():
    print("=" * 80)
    print("TECHRIDGE 1.2 REFERENCE DESIGN COMPARISON")
    print("=" * 80)

    # Reference values from PDF
    tr_parking_gsf = 127_325
    tr_total_stalls = 319
    tr_total_cost = 12_272_200
    tr_cost_per_sf = tr_total_cost / tr_parking_gsf
    tr_cost_per_stall = tr_total_cost / tr_total_stalls

    print("\nREFERENCE DESIGN (from TechRidge 1.2 SD Budget PDF):")
    print(f"  Total Parking GSF: {tr_parking_gsf:,} SF")
    print(f"  Total Stalls: {tr_total_stalls:,}")
    print(f"  Total Cost: ${tr_total_cost:,}")
    print(f"  Cost per SF: ${tr_cost_per_sf:.2f}/SF")
    print(f"  Cost per Stall: ${tr_cost_per_stall:,.0f}/stall")

    # Create our model with matching configuration
    # TR reference: 126' × 210' (2 bays), "5 parking levels"
    # Our split-level interpretation: 1 below + 8 above half-levels = 9 half-levels = 4.5 floors
    print("\nOUR MODEL CONFIGURATION:")
    print("  Building dimensions: 126' × 210' (2 bays)")
    print("  Half-levels below grade: 1 (P-0.5)")
    print("  Half-levels above grade: 8 (P0.5 through P4)")
    print("  Total half-levels: 9")
    print("  Equivalent full floors: 4.5")

    # Create garage
    garage = SplitLevelParkingGarage(
        length=210,  # feet
        half_levels_above=8,  # P0.5, P1, P1.5, P2, P2.5, P3, P3.5, P4
        half_levels_below=1   # P-0.5
    )

    print("\nOUR MODEL GEOMETRY RESULTS:")
    print(f"  Footprint: {garage.footprint_sf:,} SF")
    print(f"  Width: {garage.width:.1f}'")
    print(f"  Total parking GSF: {garage.total_gsf:,} SF")
    print(f"  Total stalls: {garage.total_stalls:,}")
    print(f"  Total levels: {garage.total_levels}")
    print(f"  Equivalent full floors: {garage.total_gsf / garage.footprint_sf:.2f}")

    # Calculate costs
    cost_db = load_cost_database()
    calculator = CostCalculator(cost_db)
    costs = calculator.calculate_all_costs(garage)

    print("\nOUR MODEL COST RESULTS:")
    print(f"  Total Cost: ${costs['total']:,.0f}")
    print(f"  Cost per SF: ${costs['cost_per_sf']:.2f}/SF")
    print(f"  Cost per Stall: ${costs['cost_per_stall']:,.0f}/stall")

    # Comparison
    print("\n" + "=" * 80)
    print("COMPARISON: Our Model vs. TechRidge Reference")
    print("=" * 80)

    gsf_variance = garage.total_gsf - tr_parking_gsf
    gsf_variance_pct = (gsf_variance / tr_parking_gsf) * 100

    stall_variance = garage.total_stalls - tr_total_stalls
    stall_variance_pct = (stall_variance / tr_total_stalls) * 100

    cost_variance = costs['total'] - tr_total_cost
    cost_variance_pct = (cost_variance / tr_total_cost) * 100

    print(f"\nGEOMETRY:")
    print(f"  Parking GSF:    {garage.total_gsf:>9,} vs {tr_parking_gsf:>9,} SF  ({gsf_variance:+7,.0f}, {gsf_variance_pct:+6.1f}%)")
    print(f"  Total Stalls:   {garage.total_stalls:>9,} vs {tr_total_stalls:>9,}     ({stall_variance:+7,.0f}, {stall_variance_pct:+6.1f}%)")

    print(f"\nCOST:")
    print(f"  Total Cost:     ${costs['total']:>9,.0f} vs ${tr_total_cost:>9,.0f}  (${cost_variance:+10,.0f}, {cost_variance_pct:+6.1f}%)")
    print(f"  Cost per SF:    ${costs['cost_per_sf']:>9.2f} vs ${tr_cost_per_sf:>9.2f}/SF")
    print(f"  Cost per Stall: ${costs['cost_per_stall']:>9,.0f} vs ${tr_cost_per_stall:>9,.0f}/stall")

    # Detailed cost breakdown comparison using mapping from cost engine
    print("\n" + "=" * 80)
    print("DETAILED COST BREAKDOWN COMPARISON (TR-MAPPED)")
    print("=" * 80)
    comparison = calculator.get_tr_comparison(garage)

    print(f"\n{'CATEGORY':<30} {'TR REFERENCE':>15} {'OUR MODEL':>15} {'VARIANCE':>15} {'%':>8}  STATUS")
    print("-" * 100)
    for row in comparison["categories"]:
        cat = row["category"]
        tr_val = row["tr_cost"]
        our_val = row["our_cost"]
        var = row["variance"]
        var_pct = row["variance_pct"]
        status = row["status"]
        print(f"{cat:<30} ${tr_val:>14,} ${our_val:>14,.0f} ${var:>+14,.0f} {var_pct:>+7.1f}%   {status}")

    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)

    if abs(gsf_variance_pct) > 5:
        print(f"\n⚠️ GEOMETRY DISCREPANCY: Our model GSF differs by {gsf_variance_pct:+.1f}%")
        print(f"   This suggests different level area calculation methodology.")

    if abs(stall_variance_pct) > 5:
        print(f"\n⚠️ STALL COUNT DISCREPANCY: Our model has {stall_variance_pct:+.1f}% different stalls")
        print(f"   This suggests different parking layout assumptions.")

    if abs(cost_variance_pct) > 10:
        print(f"\n⚠️ COST DISCREPANCY: Our model costs differ by {cost_variance_pct:+.1f}%")
        print(f"   Review individual cost categories for source of variance.")

    # Identify largest variances from mapped output
    print("\nLARGEST COST VARIANCES:")
    variances = sorted(
        [(r["category"], r["variance"], r["variance_pct"], r["tr_cost"], r["our_cost"])
         for r in comparison["categories"]
         if r["tr_cost"] > 0],
        key=lambda x: abs(x[2]),
        reverse=True
    )[:5]

    for i, (cat, var, var_pct, tr_val, our_val) in enumerate(variances, 1):
        print(f"{i}. {cat}: {var_pct:+.1f}% (${var:+,.0f})")
        print(f"   TR: ${tr_val:,} → Our: ${our_val:,.0f}")

    print("\n" + "=" * 80)
    print("END OF COMPARISON")
    print("=" * 80)

if __name__ == "__main__":
    main()
