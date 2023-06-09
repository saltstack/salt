import sys


def pkg_type():
    """
    Gather run-time information to indicate if we are running from onedir or .
    """
    if hasattr(sys, "RELENV"):
        return "onedir"
    else:
        return "system"
