# -*- coding: utf-8 -*-
'''
Manage AWS Application Load Balancer

.. versionadded:: TBD

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
'''

# Import Python Libs
import logging
import copy

# Import Salt Libs
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_elbv2' if 'boto_elbv2.target_group_exists' in __salt__ else False


def targets_registered(name, targets, region=None, key=None, keyid=None,
                       profile=None):
    '''
    Add targets to an Application Load Balancer target group. This state will not remove targets.

    name
        The ARN of the Application Load Balancer Target Group to add targets to.

    targets
        A list of target IDs or a string of a single target that this target group should
        distribute traffic to.

    .. versionadded:: TBD

    .. code-block:: yaml

        add-targets:
          boto_elb.targets_registered:
            - name: arn:myloadbalancer
            - targets:
              - instance-id1
              - instance-id2
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    tg = __salt__['boto_elbv2.target_group_exists'](name, region, key, keyid, profile)

    if tg:
        health = __salt__['boto_elbv2.describe_target_health'](name, region=region, key=key, keyid=keyid, profile=profile)
        failure = False
        changes = False
        newhealth_mock = copy.copy(health)

        if isinstance(targets, str):
            targets = [targets]

        for target in targets:
            if target in health and health.get(target) != "draining":
                ret['comment'] = ret['comment'] + 'Target/s {0} already registered and is {1}.\n'.format(target, health[target])
                ret['result'] = True
            else:
                if __opts__['test']:
                    changes = True
                    newhealth_mock.update({target: "initial"})
                else:
                    state = __salt__['boto_elbv2.register_targets'](name,
                                                                    targets,
                                                                    region,
                                                                    key,
                                                                    keyid,
                                                                    profile)
                    if state:
                        changes = True
                        ret['result'] = True
                    else:
                        ret['comment'] = 'Target Group {0} failed to add targets'.format(name)
                        failure = True
        if failure:
            ret['result'] = False
        if changes:
            ret['changes']['old'] = health
            if __opts__['test']:
                ret['comment'] = 'Target Group {0} would be changed'.format(name)
                ret['result'] = None
                ret['changes']['new'] = newhealth_mock
            else:
                ret['comment'] = 'Target Group {0} has been changed'.format(name)
                newhealth = __salt__['boto_elbv2.describe_target_health'](name, region=region, key=key, keyid=keyid, profile=profile)
                ret['changes']['new'] = newhealth
        return ret
    else:
        ret['comment'] = 'Could not find target group {0}'.format(name)
    return ret


def targets_deregistered(name, targets, region=None, key=None, keyid=None,
                       profile=None):
    '''
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
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    tg = __salt__['boto_elbv2.target_group_exists'](name, region, key, keyid, profile)
    if tg:
        health = __salt__['boto_elbv2.describe_target_health'](name, region, key, keyid, profile)
        failure = False
        changes = False
        newhealth_mock = copy.copy(health)
        if isinstance(targets, str):
            targets = [targets]
        for target in targets:
            if target not in health or health.get(target) == "draining":
                ret['comment'] = ret['comment'] + 'Target/s {0} already deregistered\n'.format(target)
                ret['result'] = True
            else:
                if __opts__['test']:
                    changes = True
                    newhealth_mock.update({target: "draining"})
                else:
                    state = __salt__['boto_elbv2.deregister_targets'](name,
                                                                    targets,
                                                                    region,
                                                                    key,
                                                                    keyid,
                                                                    profile)
                    if state:
                        changes = True
                        ret['result'] = True
                    else:
                        ret['comment'] = 'Target Group {0} failed to remove targets'.format(name)
                        failure = True
        if failure:
            ret['result'] = False
        if changes:
            ret['changes']['old'] = health
            if __opts__['test']:
                ret['comment'] = 'Target Group {0} would be changed'.format(name)
                ret['result'] = None
                ret['changes']['new'] = newhealth_mock
            else:
                ret['comment'] = 'Target Group {0} has been changed'.format(name)
                newhealth = __salt__['boto_elbv2.describe_target_health'](name, region, key, keyid, profile)
                ret['changes']['new'] = newhealth
        return ret
    else:
        ret['comment'] = 'Could not find target group {0}'.format(name)
    return ret
