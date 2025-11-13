from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
from matplotlib.figure import Figure


def _init_figure(title: str) -> Figure:
    fig: Figure = plt.figure(figsize=(10, 6))
    ax = fig.add_subplot(111)
    ax.set_aspect("equal")
    ax.set_title(title)
    ax.set_xlabel("Length (ft)")
    ax.set_ylabel("Width (ft)")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    return fig


def create_overview_diagram_figure(garage: Any, layout: Any, opt_result: Optional[Dict]) -> Figure:
    """
    Minimal overview diagram to keep the 2D Plans tab functional.
    Draws the building footprint and annotates basic metrics.
    """
    fig = _init_figure("Overview (All Levels)")
    ax = fig.axes[0]

    # Building footprint rectangle
    rect = plt.Rectangle((0, 0), garage.length, garage.width, fill=False, linewidth=2, color="black")
    ax.add_patch(rect)

    # Basic annotations
    ax.text(
        5,
        garage.width - 5,
        f"Total Stalls: {garage.total_stalls}\nTotal GSF: {garage.total_gsf:,.0f} SF",
        va="top",
        ha="left",
        fontsize=10,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
    )

    # Axis limits
    ax.set_xlim(0, max(garage.length, 10))
    ax.set_ylim(0, max(garage.width, 10))

    return fig


def create_per_level_diagram_figure(
    garage: Any, layout: Any, level_name: str, opt_result: Optional[Dict]
) -> Figure:
    """
    Minimal per-level diagram to keep the 2D Plans tab functional.
    Draws the building footprint and labels the selected level.
    """
    fig = _init_figure(f"Level Plan – {level_name}")
    ax = fig.axes[0]

    # Building footprint rectangle
    rect = plt.Rectangle((0, 0), garage.length, garage.width, fill=False, linewidth=2, color="black")
    ax.add_patch(rect)

    # Level label
    ax.text(
        garage.length * 0.5,
        garage.width * 0.5,
        level_name,
        va="center",
        ha="center",
        fontsize=16,
        weight="bold",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
    )

    # Axis limits
    ax.set_xlim(0, max(garage.length, 10))
    ax.set_ylim(0, max(garage.width, 10))

    return fig

