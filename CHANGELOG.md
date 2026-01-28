# Changelog

## v2026.01.0 (2026-01-28)
* Allow runtime configuration of the SBE Data Processing companion image by setting an envvar: `R2R_CTD_SBEDP_IMAGE`.
* Updated the default SBE Data Processing companion image to `ghcr.io/cchdo/sbedp:v2026.01.0`

## v2025.09.1 (2025-09-05)
* Skip CNV generation attempt if the hdr temperature/conductivity sensor serial number does not match the first serial number of that sensor type in the xmlcon.

## v2025.09.0 (2025-09-02)
* Added a timeout to the SBEBatch.exe container wine command, this attempts to work around a issue where the wine process would never exit even though work had finished.
  Right now the timeout is 5 minutes and fixed.
* fixed a bug where the wine retry decorator would retry forever
* Increase the cnv generation attempts from 3 to 5
* Add HTML/leaflet based map output
* If no files to test (empty breakout), set overall score to black
* Add runtime control of how to check the payload "data" directory against the manifest
* Changed final rating calculation to match original WHOI software.

## v2025.08.0 (2025-08-11)
* Initial release.
