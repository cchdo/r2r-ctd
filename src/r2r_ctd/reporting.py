import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cached_property
from importlib.metadata import metadata, version
from typing import Literal

from lxml.builder import ElementMaker
from lxml.etree import _Element

import r2r_ctd.accessors  # noqa: F401
from r2r_ctd.breakout import Breakout
from r2r_ctd.derived import (
    get_con_report_sn,
    get_hdr_sn,
    get_latitude,
    get_longitude,
    get_model,
    get_time,
)
from r2r_ctd.state import (
    R2R_QC_VARNAME,
    get_config_path,
    get_geoCSV_path,
)

E = ElementMaker(
    namespace="https://service.rvdata.us/schema/r2r-2.0",
    nsmap={"r2r": "https://service.rvdata.us/schema/r2r-2.0"},
)

# XML QA Certificate Elements
Certificate = E.certificate
Rating = E.rating
Tests = E.tests
Test = E.test
TestResult = E.test_result
Bounds = E.bounds
Bound = E.bound
Infos = E.infos
Info = E.info

# XML QA Update Elements
Update = E.update
Process = E.process
Time = E.time

# XML QA Reference elements (links to files)
Reference = E.reference

ALL = 100  # percent
A_FEW = 50  # percent


def overall_rating(rating: Literal["G", "R", "Y", "N", "X"]) -> _Element:
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


def file_presence(rating: Literal["G", "R"], test_result: str | int) -> _Element:
    """Construct the Element for the all raw files test"""
    return Test(
        Rating(rating),
        TestResult(str(test_result), uom="Percent"),
        Bounds(Bound("100", name="MinimumPercentToPass", uom="Percent")),
        description="GREEN if 100% of the casts have .hex/.dat, .con and .hdr files; else RED",
        name="Presence of All Raw Files",
    )


def valid_checksum(rating: Literal["G", "R"]) -> _Element:
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
    rating: Literal["G", "R", "Y", "N", "X"],
    test_result: str | int,
) -> _Element:
    return Test(
        Rating(rating),
        TestResult(str(test_result), uom="Percent"),
        Bounds(Bound("100", name="MinimumPercentToPass", uom="Percent")),
        name="Lat/Lon within NAV Ranges",
        description="GREEN if 100% of the profiles have lat/lon within cruise bounds; YELLOW if a few profiles without lat/lon; GRAY if no navigation was included in the distribution; else RED; BLACK if no readable lat/lon for all casts",
    )


def date_range(
    rating: Literal["G", "R", "Y", "N", "X"],
    test_result: str | int,
) -> _Element:
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
        results = [data.r2r.all_three_files for data in self.breakout]
        return int((results.count(True) / len(results)) * 100)

    @property
    def presence_of_all_files_rating(self) -> Literal["G", "R"]:
        if self.presence_of_all_files == ALL:
            return "G"
        return "R"

    @property
    def valid_checksum_rating(self) -> Literal["G", "R"]:
        if self.breakout.manifest_ok:
            return "G"
        return "R"

    @cached_property
    def lat_lon_nav_valid(self) -> int:
        results = [data.r2r.lat_lon_valid for data in self.breakout]
        return int((results.count(True) / len(results)) * 100)

    @cached_property
    def lat_lon_nav_range(self) -> int:
        results = [data.r2r.lon_lat_in(self.breakout.bbox) for data in self.breakout]
        return int((results.count(True) / len(results)) * 100)

    @property
    def lat_lon_nav_ranges_rating(self) -> Literal["G", "Y", "R", "N", "X"]:
        if self.lat_lon_nav_valid == 0:  # no readable positions to test
            return "X"  # black

        if self.breakout.bbox is None:
            return "N"  # grey

        if self.lat_lon_nav_range == ALL:
            return "G"

        # in the WHOI code, it looks like up to 50% of the casts can have bad lat/lon
        # which I guess is a "few"
        if self.lat_lon_nav_range >= A_FEW:
            return "Y"

        return "R"

    @cached_property
    def time_valid(self) -> int:
        results = [data.r2r.time_valid for data in self.breakout]
        return int((results.count(True) / len(results)) * 100)

    @cached_property
    def time_range(self) -> int:
        results = [
            data.r2r.time_in(self.breakout.temporal_bounds) for data in self.breakout
        ]
        return int((results.count(True) / len(results)) * 100)

    @property
    def time_rating(self) -> Literal["G", "Y", "R", "N", "X"]:
        if self.time_valid == 0:  # no readable dates to test
            return "X"  # black

        if self.breakout.temporal_bounds is None:
            return "N"  # grey

        if self.time_range == ALL:
            return "G"

        # in the WHOI code, it looks like up to 50% of the casts can have bad time
        # which I guess is a "few"
        if self.time_range >= A_FEW:
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
        result = [data.r2r.bottles_fired for data in self.breakout]

        return Info(
            str(result.count(True)),
            name="# of Casts with Bottles Fired",
            uom="Count",
        )

    @cached_property
    def info_model_number(self):
        model = ""
        for data in self.breakout:
            con_report = data.r2r.con_report

            if con_report is None:
                continue
            model = get_model(con_report) or ""

        return Info(model, name="Model Number of CTD Instrument", uom="Unitless")

    @cached_property
    def info_number_casts_with_nav_all_scans(self):
        number = 0
        for data in self.breakout:
            if (
                "hdr" in data
                and "Store Lat/Lon Data = Append to Every Scan" in data.hdr.item()
            ):
                number += 1

        return Info(str(number), name="# of Casts with NAV for All Scans", uom="Count")

    @cached_property
    def info_casts_without_all_raw(self):
        problem_casts = []
        for station in self.breakout.stations_hex_paths:
            data = self.breakout[station]
            if not data.r2r.all_three_files:
                problem_casts.append(station.name)

        return Info(
            " ".join(problem_casts),
            name="Casts without all Raw Files",
            uom="List",
        )

    @cached_property
    def info_casts_with_hex_bad_format(self):
        # The WHOI code runs `file -b` and checks to see if the result has one of:
        # "data", "objects", or "executable" in the type
        # I think we need an example of some bad files for this
        # For now, always returning OK
        return Info("", name="Casts with Hex file in Bad Format", uom="List")

    @cached_property
    def info_casts_with_xmlcon_bad_format(self):
        problem_casts = []
        for station in self.breakout.stations_hex_paths:
            data = self.breakout[station]
            if data.r2r.con_report is None:
                problem_casts.append(station.stem)

        return Info(
            " ".join(problem_casts),
            name="Casts with XMLCON/con file in Bad Format",
            uom="List",
        )

    @cached_property
    def info_casts_with_dock_deck_test_in_file_name(self):
        return Info(
            " ".join(path.name for path in self.breakout.deck_test_paths),
            name="Casts with dock/deck and test in file name",
            uom="List",
        )

    @cached_property
    def info_casts_with_temp_sensor_sn_problems(self):
        problem_casts = []
        for station in self.breakout.stations_hex_paths:
            data = self.breakout[station]
            con_report = data.r2r.con_report
            if con_report is None:
                continue
            models = get_con_report_sn(con_report, "Temperature")
            sn = get_hdr_sn(data.hdr.item(), "Temperature")
            if sn not in models:
                problem_casts.append(station.stem)
        return Info(
            " ".join(problem_casts),
            name="Casts with temp. sensor serial number problem",
            uom="List",
        )

    @cached_property
    def info_casts_with_cond_sensor_sn_problems(self):
        problem_casts = []
        for station in self.breakout.stations_hex_paths:
            data = self.breakout[station]
            con_report = data.r2r.con_report
            if con_report is None:
                continue
            models = get_con_report_sn(con_report, "Conductivity")
            sn = get_hdr_sn(data.hdr.item(), "Conductivity")
            if sn not in models:
                problem_casts.append(station.stem)
        return Info(
            " ".join(problem_casts),
            name="Casts with cond. sensor serial number problem",
            uom="List",
        )

    @cached_property
    def info_casts_with_bad_nav(self):
        problem_casts = [
            data[R2R_QC_VARNAME].attrs["station_name"]
            for data in self.breakout
            if data.r2r.lat_lon_valid
        ]

        return Info(
            " ".join(problem_casts),
            name="Casts with Blank, missing, or unrecognizable NAV",
            uom="List",
        )

    @cached_property
    def info_casts_failed_nav_bounds(self):
        problem_casts = [
            data[R2R_QC_VARNAME].attrs["station_name"]
            for data in self.breakout
            if not data.r2r.lon_lat_in(self.breakout.bbox)
        ]
        return Info(
            " ".join(problem_casts),
            name="Casts that Failed NAV Boundary Tests",
            uom="List",
        )

    def gen_geoCSV(self):
        header = textwrap.dedent(f"""\
        #dataset: GeoCSV 2.0
        #field_unit: (unitless),(unitless),ISO_8601,second,degrees_east,degrees_north
        #field_type: string,string,datetime,float,float
        #field_standard_name: Cast number,Model number of CTD(ex. SBE911) for these data,date and time,Unix Epoch time,longitude of vessel,latitude of vessel
        #field_missing: ,,,,,
        #delimiter: ,
        #standard_name_cv: http://www.rvdata.us/voc/fieldname
        #source: http://www.rvdata.org
        #title: R2R Data Product - Generated from {self.breakout.cruise_id} - CTD (Seabird)
        #cruise_id: {self.breakout.cruise_id}
        #device_information: CTD (SeaBird)
        #creation_date: {datetime.now().replace(microsecond=0).isoformat()}
        #input_data_doi: 10.7284/{self.breakout.fileset_id}
        #This table lists file metadata for all CTD casts for identified cruise(s)
        #dp_flag 0=unflagged,  3=invalid time, 4=invalid position, 6=out of valid cruise time range,
        #	11=out of cruise navigation range, other values are unspecified flags
        castID,ctd_type,iso_time,epoch_time,ship_longitude,ship_latitude,dp_flag""")
        data_lines = []
        for station in self.breakout.stations_hex_paths:
            data = self.breakout[station]

            lon = get_longitude(data) or ""
            lat = get_latitude(data) or ""
            time = get_time(data)

            iso_time = ""
            epoch = ""
            if time:
                iso_time = time.isoformat()
                epoch = f"{time.timestamp():.0f}"

            model = ""
            if con_report := data.r2r.con_report:
                model = get_model(con_report) or ""

            data_lines.append(
                ",".join(
                    [station.stem, model, iso_time, epoch, str(lon), str(lat), "0"],
                ),
            )
        return "\n".join([header, *data_lines])

    @property
    def certificate(self):
        return Certificate(
            overall_rating(self.rating),
            Tests(
                file_presence(
                    self.presence_of_all_files_rating,
                    self.presence_of_all_files,
                ),
                valid_checksum(self.valid_checksum_rating),
                lat_lon_range(self.lat_lon_nav_ranges_rating, self.lat_lon_nav_range),
                date_range(self.time_rating, self.time_range),
            ),
            Infos(
                self.info_total_raw_files,
                self.info_number_bottles,
                self.info_model_number,
                self.info_number_casts_with_nav_all_scans,
                self.info_casts_without_all_raw,
                self.info_casts_with_hex_bad_format,
                self.info_casts_with_xmlcon_bad_format,
                self.info_casts_with_dock_deck_test_in_file_name,
                self.info_casts_with_temp_sensor_sn_problems,
                self.info_casts_with_cond_sensor_sn_problems,
                self.info_casts_with_bad_nav,
                self.info_casts_failed_nav_bounds,
            ),
        )


def get_update_record() -> _Element:
    return Update(
        Process(metadata("r2r_ctd")["Name"], version=version("r2r_ctd")),
        Time(datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
        description="Quality Assessment (QA)",
    )


def get_new_references(breakout: "Breakout") -> list[_Element]:
    """Return a list of new Reference xml elements

    This crawls the output directories to check was was actually created to build its list
    """
    # this list is ordered, geoCSV first
    references: list[_Element] = []
    base_src = f"https://service.rvdata.us/data/cruise/{breakout.cruise_id}/fileset/{breakout.fileset_id}"
    geocsv_path = get_geoCSV_path(breakout)
    if geocsv_path.exists():
        references.append(
            Reference(
                f"Metadata for all processed CTD files on cruise {breakout.cruise_id} (geoCSV)",
                src=f"{base_src}/qa/{geocsv_path.name}",
            )
        )

    config_path = get_config_path(breakout)
    references.extend(
        Reference(
            f"CTD Configuration Report: {path.stem}",
            src=f"{base_src}/qa/config/{path.name}",
        )
        for path in sorted(config_path.glob("*.txt"))
    )

    return references
