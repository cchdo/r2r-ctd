import contextlib
from importlib.metadata import PackageNotFoundError, version

__version__: str = "999"

with contextlib.suppress(PackageNotFoundError):
    __version__ = version(__name__)
