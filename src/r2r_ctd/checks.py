"""The basic check functions that are done on files or paths.

The original intent was that all the functions that produce the 4 element stoplight report would live here and be 1-1 with each check in that report.
It became clear that this was not going to work well pretty early as most of those report elements are from an aggregate over all the stations.
Additionally, some checks serve as a sieve, for example, stations where :py:func:`is_deck_test` returns true aren't checked or considered in the report at all.

The first check in the qa report is just checking that the breakout itself is valid before anything else happens.
That check is over in :py:obj:`r2r_ctd.breakout.Breakout.manifest_ok`.
"""

from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import xarray as xr

if TYPE_CHECKING:
    from r2r_ctd.breakout import BBox, Interval

logger = getLogger(__name__)


def is_deck_test(path: Path) -> bool:
    """Check if the given path "looks like" a deck test

    This method matches the pathname against a list of strings that are common to desk tests.
    """
    logger.info(f"Checking if {path} is a decktest")
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

    Stations are, at a minimum, expected to have a .hex, .xmlcon, and .hdr file all
    next to each other. For example, a ``00101.hex`` should have a ``00101.hdr`` and
    ``00101.xmlcon`` file also present. In practice, this files need to be found in a
    case insensitive way, for example, the associated ``.xmlcon`` for a ``rr1608_01.hex``
    file might be named ``RR1608_01.XMLCON``. The underlying odf.sbe library takes care
    of these details for us.

    The input dataset is expected conform output of odf.sbe.read_hex. This dataset
    is then checked to see if it has all the correct keys.
    """
    logger.info("Checking if all three files")
    three_files = {"hex", "xmlcon", "hdr"}
    if (residual := three_files - ds.keys()) != set():
        logger.error(f"The following filetypes are missing {residual}")
        return False
    logger.debug("All three files present")
    return True


def check_lon_lat_valid(ds: xr.Dataset) -> bool:
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


def check_lon_lat(ds: xr.Dataset, bbox: "BBox | None") -> bool:
    """Checks that the lon lat of the cast are within the cruise bounding box"""
    if "hdr" not in ds:
        return False
    if bbox is None:
        return False

    lon = ds.r2r.longitude
    lat = ds.r2r.latitude

    if None in (lon, lat):
        return False

    return bbox.contains(lon, lat)


def check_dt(ds: xr.Dataset, dtrange: "Interval | None") -> bool:
    """Checks that the time of the cast are within the cruise interval"""
    if "hdr" not in ds:
        return False

    if dtrange is None:
        return False

    dt = ds.r2r.time

    if dt is None:
        return False

    return dtrange.contains(dt)
