"""
CSF Ip tables management
========================

:depends:   - csf utility
:configuration: See http://download.configserver.com/csf/install.txt
 for setup instructions.

.. code-block:: yaml

    Simply allow/deny rules:
      csf.rule_present:
        ip: 1.2.3.4
        method: allow
"""  # pylint: disable=W0105

import logging

log = logging.getLogger(__name__)


def __virtual__():
    if "csf.exists" in __salt__:
        return "csf"
    return (False, "csf module could not be loaded")


def rule_present(
    name,
    method,
    port=None,
    proto="tcp",
    direction="in",
    port_origin="d",
    ip_origin="s",
    ttl=None,
    comment="",
    reload=False,
):
    """
    Ensure iptable rule exists.

    name
        The ip address or CIDR for the rule.

    method
        The type of rule.  Either 'allow' or 'deny'.

    port
        Optional port to be open or closed for the
        iptables rule.

    proto
        The protocol. Either 'tcp', or 'udp'.
        Only applicable if port is specified.

    direction
        The diretion of traffic to apply the rule to.
        Either 'in', or 'out'. Only applicable if
        port is specified.

    port_origin
        Specifies either the source or destination
        port is relevant for this rule. Only applicable
        if port is specified.  Either 's', or 'd'.

    ip_origin
        Specifies whether the ip in this rule refers to
        the source or destination ip. Either 's', or
        'd'. Only applicable if port is specified.

    ttl
        How long the rule should exist. If supplied,
        `csf.tempallow()` or csf.tempdeny()` are used.

    comment
        An optional comment to appear after the rule
        as a #comment .

    reload
        Reload the csf service after applying this rule.
        Default false.

    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "Rule already exists.",
    }

    ip = name
    # Check if rule is already present
    exists = __salt__["csf.exists"](
        method=method,
        ip=ip,
        port=port,
        proto=proto,
        direction=direction,
        port_origin=port_origin,
        ip_origin=ip_origin,
        ttl=ttl,
        comment=comment,
    )

    if exists:
        return ret
    else:
        if ttl:
            method = f"temp{method}"
        func = __salt__[f"csf.{method}"]
        rule = func(
            ip,
            port=port,
            proto=proto,
            direction=direction,
            port_origin=port_origin,
            ip_origin=ip_origin,
            ttl=ttl,
            comment=comment,
        )

        if rule:
            comment = "Rule has been added."
        if reload:
            if __salt__["csf.reload"]():
                comment += " Csf reloaded."
            else:
                comment += " Unable to reload csf."
                ret["result"] = False
        ret["comment"] = comment
        ret["changes"]["Rule"] = "Created"
    return ret


def rule_absent(
    name,
    method,
    port=None,
    proto="tcp",
    direction="in",
    port_origin="d",
    ip_origin="s",
    ttl=None,
    reload=False,
):
    """
    Ensure iptable is not present.

    name
        The ip address or CIDR for the rule.

    method
        The type of rule.  Either 'allow' or 'deny'.

    port
        Optional port to be open or closed for the
        iptables rule.

    proto
        The protocol. Either 'tcp', 'udp'.
        Only applicable if port is specified.

    direction
        The diretion of traffic to apply the rule to.
        Either 'in', or 'out'. Only applicable if
        port is specified.

    port_origin
        Specifies either the source or destination
        port is relevant for this rule. Only applicable
        if port is specified.  Either 's', or 'd'.

    ip_origin
        Specifies whether the ip in this rule refers to
        the source or destination ip. Either 's', or
        'd'. Only applicable if port is specified.

    ttl
        How long the rule should exist. If supplied,
        `csf.tempallow()` or csf.tempdeny()` are used.

    reload
        Reload the csf service after applying this rule.
        Default false.
    """
    ip = name
    ret = {"name": name, "changes": {}, "result": True, "comment": "Rule not present."}

    exists = __salt__["csf.exists"](
        method,
        ip,
        port=port,
        proto=proto,
        direction=direction,
        port_origin=port_origin,
        ip_origin=ip_origin,
        ttl=ttl,
    )

    if not exists:
        return ret
    else:
        rule = __salt__["csf.remove_rule"](
            method=method,
            ip=ip,
            port=port,
            proto=proto,
            direction=direction,
            port_origin=port_origin,
            ip_origin=ip_origin,
            comment="",
            ttl=ttl,
        )

        if rule:
            comment = "Rule has been removed."
        if reload:
            if __salt__["csf.reload"]():
                comment += " Csf reloaded."
            else:
                comment += "Csf unable to be reloaded."
        ret["comment"] = comment
        ret["changes"]["Rule"] = "Removed"
    return ret


def ports_open(name, ports, proto="tcp", direction="in"):
    """
    Ensure ports are open for a protocol, in a direction.
    e.g. - proto='tcp', direction='in' would set the values
    for TCP_IN in the csf.conf file.

    ports
        A list of ports that should be open.

    proto
        The protocol. May be one of 'tcp', 'udp',
        'tcp6', or 'udp6'.

    direction
        Choose 'in', 'out', or both to indicate the port
        should be opened for inbound traffic, outbound
        traffic, or both.
    """

    ports = list(map(str, ports))
    diff = False
    ret = {
        "name": ",".join(ports),
        "changes": {},
        "result": True,
        "comment": "Ports open.",
    }

    current_ports = __salt__["csf.get_ports"](proto=proto, direction=direction)
    direction = direction.upper()
    directions = __salt__["csf.build_directions"](direction)
    for direction in directions:
        log.trace("current_ports[direction]: %s", current_ports[direction])
        log.trace("ports: %s", ports)
        if current_ports[direction] != ports:
            diff = True
    if diff:
        result = __salt__["csf.allow_ports"](ports, proto=proto, direction=direction)
        ret["changes"]["Ports"] = "Changed"
        ret["comment"] = result
    return ret


def nics_skip(name, nics, ipv6):
    """
    Alias for :mod:`csf.nics_skipped <salt.states.csf.nics_skipped>`
    """
    return nics_skipped(name, nics=nics, ipv6=ipv6)


def nics_skipped(name, nics, ipv6=False):
    """
    name
        Meaningless arg, but required for state.

    nics
        A list of nics to skip.

    ipv6
        Boolean. Set to true if you want to skip
        the ipv6 interface. Default false (ipv4).
    """
    ret = {
        "name": ",".join(nics),
        "changes": {},
        "result": True,
        "comment": "NICs skipped.",
    }

    current_skipped_nics = __salt__["csf.get_skipped_nics"](ipv6=ipv6)
    if nics == current_skipped_nics:
        return ret
    result = __salt__["csf.skip_nics"](nics, ipv6=ipv6)
    ret["changes"]["Skipped NICs"] = "Changed"
    return ret


def testing_on(name, reload=False):
    """
    Ensure testing mode is enabled in csf.

    reload
        Reload CSF after changing the testing status.
        Default false.
    """

    ret = {
        "name": "testing mode",
        "changes": {},
        "result": True,
        "comment": "Testing mode already ON.",
    }
    result = {}
    testing = __salt__["csf.get_testing_status"]()
    if int(testing) == 1:
        return ret
    enable = __salt__["csf.enable_testing_mode"]()
    if enable:
        comment = "Csf testing mode enabled"
        if reload:
            if __salt__["csf.reload"]():
                comment += " and csf reloaded."
    ret["changes"]["Testing Mode"] = "on"
    ret["comment"] = result
    return ret


def testing_off(name, reload=False):
    """
    Ensure testing mode is enabled in csf.

    reload
        Reload CSF after changing the testing status.
        Default false.
    """

    ret = {
        "name": "testing mode",
        "changes": {},
        "result": True,
        "comment": "Testing mode already OFF.",
    }

    result = {}
    testing = __salt__["csf.get_testing_status"]()
    if int(testing) == 0:
        return ret
    disable = __salt__["csf.disable_testing_mode"]()
    if disable:
        comment = "Csf testing mode disabled"
        if reload:
            if __salt__["csf.reload"]():
                comment += " and csf reloaded."
    ret["changes"]["Testing Mode"] = "off"
    ret["comment"] = comment
    return ret


def option_present(name, value, reload=False):
    """
    Ensure the state of a particular option/setting in csf.

    name
        The option name in csf.conf

    value
        The value it should be set to.

    reload
        Boolean. If set to true, csf will be reloaded after.
    """
    ret = {
        "name": "testing mode",
        "changes": {},
        "result": True,
        "comment": "Option already present.",
    }
    option = name
    current_option = __salt__["csf.get_option"](option)
    if current_option:
        l = __salt__["csf.split_option"](current_option)
        option_value = l[1]
        if f'"{value}"' == option_value:
            return ret
        else:
            result = __salt__["csf.set_option"](option, value)
            ret["comment"] = "Option modified."
            ret["changes"]["Option"] = "Changed"
    else:
        result = __salt__["file.append"](
            "/etc/csf/csf.conf", args=f'{option} = "{value}"'
        )
        ret["comment"] = "Option not present. Appended to csf.conf"
        ret["changes"]["Option"] = "Changed."
    if reload:
        if __salt__["csf.reload"]():
            ret["comment"] += ". Csf reloaded."
        else:
            ret["comment"] += ". Csf failed to reload."
            ret["result"] = False
    return ret
