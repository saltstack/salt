# -*- coding: utf-8 -*-
"""
Manage AWS Application Load Balancer

.. versionadded:: 2017.7.0

Add and remove targets from an ALB target group.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit alb credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    elbv2.keyid: GKTADJGHEIQSXMKKRBJ08H
    elbv2.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    elbv2.region: us-west-2

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1
"""

from __future__ import absolute_import, print_function, unicode_literals

import copy

# Import Python Libs
import logging

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto is available.
    """
    if "boto_elbv2.target_group_exists" in __salt__:
        return "boto_elbv2"
    return (False, "The boto_elbv2 module cannot be loaded: boto3 library not found")


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
    **kwargs
):

    """
    .. versionadded:: 2017.11.0

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

    CLI example:
    .. code-block:: yaml

        create-target:
          boto_elb2.create_targets_group:
            - name: myALB
            - protocol: https
            - port: 443
            - vpc_id: myVPC
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    if __salt__["boto_elbv2.target_group_exists"](name, region, key, keyid, profile):
        ret["result"] = True
        ret["comment"] = "Target Group {0} already exists".format(name)
        return ret

    if __opts__["test"]:
        ret["comment"] = "Target Group {0} will be created".format(name)
        return ret

    state = __salt__["boto_elbv2.create_target_group"](
        name,
        protocol,
        port,
        vpc_id,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
        health_check_protocol=health_check_protocol,
        health_check_port=health_check_port,
        health_check_path=health_check_path,
        health_check_interval_seconds=health_check_interval_seconds,
        health_check_timeout_seconds=health_check_timeout_seconds,
        healthy_threshold_count=healthy_threshold_count,
        unhealthy_threshold_count=unhealthy_threshold_count,
        **kwargs
    )

    if state:
        ret["changes"]["target_group"] = name
        ret["result"] = True
        ret["comment"] = "Target Group {0} created".format(name)
    else:
        ret["result"] = False
        ret["comment"] = "Target Group {0} creation failed".format(name)
    return ret


def delete_target_group(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete target group.

    name
        (string) - The Amazon Resource Name (ARN) of the resource.

    returns
        (bool) - True on success, False on failure.

    CLI example:

    .. code-block:: bash

        check-target:
          boto_elb2.delete_targets_group:
            - name: myALB
            - protocol: https
            - port: 443
            - vpc_id: myVPC
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    if not __salt__["boto_elbv2.target_group_exists"](
        name, region, key, keyid, profile
    ):
        ret["result"] = True
        ret["comment"] = "Target Group {0} does not exists".format(name)
        return ret

    if __opts__["test"]:
        ret["comment"] = "Target Group {0} will be deleted".format(name)
        return ret

    state = __salt__["boto_elbv2.delete_target_group"](
        name, region=region, key=key, keyid=keyid, profile=profile
    )

    if state:
        ret["result"] = True
        ret["changes"]["target_group"] = name
        ret["comment"] = "Target Group {0} deleted".format(name)
    else:
        ret["result"] = False
        ret["comment"] = "Target Group {0} deletion failed".format(name)
    return ret


def targets_registered(
    name, targets, region=None, key=None, keyid=None, profile=None, **kwargs
):
    """
    .. versionadded:: 2017.7.0

    Add targets to an Application Load Balancer target group. This state will not remove targets.

    name
        The ARN of the Application Load Balancer Target Group to add targets to.

    targets
        A list of target IDs or a string of a single target that this target group should
        distribute traffic to.

    .. code-block:: yaml

        add-targets:
          boto_elb.targets_registered:
            - name: arn:myloadbalancer
            - targets:
              - instance-id1
              - instance-id2
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    if __salt__["boto_elbv2.target_group_exists"](name, region, key, keyid, profile):
        health = __salt__["boto_elbv2.describe_target_health"](
            name, region=region, key=key, keyid=keyid, profile=profile
        )
        failure = False
        changes = False
        newhealth_mock = copy.copy(health)

        if isinstance(targets, six.string_types):
            targets = [targets]

        for target in targets:
            if target in health and health.get(target) != "draining":
                ret["comment"] = ret[
                    "comment"
                ] + "Target/s {0} already registered and is {1}.\n".format(
                    target, health[target]
                )
                ret["result"] = True
            else:
                if __opts__["test"]:
                    changes = True
                    newhealth_mock.update({target: "initial"})
                else:
                    state = __salt__["boto_elbv2.register_targets"](
                        name,
                        targets,
                        region=region,
                        key=key,
                        keyid=keyid,
                        profile=profile,
                    )
                    if state:
                        changes = True
                        ret["result"] = True
                    else:
                        ret[
                            "comment"
                        ] = "Target Group {0} failed to add targets".format(name)
                        failure = True
        if failure:
            ret["result"] = False
        if changes:
            ret["changes"]["old"] = health
            if __opts__["test"]:
                ret["comment"] = "Target Group {0} would be changed".format(name)
                ret["result"] = None
                ret["changes"]["new"] = newhealth_mock
            else:
                ret["comment"] = "Target Group {0} has been changed".format(name)
                newhealth = __salt__["boto_elbv2.describe_target_health"](
                    name, region=region, key=key, keyid=keyid, profile=profile
                )
                ret["changes"]["new"] = newhealth
        return ret
    else:
        ret["comment"] = "Could not find target group {0}".format(name)
    return ret


def targets_deregistered(
    name, targets, region=None, key=None, keyid=None, profile=None, **kwargs
):
    """
    Remove targets to an Application Load Balancer target group.

    name
        The ARN of the Application Load Balancer Target Group to remove targets from.

    targets
        A list of target IDs or a string of a single target registered to the target group to be removed

    .. versionadded:: Unknown

    .. code-block:: yaml

        remove-targets:
          boto_elb.targets_deregistered:
            - name: arn:myloadbalancer
            - targets:
              - instance-id1
              - instance-id2
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}
    if __salt__["boto_elbv2.target_group_exists"](name, region, key, keyid, profile):
        health = __salt__["boto_elbv2.describe_target_health"](
            name, region=region, key=key, keyid=keyid, profile=profile
        )
        failure = False
        changes = False
        newhealth_mock = copy.copy(health)
        if isinstance(targets, six.string_types):
            targets = [targets]
        for target in targets:
            if target not in health or health.get(target) == "draining":
                ret["comment"] = ret[
                    "comment"
                ] + "Target/s {0} already deregistered\n".format(target)
                ret["result"] = True
            else:
                if __opts__["test"]:
                    changes = True
                    newhealth_mock.update({target: "draining"})
                else:
                    state = __salt__["boto_elbv2.deregister_targets"](
                        name,
                        targets,
                        region=region,
                        key=key,
                        keyid=keyid,
                        profile=profile,
                    )
                    if state:
                        changes = True
                        ret["result"] = True
                    else:
                        ret[
                            "comment"
                        ] = "Target Group {0} failed to remove targets".format(name)
                        failure = True
        if failure:
            ret["result"] = False
        if changes:
            ret["changes"]["old"] = health
            if __opts__["test"]:
                ret["comment"] = "Target Group {0} would be changed".format(name)
                ret["result"] = None
                ret["changes"]["new"] = newhealth_mock
            else:
                ret["comment"] = "Target Group {0} has been changed".format(name)
                newhealth = __salt__["boto_elbv2.describe_target_health"](
                    name, region=region, key=key, keyid=keyid, profile=profile
                )
                ret["changes"]["new"] = newhealth
        return ret
    else:
        ret["comment"] = "Could not find target group {0}".format(name)
    return ret
