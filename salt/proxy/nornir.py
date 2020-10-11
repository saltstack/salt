"""
Nornir Proxy module
===================

.. versionadded:: v3000

:codeauthor: Denis Mulyalin <d.mulyalin@gmail.com>
:maturity:   new
:depends:    Nornir
:platform:   unix

Dependencies
------------

Nornir `2.5.0 <https://github.com/nornir-automation/nornir/releases/tag/v2.5.0>`_

This proxy module uses `Nornir <https://nornir.readthedocs.io/en/latest/index.html>`_
library to interact with devices over SSH, Telnet or NETCONF. Nornir module need
to be installed on proxy-minion machine - ``pip install nornir==2.5.0``, Nornir
3.0.0 not supported yet.

Introduction
------------

Single Nornir proxy-minion can work with hundreds of devices as opposed to
conventional proxy-minion that normally dedicated to managing one device/system
only.

As a result, Nornir proxy-minion requires less resources to run tasks, during
idle state only one process is active, that significantly reduces the amount
of memory required on the system.

Proxy-module recommended way of operating is :conf_minion:`multiprocessing <multiprocessing>`
set to ``True``, so that each task executed in dedicated process. That would
imply these consequences:

- multiple tasks can run in parallel handled by different processes
- each process initiates dedicated connections to devices, increasing overall execution time
- multiprocessing mode allows to eliminate problems with memory leaks

.. seealso::

    - :mod:`Nornir execution module <salt.modules.nornir_mod>`

Pillar
------

Proxy parameters:

- ``proxytype`` nornir
- ``proxy_always_alive`` is ignored
- ``multiprocessing`` set to ``True`` is a recommended way to run this proxy
- ``num_workers`` maximum number of workers threads to use within Nornir
- ``process_count_max`` maximum number of processes to use to limit
  a number of simultaneous tasks and maximum number of active connections
  to devices
- ``nornir_filter_required`` boolean, to indicate if Nornir filter is mandatory
  for tasks executed by this proxy-minion. Nornir has access to multiple devices,
  by default, if no filter provided, task will run for all devices. ``nornir_filter_required``
  allows to change behavior to opposite, if no filter provided, no devices matched,
  task will not run. It is a safety measure against running task accidentally for
  many devices. ``FB="*"`` filter can be used to run task on all devices.

Nornir uses `inventory <https://nornir.readthedocs.io/en/latest/tutorials/intro/inventory.html>`_
to store information about devices to interact with. Inventory can contain
information about ``hosts``, ``groups`` and ``defaults``. Conveniently, Nornir
inventory is nothing more than a nested, Python dictionary, as a result it is
easy to define it in proxy-minion pillar.

Nornir proxy-minion pillar example:

.. code-block:: yaml

    proxy:
      proxytype: nornir
      num_workers: 100
      process_count_max: 3
      multiprocessing: True
      nornir_filter_required: True

    hosts:
      IOL1:
        hostname: 192.168.217.10
        platform: ios
        location: B1
        groups: [lab]
      IOL2:
        hostname: 192.168.217.7
        platform: ios
        location: B2
        groups: [lab]
      IOL3:
        hostname: 192.168.217.11
        platform: ios
        location: B3
        groups: [lab]
      LAB-R1:
        hostname: 192.168.1.10
        platform: ios
        password: user
        username: user
        data:
          jumphost:
            hostname: 172.16.0.10
            port: 22
            password: admin
            username: admin

    groups:
      lab:
        username: nornir
        password: nornir
        connection_options:
          napalm:
            optional_args: {dest_file_system: "system:"}

    defaults: {}

test.ping function
------------------

On :py:func:`test.ping <salt.modules.test.ping>` call Nornir proxy establishes
TCP connections to devices on configured ports to check if they are reachable
and responding, effectively doing TCP ping.
"""

# Import python std lib
import logging
from fnmatch import fnmatchcase

# Import third party libs
try:
    from nornir import InitNornir
    from nornir.core.deserializer.inventory import Inventory
    from nornir.core.filter import F
    from nornir.plugins.tasks.networking import tcp_ping

    HAS_NORNIR = True
except ImportError:
    HAS_NORNIR = False
# -----------------------------------------------------------------------------
# proxy properties
# -----------------------------------------------------------------------------

__proxyenabled__ = ["nornir"]

# -----------------------------------------------------------------------------
# globals
# -----------------------------------------------------------------------------

__virtualname__ = "nornir"
log = logging.getLogger(__name__)
nornir_data = {"initialized": False}

# -----------------------------------------------------------------------------
# propery functions
# -----------------------------------------------------------------------------


def __virtual__():
    """
    Proxy module available only if Nornir is installed.
    """
    if not HAS_NORNIR:
        return (
            False,
            "Nornir proxy module requires https://pypi.org/project/nornir/ library",
        )
    return __virtualname__


# -----------------------------------------------------------------------------
# proxy functions
# -----------------------------------------------------------------------------


def init(opts):
    """
    Initiate nornir by calling InitNornir()
    """
    opts["multiprocessing"] = opts["proxy"].get("multiprocessing", True)
    nornir_data["nr"] = InitNornir(
        core={"num_workers": opts["proxy"].get("num_workers", 100)},
        logging={"enabled": False},
        inventory={
            "options": {
                "hosts": opts["pillar"]["hosts"],
                "groups": opts["pillar"].get("groups", {}),
                "defaults": opts["pillar"].get("defaults", {}),
            }
        },
    )
    nornir_data["nornir_filter_required"] = opts["proxy"].get(
        "nornir_filter_required", False
    )
    nornir_data["initialized"] = True
    return True


def alive(opts):
    """
    Return Nornir status
    """
    return nornir_data["initialized"]


def ping():
    """
    Check that hosts are reachable on ports given in inventory
    """
    output = nornir_data["nr"].run(task=_tcp_ping)
    return {
        h: i.result
        for h, res in output.items()
        for i in res
        if not i.name.startswith("_")
    }


def initialized():
    """
    Nornir module finished initializing?
    """
    return nornir_data["initialized"]


def shutdown():
    """
    Closes connections to devices and deletes Nornir object.
    """
    nornir_data["nr"].close_connections(on_good=True, on_failed=True)
    del nornir_data["nr"]
    nornir_data["initialized"] = False
    return True


def grains():
    """
    Does nothing, returns empty dictionary
    """
    return {}


def grains_refresh():
    """
    Does nothing, returns empty dictionary
    """
    return grains()


# -----------------------------------------------------------------------------
# proxy module private functions
# -----------------------------------------------------------------------------


def _tcp_ping(task):
    """
    Helper function to run TCP ping to hosts
    """
    port = task.host.port or 22
    task.run(task=tcp_ping, name="TCP ping", ports=[port])


def _filter_FO(ret, filter_data):
    """
    Function to filter hosts using Filter Object
    """
    if isinstance(filter_data, dict):
        ret = ret.filter(F(**filter_data))
    elif isinstance(filter_data, list):
        ret = ret.filter(F(**filter_data[0]))
        for item in filter_data[1:]:
            filtered_hosts = nornir_data["nr"].filter(F(**item))
            ret.inventory.hosts.update(filtered_hosts.inventory.hosts)
    return ret


def _filter_FB(ret, pattern):
    """
    Function to filter hosts by name using glob patterns
    """
    return ret.filter(filter_func=lambda h: fnmatchcase(h.name, pattern))


def _filter_FG(ret, group):
    """
    Function to filter hosts using Groups
    """
    return ret.filter(filter_func=lambda h: h.has_parent_group(group))


def _filter_FP(ret, pfx):
    """
    Function to filter hosts based on IP Prefixes
    """
    import ipaddress
    import socket

    socket.setdefaulttimeout(1)

    def _filter_net(host):
        # convert host ip to ip address object
        try:
            ip_addr = ipaddress.ip_address(host.hostname)
        except ValueError:
            # try to resolve hostname using DNS
            try:
                ip_str = socket.gethostbyname(host.hostname)
                ip_addr = ipaddress.ip_address(ip_str)
            except Exception as e:
                log.error(
                    "FP failed to convert host IP '{}', error '{}'".format(
                        host.name, e
                    )
                )
                return False
        # run filtering
        for net in networks:
            if ip_addr in net:
                return True
        return False

    # make a list of network objects
    prefixes = (
        [i.strip() for i in pfx.split(",")] if isinstance(pfx, str) else pfx
    )
    networks = []
    for prefix in prefixes:
        try:
            networks.append(ipaddress.ip_network(prefix))
        except Exception as e:
            log.error(
                "FP failed to convert prefix '{}', error '{}'".format(
                    prefix, e
                )
            )
    # filter hosts
    return ret.filter(filter_func=_filter_net)


def _filter_FL(ret, names_list):
    """
    Function to filter hosts names based on list of names
    """
    names_list = (
        [i.strip() for i in names_list.split(",")]
        if isinstance(names_list, str)
        else names_list
    )
    return ret.filter(filter_func=lambda h: h.name in names_list)


def _filters_dispatcher(kwargs):
    """
    Inventory filters dispatcher function
    """
    ret = nornir_data["nr"]
    nornir_data["has_filter"] = False
    if kwargs.get("FO"):
        ret = _filter_FO(ret, kwargs.pop("FO"))
        nornir_data["has_filter"] = True
    if kwargs.get("FB"):
        ret = _filter_FB(ret, kwargs.pop("FB"))
        nornir_data["has_filter"] = True
    if kwargs.get("FG"):
        ret = _filter_FG(ret, kwargs.pop("FG"))
        nornir_data["has_filter"] = True
    if kwargs.get("FP"):
        ret = _filter_FP(ret, kwargs.pop("FP"))
        nornir_data["has_filter"] = True
    if kwargs.get("FL"):
        ret = _filter_FL(ret, kwargs.pop("FL"))
        nornir_data["has_filter"] = True
    return ret


def _refresh(**kwargs):
    """
    Method to reinitiate nornir with latest pillar data
    """
    opts = {"pillar": __salt__["pillar.items"](), "proxy": __opts__["proxy"]}
    init(opts)
    log.debug("Reinitiated Nornir with latest pillar data")


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def inventory_data(**kwargs):
    """
    Return Nornir inventory as a dictionary

    :param Fx: filters to filter hosts
    """
    # re-init Nornir
    _refresh()
    # filter hosts to return inventory for
    hosts = _filters_dispatcher(kwargs=kwargs)
    return Inventory.serialize(hosts.inventory).dict()


def run(task, *args, **kwargs):
    """
    Function to run Nornir tasks

    :param task: callable task function
    :param Fx: filters to filter hosts
    :param kwargs: arguments to pass to `Nornir run <https://nornir.readthedocs.io/en/latest/ref/api/nornir.html#nornir.core.Nornir.run>`_ method
    """
    # re-init Nornir
    _refresh()
    # set dry_run argument
    nornir_data["nr"].data.dry_run = kwargs.get("dry_run", False)
    # Filter hosts to run tasks for. Do not unpack kwargs, e.g. **kwargs, as need
    # to pop filter keys from it. This is required to unpack kwargs to run method
    # without causing task function to choke on unsupported argument
    hosts = _filters_dispatcher(kwargs=kwargs)
    # check if nornir_filter_required is True but no filter
    if (
        nornir_data["nornir_filter_required"] == True and
        nornir_data.get("has_filter") == False
    ):
        log.warning("nornir_filter_required is True but no filter provided")
        return {}
    # run tasks
    ret = hosts.run(
        task,
        *[i for i in args if not i.startswith("_")],
        **{k: v for k, v in kwargs.items() if not k.startswith("_")}
    )
    return ret
