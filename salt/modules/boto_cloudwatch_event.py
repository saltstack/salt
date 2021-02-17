"""
Connection module for Amazon CloudWatch Events

.. versionadded:: 2016.11.0

:configuration: This module accepts explicit credentials but can also utilize
    IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        cloudwatch_event.keyid: GKTADJGHEIQSXMKKRBJ08H
        cloudwatch_event.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        cloudwatch_event.region: us-east-1

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

import salt.utils.compat
import salt.utils.json
import salt.utils.versions

log = logging.getLogger(__name__)

# pylint: disable=import-error
try:
    # pylint: disable=unused-import
    import boto
    import boto3

    # pylint: enable=unused-import
    from botocore.exceptions import ClientError

    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError as e:
    HAS_BOTO = False
# pylint: enable=import-error


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    return salt.utils.versions.check_boto_reqs()


def __init__(opts):
    if HAS_BOTO:
        __utils__["boto3.assign_funcs"](__name__, "events")


def exists(Name, region=None, key=None, keyid=None, profile=None):
    """
    Given a rule name, check to see if the given rule exists.

    Returns True if the given rule exists and returns False if the given
    rule does not exist.

    CLI example::

        salt myminion boto_cloudwatch_event.exists myevent region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        events = conn.list_rules(NamePrefix=Name)
        if not events:
            return {"exists": False}
        for rule in events.get("Rules", []):
            if rule.get("Name", None) == Name:
                return {"exists": True}
        return {"exists": False}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        return {"error": err}


def create_or_update(
    Name,
    ScheduleExpression=None,
    EventPattern=None,
    Description=None,
    RoleArn=None,
    State=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, create an event rule.

    Returns {created: true} if the rule was created and returns
    {created: False} if the rule was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudwatch_event.create_or_update my_rule

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        kwargs = {}
        for arg in (
            "ScheduleExpression",
            "EventPattern",
            "State",
            "Description",
            "RoleArn",
        ):
            if locals()[arg] is not None:
                kwargs[arg] = locals()[arg]
        rule = conn.put_rule(Name=Name, **kwargs)
        if rule:
            log.info("The newly created event rule is %s", rule.get("RuleArn"))

            return {"created": True, "arn": rule.get("RuleArn")}
        else:
            log.warning("Event rule was not created")
            return {"created": False}
    except ClientError as e:
        return {"created": False, "error": __utils__["boto3.get_error"](e)}


def delete(Name, region=None, key=None, keyid=None, profile=None):
    """
    Given a rule name, delete it.

    Returns {deleted: true} if the rule was deleted and returns
    {deleted: false} if the rule was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudwatch_event.delete myrule

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_rule(Name=Name)
        return {"deleted": True}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def describe(Name, region=None, key=None, keyid=None, profile=None):
    """
    Given a rule name describe its properties.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudwatch_event.describe myrule

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        rule = conn.describe_rule(Name=Name)
        if rule:
            keys = (
                "Name",
                "Arn",
                "EventPattern",
                "ScheduleExpression",
                "State",
                "Description",
                "RoleArn",
            )
            return {"rule": {k: rule.get(k) for k in keys}}
        else:
            return {"rule": None}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "RuleNotFoundException":
            return {"error": "Rule {} not found".format(Rule)}
        return {"error": __utils__["boto3.get_error"](e)}


def list_rules(region=None, key=None, keyid=None, profile=None):
    """
    List, with details, all Cloudwatch Event rules visible in the current scope.

    CLI example::

        salt myminion boto_cloudwatch_event.list_rules region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        ret = []
        NextToken = ""
        while NextToken is not None:
            args = {"NextToken": NextToken} if NextToken else {}
            r = conn.list_rules(**args)
            ret += r.get("Rules", [])
            NextToken = r.get("NextToken")
        return ret
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}


def list_targets(Rule, region=None, key=None, keyid=None, profile=None):
    """
    Given a rule name list the targets of that rule.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudwatch_event.list_targets myrule

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        targets = conn.list_targets_by_rule(Rule=Rule)
        ret = []
        if targets and "Targets" in targets:
            keys = ("Id", "Arn", "Input", "InputPath")
            for target in targets.get("Targets"):
                ret.append({k: target.get(k) for k in keys if k in target})
            return {"targets": ret}
        else:
            return {"targets": None}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "RuleNotFoundException":
            return {"error": "Rule {} not found".format(Rule)}
        return {"error": __utils__["boto3.get_error"](e)}


def put_targets(Rule, Targets, region=None, key=None, keyid=None, profile=None):
    """
    Add the given targets to the given rule

    Returns a dictionary describing any failures.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudwatch_event.put_targets myrule [{'Id': 'target1', 'Arn': 'arn:***'}]

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if isinstance(Targets, str):
            Targets = salt.utils.json.loads(Targets)
        failures = conn.put_targets(Rule=Rule, Targets=Targets)
        if failures and failures.get("FailedEntryCount", 0) > 0:
            return {"failures": failures.get("FailedEntries")}
        else:
            return {"failures": None}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "RuleNotFoundException":
            return {"error": "Rule {} not found".format(Rule)}
        return {"error": __utils__["boto3.get_error"](e)}


def remove_targets(Rule, Ids, region=None, key=None, keyid=None, profile=None):
    """
    Given a rule name remove the named targets from the target list

    Returns a dictionary describing any failures.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudwatch_event.remove_targets myrule ['Target1']

    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if isinstance(Ids, str):
            Ids = salt.utils.json.loads(Ids)
        failures = conn.remove_targets(Rule=Rule, Ids=Ids)
        if failures and failures.get("FailedEntryCount", 0) > 0:
            return {"failures": failures.get("FailedEntries", 1)}
        else:
            return {"failures": None}
    except ClientError as e:
        err = __utils__["boto3.get_error"](e)
        if e.response.get("Error", {}).get("Code") == "RuleNotFoundException":
            return {"error": "Rule {} not found".format(Rule)}
        return {"error": __utils__["boto3.get_error"](e)}
