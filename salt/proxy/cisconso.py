# -*- coding: utf-8 -*-
'''
Proxy Minion interface module for managing (practically) any network device with
Cisco Network Services Orchestrator (Cisco NSO). Cisco NSO uses a series of
remote polling
agents, APIs and SSH commands to fetch network configuration and represent
it in a data model.
PyNSO, the Python module used by this proxy minion does the task of converting
native Python dictionaries
into NETCONF/YANG syntax that the REST API for Cisco NSO can then use to set
the configuration of the target
network device.

Supported devices:
  -  A10 AX Series
  -  Arista 7150 Series
  -  Ciena 3000, 5000, ESM
  -  H3c S5800 Series
  -  Overture 1400, 2200, 5000, 5100, 6000
  -  Accedian MetroNID
  -  Avaya ERS 4000, SR8000, VSP 9000
  -  Cisco: APIC-DC, ASA, IOS, IOS XE, IOS XR, er, ME-4600, NX OS,
        Prime Network Registrar, Quantum, StarOS, UCS ManagWSA
  -  Huawei: NE40E, quidway series, Enterprise Network Simulation Framework
  -  PaloAlto PA-2000, PA-3000, Virtualized Firewalls
  - Adtran 900 Series
  -  Brocade ADX, MLX, Netiron, Vyatta
  -  Dell Force 10 Networking S-Series
  -  Infinera DTN-X Multi-Terabit Packet Optical Network Platform
  -  Pulsecom SuperG
  -  Adva 150CC Series
  -  CableLabs Converged Cable Access Platform
  -  Ericsson EFN324 Series, SE family
  -  Juniper: Contrail, EX, M, MX, QFX, SRX, Virtual SRX
  -  Quagga Routing Software
  - Affirmed Networks
  -  Citrix Netscaler
  -  F5 BIG-IP
  -  NEC iPasolink
  -  Riverbed Steelhead Series
  -  Alcatel-Lucent 7XXX, SAM
  -  Clavister
  -  Fortinet
  -  Nominum DCS
  -  Sonus SBC 5000 Series
  -  Allied Telesys
  -  Open vSwitch

.. versionadded:: 2016.11.0

:codeauthor: `Anthony Shaw <anthony.shaw@dimensiondata.com>`

This proxy minion enables a consistent interface to fetch, control and maintain
the configuration of network devices via a NETCONF-compliant control plane.
Cisco Network Services Orchestrator.

More in-depth conceptual reading on Proxy Minions can be found in the
:ref:`Proxy Minion <proxy-minion>` section of Salt's
documentation.


Dependencies
============

- pynso Python module


PyNSO
-------

PyNSO can be installed via pip:

.. code-block:: bash

    pip install pynso

Configuration
=============
To use this integration proxy module, please configure the following:

Pillar
------

Proxy minions get their configuration from Salt's Pillar. Every proxy must
have a stanza in Pillar and a reference in the Pillar top-file that matches
the ID. At a minimum for communication with the NSO host, the pillar should
look like this:

.. code-block:: yaml

    proxy:
      proxytype: cisconso
      host: <ip or dns name of host>
      port: 8080
      use_ssl: false
      username: <username>
      password: password

proxytype
^^^^^^^^^
The ``proxytype`` key and value pair is critical, as it tells Salt which
interface to load from the ``proxy`` directory in Salt's install hierarchy,
or from ``/srv/salt/_proxy`` on the Salt Master (if you have created your
own proxy module, for example). To use this Cisco NSO Proxy Module, set this to
``cisconso``.

host
^^^^
The location, or IP/dns, of the Cisco NSO API host. Required.

username
^^^^^^^^
The username used to login to the Cisco NSO host, such as ``admin``. Required.

passwords
^^^^^^^^^
The password for the given user. Required.

use_ssl
^^^^^^^^
Whether to use HTTPS messaging to speak to the API.

port
^^^^
The port that the Cisco NSO API is running on, 8080 by default


Salt Proxy
----------

After your pillar is in place, you can test the proxy. The proxy can run on
any machine that has network connectivity to your Salt Master and to the
Cisco NSO host in question. SaltStack recommends that the machine running the
salt-proxy process also run a regular minion, though it is not strictly
necessary.

On the machine that will run the proxy, make sure
there is an ``/etc/salt/proxy``
file with at least the following in it:

.. code-block:: yaml

    master: <ip or hostname of salt-master>

You can then start the salt-proxy process with:

.. code-block:: bash

    salt-proxy --proxyid <id you want to give the host>

You may want to add ``-l debug`` to run the above in the foreground in
debug mode just to make sure everything is OK.

Next, accept the key for the proxy on your salt-master, just like you
would for a regular minion:

.. code-block:: bash

    salt-key -a <id you gave the cisconso host>

You can confirm that the pillar data is in place for the proxy:

.. code-block:: bash

    salt <id> pillar.items

And now you should be able to ping the Cisco NSO host to make sure it is
responding:

.. code-block:: bash

    salt <id> test.ping
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
from salt.exceptions import SaltSystemExit

# This must be present or the Salt loader won't load this module.
__proxyenabled__ = ['cisconso']

try:
    from pynso.client import NSOClient
    from pynso.datastores import DatastoreType
    HAS_PYNSO_LIBS = True
except ImportError:
    HAS_PYNSO_LIBS = False

# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
GRAINS_CACHE = {}
DETAILS = {}

# Set up logging
log = logging.getLogger(__file__)

# Define the module's virtual name
__virtualname__ = 'cisconso'


def __virtual__():
    return HAS_PYNSO_LIBS


def init(opts):
    # Set configuration details
    DETAILS['host'] = opts['proxy'].get('host')
    DETAILS['username'] = opts['proxy'].get('username')
    DETAILS['password'] = opts['proxy'].get('password')
    DETAILS['use_ssl'] = bool(opts['proxy'].get('use_ssl'))
    DETAILS['port'] = int(opts['proxy'].get('port'))


def grains():
    '''
    Get the grains from the proxy device.
    '''
    if not GRAINS_CACHE:
        return _grains()
    return GRAINS_CACHE


def _get_client():
    return NSOClient(
        host=DETAILS['host'],
        username=DETAILS['username'],
        password=DETAILS['password'],
        port=DETAILS['port'],
        ssl=DETAILS['use_ssl'])


def ping():
    '''
    Check to see if the host is responding. Returns False if the host didn't
    respond, True otherwise.

    CLI Example:

    .. code-block:: bash

        salt cisco-nso test.ping
    '''
    try:
        client = _get_client()
        client.info()
    except SaltSystemExit as err:
        log.warning(err)
        return False

    return True


def shutdown():
    '''
    Shutdown the connection to the proxy device. For this proxy,
    shutdown is a no-op.
    '''
    log.debug('Cisco NSO proxy shutdown() called...')


def get_data(datastore, path):
    '''
    Get the configuration of the device tree at the given path

    :param datastore: The datastore, e.g. running, operational.
        One of the NETCONF store IETF types
    :type  datastore: :class:`DatastoreType` (``str`` enum).

    :param path: The device path, a list of element names in order,
        comma seperated
    :type  path: ``list`` of ``str`` OR ``tuple``

    :return: The network configuration at that tree
    :rtype: ``dict``

    .. code-block:: bash

        salt cisco-nso cisconso.get_data devices
    '''
    client = _get_client()
    return client.get_datastore_data(datastore, path)


def set_data_value(datastore, path, data):
    '''
    Get a data entry in a datastore

    :param datastore: The datastore, e.g. running, operational.
        One of the NETCONF store IETF types
    :type  datastore: :class:`DatastoreType` (``str`` enum).

    :param path: The device path to set the value at,
        a list of element names in order, comma seperated
    :type  path: ``list`` of ``str`` OR ``tuple``

    :param data: The new value at the given path
    :type  data: ``dict``

    :rtype: ``bool``
    :return: ``True`` if successful, otherwise error.
    '''
    client = _get_client()
    return client.set_data_value(datastore, path, data)


def get_rollbacks():
    '''
    Get a list of stored configuration rollbacks
    '''
    return _get_client().get_rollbacks()


def get_rollback(name):
    '''
    Get the backup of stored a configuration rollback

    :param name: Typically an ID of the backup
    :type  name: ``str``

    :rtype: ``str``
    :return: the contents of the rollback snapshot
    '''
    return _get_client().get_rollback(name)


def apply_rollback(datastore, name):
    '''
    Apply a system rollback

    :param datastore: The datastore, e.g. running, operational.
        One of the NETCONF store IETF types
    :type  datastore: :class:`DatastoreType` (``str`` enum).

    :param name: an ID of the rollback to restore
    :type  name: ``str``
    '''
    return _get_client().apply_rollback(datastore, name)


def _grains():
    '''
    Helper function to the grains from the proxied devices.
    '''
    client = _get_client()
    # This is a collection of the configuration of all running devices under NSO
    ret = client.get_datastore(DatastoreType.RUNNING)
    GRAINS_CACHE.update(ret)
    return GRAINS_CACHE
