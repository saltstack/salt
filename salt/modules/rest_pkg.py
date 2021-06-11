# -*- coding: utf-8 -*-
"""
Package support for the REST example
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging

# Import Salt libs
import salt.utils.data
import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pkg"


def __virtual__():
    """
    Only work on systems that are a proxy minion
    """
    try:
        if (
            salt.utils.platform.is_proxy()
            and __opts__["proxy"]["proxytype"] == "rest_sample"
        ):
            return __virtualname__
    except KeyError:
        return (
            False,
            "The rest_package execution module failed to load. Check the "
            "proxy key in pillar.",
        )

    return (
        False,
        "The rest_package execution module failed to load: only works on a "
        "rest_sample proxy minion.",
    )


def list_pkgs(versions_as_list=False, **kwargs):
    return __proxy__["rest_sample.package_list"]()


def install(name=None, refresh=False, fromrepo=None, pkgs=None, sources=None, **kwargs):
    return __proxy__["rest_sample.package_install"](name, **kwargs)


def remove(name=None, pkgs=None, **kwargs):
    return __proxy__["rest_sample.package_remove"](name)


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
        return six.text_type(__proxy__["rest_sample.package_status"](names[0]))


def upgrade(refresh=True, skip_verify=True, **kwargs):
    old = __proxy__["rest_sample.package_list"]()
    new = __proxy__["rest_sample.uptodate"]()
    pkg_installed = __proxy__["rest_sample.upgrade"]()
    return salt.utils.data.compare_dicts(old, pkg_installed)


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

    p = __proxy__["rest_sample.package_status"](name)
    if version is None:
        if "ret" in p:
            return six.text_type(p["ret"])
        else:
            return True
    else:
        if p is not None:
            return version == six.text_type(p)
