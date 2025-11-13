from typing import Dict
import math


def _alpha_s_for_column(y_line_type: str, x: float, y: float, length: float, width: float) -> int:
    """
    Location factor approximations for slab punching:
    - corner: 20
    - edge: 30
    - interior: 40
    Approximate corner if near both length and width edges.
    """
    tol = 1.0  # feet
    near_north = abs(x - length) <= tol
    near_south = abs(x - 0.0) <= tol
    near_east = abs(y - width) <= tol
    near_west = abs(y - 0.0) <= tol
    if (near_north or near_south) and (near_east or near_west):
        return 20  # corner
    if y_line_type == 'perimeter' or near_east or near_west or near_north or near_south:
        return 30  # edge
    return 40  # interior


def compute_slab_punching_for_level(
    *,
    fc_psi: float,
    slab_thickness_in: float,
    column_width_in: float,
    column_depth_in: float,
    y_line_type: str,
    column_x_ft: float,
    column_y_ft: float,
    building_length_ft: float,
    building_width_ft: float,
    factored_reaction_lb: float
) -> Dict:
    """
    Compute punching shear capacity vs demand at a slab-column joint for a specific level.
    Uses ACI 318-19 style equations, simplified.
    """
    cover_in = 1.0  # effective depth approximation: #7 bars, 1" to centroid
    d_inches = max(slab_thickness_in - cover_in, 4.0)

    # Critical perimeter at d/2 from column face
    d_ft = d_inches / 12.0
    col_w_ft = column_width_in / 12.0
    col_d_ft = column_depth_in / 12.0
    bo_ft = 2 * (col_w_ft + d_ft) + 2 * (col_d_ft + d_ft)
    bo_in = bo_ft * 12.0

    # Size effect factor
    lambda_s = math.sqrt(2.0 / (1.0 + 0.004 * d_inches))

    # Column aspect ratio
    beta = max(column_depth_in, column_width_in) / max(1.0, min(column_depth_in, column_width_in))

    # Location factor alpha_s
    alpha_s = _alpha_s_for_column(y_line_type, column_x_ft, column_y_ft, building_length_ft, building_width_ft)

    # Nominal punching shear stress (psi) per ACI 22.6.5.2 (simplified envelope)
    vc_psi = min(
        2 + 4 / beta,
        alpha_s * d_inches / bo_in + 2,
        4
    ) * lambda_s * math.sqrt(max(fc_psi, 2500.0))

    phi = 0.75  # shear strength reduction factor
    area_in2 = bo_in * d_inches
    phi_vc_lb = phi * vc_psi * area_in2

    vu_lb = max(0.0, factored_reaction_lb)
    utilization = (vu_lb / phi_vc_lb) if phi_vc_lb > 0 else 0.0

    requires_stud_rails = utilization > 1.0
    return {
        'phi_vc_lb': phi_vc_lb,
        'vu_lb': vu_lb,
        'utilization': utilization,
        'requires_stud_rails': requires_stud_rails,
        'd_inches': d_inches,
        'alpha_s': alpha_s
    }


