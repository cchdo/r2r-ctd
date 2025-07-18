from datetime import datetime
from logging import getLogger

from r2r_ctd.docker_ctl import run_conreport
from r2r_ctd.sbe import (
    binavg_template,
    derive_template,
    sensors_con_to_psa,
    datcnv_allsensors,
    datcnv_template,
)

from odf.sbe import accessors  # noqa: F401
from odf.sbe.parsers import parse_hdr

import xarray as xr
from lxml import etree
from lxml.builder import ElementMaker

logger = getLogger(__name__)

E = ElementMaker()


def _parse_coord(coord: str) -> float | None:
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
        return

    try:
        d = float(d_)
    except ValueError:
        logger.error(f"Could not parse degree {d_} as float", exc_info=True)
        return

    try:
        m = float(m_)
    except ValueError:
        logger.error(f"Could not parse decimal minute {m_} as float", exc_info=True)
        return

    try:
        h = hem_ints[h_.upper()]
    except KeyError:
        logger.error(f"Could not parse hemisphere {h_}", exc_info=True)
        return

    return (d + (m / 60)) * h


def get_longitude(ds: xr.Dataset) -> float | None:
    """Get the cast longitude from NMEA header

    The original code from WHOI tries to also get this from the ** Longitude line
    but the ** means it is a comment and can be _anything_ the user puts in.
    """
    headers = parse_hdr(ds.hdr.item())
    if (value := headers.get("NMEA Longitude")) is not None:
        return _parse_coord(value)


def get_latitude(ds) -> float:
    """Get the cast latitude from NMEA header

    See the docstring for get_longitude for comment on original code"""

    headers = parse_hdr(ds.hdr.item())
    if (value := headers.get("NMEA Latitude")) is not None:
        return _parse_coord(value)


def _normalize_date_strings(date: str) -> str:
    """Try to make the date strings in sbe hdr files have a consistent format

    There can be variable whitespace between time elements, this function
    tries to remove them so we can use the normal strptime method.
    """
    return " ".join(date.split())


def get_time(ds: xr.Dataset) -> float | None:
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
            return dt

    logger.warning("No time value could be parsed")


def make_conreport(ds: xr.Dataset):
    return run_conreport(ds.xmlcon.attrs["filename"], ds.sbe.to_xmlcon())


def get_model(conreport: str) -> str | None:
    if "Configuration report for SBE 25" in conreport:
        return "SBE25"
    if "Configuration report for SBE 49" in conreport:
        return "SBE49"
    if "Configuration report for SBE 911plus" in conreport:
        return "SBE911"
    if "Configuration report for SBE 19plus" in conreport:
        return "SBE19"


def _conreport_extract_sensors(conreport: str) -> list[str]:
    sensors = []
    for line in conreport.splitlines():
        # there are 3 "virtual" sensors that get added if certain flags are set (position and time)
        no_whitespace_line = line.replace(" ", "").lower()
        if no_whitespace_line == "nmeapositiondataadded:yes":
            sensors.append("Latitude")
            sensors.append("Longitude")
        if no_whitespace_line == "nmeatimeadded:yes":
            sensors.append("ETime")

        try:
            section, title = line.split(")", maxsplit=1)
            section = int(section)
            _, sensor = title.split(",", maxsplit=1)
            sensors.append(sensor.strip())
        except ValueError:
            pass

    return sensors


def _conreport_sn_getter(conreport: str, instrument: str) -> set[str]:
    section = 0
    title = ""
    sns = []
    for line in conreport.splitlines():
        try:
            section, title = line.split(")", maxsplit=1)
            section = int(section)
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

        if key == "serial number":
            sns.append(value)

    return set(sns)


def _hdr_sn_getter(hdr: str, instrument: str) -> str | None:
    header = parse_hdr(hdr)
    return header.get(f"{instrument} SN")


def make_derive_psa(conreport: str) -> str:
    template = derive_template()
    sensors = _conreport_extract_sensors(conreport)
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
        template.find(".//CalcArray").append(second_density)
        template.find(".//CalcArray").attrib["Size"] = "2"

    return etree.tostring(
        template,
        pretty_print=True,
        xml_declaration=True,
        method="xml",
        encoding="UTF-8",
    ).decode()


def make_binavg_psa(conreport: str) -> str:
    """This is a noop, but included for a consistent API"""
    template = binavg_template()
    return etree.tostring(
        template,
        pretty_print=True,
        xml_declaration=True,
        method="xml",
        encoding="UTF-8",
    ).decode()


def make_datcnv_psa(conreport: str) -> str:
    allsensors = datcnv_allsensors()
    template = datcnv_template()

    calc_array = []
    for sensor in _conreport_extract_sensors(conreport):
        if sensor == "Free":
            continue
        if sensor not in sensors_con_to_psa:
            ...
            # something new? this needs an update procedure...
            continue

        psa_sensors = sensors_con_to_psa[sensor]
        for psa_sensor in psa_sensors:
            calc_array.extend(
                allsensors.xpath(
                    "//CalcArrayItem[./Calc/FullName[@value=$psa_sensor]]",
                    psa_sensor=psa_sensor,
                )
            )
    for index, item in enumerate(calc_array):
        item.attrib["index"] = str(index)

    template.find(".//CalcArray").extend(calc_array)
    template.find(".//CalcArray").attrib["Size"] = str(len(calc_array))

    return etree.tostring(
        template,
        pretty_print=True,
        xml_declaration=True,
        method="xml",
        encoding="UTF-8",
    ).decode()
