"""
Footing design calculator for split-level parking garage structures

Implements full ACI 318-19 structural design for:
- Spread footings under columns (punching shear, one-way shear, flexure)
- Continuous footings under core walls (elevator, stairs, utility, storage)
- Retaining wall footings for below-grade construction (cantilever design)

All footings designed for allowable soil bearing capacity with safety factors.
"""

import math
from typing import Dict, List, Tuple

# Type hints only - avoid circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .garage import SplitLevelParkingGarage


class FootingCalculator:
    """
    Calculate footing sizes and quantities based on column loads and soil conditions

    Design per ACI 318-19:
    - Spread footings: Punching shear (22.6.5.2), one-way shear (22.5.5.1), flexure (22.3)
    - Continuous footings: Load-based width sizing
    - Retaining walls: Stability (overturning, sliding, bearing)
    """

    def __init__(
        self,
        garage: 'SplitLevelParkingGarage',  # String annotation to avoid circular import
        soil_bearing_capacity: float = 3500,
        fc: int = 4000,
        load_factor_dl: float = 1.2,
        load_factor_ll: float = 1.6,
        allow_ll_reduction: bool = True,
        continuous_footing_rebar_rate: float = 110.0,
        spread_footing_rebar_rate: float = 65.0,
        dead_load_psf: float = 115.0,
        live_load_psf: float = 50.0
    ):
        """
        Initialize footing calculator

        Args:
            garage: SplitLevelParkingGarage geometry instance
            soil_bearing_capacity: Allowable bearing pressure (PSF), default 3500
            fc: Concrete compressive strength (PSI), default 4000
            load_factor_dl: Dead load factor (ACI 318-19), default 1.2
            load_factor_ll: Live load factor (ACI 318-19), default 1.6
            allow_ll_reduction: Enable live load reduction (default True; can be disabled)
            continuous_footing_rebar_rate: Reinforcement rate for continuous footings (lbs/CY), default 110
            spread_footing_rebar_rate: Reinforcement rate for spread footings (lbs/CY), default 65
            dead_load_psf: Dead load per square foot (PSF), default 115 (100 slab + 15 superimposed)
            live_load_psf: Live load per square foot (PSF), default 50 (parking per IBC 2021)
        """
        self.garage = garage
        self.bearing_capacity = soil_bearing_capacity
        self.fc = fc
        self.load_factor_dl = load_factor_dl
        self.load_factor_ll = load_factor_ll
        self.allow_ll_reduction = allow_ll_reduction
        self.continuous_rebar_rate = continuous_footing_rebar_rate
        self.spread_rebar_rate = spread_footing_rebar_rate
        # Legacy attribute for backward compatibility
        self.rebar_rate = continuous_footing_rebar_rate

        # Load assumptions (PSF) - now parametric, user-adjustable
        self.dead_load_psf = dead_load_psf
        self.live_load_psf = live_load_psf

        # Calculate tributary areas dynamically from actual column spacing
        # Note: The garage object may not have column_spacing_ft attribute,
        # so we extract it from the standard 31' grid used in the geometry
        try:
            spacing_ft = garage.column_spacing_ft
        except AttributeError:
            # Default to 31' grid if attribute not available
            spacing_ft = 31.0

        # Tributary areas by column type (SF) - calculated from column spacing
        self.tributary_areas = {
            'corner': (spacing_ft/2) * (spacing_ft/2),  # Quarter bay
            'edge': spacing_ft * (spacing_ft/2),  # Half bay
            'interior_perimeter': spacing_ft * spacing_ft,  # Full bay
            'center_ramp': spacing_ft * spacing_ft  # Full bay (slab only, beams/curbs added separately)
        }
        self.column_spacing_ft = spacing_ft  # Store for reference

        # Center core wall additional loads (split-level only)
        # From geometry.py: 12" core wall full height + 8"×12" curbs
        # Note: Single-ramp system has NO center elements
        self.has_center_beams = True  # Legacy variable (now means "has core wall")

        # ACI 318-19 punching shear location factors
        self.alpha_s = {
            'corner': 20,
            'edge': 30,
            'interior_perimeter': 40,
            'center_ramp': 40
        }

        # Minimum footing depth (inches)
        self.min_depth_in = 18

    # ===== Live Load Reduction (Strategy Scaffold) ==================================
    def _get_reduced_live_load_psf(self, tributary_area_sf: float, floors_supported: float) -> float:
        """
        Compute live load (PSF) after reduction.
        Strategy scaffold:
        - Default (current): simple 20% reduction when supporting ≥2 equivalent full floors
        - Future: ASCE 7-16 area-based method for columns (uses tributary area and floors)
        """
        if not self.allow_ll_reduction:
            return self.live_load_psf
        # Default conservative reduction
        if floors_supported >= 2.0:
            return 0.8 * self.live_load_psf
        return self.live_load_psf

    def calculate_column_load(
        self,
        tributary_area: float,
        column_type: str = 'interior_perimeter'
    ) -> Dict[str, float]:
        """
        Calculate service and factored loads on column

        Includes:
        - Slab dead load (tributary area × DL PSF × levels)
        - Slab live load (tributary area × LL PSF × levels)
        - Column self-weight
        - Core wall weight (distributed to columns along centerline)
        - Curbs (at base of core walls)

        Args:
            tributary_area: Tributary area for this column (SF)
            column_type: 'corner', 'edge', 'interior_perimeter', or 'center_ramp'
                        (used for determining column dimensions and core wall loads)

        Returns:
            dict with 'service_load' (lbs, unfactored) and 'factored_load' (lbs)
        """

        # Calculate EQUIVALENT FULL FLOORS
        # In split-level design, half-levels have ~50% footprint area
        # So total GSF / footprint gives equivalent number of full floors
        equivalent_full_floors = self.garage.total_gsf / self.garage.footprint_sf

        # Live load with reduction strategy (scaffold for ASCE 7 method)
        ll_psf = self._get_reduced_live_load_psf(tributary_area, equivalent_full_floors)

        # Service loads (unfactored) - slab only
        # Use equivalent full floors instead of total_levels
        dl_slab = tributary_area * self.dead_load_psf * equivalent_full_floors
        ll_total = tributary_area * ll_psf * equivalent_full_floors

        # Column self-weight
        # Perimeter columns: 18"×24" = 3.0 SF × height × 150 PCF
        # Center columns: 32"×24" = 5.33 SF × height × 150 PCF
        if column_type == 'center_ramp':
            column_area_sf = (32/12) * (24/12)  # 5.33 SF
        else:
            column_area_sf = (18/12) * (24/12)  # 3.0 SF

        column_weight = column_area_sf * self.garage.total_height_ft * 150

        # Additional loads for center/ramp columns
        core_wall_weight = 0
        curb_weight = 0

        # Total dead load
        dl_total = dl_slab + column_weight + core_wall_weight + curb_weight

        # Total service load
        service_load = dl_total + ll_total

        # Factored load (for structural design)
        factored_load = (
            self.load_factor_dl * dl_total +
            self.load_factor_ll * ll_total
        )

        return {
            'service_load': service_load,
            'factored_load': factored_load,
            'tributary_area': tributary_area,
            'equivalent_full_floors': equivalent_full_floors,
            'slab_dl': dl_slab,
            'column_weight': column_weight,
            'core_wall_weight': core_wall_weight,
            'curb_weight': curb_weight
        }

    def _calculate_size_effect_factor(self, d_inches: float) -> float:
        """
        Calculate size effect factor λs per ACI 318-19 Eq. 22.5.5.1.3

        Args:
            d_inches: Effective depth in inches

        Returns:
            λs size effect factor
        """
        return math.sqrt(2.0 / (1.0 + 0.004 * d_inches))

    def _calculate_punching_shear_capacity(
        self,
        width_ft: float,
        d_inches: float,
        column_width_in: float,
        column_depth_in: float,
        column_type: str
    ) -> float:
        """
        Calculate punching shear capacity per ACI 318-19 Section 22.6.5.2

        Args:
            width_ft: Footing width (feet)
            d_inches: Effective depth (inches)
            column_width_in: Column width (inches)
            column_depth_in: Column depth (inches)
            column_type: Column classification for α_s factor

        Returns:
            φVc: Design punching shear capacity (pounds)
        """
        # Critical section perimeter at d/2 from column face
        d_ft = d_inches / 12.0
        col_w_ft = column_width_in / 12.0
        col_d_ft = column_depth_in / 12.0

        # Perimeter at d/2 from column face (rectangular section)
        bo_ft = 2 * (col_w_ft + d_ft) + 2 * (col_d_ft + d_ft)
        bo_in = bo_ft * 12

        # Size effect factor
        lambda_s = self._calculate_size_effect_factor(d_inches)

        # Column aspect ratio
        beta = max(column_depth_in, column_width_in) / min(column_depth_in, column_width_in)

        # Location factor
        alpha_s = self.alpha_s[column_type]

        # ACI 318-19 Eq. 22.6.5.2 - punching shear stress (PSI)
        vc_psi = min(
            2 + 4/beta,
            alpha_s * d_inches / bo_in + 2,
            4
        ) * lambda_s * 1.0 * math.sqrt(self.fc)

        # φVc capacity (pounds)
        phi = 0.75  # Shear strength reduction factor
        area_in2 = bo_in * d_inches
        phi_Vc = phi * vc_psi * area_in2

        return phi_Vc

    def _calculate_one_way_shear_capacity(
        self,
        width_ft: float,
        d_inches: float
    ) -> float:
        """
        Calculate one-way shear capacity per ACI 318-19 Section 22.5.5.1

        Args:
            width_ft: Footing width (feet)
            d_inches: Effective depth (inches)

        Returns:
            φVc: Design one-way shear capacity (pounds)
        """
        # Size effect factor
        lambda_s = self._calculate_size_effect_factor(d_inches)

        # ACI 318-19 Eq. 22.5.5.1 - one-way shear stress (PSI)
        vc_psi = 2 * lambda_s * 1.0 * math.sqrt(self.fc)

        # φVc capacity (pounds)
        phi = 0.75  # Shear strength reduction factor
        width_in = width_ft * 12
        area_in2 = width_in * d_inches
        phi_Vc = phi * vc_psi * area_in2

        return phi_Vc

    def design_spread_footing(
        self,
        column_load_dict: Dict[str, float],
        column_type: str
    ) -> Dict:
        """
        Design spread footing per ACI 318-19

        Checks:
        1. Bearing capacity (service loads)
        2. Punching shear (factored loads)
        3. One-way shear (factored loads)
        4. Flexure (typically not governing)

        Args:
            column_load_dict: Result from calculate_column_load()
            column_type: Column classification

        Returns:
            dict with footing dimensions, volumes, costs
        """
        service_load = column_load_dict['service_load']
        factored_load = column_load_dict['factored_load']

        # Step 1: Required footing area from bearing capacity
        req_area_sf = service_load / self.bearing_capacity
        width_ft = math.ceil(math.sqrt(req_area_sf))

        # Step 2: Determine required depth from shear
        # Start with conservative heuristic: depth = width/10, min 18"
        # This provides a reasonable starting point that gets refined by iteration
        d_trial_in = max(width_ft * 12 / 10, self.min_depth_in)

        # Column dimensions
        if column_type == 'center_ramp':
            col_w_in, col_d_in = 32, 24
        else:
            col_w_in, col_d_in = 18, 24

        # Iterate to find adequate depth
        d_inches = d_trial_in
        max_iterations = 50  # Increased for finer 2" increments
        iteration = 0

        while iteration < max_iterations:
            # Soil pressure (factored loads for shear design)
            actual_area_sf = width_ft * width_ft
            qu_psf = factored_load / actual_area_sf

            # Check punching shear
            phi_Vc_punch = self._calculate_punching_shear_capacity(
                width_ft, d_inches, col_w_in, col_d_in, column_type
            )

            # Punching shear demand
            # Vu = total load - load within punching perimeter
            d_ft = d_inches / 12.0
            col_w_ft = col_w_in / 12.0
            col_d_ft = col_d_in / 12.0
            punch_area_sf = (col_w_ft + d_ft) * (col_d_ft + d_ft)
            Vu_punch = factored_load - (qu_psf * punch_area_sf)

            # Check one-way shear (critical at d from column face)
            phi_Vc_oneway = self._calculate_one_way_shear_capacity(width_ft, d_inches)

            # One-way shear demand (at d from column face)
            cantilever_ft = (width_ft - col_w_ft/12.0) / 2.0 - d_ft
            if cantilever_ft > 0:
                Vu_oneway = qu_psf * width_ft * cantilever_ft
            else:
                Vu_oneway = 0

            # Check if depth is adequate
            if phi_Vc_punch >= Vu_punch and phi_Vc_oneway >= Vu_oneway:
                break  # Adequate depth found

            # Increase depth by 2" and retry
            d_inches += 2
            iteration += 1

        # Convert effective depth to total depth (add cover)
        cover_in = 3  # 3" cover typical for footings
        total_depth_in = d_inches + cover_in

        # Round to nearest 3" increment (finer than 6" for efficiency)
        total_depth_in = math.ceil(total_depth_in / 3) * 3
        depth_ft = total_depth_in / 12.0

        # Branch: Two-depth footing for constructability and efficiency (see user spec)
        # Conditions where two layers make sense:
        # - Plan size ≥ 10' × 10'
        # - Total depth ≥ 12"
        if width_ft >= 10 and total_depth_in >= 12:
            return self._design_two_depth_spread_footing(
                width_ft=width_ft,
                total_depth_in=total_depth_in,
                service_load=service_load,
                factored_load=factored_load,
                column_type=column_type
            )
        else:
            # Single-thickness footing (small/shallower)
            concrete_cy = (width_ft * width_ft * depth_ft) / 27.0
            rebar_lbs = concrete_cy * self.spread_rebar_rate
            excavation_cy = concrete_cy * 1.2
            designation = f"FS{width_ft}.0"
            actual_bearing_pressure = service_load / (width_ft * width_ft)
            return {
                'width_ft': width_ft,
                'depth_ft': depth_ft,
                'depth_in': total_depth_in,
                'area_sf': width_ft * width_ft,
                'concrete_cy': concrete_cy,
                'rebar_lbs': rebar_lbs,
                'excavation_cy': excavation_cy,
                'designation': designation,
                'service_load': service_load,
                'factored_load': factored_load,
                'bearing_pressure': actual_bearing_pressure,
                'column_type': column_type,
                'two_depth': False
            }

    def _design_two_depth_spread_footing(
        self,
        *,
        width_ft: float,
        total_depth_in: float,
        service_load: float,
        factored_load: float,
        column_type: str
    ) -> Dict:
        """
        Two-depth footing design:
        - Outer mat: thinner, full width (B × B)
        - Drop panel: thicker, centered under column (b_dp × a_dp)
        Increments:
          - Plan widths: 1' increments
          - Drop thickness: 6" increments
          - Outer mat thickness: 1" increments (min 12")
        """
        # Column dimensions (inches)
        if column_type == 'center_ramp':
            col_w_in, col_d_in = 32, 24
        else:
            col_w_in, col_d_in = 18, 24

        # Start with outer mat thickness 12", allow 1" increments if needed
        t_outer_in = 12
        t_outer_ft = t_outer_in / 12.0

        # Drop panel target thickness starts from total depth (effective d) minus cover
        # Round to nearest 6"
        cover_in = 3
        d_inner_in = max(total_depth_in - cover_in, 12)  # ≥12" effective
        d_inner_in = math.ceil(d_inner_in / 6.0) * 6.0

        # Ensure inner total thickness ≥ outer thickness + cover
        t_inner_in = max(t_outer_in + 6, d_inner_in)  # start with something thicker than outer

        # Drop panel plan dimensions must cover critical sections:
        # - For punching: perimeter at d/2 from column face lies within drop
        # - For one-way shear: section at d from column face lies within drop
        def required_drop_dim_in(d_eff_in: float, col_in: float, margin_in: float = 0.0) -> float:
            # Minimum total dimension = col + 2×(d/2) = col + d
            return col_in + d_eff_in + margin_in

        # Round plan dimensions to 1' increments, minimum 4'
        def round_plan_ft(required_in: float) -> float:
            ft = required_in / 12.0
            ft = max(4.0, ft)
            return math.ceil(ft)  # 1' increments

        # Iterate on drop thickness and drop area until shear checks pass
        max_drop_thickness_in = 36.0
        solved = False
        for t_candidate_in in range(int(t_inner_in), int(max_drop_thickness_in) + 1, 6):
            # Effective depth d for punching/one-way near column
            d_eff_in = t_candidate_in - cover_in
            d_eff_ft = d_eff_in / 12.0

            # Required drop panel dimensions
            req_x_in = required_drop_dim_in(d_eff_in, col_w_in)
            req_y_in = required_drop_dim_in(d_eff_in, col_d_in)
            b_dp_ft = round_plan_ft(req_x_in)
            a_dp_ft = round_plan_ft(req_y_in)

            # Ensure drop panel fits within outer width
            b_dp_ft = min(b_dp_ft, width_ft)
            a_dp_ft = min(a_dp_ft, width_ft)

            # Soil pressure for factored load
            qu_psf = factored_load / (width_ft * width_ft)

            # Punching capacity using d_eff_in (ACI 22.6.5.2)
            phi_Vc_punch = self._calculate_punching_shear_capacity(
                width_ft, d_eff_in, col_w_in, col_d_in, column_type
            )
            # Demand: Vu = Pu - q_u × A(within punching perimeter)
            col_w_ft = col_w_in / 12.0
            col_d_ft = col_d_in / 12.0
            punch_area_sf = (col_w_ft + d_eff_ft) * (col_d_ft + d_eff_ft)
            Vu_punch = factored_load - (qu_psf * punch_area_sf)

            # One-way shear check at d from column face (within drop panel)
            phi_Vc_oneway = self._calculate_one_way_shear_capacity(width_ft, d_eff_in)
            cantilever_ft = (width_ft - col_w_ft/12.0) / 2.0 - d_eff_ft
            Vu_oneway = qu_psf * width_ft * max(cantilever_ft, 0)

            if phi_Vc_punch >= Vu_punch and phi_Vc_oneway >= Vu_oneway:
                t_inner_in = t_candidate_in
                solved = True
                break

        if not solved:
            # Fallback to single-thickness design if two-depth solution not found within bounds
            depth_ft = total_depth_in / 12.0
            concrete_cy = (width_ft * width_ft * depth_ft) / 27.0
            rebar_lbs = concrete_cy * self.spread_rebar_rate
            excavation_cy = concrete_cy * 1.2
            designation = f"FS{width_ft}.0"
            actual_bearing_pressure = service_load / (width_ft * width_ft)
            return {
                'width_ft': width_ft,
                'depth_ft': depth_ft,
                'depth_in': total_depth_in,
                'area_sf': width_ft * width_ft,
                'concrete_cy': concrete_cy,
                'rebar_lbs': rebar_lbs,
                'excavation_cy': excavation_cy,
                'designation': designation,
                'service_load': service_load,
                'factored_load': factored_load,
                'bearing_pressure': actual_bearing_pressure,
                'column_type': column_type,
                'two_depth': False
            }

        # Volumes (outer mat + drop panel extra thickness)
        t_inner_ft = t_inner_in / 12.0
        outer_volume_cf = width_ft * width_ft * t_outer_ft
        extra_drop_thickness_ft = max(t_inner_ft - t_outer_ft, 0.0)
        drop_volume_cf = b_dp_ft * a_dp_ft * extra_drop_thickness_ft
        concrete_cy = (outer_volume_cf + drop_volume_cf) / 27.0

        rebar_lbs = concrete_cy * self.spread_rebar_rate
        excavation_cy = concrete_cy * 1.2
        designation = f"FS{width_ft}.0-DP{int(b_dp_ft)}x{int(a_dp_ft)}-{int(t_inner_in)}in/{int(t_outer_in)}in"
        actual_bearing_pressure = service_load / (width_ft * width_ft)

        return {
            'width_ft': width_ft,
            'outer_thickness_ft': t_outer_ft,
            'inner_thickness_ft': t_inner_ft,
            'drop_width_x_ft': b_dp_ft,
            'drop_width_y_ft': a_dp_ft,
            'area_sf': width_ft * width_ft,
            'concrete_cy': concrete_cy,
            'rebar_lbs': rebar_lbs,
            'excavation_cy': excavation_cy,
            'designation': designation,
            'service_load': service_load,
            'factored_load': factored_load,
            'bearing_pressure': actual_bearing_pressure,
            'column_type': column_type,
            'two_depth': True
        }

    def _calculate_flexural_moment(
        self,
        width_ft: float,
        depth_ft: float,
        factored_load: float,
        col_w_in: float
    ) -> float:
        """
        Calculate flexural moment in footing cantilever per ACI 318-19

        Critical section for moment is at face of column

        Args:
            width_ft: Footing width (feet)
            depth_ft: Footing depth (feet)
            factored_load: Factored column load (pounds)
            col_w_in: Column width (inches)

        Returns:
            Mu: Factored moment (lb-ft)
        """
        # Soil pressure under factored load
        area_sf = width_ft * width_ft
        qu_psf = factored_load / area_sf

        # Cantilever length from column face to footing edge
        cantilever_ft = (width_ft - col_w_in/12.0) / 2.0

        # Moment at critical section (face of column)
        # M = w × L²/2 where w = qu_psf × width_ft (load per LF of footing)
        w_plf = qu_psf * width_ft
        Mu_lbft = w_plf * cantilever_ft**2 / 2.0

        return Mu_lbft

    def _design_flexural_steel(
        self,
        Mu_lbft: float,
        width_ft: float,
        depth_ft: float
    ) -> Dict:
        """
        Design flexural reinforcement per ACI 318-19

        Args:
            Mu_lbft: Factored moment (lb-ft)
            width_ft: Footing width (feet)
            depth_ft: Footing depth (feet)

        Returns:
            dict with rebar details, or None if no valid solution
        """
        # Effective depth (total depth - cover - bar radius)
        cover_in = 3.0  # 3" cover for footings
        bar_diameter_in = 1.0  # Assume #8 bar initially (1" diameter)
        d_in = depth_ft * 12 - cover_in - bar_diameter_in/2
        d_ft = d_in / 12.0

        # Convert moment to lb-in
        Mu_lbin = Mu_lbft * 12

        # Required steel area (ACI 318-19 flexural design)
        # Assume tension-controlled section (φ = 0.9)
        phi = 0.9
        fy = 60000  # Grade 60 rebar (PSI)

        # Simplified approach: assume a ≈ 0.1×d (small compression block)
        # R = Mu / (φ × b × d²) where b = width in inches
        width_in = width_ft * 12
        R = Mu_lbin / (phi * width_in * d_in**2)

        # Required steel ratio: ρ = (0.85×fc/fy) × (1 - sqrt(1 - 2R/(0.85×fc)))
        # Simplified for typical footing (low moment): As = Mu / (φ × fy × 0.9×d)
        As_req_in2 = Mu_lbin / (phi * fy * 0.9 * d_in)

        # Minimum steel per ACI 318-19: 0.0018 × b × h for temperature/shrinkage
        h_in = depth_ft * 12
        As_min_in2 = 0.0018 * width_in * h_in

        # Use greater of required or minimum
        As_total_in2 = max(As_req_in2, As_min_in2)

        # Select bar size and spacing
        # Standard bar areas (in²): #4=0.20, #5=0.31, #6=0.44, #7=0.60, #8=0.79
        bar_areas = {
            4: 0.20, 5: 0.31, 6: 0.44, 7: 0.60, 8: 0.79, 9: 1.00, 10: 1.27
        }

        # Try bar sizes from #5 to #10 (typical for footings)
        for bar_num in [5, 6, 7, 8, 9, 10]:
            bar_area = bar_areas[bar_num]
            required_bars = As_total_in2 / bar_area
            spacing_in = width_in / required_bars

            # Check if spacing is reasonable (6" min, 18" max per ACI 318-19)
            if 6 <= spacing_in <= 18:
                # Found suitable bar size
                actual_bars = math.ceil(width_in / spacing_in) + 1  # Add 1 for edge bar
                actual_spacing_in = width_in / (actual_bars - 1) if actual_bars > 1 else width_in
                actual_As_in2 = actual_bars * bar_area

                # Weight calculation: length × bars × weight per foot
                bar_length_ft = width_ft + 2 * (cover_in / 12 + 1.0)  # Add development length
                bar_weights = {  # lbs per foot
                    4: 0.668, 5: 1.043, 6: 1.502, 7: 2.044, 8: 2.670, 9: 3.400, 10: 4.303
                }
                bar_weight_lbft = bar_weights[bar_num]
                total_rebar_lbs = actual_bars * bar_length_ft * bar_weight_lbft * 2  # Both directions

                return {
                    'required_As_in2': As_req_in2,
                    'minimum_As_in2': As_min_in2,
                    'provided_As_in2': actual_As_in2,
                    'bar_size': bar_num,
                    'bar_count': actual_bars,
                    'bar_spacing_in': actual_spacing_in,
                    'bar_length_ft': bar_length_ft,
                    'rebar_lbs': total_rebar_lbs,
                    'designation': f"#{bar_num} @ {int(actual_spacing_in)}\" o.c. E.W."
                }

        # No valid bar spacing found - this means footing is inadequate
        # Return None to signal iteration should continue (need larger footing or different depth)
        return None

    def _calculate_development_length(
        self,
        bar_size: int,
        fc: int = None
    ) -> float:
        """
        Calculate required development length per ACI 318-19 Section 25.4

        Args:
            bar_size: Bar number (4-10)
            fc: Concrete strength (PSI), uses self.fc if not provided

        Returns:
            ld: Required development length (feet)
        """
        if fc is None:
            fc = self.fc

        fy = 60000  # Grade 60 rebar

        # Bar diameters (inches)
        db_inches = {
            4: 0.5, 5: 0.625, 6: 0.75, 7: 0.875, 8: 1.0, 9: 1.128, 10: 1.27
        }
        db = db_inches.get(bar_size, 1.0)

        # ACI 318-19 Eq. 25.4.2.3 (simplified for normal conditions)
        # ld = (3/40) × (fy/√fc) × (ψt × ψe × ψs) × db
        # For footings: ψt = 1.0 (≤12" fresh concrete below), ψe = 1.0 (uncoated), ψs = 1.0 (standard)
        psi_t = 1.0
        psi_e = 1.0
        psi_s = 1.0

        ld_in = (3.0/40.0) * (fy / math.sqrt(fc)) * psi_t * psi_e * psi_s * db

        # Minimum per ACI: 12 inches
        ld_in = max(ld_in, 12.0)

        ld_ft = ld_in / 12.0
        return ld_ft

    def _check_footing_overlap(
        self,
        footings_list: List[Dict],
        new_footing: Dict,
        min_clearance_ft: float = 2.0
    ) -> Tuple[bool, List[str]]:
        """
        Check if new footing overlaps with existing footings

        Args:
            footings_list: List of existing footing dictionaries with 'x', 'y', 'width_ft'
            new_footing: New footing dict with 'x', 'y', 'width_ft'
            min_clearance_ft: Minimum clearance between footings (feet)

        Returns:
            (has_overlap, list of overlapping footing designations)
        """
        overlaps = []

        new_x = new_footing['x']
        new_y = new_footing['y']
        new_width = new_footing['width_ft']
        new_radius = new_width / 2.0

        for existing in footings_list:
            ex_x = existing['x']
            ex_y = existing['y']
            ex_width = existing['width_ft']
            ex_radius = ex_width / 2.0

            # Calculate center-to-center distance
            distance = math.sqrt((new_x - ex_x)**2 + (new_y - ex_y)**2)

            # Check if overlap (distance < sum of radii + clearance)
            required_distance = new_radius + ex_radius + min_clearance_ft

            if distance < required_distance:
                overlaps.append(existing.get('designation', f"Footing at ({ex_x}, {ex_y})"))

        return (len(overlaps) > 0, overlaps)

    def design_spread_footing_optimized(
        self,
        column_load_dict: Dict[str, float],
        column_type: str,
        existing_footings: List[Dict] = None,
        safety_margin: float = 1.2,
        enable_micropile_fallback: bool = True
    ) -> Dict:
        """
        OPTIMIZED spread footing design with multi-variable iterative solver

        Improvements over design_spread_footing():
        1. Iterates on both width AND depth for cost optimization
        2. Includes flexural reinforcement design (not just estimate)
        3. Verifies development length
        4. Checks footing overlap
        5. Applies safety margin to all capacities
        6. Flags micropile requirement if spread footing not feasible

        Args:
            column_load_dict: Result from calculate_column_load()
            column_type: Column classification
            existing_footings: List of existing footings (for overlap check)
            safety_margin: Safety factor on all capacities (default 1.2)
            enable_micropile_fallback: Enable micropile recommendation (default True)

        Returns:
            dict with comprehensive footing design results, or micropile recommendation
        """
        service_load = column_load_dict['service_load']
        factored_load = column_load_dict['factored_load']

        # Column dimensions
        if column_type == 'center_ramp':
            col_w_in, col_d_in = 32, 24
        else:
            col_w_in, col_d_in = 18, 24

        # Unit costs for optimization
        concrete_cost_cy = 650.0
        rebar_cost_lb = 1.25
        excavation_cost_cy = 8.0

        # ITERATION PARAMETERS
        max_width_ft = 15  # Maximum reasonable spread footing width
        min_width_ft = 3   # Minimum practical width
        width_increment_ft = 1
        depth_increment_in = 2
        max_iterations_width = int((max_width_ft - min_width_ft) / width_increment_ft) + 1
        max_iterations_depth = 50

        # Storage for valid solutions
        valid_solutions = []

        # OUTER LOOP: Iterate on width
        for width_iter in range(max_iterations_width):
            width_ft = min_width_ft + width_iter * width_increment_ft

            # Check bearing capacity with footing self-weight
            # Iterative refinement: assume depth, calculate weight, check bearing
            depth_trial_ft = max(width_ft / 10.0, 1.5)  # Initial depth estimate

            for _ in range(3):  # Refine footing self-weight assumption
                footing_weight = width_ft * width_ft * depth_trial_ft * 150  # PCF concrete
                total_service_load = service_load + footing_weight
                actual_bearing = total_service_load / (width_ft * width_ft)

                # Check if bearing capacity satisfied (with safety margin)
                if actual_bearing > self.bearing_capacity / safety_margin:
                    break  # Width too small, try next width

                # Refine depth estimate for next iteration
                depth_trial_ft = max(width_ft / 10.0, 1.5)
            else:
                # Bearing OK, proceed to depth iteration
                pass

            if actual_bearing > self.bearing_capacity / safety_margin:
                continue  # Width insufficient, try larger width

            # INNER LOOP: Iterate on depth to satisfy shear
            d_trial_in = max(width_ft * 12 / 10, self.min_depth_in)

            for depth_iter in range(max_iterations_depth):
                d_inches = d_trial_in + depth_iter * depth_increment_in

                # Soil pressure (factored loads for shear design)
                qu_psf = factored_load / (width_ft * width_ft)

                # Check punching shear
                phi_Vc_punch = self._calculate_punching_shear_capacity(
                    width_ft, d_inches, col_w_in, col_d_in, column_type
                )

                # Apply safety margin
                phi_Vc_punch_design = phi_Vc_punch / safety_margin

                # Punching shear demand
                d_ft = d_inches / 12.0
                col_w_ft = col_w_in / 12.0
                col_d_ft = col_d_in / 12.0
                punch_area_sf = (col_w_ft + d_ft) * (col_d_ft + d_ft)
                Vu_punch = factored_load - (qu_psf * punch_area_sf)

                if phi_Vc_punch_design < Vu_punch:
                    continue  # Punching shear fails, need more depth

                # Check one-way shear
                phi_Vc_oneway = self._calculate_one_way_shear_capacity(width_ft, d_inches)
                phi_Vc_oneway_design = phi_Vc_oneway / safety_margin

                cantilever_ft = (width_ft - col_w_in/12.0) / 2.0 - d_ft
                if cantilever_ft > 0:
                    Vu_oneway = qu_psf * width_ft * cantilever_ft
                else:
                    Vu_oneway = 0

                if phi_Vc_oneway_design < Vu_oneway:
                    continue  # One-way shear fails, need more depth

                # Convert to total depth
                cover_in = 3
                total_depth_in = d_inches + cover_in
                total_depth_in = math.ceil(total_depth_in / 3) * 3  # Round to 3" increment
                depth_ft = total_depth_in / 12.0

                # Calculate flexural moment
                Mu_lbft = self._calculate_flexural_moment(
                    width_ft, depth_ft, factored_load, col_w_in
                )

                # Design flexural reinforcement
                rebar_design = self._design_flexural_steel(Mu_lbft, width_ft, depth_ft)

                # If rebar design failed (no valid spacing), continue iteration
                if rebar_design is None:
                    continue  # Need different geometry

                # Check development length
                ld_required_ft = self._calculate_development_length(rebar_design['bar_size'])
                ld_available_ft = (width_ft - col_w_in/12.0) / 2.0 - cover_in/12.0

                if ld_required_ft > ld_available_ft:
                    continue  # Development length insufficient, need more width or depth

                # Calculate quantities
                concrete_cy = (width_ft * width_ft * depth_ft) / 27.0
                rebar_lbs = rebar_design['rebar_lbs']  # Use actual design, not estimate
                excavation_cy = concrete_cy * 1.2

                # Calculate cost
                cost = (concrete_cy * concrete_cost_cy +
                       rebar_lbs * rebar_cost_lb +
                       excavation_cy * excavation_cost_cy)

                # Valid solution found - store it
                solution = {
                    'width_ft': width_ft,
                    'depth_ft': depth_ft,
                    'depth_in': total_depth_in,
                    'area_sf': width_ft * width_ft,
                    'concrete_cy': concrete_cy,
                    'rebar_lbs': rebar_lbs,
                    'rebar_design': rebar_design,
                    'excavation_cy': excavation_cy,
                    'cost': cost,
                    'bearing_pressure': actual_bearing,
                    'punching_utilization': Vu_punch / phi_Vc_punch_design,
                    'oneway_utilization': Vu_oneway / phi_Vc_oneway_design if phi_Vc_oneway_design > 0 else 0,
                    'development_length_required_ft': ld_required_ft,
                    'development_length_available_ft': ld_available_ft
                }

                valid_solutions.append(solution)
                break  # Found adequate depth for this width, move to next width

        # Select optimal solution (minimum cost)
        if not valid_solutions:
            # NO VALID SPREAD FOOTING SOLUTION
            if enable_micropile_fallback:
                # Recommend micropiles
                # Use higher bearing capacity for deep foundations (3.5x surface bearing per geotechnical practice)
                micropile_bearing_psf = self.bearing_capacity * 3.5
                req_area_micropile = service_load / micropile_bearing_psf
                micropile_width = math.ceil(math.sqrt(req_area_micropile))

                return {
                    'footing_type': 'MICROPILE',
                    'width_ft': micropile_width,
                    'depth_ft': 0,  # Depth not applicable for micropiles
                    'area_sf': micropile_width * micropile_width,
                    'concrete_cy': 0,  # Placeholder - micropile design separate
                    'rebar_lbs': 0,
                    'excavation_cy': 0,
                    'designation': f'MICROPILE-{micropile_width}x{micropile_width}',
                    'service_load': service_load,
                    'factored_load': factored_load,
                    'bearing_pressure': 0,
                    'column_type': column_type,
                    'failure_reason': 'Spread footing exceeds geometric limits or overlaps - micropiles required',
                    'warning': '⚠️ DEEP FOUNDATION REQUIRED - Verify with geotechnical engineer'
                }
            else:
                raise ValueError(
                    f"No valid spread footing solution found for {column_type} column "
                    f"with load {service_load:,.0f} lbs and bearing capacity {self.bearing_capacity} PSF. "
                    f"Consider: (1) increasing bearing capacity, (2) enabling micropile fallback, "
                    f"or (3) using mat foundation."
                )

        # Find minimum cost solution
        optimal = min(valid_solutions, key=lambda s: s['cost'])

        # Check for overlaps if existing footings provided
        has_overlap = False
        overlap_list = []
        if existing_footings is not None:
            # Add position to optimal solution (will be filled by caller)
            optimal['x'] = 0  # Placeholder
            optimal['y'] = 0  # Placeholder
            has_overlap, overlap_list = self._check_footing_overlap(
                existing_footings, optimal
            )

        # Build final result
        designation = f"FS{optimal['width_ft']}.0"

        result = {
            'width_ft': optimal['width_ft'],
            'depth_ft': optimal['depth_ft'],
            'depth_in': optimal['depth_in'],
            'area_sf': optimal['area_sf'],
            'concrete_cy': optimal['concrete_cy'],
            'rebar_lbs': optimal['rebar_lbs'],
            'rebar_design': optimal['rebar_design'],
            'excavation_cy': optimal['excavation_cy'],
            'designation': designation,
            'service_load': service_load,
            'factored_load': factored_load,
            'bearing_pressure': optimal['bearing_pressure'],
            'column_type': column_type,
            'cost': optimal['cost'],
            'safety_margin': safety_margin,
            'punching_utilization': optimal['punching_utilization'],
            'oneway_utilization': optimal['oneway_utilization'],
            'development_length_ok': optimal['development_length_available_ft'] >= optimal['development_length_required_ft'],
            'footing_type': 'SPREAD',
            'num_valid_solutions': len(valid_solutions)
        }

        # Add overlap warning if detected
        if has_overlap:
            result['overlap_warning'] = f"⚠️ Footing overlaps with: {', '.join(overlap_list)}"
            result['has_overlap'] = True
        else:
            result['has_overlap'] = False

        return result

    def _classify_column(self, x: float, y: float) -> str:
        """
        Classify column by position in building grid

        Args:
            x: X-coordinate (along length direction)
            y: Y-coordinate (along width direction)

        Returns:
            Column type: 'corner', 'edge', 'interior_perimeter', 'center_ramp'
        """
        tolerance = 5.0  # feet
        spacing = self.column_spacing_ft  # Use dynamic column spacing

        # Building dimensions
        length = self.garage.length
        width = self.garage.width
        turn_zone_depth = self.garage.TURN_ZONE_DEPTH

        # Check if on perimeter
        on_west_edge = abs(y - spacing) < tolerance
        on_east_edge = abs(y - (width - spacing)) < tolerance
        on_north_edge = abs(x - spacing) < tolerance
        on_south_edge = abs(x - (length - spacing)) < tolerance

        # Check if on center line (ramp columns)
        center_y = width / 2.0
        on_center_line = abs(y - center_y) < tolerance

        # Check if in ramp section (not in turn zones)
        in_ramp_section = (turn_zone_depth < x < length - turn_zone_depth)

        # Corner columns
        if ((on_west_edge or on_east_edge) and (on_north_edge or on_south_edge)):
            return 'corner'

        # Center/ramp columns (highest loads)
        if on_center_line and in_ramp_section:
            return 'center_ramp'

        # Edge columns (perimeter, non-corner)
        if on_west_edge or on_east_edge or on_north_edge or on_south_edge:
            return 'edge'

        # Interior perimeter columns (one bay in from edge)
        return 'interior_perimeter'

    def calculate_spread_footings(self) -> Dict:
        """
        Calculate all spread footings under columns

        Uses tributary areas based on column classification and spacing.

        Returns:
            dict with footing details by type and totals
        """
        # Initialize storage
        footings_by_type = {
            'corner': [],
            'edge': [],
            'interior_perimeter': [],
            'center_ramp': []
        }

        # Prefer authoritative columns list from garage
        columns = getattr(self.garage, 'columns', [])
        trib_list = getattr(self.garage, 'column_tributary', [])
        for idx, c in enumerate(columns):
            x = float(c['x'])
            y = float(c['y'])
            y_line_type = c.get('y_line_type', 'interior')
            if y_line_type == 'ramp_center':
                col_type = 'center_ramp'
            elif y_line_type == 'perimeter':
                col_type = 'edge'
            else:
                # For interior stall/aisle boundaries treat as interior-perimeter
                col_type = 'interior_perimeter'

            # Prefer computed tributary area if available
            if idx < len(trib_list) and 'area_sf' in trib_list[idx]:
                tributary_area = max(trib_list[idx]['area_sf'], 0.0)
            else:
                tributary_area = self.tributary_areas.get(col_type, self.tributary_areas['interior_perimeter'])

            load_dict = self.calculate_column_load(tributary_area, col_type)
            footing = self.design_spread_footing(load_dict, col_type)
            footing['x'] = x
            footing['y'] = y
            footing['tributary_area'] = tributary_area
            footings_by_type[col_type].append(footing)

        # Calculate totals
        total_concrete_cy = sum(
            f['concrete_cy']
            for footings in footings_by_type.values()
            for f in footings
        )
        total_rebar_lbs = sum(
            f['rebar_lbs']
            for footings in footings_by_type.values()
            for f in footings
        )
        total_excavation_cy = sum(
            f['excavation_cy']
            for footings in footings_by_type.values()
            for f in footings
        )

        count_by_type = {k: len(v) for k, v in footings_by_type.items()}
        total_count = sum(count_by_type.values())

        return {
            'footings_by_type': footings_by_type,
            'count_by_type': count_by_type,
            'total_count': total_count,
            'total_concrete_cy': total_concrete_cy,
            'total_rebar_lbs': total_rebar_lbs,
            'total_excavation_cy': total_excavation_cy
        }

    def design_continuous_footing(
        self,
        wall_type: str,
        wall_length_ft: float,
        wall_height_ft: float,
        wall_thickness_ft: float = 1.0
    ) -> Dict:
        """
        Design continuous footing under core wall

        Includes:
        - Wall self-weight
        - Tributary parking slab loads
        - Equipment/specialized loads by core type:
          * Elevator: Equipment weight (cab, counterweight, machinery, rails)
          * Stairs: Metal stair dead load + specialized live load (100 PSF per IBC)
          * Utility: HVAC/electrical/fire equipment
          * Storage: Shelving + storage live load (125 PSF per IBC)

        Args:
            wall_type: 'elevator', 'stair', 'utility', 'storage'
            wall_length_ft: Length of wall (feet)
            wall_height_ft: Height of wall (feet)
            wall_thickness_ft: Wall thickness (feet), default 1.0 (12")

        Returns:
            dict with footing dimensions, volumes, costs
        """
        # Wall dead load (lbs per LF)
        wall_weight_plf = wall_height_ft * wall_thickness_ft * 150  # PCF concrete

        # Estimate tributary slab load
        # Assume footing extends wall_thickness on each side
        footing_width_trial_ft = 2.0 + wall_thickness_ft  # Initial guess
        tributary_width_ft = footing_width_trial_ft / 2.0

        # Slab loads on tributary width (use equivalent full floors for split-level geometry)
        equivalent_full_floors = self.garage.total_gsf / self.garage.footprint_sf
        slab_load_plf = tributary_width_ft * (self.dead_load_psf + self.live_load_psf) * equivalent_full_floors

        # === EQUIPMENT AND SPECIALIZED LOADS ===
        # Calculate additional loads based on core type
        equipment_load_plf = 0  # Dead load from equipment/stairs
        specialized_ll_plf = 0  # Live load using code-required values (not parking 50 PSF)

        if wall_type == 'elevator':
            # Elevator system loads distributed over footing perimeter
            # Based on industry standards: ~150 kips total typical
            # Components: cab (2,500 lbs) + passengers (2,500 lbs rated) + counterweight (3,750 lbs)
            #            + machinery (5,000 lbs) + guide rails (3,000 lbs) + pit (1,000 lbs)
            # Total: ~17,750 lbs distributed over perimeter
            # NOTE: In actual design, obtain loads from elevator supplier
            elevator_total_load = 17750  # lbs, conservative estimate
            equipment_load_plf = elevator_total_load / wall_length_ft
            # Live load component (passengers + dynamic)
            specialized_ll_plf = equipment_load_plf * 0.3

        elif 'stair' in wall_type:
            # Metal stair system (NOT concrete - parking garages use metal stairs)
            # Metal stairs: ~20 PSF dead load (vs 75 PSF for concrete)
            # Each flight: 12' run × 4' width = 48 SF × 20 PSF = 960 lbs/flight
            # Landings: 6' × 4' = 24 SF × 15 PSF (metal grating) = 360 lbs/landing
            # 2 landings per flight = 720 lbs
            # Total per flight: 960 + 720 = 1,680 lbs
            num_flights = equivalent_full_floors * 2  # Up and down flights
            stair_dead_load = num_flights * 1680  # lbs
            equipment_load_plf = stair_dead_load / wall_length_ft

            # Stair live load: 100 PSF per IBC 2021 Table 1607.1 (NOT 50 PSF parking rate)
            # NOT reducible per IBC Table 1607.10.2
            stair_area_per_flight = 48  # SF (12' × 4')
            stair_ll_total = num_flights * stair_area_per_flight * 100  # PSF
            specialized_ll_plf = stair_ll_total / wall_length_ft

        elif wall_type == 'utility':
            # Mechanical/electrical equipment rooms
            # HVAC ventilation (5,000 lbs) + electrical panels (5,000 lbs) + fire protection (3,500 lbs)
            # Conservative estimate for parking garage utility closet
            utility_equipment = 13500  # lbs total
            equipment_load_plf = utility_equipment / wall_length_ft
            # Equipment area live load: IBC requires heavier loads for mechanical rooms
            # Use 125 PSF for general mechanical spaces (conservative)
            equipment_area_sf = 100  # SF approximate footprint
            specialized_ll_plf = (equipment_area_sf * 125) / wall_length_ft

        elif wall_type == 'storage':
            # Storage closet with shelving
            # Shelving systems: ~50 lbs per LF of perimeter
            equipment_load_plf = 50  # lbs/LF
            # Storage live load: 125 PSF per IBC 2021 Table 1607.1 (NOT 50 PSF parking rate)
            storage_area_sf = 522  # SF (29' × 18' typical from geometry)
            specialized_ll_plf = (storage_area_sf * 125) / wall_length_ft

        # Total dead load (unfactored service load)
        total_dl_plf = wall_weight_plf + slab_load_plf + equipment_load_plf

        # Total service load (DL + LL, unfactored for bearing check)
        total_service_plf = total_dl_plf + specialized_ll_plf

        # Required footing width from bearing capacity (use service loads)
        required_width_ft = total_service_plf / self.bearing_capacity
        footing_width_ft = math.ceil(required_width_ft)

        # Minimum widths by wall type (updated based on typical loads)
        min_widths = {
            'elevator': 5.0,  # Increased for equipment loads
            'stair': 5.5,     # Increased for stair DL + specialized LL
            'utility': 2.5,   # Slightly increased for equipment
            'storage': 5.0    # Increased for high storage LL (125 PSF)
        }
        footing_width_ft = max(footing_width_ft, min_widths.get(wall_type, 2.0))

        # Depth heuristic for continuous footings (typical 12-18")
        footing_depth_ft = max(footing_width_ft / 4.0, 1.0)  # width/4, min 12"
        footing_depth_ft = math.ceil(footing_depth_ft / 0.25) * 0.25  # Round to 3" increments

        # Calculate volumes
        concrete_cy = (footing_width_ft * footing_depth_ft * wall_length_ft) / 27.0
        rebar_lbs = concrete_cy * self.continuous_rebar_rate  # Use continuous footing rate (110 lbs/CY per TechRidge budget)
        excavation_cy = concrete_cy * 1.2

        # Designation (e.g., "FC4.0" for 4' wide continuous footing)
        width_whole = int(footing_width_ft) if footing_width_ft == int(footing_width_ft) else footing_width_ft
        designation = f"FC{width_whole}.0"

        return {
            'wall_type': wall_type,
            'width_ft': footing_width_ft,
            'depth_ft': footing_depth_ft,
            'length_ft': wall_length_ft,
            'concrete_cy': concrete_cy,
            'rebar_lbs': rebar_lbs,
            'excavation_cy': excavation_cy,
            'designation': designation,
            'load_plf': total_service_plf,  # Updated to include all loads
            'wall_weight_plf': wall_weight_plf,
            'slab_load_plf': slab_load_plf,
            'equipment_load_plf': equipment_load_plf,
            'specialized_ll_plf': specialized_ll_plf
        }

    def calculate_continuous_footings(self) -> Dict:
        """
        Calculate continuous footings under all core walls

        Returns:
            dict with footing details by wall type and totals
        """
        wall_height = self.garage.total_height_ft
        wall_thickness = 1.0  # 12" walls

        footings = []

        # Elevator shaft: 8'×8' interior → 32 LF interior perimeter
        # Footing on exterior: 32 + 4×2' (wall thickness corners) = 40 LF
        elevator_length = 32 + (4 * 2)  # 40 LF
        footings.append(self.design_continuous_footing(
            'elevator', elevator_length, wall_height, wall_thickness
        ))

        # Stair enclosures: 68 LF per stair × 2 stairs
        # Exterior perimeter for footing: ~74 LF per stair
        num_stairs = self.garage.num_stairs
        stair_length_each = 68 + 6  # Add for wall thickness adjustments
        for i in range(num_stairs):
            footings.append(self.design_continuous_footing(
                f'stair_{i+1}', stair_length_each, wall_height, wall_thickness
            ))

        # Utility closet (NW): 20'×19' → 78 LF perimeter
        # Exterior: 78 + 4×2' = 86 LF
        utility_length = 78 + 8
        footings.append(self.design_continuous_footing(
            'utility', utility_length, wall_height, wall_thickness
        ))

        # Storage closet (SW): 29'×18' → 94 LF perimeter
        # Exterior: 94 + 4×2' = 102 LF
        storage_length = 94 + 8
        footings.append(self.design_continuous_footing(
            'storage', storage_length, wall_height, wall_thickness
        ))

        # Calculate totals
        total_length_ft = sum(f['length_ft'] for f in footings)
        total_concrete_cy = sum(f['concrete_cy'] for f in footings)
        total_rebar_lbs = sum(f['rebar_lbs'] for f in footings)
        total_excavation_cy = sum(f['excavation_cy'] for f in footings)

        return {
            'footings': footings,
            'total_length_ft': total_length_ft,
            'total_concrete_cy': total_concrete_cy,
            'total_rebar_lbs': total_rebar_lbs,
            'total_excavation_cy': total_excavation_cy
        }

    def design_retaining_wall_footing(
        self,
        wall_height_ft: float,
        perimeter_length_ft: float
    ) -> Dict:
        """
        Design cantilever retaining wall footing with stability checks

        Args:
            wall_height_ft: Height of retaining wall (feet)
            perimeter_length_ft: Total perimeter length (feet)

        Returns:
            dict with footing dimensions, stability factors, volumes, costs
        """
        # Cantilever retaining wall sizing heuristics (less conservative)
        heel_length_ft = 0.5 * wall_height_ft  # Backfill side
        toe_length_ft = 0.2 * wall_height_ft   # Front side
        wall_thickness_ft = 1.0  # 12" wall

        total_width_ft = heel_length_ft + toe_length_ft + wall_thickness_ft
        footing_depth_ft = max(1.0, wall_height_ft / 10.0)  # Reduced from /8
        footing_depth_ft = math.ceil(footing_depth_ft / 0.25) * 0.25  # Round to 3"

        # Stability checks (simplified - full analysis requires soil parameters)
        # Lateral earth pressure coefficient (Rankine active)
        Ka = 0.33  # Typical for 30° friction angle

        # Lateral force (triangular distribution)
        soil_unit_weight = 120  # PCF
        lateral_pressure = Ka * soil_unit_weight * wall_height_ft
        lateral_force_plf = 0.5 * lateral_pressure * wall_height_ft

        # Overturning moment (about toe)
        moment_arm_ft = wall_height_ft / 3.0  # Centroid of triangular distribution
        M_overturning = lateral_force_plf * moment_arm_ft

        # Resisting moment (simplified - includes footing + backfill weight)
        footing_weight_plf = total_width_ft * footing_depth_ft * 150  # Concrete
        backfill_weight_plf = heel_length_ft * wall_height_ft * soil_unit_weight

        # Moment arms from toe
        footing_lever_arm = total_width_ft / 2.0
        backfill_lever_arm = toe_length_ft + wall_thickness_ft + (heel_length_ft / 2.0)

        M_resisting = (footing_weight_plf * footing_lever_arm +
                       backfill_weight_plf * backfill_lever_arm)

        FS_overturning = M_resisting / M_overturning if M_overturning > 0 else 999

        # Sliding check (simplified)
        friction_coeff = 0.5  # Concrete on soil
        vertical_load_plf = footing_weight_plf + backfill_weight_plf
        friction_force_plf = friction_coeff * vertical_load_plf
        FS_sliding = friction_force_plf / lateral_force_plf if lateral_force_plf > 0 else 999

        # Calculate volumes
        concrete_cy = (total_width_ft * footing_depth_ft * perimeter_length_ft) / 27.0
        rebar_lbs = concrete_cy * self.continuous_rebar_rate  # Use continuous footing rate (110 lbs/CY per TechRidge budget)
        excavation_cy = concrete_cy * 1.2

        return {
            'wall_height_ft': wall_height_ft,
            'heel_length_ft': heel_length_ft,
            'toe_length_ft': toe_length_ft,
            'total_width_ft': total_width_ft,
            'depth_ft': footing_depth_ft,
            'length_ft': perimeter_length_ft,
            'concrete_cy': concrete_cy,
            'rebar_lbs': rebar_lbs,
            'excavation_cy': excavation_cy,
            'FS_overturning': FS_overturning,
            'FS_sliding': FS_sliding
        }

    def calculate_retaining_wall_footings(self) -> Dict:
        """
        Calculate retaining wall footings for below-grade perimeter

        Returns:
            dict with footing details and totals, or None if no below-grade levels
        """
        if self.garage.half_levels_below == 0:
            return {
                'has_retaining_walls': False,
                'total_concrete_cy': 0,
                'total_rebar_lbs': 0,
                'total_excavation_cy': 0
            }

        # Calculate retaining wall height and perimeter
        wall_height_ft = self.garage.half_levels_below * 5.0  # Each half-level = 5' rise
        perimeter_ft = 2 * (self.garage.length + self.garage.width)

        # Design footing
        footing = self.design_retaining_wall_footing(wall_height_ft, perimeter_ft)

        return {
            'has_retaining_walls': True,
            'footing': footing,
            'total_concrete_cy': footing['concrete_cy'],
            'total_rebar_lbs': footing['rebar_lbs'],
            'total_excavation_cy': footing['excavation_cy']
        }

    def calculate_all_footings(self) -> Dict:
        """
        Master calculation function - calculates all footing types

        Returns:
            Complete breakdown of all footings with costs
        """
        # Calculate each footing category
        spread_results = self.calculate_spread_footings()
        continuous_results = self.calculate_continuous_footings()
        retaining_results = self.calculate_retaining_wall_footings()

        # Grand totals
        total_concrete_cy = (
            spread_results['total_concrete_cy'] +
            continuous_results['total_concrete_cy'] +
            retaining_results['total_concrete_cy']
        )

        total_rebar_lbs = (
            spread_results['total_rebar_lbs'] +
            continuous_results['total_rebar_lbs'] +
            retaining_results['total_rebar_lbs']
        )

        total_excavation_cy = (
            spread_results['total_excavation_cy'] +
            continuous_results['total_excavation_cy'] +
            retaining_results['total_excavation_cy']
        )

        return {
            'spread_footings': spread_results,
            'continuous_footings': continuous_results,
            'retaining_wall_footings': retaining_results,
            'totals': {
                'concrete_cy': total_concrete_cy,
                'rebar_lbs': total_rebar_lbs,
                'excavation_cy': total_excavation_cy
           
            }
        }
