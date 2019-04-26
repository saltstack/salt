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


def convert_duration(duration):
    '''
    Convert the a duration string into XXhYYmZZs format

    duration
        Duration to convert

    Returns: duration_string
        String representation of duration in XXhYYmZZs format
    '''

    # durations must be specified in days, weeks or hours

    if duration.endswith('h'):
        return duration + '0m0s'
    if duration.endswith('d'):
        return '{0}h0m0s'.format(int(duration.split('d')[0]) * 24)
    if duration.endswith('w'):
        return '{0}h0m0s'.format(int(duration.split('w')[0]) * 24 * 7)
    if duration == 'INF':
        return '0s'

    return duration


def present(name, database, duration="7d",
            replication=1, default=False,
            shard_duration="0s",
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
            duration, replication, default, shard_duration, **client_args
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

    else:
        current_policy = __salt__['influxdb.get_retention_policy'](database=database, name=name)
        update_policy = False
        if current_policy['duration'] != convert_duration(duration):
            update_policy = True
            ret['changes']['duration'] = "Retention changed from {0} to {1}.".format(current_policy['duration'], duration)

        if current_policy['replicaN'] != replication:
            update_policy = True
            ret['changes']['replication'] = "Replication changed from {0} to {1}.".format(current_policy['replicaN'], replication)

        if current_policy['default'] != default:
            update_policy = True
            ret['changes']['default'] = "Default changed from {0} to {1}.".format(current_policy['default'], default)

        if current_policy['shardGroupDuration'] != convert_duration(shard_duration):
            # do not trigger false positive when shard_duration is set to 0s:
            # in that case, shard_duration will be automatically computed based
            # the retention policy duration. See:
            # https://docs.influxdata.com/influxdb/v1.7/query_language/database_management/#shard-duration
            if not (shard_duration == '0s' and
                    current_policy['shardGroupDuration'] in (
                        '1h0m0s', '24h0m0s', '168h0m0s')):
                update_policy = True
                ret['changes']['shard_duration'] = "Shard duration changed from {0} to {1}.".format(current_policy['shardGroupDuration'], shard_duration)

        if update_policy:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = ' {0} is present and set to be changed'\
                    .format(name)
                return ret
            else:
                if __salt__['influxdb.alter_retention_policy'](
                    database, name, duration, replication, default,
                    shard_duration, **client_args
                ):
                    ret['comment'] = 'retention policy {0} has been changed'\
                        .format(name)
                    return ret
                else:
                    ret['comment'] = 'Failed to update retention policy {0}'\
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
