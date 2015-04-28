# -*- coding: utf-8 -*-
'''
Module for interfacing to Junos devices

ALPHA QUALITY code.

'''
from __future__ import absolute_import

# Import python libraries
import logging

# Juniper interface libraries
# https://github.com/jeremyschulman/py-junos-eznc


try:
    # pylint: disable=W0611
    import jnpr.junos
    import jnpr.junos.utils
    import jnpr.junos.cfg
    # pylint: enable=W0611
    HAS_JUNOS = True
except ImportError:
    HAS_JUNOS = False


# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'junos'

__proxyenabled__ = ['junos']


def __virtual__():
    '''
    We need the Junos adapter libraries for this
    module to work.  We also need a proxyobject object
    in the opts dictionary
    '''
    if HAS_JUNOS and 'proxy' in __opts__:
        return __virtualname__
    else:
        return False


def facts_refresh():
    '''
    Reload the facts dictionary from the device.  Usually only needed
    if the device configuration is changed by some other actor.
    '''

    return __opts__['proxyobject'].refresh


def set_hostname(hostname=None, commit_change=True):

    ret = dict()
    conn = __opts__['proxyobject']
    if hostname is None:
        ret['out'] = False
        return ret

    # Added to recent versions of JunOs
    # Use text format instead
    set_string = 'set system host-name {0}'.format(hostname)

    conn.cu.load(set_string, format='set')
    if commit_change:
        return commit()
    else:
        ret['out'] = True
        ret['msg'] = 'set system host-name {0} is queued'.format(hostname)

    return ret


def commit():

    conn = __opts__['proxyobject']

    ret = {}
    commit_ok = conn.cu.commit_check()
    if commit_ok:
        try:
            conn.cu.commit(confirm=True)
            ret['out'] = True
            ret['message'] = 'Commit Successful.'
        except Exception as exception:
            ret['out'] = False
            ret['message'] = 'Pre-commit check succeeded but actual commit failed with "{0}"'.format(exception)
    else:
        ret['out'] = False
        ret['message'] = 'Pre-commit check failed.'

    return ret


def rollback():
    conn = __opts__['proxyobject']
    ret = dict()

    ret['out'] = conn.cu.rollback(0)

    if ret['out']:
        ret['message'] = 'Rollback successful'
    else:
        ret['message'] = 'Rollback failed'

    return ret


def diff():

    ret = dict()
    conn = __opts__['proxyobject']
    ret['out'] = True
    ret['message'] = conn.cu.diff()

    return ret


def ping():

    ret = dict()
    conn = __opts__['proxyobject']
    ret['message'] = conn.cli('show system uptime')
    ret['out'] = True
