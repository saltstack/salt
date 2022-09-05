"""
Connection module for Amazon EFS

.. versionadded:: 2017.7.0

:configuration: This module accepts explicit EFS credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles or
    it can read them from the ~/.aws/credentials file or from these
    environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary.  More information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/efs/latest/ug/
            access-control-managing-permissions.html

        http://boto3.readthedocs.io/en/latest/guide/
            configuration.html#guide-configuration

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file

    .. code-block:: yaml

        efs.keyid: GKTADJGHEIQSXMKKRBJ08H
        efs.key: askd+ghsdfjkghWupU/asdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration

    .. code-block:: yaml

        efs.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid, and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
          keyid: GKTADJGHEIQSXMKKRBJ08H
          key: askd+ghsdfjkghWupU/asdflkdfklgjsdfjajkghs
          region: us-east-1

:depends: boto3
"""


import logging

import salt.utils.versions

try:
    import boto3

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if boto3 libraries exist and if boto3 libraries are greater than
    a given version.
    """
    return salt.utils.versions.check_boto_reqs(boto3_ver="1.0.0", check_boto=False)


def _get_conn(key=None, keyid=None, profile=None, region=None, **kwargs):
    """
    Create a boto3 client connection to EFS
    """
    client = None
    if profile:
        if isinstance(profile, str):
            if profile in __pillar__:
                profile = __pillar__[profile]
            elif profile in __opts__:
                profile = __opts__[profile]
    elif key or keyid or region:
        profile = {}
        if key:
            profile["key"] = key
        if keyid:
            profile["keyid"] = keyid
        if region:
            profile["region"] = region

    if isinstance(profile, dict):
        if "region" in profile:
            profile["region_name"] = profile["region"]
            profile.pop("region", None)
        if "key" in profile:
            profile["aws_secret_access_key"] = profile["key"]
            profile.pop("key", None)
        if "keyid" in profile:
            profile["aws_access_key_id"] = profile["keyid"]
            profile.pop("keyid", None)

        client = boto3.client("efs", **profile)
    else:
        client = boto3.client("efs")

    return client


def create_file_system(
    name,
    performance_mode="generalPurpose",
    keyid=None,
    key=None,
    profile=None,
    region=None,
    creation_token=None,
    **kwargs
):
    """
    Creates a new, empty file system.

    name
        (string) - The name for the new file system

    performance_mode
        (string) - The PerformanceMode of the file system. Can be either
        generalPurpose or maxIO

    creation_token
        (string) - A unique name to be used as reference when creating an EFS.
        This will ensure idempotency. Set to name if not specified otherwise

    returns
        (dict) - A dict of the data for the elastic file system

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' boto_efs.create_file_system efs-name generalPurpose
    """

    if creation_token is None:
        creation_token = name

    tags = {"Key": "Name", "Value": name}

    client = _get_conn(key=key, keyid=keyid, profile=profile, region=region)

    response = client.create_file_system(
        CreationToken=creation_token, PerformanceMode=performance_mode
    )

    if "FileSystemId" in response:
        client.create_tags(FileSystemId=response["FileSystemId"], Tags=tags)

    if "Name" in response:
        response["Name"] = name

    return response


def create_mount_target(
    filesystemid,
    subnetid,
    ipaddress=None,
    securitygroups=None,
    keyid=None,
    key=None,
    profile=None,
    region=None,
    **kwargs
):
    """
    Creates a mount target for a file system.
    You can then mount the file system on EC2 instances via the mount target.

    You can create one mount target in each Availability Zone in your VPC.
    All EC2 instances in a VPC within a given Availability Zone share a
    single mount target for a given file system.

    If you have multiple subnets in an Availability Zone,
    you create a mount target in one of the subnets.
    EC2 instances do not need to be in the same subnet as the mount target
    in order to access their file system.

    filesystemid
        (string) - ID of the file system for which to create the mount target.

    subnetid
        (string) - ID of the subnet to add the mount target in.

    ipaddress
        (string) - Valid IPv4 address within the address range
                    of the specified subnet.

    securitygroups
        (list[string]) - Up to five VPC security group IDs,
                            of the form sg-xxxxxxxx.
                            These must be for the same VPC as subnet specified.

    returns
        (dict) - A dict of the response data

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' boto_efs.create_mount_target filesystemid subnetid
    """

    client = _get_conn(key=key, keyid=keyid, profile=profile, region=region)

    if ipaddress is None and securitygroups is None:
        return client.create_mount_target(FileSystemId=filesystemid, SubnetId=subnetid)

    if ipaddress is None:
        return client.create_mount_target(
            FileSystemId=filesystemid, SubnetId=subnetid, SecurityGroups=securitygroups
        )
    if securitygroups is None:
        return client.create_mount_target(
            FileSystemId=filesystemid, SubnetId=subnetid, IpAddress=ipaddress
        )

    return client.create_mount_target(
        FileSystemId=filesystemid,
        SubnetId=subnetid,
        IpAddress=ipaddress,
        SecurityGroups=securitygroups,
    )


def create_tags(
    filesystemid, tags, keyid=None, key=None, profile=None, region=None, **kwargs
):
    """
    Creates or overwrites tags associated with a file system.
    Each tag is a key-value pair. If a tag key specified in the request
    already exists on the file system, this operation overwrites
    its value with the value provided in the request.

    filesystemid
        (string) - ID of the file system for whose tags will be modified.

    tags
        (dict) - The tags to add to the file system

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' boto_efs.create_tags
    """

    client = _get_conn(key=key, keyid=keyid, profile=profile, region=region)

    new_tags = []
    for k, v in tags.items():
        new_tags.append({"Key": k, "Value": v})

    client.create_tags(FileSystemId=filesystemid, Tags=new_tags)


def delete_file_system(
    filesystemid, keyid=None, key=None, profile=None, region=None, **kwargs
):
    """
    Deletes a file system, permanently severing access to its contents.
    Upon return, the file system no longer exists and you can't access
    any contents of the deleted file system. You can't delete a file system
    that is in use. That is, if the file system has any mount targets,
    you must first delete them.

    filesystemid
        (string) - ID of the file system to delete.

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' boto_efs.delete_file_system filesystemid
    """

    client = _get_conn(key=key, keyid=keyid, profile=profile, region=region)

    client.delete_file_system(FileSystemId=filesystemid)


def delete_mount_target(
    mounttargetid, keyid=None, key=None, profile=None, region=None, **kwargs
):
    """
    Deletes the specified mount target.

    This operation forcibly breaks any mounts of the file system via the
    mount target that is being deleted, which might disrupt instances or
    applications using those mounts. To avoid applications getting cut off
    abruptly, you might consider unmounting any mounts of the mount target,
    if feasible. The operation also deletes the associated network interface.
    Uncommitted writes may be lost, but breaking a mount target using this
    operation does not corrupt the file system itself.
    The file system you created remains.
    You can mount an EC2 instance in your VPC via another mount target.

    mounttargetid
        (string) - ID of the mount target to delete

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' boto_efs.delete_mount_target mounttargetid
    """

    client = _get_conn(key=key, keyid=keyid, profile=profile, region=region)

    client.delete_mount_target(MountTargetId=mounttargetid)


def delete_tags(
    filesystemid, tags, keyid=None, key=None, profile=None, region=None, **kwargs
):
    """
    Deletes the specified tags from a file system.

    filesystemid
        (string) - ID of the file system for whose tags will be removed.

    tags
        (list[string]) - The tag keys to delete to the file system

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' boto_efs.delete_tags
    """

    client = _get_conn(key=key, keyid=keyid, profile=profile, region=region)

    client.delete_tags(FileSystemId=filesystemid, Tags=tags)


def get_file_systems(
    filesystemid=None,
    keyid=None,
    key=None,
    profile=None,
    region=None,
    creation_token=None,
    **kwargs
):
    """
    Get all EFS properties or a specific instance property
    if filesystemid is specified

    filesystemid
        (string) - ID of the file system to retrieve properties

    creation_token
        (string) - A unique token that identifies an EFS.
        If fileysystem created via create_file_system this would
        either be explictitly passed in or set to name.
        You can limit your search with this.

    returns
        (list[dict]) - list of all elastic file system properties

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' boto_efs.get_file_systems efs-id
    """

    result = None
    client = _get_conn(key=key, keyid=keyid, profile=profile, region=region)

    if filesystemid and creation_token:
        response = client.describe_file_systems(
            FileSystemId=filesystemid, CreationToken=creation_token
        )
        result = response["FileSystems"]
    elif filesystemid:
        response = client.describe_file_systems(FileSystemId=filesystemid)
        result = response["FileSystems"]
    elif creation_token:
        response = client.describe_file_systems(CreationToken=creation_token)
        result = response["FileSystems"]
    else:
        response = client.describe_file_systems()

        result = response["FileSystems"]

        while "NextMarker" in response:
            response = client.describe_file_systems(Marker=response["NextMarker"])
            result.extend(response["FileSystems"])

    return result


def get_mount_targets(
    filesystemid=None,
    mounttargetid=None,
    keyid=None,
    key=None,
    profile=None,
    region=None,
    **kwargs
):
    """
    Get all the EFS mount point properties for a specific filesystemid or
    the properties for a specific mounttargetid. One or the other must be
    specified

    filesystemid
        (string) - ID of the file system whose mount targets to list
                   Must be specified if mounttargetid is not

    mounttargetid
        (string) - ID of the mount target to have its properties returned
                   Must be specified if filesystemid is not

    returns
        (list[dict]) - list of all mount point properties

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' boto_efs.get_mount_targets
    """

    result = None
    client = _get_conn(key=key, keyid=keyid, profile=profile, region=region)

    if filesystemid:
        response = client.describe_mount_targets(FileSystemId=filesystemid)
        result = response["MountTargets"]
        while "NextMarker" in response:
            response = client.describe_mount_targets(
                FileSystemId=filesystemid, Marker=response["NextMarker"]
            )
            result.extend(response["MountTargets"])
    elif mounttargetid:
        response = client.describe_mount_targets(MountTargetId=mounttargetid)
        result = response["MountTargets"]

    return result


def get_tags(filesystemid, keyid=None, key=None, profile=None, region=None, **kwargs):
    """
    Return the tags associated with an EFS instance.

    filesystemid
        (string) - ID of the file system whose tags to list

    returns
        (list) - list of tags as key/value pairs

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' boto_efs.get_tags efs-id
    """
    client = _get_conn(key=key, keyid=keyid, profile=profile, region=region)
    response = client.describe_tags(FileSystemId=filesystemid)
    result = response["Tags"]

    while "NextMarker" in response:
        response = client.describe_tags(
            FileSystemId=filesystemid, Marker=response["NextMarker"]
        )
        result.extend(response["Tags"])

    return result


def set_security_groups(
    mounttargetid,
    securitygroup,
    keyid=None,
    key=None,
    profile=None,
    region=None,
    **kwargs
):
    """
    Modifies the set of security groups in effect for a mount target

    mounttargetid
        (string) - ID of the mount target whose security groups will be modified

    securitygroups
        (list[string]) - list of no more than 5 VPC security group IDs.

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' boto_efs.set_security_groups my-mount-target-id my-sec-group
    """

    client = _get_conn(key=key, keyid=keyid, profile=profile, region=region)
    client.modify_mount_target_security_groups(
        MountTargetId=mounttargetid, SecurityGroups=securitygroup
    )
