# r2r.ctd documentation

:::{toctree}
:maxdepth: 2
:caption: Contents:

installing
R2R_CTD_QualityAssessment_Description
:::

Outline of what to write:

* Running
    * The qa command
    * What is a breakout expected to look like
    * How many can be run in parallel (however many p-cores you have, see `system_profiler SPHardwareDataType`)
* SBE Container interaction
    * how to find the container
        * include if multiple are running
    * inadvertent interaction with the sbe software
* Technical (probably goes in the python source)
    * General architecture
    * How is state stored?
    * How are qa tests run?
    * How does is data moved in/out of the running container?
    * How is the software inside the container controlled?