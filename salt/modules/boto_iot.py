# -*- coding: utf-8 -*-
"""
Connection module for Amazon IoT

.. versionadded:: 2016.3.0

:depends:
    - boto
    - boto3

The dependencies listed above can be installed via package or pip.

:configuration: This module accepts explicit Lambda credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        iot.keyid: GKTADJGHEIQSXMKKRBJ08H
        iot.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        iot.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
          keyid: GKTADJGHEIQSXMKKRBJ08H
          key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
          region: us-east-1

"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import datetime
import logging

# Import Salt libs
import salt.utils.compat
import salt.utils.json
import salt.utils.versions

# Import third party libs
from salt.ext.six import string_types

log = logging.getLogger(__name__)


# pylint: disable=import-error
try:
    # pylint: disable=unused-import
    import boto
    import boto3

    # pylint: enable=unused-import
    from botocore.exceptions import ClientError
    from botocore import __version__ as found_botocore_version

    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=import-error


def __virtual__():
    """
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    """
    # the boto_lambda execution module relies on the connect_to_region() method
    # which was added in boto 2.8.0
    # https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
    return salt.utils.versions.check_boto_reqs(boto3_ver="1.2.1", botocore_ver="1.4.41")


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO:
        __utils__["boto3.assign_funcs"](__name__, "iot")


def thing_type_exists(thingTypeName, region=None, key=None, keyid=None, profile=None):
    """
    Given a thing type name, check to see if the given thing type exists

    Returns True if the given thing type exists and returns False if the
    given thing type does not exist.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.thing_type_exists mythingtype

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        res = conn.describe_thing_type(thingTypeName=thingTypeName)
        if res.get("thingTypeName"):
            return {"exists": True}
        else:
            return {"exists": False}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"exists": False}
        return {"error": err}


def describe_thing_type(thingTypeName, region=None, key=None, keyid=None, profile=None):
    """
    Given a thing type name describe its properties.

    Returns a dictionary of interesting properties.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.describe_thing_type mythingtype

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        res = conn.describe_thing_type(thingTypeName=thingTypeName)
        if res:
            res.pop("ResponseMetadata", None)
            thingTypeMetadata = res.get("thingTypeMetadata")
            if thingTypeMetadata:
                for dtype in ("creationDate", "deprecationDate"):
                    dval = thingTypeMetadata.get(dtype)
                    if dval and isinstance(dval, datetime.date):
                        thingTypeMetadata[dtype] = "{0}".format(dval)
            return {"thing_type": res}
        else:
            return {"thing_type": None}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"thing_type": None}
        return {"error": err}


def create_thing_type(
    thingTypeName,
    thingTypeDescription,
    searchableAttributesList,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, create a thing type.

    Returns {created: true} if the thing type was created and returns
    {created: False} if the thing type was not created.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.create_thing_type mythingtype \\
              thingtype_description_string '["searchable_attr_1", "searchable_attr_2"]'

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        thingTypeProperties = dict(
            thingTypeDescription=thingTypeDescription,
            searchableAttributes=searchableAttributesList,
        )
        thingtype = conn.create_thing_type(
            thingTypeName=thingTypeName, thingTypeProperties=thingTypeProperties
        )

        if thingtype:
            log.info(
                "The newly created thing type ARN is %s", thingtype["thingTypeArn"]
            )

            return {"created": True, "thingTypeArn": thingtype["thingTypeArn"]}
        else:
            log.warning("thing type was not created")
            return {"created": False}
    except ClientError as e:
        return {"created": False, "error": __utils__["boto3.get_error"](e)}


def deprecate_thing_type(
    thingTypeName, undoDeprecate=False, region=None, key=None, keyid=None, profile=None
):
    """
    Given a thing type name, deprecate it when undoDeprecate is False
    and undeprecate it when undoDeprecate is True.

    Returns {deprecated: true} if the thing type was deprecated and returns
    {deprecated: false} if the thing type was not deprecated.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.deprecate_thing_type mythingtype

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.deprecate_thing_type(
            thingTypeName=thingTypeName, undoDeprecate=undoDeprecate
        )
        deprecated = True if undoDeprecate is False else False
        return {"deprecated": deprecated}
    except ClientError as e:
        return {"deprecated": False, "error": __utils__["boto3.get_error"](e)}


def delete_thing_type(thingTypeName, region=None, key=None, keyid=None, profile=None):
    """
    Given a thing type name, delete it.

    Returns {deleted: true} if the thing type was deleted and returns
    {deleted: false} if the thing type was not deleted.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.delete_thing_type mythingtype

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_thing_type(thingTypeName=thingTypeName)
        return {"deleted": True}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"deleted": True}
        return {"deleted": False, "error": err}


def policy_exists(policyName, region=None, key=None, keyid=None, profile=None):
    """
    Given a policy name, check to see if the given policy exists.

    Returns True if the given policy exists and returns False if the given
    policy does not exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.policy_exists mypolicy

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.get_policy(policyName=policyName)
        return {"exists": True}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"exists": False}
        return {"error": err}


def create_policy(
    policyName, policyDocument, region=None, key=None, keyid=None, profile=None
):
    """
    Given a valid config, create a policy.

    Returns {created: true} if the policy was created and returns
    {created: False} if the policy was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.create_policy my_policy \\
              '{"Version":"2015-12-12",\\
              "Statement":[{"Effect":"Allow",\\
                            "Action":["iot:Publish"],\\
                            "Resource":["arn:::::topic/foo/bar"]}]}'

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not isinstance(policyDocument, string_types):
            policyDocument = salt.utils.json.dumps(policyDocument)
        policy = conn.create_policy(
            policyName=policyName, policyDocument=policyDocument
        )
        if policy:
            log.info(
                "The newly created policy version is %s", policy["policyVersionId"]
            )

            return {"created": True, "versionId": policy["policyVersionId"]}
        else:
            log.warning("Policy was not created")
            return {"created": False}
    except ClientError as e:
        return {"created": False, "error": __utils__["boto3.get_error"](e)}


def delete_policy(policyName, region=None, key=None, keyid=None, profile=None):
    """
    Given a policy name, delete it.

    Returns {deleted: true} if the policy was deleted and returns
    {deleted: false} if the policy was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.delete_policy mypolicy

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_policy(policyName=policyName)
        return {"deleted": True}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def describe_policy(policyName, region=None, key=None, keyid=None, profile=None):
    """
    Given a policy name describe its properties.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.describe_policy mypolicy

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        policy = conn.get_policy(policyName=policyName)
        if policy:
            keys = ("policyName", "policyArn", "policyDocument", "defaultVersionId")
            return {"policy": dict([(k, policy.get(k)) for k in keys])}
        else:
            return {"policy": None}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"policy": None}
        return {"error": __utils__["boto3.get_error"](e)}


def policy_version_exists(
    policyName, policyVersionId, region=None, key=None, keyid=None, profile=None
):
    """
    Given a policy name and version ID, check to see if the given policy version exists.

    Returns True if the given policy version exists and returns False if the given
    policy version does not exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.policy_version_exists mypolicy versionid

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        policy = conn.get_policy_version(
            policyName=policyName, policyversionId=policyVersionId
        )
        return {"exists": bool(policy)}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"exists": False}
        return {"error": __utils__["boto3.get_error"](e)}


def create_policy_version(
    policyName,
    policyDocument,
    setAsDefault=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, create a new version of a policy.

    Returns {created: true} if the policy version was created and returns
    {created: False} if the policy version was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.create_policy_version my_policy \\
               '{"Statement":[{"Effect":"Allow","Action":["iot:Publish"],"Resource":["arn:::::topic/foo/bar"]}]}'

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not isinstance(policyDocument, string_types):
            policyDocument = salt.utils.json.dumps(policyDocument)
        policy = conn.create_policy_version(
            policyName=policyName,
            policyDocument=policyDocument,
            setAsDefault=setAsDefault,
        )
        if policy:
            log.info(
                "The newly created policy version is %s", policy["policyVersionId"]
            )

            return {"created": True, "name": policy["policyVersionId"]}
        else:
            log.warning("Policy version was not created")
            return {"created": False}
    except ClientError as e:
        return {"created": False, "error": __utils__["boto3.get_error"](e)}


def delete_policy_version(
    policyName, policyVersionId, region=None, key=None, keyid=None, profile=None
):
    """
    Given a policy name and version, delete it.

    Returns {deleted: true} if the policy version was deleted and returns
    {deleted: false} if the policy version was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.delete_policy_version mypolicy version

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_policy_version(
            policyName=policyName, policyVersionId=policyVersionId
        )
        return {"deleted": True}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def describe_policy_version(
    policyName, policyVersionId, region=None, key=None, keyid=None, profile=None
):
    """
    Given a policy name and version describe its properties.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.describe_policy_version mypolicy version

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        policy = conn.get_policy_version(
            policyName=policyName, policyVersionId=policyVersionId
        )
        if policy:
            keys = (
                "policyName",
                "policyArn",
                "policyDocument",
                "policyVersionId",
                "isDefaultVersion",
            )
            return {"policy": dict([(k, policy.get(k)) for k in keys])}
        else:
            return {"policy": None}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"policy": None}
        return {"error": __utils__["boto3.get_error"](e)}


def list_policies(region=None, key=None, keyid=None, profile=None):
    """
    List all policies

    Returns list of policies

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.list_policies

    Example Return:

    .. code-block:: yaml

        policies:
          - {...}
          - {...}

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        policies = []
        for ret in __utils__["boto3.paged_call"](
            conn.list_policies, marker_flag="nextMarker", marker_arg="marker"
        ):
            policies.extend(ret["policies"])
        if not bool(policies):
            log.warning("No policies found")
        return {"policies": policies}
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}


def list_policy_versions(policyName, region=None, key=None, keyid=None, profile=None):
    """
    List the versions available for the given policy.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.list_policy_versions mypolicy

    Example Return:

    .. code-block:: yaml

        policyVersions:
          - {...}
          - {...}

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        vers = []
        for ret in __utils__["boto3.paged_call"](
            conn.list_policy_versions,
            marker_flag="nextMarker",
            marker_arg="marker",
            policyName=policyName,
        ):
            vers.extend(ret["policyVersions"])
        if not bool(vers):
            log.warning("No versions found")
        return {"policyVersions": vers}
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}


def set_default_policy_version(
    policyName, policyVersionId, region=None, key=None, keyid=None, profile=None
):
    """
    Sets the specified version of the specified policy as the policy's default
    (operative) version. This action affects all certificates that the policy is
    attached to.

    Returns {changed: true} if the policy version was set
    {changed: False} if the policy version was not set.


    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.set_default_policy_version mypolicy versionid

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.set_default_policy_version(
            policyName=policyName, policyVersionId=str(policyVersionId)
        )  # future lint: disable=blacklisted-function
        return {"changed": True}
    except ClientError as e:
        return {"changed": False, "error": __utils__["boto3.get_error"](e)}


def list_principal_policies(principal, region=None, key=None, keyid=None, profile=None):
    """
    List the policies attached to the given principal.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.list_principal_policies myprincipal

    Example Return:

    .. code-block:: yaml

        policies:
          - {...}
          - {...}

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        vers = []
        for ret in __utils__["boto3.paged_call"](
            conn.list_principal_policies,
            principal=principal,
            marker_flag="nextMarker",
            marker_arg="marker",
        ):
            vers.extend(ret["policies"])
        if not bool(vers):
            log.warning("No policies found")
        return {"policies": vers}
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}


def attach_principal_policy(
    policyName, principal, region=None, key=None, keyid=None, profile=None
):
    """
    Attach the specified policy to the specified principal (certificate or other
    credential.)

    Returns {attached: true} if the policy was attached
    {attached: False} if the policy was not attached.


    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.attach_principal_policy mypolicy mycognitoID

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.attach_principal_policy(policyName=policyName, principal=principal)
        return {"attached": True}
    except ClientError as e:
        return {"attached": False, "error": __utils__["boto3.get_error"](e)}


def detach_principal_policy(
    policyName, principal, region=None, key=None, keyid=None, profile=None
):
    """
    Detach the specified policy from the specified principal (certificate or other
    credential.)

    Returns {detached: true} if the policy was detached
    {detached: False} if the policy was not detached.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.detach_principal_policy mypolicy mycognitoID

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.detach_principal_policy(policyName=policyName, principal=principal)
        return {"detached": True}
    except ClientError as e:
        return {"detached": False, "error": __utils__["boto3.get_error"](e)}


def topic_rule_exists(ruleName, region=None, key=None, keyid=None, profile=None):
    """
    Given a rule name, check to see if the given rule exists.

    Returns True if the given rule exists and returns False if the given
    rule does not exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.topic_rule_exists myrule

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        rule = conn.get_topic_rule(ruleName=ruleName)
        return {"exists": True}
    except ClientError as e:
        # Nonexistent rules show up as unauthorized exceptions. It's unclear how
        # to distinguish this from a real authorization exception. In practical
        # use, it's more useful to assume lack of existence than to assume a
        # genuine authorization problem; authorization problems should not be
        # the common case.
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "UnauthorizedException":
            return {"exists": False}
        return {"error": __utils__["boto3.get_error"](e)}


def create_topic_rule(
    ruleName,
    sql,
    actions,
    description,
    ruleDisabled=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, create a topic rule.

    Returns {created: true} if the rule was created and returns
    {created: False} if the rule was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.create_topic_rule my_rule "SELECT * FROM 'some/thing'" \\
            '[{"lambda":{"functionArn":"arn:::::something"}},{"sns":{\\
            "targetArn":"arn:::::something","roleArn":"arn:::::something"}}]'

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.create_topic_rule(
            ruleName=ruleName,
            topicRulePayload={
                "sql": sql,
                "description": description,
                "actions": actions,
                "ruleDisabled": ruleDisabled,
            },
        )
        return {"created": True}
    except ClientError as e:
        return {"created": False, "error": __utils__["boto3.get_error"](e)}


def replace_topic_rule(
    ruleName,
    sql,
    actions,
    description,
    ruleDisabled=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, replace a topic rule with the new values.

    Returns {created: true} if the rule was created and returns
    {created: False} if the rule was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.replace_topic_rule my_rule 'SELECT * FROM some.thing' \\
            '[{"lambda":{"functionArn":"arn:::::something"}},{"sns":{\\
            "targetArn":"arn:::::something","roleArn":"arn:::::something"}}]'

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.replace_topic_rule(
            ruleName=ruleName,
            topicRulePayload={
                "sql": sql,
                "description": description,
                "actions": actions,
                "ruleDisabled": ruleDisabled,
            },
        )
        return {"replaced": True}
    except ClientError as e:
        return {"replaced": False, "error": __utils__["boto3.get_error"](e)}


def delete_topic_rule(ruleName, region=None, key=None, keyid=None, profile=None):
    """
    Given a rule name, delete it.

    Returns {deleted: true} if the rule was deleted and returns
    {deleted: false} if the rule was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.delete_rule myrule

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_topic_rule(ruleName=ruleName)
        return {"deleted": True}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def describe_topic_rule(ruleName, region=None, key=None, keyid=None, profile=None):
    """
    Given a topic rule name describe its properties.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.describe_topic_rule myrule

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        rule = conn.get_topic_rule(ruleName=ruleName)
        if rule and "rule" in rule:
            rule = rule["rule"]
            keys = ("ruleName", "sql", "description", "actions", "ruleDisabled")
            return {"rule": dict([(k, rule.get(k)) for k in keys])}
        else:
            return {"rule": None}
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}


def list_topic_rules(
    topic=None, ruleDisabled=None, region=None, key=None, keyid=None, profile=None
):
    """
    List all rules (for a given topic, if specified)

    Returns list of rules

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iot.list_topic_rules

    Example Return:

    .. code-block:: yaml

        rules:
          - {...}
          - {...}

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        kwargs = {}
        if topic is not None:
            kwargs["topic"] = topic
        if ruleDisabled is not None:
            kwargs["ruleDisabled"] = ruleDisabled
        rules = []
        for ret in __utils__["boto3.paged_call"](
            conn.list_topic_rules,
            marker_flag="nextToken",
            marker_arg="nextToken",
            **kwargs
        ):
            rules.extend(ret["rules"])
        if not bool(rules):
            log.warning("No rules found")
        return {"rules": rules}
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}
