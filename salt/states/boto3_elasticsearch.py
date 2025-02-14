"""
Manage Elasticsearch Service
============================

.. versionadded:: 3001

:configuration: This module accepts explicit AWS credentials but can also
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

:codeauthor: Herbert Buurman <herbert.buurman@ogd.nl>
:depends: boto3
"""

import logging

import salt.utils.json
from salt.utils.versions import Version

log = logging.getLogger(__name__)
__virtualname__ = "boto3_elasticsearch"


def __virtual__():
    """
    Only load if boto3 and the required module functions are available.
    """
    requirements = {
        "salt": [
            "boto3_elasticsearch.describe_elasticsearch_domain",
            "boto3_elasticsearch.create_elasticsearch_domain",
            "boto3_elasticsearch.update_elasticsearch_domain_config",
            "boto3_elasticsearch.exists",
            "boto3_elasticsearch.get_upgrade_status",
            "boto3_elasticsearch.wait_for_upgrade",
            "boto3_elasticsearch.check_upgrade_eligibility",
            "boto3_elasticsearch.upgrade_elasticsearch_domain",
        ],
    }
    for req in requirements["salt"]:
        if req not in __salt__:
            return (
                False,
                f"A required function was not found in __salt__: {req}",
            )
    return __virtualname__


def _check_return_value(ret):
    """
    Helper function to check if the 'result' key of the return value has been
    properly set. This is to detect unexpected code-paths that would otherwise
    return a 'success'-y value but not actually be successful.

    :param dict ret: The returned value of a state function.
    """
    if ret["result"] == "oops":
        ret["result"] = False
        ret["comment"].append(
            "An internal error has occurred: The result value was not properly changed."
        )
    return ret


def present(
    name,
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
    blocking=True,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Ensure an Elasticsearch Domain exists.

    :param str name: The name of the Elasticsearch domain that you are creating.
        Domain names are unique across the domains owned by an account within an
        AWS region. Domain names must start with a letter or number and can contain
        the following characters: a-z (lowercase), 0-9, and - (hyphen).
    :param str elasticsearch_version: String of format X.Y to specify version for
        the Elasticsearch domain eg. "1.5" or "2.3".
    :param dict elasticsearch_cluster_config: Dict specifying the configuration
        options for an Elasticsearch domain.
        Keys (case sensitive) in here are:

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
    :type access_policies: str or dict
    :param access_policies: Dict or JSON string with the IAM access policy.
    :param dict snapshot_options: Dict specifying the snapshot options.
        Keys (case senstive) in here are:

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
        Keys (case senstive) in here are:

        - Enabled (bool): Specifies the option to enable Cognito for Kibana authentication.
        - UserPoolId (str): Specifies the Cognito user pool ID for Kibana authentication.
        - IdentityPoolId (str): Specifies the Cognito identity pool ID for Kibana authentication.
        - RoleArn (str): Specifies the role ARN that provides Elasticsearch permissions
          for accessing Cognito resources.
    :param dict encryption_at_rest_options: Dict specifying the encryption at rest
        options. This option can only be used for the creation of a new Elasticsearch
        domain.
        Keys (case sensitive) in here are:

        - Enabled (bool): Specifies the option to enable Encryption At Rest.
        - KmsKeyId (str): Specifies the KMS Key ID for Encryption At Rest options.
    :param dict node_to_node_encryption_options: Dict specifying the node to node
        encryption options. This option can only be used for the creation of
        a new Elasticsearch domain.
        Keys (case sensitive) in here are:

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
    :param bool blocking: Whether or not the state should wait for all operations
        (create/update/upgrade) to be completed. Default: ``True``
    :param dict tags: Dict of tags to ensure are present on the Elasticsearch domain.

    .. versionadded:: 3001

    Example:

    This will create an elasticsearch domain consisting of a single t2.small instance
    in the eu-west-1 region (Ireland) and will wait until the instance is available
    before returning from the state.

    .. code-block:: yaml

        Create new domain:
          boto3_elasticsearch.present:
          - name: my_domain
          - elasticsearch_version: '5.1'
          - elasticsearch_cluster_config:
              InstanceType: t2.small.elasticsearch
              InstanceCount: 1
              DedicatedMasterEnabled: False
              ZoneAwarenessEnabled: False
          - ebs_options:
              EBSEnabled: True
              VolumeType: gp2
              VolumeSize: 10
          - snapshot_options:
              AutomatedSnapshotStartHour: 3
          - vpc_options:
              SubnetIds:
              - subnet-12345678
              SecurityGroupIds:
              - sg-12345678
          - node_to_node_encryption_options:
              Enabled: False
          - region: eu-west-1
          - tags:
              foo: bar
              baz: qux
    """
    ret = {"name": name, "result": "oops", "comment": [], "changes": {}}

    action = None
    current_domain = None
    target_conf = salt.utils.data.filter_falsey(
        {
            "DomainName": name,
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
            "AdvancedOptions": advanced_options,
            "LogPublishingOptions": log_publishing_options,
        },
        recurse_depth=3,
    )
    res = __salt__["boto3_elasticsearch.describe_elasticsearch_domain"](
        name, region=region, keyid=keyid, key=key, profile=profile
    )
    if not res["result"]:
        ret["result"] = False
        if "ResourceNotFoundException" in res["error"]:
            action = "create"
            config_diff = {"old": None, "new": target_conf}
        else:
            ret["comment"].append(res["error"])
    else:
        current_domain = salt.utils.data.filter_falsey(res["response"], recurse_depth=3)
        current_domain_version = current_domain["ElasticsearchVersion"]
        # Remove some values from current_domain that cannot be updated
        for item in [
            "DomainId",
            "UpgradeProcessing",
            "Created",
            "Deleted",
            "Processing",
            "Endpoints",
            "ARN",
            "EncryptionAtRestOptions",
            "NodeToNodeEncryptionOptions",
            "ElasticsearchVersion",
            "ServiceSoftwareOptions",
        ]:
            if item in current_domain:
                del current_domain[item]
        # Further remove values from VPCOptions (if present) that are read-only
        for item in ["VPCId", "AvailabilityZones"]:
            if item in current_domain.get("VPCOptions", {}):
                del current_domain["VPCOptions"][item]
        # Some special cases
        if "CognitoOptions" in current_domain:
            if (
                "CognitoOptions" not in target_conf
                and not current_domain["CognitoOptions"]["Enabled"]
            ):
                del current_domain["CognitoOptions"]
        if (
            "AdvancedOptions" not in target_conf
            and "rest.action.multi.allow_explicit_index"
            in current_domain["AdvancedOptions"]
        ):
            del current_domain["AdvancedOptions"][
                "rest.action.multi.allow_explicit_index"
            ]
        if not current_domain["AdvancedOptions"]:
            del current_domain["AdvancedOptions"]

        # Compare current configuration with provided configuration
        config_diff = salt.utils.data.recursive_diff(current_domain, target_conf)
        if config_diff:
            action = "update"

        # Compare ElasticsearchVersion separately, as the update procedure differs.
        if elasticsearch_version and current_domain_version != elasticsearch_version:
            action = "upgrade"

    if action in ["create", "update"]:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"].append(
                'The Elasticsearch Domain "{}" would have been {}d.'.format(
                    name, action
                )
            )
            ret["changes"] = config_diff
        else:
            boto_kwargs = salt.utils.data.filter_falsey(
                {
                    "elasticsearch_version": elasticsearch_version,
                    "elasticsearch_cluster_config": elasticsearch_cluster_config,
                    "ebs_options": ebs_options,
                    "vpc_options": vpc_options,
                    "access_policies": access_policies,
                    "snapshot_options": snapshot_options,
                    "cognito_options": cognito_options,
                    "encryption_at_rest_options": encryption_at_rest_options,
                    "node_to_node_encryption_options": node_to_node_encryption_options,
                    "advanced_options": advanced_options,
                    "log_publishing_options": log_publishing_options,
                    "blocking": blocking,
                    "region": region,
                    "keyid": keyid,
                    "key": key,
                    "profile": profile,
                }
            )
            if action == "update":
                # Drop certain kwargs that do not apply to updates.
                for item in [
                    "elasticsearch_version",
                    "encryption_at_rest_options",
                    "node_to_node_encryption_options",
                ]:
                    if item in boto_kwargs:
                        del boto_kwargs[item]
            res = __salt__[
                "boto3_elasticsearch.{}_elasticsearch_domain{}".format(
                    action, "_config" if action == "update" else ""
                )
            ](name, **boto_kwargs)
            if "error" in res:
                ret["result"] = False
                ret["comment"].append(res["error"])
            else:
                ret["result"] = True
                ret["comment"].append(
                    f'Elasticsearch Domain "{name}" has been {action}d.'
                )
                ret["changes"] = config_diff
    elif action == "upgrade":
        res = upgraded(
            name,
            elasticsearch_version,
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        )
        ret["result"] = res["result"]
        ret["comment"].extend(res["comment"])
        if res["changes"]:
            salt.utils.dictupdate.set_dict_key_value(
                ret, "changes:old:version", res["changes"]["old"]
            )
            salt.utils.dictupdate.set_dict_key_value(
                ret, "changes:new:version", res["changes"]["new"]
            )

    if tags is not None:
        res = tagged(
            name,
            tags=tags,
            replace=True,
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        )
        ret["result"] = res["result"]
        ret["comment"].extend(res["comment"])
        if "old" in res["changes"]:
            salt.utils.dictupdate.update_dict_key_value(
                ret, "changes:old:tags", res["changes"]["old"]
            )
        if "new" in res["changes"]:
            salt.utils.dictupdate.update_dict_key_value(
                ret, "changes:new:tags", res["changes"]["new"]
            )
    ret = _check_return_value(ret)
    return ret


def absent(name, blocking=True, region=None, keyid=None, key=None, profile=None):
    """
    Ensure the Elasticsearch Domain specified does not exist.

    :param str name: The name of the Elasticsearch domain to be made absent.
    :param bool blocking: Whether or not the state should wait for the deletion
        to be completed. Default: ``True``

    .. versionadded:: 3001

    Example:

    .. code-block:: yaml

        Remove Elasticsearch Domain:
          boto3_elasticsearch.absent:
          - name: my_domain
          - region: eu-west-1
    """
    ret = {"name": name, "result": "oops", "comment": [], "changes": {}}

    res = __salt__["boto3_elasticsearch.exists"](
        name, region=region, keyid=keyid, key=key, profile=profile
    )
    if "error" in res:
        ret["result"] = False
        ret["comment"].append(res["error"])
    elif res["result"]:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"].append(
                f'Elasticsearch domain "{name}" would have been removed.'
            )
            ret["changes"] = {"old": name, "new": None}
        else:
            res = __salt__["boto3_elasticsearch.delete_elasticsearch_domain"](
                domain_name=name,
                blocking=blocking,
                region=region,
                keyid=keyid,
                key=key,
                profile=profile,
            )
            if "error" in res:
                ret["result"] = False
                ret["comment"].append(
                    'Error deleting Elasticsearch domain "{}": {}'.format(
                        name, res["error"]
                    )
                )
            else:
                ret["result"] = True
                ret["comment"].append(
                    f'Elasticsearch domain "{name}" has been deleted.'
                )
                ret["changes"] = {"old": name, "new": None}
    else:
        ret["result"] = True
        ret["comment"].append(f'Elasticsearch domain "{name}" is already absent.')
    ret = _check_return_value(ret)
    return ret


def upgraded(
    name,
    elasticsearch_version,
    blocking=True,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Ensures the Elasticsearch domain specified runs on the specified version of
    elasticsearch. Only upgrades are possible as downgrades require a manual snapshot
    and an S3 bucket to store them in.

    Note that this operation is blocking until the upgrade is complete.

    :param str name: The name of the Elasticsearch domain to upgrade.
    :param str elasticsearch_version: String of format X.Y to specify version for
        the Elasticsearch domain eg. "1.5" or "2.3".

    .. versionadded:: 3001

    Example:

    .. code-block:: yaml

        Upgrade Elasticsearch Domain:
          boto3_elasticsearch.upgraded:
          - name: my_domain
          - elasticsearch_version: '7.2'
          - region: eu-west-1
    """
    ret = {"name": name, "result": "oops", "comment": [], "changes": {}}
    current_domain = None
    res = __salt__["boto3_elasticsearch.describe_elasticsearch_domain"](
        name, region=region, keyid=keyid, key=key, profile=profile
    )
    if not res["result"]:
        ret["result"] = False
        if "ResourceNotFoundException" in res["error"]:
            ret["comment"].append(f'The Elasticsearch domain "{name}" does not exist.')
        else:
            ret["comment"].append(res["error"])
    else:
        current_domain = res["response"]
        current_version = current_domain["ElasticsearchVersion"]
        if elasticsearch_version and current_version == elasticsearch_version:
            ret["result"] = True
            ret["comment"].append(
                'The Elasticsearch domain "{}" is already '
                "at the desired version {}"
                "".format(name, elasticsearch_version)
            )
        elif Version(elasticsearch_version) < Version(current_version):
            ret["result"] = False
            ret["comment"].append(
                'Elasticsearch domain "{}" cannot be downgraded '
                'to version "{}".'
                "".format(name, elasticsearch_version)
            )
    if isinstance(ret["result"], bool):
        return ret
    log.debug("%s :upgraded: Check upgrade in progress", __name__)
    # Check if an upgrade is already in progress
    res = __salt__["boto3_elasticsearch.get_upgrade_status"](
        name, region=region, keyid=keyid, key=key, profile=profile
    )
    if "error" in res:
        ret["result"] = False
        ret["comment"].append(
            'Error determining current upgrade status of domain "{}": {}'.format(
                name, res["error"]
            )
        )
        return ret
    if res["response"].get("StepStatus") == "IN_PROGRESS":
        if blocking:
            # An upgrade is already in progress, wait for it to complete
            res2 = __salt__["boto3_elasticsearch.wait_for_upgrade"](
                name, region=region, keyid=keyid, key=key, profile=profile
            )
            if "error" in res2:
                ret["result"] = False
                ret["comment"].append(
                    'Error waiting for upgrade of domain "{}" to complete: {}'.format(
                        name, res2["error"]
                    )
                )
            elif (
                res2["response"].get("UpgradeName", "").endswith(elasticsearch_version)
            ):
                ret["result"] = True
                ret["comment"].append(
                    'Elasticsearch Domain "{}" is already at version "{}".'.format(
                        name, elasticsearch_version
                    )
                )
        else:
            # We are not going to wait for it to complete, so bail.
            ret["result"] = True
            ret["comment"].append(
                'An upgrade of Elasticsearch domain "{}" '
                "is already underway: {}"
                "".format(name, res["response"].get("UpgradeName"))
            )
    if isinstance(ret["result"], bool):
        return ret

    log.debug("%s :upgraded: Check upgrade eligibility", __name__)
    # Check if the domain is eligible for an upgrade
    res = __salt__["boto3_elasticsearch.check_upgrade_eligibility"](
        name,
        elasticsearch_version,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )
    if "error" in res:
        ret["result"] = False
        ret["comment"].append(
            'Error checking upgrade eligibility for domain "{}": {}'.format(
                name, res["error"]
            )
        )
    elif not res["response"]:
        ret["result"] = False
        ret["comment"].append(
            'The Elasticsearch Domain "{}" is not eligible to '
            "be upgraded to version {}."
            "".format(name, elasticsearch_version)
        )
    else:
        log.debug("%s :upgraded: Start the upgrade", __name__)
        # Start the upgrade
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"].append(
                'The Elasticsearch version for domain "{}" would have been upgraded.'
            )
            ret["changes"] = {
                "old": current_domain["ElasticsearchVersion"],
                "new": elasticsearch_version,
            }
        else:
            res = __salt__["boto3_elasticsearch.upgrade_elasticsearch_domain"](
                name,
                elasticsearch_version,
                blocking=blocking,
                region=region,
                keyid=keyid,
                key=key,
                profile=profile,
            )
            if "error" in res:
                ret["result"] = False
                ret["comment"].append(
                    'Error upgrading Elasticsearch domain "{}": {}'.format(
                        name, res["error"]
                    )
                )
            else:
                ret["result"] = True
                ret["comment"].append(
                    'The Elasticsearch domain "{}" has been '
                    "upgraded to version {}."
                    "".format(name, elasticsearch_version)
                )
                ret["changes"] = {
                    "old": current_domain["ElasticsearchVersion"],
                    "new": elasticsearch_version,
                }
    ret = _check_return_value(ret)
    return ret


def latest(name, minor_only=True, region=None, keyid=None, key=None, profile=None):
    """
    Ensures the Elasticsearch domain specifies runs on the latest compatible
    version of elasticsearch, upgrading it if it is not.

    Note that this operation is blocking until the upgrade is complete.

    :param str name: The name of the Elasticsearch domain to upgrade.
    :param bool minor_only: Only upgrade to the latest minor version.

    .. versionadded:: 3001

    Example:

    The following example will ensure the elasticsearch domain ``my_domain`` is
    upgraded to the latest minor version. So if it is currently 5.1 it will be
    upgraded to 5.6.

    .. code-block:: yaml

        Upgrade Elasticsearch Domain:
          boto3_elasticsearch.latest:
          - name: my_domain
          - minor_only: True
          - region: eu-west-1
    """
    ret = {"name": name, "result": "oops", "comment": [], "changes": {}}
    # Get current version
    res = __salt__["boto3_elasticsearch.describe_elasticsearch_domain"](
        domain_name=name, region=region, keyid=keyid, key=key, profile=profile
    )
    if "error" in res:
        ret["result"] = False
        ret["comment"].append(
            'Error getting information of Elasticsearch domain "{}": {}'.format(
                name, res["error"]
            )
        )
    else:
        current_version = res["response"]["ElasticsearchVersion"]
        # Get latest compatible version
        latest_version = None
        res = __salt__["boto3_elasticsearch.get_compatible_elasticsearch_versions"](
            domain_name=name, region=region, keyid=keyid, key=key, profile=profile
        )
        if "error" in res:
            ret["result"] = False
            ret["comment"].append(
                "Error getting compatible Elasticsearch versions "
                'for Elasticsearch domain "{}": {}'
                "".format(name, res["error"])
            )
    if isinstance(ret["result"], bool):
        return ret
    try:
        latest_version = res["response"][0]["TargetVersions"].pop(-1)
    except IndexError:
        pass
    if not current_version:
        ret["result"] = True
        ret["comment"].append(f'The Elasticsearch domain "{name}" can not be upgraded.')
    elif not latest_version:
        ret["result"] = True
        ret["comment"].append(
            'The Elasticsearch domain "{}" is already at '
            'the lastest version "{}".'
            "".format(name, current_version)
        )
    else:
        a_current_version = current_version.split(".")
        a_latest_version = latest_version.split(".")
        if not (minor_only and a_current_version[0] != a_latest_version[0]):
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"].append(
                    'Elasticsearch domain "{}" would have been updated '
                    'to version "{}".'.format(name, latest_version)
                )
                ret["changes"] = {"old": current_version, "new": latest_version}
            else:
                ret = upgraded(
                    name,
                    latest_version,
                    region=region,
                    keyid=keyid,
                    key=key,
                    profile=profile,
                )
        else:
            ret["result"] = True
            ret["comment"].append(
                'Elasticsearch domain "{}" is already at its '
                "latest minor version {}."
                "".format(name, current_version)
            )
    ret = _check_return_value(ret)
    if ret["result"] and ret["changes"] and not minor_only:
        # Try and see if we can upgrade again
        res = latest(
            name,
            minor_only=minor_only,
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        )
        if res["result"] and res["changes"]:
            ret["changes"]["new"] = res["changes"]["new"]
            ret["comment"].extend(res["comment"])
    return ret


def tagged(
    name, tags=None, replace=False, region=None, keyid=None, key=None, profile=None
):
    """
    Ensures the Elasticsearch domain has the tags provided.
    Adds tags to the domain unless ``replace`` is set to ``True``, in which
    case all existing tags will be replaced with the tags provided in ``tags``.
    (This will remove all tags if ``replace`` is ``True`` and ``tags`` is empty).

    :param str name: The Elasticsearch domain to work with.
    :param dict tags: The tags to add to/replace on the Elasticsearch domain.
    :param bool replace: Whether or not to replace (``True``) all existing tags
        on the Elasticsearch domain, or add (``False``) tags to the ES domain.

    .. versionadded:: 3001

    """
    ret = {"name": name, "result": "oops", "comment": [], "changes": {}}
    current_tags = {}
    # Check if the domain exists
    res = __salt__["boto3_elasticsearch.exists"](
        name, region=region, keyid=keyid, key=key, profile=profile
    )
    if res["result"]:
        res = __salt__["boto3_elasticsearch.list_tags"](
            name, region=region, keyid=keyid, key=key, profile=profile
        )
        if "error" in res:
            ret["result"] = False
            ret["comment"].append(
                'Error fetching tags of Elasticsearch domain "{}": {}'.format(
                    name, res["error"]
                )
            )
        else:
            current_tags = res["response"] or {}
    else:
        ret["result"] = False
        ret["comment"].append(f'Elasticsearch domain "{name}" does not exist.')
    if isinstance(ret["result"], bool):
        return ret

    diff_tags = salt.utils.dictdiffer.deep_diff(current_tags, tags)
    if not diff_tags:
        ret["result"] = True
        ret["comment"].append(
            f'Elasticsearch domain "{name}" already has the specified tags.'
        )
    else:
        if replace:
            ret["changes"] = diff_tags
        else:
            ret["changes"] = {"old": current_tags, "new": current_tags.update(tags)}
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"].append(
                'Tags on Elasticsearch domain "{}" would have been {}ed.'.format(
                    name, "replac" if replace else "add"
                )
            )
        else:
            if replace:
                res = __salt__["boto3_elasticsearch.remove_tags"](
                    tag_keys=current_tags.keys(),
                    domain_name=name,
                    region=region,
                    keyid=keyid,
                    key=key,
                    profile=profile,
                )
                if "error" in res:
                    ret["result"] = False
                    ret["comment"].append(
                        "Error removing current tags from Elasticsearch "
                        'domain "{}": {}'.format(name, res["error"])
                    )
                    ret["changes"] = {}
            if isinstance(ret["result"], bool):
                return ret
            res = __salt__["boto3_elasticsearch.add_tags"](
                domain_name=name,
                tags=tags,
                region=region,
                keyid=keyid,
                key=key,
                profile=profile,
            )
            if "error" in res:
                ret["result"] = False
                ret["comment"].append(
                    'Error tagging Elasticsearch domain "{}": {}'.format(
                        name, res["error"]
                    )
                )
                ret["changes"] = {}
            else:
                ret["result"] = True
                ret["comment"].append(
                    'Tags on Elasticsearch domain "{}" have been {}ed.'.format(
                        name, "replac" if replace else "add"
                    )
                )
    ret = _check_return_value(ret)
    return ret
