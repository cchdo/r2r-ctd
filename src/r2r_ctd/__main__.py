from pathlib import Path
import logging

from rich.logging import RichHandler

from r2r_ctd.breakout import Breakout
from r2r_ctd.state import (
    initialize_or_get_state,
    get_or_write_check,
    get_or_write_derived_file,
)
from r2r_ctd.checks import check_three_files
from r2r_ctd.derived import make_conreport

import click


@click.command()
@click.argument(
    "paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, writable=True, path_type=Path),
)
def main(paths: tuple[Path, ...]):
    FORMAT = "%(message)s"
    logging.basicConfig(
        level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
    )
    for path in paths:
        breakout = Breakout(path=path)

        qa_path = breakout.qa_template_xml

        for station in breakout.stations_hex_paths:
            data = initialize_or_get_state(breakout, station)
            get_or_write_check(data, "three_files", check_three_files)
            get_or_write_derived_file(data, "conreport", make_conreport)


if __name__ == "__main__":
    main()
