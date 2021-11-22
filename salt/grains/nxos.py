"""
Grains for Cisco NX-OS minions

.. versionadded:: 2016.11.0

For documentation on setting up the nxos proxy minion look in the documentation
for :mod:`salt.proxy.nxos<salt.proxy.nxos>`.
"""

import logging

import salt.utils.nxos
import salt.utils.platform
from salt.exceptions import NxosClientError

log = logging.getLogger(__name__)

__proxyenabled__ = ["nxos"]
__virtualname__ = "nxos"


def __virtual__():
    try:
        salt.utils.nxos.version_info()
    except NxosClientError as err:
        return False, err

    return __virtualname__


def system_information(proxy=None):
    if salt.utils.platform.is_proxy():
        if proxy is None:
            return {}
        if proxy["nxos.initialized"]() is False:
            return {}
        return {"nxos": proxy["nxos.grains"]()}
    else:
        data = salt.utils.nxos.version_info()
        return salt.utils.nxos.system_info(data)
