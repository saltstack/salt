"""
Connection module for Amazon VPC.
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

import inspect
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
# Minimum required version of botocore to use tags in the _create call
SUPPORT_CREATE_TAGGING = {
    "vpc": "1.17.14",
    "subnet": "1.17.14",
    "dhcp_options": "1.17.14",
}
# Describing these resources will return an XSet instead of X-plural.
DESCRIBE_RESOURCES_RETURN_AS_SET = [
    "stale_security_group",
    "security_group_reference",
    "elastic_gpu",
    "offering",
    "host_reservation",
    "scheduled_instance_availability",
    "scheduled_instance",
    "connection_notification",
]


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


def _describe_resource(
    resource_type,
    ids=None,
    filters=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
    **kwargs
):
    """
    Helper function to deduplicate common code in describe-functions.

    :param str resource_type: The name of the resource type in snake_case.
    :param str/list ids: Zero or more resource_ids to describe.
    :param dict filters: Return only resources that match these filters.
    :param * kwargs: Any additional kwargs to pass to the boto3 function.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the result of the boto3 ``describe_{resource_type}``-call
        on succes.

    :raises: SaltInvocationError if there are errors regarding the provided arguments.
    """
    if not isinstance(ids, list):
        ids = [ids]
    if resource_type.endswith("ss"):
        resource_type_plural = resource_type + "es"
    elif resource_type.endswith("s"):
        resource_type_plural = resource_type
    elif resource_type in DESCRIBE_RESOURCES_RETURN_AS_SET:
        resource_type_plural = resource_type + "set"
    else:
        resource_type_plural = resource_type + "s"
    resource_type_uc = salt.utils.stringutils.snake_to_camel_case(
        resource_type, uppercamel=True
    )
    resource_type_uc_plural = salt.utils.stringutils.snake_to_camel_case(
        resource_type_plural, uppercamel=True
    )
    boto_filters = [
        {"Name": k, "Values": v if isinstance(v, list) else [v]}
        for k, v in (filters or {}).items()
    ]
    if client is None:
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    # Ugly hack, but AWS does not have a thing called AddressId(s), but instead uses AllocationId(s)
    params = salt.utils.data.filter_falsey(
        {
            "Filters": boto_filters,
            "{}Ids".format(
                resource_type_uc if resource_type != "address" else "Allocation"
            ): ids,
        },
        recurse_depth=1,
    )
    boto_func_name = "describe_{}".format(resource_type_plural)
    if not hasattr(client, boto_func_name):
        raise SaltInvocationError(
            'Boto3 EC2 client does not have a "{}"-function.'.format(boto_func_name)
        )
    boto_func = getattr(client, boto_func_name)
    try:
        res = boto_func(**params, **kwargs)
        log.debug("_describe_resource(%s): res: %s", resource_type, res)
        return {"result": res.get(resource_type_uc_plural)}
    except (ParamValidationError, ClientError) as exp:
        return {"error": __utils__["boto3.get_error"](exp)["message"]}


def _lookup_resource(
    resource_type,
    filters=None,
    tags=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    client=None,
):
    """
    Helper function to deduplicate common code in lookup-functions.

    :param str resource_type: The name of the resource type in snake_case.
    :param dict filters: The filters to use in the lookup.
    :param dict tags: The tags to filter on in the lookup.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the result of the boto ``describe_resource_type``-
        call on succes.
        If the call was succesful but returned nothing, both the 'error' and 'result'
        key will be set with the notice that nothing was found and an empty dict
        respectively (since it is assumed you're looking to find something).
    """
    ret = {}
    if filters is None:
        filters = {}
    if tags is not None:
        filters.update(
            {"tag:{}".format(tag_key): tag_value for tag_key, tag_value in tags.items()}
        )
    if not filters:
        raise SaltInvocationError(
            "No constraints where given when for lookup_{}.".format(resource_type)
        )
    res = _describe_resource(
        resource_type,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )
    log.debug("_lookup_resource(%s): res: %s", resource_type, res)
    if "error" in res:
        ret = res
    elif not res["result"]:
        ret["result"] = {}
        ret["error"] = "No {} found with the specified parameters".format(resource_type)
    elif len(res["result"]) > 1:
        resource_type_plural = resource_type + (
            "" if resource_type.endswith("s") else "s"
        )
        ret["error"] = (
            "There are multiple {} with the specified filters."
            " Please specify additional filters."
            "".format(resource_type_plural)
        )
    else:
        ret["result"] = res["result"][0]
    return ret


def _lookup_resources(resources, region=None, keyid=None, key=None, profile=None):
    """
    Helper function to perform multiple lookups successively

    :param str/(str, list)/(str, list, str/list)/list resources: One or more
        entries for attributes of resource types that this call requires.
        The values represent:

        - The name of the resource type to retrieve.
        - The kwargs to pass to ``lookup_resource``. You can pass alternate AWS
          IAM credentials (region, keyid, key) or profile if a specific resource
          needs to be looked up in another account, as can be the case with VPC
          peering connections.
        - The key to use with salt.utils.data.traverse_dict_and_list to extract
          the needed data element(s) from the result of _lookup_resource.
          Default: ``ResourceTypeId``

        For example, ``disassociate_route_table`` needs an AssociationId, which
        is an attribute of a ``route_table`` that can be looked up by various
        arguments (see ``lookup_route_table``). For that, this argument could be:
        ('route_table', {'route_table_name': 'My Name', 'association_subnet_id': 'subnet-1234'},
        'Associations:0:RouteTableAssociationId').

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with list of looked up resources on success.
    """
    ret = {}
    lookup_results = []
    if resources is None:
        resources = []
    elif not isinstance(resources, list):
        resources = [resources]
    for idx, item in enumerate(resources):
        resource_type, lookup_kwargs, result_keys = (list(item) + [None, None, None])[
            :3
        ]
        default_result_key = (
            salt.utils.stringutils.snake_to_camel_case(resource_type, uppercamel=True)
            + "Id"
        )
        default_lookup_kwarg = resource_type + "_id"
        if resource_type is None:
            raise saltInvocationError(
                "No resource_type specified in resource #{}".format(idx)
            )
        if lookup_kwargs and not isinstance(lookup_kwargs, dict):
            raise SaltInvocationError(
                "lookup kwargs specified is not a dict but: {}".format(
                    type(lookup_kwargs)
                )
            )
        result_keys = result_keys or [default_result_key]
        if not isinstance(result_keys, list):
            result_keys = [result_keys]
        if (
            result_keys == [default_result_key]
            and default_lookup_kwarg in lookup_kwargs
            and lookup_kwargs[default_lookup_kwarg] is not None
        ):
            # No lookup is neccesary
            lookup_results.append(lookup_kwargs[default_lookup_kwarg])
        else:
            if lookup_kwargs is None:
                lookup_kwargs = {}
            lookup_function = MODULE_FUNCTIONS.get("lookup_{}".format(resource_type))
            if not lookup_function:
                raise SaltInvocationError(
                    "This module does not have a lookup-function for {}"
                    "".format(resource_type)
                )
            conn_kwargs = {
                "region": lookup_kwargs.get("region", region),
                "keyid": lookup_kwargs.get("keyid", keyid),
                "key": lookup_kwargs.get("key", key),
                "profile": lookup_kwargs.get("profile", profile),
            }
            client = _get_client(**conn_kwargs)
            res = lookup_function(client=client, **lookup_kwargs)
            log.debug("lookup_resources: res: %s", res)
            if "error" in res:
                return res
            for result_key in result_keys:
                lookup_results.append(
                    salt.utils.data.traverse_dict_and_list(res["result"], result_key)
                )
                log.debug(
                    "lookup_resources: result_key: %s, result: %s",
                    result_key,
                    lookup_results[-1],
                )
    ret["result"] = lookup_results
    return ret


def _create_resource(
    resource_type,
    params=None,
    tags=None,
    wait_until_state=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
):
    """
    Helper function to deduplicate common code in create-functions.

    :param str resource_type: The name of the resource type in snake_case.
    :param dict params: Params to pass to the boto3 create_X function.
    :param dict tags: The tags to assign to the created object.
    :param str wait_until_state: The resource state to wait for (if available).

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the result of the boto ``create_dhcp_options``-call
        on succes.

    :raises: SaltInvocationError if there are errors regarding the provided arguments.
    """
    # support_create_tagging = LooseVersion(botocore.__version__) >= LooseVersion(SUPPORT_CREATE_TAGGING.get(resource_type, '9000'))
    support_create_tagging = False
    resource_type_uc = salt.utils.stringutils.snake_to_camel_case(
        resource_type, uppercamel=True
    )
    if params is None:
        params = {}
    if tags:
        boto_tags = [{"Key": k, "Value": v} for k, v in tags.items()]
        if support_create_tagging:
            params.update(
                {
                    "TagSpecifications": [
                        {
                            "ResourceType": resource_type.replace("_", "-"),
                            "Tags": boto_tags,
                        }
                    ],
                }
            )
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    boto_func_name = "create_{}".format(resource_type)
    if not hasattr(client, boto_func_name):
        raise SaltInvocationError(
            'Boto3 EC2 client does not have a "{}"-function.'.format(boto_func_name)
        )
    boto_func = getattr(client, boto_func_name)
    try:
        res = boto_func(**params)
        if tags and not support_create_tagging:
            tag_res = client.create_tags(
                Resources=[res[resource_type_uc]["{}Id".format(resource_type_uc)]],
                Tags=boto_tags,
            )
            if "error" in tag_res:
                return tag_res
        ret = res.get(resource_type_uc, False)
        if ret and tags and not support_create_tagging:
            # Add Tags to result description, just like when it _is_ supported.
            ret["Tags"] = boto_tags
        if ret and wait_until_state is not None:
            res = _wait_resource(resource_type, ret, wait_until_state, client=client)
            if "error" in res:
                return res
    except (ParamValidationError, ClientError) as exp:
        return {"error": __utils__["boto3.get_error"](exp)["message"]}
    return {"result": ret}


def _generic_action(
    primary,
    params,
    *args,
    required_resources=None,
    region=None,
    keyid=None,
    key=None,
    profile=None,
    **kwargs
):
    """
    Helper function to deduplicate code when calling ``primary``.

    :param callable primary: Function to call. Can either be a boto3.client function,
        or a function from this module.
    :param callable params: Callable (lambda or function) that takes the result of
        _lookup_resources(``required_resources``) (in order) and kwargs as arguments,
        and returns a dict of parameters to pass to the boto3 function.
    :param *args: Positional arguments to pass to the primary function.
    :param str/(str, list)/(str, list, str)/list required_resources: One or more
        entries for attributes of resource types that this call requires.
        The values represent:

        - The name of the resource type to retrieve.
        - The kwargs to pass to _lookup_resource. You can pass alternate AWS IAM
          credentials (region, keyid, key) or profile if a specific resource needs
          to be looked up in another account, as can be the case with VPC peering
          connections.
        - The key to use with salt.utils.data.traverse_dict_and_list to extract
          the needed data element(s) from the result of _lookup_resource.
          Default: ``ResourceTypeId``

        These retrieved data elements  will be fed into the ``params`` callable
        as positional arguments in the order they appear in ``required_resources``.

        For example, ``disassociate_route_table`` needs an AssociationId, which
        is an attribute of a ``route_table`` that can be looked up by various
        arguments (see ``lookup_route_table``). For that, this argument could be:
        ('route_table', {'route_table_name': 'My Name', 'association_subnet_id': 'subnet-1234'},
        'Associations:0:RouteTableAssociationId').
    :param dict kwargs: These will be passed to the callable ``params``.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with returned data if available, otherwise ``True`` on success.

    :raises: SaltInvocationError if there are errors regarding the provided arguments.
    """
    ret = {}
    if required_resources is None:
        required_resources = []
    elif not isinstance(required_resources, (list, tuple)):
        required_resources = [required_resources]
    if required_resources:
        lookup_results = _lookup_resources(
            required_resources,
            region=region,
            keyid=keyid,
            key=key,
            profile=profile,
            **kwargs,
        )
        if "error" in lookup_results:
            return lookup_results
        primary_params = params(*lookup_results["result"], **kwargs)
    else:
        primary_params = params(**kwargs)
    try:
        log.debug(
            "generic_action:\n" "\t\targs: %s\n" "\t\tparams: %s", args, primary_params
        )
        res = primary(*args, **primary_params)
        res.pop("ResponseMetadata", None)
    except (ParamValidationError, ClientError) as exp:
        return {"error": __utils__["boto3.get_error"](exp)["message"]}
    if "error" in res:
        return res
    if not res:
        ret["result"] = True
    elif isinstance(res, dict) and "result" in res:
        ret["result"] = res["result"]
    else:
        ret["result"] = res
    return ret


def _wait_resource(resource_type, resource_description, desired_state, client=None):
    """
    Helper function to use waiters.
    Returns immediately on error, otherwise blocks until the desired state is reached.

    :param str resource_type: The name of the resource involved.
    :param dict resource_description: The output of a describe_X or lookup_X function.
    :param str desired_state: The resource state to wait for.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with returned data if available, otherwise ``True`` on success.
    """
    ret = {}
    resource_type_cc = salt.utils.stringutils.snake_to_camel_case(
        resource_type, uppercamel=True
    )
    resource_id = resource_description.get(resource_type_cc + "Id")
    if not resource_id:
        ret["error"] = "No ResourceId found in resource_description"
    else:
        try:
            waiter = client.get_waiter(resource_type + "_" + desired_state)
            waiter.wait(**{resource_type_cc + "Ids": resource_id})
        except (ParameterValidationError, ClientError, WaiterError) as exc:
            ret["error"] = exc
    ret["result"] = "error" not in ret
    return ret


def _derive_ipv6_cidr_subnet(ipv6_subnet, ipv6_parent_block):
    """
    Helper function to create the 64bit IPv6 CIDR block given only the last
    digit(s) of the subnet.

    For example:
        ipv6_cidr_block = 1
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


# Here end the helper functions


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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    vpc_peering_connection_lookup = vpc_peering_connection_lookup or {
        "vpc_peering_connection_id": vpc_peering_connection_id
    }
    if "filters" not in vpc_peering_connection_lookup:
        vpc_peering_connection_lookup["filters"] = {}
    vpc_peering_connection_lookup["filters"].update(
        {"status-code": "pending-acceptance"}
    )
    required_resources = ("vpc_peering_connection", vpc_peering_connection_lookup)
    params = lambda x: {"VpcPeeringConnectionId": x}
    return _generic_action(
        client.accept_vpc_peering_connection,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
        with dict containing the result of the boto ``allocate_address``-call
        on succes.

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
    dhcp_options_lookup = dhcp_options_lookup or {"dhcp_options_id": dhcp_options_id}
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    required_resources = [
        ("dhcp_options", dhcp_options_lookup),
        ("vpc", vpc_lookup),
    ]
    params = lambda dhcp_options_id=None, vpc_id=None: {
        "DhcpOptionsId": dhcp_options_id,
        "VpcId": vpc_id,
    }
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return _generic_action(
        client.associate_dhcp_options, params, required_resources=required_resources,
    )


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
        with dict containing the result of the boto ``associate_route_table``-
        call on succes.

    :depends: boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_vpcs, boto3.client('ec2').describe_subnets, boto3.client('ec2').describe_route_tables, boto3.client('ec2').associate_route_table
    """
    route_table_lookup = route_table_lookup or {"route_table_id": route_table_id}
    subnet_lookup = subnet_lookup or {"subnet_id": subnet_id}
    required_resources = [
        ("route_table", route_table_lookup),
        ("subnet", subnet_lookup),
    ]
    params = lambda x, y: {"RouteTableId": x, "SubnetId": y}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return _generic_action(
        client.associate_route_table,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    subnet_lookup = subnet_lookup or {"subnet_id": subnet_id}
    res = lookup_subnet(client=client, **subnet_lookup)
    if "error" in res:
        return res
    subnet_id = res["result"]["SubnetId"]
    vpc_id = res["result"]["VpcId"]
    if ipv6_cidr_block is None:
        res = lookup_vpc(client=client, vpc_id=vpc_id)
        if "error" in res:
            return res
        ipv6_cidr_block_association_set = res["result"]["Ipv6CidrBlockAssociationSet"]
        if not ipv6_cidr_block_association_set:
            return {
                "error": 'VPC "{}" does not have an ipv6_cidr_block.'.format(vpc_id)
            }
        ipv6_cidr_block = _derive_ipv6_cidr_subnet(
            ipv6_subnet, ipv6_cidr_block_association_set[0]["Ipv6CidrBlock"]
        )
    params = lambda: {"SubnetId": subnet_id, "Ipv6CidrBlock": ipv6_cidr_block}
    return _generic_action(client.associate_subnet_cidr_block, params,)


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
    params = lambda x: salt.utils.data.filter_falsey(
        {
            "AmazonProvidedIpv6CidrBlock": amazon_provided_ipv6_cidr_block,
            "CidrBlock": cidr_block,
            "VpcId": x,
        }
    )
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    required_resources = ("vpc", vpc_lookup)
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return _generic_action(
        client.associate_vpc_cidr_block,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    internet_gateway_lookup = internet_gateway_lookup or {
        "internet_gateway_id": internet_gateway_id
    }
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    required_resources = [
        ("internet_gateway", internet_gateway_lookup),
        ("vpc", vpc_lookup),
    ]
    params = lambda x, y: {"InternetgatewayId": x, "VpcId": y}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return _generic_action(
        client.attach_internet_gateway,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    group_lookup = group_lookup or {"group_id": group_id}
    required_resources = ("security_group", group_lookup, "GroupId")
    params = lambda x: {
        "GroupId": x,
        "IpPermissions": ip_permissions,
    }
    return _generic_action(
        client.authorize_security_group_egress,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    group_lookup = group_lookup or {"group_id": group_id}
    required_resources = ("security_group", group_lookup, "GroupId")
    params = lambda x: {
        "GroupId": x,
        "IpPermissions": ip_permissions,
    }
    return _generic_action(
        client.authorize_security_group_ingress,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    return _create_resource(
        "customer_gateway",
        params,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    return _create_resource(
        "dhcp_options",
        params=params,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    res = _create_resource(
        "internet_gateway",
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    subnet_lookup = subnet_lookup or {"subnet_id": subnet_id}
    if not any((allocation_id, address_lookup)):
        # Create new Elastic IP
        res = allocate_address(region=region, keyid=keyid, key=key, profile=profile)
        if "error" in res:
            return res
        allocation_id = res["result"]["AllocationId"]
    address_lookup = address_lookup or {"allocation_id": allocation_id}
    required_resources = [
        ("subnet", subnet_lookup),
        ("address", address_lookup, "AllocationId"),
    ]
    params = lambda x, y: salt.utils.data.filter_falsey(
        {
            "params": {"SubnetId": x, "AllocationId": y},
            "tags": tags,
            "region": region,
            "keyid": keyid,
            "key": key,
            "profile": profile,
        },
        recurse_depth=1,
    )
    return _generic_action(
        _create_resource,
        params,
        "nat_gateway",
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        **({"wait_until_state": "available"} if blocking else {}),
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
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    required_resources = ("vpc", vpc_lookup)
    params = lambda x: salt.utils.data.filter_falsey(
        {
            "params": {"VpcId": x},
            "tags": tags,
            "region": region,
            "keyid": keyid,
            "key": key,
            "profile": profile,
        }
    )
    return _generic_action(
        _create_resource,
        params,
        "network_acl",
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    network_acl_lookup = network_acl_lookup or {"network_acl_id": network_acl_id}
    required_resources = ("network_acl", network_acl_lookup)
    params = lambda x: salt.utils.data.filter_falsey(
        {
            "CidrBlock": cidr_block,
            "Egress": egress,
            "IcmpTypeCode": {"Code": icmp_code, "Type": icmp_type},
            "Ipv6CidrBlock": ipv6_cidr_block,
            "NetworkAclId": x,
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
    return _generic_action(
        client.create_network_acl_entry,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


# pylint: disable=unused-argument
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
    my_locals = locals()
    lookup_results = {}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    for item in [
        "egress_only_internet_gateway",
        "gateway",
        "instance",
        "nat_gateway",
        "transit_gateway",
        "network_interface",
        "vpc_peering_connection",
    ]:
        item_id = my_locals.get(item + "_id")
        item_lookup = my_locals.get(item + "_lookup")
        item_ucc = salt.utils.stringutils.snake_to_camel_case(item, uppercamel=True)
        if item_id is None and item_lookup is not None:
            lookup_function = MODULE_FUNCTIONS.get("lookup_{}".format(item))
            if lookup_function is None:
                raise NotImplementedError(
                    "Lookup function for {} has not been implemented".format(item)
                )
            res = lookup_function(client=client, **item_lookup)
            if "error" in res:
                return res
            lookup_results[item] = res["result"][item_ucc + "Id"]
        else:
            lookup_results[item] = item_id
    route_table_lookup = route_table_lookup or {"route_table_id": route_table_id}
    required_resources = ("route_table", route_table_lookup)
    params = lambda x: salt.utils.data.filter_falsey(
        {
            "RouteTableId": x,
            "DestinationCidrBlock": destination_cidr_block,
            "DestinationIpv6CidrBlock": destination_ipv6_cidr_block,
            "DestinationPrefixListId": destination_prefix_list_id,
            "EgressOnlyInternetGatewayId": lookup_results.get(
                "egress_only_internet_gateway"
            ),
            "GatewayId": lookup_results.get("gateway"),
            "InstanceId": lookup_results.get("instance"),
            "NatGatewayId": lookup_results.get("nat_gateway"),
            "TransitGatewayId": lookup_results.get("transit_gateway"),
            "NetworkInterfaceId": lookup_results.get("network_interface"),
            "VpcPeeringConnectionId": lookup_results.get("vpc_peering_connection"),
        }
    )
    return _generic_action(
        client.create_route,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


# pylint: enable=unused-argument


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
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    required_resources = ("vpc", vpc_lookup)
    params = lambda x: salt.utils.data.filter_falsey(
        {
            "params": {"VpcId": x},
            "tags": tags,
            "region": region,
            "keyid": keyid,
            "key": key,
            "profile": profile,
        }
    )
    return _generic_action(
        _create_resource,
        params,
        "route_table",
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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

    :param
    """
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    required_resources = ("vpc", vpc_lookup)
    params = lambda x: salt.utils.data.filter_falsey(
        {
            "params": {"GroupName": name, "Description": description, "VpcId": x},
            "tags": tags,
            "region": region,
            "keyid": keyid,
            "key": key,
            "profile": profile,
        }
    )
    return _generic_action(
        _create_resource,
        params,
        "security_group",
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    if not any((vpc_id, vpc_lookup)):
        raise SaltInvocationError("At least one of vpc_id or vpc_lookup is required.")
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
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
    if ipv6_cidr_block is None:
        ipv6_cidr_block_association_set = res["result"]["Ipv6CidrBlockAssociationSet"]
        if ipv6_cidr_block_association_set:
            ipv6_cidr_block = _derive_ipv6_cidr_subnet(
                ipv6_subnet, ipv6_cidr_block_association_set[0]["Ipv6CidrBlock"]
            )
    params = salt.utils.data.filter_falsey(
        {
            "CidrBlock": cidr_block,
            "VpcId": vpc_id,
            "AvailabilityZone": availability_zone,
            "AvailabilityZoneId": availability_zone_id,
            "Ipv6CidrBlock": ipv6_cidr_block,
        }
    )
    return _create_resource(
        "subnet",
        params=params,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        **({"wait_until_state": "available"} if blocking else {}),
    )


def create_tags(resource_ids, tags, region=None, keyid=None, key=None, profile=None):
    """
    Adds or overwrites one or more tags for the specified Amazon EC2 resource or
    resources. Each resource can have a maximum of 50 tags. Each tag consists of
    a key and optional value. Tag keys must be unique per resource.

    :param str/list resource_ids: A (list of) ID(s) to create tags for.
    :param dict tags: Tags to create on the resource(s).

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with ``True`` on success.

    :depends: boto3.client('ec2').create_tags
    """
    params = {
        "Resources": resource_ids,
        "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
    }
    # Oh, the irony
    return _create_resource(
        "tags", params=params, region=region, keyid=keyid, key=key, profile=profile
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
    return _create_resource(
        "vpc",
        params=params,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


def create_vpc_endpoint(
    service_name,
    vpc_id=None,
    vpc_lookup=None,
    vpc_endpoint_type=None,
    policy_document=None,
    route_table_ids=None,  # pylint: disable=unused-argument
    route_table_lookups=None,  # pylint: disable=unused-argument
    subnet_ids=None,  # pylint: disable=unused-argument
    subnet_lookups=None,  # pylint: disable=unused-argument
    security_group_ids=None,  # pylint: disable=unused-argument
    security_group_lookups=None,  # pylint: disable=unused-argument
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
        with dict containing the result of the boto ``create_vpc_endpoint``-
        call on succes.
    """
    if not any((vpc_id, vpc_lookup)):
        raise SaltInvocationError("At least one of vpc_id or vpc_lookup is required.")
    my_locals = locals()
    lookup_results = {}
    for item in ["route_table", "subnet", "security_group"]:
        item_ids = my_locals.get(item + "_ids")
        item_lookups = my_locals.get(item + "_lookups")
        if item_ids is None and item_lookups is not None:
            item_ids = []
            lookup_function = MODULE_FUNCTIONS.get(item + "_lookup")
            if lookup_function is None:
                raise NotImplementedError(
                    "Lookup for {} is not implemented.".format(item)
                )
            for item_lookup in item_lookups:
                res = lookup_function(
                    region=region, keyid=keyid, key=key, profile=profile, **item_lookup
                )
                if "error" in res:
                    return res
                item_ids.append(
                    res["result"][
                        salt.utils.stringutils.snake_to_camel_case(
                            item + "_id", uppercamel=True
                        )
                    ]
                )
        lookup_results[item] = item_ids

    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    required_resources = ("vpc", vpc_lookup)
    params = lambda x: salt.utils.data.filter_falsey(
        {
            "params": {
                "ServiceName": service_name,
                "PolicyDocument": policy_document,
                "VpcId": x,
                "VpcEndpointType": vpc_endpoint_type,
                "RouteTableIds": lookup_results.get("route_table"),
                "SubnetIds": lookup_results.get("subnet"),
                "SecurityGroupIds": lookup_results.get("security_group"),
                "PrivateDnsEnabled": private_dns_enabled,
            },
            "tags": tags,
            "region": region,
            "keyid": keyid,
            "key": key,
            "profile": profile,
        }
    )
    res = _generic_action(
        _create_resource,
        params,
        "vpc_endpoint",
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )
    if "error" in res:
        return res
    if blocking:
        _wait_resource("vpc_endpoint", res["result"], "available", client=client)
    return res


def create_vpc_peering_connection(
    requester_vpc_id=None,
    requester_vpc_lookup=None,
    peer_vpc_id=None,
    peer_vpc_lookup=None,
    peer_owner_id=None,
    peer_region=None,
    peer_keyid=None,  # pylint: disable=unused-argument
    peer_key=None,  # pylint: disable=unused-argument
    peer_profile=None,  # pylint: disable=unused-argument
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
    if not any((requester_vpc_id, requester_vpc_lookup)):
        raise SaltInvocationError(
            "At least one of requester_vpc_id or requester_vpc_lookup is required"
        )
    if not any((peer_vpc_id, peer_vpc_lookup)):
        raise SaltInvocationError(
            "At least one of peer_vpc_id or peer_vpc_lookup is required"
        )
    if requester_vpc_id is None:
        res = vpc_lookup(
            region=region, keyid=keyid, key=key, profile=profile, **requester_vpc_lookup
        )
        if "error" in res:
            return res
        requester_vpc_id = res["result"]["VpcId"]
    if peer_vpc_id is None:
        for auth_item in ["region", "keyid", "key", "profile"]:
            peer_vpc_lookup[auth_item] = peer_vpc_lookup[auth_item] or locals().get(
                "peer_" + auth_item
            )
        res = vpc_lookup(**peer_vpc_lookup)
        if "error" in res:
            return res
        peer_vpc_id = res["result"]["VpcId"]
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    params = salt.utils.data.filter_falsey(
        {
            "VpcId": requester_vpc_id,
            "PeerVpcId": peer_vpc_id,
            "PeerOwnerId": peer_owner_id,
            "PeerRegion": peer_region or region,
        }
    )
    if LooseVersion(boto3.__version__) <= LooseVersion("1.4.6"):
        # Boto3 1.4.6 does not support the PeerRegion parameter.
        del params["PeerRegion"]
    res = _generic_action(
        client.create_vpc_peering_connection,
        lambda: params,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )
    if "error" in res:
        return res
    if blocking:
        _wait_resource(
            "vpc_peering_connection", res["result"], "pending", client=client
        )
    return res


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
    customer_gateway_lookup = customer_gateway_lookup or {
        "customer_gateway_id": customer_gateway_id
    }
    required_resources = ("customer_gateway", customer_gateway_lookup)
    params = lambda x: {"CustomerGatewayId": x}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return _generic_action(
        client.delete_customer_gateway,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    dhcp_options_lookup = dhcp_options_lookup or {"dhcp_options_id": dhcp_options_id}
    required_resources = ("dhcp_options", dhcp_options_lookup)
    params = lambda x: {"DhcpOptionsId": x}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return _generic_action(
        client.delete_dhcp_options,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    internet_gateway_lookup = internet_gateway_lookup or {
        "internet_gateway_id": internet_gateway_id
    }
    required_resources = ("internet_gateway_id", internet_gateway_lookup)
    params = lambda x: {"InternetGatewayId": x}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return _generic_action(
        client.delete_internet_gateway,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    nat_gateway_lookup = nat_gateway_lookup or {"nat_gateway_id": nat_gateway_id}
    required_resources = ("nat_gateway", nat_gateway_lookup)
    params = lambda x: {"NatGatewayId": x}
    res = _generic_action(
        client.delete_nat_gateway,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )
    if "error" in res:
        return res
    if blocking:
        nat_gateway_id = res["result"]["NatGatewayId"]
        _wait_resource("nat_gateway", res["result"], "deleted", client=client)
    return res


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
    network_acl_lookup = network_acl_lookup or {"network_acl_id": network_acl_id}
    required_resources = ("network_acl", network_acl_lookup)
    params = lambda x: {"NetworkAclId": network_acl_id}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return _generic_action(
        client.delete_network_acl,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    network_acl_lookup = network_acl_lookup or {"network_acl_id": network_acl_id}
    required_resources = ("network_acl", network_acl_lookup)
    params = lambda x: {
        "Egress": egress,
        "NetworkAclId": x,
        "RuleNumber": rule_number,
    }
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return _generic_action(
        client.delete_network_acl_entry,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    route_table_lookup = route_table_lookup or {"route_table_id": route_table_id}
    required_resources = ("route_table", route_table_lookup)
    params = lambda x: salt.utils.data.filter_falsey(
        {
            "RouteTableId": x,
            "DestinationCidrBlock": destination_cidr_block,
            "DestinationIpv6CidrBlock": destination_ipv6_cidr_block,
        }
    )
    return _generic_action(
        client.delete_route,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    route_table_lookup = route_table_lookup or {"route_table_id": route_table_id}
    required_resources = ("route_table", route_table_lookup)
    params = lambda x: {"RouteTableId": x}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return _generic_action(
        client.delete_route_table,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    if group_lookup is None:
        group_lookup = {}
    group_lookup.update(
        salt.utils.data.filter_falsey({"group_id": group_id, "group_name": group_name})
    )
    required_resources = ("security_group", group_lookup, "GroupId")
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    params = lambda x: {"GroupId": x}
    return _generic_action(
        client.delete_security_group,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    subnet_lookup = subnet_lookup or {"subnet_id": subnet_id}
    required_resources = ("subnet", subnet_lookup)
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    params = lambda x: {"SubnetId": x}
    return _generic_action(
        client.delete_subnet,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


def delete_tags(resources, tags, region=None, keyid=None, key=None, profile=None):
    """
    Deletes the specified set of tags from the specified set of resources.

    :param str/list resources: A (list of) ID(s) to delete tags from.
    :param dict tags: Tags to delete from the resource(s).

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with ``True`` on success.

    :depends: boto3.client('ec2').delete_tags
    """
    params = lambda: {
        "Resources": resources if isinstance(resources, list) else [resources],
        "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
    }
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return _generic_action(
        client.delete_tags, params, region=region, keyid=keyid, key=key, profile=profile
    )


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
    :param dict vpc_lookup: Any kwarg that lookup_vpc accepts.
        When ``vpc_id`` is not provided, this is required, otherwise ignored.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        containint ``True`` on success.

    :depends boto3.client('ec2').delete_vpc
    """
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    required_resources = ("vpc", vpc_lookup)
    params = lambda x: {"VpcId": x}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return _generic_action(
        client.delete_vpc,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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

    :param str vpc_peering_connection_name: The ``Name``-tag of the VPC peering
        connection to delete.
    :param str vpc_peering_connection_id: The ID of the VPC peering connection
        to delete

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the result of the boto ``delete_vpc_peering_connection``-
        call on succes.

    :depends: boto3.client('ec2').describe_vpc_peering_connections, boto3.client('ec2').delete_vpc_peering_connection
    """
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    vpc_peering_connection_lookup = vpc_peering_connection_lookup or {
        "vpc_peering_connection_id": vpc_peering_connection_id
    }
    required_resources = ("vpc_peering_connection", vpc_peering_connection_lookup)
    params = lambda x: {"VpcPeeringConnectionId": x}
    return _generic_action(
        client.delete_vpc_peering_connection,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    :param str/list public_ips: The (list of) Public IPs to specify the EIP(s) to describe.
    :param str/list allocation_ids: The (list of) Allocation IDs to specify the EIP(s) to describe.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the result of the boto ``describe_addresses``-
        call on succes.

    :depends: boto3.client('ec2').describe_addresses
    """
    if public_ips and not isinstance(public_ips, list):
        public_ips = [public_ips]
    return _describe_resource(
        "address",
        ids=allocation_ids,
        filters=filters,
        PublicIps=public_ips,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    return _describe_resource(
        "availability_zone",
        ids=zone_ids,
        filters=filters,
        ZoneNames=zone_names,
        AllAvailabilityZones=all_availability_zones,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list customer_gateway_ids: One or more customer gateway IDs.
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
    return _describe_resource(
        "customer_gateway",
        ids=customer_gateway_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list dhcp_option_ids: The (list of) DHCP option ID(s) to describe.
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
    return _describe_resource(
        "dhcp_options",
        ids=dhcp_option_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list internet_gateway_ids: The (list of) IDs of the internet gateway(s)
        to describe.
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
    return _describe_resource(
        "internet_gateway",
        ids=internet_gateway_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list local_gateway_ids: The (list of) ID(s) of local gateway(s)
        to describe.
    :param dict filters: One or more filters. See
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_local_gateways
        for a complete list.
        Note that the filters can be supplied as a dict with the keys being the
        names of the filter, and the value being either a string or a list of strings.
    """
    return _describe_resource(
        "local_gateway",
        ids=local_gateway_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list nat_gateway_ids: The (list of) NAT Gateway IDs to specify the NGW(s) to describe.
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
    return _describe_resource(
        "nat_gateway",
        ids=nat_gateway_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list route_table_ids: The (list of) ID(s) of network ACLs to describe.
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
    return _describe_resource(
        "network_acl",
        ids=network_acl_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list route_table_ids: The (list of) ID(s) of route tables to describe.
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
    return _describe_resource(
        "route_table",
        ids=route_table_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list group_ids: The IDs of the security groups. Required for security
        groups in a nondefault VPC. Default: Describes all your security groups.
    :param str/list group_names: [EC2-Classic and default VPC only] The names of
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
    if group_names and not isinstance(group_names, list):
        group_names = [group_names]
    return _describe_resource(
        "security_group",
        ids=group_ids,
        filters=filters,
        GroupNames=group_names,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    required_resources = ("vpc", vpc_lookup)
    params = lambda x: {"ids": x}
    return _generic_action(
        _describe_resource,
        params,
        "stale_security_group",
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list subnet_ids: The (list of) subnet IDs to specify the Subnets to describe.
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
    return _describe_resource(
        "subnet",
        ids=subnet_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _describe_resource(
        "tag",
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list transit_gateway_ids: The (list of) IDs of the transit gateways.
    :param dict filters: One or more filters. See
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_transit_gateways
        for a complete list.
        Note that the filters can be supplied as a dict with the keys being the
        names of the filter, and the value being either a string or a list of strings.
    """
    return _describe_resource(
        "transit_gateway",
        ids=transit_gateway_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


def describe_vpc_attributes(
    attributes,
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

    :param str/list attributes: The (list of) attribute(s) to get.
        Allowed values: ``enable_dns_support``, ``enable_dns_hostnames``
    :param str vpc_id: The ID of the VPC to operate on.
    :param dict vpc_lookup: Any kwarg that lookup_vpc accepts.
        When ``vpc_id`` is not provided, this is required, otherwise ignored.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the attributes and their values on succes.

    :depends: boto3.client('ec2').describe_vpc_attribute
    """
    if not any((vpc_id, vpc_lookup)):
        raise SaltInvocationError(
            "At least one of vpc_id or vpc_lookup must be specified."
        )
    if not isinstance(attributes, list):
        attributes = [attributes]
    ret = {}
    if client is None:
        client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    # We're not calling _generic_action here as that would mean it would do a
    # vpc lookup for every attribute.
    if vpc_id is None:
        res = lookup_vpc(client=client, **vpc_lookup)
        if "error" in res:
            return res
        vpc_id = res["result"]["VpcId"]
    params = {"VpcId": vpc_id}
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

    :param str/list: The (list of) ID(s) of the VPC endpoint(s) to describe.
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
    return _describe_resource(
        "vpc_endpoint",
        ids=vpc_endpoint_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list vpc_peering_connection_ids: The (list of) ID(s) of VPC Peering
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
    return _describe_resource(
        "vpc_peering_connection",
        ids=vpc_peering_connection_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list vpc_ids: One or more VPC IDs. Default: Describes all your VPCs.
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
    return _describe_resource(
        "vpc",
        ids=vpc_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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

    :param str/list vpn_gateway_ids: One or more virtual private gateway IDs.
    :param dict filters: The filters to apply to the list of virtual private gateways
        to describe.

    :rtype: dict
    :return: Dict with 'error' key if something went wrong. Contains 'result' key
        with dict containing the result of the boto ``describe_vpn_gateways``-
        call on succes.
    """
    return _describe_resource(
        "vpn_gateway",
        ids=vpn_gateway_ids,
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    if not any((vpc_id, vpc_lookup)):
        raise SaltInvocationError(
            "At least one of vpc_id or vpc_lookup must be specified."
        )
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    # Not using vpc_lookup here because _lookup_resources will not do a lookup
    # if the (implicitly wanted result key) vpc_id is already provided
    res = _lookup_resources(
        ("vpc", vpc_lookup), region=region, keyid=keyid, key=key, profile=profile,
    )
    if "error" in res:
        return res
    vpc_id = res["result"][0]

    internet_gateway_lookup = internet_gateway_lookup or {
        "internet_gateway_id": internet_gateway_id,
        "attachment_vpc_id": vpc_id,
    }
    required_resources = [
        ("internet_gateway", internet_gateway_lookup, "InternetGatewayId"),
    ]
    params = lambda x: {"InternetGatewayId": x, "VpcId": vpc_id}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return _generic_action(
        client.detach_internet_gateway,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
        if not any((subnet_id, subnet_lookup)):
            raise SaltInvocationError(
                "At least subnet_id or subnet_lookup must be specified if "
                "association_id is not given."
            )
        if subnet_id is None:
            res = lookup_subnet(client=client, **subnet_lookup)
            if "error" in res:
                return res
            subnet_id = res["result"]["SubnetId"]
        route_table_lookup = route_table_lookup or {"route_table_id": route_table_id}
        route_table_lookup["association_subnet_id"] = subnet_id
        res = lookup_route_table(client=client, **route_table_lookup)
        if "error" in res:
            return res
        association_id = res["result"]["Associations"][0]["RouteTableAssociationId"]
    params = lambda: {"AssociationId": association_id}
    return _generic_action(
        client.disassociate_route_table,
        params,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    if association_id is None:
        subnet_lookup = subnet_lookup or {"subnet_id": subnet_id}
        res = lookup_subnet(client=client, **subnet_lookup)
        if "error" in res:
            return res
        if not res["result"].get("Ipv6CidrBlockAssociationSet"):
            return {
                "error": "The subnet specified does not have an IPv6 CIDR block association"
            }
        current_associated_ipv6_cidr_block = res["Ipv6CidrBlockAssociationSet"][0][
            "Ipv6Cidrblock"
        ]
        if (
            ipv6_cidr_block is not None
            and current_associated_ipv6_cidr_block != ipv6_cidr_block
        ):
            return {
                "error": "The subnet specified has a different cidr block associated than specified for removal."
            }
        association_id = res["Ipv6CidrBlockAssociationSet"][0]["AssociationId"]
    params = lambda: {"AssociationId": association_id}
    res = _generic_action(client.disassociate_subnet_cidr_block, params,)
    if "error" in res:
        return res
    if blocking:
        # TODO: Implement custom boto waiters here.
        pass
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
    params = lambda x: {"AssociationId": x}
    if association_id is None:
        if not vpc_lookup:
            raise SaltInvocationError("vpc_lookup is required.")
        if "cidr_block" not in vpc_lookup and "ipv6_cidr_block" not in vpc_lookup:
            raise SaltinvocationError(
                'vpc_lookup must contain an entry for either "cidr_block" or "ipv6_cidr_block".'
            )
    vpc_lookup = vpc_lookup or {"association_id": association_id}
    required_resources = ("vpc", vpc_lookup, "CidrBlockAssociation:AssociationId")
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    res = _generic_action(
        client.disassociate_vpc_cidr_block,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )
    if "error" in res:
        return res
    if blocking:
        # TODO: Implement custom waiter
        pass
    return {"result": True}


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
    return _lookup_resource(
        "availability_zone",
        filters=filters,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "address",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "customer_gateway",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "dhcp_options",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "internet_gateway",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


def lookup_local_gateway(
    local_gateway_id=None,
    local_gateway_name=None,
    route_table_id=None,
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
    Helper function to find a single local gateawy.
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
    return _lookup_resource(
        "local_gateway",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    :param str state: The state of the NAT gateway:
        (``pending`` | ``failed`` | ``available`` | ``deleting`` | ``deleted``).
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
    return _lookup_resource(
        "nat_gateway",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "network_acl",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "route_table",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "security_group",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "subnet",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "tag",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "vpc",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "vpc_endpoint",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    return _lookup_resource(
        "vpc_peering_connection",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
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
    return _lookup_resource(
        "vpc_peering_connection",
        filters=filters,
        tags=tags,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
        client=client,
    )


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
    vpc_lookup = vpc_lookup or {"vpc_id": vpc_id}
    required_resources = ("vpc", vpc_lookup, "VpcId")
    params = lambda x: {"VpcId": x, "InstanceTenancy": instance_tenancy}
    client = _get_client(region=region, keyid=keyid, key=key, profile=profile)
    return _generic_action(
        client.modify_vpc_tenancy,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    address_lookup = address_lookup or {"AllocationId": address_id}
    required_resources = ("address", address_lookup, "AllocationId")
    params = lambda x: {"AllocationId": x}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    return _generic_action(
        client.release_address,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


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
        if not any((subnet_id, subnet_lookup)):
            raise SaltInvocationError(
                "Either subnet_id or subnet_lookup must be specified when "
                "association_id is not specified."
            )
        if subnet_id is None:
            client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
            subnet_lookup = subnet_lookup or {"subnet_id": subnet_id}
            res = lookup_subnet(client=client, **subnet_lookup)
            if "error" in res:
                return res
            subnet_id = res["result"]["SubnetId"]
        res = lookup_network_acl(association_subnet_id=subnet_id, client=client)
        if "error" in res:
            return res
        association_id = res["result"]["Associations"]["NetworkAclAssociationId"]
    network_acl_lookup = network_acl_lookup or {"network_acl_id": network_acl_id}
    required_resources = ("network_acl", network_acl_lookup)
    params = lambda x: {
        "AssociationId": association_id,
        "NetworkAclId": x,
    }
    return _generic_action(
        client.replace_network_acl_association,
        params,
        required_resources=required_resources,
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
    network_acl_lookup = network_acl_lookup or {"network_acl_id": network_acl_id}
    required_resources = ("network_acl", network_acl_lookup)
    params = lambda x: salt.utils.data.filter_falsey(
        {
            "CidrBlock": cidr_block,
            "Egress": egress,
            "IcmpTypeCode": {"Code": icmp_code, "Type": icmp_type},
            "Ipv6CidrBlock": ipv6_cidr_block,
            "NetworkAclId": x,
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
    return _generic_action(
        client.replace_network_acl_entry,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


# pylint: disable=unused-argument
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
    lookup_results = {}
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    # Amazon decided, in their wisdom, to let ``gateway`` be an IGW *or* a VPN gateway
    # So we need to look this up manually
    if gateway_id is None and gateway_lookup is not None:
        try:
            res = lookup_internet_gateway(client=client, **gateway_lookup)
            if res.get("result"):
                gateway_id = res["result"]["InternetGatewayId"]
            else:
                res = lookup_vpn_gateway(client=client, **gateway_lookup)
                if res.get("result"):
                    gateway_id = res["result"]["VpnGatewayId"]
        except ParameterValidationError:
            pass
        if gateway_id is None:
            if "error" in res:
                return res
            return {
                "error": (
                    "gateway_lookup was provided, but no single Internet gateway or "
                    "virtual private gateway matched."
                )
            }
    my_locals = locals()
    for item in [
        "egress_only_internet_gateway",
        "instance",
        "nat_gateway",
        "transit_gateway",
        "network_interface",
        "vpc_peering_connection",
    ]:
        item_id = my_locals.get(item + "_id")
        item_lookup = my_locals.get(item + "_lookup")
        item_ucc = salt.utils.stringutils.snake_to_camel_case(item, uppercamel=True)
        if item_id is None and item_lookup is not None:
            lookup_function = MODULE_FUNCTIONS.get("lookup_{}".format(item))
            if lookup_function is None:
                raise NotImplementedError(
                    "Lookup function for {} has not been implemented".format(item)
                )
            res = lookup_function(client=client, **item_lookup)
            if "error" in res:
                return res
            lookup_results[item] = res["result"][item_ucc + "Id"]
        else:
            lookup_results[item] = item_id
    route_table_lookup = route_table_lookup or {"route_table_id": route_table_id}
    required_resources = ("route_table", route_table_lookup)
    params = lambda x: salt.utils.data.filter_falsey(
        {
            "DestinationCidrBlock": destination_cidr_block,
            "DestinationIpv6CidrBlock": destination_ipv6_cidr_block,
            "DestinationPrefixListId": destination_prefix_list_id,
            "EgressOnlyInternetGatewayId": lookup_results.get(
                "egress_only_internet_gateway"
            ),
            "GatewayId": lookup_results.get("gateway"),
            "InstanceId": lookup_results.get("instance"),
            "LocalTarget": local_target,
            "NatGatewayId": lookup_results.get("nat_gateway"),
            "TransitGatewayId": lookup_results.get("transit_gateway"),
            "LocalGatewayid": lookup_results.get("local_gateway"),
            "NetworkInterfaceId": lookup_results.get("network_interface"),
            "RouteTableId": x,
            "VpcPeeringConnectionId": lookup_results.get("vpc_peering_connection"),
        }
    )
    return _generic_action(
        client.replace_route,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


# pylint: enable=unused-argument


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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    group_lookup = group_lookup or {"group_id": group_id}
    required_resources = ("security_group", group_lookup, "GroupId")
    params = lambda x: {
        "GroupId": x,
        "IpPermissions": ip_permissions,
    }
    return _generic_action(
        client.revoke_security_group_egress,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
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
    client = _get_client(region=region, key=key, keyid=keyid, profile=profile)
    group_lookup = group_lookup or {"group_id": group_id}
    required_resources = ("security_group", group_lookup, "GroupId")
    params = lambda x: {
        "GroupId": x,
        "IpPermissions": ip_permissions,
    }
    return _generic_action(
        client.revoke_security_group_ingress,
        params,
        required_resources=required_resources,
        region=region,
        keyid=keyid,
        key=key,
        profile=profile,
    )


# This has to be at the end of the file
MODULE_FUNCTIONS = {
    k: v for k, v in inspect.getmembers(sys.modules[__name__]) if inspect.isfunction(v)
}
