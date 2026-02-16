"""
Mapping utilities for creating GeoJSON-based map layers in Dash dashboards.

This module provides dataclasses for building GeoJSON structures from pandas DataFrames.
"""

import dash_leaflet as dl
import base64
import json
import pandas as pd
import requests
import urllib.parse

from dash import html
from dash import no_update
from dataclasses import dataclass, field
from typing import Any, Dict, List

import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)
from arcgis.geocoding import geocode, suggest, Geocoder  # noqa: E402


__all__ = [
    "GeoJsonProperty",
    "GeoJson",
    "create_arcgis_layer",
    "get_station_symbol_svg",
    "get_hq_symbol_svg",
    "create_map_legend",
    "create_legend_item",
    "create_legend_section",
    "get_geocode_icon",
    "handle_address_geocoding",
    "get_address_suggestions",
]


MIN_ADDRESS_LENGTH = 5


def handle_address_geocoding(
    selected_json: str,
    geocoder: Geocoder,
    icon: Any = None,
    zoom_level: int = 15,
) -> tuple:
    """
    Geocode a selected address JSON and return a viewport and marker.

    Args:
        selected_json: JSON string containing 'address' and 'magic_key'
        gis: Authenticated arcgis.gis.GIS instance
        icon: Optional dash-leaflet icon configuration
        zoom_level: Zoom level for the returned viewport

    Returns:
        A tuple of (viewport_dict, marker_list)
    """
    if not selected_json:
        return no_update, []

    try:
        data = json.loads(selected_json)
        address_text = data.get("address")
        magic_key = data.get("magic_key")

        # Perform geocode using the first available geocoder
        results = geocode(
            address_text,
            magic_key=magic_key,
            geocoder=geocoder,
            source_country="USA",
        )

        if not results:
            return no_update, no_update

        loc = results[0]["location"]
        viewport = {"center": [loc["y"], loc["x"]], "zoom": zoom_level}

        marker = dl.Marker(
            position=[loc["y"], loc["x"]],
            icon=icon,
            children=[dl.Tooltip(f"GeocodedAddress: {address_text}")],
        )

        return viewport, [marker]
    except Exception as e:
        print(f"Error geocoding address: {e}")
        return no_update, no_update


def _ago_suggestions_to_dash_options(
    suggest_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Converts address suggestions from ArcGIS to Dash dropdown options.

    Values are JSON-serialized to satisfy dcc.Dropdown's requirement for primitive types.
    """
    import json

    suggestions: List[Dict[str, Any]] = suggest_result.get("suggestions", [])
    options = []
    for s in suggestions:
        text = s.get("text")
        value = {"address": text, "magic_key": s.get("magicKey")}

        # Unclear to me why this serialization is required here but not for other option values...
        options.append({"label": text, "value": json.dumps(value)})
    return options


def get_address_suggestions(
    search_value: str, geocoder: Geocoder, category: str = "Address"
) -> List[Dict[str, Any]]:
    """Get address suggestions from ArcGIS for a search value."""
    if not search_value or len(search_value) < MIN_ADDRESS_LENGTH:
        return []

    try:
        results = suggest(
            text=search_value,
            category=category,
            geocoder=geocoder,
            country_code="USA",
        )

        return _ago_suggestions_to_dash_options(results)
    except Exception as e:
        print(f"Error getting address suggestions: {e}")
        return []


def create_legend_item(
    label: str, color: str = None, svg: str = None, style: Dict[str, Any] = None
) -> Any:
    """Create a single item for a map legend.

    Args:
        label: The text label for the item
        color: Optional hex color for a circular marker
        svg: Optional raw SVG string to use as an icon
        style: Optional style overrides for the item container
    """
    icon = None
    if svg:
        encoded_svg = urllib.parse.quote(svg)
        icon = html.Div(
            html.Img(
                src=f"data:image/svg+xml,{encoded_svg}",
                style={"display": "block", "maxWidth": "100%", "maxHeight": "100%"},
            ),
            style={
                "width": "24px",
                "height": "24px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "marginRight": "8px",
            },
        )
    elif color:
        icon = html.Div(
            html.Span(
                style={
                    "backgroundColor": color,
                    "width": "12px",
                    "height": "12px",
                    "borderRadius": "50%",
                    "display": "inline-block",
                }
            ),
            style={
                "width": "24px",
                "height": "24px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "marginRight": "8px",
            },
        )

    return html.Div(
        [icon, html.Span(label, style={"fontSize": "0.9em"})],
        style={
            "display": "flex",
            "alignItems": "center",
            "marginBottom": "2px",
            **(style or {}),
        },
    )


def create_legend_section(title: str = None, items: List[Any] = None) -> List[Any]:
    """Create a section of legend items with an optional title.

    Args:
        title: Optional bold title for the section
        items: List of legend item components
    """
    section = []
    if title:
        section.append(
            html.B(
                title,
                style={"display": "block", "marginBottom": "1px", "fontSize": "1em"},
            )
        )
    if items:
        section.extend(items)
    return section


def create_map_legend(sections: List[List[Any]], style: Dict[str, Any] = None) -> Any:
    """Create a complete map legend from multiple sections.

    Args:
        sections: A list of lists, where each inner list is a section of components
        style: Optional style overrides for the legend container
    """
    content = []
    for i, section in enumerate(sections):
        if i > 0:
            content.append(html.Hr(style={"margin": "10px 0"}))
        content.extend(section)

    default_style = {
        "position": "absolute",
        "bottom": "20px",
        "left": "20px",
        "zIndex": 1000,
        "backgroundColor": "rgba(255, 255, 255, 0.9)",
        "padding": "12px",
        "borderRadius": "4px",
        "boxShadow": "0 1px 5px rgba(0,0,0,0.2)",
        "lineHeight": "1",
        "color": "#333",
        "pointerEvents": "none",
    }

    return html.Div(content, style={**default_style, **(style or {})})


def get_station_symbol_svg(
    fill_color: str = "#800000",
    stroke_color: str = "#b00202",
    stroke_width: int = 4,
    fill_opacity: float = 1.0,
    size: int = 30,
) -> str:
    """Return the SVG string for a fire station symbol.

    The symbol maintains a 2:3 aspect ratio (width:height) based on the provided size (height).
    """
    height = size
    width = int(size * (2 / 3))
    return f"""
        <svg width="{width}" height="{height}" viewBox="0 0 100 150" xmlns="http://www.w3.org/2000/svg">
            <path d="M50 0 L100 75 L50 150 L0 75 Z" fill="{fill_color}" fill-opacity="{fill_opacity}" stroke="{stroke_color}" stroke-width="{stroke_width}"/>
        </svg>
    """.strip()


def get_hq_symbol_svg(
    stroke_color: str = "#3020a8",
    stroke_width: int = 15,
    fill_opacity: float = 0.0,
    size: int = 24,
) -> str:
    """Return the SVG string for a department headquarters symbol."""
    return f"""
        <svg width="{size}" height="{size}" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <circle cx="50" cy="50" r="35" stroke="{stroke_color}" stroke-width="{stroke_width}" fill="white" fill-opacity="{fill_opacity}" />
        </svg>
    """.strip()


def get_geocode_icon(
    color: str = "#7A76F7",
    size: int = 24,
    as_dl_icon: bool = False,
) -> str | dict:
    """Return the SVG string or a dash-leaflet icon for a geocoding result.

    Args:
        color: Stroke color for the inner X shape.
        size: Width and height of the symbol.
        as_dl_icon: If True, returns a dict formatted for dash-leaflet Marker icon.
                   Otherwise, returns the raw SVG string.
    """
    svg = f"""
        <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="2" y="2" width="20" height="20" stroke="gray" stroke-width="1.5" stroke-dasharray="3,3" fill="none" opacity="0.6" />
        <path d="M18 6L6 18M6 6l12 12" stroke="{color}" stroke-width="3" opacity="0.7" stroke-linecap="round" />
        </svg>
    """.strip()

    if as_dl_icon:
        encoded = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
        return {
            "iconUrl": f"data:image/svg+xml;base64,{encoded}",
            "iconSize": [size, size],
            "iconAnchor": [size // 2, size // 2],
        }

    return svg


@dataclass
class GeoJsonProperty:
    """Represents a single property in a GeoJSON feature.

    Attributes:
        name: The property key name (must match a column name in the DataFrame)
        default: Default value to use if the value is missing/None in the DataFrame
    """

    name: str
    default: Any = None


@dataclass
class GeoJson:
    """Represents a GeoJSON FeatureCollection structure.

    Attributes:
        points_df: DataFrame with x (longitude) and y (latitude) columns
        properties: List of GeoJsonProperty objects to include in each feature
    """

    points_df: pd.DataFrame
    properties: List[GeoJsonProperty] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the GeoJson object to a GeoJSON FeatureCollection dictionary."""
        if self.points_df.empty:
            return {
                "type": "FeatureCollection",
                "features": [],
            }

        features = []
        for row in self.points_df.itertuples(index=False):
            coordinates = [getattr(row, "x", 0.0), getattr(row, "y", 0.0)]

            properties = {}
            for prop in self.properties:
                row_value = getattr(row, prop.name, prop.default)
                properties[prop.name] = row_value

            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": coordinates},
                    "properties": properties,
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
        }


def create_arcgis_layer(
    server_url: str,
    layer_id: int,
    where_clause: str,
    out_fields: str,
    component_id: str,
    **kwargs,
) -> Any:
    """Fetch data from ArcGIS and create a dash-leaflet GeoJSON layer."""
    import dash_leaflet as dl

    params = {
        "where": where_clause,
        "outFields": out_fields,
        "f": "geojson",
        "returnGeometry": "true",
    }
    url = f"{server_url.rstrip('/')}/{layer_id}/query"

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if "features" not in data or not data["features"]:
            return None
        return dl.GeoJSON(data=data, id=component_id, **kwargs)
    except Exception:
        return None
