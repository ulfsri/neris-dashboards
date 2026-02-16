"""
Configuration settings for the cornsacks dashboard.
"""

from typing import Final

CACHE_TIMEOUT_SECONDS: Final[int] = 900  # 15 minutes

BASEMAP_URL: Final[str] = (
    "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
)

MAX_MAP_POINTS: Final[int] = 10000

DEPT_FEATURE_SERVER_URL: Final[str] = (
    "https://services5.arcgis.com/lPbcyJOcoLyZmvo6/ArcGIS/rest/services/"
    "NERIS%20Public%20Fire%20Departments/FeatureServer"
)
