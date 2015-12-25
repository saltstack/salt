# -*- coding: utf-8 -*-
'''
Service support for the REST example
'''
from __future__ import absolute_import

# Import python libs
import logging
import salt.utils


log = logging.getLogger(__name__)

__proxyenabled__ = ['rest_sample']
# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Only work on proxy
    '''
    if salt.utils.is_proxy():
        return __virtualname__
    return (False, 'The rest_package execution module failed to load: only available on proxy minions.')


def list_pkgs(versions_as_list=False, **kwargs):
    return __proxy__['rest_sample.package_list']()


def install(name=None, refresh=False, fromrepo=None,
            pkgs=None, sources=None, **kwargs):
    return __proxy__['rest_sample.package_install'](name, **kwargs)


def remove(name=None, pkgs=None, **kwargs):
    return __proxy__['rest_sample.package_remove'](name)


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    if len(names) == 1:
        return str(__proxy__['rest_sample.package_status'](names[0]))


def installed(
        name,
        version=None,
        refresh=False,
        fromrepo=None,
        skip_verify=False,
        pkgs=None,
        sources=None,
        **kwargs):

    p = __proxy__['rest_sample.package_status'](name)
    if version is None:
        if 'ret' in p:
            return str(p['ret'])
        else:
            return True
    else:
        if p is not None:
            return version == str(p)
