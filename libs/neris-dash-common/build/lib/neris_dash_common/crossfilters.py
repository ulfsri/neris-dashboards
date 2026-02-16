"""Cross-filtering handling helper functions."""

from typing import Any, Dict, List, Optional, Set, Tuple


__all__ = ["update_filters_from_crossfilter_selection"]


# TODO: the default value of 'all' is kind of a magic string. It should be a
# configuration option.
def update_filters_from_crossfilter_selection(
    trigger_id: str,
    component_id: str,
    selected_data: Any,
    current_filters: dict,
    filter_mapping: dict,
    click_data: Any = None,
    x_order: Optional[List[Any]] = None,
    y_order: Optional[List[Any]] = None,
    default_value: Any = "all",
    is_hierarchical: bool = False,
    clear_button_id: Optional[str] = None,
) -> Optional[Tuple[Optional[dict], dict]]:
    """
    Assemble filters for a filter store and a chart component from a cross-filter selection.

    This function handles the dual-nature of cross-filter components (which both
    read from and write to the same filter store). In conjunction with dropdowns
    and other direct UI filters, cross-filtering has a couple pitfalls: accidental
    overwrite of user-selected filters, and callback loops. This function helps
    avoid those.

    States handled:
    1. GHOST TRIGGER: Triggered by component, but selection is empty while filters
       are active. We protect against this by returning None (suppress filter update).
    2. REAL SELECTION: User de/selected points. Returns (new_filters, component_filters).
       The callback should return (new_filters, no_update) to update the store.
    3. STORE/INITIAL TRIGGER: Triggered by store or load. Returns (None, component_filters).
       The callback should return (no_update, fig) to update the component.
    4. CLEAR BUTTON TRIGGER: Triggered by an external clear button. Returns (new_filters, component_filters).

    Note: component_filters automatically excludes the filters defined in filter_mapping
    to prevent infinite callback loops where updating the figure clears the selection,
    which resets the store, which updates the figure again.

    Args:
        trigger_id: The ID of the component that triggered the callback (ctx.triggered_id).
        component_id: The ID of this specific chart component.
        selected_data: The 'selectedData' property from the graph.
        current_filters: The current state of the app's filter store.
        filter_mapping: Dict mapping point attributes ('x', 'y', 'id') to filter keys, e.g. {"x": "start_date", "y": "end_date"} or
        click_data: Optional 'clickData' property (fallback for selection).
        x_order: Optional list to map numeric x-coordinates back to labels.
        y_order: Optional list to map numeric y-coordinates back to labels.
        default_value: Value used when a filter is cleared (default "all").
        is_hierarchical: Set to True for Sunburst/Treemaps to enable zoom-out sync.
        clear_button_id: Optional ID of a button that clears this component's filters.

    Returns:
        Optional[Tuple[Optional[dict], dict]]:
            - None: Ghost trigger detected. Suppress update.
            - (new_store_filters, component_data_filters):
                - If new_store_filters is NOT None: Update the global store.
                - If new_store_filters IS None: Update only the local figure.
    """
    is_self_triggered = trigger_id == component_id
    is_clear_triggered = clear_button_id is not None and trigger_id == clear_button_id
    is_click_event = click_data is not None and selected_data is None

    # is_self_triggered: True if the callback was fired by the chart component itself (e.g., via box selection)
    # is_clear_triggered: True if the callback was fired by the explicitly provided clear button ID
    # is_click_event: True if the interaction was a single point click rather than a box/lasso selection
    # is_hierarchical: True if the chart supports drill-down/zoom-out logic (like Sunbursts or Treemaps)
    # _is_selection_empty: Returns True if the Plotly selection data contains no points or range coordinates
    # _is_active: Returns True if any of the filter keys mapped to this chart currently have non-default values

    # if is_self_triggered and is_click_event and is_hierarchical:
    # Handle hierarchical zoom-out for sunburst/treemap clicks if requested
    if is_self_triggered and is_click_event and is_hierarchical:
        click_data = _handle_hierarchical_zoom_out(click_data, default_value)

    data: dict | None = selected_data or click_data
    crossfilter_keys = _get_crossfilter_keys(filter_mapping)

    if not is_self_triggered and not is_clear_triggered:
        # 1. Triggered by store or initial load: exclude source keys from the filters
        return None, _exclude_keys(current_filters, crossfilter_keys)

    # 2. Else: Triggered by the component itself or a clear button: handle selection
    if is_clear_triggered or _is_selection_empty(data):
        # 2.a. Empty selection or clear button
        if (
            not is_clear_triggered
            and not is_click_event
            and _is_active(current_filters, crossfilter_keys, default_value)
        ):
            # 2.a.1. 👻 Ghost trigger! It was a selection (not a click) and filters
            # are active. Return None to suppress unintended update
            return None

        # 2.a.2. Not a ghost. Either a click or the user cleared the selection,
        # (or it was already empty): initialize the filters to the default value
        new_store_filters = _apply_defaults(
            current_filters, crossfilter_keys, default_value
        )

    else:
        # 2.b. Non-empty selection: process the selection to get new filters
        new_store_filters = _process_selection(
            data, current_filters, filter_mapping, x_order, y_order, default_value
        )

    if _is_unchanged(new_store_filters, current_filters, crossfilter_keys):
        # 2.b.1. Same filters as before: return None to suppress unnecessaryupdate
        return None

    # 2.b.2. Novel filters! return them, including the crossfilter keys for the
    #  store, and excluding the crossfilter keys for the figure
    return new_store_filters, _exclude_keys(new_store_filters, crossfilter_keys)


#########################
##### Private Helpers
#########################

_MISSING = object()


def _resolve_point_value(
    val: Any, order: Optional[List[Any]], handle_digit_strings: bool = False
) -> Any:
    """Resolve a single point coordinate to a label, returning _MISSING if out of bounds."""
    if order is None:
        return val

    # Handle numeric indices (Plotly defaults to these for ordered axes)
    # Get a rounded integer index to get the closest value to where the user clicked.
    # Use a sentinel for out of bounds values to avoid problems with falseys
    # that are actually valid chart values
    if isinstance(val, (int, float)):
        idx = int(round(val))
        return order[idx] if 0 <= idx < len(order) else _MISSING

    # Special case for integer-like strings (e.g. hours)
    if handle_digit_strings and str(val).isdigit():
        int_val = int(val)
        if int_val in order:
            return int_val

    return val


def _resolve_coordinate_range(range_pair: List[Any], order: Optional[List[Any]]) -> Any:
    """
    Resolve a pair of chart coordinates (min, max) to values for filtering.

    If an order list is provided, it resolves to a set of categorical labels
    corresponding to the indices within the range. If order is None, it returns
    the raw [min, max] pair directly for continuous axes (e.g., date ranges).
    """
    if len(range_pair) != 2:
        return set()

    if order is None:
        return range_pair

    start, end = int(round(range_pair[0])), int(round(range_pair[1]))

    return {order[idx] for idx in range(start, end + 1) if 0 <= idx < len(order)}


def _parse_selected_points(
    data: Any, x_order: Optional[List[Any]] = None, y_order: Optional[List[Any]] = None
) -> Dict[str, Set[Any]]:
    """
    Extract values from 'points' in Dash interaction data (selectedData or clickData).

    Returns a dict mapping keys (e.g., 'x', 'y', 'id', 'label') to sets of values.
    """
    results = {}

    if not data or "points" not in data:
        return results

    for point in data["points"]:
        for key in point.keys():
            if key not in results:
                results[key] = set()

            # Apply order-based resolution for x and y specifically
            if key == "x":
                val = _resolve_point_value(point["x"], x_order)
            elif key == "y":
                val = _resolve_point_value(
                    point["y"], y_order, handle_digit_strings=True
                )
            else:
                val = point[key]

            if val is not _MISSING:
                results[key].add(val)

    return results


def _parse_selected_range(
    data: Any, x_order: Optional[List[Any]] = None, y_order: Optional[List[Any]] = None
) -> Tuple[Set[Any], Set[Any]]:
    """Extract x and y values from 'range' in Dash selectedData."""
    selected_x, selected_y = set(), set()

    if not data or "range" not in data:
        return selected_x, selected_y

    range_data = data["range"]

    if "x" in range_data:
        selected_x.update(_resolve_coordinate_range(range_data["x"], x_order))
    if "y" in range_data:
        selected_y.update(_resolve_coordinate_range(range_data["y"], y_order))

    return selected_x, selected_y


def _is_selection_empty(selected_data: Any) -> bool:
    """Check if the Dash selectedData is effectively empty."""
    return not selected_data or (
        not selected_data.get("points") and not selected_data.get("range")
    )


def _handle_hierarchical_zoom_out(data: Any, default_value: Any) -> Any:
    """
    Adjust click data for sunburst/treemap zoom-out events.

    When a center node is clicked (percentEntry=1), Plotly zooms out to the parent.
    We transform the clicked ID to its parent ID to keep filters in sync.
    """
    if not data or "points" not in data:
        return data

    new_points = []
    for point in data["points"]:
        # percentEntry=1 indicates the clicked node is the current center/entry node
        if point.get("percentEntry") == 1.0:
            current_id = point.get("id")
            if isinstance(current_id, str) and current_id != default_value:
                # If it's a hierarchical path (contains ||), get the parent ID
                if "||" in current_id:
                    parent_id = current_id.rsplit("||", 1)[0]
                    new_point = point.copy()
                    new_point["id"] = parent_id
                    new_points.append(new_point)
                    continue
                else:
                    # Top-level node; parent is the root/default value
                    new_point = point.copy()
                    new_point["id"] = default_value
                    new_points.append(new_point)
                    continue
        new_points.append(point)

    return {"points": new_points}


def _get_crossfilter_keys(filter_mapping: dict) -> Set[str]:
    """Flatten filter mapping values into a set of all involved keys."""
    keys = set()
    for v in filter_mapping.values():
        if isinstance(v, (list, tuple)):
            keys.update(v)
        else:
            keys.add(v)
    return keys


def _exclude_keys(filters: dict, keys_to_exclude: Set[str]) -> dict:
    """Return a copy of the filters without the specified keys."""
    return {k: v for k, v in filters.items() if k not in keys_to_exclude}


def _is_active(filters: dict, keys: Set[str], default_value: Any) -> bool:
    """Check if any of the specified filter keys are currently active."""
    return any(filters.get(k) != default_value for k in keys)


def _apply_defaults(filters: dict, keys: Set[str], default_value: Any) -> dict:
    """Return a copy of filters with specified keys set to default_value."""
    new_filters = filters.copy()
    for k in keys:
        new_filters[k] = default_value
    return new_filters


def _is_unchanged(new_filters: dict, old_filters: dict, keys: Set[str]) -> bool:
    """Check if the values for the specified keys are identical in both dicts."""
    return all(new_filters.get(k) == old_filters.get(k) for k in keys)


def _process_selection(
    data: Any,
    filters: dict,
    mapping: dict,
    x_order: Optional[List[Any]],
    y_order: Optional[List[Any]],
    default_value: Any,
) -> dict:
    """Parse selection data and map it back to filter keys."""
    # points_by_attribute is a dict of {attribute: {values}}
    points_by_attribute = _parse_selected_points(data, x_order, y_order)
    range_x, range_y = _parse_selected_range(data, x_order, y_order)

    # Union points and range selections for standard Cartesian attributes
    selections = {
        "x": points_by_attribute.get("x", set()).union(range_x),
        "y": points_by_attribute.get("y", set()).union(range_y),
    }

    # Add any other attributes found in points (like 'id' or 'label')
    for attr, values in points_by_attribute.items():
        if attr not in ["x", "y"]:
            selections[attr] = values

    new_filters = filters.copy()
    for attr, selected_values in selections.items():
        filter_key = mapping.get(attr)
        if filter_key:
            _update_filters_from_selection_values(
                new_filters, filter_key, selected_values, default_value
            )

    return new_filters


def _update_filters_from_selection_values(
    filters: dict,
    filter_key: str | List[str] | Tuple[str, ...],
    selected_values: Set[Any],
    default_value: Any,
) -> None:
    """
    Update the filters dict based on the values selected for a specific data attribute.

    Handles both single-key (categorical) and multi-key (continuous range) mappings.
    """
    # 1. Handle Empty or Default Selection: Reset the key(s) to default_value
    # If the selection is empty, or if it contains only the default value (e.g. 'all' root node), reset.
    if not selected_values or (
        len(selected_values) == 1 and list(selected_values)[0] == default_value
    ):
        if isinstance(filter_key, (list, tuple)):
            for k in filter_key:
                filters[k] = default_value
        else:
            filters[filter_key] = default_value
        return

    # 2. Handle Continuous Range: Map min/max to two keys (e.g. [start_date, end_date])
    if isinstance(filter_key, (list, tuple)) and len(filter_key) == 2:
        sorted_vals = sorted(list(selected_values))
        filters[filter_key[0]] = sorted_vals[0]
        filters[filter_key[1]] = sorted_vals[-1]
        return

    # 3. Handle Categorical Selection: Map values to a single key (categorical_list)
    try:
        # Try to cast values to int if they look numeric (e.g. for hours)
        first_val = next(iter(selected_values))
        int(first_val)
        filters[filter_key] = sorted([int(v) for v in selected_values])
    except (ValueError, TypeError, StopIteration):
        filters[filter_key] = sorted(list(selected_values))
