"""
Execution module to interact with the HP iLO proxy minion.

.. versionadded:: 3002

:codeauthor: `Jasper Lievisse Adriaanse <j@jasper.la>`
"""

# Import Python libs
import logging

# Import Salt libs
import salt.utils.platform

log = logging.getLogger(__name__)

__proxyenabled__ = ["hpilo"]
__virtualname__ = "hpilo"


def __virtual__():
    if salt.utils.platform.is_proxy() and "proxy" in __opts__:
        return __virtualname__
    return (
        False,
        "The hpilo execution module cannot be loaded, it only works on proxy minions",
    )


def set_power_on():
    """
    Power on the system.

    Returns:
        boolean indicating the result of the request.

    CLI example:

    .. code-block:: bash

        salt vault-ilo hpilo.set_power_on
    """
    return __proxy__["hpilo.set_power"](True)


def set_power_off():
    """
    Forcibly power down the host. This is equivalent to pulling the power cord
    (except the iLO remains powered on). To gracefully shutdown a system use
    `shutdown_system`.

    Returns:
        boolean indicating the result of the request.

    CLI example:

    .. code-block:: bash

        salt vault-ilo hpilo.set_power_off
    """
    return __proxy__["hpilo.set_power"](False)


def shutdown_server(hold=False):
    """
    Initiate a shutdown of the server.

    Args:
        hold (boolean): whether to simulate holding the button to force
        a shutdown. Defaults to ``False``.

    Returns:
        boolean indicating the result of the request.

    CLI example:

    .. code-block:: bash

        salt vault-ilo hpilo.set_power_off
    """
    return __proxy__["hpilo.shutdown_server"](hold)


def list_users():
    """
    Query the device for all configured users.

    Returns:
        list of all users configured by the iLO.

    CLI example:

    .. code-block:: bash

        salt vault-ilo hpilo.list_users
    """
    return __proxy__["hpilo.list_users"]()


def user_details(username):
    """
    Query the device for detailed user information.

    Args:
        username (str): username to query for.

    Returns:
        dict containing details for the specified user.

    CLI example:

    .. code-block:: bash

        salt vault-ilo hpilo.user_details Administrator
    """
    return __proxy__["hpilo.get_user"](username)


def get_boot_order():
    """
    Get the list of configured boot devices, in order of usage.

    Returns:
        list of device names.

    CLI example:

    .. code-block:: bash

        salt vault-ilo hpilo.get_boot_order
    """
    return __proxy__["hpilo.get_boot_order"]()


def set_boot_order(devices):
    """
    Modify the persistent boot order. If a device is not explicitly provided
    its position in the list (as returned by `get_boot_order`) won't be modified.

    Args:
        devices (list): list of device names.

    Returns:
        boolean indicating the result of the request.

    CLI example:

    .. code-block:: bash

        salt vault-ilo hpilo.set_boot_order '["hdd", "usb", "network1"]'
    """
    return __proxy__["hpilo.set_boot"](devices)


def set_onetime_boot(device):
    """
    Set the one time boot device. Note that numered devices (such as `network1`) are not
    valid. Instead drop the integer when using it as a one time boot device.
    Additionally `normal` and `rbsu` can be used.

    Args:
        device (str): name of the one time boot device.

    Returns:
        boolean indicating the result of the request.

    CLI example:

    .. code-block:: bash

        salt vault-ilo hpilo.set_onetime_boot network

    """
    return __proxy__["hpilo.set_boot"]([device], True)
