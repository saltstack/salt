# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains for ESXi hosts.

., versionadded:: 2015.8.4

'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
from salt.exceptions import SaltSystemExit
import salt.utils
import salt.modules.vsphere

__proxyenabled__ = ['esxi']
__virtualname__ = 'esxi'

log = logging.getLogger(__file__)

GRAINS_CACHE = {}


def __virtual__():

    try:
        if salt.utils.is_proxy() and __opts__['proxy']['proxytype'] == 'esxi':
            return __virtualname__
    except KeyError:
        pass

    return False


def esxi():
    return _grains()


def kernel():
    return {'kernel': 'proxy'}


def os():
    if not GRAINS_CACHE:
        GRAINS_CACHE.update(_grains())

    try:
        return {'os': GRAINS_CACHE.get('fullName')}
    except AttributeError:
        return {'os': 'Unknown'}


def os_family():
    return {'os_family': 'proxy'}


def _find_credentials(host):
    '''
    Cycle through all the possible credentials and return the first one that
    works.
    '''
    user_names = [__pillar__['proxy'].get('username', 'root')]
    passwords = __pillar__['proxy']['passwords']
    for user in user_names:
        for password in passwords:
            try:
                # Try to authenticate with the given user/password combination
                ret = salt.modules.vsphere.system_info(host=host,
                                                       username=user,
                                                       password=password)
            except SaltSystemExit:
                # If we can't authenticate, continue on to try the next password.
                continue
            # If we have data returned from above, we've successfully authenticated.
            if ret:
                return user, password
    # We've reached the end of the list without successfully authenticating.
    raise SaltSystemExit('Cannot complete login due to an incorrect user name or password.')


def _grains():
    '''
    Get the grains from the proxied device.
    '''
    try:
        host = __pillar__['proxy']['host']
        if host:
            username, password = _find_credentials(host)
            protocol = __pillar__['proxy'].get('protocol')
            port = __pillar__['proxy'].get('port')
            ret = salt.modules.vsphere.system_info(host=host,
                                                   username=username,
                                                   password=password,
                                                   protocol=protocol,
                                                   port=port)
            GRAINS_CACHE.update(ret)
    except KeyError:
        pass

    return GRAINS_CACHE
