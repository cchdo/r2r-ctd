from pathlib import Path
from logging import getLogger
from tempfile import TemporaryDirectory
import atexit
from typing import cast, Mapping
import time

from odf.sbe.io import string_loader

import docker

from r2r_ctd.exceptions import InvalidXMLCONError
from r2r_ctd.state import NamedFile
from r2r_ctd.sbe import batch

SBEDP_IMAGE = "ghcr.io/cchdo/sbedp:v2025.07.1"

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
        SBEDP_IMAGE,
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

    tries = 10
    while tries:
        _container.reload()
        if _container.health == "healthy":
            return _container
        time.sleep(0.5)
        tries -= 1
    raise Exception("Could not start container after 5 seconds")


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


def run_conreport(xmlcon: NamedFile):
    container = get_container()

    logger.info(f"Running in container {container.name}")
    logger.info(f"{xmlcon.name} - Running ConReport.exe")

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

        infile = indir / xmlcon.name
        infile.write_bytes(xmlcon)

        outdir = work_dir / "out"
        outdir.mkdir(exist_ok=True, parents=True)

        conreport_logs = container.exec_run(
            f'su -c "/.wine/drive_c/proc/{work_dir.name}/sh/conreport.sh" abc',
            demux=True,
            environment={"TMPDIR_R2R": work_dir.name},
        )
        stdout, stderr = conreport_logs.output

        if stdout is not None:
            logger.info(stdout.decode())
        if stderr is not None:
            logger.debug(stderr.decode())
            if b"ReadConFile - failed to read" in stderr:
                logger.critical(
                    "SBE ConReport.exe could not convert the xmlcon to a text report"
                )
                raise InvalidXMLCONError("Could not read XMLCON using seabird")

        out_path = outdir / infile.with_suffix(".txt").name

        conreport = string_loader(out_path, "conreport").conreport

        return conreport


sbebatch_sh = r"""export DISPLAY=:1
export HODLL=libwow64fex.dll
export WINEPREFIX=/.wine

# if a previous run fails, some state is recorded that prevents a clean start again (via UI popup) , so we just remove that
rm -rf /.wine/drive_c/users/abc/AppData/Local/Sea-Bird/
cd /.wine/drive_c/proc/${TMPDIR_R2R}/in;
wine "/.wine/drive_c/Program Files (x86)/Sea-Bird/SBEDataProcessing-Win32/SBEBatch.exe" batch.txt ${R2R_HEXNAME} ../out ${R2R_XMLCON} ../out/${R2R_TMPCNV} -s
exit 0;
"""


def run_sbebatch(
    hex: NamedFile,
    xmlcon: NamedFile,
    datcnv: NamedFile,
    derive: NamedFile,
    binavg: NamedFile,
):
    container = get_container()

    logger.info(f"Running in container {container.name}")
    logger.info(f"{hex.name} - Converting to cnv")
    if len(hex) > 2**23:  # 8MiB
        logger.warning(f"{hex.name} is large, this might take a while")

    with TemporaryDirectory(dir=_tmpdir.name) as condir:
        work_dir = Path(condir)
        sh = work_dir / "sh" / "sbebatch.sh"
        if sh.exists():
            sh.unlink()
        sh.parent.mkdir(exist_ok=True, parents=True)
        sh.write_text(sbebatch_sh)
        sh.chmod(0o555)

        indir = work_dir / "in"
        indir.mkdir(exist_ok=True, parents=True)

        batch_file = indir / "batch.txt"
        batch_file.write_text(batch)

        for file in (hex, xmlcon, datcnv, derive, binavg):
            infile = indir / file.name
            infile.write_bytes(file)

        hex_path = Path(hex.name)

        outdir = work_dir / "out"
        outdir.mkdir(exist_ok=True, parents=True)

        batch_logs = container.exec_run(
            f'su -c "/.wine/drive_c/proc/{work_dir.name}/sh/sbebatch.sh" abc',
            demux=True,
            environment={
                "TMPDIR_R2R": work_dir.name,
                "R2R_HEXNAME": hex.name,
                "R2R_XMLCON": xmlcon.name,
                "R2R_TMPCNV": hex_path.with_suffix(".cnv"),
            },
        )
        stdout, stderr = batch_logs.output
        if stderr is not None:
            logger.debug(stderr.decode())
        if stdout is not None:
            logger.info(stdout.decode())

        cnv_24hz = outdir / f"{hex_path.stem}_24hz.cnv"
        cnv_1db = outdir / f"{hex_path.stem}_1db.cnv"

        cnv_24hz = string_loader(cnv_24hz, "cnv_24hz").cnv_24hz
        cnv_1db = string_loader(cnv_1db, "cnv_1db").cnv_1db
        return {"cnv_24hz": cnv_24hz, "cnv_1db": cnv_1db}
