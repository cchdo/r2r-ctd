from typing import Literal

from lxml.builder import ElementMaker
from lxml.etree import ElementTree

E = ElementMaker(
    namespace="https://service.rvdata.us/schema/r2r-2.0",
    nsmap={"r2r": "https://service.rvdata.us/schema/r2r-2.0"},
)

Rating = E.rating
Tests = E.tests
Test = E.test
TestResult = E.test_result
Bounds = E.bounds
Bound = E.bound

Infos = E.infos
Info = E.info


rating = {
    "description": (
        "GREEN (G) if all tests GREEN, "
        "RED (R) if at least one test RED, "
        "else YELLOW (Y); "
        "Gray(N) if no navigation was included in the distribution; "
        "X if one or more tests could not be run."
    )
}


def file_presence(rating: Literal["G", "R"], test_result: str | int) -> ElementTree:
    """Construct the ElementTree for the all raw files test"""
    return Test(
        Rating(rating),
        TestResult(str(test_result), uom="Percent"),
        Bounds(Bound("100", name="MinimumPercentToPass", uom="Percent")),
        description="GREEN if 100% of the casts have .hex/.dat, .con and .hdr files; else RED",
        name="Presence of All Raw Files",
    )


def valid_checksum(rating: Literal["G", "R"]) -> ElementTree:
    """Construct the ElementTree for the valid checksum test"""

    return Test(
        Rating(rating),
        Bounds(
            Bound("True/False", name="AllFilesHaveValidChecksum", uom="Unitless"),
        ),
        description="GREEN if 100% of the files in the manifest have valid checksums; else RED",
        name="Valid Checksum for All Files in Manifest",
    )
