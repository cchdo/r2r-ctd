from pathlib import Path


def is_deck_test(path: Path) -> bool:
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


def manifest(path: Path) -> bool:
    return True
