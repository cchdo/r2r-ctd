from logging import getLogger

import folium

from r2r_ctd.breakout import Breakout
from r2r_ctd.reporting import ResultAggregator
from r2r_ctd.state import get_map_path

logger = getLogger(__name__)


def make_maps(breakout: Breakout, results: ResultAggregator):
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
    breakout_feature = breakout.__geo_interface__

    station_features = []
    stations_not_on_map = []
    for station in breakout:
        lon = station.r2r.longitude
        lat = station.r2r.latitude
        if None in (lon, lat):
            stations_not_on_map.append(station)
            continue
        station_feature = station.r2r.__geo_interface__
        station_feature["properties"]["marker_color"] = station.r2r.get_marker_color(
            breakout.bbox, breakout.temporal_bounds
        )
        time_in = station.r2r.time_in(breakout.temporal_bounds)
        station_feature["properties"]["time_in"] = (
            f"<span style='color: {'green' if time_in else 'red'}'>{time_in}</span>"
        )
        lon_lat_in = station.r2r.lon_lat_in(breakout.bbox)
        station_feature["properties"]["lon_lat_in"] = (
            f"<span style='color: {'green' if lon_lat_in else 'red'}'>{lon_lat_in}</span>"
        )
        station_features.append(station_feature)

    if breakout_feature:
        breakout_feature["properties"]["rating"] = results.rating
        breakout_feature["properties"]["stations_not_on_map"] = (
            "All QAed stations on map"
        )

        rating_color = {
            "G": "green",
            "Y": "yellow",
            "R": "red",
            "X": "black",
            "N": "grey",
        }
        if len(stations_not_on_map) > 0:
            station_items = "".join(
                f"<li>{s.r2r.name}</li>" for s in stations_not_on_map
            )
            breakout_feature["properties"]["stations_not_on_map"] = (
                f"<ul>{station_items}</ul>"
            )

        folium.GeoJson(
            {"type": "FeatureCollection", "features": [breakout_feature]},
            popup=breakout_popup,
            tooltip=breakout_tooltip,
            style_function=lambda feature: {
                "fillColor": rating_color[results.rating],
                "weight": 0,
            },
        ).add_to(m)

    stations = folium.FeatureGroup().add_to(m)

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

    if len(station_features) > 0:
        folium.GeoJson(
            {"type": "FeatureCollection", "features": station_features},
            marker=folium.Marker(icon=folium.Icon()),
            tooltip=folium.GeoJsonTooltip(fields=station_fields),
            popup=folium.GeoJsonPopup(fields=station_fields),
            style_function=lambda feature: {
                "markerColor": feature["properties"]["marker_color"]
            },
        ).add_to(stations)
    folium.FitOverlays().add_to(m)
    map_path = get_map_path(breakout)
    m.save(map_path)
    logger.info(f"Wrote QA map to: {map_path}")
