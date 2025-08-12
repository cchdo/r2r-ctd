"""r2r_ctd, routines for doing some basic QA on SeaBird CTD Data files

The main entrypoint to the program is in :py:mod:`r2r_ctd.__main__`.
So that's probably the best place to start if you are trying to figure out how everything works.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version(__name__)
    """Version string from :py:func:`importlib.metadata.version` or 999 if not installed"""
except PackageNotFoundError:
    __version__ = "999"
