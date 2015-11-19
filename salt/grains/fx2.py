# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains for Dell FX2 chassis.
The challenge is that most of Salt isn't bootstrapped yet,
so we need to repeat a bunch of things that would normally happen
in proxy/fx2.py--just enough to get data from the chassis to include
in grains.
'''
from __future__ import absolute_import
import salt.utils
import logging
import salt.proxy.fx2
import salt.modules.cmdmod
import salt.modules.dracr

__proxyenabled__ = ['fx2']

__virtualname__ = 'fx2'

logger = logging.getLogger(__file__)


GRAINS_CACHE = {}


def __virtual__():
    if not salt.utils.is_proxy():
        return False
    else:
        return __virtualname__


def _find_credentials():
    '''
    Cycle through all the possible credentials and return the first one that
    works
    '''
    usernames = []
    usernames.append(__pillar__['proxy'].get('admin_username', 'root'))
    if 'fallback_admin_username' in __pillar__.get('proxy'):
        usernames.append(__pillar__['proxy'].get('fallback_admin_username'))

    for u in usernames:
        for p in __pillar__['proxy']['passwords']:
            r = salt.modules.dracr.get_chassis_name(host=__pillar__['proxy']['host'],
                                                    admin_username=u,
                                                    admin_password=p)
            # Retcode will be present if the chassis_name call failed
            try:
                if r.get('retcode', None) is None:
                    return (u, p)
            except AttributeError:
                # Then the above was a string, and we can return the username
                # and password
                return (u, p)

    logger.debug('grains fx2._find_credentials found no valid credentials, using Dell default')
    return ('root', 'calvin')


def _grains():
    '''
    Get the grains from the proxied device
    '''
    (username, password) = _find_credentials()
    r = salt.modules.dracr.system_info(host=__pillar__['proxy']['host'],
                                       admin_username=username,
                                       admin_password=password)

    if r.get('retcode', 0) == 0:
        GRAINS_CACHE = r
    else:
        GRAINS_CACHE = {}

    GRAINS_CACHE.update(salt.modules.dracr.inventory(host=__pillar__['proxy']['host'],
                                                     admin_username=username,
                                                     admin_password=password))

    return GRAINS_CACHE


def fx2():
    return _grains()


def kernel():
    return {'kernel': 'proxy'}


def location():
    if not GRAINS_CACHE:
        GRAINS_CACHE.update(_grains())

    try:
        return {'location': GRAINS_CACHE.get('Chassis Information').get('Chassis Location')}
    except AttributeError:
        return {'location': 'Unknown'}


def os_family():
    return {'os_family': 'proxy'}


def os_data():
    return {'os_data': 'Unknown'}
