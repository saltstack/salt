"""
Connection module for Amazon Elasticsearch Service

.. versionadded:: 2016.11.0

:configuration: This module accepts explicit AWS credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        lambda.keyid: GKTADJGHEIQSXMKKRBJ08H
        lambda.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        lambda.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

    Create and delete methods return:

    .. code-block:: yaml

        created: true

    or

    .. code-block:: yaml

        created: false
        error:
          message: error message

    Request methods (e.g., `describe_function`) return:

    .. code-block:: yaml

        domain:
          - {...}
          - {...}

    or

    .. code-block:: yaml

        error:
          message: error message

:depends: boto3

"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602


import logging

import salt.utils.compat
import salt.utils.json
import salt.utils.versions
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


# pylint: disable=import-error
try:
    # pylint: disable=unused-import
    import boto
    import boto3

    # pylint: enable=unused-import
    from botocore.exceptions import ClientError

    logging.getLogger("boto").setLevel(logging.CRITICAL)
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
    return salt.utils.versions.check_boto_reqs(boto_ver="2.8.0", boto3_ver="1.4.0")


def __init__(opts):
    if HAS_BOTO:
        __utils__["boto3.assign_funcs"](__name__, "es")


def exists(DomainName, region=None, key=None, keyid=None, profile=None):
    """
    Given a domain name, check to see if the given domain exists.

    Returns True if the given domain exists and returns False if the given
    function does not exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticsearch_domain.exists mydomain

    """

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        domain = conn.describe_elasticsearch_domain(DomainName=DomainName)
        return {"exists": True}
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return {"exists": False}
        return {"error": __utils__["boto3.get_error"](e)}


def status(DomainName, region=None, key=None, keyid=None, profile=None):
    """
    Given a domain name describe its status.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticsearch_domain.status mydomain

    """

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        domain = conn.describe_elasticsearch_domain(DomainName=DomainName)
        if domain and "DomainStatus" in domain:
            domain = domain.get("DomainStatus", {})
            keys = (
                "Endpoint",
                "Created",
                "Deleted",
                "DomainName",
                "DomainId",
                "EBSOptions",
                "SnapshotOptions",
                "AccessPolicies",
                "Processing",
                "AdvancedOptions",
                "ARN",
                "ElasticsearchVersion",
            )
            return {"domain": {k: domain.get(k) for k in keys if k in domain}}
        else:
            return {"domain": None}
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}


def describe(DomainName, region=None, key=None, keyid=None, profile=None):
    """
    Given a domain name describe its properties.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticsearch_domain.describe mydomain

    """

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        domain = conn.describe_elasticsearch_domain_config(DomainName=DomainName)
        if domain and "DomainConfig" in domain:
            domain = domain["DomainConfig"]
            keys = (
                "ElasticsearchClusterConfig",
                "EBSOptions",
                "AccessPolicies",
                "SnapshotOptions",
                "AdvancedOptions",
            )
            return {
                "domain": {
                    k: domain.get(k, {}).get("Options") for k in keys if k in domain
                }
            }
        else:
            return {"domain": None}
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}


def create(
    DomainName,
    ElasticsearchClusterConfig=None,
    EBSOptions=None,
    AccessPolicies=None,
    SnapshotOptions=None,
    AdvancedOptions=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    ElasticsearchVersion=None,
):
    """
    Given a valid config, create a domain.

    Returns {created: true} if the domain was created and returns
    {created: False} if the domain was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticsearch_domain.create mydomain \\
              {'InstanceType': 't2.micro.elasticsearch', 'InstanceCount': 1, \\
              'DedicatedMasterEnabled': false, 'ZoneAwarenessEnabled': false} \\
              {'EBSEnabled': true, 'VolumeType': 'gp2', 'VolumeSize': 10, \\
              'Iops': 0} \\
              {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"AWS": "*"}, "Action": "es:*", \\
               "Resource": "arn:aws:es:us-east-1:111111111111:domain/mydomain/*", \\
               "Condition": {"IpAddress": {"aws:SourceIp": ["127.0.0.1"]}}}]} \\
              {"AutomatedSnapshotStartHour": 0} \\
              {"rest.action.multi.allow_explicit_index": "true"}
    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        kwargs = {}
        for k in (
            "ElasticsearchClusterConfig",
            "EBSOptions",
            "AccessPolicies",
            "SnapshotOptions",
            "AdvancedOptions",
            "ElasticsearchVersion",
        ):
            if locals()[k] is not None:
                val = locals()[k]
                if isinstance(val, str):
                    try:
                        val = salt.utils.json.loads(val)
                    except ValueError as e:
                        return {
                            "updated": False,
                            "error": "Error parsing {}: {}".format(k, e.message),
                        }
                kwargs[k] = val
        if "AccessPolicies" in kwargs:
            kwargs["AccessPolicies"] = salt.utils.json.dumps(kwargs["AccessPolicies"])
        if "ElasticsearchVersion" in kwargs:
            kwargs["ElasticsearchVersion"] = str(kwargs["ElasticsearchVersion"])
        domain = conn.create_elasticsearch_domain(DomainName=DomainName, **kwargs)
        if domain and "DomainStatus" in domain:
            return {"created": True}
        else:
            log.warning("Domain was not created")
            return {"created": False}
    except ClientError as e:
        return {"created": False, "error": __utils__["boto3.get_error"](e)}


def delete(DomainName, region=None, key=None, keyid=None, profile=None):
    """
    Given a domain name, delete it.

    Returns {deleted: true} if the domain was deleted and returns
    {deleted: false} if the domain was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticsearch_domain.delete mydomain

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_elasticsearch_domain(DomainName=DomainName)
        return {"deleted": True}
    except ClientError as e:
        return {"deleted": False, "error": __utils__["boto3.get_error"](e)}


def update(
    DomainName,
    ElasticsearchClusterConfig=None,
    EBSOptions=None,
    AccessPolicies=None,
    SnapshotOptions=None,
    AdvancedOptions=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Update the named domain to the configuration.

    Returns {updated: true} if the domain was updated and returns
    {updated: False} if the domain was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticsearch_domain.update mydomain \\
              {'InstanceType': 't2.micro.elasticsearch', 'InstanceCount': 1, \\
              'DedicatedMasterEnabled': false, 'ZoneAwarenessEnabled': false} \\
              {'EBSEnabled': true, 'VolumeType': 'gp2', 'VolumeSize': 10, \\
              'Iops': 0} \\
              {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"AWS": "*"}, "Action": "es:*", \\
               "Resource": "arn:aws:es:us-east-1:111111111111:domain/mydomain/*", \\
               "Condition": {"IpAddress": {"aws:SourceIp": ["127.0.0.1"]}}}]} \\
              {"AutomatedSnapshotStartHour": 0} \\
              {"rest.action.multi.allow_explicit_index": "true"}

    """

    call_args = {}
    for k in (
        "ElasticsearchClusterConfig",
        "EBSOptions",
        "AccessPolicies",
        "SnapshotOptions",
        "AdvancedOptions",
    ):
        if locals()[k] is not None:
            val = locals()[k]
            if isinstance(val, str):
                try:
                    val = salt.utils.json.loads(val)
                except ValueError as e:
                    return {
                        "updated": False,
                        "error": "Error parsing {}: {}".format(k, e.message),
                    }
            call_args[k] = val
    if "AccessPolicies" in call_args:
        call_args["AccessPolicies"] = salt.utils.json.dumps(call_args["AccessPolicies"])
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        domain = conn.update_elasticsearch_domain_config(
            DomainName=DomainName, **call_args
        )
        if not domain or "DomainConfig" not in domain:
            log.warning("Domain was not updated")
            return {"updated": False}
        return {"updated": True}
    except ClientError as e:
        return {"updated": False, "error": __utils__["boto3.get_error"](e)}


def add_tags(
    DomainName=None, ARN=None, region=None, key=None, keyid=None, profile=None, **kwargs
):
    """
    Add tags to a domain

    Returns {tagged: true} if the domain was tagged and returns
    {tagged: False} if the domain was not tagged.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticsearch_domain.add_tags mydomain tag_a=tag_value tag_b=tag_value

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        tagslist = []
        for k, v in kwargs.items():
            if str(k).startswith("__"):
                continue
            tagslist.append({"Key": str(k), "Value": str(v)})
        if ARN is None:
            if DomainName is None:
                raise SaltInvocationError(
                    "One (but not both) of ARN or " "domain must be specified."
                )
            domaindata = status(
                DomainName=DomainName,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if not domaindata or "domain" not in domaindata:
                log.warning("Domain tags not updated")
                return {"tagged": False}
            ARN = domaindata.get("domain", {}).get("ARN")
        elif DomainName is not None:
            raise SaltInvocationError(
                "One (but not both) of ARN or " "domain must be specified."
            )
        conn.add_tags(ARN=ARN, TagList=tagslist)
        return {"tagged": True}
    except ClientError as e:
        return {"tagged": False, "error": __utils__["boto3.get_error"](e)}


def remove_tags(
    TagKeys, DomainName=None, ARN=None, region=None, key=None, keyid=None, profile=None
):
    """
    Remove tags from a trail

    Returns {tagged: true} if the trail was tagged and returns
    {tagged: False} if the trail was not tagged.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudtrail.remove_tags my_trail tag_a=tag_value tag_b=tag_value

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if ARN is None:
            if DomainName is None:
                raise SaltInvocationError(
                    "One (but not both) of ARN or " "domain must be specified."
                )
            domaindata = status(
                DomainName=DomainName,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if not domaindata or "domain" not in domaindata:
                log.warning("Domain tags not updated")
                return {"tagged": False}
            ARN = domaindata.get("domain", {}).get("ARN")
        elif DomainName is not None:
            raise SaltInvocationError(
                "One (but not both) of ARN or " "domain must be specified."
            )
        conn.remove_tags(ARN=domaindata.get("domain", {}).get("ARN"), TagKeys=TagKeys)
        return {"tagged": True}
    except ClientError as e:
        return {"tagged": False, "error": __utils__["boto3.get_error"](e)}


def list_tags(
    DomainName=None, ARN=None, region=None, key=None, keyid=None, profile=None
):
    """
    List tags of a trail

    Returns:
        tags:
          - {...}
          - {...}

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudtrail.list_tags my_trail

    """

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if ARN is None:
            if DomainName is None:
                raise SaltInvocationError(
                    "One (but not both) of ARN or " "domain must be specified."
                )
            domaindata = status(
                DomainName=DomainName,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
            )
            if not domaindata or "domain" not in domaindata:
                log.warning("Domain tags not updated")
                return {"tagged": False}
            ARN = domaindata.get("domain", {}).get("ARN")
        elif DomainName is not None:
            raise SaltInvocationError(
                "One (but not both) of ARN or " "domain must be specified."
            )
        ret = conn.list_tags(ARN=ARN)
        log.warning(ret)
        tlist = ret.get("TagList", [])
        tagdict = {}
        for tag in tlist:
            tagdict[tag.get("Key")] = tag.get("Value")
        return {"tags": tagdict}
    except ClientError as e:
        return {"error": __utils__["boto3.get_error"](e)}
