"""
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
"""

import copy
import datetime
import logging
import math
import sys

import salt.utils.dictupdate as dictupdate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger()


class GsiNotUpdatableError(Exception):
    """Raised when a global secondary index cannot be updated."""


def __virtual__():
    """
    Only load if boto_dynamodb is available.
    """
    if "boto_dynamodb.exists" in __salt__:
        return "boto_dynamodb"
    return (False, "boto_dynamodb module could not be loaded")


def present(
    name=None,
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
    backup_configs_from_pillars="boto_dynamodb_backup_configs",
):
    """
    Ensure the DynamoDB table exists. Table throughput can be updated after
    table creation.

    Global secondary indexes (GSIs) are managed with some exceptions:

    - If a GSI deletion is detected, a failure will occur (deletes should be
      done manually in the AWS console).

    - If multiple GSIs are added in a single Salt call, a failure will occur
      (boto supports one creation at a time). Note that this only applies after
      table creation; multiple GSIs can be created during table creation.

    - Updates to existing GSIs are limited to read/write capacity only
      (DynamoDB limitation).

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
        The global indexes you would like to create

    backup_configs_from_pillars
        Pillars to use to configure DataPipeline backups
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    if table_name:
        ret["warnings"] = [
            "boto_dynamodb.present: `table_name` is deprecated."
            " Please use `name` instead."
        ]
        ret["name"] = table_name
        name = table_name

    comments = []
    changes_old = {}
    changes_new = {}

    # Ensure DynamoDB table exists
    table_exists = __salt__["boto_dynamodb.exists"](name, region, key, keyid, profile)
    if not table_exists:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "DynamoDB table {} would be created.".format(name)
            return ret
        else:
            is_created = __salt__["boto_dynamodb.create_table"](
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
                global_indexes,
            )
            if not is_created:
                ret["result"] = False
                ret["comment"] = "Failed to create table {}".format(name)
                _add_changes(ret, changes_old, changes_new)
                return ret

            comments.append("DynamoDB table {} was successfully created".format(name))
            changes_new["table"] = name
            changes_new["read_capacity_units"] = read_capacity_units
            changes_new["write_capacity_units"] = write_capacity_units
            changes_new["hash_key"] = hash_key
            changes_new["hash_key_data_type"] = hash_key_data_type
            changes_new["range_key"] = range_key
            changes_new["range_key_data_type"] = range_key_data_type
            changes_new["local_indexes"] = local_indexes
            changes_new["global_indexes"] = global_indexes
    else:
        comments.append("DynamoDB table {} exists".format(name))

    # Ensure DynamoDB table provisioned throughput matches
    description = __salt__["boto_dynamodb.describe"](name, region, key, keyid, profile)
    provisioned_throughput = description.get("Table", {}).get(
        "ProvisionedThroughput", {}
    )
    current_write_capacity_units = provisioned_throughput.get("WriteCapacityUnits")
    current_read_capacity_units = provisioned_throughput.get("ReadCapacityUnits")
    throughput_matches = (
        current_write_capacity_units == write_capacity_units
        and current_read_capacity_units == read_capacity_units
    )
    if not throughput_matches:
        if __opts__["test"]:
            ret["result"] = None
            comments.append("DynamoDB table {} is set to be updated.".format(name))
        else:
            is_updated = __salt__["boto_dynamodb.update"](
                name,
                throughput={
                    "read": read_capacity_units,
                    "write": write_capacity_units,
                },
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if not is_updated:
                ret["result"] = False
                ret["comment"] = "Failed to update table {}".format(name)
                _add_changes(ret, changes_old, changes_new)
                return ret

            comments.append("DynamoDB table {} was successfully updated".format(name))
            changes_old["read_capacity_units"] = (current_read_capacity_units,)
            changes_old["write_capacity_units"] = (current_write_capacity_units,)
            changes_new["read_capacity_units"] = (read_capacity_units,)
            changes_new["write_capacity_units"] = (write_capacity_units,)
    else:
        comments.append("DynamoDB table {} throughput matches".format(name))

    provisioned_indexes = description.get("Table", {}).get("GlobalSecondaryIndexes", [])

    _ret = _global_indexes_present(
        provisioned_indexes,
        global_indexes,
        changes_old,
        changes_new,
        comments,
        name,
        region,
        key,
        keyid,
        profile,
    )
    if not _ret["result"]:
        comments.append(_ret["comment"])
        ret["result"] = _ret["result"]
        if ret["result"] is False:
            ret["comment"] = ",\n".join(comments)
            _add_changes(ret, changes_old, changes_new)
            return ret

    _ret = _alarms_present(
        name,
        alarms,
        alarms_from_pillar,
        write_capacity_units,
        read_capacity_units,
        region,
        key,
        keyid,
        profile,
    )
    ret["changes"] = dictupdate.update(ret["changes"], _ret["changes"])
    comments.append(_ret["comment"])
    if not _ret["result"]:
        ret["result"] = _ret["result"]
        if ret["result"] is False:
            ret["comment"] = ",\n".join(comments)
            _add_changes(ret, changes_old, changes_new)
            return ret

    # Ensure backup datapipeline is present
    datapipeline_configs = copy.deepcopy(
        __salt__["pillar.get"](backup_configs_from_pillars, [])
    )
    for config in datapipeline_configs:
        datapipeline_ret = _ensure_backup_datapipeline_present(
            name=name,
            schedule_name=config["name"],
            period=config["period"],
            utc_hour=config["utc_hour"],
            s3_base_location=config["s3_base_location"],
        )
        # Add comments and changes if successful changes were made (True for live mode,
        # None for test mode).
        if datapipeline_ret["result"] in [True, None]:
            ret["result"] = datapipeline_ret["result"]
            comments.append(datapipeline_ret["comment"])
            if datapipeline_ret.get("changes"):
                ret["changes"]["backup_datapipeline_{}".format(config["name"])] = (
                    datapipeline_ret.get("changes"),
                )
        else:
            ret["comment"] = ",\n".join([ret["comment"], datapipeline_ret["comment"]])
            _add_changes(ret, changes_old, changes_new)
            return ret

    ret["comment"] = ",\n".join(comments)
    _add_changes(ret, changes_old, changes_new)
    return ret


def _add_changes(ret, changes_old, changes_new):
    if changes_old:
        ret["changes"]["old"] = changes_old
    if changes_new:
        ret["changes"]["new"] = changes_new


def _global_indexes_present(
    provisioned_indexes,
    global_indexes,
    changes_old,
    changes_new,
    comments,
    name,
    region,
    key,
    keyid,
    profile,
):
    """Handles global secondary index for the table present state."""
    ret = {"result": True}
    if provisioned_indexes:
        provisioned_gsi_config = {
            index["IndexName"]: index for index in provisioned_indexes
        }
    else:
        provisioned_gsi_config = {}
    provisioned_index_names = set(provisioned_gsi_config.keys())

    # Map of index name to given Salt config for this run. This loop is complicated
    # because global_indexes is made up of OrderedDicts and lists.
    gsi_config = {}
    if global_indexes:
        for index in global_indexes:
            # Each index config is a key that maps to a list of OrderedDicts.
            index_config = next(iter(index.values()))
            index_name = None
            for entry in index_config:
                # Key by the name field in the index config.
                if entry.keys() == ["name"]:
                    index_name = next(iter(entry.values()))
            if not index_name:
                ret["result"] = False
                ret["comment"] = "Index name not found for table {}".format(name)
                return ret
            gsi_config[index_name] = index

    (
        existing_index_names,
        new_index_names,
        index_names_to_be_deleted,
    ) = _partition_index_names(provisioned_index_names, set(gsi_config.keys()))

    if index_names_to_be_deleted:
        ret["result"] = False
        ret["comment"] = (
            "Deletion of GSIs ({}) is not supported! Please do this "
            "manually in the AWS console.".format(", ".join(index_names_to_be_deleted))
        )
        return ret
    elif len(new_index_names) > 1:
        ret["result"] = False
        ret["comment"] = (
            "Creation of multiple GSIs ({}) is not supported due to API "
            "limitations. Please create them one at a time.".format(new_index_names)
        )
        return ret

    if new_index_names:
        # Given the length check above, new_index_names should have a single element here.
        index_name = next(iter(new_index_names))
        _add_global_secondary_index(
            ret,
            name,
            index_name,
            changes_old,
            changes_new,
            comments,
            gsi_config,
            region,
            key,
            keyid,
            profile,
        )
        if not ret["result"]:
            return ret

    if existing_index_names:
        _update_global_secondary_indexes(
            ret,
            changes_old,
            changes_new,
            comments,
            existing_index_names,
            provisioned_gsi_config,
            gsi_config,
            name,
            region,
            key,
            keyid,
            profile,
        )
        if not ret["result"]:
            return ret

    if "global_indexes" not in changes_old and "global_indexes" not in changes_new:
        comments.append("All global secondary indexes match")
    return ret


def _partition_index_names(provisioned_index_names, index_names):
    """Returns 3 disjoint sets of indexes: existing, to be created, and to be deleted."""
    existing_index_names = set()
    new_index_names = set()
    for name in index_names:
        if name in provisioned_index_names:
            existing_index_names.add(name)
        else:
            new_index_names.add(name)
    index_names_to_be_deleted = provisioned_index_names - existing_index_names
    return existing_index_names, new_index_names, index_names_to_be_deleted


def _add_global_secondary_index(
    ret,
    name,
    index_name,
    changes_old,
    changes_new,
    comments,
    gsi_config,
    region,
    key,
    keyid,
    profile,
):
    """Updates ret iff there was a failure or in test mode."""
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Dynamo table {} will have a GSI added: {}".format(
            name, index_name
        )
        return
    changes_new.setdefault("global_indexes", {})
    success = __salt__["boto_dynamodb.create_global_secondary_index"](
        name,
        __salt__["boto_dynamodb.extract_index"](
            gsi_config[index_name], global_index=True
        ),
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )

    if success:
        comments.append("Created GSI {}".format(index_name))
        changes_new["global_indexes"][index_name] = gsi_config[index_name]
    else:
        ret["result"] = False
        ret["comment"] = "Failed to create GSI {}".format(index_name)


def _update_global_secondary_indexes(
    ret,
    changes_old,
    changes_new,
    comments,
    existing_index_names,
    provisioned_gsi_config,
    gsi_config,
    name,
    region,
    key,
    keyid,
    profile,
):
    """Updates ret iff there was a failure or in test mode."""
    try:
        provisioned_throughputs, index_updates = _determine_gsi_updates(
            existing_index_names, provisioned_gsi_config, gsi_config
        )
    except GsiNotUpdatableError as e:
        ret["result"] = False
        ret["comment"] = str(e)
        return

    if index_updates:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Dynamo table {} will have GSIs updated: {}".format(
                name, ", ".join(index_updates.keys())
            )
            return
        changes_old.setdefault("global_indexes", {})
        changes_new.setdefault("global_indexes", {})
        success = __salt__["boto_dynamodb.update_global_secondary_index"](
            name,
            index_updates,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )

        if success:
            comments.append(
                "Updated GSIs with new throughputs {}".format(index_updates)
            )
            for index_name in index_updates:
                changes_old["global_indexes"][index_name] = provisioned_throughputs[
                    index_name
                ]
                changes_new["global_indexes"][index_name] = index_updates[index_name]
        else:
            ret["result"] = False
            ret["comment"] = "Failed to update GSI throughputs {}".format(index_updates)


def _determine_gsi_updates(existing_index_names, provisioned_gsi_config, gsi_config):
    # index name -> {'read': <read throughput>, 'write': <write throughput>}
    provisioned_throughputs = {}
    index_updates = {}
    for index_name in existing_index_names:
        current_config = provisioned_gsi_config[index_name]
        new_config = __salt__["boto_dynamodb.extract_index"](
            gsi_config[index_name], global_index=True
        ).schema()

        # The provisioned config will have more fields than the new config, so only consider
        # fields in new_config.
        for key in new_config:
            if key in current_config and key != "ProvisionedThroughput":
                new_value = new_config[key]
                current_value = current_config[key]
                # This is a special case since the Projection value can contain a list (not
                # correctly comparable with == as order doesn't matter).
                if key == "Projection":
                    if new_value["ProjectionType"] != current_value["ProjectionType"]:
                        raise GsiNotUpdatableError("GSI projection types do not match")
                    elif set(new_value.get("NonKeyAttributes", [])) != set(
                        current_value.get("NonKeyAttributes", [])
                    ):
                        raise GsiNotUpdatableError(
                            "NonKeyAttributes do not match for GSI projection"
                        )
                elif new_value != current_value:
                    raise GsiNotUpdatableError(
                        "GSI property {} cannot be updated for index {}".format(
                            key, index_name
                        )
                    )

        current_throughput = current_config.get("ProvisionedThroughput")
        current_read = current_throughput.get("ReadCapacityUnits")
        current_write = current_throughput.get("WriteCapacityUnits")
        provisioned_throughputs[index_name] = {
            "read": current_read,
            "write": current_write,
        }
        new_throughput = new_config.get("ProvisionedThroughput")
        new_read = new_throughput.get("ReadCapacityUnits")
        new_write = new_throughput.get("WriteCapacityUnits")
        if current_read != new_read or current_write != new_write:
            index_updates[index_name] = {"read": new_read, "write": new_write}

    return provisioned_throughputs, index_updates


def _alarms_present(
    name,
    alarms,
    alarms_from_pillar,
    write_capacity_units,
    read_capacity_units,
    region,
    key,
    keyid,
    profile,
):
    """helper method for present.  ensure that cloudwatch_alarms are set"""
    # load data from alarms_from_pillar
    tmp = copy.deepcopy(__salt__["config.option"](alarms_from_pillar, {}))
    # merge with data from alarms
    if alarms:
        tmp = dictupdate.update(tmp, alarms)
    # set alarms, using boto_cloudwatch_alarm.present
    merged_return_value = {"name": name, "result": True, "comment": "", "changes": {}}
    for _, info in tmp.items():
        # add dynamodb table to name and description
        info["name"] = name + " " + info["name"]
        info["attributes"]["description"] = (
            name + " " + info["attributes"]["description"]
        )
        # add dimension attribute
        info["attributes"]["dimensions"] = {"TableName": [name]}
        if (
            info["attributes"]["metric"] == "ConsumedWriteCapacityUnits"
            and "threshold" not in info["attributes"]
        ):
            info["attributes"]["threshold"] = math.ceil(
                write_capacity_units * info["attributes"]["threshold_percent"]
            )
            del info["attributes"]["threshold_percent"]
            # the write_capacity_units is given in unit / second. So we need
            # to multiply by the period to get the proper threshold.
            # http://docs.aws.amazon.com/amazondynamodb/latest/developerguide/MonitoringDynamoDB.html
            info["attributes"]["threshold"] *= info["attributes"]["period"]
        if (
            info["attributes"]["metric"] == "ConsumedReadCapacityUnits"
            and "threshold" not in info["attributes"]
        ):
            info["attributes"]["threshold"] = math.ceil(
                read_capacity_units * info["attributes"]["threshold_percent"]
            )
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
        results = __states__["boto_cloudwatch_alarm.present"](**kwargs)
        if not results["result"]:
            merged_return_value["result"] = results["result"]
        if results.get("changes", {}) != {}:
            merged_return_value["changes"][info["name"]] = results["changes"]
        if "comment" in results:
            merged_return_value["comment"] += results["comment"]
    return merged_return_value


def _ensure_backup_datapipeline_present(
    name, schedule_name, period, utc_hour, s3_base_location
):

    kwargs = {
        "name": "{}-{}-backup".format(name, schedule_name),
        "pipeline_objects": {
            "DefaultSchedule": {
                "name": schedule_name,
                "fields": {
                    "period": period,
                    "type": "Schedule",
                    "startDateTime": _next_datetime_with_utc_hour(
                        name, utc_hour
                    ).isoformat(),
                },
            },
        },
        "parameter_values": {
            "myDDBTableName": name,
            "myOutputS3Loc": "{}/{}/".format(s3_base_location, name),
        },
    }
    return __states__["boto_datapipeline.present"](**kwargs)


def _get_deterministic_value_for_table_name(table_name, max_value):
    """
    For a given table_name, returns hash of the table_name limited by max_value.
    """
    return hash(table_name) % max_value


def _next_datetime_with_utc_hour(table_name, utc_hour):
    """
    Datapipeline API is throttling us, as all the pipelines are started at the same time.
    We would like to uniformly distribute the startTime over a 60 minute window.

    Return the next future utc datetime where
        hour == utc_hour
        minute = A value between 0-59 (depending on table name)
        second = A value between 0-59 (depending on table name)
    """
    today = datetime.date.today()

    # The minute and second values generated are deterministic, as we do not want
    # pipeline definition to change for every run.
    start_date_time = datetime.datetime(
        year=today.year,
        month=today.month,
        day=today.day,
        hour=utc_hour,
        minute=_get_deterministic_value_for_table_name(table_name, 60),
        second=_get_deterministic_value_for_table_name(table_name, 60),
    )

    if start_date_time < datetime.datetime.utcnow():
        one_day = datetime.timedelta(days=1)
        start_date_time += one_day

    return start_date_time


def absent(name, region=None, key=None, keyid=None, profile=None):
    """
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
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    exists = __salt__["boto_dynamodb.exists"](name, region, key, keyid, profile)
    if not exists:
        ret["comment"] = "DynamoDB table {} does not exist".format(name)
        return ret

    if __opts__["test"]:
        ret["comment"] = "DynamoDB table {} is set to be deleted".format(name)
        ret["result"] = None
        return ret

    is_deleted = __salt__["boto_dynamodb.delete"](name, region, key, keyid, profile)
    if is_deleted:
        ret["comment"] = "Deleted DynamoDB table {}".format(name)
        ret["changes"].setdefault("old", "Table {} exists".format(name))
        ret["changes"].setdefault("new", "Table {} deleted".format(name))
    else:
        ret["comment"] = "Failed to delete DynamoDB table {}".format(name)
        ret["result"] = False
    return ret
