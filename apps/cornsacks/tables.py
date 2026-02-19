"""
Table class definitions for the Cornsacks dashboard.

Defines domain-specific table classes that encapsulate data access
and business logic for Cornsacks incident data.
"""

from typing import Any, Final

from neris_dash_common import (
    DuckParquetRelationS3,
    AggregateStat,
    AggregateStatGroup,
    FilterConfig,
    FilterRegistry,
    format_seconds_to_minutes_seconds,
    format_hour,
    create_range_formatter,
)

# TODO move this to the shared module
# Define custom formatters for specific filter types
DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
HOUR_ORDER = list(range(24))

day_of_week_formatter = create_range_formatter(DAY_ORDER)
hour_formatter = create_range_formatter(HOUR_ORDER, format_hour)

FILTER_REGISTRY: Final[FilterRegistry] = FilterRegistry(
    {
        "incidents": [
            FilterConfig(
                "authorized_neris_ids",
                "neris_id_dept",
                "categorical_list",
                source="cache",
                exclude_from_display=True,
                clearable=False,
            ),
            FilterConfig("csst_hazard_only", "csst_hazard_flag", "boolean"),
            FilterConfig("electric_hazard_only", "electric_hazard_flag", "boolean"),
            FilterConfig("powergen_hazard_only", "powergen_hazard_flag", "boolean"),
            FilterConfig(
                "medical_oxygen_hazard_only", "medical_oxygen_hazard_flag", "boolean"
            ),
            FilterConfig("aid_direction", "aid_direction", "categorical"),
            FilterConfig("department_state", "department_state", "categorical"),
            FilterConfig(
                "neris_id_dept",
                "neris_id_dept",
                "categorical",
                display_name="Department NERIS ID",
            ),
            FilterConfig("start_date", "call_create", "date_gte"),
            FilterConfig("end_date", "call_create", "date_lte"),
            FilterConfig(
                "day_of_week",
                "call_create_day_of_week",
                "categorical_list",
                display_formatter=day_of_week_formatter,
            ),
            FilterConfig(
                "hour",
                "call_create_hour",
                "categorical_list",
                display_formatter=hour_formatter,
            ),
            FilterConfig(
                "location_use_path",
                "COALESCE(type_location_use, 'No Location Use Provided')",
                "prefix",
            ),
        ],
        "incident_types": [
            FilterConfig(
                "primary_only",
                "primary_type",
                "boolean",
                exclude_from_display=True,
            ),
            FilterConfig("type_incident", "type_incident", "prefix"),
        ],
        "casualty_rescues": [
            FilterConfig("type_ff_nonff", "type_ff_nonff", "categorical"),
        ],
    }
)

INCIDENTS_SUMMARY_CARD_STATS: Final[AggregateStatGroup] = AggregateStatGroup(
    [
        AggregateStat("COUNT(*)", "total_count", "0"),
        AggregateStat("SUM(unit_response_count)", "total_unit_responses", "0"),
        AggregateStat(
            "CAST(COALESCE(QUANTILE_CONT(duration, 0.9), 0) AS BIGINT)",
            "p90_duration",
            "0m 0s",
            value_extractor=format_seconds_to_minutes_seconds,
        ),
        AggregateStat("SUM(csst_hazard_flag)", "csst_count", "0"),
        AggregateStat("SUM(electric_hazard_flag)", "electric_count", "0"),
        AggregateStat("SUM(powergen_hazard_flag)", "powergen_count", "0"),
        AggregateStat("SUM(medical_oxygen_hazard_flag)", "medical_oxygen_count", "0"),
        AggregateStat("SUM(displacement_count)", "total_displacements", "0"),
        AggregateStat("SUM(rescue_animal)", "total_rescue_animals", "0"),
        AggregateStat("SUM(exposure_count)", "total_exposures", "0"),
    ]
)


class AidRelation(DuckParquetRelationS3):
    _parquet_path = "dash/incident_basics/aids.parquet"
    _export_fields = [
        "neris_id_incident",
        "aid_concat",
    ]

    def get_path_counts(self, max_tiers: int | None = None):
        """Get path counts for incident types.

        If max_tiers is provided, paths will be truncated to that many tiers.
        """
        if max_tiers:
            # truncate the path to max_tiers
            path_expr = f"array_to_string(list_slice(string_split(aid_concat, '||'), 1, {max_tiers}), '||')"
            agg = f"{path_expr} as aid_concat, COUNT(*) as count"
            group_by = [path_expr]
        else:
            agg = "aid_concat, COUNT(*) as count"
            group_by = ["aid_concat"]

        return self.aggregate(agg, group_by=group_by)


class IncidentTypesRelation(DuckParquetRelationS3):
    _parquet_path = "dash/incident_basics/incident_types.parquet"
    _filter_configs = FILTER_REGISTRY.get_group("incident_types")
    _export_fields = [
        "neris_id_incident",
        "type_incident",
        "primary_type",
    ]

    def get_path_counts(self):
        """Get path counts for incident types."""
        agg = "type_incident, COUNT(*) as count"
        group_by = ["type_incident"]

        return self.aggregate(agg, group_by=group_by)


class CasualtyRescuesRelation(DuckParquetRelationS3):
    _parquet_path = "dash/incident_basics/casualty_rescues.parquet"
    _filter_configs = FILTER_REGISTRY.get_group("casualty_rescues")
    _export_fields = [
        "neris_id_incident",
        "type_ff_nonff",
        "age_bin",
        "type_casualty",
        "type_rescue",
    ]

    def get_contingency_counts(self):
        """Get casualty × rescue contingency counts."""

        agg = "type_casualty, type_rescue, COUNT(*) as count"
        group_by = ["type_casualty", "type_rescue"]

        return self.aggregate(agg, group_by=group_by)

    def get_demographic_counts(self):
        """Get counts for all demographic fields."""

        agg = "type_race, type_gender, type_ff_nonff, age_bin, COUNT(*) as count"
        group_by = ["type_race", "type_gender", "type_ff_nonff", "age_bin"]

        return self.aggregate(agg, group_by=group_by)


class IncidentsRelation(DuckParquetRelationS3):
    _parquet_path = "dash/incident_basics/incidents.parquet"
    _filter_configs = FILTER_REGISTRY.get_group("incidents")
    _export_fields = [
        "neris_id_incident",
        "neris_id_dept",
        "department_name",
        "department_state",
        "incident_type",
        "call_create",
        "call_create_day_of_week",
        "call_create_hour",
        "duration",
        "type_location_use",
        "csst_hazard_flag",
        "electric_hazard_flag",
        "powergen_hazard_flag",
        "medical_oxygen_hazard_flag",
        "aid_direction",
        "unit_response_count",
        "displacement_count",
        "rescue_animal",
        "exposure_count",
        "civic_location",
        "point_origin",
        "x",
        "y",
    ]

    # Custom init needed for cross-relation filters
    def __init__(self, filters: dict[str, Any] | None = None):
        super().__init__(filters)
        if filters:
            self._apply_cross_relation_filters(filters)

    def _apply_cross_relation_filters(self, filters: dict[str, Any]) -> None:
        """Check for filters that require joining other tables and apply them."""
        if filters.get("type_incident") and filters["type_incident"] != "all":
            types = IncidentTypesRelation(filters)
            self.add_join(types, "neris_id_incident", "inner")

    def get_incident_types(self, primary_only: bool = False) -> IncidentTypesRelation:
        """Get incident types relation for these here filtered incidents."""
        incident_types = IncidentTypesRelation({"primary_only": primary_only})
        return incident_types.add_join(self, "neris_id_incident", "inner")

    def get_aid(self) -> AidRelation:
        """Get aid relation for these here filtered incidents."""
        aid = AidRelation({})
        return aid.add_join(self, "neris_id_incident", "inner")

    def get_casualty_rescues(
        self, filters: dict[str, Any] = None
    ) -> CasualtyRescuesRelation:
        """Get casualty rescues relation for these here filtered incidents."""
        casualty_rescues = CasualtyRescuesRelation(filters or {})
        return casualty_rescues.add_join(self, "neris_id_incident", "inner")

    def get_summary_card_stats(self) -> tuple[str, ...]:
        """Get comprehensive incident statistics formatted for summary cards."""
        stats = self._calculate_aggregate_stats(INCIDENTS_SUMMARY_CARD_STATS)

        # Get casualty rescue count from cross-relation
        casualty_rescue_count = self.get_casualty_rescues({}).count()

        # Return tuple in the order required by card Outputs
        return (
            stats.get("total_count", "0"),
            stats.get("total_unit_responses", "0"),
            stats.get("p90_duration", "0m 0s"),
            stats.get("csst_count", "0"),
            stats.get("electric_count", "0"),
            stats.get("powergen_count", "0"),
            stats.get("medical_oxygen_count", "0"),
            f"{casualty_rescue_count:,}",
            stats.get("total_displacements", "0"),
            stats.get("total_rescue_animals", "0"),
            stats.get("total_exposures", "0"),
        )

    def unique_department_states(self) -> list[str]:
        """Get sorted list of unique states."""
        return sorted(self.distinct("department_state"))

    def unique_departments(self) -> list[dict[str, str]]:
        """Get sorted list of unique department names, states and neris_id_dept values."""
        agg = "department_name, department_state, neris_id_dept"
        group_by = ["department_name", "department_state", "neris_id_dept"]
        df = self.aggregate(agg, group_by=group_by).sort_values("department_name")
        return df.to_dict("records")

    def get_location_use_path_counts(self):
        """Get path counts for location use types."""
        agg = "COALESCE(type_location_use, 'No Location Use Provided') as location_use_path, COUNT(*) as count"
        group_by = ["COALESCE(type_location_use, 'No Location Use Provided')"]

        return self.aggregate(agg, group_by=group_by)

    def get_day_hour_counts(self):
        """Get contingency counts for day of week × hour of day."""
        where = "call_create_day_of_week IS NOT NULL AND call_create_hour IS NOT NULL"
        agg = "call_create_day_of_week, call_create_hour, COUNT(*) as count"
        group_by = ["call_create_day_of_week", "call_create_hour"]

        return self.add_where(where).aggregate(agg, group_by=group_by)
