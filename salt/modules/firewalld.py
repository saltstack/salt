# -*- coding: utf-8 -*-
"""
Support for firewalld.

.. versionadded:: 2015.2.0
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

import salt.utils.path

# Import Salt Libs
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    """
    Check to see if firewall-cmd exists
    """
    if salt.utils.path.which("firewall-cmd"):
        return True

    return (
        False,
        "The firewalld execution module cannot be loaded: the firewall-cmd binary is not in the path.",
    )


def __firewall_cmd(cmd):
    """
    Return the firewall-cmd location
    """
    firewall_cmd = "{0} {1}".format(salt.utils.path.which("firewall-cmd"), cmd)
    out = __salt__["cmd.run_all"](firewall_cmd)

    if out["retcode"] != 0:
        if not out["stderr"]:
            msg = out["stdout"]
        else:
            msg = out["stderr"]
        raise CommandExecutionError("firewall-cmd failed: {0}".format(msg))
    return out["stdout"]


def __mgmt(name, _type, action):
    """
    Perform zone management
    """
    # It's permanent because the 4 concerned functions need the permanent option, it's wrong without
    cmd = "--{0}-{1}={2} --permanent".format(action, _type, name)

    return __firewall_cmd(cmd)


def version():
    """
    Return version from firewall-cmd

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.version
    """
    return __firewall_cmd("--version")


def reload_rules():
    """
    Reload the firewall rules, which makes the permanent configuration the new
    runtime configuration without losing state information.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.reload
    """
    return __firewall_cmd("--reload")


def default_zone():
    """
    Print default zone for connections and interfaces

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.default_zone
    """
    return __firewall_cmd("--get-default-zone")


def list_zones(permanent=True):
    """
    List everything added for or enabled in all zones

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.list_zones
    """
    zones = {}

    cmd = "--list-all-zones"

    if permanent:
        cmd += " --permanent"

    for i in __firewall_cmd(cmd).splitlines():
        if i.strip():
            if bool(re.match("^[a-z0-9]", i, re.I)):
                zone_name = i.rstrip()
            else:
                (id_, val) = i.strip().split(":")

                if zones.get(zone_name, None):
                    zones[zone_name].update({id_: val})
                else:
                    zones[zone_name] = {id_: val}

    return zones


def get_zones(permanent=True):
    """
    Print predefined zones

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_zones
    """
    cmd = "--get-zones"

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd).split()


def get_services(permanent=True):
    """
    Print predefined services

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_services
    """
    cmd = "--get-services"

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd).split()


def get_icmp_types(permanent=True):
    """
    Print predefined icmptypes

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_icmp_types
    """
    cmd = "--get-icmptypes"

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd).split()


def new_zone(zone, restart=True):
    """
    Add a new zone

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.new_zone my_zone

    By default firewalld will be reloaded. However, to avoid reloading
    you need to specify the restart as False

    .. code-block:: bash

        salt '*' firewalld.new_zone my_zone False
    """
    out = __mgmt(zone, "zone", "new")

    if restart:

        if out == "success":
            return __firewall_cmd("--reload")

    return out


def delete_zone(zone, restart=True):
    """
    Delete an existing zone

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.delete_zone my_zone

    By default firewalld will be reloaded. However, to avoid reloading
    you need to specify the restart as False

    .. code-block:: bash

        salt '*' firewalld.delete_zone my_zone False
    """
    out = __mgmt(zone, "zone", "delete")

    if restart:

        if out == "success":
            return __firewall_cmd("--reload")

    return out


def set_default_zone(zone):
    """
    Set default zone

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.set_default_zone damian
    """
    return __firewall_cmd("--set-default-zone={0}".format(zone))


def new_service(name, restart=True):
    """
    Add a new service

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.new_service my_service

    By default firewalld will be reloaded. However, to avoid reloading
    you need to specify the restart as False

    .. code-block:: bash

        salt '*' firewalld.new_service my_service False
    """
    out = __mgmt(name, "service", "new")

    if restart:

        if out == "success":
            return __firewall_cmd("--reload")

    return out


def delete_service(name, restart=True):
    """
    Delete an existing service

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.delete_service my_service

    By default firewalld will be reloaded. However, to avoid reloading
    you need to specify the restart as False

    .. code-block:: bash

        salt '*' firewalld.delete_service my_service False
    """
    out = __mgmt(name, "service", "delete")

    if restart:

        if out == "success":
            return __firewall_cmd("--reload")

    return out


def list_all(zone=None, permanent=True):
    """
    List everything added for or enabled in a zone

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.list_all

    List a specific zone

    .. code-block:: bash

        salt '*' firewalld.list_all my_zone
    """
    _zone = {}
    id_ = ""

    if zone:
        cmd = "--zone={0} --list-all".format(zone)
    else:
        cmd = "--list-all"

    if permanent:
        cmd += " --permanent"

    for i in __firewall_cmd(cmd).splitlines():
        if re.match("^[a-z0-9]", i, re.I):
            zone_name = i.rstrip()
        else:
            if i.startswith("\t"):
                _zone[zone_name][id_].append(i.strip())
                continue

            (id_, val) = i.split(":", 1)

            id_ = id_.strip()

            if _zone.get(zone_name, None):
                _zone[zone_name].update({id_: [val.strip()]})
            else:
                _zone[zone_name] = {id_: [val.strip()]}

    return _zone


def list_services(zone=None, permanent=True):
    """
    List services added for zone as a space separated list.
    If zone is omitted, default zone will be used.

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.list_services

    List a specific zone

    .. code-block:: bash

        salt '*' firewalld.list_services my_zone
    """
    if zone:
        cmd = "--zone={0} --list-services".format(zone)
    else:
        cmd = "--list-services"

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd).split()


def add_service(service, zone=None, permanent=True):
    """
    Add a service for zone. If zone is omitted, default zone will be used.

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_service ssh

    To assign a service to a specific zone:

    .. code-block:: bash

        salt '*' firewalld.add_service ssh my_zone
    """
    if zone:
        cmd = "--zone={0} --add-service={1}".format(zone, service)
    else:
        cmd = "--add-service={0}".format(service)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def remove_service(service, zone=None, permanent=True):
    """
    Remove a service from zone. This option can be specified multiple times.
    If zone is omitted, default zone will be used.

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_service ssh

    To remove a service from a specific zone

    .. code-block:: bash

        salt '*' firewalld.remove_service ssh dmz
    """
    if zone:
        cmd = "--zone={0} --remove-service={1}".format(zone, service)
    else:
        cmd = "--remove-service={0}".format(service)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def add_service_port(service, port):
    """
    Add a new port to the specified service.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_service_port zone 80
    """
    if service not in get_services(permanent=True):
        raise CommandExecutionError("The service does not exist.")

    cmd = "--permanent --service={0} --add-port={1}".format(service, port)
    return __firewall_cmd(cmd)


def remove_service_port(service, port):
    """
    Remove a port from the specified service.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_service_port zone 80
    """
    if service not in get_services(permanent=True):
        raise CommandExecutionError("The service does not exist.")

    cmd = "--permanent --service={0} --remove-port={1}".format(service, port)
    return __firewall_cmd(cmd)


def get_service_ports(service):
    """
    List ports of a service.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_service_ports zone
    """
    cmd = "--permanent --service={0} --get-ports".format(service)
    return __firewall_cmd(cmd).split()


def add_service_protocol(service, protocol):
    """
    Add a new protocol to the specified service.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_service_protocol zone ssh
    """
    cmd = "--permanent --service={0} --add-protocol={1}".format(service, protocol)
    return __firewall_cmd(cmd)


def remove_service_protocol(service, protocol):
    """
    Remove a protocol from the specified service.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_service_protocol zone ssh
    """
    cmd = "--permanent --service={0} --remove-protocol={1}".format(service, protocol)
    return __firewall_cmd(cmd)


def get_service_protocols(service):
    """
    List protocols of a service.

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_service_protocols zone
    """
    cmd = "--permanent --service={0} --get-protocols".format(service)
    return __firewall_cmd(cmd).split()


def get_masquerade(zone=None, permanent=True):
    """
    Show if masquerading is enabled on a zone.
    If zone is omitted, default zone will be used.

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_masquerade zone
    """
    zone_info = list_all(zone, permanent)

    if "no" in [zone_info[i]["masquerade"][0] for i in zone_info]:
        return False

    return True


def add_masquerade(zone=None, permanent=True):
    """
    Enable masquerade on a zone.
    If zone is omitted, default zone will be used.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_masquerade

    To enable masquerade on a specific zone

    .. code-block:: bash

        salt '*' firewalld.add_masquerade dmz
    """
    if zone:
        cmd = "--zone={0} --add-masquerade".format(zone)
    else:
        cmd = "--add-masquerade"

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def remove_masquerade(zone=None, permanent=True):
    """
    Remove masquerade on a zone.
    If zone is omitted, default zone will be used.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_masquerade

    To remove masquerade on a specific zone

    .. code-block:: bash

        salt '*' firewalld.remove_masquerade dmz
    """
    if zone:
        cmd = "--zone={0} --remove-masquerade".format(zone)
    else:
        cmd = "--remove-masquerade"

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def add_port(zone, port, permanent=True, force_masquerade=False):
    """
    Allow specific ports in a zone.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_port internal 443/tcp

    force_masquerade
        when a zone is created ensure masquerade is also enabled
        on that zone.
    """
    if force_masquerade and not get_masquerade(zone):
        add_masquerade(zone)

    cmd = "--zone={0} --add-port={1}".format(zone, port)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def remove_port(zone, port, permanent=True):
    """
    Remove a specific port from a zone.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_port internal 443/tcp
    """
    cmd = "--zone={0} --remove-port={1}".format(zone, port)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def list_ports(zone, permanent=True):
    """
    List all ports in a zone.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.list_ports
    """
    cmd = "--zone={0} --list-ports".format(zone)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd).split()


def add_port_fwd(
    zone, src, dest, proto="tcp", dstaddr="", permanent=True, force_masquerade=False
):
    """
    Add port forwarding.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_port_fwd public 80 443 tcp

    force_masquerade
        when a zone is created ensure masquerade is also enabled
        on that zone.
    """
    if force_masquerade and not get_masquerade(zone):
        add_masquerade(zone)

    cmd = "--zone={0} --add-forward-port=port={1}:proto={2}:toport={3}:toaddr={4}".format(
        zone, src, proto, dest, dstaddr
    )

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def remove_port_fwd(zone, src, dest, proto="tcp", dstaddr="", permanent=True):
    """
    Remove Port Forwarding.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_port_fwd public 80 443 tcp
    """
    cmd = "--zone={0} --remove-forward-port=port={1}:proto={2}:toport={3}:toaddr={4}".format(
        zone, src, proto, dest, dstaddr
    )

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def list_port_fwd(zone, permanent=True):
    """
    List port forwarding

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.list_port_fwd public
    """
    ret = []

    cmd = "--zone={0} --list-forward-ports".format(zone)

    if permanent:
        cmd += " --permanent"

    for i in __firewall_cmd(cmd).splitlines():
        (src, proto, dest, addr) = i.split(":")

        ret.append(
            {
                "Source port": src.split("=")[1],
                "Protocol": proto.split("=")[1],
                "Destination port": dest.split("=")[1],
                "Destination address": addr.split("=")[1],
            }
        )

    return ret


def block_icmp(zone, icmp, permanent=True):
    """
    Block a specific ICMP type on a zone

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.block_icmp zone echo-reply
    """
    if icmp not in get_icmp_types(permanent):
        log.error("Invalid ICMP type")
        return False

    if icmp in list_icmp_block(zone, permanent):
        log.info("ICMP block already exists")
        return "success"

    cmd = "--zone={0} --add-icmp-block={1}".format(zone, icmp)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def allow_icmp(zone, icmp, permanent=True):
    """
    Allow a specific ICMP type on a zone

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.allow_icmp zone echo-reply
    """
    if icmp not in get_icmp_types(permanent):
        log.error("Invalid ICMP type")
        return False

    if icmp not in list_icmp_block(zone, permanent):
        log.info("ICMP Type is already permitted")
        return "success"

    cmd = "--zone={0} --remove-icmp-block={1}".format(zone, icmp)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def list_icmp_block(zone, permanent=True):
    """
    List ICMP blocks on a zone

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewlld.list_icmp_block zone
    """
    cmd = "--zone={0} --list-icmp-blocks".format(zone)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd).split()


def make_permanent():
    """
    Make current runtime configuration permanent.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.make_permanent
    """
    return __firewall_cmd("--runtime-to-permanent")


def get_interfaces(zone, permanent=True):
    """
    List interfaces bound to a zone

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_interfaces zone
    """
    cmd = "--zone={0} --list-interfaces".format(zone)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd).split()


def add_interface(zone, interface, permanent=True):
    """
    Bind an interface to a zone

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_interface zone eth0
    """
    if interface in get_interfaces(zone, permanent):
        log.info("Interface is already bound to zone.")

    cmd = "--zone={0} --add-interface={1}".format(zone, interface)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def remove_interface(zone, interface, permanent=True):
    """
    Remove an interface bound to a zone

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_interface zone eth0
    """
    if interface not in get_interfaces(zone, permanent):
        log.info("Interface is not bound to zone.")

    cmd = "--zone={0} --remove-interface={1}".format(zone, interface)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def get_sources(zone, permanent=True):
    """
    List sources bound to a zone

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_sources zone
    """
    cmd = "--zone={0} --list-sources".format(zone)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd).split()


def add_source(zone, source, permanent=True):
    """
    Bind a source to a zone

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_source zone 192.168.1.0/24
    """
    if source in get_sources(zone, permanent):
        log.info("Source is already bound to zone.")

    cmd = "--zone={0} --add-source={1}".format(zone, source)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def remove_source(zone, source, permanent=True):
    """
    Remove a source bound to a zone

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_source zone 192.168.1.0/24
    """
    if source not in get_sources(zone, permanent):
        log.info("Source is not bound to zone.")

    cmd = "--zone={0} --remove-source={1}".format(zone, source)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def get_rich_rules(zone, permanent=True):
    """
    List rich rules bound to a zone

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.get_rich_rules zone
    """
    cmd = "--zone={0} --list-rich-rules".format(zone)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd).splitlines()


def add_rich_rule(zone, rule, permanent=True):
    """
    Add a rich rule to a zone

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.add_rich_rule zone 'rule'
    """
    cmd = "--zone={0} --add-rich-rule='{1}'".format(zone, rule)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)


def remove_rich_rule(zone, rule, permanent=True):
    """
    Add a rich rule to a zone

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewalld.remove_rich_rule zone 'rule'
    """
    cmd = "--zone={0} --remove-rich-rule='{1}'".format(zone, rule)

    if permanent:
        cmd += " --permanent"

    return __firewall_cmd(cmd)
