"""
Arista pyeapi
=============

.. versionadded:: 2019.2.0

Proxy module for managing Arista switches via the eAPI using the
`pyeapi <http://pyeapi.readthedocs.io/en/master/index.html>`_ library.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net>
:maturity:   new
:depends:    pyeapi
:platform:   unix

.. note::

    To understand how to correctly enable the eAPI on your switch, please check
    https://eos.arista.com/arista-eapi-101/.


Dependencies
------------

The ``pyeapi`` Proxy module requires pyeapi to be installed:
``pip install pyeapi``.

Pillar
------

The ``pyeapi`` proxy configuration requires the following parameters in order
to connect to the network device:

transport: ``https``
    Specifies the type of connection transport to use. Valid values for the
    connection are ``socket``, ``http_local``, ``http``, and  ``https``.

host: ``localhost``
    The IP address or DNS host name of the connection device.

username: ``admin``
    The username to pass to the device to authenticate the eAPI connection.

password
    The password to pass to the device to authenticate the eAPI connection.

port
    The TCP port of the endpoint for the eAPI connection. If this keyword is
    not specified, the default value is automatically determined by the
    transport type (``80`` for ``http``, or ``443`` for ``https``).

enablepwd
    The enable mode password if required by the destination node.

All the arguments may be optional, depending on your setup.

Proxy Pillar Example
--------------------

.. code-block:: yaml

    proxy:
      proxytype: pyeapi
      host: router1.example.com
      username: example
      password: example
"""

import logging

# Import salt modules
from salt.utils.args import clean_kwargs

try:
    import pyeapi

    HAS_PYEAPI = True
except ImportError:
    HAS_PYEAPI = False


# -----------------------------------------------------------------------------
# proxy properties
# -----------------------------------------------------------------------------

__proxyenabled__ = ["pyeapi"]
# proxy name

# -----------------------------------------------------------------------------
# globals
# -----------------------------------------------------------------------------

__virtualname__ = "pyeapi"
log = logging.getLogger(__name__)
pyeapi_device = {}

# -----------------------------------------------------------------------------
# property functions
# -----------------------------------------------------------------------------


def __virtual__():
    """
    Proxy module available only if pyeapi is installed.
    """
    if not HAS_PYEAPI:
        return (
            False,
            "The pyeapi proxy module requires the pyeapi library to be installed.",
        )
    return __virtualname__


# -----------------------------------------------------------------------------
# proxy functions
# -----------------------------------------------------------------------------


def init(opts):
    """
    Open the connection to the Arista switch over the eAPI.
    """
    proxy_dict = opts.get("proxy", {})
    conn_args = proxy_dict.copy()
    conn_args.pop("proxytype", None)
    opts["multiprocessing"] = conn_args.get("multiprocessing", True)
    # This is not a SSH-based proxy, so it should be safe to enable
    # multiprocessing.
    try:
        conn = pyeapi.client.connect(**conn_args)
        node = pyeapi.client.Node(conn, enablepwd=conn_args.get("enablepwd"))
        pyeapi_device["connection"] = node
        pyeapi_device["initialized"] = True
        pyeapi_device["up"] = True
    except pyeapi.eapilib.ConnectionError as cerr:
        log.error("Unable to connect to %s", conn_args["host"], exc_info=True)
        return False
    return True


def ping():
    """
    Connection open successfully?
    """
    return pyeapi_device.get("up", False)


def initialized():
    """
    Connection finished initializing?
    """
    return pyeapi_device.get("initialized", False)


def shutdown(opts):
    """
    Closes connection with the device.
    """
    log.debug("Shutting down the pyeapi Proxy Minion %s", opts["id"])


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def conn():
    """
    Return the connection object.
    """
    return pyeapi_device.get("connection")


def call(method, *args, **kwargs):
    """
    Calls an arbitrary pyeapi method.
    """
    kwargs = clean_kwargs(**kwargs)
    return getattr(pyeapi_device["connection"], method)(*args, **kwargs)
