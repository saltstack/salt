"""
Botocore waiters that are not present in boto3+botocore (yet).

:codeauthor: Herbert Buurman <herbert.buurman@ogd.nl>
:depends: boto3
"""
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import SaltInvocationError

try:
    import botocore.waiter

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


WAITER_CONFIGS = {
    "es_domain_available": {
        "delay": 60,
        "operation": "DescribeElasticsearchDomainConfig",
        "maxAttempts": 60,
        "acceptors": [
            {
                "expected": "Active",
                "matcher": "path",
                "state": "success",
                "argument": "DomainConfig.ElasticsearchClusterConfig.Status.State",
            },
            {
                "expected": True,
                "matcher": "pathAny",
                "state": "failure",
                "argument": "DomainConfig.*.Status.PendingDeletion",
            },
        ],
    },
    "es_upgrade_finished": {
        "delay": 60,
        "operation": "DescribeElasticsearchDomain",
        "maxAttempts": 60,
        "acceptors": [
            {
                "expected": False,
                "matcher": "path",
                "state": "success",
                "argument": "DomainStatus.UpgradeProcessing",
            }
        ],
    },
    "es_domain_deleted": {
        "delay": 30,
        "operation": "DescribeElasticsearchDomain",
        "maxAttempts": 60,
        "acceptors": [
            {
                "expected": True,
                "matcher": "path",
                "state": "retry",
                "argument": "DomainStatus.Deleted",
            },
            {
                "expected": False,
                "matcher": "path",
                "state": "failure",
                "argument": "DomainStatus.Processing",
            },
            {
                "expected": "ResourceNotFoundException",
                "matcher": "error",
                "state": "success",
            },
        ],
    },
}


WAITER_CONFIG_GENERATORS = {
    "es_domain": {
        "created": {
            "value_path": "DomainStatus.Created",
            "success_values": True,
            "operation": "DescribeElasticsearchDomain",
        },
    },
    "nat_gateway": {
        "deleted": {
            "value_path": "NatGateways[].State",
            "success_values": ["deleted"],
            "failure_values": ["pending", "failed", "available"],
            "error_actions": {"InvalidNatGatewayID.NotFound": "success"},
        },
    },
    "spot_fleet_request": {
        "fulfilled": {
            "value_path": "SpotFleetRequestConfigs[].ActivityStatus",
            "success_values": ["fulfilled"],
            "failure_values": ["error", "pending_termination"],
        },
    },
    "subnet_ipv6_cidr_block": {
        "disassociated": {
            "value_path": "length(Subnets[]) == `0`",
            "success_values": [True],
            "success_matcher": "path",
            "failure_values": [],
            "operation": "DescribeSubnets",
        },
    },
    "vpc_cidr_block": {
        "associated": {
            "value_path": "Vpcs[].CidrBlockAssociationSet[].CidrBlockState.State",
            "success_values": ["associated"],
            "failure_values": ["disassociating", "disassociated", "failing", "failed"],
            "operation": "DescribeVpcs",
        },
        "disassociated": {
            "value_path": "length(Vpcs[]) == `0`",
            "success_values": [True],
            "success_matcher": "path",
            "failure_values": [],
            "operation": "DescribeVpcs",
        },
    },
    "vpc_ipv6_cidr_block": {
        "associated": {
            "value_path": "Vpcs[].Ipv6CidrBlockAssociationSet[].Ipv6CidrBlockState.State",
            "success_values": ["associated"],
            "failure_values": ["disassociating", "disassociated", "failing", "failed"],
            "operation": "DescribeVpcs",
        },
        "disassociated": {
            "value_path": "length(Vpcs[]) == `0`",
            "success_values": [True],
            "success_matcher": "path",
            "failure_values": [],
            "operation": "DescribeVpcs",
        },
    },
    "vpc_peering_connection": {
        "pending": {
            "value_path": "VpcPeeringConnections[].Status.Code",
            "success_values": ["pending-acceptance"],
            "failure_values": [
                "active",
                "deleted",
                "rejected",
                "failed",
                "expired",
                "deleting",
            ],
            "error_actions": {"InvalidVpcPeeringConnectionID.NotFound": "retry"},
        },
    },
    "vpc_endpoint": {
        "available": {
            "value_path": "VpcEndpoints[].State",
            "success_values": ["Available"],
            "failure_values": ["Deleting", "Deleted", "Rejected", "Failed", "Expired"],
            "error_actions": {"InvalidVpcEndpointId.NotFound": "retry"},
        },
    },
    "vpn_gateway": {
        "deleted": {
            "value_path": "VpnGateways[].State",
            "success_values": ["deleted"],
            "failure_values": ["pending"],
        },
        "detached": {  # Note that you will have to specify the attachment.vpc-id filter as well as the vpn gateway id.
            "value_path": "VpnGateways[].VpcAttachments[].State",
            "success_values": ["detached"],
            "failure_values": ["attaching"],
        },
    },
}


def __virtual__():
    """
    Only load if botocore libraries exist.
    """
    return HAS_BOTO and salt.utils.versions.check_boto_reqs(check_boto=False)


def _pluralize(resource):
    """
    Helper function to pluralize resources.
    Used for converting resource names to describe_function names.
    """
    ret = resource
    if resource.endswith("ss"):
        ret += "es"
    elif resource.endswith("s"):
        pass
    else:
        ret += "s"
    return ret


def generate_config(
    resource_name,
    value_path,
    success_values,
    failure_values,
    error_actions=None,
    success_matcher="pathAll",
    failure_matcher="pathAny",
    delay=30,
    max_attempts=60,
    operation=None,
):
    """
    Helper function to generate a boto3 waiter config.

    :param str resource_name: The name of the resource in snake_case.
    :param str value_path: A jsonpath-expression, applied to the result of ``operation_resource``
      that leads to the value to check against. Use ``[]`` to denote an array, and
      periods ``.`` before a nested dictionary key.
      For example: ``VpcPeeringConnections[].Status.Code``.
    :param list(str) success_values: A list of a subset of possible values retrieved
      by following ``value_path`` that indicate a success.
    :param list(str) failure_values: A list of a subset of possible values retrieved
      by following ``value_path`` that indicate failure.
    :param dict error_actions: What to do when exceptions get raised. Each entry
      consists of the name of the exception and the action to take.
      Allowed action values: ``success``, ``failure``, ``retry``.
      For example: ``{'ResourceNotFoundException': 'retry'}``.
    :param int delay: The delay in seconds between attempts.
    :param int max_attempts: The maximum attempts to take before failing.
    :param str operation: The AWS API function to call to retrieve the information
        for the waiter. Default: ``plural(DescribeResourceName)``
    """
    if not isinstance(success_values, list):
        raise SaltInvocationError(
            "The argument success_values must be a list, not {}".format(
                type(success_values)
            )
        )
    if not isinstance(failure_values, list):
        raise SaltInvocationError(
            "The argument failure_values must be a list, not {}".format(
                type(failure_values)
            )
        )
    operation = operation or salt.utils.stringutils.snake_to_camel_case(
        "describe_{}".format(_pluralize(resource_name))
    )
    ret = {
        "delay": delay,
        "operation": operation,
        "maxAttempts": max_attempts,
        "acceptors": [],
    }
    for item in success_values:
        ret["acceptors"].append(
            {
                "matcher": success_matcher,
                "expected": item,
                "state": "success",
                "argument": value_path,
            }
        )
    for item in failure_values:
        ret["acceptors"].append(
            {
                "matcher": failure_matcher,
                "expected": item,
                "state": "failure",
                "argument": value_path,
            }
        )
    for expected, state in (error_actions or {}).items():
        ret["acceptors"].append(
            {"matcher": "error", "expected": expected, "state": state}
        )
    return ret


def get_waiter(
    client, waiter=None, waiter_config=None, resource_name=None, desired_state=None
):
    """
    Gets a botocore waiter using either one of the preconfigured models by name
    ``waiter``, or with a manually supplied ``waiter_config``.
    Alternatively, you can provide ``resource_name`` and ``desired_state`` to construct
    the ``waiter``-argument. This allows for the configuration to be generated.

    :param botoclient client: The botocore client to use.
    :param str waiter: The name of the waiter config to use.
        Either ``waiter`` or ``waiter_config`` must be supplied.
        If both ``waiter`` and ``waiter_config`` are supplied, ``waiter`` takes
        presedence, unless no configuration for ``waiter`` exists.
    :param dict waiter_config: The manual waiter config to use.
        Either waiter or waiter_config must be supplied.
    :param str resource_name: Name of the resource to get a waiter for.
        For example: ``instance`` or ``vpc_peering_connection`` or ``customer_gateway``.
    :param str desired_state: The desired state to be waiting for. Used only for
        looking up the correct configuration generator.
        For example: ``available``, ``deleted``, ``created``, ``pending``.

    :returns botocore.waiter
    """
    if not waiter:
        if not all((resource_name, desired_state)):
            raise SaltInvocationError(
                "When waiter is not supplied, resource_name and desired_state are required."
            )
        waiter = "{}_{}".format(resource_name, desired_state)
    if not waiter_config:
        if waiter not in WAITER_CONFIGS:
            config_generator = WAITER_CONFIG_GENERATORS.get(resource_name, {}).get(
                desired_state, {}
            )
            if not config_generator:
                raise SaltInvocationError(
                    "No waiter_config was supplied, and no waiter configuration "
                    'could be found or generated for waiter "{}".'
                    "".format(waiter)
                )
            waiter_config = generate_config(resource_name, **config_generator)
        else:
            waiter_config = WAITER_CONFIGS[waiter]

    waiter_model = botocore.waiter.WaiterModel(
        {"version": 2, "waiters": {waiter: waiter_config}}
    )
    return botocore.waiter.create_waiter_with_client(waiter, waiter_model, client)


def list_waiters():
    """
    Lists the builtin and generatable waiter configuration names.

    :returns list
    """
    ret = list(WAITER_CONFIGS.keys())
    for resource in WAITER_CONFIG_GENERATORS:
        for desired_state in resource:
            ret.append("{}_{}".format(resource, desired_state))
    return ret
