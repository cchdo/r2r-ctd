from pathlib import Path
from logging import getLogger
from typing import TYPE_CHECKING

import xarray as xr

from r2r_ctd.derived import get_latitude, get_longitude, get_time

if TYPE_CHECKING:
    from r2r_ctd.breakout import BBox, DTRange

logger = getLogger(__name__)


def is_deck_test(path: Path) -> bool:
    """Check if the given path "looks like" a deck test

    This method matches the pathname against a list of strings that are common to desk tests
    """
    logger.debug(f"Checking if {path} is a decktest")
    # this should match the behavior of WHOI tests, but felt fragile to me
    substrs = (
        "deck",
        "dock",
        "test",
        "999",
        "998",
        "997",
        "996",
        "995",
        "994",
        "993",
        "992",
        "991",
        "990",
    )
    for substr in substrs:
        if substr in path.name.lower():
            return True
    return False


def check_three_files(ds: xr.Dataset) -> bool:
    """Check that each hex file has both an xmlcon and hdr files associated with it.

    The input dataset is expected conform output of odf.sbe.read_hex. This dataset
    is then checked to see if it has all the correct keys. The details of finding/reading
    those files is left to odf.sbe.
    """
    logger.debug("Checking if all three files")
    three_files = {"hex", "xmlcon", "hdr"}
    if (residual := three_files - ds.keys()) != set():
        logger.error(f"The following filetypes are missing {residual}")
        return False
    logger.debug("All three files present")
    return True


def check_lat_lon_valid(ds: xr.Dataset) -> bool:
    """Checks if a valid lat/lon can even be extracted from the hex/header"""

    if "hdr" not in ds:
        return False

    lon = get_longitude(ds)
    lat = get_latitude(ds)

    return None not in (lon, lat)


def check_time_valid(ds: xr.Dataset) -> bool:
    """Checks if a valid time can even be extracted from the hex/header"""

    if "hdr" not in ds:
        return False

    dt = get_time(ds)

    return dt is not None


def check_lat_lon(ds: xr.Dataset, bbox: "BBox") -> bool:
    if "hdr" not in ds:
        return False

    lon = get_longitude(ds)
    lat = get_latitude(ds)

    if None in (lon, lat):
        return False

    return bbox.contains(lon, lat)


def check_dt(ds: xr.Dataset, dtrange: "DTRange") -> bool:
    if "hdr" not in ds:
        return False

    dt = get_time(ds)

    if dt is None:
        return False

    return dtrange.contains(dt)
