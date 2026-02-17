"""
Generic filter configuration and SQL condition building.

Provides a declarative way to define filters and generate SQL WHERE clauses.
"""

from dataclasses import dataclass
from typing import Any, Callable, Literal

from dash import html
from .utils import format_title_case

__all__ = [
    "FilterType",
    "FilterConfig",
    "FilterRegistry",
    "resolve_filter_type",
]


##############################
##### Filter helpers
##############################
def resolve_filter_type(filter_config: "FilterConfig") -> "FilterType":
    """Resolve filter_type from string (registry lookup) or direct FilterType object."""
    if isinstance(filter_config.filter_type, str):
        return FILTER_TYPES[filter_config.filter_type]
    return filter_config.filter_type


def _default_display_formatter(value: Any) -> str:
    """Default formatter for filter values."""
    if value is None or value == "all":
        return "All"

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, list):
        if len(value) == 0:
            return "None"
        return ", ".join(str(v) for v in value)

    return str(value)


##############################
##### Filter structures #####
##############################
@dataclass
class FilterType:
    """
    Encapsulation of the logic for building SQL conditions.

    Args:
        name: Name of the filter type
        build_condition: Function that builds the SQL condition from the field name and value
        default_value: Default value for the filter type
    """

    name: str
    build_condition: Callable[[str, Any], str | None]
    default_value: Any


@dataclass
class FilterConfig:
    """
    Defines the mapping between UI filter state and SQL WHERE conditions.

    Args:
        filter_key: Key in filters dict (e.g., "cornsacks_only")
        field_name: SQL field name (e.g., "cornsacks_flag")
        filter_type: Name of filter type, or custom FilterType object
        display_name: Optional custom display name (defaults to title-cased filter_key)
        display_formatter: Optional custom formatter for display values (defaults to str)
        exclude_from_display: If True, this filter won't be shown in filter state displays
        clearable: If False, this filter cannot be cleared by the clear all filters button (defaults to True)
        source: Where the filter value comes from - "ui" for user interaction, "cache" for server-side auth
    """

    filter_key: str
    field_name: str
    filter_type: str | FilterType
    display_name: str | None = None
    display_formatter: Callable[[Any], str] | None = None
    exclude_from_display: bool = False
    clearable: bool = True
    source: Literal["ui", "cache"] = "ui"


class FilterRegistry:
    """
    Centralized registry for all filter configurations in a dashboard, enabling
    both full-dashboard and per-table filter configuration and management.
    """

    def __init__(self, groups: dict[str, list[FilterConfig]] | None = None):
        self._groups: dict[str, list[FilterConfig]] = groups or {}

    def add_group(self, name: str, configs: list[FilterConfig]) -> "FilterRegistry":
        """Add a filter configuration group to the registry."""
        self._groups[name] = configs
        return self

    def get_group(self, name: str) -> list[FilterConfig] | None:
        """Get filter configurations for a group by name."""
        return self._groups.get(name)

    def _get_defaults_with_filter(
        self, filter_predicate: Callable[[FilterConfig], bool] | None = None
    ) -> dict[str, Any]:
        """Helper method to get default values for filters, optionally filtered by a predicate."""
        defaults = {}
        for configs in self._groups.values():
            for filter_config in configs:
                if filter_predicate is None or filter_predicate(filter_config):
                    filter_type = resolve_filter_type(filter_config)
                    defaults[filter_config.filter_key] = filter_type.default_value
        return defaults

    def get_all_defaults(self) -> dict[str, Any]:
        """Get default values for all registered filters across all groups."""
        return self._get_defaults_with_filter()

    def get_clearable_defaults(self) -> dict[str, Any]:
        """Get default values for only clearable registered filters across all groups."""
        return self._get_defaults_with_filter(lambda config: config.clearable)

    def get_clearable_ui_values(
        self,
        filters: dict[str, Any] | None,
        filter_keys: list[str],
    ) -> tuple[Any, ...]:
        """
        Transform filter store values to UI component values for clearable filters.

        This handles the conversion from filter store format to UI component format:
        - Boolean filters: False -> [], True -> ["filter_key"] (for checklists)
        - Other filters: value as-is (for dropdowns, date pickers, etc.)

        Args:
            filters: Filter store values (None will use defaults).
            filter_keys: List of filter keys in desired return order.

        Returns:
            Tuple of UI component values in the order specified by filter_keys.
        """
        if filters is None:
            filters = self.get_all_defaults()

        ui_values = {}

        for config_group in self._groups.values():
            for config in config_group:
                if not config.clearable:
                    continue

                filter_key = config.filter_key
                filter_type = resolve_filter_type(config)
                store_value = filters.get(filter_key, filter_type.default_value)

                # boolean filters to checklist format
                if filter_type.name == "boolean":
                    ui_values[filter_key] = [filter_key] if store_value else []
                else:
                    # Other filter types use value as-is
                    ui_values[filter_key] = store_value

        return tuple(ui_values[key] for key in filter_keys)

    def format_display(self, filters: dict[str, Any]) -> list:
        """
        Format filter state for display using this registry's configuration.

        Args:
            filters: Current filter state

        Returns:
            List of Dash HTML components for display
        """
        components = []
        defaults = self.get_all_defaults()

        # TODO should be internal helper?
        config_lookup = {}
        for configs in self._groups.values():
            for config in configs:
                config_lookup[config.filter_key] = config

        for key, value in sorted(filters.items()):
            config: FilterConfig | None = config_lookup.get(key)

            if config and config.exclude_from_display:
                continue

            default_value = defaults.get(key)
            if value == default_value:
                continue

            # Format the name shown for the filter
            if config and config.display_name:
                display_name = config.display_name
            else:
                display_name = format_title_case(key)

            # Format the value
            if config and config.display_formatter:
                formatted_value = config.display_formatter(value)
            else:
                formatted_value = _default_display_formatter(value)

            # add a component for the filter name/value pair
            components.append(
                html.Div(
                    [
                        html.Div(
                            display_name,
                            style={"fontWeight": "bold", "marginBottom": "2px"},
                        ),
                        html.Div(formatted_value),
                    ],
                    style={"marginBottom": "12px"},
                )
            )

        # if no filters are active, show a message
        if not components:
            components.append(
                html.Div(
                    "All filters at default",
                    style={"fontStyle": "italic", "color": "#6c757d"},
                )
            )

        return components

    def get_ui_defaults(self) -> dict[str, Any]:
        """Get default values for UI-sourced filters only.

        Use this for client-side (dcc.Store) initialization. Server-side
        cache-sourced filters are managed server-side and should not be in the
        client store.
        """
        return self._get_defaults_with_filter(lambda config: config.source == "ui")

    def get_cache_filter_keys(self) -> list[str]:
        """Get list of filter keys be sourced from cache.

        Returns filter keys for all filters marked with source='cache'.
        These are typically auth/permission filters injected server-side.
        """
        cache_keys = []
        for configs in self._groups.values():
            for config in configs:
                if config.source == "cache":
                    cache_keys.append(config.filter_key)
        return cache_keys


##############################
##### The filters themselves #####
##############################
def _format_sql_value(v: Any) -> str:
    """Format a python value for a SQL condition (quoting strings, escaping)."""
    if isinstance(v, (int, float)):
        return str(v)
    escaped = str(v).replace("'", "''")
    return f"'{escaped}'"


def _categorical_condition(field: str, value: Any) -> str | None:
    """Helper for categorical filter - escaping quotes in lambda is messy."""
    if value and value != "all":
        return f"{field} = {_format_sql_value(value)}"
    return None


def _categorical_list_condition(field: str, value: Any) -> str | None:
    """Helper for categorical list filter - supports multiple values with IN clause."""
    if not value or value == "all" or (isinstance(value, list) and len(value) == 0):
        return None

    if isinstance(value, list):
        formatted = [_format_sql_value(v) for v in value]
        return f"{field} IN ({', '.join(formatted)})"

    # Single value fallback
    return f"{field} = {_format_sql_value(value)}"


def _prefix_condition(field: str, value: Any) -> str | None:
    """Helper for prefix filter (hierarchical paths) - uses LIKE with wildcard.
    Supports both single values and lists of values.
    """
    if not value or value == "all" or (isinstance(value, list) and len(value) == 0):
        return None

    if isinstance(value, list):
        # Escape each and wrap in ORs
        conditions = [f"{field} LIKE '{str(v).replace("'", "''")}%'" for v in value]
        return f"({' OR '.join(conditions)})"

    # Single value case
    escaped = str(value).replace("'", "''")
    return f"{field} LIKE '{escaped}%'"


# Registry of common filter types that can be reused across dashboards
# Filter logic can be defined in a lambda here, or in a helper function above,
# OR in a custom FilterType object within a dashboard app
FILTER_TYPES: dict[str, FilterType] = {
    "boolean": FilterType(
        name="boolean",
        build_condition=lambda field, value: f"{field} = true" if value else None,
        default_value=False,
    ),
    "categorical": FilterType(
        name="categorical",
        build_condition=_categorical_condition,
        default_value="all",
    ),
    "date_gte": FilterType(
        name="date_gte",
        build_condition=lambda field, value: f"{field} >= '{value}'" if value else None,
        default_value=None,
    ),
    "date_lte": FilterType(
        name="date_lte",
        build_condition=lambda field, value: f"{field} <= '{value}'" if value else None,
        default_value=None,
    ),
    "categorical_list": FilterType(
        name="categorical_list",
        build_condition=_categorical_list_condition,
        default_value="all",
    ),
    "prefix": FilterType(
        name="prefix",
        build_condition=_prefix_condition,
        default_value="all",
    ),
}
