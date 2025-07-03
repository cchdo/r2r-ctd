from pathlib import Path
from logging import getLogger

from odf.sbe.io import string_loader

import docker


logger = getLogger(__name__)

client = docker.from_env()

conreport_sh = r"""export DISPLAY=:1
export HODLL=libwow64fex.dll
export WINEPREFIX=/.wine

cd /.wine/drive_c/;
for file in tmp/*
do
  wine "Program Files (x86)/Sea-Bird/SBEDataProcessing-Win32/ConReport.exe" "${file}" "C:\proc\proc"
done
exit 0;
"""


def run_conreport(base_dir: Path, xmlcon: Path):
    sh = base_dir / "conreport.sh"
    if sh.exists():
        sh.unlink()
    sh.parent.mkdir(exist_ok=True, parents=True)
    sh.write_text(conreport_sh)
    sh.chmod(0o555)

    outdir = base_dir / "proc"
    outdir.mkdir(exist_ok=True, parents=True)

    xmlcon_path = xmlcon.absolute()
    conreport_logs = client.containers.run(
        "r2r/sbe",
        'su -c "/.wine/drive_c/proc/conreport.sh" abc',
        auto_remove=True,
        volumes={
            str(base_dir): {"bind": "/.wine/drive_c/proc", "mode": "rw"},
            str(xmlcon_path): {
                "bind": f"/.wine/drive_c/tmp/{xmlcon_path.name}",
                "mode": "ro",
            },
        },
    )
    logger.debug(conreport_logs)
    out_path = outdir / xmlcon_path.with_suffix(".txt").name
    return string_loader(out_path, "conreport").conreport
