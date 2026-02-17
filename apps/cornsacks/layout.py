"""
Layout definition for the cornsacks dashboard using modern CSS Grid/Flexbox.
"""

from dash import html, dcc
import dash_leaflet as dl
import dash_design_kit as ddk
from tables import FILTER_REGISTRY
from neris_dash_common import (
    AuthError,
    create_auth_error_layout,
    create_metric_card,
    create_last_updated_badge,
    create_action_button,
    create_graph_card,
    SMALL_ACTION_BUTTON_STYLE,
    TOOLTIPS,
    CARD_HEADER_STYLE,
    RollingWindow,
)

from config import AUTH_MANAGER, BASEMAP_URL, MAX_MAP_POINTS


def create_filter_panel():
    """Create the filter panel component using DDK Card."""
    return ddk.Card(
        [
            html.H5("Incident Filters", style=CARD_HEADER_STYLE),
            html.Hr(),
            html.Details(
                [
                    html.Summary(
                        "See current filter state",
                        style={"fontSize": "0.8rem", "cursor": "pointer"},
                    ),
                    html.Div(
                        id="current-filters-display",
                        style={
                            "fontSize": "0.85rem",
                            "padding": "10px",
                            "backgroundColor": "#f8f9fa",
                            "border": "1px solid #dee2e6",
                            "borderRadius": "4px",
                            "marginTop": "10px",
                        },
                    ),
                ],
                style={"marginBottom": "15px"},
            ),
            html.Hr(),
            create_action_button(
                "Clear all filters",
                "clear-filters-button",
                variant="default",
            ),
            html.Label(
                "Aid Direction", style={"fontWeight": "bold", "marginBottom": "5px"}
            ),
            dcc.Dropdown(
                id="aid-direction-filter",
                options=[
                    {"label": "All", "value": "all"},
                    {"label": "Given", "value": "GIVEN"},
                    {"label": "Received", "value": "RECEIVED"},
                    {"label": "Both", "value": "BOTH"},
                    {"label": "Neither", "value": "NEITHER"},
                ],
                value="all",
                clearable=False,
            ),
            html.Hr(),
            html.Label(
                "Date Range", style={"fontWeight": "bold", "marginBottom": "5px"}
            ),
            ddk.Row(
                [
                    ddk.Block(
                        [
                            html.Label(
                                "Start",
                                style={"fontSize": "0.8rem", "marginBottom": "2px"},
                            ),
                            dcc.DatePickerSingle(
                                id="start-date-filter",
                                placeholder="Start Date",
                                display_format="YYYY-MM-DD",
                            ),
                        ],
                        width=6,
                    ),
                    ddk.Block(
                        [
                            html.Label(
                                "End",
                                style={"fontSize": "0.8rem", "marginBottom": "2px"},
                            ),
                            dcc.DatePickerSingle(
                                id="end-date-filter",
                                placeholder="End Date",
                                display_format="YYYY-MM-DD",
                            ),
                        ],
                        width=6,
                    ),
                ],
                style={"marginBottom": "10px"},
            ),
            html.Hr(),
            html.Label(
                "Department's State",
                style={"fontWeight": "bold", "marginBottom": "5px"},
            ),
            dcc.Dropdown(
                id="department-state-filter",
                options=[
                    {"label": "All States", "value": "all"},
                ],
                value="all",
                clearable=False,
                searchable=True,
            ),
            html.Hr(),
            html.Label(
                "Department",
                style={"fontWeight": "bold", "marginBottom": "5px"},
            ),
            dcc.Dropdown(
                id="neris-id-dept-filter",
                options=[
                    {"label": "All Departments", "value": "all"},
                ],
                # value="all",
                clearable=True,
                searchable=True,
                placeholder="Search for a department...",
            ),
            html.Hr(),
            html.Label(
                "Emerging Hazards", style={"fontWeight": "bold", "marginBottom": "5px"}
            ),
            dcc.Checklist(
                id="csst-hazard-filter",
                options=[{"label": "CSST hazards only", "value": "csst_hazard_only"}],
                value=[],
                style={"marginBottom": "15px"},
            ),
            dcc.Checklist(
                id="electric-hazard-filter",
                options=[
                    {
                        "label": "Electric hazards only",
                        "value": "electric_hazard_only",
                    }
                ],
                value=[],
                style={"marginBottom": "15px"},
            ),
            dcc.Checklist(
                id="powergen-hazard-filter",
                options=[
                    {
                        "label": "Powergen hazards only",
                        "value": "powergen_hazard_only",
                    }
                ],
                value=[],
                style={"marginBottom": "15px"},
            ),
            dcc.Checklist(
                id="medical-oxygen-hazard-filter",
                options=[
                    {
                        "label": "Medical oxygen hazards only",
                        "value": "medical_oxygen_hazard_only",
                    }
                ],
                value=[],
                style={"marginBottom": "15px"},
            ),
            html.Hr(),
            html.Hr(),
            html.H5("Export", style=CARD_HEADER_STYLE),
            create_action_button(
                "Download data as CSV",
                "download-data-button",
                variant="default",
            ),
            dcc.Download(id="download-data"),
        ],
        style={"position": "sticky", "top": "20px", "height": "fit-content"},
        card_hover=True,
    )


def create_app_layout():
    """Create the main app layout using DDK components."""
    try:
        AUTH_MANAGER.get_and_cache_permissions()
    except AuthError as e:
        return create_auth_error_layout(e.message)

    return [
        dcc.Store(
            id="filters",
            storage_type="session",
            data=FILTER_REGISTRY.get_ui_defaults(),
        ),
        dcc.Store(
            id="dept-layers-show-store",
            storage_type="session",
            data=True,
        ),
        ddk.Header(
            [
                ddk.Title("NERIS Incident Dashboard"),
                create_last_updated_badge(),
            ],
            style={
                "textAlign": "center",
                "marginBottom": "30px",
                "position": "relative",
            },
        ),
        ddk.Row(
            [
                # Filter panel
                ddk.Block(
                    create_filter_panel(), width=15, style={"marginBottom": "20px"}
                ),
                # The main event
                ddk.Block(
                    [
                        # Primary metrics row
                        ddk.Row(
                            [
                                ddk.Block(
                                    create_metric_card(
                                        "total-incidents-card",
                                        title_text="Total Incidents",
                                        tooltip_text=TOOLTIPS.METRICS.TOTAL_INCIDENTS,
                                    ),
                                    width=3,
                                ),
                                ddk.Block(
                                    create_metric_card(
                                        "total-unit-responses-card",
                                        title_text="Total Responding Units",
                                        tooltip_text=TOOLTIPS.METRICS.TOTAL_UNIT_RESPONSES,
                                    ),
                                    width=3,
                                ),
                                ddk.Block(
                                    create_metric_card(
                                        "duration-p90-card",
                                        title_text="Incident Duration: 90th Percentile",
                                        tooltip_text=TOOLTIPS.METRICS.INCIDENT_DURATION_P90,
                                    ),
                                    width=3,
                                ),
                            ],
                            style={"marginBottom": "20px"},
                        ),
                        # Incident types and day/hour heatmap
                        ddk.Row(
                            [
                                ddk.Block(
                                    create_graph_card(
                                        "Incident Types",
                                        [
                                            TOOLTIPS.DATA_DESCRIPTIONS.INCIDENT_TYPES,
                                            TOOLTIPS.CHART_GUIDANCE.CREATE_FILTERS.DRILL_DOWN,
                                            TOOLTIPS.CHART_GUIDANCE.ADJUST_FILTERS.HIERARCHICAL,
                                        ],
                                        dcc.Graph(
                                            id="incident-types-categorical-chart",
                                            className="chart-graph",
                                            config={
                                                "responsive": True,
                                                "displayModeBar": True,
                                                "displaylogo": False,
                                            },
                                        ),
                                        style={"height": "100%"},
                                        card_hover=True,
                                        modal=True,
                                        fullscreen=False,
                                        modal_config={"width": "80%", "height": "90%"},
                                    ),
                                    width=6,
                                    style={"marginBottom": "20px"},
                                ),
                                ddk.Block(
                                    create_graph_card(
                                        "Incidents by Day of Week and Hour",
                                        [
                                            TOOLTIPS.DATA_DESCRIPTIONS.CALL_CREATE_DAY_HOUR(),
                                            TOOLTIPS.CHART_GUIDANCE.CREATE_FILTERS.BOX_SELECT,
                                            TOOLTIPS.CHART_GUIDANCE.ADJUST_FILTERS.BOX_SELECT,
                                        ],
                                        dcc.Graph(
                                            id="day-hour-heatmap",
                                            className="chart-graph",
                                            config={
                                                "responsive": True,
                                                "displayModeBar": True,
                                                "displaylogo": False,
                                            },
                                        ),
                                        extra_header_controls=create_action_button(
                                            "Clear filter",
                                            "clear-heatmap-filter",
                                            variant="default",
                                            style={
                                                **SMALL_ACTION_BUTTON_STYLE,
                                                "verticalAlign": "middle",
                                                "marginBottom": "0",
                                            },
                                        ),
                                        style={"height": "100%"},
                                        card_hover=True,
                                        modal=True,
                                        fullscreen=False,
                                        modal_config={"width": "90%", "height": "90%"},
                                    ),
                                    width=6,
                                    style={"marginBottom": "20px"},
                                ),
                            ]
                        ),
                        # Map row
                        ddk.Row(
                            [
                                ddk.Block(
                                    create_graph_card(
                                        "Incident Locations",
                                        [
                                            TOOLTIPS.DATA_DESCRIPTIONS.SAMPLED_MAP_POINTS(
                                                MAX_MAP_POINTS
                                            ),
                                            "The 'Hide Department' / 'Show Department' button can be used to toggle the visibility of the department layers."
                                            "It will be greyed out unless a department is selected in the 'Department' filter.",
                                        ],
                                        [
                                            dl.Map(
                                                [
                                                    dl.TileLayer(url=BASEMAP_URL),
                                                    dl.LayerGroup(id="incident-points"),
                                                    dl.LayerGroup(id="search-marker"),
                                                    html.Div(
                                                        [
                                                            dcc.Dropdown(
                                                                id="address-dropdown",
                                                                options=[],
                                                                searchable=True,
                                                                placeholder="Search address...",
                                                                className="expanding-address-dropdown",
                                                                style={
                                                                    "pointerEvents": "auto",
                                                                },
                                                            ),
                                                        ],
                                                        className="leaflet-top leaflet-left",
                                                        style={
                                                            "pointerEvents": "none",
                                                            "marginTop": "20px",
                                                            "marginLeft": "55px",
                                                            "zIndex": 1000,
                                                        },
                                                    ),
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                "Zoom to points",
                                                                id="zoom-to-points-button",
                                                                title="Zoom to points",
                                                                className="leaflet-bar leaflet-control custom-map-control",
                                                                style={
                                                                    **SMALL_ACTION_BUTTON_STYLE,
                                                                    "pointerEvents": "auto",
                                                                    "padding": "5px 10px",
                                                                    "fontSize": "0.85rem",
                                                                    "marginBottom": "5px",
                                                                    "display": "block",
                                                                },
                                                            ),
                                                            html.Button(
                                                                "Hide stations",
                                                                id="dept-layers-toggle-button",
                                                                className="leaflet-bar leaflet-control custom-map-control",
                                                                disabled=True,
                                                                style={
                                                                    **SMALL_ACTION_BUTTON_STYLE,
                                                                    "pointerEvents": "auto",
                                                                    "padding": "5px 10px",
                                                                    "fontSize": "0.85rem",
                                                                    "marginBottom": "5px",
                                                                    "display": "block",
                                                                    "width": "100%",
                                                                },
                                                            ),
                                                        ],
                                                        className="leaflet-top leaflet-left",
                                                        style={
                                                            "pointerEvents": "none",
                                                            "marginTop": "80px",
                                                            "zIndex": 500,
                                                        },
                                                    ),
                                                ],
                                                id="incident-map",
                                                className="cornsacks-map",
                                                style={
                                                    "height": "500px",
                                                    "width": "100%",
                                                },
                                                center=[39.8283, -98.5795],
                                                zoom=4,
                                                viewport={
                                                    "center": [39.8283, -98.5795],
                                                    "zoom": 4,
                                                },
                                                attributionControl=False,
                                            ),
                                            html.Div(id="map-legend-container"),
                                        ],
                                        style={
                                            "height": "600px",
                                            "position": "relative",
                                        },
                                        card_hover=True,
                                        modal=True,
                                        fullscreen=True,
                                        spinner=False,
                                    ),
                                    width=100,
                                    style={"marginBottom": "20px"},
                                ),
                            ]
                        ),
                        # Trendline and location use charts
                        ddk.Row(
                            [
                                ddk.Block(
                                    create_graph_card(
                                        "Incidents by Call Date",
                                        [
                                            TOOLTIPS.DATA_DESCRIPTIONS.CALL_CREATE_BY_DAY,
                                            TOOLTIPS.DATA_DESCRIPTIONS.CALL_CREATE_BY_DAY_ROLLING_AVG(
                                                RollingWindow(7, False)
                                            ),
                                            TOOLTIPS.CHART_GUIDANCE.CREATE_FILTERS.BOX_SELECT,
                                            TOOLTIPS.CHART_GUIDANCE.ADJUST_FILTERS.BOX_SELECT_TRENDLINE_WITH_PICKERS,
                                        ],
                                        dcc.Graph(
                                            id="trendline-chart",
                                            className="chart-graph",
                                            config={"responsive": True},
                                        ),
                                        extra_header_controls=create_action_button(
                                            "Clear filter",
                                            "clear-trendline-filter",
                                            variant="default",
                                            style={
                                                **SMALL_ACTION_BUTTON_STYLE,
                                                "verticalAlign": "middle",
                                                "marginBottom": "0",
                                            },
                                        ),
                                        style={"height": "100%"},
                                        card_hover=True,
                                        modal=True,
                                        fullscreen=False,
                                        modal_config={"width": "90%", "height": "90%"},
                                    ),
                                    width=6,
                                    style={"marginBottom": "20px"},
                                ),
                                ddk.Block(
                                    create_graph_card(
                                        "Location Use",
                                        [
                                            TOOLTIPS.DATA_DESCRIPTIONS.LOCATION_USE,
                                            TOOLTIPS.CHART_GUIDANCE.CREATE_FILTERS.DRILL_DOWN,
                                            TOOLTIPS.CHART_GUIDANCE.ADJUST_FILTERS.HIERARCHICAL,
                                        ],
                                        dcc.Graph(
                                            id="location-use-categorical-chart",
                                            className="chart-graph",
                                            config={
                                                "responsive": True,
                                                "displayModeBar": True,
                                                "displaylogo": False,
                                            },
                                        ),
                                        style={"height": "100%"},
                                        card_hover=True,
                                        modal=True,
                                        fullscreen=False,
                                        modal_config={"width": "80%", "height": "90%"},
                                    ),
                                    width=6,
                                    style={"marginBottom": "20px"},
                                ),
                            ]
                        ),
                        # Additional metrics
                        ddk.Row(
                            [
                                ddk.Block(
                                    create_metric_card(
                                        "total-casualty-rescues-card",
                                        title_text="All People with a Casualty or Rescue",
                                        tooltip_text=TOOLTIPS.METRICS.TOTAL_CASUALTY_RESCUE,
                                    ),
                                    width=3,
                                ),
                                ddk.Block(
                                    create_metric_card(
                                        "total-displacements-card",
                                        title_text="People/Businesses Displaced",
                                        tooltip_text=TOOLTIPS.METRICS.TOTAL_DISPLACEMENTS,
                                    ),
                                    width=3,
                                ),
                                ddk.Block(
                                    create_metric_card(
                                        "total-rescue-animals-card",
                                        title_text="Animals Rescued",
                                        tooltip_text=TOOLTIPS.METRICS.TOTAL_ANIMAL_RESCUES,
                                    ),
                                    width=3,
                                ),
                                ddk.Block(
                                    create_metric_card(
                                        "total-exposures-card",
                                        title_text="Total Exposures",
                                        tooltip_text=TOOLTIPS.METRICS.TOTAL_EXPOSURES,
                                    ),
                                    width=3,
                                ),
                            ],
                            style={"marginBottom": "20px"},
                        ),
                        # Casualty rescues section
                        ddk.Row(
                            [
                                ddk.Block(
                                    create_graph_card(
                                        "Casualties and Rescues",
                                        [
                                            TOOLTIPS.DATA_DESCRIPTIONS.CASUALTY_RESCUE_CONTINGENCY,
                                            TOOLTIPS.CHART_GUIDANCE.ADJUST_FILTERS.CASUALTY_RESCUE_FF_NONFF_RADIO,
                                        ],
                                        [
                                            dcc.RadioItems(
                                                id="casualty-ff-filter",
                                                options=[
                                                    {
                                                        "label": "Civilian",
                                                        "value": "NONFF",
                                                    },
                                                    {
                                                        "label": "Firefighter",
                                                        "value": "FF",
                                                    },
                                                ],
                                                value="NONFF",
                                                labelStyle={
                                                    "display": "inline-block",
                                                    "marginRight": "20px",
                                                },
                                                style={"marginBottom": "10px"},
                                            ),
                                            dcc.Graph(
                                                id="casualty-rescues-bubble",
                                                className="chart-graph",
                                                config={"responsive": True},
                                            ),
                                        ],
                                        style={"height": "100%"},
                                        card_hover=True,
                                        modal=True,
                                        fullscreen=False,
                                        modal_config={"width": "90%", "height": "90%"},
                                    ),
                                    width=6,
                                    style={"marginBottom": "20px"},
                                ),
                                ddk.Block(
                                    create_graph_card(
                                        "Aid Given and Received",
                                        [
                                            TOOLTIPS.DATA_DESCRIPTIONS.DEPARTMENT_AID,
                                            TOOLTIPS.CHART_GUIDANCE.VISUAL_ONLY.DRILL_DOWN,
                                        ],
                                        dcc.Graph(
                                            id="aid-sunburst-chart",
                                            className="chart-graph",
                                            config={
                                                "responsive": True,
                                                "displayModeBar": True,
                                                "displaylogo": False,
                                            },
                                        ),
                                        style={"height": "100%"},
                                        card_hover=True,
                                        modal=True,
                                        fullscreen=False,
                                        modal_config={"width": "80%", "height": "90%"},
                                    ),
                                    width=6,
                                    style={"marginBottom": "20px"},
                                ),
                            ]
                        ),
                        # Hazard metrics row
                        ddk.Row(
                            [
                                ddk.Block(
                                    create_metric_card(
                                        "csst-hazard-count-card",
                                        title_text="CSST Hazards",
                                        tooltip_text=TOOLTIPS.METRICS.TOTAL_CSST_HAZARDS,
                                    ),
                                    width=4,
                                ),
                                ddk.Block(
                                    create_metric_card(
                                        "electric-hazard-count-card",
                                        title_text="Electric Hazards",
                                        tooltip_text=TOOLTIPS.METRICS.TOTAL_ELECTRIC_HAZARDS,
                                    ),
                                    width=4,
                                ),
                                ddk.Block(
                                    create_metric_card(
                                        "powergen-hazard-count-card",
                                        title_text="Power Generation Hazards",
                                        tooltip_text=TOOLTIPS.METRICS.TOTAL_POWERGEN_HAZARDS,
                                    ),
                                    width=3,
                                ),
                                ddk.Block(
                                    create_metric_card(
                                        "medical-oxygen-hazard-count-card",
                                        title_text="Medical Oxygen Hazards",
                                        tooltip_text=TOOLTIPS.METRICS.TOTAL_MEDICAL_OXYGEN_HAZARDS,
                                    ),
                                    width=3,
                                ),
                            ],
                            style={"marginBottom": "20px"},
                        ),
                    ],
                    width=80,
                ),
            ],
            style={"marginBottom": "20px"},
        ),
    ]
