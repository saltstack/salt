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

__proxyenabled__ = ['ssh_sample']
# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Only work on proxy
    '''
    if salt.utils.is_proxy():
        return __virtualname__
    return (False, 'THe ssh_service execution module failed to load: only works on a proxy minion.')


def list_pkgs(versions_as_list=False, **kwargs):
    return __proxy__['ssh_sample.package_list']()


def install(name=None, refresh=False, fromrepo=None,
            pkgs=None, sources=None, **kwargs):
    return __proxy__['ssh_sample.package_install'](name, **kwargs)


def remove(name=None, pkgs=None, **kwargs):
    return __proxy__['ssh_sample.package_remove'](name)
