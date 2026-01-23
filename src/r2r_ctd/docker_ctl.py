"""Utilities for interacting with and managing the lifecycle of the companion container.

Basic architecture is as follows:

* A single container will exist for the lifetime of this python process, it will not be launched unless needed.
* A single temporary directory will be mapped into that container, which will be cleaned up when the python process exits.
* The functions that run things, will create their own temporary directory inside that will be cleaned up when these functions return (or throw).
* The functions work by creating a small shell script inside their temporary directory and calling that.
* As a convention, the shell script is placed inside an ``sh`` directory, the input files in an ``in`` directory, and container output files placed in an ``out`` directory
* The container will be killed when python exist.
* If the wine debugger is entered, the container is restarted and the routine is tried again.

Temporary directory structure::

  tmp_container  <-- gets bound to the container when first launched
  └── tmp_func <-- created inside the above temporary dir when each function is called
      ├── in <-- has input files (xmlcon, hex, etc..)
      ├── out <-- gets output files written (or moved)
      └── sh <-- shell scripts that run the SBE Software

The above architecture is largely due to many lessons learned during development:

The container stays running due to a very large startup cost.
    Earlier versions of this software launched/removed the container with each function call.
    However, when monitoring resource usage, there was significant hard disk activity (GBs being read/written at launch).
    This was fixed/mitigated somewhat by improvements to the container image itself, but by the time those improvements were made, this had already switched to using a single container architecture.
    Even with the improved container, it was still faster and less hard on my hard drive when a single container was used.

The nested temporary directories are due to two requirements.
    When the container is launched, we need to bind some directory as a volume mount to get data in/out of the container.
    This directory needs to exist when the container is launched, and exist for the lifetime of the container.
    Each function needs to add it own files for processing, temporary directories are used here so that they are cleaned up when the function exits.
    This avoids functions conflicting with each other and for this software to try to clean up individual files itself.

Shell scripts are mapped in rather than baked in.
    To keep the container itself portable and not need rebuilds constantly, it's easier to add the shell scripts at runtime rather than at image build time.
    This also increases the utility of that container image outside of this QA content.
"""

import atexit
import time
from collections.abc import Mapping
from functools import wraps
from logging import getLogger
from os import environ
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import docker
from docker.models.containers import Container
from odf.sbe.io import string_loader

from r2r_ctd.exceptions import (
    InvalidXMLCONError,
    WineDebuggerEnteredError,
    WineTimeoutError,
)
from r2r_ctd.sbe import batch
from r2r_ctd.state import NamedBytes

DEFAULT_SBEDP_IMAGE = "ghcr.io/cchdo/sbedp:v2026.01.0"
SBEDP_IMAGE = environ.get("R2R_CTD_SBEDP_IMAGE", DEFAULT_SBEDP_IMAGE)

"""The current image that will be downloaded/used for the processing"""

logger = getLogger(__name__)

_tmpdir = TemporaryDirectory()  # singleton tempdir for IO with docker container


def container_ready(container, timeout=5):
    """Checks the health status of the ``container``, blocks and waits for the healthy state or ``timeout`` seconds."""
    sleep = 0.5
    tries = timeout / sleep
    while tries:
        container.reload()
        if container.health == "healthy":
            return True
        time.sleep(sleep)
        tries -= 1
    return False


def test_docker():
    """Download and run the ``hello-world`` container, used as a check that this software is talking to the container runtime"""
    client = docker.from_env()
    logger.info(
        client.containers.run(
            "hello-world",
            remove=True,
        ).decode()
    )


class ContainerGetter:
    """Wrapper class that manages the single container instance.

    .. warning::
        Do not use this class yourself, use the instance already made at :py:obj:`get_container`

    Calling an instance of this class will return the container for this python processes, the container will be launched if not already running.
    """

    container: Container | None = None

    def __call__(self) -> Container:
        """Get the container instance for this python process

        If the container is already running, return a reference to it.
        If the container is not already running, launch it, wait for it to be ready, then return a reference to it.

        Launching the container will also register a kill function that will kill the container at python exit.
        """
        if self.container is not None:
            return self.container
        logger.debug("Launching container for running SBE software")
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
        logger.debug(
            f"Container launched as {self.container.name} with labels: {labels}"
        )

        def _kill_container():
            if self.container is None:
                return
            logger.debug(f"attempting to kill wine container: {self.container.name}")
            self.container.kill()

        atexit.register(_kill_container)

        if container_ready(self.container):
            return self.container
        else:
            raise Exception("Could not start container after 5 seconds")


get_container = ContainerGetter()
"""Pre initialized container getter, there must only be one per python process"""

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
"""The shell script for running ConReport.exe

An earlier versions of this tried to prepare all the xmlcon files and process them all at once.
First using the built into ConReport.exe globbing, then using a loop that still exists.
When the :py:func:`run_con_report` function was switch to just one at a time, this loop based script continued to work fine so was not modified."""


def run_con_report(xmlcon: NamedBytes):
    """Run ConReport.exe on the xmlcon file ``xmlcon``

    See the module level overview for how/why this function works the way it does.
    """
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
                    logger.error(
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
timeout ${R2R_TIMEOUT} wine "/.wine/drive_c/Program Files (x86)/Sea-Bird/SBEDataProcessing-Win32/SBEBatch.exe" batch.txt "${R2R_HEXNAME}" ../out "${R2R_XMLCON}" "../out/${R2R_TMPCNV}" -s
# if the above process times out, print something to standard error we can check for
[ $? -eq 124 ] && echo "SBEBatch.exe TIMEOUT" 1>&2 && exit 1;
exit 0;
"""
"""Shell script that runs SBEBatch.exe

Mostly works the same as you might run manually, however it will remove the Sea-Bird state directory from the wine users home directory.
If a previous batch conversion didn't go well or was interrupted, SBEBatch would ask via a GUI popup if you want to continue where it left off.
Since this was in the form of a gui pop up, it would just block waiting for user interaction.
"""


def attempts(tires=3):
    """Decorator that looks for the WineDebuggerEntered exception and restarts the container and tries the function again."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            container = get_container()
            attempt = 1
            while attempt <= tires:
                try:
                    return func(*args, **kwargs)
                except (WineTimeoutError, WineDebuggerEnteredError) as err:
                    logger.critical(f"The wine process as encountered a problem: {err}")
                    attempt += 1
                    if attempt > tires:
                        raise RuntimeError("Max retries exceed") from err
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


@attempts(5)
def run_sbebatch(
    hex: NamedBytes,
    xmlcon: NamedBytes,
    datcnv: NamedBytes,
    derive: NamedBytes,
    binavg: NamedBytes,
):
    """Run SBEBatch.exe on the input files.

    ``hex`` and ``xmlcon`` are from the cruise breakout.
    ``datcnv``, ``derive`` and ``binavg`` are the configuration files for each step that this particular station is processed with.

    See :py:mod:`r2r_ctd.sbe` for some more details on these configuration files."""
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
                "R2R_TIMEOUT": 300,  # seconds
            },
        )
        for stdout, stderr in batch_logs.output:
            if stderr is not None:
                msg = stderr.decode().strip()
                logger.debug(f"{container.name} - {msg}")
                if "starting debugger" in msg:
                    raise WineDebuggerEnteredError("wine has entered debugger")
                if "SBEBatch.exe TIMEOUT" in msg:
                    raise WineTimeoutError(
                        "SBEBatch.exe did not finish in the amount of time allowed"
                    )
            if stdout is not None:
                logger.info(f"{container.name} - {stdout.decode().strip()}")

        cnv_24hz = outdir / f"{hex_path.stem}.cnv"
        cnv_1db = outdir / f"{hex_path.stem}_1db.cnv"

        cnv_24hz = string_loader(cnv_24hz, "cnv_24hz").cnv_24hz
        cnv_1db = string_loader(cnv_1db, "cnv_1db").cnv_1db

        cnv_24hz_rename = outdir / f"{hex_path.stem}_24hz.cnv"
        cnv_24hz.attrs["filename"] = cnv_24hz_rename.name
        return {"cnv_24hz": cnv_24hz, "cnv_1db": cnv_1db}
