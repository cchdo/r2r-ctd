from tomllib import loads
from importlib.resources import read_text, path
import r2r_ctd
from lxml import etree

sensors_con_to_psa = loads(read_text(r2r_ctd, "sbe/sensors.toml"))

batch = read_text(r2r_ctd, "sbe/batch.txt")

# This needs to be a function that returns a new
# object because lxml et al. likes doing things by
# reference or side effect
def _xml_loader(fname: str) -> etree._ElementTree:
    with path(r2r_ctd, fname) as fspath:
        return etree.parse(fspath, etree.XMLParser(remove_blank_text=True))


def datcnv_allsensors():
    return _xml_loader("sbe/datcnv_allsensors.xml")


def datcnv_template():
    return _xml_loader("sbe/datcnv_template.xml")


def binavg_template():
    return _xml_loader("sbe/binavg_template.xml")


def derive_template():
    return _xml_loader("sbe/derive_template.xml")
