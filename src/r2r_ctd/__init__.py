from importlib.metadata import PackageNotFoundError, version

__version__: str = "999"

try:
    __version__ = version(__name__)
except PackageNotFoundError:
    pass
