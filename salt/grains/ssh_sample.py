# -*- coding: utf-8 -*-
"""
Generate baseline proxy minion grains
"""
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.platform

__proxyenabled__ = ["ssh_sample"]

__virtualname__ = "ssh_sample"


def __virtual__():
    if not salt.utils.platform.is_proxy():
        return False, "ssh_sample: Not a proxy minion"
    try:
        if not __opts__["proxy"]["proxytype"] == "ssh_sample":
            return False, "ssh_sample: Missing proxy configuration"
    except KeyError:
        return False, "ssh_sample: Missing proxy configuration"

    return __virtualname__


def kernel():
    return {"kernel": "proxy"}


def proxy_functions(proxy):
    """
    The loader will execute functions with one argument and pass
    a reference to the proxymodules LazyLoader object.  However,
    grains sometimes get called before the LazyLoader object is setup
    so `proxy` might be None.
    """
    return {"proxy_functions": proxy["ssh_sample.fns"]()}


def location():
    return {"location": "At the other end of an SSH Tunnel!!"}


def os_data():
    return {"os_data": "DumbShell Endpoint release 4.09.g"}
