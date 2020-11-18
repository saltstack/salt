"""
Connection module for Amazon Elasticsearch Service

.. versionadded:: Natrium

:configuration: This module accepts explicit IAM credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        es.keyid: GKTADJGHEIQSXMKKRBJ08H
        es.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        es.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

    All methods return a dict with:
        'result' key containing a boolean indicating success or failure,
        'error' key containing the errormessage returned by boto on error,
        'response' key containing the data of the response returned by boto on success.

:codeauthor: Herbert Buurman <herbert.buurman@ogd.nl>
:depends: boto3
"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602


import logging

import salt.utils.compat
import salt.utils.json
import salt.utils.versions
from salt.exceptions import SaltInvocationError
from salt.utils.decorators import depends

try:
    # Disable unused import-errors as these are only used for dependency checking
    # pylint: disable=unused-import
    import boto3
    import botocore

    # pylint: enable=unused-import
    from botocore.exceptions import ClientError, ParamValidationError, WaiterError

    logging.getLogger("boto3").setLevel(logging.INFO)
except ImportError:
    pass

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    """
    return salt.utils.versions.check_boto_reqs(boto3_ver="1.2.7")


def __init__(opts):
    _ = opts
    __utils__["boto3.assign_funcs"](__name__, "es")


def add_tags(
    domain_name=None,
    arn=None,
    tags=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Attaches tags to an existing Elasticsearch domain.
    Tags are a set of case-sensitive key value pairs.
    An Elasticsearch domain may have up to 10 tags.

    :param str domain_name: The name of the Elasticsearch domain you want to add tags to.
    :param str arn: The ARN of the Elasticsearch domain you want to add tags to.
        Specifying this overrides ``domain_name``.
    :param dict tags: The dict of tags to add to the Elasticsearch domain.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_elasticsearch.add_tags domain_name=mydomain tags='{"foo": "bar", "baz": "qux"}'
    """
    if not any((arn, domain_name)):
        raise SaltInvocationError(
            "At least one of domain_name or arn must be specified."
        )
    ret = {"result": False}
    if arn is None:
        res = describe_elasticsearch_domain(
            domain_name=domain_name,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if "error" in res:
            ret.update(res)
        elif not res["result"]:
            ret.update(
                {
                    "error": 'The domain with name "{}" does not exist.'.format(
                        domain_name
                    )
                }
            )
        else:
            arn = res["response"].get("ARN")
    if arn:
        boto_params = {
            "ARN": arn,
            "TagList": [{"Key": k, "Value": tags[k]} for k in tags or {}.items()],
        }
        try:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            conn.add_tags(**boto_params)
            ret["result"] = True
        except (ParamValidationError, ClientError) as exp:
            ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.12.21")
def cancel_elasticsearch_service_software_update(
    domain_name, region=None, keyid=None, key=None, profile=None
):
    """
    Cancels a scheduled service software update for an Amazon ES domain. You can
    only perform this operation before the AutomatedUpdateDate and when the UpdateStatus
    is in the PENDING_UPDATE state.

    :param str domain_name: The name of the domain that you want to stop the latest
        service software update on.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with the current service software options.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = conn.cancel_elasticsearch_service_software_update(DomainName=domain_name)
        ret["result"] = True
        res["response"] = res["ServiceSoftwareOptions"]
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def create_elasticsearch_domain(
    domain_name,
    elasticsearch_version=None,
    elasticsearch_cluster_config=None,
    ebs_options=None,
    access_policies=None,
    snapshot_options=None,
    vpc_options=None,
    cognito_options=None,
    encryption_at_rest_options=None,
    node_to_node_encryption_options=None,
    advanced_options=None,
    log_publishing_options=None,
    blocking=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Given a valid config, create a domain.

    :param str domain_name: The name of the Elasticsearch domain that you are creating.
        Domain names are unique across the domains owned by an account within an
        AWS region. Domain names must start with a letter or number and can contain
        the following characters: a-z (lowercase), 0-9, and - (hyphen).
    :param str elasticsearch_version: String of format X.Y to specify version for
        the Elasticsearch domain eg. "1.5" or "2.3".
    :param dict elasticsearch_cluster_config: Dictionary specifying the configuration
        options for an Elasticsearch domain. Keys (case sensitive) in here are:

        - InstanceType (str): The instance type for an Elasticsearch cluster.
        - InstanceCount (int): The instance type for an Elasticsearch cluster.
        - DedicatedMasterEnabled (bool): Indicate whether a dedicated master
          node is enabled.
        - ZoneAwarenessEnabled (bool): Indicate whether zone awareness is enabled.
          If this is not enabled, the Elasticsearch domain will only be in one
          availability zone.
        - ZoneAwarenessConfig (dict): Specifies the zone awareness configuration
          for a domain when zone awareness is enabled.
          Keys (case sensitive) in here are:

          - AvailabilityZoneCount (int): An integer value to indicate the
            number of availability zones for a domain when zone awareness is
            enabled. This should be equal to number of subnets if VPC endpoints
            is enabled. Allowed values: 2, 3

        - DedicatedMasterType (str): The instance type for a dedicated master node.
        - DedicatedMasterCount (int): Total number of dedicated master nodes,
          active and on standby, for the cluster.
    :param dict ebs_options: Dict specifying the options to enable or disable and
        specifying the type and size of EBS storage volumes.
        Keys (case sensitive) in here are:

        - EBSEnabled (bool): Specifies whether EBS-based storage is enabled.
        - VolumeType (str): Specifies the volume type for EBS-based storage.
        - VolumeSize (int): Integer to specify the size of an EBS volume.
        - Iops (int): Specifies the IOPD for a Provisioned IOPS EBS volume (SSD).
    :type access_policies: str or dict
    :param access_policies: Dict or JSON string with the IAM access policy.
    :param dict snapshot_options: Dict specifying the snapshot options.
        Keys (case sensitive) in here are:

        - AutomatedSnapshotStartHour (int): Specifies the time, in UTC format,
          when the service takes a daily automated snapshot of the specified
          Elasticsearch domain. Default value is 0 hours.
    :param dict vpc_options: Dict with the options to specify the subnets and security
        groups for the VPC endpoint.
        Keys (case sensitive) in here are:

        - SubnetIds (list): The list of subnets for the VPC endpoint.
        - SecurityGroupIds (list): The list of security groups for the VPC endpoint.
    :param dict cognito_options: Dict with options to specify the cognito user and
        identity pools for Kibana authentication.
        Keys (case sensitive) in here are:

        - Enabled (bool): Specifies the option to enable Cognito for Kibana authentication.
        - UserPoolId (str): Specifies the Cognito user pool ID for Kibana authentication.
        - IdentityPoolId (str): Specifies the Cognito identity pool ID for Kibana authentication.
        - RoleArn (str): Specifies the role ARN that provides Elasticsearch permissions
          for accessing Cognito resources.
    :param dict encryption_at_rest_options: Dict specifying the encryption at rest
        options. Keys (case sensitive) in here are:

        - Enabled (bool): Specifies the option to enable Encryption At Rest.
        - KmsKeyId (str): Specifies the KMS Key ID for Encryption At Rest options.
    :param dict node_to_node_encryption_options: Dict specifying the node to node
        encryption options. Keys (case sensitive) in here are:

        - Enabled (bool): Specify True to enable node-to-node encryption.
    :param dict advanced_options: Dict with option to allow references to indices
        in an HTTP request body. Must be False when configuring access to individual
        sub-resources. By default, the value is True.
        See http://docs.aws.amazon.com/elasticsearch-service/latest/developerguide\
        /es-createupdatedomains.html#es-createdomain-configure-advanced-options
        for more information.
    :param dict log_publishing_options: Dict with options for various type of logs.
        The keys denote the type of log file and can be one of the following:

        - INDEX_SLOW_LOGS
        - SEARCH_SLOW_LOGS
        - ES_APPLICATION_LOGS

        The value assigned to each key is a dict with the following case sensitive keys:

        - CloudWatchLogsLogGroupArn (str): The ARN of the Cloudwatch log
          group to which the log needs to be published.
        - Enabled (bool): Specifies whether given log publishing option is enabled or not.
    :param bool blocking: Whether or not to wait (block) until the Elasticsearch
        domain has been created.

    Note: Not all instance types allow enabling encryption at rest. See https://docs.aws.amazon.com\
        /elasticsearch-service/latest/developerguide/aes-supported-instance-types.html

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with the domain status configuration.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_elasticsearch.create_elasticsearch_domain mydomain \\
        elasticsearch_cluster_config='{ \\
          "InstanceType": "t2.micro.elasticsearch", \\
          "InstanceCount": 1, \\
          "DedicatedMasterEnabled": False, \\
          "ZoneAwarenessEnabled": False}' \\
        ebs_options='{ \\
          "EBSEnabled": True, \\
          "VolumeType": "gp2", \\
          "VolumeSize": 10, \\
          "Iops": 0}' \\
        access_policies='{ \\
          "Version": "2012-10-17", \\
          "Statement": [ \\
            {"Effect": "Allow", \\
             "Principal": {"AWS": "*"}, \\
             "Action": "es:*", \\
             "Resource": "arn:aws:es:us-east-1:111111111111:domain/mydomain/*", \\
             "Condition": {"IpAddress": {"aws:SourceIp": ["127.0.0.1"]}}}]}' \\
        snapshot_options='{"AutomatedSnapshotStartHour": 0}' \\
        advanced_options='{"rest.action.multi.allow_explicit_index": "true"}'
    """
    boto_kwargs = salt.utils.data.filter_falsey(
        {
            "DomainName": domain_name,
            "ElasticsearchVersion": str(elasticsearch_version or ""),
            "ElasticsearchClusterConfig": elasticsearch_cluster_config,
            "EBSOptions": ebs_options,
            "AccessPolicies": (
                salt.utils.json.dumps(access_policies)
                if isinstance(access_policies, dict)
                else access_policies
            ),
            "SnapshotOptions": snapshot_options,
            "VPCOptions": vpc_options,
            "CognitoOptions": cognito_options,
            "EncryptionAtRestOptions": encryption_at_rest_options,
            "NodeToNodeEncryptionOptions": node_to_node_encryption_options,
            "AdvancedOptions": advanced_options,
            "LogPublishingOptions": log_publishing_options,
        }
    )
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        res = conn.create_elasticsearch_domain(**boto_kwargs)
        if res and "DomainStatus" in res:
            ret["result"] = True
            ret["response"] = res["DomainStatus"]
        if blocking:
            waiter = __utils__["boto3_elasticsearch.get_waiter"](
                conn, waiter="ESDomainAvailable"
            )
            waiter.wait(DomainName=domain_name)
    except (ParamValidationError, ClientError, WaiterError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def delete_elasticsearch_domain(
    domain_name, blocking=False, region=None, key=None, keyid=None, profile=None
):
    """
    Permanently deletes the specified Elasticsearch domain and all of its data.
    Once a domain is deleted, it cannot be recovered.

    :param str domain_name: The name of the domain to delete.
    :param bool blocking: Whether or not to wait (block) until the Elasticsearch
        domain has been deleted.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_elasticsearch_domain(DomainName=domain_name)
        ret["result"] = True
        if blocking:
            waiter = __utils__["boto3_elasticsearch.get_waiter"](
                conn, waiter="ESDomainDeleted"
            )
            waiter.wait(DomainName=domain_name)
    except (ParamValidationError, ClientError, WaiterError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.7.30")
def delete_elasticsearch_service_role(region=None, keyid=None, key=None, profile=None):
    """
    Deletes the service-linked role that Elasticsearch Service uses to manage and
    maintain VPC domains. Role deletion will fail if any existing VPC domains use
    the role. You must delete any such Elasticsearch domains before deleting the role.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        conn.delete_elasticsearch_service_role()
        ret["result"] = True
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def describe_elasticsearch_domain(
    domain_name, region=None, keyid=None, key=None, profile=None
):
    """
    Given a domain name gets its status description.

    :param str domain_name: The name of the domain to get the status of.

    :rtype: dict
    :return: Dictionary ith key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with the domain status information.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        res = conn.describe_elasticsearch_domain(DomainName=domain_name)
        if res and "DomainStatus" in res:
            ret["result"] = True
            ret["response"] = res["DomainStatus"]
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def describe_elasticsearch_domain_config(
    domain_name, region=None, keyid=None, key=None, profile=None
):
    """
    Provides cluster configuration information about the specified Elasticsearch domain,
    such as the state, creation date, update version, and update date for cluster options.

    :param str domain_name: The name of the domain to describe.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with the current configuration information.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        res = conn.describe_elasticsearch_domain_config(DomainName=domain_name)
        if res and "DomainConfig" in res:
            ret["result"] = True
            ret["response"] = res["DomainConfig"]
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def describe_elasticsearch_domains(
    domain_names, region=None, keyid=None, key=None, profile=None
):
    """
    Returns domain configuration information about the specified Elasticsearch
    domains, including the domain ID, domain endpoint, and domain ARN.

    :param list domain_names: List of domain names to get information for.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with the list of domain status information.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_elasticsearch.describe_elasticsearch_domains '["domain_a", "domain_b"]'
    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = conn.describe_elasticsearch_domains(DomainNames=domain_names)
        if res and "DomainStatusList" in res:
            ret["result"] = True
            ret["response"] = res["DomainStatusList"]
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.5.18")
def describe_elasticsearch_instance_type_limits(
    instance_type,
    elasticsearch_version,
    domain_name=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Describe Elasticsearch Limits for a given InstanceType and ElasticsearchVersion.
    When modifying existing Domain, specify the `` DomainName `` to know what Limits
    are supported for modifying.

    :param str instance_type: The instance type for an Elasticsearch cluster for
        which Elasticsearch ``Limits`` are needed.
    :param str elasticsearch_version: Version of Elasticsearch for which ``Limits``
        are needed.
    :param str domain_name: Represents the name of the Domain that we are trying
        to modify. This should be present only if we are querying for Elasticsearch
        ``Limits`` for existing domain.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with the limits information.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_elasticsearch.describe_elasticsearch_instance_type_limits \\
          instance_type=r3.8xlarge.elasticsearch \\
          elasticsearch_version='6.2'
    """
    ret = {"result": False}
    boto_params = salt.utils.data.filter_falsey(
        {
            "DomainName": domain_name,
            "InstanceType": instance_type,
            "ElasticsearchVersion": str(elasticsearch_version),
        }
    )
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = conn.describe_elasticsearch_instance_type_limits(**boto_params)
        if res and "LimitsByRole" in res:
            ret["result"] = True
            ret["response"] = res["LimitsByRole"]
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.10.15")
def describe_reserved_elasticsearch_instance_offerings(
    reserved_elasticsearch_instance_offering_id=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Lists available reserved Elasticsearch instance offerings.

    :param str reserved_elasticsearch_instance_offering_id: The offering identifier
        filter value. Use this parameter to show only the available offering that
        matches the specified reservation identifier.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with the list of offerings information.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        boto_params = {
            "ReservedElasticsearchInstanceOfferingId": reserved_elasticsearch_instance_offering_id
        }
        res = []
        for page in conn.get_paginator(
            "describe_reserved_elasticsearch_instance_offerings"
        ).paginate(**boto_params):
            res.extend(page["ReservedElasticsearchInstanceOfferings"])
        if res:
            ret["result"] = True
            ret["response"] = res
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.10.15")
def describe_reserved_elasticsearch_instances(
    reserved_elasticsearch_instance_id=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Returns information about reserved Elasticsearch instances for this account.

    :param str reserved_elasticsearch_instance_id: The reserved instance identifier
        filter value. Use this parameter to show only the reservation that matches
        the specified reserved Elasticsearch instance ID.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with a list of information on
        reserved instances.
        Upon failure, also contains a key 'error' with the error message as value.

    :note: Version 1.9.174 of boto3 has a bug in that reserved_elasticsearch_instance_id
        is considered a required argument, even though the documentation says otherwise.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        boto_params = {
            "ReservedElasticsearchInstanceId": reserved_elasticsearch_instance_id,
        }
        res = []
        for page in conn.get_paginator(
            "describe_reserved_elasticsearch_instances"
        ).paginate(**boto_params):
            res.extend(page["ReservedElasticsearchInstances"])
        if res:
            ret["result"] = True
            ret["response"] = res
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.10.77")
def get_compatible_elasticsearch_versions(
    domain_name=None, region=None, keyid=None, key=None, profile=None
):
    """
    Returns a list of upgrade compatible Elastisearch versions. You can optionally
    pass a ``domain_name`` to get all upgrade compatible Elasticsearch versions
    for that specific domain.

    :param str domain_name: The name of an Elasticsearch domain.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with a list of compatible versions.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    boto_params = salt.utils.data.filter_falsey({"DomainName": domain_name})
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = conn.get_compatible_elasticsearch_versions(**boto_params)
        if res and "CompatibleElasticsearchVersions" in res:
            ret["result"] = True
            ret["response"] = res["CompatibleElasticsearchVersions"]
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.10.77")
def get_upgrade_history(domain_name, region=None, keyid=None, key=None, profile=None):
    """
    Retrieves the complete history of the last 10 upgrades that were performed on the domain.

    :param str domain_name: The name of an Elasticsearch domain. Domain names are
        unique across the domains owned by an account within an AWS region. Domain
        names start with a letter or number and can contain the following characters:
        a-z (lowercase), 0-9, and - (hyphen).

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with a list of upgrade histories.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        boto_params = {"DomainName": domain_name}
        res = []
        for page in conn.get_paginator("get_upgrade_history").paginate(**boto_params):
            res.extend(page["UpgradeHistories"])
        if res:
            ret["result"] = True
            ret["response"] = res
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.10.77")
def get_upgrade_status(domain_name, region=None, keyid=None, key=None, profile=None):
    """
    Retrieves the latest status of the last upgrade or upgrade eligibility check
    that was performed on the domain.

    :param str domain_name: The name of an Elasticsearch domain. Domain names are
        unique across the domains owned by an account within an AWS region. Domain
        names start with a letter or number and can contain the following characters:
        a-z (lowercase), 0-9, and - (hyphen).

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with upgrade status information.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    boto_params = {"DomainName": domain_name}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = conn.get_upgrade_status(**boto_params)
        ret["result"] = True
        ret["response"] = res
        del res["ResponseMetadata"]
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def list_domain_names(region=None, keyid=None, key=None, profile=None):
    """
    Returns the name of all Elasticsearch domains owned by the current user's account.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with a list of domain names.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = conn.list_domain_names()
        if res and "DomainNames" in res:
            ret["result"] = True
            ret["response"] = [item["DomainName"] for item in res["DomainNames"]]
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.5.18")
def list_elasticsearch_instance_types(
    elasticsearch_version,
    domain_name=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    List all Elasticsearch instance types that are supported for given ElasticsearchVersion.

    :param str elasticsearch_version: Version of Elasticsearch for which list of
        supported elasticsearch instance types are needed.
    :param str domain_name: DomainName represents the name of the Domain that we
        are trying to modify. This should be present only if we are querying for
        list of available Elasticsearch instance types when modifying existing domain.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with a list of Elasticsearch instance types.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        boto_params = salt.utils.data.filter_falsey(
            {
                "ElasticsearchVersion": str(elasticsearch_version),
                "DomainName": domain_name,
            }
        )
        res = []
        for page in conn.get_paginator("list_elasticsearch_instance_types").paginate(
            **boto_params
        ):
            res.extend(page["ElasticsearchInstanceTypes"])
        if res:
            ret["result"] = True
            ret["response"] = res
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.5.18")
def list_elasticsearch_versions(region=None, keyid=None, key=None, profile=None):
    """
    List all supported Elasticsearch versions.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with a list of Elasticsearch versions.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = []
        for page in conn.get_paginator("list_elasticsearch_versions").paginate():
            res.extend(page["ElasticsearchVersions"])
        if res:
            ret["result"] = True
            ret["response"] = res
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def list_tags(
    domain_name=None, arn=None, region=None, key=None, keyid=None, profile=None
):
    """
    Returns all tags for the given Elasticsearch domain.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with a dict of tags.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    if not any((arn, domain_name)):
        raise SaltInvocationError(
            "At least one of domain_name or arn must be specified."
        )
    ret = {"result": False}
    if arn is None:
        res = describe_elasticsearch_domain(
            domain_name=domain_name,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if "error" in res:
            ret.update(res)
        elif not res["result"]:
            ret.update(
                {
                    "error": 'The domain with name "{}" does not exist.'.format(
                        domain_name
                    )
                }
            )
        else:
            arn = res["response"].get("ARN")
    if arn:
        try:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            res = conn.list_tags(ARN=arn)
            ret["result"] = True
            ret["response"] = {
                item["Key"]: item["Value"] for item in res.get("TagList", [])
            }
        except (ParamValidationError, ClientError) as exp:
            ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.10.15")
def purchase_reserved_elasticsearch_instance_offering(
    reserved_elasticsearch_instance_offering_id,
    reservation_name,
    instance_count=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Allows you to purchase reserved Elasticsearch instances.

    :param str reserved_elasticsearch_instance_offering_id: The ID of the reserved
        Elasticsearch instance offering to purchase.
    :param str reservation_name: A customer-specified identifier to track this reservation.
    :param int instance_count: The number of Elasticsearch instances to reserve.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with purchase information.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    boto_params = salt.utils.data.filter_falsey(
        {
            "ReservedElasticsearchInstanceOfferingId": reserved_elasticsearch_instance_offering_id,
            "ReservationName": reservation_name,
            "InstanceCount": instance_count,
        }
    )
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = conn.purchase_reserved_elasticsearch_instance_offering(**boto_params)
        if res:
            ret["result"] = True
            ret["response"] = res
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def remove_tags(
    tag_keys,
    domain_name=None,
    arn=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Removes the specified set of tags from the specified Elasticsearch domain.

    :param list tag_keys: List with tag keys you want to remove from the Elasticsearch domain.
    :param str domain_name: The name of the Elasticsearch domain you want to remove tags from.
    :param str arn: The ARN of the Elasticsearch domain you want to remove tags from.
        Specifying this overrides ``domain_name``.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_elasticsearch.remove_tags '["foo", "bar"]' domain_name=my_domain
    """
    if not any((arn, domain_name)):
        raise SaltInvocationError(
            "At least one of domain_name or arn must be specified."
        )
    ret = {"result": False}
    if arn is None:
        res = describe_elasticsearch_domain(
            domain_name=domain_name,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if "error" in res:
            ret.update(res)
        elif not res["result"]:
            ret.update(
                {
                    "error": 'The domain with name "{}" does not exist.'.format(
                        domain_name
                    )
                }
            )
        else:
            arn = res["response"].get("ARN")
    if arn:
        try:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            conn.remove_tags(ARN=arn, TagKeys=tag_keys)
            ret["result"] = True
        except (ParamValidationError, ClientError) as exp:
            ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.12.21")
def start_elasticsearch_service_software_update(
    domain_name, region=None, keyid=None, key=None, profile=None
):
    """
    Schedules a service software update for an Amazon ES domain.

    :param str domain_name: The name of the domain that you want to update to the
        latest service software.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with service software information.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    boto_params = {"DomainName": domain_name}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = conn.start_elasticsearch_service_software_update(**boto_params)
        if res and "ServiceSoftwareOptions" in res:
            ret["result"] = True
            ret["response"] = res["ServiceSoftwareOptions"]
    except (ParamValidationError, ClientError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def update_elasticsearch_domain_config(
    domain_name,
    elasticsearch_cluster_config=None,
    ebs_options=None,
    vpc_options=None,
    access_policies=None,
    snapshot_options=None,
    cognito_options=None,
    advanced_options=None,
    log_publishing_options=None,
    blocking=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Modifies the cluster configuration of the specified Elasticsearch domain,
    for example setting the instance type and the number of instances.

    :param str domain_name: The name of the Elasticsearch domain that you are creating.
        Domain names are unique across the domains owned by an account within an
        AWS region. Domain names must start with a letter or number and can contain
        the following characters: a-z (lowercase), 0-9, and - (hyphen).
    :param dict elasticsearch_cluster_config: Dictionary specifying the configuration
        options for an Elasticsearch domain. Keys (case sensitive) in here are:

        - InstanceType (str): The instance type for an Elasticsearch cluster.
        - InstanceCount (int): The instance type for an Elasticsearch cluster.
        - DedicatedMasterEnabled (bool): Indicate whether a dedicated master
          node is enabled.
        - ZoneAwarenessEnabled (bool): Indicate whether zone awareness is enabled.
        - ZoneAwarenessConfig (dict): Specifies the zone awareness configuration
          for a domain when zone awareness is enabled.
          Keys (case sensitive) in here are:

          - AvailabilityZoneCount (int): An integer value to indicate the
            number of availability zones for a domain when zone awareness is
            enabled. This should be equal to number of subnets if VPC endpoints
            is enabled.

        - DedicatedMasterType (str): The instance type for a dedicated master node.
        - DedicatedMasterCount (int): Total number of dedicated master nodes,
          active and on standby, for the cluster.
    :param dict ebs_options: Dict specifying the options to enable or disable and
        specifying the type and size of EBS storage volumes.
        Keys (case sensitive) in here are:

        - EBSEnabled (bool): Specifies whether EBS-based storage is enabled.
        - VolumeType (str): Specifies the volume type for EBS-based storage.
        - VolumeSize (int): Integer to specify the size of an EBS volume.
        - Iops (int): Specifies the IOPD for a Provisioned IOPS EBS volume (SSD).
    :param dict snapshot_options: Dict specifying the snapshot options.
        Keys (case sensitive) in here are:

        - AutomatedSnapshotStartHour (int): Specifies the time, in UTC format,
          when the service takes a daily automated snapshot of the specified
          Elasticsearch domain. Default value is 0 hours.
    :param dict vpc_options: Dict with the options to specify the subnets and security
        groups for the VPC endpoint.
        Keys (case sensitive) in here are:

        - SubnetIds (list): The list of subnets for the VPC endpoint.
        - SecurityGroupIds (list): The list of security groups for the VPC endpoint.
    :param dict cognito_options: Dict with options to specify the cognito user and
        identity pools for Kibana authentication.
        Keys (case sensitive) in here are:

        - Enabled (bool): Specifies the option to enable Cognito for Kibana authentication.
        - UserPoolId (str): Specifies the Cognito user pool ID for Kibana authentication.
        - IdentityPoolId (str): Specifies the Cognito identity pool ID for Kibana authentication.
        - RoleArn (str): Specifies the role ARN that provides Elasticsearch permissions
          for accessing Cognito resources.
    :param dict advanced_options: Dict with option to allow references to indices
        in an HTTP request body. Must be False when configuring access to individual
        sub-resources. By default, the value is True.
        See http://docs.aws.amazon.com/elasticsearch-service/latest/developerguide\
        /es-createupdatedomains.html#es-createdomain-configure-advanced-options
        for more information.
    :param str/dict access_policies: Dict or JSON string with the IAM access policy.
    :param dict log_publishing_options: Dict with options for various type of logs.
        The keys denote the type of log file and can be one of the following:

            INDEX_SLOW_LOGS, SEARCH_SLOW_LOGS, ES_APPLICATION_LOGS.

        The value assigned to each key is a dict with the following case sensitive keys:

        - CloudWatchLogsLogGroupArn (str): The ARN of the Cloudwatch log
          group to which the log needs to be published.
        - Enabled (bool): Specifies whether given log publishing option
          is enabled or not.
    :param bool blocking: Whether or not to wait (block) until the Elasticsearch
        domain has been updated.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with the domain configuration.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_elasticsearch.update_elasticsearch_domain_config mydomain \\
          elasticsearch_cluster_config='{\\
            "InstanceType": "t2.micro.elasticsearch", \\
            "InstanceCount": 1, \\
            "DedicatedMasterEnabled": false,
            "ZoneAwarenessEnabled": false}' \\
          ebs_options='{\\
            "EBSEnabled": true, \\
            "VolumeType": "gp2", \\
            "VolumeSize": 10, \\
            "Iops": 0}' \\
          access_policies='{"Version": "2012-10-17", "Statement": [{\\
            "Effect": "Allow", "Principal": {"AWS": "*"}, "Action": "es:*", \\
            "Resource": "arn:aws:es:us-east-1:111111111111:domain/mydomain/*", \\
            "Condition": {"IpAddress": {"aws:SourceIp": ["127.0.0.1"]}}}]}' \\
          snapshot_options='{"AutomatedSnapshotStartHour": 0}' \\
          advanced_options='{"rest.action.multi.allow_explicit_index": "true"}'
    """
    ret = {"result": False}
    boto_kwargs = salt.utils.data.filter_falsey(
        {
            "DomainName": domain_name,
            "ElasticsearchClusterConfig": elasticsearch_cluster_config,
            "EBSOptions": ebs_options,
            "SnapshotOptions": snapshot_options,
            "VPCOptions": vpc_options,
            "CognitoOptions": cognito_options,
            "AdvancedOptions": advanced_options,
            "AccessPolicies": (
                salt.utils.json.dumps(access_policies)
                if isinstance(access_policies, dict)
                else access_policies
            ),
            "LogPublishingOptions": log_publishing_options,
        }
    )
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = conn.update_elasticsearch_domain_config(**boto_kwargs)
        if not res or "DomainConfig" not in res:
            log.warning("Domain was not updated")
        else:
            ret["result"] = True
            ret["response"] = res["DomainConfig"]
        if blocking:
            waiter = __utils__["boto3_elasticsearch.get_waiter"](
                conn, waiter="ESDomainAvailable"
            )
            waiter.wait(DomainName=domain_name)
    except (ParamValidationError, ClientError, WaiterError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.10.77")
def upgrade_elasticsearch_domain(
    domain_name,
    target_version,
    perform_check_only=None,
    blocking=False,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Allows you to either upgrade your domain or perform an Upgrade eligibility
    check to a compatible Elasticsearch version.

    :param str domain_name: The name of an Elasticsearch domain. Domain names are
        unique across the domains owned by an account within an AWS region. Domain
        names start with a letter or number and can contain the following characters:
        a-z (lowercase), 0-9, and - (hyphen).
    :param str target_version: The version of Elasticsearch that you intend to
        upgrade the domain to.
    :param bool perform_check_only: This flag, when set to True, indicates that
        an Upgrade Eligibility Check needs to be performed. This will not actually
        perform the Upgrade.
    :param bool blocking: Whether or not to wait (block) until the Elasticsearch
        domain has been upgraded.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with the domain configuration.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_elasticsearch.upgrade_elasticsearch_domain mydomain \\
        target_version='6.7' \\
        perform_check_only=True
    """
    ret = {"result": False}
    boto_params = salt.utils.data.filter_falsey(
        {
            "DomainName": domain_name,
            "TargetVersion": str(target_version),
            "PerformCheckOnly": perform_check_only,
        }
    )
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        res = conn.upgrade_elasticsearch_domain(**boto_params)
        if res:
            ret["result"] = True
            ret["response"] = res
        if blocking:
            waiter = __utils__["boto3_elasticsearch.get_waiter"](
                conn, waiter="ESUpgradeFinished"
            )
            waiter.wait(DomainName=domain_name)
    except (ParamValidationError, ClientError, WaiterError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def exists(domain_name, region=None, key=None, keyid=None, profile=None):
    """
    Given a domain name, check to see if the given domain exists.

    :param str domain_name: The name of the domain to check.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.describe_elasticsearch_domain(DomainName=domain_name)
        ret["result"] = True
    except (ParamValidationError, ClientError) as exp:
        if exp.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


def wait_for_upgrade(domain_name, region=None, keyid=None, key=None, profile=None):
    """
    Block until an upgrade-in-progress for domain ``name`` is finished.

    :param str name: The name of the domain to wait for.

    :rtype dict:
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    """
    ret = {"result": False}
    try:
        conn = _get_conn(region=region, keyid=keyid, key=key, profile=profile)
        waiter = __utils__["boto3_elasticsearch.get_waiter"](
            conn, waiter="ESUpgradeFinished"
        )
        waiter.wait(DomainName=domain_name)
        ret["result"] = True
    except (ParamValidationError, ClientError, WaiterError) as exp:
        ret.update({"error": __utils__["boto3.get_error"](exp)["message"]})
    return ret


@depends("botocore", version="1.10.77")
def check_upgrade_eligibility(
    domain_name, elasticsearch_version, region=None, keyid=None, key=None, profile=None
):
    """
    Helper function to determine in one call if an Elasticsearch domain can be
    upgraded to the specified Elasticsearch version.

    This assumes that the Elasticsearch domain is at rest at the moment this function
    is called. I.e. The domain is not in the process of :

    - being created.
    - being updated.
    - another upgrade running, or a check thereof.
    - being deleted.

    Behind the scenes, this does 3 things:

    - Check if ``elasticsearch_version`` is among the compatible elasticsearch versions.
    - Perform a check if the Elasticsearch domain is eligible for the upgrade.
    - Check the result of the check and return the result as a boolean.

    :param str name: The Elasticsearch domain name to check.
    :param str elasticsearch_version: The Elasticsearch version to upgrade to.

    :rtype: dict
    :return: Dictionary with key 'result' and as value a boolean denoting success or failure.
        Upon success, also contains a key 'reponse' with boolean result of the check.
        Upon failure, also contains a key 'error' with the error message as value.

    .. versionadded:: Natrium

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_elasticsearch.check_upgrade_eligibility mydomain '6.7'
    """
    ret = {"result": False}
    # Check if the desired version is in the list of compatible versions
    res = get_compatible_elasticsearch_versions(
        domain_name, region=region, keyid=keyid, key=key, profile=profile
    )
    if "error" in res:
        return res
    compatible_versions = res["response"][0]["TargetVersions"]
    if str(elasticsearch_version) not in compatible_versions:
        ret["result"] = True
        ret["response"] = False
        ret["error"] = 'Desired version "{}" not in compatible versions: {}.' "".format(
            elasticsearch_version, compatible_versions
        )
        return ret
    # Check if the domain is eligible to upgrade to the desired version
    res = upgrade_elasticsearch_domain(
        domain_name,
        elasticsearch_version,
        perform_check_only=True,
        blocking=True,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )
    if "error" in res:
        return res
    res = wait_for_upgrade(
        domain_name, region=region, keyid=keyid, key=key, profile=profile
    )
    if "error" in res:
        return res
    res = get_upgrade_status(
        domain_name, region=region, keyid=keyid, key=key, profile=profile
    )
    ret["result"] = True
    ret["response"] = (
        res["response"]["UpgradeStep"] == "PRE_UPGRADE_CHECK"
        and res["response"]["StepStatus"] == "SUCCEEDED"
    )
    return ret
