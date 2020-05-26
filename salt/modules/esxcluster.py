# -*- coding: utf-8 -*-
"""
Module used to access the esxcluster proxy connection methods
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

import salt.utils.platform

log = logging.getLogger(__name__)

__proxyenabled__ = ["esxcluster"]
# Define the module's virtual name
__virtualname__ = "esxcluster"


def __virtual__():
    """
    Only work on proxy
    """
    if salt.utils.platform.is_proxy():
        return __virtualname__
    return (False, "Must be run on a proxy minion")


def get_details():
    return __proxy__["esxcluster.get_details"]()
