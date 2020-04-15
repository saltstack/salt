# -*- coding: utf-8 -*-
"""
Connection module for Amazon CloudWatch

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit credentials but can also utilize
    IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        cloudwatch.keyid: GKTADJGHEIQSXMKKRBJ08H
        cloudwatch.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        cloudwatch.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602

from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging

import salt.utils.json
import salt.utils.odict as odict
import salt.utils.versions
import yaml  # pylint: disable=blacklisted-import

# Import Salt libs
from salt.ext import six

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.ec2.cloudwatch
    import boto.ec2.cloudwatch.listelement
    import boto.ec2.cloudwatch.dimension

    logging.getLogger("boto").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    has_boto_reqs = salt.utils.versions.check_boto_reqs(check_boto3=False)
    if has_boto_reqs is True:
        __utils__["boto.assign_funcs"](
            __name__, "cloudwatch", module="ec2.cloudwatch", pack=__salt__
        )
    return has_boto_reqs


def get_alarm(name, region=None, key=None, keyid=None, profile=None):
    """
    Get alarm details. Also can be used to check to see if an alarm exists.

    CLI example::

        salt myminion boto_cloudwatch.get_alarm myalarm region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    alarms = conn.describe_alarms(alarm_names=[name])
    if len(alarms) == 0:
        return None
    if len(alarms) > 1:
        log.error("multiple alarms matched name '%s'", name)
    return _metric_alarm_to_dict(alarms[0])


def _safe_dump(data):
    """
    this presenter magic makes yaml.safe_dump
    work with the objects returned from
    boto.describe_alarms()
    """
    custom_dumper = __utils__["yaml.get_dumper"]("SafeOrderedDumper")

    def boto_listelement_presenter(dumper, data):
        return dumper.represent_list(list(data))

    yaml.add_representer(
        boto.ec2.cloudwatch.listelement.ListElement,
        boto_listelement_presenter,
        Dumper=custom_dumper,
    )

    def dimension_presenter(dumper, data):
        return dumper.represent_dict(dict(data))

    yaml.add_representer(
        boto.ec2.cloudwatch.dimension.Dimension,
        dimension_presenter,
        Dumper=custom_dumper,
    )

    return __utils__["yaml.dump"](data, Dumper=custom_dumper)


def get_all_alarms(region=None, prefix=None, key=None, keyid=None, profile=None):
    """
    Get all alarm details.  Produces results that can be used to create an sls
    file.

    If prefix parameter is given, alarm names in the output will be prepended
    with the prefix; alarms that have the prefix will be skipped.  This can be
    used to convert existing alarms to be managed by salt, as follows:

        1. Make a "backup" of all existing alarms
            $ salt-call boto_cloudwatch.get_all_alarms --out=txt | sed "s/local: //" > legacy_alarms.sls

        2. Get all alarms with new prefixed names
            $ salt-call boto_cloudwatch.get_all_alarms "prefix=**MANAGED BY SALT** " --out=txt | sed "s/local: //" > managed_alarms.sls

        3. Insert the managed alarms into cloudwatch
            $ salt-call state.template managed_alarms.sls

        4.  Manually verify that the new alarms look right

        5.  Delete the original alarms
            $ sed s/present/absent/ legacy_alarms.sls > remove_legacy_alarms.sls
            $ salt-call state.template remove_legacy_alarms.sls

        6.  Get all alarms again, verify no changes
            $ salt-call boto_cloudwatch.get_all_alarms --out=txt | sed "s/local: //" > final_alarms.sls
            $ diff final_alarms.sls managed_alarms.sls

    CLI example::

        salt myminion boto_cloudwatch.get_all_alarms region=us-east-1 --out=txt
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    alarms = conn.describe_alarms()
    results = odict.OrderedDict()
    for alarm in alarms:
        alarm = _metric_alarm_to_dict(alarm)
        name = alarm["name"]
        if prefix:
            if name.startswith(prefix):
                continue
            name = prefix + alarm["name"]
        del alarm["name"]
        alarm_sls = [{"name": name}, {"attributes": alarm}]
        results["manage alarm " + name] = {"boto_cloudwatch_alarm.present": alarm_sls}
    return _safe_dump(results)


def create_or_update_alarm(
    connection=None,
    name=None,
    metric=None,
    namespace=None,
    statistic=None,
    comparison=None,
    threshold=None,
    period=None,
    evaluation_periods=None,
    unit=None,
    description="",
    dimensions=None,
    alarm_actions=None,
    insufficient_data_actions=None,
    ok_actions=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create or update a cloudwatch alarm.

    Params are the same as:
        https://boto.readthedocs.io/en/latest/ref/cloudwatch.html#boto.ec2.cloudwatch.alarm.MetricAlarm.

    Dimensions must be a dict. If the value of Dimensions is a string, it will
    be json decoded to produce a dict. alarm_actions, insufficient_data_actions,
    and ok_actions must be lists of string.  If the passed-in value is a string,
    it will be split on "," to produce a list. The strings themselves for
    alarm_actions, insufficient_data_actions, and ok_actions must be Amazon
    resource names (ARN's); however, this method also supports an arn lookup
    notation, as follows:

        arn:aws:....                                    ARN as per http://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html
        scaling_policy:<as_name>:<scaling_policy_name>  The named autoscale group scaling policy, for the named group (e.g.  scaling_policy:my-asg:ScaleDown)

    This is convenient for setting up autoscaling as follows.  First specify a
    boto_asg.present state for an ASG with scaling_policies, and then set up
    boto_cloudwatch_alarm.present states which have alarm_actions that
    reference the scaling_policy.

    CLI example:

        salt myminion boto_cloudwatch.create_alarm name=myalarm ... region=us-east-1
    """
    # clean up argument types, so that CLI works
    if threshold:
        threshold = float(threshold)
    if period:
        period = int(period)
    if evaluation_periods:
        evaluation_periods = int(evaluation_periods)
    if isinstance(dimensions, six.string_types):
        dimensions = salt.utils.json.loads(dimensions)
        if not isinstance(dimensions, dict):
            log.error(
                "could not parse dimensions argument: must be json encoding of a dict: '%s'",
                dimensions,
            )
            return False
    if isinstance(alarm_actions, six.string_types):
        alarm_actions = alarm_actions.split(",")
    if isinstance(insufficient_data_actions, six.string_types):
        insufficient_data_actions = insufficient_data_actions.split(",")
    if isinstance(ok_actions, six.string_types):
        ok_actions = ok_actions.split(",")

    # convert provided action names into ARN's
    if alarm_actions:
        alarm_actions = convert_to_arn(
            alarm_actions, region=region, key=key, keyid=keyid, profile=profile
        )
    if insufficient_data_actions:
        insufficient_data_actions = convert_to_arn(
            insufficient_data_actions,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
    if ok_actions:
        ok_actions = convert_to_arn(
            ok_actions, region=region, key=key, keyid=keyid, profile=profile
        )

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    alarm = boto.ec2.cloudwatch.alarm.MetricAlarm(
        connection=connection,
        name=name,
        metric=metric,
        namespace=namespace,
        statistic=statistic,
        comparison=comparison,
        threshold=threshold,
        period=period,
        evaluation_periods=evaluation_periods,
        unit=unit,
        description=description,
        dimensions=dimensions,
        alarm_actions=alarm_actions,
        insufficient_data_actions=insufficient_data_actions,
        ok_actions=ok_actions,
    )
    conn.create_alarm(alarm)
    log.info("Created/updated alarm %s", name)
    return True


def convert_to_arn(arns, region=None, key=None, keyid=None, profile=None):
    """
    Convert a list of strings into actual arns. Converts convenience names such
    as 'scaling_policy:...'

    CLI Example::

        salt '*' convert_to_arn 'scaling_policy:'
    """
    results = []
    for arn in arns:
        if arn.startswith("scaling_policy:"):
            _, as_group, scaling_policy_name = arn.split(":")
            policy_arn = __salt__["boto_asg.get_scaling_policy_arn"](
                as_group, scaling_policy_name, region, key, keyid, profile
            )
            if policy_arn:
                results.append(policy_arn)
            else:
                log.error("Could not convert: %s", arn)
        else:
            results.append(arn)
    return results


def delete_alarm(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete a cloudwatch alarm

    CLI example to delete a queue::

        salt myminion boto_cloudwatch.delete_alarm myalarm region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    conn.delete_alarms([name])
    log.info("Deleted alarm %s", name)
    return True


def _metric_alarm_to_dict(alarm):
    """
    Convert a boto.ec2.cloudwatch.alarm.MetricAlarm into a dict. Convenience
    for pretty printing.
    """
    d = odict.OrderedDict()
    fields = [
        "name",
        "metric",
        "namespace",
        "statistic",
        "comparison",
        "threshold",
        "period",
        "evaluation_periods",
        "unit",
        "description",
        "dimensions",
        "alarm_actions",
        "insufficient_data_actions",
        "ok_actions",
    ]
    for f in fields:
        if hasattr(alarm, f):
            d[f] = getattr(alarm, f)
    return d
