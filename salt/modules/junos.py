# -*- coding: utf-8 -*-
'''
Module for interfacing to Junos devices

ALPHA QUALITY code.

'''

# Import python libraries
import re
import logging

# Salt libraries
import salt.roster

# Juniper interface libraries
# https://github.com/jeremyschulman/py-junos-eznc


try:
    import jnpr.junos
    import jnpr.junos.utils
    import jnpr.junos.cfg
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
    module to work.  We also need a proxyconn object
    in the opts dictionary
    '''
    if HAS_JUNOS and 'proxyconn' in __opts__:
        return __virtualname__
    else:
        return False


def facts_refresh():
    '''
    Reload the facts dictionary from the device.  Usually only needed
    if the device configuration is changed by some other actor.
    '''

    return __opts__['proxyconn'].refresh


def set_hostname(hostname=None, commit=True):

    ret = dict()
    conn = __opts__['proxyconn']
    if hostname is None:
        ret['out'] = False
        return ret

    # Added to recent versions of JunOs
    # Use text format instead
    set_string = 'set system host-name {}'.format(hostname)

    conn.cu.load(set_string, format='set')
    if commit:
        return commit()
    else:
        single['out'] = True
        single['message'] = 'set system host-name {} is queued'.format(hostname)

    return ret


def commit():

    conn = __opts__['proxyconn']

    commit_ok = conn.cu.commit_check()
    if commit_ok:
        try:
            conn.cu.commit(confirm=True)
            ret['out'] = True
            ret['message'] = 'Commit Successful.'
        except EzNcException as e:
            ret['out'] = False
            ret['message'] = 'Pre-commit check succeeded but actual commit failed with "{}"'.format(e.message)
    else:
        ret['out'] = False
        ret['message'] = 'Pre-commit check failed.'

    return ret


def rollback():
    conn = __opts__['proxyconn']
    ret = dict()

    ret['out'] = conn.cu.rollback(0)

    if ret['out']:
        ret['message'] = 'Rollback successful'
    else:
        ret['message'] = 'Rollback failed'

    return ret


def diff():

    ret = dict()
    conn = __opt__['proxyconn']
    ret['out'] = True
    ret['message'] = conn.cu.diff()

    return ret

def ping():

    ret = dict()
    conn = __opt__['proxyconn']
    ret['message'] = conn.cli('show system uptime')
    ret['out'] = True


