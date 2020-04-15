# -*- coding: utf-8 -*-
"""
Manage IoT Objects
==================

.. versionadded:: 2016.3.0

Create and destroy IoT objects. Be aware that this interacts with Amazon's services,
and so may incur charges.

:depends:
    - boto
    - boto3

The dependencies listed above can be installed via package or pip.

This module accepts explicit vpc credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
    vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure policy exists:
        boto_iot.policy_present:
            - policyName: mypolicy
            - policyDocument:
                Version: "2012-10-17"
                Statement:
                  Action:
                    - iot:Publish
                  Resource:
                    - "*"
                  Effect: "Allow"
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    Ensure topic rule exists:
        boto_iot.topic_rule_present:
            - ruleName: myrule
            - sql: "SELECT * FROM 'iot/test'"
            - description: 'test rule'
            - ruleDisabled: false
            - actions:
              - lambda:
                  functionArn: "arn:aws:us-east-1:1234:function/functionname"
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import datetime
import logging
import os
import time

# Import Salt libs
import salt.utils.data
import salt.utils.json

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto is available.
    """
    return "boto_iot" if "boto_iot.policy_exists" in __salt__ else False


def thing_type_present(
    name,
    thingTypeName,
    thingTypeDescription,
    searchableAttributesList,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure thing type exists.

    .. versionadded:: 2016.11.0

    name
        The name of the state definition

    thingTypeName
        Name of the thing type

    thingTypeDescription
        Description of the thing type

    searchableAttributesList
        List of string attributes that are searchable for
        the thing type

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used

    profile
        A dict with region, key, keyid, or a pillar key (string) that
        contains a dict with region, key, and keyid

    """
    ret = {"name": thingTypeName, "result": True, "comment": "", "changes": {}}

    r = __salt__["boto_iot.thing_type_exists"](
        thingTypeName=thingTypeName,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )

    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to create thing type: {0}.".format(
            r["error"]["message"]
        )
        return ret

    if r.get("exists"):
        ret["result"] = True
        ret["comment"] = "Thing type with given name {0} already exists".format(
            thingTypeName
        )
        return ret

    if __opts__["test"]:
        ret["comment"] = "Thing type {0} is set to be created.".format(thingTypeName)
        ret["result"] = None
        return ret

    r = __salt__["boto_iot.create_thing_type"](
        thingTypeName=thingTypeName,
        thingTypeDescription=thingTypeDescription,
        searchableAttributesList=searchableAttributesList,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )

    if not r.get("created"):
        ret["result"] = False
        ret["comment"] = "Failed to create thing type: {0}.".format(
            r["error"]["message"]
        )
        return ret

    _describe = __salt__["boto_iot.describe_thing_type"](
        thingTypeName=thingTypeName,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    ret["changes"]["old"] = {"thing_type": None}
    ret["changes"]["new"] = _describe
    ret["comment"] = "Thing Type {0} created.".format(thingTypeName)
    return ret


def thing_type_absent(
    name, thingTypeName, region=None, key=None, keyid=None, profile=None
):
    """
    Ensure thing type with passed properties is absent.

    .. versionadded:: 2016.11.0

    name
        The name of the state definition.

    thingTypeName
        Name of the thing type.

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

    ret = {"name": thingTypeName, "result": True, "comment": "", "changes": {}}

    _describe = __salt__["boto_iot.describe_thing_type"](
        thingTypeName=thingTypeName,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if "error" in _describe:
        ret["result"] = False
        ret["comment"] = "Failed to delete thing type: {0}.".format(
            _describe["error"]["message"]
        )
        return ret

    if _describe and not _describe["thing_type"]:
        ret["comment"] = "Thing Type {0} does not exist.".format(thingTypeName)
        return ret

    _existing_thing_type = _describe["thing_type"]
    _thing_type_metadata = _existing_thing_type.get("thingTypeMetadata")
    _deprecated = _thing_type_metadata.get("deprecated", False)

    if __opts__["test"]:
        if _deprecated:
            _change_desc = "removed"
        else:
            _change_desc = "deprecated and removed"
        ret["comment"] = "Thing Type {0} is set to be {1}.".format(
            thingTypeName, _change_desc
        )
        ret["result"] = None
        return ret

    # initialize a delete_wait_timer to be 5 minutes
    # AWS does not allow delete thing type until 5 minutes
    # after a thing type is marked deprecated.
    _delete_wait_timer = 300

    if _deprecated is False:
        _deprecate = __salt__["boto_iot.deprecate_thing_type"](
            thingTypeName=thingTypeName,
            undoDeprecate=False,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if "error" in _deprecate:
            ret["result"] = False
            ret["comment"] = "Failed to deprecate thing type: {0}.".format(
                _deprecate["error"]["message"]
            )
            return ret
    else:
        # grab the deprecation date string from _thing_type_metadata
        _deprecation_date_str = _thing_type_metadata.get("deprecationDate")
        if _deprecation_date_str:
            # see if we can wait less than 5 minutes
            _tz_index = _deprecation_date_str.find("+")
            if _tz_index != -1:
                _deprecation_date_str = _deprecation_date_str[:_tz_index]

            _deprecation_date = datetime.datetime.strptime(
                _deprecation_date_str, "%Y-%m-%d %H:%M:%S.%f"
            )

            _elapsed_time_delta = datetime.datetime.utcnow() - _deprecation_date
            if _elapsed_time_delta.seconds >= 300:
                _delete_wait_timer = 0
            else:
                _delete_wait_timer = 300 - _elapsed_time_delta.seconds

    # wait required 5 minutes since deprecation time
    if _delete_wait_timer:
        log.warning(
            "wait for %s seconds per AWS (5 minutes after deprecation time) "
            "before we can delete iot thing type",
            _delete_wait_timer,
        )
        time.sleep(_delete_wait_timer)

    # delete thing type
    r = __salt__["boto_iot.delete_thing_type"](
        thingTypeName=thingTypeName,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if not r["deleted"]:
        ret["result"] = False
        ret["comment"] = "Failed to delete thing type: {0}.".format(
            r["error"]["message"]
        )
        return ret
    ret["changes"]["old"] = _describe
    ret["changes"]["new"] = {"thing_type": None}
    ret["comment"] = "Thing Type {0} deleted.".format(thingTypeName)
    return ret


def policy_present(
    name, policyName, policyDocument, region=None, key=None, keyid=None, profile=None
):
    """
    Ensure policy exists.

    name
        The name of the state definition

    policyName
        Name of the policy.

    policyDocument
        The JSON document that describes the policy. The length of the
        policyDocument must be a minimum length of 1, with a maximum length of
        2048, excluding whitespace.

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
    ret = {"name": policyName, "result": True, "comment": "", "changes": {}}

    r = __salt__["boto_iot.policy_exists"](
        policyName=policyName, region=region, key=key, keyid=keyid, profile=profile
    )

    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to create policy: {0}.".format(r["error"]["message"])
        return ret

    if not r.get("exists"):
        if __opts__["test"]:
            ret["comment"] = "Policy {0} is set to be created.".format(policyName)
            ret["result"] = None
            return ret
        r = __salt__["boto_iot.create_policy"](
            policyName=policyName,
            policyDocument=policyDocument,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not r.get("created"):
            ret["result"] = False
            ret["comment"] = "Failed to create policy: {0}.".format(
                r["error"]["message"]
            )
            return ret
        _describe = __salt__["boto_iot.describe_policy"](
            policyName, region=region, key=key, keyid=keyid, profile=profile
        )
        ret["changes"]["old"] = {"policy": None}
        ret["changes"]["new"] = _describe
        ret["comment"] = "Policy {0} created.".format(policyName)
        return ret

    ret["comment"] = os.linesep.join(
        [ret["comment"], "Policy {0} is present.".format(policyName)]
    )
    ret["changes"] = {}
    # policy exists, ensure config matches
    _describe = __salt__["boto_iot.describe_policy"](
        policyName=policyName, region=region, key=key, keyid=keyid, profile=profile
    )["policy"]

    if isinstance(_describe["policyDocument"], six.string_types):
        describeDict = salt.utils.json.loads(_describe["policyDocument"])
    else:
        describeDict = _describe["policyDocument"]

    if isinstance(policyDocument, six.string_types):
        policyDocument = salt.utils.json.loads(policyDocument)

    r = salt.utils.data.compare_dicts(describeDict, policyDocument)
    if bool(r):
        if __opts__["test"]:
            msg = "Policy {0} set to be modified.".format(policyName)
            ret["comment"] = msg
            ret["result"] = None
            return ret

        ret["comment"] = os.linesep.join([ret["comment"], "Policy to be modified"])
        policyDocument = salt.utils.json.dumps(policyDocument)

        r = __salt__["boto_iot.create_policy_version"](
            policyName=policyName,
            policyDocument=policyDocument,
            setAsDefault=True,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not r.get("created"):
            ret["result"] = False
            ret["comment"] = "Failed to update policy: {0}.".format(
                r["error"]["message"]
            )
            ret["changes"] = {}
            return ret

        __salt__["boto_iot.delete_policy_version"](
            policyName=policyName,
            policyVersionId=_describe["defaultVersionId"],
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )

        ret["changes"].setdefault("new", {})["policyDocument"] = policyDocument
        ret["changes"].setdefault("old", {})["policyDocument"] = _describe[
            "policyDocument"
        ]
    return ret


def policy_absent(name, policyName, region=None, key=None, keyid=None, profile=None):
    """
    Ensure policy with passed properties is absent.

    name
        The name of the state definition.

    policyName
        Name of the policy.

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

    ret = {"name": policyName, "result": True, "comment": "", "changes": {}}

    r = __salt__["boto_iot.policy_exists"](
        policyName, region=region, key=key, keyid=keyid, profile=profile
    )
    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to delete policy: {0}.".format(r["error"]["message"])
        return ret

    if r and not r["exists"]:
        ret["comment"] = "Policy {0} does not exist.".format(policyName)
        return ret

    if __opts__["test"]:
        ret["comment"] = "Policy {0} is set to be removed.".format(policyName)
        ret["result"] = None
        return ret
    # delete non-default versions
    versions = __salt__["boto_iot.list_policy_versions"](
        policyName, region=region, key=key, keyid=keyid, profile=profile
    )
    if versions:
        for version in versions.get("policyVersions", []):
            if version.get("isDefaultVersion", False):
                continue
            r = __salt__["boto_iot.delete_policy_version"](
                policyName,
                policyVersionId=version.get("versionId"),
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if not r["deleted"]:
                ret["result"] = False
                ret["comment"] = "Failed to delete policy: {0}.".format(
                    r["error"]["message"]
                )
                return ret
    # For the delete to succeed, the policy must be detached from any
    # principals. However, no API is provided to list the principals to which it
    # is attached. (A policy may be attached to a principal not associated with
    # any Thing.) So it is up to the user to ensure that it is properly
    # detached.

    # delete policy
    r = __salt__["boto_iot.delete_policy"](
        policyName, region=region, key=key, keyid=keyid, profile=profile
    )
    if not r["deleted"]:
        ret["result"] = False
        ret["comment"] = "Failed to delete policy: {0}.".format(r["error"]["message"])
        return ret
    ret["changes"]["old"] = {"policy": policyName}
    ret["changes"]["new"] = {"policy": None}
    ret["comment"] = "Policy {0} deleted.".format(policyName)
    return ret


def policy_attached(
    name, policyName, principal, region=None, key=None, keyid=None, profile=None
):
    """
    Ensure policy is attached to the given principal.

    name
        The name of the state definition

    policyName
        Name of the policy.

    principal
        The principal which can be a certificate ARN or a Cognito ID.

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
    ret = {"name": policyName, "result": True, "comment": "", "changes": {}}

    r = __salt__["boto_iot.list_principal_policies"](
        principal=principal, region=region, key=key, keyid=keyid, profile=profile
    )

    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to attach policy: {0}.".format(r["error"]["message"])
        return ret

    attached = False
    for policy in r.get("policies", []):
        if policy.get("policyName") == policyName:
            attached = True
            break
    if not attached:
        if __opts__["test"]:
            ret["comment"] = "Policy {0} is set to be attached to {1}.".format(
                policyName, principal
            )
            ret["result"] = None
            return ret
        r = __salt__["boto_iot.attach_principal_policy"](
            policyName=policyName,
            principal=principal,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not r.get("attached"):
            ret["result"] = False
            ret["comment"] = "Failed to attach policy: {0}.".format(
                r["error"]["message"]
            )
            return ret
        ret["changes"]["old"] = {"attached": False}
        ret["changes"]["new"] = {"attached": True}
        ret["comment"] = "Policy {0} attached to {1}.".format(policyName, principal)
        return ret

    ret["comment"] = os.linesep.join(
        [ret["comment"], "Policy {0} is attached.".format(policyName)]
    )
    ret["changes"] = {}

    return ret


def policy_detached(
    name, policyName, principal, region=None, key=None, keyid=None, profile=None
):
    """
    Ensure policy is attached to the given principal.

    name
        The name of the state definition.

    policyName
        Name of the policy.

    principal
        The principal which can be a certificate ARN or a Cognito ID.

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

    ret = {"name": policyName, "result": True, "comment": "", "changes": {}}

    r = __salt__["boto_iot.list_principal_policies"](
        principal=principal, region=region, key=key, keyid=keyid, profile=profile
    )

    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to detached policy: {0}.".format(r["error"]["message"])
        return ret

    attached = False
    for policy in r.get("policies", []):
        if policy.get("policyName") == policyName:
            attached = True
            break
    if attached:
        if __opts__["test"]:
            ret["comment"] = "Policy {0} is set to be detached from {1}.".format(
                policyName, principal
            )
            ret["result"] = None
            return ret
        r = __salt__["boto_iot.detach_principal_policy"](
            policyName=policyName,
            principal=principal,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not r.get("detached"):
            ret["result"] = False
            ret["comment"] = "Failed to detach policy: {0}.".format(
                r["error"]["message"]
            )
            return ret
        ret["changes"]["old"] = {"attached": True}
        ret["changes"]["new"] = {"attached": False}
        ret["comment"] = "Policy {0} detached from {1}.".format(policyName, principal)
        return ret

    ret["comment"] = os.linesep.join(
        [ret["comment"], "Policy {0} is detached.".format(policyName)]
    )
    ret["changes"] = {}

    return ret


def topic_rule_present(
    name,
    ruleName,
    sql,
    actions,
    description="",
    ruleDisabled=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Ensure topic rule exists.

    name
        The name of the state definition

    ruleName
        Name of the rule.

    sql
        The SQL statement used to query the topic.

    actions
        The actions associated with the rule.

    description
        The description of the rule.

    ruleDisable
        Specifies whether the rule is disabled.

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
    ret = {"name": ruleName, "result": True, "comment": "", "changes": {}}

    r = __salt__["boto_iot.topic_rule_exists"](
        ruleName=ruleName, region=region, key=key, keyid=keyid, profile=profile
    )

    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to create rule: {0}.".format(r["error"]["message"])
        return ret

    if not r.get("exists"):
        if __opts__["test"]:
            ret["comment"] = "Rule {0} is set to be created.".format(ruleName)
            ret["result"] = None
            return ret
        r = __salt__["boto_iot.create_topic_rule"](
            ruleName=ruleName,
            sql=sql,
            actions=actions,
            description=description,
            ruleDisabled=ruleDisabled,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not r.get("created"):
            ret["result"] = False
            ret["comment"] = "Failed to create rule: {0}.".format(r["error"]["message"])
            return ret
        _describe = __salt__["boto_iot.describe_topic_rule"](
            ruleName, region=region, key=key, keyid=keyid, profile=profile
        )
        ret["changes"]["old"] = {"rule": None}
        ret["changes"]["new"] = _describe
        ret["comment"] = "Rule {0} created.".format(ruleName)
        return ret

    ret["comment"] = os.linesep.join(
        [ret["comment"], "Rule {0} is present.".format(ruleName)]
    )
    ret["changes"] = {}
    # policy exists, ensure config matches
    _describe = __salt__["boto_iot.describe_topic_rule"](
        ruleName=ruleName, region=region, key=key, keyid=keyid, profile=profile
    )["rule"]

    if isinstance(actions, six.string_types):
        actions = salt.utils.json.loads(actions)

    need_update = False
    # cmp() function is deprecated in Python 3: use the following as a substitute for 'r'.
    r = (_describe["actions"] > actions) - (_describe["actions"] < actions)
    if bool(r):
        need_update = True
        ret["changes"].setdefault("new", {})["actions"] = actions
        ret["changes"].setdefault("old", {})["actions"] = _describe["actions"]

    for var in ("sql", "description", "ruleDisabled"):
        if _describe[var] != locals()[var]:
            need_update = True
            ret["changes"].setdefault("new", {})[var] = locals()[var]
            ret["changes"].setdefault("old", {})[var] = _describe[var]
    if need_update:
        if __opts__["test"]:
            msg = "Rule {0} set to be modified.".format(ruleName)
            ret["changes"] = {}
            ret["comment"] = msg
            ret["result"] = None
            return ret
        ret["comment"] = os.linesep.join([ret["comment"], "Rule to be modified"])
        r = __salt__["boto_iot.replace_topic_rule"](
            ruleName=ruleName,
            sql=sql,
            actions=actions,
            description=description,
            ruleDisabled=ruleDisabled,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if not r.get("replaced"):
            ret["result"] = False
            ret["comment"] = "Failed to update rule: {0}.".format(r["error"]["message"])
            ret["changes"] = {}
    return ret


def topic_rule_absent(name, ruleName, region=None, key=None, keyid=None, profile=None):
    """
    Ensure topic rule with passed properties is absent.

    name
        The name of the state definition.

    ruleName
        Name of the policy.

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

    ret = {"name": ruleName, "result": True, "comment": "", "changes": {}}

    r = __salt__["boto_iot.topic_rule_exists"](
        ruleName, region=region, key=key, keyid=keyid, profile=profile
    )
    if "error" in r:
        ret["result"] = False
        ret["comment"] = "Failed to delete rule: {0}.".format(r["error"]["message"])
        return ret

    if r and not r["exists"]:
        ret["comment"] = "Rule {0} does not exist.".format(ruleName)
        return ret

    if __opts__["test"]:
        ret["comment"] = "Rule {0} is set to be removed.".format(ruleName)
        ret["result"] = None
        return ret
    r = __salt__["boto_iot.delete_topic_rule"](
        ruleName, region=region, key=key, keyid=keyid, profile=profile
    )
    if not r["deleted"]:
        ret["result"] = False
        ret["comment"] = "Failed to delete rule: {0}.".format(r["error"]["message"])
        return ret
    ret["changes"]["old"] = {"rule": ruleName}
    ret["changes"]["new"] = {"rule": None}
    ret["comment"] = "Rule {0} deleted.".format(ruleName)
    return ret
