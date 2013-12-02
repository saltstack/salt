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
    HAS_JUNOS = True
except ImportError:
    HAS_JUNOS = False


# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'junos'


def __virtual__():
    '''
    Not currently any restrictions for this module
    '''
    if HAS_JUNOS:
        return __virtualname__
    else:
        return False


def _get_conn(user=None, host=None, passwd=None):

    if 'juniper.conn.{0}.{1}'.format(user, host) in __context__:
        return __context__['juniper.conn.{0}.{1}'.format(user, host)]
    else:
        jdev = jnpr.junos.Device(user=user, host=host, password=passwd)
        jdev.open()
        jdev.bind(cu=jnpr.junos.utils.Config)
        __context__['juniper.conn.{0}.{1}'.format(user, host)] = jdev
        __context__['juniper.facts.{0}.{1}'.format(user, host)] = jdev.facts

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

        single_ret['host-name'] = conn.facts['hostname']
        single_ret['model'] = conn.facts['model']
        single_ret['software-version'] = conn.facts['version']

        ret[hkey] = single_ret

    return ret


def inventory(tgt=None, user=None, host=None, passwd=None):

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

        single_ret['host-name'] = \
            __context__['juniper.facts.{0}.{1}'.format(hkey['user'], hkey['host'])]['host-name']
        single_ret['model'] = inv.find('chassis/description').text
        single_ret['serial-number'] = inv.find('chassis/serial-number').text
        single_ret['host-name'] = inv.find('chassis/host-name').text

        ret[hkey] = single_ret

    return ret


def facts_refresh(tgt=None, user=None, host=None, passwd=None):

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
        conn = _get_conn(user=user, host=host, passwd=passwd)
        conn.facts_refresh()

        __context__['juniper.facts.{0}.{1}'.format(user, host)] = conn.facts

        single_ret = dict()

        single_ret['facts'] = facts
        ret['host'] = single_ret

    return ret


# TODO add roster support
def set_hostname(hostname=None, user=None, host=None, passwd=None, commit=True):

    conn = _get_conn(user=user, host=host, passwd=passwd)
    ret = dict()
    # Added to recent versions of JunOs
    # Use text format instead
    set_string = 'set system host-name {}'.format(hostname)

    conn.cu.load(set_string, format='set')
    if commit:
        single['out'] = commit(user=user, host=host, passwd=passwd)
        if single['out']:
            single['message'] = 'Commit successful'
        else:
            single['message'] = 'Commit failed'
    else:
        single['out'] = True
        single['message'] = 'set system host-name {} is queued'.format(hostname)

    return ret


def commit(tgt=None, user=None, host=None, passwd=None):

    hosts = dict()
    ret = dict()

    if tgt:
        hosts = _roster(tgt)
    else:
        hosts[host] = {'id': host,
                       'host': host,
                       'user': user,
                       'passwd': passwd}

    for hkey in hosts:
        single_ret = dict()
        conn = _get_conn(user=hkey['user'], host=hkey['host'], passwd=hkey['passwd'])

        commit_ok = conn.cu.commit_check()
        if commit_ok:
            try:
                conn.cu.commit(confirm=True)
                single_ret['out'] = True
                single_ret['message'] = 'Commit Successful.'
            except EzNcException as e:
                single_ret['out'] = False
                single_ret['message'] = 'Pre-commit check succeeded but actual commit failed with "{}"'.format(e.message)
        else:
            single_ret['out'] = False
            single_ret['message'] = 'Pre-commit check failed.'

        ret['hkey'] = single_ret

    return ret


def rollback(tgt=None, user=None, host=None, passwd=None):

    hosts = dict()
    ret = dict()

    if tgt:
        hosts = _roster(tgt)
    else:
        hosts[host] = {'id': host,
                       'host': host,
                       'user': user,
                       'passwd': passwd}

    for hkey in hosts:
        single_ret = dict()
        conn = _get_conn(user=hkey['user'], host=hkey['host'], passwd=hkey['passwd'])

        single_ret['out'] = conn.cu.rollback(0)
        if single_ret['out']:
            single_ret['message'] = 'Rollback successful'
        else:
            single_ret['message'] = 'Rollback failed'

        ret['hkey'] = single_ret

    return ret


def diff(tgt=None, user=None, host=None, passwd=None):

    hosts = dict()
    ret = dict()

    if tgt:
        hosts = _roster(tgt)
    else:
        hosts[host] = {'id': host,
                       'host': host,
                       'user': user,
                       'passwd': passwd}

    for hkey in hosts:
        single_ret = dict()
        conn = _get_conn(user=hkey['user'], host=hkey['host'], passwd=hkey['passwd'])
        single_ret = dict()
        single_ret['out'] = True
        single_ret['message'] = conn.cu.diff()

        ret['hkey'] = single_ret

    return ret

