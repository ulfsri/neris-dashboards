"""
Callback functions for the cornsacks dashboard.

Each callback is self-contained, loading its own data with server-side caching.
Most callbacks run in parallel for maximum performance. Cross-filtering callbacks
are handled separately, by a single callback, to avoid callback loops.
"""

import os
from typing import Tuple

from dash import Input, Output, State, ctx, no_update
import dash_leaflet as dl
from neris_dash_common import (
    build_options,
    create_arcgis_layer,
    create_contingency_bubble,
    create_heatmap,
    create_hierarchical_chart,
    create_legend_item,
    create_legend_section,
    create_map_legend,
    create_time_series_trendline,
    create_zip_from_dataframes,
    DEFAULT_INCIDENT_TYPE_COLORS,
    DEFAULT_LOCATION_USE_COLORS,
    FF_COLOR,
    format_enum_text,
    format_hour,
    GeoJson,
    GeoJsonProperty,
    get_address_suggestions,
    get_geocode_icon,
    get_hq_symbol_svg,
    get_station_symbol_svg,
    handle_address_geocoding,
    log_timing,
    NONFF_COLOR,
    register_button_loading_state,
    RollingWindow,
    update_filters_from_crossfilter_selection,
)

from tables import (
    FILTER_REGISTRY,
    IncidentsRelation,
)
from config import CACHE_TIMEOUT_SECONDS, MAX_MAP_POINTS, DEPT_FEATURE_SERVER_URL

import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)
from arcgis.gis import GIS  # noqa: E402
from arcgis.geocoding import Geocoder, get_geocoders  # noqa: E402

# This needs to be done in the app so it's just done once, and not for every callback.
# I put a function to get these in the shared module but it wasn't working for some reason.
gis: GIS = GIS(api_key=os.getenv("AGO_API_KEY"))
geocoder: Geocoder = get_geocoders(gis)[0]

# TODO move these to the shared module
DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
HOUR_ORDER = list(range(24))[::-1]


#########################
##### Filter Options
#########################
def register_filter_component_callbacks(app, cache):
    """Register filter-related callbacks."""

    # Button loading states for the clear filters buttons
    register_button_loading_state(
        app=app,
        button_id="clear-filters-button",
        loading_text="Clearing...",
        reset_trigger_id="filters",
        reset_trigger_prop="data",
        initial_text="Clear all filters",
    )

    register_button_loading_state(
        app=app,
        button_id="clear-trendline-filter",
        loading_text="Clearing...",
        reset_trigger_id="filters",
        reset_trigger_prop="data",
        initial_text="Clear selection",
    )

    register_button_loading_state(
        app=app,
        button_id="clear-heatmap-filter",
        loading_text="Clearing...",
        reset_trigger_id="filters",
        reset_trigger_prop="data",
        initial_text="Clear selection",
    )

    register_button_loading_state(
        app=app,
        button_id="zoom-to-points-button",
        loading_text="Zooming...",
        reset_trigger_id="incident-map",
        reset_trigger_prop="viewport",
        initial_text="Zoom to points",
    )

    @app.callback(
        Output("filters", "data"),
        Input("csst-hazard-filter", "value"),
        Input("electric-hazard-filter", "value"),
        Input("powergen-hazard-filter", "value"),
        Input("medical-oxygen-hazard-filter", "value"),
        Input("aid-direction-filter", "value"),
        Input("department-state-filter", "value"),
        Input("neris-id-dept-filter", "value"),
        Input("start-date-filter", "date"),
        Input("end-date-filter", "date"),
        State("filters", "data"),
        prevent_initial_call=True,
    )
    def update_filter_store(
        csst_hazard_filter,
        electric_hazard_filter,
        powergen_hazard_filter,
        medical_oxygen_hazard_filter,
        aid_direction_filter,
        department_state_filter,
        neris_id_dept_filter,
        start_date_filter,
        end_date_filter,
        current_filters,
    ):
        """Update filter state from UI inputs.

        Note: Cross-filters are handled by the crossfilter_controller callback
        to avoid callback loops.
        """
        print(f"update_filter_store triggered by: {ctx.triggered_id}")

        # Start with current filters from State, or defaults
        filters = (current_filters or FILTER_REGISTRY.get_all_defaults()).copy()

        # Update filters from UI inputs
        filters["csst_hazard_only"] = "csst_hazard_only" in (csst_hazard_filter or [])
        filters["electric_hazard_only"] = "electric_hazard_only" in (
            electric_hazard_filter or []
        )
        filters["powergen_hazard_only"] = "powergen_hazard_only" in (
            powergen_hazard_filter or []
        )
        filters["medical_oxygen_hazard_only"] = "medical_oxygen_hazard_only" in (
            medical_oxygen_hazard_filter or []
        )
        filters["aid_direction"] = aid_direction_filter or "all"
        filters["department_state"] = department_state_filter or "all"
        filters["neris_id_dept"] = neris_id_dept_filter or "all"
        filters["start_date"] = start_date_filter
        filters["end_date"] = end_date_filter

        return filters

    @app.callback(
        Output("current-filters-display", "children"),
        Input("filters", "data"),
    )
    def update_current_filters_display(filters):
        """Update the display with the current filter state."""
        return FILTER_REGISTRY.format_display(filters or {})

    @app.callback(
        Output("csst-hazard-filter", "value", allow_duplicate=True),
        Output("electric-hazard-filter", "value", allow_duplicate=True),
        Output("powergen-hazard-filter", "value", allow_duplicate=True),
        Output("medical-oxygen-hazard-filter", "value", allow_duplicate=True),
        Output("aid-direction-filter", "value", allow_duplicate=True),
        Output("department-state-filter", "value", allow_duplicate=True),
        Output("neris-id-dept-filter", "value", allow_duplicate=True),
        Output("start-date-filter", "date", allow_duplicate=True),
        Output("end-date-filter", "date", allow_duplicate=True),
        Input("filters", "data"),
        prevent_initial_call=True,
    )
    def sync_filters_to_ui(filters):
        """Sync filter UI components to align with the filter store.

        This ensures UI components stay in sync when filters are updated
        programmatically (e.g., by clear button or cross-filters).
        """
        return FILTER_REGISTRY.get_clearable_ui_values(
            filters,
            [
                "csst_hazard_only",
                "electric_hazard_only",
                "powergen_hazard_only",
                "medical_oxygen_hazard_only",
                "aid_direction",
                "department_state",
                "neris_id_dept",
                "start_date",
                "end_date",
            ],
        )

    @app.callback(
        Output("data-last-updated", "children"),
        Input("filters", "data"),
    )
    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    @log_timing
    def update_data_last_updated(filters):
        """Update the data last updated timestamp."""
        incidents = IncidentsRelation(filters or {})
        return incidents.get_last_updated()

    @app.callback(
        Output("department-state-filter", "options"),
        Input("filters", "data"),
    )
    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    @log_timing
    def update_state_options(filters):
        """Update state options based on other active filters."""
        # Create a copy of filters without the 'department_state' filter so we can see
        # all states that match other active filters.
        state_filters = {
            k: v for k, v in (filters or {}).items() if k != "department_state"
        }

        incidents = IncidentsRelation(state_filters)
        states = incidents.unique_department_states()

        return build_options(states, all_label="All States", all_value="all")

    @app.callback(
        Output("neris-id-dept-filter", "options"),
        Input("filters", "data"),
    )
    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    @log_timing
    def update_department_options(filters):
        """Update department options based on other active filters."""
        # Create a copy of filters without the 'neris_id_dept' filter so we
        # can see all departments that match other active filters.
        department_filters = {
            k: v for k, v in (filters or {}).items() if k != "neris_id_dept"
        }
        incidents = IncidentsRelation(department_filters)
        departments = incidents.unique_departments()

        options = [
            {
                "label": f"{department['department_name']} - {department['department_state']} ({department['neris_id_dept']})",
                "value": department["neris_id_dept"],
                "title": f"{department['department_name']} - {department['department_state']} ({department['neris_id_dept']})",
            }
            for department in departments
        ]

        return options


#########################
##### Cross-filter Controllers
#########################
def register_crossfilter_callbacks(app, cache):
    """Register callbacks for charts that support cross-filtering."""

    # TODO: even with update_filters_from_crossfilter_selection there's a lot of
    # duplicated logic in the callbacks. Investigate DRYing out even more. Perhaps
    # with a custom decorator?

    @app.callback(
        Output("filters", "data", allow_duplicate=True),
        Output("trendline-chart", "figure"),
        Input("filters", "data"),
        Input("trendline-chart", "selectedData"),
        Input("clear-trendline-filter", "n_clicks"),
        State("filters", "data"),
        prevent_initial_call="initial_duplicate",
    )
    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    @log_timing
    def trendline_controller(
        store_input, selected_data, clear_n_clicks, current_filters
    ):
        """Update trendline and process date range selections."""
        trigger = ctx.triggered_id
        print(f"trendline_controller triggered by: {trigger}")

        # 1. APPLY CROSSFILTER PROCESSING
        # Map x-axis to both start and end date filters. x_order is None for continuous axis.
        new_filter_sets = update_filters_from_crossfilter_selection(
            trigger_id=trigger,
            component_id="trendline-chart",
            selected_data=selected_data,
            current_filters=current_filters,
            filter_mapping={"x": ("start_date", "end_date")},
            x_order=None,
            clear_button_id="clear-trendline-filter",
        )

        if new_filter_sets is None:
            return no_update, no_update

        # `_` would be the trendline_filters, but we're going to use
        # current_filters so this crossfilter filters/zooms itself (unlike
        # our other crossfilters, which don't respect the filters they create)
        new_store_filters, _ = new_filter_sets

        # Format datetimes to just YYYY-MM-DD to match date picker expectations
        if new_store_filters:
            for k in ["start_date", "end_date"]:
                if new_store_filters.get(k) and new_store_filters[k] != "all":
                    new_store_filters[k] = str(new_store_filters[k])[:10]

        # 2. GENERATE DATA FOR FIGURE
        rolling_window = RollingWindow(window=7, include_current=False)
        incidents = IncidentsRelation(current_filters)
        daily_df = incidents.time_series_counts(
            date_column="call_create", interval="daily", rolling_window=rolling_window
        )

        fig = create_time_series_trendline(
            daily_df,
            date_column="date",
            rolling_window=rolling_window,
            interval="daily",
            y_axis_title="Incident Count",
        )

        # 3. FINAL ROUTING
        if new_store_filters is not None:
            return new_store_filters, no_update

        return no_update, fig

    @app.callback(
        Output("filters", "data", allow_duplicate=True),
        Output("day-hour-heatmap", "figure"),
        Input("filters", "data"),
        Input("day-hour-heatmap", "selectedData"),
        Input("clear-heatmap-filter", "n_clicks"),
        State("filters", "data"),
        prevent_initial_call="initial_duplicate",
    )
    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    @log_timing
    def heatmap_controller(store_input, selected_data, clear_n_clicks, current_filters):
        """Load data and create day of week × hour of day heatmap."""
        trigger = ctx.triggered_id
        print(f"heatmap_controller triggered by: {trigger}")

        # 1. APPLY CROSSFILTER PROCESSING
        new_filter_sets: Tuple[dict | None, dict] | None = (
            update_filters_from_crossfilter_selection(
                trigger_id=trigger,
                component_id="day-hour-heatmap",
                selected_data=selected_data,
                current_filters=current_filters,
                filter_mapping={"x": "day_of_week", "y": "hour"},
                x_order=DAY_ORDER,
                y_order=HOUR_ORDER,
                clear_button_id="clear-heatmap-filter",
            )
        )

        if new_filter_sets is None:
            return no_update, no_update

        new_store_filters, heatmap_filters = new_filter_sets

        # 2. GENERATE DATA FOR FIGURE
        incidents = IncidentsRelation(heatmap_filters)
        day_hour_counts_df = incidents.get_day_hour_counts()

        fig = create_heatmap(
            day_hour_counts_df,
            x_column="call_create_day_of_week",
            y_column="call_create_hour",
            x_order=DAY_ORDER,
            y_order=HOUR_ORDER,
            count_column="count",
            colorscale="Burg",
            x_label_formatter=format_enum_text,
            y_label_formatter=format_hour,
        )

        fig.update_xaxes(showgrid=False, showline=False, ticks="", zeroline=False)
        fig.update_yaxes(showgrid=False, showline=False, ticks="", zeroline=False)
        fig.update_layout(
            hovermode="closest",
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Inter, Segoe UI, Arial",
                font_color="#333333",
            ),
        )
        fig.update_traces(
            xgap=2,
            ygap=2,
            hovertemplate="%{customdata[1]}<br>%{customdata[0]}<br>%{z:,}<extra></extra>",
        )

        # 3. FINAL ROUTING
        if new_store_filters is not None:
            return new_store_filters, no_update

        return no_update, fig

    # Splitting the caching from the callback itself was needed here to get
    # deal with the fact that in categorical charts, clicking on a specific value
    # can indicate two different things: either a drill-down or a zoom-out.
    # Splitting out this way allows us to include the trigger in the function call,
    # which helps keep track of which direction we're going.
    # TODO: investigate if there's a better way, perhaps an arg in cache.memoize?
    @app.callback(
        Output("filters", "data", allow_duplicate=True),
        Output("incident-types-categorical-chart", "figure"),
        Input("filters", "data"),
        Input("incident-types-categorical-chart", "clickData"),
        State("filters", "data"),
        prevent_initial_call="initial_duplicate",
    )
    @log_timing
    def incident_types_categorical_controller(store_input, click_data, current_filters):
        """Update incident types categorical and process hierarchical segment clicks."""
        trigger = ctx.triggered_id
        return _incident_types_categorical_controller_memoized(
            store_input, click_data, current_filters, trigger
        )

    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    def _incident_types_categorical_controller_memoized(
        store_input, click_data, current_filters, trigger
    ):
        """Memoized implementation of incident-types-categorical-controller, keyed by trigger to avoid collisions."""

        # 1. APPLY CROSSFILTER PROCESSING
        # Map hierarchical 'id' (the path) to the type_incident filter
        new_filter_sets = update_filters_from_crossfilter_selection(
            trigger_id=trigger,
            component_id="incident-types-categorical-chart",
            selected_data=None,  # categorical uses clickData
            click_data=click_data,
            current_filters=current_filters,
            filter_mapping={"id": "type_incident"},
            is_hierarchical=True,
        )

        if new_filter_sets is None:
            return no_update, no_update

        new_store_filters, categorical_filters = new_filter_sets

        # 2. GENERATE DATA FOR FIGURE
        incidents = IncidentsRelation(categorical_filters)
        incident_types = incidents.get_incident_types()
        incident_type_counts_df = incident_types.get_path_counts()

        # Determine the drill level to display based on the active filters
        active_filters = (
            new_store_filters if new_store_filters is not None else current_filters
        )
        current_path = active_filters.get("type_incident", "all")
        if isinstance(current_path, list) and current_path:
            initial_level = current_path[0]
        else:
            initial_level = current_path

        fig = create_hierarchical_chart(
            incident_type_counts_df,
            path_column="type_incident",
            count_column="count",
            chart_type="treemap",
            base_color_map=DEFAULT_INCIDENT_TYPE_COLORS,
            root_label="Total Incidents",
            initial_level=initial_level,
            maxdepth=3,
        )
        # Use path as uirevision so zoom resets when path changes (including back to "all")
        # fig.update_layout(uirevision="constant")
        fig.update_layout(uirevision=str(current_path))

        # 3. FINAL ROUTING
        if new_store_filters is not None:
            return new_store_filters, no_update

        return no_update, fig

    @app.callback(
        Output("filters", "data", allow_duplicate=True),
        Output("location-use-categorical-chart", "figure"),
        Input("filters", "data"),
        Input("location-use-categorical-chart", "clickData"),
        State("filters", "data"),
        prevent_initial_call="initial_duplicate",
    )
    @log_timing
    def location_use_controller(store_input, click_data, current_filters):
        """Update location use treemap and process hierarchical segment clicks."""
        trigger = ctx.triggered_id
        return _location_use_controller_memoized(
            store_input, click_data, current_filters, trigger
        )

    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    def _location_use_controller_memoized(
        store_input, click_data, current_filters, trigger
    ):
        """Memoized implementation of location_use_controller, keyed by trigger to avoid collisions."""

        # 1. APPLY CROSSFILTER PROCESSING
        # Map hierarchical 'id' (the path) to the location_use_path filter
        new_filter_sets = update_filters_from_crossfilter_selection(
            trigger_id=trigger,
            component_id="location-use-categorical-chart",
            selected_data=None,  # Treemap uses clickData for hierarchical
            click_data=click_data,
            current_filters=current_filters,
            filter_mapping={"id": "location_use_path"},
            is_hierarchical=True,
        )

        if new_filter_sets is None:
            return no_update, no_update

        new_store_filters, location_use_filters = new_filter_sets

        # 2. GENERATE DATA FOR FIGURE
        incidents = IncidentsRelation(location_use_filters)
        location_use_counts_df = incidents.get_location_use_path_counts()

        # Determine the drill level to display based on the active filters
        active_filters = (
            new_store_filters if new_store_filters is not None else current_filters
        )
        current_path = active_filters.get("location_use_path", "all")
        if isinstance(current_path, list) and current_path:
            initial_level = current_path[0]
        else:
            initial_level = current_path

        fig = create_hierarchical_chart(
            location_use_counts_df,
            path_column="location_use_path",
            count_column="count",
            chart_type="treemap",
            base_color_map=DEFAULT_LOCATION_USE_COLORS,
            root_label="All Locations",
            initial_level=initial_level,
        )

        # Use path as uirevision so zoom resets when path changes (including back to "all")
        # fig.update_layout(uirevision="constant")
        fig.update_layout(uirevision=str(current_path))

        # 3. FINAL ROUTING
        if new_store_filters is not None:
            return new_store_filters, no_update

        return no_update, fig


#########################
##### Read Only Charts
#########################
def register_read_only_chart_callbacks(app, cache):
    """Register standard chart callbacks."""

    @app.callback(
        Output("aid-sunburst-chart", "figure"),
        Input("filters", "data"),
    )
    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    @log_timing
    def update_aid_sunburst(filters):
        """Update the aid sunburst chart."""
        filters = filters or {}
        incidents = IncidentsRelation(filters)
        aid = incidents.get_aid()

        # Check if a department filter is active
        neris_id_dept = filters.get("neris_id_dept")
        is_dept_filtered = neris_id_dept and neris_id_dept != "all"

        # If no department filter, we only want the first two tiers.
        # If department filter is active, we want all three tiers.
        max_tiers = 3 if is_dept_filtered else 2
        aid_counts_df = aid.get_path_counts(max_tiers=max_tiers)

        fig = create_hierarchical_chart(
            aid_counts_df,
            path_column="aid_concat",
            count_column="count",
            chart_type="sunburst",
        )

        fig.update_traces(insidetextorientation="horizontal")

        return fig


def register_map_callbacks(app, cache):
    """Register map-related callbacks."""

    @app.callback(
        Output("incident-map", "viewport"),
        Output("search-marker", "children"),
        Input("zoom-to-points-button", "n_clicks"),
        Input("address-dropdown", "value"),
        State("filters", "data"),
        prevent_initial_call=True,
    )
    @log_timing
    def update_map_viewport(n_clicks, selected_address, filters):
        """Update map viewport based on zoom button or address search."""
        trigger = ctx.triggered_id

        if trigger == "zoom-to-points-button":
            if n_clicks is None:
                return no_update, no_update

            incidents = IncidentsRelation(filters or {})
            bounds = incidents.get_bounds()

            if bounds is None:
                return no_update, no_update

            return {"bounds": bounds}, no_update

        elif trigger == "address-dropdown":
            icon = get_geocode_icon(size=30, as_dl_icon=True)

            return handle_address_geocoding(
                selected_address,
                geocoder=geocoder,
                icon=icon,
                zoom_level=15,
            )

        return no_update, no_update

    @app.callback(
        Output("dept-layers-toggle-button", "disabled"),
        Input("filters", "data"),
    )
    def update_dept_toggle_state(filters):
        """Enable/disable the department layers toggle based on filter state."""
        neris_id_dept = (filters or {}).get("neris_id_dept")
        is_active = neris_id_dept and neris_id_dept != "all"

        return not is_active

    @app.callback(
        Output("dept-layers-show-store", "data"),
        Output("dept-layers-toggle-button", "children"),
        Input("dept-layers-toggle-button", "n_clicks"),
        State("dept-layers-show-store", "data"),
        prevent_initial_call=True,
    )
    def toggle_dept_layers(n_clicks, currently_showing):
        """Toggle the department layers state and update button text."""
        if n_clicks is None:
            return no_update, no_update

        new_showing = not currently_showing
        button_text = "Hide stations" if new_showing else "Show stations"

        return new_showing, button_text

    @app.callback(
        Output("map-legend-container", "children"),
        Input("filters", "data"),
        Input("dept-layers-show-store", "data"),
    )
    def update_map_legend(filters, show_dept_layers):
        """Update the map legend based on active filters and toggle."""
        # 1. Incident Type Section (Always present)
        incident_items = [
            create_legend_item(format_enum_text(itype), color=color)
            for itype, color in DEFAULT_INCIDENT_TYPE_COLORS.items()
        ]
        incident_items.append(create_legend_item("Multiple Types", color="#808080"))

        sections = [create_legend_section("Incident Type", incident_items)]

        # 2. Department Section (Only if filtered)
        neris_id_dept = (filters or {}).get("neris_id_dept")
        if neris_id_dept and neris_id_dept != "all":
            dept_items = [
                create_legend_item(
                    "Department HQ", svg=get_hq_symbol_svg(fill_opacity=0.80)
                ),
            ]
            # Only show stations in legend if toggle is on
            if show_dept_layers:
                dept_items.append(
                    create_legend_item(
                        "Fire Station",
                        svg=get_station_symbol_svg(size=18, fill_opacity=0.80),
                    )
                )
            sections.append(create_legend_section(items=dept_items))

        return create_map_legend(sections)

    @app.callback(
        Output("address-dropdown", "options"),
        Input("address-dropdown", "search_value"),
        prevent_initial_call=True,
    )
    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    def update_address_suggestions(search_value):
        """Get address suggestions from ArcGIS as the user types."""
        options = get_address_suggestions(search_value, geocoder=geocoder)
        if not options:
            return no_update
        return options

    @app.callback(
        Output("incident-points", "children"),
        Input("filters", "data"),
        Input("incident-map", "bounds"),
        Input("incident-map", "viewport"),
        Input("dept-layers-show-store", "data"),
    )
    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    @log_timing
    def update_map(filters, bounds, viewport, show_dept_layers):
        """Load sampled points and create map markers."""
        trigger = ctx.triggered_id

        # If the map update was triggered by a viewport change from the address dropdown,
        # we don't want to re-render everything if we don't have to, but we must
        # ensure we don't return no_update if we want the marker to stay.
        # However, this callback only controls 'incident-points' children.

        incidents = IncidentsRelation(filters or {})
        points_df = incidents.get_sampled_points(limit=MAX_MAP_POINTS, bounds=bounds)

        layers = []
        # TODO: the styling, tooltip, and popup functions have to be defined in a
        # separate JavaScript (assets/map_utils.js) file, making reusability a
        # bit kludgy. I tried to get them working with dash-extensions' assign function,
        # but it was a not working and I'm moving on.
        neris_id_dept = (filters or {}).get("neris_id_dept")
        if neris_id_dept and neris_id_dept != "all":
            # 1. Department Boundaries (bottom layer) - Always show if dept selected
            boundary_layer = create_arcgis_layer(
                server_url=DEPT_FEATURE_SERVER_URL,
                layer_id=2,
                where_clause=f"neris_id = '{neris_id_dept}'",
                out_fields="name",
                component_id=f"dept-boundary-{neris_id_dept}",
                zoomToBounds=trigger == "filters",
                style={
                    "variable": "window.dash_leaflet.cornsacks.styleDeptJurisdiction"
                },
            )
            if boundary_layer is not None:
                layers.append(boundary_layer)

            # 2. Department Headquarters - Always show if dept selected
            hq_layer = create_arcgis_layer(
                server_url=DEPT_FEATURE_SERVER_URL,
                layer_id=0,
                where_clause=f"neris_id = '{neris_id_dept}'",
                out_fields="neris_id,name,state,address_line_1,address_line_2,city,zip_code",
                component_id=f"dept-hq-{neris_id_dept}",
                pointToLayer={
                    "variable": "window.dash_leaflet.cornsacks.pointToLayerDeptHq"
                },
                onEachFeature={
                    "variable": "window.dash_leaflet.cornsacks.renderPopupDeptHq"
                },
                hideout={"hqSvg": get_hq_symbol_svg(fill_opacity=0.80)},
            )
            if hq_layer is not None:
                layers.append(hq_layer)

            # 3. Fire Stations - Only show if toggle is ON
            if show_dept_layers:
                stations_layer = create_arcgis_layer(
                    server_url=DEPT_FEATURE_SERVER_URL,
                    layer_id=1,
                    where_clause=f"department_neris_id = '{neris_id_dept}'",
                    out_fields="neris_id,station_name,address_line_1,address_line_2,city,state,zip_code",
                    component_id=f"dept-stations-{neris_id_dept}",
                    pointToLayer={
                        "variable": "window.dash_leaflet.cornsacks.pointToLayerStation"
                    },
                    onEachFeature={
                        "variable": "window.dash_leaflet.cornsacks.renderPopupStation"
                    },
                    hideout={
                        "stationSvg": get_station_symbol_svg(size=25, fill_opacity=0.80)
                    },
                )
                if stations_layer is not None:
                    layers.append(stations_layer)

        # 4. Incident Points (top layer)
        if not points_df.empty:
            geojson = GeoJson(
                points_df=points_df,
                properties=[
                    GeoJsonProperty("neris_id_incident", "Unknown"),
                    GeoJsonProperty("civic_location", "No Localization Provided"),
                    GeoJsonProperty("incident_type", "No Incident Type Provided"),
                    GeoJsonProperty("call_create", "No Call Created Provided"),
                    GeoJsonProperty("department_name", "No Department Provided"),
                ],
            )

            # Only zoom to bounds when filters change, not when user pans/zooms to prevent callback loop
            zoom_to_bounds = trigger == "filters"

            markers_layer = dl.GeoJSON(
                data=geojson.to_dict(),
                id="incident-geojson",
                zoomToBounds=zoom_to_bounds,
                hideout={
                    "colors": DEFAULT_INCIDENT_TYPE_COLORS,
                    "defaultColor": "#808080",
                },
                # these two have to be defined in assets/map_utils.js
                pointToLayer={
                    "variable": "window.dash_leaflet.cornsacks.pointToLayerIncident"
                },
                onEachFeature={
                    "variable": "window.dash_leaflet.cornsacks.renderPopupIncident"
                },
            )
            layers.append(markers_layer)

        return layers


def register_casualty_rescues_callbacks(app, cache):
    """Register casualty rescues callbacks."""

    @app.callback(
        Output("casualty-rescues-bubble", "figure"),
        Input("filters", "data"),
        Input("casualty-ff-filter", "value"),
    )
    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    @log_timing
    def update_casualty_rescues_bubble(filters, ff_filter):
        """Load data and create bubble chart - cached and runs in parallel."""
        # Merge the local FF filter into the global filters for this query
        # The FF/NONFF filter is stored locally in the radio button component
        # so it doesn't affect data download etc.
        query_filters = (filters or {}).copy()
        if ff_filter:
            query_filters["type_ff_nonff"] = ff_filter

        incidents = IncidentsRelation(query_filters)
        casualty_rescues = incidents.get_casualty_rescues(query_filters)
        contingency_df = casualty_rescues.get_contingency_counts()

        # Define color based on filter
        bubble_color = FF_COLOR if ff_filter == "FF" else NONFF_COLOR

        return create_contingency_bubble(
            contingency_df,
            row_column="type_casualty",
            col_column="type_rescue",
            count_column="count",
            x_title="Rescue Type",
            y_title="Casualty Type",
            height=600,
            color=bubble_color,
        )


#########################
##### Summary Cards
#########################
def register_summary_cards_callbacks(app, cache):
    """Register summary cards callbacks."""

    @app.callback(
        Output("total-incidents-card", "children"),
        Output("total-unit-responses-card", "children"),
        Output("duration-p90-card", "children"),
        Output("csst-hazard-count-card", "children"),
        Output("electric-hazard-count-card", "children"),
        Output("powergen-hazard-count-card", "children"),
        Output("medical-oxygen-hazard-count-card", "children"),
        Output("total-casualty-rescues-card", "children"),
        Output("total-displacements-card", "children"),
        Output("total-rescue-animals-card", "children"),
        Output("total-exposures-card", "children"),
        Input("filters", "data"),
    )
    @cache.memoize(timeout=CACHE_TIMEOUT_SECONDS)
    @log_timing
    def update_summary_cards(filters):
        """Load data and update cards."""
        incidents = IncidentsRelation(filters or {})

        return incidents.get_summary_card_stats()


#########################
##### Info Display
#########################
def register_info_callbacks(app, cache):
    """Register callbacks for debugging and info display."""

    @app.callback(
        Output("filters", "data", allow_duplicate=True),
        Output("trendline-chart", "selectedData", allow_duplicate=True),
        Input("clear-trendline-filter", "n_clicks"),
        State("filters", "data"),
        prevent_initial_call=True,
    )
    def clear_trendline_filter(n_clicks, current_filters):
        """Clear the date range filters set by the trendline chart."""
        if n_clicks == 0:
            return no_update, no_update

        filters = (current_filters or FILTER_REGISTRY.get_all_defaults()).copy()
        defaults = FILTER_REGISTRY.get_all_defaults()
        filters["start_date"] = defaults.get("start_date")
        filters["end_date"] = defaults.get("end_date")

        return filters, None

    @app.callback(
        Output("filters", "data", allow_duplicate=True),
        Output("trendline-chart", "selectedData", allow_duplicate=True),
        Output("day-hour-heatmap", "selectedData", allow_duplicate=True),
        Output("incident-types-categorical-chart", "clickData", allow_duplicate=True),
        Output("location-use-categorical-chart", "clickData", allow_duplicate=True),
        Output("casualty-ff-filter", "value", allow_duplicate=True),
        Input("clear-filters-button", "n_clicks"),
        State("filters", "data"),
        prevent_initial_call=True,
    )
    def clear_all_filters(n_clicks, current_filters):
        """Clear all clearable filters, resetting them to their default values.

        Also clears selections on cross-filter charts to reset them to their
        original states.
        """
        if n_clicks == 0:
            return no_update, no_update, no_update, no_update, no_update

        # Start with current filters to preserve non-clearable filters
        filters = (current_filters or FILTER_REGISTRY.get_all_defaults()).copy()

        # Get and update only clearable filters to their defaults
        clearable_defaults = FILTER_REGISTRY.get_clearable_defaults()
        for key, default_value in clearable_defaults.items():
            filters[key] = default_value

        # Clear chart selections by setting them to None
        # Returns: filters, trendline selection, heatmap selection, incident types drill-down, location use drill-down, casualty radio toggle
        return filters, None, None, None, None, "NONFF"


#########################
##### Data Export
#########################
def register_export_callbacks(app, cache):
    """Register callbacks for data export functionality."""

    # We should probably only expose this when filtered down to a specific entity
    # i.e. not the full NERIS Public dashboard. Let's let AGO handle public
    # downloads of massive data.

    # calling `register_button_loading_state` registers a callback for a button
    # callbacks for the download data BUTTON
    register_button_loading_state(
        app=app,
        button_id="download-data-button",
        loading_text="Generating download...",
        reset_trigger_id="download-data",
        reset_trigger_prop="data",
        initial_text="Download data as CSV",
    )

    # Don't cache! We don't want to keep a bunch of zip file buffers.
    @app.callback(
        Output("download-data", "data"),
        Input("download-data-button", "n_clicks"),
        State("filters", "data"),
        prevent_initial_call=True,
    )
    @log_timing
    def download_data_as_csv(n_clicks, filters):
        """Export filtered data from all three tables as CSV files in a zip archive."""
        if n_clicks == 0:
            return no_update

        # Get filtered data from each table
        incidents = IncidentsRelation(filters or {})
        incidents_df = incidents.get_export_data()

        casualty_rescues = incidents.get_casualty_rescues(filters or {})
        casualty_rescues_df = casualty_rescues.get_export_data()

        incident_types = incidents.get_incident_types()
        incident_types_df = incident_types.get_export_data()

        aids = incidents.get_aid()
        aids_df = aids.get_export_data()

        # Use shared utility to create zip file
        dataframes = [
            ("incidents.csv", incidents_df),
            ("casualty_rescues.csv", casualty_rescues_df),
            ("incident_types.csv", incident_types_df),
            ("aids.csv", aids_df),
        ]

        return create_zip_from_dataframes(
            dataframes, zip_filename="neris_incidents", timestamp=True
        )


#########################
##### Registration
#########################
def register_all_callbacks(app, cache):
    """Register all callbacks for the app."""
    register_filter_component_callbacks(app, cache)
    register_crossfilter_callbacks(app, cache)
    register_read_only_chart_callbacks(app, cache)
    register_map_callbacks(app, cache)
    register_summary_cards_callbacks(app, cache)
    register_casualty_rescues_callbacks(app, cache)
    register_info_callbacks(app, cache)
    register_export_callbacks(app, cache)
