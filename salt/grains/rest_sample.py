# -*- coding: utf-8 -*-
"""
Generate baseline proxy minion grains
"""
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.platform

__proxyenabled__ = ["rest_sample"]

__virtualname__ = "rest_sample"


def __virtual__():
    try:
        if (
            salt.utils.platform.is_proxy()
            and __opts__["proxy"]["proxytype"] == "rest_sample"
        ):
            return __virtualname__
    except KeyError:
        pass

    return False


def kernel():
    return {"kernel": "proxy"}


def proxy_functions(proxy):
    """
    The loader will execute functions with one argument and pass
    a reference to the proxymodules LazyLoader object.  However,
    grains sometimes get called before the LazyLoader object is setup
    so `proxy` might be None.
    """
    if proxy:
        return {"proxy_functions": proxy["rest_sample.fns"]()}


def os():
    return {"os": "RestExampleOS"}


def location():
    return {"location": "In this darn virtual machine.  Let me out!"}


def os_family():
    return {"os_family": "proxy"}


def os_data():
    return {"os_data": "funkyHttp release 1.0.a.4.g"}
