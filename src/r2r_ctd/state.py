"""Functions for manipulating the state netCDF files and getting paths for derived files.

Anything that modifies the state must go though functions contained here.
This module also contains a bunch of functions that calculate where output files should go."""

from collections.abc import Callable
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

import numpy as np
import xarray as xr
from odf.sbe import read_hex

from r2r_ctd.exceptions import InvalidSBEFileError

if TYPE_CHECKING:
    from r2r_ctd.breakout import Breakout

R2R_QC_VARNAME = "r2r_qc"
"""Variable name used within the state netCDF files a an attribute key-value container.
This is done to keep all the qa result contained instead of e.g. prefixing attribute names and having everything as a global attribute."""

logger = getLogger(__name__)


class NamedBytes(bytes):
    """bytes object that has a name string property

    This is for passing around files with their names internally.
    The instance objects are "fragile" in that the name property will get dropped on any operation
    that returns a new bytes object (which is most of them).

    >>> b = NamedBytes(b'hello world', name="example.txt")
    >>> b
    b'hello world'
    >>> b.name
    'example.txt'
    """

    name: str

    def __new__(cls, *args, name: str = ""):
        b = super().__new__(cls, *args)
        b.name = name
        return b


class CheckFunc(Protocol):
    def __call__(self, ds: xr.Dataset, *args: Any, **kwargs: Any) -> bool: ...


def write_ds_r2r(ds: xr.Dataset) -> None:
    """Given a Dataset, serialize it to the path contained on the ```__path``` global attribute.

    The ``__path`` attribute is not serialized, but rather added by the :py:func:`initialize_or_get_state` on read in.
    """
    path = ds.attrs.pop("__path")
    ds.to_netcdf(path, mode="a")
    logger.debug(f"State saved to {path}")
    ds.attrs["__path"] = path


def get_state_path(breakout: "Breakout", hex_path: Path) -> Path:
    """Given a breakout and hex_path in that breakout, calculate what the state path would be"""
    nc_dir = breakout.path / "proc" / "nc"

    if not nc_dir.exists():
        logger.debug(f"Making nc state directory {nc_dir}")

    nc_dir.mkdir(exist_ok=True, parents=True)

    nc_fname = hex_path.with_suffix(".nc").name
    return nc_dir / nc_fname


def get_qa_dir(breakout: "Breakout") -> Path:
    """Determine the directory path used for QA output files, creating it if necessary."""
    qa_dir = breakout.path / "proc" / "qa"
    qa_dir.mkdir(exist_ok=True, parents=True)

    return qa_dir


def get_xml_qa_path(breakout: "Breakout") -> Path:
    """Get the path of where to write the QA XML report.

    This is the same name as the template, but with xml instead of xmlt"""
    xml_qa_name = breakout.qa_template_path.with_suffix(".xml").name
    return get_qa_dir(breakout) / xml_qa_name


def get_geoCSV_path(breakout: "Breakout") -> Path:
    """Get the path of where to write the geoCSV file.

    This is the same name as the XML template, but with _ctd_metdata.geoCSV ``_ctd_metdata.geoCSV`` suffix
    rather than ``_qa.2.0.xmlt``.
    """
    geocsv_name = breakout.qa_template_path.name.replace(
        "_qa.2.0.xmlt",
        "_ctd_metdata.geoCSV",
    )

    return get_qa_dir(breakout) / geocsv_name


def get_config_path(breakout: "Breakout") -> Path:
    """Get the directory for writing the seabird configuration report files, creating it if necessary"""
    config_path = get_qa_dir(breakout) / "config"
    config_path.mkdir(exist_ok=True, parents=True)

    return config_path


def get_product_path(breakout: "Breakout") -> Path:
    """Get the directory to write the cnv product files to, creating it if necessary."""
    product_dir = breakout.path / "proc" / "products" / "r2rctd"
    product_dir.mkdir(exist_ok=True, parents=True)

    return product_dir


def get_filename(da: xr.DataArray) -> str:
    """Gets the ``filename`` attribute of a DataArray object that represents a file.

    This is mostly use as sugar for type casting to a string"""
    return cast("str", da.attrs["filename"])


def initialize_or_get_state(breakout: "Breakout", hex_path: Path) -> xr.Dataset:
    """Given a hex_path, get the state as an xarray Dataset

    This will either find the existing netCDF file and open it (not load) or make
    a new state Dataset by calling :py:func:`odf.sbe.read_hex` on that path.

    This adds an attribute to the dataset ``__path`` that is used to keep track of where this
    file is actually written.
    This attribute is stripped by :py:func:`write_ds_r2r` when the Dataset is serialized.
    """
    state_path = get_state_path(breakout, hex_path)

    if state_path.exists():
        logger.debug(f"Found existing state file: {state_path}, skipping read_hex")
        ds = xr.open_dataset(state_path, mode="a")
        ds.attrs["__path"] = state_path
        return ds

    logger.debug(f"Reading {hex_path} using odf.sbe.read_hex")
    data = read_hex(hex_path)
    data.attrs["__path"] = state_path

    data[R2R_QC_VARNAME] = xr.DataArray()
    data[R2R_QC_VARNAME].attrs["station_name"] = hex_path.stem

    write_ds_r2r(data)

    return data


def get_or_write_derived_file(ds: xr.Dataset, key: str, func: Callable, **kwargs):
    """Get a derived file either from the state, or from the result of the callable func.

    This function is used to store create and store the instrument configuration reports and cnv files.
    The callable ``func`` will be passed the dataset ``ds`` as the first argument and any extra ``kwargs``.
    The ``ds`` will be checked for ``key`` before ``func`` is called and if present, those contents will be returned and ``func`` will not be called.

    If ``func`` returns a dictionary mapping of keys to DataArrays, then ``key`` must be one of the keys in that dict.
    All keys in the mapping will be stored on ds.

    This function also checks if the callable raises an :py:class:`InvalidSBEFileError` and also skips calling ``func`` returning None instead.
    """
    filename = ""
    if "hex" in ds:
        filename = ds.hex.attrs["filename"]

    if key in ds:
        logger.debug(f"{filename} - Found existing {key}, skipping regeneration")
        return ds[key]

    error_key = f"{key}_error"
    if R2R_QC_VARNAME in ds and ds[R2R_QC_VARNAME].attrs.get(error_key) is not None:
        logger.debug(f"{filename} - Previously failed to generate {key} not retrying")
        return None

    try:
        result = func(ds, **kwargs)
    except InvalidSBEFileError:
        get_or_write_check(ds, error_key, lambda ds, **kwargs: False)
        return None

    if isinstance(result, dict):
        if key not in result:
            raise ValueError(
                f"{filename} - Callable func returning dictionary must have key {key}, got {result.keys()}",
            )
        for _key, value in result.items():
            ds[_key] = value
    else:
        ds[key] = result

    write_ds_r2r(ds)
    return ds[key]


def get_or_write_check(ds: xr.Dataset, key: str, func: CheckFunc, **kwargs) -> bool:
    """Get or determine and write the boolean result of `func`

    The callable ``func`` will be passed the dataset ``ds`` as the first argument and any extra ``kwargs``.
    ``func`` must return a boolean value which will then be stored on ``ds`` in the attributes a special variable :py:obj:`R2R_QC_VARNAME`.
    This object simply serves as a container for these results.

    .. note::
        netCDF doesn't have a boolean data type, so these checks are stored as literal 1 or 0 inside the state file.
    """
    filename = ""
    if "hex" in ds:
        filename = ds.hex.attrs["filename"]

    if R2R_QC_VARNAME not in ds:
        ds[R2R_QC_VARNAME] = xr.DataArray()

    if key in ds[R2R_QC_VARNAME].attrs:
        value = ds[R2R_QC_VARNAME].attrs[key]
        logger.debug(
            f"{filename} - {key}: found result already with value {bool(value)}, skipping test",
        )
        return bool(value)

    logger.debug(f"{filename}: Results not found running test {key}")
    check_result = func(ds, **kwargs)
    logger.debug(
        f"{filename}: Test result for {key} if {check_result}, writing to state",
    )
    ds[R2R_QC_VARNAME].attrs[key] = np.int8(check_result)
    write_ds_r2r(ds)

    return check_result
