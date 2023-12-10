"""
Provide the service module for the proxy-minion SSH sample
.. versionadded:: 2015.8.2
"""

import fnmatch
import logging
import re

import salt.utils.platform

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}

# Define the module's virtual name
__virtualname__ = "service"


def __virtual__():
    """
    Only work on systems that are a proxy minion
    """
    try:
        if (
            salt.utils.platform.is_proxy()
            and __opts__["proxy"]["proxytype"] == "ssh_sample"
        ):
            return __virtualname__
    except KeyError:
        return (
            False,
            "The ssh_service execution module failed to load. Check the "
            "proxy key in pillar.",
        )

    return (
        False,
        "The ssh_service execution module failed to load: only works on an "
        "ssh_sample proxy minion.",
    )


def get_all():
    """
    Return a list of all available services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    """
    proxy_fn = "ssh_sample.service_list"
    return __proxy__[proxy_fn]()


def list_():
    """
    Return a list of all available services.

    CLI Example:

    .. code-block:: bash

        salt '*' service.list
    """
    return get_all()


def start(name, sig=None):
    """
    Start the specified service on the ssh_sample

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    """

    proxy_fn = "ssh_sample.service_start"
    return __proxy__[proxy_fn](name)


def stop(name, sig=None):
    """
    Stop the specified service on the rest_sample

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    """
    proxy_fn = "ssh_sample.service_stop"
    return __proxy__[proxy_fn](name)


def restart(name, sig=None):
    """
    Restart the specified service with rest_sample

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    """

    proxy_fn = "ssh_sample.service_restart"
    return __proxy__[proxy_fn](name)


def status(name, sig=None):
    """
    Return the status for a service via ssh_sample.
    If the name contains globbing, a dict mapping service name to True/False
    values is returned.

    .. versionchanged:: 2018.3.0
        The service name can now be a glob (e.g. ``salt*``)

    Args:
        name (str): The name of the service to check
        sig (str): Not implemented

    Returns:
        bool: True if running, False otherwise
        dict: Maps service name to True if running, False otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    """

    proxy_fn = "ssh_sample.service_status"
    contains_globbing = bool(re.search(r"\*|\?|\[.+\]", name))
    if contains_globbing:
        services = fnmatch.filter(get_all(), name)
    else:
        services = [name]
    results = {}
    for service in services:
        resp = __proxy__[proxy_fn](service)
        if resp["comment"] == "running":
            results[service] = True
        else:
            results[service] = False
    if contains_globbing:
        return results
    return results[name]


def running(name, sig=None):
    """
    Return whether this service is running.
    """
    return status(name).get(name, False)


def enabled(name, sig=None):
    """
    Only the 'redbull' service is 'enabled' in the test
    """
    return name == "redbull"
