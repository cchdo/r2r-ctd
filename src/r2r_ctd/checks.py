from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import xarray as xr

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
    return any(substr in path.name.lower() for substr in substrs)


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

    lon = ds.r2r.longitude
    lat = ds.r2r.latitude

    return None not in (lon, lat)


def check_time_valid(ds: xr.Dataset) -> bool:
    """Checks if a valid time can even be extracted from the hex/header"""
    if "hdr" not in ds:
        return False

    return ds.r2r.time is not None


def check_lat_lon(ds: xr.Dataset, bbox: "BBox | None") -> bool:
    if "hdr" not in ds:
        return False
    if bbox is None:
        return False

    lon = ds.r2r.longitude
    lat = ds.r2r.latitude

    if None in (lon, lat):
        return False

    return bbox.contains(lon, lat)


def check_dt(ds: xr.Dataset, dtrange: "DTRange | None") -> bool:
    if "hdr" not in ds:
        return False

    if dtrange is None:
        return False

    dt = ds.r2r.time

    if dt is None:
        return False

    return dtrange.contains(dt)
