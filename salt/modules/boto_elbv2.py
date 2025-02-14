"""
Connection module for Amazon ALB

.. versionadded:: 2017.7.0

:configuration: This module accepts explicit elb credentials but can also utilize
    IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        elbv2.keyid: GKTADJGHEIQSXMKKRBJ08H
        elbv2.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        elbv2.region: us-west-2

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto3

"""

# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602

import logging

import salt.utils.versions

try:
    # pylint: disable=unused-import
    import boto3
    import botocore

    # pylint: enable=unused-import
    # TODO Version check using salt.utils.versions
    from botocore.exceptions import ClientError

    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto3 libraries exist.
    """
    has_boto_reqs = salt.utils.versions.check_boto_reqs()
    if has_boto_reqs is True:
        __utils__["boto3.assign_funcs"](__name__, "elbv2")
    return has_boto_reqs


def create_target_group(
    name,
    protocol,
    port,
    vpc_id,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    health_check_protocol="HTTP",
    health_check_port="traffic-port",
    health_check_path="/",
    health_check_interval_seconds=30,
    health_check_timeout_seconds=5,
    healthy_threshold_count=5,
    unhealthy_threshold_count=2,
):
    """
    Create target group if not present.

    name
        (string) - The name of the target group.
    protocol
        (string) - The protocol to use for routing traffic to the targets
    port
        (int) - The port on which the targets receive traffic. This port is used unless
        you specify a port override when registering the traffic.
    vpc_id
        (string) - The identifier of the virtual private cloud (VPC).
    health_check_protocol
        (string) - The protocol the load balancer uses when performing health check on
        targets. The default is the HTTP protocol.
    health_check_port
        (string) - The port the load balancer uses when performing health checks on
        targets. The default is 'traffic-port', which indicates the port on which each
        target receives traffic from the load balancer.
    health_check_path
        (string) - The ping path that is the destination on the targets for health
        checks. The default is /.
    health_check_interval_seconds
        (integer) - The approximate amount of time, in seconds, between health checks
        of an individual target. The default is 30 seconds.
    health_check_timeout_seconds
        (integer) - The amount of time, in seconds, during which no response from a
        target means a failed health check. The default is 5 seconds.
    healthy_threshold_count
        (integer) - The number of consecutive health checks successes required before
        considering an unhealthy target healthy. The default is 5.
    unhealthy_threshold_count
        (integer) - The number of consecutive health check failures required before
        considering a target unhealthy. The default is 2.

    returns
        (bool) - True on success, False on failure.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elbv2.create_target_group learn1give1 protocol=HTTP port=54006 vpc_id=vpc-deadbeef
    """

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if target_group_exists(name, region, key, keyid, profile):
        return True

    try:
        alb = conn.create_target_group(
            Name=name,
            Protocol=protocol,
            Port=port,
            VpcId=vpc_id,
            HealthCheckProtocol=health_check_protocol,
            HealthCheckPort=health_check_port,
            HealthCheckPath=health_check_path,
            HealthCheckIntervalSeconds=health_check_interval_seconds,
            HealthCheckTimeoutSeconds=health_check_timeout_seconds,
            HealthyThresholdCount=healthy_threshold_count,
            UnhealthyThresholdCount=unhealthy_threshold_count,
        )
        if alb:
            log.info(
                "Created ALB %s: %s", name, alb["TargetGroups"][0]["TargetGroupArn"]
            )
            return True
        else:
            log.error("Failed to create ALB %s", name)
            return False
    except ClientError as error:
        log.error(
            "Failed to create ALB %s: %s: %s",
            name,
            error.response["Error"]["Code"],
            error.response["Error"]["Message"],
            exc_info_on_loglevel=logging.DEBUG,
        )


def delete_target_group(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete target group.

    name
        (string) - Target Group Name or Amazon Resource Name (ARN).

    returns
        (bool) - True on success, False on failure.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elbv2.delete_target_group arn:aws:elasticloadbalancing:us-west-2:644138682826:targetgroup/learn1give1-api/414788a16b5cf163
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not target_group_exists(name, region, key, keyid, profile):
        return True

    try:
        if name.startswith("arn:aws:elasticloadbalancing"):
            conn.delete_target_group(TargetGroupArn=name)
            log.info("Deleted target group %s", name)
        else:
            tg_info = conn.describe_target_groups(Names=[name])
            if len(tg_info["TargetGroups"]) != 1:
                return False
            arn = tg_info["TargetGroups"][0]["TargetGroupArn"]
            conn.delete_target_group(TargetGroupArn=arn)
            log.info("Deleted target group %s ARN %s", name, arn)
        return True
    except ClientError as error:
        log.error(
            "Failed to delete target group %s", name, exc_info_on_loglevel=logging.DEBUG
        )
        return False


def target_group_exists(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if an target group exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elbv2.target_group_exists arn:aws:elasticloadbalancing:us-west-2:644138682826:targetgroup/learn1give1-api/414788a16b5cf163
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        if name.startswith("arn:aws:elasticloadbalancing"):
            alb = conn.describe_target_groups(TargetGroupArns=[name])
        else:
            alb = conn.describe_target_groups(Names=[name])
        if alb:
            return True
        else:
            log.warning("The target group does not exist in region %s", region)
            return False
    except ClientError as error:
        log.warning("target_group_exists check for %s returned: %s", name, error)
        return False


def describe_target_health(
    name, targets=None, region=None, key=None, keyid=None, profile=None
):
    """
    Get the curret health check status for targets in a target group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elbv2.describe_target_health arn:aws:elasticloadbalancing:us-west-2:644138682826:targetgroup/learn1give1-api/414788a16b5cf163 targets=["i-isdf23ifjf"]
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        if targets:
            targetsdict = []
            for target in targets:
                targetsdict.append({"Id": target})
            instances = conn.describe_target_health(
                TargetGroupArn=name, Targets=targetsdict
            )
        else:
            instances = conn.describe_target_health(TargetGroupArn=name)
        ret = {}
        for instance in instances["TargetHealthDescriptions"]:
            ret.update({instance["Target"]["Id"]: instance["TargetHealth"]["State"]})

        return ret
    except ClientError as error:
        log.warning(error)
        return {}


def register_targets(name, targets, region=None, key=None, keyid=None, profile=None):
    """
    Register targets to a target froup of an ALB. ``targets`` is either a
    instance id string or a list of instance id's.

    Returns:

    - ``True``: instance(s) registered successfully
    - ``False``: instance(s) failed to be registered

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elbv2.register_targets myelb instance_id
        salt myminion boto_elbv2.register_targets myelb "[instance_id,instance_id]"
    """
    targetsdict = []
    if isinstance(targets, str):
        targetsdict.append({"Id": targets})
    else:
        for target in targets:
            targetsdict.append({"Id": target})
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        registered_targets = conn.register_targets(
            TargetGroupArn=name, Targets=targetsdict
        )
        if registered_targets:
            return True
        return False
    except ClientError as error:
        log.warning(error)
        return False


def deregister_targets(name, targets, region=None, key=None, keyid=None, profile=None):
    """
    Deregister targets to a target froup of an ALB. ``targets`` is either a
    instance id string or a list of instance id's.

    Returns:

    - ``True``: instance(s) deregistered successfully
    - ``False``: instance(s) failed to be deregistered

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elbv2.deregister_targets myelb instance_id
        salt myminion boto_elbv2.deregister_targets myelb "[instance_id,instance_id]"
    """
    targetsdict = []
    if isinstance(targets, str):
        targetsdict.append({"Id": targets})
    else:
        for target in targets:
            targetsdict.append({"Id": target})
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        registered_targets = conn.deregister_targets(
            TargetGroupArn=name, Targets=targetsdict
        )
        if registered_targets:
            return True
        return False
    except ClientError as error:
        log.warning(error)
        return False
