"""
utils/helpers.py
----------------
General helper functions used across the pipeline:
- JSON serialization for numpy types
- Color palette management
- Formatted number helpers
- Chart theme configuration
"""

import json
import numpy as np
import pandas as pd
from typing import Any


BRAND_COLORS = {
    "Safari": "#FF6B35",
    "Skybags": "#4ECDC4",
    "American Tourister": "#1A1A2E",
    "VIP": "#E74C3C",
    "Aristocrat": "#8E44AD",
    "Nasher Miles": "#27AE60",
}

PLOTLY_THEME = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"family": "Syne, sans-serif", "color": "#E8E3D5"},
    "xaxis": {"gridcolor": "rgba(232,227,213,0.1)", "zerolinecolor": "rgba(232,227,213,0.2)"},
    "yaxis": {"gridcolor": "rgba(232,227,213,0.1)", "zerolinecolor": "rgba(232,227,213,0.2)"},
    "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
}


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types for API responses."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return super().default(obj)


def safe_json(data: Any) -> str:
    """Serialize data to JSON string handling numpy types."""
    return json.dumps(data, cls=NumpyEncoder)


def format_inr(amount: float) -> str:
    """Format a number as Indian Rupees string."""
    if pd.isna(amount):
        return "N/A"
    return f"₹{amount:,.0f}"


def get_brand_color(brand: str) -> str:
    """Return brand-specific color or a fallback."""
    return BRAND_COLORS.get(brand, "#95A5A6")


def get_all_brand_colors(brands: list) -> list:
    """Return ordered list of colors for given brands."""
    return [get_brand_color(b) for b in brands]


def sentiment_to_label(score: float) -> str:
    """Convert numeric sentiment score to human-readable label."""
    if score >= 0.7:
        return "Very Positive"
    elif score >= 0.55:
        return "Positive"
    elif score >= 0.45:
        return "Neutral"
    elif score >= 0.3:
        return "Negative"
    return "Very Negative"


def sentiment_to_emoji(score: float) -> str:
    """Map sentiment score to emoji indicator."""
    if score >= 0.7:
        return "🟢"
    elif score >= 0.55:
        return "🟡"
    elif score >= 0.45:
        return "🟠"
    return "🔴"


def apply_plotly_theme(fig, title: str = "") -> object:
    """Apply consistent dark theme to a Plotly figure."""
    fig.update_layout(
        title={"text": title, "font": {"size": 14, "color": "#E8E3D5"}},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,13,20,0.6)",
        font={"family": "Syne, sans-serif", "color": "#E8E3D5"},
        margin={"l": 50, "r": 20, "t": 50, "b": 40},
        legend={"bgcolor": "rgba(0,0,0,0)", "bordercolor": "rgba(255,255,255,0.1)"},
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)")
    return fig