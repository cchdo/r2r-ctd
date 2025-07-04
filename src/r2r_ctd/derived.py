from pathlib import Path
from tempfile import TemporaryDirectory

from r2r_ctd.docker_ctl import run_conreport

from odf.sbe import accessors  # noqa: F401
import xarray as xr

def get_latitude(ds) -> float:
    ...

def get_longitude(ds) -> float:
    ...

def get_time(ds:xr.Dataset) -> float:
    ...

def make_conreport(ds: xr.Dataset):
    with TemporaryDirectory() as tmpdir:
        tmpdirp = Path(tmpdir)
        xmlcon_path = tmpdirp / ds.xmlcon.attrs["filename"]
        ds.sbe.to_xmlcon(xmlcon_path)
        return run_conreport(Path(tmpdir), xmlcon_path)
