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


def target_group_exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an target group exists.

    CLI example:

    .. code-block:: bash

        salt myminion boto_elbv2.exists arn:aws:elasticloadbalancing:us-west-2:644138682826:targetgroup/learn1give1-api/414788a16b5cf163
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        alb = conn.describe_target_groups(TargetGroupArns=[name])
        if alb:
            return True
        else:
            msg = 'The load balancer does not exist in region {0}'.format(region)
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
