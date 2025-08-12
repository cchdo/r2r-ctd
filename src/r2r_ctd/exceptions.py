"""Exception classes for very specific things we want to catch related to the containerized SBE software"""


class InvalidSBEFileError(ValueError):
    """Base exception for when things go wrong with the SeaBird software itself"""


class InvalidXMLCONError(InvalidSBEFileError):
    """Exception raised when ConReport.exe says the XMLCON is not valid"""


class WineDebuggerEnteredError(RuntimeError):
    """Exception raised when the debugger launched message appears within the container logs"""
