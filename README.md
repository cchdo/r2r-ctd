# R2R CTD
A port/update of the WHOI CTD QC code to something more packaged/modern

This operates on an r2r CTD breakout direrctory that assumes the following structure:
* /data/
    * contains the raw ctd datafiles
* /manifest-md5.txt
    * A text file with md5 and file path pairs
    * This file can be passed into md5sum -c and should result in a "OK" for each entry
* /qc/
    * should have 3 xmlt files for a fresh breakout, we are interested in the file with the _qa.2.0.xmlt suffix
    * The bounding box and temporal bounds are in this file.

Steps needed to do:
- [x] Check manifest file against breakout contents
- [x] create a list of "stations" from these files
- [ ] initialize a geocsv
- [ ] for each "station"
  - [X] exclude if looks like a deck test
  - [X] run conreport (dockerized sbe software)
  - [X] check if "all 3" files are present
  - [X] validate time against curise bounds
  - [X] validate lat/lon against cruise bounds
  - [X] collect "cast info" (there is a bunch that goes in here)
  - [ ] write a record in the geoCSV
  - [ ] make seabird output products (dockerized sbe software)

Progress as of 2025-05-20:
* Had meeting with Alan about if this approach is workable, agreement that yes it is a good idea, so "full speed ahead"
* 3 files present test being wirtten into nc state
* conreport results being written into nc state

Progress as of 2025-05-19:
* Decided to do with the odf.sbe netCDF/xarray file as a container for state and implimenting this. Plan is as follows:
 - Check results will go into a r2r_qc var namespace
 - results of file processing (e.g. conreport or other sbe processing steps) will go into their own vars so we can check if they are done to save processing time on repeat errors

Progress as of 2025-05-16:
* Started on an actual package to capture all the processing code
* Able to generate the config reports using the dockerized seabird software, it is not speedy (about 10s per conf) but it works. The host - guest boundary is a little tricky to navigate here and will need a lot of explination.

Other things needing to be sorted out:
* How is state stored? some of these steps are not speedy and should be avoided if not needed to be run again.
  - options I can think of: specific file strcutre on disk; state in xarray object/netCDF building on odf.sbe; keep things in the qa xml?
* The existing QA code is class based and a little tricky to follow, do we want to continue the class based method? If yes, I'd rather keep things in an xarray object as above idea.