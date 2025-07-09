from pathlib import Path
import logging
from dataclasses import dataclass
from typing import Literal

from rich.logging import RichHandler
from lxml import etree

from r2r_ctd.breakout import Breakout
from r2r_ctd.state import (
    initialize_or_get_state,
    get_or_write_check,
    get_or_write_derived_file,
)
from r2r_ctd.checks import (
    check_three_files,
    check_dt,
    check_lat_lon,
    check_time_valid,
    check_lat_lon_valid,
)
from r2r_ctd.derived import make_conreport

from r2r_ctd import reporting

import click


@dataclass
class ResultAggregator:
    breakout: Breakout

    @property
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

    @property
    def lat_lon_nav_valid(self) -> int:
        results = []
        for station in self.breakout.stations_hex_paths:
            data = initialize_or_get_state(self.breakout, station)
            results.append(
                get_or_write_check(data, "lat_lon_valid", check_lat_lon_valid)
            )

        return int((results.count(True) / len(results)) * 100)

    @property
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

    @property
    def time_valid(self) -> int:
        results = []
        for station in self.breakout.stations_hex_paths:
            data = initialize_or_get_state(self.breakout, station)
            results.append(get_or_write_check(data, "date_valid", check_time_valid))

        return int((results.count(True) / len(results)) * 100)

    @property
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
    def certificate(self):
        return reporting.Certificate(
            reporting.overall_rating(self.rating),
            reporting.Tests(
                reporting.file_presence(
                    self.presence_of_all_files_rating, self.presence_of_all_files
                ),
                reporting.valid_checksum(self.valid_checksum_rating),
                reporting.lat_lon_range(
                    self.lat_lon_nav_ranges_rating, self.lat_lon_nav_range
                ),
                reporting.date_range(self.time_rating, self.time_range),
            ),
        )


@click.command()
@click.argument(
    "paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, writable=True, path_type=Path),
)
def main(paths: tuple[Path, ...]):
    FORMAT = "%(message)s"
    logging.basicConfig(
        level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
    )
    for path in paths:
        breakout = Breakout(path=path)

        qa_path = breakout.qa_template_xml

        ra = ResultAggregator(breakout)
        # print(etree.tostring(ra.certificate, pretty_print=True).decode())

        nsmap = qa_path.nsmap
        prefix = "/r2r:qareport"
        cert = qa_path.xpath(f"{prefix}/r2r:certificate", namespaces=nsmap)[0]
        qa_path.replace(cert, ra.certificate)
        print(etree.tostring(qa_path, pretty_print=True).decode())


if __name__ == "__main__":
    main()
