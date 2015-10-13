# -*- coding: utf-8 -*-
'''
Proxy minion interface module for managing Dell FX2 chassis
'''
from __future__ import absolute_import

# Import python libs
import logging
import salt.utils
import salt.utils.http

# This must be present or the Salt loader won't load this module
__proxyenabled__ = ['fx2']


# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
GRAINS_CACHE = {}
DETAILS = {}

# Want logging!
log = logging.getLogger(__file__)


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    if not salt.utils.which('racadm'):
        log.critical('fx2 proxy minion needs "racadm" to be installed.')
        return False

    return True


def init(opts):
    '''
    Every proxy module needs an 'init', though you can
    just put a 'pass' here if it doesn't need to do anything.
    '''
    # Save the login details
    DETAILS['admin_username'] = opts['proxy']['admin_username']
    DETAILS['admin_password'] = opts['proxy']['admin_password']
    DETAILS['host'] = opts['proxy']['host']


def grains():
    '''
    Get the grains from the proxied device
    '''
    if not GRAINS_CACHE:
        r = __salt__['dracr.system_info'](host=DETAILS['host'],
                                          admin_username=DETAILS['admin_username'],
                                          admin_password=DETAILS['admin_password'])
        GRAINS_CACHE = r
    return GRAINS_CACHE


def grains_refresh():
    '''
    Refresh the grains from the proxied device
    '''
    GRAINS_CACHE = {}
    return grains()


def chconfig(cmd, *args, **kwargs):
    # Strip the __pub_ keys...is there a better way to do this?
    for k in kwargs.keys():
        if k.startswith('__pub_'):
            kwargs.pop(k)
    if 'dracr.'+cmd not in __salt__:
        return {'retcode': -1, 'message': 'dracr.' + cmd + ' is not available'}
    else:
        return __salt__['dracr.'+cmd](*args, **kwargs)


def ping():
    '''
    Is the REST server up?
    '''
    r = __salt__['dracr.system_info'](host=DETAILS['host'],
                                      admin_username=DETAILS['admin_username'],
                                      admin_password=DETAILS['admin_password'])
    if r.get('retcode', 0) == 1:
        return False
    else:
        return True
    try:
        return r['dict'].get('ret', False)
    except Exception:
        return False


def shutdown(opts):
    '''
    For this proxy shutdown is a no-op
    '''
    log.debug('fx2 proxy shutdown() called...')
