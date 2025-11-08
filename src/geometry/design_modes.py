"""
Design mode configuration for parking garage ramp systems

This module defines the two fundamental ramp system architectures and
provides logic for automatically selecting the optimal system based on
building geometry.
"""

from enum import Enum


class RampSystemType(Enum):
    """
    Parking garage ramp system architectures

    SPLIT_LEVEL_DOUBLE: Current system with two interleaved helical ramps
    SINGLE_RAMP_FULL: New system with one ramp bay and full-height floors
    """
    SPLIT_LEVEL_DOUBLE = "split_level_double"
    SINGLE_RAMP_FULL = "single_ramp_full"

    @staticmethod
    def determine_optimal(length: float, num_bays: int) -> 'RampSystemType':
        """
        Determine optimal ramp system based on building geometry

        Args:
            length: Building length in feet
            num_bays: Number of parking bays (2-7)

        Returns:
            Recommended ramp system type

        Logic:
            Single-ramp requires sufficient length for proper ramp geometry:
            - 6.67% slope (IBC maximum for parking on ramps)
            - 9.0' vertical rise per full floor
            - Ramp length needed: 9.0' / 0.0667 = 135'
            - Plus turn zones: 2 × 48' = 96'
            - Plus transitions: ~20'
            - Total minimum: 135' + 96' + 20' = 251'

            Threshold set at 250' for safety margin.

        Benefits of single-ramp at lengths ≥250':
            - 15-20% cost reduction (fewer elevator stops, stairs, barriers)
            - 15% height reduction (9' vs 10.656' floor-to-floor)
            - Simpler construction (no center beams/columns/curbs)
        """
        if length >= SINGLE_RAMP_MIN_LENGTH:
            return RampSystemType.SINGLE_RAMP_FULL
        else:
            return RampSystemType.SPLIT_LEVEL_DOUBLE


# ============================================================================
# RAMP SYSTEM CONSTANTS
# ============================================================================

# Minimum length for single-ramp system (feet)
SINGLE_RAMP_MIN_LENGTH = 250

# Ramp slopes
RAMP_SLOPE_SPLIT_LEVEL = 0.05    # 5% (current split-level system)
RAMP_SLOPE_SINGLE_RAMP = 0.0667  # 6.67% (IBC max for parking on ramps - Section 406.4.3/4)

# Floor-to-floor heights
FLOOR_TO_FLOOR_SPLIT = 10.656    # feet (10' 7-7/8" - current split-level)
FLOOR_TO_FLOOR_SINGLE = 9.0      # feet (optimized for single-ramp efficiency)

# Derived level heights
LEVEL_HEIGHT_SPLIT = FLOOR_TO_FLOOR_SPLIT / 2  # 5.328' per half-level
LEVEL_HEIGHT_SINGLE = FLOOR_TO_FLOOR_SINGLE     # 9.0' per full floor


def get_ramp_config(ramp_system: RampSystemType) -> dict:
    """
    Get configuration parameters for a ramp system

    Args:
        ramp_system: The ramp system type

    Returns:
        Dictionary with ramp configuration:
        - floor_to_floor: Floor-to-floor height
        - level_height: Vertical rise per parking level
        - ramp_slope: Ramp slope (decimal, e.g., 0.05 = 5%)
        - is_half_level: Whether system uses half-levels
    """
    if ramp_system == RampSystemType.SPLIT_LEVEL_DOUBLE:
        return {
            'floor_to_floor': FLOOR_TO_FLOOR_SPLIT,
            'level_height': LEVEL_HEIGHT_SPLIT,
            'ramp_slope': RAMP_SLOPE_SPLIT_LEVEL,
            'is_half_level': True
        }
    else:  # SINGLE_RAMP_FULL
        return {
            'floor_to_floor': FLOOR_TO_FLOOR_SINGLE,
            'level_height': LEVEL_HEIGHT_SINGLE,
            'ramp_slope': RAMP_SLOPE_SINGLE_RAMP,
            'is_half_level': False
        }
