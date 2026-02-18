"""
DuckDB-based data infrastructure for Dash dashboards.

This module provides lazy data loading with query pushdown capabilities,
using DuckDB to read parquet files from S3 with maximum performance.
"""

import duckdb
import json
import os
import threading

from abc import ABC
from pandas import (
    DataFrame,
    to_datetime,
    read_sql,
    notna,
)
from pathlib import Path
from sqlalchemy import create_engine, URL, Engine
from typing import Any, List, Literal, Dict


from neris_dash_common.aggregations import AggregateStatGroup
from neris_dash_common.auth import get_auth_cache_value
from neris_dash_common.filters import (
    FilterConfig,
    FilterType,
    resolve_filter_type,
)
from neris_dash_common.time_series import (
    TimeSeriesInterval,
    get_sql_expression,
    RollingWindow,
)
from neris_dash_common.utils import _get_credentials


__all__ = [
    "initialize_data_sources",
    "get_schema_prefix",
    "load_data_from_sql",
    "DuckParquetRelationS3",
    "DuckParquetRelationFS",
]

#########################
##### Dash Enterprise data sources
#########################


# TODO: find a better fix for this. I was running into circular import issues
# with the data_sources module, and this fixes them, at least for data sourced
# from s3. If we really need to do soething like this, we should find a way to
# cache the credentials themselves and then pass them into the connection-getting
# functions. As-is, DuckDBManager is caching the connection, so the credentials
# are only requested once per process, but the db connection is being called
# every time a callback is run.
def initialize_data_sources(source_type: Literal["s3", "db"]):
    """
    Initialize the data_sources module early to avoid circular import issues.

    This should be called during app initialization, before callbacks are registered.
    The module uses deferred imports that need to be resolved before callbacks run.
    """
    from dash_enterprise_libraries import data_sources

    # for whatever reason the db data source in dash enterprise is suffixed with "analytics" rather than "db"
    source_suffix: Dict[str, str] = {
        "s3": "s3",
        "db": "analytics",
    }

    context = os.environ.get("DASHBOARD_CONTEXT", "local")
    credential_name = f"{context}_{source_suffix[source_type]}"

    try:
        data_sources.credentials(credential_name)
    except Exception:
        pass


#############################
##### Database via pandas/sqlalchemy
#############################
def get_schema_prefix() -> str:
    """Get the schema prefix for the current environment."""
    # HOST_USER is set in the dev container, but when deployed this should fall back to "root",
    # since that's the user running dbt in the deployed contexts.
    return f"_{os.environ.get('HOST_USER', 'root')}__"


# TODO cache the credentials so this doesn't get called every time a callback is run
# See TODO above on initialize_data_sources.
def _get_db_engine() -> Engine:
    """Get a SQLAlchemy engine for the NERIS database, using context-specific credentials from dash enterprise."""
    context = os.environ.get("DASHBOARD_CONTEXT")
    creds = _get_credentials(f"{'dev' if context == 'local' else context}_analytics")
    host = "0.0.0.0" if context == "local" else creds.host

    engine = create_engine(
        url=URL.create(
            drivername="postgresql",
            username=creds.username,
            password=creds.password,
            host=host,
            port=creds.port,
            database=creds.database,
        )
    )
    engine.connect()
    print(f"Connected to {host} 🚀")
    return engine


def _align_types(
    df: DataFrame,
    parse_dates: list[str] | None = None,
    dtype: dict[str, str] | None = None,
    json_columns: list[str] | None = None,
) -> DataFrame:
    """Helper to apply dtype conversions, parse dates, and parse JSON columns on a pandas DataFrame."""
    if parse_dates:
        for col in parse_dates:
            if col in df.columns:
                df[col] = to_datetime(df[col], errors="coerce")
                if hasattr(df[col].dtype, "tz") and df[col].dt.tz is not None:
                    df[col] = df[col].dt.tz_localize(None)

    if dtype:
        for col, target_dtype in dtype.items():
            if col in df.columns:
                if target_dtype == "boolean":
                    df[col] = df[col].astype("boolean")
                elif target_dtype == "category":
                    df[col] = df[col].astype("category")
                else:
                    df[col] = df[col].astype(target_dtype)

    if json_columns:
        for col in json_columns:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: json.loads(x) if notna(x) and x else None
                )

    return df


def load_data_from_sql(
    query: str,
    engine: Engine | None = None,
    parse_dates: list[str] | None = None,
    dtype: dict[str, str] | None = None,
    json_columns: list[str] | None = None,
) -> DataFrame:
    """Load data from SQL query using the NERIS engine.

    parse_dates: list of column names to parse as datetimes
    dtype: optional mapping of column name to dtype; applied after load
    json_columns: columns containing JSON strings to parse (only needed if reading from old exports)
    """
    if engine is None:
        engine = _get_db_engine()

    df = read_sql(query, engine, parse_dates=parse_dates)
    return _align_types(df, parse_dates, dtype, json_columns)


#############################
##### Parquet via DuckDB
#############################
def _get_duckdb_connection() -> duckdb.DuckDBPyConnection:
    """Get a DuckDB connection, configured with S3 credentials based on context."""
    con = duckdb.connect()
    con.execute("SET parquet_metadata_cache=true;")

    return con


def _get_s3_path(path: str) -> str:
    """Get the full S3 path for a given relative path or table name."""
    # Not sure how this could happen...but if it's already an S3 path, return it as-is.
    if path.startswith("s3://"):
        return path

    context = os.environ.get("DASHBOARD_CONTEXT", "local")
    bucket = f"neris-analytics-exports-{context}"

    return f"s3://{bucket}/{path}"


class DuckDBManager:
    """
    Thread-safe manager for DuckDB connections in Dash apps.

    Each thread gets its own connection to avoid concurrency issues,
    since Dash callbacks run in parallel. It's not clear to me if this is
    actually necessary for deployed applications because those use gunicorn
    with multiple processes (only one thread per process I _think_), but it
    should be harmless if not needed.
    """

    _thread_local = threading.local()

    @classmethod
    def get_s3_credentials(cls):
        """Get S3 credentials based on the current context."""
        context = os.environ.get("DASHBOARD_CONTEXT", "local")
        credential_name = (
            "analytics-export-s3-access-key-local"
            if context == "local"
            else f"{context}_s3"
        )
        return _get_credentials(credential_name)

    # Is this actually needed for deployed Dash apps? What is DE actually doing?
    # probably safe for sync and threaded workers, but maybe not for async workers
    @classmethod
    def get_connection(
        cls, storage_type: Literal["s3", "filesystem"]
    ) -> duckdb.DuckDBPyConnection:
        """Get or create a thread-local DuckDB connection."""
        if (
            not hasattr(cls._thread_local, "connection")
            or cls._thread_local.connection is None
        ):
            con = _get_duckdb_connection()

            if storage_type == "s3":
                creds = cls.get_s3_credentials()

                # httpfs extension for S3 support
                con.execute("INSTALL httpfs; LOAD httpfs;")
                con.execute(f"SET s3_access_key_id='{creds.access_key_id}';")
                con.execute(f"SET s3_secret_access_key='{creds.secret_access_key}';")
                con.execute(f"SET s3_region='{creds.region}';")

            cls._thread_local.connection = con
            print(f"🦆 DuckDB connection to {storage_type} ready 🦆")

        return cls._thread_local.connection


class _DuckParquetRelationBase(ABC):
    """
    Abstract base class for DuckDB relations to parquet files. Lazily builds a query plan that
    accumulates query logic and only executes data reads when a materialization
    is requested via .df(), .count(), or other custom methods.

    - apply_filters() applies UI filters using FilterConfig objects
    - add_where() adds direct SQL WHERE conditions
    - set_projection() adds column projections
    - add_join() adds table joins

    This class is intended to be subclassed for parquet files stored in different locations,
    (S3 or filesystem) for handling of storage-specific initialization.
    Domain-specific datasets (e.g., IncidentsRelation or CasualtyRescuesRelation)
    should inherit from one of these storage-specific subclasses.

    """

    _parquet_path: str
    _filter_configs: list[FilterConfig] | None = None
    _export_fields: list[str] | None = None

    ##############################
    ##### Initialization with filter state
    ##############################
    def __init__(self, filters: dict[str, Any] | None = None):
        # Initialize query plan components
        self._filters: List[str] = []
        self._projections: List[str] | None = None
        self._joins: List[tuple] = []

        # Apply filters from the filter dict automatically
        if filters:
            self._apply_filters(filters)

    def _apply_filters(self, filters: dict[str, Any]) -> "_DuckParquetRelationBase":
        """
        Apply filters using the table's filter configurations.

        Converts a dictionary of filter key/value pairs into a list of SQL WHERE
        conditions, then adds them to the query plan. For UI-sourced filters,
        reads values from the provided filters dict. For cache-sourced filters
        (e.g. auth restrictions), reads values directly from the Flask session,
        keeping them invisible to and immutable by the client.
        """
        if not self._filter_configs:
            return self

        for filter_config in self._filter_configs:
            if filter_config.source == "cache":
                filter_value = get_auth_cache_value(filter_config.filter_key)
            else:
                filter_value = filters.get(filter_config.filter_key)

            if filter_value is None:
                continue

            filter_type: FilterType = resolve_filter_type(filter_config)
            condition: str | None = filter_type.build_condition(
                filter_config.field_name, filter_value
            )

            if condition:
                self.add_where(condition)

        return self

    ##############################
    ##### Query plan methods
    ##############################
    def add_where(self, condition: str) -> "_DuckParquetRelationBase":
        """Add a WHERE condition to the query plan."""
        self._filters.append(condition)
        return self

    def add_join(
        self, other_table: "_DuckParquetRelationBase", condition: str, how: str
    ) -> "_DuckParquetRelationBase":
        """Add a join to the query plan."""
        self._joins.append((other_table, condition, how))
        return self

    def set_projection(self, *columns: str) -> "_DuckParquetRelationBase":
        """Set column projections for the query plan."""
        self._projections = list(columns)
        return self

    def _build_relation(
        self, include_projections: bool = True
    ) -> duckdb.DuckDBPyRelation:
        """Build the DuckDB relation by assembling the query plan from the query plan components.

        Args:
            include_projections: Whether to apply column projections. Set to False
                for operations like count() that don't need specific columns.
        """
        # Start with base parquet file, then filter, join, and project as needed
        # read_parquet just reads the file's metadata, not the data itself
        rel = self._connection.read_parquet(self.parquet_path)

        for condition in self._filters:
            rel = rel.filter(condition)

        for other_table, condition, how in self._joins:
            other_rel = other_table._build_relation(include_projections=True)
            rel = rel.join(other_rel, condition=condition, how=how)

        if include_projections and self._projections:
            rel = rel.project(", ".join(self._projections))

        return rel

    ##############################
    ##### Query execution methods
    ##############################
    def df(self) -> DataFrame:
        """Materialize the query plan to a pandas DataFrame."""
        rel = self._build_relation(include_projections=True)
        return rel.df()

    def count(self) -> int:
        """Execute count on the query plan without full materialization."""
        rel = self._build_relation(include_projections=False)
        return rel.count("*").fetchone()[0]

    def distinct(self, column: str) -> list:
        """Get distinct values from a column."""
        rel = self._build_relation()
        distinct_rel = rel.project(column).distinct()
        results = distinct_rel.fetchall()
        return [row[0] for row in results]

    def aggregate(
        self, *expressions: str, group_by: List[str] | None = None
    ) -> DataFrame:
        """Add aggregations to the query plan and materialize them to a DataFrame.

        Args:
            *expressions: SQL aggregation expressions (e.g., "SUM(col)", "COUNT(*)")
            group_by: Optional list of columns/expressions to group by
        """
        rel = self._build_relation()

        agg_sql = ", ".join(expressions)
        group_sql = "" if not group_by else ", ".join(group_by)

        return rel.aggregate(agg_sql, group_sql).df()

    def sample(self, rows: int) -> DataFrame:
        """Sample a fixed number of rows from the relation using DuckDB sampling."""
        rel = self._build_relation()
        return rel.query(
            "rel_to_sample", f"SELECT * FROM rel_to_sample USING SAMPLE {rows} ROWS"
        ).df()

    def time_series_counts(
        self,
        date_column: str,
        interval: TimeSeriesInterval = "daily",
        rolling_window: RollingWindow | None = None,
    ) -> DataFrame:
        """Get time series counts grouped by the specified time interval.

        This is a generic method that can be used by any _DuckParquetRelationBase subclass
        to compute time-based aggregations. Only the aggregated results are materialized.

        Args:
            date_column: The column to use for time grouping
            interval: The time interval for grouping
            rolling_window: Optional RollingWindow configuration
        """
        group_expr = get_sql_expression(interval, date_column)

        expressions = [f"{group_expr} as date", "COUNT(*) as count"]
        if rolling_window:
            end_row = "CURRENT ROW" if rolling_window.include_current else "1 PRECEDING"
            start_offset = (
                rolling_window.window - 1
                if rolling_window.include_current
                else rolling_window.window
            )

            expressions.append(
                f"""AVG(COUNT(*)) OVER (
                        ORDER BY {group_expr} ROWS
                        BETWEEN {start_offset} PRECEDING AND {end_row}
                    ) as rolling_window_avg
                """
            )

        result = self.aggregate(*expressions, group_by=[group_expr])
        result["date"] = to_datetime(result["date"])
        return result.sort_values("date").reset_index(drop=True)

    def get_export_data(self) -> DataFrame:
        """Get data for CSV export with only the specified export fields."""
        if self._export_fields is None:
            return self.df()
        return self.set_projection(*self._export_fields).df()

    def get_sampled_points(
        self,
        limit: int = 10000,
        bounds: list[list[float]] | None = None,
        x_col: str = "x",
        y_col: str = "y",
    ) -> DataFrame:
        """Get sampled points, optionally filtered by bounding box."""
        # Always filter out nulls and [0,0] fallbacks at the file-read level
        rel = self.add_where(
            f"{x_col} IS NOT NULL AND {y_col} IS NOT NULL AND {x_col} != 0 AND {y_col} != 0"
        )

        if bounds:
            south, west = bounds[0]
            north, east = bounds[1]
            where_bounds = f"{y_col} BETWEEN {south} AND {north} AND {x_col} BETWEEN {west} AND {east}"
            rel = rel.add_where(where_bounds)

        return rel.sample(limit)

    def get_bounds(
        self, x_col: str = "x", y_col: str = "y"
    ) -> list[list[float]] | None:
        """Get the bounding box of all filtered records. Note that these are for all records
        matching the current filter state, not just the sampled points, which could conceivably
        lead to some weirdness."""
        agg = f"MIN({y_col}) as min_y, MIN({x_col}) as min_x, MAX({y_col}) as max_y, MAX({x_col}) as max_x"
        res = self.add_where(
            f"{x_col} IS NOT NULL AND {y_col} IS NOT NULL AND {x_col} != 0 AND {y_col} != 0"
        ).aggregate(agg)

        if res.empty or res.iloc[0].isna().any():
            return None

        row = res.iloc[0]
        # Leaflet bounds format: [[south, west], [north, east]]
        return [[row["min_y"], row["min_x"]], [row["max_y"], row["max_x"]]]

    def get_last_updated(self) -> str:
        """Get the last modified time of the parquet file as a formatted string."""
        raise NotImplementedError(
            "Subclasses must implement get_last_updated() if needed"
        )

    ##############################
    ##### Helpers for child-specific query execution methods #####
    ##############################
    def _calculate_aggregate_stats(
        self, aggregate_stat_group: AggregateStatGroup
    ) -> dict[str, Any]:
        """
        Helper method to calculate aggregate statistics for an AggregateStatGroup.

        This is a generic, internal helper for use in _DuckParquetRelationBase
        subclasses. Child classes should define domain-specific methods (e.g.,
        get_summary_card_stats) that call this with their specific
        AggregateStatGroup configuration.
        """
        # Return defaults if filter state results in no rows
        if self.count() == 0:
            return aggregate_stat_group.get_defaults()

        # Get aggregated data
        stats_df = self.aggregate(*aggregate_stat_group.get_expressions())
        row = stats_df.iloc[0]

        # Extract values, using defaults for None/NaN
        return aggregate_stat_group.extract_values(row)


class DuckParquetRelationS3(_DuckParquetRelationBase):
    """
    DuckDB relation to a parquet file stored in S3.

    Required attributes:
    - _parquet_path: a relative S3 key (e.g., "dash/cornsacks/incidents.parquet")
    - _filter_configs: a list of FilterConfig objects

    """

    def __init__(self, filters: dict[str, Any] | None = None):
        self.context = os.environ.get("DASHBOARD_CONTEXT", "local")
        self.bucket = f"neris-analytics-exports-{self.context}"
        self.parquet_path = _get_s3_path(self._parquet_path)
        self._connection = DuckDBManager.get_connection(storage_type="s3")
        super().__init__(filters)

    def get_last_updated(self) -> str:
        """Get the last modified time of the parquet file from S3."""
        try:
            import boto3
            from botocore.exceptions import ClientError

            creds = DuckDBManager.get_s3_credentials()

            s3_client = boto3.client(
                "s3",
                aws_access_key_id=creds.access_key_id,
                aws_secret_access_key=creds.secret_access_key,
                region_name=creds.region,
            )
            response = s3_client.head_object(Bucket=self.bucket, Key=self._parquet_path)
            last_modified = response["LastModified"]

            return last_modified.strftime("%Y-%m-%d %H:%M:%S UTC")
        except (ClientError, Exception):
            return ""


class DuckParquetRelationFS(_DuckParquetRelationBase):
    """
    DuckDB relation to a parquet file stored on the local filesystem.

    Required attributes:
    - _parquet_path: an absolute path (e.g., "/opt/dash/data/cornsacks/incidents.parquet")
    - _filter_configs: a list of FilterConfig objects
    """

    def __init__(self, filters: dict[str, Any] | None = None):
        self.parquet_path = self._parquet_path
        self._connection = DuckDBManager.get_connection(storage_type="filesystem")
        super().__init__(filters)

    def get_last_updated(self) -> str:
        """Get the last modified time of the parquet file from the filesystem."""
        try:
            from datetime import datetime

            file_path = Path(self.parquet_path)

            mtime = file_path.stat().st_mtime
            last_modified = datetime.utcfromtimestamp(mtime)

            return last_modified.strftime("%Y-%m-%d %H:%M:%S UTC")
        except (OSError, Exception):
            return ""
