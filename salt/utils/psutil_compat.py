"""
Version agnostic psutil hack to fully support both old (<2.0) and new (>=2.0)
psutil versions.

The old <1.0 psutil API is dropped in psutil 3.0

Should be removed once support for psutil <2.0 is dropped. (eg RHEL 6)

Built off of http://grodola.blogspot.com/2014/01/psutil-20-porting.html
"""

from psutil import *  # pylint: disable=wildcard-import,unused-wildcard-import,3rd-party-module-not-gated

import salt.utils.versions

salt.utils.versions.warn_until(
    3008,
    "Please stop importing 'salt.utils.psutil_compat' and instead import "
    "'psutil' directly as there's no longer a need for a compatability "
    "layer. The 'salt.utils.psutil_compat' will go away on Salt {version}.",
)
