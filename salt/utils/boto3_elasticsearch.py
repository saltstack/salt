"""
Botocore waiters for elasticsearch that are not present in boto3+botocore (yet).

:codeauthor: Herbert Buurman <herbert.buurman@ogd.nl>
:depends: boto3
"""

import salt.utils.versions
from salt.exceptions import SaltInvocationError

try:
    import botocore.waiter
except ImportError:
    pass


WAITER_CONFIGS = {
    "ESDomainAvailable": {
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
    "ESUpgradeFinished": {
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
    "ESDomainDeleted": {
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
    "ESDomainCreated": {
        "delay": 30,
        "operation": "DescribeElasticsearchDomain",
        "maxAttempts": 60,
        "acceptors": [
            {
                "expected": True,
                "matcher": "path",
                "state": "success",
                "argument": "DomainStatus.Created",
            }
        ],
    },
}


def __virtual__():
    """
    Only load if botocore libraries exist.
    """
    return salt.utils.versions.check_boto_reqs(check_boto=False)


@salt.utils.decorators.is_deprecated(globals(), "Sulfur")
def get_waiter(client, waiter=None, waiter_config=None):
    """
    Gets a botocore waiter using either one of the preconfigured models by name
    ``waiter``, or with a manually supplied ``waiter_config``.

    :param botoclient client: The botocore client to use.
    :param str waiter: The name of the waiter config to use.
        Either ``waiter`` or ``waiter_config`` must be supplied.
        If both ``waiter`` and ``waiter_config`` are supplied, ``waiter`` takes
        presedence, unless no configuration for ``waiter`` exists.
    :param dict waiter_config: The manual waiter config to use.
        Either waiter or waiter_config must be supplied.

    :returns botocore.waiter
    """
    if not any((waiter, waiter_config)):
        raise SaltInvocationError(
            "At least one of waiter or waiter_config must be specified."
        )
    waiter_model = botocore.waiter.WaiterModel(
        {"version": 2, "waiters": {waiter: WAITER_CONFIGS.get(waiter, waiter_config)}}
    )
    return botocore.waiter.create_waiter_with_client(waiter, waiter_model, client)


@salt.utils.decorators.is_deprecated(globals(), "Sulfur")
def list_waiters():
    """
    Lists the builtin waiter configuration names.

    :returns list
    """
    return WAITER_CONFIGS.keys()
