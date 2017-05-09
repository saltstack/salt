# -*- coding: utf-8 -*-
'''
Manage DynamoDB Tables
======================

.. versionadded:: 2015.5.0

Create and destroy DynamoDB tables. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit DynamoDB credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    keyid: GKTADJGHEIQSXMKKRBJ08H
    key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    region: us-east-1

It's also possible to specify ``key``, ``keyid`` and ``region`` via a
profile, either passed in as a dict, or as a string to pull from
pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure DynamoDB table does not exist:
      boto_dynamodb.absent:
        - table_name: new_table
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        - region: us-east-1

    Ensure DynamoDB table exists:
      boto_dynamodb.present:
        - table_name: new_table
        - read_capacity_units: 1
        - write_capacity_units: 2
        - hash_key: primary_id
        - hash_key_data_type: N
        - range_key: start_timestamp
        - range_key_data_type: N
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        - region: us-east-1
        - local_indexes:
            - index:
                - name: "primary_id_end_timestamp_index"
                - hash_key: primary_id
                - hash_key_data_type: N
                - range_key: end_timestamp
                - range_key_data_type: N
        - global_indexes:
            - index:
                - name: "name_end_timestamp_index"
                - hash_key: name
                - hash_key_data_type: S
                - range_key: end_timestamp
                - range_key_data_type: N
                - read_capacity_units: 3
                - write_capacity_units: 4

It's possible to specify cloudwatch alarms that will be setup along with the
DynamoDB table. Note the alarm name will be defined by the name attribute
provided, plus the DynamoDB resource name.

.. code-block:: yaml

    Ensure DynamoDB table exists:
      boto_dynamodb.present:
        - name: new_table
        - read_capacity_units: 1
        - write_capacity_units: 2
        - hash_key: primary_id
        - hash_key_data_type: N
        - range_key: start_timestamp
        - range_key_data_type: N
        - alarms:
             ConsumedWriteCapacityUnits:
                name: 'DynamoDB ConsumedWriteCapacityUnits **MANAGED BY SALT**'
                attributes:
                  metric: ConsumedWriteCapacityUnits
                  namespace: AWS/DynamoDB
                  statistic: Sum
                  comparison: '>='
                  # threshold_percent is used to calculate the actual threshold
                  # based on the provisioned capacity for the table.
                  threshold_percent: 0.75
                  period: 300
                  evaluation_periods: 2
                  unit: Count
                  description: 'DynamoDB ConsumedWriteCapacityUnits'
                  alarm_actions: [ 'arn:aws:sns:us-east-1:1234:my-alarm' ]
                  insufficient_data_actions: []
                  ok_actions: [ 'arn:aws:sns:us-east-1:1234:my-alarm' ]
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        - region: us-east-1

You can also use alarms from pillars, and override values from the pillar
alarms by setting overrides on the resource. Note that 'boto_dynamodb_alarms'
will be used as a default value for all resources, if defined and can be
used to ensure alarms are always set for a resource.

Setting the alarms in a pillar:

.. code-block:: yaml

    boto_dynamodb_alarms:
      ConsumedWriteCapacityUnits:
        name: 'DynamoDB ConsumedWriteCapacityUnits **MANAGED BY SALT**'
        attributes:
          metric: ConsumedWriteCapacityUnits
          namespace: AWS/DynamoDB
          statistic: Sum
          comparison: '>='
          # threshold_percent is used to calculate the actual threshold
          # based on the provisioned capacity for the table.
          threshold_percent: 0.75
          period: 300
          evaluation_periods: 2
          unit: Count
          description: 'DynamoDB ConsumedWriteCapacityUnits'
          alarm_actions: [ 'arn:aws:sns:us-east-1:1234:my-alarm' ]
          insufficient_data_actions: []
          ok_actions: [ 'arn:aws:sns:us-east-1:1234:my-alarm' ]

    Ensure DynamoDB table exists:
      boto_dynamodb.present:
        - name: new_table
        - read_capacity_units: 1
        - write_capacity_units: 2
        - hash_key: primary_id
        - hash_key_data_type: N
        - range_key: start_timestamp
        - range_key_data_type: N
        - alarms:
             ConsumedWriteCapacityUnits:
                attributes:
                  threshold_percent: 0.90
                  period: 900
'''
# Import Python libs
from __future__ import absolute_import
import datetime
import math
import sys
import logging
import copy

# Import salt libs
import salt.ext.six as six
import salt.utils.dictupdate as dictupdate

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    stream=sys.stdout
)
log = logging.getLogger()


def __virtual__():
    '''
    Only load if boto_dynamodb is available.
    '''
    ret = 'boto_dynamodb' if 'boto_dynamodb.exists' in __salt__ else False
    return ret


def present(name=None,
            table_name=None,
            region=None,
            key=None,
            keyid=None,
            profile=None,
            read_capacity_units=None,
            write_capacity_units=None,
            alarms=None,
            alarms_from_pillar="boto_dynamodb_alarms",
            hash_key=None,
            hash_key_data_type=None,
            range_key=None,
            range_key_data_type=None,
            local_indexes=None,
            global_indexes=None,
            backup_configs_from_pillars='boto_dynamodb_backup_configs'):
    '''
    Ensure the DynamoDB table exists.  Note: all properties of the table
    can only be set during table creation.  Adding or changing
    indexes or key schema cannot be done after table creation

    name
        Name of the DynamoDB table

    table_name
        Name of the DynamoDB table (deprecated)

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

    read_capacity_units
        The read throughput for this table

    write_capacity_units
        The write throughput for this table

    hash_key
        The name of the attribute that will be used as the hash key
        for this table

    hash_key_data_type
        The DynamoDB datatype of the hash key

    range_key
        The name of the attribute that will be used as the range key
        for this table

    range_key_data_type
        The DynamoDB datatype of the range key

    local_indexes
        The local indexes you would like to create

    global_indexes
        The local indexes you would like to create

    backup_configs_from_pillars
        Pillars to use to configure DataPipeline backups
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if table_name:
        ret['warnings'] = ['boto_dynamodb.present: `table_name` is deprecated.'
                           ' Please use `name` instead.']
        ret['name'] = table_name
        name = table_name

    comments = []
    changes_old = {}
    changes_new = {}

    # Ensure DynamoDB table exists
    table_exists = __salt__['boto_dynamodb.exists'](
        name,
        region,
        key,
        keyid,
        profile
    )
    if not table_exists:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'DynamoDB table {0} is set to be created.'.format(name)
            return ret

        is_created = __salt__['boto_dynamodb.create_table'](
            name,
            region,
            key,
            keyid,
            profile,
            read_capacity_units,
            write_capacity_units,
            hash_key,
            hash_key_data_type,
            range_key,
            range_key_data_type,
            local_indexes,
            global_indexes
        )
        if not is_created:
            ret['result'] = False
            ret['comment'] = 'Failed to create table {0}'.format(name)
            return ret

        comments.append('DynamoDB table {0} was successfully created'.format(name))
        changes_new['table'] = name
        changes_new['read_capacity_units'] = read_capacity_units
        changes_new['write_capacity_units'] = write_capacity_units
        changes_new['hash_key'] = hash_key
        changes_new['hash_key_data_type'] = hash_key_data_type
        changes_new['range_key'] = range_key
        changes_new['range_key_data_type'] = range_key_data_type
        changes_new['local_indexes'] = local_indexes
        changes_new['global_indexes'] = global_indexes
    else:
        comments.append('DynamoDB table {0} exists'.format(name))

    # Ensure DynamoDB table provisioned throughput matches
    description = __salt__['boto_dynamodb.describe'](
        name,
        region,
        key,
        keyid,
        profile
    )
    provisioned_throughput = description.get('Table', {}).get('ProvisionedThroughput', {})
    current_write_capacity_units = provisioned_throughput.get('WriteCapacityUnits')
    current_read_capacity_units = provisioned_throughput.get('ReadCapacityUnits')
    throughput_matches = (current_write_capacity_units == write_capacity_units and
                          current_read_capacity_units == read_capacity_units)
    if not throughput_matches:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'DynamoDB table {0} is set to be updated.'.format(name)
            return ret

        is_updated = __salt__['boto_dynamodb.update'](
            name,
            throughput={
                'read': read_capacity_units,
                'write': write_capacity_units,
            },
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not is_updated:
            ret['result'] = False
            ret['comment'] = 'Failed to update table {0}'.format(name)
            return ret

        comments.append('DynamoDB table {0} was successfully updated'.format(name))
        changes_old['read_capacity_units'] = current_read_capacity_units,
        changes_old['write_capacity_units'] = current_write_capacity_units,
        changes_new['read_capacity_units'] = read_capacity_units,
        changes_new['write_capacity_units'] = write_capacity_units,
    else:
        comments.append('DynamoDB table {0} throughput matches'.format(name))

    _ret = _alarms_present(name, alarms, alarms_from_pillar,
                           write_capacity_units, read_capacity_units,
                           region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret

    # Ensure backup datapipeline is present
    datapipeline_configs = copy.deepcopy(
        __salt__['pillar.get'](backup_configs_from_pillars, [])
    )
    for config in datapipeline_configs:
        datapipeline_ret = _ensure_backup_datapipeline_present(
            name=name,
            schedule_name=config['name'],
            period=config['period'],
            utc_hour=config['utc_hour'],
            s3_base_location=config['s3_base_location'],
        )
        if datapipeline_ret['result']:
            comments.append(datapipeline_ret['comment'])
            if datapipeline_ret.get('changes'):
                ret['changes']['backup_datapipeline_{0}'.format(config['name'])] = \
                    datapipeline_ret.get('changes'),
        else:
            ret['comment'] = datapipeline_ret['comment']
            return ret

    if changes_old:
        ret['changes']['old'] = changes_old
    if changes_new:
        ret['changes']['new'] = changes_new
    ret['comment'] = ',\n'.join(comments)
    return ret


def _alarms_present(name, alarms, alarms_from_pillar,
                    write_capacity_units, read_capacity_units,
                    region, key, keyid, profile):
    '''helper method for present.  ensure that cloudwatch_alarms are set'''
    # load data from alarms_from_pillar
    tmp = copy.deepcopy(
        __salt__['config.option'](alarms_from_pillar, {})
    )
    # merge with data from alarms
    if alarms:
        tmp = dictupdate.update(tmp, alarms)
    # set alarms, using boto_cloudwatch_alarm.present
    merged_return_value = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    for _, info in six.iteritems(tmp):
        # add dynamodb table to name and description
        info["name"] = name + " " + info["name"]
        info["attributes"]["description"] = name + " " + info["attributes"]["description"]
        # add dimension attribute
        info["attributes"]["dimensions"] = {"TableName": [name]}
        if info["attributes"]["metric"] == "ConsumedWriteCapacityUnits" \
           and "threshold" not in info["attributes"]:
            info["attributes"]["threshold"] = math.ceil(write_capacity_units * info["attributes"]["threshold_percent"])
            del info["attributes"]["threshold_percent"]
            # the write_capacity_units is given in unit / second. So we need
            # to multiply by the period to get the proper threshold.
            # http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/MonitoringDynamoDB.html
            info["attributes"]["threshold"] *= info["attributes"]["period"]
        if info["attributes"]["metric"] == "ConsumedReadCapacityUnits" \
           and "threshold" not in info["attributes"]:
            info["attributes"]["threshold"] = math.ceil(read_capacity_units * info["attributes"]["threshold_percent"])
            del info["attributes"]["threshold_percent"]
            # the read_capacity_units is given in unit / second. So we need
            # to multiply by the period to get the proper threshold.
            # http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/MonitoringDynamoDB.html
            info["attributes"]["threshold"] *= info["attributes"]["period"]
        # set alarm
        kwargs = {
            "name": info["name"],
            "attributes": info["attributes"],
            "region": region,
            "key": key,
            "keyid": keyid,
            "profile": profile,
        }
        results = __states__['boto_cloudwatch_alarm.present'](**kwargs)
        if not results["result"]:
            merged_return_value["result"] = results["result"]
        if results.get("changes", {}) != {}:
            merged_return_value["changes"][info["name"]] = results["changes"]
        if "comment" in results:
            merged_return_value["comment"] += results["comment"]
    return merged_return_value


def _ensure_backup_datapipeline_present(name, schedule_name, period,
                                        utc_hour, s3_base_location):

    kwargs = {
        'name': '{0}-{1}-backup'.format(name, schedule_name),
        'pipeline_objects': {
            'DefaultSchedule': {
                'name': schedule_name,
                'fields': {
                    'period': period,
                    'type': 'Schedule',
                    'startDateTime': _next_datetime_with_utc_hour(utc_hour).isoformat(),
                }
            },
        },
        'parameter_values': {
            'myDDBTableName': name,
            'myOutputS3Loc': '{0}/{1}/'.format(s3_base_location, name),
        }
    }
    return __states__['boto_datapipeline.present'](**kwargs)


def _next_datetime_with_utc_hour(utc_hour):
    '''Return the next future utc datetime where hour == utc_hour'''
    today = datetime.date.today()
    start_date_time = datetime.datetime(
        year=today.year,
        month=today.month,
        day=today.day,
        hour=utc_hour,
    )

    if start_date_time < datetime.datetime.utcnow():
        one_day = datetime.timedelta(days=1)
        start_date_time += one_day

    return start_date_time


def absent(name,
           region=None,
           key=None,
           keyid=None,
           profile=None):
    '''
    Ensure the DynamoDB table does not exist.

    name
        Name of the DynamoDB table.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto_dynamodb.exists'](
        name,
        region,
        key,
        keyid,
        profile
    )
    if not exists:
        ret['comment'] = 'DynamoDB table {0} does not exist'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'DynamoDB table {0} is set to be deleted \
                         '.format(name)
        ret['result'] = None
        return ret

    is_deleted = __salt__['boto_dynamodb.delete'](name, region, key, keyid, profile)
    if is_deleted:
        ret['comment'] = 'Deleted DynamoDB table {0}'.format(name)
        ret['changes'].setdefault('old', 'Table {0} exists'.format(name))
        ret['changes'].setdefault('new', 'Table {0} deleted'.format(name))
    else:
        ret['comment'] = 'Failed to delete DynamoDB table {0} \
                         '.format(name)
        ret['result'] = False
    return ret
