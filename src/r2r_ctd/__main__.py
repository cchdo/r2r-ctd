from pathlib import Path
from tempfile import TemporaryDirectory

from odf.sbe import read_hex, accessors as _accessors

from r2r_ctd.docker_ctl import run_conreport
from r2r_ctd.breakout import Breakout

import click

@click.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, file_okay=False, writable=True, path_type=Path))
def main(paths:tuple[Path, ...]):
    for path in paths:
        breakout = Breakout(path=path)
        print(breakout.manifest_ok)

        for station in breakout.stations_hex_paths:
            a = read_hex(station)
            if "xmlcon" in a:
                with TemporaryDirectory() as tmpdir:
                    tmpdirp = Path(tmpdir)
                    xmlcon_path = tmpdirp / a.xmlcon.attrs["filename"]
                    print(xmlcon_path)
                    a.sbe.to_xmlcon(xmlcon_path)
                    print("run_docker")
                    conreport = run_conreport(path.absolute(), xmlcon_path)
                    a["conreport"] = conreport.conreport
                    print(a)

if __name__ == "__main__":
    main()