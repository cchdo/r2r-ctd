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
    get_xml_qa_path,
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


def lon_lat_range(
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
    def lon_lat_nav_valid(self) -> int:
        results = [data.r2r.lon_lat_valid for data in self.breakout]
        return int((results.count(True) / len(results)) * 100)

    @cached_property
    def lon_lat_nav_range(self) -> int:
        results = [data.r2r.lon_lat_in(self.breakout.bbox) for data in self.breakout]
        return int((results.count(True) / len(results)) * 100)

    @property
    def lon_lat_nav_ranges_rating(self) -> Literal["G", "Y", "R", "N", "X"]:
        if self.lon_lat_nav_valid == 0:  # no readable positions to test
            return "X"  # black

        if self.breakout.bbox is None:
            return "N"  # grey

        if self.lon_lat_nav_range == ALL:
            return "G"

        # in the WHOI code, it looks like up to 50% of the casts can have bad lat/lon
        # which I guess is a "few"
        if self.lon_lat_nav_range >= A_FEW:
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
            self.lon_lat_nav_ranges_rating,
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
        """Get the number of casts that have bottles fired

        .. admonition:: WHOI Divergence
            :class: warning

            The original WHOI code simply checks if there is a .bl file and says the cast has bottles fired
            if this file is present.

            This is incorrect, you need to check to see if there are any actual bottle fire records in that file.
            This code does that check.

            In the example breakout 138036 there are three casts but only one fired bottles, the QA report in that breakout
            incorrectly says 0 casts with bottles fired.
            My understanding is the current WHOI code would report 3 for this breakout, I don't know why is says 0
            but both are incorrect.
        """
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
        """Always reports OK

        .. admonition:: WHOI Divergence
            :class: warning

            In the original WHOI code, this works the same way as :py:meth:`.info_casts_with_xmlcon_bad_format`.

            I would like to implement this in the same way that the bad xmlcon report does, but need to actually make or find some bad data.
        """
        return Info("", name="Casts with Hex file in Bad Format", uom="List")

    @cached_property
    def info_casts_with_xmlcon_bad_format(self):
        """Report the casts which could not have a conreport generated

        .. admonition:: WHOI Divergence
            :class: warning

            The original code would run the ``file`` command and check to make sure any of
            "data", "object", or "executable" were not in the output of the command.
            Instead, this will just check to see which casts the ConReport.exe failed on,
            i.e. let seabird software figure out if the xmlcon is a bad format.

            The original documentation also says it is looking for ASCII, but the code does not appear
            to do any encoding checks, they would likely be invalid anyway since Seabird files, being on windows,
            are usually `CP437 <https://en.wikipedia.org/wiki/Code_page_437>`_.
        """
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
        """List of casts where the serial number in the data header does not
        match any serial numbers in the xmlcon.

        .. admonition:: WHOI Divergence
            :class: warning

            There can be more than one temperature sensor and they will have different serial numbers.
            The datafile would only have one serial number, but the xmlcon will list all the sensors.
            The original WHOI code would only check one of the serial numbers found in the xmlcon.

            I'm not sure the exact cause, but there are a lot of false problems in the breakouts I was given
            to test with, for example: 156405 reports that all the casts have SN problems, but a manual examination
            and this code, show that there are no mismatches.

            This code checks the serial number in the header file against all the serial numbers in the xmlcon of the
            same instrument type (e.g. all temperature sensor serial numbers)
        """
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
        """List of casts where the serial number in the data header does not
        match any serial numbers in the xmlcon.

        .. admonition:: WHOI Divergence
            :class: warning

            See the info_casts_with_temp_sensor_sn_problems divergence note
        """
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
            if not data.r2r.lon_lat_valid
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
            if data.r2r.lon_lat_valid and not data.r2r.lon_lat_in(self.breakout.bbox)
        ]
        return Info(
            " ".join(problem_casts),
            name="Casts that Failed NAV Boundary Tests",
            uom="List",
        )

    def gen_geoCSV(self):
        """Generates the "geoCSV" file

        The header was taken verbatim from the WHOI Code, and could probably use some cleanup.
        Of particular note is that the field types, units, etc.. metadata in the header, does not
        match the number of columns in the actual "data" part.

        The original WHOI code also doesn't calculate the dp_flag and just sets to a hard coded 0.
        Better might be to use a bit mask because there can be multiple problems with each cast.
        """
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
                lon_lat_range(self.lon_lat_nav_ranges_rating, self.lon_lat_nav_range),
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


def write_xml_qa_report(breakout: "Breakout", certificate: _Element):
    qa_xml = breakout.qa_template_xml
    root = qa_xml.getroot()
    cert = root.xpath("/r2r:qareport/r2r:certificate", namespaces=breakout.namespaces)[
        0
    ]
    updates = root.xpath(
        "/r2r:qareport/r2r:provenance/r2r:updates",
        namespaces=breakout.namespaces,
    )[0]
    updates.append(get_update_record())
    references = root.xpath(
        "/r2r:qareport/r2r:references", namespaces=breakout.namespaces
    )[0]

    new_refs = get_new_references(breakout)
    references.extend(new_refs)
    root.replace(cert, certificate)

    with get_xml_qa_path(breakout).open("wb") as f:
        qa_xml.write(
            f,
            pretty_print=True,
            xml_declaration=True,
            method="xml",
            encoding="UTF-8",
        )
