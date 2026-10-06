import pathlib
import sys

import salt.utils.files


def bundled():
    """
    Gather run-time information to indicate if we are running from relenv onedir
    """
    if hasattr(sys, "RELENV"):
        return True
    else:
        return False


def pkg_type():
    """
    Utility to find out how Salt was installed.
    """
    # Relenv / onedir installs must win over a sibling ``_pkg.txt`` from a
    # source checkout (which often says ``pip`` when the tree is bind-mounted
    # next to a relenv interpreter).
    if bundled():
        return "onedir"
    pkg_file = pathlib.Path(__file__).parent.parent / "_pkg.txt"
    if pkg_file.is_file():
        with salt.utils.files.fopen(pkg_file) as _fp:
            content = _fp.read()
            if content:
                return content.strip()
    return None
