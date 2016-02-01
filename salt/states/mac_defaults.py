# -*- coding: utf-8 -*-
'''
Writing/reading defaults from an OS X minion
=======================

'''

# Import python libs
from __future__ import absolute_import
import logging
import os

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)
__virtualname__ = 'macdefaults'


def __virtual__():
    '''
    Only work on Mac OS
    '''
    if salt.utils.is_darwin():
        return __virtualname__
    return False


def write(name, domain, value, type='string', user=None):
    '''
    Write a default to the system

    name
        The key of the given domain to write to

    domain
        The name of the domain to write to

    value
        The value to write to the given key

    type
        The type of value to be written, vaid types are string, data, int[eger],
        float, bool[ean], date, array, array-add, dict, dict-add

    user
        The user to write the defaults to


    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    def safe_cast(val, to_type, default=None):
        try:
            return to_type(val)
        except ValueError:
            return default

    current_value = __salt__['macdefaults.read'](domain, name, user)

    if (type == 'bool' or type == 'boolean') and (
                ((value is True or value is 'TRUE' or value is 'YES') and current_value == '1') or (
                        (value is False or value is 'FALSE' or value is 'NO') and current_value == '0')):
        ret['comment'] += '{0} {1} is already set to {2}'.format(domain, name, value)
    elif (type == 'int' or type == 'integer') and safe_cast(current_value, int) == safe_cast(value, int):
        ret['comment'] += '{0} {1} is already set to {2}'.format(domain, name, value)
    elif current_value == value:
        ret['comment'] += '{0} {1} is already set to {2}'.format(domain, name, value)
    else:
        out = __salt__['macdefaults.write'](domain, name, value, type, user)
        if out['retcode'] != 0:
            ret['result'] = False
            ret['comment'] = 'Failed to write default. {0}'.format(out['stdout'])
        else:
            ret['changes']['written'] = '{0} {1} is set to {2}'.format(domain, name, value)

    return ret