import logging
from pathlib import Path

import click
from rich.logging import RichHandler

from r2r_ctd.breakout import Breakout
from r2r_ctd.reporting import ResultAggregator, get_new_references, get_update_record
from r2r_ctd.state import (
    get_geoCSV_path,
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

        root = qa_xml.getroot()
        cert = root.xpath(
            "/r2r:qareport/r2r:certificate", namespaces=breakout.namespaces
        )[0]
        updates = root.xpath(
            "/r2r:qareport/r2r:provenance/r2r:updates",
            namespaces=breakout.namespaces,
        )[0]
        updates.append(get_update_record())
        references = root.xpath(
            "/r2r:qareport/r2r:references", namespaces=breakout.namespaces
        )[0]

        new_refs = get_new_references(breakout)
        references.extend(new_refs)
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
