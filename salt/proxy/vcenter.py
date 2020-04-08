# -*- coding: utf-8 -*-
"""
Proxy Minion interface module for managing VMWare vCenters.

:codeauthor: :email:`Rod McKenzie (roderick.mckenzie@morganstanley.com)`
:codeauthor: :email:`Alexandru Bleotu (alexandru.bleotu@morganstanley.com)`

Dependencies
============

- pyVmomi Python Module

pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on certain
    versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that this original ESXi State
Module was developed against.


Configuration
=============
To use this proxy module, please use on of the following configurations:


.. code-block:: yaml

    proxy:
      proxytype: vcenter
      vcenter: <ip or dns name of parent vcenter>
      username: <vCenter username>
      mechanism: userpass
      passwords:
        - first_password
        - second_password
        - third_password

    proxy:
      proxytype: vcenter
      vcenter: <ip or dns name of parent vcenter>
      username: <vCenter username>
      domain: <user domain>
      mechanism: sspi
      principal: <host kerberos principal>

proxytype
^^^^^^^^^
The ``proxytype`` key and value pair is critical, as it tells Salt which
interface to load from the ``proxy`` directory in Salt's install hierarchy,
or from ``/srv/salt/_proxy`` on the Salt Master (if you have created your
own proxy module, for example). To use this Proxy Module, set this to
``vcenter``.

vcenter
^^^^^^^
The location of the VMware vCenter server (host of ip). Required

username
^^^^^^^^
The username used to login to the vcenter, such as ``root``.
Required only for userpass.

mechanism
^^^^^^^^
The mechanism used to connect to the vCenter server. Supported values are
``userpass`` and ``sspi``. Required.

passwords
^^^^^^^^^
A list of passwords to be used to try and login to the vCenter server. At least
one password in this list is required if mechanism is ``userpass``

The proxy integration will try the passwords listed in order.

domain
^^^^^^
User domain. Required if mechanism is ``sspi``

principal
^^^^^^^^
Kerberos principal. Rquired if mechanism is ``sspi``

protocol
^^^^^^^^
If the vCenter is not using the default protocol, set this value to an
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

On the machine that will run the proxy, make sure there is an ``/etc/salt/proxy``
file with at least the following in it:

.. code-block:: yaml

    master: <ip or hostname of salt-master>

You can then start the salt-proxy process with:

.. code-block:: bash

    salt-proxy --proxyid <id of the cluster>

You may want to add ``-l debug`` to run the above in the foreground in
debug mode just to make sure everything is OK.

Next, accept the key for the proxy on your salt-master, just like you
would for a regular minion:

.. code-block:: bash

    salt-key -a <id you gave the vcenter host>

You can confirm that the pillar data is in place for the proxy:

.. code-block:: bash

    salt <id> pillar.items

And now you should be able to ping the ESXi host to make sure it is
responding:

.. code-block:: bash

    salt <id> test.ping

At this point you can execute one-off commands against the vcenter. For
example, you can get if the proxy can actually connect to the vCenter:

.. code-block:: bash

    salt <id> vsphere.test_vcenter_connection

Note that you don't need to provide credentials or an ip/hostname. Salt
knows to use the credentials you stored in Pillar.

It's important to understand how this particular proxy works.
:mod:`Salt.modules.vsphere </ref/modules/all/salt.modules.vsphere>` is a
standard Salt execution module.

 If you pull up the docs for it you'll see
that almost every function in the module takes credentials and a targets either
a vcenter or a host. When credentials and a host aren't passed, Salt runs commands
through ``pyVmomi`` against the local machine. If you wanted, you could run
functions from this module on any host where an appropriate version of
``pyVmomi`` is installed, and that host would reach out over the network
and communicate with the ESXi host.
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os

# Import Salt Libs
import salt.exceptions
from salt.config.schemas.vcenter import VCenterProxySchema
from salt.utils.dictupdate import merge

# This must be present or the Salt loader won't load this module.
__proxyenabled__ = ["vcenter"]

# External libraries
try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
DETAILS = {}


# Set up logging
log = logging.getLogger(__name__)
# Define the module's virtual name
__virtualname__ = "vcenter"


def __virtual__():
    """
    Only load if the vsphere execution module is available.
    """
    if HAS_JSONSCHEMA:
        return __virtualname__

    return False, "The vcenter proxy module did not load."


def init(opts):
    """
    This function gets called when the proxy starts up.
    For login the protocol and port are cached.
    """
    log.info("Initting vcenter proxy module in process %s", os.getpid())
    log.trace("VCenter Proxy Validating vcenter proxy input")
    schema = VCenterProxySchema.serialize()
    log.trace("schema = %s", schema)
    proxy_conf = merge(opts.get("proxy", {}), __pillar__.get("proxy", {}))
    log.trace("proxy_conf = %s", proxy_conf)
    try:
        jsonschema.validate(proxy_conf, schema)
    except jsonschema.exceptions.ValidationError as exc:
        raise salt.exceptions.InvalidConfigError(exc)

    # Save mandatory fields in cache
    for key in ("vcenter", "mechanism"):
        DETAILS[key] = proxy_conf[key]

    # Additional validation
    if DETAILS["mechanism"] == "userpass":
        if "username" not in proxy_conf:
            raise salt.exceptions.InvalidConfigError(
                "Mechanism is set to 'userpass' , but no "
                "'username' key found in proxy config"
            )
        if "passwords" not in proxy_conf:
            raise salt.exceptions.InvalidConfigError(
                "Mechanism is set to 'userpass' , but no "
                "'passwords' key found in proxy config"
            )
        for key in ("username", "passwords"):
            DETAILS[key] = proxy_conf[key]
    else:
        if "domain" not in proxy_conf:
            raise salt.exceptions.InvalidConfigError(
                "Mechanism is set to 'sspi' , but no "
                "'domain' key found in proxy config"
            )
        if "principal" not in proxy_conf:
            raise salt.exceptions.InvalidConfigError(
                "Mechanism is set to 'sspi' , but no "
                "'principal' key found in proxy config"
            )
        for key in ("domain", "principal"):
            DETAILS[key] = proxy_conf[key]

    # Save optional
    DETAILS["protocol"] = proxy_conf.get("protocol")
    DETAILS["port"] = proxy_conf.get("port")

    # Test connection
    if DETAILS["mechanism"] == "userpass":
        # Get the correct login details
        log.info(
            "Retrieving credentials and testing vCenter connection for "
            "mehchanism 'userpass'"
        )
        try:
            username, password = find_credentials()
        except salt.exceptions.SaltSystemExit as err:
            log.critical("Error: %s", err)
            return False
        else:
            DETAILS["password"] = password
    return True


def ping():
    """
    Returns True.

    CLI Example:

    .. code-block:: bash

        salt vcenter test.ping
    """
    return True


def shutdown():
    """
    Shutdown the connection to the proxy device. For this proxy,
    shutdown is a no-op.
    """
    log.debug("VCenter proxy shutdown() called...")


def find_credentials():
    """
    Cycle through all the possible credentials and return the first one that
    works.
    """

    # if the username and password were already found don't fo though the
    # connection process again
    if "username" in DETAILS and "password" in DETAILS:
        return DETAILS["username"], DETAILS["password"]

    passwords = __pillar__["proxy"]["passwords"]
    for password in passwords:
        DETAILS["password"] = password
        if not __salt__["vsphere.test_vcenter_connection"]():
            # We are unable to authenticate
            continue
        # If we have data returned from above, we've successfully authenticated.
        return DETAILS["username"], password
    # We've reached the end of the list without successfully authenticating.
    raise salt.exceptions.VMwareConnectionError(
        "Cannot complete login due to " "incorrect credentials."
    )


def get_details():
    """
    Function that returns the cached details
    """
    return DETAILS
