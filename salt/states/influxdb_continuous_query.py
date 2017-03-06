# -*- coding: utf-8 -*-
'''
Management of Influxdb continuous queries
=========================================

.. versionadded:: Nitrogen

(compatible with InfluxDB version 0.9+)
'''


def __virtual__():
    '''
    Only load if the influxdb module is available
    '''
    if 'influxdb.db_exists' in __salt__:
        return 'influxdb_continuous_query'
    return False


def present(name, database, query, resample_time=None, coverage_period=None, **client_args):
    '''
    Ensure that given continuous query is present.

    name
        Name of the continuous query to create.

    database
        Database to create continuous query on.

    query
        The query content

    resample_time : None
        Duration between continuous query resampling.

    coverage_period : None
        Duration specifying time period per sample.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'continuous query {0} is already present'.format(name)}

    if not __salt__['influxdb.continuous_query_exists'](name=name,
                                                        database=database,
                                                        **client_args):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ' {0} is absent and will be created'\
                .format(name)
            return ret
        if __salt__['influxdb.create_continuous_query'](
            database, name, query, resample_time, coverage_period
        ):
            ret['comment'] = 'continuous query {0} has been created'\
                .format(name)
            ret['changes'][name] = 'Present'
            return ret
        else:
            ret['comment'] = 'Failed to create continuous query {0}'\
                .format(name)
            ret['result'] = False
            return ret

    return ret


def absent(name, database, **client_args):
    '''
    Ensure that given continuous query is absent.

    name
        Name of the continuous query to remove.

    database
        Name of the database that the continuous query was defined on.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'continuous query {0} is not present'.format(name)}

    if __salt__['influxdb.continuous_query_exists'](database, name, **client_args):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = (
                'continuous query {0} is present and needs to be removed'
            ).format(name)
            return ret
        if __salt__['influxdb.drop_continuous_query'](database, name, **client_args):
            ret['comment'] = 'continuous query {0} has been removed'\
                .format(name)
            ret['changes'][name] = 'Absent'
            return ret
        else:
            ret['comment'] = 'Failed to remove continuous query {0}'\
               .format(name)
            ret['result'] = False
            return ret

    return ret
