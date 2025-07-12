from functools import cached_property
from typing import Literal
from dataclasses import dataclass

from lxml.builder import ElementMaker
from lxml.etree import Element

from r2r_ctd.breakout import Breakout
from r2r_ctd.checks import (
    check_dt,
    check_lat_lon,
    check_lat_lon_valid,
    check_three_files,
    check_time_valid,
)
from r2r_ctd.derived import make_conreport
from r2r_ctd.state import (
    get_or_write_check,
    get_or_write_derived_file,
    initialize_or_get_state,
)

E = ElementMaker(
    namespace="https://service.rvdata.us/schema/r2r-2.0",
    nsmap={"r2r": "https://service.rvdata.us/schema/r2r-2.0"},
)

Certificate = E.certificate
Rating = E.rating
Tests = E.tests
Test = E.test
TestResult = E.test_result
Bounds = E.bounds
Bound = E.bound

Infos = E.infos
Info = E.info


def overall_rating(rating: Literal["G", "R", "Y", "N", "X"]) -> Element:
    return Rating(
        rating,
        description=(
            "GREEN (G) if all tests GREEN, "
            "RED (R) if at least one test RED, "
            "else YELLOW (Y); "
            "Gray(N) if no navigation was included in the distribution; "
            "X if one or more tests could not be run."
        ),
    )


def file_presence(rating: Literal["G", "R"], test_result: str | int) -> Element:
    """Construct the Element for the all raw files test"""
    return Test(
        Rating(rating),
        TestResult(str(test_result), uom="Percent"),
        Bounds(Bound("100", name="MinimumPercentToPass", uom="Percent")),
        description="GREEN if 100% of the casts have .hex/.dat, .con and .hdr files; else RED",
        name="Presence of All Raw Files",
    )


def valid_checksum(rating: Literal["G", "R"]) -> Element:
    """Construct the Element for the valid checksum test"""

    return Test(
        Rating(rating),
        Bounds(
            Bound("True/False", name="AllFilesHaveValidChecksum", uom="Unitless"),
        ),
        description="GREEN if 100% of the files in the manifest have valid checksums; else RED",
        name="Valid Checksum for All Files in Manifest",
    )


def lat_lon_range(
    rating: Literal["G", "R", "Y", "N", "X"], test_result: str | int
) -> Element:
    return Test(
        Rating(rating),
        TestResult(str(test_result), uom="Percent"),
        Bounds(Bound("100", name="MinimumPercentToPass", uom="Percent")),
        name="Lat/Lon within NAV Ranges",
        description="GREEN if 100% of the profiles have lat/lon within cruise bounds; YELLOW if a few profiles without lat/lon; GRAY if no navigation was included in the distribution; else RED; BLACK if no readable lat/lon for all casts",
    )


def date_range(
    rating: Literal["G", "R", "Y", "N", "X"], test_result: str | int
) -> Element:
    return Test(
        Rating(rating),
        TestResult(str(test_result), uom="Percent"),
        Bounds(Bound("100", name="PercentFilesWithValidTemporalRange", uom="Percent")),
        name="Dates within NAV Ranges",
        description="GREEN if 100% of the profiles have Date within cruise bounds; YELLOW if a few profile times out of cruise bounds; GRAY if no navigation was provided in the distribution; else RED; BLACK if no readable dates to test",
    )


@dataclass
class ResultAggregator:
    breakout: Breakout

    @cached_property
    def presence_of_all_files(self) -> int:
        results = []
        for station in self.breakout.stations_hex_paths:
            data = initialize_or_get_state(self.breakout, station)
            results.append(get_or_write_check(data, "three_files", check_three_files))

        return int((results.count(True) / len(results)) * 100)

    @property
    def presence_of_all_files_rating(self) -> Literal["G", "R"]:
        if self.presence_of_all_files == 100:
            return "G"
        return "R"

    @property
    def valid_checksum_rating(self) -> Literal["G", "R"]:
        if self.breakout.manifest_ok:
            return "G"
        return "R"

    @cached_property
    def lat_lon_nav_valid(self) -> int:
        results = []
        for station in self.breakout.stations_hex_paths:
            data = initialize_or_get_state(self.breakout, station)
            results.append(
                get_or_write_check(data, "lat_lon_valid", check_lat_lon_valid)
            )

        return int((results.count(True) / len(results)) * 100)

    @cached_property
    def lat_lon_nav_range(self) -> int:
        results = []
        for station in self.breakout.stations_hex_paths:
            data = initialize_or_get_state(self.breakout, station)
            results.append(
                get_or_write_check(
                    data, "lat_lon_range", check_lat_lon, bbox=self.breakout.bbox
                )
            )

        return int((results.count(True) / len(results)) * 100)

    @property
    def lat_lon_nav_ranges_rating(self) -> Literal["G", "Y", "R", "N", "X"]:
        if self.lat_lon_nav_valid == 0:  # no readable positions to test
            return "X"  # black

        # TODO: handle case of breakout itself not having bounds
        # if self.breakout.bbox:
        #   return "N" # grey

        if self.lat_lon_nav_range == 100:
            return "G"

        # in the WHOI code, it looks like up to 50% of the casts can have bad lat/lon
        # which I guess is a "few"
        if self.lat_lon_nav_range >= 50:
            return "Y"

        return "R"

    @cached_property
    def time_valid(self) -> int:
        results = []
        for station in self.breakout.stations_hex_paths:
            data = initialize_or_get_state(self.breakout, station)
            results.append(get_or_write_check(data, "date_valid", check_time_valid))

        return int((results.count(True) / len(results)) * 100)

    @cached_property
    def time_range(self) -> int:
        results = []
        for station in self.breakout.stations_hex_paths:
            data = initialize_or_get_state(self.breakout, station)
            results.append(
                get_or_write_check(
                    data,
                    "date_range",
                    check_dt,
                    dtrange=self.breakout.temporal_bounds(),
                )
            )

        return int((results.count(True) / len(results)) * 100)

    @property
    def time_rating(self) -> Literal["G", "Y", "R", "N", "X"]:
        if self.time_valid == 0:  # no readable dates to test
            return "X"  # black

        # TODO: handle case of breakout itself not having bounds
        # if self.breakout.temporal_bounds():
        #   return "N" # grey

        if self.time_range == 100:
            return "G"

        # in the WHOI code, it looks like up to 50% of the casts can have bad time
        # which I guess is a "few"
        if self.time_range >= 50:
            return "Y"

        return "R"

    @property
    def rating(self):
        ratings = {
            self.presence_of_all_files_rating,
            self.valid_checksum_rating,
            self.lat_lon_nav_ranges_rating,
            self.time_rating,
        }
        if "R" in ratings:
            return "R"
        if "N" in ratings:
            return "N"
        if "X" in ratings:
            return "X"
        if "Y" in ratings:
            return "Y"
        return "G"

    @property
    def info_total_raw_files(self):
        return Info(
            str(len(self.breakout.hex_paths)),
            name="Total Raw Files",
            uom="# of .hex/.dat Files",
        )

    @cached_property
    def info_number_bottles(self):
        result = []
        for station in self.breakout.stations_hex_paths:
            data = initialize_or_get_state(self.breakout, station)
            result.append("bl" in data)

        return Info(
            str(result.count(True)), name="# of Casts with Bottles Fired", uom="Count"
        )

    @cached_property
    def info_model_number(self):
        # The WHOI code did this in a loop that didn't handle the case
        # of multiple instrument types in the same breakout
        # it also appears to just use the last station iterated over (unsure if ordered)
        # we are going to emulate that here
        for station in self.breakout.stations_hex_paths:
            data = initialize_or_get_state(self.breakout, station)
            conreport = get_or_write_derived_file(data, "conreport", make_conreport)

        return Info("SBE9")

    @property
    def certificate(self):
        return Certificate(
            overall_rating(self.rating),
            Tests(
                file_presence(
                    self.presence_of_all_files_rating, self.presence_of_all_files
                ),
                valid_checksum(self.valid_checksum_rating),
                lat_lon_range(self.lat_lon_nav_ranges_rating, self.lat_lon_nav_range),
                date_range(self.time_rating, self.time_range),
            ),
            Infos(
                self.info_total_raw_files,
                self.info_number_bottles,
                self.info_model_number,
            ),
        )
