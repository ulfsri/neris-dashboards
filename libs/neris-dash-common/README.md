The `neris-dash-common` library is a set of tools and resources to aid in developing dashboards for the NERIS project:
- Standardizing the means of accessing data, so optimizations can be leveraged
across apps. This includes cache configuration and the syncing of files to
- Providing common chart configurations, such that common NERIS data structures (e.g. TIERED||VALUE||SETS -> sunburst charts) can easily be visualized, and in a common way, helping to build a NERIS analytics visual brand.

Basics of using the `neris-dash-common` library for dashboard development:

## Data access and aggregation
- While functionality exists for connecting directly to a database, the primary
intended means of loading data is reading parquet files via DuckDB.
- Specify a `FilterRegistry` with a `group` of `FilterConfig`s for each data
table that will be queries based on filters.
- Optinally define one or more `AggregateStatGroup` to produce simple stats
for use in metric cards etc
- Define a class inheriting from `DuckParquetRelationS3` or `DuckParquetRelationFS`
for each of the files the dashboard will read from. Each class should include
    - `_parquet_path` to the file
    - `_filter_configs`, generally a list of `FilterConfig` accessed via `FilterRegsitry.get_group()`
    - Custom data querying and aggregation methods, as required's performance by callbacks
- Data Data from a `DuckParquetRelation*` can of course be materialized at any point: directly calling `.df()` will materialize the entire (filtered) file to a pandas DataFrame. However, DuckDB's performance is often vastly superior to that of pandas, as it only reads the rows and columns actually needed for a given transformation, and it is often preferable to push transformation logic down into the DuckDB query itself.

## Layout
- Define a `dcc.Store` for storing filter state, and point a callback updating all filters to it. This pattern allows multiple figure-updating callbacks to run in parallel, pointing to a common filter state, aiding performance and helping ensure consistency across figure-updating callbacks.

## Callbacks
