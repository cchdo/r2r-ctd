from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version(__name__)
    """Version string from :py:func:`importlib.metadata.version` or 999 if not installed"""
except PackageNotFoundError:
    __version__ = "999"
