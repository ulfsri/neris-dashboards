"""
Functions that transform raw data into chart-ready formats.

These are NOT complete Plotly figures, but rather data preparation
utilities for building charts.
"""

from typing import Iterable, List

import pandas as pd
from .utils import format_enum_text


__all__ = [
    "split_hierarchy_path",
    "build_tiered_type_nodes",
    "format_sunburst_labels",
    "sort_values_not_reported_last",
    "build_contingency_table",
    "contingency_to_bubble_df",
]

HIERARCHY_SEPARATOR = "||"


def split_hierarchy_path(path: str) -> List[str]:
    """Split a hierarchical path string into individual tier levels."""
    return [part for part in path.split(HIERARCHY_SEPARATOR) if part is not None]


def build_tiered_type_nodes(
    paths: Iterable[str], root_label: str | None = None
) -> pd.DataFrame:
    """Build hierarchical node structure from a NERIS tiered-type string column,
    suitable for a sunburst chart etc.

    Parameters:
        - paths: iterable of hierarchical paths ('level1||level2||...').
        - root_label: optional, creates a single root node encompassing all
            paths. If not included, the chart will not have a total node.
    Returns:
        - DataFrame with columns: ids, labels, parents, values, cumulative_count,
          labels_with_counts, hover_text.
    """
    nodes: dict[str, dict] = {}

    counts_series = pd.Series(list(paths)).value_counts()

    # Add optional root node
    if root_label:
        nodes[""] = {
            "ids": "all",
            "labels": root_label,
            "parents": "",
            "values": 0,
            "cumulative_count": int(counts_series.sum()),
        }

    for path, count in counts_series.items():
        tiers = split_hierarchy_path(path)

        for i, tier in enumerate(tiers):
            # ids must be full paths to ensure uniqueness and support prefix filtering
            node_id = HIERARCHY_SEPARATOR.join(tiers[: i + 1])

            if i == 0:
                parent_id = "all" if root_label else ""
            else:
                parent_id = HIERARCHY_SEPARATOR.join(tiers[:i])

            if node_id not in nodes:
                nodes[node_id] = {
                    "ids": node_id,
                    "labels": format_enum_text(tier),
                    "parents": parent_id,
                    "values": 0,
                    "cumulative_count": 0,
                }

            nodes[node_id]["cumulative_count"] += int(count)
            if i == len(tiers) - 1:
                nodes[node_id]["values"] += int(count)

    df = pd.DataFrame(list(nodes.values()))
    return format_sunburst_labels(df)


def format_sunburst_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Add display labels and hover text based on cumulative counts and parents."""
    out = df.copy()

    # Calculate total count for percentages
    # If root node "all" exists, its cumulative_count is the total
    # Otherwise, sum of cumulative_count for nodes with parents == ""
    if "all" in out["ids"].values:
        total_count = out.loc[out["ids"] == "all", "cumulative_count"].iloc[0]
    else:
        total_count = out[out["parents"] == ""]["cumulative_count"].sum()

    def _format_label(row: pd.Series) -> str:
        label = row["labels"]
        count = int(row["cumulative_count"])
        if count <= 0:
            return label

        if total_count > 0:
            pct = (count / total_count) * 100
            return f"{label}<br>{count:,} ({pct:.1f}%)"
        return f"{label}<br>{count:,}"

    out["labels_with_counts"] = out.apply(_format_label, axis=1)

    def _build_hover_text(row: pd.Series) -> str:
        label = row["labels"]
        count = int(row["cumulative_count"])
        count_str = f"{count:,}"
        if total_count > 0:
            pct = (count / total_count) * 100
            count_str = f"{count_str} ({pct:.1f}%)"

        parent_id = row["parents"]
        if parent_id == "":
            return f"{label}: {count_str}"
        return f"{label}: {count_str}<br>Parent: {parent_id}"

    out["hover_text"] = out.apply(_build_hover_text, axis=1)
    return out


def sort_values_not_reported_last(values: list[str]) -> list[str]:
    """Sort values with NOT_REPORTED placed last."""

    def sort_key(x):
        return (x == "NOT_REPORTED", x)

    return sorted(values, key=sort_key)


def build_contingency_table(
    pairs_df: pd.DataFrame, row_field: str, col_field: str
) -> pd.DataFrame:
    """Build a contingency table from a dataframe of pairs."""
    if pairs_df.empty:
        return pd.DataFrame()
    table = pd.crosstab(pairs_df[row_field], pairs_df[col_field])
    return table


def contingency_to_bubble_df(
    contingency_table: pd.DataFrame,
    *,
    row_field: str,
    col_field: str,
    count_field: str = "count",
) -> pd.DataFrame:
    """Convert a contingency/cross-tab table into a long-form bubble dataframe.

    Only includes cells with count > 0. Row/column names are preserved in the
    provided field names.
    """
    bubble_rows: list[dict] = []
    if contingency_table.empty:
        return pd.DataFrame(columns=[row_field, col_field, count_field])

    for r in contingency_table.index:
        for c in contingency_table.columns:
            count = int(contingency_table.loc[r, c])
            if count > 0:
                bubble_rows.append({row_field: r, col_field: c, count_field: count})
    return pd.DataFrame(bubble_rows)
