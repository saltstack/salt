"""
Generate baseline proxy minion grains for ESXi hosts.

.. Warning::
    This module will be deprecated in a future release of Salt. VMware strongly
    recommends using the
    `VMware Salt extensions <https://docs.saltproject.io/salt/extensions/salt-ext-modules-vmware/en/latest/all.html>`_
    instead of the ESXi module. Because the Salt extensions are newer and
    actively supported by VMware, they are more compatible with current versions
    of ESXi and they work well with the latest features in the VMware product
    line.


"""


import logging

import salt.utils.proxy
from salt.exceptions import SaltSystemExit

__proxyenabled__ = ["esxi"]
__virtualname__ = "esxi"

log = logging.getLogger(__file__)

GRAINS_CACHE = {}


def __virtual__():

    # import salt.utils.proxy again
    # so it is available for tests.
    import salt.utils.proxy

    try:
        if salt.utils.proxy.is_proxytype(__opts__, "esxi"):
            import salt.modules.vsphere

            return __virtualname__
    except KeyError:
        pass

    return False


def esxi():
    return _grains()


def kernel():
    return {"kernel": "proxy"}


def os():
    if not GRAINS_CACHE:
        GRAINS_CACHE.update(_grains())

    try:
        return {"os": GRAINS_CACHE.get("fullName")}
    except AttributeError:
        return {"os": "Unknown"}


def os_family():
    return {"os_family": "proxy"}


def _find_credentials(host):
    """
    Cycle through all the possible credentials and return the first one that
    works.
    """
    user_names = [__pillar__["proxy"].get("username", "root")]
    passwords = __pillar__["proxy"]["passwords"]
    for user in user_names:
        for password in passwords:
            try:
                # Try to authenticate with the given user/password combination
                ret = salt.modules.vsphere.system_info(
                    host=host, username=user, password=password
                )
            except SaltSystemExit:
                # If we can't authenticate, continue on to try the next password.
                continue
            # If we have data returned from above, we've successfully authenticated.
            if ret:
                return user, password
    # We've reached the end of the list without successfully authenticating.
    raise SaltSystemExit(
        "Cannot complete login due to an incorrect user name or password."
    )


def _grains():
    """
    Get the grains from the proxied device.
    """
    try:
        host = __pillar__["proxy"]["host"]
        if host:
            username, password = _find_credentials(host)
            protocol = __pillar__["proxy"].get("protocol")
            port = __pillar__["proxy"].get("port")
            ret = salt.modules.vsphere.system_info(
                host=host,
                username=username,
                password=password,
                protocol=protocol,
                port=port,
            )
            GRAINS_CACHE.update(ret)
    except KeyError:
        pass

    return GRAINS_CACHE
