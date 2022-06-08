"""
This package contains the runtime hooks support code for when Salt is pacakged with PyInstaller.
"""
import logging
import os
import subprocess
import sys

import salt.utils.vt

log = logging.getLogger(__name__)


def clean_pyinstaller_vars(environ):
    """
    Restore or cleanup PyInstaller specific environent variable behavior.
    """
    if environ is None:
        environ = {}
    # When Salt is bundled with tiamat, it MUST NOT contain LD_LIBRARY_PATH
    # when shelling out, or, at least the value of LD_LIBRARY_PATH set by
    # pyinstaller.
    # See:
    #  https://pyinstaller.readthedocs.io/en/stable/runtime-information.html#ld-library-path-libpath-considerations
    for varname in ("LD_LIBRARY_PATH", "LIBPATH"):
        original_varname = "{}_ORIG".format(varname)
        if varname in environ and environ[varname] == sys._MEIPASS:
            # If we find the varname on the user provided environment we need to at least
            # check if it's not the value set by PyInstaller, if it is, remove it.
            log.debug(
                "User provided environment variable %r with value %r which is "
                "the value that PyInstaller set's. Removing it",
                varname,
                environ[varname],
            )
            environ.pop(varname)

        if original_varname in environ and varname not in environ:
            # We found the original variable set by PyInstaller, and we didn't find
            # any user provided variable, let's rename it.
            log.debug(
                "The %r variable was found in the passed environment, renaming it to %r",
                original_varname,
                varname,
            )
            environ[varname] = environ.pop(original_varname)

        if varname not in environ:
            if original_varname in os.environ:
                log.debug(
                    "Renaming environment variable %r to %r", original_varname, varname
                )
                environ[varname] = os.environ[original_varname]
            elif varname in os.environ:
                # Override the system environ variable with an empty one
                log.debug("Setting environment variable %r to an empty string", varname)
                environ[varname] = ""
    return environ


class PyinstallerPopen(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        kwargs["env"] = clean_pyinstaller_vars(kwargs.pop("env", None))
        super().__init__(*args, **kwargs)


class PyinstallerTerminal(salt.utils.vt.Terminal):  # pylint: disable=abstract-method
    def __init__(self, *args, **kwargs):
        kwargs["env"] = clean_pyinstaller_vars(kwargs.pop("env", None))
        super().__init__(*args, **kwargs)
