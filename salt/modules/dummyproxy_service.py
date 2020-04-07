# -*- coding: utf-8 -*-
"""
Provide the service module for the dummy proxy used in integration tests
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
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
        if salt.utils.platform.is_proxy() and __opts__["proxy"]["proxytype"] == "dummy":
            return __virtualname__
    except KeyError:
        return (
            False,
            "The dummyproxy_service execution module failed to load. Check "
            "the proxy key in pillar or /etc/salt/proxy.",
        )

    return (
        False,
        "The dummyproxy_service execution module failed to load: only works "
        "on the integration testsuite dummy proxy minion.",
    )


def get_all():
    """
    Return a list of all available services

    .. versionadded:: 2016.11.3

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    """
    proxy_fn = "dummy.service_list"
    return __proxy__[proxy_fn]()


def list_():
    """
    Return a list of all available services.

    .. versionadded:: 2016.11.3

    CLI Example:

    .. code-block:: bash

        salt '*' service.list
    """
    return get_all()


def start(name, sig=None):
    """
    Start the specified service on the dummy

    .. versionadded:: 2016.11.3

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    """

    proxy_fn = "dummy.service_start"
    return __proxy__[proxy_fn](name)


def stop(name, sig=None):
    """
    Stop the specified service on the dummy

    .. versionadded:: 2016.11.3

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    """
    proxy_fn = "dummy.service_stop"
    return __proxy__[proxy_fn](name)


def restart(name, sig=None):
    """
    Restart the specified service with dummy.

    .. versionadded:: 2016.11.3

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    """

    proxy_fn = "dummy.service_restart"
    return __proxy__[proxy_fn](name)


def status(name, sig=None):
    """
    Return the status for a service via dummy, returns a bool
    whether the service is running.

    .. versionadded:: 2016.11.3

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    """

    proxy_fn = "dummy.service_status"
    resp = __proxy__[proxy_fn](name)
    if resp["comment"] == "stopped":
        return False
    if resp["comment"] == "running":
        return True


def running(name, sig=None):
    """
    Return whether this service is running.

    .. versionadded:: 2016.11.3

    """
    return status(name).get(name, False)


def enabled(name, sig=None):
    """
    Only the 'redbull' service is 'enabled' in the test

    .. versionadded:: 2016.11.3

    """
    return name == "redbull"
