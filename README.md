# r2r-ctd
A port/update of the WHOI CTD QC code to something more packaged/modern

This operates on an r2r CTD breakout directory that assumes the following structure:
* /data/
    * contains the raw ctd datafiles
* /manifest-md5.txt
    * A text file with md5 and file path pairs
    * This file can be passed into md5sum -c and should result in a "OK" for each entry
* /qc/
    * should have 3 xmlt files for a fresh breakout, we are interested in the file with the _qa.2.0.xmlt suffix
    * The bounding box and temporal bounds are in this file.