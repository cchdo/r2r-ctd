# R2R Technical Report Quality Assessment Description CTD
:version: 1

:::{note}
This was ported from a PDF into the CTD processing code for reference.
The [original document](https://service.rvdata.us/docs/qa_docs/CTD/R2R_CTD_QualityAssessment_Description.pdf) is still authoritative for R2R.
:::

## Contact
R2R Program, info@rvdata.us

## Authors
* Cynthia Sellers,Woods Hole Oceanographic Institution, US
* Laura Stolp, Woods Hole Oceanographic Institution, USo

## About R2R
The Rolling Deck to Repository (R2R) Program works with the US academic research fleet
community to routinely document, assess, and preserve the underway sensor data from
oceanographic research vessels. For more information, see the R2R website at
http://www.rvdata.us/ .

## Acknowledgements
R2R is funded primarily by the National Science Foundation and Office of Naval Research
(ONR), with assistance from the University-National Oceanographic Laboratory System
(UNOLS) and in close partnership with NOAA's National Centers for Environmental Information.

Any opinions, findings, and conclusions or recommendations expressed in this material are
those of the author(s) and do not necessarily reflect the views of NSF or any other
agency/contributor

## Overview of Workflow
R2R performs Quality Assessment (QA) on the original data set as received from the vessel. QA
has been designed to highlight potential problems with the data sets but does not address the
scientific validity of the data. This assessment includes tests of the individual files and variables
within the files of a data set. Each test is given a rating of green (passed all tests), yellow
(suspicious test results), or red (possible significant problems), with the thresholds for each test.
An overall rating for the entire file is derived from the ratings for the individual tests.

All tests are performed programmatically, no manual evaluations are run. QA tests include
dataset-level assessments, such as whether appropriate metadata exists and checking for
errors in the file formatting, and can also include summaries of record-level testing of the data.
R2R QA routines do not alter the original data files. The results of QA are publicly accessible
on the [R2R QA dashboard](http://get.rvdata.us/qa_inc/?view=verbose) as well as through the cruise catalog and web services. Test results
for each data file are recorded in an XML report which is distributed with the raw data products.
Detailed information on the specific tests performed is listed in the Description of QA Processing
section.

## Description of QA Processing
For each SBE 911 CTD cast within the cruise being assessed, a series of tests are performed
on the raw data files to determine if the data were collected properly, using the vendor-provided,
SeaSave software, and whether the cast occurred within the temporal and spatial bounds of the
cruise. Specific results of the tests differ in format – some may be simple true/false checks,
others may have a specific numeric value – but each test is assigned an associated green,
yellow, or red value. Test results are recorded in an xml report that is distributed with the set of
products. Four tests are performed and additional file info blocks are provided in order to
assess the overall quality of a dataset. Detailed information on the specific tests performed is
listed below:

* _Presence of All Raw Files_: Percent of casts with the three files required for processing (hex/dat,xmlcon/con,hdr). If all three files are not present the CTD cast cannot be processed. Additional informational flags:

    * number of raw files present, indicating the number of CTD casts in the cruise.
    * number of casts that include a .bl (bottle file), indicating whether water bottles were tripped during the cast.
    * list of casts without all 3 raw files required for processing(.hex,.hdr,.xmlcon), if all three files are not present the the cast cannot be processed and are noted in the associated XML report.

* _Valid Checksum for All Files in Manifest_: Verifies that the computed checksum for all manifested data files match the listed checksum. An invalid checksum can indicate a corrupted data file, missing or unreadable files, these files are not checked, and this included in the XML report.
* _Lat/Lon within NAV Ranges_: Percent of files with Lat/Lon within cruise boundaries.

    * number of casts with nav for every scan.
    * list of casts with bad nav format in header.
    * list of casts with blank or missing nav in header.
    * list of casts outside of nav/date bounds.

* _Dates within NAV Ranges_: Percent of files with Date/Time within cruise boundaries.
* _Additional Info blocks_: Information gathered about the data and also creates a lists of casts provided by the QA analysis which will not be processed:

    * number of casts with nav for every scan.
    * list of casts with bad nav format in header.
    * list of casts with blank or missing nav in header.
    * list of casts outside of nav/date bounds.
    * list of casts with 'deck'/’dock’ and 'test' in the file name.
    * list of casts with a hex file that is not ascii hex.
    * list of casts with a con file that is not ascii.
    * list of casts with cond. sensor mismatch (data file vs con file), this would show raw files had been hand edited, or the con file is incorrect.
    * list of casts with temp. sensor mismatch (data file vs con file), this would show raw files had been hand edited, or the con file is incorrect.
    * list of casts where ‘Bytes Per Scan’ does not equal ‘Scan Length’

During QA analysis, ‘virtually empty’ CTD filesets, those with no casts that can be processed, are discovered and reported back to R2R to be flagged as cruise without valid CTD data, and data should not be submitted to NCEI.

## Description of Product Set

### XML Reports
An XML QA report summarizing the tests performed, the result values of each test (if applicable) and the resulting green/yellow/red grades for each test is generated during QA. This XML report contains a comprehensive set of cruise and fileset level metadata for the original, input data. The XML QA report is available on the [R2R QA dashboard](http://get.rvdata.us/qa_inc/?view=verbose) as well as through the cruise catalog and web services.

## References
Additional documentation for the vessel, device make/model and file formats may be available
for download through the references section of the XML QA reports for each file set processed.
See the [R2R QA dashboard](http://get.rvdata.us/qa_inc/?view=verbose) for more information.

R2R is working towards making the code developed for quality assessment and data processing
Currently, the existing code requires access to R2R database and directory
publicly available. structures.

## R2R CTD QA Revision History
### Version 1
List of files to avoid in the Data Processing step is made up of casts which did not pass the four
QA tests.
Since early 2017 These additional checks have performed:

* cruise boundaries are increased by .0002 degrees) to avoid occasional rounding causing casts to fail the cruise boundary test.
* list of casts with 'deck'/’dock’ and 'test' in the file name
* list of casts with a hex file that isn't ASCII hex
* list of casts with a con file that isn't ASCII
* list of casts with cond. sensor mismatch(data file vs con file)
* list of casts with temp. sensor mismatch(data file vs con file)
* list of casts where ‘Bytes Per Scan’ does not equal ‘Scan Length’

Casts in these lists will also be avoided during Data Processing.