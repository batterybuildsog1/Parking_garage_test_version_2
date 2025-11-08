"""
Geometry package for split-level parking garage analysis

This package provides modular geometry calculations for parametric parking garage design.

Main Classes:
    - SplitLevelParkingGarage: Main facade class (from parent geometry.py for now)
    - DiscreteLevelCalculator: Calculate individual level floor areas
    - CoreBlockage: Represent corner cores that block parking
    - ParkingSection: Represent parking rows/strips
    - ParkingLayout: 2D parking layout analysis (from parent geometry.py for now)

Architecture:
    The package is organized into focused modules, each handling one aspect of
    the garage geometry. This improves testability, maintainability, and clarity.
"""

# Phase 1 exports (newly extracted modules)
from .level_calculator import DiscreteLevelCalculator
from .core_elements import CoreBlockage, ParkingSection

# Phase 2 exports
from .parking_layout import ParkingLayout

# Legacy exports note:
# SplitLevelParkingGarage and load_cost_database are still in
# the parent garage.py file and will be extracted in later refactoring phases.
# For now, import these directly: from garage import SplitLevelParkingGarage

__all__ = [
    # Phase 1: New modular classes
    'DiscreteLevelCalculator',
    'CoreBlockage',
    'ParkingSection',

    # Phase 2: Parking layout
    'ParkingLayout',
]
