"""Functions that take some existing data, and either extract from or transform it

e.g. the :py:func:`get_longitude` function tries to extract the longitude information from the hdr file"""

from datetime import datetime
from logging import getLogger

import xarray as xr
from lxml import etree
from lxml.builder import ElementMaker
from odf.sbe import accessors  # noqa: F401
from odf.sbe.parsers import parse_hdr

from r2r_ctd.docker_ctl import run_con_report, run_sbebatch
from r2r_ctd.sbe import (
    binavg_template,
    datcnv_allsensors,
    datcnv_template,
    derive_template,
    sensors_con_to_psa,
)
from r2r_ctd.state import NamedBytes

logger = getLogger(__name__)


def _parse_coord(coord: str) -> float | None:
    """Parses a spaced separated DDM coordinate with hemisphere to decimal degrees

    >>> _parse_coord("32 52.02 N")
    32.867
    >>> _parse_coord("117 15.435 W")
    -117.25725
    """
    hem_ints = {
        "N": 1,
        "S": -1,
        "E": 1,
        "W": -1,
    }

    try:
        d_, m_, h_ = coord.split()
    except ValueError:
        logger.error(f"Could not unpack {coord} into DDM", exc_info=True)
        return None

    try:
        d = float(d_)
    except ValueError:
        logger.error(f"Could not parse degree {d_} as float", exc_info=True)
        return None

    try:
        m = float(m_)
    except ValueError:
        logger.error(f"Could not parse decimal minute {m_} as float", exc_info=True)
        return None

    try:
        h = hem_ints[h_.upper()]
    except KeyError:
        logger.error(f"Could not parse hemisphere {h_}", exc_info=True)
        return None

    return (d + (m / 60)) * h


def get_longitude(ds: xr.Dataset) -> float | None:
    """Get the cast longitude from NMEA header

    .. admonition:: WHOI Divergence
        :class: warning

        The original code from WHOI tries to also get this from the ``** Longitude`` line
        but I think the ``**`` means it is a comment and can be *anything* the user puts in.
    """
    headers = parse_hdr(ds.hdr.item())
    if (value := headers.get("NMEA Longitude")) is not None:
        return _parse_coord(value)

    return None


def get_latitude(ds: xr.Dataset) -> float | None:
    """Get the cast latitude from NMEA header

    .. admonition:: WHOI Divergence
        :class: warning

        The original code from WHOI tries to also get this from the ``** Latitude`` line
        but I think the ``**`` means it is a comment and can be *anything* the user puts in.
    """
    headers = parse_hdr(ds.hdr.item())
    if (value := headers.get("NMEA Latitude")) is not None:
        return _parse_coord(value)

    return None


def _normalize_date_strings(date: str) -> str:
    """Try to make the date strings in sbe hdr files have a consistent format

    There can be variable whitespace between time elements, this function
    tries to remove them so we can use the normal strptime method.

    >>> _normalize_date_strings("Oct 09 2019  17:05:53")
    'Oct 09 2019 17:05:53'
    """
    return " ".join(date.split())


def get_time(ds: xr.Dataset) -> datetime | None:
    """Gets the time from the hdr file

    In the following priority order:
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
            return dt

    logger.warning("No time value could be parsed")
    return None


def make_con_report(ds: xr.Dataset):
    """Runs ConReport.exe on the xmlcon file in the dataset"""
    xmlcon = NamedBytes(ds.sbe.to_xmlcon(), name=ds.xmlcon.attrs["filename"])
    return run_con_report(xmlcon)


def get_model(con_report: str) -> str | None:
    """Given a configuration report, get the SBE model string

    Uses string matching and doesn't parse/transform the model lines in the config report.
    """
    if "Configuration report for SBE 25" in con_report:
        return "SBE25"
    if "Configuration report for SBE 49" in con_report:
        return "SBE49"
    if "Configuration report for SBE 911plus" in con_report:
        return "SBE911"
    if "Configuration report for SBE 19plus" in con_report:
        return "SBE19"

    return None


def _con_report_extract_sensors(con_report: str) -> list[str]:
    """Extract a list of sensors from a configuration report, adds some virtual sensors if NMEA information was added to the data

    This is looking for lines in the form of::

        1) channel type, sensor name

    eg::

        1) Frequency 0, Temperature

    Then extracting the "sensor name" part of that line.

    If "NMEA position data added" is "yes", virtual latitude and longitude sensors are added to the list.
    If "NMEA time added" is "yes", a virtual "ETime" sensor is added to the list.
    If the model of the instrument is an SBE911, a "pump" sensor is added to the list.
    """
    sensors = []
    model = get_model(con_report)

    for line in con_report.splitlines():
        # there are 3 "virtual" sensors that get added if certain flags are set (position and time)
        # there is no fixed amount of space between the label and the :yes or :no, so we just squish everything
        # into a single lowercase no space string.
        no_whitespace_line = line.replace(" ", "").lower()
        if no_whitespace_line == "nmeapositiondataadded:yes":
            sensors.append("Latitude")
            sensors.append("Longitude")
        if no_whitespace_line == "nmeatimeadded:yes":
            sensors.append("ETime")

        try:
            section, title = line.split(")", maxsplit=1)
            int(section)  # we only care that this doesn't raise
            _, sensor = title.split(",", maxsplit=1)
            sensors.append(sensor.strip())
        except ValueError:
            pass

    if model == "SBE911":
        sensors.append("pumps")

    return sensors


def get_con_report_sn(con_report: str, instrument: str) -> list[str]:
    """Get the serial numbers for instruments from the configuration report (XMLCON)."""
    title = ""
    sns = []
    for line in con_report.splitlines():
        try:
            section, title = line.split(")", maxsplit=1)
            int(section)
        except ValueError:
            pass
        if instrument not in title:
            continue

        try:
            key, value = line.split(":", maxsplit=1)
        except ValueError:
            continue

        key = key.strip().lower()
        value = value.strip()

        if key == "serial number" and value not in sns:
            sns.append(value)

    return sns


def get_hdr_sn(hdr: str, instrument: str) -> str | None:
    """Get an instruments serial number from the .hdr file.

    That this serial number intersects with the set generated by :py:func:`get_con_report_sn` is reported in the QA.
    """
    header = parse_hdr(hdr)
    return header.get(f"{instrument} SN")


def make_derive_psa(con_report: str) -> bytes:
    """Makes the derive psa config file for derive.exe based on the configuration report, will add second density calculation if dual channel"""
    E = ElementMaker()
    template = derive_template()
    sensors = _con_report_extract_sensors(con_report)
    is_dual_channel = {"Temperature, 2", "Conductivity, 2"} <= set(sensors)
    logger.info(f"Cast is dual channel: {is_dual_channel}")

    if is_dual_channel:
        logger.info("Cast is dual channel adding second density to derive psa")
        second_density = E.CalcArrayItem(
            E.Calc(
                E.FullName(value="Density, 2 [density, kg/m^3]"),
                UnitID="11",
                Ordinal="1",
            ),
            index="1",
            CalcID="15",
        )
        if (calc_array := template.find(".//CalcArray")) is not None:
            calc_array.append(second_density)
            calc_array.attrib["Size"] = "2"
        else:
            raise RuntimeError(
                "Could not find CalcArray in built in derive psa file, this indicates a broken installation"
            )

    return etree.tostring(
        template,
        pretty_print=True,
        xml_declaration=True,
        method="xml",
        encoding="UTF-8",
    )


def make_binavg_psa(con_report: str) -> bytes:
    """Get the binage psa config from :py:func:`r2r_ctd.sbe.binavg_template` and return it unmodified."""
    template = binavg_template()
    return etree.tostring(
        template,
        pretty_print=True,
        xml_declaration=True,
        method="xml",
        encoding="UTF-8",
    )


def make_datcnv_psa(con_report: str) -> bytes:
    """Make the datcnv psa config based on the configuration report, populating the CalcArray element"""
    allsensors = datcnv_allsensors()
    template = datcnv_template()

    calc_array_items = []
    for sensor in _con_report_extract_sensors(con_report):
        if sensor == "Free":
            continue
        if sensor not in sensors_con_to_psa:
            # something new? this needs an update procedure...
            continue

        psa_sensors = sensors_con_to_psa[sensor]
        for psa_sensor in psa_sensors:
            calc_array_items.extend(
                allsensors.xpath(
                    "//CalcArrayItem[./Calc/FullName[@value=$psa_sensor]]",
                    psa_sensor=psa_sensor,
                ),
            )
    for index, item in enumerate(calc_array_items):
        item.attrib["index"] = str(index)

    if (calc_array := template.find(".//CalcArray")) is not None:
        calc_array.extend(calc_array_items)
        calc_array.attrib["Size"] = str(len(calc_array))
    else:
        raise RuntimeError(
            "Could not find CalcArray in built in derive psa file, this indicates a broken installation"
        )

    return etree.tostring(
        template,
        pretty_print=True,
        xml_declaration=True,
        method="xml",
        encoding="UTF-8",
    )


def make_cnvs(ds: xr.Dataset) -> dict[str, xr.Dataset]:
    """Makes the derived cnv files

    Creates all the various configuration files, then passes everything off to the companion container to actually be processed.
    """
    con_report = ds.r2r.con_report

    datcnv = NamedBytes(make_datcnv_psa(con_report), name="datcnv.psa")
    derive = NamedBytes(make_derive_psa(con_report), name="derive.psa")
    binavg = NamedBytes(make_binavg_psa(con_report), name="binavg.psa")

    xmlcon = NamedBytes(ds.sbe.to_xmlcon(), name=ds.xmlcon.attrs["filename"])
    hex = NamedBytes(ds.sbe.to_hex(), name=ds.hex.attrs["filename"])

    return run_sbebatch(hex, xmlcon, datcnv, derive, binavg)
