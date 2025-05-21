from pathlib import Path
from logging import getLogger

import numpy as np

logger = getLogger(__name__)


def is_deck_test(path: Path) -> bool:
    logger.debug(f"Checking if {path} is a decktest")
    # this should match the behavior of tests, but felt fragile to me
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


def check_three_files(ds):
    logger.debug("Checking if all three files")
    three_files = {"hex", "xmlcon", "hdr"}
    if (residual := three_files - ds.keys()) != set():
        logger.error(f"The following filetypes are missing {residual}")
        return np.int8(0)
    logger.debug("All three files present")
    return np.int8(1)


def manifest(path: Path) -> bool:
    return True
