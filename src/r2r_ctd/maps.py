"""Functions for making maps to help QA work"""

from logging import getLogger

import folium

from r2r_ctd.reporting import ResultAggregator
from r2r_ctd.state import get_map_path

logger = getLogger(__name__)


def make_map(results: ResultAggregator):
    """Write the results to a map using folium.

    Useful for seeing what stations failed and what the tested bounding box was"""
    m = folium.Map()

    breakout_fields = [
        "cruise_id",
        "fileset_id",
        "rating",
        "manifest_ok",
        "start_date",
        "end_date",
        "stations_not_on_map",
    ]
    breakout_popup = folium.GeoJsonPopup(
        fields=breakout_fields,
    )
    breakout_tooltip = folium.GeoJsonTooltip(
        fields=breakout_fields,
    )

    breakout_feature = results.geo_breakout_feature()

    station_features = results.geo_station_feature()

    if breakout_feature:
        folium.GeoJson(
            breakout_feature,
            popup=breakout_popup,
            tooltip=breakout_tooltip,
            style_function=lambda feature: {
                "fillColor": feature["properties"]["rating"],
                "weight": 0,
            },
        ).add_to(m)

    station_fields = [
        "name",
        "time",
        "all_three_files",
        "lon_lat_valid",
        "time_valid",
        "time_in",
        "lon_lat_in",
        "bottles_fired",
    ]

    if len(station_features["features"]) > 0:
        folium.GeoJson(
            station_features,
            marker=folium.Marker(icon=folium.Icon()),
            tooltip=folium.GeoJsonTooltip(fields=station_fields),
            popup=folium.GeoJsonPopup(fields=station_fields),
            style_function=lambda feature: {
                "markerColor": feature["properties"]["marker_color"]
            },
        ).add_to(m)
    folium.FitOverlays().add_to(m)

    map_path = get_map_path(results.breakout)
    m.save(map_path)
    logger.info(f"Wrote QA map to: {map_path}")
