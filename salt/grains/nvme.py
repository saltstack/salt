"""
Grains for NVMe Qualified Names (NQN).

.. versionadded:: 3000

To enable these grains set `nvme_grains: True` in the minion config.

.. code-block:: yaml

    nvme_grains: True
"""

import errno
import logging

import salt.utils.files
import salt.utils.path
import salt.utils.platform

__virtualname__ = "nvme"

# Get logging started
log = logging.getLogger(__name__)


def __virtual__():
    if __opts__.get("nvme_grains", False) is False:
        return False
    return __virtualname__


def nvme_nqn():
    """
    Return NVMe NQN
    """
    grains = {}
    grains["nvme_nqn"] = False
    if salt.utils.platform.is_linux():
        grains["nvme_nqn"] = _linux_nqn()
    return grains


def _linux_nqn():
    """
    Return NVMe NQN from a Linux host.
    """
    ret = []

    initiator = "/etc/nvme/hostnqn"
    try:
        with salt.utils.files.fopen(initiator, "r") as _nvme:
            for line in _nvme:
                line = line.strip()
                if line.startswith("nqn."):
                    ret.append(line)
    except OSError as ex:
        if ex.errno != errno.ENOENT:
            log.debug("Error while accessing '%s': %s", initiator, ex)

    return ret
