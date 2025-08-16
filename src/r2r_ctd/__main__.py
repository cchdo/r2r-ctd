"""The main entry point for this software, specifically the :py:func:`qa` function.

Inside the that qa func, the basic architecture is, for each ``path`` in ``paths``:

* Construct a :py:class:`~r2r_ctd.breakout.Breakout` instance passing ``path`` as the sole argument.
* Construct a :py:class:`~r2r_ctd.reporting.ResultAggregator` from that breakout instance.
* Write the geoCSV, the :py:class:`~r2r_ctd.breakout.Breakout` instance knows where, the :py:class:`~r2r_ctd.reporting.ResultAggregator` knows the contents.
* For each station in :py:class:`~r2r_ctd.breakout.Breakout.stations_hex_paths`, generate and write the instrument configuration report, requires the companion docker container.
* Optionally and by default: for each station in :py:class:`~r2r_ctd.breakout.Breakout.stations_hex_paths`, generate and write the two cnv products, requires the companion docker container.
* Finally, write the xml QA report.


The majority of the work of the QA is being done by the :py:class:`~r2r_ctd.reporting.ResultAggregator`.
"""

import logging
from pathlib import Path

import click
from rich.logging import RichHandler

from r2r_ctd.breakout import Breakout
from r2r_ctd.docker_ctl import test_docker as _test_docker
from r2r_ctd.maps import make_maps
from r2r_ctd.reporting import (
    ResultAggregator,
    write_xml_qa_report,
)
from r2r_ctd.state import (
    get_geoCSV_path,
)


@click.group()
@click.version_option()
@click.option("-q", "--quiet", count=True)
def cli(quiet):
    FORMAT = "%(message)s"
    logging.basicConfig(
        level=(quiet + 1) * 10,
        format=FORMAT,
        datefmt="[%X]",
        handlers=[RichHandler()],
    )


@cli.command()
def test_docker():
    "Run the docker 'hello-world' container and exit"
    _test_docker()


@cli.command()
@click.argument(
    "paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, writable=True, path_type=Path),
)
@click.option("--gen-cnvs/--no-gen-cnvs", default=True)
def qa(gen_cnvs: bool, paths: tuple[Path, ...]):
    """Run the QA routines on one or more directories."""
    for path in paths:
        breakout = Breakout(path=path)
        ra = ResultAggregator(breakout)

        # write geoCSV
        get_geoCSV_path(breakout).write_text(ra.gen_geoCSV())

        # write the SBE Configuration Reports
        for station in breakout:
            station.r2r.write_con_report(breakout)

        write_xml_qa_report(breakout, ra.certificate)
        make_maps(ra)

        # write the cnv files if asked
        if gen_cnvs:
            for station in breakout:
                station.r2r.write_cnv(breakout, "cnv_24hz")
                station.r2r.write_cnv(breakout, "cnv_1db")


if __name__ == "__main__":
    cli()
