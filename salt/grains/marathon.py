# -*- coding: utf-8 -*-
"""
Generate marathon proxy minion grains.

.. versionadded:: 2015.8.2

"""
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.http
import salt.utils.platform

__proxyenabled__ = ["marathon"]
__virtualname__ = "marathon"


def __virtual__():
    if not salt.utils.platform.is_proxy():
        return False, "marathon: Not a proxy minion"
    try:
        if not __opts__["proxy"]["proxytype"] == "marathon":
            return False, "marathon: Missing proxy configuration"
    except KeyError:
        return False, "marathon: Missing proxy configuration"

    return __virtualname__


def kernel():
    return {"kernel": "marathon"}


def os():
    return {"os": "marathon"}


def os_family():
    return {"os_family": "marathon"}


def os_data():
    return {"os_data": "marathon"}


def marathon():
    response = salt.utils.http.query(
        "{0}/v2/info".format(
            __opts__["proxy"].get("base_url", "http://locahost:8080",)
        ),
        decode_type="json",
        decode=True,
    )
    if not response or "dict" not in response:
        return {"marathon": None}
    return {"marathon": response["dict"]}
