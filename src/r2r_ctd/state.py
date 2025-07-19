from pathlib import Path
from logging import getLogger
from typing import Callable, Protocol, Any, TYPE_CHECKING

import xarray as xr
import numpy as np

from odf.sbe import read_hex

if TYPE_CHECKING:
    from r2r_ctd.breakout import Breakout

R2R_QC_VARNAME = "r2r_qc"

logger = getLogger(__name__)

class NamedFile(bytes):
    name: str
    def __new__(cls, *args, name: str = ""):
        b = super().__new__(cls, *args)
        b.name = name
        return b

class CheckFunc(Protocol):
    def __call__(self, ds: xr.Dataset, **kwargs: Any) -> bool: ...


def write_ds_r2r(ds: xr.Dataset) -> None:
    path = ds.attrs.pop("__path")
    ds.to_netcdf(path, mode="a")
    logger.debug(f"State saved to {path}")
    ds.attrs["__path"] = path


def get_state_path(breakout: "Breakout", hex_path: Path) -> Path:
    nc_dir = breakout.path / "proc" / "nc"

    if not nc_dir.exists():
        logger.debug(f"Making nc state directory {nc_dir}")

    nc_dir.mkdir(exist_ok=True, parents=True)

    nc_fname = hex_path.with_suffix(".nc").name
    return nc_dir / nc_fname


def get_xml_qa_path(breakout: "Breakout") -> Path:
    xml_qa_name = breakout.qa_template_path.with_suffix(".xml").name

    qa_dir = breakout.path / "proc"
    qa_dir.mkdir(exist_ok=True, parents=True)

    return qa_dir / xml_qa_name


def initialize_or_get_state(breakout: "Breakout", hex_path: Path) -> xr.Dataset:
    state_path = get_state_path(breakout, hex_path)

    if state_path.exists():
        logger.debug(f"Found existing state file: {state_path}, skipping read_hex")
        ds = xr.open_dataset(state_path, mode="a")
        ds.attrs["__path"] = state_path
        return ds

    logger.debug(f"Reading {hex_path} using odf.sbe.read_hex")
    data = read_hex(hex_path)
    data.attrs["__path"] = state_path

    write_ds_r2r(data)

    return data


def get_or_write_derived_file(ds: xr.Dataset, key: str, func: Callable, **kwargs):
    if key in ds:
        logger.debug(f"Found existing {key}, skipping regeneration")
        return ds[key]

    result = func(ds, **kwargs)
    if isinstance(result, dict):
        if key not in result:
            raise ValueError(f"Callable func returning dictionary must have key {key}, got {result.keys()}")
        for _key, value in result.items():
            ds[_key] = value
    else:
        ds[key] = result

    write_ds_r2r(ds)
    return ds[key]


def get_or_write_check(ds: xr.Dataset, key: str, func: CheckFunc, **kwargs) -> bool:
    if R2R_QC_VARNAME not in ds:
        ds[R2R_QC_VARNAME] = xr.DataArray()

    if key in ds[R2R_QC_VARNAME].attrs:
        value = ds[R2R_QC_VARNAME].attrs[key]
        logger.debug(
            f"{key}: found result already with value {bool(value)}, skipping test"
        )
        return bool(value)

    logger.debug(f"Results not found running test {key}")
    check_result = func(ds, **kwargs)
    logger.debug(f"Test result for {key} if {check_result}, writing to state")
    ds[R2R_QC_VARNAME].attrs[key] = np.int8(check_result)
    write_ds_r2r(ds)

    return check_result
