# Installing

## Package Installation

This package is published on pypi, so you can install it in your environment of choice using pip or pip compatible tool:

> pip install r2r-ctd

For actual usage it is probably more convenient to use a tool runner such as uvx:

> uvx r2r-ctd

:::{note}
Using a tool runner, specifically `uvx`, is the preferred method and will be the way commands are show in the rest of this document.

Uv is an excellent tool that, at the time of writing, is basically taking over the python package related tool ecosystems
If you aren't already using it consider switching to it.

Uv can installed via [homebrew][homebrew_url] (on a mac) or by following the [installation instructions](https://docs.astral.sh/uv/#installation) in the uv documentation (all OSes).
:::

## Runtime Requirements

### Docker

This package has runtime requirements that make it a little more tricky than a pure python software stack.
Specifically we need to interact with a [companion docker image](https://github.com/cchdo/sbedp) that has the actual seabird data processing software in it.
Make sure you have docker (or compatible container runtime) installed on your system[^1].
Also ensure that docker itself is running after installation and whenever you are using `r2r-ctd`.
[^1]: This author prefers to install everything, including GUI apps, on their computer using [homebrew][homebrew_url] so a `brew install docker-desktop` should get you what you need.

The image will be pulled automatically on first use of the `qa` subcommand when it encounters something that needs processing in the image, but it is a bit large and download progress will not be shown.
The image can be pulled in advance:

> docker pull {{SBEDP_IMAGE}}

:::{warning}
The docker image is for arm64 only.

While it has only been tested on M-family (M1,M2,etc..) arm based Apple hardware, the build process in github uses linux based arm runner, so presumably it will work on arm based linux machines as long as they can run docker.
:::

Interacting with this companion image is done via the [Docker SDK](https://docker-py.readthedocs.io/en/stable/index.html).
This requires that the docker unix socket be reachable.
You can test that `r2r-ctd` can talk to docker by running the following:

> uvx r2r-ctd test-docker

This will download the docker hello-world and run it.
If all is well, you'll see a bunch of debug level logs being printed to your console followed by the "Hello from Docker!" paragraph.
If things are not well, an exception will be thrown, in testing a rather cryptic "FileNotFoundError" would be one of the last lines of the traceback.
Things to check:
1. Docker is running?

    Try a `docker ps` in the terminal, it should print out a table of running containers, or just the table column labels if no containers are running
2. Is the `docker.sock` file in the default location?

   This default location is `/var/run/docker.sock` but on a mac this requires admin permissions to use/make.
   See the "Allow the default Docker socket" section of the [advanced tab](https://docs.docker.com/desktop/settings-and-maintenance/settings/#advanced-1) of the docker desktop settings.
3. If the `docker.sock` is not in its default location, is the `DOCKER_HOST` envar set?

   On a mac try setting this to `unix:///Users/<user>/.docker/run/docker.sock`, be sure to replace `<user>` with your actual home directory name. 

### Host
As such, at this time the python part of `r2r-ctd` needs to be running on the docker host system and not in a container itself or a remote machine.
`r2r-ctd` does some volume mounts to get data in/out of the running containers and this basically requires the two to be on the same system.

It is probably possible to do some docker-in-docker techniques such that both the python parts and seabird parts can be in containers but they haven't been tried.
Similarly there are ways to do network volumes with docker.
Both docker in docker and remote volumes have caveats, edge cases, and complexities that are not worth the trade off at this point.


[homebrew_url]: https://brew.sh/