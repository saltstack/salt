# -*- coding: utf-8 -*-
"""
Enforce state for SSL/TLS
=========================

"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import datetime
import logging
import time

__virtualname__ = "tls"
log = logging.getLogger(__name__)


def __virtual__():
    if "tls.cert_info" not in __salt__:
        return False

    return __virtualname__


def valid_certificate(name, weeks=0, days=0, hours=0, minutes=0, seconds=0):
    """
    Verify that a TLS certificate is valid now and (optionally) will be valid
    for the time specified through weeks, days, hours, minutes, and seconds.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    now = time.time()
    try:
        cert_info = __salt__["tls.cert_info"](name)
    except IOError as exc:
        ret["comment"] = "{}".format(exc)
        ret["result"] = False
        log.error(ret["comment"])
        return ret

    # verify that the cert is valid *now*
    if now < cert_info["not_before"]:
        ret["comment"] = "Certificate is not yet valid"
        return ret
    if now > cert_info["not_after"]:
        ret["comment"] = "Certificate is expired"
        return ret

    # verify the cert will be valid for defined time
    delta_remaining = datetime.timedelta(seconds=cert_info["not_after"] - now)
    delta_kind_map = {
        "weeks": weeks,
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
    }

    delta_min = datetime.timedelta(**delta_kind_map)
    # if ther eisn't enough time remaining, we consider it a failure
    if delta_remaining < delta_min:
        ret[
            "comment"
        ] = "Certificate will expire in {0}, which is less than {1}".format(
            delta_remaining, delta_min
        )
        return ret

    ret["result"] = True
    ret["comment"] = "Certificate is valid for {0}".format(delta_remaining)
    return ret
