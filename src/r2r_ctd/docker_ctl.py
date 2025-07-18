from pathlib import Path
from logging import getLogger
from tempfile import TemporaryDirectory
import atexit
from typing import cast, Mapping

from odf.sbe.io import string_loader

import docker

logger = getLogger(__name__)

_container = None  # singleton of the sbe container
_tmpdir = TemporaryDirectory()  # singleton tempdir for IO with docker container


def get_container():
    global _container
    if _container is not None:
        return _container
    logger.info("Launching container for running SBE software")
    client = docker.from_env()
    labels = ["us.rvdata.ctd-proc"]
    _container = client.containers.run(
        "r2r/sbe",
        auto_remove=True,
        detach=True,
        volumes={str(_tmpdir.name): {"bind": "/.wine/drive_c/proc", "mode": "rw"}},
        labels=labels,
        # The following binds an ephemeral port to 127.0.0.1 and not 0.0.0.0
        # we are doing this for security reasons
        # looks like the python typeshed is not correct here so I am casting to
        # something it knows about
        ports=cast(Mapping[str, None], {"3000/tcp": ("127.0.0.1",)}),
    )
    logger.info(f"Container launched as {_container.name} with labels: {labels}")

    def _kill_container():
        logger.info(f"attempting to kill wine container: {_container.name}")
        _container.kill()

    atexit.register(_kill_container)

    return _container


conreport_sh = r"""export DISPLAY=:1
export HODLL=libwow64fex.dll
export WINEPREFIX=/.wine

cd /.wine/drive_c/;
for file in proc/$TMPDIR_R2R/in/*
do
  wine "Program Files (x86)/Sea-Bird/SBEDataProcessing-Win32/ConReport.exe" "${file}" "C:\proc\\${TMPDIR_R2R}\out"
done
exit 0;
"""


def run_conreport(fname: str, xmlcon: bytes):
    container = get_container()

    with TemporaryDirectory(dir=_tmpdir.name) as condir:
        work_dir = Path(condir)
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
            f'su -c "/.wine/drive_c/proc/{work_dir.name}/sh/conreport.sh" abc',
            demux=True,
            environment={"TMPDIR_R2R": work_dir.name},
        )
        try:
            logger.debug(conreport_logs.output[1].decode())  # Stderr
        except IndexError:
            pass

        logger.info(conreport_logs.output[0].decode())  # stdout

        out_path = outdir / infile.with_suffix(".txt").name

        conreport = string_loader(out_path, "conreport").conreport

        return conreport
