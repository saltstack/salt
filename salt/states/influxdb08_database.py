# -*- coding: utf-8 -*-
'''
Management of Influxdb 0.8 databases
====================================

(compatible with InfluxDB version 0.5-0.8)

.. versionadded:: 2014.7.0

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    '''
    Only load if the influxdb08 module is available
    '''
    if 'influxdb08.db_exists' in __salt__:
        return 'influxdb08_database'
    return False


def present(name, user=None, password=None, host=None, port=None):
    '''
    Ensure that the named database is present

    name
        The name of the database to create

    user
        The user to connect as (must be able to remove the database)

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check if database exists
    if not __salt__['influxdb08.db_exists'](name, user, password, host, port):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Database {0} is absent and needs to be created'\
                .format(name)
            return ret
        if __salt__['influxdb08.db_create'](name, user, password, host, port):
            ret['comment'] = 'Database {0} has been created'.format(name)
            ret['changes'][name] = 'Present'
            return ret
        else:
            ret['comment'] = 'Failed to create database {0}'.format(name)
            ret['result'] = False
            return ret

    # fallback
    ret['comment'] = 'Database {0} is already present, so cannot be created'\
        .format(name)
    return ret


def absent(name, user=None, password=None, host=None, port=None):
    '''
    Ensure that the named database is absent

    name
        The name of the database to remove

    user
        The user to connect as (must be able to remove the database)

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check if database exists and remove it
    if __salt__['influxdb08.db_exists'](name, user, password, host, port):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Database {0} is present and needs to be removed'\
                .format(name)
            return ret
        if __salt__['influxdb08.db_remove'](name, user, password, host, port):
            ret['comment'] = 'Database {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret
        else:
            ret['comment'] = 'Failed to remove database {0}'.format(name)
            ret['result'] = False
            return ret

    # fallback
    ret['comment'] = 'Database {0} is not present, so it cannot be removed'\
        .format(name)
    return ret
