# -*- coding: utf-8 -*-
"""
Module used to access the vcenter proxy connection methods
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

import salt.utils.platform

log = logging.getLogger(__name__)

__proxyenabled__ = ["vcenter"]
# Define the module's virtual name
__virtualname__ = "vcenter"


def __virtual__():
    """
    Only work on proxy
    """
    if salt.utils.platform.is_proxy():
        return __virtualname__
    return False


def get_details():
    return __proxy__["vcenter.get_details"]()
