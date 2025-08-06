# Running QA Routines

:::{important}
Make sure `r2r-ctd` is talking to docker, see [](#docker) in the [](installing.md) instructions.
:::


## Basic Usage
Given an R2R CTD breakout, run the QA routines by executing:
```
uvx r2r-ctd qa <path_to_breakout>
```
Multiple breakouts can be specified and they will be proceed in sequence:
```
uvx r2r-ctd qa <path_to_breakout1> <path_to_breakout2>
```
:::{important}
Almost all crashes are considered bugs and should be reported/fixed.

With the exception of an invalid breakout structure where the xmlt and manifest files are missing or malformed,
the QA processing should not throw or crash in the case of invalid input files, the invalidness should be reported in the QA xml report itself.

If the xmlt and manifrst file are malformed or missing, something has gone wrong on the r2r side that needs to be investigated.
:::

### Switches
#### Quiet `-q`
The verbosity of the logging can be controlled by adding one or more `-q` flags after the `r2r-ctd` but _before_ the `qa` subcommand.

```
uvx r2r-ctd -q qa <path_to_breakout>
```
Only prints log message of level `INFO` or greater.
Each `q` reduces the log verbosity by one [level](https://docs.python.org/3/library/logging.html#logging-levels) from the default which is `DEBUG`.

```
uvx r2r-ctd -qq qa <path_to_breakout>
```
Only prints logs messages of level `WARNING` or greater.

#### Skip CNV generation `--no-gen-cnvs`
Generating the cnv products is not necessary for the QA routines, it is also computationally expensive.
Adding a `--no-gen-cnvs` will skip generating these files:
```
uvx r2r-ctd qa --no-gen-cnvs <path_to_breakout>
```

## Breakout Structure
The R2R CTD Breakout must have the following structure and _almost_ follows the [BagIt][bagit] standard[^bagit_note].
The starting `/` will refer here to the root of the breakout
[^bagit_note]: It’s basically only missing the `bagit.txt` file.


* A `/manifest-md5.txt` containing a list of md5 file hashes and relative paths to the files corresponding to those hashes.
* A `/qa` directory containing at a minimum a `*_qa.2.0.xmlt` file that conforms to the [R2R QA 2.0 Schema](http://schema.rvdata.us/2.0/qareport.xsd) schema.
  The prefix of this xml file is probably some combination of cruise name and breakout id, however this is not too important, only that exactly one file matches this pattern.

While the [BagIt][BagIt] spec wants all the actual content to be in a `/data` directory, `r2r-ctd` just uses the paths inside the `manifest-md5.txt` file.
The details of what cruise specific files are being looked for within the `/data` directory are in the API documentation.


[bagit]: https://en.wikipedia.org/wiki/BagIt

### `*_qa.2.0.xmlt`
This xml file is the "template" that will both be updated with the results of the QA routines, but also contains some of the metadata that the breakout files are tested against.
Specifically, the cruise start/end dates and the bounding box.


## QA Results
Several result files are produced along with some processing state files.
Everything `r2r-ctd` generates will be placed into a `/proc` directory[^whoi_diff1].
Inside this `/proc` directory are several other directories:
[^whoi_diff1]: This differs from the inherited project code that modifies the QA directory of the original breakout. The choice here is to keep a hard (ish) separation between the original breakout and things derived from it. You can just delete the whole `/proc` directory and be able to run the whole QA routine again.

* `/proc/nc` has netCDF files containing all the "state" of the QA routines, this includes test results and derived files.
  These netCDF files are an implementation detail and the contents can be ignored unless things are going really wrong.
  These files can be safely deleted, but is removes the "cache" of the QA results for each cast.
  Do not modify these files.
* `/proc/qa` will have the qa results:
    * If the QA routines finished a `*_qa.2.0.xml` will be present (note the lack of `t` in the file extension), updated with results
    * A `*_ctd_metdata.geoCSV` file should be present.
    * A `/proc/qa/config` directory containing the instrument configuration report text files.
* `/proc/products/r2rctd` will have all the generated cnv files (2 per cast) if the `--no-gen-cnvs` switch was not provided.

Presumably, the contents of `/proc` excluding the `nc` sub-directory can be rsync-ed back to the r2r server (without the `--delete` switch)

## Parallel Processing
Since docker provides reasonable process isolation for the Windows based conversion tools, it is possible to have multiple container instances running the Seabird software in parallel.
This is most simply done by having multiple terminal sessions open and running the basic usage commands above on a single breakout in each session.
In the same session you could also use something like `xargs` to parallelize, but the emitted log message will be muxed making it difficult to follow what is going on.

In general, you'll want to limit the number of parallel processors going to the number of physical cores in your CPU, in the case of Apple arm hardware, this is the number of performance cores your machine has.
To see how many performance cores are present on an M-family mac, you can use the `system_profiler` command:
```
system_profiler SPHardwareDataType
```
Look for the line that says: `Total Number of Cores:`
In parenthesis it should have the breakdown between performance and efficiency cores.
For example, the baseline M4 MacBook Air has 10 cores but only 4 are performance, so the number of parallel processes should reasonably kept to 4:
```
Total Number of Cores: 10 (4 performance and 6 efficiency)
```