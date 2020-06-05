# -*- coding: utf-8 -*-
"""
Generate chronos proxy minion grains.

.. versionadded:: 2015.8.2

"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.http
import salt.utils.platform

__proxyenabled__ = ["chronos"]
__virtualname__ = "chronos"


def __virtual__():
    if not salt.utils.platform.is_proxy():
        return False, "chronos: Not a proxy minion"
    try:
        if not __opts__["proxy"]["proxytype"] == "chronos":
            return False, "chronos: Missing proxy configuration"
    except KeyError:
        return False, "chronos: Missing proxy configuration"

    return __virtualname__


def kernel():
    return {"kernel": "chronos"}


def os():
    return {"os": "chronos"}


def os_family():
    return {"os_family": "chronos"}


def os_data():
    return {"os_data": "chronos"}
