"""General-purpose utility functions, such as text formatting, string manipulation, and other general helpers."""

import json
import os

from functools import wraps
from time import time
from typing import Any

from dash_enterprise_libraries import data_sources as ds

__all__ = [
    "format_enum_text",
    "format_seconds_to_minutes_seconds",
    "format_hour",
    "format_title_case",
    "create_range_formatter",
    "log_timing",
    "get_cache_config",
]

# TODO do any of these really need to be public?


#########################
##### String utils
#########################
def format_enum_text(text: str) -> str:
    """Convert CAPS_UNDERSCORE_CASE to Reader Friendly Case."""
    return text.replace("_", " ").title()


def format_title_case(text: str) -> str:
    """Convert snake_case to Title Case."""
    return text.replace("_", " ").title()


def format_hour(hour: int) -> str:
    """Format hour (0-23) as 12a, 1a, 2a...11p."""
    if not isinstance(hour, int) or not (0 <= hour < 24):
        return str(hour)
    if hour == 0:
        return "12a"
    elif hour < 12:
        return f"{hour}a"
    elif hour == 12:
        return "12p"
    else:
        return f"{hour - 12}p"


def format_seconds_to_minutes_seconds(seconds: Any, default: str) -> str:
    """Format seconds as an 'Xm Ys' string."""
    if seconds is None:
        return default
    try:
        total_seconds = int(float(seconds))
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"
    except (ValueError, TypeError):
        return str(default)


def _is_consecutive_range(values: list, order: list) -> bool:
    """Check if values form a consecutive range in the given order."""
    if len(values) < 2:
        return False

    try:
        indices = sorted([order.index(v) for v in values])
        # Check if consecutive
        for i in range(len(indices) - 1):
            if indices[i + 1] - indices[i] != 1:
                return False
        return True
    except ValueError:
        return False


def create_range_formatter(
    order: list,
    item_formatter: Any = None,
) -> Any:
    """
    Create a formatter that displays consecutive values as ranges.

    Args:
        order: The ordered list of possible values (e.g., days of week, hours)
        item_formatter: Optional formatter for individual items (e.g., format_hour)

    Returns:
        A formatter function that handles lists, showing ranges when consecutive
    """
    if item_formatter is None:
        item_formatter = str

    def formatter(value: Any) -> str:
        if value is None or value == "all":
            return "All"

        if not isinstance(value, list):
            return item_formatter(value)

        if len(value) == 0:
            return "None"

        # Check if consecutive range
        if _is_consecutive_range(value, order):
            sorted_values = sorted(value, key=lambda v: order.index(v))
            return f"{item_formatter(sorted_values[0])} - {item_formatter(sorted_values[-1])}"

        # Otherwise, format each individually
        sorted_values = sorted(
            value, key=lambda v: order.index(v) if v in order else float("inf")
        )
        return ", ".join(item_formatter(v) for v in sorted_values)

    return formatter


#########################
##### Logging utils
#########################
def log_timing(func):
    """Decorator to log callback execution time."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time()
        result = func(*args, **kwargs)
        elapsed = time() - t0
        print(f"[Dashboard] {func.__name__}: {elapsed:.2f}s")
        return result

    return wrapper


#########################
##### Cache utils
#########################
def get_cache_config(cache_timeout_seconds: int) -> dict:
    """
    Get cache configuration based on environment.

    Simple is fine for single-worker setup (local in particular) but
    Redis is better for multiple workers, so cache isn't process-dependent.
    """
    redis_url = os.environ.get("REDIS_URL")

    if redis_url:
        return {
            "CACHE_TYPE": "redis",
            "CACHE_REDIS_URL": redis_url,
            "CACHE_DEFAULT_TIMEOUT": cache_timeout_seconds,
        }
    else:
        return {
            "CACHE_TYPE": "simple",
            "CACHE_DEFAULT_TIMEOUT": cache_timeout_seconds,
        }


#########################
##### DE utils
#########################


class _CredentialsWrapper:
    """
    Wrapper to provide consistent attribute access for credentials from either
    Dash Enterprise (object with attributes) or AWS Secrets Manager (dict).
    """

    def __init__(self, creds: Any):
        self._creds = creds

    def __getattr__(self, name: str) -> Any:
        # If creds is a dict (from AWS directly), access it that way
        if isinstance(self._creds, dict):
            if name in self._creds:
                return self._creds[name]
        # But if it's an object (from Dash Enterprise), use attribute access
        else:
            return getattr(self._creds, name)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )


def _get_credentials(credential_name: str) -> _CredentialsWrapper:
    """
    Get credentials from Dash Enterprise or AWS Secrets Manager based on context.

    In local context, fetches from AWS Secrets Manager (if available).
    In deployed contexts, uses Dash Enterprise data sources.
    """
    context = os.environ.get("DASHBOARD_CONTEXT", "local")

    if context == "local":
        try:
            from cloud.aws import get_secret
        except ImportError:
            raise ImportError("""
            cloud.neris.get_secret is not available. Credentials can only be
            accessed directly from AWS in local context, as part of the
            Analytics repo (not a deployed context).
            """)
        secret = get_secret(credential_name)
        if isinstance(secret, dict):
            return _CredentialsWrapper(secret)
        else:
            # If secret is a string, try to parse as JSON
            try:
                return _CredentialsWrapper(json.loads(secret))
            except (json.JSONDecodeError, TypeError):
                raise ValueError(
                    f"Secret {credential_name} must be a JSON object, got: {type(secret)}"
                )
    else:
        # Use Dash Enterprise data sources
        return _CredentialsWrapper(ds.credentials(credential_name))
