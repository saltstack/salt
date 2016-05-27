# -*- coding: utf-8 -*-
'''
Service support for the REST example
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import Salt's libs
import salt.utils


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Only work on proxy
    '''
    try:
        if salt.utils.is_proxy() and __opts__['proxy']['proxytype'] == 'ssh_sample':
            return __virtualname__
    except KeyError:
        return (False, 'The ssh_package execution module failed to load.  Check the proxy key in pillar.')

    return (False, 'The ssh_package execution module failed to load: only works on an ssh_sample proxy minion.')


def list_pkgs(versions_as_list=False, **kwargs):
    return __proxy__['ssh_sample.package_list']()


def install(name=None, refresh=False, fromrepo=None,
            pkgs=None, sources=None, **kwargs):
    return __proxy__['ssh_sample.package_install'](name, **kwargs)


def remove(name=None, pkgs=None, **kwargs):
    return __proxy__['ssh_sample.package_remove'](name)
