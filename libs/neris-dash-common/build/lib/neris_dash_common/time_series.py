"""Time series utilities and interval configurations."""

from dataclasses import dataclass
from typing import Callable, Literal
from datetime import datetime

__all__ = [
    "TimeSeriesInterval",
    "IntervalConfig",
    "get_sql_expression",
    "get_style_config",
    "RollingWindow",
]

TimeSeriesInterval = Literal["daily", "weekly", "monthly", "quarterly"]


@dataclass
class IntervalConfig:
    """Complete configuration for a time series interval."""

    sql_expression_template: str
    x_tickformat: str
    hover_date_format: str
    title_formatter: Callable[[datetime, datetime], str]


@dataclass
class IntervalStyleConfig:
    """Styling configuration for a time series interval (for backward compatibility)."""

    x_tickformat: str
    hover_date_format: str
    title_formatter: Callable[[datetime, datetime], str]


@dataclass
class RollingWindow:
    """Configuration for a rolling window for a time series trendline."""

    window: int
    include_current: bool


def _format_daily_title(min_date: datetime, max_date: datetime) -> str:
    """Format title for daily interval."""
    if min_date != max_date:
        return f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
    return min_date.strftime("%Y-%m-%d")


def _format_weekly_title(min_date: datetime, max_date: datetime) -> str:
    """Format title for weekly interval."""
    if min_date != max_date:
        return (
            f"Week of {min_date.strftime('%Y-%m-%d')} to "
            f"Week of {max_date.strftime('%Y-%m-%d')}"
        )
    return f"Week of {min_date.strftime('%Y-%m-%d')}"


def _format_monthly_title(min_date: datetime, max_date: datetime) -> str:
    """Format title for monthly interval."""
    if min_date != max_date:
        return f"{min_date.strftime('%B %Y')} to {max_date.strftime('%B %Y')}"
    return min_date.strftime("%B %Y")


def _format_quarterly_title(min_date: datetime, max_date: datetime) -> str:
    """Format title for quarterly interval."""
    min_q = f"Q{(min_date.month - 1) // 3 + 1}"
    max_q = f"Q{(max_date.month - 1) // 3 + 1}"
    if min_date != max_date:
        return f"{min_q} {min_date.year} to {max_q} {max_date.year}"
    return f"{min_q} {min_date.year}"


# Both data assembly and styling interval configurations defined here
TIME_SERIES_INTERVALS: dict[str, IntervalConfig] = {
    "daily": IntervalConfig(
        sql_expression_template="CAST({date_column} AS DATE)",
        x_tickformat="%Y-%m-%d",
        hover_date_format="%Y-%m-%d",
        title_formatter=_format_daily_title,
    ),
    "weekly": IntervalConfig(
        sql_expression_template="DATE_TRUNC('week', {date_column})",
        x_tickformat="%Y-%m-%d",
        hover_date_format="Week of %Y-%m-%d",
        title_formatter=_format_weekly_title,
    ),
    "monthly": IntervalConfig(
        sql_expression_template="DATE_TRUNC('month', {date_column})",
        x_tickformat="%b %Y",
        hover_date_format="%B %Y",
        title_formatter=_format_monthly_title,
    ),
    "quarterly": IntervalConfig(
        sql_expression_template="DATE_TRUNC('quarter', {date_column})",
        x_tickformat="%Y",  # Plotly doesn't support %q in strftime
        hover_date_format="%B %Y",  # Shows month and year (quarter start month)
        title_formatter=_format_quarterly_title,
    ),
}


def get_sql_expression(interval: TimeSeriesInterval, date_column: str) -> str:
    """Get SQL grouping expression for a time series interval."""
    config = TIME_SERIES_INTERVALS[interval]
    return config.sql_expression_template.format(date_column=date_column)


def get_style_config(interval: TimeSeriesInterval) -> IntervalStyleConfig:
    """Get styling configuration for the specified time series interval."""
    config = TIME_SERIES_INTERVALS[interval]
    return IntervalStyleConfig(
        x_tickformat=config.x_tickformat,
        hover_date_format=config.hover_date_format,
        title_formatter=config.title_formatter,
    )
