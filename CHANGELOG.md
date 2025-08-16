# Changelog

## v2025.08.1 (2025-08-??)
* Added a timeout to the SBEBatch.exe container wine command, this attempts to work around a issue where the wine process would never exit even though work had finished.
  Right now the timeout is 5 minutes and fixed.
* fixed a bug where the wine retry decorator would retry forever
* Increase the cnv generation attempts from 3 to 5
* Add HTML/leaflet based map output

## v2025.08.0 (2025-08-11)
* Initial release.