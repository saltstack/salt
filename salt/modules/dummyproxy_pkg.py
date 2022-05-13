"""
Package support for the dummy proxy used by the test suite
"""

import logging

import salt.utils.data
import salt.utils.platform

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Only work on systems that are a proxy minion
    """
    try:
        if salt.utils.platform.is_proxy() and __opts__["proxy"]["proxytype"] == "dummy":
            return __virtualname__
    except KeyError:
        return (
            False,
            "The dummyproxy_package execution module failed to load. Check "
            "the proxy key in pillar or /etc/salt/proxy.",
        )

    return (
        False,
        "The dummyproxy_package execution module failed to load: only works "
        "on a dummy proxy minion.",
    )


def list_pkgs(versions_as_list=False, **kwargs):
    return __proxy__["dummy.package_list"]()


def install(name=None, refresh=False, fromrepo=None, pkgs=None, sources=None, **kwargs):
    return __proxy__["dummy.package_install"](name, **kwargs)


def remove(name=None, pkgs=None, **kwargs):
    return __proxy__["dummy.package_remove"](name)


def version(*names, **kwargs):
    """
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    """
    if len(names) == 1:
        vers = __proxy__["dummy.package_status"](names[0])
        return vers[names[0]]
    else:
        results = {}
        for n in names:
            vers = __proxy__["dummy.package_status"](n)
            results.update(vers)
        return results


def upgrade(
    name=None, pkgs=None, refresh=True, skip_verify=True, normalize=True, **kwargs
):
    old = __proxy__["dummy.package_list"]()
    new = __proxy__["dummy.uptodate"]()
    pkg_installed = __proxy__["dummy.upgrade"]()
    ret = salt.utils.data.compare_dicts(old, pkg_installed)
    return ret


def installed(
    name,
    version=None,
    refresh=False,
    fromrepo=None,
    skip_verify=False,
    pkgs=None,
    sources=None,
    **kwargs
):

    p = __proxy__["dummy.package_status"](name)
    if version is None:
        if "ret" in p:
            return str(p["ret"])
        else:
            return True
    else:
        if p is not None:
            return version == str(p)
