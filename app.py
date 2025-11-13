"""
TechRidge Split-Level Parking Garage Analyzer
Interactive parametric cost and geometry analysis tool
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import matplotlib.pyplot as plt
import io
from typing import Any, Dict
from src.garage import ParkingLayout, compute_width_ft
from src.cost_engine import load_cost_database
from src.pipeline import run_scenario
from src.reporting import (
    build_detailed_takeoffs as reporting_build_detailed_takeoffs,
    build_tr_comparison as reporting_build_tr_comparison,
    build_tr_aligned_breakdown as reporting_build_tr_aligned_breakdown,
)


build_detailed_takeoffs = reporting_build_detailed_takeoffs
build_tr_comparison = reporting_build_tr_comparison

from src.visualization import create_3d_parking_garage
from visualize_parking_layout import create_overview_diagram_figure, create_per_level_diagram_figure

# Page config
st.set_page_config(
    page_title="TechRidge Parking Garage Analyzer",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title
st.title("🏗️ TechRidge Split-Level Parking Garage Analyzer")
st.markdown("**Parametric cost and geometry analysis for podium-style parking structures**")

# Load cost database
@st.cache_data
def load_costs():
    return load_cost_database()

cost_db = load_costs()

# Sidebar - Input Parameters
st.sidebar.header("Design Parameters")

st.sidebar.markdown("### Dimensions")

num_bays = st.sidebar.slider(
    "Number of Bays",
    min_value=2,
    max_value=7,
    value=2,
    step=1,
    help="Number of ramp bays (2 bays = 126', 3 bays = 190', etc.)"
)

# Calculate and display width (single source of truth from geometry)
calculated_width = compute_width_ft(num_bays)
st.sidebar.info(f"**Width: {calculated_width:.0f}'**")

length = st.sidebar.slider(
    "Length (feet)",
    min_value=150,
    max_value=360,
    value=210,
    step=31,
    help="Building length in feet (31' increments recommended for structural grid)"
)

st.sidebar.markdown("### Levels")

half_levels_above = st.sidebar.slider(
    "Levels Above Grade",
    min_value=2,
    max_value=12,
    value=10,
    step=1,
    help="""Number of parking levels above grade.

• **Split-Level system:** Half-levels (e.g., 10 = P1, P1.5, P2, P2.5... P5.5)
• **Single-Ramp system:** Full floors (e.g., 10 = P1, P2, P3... P10)

System auto-selected based on building length (250' threshold)."""
)

half_levels_below = st.sidebar.slider(
    "Levels Below Grade",
    min_value=0,
    max_value=6,
    value=0,
    step=1,
    help="""Number of parking levels below grade.

• **Split-Level system:** Half-levels (e.g., 4 = B-0.5, B-1, B-1.5, B-2)
• **Single-Ramp system:** Full floors (e.g., 4 = B-1, B-2, B-3, B-4)"""
)

# Calculate display information
# Detect ramp system early to get correct level_height
from src.geometry.design_modes import RampSystemType, get_ramp_config
detected_system = RampSystemType.determine_optimal(length, num_bays)
ramp_config = get_ramp_config(detected_system)
level_height = ramp_config['level_height']

# Total levels = all levels (interpretation depends on system)
total_levels_display = half_levels_below + half_levels_above
if detected_system == RampSystemType.SPLIT_LEVEL_DOUBLE:
    deepest = f"B-{half_levels_below / 2:.1f}" if half_levels_below else "P0.5"
    highest = f"P{half_levels_above / 2:.1f}"
else:
    deepest = f"B-{int(half_levels_below)}" if half_levels_below else "P1"
    highest = f"P{int(half_levels_above)}"
vertical_span_ft = total_levels_display * level_height

st.sidebar.info(
    f"**{total_levels_display} parking levels total**\n\n"
    f"Range: **{deepest}** (entry) to **{highest}**\n\n"
    f"Height: {vertical_span_ft:.1f} ft ({half_levels_above * level_height:.1f}' above, {half_levels_below * level_height:.1f}' below)"
)

# === RAMP SYSTEM INDICATOR ===
st.sidebar.markdown("### Ramp System")

if detected_system == RampSystemType.SPLIT_LEVEL_DOUBLE:
    system_label = "Split-Level (Double Ramp)"
    system_icon = "🔀"
    system_desc = "Two interleaved helical ramps\nHalf-levels at 5.3' spacing"
else:
    system_label = "Single-Ramp (Full Floors)"
    system_icon = "⬆️"
    system_desc = "One ramp bay with parking on slope\nFull floors at 9.0' spacing"

st.sidebar.info(
    f"{system_icon} **Active System: {system_label}**\n\n"
    f"{system_desc}\n\n"
    f"Auto-selected (length: {length}', threshold: 250')"
)

st.sidebar.markdown("### General Conditions")
gc_method = st.sidebar.radio(
    "Calculation Method",
    options=["Percentage of Hard Costs", "Monthly Rate"],
    index=0,
    help="Choose how to calculate General Conditions costs"
)

if gc_method == "Percentage of Hard Costs":
    gc_percentage = st.sidebar.slider(
        "GC Percentage (%)",
        min_value=5.0,
        max_value=20.0,
        value=9.37,
        step=0.1,
        help="General Conditions as % of hard costs (baseline: 9.37% from TechRidge budget)"
    )
    gc_params = {"method": "percentage", "value": gc_percentage}
else:
    estimated_duration_months = st.sidebar.number_input(
        "Estimated Duration (months)",
        min_value=3.0,
        max_value=24.0,
        value=5.0,
        step=0.5,
        help="Construction duration estimate"
    )
    gc_params = {"method": "monthly_rate", "value": estimated_duration_months}

st.sidebar.markdown("### Soil Parameters")

soil_bearing_capacity = st.sidebar.number_input(
    "Allowable Bearing Capacity (PSF)",
    min_value=1000,
    max_value=15000,
    value=3500,
    step=500,
    help="From geotechnical report. Typical values:\n• 2000-4000 PSF: Clay/Silt\n• 4000-8000 PSF: Sand/Gravel\n• 8000+ PSF: Rock/Engineered Fill\n\n⚠️ Footing costs shown use gravity loads only (1.2D + 1.6L). Excludes wind/seismic/uplift effects."
)

with st.sidebar.expander("Additional Soil Properties (Advanced)"):
    soil_unit_weight = st.number_input(
        "Soil Unit Weight (PCF)",
        min_value=90,
        max_value=140,
        value=120,
        step=5,
        help="Typical values:\n• 100-120 PCF: Loose sand\n• 120-130 PCF: Dense sand\n• 90-110 PCF: Clay"
    )

    soil_friction_angle = st.number_input(
        "Soil Friction Angle (degrees)",
        min_value=20,
        max_value=45,
        value=30,
        step=5,
        help="Typical values:\n• 28-35°: Sand\n• 20-25°: Silt\n• 0-15°: Clay"
    )

st.sidebar.markdown("### Load Assumptions")

reduce_live_load = st.sidebar.checkbox(
    "Reduce Live Load with Level Count (ASCE 7/IBC)",
    value=True,
    help="Apply a standard live load reduction for columns supporting multiple levels. You can turn this off to be conservative."
)

dead_load_psf = st.sidebar.number_input(
    "Dead Load (PSF)",
    min_value=50.0,
    max_value=200.0,
    value=115.0,
    step=5.0,
    help="Dead load per square foot:\n• 100 PSF: Slab self-weight (typical 8\" PT slab)\n• 15 PSF: Superimposed dead load (MEP, finishes)\n• Default 115 PSF total"
)

live_load_psf = st.sidebar.number_input(
    "Live Load (PSF)",
    min_value=40.0,
    max_value=150.0,
    value=50.0,
    step=5.0,
    help="Live load per square foot:\n• 50 PSF: Parking garage (IBC 2021 Table 1607.1)\n• 100 PSF: Stairs (IBC code requirement)\n• 125 PSF: Storage areas (IBC code requirement)"
)

# Advanced settings
with st.sidebar.expander("Advanced"):
    ramp_termination_length = st.number_input(
        "Ramp Termination Length (ft)",
        min_value=20,
        max_value=80,
        value=40,
        step=1,
        help="Flat zone at ramp termination (default 40')."
    )

# Calculate garage
try:
    scenario_inputs = {
        "length": length,
        "half_levels_above": half_levels_above,
        "half_levels_below": half_levels_below,
        "num_bays": num_bays,
        "ramp_system": detected_system,
        "ramp_termination_length": ramp_termination_length,
        "soil_bearing_capacity": soil_bearing_capacity,
        "allow_ll_reduction": reduce_live_load,
        "dead_load_psf": dead_load_psf,
        "live_load_psf": live_load_psf,
    }
    result = run_scenario(
        inputs=scenario_inputs,
        cost_database=cost_db,
        gc_params=gc_params
    )
    garage = result.garage
    diagnostics = result.diagnostics if hasattr(result, "diagnostics") else {}
    geom_diag = diagnostics.get("geometry", {})
    costs = result.cost_summary
    cost_items_df = result.table("cost_items")
    quantities_df = result.table("quantities")
    elements_df = result.table("elements")
    detailed_takeoffs = build_detailed_takeoffs(cost_items_df, garage)
    tr_comparison_data = build_tr_comparison(costs, cost_db, garage)
    summary = garage.get_summary()

    # === METRICS ROW ===
    st.markdown("---")
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)

    with col1:
        st.metric(
            "Total Stalls",
            f"{garage.total_stalls:,}",
            help="Total parking stall count"
        )

    with col2:
        st.metric(
            "SF per Stall",
            f"{garage.sf_per_stall:.0f}",
            help="Gross square feet per parking stall (industry standard efficiency metric)"
        )

    with col3:
        st.metric(
            "Total Cost",
            f"${costs['total']:,.0f}",
            help="Total construction cost"
        )

    with col4:
        st.metric(
            "Cost per Stall",
            f"${costs['cost_per_stall']:,.0f}",
            help="Total cost divided by stall count"
        )

    with col5:
        st.metric(
            "Cost per SF",
            f"${costs['cost_per_sf']:,.0f}",
            help="Total cost per SF of total GSF (sum of discrete level areas)"
        )

    with col6:
        system_short = "Split-Level" if garage.ramp_system == RampSystemType.SPLIT_LEVEL_DOUBLE else "Single-Ramp"
        st.metric(
            "Ramp System",
            system_short,
            help="Auto-selected based on building length (250' threshold)"
        )

    with col7:
        st.metric(
            "Floor-to-Floor",
            f"{garage.floor_to_floor:.1f}'",
            help="Vertical spacing between parking levels"
        )

    # === CACHING FUNCTIONS FOR 2D DIAGRAMS ===
    @st.cache_data
    def calculate_layout_optimization(width, length, num_bays):
        """Cache expensive optimization calculation

        Optimization creates 18 ParkingLayout instances to test incremental
        length additions. This is the most expensive operation.
        """
        layout = ParkingLayout(width, length, num_bays)
        layout.apply_core_blockages()
        return layout.calculate_length_optimization()

    @st.cache_data(max_entries=50)
    def generate_overview_diagram_bytes(_garage, width, length, num_bays, _opt_result):
        """Generate and cache overview diagram as PNG bytes

        max_entries=50 allows caching ~50 different configurations (~15-25 MB)
        within the 100MB memory budget. Balance between hit rate and memory.

        Args with _ prefix are not hashed for cache key (complex objects).
        Args without _ are hashed (primitives).

        Returns PNG bytes for display with st.image()
        """
        layout = ParkingLayout(width, length, num_bays, turn_zone_depth=_garage.TURN_ZONE_DEPTH)
        layout.apply_core_blockages()
        fig = create_overview_diagram_figure(_garage, layout, _opt_result)

        # Convert to bytes for reliable caching (matplotlib figures don't pickle)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)  # Clean up immediately
        buf.seek(0)
        return buf.getvalue()

    @st.cache_data(max_entries=200)
    def generate_level_diagram_bytes(_garage, width, length, num_bays, level_name, _opt_result):
        """Generate and cache per-level diagram as PNG bytes

        max_entries=200 allows caching many level views (~60-100 MB) within budget.
        Users frequently browse levels, so higher limit than overview.

        Returns PNG bytes for display with st.image()
        """
        layout = ParkingLayout(width, length, num_bays, turn_zone_depth=_garage.TURN_ZONE_DEPTH)
        layout.apply_core_blockages()
        fig = create_per_level_diagram_figure(_garage, layout, level_name, _opt_result)

        # Convert to bytes for reliable caching
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)  # Clean up immediately
        buf.seek(0)
        return buf.getvalue()

    # === TABS ===
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📊 Cost Breakdown", "📐 Geometry", "🏗️ 3D Model", "📋 2D Plans", "📈 Comparison", "📋 Detailed Quantities", "🔍 TR Audit"])

    with tab1:
        st.subheader("Cost Breakdown")

        # Hard costs
        st.markdown("### Hard Costs")
        hard_costs_df = pd.DataFrame([
            {"Category": "Foundation", "Cost": costs['foundation'], "% of Total": costs['foundation']/costs['total']*100},
            {"Category": "Excavation & Site Prep", "Cost": costs['excavation'], "% of Total": costs['excavation']/costs['total']*100},
            {"Category": "Structure (Above Grade)", "Cost": costs['structure_above'], "% of Total": costs['structure_above']/costs['total']*100},
            {"Category": "Structure (Below Grade)", "Cost": costs['structure_below'], "% of Total": costs['structure_below']/costs['total']*100},
            {"Category": "Concrete Pumping", "Cost": costs['concrete_pumping'], "% of Total": costs['concrete_pumping']/costs['total']*100},
            {"Category": "Rebar (All Components)", "Cost": costs['rebar'], "% of Total": costs['rebar']/costs['total']*100},
            {"Category": "Post-Tensioning", "Cost": costs['post_tensioning'], "% of Total": costs['post_tensioning']/costs['total']*100},
            {"Category": "Center Elements (Beams, Columns, Curbs)", "Cost": costs['core_walls'], "% of Total": costs['core_walls']/costs['total']*100},
            {"Category": "Ramp System", "Cost": costs['ramp_system'], "% of Total": costs['ramp_system']/costs['total']*100},
            {"Category": "Elevators", "Cost": costs['elevators'], "% of Total": costs['elevators']/costs['total']*100},
            {"Category": "Stairs", "Cost": costs['stairs'], "% of Total": costs['stairs']/costs['total']*100},
            {"Category": "MEP Systems", "Cost": costs['mep'], "% of Total": costs['mep']/costs['total']*100},
            {"Category": "Exterior Walls/Screen", "Cost": costs['exterior'], "% of Total": costs['exterior']/costs['total']*100},
            {"Category": "Site Finishes", "Cost": costs['site_finishes'], "% of Total": costs['site_finishes']/costs['total']*100},
        ])

        st.dataframe(
            hard_costs_df.style.format({"Cost": "${:,.0f}", "% of Total": "{:.1f}%"}),
            use_container_width=True
        )

        st.metric("Hard Cost Subtotal", f"${costs['hard_cost_subtotal']:,.0f}")

        # Soft costs
        st.markdown("### Soft Costs")
        soft_costs_df = pd.DataFrame([
            {"Category": "General Conditions", "Cost": costs['general_conditions'], "% of Hard": costs['general_conditions']/costs['hard_cost_subtotal']*100},
            {"Category": "CM Fee", "Cost": costs['cm_fee'], "% of Hard": costs['cm_fee']/costs['hard_cost_subtotal']*100},
            {"Category": "Insurance", "Cost": costs['insurance'], "% of Hard": costs['insurance']/costs['hard_cost_subtotal']*100},
            {"Category": "Contingency", "Cost": costs['contingency'], "% of Hard": costs['contingency']/costs['hard_cost_subtotal']*100},
        ])

        st.dataframe(
            soft_costs_df.style.format({"Cost": "${:,.0f}", "% of Hard": "{:.1f}%"}),
            use_container_width=True
        )

        # Pie chart
        st.markdown("### Cost Distribution")
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Foundation', 'Excavation', 'Structure Above', 'Structure Below',
                   'Ramp', 'MEP', 'Exterior', 'Site', 'Soft Costs'],
            values=[
                costs['foundation'], costs['excavation'], costs['structure_above'],
                costs['structure_below'], costs['ramp_system'], costs['mep'],
                costs['exterior'], costs['site_finishes'], costs['soft_cost_subtotal']
            ],
            hole=0.3
        )])
        fig_pie.update_layout(title="Cost Distribution by Category")
        st.plotly_chart(fig_pie, use_container_width=True)

    with tab2:
        st.subheader("Geometry Summary")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Dimensions")
            system_name = "Split-Level (Double Ramp)" if garage.ramp_system.name == "SPLIT_LEVEL_DOUBLE" else "Single-Ramp (Full Floors)"
            dims_df = pd.DataFrame([
                {"Property": "Ramp System", "Value": system_name},
                {"Property": "Floor-to-Floor Height", "Value": f"{garage.floor_to_floor:.3f} ft"},
                {"Property": "Number of Bays", "Value": f"{summary['dimensions']['num_bays']}"},
                {"Property": "Number of Center Lines", "Value": f"{summary['dimensions'].get('num_center_lines', summary['dimensions'].get('num_core_walls', 0))}"},
                {"Property": "Width", "Value": f"{summary['dimensions']['width_ft']:,} ft"},
                {"Property": "Length", "Value": f"{summary['dimensions']['length_ft']:,} ft"},
                {"Property": "Footprint", "Value": f"{summary['dimensions']['footprint_sf']:,} SF"},
                {"Property": "Perimeter", "Value": f"{summary['dimensions']['perimeter_lf']:,} LF"},
                {"Property": "Total Height", "Value": f"{summary['dimensions']['total_height_ft']:,} ft"},
                {"Property": "Depth Below Grade", "Value": f"{summary['dimensions']['depth_below_grade_ft']:,} ft"},
            ])
            st.dataframe(dims_df, use_container_width=True, hide_index=True)

            st.markdown("### Parking")
            parking_df = pd.DataFrame([
                {"Property": "Total Stalls", "Value": f"{summary['parking']['total_stalls']:,}"},
                {"Property": "SF per Stall", "Value": f"{summary['parking']['sf_per_stall']:.1f} SF"},
                {"Property": "Avg Stalls/Level", "Value": f"{summary['parking']['avg_stalls_per_level']:.1f}"},
                {"Property": "Discrete Levels", "Value": f"{summary['levels']['num_discrete_levels']}"},
                {"Property": "Level Range", "Value": f"{summary['levels']['deepest_level']} to {summary['levels']['highest_level']}"},
            ])
            st.dataframe(parking_df, use_container_width=True, hide_index=True)

        with col2:
            st.markdown("### Structure")
            struct_df = pd.DataFrame([
                {"Property": "Number of Columns", "Value": f"{summary['structure']['num_columns']:,}"},
                {"Property": "Number of Stair Flights", "Value": f"{summary['structure']['num_stair_flights']:,}"},
                {"Property": "Number of Elevator Stops", "Value": f"{summary['structure']['num_elevator_stops']:,}"},
                {"Property": "Total Slab Area", "Value": f"{summary['structure']['total_slab_sf']:,} SF"},
                {"Property": "Core Walls", "Value": f"{summary['structure'].get('core_wall_area_sf', 0):,.0f} SF"},
                {"Property": "Total Concrete", "Value": f"{summary['structure']['total_concrete_cy']:,} CY"},
                {"Property": "Rebar", "Value": f"{summary['structure']['rebar_lbs']:,} LBS"},
                {"Property": "Post-Tension Cables", "Value": f"{summary['structure']['post_tension_lbs']:,} LBS"},
                {"Property": "Exterior Wall Area", "Value": f"{summary['structure']['exterior_wall_sf']:,} SF"},
            ])
            st.dataframe(struct_df, use_container_width=True, hide_index=True)

            if summary['excavation']['excavation_cy'] > 0:
                st.markdown("### Excavation")
                ex_df = pd.DataFrame([
                    {"Property": "Excavation Volume", "Value": f"{summary['excavation']['excavation_cy']:,} CY"},
                    {"Property": "Export/Haul-Off", "Value": f"{summary['excavation']['export_cy']:,} CY"},
                    {"Property": "Structural Fill", "Value": f"{summary['excavation']['structural_fill_cy']:,} CY"},
                    {"Property": "Retaining Wall Area", "Value": f"{summary['excavation']['retaining_wall_sf']:,} SF"},
                ])
                st.dataframe(ex_df, use_container_width=True, hide_index=True)

        # === STRUCTURAL CHECKS SUMMARY ===
        st.markdown("### Structural Checks")
        col1, col2, col3 = st.columns(3)
        studs = getattr(garage, 'stud_rail_required_joints', 0)
        lvl_val = getattr(garage, 'per_level_area_validation', [])
        if lvl_val:
            variances = [abs(v.get('variance_pct', 0.0)) for v in lvl_val]
            max_var = max(variances) if variances else 0.0
            within2 = sum(1 for v in variances if v < 2.0)
            total_lvls = len(variances)
        else:
            max_var = 0.0
            within2 = 0
            total_lvls = 0
        with col1:
            st.metric("Stud Rail Joints Required", f"{int(studs)}", help="Count of slab-column joints requiring stud rails (punching utilization > 1.0).")
        with col2:
            st.metric("Max Level Area Variance", f"{max_var:.1f}%", help="Max |(Sum column areas − GSF)/GSF| across levels.")
        with col3:
            st.metric("Levels within 2%", f"{within2}/{total_lvls}", help="Per-level area conservation check within ±2%.")

        # === DIAGNOSTICS (MVP) ===
        with st.expander("Diagnostics (MVP)"):
            # Columns/Floors summary
            c_cols, c_floors, c_rebar = st.columns(3)

            with c_cols:
                cols_info = geom_diag.get("components", {}).get("columns", {})
                st.markdown("**Columns**")
                st.metric("Total Columns", f"{cols_info.get('total_count', 0)}")
                per_level = cols_info.get("per_level", [])
                if per_level:
                    st.dataframe(pd.DataFrame(per_level), use_container_width=True, hide_index=True)

            with c_floors:
                floors_info = geom_diag.get("components", {}).get("floors", {})
                st.markdown("**Floors**")
                st.metric("Total Levels", f"{floors_info.get('total_levels', 0)}")
                lvl_rows = floors_info.get("levels", [])
                if lvl_rows:
                    st.dataframe(pd.DataFrame(lvl_rows), use_container_width=True, hide_index=True)

            with c_rebar:
                rebar = geom_diag.get("components", {}).get("rebar", {})
                st.markdown("**Rebar (Slabs + Footings)**")
                st.text(f"SOG SF: {rebar.get('sog_sf', 0):,.0f} @ {rebar.get('sog_rebar_rate_lbs_per_sf', 0):.2f} lb/SF")
                st.text(f"Suspended SF: {rebar.get('suspended_slab_sf', 0):,.0f} @ {rebar.get('suspended_rebar_rate_lbs_per_sf', 0):.2f} lb/SF")
                st.text(f"SOG Rebar: {rebar.get('sog_rebar_lbs', 0):,.0f} lb")
                st.text(f"Suspended Rebar: {rebar.get('suspended_slab_rebar_lbs', 0):,.0f} lb")
                st.text(f"Footing Rebar: {rebar.get('total_footing_rebar_lbs', 0):,.0f} lb")
                st.metric("Total Rebar (All)", f"{rebar.get('total_rebar_lbs_all', 0):,.0f} lb")

            # Retaining walls + cores
            c_ret, c_cores = st.columns(2)
            with c_ret:
                walls = geom_diag.get("components", {}).get("retaining_walls", {})
                st.markdown("**Retaining Walls**")
                st.text(f"Perimeter: {walls.get('perimeter_lf', 0):,.0f} LF")
                st.text(f"Total Area: {walls.get('total_area_sf', 0):,.0f} SF")
                st.text(f"Tracked Area: {walls.get('tracked_total_area_sf', 0):,.0f} SF")
                per_lvl = walls.get("area_sf_by_level", [])
                if per_lvl:
                    st.dataframe(pd.DataFrame(per_lvl), use_container_width=True, hide_index=True)
            with c_cores:
                cores = geom_diag.get("components", {}).get("cores", {})
                st.markdown("**Cores**")
                st.text(f"Stairs: {cores.get('num_stairs', 0)}")
                st.text(f"Stair Flights: {cores.get('num_stair_flights', 0)}")
                st.text(f"Elevator Stops: {cores.get('num_elevator_stops', 0)}")

            # Imposed load reconciliation
            st.markdown("**Imposed Load Reconciliation**")
            il = geom_diag.get("imposed_load_check", {})
            modeled = il.get("modeled", {})
            expected = il.get("expected", {})
            deltas = il.get("deltas_pct", {})
            tol = il.get("tolerance_pct", 3.0)
            passes = il.get("passes", {})
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.metric("DL Modeled", f"{modeled.get('dl_lb_total', 0):,.0f} lb")
                st.metric("DL Expected", f"{expected.get('dl_lb_total', 0):,.0f} lb")
                st.metric("DL Δ%", f"{deltas.get('dl', 0.0):+.1f}%")
            with col_b:
                st.metric("LL Modeled", f"{modeled.get('ll_lb_total', 0):,.0f} lb")
                st.metric("LL Expected", f"{expected.get('ll_lb_total', 0):,.0f} lb")
                st.metric("LL Δ%", f"{deltas.get('ll', 0.0):+.1f}%")
            with col_c:
                st.metric("Total Modeled", f"{modeled.get('total_lb', 0):,.0f} lb")
                st.metric("Total Expected", f"{expected.get('total_lb', 0):,.0f} lb")
                st.metric("Total Δ%", f"{deltas.get('total', 0.0):+.1f}%")
            with col_d:
                badge = "✅ PASS" if passes.get("all") else "❌ FAIL"
                st.metric("Tolerance", f"±{tol:.1f}%", badge)

        # === COLUMNS (Per-element detail) ===
        st.markdown("### Columns (Per-Element Details)")
        columns = getattr(garage, 'columns', [])
        if not columns:
            st.info("No columns generated for this configuration.")
        else:
            # Build overview table
            over_rows = []
            for i, c in enumerate(columns):
                area_sf = (c['width_in'] / 12.0) * (c['depth_in'] / 12.0)
                vol_cy = (area_sf * garage.total_height_ft) / 27.0
                over_rows.append({
                    "Index": i + 1,
                    "X (ft)": round(c['x'], 2),
                    "Y (ft)": round(c['y'], 2),
                    "Type": c.get('y_line_type', ''),
                    "Size (in)": f"{int(c['width_in'])}x{int(c['depth_in'])}",
                    "Concrete (CY)": round(vol_cy, 3)
                })
            st.dataframe(pd.DataFrame(over_rows), use_container_width=True, hide_index=True)

            # Select a column for details
            sel_idx = st.selectbox("Select Column", options=list(range(1, len(columns) + 1)), index=0)
            c = columns[sel_idx - 1]
            area_sf = (c['width_in'] / 12.0) * (c['depth_in'] / 12.0)
            col_vol_cy = (area_sf * garage.total_height_ft) / 27.0
            col_self_weight = area_sf * garage.total_height_ft * 150.0  # lbs

            # Tributary area (aligned with calculator defaults)
            spacing_ft = getattr(garage, 'column_spacing_ft', 31.0)
            ytype = c.get('y_line_type')
            if ytype == 'ramp_center':
                trib_sf = spacing_ft * spacing_ft
            elif ytype == 'perimeter':
                trib_sf = spacing_ft * (spacing_ft / 2.0)
            else:
                trib_sf = spacing_ft * spacing_ft

            # Floors supported (equivalent full floors)
            eq_floors = garage.total_gsf / garage.footprint_sf if garage.footprint_sf > 0 else 0.0
            ll_psf_eff = live_load_psf
            if reduce_live_load and eq_floors >= 2.0:
                ll_psf_eff = 0.8 * live_load_psf
            dl_total = trib_sf * dead_load_psf * eq_floors
            ll_total = trib_sf * ll_psf_eff * eq_floors
            service_load = dl_total + ll_total + col_self_weight
            factored_load = garage.load_factor_dl * (dl_total + col_self_weight) + garage.load_factor_ll * ll_total

            # Find nearest footing (by plan distance)
            nearest = None
            nearest_d = None
            for f_list in getattr(garage, 'spread_footings_by_type', {}).values():
                for f in f_list:
                    fx, fy = f.get('x'), f.get('y')
                    if fx is None or fy is None:
                        continue
                    d = ((fx - c['x']) ** 2 + (fy - c['y']) ** 2) ** 0.5
                    if nearest is None or d < nearest_d:
                        nearest = f
                        nearest_d = d

            # Cost list (column + footing, using unit costs)
            uc = cost_db.get("unit_costs", {})
            cs = cost_db.get("component_specific_costs", {})
            col_unit_cy = uc.get("structure", {}).get("columns_18x24_cy", 0.0)
            col_conc_cost = col_vol_cy * col_unit_cy
            rebar_per_cy = cs.get("rebar_columns_lbs_per_cy_concrete", 0.0)
            rebar_lb_rate = cs.get("rebar_cost_per_lb", 0.0)
            col_rebar_lbs = col_vol_cy * rebar_per_cy
            col_rebar_cost = col_rebar_lbs * rebar_lb_rate

            footing_items = []
            if nearest:
                f_conc_cy = nearest.get("concrete_cy", 0.0)
                f_rebar_lbs = nearest.get("rebar_lbs", 0.0)
                f_exc_cy = nearest.get("excavation_cy", 0.0)
                f_conc_cost = f_conc_cy * uc.get("foundation", {}).get("footings_spot_cy", 0.0)
                f_rebar_cost = f_rebar_lbs * rebar_lb_rate
                f_exc_cost = f_exc_cy * uc.get("foundation", {}).get("excavation_footings_cy", 0.0)
                footing_items = [
                    {"Component": "Footing Concrete", "Quantity": f_conc_cy, "Unit": "CY", "Cost": f_conc_cost},
                    {"Component": "Footing Rebar", "Quantity": f_rebar_lbs, "Unit": "LB", "Cost": f_rebar_cost},
                    {"Component": "Footing Excavation", "Quantity": f_exc_cy, "Unit": "CY", "Cost": f_exc_cost},
                ]

            cost_rows = [
                {"Component": "Column Concrete", "Quantity": round(col_vol_cy, 3), "Unit": "CY", "Cost": col_conc_cost},
                {"Component": "Column Rebar", "Quantity": round(col_rebar_lbs, 1), "Unit": "LB", "Cost": col_rebar_cost},
                {"Component": "Stud Rails (Slab)", "Quantity": 0, "Unit": "LB", "Cost": 0},
            ] + footing_items
            st.markdown("#### Cost Attribution (Per Selected Column)")
            st.dataframe(pd.DataFrame(cost_rows).style.format({"Quantity": "{:,.2f}", "Cost": "${:,.2f}"}), use_container_width=True, hide_index=True)

            # Loads table
            loads_rows = [
                {"Metric": "Tributary Area", "Value": trib_sf, "Unit": "SF"},
                {"Metric": "Equivalent Floors", "Value": eq_floors, "Unit": "-"},
                {"Metric": "DL (slab)", "Value": dl_total, "Unit": "LB"},
                {"Metric": "LL (slab, reduced)", "Value": ll_total, "Unit": "LB"},
                {"Metric": "Column Self-Weight", "Value": col_self_weight, "Unit": "LB"},
                {"Metric": "Service Load", "Value": service_load, "Unit": "LB"},
                {"Metric": "Factored Load", "Value": factored_load, "Unit": "LB"},
            ]
            st.markdown("#### Loads (Approximate)")
            st.dataframe(pd.DataFrame(loads_rows).style.format({"Value": "{:,.0f}"}), use_container_width=True, hide_index=True)

            # Per-level areas & loads
            per_col_levels = getattr(garage, 'per_level_column_data', [])
            if per_col_levels and len(per_col_levels) >= sel_idx:
                st.markdown("#### Per-level Areas & Loads")
                lvl_entries = per_col_levels[sel_idx - 1]
                lvl_df = pd.DataFrame([{
                    "Level": f"{e.get('level_index')}:{e.get('level_name','')}",
                    "Area (SF)": e.get('area_sf', 0.0),
                    "DL (lb)": e.get('dl_lb', 0.0),
                    "LL (lb)": e.get('ll_lb', 0.0),
                    "Service (lb)": e.get('service_lb', 0.0),
                    "Factored (lb)": e.get('factored_lb', 0.0),
                    "Punch Util": e.get('punch_utilization', None),
                    "Stud Rails": "Req" if e.get('stud_rails_required') else "",
                    "Suspended": "Yes" if e.get('slab_type') == 'suspended' else "No"
                } for e in lvl_entries])
                st.dataframe(lvl_df.style.format({
                    "Area (SF)": "{:,.1f}",
                    "DL (lb)": "{:,.0f}",
                    "LL (lb)": "{:,.0f}",
                    "Service (lb)": "{:,.0f}",
                    "Factored (lb)": "{:,.0f}",
                    "Punch Util": "{:.2f}"
                }), use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("3D Model")

        # Warning for single-ramp systems
        if garage.ramp_system == RampSystemType.SINGLE_RAMP_FULL:
            st.warning(
                "⚠️ **3D visualization currently supports split-level systems only.**\n\n"
                "Single-ramp 3D rendering will be added in a future update. "
                "For now, please use the **2D Plans** tab to visualize the layout."
            )

        # Interactive controls in sidebar section
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 3D Visualization Controls")

        # Layer visibility
        show_slabs = st.sidebar.checkbox("Floor Slabs", value=True, help="Show discrete level floor plates")
        show_columns = st.sidebar.checkbox("Structural Columns", value=True, help="Show columns from the structural generator (≤31' spans)")
        show_walls = st.sidebar.checkbox("Center Elements", value=True, help="Show ramp edge barriers (split-level only)")
        show_circulation = st.sidebar.checkbox("Circulation Paths", value=False, help="Show optional traffic flow paths")
        show_half_levels = st.sidebar.checkbox("Half-Levels", value=True, help="Show half-level floor plates (P1.5, P2.5, etc.)")
        simplify_slabs = st.sidebar.checkbox("Simplified Slabs (Horizontal)", value=False, help="Render horizontal planes instead of helical ramps for clarity/performance")

        # Building features
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Building Features")
        show_cores = st.sidebar.checkbox("Corner Cores", value=True, help="Elevator, stairs, utility, and storage rooms")
        show_barriers = st.sidebar.checkbox("Safety Barriers", value=True, help="Perimeter guards, curbs, and edge protection")
        show_entrance = st.sidebar.checkbox("Entrance Ramp", value=True, help="North entrance with down ramp from street")

        # Camera view
        camera_view = st.sidebar.selectbox(
            "Camera View",
            options=['Isometric', 'Plan', 'Elevation_Front', 'Elevation_Side', 'Perspective'],
            index=0,
            help="Select viewing angle for 3D model"
        )

        # Floor range filter
        if garage.total_levels > 1:
            if garage.ramp_system == RampSystemType.SPLIT_LEVEL_DOUBLE:
                floor_slider_max = float(garage.half_levels_above / 2 + 0.5)
                floor_range = st.sidebar.slider(
                    "Show Floor Range",
                    min_value=0.5,
                    max_value=floor_slider_max,
                    value=(0.5, floor_slider_max),
                    step=0.5,
                    help="Filter which floors to display"
                )
            else:
                floor_slider_max = float(garage.half_levels_above)
                floor_range = st.sidebar.slider(
                    "Show Floor Range",
                    min_value=1.0,
                    max_value=floor_slider_max,
                    value=(1.0, floor_slider_max),
                    step=1.0,
                    help="Filter which floors to display"
                )
        else:
            floor_range = None

        # Generate 3D model
        try:
            fig_3d = create_3d_parking_garage(
                garage,
                show_slabs=show_slabs,
                show_columns=show_columns,
                show_walls=show_walls,
                show_footings=True,
                show_circulation=show_circulation,
                show_half_levels=show_half_levels,
                show_barriers=show_barriers,
                show_cores=show_cores,
                show_entrance=show_entrance,
                floor_range=floor_range,
                camera_preset=camera_view.lower(),
                simplify_slabs=simplify_slabs
            )

            # Display 3D model
            st.plotly_chart(fig_3d, use_container_width=True, key="garage_3d")
            st.caption("Note: Footings shown are conceptual for planning and cost purposes only (not for construction).")

            # Building info below model
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Footprint", f"{garage.width:.0f}' × {garage.length:.0f}'")
            col2.metric("Total Levels", len(garage.levels))
            col3.metric("Height", f"{garage.total_height_ft:.1f}'")
            col4.metric("Columns", garage.num_columns)

            # Discrete level breakdown
            with st.expander("Discrete Level Breakdown (GSF & Stalls per Level)"):
                levels_data = []
                for level_name, gsf, slab_type, elevation in garage.levels:
                    # Determine grade status
                    if elevation == garage.entry_elevation:
                        grade_status = "Entry (at grade)"
                    elif elevation < 0:
                        grade_status = f"Below grade ({elevation:.1f}')"
                    else:
                        grade_status = f"Above grade (+{elevation:.1f}')"

                    # Get stall count for this level
                    stalls = garage.stalls_by_level.get(level_name, {}).get('stalls', 0)
                    sf_per_stall = f"{gsf/stalls:.0f}" if stalls > 0 else "N/A"

                    levels_data.append({
                        "Level": level_name,
                        "Elevation": grade_status,
                        "GSF": f"{gsf:,.0f} SF",
                        "Stalls": stalls,
                        "SF/Stall": sf_per_stall,
                        "Type": slab_type.upper(),
                        "% of Footprint": f"{(gsf / garage.footprint_sf * 100):.1f}%"
                    })
                st.dataframe(pd.DataFrame(levels_data), use_container_width=True, hide_index=True)

                # System-specific level note
                if garage.is_half_level_system:
                    level_note = "*All levels are half-levels (~50% footprint) except entry/top which have reductions*"
                else:
                    level_note = "*All levels are full floors (100% footprint) except top level which has ramp termination reduction*"

                st.markdown(f"""
                **Total GSF:** {garage.total_gsf:,.0f} SF
                **Entry Level:** {garage.get_level_name(garage.entry_level_index)} at elevation {garage.entry_elevation:.1f}'
                **SOG Levels:** {garage.sog_levels_sf:,.0f} SF (ground contact)
                **Suspended Levels:** {garage.suspended_levels_sf:,.0f} SF (elevated)
                **Depth Below Grade:** {garage.depth_below_grade_ft:.1f}'

                {level_note}
                """)

        except Exception as e:
            st.error(f"Error generating 3D visualization: {e}")
            st.info("3D model unavailable. Check console for details.")
            import traceback
            st.code(traceback.format_exc())

    with tab4:
        st.subheader("2D Parking Layout Plans")
        st.markdown("Detailed floor plans showing stall-by-stall layout, core blockages, and optimization opportunities.")

        # View mode selector
        col1, col2 = st.columns([4, 1])
        with col1:
            view_mode = st.radio(
                "View Mode",
                ["Overview (All Levels)", "Individual Levels"],
                horizontal=True,
                help="Overview shows all stalls across all levels; Individual shows per-level breakdown"
            )

        # Calculate optimization once (cached for this configuration)
        opt_result = calculate_layout_optimization(garage.width, garage.length, garage.num_bays)

        st.markdown("---")

        if view_mode == "Overview (All Levels)":
            # === OVERVIEW DIAGRAM ===
            with st.spinner("Generating overview diagram..."):
                overview_bytes = generate_overview_diagram_bytes(
                    garage, garage.width, garage.length, garage.num_bays, opt_result
                )
                st.image(overview_bytes, use_container_width=True)

            # Information box
            st.info(f"""
            **Overview Legend:**
            - **Total stalls:** {garage.total_stalls} (all levels combined)
            - **Color coding:** North turn (light blue), South turn (sky blue), West row (light green), East row (pale green), Center rows (yellow)
            - **Red hatched areas:** Core blockages (elevator, stairs, utilities, storage)
            - **Dimension lines:** Show excess space at row ends (optimization opportunities)
            - **Optimization box:** Bottom-right corner shows recommended length adjustments
            """)

        else:
            # === INDIVIDUAL LEVEL SELECTOR ===
            col1, col2, col3 = st.columns([4, 1, 1])

            with col1:
                level_names = [level[0] for level in garage.levels]
                selected_level = st.selectbox(
                    "Select Level",
                    level_names,
                    index=0,
                    help="Choose a parking level to view detailed stall layout"
                )

            with col2:
                # Show level stall count
                level_data = garage.stalls_by_level.get(selected_level, {})
                st.metric("Stalls", level_data.get('stalls', 0))

            with col3:
                # Show level GSF
                level_gsf = next((gsf for name, gsf, _, _ in garage.levels if name == selected_level), 0)
                st.metric("GSF", f"{level_gsf:,.0f}")

            # Generate and display level diagram
            with st.spinner(f"Generating {selected_level} diagram..."):
                level_bytes = generate_level_diagram_bytes(
                    garage, garage.width, garage.length, garage.num_bays, selected_level, opt_result
                )
                st.image(level_bytes, use_container_width=True)

            # Level details below diagram
            if level_data:
                st.markdown("---")
                st.markdown("### Level Configuration")

                col1, col2, col3 = st.columns(3)
                col1.metric("Turn Zone", level_data.get('turn_zone', 'N/A').upper())
                col2.metric("Ramp Side", level_data.get('ramp_side', 'N/A').upper())
                col3.metric("SF/Stall", f"{level_gsf / level_data.get('stalls', 1):.0f}" if level_data.get('stalls') else "N/A")

                # Zone breakdown table
                zones = level_data.get('zones', {})
                if zones:
                    st.markdown("#### Stalls by Zone")
                    zone_data = []
                    for zone_name, zone_info in zones.items():
                        zone_data.append({
                            "Zone": zone_name.replace('_', ' ').title(),
                            "Stalls": zone_info.get('stalls', 0)
                        })

                    zone_df = pd.DataFrame(zone_data)
                    st.dataframe(zone_df, use_container_width=True, hide_index=True)

    with tab5:
        st.subheader("Scenario Comparison")
        st.info("Scenario comparison tool coming soon! Save and compare multiple configurations.")

        # Baseline comparison
        baseline_stalls = 284
        baseline_cost = 12272200

        st.markdown("### vs. Baseline Design")
        comp_df = pd.DataFrame([
            {"Metric": "Stall Count", "Baseline": baseline_stalls, "Current": garage.total_stalls, "Change": garage.total_stalls - baseline_stalls},
            {"Metric": "Total Cost", "Baseline": baseline_cost, "Current": costs['total'], "Change": costs['total'] - baseline_cost},
            {"Metric": "Cost per Stall", "Baseline": baseline_cost/baseline_stalls, "Current": costs['cost_per_stall'], "Change": costs['cost_per_stall'] - baseline_cost/baseline_stalls},
        ])
        st.dataframe(comp_df.style.format({
            "Baseline": "{:,.0f}",
            "Current": "{:,.0f}",
            "Change": "{:+,.0f}"
        }), use_container_width=True, hide_index=True)

    with tab6:
        st.subheader("Detailed Quantity Takeoffs & Cost Attribution")
        st.markdown("Complete component-level breakdown with quantities, units, unit costs, and total costs.")

        # Get detailed takeoffs data
        detailed_data = detailed_takeoffs

        # ========== SECTION 1: FOUNDATION ==========
        with st.expander("01 - FOUNDATION", expanded=False):
            section = detailed_data['01_foundation']
            st.markdown(f"**Section Total: ${section['total']:,.0f}**")

            # Create DataFrame for foundation items
            foundation_df = pd.DataFrame(section['items'])

            # Format the dataframe
            st.dataframe(
                foundation_df.style.format({
                    'quantity': '{:,.1f}',
                    'unit_cost': lambda x: f'${x:,.2f}' if x is not None else '-',
                    'total': lambda x: f'${x:,.0f}' if x is not None else '-'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    'component': st.column_config.TextColumn('Component', width='medium'),
                    'quantity': st.column_config.NumberColumn('Quantity', width='small'),
                    'unit': st.column_config.TextColumn('Unit', width='small'),
                    'unit_cost': st.column_config.TextColumn('Unit Cost', width='small'),
                    'total': st.column_config.TextColumn('Total Cost', width='small'),
                    'notes': st.column_config.TextColumn('Notes', width='large')
                }
            )

        # ========== SECTION 2: EXCAVATION & EARTHWORK ==========
        with st.expander("02 - EXCAVATION & EARTHWORK", expanded=False):
            section = detailed_data['02_excavation']
            st.markdown(f"**Section Total: ${section['total']:,.0f}**")

            excavation_df = pd.DataFrame(section['items'])
            st.dataframe(
                excavation_df.style.format({
                    'quantity': '{:,.1f}',
                    'unit_cost': lambda x: f'${x:,.2f}' if x is not None and x > 0 else '-',
                    'total': lambda x: f'${x:,.0f}' if x is not None and x > 0 else '-'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    'component': st.column_config.TextColumn('Component', width='medium'),
                    'quantity': st.column_config.NumberColumn('Quantity', width='small'),
                    'unit': st.column_config.TextColumn('Unit', width='small'),
                    'unit_cost': st.column_config.TextColumn('Unit Cost', width='small'),
                    'total': st.column_config.TextColumn('Total Cost', width='small'),
                    'notes': st.column_config.TextColumn('Notes', width='large')
                }
            )

        # ========== SECTION 3: STRUCTURE - CONCRETE ==========
        with st.expander("03 - STRUCTURE - CONCRETE", expanded=False):
            section = detailed_data['03_concrete']
            st.markdown(f"**Section Total: ${section['total']:,.0f}**")

            concrete_df = pd.DataFrame(section['items'])
            st.dataframe(
                concrete_df.style.format({
                    'quantity': '{:,.1f}',
                    'unit_cost': '${:,.2f}',
                    'total': '${:,.0f}'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    'component': st.column_config.TextColumn('Component', width='medium'),
                    'quantity': st.column_config.NumberColumn('Quantity', width='small'),
                    'unit': st.column_config.TextColumn('Unit', width='small'),
                    'unit_cost': st.column_config.TextColumn('Unit Cost', width='small'),
                    'total': st.column_config.TextColumn('Total Cost', width='small'),
                    'notes': st.column_config.TextColumn('Notes', width='large')
                }
            )

        # ========== SECTION 4: STRUCTURE - REINFORCEMENT ==========
        with st.expander("04 - STRUCTURE - REINFORCEMENT (Cost Attribution)", expanded=True):
            section = detailed_data['04_reinforcement']
            st.markdown(f"**Section Total: ${section['total']:,.0f}**")
            st.info("This section shows component-level attribution for all reinforcement: footing rebar, column rebar, slab rebar, wall rebar, and post-tensioning cables.")

            reinforcement_df = pd.DataFrame(section['items'])
            st.dataframe(
                reinforcement_df.style.format({
                    'quantity': '{:,.0f}',
                    'unit_cost': '${:,.2f}',
                    'total': '${:,.0f}'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    'component': st.column_config.TextColumn('Component', width='medium'),
                    'quantity': st.column_config.NumberColumn('Quantity', width='small'),
                    'unit': st.column_config.TextColumn('Unit', width='small'),
                    'unit_cost': st.column_config.TextColumn('Unit Cost', width='small'),
                    'total': st.column_config.TextColumn('Total Cost', width='small'),
                    'notes': st.column_config.TextColumn('Notes/Formula', width='large')
                }
            )

        # ========== SECTION 5: STRUCTURE - WALLS & CORES ==========
        with st.expander("05 - STRUCTURE - WALLS & CORES (Linear Feet Breakdown)", expanded=True):
            section = detailed_data['05_walls_cores']
            st.markdown(f"**Section Total: ${section['total']:,.0f}**")
            st.info("This section shows all vertical concrete elements with linear feet calculations.")

            walls_df = pd.DataFrame(section['items'])
            st.dataframe(
                walls_df.style.format({
                    'quantity': '{:,.1f}',
                    'unit_cost': lambda x: f'${x:,.2f}' if x is not None else '-',
                    'total': lambda x: f'${x:,.0f}' if x is not None else '-'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    'component': st.column_config.TextColumn('Component', width='medium'),
                    'quantity': st.column_config.NumberColumn('Quantity', width='small'),
                    'unit': st.column_config.TextColumn('Unit', width='small'),
                    'unit_cost': st.column_config.TextColumn('Unit Cost', width='small'),
                    'total': st.column_config.TextColumn('Total Cost', width='small'),
                    'notes': st.column_config.TextColumn('LF × Height', width='large')
                }
            )

        # ========== SECTION 6: VERTICAL TRANSPORTATION ==========
        with st.expander("06 - VERTICAL TRANSPORTATION", expanded=False):
            section = detailed_data['06_vertical']
            st.markdown(f"**Section Total: ${section['total']:,.0f}**")

            vertical_df = pd.DataFrame(section['items'])
            st.dataframe(
                vertical_df.style.format({
                    'quantity': '{:,.0f}',
                    'unit_cost': '${:,.0f}',
                    'total': '${:,.0f}'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    'component': st.column_config.TextColumn('Component', width='medium'),
                    'quantity': st.column_config.NumberColumn('Quantity', width='small'),
                    'unit': st.column_config.TextColumn('Unit', width='small'),
                    'unit_cost': st.column_config.TextColumn('Unit Cost', width='small'),
                    'total': st.column_config.TextColumn('Total Cost', width='small'),
                    'notes': st.column_config.TextColumn('Notes', width='large')
                }
            )

        # ========== SECTION 7: MEP SYSTEMS ==========
        with st.expander("07 - MEP SYSTEMS", expanded=False):
            section = detailed_data['07_mep']
            st.markdown(f"**Section Total: ${section['total']:,.0f}**")
            st.markdown(f"*All MEP costs applied to total GSF: {garage.total_gsf:,.0f} SF*")

            mep_df = pd.DataFrame(section['items'])
            st.dataframe(
                mep_df.style.format({
                    'quantity': '{:,.0f}',
                    'unit_cost': '${:,.2f}',
                    'total': '${:,.0f}'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    'component': st.column_config.TextColumn('Component', width='medium'),
                    'quantity': st.column_config.NumberColumn('Quantity', width='small'),
                    'unit': st.column_config.TextColumn('Unit', width='small'),
                    'unit_cost': st.column_config.TextColumn('Unit Cost', width='small'),
                    'total': st.column_config.TextColumn('Total Cost', width='small'),
                    'notes': st.column_config.TextColumn('Notes', width='large')
                }
            )

        # ========== SECTION 8: EXTERIOR & FINISHES ==========
        with st.expander("08 - EXTERIOR & FINISHES", expanded=False):
            section = detailed_data['08_exterior']
            st.markdown(f"**Section Total: ${section['total']:,.0f}**")

            exterior_df = pd.DataFrame(section['items'])
            st.dataframe(
                exterior_df.style.format({
                    'quantity': '{:,.0f}',
                    'unit_cost': '${:,.2f}',
                    'total': '${:,.0f}'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    'component': st.column_config.TextColumn('Component', width='medium'),
                    'quantity': st.column_config.NumberColumn('Quantity', width='small'),
                    'unit': st.column_config.TextColumn('Unit', width='small'),
                    'unit_cost': st.column_config.TextColumn('Unit Cost', width='small'),
                    'total': st.column_config.TextColumn('Total Cost', width='small'),
                    'notes': st.column_config.TextColumn('Notes', width='large')
                }
            )

        # ========== SECTION 9: LEVEL-BY-LEVEL SUMMARY ==========
        with st.expander("09 - LEVEL-BY-LEVEL SUMMARY", expanded=True):
            section = detailed_data['09_level_summary']
            st.markdown(f"**Total GSF: {section['total_gsf']:,.0f} SF | Total Stalls: {section['total_stalls']:,}**")
            st.info("Discrete level areas showing GSF and stall counts for each half-level/full-level.")

            # Create DataFrame from level data
            levels_df = pd.DataFrame(section['levels'])

            # Reorder columns for display
            display_df = levels_df[[
                'level_name', 'elevation_ft', 'gsf', 'stalls',
                'level_size', 'level_type', 'slab_type'
            ]]

            st.dataframe(
                display_df.style.format({
                    'elevation_ft': '{:.2f}',
                    'gsf': '{:,.0f}',
                    'stalls': '{:.0f}'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    'level_name': st.column_config.TextColumn('Level', width='small'),
                    'elevation_ft': st.column_config.NumberColumn('Elevation (ft)', width='small'),
                    'gsf': st.column_config.NumberColumn('GSF', width='small'),
                    'stalls': st.column_config.NumberColumn('Stalls', width='small'),
                    'level_size': st.column_config.TextColumn('Size', width='small'),
                    'level_type': st.column_config.TextColumn('Type', width='small'),
                    'slab_type': st.column_config.TextColumn('Slab Type', width='medium')
                }
            )

            # Summary metrics
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            col1.metric("Avg GSF/Level", f"{section['total_gsf'] / len(section['levels']):,.0f} SF")
            col2.metric("Avg Stalls/Level", f"{section['total_stalls'] / len(section['levels']):.1f}")
            col3.metric("Avg SF/Stall", f"{section['total_gsf'] / section['total_stalls']:.1f} SF")

        st.markdown("---")
        st.markdown("### Cost Items Ledger")
        if cost_items_df.empty:
            st.info("No cost items recorded in the current scenario.")
        else:
            ledger_df = cost_items_df[
                ["category", "description", "unit", "quantity", "unit_cost", "total_cost", "source_pass"]
            ].sort_values("total_cost", ascending=False)
            st.dataframe(
                ledger_df.style.format(
                    {
                        "quantity": "{:,.2f}",
                        "unit_cost": "${:,.2f}",
                        "total_cost": "${:,.0f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("### Quantity Table")
        if quantities_df.empty:
            st.info("No quantities recorded.")
        else:
            quantities_display = quantities_df.merge(
                elements_df[["element_id", "element_type", "name"]],
                on="element_id",
                how="left",
            )
            st.dataframe(
                quantities_display[
                    ["element_type", "name", "measure", "value", "unit", "source_pass", "notes"]
                ].sort_values(["element_type", "name"]),
                use_container_width=True,
                hide_index=True,
            )

    with tab7:
        st.subheader("TechRidge Budget Comparison")
        st.markdown("Compare model costs against TechRidge 1.2 SD Budget (May 2025 PDF)")

        # Get TR comparison data
        tr_comparison = tr_comparison_data

        # Overall Summary
        st.markdown("### Overall Variance")
        col1, col2, col3 = st.columns(3)

        totals = tr_comparison['totals']
        uc = tr_comparison['unit_costs']
        geom = tr_comparison['geometry']

        with col1:
            st.metric(
                "Total Cost Variance",
                f"${totals['variance']:+,.0f}",
                f"{totals['variance_pct']:+.1f}%",
                delta_color="inverse"
            )

        with col2:
            st.metric(
                "Our Total",
                f"${totals['our_total']:,.0f}",
                f"${uc['our_cost_per_sf']:.2f}/SF"
            )

        with col3:
            st.metric(
                "TR Total",
                f"${totals['tr_total']:,.0f}",
                f"${uc['tr_cost_per_sf']:.2f}/SF"
            )

        # Geometry Comparison
        st.markdown("### Geometry Comparison")
        geom_df = pd.DataFrame([
            {"Metric": "Total GSF", "TechRidge": f"{geom['tr_gsf']:,} SF", "Our Model": f"{geom['our_gsf']:,.0f} SF"},
            {"Metric": "Total Stalls", "TechRidge": f"{geom['tr_stalls']}", "Our Model": f"{geom['our_stalls']}"},
            {"Metric": "Cost per SF", "TechRidge": f"${uc['tr_cost_per_sf']:.2f}", "Our Model": f"${uc['our_cost_per_sf']:.2f}"},
            {"Metric": "Cost per Stall", "TechRidge": f"${uc['tr_cost_per_stall']:,.0f}", "Our Model": f"${uc['our_cost_per_stall']:,.0f}"}
        ])
        st.dataframe(geom_df, use_container_width=True, hide_index=True)

        # Category-by-Category Comparison
        st.markdown("### Category-by-Category Comparison")
        st.markdown("**Legend:** ✓ Within 10% | ⚠️ Within 20% | ❌ Over 20% variance | ⊕ Our item (not in TR)")

        # Create DataFrame for categories
        categories_data = []
        for cat in tr_comparison['categories']:
            categories_data.append({
                "Category": cat['category'],
                "TR Cost": cat['tr_cost'],
                "Our Cost": cat['our_cost'],
                "Variance": cat['variance'],
                "Variance %": cat['variance_pct'],
                "Status": cat['status'],
                "Notes": cat.get('notes', '')
            })

        categories_df = pd.DataFrame(categories_data)

        # Display with formatting
        st.dataframe(
            categories_df.style.format({
                'TR Cost': lambda x: f'${x:,.0f}',
                'Our Cost': lambda x: f'${x:,.0f}',
                'Variance': lambda x: f'${x:+,.0f}',
                'Variance %': lambda x: f'{x:+.1f}%'
            }),
            use_container_width=True,
            hide_index=True,
            column_config={
                'Category': st.column_config.TextColumn('Category', width='large'),
                'TR Cost': st.column_config.NumberColumn('TR Cost', width='small'),
                'Our Cost': st.column_config.NumberColumn('Our Cost', width='small'),
                'Variance': st.column_config.NumberColumn('Variance', width='small'),
                'Variance %': st.column_config.NumberColumn('Variance %', width='small'),
                'Status': st.column_config.TextColumn('Status', width='small'),
                'Notes': st.column_config.TextColumn('Notes', width='large')
            }
        )

        # Key Findings
        st.markdown("### Key Findings")

        # Count by status (ignore categories with no baseline)
        within_10 = sum(1 for cat in tr_comparison['categories'] if cat.get('status') == "✓")
        within_20 = sum(1 for cat in tr_comparison['categories'] if cat.get('status') == "⚠️")
        over_20 = sum(1 for cat in tr_comparison['categories'] if cat.get('status') == "❌")
        na_missing = sum(1 for cat in tr_comparison['categories'] if cat.get('status') == "N/A")

        col1, col2, col3 = st.columns(3)
        col1.metric("✓ Within 10%", f"{within_10} categories")
        col2.metric("⚠️ Within 20%", f"{within_20} categories")
        col3.metric("❌ Over 20%", f"{over_20} categories")
        if na_missing:
            st.caption(f"ℹ️ {na_missing} categories have no baseline value (marked N/A).")

        st.markdown("#### Notes:")
        st.markdown("""
        - **Footing rebar double-count has been FIXED** (previously added ~$500-700)
        - **Exterior screen variance** is expected (TR has different building height/configuration)
        - **Site work variance** is expected (we don't model utilities, drainage, erosion control)
        - **VDC Coordination** is in our model but not separately broken out in TR (likely in GC)
        - **Overall +9.2% variance** is acceptable given design differences
        """)

        # TR-Aligned Ledger Breakdown
        st.markdown("### TR-Aligned Ledger (Our Lines Mapped to TR Buckets)")
        tr_aligned = reporting_build_tr_aligned_breakdown(cost_items_df)

        # Totals by TR bucket (compact summary bar)
        totals_rows = [{"TR Category": k, "Our Total": v} for k, v in tr_aligned["totals_by_tr"].items()]
        totals_df = pd.DataFrame(totals_rows)
        st.dataframe(
            totals_df.style.format({"Our Total": "${:,.0f}"}),
            use_container_width=True,
            hide_index=True,
        )

        # Detailed lines
        lines_df = pd.DataFrame(tr_aligned["rows"])
        if not lines_df.empty:
            st.dataframe(
                lines_df.sort_values(["tr_category", "total"], ascending=[True, False]).style.format({
                    "quantity": "{:,.2f}",
                    "unit_cost": "${:,.2f}",
                    "total": "${:,.0f}",
                }),
                use_container_width=True,
                hide_index=True,
            )
            # Export button
            csv_bytes = lines_df.to_csv(index=False).encode("utf-8")
            st.download_button("Download TR-Aligned Ledger (CSV)", csv_bytes, file_name="tr_aligned_ledger.csv", mime="text/csv")

except Exception as e:
    st.error(f"Error calculating garage: {str(e)}")
    import traceback
    st.code(traceback.format_exc())

# Footer
st.markdown("---")
st.markdown("**TechRidge Split-Level Parking Garage Analyzer** | Built with Streamlit & Plotly")
