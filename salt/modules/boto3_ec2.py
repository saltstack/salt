"""
Connection module for Amazon EC2/VPC.
Be aware that this interacts with Amazon's services, and so may incur charges.

:configuration: This module accepts explicit IAM credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

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

:depends: boto3
"""
# Import Python libs
import hashlib
import inspect
import itertools
import json
import logging
import sys

# Import Salt libs
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
# Import third party libs
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


def arguments_to_list(*args):
    """
    Decorator function to specify arguments to _listify

    :param list(str) args: keywords of kwargs of called function to _listify.
    """

    def _listify(thing):
        """
        Helper function to convert thing into [thing] if it is not already a list.
        Used in functions that accept a thing or a list of things to internally
        always handle it as a list of things.
        Note: Does nothing when ``thing`` is ``None``.

        :param any thing: Something to put in a list or not.

        :rtype: list
        """
        return [thing] if thing is not None and not isinstance(thing, list) else thing

    def decorator(func):
        def wrapper(*f_args, **f_kwargs):
            for keyword in args:
                if keyword in f_kwargs:
                    f_kwargs[keyword] = _listify(f_kwargs[keyword])
            return func(*f_args, **f_kwargs)

        return wrapper

    return decorator


def _derive_ipv6_cidr_subnet(ipv6_subnet, ipv6_parent_block):
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
    (ipv6_parent_block, _) = ipv6_parent_block.split("/")
    ipv6_parent_block = ipv6_parent_block.split(":")
    res = (":".join(ipv6_parent_block[:-2]))[:-2] + "{:02d}::/64".format(ipv6_subnet)
    log.debug("%s:derive_ipv6_cidr_subnet:\n" "\t\tres: %s", __name__, res)
    return res


@arguments_to_list("vpc_endpoint_ids", "vpc_endpoint_lookups")
def accept_vpc_endpoint_connections(
    service_id=None,
    service_lookup=None,
    vpc_endpoint_ids=None,
    vpc_endpoint_lookups=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Accepts one or more interface VPC endpoint connection requests to your VPC
    endpoint service.

    :param str service_id: The ID of the VPC endpoint service.
    :param dict service_lookup: Any kwarg that ``lookup_vpc_endpoint_service``
      accepts. Used to lookup the ``service_id`` if it is not provided.
    :param str/list(str) vpc_endpoint_ids: The (list of) ID(s) of the interface
      VPC endpoint(s).
    :param dict/list(dict) vpc_endpoint_lookups: One or more dicts of kwargs that
      ``lookup_vpc_endpoint`` accepts. Used to lookup any ``vpc_endpoint_ids``
      if none are provided.

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
    vpc_peering_connection_id=None,
    vpc_peering_connection_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Accept a VPC peering connection request. To accept a request, the VPC peering
    connection must be in the pending-acceptance state, and you must be the owner
    of the peer VPC. Use DescribeVpcPeeringConnections to view your outstanding
    VPC peering connection requests.

    For an inter-region VPC peering connection request, you must accept the VPC
    peering connection in the region of the accepter VPC.

    :param str vpc_peering_connection_id: The ID of the VPC peering connection.
    :param dict vpc_peering_lookup: Any kwarg that ``lookup_vpc_peering_connection``
      accepts. Used to lookup the ``vpc_peering_connection_id`` if it is not provided.

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
    address=None, public_ipv4_pool=None, region=None, keyid=None, key=None, profile=None
):
    """
    Allocates an Elastic IP address to your AWS account. After you allocate the
    Elastic IP address you can associate it with an instance or network interface.
    After you release an Elastic IP address, it is released to the IP address pool
    and can be allocated to a different AWS account.
    You can allocate an Elastic IP address from an address pool owned by AWS or
    from an address pool created from a public IPv4 address range that you have
    brought to AWS for use with your AWS resources using bring your own IP addresses
    (BYOIP). For more information, see Bring Your Own IP Addresses (BYOIP) in the
    Amazon Elastic Compute Cloud User Guide .
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
      specify a specific address from the address pool, use the Address parameter
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
    allocation_id=None,
    address_lookup=None,
    instance_id=None,
    instance_lookup=None,
    public_ip=None,
    allow_reassociation=None,
    network_interface_id=None,
    network_interface_lookup=None,
    private_ip_address=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict address_lookup: [EC2-VPC] Any kwarg that ``lookup_address`` accepts.
      When ``allocation_id`` is not provided, this is required, otherwise ignored.
    :param str instance_id: The ID of the instance. This is required for EC2-Classic.
      For EC2-VPC, you can specify either the instance ID or the network interface
      ID, but not both. The operation fails if you specify an instance ID unless
      exactly one network interface is attached.
    :param dict instance_lookup: Any kwarg that ``lookup_instance`` accepts. Used
      to lookup the ``instance_id`` if it is not provided.
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
    :param dict network_interface_lookup: [EC2-VPC] Any kwarg that ``lookup_network_interface``
      accepts. Used to lookup ``network_interface_id`` if it is not provided.
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
    dhcp_options_id=None,
    dhcp_options_lookup=None,
    vpc_id=None,
    vpc_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict dhcp_options_lookup: Any kwarg that lookup_dhcp_options accepts.
      When ``dhcp_options_id`` is not provided, this is required, otherwise ignored.
    :param str vpc_id: The ID of the VPC to associate the options with.
    :param dict vpc_lookup: Any kwarg that lookup_vpc accepts.
      When ``vpc_id`` is not provided, this is required, otherwise ignored.

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
    route_table_id=None,
    route_table_lookup=None,
    subnet_id=None,
    subnet_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Associates a subnet with a route table. The subnet and route table must be
    in the same VPC. This association causes traffic originating from the subnet
    to be routed according to the routes in the route table. The action returns
    an association ID, which you need in order to disassociate the route table
    from the subnet later. A route table can be associated with multiple subnets.

    :param str route_table_id: The ID of the route table to associate.
    :param dict route_table_lookup: Any kwarg that ``lookup_route_table`` accepts.
      Used to lookup the route_table's ID if ``route_table_id`` is not provided.
    :param str subnet_id: the ID of the subnet to associate with.
    :param dict subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Used to lookup the subnet's ID if ``subnet_id`` is not provided.

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
    subnet_id=None,
    subnet_lookup=None,
    ipv6_cidr_block=None,
    ipv6_subnet=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Associates a CIDR block with your subnet. You can only associate a single
    IPv6 CIDR block with your subnet. An IPv6 CIDR block must have a prefix length
    of /64.

    :param str subnet_id: The ID of the subnet to work on.
    :param dict subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Used to lookup the Subnet's ID if ``subnet_id`` is not provided.
    :param str ipv6_cidr_block: The IPv6 CIDR block for your subnet. The subnet
      must have a /64 prefix length. Exclusive with ipv6_subnet.
    :param int ipv6_subnet: The IPv6 subnet. This uses an implicit /64 netmask.
      Use this if you don't know the parent subnet and want to extract that
      from the VPC information. Exclusive with ipv6_cidr_block.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``associate_subnet_cidr_block``-
      call on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_subnets, boto3.client('ec2').describe_vpcs, boto3.client('ec2').associate_subnet_cidr_block
    """
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
    vpc_id=None,
    vpc_lookup=None,
    amazon_provided_ipv6_cidr_block=None,
    cidr_block=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Associates a CIDR block with your VPC. You can associate a secondary IPv4 CIDR
    block, or you can associate an Amazon-provided IPv6 CIDR block. The IPv6 CIDR
    block size is fixed at /56.

    :param str vpc_id: The ID of the VPC to operate on.
    :param str vpc_lookup: Any kwarg that lookup_vpc accepts.
      This is used to lookup the VPC when ``vpc_id`` is not provided, otherwise
      it is ignored.
    :param bool amazon_provided_ipv6_cidr_block: Requests an Amazon-provided IPv6
      CIDR block with a /56 prefix length for the VPC. You cannot specify the
      range of IPv6 addresses, or the size of the CIDR block.
    :param str cidr_block: An IPv4 CIDR block to associate with the VPC.

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
            }
        )
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.handle_response"](client.associate_vpc_cidr_block, params)


def attach_internet_gateway(
    internet_gateway_id=None,
    internet_gateway_lookup=None,
    vpc_id=None,
    vpc_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Attaches an internet gateway to a VPC, enabling connectivity between the
    internet and the VPC.

    :param str internet_gateway_id: The ID of the Internet gateway to attach.
    :param dict internet_gateway_lookup: Any kwarg that ``lookup_internet_gateway``
      accepts. Used to lookup the Internet gateway's ID if ``internet_gateway_id``
      is not provided.
    :param str vpc_id: The ID of the VPC to attach the Internet gateway to.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.

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
            "InternetgatewayId": res["internet_gateway"],
            "VpcId": res["vpc"],
        }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.attach_internet_gateway, params)


def attach_network_interface(
    device_index,
    instance_id=None,
    instance_lookup=None,
    network_interface_id=None,
    network_interface_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Attaches a network interface to an instance.

    :param int device_index: The index of the device for the network interface
      attachment.
    :param str instance_id: The ID of the instance.
    :param dict instance_lookup: Any kwarg that ``lookup_instance`` accepts.
      Used to lookup the instance's ID if ``instance_id`` is not provided.
    :param str network_interface_id: The ID of the network interface.
    :param dict network_interface_lookup: Any kwarg that ``lookup_network_interface``
      accepts. Used to lookup the network interface's ID if ``network_itnerface_id``
      is not provided.

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
    device,
    instance_id=None,
    instance_lookup=None,
    volume_id=None,
    volume_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict instance_lookup: Any kwarg that ``lookup_instance`` accepts.
      Used to lookup the instance's ID if ``instance_id`` is not provided.
    :param str volume_id: The ID of the EBS volume.  The volume and instance must
      be within the same Availability Zone.
    :param dict volume_lookup: Any kwarg that ``lookup_volume`` accepts.
      Used to lookup the volume's ID if ``volume_id`` is not provided.

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
    vpc_id=None,
    vpc_lookup=None,
    vpn_gateway_id=None,
    vpn_gateway_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Attaches a virtual private gateway to a VPC. You can attach one virtual private
    gateway to one VPC at a time.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC ID if ``vpc_id`` is not provided.
    :param str vpn_gateway_id: The ID of the virtual private gateway.
    :param dict vpn_gateway_lookup: Any kwarg that ``lookup_vpn_gateway`` accepts.
      Used to lookup the VPN gateway's ID if ``vpn_gateway_id`` is not provided.

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


def authorize_security_group_egress(
    group_id=None,
    group_lookup=None,
    ip_permissions=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict group_lookup: Any kwarg that ``lookup_security_group`` accepts.
      Used to lookup the security group's ID if ``security_group_id`` is not provided.
    :param list(dict) ip_permissions: The sets of IP permissions. You can't specify
      a destination security group and a CIDR IP address range in the same set
      of permissions. These sets consist of:

      - FromPort (int): The start of port range for the TCP and UDP protocols,
        or an ICMP/ICMPv6 type number. A value of -1 indicates all ICMP/ICMPv6
        types. If you specify all ICMP/ICMPv6 types, you must specify all codes.
      - IpProtocol (str): The IP protocol name (tcp, udp, icmp, icmpv6 ) or number.
        [VPC only] Use -1 to specify all protocols. When authorizing security
        group rules, specifying -1 or a protocol number other than tcp, udp,
        icmp, or icmpv6 allows traffic on all ports, regardless of any port range
        you specify. For tcp, udp, and icmp, you must specify a port range. For
        icmpv6, the port range is optional; if you omit the port range, traffic
        for all types and codes is allowed.
      - IpRanges (list(dict)): The IPv4 ranges. These consist of:

        - CidrIp (str): The IPv4 CIDR range. You can either specify a CIDR range
          or a source security group, not both. To specify a single IPv4 address,
          use the /32 prefix length.
        - Description: A description for the security group rule that references
          this IPv4 address range.

      - IPv6Ranges (list(dict)): The IPv6 ranges. These consist of:

        - CidrIpv6 (str): The IPv6 CIDR range. You can either specify a CIDR
          range or a source security group, not both. To specify a single IPv6
          address, use the /128 prefix length.
        - Description (str): A description for the security group rule that references
          this IPv6 address range.

      - PrefixListIds (list(dict)): The prefix list IDs. These consist of:

        - Description (str): A description for the security group rule that references
          this prefix list ID.
        - PrefixListId (str): The ID of the prefix.

      - ToPort (int): The end of port range for the TCP and UDP protocols, or
        an ICMP/ICMPv6 code. A value of -1 indicates all ICMP/ICMPv6 codes.
        If you specify all ICMP/ICMPv6 types, you must specify all codes.
      - UserIdGroupPairs (list(dict)): The security group and AWS account ID
        pairs. These consist of:

        - Description (str): A description for the security group rule that references
          this user ID group pair.
        - GroupId (str): The ID of the security group.
        - GroupName (str): The name of the security group. In a request, use
          this parameter for a security group in EC2-Classic or a default VPC
          only. For a security group in a nondefault VPC, use the security group ID.
          For a referenced security group in another VPC, this value is not returned
          if the referenced security group is deleted.
        - PeeringStatus (str): The status of a VPC peering connection, if applicable.
        - UserId (str): The ID of an AWS account.
          For a referenced security group in another VPC, the account ID of the
          referenced security group is returned in the response. If the referenced
          security group is deleted, this value is not returned.
          [EC2-Classic] Required when adding or removing rules that reference
          a security group in another AWS account.
        - VpcId (str): The ID of the VPC for the referenced security group,
          if applicable.
        - VpcPeeringConnectionId (str): The ID of the VPC peering connection,
          if applicable.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
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


def authorize_security_group_ingress(
    group_id=None,
    group_lookup=None,
    ip_permissions=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict group_lookup: Any kwarg that ``lookup_security_group`` accepts.
      Used to lookup the security group's ID if ``security_group_id`` is not provided.
    :param list(dict) ip_permissions: The sets of IP permissions. You can't specify
      a source security group and a CIDR IP address range in the same set
      of permissions. For the content specifications, see ``authorise_security_group_egress``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
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


@arguments_to_list("spot_fleet_request_ids", "spot_fleet_request_lookups")
def cancel_spot_fleet_requests(
    spot_fleet_requests_ids=None,
    spot_fleet_requests_lookups=None,
    terminate_instances=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Cancels the specified Spot Fleet requests.

    After you cancel a Spot Fleet request, the Spot Fleet launches no new Spot Instances.
    You must specify whether the Spot Fleet should also terminate its Spot Instances.
    If you terminate the instances, the Spot Fleet request enters the ``cancelled_terminating``
    state. Otherwise, the Spot Fleet request enters the ``cancelled_running`` state
    and the instances continue to run until they are interrupted or you terminate
    them manually.

    :param str/list(str) spot_fleet_request_ids: The IDs of the Spot Fleet requests.
    :param dict/list(dict) spot_fleet_request_lookups: Any kwarg or list of kwargs
      that ``lookup_spot_fleet_request`` accepts. Used to lookup the Spot Fleet
      request ID(s) if ``spot_fleet_request_ids`` is not provided.
    :param bool terminate_instances: Indicates whether to terminate instances for
      a Spot Fleet request if it is canceled successfully.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``cancel_spot_fleet_requests``-
      call on succes.
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "spot_fleet_requests",
            "kwargs": spot_fleet_requests_lookups
            or [
                {"spot_fleet_request_id": item}
                for item in spot_fleet_requests_ids or []
            ],
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
                "SpotFleetRequestIds": itertools.chain.from_iterable(
                    res["result"]["spot_fleet_requests"]
                ),
                "TerminateInstances": terminate_instances,
            }
        )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.cancel_spot_fleet_requests, params)


@arguments_to_list("spot_instance_request_ids", "spot_instance_request_lookups")
def cancel_spot_instance_requests(
    spot_instance_request_ids=None,
    spot_instance_request_lookups=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Cancels one or more Spot Instance requests.

    :param str/list(str) spot_instance_request_ids: One or more Spot Instance request IDs.
    :param dict/list(dict) spot_instance_request_lookups: Any kwarg or list of
      kwargs that ``lookup_spot_instance_request`` accepts. Used to lookup the
      Spot Instance request ID(s) if ``spot_instance_request_ids`` is not provided.

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
    name,
    source_region,
    source_image_id=None,
    source_image_lookup=None,
    description=None,
    encrypted=None,
    kms_key_id=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict source_image_lookup: Any kwarg that ``lookup_image`` accepts.
      Used to lookup the AMI ID if ``source_image_id`` is not provided.
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
    source_region,
    source_snapshot_id=None,
    source_snapshot_lookup=None,
    description=None,
    encrypted=None,
    kms_key_id=None,
    tags=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict source_snapshot_lookup: Any kwarg that ``lookup_snapshot`` accepts.
      Used to lookup the EBS snapshot ID if ``source_snapshot_id`` is not provided.
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
    bgp_asn,
    gateway_type,
    public_ip=None,
    certificate_arn=None,
    device_name=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
        "customer_gateway", params=params, tags=tags, client=client,
    )


def create_dhcp_options(
    domain_name_servers=None,
    domain_name=None,
    ntp_servers=None,
    netbios_name_servers=None,
    netbios_node_type=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
        "dhcp_options", params=params, tags=tags, client=client,
    )


def create_image(
    name,
    instance_id=None,
    instance_lookup=None,
    block_device_mappings=None,
    description=None,
    no_reboot=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict instance_lookup: Any kwarg that ``lookup_instance`` accepts.
      Used to lookup the instance's ID if ``instance_id`` is not provided.
    :param dict/list(dict) block_device_mappings: The block device mappings.
      This parameter cannot be used to modify the encryption status of existing
      volumes or snapshots. To create an AMI with encrypted snapshots, use the
      ``copy_image`` function. These dicts consist of:

      - DeviceName (str): The device name (for example, ``/dev/sdh`` or ``xvdh``).
      - VirtualName (str): The virtual device name (ephemeral N). Instance store
        volumes are numbered starting from 0. An instance type with 2 available
        instance store volumes can specify mappings for ``ephemeral0`` and ``ephemeral1``.
        The number of available instance store volumes depends on the instance type.
        After you connect to the instance, you must mount the volume.
        NVMe instance store volumes are automatically enumerated and assigned
        a device name. Including them in your block device mapping has no effect.
        Constraints: For M3 instances, you must specify instance store volumes
        in the block device mapping for the instance. When you launch an M3 instance,
        we ignore any instance store volumes specified in the block device mapping
        for the AMI.
      - Ebs (dict): Parameters used to automatically set up EBS volumes when
        the instance is launched. This dict consists of:

        - DeleteOnTermination (bool): Indicates whether the EBS volume is deleted
          on instance termination.
        - Iops (int): The number of I/O operations per second (IOPS) that the
          volume supports. For io1 volumes, this represents the number of IOPS
          that are provisioned for the volume. For gp2 volumes, this represents
          the baseline performance of the volume and the rate at which the volume
          accumulates I/O credits for bursting.
          Constraints: Range is 100-16,000 IOPS for gp2 volumes and 100 to 64,000
          IOPS for io1 volumes in most Regions. Maximum io1 IOPS of 64,000 is
          guaranteed only on Nitro-based instances. Other instance families guarantee
          performance up to 32,000 IOPS.
          Condition: This parameter is required for requests to create io1 volumes;
          it is not used in requests to create gp2, st1, sc1, or standard volumes.
        - SnapshotId (str): The ID of the snapshot.
        - VolumeSize (int): The size of the volume, in GiB.
          Default: If you're creating the volume from a snapshot and don't specify
          a volume size, the default is the snapshot size.
          Constraints: 1-16384 for General Purpose SSD (gp2), 4-16384 for Provisioned
          IOPS SSD (io1), 500-16384 for Throughput Optimized HDD (st1), 500-16384
          for Cold HDD (sc1), and 1-1024 for Magnetic (standard ) volumes. If
          you specify a snapshot, the volume size must be equal to or larger
          than the snapshot size.
        - VolumeType (str): The volume type. If you set the type to ``io1``,
          you must also specify the Iops parameter. If you set the type to ``gp2``,
          ``st1``, ``sc1``, or ``standard``, you must omit the Iops parameter.
          Default: ``gp2``
      - NoDevice (str): Suppresses the specified device included in the block
        device mapping of the AMI.
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
    vpc_id=None,
    vpc_lookup=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Creates an internet gateway for use with a VPC.
    Optionally attaches it to a VPC if it is specified via either ``vpc_id`` or
    ``vpc_lookup``.

    :param str vpc_id: The ID of the VPC to attach the IGW to after creation.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.
    :param dict tags: Tags to assign to the Internet gateway after creation.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``create_internet_gateway``-
      call on succes.

    :depends: boto3.client('ec2').create_internet_gateway, boto3.client('ec2').describe_internet_gateways, boto3.client('ec2').describe_vpcs, boto3.client('ec2').attach_internet_gateway
    """
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    res = __utils__["boto3.create_resource"](
        "internet_gateway", tags=tags, client=client,
    )
    if "error" in res:
        return res
    ret = res
    igw_id = res["result"].get("InternetGatewayId")
    if igw_id and (vpc_id or vpc_lookup):
        res2 = attach_internet_gateway(
            internet_gateway_id=igw_id,
            vpc_id=vpc_id,
            vpc_lookup=vpc_lookup,
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        )
        if "error" in res2:
            ret.update(res2)
    return ret


def create_key_pair(
    key_name, tags=None, region=None, keyid=None, key=None, profile=None
):
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
        "key_pair", params={"KeyName": key_name}, tags=tags, client=client,
    )


def create_launch_template(
    launch_template_name,
    version_description=None,
    kernel_id=None,
    ebs_optimized=None,
    iam_instance_profile=None,
    block_device_mappings=None,
    network_interfaces=None,
    image_id=None,
    image_lookup=None,
    instance_type=None,
    key_name=None,
    monitoring_enabled=None,
    placement=None,
    ram_disk_id=None,
    disable_api_termination=None,
    instance_initiated_shutdown_behavior=None,
    user_data=None,
    tag_specifications=None,
    elastic_gpu_type=None,
    elastic_inference_accelerators=None,
    security_group_ids=None,
    security_group_lookups=None,
    instance_market_options=None,
    credit_specification=None,
    cpu_options=None,
    capacity_reservation_specification=None,
    license_specifications=None,
    hibernation_configured=None,
    metadata_options=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param list(dict) block_device_mappings: The block device mapping.
      For a complete description of this, see :py:func:create_image.
    :param list(dict) network_interfaces: One or more network interfaces. If you
      specify a network interface, you must specify any security groups and subnets
      as part of the network interface. These dicts contsist of:

        - AssociateCarrierIpAddress (bool): Associates a Carrier IP address with
          eth0 for a new network interface. Use this option when you launch an instance
          in a Wavelength Zone and want to associate a Carrier IP address with the
          network interface.
        - AssociatePublicIpAddress (bool): Associates a public IPv4 address with
          eth0 for a new network interface.
        - DeleteOnTermination (bool): Indicates whether the network interface is
          deleted when the instance is terminated.
        - Description (str): A description for the network interface.
        - DeviceIndex (int): The device index for the network interface attachment.
        - Groups (list(str)): The IDs of one or more security groups.
        - InterfaceType (str): The type of network interface. To create an Elastic
          Fabric Adapter (EFA), specify ``efa``. If you are not creating an EFA,
          specify ``interface`` or omit this parameter.
          Allowed values: interface, efa.
        - Ipv6AddressCount (int): The number of IPv6 addresses to assign to a network
          interface. Amazon EC2 automatically selects the IPv6 addresses from the
          subnet range. You can't use this option if specifying specific IPv6 addresses.
        - Ipv6Addresses (list(dict)): One or more specific IPv6 addresses from
          the IPv6 CIDR block range of your subnet. You can't use this option if
          you're specifying a number of IPv6 addresses. The dict consists of:

            - Ipv6Address (str): The IPv6 address.
        - NetworkInterfaceId (str): The ID of the network interface.
        - PrivateIpAddress (str): The primary private IPv4 address of the network interface.
        - PrivateIpAddresses (list(dict)): One or more secondary private IPv4 addresses.
          The dict consists of:

            - Primary (bool): Indicates whether the private IPv4 address is the primary
              private IPv4 address. Only one IPv4 address can be designated as primary.
            - PrivateIpAddress (str): The private IPv4 address.
        - SecondaryPrivateIpAddressCount (int): The number of secondary private IPv4
          addresses to assign to a network interface.
        - SubnetId (str): The ID of the subnet for the network interface.
    :param str image_id: The ID of the AMI.
    :param dict image_lookup: Any kwarg that lookup_image accepts. used to
      lookup the image_id when ``image_id`` is not provided.
    :param str instance_type: The instance type.
    :param str key_name: The name of the key pair. You can create a key pair using
      ``create_key_pair`` or ``import_key_pair``.
      Warning: If you do not specify a key pair, you can't connect to the instance
      unless you choose an AMI that is configured to allow users another way
      to log in.
    :param bool monitoring_enabled: Specify true to enable detailed monitoring.
      Otherwise, basic monitoring is enabled.
    :param dict placement: The placement for the instance. The dict consiste of:

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
    :param elastic_gpu_type: The type of Elastic Graphics accelerator to associate
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
      that ``lookup_security_group`` accepts. Used to lookup security groups
      if ``security_group_ids`` is not provided.
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

            - open: The instance can run in any open Capacity Reservation that has
              matching attributes (instance type, platform, Availability Zone).
            - none: The instance avoids running in a Capacity Reservation even if
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
            or {"security_group_ids": security_group_ids},
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
        "launch_template", params=params, tags=tags, client=client,
    )


def create_nat_gateway(
    subnet_id=None,
    subnet_lookup=None,
    allocation_id=None,
    address_lookup=None,
    tags=None,
    blocking=False,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Creates a NAT gateway in the specified public subnet. This action creates a
    network interface in the specified subnet with a private IP address from the
    IP address range of the subnet. Internet-bound traffic from a private subnet
    can be routed to the NAT gateway, therefore enabling instances in the private
    subnet to connect to the internet.

    :param str subnet_id: The subnet in which to create the NAT gateway.
    :param dict subnet_lookup: Any kwarg that lookup_subnet accepts. Used to
      lookup the subnet_id when ``subnet_id`` is not provided.
    :param str allocation_id: The allocation ID of an Elastic IP address to
      associate with the NAT gateway. If the Elastic IP address is associated
      with another resource, you must first disassociate it.
    :param str address_lookup: Any kwarg that lookup_address accepts. used to
      lookup the allocation_id when ``allocation_id`` is not provided. You can,
      for example provide ``{'public_ip': '1.2.3.4'}`` to specify the Elastic IP
      to use for the NAT gateway.
      Either allocation_id or address_lookup must be specified.
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
    vpc_id=None,
    vpc_lookup=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Creates a network ACL in a VPC. Network ACLs provide an optional layer of security
    (in addition to security groups) for the instances in your VPC.

    :param str vpc_id: The ID of the VPC to create the network ACL in.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.
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
    protocol,
    egress,
    rule_number,
    rule_action,
    network_acl_id=None,
    network_acl_lookup=None,
    cidr_block=None,
    icmp_code=None,
    icmp_type=None,
    ipv6_cidr_block=None,
    port_range=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param str network_acl_lookup: Any kwarg that ``lookup_network_acl`` accepts.
      Used to lookup the network ACL ID if ``network_acl_id`` is not provided.
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
        elif len(port_range) != 2:
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


def create_network_interface(
    subnet_id=None,
    subnet_lookup=None,
    description=None,
    security_group_ids=None,
    security_group_lookups=None,
    ipv6_address_count=None,
    ipv6_addresses=None,
    primary_private_ip_address=None,
    secondary_private_ip_address_count=None,
    secondary_private_ip_addresses=None,
    interface_type=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Creates a network interface in the specified subnet.

    :param str subnet_id: The ID of the subnet.
    :param dict subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Used to lookup the subnet ID if ``subnet_id`` is not provided.
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
            or {"security_group_ids": security_group_ids},
            "required": False,
            "result_keys": "SecurityGroupIds",
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
    route_table_id=None,
    route_table_lookup=None,
    destination_cidr_block=None,
    destination_ipv6_cidr_block=None,
    destination_prefix_list_id=None,
    egress_only_internet_gateway_id=None,
    egress_only_internet_gateway_lookup=None,
    gateway_id=None,
    gateway_lookup=None,
    instance_id=None,
    instance_lookup=None,
    nat_gateway_id=None,
    nat_gateway_lookup=None,
    transit_gateway_id=None,
    transit_gateway_lookup=None,
    local_gateway_id=None,
    local_gateway_lookup=None,
    network_interface_id=None,
    network_interface_lookup=None,
    vpc_peering_connection_id=None,
    vpc_peering_connection_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict route_table_lookup: Any kwarg that ``lookup_route_table`` accepts.
      Used to lookup the route_table's ID if ``route_table_id`` is not provided.
    :param str destination_cidr_block: The IPv4 CIDR address block used for the
      destination match. Routing decisions are based on the most specific match.
    :param str destination_ipv6_cidr_block: The IPv6 CIDR block used for the
      destination match. Routing decisions are based on the most specific match.
    :param str destination_prefix_list_id: The ID of a prefix list used for the
      destination match.
    :param str egress_only_internet_gateway_id: [IPv6 traffic only] The ID of an
      egress-only internet gateway.
    :param dict egress_only_internet_gateway_lookup: Any kwarg that
      ``lookup_egress_only_internet_gateway`` accepts. Used to lookup the egress-
      only internet gateway if ``egress_only_internet_gateway_id`` is not provided.
    :param str gateway_id: The ID of an internet gateway or virtual private gateway
      attached to your VPC.
    :param dict gateway_lookup: Any kwarg that ``lookup_gateway`` accepts.
      Used to lookup the gateway's ID if ``gateway_id`` is not provided.
    :param str instance_id: The ID of a NAT instance in your VPC. The operation
      fails if you specify an instance ID unless exactly one network interface
      is attached.
    :param dict instance_lookup: Any kwarg that ``lookup_instance`` accepts.
      Used to lookup the instance's ID if ``instance_id`` is not provided.
    :param str nat_gateway_id: [IPv4 traffic only] The ID of a NAT gateway.
    :param dict nat_gateway_lookup: Any kwarg that ``lookup_nat_gateway`` accepts.
      Used to lookup the NAT gateway if ``nat_gateway_id`` is not provided.
    :param str transit_gateway_id: The ID of a transit gateway.
    :param dict transit_gateway_lookup: Any kwarg that ``lookup_transit_gateway``
      accepts. Used to lookup the transit gateway if ``transit_gateway_id`` is
      not provided.
    :param str local_gateway_id: The ID of the local gateway.
    :param dict local_gateway_lookup: Any kwarg that ``lookup_local_gateway``
      accepts. Used to lookup the transit gateway if ``local_gateway_id`` is
      not provided.
    :param str network_interface_id: The ID of a network interface.
    :param dict network_interface_lookup: Any kwarg that ``lookup_network_interface``
      accepts. Used to lookup the network interface if ``network_interface_id``
      is not provided.
    :param str vpc_peering_connection_id: The ID of a VPC peering connection.
    :param dict vpc_peering_connection_lookup: Any kwarg that ``lookup_vpc_peering_connection``
      accepts. Used to lookup the VPC peering connction if ``vpc_peering_connection_id``
      is not provided.

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
            "name": "gateway",
            "kwargs": gateway_lookup or {"gateway_id": gateway_id},
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
                "RouteTableId": res["route_table"],
                "DestinationCidrBlock": destination_cidr_block,
                "DestinationIpv6CidrBlock": destination_ipv6_cidr_block,
                "DestinationPrefixListId": destination_prefix_list_id,
                "EgressOnlyInternetGatewayId": res.get("egress_only_internet_gateway"),
                "GatewayId": res.get("gateway"),
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
    vpc_id=None,
    vpc_lookup=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Creates a route table for the specified VPC. After you create a route table,
    you can add routes and associate the table with a subnet.

    :param str vpc_id: the ID of the VPC the route table is to be created in.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.

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
    name,
    description,
    vpc_id=None,
    vpc_lookup=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Creates a security group.

    A security group acts as a virtual firewall for your instance to control inbound
    and outbound traffic. For more information, see Amazon EC2 Security Groups
    in the Amazon Elastic Compute Cloud User Guide and Security Groups for Your
    VPC in the Amazon Virtual Private Cloud User Guide .

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
    :param str vpc_lookup: [EC2-VPC] Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.
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
    description=None,
    volume_id=None,
    volume_lookup=None,
    tags=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict volume_lookup: Any kwarg that :py:func:`lookup_volume` accepts.
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
    cidr_block,
    vpc_id=None,
    vpc_lookup=None,
    ipv6_cidr_block=None,
    availability_zone=None,
    availability_zone_id=None,
    tags=None,
    blocking=False,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.
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


def create_tags(resource_ids, tags, region=None, keyid=None, key=None, profile=None):
    """
    Adds or overwrites one or more tags for the specified Amazon EC2 resource or
    resources. Each resource can have a maximum of 50 tags. Each tag consists of
    a key and optional value. Tag keys must be unique per resource.

    :param str/list(str) resource_ids: A (list of) ID(s) to create tags for.
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
    return __utils__["boto3.create_resource"]("tags", params=params, client=client,)


def create_volume(
    availability_zone,
    encrypted=None,
    iops=None,
    kms_key_id=None,
    outpost_arn=None,
    size=None,
    snapshot_id=None,
    snapshot_lookup=None,
    volume_type=None,
    tags=None,
    multi_attach_enabled=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict snapshot_lookup: Any kwarg that ``lookup_snapshot`` accepts.
      Used to lookup the snapshot ID if ``snapshot_id`` is not provided.
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
    cidr_block,
    amazon_provided_ipv6_cidr_block=None,
    instance_tenancy=None,
    ipv6_pool=None,
    ipv6_cidr_block=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Creates a VPC with the specified IPv4 CIDR block. The smallest VPC you can
    create uses a /28 netmask (16 IPv4 addresses), and the largest uses a /16
    netmask (65,536 IPv4 addresses). For more information about how large to make
    your VPC, see Your VPC and Subnets in the Amazon Virtual Private Cloud User Guide.

    You can optionally request an IPv6 CIDR block for the VPC. You can request an
    Amazon-provided IPv6 CIDR block from Amazon's pool of IPv6 addresses, or an
    IPv6 CIDR block from an IPv6 address pool that you provisioned through bring
    your own IP addresses (BYOIP).

    By default, each instance you launch in the VPC has the default DHCP options,
    which include only a default DNS server that we provide (AmazonProvidedDNS).
    For more information, see DHCP Options Sets in the Amazon Virtual Private Cloud
    User Guide.

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
        "vpc", params=params, tags=tags, client=client,
    )


def create_vpc_endpoint(
    service_name,
    vpc_id=None,
    vpc_lookup=None,
    vpc_endpoint_type=None,
    policy_document=None,
    route_table_ids=None,
    route_table_lookups=None,
    subnet_ids=None,
    subnet_lookups=None,
    security_group_ids=None,
    security_group_lookups=None,
    private_dns_enabled=None,
    tags=None,
    blocking=False,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Creates a VPC endpoint for a specified service. An endpoint enables you to
    create a private connection between your VPC and the service. The service may
    be provided by AWS, an AWS Marketplace Partner, or another AWS account. For
    more information, see VPC Endpoints in the Amazon Virtual Private Cloud User Guide .

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
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.
    :param str vpc_endpoint_type: The type of endpoint. Allowed values:
      Interface, Gateway. Default: Gateway
    :param list(str) route_table_ids: [Gateway endpoint] One or more route table IDs.
    :param list(dict) route_table_lookups: [Gateway endpoint] List of dicts that
      contain kwargs that ``lookup_route_table`` accepts. Used to lookup route_tables
      if ``route_table_ids`` is not provided.
    :param list(str) subnet_ids: [Interface endpoint] One or more subnets in which
      to create an endpoint network interface.
    :param list(dict) subnet_lookups: [Interface endpoint] List of dicts that
      contain kwargs that ``lookup_subnet`` accepts. Used to lookup subnets if
      ``subnet_ids`` is not provided.
    :param list(str) security_group_ids: [Interface endpoint] The ID of one or
      more security groups to associate with the endpoint network interface.
    :param list(dict) security_group_lookups: [interface endpoint] List of dicts
      that contain kwargs that ``lookup_security_group`` accepts. Used to lookup
      security groups if ``security_group_ids`` is not provided.
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
            or {"security_group_ids": security_group_ids},
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


@arguments_to_list("network_load_balancer_arns")
def create_vpc_endpoint_service_configuration(
    network_load_balancer_arns=None,
    network_load_balancer_lookup=None,
    acceptance_required=None,
    private_dns_name=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Creates a VPC endpoint service configuration to which service consumers (AWS
    accounts, IAM users, and IAM roles) can connect. Service consumers can create
    an interface VPC endpoint to connect to your service.
    To create an endpoint service configuration, you must first create a Network
    Load Balancer for your service.
    If you set the private DNS name, you must prove that you own the private DNS
    domain name.

    :param str/list(str) network_load_balancer_arns: The Amazon Resource Names
      (ARNs) of one or more Network Load Balancers for your service.
    :param dict network_load_balancer_lookup: Dict that contains kwargs
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
    if network_load_balancer_lookup:
        with __salt__["boto3_generic.lookup_resources"](
            {
                "service": "elb",
                "name": "load_balancer",
                "kwargs": network_load_balancer_lookup,
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
        "vpc_endpoint_service_configuration", params, tags=tags, client=client,
    )


def create_vpc_peering_connection(
    requester_vpc_id=None,
    requester_vpc_lookup=None,
    peer_vpc_id=None,
    peer_vpc_lookup=None,
    peer_owner_id=None,
    blocking=False,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Requests a VPC peering connection between two VPCs: a requester VPC that you
    own and an accepter VPC with which to create the connection. The accepter VPC
    can belong to another AWS account and can be in a different Region to the requester
    VPC. The requester VPC and accepter VPC cannot have overlapping CIDR blocks.

    :param str requester_vpc_id: The ID of the requester VPC.
    :param dict requester_vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the requester's VPC ID if ``requester_vpc_id`` is not provided.
    :param str peer_vpc_id: The ID of the accepter VPC.
    :param dict peer_vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the peer VPC ID if ``peer_vpc_id`` is not provided.
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
    vpn_type,
    customer_gateway_id=None,
    customer_gateway_lookup=None,
    vpn_gateway_id=None,
    vpn_gateway_lookup=None,
    transit_gateway_id=None,
    transit_gateway_lookup=None,
    enable_acceleration=None,
    static_routes_only=None,
    tunnel_inside_ip_version=None,
    tunnel_inside_cidr=None,
    tunnel_inside_ipv6_cidr=None,
    pre_shared_key=None,
    phase_1_lifetime_seconds=None,
    phase_2_lifetime_seconds=None,
    rekey_margin_time_seconds=None,
    rekey_fuzz_percentage=None,
    replay_window_size=None,
    dpd_timeout_seconds=None,
    phase_1_encryption_algorithms=None,
    phase_2_encryption_algorithms=None,
    phase_1_integrity_algorithms=None,
    phase_2_integrity_algorithms=None,
    phase_1_dh_group_numbers=None,
    phase_2_dh_group_numbers=None,
    ike_versions=None,
    tags=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict customer_gateway_lookup: Any kwarg that ``lookup_customer_gateway``
      accepts. Used to lookup the customer gateway ID if ``customer_gateway_id``
      is not provided.
    :param str vpn_gateway_id: The ID of the virtual private gateway. If you specify
      a virtual private gateway, you cannot specify a transit gateway.
    :param dict vpn_gateway_lookup: Any kwarg that :py:func:`lookup_vpn_gateway` accepts.
      Used to lookup the customer gateway ID if ``vpn_gateway_id`` is not provided.
    :param str transit_gateway_id: The ID of the transit gateway. If you specify
      a transit gateway, you cannot specify a virtual private gateway.
    :param dict transit_gateway_lookup: Any kwarg that ``lookup_transit_gateway``
      accepts. Used to lookup the transit gateway ID if ``transit_gateway_id``
      is not provided.
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
    vpn_type,
    availability_zone=None,
    tags=None,
    amazon_side_asn=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    operation,
    group_id=None,
    group_lookup=None,
    direction=None,
    description=None,
    port_range=None,
    ip_protocol=None,
    ip_range=None,
    prefix_list_id=None,
    user_id_group_pair=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Helper function to add/remove/update a single ingress or egress rule to a
    security group. Note that "update" only updates a rule's description as all
    other items of the rule determine which rule to update.

    :param str operation: What to do with the security group rule. Allowed values:
      add, remove, update.
    :param str group_id: The ID of the security group to add the rule to.
    :param dict group_lookup: Any kwarg that ``lookup_security_group`` accepts.
      Used to lookup the security group's ID if ``group_id`` is not provided.
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
    :param str prefix_list_lookup: Any kwargs that ``lookup_prefix_list`` accepts.
      Used to lookup prefix list IDs if ``lookup_prefix_id`` is not provided.
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
    if prefix_list_lookup:
        res = lookup_prefix_list(
            region=region, keyid=keyid, key=key, profile=profile, **prefix_list_lookup
        )
        if "error" in res:
            return res
        prefix_list_id = res["result"]["PrefixListId"]
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
    customer_gateway_id=None,
    customer_gateway_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified customer gateway. You must delete the VPN connection
    before you can delete the customer gateway.

    :param str customer_gateway_id: The ID of the customer gateway.
    :param str customer_gateway_lookup: Any kwarg that ``lookup_customer_gateway``
      accepts. Used to lookup the customer gateway ID if ``customer_gateway_id``
      is not provided.

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
    dhcp_options_id=None,
    dhcp_options_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified set of DHCP options. You must disassociate the set of
    DHCP options before you can delete it. You can disassociate the set of DHCP
    options by associating either a new set of options or the default set of
    options with the VPC.

    :param str dhcp_options_id: The ID of the DHCP option set to delete.
    :param str dhcp_options_lookup: Any kwarg that lookup_dhcp_options accepts.
      When ``dhcp_options_id`` is not provided, this is required, otherwise ignored.

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
    internet_gateway_id=None,
    internet_gateway_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified internet gateway. You must detach the internet gateway
    from the VPC before you can delete it.

    :param str internet_gateway_id: The ID of the Internet Gateway.
    :param dict internet_gateway_lookup: Any kwarg that ``lookup_internet_gateway``
      accepts. Used to lookup the Internet gateway's ID if ``internet_gateway_id``
      is not provided.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_internet_gateways, boto3.client('ec2').delete_internet_gateway
    """
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "internet_gateway",
            "kwargs": internet_gateway_lookup
            or {"internet_gateway_id": internet_gateway_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {"InternetGatewayId": res["result"]["internet_gateway"]}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.delete_internet_gateway, params)


def delete_key_pair(
    key_name=None, key_pair_id=None, key_pair_lookup=None,
):
    """
    Deletes the specified key pair, by removing the public key from Amazon EC2.

    :param str key_name: The name of the key pair.
    :param str key_pair_id: The ID of the key pair.
    :param dict key_pair_lookup: Any kwarg that ``lookup_key_pair`` accepts.
      Used to lookup the Internet gateway's ID if ``key_pair_id`` and ``key_name``
      are not provided.

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
    nat_gateway_id=None,
    nat_gateway_lookup=None,
    blocking=False,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified NAT gateway. Deleting a NAT gateway disassociates its
    Elastic IP address, but does not release the address from your account.
    Deleting a NAT gateway does not delete any NAT gateway routes in your route tables.

    :param str nat_gateway_id: The ID of the NAT gateway to delete.
    :param dict nat_gateway_lookup: Any kwarg that lookup_nat_gateway accepts.
      Used to lookup the nat_gateway_id when ``nat_gateway_id`` is not provided.
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
            "nat_gateway", "deleted", resource_id=nat_gateway_id, client=client,
        )
    else:
        ret = {"result": True}
    return ret


def delete_network_acl(
    network_acl_id=None,
    network_acl_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified network ACL. You can't delete the ACL if it's associated
    with any subnets. You can't delete the default network ACL.

    :param str network_acl_id: The ID of the network ACL.
    :param str network_acl_lookup: Any kwarg that ``lookup_network_acl`` accepts.
      Used to lookup the network ACL ID if ``network_acl_id`` is not provided.

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
    rule_number,
    egress,
    network_acl_id=None,
    network_acl_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified ingress or egress entry (rule) from the specified network ACL.

    :param int rule_number: The rule number of the entry to delete.
    :param bool egress: Indicates whether the rule is an egress rule.
    :param str network_acl_id: The ID of the network ACL.
    :param str network_acl_lookup: Any kwarg that ``lookup_network_acl`` accepts.
      Used to lookup the network ACL ID if ``network_acl_id`` is not provided.

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
    network_interface_id=None,
    network_interface_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified network interface. You must detach the network interface
    before you can delete it.

    :param str network_interface_id: The ID of the network interface.
    :param dict network_interface_lookup: Any kwarg that ``lookup_network_interface``
      accepts. Used to lookup the network interface ID if ``network_interface_id``
      is not provided.

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
    route_table_id=None,
    route_table_lookup=None,
    destination_cidr_block=None,
    destination_ipv6_cidr_block=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified route from the specified route table.

    :param str route_table_id: The ID of the route table.
    :param dict route_table_lookup: Any kwarg that ``lookup_route_table`` accepts.
      Used to lookup the route_table's ID if ``route_table_id`` is not provided.
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
    route_table_id=None,
    route_table_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified route table. You must disassociate the route table from
    any subnets before you can delete it. You can't delete the main route table.

    :param str route_table_id: The ID of the route table to delete.
    :param dict route_table_lookup: Any kwarg that ``lookup_route_table`` accepts.
      Used to lookup the route_table's ID if ``route_table_id`` is not provided.

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
    group_id=None,
    group_name=None,
    group_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes a security group.

    If you attempt to delete a security group that is associated with an instance,
    or is referenced by another security group, the operation fails with InvalidGroup.InUse
    in EC2-Classic or DependencyViolation in EC2-VPC.

    :param str group_id: The ID of the security group.
    :param str group_name: [EC2-Classic, default VPC] The name of the security group.
      This only works when the security group is in the default VPC. If this is
      not the case, use ``group_lookup`` below.
    :param dict group_lookup: Any kwarg that ``lookup_security_group`` accepts.
      Used to lookup the security_group ID if ``group_id`` and ``group_name``
      are not provided or you want to delete a security group by name in a non-
      default VPC.

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
    snapshot_id=None,
    snapshot_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict snapshot_lookup: Any kwarg that ``lookup_snapshot`` accepts.
      Used to lookup the snapshot ID if ``snapshot_id`` is not provided.

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
    subnet_id=None, subnet_lookup=None, region=None, keyid=None, key=None, profile=None,
):
    """
    Deletes the specified subnet. You must terminate all running instances in
    the subnet before you can delete the subnet.

    :param str subnet_id: The ID of the subnet to delete.
    :param dict subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Used to lookup the Subnet's ID if ``subnet_id`` is not provided.

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


def delete_tags(resources, tags, region=None, keyid=None, key=None, profile=None):
    """
    Deletes the specified set of tags from the specified set of resources.

    :param str/list(str) resources: A (list of) ID(s) to delete tags from.
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
    volume_id=None,
    volume_lookup=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified EBS volume. The volume must be in the available state
    (not attached to an instance).

    The volume can remain in the deleting state for several minutes.

    :param str volume_id: The ID of the volume.
    :param dict volume_lookup: Any kwarg that :py:func:`lookup_volume` accepts.
      When ``volume_id`` is not provided, this is required, otherwise ignored.
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
            "volume", "deleted", resource_id=volume_id, client=client,
        )
    else:
        ret = {"result": True}
    return ret


def delete_vpc(
    vpc_id=None, vpc_lookup=None, region=None, keyid=None, key=None, profile=None
):
    """
    Deletes the specified VPC. You must detach or delete all gateways and resources
    that are associated with the VPC before you can delete it. For example, you
    must terminate all instances running in the VPC, delete all security groups
    associated with the VPC (except the default one), delete all route tables
    associated with the VPC (except the default one), and so on.

    :param str vpc_id: The ID of the VPC to delete.
    :param dict vpc_lookup: Any kwarg that :py:func:`lookup_vpc` accepts.
      When ``vpc_id`` is not provided, this is required, otherwise ignored.

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


@arguments_to_list("service_ids", "service_lookups")
def delete_vpc_endpoint_service_configurations(
    service_ids=None,
    service_lookups=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes one or more VPC endpoint service configurations in your account. Before
    you delete the endpoint service configuration, you must reject any ``Available``
    or ``PendingAcceptance`` interface endpoint connections that are attached to the
    service.

    :param str/list(str) service_ids: The IDs of one or more services
    :param dict/list(dict) service_lookups: Any kwargs that ``lookup_vpc_endpoint_service``
      accepts. When ``service_ids`` is not provided, this is required, otherwise ignored.

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


@arguments_to_list("vpc_endpoint_ids", "vpc_endpoint_lookups")
def delete_vpc_endpoints(
    vpc_endpoint_ids=None,
    vpc_endpoint_lookups=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes one or more specified VPC endpoints. Deleting a gateway endpoint also
    deletes the endpoint routes in the route tables that were associated with the
    endpoint. Deleting an interface endpoint deletes the endpoint network interfaces.

    :param str/list(str) vpc_endpoint_ids: One or more VPC endpoint IDs.
    :param dict/list(dict) vpc_endpoint_lookups: Any kwargs that ``lookup_vpc_endpoint``
      accepts. When ``vpc_endpoint_ids`` is not provided, this is required,
      otherwise ignored.

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
    vpc_peering_connection_id=None,
    vpc_peering_connection_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes a VPC peering connection. Either the owner of the requester VPC or
    the owner of the accepter VPC can delete the VPC peering connection if it's
    in the ``active`` state. The owner of the requester VPC can delete a VPC peering
    connection in the ``pending-acceptance`` state. You cannot delete a VPC peering
    connection that's in the ``failed`` state.

    :param str vpc_peering_connection_id: The ID of the VPC peering connection
      to delete.
    :param dict vpc_peering_connection_lookup: Any kwargs that ``lookup_vpc_peering_connection``
      accepts. When ``vpc_peering_connection_id`` is not provided, this is required,
      otherwise ignored.
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
    vpn_connection_id=None,
    vpn_connection_lookup=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict vpn_connection_lookup: Any kwargs that ``lookup_vpn_connection``
      accepts. When ``vpc_connection_id`` is not provided, this is required,
      otherwise ignored.
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
    vpn_gateway_id=None,
    vpn_gateway_lookup=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Deletes the specified virtual private gateway. You must first detach the virtual
    private gateway from the VPC. Note that you don't need to delete the virtual
    private gateway if you plan to delete and recreate the VPN connection between
    your VPC and your network.

    :param str vpn_gateway_id: The ID of the virtual private gateway.
    :param dict vpn_gateway_lookup: Any kwargs that ``lookup_vpn_gateway``
      accepts. When ``vpc_gateway_id`` is not provided, this is required,
      otherwise ignored.
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
    image_id=None, image_lookup=None, region=None, keyid=None, key=None, profile=None
):
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
    :param dict image_lookup: Any kwargs that ``lookup_image`` accepts. When ``image_id``
      is not provided, this is required, otherwise ignored.

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


@arguments_to_list("attributes")
def describe_account_attributes(
    attributes=None, region=None, keyid=None, key=None, profile=None, client=None,
):
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

    :param str/list(str) attributes: One or more attributes to describe.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``describe_account_attributes``-
      call on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"](
        "account_attribute", AttributeNames=attributes, client=client,
    )


@arguments_to_list("public_ips", "allocation_ids")
def describe_addresses(
    filters=None,
    public_ips=None,
    allocation_ids=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more Elastic IP addresses.

    :param dict filters: The dict with filters to specify the EIP(s) to describe.
    :param str/list(str) public_ips: The (list of) Public IPs to specify the EIP(s) to describe.
    :param str/list(str) allocation_ids: The (list of) Allocation IDs to specify the EIP(s) to describe.

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
    zone_ids=None,
    zone_names=None,
    all_availability_zones=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_availability_zones
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


@arguments_to_list("customer_gateway_ids")
def describe_customer_gateways(
    customer_gateway_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your VPN customer gateways.

    :param str/list(str) customer_gateway_ids: One or more customer gateway IDs.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_customer_gateways
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
        "customer_gateway", ids=customer_gateway_ids, filters=filters, client=client,
    )


@arguments_to_list("dhcp_option_ids")
def describe_dhcp_options(
    dhcp_option_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your DHCP options sets.

    :param str/list(str) dhcp_option_ids: The (list of) DHCP option ID(s) to describe.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_dhcp_options
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
        "dhcp_options", ids=dhcp_option_ids, filters=filters, client=client,
    )


@arguments_to_list("egress_only_internet_gateway_ids")
def describe_egress_only_internet_gateways(
    egress_only_internet_gateway_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=none,
):
    """
    Describes one or more of your egress-only internet gateways.

    :param str/list(str): egress_only_internet_gateway_ids: One or more egress-only
      internet gateway IDs.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_egress_only_internet_gateways
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


@arguments_to_list("elastic_gpu_ids")
def describe_elastic_gpus(
    elastic_gpu_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the Elastic Graphics accelerator associated with your instances.

    :param str/list(str) elastic_gpu_ids: The Elastic Graphic accelerator IDs.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_elastic_gpus
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
        "elastic_gpu", ids=elastic_gpu_ids, filters=filters, client=client,
    )


@arguments_to_list("fleet_ids")
def describe_fleets(
    fleet_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the specified EC2 Fleets or all of your EC2 Fleets.

    :param str/list(str) fleet_ids: The ID of the EC2 Fleets.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_fleets
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
        "fleet", ids=fleet_ids, filters=filters, client=client,
    )


@arguments_to_list("attributes")
def describe_fpga_image_attribute(
    attributes=None,
    fpga_image_id=None,
    fpga_image_lookup=None,
    region=None,
    keyid=NOne,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the specified attribute of the specified Amazon FPGA Image (AFI).

    :param str/list(str) attributes: The AFI attribute. Allowed values:
        ``description``, ``name``, ``load_permission``, ``product_codes``.
    :param str fpga_image_id: The ID of the AFI.
    :param dict fpga_image_lookup: Any kwargs that ``lookup_fpga_image`` accepts.
      When ``fpga_image_id`` is not provided, this is required, otherwise ignored.

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


@arguments_to_list("fpga_image_ids", "owners")
def describe_fpga_images(
    fpga_image_ids=None,
    owners=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the Amazon FPGA Images (AFIs) available to you. These include public
    AFIs, private AFIs that you own, and AFIs owned by other AWS accounts for which
    you have load permissions.

    :param str/list(str) fpga_image_ids: The AFI IDs.
    :param str/list(str) owners: Filters the AFI by owner. Specify an AWS account
      ID, ``self`` (owner is the sender of the request), or an AWS owner alias
      (valid values are ``amazon``,  ``aws-marketplace``).
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_fpga_images
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
        "fpga_image", ids=fpga_image_ids, filters=filters, client=client, Owners=owners,
    )


@arguments_to_list("host_ids")
def describe_hosts(
    host_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the specified Dedicated Hosts or all your Dedicated Hosts.

    The results describe only the Dedicated Hosts in the Region you're currently
    using. All listed instances consume capacity on your Dedicated Host. Dedicated
    Hosts that have recently been released are listed with the state ``released``.

    :param str/list(str) host_ids: The IDs of the Dedicated Hosts. The IDs are
      used for targeted instance launches.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_hosts
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
        "host", ids=host_ids, filters=filters, client=client,
    )


@arguments_to_list("association_ids")
def describe_iam_instance_profile_associations(
    association_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes your IAM instance profile associations.

    :param str/list(str) association_ids: The IAM instance profile associations.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_iam_instance_profile_associations
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


@arguments_to_list("attributes")
def describe_image_attribute(
    attributes=None,
    image_id=None,
    image_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the specified attribute(s) of the specified AMI.

    :param str/list(str) attributes: One or more AMI attributes to describe.
      Allowed values: ``description``, ``kernel``, ``ramdisk``, ``launch_permission``,
      ``product_codes``, ``block_device_mapping``, ``sriov_net_support``.
    :param str image_id: The ID of the AMI.
    :param dict image_lookup: Any kwargs that ``lookup_image`` accepts.
      When ``image_id`` is not provided, this is required, otherwise ignored.

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


def describe_images(
    image_ids=None,
    filters=None,
    executable_users=None,
    owners=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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

    :param list(str) image_ids: The image IDs.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_images
      for a complete list.
      Note that the filters can be supplied as a dict with the keys being the
      names of the filter, and the value being either a string or a list of strings.
    :param list(str) executable_users: Scopes the images by users with explicit
      launch permissions. Specify an AWS account ID, ``self`` (the sender of the
      request), or ``all`` (public AMIs).
    :param list(str) owners: Scopes the results to images with the specified owners.
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


@arguments_to_list("attributes")
def describe_instance_attribute(
    attributes=None,
    instance_id=None,
    instance_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more specified attributes of the specified instance.
    Valid attribute values are: ``instance_type``, ``kernel``, ``ramdisk``, ``user_data``,
    ``disable_api_termination``, ``instance_initiated_shutdown_behavior``, ``root_device_name``,
    ``block_device_mapping``, ``product_codes``, ``source_dest_check``, ``group_set``,
    ``ebs_optimized``, ``sriov_net_support``.

    :param str/list(str) attributes: One or more instance attributes to describe.
    :param str instance_id: The ID of the instance.
    :param dict instance_lookup: Any kwargs that ``lookup_instance`` accepts.
      When ``instance_id`` is not provided, this is required, otherwise ignored.

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


@arguments_to_list("instance_ids")
def describe_instance_credit_specifications(
    instance_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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

    :param str/list(str) instance_ids: The (list of) IDs of the instance(s).
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_instance_credit_specifications
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


@arguments_to_list("instance_ids", "instance_lookups")
def describe_instance_status(
    instance_ids=None,
    instance_lookups=None,
    include_all_instances=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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

    :param str/list(str) instance_ids: The instance IDs. Default: describes all
      your instances. Constraints: Maximum 100 explicitly specified instance IDs.
    :param dict/list(dict) instance_lookups: One or more dicts of kwargs that
      ``lookup_instance`` accepts. Used to lookup any ``instance_ids``
      if none are provided.
    :param bool include_all_instances: When ``True``, includes the health status
      for all instances. When ``False``, includes the health status for running
      instances only. Default: ``False``
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_instance_status
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


@arguments_to_list("instance_ids")
def describe_instances(
    instance_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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

    :param str/list(str) instance_ids: The instance IDs. Default: Describes all
      your instances.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_instances
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
        "instance", ids=instance_ids, filters=filters, client=client,
    )


@arguments_to_list("internet_gateway_ids")
def describe_internet_gateways(
    internet_gateway_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your internet gateways.

    :param str/list(str) internet_gateway_ids: The (list of) IDs of the internet
      gateway(s) to describe.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_internet_gateways
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
        "internet_gateway", ids=internet_gateway_ids, filters=filters, client=client,
    )


@arguments_to_list("pool_ids")
def describe_ipv6_pools(
    pool_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes your IPv6 address pools.

    :param str/list(str): pool_ids: The IDs of the IPv6 address pools.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_ipv6_pools
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
        "ipv6_pool", ids=pool_ids, filters=filters, client=client,
    )


@arguments_to_list("launch_template_ids", "launch_template_names")
def describe_launch_templates(
    launch_template_ids=None,
    launch_template_names=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more launch templates.

    :param str/list(str) launch_template_ids: One or more launch template IDs.
    :param str/list(str) launch_template_names: One or more launch template names.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_launch_templates
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


@arguments_to_list("key_pair_ids", "key_names")
def describe_key_pairs(
    key_pair_ids=None,
    key_names=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the specified key pairs or all of your key pairs.

    :param str/list(str) key_pair_ids: The IDs of the key pairs.
    :param str/list(str) key_names: The key pair names.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_key_pairs
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


@arguments_to_list("local_gateway_ids")
def describe_local_gateways(
    local_gateway_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more local gateways. By default, all local gateways are described.
    Alternatively, you can filter the results.

    :param str/list(str) local_gateway_ids: The (list of) ID(s) of local gateway(s)
      to describe.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_local_gateways
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
        "local_gateway", ids=local_gateway_ids, filters=filters, client=client,
    )


@arguments_to_list("nat_gateway_ids")
def describe_nat_gateways(
    nat_gateway_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more NAT Gateways.

    :param str/list(str) nat_gateway_ids: The (list of) NAT Gateway IDs to specify the NGW(s) to describe.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_nat_gateways
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
        "nat_gateway", ids=nat_gateway_ids, filters=filters, client=client,
    )


@arguments_to_list("network_acl_ids")
def describe_network_acls(
    network_acl_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your network ACLs.

    :param str/list(str) network_acl_ids: The (list of) ID(s) of network ACLs to describe.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_network_acls
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
        "network_acl", ids=network_acl_ids, filters=filters, client=client,
    )


@arguments_to_list("network_interface_ids")
def describe_network_interfaces(
    network_interface_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your network interfaces.

    :param str/list(str) network_interface_ids: One or more network interface IDs.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_network_interfaces
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
        "network_interface", ids=network_interface_ids, filters=filters, client=client,
    )


@arguments_to_list("region_names")
def describe_regions(
    region_names=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the Regions that are enabled for your account, or all Regions.

    :param str/list(str) region_names: The names of the Regions. You can specify
      any Regions, whether they are enabled and disabled for your account.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_regions
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
        "region", filters=filters, client=client, RegionNames=region_names,
    )


@arguments_to_list("route_table_ids")
def describe_route_tables(
    route_table_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your route tables.

    :param str/list(str) route_table_ids: The (list of) ID(s) of route tables to describe.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_route_tables
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
        "route_table", ids=route_table_ids, filters=filters, client=client,
    )


@arguments_to_list("group_ids", "group_names")
def describe_security_groups(
    group_ids=None,
    group_names=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the specified security groups or all of your security groups.

    :param str/list(str) group_ids: The IDs of the security groups. Required for security
      groups in a nondefault VPC. Default: Describes all your security groups.
    :param str/list(str) group_names: [EC2-Classic and default VPC only] The names of
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


@arguments_to_list("snapshot_ids", "owner_ids")
def describe_snapshots(
    snapshot_ids=None,
    owner_ids=None,
    restorable_by_user_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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

    :param str/list(str) snapshot_ids: The snapshot IDs.
      Default: Describes the snapshots for which you have create volume permissions.
    :param list(str) owner_ids: Scopes the results to snapshots with the specified
      owners. You can specify a combination of AWS account IDs, ``self``, and ``amazon``.
    :param list(str) restorable_by_user_ids: The IDs of the AWS accounts that can
      create volumes from the snapshot.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_snapshots
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
    spot_fleet_request_id, region=None, keyid=None, key=None, profile=None, client=None,
):
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


@arguments_to_list("spot_fleet_request_ids")
def describe_spot_fleet_requests(
    spot_fleet_request_ids=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes your Spot Fleet requests.

    Spot Fleet requests are deleted 48 hours after they are canceled and their
    instances are terminated.

    :param str/list(str) spot_fleet_request_ids: The IDs of the Spot Fleet requests.

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


@arguments_to_list("spot_instance_request_ids")
def describe_spot_instance_requests(
    spot_instance_request_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the specified Spot Instance requests.

    You can use DescribeSpotInstanceRequests to find a running Spot Instance by
    examining the response. If the status of the Spot Instance is ``fulfilled``,
    the instance ID appears in the response and contains the identifier of the
    instance. Alternatively, you can use DescribeInstances with a filter to look
    for instances where the instance lifecycle is ``spot``.

    Spot Instance requests are deleted four hours after they are canceled and their
    instances are terminated.

    :param str/list(str) spot_instance_request_ids: One or more Spot Instance request IDs.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_spot_instance_requests
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
    vpc_id=None,
    vpc_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the stale security group rules for security groups in a specified
    VPC. Rules are stale when they reference a deleted security group in a peer
    VPC, or a security group in a peer VPC for which the VPC peering connection
    has been deleted.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwarg that lookup_vpc accepts.
      When ``vpc_id`` is not provided, this is required, otherwise ignored.

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
            "stale_security_group", ids=res["result"]["vpc"], client=client,
        )


@arguments_to_list("subnet_ids")
def describe_subnets(
    subnet_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your subnets.

    :param str/list(str) subnet_ids: The (list of) subnet IDs to specify the Subnets to describe.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_subnets
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
        "subnet", ids=subnet_ids, filters=filters, client=client,
    )


def describe_tags(
    filters=None, region=None, keyid=None, key=None, profile=None, client=None
):
    """
    Describes the specified tags for your EC2 resources.

    :param dict filters: The filters.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key with
      dict containing the tags on succes.
    """
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.describe_resource"]("tag", filters=filters, client=client,)


@arguments_to_list("transit_gateway_ids")
def describe_transit_gateways(
    transit_gateway_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more transit gateways. By default, all transit gateways are
    described. Alternatively, you can filter the results.

    :param str/list(str) transit_gateway_ids: The (list of) IDs of the transit gateways.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_transit_gateways
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
        "transit_gateway", ids=transit_gateway_ids, filters=filters, client=client,
    )


@arguments_to_list("volume_ids")
def describe_volumes(
    volume_ids=None, filters=None, region=None, keyid=None, key=None, profile=None,
):
    """
    Describes the specified EBS volumes or all of your EBS volumes.

    :param str/list(str) volume_ids: The volume IDs.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_volumes
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
        "volume", ids=volume_ids, filters=filters, client=client,
    )


@argument_to_list("attributes")
def describe_vpc_attributes(
    attributes=None,
    vpc_id=None,
    vpc_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the specified attribute(s) of the specified VPC.

    :param str/list(str) attributes: One or more attributes to describe.
      Allowed values: ``enable_dns_support``, ``enable_dns_hostnames``
    :param str vpc_id: The ID of the VPC to operate on.
    :param dict vpc_lookup: Any kwarg that lookup_vpc accepts.
      When ``vpc_id`` is not provided, this is required, otherwise ignored.

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


@arguments_to_list("service_ids")
def describe_vpc_endpoint_service_configurations(
    service_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the VPC endpoint service configurations in your account (your services).

    :param str/list(str) service_ids: The IDs of one or more services.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_endpoint_service_configurations
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
    service_id=None,
    service_lookup=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes the principals (service consumers) that are permitted to discover
    your VPC endpoint service.

    :param str service_id: The ID of the service.
    :param dict service_lookup: Any kwarg that ``lookup_vpc_endpoint_service`` accepts.
      When ``service_id`` is not provided, this is required, otherwise ignored.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_endpoint_service_permissions
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


@arguments_to_list("service_names")
def describe_vpc_endpoint_services(
    service_names=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes available services to which you can create a VPC endpoint.

    :param str/list(str) service_names: One or more service names.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_endpoint_services
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


@arguments_to_list("vpc_endpoint_ids")
def describe_vpc_endpoints(
    vpc_endpoint_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your VPC endpoints.

    :param str/list(str) vpc_endpoint_ids: The (list of) ID(s) of the VPC endpoint(s) to describe.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_endpoints
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
        "vpc_endpoint", ids=vpc_endpoint_ids, filters=filters, client=client,
    )


@arguments_to_list("vpc_peering_connection_ids")
def describe_vpc_peering_connections(
    vpc_peering_connection_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your VPC peering connections.

    :param str/list(str) vpc_peering_connection_ids: The (list of) ID(s) of VPC Peering
      connections to describe.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpc_peering_connections
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


@arguments_to_list("vpc_ids")
def describe_vpcs(
    vpc_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your VPCs.

    :param str/list(str) vpc_ids: One or more VPC IDs. Default: Describes all your VPCs.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpcs
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
        "vpc", ids=vpc_ids, filters=filters, client=client,
    )


@arguments_to_list("vpn_connection_ids")
def describe_vpn_connections(
    vpn_connection_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Describes one or more of your VPN connections.

    :param str/list(str) vpn_connection_ids: One or more VPN connection IDs.
      Default: Describes your VPN connections.
    :param dict filters: One or more filters. See
      https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_vpn_connections
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
        "vpn_connection", ids=vpn_connection_ids, filters=filters, client=client,
    )


@arguments_to_list("vpn_gateway_ids")
def describe_vpn_gateways(
    vpn_gateway_ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Describes one or more of your virtual private gateways.

    :param str/list(str) vpn_gateway_ids: One or more virtual private gateway IDs.
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
        "vpn_gateway", ids=vpn_gateway_ids, filters=filters, client=client,
    )


def detach_internet_gateway(
    internet_gateway_id=None,
    internet_gateway_lookup=None,
    vpc_id=None,
    vpc_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Detaches an internet gateway from a VPC, disabling connectivity between the
    internet and the VPC. The VPC must not contain any running instances with
    Elastic IP addresses or public IPv4 addresses.

    :param str internet_gateway_id: The ID of the Internet gateway to detach.
    :param dict internet_gateway_lookup: Any kwarg that ``lookup_internet_gateway``
      accepts. Used to lookup the Internet gateway's ID if ``internet_gateway_id``
      is not provided.
    :param str vpc_id: The ID of the VPC to detach from the IGW.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success.

    :depends: boto3.client('ec2').describe_internet_gateways, boto3.client('ec2').describe_vpcs, boto3.client('ec2').detach_internet_gateway
    """
    with __salt__["boto3_generic.lookup_resources"](
        {"service": "ec2", "name": vpc, "kwargs": vpc_lookup or {"vpc_id": vpc_id}},
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
    attachment_id=None,
    network_interface_lookup=None,
    force=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Detaches a network interface from an instance.

    :param str attachment_id: The ID of the attachment.
    :param dict network_interface_lookup: Any kwarg that ``lookup_network_interface``
      accepts. Used to lookup the attachment ID if ``attachment_id`` is not provided.
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
                "result_keys": "Attachment:AttachmentId",
            },
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
        ) as res:
            if "error" in res:
                return res
            attachment_id = res["result"]["network_interface"]
    params = salt.utils.data.filter_falsey(
        {"AttachmentId": attachment_id, "Force": force}
    )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return __utils__["boto3.handle_response"](client.detach_network_interface, params)


def detach_volume(
    volume_id=None,
    volume_lookup=None,
    instance_id=None,
    instance_lookup=None,
    device=None,
    force=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict volume_lookup: Any kwarg that ``lookup_volume`` accepts. Used to
      lookup ``volume_id`` if it is not provided.
    :param str instance_id: The ID of the instance. If you are detaching a Multi-
      Attach enabled volume, you must specify an instance ID.
    :param dict instance_lookup: Any kwarg that ``lookup_instance`` accepts. Used
      to lookup ``instance_id`` if it is not provided.
    :param str device: The device name.
    :param bool Force: Forces detachment if the previous detachment attempt did
      not occur cleanly (for example, logging into an instance, unmounting the
      volume, and detaching normally). This option can lead to data loss or a corrupted
      file system. Use this option only as a last resort to detach a volume from
      a failed instance. The instance won't have an opportunity to flush file system
      caches or file system metadata. If you use this option, you must perform
      file system check and repair procedures.

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
    return __utils__["boto3.handle_response"](client.detach_volume, params)


def detach_vpn_gateway(
    vpc_id=None,
    vpc_lookup=None,
    vpn_gateway_id=None,
    vpn_gateway_lookup=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Detaches a virtual private gateway from a VPC. You do this if you're planning
    to turn off the VPC and not use it anymore. You can confirm a virtual private
    gateway has been completely detached from a VPC by describing the virtual private
    gateway (any attachments to the virtual private gateway are also described).

    You must wait for the attachment's state to switch to detached before you can
    delete the VPC or attach a different VPC to the virtual private gateway.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts. Used to lookup
      ``vpc_id`` if it is not provided.
    :param str vpn_gateway_id: The ID of the virtual private gateway.
    :param dict vpn_gateway_lookup: Any kwarg that ``lookup_vpn_gateway`` accepts.
      Used to lookup ``vpn_gateway_id`` if it is not provided.
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
    vpc_id=None, vpc_lookup=None, region=None, keyid=None, key=None, profile=None,
):
    """
    Disables ClassicLink for a VPC. You cannot disable ClassicLink for a VPC that
    has EC2-Classic instances linked to it.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts. Used to lookup
      ``vpc_id`` if it is not provided.

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
    return __utils__["boto3.handle_response"](client.disable_vpc_classic_link, params)


def disable_vpc_classic_link_dns_support(
    vpc_id=None, vpc_lookup=None, region=None, keyid=None, key=None, profile=None,
):
    """
    Disables ClassicLink DNS support for a VPC. If disabled, DNS hostnames resolve
    to public IP addresses when addressed between a linked EC2-Classic instance
    and instances in the VPC to which it's linked. For more information, see ClassicLink
    in the Amazon Elastic Compute Cloud User Guide .

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts. Used to lookup
      ``vpc_id`` if it is not provided.

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
    return __utils__["boto3.handle_response"](
        client.disable_vpc_classic_link_dns_support, params
    )


def disassociate_address(
    association_id=None,
    address_lookup=None,
    public_ip=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Disassociates an Elastic IP address from the instance or network interface
    it's associated with.

    :param str association_id: [EC2-VPC] The association ID.
    :param dict address_lookup: Any kwarg that ``lookup_address`` accepts. Used
      to lookup ``association_id`` if it is not provided.
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
    association_id=None,
    route_table_id=None,
    route_table_lookup=None,
    subnet_id=None,
    subnet_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Disassociates a subnet from a route table. You can either specify an
    association_id, or (route_table and subnet).
    After you perform this action, the subnet no longer uses the routes in the
    route table. Instead, it uses the routes in the VPC's main route table.

    :param str association_id: The association ID of the route table-subnet association.
      If this is not known, it will be looked up using describe_route_tables
      and the route_table- and subnet-information below.
    :param str route_table_id: The ID of the route table to disassociate.
    :param dict route_table_lookup: Any kwarg that ``lookup_route_table`` accepts.
      Used to lookup the route_table's ID if ``route_table_id`` is not provided.
    :param str subnet_id: The ID of the subnet to disassociate from.
      If ``association_subnet_id`` is present in ``route_table_lookup``, that
      is assumed to be the subnet_id to disassociate from and this argument
      is ignored.
    :param dict subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Used to lookup the subnet's ID if ``subnet_id`` is not provided.
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
    association_id=None,
    ipv6_cidr_block=None,
    subnet_id=None,
    subnet_lookup=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
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
    :param dict subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Used to lookup the Subnet's ID if ``subnet_id`` is not provided.
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
                "error": "The subnet specified does not have an IPv6 CIDR block association"
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
            "subnet_ipv6_cidr_block", "disassociated", params=params, client=client,
        )
    return {"result": True}


def disassociate_vpc_cidr_block(
    association_id=None,
    vpc_lookup=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Disassociates a CIDR block from a VPC. To disassociate the CIDR block, you
    must specify its association ID. You can get the association ID by using
    DescribeVpcs. You must detach or delete all gateways and resources that are
    associated with the CIDR block before you can disassociate it.
    You cannot disassociate the CIDR block with which you originally created the
    VPC (the primary CIDR block).

    :param str association_id: The ID of the association to remove.
    :param str vpc_lookup: Any kwarg that lookup_vpc accepts.
      This is used to lookup the association_id. As such, it must contain the
      either the kwarg ``cidr_block`` or ``ipv6_cidr_block`` to specify the exact
      IPv4/IPv6 CIDR block to disassociate.
      When ``association_id`` is not provided, this is required, otherwise ignored.
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
            raise SaltInvocationError("vpc_lookup is required.")
        if "cidr_block" not in vpc_lookup and "ipv6_cidr_block" not in vpc_lookup:
            raise SaltinvocationError(
                'vpc_lookup must contain an entry for either "cidr_block" or "ipv6_cidr_block".'
            )
        else:
            cidr_block_type = "ipv6" if "ipv6_cidr_block" in vpc_lookup else ""
    # ... So we will have to lookup both ...
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "vpc",
            "kwargs": vpc_lookup
            or {"cidr-block-association.association-id": association_id},
            "result_keys": "CidrBlockAssociationSet",
            "required": False,
        },
        {
            "service": "ec2",
            "name": "vpc",
            "as": "vpc6",
            "kwargs": {"ipv6-cidr-block-association.association-id": association_id},
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
        # ... And figure out which one it was ...
        if association_id:
            matching_ipv4_cidr_blocks = [
                item for item in res["vpc"] if item["AssociationId"] == association_id
            ]
            matching_ipv6_cidr_blocks = [
                item for item in res["vpc6"] if item["AssociationId"] == association_id
            ]
            if not any((matching_ipv4_cidr_blocks, matching_ipv6_cidr_blocks)):
                raise SaltInvocationError(
                    "No VPC found with matching associated IPv4 or IPv6 CIDR blocks."
                )
        else:
            matching_ipv4_cidr_blocks = [
                item
                for item in res["vpc"]
                if item["CidrBlock"] == vpc_lookup.get("cidr_block")
            ]
            matching_ipv6_cidr_blocks = [
                item
                for item in res["vpc6"]
                if item["Ipv6CidrBlock"] == vpc_lookup.get("ipv6_cidr_block")
            ]
        cidr_block_type = "ipv6" if matching_ipv6_cidr_blocks else ""
        res = (
            res["result"]["vpc6"][0]
            if matching_ipv6_cidr_blocks
            else res["result"]["vpc"][0]
        )
        association_id = res["vpc{}".format("6" if cidr_block_type else "")][
            "AssociationId"
        ]
        params = {"AssociationId": association_id}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    res = __utils__["boto3.handle_response"](client.disassociate_vpc_cidr_block, params)
    if "error" in res:
        return res
    if blocking:
        # ... All so we can wait for the correct CIDR block to be disassociated.
        params = __utils__["boto3.dict_to_boto_filters"](
            {
                "{}{}cidr-block-association.association_id".format(
                    cidr_block_type, "-" if cidr_block_type else ""
                ): association_id
            }
        )
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
    vpc_id=None, vpc_lookup=None, region=None, keyid=None, key=None, profile=None,
):
    """
    Enables a VPC for ClassicLink. You can then link EC2-Classic instances to your
    ClassicLink-enabled VPC to allow communication over private IP addresses. You
    cannot enable your VPC for ClassicLink if any of your VPC route tables have
    existing routes for address ranges within the 10.0.0.0/8 IP address range,
    excluding local routes for VPCs in the 10.0.0.0/16 and 10.1.0.0/16 IP address ranges.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts. Used to lookup
      ``vpc_id`` if it is not provided.

    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with dict containing the result of the boto ``enable_vpc_classic_link``-
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
    return __utils__["boto3.handle_response"](client.enable_vpc_classic_link, params)


def enable_vpc_classic_link_dns_support(
    vpc_id=None, vpc_lookup=None, region=None, keyid=None, key=None, profile=None,
):
    """
    Enables a VPC to support DNS hostname resolution for ClassicLink. If enabled,
    the DNS hostname of a linked EC2-Classic instance resolves to its private IP
    address when addressed from an instance in the VPC to which it's linked. Similarly,
    the DNS hostname of an instance in a VPC resolves to its private IP address
    when addressed from a linked EC2-Classic instance.

    :param str vpc_id: The ID of the VPC.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts. Used to lookup
      ``vpc_id`` if it is not provided.

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
    return __utils__["boto3.handle_response"](
        client.enable_vpc_classic_link_dns_support, params
    )


def import_key_pair(
    key_name,
    public_key_material,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
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
    zone_id=None,
    zone_name=None,
    group_name=None,
    message=None,
    opt_in_status=None,
    region_name=None,
    state=None,
    zone_type=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
        "availability_zone", filters=filters, client=client,
    )


def lookup_address(
    allocation_name=None,
    allocation_id=None,
    association_id=None,
    domain=None,
    instance_id=None,
    instance_lookup=None,
    network_border_group=None,
    network_interface_id=None,
    network_interface_lookup=None,
    network_interface_owner_id=None,
    private_ip_address=None,
    public_ip=None,
    tags=None,
    tag_key=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
    :param dict instance_lookup: Any kwarg that ``lookup_instance``
      accepts. Used to lookup ``instance_id`` if it is not provided.
    :param str network_border_group: The location from where the IP address is
      advertised.
    :param str network_interface_id: [EC2-VPC] The ID of the network interface
      that the address is associated with, if any.
    :param dict network_interface_lookup: Any kwarg that ``lookup_network_interface``
      accepts. Used to lookup ``network_interface_id`` if it is not provided.
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
    if instance_id is None and instance_lookup is not None:
        res = lookup_instance(
            region=region, keyid=keyid, key=key, profile=profile, **instance_lookup
        )
        if "error" in res:
            return res
        instance_id = res["result"]["InstanceId"]
    if network_interface_id is None and network_interface_lookup is not None:
        res = lookup_network_interface(
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            **network_interface_lookup,
        )
        if "error" in res:
            return res
        network_interface_id = res["result"]["NetworkInterfaceId"]
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
        "address", filters=filters, tags=tags, client=client,
    )


def lookup_customer_gateway(
    customer_gateway_id=None,
    customer_gateway_name=None,
    bgp_asn=None,
    ip_address=None,
    state=None,
    gateway_type=None,
    tags=None,
    tag_key=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Helper function to find a single DHCP options set.
    Can also be used to determine if a DHCP options set exists.

    The following paramers are translated into filters to refine the lookup:

    :param str customer_gateway_id: ID of the VPN customer gateway.
    :param str customer_gateway_name: The ``Name``-tag of the VPN customer gateway.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str bgp_asn: The customer gateway's Border Gateway Protocol (BGP)
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
        "customer_gateway", filters=filters, tags=tags, client=client,
    )


def lookup_dhcp_options(
    dhcp_options_id=None,
    dhcp_options_name=None,
    domain_name_servers=None,
    domain_name=None,
    ntp_servers=None,
    netbios_name_servers=None,
    netbios_node_type=None,
    owner_id=None,
    tags=None,
    tag_key=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
        "dhcp_options", filters=filters, tags=tags, client=client,
    )


def lookup_image(
    image_id=None,
    image_name=None,
    architecture=None,
    delete_on_termination=None,
    device_name=None,
    snapshot_id=None,
    volume_size=None,
    volume_type=None,
    encrypted=None,
    description=None,
    ena_support=None,
    hypervisor=None,
    image_type=None,
    is_public=None,
    kernel_id=None,
    manifest_location=None,
    owner_alias=None,
    owner_id=None,
    platform=None,
    product_code=None,
    product_code_type=None,
    ramdisk_id=None,
    root_device_name=None,
    root_device_type=None,
    state=None,
    state_reason_code=None,
    state_reason_message=None,
    sriov_net_support=None,
    tags=None,
    tag_key=None,
    virtualization_type=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    client=None,
):
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
        "image", filters=filters, tags=tags, client=client,
    )


def lookup_internet_gateway(
    internet_gateway_id=None,
    internet_gateway_name=None,
    attachment_state=None,
    attachment_vpc_id=None,
    attachment_vpc_lookup=None,
    owner_id=None,
    tags=None,
    tag_key=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
    :param dict attachment_vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``attachment_vpc_id`` is not provided.
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
    if attachment_vpc_id is None and attachment_vpc_lookup is not None:
        res = lookup_vpc(
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            client=client,
            **atachment_vpc_lookup,
        )
        if "error" in res:
            return res
        attachment_vpc_id = res["result"]["VpcId"]
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
        "internet_gateway", filters=filters, tags=tags, client=client,
    )


def lookup_key_pair(
    key_pair_id=None,
    fingerprint=None,
    key_name=None,
    tag_key=None,
    tags=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
        "key_pair", filters=filters, tags=tags, client=client,
    )


def lookup_local_gateway(
    local_gateway_id=None,
    local_gateway_name=None,
    route_table_id=None,
    route_table_lookup=None,
    association_id=None,
    virtual_interface_group_id=None,
    outpost_arn=None,
    state=None,
    tags=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Helper function to find a single local gateway.
    Can also be used to determine if a local gateway exists.

    The following paramers are translated into filters to refine the lookup:

    :param str local_gateway_id: The ID of a local gateway.
    :param str local_gateway_name: The ``Name``-tag of a local gateway.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str route_table_id: The ID of the local gateway route table.
    :param dict route_table_lookup: Any kwarg that ``lookup_route_table`` accepts.
      Used to lookup the route_table's ID if ``route_table_id`` is not provided.
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
    if route_table_id is None and route_table_lookup is not None:
        res = lookup_route_table(
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            client=client,
            **route_table_lookup,
        )
        if "error" in res:
            return res
        route_table_id = res["result"]["RouteTableId"]
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
        "local_gateway", filters=filters, tags=tags, client=client,
    )


def lookup_nat_gateway(
    nat_gateway_id=None,
    nat_gateway_name=None,
    state=None,
    subnet_id=None,
    subnet_lookup=None,
    tags=None,
    tag_key=None,
    vpc_id=None,
    vpc_lookup=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
    :param dict subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Used to lookup the subnet's ID if ``subnet_id`` is not provided.
      If ``vpc_id`` or ``vpc_lookup`` are provided, the resulting VPC ID will
      be used in the lookup of the subnet.
    :param dict tags: Any tags to filter on.
    :param str tag_key: The key of a tag assigned to the resource. Use this filter
      to find all resources assigned a tag with a specific key, regardless of
      the tag value.
    :param str vpc_id: The ID of the VPC in which the NAT gateway resides.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the vpc's ID if ``vpc_id`` is not provided.
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
    if vpc_id is None and vpc_lookup is not None:
        res = lookup_vpc(
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            client=client,
            **vpc_lookup,
        )
        if "error" in res:
            return res
        vpc_id = res["result"]["VpcId"]
    if subnet_id is None and subnet_lookup is not None:
        if vpc_id is not None:
            subnet_lookup["vpc_id"] = vpc_id
        res = lookup_subnet(
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            client=client,
            **subnet_lookup,
        )
        if "error" in res:
            return res
        subnet_id = res["result"]["SubnetId"]
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
        "nat_gateway", filters=filters, tags=tags, client=client,
    )


def lookup_network_acl(
    network_acl_id=None,
    network_acl_name=None,
    vpc_id=None,
    vpc_lookup=None,
    association_id=None,
    association_network_acl_id=None,
    association_subnet_id=None,
    association_subnet_lookup=None,
    default=None,
    entry_cidr=None,
    entry_icmp_code=None,
    entry_icmp_type=None,
    entry_ipv6_cidr=None,
    entry_port_range_from=None,
    entry_port_range_to=None,
    entry_protocol=None,
    entry_rule_action=None,
    entry_rule_number=None,
    filters=None,
    owner_id=None,
    tags=None,
    tag_key=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Helper function to find a single network ACL.
    Can also be used to determine if a network ACL exists.

    The following paramers are translated into filters to refine the lookup:

    :param str network_acl_id: ID of the network ACL.
    :param str network_acl_name: The ``Name``-tag of the network ACL.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str vpc_id: The ID of the VPC for the network ACL.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.
    :param str association_id: The ID of an association ID for the ACL.
    :param str association_network_acl_id: The ID of the network ACL involved in
      the association.
    :param str assocation_subnet_id: The ID of the subnet involved in the association.
    :param dict association_subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Used to lookup the associated subnet ID if ``association_subnet_id`` is
      not provided.
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
    if vpc_id is None and vpc_lookup is not None:
        res = lookup_vpc(
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            client=client,
            **vpc_lookup,
        )
        if "error" in res:
            return res
        vpc_id = res["result"]["VpcId"]
    if association_subnet_id is None and association_subnet_lookup is not None:
        res = lookup_subnet(
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            client=client,
            **association_subnet_lookup,
        )
        if "error" in res:
            return res
        association_subnet_id = res["result"]["SubnetId"]
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
        "network_acl", filters=filters, tags=tags, client=client,
    )


def lookup_route_table(
    route_table_id=None,
    route_table_name=None,
    vpc_id=None,
    vpc_lookup=None,
    association_id=None,
    association_route_table_id=None,
    association_subnet_id=None,
    association_subnet_lookup=None,
    association_main=None,
    owner_id=None,
    route_destination_cidr_block=None,
    route_destination_ipv6_cidr_block=None,
    route_destination_prefix_list_id=None,
    route_egress_only_internet_gateway_id=None,
    route_gateway_id=None,
    route_instance_id=None,
    route_nat_gateway_id=None,
    route_transit_gateway_id=None,
    route_origin=None,
    route_state=None,
    route_vpc_peering_connection_id=None,
    tags=None,
    tag_key=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Helper function to find a single route table.
    Can also be used to determine if a route table exists.

    The following paramers are translated into filters to refine the lookup:

    :param str route_table_id: ID of the route table.
    :param str route_table_name: The ``Name``-tag of the route table.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str vpc_id: The ID of the VPC for the route table.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.
    :param str association_id: The ID of an association ID for the route table.
    :param str association_route_table_id: The ID of the route table involved in
      the association.
    :param str association_subnet_id: The ID of the subnet involved in the association.
    :param dict association_subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Use dto lookup the subnet's ID if ``association_subnet_id`` is not provided.
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
    :param str route_egress_only_internet_gateway_id:  The ID of an egress-only
      Internet gateway specified in a route in the route table.
    :param str route_gateway_id: The ID of a gateway specified in a route in the table.
    :param str route_instance_id: The ID of an instance specified in a route in
      the table.
    :param str route_nat_gateway_id: The ID of a NAT gateway.
    :param str route_transit_gateway_id: The ID of a transit gateway.
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
    if vpc_id is None and vpc_lookup is not None:
        res = lookup_vpc(
            region=region, keyid=keyid, key=key, profile=profile, **vpc_lookup
        )
        if "error" in res:
            return res
        vpc_id = res["result"]["VpcId"]
    if association_subnet_id is None and association_subnet_lookup is not None:
        res = lookup_subnet(
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            **association_subnet_lookup,
        )
        if "error" in res:
            return res
        association_subnet_id = res["result"]["SubnetId"]
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
        "route_table", filters=filters, tags=tags, client=client,
    )


def lookup_security_group(
    group_id=None,
    group_name=None,
    description=None,
    egress_ip_permission_cidr=None,
    egress_ip_permission_from_port=None,
    egress_ip_permission_group_id=None,
    egress_ip_permission_group_name=None,
    egress_ip_permission_ipv6_cidr=None,
    egress_ip_permission_prefix_list_id=None,
    egress_ip_permission_protocol=None,
    egress_ip_permission_to_port=None,
    egress_ip_permission_user_id=None,
    ip_permission_cidr=None,
    ip_permission_from_port=None,
    ip_permission_group_id=None,
    ip_permission_group_name=None,
    ip_permission_ipv6_cidr=None,
    ip_permission_prefix_list_id=None,
    ip_permission_protocol=None,
    ip_permission_to_port=None,
    ip_permission_user_id=None,
    owner_id=None,
    tags=None,
    tag_key=None,
    vpc_id=None,
    vpc_lookup=None,
):
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
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.
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
    if vpc_id is None and vpc_lookup is not None:
        res = lookup_vpc(
            region=region, keyid=keyid, key=key, profile=profile, **vpc_lookup,
        )
        if "error" in res:
            return res
        vpc_id = res["result"]["VpcId"]
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
        "security_group", filters=filters, tags=tags, client=client,
    )


def lookup_subnet(
    subnet_id=None,
    subnet_name=None,
    subnet_arn=None,
    vpc_id=None,
    vpc_lookup=None,
    availability_zone=None,
    availability_zone_id=None,
    available_ip_address_count=None,
    cidr_block=None,
    default_for_az=None,
    ipv6_cidr_block=None,
    ipv6_cidr_block_association_id=None,
    ipv6_cidr_block_state=None,
    owner_id=None,
    state=None,
    tag_key=None,
    tags=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Helper function to find a single subnet.
    Can also be used to determine if a subnet exists.

    The following paramers are translated into filters to refine the lookup:

    :param str subnet_id: ID of the subnet.
    :param str subnet_name: The ``Name``-tag of the subnet.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str subnet_arn: The Amaxon Resource Name (ARN) of the subnet.
    :param str vpc_id: The ID of the VPC for the subnet.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup the VPC's ID if ``vpc_id`` is not provided.
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
    if vpc_id is None and vpc_lookup is not None:
        res = lookup_vpc(
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            client=client,
            **vpc_lookup,
        )
        if "error" in res:
            return res
        vpc_id = res["result"]["VpcId"]
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
                "vpc_id": vpc_id,
            }
        )
    )
    if client is None:
        client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return __utils__["boto3.lookup_resource"](
        "subnet", filters=filters, tags=tags, client=client,
    )


def lookup_tag(
    tag_key=None,
    resource_id=None,
    resource_type=None,
    tags=None,
    tag_value=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
        "tag", filters=filters, tags=tags, client=client,
    )


def lookup_vpc(
    vpc_id=None,
    vpc_name=None,
    cidr=None,
    cidr_block=None,
    cidr_block_association_id=None,
    cidr_block_state=None,
    dhcp_options_id=None,
    ipv6_cidr_block=None,
    ipv6_cidr_block_pool=None,
    ipv6_cidr_block_association_id=None,
    ipv6_cidr_block_state=None,
    is_default=None,
    owner_id=None,
    state=None,
    tags=None,
    tag_key=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
        "vpc", filters=filters, tags=tags, client=client,
    )


def lookup_vpc_endpoint(
    vpc_endpoint_id=None,
    vpc_endpoint_name=None,
    service_name=None,
    vpc_id=None,
    vpc_lookup=None,
    vpc_endpoint_state=None,
    tags=None,
    tag_key=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Helper function to find a single VPC peering connection.
    Can also be used to determine if a VPC peering connection exists.

    The following paramers are translated into filters to refine the lookup:

    :param str vpc_endpoint_id: The ID of the endpoint.
    :param str vpc_endpoint_name: The ``Name``-tag of the VPC endpoint.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str service_name: The name of the service.
    :param str vpc_id: The ID of the VPC in which the endpoint resides.
    :param dict vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup ``vpc_id`` if it is not provided.
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
    if vpc_id is None and vpc_lookup is not None:
        res = lookup_vpc(
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            client=client,
            **vpc_lookup,
        )
        if "error" in res:
            return res
        vpc_id = res["result"]["VpcId"]
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
        "vpc_endpoint", filters=filters, tags=tags, client=client,
    )


def lookup_vpc_endpoint_service(
    service_name=None,
    tags=None,
    tag_key=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    service_name=None,
    service_id=None,
    service_state=None,
    tags=None,
    tag_key=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
    vpc_peering_connection_id=None,
    vpc_peering_connection_name=None,
    accepter_vpc_cidr_block=None,
    accepter_vpc_owner_id=None,
    accepter_vpc_id=None,
    accepter_vpc_lookup=None,
    expiration_time=None,
    requester_vpc_cidr_block=None,
    requester_vpc_owner_id=None,
    requester_vpc_id=None,
    requester_vpc_lookup=None,
    status_code=None,
    status_message=None,
    tags=None,
    tag_key=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
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
    :param dict accepter_vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup ``accepter_vpc_id`` if it is not provided.
      It is allowed to provide alternative credentials in this dict if the owner
      of the accepter VPC is different from the account that is used to perform
      this lookup.
    :param datetime expiration_time: The expiration date and time for the VPC
      peering connection.
    :param str requester_vpc_cidr_block: The IPv4 CIDR block of the requester's VPC.
    :param str requester_vpc_owner_id: The AWS account ID of the owner of the
      requester VPC.
    :param str requester_vpc_id: The ID of the requester VPC.
    :param dict requester_vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup ``requester_vpc_id`` if it is not provided.
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
    if accepter_vpc_id is None and accepter_vpc_lookup is not None:
        for auth_item in ["region", "keyid", "key", "profile"]:
            if auth_item not in accepter_vpc_lookup and auth_item in locals():
                accepter_vpc_lookup[auth_item] = locals().get(auth_item)
        res = lookup_vpc(**accepter_vpc_lookup)
        if "error" in res:
            return res
        accepter_vpc_id = res["result"]["VpcId"]
    if requester_vpc_id is None and requester_vpc_lookup is not None:
        for auth_item in ["region", "keyid", "key", "profile"]:
            if auth_item not in requester_vpc_lookup and auth_item in locals():
                requester_vpc_lookup[auth_item] = locals().get(auth_item)
        res = lookup_vpc(**requester_vpc_lookup)
        if "error" in res:
            return res
        requester_vpc_id = res["result"]["VpcId"]
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
        "vpc_peering_connection", filters=filters, tags=tags, client=client,
    )


def lookup_vpn_gateway(
    vpn_gateway_id=None,
    vpn_gateway_name=None,
    amazon_side_asn=None,
    attachment_state=None,
    attachment_vpc_id=None,
    attachment_vpc_lookup=None,
    availability_zone=None,
    state=None,
    tags=None,
    tag_key=None,
    vpn_gateway_type=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Helper function to find a single virtual private gateway.
    Can also be used to determine if a virtual private gateway exists.

    The following paramers are translated into filters to refine the lookup:

    :param str vpn_gateway_id: The ID of the virtual private gateway.
    :param str vpn_gateway_name: The ``Name``-tag of the virtual private gateway.
      If also specifying ``Name`` in ``tags``, this option takes precedence.
    :param str amazon_side_asn: The Autonomous System Number (ASN) for the Amazon
      side of the gateway.
    :param str attachment_state: The current state of the attachment between the
      gateway and the VPC. Allowed values: attaching, attached, detaching, detached.
    :param str attachment_vpc_id: The ID of an attached VPC.
    :param dict attachment_vpc_lookup: Any kwarg that ``lookup_vpc`` accepts.
      Used to lookup ``attachment_vpc_id`` if it is not provided.
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
    if attachment_vpc_id is None and attachment_vpc_lookup is not None:
        res = lookup_vpc(**attachment_vpc_lookup)
        if "error" in res:
            return res
        attachment_vpc_id = res["result"]["VpcId"]
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
        "vpc_peering_connection", filters=filters, tags=tags, client=client,
    )


@arguments_to_list("security_group_ids", "security_group_lookups")
def modify_network_interface_attribute(
    network_interface_id=None,
    network_interface_lookup=None,
    delete_on_termination=None,
    attachment_id=None,
    description=None,
    security_group_ids=None,
    security_group_lookups=None,
    source_dest_check=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Modifies the specified network interface attribute. You can use this action
    to attach and detach security groups from an existing EC2 instance.
    You can modify multiple attributes; this function will call boto multiple times
    for each attribute. At the first failure, the error will be returned.

    :param str network_interface_id: The ID of the network interface.
    :param str network_interface_lookup: Any kwarg that ``lookup_network_interface``
      accepts. Used to lookup ``network_interface_id`` if it is not provided.
    :param bool delete_on_termination: Indicates whether the network interface
      is deleted when the instance is terminated. You must specify ``attachment_id``,
      ``network_interface_id`` or ``network_interface_lookup`` when modifying
      this attribute.
    :param str attachment_id: The ID of the network interface attachment.
    :param str description: A description for the network interface.
    :param str/list(str) security_group_ids: Changes the security groups for the
      network interface. The new set of groups you specify replaces the current
      set. You must specify at least one group, even if it's just the default security
      group in the VPC.
    :param str/list(str) security_group_lookups: Any kwarg that ``lookup_security_group``
      accepts. Used to lookup ``security_group_ids`` if it is not provided.
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
            "result_keys": "GroupId",
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
    spot_fleet_request_id=None,
    spot_fleet_request_lookup=None,
    excess_capacity_termination_policy=None,
    target_capacity=None,
    on_demand_target_capacity=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict spot_fleet_request_lookup: Any kwarg that ``lookup_spot_fleet_request``
      accepts. Used to lookup ``spot_fleet_request_id`` if it is not provided.
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
    with __salt__["boto3_generic.lookup_resources"](
        {
            "service": "ec2",
            "name": "spot_fleet_request",
            "kwargs": spot_fleet_request_lookup
            or {"spot_fleet_request_id": spot_fleet_request_id},
        },
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    ) as res:
        if "error" in res:
            return res
        params = {
            "ExcessCapacityTerminationPolicy": excess_capacity_termination_policy,
            "SpotFleetRequestId": res["result"]["spot_fleet_request"],
            "TargetCapacity": target_capacity,
            "OnDemandTargetCapacity": on_demand_target_capacity,
        }
    return __utils__["boto3.handle_response"](client.modify_spot_fleet_request, params)


def modify_subnet_attribute(
    subnet_id=None,
    subnet_lookup=None,
    assign_ipv6_address_on_creation=None,
    map_public_ip_on_launch=None,
    map_customer_owned_ip_on_launch=None,
    customer_owned_ipv4_pool=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Modifies one or more subnet attributes.

    :param str subnet_id: The ID of the subnet to modify.
    :param dict subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Used to lookup the Subnet's ID if ``subnet_id`` is not provided.
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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    if subnet_id is None and subnet_lookup is not None:
        res = lookup_subnet(client=client, **subnet_lookup)
        if "error" in res:
            return res
        subnet_id = res["result"]["SubnetId"]
    params = salt.utils.data.filter_falsey(
        {
            "AssignIpv6AddressOnCreation": {"Value": assign_ipv6_address_on_creation},
            "MapPublciIpOnLaunch": {"Value": map_public_ip_on_launch},
            "MapCustomerOwnedIpOnLaunch": {"Value": map_customer_owned_ip_on_launch},
        },
        recurse_depth=1,
    )
    for item, value in params.items():
        try:
            client.modify_subnet_attribute(SubnetId=subnet_id, **{item: value})
        except (ParamValidationError, ClientError) as exp:
            return {"error": __utils__["boto3.get_error"](exp)["message"]}
    return {"result": True}


def modify_vpc_attribute(
    vpc_id=None,
    vpc_lookup=None,
    enable_dns_support=None,
    enable_dns_hostnames=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Modifies the specified attribute of the specified VPC.

    :param str vpc_id: The ID of the VPC to operate on.
    :param dict vpc_lookup: Any kwarg that lookup_vpc accepts.
      When ``vpc_id`` is not provided, this is required, otherwise ignored.
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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    # We're doing the lookup manually here, as we only need to do it once.
    if vpc_id is None:
        res = lookup_vpc(client=client, **vpc_lookup)
        if "error" in res:
            return res
        vpc_id = res["result"]["VpcId"]
    params = salt.utils.data.filter_falsey(
        {
            "EnableDnsSupport": {"Value": enable_dns_support},
            "EnableDnsHostnames": {"Value": enable_dns_hostnames},
        },
        recurse_depth=1,
    )
    for item, value in params.items():
        try:
            client.modify_vpc_attribute(VpcId=vpc_id, **{item: value})
            ret["result"] = True
        except (ParamValidationError, ClientError) as exp:
            ret["error"] = __utils__["boto3.get_error"](exp)["message"]
    return ret


@arguments_to_list(
    "add_network_load_balancer_arns", "remove_network_load_balancer_arns"
)
def modify_vpc_endpoint_service_configuration(
    service_id=None,
    service_lookup=None,
    private_dns_name=None,
    remove_private_dns_name=None,
    acceptance_required=None,
    add_network_load_balancer_arns=None,
    remove_network_load_balancer_arns=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Modifies the attributes of your VPC endpoint service configuration. You can
    change the Network Load Balancers for your service, and you can specify whether
    acceptance is required for requests to connect to your endpoint service through
    an interface VPC endpoint.

    If you set or modify the private DNS name, you must prove that you own the
    private DNS domain name.

    :param str service_id: The ID of the service.
    :param dict service_lookup: Any kwarg that ``lookup_vpc_endpoint_service`` accepts.
      When ``service_id`` is not provided, this is required, otherwise ignored.
    :param str private_dns_name: The private DNS name to assign to the endpoint service.
    :param bool remove_private_dns_name: Removes the private DNS name of the endpoint service.
    :param bool acceptance_required: Indicates whether requests to create an endpoint
      to your service must be accepted.
    :param str/list(str) add_network_load_balancer_arns: The Amazon Resource Names
      (ARNs) of Network Load Balancers to add to your service configuration.
    :param str/list(str) remove_network_load_balancer_arns: The Amazon Resource
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
    service_id=None,
    service_lookup=None,
    add_allowed_principals=None,
    remove_allowed_principals=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Modifies the permissions for your VPC endpoint service. You can add or remove
    permissions for service consumers (IAM users, IAM roles, and AWS accounts)
    to connect to your endpoint service.

    If you grant permissions to all principals, the service is public. Any users
    who know the name of a public service can send a request to attach an endpoint.
    If the service does not require manual approval, attachments are automatically
    approved.

    :param str service_id: The ID of the service.
    :param dict service_lookup: Any kwarg that ``lookup_vpc_endpoint_service`` accepts.
      When ``service_id`` is not provided, this is required, otherwise ignored.
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
    instance_tenancy,
    vpc_id=None,
    vpc_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Modifies the instance tenancy attribute of the specified VPC. You can change
    the instance tenancy attribute of a VPC to ``default`` only. You cannot change
    the instance tenancy attribute to ``dedicated``.

    After you modify the tenancy of the VPC, any new instances that you launch
    into the VPC have a tenancy of ``default``, unless you specify otherwise during
    launch. The tenancy of any existing instances in the VPC is not affected.

    :param str instance_tenancy: The instance tenancy attribute for the VPC.
    :param str vpc_id: The ID of the VPC to operate on.
    :param dict vpc_lookup: Any kwarg that lookup_vpc accepts.
      When ``vpc_id`` is not provided, this is required, otherwise ignored.

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


@arguments_to_list("instance_ids", "instance_lookups")
def reboot_instances(
    instance_ids=None,
    instance_lookups=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Requests a reboot of the specified instances. This operation is asynchronous;
    it only queues a request to reboot the specified instances. The operation succeeds
    if the instances are valid and belong to you. Requests to reboot terminated
    instances are ignored.

    If an instance does not cleanly shut down within four minutes, Amazon EC2 performs
    a hard reboot.

    :param str/list(str) instance_ids: The instance IDs.
    :param dict/list(dict) instance_lookups: One or more dicts of kwargs that
      ``lookup_instance`` accepts. Used to lookup any ``instance_ids``
      if none are provided.

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


def register_image(
    name,
    image_location=None,
    architecture=None,
    block_device_mappings=None,
    description=None,
    ena_support=None,
    kernel_id=None,
    billing_products=None,
    ramdisk_id=None,
    root_device_name=None,
    sriov_net_support=None,
    virtualization_type=None,
    tags=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
      - Create an AMI from the instance using CreateImage .
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
    :param list(dict) block_device_mappings: See :py:func:`create_image` for the
      full description of this argument.
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
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Rejects a VPC peering connection request. The VPC peering connection must be
    in the pending-acceptance state. Use :py:func:`describe_vpc_peering_connections`
    to view your outstanding VPC peering connection requests. To delete an active
    VPC peering connection, or to delete a VPC peering connection request that
    you initiated, use :py:func:`delete_vpc_peering_connection`.

    :param str vpc_peering_connection_id: The ID of the VPC peering connection.
    :param dict vpc_peering_connection_lookup: Any kwarg that ``lookup_vpc_peering_connection``
      accepts. Used to lookup ``vpc_peering_connection_id`` if it is not provided.

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
    address_id=None,
    address_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    be able to recover it. For more information, see AllocateAddress .

    :param str address_id: The (Allocation)ID of the Elastic IP.
    :param dict address_lookup: Any kwarg that ``lookup_address``
      accepts. Used to lookup the address' ID if ``address_id``
      is not provided.
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
    association_id=None,
    network_acl_id=None,
    network_acl_lookup=None,
    subnet_id=None,
    subnet_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Changes which network ACL a subnet is associated with. By default when you
    create a subnet, it's automatically associated with the default network ACL.

    :param str association_id: The The ID of the current association between the
      original network ACL and the subnet.
    :param str network_acl_id: The ID of the new network ACL to associate with
      the subnet.
    :param str network_acl_lookup: Any kwarg that ``lookup_network_acl`` accepts.
      Used to lookup the network ACL ID if ``network_acl_id`` is not provided.
    :param str subnet_id: The ID of the subnet to associate the network ACL with.
      Only needs to be specified if ``association_id`` is not provided.
      Since a subnet can only be associated with one network ACL at a time,
      specifying the subnet is an alternative to specifying ``association_id``.
    :param str subnet_lookup: Any kwarg that ``lookup_subnet`` accepts.
      Used to lookup the subnet ID if ``subnet_id`` is not provided.

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
    protocol,
    egress,
    rule_number,
    rule_action,
    network_acl_id=None,
    network_acl_lookup=None,
    cidr_block=None,
    icmp_type=None,
    icmp_code=None,
    ipv6_cidr_block=None,
    port_range=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param str network_acl_lookup: Any kwarg that ``lookup_network_acl`` accepts.
      Used to lookup the network ACL ID if ``network_acl_id`` is not provided.
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
        elif len(port_range) != 2:
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
    route_table_id=None,
    route_table_lookup=None,
    destination_cidr_block=None,
    destination_ipv6_cidr_block=None,
    destination_prefix_list_id=None,
    egress_only_internet_gateway_id=None,
    egress_only_internet_gateway_lookup=None,
    gateway_id=None,
    gateway_lookup=None,
    instance_id=None,
    instance_lookup=None,
    local_target=None,
    nat_gateway_id=None,
    nat_gateway_lookup=None,
    transit_gateway_id=None,
    transit_gateway_lookup=None,
    local_gateway_id=None,
    local_gateway_lookup=None,
    network_interface_id=None,
    network_interface_lookup=None,
    vpc_peering_connection_id=None,
    vpc_peering_connection_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Replaces an existing route within a route table in a VPC. You must provide
    only one of the following: internet gateway, virtual private gateway, NAT
    instance, NAT gateway, VPC peering connection, network interface, egress-only
    internet gateway, or transit gateway.
    If you specify the route table by name only, you must supply at least one of
    ``vpc_name`` or ``vpc_id`` to perform the lookup for you.

    :param int route_table_id: The ID of the route table to operate on.
    :param dict route_table_lookup: Any kwarg that ``lookup_route_table`` accepts.
      Used to lookup the route_table's ID if ``route_table_id`` is not provided.
    :param str destination_cidr_block: The IPv4 CIDR address block used for the
      destination match. The value that you provide must match the CIDR of an
      existing route in the table.
    :param str destination_ipv6_cidr_block: The IPv6 CIDR address block used for
      the destination match. The value that you provide must match the CIDR of
      an existing route in the table.
    :param str destination_prefix_list_id: The ID of the prefix list for the route.
    :param str egress_only_internet_gateway_id: [IPv6 traffic only] The ID of an
      egress-only internet gateway.
    :param dict egress_only_internet_gateway_lookup: Any kwarg that
      ``lookup_egress_only_internet_gateway`` accepts. Used to lookup the egress-
      only internet gateway if ``egress_only_internet_gateway_id`` is not provided.
    :param str gateway_id: The ID of an internet gateway or virtual private gateway.
    :param dict gateway_lookup: Any kwarg that ``lookup_gateway`` accepts.
      Used to lookup the gateway's ID if ``gateway_id`` is not provided.
    :param str instance_id: The ID of a NAT instance in your VPC.
    :param dict instance_lookup: Any kwarg that ``lookup_instance`` accepts.
      Used to lookup the instance's ID if ``instance_id`` is not provided.
    :param bool local_target: Specifies whether to reset the local route to its
      default target (``local``).
    :param str nat_gateway_id: [IPv4 traffic only] The ID of a NAT gateway.
    :param dict nat_gateway_lookup: Any kwarg that ``lookup_nat_gateway`` accepts.
      Used to lookup the NAT gateway if ``nat_gateway_id`` is not provided.
    :param str transit_gateway_id: The ID of a transit gateway.
    :param dict transit_gateway_lookup: Any kwarg that ``lookup_transit_gateway``
      accepts. Used to lookup the transit gateway if ``transit_gateway_id`` is
      not provided.
    :param str local_gateway_id: The ID of the local gateway.
    :param dict local_gateway_lookup: Any kwarg that ``lookup_local_gateway``
      accepts. Used to lookup the transit gateway if ``local_gateway_id`` is
      not provided.
    :param str network_interface_id: The ID of a network interface.
    :param dict network_interface_lookup: Any kwarg that ``lookup_network_interface``
      accepts. Used to lookup the network interface if ``network_interface_id``
      is not provided.
    :param str vpc_peering_connection_id: The ID of a VPC peering connection.
    :param dict vpc_peering_connection_lookup: Any kwarg that ``lookup_vpc_peering_connection``
      accepts. Used to lookup the VPC peering connction if ``vpc_peering_connection_id``
      is not provided.

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
                "DestinationPrefixListId": destination_prefix_list_id,
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
    association_id=None,
    current_route_table_lookup=None,
    route_table_id=None,
    route_table_lookup=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Changes the route table associated with a given subnet, internet gateway, or
    virtual private gateway in a VPC. After the operation completes, the subnet
    or gateway uses the routes in the new route table.

    You can also use this operation to change which table is the main route table
    in the VPC. Specify the main route table's association ID and the route table
    ID of the new main route table.

    :param str association_id: The association ID.
    :param dict current_route_table_lookup: Any kwarg that ``lookup_route_table``
      accepts. Used to lookup the ``association_id`` if it is not provided.
    :param str route_table_id: The ID of the new route table to associate with
      the subnet.
    :param dict route_table_lookup: Any kwarg that ``lookup_route_table`` accepts.
      Used to lookup ``route_table_id`` if it is not provided.

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


def request_spot_fleet(
    iam_fleet_role,
    target_capacity,
    allocation_strategy=None,
    on_demand_allocation_strategy=None,
    excess_capacity_termination_policy=None,
    fulfilled_capacity=None,
    on_demand_fulfilled_capacity=None,
    launch_specifications=None,
    launch_template_configs=None,
    spot_price=None,
    on_demand_target_capacity=None,
    on_demand_max_total_price=None,
    spot_max_total_price=None,
    terminate_instances_with_expiration=None,
    request_type=None,
    valid_from=None,
    valid_until=None,
    replace_unhealthy_instances=None,
    instance_interruption_behavior=None,
    load_balancers_config=None,
    instance_pools_to_use_count=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param list(dict) launch_specifications: The launch specifications for the
      Spot Fleet request. If you specify ``launch_specifications``, you can't specify
      ``launch_template_configs``. If you include On-Demand capacity in your request,
      you must use ``launch_template_configs``. These dicts consist of:

      - SecurityGroups(list(dict)): One or more security groups. When requesting
        instances in a VPC, you must specify the IDs of the security groups. When
        requesting instances in EC2-Classic, you can specify the names or the IDs
        of the security groups. These dicts consist of:

        - GroupName (str): The name of the security group.
        - GroupId (str): The ID of the security group.
      - BlockDeviceMappings (list(dict)): One or more block devices that are mapped
        to the Spot Instances. You can't specify both a snapshot ID and an encryption
        value. This is because only blank volumes can be encrypted on creation.
        If a snapshot is the basis for a volume, it is not blank and its encryption
        status is used for the volume encryption status. For the specification of
        these dicts, see :py:func:`create_image`.
      - EbsOptimized (bool): Indicates whether the instances are optimized for
        EBS I/O. This optimization provides dedicated throughput to Amazon EBS
        and an optimized configuration stack to provide optimal EBS I/O performance.
        This optimization isn't available with all instance types. Additional usage
        charges apply when using an EBS Optimized instance.
        Default: ``False``
      - IamInstanceProfile (dict): The IAM instance profile. This dict consists of:

        - Arn (str): The Amazon Resource Name (ARN) of the instance profile.
        - Name (str): The name of the instance profile.
      - ImageId (str): The ID of the AMI.
      - InstanceType (str): The instance type.
      - KernelId (str): The ID of the kernel.
      - KeyName (str): The name of the key pair.
      - Monitoring (dict): Enable or disable monitoring for the instances. This
        dict consists of:

        - Enabled (bool): Enables monitoring for the instance. Default: ``False``.
      - NetworkInterfaces (list(dict)): One or more network interfaces. If you
        specify a network interface, you must specify subnet IDs and security group
        IDs using the network interface. See :py:func:`create_launch_template` for
        the description of these dicts.
      - Placement (dict): The placement information. This dict consists of:

        - AvailabilityZone (str): The Availability Zone.
          [Spot Fleet only] To specify multiple Availability Zones, separate them
          using commas; for example, "us-west-2a, us-west-2b".
        - GroupName (str): The name of the placement group.
        - Tenancy (str): The tenancy of the instance (if the instance is running
          in a VPC). An instance with a tenancy of ``dedicated`` runs on single-tenant
          hardware. The ``host`` tenancy is not supported for Spot Instances.
      - RamdiskId (str): The ID of the RAM disk. Some kernels require additional
        drivers at launch. Check the kernel requirements for information about
        whether you need to specify a RAM disk. To find kernel requirements, refer
        to the AWS Resource Center and search for the kernel ID.
      - SpotPrice (str): The maximum price per unit hour that you are willing to
        pay for a Spot Instance. If this value is not specified, the default is
        the Spot price specified for the fleet. To determine the Spot price per
        unit hour, divide the Spot price by the value of ``WeightedCapacity``.
      - SubnetId (str): The IDs of the subnets in which to launch the instances.
        To specify multiple subnets, separate them using commas; for example,
        "subnet-1234abcdeexample1, subnet-0987cdef6example2".
      - UserData (str): The Base64-encoded user data that instances use when starting up.
      - WeightedCapacity (float): The number of units provided by the specified
        instance type. These are the same units that you chose to set the target
        capacity in terms of instances, or a performance characteristic such as
        vCPUs, memory, or I/O.
        If the target capacity divided by this value is not a whole number, Amazon
        EC2 rounds the number of instances to the next whole number. If this value
        is not specified, the default is 1.
      - TagSpecifications (list(dict)): The tags to apply during creation.
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
    availability_zone_group=None,
    block_duration_minutes=None,
    instance_count=None,
    launch_group=None,
    launch_specification=None,
    spot_price=None,
    request_type=None,
    valid_from=None,
    valid_until=None,
    tags=None,
    instance_interruption_behavior=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict launch_specification: The launch specification. TODO: Fill in details or create a builder.
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


def revoke_security_group_egress(
    group_id=None,
    group_lookup=None,
    ip_permissions=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict group_lookup: Any kwarg that ``lookup_security_group`` accepts.
      Used to lookup the security group's ID if ``security_group_id`` is not provided.
    :param list(dict) ip_permissions: The sets of IP permissions. You can't specify
      a destination security group and a CIDR IP address range in the same set
      of permissions. For the content specifications, see ``authorise_security_group_egress``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
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


def revoke_security_group_ingress(
    group_id=None,
    group_lookup=None,
    ip_permissions=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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
    :param dict group_lookup: Any kwarg that ``lookup_security_group`` accepts.
      Used to lookup the security group's ID if ``security_group_id`` is not provided.
    :param list(dict) ip_permissions: The sets of IP permissions. You can't specify
      a destination security group and a CIDR IP address range in the same set
      of permissions. For the content specifications, see ``authorise_security_group_egress``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
      with ``True`` on success
    """
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


@arguments_to_list("instance_ids", "instance_lookups")
def start_instances(
    instance_ids=None,
    instance_lookups=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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

    :param str/list(str) instance_ids: The IDs of the instances.
    :param dict/lict(dict) instance_lookups: One or more dicts of kwargs that
      ``lookup_instance`` accepts. Used to lookup any ``instance_ids``
      if none are provided.
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
            "instance", "running", resource_id=instance_ids, client=client,
        )
    return res


@arguments_to_list("instance_ids", "instance_lookups")
def stop_instances(
    instance_ids=None,
    instance_lookups=None,
    hibernate=None,
    force=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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

    :param str/list(str) instance_ids: The IDs of the instances.
    :param dict/lict(dict) instance_lookups: One or more dicts of kwargs that
      ``lookup_instance`` accepts. Used to lookup any ``instance_ids``
      if none are provided.
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
            "instance", "stopped", resource_id=instance_ids, client=client,
        )
    return res


@arguments_to_list("instance_ids", "instance_lookups")
def terminate_instances(
    instance_ids=None,
    instance_lookups=None,
    blocking=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
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

    :param str/list(str) instance_ids: The IDs of the instances.
      Constraints: Up to 1000 instance IDs. We recommend breaking up this request
      into smaller batches.
    :param dict/lict(dict) instance_lookups: One or more dicts of kwargs that
      ``lookup_instance`` accepts. Used to lookup any ``instance_ids``
      if none are provided.
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
            "instance", "terminated", resource_id=instance_ids, client=client,
        )
    return res


# This has to be at the end of the file
MODULE_FUNCTIONS = {
    k: v for k, v in inspect.getmembers(sys.modules[__name__]) if inspect.isfunction(v)
}
