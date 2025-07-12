from pathlib import Path
from logging import getLogger
from tempfile import TemporaryDirectory
import atexit

from odf.sbe.io import string_loader

import docker


logger = getLogger(__name__)

client = docker.from_env()
tmpdir = TemporaryDirectory()
container = client.containers.run(
    "r2r/sbe",
    auto_remove=True,
    detach=True,
    volumes={str(tmpdir.name): {"bind": "/.wine/drive_c/proc", "mode": "rw"}},
)


def _kill_container():
    print(f"attempting to kill wine container: {container.name}")
    container.kill()


atexit.register(_kill_container)

conreport_sh = r"""export DISPLAY=:1
export HODLL=libwow64fex.dll
export WINEPREFIX=/.wine

cd /.wine/drive_c/;
for file in proc/in/*
do
  wine "Program Files (x86)/Sea-Bird/SBEDataProcessing-Win32/ConReport.exe" "${file}" "C:\proc\out"
done
exit 0;
"""


def run_conreport(fname: str, xmlcon: str):
    work_dir = Path(tmpdir.name)
    sh = work_dir / "sh" / "conreport.sh"
    if sh.exists():
        sh.unlink()
    sh.parent.mkdir(exist_ok=True, parents=True)
    sh.write_text(conreport_sh)
    sh.chmod(0o555)

    indir = work_dir / "in"
    indir.mkdir(exist_ok=True, parents=True)

    infile = indir / fname
    infile.write_bytes(xmlcon)

    outdir = work_dir / "out"
    outdir.mkdir(exist_ok=True, parents=True)

    conreport_logs = container.exec_run(
        'su -c "/.wine/drive_c/proc/sh/conreport.sh" abc',
    )
    logger.debug(conreport_logs)
    out_path = outdir / infile.with_suffix(".txt").name

    conreport = string_loader(out_path, "conreport").conreport

    # try to clean up
    infile.unlink(missing_ok=True)
    out_path.unlink(missing_ok=True)

    return conreport
