from pathlib import Path
from logging import getLogger

import numpy as np
import xarray as xr

logger = getLogger(__name__)


def is_deck_test(path: Path) -> bool:
    """Check if the given path "looks like" a deck test
    
    This method matches the pathname against a list of strings that are common to desk tests
    """
    logger.debug(f"Checking if {path} is a decktest")
    # this should match the behavior of WHOI tests, but felt fragile to me
    substrs = (
        "deck",
        "dock",
        "test",
        "999",
        "998",
        "997",
        "996",
        "995",
        "994",
        "993",
        "992",
        "991",
        "990",
    )
    for substr in substrs:
        if substr in path.name:
            return True
    return False


def check_three_files(ds: xr.Dataset) -> np.int8:
    """Check that each hex file has both an xmlcon and hdr files associated with it.
    
    The input dataset is expected conform output of odf.sbe.read_hex. This dataset
    is then checked to see if it has all the correct keys. The details of finding/reading
    those files is left to odf.sbe.

    This the result of this function need to be an integer 0 or 1 because it will be stored 
    """
    logger.debug("Checking if all three files")
    three_files = {"hex", "xmlcon", "hdr"}
    if (residual := three_files - ds.keys()) != set():
        logger.error(f"The following filetypes are missing {residual}")
        return np.int8(0)
    logger.debug("All three files present")
    return np.int8(1)


def manifest(path: Path) -> bool:
    return True
