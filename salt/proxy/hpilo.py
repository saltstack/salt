"""
Proxy minion to interact with HP iLO.

.. versionadded:: 3002

:codeauthor: `Jasper Lievisse Adriaanse <j@jasper.la>`

Dependencies
============

The `hpilo` Python module, this can be installed via pip:

.. code-block:: bash

    pip install python-hpilo

Configuration
=============

To connect the proxy minion to an HP iLO device the following settings are
required to be set in the pillar, e.g. `/srv/pillar/node1-oob.sls`

.. code-block:: yaml

    proxy:
        proxytype: hpilo
        host: <IP or hostname of the iLO>
        port: 443 (default)
        username: Administrator (default)
        password: <password>

Then hook this up for the proxy minion with id `node1-oob` in `/src/pillar/top.sls`

.. code-block:: yaml

    base:
        'node1-ilo':
          - node1-oob
"""

# Import python libs
import logging

try:
    import hpilo

    HAVE_HPILO = True
except ImportError:
    HAVE_HPILO = False

log = logging.getLogger(__name__)

__proxyenabled__ = ["hpilo"]
__virtualname__ = "hpilo"

DETAILS = {}


def __virtual__():
    """
    Ensure python-hpilo is available.
    """
    if HAVE_HPILO:
        return __virtualname__
    else:
        return (
            False,
            "The hpilo execution module cannot be loaded: required hpilo module not found.",
        )


def init(opts):
    """
    Establish a connection to the device and perform a login.
    """
    # At least the host and password are required.
    DETAILS["credentials"] = {
        "hostname": opts["proxy"]["host"],
        "login": opts["proxy"].get("username", "Administrator"),
        "password": opts["proxy"]["password"],
        "port": opts["proxy"].get("port", 443),
        "ssl_verify": opts["proxy"].get("ssl_verify", True),
    }

    try:
        DETAILS["conn"] = hpilo.Ilo(**DETAILS["credentials"])
    except hpilo.IloLoginFailed:
        log.error(
            "Failed to authenticate to {}. Please check the provided username/password.".format(
                DETAILS["credentials"]["hostname"]
            )
        )
        raise


def initialized():
    """
    Returns True if init() was successfully called.
    """
    return DETAILS.get("conn", False)


def _conn():
    return DETAILS.get("conn", None)


def ping():
    """
    Perform a simple request to ensure the device is still alive.

    CLI example:

    .. code-block:: bash

        salt vault-ilo test.ping
    """
    try:
        _conn().get_server_name()
        return True
    except hpilo.IloError:
        return False


def shutdown(opts):
    """
    Shut down by means of explicitly deleting the session object requiring a new logon.
    """
    del DETAILS["conn"]


def grains():
    """
    Return cache of dynamic grains.

    The following facts are set:
    - asset_tag
    - firmware_date
    - firmware_version
    - license_type
    - management_processor
    - power_status
    - product_name

    Based on the type of device (i.e. rack servers) these additional grains are also set:
    - bay
    - enclosure_name
    - enclosure_sn
    - enclosure_type
    - enclosure_uuid
    - rack_name

    CLI example:

    .. code-block:: bash

        salt vault-ilo grains.items
    """
    if not DETAILS.get("grains_cache", {}):
        return _grains()

    return DETAILS["grains_cache"]


def _grains():
    """
    Helper function to gather a set of information from the iLO which are returned as facts.

    XXX: pick out relevant information from get_host_data() to get mem_total, hwaddr_interfaces
    XXX: additionally call get_network_settings() to set dns and perhaps some IP address related settings?
         see what a regular minion sets for these types of grains
    """
    DETAILS["grains_cache"] = _conn().get_fw_version()
    DETAILS["grains_cache"].update(_conn().get_asset_tag())
    DETAILS["grains_cache"]["vendor"] = "HP"
    DETAILS["grains_cache"]["power_status"] = _conn().get_host_power_status()
    DETAILS["grains_cache"]["product_name"] = _conn().get_product_name()

    try:
        DETAILS["grains_cache"] = _conn().get_rack_settings()
    except hpilo.IloNotARackServer:
        log.debug("_grains(): Server is NOT a rack server; Rack commands do not apply.")

    return DETAILS["grains_cache"]


def grains_refresh():
    """
    Refresh grains from the proxied device.
    """
    DETAILS["grains_cache"] = None
    return grains()


def set_power(state):
    """
    Set host power to the desired state.
    """
    try:
        pwr = _conn().set_host_power(state)
        return True
    except hpilo.IloError as e:
        log.error(
            "Failed to set host power on {} to {}: {}".format(
                DETAILS["credentials"]["hostname"], state, e
            )
        )
        return False


def shutdown_server(hold=False):
    """
    Gracefully shutdown the server.
    """
    # Check to see if the server is powered off already, because pushing
    # the button again in that case will power it on again.
    if not _conn().get_host_power_status():
        log.debug("server already powered off")
        return True

    try:
        if hold:
            _conn().hold_pwr_btn()
        else:
            _conn().press_pwr_btn()

        return True
    except hpilo.IloError as e:
        log.error(
            "Failed to power off {}: {}".format(DETAILS["credentials"]["hostname"], e)
        )
        return False


def list_users():
    """
    List all configured users on the system.
    """
    try:
        return _conn().get_all_users()
    except hpilo.IloError as e:
        log.error(
            "Failed to get all users from {}: {}".format(
                DETAILS["credentials"]["hostname"], e
            )
        )
        return {}


def get_user(username):
    """
    Get detailed information about a single configured user.
    """
    try:
        return _conn().get_user(username)
    except hpilo.IloError as e:
        log.error(
            "Failed to get user information about {} from {}: {}".format(
                username, DETAILS["credentials"]["hostname"], e
            )
        )
        return {}


def get_boot_order():
    """
    Return the list of persistent boot devices.
    """
    return _conn().get_persistent_boot()


def set_boot(devices, onetime=False):
    """
    Set the boot devices where `devices`. This applies to both persistent and one time boot.
    """
    try:
        if onetime:
            _conn().set_one_time_boot("".join(devices))
        else:
            _conn().set_persistent_boot(",".join(devices))
        return True
    except hpilo.IloError as e:
        log.error(
            "Failed to set boot device(s) on {}: {}".format(
                DETAILS["credentials"]["hostname"], e
            )
        )
        return False
