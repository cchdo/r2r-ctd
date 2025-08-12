"""Loaders for config and templates for SBEBatch.exe

This contains (as package data) some SBE config templates and instrument lists.
There is also a mapping between instruments and their derived parameters.
Most of these files were inherited and I do not know how they were made or what situations would require updating, some hints however:

batch.txt
    Contains the SBEBatch.exe "batch file", it probably will not need to be modified, but :py:func:`r2r_ctd.docker_ctl.run_sbebatch` depends on this being the way it is.

binavg_template.xml
    Has no station/cast specific config and will probably not need modifying unless there is some reason to change the bin size.

datcnv_allsensors.xml
    This contains a collection of CalcArrayItem elements that are inserted into the CalcArray of the datcnv_template.xml.
    The elements that get inserted are station specific.
    sensors.toml maps between what the .xmlcon of a station calls a sensors, to what datcnv_allsensors.xml expects.

    This file, along with sensors.toml will need to be modified if a new sensor and calculated output need to be added.

datcnv_template.xml
    Contains the basic config for converting the raw hex into a table like cnv text file.
    This is missing the actual parameters that are output, which come from the datcnv_allsensors.xml

derive_template.xml
    Contains the configuration for calculating density, it might be modified by adding a second density channel if the station has secondary temperature and conductivity sensors.
    See :py:func:`r2r_ctd.derived.make_derive_psa`

sensors.toml
    Has a mapping between .xmlcon sensor name and one or more CalcArrayItems in datcnv_allsensors.xml.

    This file, along with datcnv_allsensors.xml will need to be modified if a new sensor and calculated output need to be added.
"""

from importlib.resources import path, read_text
from tomllib import loads

from lxml import etree

import r2r_ctd

sensors_con_to_psa = loads(read_text(r2r_ctd, "sbe/sensors.toml"))
"""Mapping between what the sensors are called in ConReport.exe and their derived parameters in the SBEBatch configuration psa files.

This difference is mostly due to sensor names not having units, but also some sensors have more than one output, e.g. the pressure
sensors is converted to pressure in dbar and depth in the water column (meters).

The inherited file was a custom text format that was very close to TOML, so I converted it to TOML rather than port the custom parsing code.
I do not know how this file was generated.
"""

batch = read_text(r2r_ctd, "sbe/batch.txt")
"""Static batch.txt file that is passed to SBEBatch.exe see the `SBE Data Processing Manual`_

.. _SBE Data Processing Manual: https://www.seabird.com/asset-get.download.jsa?code=251446
"""


def _xml_loader(fname: str) -> etree._ElementTree:
    """Loads an internal xml file and returns a new element tree object.

    Manipulating the lxml element tree is basically all side effect based, so a new template needs to be loaded for each station.
    """
    with path(r2r_ctd, fname) as fspath:
        return etree.parse(fspath, etree.XMLParser(remove_blank_text=True))


def datcnv_allsensors():
    """Load the xml document containing all possible sensors.

    The input xmlcon file is examined and the "calcarray" element is populated with the sensors from this template.
    """
    return _xml_loader("sbe/datcnv_allsensors.xml")


def datcnv_template():
    """Load the xml document containing the raw conversion configuration.

    The calcarray element is empty and needs to be populated with items from the :py:func:`datcnv_allsensors` document on a per station basis"""
    return _xml_loader("sbe/datcnv_template.xml")


def binavg_template():
    """Load the xml document containing the bin average configuration.

    This document has no station specific configuration.
    """
    return _xml_loader("sbe/binavg_template.xml")


def derive_template():
    """Load the xml document containing the derive configuration, in this case only density is derived.

    This document has may have a second density calculation added to it by :py:func:`r2r_ctd.derived.make_derive_psa` if there is a second temp and conductivity channel.
    """
    return _xml_loader("sbe/derive_template.xml")
