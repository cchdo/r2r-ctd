from functools import cached_property
import textwrap
from typing import Literal
from dataclasses import dataclass
from datetime import datetime

from lxml.builder import ElementMaker
from lxml.etree import _Element

from r2r_ctd.breakout import Breakout
from r2r_ctd.checks import (
    check_dt,
    check_lat_lon,
    check_lat_lon_valid,
    check_three_files,
    check_time_valid,
)
from r2r_ctd.derived import (
    get_conreport_sn,
    get_hdr_sn,
    get_latitude,
    get_longitude,
    get_model,
    get_time,
    make_conreport,
    make_cnvs,
)
from r2r_ctd.state import (
    get_or_write_check,
    get_or_write_derived_file,
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
    rating: Literal["G", "R", "Y", "N", "X"], test_result: str | int
) -> _Element:
    return Test(
        Rating(rating),
        TestResult(str(test_result), uom="Percent"),
        Bounds(Bound("100", name="MinimumPercentToPass", uom="Percent")),
        name="Lat/Lon within NAV Ranges",
        description="GREEN if 100% of the profiles have lat/lon within cruise bounds; YELLOW if a few profiles without lat/lon; GRAY if no navigation was included in the distribution; else RED; BLACK if no readable lat/lon for all casts",
    )


def date_range(
    rating: Literal["G", "R", "Y", "N", "X"], test_result: str | int
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
        results = []
        for station in self.breakout.stations_hex_paths:
            data = self.breakout[station]
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
        for data in self.breakout:
            results.append(
                get_or_write_check(data, "lat_lon_valid", check_lat_lon_valid)
            )

        return int((results.count(True) / len(results)) * 100)

    @cached_property
    def lat_lon_nav_range(self) -> int:
        results = []
        for data in self.breakout:
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
        for data in self.breakout:
            results.append(get_or_write_check(data, "date_valid", check_time_valid))

        return int((results.count(True) / len(results)) * 100)

    @cached_property
    def time_range(self) -> int:
        results = []
        for data in self.breakout:
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
        for data in self.breakout:
            result.append("bl" in data)

        return Info(
            str(result.count(True)), name="# of Casts with Bottles Fired", uom="Count"
        )

    @cached_property
    def info_model_number(self):
        model = ""
        for data in self.breakout:
            conreport = get_or_write_derived_file(data, "conreport", make_conreport)

            if conreport is None:
                continue
            model = get_model(conreport.item()) or ""

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
            all_raw = (get_or_write_check(data, "three_files", check_three_files))
            if not all_raw:
                problem_casts.append(station.name)

        return Info(" ".join(problem_casts), name="Casts without all Raw Files", uom="List")
    

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
            conreport = get_or_write_derived_file(data, "conreport", make_conreport)
            if conreport is None:
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
            conreport = get_or_write_derived_file(data, "conreport", make_conreport)
            if conreport is None:
                continue
            models = get_conreport_sn(conreport.item(), "Temperature")
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
            conreport = get_or_write_derived_file(data, "conreport", make_conreport)
            if conreport is None:
                continue
            models = get_conreport_sn(conreport.item(), "Conductivity")
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
        problem_casts = []
        for station in self.breakout.stations_hex_paths:
            data = self.breakout[station]
            if not get_or_write_check(data, "lat_lon_valid", check_lat_lon_valid):
                problem_casts.append(station.stem)
        return Info(
            " ".join(problem_casts),
            name="Casts with Blank, missing, or unrecognizable NAV",
            uom="List",
        )

    @cached_property
    def info_casts_failed_nav_bounds(self):
        problem_casts = []
        for station in self.breakout.stations_hex_paths:
            data = self.breakout[station]
            if not get_or_write_check(
                data, "lat_lon_range", check_lat_lon, bbox=self.breakout.bbox
            ):
                problem_casts.append(station.stem)
        return Info(
            " ".join(problem_casts),
            name="Casts that Failed NAV Boundary Tests",
            uom="List",
        )

    def gen_cnvs(self):
        for station in self.breakout.stations_hex_paths:
            data = self.breakout[station]

            # if the conreport failed, don't bother with this cast
            conreport = get_or_write_derived_file(data, "conreport", make_conreport)
            if conreport is None:
                continue

            get_or_write_derived_file(data, "cnv_24hz", make_cnvs)
            get_or_write_derived_file(data, "cnv_1db", make_cnvs)

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
            conreport = get_or_write_derived_file(data, "conreport", make_conreport)

            lon = get_longitude(data) or ""
            lat = get_latitude(data) or ""
            time = get_time(data)

            iso_time = ""
            epoch = ""
            if time:
                iso_time = time.isoformat()
                epoch = f"{time.timestamp():.0f}"

            model = ""
            if conreport:
                model = get_model(conreport.item()) or ""

            data_lines.append(
                ",".join(
                    [station.stem, model, iso_time, epoch, str(lon), str(lat), "0"]
                )
            )
        return "\n".join([header, *data_lines])

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
