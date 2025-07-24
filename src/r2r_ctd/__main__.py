from pathlib import Path
import logging

from rich.logging import RichHandler

from r2r_ctd.breakout import Breakout
from r2r_ctd.reporting import ResultAggregator

import click

from r2r_ctd.state import get_xml_qa_path


@click.group()
def cli(): ...


@cli.command()
@click.argument(
    "paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, writable=True, path_type=Path),
)
def qa(paths: tuple[Path, ...]):
    """Run the QA routines on one or more directories"""
    FORMAT = "%(message)s"
    logging.basicConfig(
        level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
    )
    for path in paths:
        breakout = Breakout(path=path)

        qa_xml = breakout.qa_template_xml

        ra = ResultAggregator(breakout)
        ra.gen_geoCSV()
        certificate = ra.certificate
        ra.gen_cnvs()

        root = qa_xml.getroot()
        nsmap = root.nsmap
        prefix = "/r2r:qareport"
        cert = root.xpath(f"{prefix}/r2r:certificate", namespaces=nsmap)[0]
        root.replace(cert, certificate)
        with open(get_xml_qa_path(breakout), "wb") as f:
            qa_xml.write(
                f,
                pretty_print=True,
                xml_declaration=True,
                method="xml",
                encoding="UTF-8",
            )


if __name__ == "__main__":
    cli()
