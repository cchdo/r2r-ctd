from pathlib import Path
from tempfile import TemporaryDirectory
import logging

from rich.logging import RichHandler

from r2r_ctd.docker_ctl import run_conreport
from r2r_ctd.breakout import Breakout
from r2r_ctd.state import initialize_or_get_state, get_or_write_check
from r2r_ctd.checks import check_three_files

import click

@click.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, file_okay=False, writable=True, path_type=Path))
def main(paths:tuple[Path, ...]):

    FORMAT = "%(message)s"
    logging.basicConfig(
        level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
    )
    for path in paths:
        breakout = Breakout(path=path)

        for station in breakout.stations_hex_paths:
            data = initialize_or_get_state(breakout, station)
            get_or_write_check(data, "three_files", check_three_files)

            #if "xmlcon" in a:
            #    with TemporaryDirectory() as tmpdir:
            #        tmpdirp = Path(tmpdir)
            #        xmlcon_path = tmpdirp / a.xmlcon.attrs["filename"]
            #        a.sbe.to_xmlcon(xmlcon_path)
            #        conreport = run_conreport(path.absolute(), xmlcon_path)
            #        a["conreport"] = conreport.conreport

if __name__ == "__main__":
    main()