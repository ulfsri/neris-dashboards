"""Centralized repository for user-facing strings and tooltips."""

from .time_series import RollingWindow


# This may be a bit overengineered, but this or something like it will make it easier to
# manage messaging across apps, keep it all in sync.

__all__ = ["TOOLTIPS"]


class TOOLTIPS:
    class CHART_GUIDANCE:
        class CREATE_FILTERS:
            DRILL_DOWN = (
                "Clicking a value in this chart will focus the chart on that selection, "
                "and will filter the data in the rest of the dashboard to just that selection."
            )
            BOX_SELECT = "Drag a box on the chart to select a range to filter the data."

        class VISUAL_ONLY:
            DRILL_DOWN = (
                "Clicking a value in this chart will focus the chart on that selection, "
                "but will not filter the data in the rest of the dashboard."
            )

        class ADJUST_FILTERS:
            HIERARCHICAL = (
                "Adjust the filter using the hierarchical bar at the top of the chart, "
                "or click the 'Clear all filters' button to reset all filters."
            )
            BOX_SELECT = (
                "Adjust the filter by dragging a box around a different range, "
                "or click the 'Clear all filters' button to reset all filters."
            )
            BOX_SELECT_TRENDLINE_WITH_PICKERS = (
                "Adjust the filter by dragging a box around a different range, "
                "using the date pickers to modify the range, clicking the "
                "'Clear filter' button to clear this chart's filter, or clicking "
                "the 'Clear all filters' button to reset all filters."
            )
            CASUALTY_RESCUE_FF_NONFF_RADIO = "Click the radio buttons at the top of the chart to toggle between civilian and firefighter casualty and rescue types. Defaults to civilian."

    class DATA_DESCRIPTIONS:
        INCIDENT_TYPES = (
            "All incident types for the incident reports matching the current filter settings. "
            "Note that these are not 1:1 with the incident reports, as an incident may have up to three different types."
        )
        DEPARTMENT_AID = (
            "Mutual aid by direction and type for the incident reports matching the current filter settings. "
            "Note that these are not 1:1 with the incident reports, as an incident may have multiple aid instances."
        )
        CALL_CREATE_BY_DAY = "Count of incidents reports by date of call creation for the incident reports matching the current filter settings."

        @staticmethod
        def CALL_CREATE_BY_DAY_ROLLING_AVG(rolling_window: "RollingWindow"):
            label = (
                f"{rolling_window.window}-day"
                if rolling_window.include_current
                else f"previous {rolling_window.window}-day"
            )
            return (
                f"The dashed grey line represents the {label} rolling average of incident counts, "
                f"helping identify unusually high or low-volume days."
            )

        LOCATION_USE = (
            "All primary location use types for the incident reports matching the current filter settings. "
            "Note this is an optional field in NERIS: those for which it was not provided have a value of 'No Location Use Provided'."
        )
        CASUALTY_RESCUE_CONTINGENCY = "Distribution of casualty types and rescue types for the incident reports matching the current filter settings."

        @staticmethod
        def CALL_CREATE_DAY_HOUR(timezone: str = "UTC"):
            return f"The day of week and hour of day ({timezone}) of call creation time for the incident reports matching the current filter settings."

        @staticmethod
        def SAMPLED_MAP_POINTS(max_points: int):
            return [
                f"A subset of up to {max_points:,} incident point for the incident reports matching the current filter settings.",
                "These are taken from the incident point, geocoded incident location, dispatch point, and geocoded dispatch location (in that order of priority).",
            ]

    class METRICS:
        TOTAL_INCIDENTS = "Count of all distinct incident reports in NERIS matching the current filter settings."
        TOTAL_UNIT_RESPONSES = "Count of all incident unit responses for the incident reports matching the current filter settings."
        INCIDENT_DURATION_P90 = "90th percentile duration (time from call creation to incident clearance) for the incident reports matching the current filter settings."
        TOTAL_CASUALTY_RESCUE = "Total count of individuals involved in a casualty and/or rescue for the incident reports matching the current filter settings."
        TOTAL_DISPLACEMENTS = "Total count of people or businesses displaced for the incident reports matching the current filter settings."
        TOTAL_ANIMAL_RESCUES = "Total count of animals rescued for the incident reports matching the current filter settings."
        TOTAL_EXPOSURES = "Total count of exposures for the incident reports matching the current filter settings."
        TOTAL_CSST_HAZARDS = "Total count of incidents identified as involving Corrugated Stainless Steel Tubing for the incident reports matching the current filter settings."
        TOTAL_ELECTRIC_HAZARDS = "Total count of incidents identified as involving electrical hazards for the incident reports matching the current filter settings."
        TOTAL_POWERGEN_HAZARDS = "Total count of incidents identified as involving power generation equipment for the incident reports matching the current filter settings."
        TOTAL_MEDICAL_OXYGEN_HAZARDS = "Total count of incidents identified as involving medical oxygen for the incident reports matching the current filter settings."
