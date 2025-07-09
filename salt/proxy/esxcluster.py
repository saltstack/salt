"""
Proxy Minion interface module for managing VMWare ESXi clusters.

Dependencies
============

- pyVmomi
- jsonschema

Configuration
=============
To use this integration proxy module, please configure the following:

Pillar
------

Proxy minions get their configuration from Salt's Pillar. This can now happen
from the proxy's configuration file.

Example pillars:

``userpass`` mechanism:

.. code-block:: yaml

    proxy:
      proxytype: esxcluster
      cluster: <cluster name>
      datacenter: <datacenter name>
      vcenter: <ip or dns name of parent vcenter>
      mechanism: userpass
      username: <vCenter username>
      passwords: (required if userpass is used)
        - first_password
        - second_password
        - third_password

``sspi`` mechanism:

.. code-block:: yaml

    proxy:
      proxytype: esxcluster
      cluster: <cluster name>
      datacenter: <datacenter name>
      vcenter: <ip or dns name of parent vcenter>
      mechanism: sspi
      domain: <user domain>
      principal: <host kerberos principal>

proxytype
^^^^^^^^^
To use this Proxy Module, set this to ``esxdatacenter``.

cluster
^^^^^^^
Name of the managed cluster. Required.

datacenter
^^^^^^^^^^
Name of the datacenter the managed cluster is in. Required.

vcenter
^^^^^^^
The location of the VMware vCenter server (host of ip) where the datacenter
should be managed. Required.

mechanism
^^^^^^^^^
The mechanism used to connect to the vCenter server. Supported values are
``userpass`` and ``sspi``. Required.

Note:
    Connections are attempted using all (``username``, ``password``)
    combinations on proxy startup.

username
^^^^^^^^
The username used to login to the host, such as ``root``. Required if mechanism
is ``userpass``.

passwords
^^^^^^^^^
A list of passwords to be used to try and login to the vCenter server. At least
one password in this list is required if mechanism is ``userpass``.  When the
proxy comes up, it will try the passwords listed in order.

domain
^^^^^^
User domain. Required if mechanism is ``sspi``.

principal
^^^^^^^^^
Kerberos principal. Rquired if mechanism is ``sspi``.

protocol
^^^^^^^^
If the ESXi host is not using the default protocol, set this value to an
alternate protocol. Default is ``https``.

port
^^^^
If the ESXi host is not using the default port, set this value to an
alternate port. Default is ``443``.

Salt Proxy
----------

After your pillar is in place, you can test the proxy. The proxy can run on
any machine that has network connectivity to your Salt Master and to the
vCenter server in the pillar. SaltStack recommends that the machine running the
salt-proxy process also run a regular minion, though it is not strictly
necessary.

To start a proxy minion one needs to establish its identity <id>:

.. code-block:: bash

    salt-proxy --proxyid <proxy_id>

On the machine that will run the proxy, make sure there is a configuration file
present. By default this is ``/etc/salt/proxy``. If in a different location, the
``<configuration_folder>`` has to be specified when running the proxy:
file with at least the following in it:

.. code-block:: bash

    salt-proxy --proxyid <proxy_id> -c <configuration_folder>

Commands
--------

Once the proxy is running it will connect back to the specified master and
individual commands can be runs against it:

.. code-block:: bash

    # Master - minion communication
    salt <cluster_name> test.ping

    # Test vcenter connection
    salt <cluster_name> vsphere.test_vcenter_connection

States
------

Associated states are documented in
:mod:`salt.states.esxcluster </ref/states/all/salt.states.esxcluster>`.
Look there to find an example structure for Pillar as well as an example
``.sls`` file for configuring an ESX cluster from scratch.
"""

import logging
import os

import salt.exceptions
from salt.config.schemas.esxcluster import EsxclusterProxySchema
from salt.utils.dictupdate import merge

# This must be present or the Salt loader won't load this module.
__proxyenabled__ = ["esxcluster"]

# External libraries
try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
GRAINS_CACHE = {}
DETAILS = {}


# Set up logging
log = logging.getLogger(__name__)
# Define the module's virtual name
__virtualname__ = "esxcluster"


def __virtual__():
    """
    Only load if the vsphere execution module is available.
    """
    if HAS_JSONSCHEMA:
        return __virtualname__

    return False, "The esxcluster proxy module did not load."


def init(opts):
    """
    This function gets called when the proxy starts up. For
    login
    the protocol and port are cached.
    """
    log.debug("Initting esxcluster proxy module in process %s", os.getpid())
    log.debug("Validating esxcluster proxy input")
    schema = EsxclusterProxySchema.serialize()
    log.trace("schema = %s", schema)
    proxy_conf = merge(opts.get("proxy", {}), __pillar__.get("proxy", {}))
    log.trace("proxy_conf = %s", proxy_conf)
    try:
        jsonschema.validate(proxy_conf, schema)
    except jsonschema.exceptions.ValidationError as exc:
        raise salt.exceptions.InvalidConfigError(exc)

    # Save mandatory fields in cache
    for key in ("vcenter", "datacenter", "cluster", "mechanism"):
        DETAILS[key] = proxy_conf[key]

    # Additional validation
    if DETAILS["mechanism"] == "userpass":
        if "username" not in proxy_conf:
            raise salt.exceptions.InvalidConfigError(
                "Mechanism is set to 'userpass', but no "
                "'username' key found in proxy config."
            )
        if "passwords" not in proxy_conf:
            raise salt.exceptions.InvalidConfigError(
                "Mechanism is set to 'userpass', but no "
                "'passwords' key found in proxy config."
            )
        for key in ("username", "passwords"):
            DETAILS[key] = proxy_conf[key]
    else:
        if "domain" not in proxy_conf:
            raise salt.exceptions.InvalidConfigError(
                "Mechanism is set to 'sspi', but no 'domain' key found in proxy config."
            )
        if "principal" not in proxy_conf:
            raise salt.exceptions.InvalidConfigError(
                "Mechanism is set to 'sspi', but no "
                "'principal' key found in proxy config."
            )
        for key in ("domain", "principal"):
            DETAILS[key] = proxy_conf[key]

    # Save optional
    DETAILS["protocol"] = proxy_conf.get("protocol")
    DETAILS["port"] = proxy_conf.get("port")

    # Test connection
    if DETAILS["mechanism"] == "userpass":
        # Get the correct login details
        log.debug(
            "Retrieving credentials and testing vCenter connection for "
            "mehchanism 'userpass'"
        )
        try:
            username, password = find_credentials()
            DETAILS["password"] = password
        except salt.exceptions.SaltSystemExit as err:
            log.critical("Error: %s", err)
            return False
    return True


def ping():
    """
    Returns True.

    CLI Example:

    .. code-block:: bash

        salt esx-cluster test.ping
    """
    return True


def shutdown():
    """
    Shutdown the connection to the proxy device. For this proxy,
    shutdown is a no-op.
    """
    log.debug("esxcluster proxy shutdown() called...")


def find_credentials():
    """
    Cycle through all the possible credentials and return the first one that
    works.
    """

    # if the username and password were already found don't fo though the
    # connection process again
    if "username" in DETAILS and "password" in DETAILS:
        return DETAILS["username"], DETAILS["password"]

    passwords = DETAILS["passwords"]
    for password in passwords:
        DETAILS["password"] = password
        if not __salt__["vsphere.test_vcenter_connection"]():
            # We are unable to authenticate
            continue
        # If we have data returned from above, we've successfully authenticated.
        return DETAILS["username"], password
    # We've reached the end of the list without successfully authenticating.
    raise salt.exceptions.VMwareConnectionError(
        "Cannot complete login due to incorrect credentials."
    )


def get_details():
    """
    Function that returns the cached details
    """
    return DETAILS
