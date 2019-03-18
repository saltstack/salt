# -*- coding: utf-8 -*-
'''
Management of Influxdb retention policies
=========================================

.. versionadded:: 2017.7.0

(compatible with InfluxDB version 0.9+)
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    '''
    Only load if the influxdb module is available
    '''
    if 'influxdb.db_exists' in __salt__:
        return 'influxdb_retention_policy'
    return False


def present(name, database, duration="7d",
            replication=1, default=False,
            **client_args):
    '''
    Ensure that given retention policy is present.

    name
        Name of the retention policy to create.

    database
        Database to create retention policy on.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'retention policy {0} is already present'.format(name)}

    if not __salt__['influxdb.retention_policy_exists'](name=name,
                                                        database=database,
                                                        **client_args):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ' {0} is absent and will be created'\
                .format(name)
            return ret
        if __salt__['influxdb.create_retention_policy'](
            database, name,
            duration, replication, default, **client_args
        ):
            ret['comment'] = 'retention policy {0} has been created'\
                .format(name)
            ret['changes'][name] = 'Present'
            return ret
        else:
            ret['comment'] = 'Failed to create retention policy {0}'\
                .format(name)
            ret['result'] = False
            return ret

    return ret


def absent(name, database, **client_args):
    '''
    Ensure that given retention policy is absent.

    name
        Name of the retention policy to remove.

    database
        Name of the database that the retention policy was defined on.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'retention policy {0} is not present'.format(name)}

    if __salt__['influxdb.retention_policy_exists'](database, name, **client_args):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = (
                'retention policy {0} is present and needs to be removed'
            ).format(name)
            return ret
        if __salt__['influxdb.drop_retention_policy'](database, name, **client_args):
            ret['comment'] = 'retention policy {0} has been removed'\
                .format(name)
            ret['changes'][name] = 'Absent'
            return ret
        else:
            ret['comment'] = 'Failed to remove retention policy {0}'\
               .format(name)
            ret['result'] = False
            return ret

    return ret
