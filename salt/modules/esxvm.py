"""
Module used to access the esx proxy connection methods
"""


import logging
from functools import wraps

import salt.utils.platform

log = logging.getLogger(__name__)

__proxyenabled__ = ["esxvm"]
# Define the module's virtual name
__virtualname__ = "esxvm"


def __virtual__():
    """
    Only work on proxy
    """
    if salt.utils.platform.is_proxy():
        return __virtualname__
    return (False, "Must be run on a proxy minion")


def _deprecation_message(function):
    """
    Decorator wrapper to warn about azurearm deprecation
    """

    @wraps(function)
    def wrapped(*args, **kwargs):
        salt.utils.versions.warn_until(
            "Argon",
            "The 'esxvm' functionality in Salt has been deprecated and its "
            "functionality will be removed in version 3008 in favor of the "
            "saltext.vmware Salt Extension. "
            "(https://github.com/saltstack/salt-ext-modules-vmware)",
            category=FutureWarning,
        )
        ret = function(*args, **salt.utils.args.clean_kwargs(**kwargs))
        return ret

    return wrapped


@_deprecation_message
def get_details():
    return __proxy__["esxvm.get_details"]()
