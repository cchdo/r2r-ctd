from pathlib import Path

from r2r_ctd.docker_ctl import run_conreport

import click

@click.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, file_okay=False, writable=True, path_type=Path))
def main(paths:tuple[Path, ...]):
    click.echo("processing xmlcon")
    for line in (paths[0] / "manifest-md5.txt").read_text().splitlines():
        md5hash, path = line.split(" ", maxsplit=1)
        if path.lower().endswith("xmlcon"):
            click.echo(f"processing: {path}")
            print(run_conreport(paths[0].absolute(), Path(path.strip())))

if __name__ == "__main__":
    main()