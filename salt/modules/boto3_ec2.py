"""
Connection module for Amazon EC2/VPC.
Be aware that this interacts with Amazon's services, and so may incur charges.

:configuration: This module accepts explicit IAM credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available `here <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`__

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file. Entries in the config file take presedence over
    entries in the pillar.
    The keyid, key, and region can be specified in the config file or pillar as
    separate values, or combined in a profile dict:

    .. code-block:: yaml

        ec2.keyid: GKTADJGHEIQSXMKKRBJ08H
        ec2.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        ec2.region: us-east-1

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

    If a region is not specified, the default is us-east-1.

    When calling functions in this module, you can provide keyid, key, or region,
    or a profile (as a dict, or as a string which will be looked up in the
    configuration file and the pillar respectively) with each call. If you do
    not provide these parameters, they will be retrieved from respectively the
    config file and the pillar as mentioned above. If they are not present there,
    an attempt will be made to retrieve the credentials from the IAM profile of
    the EC2 instance this function is called on.

:depends: boto3, botocore
"""
import functools
import hashlib
import inspect
import itertools
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Tuple, Union

# pylint: disable=3rd-party-module-not-gated
import salt.utils.compat
import salt.utils.data
import salt.utils.dicttrim
import salt.utils.network
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError
from salt.utils.versions import LooseVersion

# pylint: enable=3rd-party-module-not-gated

# keep lint from choking on _get_client and _cache_id
# pylint: disable=E0602
try:
    import boto3
    import botocore  # pylint: disable=unused-import
    from botocore.exceptions import ParamValidationError, ClientError

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


log = logging.getLogger(__name__)
__virtualname__ = "boto3_vpc"


def __virtual__():
    """
    Only load if boto3 libraries exist.
    """
    if "boto3.assign_funcs" in __utils__ and HAS_BOTO3:
        return True
    return (
        False,
        "The {} module could not be loaded: boto3 libraries not "
        "found".format(__virtualname__),
    )


def __init__(opts):
    _ = opts
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO3:
        __utils__["boto3.assign_funcs"](
            __name__, "ec2", get_conn_funcname="_get_client"
        )
    logging.getLogger("boto3").setLevel(logging.INFO)


def _arguments_to_list(*args):
    """
    Decorator function to specify arguments to _listify

    :param list(str) args: keywords of kwargs of called function to _listify.
    """

    def _listify(thing: Any) -> List:
        """
        Helper function to convert thing into [thing] if it is not already a list.
        Used in functions that accept a thing or a list of things to internally
        always handle it as a list of things.
        Note: Does nothing when ``thing`` is ``None``.

        :param any thing: Something to put in a list or not.

        :rtype: list
        """
        return [thing] if thing is not None and not isinstance(thing, list) else thing

    def actual_decorator(func):
        @functools.wraps(func)
        def wrapped(*f_args, **f_kwargs):
            for keyword in args:
                if keyword in f_kwargs:
                    f_kwargs[keyword] = _listify(f_kwargs[keyword])
            return func(*f_args, **f_kwargs)

        return wrapped

    return actual_decorator


def _derive_ipv6_cidr_subnet(ipv6_subnet: int, ipv6_parent_block: str) -> str:
    """
    Helper function to create the 64bit IPv6 CIDR block given only the last
    digit(s) of the subnet.

    For example:
        ipv6_subnet = 1
        ipv6_parent_block = 'fdc8:4d2f:d387:fc00::/56'
        result = 'fdc8:4d2f:d387:fc01/64'

    :param int ipv6_subnet: The subnet number (range 1-ff)
    :param str ipv6_parent_block: The /56 CIDR block this subnet goes into.

    :rtype: str
    :return: The full IPv6 CIDR block for the /64 subnet.
    """
    log.debug(
        "%s:derive_ipv6_cidr_subnet:\n"
        "\t\tipv6_subnet: %s\n"
        "\t\tipv6_parent_block: %s",
        __name__,
        ipv6_subnet,
        ipv6_parent_block,
    )
    if not 0 <= ipv6_subnet <= 255:
        raise SaltInvocationError("ipv6_subnet must be in the range of [0, 255].")
    (ipv6_parent_block, _) = ipv6_parent_block.split("/")
    ipv6_parent_block = ipv6_parent_block.split(":")
    res = (":".join(ipv6_parent_block[:-2]))[:-2] + "{:02d}::/64".format(ipv6_subnet)
    log.debug("%s:derive_ipv6_cidr_subnet:\n" "\t\tres: %s", __name__, res)
    return res


def build_block_device_mapping(
    device_name: str = None,
    ebs_delete_on_termination: bool = None,
    ebs_encrypted: bool = None,
    ebs_iops: int = None,
    ebs_kms_key_id: str = None,
    ebs_snapshot_id: str = None,
    ebs_snapshot_lookup: Mapping = None,
    ebs_volume_size: int = None,
    no_device: str = None,
    virtual_name: str = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Helper function to create a block device mapping for use in various functions.
    You only need to specify IAM credentials if you want to lookup the snapshot.

    :param str device_name: The device name (for example ``/dev/sdh`` or ``xvdh``).
    :param bool ebs_delete_on_termination: Indicates whether the EBS volume is
      deleted on instance termination.
    :param bool ebs_encrypted: Indicates whether the encryption state of an EBS
      volume is changed while being restored from a backing snapshot. The effect
      of setting the encryption state to true depends on the volume origin (new
      or from a snapshot), starting encryption state, ownership, and whether encryption
      by default is enabled.
      In no case can you remove encryption from an encrypted volume.
      Encrypted volumes can only be attached to instances that support Amazon EBS encryption.
      This parameter is not returned by :py:func:`describe_image_attribute`.
    :param int ebs_iops: The number of I/O operations per second (IOPS) that the volume
      supports. For ``io1`` and ``io2`` volumes, this represents the number of
      IOPS that are provisioned for the volume. For ``gp2`` volumes, this represents
      the baseline performance of the volume and the rate at which the volume accumulates
      I/O credits for bursting.
      Constraints: Range is 100-16,000 IOPS for ``gp2`` volumes and 100 to 64,000
      IOPS for ``io1`` and ``io2`` volumes in most Regions. Maximum ``io1`` and
      ``io2`` IOPS of 64,000 is guaranteed only on Nitro-based instances. Other
      instance families guarantee performance up to 32,000 IOPS.
      Condition: This parameter is required for requests to create ``io1`` and
      ``io2`` volumes; it is not used in requests to create ``gp2``, ``st1``, ``sc1``,
      or ``standard`` volumes.
    :param str ebs_kms_key_id: Identifier (key ID, key alias, ID ARN, or alias ARN)
      for a customer managed CMK under which the EBS volume is encrypted.
      This parameter is only supported on BlockDeviceMapping objects called by
      :py:func:`run_instances`, :py:func:`request_spot_fleet`, and :py:func:`request_spot_instances`.
    :param str ebs_snapshot_id: The ID of the snapshot.
    :param dict ebs_snapshot_lookup: Any kwargs that :py:func:`lookup_snapshot` accepts.
      Used to lookup ``ebs_snapshot_id``.
    :param int ebs_volume_size: The size of the volume, in GiB.
      Default: If you're creating the volume from a snapshot and don't specify
      a volume size, the default is the snapshot size.
      Constraints: 1-16384 for General Purpose SSD (``gp2``), 4-16384 for Provisioned
      IOPS SSD (``io1`` and ``io2``), 500-16384 for Throughput Optimized HDD (``st1``),
      500-16384 for Cold HDD (``sc1``), and 1-1024 for Magnetic (standard) volumes.
      If you specify a snapshot, the volume size must be equal to or larger than
      the snapshot size.
    :param str ebs_volume_type: The volume type. If you set the type to ``io1`` or ``io2``,
      you must also specify the ``iops`` parameter. If you set the type to ``gp2``,
      ``st1``, ``sc1``, or ``standard``, you must omit the ``iops`` parameter.
      Default: ``gp2``. Allowed values: ``standard``, ``io1``, ``io2``, ``gp2``,
      ``sc1``, ``st1``.
    :param str no_device: Suppresses the specified device included in the block
      device mapping of the AMI.
    :param str virtual_name: The virtual device name (``ephemeralN``). Instance store
      volumes are numbered starting from 0. An instance type with 2 available instance
      store volumes can specify mappings for ``ephemeral0`` and ``ephemeral1``.
      The number of available instance store volumes depends on the instance type.
      After you connect to the instance, you must mount the volume.
      NVMe instance store volumes are automatically enumerated and assigned a device
      name. Including them in your block device mapping has no effect.
      Constraints: For M3 instances, you must specify instance store volumes in
      the block device mapping for the instance. When you launch an M3 instance,
      we ignore any instance store volumes specified in the block device mapping
      for the AMI.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict with structure matching a BlockDeviceMapping object on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "snapshot",
            "kwargs": ebs_snapshot_lookup or {"snapshot_id": ebs_snapshot_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        ebs_snapshot_id = res["result"].get("snapshot")
    return {
        "result": salt.utils.data.filter_falsey(
            {
                "DeviceName": device_name,
                "Ebs": {
                    "DeleteOnTermination": ebs_delete_on_termination,
                    "Encrypted": ebs_encrypted,
                    "Iops": ebs_iops,
                    "KmsKeyId": ebs_kms_key_id,
                    "SnapshotId": ebs_snapshot_id,
                    "VolumeSize": ebs_volume_size,
                    "VolumeType": ebs_volume_type,
                },
                "NoDevice": no_device,
                "VirtualName": virtual_name,
            },
            recurse_depth=1,
        )
    }


def build_ip_permission(
    description: str = None,
    ip_protocol: str = None,
    from_port: int = None,
    to_port: int = None,
    cidr_block: str = None,
    prefix_list_id: str = None,
    prefix_list_lookup: Mapping = None,
    security_group_id: str = None,
    security_group_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Helper function to create an IpPermission dict. Used in
    :py:func:`authorize_security_group_egress`, :py:func:`authorize_security_group_ingress`,
    :py:func:`revoke_security_group_egress` and :py:func:`revoke_security_group_ingress`.

    Note that the arguments ``cidr_ip``, ``cidr_ipv6``, ``prefix_list_id``, ``prefix_list_lookup``,
    ``security_group_id`` and ``security_group_lookup`` are used as ``Source`` when
    used in ``ingress``-functions, and used as ``Target`` when used in ``egress``-functions.

    Also note that you must provide exactly one of either ``cidr_ip``, ``prefix_list_id``,
    ``prefix_list_lookup``, ``security_group_id`` or ``security_group_lookup``.
    You will only need to supply IAM credentials if lookups need to be performed.

    :param str description: A description for this rule.
    :param str ip_protocol: The IP protocol name (tcp, udp, icmp, icmpv6 ) or number.
      [VPC only] Use -1 to specify all protocols. When authorizing security
      group rules, specifying -1 or a protocol number other than tcp, udp,
      icmp, or icmpv6 allows traffic on all ports, regardless of any port range
      you specify. For tcp, udp, and icmp, you must specify a port range. For
      icmpv6, the port range is optional; if you omit the port range, traffic
      for all types and codes is allowed.
    :param int from_port: The start of port range for the TCP and UDP protocols,
      or an ICMP/ICMPv6 type number. A value of -1 indicates all ICMP/ICMPv6
      types. If you specify all ICMP/ICMPv6 types, you must specify all codes.
    :param int to_port: The end of port range for the TCP and UDP protocols, or
        an ICMP/ICMPv6 code. A value of -1 indicates all ICMP/ICMPv6 codes.
        If you specify all ICMP/ICMPv6 types, you must specify all codes.
    :param str cidr_block: The IPv4 or IPv6 CIDR range for this rule. Use ``/32``
      (IPv4) or ``/64`` (IPv6) to specify a single IP.
    :param str prefix_list_id: The ID of the prefix list.
    :param dict prefix_list_lookup: Any kwargs that :py:func:`lookup_managed_prefix_list`
      accepts. Used to lookup ``prefix_list_id``.
    :param str security_group_id: The ID of the security group that references this rule.
    :param str security_group_lookup: Any kwargs that :py:func:`lookup_security_group`
      accepts. Used to lookup ``security_group_id``. This can be used to reference
      security groups in other VPCs or other accounts. You will have to provide
      alternative credentials in order to perform the lookup in another account.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict with structure matching an IpPermission object on success.
    """
    if not salt.utils.data.exactly_one(
        (
            cidr_ip,
            prefix_list_id,
            prefix_list_lookup,
            security_group_id,
            security_group_lookup,
        )
    ):
        raise SaltInvocationError(
            "You must specify exactly one of cidr_ip, prefix_list_id, prefix_list_lookup, security_group_id, or security_group_lookup."
        )
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": security_group_lookup or {"group_id": security_group_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "managed_prefix_list",
            "kwargs": prefix_list_lookup or {"prefix_list_id": prefix_list_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        security_group_id = res["result"].get("security_group")
        prefix_list_id = res["result"].get("managed_prefix_list")
    ret = salt.utils.data.filter_falsey(
        {
            "FromPort": from_port,
            "ToPort": to_port,
            "IpProtocol": ip_protocol,
        }
    )
    if cidr_block:
        if salt.utils.network.is_ipv6_subnet(cidr_block):
            ret.update(
                {
                    "Ipv6Ranges": [
                        salt.utils.data.filter_falsey(
                            {"CidrIpv6": cidr_block, "Description": description}
                        )
                    ]
                }
            )
        elif salt.utils.network.is_ipv4_subnet(cidr_block):
            ret.update(
                {
                    "IpRanges": [
                        salt.utils.data.filter_falsey(
                            {"CidrIp": cidr_block, "Description": description}
                        )
                    ]
                }
            )
        else:
            raise SaltInvocationError(
                'The provided cidr_block "{}" is not a valid IPv4 or IPv6 CIDR block.'.format(
                    cidr_block
                )
            )
    elif prefix_list_id:
        ret.update(
            {
                "PrefixListIds": [
                    salt.utils.data.filter_falsey(
                        {"PrefixListId": prefix_list_id, "Description": description}
                    )
                ]
            }
        )
    elif security_group_id:
        ret.update(
            {
                "UserIdGroupPairs": [
                    salt.utils.data.filter_falsey(
                        {"GroupId": security_group_id, "Description": description}
                    )
                ]
            }
        )
    return {"result": ret}


@_arguments_to_list(
    "block_device_mappings",
    "network_interfaces",
    "security_group_ids",
    "security_group_lookups",
)
def build_launch_specification(
    block_device_mappings: Union[Mapping, Iterable[Mapping]] = None,
    ebs_optimized: bool = None,
    iam_instance_profile_arn: str = None,
    iam_instance_profile_name: str = None,
    image_id: str = None,
    image_lookup: Mapping = None,
    instance_type: str = None,
    kernel_id: str = None,
    key_pair_name: str = None,
    monitoring: bool = None,
    network_interfaces: Union[Mapping, Iterable[Mapping]] = None,
    placement_availability_zone: str = None,
    placement_group_name: str = None,
    placement_tenancy: str = None,
    ramdisk_id: str = None,
    security_group_ids: Union[str, Iterable[str]] = None,
    security_group_lookups: Union[Mapping, Iterable[Mapping]] = None,
    spot_price: float = None,
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    tags: Mapping = None,
    user_data: str = None,
    weighted_capacity: float = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Helper function to create a launch specification for use in :py:func:`request_spot_fleet`
    and :py:func:`request_spot_instances`.

    :type block_device_mappings: dict or list(dict)
    :param block_device_mappings: One or more block devices (that are mapped
      to the Spot Instances). You can't specify both a snapshot ID and an encryption
      value. This is because only blank volumes can be encrypted on creation. If
      a snapshot is the basis for a volume, it is not blank and its encryption
      status is used for the volume encryption status. These dicts can either
      contain the structure as described
      `here <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_BlockDeviceMapping.html>`__
      or contain the kwargs that :py:func:`build_block_device_mapping` accepts.
    :param bool ebs_optimized: Indicates whether the instances are optimized for
      EBS I/O. This optimization provides dedicated throughput to Amazon EBS and
      an optimized configuration stack to provide optimal EBS I/O performance.
      This optimization isn't available with all instance types. Additional usage
      charges apply when using an EBS Optimized instance.
      Default: ``False``
    :param str iam_instance_profile_arn: The ARN of the IAM instance profile.
    :param str iam_instance_profile_name: The name of the IAM instance profile.
    :param str image_id: The ID of the AMI.
    :param dict image_lookup: Any kwargs that :py:func:`lookup_image` accepts.
      Used to lookup ``image_id``.
    :param str instance_type: The instance type.
    :param str kernel_id: The ID of the kernel
    :param str key_pair_name: The name of the key pair.
    :param bool monitoring: Enable or disable monitoring for the instances.
    :type network_interfaces: dict or list(dict)
    :param network_interfaces: One or more network interfaces. If you specify a
      network interface, you must specify subnet IDs and security group IDs using
      the network interface.
      You can use :py:func:`build_network_interface_config` to create this dict
      from separate arguments.
    :param str placement_availability_zone: The availability zone.
      [Spot Fleet only] To specify multiple Availability Zones, separate them using
      commas; for example, "us-west-2a, us-west-2b".
    :param str placement_group_name: The name of the placement group.
    :param str placement_tenancy: The tenancy of the instance (if the instance is
      running in a VPC). An instance with a tenancy of dedicated runs on single-tenant
      hardware. The host tenancy is not supported for Spot Instances.
      Allowed values: ``default``, ``dedicated``, ``host``.
    :param str ramdisk_id: The ID of the RAM disk. Some kernels require additional
      drivers at launch. Check the kernel requirements for information about whether
      you need to specify a RAM disk. To find kernel requirements, refer to the
      AWS Resource Center and search for the kernel ID.
    :param list(str) security_group_ids: One or more security group IDs.
    :param list(dict) security_group_lookups: List of dicts that contain kwargs
      that :py:func:`lookup_security_group` accepts. Used to lookup ``security_group_ids``.
    :param str spot_price: [Spot Fleet only] The maximum price per unit hour that
      you are willing to pay for a Spot Instance. If this value is not specified,
      the default is the Spot price specified for the fleet. To determine the Spot
      price per unit hour, divide the Spot price by the value of ``weighted_capacity``.
    :type subnet_id: str or list(str)
    :param subnet_id: The IDs of one or more subnets in which to launch the instances.
    :type subnet_lookup: dict or list(dict)
    :type subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
    :param dict tags: [Spot Fleet only] The tags to apply to instances of the fleet
      during creation.
    :param str user_data: The Base64-encoded user data that instances use when starting up.
    :param double weighted_capacity: [Spot Fleet only] The number of units provided
      by the specified instance type. These are the same units that you chose to
      set the target capacity in terms of instances, or a performance characteristic
      such as vCPUs, memory, or I/O.
      If the target capacity divided by this value is not a whole number, Amazon
      EC2 rounds the number of instances to the next whole number. If this value
      is not specified, the default is 1.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict with structure matching ``RequestSpotLaunchSpecification`` and
      ``SpotFleetLaunchSpecification`` objects on success.
    """
    # block_device_mappings is either properly supplied by the user in Boto-form,
    # or in the format passable to :py:func:`build_block_device_mapping`
    try:
        block_device_mappings = [
            build_block_device_mapping(item)["result"] for item in block_device_mappings
        ]
    except (TypeError, KeyError):  # unexpected keyword arguments
        pass  # to Boto as-is
    try:
        network_interfaces = [
            build_network_interface_config(item)["result"]
            for item in network_interfaces
        ]
    except (TypeError, KeyError):
        pass  # to Boto as-is
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "image",
            "kwargs": image_lookup or {"image_id": image_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": security_group_lookups
            or [{"group_id": group_id} for group_id in security_group_ids or []],
            "required": False,
            "result_keys": "GroupId",
        },
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        image_id = res.get("image")
        security_group_ids = res.get("security_group")
        subnet_id = res.get("subnet")
    return {
        "result": salt.utils.data.filter_falsey(
            {
                "BlockDeviceMappings": block_device_mappings,
                "EbsOptimized": ebs_optimized,
                "SecurityGroups": [
                    {"GroupId": item} for item in security_group_ids or []
                ],
                "IamInstanceProfile": {
                    "Arn": iam_instance_profile_arn,
                    "Name": iam_instance_profile_name,
                },
                "ImageId": image_id,
                "InstanceType": instance_type,
                "KernelId": kernel_id,
                "KeyName": key_pair_name,
                "Monitoring": {"Enabled": monitoring},
                "NetworkInterfaces": network_interfaces,
                "Placement": {
                    "AvailabilityZone": placement_availability_zone,
                    "GroupName": placement_group_name,
                    "Tenancy": placement_tenancy,
                },
                "RamDiskId": ramdisk_id,
                "SpotPrice": spot_price,
                "SubnetId": subnet_id,
                "TagSpecifications": {
                    "ResourceType": "instance",
                    "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
                },
                "UserData": user_data,
                "WeightedCapacity": weighted_capacity,
            },
            recurse_depth=2,
        )
    }


@_arguments_to_list(
    "ipv6_addresses",
    "private_ip_addresses",
    "security_group_ids",
    "security_group_lookups",
)
def build_network_interface_config(
    associate_carrier_ip_address: bool = None,
    associate_public_ip_address: bool = None,
    delete_on_termination: bool = None,
    description: str = None,
    device_index: int = None,
    interface_type: str = None,
    ipv6_address_count: int = None,
    ipv6_addresses: Iterable[str] = None,
    network_interface_id: str = None,
    network_interface_lookup: Mapping = None,
    primary_ip_address: str = None,
    private_ip_addresses: Union[str, Iterable[str]] = None,
    secondary_private_ip_address_count: int = None,
    security_group_ids: Union[str, Iterable[str]] = None,
    security_group_lookups: Union[Mapping, Iterable[Mapping]] = None,
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Helper function to create a network interface config for use in
    :py:func:`build_launch_specification` and :py:func:`create_launch_template`.
    IAM credentials are only required when lookups are performed.

    :param bool associate_carrier_ip_address: Associates a Carrier IP address with
      eth0 for a new network interface.
      Use this option when you launch an instance in a Wavelength Zone and want
      to associate a Carrier IP address with the network interface.
    :param bool associate_public_ip_address: Indicates whether to assign a public
      IPv4 address to an instance you launch in a VPC. The public IP address can
      only be assigned to a network interface for eth0, and can only be assigned
      to a new network interface, not an existing one. You cannot specify more
      than one network interface in the request. If launching into a default subnet,
      the default value is ``True``.
    :param bool delete_on_termination: If set to ``True``, the interface is deleted
      when the instance is terminated. You can specify ``True`` only if creating
      a new network interface when launching an instance.
    :param str description: The description of the network interface. Applies only
      if creating a network interface when launching an instance.
    :param int device_index: The position of the network interface in the attachment
      order. A primary network interface has a device index of 0.
      If you specify a network interface when launching an instance, you must specify
      the device index.
    :param str interface_type: The type of network interface. To create an Elastic
      Fabric Adapter (EFA), specify ``efa``. If you are not creating an EFA, specify
      ``interface`` or omit this parameter. Allowed values: ``interface``, ``efa``.
    :param int ipv6_address_count: A number of IPv6 addresses to assign to the
      network interface. Amazon EC2 chooses the IPv6 addresses from the range of
      the subnet. You cannot specify this option and the option to assign specific
      IPv6 addresses in the same request. You can specify this option if you've
      specified a minimum number of instances to launch.
    :type ipv6_addresses: str or list(str)
    :param ipv6_addresses: One or more IPv6 addresses to assign to the network
      interface. You cannot specify this option and the option to assign a number
      of IPv6 addresses in the same request. You cannot specify this option if
      you've specified a minimum number of instances to launch.
    :param str network_interface_id: The ID of the network interface.
      If you are creating a Spot Fleet, omit this parameter because you can’t specify
      a network interface ID in a launch specification.
    :param dict network_interface_lookup: Any kwargs that :py:func:`lookup_network_interface`
      accepts. Used to lookup ``network_interface_id``.
    :param str primary_ip_address: The primary private IPv4 address of the network
      interface. Applies only if creating a network interface when launching an
      instance. You cannot specify this option if you're launching more than one
      instance in a :py:func:`run_instances` request.
    :param list(str) private_ip_addresses: One or more private IPv4 addresses to
      assign to the network interface. Only one private IPv4 address can be designated
      as primary. Use ``primary_ip_address`` for that. You cannot specify this
      option if you're launching more than one instance in a :py:func:`run_instances` request.
    :param int secondary_private_ip_address_count: The number of secondary private
      IPv4 addresses. You can't specify this option and specify more than one private
      IP address using the ``private_ip_addresses`` option. You cannot specify
      this option if you're launching more than one instance in a :py:func:`run_instances`
      request.
    :type security_group_ids: str or list(str)
    :param security_group_ids: The IDs of the security groups for the network interface.
      Applies only if creating a network interface when launching an instance.
    :type security_group_lookups: dict or list(dict)
    :param security_group_lookups: Dict or list of dicts that contain kwargs
      that :py:func:`lookup_security_group` accepts. Used to lookup ``security_group_ids``.
    :param str subnet_id: The ID of the subnet associated with the network interface.
      Applies only if creating a network interface when launching an instance.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict with structure matching both ``InstanceNetworkInterfaceSpecification``
      and ``LaunchTemplateInstanceNetworkInterfaceSpecificationRequest`` objects
      on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "network_interface",
            "kwargs": network_interface_lookup
            or {"network_interface_id": network_interface_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": security_group_lookups
            or [{"group_id": group_id} for group_id in security_group_ids or []],
            "required": False,
            "result_keys": "GroupId",
        },
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        network_interface_id = res.get("network_interface")
        security_group_ids = res.get("security_group")
        subnet_id = res.get("subnet")
    return {
        "result": salt.utils.data.filter_falsey(
            {
                "AssociateCarrierIpAddress": associate_carrier_ip_address,
                "AssociatePublicIpAddress": associate_public_ip_address,
                "DeleteOnTermination": delete_on_termination,
                "Description": description,
                "DeviceIndex": device_index,
                "InterfaceType": interface_type,
                "IPv6AddressCount": ipv6_address_count,
                "Ipv6Addresses": [{"Ipv6Address": item} for item in ipv6_addresses],
                "NetworkInterfaceId": network_interface_id,
                "PrivateIpAddress": primary_ip_address,
                "PrivateIpAddresses": [
                    {"PrivateIpAddress": item} for item in private_ip_addresses
                ],
                "SecondaryPrivateIpAddressCount": secondary_private_ip_address_count,
                "Groups": security_group_ids,
                "SubnetId": subnet_id,
            },
            recurse_depth=1,
        )
    }


@_arguments_to_list("vpc_endpoint_ids", "vpc_endpoint_lookups")
def accept_vpc_endpoint_connections(
    service_id: str = None,
    service_lookup: dict = None,
    vpc_endpoint_ids: Union[str, Iterable[str]] = None,
    vpc_endpoint_lookups: Union[Mapping, Iterable[Mapping]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Accepts one or more interface VPC endpoint connection requests to your VPC
    endpoint service.

    :param str service_id: The ID of the VPC endpoint service.
    :param dict service_lookup: Any kwargs that :py:func:`lookup_vpc_endpoint_service`
      accepts. Used to lookup ``service_id``.
    :type vpc_endpoint_ids: str or list(str)
    :param vpc_endpoint_ids: One or more IDs of interface VPC endpoints.
    :type vpc_endpoint_lookups: dict or list(dict)
    :param vpc_endpoint_lookups: One or more dicts of kwargs that
      :py:func:`lookup_vpc_endpoint` accepts. Used to lookup ``vpc_endpoint_ids``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``accept_vpc_endpoint_connections``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc_endpoint_service",
            "kwargs": service_lookup or {"service_id": service_id},
            "result_keys": "ServiceId",
        },
        {
            "service": "ec2",
            "name": "vpc_endpoint",
            "kwargs": vpc_endpoint_lookups
            or [{"vpc_endpoint_id": item} for item in vpc_endpoint_ids or []],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = {
            "ServiceId": res["vpc_endpoint_service"],
            "VpcEndpointIds": itertools.chain.from_iterable(res["vpc_endpoint"]),
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](
        client.accept_vpc_endpoint_connections, params
    )


def accept_vpc_peering_connection(
    vpc_peering_connection_id: str = None,
    vpc_peering_connection_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Accept a VPC peering connection request. To accept a request, the VPC peering
    connection must be in the pending-acceptance state, and you must be the owner
    of the peer VPC. Use DescribeVpcPeeringConnections to view your outstanding
    VPC peering connection requests.

    For an inter-region VPC peering connection request, you must accept the VPC
    peering connection in the region of the accepter VPC.

    :param str vpc_peering_connection_id: The ID of the VPC peering connection.
    :param dict vpc_peering_lookup: Any kwargs that :py:func:`lookup_vpc_peering_connection`
      accepts. Used to lookup ``vpc_peering_connection_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``accept_vpc_peering_connection``-
      call on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_vpc_peering_connections, boto3.client('ec2').accept_vpc_peering_connection
    """
    vpc_peering_connection_lookup = vpc_peering_connection_lookup or {
        "vpc_peering_connection_id": vpc_peering_connection_id
    }
    if "filters" not in vpc_peering_connection_lookup:
        vpc_peering_connection_lookup["filters"] = {}
    vpc_peering_connection_lookup["filters"].update(
        {"status-code": "pending-acceptance"}
    )
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc_peering_connection",
            "kwargs": vpc_peering_connection_lookup,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = {"VpcPeeringConnectionId": res["vpc_peering_connection"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](
        client.accept_vpc_peering_connection, params
    )


def allocate_address(
    address: str = None,
    public_ipv4_pool: str = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Allocates an Elastic IP address to your AWS account. After you allocate the
    Elastic IP address you can associate it with an instance or network interface.
    After you release an Elastic IP address, it is released to the IP address pool
    and can be allocated to a different AWS account.

    You can allocate an Elastic IP address from an address pool owned by AWS or
    from an address pool created from a public IPv4 address range that you have
    brought to AWS for use with your AWS resources using bring your own IP addresses
    (BYOIP).

    [EC2-VPC] If you release an Elastic IP address, you might be able to recover
    it. You cannot recover an Elastic IP address that you released after it is
    allocated to another AWS account. You cannot recover an Elastic IP address
    for EC2-Classic. To attempt to recover an Elastic IP address that you released,
    specify it in this operation.

    An Elastic IP address is for use either in the EC2-Classic platform or in a
    VPC. By default, you can allocate 5 Elastic IP addresses for EC2-Classic per
    region and 5 Elastic IP addresses for EC2-VPC per region.

    :param str address: The Elastic IP address to recover or an IPv4 address from
      an address pool.
    :param str public_ipv4_pool: The ID of an address pool that you own. Use this
      parameter to let Amazon EC2 select an address from the address pool. To
      specify a specific address from the address pool, use the ``address`` parameter
      instead.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``allocate_address``-call on succes.

    :depends: boto3.client('ec2').allocate_address
    """
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    params = salt.utils.data.filter_falsey(
        {"Domain": "vpc", "Address": address, "PublicIpv4Pool": public_ipv4_pool}
    )
    try:
        res = client.allocate_address(**params)
        return {"result": res}
    except (ParamValidationError, ClientError) as exp:
        return {"error": __utils__["boto3.get_error"](exp)["message"]}


def associate_address(
    allocation_id: str = None,
    address_lookup: Mapping = None,
    instance_id: str = None,
    instance_lookup: Mapping = None,
    public_ip: str = None,
    allow_reassociation: bool = None,
    network_interface_id: str = None,
    network_interface_lookup: Mapping = None,
    private_ip_address: str = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Associates an Elastic IP address, or carrier IP address (for instances that
    are in subnets in Wavelength Zones) with an instance or a network interface.
    Before you can use an Elastic IP address, you must allocate it to your account.

    An Elastic IP address is for use in either the EC2-Classic platform or in a VPC.

    If the Elastic IP address is already associated with a different instance,
    it is disassociated from that instance and associated with the specified instance.
    If you associate an Elastic IP address with an instance that has an existing
    Elastic IP address, the existing address is disassociated from the instance,
    but remains allocated to your account.

    [VPC in an EC2-Classic account] If you don't specify a private IP address,
    the Elastic IP address is associated with the primary IP address. If the Elastic
    IP address is already associated with a different instance or a network interface,
    you get an error unless you allow reassociation. You cannot associate an Elastic
    IP address with an instance or network interface that has an existing Elastic
    IP address.

    [Subnets in Wavelength Zones] You can associate an IP address from the telecommunication
    carrier to the instance or network interface.

    You cannot associate an Elastic IP address with an interface in a different
    network border group.

    :param str allocation_id: [EC2-VPC] The allocation ID. This is required for EC2-VPC.
    :param dict address_lookup: [EC2-VPC] Any kwargs that :py:func:`lookup_address`
      accepts. Used to lookup ``allocation_id``.
    :param str instance_id: The ID of the instance. This is required for EC2-Classic.
      For EC2-VPC, you can specify either the instance ID or the network interface
      ID, but not both. The operation fails if you specify an instance ID unless
      exactly one network interface is attached.
    :param dict instance_lookup: Any kwargs that :py:func:`lookup_instance` accepts.
      Used to lookup ``instance_id``.
    :param str public_ip: The Elastic IP address to associate with the instance.
      This is required for EC2-Classic.
    :param bool allow_reassociation: [EC2-VPC] For a VPC in an EC2-Classic account,
      specify true to allow an Elastic IP address that is already associated
      with an instance or network interface to be reassociated with the specified
      instance or network interface. Otherwise, the operation fails. In a VPC
      in an EC2-VPC-only account, reassociation is automatic, therefore you can
      specify false to ensure the operation fails if the Elastic IP address is
      already associated with another resource.
    :param str network_interface_id: [EC2-VPC] The ID of the network interface.
      If the instance has more than one network interface, you must specify a
      network interface ID.
      For EC2-VPC, you can specify either the instance ID or the network interface
      ID, but not both.
    :param dict network_interface_lookup: [EC2-VPC] Any kwargs that :py:func:`lookup_network_interface`
      accepts. Used to lookup ``network_interface_id``.
    :param str private_ip_address: [EC2-VPC] The primary or secondary private IP
      address to associate with the Elastic IP address. If no private IP address
      is specified, the Elastic IP address is associated with the primary private
      IP address.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``associate_address``-call
      on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "address",
            "kwargs": address_lookup or {"allocation_id": allocation_id},
        },
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookup or {"instance_id": instance_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "network_interface",
            "kwargs": network_interface_lookup
            or {"network_interface_id": network_interface_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = salt.utils.data.filter_falsey(
            {
                "AllocationId": res["address"],
                "InstanceId": res.get("instance"),
                "PublicIp": public_ip,
                "AllowReassociation": allow_reassociation,
                "NetworkInterfaceId": res.get("network_interface"),
                "PrivateIpAddress": private_ip_address,
            }
        )
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](client.associate_address, params)


def associate_dhcp_options(
    dhcp_options_id: str = None,
    dhcp_options_lookup: Mapping = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Associates a set of DHCP options (that you've previously created) with the
    specified VPC, or associates no DHCP options with the VPC.

    After you associate the options with the VPC, any existing instances and all
    new instances that you launch in that VPC use the options. You don't need to
    restart or relaunch the instances. They automatically pick up the changes
    within a few hours, depending on how frequently the instance renews its DHCP
    lease. You can explicitly renew the lease using the operating system on the
    instance.

    :param str dhcp_options_id: The ID of the DHCP options set, or ``default`` to
      associate no DHCP options with the VPC.
    :param dict dhcp_options_lookup: Any kwargs that :py:func:`lookup_dhcp_options`
      accepts. Used to lookup ``dhcp_options_id``.
    :param str vpc_id: The ID of the VPC to associate the options with.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      used to lookup ``vpc_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_dhcp_options, boto3.client('ec2').associate_dhcp_options
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "dhcp_options",
            "kwargs": dhcp_options_lookup or {"dhcp_options_id": dhcp_options_id},
        },
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = {
            "DhcpOptionsId": res["dhcp_options"],
            "VpcId": res["vpc"],
        }
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](client.associate_dhcp_options, params)


def associate_route_table(
    route_table_id: str = None,
    route_table_lookup: Mapping = None,
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Associates a subnet with a route table. The subnet and route table must be
    in the same VPC. This association causes traffic originating from the subnet
    to be routed according to the routes in the route table. The action returns
    an association ID, which you need in order to disassociate the route table
    from the subnet later. A route table can be associated with multiple subnets.

    :param str route_table_id: The ID of the route table to associate.
    :param dict route_table_lookup: Any kwargs that :py:func:`lookup_route_table`
      accepts. Used to lookup ``route_table_id``.
    :param str subnet_id: the ID of the subnet to associate with.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``associate_route_table``-call
      on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_subnets, boto3.client('ec2').describe_route_tables, boto3.client('ec2').associate_route_table
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "route_table",
            "kwargs": route_table_lookup or {"route_table_id": route_table_id},
        },
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = {
            "RouteTableId": res["route_table"],
            "SubnetId": res["subnet"],
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.associate_route_table, params)


def associate_subnet_cidr_block(
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    ipv6_cidr_block: str = None,
    ipv6_subnet: int = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Associates a CIDR block with your subnet. You can only associate a single
    IPv6 CIDR block with your subnet. An IPv6 CIDR block must have a prefix length
    of /64.

    :param str subnet_id: The ID of the subnet to work on.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
    :param str ipv6_cidr_block: The IPv6 CIDR block for your subnet. The subnet
      must have a /64 prefix length. Can not be used with ``ipv6_subnet``.
    :param int ipv6_subnet: The IPv6 subnet. This uses an implicit /64 netmask.
      Use this if you don't know the parent subnet and want to extract that
      from the VPC information. Can not be used with ``ipv6_cidr_block``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``associate_subnet_cidr_block``-
      call on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_subnets, boto3.client('ec2').describe_vpcs, boto3.client('ec2').associate_subnet_cidr_block
    """
    if not salt.utils.data.exactly_one((ipv6_cidr_block, ipv6_subnet)):
        raise SaltInvocationError(
            'You must specify exactly one of "ipv6_cidr_block" or "ipv6_subnet".'
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
            "result_keys": ["SubnetId", "VpcId"],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]["subnet"]
        subnet_id = res["SubnetId"]
        vpc_id = res["VpcId"]
    if ipv6_cidr_block is None:
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "vpc",
                "kwargs": {"vpc_id": vpc_id},
                "result_keys": "Ipv6CidrBlockAssociationSet",
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            ipv6_cidr_block_association_set = res["result"]["vpc"]
            if not ipv6_cidr_block_association_set:
                return {
                    "error": 'VPC "{}" does not have an ipv6_cidr_block.'.format(vpc_id)
                }
            ipv6_cidr_block = _derive_ipv6_cidr_subnet(
                ipv6_subnet, ipv6_cidr_block_association_set[0]["Ipv6CidrBlock"]
            )
    params = {"SubnetId": subnet_id, "Ipv6CidrBlock": ipv6_cidr_block}
    return __utils__["boto3.handle_response"](
        client.associate_subnet_cidr_block, params
    )


def associate_vpc_cidr_block(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    amazon_provided_ipv6_cidr_block: bool = None,
    cidr_block: str = None,
    ipv6_cidr_block_network_border_group: str = None,
    ipv6_pool: str = None,
    ipv6_cidr_block: str = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Associates a CIDR block with your VPC. You can associate a secondary IPv4 CIDR
    block, or you can associate an Amazon-provided IPv6 CIDR block. The IPv6 CIDR
    block size is fixed at /56.

    :param str vpc_id: The ID of the VPC to operate on.
    :param str vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param bool amazon_provided_ipv6_cidr_block: Requests an Amazon-provided IPv6
      CIDR block with a /56 prefix length for the VPC. You cannot specify the
      range of IPv6 addresses, or the size of the CIDR block.
    :param str cidr_block: An IPv4 CIDR block to associate with the VPC.
    :param str ipv6_cidr_block_network_border_group: The name of the location from
      which we advertise the IPV6 CIDR block. Use this parameter to limit the CIDR
      block to this location.
      You must set ``amazon_provided_ipv6_cidr_block`` to ``True`` to use this parameter.
      You can have one IPv6 CIDR block association per network border group.
    :param str ipv6_pool: The ID of an IPv6 address pool from which to allocate
      the IPv6 CIDR block.
    :param str ipv6_cidr_block: An IPv6 CIDR block from the IPv6 address pool.
      You must also specify ``IPv6Pool`` in the request.
      To let Amazon choose the IPv6 CIDR block for you, omit this parameter.
    :param bool blocking: Wait for the CIDR block to be associated.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``associate_vpc_cidr_block``-
      call on succes.

    :depends: boto3.client('ec2').associate_vpc_cidr_block
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = salt.utils.data.filter_falsey(
            {
                "AmazonProvidedIpv6CidrBlock": amazon_provided_ipv6_cidr_block,
                "CidrBlock": cidr_block,
                "VpcId": res["result"]["vpc"],
                "Ipv6CidrBlockNetworkBorderGroup": ipv6_cidr_block_network_border_group,
                "Ipv6Pool": ipv6_pool,
                "Ipv6CidrBlock": ipv6_cidr_block,
            }
        )
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    ret = __utils__["boto3.handle_response"](client.associate_vpc_cidr_block, params)
    if "error" in ret:
        return ret
    if blocking:
        ip_version_filler_uc = "" if cidr_block else "Ipv6"
        params = {
            "Filters": __utils__["boto3.dict_to_boto_filters"](
                {
                    "{}cidr-block-association.association-id".format(
                        "" if cidr_block else "ipv6-"
                    ): ret["result"][
                        "{}CidrBlockAssociation".format(ip_version_filler_uc)
                    ][
                        "AssociationId"
                    ]
                }
            )
        }
        res = __utils__["boto3.wait_resource"](
            "vpc_{}cidr_block".format("" if cidr_block else "ipv6_"),
            "associated",
            params=params,
            client=client,
        )
        if "error" in res:
            return res
        if res.get("result") is True:
            # Overwrite earlier result to show that the CIDR block is associated
            ret["result"]["{}CidrBlockAssociation".format(ip_version_filler_uc)][
                "{}CidrBlockState".format(ip_version_filler_uc)
            ]["State"] = "associated"
    return ret


def attach_internet_gateway(
    internet_gateway_id: str = None,
    internet_gateway_lookup: Mapping = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Attaches an internet gateway to a VPC, enabling connectivity between the
    internet and the VPC.

    :param str internet_gateway_id: The ID of the Internet gateway to attach.
    :param dict internet_gateway_lookup: Any kwargs that :py:func:`lookup_internet_gateway`
      accepts. Used to lookup ``internet_gateway_id``.
    :param str vpc_id: The ID of the VPC to attach the Internet gateway to.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_internet_gateways, boto3.client('ec2').describe_vpcs, boto3.client('ec2').attach_internet_gateway
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "internet_gateway",
            "kwargs": internet_gateway_lookup
            or {"internet_gateway_id": internet_gateway_id},
        },
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = {
            "InternetGatewayId": res["internet_gateway"],
            "VpcId": res["vpc"],
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.attach_internet_gateway, params)


def attach_network_interface(
    device_index: int,
    instance_id: str = None,
    instance_lookup: Mapping = None,
    network_interface_id: str = None,
    network_interface_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Attaches a network interface to an instance.

    :param int device_index: The index of the device for the network interface
      attachment.
    :param str instance_id: The ID of the instance.
    :param dict instance_lookup: Any kwargs that :py:func:`lookup_instance` accepts.
      Used to lookup ``instance_id``.
    :param str network_interface_id: The ID of the network interface.
    :param dict network_interface_lookup: Any kwargs that :py:func:`lookup_network_interface`
      accepts. Used to lookup ``network_interface_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``attach_network_interface``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"name": "instance", "kwargs": instance_lookup or {"instance_id": instance_id}},
        {
            "service": "ec2",
            "name": "network_interface",
            "kwargs": network_interface_lookup
            or {"network_interface_id": network_interface_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = {
            "DeviceIndex": device_index,
            "InstanceId": res["instance"],
            "NetworkInterfaceId": res["network_interface"],
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.attach_network_interface, params)


def attach_volume(
    device: str,
    instance_id: str = None,
    instance_lookup: Mapping = None,
    volume_id: str = None,
    volume_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Attaches an EBS volume to a running or stopped instance and exposes it to the
    instance with the specified device name.

    Encrypted EBS volumes must be attached to instances that support Amazon EBS
    encryption.

    After you attach an EBS volume, you must make it available.

    If a volume has an AWS Marketplace product code:
      The volume can be attached only to a stopped instance.
      AWS Marketplace product codes are copied from the volume to the instance.
      You must be subscribed to the product.
      The instance type and operating system of the instance must support the
      product. For example, you can't detach a volume from a Windows instance
      and attach it to a Linux instance.

    :param str device: The device name (for example, ``/dev/sdh`` or ``xvdh``).
    :param str instance_id: The ID of the instance.
    :param dict instance_lookup: Any kwargs that :py:func:`lookup_instance` accepts.
      Used to lookup ``instance_id``.
    :param str volume_id: The ID of the EBS volume.  The volume and instance must
      be within the same Availability Zone.
    :param dict volume_lookup: Any kwargs that :py:func:`lookup_volume` accepts.
      Used to lookup ``volume_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``attach_volume``-call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookup or {"instance_id": instance_id},
        },
        {
            "service": "ec2",
            "name": "volume",
            "kwargs": volume_lookup or {"volume_id": volume_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = {
            "Device": device,
            "InstanceId": res["instance"],
            "VolumeId": res["volume"],
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.attach_volume, params)


def attach_vpn_gateway(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    vpn_gateway_id: str = None,
    vpn_gateway_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Attaches a virtual private gateway to a VPC. You can attach one virtual private
    gateway to one VPC at a time.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param str vpn_gateway_id: The ID of the virtual private gateway.
    :param dict vpn_gateway_lookup: Any kwargs that :py:func:`lookup_vpn_gateway` accepts.
      Used to lookup ``vpn_gateway_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``attach_vpn_gateway``-call
      on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        {
            "service": "ec2",
            "name": "vpn_gateway",
            "kwargs": vpn_gateway_lookup or {"vpn_gateway_id": vpn_gateway_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = {
            "VpcId": res["vpc"],
            "VpnGatewayId": res["vpn_gateway"],
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.attach_vpn_gateway, params)


@_arguments_to_list("ip_permissions")
def authorize_security_group_egress(
    group_id: str = None,
    group_lookup: Mapping = None,
    ip_permissions: Union[Mapping, Iterable[Mapping]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    [VPC only] Adds the specified egress rules to a security group for use witha VPC.
    An outbound rule permits instances to send traffic to the specified IPv4 or
    IPv6 CIDR address ranges, or to the instances associated with the specified
    destination security groups.

    You specify a protocol for each rule (for example, TCP). For the TCP and UDP
    protocols, you must also specify the destination port or port range. For the
    ICMP protocol, you must also specify the ICMP type and code. You can use -1
    for the type or code to mean all types or all codes.

    Rule changes are propagated to affected instances as quickly as possible.
    However, a small delay might occur.

    :param str group_id: The ID of the security group to add egress rules to.
    :param dict group_lookup: Any kwargs that :py:func:`lookup_security_group`
      accepts. Used to lookup ``security_group_id``.
    :type ip_permissions: dict or list(dict)
    :param ip_permissions: One or more IP permissions. You can't specify
      a destination security group and a CIDR IP address range in the same set
      of permissions. These dicts can either contain the structure as described
      `here <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_IpPermission.html>`__
      or contain the kwargs that :py:func:`build_ip_permission` accepts.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
    try:
        ip_permissions = [
            build_ip_permission(item)["result"] for item in ip_permissions
        ]
    except (TypeError, KeyError):
        pass  # to Boto as-is
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": group_lookup or {"group_id": group_id},
            "result_keys": "GroupId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "GroupId": res["result"]["security_group"],
            "IpPermissions": ip_permissions,
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](
        client.authorize_security_group_egress, params
    )


@_arguments_to_list("ip_permissions")
def authorize_security_group_ingress(
    group_id: str = None,
    group_lookup: Mapping = None,
    ip_permissions: Union[Mapping, Iterable[Mapping]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Adds the specified ingress rules to a security group.

    An inbound rule permits instances to receive traffic from the specified IPv4
    or IPv6 CIDR address ranges, or from the instances associated with the specified
    destination security groups.

    You specify a protocol for each rule (for example, TCP). For TCP and UDP, you
    must also specify the destination port or port range. For ICMP/ICMPv6, you
    must also specify the ICMP/ICMPv6 type and code. You can use -1 to mean all
    types or all codes.

    Rule changes are propagated to instances within the security group as quickly
    as possible. However, a small delay might occur.

    :param str group_id: The ID of the security group to add ingress rules to.
    :param dict group_lookup: Any kwargs that :py:func:`lookup_security_group`
      accepts. Used to lookup ``security_group_id``.
    :type ip_permissions: dict or list(dict)
    :param ip_permissions: One or more IP permissions. You can't specify
      a source security group and a CIDR IP address range in the same set
      of permissions. These dicts can either contain the structure as described
      `here <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_IpPermission.html>`__
      or contain the kwargs that :py:func:`build_ip_permission` accepts.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
    try:
        ip_permissions = [
            build_ip_permission(item)["result"] for item in ip_permissions
        ]
    except (TypeError, KeyError):
        pass  # to Boto as-is
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": group_lookup or {"group_id": group_id},
            "result_keys": "GroupId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "GroupId": res["result"]["security_group"],
            "IpPermissions": ip_permissions,
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](
        client.authorize_security_group_ingress, params
    )


@_arguments_to_list("spot_fleet_request_ids")
def cancel_spot_fleet_requests(
    spot_fleet_request_ids: Union[str, Iterable[str]] = None,
    terminate_instances: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Cancels the specified Spot Fleet requests.

    After you cancel a Spot Fleet request, the Spot Fleet launches no new Spot Instances.
    You must specify whether the Spot Fleet should also terminate its Spot Instances.
    If you terminate the instances, the Spot Fleet request enters the ``cancelled_terminating``
    state. Otherwise, the Spot Fleet request enters the ``cancelled_running`` state
    and the instances continue to run until they are interrupted or you terminate
    them manually.

    :type spot_fleet_request_ids: str or list(str)
    :param spot_fleet_request_ids: The IDs of the Spot Fleet requests.
    :param bool terminate_instances: Indicates whether to terminate instances for
      a Spot Fleet request if it is canceled successfully.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``cancel_spot_fleet_requests``-
      call on succes.
    """
    params = salt.utils.data.filter_falsey(
        {
            "SpotFleetRequestIds": spot_fleet_request_ids,
            "TerminateInstances": terminate_instances,
        }
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.cancel_spot_fleet_requests, params)


@_arguments_to_list("spot_instance_request_ids", "spot_instance_request_lookups")
def cancel_spot_instance_requests(
    spot_instance_request_ids: Union[str, Iterable[str]] = None,
    spot_instance_request_lookups: Union[Mapping, Iterable[Mapping]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Cancels one or more Spot Instance requests.

    :type spot_instance_request_ids: str or list(str)
    :param spot_instance_request_ids: One or more Spot Instance request IDs.
    :type spot_instance_request_lookups: dict or list(dict)
    :param spot_instance_request_lookups: Any kwargs or list of
      kwargs that :py:func:`lookup_spot_instance_request` accepts. Used to lookup
      ``spot_instance_request_ids``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``cancel_spot_instance_requests``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "spot_instance_requests",
            "kwargs": spot_instance_request_lookups
            or [
                {"spot_instance_request_id": item}
                for item in spot_instance_request_ids or []
            ],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "SpotInstanceRequestIds": itertools.chain.from_iterable(
                res["result"]["spot_instance_requests"]
            ),
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](
        client.cancel_spot_instance_requests, params
    )


def copy_image(
    name: str,
    source_region: str,
    source_image_id: str = None,
    source_image_lookup: Mapping = None,
    description: str = None,
    encrypted: bool = None,
    kms_key_id: str = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Initiates the copy of an AMI from the specified source Region to the current
    Region. You specify the destination Region by using its endpoint when making
    the request.

    Copies of encrypted backing snapshots for the AMI are encrypted. Copies of
    unencrypted backing snapshots remain unencrypted, unless you set Encrypted
    during the copy operation. You cannot create an unencrypted copy of an encrypted
    backing snapshot.

    :param str name: The name of the new AMI in the destination Region.
    :param str source_region: The name of the Region that contains the AMI to copy.
    :param str source_image_id: The ID of the AMI to copy.
    :param dict source_image_lookup: Any kwargs that :py:func:`lookup_image` accepts.
      Used to lookup ``source_image_id``.
    :param str description: A description for the new AMI in the destination Region.
    :param bool encrypted: Specifies whether the destination snapshots of the copied
      image should be encrypted. You can encrypt a copy of an unencrypted snapshot,
      but you cannot create an unencrypted copy of an encrypted snapshot. The
      default CMK for EBS is used unless you specify a non-default AWS Key Management
      Service (AWS KMS) CMK using ``kms_key_id``.
    :param str kms_key_id: An identifier for the symmetric AWS Key Management Service
      (AWS KMS) customer master key (CMK) to use when creating the encrypted
      volume. This parameter is only required if you want to use a non-default
      CMK; if this parameter is not specified, the default CMK for EBS is used.
      If a KmsKeyId is specified, the Encrypted flag must also be set.
      To specify a CMK, use its key ID, Amazon Resource Name (ARN), alias name,
      or alias ARN. When using an alias name, prefix it with "alias/". For example:

        Key ID: 1234abcd-12ab-34cd-56ef-1234567890ab
        Key ARN: arn:aws:kms:us-east-2:111122223333:key/1234abcd-12ab-34cd-56ef-1234567890ab
        Alias name: alias/ExampleAlias
        Alias ARN: arn:aws:kms:us-east-2:111122223333:alias/ExampleAlias

      AWS parses KmsKeyId asynchronously, meaning that the action you call may
      appear to complete even though you provided an invalid identifier. This
      action will eventually report failure.
      The specified CMK must exist in the Region that the snapshot is being copied to.
      Amazon EBS does not support asymmetric CMKs.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``copy_image``-call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "image",
            "kwargs": source_image_lookup or {"image_id": source_image_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = salt.utils.data.filter_falsey(
            {
                "Description": description,
                "Encrypted": encrypted,
                "KmsKeyId": kms_key_id,
                "Name": name,
                "SourceImageId": res["result"]["image"],
                "SourceRegion": source_region,
            }
        )
    params.update(
        {"ClientToken": hashlib.sha1(json.dumps(params).encode("utf8")).hexdigest()}
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.copy_image, params)


def copy_snapshot(
    source_region: str,
    source_snapshot_id: str = None,
    source_snapshot_lookup: Mapping = None,
    description: str = None,
    encrypted: bool = None,
    kms_key_id: str = None,
    tags: Mapping = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Copies a point-in-time snapshot of an EBS volume and stores it in Amazon S3.
    You can copy the snapshot within the same Region or from one Region to another.
    You can use the snapshot to create EBS volumes or Amazon Machine Images (AMIs).

    Copies of encrypted EBS snapshots remain encrypted. Copies of unencrypted snapshots
    remain unencrypted, unless you enable encryption for the snapshot copy operation.
    By default, encrypted snapshot copies use the default AWS Key Management Service
    (AWS KMS) customer master key (CMK); however, you can specify a different CMK.

    To copy an encrypted snapshot that has been shared from another account, you
    must have permissions for the CMK used to encrypt the snapshot.

    Snapshots created by copying another snapshot have an arbitrary volume ID that
    should not be used for any purpose.

    :param str source_region: The ID of the Region that contains the snapshot to
      be copied.
    :param str source_snapshot_id: The ID of the EBS snapshot to copy.
    :param dict source_snapshot_lookup: Any kwargs that :py:func:`lookup_snapshot` accepts.
      Used to lookup ``source_snapshot_id``.
    :param str description: A description for the EBS snapshot.
    :param bool encrypted: To encrypt a copy of an unencrypted snapshot if encryption
      by default is not enabled, enable encryption using this parameter. Otherwise,
      omit this parameter. Encrypted snapshots are encrypted, even if you omit
      this parameter and encryption by default is not enabled. You cannot set
      this parameter to false.
    :param str kms_key_id: The identifier of the AWS Key Management Service (AWS KMS)
      customer master key (CMK) to use for Amazon EBS encryption. If this parameter
      is not specified, your AWS managed CMK for EBS is used. If KmsKeyId is
      specified, the encrypted state must be ``True``.
      You can specify the CMK using any of the following:

        Key ID. For example, key/1234abcd-12ab-34cd-56ef-1234567890ab.
        Key alias. For example, alias/ExampleAlias.
        Key ARN. For example, arn:aws:kms:us-east-1:012345678910:key/abcd1234-a123-456a-a12b-a123b4cd56ef.
        Alias ARN. For example, arn:aws:kms:us-east-1:012345678910:alias/ExampleAlias.

      AWS authenticates the CMK asynchronously. Therefore, if you specify an
      ID, alias, or ARN that is not valid, the action can appear to complete,
      but eventually fails.
    :param dict tags: The tags to apply to a resource when the resource is being created.
    :param bool blocking: Wait for the snapshot to become available.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``copy_snapshot``-call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "snapshot",
            "kwargs": source_snapshot_lookup or {"snapshot_id": source_snapshot_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {
                "params": {
                    "Description": description,
                    "Encrypted": encrypted,
                    "KmsKeyId": kms_key_id,
                    "SourceRegion": source_region,
                    "SourceSnapshotId": res["result"]["snapshot"],
                },
                "boto_function_name": "copy_snapshot",
                "tags": tags,
                "wait_until_state": "completed" if blocking else None,
                "client": client,
            },
            recurse_depth=1,
        )
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "snapshot"
    )


def create_customer_gateway(
    bgp_asn: int,
    gateway_type: str,
    public_ip: str = None,
    certificate_arn: str = None,
    device_name: str = None,
    tags: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Provides information to AWS about your VPN customer gateway device. The customer
    gateway is the appliance at your end of the VPN connection. (The device on
    the AWS side of the VPN connection is the virtual private gateway.) You must
    provide the Internet-routable IP address of the customer gateway's external
    interface. The IP address must be static and can be behind a device performing
    network address translation (NAT).

    For devices that use Border Gateway Protocol (BGP), you can also provide the
    device's BGP Autonomous System Number (ASN). You can use an existing ASN assigned
    to your network. If you don't have an ASN already, you can use a private ASN
    (in the 64512 - 65534 range).

    Note: Amazon EC2 supports all 2-byte ASN numbers in the range of 1 - 65534,
    with the exception of 7224, which is reserved in the us-east-1 Region, and
    9059, which is reserved in the eu-west-1 Region.

    Warning: To create more than one customer gateway with the same VPN type, IP
    address, and BGP ASN, specify a unique device name for each customer gateway.
    Identical requests return information about the existing customer gateway and
    do not create new customer gateways.

    :param int bgp_asn: For devices that support BGP, the customer gateway's BGP ASN.
    :param str gateway_type: The type of VPN connection that this customer gateway
      supports (ipsec.1).
    :param str public_ip: The Internet-routable IP address for the customer gateway's
      outside interface. The address must be static.
    :param str certificate_arn: The Amazon Resource Name (ARN) for the customer
      gateway certificate.
    :param str device_name: A name for the customer gateway device.
      Length Constraints: Up to 255 characters.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_customer_gateway``-call
      on succes.
    """
    params = salt.utils.data.filter_falsey(
        {
            "BgpAsn": bgp_asn,
            "PublicIp": public_ip,
            "CertificateArn": certificate_arn,
            "Type": gateway_type,
            "DeviceName": device_name,
        }
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.create_resource"](
        "customer_gateway",
        params=params,
        tags=tags,
        client=client,
    )


@_arguments_to_list("domain_name_servers", "ntp_servers", "netbios_name_servers")
def create_dhcp_options(
    domain_name_servers: Union[str, Iterable[str]] = None,
    domain_name: str = None,
    ntp_servers: Union[str, Iterable[str]] = None,
    netbios_name_servers: Union[str, Iterable[str]] = None,
    netbios_node_type: str = None,
    tags: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a set of DHCP options for your VPC. After creating the set, you must
    associate it with the VPC, causing all existing and new instances that you
    launch in the VPC to use this set of DHCP options.

    :param list domain_name_servers: The IP addresses of up to four domain name servers,
      or AmazonProvidedDNS. The default DHCP option set specifies AmazonProvidedDNS.
      If specifying more than one domain name server, specify the IP addresses
      in a single parameter, separated by commas. To have your instance receive
      a custom DNS hostname as specified in domain-name , you must set domain-name-servers
      to a custom DNS server.
    :param str domain_name: If you're using AmazonProvidedDNS in ``us-east-1``, specify
      ``ec2.internal``. If you're using AmazonProvidedDNS in another Region,
      specify region.compute.internal (for example, ``ap-northeast-1.compute.internal``).
      Otherwise, specify a domain name (for example, ExampleCompany.com ).
      This value is used to complete unqualified DNS hostnames. Important:
      Some Linux operating systems accept multiple domain names separated by
      spaces. However, Windows and other Linux operating systems treat the
      value as a single domain, which results in unexpected behavior. If your
      DHCP options set is associated with a VPC that has instances with multiple
      operating systems, specify only one domain name.
    :param list ntp_servers: The IP addresses of up to four Network Time Protocol (NTP) servers.
    :param list netbios_name_servers: The IP addresses of up to four NetBIOS name servers.
    :param str netbios_node_type: The NetBIOS node type ("1", "2", "4", or "8").
      We recommend that you specify "2" (broadcast and multicast are not currently
      supported). For more information about these node types, see RFC 2132.
    :param dict tags: Tags to assign to the DHCP option set after creation.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_dhcp_options``-call
      on succes.

    :depends: boto3.client('ec2').create_dhcp_options
    """
    params = salt.utils.data.filter_falsey(
        {
            "DhcpConfigurations": [
                {"Key": "domain-name-servers", "Values": domain_name_servers}
                if domain_name_servers
                else None,
                {"Key": "domain-name", "Values": [domain_name]}
                if domain_name
                else None,
                {"Key": "ntp-servers", "Values": ntp_servers} if ntp_servers else None,
                {"Key": "netbios-name-servers", "Values": netbios_name_servers}
                if netbios_name_servers
                else None,
                {"Key": "netbios-node-type", "Values": [str(netbios_node_type)]}
                if netbios_node_type
                else None,
            ],
        }
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.create_resource"](
        "dhcp_options",
        params=params,
        tags=tags,
        client=client,
    )


@_arguments_to_list("block_device_mappings")
def create_image(
    name: str,
    instance_id: str = None,
    instance_lookup: Mapping = None,
    block_device_mappings: Union[Mapping, Iterable[Mapping]] = None,
    description: str = None,
    no_reboot: bool = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates an Amazon EBS-backed AMI from an Amazon EBS-backed instance that is
    either running or stopped.

    If you customized your instance with instance store volumes or EBS volumes
    in addition to the root device volume, the new AMI contains block device mapping
    information for those volumes. When you launch an instance from this new AMI,
    the instance automatically launches with those additional volumes.

    :param str name: A name for the new image.
      Constraints: 3-128 alphanumeric characters, parentheses (()), square
      brackets ([]), spaces ( ), periods (.), slashes (/), dashes (-), single
      quotes ('), at-signs (@), or underscores(_)
    :param str instance_id: The ID of the instance.
    :param dict instance_lookup: Any kwargs that :py:func`lookup_instance` accepts.
      Used to lookup ``instance_id``.
    :type block_device_mappings: dict or list(dict)
    :param block_device_mappings: The block device mappings.
      This parameter cannot be used to modify the encryption status of existing
      volumes or snapshots. To create an AMI with encrypted snapshots, use the
      ``copy_image`` function.
      These dicts can either contain the structure as described
      `here <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_BlockDeviceMapping.html>`__
      or contain the kwargs that :py:func:`build_block_device_mapping` accepts.
    :param str description: A description for the new image.
    :param bool no_reboot:  By default, Amazon EC2 attempts to shut down and reboot
      the instance before creating the image. If the 'No Reboot' option is set,
      Amazon EC2 doesn't shut down the instance before creating the image. When
      this option is used, file system integrity on the created image can't be
      guaranteed.
    :param bool blocking: Wait for the image to become available.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_image``-call on succes.
    """
    try:
        block_device_mappings = [
            build_block_device_mapping(item)["result"] for item in block_device_mappings
        ]
    except (TypeError, KeyError):
        # Probably unexpected kwargs to build_block_device_mapping.
        pass  # to Boto as-is
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookup or {"instance_id": instance_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {
                "params": {
                    "BlockDeviceMappings": block_device_mappings,
                    "Description": description,
                    "InstanceId": res["result"]["instance"],
                    "Name": name,
                    "NoReboot": no_reboot,
                },
                "wait_until_state": "available" if blocking else None,
                "client": client,
            },
            recurse_depth=1,
        )
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "image"
    )


def create_internet_gateway(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    tags: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates an internet gateway for use with a VPC.
    Optionally attaches it to a VPC if it is specified via either ``vpc_id`` or
    ``vpc_lookup``.

    :param str vpc_id: The ID of the VPC to attach the IGW to after creation.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param dict tags: Tags to assign to the Internet gateway after creation.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_internet_gateway``-
      call on succes.

    :depends: boto3.client('ec2').create_internet_gateway, boto3.client('ec2').describe_internet_gateways, boto3.client('ec2').describe_vpcs, boto3.client('ec2').attach_internet_gateway
    """
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.create_resource"](
        "internet_gateway",
        tags=tags,
        client=client,
    )
    if "error" in res:
        return res
    ret = res
    igw_id = res["result"].get("InternetGatewayId")
    if igw_id and (vpc_id or vpc_lookup):
        res = attach_internet_gateway(
            internet_gateway_id=igw_id,
            vpc_id=vpc_id,
            vpc_lookup=vpc_lookup,
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        )
        if "error" in res:
            ret.update(res)
        else:
            # Describe the internet gateway so we can update the attachment information in ret
            res = describe_internet_gateways(internet_gateway_ids=igw_id, client=client)
            if "error" in res:
                ret.update(res)
            else:
                ret["result"] = res["result"][0]
    return ret


def create_key_pair(
    key_name: str,
    tags: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a 2048-bit RSA key pair with the specified name. Amazon EC2 stores
    the public key and displays the private key for you to save to a file. The
    private key is returned as an unencrypted PEM encoded PKCS#1 private key. If
    a key with the specified name already exists, Amazon EC2 returns an error.

    You can have up to five thousand key pairs per Region.

    The key pair returned to you is available only in the Region in which you create
    it. If you prefer, you can create your own key pair using a third-party tool
    and upload it to any Region using ``import_key_pair``.

    :param str key_name: A unique name for the key pair.
      Constraints: Up to 255 ASCII characters
    :param dict tags: The tags to apply to a resource when the resource is being created.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_key_pair``-call on succes.
    """
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.create_resource"](
        "key_pair",
        params={"KeyName": key_name},
        tags=tags,
        client=client,
    )


@_arguments_to_list("block_device_mappings", "network_interfaces")
def create_launch_template(
    launch_template_name: str,
    version_description: str = None,
    kernel_id: str = None,
    ebs_optimized: bool = None,
    iam_instance_profile: Mapping = None,
    block_device_mappings: Union[Mapping, Iterable[Mapping]] = None,
    network_interfaces: Union[Mapping, Iterable[Mapping]] = None,
    image_id: str = None,
    image_lookup: Mapping = None,
    instance_type: str = None,
    key_name: str = None,
    monitoring_enabled: bool = None,
    placement: Mapping = None,
    ram_disk_id: str = None,
    disable_api_termination: bool = None,
    instance_initiated_shutdown_behavior: str = None,
    user_data: str = None,
    tag_specifications: Mapping = None,
    elastic_gpu_type: str = None,
    elastic_inference_accelerators: Iterable[Mapping] = None,
    security_group_ids: Union[str, Iterable[str]] = None,
    security_group_lookups: Union[Mapping, Iterable[Mapping]] = None,
    instance_market_options: Mapping = None,
    credit_specification: str = None,
    cpu_options: Mapping = None,
    capacity_reservation_specification: Mapping = None,
    license_specifications: Iterable[str] = None,
    hibernation_configured: bool = None,
    metadata_options: Mapping = None,
    tags: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a launch template. A launch template contains the parameters to launch
    an instance. When you launch an instance using RunInstances , you can specify
    a launch template instead of providing the launch parameters in the request.

    :param str launch_template_name: A name for the launch template.
    :param str version_description: A description for the first version of the
      launch template.
    :param str kernel_id: The ID of the kernel.
      Warning: We recommend that you use PV-GRUB instead of kernels and RAM disks.
    :param bool ebs_optimized: Indicates whether the instance is optimized for
      Amazon EBS I/O. This optimization provides dedicated throughput to Amazon
      EBS and an optimized configuration stack to provide optimal Amazon EBS
      I/O performance. This optimization isn't available with all instance types.
      Additional usage charges apply when using an EBS-optimized instance.
    :param dict iam_instance_profile: The IAM instance profile. This consists of:
      - Arn (str): The Amazon Resource Name (ARN) of the instance profile.
      - Name (str): The name of the instance profile.
    :type block_device_mappings: dict or list(dict)
    :param block_device_mappings: The block device mapping. These dicts can either
      contain the structure as described
      `here <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_BlockDeviceMapping.html>`__
      or contain the kwargs that :py:func:`build_block_device_mapping` accepts.
    :type network_interfaces: dict or list(dict)
    :param network_interfaces: One or more network interface configurations.
      These dicts can either contain the structure as described
      `here <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_LaunchTemplateInstanceNetworkInterfaceSpecificationRequest.html>`__
      or contain the kwargs that :py:func:`build_network_interface_config` accepts.
    :param str image_id: The ID of the AMI.
    :param dict image_lookup: Any kwargs that :py:func:`lookup_image` accepts.
      Used to ``image_id``.
    :param str instance_type: The instance type.
    :param str key_name: The name of the key pair. You can create a key pair using
      ``create_key_pair`` or ``import_key_pair``.
      Warning: If you do not specify a key pair, you can't connect to the instance
      unless you choose an AMI that is configured to allow users another way
      to log in.
    :param bool monitoring_enabled: Specify true to enable detailed monitoring.
      Otherwise, basic monitoring is enabled.
    :param dict placement: The placement for the instance. The dict consists of: TODO: builder

      - AvailabilityZone (str): The availability zone for the instance.
      - Affinity (str): the affinity setting for an instance on a Dedicated Host.
      - GroupName (str): The name of the placement group for the instance.
      - HostId (str): The ID of the Dedicated Host for the instance.
      - Tenancy (str): The tenancy of the instance (if the instance is running
        in a VPC). An instance with a tenancy of ``dedicated`` runs on single-tenant
        hardware.
      - HostResourceGroupArn (str): The ARN of the host resource group in which
        to launch the instances. If you specify a host resource group ARN, omit
        the Tenancy parameter or set it to ``host``.
      - PartitionNumber (int): The number of the partition the instance should
        launch in. Valid only if the placement group strategy is set to ``partition``.
    :param str ram_disk_id: The ID of the RAM disk.
      Warning: We recommend that you use PV-GRUB instead of kernels and RAM disks.
    :param bool disable_api_termination: If you set this parameter to ``True``,
      you can't terminate the instance using the Amazon EC2 console, CLI, or API;
      otherwise, you can. To change this attribute after launch, use ``modify_instance_attribute``.
      Alternatively, if you set ``instance_initiated_shutdown_behavior`` to
      ``terminate``, you can terminate the instance by running the shutdown command
      from the instance.
    :param str instance_initiated_shutdown_behavior: Indicates whether an instance
      stops or terminates when you initiate shutdown from the instance (using
      the operating system command for system shutdown).
      Default: stop
    :param str user_data: The Base64-encoded user data to make available to the instance.
    :param dict instance_tags: The tags to apply to the resources during launch.
      The specified tags are applied to all instances or volumes that are created
      during launch.
    :param str elastic_gpu_type: The type of Elastic Graphics accelerator to associate
      with the instance.
    :param list(dict) elastic_inference_accelerators: The elastic inference accelerator
      for the instance. The dict consists of:

      - Type (str): The type of elastic inference accelerator.
        Allowed values are: eia1.medium, eia1.large, and eia1.xlarge.
      - Count (int): The number of elastic inference accelerators to attach to
        the instance. Default: 1
    :param list(str) security_group_ids: One or more security group IDs. You can
      create a security group using :py:func:`create_security_group`.
    :param list(dict) security_group_lookups: List of dicts that contain kwargs
      that :py:func:`lookup_security_group` accepts. Used to lookup ``security_group_ids``.
    :param dict instance_market_options: The market (purchasing) option for the
      instances. This dict consists of:

      - MarketType (str): The market type.
      - SpotOptions (dict): The options for Spot instances. This dict consists of:

        - MaxPrice (str): The maximum hourly price you're willing to pay for the
          Spot Instances
        - SpotInstanceType (str): The Spot Instance request type.
        - BlockDurationMinutes (int): The required duration for the Spot Instances
          (also known as Spot blocks), in minutes. This value must be a multiple
          of 60 (60, 120, 180, 240, 300, or 360).
        - ValidUntil (datetime): The end date of the request. For a one-time request,
          the request remains active until all instances launch, the request is
          canceled, or this date is reached. If the request is persistent, it remains
          active until it is canceled or this date and time is reached. The default
          end date is 7 days from the current date.
        - InstanceInterruptionBehavior: The behavior when a Spot Instance is interrupted.
          The default is ``terminate``.
    :param str credit_specification: The credit option for CPU usage of a T2, T3,
      or T3a instance. Allowed values: ``standard``, ``unlimited``.
    :param dict cpu_options: The CPU options for the instance. This dict consists of:

      - CoreCount (int): The number of CPU cores for the instance.
      - ThreadsPerCore (int): The number of threads per CPU core. To disable multithreading
        for the instance, specify a value of 1. Otherwise, specify the default
        value of 2.
    :param dict capacity_reservation_specification: The Capacity Reservation targeting
      option. If you do not specify this parameter, the instance's Capacity Reservation
      preference defaults to ``open``, which enables it to run in any open Capacity
      Reservation that has matching attributes (instance type, platform, Availability Zone).
      This dict consists of:

      - CapacityReservationPreference (str): Indicates the instance's Capacity
        Reservation preferences. Possible preferences include:

        - ``open``: The instance can run in any open Capacity Reservation that has
          matching attributes (instance type, platform, Availability Zone).
        - ``none``: The instance avoids running in a Capacity Reservation even if
          one is available. The instance runs in On-Demand capacity.
      - CapacityReservationTarget (dict): Information about the target Capacity
        Reservation or Capacity Reservation group. This dict consists of:

        - CapacityReservationId (str): The ID of the Capacity Reservation in which
          to run the instance.
        - CapacityReservationResourceGroupArn (str): The ARN of the Capacity Reservation
          resource group in which to run the instance.
    :param list(str) license_specifications: List of Amazon Resource Names (ARNs)
      of the license configurations.
    :param bool hibernation_configured: If you set this parameter to ``True``,
      the instance is enabled for hibernation. Default: ``False``.
    :param dict metadata_options: The metadata options for the instance. This dict
      consists of:

      - HttpTokens (str): The state of token usage for your instance metadata requests.
        If the parameter is not specified in the request, the default state is ``optional``.
        If the state is ``optional``, you can choose to retrieve instance metadata
        with or without a signed token header on your request. If you retrieve
        the IAM role credentials without a token, the version 1.0 role credentials
        are returned. If you retrieve the IAM role credentials using a valid signed
        token, the version 2.0 role credentials are returned.
        If the state is ``required``, you must send a signed token header with
        any instance metadata retrieval requests. In this state, retrieving the
        IAM role credentials always returns the version 2.0 credentials; the version
        1.0 credentials are not available.
      - HttpPutResponseHopLimit (int): The desired HTTP PUT response hop limit
        for instance metadata requests. The larger the number, the further instance
        metadata requests can travel. Default: 1. Allowed values: Integers from 1 to 64.
      - HttpEndpoint (str): This parameter enables or disables the HTTP metadata
        endpoint on your instances. If the parameter is not specified, the default
        state is ``enabled``. Note: If you specify a value of ``disabled``, you
        will not be able to access your instance metadata.
    :param dict tags: The tags to apply to the launch template during creation.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_launch_template``-call
      on succes.
    """
    try:
        block_device_mappings = [
            build_block_device_mapping(item)["result"] for item in block_device_mappings
        ]
    except (TypeError, KeyError):
        pass  # to Boto as-is
    try:
        network_interfaces = [
            build_network_interface_config(item)["result"]
            for item in network_interfaces
        ]
    except (TypeError, KeyError):
        pass  # to Boto as-is
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "image",
            "kwargs": image_lookup or {"image_id": image_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": security_group_lookups
            or [{"group_id": group_id} for group_id in security_group_ids or []],
            "required": False,
            "result_keys": "GroupId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = salt.utils.data.filter_falsey(
            {
                "LaunchTemplateName": launch_template_name,
                "VersionDescription": version_description,
                "LaunchTemplateData": {
                    "KernelId": kernel_id,
                    "EbsOptimized": ebs_optimized,
                    "IamInstanceProfile": iam_instance_profile,
                    "BlockDeviceMappings": block_device_mappings,
                    "NetworkInterfaces": network_interfaces,
                    "ImageId": res.get("image"),
                    "InstanceType": instance_type,
                    "KeyName": key_name,
                    "Monitoring": {"Enabled": monitoring_enabled},
                    "Placement": placement,
                    "RamDiskId": ram_disk_id,
                    "DisableApiTermination": disable_api_termination,
                    "InstanceInitiatedShutdownBehavior": instance_initiated_shutdown_behavior,
                    "UserData": user_data,
                    "TagSpecifications": tag_specifications,
                    "ElasticGpuSpecifications": [{"Type": elastic_gpu_type}],
                    "ElasticInferenceAccelerators": elastic_inference_accelerators,
                    "SecurityGroupIds": res.get("security_group"),
                    "InstanceMarketOptions": instance_market_options,
                    "CreditSpecification": {"CpuCredits": credit_specification},
                    "CpuOptions": cpu_options,
                    "CapacityReservationSpecification": capacity_reservation_specification,
                    "LicenseSpecifications": [
                        {"LicenseConfigurationArn": item}
                        for item in license_specifications
                    ],
                    "HibernationOptions": {"Configured": hibernation_configured},
                    "MetadataOptions": metadata_options,
                },
            }
        )
    params.update(
        {"ClientToken": hashlib.sha1(json.dumps(params).encode("utf8")).hexdigest()}
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.create_resource"](
        "launch_template",
        params=params,
        tags=tags,
        client=client,
    )


def create_nat_gateway(
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    allocation_id: str = None,
    address_lookup: Mapping = None,
    tags: Mapping = None,
    blocking: bool = False,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a NAT gateway in the specified public subnet. This action creates a
    network interface in the specified subnet with a private IP address from the
    IP address range of the subnet. Internet-bound traffic from a private subnet
    can be routed to the NAT gateway, therefore enabling instances in the private
    subnet to connect to the internet.

    :param str subnet_id: The subnet in which to create the NAT gateway.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
    :param str allocation_id: The allocation ID of an Elastic IP address to
      associate with the NAT gateway. If the Elastic IP address is associated
      with another resource, you must first disassociate it.
    :param str address_lookup: Any kwargs that :py:func:`lookup_address` accepts.
      Used to lookup ``allocation_id``. You can, for example provide
      ``{'public_ip': '1.2.3.4'}`` to specify the Elastic IP to use for the NAT gateway.
      Either ``allocation_id`` or ``address_lookup`` must be specified.
      If this is not done, a new Elastic IP address will be created.
    :param dict tags: Tags to assign to the NAT gateway after creation.
    :param bool blocking: Wait for the NAT gateway to become available.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_nat_gateway``-call
      on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_subnets, boto3.client('ec2').describe_addresses, boto3.client('ec2').allocate_address, boto3.client('ec2').create_nat_gateway, boto3.client('ec2').get_waiter('nat_gateway_available')
    """
    if not any((allocation_id, address_lookup)):
        # Create new Elastic IP
        res = allocate_address(region=region, keyid=keyid, key=key, profile=profile)
        if "error" in res:
            return res
        allocation_id = res["result"]["AllocationId"]
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
        },
        {
            "service": "ec2",
            "name": "address",
            "kwargs": address_lookup or {"allocation_id": allocation_id},
            "result_keys": "AllocationId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {
                "params": {"SubnetId": res["subnet"], "AllocationId": res["address"]},
                "tags": tags,
                "wait_until_state": "available" if blocking else None,
            },
            recurse_depth=1,
        )
        params["params"].update(
            {
                "ClientToken": hashlib.sha1(
                    json.dumps(params).encode("utf8")
                ).hexdigest(),
            }
        )
        params.update({"client": client})
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "nat_gateway"
    )


def create_network_acl(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    tags: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a network ACL in a VPC. Network ACLs provide an optional layer of security
    (in addition to security groups) for the instances in your VPC.

    :param str vpc_id: The ID of the VPC to create the network ACL in.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param dict tags: Tags to assign to the network ACL after creation.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_network_acl``-
      call on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').create_network_acl
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {"params": {"VpcId": res["result"]["vpc"]}, "tags": tags, "client": client}
        )
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "network_acl"
    )


def create_network_acl_entry(
    protocol: str,
    egress: bool,
    rule_number: int,
    rule_action: str,
    network_acl_id: str = None,
    network_acl_lookup: Mapping = None,
    cidr_block: str = None,
    icmp_code: int = None,
    icmp_type: int = None,
    ipv6_cidr_block: str = None,
    port_range: Tuple[int, int] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates an entry (a rule) in a network ACL with the specified rule number.
    Each network ACL has a set of numbered ingress rules and a separate set of
    numbered egress rules. When determining whether a packet should be allowed
    in or out of a subnet associated with the ACL, we process the entries in the
    ACL according to the rule numbers, in ascending order. Each network ACL has
    a set of ingress rules and a separate set of egress rules.

    We recommend that you leave room between the rule numbers (for example, 100,
    110, 120, ...), and not number them one right after the other (for example,
    101, 102, 103, ...). This makes it easier to add a rule between existing ones
    without having to renumber the rules.

    After you add an entry, you can't modify it; you must either replace it, or
    create an entry and delete the old one.

    :param str protocol: The protocol number. A value of "-1" means all protocols.
      If you specify "-1" or a protocol number other than "6" (TCP), "17" (UDP),
      or "1" (ICMP), traffic on all ports is allowed, regardless of any ports
      or ICMP types or codes that you specify. If you specify protocol "58" (ICMPv6)
      and specify an IPv4 CIDR block, traffic for all ICMP types and codes allowed,
      regardless of any that you specify. If you specify protocol "58" (ICMPv6)
      and specify an IPv6 CIDR block, you must specify an ICMP type and code.
    :param bool egress: Indicates whether this is an egress rule (rule is applied
      to traffic leaving the subnet).
    :param int rule_number: The rule number for the entry (for example, 100).
      ACL entries are processed in ascending order by rule number.
      Constraints: Positive integer from 1 to 32766. The range 32767 to 65535
      is reserved for internal use.
    :param str rule_action: Indicates whether to allow or deny the traffic that
      matches the rule. Allowed values: allow, deny.
    :param str network_acl_id: The ID of the network ACL.
    :param str network_acl_lookup: Any kwargs that :py:func:`lookup_network_acl`
      accepts. Used to lookup ``network_acl_id``.
    :param str cidr_block:  The IPv4 network range to allow or deny, in CIDR notation
      (for example ``172.16.0.0/24``). We modify the specified CIDR block to its
      canonical form; for example, if you specify ``100.68.0.18/18``, we modify
      it to ``100.68.0.0/18``.
    :param int icmp_code: The ICMP code. A value of -1 means all codes for the
      specified ICMP type.
    :param int icmp_type: The ICMP type. A value of -1 means all types.
    :param str ipv6_cidr_block: The IPv6 network range to allow or deny, in CIDR
      notation (for example ``2001:db8:1234:1a00::/64``).
    :param tuple(int, int) port_range: The first and last port in the range.
      TCP or UDP protocols: The range of ports the rule applies to.
      Required if specifying protocol 6 (TCP) or 17 (UDP).

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success

    :depends: boto3.client('ec2').create_network_acl_entry, boto3.client('ec2').describe_network_acls, boto3.client('ec2').describe_vpcs
    """
    if port_range is not None:
        if not isinstance(portrange, (list, tuple)):
            raise SaltInvocationError(
                "port_range must be a list or tuple, not {}".format(type(port_range))
            )
        if len(port_range) != 2:
            raise SaltInvocationError(
                "port_range must contain exactly two items, not {}".format(
                    len(port_range)
                )
            )
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "network_acl",
            "kwargs": network_acl_lookup or {"network_acl_id": network_acl_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = salt.utils.data.filter_falsey(
            {
                "CidrBlock": cidr_block,
                "Egress": egress,
                "IcmpTypeCode": {"Code": icmp_code, "Type": icmp_type},
                "Ipv6CidrBlock": ipv6_cidr_block,
                "NetworkAclId": res["result"]["network_acl"],
                "PortRange": {"From": port_range[0], "To": port_range[1]}
                if port_range
                else None,
                "Protocol": protocol,
                "RuleAction": rule_action,
                "RuleNumber": rule_number,
            },
            recurse_depth=1,
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.create_network_acl_entry, params)


@_arguments_to_list("security_group_ids", "security_group_lookups")
def create_network_interface(
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    description: str = None,
    security_group_ids: Union[str, Iterable[str]] = None,
    security_group_lookups: Union[Mapping, Iterable[Mapping]] = None,
    ipv6_address_count: int = None,
    ipv6_addresses: Iterable[str] = None,
    primary_private_ip_address: str = None,
    secondary_private_ip_address_count: int = None,
    secondary_private_ip_addresses: Iterable[str] = None,
    interface_type: str = None,
    tags: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a network interface in the specified subnet.

    :param str subnet_id: The ID of the subnet.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
    :param str description: A description for the network interface.
    :param list(str) security_group_ids: The IDs of one or more security groups.
    :param list(dict) security_group_lookups: List of dicts that contain kwargs
      that :py:func:`lookup_security_group` accepts. Used to lookup security groups
      if ``security_group_ids`` is not provided.
    :param int ipv6_address_count: The number of IPv6 addresses to assign to a
      network interface. Amazon EC2 automatically selects the IPv6 addresses
      from the subnet range. You can't use this option if specifying specific
      IPv6 addresses. If your subnet has the AssignIpv6AddressOnCreation attribute
      set to ``True``, you can specify ``0`` to override this setting.
    :param list(str) ipv6_addresses: One or more specific IPv6 addresses from the
      IPv6 CIDR block range of your subnet. You can't use this option if you're
      specifying a number of IPv6 addresses.
    :param str primary_private_ip_address: The primary private IPv4 address of
      the network interface. If you don't specify an IPv4 address, Amazon EC2
      selects one for you from the subnet's IPv4 CIDR range.
    :param int secondary_private_ip_address_count: The number of secondary private
      IPv4 addresses to assign to a network interface. When you specify a number
      of secondary IPv4 addresses, Amazon EC2 selects these IP addresses within
      the subnet's IPv4 CIDR range. You can't specify this option and specify
      more than one private IP address using ``secondary_private_ip_addresses``.
      The number of IP addresses you can assign to a network interface varies
      by instance type.
    :param list(str): secondary_private_ip_addresses: One or more private IPv4
      addresses.
    :param str interface_type: Indicates the type of network interface. To create
      an Elastic Fabric Adapter (EFA), specify ``efa``.
    :param dict tags: Tags to apply to the new network interface.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_network_interface``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
        },
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": security_group_lookups
            or [{"group_id": group_id} for group_id in security_group_ids or []],
            "required": False,
            "result_keys": "GroupId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {
                "params": {
                    "Description": description,
                    "Groups": res.get("security_group"),
                    "Ipv6AddressCount": ipv6_address_count,
                    "Ipv6Addresses": [{"Ipv6Address": item} for item in ipv6_addresses],
                    "PrivateIpAddress": primary_private_ip_address,
                    "SecondaryPrivateIpAddressCount": secondary_private_ip_address_count,
                    "PrivateIpAddresses": [
                        {"PrivateIpAddress": item}
                        for item in secondary_private_ip_addresses
                    ],
                    "InterfaceType": interface_type,
                    "SubnetId": res["subnet"],
                },
                "tags": tags,
                "client": client,
            }
        )
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "network_interface"
    )


def create_route(
    route_table_id: str = None,
    route_table_lookup: Mapping = None,
    destination_cidr_block: str = None,
    destination_ipv6_cidr_block: str = None,
    destination_prefix_list_id: str = None,
    destination_prefix_list_lookup: Mapping = None,
    egress_only_internet_gateway_id: str = None,
    egress_only_internet_gateway_lookup: Mapping = None,
    internet_gateway_id: str = None,
    internet_gateway_lookup: Mapping = None,
    instance_id: str = None,
    instance_lookup: Mapping = None,
    nat_gateway_id: str = None,
    nat_gateway_lookup: Mapping = None,
    transit_gateway_id: str = None,
    transit_gateway_lookup: Mapping = None,
    local_gateway_id: str = None,
    local_gateway_lookup: Mapping = None,
    network_interface_id: str = None,
    network_interface_lookup: Mapping = None,
    vpc_peering_connection_id: str = None,
    vpc_peering_connection_lookup: Mapping = None,
    vpn_gateway_id: str = None,
    vpn_gateway_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a route in a route table within a VPC.

    You must specify one of the following targets: internet gateway or virtual
    private gateway, NAT instance, NAT gateway, VPC peering connection, network
    interface, or egress-only internet gateway.

    When determining how to route traffic, we use the route with the most specific
    match. For example, traffic is destined for the IPv4 address 192.0.2.3 , and
    the route table includes the following two IPv4 routes:

      192.0.2.0/24 (goes to some target A)
      192.0.2.0/28 (goes to some target B)

    Both routes apply to the traffic destined for 192.0.2.3 . However, the second
    route in the list covers a smaller number of IP addresses and is therefore
    more specific, so we use that route to determine where to target the traffic.

    :param str route_table_id: The ID of the route table for the route.
    :param dict route_table_lookup: Any kwargs that :py:func:`lookup_route_table`
      accepts. Used to lookup ``route_table_id``.
    :param str destination_cidr_block: The IPv4 CIDR address block used for the
      destination match. Routing decisions are based on the most specific match.
    :param str destination_ipv6_cidr_block: The IPv6 CIDR block used for the
      destination match. Routing decisions are based on the most specific match.
    :param str destination_prefix_list_id: The ID of a prefix list used for the
      destination match.
    :param dict destination_prefix_list_lookup: Any kwargs that :py:func:`lookup_managed_prefix_list`
      accepts. Used to lookup ``destination_prefix_list_id``.
    :param str egress_only_internet_gateway_id: [IPv6 traffic only] The ID of an
      egress-only internet gateway.
    :param dict egress_only_internet_gateway_lookup: Any kwargs that
      :py:func:`lookup_egress_only_internet_gateway` accepts. Used to lookup
      ``egress_only_internet_gateway_id``.
    :param str internet_gateway_id: The ID of an internet gateway attached to your VPC.
      You can either specify an internet gateway, or a VPN gateway, not both.
    :param dict internet_gateway_lookup: Any kwargs that :py:func:`lookup_internet_gateway`
      accepts. Used to lookup ``internet_gateway_id``.
    :param str instance_id: The ID of a NAT instance in your VPC. The operation
      fails if you specify an instance ID unless exactly one network interface
      is attached.
    :param dict instance_lookup: Any kwargs that :py:func:`lookup_instance` accepts.
      Used to lookup ``instance_id``.
    :param str nat_gateway_id: [IPv4 traffic only] The ID of a NAT gateway.
    :param dict nat_gateway_lookup: Any kwargs that :py:func:`lookup_nat_gateway`
      accepts. Used to lookup ``nat_gateway_id``.
    :param str transit_gateway_id: The ID of a transit gateway.
    :param dict transit_gateway_lookup: Any kwargs that :py:func:`lookup_transit_gateway`
      accepts. Used to lookup ``transit_gateway_id``.
    :param str local_gateway_id: The ID of the local gateway.
    :param dict local_gateway_lookup: Any kwargs that :py:func:`lookup_local_gateway`
      accepts. Used to lookup ``local_gateway_id``.
    :param str network_interface_id: The ID of a network interface.
    :param dict network_interface_lookup: Any kwargs that :py:func:`lookup_network_interface`
      accepts. Used to lookup ``network_interface_id``.
    :param str vpc_peering_connection_id: The ID of a VPC peering connection.
    :param dict vpc_peering_connection_lookup: Any kwargs that :py:func:`lookup_vpc_peering_connection`
      accepts. Used to lookup ``vpc_peering_connection_id``.
    :param str vpn_gateway_id: The ID of a virtual private gateway attached to your VPC.
      You can either specify an internet gateway, or a VPN gateway, not both.
    :param dict vpn_gateway_lookup: Any kwargs that :py:func:`lookup_vpn_gateway`
      accepts. Used to lookup ``vpn_gateway_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_route``-call on succes.

    :depends: boto3.client('ec2').create_route
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "route_table",
            "kwargs": route_table_lookup or {"route_table_id": route_table_id},
        },
        {
            "service": "ec2",
            "name": "egress_only_internet_gateway",
            "kwargs": egress_only_internet_gateway_lookup
            or {"egress_only_internet_gateway_id": egress_only_internet_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "internet_gateway",
            "kwargs": internet_gateway_lookup
            or {"internet_gateway_id": internet_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "managed_prefix_list",
            "kwargs": destination_prefix_list_lookup
            or {"prefix_list_id": destination_prefix_list_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookup or {"instance_id": instance_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "local_gateway",
            "kwargs": local_gateway_lookup or {"local_gateway_id": local_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "nat_gateway",
            "kwargs": nat_gateway_lookup or {"nat_gateway_id": nat_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "transit_gateway",
            "kwargs": transit_gateway_lookup
            or {"transit_gateway_id": transit_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "network_interface",
            "kwargs": network_interface_lookup
            or {"network_interface_id": network_interface_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpc_peering_connection",
            "kwargs": vpc_peering_connection_lookup
            or {"vpc_peering_connection_id": vpc_peering_connection_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpn_gateway",
            "kwargs": vpn_gateway_lookup or {"vpn_gateway_id": vpn_gateway_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        if res.get("internet_gateway") and res.get("vpn_gateway"):
            raise SaltInvocationError(
                "You can only specify one of internet_gateway or vpn_gateway, not both."
            )
        params = salt.utils.data.filter_falsey(
            {
                "RouteTableId": res["route_table"],
                "DestinationCidrBlock": destination_cidr_block,
                "DestinationIpv6CidrBlock": destination_ipv6_cidr_block,
                "DestinationPrefixListId": res.get("managed_prefix_list"),
                "EgressOnlyInternetGatewayId": res.get("egress_only_internet_gateway"),
                "GatewayId": res.get("internet_gateway", res.get("vpn_gateway")),
                "InstanceId": res.get("instance"),
                "LocalGatewayId": res.get("local_gateway"),
                "NatGatewayId": res.get("nat_gateway"),
                "TransitGatewayId": res.get("transit_gateway"),
                "NetworkInterfaceId": res.get("network_interface"),
                "VpcPeeringConnectionId": res.get("vpc_peering_connection"),
            }
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.create_route, params)


def create_route_table(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    tags: Dict = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a route table for the specified VPC. After you create a route table,
    you can add routes and associate the table with a subnet.

    :param str vpc_id: the ID of the VPC the route table is to be created in.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_route_table``-call
      on succes.
    :param dict tags: Tags to assign to the route_table after creation.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').create_route_table
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {"params": {"VpcId": res["result"]["vpc"]}, "tags": tags, "client": client}
        )
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "route_table"
    )


def create_security_group(
    name: str,
    description: str,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    tags: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a security group.

    A security group acts as a virtual firewall for your instance to control inbound
    and outbound traffic.

    When you create a security group, you specify a friendly name of your choice.
    You can have a security group for use in EC2-Classic with the same name as
    a security group for use in a VPC. However, you can't have two security groups
    for use in EC2-Classic with the same name or two security groups for use in
    a VPC with the same name.

    You have a default security group for use in EC2-Classic and a default security
    group for use in your VPC. If you don't specify a security group when you launch
    an instance, the instance is launched into the appropriate default security
    group. A default security group includes a default rule that grants instances
    unrestricted network access to each other.

    You can add or remove rules from your security groups using
    authorize_security_group_ingress, authorize_security_group_egress,
    revoke_security_group_ingress, and revoke_security_group_egress.

    :param str name: The name of the security group.
      Constraints: Up to 255 characters in length. Cannot start with ``sg-``.
      Constraints for EC2-Classic: ASCII characters
      Constraints for EC2-VPC: a-z, A-Z, 0-9, spaces, and ._-:/()#,@[]+=&;{}!$*
    :param str description: A description for the security group. This is informational only.
      Constraints: Up to 255 characters in length
      Constraints for EC2-Classic: ASCII characters
      Constraints for EC2-VPC: a-z, A-Z, 0-9, spaces, and ._-:/()#,@[]+=&;{}!$*
    :param str vpc_id: [EC2-VPC] The ID of the VPC. Required for EC2-VPC.
    :param str vpc_lookup: [EC2-VPC] Any kwargs that :py:func`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param dict tags: The tags to assign to the security group.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_security_group``-call
      on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {
                "params": {
                    "GroupName": name,
                    "Description": description,
                    "VpcId": res["result"]["vpc"],
                },
                "tags": tags,
                "client": client,
            }
        )
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "security_group"
    )


def create_snapshot(
    description: str = None,
    volume_id: str = None,
    volume_lookup: Mapping = None,
    tags: Mapping = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a snapshot of an EBS volume and stores it in Amazon S3. You can use
    snapshots for backups, to make copies of EBS volumes, and to save data before
    shutting down an instance.

    When a snapshot is created, any AWS Marketplace product codes that are associated
    with the source volume are propagated to the snapshot.

    You can take a snapshot of an attached volume that is in use. However, snapshots
    only capture data that has been written to your EBS volume at the time the
    snapshot command is issued; this may exclude any data that has been cached
    by any applications or the operating system. If you can pause any file systems
    on the volume long enough to take a snapshot, your snapshot should be complete.
    However, if you cannot pause all file writes to the volume, you should unmount
    the volume from within the instance, issue the snapshot command, and then remount
    the volume to ensure a consistent and complete snapshot. You may remount and
    use your volume while the snapshot status is ``pending``.

    To create a snapshot for EBS volumes that serve as root devices, you should
    stop the instance before taking the snapshot.

    Snapshots that are taken from encrypted volumes are automatically encrypted.
    Volumes that are created from encrypted snapshots are also automatically encrypted.
    Your encrypted volumes and any associated snapshots always remain protected.

    You can tag your snapshots during creation.

    :param str description: A description for the snapshot.
    :param str volume_id: The ID of the EBS volume.
    :param dict volume_lookup: Any kwargs that :py:func:`lookup_volume` accepts.
      Used to lookup the volume ID if ``volume_id`` is not provided.
    :param dict tags: Tags to apply to the snapshot during creation.
    :param bool blocking: Wait for the snapshot to be completed.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_snapshot``-call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "volume",
            "kwargs": volume_lookup or {"volume_id": volume_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {
                "params": {
                    "Description": description,
                    "VolumeId": res["result"]["volume"],
                },
                "tags": tags,
                "wait_until_state": "completed" if blocking else None,
                "client": client,
            }
        )
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "snapshot"
    )


def create_subnet(
    cidr_block: str,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    ipv6_cidr_block: str = None,
    ipv6_subnet: int = None,
    availability_zone: str = None,
    availability_zone_id: str = None,
    tags: Mapping = None,
    blocking: bool = False,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a subnet in an existing VPC.

    When you create each subnet, you provide the VPC ID and IPv4 CIDR block
    for the subnet. After you create a subnet, you can't change its CIDR block.
    The size of the subnet's IPv4 CIDR block can be the same as a VPC's IPv4
    CIDR block, or a subset of a VPC's IPv4 CIDR block. If you create more than
    one subnet in a VPC, the subnets' CIDR blocks must not overlap. The smallest
    IPv4 subnet (and VPC) you can create uses a /28 netmask (16 IPv4 addresses),
    and the largest uses a /16 netmask (65,536 IPv4 addresses).

    If you've associated an IPv6 CIDR block with your VPC, you can create a subnet
    with an IPv6 CIDR block that uses a /64 prefix length.

    Warning: AWS reserves both the first four and the last IPv4 address in each
    subnet's CIDR block. They're not available for use.

    If you add more than one subnet to a VPC, they're set up in a star topology
    with a logical router in the middle.

    If you launch an instance in a VPC using an Amazon EBS-backed AMI, the IP
    address doesn't change if you stop and restart the instance (unlike a similar
    instance launched outside a VPC, which gets a new IP address when restarted).
    It's therefore possible to have a subnet with no running instances (they're
    all stopped), but no remaining IP addresses available.

    :param str cidr_block: The IPv4 network range for the subnet, in CIDR notation.
      For example, 10.0.0.0/24.
    :param str vpc_id: The ID of the VPC to create the subnet in.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param str ipv6_cidr_block: The IPv6 CIDR block for your subnet. The subnet
      must have a /64 prefix length. Exclusive with ipv6_subnet.
    :param int ipv6_subnet: The IPv6 subnet. This uses an implicit /64 netmask.
      Use this if you don't know the parent subnet and want to extract that
      from the VPC information. Exclusive with ipv6_cidr_block.
    :param str availability_zone: The Availability Zone to create the subnet in.
    :param str availability_zone_id: The ID of the AZ to create the subnet in.
      Either availability_zone or availability_zone_id must be specified. If
      both are specified, availability_zone_id takes precedence.
    :param dict tags: Tags to assign to the subnet after creation.
      Only supported with botocore 1.17.14 or newer.
    :param bool blocking: Specify ``True`` to wait until the subnet is available.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_subnet``-call on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_vpcs, boto3.client('ec2').create_subnet, boto3.client('ec2').get_waiter("subnet_available")
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup or {"vpc_id": vpc_id},
            "result_keys": ["VpcId", "Ipv6CidrBlockAssociationSet"],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        if ipv6_cidr_block is None:
            ipv6_cidr_block_association_set = res["vpc"]["Ipv6CidrBlockAssociationSet"]
            if ipv6_cidr_block_association_set:
                ipv6_cidr_block = _derive_ipv6_cidr_subnet(
                    ipv6_subnet, ipv6_cidr_block_association_set[0]["Ipv6CidrBlock"]
                )
        params = salt.utils.data.filter_falsey(
            {
                "CidrBlock": cidr_block,
                "VpcId": res["vpc"]["VpcId"],
                "AvailabilityZone": availability_zone,
                "AvailabilityZoneId": availability_zone_id,
                "Ipv6CidrBlock": ipv6_cidr_block,
            }
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.create_resource"](
        "subnet",
        params=params,
        tags=tags,
        wait_until_state="available" if blocking else None,
        client=client,
    )


def create_tags(
    resource_ids: Union[str, Iterable[str]],
    tags: Mapping,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Adds or overwrites one or more tags for the specified Amazon EC2 resource or
    resources. Each resource can have a maximum of 50 tags. Each tag consists of
    a key and optional value. Tag keys must be unique per resource.

    :type resource_ids: str or list(str)
    :param resource_ids: A (list of) ID(s) to create tags for.
    :param dict tags: Tags to create on the resource(s).

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').create_tags
    """
    params = {
        "Resources": resource_ids if isinstance(resource_ids, list) else [resource_ids],
        "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
    }
    # Oh, the irony
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.create_resource"](
        "tags",
        params=params,
        client=client,
    )


def create_volume(
    availability_zone: str,
    encrypted: bool = None,
    iops: int = None,
    kms_key_id: str = None,
    outpost_arn: str = None,
    size: int = None,
    snapshot_id: str = None,
    snapshot_lookup: Mapping = None,
    volume_type: str = None,
    tags: Mapping = None,
    multi_attach_enabled: bool = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates an EBS volume that can be attached to an instance in the same Availability
    Zone. The volume is created in the regional endpoint that you send the HTTP request to.
    You can create a new empty volume or restore a volume from an EBS snapshot.
    Any AWS Marketplace product codes from the snapshot are propagated to the volume.
    You can create encrypted volumes. Encrypted volumes must be attached to instances
    that support Amazon EBS encryption. Volumes that are created from encrypted
    snapshots are also automatically encrypted.
    You can tag your volumes during creation.

    :param str availability_zone: The Availability Zone in which to create the volume.
    :param bool encrypted: Specifies whether the volume should be encrypted. The
      effect of setting the encryption state to true depends on the volume origin
      (new or from a snapshot), starting encryption state, ownership, and whether
      encryption by default is enabled. Encrypted Amazon EBS volumes must be
      attached to instances that support Amazon EBS encryption.
    :param int iops: The number of I/O operations per second (IOPS) to provision
      for the volume, with a maximum ratio of 50 IOPS/GiB. Range is 100 to 64,000
      IOPS for volumes in most Regions. Maximum IOPS of 64,000 is guaranteed
      only on Nitro-based instances. Other instance families guarantee performance
      up to 32,000 IOPS.
    :param str kms_key_id: The identifier of the AWS Key Management Service (AWS KMS)
      customer master key (CMK) to use for Amazon EBS encryption. If this parameter
      is not specified, your AWS managed CMK for EBS is used. If KmsKeyId is
      specified, the encrypted state must be ``True``.
      You can specify the CMK using any of the following:
      - Key ID. For example, key/1234abcd-12ab-34cd-56ef-1234567890ab.
      - Key alias. For example, alias/ExampleAlias.
      - Key ARN. For example, arn:aws:kms:us-east-1:012345678910:key/abcd1234-a123-456a-a12b-a123b4cd56ef.
      - Alias ARN. For example, arn:aws:kms:us-east-1:012345678910:alias/ExampleAlias.
      AWS authenticates the CMK asynchronously. Therefore, if you specify an ID,
      alias, or ARN that is not valid, the action can appear to complete, but
      eventually fails.
    :param str outpost_arn: The Amazon Resource Name (ARN) of the Outpost.
    :param int size: The size of the volume, in GiBs. You must specify either a
      snapshot ID or a volume size.
      Constraints: 1-16,384 for gp2, 4-16,384 for io1, 500-16,384 for st1, 500-16,384
      for sc1, and 1-1,024 for standard. If you specify a snapshot, the volume
      size must be equal to or larger than the snapshot size.
      Default: If you're creating the volume from a snapshot and don't specify
      a volume size, the default is the snapshot size.
    :param str snapshot_id: The snapshot from which to create the volume. You must
      specify either a snapshot ID or a volume size.
    :param dict snapshot_lookup: Any kwargs that :py:func:`lookup_snapshot` accepts.
      Used to lookup ``snapshot_id``.
    :param str volume_type: The volume type. This can be ``gp2`` for General Purpose
      SSD, ``io1`` for Provisioned IOPS SSD, ``st1`` for Throughput Optimized
      HDD, ``sc1`` for Cold HDD, or ``standard`` for Magnetic volumes.
      Default: ``gp2``.
    :param dict tags: Tags to apply to the volume during creation.
    :param bool multi_attach_enabled:  Specifies whether to enable Amazon EBS Multi-
      Attach. If you enable Multi-Attach, you can attach the volume to up to
      16 Nitro-based instances in the same Availability Zone.
    :param bool blocking: Wait until the volume has become available.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_volume``-call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "snapshot",
            "kwargs": snapshot_lookup or {"snapshot_id": snapshot_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = salt.utils.data.filter_falsey(
            {
                "AvailabilityZone": availability_zone,
                "Encrypted": encrypted,
                "Iops": iops,
                "KmsKeyId": kms_key_id,
                "OutpostArn": outpost_arn,
                "Size": size,
                "SnapshotId": res["result"].get("snapshot"),
                "VolumeType": volume_type,
                "MultiAttachEnabled": multi_attach_enabled,
            }
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.create_resource"](
        "volume",
        params,
        tags=tags,
        wait_until_state="available" if blocking else None,
        client=client,
    )


def create_vpc(
    cidr_block: str,
    amazon_provided_ipv6_cidr_block: bool = None,
    instance_tenancy: str = None,
    ipv6_pool: str = None,
    ipv6_cidr_block: str = None,
    tags: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a VPC with the specified IPv4 CIDR block. The smallest VPC you can
    create uses a /28 netmask (16 IPv4 addresses), and the largest uses a /16
    netmask (65,536 IPv4 addresses).

    You can optionally request an IPv6 CIDR block for the VPC. You can request an
    Amazon-provided IPv6 CIDR block from Amazon's pool of IPv6 addresses, or an
    IPv6 CIDR block from an IPv6 address pool that you provisioned through bring
    your own IP addresses (BYOIP).

    By default, each instance you launch in the VPC has the default DHCP options,
    which include only a default DNS server that we provide (AmazonProvidedDNS).

    You can specify the instance tenancy value for the VPC when you create it.
    You can only modify the instance tenancy to ``default`` later on. Modifying
    the instance tenancy to ``dedicated`` is not possible.

    :param str cidr_block: The primary CIDR block to create the VPC with.
    :param bool amazon_provided_ipv6_cidr_block: Requests an Amazon-provided IPv6
      CIDR block with a /56 prefix length for the VPC. You cannot specify the
      range of IP addresses, or the size of the CIDR block.
    :param str ipv6_pool: The ID of an IPv6 address pool from which to allocate
      the IPv6 CIDR block.
    :param str ipv6_cidr_block: The IPv6 CIDR block from the IPv6 address pool.
      You must also specify Ipv6Pool in the request.
      To let Amazon choose the IPv6 CIDR block for you, omit this parameter.
    :param str instance_tenancy: The tenancy options for instances launched into
      the VPC. For ``default``, instances are launched with shared tenancy by
      default. You can launch instances with any tenancy into a shared tenancy
      VPC. For ``dedicated``, instances are launched as dedicated tenancy instances
      by default. You can only launch instances with a tenancy of ``dedicated``
      or ``host`` into a dedicated tenancy VPC.
    :param dict tags: Tags to apply to the VPC after creation.
      Only supported with botocore 1.17.14 or newer.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_vpc``-call on succes.

    :depends: boto3.client('ec2').create_vpc
    """
    if ipv6_cidr_block and not ipv6_pool:
        raise SaltInvocationError(
            "You must specify ipv6_pool when using ipv6_cidr_block"
        )
    params = salt.utils.data.filter_falsey(
        {
            "CidrBlock": cidr_block,
            "AmazonProvidedIpv6CidrBlock": amazon_provided_ipv6_cidr_block,
            "Ipv6Pool": ipv6_pool,
            "Ipv6CidrBlock": ipv6_cidr_block,
            "InstanceTenancy": instance_tenancy,
        }
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.create_resource"](
        "vpc",
        params=params,
        tags=tags,
        client=client,
    )


@_arguments_to_list(
    "route_table_ids",
    "route_table_lookups",
    "security_group_ids",
    "security_group_lookups",
    "subnet_ids",
    "subnet_lookups",
)
def create_vpc_endpoint(
    service_name: str,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    vpc_endpoint_type: str = None,
    policy_document: str = None,
    route_table_ids: Union[str, Iterable[str]] = None,
    route_table_lookups: Union[Mapping, Iterable[Mapping]] = None,
    subnet_ids: Union[str, Iterable[str]] = None,
    subnet_lookups: Union[Mapping, Iterable[Mapping]] = None,
    security_group_ids: Union[str, Iterable[str]] = None,
    security_group_lookups: Union[Mapping, Iterable[Mapping]] = None,
    private_dns_enabled: bool = None,
    tags: Mapping = None,
    blocking: bool = False,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a VPC endpoint for a specified service. An endpoint enables you to
    create a private connection between your VPC and the service. The service may
    be provided by AWS, an AWS Marketplace Partner, or another AWS account.

    A gateway endpoint serves as a target for a route in your route table for traffic
    destined for the AWS service. You can specify an endpoint policy to attach to
    the endpoint, which will control access to the service from your VPC. You can
    also specify the VPC route tables that use the endpoint.

    An interface endpoint is a network interface in your subnet that serves as an
    endpoint for communicating with the specified service. You can specify the
    subnets in which to create an endpoint, and the security groups to associate
    with the endpoint network interface.

    Use describe_vpc_endpoint_services to get a list of supported services.

    :param str service_name: The service name. To get a list of available services,
      use the describe_vpc_endpoint_services function, or get the name from the
      service provider.
    :param str vpc_id: The ID of the VPC in which the endpoint will be used.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param str vpc_endpoint_type: The type of endpoint. Allowed values:
      Interface, Gateway. Default: Gateway
    :param str policy_document: A policy to attach to the endpoint that controls
      access to the service. The policy must be in valid JSON format. If this parameter
      is not specified, we attach a default policy that allows full access to the service.
    :type route_table_ids: str or list(str)
    :param route_table_ids: [Gateway endpoint] One or more route table IDs.
    :type route_table_lookups: dict or list(dict)
    :param route_table_lookups: [Gateway endpoint] List of dicts that
      contain kwargs that :py:func:`lookup_route_table` accepts. Used to lookup
      ``route_table_ids``.
    :type subnet_ids: str or list(str)
    :param subnet_ids: [Interface endpoint] One or more subnets in which
      to create an endpoint network interface.
    :type subnet_lookups: dict or list(dict)
    :param subnet_lookups: [Interface endpoint] List of dicts that
      contain kwargs that :py:func:`lookup_subnet` accepts. Used to lookup ``subnet_ids``.
    :type security_group_ids: str or list(str)
    :param security_group_ids: [Interface endpoint] The ID of one or
      more security groups to associate with the endpoint network interface.
    :type security_group_lookups: dict or list(dict)
    :param security_group_lookups: [interface endpoint] List of dicts
      that contain kwargs that :py:func:`lookup_security_group` accepts. Used to lookup
      ``security_group_ids``.
    :param bool private_dns_enabled: [Interface endpoint] Indicates whether to
      associate a private hosted zone with the specified VPC. The private hosted
      zone contains a record set for the default public DNS name for the service
      for the Region (for example, ``kinesis.us-east-1.amazonaws.com``), which
      resolves to the private IP addresses of the endpoint network interfaces
      in the VPC. This enables you to make requests to the default public DNS
      name for the service instead of the public DNS names that are automatically
      generated by the VPC endpoint service.
      To use a private hosted zone, you must set the following VPC attributes
      to ``True`` : ``enableDnsHostnames`` and ``enableDnsSupport``.
      Use modify_vpc_attributes to set the VPC attributes.
    :param dict tags: Tags to associate with the endpoint after creation.
    :param bool blocking: Wait for the VPC endpoint to be in the ``available`` state.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_vpc_endpoint``-call
      on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        {
            "service": "ec2",
            "name": "route_table",
            "kwargs": route_table_lookups
            or [
                {"route_table_id": route_table_id} for route_table_id in route_table_ids
            ],
            "required": False,
        },
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookups
            or [{"subnet_id": subnet_id} for subnet_id in subnet_ids],
            "required": False,
        },
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": security_group_lookups
            or [{"group_id": group_id} for group_id in security_group_ids or []],
            "required": False,
            "result_keys": "GroupId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {
                "params": {
                    "ServiceName": service_name,
                    "PolicyDocument": policy_document,
                    "VpcId": res["vpc"],
                    "VpcEndpointType": vpc_endpoint_type,
                    "RouteTableIds": res.get("route_table"),
                    "SubnetIds": res.get("subnet"),
                    "SecurityGroupIds": res.get("security_group"),
                    "PrivateDnsEnabled": private_dns_enabled,
                },
                "tags": tags,
                "wait_until_state": "available" if blocking else None,
            }
        )
    params["params"].update(
        {"ClientToken": hashlib.sha1(json.dumps(params).encode("utf8")).hexdigest()}
    )
    param.update({"client": client})
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "vpc_endpoint"
    )


@_arguments_to_list("network_load_balancer_arns", "network_load_balancer_lookups")
def create_vpc_endpoint_service_configuration(
    network_load_balancer_arns: Union[str, Iterable[str]] = None,
    network_load_balancer_lookups: Union[Mapping, Iterable[Mapping]] = None,
    acceptance_required: bool = None,
    private_dns_name: str = None,
    tags: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a VPC endpoint service configuration to which service consumers (AWS
    accounts, IAM users, and IAM roles) can connect. Service consumers can create
    an interface VPC endpoint to connect to your service.
    To create an endpoint service configuration, you must first create a Network
    Load Balancer for your service.
    If you set the private DNS name, you must prove that you own the private DNS
    domain name.

    :type network_load_balancer_arns: str or list(str)
    :param network_load_balancer_arns: The Amazon Resource Names
      (ARNs) of one or more Network Load Balancers for your service.
    :type network_load_balancer_lookups: dict or list(dict)
    :param network_load_balancer_lookups: Dict or list of dict that contains kwargs
      that ``describe_network_load_balancer`` accepts. Used to lookup network
      loadbalancers if ``network_load_balancer_arns`` is not provided.
      Only supported if ``boto3_elb.describe_load_balancers`` exists.
    :param bool acceptance_required: Indicates whether requests from service consumers
      to create an endpoint to your service must be accepted. To accept a request,
      use ``accept_vpc_endpoint_connections``.
    :param str private_dns_name: The private DNS name to assign to the VPC endpoint
      service.
    :param dict tags: Tags to assign to the VPC endpoint service after creation.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_vpc_endpoint_service_configuration``-
      call on succes.
    """
    if network_load_balancer_lookups:
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "elb",
                "name": "load_balancer",
                "kwargs": network_load_balancer_lookups,
                "result_keys": "LoadBalancerArn",
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            network_load_balancer_arns = [
                item["LoadBalancerArn"] for item in res["result"]
            ]
    params = salt.utils.data.filter_falsey(
        {
            "AcceptanceRequired": acceptance_required,
            "PrivateDnsName": private_dns_name,
            "NetworkLoadbalancerArns": network_load_balancer_arns,
        }
    )
    params.update(
        {"ClientToken": hashlib.sha1(json.dumps(params).encode("utf8")).hexdigest()}
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.create_resource"](
        "vpc_endpoint_service_configuration",
        params,
        tags=tags,
        client=client,
    )


def create_vpc_peering_connection(
    requester_vpc_id: str = None,
    requester_vpc_lookup: Mapping = None,
    peer_vpc_id: str = None,
    peer_vpc_lookup: Mapping = None,
    peer_owner_id: str = None,
    blocking: bool = False,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Requests a VPC peering connection between two VPCs: a requester VPC that you
    own and an accepter VPC with which to create the connection. The accepter VPC
    can belong to another AWS account and can be in a different Region to the requester
    VPC. The requester VPC and accepter VPC cannot have overlapping CIDR blocks.

    :param str requester_vpc_id: The ID of the requester VPC.
    :param dict requester_vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``requester_vpc_id``.
    :param str peer_vpc_id: The ID of the accepter VPC.
    :param dict peer_vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``peer_vpc_id``.
      If the peer VPC belongs to another account, you must provide the appropriate
      region, keyid and key (or profile containing all of those) in the
      ``peer_vpc_lookup``-dict.
    :param str peer_owner_id: The Account ID of the owner of the accepter VPC.
      Only supply this if it differs from the account ID of the requester.
    :param bool blocking: Wait for the VPC peering connection to be in the
      ``pending-acceptance``-state.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_vpc_peering_connection``-
      call on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').create_vpc_peering_connection, boto3.client('ec2').get_waiter("vpc_peering_connection_pending")
    """
    peer_region_supported = LooseVersion(boto3.__version__) > LooseVersion("1.4.6")
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "as": "requester_vpc",
            "kwargs": requester_vpc_lookup or {"vpc_id": requester_vpc_id},
        },
        {
            "service": "ec2",
            "name": "vpc",
            "as": "peer_vpc",
            "kwargs": peer_vpc_lookup or {"vpc_id": peer_vpc_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {
                "params": {
                    "VpcId": res["requester_vpc"],
                    "PeerVpcId": res["peer_vpc"],
                    "PeerOwnerId": peer_owner_id,
                    "PeerRegion": peer_vpc_lookup.get("region", region)
                    if peer_vpc_lookup and peer_region_supported
                    else None,
                },
                "wait_until_state": "pending" if blocking else None,
                "client": client,
            },
            recurse_depth=1,
        )
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "vpc_peering_connection"
    )


def create_vpn_connection(
    vpn_type: str,
    customer_gateway_id: str = None,
    customer_gateway_lookup: Mapping = None,
    vpn_gateway_id: str = None,
    vpn_gateway_lookup: Mapping = None,
    transit_gateway_id: str = None,
    transit_gateway_lookup: Mapping = None,
    enable_acceleration: bool = None,
    static_routes_only: bool = None,
    tunnel_inside_ip_version: str = None,
    tunnel_inside_cidr: str = None,
    tunnel_inside_ipv6_cidr: str = None,
    pre_shared_key: str = None,
    phase_1_lifetime_seconds: int = None,
    phase_2_lifetime_seconds: int = None,
    rekey_margin_time_seconds: int = None,
    rekey_fuzz_percentage: int = None,
    replay_window_size: int = None,
    dpd_timeout_seconds: int = None,
    phase_1_encryption_algorithms: Iterable[str] = None,
    phase_2_encryption_algorithms: Iterable[str] = None,
    phase_1_integrity_algorithms: Iterable[str] = None,
    phase_2_integrity_algorithms: Iterable[str] = None,
    phase_1_dh_group_numbers: Iterable[int] = None,
    phase_2_dh_group_numbers: Iterable[int] = None,
    ike_versions: Iterable[str] = None,
    tags: Mapping = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a VPN connection between an existing virtual private gateway or transit
    gateway and a customer gateway. The supported connection type is `ipsec.1`.

    The response includes information that you need to give to your network administrator
    to configure your customer gateway.

    Warning: We strongly recommend that you use HTTPS when calling this operation
    because the response contains sensitive cryptographic information for configuring
    your customer gateway device.

    If you decide to shut down your VPN connection for any reason and later create
    a new VPN connection, you must reconfigure your customer gateway with the new
    information returned from this call.

    This is an idempotent operation. If you perform the operation more than once,
    Amazon EC2 doesn't return an error.

    :param str vpn_type: The type of VPN connection. Allowed values: ``ipsec.1``.
    :param str customer_gateway_id: The ID of the customer gateway.
    :param dict customer_gateway_lookup: Any kwargs that :py:func:`lookup_customer_gateway`
      accepts. Used to lookup ``customer_gateway_id``.
    :param str vpn_gateway_id: The ID of the virtual private gateway. If you specify
      a virtual private gateway, you cannot specify a transit gateway.
    :param dict vpn_gateway_lookup: Any kwargs that :py:func:`lookup_vpn_gateway` accepts.
      Used to lookup ``vpn_gateway_id``.
    :param str transit_gateway_id: The ID of the transit gateway. If you specify
      a transit gateway, you cannot specify a virtual private gateway.
    :param dict transit_gateway_lookup: Any kwargs that :py:func:`lookup_transit_gateway`
      accepts. Used to lookup ``transit_gateway_id``.
    :param bool enable_acceleration: Indicate whether to enable acceleration for
      the VPN connection. Default: ``False``.
    :param bool static_routes_only: Indicate whether the VPN connection uses static
      routes only. If you are creating a VPN connection for a device that does
      not support BGP, you must specify ``True``.
      Use :py:func:`create_vpn_connection_route` to create a static route.
    :param str tunnel_inside_ip_version: Indicate whether the VPN tunnels process
      IPv4 or IPv6 traffic. Default: ``ipv4``.
    :param str tunnel_inside_cidr: The range of inside IPv4 addresses for the tunnel.
      Any specified CIDR blocks must be unique across all VPN connections that
      use the same virtual private gateway.
      Constraints: A size /30 CIDR block from the 169.254.0.0/16 range.
      The following CIDR blocks are reserved and cannot be used:
      - 169.254.0.0/30
      - 169.254.1.0/30
      - 169.254.2.0/30
      - 169.254.3.0/30
      - 169.254.4.0/30
      - 169.254.5.0/30
      - 169.254.169.252/30
    :param str tunnel_inside_ipv6_cidr: The range of inside IPv6 addresses for
      the tunnel. Any specified CIDR blocks must be unique across all VPN connections
      that use the same transit gateway.
      Constraints: A size /126 CIDR block from the local fd00::/8 range.
    :param str pre_shared_key: The pre-shared key (PSK) to establish initial authentication
      between the virtual private gateway and customer gateway.
      Constraints: Allowed characters are alphanumeric characters, periods (.),
      and underscores (_). Must be between 8 and 64 characters in length and
      cannot start with zero (0).
    :param int phase_1_lifetime_seconds: The lifetime for phase 1 of the IKE negotiation,
      in seconds. Constraints: A value between 900 and 28,800. Default: 28800
    :param int phase_2_lifetime_seconds: The lifetime for phase 2 of the IKE negotiation,
      in seconds. Constraints: A value between 900 and 3,600. The value must
      be less than the value for ``phase_1_lifetime_seconds``. Default: 3600
    :param int rekey_margin_time_seconds: The margin time, in seconds, before the
      phase 2 lifetime expires, during which the AWS side of the VPN connection
      performs an IKE rekey. The exact time of the rekey is randomly selected
      based on the value for ``rekey_fuzz_percentage``. Constraints: A value
      between 60 and half of ``phase_2_lifetime_seconds``. Default: 540
    :param int rekey_fuzz_percentage: The percentage of the rekey window (determined
      by ``rekey_margin_time_seconds``) during which the rekey time is randomly
      selected. Constraints: A value between 0 and 100. Default: 100
    :param int replay_window_size: The number of packets in an IKE replay window.
      Constraints: A value between 64 and 2048. Default: 1024
    :param int dpd_timeout_seconds: The number of seconds after which a DPD timeout
      occurs. Constraints: A value between 0 and 30. Default: 30
    :param list(str) phase_1_encryption_algorithms: One or more encryption algorithms
      that are permitted for the VPN tunnel for phase 1 IKE negotiations.
      Allowed values: AES128, AES256, AES128-GCM-16, AES256-GCM-16
    :param list(str) phase_2_encryption_algorithms: One or more encryption algorithms
      that are permitted for the VPN tunnel for phase 2 IKE negotiations.
      Allowed values: AES128, AES256, AES128-GCM-16, AES256-GCM-16
    :param list(str) phase_1_integrity_algorithms: One or more integrity algorithms
      that are permitted for the VPN tunnel for phase 1 IKE negotiations.
      Allowed values: SHA1, SHA2-256, SHA2-384, SHA2-512
    :param list(str) phase_2_integrity_algorithms: One or more integrity algorithms
      that are permitted for the VPN tunnel for phase 2 IKE negotiations.
      Allowed values: SHA1, SHA2-256, SHA2-384, SHA2-512
    :param list(int) phase_1_dh_group_numbers: One or more Diffie-Hellman group
      numbers that are permitted for the VPN tunnel for phase 1 IKE negotiations.
      Allowed values: 2, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24
    :param list(int) phase_2_dh_group_numbers: One or more Diffie-Hellman group
      numbers that are permitted for the VPN tunnel for phase 2 IKE negotiations.
      Allowed values: 2, 5, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24
    :param list(str) ike_versions: The IKE versions that are permitted for the
      VPN tunnel. Allowed values: ikev1, ikev2
    :param dict tags: The tags to apply to the VPN connection.
    :param bool blocking: Whether to wait until the VPN becomes available.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_vpn_connection``-call
      on succes.
    """
    if (vpn_gateway_id or vpn_gateway_lookup) and (
        transit_gateway_id or transit_gateway_lookup
    ):
        raise SaltInvocationError(
            "You can only specify a vpn gateway or a transit gateway, not both."
        )
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "customer_gateway",
            "kwargs": customer_gateway_lookup
            or {"customer_gateway_id": customer_gateway_id},
        },
        {
            "service": "ec2",
            "name": "vpn_gateway",
            "kwargs": vpn_gateway_lookup or {"vpn_gateway_id": vpn_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "transit_gateway",
            "kwargs": transit_gateway_lookup
            or {"transit_gateway_id": transit_gateway_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
        params = salt.utils.data.filter_falsey(
            {
                "params": {
                    "CustomerGateawyId": res["customer_gateway"],
                    "Type": vpn_type,
                    "VpnGatewayId": res.get("vpn_gateway"),
                    "TransitGatewayId": res.get("transit_gateway"),
                    "Options": {
                        "EnableAcceleration": enable_acceleration,
                        "StaticRoutesOnly": static_routes_only,
                        "TunnelInsideIpVersion": tunnel_inside_ip_version,
                        "TunnelOptions": [
                            {
                                "TunnelInsideCidr": tunnel_inside_cidr,
                                "TunnelInsideIpv6Cidr": tunnel_inside_ipv6_cidr,
                                "PreSharedKey": pre_shared_key,
                                "Phase1LifetimeSeconds": phase_1_lifetime_seconds,
                                "Phase2LifetimeSeconds": phase_2_lifetime_seconds,
                                "RekeyMarginTimeSeconds": rekey_margin_time_seconds,
                                "RekeyFuzzPercentage": rekey_fuzz_percentage,
                                "ReplayWindowSize": replay_window_size,
                                "DPDTimeoutSeconds": dpd_timeout_seconds,
                                "Phase1EncryptionAlgorithms": phase_1_encryption_algorithms,
                                "Phase2EncryptionAlgorithms": phase_2_encryption_algorithms,
                                "Phase1IntegrityAlgorithms": phase_1_integrity_algorithms,
                                "Phase2IntegrityAlgorithms": phase_2_integrity_algorithms,
                                "Phase1DHGroupNumbers": phase_1_dh_group_numbers,
                                "Phase2DHGroupNumbers": phase_2_dh_group_numbers,
                                "IKEVersions": ike_versions,
                            }
                        ],
                    },
                },
                "tags": tags,
                "wait_until_state": "available" if blocking else None,
                "client": client,
            },
            recurse_depth=4,
        )
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"], params, "vpn_connection"
    )


def create_vpn_gateway(
    vpn_type: str,
    availability_zone: str = None,
    tags: Mapping = None,
    amazon_side_asn: int = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a virtual private gateway. A virtual private gateway is the endpoint
    on the VPC side of your VPN connection. You can create a virtual private gateway
    before creating the VPC itself.

    :param str vpn_type: The type of VPN connection this virtual private gateway supports.
    :param str availability_zone: The Availability Zone for the virtual private gateway.
    :param dict tags: The tags to apply to the virtual private gateway.
    :param int amazon_side_asn: A private Autonomous System Number (ASN) for the
      Amazon side of a BGP session. If you're using a 16-bit ASN, it must be
      in the 64512 to 65534 range. If you're using a 32-bit ASN, it must be in
      the 4200000000 to 4294967294 range. Default: 64512
    :param bool blocking: Wait until the VPN gateway becomes available.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_vpn_gateway``-call
      on succes.
    """
    params = salt.utils.data.filter_falsey(
        {
            "AvailabilityZone": availability_zone,
            "Type": vpn_type,
            "AmazonSideAsn": amazon_side_asn,
        }
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.create_resource"](
        "vpn_gateway",
        params=params,
        tags=tags,
        wait_until_state="available" if blocking else None,
        client=client,
    )


def crud_security_group_rule(
    operation: str,
    group_id: str = None,
    group_lookup: Mapping = None,
    direction: str = None,
    description: str = None,
    port_range: Tuple[int, int] = None,
    ip_protocol: str = None,
    ip_range: str = None,
    prefix_list_id: str = None,
    prefix_list_lookup: Mapping = None,
    user_id_group_pair: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Helper function to add/remove/update a single ingress or egress rule to a
    security group. Note that "update" only updates a rule's description as all
    other items of the rule determine which rule to update.

    :param str operation: What to do with the security group rule. Allowed values:
      add, remove, update.
    :param str group_id: The ID of the security group to add the rule to.
    :param dict group_lookup: Any kwargs that :py:func:`lookup_security_group`
      accepts. Used to lookup ``group_id``.
    :param str direction: To specify whether this is an egress or ingress rule.
      Allowed values: egress, ingress.

    The following arguments are part of the security group rule to add:

    :param str description: The description of the rule target.
    :param tuple(int, int) port_range: The start and end of the port range for
      the TCP and UDP protocols, or an ICMP/ICMPv6 type number. A value of
      (-1, -1) indicates all ICMP/ICMPv6 types.
    :param str ip_protocol: The IP protocol name (tcp, udp, icmp, icmpv6).
      Use ``-1`` to specify all protocols.

    The following designate the rule target. You must provide exactly one:

    :param str ip_range: Either an IPv4 or IPv6 CIDR range or a security
      group name.
    :param str prefix_list_id: The ID of a prefix list.
    :param str prefix_list_lookup: Any kwargs that :py:func:`lookup_managed_prefix_list`
      accepts. Used to lookup ``prefix_list_id``.
    :param dict user_id_group_pair: A security group and AWS account ID pair.
      A full description of its contents is given in the documentation of
      ``authorize_security_group_egress``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``allocate_address``-call
      on succes.
    """
    if not salt.utils.data.exactly_one(
        [ip_range, prefix_list_id, prefix_list_lookup, user_id_group_pair]
    ):
        raise SaltInvocationError(
            "You must specify exactly one of iprange, prefix_list_id, prefix_list_lookup, "
            "user_id_group_pair."
        )
    if direction not in ["egress", "ingress"]:
        raise SaltInvocationError(
            'Direction must be either "egress" or "ingress", not "{}".'.format(
                direction
            )
        )
    if operation not in ["add", "remove", "update"]:
        raise SaltInvocationError(
            'Operation must be either "add", "remove", or "update", not "{}".'.format(
                operation
            )
        )
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "managed_prefix_list",
            "kwargs": prefix_list_lookup or {"prefix_list_id": prefix_list_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        prefix_list_id = res["result"]["managed_prefix_list"]
    if user_id_group_pair and description and "Description" not in user_id_group_pair:
        user_id_group_pair.update({"Description": description})
    rule = salt.utils.data.filter_falsey(
        {
            "FromPort": port_range[0],
            "ToPort": port_range[1],
            "IpProtocol": ip_protocol,
            "Ipv6Ranges": [
                {"CidrIpv6": ip_range, "Description": description}
                if salt.utils.network.is_ipv6_subnet(ip_range)
                else {}
            ],
            "IpRanges": [
                {"CidrIp": ip_range, "Description": description}
                if not salt.utils.network.is_ipv6_subnet(ip_range)
                else {}
            ],
            "PrefixListIds": [
                {"PrefixListId": prefix_list_id, "Description": description}
                if prefix_list_id
                else {}
            ],
            "UserIdGroupPairs": [user_id_group_pair],
        },
        recurse_depth=2,
    )
    target_function_name = {
        "add": "authorize_security_group_{}",
        "remove": "revoke_security_group_{}",
        "update": "update_security_group_rule_description_{}",
    }
    target_function = MODULE_FUNCTIONs[
        target_function_name.get(operation).format(direction)
    ]
    return target_function(
        group_id=group_id,
        group_lookup=group_lookup,
        ip_permissions=[rule],
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


def delete_customer_gateway(
    customer_gateway_id: str = None,
    customer_gateway_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified customer gateway. You must delete the VPN connection
    before you can delete the customer gateway.

    :param str customer_gateway_id: The ID of the customer gateway.
    :param str customer_gateway_lookup: Any kwargs that :py:func:`lookup_customer_gateway`
      accepts. Used to lookup ``customer_gateway_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "customer_gateway",
            "kwargs": customer_gateway_lookup
            or {"customer_gateway_id": customer_gateway_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"CustomerGatewayId": res["result"]["customer_gateway"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_customer_gateway, params)


def delete_dhcp_options(
    dhcp_options_id: str = None,
    dhcp_options_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified set of DHCP options. You must disassociate the set of
    DHCP options before you can delete it. You can disassociate the set of DHCP
    options by associating either a new set of options or the default set of
    options with the VPC.

    :param str dhcp_options_id: The ID of the DHCP option set to delete.
    :param str dhcp_options_lookup: Any kwargs that :py:func:`lookup_dhcp_options`
      accepts. Used to lookup ``dhcp_options_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_dhcp_options, boto3.client('ec2').delete_dhcp_options
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "dhcp_options",
            "kwargs": dhcp_options_lookup or {"dhcp_options_id": dhcp_options_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"DhcpOptionsId": res["result"]["dhcp_options"]}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_dhcp_options, params)


def delete_internet_gateway(
    internet_gateway_id: str = None,
    internet_gateway_lookup: Mapping = None,
    detach: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified internet gateway. You must detach the internet gateway
    from the VPC before you can delete it.

    :param str internet_gateway_id: The ID of the Internet Gateway.
    :param dict internet_gateway_lookup: Any kwargs that :py:func:`lookup_internet_gateway`
      accepts. Used to lookup ``internet_gateway_id``.
    :param bool detach: Detach an attached Internet Gateway automatically before deleting.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_internet_gateways, boto3.client('ec2').delete_internet_gateway
    """
    result_keys = ["InternetGatewayId"]
    if detach:
        result_keys.append("Attachments")
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "internet_gateway",
            "kwargs": internet_gateway_lookup
            or {"internet_gateway_id": internet_gateway_id},
            "result_keys": result_keys,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]["internet_gateway"]
        internet_gateway_id = res["InternetGatewayId"] if len(result_keys) > 1 else res
        attachments = res["Attachments"] if detach else []
    if detach and attachments:
        for attached_vpc_id in [item["VpcId"] for item in attachments]:
            res = detach_internet_gateway(
                internet_gateway_id=internet_gateway_id,
                vpc_id=attached_vpc_id,
                region=region,
                keyid=keyid,
                key=key,
                profile=profile,
            )
            if "error" in res:
                return res
    params = {"InternetGatewayId": internet_gateway_id}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_internet_gateway, params)


def delete_key_pair(
    key_name: str = None,
    key_pair_id: str = None,
    key_pair_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified key pair, by removing the public key from Amazon EC2.

    :param str key_name: The name of the key pair.
    :param str key_pair_id: The ID of the key pair.
    :param dict key_pair_lookup: Any kwargs that :py:func:`lookup_key_pair` accepts.
      Used to lookup ``key_pair_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "key_pair",
            "kwargs": key_pair_lookup
            or salt.utils.data.filter_falsey(
                {"ids": key_pair_id, "key_names": key_name}
            ),
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = salt.utils.data.filter_falsey(
            {"KeyPairId": res["key_pair"], "KeyName": key_name}
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_key_pair, params)


def delete_nat_gateway(
    nat_gateway_id: str = None,
    nat_gateway_lookup: Mapping = None,
    blocking: bool = False,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified NAT gateway. Deleting a NAT gateway disassociates its
    Elastic IP address, but does not release the address from your account.
    Deleting a NAT gateway does not delete any NAT gateway routes in your route tables.

    :param str nat_gateway_id: The ID of the NAT gateway to delete.
    :param dict nat_gateway_lookup: Any kwargs that :py:func:`lookup_nat_gateway` accepts.
      Used to lookup ``nat_gateway_id``.
    :param bool blocking: Whether to wait for the deletion to be complete.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_nat_gateways, boto3.client('ec2').delete_nat_gateway, boto3.client('ec2').get_waiter('nat_gateway_deleted')
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "nat_gateway",
            "kwargs": nat_gateway_lookup or {"nat_gateway_id": nat_gateway_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        nat_gateway_id = res["result"]["nat_gateway"]
        params = {"NatGatewayId": nat_gateway_id}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](client.delete_nat_gateway, params)
    if "error" in res:
        return res
    if blocking:
        ret = __utils__["boto3.wait_resource"](
            "nat_gateway",
            "deleted",
            resource_id=nat_gateway_id,
            client=client,
        )
    else:
        ret = {"result": True}
    return ret


def delete_network_acl(
    network_acl_id: str = None,
    network_acl_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified network ACL. You can't delete the ACL if it's associated
    with any subnets. You can't delete the default network ACL.

    :param str network_acl_id: The ID of the network ACL.
    :param str network_acl_lookup: Any kwargs that :py:func:`lookup_network_acl` accepts.
      Used to lookup ``network_acl_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success

    :depends: boto3.client('ec2').delete_network_acl, boto3.client('ec2').describe_network_acls, boto3.client('ec2').describe_vpcs
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "network_acl",
            "kwargs": network_acl_lookup or {"network_acl_id": network_acl_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"NetworkAclId": res["result"]["network_acl"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_network_acl, params)


def delete_network_acl_entry(
    rule_number: int,
    egress: bool,
    network_acl_id: str = None,
    network_acl_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified ingress or egress entry (rule) from the specified network ACL.

    :param int rule_number: The rule number of the entry to delete.
    :param bool egress: Indicates whether the rule is an egress rule.
    :param str network_acl_id: The ID of the network ACL.
    :param str network_acl_lookup: Any kwargs that :py:func:`lookup_network_acl` accepts.
      Used to lookup ``network_acl_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "network_acl",
            "kwargs": network_acl_lookup or {"network_acl_id": network_acl_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "Egress": egress,
            "NetworkAclId": res["result"]["network_acl"],
            "RuleNumber": rule_number,
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_network_acl_entry, params)


def delete_network_interface(
    network_interface_id: str = None,
    network_interface_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified network interface. You must detach the network interface
    before you can delete it.

    :param str network_interface_id: The ID of the network interface.
    :param dict network_interface_lookup: Any kwargs that :py:func:`lookup_network_interface`
      accepts. Used to lookup ``network_interface_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "network_interface",
            "kwargs": network_interface_lookup
            or {"network_interface_id": network_interface_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"NetworkInterfaceId": res["result"]["network_interface"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_network_interface, params)


def delete_route(
    route_table_id: str = None,
    route_table_lookup: Mapping = None,
    destination_cidr_block: str = None,
    destination_ipv6_cidr_block: str = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified route from the specified route table.

    :param str route_table_id: The ID of the route table.
    :param dict route_table_lookup: Any kwargs that :py:func:`lookup_route_table`
      accepts. Used to lookup ``route_table_id``.
    :param str destination_cidr_block: The IPv4 CIDR range for the route. The
      value you specify must match the CIDR for the route exactly.
    :param str destination_ipv6_cidr_block: The IPv6 CIDR range for the route.
      The value you specify must match the CIDR for the route exactly.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').delete_route
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "route_table",
            "kwargs": route_table_lookup or {"route_table_id": route_table_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = salt.utils.data.filter_falsey(
            {
                "RouteTableId": res["result"]["route_table"],
                "DestinationCidrBlock": destination_cidr_block,
                "DestinationIpv6CidrBlock": destination_ipv6_cidr_block,
            }
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_route, params)


def delete_route_table(
    route_table_id: str = None,
    route_table_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified route table. You must disassociate the route table from
    any subnets before you can delete it. You can't delete the main route table.

    :param str route_table_id: The ID of the route table to delete.
    :param dict route_table_lookup: Any kwargs that :py:func:`lookup_route_table`
      accepts. Used to lookup ``route_table_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').delete_route_table
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "route_table",
            "kwargs": route_table_lookup or {"route_table_id": route_table_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"RouteTableId": res["result"]["route_table"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_route_table, params)


def delete_security_group(
    group_id: str = None,
    group_name: str = None,
    group_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes a security group.

    If you attempt to delete a security group that is associated with an instance,
    or is referenced by another security group, the operation fails with InvalidGroup.InUse
    in EC2-Classic or DependencyViolation in EC2-VPC.

    :param str group_id: The ID of the security group.
    :param str group_name: [EC2-Classic, default VPC] The name of the security group.
      This only works when the security group is in the default VPC. If this is
      not the case, use ``group_lookup`` below.
    :param dict group_lookup: Any kwargs that :py:func:`lookup_security_group`
      accepts. Used to lookup ``group_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": group_lookup
            or salt.utils.data.filter_falsey(
                {"group_id": group_id, "group_name": group_name}
            ),
            "result_keys": "GroupId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"GroupId": res["result"]["security_group"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_security_group, params)


def delete_snapshot(
    snapshot_id: str = None,
    snapshot_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified snapshot.
    When you make periodic snapshots of a volume, the snapshots are incremental,
    and only the blocks on the device that have changed since your last snapshot
    are saved in the new snapshot. When you delete a snapshot, only the data not
    needed for any other snapshot is removed. So regardless of which prior snapshots
    have been deleted, all active snapshots will have access to all the information
    needed to restore the volume.

    You cannot delete a snapshot of the root device of an EBS volume used by a
    registered AMI. You must first de-register the AMI before you can delete the
    snapshot.

    :param str snapshot_id: The ID of the EBS snapshot.
    :param dict snapshot_lookup: Any kwargs that :py:func:`lookup_snapshot` accepts.
      Used to lookup ``snapshot_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "snapshot",
            "kwargs": snapshot_lookup or {"snapshot_id": snapshot_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"SnapshotId": res["result"]["snapshot"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_snapshot, params)


def delete_subnet(
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified subnet. You must terminate all running instances in
    the subnet before you can delete the subnet.

    :param str subnet_id: The ID of the subnet to delete.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_subnets, boto3.client('ec2').delete_subnet
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"SubnetId": res["result"]["subnet"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_subnet, params)


def delete_tags(
    resources: Union[str, Iterable[str]],
    tags: Mapping,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified set of tags from the specified set of resources.

    :type resources: str or list(str)
    :param resources: A (list of) ID(s) to delete tags from.
    :param dict tags: Tags to delete from the resource(s).

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').delete_tags
    """
    params = {
        "Resources": resources if isinstance(resources, list) else [resources],
        "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
    }
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_tags, params)


def delete_volume(
    volume_id: str = None,
    volume_lookup: Mapping = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified EBS volume. The volume must be in the available state
    (not attached to an instance).

    The volume can remain in the deleting state for several minutes.

    :param str volume_id: The ID of the volume.
    :param dict volume_lookup: Any kwargs that :py:func:`lookup_volume` accepts.
      Used to lookup ``volume_id``.
    :param bool blocking: Whether to wait for the volume to be deleted.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "volume",
            "kwargs": volume_lookup or {"volume_id": volume_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        volume_id = res["result"]["volume"]
        params = {"VolumeId": volume_id}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    ret = __utils__["boto3.handle_response"](client.delete_volume, params)
    if "error" in res:
        return res
    if blocking:
        ret = __utils__["boto3.wait_resource"](
            "volume",
            "deleted",
            resource_id=volume_id,
            client=client,
        )
    else:
        ret = {"result": True}
    return ret


def delete_vpc(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified VPC. You must detach or delete all gateways and resources
    that are associated with the VPC before you can delete it. For example, you
    must terminate all instances running in the VPC, delete all security groups
    associated with the VPC (except the default one), delete all route tables
    associated with the VPC (except the default one), and so on.

    :param str vpc_id: The ID of the VPC to delete.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      containint ``True`` on success.

    :depends boto3.client('ec2').delete_vpc
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"VpcId": res["result"]["vpc"]}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_vpc, params)


@_arguments_to_list("service_ids", "service_lookups")
def delete_vpc_endpoint_service_configurations(
    service_ids: Union[str, Iterable[str]] = None,
    service_lookups: Union[Mapping, Iterable[Mapping]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes one or more VPC endpoint service configurations in your account. Before
    you delete the endpoint service configuration, you must reject any ``Available``
    or ``PendingAcceptance`` interface endpoint connections that are attached to the
    service.

    :type service_ids: str or list(str)
    :param service_ids: The IDs of one or more services
    :type service_lookups: dict or list(dict)
    :param service_lookups: Any kwargs that :py:func:`lookup_vpc_endpoint_service`
      accepts. Used to lookup ``service_ids``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``accept_vpc_endpoint_connections``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc_endpoint_service",
            "kwargs": service_lookups
            or [{"service_id": item} for item in service_ids or []],
            "result_keys": "ServiceId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "ServiceIds": itertools.chain.from_iterable(
                res["result"]["vpc_endpoint_service"]
            )
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](
        client.delete_vpc_endpoint_services, params
    )


@_arguments_to_list("vpc_endpoint_ids", "vpc_endpoint_lookups")
def delete_vpc_endpoints(
    vpc_endpoint_ids: Union[str, Iterable[str]] = None,
    vpc_endpoint_lookups: Union[Mapping, Iterable[Mapping]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes one or more specified VPC endpoints. Deleting a gateway endpoint also
    deletes the endpoint routes in the route tables that were associated with the
    endpoint. Deleting an interface endpoint deletes the endpoint network interfaces.

    :type vpc_endpoint_ids: str or list(str)
    :param vpc_endpoint_ids: One or more VPC endpoint IDs.
    :type vpc_endpoint_lookups: dict or list(dict)
    :param vpc_endpoint_lookups: Any kwargs that :py:func:`lookup_vpc_endpoint`
      accepts. Used to lookup ``vpc_endpoint_ids``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``delete_vpc_endpoints``-call
      on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc_endpoint",
            "kwargs": vpc_endpoint_lookups
            or [{"vpc_endpoint_id": item} for item in vpc_endpoint_ids or []],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "VpcEndpointIds": itertools.chain.from_iterable(
                res["result"]["vpc_endpoint"]
            )
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_vpc_endpoints, params)


def delete_vpc_peering_connection(
    vpc_peering_connection_id: str = None,
    vpc_peering_connection_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes a VPC peering connection. Either the owner of the requester VPC or
    the owner of the accepter VPC can delete the VPC peering connection if it's
    in the ``active`` state. The owner of the requester VPC can delete a VPC peering
    connection in the ``pending-acceptance`` state. You cannot delete a VPC peering
    connection that's in the ``failed`` state.

    :param str vpc_peering_connection_id: The ID of the VPC peering connection
      to delete.
    :param dict vpc_peering_connection_lookup: Any kwargs that :py:func:`lookup_vpc_peering_connection`
      accepts. Used to lookup ``vpc_peering_connection_id``.
    :param bool blocking: Wait until the vpc_peering_connection is deleted.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``delete_vpc_peering_connection``-
      call on succes.

    :depends: boto3.client('ec2').describe_vpc_peering_connections, boto3.client('ec2').delete_vpc_peering_connection
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc_peering_connection",
            "kwargs": vpc_peering_connection_lookup
            or {"vpc_peering_connection_id": vpc_peering_connection_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"VpcPeeringConnectionId": res["result"]["vpc_peering_connection"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](
        client.delete_vpc_peering_connection, params
    )
    if "error" in res:
        return res
    if blocking:
        ret = __utils__["boto3.wait_resource"](
            "vpn_peering_connection", params, "deleted", client=client
        )
    else:
        ret = {"result": True}
    return ret


def delete_vpn_connection(
    vpn_connection_id: str = None,
    vpn_connection_lookup: Mapping = None,
    blocking=None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified VPN connection.

    If you're deleting the VPC and its associated components, we recommend that
    you detach the virtual private gateway from the VPC and delete the VPC before
    deleting the VPN connection. If you believe that the tunnel credentials for
    your VPN connection have been compromised, you can delete the VPN connection
    and create a new one that has new keys, without needing to delete the VPC or
    virtual private gateway. If you create a new VPN connection, you must reconfigure
    the customer gateway device using the new configuration information returned
    with the new VPN connection ID.

    For certificate-based authentication, delete all AWS Certificate Manager (ACM)
    private certificates used for the AWS-side tunnel endpoints for the VPN connection
    before deleting the VPN connection.

    :param str vpn_connection_id: The ID of the VPN connection.
    :param dict vpn_connection_lookup: Any kwargs that :py:func:`lookup_vpn_connection`
      accepts. Used to lookup ``vpc_connection_id``.
    :param bool blocking: Wait until the VPN connection is deleted.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpn_connection",
            "kwargs": vpn_connection_lookup or {"vpn_connection_id": vpn_connection_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"VpnConnectionId": res["result"]["vpn_connection"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](client.delete_vpn_connection, params)
    if "error" in res:
        return res
    if blocking:
        ret = __utils__["boto3.wait_resource"](
            "vpn_connection", params, "deleted", client=client
        )
    else:
        ret = {"result": True}
    return ret


def delete_vpn_gateway(
    vpn_gateway_id: str = None,
    vpn_gateway_lookup: Mapping = None,
    blocking=None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deletes the specified virtual private gateway. You must first detach the virtual
    private gateway from the VPC. Note that you don't need to delete the virtual
    private gateway if you plan to delete and recreate the VPN connection between
    your VPC and your network.

    :param str vpn_gateway_id: The ID of the virtual private gateway.
    :param dict vpn_gateway_lookup: Any kwargs that :py:func:`lookup_vpn_gateway`
      accepts. Used to lookup ``vpc_gateway_id``.
    :param bool blocking: Wait until the VPN gateway is deleted.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpn_gateway",
            "kwargs": vpn_gateway_lookup or {"vpn_gateway_id": vpn_gateway_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"VpnGatewayId": res["result"]["vpn_gateway"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](client.delete_vpn_gateway, params)
    if "error" in res:
        return res
    if blocking:
        ret = __utils__["boto3.wait_resource"](
            "vpn_gateway", params, "deleted", client=client
        )
    else:
        ret = {"result": True}
    return ret


def deregister_image(
    image_id: str = None,
    image_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Deregisters the specified AMI. After you deregister an AMI, it can't be used
    to launch new instances; however, it doesn't affect any instances that you've
    already launched from the AMI. You'll continue to incur usage costs for those
    instances until you terminate them.

    When you deregister an Amazon EBS-backed AMI, it doesn't affect the snapshot
    that was created for the root volume of the instance during the AMI creation
    process. When you deregister an instance store-backed AMI, it doesn't affect
    the files that you uploaded to Amazon S3 when you created the AMI.

    :param str image_id: The ID of the AMI.
    :param dict image_lookup: Any kwargs that :py:func:`lookup_image` accepts.
      Used to lookup ``image_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``deregister_image``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "image",
            "kwargs": image_lookup or {"image_id": image_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"ImageId": res["result"]["image"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.deregister_image, params)


@_arguments_to_list("attributes")
def describe_account_attributes(
    attributes: Union[str, Iterable[str]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes attributes of your AWS account. The following are the supported account
    attributes:

    ``supported-platforms``: Indicates whether your account can launch instances
    into EC2-Classic and EC2-VPC, or only into EC2-VPC.
    ``default-vpc``: The ID of the default VPC for your account, or ``none``.
    ``max-instances``: This attribute is no longer supported. The returned value
    does not reflect your actual vCPU limit for running On-Demand Instances.
    ``vpc-max-security-groups-per-interface``: The maximum number of security groups
    that you can assign to a network interface.
    ``max-elastic-ips``: The maximum number of Elastic IP addresses that you can
    allocate for use with EC2-Classic.
    ``vpc-max-elastic-ips``: The maximum number of Elastic IP addresses that you
    can allocate for use with EC2-VPC.

    :type attributes: str or list(str)
    :param attributes: One or more attributes to describe.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_account_attributes``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "account_attribute",
        AttributeNames=attributes,
        client=client,
    )


@_arguments_to_list("public_ips", "allocation_ids")
def describe_addresses(
    filters: Mapping = None,
    public_ips: Union[str, Iterable[str]] = None,
    allocation_ids: Union[str, Iterable[str]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more Elastic IP addresses.

    :param dict filters: The dict with filters to specify the EIP(s) to describe.
    :type public_ips: str or list(str)
    :param public_ips: The (list of) Public IPs to specify the EIP(s) to describe.
    :type allocation_ids: str or list(str)
    :param allocation_ids: The (list of) Allocation IDs to specify the EIP(s) to describe.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_addresses``-
      call on succes.

    :depends: boto3.client('ec2').describe_addresses
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "address",
        ids=allocation_ids,
        filters=filters,
        PublicIps=public_ips,
        client=client,
    )


def describe_availability_zones(
    zone_ids: Iterable[str] = None,
    zone_names: Iterable[str] = None,
    all_availability_zones: bool = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the Availability Zones and Local Zones that are available to you.
    If there is an event impacting an Availability Zone or Local Zone, you can
    use this request to view the state and any provided messages for that
    Availability Zone or Local Zone.

    :param list(str) zone_ids: The IDs of the Zones.
    :param list(str) zone_names: The names of the Zones.
    :param bool all_availability_zones: Include all Availability Zones and Local
      Zones regardless of your opt in status.
      If you do not use this parameter, the results include only the zones for
      the Regions where you have chosen the option to opt in.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_availability_zones>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_availability_zone``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "availability_zone",
        ids=zone_ids,
        filters=filters,
        ZoneNames=zone_names,
        AllAvailabilityZones=all_availability_zones,
        client=client,
    )


@_arguments_to_list("customer_gateway_ids")
def describe_customer_gateways(
    customer_gateway_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your VPN customer gateways.

    :type customer_gateway_ids: str or list(str)
    :param customer_gateway_ids: One or more customer gateway IDs.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_customer_gateways>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_customer_gateways``-call
      on succes.

    :depends: boto3.client('ec2').describe_customer_gateways
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "customer_gateway",
        ids=customer_gateway_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("dhcp_option_ids")
def describe_dhcp_options(
    dhcp_option_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your DHCP options sets.

    :type dhcp_option_ids: str or list(str)
    :param dhcp_option_ids: The (list of) DHCP option ID(s) to describe.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_dhcp_options>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_dhcp_options``-call
      on succes.

    :depends: boto3.client('ec2').describe_dhcp_options
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "dhcp_options",
        ids=dhcp_option_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("egress_only_internet_gateway_ids")
def describe_egress_only_internet_gateways(
    egress_only_internet_gateway_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your egress-only internet gateways.

    :type egress_only_internet_gateway_ids: str or list(str)
    :param egress_only_internet_gateway_ids: One or more egress-only
      internet gateway IDs.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_egress_only_internet_gateways>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_egress_only_internet_gateways``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "egress_only_internet_gateway",
        ids=egress_only_internet_gateway_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("elastic_gpu_ids")
def describe_elastic_gpus(
    elastic_gpu_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the Elastic Graphics accelerator associated with your instances.

    :type elastic_gpu_ids: str or list(str)
    :param elastic_gpu_ids: The Elastic Graphic accelerator IDs.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_elastic_gpus>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_elastic_gpus``-call
      on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "elastic_gpu",
        ids=elastic_gpu_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("fleet_ids")
def describe_fleets(
    fleet_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified EC2 Fleets or all of your EC2 Fleets.

    :type fleet_ids: str or list(str)
    :param fleet_ids: The ID of the EC2 Fleets.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_fleets>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_fleets``-call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "fleet",
        ids=fleet_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("attributes")
def describe_fpga_image_attribute(
    attributes: Union[str, Iterable[str]] = None,
    fpga_image_id: str = None,
    fpga_image_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified attribute of the specified Amazon FPGA Image (AFI).

    :type attributes: str or list(str)
    :param attributes: The AFI attribute. Allowed values:
        ``description``, ``name``, ``load_permission``, ``product_codes``.
    :param str fpga_image_id: The ID of the AFI.
    :param dict fpga_image_lookup: Any kwargs that :py:func:`lookup_fpga_image`
      accepts. Used to lookup ``fpga_image_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_fpga_image_attribute``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "fpga_image",
            "kwargs": fpga_image_lookup or {"fpga_image_id": fpga_image_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"FpgaImageId": res["result"]["fpga_image"]}
    ret = {}
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    for attribute in attributes:
        # Well this is nasty. When selecting the attribute for querying, it needs
        # to be lowerCamelCased, but the returned attribute is UpperCamelCased.
        params["Attribute"] = salt.utils.stringutils.snake_to_camel_case(attribute)
        try:
            res = client.describe_fpga_image_attribute(**params)
            ret[attribute] = res[
                salt.utils.stringutils.snake_to_camel_case(attribute, uppercamel=True)
            ]["Value"]
        except (ParamValidationError, ClientError) as exp:
            return {"error": __utils__["boto3.get_error"](exp)["message"]}
    return {"result": ret}


@_arguments_to_list("fpga_image_ids", "owners")
def describe_fpga_images(
    fpga_image_ids: Union[str, Iterable[str]] = None,
    owners: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the Amazon FPGA Images (AFIs) available to you. These include public
    AFIs, private AFIs that you own, and AFIs owned by other AWS accounts for which
    you have load permissions.

    :type fpga_image_ids: str or list(str)
    :param fpga_image_ids: The AFI IDs.
    :type owners: str or list(str)
    :param owners: Filters the AFI by owner. Specify an AWS account
      ID, ``self`` (owner is the sender of the request), or an AWS owner alias
      (valid values are ``amazon``,  ``aws-marketplace``).
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_fpga_images>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_fpga_images``-call
      on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "fpga_image",
        ids=fpga_image_ids,
        filters=filters,
        client=client,
        Owners=owners,
    )


@_arguments_to_list("host_ids")
def describe_hosts(
    host_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified Dedicated Hosts or all your Dedicated Hosts.

    The results describe only the Dedicated Hosts in the Region you're currently
    using. All listed instances consume capacity on your Dedicated Host. Dedicated
    Hosts that have recently been released are listed with the state ``released``.

    :type host_ids: str or list(str)
    :param host_ids: The IDs of the Dedicated Hosts. The IDs are
      used for targeted instance launches.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_hosts>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_hosts``-call
      on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "host",
        ids=host_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("association_ids")
def describe_iam_instance_profile_associations(
    association_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes your IAM instance profile associations.

    :type association_ids: str or list(str)
    :param association_ids: The IAM instance profile associations.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_iam_instance_profile_associations>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_iam_instance_profile_associations``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "iam_instance_profile_association",
        AssociationIds=association_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("attributes")
def describe_image_attribute(
    attributes: Union[str, Iterable[str]] = None,
    image_id: str = None,
    image_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified attribute(s) of the specified AMI.

    :type attributes: str or list(str)
    :param attributes: One or more AMI attributes to describe.
      Allowed values: ``description``, ``kernel``, ``ramdisk``, ``launch_permission``,
      ``product_codes``, ``block_device_mapping``, ``sriov_net_support``.
    :param str image_id: The ID of the AMI.
    :param dict image_lookup: Any kwargs that :py:func:`lookup_image` accepts.
      Used to lookup ``image_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the attributes and their values on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "image",
            "kwargs": image_lookup or {"image_id": image_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"ImageId": res["result"]["image"]}
    ret = {}
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    for attribute in attributes:
        # Well this is nasty. When selecting the attribute for querying, it needs
        # to be lowerCamelCased, but the returned attribute is UpperCamelCased.
        params["Attribute"] = salt.utils.stringutils.snake_to_camel_case(attribute)
        try:
            res = client.describe_image_attribute(**params)
            ret[attribute] = res[
                salt.utils.stringutils.snake_to_camel_case(attribute, uppercamel=True)
            ]["Value"]
        except (ParamValidationError, ClientError) as exp:
            return {"error": __utils__["boto3.get_error"](exp)["message"]}
    return {"result": ret}


@_arguments_to_list("image_ids", "executable_users", "owners")
def describe_images(
    image_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    executable_users: Union[str, Iterable[str]] = None,
    owners: Union[str, Iterable[str]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified images (AMIs, AKIs, and ARIs) available to you or all
    of the images available to you.

    The images available to you include public images, private images that you
    own, and private images owned by other AWS accounts for which you have explicit
    launch permissions.

    Recently deregistered images appear in the returned results for a short interval
    and then return empty results. After all instances that reference a deregistered
    AMI are terminated, specifying the ID of the image results in an error indicating
    that the AMI ID cannot be found.

    :type image_ids: str or list(str)
    :param image_ids: The image IDs.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_images>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.
    :type executable_users: str or list(str)
    :param executable_users: Scopes the images by users with explicit
      launch permissions. Specify an AWS account ID, ``self`` (the sender of the
      request), or ``all`` (public AMIs).
    :type owners: str or list(str)
    :param owners: Scopes the results to images with the specified owners.
      You can specify a combination of AWS account IDs, self , amazon , and aws-marketplace .
      If you omit this parameter, the results include all images for which you
      have launch permissions, regardless of ownership.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the result of the boto ``describe_images``-call
        on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    params = salt.utils.data.filter_falsey(
        {"ExecutableUsers": executable_users, "Owners": owners}
    )
    return __utils__["boto3.describe_resource"](
        "image", ids=image_ids, filters=filters, client=client, **params
    )


@_arguments_to_list("attributes")
def describe_instance_attribute(
    attributes: Union[str, Iterable[str]] = None,
    instance_id: str = None,
    instance_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more specified attributes of the specified instance.
    Valid attribute values are: ``instance_type``, ``kernel``, ``ramdisk``, ``user_data``,
    ``disable_api_termination``, ``instance_initiated_shutdown_behavior``, ``root_device_name``,
    ``block_device_mapping``, ``product_codes``, ``source_dest_check``, ``group_set``,
    ``ebs_optimized``, ``sriov_net_support``.

    :type attributes: str or list(str)
    :param attributes: One or more instance attributes to describe.
    :param str instance_id: The ID of the instance.
    :param dict instance_lookup: Any kwargs that :py:func:`lookup_instance` accepts.
      Used to lookup ``instance_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_instance_attribute``-call
      on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookup or {"instance_id": instance_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"InstanceId": res["result"]["instance"]}
    ret = {}
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    for attribute in attributes:
        # Well this is nasty. When selecting the attribute for querying, it needs
        # to be lowerCamelCased, but the returned attribute is UpperCamelCased.
        params["Attribute"] = salt.utils.stringutils.snake_to_camel_case(attribute)
        try:
            res = client.describe_instance_attribute(**params)
            ret[attribute] = res[
                salt.utils.stringutils.snake_to_camel_case(attribute, uppercamel=True)
            ]["Value"]
        except (ParamValidationError, ClientError) as exp:
            return {"error": __utils__["boto3.get_error"](exp)["message"]}
    return {"result": ret}


@_arguments_to_list("instance_ids")
def describe_instance_credit_specifications(
    instance_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the credit option for CPU usage of the specified burstable performance
    instances. The credit options are ``standard`` and ``unlimited``.

    If you do not specify an instance ID, Amazon EC2 returns burstable performance
    instances with the unlimited credit option, as well as instances that were
    previously configured as T2, T3, and T3a with the unlimited credit option.
    For example, if you resize a T2 instance, while it is configured as ``unlimited``,
    to an M4 instance, Amazon EC2 returns the M4 instance.

    If you specify one or more instance IDs, Amazon EC2 returns the credit option
    (``standard`` or ``unlimited``) of those instances. If you specify an instance
    ID that is not valid, such as an instance that is not a burstable performance
    instance, an error is returned.

    Recently terminated instances might appear in the returned results. This interval
    is usually less than one hour.

    If an Availability Zone is experiencing a service disruption and you specify
    instance IDs in the affected zone, or do not specify any instance IDs at all,
    the call fails. If you specify only instance IDs in an unaffected zone, the
    call works normally.

    :type instance_ids: str or list(str)
    :param instance_ids: The (list of) IDs of the instance(s).
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_instance_credit_specifications>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_instance_credit_specifications``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "instance_credit_specification",
        ids=instance_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("instance_ids", "instance_lookups")
def describe_instance_status(
    instance_ids: Union[str, Iterable[str]] = None,
    instance_lookups: Union[Mapping, Iterable[Mapping]] = None,
    include_all_instances: bool = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the status of the specified instances or all of your instances. By
    default, only running instances are described, unless you specifically indicate
    to return the status of all instances.

    Instance status includes the following components:
      - Status checks - Amazon EC2 performs status checks on running EC2 instances
        to identify hardware and software issues.
      - Scheduled events - Amazon EC2 can schedule events (such as reboot, stop,
        or terminate) for your instances related to hardware issues, software updates,
        or system maintenance.
      - Instance state - You can manage your instances from the moment you launch
        them through their termination.

    :type instance_ids: str or list(str)
    :param instance_ids: The instance IDs. Default: describes all
      your instances. Constraints: Maximum 100 explicitly specified instance IDs.
    :type instance_lookups: dict or list(dict)
    :param instance_lookups: One or more dicts of kwargs that
      :py:func:`lookup_instance` accepts. Used to lookup ``instance_ids``.
    :param bool include_all_instances: When ``True``, includes the health status
      for all instances. When ``False``, includes the health status for running
      instances only. Default: ``False``
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_instance_status>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_instance_status``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookups
            or [{"instance_id": instance_id} for instance_id in instance_ids or []],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = salt.utils.data.filter_falsey(
            {
                "ids": res["result"]["instance"],
                "filters": filters,
                "IncludeAllInstances": include_all_instances,
            }
        )
    return __utils__["boto3.describe_resource"](
        "instance_status", client=client, **params
    )


@_arguments_to_list("instance_ids")
def describe_instances(
    instance_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified instances or all instances.

    If you specify instance IDs, the output includes information for only the specified
    instances. If you specify filters, the output includes information for only
    those instances that meet the filter criteria. If you do not specify instance
    IDs or filters, the output includes information for all instances, which can
    affect performance. We recommend that you use pagination to ensure that the
    operation returns quickly and successfully.

    If you specify an instance ID that is not valid, an error is returned. If you
    specify an instance that you do not own, it is not included in the output.

    Recently terminated instances might appear in the returned results. This interval
    is usually less than one hour.

    If you describe instances in the rare case where an Availability Zone is experiencing
    a service disruption and you specify instance IDs that are in the affected
    zone, or do not specify any instance IDs at all, the call fails. If you describe
    instances and specify only instance IDs that are in an unaffected zone, the
    call works normally.

    :type instance_ids: str or list(str)
    :param instance_ids: The instance IDs. Default: Describes all
      your instances.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_instances>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_instances``-call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "instance",
        ids=instance_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("internet_gateway_ids")
def describe_internet_gateways(
    internet_gateway_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your internet gateways.

    :type internet_gateway_ids: str or list(str)
    :param internet_gateway_ids: The (list of) IDs of the internet
      gateway(s) to describe.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_internet_gateways>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_internet_gateways``-
      call on succes.

    :depends: boto3.client('ec2').describe_internet_gateways
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "internet_gateway",
        ids=internet_gateway_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("pool_ids")
def describe_ipv6_pools(
    pool_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes your IPv6 address pools.

    :type pool_ids: str or list(str)
    :param pool_ids: The IDs of the IPv6 address pools.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_ipv6_pools>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_ipv6_pools``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "ipv6_pool",
        ids=pool_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("launch_template_ids", "launch_template_names")
def describe_launch_templates(
    launch_template_ids: Union[str, Iterable[str]] = None,
    launch_template_names: Union[Mapping, Iterable[Mapping]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more launch templates.

    :type launch_template_ids: str or list(str)
    :param launch_template_ids: One or more launch template IDs.
    :type launch_template_names: str or list(str)
    :param launch_template_names: One or more launch template names.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_launch_templates>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_launch_templates``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    params = salt.utils.data.filter_falsey(
        {"LaunchTemplateNames": launch_template_names}
    )
    return __utils__["boto3.describe_resource"](
        "launch_template",
        ids=launch_template_ids,
        filters=filters,
        client=client,
        **params,
    )


@_arguments_to_list("key_pair_ids", "key_names")
def describe_key_pairs(
    key_pair_ids: Union[str, Iterable[str]] = None,
    key_names: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified key pairs or all of your key pairs.

    :type key_pair_ids: str or list(str)
    :param key_pair_ids: The IDs of the key pairs.
    :type key_names: str or list(str)
    :param key_names: The key pair names.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_key_pairs>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_key_pairs``-call
      on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "key_pair",
        ids=key_pair_ids,
        filters=filters,
        client=client,
        KeyNames=key_names,
    )


@_arguments_to_list("local_gateway_route_table_ids")
def describe_local_gateway_route_tables(
    local_gateway_route_table_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Describes one or more local gateway route tables. By default, all local gateway
    route tables are described. Alternatively, you can filter the results.

    :type local_gateway_route_table_ids: str or list(str)
    :param local_gateway_route_table_ids: The IDs of the local gateway
      route tables.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_local_gateway_route_tables>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_local_gateway_route_tables``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "local_gateway_route_table",
        ids=local_gateway_route_table_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("local_gateway_ids")
def describe_local_gateways(
    local_gateway_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more local gateways. By default, all local gateways are described.
    Alternatively, you can filter the results.

    :type local_gateway_ids: str or list(str)
    :param local_gateway_ids: The (list of) ID(s) of local gateway(s)
      to describe.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_local_gateways>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_local_gateways``-call
      on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "local_gateway",
        ids=local_gateway_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("prefix_list_ids")
def describe_managed_prefix_lists(
    prefix_list_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes your managed prefix lists and any AWS-managed prefix lists.

    To view the entries for your prefix list, use GetManagedPrefixListEntries.

    :type prefix_list_ids: str or list(str)
    :param prefix_list_ids: One or more prefix list IDs.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_managed_prefix_lists>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_managed_prefix_lists``-
      call on succes.

    :depends: boto3.client('ec2').describe_managed_prefix_lists
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "managed_prefix_list",
        ids=prefix_list_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("nat_gateway_ids")
def describe_nat_gateways(
    nat_gateway_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more NAT Gateways.

    :type nat_gateway_ids: str or list(str)
    :param nat_gateway_ids: The (list of) NAT Gateway IDs to specify the NGW(s) to describe.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_nat_gateways>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_nat_gateways``-
      call on succes.

    :depends: boto3.client('ec2').describe_nat_gateways
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "nat_gateway",
        ids=nat_gateway_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("network_acl_ids")
def describe_network_acls(
    network_acl_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your network ACLs.

    :type network_acl_ids: str or list(str)
    :param network_acl_ids: The (list of) ID(s) of network ACLs to describe.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_network_acls>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_network_acls``-
      call on succes.

    :depends: boto3.client('ec2').describe_network_acls
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "network_acl",
        ids=network_acl_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("attributes")
def describe_network_interface_attribute(
    attributes: Union[str, Iterable[str]] = None,
    network_interface_id: str = None,
    network_interface_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more network interface attributes.

    :type attributes: str or list(str)
    :param attributes: One or more attributes to describe.
      Allowed values: ``description``, ``group_set``, ``source_dest_check``, ``attachment``.
    :param str network_interface_id: The ID of the network interface to operate on.
    :param dict network_interface_lookup: Any kwargs that :py:func:`lookup_network_interface`
      accepts. Used to lookup ``network_interface_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the attributes and their values on succes.

    :depends: boto3.client('ec2').describe_network_interface_attribute
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "network_interface",
            "kwargs": network_interface_lookup
            or {"network_interface_id": network_interface_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"NetworkInterfaceId": res["result"]["network_interface"]}
    ret = {}
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    for attribute in attributes:
        # Well this is nasty. When selecting the attribute for querying, it needs
        # to be lowerCamelCased, but the returned attribute is UpperCamelCased.
        params["Attribute"] = salt.utils.stringutils.snake_to_camel_case(attribute)
        try:
            res = client.describe_vpc_attribute(**params)
            ret[attribute] = res[
                salt.utils.stringutils.snake_to_camel_case(attribute, uppercamel=True)
            ]["Value"]
        except (ParamValidationError, ClientError) as exp:
            return {"error": __utils__["boto3.get_error"](exp)["message"]}
    return {"result": ret}


@_arguments_to_list("network_interface_permission_ids")
def describe_network_interface_permissions(
    network_interface_permission_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the permissions for your network interfaces.

    :type network_interface_permission_ids: str or list(str)
    :param network_interface_permission_ids: One or more network
      interface permission IDs.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_network_interface_permissions>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_network_interface_permissions``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "network_interface_permission",
        ids=network_interface_permission_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("network_interface_ids")
def describe_network_interfaces(
    network_interface_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your network interfaces.

    :type network_interface_ids: str or list(str)
    :param network_interface_ids: One or more network interface IDs.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_network_interfaces>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_network_interfaces``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "network_interface",
        ids=network_interface_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("group_ids", "group_names")
def describe_placement_groups(
    group_ids: Union[str, Iterable[str]] = None,
    group_names: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified placement groups or all of your placement groups.

    :type group_ids: str or list(str)
    :param group_ids: The IDs of the placement groups.
    :type group_names: str or list(str)
    :param group_names: The names of the placement groups.
      Default: Describes all your placement groups, or only those otherwise specified.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_placement_groups>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_placement_groups``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "placement_group",
        ids=group_ids,
        filters=filters,
        client=client,
        GroupNames=group_names,
    )


@_arguments_to_list("pool_ids")
def describe_public_ipv4_pools(
    pool_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified IPv4 address pools.

    :type pool_ids: str or list(str)
    :param pool_ids: The IDs of the address pools.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_public_ipv4_pools>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_public_ipv4_pools``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "public_ipv4_pool",
        ids=pool_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("region_names")
def describe_regions(
    region_names: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the Regions that are enabled for your account, or all Regions.

    :type region_names: str or list(str)
    :param region_names: The names of the Regions. You can specify
      any Regions, whether they are enabled and disabled for your account.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_regions>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_regions``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "region",
        filters=filters,
        client=client,
        RegionNames=region_names,
    )


@_arguments_to_list("route_table_ids")
def describe_route_tables(
    route_table_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your route tables.

    :type route_table_ids: str or list(str)
    :param route_table_ids: The (list of) ID(s) of route tables to describe.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_route_tables>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_route_tables``-
      call on succes.

    :depends: boto3.client('ec2').describe_route_tables
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "route_table",
        ids=route_table_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("group_id")
def describe_security_group_references(
    group_id: Union[str, Iterable[str]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    [VPC only] Describes the VPCs on the other side of a VPC peering connection
    that are referencing the security groups you've specified in this request.

    :type group_id: str or list(str)
    :param group_id: The IDs of the security groups in your account.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_route_tables``-
      call on succes.

    :depends: boto3.client('ec2').describe_security_group_references
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "security_group_reference",
        client=client,
        GroupId=group_id,
    )


@_arguments_to_list("group_ids", "group_names")
def describe_security_groups(
    group_ids: Union[str, Iterable[str]] = None,
    group_names: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified security groups or all of your security groups.

    :type group_ids: str or list(str)
    :param group_ids: The IDs of the security groups. Required for security
      groups in a nondefault VPC. Default: Describes all your security groups.
    :type group_names: str or list(str)
    :param group_names: [EC2-Classic and default VPC only] The names of
      the security groups. You can specify either the security group name or
      the security group ID. For security groups in a nondefault VPC, use the
      group-name filter to describe security groups by name.
      Default: Describes all your security groups.
    :param dict filters: The filters. If using multiple filters for rules, the
      results include security groups for which any combination of rules - not
      necessarily a single rule - match all filters.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_security_groups``
      call on succes.

    :depends: boto3.client('ec2').describe_security_groups
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "security_group",
        ids=group_ids,
        filters=filters,
        GroupNames=group_names,
        client=client,
    )


@_arguments_to_list("attributes")
def describe_snapshot_attribute(
    attributes: Union[str, Iterable[str]] = None,
    snapshot_id: str = None,
    snapshot_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
):
    """
    Describes one or more attributes of the specified snapshot.

    :type attributes: str or list(str)
    :param attributes: The snapshot attributes you would like to view.
    :param str snapshot_id: The ID of the EBS snapshot.
    :param dict snapshot_lookup: Any kwargs that :py:func:`lookup_snapshot` accepts.
      Used to lookup ``snapshot_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the attributes and their values on succes.

    :depends: boto3.client('ec2').describe_snapshot_attribute
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "snapshot",
            "kwargs": snapshot_lookup or {"snapshot_id": snapshot_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"SnapshotId": res["result"]["snapshot"]}
    ret = {}
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    for attribute in attributes:
        # Well this is nasty. When selecting the attribute for querying, it needs
        # to be lowerCamelCased, but the returned attribute is UpperCamelCased.
        params["Attribute"] = salt.utils.stringutils.snake_to_camel_case(attribute)
        try:
            res = client.describe_vpc_attribute(**params)
            ret[attribute] = res[
                salt.utils.stringutils.snake_to_camel_case(attribute, uppercamel=True)
            ]["Value"]
        except (ParamValidationError, ClientError) as exp:
            return {"error": __utils__["boto3.get_error"](exp)["message"]}
    return {"result": ret}


@_arguments_to_list("snapshot_ids", "owner_ids", "restorable_by_user_ids")
def describe_snapshots(
    snapshot_ids: Union[str, Iterable[str]] = None,
    owner_ids: Union[str, Iterable[str]] = None,
    restorable_by_user_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified EBS snapshots available to you or all of the EBS snapshots
    available to you.

    The snapshots available to you include public snapshots, private snapshots
    that you own, and private snapshots owned by other AWS accounts for which you
    have explicit create volume permissions.

    The create volume permissions fall into the following categories:
      - public: The owner of the snapshot granted create volume permissions for
        the snapshot to the all group. All AWS accounts have create volume permissions
        for these snapshots.
      - explicit: The owner of the snapshot granted create volume permissions to
        a specific AWS account.
      - implicit: An AWS account has implicit create volume permissions for all
        snapshots it owns.

    The list of snapshots returned can be filtered by specifying snapshot IDs,
    snapshot owners, or AWS accounts with create volume permissions. If no options
    are specified, Amazon EC2 returns all snapshots for which you have create volume
    permissions.

    If you specify one or more snapshot IDs, only snapshots that have the specified
    IDs are returned. If you specify an invalid snapshot ID, an error is returned.
    If you specify a snapshot ID for which you do not have access, it is not included
    in the returned results.

    If you specify one or more snapshot owners using the OwnerIds option, only
    snapshots from the specified owners and for which you have access are returned.
    The results can include the AWS account IDs of the specified owners, amazon
    for snapshots owned by Amazon, or self for snapshots that you own.

    If you specify a list of restorable users, only snapshots with create snapshot
    permissions for those users are returned. You can specify AWS account IDs (if
    you own the snapshots), self for snapshots for which you own or have explicit
    permissions, or all for public snapshots.

    To get the state of fast snapshot restores for a snapshot, use :py:func:`describe_fast_snapshot_restores`.

    :type snapshot_ids: str or list(str)
    :param snapshot_ids: The snapshot IDs.
      Default: Describes the snapshots for which you have create volume permissions.
    :type owner_ids: str or list(str)
    :param owner_ids: Scopes the results to snapshots with the specified owners.
      You can specify a combination of AWS account IDs, ``self``, and ``amazon``.
    :type restorable_by_user_ids: str or list(str)
    :param restorable_by_user_ids: The IDs of the AWS accounts that can create
      volumes from the snapshot.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_snapshots>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_snapshots``-call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "snapshot",
        ids=snapshot_ids,
        filters=filters,
        client=client,
        OwnerIds=owner_ids,
        RestorableByUserIds=restorable_by_user_ids,
    )


def describe_spot_fleet_instances(
    spot_fleet_request_id: str,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the running instances for the specified Spot Fleet.

    :param str spot_fleet_request_id: The ID of the Spot Fleet request.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_spot_fleet_instances``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "spot_fleet_instance",
        client=client,
        result_key="ActiveInstances",
        SpotFleetRequestId=spot_fleet_request_id,
    )


@_arguments_to_list("spot_fleet_request_ids")
def describe_spot_fleet_requests(
    spot_fleet_request_ids: Union[str, Iterable[str]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Mapping:
    """
    Describes your Spot Fleet requests.

    Spot Fleet requests are deleted 48 hours after they are canceled and their
    instances are terminated.

    :type spot_fleet_request_ids: str or list(str)
    :param spot_fleet_request_ids: The IDs of the Spot Fleet requests.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_spot_fleet_requests``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "spot_fleet_request",
        ids=spot_fleet_request_ids,
        client=client,
        result_key="SpotFleetRequestConfigs",
    )


@_arguments_to_list("spot_instance_request_ids")
def describe_spot_instance_requests(
    spot_instance_request_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified Spot Instance requests.

    You can use DescribeSpotInstanceRequests to find a running Spot Instance by
    examining the response. If the status of the Spot Instance is ``fulfilled``,
    the instance ID appears in the response and contains the identifier of the
    instance. Alternatively, you can use DescribeInstances with a filter to look
    for instances where the instance lifecycle is ``spot``.

    Spot Instance requests are deleted four hours after they are canceled and their
    instances are terminated.

    :type spot_instance_request_ids: str or list(str)
    :param spot_instance_request_ids: One or more Spot Instance request IDs.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_spot_instance_requests>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_spot_instance_requests``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "spot_instance_request",
        ids=spot_instance_request_ids,
        filters=filters,
        client=client,
    )


def describe_stale_security_groups(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the stale security group rules for security groups in a specified
    VPC. Rules are stale when they reference a deleted security group in a peer
    VPC, or a security group in a peer VPC for which the VPC peering connection
    has been deleted.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_stale_security_groups``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        return __utils__["boto3.describe_resource"](
            "stale_security_group",
            ids=res["result"]["vpc"],
            client=client,
        )


@_arguments_to_list("subnet_ids")
def describe_subnets(
    subnet_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your subnets.

    :type subnet_ids: str or list(str)
    :param subnet_ids: The (list of) subnet IDs to specify the Subnets to describe.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_subnets>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_subnets``-call
      on succes.

    :depends: boto3.client('ec2').describe_subnets
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "subnet",
        ids=subnet_ids,
        filters=filters,
        client=client,
    )


def describe_tags(
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client=None,
) -> Dict:
    """
    Describes the specified tags for your EC2 resources.

    :param dict filters: The filters.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key with
      dict containing the tags on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "tag",
        filters=filters,
        client=client,
    )


@_arguments_to_list("transit_gateway_ids")
def describe_transit_gateways(
    transit_gateway_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more transit gateways. By default, all transit gateways are
    described. Alternatively, you can filter the results.

    :type transit_gateway_ids: str or list(str)
    :param transit_gateway_ids: The (list of) IDs of the transit gateways.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_transit_gateways>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_transit_gateways``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "transit_gateway",
        ids=transit_gateway_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("attributes")
def describe_volume_attribute(
    attributes: Union[str, Iterable[str]] = None,
    volume_id: str = None,
    volume_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more attributes of the specified volume.

    :type attributes: str or list(str)
    :param attributes: The snapshot attributes you would like to view.
    :param str volume_id: The ID of the volume.
    :param dict volume_lookup: Any kwargs that :py:func:`lookup_volume` accepts.
      Used to lookup ``volume_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the attributes and their values on succes.

    :depends: boto3.client('ec2').describe_volume_attribute
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "volume",
            "kwargs": volume_lookup or {"volume_id": volume_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"volumeId": res["result"]["volume"]}
    ret = {}
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    for attribute in attributes:
        # Well this is nasty. When selecting the attribute for querying, it needs
        # to be lowerCamelCased, but the returned attribute is UpperCamelCased.
        params["Attribute"] = salt.utils.stringutils.snake_to_camel_case(attribute)
        try:
            res = client.describe_vpc_attribute(**params)
            ret[attribute] = res[
                salt.utils.stringutils.snake_to_camel_case(attribute, uppercamel=True)
            ]["Value"]
        except (ParamValidationError, ClientError) as exp:
            return {"error": __utils__["boto3.get_error"](exp)["message"]}
    return {"result": ret}


@_arguments_to_list("volume_ids")
def describe_volumes(
    volume_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Describes the specified EBS volumes or all of your EBS volumes.

    :type volume_ids: str or list(str)
    :param volume_ids: The volume IDs.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_volumes>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_volumes``-call
      on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "volume",
        ids=volume_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("volume_ids", "volume_lookups")
def describe_volumes_modifications(
    volume_ids: Union[str, Iterable[str]] = None,
    volume_lookups: Union[Mapping, Iterable[Mapping]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the most recent volume modification request for the specified EBS volumes.

    If a volume has never been modified, some information in the output will be null.
    If a volume has been modified more than once, the output includes only the
    most recent modification request.

    :type volume_ids: str or list(str)
    :param volume_ids: The IDs of the volumes.
    :type volume_lookups: dict or list(dict)
    :param volume_lookups: One or more dicts of kwargs that :py:func:`lookup_volume`
      accepts. Used to lookup any ``volume_ids`` if none are provided.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_volumes_modifications>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_volumes_modifications``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "volume",
            "kwargs": volume_lookups
            or [{"volume_id": volume_id} for volume_id in volume_ids],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        volume_ids = res["result"]["volume"]
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "volumes_modification",
        ids=volume_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("attributes")
def describe_vpc_attribute(
    attributes: Union[str, Iterable[str]] = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the specified attribute(s) of the specified VPC.

    :type attributes: str or list(str)
    :param attributes: One or more attributes to describe.
      Allowed values: ``enable_dns_support``, ``enable_dns_hostnames``
    :param str vpc_id: The ID of the VPC to operate on.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the attributes and their values on succes.

    :depends: boto3.client('ec2').describe_vpc_attribute
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"VpcId": res["result"]["vpc"]}
    ret = {}
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    for attribute in attributes:
        # Well this is nasty. When selecting the attribute for querying, it needs
        # to be lowerCamelCased, but the returned attribute is UpperCamelCased.
        params["Attribute"] = salt.utils.stringutils.snake_to_camel_case(attribute)
        try:
            res = client.describe_vpc_attribute(**params)
            ret[attribute] = res[
                salt.utils.stringutils.snake_to_camel_case(attribute, uppercamel=True)
            ]["Value"]
        except (ParamValidationError, ClientError) as exp:
            return {"error": __utils__["boto3.get_error"](exp)["message"]}
    return {"result": ret}


@_arguments_to_list("vpc_ids", "vpc_lookups")
def describe_vpc_classic_link(
    vpc_ids: Union[str, Iterable[str]] = None,
    vpc_lookups: Union[Mapping, Iterable[Mapping]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the ClassicLink status of one or more VPCs.

    :type vpc_ids: str or list(str)
    :param vpc_ids: One or more VPCs for which you want to describe
      the ClassicLink status.
    :type vpc_lookups: dict or list(dict)
    :param vpc_lookups: One or more dicts of kwargs that :py:func:`lookup_vpc`
      accepts. Used to lookup any ``vpc_ids`` if none are provided.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_classic_link>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_classic_link``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookups or [{"vpc_id": vpc_id} for vpc_id in vpc_ids or []],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        vpc_ids = res["result"]["vpc"]
        params = salt.utils.data.filter_falsey(
            {
                "VpcIds": vpc_ids if isinstance(vpc_ids, list) else [vpc_ids],
                "Filters": __utils__["boto3.dict_to_boto_filters"](filters),
            }
        )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](
        client.describe_vpc_classic_link,
        params,
    )


@_arguments_to_list("vpc_ids", "vpc_lookups")
def describe_vpc_classic_link_dns_support(
    vpc_ids: Union[str, Iterable[str]] = None,
    vpc_lookups: Union[Mapping, Iterable[Mapping]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the ClassicLink DNS support status of one or more VPCs. If enabled,
    the DNS hostname of a linked EC2-Classic instance resolves to its private IP
    address when addressed from an instance in the VPC to which it's linked.
    Similarly, the DNS hostname of an instance in a VPC resolves to its private
    IP address when addressed from a linked EC2-Classic instance.

    :type vpc_ids: str or list(str)
    :param vpc_ids: One or more VPC IDs.
    :type vpc_lookups: dict or list(dict)
    :param vpc_lookups: One or more dicts of kwargs that :py:func:`lookup_vpc`
      accepts. Used to lookup any ``vpc_ids`` if none are provided.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_classic_link_dns_support``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookups or [{"vpc_id": vpc_id} for vpc_id in vpc_ids or []],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        vpc_ids = res["result"]["vpc"]
        params = {"VpcIds": vpc_ids if isinstance(vpc_ids, list) else [vpc_ids]}
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](
        client.describe_vpc_classic_link_dns_support,
        params,
    )


def describe_vpc_endpoint_connections(
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the VPC endpoint connections to your VPC endpoint services, including
    any endpoints that are pending your acceptance.

    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_endpoint_connections>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_endpoint_connections``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "vpc_endpoint_connection",
        filters=filters,
        client=client,
    )


@_arguments_to_list("service_ids")
def describe_vpc_endpoint_service_configurations(
    service_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the VPC endpoint service configurations in your account (your services).

    :type service_ids: str or list(str)
    :param service_ids: The IDs of one or more services.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_endpoint_service_configurations>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_endpoint_service_configurations``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "vpc_endpoint_service_configuration",
        ids=service_ids,
        filters=filters,
        result_key="ServiceConfigurations",
        client=client,
    )


def describe_vpc_endpoint_service_permissions(
    service_id: str = None,
    service_lookup: Mapping = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes the principals (service consumers) that are permitted to discover
    your VPC endpoint service.

    :param str service_id: The ID of the service.
    :param dict service_lookup: Any kwargs that :py:func:`lookup_vpc_endpoint_service`
      accepts. Used to lookup ``service_id``.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_endpoint_service_permissions>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto
      ``describe_vpc_endpoint_service_permissions``-call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc_endpoint_service",
            "kwargs": service_lookup or {"service_id": service_id},
            "result_keys": "ServiceId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        return __utils__["boto3.describe_resource"](
            "vpc_endpoint_service_permission",
            filters=filters,
            client=client,
            ServiceId=res["result"]["vpc_endpoint_service"],
        )


@_arguments_to_list("service_names")
def describe_vpc_endpoint_services(
    service_names: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes available services to which you can create a VPC endpoint.

    :type service_names: str or list(str)
    :param service_names: One or more service names.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_endpoint_services>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_endpoint_services``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "vpc_endpoint_service",
        filters=filters,
        client=client,
        ServiceNames=service_names,
    )


@_arguments_to_list("vpc_endpoint_ids")
def describe_vpc_endpoints(
    vpc_endpoint_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your VPC endpoints.

    :type vpc_endpoint_ids: str or list(str)
    :param vpc_endpoint_ids: The (list of) ID(s) of the VPC endpoint(s) to describe.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_endpoints>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_endpoints``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "vpc_endpoint",
        ids=vpc_endpoint_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("vpc_peering_connection_ids")
def describe_vpc_peering_connections(
    vpc_peering_connection_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your VPC peering connections.

    :type vpc_peering_connection_ids: str or list(str)
    :param vpc_peering_connection_ids: The (list of) ID(s) of VPC Peering
      connections to describe.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_peering_connections>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_peering_connections``-
      call on succes.

    :depends: boto3.client('ec2').describe_vpc_peering_connections
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "vpc_peering_connection",
        ids=vpc_peering_connection_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("vpc_ids")
def describe_vpcs(
    vpc_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your VPCs.

    :type vpc_ids: str or list(str)
    :param vpc_ids: One or more VPC IDs. Default: Describes all your VPCs.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpcs>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpcs``-call on succes.

    :depends: boto3.client('ec2').describe_vpcs
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "vpc",
        ids=vpc_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("vpn_connection_ids")
def describe_vpn_connections(
    vpn_connection_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> str:
    """
    Describes one or more of your VPN connections.

    :type vpn_connection_ids: str or list(str)
    :param vpn_connection_ids: One or more VPN connection IDs.
      Default: Describes your VPN connections.
    :param dict filters: One or more filters. See
      `here <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpn_connections>`__
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpcs``-call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "vpn_connection",
        ids=vpn_connection_ids,
        filters=filters,
        client=client,
    )


@_arguments_to_list("vpn_gateway_ids")
def describe_vpn_gateways(
    vpn_gateway_ids: Union[str, Iterable[str]] = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of your virtual private gateways.

    :type vpn_gateway_ids: str or list(str)
    :param vpn_gateway_ids: One or more virtual private gateway IDs.
    :param dict filters: The filters to apply to the list of virtual private gateways
      to describe.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpn_gateways``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "vpn_gateway",
        ids=vpn_gateway_ids,
        filters=filters,
        client=client,
    )


def detach_internet_gateway(
    internet_gateway_id: str = None,
    internet_gateway_lookup: Mapping = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Detaches an internet gateway from a VPC, disabling connectivity between the
    internet and the VPC. The VPC must not contain any running instances with
    Elastic IP addresses or public IPv4 addresses.

    :param str internet_gateway_id: The ID of the Internet gateway to detach.
    :param dict internet_gateway_lookup: Any kwargs that :py:func:`lookup_internet_gateway`
      accepts. Used to lookup ``internet_gateway_id``.
    :param str vpc_id: The ID of the VPC to detach from the IGW.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_internet_gateways, boto3.client('ec2').describe_vpcs, boto3.client('ec2').detach_internet_gateway
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        vpc_id = res["vpc"]
    internet_gateway_lookup = internet_gateway_lookup or {
        "internet_gateway_id": internet_gateway_id,
        "attachment_vpc_id": vpc_id,
    }
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "internet_gateway",
            "kwargs": internet_gateway_lookup,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = {"InternetGatewayId": res["internet_gateway"], "VpcId": vpc_id}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.detach_internet_gateway, params)


def detach_network_interface(
    attachment_id: str = None,
    network_interface_lookup: Mapping = None,
    force: bool = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Detaches a network interface from an instance.

    :param str attachment_id: The ID of the attachment.
    :param dict network_interface_lookup: Any kwargs that :py:func:`lookup_network_interface`
      accepts. Used to lookup ``attachment_id``.
    :param bool force: Specifies whether to force a detachment. Note:
      Use the Force parameter only as a last resort to detach a network interface
      from a failed instance.
      If you use the Force parameter to detach a network interface, you might not
      be able to attach a different network interface to the same index on the
      instance without first stopping and starting the instance.
      If you force the detachment of a network interface, the instance metadata
      might not get updated. This means that the attributes associated with the
      detached network interface might still be visible. The instance metadata
      will get updated when you stop and start the instance.
    :param bool blocking: Wait until the network interface becomes available.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on succes.
    """
    if attachment_id is None:
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "network_interface",
                "kwargs": network_interface_lookup,
                "result_keys": ["NetworkInterfaceId", "Attachment:AttachmentId"],
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            res = res["result"]["network_interface"]
            attachment_id = res["Attachment:AttachmentId"]
            network_interface_id = res["NetworkInterfaceId"]
    params = salt.utils.data.filter_falsey(
        {"AttachmentId": attachment_id, "Force": force}
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](client.detach_network_interface, params)
    if "error" in res:
        return res
    if blocking:
        ret = __utils__["boto3.wait_resource"](
            "network_interface",
            "available",
            params={
                "NetworkInterfaceIds": [network_interface_id],
            },
            client=client,
        )
    else:
        ret = {"result": True}
    return ret


def detach_volume(
    volume_id: str = None,
    volume_lookup: Mapping = None,
    instance_id: str = None,
    instance_lookup: Mapping = None,
    device: str = None,
    force: bool = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Detaches an EBS volume from an instance. Make sure to unmount any file systems
    on the device within your operating system before detaching the volume. Failure
    to do so can result in the volume becoming stuck in the busy state while detaching.
    If this happens, detachment can be delayed indefinitely until you unmount the
    volume, force detachment, reboot the instance, or all three. If an EBS volume
    is the root device of an instance, it can't be detached while the instance is
    running. To detach the root volume, stop the instance first.

    When a volume with an AWS Marketplace product code is detached from an instance,
    the product code is no longer associated with the instance.

    :param str volume_id: The ID of the volume.
    :param dict volume_lookup: Any kwargs that :py:func:`lookup_volume` accepts.
      Used to lookup ``volume_id``.
    :param str instance_id: The ID of the instance. If you are detaching a Multi-
      Attach enabled volume, you must specify an instance ID.
    :param dict instance_lookup: Any kwargs that :py:func:`lookup_instance` accepts.
      Used to lookup ``instance_id``.
    :param str device: The device name.
    :param bool Force: Forces detachment if the previous detachment attempt did
      not occur cleanly (for example, logging into an instance, unmounting the
      volume, and detaching normally). This option can lead to data loss or a corrupted
      file system. Use this option only as a last resort to detach a volume from
      a failed instance. The instance won't have an opportunity to flush file system
      caches or file system metadata. If you use this option, you must perform
      file system check and repair procedures.
    :param bool blocking: Wait until the volume becomes available.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``detach_volume``-call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "volume",
            "kwargs": volume_lookup or {"volume_id": volume_id},
        },
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookup or {"instance_id": instance_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = salt.utils.data.filter_falsey(
            {
                "Device": device,
                "Force": force,
                "InstanceId": res["instance"],
                "VolumeId": res["volume"],
            }
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](client.detach_volume, params)
    if "error" in res:
        return res
    if blocking:
        ret = __utils__["boto3.wait_resource"](
            "volume",
            "available",
            params={
                "VolumeIds": [volume_id],
            },
            client=client,
        )
    else:
        ret = {"result": True}
    return ret


def detach_vpn_gateway(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    vpn_gateway_id: str = None,
    vpn_gateway_lookup: Mapping = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Detaches a virtual private gateway from a VPC. You do this if you're planning
    to turn off the VPC and not use it anymore. You can confirm a virtual private
    gateway has been completely detached from a VPC by describing the virtual private
    gateway (any attachments to the virtual private gateway are also described).

    You must wait for the attachment's state to switch to detached before you can
    delete the VPC or attach a different VPC to the virtual private gateway.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param str vpn_gateway_id: The ID of the virtual private gateway.
    :param dict vpn_gateway_lookup: Any kwargs that :py:func:`lookup_vpn_gateway`
      accepts. Used to lookup ``vpn_gateway_id``.
    :param bool blocking: Wait until the virtual private gateway is detached.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        {
            "service": "ec2",
            "name": "vpn_gateway",
            "kwargs": vpn_gateway_lookup or {"vpn_gateway_id": vpn_gateway_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        vpc_id = res["vpc"]
        vpn_gateway_id = res["vpn_gateway"]
    params = salt.utils.data.filter_falsey(
        {"VpcId": vpc_id, "VpnGatewayId": vpn_gateway_id}
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](client.detach_vpn_gateway, params)
    if "error" in res:
        return res
    if blocking:
        ret = __utils__["boto3.wait_resource"](
            "vpn_gateway",
            "detached",
            params={
                "VpnGatewayIds": vpn_gateway_id,
                "Filters": __utils__["boto3.dict_to_boto_filters"](
                    {"attachment.vpc-id": vpc_id}
                ),
            },
            client=client,
        )
    else:
        ret = {"result": True}
    return ret


def disable_vpc_classic_link(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Disables ClassicLink for a VPC. You cannot disable ClassicLink for a VPC that
    has EC2-Classic instances linked to it.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = salt.utils.data.filter_falsey({"VpcId": res["result"]["vpc"]})
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](client.disable_vpc_classic_link, params)
    if "error" in res:
        return res
    return {"result": res["result"]["Return"]}


def disable_vpc_classic_link_dns_support(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Disables ClassicLink DNS support for a VPC. If disabled, DNS hostnames resolve
    to public IP addresses when addressed between a linked EC2-Classic instance
    and instances in the VPC to which it's linked.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = salt.utils.data.filter_falsey({"VpcId": res["result"]["vpc"]})
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](
        client.disable_vpc_classic_link_dns_support, params
    )
    if "error" in res:
        return res
    return {"result": res["result"]["Return"]}


def disassociate_address(
    association_id: str = None,
    address_lookup: Mapping = None,
    public_ip: str = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Disassociates an Elastic IP address from the instance or network interface
    it's associated with.

    :param str association_id: [EC2-VPC] The association ID.
    :param dict address_lookup: Any kwargs that :py:func:`lookup_address` accepts.
      Used to lookup ``association_id``.
    :param str public_ip: [EC2-Classic] The Elastic IP address.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "address",
            "kwargs": address_lookup or {"association_id": association_id},
            "result_keys": "AssociationId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = salt.utils.data.filter_falsey(
            {"AssociationId": res["result"]["address"], "PublicIp": public_ip}
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.disassociate_address, params)


def disassociate_route_table(
    association_id: str = None,
    route_table_id: str = None,
    route_table_lookup: Mapping = None,
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Disassociates a subnet from a route table. You can either specify an
    association_id, or (route_table and subnet).
    After you perform this action, the subnet no longer uses the routes in the
    route table. Instead, it uses the routes in the VPC's main route table.

    :param str association_id: The association ID of the route table-subnet association.
      If this is not known, it will be looked up using describe_route_tables
      and the route_table- and subnet-information below.
    :param str route_table_id: The ID of the route table to disassociate.
    :param dict route_table_lookup: Any kwargs that :py:func:`lookup_route_table`
      accepts. Used to lookup ``route_table_id``.
    :param str subnet_id: The ID of the subnet to disassociate from.
      If ``association_subnet_id`` is present in ``route_table_lookup``, that
      is assumed to be the subnet_id to disassociate from and this argument
      is ignored.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
      If ``association_subnet_id`` is present in ``route_table_lookup``, that
      is assumed to be the subnet_id to disassociate from, negating the need
      for a subnet lookup.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``disassociate_route_table``-
      call on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_subnets, boto3.client('ec2').describe_route_tables, boto3.client('ec2').disassociate_route_table
    """
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    if not association_id:
        if not any((route_table_id, route_table_lookup)):
            raise SaltInvocationError(
                "At least route_table_id or route_table_lookup must be specified "
                "if association_id is not given."
            )
        if (
            isinstance(route_table_lookup, dict)
            and route_table_lookup.get("association_subnet_id") is not None
        ):
            subnet_id = route_table_lookup.get("association_subnet_id")
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "subnet",
                "kwargs": subnet_lookup or {"subnet_id": subnet_id},
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            subnet_id = res["result"]["subnet"]
        route_table_lookup = route_table_lookup or {"route_table_id": route_table_id}
        route_table_lookup["association_subnet_id"] = subnet_id
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "route_table",
                "kwargs": route_table_lookup,
                "result_keys": "Associations:0:RouteTableAssociationId",
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            association_id = res["result"]["route_table"]
    params = {"AssociationId": association_id}
    return __utils__["boto3.handle_response"](client.disassociate_route_table, params)


def disassociate_subnet_cidr_block(
    association_id: str = None,
    ipv6_cidr_block: str = None,
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
):
    """
    Disassociates a CIDR block from a subnet. Currently, you can disassociate an
    IPv6 CIDR block only. You must detach or delete all gateways and resources
    that are associated with the CIDR block before you can disassociate it.

    :param str association_id: The association ID for the CIDR block.
    :param str ipv6_cidr_block: The IPv6 CIDR block to disassociate.
      Provide this together with ``subnet_id`` or ``subnet_lookup`` if you want
      the association_id looked up. Since a subnet can only be associated with
      a single ipv6_cidr_block, this argument is optional.
    :param str subnet_id: The ID of the subnet to work on.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
    :param bool blocking: Block until the ipv6_cidr_block has been disassociated.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``disassociate_subnet_cidr_block``-
      call on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_subnets, boto3.client('ec2').describe_subnets, boto3.client('ec2').disassociate_subnet_cidr_block
    """
    if association_id is None:
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "subnet",
                "kwargs": subnet_lookup or {"subnet_id": subnet_id},
                "result_keys": "Ipv6CidrBlockAssociationSet",
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            current_ipv6_association = res["result"]["subnet"]
        if not current_ipv6_association:
            return {
                "error": "The subnet specified does not have an IPv6 CIDR block association."
            }
        current_associated_ipv6_cidr_block = [
            item
            for item in current_ipv6_association
            if item["Ipv6CidrBlock"] == ipv6_cidr_block
        ]
        if not current_associated_ipv6_cidr_block:
            return {
                "error": "The subnet does not have the specified IPv6 CIDR block associated."
            }
        association_id = current_associated_ipv6_cidr_block[0]["AssociationId"]
    params = {"AssociationId": association_id}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](
        client.disassociate_subnet_cidr_block, params
    )
    if "error" in res:
        return res
    if blocking:
        params = __utils__["boto3.dict_to_boto_filters"](
            {"ipv6-cidr-block-association.association_id": association_id}
        )
        __utils__["boto3.wait_resource"](
            "subnet_ipv6_cidr_block",
            "disassociated",
            params=params,
            client=client,
        )
    return {"result": True}


def disassociate_vpc_cidr_block(
    association_id: str = None,
    vpc_lookup: Mapping = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Disassociates a CIDR block from a VPC. To disassociate the CIDR block, you
    must specify its association ID. You can get the association ID by using
    DescribeVpcs. You must detach or delete all gateways and resources that are
    associated with the CIDR block before you can disassociate it.
    You cannot disassociate the CIDR block with which you originally created the
    VPC (the primary CIDR block).

    :param str association_id: The ID of the association to remove.
    :param str vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``association_id``. As such, it must contain the
      either the kwarg ``cidr_block`` or ``ipv6_cidr_block`` to specify the exact
      IPv4/IPv6 CIDR block to disassociate.
    :param bool blocking: Wait for the disassociation to be complete.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``disassociate_vpc_cidr_block``-
      call on succes.

    :depends: boto3.client('ec2').disassociate_vpc_cidr_block
    """
    # The annoying thing here is that if association_id is given, we don't know
    # whether that's an IPv4 CIDR block or an IPv6 CIDR block ...
    if association_id is None:
        if not vpc_lookup:
            raise SaltInvocationError(
                'When not providing an association_id, the argument "vpc_lookup" is required.'
            )
        if "cidr_block" not in vpc_lookup and "ipv6_cidr_block" not in vpc_lookup:
            raise SaltInvocationError(
                'The argument vpc_lookup must contain an entry for either "cidr_block" or "ipv6_cidr_block".'
            )
        cidr_block_type = "ipv6" if "ipv6_cidr_block" in vpc_lookup else ""
    # ... So we will have to lookup both ...
    if association_id is None or blocking:
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "vpc",
                "kwargs": vpc_lookup or {"cidr_block_association_id": association_id},
                "result_keys": "CidrBlockAssociationSet",
                "required": False,
            },
            {
                "service": "ec2",
                "name": "vpc",
                "as": "vpc6",
                "kwargs": vpc_lookup
                or {"ipv6_cidr_block_association_id": association_id},
                "result_keys": "Ipv6CidrBlockAssociationSet",
                "required": False,
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            res = res["result"]
            log.debug("HERBERT: res: %s", res)
            # ... And figure out which one it was ...
            if association_id:
                matching_ipv4_cidr_blocks = [
                    item
                    for item in res["vpc"]
                    if item["AssociationId"] == association_id
                ]
                matching_ipv6_cidr_blocks = [
                    item
                    for item in res["vpc6"]
                    if item["AssociationId"] == association_id
                ]
                if not any((matching_ipv4_cidr_blocks, matching_ipv6_cidr_blocks)):
                    raise SaltInvocationError(
                        "No VPC found with matching associated IPv4 or IPv6 CIDR blocks."
                    )
                cidr_block_type = "ipv6" if matching_ipv6_cidr_blocks else ""
            elif "cidr_block" in vpc_lookup:
                if res["vpc"] is None:
                    return {
                        "error": 'No IPv4 CIDR block association was found with the information provided in "vpc_lookup".'
                    }
                cidr_block_type = ""
                matching_ipv4_cidr_blocks = [
                    item
                    for item in res["vpc"]
                    if item["CidrBlock"] == vpc_lookup.get("cidr_block")
                ]
            elif "ipv6_cidr_block" in vpc_lookup:
                if res["vpc6"] is None:
                    return {
                        "error": 'No IPv6 CIDR block association was found with the information provided in "vpc_lookup".'
                    }
                cidr_block_type = "ipv6"
                matching_ipv6_cidr_blocks = [
                    item
                    for item in res["vpc6"]
                    if item["Ipv6CidrBlock"] == vpc_lookup.get("ipv6_cidr_block")
                ]
            res = (
                matching_ipv6_cidr_blocks[0]
                if cidr_block_type == "ipv6"
                else matching_ipv4_cidr_blocks[0]
            )
            association_id = res["AssociationId"]
    params = {"AssociationId": association_id}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    res = __utils__["boto3.handle_response"](client.disassociate_vpc_cidr_block, params)
    if "error" in res:
        return res
    if blocking:
        # ... All so we can wait for the correct CIDR block to be disassociated.
        params = {
            "Filters": __utils__["boto3.dict_to_boto_filters"](
                {
                    "{}{}cidr-block-association.association-id".format(
                        cidr_block_type, "-" if cidr_block_type else ""
                    ): association_id
                }
            )
        }
        res = __utils__["boto3.wait_resource"](
            "vpc_{}{}cidr_block".format(
                cidr_block_type, "_" if cidr_block_type else ""
            ),
            "disassociated",
            params=params,
            client=client,
        )
        if "error" in res:
            return res
    return {"result": True}


def enable_vpc_classic_link(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Enables a VPC for ClassicLink. You can then link EC2-Classic instances to your
    ClassicLink-enabled VPC to allow communication over private IP addresses. You
    cannot enable your VPC for ClassicLink if any of your VPC route tables have
    existing routes for address ranges within the 10.0.0.0/8 IP address range,
    excluding local routes for VPCs in the 10.0.0.0/16 and 10.1.0.0/16 IP address ranges.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the resulting boolean of the boto ``enable_vpc_classic_link``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"VpcId": res["result"]["vpc"]}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    res = __utils__["boto3.handle_response"](client.enable_vpc_classic_link, params)
    if "error" in res:
        return res
    return {"result": res["result"]["Return"]}


def enable_vpc_classic_link_dns_support(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Enables a VPC to support DNS hostname resolution for ClassicLink. If enabled,
    the DNS hostname of a linked EC2-Classic instance resolves to its private IP
    address when addressed from an instance in the VPC to which it's linked. Similarly,
    the DNS hostname of an instance in a VPC resolves to its private IP address
    when addressed from a linked EC2-Classic instance.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``enable_vpc_classic_link_dns_support``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"VpcId": res["result"]["vpc"]}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    res = __utils__["boto3.handle_response"](
        client.enable_vpc_classic_link_dns_support, params
    )
    if "error" in res:
        return res
    return {"result": res["result"]["Return"]}


def import_key_pair(
    key_name,
    public_key_material,
    tags=None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
):
    """
    Imports the public key from an RSA key pair that you created with a third-party
    tool. Compare this with :py:func:`create_key_pair`, in which AWS creates the
    key pair and gives the keys to you (AWS keeps a copy of the public key).
    With :py:func:`import_key_pair`, you create the key pair and give AWS just
    the public key. The private key is never transferred between you and AWS.

    :param str key_name: A unique name for the key pair.
    :param str public_key_material: The base64-encoded public key.
    :param dict tags: The tags to apply to the imported key pair.
    """
    params = {
        "KeyName": key_name,
        "PublicKeyMaterial": public_key_material,
    }
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.create_resource"](
        "key_pair",
        boto_function_name="import_key_pair",
        params=params,
        tags=tags,
        client=client,
    )


def lookup_availability_zone(
    zone_id: str = None,
    zone_name: str = None,
    group_name: str = None,
    message: str = None,
    opt_in_status: str = None,
    region_name: str = None,
    state: str = None,
    zone_type: str = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single Availability Zone.
    Can also be used to determine if an Availability Zone exists.

    :param str zone_id: The ID of the Availability Zone (for example, ``use1-az1``)
      or the Local Zone (for example, use ``usw2-lax1-az1``).
    :param str zone_name: The name of the Availability Zone (for example, ``us-east-1a``)
      or the Local Zone (for example, use ``us-west-2-lax-1a``).
    :param str group_name: For Availability Zones, use the Region name. For Local
      Zones, use the name of the group associated with the Local Zone (for example,
      ``us-west-2-lax-1``).
    :param str message: The Zone message.
    :param str opt_in_status: The opt in status.
      Allowed values: opted-in, not-opted-in, opt-in-not-required.
    :param str region_name: The name of the Region for the Zone (for example, ``us-east-1``).
    :param str state: The state of the Availability Zone or Local Zone.
      Allowed values: available, information, impaired, unavailable.
    :param str zone_type: The type of zone, for example, ``local-zone``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_availability_zones``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_availability_zone
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "group-name": group_name,
                "message": message,
                "opt-in-status": opt_in_status,
                "region-name": region_name,
                "state": state,
                "zone-id": zone_id,
                "zone-type": zone_type,
                "zone-name": zone_name,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "availability_zone",
        filters=filters,
        client=client,
    )


def lookup_address(
    allocation_name: str = None,
    allocation_id: str = None,
    association_id: str = None,
    domain: str = None,
    instance_id: str = None,
    instance_lookup: Mapping = None,
    network_border_group: str = None,
    network_interface_id: str = None,
    network_interface_lookup: Mapping = None,
    network_interface_owner_id: str = None,
    private_ip_address: str = None,
    public_ip: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single Elastic IP.
    Can also be used to determine if an Elastic IP exists.

    The following paramers are translated into filters to refine the lookup:

    :param str allocation_name: The ``Name``-tag of the address.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str allocation_id: [EC2-VPC] The allocation ID for the address.
    :param str association_id: [EC2-VPC] The association ID for the address.
    :param str domain: Indicates whether the address is for use in EC2-Classic
      (``standard``) or in a VPC (``vpc``).
    :param str instance_id: The ID of the instance the address is associated
      with, if any.
    :param dict instance_lookup: Any kwargs that :py:func:`lookup_instance`
      accepts. Used to lookup ``instance_id``.
    :param str network_border_group: The location from where the IP address is
      advertised.
    :param str network_interface_id: [EC2-VPC] The ID of the network interface
      that the address is associated with, if any.
    :param dict network_interface_lookup: Any kwargs that :py:func:`lookup_network_interface`
      accepts. Used to lookup ``network_interface_id``.
    :param str network_interface_owner_id:  The AWS account ID of the owner.
    :param str private_ip_address:  [EC2-VPC] The private IP address associated
      with the Elastic IP address.
    :param str public_ip: The Elastic IP address.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the Elastic IP.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_addresses``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_addresses
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookup or {"instance_id": instance_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "network_interface",
            "kwargs": network_interface_lookup
            or {"network_interface_id": network_interface_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        instance_id = res.get("instance")
        network_interface_id = res.get("network_interface")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "allocation-id": allocation_id,
                "association-id": association_id,
                "domain": domain,
                "instance-id": instance_id,
                "network-border-group": network_border_group,
                "network-interface-id": network_interface_id,
                "network-interface-owner-id": network_interface_owner_id,
                "private-ip-address": private_ip_address,
                "public_ip": public_ip,
                "tag-key": tag_key,
                "tag:Name": allocation_name,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "address",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_customer_gateway(
    customer_gateway_id: str = None,
    customer_gateway_name: str = None,
    bgp_asn: int = None,
    ip_address: str = None,
    state: str = None,
    gateway_type: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single DHCP options set.
    Can also be used to determine if a DHCP options set exists.

    The following paramers are translated into filters to refine the lookup:

    :param str customer_gateway_id: ID of the VPN customer gateway.
    :param str customer_gateway_name: The ``Name``-tag of the VPN customer gateway.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param int bgp_asn: The customer gateway's Border Gateway Protocol (BGP)
      Autonomous System Number (ASN).
    :param str ip_address: The IP address of the customer gateway's Internet-routable
      external interface.
    :param str state: The state of the customer gateway.
      Allowed values: pending, available, deleting, deleted.
    :param str gateway_type: The type of customer gateway. Currently, the only
      supported type is ipsec.1
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the VPN customer gateway.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_customer_gateways``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_customer_gateways
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "bgp-asn": bgp_asn,
                "customer-gateway-id": customer_gateway_id,
                "ip-address": ip_address,
                "state": state,
                "type": gateway_type,
                "tag-key": tag_key,
                "tag:Name": customer_gateway_name,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "customer_gateway",
        filters=filters,
        tags=tags,
        client=client,
    )


@_arguments_to_list("domain_name_servers", "ntp_servers", "netbios_name_servers")
def lookup_dhcp_options(
    dhcp_options_id: str = None,
    dhcp_options_name: str = None,
    domain_name_servers: Union[str, Iterable[str]] = None,
    domain_name: str = None,
    ntp_servers: Union[str, Iterable[str]] = None,
    netbios_name_servers: Union[str, Iterable[str]] = None,
    netbios_node_type: str = None,
    owner_id: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single DHCP options set.
    Can also be used to determine if a DHCP options set exists.

    The following paramers are translated into filters to refine the lookup:

    :param str dhcp_options_id: ID of the DHCP options set.
    :param str dhcp_options_name: The ``Name``-tag of the DHCP options set.
      If also specifying ``Name`` in ``tags``, this option is ignored.
    :param list domain_name_servers: Value of this option.
    :param str domain_name: Value of this option.
    :param list ntp_servers: Value of this option.
    :param list netbios_name_servers: Value of this option.
    :param str netbios_node_type: Value of this option.
    :param str owner_id: The ID of the AWS account that owns the DHCP options set.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the DHCP options.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_dhcp_options``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_dhcp_options
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "dhcp-options-id": dhcp_options_id,
                "domain-name-servers": domain_name_servers,
                "domain-name": domain_name,
                "ntp-servers": ntp_servers,
                "netbios-name-servers": netbios_name_servers,
                "netbios-node-type": str(netbios_node_type),
                "owner-id": owner_id,
                "tag-key": tag_key,
                "tag:Name": dhcp_options_name,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "dhcp_options",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_egress_only_internet_gateway(
    egress_only_internet_gateway_id: str = None,
    tag_key: str = None,
    tags: Mapping = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single egress only internet gateway.
    Can also be used to determine if an egress only internet gateway exists.

    The following paramers are translated into filters to refine the lookup:

    :param str: The egress-only internet gateway ID.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the egress only internet gateway.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_egress_only_internet_gateway``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    if filters is None:
        filters = {}
    filters.update(salt.utils.data.filter_falsey({"tag-key": tag_key}))
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "egress_only_internet_gateway",
        ids=egress_only_internet_gateway_id,
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_fpga_image(
    fpga_image_id: str = None,
    fpga_global_image_id: str = None,
    name: str = None,
    owner_id: str = None,
    product_code: str = None,
    shell_version: str = None,
    state: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    update_time: datetime = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single FPGA image.
    Can also be used to determine if an FPGA image exists.

    The following paramers are translated into filters to refine the lookup:

    :param datetime create_time: The creation time of the AFI.
    :param str fpga_image_id: The FPGA image identifier (AFI ID).
    :param str fpga_global_image_id: The global FPGA image identifier (AGFI ID).
    :param str name: The name of the AFI.
    :param str owner_id: The AWS account ID of the AFI owner.
    :param str product_code: The product code.
    :param str shell_version: The version of the AWS shell that was used to create
      the bitstream.
    :param str state: The state of the AFI. Allowed values: ``pending``, ``failed``,
      ``available``, ``unavailable``.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param datetime update_time: The time of the most recent update.
    :param dict filters: Dict with filters to identify the FPGA image.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_fpga_image``-call
      on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "create-time": create_time,
                "fpga-image-id": fpga_image_id,
                "fpga-image-global-id": fpga_global_image_id,
                "name": name,
                "owner-id": owner_id,
                "product-code": product_code,
                "shell-version": shell_version,
                "state": state,
                "tag-key": tag_key,
                "update-time": update_time,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "fpga_image",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_image(
    image_id: str = None,
    image_name: str = None,
    architecture: str = None,
    delete_on_termination: bool = None,
    device_name: str = None,
    snapshot_id: str = None,
    volume_size: int = None,
    volume_type: str = None,
    encrypted: bool = None,
    description: str = None,
    ena_support: bool = None,
    hypervisor: str = None,
    image_type: str = None,
    is_public: bool = None,
    kernel_id: str = None,
    manifest_location: str = None,
    owner_alias: str = None,
    owner_id: str = None,
    platform: str = None,
    product_code: str = None,
    product_code_type: str = None,
    ramdisk_id: str = None,
    root_device_name: str = None,
    root_device_type: str = None,
    state: str = None,
    state_reason_code: str = None,
    state_reason_message: str = None,
    sriov_net_support: bool = None,
    tags: Mapping = None,
    tag_key: str = None,
    virtualization_type: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single Image.
    Can also be used to determine if an Image exists.

    The following paramers are translated into filters to refine the lookup:

    :param str image_id: The ID of the image.
    :param str image_name: The name of the AMI (provided during image creation).
    :param str architecture: The image architecture. Allowed values: i386, x86_64, arm64.
    :param bool delete_on_termination: A Boolean value that indicates whether the
      Amazon EBS volume is deleted on instance termination.
    :param str device_name: The device name specified in the block device mapping.
      (for example, ``/dev/sdh`` or ``xvdh``).
    :param str snapshot_id: The ID of the snapshot used for the EBS volume.
    :param int volume_size: The volume size of the EBS volume, in GiB.
    :param str volume_type: The volume type of the EBS volume. Allowed values:
      gp2, io1, st1, sc1, standard.
    :param bool encrypted: A Boolean that indicates whether the EBS volume is encrypted.
    :param str description: The description of the image (provided during image creation).
    :param bool ena_support: A Boolean that indicates whether enhanced networking
      with ENA is enabled.
    :param str hypervisor: The hypervisor type. Allowed values: ovm, xen.
    :param str image_type: The image type. Allowed values: machine, kernel, ramdisk.
    :param bool is_public: A Boolean that indicates whether the image is public.
    :param str kernel_id: The kernel ID.
    :param str manifest_location: The location of the image manifest.
    :param str owner_alias: The owner alias, from an Amazon-maintained list
      (``amazon`` or ``aws-marketplace``). This is not the user-configured AWS
      account alias set using the IAM console. We recommend that you use the related
      parameter instead of this filter.
    :param str owner_id: The AWS account ID of the owner. We recommend that you
      use the related parameter instead of this filter.
    :param str platform: The platform. To only list Windows-based AMIs, use ``windows``.
    :param str product_code: The product code.
    :param str product_code_type: The type of the product code. Allowed values:
      devpay, marketplace.
    :param str ramdisk_id: The RAM disk ID.
    :param str root_device_name: The device name of the root device volume (for
      example, ``/dev/sda1``).
    :param str root_device_type: The type of the root device volume. Allowed values:
      ebs, instance-store.
    :param str state: The state of the image. Allowed values: available, pending, failed.
    :param str state_reason_code: The reason code for the state change.
    :param str state_reason_message: The message for the state change.
    :param str sriov_net_support: A value of ``simple`` indicates that enhanced
      networking with the Intel 82599 VF interface is enabled.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str virtualization_type: The virtualization type. Allowed values: paravirtual, hvm.
    :param dict filters: Dict with filters to identify the Image.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_image``-call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "architecture": architecture,
                "block-device-mapping.delete-on-termination": delete_on_termination,
                "block-device-mapping.device-name": device_name,
                "block-device-mapping.snapshot-id": snapshot_id,
                "block-device-mapping.volume-size": volume_size,
                "block-device-mapping.volume-type": volume_type,
                "block-device-mapping.encrypted": encrypted,
                "description": description,
                "ena-support": ena_support,
                "hypervisor": hypervisor,
                "image-id": image_id,
                "image-type": image_type,
                "is-public": is_public,
                "kernel-id": kernel_id,
                "manifest-location": manifest_location,
                "name": image_name,
                "owner-alias": owner_alias,
                "owner-id": owner_id,
                "platform": platform,
                "product-code": product_code,
                "product-code-type": product_code_type,
                "ramdisk-id": ramdisk_id,
                "root-device-name": root_device_name,
                "root-device-type": root_device_type,
                "state": state,
                "state-reason-code": state_reason_code,
                "state-reason-message": state_reason_message,
                "sriov-net-support": sriov_net_support,
                "tag-key": tag_key,
                "virtualization_type": virtualization_type,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "image",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_instance(
    affinity: str = None,
    architecture: str = None,
    availability_zone: str = None,
    block_device_attach_time: datetime = None,
    block_device_delete_on_termination: bool = None,
    block_device_name: str = None,
    block_device_status: str = None,
    block_device_volume_id: str = None,
    block_device_volume_lookup: Mapping = None,
    dns_name: str = None,
    group_id: str = None,
    group_name: str = None,
    hibernation_configured: bool = None,
    host_id: str = None,
    hypervisor: str = None,
    iam_instance_profile_arn: str = None,
    image_id: str = None,
    image_lookup: Mapping = None,
    instance_id: str = None,
    instance_lifecycle: str = None,
    instance_state_code: int = None,
    instance_state_name: str = None,
    instance_type: str = None,
    instance_group_id: str = None,
    instance_group_name: str = None,
    ip_address: str = None,
    kernel_id: str = None,
    key_name: str = None,
    launch_index: int = None,
    launch_time: datetime = None,
    metadata_http_tokens: str = None,
    metadata_http_hop_limit: int = None,
    metadata_http_enabled: bool = None,
    monitoring_state: bool = None,
    network_interface_addresses_private_ip_address: str = None,
    network_interface_addresses_primary: bool = None,
    network_interface_addresses_association_public_ip: str = None,
    network_interface_addresses_association_ip_owner_id: str = None,
    network_interface_association_public_ip: str = None,
    network_interface_association_ip_owner_id: str = None,
    network_interface_association_allocation_id: str = None,
    network_interface_association_id: str = None,
    network_interface_attachment_id: str = None,
    network_interface_attachment_instance_id: str = None,
    network_interface_attachment_instance_owner_id: str = None,
    network_interface_attachment_device_index: int = None,
    network_interface_attachment_status: str = None,
    network_interface_attachment_attach_time: datetime = None,
    network_interface_attachment_delete_on_termination: bool = None,
    network_interface_availability_zone: str = None,
    network_interface_description: str = None,
    network_interface_group_id: str = None,
    network_interface_group_name: str = None,
    network_interface_ipv6_address: str = None,
    network_interface_mac_address: str = None,
    network_interface_id: str = None,
    network_interface_owner_id: str = None,
    network_interface_private_dns_name: str = None,
    network_interface_requester_id: str = None,
    network_interface_requester_managed: bool = None,
    network_interface_status: str = None,
    network_interface_source_dest_check: bool = None,
    network_interface_subnet_id: str = None,
    network_interface_vpc_id: str = None,
    owner_id: str = None,
    placement_group_name: str = None,
    placement_partition_number: int = None,
    platform: str = None,
    private_dns_name: str = None,
    private_ip_address: str = None,
    product_code: str = None,
    product_code_type: str = None,
    ramdisk_id: str = None,
    reason: str = None,
    requester_id: str = None,
    reservation_id: str = None,
    root_device_name: str = None,
    root_device_type: str = None,
    source_dest_check: bool = None,
    spot_instance_request_id: str = None,
    state_reason_code: str = None,
    state_reason_message: str = None,
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    tags: Mapping = None,
    tag_key: str = None,
    tenancy: str = None,
    virtualization_type: str = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single instance.
    Can also be used to determine if an instance exists.

    The following paramers are translated into filters to refine the lookup:

    :param str affinity: The affinity setting for an instance running on a Dedicated
      Host. Allowed values: ``default``, ``host``.
    :param str architecture: The instance architecture. Allowed values: ``i386``,
      ``x86_64``, ``arm64``.
    :param str availability_zone: The Availability Zone of the instance.
    :param datetime block_device_attach_time: The attach time for an EBS volume
      mapped to the instance.
    :param bool block_device_delete_on_termination: Indicate whether the EBS volume
      is deleted on instance termination.
    :param str block_device_name: The device name specified in the block device mapping.
      For example: ``/dev/sdh`` or ``xvdh``.
    :param str block_device_status: The status for the EBS volume. Allowed values:
      ``attaching``, ``attached``, ``detaching``, ``detached``.
    :param str block_device_volume_id: The volume ID of the EBS volume.
    :param dict block_device_volume_lookup: Any kwargs that :py:func:`lookup_volume`
      accepts. Used to lookup ``block_device_volume_id``.
    :param str dns_name: The public DNS name of the instance.
    :param str group_id: [EC2-Classic] The ID of the security group for the instance.
    :param str group_name: [EC2-Classic] The name of the security group for the instance.
    :param bool hibernation_configured: Indicates whether the instance is enabled
      for hibernation.
    :param str host_id: The ID of the Dedicated Host on which the instance is running,
      if applicable.
    :param str hypervisor: The hypervisor type of the instance. Allowed values:
      ``ovm``, ``xen``. The value ``xen`` is used for both Xen and Nitro hypervisors.
    :param str iam_instance_profile_arn: The ARN of the instance profile associated
      with the instance.
    :param str image_id: The ID of the image used to launch the instance.
    :param dict image_lookup: Any kwargs that :py:func:`lookup_image` accepts.
      Used to lookup ``image_id``.
    :param str instance_id: The ID of the instance.
    :param str instance_lifecycle: Indicates whether this is a Spot instance or
      a Scheduled Instance. Allowed values: ``spot``, ``scheduled``.
    :param int instance_state_code: The state of the instance, as a 16-bit unsigned
      integer. The high byte is used for internal purposes and should be ignored.
      The low byte is set based on the state represented. The valid values are:
      0 (pending), 16 (running), 32 (shutting-down), 48 (terminated), 64 (stopping),
      and 80 (stopped).
    :param str instance_state_name: The state of the instance. Allowed values:
      ``pending``, ``running``, ``shutting_down``, ``terminated``, ``stopping``,
      ``stopped``.
    :param str instance_type: The type of the instance (for example ``t2.micro``).
    :param str instance_group_id: The ID of the security group for the instance.
    :param str instance_group_name: The name of the security group for the instance.
    :param str ip_address: The public IPv4 address of the instance.
    :param str kernel_id: The kernel ID.
    :param str key_name: The name of the key pair used when the instance was launched.
    :param int launch_index: When launching multiple instances, this is the index
      for the instance in the launch group (for example: 0, 1, 2, ...).
    :param datetime launch_time: The time when the instance was launched.
    :param str metadata_http_tokens: The metadata request authorization state.
      Allowed values: ``optional``, ``required``.
    :param int metadata_http_hop_limit: The http metadata request put response
      hop limit. Allowed values: 1 to 64.
    :param bool metadata_http_enabled: Indicates whether metadata access on http
      endpoint is enabled.
    :param bool monitoring_state: Indicates whether detailed monitoring is enabled.
    :param str network_interface_addresses_private_ip_address: The private IPv4
      address associated with the network interface.
    :param bool network_interface_addresses_primary: Specifies whether the IPv4
      address of the network interface is the primary private IPv4 address.
    :param str network_interface_addresses_association_public_ip: The ID of the
      association of an Elastic IP address (IPv4) with a network interface.
    :param str network_interface_addresses_association_ip_owner_id: The owner ID
      of the private IPv4 address associated with the network interface.
    :param str network_interface_association_public_ip: The address of the Elastic
      IP address (IPv4) associated with the network interface.
    :param str network_interface_association_ip_owner_id: The owner ID of Elastic
      IP address (Ipv4) associated with the network interface.
    :param str network_interface_association_allocation_id: The allocation ID returned
      when you allocated the Elastic IP address (IPv4) for your network interface.
    :param str network_interface_association_id: The association ID returned when
      the network interface was associated with an IPv4 address.
    :param str network_interface_attachment_id: The ID of the interface attachment.
    :param str network_interface_attachment_instance_id: The ID of the instance
      to which the network interface is attached.
    :param str network_interface_attachment_instance_owner_id: The owner ID of the
      instance to which the network interface is attached.
    :param int network_interface_attachment_device_index: The device index to which
      the network interface is attached.
    :param str network_interface_attachment_status: The status of the attachment.
      Allowed values: ``attaching``, ``attached``, ``detaching``, ``detached``.
    :param datetime network_interface_attachment_attach_time: The time that the
      network interface was attached to an instance.
    :param bool network_interface_attachment_delete_on_termination: Specifies whether
      the attachment is deleted when an instance is terminated.
    :param str network_interface_availability_zone: The Availability Zone for the
      network interface.
    :param str network_interface_description: The description of the network interface.
    :param str network_interface_group_id: The ID of a security group associated
      with the network interface.
    :param str network_interface_group_name: The name of a security group associated
      with the network interface.
    :param str network_interface_ipv6_address: The IPv6 address associated with
      the network interface.
    :param str network_interface_mac_address: The MAC address of the network interface.
    :param str network_interface_id: The ID of the network interface.
    :param str network_interface_owner_id: The ID of the owner of the network interface.
    :param str network_interface_private_dns_name: The private DNS name of the
      network interface.
    :param str network_interface_requester_id: The requester ID for the network interface.
    :param bool network_interface_requester_managed: Indicates whether the network
      interrface is being managed by AWS.
    :param str network_interface_status: The status of the network interface.
      Allowed values: ``available``, ``in-use``.
    :param bool network_interface_source_dest_check: Whether the network interface
      performs source/destination checking. A value of ``True`` means that checking
      is enabled, and ``False`` means that checking is disabled. The value must
      be ``False`` for the network interface to perform network address translation
      (NAT) in your VPC.
    :param str network_interface_subnet_id: The ID of the subnet for the network interface.
    :param str network_interface_vpc_id: The ID of the VPC for the network interface.
    :param str owner_id: The AWS account ID of the instance owner.
    :param str placement_group_name: The name of the placement group for the instance.
    :param int placement_partition_number: The partition in which the instance is located.
    :param str platform: The platform. To list only Windows instances, use ``windows``.
    :param str private_dns_name: The private IPv4 DNS name of the instance.
    :param str private_ip_address: The private IPv4 address of the instance.
    :param str product_code: The product code associated with the AMI used to launch
      the instance.
    :param str product_code_type: The type of product code.
      Allowed values: ``devpay``, ``marketplace``.
    :param str ramdisk_id: The RAM disk ID.
    :param str reason: The reason for the current state of the instance (for example,
      shows "User Initiated [date]" when you stop or terminate the instance).
      Similar to the ``state_reason_code`` filter.
    :param str requester_id: The ID of the entity that launched the instance on
      your behalf (for example, AWS Management Console, Auto Scaling, and so on).
    :param str reservation_id: The ID of the instance's reservation. A reservation
      ID is created any time you launch an instance. A reservation ID has a one-to-one
      relationship with an instance launch request, but can be associated with
      more than one instance if you launch multiple instances using the same launch
      request. For example, if you launch one instance, you get one reservation ID.
      If you launch ten instances using the same launch request, you also get one
      reservation ID.
    :param str root_device_name: The device name of the root device volume.
      For example ``/dev/sda1``.
    :param str root_device_type: The type of the root device volume.
      Allowed values: ``ebs``, ``instance-store``.
    :param bool source_dest_check: Indicates whether the instance performs source/destination
      checking. A value of true means that checking is enabled, and false means
      that checking is disabled. The value must be false for the instance to perform
      network address translation (NAT) in your VPC.
    :param str spot_instance_request_id: The ID of the Spot Instance request.
    :param str state_reason_code: The reason code for the state change.
    :param str state_reason_message: A message that describes the state change.
    :param str subnet_id: The ID of the subnet for the instance.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str tenancy: The tenancy of an instance. Allowed values: ``dedicated``,
      ``default``, ``host``.
    :param str virtualization_type: The virtualization type of the instance.
      Allowed values: ``paravirtual``, ``hvm``.
    :param str vpc_id: The ID for the VPC that the instance is running on.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param dict filters: Dict with filters to identify the instance.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_instance``-call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    if filters is None:
        filters = {}
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "image",
            "kwargs": image_lookup or {"image_id": image_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "volume",
            "kwargs": block_device_volume_lookup
            or {"volume_id": block_device_volume_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup or {"vpc_id": vpc_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        block_device_volume_id = res.get("volume")
        image_id = res.get("image")
        subnet_id = res.get("subnet")
        vpc_id = res.get("vpc")
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "affinity": affinity,
                "architecture": architecture,
                "availability-zone": availability_zone,
                "block-device-mapping.attach-time": block_device_attach_time,
                "block-device-mapping.delete-on-termination": block_device_delete_on_termination,
                "block-device-mapping.device-name": block_device_name,
                "block-device-mapping.status": block_device_status,
                "block-device-mapping.volume-id": block_device_volume_id,
                "dns-name": dns_name,
                "group-id": group_id,
                "group-name": group_name,
                "hibernation-options.configured": hibernation_configured,
                "host-id": host_id,
                "hypervisor": hypervisor,
                "iam-instance-profile.arn": iam_instance_profile_arn,
                "image-id": image_id,
                "instance-id": instance_id,
                "instance-lifecycle": instance_lifecycle,
                "instance-state-code": instance_state_code,
                "instance-state-name": instance_state_name,
                "instance-type": instance_type,
                "instance.group-id": instance_group_id,
                "instance.group-name": instance_group_name,
                "ip-address": ip_address,
                "kernel-id": kernel_id,
                "key-name": key_name,
                "launch-index": launch_index,
                "launch-time": launch_time,
                "metadata-options.http-tokens": metadata_http_tokens,
                "metadata-options.http-put-response-hop-limit": metadata_http_hop_limit,
                "metadata-options.http-endpoint": metadata_http_enabled,
                "monitoring-state": monitoring_state,
                "network-interface.addresses.private-ip-address": network_interface_addresses_private_ip_address,
                "network-interface.addresses.primary": network_interface_addresses_primary,
                "network-interface.addresses.association.public-ip": network_interface_addresses_association_public_ip,
                "network-interface.addresses.association.ip-owner-id": network_interface_addresses_association_ip_owner_id,
                "network-interface.association.public-ip": network_interface_association_public_ip,
                "network-interface.association.ip-owner-id": network_interface_association_ip_owner_id,
                "network-interface.association.allocation-id": network_interface_association_allocation_id,
                "network-interface.association.association-id": network_interface_association_id,
                "network-interface.attachment.attachment_id": network_interface_attachment_id,
                "network-interface.attachment.instance-id": network_interface_attachment_instance_id,
                "network-interface.attachment.instance-owner-id": network_interface_attachment_instance_owner_id,
                "network-interface.attachment.device-index": network_interface_attachment_device_index,
                "network-interface.attachment.status": network_interface_attachment_status,
                "network-interface.attachment.attach-time": network_interface_attachment_attach_time,
                "network-interface.attachment.delete-on-termination": network_interface_attachment_delete_on_termination,
                "network-interface.availability-zone": network_interface_availability_zone,
                "network-interface.description": network_interface_description,
                "network-interface.group-id": network_interface_group_id,
                "network-interface.group-name": network_interface_group_name,
                "network-interface.ipv6-addresses.ipv6-address": network_interface_ipv6_address,
                "network-interface.mac-address": network_interface_mac_address,
                "network-interface.network-interface-id": network_interface_id,
                "network-interface.owner-id": network_interface_owner_id,
                "network-interface.private-dns-name": network_interface_private_dns_name,
                "network-interface.requester-id": network_interface_requester_id,
                "network-interface.requester-managed": network_interface_requester_managed,
                "network-interface.status": network_interface_status,
                "network-interface.source-dest-check": network_interface_source_dest_check,
                "network-interface.subnet-id": network_interface_subnet_id,
                "network-interface.vpc-id": network_interface_vpc_id,
                "owner-id": owner_id,
                "placement-group-name": placement_group_name,
                "placement-partition-number": placement_partition_number,
                "platform": platform,
                "private-dns-name": private_dns_name,
                "private-ip-address": private_ip_address,
                "product-code": product_code,
                "product-code-type": product_code_type,
                "ramdisk-id": ramdisk_id,
                "reason": reason,
                "requester-id": requester_id,
                "reservation-id": reservation_id,
                "root-device-name": root_device_name,
                "root-device-type": root_device_type,
                "source-dest-check": source_dest_check,
                "spot-instance-request-id": spot_instance_request_id,
                "state-reason-code": state_reason_code,
                "state-reason-message": state_reason_message,
                "subnet-id": subnet_id,
                "tag-key": tag_key,
                "tenancy": tenancy,
                "virtualization-type": virtualization_type,
                "vpc-id": vpc_id,
            }
        )
    )
    params.update(
        {"ClientToken": hashlib.sha1(json.dumps(params).encode("utf8")).hexdigest()}
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "instance",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_internet_gateway(
    internet_gateway_id: str = None,
    internet_gateway_name: str = None,
    attachment_state: str = None,
    attachment_vpc_id: str = None,
    attachment_vpc_lookup: Mapping = None,
    owner_id: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single Internet gateway.
    Can also be used to determine if an Internet gateway exists.

    The following paramers are translated into filters to refine the lookup:

    :param str internet_gateway_id: ID of the Internet gateway.
    :param str internet_gateway_name: The ``Name``-tag of the Internet gateway.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str attachment_state: The current state of the attachment between the
      gateway and the VPC (``available``). Present only if a VPC is attached.
    :param str attachment_vpc_id: The ID of an attached VPC.
    :param dict attachment_vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``attachment_vpc_id``.
    :param str owner_id: The ID of the AWS account that owns the internet gateway.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the Internet gateway.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_internet_gateways``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_internet_gateways
    """
    if attachment_vpc_lookup:
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "vpc",
                "kwargs": attachment_vpc_lookup,
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            attachment_vpc_id = res["result"].get("vpc")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "attachment.state": attachment_state,
                "attachment.vpc-id": attachment_vpc_id,
                "internet-gateway-id": internet_gateway_id,
                "owner-id": owner_id,
                "tag-key": tag_key,
                "tag:Name": internet_gateway_name,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "internet_gateway",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_key_pair(
    key_pair_id: str = None,
    fingerprint: str = None,
    key_name: str = None,
    tag_key: str = None,
    tags: Mapping = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single key pair.
    Can also be used to determine if a key pair exists.

    The following paramers are translated into filters to refine the lookup:

    :param str key_pair_id: The ID of the key pair.
    :param str fingerprint: The fingerprint of the key pair.
    :param str key_name: The name of the key pair.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict tags: The tags to filter on.
    :param dict filters: Dict with filters to identify the key pair.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_key_pairs``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "key-pair-id": key_pair_id,
                "fingerprint": fingerprint,
                "key-name": key_name,
                "tag-key": tag_key,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "key_pair",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_local_gateway(
    local_gateway_id: str = None,
    local_gateway_name: str = None,
    route_table_id: str = None,
    route_table_lookup: Mapping = None,
    association_id: str = None,
    virtual_interface_group_id: str = None,
    outpost_arn: str = None,
    state: str = None,
    tags: Mapping = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single local gateway.
    Can also be used to determine if a local gateway exists.

    The following paramers are translated into filters to refine the lookup:

    :param str local_gateway_id: The ID of a local gateway.
    :param str local_gateway_name: The ``Name``-tag of a local gateway.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str route_table_id: The ID of the local gateway route table.
    :param dict route_table_lookup: Any kwargs that :py:func:`lookup_route_table`
      accepts. Used to lookup ``route_table_id``.
    :param str association_id: The ID of the association.
    :param str virtual_interface_group_id: The ID of the virtual interface group.
    :param str outpost_arn: The Amazon Resouce Name of the Outpost.
    :param str state: The state of the association.
    :param dict tags: Any tags to filter on.
    :param dict filters: Dict with filters to identify the local gateway.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_local_gateways``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "route_table",
            "kwargs": route_table_lookup or {"route_table_id": route_table_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        route_table_id = res["result"].get("route_table")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "tag:Name": local_gateway_name,
                "local-gateway-id": local_gateway_id,
                "local-gateway-route-table-id": route_table_id,
                "local-gateway-route-table-virtual-interface-group-association-id": association_id,
                "local-gateawy-route-table-virtual-interface-group-id": virtual_interface_group_id,
                "outpost-arn": outpost_arn,
                "state": state,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "local_gateway",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_managed_prefix_list(
    owner_id: str = None,
    prefix_list_id: str = None,
    prefix_list_name: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single managed prefix list.
    Can also be used to determine if a managed prefix list exists.

    The following paramers are translated into filters to refine the lookup:

    :param str owner_id: The ID of the prefix list owner.
    :param str prefix_list_id: The ID of the prefix list.
    :param str prefix_list_name: The name of the prefix list.
    :param dict filters: Dict with filters to identify the managed prefix list.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_managed_prefix_lists``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "owner-id": owner_id,
                "prefix-list-id": prefix_list_id,
                "prefix-list-name": prefix_list_name,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "managed_prefix_list",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_nat_gateway(
    nat_gateway_id: str = None,
    nat_gateway_name: str = None,
    state: str = None,
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    tags: Mapping = None,
    tag_key: str = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single NAT gateway.
    Can also be used to determine if a NAT gateway exists.

    The following paramers are translated into filters to refine the lookup:

    :param str nat_gateway_id: ID of the NAT gateway.
    :param str nat_gateway_name: The ``Name``-tag of the NAT gateway.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str state: The state of the NAT gateway. Allowed values:
      ``pending``, ``failed``, ``available``, ``deleting``, ``deleted``.
    :param str subnet_id: The ID of the subnet in which the NAT gateway resides.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
      If ``vpc_id`` or ``vpc_lookup`` are provided, the resulting VPC ID will
      be used in the lookup of the subnet.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str vpc_id: The ID of the VPC in which the NAT gateway resides.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param dict filters: Dict with filters to identify the NAT gateway.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_nat_gateways``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_nat_gateways
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup or {"vpc_id": vpc_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        subnet_id = res.get("subnet")
        vpc_id = res.get("vpc")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "nat-gateway-id": nat_gateway_id,
                "state": state,
                "subnet-id": subnet_id,
                "vpc-id": vpc_id,
                "tag-key": tag_key,
                "tag:Name": nat_gateway_name,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "nat_gateway",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_network_acl(
    network_acl_id: str = None,
    network_acl_name: str = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    association_id: str = None,
    association_network_acl_id: str = None,
    association_subnet_id: str = None,
    association_subnet_lookup: Mapping = None,
    default: bool = None,
    entry_cidr: str = None,
    entry_icmp_code: int = None,
    entry_icmp_type: int = None,
    entry_ipv6_cidr: str = None,
    entry_port_range_from: int = None,
    entry_port_range_to: int = None,
    entry_protocol: str = None,
    entry_rule_action: str = None,
    entry_rule_number: int = None,
    filters: Mapping = None,
    owner_id: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single network ACL.
    Can also be used to determine if a network ACL exists.

    The following paramers are translated into filters to refine the lookup:

    :param str network_acl_id: ID of the network ACL.
    :param str network_acl_name: The ``Name``-tag of the network ACL.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str vpc_id: The ID of the VPC for the network ACL.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param str association_id: The ID of an association ID for the ACL.
    :param str association_network_acl_id: The ID of the network ACL involved in
      the association.
    :param str assocation_subnet_id: The ID of the subnet involved in the association.
    :param dict association_subnet_lookup: Any kwargs that :py:func:`lookup_subnet`
      accepts. Used to lookup ``association_subnet_id``.
    :param bool default: Indicates whether the ACL is the default network ACL for
      the VPC.
    :param str entry_cidr: The IPv4 CIDR range specified in the entry.
    :param int entry_icmp_code: The ICMP code specified in the entry, if any.
    :param int entry_icmp_type: The ICMP type specified in the entry, if any.
    :param str entry_ipv6_cidr: The IPv6 CIDR range specified in the entry.
    :param int entry_port_range_from: The start of the port range specified in the entry.
    :param int entry_port_range_to: The end of the port range specified in the entry.
    :param str entry_protocol: The protocol specified in the entry.
      Allowed values: tcp, udp, icmp or a protocol number.
    :param str entry_rule_action: Allows or denies the matching traffic.
      Allowed values: allow, deny.
    :param str entry_rule_number: The number of an entry (in other words, rule)
      in the set of ACL entries.
    :param str owner_id:  The ID of the AWS account that owns the network ACL.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the network ACL.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_network_acls``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_network_acls
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": association_subnet_lookup or {"subnet_id": association_subnet_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup or {"vpc_id": vpc_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        association_subnet_id = res.get("subnet")
        vpc_id = res.get("vpc")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "tag:Name": network_acl_name,
                "association.association-id": association_id,
                "association.network-acl-id": association_network_acl_id,
                "association.subnet-id": association_subnet_id,
                "default": default,
                "entry.cidr": entry_cidr,
                "entry.icmp.code": entry_icmp_code,
                "entry.icmp.type": entry_icmp_type,
                "entry.ipv6-cidr": entry_ipv6_cidr,
                "entry.port-range.from": entry_port_range_from,
                "entry.port-range.to": entry_port_range_to,
                "entry.protocol": entry_protocol,
                "entry.rule-action": entry_rule_action,
                "entry.rule-number": entry_rule_number,
                "network-acl-id": network_acl_id,
                "owner-id": owner_id,
                "tag-key": tag_key,
                "vpc_id": vpc_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "network_acl",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_network_interface(
    addresses_private_ip_address: str = None,
    addresses_primary: bool = None,
    addresses_association_public_ip: str = None,
    addresses_association_owner_id: str = None,
    association_association_id: str = None,
    association_allocation_id: str = None,
    association_ip_owner_id: str = None,
    association_public_ip: str = None,
    association_public_dns_name: str = None,
    attachment_id: str = None,
    attachment_attach_time: datetime = None,
    attachment_delete_on_termination: bool = None,
    attachment_device_index: str = None,
    attachment_instance_id: str = None,
    attachment_instance_owner_id: str = None,
    attachment_status: str = None,
    availability_zone: str = None,
    description: str = None,
    group_id: str = None,
    group_name: str = None,
    ipv6_address: str = None,
    mac_address: str = None,
    network_interface_id: str = None,
    owner_id: str = None,
    private_ip_address: str = None,
    private_dns_name: str = None,
    requester_id: str = None,
    requester_managed: bool = None,
    source_dest_check: bool = None,
    status: str = None,
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    tags: Mapping = None,
    tag_key: str = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single network interface.
    Can also be used to determine if a network interface exists.

    The following paramers are translated into filters to refine the lookup:

    :param str addresses_private_ip_address: The private IPv4 addresses associated
      with the network interface.
    :param bool addresses_primary: Whether the private IPv4 address is the primary
      IP address associated with the network interface.
    :param str addresses_association_public_ip: The association ID returned when
      the network interface was associated with the Elastic IP address (IPv4).
      (Note, this doesn't look like the correct description. Maybe bug@aws?)
    :param str addresses_association_owner_id: The owner ID of the addresses associated
      with the network interface.
    :param str association_association_id: The association ID returned when the
      network interface was associated with an IPv4 address.
    :param str association_allocation_id: The allocation ID returned when you allocated
      the Elastic IP address (IPv4) for your network interface.
    :param str association_ip_owner_id: The owner of the Elastic IP address associated
      with the network interface.
    :param str association_public_ip: The address of the Elastic IP address bound
      to the network interface.
    :param str association_public_dns_name: The public DNS name for the network interface (IPv4).
    :param str attachment_id: The ID of the interface attachment.
    :param datetime attachment_attach_time: The time that the network interface
      was attached to an instance.
    :param bool attachment_delete_on_termination: Indicates whether the attachment
      is deleted when an instance is terminated.
    :param str attachment_device_index: The device index to which the network
      interface is attached.
    :param str attachment_instance_id: The ID of the instance to which the network
      interface is attached.
    :param str attachment_instance_owner_id: The owner ID of the instance to which
      the network interface is attached.
    :param attachment_status: The status of the attachment. Allowed values:
      ``attaching``, ``attached``, ``detaching``, ``detached``.
    :param str availability_zone: The Availability Zone of the network interface.
    :param str description: The description of the network interface.
    :param str group_id: The ID of a security group associated with the network interface.
    :param str group_name: The name of a security group associated with the network interface.
    :param str ipv6_address: An ipv6_address associated with the network interface.
    :param str mac_address: The MAC address of the network interface.
    :param str network_interface_id: The ID of the network interface.
    :param str owner_id: The AWS account ID of the network interface owner.
    :param str private_ip_address: The private IPv4 address(es) of the network interface.
    :param str private_dns_name: The private DNS name of the network interface (IPv4).
    :param str requester_id: The ID of the entity that launched the instance on
      your behalf (for example, AWS Management Console, Auto Scaling, and so on).
    :param bool requester_managed: Indicates whether the network interface is being
      managed by an AWS service.
    :param bool source_dest_check: Indicates whether the network interface performs
      source/destination checking. A value of ``True`` means checking is enabled,
      and ``False`` means checking is disabled. The value must be ``False`` for
      the network interface to perform network address translation (NAT) in your VPC.
    :param str status: The status of the network interface. If the network interface
      is not attached to an instance, the status is ``available``; if a network
      interface is attached to an instance the status is ``in-use``.
    :param str subnet_id: The ID of the subnet for the network interface.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str vpc_id: The ID of the VPC for the network interface.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param dict filters: Dict with filters to identify the network interface.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_network_interfaces``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup or {"vpc_id": vpc_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        subnet_id = res.get("subnet")
        vpc_id = res.get("vpc")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "addresses.private-ip-address": addresses_private_ip_address,
                "addresses.primary": addresses_primary,
                "addresses.association.public-ip": addresses_association_public_ip,
                "addresses.association.owner-id": addresses_association_owner_id,
                "association.association-id": association_association_id,
                "association.allocation-id": association_allocation_id,
                "association.ip-owner-id": association_ip_owner_id,
                "association.public-ip": association_public_ip,
                "association.public-dns-name": association_public_dns_name,
                "attachment.attachment-id": attachment_id,
                "attachment.attach-time": attachment_attach_time,
                "attachment.delete-on-termination": attachment_delete_on_termination,
                "attachment.device-index": attachment_device_index,
                "attachment.instance-id": attachment_instance_id,
                "attachment.instance-owner-id": attachment_instance_owner_id,
                "attachment.status": attachment_status,
                "availability-zone": availability_zone,
                "description": description,
                "group-id": group_id,
                "group-name": group_name,
                "ipv6-addresses.ipv6-address": ipv6_address,
                "mac-address": mac_address,
                "network-interface-id": network_interface_id,
                "owner-id": owner_id,
                "private-ip-address": private_ip_address,
                "private-dns-name": private_dns_name,
                "requester-id": requester_id,
                "requester-managed": requester_managed,
                "source-dest-check": source_dest_check,
                "status": status,
                "subnet-id": subnet_id,
                "tag-key": tag_key,
                "vpc-id": vpc_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "network_interface",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_route_table(
    route_table_id: str = None,
    route_table_name: str = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    association_id: str = None,
    association_route_table_id: str = None,
    association_subnet_id: str = None,
    association_subnet_lookup: Mapping = None,
    association_main: str = None,
    owner_id: str = None,
    route_destination_cidr_block: str = None,
    route_destination_ipv6_cidr_block: str = None,
    route_destination_prefix_list_id: str = None,
    route_destination_prefix_list_lookup: Mapping = None,
    route_egress_only_internet_gateway_id: str = None,
    route_egress_only_internet_gateway_lookup: Mapping = None,
    route_gateway_id: str = None,
    route_gateway_lookup: Mapping = None,
    route_instance_id: str = None,
    route_instance_lookup: Mapping = None,
    route_nat_gateway_id: str = None,
    route_nat_gateway_lookup: Mapping = None,
    route_transit_gateway_id: str = None,
    route_transit_gateway_lookup: Mapping = None,
    route_origin: str = None,
    route_state: str = None,
    route_vpc_peering_connection_id: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single route table.
    Can also be used to determine if a route table exists.

    The following paramers are translated into filters to refine the lookup:

    :param str route_table_id: ID of the route table.
    :param str route_table_name: The ``Name``-tag of the route table.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str vpc_id: The ID of the VPC for the route table.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param str association_id: The ID of an association ID for the route table.
    :param str association_route_table_id: The ID of the route table involved in
      the association.
    :param str association_subnet_id: The ID of the subnet involved in the association.
    :param dict association_subnet_lookup: Any kwargs that :py:func:`lookup_subnet`
      accepts. Used to lookup ``association_subnet_id``.
    :param bool association_main: Indicates whether the route table is the main
      route table for the VPC. Route tables that do not have an association ID
      are not returned in the response.
    :param str owner_id: The ID of the AWS account that owns the route table.
    :param str route_destination_cidr_block: The IPv4 CIDR range specified in a
      route in the table.
    :param str route_destination_ipv6_cidr_block: The IPv6 CIDR range specified
      in a route in the route table.
    :param str route_destination_prefix_list_id: The ID (prefix) of the AWS service
      specified in a route in the table.
    :param dict route_destination_prefix_list_lookup: Any kwargs that :py:fync:`lookup_managed_prefix_list`
      accepts. Used to lookup ``route_destination_prefix_list_id``.
    :param str route_egress_only_internet_gateway_id:  The ID of an egress-only
      Internet gateway specified in a route in the route table.
    :param dict route_egress_only_internet_gateway_lookup: Any kwargs that
      :py:func:`lookup_egress_only_internet_gateway` accepts. Used to lookup
      ``route_egress_only_internet_gateway_id``.
    :param str route_gateway_id: The ID of a gateway specified in a route in the table.
    :param dict route_gateway_lookup: Any kwargs that :py:func:`lookup_internet_gateway`
      or :py:func:`lookup_vpn_gateway` accepts. Used to lookup ``route_gateway_id``.
    :param str route_instance_id: The ID of an instance specified in a route in
      the table.
    :param dict route_instance_lookup: Any kwargs that :py:func:`lookup_instance`
      accepts. Used to lookup ``route_instance_id``.
    :param str route_nat_gateway_id: The ID of a NAT gateway specified in a route
      in the table.
    :param dict route_nat_gateway_lookup: Any kwargs that :py:func:`lookup_nat_gateway`
      accepts. Used to lookup ``route_nat_gateway_id``.
    :param str route_transit_gateway_id: The ID of a transit gateway specified in
      a route in the table.
    :param dict route_transit_gateway_lookup: Any kwargs that :py:func:`lookup_transit_gateway`
      accepts. Used to lookup ``route_transit_gateway_id``.
    :param str route_origin: Describes how the route was created. ``CreateRouteTable``
      indicates that the route was automatically created when the route table
      was created; ``CreateRoute`` indicates that the route was manually added
      to the route table; ``EnableVgwRoutePropagation`` indicates that the route
      was propagated by route propagation.
    :param str route_state: The state of a route in the route table. Allowed values:
      ``active``, ``blackhole``. The blackhole state indicates that the route's
      target isn't available (for example, the specified gateway isn't attached
      to the VPC, the specified NAT instance has been terminated, and so on).
    :param str route_vpc_peering_connection_id: The ID of a VPC peering connection
      specified in a route in the table.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the route table.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_route_tables``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_route_tables
    """
    # Amazon decided, in their wisdom, to let ``gateway`` be an IGW *or* a VPN gateway
    # So we need to look this up manually
    if route_gateway_id is None and route_gateway_lookup is not None:
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "internet_gateway",
                "kwargs": route_gateway_lookup
                or {"internet_gateway_id": route_gateway_id},
                "required": False,
            },
            {
                "service": "ec2",
                "name": "vpn_gateway",
                "kwargs": route_gateway_lookup or {"vpn_gateway_id": route_gateway_id},
                "required": False,
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" not in res:
                route_gateway_id = res["result"].get(
                    "internet_gateway", res["result"].get("vpn_gateway")
                )
            if route_gateway_id is None:
                if "error" in res:
                    return res
                return {
                    "error": (
                        "route_gateway_lookup was provided, but no single Internet "
                        "gateway or virtual private gateway matched."
                    )
                }
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": association_subnet_lookup or {"subnet_id": association_subnet_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "managed_prefix_list",
            "kwargs": route_destination_prefix_list_lookup
            or {"prefix_list_id": route_destination_prefix_list_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "egress_only_internet_gateway",
            "kwargs": route_egress_only_internet_gateway_lookup
            or {
                "egress_only_internet_gateway_id": route_egress_only_internet_gateway_id
            },
            "required": False,
        },
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": route_instance_lookup or {"instacce_id": route_instance_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "nat_gateway",
            "kwargs": route_nat_gateway_lookup
            or {"nat_gateway_id": route_nat_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "transit_gateway",
            "kwargs": route_transit_gateway_lookup
            or {"transit_gateway_id": route_transit_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup or {"vpc_id": vpc_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        association_subnet_id = res.get("subnet")
        route_destination_prefix_list_id = res.get("managed_prefix_list")
        route_egress_only_internet_gateway_id = res.get("egress_only_internet_gateway")
        route_instance_id = res.get("instance")
        route_nat_gateway_id = res.get("nat_gateway")
        route_transit_gateway_id = res.get("transit_gateway")
        vpc_id = res.get("vpc")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "tag:Name": route_table_name,
                "association.route-table-association-id": association_id,
                "association.route-table-id": association_route_table_id,
                "association.subnet-id": association_subnet_id,
                "association.main": association_main,
                "owner-id": owner_id,
                "route-table-id": route_table_id,
                "route.destination-cidr-block": route_destination_cidr_block,
                "route.destination-ipv6-cidr-block": route_destination_ipv6_cidr_block,
                "route.destination-prefix-list-id": route_destination_prefix_list_id,
                "route.egress-only-internet-gateway-id": route_egress_only_internet_gateway_id,
                "route.gateway-id": route_gateway_id,
                "route.instance-id": route_instance_id,
                "route.nat-gateway-id": route_nat_gateway_id,
                "route.transit-gateway-id": route_transit_gateway_id,
                "route.origin": route_origin,
                "route.state": route_state,
                "route.vpc-peering-connection-id": route_vpc_peering_connection_id,
                "tag-key": tag_key,
                "vpc-id": vpc_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "route_table",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_security_group(
    group_id: str = None,
    group_name: str = None,
    description: str = None,
    egress_ip_permission_cidr: str = None,
    egress_ip_permission_from_port: int = None,
    egress_ip_permission_group_id: str = None,
    egress_ip_permission_group_name: str = None,
    egress_ip_permission_ipv6_cidr: str = None,
    egress_ip_permission_prefix_list_id: str = None,
    egress_ip_permission_protocol: str = None,
    egress_ip_permission_to_port: int = None,
    egress_ip_permission_user_id: str = None,
    ip_permission_cidr: str = None,
    ip_permission_from_port: int = None,
    ip_permission_group_id: str = None,
    ip_permission_group_name: str = None,
    ip_permission_ipv6_cidr: str = None,
    ip_permission_prefix_list_id: str = None,
    ip_permission_protocol: str = None,
    ip_permission_to_port: int = None,
    ip_permission_user_id: str = None,
    owner_id: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single security group.
    Can also be used to determine if a security group exists.

    The following paramers are translated into filters to refine the lookup:

    :param str group_id: The ID of the security group.
    :param str group_name: The name of the security group.
    :param str description: The description of the security group.
    :param str egress_ip_permission_cidr: An IPv4 CIDR block for an outbound
      security group rule.
    :param int egress_ip_permission_from_port: For an outbound rule, the start
      of port range for the TCP and UDP protocols, or an ICMP type number.
    :param str egress_ip_permission_group_id: The ID of a security group that
      has been referenced in an outbound security group rule.
    :param str egress_ip_permission_group_name: The name of a security group
      that has been referenced in an outbound security group rule.
    :param str egress_ip_permission_ipv6_cidr: An IPv6 CIDR block for an outbound
      security group rule.
    :param str egress_ip_permission_prefix_list_id: The ID of a prefix list to
      which a security group rule allows outbound access.
    :param str egress_ip_permission_protocol: The IP protocol for an outbound
      security group rule. Allowed values: tcp, udp, icmp or a protocol number.
    :param int egress_ip_permission_to_port: For an outbound rule, the end of
      port range for the TCP and UDP protocols, or an ICMP code.
    :param str egress_ip_permission_user_id: The ID of an AWS account that has
      been referenced in an outbound security group rule.
    :param str ip_permission_cidr: An IPv4 CIDR block for an inbound security
      group rule.
    :param int ip_permission_from_port: For an inbound rule, the start of port
      range for the TCP and UDP protocols, or an ICMP type number.
    :param str ip_permission_group_id: The ID of a security group that has been
      referenced in an inbound security group rule.
    :param str ip_permission_group_name: The name of a security group that has
      been referenced in an inbound security group rule.
    :param str ip_permission_ipv6_cidr: An IPv6 CIDR block for an inbound security
      group rule.
    :param str ip_permission_prefix_list_id: The ID of a prefix list from which
      a security group rule allows inbound access.
    :param str ip_permission_protocol: The IP protocol for an inbound security
      group rule. Allowed values: tcp, udp, icmp or a protocol number.
    :param int ip_permission_to_port: For an inbound rule, the end of port range
      for the TCP and UDP protocols, or an ICMP code.
    :param str ip_permission_user_id: The ID of an AWS account that has been referenced
      in an inbound security group rule.
    :param str owner_id: The AWS account ID of the owner of the security group.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str vpc_id: The ID of the VPC specified when the security group was created.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param dict filters: Dict with filters to identify the security group.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_security_groups``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup or {"vpc_id": vpc_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        vpc_id = res["result"].get("vpc")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "description": description,
                "egress.ip-permission.cidr": egress_ip_permission_cidr,
                "egress.ip-permission.from-port": egress_ip_permission_from_port,
                "egress.ip-permission.group-id": egress_ip_permission_group_id,
                "egress.ip-permisison.group-name": egress_ip_permission_group_name,
                "egress.ip-permisison.ipv6-cidr": egress_ip_permission_ipv6_cidr,
                "egress.ip-permission.prefix-list-id": egress_ip_permission_prefix_list_id,
                "egress.ip-permisison.protocol": egress_ip_permission_protocol,
                "egress.ip-permission.to-port": egress_ip_permission_to_port,
                "egress.ip-permission.user-id": egress_ip_permission_user_id,
                "group-id": group_id,
                "group-name": group_name,
                "ip-permission.cidr": ip_permission_cidr,
                "ip-permission.from-port": ip_permission_from_port,
                "ip-permission.group-id": ip_permission_group_id,
                "ip-permission.group-name": ip_permission_group_name,
                "ip-permission.ipv6-cidr": ip_permission_ipv6_cidr,
                "ip-permission.prefix-list-id": ip_permission_prefix_list_id,
                "ip-permissson.protocol": ip_permission_protocol,
                "ip-permission.to-port": ip_permission_to_port,
                "ip-permission.user-id": ip_permission_user_id,
                "owner-id": owner_id,
                "tag-key": tag_key,
                "vpc-id": vpc_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "security_group",
        filters=filters,
        tags=tags,
        client=client,
    )


@_arguments_to_list("owner_ids", "restorable_by_user_ids")
def lookup_snapshot(
    description: str = None,
    encrypted: bool = None,
    owner_ids: Union[str, Iterable[str]] = None,
    progress: str = None,
    restorable_by_user_ids: Union[str, Iterable[str]] = None,
    snapshot_id: str = None,
    start_time: datetime = None,
    status: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    volume_id: str = None,
    volume_lookup: str = None,
    volume_size: int = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single snapshot.
    Can also be used to determine if a snapshot exists.

    The following paramers are translated into filters to refine the lookup:

    :param str description: A description of the snapshot.
    :param bool encrypted: Indicates whether the snapshot is encrypted.
    :type owner_ids: str or list(str)
    :param owner_ids: Scopes the results to snapshots with the specified
      owners. You can specify a combination of AWS account IDs, ``self``, and ``amazon``.
    :param str progress: The progress of the snapshot, as a percentage.
      For example, ``80%``.
    :type restorable_by_user_ids: str or list(str)
    :param restorable_by_user_ids: The IDs of the AWS accounts that
      can create volumes from the snapshot.
    :param str snapshot_id: The snapshot ID.
    :param datetime start_time: The time stamp when the snapshot was initiated.
    :param str status: The status of the snapshot. Allowed values: ``pending``,
      ``completed``, ``error``.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str volume_id: The ID of the volume the snapshot is for.
    :param dict volume_lookup: Any kwargs that :py:func:`lookup_volume` accepts.
      Used to lookup ``volume_id``.
    :param int volume_size: The size of the volume, in GiB.
    :param dict filters: Dict with filters to identify the snapshot.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_snapshots``-call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "volume",
            "kwargs": volume_lookup or {"volume_id": volume_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        volume_id = res["result"].get("volume")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "description": description,
                "encrypted": encrypted,
                "progress": progress,
                "snapshot-id": snapshot_id,
                "start-time": start_time,
                "status": status,
                "tag-key": tag_key,
                "volume-id": volume_id,
                "volume-size": volume_size,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "snapshot",
        filters=filters,
        tags=tags,
        client=client,
        OwnerIds=owner_ids,
        RestorableByUserIds=restorable_by_user_ids,
    )


def lookup_spot_instance_request(
    availability_zone_group: str = None,
    create_time: datetime = None,
    fault_code: str = None,
    fault_message: str = None,
    instance_id: str = None,
    launch_group: str = None,
    block_device_delete_on_termination: bool = None,
    block_device_name: str = None,
    block_device_snapshot_id: str = None,
    block_device_volume_size: int = None,
    block_device_volume_type: str = None,
    launch_group_id: str = None,
    launch_group_name: str = None,
    launch_image_id: str = None,
    launch_instance_type: str = None,
    launch_kernel_id: str = None,
    launch_key_name: str = None,
    launch_monitoring_enabled: bool = None,
    launch_ramdisk_id: str = None,
    launched_availability_zone: str = None,
    network_interface_addresses_primary: bool = None,
    network_interface_delete_on_termination: bool = None,
    network_interface_description: str = None,
    network_interface_device_index: int = None,
    network_interface_group_id: str = None,
    network_interface_id: str = None,
    network_interface_private_ip_address: str = None,
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    product_description: str = None,
    spot_instance_request_id: str = None,
    spot_price: float = None,
    state: str = None,
    status_code: int = None,
    status_message: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    request_type: str = None,
    valid_from: datetime = None,
    valid_until: datetime = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single spot instance request.
    Can also be used to determine if a spot instance request exists.

    The following paramers are translated into filters to refine the lookup:

    :param str availability_zone_group: The Availability Zone group.
    :param datetime create_time: The time stamp when the Spot Instance request
      was created.
    :param str fault_code: The fault code related to the request.
    :param str fault_message: The fault message related to the request.
    :param str instance_id: The ID of the instance that fulfilled the request.
    :param str launch_group: The Spot Instance launch group.
    :param bool launch_block_device_mapping_delete_on_termination: Indicates whether
      the EBS volume is deleted on instance termination.
    :param str block_device_name: The device name for the
      volume in the block device mapping (for example, ``/dev/sdh`` or ``xvdh``).
    :param str block_device_snapshot_id: The ID of the snapshot
      for the EBS volume.
    :param int block_device_volume_size: The size of the EBS volume, in GiB.
    :param str block_device_volume_type: The type of EBS volume:
      ``gp2`` for General Purpose SSD, ``io1`` for Provisioned IOPS SSD,
      ``st1`` for Throughput Optimized HDD, ``sc1`` for Cold HDD, or ``standard``
      for Magnetic.
    :param str launch_group_id: The ID of the security group for the instance.
    :param str launch_group_name: The name of the security group for the instance.
    :param str launch_image_id: The ID of the AMI.
    :param str launch_instance_type: The type of instance (for example, ``m3.medium``).
    :param str launch_kernel_id: The kernel ID.
    :param str launch_key_name: The name of the key pair the instance launched with.
    :param bool launch_monitoring_enabled: Whether detailed monitoring is enabled
      for the Spot Instance.
    :param str launch_ramdisk_id: The RAM disk ID.
    :param str launched_availability_zone: The Availability Zone in which the request
      is launched.
    :param bool network_interface_addresses_primary: Indicates whether the IP address
      is the primary private IP address.
    :param bool network_interface_delete_on_termination: Indicates whether the
      network interface is deleted when the instance is terminated.
    :param str network_interface_description: A description of the network interface.
    :param int network_interface_device_index: The index of the device for the
      network interface attachment on the instance.
    :param str network_interface_group_id: The ID of the security group associated
      with the network interface.
    :param str network_interface_id: The ID of the network interface.
    :param str network_interface_private_ip_address: The primary private IP address
      of the network interface.
    :param str subnet_id: The ID of the subnet for the instance.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
    :param str product_description: The product description associated with the
      instance. Allowed values: ``Linux/UNIX``, ``Windows``.
    :param str spot_instance_request_id: The Spot Instance request ID.
    :param float spot_price: The maximum hourly price for any Spot Instance launched
      to fulfill the request.
    :param str state: The state of the Spot Instance request. Allowed values:
      ``open``, ``active``, ``closed``, ``cancelled``, ``failed``.
    :param int status_code: The short code describing the most recent evaluation
      of your Spot Instance request.
    :param str status_message: The message explaining the status of the Spot Instance request.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str request_type: The type of Spot Instance request. Allowed values:
      ``one-time``, ``persistent``.
    :param datetime valid_from: The start date of the request.
    :param datetime valid_until: The end date of the request.
    :param dict filters: Dict with filters to identify the spot instance request.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_spot_instance_requests``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        subnet_id = res["result"].get("subnet")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "availability-zone-group": availability_zone_group,
                "create-time": create_time,
                "fault-code": fault_code,
                "fault-message": fault_message,
                "instance-id": instance_id,
                "launch-group": launch_group,
                "launch.block-device-mapping.delete-on-termination": block_device_delete_on_termination,
                "launch.block-device-mapping.device-name": block_device_name,
                "launch.block-device-mapping.snapshot-id": block_device_snapshot_id,
                "launch.block-device-mapping.volume-size": block_device_volume_size,
                "launch.block-device-mapping.volume-type": block_device_volume_type,
                "launch.group-id": launch_group_id,
                "launch.group-name": launch_group_name,
                "launch.image-id": launch_image_id,
                "launch.instance-type": launch_instance_type,
                "launch.kernel-id": launch_kernel_id,
                "launch.key-name": launch_key_name,
                "launch.monitoring-enabled": launch_monitoring_enabled,
                "launch.ramdisk-id": launch_ramdisk_id,
                "launched-availability-zone": launched_availability_zone,
                "network-interface.addresses.primary": network_interface_addresses_primary,
                "network-interface.delete-on-termination": network_interface_delete_on_termination,
                "network-interface.description": network_interface_description,
                "network-interface.device-index": network_interface_device_index,
                "network-interface.group-id": network_interface_group_id,
                "network-interface.network-interface-id": network_interface_id,
                "network-interface.private-ip-address": network_interface_private_ip_address,
                "network-interface.subnet-id": subnet_id,
                "product-description": product_description,
                "spot-instance-request-id": spot_instance_request_id,
                "spot-price": spot_price,
                "state": state,
                "status-code": status_code,
                "status-message": status_message,
                "tag-key": tag_key,
                "type": request_type,
                "valid-from": valid_from,
                "valid-until": valid_until,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "spot_instance_request",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_subnet(
    subnet_id: str = None,
    subnet_name: str = None,
    subnet_arn: str = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    availability_zone: str = None,
    availability_zone_id: str = None,
    available_ip_address_count: int = None,
    cidr_block: str = None,
    default_for_az: bool = None,
    ipv6_cidr_block: str = None,
    ipv6_cidr_block_association_id: str = None,
    ipv6_cidr_block_state: str = None,
    owner_id: str = None,
    state: str = None,
    tag_key: str = None,
    tags: Mapping = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single subnet.
    Can also be used to determine if a subnet exists.

    The following paramers are translated into filters to refine the lookup:

    :param str subnet_id: ID of the subnet.
    :param str subnet_name: The ``Name``-tag of the subnet.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str subnet_arn: The Amaxon Resource Name (ARN) of the subnet.
    :param str vpc_id: The ID of the VPC for the subnet.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param str availability_zone: The Availability Zone for the subnet.
    :param str availability_zone_id: The ID of the Availability Zone for the subnet.
    :param str available_ip_address_count: The number of IPv4 addresses in the
      subnet that are available.
    :param str cidr_block: The IPv4 CIDR block of the subnet. The CIDR block you
      specify must exactly match the subnet's CIDR block for information to be
      returned for the subnet.
    :param bool default_for_az: Indicates whether this is the default subnet for
      the Availability Zone.
    :param str ipv6_cidr_block: An IPv6 CIDR block associated with the subnet.
    :param str ipv6_cidr_block_association_id: An association ID for an IPv6 CIDR
      block associated with the subnet.
    :param str ipv6_cidr_block_state: The state of an IPv6 CIDR block associated
      with the subnet.
    :param str owner_id:  The ID of the AWS account that owns the subnet.
    :param str state: The state of the subnet (``pending`` | ``available``).
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the subnet.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_subnets``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_subnets
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup or {"vpc_id": vpc_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        vpc_id = res["result"].get("vpc")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "tag:Name": subnet_name,
                "availability-zone": availability_zone,
                "availability-zone-id": availability_zone_id,
                "available_ip_address_count": available_ip_address_count,
                "cidr_block": cidr_block,
                "default-for-az": default_for_az,
                "ipv6-cidr-block-association.ipv6-cidr-block": ipv6_cidr_block,
                "ipv6-cidr-block-association.association_id": ipv6_cidr_block_association_id,
                "ipv6-cidr-block-association.state": ipv6_cidr_block_state,
                "owner-id": owner_id,
                "state": state,
                "subnet-id": subnet_id,
                "subnet-arn": subnet_arn,
                "tag-key": tag_key,
                "vpc-id": vpc_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "subnet",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_tag(
    tag_key: str = None,
    resource_id: str = None,
    resource_type: str = None,
    tags: Mapping = None,
    tag_value: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Describes one or more of the tags for your EC2 resources.

    The following arguments specify filters to select the resource(s) to describe
    the tags of:

    :param str tag_key: The tag key to filter on regardless of value.
    :param str resource_id: The ID of the resource to filter on.
    :param str resource_type: The resource type to filter on. Allowed values:
      customer-gateway, dedicated-host, dhcp-options, elastic-ip, fleet, fpga-image,
      host-reservation, image, instance, internet-gateway, key-pair, launch-template,
      natgateway, network-acl, network-interface, placement-group, reserved-instances,
      route-table, security-group, snapshot, spot-instances-request, subnet, volume,
      vpc, vpc-endpoint, vpc-endpoint-service, vpc-peering-connection, vpn-connection,
      vpn-gateway.
    :param dict tags: Tags to filter on.
    :param str tag_value: The tag value to filter on, regardless of key.
    :param dict filters: The dict with filters to specify the resource to
      describe tags of.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_tags``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_tags
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "key": tag_key,
                "resource-id": resource_id,
                "resource-type": resource_type,
                "value": tag_value,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "tag",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_transit_gateway(
    propagation_default_route_table_id: str = None,
    amazon_side_asn: int = None,
    association_default_route_table_id: str = None,
    auto_accept_shared_attachments: bool = None,
    default_route_table_association: bool = None,
    default_route_table_propagation: bool = None,
    dns_support: bool = None,
    vpn_ecmp_support: bool = None,
    owner_id: str = None,
    state: str = None,
    transit_gateway_id: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single transit gateway.
    Can also be used to determine if a transit gateway exists.

    The following paramers are translated into filters to refine the lookup:

    :param str propagation_default_route_table_id: The ID of the default propagation
      route table.
    :param int amazon_side_asn: The private ASN for the Amazon side of a BGP session.
    :param str association_default_route_table_id: The ID of the default association
      route table.
    :param bool auto_accept_shared_attachments: Indicates whether there is automatic
      acceptance of attachment requests.
    :param bool default_route_table_association: Indicates whether resource attachments
      are automatically associated with the default association route table.
    :param bool default_route_table_propagation: Indicates whether resource attachments
      automatically propagate routes to the default propagation route table.
    :param bool dns_support: Indicates whether DNS support is enabled.
    :param bool vpn_ecmp_support: Indicates whether Equal Cost Multipath Protocol
      support is enabled.
    :param str owner_id: The ID of the AWS account that owns the transit gateway.
    :param str state: The state of the attachment. Allowed values: ``available``,
      ``deleted``, ``deleting``, ``failed``, ``modifying``, ``pendingAcceptance``,
      ``pending``, ``rollingBack``, ``rejected``, ``rejecting``.
    :param str transit_gateway_id: The ID of the transit gateway.
    :param dict filters: Dict with filters to identify the transit gateway.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_transit_gateways``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "options.propagation-default-route-table-id": propagation_default_route_table_id,
                "options.amazon-side-asn": amazon_side_asn,
                "options.association-default-route-table-id": association_default_route_table_id,
                "options.auto-accept-shared-attachments": __utils__[
                    "boto3.bool_to_enable_disable"
                ](auto_accept_shared_attachments),
                "options.default-route-table-association": __utils__[
                    "boto3.bool_to_enable_disable"
                ](default_route_table_association),
                "options.default-route-table-propagation": __utils__[
                    "boto3.bool_to_enable_disable"
                ](default_route_table_propagation),
                "options.dns-support": __utils__["boto3.bool_to_enable_disable"](
                    dns_support
                ),
                "options.vpn-ecmp-support": __utils__["boto3.bool_to_enable_disable"](
                    vpn_ecmp_support
                ),
                "owner-id": owner_id,
                "state": state,
                "transit-gateway-id": transit_gateway_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "transit_gateway",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_volume(
    attach_time: datetime = None,
    delete_on_termination: bool = None,
    device_name: str = None,
    instance_id: str = None,
    instance_lookup: Mapping = None,
    attachment_status: str = None,
    availability_zone: str = None,
    create_time: datetime = None,
    encrypted: bool = None,
    multi_attach_enabled: bool = None,
    fast_restored: bool = None,
    size: int = None,
    snapshot_id: str = None,
    snapshot_lookup: Mapping = None,
    status: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    volume_id: str = None,
    volume_type: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single volume.
    Can also be used to determine if a volume exists.

    The following paramers are translated into filters to refine the lookup:

    :param datetime attach_time: The time stamp when the attachment initiated.
    :param bool delete_on_termination: Whether the volume is deleted on instance termination.
    :param str device_name: The device name specified in the block device mapping (for example, ``/dev/sda1``).
    :param str instance_id: The ID of the instance the volume is attached to.
    :param dict instance_lookup: Any kwargs that :py:func:`lookup_instance` accepts.
      Used to lookup ``instance_id``.
    :param str attachment_status: The attachment state. Allowed values: ``attaching``,
      ``attached``, ``detaching``.
    :param str availability_zone: The Availability Zone in which the volume was created.
    :param datetime create_time: The time stamp when the volume was created.
    :param bool encrypted: Indicates whether the volume is encrypted.
    :param bool multi_attach_enabled: Indicates whether the volume is enabled for Multi-Attach.
    :param bool fast_restored: Indicates whether the volume was created from a snapshot that is enabled for fast snapshot restore.
    :param int size: The size of the volume, in GiB.
    :param str snapshot_id: The snapshot from which the volume was created.
    :param dict snapshot_lookup: Any kwargs that :py:func:`lookup_snapshot` accepts.
      Used to lookup ``snapshot_id``.
    :param str status: The status of the volume. Allowed values: ``creating``,
      ``available``, ``in-use``, ``deleting``, ``deleted``, ``error``.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str volume_id: The Volume ID.
    :param str volume_type: The Amazon EBS volume type. This can be ``gp2`` for
      General Purpose SSD, ``io1`` for Provisioned IOPS SSD, ``st1`` for Throughput
      Optimized HDD, ``sc1`` for Cold HDD, or ``standard`` for Magnetic volumes.
    :param dict filters: Dict with filters to identify the volume.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_volumes``-call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookup or {"instance_id": instance_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "snapshot",
            "kwargs": snapshot_lookup or {"snapshot_id": snapshot_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        instance_id = res.get("instance")
        snapshot_id = res.get("snapshot")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "attachment.attach-time": attach_time,
                "attachment.delete-on-termination": delete_on_termination,
                "attachment.device": device_name,
                "attachment.instance-id": instance_id,
                "attachment.status": attachment_status,
                "availability-zone": availability_zone,
                "create-time": create_time,
                "encrypted": encrypted,
                "multi-attach-enabled": multi_attach_enabled,
                "fast-restored": fast_restored,
                "size": size,
                "snapshot-id": snapshot_id,
                "status": status,
                "tag-key": tag_key,
                "volume-id": volume_id,
                "volume-type": volume_type,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "volume",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_vpc(
    vpc_id: str = None,
    vpc_name: str = None,
    cidr: str = None,
    cidr_block: str = None,
    cidr_block_association_id: str = None,
    cidr_block_state: str = None,
    dhcp_options_id: str = None,
    ipv6_cidr_block: str = None,
    ipv6_cidr_block_pool: str = None,
    ipv6_cidr_block_association_id: str = None,
    ipv6_cidr_block_state: str = None,
    is_default: bool = None,
    owner_id: str = None,
    state: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single VPC.
    Can also be used to determine if a VPC exists.

    The following paramers are translated into filters to refine the lookup:

    :param str vpc_id: ID of the VPC.
    :param str vpc_name: The ``Name``-tag of the VPC.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str cidr: The primary IPv4 CIDR block of the VPC. The CIDR block you
      specify must exactly match the VPC's CIDR block for information to be
      returned for the VPC. Must contain the slash followed by one or two digits
      (for example, ``/28`` ).
    :param str cidr_block: An IPv4 CIDR block associated with the VPC.
    :param str cidr_block_association_id: The association ID for an IPv4 CIDR
      block associated with the VPC.
    :param str cidr_block_state: The state of an IPv4 CIDR block associated with
      the VPC.
    :param str dhcp_options_id: The ID of a set of DHCP options.
    :param str ipv6_cidr_block: An IPv6 CIDR block associated with the VPC.
    :param str ipv6_cidr_block_pool: The ID of the IPv6 address pool from which
      the IPv6 CIDR block is allocated.
    :param str ipv6_cidr_block_association_id: The association ID for an IPv6
      CIDR block associated with the VPC.
    :param str ipv6_cidr_block_state: The state of an IPv6 CIDR block associated
      with the VPC.
    :param str is_default: Indicates whether the VPC is the default VPC.
    :param str owner_id: The ID of the AWS account that owns the VPC.
    :param str state: The state of the VPC (``pending`` | ``available``).
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the VPC.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.
    :param str region: The region to connect to to perform the lookup.
    :param str keyid: The AWS Access key to use to perform the lookup.
    :param str key: The AWS secret key to use to perform the lookup.
    :param str profile: The Boto3 authentication profile to use to perform the lookup.
    :param object client: An already connected Boto3 client object to use to
      perform the lookup.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpcs``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_vpcs
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "cidr": cidr,
                "cidr-block-association.cidr-block": cidr_block,
                "cidr-block-association.association-id": cidr_block_association_id,
                "cidr-block-association.stats": cidr_block_state,
                "dhcp-options-id": dhcp_options_id,
                "ipv6-cidr-block-association.ipv6-cidr-block": ipv6_cidr_block,
                "ipv6-cidr-block-association.ipv6-pool": ipv6_cidr_block_pool,
                "ipv6-cidr-block-association.association-id": ipv6_cidr_block_association_id,
                "ipv6-cidr-block-association.state": ipv6_cidr_block_state,
                "isDefault": is_default,
                "owner-id": owner_id,
                "state": state,
                "tag-key": tag_key,
                "tag:Name": vpc_name,
                "vpc-id": vpc_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "vpc",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_vpc_endpoint(
    vpc_endpoint_id: str = None,
    vpc_endpoint_name: str = None,
    service_name: str = None,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    vpc_endpoint_state: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single VPC peering connection.
    Can also be used to determine if a VPC peering connection exists.

    The following paramers are translated into filters to refine the lookup:

    :param str vpc_endpoint_id: The ID of the endpoint.
    :param str vpc_endpoint_name: The ``Name``-tag of the VPC endpoint.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str service_name: The name of the service.
    :param str vpc_id: The ID of the VPC in which the endpoint resides.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param str vpc_endpoint_state: The state of the endpoint. Allowed values:
      pendingAcceptance, pending, available, deleting, deleted, rejected, failed.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the VPC endpoint.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_endpoints``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup or {"vpc_id": vpc_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        vpc_id = res["result"].get("vpc")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "tag:Name": vpc_endpoint_name,
                "service-name": service_name,
                "vpc-id": vpc_id,
                "vpc-endpoint-id": vpc_endpoint_id,
                "vpc-endpoint-state": vpc_endpoint_state,
                "tag-key": tag_key,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "vpc_endpoint",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_vpc_endpoint_service(
    service_name: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Helper function to find a single VPC endpoint service.
    Can also be used to determine if a VPC endpoint service exists.

    The following paramers are translated into filters to refine the lookup:

    :param str service_name: The name of the service.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the VPC endpoint service.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_endpoint_services``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {"service-name": service_name, "tag-key": tag_key}
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "vpc_endpoint_service",
        filters=filters,
        tags=tags,
        result_key="ServiceDetails",
        client=client,
    )


def lookup_vpc_endpoint_service_configuration(
    service_name: str = None,
    service_id: str = None,
    service_state: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single VPC endpoint service.
    Can also be used to determine if a VPC endpoint service exists.

    The following paramers are translated into filters to refine the lookup:

    :param str service_name: The name of the service.
    :param str service_id: The ID of the service.
    :param str service_state: The state of the service. Allowed values: Pending,
      Available, Deleting, Deleted, Failed.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the VPC peering connection.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_endpoint_service_configurations``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "service-name": service_name,
                "service-id": service_id,
                "service-state": service_state,
                "tag-key": tag_key,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "vpc_endpoint_service_configuration",
        filters=filters,
        tags=tags,
        result_key="ServiceConfigurations",
        client=client,
    )


def lookup_vpc_peering_connection(
    vpc_peering_connection_id: str = None,
    vpc_peering_connection_name: str = None,
    accepter_vpc_cidr_block: str = None,
    accepter_vpc_owner_id: str = None,
    accepter_vpc_id: str = None,
    accepter_vpc_lookup: Mapping = None,
    expiration_time: datetime = None,
    requester_vpc_cidr_block: str = None,
    requester_vpc_owner_id: str = None,
    requester_vpc_id: str = None,
    requester_vpc_lookup: Mapping = None,
    status_code: int = None,
    status_message: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single VPC peering connection.
    Can also be used to determine if a VPC peering connection exists.

    The following paramers are translated into filters to refine the lookup:

    :param str vpc_peering_connection_id: ID of the VPC peering connection.
    :param str vpc_peering_connection_name: The ``Name``-tag of the VPC peering
      connection.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str accepter_vpc_cidr_block: The IPv4 CIDR block of the accepter VPC.
    :param str accepter_vpc_owner_id:  The AWS account ID of the owner of the
      accepter VPC.
    :param str accepter_vpc_id: The ID of the accepter VPC.
    :param dict accepter_vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``accepter_vpc_id``.
      It is allowed to provide alternative credentials in this dict if the owner
      of the accepter VPC is different from the account that is used to perform
      this lookup.
    :param datetime expiration_time: The expiration date and time for the VPC
      peering connection.
    :param str requester_vpc_cidr_block: The IPv4 CIDR block of the requester's VPC.
    :param str requester_vpc_owner_id: The AWS account ID of the owner of the
      requester VPC.
    :param str requester_vpc_id: The ID of the requester VPC.
    :param dict requester_vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``requester_vpc_id``.
      It is allowed to provide alternative credentials in this dict if the owner
      of the requester VPC is different from the account that is used to perform
      this lookup.
    :param str status_code: The status of the VPC peering connection.
      Allowed values: pending-acceptance, failed, expired, provisioning, active,
      deleting, deleted, rejected.
    :param str status_message: A message that provides more information about the
      status of the VPC peering connection, if applicable.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param dict filters: Dict with filters to identify the VPC peering connection.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpc_peering_connections``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).

    :depends: boto3.client('ec2').describe_vpc_peering_connections
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "as": "accepter_vpc",
            "kwargs": accepter_vpc_lookup or {"vpc_id": accepter_vpc_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpc",
            "as": "requester_vpc",
            "kwargs": requester_vpc_lookup or {"vpc_id": requester_vpc_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        accepter_vpc_id = res.get("accepter_vpc")
        requester_vpc_id = res.get("requester_vpc")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "tag:Name": vpc_peering_connection_name,
                "accepter-vpc-info.cidr-block": accepter_vpc_cidr_block,
                "accepter-vpc-info.owner-id": accepter_vpc_owner_id,
                "accepter-vpc-info.vpc-id": accepter_vpc_id,
                "expiration-time": expiration_time,
                "requester-vpc-info.cidr-block": requester_vpc_cidr_block,
                "requester-vpc-info.owner-id": requester_vpc_owner_id,
                "requester-vpc-info.vpc-id": requester_vpc_id,
                "status-code": status_code,
                "status-message": status_message,
                "tag-key": tag_key,
                "vpc-peering-connection-id": vpc_peering_connection_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "vpc_peering_connection",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_vpn_connection(
    customer_gateway_configuration: str = None,
    customer_gateway_id: str = None,
    customer_gateway_lookup: Mapping = None,
    state: str = None,
    static_routes_only: bool = None,
    destination_cidr_block: str = None,
    bgp_asn: int = None,
    tags: Mapping = None,
    tag_key: str = None,
    connection_type: str = None,
    vpn_connection_id: str = None,
    vpn_gateway_id: str = None,
    vpn_gateway_lookup: Mapping = None,
    transit_gateway_id: str = None,
    transit_gateway_lookup: Mapping = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single vpn connection.
    Can also be used to determine if a vpn connection exists.

    The following paramers are translated into filters to refine the lookup:

    :param str customer_gateway_configuration: The configuration information for the customer gateway.
    :param str customer_gateway_id: The ID of a customer gateway associated with the VPN connection.
    :param dict customer_gateway_lookup: Any kwargs that :py:func:`lookup_customer_gateway`
      accepts. Used to lookup ``customer_gateway_id``.
    :param str state: The state of the VPN connection. Allowed values: ``pending``,
      ``available``, ``deleting``, ``deleted``.
    :param bool static_routes_only: Indicates whether the connection has static routes only. Used for devices that do not support Border Gateway Protocol (BGP).
    :param str destination_cidr_block: The destination CIDR block. This corresponds to the subnet used in a customer data center.
    :param str bgp_asn: The BGP Autonomous System Number (ASN) associated with a BGP device.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str connection_type: The type of VPN connection. Currently the only supported type is ``ipsec.1``.
    :param str vpn_connection_id: The ID of the VPN connection.
    :param str vpn_gateway_id: The ID of a virtual private gateway associated with the VPN connection.
    :param dict vpn_gateway_lookup: Any kwargs that :py:func:`lookup_vpn_gateway`
      accepts. Used to lookup ``vpn_gateway_id``.
    :param str transit_gateway_id: The ID of a transit gateway associated with the VPN connection.
    :param dict transit_gateway_lookup: Any kwargs that :py:func:`lookup_transit_gateway`
      accepts. Used to lookup ``transit_gateway_id``.
    :param dict filters: Dict with filters to identify the vpn connection.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpn_connections``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "customer_gateway",
            "kwargs": customer_gateway_lookup
            or {"customer_gateway_id": customer_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpn_gateway",
            "kwargs": vpn_gateway_lookup or {"vpn_gateway_id": vpn_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "transit_gateway",
            "kwargs": transit_gateway_lookup
            or {"transit_gateway_id": transit_gateway_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        customer_gateway_id = res.get("customer_gateway")
        vpn_gateway_id = res.get("vpn_gateway")
        transit_gateway_id = res.get("transit_gateway")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "customer-gateway-configuration": customer_gateway_configuration,
                "customer-gateway-id": customer_gateway_id,
                "state": state,
                "option.static-routes-only": static_routes_only,
                "route.destination-cidr-block": destination_cidr_block,
                "bgp-asn": bgp_asn,
                "tag-key": tag_key,
                "type": connection_type,
                "vpn-connection-id": vpn_connection_id,
                "vpn-gateway-id": vpn_gateway_id,
                "transit-gateway-id": transit_gateway_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "vpn_connection",
        filters=filters,
        tags=tags,
        client=client,
    )


def lookup_vpn_gateway(
    vpn_gateway_id: str = None,
    vpn_gateway_name: str = None,
    amazon_side_asn: int = None,
    attachment_state: str = None,
    attachment_vpc_id: str = None,
    attachment_vpc_lookup: Mapping = None,
    availability_zone: str = None,
    state: str = None,
    tags: Mapping = None,
    tag_key: str = None,
    vpn_gateway_type: str = None,
    filters: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
    client: botocore.client.BaseClient = None,
) -> Dict:
    """
    Helper function to find a single virtual private gateway.
    Can also be used to determine if a virtual private gateway exists.

    The following paramers are translated into filters to refine the lookup:

    :param str vpn_gateway_id: The ID of the virtual private gateway.
    :param str vpn_gateway_name: The ``Name``-tag of the virtual private gateway.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param int amazon_side_asn: The Autonomous System Number (ASN) for the Amazon
      side of the gateway.
    :param str attachment_state: The current state of the attachment between the
      gateway and the VPC. Allowed values: attaching, attached, detaching, detached.
    :param str attachment_vpc_id: The ID of an attached VPC.
    :param dict attachment_vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``attachment_vpc_id``.
    :param str availability_zone:  The Availability Zone for the virtual private
      gateway (if applicable).
    :param str state: The state of the virtual private gateway.
      Allowed values: pending, available, deleting, deleted.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str vpn_gateway_type: The type of virtual private gateway.
      Currently the only supported type is ``ipsec.1``.
    :param dict filters: Dict with filters to identify the VPC peering connection.
      Note that for any of the values supplied in the arguments above that also
      occur in ``filters``, the arguments above will take presedence.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_vpn_gateways``-
      call on succes.
      If the call was succesful but returned nothing, both the 'error' and 'result'
      key will be set with the notice that nothing was found and an empty dict
      respectively (since it is assumed you're looking to find something).
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": attachment_vpc_lookup or {"vpc_id": attachment_vpc_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        attachment_vpc_id = res["result"].get("vpc")
    if filters is None:
        filters = {}
    filters.update(
        salt.utils.data.filter_falsey(
            {
                "tag:Name": vpn_gateway_name,
                "amazon-side-asn": amazon_side_asn,
                "attachment.state": attachment_state,
                "attachment.vpc-id": attachment_vpc_id,
                "availability-zone": availability_zone,
                "state": state,
                "tag-key": tag_key,
                "type": vpn_gateway_type,
                "vpn-gateway-id": vpn_gateway_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "vpc_peering_connection",
        filters=filters,
        tags=tags,
        client=client,
    )


@_arguments_to_list("security_group_ids", "security_group_lookups")
def modify_network_interface_attribute(
    network_interface_id: str = None,
    network_interface_lookup: Mapping = None,
    delete_on_termination: bool = None,
    attachment_id: str = None,
    description: str = None,
    security_group_ids: Union[str, Iterable[str]] = None,
    security_group_lookups: Union[Mapping, Iterable[Mapping]] = None,
    source_dest_check: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Modifies the specified network interface attribute. You can use this action
    to attach and detach security groups from an existing EC2 instance.
    You can modify multiple attributes; this function will call boto multiple times
    for each attribute. At the first failure, the error will be returned.

    :param str network_interface_id: The ID of the network interface.
    :param str network_interface_lookup: Any kwargs that :py:func:`lookup_network_interface`
      accepts. Used to lookup ``network_interface_id``.
    :param bool delete_on_termination: Indicates whether the network interface
      is deleted when the instance is terminated. You must specify ``attachment_id``,
      ``network_interface_id`` or ``network_interface_lookup`` when modifying
      this attribute.
    :param str attachment_id: The ID of the network interface attachment.
    :param str description: A description for the network interface.
    :type security_group_ids: str or list(str)
    :param security_group_ids: Changes the security groups for the
      network interface. The new set of groups you specify replaces the current
      set. You must specify at least one group, even if it's just the default security
      group in the VPC.
    :type security_group_lookups: dict or list(dict)
    :param security_group_lookups: Any kwargs that :py:func:`lookup_security_group`
      accepts. Used to lookup ``security_group_ids``.
    :param bool source_dest_check: Indicates whether source/destination checking
      is enabled. A value of ``True`` means checking is enabled, and ``False``
      means checking is disabled. This value must be ``False`` for a NAT instance
      to perform NAT.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "network_interface",
            "kwargs": network_interface_lookup
            or salt.utils.data.filter_falsey(
                {
                    "network_interface_id": network_interface_id,
                    "attachment_id": attachment_id,
                }
            ),
            "result_keys": ["NetworkInterfaceId", "Attachment:AttachmentId"],
        },
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": security_group_lookups
            or [{"group_id": group_id} for group_id in security_group_ids or []],
            "required": False,
            "result_keys": "GroupId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        network_interface_id = res["network_interface"]["NetworkInterfaceId"]
        params = salt.utils.data.filter_falsey(
            {
                "Attachment": {
                    "AttachmentId": res["network_interface"]["Attachment:AttachmentId"],
                    "DeleteOnTermination": delete_on_termination,
                },
                "Description": {"Value": description},
                "Groups": res.get("security_group"),
                "SourceDestCheck": {"Value": source_dest_check},
            }
        )
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    for attribute, new_value in params.items():
        res = __utils__["boto3.handle_response"](
            client.modify_network_interface_attribute,
            NetworkInterfaceId=network_interface_id,
            **{attribute: new_value},
        )
        if "error" in res:
            return res
    return {"result": True}


def modify_spot_fleet_request(
    spot_fleet_request_id: str = None,
    excess_capacity_termination_policy: str = None,
    target_capacity: int = None,
    on_demand_target_capacity: int = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Modifies the specified Spot Fleet request.

    You can only modify a Spot Fleet request of type ``maintain``.

    While the Spot Fleet request is being modified, it is in the modifying state.

    To scale up your Spot Fleet, increase its target capacity. The Spot Fleet launches
    the additional Spot Instances according to the allocation strategy for the
    Spot Fleet request. If the allocation strategy is lowestPrice , the Spot Fleet
    launches instances using the Spot Instance pool with the lowest price. If the
    allocation strategy is diversified , the Spot Fleet distributes the instances
    across the Spot Instance pools. If the allocation strategy is ``capacityOptimized``,
    Spot Fleet launches instances from Spot Instance pools with optimal capacity
    for the number of instances that are launching.

    To scale down your Spot Fleet, decrease its target capacity. First, the Spot
    Fleet cancels any open requests that exceed the new target capacity. You can
    request that the Spot Fleet terminate Spot Instances until the size of the
    fleet no longer exceeds the new target capacity. If the allocation strategy
    is ``lowestPrice``, the Spot Fleet terminates the instances with the highest
    price per unit. If the allocation strategy is ``capacityOptimized``, the Spot
    Fleet terminates the instances in the Spot Instance pools that have the least
    available Spot Instance capacity. If the allocation strategy is ``diversified``,
    the Spot Fleet terminates instances across the Spot Instance pools. Alternatively,
    you can request that the Spot Fleet keep the fleet at its current size, but
    not replace any Spot Instances that are interrupted or that you terminate manually.

    If you are finished with your Spot Fleet for now, but will use it again later,
    you can set the target capacity to 0.

    :param str spot_fleet_request_id: The ID of the Spot Fleet request.
    :param str excess_capacity_termination_policy: Indicates whether running Spot
      Instances should be terminated if the target capacity of the Spot Fleet request
      is decreased below the current size of the Spot Fleet.
    :param int target_capacity: The size of the fleet.
    :param int on_demand_target_capacity: The number of On-Demand Instances in
      the fleet.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on succes.
    """
    params = salt.utils.data.filter_falsey(
        {
            "ExcessCapacityTerminationPolicy": excess_capacity_termination_policy,
            "SpotFleetRequestId": spot_fleet_request_id,
            "TargetCapacity": target_capacity,
            "OnDemandTargetCapacity": on_demand_target_capacity,
        }
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.modify_spot_fleet_request, params)


def modify_subnet_attribute(
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    assign_ipv6_address_on_creation: bool = None,
    map_public_ip_on_launch: bool = None,
    map_customer_owned_ip_on_launch: bool = None,
    customer_owned_ipv4_pool: str = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Modifies one or more subnet attributes.

    :param str subnet_id: The ID of the subnet to modify.
    :param dict subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.
    :param bool assign_ipv6_address_on_creation: Specify ``True`` to indicate that
      network interfaces created in the specified subnet should be assigned an
      IPv6 address. This includes a network interface that's created when launching
      an instance into the subnet (the instance therefore receives an IPv6 address).
      If you enable the IPv6 addressing feature for your subnet, your network
      interface or instance only receives an IPv6 address if it's created using
      version 2016-11-15 or later of the Amazon EC2 API.
    :param bool map_public_ip_on_launch: Specify ``True`` to indicate that network
      interfaces created in the specified subnet should be assigned a public
      IPv4 address. This includes a network interface that's created when launching
      an instance into the subnet (the instance therefore receives a public IPv4
      address).
    :param bool map_customer_owned_ip_on_launch: Specify ``True`` to indicate that
      network interfaces attached to instances created in the specified subnet
      should be assigned a customer-owned IPv4 address.
      When this value is ``True``, you must specify the customer-owned IP pool
      using ``customer_owned_ipv4_pool``.
    :param str customer_owned_ipv4_pool: The customer-owned IPv4 address pool
      associated with the subnet.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_subnets, boto3.client('ec2').modify_subnet_attribute
    """
    if map_customer_owned_ip_on_launch is True and not customer_owned_ipv4_pool:
        raise SaltInvocationError(
            "Specifying map_customer_owned_ip_on_launch requires specifying "
            "customer_owned_ipv4_pool."
        )
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "subnet",
            "kwargs": subnet_lookup or {"subnet_id": subnet_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        subnet_id = res["result"]["subnet"]
    params = salt.utils.data.filter_falsey(
        {
            "AssignIpv6AddressOnCreation": {"Value": assign_ipv6_address_on_creation},
            "MapPublicIpOnLaunch": {"Value": map_public_ip_on_launch},
            "MapCustomerOwnedIpOnLaunch": {"Value": map_customer_owned_ip_on_launch},
        },
        recurse_depth=1,
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    for item, value in params.items():
        try:
            client.modify_subnet_attribute(SubnetId=subnet_id, **{item: value})
        except (ParamValidationError, ClientError) as exp:
            return {"error": __utils__["boto3.get_error"](exp)["message"]}
    return {"result": True}


def modify_vpc_attribute(
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    enable_dns_support: bool = None,
    enable_dns_hostnames: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Modifies the specified attribute of the specified VPC.

    :param str vpc_id: The ID of the VPC to operate on.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.
    :param bool enable_dns_support: Indicates whether the DNS resolution is supported
      for the VPC. If enabled, queries to the Amazon provided DNS server at the
      169.254.169.253 IP address, or the reserved IP address at the base of the
      VPC network range "plus two" succeed. If disabled, the Amazon provided DNS
      service in the VPC that resolves public DNS hostnames to IP addresses is
      not enabled.
    :param bool enable_dns_hostnames: Indicates whether the instances launched
      in the VPC get DNS hostnames. If enabled, instances in the VPC get DNS
      hostnames; otherwise, they do not.
      You can only enable DNS hostnames if DNS support is already enabled.
      If you specify both these attributes, two calls will be executed in the
      correct order.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      containing ``True`` on succes.

    :depends boto3.client('ec2').modify_vpc_attribute
    """
    ret = {}
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup or {"vpc_id": vpc_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        vpc_id = res["result"]["vpc"]
    params = salt.utils.data.filter_falsey(
        {
            "EnableDnsSupport": {"Value": enable_dns_support},
            "EnableDnsHostnames": {"Value": enable_dns_hostnames},
        },
        recurse_depth=1,
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    for item, value in params.items():
        try:
            client.modify_vpc_attribute(VpcId=vpc_id, **{item: value})
            ret["result"] = True
        except (ParamValidationError, ClientError) as exp:
            ret["error"] = __utils__["boto3.get_error"](exp)["message"]
    return ret


@_arguments_to_list(
    "add_network_load_balancer_arns", "remove_network_load_balancer_arns"
)
def modify_vpc_endpoint_service_configuration(
    service_id: str = None,
    service_lookup: Mapping = None,
    private_dns_name: str = None,
    remove_private_dns_name: bool = None,
    acceptance_required: bool = None,
    add_network_load_balancer_arns: Union[str, Iterable[str]] = None,
    remove_network_load_balancer_arns: Union[str, Iterable[str]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Modifies the attributes of your VPC endpoint service configuration. You can
    change the Network Load Balancers for your service, and you can specify whether
    acceptance is required for requests to connect to your endpoint service through
    an interface VPC endpoint.

    If you set or modify the private DNS name, you must prove that you own the
    private DNS domain name.

    :param str service_id: The ID of the service.
    :param dict service_lookup: Any kwargs that :py:func:`lookup_vpc_endpoint_service`
      accepts. Used to lookup ``service_id``.
    :param str private_dns_name: The private DNS name to assign to the endpoint service.
    :param bool remove_private_dns_name: Removes the private DNS name of the endpoint service.
    :param bool acceptance_required: Indicates whether requests to create an endpoint
      to your service must be accepted.
    :type add_network_load_balancer_arns: str or list(str)
    :param add_network_load_balancer_arns: The Amazon Resource Names
      (ARNs) of Network Load Balancers to add to your service configuration.
    :type remove_network_load_balancer_arns: str or list(str)
    :param remove_network_load_balancer_arns: The Amazon Resource
      Names (ARNs) of Network Load Balancers to remove from your service configuration.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        containing ``True`` on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc_endpoint_service",
            "kwargs": service_lookup or {"service_id": service_id},
            "result_keys": "ServiceId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = salt.utils.data.filter_falsey(
            {
                "ServiceId": res["vpc_endpoint_service"],
                "PrivateDnsName": private_dns_name,
                "RemovePrivateDnsName": remove_private_dns_name,
                "AcceptanceRequired": acceptance_required,
                "AddNetworkLoadBalancerArns": add_network_load_balancer_arns,
                "RemoveNetworkLoadBalancerArns": remove_network_load_balancer_arns,
            }
        )
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](
        client.modify_vpc_endpoint_service_configuration, params
    )


def modify_vpc_endpoint_service_permissions(
    service_id: str = None,
    service_lookup: Mapping = None,
    add_allowed_principals: Iterable[str] = None,
    remove_allowed_principals: Iterable[str] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Modifies the permissions for your VPC endpoint service. You can add or remove
    permissions for service consumers (IAM users, IAM roles, and AWS accounts)
    to connect to your endpoint service.

    If you grant permissions to all principals, the service is public. Any users
    who know the name of a public service can send a request to attach an endpoint.
    If the service does not require manual approval, attachments are automatically
    approved.

    :param str service_id: The ID of the service.
    :param dict service_lookup: Any kwargs that :py:func:`lookup_vpc_endpoint_service`
      accepts. Used to lookup ``service_id``.
    :param list(str) add_allowed_principals: The Amazon Resource Names (ARN) of
      one or more principals. Permissions are granted to the principals in this
      list. To grant permissions to all principals, specify an asterisk (*).
    :param list(str) remove_allowed_principals: The Amazon Resource Names (ARN) of
      one or more principals. Permissions are revoked for principals in this list.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc_endpoint_service",
            "kwargs": service_lookup or {"service_id": service_id},
            "result_keys": "ServiceId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = salt.utils.data.filter_falsey(
            {
                "ServiceId": res["vpc_endpoint_service"],
                "AddAllowedPrincipals": add_allowed_principals,
                "RemoveAllowedPrincipals": remove_allowed_principals,
            }
        )
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](
        client.modify_vpc_endpoint_service_permissions, params
    )


def modify_vpc_tenancy(
    instance_tenancy: str,
    vpc_id: str = None,
    vpc_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Modifies the instance tenancy attribute of the specified VPC. You can change
    the instance tenancy attribute of a VPC to ``default`` only. You cannot change
    the instance tenancy attribute to ``dedicated``.

    After you modify the tenancy of the VPC, any new instances that you launch
    into the VPC have a tenancy of ``default``, unless you specify otherwise during
    launch. The tenancy of any existing instances in the VPC is not affected.

    :param str instance_tenancy: The instance tenancy attribute for the VPC.
    :param str vpc_id: The ID of the VPC to operate on.
    :param dict vpc_lookup: Any kwargs that :py:func:`lookup_vpc` accepts.
      Used to lookup ``vpc_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key with
      dict containing the result of the boto ``modify_vpc_tenancy``-call on succes.

    :depends: boto3.client('ec2').modify_vpc_tenancy
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": "vpc", "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"VpcId": res["result"]["vpc"], "InstanceTenancy": instance_tenancy}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](client.modify_vpc_tenancy, params)


@_arguments_to_list("instance_ids", "instance_lookups")
def reboot_instances(
    instance_ids: Union[str, Iterable[str]] = None,
    instance_lookups: Union[Mapping, Iterable[Mapping]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Requests a reboot of the specified instances. This operation is asynchronous;
    it only queues a request to reboot the specified instances. The operation succeeds
    if the instances are valid and belong to you. Requests to reboot terminated
    instances are ignored.

    If an instance does not cleanly shut down within four minutes, Amazon EC2 performs
    a hard reboot.

    :type instance_ids: str or list(str)
    :param instance_ids: The instance IDs.
    :type instance_lookups: dict or list(dict)
    :param instance_lookups: One or more dicts of kwargs that
      :py:func:`lookup_instance` accepts. Used to lookup ``instance_ids``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookups
            or [{"instance_ids": instance_id} for instance_id in instance_ids or []],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"InstanceIds": res["instance"]}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](client.reboot_instances, params)


@_arguments_to_list("block_device_mappings")
def register_image(
    name: str,
    image_location: str = None,
    architecture: str = None,
    block_device_mappings: Union[Mapping, Iterable[Mapping]] = None,
    description: str = None,
    ena_support: bool = None,
    kernel_id: str = None,
    billing_products: Iterable[str] = None,
    ramdisk_id: str = None,
    root_device_name: str = None,
    sriov_net_support: bool = None,
    virtualization_type: str = None,
    tags: Mapping = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Registers an AMI. When you're creating an AMI, this is the final step you must
    complete before you can launch an instance from the AMI.

    Note:
      For Amazon EBS-backed instances, ``create_image`` creates and registers the
      AMI in a single request, so you don't have to register the AMI yourself.

    You can also use ``register_image`` to create an Amazon EBS-backed Linux AMI
    from a snapshot of a root device volume. You specify the snapshot using the
    block device mapping.

    If any snapshots have AWS Marketplace product codes, they are copied to the
    new AMI.

    Windows and some Linux distributions, such as Red Hat Enterprise Linux (RHEL)
    and SUSE Linux Enterprise Server (SLES), use the EC2 billing product code associated
    with an AMI to verify the subscription status for package updates. To create
    a new AMI for operating systems that require a billing product code, instead
    of registering the AMI, do the following to preserve the billing product code
    association:

      - Launch an instance from an existing AMI with that billing product code.
      - Customize the instance.
      - Create an AMI from the instance using :py:func:`create_image`.

    If you purchase a Reserved Instance to apply to an On-Demand Instance that
    was launched from an AMI with a billing product code, make sure that the Reserved
    Instance has the matching billing product code. If you purchase a Reserved
    Instance without the matching billing product code, the Reserved Instance will
    not be applied to the On-Demand Instance.

    If needed, you can deregister an AMI at any time. Any modifications you make
    to an AMI backed by an instance store volume invalidates its registration.
    If you make changes to an image, deregister the previous image and register
    the new image.

    :param str name: A name for your AMI. Constraints: 3-128 alphanumeric characters,
      parentheses (()), square brackets ([]), spaces ( ), periods (.), slashes (/),
      dashes (-), single quotes ('), at-signs (@), or underscores(_)
    :param str image_location: The full path to your AMI manifest in Amazon S3
      storage. The specified bucket must have the aws-exec-read canned access control
      list (ACL) to ensure that it can be accessed by Amazon EC2.
    :param str architecture: The architecture of the AMI.
      Default: For Amazon EBS-backed AMIs, ``i386``. For instance store-backed
      AMIs, the architecture specified in the manifest file.
    :type block_device_mappings: dict or list(dict)
    :param block_device_mappings: The block device mapping. These dicts can either
      contain the structure as described
      `here <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_BlockDeviceMapping.html>`__
      or contain the kwargs that :py:func:`build_block_device_mapping` accepts.
    :param str description: A description for your AMI.
    :param bool ena_support: Set to true to enable enhanced networking with ENA
      for the AMI and any instances that you launch from the AMI.
      This option is supported only for HVM AMIs. Specifying this option with a
      PV AMI can make instances launched from the AMI unreachable.
    :param str kernel_id: The ID of the kernel.
    :param list(str): billing_products: The billing product codes. Your account
      must be authorized to specify billing product codes. Otherwise, you can use
      the AWS Marketplace to bill for the use of an AMI.
    :param str ramdisk_id: The ID of the RAM disk.
    :param str root_device_name: The device name of the root device volume
      (for example, ``/dev/sda1``).
    :param str sriov_net_support: Set to simple to enable enhanced networking with
      the Intel 82599 Virtual Function interface for the AMI and any instances
      that you launch from the AMI.
      There is no way to disable sriovNetSupport at this time.
      This option is supported only for HVM AMIs. Specifying this option with a
      PV AMI can make instances launched from the AMI unreachable.
    :param str virtualization_type: The type of virtualization.
      Allowed values: hvm, paravirtual. Default: paravirtual
    :param dict tags: The tags to apply to the created image.
    :param bool blocking: Wait until the image becomes available.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``register_image``-call on succes.
    """
    try:
        block_device_mappings = [
            build_block_device_mapping(item)["result"] for item in block_device_mappings
        ]
    except (TypeError, KeyError):
        pass  # to Boto as-is.
    params = salt.utils.data.filter_falsey(
        {
            "ImageLocation": image_location,
            "Architecture": architecture,
            "BlockDeviceMappings": block_device_mappings,
            "Description": description,
            "EnaSupport": ena_support,
            "KernelId": kernel_id,
            "Name": name,
            "BillingProducts": billing_products,
            "RamdiskId": ramdisk_id,
            "RootDeviceName": root_device_name,
            "SriovNetSupport": sriov_net_support,
            "VirtualizationType": virtualization_type,
        }
    )
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"],
        "image",
        boto_function_name="register_image",
        params=params,
        tags=tags,
        wait_until_state="available" if blocking else None,
        client=client,
    )


def reject_vpc_peering_connection(
    vpc_peering_connection_id=None,
    vpc_peering_connection_lookup=None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Rejects a VPC peering connection request. The VPC peering connection must be
    in the pending-acceptance state. Use :py:func:`describe_vpc_peering_connections`
    to view your outstanding VPC peering connection requests. To delete an active
    VPC peering connection, or to delete a VPC peering connection request that
    you initiated, use :py:func:`delete_vpc_peering_connection`.

    :param str vpc_peering_connection_id: The ID of the VPC peering connection.
    :param dict vpc_peering_connection_lookup: Any kwargs that :py:func:`lookup_vpc_peering_connection`
      accepts. Used to lookup ``vpc_peering_connection_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc_peering_connection",
            "kwargs": vpc_peering_connection_lookup
            or {"vpc_peering_connection_id": vpc_peering_connection_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"VpcPeeringConnectionId": res["vpc_peering_connection"]}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](
        client.reject_vpc_peering_connection, params
    )


def release_address(
    address_id: str = None,
    address_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Releases the specified Elastic IP address.

    [EC2-Classic, default VPC] Releasing an Elastic IP address automatically
    disassociates it from any instance that it's associated with. To disassociate
    an Elastic IP address without releasing it, use DisassociateAddress .

    [Nondefault VPC] You must use DisassociateAddress to disassociate the Elastic
    IP address before you can release it. Otherwise, Amazon EC2 returns an error
    (InvalidIPAddress.InUse ).

    After releasing an Elastic IP address, it is released to the IP address pool.
    Be sure to update your DNS records and any servers or devices that communicate
    with the address. If you attempt to release an Elastic IP address that you
    already released, you'll get an AuthFailure error if the address is already
    allocated to another AWS account.

    [EC2-VPC] After you release an Elastic IP address for use in a VPC, you might
    be able to recover it. For more information, see :py:func:`allocate_address`.

    :param str address_id: The (Allocation)ID of the Elastic IP.
    :param dict address_lookup: Any kwargs that :py:func:`lookup_address`
      accepts. Used to lookup ``address_id``.
    :param str eip_id: The AllocationID of the Elastic IP.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_addresses, boto3.client('ec2').release_address
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "address",
            "kwargs": address_lookup or {"allocation_id": address_id},
            "result_keys": "AllocationId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = {"AllocationId": res["address"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.release_address, params)


def replace_network_acl_association(
    association_id: str = None,
    network_acl_id: str = None,
    network_acl_lookup: Mapping = None,
    subnet_id: str = None,
    subnet_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Changes which network ACL a subnet is associated with. By default when you
    create a subnet, it's automatically associated with the default network ACL.

    :param str association_id: The The ID of the current association between the
      original network ACL and the subnet.
    :param str network_acl_id: The ID of the new network ACL to associate with
      the subnet.
    :param str network_acl_lookup: Any kwargs that :py:func:`lookup_network_acl`
      accepts. Used to lookup ``network_acl_id``.
    :param str subnet_id: The ID of the subnet to associate the network ACL with.
      Only needs to be specified if ``association_id`` is not provided.
      Since a subnet can only be associated with one network ACL at a time,
      specifying the subnet is an alternative to specifying ``association_id``.
    :param str subnet_lookup: Any kwargs that :py:func:`lookup_subnet` accepts.
      Used to lookup ``subnet_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``replace_network_acl_association``-
      call on succes.
    """
    if not association_id:
        # A subnet can only be associated with a single network ACL. So if we find
        # the subnet, we find the correct ACL.
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "subnet",
                "kwargs": subnet_lookup or {"subnet_id": subnet_id},
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            subnet_id = res["result"]["subnet"]
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "network_acl",
                "kwargs": {"association_subnet_id": subnet_id},
                "result_keys": ["NetworkAclId", "Associations"],
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            res = res["result"]["network_acl"]
            association_id = [
                item["NetworkAclAssociationId"]
                for item in res["Associations"]
                if item["SubnetId"] == subnet_id
            ][0]
            network_acl_id = res["NetworkAclId"]
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "network_acl",
            "kwargs": network_acl_lookup or {"network_acl_id": network_acl_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "AssociationId": association_id,
            "NetworkAclId": res["result"]["network_acl"],
        }
    return __utils__["boto3.handle_response"](
        client.replace_network_acl_association, params
    )


def replace_network_acl_entry(
    protocol: str,
    egress: bool,
    rule_number: int,
    rule_action: str,
    network_acl_id: str = None,
    network_acl_lookup: Mapping = None,
    cidr_block: str = None,
    icmp_type: int = None,
    icmp_code: int = None,
    ipv6_cidr_block: str = None,
    port_range: Tuple[int, int] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Replaces an entry (rule) in a network ACL.

    :param str protocol: The protocol number. A value of "-1" means all protocols.
      If you specify "-1" or a protocol number other than "6" (TCP), "17" (UDP),
      or "1" (ICMP), traffic on all ports is allowed, regardless of any ports
      or ICMP types or codes that you specify. If you specify protocol "58" (ICMPv6)
      and specify an IPv4 CIDR block, traffic for all ICMP types and codes allowed,
      regardless of any that you specify. If you specify protocol "58" (ICMPv6)
      and specify an IPv6 CIDR block, you must specify an ICMP type and code.
    :param bool egress: Indicates whether this is an egress rule (rule is applied
      to traffic leaving the subnet).
    :param int rule_number: The rule number for the entry (for example, 100).
      ACL entries are processed in ascending order by rule number.
      Constraints: Positive integer from 1 to 32766. The range 32767 to 65535
      is reserved for internal use.
    :param str rule_action: Indicates whether to allow or deny the traffic that
      matches the rule. Allowed values: allow, deny.
    :param str network_acl_id: The ID of the network ACL.
    :param str network_acl_lookup: Any kwargs that :py:func:`lookup_network_acl`
      accepts. Used to lookup ``network_acl_id``.
    :param str cidr_block:  The IPv4 network range to allow or deny, in CIDR notation
      (for example ``172.16.0.0/24``). We modify the specified CIDR block to its
      canonical form; for example, if you specify ``100.68.0.18/18``, we modify
      it to ``100.68.0.0/18``.
    :param int icmp_code: The ICMP code. A value of -1 means all codes for the
      specified ICMP type.
    :param int icmp_type: The ICMP type. A value of -1 means all types.
    :param str ipv6_cidr_block: The IPv6 network range to allow or deny, in CIDR
      notation (for example ``2001:db8:1234:1a00::/64``).
    :param tuple(int, int) port_range: The first and last port in the range.
      TCP or UDP protocols: The range of ports the rule applies to.
      Required if specifying protocol 6 (TCP) or 17 (UDP).

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
    if port_range is not None:
        if not isinstance(portrange, (list, tuple)):
            raise SaltInvocationError(
                "port_range must be a list or tuple, not {}".format(type(port_range))
            )
        if len(port_range) != 2:
            raise SaltInvocationError(
                "port_range must contain exactly two items, not {}".format(
                    len(port_range)
                )
            )
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "network_acl",
            "kwargs": network_acl_lookup or {"network_acl_id": network_acl_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = salt.utils.data.filter_falsey(
            {
                "CidrBlock": cidr_block,
                "Egress": egress,
                "IcmpTypeCode": {"Code": icmp_code, "Type": icmp_type},
                "Ipv6CidrBlock": ipv6_cidr_block,
                "NetworkAclId": res["result"]["network_acl"],
                "PortRange": {"From": port_range[0], "To": port_range[1]}
                if port_range
                else None,
                "Protocol": protocol,
                "RuleAction": rule_action,
                "RuleNumber": rule_number,
            },
            recurse_depth=1,
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.replace_network_acl_entry, params)


def replace_route(
    route_table_id: str = None,
    route_table_lookup: Mapping = None,
    destination_cidr_block: str = None,
    destination_ipv6_cidr_block: str = None,
    destination_prefix_list_id: str = None,
    destination_prefix_list_lookup: Mapping = None,
    egress_only_internet_gateway_id: str = None,
    egress_only_internet_gateway_lookup: Mapping = None,
    gateway_id: str = None,
    gateway_lookup: Mapping = None,
    instance_id: str = None,
    instance_lookup: Mapping = None,
    local_target: bool = None,
    nat_gateway_id: str = None,
    nat_gateway_lookup: Mapping = None,
    transit_gateway_id: str = None,
    transit_gateway_lookup: Mapping = None,
    local_gateway_id: str = None,
    local_gateway_lookup: Mapping = None,
    network_interface_id: str = None,
    network_interface_lookup: Mapping = None,
    vpc_peering_connection_id: str = None,
    vpc_peering_connection_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Replaces an existing route within a route table in a VPC. You must provide
    only one of the following: internet gateway, virtual private gateway, NAT
    instance, NAT gateway, VPC peering connection, network interface, egress-only
    internet gateway, or transit gateway.
    If you specify the route table by name only, you must supply at least one of
    ``vpc_name`` or ``vpc_id`` to perform the lookup for you.

    :param int route_table_id: The ID of the route table to operate on.
    :param dict route_table_lookup: Any kwargs that :py:func:`lookup_route_table`
      accepts. Used to lookup ``route_table_id``.
    :param str destination_cidr_block: The IPv4 CIDR address block used for the
      destination match. The value that you provide must match the CIDR of an
      existing route in the table.
    :param str destination_ipv6_cidr_block: The IPv6 CIDR address block used for
      the destination match. The value that you provide must match the CIDR of
      an existing route in the table.
    :param str destination_prefix_list_id: The ID of the prefix list for the route.
    :param dict destination_prefix_list_lookup: Any kwargs that :py:func:`lookup_managed_prefix_list`
      accepts. Used to lookup ``destination_prefix_list_id``.
    :param str egress_only_internet_gateway_id: [IPv6 traffic only] The ID of an
      egress-only internet gateway.
    :param dict egress_only_internet_gateway_lookup: Any kwargs that
      :py:func:`lookup_egress_only_internet_gateway` accepts. Used to lookup
      ``egress_only_internet_gateway_id``.
    :param str gateway_id: The ID of an internet gateway or virtual private gateway.
    :param dict gateway_lookup: Any kwargs that :py:func:`lookup_internet_gateway` or
      :py:func:`lookup_vpn_gateway` accepts. Used to lookup ``gateway_id`` is not provided.
    :param str instance_id: The ID of a NAT instance in your VPC.
    :param dict instance_lookup: Any kwarg that :py:func:`lookup_instance` accepts.
      Used to lookup ``instance_id``.
    :param bool local_target: Specifies whether to reset the local route to its
      default target (``local``).
    :param str nat_gateway_id: [IPv4 traffic only] The ID of a NAT gateway.
    :param dict nat_gateway_lookup: Any kwarg that :py:func:`lookup_nat_gateway` accepts.
      Used to lookup ``nat_gateway_id``.
    :param str transit_gateway_id: The ID of a transit gateway.
    :param dict transit_gateway_lookup: Any kwarg that :py:func:`lookup_transit_gateway`
      accepts. Used to lookup ``transit_gateway_id``.
    :param str local_gateway_id: The ID of the local gateway.
    :param dict local_gateway_lookup: Any kwarg that :py:func:`lookup_local_gateway`
      accepts. Used to lookup ``local_gateway_id``.
    :param str network_interface_id: The ID of a network interface.
    :param dict network_interface_lookup: Any kwarg that :py:func:`lookup_network_interface`
      accepts. Used to lookup ``network_interface_id``.
    :param str vpc_peering_connection_id: The ID of a VPC peering connection.
    :param dict vpc_peering_connection_lookup: Any kwarg that :py:func:`lookup_vpc_peering_connection`
      accepts. Used to lookup ``vpc_peering_connection_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
    # Amazon decided, in their wisdom, to let ``gateway`` be an IGW *or* a VPN gateway
    # So we need to look this up manually
    if gateway_id is None and gateway_lookup is not None:
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "internet_gateway",
                "kwargs": gateway_lookup or {"internet_gateway_id": gateway_id},
                "required": False,
            },
            {
                "service": "ec2",
                "name": "vpn_gateway",
                "kwargs": gateway_lookup or {"vpn_gateway_id": gateway_id},
                "required": False,
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" not in res:
                gateway_id = res["result"].get(
                    "internet_gateway", res["result"].get("vpn_gateway")
                )
            if gateway_id is None:
                if "error" in res:
                    return res
                return {
                    "error": (
                        "gateway_lookup was provided, but no single Internet gateway or "
                        "virtual private gateway matched."
                    )
                }
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "route_table",
            "kwargs": route_table_lookup or {"route_table_id": route_table_id},
        },
        {
            "service": "ec2",
            "name": "managed_prefix_list",
            "kwargs": destination_prefix_list_lookup
            or {"prefix_list_id": destination_prefix_list_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "egress_only_internet_gateway",
            "kwargs": egress_only_internet_gateway_lookup
            or {"egress_only_internet_gateway_id": egress_only_internet_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookup or {"instance_id": instance_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "local_gateway",
            "kwargs": local_gateway_lookup or {"local_gateway_id": local_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "nat_gateway",
            "kwargs": nat_gateway_lookup or {"nat_gateway_id": nat_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "transit_gateway",
            "kwargs": transit_gateway_lookup
            or {"transit_gateway_id": transit_gateway_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "network_interface",
            "kwargs": network_interface_lookup
            or {"network_interface_id": network_interface_id},
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpc_peering_connection",
            "kwargs": vpc_peering_connection_lookup
            or {"vpc_peering_connection_id": vpc_peering_connection_id},
            "required": False,
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        res = res["result"]
        params = salt.utils.data.filter_falsey(
            {
                "DestinationCidrBlock": destination_cidr_block,
                "DestinationIpv6CidrBlock": destination_ipv6_cidr_block,
                "DestinationPrefixListId": res.get("managed_prefix_list"),
                "EgressOnlyInternetGatewayId": res.get("egress_only_internet_gateway"),
                "GatewayId": gateway_id,
                "InstanceId": res.get("instance"),
                "LocalTarget": local_target,
                "NatGatewayId": res.get("nat_gateway"),
                "TransitGatewayId": res.get("transit_gateway"),
                "LocalGatewayid": res.get("local_gateway"),
                "NetworkInterfaceId": res.get("network_interface"),
                "RouteTableId": res["route_table"],
                "VpcPeeringConnectionId": res.get("vpc_peering_connection"),
            }
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.replace_route, params)


def replace_route_table_association(
    association_id: str = None,
    current_route_table_lookup: Mapping = None,
    route_table_id: str = None,
    route_table_lookup: Mapping = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Changes the route table associated with a given subnet, internet gateway, or
    virtual private gateway in a VPC. After the operation completes, the subnet
    or gateway uses the routes in the new route table.

    You can also use this operation to change which table is the main route table
    in the VPC. Specify the main route table's association ID and the route table
    ID of the new main route table.

    :param str association_id: The association ID.
    :param dict current_route_table_lookup: Any kwarg that :py:func:`lookup_route_table`
      accepts. Used to lookup ``association_id``.
    :param str route_table_id: The ID of the new route table to associate with
      the subnet.
    :param dict route_table_lookup: Any kwarg that :py:func:`lookup_route_table`
      accepts. Used to lookup ``route_table_id``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``replace_route_table_association``-
      call on succes.
    """
    if not association_id:
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "ec2",
                "name": "route_table",
                "kwargs": current_route_table_lookup,
                "result_keys": ["RouteTableId", "Associations"],
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            current_route_table_id = res["result"]["route_table"]["RouteTableId"]
            association_id = [
                item["RouteTableAssociationId"]
                for item in res["result"]["route_table"]["Associations"]
                if item["RouteTableId"] == current_route_table_id
            ][0]
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "route_table",
            "kwargs": route_table_lookup or {"route_table_id": route_table_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "AssociationId": association_id,
            "RouteTableId": res["result"]["route_table"],
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](
        client.replace_route_table_association, params
    )


@_arguments_to_list("launch_specifications")
def request_spot_fleet(
    iam_fleet_role: str,
    target_capacity: int,
    allocation_strategy: str = None,
    on_demand_allocation_strategy: str = None,
    excess_capacity_termination_policy: str = None,
    fulfilled_capacity: float = None,
    on_demand_fulfilled_capacity: float = None,
    launch_specifications: Union[Mapping, Iterable[Mapping]] = None,
    launch_template_configs: Iterable[Mapping] = None,
    spot_price: str = None,
    on_demand_target_capacity: int = None,
    on_demand_max_total_price: str = None,
    spot_max_total_price: str = None,
    terminate_instances_with_expiration: bool = None,
    request_type: str = None,
    valid_from: datetime = None,
    valid_until: datetime = None,
    replace_unhealthy_instances: bool = None,
    instance_interruption_behavior: str = None,
    load_balancers_config: Mapping = None,
    instance_pools_to_use_count: int = None,
    tags: Mapping = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a Spot Fleet request.

    The Spot Fleet request specifies the total target capacity and the On-Demand
    target capacity. Amazon EC2 calculates the difference between the total capacity
    and On-Demand capacity, and launches the difference as Spot capacity.

    You can submit a single request that includes multiple launch specifications
    that vary by instance type, AMI, Availability Zone, or subnet.

    By default, the Spot Fleet requests Spot Instances in the Spot Instance pool
    where the price per unit is the lowest. Each launch specification can include
    its own instance weighting that reflects the value of the instance type to
    your application workload.

    Alternatively, you can specify that the Spot Fleet distribute the target capacity
    across the Spot pools included in its launch specifications. By ensuring that
    the Spot Instances in your Spot Fleet are in different Spot pools, you can
    improve the availability of your fleet.

    You can specify tags for the Spot Fleet request and instances launched by the
    fleet. You cannot tag other resource types in a Spot Fleet request because
    only the spot-fleet-request and instance resource types are supported.

    :param str iam_fleet_role: The Amazon Resource Name (ARN) of an AWS Identity
      and Access Management (IAM) role that grants the Spot Fleet the permission
      to request, launch, terminate, and tag instances on your behalf.
      Spot Fleet can terminate Spot Instances on your behalf when you cancel its
      Spot Fleet request using :py:func:`cancel_spot_fleet_requests` or when the
      Spot Fleet request expires, if you set ``terminate_instances_with_expiration``.
    :param int target_capacity: The number of units to request for the Spot Fleet.
      You can choose to set the target capacity in terms of instances or a performance
      characteristic that is important to your application workload, such as vCPUs,
      memory, or I/O. If the request type is maintain , you can specify a target
      capacity of 0 and add capacity later.
    :param str allocation_strategy: Indicates how to allocate the target Spot Instance
      capacity across the Spot Instance pools specified by the Spot Fleet request.
      If the allocation strategy is ``lowestPrice``, Spot Fleet launches instances
      from the Spot Instance pools with the lowest price. This is the default allocation
      strategy.
      If the allocation strategy is ``diversified``, Spot Fleet launches instances
      from all the Spot Instance pools that you specify.
      If the allocation strategy is ``capacityOptimized``, Spot Fleet launches
      instances from Spot Instance pools with optimal capacity for the number of
      instances that are launching.
    :param str on_demand_allocation_strategy: The order of the launch template
      overrides to use in fulfilling On-Demand capacity. If you specify ``lowestPrice``,
      Spot Fleet uses price to determine the order, launching the lowest price
      first. If you specify ``prioritized``, Spot Fleet uses the priority that
      you assign to each Spot Fleet launch template override, launching the highest
      priority first. If you do not specify a value, Spot Fleet defaults to ``lowestPrice``.
    :param str excess_capacity_termination_policy: Indicates whether running Spot
      Instances should be terminated if you decrease the target capacity of the
      Spot Fleet request below the current size of the Spot Fleet.
      Allowed values: noTermination, default
    :param float fulfilled_capacity: The number of units fulfilled by this request
      compared to the set target capacity. You cannot set this value.
    :param float on_demand_fulfilled_capacity: The number of On-Demand units fulfilled
      by this request compared to the set target On-Demand capacity.
    :type launch_specifications: dict or list(dict)
    :param launch_specifications: The launch specifications for the
      Spot Fleet request. If you specify ``launch_specifications``, you can't specify
      ``launch_template_configs``. If you include On-Demand capacity in your request,
      you must use ``launch_template_configs``. These dicts either contain the structure
      described `<here https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_SpotFleetLaunchSpecification.html>`__
      or the kwargs that :py:func:`build_launch_specification` accepts.
    :param list(dict) launch_template_configs: The launch template and overrides.
      If you specify ``launch_template_configs``, you can't specify ``launch_specifications``.
      If you include On-Demand capacity in your request, you must use ``launch_template_configs``.
      These dicts consist of:

      - LaunchTemplateSpecification (dict): The launch template. This dict consists of:

        - LaunchTemplateId (str): The ID of the launch template. If you specify
          the template ID, you can't specify the template name.
        - LaunchTempalteName (str): The name of the launch template. If you specify
          the template name, you can't specify the template ID.
        - Version (str): The launch template version number, ``$Latest``, or ``$Default``.
          You must specify a value, otherwise the request fails.
          If the value is ``$Latest``, Amazon EC2 uses the latest version of the
          launch template.
          If the value is ``$Default``, Amazon EC2 uses the default version of
          the launch template.
      - Overrides (list(dict)): Any parameters that you specify override the same
        parameters in the launch template. These dicts consist of:

        - InstanceType (str): The instance type.
        - SpotPrice (str): The maximum price per unit hour that you are willing
          to pay for a Spot Instance.
        - SubnetId (str): The ID of the subnet in which to launch the instances.
        - AvailabilityZone (str): The Availability Zone in which to launch the instances.
        - WeightedCapacity (float): The number of units provided by the specified
          instance type.
        - Priority (int): The priority for the launch template override.
          If ``on_demand_allocation_strategy`` is set to ``prioritized``, Spot
          Fleet uses priority to determine which launch template override to use
          first in fulfilling On-Demand capacity. The highest priority is launched
          first. Valid values are whole numbers starting at 0. The lower the number,
          the higher the priority. If no number is set, the launch template override
          has the lowest priority.
    :param str spot_price: The maximum price per unit hour that you are willing
      to pay for a Spot Instance. The default is the On-Demand price.
    :param int on_demand_target_capacity: The number of On-Demand units to request.
      You can choose to set the target capacity in terms of instances or a performance
      characteristic that is important to your application workload, such as vCPUs,
      memory, or I/O. If the request type is maintain , you can specify a target
      capacity of 0 and add capacity later.
    :param str on_demand_max_total_price: The maximum amount per hour for On-Demand
      Instances that you're willing to pay. You can use the ``on_demand_max_total_price``
      parameter, the ``spot_max_total_price`` parameter, or both parameters to
      ensure that your fleet cost does not exceed your budget. If you set a maximum
      price per hour for the On-Demand Instances and Spot Instances in your request,
      Spot Fleet will launch instances until it reaches the maximum amount you're
      willing to pay. When the maximum amount you're willing to pay is reached,
      the fleet stops launching instances even if it hasn’t met the target capacity.
    :param str spot_max_total_price: The maximum amount per hour for Spot Instances
      that you're willing to pay. You can use the ``spot_max_total_price`` parameter,
      the ``on_demand_max_total_price`` parameter, or both parameters to ensure that
      your fleet cost does not exceed your budget. If you set a maximum price per
      hour for the On-Demand Instances and Spot Instances in your request, Spot
      Fleet will launch instances until it reaches the maximum amount you're willing
      to pay. When the maximum amount you're willing to pay is reached, the fleet
      stops launching instances even if it hasn’t met the target capacity.
    :param bool terminate_instances_with_expiration: Indicates whether running Spot
      Instances are terminated when the Spot Fleet request expires.
    :param str request_type: The type of request. Indicates whether the Spot Fleet
      only requests the target capacity or also attempts to maintain it. When this
      value is ``request``, the Spot Fleet only places the required requests. It
      does not attempt to replenish Spot Instances if capacity is diminished, nor
      does it submit requests in alternative Spot pools if capacity is not available.
      When this value is ``maintain``, the Spot Fleet maintains the target capacity.
      The Spot Fleet places the required requests to meet capacity and automatically
      replenishes any interrupted instances. Default: ``maintain``. ``instant`` is
      listed but is not used by Spot Fleet.
    :param datetime valid_from: The start date and time of the request, in UTC
      format (YYYY-MM-DDT*HH*:MM:SS Z). By default, Amazon EC2 starts fulfilling
      the request immediately.
    :param datetime valid_until: The end date and time of the request, in UTC format
      (YYYY-MM-DDT*HH*:MM:SS Z). After the end date and time, no new Spot
      Instance requests are placed or able to fulfill the request. If no value
      is specified, the Spot Fleet request remains until you cancel it.
    :param bool replace_unhealthy_instances: Indicates whether Spot Fleet should
      replace unhealthy instances.
    :param str instance_interruption_behavior: The behavior when a Spot Instance
      is interrupted. Allowed values: hibernate, stop, terminate. Default: terminate.
    :param dict load_balancers_config: One or more Classic Load Balancers and target
      groups to attach to the Spot Fleet request. Spot Fleet registers the running
      Spot Instances with the specified Classic Load Balancers and target groups.
      With Network Load Balancers, Spot Fleet cannot register instances that have
      the following instance types: C1, CC1, CC2, CG1, CG2, CR1, CS1, G1, G2, HI1,
      HS1, M1, M2, M3, and T1. This dict consists of:

      - ClassicLoadBalancersConfig (dict): The Classic Load Balancers:

        - ClassicLoadBalancers (list(dict)): One or more Classic Load Balancers.
          These dicts consist of:

          - Name (str): The name of the load balancer.
      - TargetGroupsConfig (dict): The target groups:

        - TargetGroups (list(dict)): One or more target groups. These dicts consist of:

          - Arn (str): The Amazon Resource Name (ARN) of the target group.
    :param int instance_pools_to_use_count: The number of Spot pools across which
      to allocate your target Spot capacity. Valid only when Spot ``allocation_strategy``
      is set to ``lowest-price``. Spot Fleet selects the cheapest Spot pools and
      evenly allocates your target Spot capacity across the number of Spot pools
      that you specify.
    :param dict tags: The tags to appy to the Spot Fleet request. To tag instances
      at launch, specify the tags in the launch template (valid only if you use
      ``launch_template_configs``) or in the ``spot_fleet_tag_specification``
      (valid only if you use ``launch_specifications``).
    :param bool blocking: Wait until the spot fleet request has been fulfilled.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``request_spot_fleet``-call
      on succes.
    """
    try:
        launch_specifications = [
            build_launch_specification(item)["result"] for item in launch_specifications
        ]
    except (TypeError, KeyError):
        pass  # to Boto as-is.
    params = salt.utils.data.filter_falsey(
        {
            "SpotFleetRequestConfig": {
                "AllocationStrategy": allocation_strategy,
                "OnDemandAllocationStrategy": on_demand_allocation_strategy,
                "ExcessCapacityTerminationPolicy": excess_capacity_termination_policy,
                "FulfilledCapacity": fulfilled_capacity,
                "OnDemandFulfilledCapacity": on_demand_fulfilled_capacity,
                "IamFleetRole": iam_fleet_role,
                "LaunchSpecifications": launch_specifications,
                "LaunchTemplateConfigs": launch_template_configs,
                "SpotPrice": spot_price,
                "TargetCapacity": target_capacity,
                "OnDemandTargetCapacity": on_demand_target_capacity,
                "OnDemandMaxTotalPrice": on_demand_max_total_price,
                "SpotMaxTotalPrice": spot_max_total_price,
                "TerminateInstancesWithExpiration": terminate_instances_with_expiration,
                "Type": request_type,
                "ValidFrom": valid_from,
                "ValidUntil": valid_until,
                "ReplaceUnhealthyInstances": replace_unhealthy_instances,
                "InstanceInterruptionBehavior": instance_interruption_behavior,
                "LoadBalancersConfig": load_balancers_config,
                "InstancePoolsToUseCount": instance_pools_to_use_count,
            },
        }
    )
    params.update(
        {"ClientToken": hashlib.sha1(json.dumps(params).encode("utf8")).hexdigest()}
    )
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"],
        "spot_fleet_request",
        boto_function_name="request_spot_fleet",
        params=params,
        tags=tags,
        wait_until_state="fulfilled" if blocking else None,
        client=client,
    )


def request_spot_instances(
    availability_zone_group: str = None,
    block_duration_minutes: int = None,
    instance_count: int = None,
    launch_group: str = None,
    launch_specification: Mapping = None,
    spot_price: str = None,
    request_type: str = None,
    valid_from: datetime = None,
    valid_until: datetime = None,
    tags: Mapping = None,
    instance_interruption_behavior: str = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Creates a Spot Instance request.

    :param str availability_zone_group: The user-specified name for a logical grouping
      of requests. When you specify an Availability Zone group in a Spot Instance
      request, all Spot Instances in the request are launched in the same Availability
      Zone. Instance proximity is maintained with this parameter, but the choice
      of Availability Zone is not. The group applies only to requests for Spot
      Instances of the same instance type. Any additional Spot Instance requests
      that are specified with the same Availability Zone group name are launched
      in that same Availability Zone, as long as at least one instance from the
      group is still active.
      If there is no active instance running in the Availability Zone group that
      you specify for a new Spot Instance request (all instances are terminated,
      the request is expired, or the maximum price you specified falls below current
      Spot price), then Amazon EC2 launches the instance in any Availability Zone
      where the constraint can be met. Consequently, the subsequent set of Spot
      Instances could be placed in a different zone from the original request,
      even if you specified the same Availability Zone group.
      Default: Instances are launched in any available Availability Zone.
    :param int block_duration_minutes: The required duration for the Spot Instances
      (also known as Spot blocks), in minutes. This value must be a multiple of
      60 (60, 120, 180, 240, 300, or 360).
      The duration period starts as soon as your Spot Instance receives its instance
      ID. At the end of the duration period, Amazon EC2 marks the Spot Instance
      for termination and provides a Spot Instance termination notice, which gives
      the instance a two-minute warning before it terminates.
      You can't specify an Availability Zone group or a launch group if you specify
      a duration.
    :param int instance_count: The maximum number of Spot Instances to launch.
      Default: 1
    :param str launch_group: The instance launch group. Launch groups are Spot
      Instances that launch together and terminate together.
      Default: Instances are launched and terminated individually
    :param dict launch_specification: The launch specification. This dict either
      contains the structure described `here <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_RequestSpotLaunchSpecification.html>`__
      or the kwargs that :py:func:`build_launch_specification` accepts.
    :param str spot_price:  The maximum price per hour that you are willing to
       pay for a Spot Instance. The default is the On-Demand price.
    :param str request_type: The Spot Instance request type.
       Allowed values: one-time, persistent. Default: one-time
    :param datetime valid_from: The start date of the request. If this is a one-time
      request, the request becomes active at this date and time and remains active
      until all instances launch, the request expires, or the request is canceled.
      If the request is persistent, the request becomes active at this date and
      time and remains active until it expires or is canceled.
      The specified start date and time cannot be equal to the current date and
      time. You must specify a start date and time that occurs after the current
      date and time.
    :param datetime valid_until: The end date of the request. If this is a one-time
      request, the request remains active until all instances launch, the request
      is canceled, or this date is reached. If the request is persistent, it remains
      active until it is canceled or this date is reached. The default end date
      is 7 days from the current date.
    :param dict tags: The tags to apply to the Spot Instance request.
    :param str instance_interruption_behavior: The behavior when a Spot Instance
      is interrupted. Allowed values: hibernate, stop, terminate. Default: terminate.
    :param bool blocking: Wait until the request has been fulfilled.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``request_spot_instances``-call
      on succes.
    """
    try:
        launch_specification = build_launch_specification(launch_specification)[
            "result"
        ]
    except (TypeError, KeyError):
        pass  # to Boto as-is
    params = salt.utils.data.filter_falsey(
        {
            "AvailabilityZoneGroup": availability_zone_group,
            "BlockDurationMinutes": block_duration_minutes,
            "InstanceCount": instance_count,
            "LaunchGroup": launch_group,
            "LaunchSpecification": launch_specification,
            "SpotPrice": spot_price,
            "Type": request_type,
            "ValidFrom": valid_from,
            "ValidUntil": valid_until,
            "InstanceInterruptionBehavior": instance_interruption_behavior,
        }
    )
    params.update(
        {"ClientToken": hashlib.sha1(json.dumps(params).encode("utf8")).hexdigest()}
    )
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](
        __utils__["boto3.create_resource"],
        "spot_instance_request",
        boto_function_name="request_spot_instances",
        params=params,
        tags=tags,
        wait_until_state="fulfilled" if blocking else None,
        client=client,
    )


@_arguments_to_list("ip_permissions")
def revoke_security_group_egress(
    group_id: str = None,
    group_lookup: Mapping = None,
    ip_permissions: Union[Mapping, Iterable[Mapping]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    [VPC only] Removes the specified egress rules from a security group for EC2-VPC.
    This action doesn't apply to security groups for use in EC2-Classic. To remove
    a rule, the values that you specify (for example, ports) must match the existing
    rule's values exactly.

    Each rule consists of the protocol and the IPv4 or IPv6 CIDR range or source
    security group. For the TCP and UDP protocols, you must also specify the destination
    port or range of ports. For the ICMP protocol, you must also specify the ICMP
    type and code. If the security group rule has a description, you do not have
    to specify the description to revoke the rule.

    Rule changes are propagated to instances within the security group as quickly
    as possible. However, a small delay might occur.

    :param str group_id: The ID of the security group to revoke egress rules from.
    :param dict group_lookup: Any kwarg that :py:func:`lookup_security_group` accepts.
      Used to lookup ``security_group_id``.
    :type ip_permissions: dict or list(dict)
    :param ip_permissions: One or more IP permissions. You can't specify
      a destination security group and a CIDR IP address range in the same set
      of permissions. These dicts can either contain the structure as described
      `here <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_IpPermission.html>`__
      or contain the kwargs that :py:func:`build_ip_permission` accepts.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
    try:
        ip_permissions = [
            build_ip_permission(item)["result"] for item in ip_permissions
        ]
    except (TypeError, KeyError):
        pass  # to Boto as-is
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": group_lookup or {"group_id": group_id},
            "result_keys": "GroupId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "GroupId": res["result"]["security_group"],
            "IpPermissions": ip_permissions,
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](
        client.revoke_security_group_egress, params
    )


@_arguments_to_list("ip_permissions")
def revoke_security_group_ingress(
    group_id: str = None,
    group_lookup: Mapping = None,
    ip_permissions: Union[Mapping, Iterable[Mapping]] = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Removes the specified ingress rules from a security group. To remove a rule,
    the values that you specify (for example, ports) must match the existing rule's
    values exactly.

    Note: [EC2-Classic only] If the values you specify do not match the existing
    rule's values, no error is returned. Use DescribeSecurityGroups to verify that
    the rule has been removed.

    Each rule consists of the protocol and the CIDR range or source security group.
    For the TCP and UDP protocols, you must also specify the destination port or
    range of ports. For the ICMP protocol, you must also specify the ICMP type and
    code. If the security group rule has a description, you do not have to specify
    the description to revoke the rule.

    Rule changes are propagated to instances within the security group as quickly
    as possible. However, a small delay might occur.

    :param str group_id: The ID of the security group to revoke egress rules from.
    :param dict group_lookup: Any kwarg that :py:func:`lookup_security_group` accepts.
      Used to lookup ``security_group_id``.
    :type ip_permissions: dict or list(dict)
    :param ip_permissions: One or more IP permissions. You can't specify
      a source security group and a CIDR IP address range in the same set
      of permissions. These dicts can either contain the structure as described
      `here <https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_IpPermission.html>`__
      or contain the kwargs that :py:func:`build_ip_permission` accepts.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
    try:
        ip_permissions = [
            build_ip_permission(item)["result"] for item in ip_permissions
        ]
    except (TypeError, KeyError):
        pass  # to Boto as-is
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "security_group",
            "kwargs": group_lookup or {"group_id": group_id},
            "result_keys": "GroupId",
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "GroupId": res["result"]["security_group"],
            "IpPermissions": ip_permissions,
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](
        client.revoke_security_group_ingress, params
    )


@_arguments_to_list("instance_ids", "instance_lookups")
def start_instances(
    instance_ids: Union[str, Iterable[str]] = None,
    instance_lookups: Union[Mapping, Iterable[Mapping]] = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Starts an Amazon EBS-backed instance that you've previously stopped.

    Instances that use Amazon EBS volumes as their root devices can be quickly
    stopped and started. When an instance is stopped, the compute resources are
    released and you are not billed for instance usage. However, your root partition
    Amazon EBS volume remains and continues to persist your data, and you are charged
    for Amazon EBS volume usage. You can restart your instance at any time. Every
    time you start your Windows instance, Amazon EC2 charges you for a full instance
    hour. If you stop and restart your Windows instance, a new instance hour begins
    and Amazon EC2 charges you for another full instance hour even if you are still
    within the same 60-minute period when it was stopped. Every time you start
    your Linux instance, Amazon EC2 charges a one-minute minimum for instance usage,
    and thereafter charges per second for instance usage.

    Before stopping an instance, make sure it is in a state from which it can be
    restarted. Stopping an instance does not preserve data stored in RAM.

    Performing this operation on an instance that uses an instance store as its
    root device returns an error.

    :type instance_ids: str or list(str)
    :param instance_ids: The IDs of the instances.
    :type instance_lookups: dict or list(dict)
    :param instance_lookups: One or more dicts of kwargs that
      :py:func:`lookup_instance` accepts. Used to lookup ``instance_ids``.
    :param bool blocking: Wait until all the instances are running.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``start_instances``-call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookups
            or [{"instance_id": instance_id} for instance_id in instance_ids or []],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        instance_ids = res["result"]["instance"]
    params = {"InstanceIds": instance_ids}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](client.start_instances, params)
    if "error" in res:
        return res
    if blocking:
        __utils__["boto3.wait_resource"](
            "instance",
            "running",
            resource_id=instance_ids,
            client=client,
        )
    return res


@_arguments_to_list("instance_ids", "instance_lookups")
def stop_instances(
    instance_ids: Union[str, Iterable[str]] = None,
    instance_lookups: Union[Mapping, Iterable[Mapping]] = None,
    hibernate: bool = None,
    force: bool = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Stops an Amazon EBS-backed instance.

    You can use the Stop action to hibernate an instance if the instance is enabled
    for hibernation and it meets the hibernation prerequisites.

    We don't charge usage for a stopped instance, or data transfer fees; however,
    your root partition Amazon EBS volume remains and continues to persist your
    data, and you are charged for Amazon EBS volume usage. Every time you start
    your Windows instance, Amazon EC2 charges you for a full instance hour. If
    you stop and restart your Windows instance, a new instance hour begins and
    Amazon EC2 charges you for another full instance hour even if you are still
    within the same 60-minute period when it was stopped. Every time you start
    your Linux instance, Amazon EC2 charges a one-minute minimum for instance usage,
    and thereafter charges per second for instance usage.

    You can't stop or hibernate instance store-backed instances. You can't use
    the Stop action to hibernate Spot Instances, but you can specify that Amazon
    EC2 should hibernate Spot Instances when they are interrupted.

    When you stop or hibernate an instance, we shut it down. You can restart your
    instance at any time. Before stopping or hibernating an instance, make sure
    it is in a state from which it can be restarted. Stopping an instance does
    not preserve data stored in RAM, but hibernating an instance does preserve
    data stored in RAM. If an instance cannot hibernate successfully, a normal
    shutdown occurs.

    Stopping and hibernating an instance is different to rebooting or terminating
    it. For example, when you stop or hibernate an instance, the root device and
    any other devices attached to the instance persist. When you terminate an instance,
    the root device and any other devices attached during the instance launch are
    automatically deleted.

    When you stop an instance, we attempt to shut it down forcibly after a short
    while. If your instance appears stuck in the stopping state after a period
    of time, there may be an issue with the underlying host computer.

    :type instance_ids: str or list(str)
    :param instance_ids: The IDs of the instances.
    :type instance_lookups: dict or list(dict)
    :param instance_lookups: One or more dicts of kwargs that
      :py:func:`lookup_instance` accepts. Used to lookup ``instance_ids``.
    :param bool hibernate: Hibernates the instance if the instance was enabled
      for hibernation at launch. If the instance cannot hibernate successfully,
      a normal shutdown occurs.
    :param bool force: Forces the instances to stop. The instances do not have
      an opportunity to flush file system caches or file system metadata. If you
      use this option, you must perform file system check and repair procedures.
      This option is not recommended for Windows instances.
      Default: ``False``
    :param bool blocking: Wait until all instances are stopped.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``stop_instances``-call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookups
            or [{"instance_id": instance_id} for instance_id in instance_ids or []],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        instance_ids = res["result"]["instance"]
    params = salt.utils.data.filter_falsey(
        {"InstanceIds": instance_ids, "Hibernate": hibernate, "Force": force}
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](client.stop_instances, params)
    if "error" in res:
        return res
    if blocking:
        __utils__["boto3.wait_resource"](
            "instance",
            "stopped",
            resource_id=instance_ids,
            client=client,
        )
    return res


@_arguments_to_list("instance_ids", "instance_lookups")
def terminate_instances(
    instance_ids: Union[str, Iterable[str]] = None,
    instance_lookups: Union[Mapping, Iterable[Mapping]] = None,
    blocking: bool = None,
    region: str = None,
    keyid: str = None,
    key: str = None,
    profile: Mapping = None,
) -> Dict:
    """
    Shuts down the specified instances. This operation is idempotent; if you terminate
    an instance more than once, each call succeeds.

    If you specify multiple instances and the request fails (for example, because
    of a single incorrect instance ID), none of the instances are terminated.

    Terminated instances remain visible after termination (for approximately one hour).

    By default, Amazon EC2 deletes all EBS volumes that were attached when the
    instance launched. Volumes attached after instance launch continue running.

    You can stop, start, and terminate EBS-backed instances. You can only terminate
    instance store-backed instances. What happens to an instance differs if you
    stop it or terminate it. For example, when you stop an instance, the root device
    and any other devices attached to the instance persist. When you terminate an
    instance, any attached EBS volumes with the DeleteOnTermination block device
    mapping parameter set to true are automatically deleted.

    :type instance_ids: str or list(str)
    :param instance_ids: The IDs of the instances.
      Constraints: Up to 1000 instance IDs. We recommend breaking up this request
      into smaller batches.
    :type instance_lookups: dict or list(dict)
    :param instance_lookups: One or more dicts of kwargs that
      :py:func:`lookup_instance` accepts. Used to lookup ``instance_ids``.
    :param bool blocking: Wait until all instances are terminated.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``terminate_instances``-call
      on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "instance",
            "kwargs": instance_lookups
            or [{"instance_id": instance_id} for instance_id in instance_ids or []],
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        instance_ids = res["result"]["instance"]
    params = {"InstanceIds": instance_ids}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.handle_response"](client.terminate_instances, params)
    if "error" in res:
        return res
    if blocking:
        __utils__["boto3.wait_resource"](
            "instance",
            "terminated",
            resource_id=instance_ids,
            client=client,
        )
    return res


# This has to be at the end of the file
MODULE_FUNCTIONS = {
    k: v for k, v in inspect.getmembers(sys.modules[__name__]) if inspect.isfunction(v)
}
