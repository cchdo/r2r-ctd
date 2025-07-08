from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
from logging import getLogger

from r2r_ctd.docker_ctl import run_conreport

from odf.sbe import accessors  # noqa: F401
from odf.sbe.parsers import parse_hdr

import xarray as xr

logger = getLogger(__name__)

def get_latitude(ds) -> float:
    ...

def get_longitude(ds) -> float:
    ...

def _normalize_date_strings(date:str) -> str:
    """Try to make the date strings in sbe hdr files have a consistent format

    There can be variable whitespace between time elements, this function
    tries to remove them so we can use the normal strptime method.
    """
    return " ".join(date.split())


def get_time(ds:xr.Dataset) -> float | None:
    """Gets the time from the hdr file
    
    In the following prioirty order:
    * NMEA UTC (Time)
    * System UTC
    * System Upload Time
    """
    time_headers = ("NMEA UTC (Time)", "System UTC", "System UpLoad Time")

    headers = parse_hdr(ds.hdr.item())

    for hdr in time_headers:
        if (value := headers.get(hdr)) is not None:
            logger.debug(f"Found time header {hdr}")
            normalized = _normalize_date_strings(value)
            logger.debug(f"Time header normalized from `{value}` to `{normalized}`")

            try:
                dt = datetime.strptime(normalized, "%b %d %Y %H:%M:%S")
            except ValueError:
                logger.error("Could not parse header time value", exc_info=True)
                continue
            return dt.timestamp()

    logger.warning("No time value could be parsed")

def make_conreport(ds: xr.Dataset):
    with TemporaryDirectory() as tmpdir:
        tmpdirp = Path(tmpdir)
        xmlcon_path = tmpdirp / ds.xmlcon.attrs["filename"]
        ds.sbe.to_xmlcon(xmlcon_path)
        return run_conreport(Path(tmpdir), xmlcon_path)
