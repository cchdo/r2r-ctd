from typing import Literal

from lxml.builder import ElementMaker
from lxml.etree import Element

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
        Bounds(Bound("100", name="MinimumPercentToPass", uom="Percent")),
        name="Dates within NAV Ranges",
        description="GREEN if 100% of the profiles have Date within cruise bounds; YELLOW if a few profile times out of cruise bounds; GRAY if no navigation was provided in the distribution; else RED; BLACK if no readable dates to test",
    )
