"""
Grains for detecting what type of package Salt is using

.. versionadded:: 3007.0
"""

import logging

import salt.utils.package

log = logging.getLogger(__name__)


__virtualname__ = "package"


def __virtual__():
    return __virtualname__


def package():
    """
    Function to determine if the user is currently using
    onedir, pip or system level package of Salt.
    """
    return {"package": salt.utils.package.pkg_type()}
