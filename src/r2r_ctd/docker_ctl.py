import atexit
import time
from collections.abc import Mapping
from functools import wraps
from logging import getLogger
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import docker
from docker.models.containers import Container
from odf.sbe.io import string_loader

from r2r_ctd.exceptions import InvalidXMLCONError, WineDebuggerEnteredError
from r2r_ctd.sbe import batch
from r2r_ctd.state import NamedFile

SBEDP_IMAGE = "ghcr.io/cchdo/sbedp:v2025.07.1"

logger = getLogger(__name__)

_tmpdir = TemporaryDirectory()  # singleton tempdir for IO with docker container


def container_ready(container, timeout=5):
    sleep = 0.5
    tries = timeout / sleep
    while tries:
        container.reload()
        if container.health == "healthy":
            return True
        time.sleep(sleep)
        tries -= 1
    return False


class ContainerGetter:
    container: Container | None = None

    def __call__(self) -> Container:
        if self.container is not None:
            return self.container
        logger.info("Launching container for running SBE software")
        client = docker.from_env()
        labels = ["us.rvdata.ctd-proc"]
        self.container = client.containers.run(
            SBEDP_IMAGE,
            auto_remove=True,
            detach=True,
            volumes={str(_tmpdir.name): {"bind": "/.wine/drive_c/proc", "mode": "rw"}},
            labels=labels,
            # The following binds an ephemeral port to 127.0.0.1 and not 0.0.0.0
            # we are doing this for security reasons
            # looks like the python typeshed is not correct here so I am casting to
            # something it knows about
            ports=cast("Mapping[str, None]", {"3000/tcp": ("127.0.0.1",)}),
        )
        logger.info(
            f"Container launched as {self.container.name} with labels: {labels}"
        )

        def _kill_container():
            if self.container is None:
                return
            logger.info(f"attempting to kill wine container: {self.container.name}")
            self.container.kill()

        atexit.register(_kill_container)

        if container_ready(self.container):
            return self.container
        else:
            raise Exception("Could not start container after 5 seconds")


get_container = ContainerGetter()

con_report_sh = r"""export DISPLAY=:1
export HODLL=libwow64fex.dll
export WINEPREFIX=/.wine

cd /.wine/drive_c/;
for file in proc/$TMPDIR_R2R/in/*
do
  wine "Program Files (x86)/Sea-Bird/SBEDataProcessing-Win32/ConReport.exe" "${file}" "C:\proc\\${TMPDIR_R2R}\out"
done
exit 0;
"""


def run_con_report(xmlcon: NamedFile):
    container = get_container()

    logger.info(f"Running in container {container.name}")
    logger.info(f"{xmlcon.name} - Running ConReport.exe")

    with TemporaryDirectory(dir=_tmpdir.name) as condir:
        work_dir = Path(condir)
        sh = work_dir / "sh" / "con_report.sh"
        if sh.exists():
            sh.unlink()
        sh.parent.mkdir(exist_ok=True, parents=True)
        sh.write_text(con_report_sh)
        sh.chmod(0o555)

        indir = work_dir / "in"
        indir.mkdir(exist_ok=True, parents=True)

        infile = indir / xmlcon.name
        infile.write_bytes(xmlcon)

        outdir = work_dir / "out"
        outdir.mkdir(exist_ok=True, parents=True)

        con_report_logs = container.exec_run(
            f'su -c "/.wine/drive_c/proc/{work_dir.name}/sh/con_report.sh" abc',
            demux=True,
            stream=True,
            environment={"TMPDIR_R2R": work_dir.name},
        )
        for stdout, stderr in con_report_logs.output:
            if stdout is not None:
                logger.info(f"{container.name} - {stdout.decode().strip()}")
            if stderr is not None:
                logger.debug(f"{container.name} - {stderr.decode().strip()}")
                if b"ReadConFile - failed to read" in stderr:
                    logger.critical(
                        "SBE ConReport.exe could not convert the xmlcon to a text report",
                    )
                    raise InvalidXMLCONError("Could not read XMLCON using seabird")

        out_path = outdir / infile.with_suffix(".txt").name

        con_report = string_loader(out_path, "con_report").con_report

        return con_report


sbebatch_sh = r"""export DISPLAY=:1
export HODLL=libwow64fex.dll
export WINEPREFIX=/.wine

# if a previous run fails, some state is recorded that prevents a clean start again (via UI popup) , so we just remove that
rm -rf /.wine/drive_c/users/abc/AppData/Local/Sea-Bird/
cd /.wine/drive_c/proc/${TMPDIR_R2R}/in;
wine "/.wine/drive_c/Program Files (x86)/Sea-Bird/SBEDataProcessing-Win32/SBEBatch.exe" batch.txt ${R2R_HEXNAME} ../out ${R2R_XMLCON} ../out/${R2R_TMPCNV} -s
exit 0;
"""


def attempts(tires=3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            container = get_container()
            attempt = 1
            while attempt <= tires:
                try:
                    return func(*args, **kwargs)
                except WineDebuggerEnteredError as err:
                    logger.critical(
                        "Wine appears to have entered the debugger, retrying"
                    )
                    attempt += 1
                    logger.critical(f"Attempt {attempt} of {tires}")
                    logger.critical(f"Restarting {container.name}")
                    container.restart()
                    logger.critical(f"Waiting for {container.name} to be ready")
                    if not container_ready(container):
                        raise Exception(
                            "Could not restart container after 5 seconds"
                        ) from err

        return wrapper

    return decorator


@attempts(3)
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
            stream=True,
            environment={
                "TMPDIR_R2R": work_dir.name,
                "R2R_HEXNAME": hex.name,
                "R2R_XMLCON": xmlcon.name,
                "R2R_TMPCNV": hex_path.with_suffix(".cnv"),
            },
        )
        for stdout, stderr in batch_logs.output:
            if stderr is not None:
                msg = stderr.decode().strip()
                logger.debug(f"{container.name} - {msg}")
                if "starting debugger" in msg:
                    raise WineDebuggerEnteredError("wine crashed?")
            if stdout is not None:
                logger.info(f"{container.name} - {stdout.decode().strip()}")

        cnv_24hz = outdir / f"{hex_path.stem}.cnv"
        cnv_1db = outdir / f"{hex_path.stem}_1db.cnv"

        cnv_24hz = string_loader(cnv_24hz, "cnv_24hz").cnv_24hz
        cnv_1db = string_loader(cnv_1db, "cnv_1db").cnv_1db

        cnv_24hz_rename = outdir / f"{hex_path.stem}_24hz.cnv"
        cnv_24hz.attrs["filename"] = cnv_24hz_rename.name
        return {"cnv_24hz": cnv_24hz, "cnv_1db": cnv_1db}
