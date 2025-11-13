import pytest

from src.garage import create_parking_garage, SplitLevelParkingGarage, ParkingGarage, compute_width_ft
from src.geometry.design_modes import RampSystemType


def test_factory_auto_select_split_level():
    g = create_parking_garage(length=210, half_levels_above=8, half_levels_below=0, num_bays=2)
    assert g.ramp_system == RampSystemType.SPLIT_LEVEL_DOUBLE


def test_factory_auto_select_single_ramp():
    g = create_parking_garage(length=250, half_levels_above=8, half_levels_below=0, num_bays=2)
    assert g.ramp_system == RampSystemType.SINGLE_RAMP_FULL


def test_factory_override_respected():
    g = create_parking_garage(
        length=210,
        half_levels_above=8,
        half_levels_below=0,
        num_bays=2,
        ramp_system=RampSystemType.SINGLE_RAMP_FULL
    )
    assert g.ramp_system == RampSystemType.SINGLE_RAMP_FULL


def test_alias_parity_width():
    # Direct vs factory with the same selected system
    direct = SplitLevelParkingGarage(length=210, half_levels_above=8, half_levels_below=0, num_bays=3)
    via_factory = create_parking_garage(
        length=210, half_levels_above=8, half_levels_below=0, num_bays=3, ramp_system=direct.ramp_system
    )
    assert round(direct.width, 3) == round(via_factory.width, 3)
    # Also confirm compute_width_ft agrees
    assert round(via_factory.width, 3) == round(compute_width_ft(3), 3)



