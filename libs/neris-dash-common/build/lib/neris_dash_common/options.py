"""Dropdown/select option builders."""

from typing import Iterable, Callable, Any, List

__all__ = ["build_options"]


def build_options(
    values: Iterable[Any],
    *,
    all_label: str | None = None,
    all_value: str = "all",
    format_label: Callable[[Any], str] | None = None,
) -> List[dict]:
    """Build a list of options for a dropdown."""
    options = []
    if all_label is not None:
        options.append({"label": all_label, "value": all_value})
    for v in values:
        options.append({"label": format_label(v) if format_label else v, "value": v})
    return options
