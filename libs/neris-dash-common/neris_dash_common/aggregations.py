from dataclasses import dataclass

from typing import Any, Callable
from pandas import isna


__all__ = [
    "AggregateStat",
    "AggregateStatGroup",
]


def _default_string_extractor(value: Any, default: Any) -> str:
    """Default value extractor that converts values to strings."""
    if value is None or isna(value):
        return str(default)

    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


@dataclass
class AggregateStat:
    """Configuration for an aggregation statistic.

    Args:
        aggregation_expr: SQL aggregation expression (e.g., "COUNT(*)", "SUM(col)")
        column_alias: Column alias in result (e.g., "total_count")
        default_value: Default value if result is None or count is 0
        value_extractor: Optional custom function to extract/transform the value from the row.
            Signature: (value, default_value) -> extracted_value
            If None, uses default behavior: str(value) if value is not None else str(default_value)
    """

    aggregation_expr: str
    column_alias: str
    default_value: Any
    value_extractor: Callable[[Any, Any], Any] = _default_string_extractor


@dataclass
class AggregateStatGroup:
    """Configuration for an aggregation statistic group."""

    stats: list[AggregateStat]

    def get_defaults(self) -> dict[str, Any]:
        """Return dictionary of default values for when count == 0."""
        return {stat.column_alias: stat.default_value for stat in self.stats}

    def get_expressions(self) -> list[str]:
        """Return list of SQL aggregation expressions with aliases."""
        return [
            f"{stat.aggregation_expr} as {stat.column_alias}" for stat in self.stats
        ]

    def extract_values(self, row: Any) -> dict[str, Any]:
        """Extract values from a DataFrame row, using defaults for None/NaN."""
        result = {}
        for stat in self.stats:
            value = row[stat.column_alias]
            result[stat.column_alias] = stat.value_extractor(value, stat.default_value)
        return result
