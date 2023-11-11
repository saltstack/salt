"""
This module is deprecated and will be removed in Salt 3009. Please import ``psutil`` directly.
"""
from psutil import *  # pylint: disable=unused-wildcard-import,

import salt.utils.versions

salt.utils.versions.warn_until(
    3009,
    "The 'salt.utils.psutil_compat' module is deprecated. Please import 'psutil' directly.",
    category=DeprecationWarning,
)
