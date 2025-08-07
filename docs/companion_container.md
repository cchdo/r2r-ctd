# Companion Container Interaction
The companion container is responsible for running all the seabird software.
It does this by using [wine](https://www.winehq.org/), this container is doing other magic to allow a 32-bit x86 windows program run on 64-bit arm machines.
The specifics of this can help you understand the log message being printed to the console.

The companion container is not launched until it needs to have something run inside of it.
One is it launched, it will remain running and ready to receive work until the controlling python process exits.
Caching of the results means that the container might noy be launched at all if all the derivative files have been made already.
The two output this container makes are:
* A "human readable" configuration report from the .xmlcon files (ConReport.exe)
* cnv files, which are table like text data files converted from the raw inputs (SBEBatch.exe which calls some other programs)
The configuration report is required for the QA routines to finish, but is a fully CLI program that seems to be very robust in the container environment.
The cnv files are not required for the QA to finish and their generation can be suppressed.
Specifics for how the programs are run and how data get in and out of the container are in the [](#r2r_ctd.docker_ctl) section of the API documentation.

As stated above the ConReport.exe program seems to be robust in the container environment.
In testing during development it would either finish or report an error to the console.
It is also a console program and does not try to display any sort of GUI and will continue to work even if the virtual framebuffer isn't running or the DISPLAY envar is not set correctly.

The programs that make the cnv files are not so well behaved.
They need to open a window (GUI), progress isn't printed to the console, and can be a little buggy even natively on windows.
To see the progress, or more critically, see if there is anything going wrong with the conversions, the container needs to be connected to in a vnc session.

## Finding the Running Container
When the container is launched, it will be assigned a random name in the form of `<adjective>_<noun>` from an internal list of both[^hahaha].
This name will be printed several times in the log outputs, when it is first launched, and as a prefix in the captured stdout and stderr streams from the running container.
The container launch log message will look like:
```console
DEBUG    Container launched as busy_mclean with labels: ['us.rvdata.ctd-proc']
```
The label `us.rvdata.ctd-proc` will be consistent across all running containers and can be used as a [filter](https://docs.docker.com/engine/cli/filter/).
As the container is running, messages to stdout are echoed as INFO level log messages in the console.
For example, this is the output of a successful execution of ConReport.exe, though it's in a sea of debug messages emanating from wine:
```console
INFO     busy_mclean - C:\proc\tmpgkehfkyf\out\GF418C11.txt
INFO     busy_mclean - 1 report written to C:\proc\tmpgkehfkyf\out
```

[^hahaha]: In development, I actually laughed out loud when one of my running containers got named `pedantic_torvalds`.

Another bit of information is needed to actually connect to the container, the port which the container is bound to.
To find that run `docker ps` in a different terminal session on the same machine (this is wide, scroll to the right to see the whole output):
```console
CONTAINER ID   IMAGE                            COMMAND   CREATED          STATUS                   PORTS                                 NAMES
91752b5dc22c   ghcr.io/cchdo/sbedp:v2025.07.1   "/init"   10 seconds ago   Up 9 seconds (healthy)   3001/tcp, 127.0.0.1:32779->3000/tcp   busy_mclean
```
If there are a lot of containers listed, you can use the `--filter` switch to limit which containers are printed:
```
docker ps --filter "label=us.rvdata.ctd-proc"
```
Here is what it might look like if multiple containers are running in parallel:
```console
CONTAINER ID   IMAGE                            COMMAND   CREATED         STATUS                   PORTS                                 NAMES
91752b5dc22c   ghcr.io/cchdo/sbedp:v2025.07.1   "/init"   10 seconds ago  Up 9 seconds (healthy)   3001/tcp, 127.0.0.1:32779->3000/tcp   busy_mclean
d685a329538f   ghcr.io/cchdo/sbedp:v2025.07.1   "/init"   8 seconds ago   Up 7 seconds (healthy)   3001/tcp, 127.0.0.1:32792->3000/tcp   trusting_swirles
f9c90038e2cc   ghcr.io/cchdo/sbedp:v2025.07.1   "/init"   8 seconds ago   Up 7 seconds (healthy)   3001/tcp, 127.0.0.1:32791->3000/tcp   confident_johnson
463934b98584   ghcr.io/cchdo/sbedp:v2025.07.1   "/init"   8 seconds ago   Up 8 seconds (healthy)   3001/tcp, 127.0.0.1:32790->3000/tcp   busy_hamilton
aca42bf41dad   ghcr.io/cchdo/sbedp:v2025.07.1   "/init"   8 seconds ago   Up 8 seconds (healthy)   3001/tcp, 127.0.0.1:32789->3000/tcp   quirky_darwin
0cae07fdc22f   ghcr.io/cchdo/sbedp:v2025.07.1   "/init"   8 seconds ago   Up 8 seconds (healthy)   3001/tcp, 127.0.0.1:32786->3000/tcp   gallant_torvalds
26fe934ef656   ghcr.io/cchdo/sbedp:v2025.07.1   "/init"   8 seconds ago   Up 8 seconds (healthy)   3001/tcp, 127.0.0.1:32787->3000/tcp   naughty_kapitsa
186aea37a48a   ghcr.io/cchdo/sbedp:v2025.07.1   "/init"   8 seconds ago   Up 8 seconds (healthy)   3001/tcp, 127.0.0.1:32788->3000/tcp   quirky_davinci
```

## Connecting to the Running Container
We will be using the first example (busy_mclean) in the above tables.

In the above list of containers, we need the information listed under the PORTS column label.
This shows what port the container has bound to on the host.
In the above case it is: `127.0.0.1:32779` which is mapped to port 3000 inside the container.
The `127.0.0.1` bind address is used to avoid exposing this port beyond the docker host.
The port `32779` will be assigned by docker and will not be the same each time.
Each running container instance will be mapped to a different port.

In a web browser, navigate to `http://127.0.0.1:32779` (use the actual port of your running container) and you should see a big white terminal session.
If the cnv processing has started, you should see windows with progress bars.

::::{danger}
Interaction with the GUI windows can cause the program to never exit.
If the programs do not exit, the controlling python process will not know that data processing as finished and continue.

This interaction is not necessarily cursor based.
For example, I had the VNC client open and went to tab away from the browser to the process running in a terminal.
However, the first press of the {kbd}`command` key as part of a {kbd}`command` + {kbd}`tab` was sent to the VNC client.
This resulted in the File menu of the running program being selected (but not opened).
Since the program was waiting for my interaction, it never closed, see the following screenshot.
Clicking off the window and on to the big white terminal behind allowed the processing to continue.

:::{figure} figures/inadvertent_interaction.png
:alt: Screenshot of the Derive.exe showing that the File menu has been interacted with

Screenshot of Derive.exe that has completed processing but the File menu has been selected but not opened, preventing the application from closing.
:::

::::