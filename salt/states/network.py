"""
Configuration of network interfaces
===================================

The network module is used to create and manage network settings,
interfaces can be set as either managed or ignored. By default
all interfaces are ignored unless specified.

.. note::

    RedHat-based systems (RHEL, CentOS, Scientific, etc.)
    have been supported since version 2014.1.0.

    Debian-based systems (Debian, Ubuntu, etc.) have been
    supported since version 2017.7.0. The following options
    are not supported: ipaddr_start, and ipaddr_end.

    Other platforms are not yet supported.

.. note::

    On Debian-based systems, networking configuration can be specified
    in `/etc/network/interfaces` or via included files such as (by default)
    `/etc/network/interfaces.d/*`. This can be problematic for configuration
    management. It is recommended to use either `file.managed` *or*
    `network.managed`.

    If using ``network.managed``, it can be useful to ensure ``interfaces.d/``
    is empty. This can be done using the following state

    .. code-block:: yaml

        /etc/network/interfaces.d:
          file.directory:
            - clean: True

Configuring Global Network Settings
-----------------------------------

Use the :py:func:`network.system <salt.states.network.system>` state to set
global network settings:

.. code-block:: yaml

    system:
      network.system:
        - enabled: True
        - hostname: server1.example.com
        - gateway: 192.168.0.1
        - gatewaydev: eth0
        - nozeroconf: True
        - nisdomain: example.com
        - require_reboot: True
        - apply_hostname: True

.. note::
    The use of ``apply_hostname`` above will apply changes to the hostname
    immediately.

.. versionchanged:: 2015.5.0
    ``apply_hostname`` added

retain_settings
***************

.. versionadded:: 2016.11.0

Use `retain_settings` to retain current network settings that are not otherwise
specified in the state. Particularly useful if only setting the hostname.
Default behavior is to delete unspecified network settings.

.. code-block:: yaml

    system:
      network.system:
        - hostname: server2.example.com
        - apply_hostname: True
        - retain_settings: True

Configuring Network Routes
--------------------------

Use the :py:func:`network.routes <salt.states.network.routes>` state to set
network routes.

.. code-block:: yaml

    routes:
      network.routes:
        - name: eth0
        - routes:
          - name: secure_network
            ipaddr: 10.2.0.0
            netmask: 255.255.255.0
            gateway: 10.1.0.3
          - name: HQ_network
            ipaddr: 10.100.0.0
            netmask: 255.255.0.0
            gateway: 10.1.0.10

Managing Network Interfaces
---------------------------

The :py:func:`network.managed <salt.states.network.managed>` state is used to
configure network interfaces. Here are several examples:

Ethernet Interface
******************

.. code-block:: yaml

    eth0:
      network.managed:
        - enabled: True
        - type: eth
        - proto: static
        - ipaddr: 10.1.0.7
        - netmask: 255.255.255.0
        - gateway: 10.1.0.1
        - enable_ipv6: true
        - ipv6proto: static
        - ipv6addrs:
          - 2001:db8:dead:beef::3/64
          - 2001:db8:dead:beef::7/64
        - ipv6gateway: 2001:db8:dead:beef::1
        - ipv6netmask: 64
        - dns:
          - 8.8.8.8
          - 8.8.4.4
        - channels:
            rx: 4
            tx: 4
            other: 4
            combined: 4

Ranged Interfaces (RHEL/CentOS Only)
************************************

.. versionadded:: 2015.8.0

Ranged interfaces can be created by including the word ``range`` in the
interface name.

.. important::
    The interface type must be ``eth``.

.. code-block:: yaml

    eth0-range0:
      network.managed:
        - type: eth
        - ipaddr_start: 192.168.1.1
        - ipaddr_end: 192.168.1.10
        - clonenum_start: 10
        - mtu: 9000

    bond0-range0:
      network.managed:
        - type: eth
        - ipaddr_start: 192.168.1.1
        - ipaddr_end: 192.168.1.10
        - clonenum_start: 10
        - mtu: 9000

    eth1.0-range0:
      network.managed:
        - type: eth
        - ipaddr_start: 192.168.1.1
        - ipaddr_end: 192.168.1.10
        - clonenum_start: 10
        - vlan: True
        - mtu: 9000

    bond0.1-range0:
      network.managed:
        - type: eth
        - ipaddr_start: 192.168.1.1
        - ipaddr_end: 192.168.1.10
        - clonenum_start: 10
        - vlan: True
        - mtu: 9000

Bond Interfaces
***************

To configure a bond, you must do the following:

- Configure the bond slaves with a ``type`` of ``slave``, and a ``master``
  option set to the name of the bond interface.

- Configure the bond interface with a ``type`` of ``bond``, and a ``slaves``
  option defining the bond slaves for the bond interface.

.. code-block:: yaml

    eth2:
      network.managed:
        - enabled: True
        - type: slave
        - master: bond0

    eth3:
      network.managed:
        - enabled: True
        - type: slave
        - master: bond0

    bond0:
      network.managed:
        - type: bond
        - ipaddr: 10.1.0.1
        - netmask: 255.255.255.0
        - mode: gre
        - proto: static
        - dns:
          - 8.8.8.8
          - 8.8.4.4
        - enabled: False
        - slaves: eth2 eth3
        - require:
          - network: eth2
          - network: eth3
        - miimon: 100
        - arp_interval: 250
        - downdelay: 200
        - lacp_rate: fast
        - max_bonds: 1
        - updelay: 0
        - use_carrier: on
        - hashing-algorithm: layer2
        - mtu: 9000
        - autoneg: on
        - speed: 1000
        - duplex: full
        - rx: on
        - tx: off
        - sg: on
        - tso: off
        - ufo: off
        - gso: off
        - gro: off
        - lro: off

VLANs
*****

Set ``type`` to ``vlan`` to configure a VLANs. These VLANs are configured on
the bond interface defined above.

.. code-block:: yaml

    bond0.2:
      network.managed:
        - type: vlan
        - ipaddr: 10.1.0.2
        - use:
          - network: bond0
        - require:
          - network: bond0

    bond0.3:
      network.managed:
        - type: vlan
        - ipaddr: 10.1.0.3
        - use:
          - network: bond0
        - require:
          - network: bond0

    bond0.10:
      network.managed:
        - type: vlan
        - ipaddr: 10.1.0.4
        - use:
          - network: bond0
        - require:
          - network: bond0

    bond0.12:
      network.managed:
        - type: vlan
        - ipaddr: 10.1.0.5
        - use:
          - network: bond0
        - require:
          - network: bond0

Bridge Interfaces
*****************

.. code-block:: yaml

    eth4:
      network.managed:
        - enabled: True
        - type: eth
        - proto: dhcp
        - bridge: br0

    br0:
      network.managed:
        - enabled: True
        - type: bridge
        - proto: dhcp
        - bridge: br0
        - delay: 0
        - ports: eth4
        - bypassfirewall: True
        - use:
          - network: eth4
        - require:
          - network: eth4

.. note::
    When managing bridged interfaces on a Debian/Ubuntu based system, the
    ``ports`` argument is required. RedHat-based systems will ignore the
    argument.

Network Teaming (RHEL/CentOS 7 and later)
*****************************************

.. versionadded:: 3002

- Configure the members of the team interface with a ``type`` of ``teamport``,
  and a ``team_master`` option set to the name of the bond interface.

  - ``master`` also works, but will be ignored if both ``team_master`` and
    ``master`` are present.

  - If applicable, include a ``team_port_config`` option. This should be
    formatted as a dictionary. Keep in mind that due to a quirk of PyYAML,
    dictionaries nested under a list item must be double-indented (see example
    below for interface ``eth5``).

- Configure the team interface with a ``type`` of ``team``. The team
  configuration should be passed via the ``team_config`` option. As with
  ``team_port_config``, the dictionary should be double-indented.

.. code-block:: yaml

    eth5:
      network.managed:
        - type: teamport
        - team_master: team0
        - team_port_config:
            prio: 100

    eth6:
      network.managed:
        - type: teamport
        - team_master: team0

    team0:
      network.managed:
        - type: team
        - ipaddr: 172.24.90.42
        - netmask: 255.255.255.128
        - enable_ipv6: True
        - ipv6addr: 'fee1:dead:beef:af43::'
        - team_config:
            runner:
              hwaddr_policy: by_active
              name: activebackup
              link_watch:
                name: ethtool

.. note::
    While ``teamd`` must be installed to manage a team interface, it is not
    required to configure a separate :py:func:`pkg.installed
    <salt.states.pkg.installed>` state for it, as it will be silently installed
    if needed.

Configuring the Loopback Interface
**********************************

Use :py:func:`network.managed <salt.states.network.managed>` with a ``type`` of
``eth`` and a ``proto`` of ``loopback``.

.. code-block:: yaml

    lo:
      network.managed:
        - name: lo
        - type: eth
        - proto: loopback
        - onboot: yes
        - userctl: no
        - ipv6_autoconf: no
        - enable_ipv6: true

Other Useful Options
--------------------

noifupdown
**********

The ``noifupdown`` option, if set to ``True``, will keep Salt from restart the
interface if changes are made, requiring them to be restarted manually. Here
are a couple examples:

.. code-block:: yaml

    eth7:
      network.managed:
        - enabled: True
        - type: eth
        # Automatic IP/DNS
        - proto: dhcp
        - noifupdown: True

    eth8:
      network.managed:
        - type: eth
        - noifupdown: True

        # IPv4
        - proto: static
        - ipaddr: 192.168.4.9
        - netmask: 255.255.255.0
        - gateway: 192.168.4.1
        - enable_ipv6: True

        # IPv6
        - ipv6proto: static
        - ipv6addr: 2001:db8:dead:c0::3
        - ipv6netmask: 64
        - ipv6gateway: 2001:db8:dead:c0::1
        # override shared; makes those options v4-only
        - ipv6ttl: 15

        # Shared
        - mtu: 1480
        - ttl: 18
        - dns:
          - 8.8.8.8
          - 8.8.4.4
"""

import difflib
import logging

import salt.loader
import salt.utils.network
import salt.utils.platform

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    """
    Confine this module to non-Windows systems with the required execution
    module available.
    """
    if salt.utils.platform.is_windows():
        return (False, "Only supported on non-Windows OSs")
    if "ip.get_interface" in __salt__:
        return True
    return (False, "ip module could not be loaded")


def managed(name, enabled=True, **kwargs):
    """
    Ensure that the named interface is configured properly.

    name
        The name of the interface to manage

    type : eth
        Type of interface and configuration

        .. versionchanged:: 3002

    enabled
        Designates the state of this interface.
    """
    # For this function we are purposefully overwriting a bif
    # to enhance the user experience. This does not look like
    # it will cause a problem. Just giving a heads up in case
    # it does create a problem.
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "Interface {} is up to date.".format(name),
    }
    if "test" not in kwargs:
        kwargs["test"] = __opts__.get("test", False)

    # set ranged status
    apply_ranged_setting = False

    # Pull interface type out of kwargs
    iface_type = str(kwargs.pop("type", "eth"))

    if "addr" in kwargs:
        hwaddr = kwargs.pop("addr")
        msg = "'addr' is not a valid argument name, "
        if "hwaddr" not in kwargs:
            msg += "its value has been assigned to 'hwaddr' instead."
            kwargs["hwaddr"] = hwaddr
        else:
            msg += "it has been ignored in favor of 'hwaddr'."
        msg += " Update your SLS file to get rid of this warning."
        ret.setdefault("warnings", []).append(msg)

    # Build interface
    try:
        old = __salt__["ip.get_interface"](name)
        new = __salt__["ip.build_interface"](name, iface_type, enabled, **kwargs)
        if kwargs["test"]:
            if old == new:
                pass
            if not old and new:
                ret["result"] = None
                ret["comment"] = "Interface {} is set to be added.".format(name)
            elif old != new:
                diff = difflib.unified_diff(old, new, lineterm="")
                ret["result"] = None
                ret["comment"] = "Interface {} is set to be updated:\n{}".format(
                    name, "\n".join(diff)
                )
        else:
            if not old and new:
                ret["comment"] = "Interface {} added.".format(name)
                ret["changes"]["interface"] = "Added network interface."
                apply_ranged_setting = True
            elif old != new:
                diff = difflib.unified_diff(old, new, lineterm="")
                ret["comment"] = "Interface {} updated.".format(name)
                ret["changes"]["interface"] = "\n".join(diff)
                apply_ranged_setting = True
    except AttributeError as error:
        ret["result"] = False
        ret["comment"] = str(error)
        return ret

    # Debian based system can have a type of source
    # in the interfaces file, we don't ifup or ifdown it
    if iface_type == "source":
        return ret

    # Setup up bond modprobe script if required
    if iface_type == "bond" and "ip.get_bond" in __salt__:
        try:
            old = __salt__["ip.get_bond"](name)
            new = __salt__["ip.build_bond"](name, **kwargs)
            if kwargs["test"]:
                if not old and new:
                    ret["result"] = None
                    ret["comment"] = "Bond interface {} is set to be added.".format(
                        name
                    )
                elif old != new:
                    diff = difflib.unified_diff(old, new, lineterm="")
                    ret["result"] = None
                    ret[
                        "comment"
                    ] = "Bond interface {} is set to be updated:\n{}".format(
                        name, "\n".join(diff)
                    )
            else:
                if not old and new:
                    ret["comment"] = "Bond interface {} added.".format(name)
                    ret["changes"]["bond"] = "Added bond {}.".format(name)
                    apply_ranged_setting = True
                elif old != new:
                    diff = difflib.unified_diff(old, new, lineterm="")
                    ret["comment"] = "Bond interface {} updated.".format(name)
                    ret["changes"]["bond"] = "\n".join(diff)
                    apply_ranged_setting = True
        except AttributeError as error:
            # TODO Add a way of reversing the interface changes.
            ret["result"] = False
            ret["comment"] = str(error)
            return ret

    if kwargs["test"]:
        return ret

    # For Redhat/Centos ranged network
    if "range" in name:
        if apply_ranged_setting:
            try:
                ret["result"] = __salt__["service.restart"]("network")
                ret["comment"] = "network restarted for change of ranged interfaces"
                return ret
            except Exception as error:  # pylint: disable=broad-except
                ret["result"] = False
                ret["comment"] = str(error)
                return ret
        ret["result"] = True
        ret["comment"] = "no change, passing it"
        return ret

    # Bring up/shutdown interface
    try:
        # Get Interface current status
        interfaces = salt.utils.network.interfaces()
        interface_status = False
        if name in interfaces:
            interface_status = interfaces[name].get("up")
        else:
            for iface in interfaces:
                if "secondary" in interfaces[iface]:
                    for second in interfaces[iface]["secondary"]:
                        if second.get("label", "") == name:
                            interface_status = True
                if iface == "lo":
                    if "inet" in interfaces[iface]:
                        inet_data = interfaces[iface]["inet"]
                        if len(inet_data) > 1:
                            for data in inet_data:
                                if data.get("label", "") == name:
                                    interface_status = True
                    if "inet6" in interfaces[iface]:
                        inet6_data = interfaces[iface]["inet6"]
                        if len(inet6_data) > 1:
                            for data in inet6_data:
                                if data.get("label", "") == name:
                                    interface_status = True
        if enabled:
            if "noifupdown" not in kwargs:
                if interface_status:
                    if ret["changes"]:
                        # Interface should restart to validate if it's up
                        __salt__["ip.down"](name, iface_type)
                        __salt__["ip.up"](name, iface_type)
                        ret["changes"][
                            "status"
                        ] = "Interface {} restart to validate".format(name)
                else:
                    __salt__["ip.up"](name, iface_type)
                    ret["changes"]["status"] = "Interface {} is up".format(name)
        else:
            if "noifupdown" not in kwargs:
                if interface_status:
                    __salt__["ip.down"](name, iface_type)
                    ret["changes"]["status"] = "Interface {} down".format(name)
    except Exception as error:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = str(error)
        return ret

    # Try to enslave bonding interfaces after master was created
    if iface_type == "bond" and "noifupdown" not in kwargs:

        if "slaves" in kwargs and kwargs["slaves"]:
            # Check that there are new slaves for this master
            present_slaves = __salt__["cmd.run"](
                ["cat", "/sys/class/net/{}/bonding/slaves".format(name)]
            ).split()
            desired_slaves = kwargs["slaves"].split()
            missing_slaves = set(desired_slaves) - set(present_slaves)

            # Enslave only slaves missing in master
            if missing_slaves:
                ifenslave_path = __salt__["cmd.run"](["which", "ifenslave"]).strip()
                if ifenslave_path:
                    log.info(
                        "Adding slaves '%s' to the master %s",
                        " ".join(missing_slaves),
                        name,
                    )
                    cmd = [ifenslave_path, name] + list(missing_slaves)
                    __salt__["cmd.run"](cmd, python_shell=False)
                else:
                    log.error("Command 'ifenslave' not found")
                ret["changes"]["enslave"] = "Added slaves '{}' to master '{}'".format(
                    " ".join(missing_slaves), name
                )
            else:
                log.info(
                    "All slaves '%s' are already added to the master %s"
                    ", no actions required",
                    " ".join(missing_slaves),
                    name,
                )

    if enabled and interface_status:
        # Interface was restarted, return
        return ret

    # Make sure that the network grains reflect any changes made here
    __salt__["saltutil.refresh_grains"]()
    return ret


def routes(name, **kwargs):
    """
    Manage network interface static routes.

    name
        Interface name to apply the route to.

    kwargs
        Named routes
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "Interface {} routes are up to date.".format(name),
    }
    apply_routes = False
    if "test" not in kwargs:
        kwargs["test"] = __opts__.get("test", False)

    # Build interface routes
    try:
        old = __salt__["ip.get_routes"](name)
        new = __salt__["ip.build_routes"](name, **kwargs)
        if kwargs["test"]:
            if old == new:
                return ret
            if not old and new:
                ret["result"] = None
                ret["comment"] = "Interface {} routes are set to be added.".format(name)
                return ret
            elif old != new:
                diff = difflib.unified_diff(old, new, lineterm="")
                ret["result"] = None
                ret[
                    "comment"
                ] = "Interface {} routes are set to be updated:\n{}".format(
                    name, "\n".join(diff)
                )
                return ret
        if not old and new:
            apply_routes = True
            ret["comment"] = "Interface {} routes added.".format(name)
            ret["changes"]["network_routes"] = "Added interface {} routes.".format(name)
        elif old != new:
            diff = difflib.unified_diff(old, new, lineterm="")
            apply_routes = True
            ret["comment"] = "Interface {} routes updated.".format(name)
            ret["changes"]["network_routes"] = "\n".join(diff)
    except AttributeError as error:
        ret["result"] = False
        ret["comment"] = str(error)
        return ret

    # Apply interface routes
    if apply_routes:
        try:
            __salt__["ip.apply_network_settings"](**kwargs)
        except AttributeError as error:
            ret["result"] = False
            ret["comment"] = str(error)
            return ret

    return ret


def system(name, **kwargs):
    """
    Ensure that global network settings are configured properly.

    name
        Custom name to represent this configuration change.

    kwargs
        The global parameters for the system.

    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "Global network settings are up to date.",
    }
    apply_net_settings = False
    kwargs["test"] = __opts__["test"]
    # Build global network settings
    try:
        old = __salt__["ip.get_network_settings"]()
        new = __salt__["ip.build_network_settings"](**kwargs)
        if __opts__["test"]:
            if old == new:
                return ret
            if not old and new:
                ret["result"] = None
                ret["comment"] = "Global network settings are set to be added."
                return ret
            elif old != new:
                diff = difflib.unified_diff(old, new, lineterm="")
                ret["result"] = None
                ret[
                    "comment"
                ] = "Global network settings are set to be updated:\n{}".format(
                    "\n".join(diff)
                )
                return ret
        if not old and new:
            apply_net_settings = True
            ret["changes"]["network_settings"] = "Added global network settings."
        elif old != new:
            diff = difflib.unified_diff(old, new, lineterm="")
            apply_net_settings = True
            ret["changes"]["network_settings"] = "\n".join(diff)
    except AttributeError as error:
        ret["result"] = False
        ret["comment"] = str(error)
        return ret
    except KeyError as error:
        ret["result"] = False
        ret["comment"] = str(error)
        return ret

    # Apply global network settings
    if apply_net_settings:
        try:
            __salt__["ip.apply_network_settings"](**kwargs)
        except AttributeError as error:
            ret["result"] = False
            ret["comment"] = str(error)
            return ret

    return ret
