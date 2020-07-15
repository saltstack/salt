# -*- coding: utf-8 -*-
"""
Grains for Fibre Channel WWN's. On Windows this runs a PowerShell command that
queries WMI to get the Fibre Channel WWN's available.

.. versionadded:: 2018.3.0

To enable these grains set ``fibre_channel_grains: True``.

.. code-block:: yaml

    fibre_channel_grains: True
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import glob
import logging

# Import Salt libs
import salt.modules.cmdmod
import salt.utils.files
import salt.utils.platform

__virtualname__ = "fibre_channel"

# Get logging started
log = logging.getLogger(__name__)


def __virtual__():
    if __opts__.get("fibre_channel_grains", False) is False:
        return False
    else:
        return __virtualname__


def _linux_wwns():
    """
    Return Fibre Channel port WWNs from a Linux host.
    """
    ret = []
    for fc_file in glob.glob("/sys/class/fc_host/*/port_name"):
        with salt.utils.files.fopen(fc_file, "r") as _wwn:
            content = _wwn.read()
            for line in content.splitlines():
                ret.append(line.rstrip()[2:])
    return ret


def _windows_wwns():
    """
    Return Fibre Channel port WWNs from a Windows host.
    """
    ps_cmd = (
        r"Get-WmiObject -ErrorAction Stop "
        r"-class MSFC_FibrePortHBAAttributes "
        r'-namespace "root\WMI" | '
        r"Select -Expandproperty Attributes | "
        r'%{($_.PortWWN | % {"{0:x2}" -f $_}) -join ""}'
    )
    ret = []
    cmd_ret = salt.modules.cmdmod.powershell(ps_cmd)
    for line in cmd_ret:
        ret.append(line.rstrip())
    return ret


def fibre_channel_wwns():
    """
    Return list of fiber channel HBA WWNs
    """
    grains = {"fc_wwn": False}
    if salt.utils.platform.is_linux():
        grains["fc_wwn"] = _linux_wwns()
    elif salt.utils.platform.is_windows():
        grains["fc_wwn"] = _windows_wwns()
    return grains
