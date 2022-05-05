"""
Module used to access the esxdatacenter proxy connection methods
"""

import logging

import salt.utils.platform

log = logging.getLogger(__name__)

__proxyenabled__ = ["esxdatacenter"]
# Define the module's virtual name
__virtualname__ = "esxdatacenter"


def __virtual__():
    """
    Only work on proxy
    """
    if salt.utils.platform.is_proxy():
        return __virtualname__
    return (False, "Must be run on a proxy minion")


def get_details():
    return __proxy__["esxdatacenter.get_details"]()
