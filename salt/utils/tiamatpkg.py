import os
import subprocess
import sys

import salt.utils.vt
from salt.utils.decorators import memoize

# This code is temporary and will exist until we can handle this on salt-pkg


@memoize
def is_tiamat_packaged():
    """
    Returns True if salt is running from a tiamat pacakge, False otherwise
    """
    return hasattr(sys, "_MEIPASS")


def _cleanup_environ(environ):
    if environ is None:
        environ = os.environ.copy()

    # When Salt is bundled with tiamat, it MUST NOT contain LD_LIBRARY_PATH
    # when shelling out, or, at least the value of LD_LIBRARY_PATH set by
    # pyinstaller.
    # See:
    #  https://pyinstaller.readthedocs.io/en/stable/runtime-information.html#ld-library-path-libpath-considerations
    for varname in ("LD_LIBRARY_PATH", "LIBPATH"):
        original_varname = "{}_ORIG".format(varname)
        if original_varname in environ:
            environ[varname] = environ.pop(original_varname)
        elif varname in environ:
            environ.pop(varname)
    return environ


class TiamatPopen(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        kwargs["env"] = _cleanup_environ(kwargs.pop("env", None))
        super().__init__(*args, **kwargs)


class TiamatTerminal(salt.utils.vt.Terminal):  # pylint: disable=abstract-method
    def __init__(self, *args, **kwargs):
        kwargs["env"] = _cleanup_environ(kwargs.pop("env", None))
        super().__init__(*args, **kwargs)


if is_tiamat_packaged():
    subprocess.Popen = TiamatPopen
    salt.utils.vt.Terminal = TiamatTerminal
