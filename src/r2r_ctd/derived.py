from pathlib import Path
from tempfile import TemporaryDirectory

from r2r_ctd.docker_ctl import run_conreport

from odf.sbe import accessors as _accessors

def make_conreport(ds):
    with TemporaryDirectory() as tmpdir:
        tmpdirp = Path(tmpdir)
        xmlcon_path = tmpdirp / ds.xmlcon.attrs["filename"]
        ds.sbe.to_xmlcon(xmlcon_path)
        return run_conreport(Path(tmpdir), xmlcon_path)