"""Style and theme configuration for NERIS dashboards."""

from typing import List, Dict, Any

# TODO these shouldn't need to be externalized
__all__ = [
    "DEFAULT_COLOR_SEQUENCE",
    "DEFAULT_INCIDENT_TYPE_COLORS",
    "DEFAULT_LOCATION_USE_COLORS",
    "BUTTON_BASE_STYLE",
    "BUTTON_VARIANT_STYLES",
    "SMALL_ACTION_BUTTON_STYLE",
    "BASE_INFO_ICON_STYLE",
    "CARD_HEADER_STYLE",
    "DEFAULT_SPINNER_CHART",
    "DEFAULT_SPINNER_METRIC",
    "FF_COLOR",
    "NONFF_COLOR",
]


# Default qualitative color sequence for general hierarchical charts
DEFAULT_COLOR_SEQUENCE: List[str] = [
    "#FF6B6B",
    "#4ECDC4",
    "#45B7D1",
    "#FFA07A",
    "#98D8C8",
    "#F7DC6F",
    "#BB8FCE",
    "#85C1E2",
]

# Default color maps for common hierarchical dimensions
DEFAULT_INCIDENT_TYPE_COLORS: dict[str, str] = {
    "FIRE": "#c42b47",  # Red
    "MEDICAL": "#997b02",  # Gold
    "HAZSIT": "#4ECDC4",  # Teal
    "RESCUE": "#9302a6",  # Purple
    "NOEMERG": "#038c6a",  # Green
    "LAWENFORCE": "#047a94",  # Blue
    "PUBSERV": "#BF6717",  # "Mango Tango" per the style guide
}

DEFAULT_LOCATION_USE_COLORS: dict[str, str] = {
    "AGRICULTURE_STRUCT": "#8d6e63",  # Brown
    "ASSEMBLY": "#ec407a",  # Pink
    "COMMERCIAL": "#5c6bc0",  # Indigo
    "EDUCATION": "#ffa726",  # Orange
    "GOVERNMENT": "#26a69a",  # Teal/Cyan
    "INDUSTRIAL": "#78909c",  # Blue Grey
    "HEALTH_CARE": "#66bb6a",  # Light Green
    "RESIDENTIAL": "#42a5f5",  # Blue
    "UNCLASSIFIED": "#bdbdbd",  # Grey
    "UTILITY_MISC": "#26c6da",  # Cyan
    "STORAGE": "#7e57c2",  # Deep Purple
    "ROADWAY_ACCESS": "#607d8b",  # Slate
    "OUTDOOR": "#9ccc65",  # Light Green
    "OUTDOOR_INDUSTRIAL": "#546e7a",  # Dark Slate
}

BUTTON_BASE_STYLE: Dict[str, str] = {
    "width": "100%",
    "padding": "10px",
    "border": "none",
    "borderRadius": "4px",
    "cursor": "pointer",
    "fontSize": "0.9rem",
    "fontWeight": "bold",
    "marginBottom": "15px",
}

BUTTON_VARIANT_STYLES: Dict[str, Dict[str, str]] = {
    "default": {
        "backgroundColor": "#b9c3cb",
        "color": "white",
        "padding": "8px 12px",
        "fontSize": "0.85rem",
        "fontWeight": "500",
    },
    "primary": {
        "backgroundColor": "#007bff",
        "color": "white",
    },
    "secondary": {
        "backgroundColor": "#6c757d",
        "color": "white",
    },
}

SMALL_ACTION_BUTTON_STYLE: Dict[str, str] = {
    "backgroundColor": "#b9c3cb",
    "color": "white",
    "fontWeight": "500",
    "border": "none",
    "borderRadius": "4px",
    "padding": "2px 8px",
    "fontSize": "0.7rem",
    "cursor": "pointer",
    "width": "auto",
}

BASE_INFO_ICON_STYLE: Dict[str, str] = {
    "color": "#adb5bd",
    "cursor": "help",
    "fontSize": "0.8em",
}

CARD_HEADER_STYLE: Dict[str, str] = {
    "fontWeight": "bold",
    "margin": "0 0 15px 0",
}

DEFAULT_SPINNER_CHART: Dict[str, Any] = {
    "type": "cube",
    "color": "#7b859e",
    # add delays to try to prevent "blinking" effect as things settle
    "delay_show": 500,
    "delay_hide": 500,
}

DEFAULT_SPINNER_METRIC: Dict[str, Any] = {
    "type": "dot",
    "color": "#7b859e",
    # add delays to try to prevent "blinking" effect as things settle
    "delay_show": 500,
    "delay_hide": 500,
}


FF_COLOR = "#c95d26"
NONFF_COLOR = "#21b8a4"
