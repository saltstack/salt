# -*- coding: utf-8 -*-
"""
Manage CloudTrail Objects
=========================

.. versionadded:: 2016.11.0

Create and destroy CloudWatch event rules. Be aware that this interacts with Amazon's services,
and so may incur charges.

This module uses ``boto3``, which can be installed via package, or pip.

This module accepts explicit vpc credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    cloudwatch_event.keyid: GKTADJGHEIQSXMKKRBJ08H
    cloudwatch_event.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure event rule exists:
        boto_cloudwatch_event.present:
            - Name: mytrail
            - ScheduleExpression: 'rate(120 minutes)'
            - State: 'DISABLED'
            - Targets:
              - Id: "target1"
                Arn: "arn:aws:lambda:us-west-1:124456715622:function:my_function"
                Input: '{"arbitrary": "json"}'
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os

# Import Salt libs
import salt.utils.json

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto is available.
    """
    return (
        "boto_cloudwatch_event" if "boto_cloudwatch_event.exists" in __salt__ else False
    )


def present(
    name,
    Name=None,
    ScheduleExpression=None,
    EventPattern=None,
    Description=None,
    RoleArn=None,
    State=None,
    Targets=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure trail exists.

    name
        The name of the state definition

    Name
        Name of the event rule.  Defaults to the value of the 'name' param if
        not provided.

    ScheduleExpression
        The scheduling expression. For example, ``cron(0 20 * * ? *)``,
        "rate(5 minutes)"

    EventPattern
        The event pattern.

    Description
        A description of the rule

    State
        Indicates whether the rule is ENABLED or DISABLED.

    RoleArn
        The Amazon Resource Name (ARN) of the IAM role associated with the
        rule.

    Targets
        A list of rresources to be invoked when the rule is triggered.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    """
    ret = {"name": Name, "result": True, "comment": "", "changes": {}}

    Name = Name if Name else name

    if isinstance(Targets, six.string_types):
        Targets = salt.utils.json.loads(Targets)
    if Targets is None:
        Targets = []

    r = __salt__["boto_cloudwatch_event.exists"](
        Name=Name, region=region, key=key, keyid=keyid, profile=profile
    )

    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to create event rule: {0}.".format(
            r["error"]["message"]
        )
        return ret

    if not r.get("exists"):
        if __opts__["test"]:
            ret["comment"] = "CloudWatch event rule {0} is set to be created.".format(
                Name
            )
            ret["result"] = None
            return ret
        r = __salt__["boto_cloudwatch_event.create_or_update"](
            Name=Name,
            ScheduleExpression=ScheduleExpression,
            EventPattern=EventPattern,
            Description=Description,
            RoleArn=RoleArn,
            State=State,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not r.get("created"):
            ret["result"] = False
            ret["comment"] = "Failed to create event rule: {0}.".format(
                r["error"]["message"]
            )
            return ret
        _describe = __salt__["boto_cloudwatch_event.describe"](
            Name, region=region, key=key, keyid=keyid, profile=profile
        )
        if "error" in _describe:
            ret["result"] = False
            ret["comment"] = "Failed to create event rule: {0}.".format(
                _describe["error"]["message"]
            )
            ret["changes"] = {}
            return ret
        ret["changes"]["old"] = {"rule": None}
        ret["changes"]["new"] = _describe
        ret["comment"] = "CloudTrail {0} created.".format(Name)

        if bool(Targets):
            r = __salt__["boto_cloudwatch_event.put_targets"](
                Rule=Name,
                Targets=Targets,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if "error" in r:
                ret["result"] = False
                ret["comment"] = "Failed to create event rule: {0}.".format(
                    r["error"]["message"]
                )
                ret["changes"] = {}
                return ret
            ret["changes"]["new"]["rule"]["Targets"] = Targets
        return ret

    ret["comment"] = os.linesep.join(
        [ret["comment"], "CloudWatch event rule {0} is present.".format(Name)]
    )
    ret["changes"] = {}
    # trail exists, ensure config matches
    _describe = __salt__["boto_cloudwatch_event.describe"](
        Name=Name, region=region, key=key, keyid=keyid, profile=profile
    )
    if "error" in _describe:
        ret["result"] = False
        ret["comment"] = "Failed to update event rule: {0}.".format(
            _describe["error"]["message"]
        )
        ret["changes"] = {}
        return ret
    _describe = _describe.get("rule")

    r = __salt__["boto_cloudwatch_event.list_targets"](
        Rule=Name, region=region, key=key, keyid=keyid, profile=profile
    )
    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to update event rule: {0}.".format(
            r["error"]["message"]
        )
        ret["changes"] = {}
        return ret
    _describe["Targets"] = r.get("targets", [])

    need_update = False
    rule_vars = {
        "ScheduleExpression": "ScheduleExpression",
        "EventPattern": "EventPattern",
        "Description": "Description",
        "RoleArn": "RoleArn",
        "State": "State",
        "Targets": "Targets",
    }
    for invar, outvar in six.iteritems(rule_vars):
        if _describe[outvar] != locals()[invar]:
            need_update = True
            ret["changes"].setdefault("new", {})[invar] = locals()[invar]
            ret["changes"].setdefault("old", {})[invar] = _describe[outvar]

    if need_update:
        if __opts__["test"]:
            msg = "CloudWatch event rule {0} set to be modified.".format(Name)
            ret["comment"] = msg
            ret["result"] = None
            return ret

        ret["comment"] = os.linesep.join(
            [ret["comment"], "CloudWatch event rule to be modified"]
        )
        r = __salt__["boto_cloudwatch_event.create_or_update"](
            Name=Name,
            ScheduleExpression=ScheduleExpression,
            EventPattern=EventPattern,
            Description=Description,
            RoleArn=RoleArn,
            State=State,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not r.get("created"):
            ret["result"] = False
            ret["comment"] = "Failed to update event rule: {0}.".format(
                r["error"]["message"]
            )
            ret["changes"] = {}
            return ret

        if _describe["Targets"] != Targets:
            removes = [i.get("Id") for i in _describe["Targets"]]
            log.error(Targets)
            if bool(Targets):
                for target in Targets:
                    tid = target.get("Id", None)
                    if tid is not None and tid in removes:
                        ix = removes.index(tid)
                        removes.pop(ix)
                r = __salt__["boto_cloudwatch_event.put_targets"](
                    Rule=Name,
                    Targets=Targets,
                    region=region,
                    key=key,
                    keyid=keyid,
                    profile=profile,
                )
                if "error" in r:
                    ret["result"] = False
                    ret["comment"] = "Failed to update event rule: {0}.".format(
                        r["error"]["message"]
                    )
                    ret["changes"] = {}
                    return ret
            if bool(removes):
                r = __salt__["boto_cloudwatch_event.remove_targets"](
                    Rule=Name,
                    Ids=removes,
                    region=region,
                    key=key,
                    keyid=keyid,
                    profile=profile,
                )
                if "error" in r:
                    ret["result"] = False
                    ret["comment"] = "Failed to update event rule: {0}.".format(
                        r["error"]["message"]
                    )
                    ret["changes"] = {}
                    return ret
    return ret


def absent(name, Name=None, region=None, key=None, keyid=None, profile=None):
    """
    Ensure CloudWatch event rule with passed properties is absent.

    name
        The name of the state definition.

    Name
        Name of the event rule.  Defaults to the value of the 'name' param if
        not provided.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    """

    ret = {"name": Name, "result": True, "comment": "", "changes": {}}

    Name = Name if Name else name

    r = __salt__["boto_cloudwatch_event.exists"](
        Name, region=region, key=key, keyid=keyid, profile=profile
    )
    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to delete event rule: {0}.".format(
            r["error"]["message"]
        )
        return ret

    if r and not r["exists"]:
        ret["comment"] = "CloudWatch event rule {0} does not exist.".format(Name)
        return ret

    if __opts__["test"]:
        ret["comment"] = "CloudWatch event rule {0} is set to be removed.".format(Name)
        ret["result"] = None
        return ret

    # must remove all targets first
    r = __salt__["boto_cloudwatch_event.list_targets"](
        Rule=Name, region=region, key=key, keyid=keyid, profile=profile
    )
    if not r.get("targets"):
        ret["result"] = False
        ret["comment"] = "Failed to delete event rule: {0}.".format(
            r["error"]["message"]
        )
        return ret
    ids = [t.get("Id") for t in r["targets"]]
    if bool(ids):
        r = __salt__["boto_cloudwatch_event.remove_targets"](
            Rule=Name, Ids=ids, region=region, key=key, keyid=keyid, profile=profile
        )
        if "error" in r:
            ret["result"] = False
            ret["comment"] = "Failed to delete event rule: {0}.".format(
                r["error"]["message"]
            )
            return ret
        if r.get("failures"):
            ret["result"] = False
            ret["comment"] = "Failed to delete event rule: {0}.".format(r["failures"])
            return ret

    r = __salt__["boto_cloudwatch_event.delete"](
        Name, region=region, key=key, keyid=keyid, profile=profile
    )
    if not r["deleted"]:
        ret["result"] = False
        ret["comment"] = "Failed to delete event rule: {0}.".format(
            r["error"]["message"]
        )
        return ret
    ret["changes"]["old"] = {"rule": Name}
    ret["changes"]["new"] = {"rule": None}
    ret["comment"] = "CloudWatch event rule {0} deleted.".format(Name)
    return ret
