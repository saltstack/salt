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


def _grains():
    '''
    Get the grains from the proxied device
    '''
    r = salt.modules.dracr.system_info(host=__pillar__['proxy']['host'],
                                       admin_username=__pillar__['proxy']['admin_username'],
                                       admin_password=__pillar__['proxy']['admin_password'])

    if r.get('retcode', 0) == 0:
        GRAINS_CACHE = r
        username = __pillar__['proxy']['admin_username']
        password = __pillar__['proxy']['admin_password']
    else:
        r = salt.modules.dracr.system_info(host=__pillar__['proxy']['host'],
                                           admin_username=__pillar__['proxy']['fallback_admin_username'],
                                           admin_password=__pillar__['proxy']['fallback_admin_password'])
        if r.get('retcode', 0) == 0:
            GRAINS_CACHE = r
            username = __pillar__['proxy']['fallback_admin_username']
            password = __pillar__['proxy']['fallback_admin_password']
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
        return GRAINS_CACHE.get('Chassis Information').get('Chassis Location')
    except AttributeError:
        return "Unknown"


def os_family():
    return {'os_family': 'proxy'}


def os_data():
    return {'os_data': 'Unknown'}
