# -*- coding: utf-8 -*-
'''
Connection module for Amazon ALB

.. versionadded:: TBD

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
'''
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging

log = logging.getLogger(__name__)

# Import Salt libs

# Import third party libs
import salt.ext.six as six

try:
    # pylint: disable=unused-import
    import salt.utils.boto3
    # pylint: enable=unused-import

    # TODO Version check using salt.utils.versions
    from botocore.exceptions import ClientError
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    '''
    Only load if boto3 libraries exist.
    '''
    if not HAS_BOTO:
        return (False, "The boto_elbv2 module cannot be loaded: boto3 library not found")
    __utils__['boto3.assign_funcs'](__name__, 'elbv2')
    return True

def create_target_group(name, protocol, port, vpc_id,
                        region=None, key=None, keyid=None, profile=None,
                        health_check_protocol='HTTP', health_check_port='traffic-port',
                        health_check_path='/', health_check_interval_seconds=30,
                        health_check_timeout_seconds=5, healthy_threshold_count=5,
                        unhealthy_threshold_count=2):
    '''
    Create target group if not present.

    CLI example:
    .. code-block:: bash

        salt myminion boto_elbv2.create_target_group learn1give1 protocol=HTTP port=54006 vpc_id=vpc-deadbeef 
    '''

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if target_group_exists(name, region, key, keyid, profile):
        return True
    else:
        try:
            lb = conn.create_target_group(Name=name, Protocol=protocol, Port=port,
                                        VpcId=vpc_id, HealthCheckProtocol=health_check_protocol,
                                        HealthCheckPort=health_check_port,
                                        HealthCheckPath=health_check_path,
                                        HealthCheckIntervalSeconds=health_check_interval_seconds,
                                        HealthCheckTimeoutSeconds=health_check_timeout_seconds,
                                        HealthyThresholdCount=healthy_threshold_count,
                                        UnhealthyThresholdCount=unhealthy_threshold_count)
            if lb:
                log.info('Created ALB {0}: {1}'.format(name,
                                        lb['TargetGroups'][0]['TargetGroupArn']))
                return True
            else:
                log.error('Failed to create ALB {0}'.format(name))
                return False
        except ClientError as error:
            log.debug(error)
            log.error('Failed to create ALB {0}: {1}: {2}'.format(name,
                                            error.response['Error']['Code'],
                                            error.response['Error']['Message']))

def delete_target_group(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete target group.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elbv2.delete_target_group arn:aws:elasticloadbalancing:us-west-2:644138682826:targetgroup/learn1give1-api/414788a16b5cf163
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        conn.delete_target_group(TargetGroupArn=name)
        log.info('Deleted target group {0}'.format(name))
        return True
    except ClientError as error:
        log.debug(error)
        log.error('Failed to delete target group {0}'.format(name))
        return False

def target_group_exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an target group exists.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elbv2.target_group_exists arn:aws:elasticloadbalancing:us-west-2:644138682826:targetgroup/learn1give1-api/414788a16b5cf163
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        if name.startswith('arn:aws:elasticloadbalancing'):
            alb = conn.describe_target_groups(TargetGroupArns=[name])
        else:
            alb = conn.describe_target_groups(Names=[name])
        if alb:
            return True
        else:
            log.warning('The target group does not exist in region {0}'.format(region))
            return False
    except ClientError as error:
        log.warning(error)
        return False


def describe_target_health(name, targets=None, region=None, key=None, keyid=None, profile=None):
    '''
    Get the curret health check status for targets in a target group.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elbv2.describe_target_health arn:aws:elasticloadbalancing:us-west-2:644138682826:targetgroup/learn1give1-api/414788a16b5cf163 targets=["i-isdf23ifjf"]
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        if targets:
            targetsdict = []
            for target in targets:
                targetsdict.append({"Id": target})
            instances = conn.describe_target_health(TargetGroupArn=name, Targets=targetsdict)
        else:
            instances = conn.describe_target_health(TargetGroupArn=name)
        ret = {}
        for instance in instances['TargetHealthDescriptions']:
            ret.update({instance['Target']['Id']: instance['TargetHealth']['State']})

        return ret
    except ClientError as error:
        log.warning(error)
        return {}


def register_targets(name, targets, region=None, key=None, keyid=None,
                       profile=None):
    '''
    Register targets to a target froup of an ALB. ``targets`` is either a
    instance id string or a list of instance id's.

    Returns:

    - ``True``: instance(s) registered successfully
    - ``False``: instance(s) failed to be registered

    CLI example:

    .. code-block:: bash

        salt myminion boto_elbv2.register_targets myelb instance_id
        salt myminion boto_elbv2.register_targets myelb "[instance_id,instance_id]"
    '''
    targetsdict = []
    if isinstance(targets, str) or isinstance(targets, six.text_type):
        targetsdict.append({"Id": targets})
    else:
        for target in targets:
            targetsdict.append({"Id": target})
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        registered_targets = conn.register_targets(TargetGroupArn=name, Targets=targetsdict)
        if registered_targets:
            return True
        else:
            return False
    except ClientError as error:
        log.warning(error)
        return False


def deregister_targets(name, targets, region=None, key=None, keyid=None,
                         profile=None):
    '''
    Deregister targets to a target froup of an ALB. ``targets`` is either a
    instance id string or a list of instance id's.

    Returns:

    - ``True``: instance(s) deregistered successfully
    - ``False``: instance(s) failed to be deregistered

    CLI example:

    .. code-block:: bash

        salt myminion boto_elbv2.deregister_targets myelb instance_id
        salt myminion boto_elbv2.deregister_targets myelb "[instance_id,instance_id]"
    '''
    targetsdict = []
    if isinstance(targets, str) or isinstance(targets, six.text_type):
        targetsdict.append({"Id": targets})
    else:
        for target in targets:
            targetsdict.append({"Id": target})
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        registered_targets = conn.deregister_targets(TargetGroupArn=name, Targets=targetsdict)
        if registered_targets:
            return True
        else:
            return False
    except ClientError as error:
        log.warning(error)
        return False
