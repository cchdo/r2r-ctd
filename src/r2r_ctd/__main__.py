import logging
from pathlib import Path
from typing import cast

import click
from rich.logging import RichHandler

from r2r_ctd.breakout import Breakout
from r2r_ctd.reporting import ResultAggregator
from r2r_ctd.state import (
    get_config_path,
    get_geoCSV_path,
    get_product_path,
    get_xml_qa_path,
)


@click.group()
@click.version_option()
def cli(): ...


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
    FORMAT = "%(message)s"
    logging.basicConfig(
        level="NOTSET",
        format=FORMAT,
        datefmt="[%X]",
        handlers=[RichHandler()],
    )
    for path in paths:
        breakout = Breakout(path=path)

        qa_xml = breakout.qa_template_xml

        ra = ResultAggregator(breakout)
        certificate = ra.certificate

        if gen_cnvs:
            ra.gen_cnvs()

        # write geoCSV
        get_geoCSV_path(breakout).write_text(ra.gen_geoCSV())

        for station in breakout:
            if "conreport" not in station:
                continue

            path = get_config_path(breakout) / cast(
                "str",
                station.conreport.attrs["filename"],
            )
            path.write_text(station.conreport.item())

        for station in breakout:
            if "cnv_24hz" in station:
                path = get_product_path(breakout) / cast(
                    "str",
                    station.cnv_24hz.attrs["filename"],
                )
                path.write_text(station.cnv_24hz.item())
            if "cnv_1db" in station:
                path = get_product_path(breakout) / cast(
                    "str",
                    station.cnv_1db.attrs["filename"],
                )
                path.write_text(station.cnv_1db.item())

        root = qa_xml.getroot()
        nsmap = root.nsmap
        cert = root.xpath("/r2r:qareport/r2r:certificate", namespaces=nsmap)[0]
        updates = root.xpath(
            "/r2r:qareport/r2r:provenance/r2r:updates",
            namespaces=nsmap,
        )[0]
        references = root.xpath("/r2r:qareport/r2r:references", namespaces=nsmap)[0]
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
