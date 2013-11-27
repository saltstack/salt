# -*- coding: utf-8 -*-
'''
Module for interfacing to Juniper switches

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
    HAS_JUNIPER = True
except ImportError:
    HAS_JUNIPER = False



# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'juniper'


def __virtual__():
    '''
    Not currently any restrictions for this module
    '''

    return __virtualname__


def _get_conn(user=None, host=None, passwd=None):

    if 'juniper.conn.{0}.{1}'.format(user, host) in __context__:
        return __context__['juniper.conn.{0}.{1}'.format(user, host)]
    else:
        jdev = jnpr.junos.Device(user=user, host=host, password=passwd)
        jdev.open()
        jdev.bind(cu=jnpr.junos.utils.Config)
        __context__['juniper.conn.{0}.{1}'.format(user, host)] = jdev

        return jdev


def _roster(tgt):

    roster = salt.roster.Roster(opts=__opts__).targets(tgt=tgt, tgt_type='glob')
    return roster


def version(tgt=None, user=None, host=None, passwd=None):

    ret = {}

    hosts = {}

    if tgt:
        hosts = _roster(tgt)
    else:
        hosts[host] = {'id': host,
                       'host': host,
                       'user': user,
                       'passwd': passwd}

    for hkey in hosts:
        h = hosts[hkey]
        single_ret = {}
        conn = _get_conn(user=h['user'],  host=h['host'], passwd=h['passwd'])

        raw_version = conn.cli('show version')

        matches = re.search('.*Hostname: (.*)\nModel: (.*)\n(.*)\n', raw_version)
        single_ret['host-name'] = matches.group(1)
        single_ret['model'] = matches.group(2)

        # Better to use version from facts
        single_ret['software-version'] = matches.group(3)

        ret[h['id']] = single_ret

    return ret


def inventory(user=None, host=None, passwd=None):

    conn = _get_conn(user=user, host=host, passwd=passwd)

    inv = conn.rpc.get_chassis_inventory()

    # Also use facts
    ret = {}
    ret['host-name'] = hostname
    ret['model'] = inv.find('chassis/description').text
    ret['serial-number'] = inv.find('chassis/serial-number').text
    ret['host-name'] = inv.find('chassis/host-name').text

    return ret

def facts(user=None, host=None, passwd=None):
    conn = _get_conn(user=user, host=host, passwd=passwd)
    facts = conn.facts

    ret = dict()

    ret['facts'] = facts

    return ret

def set_hostname(hostname=None, user=None, host=None, passwd=None, commit=True):

    conn = _get_conn(user=user, host=host, passwd=passwd)
    ret = dict()
    # Added to recent versions of JunOs
    # Use text format instead
    set_string = 'set system host-name {}'.format(hostname)

    conn.cu.load(set_string, format='set')
    if commit:
        ret['out'] = commit(user=user, host=host, passwd=passwd)
        if ret['out']:
            ret['message'] = 'Commit successful'
        else:
            ret['message'] = 'Commit failed'
    else:
        ret['out'] = True
        ret['message'] = 'set system host-name {} is queued'.format(hostname)

    return ret


def commit(user=None, host=None, passwd=None):

    conn = _get_conn(user=user, host=host, passwd=passwd)
    ret = dict()

    # Could use try/except block here
    commit_ok = conn.cu.commit_check()
    if commit_ok:
        conn.cu.commit(confirm=True)
        ret['out'] = True
        ret['message'] = 'Commit Successful.'
    else:
        ret['out'] = False
        ret['message'] = 'Pre-commit check failed.'

    return ret


def rollback(user=None, host=None, passwd=None):

    conn = _get_conn(user=user, host=host, passwd=passwd)

    ret = dict()

    # Rollback takes parameter
    result = conn.cu.rollback()
    ret['out'] = result
    if result:
        ret['message'] = 'Rollback successful.'
    else:
        ret['message'] = 'Rollback failed.'

    return ret

def diff(user=None, host=None, passwd=None):

    conn = _get_conn(user=user, host=host, passwd=passwd)

    ret = dict()
    ret['out'] = True
    ret['message'] = conn.cu.diff()
    return ret

