from pathlib import Path

import docker

client = docker.from_env()

conreport_sh = r"""export DISPLAY=:1
export HODLL=libwow64fex.dll

cd ~/.wine/drive_c/;
for file in tmp/*
do
  wine "Program Files (x86)/Sea-Bird/SBEDataProcessing-Win32/ConReport.exe" "${file}" "C:\proc\proc\config"
done
exit 0;
"""

def run_conreport(base_dir:Path, xmlcon:Path):
    sh = base_dir / "proc" / "sh" / "conreport.sh"
    if sh.exists():
        sh.unlink()
    sh.parent.mkdir(exist_ok=True, parents=True)
    sh.write_text(conreport_sh)
    sh.chmod(0o555)

    outdir = base_dir / "proc" / "config"
    outdir.mkdir(exist_ok=True, parents=True)

    xmlcon_path = (base_dir / xmlcon).absolute()
    print(xmlcon_path, xmlcon_path.exists())
    return client.containers.run("r2r/sbe", 'su -c "/config/.wine/drive_c/proc/proc/sh/conreport.sh" abc', remove=True, volumes={
    str(base_dir): {
        "bind": "/config/.wine/drive_c/proc", "mode":"rw"
    },
    str(xmlcon_path): {
        "bind": f"/config/.wine/drive_c/tmp/{xmlcon_path.name}", "mode":"ro"
    }
})