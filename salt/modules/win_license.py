# -*- coding: utf-8 -*-
"""
This module allows you to manage windows licensing via slmgr.vbs

.. code-block:: bash

    salt '*' license.install XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

# Import Salt Libs
import salt.utils.platform

log = logging.getLogger(__name__)
__virtualname__ = "license"


def __virtual__():
    """
    Only work on Windows
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return False


def installed(product_key):
    """
    Check to see if the product key is already installed.

    Note: This is not 100% accurate as we can only see the last
     5 digits of the license.

    CLI Example:

    .. code-block:: bash

        salt '*' license.installed XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """
    cmd = r"cscript C:\Windows\System32\slmgr.vbs /dli"
    out = __salt__["cmd.run"](cmd)
    return product_key[-5:] in out


def install(product_key):
    """
    Install the given product key

    CLI Example:

    .. code-block:: bash

        salt '*' license.install XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """
    cmd = r"cscript C:\Windows\System32\slmgr.vbs /ipk {0}".format(product_key)
    return __salt__["cmd.run"](cmd)


def uninstall():
    """
    Uninstall the current product key

    CLI Example:

    .. code-block:: bash

        salt '*' license.uninstall
    """
    cmd = r"cscript C:\Windows\System32\slmgr.vbs /upk"
    return __salt__["cmd.run"](cmd)


def activate():
    """
    Attempt to activate the current machine via Windows Activation

    CLI Example:

    .. code-block:: bash

        salt '*' license.activate
    """
    cmd = r"cscript C:\Windows\System32\slmgr.vbs /ato"
    return __salt__["cmd.run"](cmd)


def licensed():
    """
    Return true if the current machine is licensed correctly

    CLI Example:

    .. code-block:: bash

        salt '*' license.licensed
    """
    cmd = r"cscript C:\Windows\System32\slmgr.vbs /dli"
    out = __salt__["cmd.run"](cmd)
    return "License Status: Licensed" in out


def info():
    """
    Return information about the license, if the license is not
    correctly activated this will return None.

    CLI Example:

    .. code-block:: bash

        salt '*' license.info
    """
    cmd = r"cscript C:\Windows\System32\slmgr.vbs /dli"
    out = __salt__["cmd.run"](cmd)

    match = re.search(
        r"Name: (.*)\r\nDescription: (.*)\r\nPartial Product Key: (.*)\r\nLicense Status: (.*)",
        out,
        re.MULTILINE,
    )

    if match is not None:
        groups = match.groups()
        return {
            "name": groups[0],
            "description": groups[1],
            "partial_key": groups[2],
            "licensed": "Licensed" in groups[3],
        }

    return None
