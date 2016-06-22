# -*- coding: utf-8 -*-
'''
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

'''
def __virtual__():
    return 'csf'

def rule_present(name,
                method,
                port=None,
                proto='tcp',
                direction='in',
                port_origin='d',
                ip_origin='s',
                ttl=None,
                comment=''):
    '''
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


    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Rule already exists.'}

    ip = name
    # Check if rule is already present
    exists = __salt__['csf.exists'](method=method,
                                    ip=ip,
                                    port=port,
                                    proto=proto,
                                    direction=direction,
                                    port_origin=port_origin,
                                    ip_origin=ip_origin,
                                    ttl=ttl,
                                    comment=comment)

    if exists:
        return ret
    else:
        if ttl:
            method = 'temp{0}'.format(method)
        func = __salt__['csf.{0}'.format(method)]
        rule = func(ip,
                    port=port,
                    proto=proto,
                    direction=direction,
                    port_origin=port_origin,
                    ip_origin=ip_origin,
                    ttl=ttl,
                    comment=comment)

        ret['comment'] = 'Rule has been added.'
        ret['changes']['Rule'] = 'Created'
    return ret


def rule_absent(name,
                method,
                port=None,
                proto='tcp',
                direction='in',
                port_origin='d',
                ip_origin='s',
                ttl=None):
    '''
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
    '''
    ip = name
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Rule not present.'}

    exists = __salt__['csf.exists'](method,
                                    ip,
                                    port=port,
                                    proto=proto,
                                    direction=direction,
                                    port_origin=port_origin,
                                    ip_origin=ip_origin,
                                    ttl=ttl)

    if not exists:
        return ret
    else:
        rule = __salt__['csf.remove_rule'](method,
                                            ip,
                                            port=port,
                                            proto=proto,
                                            direction=direction,
                                            port_origin=port_origin,
                                            ip_origin=ip_origin,
                                            ttl=ttl)

        ret['comment'] = 'Rule has been removed.'
        ret['changes']['Rule'] = 'Removed'
    return ret

def ports_open(name, ports, proto='tcp', direction='in'):
    '''
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
    '''

    ports = map(str, ports)
    diff = False
    ret = {'name': ','.join(ports),
           'changes': {},
           'result': True,
           'comment': 'Ports open.'}

    current_ports = __salt__['csf.get_ports'](proto=proto, direction=direction)  
    direction = direction.upper()
    directions = __salt__['csf.build_directions'](direction)
    for direction in directions:
        print current_ports[direction]
        print ports
        if current_ports[direction] != ports:
            diff = True
    if diff:
        result = __salt__['csf.allow_ports'](ports, proto=proto, direction=direction)
        ret['changes']['Ports'] = 'Changed'
        ret['comment'] = result
    return ret


def nics_skip(name, nics, ipv6):
    '''
    Alias for func::csf.nics_skipped
    '''
    return nics_skipped(name, nics=nics, ipv6=ipv6)


def nics_skipped(name, nics, ipv6=False):
    '''
    name
        Meaningless arg, but required for state.

    nics
        A list of nics to skip.

    ipv6
        Boolean. Set to true if you want to skip
        the ipv6 interface. Default false (ipv4).
    '''
    ret = {'name': ','.join(nics),
           'changes': {},
           'result': True,
           'comment': 'NICs skipped.'}

    current_skipped_nics = __salt__['csf.get_skipped_nics'](ipv6=ipv6)
    if nics == current_skipped_nics:
        return ret
    result = __salt__['csf.skip_nics'](nics, ipv6=ipv6)
    ret['changes']['Skipped NICs'] = 'Changed'
    return ret

