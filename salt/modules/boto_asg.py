"""
Connection module for Amazon Autoscale Groups

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit autoscale credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        asg.keyid: GKTADJGHEIQSXMKKRBJ08H
        asg.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        asg.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
:depends: boto3
"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602


import datetime
import email.mime.multipart
import logging
import sys
import time

import salt.utils.compat
import salt.utils.json
import salt.utils.odict as odict
import salt.utils.versions

log = logging.getLogger(__name__)
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


try:
    import boto
    import boto.ec2
    import boto.ec2.instance
    import boto.ec2.blockdevicemapping as blockdevicemapping
    import boto.ec2.autoscale as autoscale

    logging.getLogger("boto").setLevel(logging.CRITICAL)
    import boto3  # pylint: disable=unused-import
    from botocore.exceptions import ClientError

    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    has_boto_reqs = salt.utils.versions.check_boto_reqs()
    if has_boto_reqs is True:
        __utils__["boto.assign_funcs"](
            __name__, "asg", module="ec2.autoscale", pack=__salt__
        )
        setattr(
            sys.modules[__name__],
            "_get_ec2_conn",
            __utils__["boto.get_connection_func"]("ec2"),
        )
    return has_boto_reqs


def __init__(opts):
    if HAS_BOTO:
        __utils__["boto3.assign_funcs"](
            __name__, "autoscaling", get_conn_funcname="_get_conn_autoscaling_boto3"
        )


def exists(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if an autoscale group exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.exists myasg region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30
    while True:
        try:
            _conn = conn.get_all_groups(names=[name])
            if _conn:
                return True
            else:
                msg = "The autoscale group does not exist in region {}".format(region)
                log.debug(msg)
                return False
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            return False


def get_config(name, region=None, key=None, keyid=None, profile=None):
    """
    Get the configuration for an autoscale group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.get_config myasg region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30
    while True:
        try:
            asg = conn.get_all_groups(names=[name])
            if asg:
                asg = asg[0]
            else:
                return {}
            ret = odict.OrderedDict()
            attrs = [
                "name",
                "availability_zones",
                "default_cooldown",
                "desired_capacity",
                "health_check_period",
                "health_check_type",
                "launch_config_name",
                "load_balancers",
                "max_size",
                "min_size",
                "placement_group",
                "vpc_zone_identifier",
                "tags",
                "termination_policies",
                "suspended_processes",
            ]
            for attr in attrs:
                # Tags are objects, so we need to turn them into dicts.
                if attr == "tags":
                    _tags = []
                    for tag in asg.tags:
                        _tag = odict.OrderedDict()
                        _tag["key"] = tag.key
                        _tag["value"] = tag.value
                        _tag["propagate_at_launch"] = tag.propagate_at_launch
                        _tags.append(_tag)
                    ret["tags"] = _tags
                # Boto accepts a string or list as input for vpc_zone_identifier,
                # but always returns a comma separated list. We require lists in
                # states.
                elif attr == "vpc_zone_identifier":
                    ret[attr] = getattr(asg, attr).split(",")
                # convert SuspendedProcess objects to names
                elif attr == "suspended_processes":
                    suspended_processes = getattr(asg, attr)
                    ret[attr] = sorted([x.process_name for x in suspended_processes])
                else:
                    ret[attr] = getattr(asg, attr)
            # scaling policies
            policies = conn.get_all_policies(as_group=name)
            ret["scaling_policies"] = []
            for policy in policies:
                ret["scaling_policies"].append(
                    dict(
                        [
                            ("name", policy.name),
                            ("adjustment_type", policy.adjustment_type),
                            ("scaling_adjustment", policy.scaling_adjustment),
                            ("min_adjustment_step", policy.min_adjustment_step),
                            ("cooldown", policy.cooldown),
                        ]
                    )
                )
            # scheduled actions
            actions = conn.get_all_scheduled_actions(as_group=name)
            ret["scheduled_actions"] = {}
            for action in actions:
                end_time = None
                if action.end_time:
                    end_time = action.end_time.isoformat()
                ret["scheduled_actions"][action.name] = dict(
                    [
                        ("min_size", action.min_size),
                        ("max_size", action.max_size),
                        # AWS bug
                        ("desired_capacity", int(action.desired_capacity)),
                        ("start_time", action.start_time.isoformat()),
                        ("end_time", end_time),
                        ("recurrence", action.recurrence),
                    ]
                )
            return ret
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            return {}


def create(
    name,
    launch_config_name,
    availability_zones,
    min_size,
    max_size,
    desired_capacity=None,
    load_balancers=None,
    default_cooldown=None,
    health_check_type=None,
    health_check_period=None,
    placement_group=None,
    vpc_zone_identifier=None,
    tags=None,
    termination_policies=None,
    suspended_processes=None,
    scaling_policies=None,
    scheduled_actions=None,
    region=None,
    notification_arn=None,
    notification_types=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create an autoscale group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.create myasg mylc '["us-east-1a", "us-east-1e"]' 1 10 load_balancers='["myelb", "myelb2"]' tags='[{"key": "Name", value="myasg", "propagate_at_launch": True}]'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if isinstance(availability_zones, str):
        availability_zones = salt.utils.json.loads(availability_zones)
    if isinstance(load_balancers, str):
        load_balancers = salt.utils.json.loads(load_balancers)
    if isinstance(vpc_zone_identifier, str):
        vpc_zone_identifier = salt.utils.json.loads(vpc_zone_identifier)
    if isinstance(tags, str):
        tags = salt.utils.json.loads(tags)
    # Make a list of tag objects from the dict.
    _tags = []
    if tags:
        for tag in tags:
            try:
                key = tag.get("key")
            except KeyError:
                log.error("Tag missing key.")
                return False
            try:
                value = tag.get("value")
            except KeyError:
                log.error("Tag missing value.")
                return False
            propagate_at_launch = tag.get("propagate_at_launch", False)
            _tag = autoscale.Tag(
                key=key,
                value=value,
                resource_id=name,
                propagate_at_launch=propagate_at_launch,
            )
            _tags.append(_tag)
    if isinstance(termination_policies, str):
        termination_policies = salt.utils.json.loads(termination_policies)
    if isinstance(suspended_processes, str):
        suspended_processes = salt.utils.json.loads(suspended_processes)
    if isinstance(scheduled_actions, str):
        scheduled_actions = salt.utils.json.loads(scheduled_actions)
    retries = 30
    while True:
        try:
            _asg = autoscale.AutoScalingGroup(
                name=name,
                launch_config=launch_config_name,
                availability_zones=availability_zones,
                min_size=min_size,
                max_size=max_size,
                desired_capacity=desired_capacity,
                load_balancers=load_balancers,
                default_cooldown=default_cooldown,
                health_check_type=health_check_type,
                health_check_period=health_check_period,
                placement_group=placement_group,
                tags=_tags,
                vpc_zone_identifier=vpc_zone_identifier,
                termination_policies=termination_policies,
                suspended_processes=suspended_processes,
            )
            conn.create_auto_scaling_group(_asg)
            # create scaling policies
            _create_scaling_policies(conn, name, scaling_policies)
            # create scheduled actions
            _create_scheduled_actions(conn, name, scheduled_actions)
            # create notifications
            if notification_arn and notification_types:
                conn.put_notification_configuration(
                    _asg, notification_arn, notification_types
                )
            log.info("Created ASG %s", name)
            return True
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            msg = "Failed to create ASG %s", name
            log.error(msg)
            return False


def update(
    name,
    launch_config_name,
    availability_zones,
    min_size,
    max_size,
    desired_capacity=None,
    load_balancers=None,
    default_cooldown=None,
    health_check_type=None,
    health_check_period=None,
    placement_group=None,
    vpc_zone_identifier=None,
    tags=None,
    termination_policies=None,
    suspended_processes=None,
    scaling_policies=None,
    scheduled_actions=None,
    notification_arn=None,
    notification_types=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Update an autoscale group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.update myasg mylc '["us-east-1a", "us-east-1e"]' 1 10 load_balancers='["myelb", "myelb2"]' tags='[{"key": "Name", value="myasg", "propagate_at_launch": True}]'
    """

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    conn3 = _get_conn_autoscaling_boto3(
        region=region, key=key, keyid=keyid, profile=profile
    )
    if not conn:
        return False, "failed to connect to AWS"
    if isinstance(availability_zones, str):
        availability_zones = salt.utils.json.loads(availability_zones)
    if isinstance(load_balancers, str):
        load_balancers = salt.utils.json.loads(load_balancers)
    if isinstance(vpc_zone_identifier, str):
        vpc_zone_identifier = salt.utils.json.loads(vpc_zone_identifier)
    if isinstance(tags, str):
        tags = salt.utils.json.loads(tags)
    if isinstance(termination_policies, str):
        termination_policies = salt.utils.json.loads(termination_policies)
    if isinstance(suspended_processes, str):
        suspended_processes = salt.utils.json.loads(suspended_processes)
    if isinstance(scheduled_actions, str):
        scheduled_actions = salt.utils.json.loads(scheduled_actions)

    # Massage our tagset into  add / remove lists
    # Use a boto3 call here b/c the boto2 call doeesn't implement filters
    current_tags = conn3.describe_tags(
        Filters=[{"Name": "auto-scaling-group", "Values": [name]}]
    ).get("Tags", [])
    current_tags = [
        {
            "key": t["Key"],
            "value": t["Value"],
            "resource_id": t["ResourceId"],
            "propagate_at_launch": t.get("PropagateAtLaunch", False),
        }
        for t in current_tags
    ]
    add_tags = []
    desired_tags = []
    if tags:
        tags = __utils__["boto3.ordered"](tags)
        for tag in tags:
            try:
                key = tag.get("key")
            except KeyError:
                log.error("Tag missing key.")
                return False, "Tag {} missing key".format(tag)
            try:
                value = tag.get("value")
            except KeyError:
                log.error("Tag missing value.")
                return False, "Tag {} missing value".format(tag)
            propagate_at_launch = tag.get("propagate_at_launch", False)
            _tag = {
                "key": key,
                "value": value,
                "resource_id": name,
                "propagate_at_launch": propagate_at_launch,
            }
            if _tag not in current_tags:
                add_tags.append(_tag)
            desired_tags.append(_tag)
    delete_tags = [t for t in current_tags if t not in desired_tags]

    retries = 30
    while True:
        try:
            _asg = autoscale.AutoScalingGroup(
                connection=conn,
                name=name,
                launch_config=launch_config_name,
                availability_zones=availability_zones,
                min_size=min_size,
                max_size=max_size,
                desired_capacity=desired_capacity,
                load_balancers=load_balancers,
                default_cooldown=default_cooldown,
                health_check_type=health_check_type,
                health_check_period=health_check_period,
                placement_group=placement_group,
                tags=add_tags,
                vpc_zone_identifier=vpc_zone_identifier,
                termination_policies=termination_policies,
            )
            if notification_arn and notification_types:
                conn.put_notification_configuration(
                    _asg, notification_arn, notification_types
                )
            _asg.update()
            # Seems the update call doesn't handle tags, so we'll need to update
            # that separately.
            if add_tags:
                log.debug("Adding/updating tags from ASG: %s", add_tags)
                conn.create_or_update_tags([autoscale.Tag(**t) for t in add_tags])
            if delete_tags:
                log.debug("Deleting tags from ASG: %s", delete_tags)
                conn.delete_tags([autoscale.Tag(**t) for t in delete_tags])
            # update doesn't handle suspended_processes either
            # Resume all processes
            _asg.resume_processes()
            # suspend any that are specified.  Note that the boto default of empty
            # list suspends all; don't do that.
            if suspended_processes:
                _asg.suspend_processes(suspended_processes)
            log.info("Updated ASG %s", name)
            # ### scaling policies
            # delete all policies, then recreate them
            for policy in conn.get_all_policies(as_group=name):
                conn.delete_policy(policy.name, autoscale_group=name)
            _create_scaling_policies(conn, name, scaling_policies)
            # ### scheduled actions
            # delete all scheduled actions, then recreate them
            for scheduled_action in conn.get_all_scheduled_actions(as_group=name):
                conn.delete_scheduled_action(
                    scheduled_action.name, autoscale_group=name
                )
            _create_scheduled_actions(conn, name, scheduled_actions)
            return True, ""
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            msg = "Failed to update ASG {}".format(name)
            log.error(msg)
            return False, str(e)


def _create_scaling_policies(conn, as_name, scaling_policies):
    "helper function to create scaling policies"
    if scaling_policies:
        for policy in scaling_policies:
            policy = autoscale.policy.ScalingPolicy(
                name=policy["name"],
                as_name=as_name,
                adjustment_type=policy["adjustment_type"],
                scaling_adjustment=policy["scaling_adjustment"],
                min_adjustment_step=policy.get("min_adjustment_step", None),
                cooldown=policy["cooldown"],
            )
            conn.create_scaling_policy(policy)


def _create_scheduled_actions(conn, as_name, scheduled_actions):
    """
    Helper function to create scheduled actions
    """
    if scheduled_actions:
        for name, action in scheduled_actions.items():
            if "start_time" in action and isinstance(action["start_time"], str):
                action["start_time"] = datetime.datetime.strptime(
                    action["start_time"], DATE_FORMAT
                )
            if "end_time" in action and isinstance(action["end_time"], str):
                action["end_time"] = datetime.datetime.strptime(
                    action["end_time"], DATE_FORMAT
                )
            conn.create_scheduled_group_action(
                as_name,
                name,
                desired_capacity=action.get("desired_capacity"),
                min_size=action.get("min_size"),
                max_size=action.get("max_size"),
                start_time=action.get("start_time"),
                end_time=action.get("end_time"),
                recurrence=action.get("recurrence"),
            )


def delete(name, force=False, region=None, key=None, keyid=None, profile=None):
    """
    Delete an autoscale group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.delete myasg region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30
    while True:
        try:
            conn.delete_auto_scaling_group(name, force)
            msg = "Deleted autoscale group {}.".format(name)
            log.info(msg)
            return True
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            msg = "Failed to delete autoscale group {}".format(name)
            log.error(msg)
            return False


def get_cloud_init_mime(cloud_init):
    """
    Get a mime multipart encoded string from a cloud-init dict. Currently
    supports boothooks, scripts and cloud-config.

    CLI Example:

    .. code-block:: bash

        salt myminion boto.get_cloud_init_mime <cloud init>
    """
    if isinstance(cloud_init, str):
        cloud_init = salt.utils.json.loads(cloud_init)
    _cloud_init = email.mime.multipart.MIMEMultipart()
    if "boothooks" in cloud_init:
        for script_name, script in cloud_init["boothooks"].items():
            _script = email.mime.text.MIMEText(script, "cloud-boothook")
            _cloud_init.attach(_script)
    if "scripts" in cloud_init:
        for script_name, script in cloud_init["scripts"].items():
            _script = email.mime.text.MIMEText(script, "x-shellscript")
            _cloud_init.attach(_script)
    if "cloud-config" in cloud_init:
        cloud_config = cloud_init["cloud-config"]
        _cloud_config = email.mime.text.MIMEText(
            salt.utils.yaml.safe_dump(cloud_config, default_flow_style=False),
            "cloud-config",
        )
        _cloud_init.attach(_cloud_config)
    return _cloud_init.as_string()


def launch_configuration_exists(name, region=None, key=None, keyid=None, profile=None):
    """
    Check for a launch configuration's existence.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.launch_configuration_exists mylc
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30
    while True:
        try:
            lc = conn.get_all_launch_configurations(names=[name])
            if lc:
                return True
            else:
                msg = "The launch configuration does not exist in region {}".format(
                    region
                )
                log.debug(msg)
                return False
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            return False


def get_all_launch_configurations(region=None, key=None, keyid=None, profile=None):
    """
    Fetch and return all Launch Configuration with details.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.get_all_launch_configurations
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30
    while True:
        try:
            return conn.get_all_launch_configurations()
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            return []


def list_launch_configurations(region=None, key=None, keyid=None, profile=None):
    """
    List all Launch Configurations.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.list_launch_configurations
    """
    ret = get_all_launch_configurations(region, key, keyid, profile)
    return [r.name for r in ret]


def describe_launch_configuration(
    name, region=None, key=None, keyid=None, profile=None
):
    """
    Dump details of a given launch configuration.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.describe_launch_configuration mylc
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30
    while True:
        try:
            lc = conn.get_all_launch_configurations(names=[name])
            if lc:
                return lc[0]
            else:
                msg = "The launch configuration does not exist in region {}".format(
                    region
                )
                log.debug(msg)
                return None
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            return None


def create_launch_configuration(
    name,
    image_id,
    key_name=None,
    vpc_id=None,
    vpc_name=None,
    security_groups=None,
    user_data=None,
    instance_type="m1.small",
    kernel_id=None,
    ramdisk_id=None,
    block_device_mappings=None,
    instance_monitoring=False,
    spot_price=None,
    instance_profile_name=None,
    ebs_optimized=False,
    associate_public_ip_address=None,
    volume_type=None,
    delete_on_termination=True,
    iops=None,
    use_block_device_types=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create a launch configuration.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.create_launch_configuration mylc image_id=ami-0b9c9f62 key_name='mykey' security_groups='["mygroup"]' instance_type='c3.2xlarge'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if isinstance(security_groups, str):
        security_groups = salt.utils.json.loads(security_groups)
    if isinstance(block_device_mappings, str):
        block_device_mappings = salt.utils.json.loads(block_device_mappings)
    _bdms = []
    if block_device_mappings:
        # Boto requires objects for the mappings and the devices.
        _block_device_map = blockdevicemapping.BlockDeviceMapping()
        for block_device_dict in block_device_mappings:
            for block_device, attributes in block_device_dict.items():
                _block_device = blockdevicemapping.EBSBlockDeviceType()
                for attribute, value in attributes.items():
                    setattr(_block_device, attribute, value)
                _block_device_map[block_device] = _block_device
        _bdms = [_block_device_map]

    # If a VPC is specified, then determine the secgroup id's within that VPC, not
    # within the default VPC. If a security group id is already part of the list,
    # convert_to_group_ids leaves that entry without attempting a lookup on it.
    if security_groups and (vpc_id or vpc_name):
        security_groups = __salt__["boto_secgroup.convert_to_group_ids"](
            security_groups,
            vpc_id=vpc_id,
            vpc_name=vpc_name,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
    lc = autoscale.LaunchConfiguration(
        name=name,
        image_id=image_id,
        key_name=key_name,
        security_groups=security_groups,
        user_data=user_data,
        instance_type=instance_type,
        kernel_id=kernel_id,
        ramdisk_id=ramdisk_id,
        block_device_mappings=_bdms,
        instance_monitoring=instance_monitoring,
        spot_price=spot_price,
        instance_profile_name=instance_profile_name,
        ebs_optimized=ebs_optimized,
        associate_public_ip_address=associate_public_ip_address,
        volume_type=volume_type,
        delete_on_termination=delete_on_termination,
        iops=iops,
        use_block_device_types=use_block_device_types,
    )
    retries = 30
    while True:
        try:
            conn.create_launch_configuration(lc)
            log.info("Created LC %s", name)
            return True
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            msg = "Failed to create LC {}".format(name)
            log.error(msg)
            return False


def delete_launch_configuration(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete a launch configuration.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_asg.delete_launch_configuration mylc
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30
    while True:
        try:
            conn.delete_launch_configuration(name)
            log.info("Deleted LC %s", name)
            return True
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            msg = "Failed to delete LC {}".format(name)
            log.error(msg)
            return False


def get_scaling_policy_arn(
    as_group, scaling_policy_name, region=None, key=None, keyid=None, profile=None
):
    """
    Return the arn for a scaling policy in a specific autoscale group or None
    if not found. Mainly used as a helper method for boto_cloudwatch_alarm, for
    linking alarms to scaling policies.

    CLI Example:

    .. code-block:: bash

        salt '*' boto_asg.get_scaling_policy_arn mygroup mypolicy
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30
    while retries > 0:
        retries -= 1
        try:
            policies = conn.get_all_policies(as_group=as_group)
            for policy in policies:
                if policy.name == scaling_policy_name:
                    return policy.policy_arn
            log.error("Could not convert: %s", as_group)
            return None
        except boto.exception.BotoServerError as e:
            if e.error_code != "Throttling":
                raise
            log.debug("Throttled by API, will retry in 5 seconds")
            time.sleep(5)

    log.error("Maximum number of retries exceeded")
    return None


def get_all_groups(region=None, key=None, keyid=None, profile=None):
    """
    Return all AutoScale Groups visible in the account
    (as a list of boto.ec2.autoscale.group.AutoScalingGroup).

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt-call boto_asg.get_all_groups region=us-east-1 --output yaml

    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30
    while True:
        try:
            next_token = ""
            asgs = []
            while next_token is not None:
                ret = conn.get_all_groups(next_token=next_token)
                asgs += [a for a in ret]
                next_token = ret.next_token
            return asgs
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            return []


def list_groups(region=None, key=None, keyid=None, profile=None):
    """
    Return all AutoScale Groups visible in the account
    (as a list of names).

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt-call boto_asg.list_groups region=us-east-1

    """
    return [
        a.name
        for a in get_all_groups(region=region, key=key, keyid=keyid, profile=profile)
    ]


def get_instances(
    name,
    lifecycle_state="InService",
    health_status="Healthy",
    attribute="private_ip_address",
    attributes=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    return attribute of all instances in the named autoscale group.

    CLI Example:

    .. code-block:: bash

        salt-call boto_asg.get_instances my_autoscale_group_name

    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    ec2_conn = _get_ec2_conn(region=region, key=key, keyid=keyid, profile=profile)
    retries = 30
    while True:
        try:
            asgs = conn.get_all_groups(names=[name])
            break
        except boto.exception.BotoServerError as e:
            if retries and e.code == "Throttling":
                log.debug("Throttled by AWS API, retrying in 5 seconds...")
                time.sleep(5)
                retries -= 1
                continue
            log.error(e)
            return False
    if len(asgs) != 1:
        log.debug(
            "name '%s' returns multiple ASGs: %s", name, [asg.name for asg in asgs]
        )
        return False
    asg = asgs[0]
    instance_ids = []
    # match lifecycle_state and health_status
    for i in asg.instances:
        if lifecycle_state is not None and i.lifecycle_state != lifecycle_state:
            continue
        if health_status is not None and i.health_status != health_status:
            continue
        instance_ids.append(i.instance_id)
    # get full instance info, so that we can return the attribute
    instances = ec2_conn.get_only_instances(instance_ids=instance_ids)
    if attributes:
        return [
            [_convert_attribute(instance, attr) for attr in attributes]
            for instance in instances
        ]
    else:
        # properly handle case when not all instances have the requested attribute
        return [
            _convert_attribute(instance, attribute)
            for instance in instances
            if getattr(instance, attribute)
        ]


def _convert_attribute(instance, attribute):
    if attribute == "tags":
        tags = dict(getattr(instance, attribute))
        return {
            key.encode("utf-8"): value.encode("utf-8") for key, value in tags.items()
        }

    return getattr(instance, attribute).encode("ascii")


def enter_standby(
    name,
    instance_ids,
    should_decrement_desired_capacity=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Switch desired instances to StandBy mode

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt-call boto_asg.enter_standby my_autoscale_group_name '["i-xxxxxx"]'

    """
    conn = _get_conn_autoscaling_boto3(
        region=region, key=key, keyid=keyid, profile=profile
    )
    try:
        response = conn.enter_standby(
            InstanceIds=instance_ids,
            AutoScalingGroupName=name,
            ShouldDecrementDesiredCapacity=should_decrement_desired_capacity,
        )
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"exists": False}
        return {"error": err}
    return all(
        activity["StatusCode"] != "Failed" for activity in response["Activities"]
    )


def exit_standby(
    name,
    instance_ids,
    should_decrement_desired_capacity=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Exit desired instances from StandBy mode

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt-call boto_asg.exit_standby my_autoscale_group_name '["i-xxxxxx"]'

    """
    conn = _get_conn_autoscaling_boto3(
        region=region, key=key, keyid=keyid, profile=profile
    )
    try:
        response = conn.exit_standby(
            InstanceIds=instance_ids, AutoScalingGroupName=name
        )
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"exists": False}
        return {"error": err}
    return all(
        activity["StatusCode"] != "Failed" for activity in response["Activities"]
    )
