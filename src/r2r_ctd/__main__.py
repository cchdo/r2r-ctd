import logging
from pathlib import Path

import click
from rich.logging import RichHandler

from r2r_ctd.breakout import Breakout
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
@click.argument(
    "paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, writable=True, path_type=Path),
)
@click.option("--gen-cnvs/--no-gen-cnvs", default=True)
def qa(gen_cnvs: bool, paths: tuple[Path, ...]):
    """Run the QA routines on one or more directories"""
    for path in paths:
        breakout = Breakout(path=path)
        ra = ResultAggregator(breakout)

        # write geoCSV
        get_geoCSV_path(breakout).write_text(ra.gen_geoCSV())

        # write the SBE Configuration Reports
        for station in breakout:
            station.r2r.write_con_report(breakout)

        # write the cnv files
        if gen_cnvs:
            for station in breakout:
                station.r2r.write_cnv(breakout, "cnv_24hz")
                station.r2r.write_cnv(breakout, "cnv_1db")

        write_xml_qa_report(breakout, ra.certificate)


if __name__ == "__main__":
    cli()
