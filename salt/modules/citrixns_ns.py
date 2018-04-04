# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the ns key.

:codeauthor: :email:`Spencer Ervin <spencer_ervin@hotmail.com>`
:maturity:   new
:depends:    none
:platform:   unix


Configuration
=============
This module accepts connection configuration details either as
parameters, or as configuration settings in pillar as a Salt proxy.
Options passed into opts will be ignored if options are passed into pillar.

.. seealso::
    :prox:`Citrix Netscaler Proxy Module <salt.proxy.citrixns>`

About
=====
This execution module was designed to handle connections to a Citrix Netscaler. This module adds support to send
connections directly to the device through the rest API.

'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils.platform
import salt.proxy.citrixns

log = logging.getLogger(__name__)

__virtualname__ = 'ns'


def __virtual__():
    '''
    Will load for the citrixns proxy minions.
    '''
    try:
        if salt.utils.platform.is_proxy() and \
           __opts__['proxy']['proxytype'] == 'citrixns':
            return __virtualname__
    except KeyError:
        pass

    return False, 'The ns execution module can only be loaded for citrixns proxy minions.'


def add_nsacl(aclname=None, aclaction=None, td=None, srcip=None, srcipop=None, srcipval=None, srcport=None,
              srcportop=None, srcportval=None, destip=None, destipop=None, destipval=None, destport=None,
              destportop=None, destportval=None, ttl=None, srcmac=None, srcmacmask=None, protocol=None,
              protocolnumber=None, vlan=None, vxlan=None, interface=None, established=None, icmptype=None, icmpcode=None,
              priority=None, state=None, logstate=None, ratelimit=None, newname=None, save=False):
    '''
    Add a new nsacl to the running configuration.

    aclname(str): Name for the extended ACL rule. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Minimum length = 1

    aclaction(str): Action to perform on incoming IPv4 packets that match the extended ACL rule. Available settings function
        as follows: * ALLOW - The NetScaler appliance processes the packet. * BRIDGE - The NetScaler appliance bridges
        the packet to the destination without processing it. * DENY - The NetScaler appliance drops the packet. Possible
        values = BRIDGE, DENY, ALLOW

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcip(bool): IP address or range of IP addresses to match against the source IP address of an incoming IPv4 packet. In
        the command line interface, separate the range with a hyphen. For example: 10.102.29.30-10.102.29.189.

    srcipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcipval(str): IP address or range of IP addresses to match against the source IP address of an incoming IPv4 packet. In
        the command line interface, separate the range with a hyphen. For example:10.102.29.30-10.102.29.189.

    srcport(bool): Port number or range of port numbers to match against the source port number of an incoming IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90.

    srcportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcportval(str): Port number or range of port numbers to match against the source port number of an incoming IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90. Maximum length = 65535

    destip(bool): IP address or range of IP addresses to match against the destination IP address of an incoming IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 10.102.29.30-10.102.29.189.

    destipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destipval(str): IP address or range of IP addresses to match against the destination IP address of an incoming IPv4
        packet. In the command line interface, separate the range with a hyphen. For example:
        10.102.29.30-10.102.29.189.

    destport(bool): Port number or range of port numbers to match against the destination port number of an incoming IPv4
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols.

    destportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destportval(str): Port number or range of port numbers to match against the destination port number of an incoming IPv4
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols. Maximum length = 65535

    ttl(int): Number of seconds, in multiples of four, after which the extended ACL rule expires. If you do not want the
        extended ACL rule to expire, do not specify a TTL value. Minimum value = 1 Maximum value = 2147483647

    srcmac(str): MAC address to match against the source MAC address of an incoming IPv4 packet.

    srcmacmask(str): Used to define range of Source MAC address. It takes string of 0 and 1, 0s are for exact match and 1s
        for wildcard. For matching first 3 bytes of MAC address, srcMacMask value "000000111111". . Default value:
        "000000000000"

    protocol(str): Protocol to match against the protocol of an incoming IPv4 packet. Possible values = ICMP, IGMP, TCP, EGP,
        IGP, ARGUS, UDP, RDP, RSVP, EIGRP, L2TP, ISIS

    protocolnumber(int): Protocol to match against the protocol of an incoming IPv4 packet. Minimum value = 1 Maximum value =
        255

    vlan(int): ID of the VLAN. The NetScaler appliance applies the ACL rule only to the incoming packets of the specified
        VLAN. If you do not specify a VLAN ID, the appliance applies the ACL rule to the incoming packets on all VLANs.
        Minimum value = 1 Maximum value = 4094

    vxlan(int): ID of the VXLAN. The NetScaler appliance applies the ACL rule only to the incoming packets of the specified
        VXLAN. If you do not specify a VXLAN ID, the appliance applies the ACL rule to the incoming packets on all
        VXLANs. Minimum value = 1 Maximum value = 16777215

    interface(str): ID of an interface. The NetScaler appliance applies the ACL rule only to the incoming packets from the
        specified interface. If you do not specify any value, the appliance applies the ACL rule to the incoming packets
        of all interfaces.

    established(bool): Allow only incoming TCP packets that have the ACK or RST bit set, if the action set for the ACL rule
        is ALLOW and these packets match the other conditions in the ACL rule.

    icmptype(int): ICMP Message type to match against the message type of an incoming ICMP packet. For example, to block
        DESTINATION UNREACHABLE messages, you must specify 3 as the ICMP type.  Note: This parameter can be specified
        only for the ICMP protocol. Minimum value = 0 Maximum value = 65536

    icmpcode(int): Code of a particular ICMP message type to match against the ICMP code of an incoming ICMP packet. For
        example, to block DESTINATION HOST UNREACHABLE messages, specify 3 as the ICMP type and 1 as the ICMP code.  If
        you set this parameter, you must set the ICMP Type parameter. Minimum value = 0 Maximum value = 65536

    priority(int): Priority for the extended ACL rule that determines the order in which it is evaluated relative to the
        other extended ACL rules. If you do not specify priorities while creating extended ACL rules, the ACL rules are
        evaluated in the order in which they are created. Minimum value = 1 Maximum value = 100000

    state(str): Enable or disable the extended ACL rule. After you apply the extended ACL rules, the NetScaler appliance
        compares incoming packets against the enabled extended ACL rules. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    logstate(str): Enable or disable logging of events related to the extended ACL rule. The log messages are stored in the
        configured syslog or auditlog server. Default value: DISABLED Possible values = ENABLED, DISABLED

    ratelimit(int): Maximum number of log messages to be generated per second. If you set this parameter, you must enable the
        Log State parameter. Default value: 100 Minimum value = 1 Maximum value = 10000

    newname(str): New name for the extended ACL rule. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsacl <args>

    '''

    result = {}

    payload = {'nsacl': {}}

    if aclname:
        payload['nsacl']['aclname'] = aclname

    if aclaction:
        payload['nsacl']['aclaction'] = aclaction

    if td:
        payload['nsacl']['td'] = td

    if srcip:
        payload['nsacl']['srcip'] = srcip

    if srcipop:
        payload['nsacl']['srcipop'] = srcipop

    if srcipval:
        payload['nsacl']['srcipval'] = srcipval

    if srcport:
        payload['nsacl']['srcport'] = srcport

    if srcportop:
        payload['nsacl']['srcportop'] = srcportop

    if srcportval:
        payload['nsacl']['srcportval'] = srcportval

    if destip:
        payload['nsacl']['destip'] = destip

    if destipop:
        payload['nsacl']['destipop'] = destipop

    if destipval:
        payload['nsacl']['destipval'] = destipval

    if destport:
        payload['nsacl']['destport'] = destport

    if destportop:
        payload['nsacl']['destportop'] = destportop

    if destportval:
        payload['nsacl']['destportval'] = destportval

    if ttl:
        payload['nsacl']['ttl'] = ttl

    if srcmac:
        payload['nsacl']['srcmac'] = srcmac

    if srcmacmask:
        payload['nsacl']['srcmacmask'] = srcmacmask

    if protocol:
        payload['nsacl']['protocol'] = protocol

    if protocolnumber:
        payload['nsacl']['protocolnumber'] = protocolnumber

    if vlan:
        payload['nsacl']['vlan'] = vlan

    if vxlan:
        payload['nsacl']['vxlan'] = vxlan

    if interface:
        payload['nsacl']['Interface'] = interface

    if established:
        payload['nsacl']['established'] = established

    if icmptype:
        payload['nsacl']['icmptype'] = icmptype

    if icmpcode:
        payload['nsacl']['icmpcode'] = icmpcode

    if priority:
        payload['nsacl']['priority'] = priority

    if state:
        payload['nsacl']['state'] = state

    if logstate:
        payload['nsacl']['logstate'] = logstate

    if ratelimit:
        payload['nsacl']['ratelimit'] = ratelimit

    if newname:
        payload['nsacl']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/nsacl', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsacl6(acl6name=None, acl6action=None, td=None, srcipv6=None, srcipop=None, srcipv6val=None, srcport=None,
               srcportop=None, srcportval=None, destipv6=None, destipop=None, destipv6val=None, destport=None,
               destportop=None, destportval=None, ttl=None, srcmac=None, srcmacmask=None, protocol=None,
               protocolnumber=None, vlan=None, vxlan=None, interface=None, established=None, icmptype=None,
               icmpcode=None, priority=None, state=None, aclaction=None, newname=None, save=False):
    '''
    Add a new nsacl6 to the running configuration.

    acl6name(str): Name for the ACL6 rule. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Minimum length = 1

    acl6action(str): Action to perform on the incoming IPv6 packets that match the ACL6 rule. Available settings function as
        follows: * ALLOW - The NetScaler appliance processes the packet. * BRIDGE - The NetScaler appliance bridges the
        packet to the destination without processing it. * DENY - The NetScaler appliance drops the packet. Possible
        values = BRIDGE, DENY, ALLOW

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcipv6(bool): IP address or range of IP addresses to match against the source IP address of an incoming IPv6 packet. In
        the command line interface, separate the range with a hyphen.

    srcipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcipv6val(str): Source IPv6 address (range).

    srcport(bool): Port number or range of port numbers to match against the source port number of an incoming IPv6 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The destination port
        can be specified only for TCP and UDP protocols.

    srcportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcportval(str): Source port (range). Maximum length = 65535

    destipv6(bool): IP address or range of IP addresses to match against the destination IP address of an incoming IPv6
        packet. In the command line interface, separate the range with a hyphen.

    destipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destipv6val(str): Destination IPv6 address (range).

    destport(bool): Port number or range of port numbers to match against the destination port number of an incoming IPv6
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols.

    destportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destportval(str): Destination port (range). Maximum length = 65535

    ttl(int): Time to expire this ACL6 (in seconds). Minimum value = 1 Maximum value = 2147483647

    srcmac(str): MAC address to match against the source MAC address of an incoming IPv6 packet.

    srcmacmask(str): Used to define range of Source MAC address. It takes string of 0 and 1, 0s are for exact match and 1s
        for wildcard. For matching first 3 bytes of MAC address, srcMacMask value "000000111111". . Default value:
        "000000000000"

    protocol(str): Protocol, identified by protocol name, to match against the protocol of an incoming IPv6 packet. Possible
        values = ICMPV6, TCP, UDP

    protocolnumber(int): Protocol, identified by protocol number, to match against the protocol of an incoming IPv6 packet.
        Minimum value = 1 Maximum value = 255

    vlan(int): ID of the VLAN. The NetScaler appliance applies the ACL6 rule only to the incoming packets on the specified
        VLAN. If you do not specify a VLAN ID, the appliance applies the ACL6 rule to the incoming packets on all VLANs.
        Minimum value = 1 Maximum value = 4094

    vxlan(int): ID of the VXLAN. The NetScaler appliance applies the ACL6 rule only to the incoming packets on the specified
        VXLAN. If you do not specify a VXLAN ID, the appliance applies the ACL6 rule to the incoming packets on all
        VXLANs. Minimum value = 1 Maximum value = 16777215

    interface(str): ID of an interface. The NetScaler appliance applies the ACL6 rule only to the incoming packets from the
        specified interface. If you do not specify any value, the appliance applies the ACL6 rule to the incoming packets
        from all interfaces.

    established(bool): Allow only incoming TCP packets that have the ACK or RST bit set if the action set for the ACL6 rule
        is ALLOW and these packets match the other conditions in the ACL6 rule.

    icmptype(int): ICMP Message type to match against the message type of an incoming IPv6 ICMP packet. For example, to block
        DESTINATION UNREACHABLE messages, you must specify 3 as the ICMP type.  Note: This parameter can be specified
        only for the ICMP protocol. Minimum value = 0 Maximum value = 65536

    icmpcode(int): Code of a particular ICMP message type to match against the ICMP code of an incoming IPv6 ICMP packet. For
        example, to block DESTINATION HOST UNREACHABLE messages, specify 3 as the ICMP type and 1 as the ICMP code.  If
        you set this parameter, you must set the ICMP Type parameter. Minimum value = 0 Maximum value = 65536

    priority(int): Priority for the ACL6 rule, which determines the order in which it is evaluated relative to the other ACL6
        rules. If you do not specify priorities while creating ACL6 rules, the ACL6 rules are evaluated in the order in
        which they are created. Minimum value = 1 Maximum value = 81920

    state(str): State of the ACL6. Default value: ENABLED Possible values = ENABLED, DISABLED

    aclaction(str): Action associated with the ACL6. Possible values = BRIDGE, DENY, ALLOW

    newname(str): New name for the ACL6 rule. Must begin with an ASCII alphabetic or underscore \\(_\\) character, and must
        contain only ASCII alphanumeric, underscore, hash \\(\\#\\), period \\(.\\), space, colon \\(:\\), at \\(@\\),
        equals \\(=\\), and hyphen \\(-\\) characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsacl6 <args>

    '''

    result = {}

    payload = {'nsacl6': {}}

    if acl6name:
        payload['nsacl6']['acl6name'] = acl6name

    if acl6action:
        payload['nsacl6']['acl6action'] = acl6action

    if td:
        payload['nsacl6']['td'] = td

    if srcipv6:
        payload['nsacl6']['srcipv6'] = srcipv6

    if srcipop:
        payload['nsacl6']['srcipop'] = srcipop

    if srcipv6val:
        payload['nsacl6']['srcipv6val'] = srcipv6val

    if srcport:
        payload['nsacl6']['srcport'] = srcport

    if srcportop:
        payload['nsacl6']['srcportop'] = srcportop

    if srcportval:
        payload['nsacl6']['srcportval'] = srcportval

    if destipv6:
        payload['nsacl6']['destipv6'] = destipv6

    if destipop:
        payload['nsacl6']['destipop'] = destipop

    if destipv6val:
        payload['nsacl6']['destipv6val'] = destipv6val

    if destport:
        payload['nsacl6']['destport'] = destport

    if destportop:
        payload['nsacl6']['destportop'] = destportop

    if destportval:
        payload['nsacl6']['destportval'] = destportval

    if ttl:
        payload['nsacl6']['ttl'] = ttl

    if srcmac:
        payload['nsacl6']['srcmac'] = srcmac

    if srcmacmask:
        payload['nsacl6']['srcmacmask'] = srcmacmask

    if protocol:
        payload['nsacl6']['protocol'] = protocol

    if protocolnumber:
        payload['nsacl6']['protocolnumber'] = protocolnumber

    if vlan:
        payload['nsacl6']['vlan'] = vlan

    if vxlan:
        payload['nsacl6']['vxlan'] = vxlan

    if interface:
        payload['nsacl6']['Interface'] = interface

    if established:
        payload['nsacl6']['established'] = established

    if icmptype:
        payload['nsacl6']['icmptype'] = icmptype

    if icmpcode:
        payload['nsacl6']['icmpcode'] = icmpcode

    if priority:
        payload['nsacl6']['priority'] = priority

    if state:
        payload['nsacl6']['state'] = state

    if aclaction:
        payload['nsacl6']['aclaction'] = aclaction

    if newname:
        payload['nsacl6']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/nsacl6', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsappflowcollector(name=None, ipaddress=None, port=None, save=False):
    '''
    Add a new nsappflowcollector to the running configuration.

    name(str): Name of the AppFlow collector. Minimum length = 1 Maximum length = 127

    ipaddress(str): The IPv4 address of the AppFlow collector.

    port(int): The UDP port on which the AppFlow collector is listening. Default value: 4739

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsappflowcollector <args>

    '''

    result = {}

    payload = {'nsappflowcollector': {}}

    if name:
        payload['nsappflowcollector']['name'] = name

    if ipaddress:
        payload['nsappflowcollector']['ipaddress'] = ipaddress

    if port:
        payload['nsappflowcollector']['port'] = port

    execution = __proxy__['citrixns.post']('config/nsappflowcollector', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsassignment(name=None, variable=None, ns_set=None, add=None, sub=None, append=None, clear=None, comment=None,
                     newname=None, save=False):
    '''
    Add a new nsassignment to the running configuration.

    name(str): Name for the assignment. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Can be changed after the assignment is added.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my assignment" or my assignment).

    variable(str): Left hand side of the assigment, of the form $variable-name (for a singleton variabled) or
        $variable-name[key-expression], where key-expression is a default syntax expression that evaluates to a text
        string and provides the key to select a map entry.

    ns_set(str): Right hand side of the assignment. The default syntax expression is evaluated and assigned to theleft hand
        variable.

    add(str): Right hand side of the assignment. The default syntax expression is evaluated and added to the left hand
        variable.

    sub(str): Right hand side of the assignment. The default syntax expression is evaluated and subtracted from the left hand
        variable.

    append(str): Right hand side of the assignment. The default syntax expression is evaluated and appended to the left hand
        variable.

    clear(bool): Clear the variable value. Deallocates a text value, and for a map, the text key.

    comment(str): Comment. Can be used to preserve information about this rewrite action.

    newname(str): New name for the assignment. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon (:),
        and underscore characters. Can be changed after the rewrite policy is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my assignment" or my assignment). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsassignment <args>

    '''

    result = {}

    payload = {'nsassignment': {}}

    if name:
        payload['nsassignment']['name'] = name

    if variable:
        payload['nsassignment']['variable'] = variable

    if ns_set:
        payload['nsassignment']['set'] = ns_set

    if add:
        payload['nsassignment']['Add'] = add

    if sub:
        payload['nsassignment']['sub'] = sub

    if append:
        payload['nsassignment']['append'] = append

    if clear:
        payload['nsassignment']['clear'] = clear

    if comment:
        payload['nsassignment']['comment'] = comment

    if newname:
        payload['nsassignment']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/nsassignment', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nscentralmanagementserver(ns_type=None, username=None, password=None, ipaddress=None, servername=None,
                                  save=False):
    '''
    Add a new nscentralmanagementserver to the running configuration.

    ns_type(str): Type of the central management server. Must be either CLOUD or ONPREM depending on whether the server is on
        the cloud or on premise. Possible values = CLOUD, ONPREM

    username(str): Username for access to central management server. Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters.  The following requirement applies only to the NetScaler
        CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for example,
        "my ns centralmgmtserver" or "my ns centralmgmtserver"). Minimum length = 1 Maximum length = 127

    password(str): Password for access to central management server. Required for any user account. Minimum length = 1
        Maximum length = 127

    ipaddress(str): Ip Address of central management server. Minimum length = 1

    servername(str): Fully qualified domain name of the central management server.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nscentralmanagementserver <args>

    '''

    result = {}

    payload = {'nscentralmanagementserver': {}}

    if ns_type:
        payload['nscentralmanagementserver']['type'] = ns_type

    if username:
        payload['nscentralmanagementserver']['username'] = username

    if password:
        payload['nscentralmanagementserver']['password'] = password

    if ipaddress:
        payload['nscentralmanagementserver']['ipaddress'] = ipaddress

    if servername:
        payload['nscentralmanagementserver']['servername'] = servername

    execution = __proxy__['citrixns.post']('config/nscentralmanagementserver', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsencryptionkey(name=None, method=None, keyvalue=None, padding=None, iv=None, comment=None, save=False):
    '''
    Add a new nsencryptionkey to the running configuration.

    name(str): Key name. This follows the same syntax rules as other default syntax expression entity names:  It must begin
        with an alpha character (A-Z or a-z) or an underscore (_).  The rest of the characters must be alpha, numeric
        (0-9) or underscores.  It cannot be re or xp (reserved for regular and XPath expressions).  It cannot be a
        default syntax expression reserved word (e.g. SYS or HTTP).  It cannot be used for an existing default syntax
        expression object (HTTP callout, patset, dataset, stringmap, or named expression). Minimum length = 1

    method(str): Cipher method to be used to encrypt and decrypt content.  NONE - no encryption or decryption is performed
        The output of ENCRYPT() and DECRYPT() is the same as the input.  RC4 - the RC4 stream cipher with a 128 bit (16
        byte) key; RC4 is now considered insecure and should only be used if required by existing applciations.
        DES[-;lt;mode;gt;] - the Data Encryption Standard (DES) block cipher with a 64-bit (8 byte) key, with 56 data
        bits and 8 parity bits. DES is considered less secure than DES3 or AES so it should only be used if required by
        an existing applicastion. The optional mode is described below; DES without a mode is equivalent to DES-CBC.
        DES3[-;lt;mode;gt;] - the Triple Data Encryption Standard (DES) block cipher with a 192-bit (24 byte) key. The
        optional mode is described below; DES3 without a mode is equivalent to DES3-CBC.
        AES;lt;keysize;gt;[-;lt;mode;gt;] - the Advanced Encryption Standard block cipher, available with 128 bit (16
        byte), 192 bit (24 byte), and 256 bit (32 byte) keys. The optional mode is described below; AES;lt;keysize;gt;
        without a mode is equivalent to AES;lt;keysize;gt;-CBC.  For a block cipher, the ;lt;mode;gt; specifies how
        multiple blocks of plaintext are encrypted and how the Initialization Vector (IV) is used. Choices are  CBC
        (Cipher Block Chaining) - Each block of plaintext is XORed with the previous ciphertext block, or IV for the
        first block, before being encrypted. Padding is required if the plaintext is not a multiple of the cipher block
        size.  CFB (Cipher Feedback) - The previous ciphertext block, or the IV for the first block, is encrypted and the
        output is XORed with the current plaintext block to create the current ciphertext block. The 128-bit version of
        CFB is provided. Padding is not required.  OFB (Output Feedback) - A keystream is generated by applying the
        cipher successfully to the IV and XORing the keystream blocks with the plaintext. Padding is not required.  ECB
        (Electronic Codebook) - Each block of plaintext is independently encrypted. An IV is not used. Padding is
        required. This mode is considered less secure than the other modes because the same plaintext always produces the
        same encrypted text and should only be used if required by an existing application. Possible values = NONE, RC4,
        DES3, AES128, AES192, AES256, DES, DES-CBC, DES-CFB, DES-OFB, DES-ECB, DES3-CBC, DES3-CFB, DES3-OFB, DES3-ECB,
        AES128-CBC, AES128-CFB, AES128-OFB, AES128-ECB, AES192-CBC, AES192-CFB, AES192-OFB, AES192-ECB, AES256-CBC,
        AES256-CFB, AES256-OFB, AES256-ECB

    keyvalue(str): The hex-encoded key value. The length is determined by the cipher method:  RC4 - 16 bytes  DES - 8 bytes
        (all modes)  DES3 - 24 bytes (all modes)  AES128 - 16 bytes (all modes)  AES192 - 24 bytes (all modes)  AES256 -
        32 bytes (all modes) Note that the keyValue will be encrypted when it it is saved.

    padding(str): Enables or disables the padding of plaintext to meet the block size requirements of block ciphers:  ON -
        For encryption, PKCS5/7 padding is used, which appends n bytes of value n on the end of the plaintext to bring it
        to the cipher block lnegth. If the plaintext length is alraady a multiple of the block length, an additional
        block with bytes of value block_length will be added. For decryption, ISO 10126 padding is accepted, which
        expects the last byte of the block to be the number of added pad bytes. Note that this accepts PKCS5/7 padding,
        as well as ANSI_X923 padding. Padding ON is the default for the ECB and CBD modes.  OFF - No padding. An Undef
        error will occur with the ECB or CBC modes if the plaintext length is not a multitple of the cipher block size.
        This can be used with the CFB and OFB modes, and with the ECB and CBC modes if the plaintext will always be an
        integral number of blocks, or if custom padding is implemented using a policy extension function. Padding OFf is
        the default for CFB and OFB modes. Default value: DEFAULT Possible values = OFF, ON

    iv(str): The initalization voector (IV) for a block cipher, one block of data used to initialize the encryption. The best
        practice is to not specify an IV, in which case a new random IV will be generated for each encryption. The format
        must be iv_data or keyid_iv_data to include the generated IV in the encrypted data. The IV should only be
        specified if it cannot be included in the encrypted data. The IV length is the cipher block size:  RC4 - not used
        (error if IV is specified)  DES - 8 bytes (all modes)  DES3 - 8 bytes (all modes)  AES128 - 16 bytes (all modes)
        AES192 - 16 bytes (all modes)  AES256 - 16 bytes (all modes).

    comment(str): Comments associated with this encryption key.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsencryptionkey <args>

    '''

    result = {}

    payload = {'nsencryptionkey': {}}

    if name:
        payload['nsencryptionkey']['name'] = name

    if method:
        payload['nsencryptionkey']['method'] = method

    if keyvalue:
        payload['nsencryptionkey']['keyvalue'] = keyvalue

    if padding:
        payload['nsencryptionkey']['padding'] = padding

    if iv:
        payload['nsencryptionkey']['iv'] = iv

    if comment:
        payload['nsencryptionkey']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/nsencryptionkey', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsextension(src=None, name=None, comment=None, overwrite=None, trace=None, tracefunctions=None,
                    tracevariables=None, detail=None, save=False):
    '''
    Add a new nsextension to the running configuration.

    src(str): Local path to and name of, or URL (protocol, host, path, and file name) for, the file in which to store the
        imported extension. NOTE: The import fails if the object to be imported is on an HTTPS server that requires
        client certificate authentication for access. Minimum length = 1 Maximum length = 2047

    name(str): Name to assign to the extension object on the NetScaler appliance. Minimum length = 1 Maximum length = 31

    comment(str): Any comments to preserve information about the extension object. Maximum length = 128

    overwrite(bool): Overwrites the existing file.

    trace(str): Enables tracing to the NS log file of extension execution:  off - turns off tracing (equivalent to unset ns
        extension ;lt;extension-name;gt; -trace)  calls - traces extension function calls with arguments and function
        returns with the first return value  lines - traces the above plus line numbers for executed extension lines  all
        - traces the above plus local variables changed by executed extension lines Note that the DEBUG log level must be
        enabled to see extension tracing. This can be done by set audit syslogParams -loglevel ALL or -loglevel DEBUG.
        Default value: off Possible values = off, calls, lines, all

    tracefunctions(str): Comma-separated list of extension functions to trace. By default, all extension functions are
        traced. Maximum length = 256

    tracevariables(str): Comma-separated list of variables (in traced extension functions) to trace. By default, all
        variables are traced. Maximum length = 256

    detail(str): Show detail for extension function. Possible values = brief, all

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsextension <args>

    '''

    result = {}

    payload = {'nsextension': {}}

    if src:
        payload['nsextension']['src'] = src

    if name:
        payload['nsextension']['name'] = name

    if comment:
        payload['nsextension']['comment'] = comment

    if overwrite:
        payload['nsextension']['overwrite'] = overwrite

    if trace:
        payload['nsextension']['trace'] = trace

    if tracefunctions:
        payload['nsextension']['tracefunctions'] = tracefunctions

    if tracevariables:
        payload['nsextension']['tracevariables'] = tracevariables

    if detail:
        payload['nsextension']['detail'] = detail

    execution = __proxy__['citrixns.post']('config/nsextension', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nshmackey(name=None, digest=None, keyvalue=None, comment=None, save=False):
    '''
    Add a new nshmackey to the running configuration.

    name(str): Key name. This follows the same syntax rules as other default syntax expression entity names:  It must begin
        with an alpha character (A-Z or a-z) or an underscore (_).  The rest of the characters must be alpha, numeric
        (0-9) or underscores.  It cannot be re or xp (reserved for regular and XPath expressions).  It cannot be a
        default syntax expression reserved word (e.g. SYS or HTTP).  It cannot be used for an existing default syntax
        expression object (HTTP callout, patset, dataset, stringmap, or named expression). Minimum length = 1

    digest(str): Digest (hash) function to be used in the HMAC computation. Possible values = MD2, MD4, MD5, SHA1, SHA224,
        SHA256, SHA384, SHA512

    keyvalue(str): The hex-encoded key to be used in the HMAC computation. The key can be any length (up to a
        NetScaler-imposed maximum of 255 bytes). If the length is less than the digest block size, it will be zero padded
        up to the block size. If it is greater than the block size, it will be hashed using the digest function to the
        block size. The block size for each digest is:  MD2 - 16 bytes  MD4 - 16 bytes  MD5 - 16 bytes  SHA1 - 20 bytes
        SHA224 - 28 bytes  SHA256 - 32 bytes  SHA384 - 48 bytes  SHA512 - 64 bytes Note that the key will be encrypted
        when it it is saved.

    comment(str): Comments associated with this encryption key.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nshmackey <args>

    '''

    result = {}

    payload = {'nshmackey': {}}

    if name:
        payload['nshmackey']['name'] = name

    if digest:
        payload['nshmackey']['digest'] = digest

    if keyvalue:
        payload['nshmackey']['keyvalue'] = keyvalue

    if comment:
        payload['nshmackey']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/nshmackey', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nshttpprofile(name=None, dropinvalreqs=None, markhttp09inval=None, markconnreqinval=None, cmponpush=None,
                      conmultiplex=None, maxreusepool=None, dropextracrlf=None, incomphdrdelay=None, websocket=None,
                      rtsptunnel=None, reqtimeout=None, adpttimeout=None, reqtimeoutaction=None, dropextradata=None,
                      weblog=None, clientiphdrexpr=None, maxreq=None, persistentetag=None, spdy=None, http2=None,
                      http2direct=None, altsvc=None, reusepooltimeout=None, maxheaderlen=None, minreusepool=None,
                      http2maxheaderlistsize=None, http2maxframesize=None, http2maxconcurrentstreams=None,
                      http2initialwindowsize=None, http2headertablesize=None, http2minseverconn=None,
                      apdexcltresptimethreshold=None, save=False):
    '''
    Add a new nshttpprofile to the running configuration.

    name(str): Name for an HTTP profile. Must begin with a letter, number, or the underscore \\(_\\) character. Other
        characters allowed, after the first character, are the hyphen \\(-\\), period \\(.\\), hash \\(\\#\\), space \\(
        \\), at \\(@\\), colon \\(:\\), and equal \\(=\\) characters. The name of a HTTP profile cannot be changed after
        it is created.  CLI Users: If the name includes one or more spaces, enclose the name in double or single
        quotation marks \\(for example, "my http profile" or my http profile\\). Minimum length = 1 Maximum length = 127

    dropinvalreqs(str): Drop invalid HTTP requests or responses. Default value: DISABLED Possible values = ENABLED, DISABLED

    markhttp09inval(str): Mark HTTP/0.9 requests as invalid. Default value: DISABLED Possible values = ENABLED, DISABLED

    markconnreqinval(str): Mark CONNECT requests as invalid. Default value: DISABLED Possible values = ENABLED, DISABLED

    cmponpush(str): Start data compression on receiving a TCP packet with PUSH flag set. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    conmultiplex(str): Reuse server connections for requests from more than one client connections. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    maxreusepool(int): Maximum limit on the number of connections, from the NetScaler to a particular server that are kept in
        the reuse pool. This setting is helpful for optimal memory utilization and for reducing the idle connections to
        the server just after the peak time. Zero implies no limit on reuse pool size. If non-zero value is given, it has
        to be greater than or equal to the number of running Packet Engines. Default value: 0 Minimum value = 0 Maximum
        value = 360000

    dropextracrlf(str): Drop any extra CR and LF characters present after the header. Default value: ENABLED Possible values
        = ENABLED, DISABLED

    incomphdrdelay(int): Maximum time to wait, in milliseconds, between incomplete header packets. If the header packets take
        longer to arrive at NetScaler, the connection is silently dropped. Default value: 7000 Minimum value = 1 Maximum
        value = 360000

    websocket(str): HTTP connection to be upgraded to a web socket connection. Once upgraded, NetScaler does not process
        Layer 7 traffic on this connection. Default value: DISABLED Possible values = ENABLED, DISABLED

    rtsptunnel(str): Allow RTSP tunnel in HTTP. Once application/x-rtsp-tunnelled is seen in Accept or Content-Type header,
        NetScaler does not process Layer 7 traffic on this connection. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    reqtimeout(int): Time, in seconds, within which the HTTP request must complete. If the request does not complete within
        this time, the specified request timeout action is executed. Zero disables the timeout. Default value: 0 Minimum
        value = 0 Maximum value = 86400

    adpttimeout(str): Adapts the configured request timeout based on flow conditions. The timeout is increased or decreased
        internally and applied on the flow. Default value: DISABLED Possible values = ENABLED, DISABLED

    reqtimeoutaction(str): Action to take when the HTTP request does not complete within the specified request timeout
        duration. You can configure the following actions: * RESET - Send RST (reset) to client when timeout occurs. *
        DROP - Drop silently when timeout occurs. * Custom responder action - Name of the responder action to trigger
        when timeout occurs, used to send custom message.

    dropextradata(str): Drop any extra data when server sends more data than the specified content-length. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    weblog(str): Enable or disable web logging. Default value: ENABLED Possible values = ENABLED, DISABLED

    clientiphdrexpr(str): Name of the header that contains the real client IP address.

    maxreq(int): Maximum number of requests allowed on a single connection. Zero implies no limit on the number of requests.
        Default value: 0 Minimum value = 0 Maximum value = 65534

    persistentetag(str): Generate the persistent NetScaler specific ETag for the HTTP response with ETag header. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    spdy(str): Enable SPDYv2 or SPDYv3 or both over SSL vserver. SSL will advertise SPDY support either during NPN Handshake
        or when client will advertises SPDY support during ALPN handshake. Both SPDY versions are enabled when this
        parameter is set to ENABLED. Default value: DISABLED Possible values = DISABLED, ENABLED, V2, V3

    http2(str): Choose whether to enable support for HTTP/2. Default value: DISABLED Possible values = ENABLED, DISABLED

    http2direct(str): Choose whether to enable support for Direct HTTP/2. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    altsvc(str): Choose whether to enable support for Alternative Service. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    reusepooltimeout(int): Idle timeout (in seconds) for server connections in re-use pool. Connections in the re-use pool
        are flushed, if they remain idle for the configured timeout. Default value: 0 Minimum value = 0 Maximum value =
        31536000

    maxheaderlen(int): Number of bytes to be queued to look for complete header before returning error. If complete header is
        not obtained after queuing these many bytes, request will be marked as invalid and no L7 processing will be done
        for that TCP connection. Default value: 24820 Minimum value = 2048 Maximum value = 61440

    minreusepool(int): Minimum limit on the number of connections, from the NetScaler to a particular server that are kept in
        the reuse pool. This setting is helpful for optimal memory utilization and for reducing the idle connections to
        the server just after the peak time. Zero implies no limit on reuse pool size. Default value: 0 Minimum value = 0
        Maximum value = 360000

    http2maxheaderlistsize(int): Maximum size of header list that the NetScaler is prepared to accept, in bytes. NOTE: The
        actual plain text header size that the NetScaler accepts is limited by maxHeaderLen. Please change this parameter
        as well when modifying http2MaxHeaderListSize. Default value: 24576 Minimum value = 8192 Maximum value = 65535

    http2maxframesize(int): Maximum size of the frame payload that the NetScaler is willing to receive, in bytes. Default
        value: 16384 Minimum value = 16384 Maximum value = 16777215

    http2maxconcurrentstreams(int): Maximum number of concurrent streams that is allowed per connection. Default value: 100
        Minimum value = 0 Maximum value = 1000

    http2initialwindowsize(int): Initial window size for stream level flow control, in bytes. Default value: 65535 Minimum
        value = 8192 Maximum value = 20971520

    http2headertablesize(int): Maximum size of the header compression table used to decode header blocks, in bytes. Default
        value: 4096 Minimum value = 0 Maximum value = 16384

    http2minseverconn(int): Minimum number of HTTP2 connections established to backend server, on receiving HTTP requests
        from client before multiplexing the streams into the available HTTP/2 connections. Default value: 20 Minimum
        value = 1 Maximum value = 360000

    apdexcltresptimethreshold(int): This option sets the satisfactory threshold (T) for client response time in milliseconds
        to be used for APDEX calculations. This means a transaction responding in less than this threshold is considered
        satisfactory. Transaction responding between T and 4*T is considered tolerable. Any transaction responding in
        more than 4*T time is considered frustrating. Netscaler maintains stats for such tolerable and frustrating
        transcations. And client response time related apdex counters are only updated on a vserver which receives
        clients traffic. Default value: 500 Minimum value = 1 Maximum value = 3600000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nshttpprofile <args>

    '''

    result = {}

    payload = {'nshttpprofile': {}}

    if name:
        payload['nshttpprofile']['name'] = name

    if dropinvalreqs:
        payload['nshttpprofile']['dropinvalreqs'] = dropinvalreqs

    if markhttp09inval:
        payload['nshttpprofile']['markhttp09inval'] = markhttp09inval

    if markconnreqinval:
        payload['nshttpprofile']['markconnreqinval'] = markconnreqinval

    if cmponpush:
        payload['nshttpprofile']['cmponpush'] = cmponpush

    if conmultiplex:
        payload['nshttpprofile']['conmultiplex'] = conmultiplex

    if maxreusepool:
        payload['nshttpprofile']['maxreusepool'] = maxreusepool

    if dropextracrlf:
        payload['nshttpprofile']['dropextracrlf'] = dropextracrlf

    if incomphdrdelay:
        payload['nshttpprofile']['incomphdrdelay'] = incomphdrdelay

    if websocket:
        payload['nshttpprofile']['websocket'] = websocket

    if rtsptunnel:
        payload['nshttpprofile']['rtsptunnel'] = rtsptunnel

    if reqtimeout:
        payload['nshttpprofile']['reqtimeout'] = reqtimeout

    if adpttimeout:
        payload['nshttpprofile']['adpttimeout'] = adpttimeout

    if reqtimeoutaction:
        payload['nshttpprofile']['reqtimeoutaction'] = reqtimeoutaction

    if dropextradata:
        payload['nshttpprofile']['dropextradata'] = dropextradata

    if weblog:
        payload['nshttpprofile']['weblog'] = weblog

    if clientiphdrexpr:
        payload['nshttpprofile']['clientiphdrexpr'] = clientiphdrexpr

    if maxreq:
        payload['nshttpprofile']['maxreq'] = maxreq

    if persistentetag:
        payload['nshttpprofile']['persistentetag'] = persistentetag

    if spdy:
        payload['nshttpprofile']['spdy'] = spdy

    if http2:
        payload['nshttpprofile']['http2'] = http2

    if http2direct:
        payload['nshttpprofile']['http2direct'] = http2direct

    if altsvc:
        payload['nshttpprofile']['altsvc'] = altsvc

    if reusepooltimeout:
        payload['nshttpprofile']['reusepooltimeout'] = reusepooltimeout

    if maxheaderlen:
        payload['nshttpprofile']['maxheaderlen'] = maxheaderlen

    if minreusepool:
        payload['nshttpprofile']['minreusepool'] = minreusepool

    if http2maxheaderlistsize:
        payload['nshttpprofile']['http2maxheaderlistsize'] = http2maxheaderlistsize

    if http2maxframesize:
        payload['nshttpprofile']['http2maxframesize'] = http2maxframesize

    if http2maxconcurrentstreams:
        payload['nshttpprofile']['http2maxconcurrentstreams'] = http2maxconcurrentstreams

    if http2initialwindowsize:
        payload['nshttpprofile']['http2initialwindowsize'] = http2initialwindowsize

    if http2headertablesize:
        payload['nshttpprofile']['http2headertablesize'] = http2headertablesize

    if http2minseverconn:
        payload['nshttpprofile']['http2minseverconn'] = http2minseverconn

    if apdexcltresptimethreshold:
        payload['nshttpprofile']['apdexcltresptimethreshold'] = apdexcltresptimethreshold

    execution = __proxy__['citrixns.post']('config/nshttpprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsip(ipaddress=None, netmask=None, ns_type=None, arp=None, icmp=None, vserver=None, telnet=None, ftp=None,
             gui=None, ssh=None, snmp=None, mgmtaccess=None, restrictaccess=None, dynamicrouting=None, ospf=None,
             bgp=None, rip=None, hostroute=None, networkroute=None, tag=None, hostrtgw=None, metric=None,
             vserverrhilevel=None, vserverrhimode=None, ospflsatype=None, ospfarea=None, state=None, vrid=None,
             icmpresponse=None, ownernode=None, arpresponse=None, ownerdownresponse=None, td=None, save=False):
    '''
    Add a new nsip to the running configuration.

    ipaddress(str): IPv4 address to create on the NetScaler appliance. Cannot be changed after the IP address is created.
        Minimum length = 1

    netmask(str): Subnet mask associated with the IP address.

    ns_type(str): Type of the IP address to create on the NetScaler appliance. Cannot be changed after the IP address is
        created. The following are the different types of NetScaler owned IP addresses: * A Subnet IP (SNIP) address is
        used by the NetScaler ADC to communicate with the servers. The NetScaler also uses the subnet IP address when
        generating its own packets, such as packets related to dynamic routing protocols, or to send monitor probes to
        check the health of the servers. * A Virtual IP (VIP) address is the IP address associated with a virtual server.
        It is the IP address to which clients connect. An appliance managing a wide range of traffic may have many VIPs
        configured. Some of the attributes of the VIP address are customized to meet the requirements of the virtual
        server. * A GSLB site IP (GSLBIP) address is associated with a GSLB site. It is not mandatory to specify a GSLBIP
        address when you initially configure the NetScaler appliance. A GSLBIP address is used only when you create a
        GSLB site. * A Cluster IP (CLIP) address is the management address of the cluster. All cluster configurations
        must be performed by accessing the cluster through this IP address. Default value: SNIP Possible values = SNIP,
        VIP, NSIP, GSLBsiteIP, CLIP, LSN

    arp(str): Respond to ARP requests for this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    icmp(str): Respond to ICMP requests for this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    vserver(str): Use this option to set (enable or disable) the virtual server attribute for this IP address. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    telnet(str): Allow Telnet access to this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    ftp(str): Allow File Transfer Protocol (FTP) access to this IP address. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    gui(str): Allow graphical user interface (GUI) access to this IP address. Default value: ENABLED Possible values =
        ENABLED, SECUREONLY, DISABLED

    ssh(str): Allow secure shell (SSH) access to this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    snmp(str): Allow Simple Network Management Protocol (SNMP) access to this IP address. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    mgmtaccess(str): Allow access to management applications on this IP address. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    restrictaccess(str): Block access to nonmanagement applications on this IP. This option is applicable for MIPs, SNIPs,
        and NSIP, and is disabled by default. Nonmanagement applications can run on the underlying NetScaler Free BSD
        operating system. Default value: DISABLED Possible values = ENABLED, DISABLED

    dynamicrouting(str): Allow dynamic routing on this IP address. Specific to Subnet IP (SNIP) address. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    ospf(str): Use this option to enable or disable OSPF on this IP address for the entity. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    bgp(str): Use this option to enable or disable BGP on this IP address for the entity. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    rip(str): Use this option to enable or disable RIP on this IP address for the entity. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    hostroute(str): Option to push the VIP to ZebOS routing table for Kernel route redistribution through dynamic routing
        protocols. Possible values = ENABLED, DISABLED

    networkroute(str): Option to push the SNIP subnet to ZebOS routing table for Kernel route redistribution through dynamic
        routing protocol. Possible values = ENABLED, DISABLED

    tag(int): Tag value for the network/host route associated with this IP. Default value: 0

    hostrtgw(str): IP address of the gateway of the route for this VIP address. Default value: -1

    metric(int): Integer value to add to or subtract from the cost of the route advertised for the VIP address. Minimum value
        = -16777215

    vserverrhilevel(str): Advertise the route for the Virtual IP (VIP) address on the basis of the state of the virtual
        servers associated with that VIP. * NONE - Advertise the route for the VIP address, regardless of the state of
        the virtual servers associated with the address. * ONE VSERVER - Advertise the route for the VIP address if at
        least one of the associated virtual servers is in UP state. * ALL VSERVER - Advertise the route for the VIP
        address if all of the associated virtual servers are in UP state. * VSVR_CNTRLD - Advertise the route for the VIP
        address according to the RHIstate (RHI STATE) parameter setting on all the associated virtual servers of the VIP
        address along with their states.  When Vserver RHI Level (RHI) parameter is set to VSVR_CNTRLD, the following are
        different RHI behaviors for the VIP address on the basis of RHIstate (RHI STATE) settings on the virtual servers
        associated with the VIP address:  * If you set RHI STATE to PASSIVE on all virtual servers, the NetScaler ADC
        always advertises the route for the VIP address.  * If you set RHI STATE to ACTIVE on all virtual servers, the
        NetScaler ADC advertises the route for the VIP address if at least one of the associated virtual servers is in UP
        state.  *If you set RHI STATE to ACTIVE on some and PASSIVE on others, the NetScaler ADC advertises the route for
        the VIP address if at least one of the associated virtual servers, whose RHI STATE set to ACTIVE, is in UP state.
         Default value: ONE_VSERVER Possible values = ONE_VSERVER, ALL_VSERVERS, NONE, VSVR_CNTRLD

    vserverrhimode(str): Advertise the route for the Virtual IP (VIP) address using dynamic routing protocols or using RISE *
        DYNMAIC_ROUTING - Advertise the route for the VIP address using dynamic routing protocols (default) * RISE -
        Advertise the route for the VIP address using RISE. Default value: DYNAMIC_ROUTING Possible values =
        DYNAMIC_ROUTING, RISE

    ospflsatype(str): Type of LSAs to be used by the OSPF protocol, running on the NetScaler appliance, for advertising the
        route for this VIP address. Default value: TYPE5 Possible values = TYPE1, TYPE5

    ospfarea(int): ID of the area in which the type1 link-state advertisements (LSAs) are to be advertised for this virtual
        IP (VIP) address by the OSPF protocol running on the NetScaler appliance. When this parameter is not set, the VIP
        is advertised on all areas. Default value: -1 Minimum value = 0 Maximum value = 4294967294LU

    state(str): Enable or disable the IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    vrid(int): A positive integer that uniquely identifies a VMAC address for binding to this VIP address. This binding is
        used to set up NetScaler appliances in an active-active configuration using VRRP. Minimum value = 1 Maximum value
        = 255

    icmpresponse(str): Respond to ICMP requests for a Virtual IP (VIP) address on the basis of the states of the virtual
        servers associated with that VIP. Available settings function as follows: * NONE - The NetScaler appliance
        responds to any ICMP request for the VIP address, irrespective of the states of the virtual servers associated
        with the address. * ONE VSERVER - The NetScaler appliance responds to any ICMP request for the VIP address if at
        least one of the associated virtual servers is in UP state. * ALL VSERVER - The NetScaler appliance responds to
        any ICMP request for the VIP address if all of the associated virtual servers are in UP state. * VSVR_CNTRLD -
        The behavior depends on the ICMP VSERVER RESPONSE setting on all the associated virtual servers.  The following
        settings can be made for the ICMP VSERVER RESPONSE parameter on a virtual server: * If you set ICMP VSERVER
        RESPONSE to PASSIVE on all virtual servers, NetScaler always responds. * If you set ICMP VSERVER RESPONSE to
        ACTIVE on all virtual servers, NetScaler responds if even one virtual server is UP. * When you set ICMP VSERVER
        RESPONSE to ACTIVE on some and PASSIVE on others, NetScaler responds if even one virtual server set to ACTIVE is
        UP. Default value: 5 Possible values = NONE, ONE_VSERVER, ALL_VSERVERS, VSVR_CNTRLD

    ownernode(int): The owner node in a Cluster for this IP address. Owner node can vary from 0 to 31. If ownernode is not
        specified then the IP is treated as Striped IP. Default value: 255

    arpresponse(str): Respond to ARP requests for a Virtual IP (VIP) address on the basis of the states of the virtual
        servers associated with that VIP. Available settings function as follows:  * NONE - The NetScaler appliance
        responds to any ARP request for the VIP address, irrespective of the states of the virtual servers associated
        with the address. * ONE VSERVER - The NetScaler appliance responds to any ARP request for the VIP address if at
        least one of the associated virtual servers is in UP state. * ALL VSERVER - The NetScaler appliance responds to
        any ARP request for the VIP address if all of the associated virtual servers are in UP state. Default value: 5
        Possible values = NONE, ONE_VSERVER, ALL_VSERVERS

    ownerdownresponse(str): in cluster system, if the owner node is down, whether should it respond to icmp/arp. Default
        value: YES Possible values = YES, NO

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsip <args>

    '''

    result = {}

    payload = {'nsip': {}}

    if ipaddress:
        payload['nsip']['ipaddress'] = ipaddress

    if netmask:
        payload['nsip']['netmask'] = netmask

    if ns_type:
        payload['nsip']['type'] = ns_type

    if arp:
        payload['nsip']['arp'] = arp

    if icmp:
        payload['nsip']['icmp'] = icmp

    if vserver:
        payload['nsip']['vserver'] = vserver

    if telnet:
        payload['nsip']['telnet'] = telnet

    if ftp:
        payload['nsip']['ftp'] = ftp

    if gui:
        payload['nsip']['gui'] = gui

    if ssh:
        payload['nsip']['ssh'] = ssh

    if snmp:
        payload['nsip']['snmp'] = snmp

    if mgmtaccess:
        payload['nsip']['mgmtaccess'] = mgmtaccess

    if restrictaccess:
        payload['nsip']['restrictaccess'] = restrictaccess

    if dynamicrouting:
        payload['nsip']['dynamicrouting'] = dynamicrouting

    if ospf:
        payload['nsip']['ospf'] = ospf

    if bgp:
        payload['nsip']['bgp'] = bgp

    if rip:
        payload['nsip']['rip'] = rip

    if hostroute:
        payload['nsip']['hostroute'] = hostroute

    if networkroute:
        payload['nsip']['networkroute'] = networkroute

    if tag:
        payload['nsip']['tag'] = tag

    if hostrtgw:
        payload['nsip']['hostrtgw'] = hostrtgw

    if metric:
        payload['nsip']['metric'] = metric

    if vserverrhilevel:
        payload['nsip']['vserverrhilevel'] = vserverrhilevel

    if vserverrhimode:
        payload['nsip']['vserverrhimode'] = vserverrhimode

    if ospflsatype:
        payload['nsip']['ospflsatype'] = ospflsatype

    if ospfarea:
        payload['nsip']['ospfarea'] = ospfarea

    if state:
        payload['nsip']['state'] = state

    if vrid:
        payload['nsip']['vrid'] = vrid

    if icmpresponse:
        payload['nsip']['icmpresponse'] = icmpresponse

    if ownernode:
        payload['nsip']['ownernode'] = ownernode

    if arpresponse:
        payload['nsip']['arpresponse'] = arpresponse

    if ownerdownresponse:
        payload['nsip']['ownerdownresponse'] = ownerdownresponse

    if td:
        payload['nsip']['td'] = td

    execution = __proxy__['citrixns.post']('config/nsip', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsip6(ipv6address=None, scope=None, ns_type=None, vlan=None, nd=None, icmp=None, vserver=None, telnet=None,
              ftp=None, gui=None, ssh=None, snmp=None, mgmtaccess=None, restrictaccess=None, dynamicrouting=None,
              hostroute=None, networkroute=None, tag=None, ip6hostrtgw=None, metric=None, vserverrhilevel=None,
              ospf6lsatype=None, ospfarea=None, state=None, ns_map=None, vrid6=None, ownernode=None,
              ownerdownresponse=None, td=None, save=False):
    '''
    Add a new nsip6 to the running configuration.

    ipv6address(str): IPv6 address to create on the NetScaler appliance. Minimum length = 1

    scope(str): Scope of the IPv6 address to be created. Cannot be changed after the IP address is created. Default value:
        global Possible values = global, link-local

    ns_type(str): Type of IP address to be created on the NetScaler appliance. Cannot be changed after the IP address is
        created. Default value: SNIP Possible values = NSIP, VIP, SNIP, GSLBsiteIP, ADNSsvcIP, RADIUSListenersvcIP, CLIP

    vlan(int): The VLAN number. Default value: 0 Minimum value = 0 Maximum value = 4094

    nd(str): Respond to Neighbor Discovery (ND) requests for this IP address. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    icmp(str): Respond to ICMP requests for this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    vserver(str): Enable or disable the state of all the virtual servers associated with this VIP6 address. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    telnet(str): Allow Telnet access to this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    ftp(str): Allow File Transfer Protocol (FTP) access to this IP address. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    gui(str): Allow graphical user interface (GUI) access to this IP address. Default value: ENABLED Possible values =
        ENABLED, SECUREONLY, DISABLED

    ssh(str): Allow secure Shell (SSH) access to this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    snmp(str): Allow Simple Network Management Protocol (SNMP) access to this IP address. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    mgmtaccess(str): Allow access to management applications on this IP address. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    restrictaccess(str): Block access to nonmanagement applications on this IP address. This option is applicable forMIP6s,
        SNIP6s, and NSIP6s, and is disabled by default. Nonmanagement applications can run on the underlying NetScaler
        Free BSD operating system. Default value: DISABLED Possible values = ENABLED, DISABLED

    dynamicrouting(str): Allow dynamic routing on this IP address. Specific to Subnet IPv6 (SNIP6) address. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    hostroute(str): Option to push the VIP6 to ZebOS routing table for Kernel route redistribution through dynamic routing
        protocols. Possible values = ENABLED, DISABLED

    networkroute(str): Option to push the SNIP6 subnet to ZebOS routing table for Kernel route redistribution through dynamic
        routing protocol. Possible values = ENABLED, DISABLED

    tag(int): Tag value for the network/host route associated with this IP. Default value: 0

    ip6hostrtgw(str): IPv6 address of the gateway for the route. If Gateway is not set, VIP uses :: as the gateway. Default
        value: 0

    metric(int): Integer value to add to or subtract from the cost of the route advertised for the VIP6 address. Minimum
        value = -16777215

    vserverrhilevel(str): Advertise or do not advertise the route for the Virtual IP (VIP6) address on the basis of the state
        of the virtual servers associated with that VIP6. * NONE - Advertise the route for the VIP6 address, irrespective
        of the state of the virtual servers associated with the address. * ONE VSERVER - Advertise the route for the VIP6
        address if at least one of the associated virtual servers is in UP state. * ALL VSERVER - Advertise the route for
        the VIP6 address if all of the associated virtual servers are in UP state. * VSVR_CNTRLD. Advertise the route for
        the VIP address according to the RHIstate (RHI STATE) parameter setting on all the associated virtual servers of
        the VIP address along with their states.  When Vserver RHI Level (RHI) parameter is set to VSVR_CNTRLD, the
        following are different RHI behaviors for the VIP address on the basis of RHIstate (RHI STATE) settings on the
        virtual servers associated with the VIP address:  * If you set RHI STATE to PASSIVE on all virtual servers, the
        NetScaler ADC always advertises the route for the VIP address.  * If you set RHI STATE to ACTIVE on all virtual
        servers, the NetScaler ADC advertises the route for the VIP address if at least one of the associated virtual
        servers is in UP state.  *If you set RHI STATE to ACTIVE on some and PASSIVE on others, the NetScaler ADC
        advertises the route for the VIP address if at least one of the associated virtual servers, whose RHI STATE set
        to ACTIVE, is in UP state. Default value: ONE_VSERVER Possible values = ONE_VSERVER, ALL_VSERVERS, NONE,
        VSVR_CNTRLD

    ospf6lsatype(str): Type of LSAs to be used by the IPv6 OSPF protocol, running on the NetScaler appliance, for advertising
        the route for the VIP6 address. Default value: EXTERNAL Possible values = INTRA_AREA, EXTERNAL

    ospfarea(int): ID of the area in which the Intra-Area-Prefix LSAs are to be advertised for the VIP6 address by the IPv6
        OSPF protocol running on the NetScaler appliance. When ospfArea is not set, VIP6 is advertised on all areas.
        Default value: -1 Minimum value = 0 Maximum value = 4294967294LU

    state(str): Enable or disable the IP address. Default value: ENABLED Possible values = DISABLED, ENABLED

    ns_map(str): Mapped IPV4 address for the IPV6 address.

    vrid6(int): A positive integer that uniquely identifies a VMAC address for binding to this VIP address. This binding is
        used to set up NetScaler appliances in an active-active configuration using VRRP. Minimum value = 1 Maximum value
        = 255

    ownernode(int): ID of the cluster node for which you are adding the IP address. Must be used if you want the IP address
        to be active only on the specific node. Can be configured only through the cluster IP address. Cannot be changed
        after the IP address is created. Default value: 255

    ownerdownresponse(str): in cluster system, if the owner node is down, whether should it respond to icmp/arp. Default
        value: YES Possible values = YES, NO

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsip6 <args>

    '''

    result = {}

    payload = {'nsip6': {}}

    if ipv6address:
        payload['nsip6']['ipv6address'] = ipv6address

    if scope:
        payload['nsip6']['scope'] = scope

    if ns_type:
        payload['nsip6']['type'] = ns_type

    if vlan:
        payload['nsip6']['vlan'] = vlan

    if nd:
        payload['nsip6']['nd'] = nd

    if icmp:
        payload['nsip6']['icmp'] = icmp

    if vserver:
        payload['nsip6']['vserver'] = vserver

    if telnet:
        payload['nsip6']['telnet'] = telnet

    if ftp:
        payload['nsip6']['ftp'] = ftp

    if gui:
        payload['nsip6']['gui'] = gui

    if ssh:
        payload['nsip6']['ssh'] = ssh

    if snmp:
        payload['nsip6']['snmp'] = snmp

    if mgmtaccess:
        payload['nsip6']['mgmtaccess'] = mgmtaccess

    if restrictaccess:
        payload['nsip6']['restrictaccess'] = restrictaccess

    if dynamicrouting:
        payload['nsip6']['dynamicrouting'] = dynamicrouting

    if hostroute:
        payload['nsip6']['hostroute'] = hostroute

    if networkroute:
        payload['nsip6']['networkroute'] = networkroute

    if tag:
        payload['nsip6']['tag'] = tag

    if ip6hostrtgw:
        payload['nsip6']['ip6hostrtgw'] = ip6hostrtgw

    if metric:
        payload['nsip6']['metric'] = metric

    if vserverrhilevel:
        payload['nsip6']['vserverrhilevel'] = vserverrhilevel

    if ospf6lsatype:
        payload['nsip6']['ospf6lsatype'] = ospf6lsatype

    if ospfarea:
        payload['nsip6']['ospfarea'] = ospfarea

    if state:
        payload['nsip6']['state'] = state

    if ns_map:
        payload['nsip6']['map'] = ns_map

    if vrid6:
        payload['nsip6']['vrid6'] = vrid6

    if ownernode:
        payload['nsip6']['ownernode'] = ownernode

    if ownerdownresponse:
        payload['nsip6']['ownerdownresponse'] = ownerdownresponse

    if td:
        payload['nsip6']['td'] = td

    execution = __proxy__['citrixns.post']('config/nsip6', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nslicenseproxyserver(serverip=None, servername=None, port=None, save=False):
    '''
    Add a new nslicenseproxyserver to the running configuration.

    serverip(str): IP address of the License proxy server. Minimum length = 1

    servername(str): Fully qualified domain name of the License proxy server.

    port(int): License proxy server port.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nslicenseproxyserver <args>

    '''

    result = {}

    payload = {'nslicenseproxyserver': {}}

    if serverip:
        payload['nslicenseproxyserver']['serverip'] = serverip

    if servername:
        payload['nslicenseproxyserver']['servername'] = servername

    if port:
        payload['nslicenseproxyserver']['port'] = port

    execution = __proxy__['citrixns.post']('config/nslicenseproxyserver', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nslicenseserver(licenseserverip=None, servername=None, port=None, nodeid=None, save=False):
    '''
    Add a new nslicenseserver to the running configuration.

    licenseserverip(str): IP address of the License server. Minimum length = 1

    servername(str): Fully qualified domain name of the License server.

    port(int): License server port.

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nslicenseserver <args>

    '''

    result = {}

    payload = {'nslicenseserver': {}}

    if licenseserverip:
        payload['nslicenseserver']['licenseserverip'] = licenseserverip

    if servername:
        payload['nslicenseserver']['servername'] = servername

    if port:
        payload['nslicenseserver']['port'] = port

    if nodeid:
        payload['nslicenseserver']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/nslicenseserver', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nslimitidentifier(limitidentifier=None, threshold=None, timeslice=None, mode=None, limittype=None,
                          selectorname=None, maxbandwidth=None, trapsintimeslice=None, save=False):
    '''
    Add a new nslimitidentifier to the running configuration.

    limitidentifier(str): Name for a rate limit identifier. Must begin with an ASCII letter or underscore (_) character, and
        must consist only of ASCII alphanumeric or underscore characters. Reserved words must not be used.

    threshold(int): Maximum number of requests that are allowed in the given timeslice when requests (mode is set as
        REQUEST_RATE) are tracked per timeslice. When connections (mode is set as CONNECTION) are tracked, it is the
        total number of connections that would be let through. Default value: 1 Minimum value = 1

    timeslice(int): Time interval, in milliseconds, specified in multiples of 10, during which requests are tracked to check
        if they cross the threshold. This argument is needed only when the mode is set to REQUEST_RATE. Default value:
        1000 Minimum value = 10

    mode(str): Defines the type of traffic to be tracked. * REQUEST_RATE - Tracks requests/timeslice. * CONNECTION - Tracks
        active transactions.  Examples  1. To permit 20 requests in 10 ms and 2 traps in 10 ms: add limitidentifier
        limit_req -mode request_rate -limitType smooth -timeslice 1000 -Threshold 2000 -trapsInTimeSlice 200  2. To
        permit 50 requests in 10 ms: set limitidentifier limit_req -mode request_rate -timeslice 1000 -Threshold 5000
        -limitType smooth  3. To permit 1 request in 40 ms: set limitidentifier limit_req -mode request_rate -timeslice
        2000 -Threshold 50 -limitType smooth  4. To permit 1 request in 200 ms and 1 trap in 130 ms: set limitidentifier
        limit_req -mode request_rate -timeslice 1000 -Threshold 5 -limitType smooth -trapsInTimeSlice 8  5. To permit
        5000 requests in 1000 ms and 200 traps in 1000 ms: set limitidentifier limit_req -mode request_rate -timeslice
        1000 -Threshold 5000 -limitType BURSTY. Default value: REQUEST_RATE Possible values = CONNECTION, REQUEST_RATE,
        NONE

    limittype(str): Smooth or bursty request type. * SMOOTH - When you want the permitted number of requests in a given
        interval of time to be spread evenly across the timeslice * BURSTY - When you want the permitted number of
        requests to exhaust the quota anytime within the timeslice. This argument is needed only when the mode is set to
        REQUEST_RATE. Default value: BURSTY Possible values = BURSTY, SMOOTH

    selectorname(str): Name of the rate limit selector. If this argument is NULL, rate limiting will be applied on all
        traffic received by the virtual server or the NetScaler (depending on whether the limit identifier is bound to a
        virtual server or globally) without any filtering. Minimum length = 1

    maxbandwidth(int): Maximum bandwidth permitted, in kbps. Minimum value = 0 Maximum value = 4294967287

    trapsintimeslice(int): Number of traps to be sent in the timeslice configured. A value of 0 indicates that traps are
        disabled. Minimum value = 0 Maximum value = 65535

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nslimitidentifier <args>

    '''

    result = {}

    payload = {'nslimitidentifier': {}}

    if limitidentifier:
        payload['nslimitidentifier']['limitidentifier'] = limitidentifier

    if threshold:
        payload['nslimitidentifier']['threshold'] = threshold

    if timeslice:
        payload['nslimitidentifier']['timeslice'] = timeslice

    if mode:
        payload['nslimitidentifier']['mode'] = mode

    if limittype:
        payload['nslimitidentifier']['limittype'] = limittype

    if selectorname:
        payload['nslimitidentifier']['selectorname'] = selectorname

    if maxbandwidth:
        payload['nslimitidentifier']['maxbandwidth'] = maxbandwidth

    if trapsintimeslice:
        payload['nslimitidentifier']['trapsintimeslice'] = trapsintimeslice

    execution = __proxy__['citrixns.post']('config/nslimitidentifier', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nslimitselector(selectorname=None, rule=None, save=False):
    '''
    Add a new nslimitselector to the running configuration.

    selectorname(str): .

    rule(list(str)): . Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nslimitselector <args>

    '''

    result = {}

    payload = {'nslimitselector': {}}

    if selectorname:
        payload['nslimitselector']['selectorname'] = selectorname

    if rule:
        payload['nslimitselector']['rule'] = rule

    execution = __proxy__['citrixns.post']('config/nslimitselector', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nspartition(partitionname=None, maxbandwidth=None, minbandwidth=None, maxconn=None, maxmemlimit=None,
                    partitionmac=None, save=False):
    '''
    Add a new nspartition to the running configuration.

    partitionname(str): Name of the Partition. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Minimum length = 1

    maxbandwidth(int): Maximum bandwidth, in Kbps, that the partition can consume. A zero value indicates the bandwidth is
        unrestricted on the partition and it can consume up to the system limits. Default value: 10240

    minbandwidth(int): Minimum bandwidth, in Kbps, that the partition can consume. A zero value indicates the bandwidth is
        unrestricted on the partition and it can consume up to the system limits. Default value: 10240

    maxconn(int): Maximum number of concurrent connections that can be open in the partition. A zero value indicates no limit
        on number of open connections. Default value: 1024

    maxmemlimit(int): Maximum memory, in megabytes, allocated to the partition. A zero value indicates the memory is
        unlimited on the partition and it can consume up to the system limits. Default value: 10

    partitionmac(str): Special MAC address for the partition which is used for communication over shared vlans in this
        partition. If not specified, the MAC address is auto-generated.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nspartition <args>

    '''

    result = {}

    payload = {'nspartition': {}}

    if partitionname:
        payload['nspartition']['partitionname'] = partitionname

    if maxbandwidth:
        payload['nspartition']['maxbandwidth'] = maxbandwidth

    if minbandwidth:
        payload['nspartition']['minbandwidth'] = minbandwidth

    if maxconn:
        payload['nspartition']['maxconn'] = maxconn

    if maxmemlimit:
        payload['nspartition']['maxmemlimit'] = maxmemlimit

    if partitionmac:
        payload['nspartition']['partitionmac'] = partitionmac

    execution = __proxy__['citrixns.post']('config/nspartition', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nspartition_bridgegroup_binding(bridgegroup=None, partitionname=None, save=False):
    '''
    Add a new nspartition_bridgegroup_binding to the running configuration.

    bridgegroup(int): Identifier of the bridge group that is assigned to this partition. Minimum value = 1 Maximum value =
        1000

    partitionname(str): Name of the Partition. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nspartition_bridgegroup_binding <args>

    '''

    result = {}

    payload = {'nspartition_bridgegroup_binding': {}}

    if bridgegroup:
        payload['nspartition_bridgegroup_binding']['bridgegroup'] = bridgegroup

    if partitionname:
        payload['nspartition_bridgegroup_binding']['partitionname'] = partitionname

    execution = __proxy__['citrixns.post']('config/nspartition_bridgegroup_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nspartition_vlan_binding(vlan=None, partitionname=None, save=False):
    '''
    Add a new nspartition_vlan_binding to the running configuration.

    vlan(int): Identifier of the vlan that is assigned to this partition. Minimum value = 1 Maximum value = 4094

    partitionname(str): Name of the Partition. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nspartition_vlan_binding <args>

    '''

    result = {}

    payload = {'nspartition_vlan_binding': {}}

    if vlan:
        payload['nspartition_vlan_binding']['vlan'] = vlan

    if partitionname:
        payload['nspartition_vlan_binding']['partitionname'] = partitionname

    execution = __proxy__['citrixns.post']('config/nspartition_vlan_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nspartition_vxlan_binding(partitionname=None, save=False):
    '''
    Add a new nspartition_vxlan_binding to the running configuration.

    partitionname(str): Name of the Partition. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nspartition_vxlan_binding <args>

    '''

    result = {}

    payload = {'nspartition_vxlan_binding': {}}

    if partitionname:
        payload['nspartition_vxlan_binding']['partitionname'] = partitionname

    execution = __proxy__['citrixns.post']('config/nspartition_vxlan_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nspbr(name=None, action=None, td=None, srcip=None, srcipop=None, srcipval=None, srcport=None, srcportop=None,
              srcportval=None, destip=None, destipop=None, destipval=None, destport=None, destportop=None,
              destportval=None, nexthop=None, nexthopval=None, iptunnel=None, iptunnelname=None, vxlanvlanmap=None,
              srcmac=None, srcmacmask=None, protocol=None, protocolnumber=None, vlan=None, vxlan=None, interface=None,
              priority=None, msr=None, monitor=None, state=None, ownergroup=None, detail=None, save=False):
    '''
    Add a new nspbr to the running configuration.

    name(str): Name for the PBR. Must begin with an ASCII alphabetic or underscore \\(_\\) character, and must contain only
        ASCII alphanumeric, underscore, hash \\(\\#\\), period \\(.\\), space, colon \\(:\\), at \\(@\\), equals \\(=\\),
        and hyphen \\(-\\) characters. Cannot be changed after the PBR is created. Minimum length = 1

    action(str): Action to perform on the outgoing IPv4 packets that match the PBR.  Available settings function as follows:
        * ALLOW - The NetScaler appliance sends the packet to the designated next-hop router. * DENY - The NetScaler
        appliance applies the routing table for normal destination-based routing. Possible values = ALLOW, DENY

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcip(bool): IP address or range of IP addresses to match against the source IP address of an outgoing IPv4 packet. In
        the command line interface, separate the range with a hyphen. For example: 10.102.29.30-10.102.29.189.

    srcipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcipval(str): IP address or range of IP addresses to match against the source IP address of an outgoing IPv4 packet. In
        the command line interface, separate the range with a hyphen. For example: 10.102.29.30-10.102.29.189.

    srcport(bool): Port number or range of port numbers to match against the source port number of an outgoing IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The destination port
        can be specified only for TCP and UDP protocols.

    srcportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcportval(str): Port number or range of port numbers to match against the source port number of an outgoing IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The destination port
        can be specified only for TCP and UDP protocols. Maximum length = 65535

    destip(bool): IP address or range of IP addresses to match against the destination IP address of an outgoing IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 10.102.29.30-10.102.29.189.

    destipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destipval(str): IP address or range of IP addresses to match against the destination IP address of an outgoing IPv4
        packet. In the command line interface, separate the range with a hyphen. For example:
        10.102.29.30-10.102.29.189.

    destport(bool): Port number or range of port numbers to match against the destination port number of an outgoing IPv4
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols.

    destportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destportval(str): Port number or range of port numbers to match against the destination port number of an outgoing IPv4
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols. Maximum length = 65535

    nexthop(bool): IP address of the next hop router or the name of the link load balancing virtual server to which to send
        matching packets if action is set to ALLOW. If you specify a link load balancing (LLB) virtual server, which can
        provide a backup if a next hop link fails, first make sure that the next hops bound to the LLB virtual server are
        actually next hops that are directly connected to the NetScaler appliance. Otherwise, the NetScaler throws an
        error when you attempt to create the PBR. The next hop can be null to represent null routes.

    nexthopval(str): The Next Hop IP address or gateway name.

    iptunnel(bool): The Tunnel name.

    iptunnelname(str): The iptunnel name where packets need to be forwarded upon.

    vxlanvlanmap(str): The vlan to vxlan mapping to be applied for incoming packets over this pbr tunnel.

    srcmac(str): MAC address to match against the source MAC address of an outgoing IPv4 packet.

    srcmacmask(str): Used to define range of Source MAC address. It takes string of 0 and 1, 0s are for exact match and 1s
        for wildcard. For matching first 3 bytes of MAC address, srcMacMask value "000000111111". . Default value:
        "000000000000"

    protocol(str): Protocol, identified by protocol name, to match against the protocol of an outgoing IPv4 packet. Possible
        values = ICMP, IGMP, TCP, EGP, IGP, ARGUS, UDP, RDP, RSVP, EIGRP, L2TP, ISIS

    protocolnumber(int): Protocol, identified by protocol number, to match against the protocol of an outgoing IPv4 packet.
        Minimum value = 1 Maximum value = 255

    vlan(int): ID of the VLAN. The NetScaler appliance compares the PBR only to the outgoing packets on the specified VLAN.
        If you do not specify any interface ID, the appliance compares the PBR to the outgoing packets on all VLANs.
        Minimum value = 1 Maximum value = 4094

    vxlan(int): ID of the VXLAN. The NetScaler appliance compares the PBR only to the outgoing packets on the specified
        VXLAN. If you do not specify any interface ID, the appliance compares the PBR to the outgoing packets on all
        VXLANs. Minimum value = 1 Maximum value = 16777215

    interface(str): ID of an interface. The NetScaler appliance compares the PBR only to the outgoing packets on the
        specified interface. If you do not specify any value, the appliance compares the PBR to the outgoing packets on
        all interfaces.

    priority(int): Priority of the PBR, which determines the order in which it is evaluated relative to the other PBRs. If
        you do not specify priorities while creating PBRs, the PBRs are evaluated in the order in which they are created.
        Minimum value = 1 Maximum value = 81920

    msr(str): Monitor the route specified byte Next Hop parameter. This parameter is not applicable if you specify a link
        load balancing (LLB) virtual server name with the Next Hop parameter. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    monitor(str): The name of the monitor.(Can be only of type ping or ARP ). Minimum length = 1

    state(str): Enable or disable the PBR. After you apply the PBRs, the NetScaler appliance compares outgoing packets to the
        enabled PBRs. Default value: ENABLED Possible values = ENABLED, DISABLED

    ownergroup(str): The owner node group in a Cluster for this pbr rule. If ownernode is not specified then the pbr rule is
        treated as Striped pbr rule. Default value: DEFAULT_NG Minimum length = 1

    detail(bool): To get a detailed view.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nspbr <args>

    '''

    result = {}

    payload = {'nspbr': {}}

    if name:
        payload['nspbr']['name'] = name

    if action:
        payload['nspbr']['action'] = action

    if td:
        payload['nspbr']['td'] = td

    if srcip:
        payload['nspbr']['srcip'] = srcip

    if srcipop:
        payload['nspbr']['srcipop'] = srcipop

    if srcipval:
        payload['nspbr']['srcipval'] = srcipval

    if srcport:
        payload['nspbr']['srcport'] = srcport

    if srcportop:
        payload['nspbr']['srcportop'] = srcportop

    if srcportval:
        payload['nspbr']['srcportval'] = srcportval

    if destip:
        payload['nspbr']['destip'] = destip

    if destipop:
        payload['nspbr']['destipop'] = destipop

    if destipval:
        payload['nspbr']['destipval'] = destipval

    if destport:
        payload['nspbr']['destport'] = destport

    if destportop:
        payload['nspbr']['destportop'] = destportop

    if destportval:
        payload['nspbr']['destportval'] = destportval

    if nexthop:
        payload['nspbr']['nexthop'] = nexthop

    if nexthopval:
        payload['nspbr']['nexthopval'] = nexthopval

    if iptunnel:
        payload['nspbr']['iptunnel'] = iptunnel

    if iptunnelname:
        payload['nspbr']['iptunnelname'] = iptunnelname

    if vxlanvlanmap:
        payload['nspbr']['vxlanvlanmap'] = vxlanvlanmap

    if srcmac:
        payload['nspbr']['srcmac'] = srcmac

    if srcmacmask:
        payload['nspbr']['srcmacmask'] = srcmacmask

    if protocol:
        payload['nspbr']['protocol'] = protocol

    if protocolnumber:
        payload['nspbr']['protocolnumber'] = protocolnumber

    if vlan:
        payload['nspbr']['vlan'] = vlan

    if vxlan:
        payload['nspbr']['vxlan'] = vxlan

    if interface:
        payload['nspbr']['Interface'] = interface

    if priority:
        payload['nspbr']['priority'] = priority

    if msr:
        payload['nspbr']['msr'] = msr

    if monitor:
        payload['nspbr']['monitor'] = monitor

    if state:
        payload['nspbr']['state'] = state

    if ownergroup:
        payload['nspbr']['ownergroup'] = ownergroup

    if detail:
        payload['nspbr']['detail'] = detail

    execution = __proxy__['citrixns.post']('config/nspbr', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nspbr6(name=None, td=None, action=None, srcipv6=None, srcipop=None, srcipv6val=None, srcport=None,
               srcportop=None, srcportval=None, destipv6=None, destipop=None, destipv6val=None, destport=None,
               destportop=None, destportval=None, srcmac=None, srcmacmask=None, protocol=None, protocolnumber=None,
               vlan=None, vxlan=None, interface=None, priority=None, state=None, msr=None, monitor=None, nexthop=None,
               nexthopval=None, iptunnel=None, vxlanvlanmap=None, nexthopvlan=None, ownergroup=None, detail=None,
               save=False):
    '''
    Add a new nspbr6 to the running configuration.

    name(str): Name for the PBR6. Must begin with an ASCII alphabetic or underscore \\(_\\) character, and must contain only
        ASCII alphanumeric, underscore, hash \\(\\#\\), period \\(.\\), space, colon \\(:\\), at \\(@\\), equals \\(=\\),
        and hyphen \\(-\\) characters. Cannot be changed after the PBR6 is created. Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    action(str): Action to perform on the outgoing IPv6 packets that match the PBR6.  Available settings function as follows:
        * ALLOW - The NetScaler appliance sends the packet to the designated next-hop router. * DENY - The NetScaler
        appliance applies the routing table for normal destination-based routing. Possible values = ALLOW, DENY

    srcipv6(bool): IP address or range of IP addresses to match against the source IP address of an outgoing IPv6 packet. In
        the command line interface, separate the range with a hyphen.

    srcipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcipv6val(str): IP address or range of IP addresses to match against the source IP address of an outgoing IPv6 packet.
        In the command line interface, separate the range with a hyphen.

    srcport(bool): Port number or range of port numbers to match against the source port number of an outgoing IPv6 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90.

    srcportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcportval(str): Source port (range). Maximum length = 65535

    destipv6(bool): IP address or range of IP addresses to match against the destination IP address of an outgoing IPv6
        packet. In the command line interface, separate the range with a hyphen.

    destipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destipv6val(str): IP address or range of IP addresses to match against the destination IP address of an outgoing IPv6
        packet. In the command line interface, separate the range with a hyphen.

    destport(bool): Port number or range of port numbers to match against the destination port number of an outgoing IPv6
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols.

    destportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destportval(str): Destination port (range). Maximum length = 65535

    srcmac(str): MAC address to match against the source MAC address of an outgoing IPv6 packet.

    srcmacmask(str): Used to define range of Source MAC address. It takes string of 0 and 1, 0s are for exact match and 1s
        for wildcard. For matching first 3 bytes of MAC address, srcMacMask value "000000111111". . Default value:
        "000000000000"

    protocol(str): Protocol, identified by protocol name, to match against the protocol of an outgoing IPv6 packet. Possible
        values = ICMPV6, TCP, UDP

    protocolnumber(int): Protocol, identified by protocol number, to match against the protocol of an outgoing IPv6 packet.
        Minimum value = 1 Maximum value = 255

    vlan(int): ID of the VLAN. The NetScaler appliance compares the PBR6 only to the outgoing packets on the specified VLAN.
        If you do not specify an interface ID, the appliance compares the PBR6 to the outgoing packets on all VLANs.
        Minimum value = 1 Maximum value = 4094

    vxlan(int): ID of the VXLAN. The NetScaler appliance compares the PBR6 only to the outgoing packets on the specified
        VXLAN. If you do not specify an interface ID, the appliance compares the PBR6 to the outgoing packets on all
        VXLANs. Minimum value = 1 Maximum value = 16777215

    interface(str): ID of an interface. The NetScaler appliance compares the PBR6 only to the outgoing packets on the
        specified interface. If you do not specify a value, the appliance compares the PBR6 to the outgoing packets on
        all interfaces.

    priority(int): Priority of the PBR6, which determines the order in which it is evaluated relative to the other PBR6s. If
        you do not specify priorities while creating PBR6s, the PBR6s are evaluated in the order in which they are
        created. Minimum value = 1 Maximum value = 81920

    state(str): Enable or disable the PBR6. After you apply the PBR6s, the NetScaler appliance compares outgoing packets to
        the enabled PBR6s. Default value: ENABLED Possible values = ENABLED, DISABLED

    msr(str): Monitor the route specified by the Next Hop parameter. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    monitor(str): The name of the monitor.(Can be only of type ping or ARP ). Minimum length = 1

    nexthop(bool): IP address of the next hop router to which to send matching packets if action is set to ALLOW. This next
        hop should be directly reachable from the appliance.

    nexthopval(str): The Next Hop IPv6 address.

    iptunnel(str): The iptunnel name where packets need to be forwarded upon.

    vxlanvlanmap(str): The vlan to vxlan mapping to be applied for incoming packets over this pbr tunnel.

    nexthopvlan(int): VLAN number to be used for link local nexthop . Minimum value = 1 Maximum value = 4094

    ownergroup(str): The owner node group in a Cluster for this pbr rule. If owner node group is not specified then the pbr
        rule is treated as Striped pbr rule. Default value: DEFAULT_NG Minimum length = 1

    detail(bool): To get a detailed view.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nspbr6 <args>

    '''

    result = {}

    payload = {'nspbr6': {}}

    if name:
        payload['nspbr6']['name'] = name

    if td:
        payload['nspbr6']['td'] = td

    if action:
        payload['nspbr6']['action'] = action

    if srcipv6:
        payload['nspbr6']['srcipv6'] = srcipv6

    if srcipop:
        payload['nspbr6']['srcipop'] = srcipop

    if srcipv6val:
        payload['nspbr6']['srcipv6val'] = srcipv6val

    if srcport:
        payload['nspbr6']['srcport'] = srcport

    if srcportop:
        payload['nspbr6']['srcportop'] = srcportop

    if srcportval:
        payload['nspbr6']['srcportval'] = srcportval

    if destipv6:
        payload['nspbr6']['destipv6'] = destipv6

    if destipop:
        payload['nspbr6']['destipop'] = destipop

    if destipv6val:
        payload['nspbr6']['destipv6val'] = destipv6val

    if destport:
        payload['nspbr6']['destport'] = destport

    if destportop:
        payload['nspbr6']['destportop'] = destportop

    if destportval:
        payload['nspbr6']['destportval'] = destportval

    if srcmac:
        payload['nspbr6']['srcmac'] = srcmac

    if srcmacmask:
        payload['nspbr6']['srcmacmask'] = srcmacmask

    if protocol:
        payload['nspbr6']['protocol'] = protocol

    if protocolnumber:
        payload['nspbr6']['protocolnumber'] = protocolnumber

    if vlan:
        payload['nspbr6']['vlan'] = vlan

    if vxlan:
        payload['nspbr6']['vxlan'] = vxlan

    if interface:
        payload['nspbr6']['Interface'] = interface

    if priority:
        payload['nspbr6']['priority'] = priority

    if state:
        payload['nspbr6']['state'] = state

    if msr:
        payload['nspbr6']['msr'] = msr

    if monitor:
        payload['nspbr6']['monitor'] = monitor

    if nexthop:
        payload['nspbr6']['nexthop'] = nexthop

    if nexthopval:
        payload['nspbr6']['nexthopval'] = nexthopval

    if iptunnel:
        payload['nspbr6']['iptunnel'] = iptunnel

    if vxlanvlanmap:
        payload['nspbr6']['vxlanvlanmap'] = vxlanvlanmap

    if nexthopvlan:
        payload['nspbr6']['nexthopvlan'] = nexthopvlan

    if ownergroup:
        payload['nspbr6']['ownergroup'] = ownergroup

    if detail:
        payload['nspbr6']['detail'] = detail

    execution = __proxy__['citrixns.post']('config/nspbr6', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsservicefunction(servicefunctionname=None, ingressvlan=None, save=False):
    '''
    Add a new nsservicefunction to the running configuration.

    servicefunctionname(str): Name of the service function to be created. Leading character must be a number or letter. Other
        characters allowed, after the first character, are @ _ - . (period) : (colon) # and space ( ). Minimum length =
        1

    ingressvlan(int): VLAN ID on which the traffic from service function reaches Netscaler. Minimum value = 1 Maximum value =
        4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsservicefunction <args>

    '''

    result = {}

    payload = {'nsservicefunction': {}}

    if servicefunctionname:
        payload['nsservicefunction']['servicefunctionname'] = servicefunctionname

    if ingressvlan:
        payload['nsservicefunction']['ingressvlan'] = ingressvlan

    execution = __proxy__['citrixns.post']('config/nsservicefunction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsservicepath(servicepathname=None, save=False):
    '''
    Add a new nsservicepath to the running configuration.

    servicepathname(str): Name for the Service path. Must begin with an ASCII alphanumeric or underscore (_) character, and
        must  contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=),
        and hyphen (-)  characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsservicepath <args>

    '''

    result = {}

    payload = {'nsservicepath': {}}

    if servicepathname:
        payload['nsservicepath']['servicepathname'] = servicepathname

    execution = __proxy__['citrixns.post']('config/nsservicepath', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsservicepath_nsservicefunction_binding(servicepathname=None, save=False):
    '''
    Add a new nsservicepath_nsservicefunction_binding to the running configuration.

    servicepathname(str): Name for the Service path. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsservicepath_nsservicefunction_binding <args>

    '''

    result = {}

    payload = {'nsservicepath_nsservicefunction_binding': {}}

    if servicepathname:
        payload['nsservicepath_nsservicefunction_binding']['servicepathname'] = servicepathname

    execution = __proxy__['citrixns.post']('config/nsservicepath_nsservicefunction_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nssimpleacl(aclname=None, aclaction=None, td=None, srcip=None, destport=None, protocol=None, ttl=None,
                    estsessions=None, save=False):
    '''
    Add a new nssimpleacl to the running configuration.

    aclname(str): Name for the simple ACL rule. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the simple ACL rule is created. Minimum length = 1

    aclaction(str): Drop incoming IPv4 packets that match the simple ACL rule. Possible values = DENY

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcip(str): IP address to match against the source IP address of an incoming IPv4 packet.

    destport(int): Port number to match against the destination port number of an incoming IPv4 packet.  DestPort is
        mandatory while setting Protocol. Omitting the port number and protocol creates an all-ports and all protocols
        simple ACL rule, which matches any port and any protocol. In that case, you cannot create another simple ACL rule
        specifying a specific port and the same source IPv4 address. Minimum value = 1 Maximum value = 65535

    protocol(str): Protocol to match against the protocol of an incoming IPv4 packet. You must set this parameter if you have
        set the Destination Port parameter. Possible values = TCP, UDP

    ttl(int): Number of seconds, in multiples of four, after which the simple ACL rule expires. If you do not want the simple
        ACL rule to expire, do not specify a TTL value. Minimum value = 4 Maximum value = 2147483647

    estsessions(bool): .

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nssimpleacl <args>

    '''

    result = {}

    payload = {'nssimpleacl': {}}

    if aclname:
        payload['nssimpleacl']['aclname'] = aclname

    if aclaction:
        payload['nssimpleacl']['aclaction'] = aclaction

    if td:
        payload['nssimpleacl']['td'] = td

    if srcip:
        payload['nssimpleacl']['srcip'] = srcip

    if destport:
        payload['nssimpleacl']['destport'] = destport

    if protocol:
        payload['nssimpleacl']['protocol'] = protocol

    if ttl:
        payload['nssimpleacl']['ttl'] = ttl

    if estsessions:
        payload['nssimpleacl']['estsessions'] = estsessions

    execution = __proxy__['citrixns.post']('config/nssimpleacl', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nssimpleacl6(aclname=None, td=None, aclaction=None, srcipv6=None, destport=None, protocol=None, ttl=None,
                     estsessions=None, save=False):
    '''
    Add a new nssimpleacl6 to the running configuration.

    aclname(str): Name for the simple ACL6 rule. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the simple ACL6 rule is created. Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    aclaction(str): Drop incoming IPv6 packets that match the simple ACL6 rule. Possible values = DENY

    srcipv6(str): IP address to match against the source IP address of an incoming IPv6 packet.

    destport(int): Port number to match against the destination port number of an incoming IPv6 packet.  DestPort is
        mandatory while setting Protocol. Omitting the port number and protocol creates an all-ports and all protocol
        simple ACL6 rule, which matches any port and any protocol. In that case, you cannot create another simple ACL6
        rule specifying a specific port and the same source IPv6 address. Minimum value = 1 Maximum value = 65535

    protocol(str): Protocol to match against the protocol of an incoming IPv6 packet. You must set this parameter if you set
        the Destination Port parameter. Possible values = TCP, UDP

    ttl(int): Number of seconds, in multiples of four, after which the simple ACL6 rule expires. If you do not want the
        simple ACL6 rule to expire, do not specify a TTL value. Minimum value = 4 Maximum value = 2147483647

    estsessions(bool): .

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nssimpleacl6 <args>

    '''

    result = {}

    payload = {'nssimpleacl6': {}}

    if aclname:
        payload['nssimpleacl6']['aclname'] = aclname

    if td:
        payload['nssimpleacl6']['td'] = td

    if aclaction:
        payload['nssimpleacl6']['aclaction'] = aclaction

    if srcipv6:
        payload['nssimpleacl6']['srcipv6'] = srcipv6

    if destport:
        payload['nssimpleacl6']['destport'] = destport

    if protocol:
        payload['nssimpleacl6']['protocol'] = protocol

    if ttl:
        payload['nssimpleacl6']['ttl'] = ttl

    if estsessions:
        payload['nssimpleacl6']['estsessions'] = estsessions

    execution = __proxy__['citrixns.post']('config/nssimpleacl6', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nstcpprofile(name=None, ws=None, sack=None, wsval=None, nagle=None, ackonpush=None, mss=None, maxburst=None,
                     initialcwnd=None, delayedack=None, oooqsize=None, maxpktpermss=None, pktperretx=None, minrto=None,
                     slowstartincr=None, buffersize=None, syncookie=None, kaprobeupdatelastactivity=None, flavor=None,
                     dynamicreceivebuffering=None, ka=None, kaconnidletime=None, kamaxprobes=None, kaprobeinterval=None,
                     sendbuffsize=None, mptcp=None, establishclientconn=None, tcpsegoffload=None,
                     rstwindowattenuate=None, rstmaxack=None, spoofsyndrop=None, ecn=None, mptcpdropdataonpreestsf=None,
                     mptcpfastopen=None, mptcpsessiontimeout=None, timestamp=None, dsack=None, ackaggregation=None,
                     frto=None, maxcwnd=None, fack=None, tcpmode=None, tcpfastopen=None, hystart=None, dupackthresh=None,
                     burstratecontrol=None, tcprate=None, rateqmax=None, drophalfclosedconnontimeout=None,
                     dropestconnontimeout=None, save=False):
    '''
    Add a new nstcpprofile to the running configuration.

    name(str): Name for a TCP profile. Must begin with a letter, number, or the underscore \\(_\\) character. Other
        characters allowed, after the first character, are the hyphen \\(-\\), period \\(.\\), hash \\(\\#\\), space \\(
        \\), at \\(@\\), colon \\(:\\), and equal \\(=\\) characters. The name of a TCP profile cannot be changed after
        it is created.  CLI Users: If the name includes one or more spaces, enclose the name in double or single
        quotation marks \\(for example, "my tcp profile" or my tcp profile\\). Minimum length = 1 Maximum length = 127

    ws(str): Enable or disable window scaling. Default value: DISABLED Possible values = ENABLED, DISABLED

    sack(str): Enable or disable Selective ACKnowledgement (SACK). Default value: DISABLED Possible values = ENABLED,
        DISABLED

    wsval(int): Factor used to calculate the new window size. This argument is needed only when window scaling is enabled.
        Default value: 4 Minimum value = 0 Maximum value = 14

    nagle(str): Enable or disable the Nagle algorithm on TCP connections. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    ackonpush(str): Send immediate positive acknowledgement (ACK) on receipt of TCP packets with PUSH flag. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    mss(int): Maximum number of octets to allow in a TCP data segment. Minimum value = 0 Maximum value = 9176

    maxburst(int): Maximum number of TCP segments allowed in a burst. Default value: 6 Minimum value = 1 Maximum value = 255

    initialcwnd(int): Initial maximum upper limit on the number of TCP packets that can be outstanding on the TCP link to the
        server. Default value: 4 Minimum value = 1 Maximum value = 44

    delayedack(int): Timeout for TCP delayed ACK, in milliseconds. Default value: 100 Minimum value = 10 Maximum value = 300

    oooqsize(int): Maximum size of out-of-order packets queue. A value of 0 means no limit. Default value: 64 Minimum value =
        0 Maximum value = 65535

    maxpktpermss(int): Maximum number of TCP packets allowed per maximum segment size (MSS). Minimum value = 0 Maximum value
        = 1460

    pktperretx(int): Maximum limit on the number of packets that should be retransmitted on receiving a partial ACK. Default
        value: 1 Minimum value = 1 Maximum value = 512

    minrto(int): Minimum retransmission timeout, in milliseconds, specified in 10-millisecond increments (value must yield a
        whole number if divided by 10). Default value: 1000 Minimum value = 10 Maximum value = 64000

    slowstartincr(int): Multiplier that determines the rate at which slow start increases the size of the TCP transmission
        window after each acknowledgement of successful transmission. Default value: 2 Minimum value = 1 Maximum value =
        100

    buffersize(int): TCP buffering size, in bytes. Default value: 8190 Minimum value = 8190 Maximum value = 20971520

    syncookie(str): Enable or disable the SYNCOOKIE mechanism for TCP handshake with clients. Disabling SYNCOOKIE prevents
        SYN attack protection on the NetScaler appliance. Default value: ENABLED Possible values = ENABLED, DISABLED

    kaprobeupdatelastactivity(str): Update last activity for the connection after receiving keep-alive (KA) probes. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    flavor(str): Set TCP congestion control algorithm. Default value: Default Possible values = Default, Westwood, BIC,
        CUBIC, Nile

    dynamicreceivebuffering(str): Enable or disable dynamic receive buffering. When enabled, allows the receive buffer to be
        adjusted dynamically based on memory and network conditions. Note: The buffer size argument must be set for
        dynamic adjustments to take place. Default value: DISABLED Possible values = ENABLED, DISABLED

    ka(str): Send periodic TCP keep-alive (KA) probes to check if peer is still up. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    kaconnidletime(int): Duration, in seconds, for the connection to be idle, before sending a keep-alive (KA) probe. Minimum
        value = 1 Maximum value = 4095

    kamaxprobes(int): Number of keep-alive (KA) probes to be sent when not acknowledged, before assuming the peer to be down.
        Minimum value = 1 Maximum value = 254

    kaprobeinterval(int): Time interval, in seconds, before the next keep-alive (KA) probe, if the peer does not respond.
        Minimum value = 1 Maximum value = 4095

    sendbuffsize(int): TCP Send Buffer Size. Default value: 8190 Minimum value = 8190 Maximum value = 20971520

    mptcp(str): Enable or disable Multipath TCP. Default value: DISABLED Possible values = ENABLED, DISABLED

    establishclientconn(str): Establishing Client Client connection on First data/ Final-ACK / Automatic. Default value:
        AUTOMATIC Possible values = AUTOMATIC, CONN_ESTABLISHED, ON_FIRST_DATA

    tcpsegoffload(str): Offload TCP segmentation to the NIC. If set to AUTOMATIC, TCP segmentation will be offloaded to the
        NIC, if the NIC supports it. Default value: AUTOMATIC Possible values = AUTOMATIC, DISABLED

    rstwindowattenuate(str): Enable or disable RST window attenuation to protect against spoofing. When enabled, will reply
        with corrective ACK when a sequence number is invalid. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    rstmaxack(str): Enable or disable acceptance of RST that is out of window yet echoes highest ACK sequence number. Useful
        only in proxy mode. Default value: DISABLED Possible values = ENABLED, DISABLED

    spoofsyndrop(str): Enable or disable drop of invalid SYN packets to protect against spoofing. When disabled, established
        connections will be reset when a SYN packet is received. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    ecn(str): Enable or disable TCP Explicit Congestion Notification. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    mptcpdropdataonpreestsf(str): Enable or disable silently dropping the data on Pre-Established subflow. When enabled, DSS
        data packets are dropped silently instead of dropping the connection when data is received on pre established
        subflow. Default value: DISABLED Possible values = ENABLED, DISABLED

    mptcpfastopen(str): Enable or disable Multipath TCP fastopen. When enabled, DSS data packets are accepted before
        receiving the third ack of SYN handshake. Default value: DISABLED Possible values = ENABLED, DISABLED

    mptcpsessiontimeout(int): MPTCP session timeout in seconds. If this value is not set, idle MPTCP sessions are flushed
        after vservers client idle timeout. Default value: 0 Minimum value = 0 Maximum value = 86400

    timestamp(str): Enable or Disable TCP Timestamp option (RFC 1323). Default value: DISABLED Possible values = ENABLED,
        DISABLED

    dsack(str): Enable or disable DSACK. Default value: ENABLED Possible values = ENABLED, DISABLED

    ackaggregation(str): Enable or disable ACK Aggregation. Default value: DISABLED Possible values = ENABLED, DISABLED

    frto(str): Enable or disable FRTO (Forward RTO-Recovery). Default value: DISABLED Possible values = ENABLED, DISABLED

    maxcwnd(int): TCP Maximum Congestion Window. Default value: 524288 Minimum value = 8190 Maximum value = 20971520

    fack(str): Enable or disable FACK (Forward ACK). Default value: DISABLED Possible values = ENABLED, DISABLED

    tcpmode(str): TCP Optimization modes TRANSPARENT / ENDPOINT. Default value: TRANSPARENT Possible values = TRANSPARENT,
        ENDPOINT

    tcpfastopen(str): Enable or disable TCP Fastopen. When enabled, NS can receive or send Data in SYN or SYN-ACK packets.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    hystart(str): Enable or disable CUBIC Hystart. Default value: DISABLED Possible values = ENABLED, DISABLED

    dupackthresh(int): TCP dupack threshold. Default value: 3 Minimum value = 1 Maximum value = 15

    burstratecontrol(str): TCP Burst Rate Control DISABLED/FIXED/DYNAMIC. FIXED requires a TCP rate to be set. Default value:
        DISABLED Possible values = DISABLED, FIXED, DYNAMIC

    tcprate(int): TCP connection payload send rate in Kb/s. Default value: 0 Minimum value = 0 Maximum value = 10000000

    rateqmax(int): Maximum connection queue size in bytes, when BurstRateControl is used. Default value: 0 Minimum value = 0
        Maximum value = 1000000000

    drophalfclosedconnontimeout(str): Silently drop tcp half closed connections on idle timeout. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    dropestconnontimeout(str): Silently drop tcp established connections on idle timeout. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nstcpprofile <args>

    '''

    result = {}

    payload = {'nstcpprofile': {}}

    if name:
        payload['nstcpprofile']['name'] = name

    if ws:
        payload['nstcpprofile']['ws'] = ws

    if sack:
        payload['nstcpprofile']['sack'] = sack

    if wsval:
        payload['nstcpprofile']['wsval'] = wsval

    if nagle:
        payload['nstcpprofile']['nagle'] = nagle

    if ackonpush:
        payload['nstcpprofile']['ackonpush'] = ackonpush

    if mss:
        payload['nstcpprofile']['mss'] = mss

    if maxburst:
        payload['nstcpprofile']['maxburst'] = maxburst

    if initialcwnd:
        payload['nstcpprofile']['initialcwnd'] = initialcwnd

    if delayedack:
        payload['nstcpprofile']['delayedack'] = delayedack

    if oooqsize:
        payload['nstcpprofile']['oooqsize'] = oooqsize

    if maxpktpermss:
        payload['nstcpprofile']['maxpktpermss'] = maxpktpermss

    if pktperretx:
        payload['nstcpprofile']['pktperretx'] = pktperretx

    if minrto:
        payload['nstcpprofile']['minrto'] = minrto

    if slowstartincr:
        payload['nstcpprofile']['slowstartincr'] = slowstartincr

    if buffersize:
        payload['nstcpprofile']['buffersize'] = buffersize

    if syncookie:
        payload['nstcpprofile']['syncookie'] = syncookie

    if kaprobeupdatelastactivity:
        payload['nstcpprofile']['kaprobeupdatelastactivity'] = kaprobeupdatelastactivity

    if flavor:
        payload['nstcpprofile']['flavor'] = flavor

    if dynamicreceivebuffering:
        payload['nstcpprofile']['dynamicreceivebuffering'] = dynamicreceivebuffering

    if ka:
        payload['nstcpprofile']['ka'] = ka

    if kaconnidletime:
        payload['nstcpprofile']['kaconnidletime'] = kaconnidletime

    if kamaxprobes:
        payload['nstcpprofile']['kamaxprobes'] = kamaxprobes

    if kaprobeinterval:
        payload['nstcpprofile']['kaprobeinterval'] = kaprobeinterval

    if sendbuffsize:
        payload['nstcpprofile']['sendbuffsize'] = sendbuffsize

    if mptcp:
        payload['nstcpprofile']['mptcp'] = mptcp

    if establishclientconn:
        payload['nstcpprofile']['establishclientconn'] = establishclientconn

    if tcpsegoffload:
        payload['nstcpprofile']['tcpsegoffload'] = tcpsegoffload

    if rstwindowattenuate:
        payload['nstcpprofile']['rstwindowattenuate'] = rstwindowattenuate

    if rstmaxack:
        payload['nstcpprofile']['rstmaxack'] = rstmaxack

    if spoofsyndrop:
        payload['nstcpprofile']['spoofsyndrop'] = spoofsyndrop

    if ecn:
        payload['nstcpprofile']['ecn'] = ecn

    if mptcpdropdataonpreestsf:
        payload['nstcpprofile']['mptcpdropdataonpreestsf'] = mptcpdropdataonpreestsf

    if mptcpfastopen:
        payload['nstcpprofile']['mptcpfastopen'] = mptcpfastopen

    if mptcpsessiontimeout:
        payload['nstcpprofile']['mptcpsessiontimeout'] = mptcpsessiontimeout

    if timestamp:
        payload['nstcpprofile']['timestamp'] = timestamp

    if dsack:
        payload['nstcpprofile']['dsack'] = dsack

    if ackaggregation:
        payload['nstcpprofile']['ackaggregation'] = ackaggregation

    if frto:
        payload['nstcpprofile']['frto'] = frto

    if maxcwnd:
        payload['nstcpprofile']['maxcwnd'] = maxcwnd

    if fack:
        payload['nstcpprofile']['fack'] = fack

    if tcpmode:
        payload['nstcpprofile']['tcpmode'] = tcpmode

    if tcpfastopen:
        payload['nstcpprofile']['tcpfastopen'] = tcpfastopen

    if hystart:
        payload['nstcpprofile']['hystart'] = hystart

    if dupackthresh:
        payload['nstcpprofile']['dupackthresh'] = dupackthresh

    if burstratecontrol:
        payload['nstcpprofile']['burstratecontrol'] = burstratecontrol

    if tcprate:
        payload['nstcpprofile']['tcprate'] = tcprate

    if rateqmax:
        payload['nstcpprofile']['rateqmax'] = rateqmax

    if drophalfclosedconnontimeout:
        payload['nstcpprofile']['drophalfclosedconnontimeout'] = drophalfclosedconnontimeout

    if dropestconnontimeout:
        payload['nstcpprofile']['dropestconnontimeout'] = dropestconnontimeout

    execution = __proxy__['citrixns.post']('config/nstcpprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nstimer(name=None, interval=None, unit=None, comment=None, newname=None, save=False):
    '''
    Add a new nstimer to the running configuration.

    name(str): Timer name. Minimum length = 1

    interval(int): The frequency at which the policies bound to this timer are invoked. The minimum value is 20 msec. The
        maximum value is 20940 in seconds and 349 in minutes. Default value: 5 Minimum value = 1 Maximum value =
        20940000

    unit(str): Timer interval unit. Default value: SEC Possible values = SEC, MIN

    comment(str): Comments associated with this timer.

    newname(str): The new name of the timer. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nstimer <args>

    '''

    result = {}

    payload = {'nstimer': {}}

    if name:
        payload['nstimer']['name'] = name

    if interval:
        payload['nstimer']['interval'] = interval

    if unit:
        payload['nstimer']['unit'] = unit

    if comment:
        payload['nstimer']['comment'] = comment

    if newname:
        payload['nstimer']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/nstimer', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nstimer_autoscalepolicy_binding(priority=None, gotopriorityexpression=None, policyname=None, name=None,
                                        threshold=None, samplesize=None, vserver=None, save=False):
    '''
    Add a new nstimer_autoscalepolicy_binding to the running configuration.

    priority(int): Specifies the priority of the timer policy.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policyname(str): The timer policy associated with the timer.

    name(str): Timer name. Minimum length = 1

    threshold(int): Denotes the threshold. If the rule of the policy in the binding relation evaluates threshold size number
        of times in sample size to true, then the corresponding action is taken. Its value needs to be less than or equal
        to the sample size value. Default value: 3 Minimum value = 1 Maximum value = 32

    samplesize(int): Denotes the sample size. Sample size value of x means that previous (x - 1) policys rule evaluation
        results and the current evaluation result are present with the binding. For example, sample size of 10 means that
        there is a state of previous 9 policy evaluation results and also the current policy evaluation result. Default
        value: 3 Minimum value = 1 Maximum value = 32

    vserver(str): Name of the vserver which provides the context for the rule in timer policy. When not specified it is
        treated as a Global Default context.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nstimer_autoscalepolicy_binding <args>

    '''

    result = {}

    payload = {'nstimer_autoscalepolicy_binding': {}}

    if priority:
        payload['nstimer_autoscalepolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['nstimer_autoscalepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policyname:
        payload['nstimer_autoscalepolicy_binding']['policyname'] = policyname

    if name:
        payload['nstimer_autoscalepolicy_binding']['name'] = name

    if threshold:
        payload['nstimer_autoscalepolicy_binding']['threshold'] = threshold

    if samplesize:
        payload['nstimer_autoscalepolicy_binding']['samplesize'] = samplesize

    if vserver:
        payload['nstimer_autoscalepolicy_binding']['vserver'] = vserver

    execution = __proxy__['citrixns.post']('config/nstimer_autoscalepolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nstrafficdomain(td=None, aliasname=None, vmac=None, save=False):
    '''
    Add a new nstrafficdomain to the running configuration.

    td(int): Integer value that uniquely identifies a traffic domain. Minimum value = 1 Maximum value = 4094

    aliasname(str): Name of traffic domain being added. Minimum length = 1 Maximum length = 31

    vmac(str): Associate the traffic domain with a VMAC address instead of with VLANs. The NetScaler ADC then sends the VMAC
        address of the traffic domain in all responses to ARP queries for network entities in that domain. As a result,
        the ADC can segregate subsequent incoming traffic for this traffic domain on the basis of the destination MAC
        address, because the destination MAC address is the VMAC address of the traffic domain. After creating entities
        on a traffic domain, you can easily manage and monitor them by performing traffic domain level operations.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nstrafficdomain <args>

    '''

    result = {}

    payload = {'nstrafficdomain': {}}

    if td:
        payload['nstrafficdomain']['td'] = td

    if aliasname:
        payload['nstrafficdomain']['aliasname'] = aliasname

    if vmac:
        payload['nstrafficdomain']['vmac'] = vmac

    execution = __proxy__['citrixns.post']('config/nstrafficdomain', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nstrafficdomain_bridgegroup_binding(bridgegroup=None, td=None, save=False):
    '''
    Add a new nstrafficdomain_bridgegroup_binding to the running configuration.

    bridgegroup(int): ID of the configured bridge to bind to this traffic domain. More than one bridge group can be bound to
        a traffic domain, but the same bridge group cannot be a part of multiple traffic domains. Minimum value = 1
        Maximum value = 1000

    td(int): Integer value that uniquely identifies a traffic domain. Minimum value = 1 Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nstrafficdomain_bridgegroup_binding <args>

    '''

    result = {}

    payload = {'nstrafficdomain_bridgegroup_binding': {}}

    if bridgegroup:
        payload['nstrafficdomain_bridgegroup_binding']['bridgegroup'] = bridgegroup

    if td:
        payload['nstrafficdomain_bridgegroup_binding']['td'] = td

    execution = __proxy__['citrixns.post']('config/nstrafficdomain_bridgegroup_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nstrafficdomain_vlan_binding(vlan=None, td=None, save=False):
    '''
    Add a new nstrafficdomain_vlan_binding to the running configuration.

    vlan(int): ID of the VLAN to bind to this traffic domain. More than one VLAN can be bound to a traffic domain, but the
        same VLAN cannot be a part of multiple traffic domains. Minimum value = 1 Maximum value = 4094

    td(int): Integer value that uniquely identifies a traffic domain. Minimum value = 1 Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nstrafficdomain_vlan_binding <args>

    '''

    result = {}

    payload = {'nstrafficdomain_vlan_binding': {}}

    if vlan:
        payload['nstrafficdomain_vlan_binding']['vlan'] = vlan

    if td:
        payload['nstrafficdomain_vlan_binding']['td'] = td

    execution = __proxy__['citrixns.post']('config/nstrafficdomain_vlan_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nstrafficdomain_vxlan_binding(td=None, vxlan=None, save=False):
    '''
    Add a new nstrafficdomain_vxlan_binding to the running configuration.

    td(int): Integer value that uniquely identifies a traffic domain. Minimum value = 1 Maximum value = 4094

    vxlan(int): ID of the VXLAN to bind to this traffic domain. More than one VXLAN can be bound to a traffic domain, but the
        same VXLAN cannot be a part of multiple traffic domains. Minimum value = 1 Maximum value = 16777215

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nstrafficdomain_vxlan_binding <args>

    '''

    result = {}

    payload = {'nstrafficdomain_vxlan_binding': {}}

    if td:
        payload['nstrafficdomain_vxlan_binding']['td'] = td

    if vxlan:
        payload['nstrafficdomain_vxlan_binding']['vxlan'] = vxlan

    execution = __proxy__['citrixns.post']('config/nstrafficdomain_vxlan_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsvariable(name=None, ns_type=None, scope=None, iffull=None, ifvaluetoobig=None, ifnovalue=None, init=None,
                   expires=None, comment=None, save=False):
    '''
    Add a new nsvariable to the running configuration.

    name(str): Variable name. This follows the same syntax rules as other default syntax expression entity names:  It must
        begin with an alpha character (A-Z or a-z) or an underscore (_).  The rest of the characters must be alpha,
        numeric (0-9) or underscores.  It cannot be re or xp (reserved for regular and XPath expressions).  It cannot be
        a default syntax expression reserved word (e.g. SYS or HTTP).  It cannot be used for an existing default syntax
        expression object (HTTP callout, patset, dataset, stringmap, or named expression). Minimum length = 1

    ns_type(str): Specification of the variable type; one of the following:  ulong - singleton variable with an unsigned
        64-bit value.  text(value-max-size) - singleton variable with a text string value.
        map(text(key-max-size),ulong,max-entries) - map of text string keys to unsigned 64-bit values.
        map(text(key-max-size),text(value-max-size),max-entries) - map of text string keys to text string values. where
        value-max-size is a positive integer that is the maximum number of bytes in a text string value.  key-max-size is
        a positive integer that is the maximum number of bytes in a text string key.  max-entries is a positive integer
        that is the maximum number of entries in a map variable.  For a global singleton text variable, value-max-size
        ;lt;= 64000.  For a global map with ulong values, key-max-size ;lt;= 64000.  For a global map with text values,
        key-max-size + value-max-size ;lt;= 64000.  max-entries is a positive integer that is the maximum number of
        entries in a map variable. This has a theoretical maximum of 2^64-1, but in actual use will be much smaller,
        considering the memory available for use by the map. Example:  map(text(10),text(20),100) specifies a map of text
        string keys (max size 10 bytes) to text string values (max size 20 bytes), with 100 max entries. Minimum length =
        1

    scope(str): Scope of the variable:  global - (default) one set of values visible across all Packet Engines and, in a
        cluster, all nodes  transaction - one value for each request-response transaction (singleton variables only; no
        expiration). Default value: global Possible values = global, transaction

    iffull(str): Action to perform if an assignment to a map exceeds its configured max-entries:  lru - (default) reuse the
        least recently used entry in the map.  undef - force the assignment to return an undefined (Undef) result to the
        policy executing the assignment. Default value: lru Possible values = undef, lru

    ifvaluetoobig(str): Action to perform if an value is assigned to a text variable that exceeds its configured max-size, or
        if a key is used that exceeds its configured max-size:  truncate - (default) truncate the text string to the
        first max-size bytes and proceed.  undef - force the assignment or expression evaluation to return an undefined
        (Undef) result to the policy executing the assignment or expression. Default value: truncate Possible values =
        undef, truncate

    ifnovalue(str): Action to perform if on a variable reference in an expression if the variable is single-valued and
        uninitialized or if the variable is a map and there is no value for the specified key:  init - (default)
        initialize the single-value variable, or create a map entry for the key and the initial value, using the -init
        value or its default.  undef - force the expression evaluation to return an undefined (Undef) result to the
        policy executing the expression. Default value: init Possible values = undef, init

    init(str): Initialization value for values in this variable. Default: 0 for ulong, NULL for text.

    expires(int): Value expiration in seconds. If the value is not referenced within the expiration period it will be
        deleted. 0 (the default) means no expiration. Minimum value = 0 Maximum value = 31622400

    comment(str): Comments associated with this variable.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsvariable <args>

    '''

    result = {}

    payload = {'nsvariable': {}}

    if name:
        payload['nsvariable']['name'] = name

    if ns_type:
        payload['nsvariable']['type'] = ns_type

    if scope:
        payload['nsvariable']['scope'] = scope

    if iffull:
        payload['nsvariable']['iffull'] = iffull

    if ifvaluetoobig:
        payload['nsvariable']['ifvaluetoobig'] = ifvaluetoobig

    if ifnovalue:
        payload['nsvariable']['ifnovalue'] = ifnovalue

    if init:
        payload['nsvariable']['init'] = init

    if expires:
        payload['nsvariable']['expires'] = expires

    if comment:
        payload['nsvariable']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/nsvariable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_nsxmlnamespace(prefix=None, namespace=None, description=None, save=False):
    '''
    Add a new nsxmlnamespace to the running configuration.

    prefix(str): XML prefix. Minimum length = 1

    namespace(str): Expanded namespace for which the XML prefix is provided. Minimum length = 1

    description(str): Description for the prefix. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.add_nsxmlnamespace <args>

    '''

    result = {}

    payload = {'nsxmlnamespace': {}}

    if prefix:
        payload['nsxmlnamespace']['prefix'] = prefix

    if namespace:
        payload['nsxmlnamespace']['Namespace'] = namespace

    if description:
        payload['nsxmlnamespace']['description'] = description

    execution = __proxy__['citrixns.post']('config/nsxmlnamespace', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_nsacl(aclname=None, save=False):
    '''
    Disables a nsacl matching the specified filter.

    aclname(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.disable_nsacl aclname=foo

    '''

    result = {}

    payload = {'nsacl': {}}

    if aclname:
        payload['nsacl']['aclname'] = aclname
    else:
        result['result'] = 'False'
        result['error'] = 'aclname value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nsacl?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_nsacl6(acl6name=None, save=False):
    '''
    Disables a nsacl6 matching the specified filter.

    acl6name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.disable_nsacl6 acl6name=foo

    '''

    result = {}

    payload = {'nsacl6': {}}

    if acl6name:
        payload['nsacl6']['acl6name'] = acl6name
    else:
        result['result'] = 'False'
        result['error'] = 'acl6name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nsacl6?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_nsfeature(feature=None, save=False):
    '''
    Disables a nsfeature matching the specified filter.

    feature(list(str)): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.disable_nsfeature feature=foo

    '''

    result = {}

    payload = {'nsfeature': {}}

    if feature:
        payload['nsfeature']['feature'] = feature
    else:
        result['result'] = 'False'
        result['error'] = 'feature value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nsfeature?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_nsip(ipaddress=None, save=False):
    '''
    Disables a nsip matching the specified filter.

    ipaddress(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.disable_nsip ipaddress=foo

    '''

    result = {}

    payload = {'nsip': {}}

    if ipaddress:
        payload['nsip']['ipaddress'] = ipaddress
    else:
        result['result'] = 'False'
        result['error'] = 'ipaddress value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nsip?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_nsmode(mode=None, save=False):
    '''
    Disables a nsmode matching the specified filter.

    mode(list(str)): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.disable_nsmode mode=foo

    '''

    result = {}

    payload = {'nsmode': {}}

    if mode:
        payload['nsmode']['mode'] = mode
    else:
        result['result'] = 'False'
        result['error'] = 'mode value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nsmode?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_nspbr(name=None, save=False):
    '''
    Disables a nspbr matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.disable_nspbr name=foo

    '''

    result = {}

    payload = {'nspbr': {}}

    if name:
        payload['nspbr']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nspbr?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_nspbr6(name=None, save=False):
    '''
    Disables a nspbr6 matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.disable_nspbr6 name=foo

    '''

    result = {}

    payload = {'nspbr6': {}}

    if name:
        payload['nspbr6']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nspbr6?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_nstrafficdomain(td=None, save=False):
    '''
    Disables a nstrafficdomain matching the specified filter.

    td(int): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.disable_nstrafficdomain td=foo

    '''

    result = {}

    payload = {'nstrafficdomain': {}}

    if td:
        payload['nstrafficdomain']['td'] = td
    else:
        result['result'] = 'False'
        result['error'] = 'td value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nstrafficdomain?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_nsacl(aclname=None, save=False):
    '''
    Enables a nsacl matching the specified filter.

    aclname(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.enable_nsacl aclname=foo

    '''

    result = {}

    payload = {'nsacl': {}}

    if aclname:
        payload['nsacl']['aclname'] = aclname
    else:
        result['result'] = 'False'
        result['error'] = 'aclname value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nsacl?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_nsacl6(acl6name=None, save=False):
    '''
    Enables a nsacl6 matching the specified filter.

    acl6name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.enable_nsacl6 acl6name=foo

    '''

    result = {}

    payload = {'nsacl6': {}}

    if acl6name:
        payload['nsacl6']['acl6name'] = acl6name
    else:
        result['result'] = 'False'
        result['error'] = 'acl6name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nsacl6?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_nsfeature(feature=None, save=False):
    '''
    Enables a nsfeature matching the specified filter.

    feature(list(str)): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.enable_nsfeature feature=foo

    '''

    result = {}

    payload = {'nsfeature': {}}

    if feature:
        payload['nsfeature']['feature'] = feature
    else:
        result['result'] = 'False'
        result['error'] = 'feature value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nsfeature?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_nsip(ipaddress=None, save=False):
    '''
    Enables a nsip matching the specified filter.

    ipaddress(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.enable_nsip ipaddress=foo

    '''

    result = {}

    payload = {'nsip': {}}

    if ipaddress:
        payload['nsip']['ipaddress'] = ipaddress
    else:
        result['result'] = 'False'
        result['error'] = 'ipaddress value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nsip?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_nsmode(mode=None, save=False):
    '''
    Enables a nsmode matching the specified filter.

    mode(list(str)): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.enable_nsmode mode=foo

    '''

    result = {}

    payload = {'nsmode': {}}

    if mode:
        payload['nsmode']['mode'] = mode
    else:
        result['result'] = 'False'
        result['error'] = 'mode value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nsmode?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_nspbr(name=None, save=False):
    '''
    Enables a nspbr matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.enable_nspbr name=foo

    '''

    result = {}

    payload = {'nspbr': {}}

    if name:
        payload['nspbr']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nspbr?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_nspbr6(name=None, save=False):
    '''
    Enables a nspbr6 matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.enable_nspbr6 name=foo

    '''

    result = {}

    payload = {'nspbr6': {}}

    if name:
        payload['nspbr6']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nspbr6?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_nstrafficdomain(td=None, save=False):
    '''
    Enables a nstrafficdomain matching the specified filter.

    td(int): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.enable_nstrafficdomain td=foo

    '''

    result = {}

    payload = {'nstrafficdomain': {}}

    if td:
        payload['nstrafficdomain']['td'] = td
    else:
        result['result'] = 'False'
        result['error'] = 'td value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/nstrafficdomain?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_nsacl(aclname=None, aclaction=None, td=None, srcip=None, srcipop=None, srcipval=None, srcport=None,
              srcportop=None, srcportval=None, destip=None, destipop=None, destipval=None, destport=None,
              destportop=None, destportval=None, ttl=None, srcmac=None, srcmacmask=None, protocol=None,
              protocolnumber=None, vlan=None, vxlan=None, interface=None, established=None, icmptype=None, icmpcode=None,
              priority=None, state=None, logstate=None, ratelimit=None, newname=None):
    '''
    Show the running configuration for the nsacl config key.

    aclname(str): Filters results that only match the aclname field.

    aclaction(str): Filters results that only match the aclaction field.

    td(int): Filters results that only match the td field.

    srcip(bool): Filters results that only match the srcip field.

    srcipop(str): Filters results that only match the srcipop field.

    srcipval(str): Filters results that only match the srcipval field.

    srcport(bool): Filters results that only match the srcport field.

    srcportop(str): Filters results that only match the srcportop field.

    srcportval(str): Filters results that only match the srcportval field.

    destip(bool): Filters results that only match the destip field.

    destipop(str): Filters results that only match the destipop field.

    destipval(str): Filters results that only match the destipval field.

    destport(bool): Filters results that only match the destport field.

    destportop(str): Filters results that only match the destportop field.

    destportval(str): Filters results that only match the destportval field.

    ttl(int): Filters results that only match the ttl field.

    srcmac(str): Filters results that only match the srcmac field.

    srcmacmask(str): Filters results that only match the srcmacmask field.

    protocol(str): Filters results that only match the protocol field.

    protocolnumber(int): Filters results that only match the protocolnumber field.

    vlan(int): Filters results that only match the vlan field.

    vxlan(int): Filters results that only match the vxlan field.

    interface(str): Filters results that only match the Interface field.

    established(bool): Filters results that only match the established field.

    icmptype(int): Filters results that only match the icmptype field.

    icmpcode(int): Filters results that only match the icmpcode field.

    priority(int): Filters results that only match the priority field.

    state(str): Filters results that only match the state field.

    logstate(str): Filters results that only match the logstate field.

    ratelimit(int): Filters results that only match the ratelimit field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsacl

    '''

    search_filter = []

    if aclname:
        search_filter.append(['aclname', aclname])

    if aclaction:
        search_filter.append(['aclaction', aclaction])

    if td:
        search_filter.append(['td', td])

    if srcip:
        search_filter.append(['srcip', srcip])

    if srcipop:
        search_filter.append(['srcipop', srcipop])

    if srcipval:
        search_filter.append(['srcipval', srcipval])

    if srcport:
        search_filter.append(['srcport', srcport])

    if srcportop:
        search_filter.append(['srcportop', srcportop])

    if srcportval:
        search_filter.append(['srcportval', srcportval])

    if destip:
        search_filter.append(['destip', destip])

    if destipop:
        search_filter.append(['destipop', destipop])

    if destipval:
        search_filter.append(['destipval', destipval])

    if destport:
        search_filter.append(['destport', destport])

    if destportop:
        search_filter.append(['destportop', destportop])

    if destportval:
        search_filter.append(['destportval', destportval])

    if ttl:
        search_filter.append(['ttl', ttl])

    if srcmac:
        search_filter.append(['srcmac', srcmac])

    if srcmacmask:
        search_filter.append(['srcmacmask', srcmacmask])

    if protocol:
        search_filter.append(['protocol', protocol])

    if protocolnumber:
        search_filter.append(['protocolnumber', protocolnumber])

    if vlan:
        search_filter.append(['vlan', vlan])

    if vxlan:
        search_filter.append(['vxlan', vxlan])

    if interface:
        search_filter.append(['Interface', interface])

    if established:
        search_filter.append(['established', established])

    if icmptype:
        search_filter.append(['icmptype', icmptype])

    if icmpcode:
        search_filter.append(['icmpcode', icmpcode])

    if priority:
        search_filter.append(['priority', priority])

    if state:
        search_filter.append(['state', state])

    if logstate:
        search_filter.append(['logstate', logstate])

    if ratelimit:
        search_filter.append(['ratelimit', ratelimit])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsacl{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsacl')

    return response


def get_nsacl6(acl6name=None, acl6action=None, td=None, srcipv6=None, srcipop=None, srcipv6val=None, srcport=None,
               srcportop=None, srcportval=None, destipv6=None, destipop=None, destipv6val=None, destport=None,
               destportop=None, destportval=None, ttl=None, srcmac=None, srcmacmask=None, protocol=None,
               protocolnumber=None, vlan=None, vxlan=None, interface=None, established=None, icmptype=None,
               icmpcode=None, priority=None, state=None, aclaction=None, newname=None):
    '''
    Show the running configuration for the nsacl6 config key.

    acl6name(str): Filters results that only match the acl6name field.

    acl6action(str): Filters results that only match the acl6action field.

    td(int): Filters results that only match the td field.

    srcipv6(bool): Filters results that only match the srcipv6 field.

    srcipop(str): Filters results that only match the srcipop field.

    srcipv6val(str): Filters results that only match the srcipv6val field.

    srcport(bool): Filters results that only match the srcport field.

    srcportop(str): Filters results that only match the srcportop field.

    srcportval(str): Filters results that only match the srcportval field.

    destipv6(bool): Filters results that only match the destipv6 field.

    destipop(str): Filters results that only match the destipop field.

    destipv6val(str): Filters results that only match the destipv6val field.

    destport(bool): Filters results that only match the destport field.

    destportop(str): Filters results that only match the destportop field.

    destportval(str): Filters results that only match the destportval field.

    ttl(int): Filters results that only match the ttl field.

    srcmac(str): Filters results that only match the srcmac field.

    srcmacmask(str): Filters results that only match the srcmacmask field.

    protocol(str): Filters results that only match the protocol field.

    protocolnumber(int): Filters results that only match the protocolnumber field.

    vlan(int): Filters results that only match the vlan field.

    vxlan(int): Filters results that only match the vxlan field.

    interface(str): Filters results that only match the Interface field.

    established(bool): Filters results that only match the established field.

    icmptype(int): Filters results that only match the icmptype field.

    icmpcode(int): Filters results that only match the icmpcode field.

    priority(int): Filters results that only match the priority field.

    state(str): Filters results that only match the state field.

    aclaction(str): Filters results that only match the aclaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsacl6

    '''

    search_filter = []

    if acl6name:
        search_filter.append(['acl6name', acl6name])

    if acl6action:
        search_filter.append(['acl6action', acl6action])

    if td:
        search_filter.append(['td', td])

    if srcipv6:
        search_filter.append(['srcipv6', srcipv6])

    if srcipop:
        search_filter.append(['srcipop', srcipop])

    if srcipv6val:
        search_filter.append(['srcipv6val', srcipv6val])

    if srcport:
        search_filter.append(['srcport', srcport])

    if srcportop:
        search_filter.append(['srcportop', srcportop])

    if srcportval:
        search_filter.append(['srcportval', srcportval])

    if destipv6:
        search_filter.append(['destipv6', destipv6])

    if destipop:
        search_filter.append(['destipop', destipop])

    if destipv6val:
        search_filter.append(['destipv6val', destipv6val])

    if destport:
        search_filter.append(['destport', destport])

    if destportop:
        search_filter.append(['destportop', destportop])

    if destportval:
        search_filter.append(['destportval', destportval])

    if ttl:
        search_filter.append(['ttl', ttl])

    if srcmac:
        search_filter.append(['srcmac', srcmac])

    if srcmacmask:
        search_filter.append(['srcmacmask', srcmacmask])

    if protocol:
        search_filter.append(['protocol', protocol])

    if protocolnumber:
        search_filter.append(['protocolnumber', protocolnumber])

    if vlan:
        search_filter.append(['vlan', vlan])

    if vxlan:
        search_filter.append(['vxlan', vxlan])

    if interface:
        search_filter.append(['Interface', interface])

    if established:
        search_filter.append(['established', established])

    if icmptype:
        search_filter.append(['icmptype', icmptype])

    if icmpcode:
        search_filter.append(['icmpcode', icmpcode])

    if priority:
        search_filter.append(['priority', priority])

    if state:
        search_filter.append(['state', state])

    if aclaction:
        search_filter.append(['aclaction', aclaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsacl6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsacl6')

    return response


def get_nsappflowcollector(name=None, ipaddress=None, port=None):
    '''
    Show the running configuration for the nsappflowcollector config key.

    name(str): Filters results that only match the name field.

    ipaddress(str): Filters results that only match the ipaddress field.

    port(int): Filters results that only match the port field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsappflowcollector

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if port:
        search_filter.append(['port', port])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsappflowcollector{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsappflowcollector')

    return response


def get_nsappflowparam():
    '''
    Show the running configuration for the nsappflowparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsappflowparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsappflowparam'), 'nsappflowparam')

    return response


def get_nsaptlicense():
    '''
    Show the running configuration for the nsaptlicense config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsaptlicense

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsaptlicense'), 'nsaptlicense')

    return response


def get_nsassignment(name=None, variable=None, ns_set=None, add=None, sub=None, append=None, clear=None, comment=None,
                     newname=None):
    '''
    Show the running configuration for the nsassignment config key.

    name(str): Filters results that only match the name field.

    variable(str): Filters results that only match the variable field.

    ns_set(str): Filters results that only match the set field.

    add(str): Filters results that only match the Add field.

    sub(str): Filters results that only match the sub field.

    append(str): Filters results that only match the append field.

    clear(bool): Filters results that only match the clear field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsassignment

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if variable:
        search_filter.append(['variable', variable])

    if ns_set:
        search_filter.append(['set', ns_set])

    if add:
        search_filter.append(['Add', add])

    if sub:
        search_filter.append(['sub', sub])

    if append:
        search_filter.append(['append', append])

    if clear:
        search_filter.append(['clear', clear])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsassignment{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsassignment')

    return response


def get_nscapacity():
    '''
    Show the running configuration for the nscapacity config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nscapacity

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nscapacity'), 'nscapacity')

    return response


def get_nscentralmanagementserver(ns_type=None, username=None, password=None, ipaddress=None, servername=None):
    '''
    Show the running configuration for the nscentralmanagementserver config key.

    ns_type(str): Filters results that only match the type field.

    username(str): Filters results that only match the username field.

    password(str): Filters results that only match the password field.

    ipaddress(str): Filters results that only match the ipaddress field.

    servername(str): Filters results that only match the servername field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nscentralmanagementserver

    '''

    search_filter = []

    if ns_type:
        search_filter.append(['type', ns_type])

    if username:
        search_filter.append(['username', username])

    if password:
        search_filter.append(['password', password])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if servername:
        search_filter.append(['servername', servername])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nscentralmanagementserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nscentralmanagementserver')

    return response


def get_nsconfig():
    '''
    Show the running configuration for the nsconfig config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsconfig

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsconfig'), 'nsconfig')

    return response


def get_nsconnectiontable(filterexpression=None, link=None, filtername=None, detail=None, listen=None, nodeid=None):
    '''
    Show the running configuration for the nsconnectiontable config key.

    filterexpression(str): Filters results that only match the filterexpression field.

    link(bool): Filters results that only match the link field.

    filtername(bool): Filters results that only match the filtername field.

    detail(list(str)): Filters results that only match the detail field.

    listen(bool): Filters results that only match the listen field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsconnectiontable

    '''

    search_filter = []

    if filterexpression:
        search_filter.append(['filterexpression', filterexpression])

    if link:
        search_filter.append(['link', link])

    if filtername:
        search_filter.append(['filtername', filtername])

    if detail:
        search_filter.append(['detail', detail])

    if listen:
        search_filter.append(['listen', listen])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsconnectiontable{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsconnectiontable')

    return response


def get_nsconsoleloginprompt():
    '''
    Show the running configuration for the nsconsoleloginprompt config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsconsoleloginprompt

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsconsoleloginprompt'), 'nsconsoleloginprompt')

    return response


def get_nsdhcpparams():
    '''
    Show the running configuration for the nsdhcpparams config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsdhcpparams

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsdhcpparams'), 'nsdhcpparams')

    return response


def get_nsdiameter():
    '''
    Show the running configuration for the nsdiameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsdiameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsdiameter'), 'nsdiameter')

    return response


def get_nsencryptionkey(name=None, method=None, keyvalue=None, padding=None, iv=None, comment=None):
    '''
    Show the running configuration for the nsencryptionkey config key.

    name(str): Filters results that only match the name field.

    method(str): Filters results that only match the method field.

    keyvalue(str): Filters results that only match the keyvalue field.

    padding(str): Filters results that only match the padding field.

    iv(str): Filters results that only match the iv field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsencryptionkey

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if method:
        search_filter.append(['method', method])

    if keyvalue:
        search_filter.append(['keyvalue', keyvalue])

    if padding:
        search_filter.append(['padding', padding])

    if iv:
        search_filter.append(['iv', iv])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsencryptionkey{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsencryptionkey')

    return response


def get_nsencryptionparams():
    '''
    Show the running configuration for the nsencryptionparams config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsencryptionparams

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsencryptionparams'), 'nsencryptionparams')

    return response


def get_nsevents(eventno=None):
    '''
    Show the running configuration for the nsevents config key.

    eventno(int): Filters results that only match the eventno field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsevents

    '''

    search_filter = []

    if eventno:
        search_filter.append(['eventno', eventno])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsevents{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsevents')

    return response


def get_nsextension(src=None, name=None, comment=None, overwrite=None, trace=None, tracefunctions=None,
                    tracevariables=None, detail=None):
    '''
    Show the running configuration for the nsextension config key.

    src(str): Filters results that only match the src field.

    name(str): Filters results that only match the name field.

    comment(str): Filters results that only match the comment field.

    overwrite(bool): Filters results that only match the overwrite field.

    trace(str): Filters results that only match the trace field.

    tracefunctions(str): Filters results that only match the tracefunctions field.

    tracevariables(str): Filters results that only match the tracevariables field.

    detail(str): Filters results that only match the detail field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsextension

    '''

    search_filter = []

    if src:
        search_filter.append(['src', src])

    if name:
        search_filter.append(['name', name])

    if comment:
        search_filter.append(['comment', comment])

    if overwrite:
        search_filter.append(['overwrite', overwrite])

    if trace:
        search_filter.append(['trace', trace])

    if tracefunctions:
        search_filter.append(['tracefunctions', tracefunctions])

    if tracevariables:
        search_filter.append(['tracevariables', tracevariables])

    if detail:
        search_filter.append(['detail', detail])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsextension{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsextension')

    return response


def get_nsextension_binding():
    '''
    Show the running configuration for the nsextension_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsextension_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsextension_binding'), 'nsextension_binding')

    return response


def get_nsextension_extensionfunction_binding(name=None):
    '''
    Show the running configuration for the nsextension_extensionfunction_binding config key.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsextension_extensionfunction_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsextension_extensionfunction_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsextension_extensionfunction_binding')

    return response


def get_nsfeature():
    '''
    Show the running configuration for the nsfeature config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsfeature

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsfeature'), 'nsfeature')

    return response


def get_nshardware():
    '''
    Show the running configuration for the nshardware config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nshardware

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nshardware'), 'nshardware')

    return response


def get_nshmackey(name=None, digest=None, keyvalue=None, comment=None):
    '''
    Show the running configuration for the nshmackey config key.

    name(str): Filters results that only match the name field.

    digest(str): Filters results that only match the digest field.

    keyvalue(str): Filters results that only match the keyvalue field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nshmackey

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if digest:
        search_filter.append(['digest', digest])

    if keyvalue:
        search_filter.append(['keyvalue', keyvalue])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nshmackey{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nshmackey')

    return response


def get_nshostname(hostname=None, ownernode=None):
    '''
    Show the running configuration for the nshostname config key.

    hostname(str): Filters results that only match the hostname field.

    ownernode(int): Filters results that only match the ownernode field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nshostname

    '''

    search_filter = []

    if hostname:
        search_filter.append(['hostname', hostname])

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nshostname{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nshostname')

    return response


def get_nshttpparam():
    '''
    Show the running configuration for the nshttpparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nshttpparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nshttpparam'), 'nshttpparam')

    return response


def get_nshttpprofile(name=None, dropinvalreqs=None, markhttp09inval=None, markconnreqinval=None, cmponpush=None,
                      conmultiplex=None, maxreusepool=None, dropextracrlf=None, incomphdrdelay=None, websocket=None,
                      rtsptunnel=None, reqtimeout=None, adpttimeout=None, reqtimeoutaction=None, dropextradata=None,
                      weblog=None, clientiphdrexpr=None, maxreq=None, persistentetag=None, spdy=None, http2=None,
                      http2direct=None, altsvc=None, reusepooltimeout=None, maxheaderlen=None, minreusepool=None,
                      http2maxheaderlistsize=None, http2maxframesize=None, http2maxconcurrentstreams=None,
                      http2initialwindowsize=None, http2headertablesize=None, http2minseverconn=None,
                      apdexcltresptimethreshold=None):
    '''
    Show the running configuration for the nshttpprofile config key.

    name(str): Filters results that only match the name field.

    dropinvalreqs(str): Filters results that only match the dropinvalreqs field.

    markhttp09inval(str): Filters results that only match the markhttp09inval field.

    markconnreqinval(str): Filters results that only match the markconnreqinval field.

    cmponpush(str): Filters results that only match the cmponpush field.

    conmultiplex(str): Filters results that only match the conmultiplex field.

    maxreusepool(int): Filters results that only match the maxreusepool field.

    dropextracrlf(str): Filters results that only match the dropextracrlf field.

    incomphdrdelay(int): Filters results that only match the incomphdrdelay field.

    websocket(str): Filters results that only match the websocket field.

    rtsptunnel(str): Filters results that only match the rtsptunnel field.

    reqtimeout(int): Filters results that only match the reqtimeout field.

    adpttimeout(str): Filters results that only match the adpttimeout field.

    reqtimeoutaction(str): Filters results that only match the reqtimeoutaction field.

    dropextradata(str): Filters results that only match the dropextradata field.

    weblog(str): Filters results that only match the weblog field.

    clientiphdrexpr(str): Filters results that only match the clientiphdrexpr field.

    maxreq(int): Filters results that only match the maxreq field.

    persistentetag(str): Filters results that only match the persistentetag field.

    spdy(str): Filters results that only match the spdy field.

    http2(str): Filters results that only match the http2 field.

    http2direct(str): Filters results that only match the http2direct field.

    altsvc(str): Filters results that only match the altsvc field.

    reusepooltimeout(int): Filters results that only match the reusepooltimeout field.

    maxheaderlen(int): Filters results that only match the maxheaderlen field.

    minreusepool(int): Filters results that only match the minreusepool field.

    http2maxheaderlistsize(int): Filters results that only match the http2maxheaderlistsize field.

    http2maxframesize(int): Filters results that only match the http2maxframesize field.

    http2maxconcurrentstreams(int): Filters results that only match the http2maxconcurrentstreams field.

    http2initialwindowsize(int): Filters results that only match the http2initialwindowsize field.

    http2headertablesize(int): Filters results that only match the http2headertablesize field.

    http2minseverconn(int): Filters results that only match the http2minseverconn field.

    apdexcltresptimethreshold(int): Filters results that only match the apdexcltresptimethreshold field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nshttpprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if dropinvalreqs:
        search_filter.append(['dropinvalreqs', dropinvalreqs])

    if markhttp09inval:
        search_filter.append(['markhttp09inval', markhttp09inval])

    if markconnreqinval:
        search_filter.append(['markconnreqinval', markconnreqinval])

    if cmponpush:
        search_filter.append(['cmponpush', cmponpush])

    if conmultiplex:
        search_filter.append(['conmultiplex', conmultiplex])

    if maxreusepool:
        search_filter.append(['maxreusepool', maxreusepool])

    if dropextracrlf:
        search_filter.append(['dropextracrlf', dropextracrlf])

    if incomphdrdelay:
        search_filter.append(['incomphdrdelay', incomphdrdelay])

    if websocket:
        search_filter.append(['websocket', websocket])

    if rtsptunnel:
        search_filter.append(['rtsptunnel', rtsptunnel])

    if reqtimeout:
        search_filter.append(['reqtimeout', reqtimeout])

    if adpttimeout:
        search_filter.append(['adpttimeout', adpttimeout])

    if reqtimeoutaction:
        search_filter.append(['reqtimeoutaction', reqtimeoutaction])

    if dropextradata:
        search_filter.append(['dropextradata', dropextradata])

    if weblog:
        search_filter.append(['weblog', weblog])

    if clientiphdrexpr:
        search_filter.append(['clientiphdrexpr', clientiphdrexpr])

    if maxreq:
        search_filter.append(['maxreq', maxreq])

    if persistentetag:
        search_filter.append(['persistentetag', persistentetag])

    if spdy:
        search_filter.append(['spdy', spdy])

    if http2:
        search_filter.append(['http2', http2])

    if http2direct:
        search_filter.append(['http2direct', http2direct])

    if altsvc:
        search_filter.append(['altsvc', altsvc])

    if reusepooltimeout:
        search_filter.append(['reusepooltimeout', reusepooltimeout])

    if maxheaderlen:
        search_filter.append(['maxheaderlen', maxheaderlen])

    if minreusepool:
        search_filter.append(['minreusepool', minreusepool])

    if http2maxheaderlistsize:
        search_filter.append(['http2maxheaderlistsize', http2maxheaderlistsize])

    if http2maxframesize:
        search_filter.append(['http2maxframesize', http2maxframesize])

    if http2maxconcurrentstreams:
        search_filter.append(['http2maxconcurrentstreams', http2maxconcurrentstreams])

    if http2initialwindowsize:
        search_filter.append(['http2initialwindowsize', http2initialwindowsize])

    if http2headertablesize:
        search_filter.append(['http2headertablesize', http2headertablesize])

    if http2minseverconn:
        search_filter.append(['http2minseverconn', http2minseverconn])

    if apdexcltresptimethreshold:
        search_filter.append(['apdexcltresptimethreshold', apdexcltresptimethreshold])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nshttpprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nshttpprofile')

    return response


def get_nsip(ipaddress=None, netmask=None, ns_type=None, arp=None, icmp=None, vserver=None, telnet=None, ftp=None,
             gui=None, ssh=None, snmp=None, mgmtaccess=None, restrictaccess=None, dynamicrouting=None, ospf=None,
             bgp=None, rip=None, hostroute=None, networkroute=None, tag=None, hostrtgw=None, metric=None,
             vserverrhilevel=None, vserverrhimode=None, ospflsatype=None, ospfarea=None, state=None, vrid=None,
             icmpresponse=None, ownernode=None, arpresponse=None, ownerdownresponse=None, td=None):
    '''
    Show the running configuration for the nsip config key.

    ipaddress(str): Filters results that only match the ipaddress field.

    netmask(str): Filters results that only match the netmask field.

    ns_type(str): Filters results that only match the type field.

    arp(str): Filters results that only match the arp field.

    icmp(str): Filters results that only match the icmp field.

    vserver(str): Filters results that only match the vserver field.

    telnet(str): Filters results that only match the telnet field.

    ftp(str): Filters results that only match the ftp field.

    gui(str): Filters results that only match the gui field.

    ssh(str): Filters results that only match the ssh field.

    snmp(str): Filters results that only match the snmp field.

    mgmtaccess(str): Filters results that only match the mgmtaccess field.

    restrictaccess(str): Filters results that only match the restrictaccess field.

    dynamicrouting(str): Filters results that only match the dynamicrouting field.

    ospf(str): Filters results that only match the ospf field.

    bgp(str): Filters results that only match the bgp field.

    rip(str): Filters results that only match the rip field.

    hostroute(str): Filters results that only match the hostroute field.

    networkroute(str): Filters results that only match the networkroute field.

    tag(int): Filters results that only match the tag field.

    hostrtgw(str): Filters results that only match the hostrtgw field.

    metric(int): Filters results that only match the metric field.

    vserverrhilevel(str): Filters results that only match the vserverrhilevel field.

    vserverrhimode(str): Filters results that only match the vserverrhimode field.

    ospflsatype(str): Filters results that only match the ospflsatype field.

    ospfarea(int): Filters results that only match the ospfarea field.

    state(str): Filters results that only match the state field.

    vrid(int): Filters results that only match the vrid field.

    icmpresponse(str): Filters results that only match the icmpresponse field.

    ownernode(int): Filters results that only match the ownernode field.

    arpresponse(str): Filters results that only match the arpresponse field.

    ownerdownresponse(str): Filters results that only match the ownerdownresponse field.

    td(int): Filters results that only match the td field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsip

    '''

    search_filter = []

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if netmask:
        search_filter.append(['netmask', netmask])

    if ns_type:
        search_filter.append(['type', ns_type])

    if arp:
        search_filter.append(['arp', arp])

    if icmp:
        search_filter.append(['icmp', icmp])

    if vserver:
        search_filter.append(['vserver', vserver])

    if telnet:
        search_filter.append(['telnet', telnet])

    if ftp:
        search_filter.append(['ftp', ftp])

    if gui:
        search_filter.append(['gui', gui])

    if ssh:
        search_filter.append(['ssh', ssh])

    if snmp:
        search_filter.append(['snmp', snmp])

    if mgmtaccess:
        search_filter.append(['mgmtaccess', mgmtaccess])

    if restrictaccess:
        search_filter.append(['restrictaccess', restrictaccess])

    if dynamicrouting:
        search_filter.append(['dynamicrouting', dynamicrouting])

    if ospf:
        search_filter.append(['ospf', ospf])

    if bgp:
        search_filter.append(['bgp', bgp])

    if rip:
        search_filter.append(['rip', rip])

    if hostroute:
        search_filter.append(['hostroute', hostroute])

    if networkroute:
        search_filter.append(['networkroute', networkroute])

    if tag:
        search_filter.append(['tag', tag])

    if hostrtgw:
        search_filter.append(['hostrtgw', hostrtgw])

    if metric:
        search_filter.append(['metric', metric])

    if vserverrhilevel:
        search_filter.append(['vserverrhilevel', vserverrhilevel])

    if vserverrhimode:
        search_filter.append(['vserverrhimode', vserverrhimode])

    if ospflsatype:
        search_filter.append(['ospflsatype', ospflsatype])

    if ospfarea:
        search_filter.append(['ospfarea', ospfarea])

    if state:
        search_filter.append(['state', state])

    if vrid:
        search_filter.append(['vrid', vrid])

    if icmpresponse:
        search_filter.append(['icmpresponse', icmpresponse])

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    if arpresponse:
        search_filter.append(['arpresponse', arpresponse])

    if ownerdownresponse:
        search_filter.append(['ownerdownresponse', ownerdownresponse])

    if td:
        search_filter.append(['td', td])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsip{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsip')

    return response


def get_nsip6(ipv6address=None, scope=None, ns_type=None, vlan=None, nd=None, icmp=None, vserver=None, telnet=None,
              ftp=None, gui=None, ssh=None, snmp=None, mgmtaccess=None, restrictaccess=None, dynamicrouting=None,
              hostroute=None, networkroute=None, tag=None, ip6hostrtgw=None, metric=None, vserverrhilevel=None,
              ospf6lsatype=None, ospfarea=None, state=None, ns_map=None, vrid6=None, ownernode=None,
              ownerdownresponse=None, td=None):
    '''
    Show the running configuration for the nsip6 config key.

    ipv6address(str): Filters results that only match the ipv6address field.

    scope(str): Filters results that only match the scope field.

    ns_type(str): Filters results that only match the type field.

    vlan(int): Filters results that only match the vlan field.

    nd(str): Filters results that only match the nd field.

    icmp(str): Filters results that only match the icmp field.

    vserver(str): Filters results that only match the vserver field.

    telnet(str): Filters results that only match the telnet field.

    ftp(str): Filters results that only match the ftp field.

    gui(str): Filters results that only match the gui field.

    ssh(str): Filters results that only match the ssh field.

    snmp(str): Filters results that only match the snmp field.

    mgmtaccess(str): Filters results that only match the mgmtaccess field.

    restrictaccess(str): Filters results that only match the restrictaccess field.

    dynamicrouting(str): Filters results that only match the dynamicrouting field.

    hostroute(str): Filters results that only match the hostroute field.

    networkroute(str): Filters results that only match the networkroute field.

    tag(int): Filters results that only match the tag field.

    ip6hostrtgw(str): Filters results that only match the ip6hostrtgw field.

    metric(int): Filters results that only match the metric field.

    vserverrhilevel(str): Filters results that only match the vserverrhilevel field.

    ospf6lsatype(str): Filters results that only match the ospf6lsatype field.

    ospfarea(int): Filters results that only match the ospfarea field.

    state(str): Filters results that only match the state field.

    ns_map(str): Filters results that only match the map field.

    vrid6(int): Filters results that only match the vrid6 field.

    ownernode(int): Filters results that only match the ownernode field.

    ownerdownresponse(str): Filters results that only match the ownerdownresponse field.

    td(int): Filters results that only match the td field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsip6

    '''

    search_filter = []

    if ipv6address:
        search_filter.append(['ipv6address', ipv6address])

    if scope:
        search_filter.append(['scope', scope])

    if ns_type:
        search_filter.append(['type', ns_type])

    if vlan:
        search_filter.append(['vlan', vlan])

    if nd:
        search_filter.append(['nd', nd])

    if icmp:
        search_filter.append(['icmp', icmp])

    if vserver:
        search_filter.append(['vserver', vserver])

    if telnet:
        search_filter.append(['telnet', telnet])

    if ftp:
        search_filter.append(['ftp', ftp])

    if gui:
        search_filter.append(['gui', gui])

    if ssh:
        search_filter.append(['ssh', ssh])

    if snmp:
        search_filter.append(['snmp', snmp])

    if mgmtaccess:
        search_filter.append(['mgmtaccess', mgmtaccess])

    if restrictaccess:
        search_filter.append(['restrictaccess', restrictaccess])

    if dynamicrouting:
        search_filter.append(['dynamicrouting', dynamicrouting])

    if hostroute:
        search_filter.append(['hostroute', hostroute])

    if networkroute:
        search_filter.append(['networkroute', networkroute])

    if tag:
        search_filter.append(['tag', tag])

    if ip6hostrtgw:
        search_filter.append(['ip6hostrtgw', ip6hostrtgw])

    if metric:
        search_filter.append(['metric', metric])

    if vserverrhilevel:
        search_filter.append(['vserverrhilevel', vserverrhilevel])

    if ospf6lsatype:
        search_filter.append(['ospf6lsatype', ospf6lsatype])

    if ospfarea:
        search_filter.append(['ospfarea', ospfarea])

    if state:
        search_filter.append(['state', state])

    if ns_map:
        search_filter.append(['map', ns_map])

    if vrid6:
        search_filter.append(['vrid6', vrid6])

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    if ownerdownresponse:
        search_filter.append(['ownerdownresponse', ownerdownresponse])

    if td:
        search_filter.append(['td', td])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsip6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsip6')

    return response


def get_nslicense():
    '''
    Show the running configuration for the nslicense config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nslicense

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nslicense'), 'nslicense')

    return response


def get_nslicenseproxyserver(serverip=None, servername=None, port=None):
    '''
    Show the running configuration for the nslicenseproxyserver config key.

    serverip(str): Filters results that only match the serverip field.

    servername(str): Filters results that only match the servername field.

    port(int): Filters results that only match the port field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nslicenseproxyserver

    '''

    search_filter = []

    if serverip:
        search_filter.append(['serverip', serverip])

    if servername:
        search_filter.append(['servername', servername])

    if port:
        search_filter.append(['port', port])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nslicenseproxyserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nslicenseproxyserver')

    return response


def get_nslicenseserver(licenseserverip=None, servername=None, port=None, nodeid=None):
    '''
    Show the running configuration for the nslicenseserver config key.

    licenseserverip(str): Filters results that only match the licenseserverip field.

    servername(str): Filters results that only match the servername field.

    port(int): Filters results that only match the port field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nslicenseserver

    '''

    search_filter = []

    if licenseserverip:
        search_filter.append(['licenseserverip', licenseserverip])

    if servername:
        search_filter.append(['servername', servername])

    if port:
        search_filter.append(['port', port])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nslicenseserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nslicenseserver')

    return response


def get_nslicenseserverpool():
    '''
    Show the running configuration for the nslicenseserverpool config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nslicenseserverpool

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nslicenseserverpool'), 'nslicenseserverpool')

    return response


def get_nslimitidentifier(limitidentifier=None, threshold=None, timeslice=None, mode=None, limittype=None,
                          selectorname=None, maxbandwidth=None, trapsintimeslice=None):
    '''
    Show the running configuration for the nslimitidentifier config key.

    limitidentifier(str): Filters results that only match the limitidentifier field.

    threshold(int): Filters results that only match the threshold field.

    timeslice(int): Filters results that only match the timeslice field.

    mode(str): Filters results that only match the mode field.

    limittype(str): Filters results that only match the limittype field.

    selectorname(str): Filters results that only match the selectorname field.

    maxbandwidth(int): Filters results that only match the maxbandwidth field.

    trapsintimeslice(int): Filters results that only match the trapsintimeslice field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nslimitidentifier

    '''

    search_filter = []

    if limitidentifier:
        search_filter.append(['limitidentifier', limitidentifier])

    if threshold:
        search_filter.append(['threshold', threshold])

    if timeslice:
        search_filter.append(['timeslice', timeslice])

    if mode:
        search_filter.append(['mode', mode])

    if limittype:
        search_filter.append(['limittype', limittype])

    if selectorname:
        search_filter.append(['selectorname', selectorname])

    if maxbandwidth:
        search_filter.append(['maxbandwidth', maxbandwidth])

    if trapsintimeslice:
        search_filter.append(['trapsintimeslice', trapsintimeslice])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nslimitidentifier{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nslimitidentifier')

    return response


def get_nslimitidentifier_binding():
    '''
    Show the running configuration for the nslimitidentifier_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nslimitidentifier_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nslimitidentifier_binding'), 'nslimitidentifier_binding')

    return response


def get_nslimitidentifier_nslimitsessions_binding(limitidentifier=None):
    '''
    Show the running configuration for the nslimitidentifier_nslimitsessions_binding config key.

    limitidentifier(str): Filters results that only match the limitidentifier field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nslimitidentifier_nslimitsessions_binding

    '''

    search_filter = []

    if limitidentifier:
        search_filter.append(['limitidentifier', limitidentifier])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nslimitidentifier_nslimitsessions_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nslimitidentifier_nslimitsessions_binding')

    return response


def get_nslimitselector(selectorname=None, rule=None):
    '''
    Show the running configuration for the nslimitselector config key.

    selectorname(str): Filters results that only match the selectorname field.

    rule(list(str)): Filters results that only match the rule field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nslimitselector

    '''

    search_filter = []

    if selectorname:
        search_filter.append(['selectorname', selectorname])

    if rule:
        search_filter.append(['rule', rule])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nslimitselector{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nslimitselector')

    return response


def get_nslimitsessions(limitidentifier=None, detail=None):
    '''
    Show the running configuration for the nslimitsessions config key.

    limitidentifier(str): Filters results that only match the limitidentifier field.

    detail(bool): Filters results that only match the detail field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nslimitsessions

    '''

    search_filter = []

    if limitidentifier:
        search_filter.append(['limitidentifier', limitidentifier])

    if detail:
        search_filter.append(['detail', detail])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nslimitsessions{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nslimitsessions')

    return response


def get_nsmode():
    '''
    Show the running configuration for the nsmode config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsmode

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsmode'), 'nsmode')

    return response


def get_nsparam():
    '''
    Show the running configuration for the nsparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsparam'), 'nsparam')

    return response


def get_nspartition(partitionname=None, maxbandwidth=None, minbandwidth=None, maxconn=None, maxmemlimit=None,
                    partitionmac=None):
    '''
    Show the running configuration for the nspartition config key.

    partitionname(str): Filters results that only match the partitionname field.

    maxbandwidth(int): Filters results that only match the maxbandwidth field.

    minbandwidth(int): Filters results that only match the minbandwidth field.

    maxconn(int): Filters results that only match the maxconn field.

    maxmemlimit(int): Filters results that only match the maxmemlimit field.

    partitionmac(str): Filters results that only match the partitionmac field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nspartition

    '''

    search_filter = []

    if partitionname:
        search_filter.append(['partitionname', partitionname])

    if maxbandwidth:
        search_filter.append(['maxbandwidth', maxbandwidth])

    if minbandwidth:
        search_filter.append(['minbandwidth', minbandwidth])

    if maxconn:
        search_filter.append(['maxconn', maxconn])

    if maxmemlimit:
        search_filter.append(['maxmemlimit', maxmemlimit])

    if partitionmac:
        search_filter.append(['partitionmac', partitionmac])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nspartition{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nspartition')

    return response


def get_nspartition_binding():
    '''
    Show the running configuration for the nspartition_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nspartition_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nspartition_binding'), 'nspartition_binding')

    return response


def get_nspartition_bridgegroup_binding(bridgegroup=None, partitionname=None):
    '''
    Show the running configuration for the nspartition_bridgegroup_binding config key.

    bridgegroup(int): Filters results that only match the bridgegroup field.

    partitionname(str): Filters results that only match the partitionname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nspartition_bridgegroup_binding

    '''

    search_filter = []

    if bridgegroup:
        search_filter.append(['bridgegroup', bridgegroup])

    if partitionname:
        search_filter.append(['partitionname', partitionname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nspartition_bridgegroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nspartition_bridgegroup_binding')

    return response


def get_nspartition_vlan_binding(vlan=None, partitionname=None):
    '''
    Show the running configuration for the nspartition_vlan_binding config key.

    vlan(int): Filters results that only match the vlan field.

    partitionname(str): Filters results that only match the partitionname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nspartition_vlan_binding

    '''

    search_filter = []

    if vlan:
        search_filter.append(['vlan', vlan])

    if partitionname:
        search_filter.append(['partitionname', partitionname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nspartition_vlan_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nspartition_vlan_binding')

    return response


def get_nspartition_vxlan_binding(partitionname=None):
    '''
    Show the running configuration for the nspartition_vxlan_binding config key.

    partitionname(str): Filters results that only match the partitionname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nspartition_vxlan_binding

    '''

    search_filter = []

    if partitionname:
        search_filter.append(['partitionname', partitionname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nspartition_vxlan_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nspartition_vxlan_binding')

    return response


def get_nspbr(name=None, action=None, td=None, srcip=None, srcipop=None, srcipval=None, srcport=None, srcportop=None,
              srcportval=None, destip=None, destipop=None, destipval=None, destport=None, destportop=None,
              destportval=None, nexthop=None, nexthopval=None, iptunnel=None, iptunnelname=None, vxlanvlanmap=None,
              srcmac=None, srcmacmask=None, protocol=None, protocolnumber=None, vlan=None, vxlan=None, interface=None,
              priority=None, msr=None, monitor=None, state=None, ownergroup=None, detail=None):
    '''
    Show the running configuration for the nspbr config key.

    name(str): Filters results that only match the name field.

    action(str): Filters results that only match the action field.

    td(int): Filters results that only match the td field.

    srcip(bool): Filters results that only match the srcip field.

    srcipop(str): Filters results that only match the srcipop field.

    srcipval(str): Filters results that only match the srcipval field.

    srcport(bool): Filters results that only match the srcport field.

    srcportop(str): Filters results that only match the srcportop field.

    srcportval(str): Filters results that only match the srcportval field.

    destip(bool): Filters results that only match the destip field.

    destipop(str): Filters results that only match the destipop field.

    destipval(str): Filters results that only match the destipval field.

    destport(bool): Filters results that only match the destport field.

    destportop(str): Filters results that only match the destportop field.

    destportval(str): Filters results that only match the destportval field.

    nexthop(bool): Filters results that only match the nexthop field.

    nexthopval(str): Filters results that only match the nexthopval field.

    iptunnel(bool): Filters results that only match the iptunnel field.

    iptunnelname(str): Filters results that only match the iptunnelname field.

    vxlanvlanmap(str): Filters results that only match the vxlanvlanmap field.

    srcmac(str): Filters results that only match the srcmac field.

    srcmacmask(str): Filters results that only match the srcmacmask field.

    protocol(str): Filters results that only match the protocol field.

    protocolnumber(int): Filters results that only match the protocolnumber field.

    vlan(int): Filters results that only match the vlan field.

    vxlan(int): Filters results that only match the vxlan field.

    interface(str): Filters results that only match the Interface field.

    priority(int): Filters results that only match the priority field.

    msr(str): Filters results that only match the msr field.

    monitor(str): Filters results that only match the monitor field.

    state(str): Filters results that only match the state field.

    ownergroup(str): Filters results that only match the ownergroup field.

    detail(bool): Filters results that only match the detail field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nspbr

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if action:
        search_filter.append(['action', action])

    if td:
        search_filter.append(['td', td])

    if srcip:
        search_filter.append(['srcip', srcip])

    if srcipop:
        search_filter.append(['srcipop', srcipop])

    if srcipval:
        search_filter.append(['srcipval', srcipval])

    if srcport:
        search_filter.append(['srcport', srcport])

    if srcportop:
        search_filter.append(['srcportop', srcportop])

    if srcportval:
        search_filter.append(['srcportval', srcportval])

    if destip:
        search_filter.append(['destip', destip])

    if destipop:
        search_filter.append(['destipop', destipop])

    if destipval:
        search_filter.append(['destipval', destipval])

    if destport:
        search_filter.append(['destport', destport])

    if destportop:
        search_filter.append(['destportop', destportop])

    if destportval:
        search_filter.append(['destportval', destportval])

    if nexthop:
        search_filter.append(['nexthop', nexthop])

    if nexthopval:
        search_filter.append(['nexthopval', nexthopval])

    if iptunnel:
        search_filter.append(['iptunnel', iptunnel])

    if iptunnelname:
        search_filter.append(['iptunnelname', iptunnelname])

    if vxlanvlanmap:
        search_filter.append(['vxlanvlanmap', vxlanvlanmap])

    if srcmac:
        search_filter.append(['srcmac', srcmac])

    if srcmacmask:
        search_filter.append(['srcmacmask', srcmacmask])

    if protocol:
        search_filter.append(['protocol', protocol])

    if protocolnumber:
        search_filter.append(['protocolnumber', protocolnumber])

    if vlan:
        search_filter.append(['vlan', vlan])

    if vxlan:
        search_filter.append(['vxlan', vxlan])

    if interface:
        search_filter.append(['Interface', interface])

    if priority:
        search_filter.append(['priority', priority])

    if msr:
        search_filter.append(['msr', msr])

    if monitor:
        search_filter.append(['monitor', monitor])

    if state:
        search_filter.append(['state', state])

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if detail:
        search_filter.append(['detail', detail])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nspbr{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nspbr')

    return response


def get_nspbr6(name=None, td=None, action=None, srcipv6=None, srcipop=None, srcipv6val=None, srcport=None,
               srcportop=None, srcportval=None, destipv6=None, destipop=None, destipv6val=None, destport=None,
               destportop=None, destportval=None, srcmac=None, srcmacmask=None, protocol=None, protocolnumber=None,
               vlan=None, vxlan=None, interface=None, priority=None, state=None, msr=None, monitor=None, nexthop=None,
               nexthopval=None, iptunnel=None, vxlanvlanmap=None, nexthopvlan=None, ownergroup=None, detail=None):
    '''
    Show the running configuration for the nspbr6 config key.

    name(str): Filters results that only match the name field.

    td(int): Filters results that only match the td field.

    action(str): Filters results that only match the action field.

    srcipv6(bool): Filters results that only match the srcipv6 field.

    srcipop(str): Filters results that only match the srcipop field.

    srcipv6val(str): Filters results that only match the srcipv6val field.

    srcport(bool): Filters results that only match the srcport field.

    srcportop(str): Filters results that only match the srcportop field.

    srcportval(str): Filters results that only match the srcportval field.

    destipv6(bool): Filters results that only match the destipv6 field.

    destipop(str): Filters results that only match the destipop field.

    destipv6val(str): Filters results that only match the destipv6val field.

    destport(bool): Filters results that only match the destport field.

    destportop(str): Filters results that only match the destportop field.

    destportval(str): Filters results that only match the destportval field.

    srcmac(str): Filters results that only match the srcmac field.

    srcmacmask(str): Filters results that only match the srcmacmask field.

    protocol(str): Filters results that only match the protocol field.

    protocolnumber(int): Filters results that only match the protocolnumber field.

    vlan(int): Filters results that only match the vlan field.

    vxlan(int): Filters results that only match the vxlan field.

    interface(str): Filters results that only match the Interface field.

    priority(int): Filters results that only match the priority field.

    state(str): Filters results that only match the state field.

    msr(str): Filters results that only match the msr field.

    monitor(str): Filters results that only match the monitor field.

    nexthop(bool): Filters results that only match the nexthop field.

    nexthopval(str): Filters results that only match the nexthopval field.

    iptunnel(str): Filters results that only match the iptunnel field.

    vxlanvlanmap(str): Filters results that only match the vxlanvlanmap field.

    nexthopvlan(int): Filters results that only match the nexthopvlan field.

    ownergroup(str): Filters results that only match the ownergroup field.

    detail(bool): Filters results that only match the detail field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nspbr6

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if td:
        search_filter.append(['td', td])

    if action:
        search_filter.append(['action', action])

    if srcipv6:
        search_filter.append(['srcipv6', srcipv6])

    if srcipop:
        search_filter.append(['srcipop', srcipop])

    if srcipv6val:
        search_filter.append(['srcipv6val', srcipv6val])

    if srcport:
        search_filter.append(['srcport', srcport])

    if srcportop:
        search_filter.append(['srcportop', srcportop])

    if srcportval:
        search_filter.append(['srcportval', srcportval])

    if destipv6:
        search_filter.append(['destipv6', destipv6])

    if destipop:
        search_filter.append(['destipop', destipop])

    if destipv6val:
        search_filter.append(['destipv6val', destipv6val])

    if destport:
        search_filter.append(['destport', destport])

    if destportop:
        search_filter.append(['destportop', destportop])

    if destportval:
        search_filter.append(['destportval', destportval])

    if srcmac:
        search_filter.append(['srcmac', srcmac])

    if srcmacmask:
        search_filter.append(['srcmacmask', srcmacmask])

    if protocol:
        search_filter.append(['protocol', protocol])

    if protocolnumber:
        search_filter.append(['protocolnumber', protocolnumber])

    if vlan:
        search_filter.append(['vlan', vlan])

    if vxlan:
        search_filter.append(['vxlan', vxlan])

    if interface:
        search_filter.append(['Interface', interface])

    if priority:
        search_filter.append(['priority', priority])

    if state:
        search_filter.append(['state', state])

    if msr:
        search_filter.append(['msr', msr])

    if monitor:
        search_filter.append(['monitor', monitor])

    if nexthop:
        search_filter.append(['nexthop', nexthop])

    if nexthopval:
        search_filter.append(['nexthopval', nexthopval])

    if iptunnel:
        search_filter.append(['iptunnel', iptunnel])

    if vxlanvlanmap:
        search_filter.append(['vxlanvlanmap', vxlanvlanmap])

    if nexthopvlan:
        search_filter.append(['nexthopvlan', nexthopvlan])

    if ownergroup:
        search_filter.append(['ownergroup', ownergroup])

    if detail:
        search_filter.append(['detail', detail])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nspbr6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nspbr6')

    return response


def get_nsratecontrol():
    '''
    Show the running configuration for the nsratecontrol config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsratecontrol

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsratecontrol'), 'nsratecontrol')

    return response


def get_nsrollbackcmd():
    '''
    Show the running configuration for the nsrollbackcmd config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsrollbackcmd

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsrollbackcmd'), 'nsrollbackcmd')

    return response


def get_nsrpcnode(ipaddress=None, password=None, srcip=None, secure=None):
    '''
    Show the running configuration for the nsrpcnode config key.

    ipaddress(str): Filters results that only match the ipaddress field.

    password(str): Filters results that only match the password field.

    srcip(str): Filters results that only match the srcip field.

    secure(str): Filters results that only match the secure field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsrpcnode

    '''

    search_filter = []

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if password:
        search_filter.append(['password', password])

    if srcip:
        search_filter.append(['srcip', srcip])

    if secure:
        search_filter.append(['secure', secure])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsrpcnode{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsrpcnode')

    return response


def get_nsrunningconfig():
    '''
    Show the running configuration for the nsrunningconfig config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsrunningconfig

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsrunningconfig'), 'nsrunningconfig')

    return response


def get_nssavedconfig():
    '''
    Show the running configuration for the nssavedconfig config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nssavedconfig

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nssavedconfig'), 'nssavedconfig')

    return response


def get_nsservicefunction(servicefunctionname=None, ingressvlan=None):
    '''
    Show the running configuration for the nsservicefunction config key.

    servicefunctionname(str): Filters results that only match the servicefunctionname field.

    ingressvlan(int): Filters results that only match the ingressvlan field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsservicefunction

    '''

    search_filter = []

    if servicefunctionname:
        search_filter.append(['servicefunctionname', servicefunctionname])

    if ingressvlan:
        search_filter.append(['ingressvlan', ingressvlan])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsservicefunction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsservicefunction')

    return response


def get_nsservicepath(servicepathname=None):
    '''
    Show the running configuration for the nsservicepath config key.

    servicepathname(str): Filters results that only match the servicepathname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsservicepath

    '''

    search_filter = []

    if servicepathname:
        search_filter.append(['servicepathname', servicepathname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsservicepath{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsservicepath')

    return response


def get_nsservicepath_binding():
    '''
    Show the running configuration for the nsservicepath_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsservicepath_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsservicepath_binding'), 'nsservicepath_binding')

    return response


def get_nsservicepath_nsservicefunction_binding(servicepathname=None):
    '''
    Show the running configuration for the nsservicepath_nsservicefunction_binding config key.

    servicepathname(str): Filters results that only match the servicepathname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsservicepath_nsservicefunction_binding

    '''

    search_filter = []

    if servicepathname:
        search_filter.append(['servicepathname', servicepathname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsservicepath_nsservicefunction_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsservicepath_nsservicefunction_binding')

    return response


def get_nssimpleacl(aclname=None, aclaction=None, td=None, srcip=None, destport=None, protocol=None, ttl=None,
                    estsessions=None):
    '''
    Show the running configuration for the nssimpleacl config key.

    aclname(str): Filters results that only match the aclname field.

    aclaction(str): Filters results that only match the aclaction field.

    td(int): Filters results that only match the td field.

    srcip(str): Filters results that only match the srcip field.

    destport(int): Filters results that only match the destport field.

    protocol(str): Filters results that only match the protocol field.

    ttl(int): Filters results that only match the ttl field.

    estsessions(bool): Filters results that only match the estsessions field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nssimpleacl

    '''

    search_filter = []

    if aclname:
        search_filter.append(['aclname', aclname])

    if aclaction:
        search_filter.append(['aclaction', aclaction])

    if td:
        search_filter.append(['td', td])

    if srcip:
        search_filter.append(['srcip', srcip])

    if destport:
        search_filter.append(['destport', destport])

    if protocol:
        search_filter.append(['protocol', protocol])

    if ttl:
        search_filter.append(['ttl', ttl])

    if estsessions:
        search_filter.append(['estsessions', estsessions])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nssimpleacl{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nssimpleacl')

    return response


def get_nssimpleacl6(aclname=None, td=None, aclaction=None, srcipv6=None, destport=None, protocol=None, ttl=None,
                     estsessions=None):
    '''
    Show the running configuration for the nssimpleacl6 config key.

    aclname(str): Filters results that only match the aclname field.

    td(int): Filters results that only match the td field.

    aclaction(str): Filters results that only match the aclaction field.

    srcipv6(str): Filters results that only match the srcipv6 field.

    destport(int): Filters results that only match the destport field.

    protocol(str): Filters results that only match the protocol field.

    ttl(int): Filters results that only match the ttl field.

    estsessions(bool): Filters results that only match the estsessions field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nssimpleacl6

    '''

    search_filter = []

    if aclname:
        search_filter.append(['aclname', aclname])

    if td:
        search_filter.append(['td', td])

    if aclaction:
        search_filter.append(['aclaction', aclaction])

    if srcipv6:
        search_filter.append(['srcipv6', srcipv6])

    if destport:
        search_filter.append(['destport', destport])

    if protocol:
        search_filter.append(['protocol', protocol])

    if ttl:
        search_filter.append(['ttl', ttl])

    if estsessions:
        search_filter.append(['estsessions', estsessions])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nssimpleacl6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nssimpleacl6')

    return response


def get_nssourceroutecachetable():
    '''
    Show the running configuration for the nssourceroutecachetable config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nssourceroutecachetable

    '''

    search_filter = []

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nssourceroutecachetable{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nssourceroutecachetable')

    return response


def get_nsspparams():
    '''
    Show the running configuration for the nsspparams config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsspparams

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsspparams'), 'nsspparams')

    return response


def get_nstcpbufparam():
    '''
    Show the running configuration for the nstcpbufparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstcpbufparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstcpbufparam'), 'nstcpbufparam')

    return response


def get_nstcpparam():
    '''
    Show the running configuration for the nstcpparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstcpparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstcpparam'), 'nstcpparam')

    return response


def get_nstcpprofile(name=None, ws=None, sack=None, wsval=None, nagle=None, ackonpush=None, mss=None, maxburst=None,
                     initialcwnd=None, delayedack=None, oooqsize=None, maxpktpermss=None, pktperretx=None, minrto=None,
                     slowstartincr=None, buffersize=None, syncookie=None, kaprobeupdatelastactivity=None, flavor=None,
                     dynamicreceivebuffering=None, ka=None, kaconnidletime=None, kamaxprobes=None, kaprobeinterval=None,
                     sendbuffsize=None, mptcp=None, establishclientconn=None, tcpsegoffload=None,
                     rstwindowattenuate=None, rstmaxack=None, spoofsyndrop=None, ecn=None, mptcpdropdataonpreestsf=None,
                     mptcpfastopen=None, mptcpsessiontimeout=None, timestamp=None, dsack=None, ackaggregation=None,
                     frto=None, maxcwnd=None, fack=None, tcpmode=None, tcpfastopen=None, hystart=None, dupackthresh=None,
                     burstratecontrol=None, tcprate=None, rateqmax=None, drophalfclosedconnontimeout=None,
                     dropestconnontimeout=None):
    '''
    Show the running configuration for the nstcpprofile config key.

    name(str): Filters results that only match the name field.

    ws(str): Filters results that only match the ws field.

    sack(str): Filters results that only match the sack field.

    wsval(int): Filters results that only match the wsval field.

    nagle(str): Filters results that only match the nagle field.

    ackonpush(str): Filters results that only match the ackonpush field.

    mss(int): Filters results that only match the mss field.

    maxburst(int): Filters results that only match the maxburst field.

    initialcwnd(int): Filters results that only match the initialcwnd field.

    delayedack(int): Filters results that only match the delayedack field.

    oooqsize(int): Filters results that only match the oooqsize field.

    maxpktpermss(int): Filters results that only match the maxpktpermss field.

    pktperretx(int): Filters results that only match the pktperretx field.

    minrto(int): Filters results that only match the minrto field.

    slowstartincr(int): Filters results that only match the slowstartincr field.

    buffersize(int): Filters results that only match the buffersize field.

    syncookie(str): Filters results that only match the syncookie field.

    kaprobeupdatelastactivity(str): Filters results that only match the kaprobeupdatelastactivity field.

    flavor(str): Filters results that only match the flavor field.

    dynamicreceivebuffering(str): Filters results that only match the dynamicreceivebuffering field.

    ka(str): Filters results that only match the ka field.

    kaconnidletime(int): Filters results that only match the kaconnidletime field.

    kamaxprobes(int): Filters results that only match the kamaxprobes field.

    kaprobeinterval(int): Filters results that only match the kaprobeinterval field.

    sendbuffsize(int): Filters results that only match the sendbuffsize field.

    mptcp(str): Filters results that only match the mptcp field.

    establishclientconn(str): Filters results that only match the establishclientconn field.

    tcpsegoffload(str): Filters results that only match the tcpsegoffload field.

    rstwindowattenuate(str): Filters results that only match the rstwindowattenuate field.

    rstmaxack(str): Filters results that only match the rstmaxack field.

    spoofsyndrop(str): Filters results that only match the spoofsyndrop field.

    ecn(str): Filters results that only match the ecn field.

    mptcpdropdataonpreestsf(str): Filters results that only match the mptcpdropdataonpreestsf field.

    mptcpfastopen(str): Filters results that only match the mptcpfastopen field.

    mptcpsessiontimeout(int): Filters results that only match the mptcpsessiontimeout field.

    timestamp(str): Filters results that only match the timestamp field.

    dsack(str): Filters results that only match the dsack field.

    ackaggregation(str): Filters results that only match the ackaggregation field.

    frto(str): Filters results that only match the frto field.

    maxcwnd(int): Filters results that only match the maxcwnd field.

    fack(str): Filters results that only match the fack field.

    tcpmode(str): Filters results that only match the tcpmode field.

    tcpfastopen(str): Filters results that only match the tcpfastopen field.

    hystart(str): Filters results that only match the hystart field.

    dupackthresh(int): Filters results that only match the dupackthresh field.

    burstratecontrol(str): Filters results that only match the burstratecontrol field.

    tcprate(int): Filters results that only match the tcprate field.

    rateqmax(int): Filters results that only match the rateqmax field.

    drophalfclosedconnontimeout(str): Filters results that only match the drophalfclosedconnontimeout field.

    dropestconnontimeout(str): Filters results that only match the dropestconnontimeout field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstcpprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ws:
        search_filter.append(['ws', ws])

    if sack:
        search_filter.append(['sack', sack])

    if wsval:
        search_filter.append(['wsval', wsval])

    if nagle:
        search_filter.append(['nagle', nagle])

    if ackonpush:
        search_filter.append(['ackonpush', ackonpush])

    if mss:
        search_filter.append(['mss', mss])

    if maxburst:
        search_filter.append(['maxburst', maxburst])

    if initialcwnd:
        search_filter.append(['initialcwnd', initialcwnd])

    if delayedack:
        search_filter.append(['delayedack', delayedack])

    if oooqsize:
        search_filter.append(['oooqsize', oooqsize])

    if maxpktpermss:
        search_filter.append(['maxpktpermss', maxpktpermss])

    if pktperretx:
        search_filter.append(['pktperretx', pktperretx])

    if minrto:
        search_filter.append(['minrto', minrto])

    if slowstartincr:
        search_filter.append(['slowstartincr', slowstartincr])

    if buffersize:
        search_filter.append(['buffersize', buffersize])

    if syncookie:
        search_filter.append(['syncookie', syncookie])

    if kaprobeupdatelastactivity:
        search_filter.append(['kaprobeupdatelastactivity', kaprobeupdatelastactivity])

    if flavor:
        search_filter.append(['flavor', flavor])

    if dynamicreceivebuffering:
        search_filter.append(['dynamicreceivebuffering', dynamicreceivebuffering])

    if ka:
        search_filter.append(['ka', ka])

    if kaconnidletime:
        search_filter.append(['kaconnidletime', kaconnidletime])

    if kamaxprobes:
        search_filter.append(['kamaxprobes', kamaxprobes])

    if kaprobeinterval:
        search_filter.append(['kaprobeinterval', kaprobeinterval])

    if sendbuffsize:
        search_filter.append(['sendbuffsize', sendbuffsize])

    if mptcp:
        search_filter.append(['mptcp', mptcp])

    if establishclientconn:
        search_filter.append(['establishclientconn', establishclientconn])

    if tcpsegoffload:
        search_filter.append(['tcpsegoffload', tcpsegoffload])

    if rstwindowattenuate:
        search_filter.append(['rstwindowattenuate', rstwindowattenuate])

    if rstmaxack:
        search_filter.append(['rstmaxack', rstmaxack])

    if spoofsyndrop:
        search_filter.append(['spoofsyndrop', spoofsyndrop])

    if ecn:
        search_filter.append(['ecn', ecn])

    if mptcpdropdataonpreestsf:
        search_filter.append(['mptcpdropdataonpreestsf', mptcpdropdataonpreestsf])

    if mptcpfastopen:
        search_filter.append(['mptcpfastopen', mptcpfastopen])

    if mptcpsessiontimeout:
        search_filter.append(['mptcpsessiontimeout', mptcpsessiontimeout])

    if timestamp:
        search_filter.append(['timestamp', timestamp])

    if dsack:
        search_filter.append(['dsack', dsack])

    if ackaggregation:
        search_filter.append(['ackaggregation', ackaggregation])

    if frto:
        search_filter.append(['frto', frto])

    if maxcwnd:
        search_filter.append(['maxcwnd', maxcwnd])

    if fack:
        search_filter.append(['fack', fack])

    if tcpmode:
        search_filter.append(['tcpmode', tcpmode])

    if tcpfastopen:
        search_filter.append(['tcpfastopen', tcpfastopen])

    if hystart:
        search_filter.append(['hystart', hystart])

    if dupackthresh:
        search_filter.append(['dupackthresh', dupackthresh])

    if burstratecontrol:
        search_filter.append(['burstratecontrol', burstratecontrol])

    if tcprate:
        search_filter.append(['tcprate', tcprate])

    if rateqmax:
        search_filter.append(['rateqmax', rateqmax])

    if drophalfclosedconnontimeout:
        search_filter.append(['drophalfclosedconnontimeout', drophalfclosedconnontimeout])

    if dropestconnontimeout:
        search_filter.append(['dropestconnontimeout', dropestconnontimeout])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstcpprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nstcpprofile')

    return response


def get_nstimeout():
    '''
    Show the running configuration for the nstimeout config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstimeout

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstimeout'), 'nstimeout')

    return response


def get_nstimer(name=None, interval=None, unit=None, comment=None, newname=None):
    '''
    Show the running configuration for the nstimer config key.

    name(str): Filters results that only match the name field.

    interval(int): Filters results that only match the interval field.

    unit(str): Filters results that only match the unit field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstimer

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if interval:
        search_filter.append(['interval', interval])

    if unit:
        search_filter.append(['unit', unit])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstimer{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nstimer')

    return response


def get_nstimer_autoscalepolicy_binding(priority=None, gotopriorityexpression=None, policyname=None, name=None,
                                        threshold=None, samplesize=None, vserver=None):
    '''
    Show the running configuration for the nstimer_autoscalepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policyname(str): Filters results that only match the policyname field.

    name(str): Filters results that only match the name field.

    threshold(int): Filters results that only match the threshold field.

    samplesize(int): Filters results that only match the samplesize field.

    vserver(str): Filters results that only match the vserver field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstimer_autoscalepolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if policyname:
        search_filter.append(['policyname', policyname])

    if name:
        search_filter.append(['name', name])

    if threshold:
        search_filter.append(['threshold', threshold])

    if samplesize:
        search_filter.append(['samplesize', samplesize])

    if vserver:
        search_filter.append(['vserver', vserver])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstimer_autoscalepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nstimer_autoscalepolicy_binding')

    return response


def get_nstimer_binding():
    '''
    Show the running configuration for the nstimer_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstimer_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstimer_binding'), 'nstimer_binding')

    return response


def get_nstrafficdomain(td=None, aliasname=None, vmac=None):
    '''
    Show the running configuration for the nstrafficdomain config key.

    td(int): Filters results that only match the td field.

    aliasname(str): Filters results that only match the aliasname field.

    vmac(str): Filters results that only match the vmac field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstrafficdomain

    '''

    search_filter = []

    if td:
        search_filter.append(['td', td])

    if aliasname:
        search_filter.append(['aliasname', aliasname])

    if vmac:
        search_filter.append(['vmac', vmac])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstrafficdomain{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nstrafficdomain')

    return response


def get_nstrafficdomain_binding():
    '''
    Show the running configuration for the nstrafficdomain_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstrafficdomain_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstrafficdomain_binding'), 'nstrafficdomain_binding')

    return response


def get_nstrafficdomain_bridgegroup_binding(bridgegroup=None, td=None):
    '''
    Show the running configuration for the nstrafficdomain_bridgegroup_binding config key.

    bridgegroup(int): Filters results that only match the bridgegroup field.

    td(int): Filters results that only match the td field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstrafficdomain_bridgegroup_binding

    '''

    search_filter = []

    if bridgegroup:
        search_filter.append(['bridgegroup', bridgegroup])

    if td:
        search_filter.append(['td', td])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstrafficdomain_bridgegroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nstrafficdomain_bridgegroup_binding')

    return response


def get_nstrafficdomain_vlan_binding(vlan=None, td=None):
    '''
    Show the running configuration for the nstrafficdomain_vlan_binding config key.

    vlan(int): Filters results that only match the vlan field.

    td(int): Filters results that only match the td field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstrafficdomain_vlan_binding

    '''

    search_filter = []

    if vlan:
        search_filter.append(['vlan', vlan])

    if td:
        search_filter.append(['td', td])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstrafficdomain_vlan_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nstrafficdomain_vlan_binding')

    return response


def get_nstrafficdomain_vxlan_binding(td=None, vxlan=None):
    '''
    Show the running configuration for the nstrafficdomain_vxlan_binding config key.

    td(int): Filters results that only match the td field.

    vxlan(int): Filters results that only match the vxlan field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nstrafficdomain_vxlan_binding

    '''

    search_filter = []

    if td:
        search_filter.append(['td', td])

    if vxlan:
        search_filter.append(['vxlan', vxlan])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstrafficdomain_vxlan_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nstrafficdomain_vxlan_binding')

    return response


def get_nsvariable(name=None, ns_type=None, scope=None, iffull=None, ifvaluetoobig=None, ifnovalue=None, init=None,
                   expires=None, comment=None):
    '''
    Show the running configuration for the nsvariable config key.

    name(str): Filters results that only match the name field.

    ns_type(str): Filters results that only match the type field.

    scope(str): Filters results that only match the scope field.

    iffull(str): Filters results that only match the iffull field.

    ifvaluetoobig(str): Filters results that only match the ifvaluetoobig field.

    ifnovalue(str): Filters results that only match the ifnovalue field.

    init(str): Filters results that only match the init field.

    expires(int): Filters results that only match the expires field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsvariable

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ns_type:
        search_filter.append(['type', ns_type])

    if scope:
        search_filter.append(['scope', scope])

    if iffull:
        search_filter.append(['iffull', iffull])

    if ifvaluetoobig:
        search_filter.append(['ifvaluetoobig', ifvaluetoobig])

    if ifnovalue:
        search_filter.append(['ifnovalue', ifnovalue])

    if init:
        search_filter.append(['init', init])

    if expires:
        search_filter.append(['expires', expires])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsvariable{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsvariable')

    return response


def get_nsversion():
    '''
    Show the running configuration for the nsversion config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsversion

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsversion'), 'nsversion')

    return response


def get_nsvpxparam():
    '''
    Show the running configuration for the nsvpxparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsvpxparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsvpxparam'), 'nsvpxparam')

    return response


def get_nsweblogparam():
    '''
    Show the running configuration for the nsweblogparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsweblogparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsweblogparam'), 'nsweblogparam')

    return response


def get_nsxmlnamespace(prefix=None, namespace=None, description=None):
    '''
    Show the running configuration for the nsxmlnamespace config key.

    prefix(str): Filters results that only match the prefix field.

    namespace(str): Filters results that only match the Namespace field.

    description(str): Filters results that only match the description field.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.get_nsxmlnamespace

    '''

    search_filter = []

    if prefix:
        search_filter.append(['prefix', prefix])

    if namespace:
        search_filter.append(['Namespace', namespace])

    if description:
        search_filter.append(['description', description])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nsxmlnamespace{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'nsxmlnamespace')

    return response


def save_config():
    '''
    Saves the running configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' ns.save_config

    '''

    payload = {'nsconfig': {}}

    return __proxy__['citrixns.post']('config/nsconfig?action=save', payload)


def unset_nsacl(aclname=None, aclaction=None, td=None, srcip=None, srcipop=None, srcipval=None, srcport=None,
                srcportop=None, srcportval=None, destip=None, destipop=None, destipval=None, destport=None,
                destportop=None, destportval=None, ttl=None, srcmac=None, srcmacmask=None, protocol=None,
                protocolnumber=None, vlan=None, vxlan=None, interface=None, established=None, icmptype=None,
                icmpcode=None, priority=None, state=None, logstate=None, ratelimit=None, newname=None, save=False):
    '''
    Unsets values from the nsacl configuration key.

    aclname(bool): Unsets the aclname value.

    aclaction(bool): Unsets the aclaction value.

    td(bool): Unsets the td value.

    srcip(bool): Unsets the srcip value.

    srcipop(bool): Unsets the srcipop value.

    srcipval(bool): Unsets the srcipval value.

    srcport(bool): Unsets the srcport value.

    srcportop(bool): Unsets the srcportop value.

    srcportval(bool): Unsets the srcportval value.

    destip(bool): Unsets the destip value.

    destipop(bool): Unsets the destipop value.

    destipval(bool): Unsets the destipval value.

    destport(bool): Unsets the destport value.

    destportop(bool): Unsets the destportop value.

    destportval(bool): Unsets the destportval value.

    ttl(bool): Unsets the ttl value.

    srcmac(bool): Unsets the srcmac value.

    srcmacmask(bool): Unsets the srcmacmask value.

    protocol(bool): Unsets the protocol value.

    protocolnumber(bool): Unsets the protocolnumber value.

    vlan(bool): Unsets the vlan value.

    vxlan(bool): Unsets the vxlan value.

    interface(bool): Unsets the interface value.

    established(bool): Unsets the established value.

    icmptype(bool): Unsets the icmptype value.

    icmpcode(bool): Unsets the icmpcode value.

    priority(bool): Unsets the priority value.

    state(bool): Unsets the state value.

    logstate(bool): Unsets the logstate value.

    ratelimit(bool): Unsets the ratelimit value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsacl <args>

    '''

    result = {}

    payload = {'nsacl': {}}

    if aclname:
        payload['nsacl']['aclname'] = True

    if aclaction:
        payload['nsacl']['aclaction'] = True

    if td:
        payload['nsacl']['td'] = True

    if srcip:
        payload['nsacl']['srcip'] = True

    if srcipop:
        payload['nsacl']['srcipop'] = True

    if srcipval:
        payload['nsacl']['srcipval'] = True

    if srcport:
        payload['nsacl']['srcport'] = True

    if srcportop:
        payload['nsacl']['srcportop'] = True

    if srcportval:
        payload['nsacl']['srcportval'] = True

    if destip:
        payload['nsacl']['destip'] = True

    if destipop:
        payload['nsacl']['destipop'] = True

    if destipval:
        payload['nsacl']['destipval'] = True

    if destport:
        payload['nsacl']['destport'] = True

    if destportop:
        payload['nsacl']['destportop'] = True

    if destportval:
        payload['nsacl']['destportval'] = True

    if ttl:
        payload['nsacl']['ttl'] = True

    if srcmac:
        payload['nsacl']['srcmac'] = True

    if srcmacmask:
        payload['nsacl']['srcmacmask'] = True

    if protocol:
        payload['nsacl']['protocol'] = True

    if protocolnumber:
        payload['nsacl']['protocolnumber'] = True

    if vlan:
        payload['nsacl']['vlan'] = True

    if vxlan:
        payload['nsacl']['vxlan'] = True

    if interface:
        payload['nsacl']['Interface'] = True

    if established:
        payload['nsacl']['established'] = True

    if icmptype:
        payload['nsacl']['icmptype'] = True

    if icmpcode:
        payload['nsacl']['icmpcode'] = True

    if priority:
        payload['nsacl']['priority'] = True

    if state:
        payload['nsacl']['state'] = True

    if logstate:
        payload['nsacl']['logstate'] = True

    if ratelimit:
        payload['nsacl']['ratelimit'] = True

    if newname:
        payload['nsacl']['newname'] = True

    execution = __proxy__['citrixns.post']('config/nsacl?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsacl6(acl6name=None, acl6action=None, td=None, srcipv6=None, srcipop=None, srcipv6val=None, srcport=None,
                 srcportop=None, srcportval=None, destipv6=None, destipop=None, destipv6val=None, destport=None,
                 destportop=None, destportval=None, ttl=None, srcmac=None, srcmacmask=None, protocol=None,
                 protocolnumber=None, vlan=None, vxlan=None, interface=None, established=None, icmptype=None,
                 icmpcode=None, priority=None, state=None, aclaction=None, newname=None, save=False):
    '''
    Unsets values from the nsacl6 configuration key.

    acl6name(bool): Unsets the acl6name value.

    acl6action(bool): Unsets the acl6action value.

    td(bool): Unsets the td value.

    srcipv6(bool): Unsets the srcipv6 value.

    srcipop(bool): Unsets the srcipop value.

    srcipv6val(bool): Unsets the srcipv6val value.

    srcport(bool): Unsets the srcport value.

    srcportop(bool): Unsets the srcportop value.

    srcportval(bool): Unsets the srcportval value.

    destipv6(bool): Unsets the destipv6 value.

    destipop(bool): Unsets the destipop value.

    destipv6val(bool): Unsets the destipv6val value.

    destport(bool): Unsets the destport value.

    destportop(bool): Unsets the destportop value.

    destportval(bool): Unsets the destportval value.

    ttl(bool): Unsets the ttl value.

    srcmac(bool): Unsets the srcmac value.

    srcmacmask(bool): Unsets the srcmacmask value.

    protocol(bool): Unsets the protocol value.

    protocolnumber(bool): Unsets the protocolnumber value.

    vlan(bool): Unsets the vlan value.

    vxlan(bool): Unsets the vxlan value.

    interface(bool): Unsets the interface value.

    established(bool): Unsets the established value.

    icmptype(bool): Unsets the icmptype value.

    icmpcode(bool): Unsets the icmpcode value.

    priority(bool): Unsets the priority value.

    state(bool): Unsets the state value.

    aclaction(bool): Unsets the aclaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsacl6 <args>

    '''

    result = {}

    payload = {'nsacl6': {}}

    if acl6name:
        payload['nsacl6']['acl6name'] = True

    if acl6action:
        payload['nsacl6']['acl6action'] = True

    if td:
        payload['nsacl6']['td'] = True

    if srcipv6:
        payload['nsacl6']['srcipv6'] = True

    if srcipop:
        payload['nsacl6']['srcipop'] = True

    if srcipv6val:
        payload['nsacl6']['srcipv6val'] = True

    if srcport:
        payload['nsacl6']['srcport'] = True

    if srcportop:
        payload['nsacl6']['srcportop'] = True

    if srcportval:
        payload['nsacl6']['srcportval'] = True

    if destipv6:
        payload['nsacl6']['destipv6'] = True

    if destipop:
        payload['nsacl6']['destipop'] = True

    if destipv6val:
        payload['nsacl6']['destipv6val'] = True

    if destport:
        payload['nsacl6']['destport'] = True

    if destportop:
        payload['nsacl6']['destportop'] = True

    if destportval:
        payload['nsacl6']['destportval'] = True

    if ttl:
        payload['nsacl6']['ttl'] = True

    if srcmac:
        payload['nsacl6']['srcmac'] = True

    if srcmacmask:
        payload['nsacl6']['srcmacmask'] = True

    if protocol:
        payload['nsacl6']['protocol'] = True

    if protocolnumber:
        payload['nsacl6']['protocolnumber'] = True

    if vlan:
        payload['nsacl6']['vlan'] = True

    if vxlan:
        payload['nsacl6']['vxlan'] = True

    if interface:
        payload['nsacl6']['Interface'] = True

    if established:
        payload['nsacl6']['established'] = True

    if icmptype:
        payload['nsacl6']['icmptype'] = True

    if icmpcode:
        payload['nsacl6']['icmpcode'] = True

    if priority:
        payload['nsacl6']['priority'] = True

    if state:
        payload['nsacl6']['state'] = True

    if aclaction:
        payload['nsacl6']['aclaction'] = True

    if newname:
        payload['nsacl6']['newname'] = True

    execution = __proxy__['citrixns.post']('config/nsacl6?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsappflowparam(templaterefresh=None, udppmtu=None, httpurl=None, httpcookie=None, httpreferer=None,
                         httpmethod=None, httphost=None, httpuseragent=None, clienttrafficonly=None, save=False):
    '''
    Unsets values from the nsappflowparam configuration key.

    templaterefresh(bool): Unsets the templaterefresh value.

    udppmtu(bool): Unsets the udppmtu value.

    httpurl(bool): Unsets the httpurl value.

    httpcookie(bool): Unsets the httpcookie value.

    httpreferer(bool): Unsets the httpreferer value.

    httpmethod(bool): Unsets the httpmethod value.

    httphost(bool): Unsets the httphost value.

    httpuseragent(bool): Unsets the httpuseragent value.

    clienttrafficonly(bool): Unsets the clienttrafficonly value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsappflowparam <args>

    '''

    result = {}

    payload = {'nsappflowparam': {}}

    if templaterefresh:
        payload['nsappflowparam']['templaterefresh'] = True

    if udppmtu:
        payload['nsappflowparam']['udppmtu'] = True

    if httpurl:
        payload['nsappflowparam']['httpurl'] = True

    if httpcookie:
        payload['nsappflowparam']['httpcookie'] = True

    if httpreferer:
        payload['nsappflowparam']['httpreferer'] = True

    if httpmethod:
        payload['nsappflowparam']['httpmethod'] = True

    if httphost:
        payload['nsappflowparam']['httphost'] = True

    if httpuseragent:
        payload['nsappflowparam']['httpuseragent'] = True

    if clienttrafficonly:
        payload['nsappflowparam']['clienttrafficonly'] = True

    execution = __proxy__['citrixns.post']('config/nsappflowparam?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsassignment(name=None, variable=None, ns_set=None, add=None, sub=None, append=None, clear=None, comment=None,
                       newname=None, save=False):
    '''
    Unsets values from the nsassignment configuration key.

    name(bool): Unsets the name value.

    variable(bool): Unsets the variable value.

    ns_set(bool): Unsets the ns_set value.

    add(bool): Unsets the add value.

    sub(bool): Unsets the sub value.

    append(bool): Unsets the append value.

    clear(bool): Unsets the clear value.

    comment(bool): Unsets the comment value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsassignment <args>

    '''

    result = {}

    payload = {'nsassignment': {}}

    if name:
        payload['nsassignment']['name'] = True

    if variable:
        payload['nsassignment']['variable'] = True

    if ns_set:
        payload['nsassignment']['set'] = True

    if add:
        payload['nsassignment']['Add'] = True

    if sub:
        payload['nsassignment']['sub'] = True

    if append:
        payload['nsassignment']['append'] = True

    if clear:
        payload['nsassignment']['clear'] = True

    if comment:
        payload['nsassignment']['comment'] = True

    if newname:
        payload['nsassignment']['newname'] = True

    execution = __proxy__['citrixns.post']('config/nsassignment?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nscapacity(bandwidth=None, edition=None, unit=None, platform=None, nodeid=None, save=False):
    '''
    Unsets values from the nscapacity configuration key.

    bandwidth(bool): Unsets the bandwidth value.

    edition(bool): Unsets the edition value.

    unit(bool): Unsets the unit value.

    platform(bool): Unsets the platform value.

    nodeid(bool): Unsets the nodeid value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nscapacity <args>

    '''

    result = {}

    payload = {'nscapacity': {}}

    if bandwidth:
        payload['nscapacity']['bandwidth'] = True

    if edition:
        payload['nscapacity']['edition'] = True

    if unit:
        payload['nscapacity']['unit'] = True

    if platform:
        payload['nscapacity']['platform'] = True

    if nodeid:
        payload['nscapacity']['nodeid'] = True

    execution = __proxy__['citrixns.post']('config/nscapacity?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsconfig(force=None, level=None, rbaconfig=None, ipaddress=None, netmask=None, nsvlan=None, ifnum=None,
                   tagged=None, httpport=None, maxconn=None, maxreq=None, cip=None, cipheader=None, cookieversion=None,
                   securecookie=None, pmtumin=None, pmtutimeout=None, ftpportrange=None, crportrange=None, timezone=None,
                   grantquotamaxclient=None, exclusivequotamaxclient=None, grantquotaspillover=None,
                   exclusivequotaspillover=None, config1=None, config2=None, outtype=None, template=None,
                   ignoredevicespecific=None, weakpassword=None, config=None, save=False):
    '''
    Unsets values from the nsconfig configuration key.

    force(bool): Unsets the force value.

    level(bool): Unsets the level value.

    rbaconfig(bool): Unsets the rbaconfig value.

    ipaddress(bool): Unsets the ipaddress value.

    netmask(bool): Unsets the netmask value.

    nsvlan(bool): Unsets the nsvlan value.

    ifnum(bool): Unsets the ifnum value.

    tagged(bool): Unsets the tagged value.

    httpport(bool): Unsets the httpport value.

    maxconn(bool): Unsets the maxconn value.

    maxreq(bool): Unsets the maxreq value.

    cip(bool): Unsets the cip value.

    cipheader(bool): Unsets the cipheader value.

    cookieversion(bool): Unsets the cookieversion value.

    securecookie(bool): Unsets the securecookie value.

    pmtumin(bool): Unsets the pmtumin value.

    pmtutimeout(bool): Unsets the pmtutimeout value.

    ftpportrange(bool): Unsets the ftpportrange value.

    crportrange(bool): Unsets the crportrange value.

    timezone(bool): Unsets the timezone value.

    grantquotamaxclient(bool): Unsets the grantquotamaxclient value.

    exclusivequotamaxclient(bool): Unsets the exclusivequotamaxclient value.

    grantquotaspillover(bool): Unsets the grantquotaspillover value.

    exclusivequotaspillover(bool): Unsets the exclusivequotaspillover value.

    config1(bool): Unsets the config1 value.

    config2(bool): Unsets the config2 value.

    outtype(bool): Unsets the outtype value.

    template(bool): Unsets the template value.

    ignoredevicespecific(bool): Unsets the ignoredevicespecific value.

    weakpassword(bool): Unsets the weakpassword value.

    config(bool): Unsets the config value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsconfig <args>

    '''

    result = {}

    payload = {'nsconfig': {}}

    if force:
        payload['nsconfig']['force'] = True

    if level:
        payload['nsconfig']['level'] = True

    if rbaconfig:
        payload['nsconfig']['rbaconfig'] = True

    if ipaddress:
        payload['nsconfig']['ipaddress'] = True

    if netmask:
        payload['nsconfig']['netmask'] = True

    if nsvlan:
        payload['nsconfig']['nsvlan'] = True

    if ifnum:
        payload['nsconfig']['ifnum'] = True

    if tagged:
        payload['nsconfig']['tagged'] = True

    if httpport:
        payload['nsconfig']['httpport'] = True

    if maxconn:
        payload['nsconfig']['maxconn'] = True

    if maxreq:
        payload['nsconfig']['maxreq'] = True

    if cip:
        payload['nsconfig']['cip'] = True

    if cipheader:
        payload['nsconfig']['cipheader'] = True

    if cookieversion:
        payload['nsconfig']['cookieversion'] = True

    if securecookie:
        payload['nsconfig']['securecookie'] = True

    if pmtumin:
        payload['nsconfig']['pmtumin'] = True

    if pmtutimeout:
        payload['nsconfig']['pmtutimeout'] = True

    if ftpportrange:
        payload['nsconfig']['ftpportrange'] = True

    if crportrange:
        payload['nsconfig']['crportrange'] = True

    if timezone:
        payload['nsconfig']['timezone'] = True

    if grantquotamaxclient:
        payload['nsconfig']['grantquotamaxclient'] = True

    if exclusivequotamaxclient:
        payload['nsconfig']['exclusivequotamaxclient'] = True

    if grantquotaspillover:
        payload['nsconfig']['grantquotaspillover'] = True

    if exclusivequotaspillover:
        payload['nsconfig']['exclusivequotaspillover'] = True

    if config1:
        payload['nsconfig']['config1'] = True

    if config2:
        payload['nsconfig']['config2'] = True

    if outtype:
        payload['nsconfig']['outtype'] = True

    if template:
        payload['nsconfig']['template'] = True

    if ignoredevicespecific:
        payload['nsconfig']['ignoredevicespecific'] = True

    if weakpassword:
        payload['nsconfig']['weakpassword'] = True

    if config:
        payload['nsconfig']['config'] = True

    execution = __proxy__['citrixns.post']('config/nsconfig?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsconsoleloginprompt(promptstring=None, save=False):
    '''
    Unsets values from the nsconsoleloginprompt configuration key.

    promptstring(bool): Unsets the promptstring value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsconsoleloginprompt <args>

    '''

    result = {}

    payload = {'nsconsoleloginprompt': {}}

    if promptstring:
        payload['nsconsoleloginprompt']['promptstring'] = True

    execution = __proxy__['citrixns.post']('config/nsconsoleloginprompt?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsdhcpparams(dhcpclient=None, saveroute=None, save=False):
    '''
    Unsets values from the nsdhcpparams configuration key.

    dhcpclient(bool): Unsets the dhcpclient value.

    saveroute(bool): Unsets the saveroute value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsdhcpparams <args>

    '''

    result = {}

    payload = {'nsdhcpparams': {}}

    if dhcpclient:
        payload['nsdhcpparams']['dhcpclient'] = True

    if saveroute:
        payload['nsdhcpparams']['saveroute'] = True

    execution = __proxy__['citrixns.post']('config/nsdhcpparams?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsdiameter(identity=None, realm=None, serverclosepropagation=None, save=False):
    '''
    Unsets values from the nsdiameter configuration key.

    identity(bool): Unsets the identity value.

    realm(bool): Unsets the realm value.

    serverclosepropagation(bool): Unsets the serverclosepropagation value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsdiameter <args>

    '''

    result = {}

    payload = {'nsdiameter': {}}

    if identity:
        payload['nsdiameter']['identity'] = True

    if realm:
        payload['nsdiameter']['realm'] = True

    if serverclosepropagation:
        payload['nsdiameter']['serverclosepropagation'] = True

    execution = __proxy__['citrixns.post']('config/nsdiameter?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsencryptionkey(name=None, method=None, keyvalue=None, padding=None, iv=None, comment=None, save=False):
    '''
    Unsets values from the nsencryptionkey configuration key.

    name(bool): Unsets the name value.

    method(bool): Unsets the method value.

    keyvalue(bool): Unsets the keyvalue value.

    padding(bool): Unsets the padding value.

    iv(bool): Unsets the iv value.

    comment(bool): Unsets the comment value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsencryptionkey <args>

    '''

    result = {}

    payload = {'nsencryptionkey': {}}

    if name:
        payload['nsencryptionkey']['name'] = True

    if method:
        payload['nsencryptionkey']['method'] = True

    if keyvalue:
        payload['nsencryptionkey']['keyvalue'] = True

    if padding:
        payload['nsencryptionkey']['padding'] = True

    if iv:
        payload['nsencryptionkey']['iv'] = True

    if comment:
        payload['nsencryptionkey']['comment'] = True

    execution = __proxy__['citrixns.post']('config/nsencryptionkey?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsextension(src=None, name=None, comment=None, overwrite=None, trace=None, tracefunctions=None,
                      tracevariables=None, detail=None, save=False):
    '''
    Unsets values from the nsextension configuration key.

    src(bool): Unsets the src value.

    name(bool): Unsets the name value.

    comment(bool): Unsets the comment value.

    overwrite(bool): Unsets the overwrite value.

    trace(bool): Unsets the trace value.

    tracefunctions(bool): Unsets the tracefunctions value.

    tracevariables(bool): Unsets the tracevariables value.

    detail(bool): Unsets the detail value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsextension <args>

    '''

    result = {}

    payload = {'nsextension': {}}

    if src:
        payload['nsextension']['src'] = True

    if name:
        payload['nsextension']['name'] = True

    if comment:
        payload['nsextension']['comment'] = True

    if overwrite:
        payload['nsextension']['overwrite'] = True

    if trace:
        payload['nsextension']['trace'] = True

    if tracefunctions:
        payload['nsextension']['tracefunctions'] = True

    if tracevariables:
        payload['nsextension']['tracevariables'] = True

    if detail:
        payload['nsextension']['detail'] = True

    execution = __proxy__['citrixns.post']('config/nsextension?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nshmackey(name=None, digest=None, keyvalue=None, comment=None, save=False):
    '''
    Unsets values from the nshmackey configuration key.

    name(bool): Unsets the name value.

    digest(bool): Unsets the digest value.

    keyvalue(bool): Unsets the keyvalue value.

    comment(bool): Unsets the comment value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nshmackey <args>

    '''

    result = {}

    payload = {'nshmackey': {}}

    if name:
        payload['nshmackey']['name'] = True

    if digest:
        payload['nshmackey']['digest'] = True

    if keyvalue:
        payload['nshmackey']['keyvalue'] = True

    if comment:
        payload['nshmackey']['comment'] = True

    execution = __proxy__['citrixns.post']('config/nshmackey?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nshttpparam(dropinvalreqs=None, markhttp09inval=None, markconnreqinval=None, insnssrvrhdr=None, nssrvrhdr=None,
                      logerrresp=None, conmultiplex=None, maxreusepool=None, save=False):
    '''
    Unsets values from the nshttpparam configuration key.

    dropinvalreqs(bool): Unsets the dropinvalreqs value.

    markhttp09inval(bool): Unsets the markhttp09inval value.

    markconnreqinval(bool): Unsets the markconnreqinval value.

    insnssrvrhdr(bool): Unsets the insnssrvrhdr value.

    nssrvrhdr(bool): Unsets the nssrvrhdr value.

    logerrresp(bool): Unsets the logerrresp value.

    conmultiplex(bool): Unsets the conmultiplex value.

    maxreusepool(bool): Unsets the maxreusepool value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nshttpparam <args>

    '''

    result = {}

    payload = {'nshttpparam': {}}

    if dropinvalreqs:
        payload['nshttpparam']['dropinvalreqs'] = True

    if markhttp09inval:
        payload['nshttpparam']['markhttp09inval'] = True

    if markconnreqinval:
        payload['nshttpparam']['markconnreqinval'] = True

    if insnssrvrhdr:
        payload['nshttpparam']['insnssrvrhdr'] = True

    if nssrvrhdr:
        payload['nshttpparam']['nssrvrhdr'] = True

    if logerrresp:
        payload['nshttpparam']['logerrresp'] = True

    if conmultiplex:
        payload['nshttpparam']['conmultiplex'] = True

    if maxreusepool:
        payload['nshttpparam']['maxreusepool'] = True

    execution = __proxy__['citrixns.post']('config/nshttpparam?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nshttpprofile(name=None, dropinvalreqs=None, markhttp09inval=None, markconnreqinval=None, cmponpush=None,
                        conmultiplex=None, maxreusepool=None, dropextracrlf=None, incomphdrdelay=None, websocket=None,
                        rtsptunnel=None, reqtimeout=None, adpttimeout=None, reqtimeoutaction=None, dropextradata=None,
                        weblog=None, clientiphdrexpr=None, maxreq=None, persistentetag=None, spdy=None, http2=None,
                        http2direct=None, altsvc=None, reusepooltimeout=None, maxheaderlen=None, minreusepool=None,
                        http2maxheaderlistsize=None, http2maxframesize=None, http2maxconcurrentstreams=None,
                        http2initialwindowsize=None, http2headertablesize=None, http2minseverconn=None,
                        apdexcltresptimethreshold=None, save=False):
    '''
    Unsets values from the nshttpprofile configuration key.

    name(bool): Unsets the name value.

    dropinvalreqs(bool): Unsets the dropinvalreqs value.

    markhttp09inval(bool): Unsets the markhttp09inval value.

    markconnreqinval(bool): Unsets the markconnreqinval value.

    cmponpush(bool): Unsets the cmponpush value.

    conmultiplex(bool): Unsets the conmultiplex value.

    maxreusepool(bool): Unsets the maxreusepool value.

    dropextracrlf(bool): Unsets the dropextracrlf value.

    incomphdrdelay(bool): Unsets the incomphdrdelay value.

    websocket(bool): Unsets the websocket value.

    rtsptunnel(bool): Unsets the rtsptunnel value.

    reqtimeout(bool): Unsets the reqtimeout value.

    adpttimeout(bool): Unsets the adpttimeout value.

    reqtimeoutaction(bool): Unsets the reqtimeoutaction value.

    dropextradata(bool): Unsets the dropextradata value.

    weblog(bool): Unsets the weblog value.

    clientiphdrexpr(bool): Unsets the clientiphdrexpr value.

    maxreq(bool): Unsets the maxreq value.

    persistentetag(bool): Unsets the persistentetag value.

    spdy(bool): Unsets the spdy value.

    http2(bool): Unsets the http2 value.

    http2direct(bool): Unsets the http2direct value.

    altsvc(bool): Unsets the altsvc value.

    reusepooltimeout(bool): Unsets the reusepooltimeout value.

    maxheaderlen(bool): Unsets the maxheaderlen value.

    minreusepool(bool): Unsets the minreusepool value.

    http2maxheaderlistsize(bool): Unsets the http2maxheaderlistsize value.

    http2maxframesize(bool): Unsets the http2maxframesize value.

    http2maxconcurrentstreams(bool): Unsets the http2maxconcurrentstreams value.

    http2initialwindowsize(bool): Unsets the http2initialwindowsize value.

    http2headertablesize(bool): Unsets the http2headertablesize value.

    http2minseverconn(bool): Unsets the http2minseverconn value.

    apdexcltresptimethreshold(bool): Unsets the apdexcltresptimethreshold value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nshttpprofile <args>

    '''

    result = {}

    payload = {'nshttpprofile': {}}

    if name:
        payload['nshttpprofile']['name'] = True

    if dropinvalreqs:
        payload['nshttpprofile']['dropinvalreqs'] = True

    if markhttp09inval:
        payload['nshttpprofile']['markhttp09inval'] = True

    if markconnreqinval:
        payload['nshttpprofile']['markconnreqinval'] = True

    if cmponpush:
        payload['nshttpprofile']['cmponpush'] = True

    if conmultiplex:
        payload['nshttpprofile']['conmultiplex'] = True

    if maxreusepool:
        payload['nshttpprofile']['maxreusepool'] = True

    if dropextracrlf:
        payload['nshttpprofile']['dropextracrlf'] = True

    if incomphdrdelay:
        payload['nshttpprofile']['incomphdrdelay'] = True

    if websocket:
        payload['nshttpprofile']['websocket'] = True

    if rtsptunnel:
        payload['nshttpprofile']['rtsptunnel'] = True

    if reqtimeout:
        payload['nshttpprofile']['reqtimeout'] = True

    if adpttimeout:
        payload['nshttpprofile']['adpttimeout'] = True

    if reqtimeoutaction:
        payload['nshttpprofile']['reqtimeoutaction'] = True

    if dropextradata:
        payload['nshttpprofile']['dropextradata'] = True

    if weblog:
        payload['nshttpprofile']['weblog'] = True

    if clientiphdrexpr:
        payload['nshttpprofile']['clientiphdrexpr'] = True

    if maxreq:
        payload['nshttpprofile']['maxreq'] = True

    if persistentetag:
        payload['nshttpprofile']['persistentetag'] = True

    if spdy:
        payload['nshttpprofile']['spdy'] = True

    if http2:
        payload['nshttpprofile']['http2'] = True

    if http2direct:
        payload['nshttpprofile']['http2direct'] = True

    if altsvc:
        payload['nshttpprofile']['altsvc'] = True

    if reusepooltimeout:
        payload['nshttpprofile']['reusepooltimeout'] = True

    if maxheaderlen:
        payload['nshttpprofile']['maxheaderlen'] = True

    if minreusepool:
        payload['nshttpprofile']['minreusepool'] = True

    if http2maxheaderlistsize:
        payload['nshttpprofile']['http2maxheaderlistsize'] = True

    if http2maxframesize:
        payload['nshttpprofile']['http2maxframesize'] = True

    if http2maxconcurrentstreams:
        payload['nshttpprofile']['http2maxconcurrentstreams'] = True

    if http2initialwindowsize:
        payload['nshttpprofile']['http2initialwindowsize'] = True

    if http2headertablesize:
        payload['nshttpprofile']['http2headertablesize'] = True

    if http2minseverconn:
        payload['nshttpprofile']['http2minseverconn'] = True

    if apdexcltresptimethreshold:
        payload['nshttpprofile']['apdexcltresptimethreshold'] = True

    execution = __proxy__['citrixns.post']('config/nshttpprofile?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsip(ipaddress=None, netmask=None, ns_type=None, arp=None, icmp=None, vserver=None, telnet=None, ftp=None,
               gui=None, ssh=None, snmp=None, mgmtaccess=None, restrictaccess=None, dynamicrouting=None, ospf=None,
               bgp=None, rip=None, hostroute=None, networkroute=None, tag=None, hostrtgw=None, metric=None,
               vserverrhilevel=None, vserverrhimode=None, ospflsatype=None, ospfarea=None, state=None, vrid=None,
               icmpresponse=None, ownernode=None, arpresponse=None, ownerdownresponse=None, td=None, save=False):
    '''
    Unsets values from the nsip configuration key.

    ipaddress(bool): Unsets the ipaddress value.

    netmask(bool): Unsets the netmask value.

    ns_type(bool): Unsets the ns_type value.

    arp(bool): Unsets the arp value.

    icmp(bool): Unsets the icmp value.

    vserver(bool): Unsets the vserver value.

    telnet(bool): Unsets the telnet value.

    ftp(bool): Unsets the ftp value.

    gui(bool): Unsets the gui value.

    ssh(bool): Unsets the ssh value.

    snmp(bool): Unsets the snmp value.

    mgmtaccess(bool): Unsets the mgmtaccess value.

    restrictaccess(bool): Unsets the restrictaccess value.

    dynamicrouting(bool): Unsets the dynamicrouting value.

    ospf(bool): Unsets the ospf value.

    bgp(bool): Unsets the bgp value.

    rip(bool): Unsets the rip value.

    hostroute(bool): Unsets the hostroute value.

    networkroute(bool): Unsets the networkroute value.

    tag(bool): Unsets the tag value.

    hostrtgw(bool): Unsets the hostrtgw value.

    metric(bool): Unsets the metric value.

    vserverrhilevel(bool): Unsets the vserverrhilevel value.

    vserverrhimode(bool): Unsets the vserverrhimode value.

    ospflsatype(bool): Unsets the ospflsatype value.

    ospfarea(bool): Unsets the ospfarea value.

    state(bool): Unsets the state value.

    vrid(bool): Unsets the vrid value.

    icmpresponse(bool): Unsets the icmpresponse value.

    ownernode(bool): Unsets the ownernode value.

    arpresponse(bool): Unsets the arpresponse value.

    ownerdownresponse(bool): Unsets the ownerdownresponse value.

    td(bool): Unsets the td value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsip <args>

    '''

    result = {}

    payload = {'nsip': {}}

    if ipaddress:
        payload['nsip']['ipaddress'] = True

    if netmask:
        payload['nsip']['netmask'] = True

    if ns_type:
        payload['nsip']['type'] = True

    if arp:
        payload['nsip']['arp'] = True

    if icmp:
        payload['nsip']['icmp'] = True

    if vserver:
        payload['nsip']['vserver'] = True

    if telnet:
        payload['nsip']['telnet'] = True

    if ftp:
        payload['nsip']['ftp'] = True

    if gui:
        payload['nsip']['gui'] = True

    if ssh:
        payload['nsip']['ssh'] = True

    if snmp:
        payload['nsip']['snmp'] = True

    if mgmtaccess:
        payload['nsip']['mgmtaccess'] = True

    if restrictaccess:
        payload['nsip']['restrictaccess'] = True

    if dynamicrouting:
        payload['nsip']['dynamicrouting'] = True

    if ospf:
        payload['nsip']['ospf'] = True

    if bgp:
        payload['nsip']['bgp'] = True

    if rip:
        payload['nsip']['rip'] = True

    if hostroute:
        payload['nsip']['hostroute'] = True

    if networkroute:
        payload['nsip']['networkroute'] = True

    if tag:
        payload['nsip']['tag'] = True

    if hostrtgw:
        payload['nsip']['hostrtgw'] = True

    if metric:
        payload['nsip']['metric'] = True

    if vserverrhilevel:
        payload['nsip']['vserverrhilevel'] = True

    if vserverrhimode:
        payload['nsip']['vserverrhimode'] = True

    if ospflsatype:
        payload['nsip']['ospflsatype'] = True

    if ospfarea:
        payload['nsip']['ospfarea'] = True

    if state:
        payload['nsip']['state'] = True

    if vrid:
        payload['nsip']['vrid'] = True

    if icmpresponse:
        payload['nsip']['icmpresponse'] = True

    if ownernode:
        payload['nsip']['ownernode'] = True

    if arpresponse:
        payload['nsip']['arpresponse'] = True

    if ownerdownresponse:
        payload['nsip']['ownerdownresponse'] = True

    if td:
        payload['nsip']['td'] = True

    execution = __proxy__['citrixns.post']('config/nsip?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsip6(ipv6address=None, scope=None, ns_type=None, vlan=None, nd=None, icmp=None, vserver=None, telnet=None,
                ftp=None, gui=None, ssh=None, snmp=None, mgmtaccess=None, restrictaccess=None, dynamicrouting=None,
                hostroute=None, networkroute=None, tag=None, ip6hostrtgw=None, metric=None, vserverrhilevel=None,
                ospf6lsatype=None, ospfarea=None, state=None, ns_map=None, vrid6=None, ownernode=None,
                ownerdownresponse=None, td=None, save=False):
    '''
    Unsets values from the nsip6 configuration key.

    ipv6address(bool): Unsets the ipv6address value.

    scope(bool): Unsets the scope value.

    ns_type(bool): Unsets the ns_type value.

    vlan(bool): Unsets the vlan value.

    nd(bool): Unsets the nd value.

    icmp(bool): Unsets the icmp value.

    vserver(bool): Unsets the vserver value.

    telnet(bool): Unsets the telnet value.

    ftp(bool): Unsets the ftp value.

    gui(bool): Unsets the gui value.

    ssh(bool): Unsets the ssh value.

    snmp(bool): Unsets the snmp value.

    mgmtaccess(bool): Unsets the mgmtaccess value.

    restrictaccess(bool): Unsets the restrictaccess value.

    dynamicrouting(bool): Unsets the dynamicrouting value.

    hostroute(bool): Unsets the hostroute value.

    networkroute(bool): Unsets the networkroute value.

    tag(bool): Unsets the tag value.

    ip6hostrtgw(bool): Unsets the ip6hostrtgw value.

    metric(bool): Unsets the metric value.

    vserverrhilevel(bool): Unsets the vserverrhilevel value.

    ospf6lsatype(bool): Unsets the ospf6lsatype value.

    ospfarea(bool): Unsets the ospfarea value.

    state(bool): Unsets the state value.

    ns_map(bool): Unsets the ns_map value.

    vrid6(bool): Unsets the vrid6 value.

    ownernode(bool): Unsets the ownernode value.

    ownerdownresponse(bool): Unsets the ownerdownresponse value.

    td(bool): Unsets the td value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsip6 <args>

    '''

    result = {}

    payload = {'nsip6': {}}

    if ipv6address:
        payload['nsip6']['ipv6address'] = True

    if scope:
        payload['nsip6']['scope'] = True

    if ns_type:
        payload['nsip6']['type'] = True

    if vlan:
        payload['nsip6']['vlan'] = True

    if nd:
        payload['nsip6']['nd'] = True

    if icmp:
        payload['nsip6']['icmp'] = True

    if vserver:
        payload['nsip6']['vserver'] = True

    if telnet:
        payload['nsip6']['telnet'] = True

    if ftp:
        payload['nsip6']['ftp'] = True

    if gui:
        payload['nsip6']['gui'] = True

    if ssh:
        payload['nsip6']['ssh'] = True

    if snmp:
        payload['nsip6']['snmp'] = True

    if mgmtaccess:
        payload['nsip6']['mgmtaccess'] = True

    if restrictaccess:
        payload['nsip6']['restrictaccess'] = True

    if dynamicrouting:
        payload['nsip6']['dynamicrouting'] = True

    if hostroute:
        payload['nsip6']['hostroute'] = True

    if networkroute:
        payload['nsip6']['networkroute'] = True

    if tag:
        payload['nsip6']['tag'] = True

    if ip6hostrtgw:
        payload['nsip6']['ip6hostrtgw'] = True

    if metric:
        payload['nsip6']['metric'] = True

    if vserverrhilevel:
        payload['nsip6']['vserverrhilevel'] = True

    if ospf6lsatype:
        payload['nsip6']['ospf6lsatype'] = True

    if ospfarea:
        payload['nsip6']['ospfarea'] = True

    if state:
        payload['nsip6']['state'] = True

    if ns_map:
        payload['nsip6']['map'] = True

    if vrid6:
        payload['nsip6']['vrid6'] = True

    if ownernode:
        payload['nsip6']['ownernode'] = True

    if ownerdownresponse:
        payload['nsip6']['ownerdownresponse'] = True

    if td:
        payload['nsip6']['td'] = True

    execution = __proxy__['citrixns.post']('config/nsip6?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nslimitidentifier(limitidentifier=None, threshold=None, timeslice=None, mode=None, limittype=None,
                            selectorname=None, maxbandwidth=None, trapsintimeslice=None, save=False):
    '''
    Unsets values from the nslimitidentifier configuration key.

    limitidentifier(bool): Unsets the limitidentifier value.

    threshold(bool): Unsets the threshold value.

    timeslice(bool): Unsets the timeslice value.

    mode(bool): Unsets the mode value.

    limittype(bool): Unsets the limittype value.

    selectorname(bool): Unsets the selectorname value.

    maxbandwidth(bool): Unsets the maxbandwidth value.

    trapsintimeslice(bool): Unsets the trapsintimeslice value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nslimitidentifier <args>

    '''

    result = {}

    payload = {'nslimitidentifier': {}}

    if limitidentifier:
        payload['nslimitidentifier']['limitidentifier'] = True

    if threshold:
        payload['nslimitidentifier']['threshold'] = True

    if timeslice:
        payload['nslimitidentifier']['timeslice'] = True

    if mode:
        payload['nslimitidentifier']['mode'] = True

    if limittype:
        payload['nslimitidentifier']['limittype'] = True

    if selectorname:
        payload['nslimitidentifier']['selectorname'] = True

    if maxbandwidth:
        payload['nslimitidentifier']['maxbandwidth'] = True

    if trapsintimeslice:
        payload['nslimitidentifier']['trapsintimeslice'] = True

    execution = __proxy__['citrixns.post']('config/nslimitidentifier?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nslimitselector(selectorname=None, rule=None, save=False):
    '''
    Unsets values from the nslimitselector configuration key.

    selectorname(bool): Unsets the selectorname value.

    rule(bool): Unsets the rule value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nslimitselector <args>

    '''

    result = {}

    payload = {'nslimitselector': {}}

    if selectorname:
        payload['nslimitselector']['selectorname'] = True

    if rule:
        payload['nslimitselector']['rule'] = True

    execution = __proxy__['citrixns.post']('config/nslimitselector?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsparam(httpport=None, maxconn=None, maxreq=None, cip=None, cipheader=None, cookieversion=None,
                  securecookie=None, pmtumin=None, pmtutimeout=None, ftpportrange=None, crportrange=None, timezone=None,
                  grantquotamaxclient=None, exclusivequotamaxclient=None, grantquotaspillover=None,
                  exclusivequotaspillover=None, useproxyport=None, internaluserlogin=None,
                  aftpallowrandomsourceport=None, icaports=None, tcpcip=None, servicepathingressvlan=None,
                  secureicaports=None, save=False):
    '''
    Unsets values from the nsparam configuration key.

    httpport(bool): Unsets the httpport value.

    maxconn(bool): Unsets the maxconn value.

    maxreq(bool): Unsets the maxreq value.

    cip(bool): Unsets the cip value.

    cipheader(bool): Unsets the cipheader value.

    cookieversion(bool): Unsets the cookieversion value.

    securecookie(bool): Unsets the securecookie value.

    pmtumin(bool): Unsets the pmtumin value.

    pmtutimeout(bool): Unsets the pmtutimeout value.

    ftpportrange(bool): Unsets the ftpportrange value.

    crportrange(bool): Unsets the crportrange value.

    timezone(bool): Unsets the timezone value.

    grantquotamaxclient(bool): Unsets the grantquotamaxclient value.

    exclusivequotamaxclient(bool): Unsets the exclusivequotamaxclient value.

    grantquotaspillover(bool): Unsets the grantquotaspillover value.

    exclusivequotaspillover(bool): Unsets the exclusivequotaspillover value.

    useproxyport(bool): Unsets the useproxyport value.

    internaluserlogin(bool): Unsets the internaluserlogin value.

    aftpallowrandomsourceport(bool): Unsets the aftpallowrandomsourceport value.

    icaports(bool): Unsets the icaports value.

    tcpcip(bool): Unsets the tcpcip value.

    servicepathingressvlan(bool): Unsets the servicepathingressvlan value.

    secureicaports(bool): Unsets the secureicaports value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsparam <args>

    '''

    result = {}

    payload = {'nsparam': {}}

    if httpport:
        payload['nsparam']['httpport'] = True

    if maxconn:
        payload['nsparam']['maxconn'] = True

    if maxreq:
        payload['nsparam']['maxreq'] = True

    if cip:
        payload['nsparam']['cip'] = True

    if cipheader:
        payload['nsparam']['cipheader'] = True

    if cookieversion:
        payload['nsparam']['cookieversion'] = True

    if securecookie:
        payload['nsparam']['securecookie'] = True

    if pmtumin:
        payload['nsparam']['pmtumin'] = True

    if pmtutimeout:
        payload['nsparam']['pmtutimeout'] = True

    if ftpportrange:
        payload['nsparam']['ftpportrange'] = True

    if crportrange:
        payload['nsparam']['crportrange'] = True

    if timezone:
        payload['nsparam']['timezone'] = True

    if grantquotamaxclient:
        payload['nsparam']['grantquotamaxclient'] = True

    if exclusivequotamaxclient:
        payload['nsparam']['exclusivequotamaxclient'] = True

    if grantquotaspillover:
        payload['nsparam']['grantquotaspillover'] = True

    if exclusivequotaspillover:
        payload['nsparam']['exclusivequotaspillover'] = True

    if useproxyport:
        payload['nsparam']['useproxyport'] = True

    if internaluserlogin:
        payload['nsparam']['internaluserlogin'] = True

    if aftpallowrandomsourceport:
        payload['nsparam']['aftpallowrandomsourceport'] = True

    if icaports:
        payload['nsparam']['icaports'] = True

    if tcpcip:
        payload['nsparam']['tcpcip'] = True

    if servicepathingressvlan:
        payload['nsparam']['servicepathingressvlan'] = True

    if secureicaports:
        payload['nsparam']['secureicaports'] = True

    execution = __proxy__['citrixns.post']('config/nsparam?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nspartition(partitionname=None, maxbandwidth=None, minbandwidth=None, maxconn=None, maxmemlimit=None,
                      partitionmac=None, save=False):
    '''
    Unsets values from the nspartition configuration key.

    partitionname(bool): Unsets the partitionname value.

    maxbandwidth(bool): Unsets the maxbandwidth value.

    minbandwidth(bool): Unsets the minbandwidth value.

    maxconn(bool): Unsets the maxconn value.

    maxmemlimit(bool): Unsets the maxmemlimit value.

    partitionmac(bool): Unsets the partitionmac value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nspartition <args>

    '''

    result = {}

    payload = {'nspartition': {}}

    if partitionname:
        payload['nspartition']['partitionname'] = True

    if maxbandwidth:
        payload['nspartition']['maxbandwidth'] = True

    if minbandwidth:
        payload['nspartition']['minbandwidth'] = True

    if maxconn:
        payload['nspartition']['maxconn'] = True

    if maxmemlimit:
        payload['nspartition']['maxmemlimit'] = True

    if partitionmac:
        payload['nspartition']['partitionmac'] = True

    execution = __proxy__['citrixns.post']('config/nspartition?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nspbr(name=None, action=None, td=None, srcip=None, srcipop=None, srcipval=None, srcport=None, srcportop=None,
                srcportval=None, destip=None, destipop=None, destipval=None, destport=None, destportop=None,
                destportval=None, nexthop=None, nexthopval=None, iptunnel=None, iptunnelname=None, vxlanvlanmap=None,
                srcmac=None, srcmacmask=None, protocol=None, protocolnumber=None, vlan=None, vxlan=None, interface=None,
                priority=None, msr=None, monitor=None, state=None, ownergroup=None, detail=None, save=False):
    '''
    Unsets values from the nspbr configuration key.

    name(bool): Unsets the name value.

    action(bool): Unsets the action value.

    td(bool): Unsets the td value.

    srcip(bool): Unsets the srcip value.

    srcipop(bool): Unsets the srcipop value.

    srcipval(bool): Unsets the srcipval value.

    srcport(bool): Unsets the srcport value.

    srcportop(bool): Unsets the srcportop value.

    srcportval(bool): Unsets the srcportval value.

    destip(bool): Unsets the destip value.

    destipop(bool): Unsets the destipop value.

    destipval(bool): Unsets the destipval value.

    destport(bool): Unsets the destport value.

    destportop(bool): Unsets the destportop value.

    destportval(bool): Unsets the destportval value.

    nexthop(bool): Unsets the nexthop value.

    nexthopval(bool): Unsets the nexthopval value.

    iptunnel(bool): Unsets the iptunnel value.

    iptunnelname(bool): Unsets the iptunnelname value.

    vxlanvlanmap(bool): Unsets the vxlanvlanmap value.

    srcmac(bool): Unsets the srcmac value.

    srcmacmask(bool): Unsets the srcmacmask value.

    protocol(bool): Unsets the protocol value.

    protocolnumber(bool): Unsets the protocolnumber value.

    vlan(bool): Unsets the vlan value.

    vxlan(bool): Unsets the vxlan value.

    interface(bool): Unsets the interface value.

    priority(bool): Unsets the priority value.

    msr(bool): Unsets the msr value.

    monitor(bool): Unsets the monitor value.

    state(bool): Unsets the state value.

    ownergroup(bool): Unsets the ownergroup value.

    detail(bool): Unsets the detail value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nspbr <args>

    '''

    result = {}

    payload = {'nspbr': {}}

    if name:
        payload['nspbr']['name'] = True

    if action:
        payload['nspbr']['action'] = True

    if td:
        payload['nspbr']['td'] = True

    if srcip:
        payload['nspbr']['srcip'] = True

    if srcipop:
        payload['nspbr']['srcipop'] = True

    if srcipval:
        payload['nspbr']['srcipval'] = True

    if srcport:
        payload['nspbr']['srcport'] = True

    if srcportop:
        payload['nspbr']['srcportop'] = True

    if srcportval:
        payload['nspbr']['srcportval'] = True

    if destip:
        payload['nspbr']['destip'] = True

    if destipop:
        payload['nspbr']['destipop'] = True

    if destipval:
        payload['nspbr']['destipval'] = True

    if destport:
        payload['nspbr']['destport'] = True

    if destportop:
        payload['nspbr']['destportop'] = True

    if destportval:
        payload['nspbr']['destportval'] = True

    if nexthop:
        payload['nspbr']['nexthop'] = True

    if nexthopval:
        payload['nspbr']['nexthopval'] = True

    if iptunnel:
        payload['nspbr']['iptunnel'] = True

    if iptunnelname:
        payload['nspbr']['iptunnelname'] = True

    if vxlanvlanmap:
        payload['nspbr']['vxlanvlanmap'] = True

    if srcmac:
        payload['nspbr']['srcmac'] = True

    if srcmacmask:
        payload['nspbr']['srcmacmask'] = True

    if protocol:
        payload['nspbr']['protocol'] = True

    if protocolnumber:
        payload['nspbr']['protocolnumber'] = True

    if vlan:
        payload['nspbr']['vlan'] = True

    if vxlan:
        payload['nspbr']['vxlan'] = True

    if interface:
        payload['nspbr']['Interface'] = True

    if priority:
        payload['nspbr']['priority'] = True

    if msr:
        payload['nspbr']['msr'] = True

    if monitor:
        payload['nspbr']['monitor'] = True

    if state:
        payload['nspbr']['state'] = True

    if ownergroup:
        payload['nspbr']['ownergroup'] = True

    if detail:
        payload['nspbr']['detail'] = True

    execution = __proxy__['citrixns.post']('config/nspbr?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nspbr6(name=None, td=None, action=None, srcipv6=None, srcipop=None, srcipv6val=None, srcport=None,
                 srcportop=None, srcportval=None, destipv6=None, destipop=None, destipv6val=None, destport=None,
                 destportop=None, destportval=None, srcmac=None, srcmacmask=None, protocol=None, protocolnumber=None,
                 vlan=None, vxlan=None, interface=None, priority=None, state=None, msr=None, monitor=None, nexthop=None,
                 nexthopval=None, iptunnel=None, vxlanvlanmap=None, nexthopvlan=None, ownergroup=None, detail=None,
                 save=False):
    '''
    Unsets values from the nspbr6 configuration key.

    name(bool): Unsets the name value.

    td(bool): Unsets the td value.

    action(bool): Unsets the action value.

    srcipv6(bool): Unsets the srcipv6 value.

    srcipop(bool): Unsets the srcipop value.

    srcipv6val(bool): Unsets the srcipv6val value.

    srcport(bool): Unsets the srcport value.

    srcportop(bool): Unsets the srcportop value.

    srcportval(bool): Unsets the srcportval value.

    destipv6(bool): Unsets the destipv6 value.

    destipop(bool): Unsets the destipop value.

    destipv6val(bool): Unsets the destipv6val value.

    destport(bool): Unsets the destport value.

    destportop(bool): Unsets the destportop value.

    destportval(bool): Unsets the destportval value.

    srcmac(bool): Unsets the srcmac value.

    srcmacmask(bool): Unsets the srcmacmask value.

    protocol(bool): Unsets the protocol value.

    protocolnumber(bool): Unsets the protocolnumber value.

    vlan(bool): Unsets the vlan value.

    vxlan(bool): Unsets the vxlan value.

    interface(bool): Unsets the interface value.

    priority(bool): Unsets the priority value.

    state(bool): Unsets the state value.

    msr(bool): Unsets the msr value.

    monitor(bool): Unsets the monitor value.

    nexthop(bool): Unsets the nexthop value.

    nexthopval(bool): Unsets the nexthopval value.

    iptunnel(bool): Unsets the iptunnel value.

    vxlanvlanmap(bool): Unsets the vxlanvlanmap value.

    nexthopvlan(bool): Unsets the nexthopvlan value.

    ownergroup(bool): Unsets the ownergroup value.

    detail(bool): Unsets the detail value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nspbr6 <args>

    '''

    result = {}

    payload = {'nspbr6': {}}

    if name:
        payload['nspbr6']['name'] = True

    if td:
        payload['nspbr6']['td'] = True

    if action:
        payload['nspbr6']['action'] = True

    if srcipv6:
        payload['nspbr6']['srcipv6'] = True

    if srcipop:
        payload['nspbr6']['srcipop'] = True

    if srcipv6val:
        payload['nspbr6']['srcipv6val'] = True

    if srcport:
        payload['nspbr6']['srcport'] = True

    if srcportop:
        payload['nspbr6']['srcportop'] = True

    if srcportval:
        payload['nspbr6']['srcportval'] = True

    if destipv6:
        payload['nspbr6']['destipv6'] = True

    if destipop:
        payload['nspbr6']['destipop'] = True

    if destipv6val:
        payload['nspbr6']['destipv6val'] = True

    if destport:
        payload['nspbr6']['destport'] = True

    if destportop:
        payload['nspbr6']['destportop'] = True

    if destportval:
        payload['nspbr6']['destportval'] = True

    if srcmac:
        payload['nspbr6']['srcmac'] = True

    if srcmacmask:
        payload['nspbr6']['srcmacmask'] = True

    if protocol:
        payload['nspbr6']['protocol'] = True

    if protocolnumber:
        payload['nspbr6']['protocolnumber'] = True

    if vlan:
        payload['nspbr6']['vlan'] = True

    if vxlan:
        payload['nspbr6']['vxlan'] = True

    if interface:
        payload['nspbr6']['Interface'] = True

    if priority:
        payload['nspbr6']['priority'] = True

    if state:
        payload['nspbr6']['state'] = True

    if msr:
        payload['nspbr6']['msr'] = True

    if monitor:
        payload['nspbr6']['monitor'] = True

    if nexthop:
        payload['nspbr6']['nexthop'] = True

    if nexthopval:
        payload['nspbr6']['nexthopval'] = True

    if iptunnel:
        payload['nspbr6']['iptunnel'] = True

    if vxlanvlanmap:
        payload['nspbr6']['vxlanvlanmap'] = True

    if nexthopvlan:
        payload['nspbr6']['nexthopvlan'] = True

    if ownergroup:
        payload['nspbr6']['ownergroup'] = True

    if detail:
        payload['nspbr6']['detail'] = True

    execution = __proxy__['citrixns.post']('config/nspbr6?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsratecontrol(tcpthreshold=None, udpthreshold=None, icmpthreshold=None, tcprstthreshold=None, save=False):
    '''
    Unsets values from the nsratecontrol configuration key.

    tcpthreshold(bool): Unsets the tcpthreshold value.

    udpthreshold(bool): Unsets the udpthreshold value.

    icmpthreshold(bool): Unsets the icmpthreshold value.

    tcprstthreshold(bool): Unsets the tcprstthreshold value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsratecontrol <args>

    '''

    result = {}

    payload = {'nsratecontrol': {}}

    if tcpthreshold:
        payload['nsratecontrol']['tcpthreshold'] = True

    if udpthreshold:
        payload['nsratecontrol']['udpthreshold'] = True

    if icmpthreshold:
        payload['nsratecontrol']['icmpthreshold'] = True

    if tcprstthreshold:
        payload['nsratecontrol']['tcprstthreshold'] = True

    execution = __proxy__['citrixns.post']('config/nsratecontrol?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsrpcnode(ipaddress=None, password=None, srcip=None, secure=None, save=False):
    '''
    Unsets values from the nsrpcnode configuration key.

    ipaddress(bool): Unsets the ipaddress value.

    password(bool): Unsets the password value.

    srcip(bool): Unsets the srcip value.

    secure(bool): Unsets the secure value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsrpcnode <args>

    '''

    result = {}

    payload = {'nsrpcnode': {}}

    if ipaddress:
        payload['nsrpcnode']['ipaddress'] = True

    if password:
        payload['nsrpcnode']['password'] = True

    if srcip:
        payload['nsrpcnode']['srcip'] = True

    if secure:
        payload['nsrpcnode']['secure'] = True

    execution = __proxy__['citrixns.post']('config/nsrpcnode?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsspparams(basethreshold=None, throttle=None, save=False):
    '''
    Unsets values from the nsspparams configuration key.

    basethreshold(bool): Unsets the basethreshold value.

    throttle(bool): Unsets the throttle value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsspparams <args>

    '''

    result = {}

    payload = {'nsspparams': {}}

    if basethreshold:
        payload['nsspparams']['basethreshold'] = True

    if throttle:
        payload['nsspparams']['throttle'] = True

    execution = __proxy__['citrixns.post']('config/nsspparams?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nstcpbufparam(size=None, memlimit=None, save=False):
    '''
    Unsets values from the nstcpbufparam configuration key.

    size(bool): Unsets the size value.

    memlimit(bool): Unsets the memlimit value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nstcpbufparam <args>

    '''

    result = {}

    payload = {'nstcpbufparam': {}}

    if size:
        payload['nstcpbufparam']['size'] = True

    if memlimit:
        payload['nstcpbufparam']['memlimit'] = True

    execution = __proxy__['citrixns.post']('config/nstcpbufparam?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nstcpparam(ws=None, wsval=None, sack=None, learnvsvrmss=None, maxburst=None, initialcwnd=None,
                     recvbuffsize=None, delayedack=None, downstaterst=None, nagle=None, limitedpersist=None,
                     oooqsize=None, ackonpush=None, maxpktpermss=None, pktperretx=None, minrto=None, slowstartincr=None,
                     maxdynserverprobes=None, synholdfastgiveup=None, maxsynholdperprobe=None, maxsynhold=None,
                     msslearninterval=None, msslearndelay=None, maxtimewaitconn=None, kaprobeupdatelastactivity=None,
                     maxsynackretx=None, synattackdetection=None, connflushifnomem=None, connflushthres=None,
                     mptcpconcloseonpassivesf=None, mptcpchecksum=None, mptcpsftimeout=None, mptcpsfreplacetimeout=None,
                     mptcpmaxsf=None, mptcpmaxpendingsf=None, mptcppendingjointhreshold=None, mptcprtostoswitchsf=None,
                     mptcpusebackupondss=None, tcpmaxretries=None, mptcpimmediatesfcloseonfin=None,
                     mptcpclosemptcpsessiononlastsfclose=None, tcpfastopencookietimeout=None, autosyncookietimeout=None,
                     save=False):
    '''
    Unsets values from the nstcpparam configuration key.

    ws(bool): Unsets the ws value.

    wsval(bool): Unsets the wsval value.

    sack(bool): Unsets the sack value.

    learnvsvrmss(bool): Unsets the learnvsvrmss value.

    maxburst(bool): Unsets the maxburst value.

    initialcwnd(bool): Unsets the initialcwnd value.

    recvbuffsize(bool): Unsets the recvbuffsize value.

    delayedack(bool): Unsets the delayedack value.

    downstaterst(bool): Unsets the downstaterst value.

    nagle(bool): Unsets the nagle value.

    limitedpersist(bool): Unsets the limitedpersist value.

    oooqsize(bool): Unsets the oooqsize value.

    ackonpush(bool): Unsets the ackonpush value.

    maxpktpermss(bool): Unsets the maxpktpermss value.

    pktperretx(bool): Unsets the pktperretx value.

    minrto(bool): Unsets the minrto value.

    slowstartincr(bool): Unsets the slowstartincr value.

    maxdynserverprobes(bool): Unsets the maxdynserverprobes value.

    synholdfastgiveup(bool): Unsets the synholdfastgiveup value.

    maxsynholdperprobe(bool): Unsets the maxsynholdperprobe value.

    maxsynhold(bool): Unsets the maxsynhold value.

    msslearninterval(bool): Unsets the msslearninterval value.

    msslearndelay(bool): Unsets the msslearndelay value.

    maxtimewaitconn(bool): Unsets the maxtimewaitconn value.

    kaprobeupdatelastactivity(bool): Unsets the kaprobeupdatelastactivity value.

    maxsynackretx(bool): Unsets the maxsynackretx value.

    synattackdetection(bool): Unsets the synattackdetection value.

    connflushifnomem(bool): Unsets the connflushifnomem value.

    connflushthres(bool): Unsets the connflushthres value.

    mptcpconcloseonpassivesf(bool): Unsets the mptcpconcloseonpassivesf value.

    mptcpchecksum(bool): Unsets the mptcpchecksum value.

    mptcpsftimeout(bool): Unsets the mptcpsftimeout value.

    mptcpsfreplacetimeout(bool): Unsets the mptcpsfreplacetimeout value.

    mptcpmaxsf(bool): Unsets the mptcpmaxsf value.

    mptcpmaxpendingsf(bool): Unsets the mptcpmaxpendingsf value.

    mptcppendingjointhreshold(bool): Unsets the mptcppendingjointhreshold value.

    mptcprtostoswitchsf(bool): Unsets the mptcprtostoswitchsf value.

    mptcpusebackupondss(bool): Unsets the mptcpusebackupondss value.

    tcpmaxretries(bool): Unsets the tcpmaxretries value.

    mptcpimmediatesfcloseonfin(bool): Unsets the mptcpimmediatesfcloseonfin value.

    mptcpclosemptcpsessiononlastsfclose(bool): Unsets the mptcpclosemptcpsessiononlastsfclose value.

    tcpfastopencookietimeout(bool): Unsets the tcpfastopencookietimeout value.

    autosyncookietimeout(bool): Unsets the autosyncookietimeout value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nstcpparam <args>

    '''

    result = {}

    payload = {'nstcpparam': {}}

    if ws:
        payload['nstcpparam']['ws'] = True

    if wsval:
        payload['nstcpparam']['wsval'] = True

    if sack:
        payload['nstcpparam']['sack'] = True

    if learnvsvrmss:
        payload['nstcpparam']['learnvsvrmss'] = True

    if maxburst:
        payload['nstcpparam']['maxburst'] = True

    if initialcwnd:
        payload['nstcpparam']['initialcwnd'] = True

    if recvbuffsize:
        payload['nstcpparam']['recvbuffsize'] = True

    if delayedack:
        payload['nstcpparam']['delayedack'] = True

    if downstaterst:
        payload['nstcpparam']['downstaterst'] = True

    if nagle:
        payload['nstcpparam']['nagle'] = True

    if limitedpersist:
        payload['nstcpparam']['limitedpersist'] = True

    if oooqsize:
        payload['nstcpparam']['oooqsize'] = True

    if ackonpush:
        payload['nstcpparam']['ackonpush'] = True

    if maxpktpermss:
        payload['nstcpparam']['maxpktpermss'] = True

    if pktperretx:
        payload['nstcpparam']['pktperretx'] = True

    if minrto:
        payload['nstcpparam']['minrto'] = True

    if slowstartincr:
        payload['nstcpparam']['slowstartincr'] = True

    if maxdynserverprobes:
        payload['nstcpparam']['maxdynserverprobes'] = True

    if synholdfastgiveup:
        payload['nstcpparam']['synholdfastgiveup'] = True

    if maxsynholdperprobe:
        payload['nstcpparam']['maxsynholdperprobe'] = True

    if maxsynhold:
        payload['nstcpparam']['maxsynhold'] = True

    if msslearninterval:
        payload['nstcpparam']['msslearninterval'] = True

    if msslearndelay:
        payload['nstcpparam']['msslearndelay'] = True

    if maxtimewaitconn:
        payload['nstcpparam']['maxtimewaitconn'] = True

    if kaprobeupdatelastactivity:
        payload['nstcpparam']['kaprobeupdatelastactivity'] = True

    if maxsynackretx:
        payload['nstcpparam']['maxsynackretx'] = True

    if synattackdetection:
        payload['nstcpparam']['synattackdetection'] = True

    if connflushifnomem:
        payload['nstcpparam']['connflushifnomem'] = True

    if connflushthres:
        payload['nstcpparam']['connflushthres'] = True

    if mptcpconcloseonpassivesf:
        payload['nstcpparam']['mptcpconcloseonpassivesf'] = True

    if mptcpchecksum:
        payload['nstcpparam']['mptcpchecksum'] = True

    if mptcpsftimeout:
        payload['nstcpparam']['mptcpsftimeout'] = True

    if mptcpsfreplacetimeout:
        payload['nstcpparam']['mptcpsfreplacetimeout'] = True

    if mptcpmaxsf:
        payload['nstcpparam']['mptcpmaxsf'] = True

    if mptcpmaxpendingsf:
        payload['nstcpparam']['mptcpmaxpendingsf'] = True

    if mptcppendingjointhreshold:
        payload['nstcpparam']['mptcppendingjointhreshold'] = True

    if mptcprtostoswitchsf:
        payload['nstcpparam']['mptcprtostoswitchsf'] = True

    if mptcpusebackupondss:
        payload['nstcpparam']['mptcpusebackupondss'] = True

    if tcpmaxretries:
        payload['nstcpparam']['tcpmaxretries'] = True

    if mptcpimmediatesfcloseonfin:
        payload['nstcpparam']['mptcpimmediatesfcloseonfin'] = True

    if mptcpclosemptcpsessiononlastsfclose:
        payload['nstcpparam']['mptcpclosemptcpsessiononlastsfclose'] = True

    if tcpfastopencookietimeout:
        payload['nstcpparam']['tcpfastopencookietimeout'] = True

    if autosyncookietimeout:
        payload['nstcpparam']['autosyncookietimeout'] = True

    execution = __proxy__['citrixns.post']('config/nstcpparam?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nstcpprofile(name=None, ws=None, sack=None, wsval=None, nagle=None, ackonpush=None, mss=None, maxburst=None,
                       initialcwnd=None, delayedack=None, oooqsize=None, maxpktpermss=None, pktperretx=None, minrto=None,
                       slowstartincr=None, buffersize=None, syncookie=None, kaprobeupdatelastactivity=None, flavor=None,
                       dynamicreceivebuffering=None, ka=None, kaconnidletime=None, kamaxprobes=None,
                       kaprobeinterval=None, sendbuffsize=None, mptcp=None, establishclientconn=None, tcpsegoffload=None,
                       rstwindowattenuate=None, rstmaxack=None, spoofsyndrop=None, ecn=None,
                       mptcpdropdataonpreestsf=None, mptcpfastopen=None, mptcpsessiontimeout=None, timestamp=None,
                       dsack=None, ackaggregation=None, frto=None, maxcwnd=None, fack=None, tcpmode=None,
                       tcpfastopen=None, hystart=None, dupackthresh=None, burstratecontrol=None, tcprate=None,
                       rateqmax=None, drophalfclosedconnontimeout=None, dropestconnontimeout=None, save=False):
    '''
    Unsets values from the nstcpprofile configuration key.

    name(bool): Unsets the name value.

    ws(bool): Unsets the ws value.

    sack(bool): Unsets the sack value.

    wsval(bool): Unsets the wsval value.

    nagle(bool): Unsets the nagle value.

    ackonpush(bool): Unsets the ackonpush value.

    mss(bool): Unsets the mss value.

    maxburst(bool): Unsets the maxburst value.

    initialcwnd(bool): Unsets the initialcwnd value.

    delayedack(bool): Unsets the delayedack value.

    oooqsize(bool): Unsets the oooqsize value.

    maxpktpermss(bool): Unsets the maxpktpermss value.

    pktperretx(bool): Unsets the pktperretx value.

    minrto(bool): Unsets the minrto value.

    slowstartincr(bool): Unsets the slowstartincr value.

    buffersize(bool): Unsets the buffersize value.

    syncookie(bool): Unsets the syncookie value.

    kaprobeupdatelastactivity(bool): Unsets the kaprobeupdatelastactivity value.

    flavor(bool): Unsets the flavor value.

    dynamicreceivebuffering(bool): Unsets the dynamicreceivebuffering value.

    ka(bool): Unsets the ka value.

    kaconnidletime(bool): Unsets the kaconnidletime value.

    kamaxprobes(bool): Unsets the kamaxprobes value.

    kaprobeinterval(bool): Unsets the kaprobeinterval value.

    sendbuffsize(bool): Unsets the sendbuffsize value.

    mptcp(bool): Unsets the mptcp value.

    establishclientconn(bool): Unsets the establishclientconn value.

    tcpsegoffload(bool): Unsets the tcpsegoffload value.

    rstwindowattenuate(bool): Unsets the rstwindowattenuate value.

    rstmaxack(bool): Unsets the rstmaxack value.

    spoofsyndrop(bool): Unsets the spoofsyndrop value.

    ecn(bool): Unsets the ecn value.

    mptcpdropdataonpreestsf(bool): Unsets the mptcpdropdataonpreestsf value.

    mptcpfastopen(bool): Unsets the mptcpfastopen value.

    mptcpsessiontimeout(bool): Unsets the mptcpsessiontimeout value.

    timestamp(bool): Unsets the timestamp value.

    dsack(bool): Unsets the dsack value.

    ackaggregation(bool): Unsets the ackaggregation value.

    frto(bool): Unsets the frto value.

    maxcwnd(bool): Unsets the maxcwnd value.

    fack(bool): Unsets the fack value.

    tcpmode(bool): Unsets the tcpmode value.

    tcpfastopen(bool): Unsets the tcpfastopen value.

    hystart(bool): Unsets the hystart value.

    dupackthresh(bool): Unsets the dupackthresh value.

    burstratecontrol(bool): Unsets the burstratecontrol value.

    tcprate(bool): Unsets the tcprate value.

    rateqmax(bool): Unsets the rateqmax value.

    drophalfclosedconnontimeout(bool): Unsets the drophalfclosedconnontimeout value.

    dropestconnontimeout(bool): Unsets the dropestconnontimeout value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nstcpprofile <args>

    '''

    result = {}

    payload = {'nstcpprofile': {}}

    if name:
        payload['nstcpprofile']['name'] = True

    if ws:
        payload['nstcpprofile']['ws'] = True

    if sack:
        payload['nstcpprofile']['sack'] = True

    if wsval:
        payload['nstcpprofile']['wsval'] = True

    if nagle:
        payload['nstcpprofile']['nagle'] = True

    if ackonpush:
        payload['nstcpprofile']['ackonpush'] = True

    if mss:
        payload['nstcpprofile']['mss'] = True

    if maxburst:
        payload['nstcpprofile']['maxburst'] = True

    if initialcwnd:
        payload['nstcpprofile']['initialcwnd'] = True

    if delayedack:
        payload['nstcpprofile']['delayedack'] = True

    if oooqsize:
        payload['nstcpprofile']['oooqsize'] = True

    if maxpktpermss:
        payload['nstcpprofile']['maxpktpermss'] = True

    if pktperretx:
        payload['nstcpprofile']['pktperretx'] = True

    if minrto:
        payload['nstcpprofile']['minrto'] = True

    if slowstartincr:
        payload['nstcpprofile']['slowstartincr'] = True

    if buffersize:
        payload['nstcpprofile']['buffersize'] = True

    if syncookie:
        payload['nstcpprofile']['syncookie'] = True

    if kaprobeupdatelastactivity:
        payload['nstcpprofile']['kaprobeupdatelastactivity'] = True

    if flavor:
        payload['nstcpprofile']['flavor'] = True

    if dynamicreceivebuffering:
        payload['nstcpprofile']['dynamicreceivebuffering'] = True

    if ka:
        payload['nstcpprofile']['ka'] = True

    if kaconnidletime:
        payload['nstcpprofile']['kaconnidletime'] = True

    if kamaxprobes:
        payload['nstcpprofile']['kamaxprobes'] = True

    if kaprobeinterval:
        payload['nstcpprofile']['kaprobeinterval'] = True

    if sendbuffsize:
        payload['nstcpprofile']['sendbuffsize'] = True

    if mptcp:
        payload['nstcpprofile']['mptcp'] = True

    if establishclientconn:
        payload['nstcpprofile']['establishclientconn'] = True

    if tcpsegoffload:
        payload['nstcpprofile']['tcpsegoffload'] = True

    if rstwindowattenuate:
        payload['nstcpprofile']['rstwindowattenuate'] = True

    if rstmaxack:
        payload['nstcpprofile']['rstmaxack'] = True

    if spoofsyndrop:
        payload['nstcpprofile']['spoofsyndrop'] = True

    if ecn:
        payload['nstcpprofile']['ecn'] = True

    if mptcpdropdataonpreestsf:
        payload['nstcpprofile']['mptcpdropdataonpreestsf'] = True

    if mptcpfastopen:
        payload['nstcpprofile']['mptcpfastopen'] = True

    if mptcpsessiontimeout:
        payload['nstcpprofile']['mptcpsessiontimeout'] = True

    if timestamp:
        payload['nstcpprofile']['timestamp'] = True

    if dsack:
        payload['nstcpprofile']['dsack'] = True

    if ackaggregation:
        payload['nstcpprofile']['ackaggregation'] = True

    if frto:
        payload['nstcpprofile']['frto'] = True

    if maxcwnd:
        payload['nstcpprofile']['maxcwnd'] = True

    if fack:
        payload['nstcpprofile']['fack'] = True

    if tcpmode:
        payload['nstcpprofile']['tcpmode'] = True

    if tcpfastopen:
        payload['nstcpprofile']['tcpfastopen'] = True

    if hystart:
        payload['nstcpprofile']['hystart'] = True

    if dupackthresh:
        payload['nstcpprofile']['dupackthresh'] = True

    if burstratecontrol:
        payload['nstcpprofile']['burstratecontrol'] = True

    if tcprate:
        payload['nstcpprofile']['tcprate'] = True

    if rateqmax:
        payload['nstcpprofile']['rateqmax'] = True

    if drophalfclosedconnontimeout:
        payload['nstcpprofile']['drophalfclosedconnontimeout'] = True

    if dropestconnontimeout:
        payload['nstcpprofile']['dropestconnontimeout'] = True

    execution = __proxy__['citrixns.post']('config/nstcpprofile?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nstimeout(zombie=None, client=None, server=None, httpclient=None, httpserver=None, tcpclient=None,
                    tcpserver=None, anyclient=None, anyserver=None, anytcpclient=None, anytcpserver=None, halfclose=None,
                    nontcpzombie=None, reducedfintimeout=None, reducedrsttimeout=None, newconnidletimeout=None,
                    save=False):
    '''
    Unsets values from the nstimeout configuration key.

    zombie(bool): Unsets the zombie value.

    client(bool): Unsets the client value.

    server(bool): Unsets the server value.

    httpclient(bool): Unsets the httpclient value.

    httpserver(bool): Unsets the httpserver value.

    tcpclient(bool): Unsets the tcpclient value.

    tcpserver(bool): Unsets the tcpserver value.

    anyclient(bool): Unsets the anyclient value.

    anyserver(bool): Unsets the anyserver value.

    anytcpclient(bool): Unsets the anytcpclient value.

    anytcpserver(bool): Unsets the anytcpserver value.

    halfclose(bool): Unsets the halfclose value.

    nontcpzombie(bool): Unsets the nontcpzombie value.

    reducedfintimeout(bool): Unsets the reducedfintimeout value.

    reducedrsttimeout(bool): Unsets the reducedrsttimeout value.

    newconnidletimeout(bool): Unsets the newconnidletimeout value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nstimeout <args>

    '''

    result = {}

    payload = {'nstimeout': {}}

    if zombie:
        payload['nstimeout']['zombie'] = True

    if client:
        payload['nstimeout']['client'] = True

    if server:
        payload['nstimeout']['server'] = True

    if httpclient:
        payload['nstimeout']['httpclient'] = True

    if httpserver:
        payload['nstimeout']['httpserver'] = True

    if tcpclient:
        payload['nstimeout']['tcpclient'] = True

    if tcpserver:
        payload['nstimeout']['tcpserver'] = True

    if anyclient:
        payload['nstimeout']['anyclient'] = True

    if anyserver:
        payload['nstimeout']['anyserver'] = True

    if anytcpclient:
        payload['nstimeout']['anytcpclient'] = True

    if anytcpserver:
        payload['nstimeout']['anytcpserver'] = True

    if halfclose:
        payload['nstimeout']['halfclose'] = True

    if nontcpzombie:
        payload['nstimeout']['nontcpzombie'] = True

    if reducedfintimeout:
        payload['nstimeout']['reducedfintimeout'] = True

    if reducedrsttimeout:
        payload['nstimeout']['reducedrsttimeout'] = True

    if newconnidletimeout:
        payload['nstimeout']['newconnidletimeout'] = True

    execution = __proxy__['citrixns.post']('config/nstimeout?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nstimer(name=None, interval=None, unit=None, comment=None, newname=None, save=False):
    '''
    Unsets values from the nstimer configuration key.

    name(bool): Unsets the name value.

    interval(bool): Unsets the interval value.

    unit(bool): Unsets the unit value.

    comment(bool): Unsets the comment value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nstimer <args>

    '''

    result = {}

    payload = {'nstimer': {}}

    if name:
        payload['nstimer']['name'] = True

    if interval:
        payload['nstimer']['interval'] = True

    if unit:
        payload['nstimer']['unit'] = True

    if comment:
        payload['nstimer']['comment'] = True

    if newname:
        payload['nstimer']['newname'] = True

    execution = __proxy__['citrixns.post']('config/nstimer?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsvariable(name=None, ns_type=None, scope=None, iffull=None, ifvaluetoobig=None, ifnovalue=None, init=None,
                     expires=None, comment=None, save=False):
    '''
    Unsets values from the nsvariable configuration key.

    name(bool): Unsets the name value.

    ns_type(bool): Unsets the ns_type value.

    scope(bool): Unsets the scope value.

    iffull(bool): Unsets the iffull value.

    ifvaluetoobig(bool): Unsets the ifvaluetoobig value.

    ifnovalue(bool): Unsets the ifnovalue value.

    init(bool): Unsets the init value.

    expires(bool): Unsets the expires value.

    comment(bool): Unsets the comment value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsvariable <args>

    '''

    result = {}

    payload = {'nsvariable': {}}

    if name:
        payload['nsvariable']['name'] = True

    if ns_type:
        payload['nsvariable']['type'] = True

    if scope:
        payload['nsvariable']['scope'] = True

    if iffull:
        payload['nsvariable']['iffull'] = True

    if ifvaluetoobig:
        payload['nsvariable']['ifvaluetoobig'] = True

    if ifnovalue:
        payload['nsvariable']['ifnovalue'] = True

    if init:
        payload['nsvariable']['init'] = True

    if expires:
        payload['nsvariable']['expires'] = True

    if comment:
        payload['nsvariable']['comment'] = True

    execution = __proxy__['citrixns.post']('config/nsvariable?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsweblogparam(buffersizemb=None, customreqhdrs=None, customrsphdrs=None, save=False):
    '''
    Unsets values from the nsweblogparam configuration key.

    buffersizemb(bool): Unsets the buffersizemb value.

    customreqhdrs(bool): Unsets the customreqhdrs value.

    customrsphdrs(bool): Unsets the customrsphdrs value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsweblogparam <args>

    '''

    result = {}

    payload = {'nsweblogparam': {}}

    if buffersizemb:
        payload['nsweblogparam']['buffersizemb'] = True

    if customreqhdrs:
        payload['nsweblogparam']['customreqhdrs'] = True

    if customrsphdrs:
        payload['nsweblogparam']['customrsphdrs'] = True

    execution = __proxy__['citrixns.post']('config/nsweblogparam?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_nsxmlnamespace(prefix=None, namespace=None, description=None, save=False):
    '''
    Unsets values from the nsxmlnamespace configuration key.

    prefix(bool): Unsets the prefix value.

    namespace(bool): Unsets the namespace value.

    description(bool): Unsets the description value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.unset_nsxmlnamespace <args>

    '''

    result = {}

    payload = {'nsxmlnamespace': {}}

    if prefix:
        payload['nsxmlnamespace']['prefix'] = True

    if namespace:
        payload['nsxmlnamespace']['Namespace'] = True

    if description:
        payload['nsxmlnamespace']['description'] = True

    execution = __proxy__['citrixns.post']('config/nsxmlnamespace?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsacl(aclname=None, aclaction=None, td=None, srcip=None, srcipop=None, srcipval=None, srcport=None,
                 srcportop=None, srcportval=None, destip=None, destipop=None, destipval=None, destport=None,
                 destportop=None, destportval=None, ttl=None, srcmac=None, srcmacmask=None, protocol=None,
                 protocolnumber=None, vlan=None, vxlan=None, interface=None, established=None, icmptype=None,
                 icmpcode=None, priority=None, state=None, logstate=None, ratelimit=None, newname=None, save=False):
    '''
    Update the running configuration for the nsacl config key.

    aclname(str): Name for the extended ACL rule. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Minimum length = 1

    aclaction(str): Action to perform on incoming IPv4 packets that match the extended ACL rule. Available settings function
        as follows: * ALLOW - The NetScaler appliance processes the packet. * BRIDGE - The NetScaler appliance bridges
        the packet to the destination without processing it. * DENY - The NetScaler appliance drops the packet. Possible
        values = BRIDGE, DENY, ALLOW

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcip(bool): IP address or range of IP addresses to match against the source IP address of an incoming IPv4 packet. In
        the command line interface, separate the range with a hyphen. For example: 10.102.29.30-10.102.29.189.

    srcipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcipval(str): IP address or range of IP addresses to match against the source IP address of an incoming IPv4 packet. In
        the command line interface, separate the range with a hyphen. For example:10.102.29.30-10.102.29.189.

    srcport(bool): Port number or range of port numbers to match against the source port number of an incoming IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90.

    srcportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcportval(str): Port number or range of port numbers to match against the source port number of an incoming IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90. Maximum length = 65535

    destip(bool): IP address or range of IP addresses to match against the destination IP address of an incoming IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 10.102.29.30-10.102.29.189.

    destipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destipval(str): IP address or range of IP addresses to match against the destination IP address of an incoming IPv4
        packet. In the command line interface, separate the range with a hyphen. For example:
        10.102.29.30-10.102.29.189.

    destport(bool): Port number or range of port numbers to match against the destination port number of an incoming IPv4
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols.

    destportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destportval(str): Port number or range of port numbers to match against the destination port number of an incoming IPv4
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols. Maximum length = 65535

    ttl(int): Number of seconds, in multiples of four, after which the extended ACL rule expires. If you do not want the
        extended ACL rule to expire, do not specify a TTL value. Minimum value = 1 Maximum value = 2147483647

    srcmac(str): MAC address to match against the source MAC address of an incoming IPv4 packet.

    srcmacmask(str): Used to define range of Source MAC address. It takes string of 0 and 1, 0s are for exact match and 1s
        for wildcard. For matching first 3 bytes of MAC address, srcMacMask value "000000111111". . Default value:
        "000000000000"

    protocol(str): Protocol to match against the protocol of an incoming IPv4 packet. Possible values = ICMP, IGMP, TCP, EGP,
        IGP, ARGUS, UDP, RDP, RSVP, EIGRP, L2TP, ISIS

    protocolnumber(int): Protocol to match against the protocol of an incoming IPv4 packet. Minimum value = 1 Maximum value =
        255

    vlan(int): ID of the VLAN. The NetScaler appliance applies the ACL rule only to the incoming packets of the specified
        VLAN. If you do not specify a VLAN ID, the appliance applies the ACL rule to the incoming packets on all VLANs.
        Minimum value = 1 Maximum value = 4094

    vxlan(int): ID of the VXLAN. The NetScaler appliance applies the ACL rule only to the incoming packets of the specified
        VXLAN. If you do not specify a VXLAN ID, the appliance applies the ACL rule to the incoming packets on all
        VXLANs. Minimum value = 1 Maximum value = 16777215

    interface(str): ID of an interface. The NetScaler appliance applies the ACL rule only to the incoming packets from the
        specified interface. If you do not specify any value, the appliance applies the ACL rule to the incoming packets
        of all interfaces.

    established(bool): Allow only incoming TCP packets that have the ACK or RST bit set, if the action set for the ACL rule
        is ALLOW and these packets match the other conditions in the ACL rule.

    icmptype(int): ICMP Message type to match against the message type of an incoming ICMP packet. For example, to block
        DESTINATION UNREACHABLE messages, you must specify 3 as the ICMP type.  Note: This parameter can be specified
        only for the ICMP protocol. Minimum value = 0 Maximum value = 65536

    icmpcode(int): Code of a particular ICMP message type to match against the ICMP code of an incoming ICMP packet. For
        example, to block DESTINATION HOST UNREACHABLE messages, specify 3 as the ICMP type and 1 as the ICMP code.  If
        you set this parameter, you must set the ICMP Type parameter. Minimum value = 0 Maximum value = 65536

    priority(int): Priority for the extended ACL rule that determines the order in which it is evaluated relative to the
        other extended ACL rules. If you do not specify priorities while creating extended ACL rules, the ACL rules are
        evaluated in the order in which they are created. Minimum value = 1 Maximum value = 100000

    state(str): Enable or disable the extended ACL rule. After you apply the extended ACL rules, the NetScaler appliance
        compares incoming packets against the enabled extended ACL rules. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    logstate(str): Enable or disable logging of events related to the extended ACL rule. The log messages are stored in the
        configured syslog or auditlog server. Default value: DISABLED Possible values = ENABLED, DISABLED

    ratelimit(int): Maximum number of log messages to be generated per second. If you set this parameter, you must enable the
        Log State parameter. Default value: 100 Minimum value = 1 Maximum value = 10000

    newname(str): New name for the extended ACL rule. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsacl <args>

    '''

    result = {}

    payload = {'nsacl': {}}

    if aclname:
        payload['nsacl']['aclname'] = aclname

    if aclaction:
        payload['nsacl']['aclaction'] = aclaction

    if td:
        payload['nsacl']['td'] = td

    if srcip:
        payload['nsacl']['srcip'] = srcip

    if srcipop:
        payload['nsacl']['srcipop'] = srcipop

    if srcipval:
        payload['nsacl']['srcipval'] = srcipval

    if srcport:
        payload['nsacl']['srcport'] = srcport

    if srcportop:
        payload['nsacl']['srcportop'] = srcportop

    if srcportval:
        payload['nsacl']['srcportval'] = srcportval

    if destip:
        payload['nsacl']['destip'] = destip

    if destipop:
        payload['nsacl']['destipop'] = destipop

    if destipval:
        payload['nsacl']['destipval'] = destipval

    if destport:
        payload['nsacl']['destport'] = destport

    if destportop:
        payload['nsacl']['destportop'] = destportop

    if destportval:
        payload['nsacl']['destportval'] = destportval

    if ttl:
        payload['nsacl']['ttl'] = ttl

    if srcmac:
        payload['nsacl']['srcmac'] = srcmac

    if srcmacmask:
        payload['nsacl']['srcmacmask'] = srcmacmask

    if protocol:
        payload['nsacl']['protocol'] = protocol

    if protocolnumber:
        payload['nsacl']['protocolnumber'] = protocolnumber

    if vlan:
        payload['nsacl']['vlan'] = vlan

    if vxlan:
        payload['nsacl']['vxlan'] = vxlan

    if interface:
        payload['nsacl']['Interface'] = interface

    if established:
        payload['nsacl']['established'] = established

    if icmptype:
        payload['nsacl']['icmptype'] = icmptype

    if icmpcode:
        payload['nsacl']['icmpcode'] = icmpcode

    if priority:
        payload['nsacl']['priority'] = priority

    if state:
        payload['nsacl']['state'] = state

    if logstate:
        payload['nsacl']['logstate'] = logstate

    if ratelimit:
        payload['nsacl']['ratelimit'] = ratelimit

    if newname:
        payload['nsacl']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/nsacl', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsacl6(acl6name=None, acl6action=None, td=None, srcipv6=None, srcipop=None, srcipv6val=None, srcport=None,
                  srcportop=None, srcportval=None, destipv6=None, destipop=None, destipv6val=None, destport=None,
                  destportop=None, destportval=None, ttl=None, srcmac=None, srcmacmask=None, protocol=None,
                  protocolnumber=None, vlan=None, vxlan=None, interface=None, established=None, icmptype=None,
                  icmpcode=None, priority=None, state=None, aclaction=None, newname=None, save=False):
    '''
    Update the running configuration for the nsacl6 config key.

    acl6name(str): Name for the ACL6 rule. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Minimum length = 1

    acl6action(str): Action to perform on the incoming IPv6 packets that match the ACL6 rule. Available settings function as
        follows: * ALLOW - The NetScaler appliance processes the packet. * BRIDGE - The NetScaler appliance bridges the
        packet to the destination without processing it. * DENY - The NetScaler appliance drops the packet. Possible
        values = BRIDGE, DENY, ALLOW

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcipv6(bool): IP address or range of IP addresses to match against the source IP address of an incoming IPv6 packet. In
        the command line interface, separate the range with a hyphen.

    srcipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcipv6val(str): Source IPv6 address (range).

    srcport(bool): Port number or range of port numbers to match against the source port number of an incoming IPv6 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The destination port
        can be specified only for TCP and UDP protocols.

    srcportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcportval(str): Source port (range). Maximum length = 65535

    destipv6(bool): IP address or range of IP addresses to match against the destination IP address of an incoming IPv6
        packet. In the command line interface, separate the range with a hyphen.

    destipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destipv6val(str): Destination IPv6 address (range).

    destport(bool): Port number or range of port numbers to match against the destination port number of an incoming IPv6
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols.

    destportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destportval(str): Destination port (range). Maximum length = 65535

    ttl(int): Time to expire this ACL6 (in seconds). Minimum value = 1 Maximum value = 2147483647

    srcmac(str): MAC address to match against the source MAC address of an incoming IPv6 packet.

    srcmacmask(str): Used to define range of Source MAC address. It takes string of 0 and 1, 0s are for exact match and 1s
        for wildcard. For matching first 3 bytes of MAC address, srcMacMask value "000000111111". . Default value:
        "000000000000"

    protocol(str): Protocol, identified by protocol name, to match against the protocol of an incoming IPv6 packet. Possible
        values = ICMPV6, TCP, UDP

    protocolnumber(int): Protocol, identified by protocol number, to match against the protocol of an incoming IPv6 packet.
        Minimum value = 1 Maximum value = 255

    vlan(int): ID of the VLAN. The NetScaler appliance applies the ACL6 rule only to the incoming packets on the specified
        VLAN. If you do not specify a VLAN ID, the appliance applies the ACL6 rule to the incoming packets on all VLANs.
        Minimum value = 1 Maximum value = 4094

    vxlan(int): ID of the VXLAN. The NetScaler appliance applies the ACL6 rule only to the incoming packets on the specified
        VXLAN. If you do not specify a VXLAN ID, the appliance applies the ACL6 rule to the incoming packets on all
        VXLANs. Minimum value = 1 Maximum value = 16777215

    interface(str): ID of an interface. The NetScaler appliance applies the ACL6 rule only to the incoming packets from the
        specified interface. If you do not specify any value, the appliance applies the ACL6 rule to the incoming packets
        from all interfaces.

    established(bool): Allow only incoming TCP packets that have the ACK or RST bit set if the action set for the ACL6 rule
        is ALLOW and these packets match the other conditions in the ACL6 rule.

    icmptype(int): ICMP Message type to match against the message type of an incoming IPv6 ICMP packet. For example, to block
        DESTINATION UNREACHABLE messages, you must specify 3 as the ICMP type.  Note: This parameter can be specified
        only for the ICMP protocol. Minimum value = 0 Maximum value = 65536

    icmpcode(int): Code of a particular ICMP message type to match against the ICMP code of an incoming IPv6 ICMP packet. For
        example, to block DESTINATION HOST UNREACHABLE messages, specify 3 as the ICMP type and 1 as the ICMP code.  If
        you set this parameter, you must set the ICMP Type parameter. Minimum value = 0 Maximum value = 65536

    priority(int): Priority for the ACL6 rule, which determines the order in which it is evaluated relative to the other ACL6
        rules. If you do not specify priorities while creating ACL6 rules, the ACL6 rules are evaluated in the order in
        which they are created. Minimum value = 1 Maximum value = 81920

    state(str): State of the ACL6. Default value: ENABLED Possible values = ENABLED, DISABLED

    aclaction(str): Action associated with the ACL6. Possible values = BRIDGE, DENY, ALLOW

    newname(str): New name for the ACL6 rule. Must begin with an ASCII alphabetic or underscore \\(_\\) character, and must
        contain only ASCII alphanumeric, underscore, hash \\(\\#\\), period \\(.\\), space, colon \\(:\\), at \\(@\\),
        equals \\(=\\), and hyphen \\(-\\) characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsacl6 <args>

    '''

    result = {}

    payload = {'nsacl6': {}}

    if acl6name:
        payload['nsacl6']['acl6name'] = acl6name

    if acl6action:
        payload['nsacl6']['acl6action'] = acl6action

    if td:
        payload['nsacl6']['td'] = td

    if srcipv6:
        payload['nsacl6']['srcipv6'] = srcipv6

    if srcipop:
        payload['nsacl6']['srcipop'] = srcipop

    if srcipv6val:
        payload['nsacl6']['srcipv6val'] = srcipv6val

    if srcport:
        payload['nsacl6']['srcport'] = srcport

    if srcportop:
        payload['nsacl6']['srcportop'] = srcportop

    if srcportval:
        payload['nsacl6']['srcportval'] = srcportval

    if destipv6:
        payload['nsacl6']['destipv6'] = destipv6

    if destipop:
        payload['nsacl6']['destipop'] = destipop

    if destipv6val:
        payload['nsacl6']['destipv6val'] = destipv6val

    if destport:
        payload['nsacl6']['destport'] = destport

    if destportop:
        payload['nsacl6']['destportop'] = destportop

    if destportval:
        payload['nsacl6']['destportval'] = destportval

    if ttl:
        payload['nsacl6']['ttl'] = ttl

    if srcmac:
        payload['nsacl6']['srcmac'] = srcmac

    if srcmacmask:
        payload['nsacl6']['srcmacmask'] = srcmacmask

    if protocol:
        payload['nsacl6']['protocol'] = protocol

    if protocolnumber:
        payload['nsacl6']['protocolnumber'] = protocolnumber

    if vlan:
        payload['nsacl6']['vlan'] = vlan

    if vxlan:
        payload['nsacl6']['vxlan'] = vxlan

    if interface:
        payload['nsacl6']['Interface'] = interface

    if established:
        payload['nsacl6']['established'] = established

    if icmptype:
        payload['nsacl6']['icmptype'] = icmptype

    if icmpcode:
        payload['nsacl6']['icmpcode'] = icmpcode

    if priority:
        payload['nsacl6']['priority'] = priority

    if state:
        payload['nsacl6']['state'] = state

    if aclaction:
        payload['nsacl6']['aclaction'] = aclaction

    if newname:
        payload['nsacl6']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/nsacl6', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsappflowparam(templaterefresh=None, udppmtu=None, httpurl=None, httpcookie=None, httpreferer=None,
                          httpmethod=None, httphost=None, httpuseragent=None, clienttrafficonly=None, save=False):
    '''
    Update the running configuration for the nsappflowparam config key.

    templaterefresh(int): IPFIX template refresh interval (in seconds). Default value: 600 Minimum value = 60 Maximum value =
        3600

    udppmtu(int): MTU to be used for IPFIX UDP packets. Default value: 1472 Minimum value = 128 Maximum value = 1472

    httpurl(str): Enable AppFlow HTTP URL logging. Default value: DISABLED Possible values = ENABLED, DISABLED

    httpcookie(str): Enable AppFlow HTTP cookie logging. Default value: DISABLED Possible values = ENABLED, DISABLED

    httpreferer(str): Enable AppFlow HTTP referer logging. Default value: DISABLED Possible values = ENABLED, DISABLED

    httpmethod(str): Enable AppFlow HTTP method logging. Default value: DISABLED Possible values = ENABLED, DISABLED

    httphost(str): Enable AppFlow HTTP host logging. Default value: DISABLED Possible values = ENABLED, DISABLED

    httpuseragent(str): Enable AppFlow HTTP user-agent logging. Default value: DISABLED Possible values = ENABLED, DISABLED

    clienttrafficonly(str): Control whether AppFlow records should be generated only for client-side traffic. Default value:
        NO Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsappflowparam <args>

    '''

    result = {}

    payload = {'nsappflowparam': {}}

    if templaterefresh:
        payload['nsappflowparam']['templaterefresh'] = templaterefresh

    if udppmtu:
        payload['nsappflowparam']['udppmtu'] = udppmtu

    if httpurl:
        payload['nsappflowparam']['httpurl'] = httpurl

    if httpcookie:
        payload['nsappflowparam']['httpcookie'] = httpcookie

    if httpreferer:
        payload['nsappflowparam']['httpreferer'] = httpreferer

    if httpmethod:
        payload['nsappflowparam']['httpmethod'] = httpmethod

    if httphost:
        payload['nsappflowparam']['httphost'] = httphost

    if httpuseragent:
        payload['nsappflowparam']['httpuseragent'] = httpuseragent

    if clienttrafficonly:
        payload['nsappflowparam']['clienttrafficonly'] = clienttrafficonly

    execution = __proxy__['citrixns.put']('config/nsappflowparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsassignment(name=None, variable=None, ns_set=None, add=None, sub=None, append=None, clear=None, comment=None,
                        newname=None, save=False):
    '''
    Update the running configuration for the nsassignment config key.

    name(str): Name for the assignment. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Can be changed after the assignment is added.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my assignment" or my assignment).

    variable(str): Left hand side of the assigment, of the form $variable-name (for a singleton variabled) or
        $variable-name[key-expression], where key-expression is a default syntax expression that evaluates to a text
        string and provides the key to select a map entry.

    ns_set(str): Right hand side of the assignment. The default syntax expression is evaluated and assigned to theleft hand
        variable.

    add(str): Right hand side of the assignment. The default syntax expression is evaluated and added to the left hand
        variable.

    sub(str): Right hand side of the assignment. The default syntax expression is evaluated and subtracted from the left hand
        variable.

    append(str): Right hand side of the assignment. The default syntax expression is evaluated and appended to the left hand
        variable.

    clear(bool): Clear the variable value. Deallocates a text value, and for a map, the text key.

    comment(str): Comment. Can be used to preserve information about this rewrite action.

    newname(str): New name for the assignment. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon (:),
        and underscore characters. Can be changed after the rewrite policy is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my assignment" or my assignment). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsassignment <args>

    '''

    result = {}

    payload = {'nsassignment': {}}

    if name:
        payload['nsassignment']['name'] = name

    if variable:
        payload['nsassignment']['variable'] = variable

    if ns_set:
        payload['nsassignment']['set'] = ns_set

    if add:
        payload['nsassignment']['Add'] = add

    if sub:
        payload['nsassignment']['sub'] = sub

    if append:
        payload['nsassignment']['append'] = append

    if clear:
        payload['nsassignment']['clear'] = clear

    if comment:
        payload['nsassignment']['comment'] = comment

    if newname:
        payload['nsassignment']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/nsassignment', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nscapacity(bandwidth=None, edition=None, unit=None, platform=None, nodeid=None, save=False):
    '''
    Update the running configuration for the nscapacity config key.

    bandwidth(int): System bandwidth limit.

    edition(str): Product edition. Possible values = Standard, Enterprise, Platinum

    unit(str): Bandwidth unit. Possible values = Gbps, Mbps

    platform(str): appliance platform type. Possible values = VS1, VP1, VS5, VP5, VS10, VE10, VP10, VS25, VE25, VP25, VS50,
        VE50, VP50, VS100, VE100, VP100, VS200, VE200, VP200, VS500, VE500, VP500, VS1000, VE1000, VP1000, VP2000,
        VS3000, VE3000, VP3000, VP4000, VS5000, VE5000, VP5000, VS8000, VE8000, VP8000, CP1000

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nscapacity <args>

    '''

    result = {}

    payload = {'nscapacity': {}}

    if bandwidth:
        payload['nscapacity']['bandwidth'] = bandwidth

    if edition:
        payload['nscapacity']['edition'] = edition

    if unit:
        payload['nscapacity']['unit'] = unit

    if platform:
        payload['nscapacity']['platform'] = platform

    if nodeid:
        payload['nscapacity']['nodeid'] = nodeid

    execution = __proxy__['citrixns.put']('config/nscapacity', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsconfig(force=None, level=None, rbaconfig=None, ipaddress=None, netmask=None, nsvlan=None, ifnum=None,
                    tagged=None, httpport=None, maxconn=None, maxreq=None, cip=None, cipheader=None, cookieversion=None,
                    securecookie=None, pmtumin=None, pmtutimeout=None, ftpportrange=None, crportrange=None,
                    timezone=None, grantquotamaxclient=None, exclusivequotamaxclient=None, grantquotaspillover=None,
                    exclusivequotaspillover=None, config1=None, config2=None, outtype=None, template=None,
                    ignoredevicespecific=None, weakpassword=None, config=None, save=False):
    '''
    Update the running configuration for the nsconfig config key.

    force(bool): Configurations will be cleared without prompting for confirmation.

    level(str): Types of configurations to be cleared. * basic: Clears all configurations except the following:  - NSIP,
        default route (gateway), MIPs, and SNIPs  - Network settings (DG, VLAN, RHI and DNS settings)  - Cluster settings
         - HA node definitions  - Feature and mode settings  - nsroot password * extended: Clears the same configurations
        as the basic option. In addition, it clears the feature and mode settings. * full: Clears all configurations
        except NSIP, default route, and interface settings. Note: When you clear the configurations through the cluster
        IP address, by specifying the level as full, the cluster is deleted and all cluster nodes become standalone
        appliances. The basic and extended levels are propagated to the cluster nodes. Possible values = basic, extended,
        full

    rbaconfig(str): RBA configurations and TACACS policies bound to system global will not be cleared if RBA is set to
        NO.This option is applicable only for BASIC level of clear configuration.Default is YES, which will clear rba
        configurations. Default value: YES Possible values = YES, NO

    ipaddress(str): IP address of the NetScaler appliance. Commonly referred to as NSIP address. This parameter is mandatory
        to bring up the appliance. Minimum length = 1

    netmask(str): Netmask corresponding to the IP address. This parameter is mandatory to bring up the appliance.

    nsvlan(int): VLAN (NSVLAN) for the subnet on which the IP address resides. Minimum value = 2 Maximum value = 4094

    ifnum(list(str)): Interfaces of the appliances that must be bound to the NSVLAN. Minimum length = 1

    tagged(str): Specifies that the interfaces will be added as 802.1q tagged interfaces. Packets sent on these interface on
        this VLAN will have an additional 4-byte 802.1q tag which identifies the VLAN. To use 802.1q tagging, the switch
        connected to the appliances interfaces must also be configured for tagging. Default value: YES Possible values =
        YES, NO

    httpport(list(int)): The HTTP ports on the Web server. This allows the system to perform connection off-load for any
        client request that has a destination port matching one of these configured ports. Minimum value = 1

    maxconn(int): The maximum number of connections that will be made from the system to the web server(s) attached to it.
        The value entered here is applied globally to all attached servers. Minimum value = 0 Maximum value = 4294967294

    maxreq(int): The maximum number of requests that the system can pass on a particular connection between the system and a
        server attached to it. Setting this value to 0 allows an unlimited number of requests to be passed. Minimum value
        = 0 Maximum value = 65535

    cip(str): The option to control (enable or disable) the insertion of the actual client IP address into the HTTP header
        request passed from the client to one, some, or all servers attached to the system. The passed address can then
        be accessed through a minor modification to the server. l If cipHeader is specified, it will be used as the
        client IP header. l If it is not specified, then the value that has been set by the set ns config CLI command
        will be used as the client IP header. Possible values = ENABLED, DISABLED

    cipheader(str): The text that will be used as the client IP header. Minimum length = 1

    cookieversion(str): The version of the cookie inserted by system. Possible values = 0, 1

    securecookie(str): enable/disable secure flag for persistence cookie. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    pmtumin(int): The minimum Path MTU. Default value: 576 Minimum value = 168 Maximum value = 1500

    pmtutimeout(int): The timeout value in minutes. Default value: 10 Minimum value = 1 Maximum value = 1440

    ftpportrange(str): Port range configured for FTP services. Minimum length = 1024 Maximum length = 64000

    crportrange(str): Port range for cache redirection services. Minimum length = 1 Maximum length = 65535

    timezone(str): Name of the timezone. Possible values = CoordinatedUniversalTime, GMT+01:00-CET-Europe/Andorra,
        GMT+04:00-GST-Asia/Dubai, GMT+04:30-AFT-Asia/Kabul, GMT-04:00-AST-America/Antigua,
        GMT-04:00-AST-America/Anguilla, GMT+01:00-CET-Europe/Tirane, GMT+04:00-+04-Asia/Yerevan,
        GMT+01:00-WAT-Africa/Luanda, GMT+13:00-NZDT-Antarctica/McMurdo, GMT+08:00-+08-Antarctica/Casey,
        GMT+07:00-+07-Antarctica/Davis, GMT+10:00-+10-Antarctica/DumontDUrville, GMT+05:00-+05-Antarctica/Mawson,
        GMT-03:00-CLST-Antarctica/Palmer, GMT-03:00--03-Antarctica/Rothera, GMT+03:00-+03-Antarctica/Syowa,
        GMT+00:00-+00-Antarctica/Troll, GMT+06:00-+06-Antarctica/Vostok, GMT-03:00-ART-America/Argentina/Buenos_Aires,
        GMT-03:00-ART-America/Argentina/Cordoba, GMT-03:00-ART-America/Argentina/Salta,
        GMT-03:00-ART-America/Argentina/Jujuy, GMT-03:00-ART-America/Argentina/Tucuman,
        GMT-03:00-ART-America/Argentina/Catamarca, GMT-03:00-ART-America/Argentina/La_Rioja,
        GMT-03:00-ART-America/Argentina/San_Juan, GMT-03:00-ART-America/Argentina/Mendoza,
        GMT-03:00-ART-America/Argentina/San_Luis, GMT-03:00-ART-America/Argentina/Rio_Gallegos,
        GMT-03:00-ART-America/Argentina/Ushuaia, GMT-11:00-SST-Pacific/Pago_Pago, GMT+01:00-CET-Europe/Vienna,
        GMT+11:00-LHDT-Australia/Lord_Howe, GMT+11:00-MIST-Antarctica/Macquarie, GMT+11:00-AEDT-Australia/Hobart,
        GMT+11:00-AEDT-Australia/Currie, GMT+11:00-AEDT-Australia/Melbourne, GMT+11:00-AEDT-Australia/Sydney,
        GMT+10:30-ACDT-Australia/Broken_Hill, GMT+10:00-AEST-Australia/Brisbane, GMT+10:00-AEST-Australia/Lindeman,
        GMT+10:30-ACDT-Australia/Adelaide, GMT+09:30-ACST-Australia/Darwin, GMT+08:00-AWST-Australia/Perth,
        GMT+08:45-ACWST-Australia/Eucla, GMT-04:00-AST-America/Aruba, GMT+02:00-EET-Europe/Mariehamn,
        GMT+04:00-+04-Asia/Baku, GMT+01:00-CET-Europe/Sarajevo, GMT-04:00-AST-America/Barbados, GMT+06:00-BDT-Asia/Dhaka,
        GMT+01:00-CET-Europe/Brussels, GMT+00:00-GMT-Africa/Ouagadougou, GMT+02:00-EET-Europe/Sofia,
        GMT+03:00-AST-Asia/Bahrain, GMT+02:00-CAT-Africa/Bujumbura, GMT+01:00-WAT-Africa/Porto-Novo,
        GMT-04:00-AST-America/St_Barthelemy, GMT-04:00-AST-Atlantic/Bermuda, GMT+08:00-BNT-Asia/Brunei,
        GMT-04:00-BOT-America/La_Paz, GMT-04:00-AST-America/Kralendijk, GMT-02:00-FNT-America/Noronha,
        GMT-03:00-BRT-America/Belem, GMT-03:00-BRT-America/Fortaleza, GMT-03:00-BRT-America/Recife,
        GMT-03:00-BRT-America/Araguaina, GMT-03:00-BRT-America/Maceio, GMT-03:00-BRT-America/Bahia,
        GMT-03:00-BRT-America/Sao_Paulo, GMT-04:00-AMT-America/Campo_Grande, GMT-04:00-AMT-America/Cuiaba,
        GMT-03:00-BRT-America/Santarem, GMT-04:00-AMT-America/Porto_Velho, GMT-04:00-AMT-America/Boa_Vista,
        GMT-04:00-AMT-America/Manaus, GMT-05:00-ACT-America/Eirunepe, GMT-05:00-ACT-America/Rio_Branco,
        GMT-05:00-EST-America/Nassau, GMT+06:00-BTT-Asia/Thimphu, GMT+02:00-CAT-Africa/Gaborone,
        GMT+03:00-+03-Europe/Minsk, GMT-06:00-CST-America/Belize, GMT-03:30-NST-America/St_Johns,
        GMT-04:00-AST-America/Halifax, GMT-04:00-AST-America/Glace_Bay, GMT-04:00-AST-America/Moncton,
        GMT-04:00-AST-America/Goose_Bay, GMT-04:00-AST-America/Blanc-Sablon, GMT-05:00-EST-America/Toronto,
        GMT-05:00-EST-America/Nipigon, GMT-05:00-EST-America/Thunder_Bay, GMT-05:00-EST-America/Iqaluit,
        GMT-05:00-EST-America/Pangnirtung, GMT-05:00-EST-America/Atikokan, GMT-06:00-CST-America/Winnipeg,
        GMT-06:00-CST-America/Rainy_River, GMT-06:00-CST-America/Resolute, GMT-06:00-CST-America/Rankin_Inlet,
        GMT-06:00-CST-America/Regina, GMT-06:00-CST-America/Swift_Current, GMT-07:00-MST-America/Edmonton,
        GMT-07:00-MST-America/Cambridge_Bay, GMT-07:00-MST-America/Yellowknife, GMT-07:00-MST-America/Inuvik,
        GMT-07:00-MST-America/Creston, GMT-07:00-MST-America/Dawson_Creek, GMT-07:00-MST-America/Fort_Nelson,
        GMT-08:00-PST-America/Vancouver, GMT-08:00-PST-America/Whitehorse, GMT-08:00-PST-America/Dawson,
        GMT+06:30-CCT-Indian/Cocos, GMT+01:00-WAT-Africa/Kinshasa, GMT+02:00-CAT-Africa/Lubumbashi,
        GMT+01:00-WAT-Africa/Bangui, GMT+01:00-WAT-Africa/Brazzaville, GMT+01:00-CET-Europe/Zurich,
        GMT+00:00-GMT-Africa/Abidjan, GMT-10:00-CKT-Pacific/Rarotonga, GMT-03:00-CLST-America/Santiago,
        GMT-05:00-EASST-Pacific/Easter, GMT+01:00-WAT-Africa/Douala, GMT+08:00-CST-Asia/Shanghai,
        GMT+06:00-XJT-Asia/Urumqi, GMT-05:00-COT-America/Bogota, GMT-06:00-CST-America/Costa_Rica,
        GMT-05:00-CST-America/Havana, GMT-01:00-CVT-Atlantic/Cape_Verde, GMT-04:00-AST-America/Curacao,
        GMT+07:00-CXT-Indian/Christmas, GMT+02:00-EET-Asia/Nicosia, GMT+01:00-CET-Europe/Prague,
        GMT+01:00-CET-Europe/Berlin, GMT+01:00-CET-Europe/Busingen, GMT+03:00-EAT-Africa/Djibouti,
        GMT+01:00-CET-Europe/Copenhagen, GMT-04:00-AST-America/Dominica, GMT-04:00-AST-America/Santo_Domingo,
        GMT+01:00-CET-Africa/Algiers, GMT-05:00-ECT-America/Guayaquil, GMT-06:00-GALT-Pacific/Galapagos,
        GMT+02:00-EET-Europe/Tallinn, GMT+02:00-EET-Africa/Cairo, GMT+00:00-WET-Africa/El_Aaiun,
        GMT+03:00-EAT-Africa/Asmara, GMT+01:00-CET-Europe/Madrid, GMT+01:00-CET-Africa/Ceuta,
        GMT+00:00-WET-Atlantic/Canary, GMT+03:00-EAT-Africa/Addis_Ababa, GMT+02:00-EET-Europe/Helsinki,
        GMT+12:00-FJT-Pacific/Fiji, GMT-03:00-FKST-Atlantic/Stanley, GMT+10:00-CHUT-Pacific/Chuuk,
        GMT+11:00-PONT-Pacific/Pohnpei, GMT+11:00-KOST-Pacific/Kosrae, GMT+00:00-WET-Atlantic/Faroe,
        GMT+01:00-CET-Europe/Paris, GMT+01:00-WAT-Africa/Libreville, GMT+00:00-GMT-Europe/London,
        GMT-04:00-AST-America/Grenada, GMT+04:00-+04-Asia/Tbilisi, GMT-03:00-GFT-America/Cayenne,
        GMT+00:00-GMT-Europe/Guernsey, GMT+00:00-GMT-Africa/Accra, GMT+01:00-CET-Europe/Gibraltar,
        GMT-03:00-WGT-America/Godthab, GMT+00:00-GMT-America/Danmarkshavn, GMT-01:00-EGT-America/Scoresbysund,
        GMT-04:00-AST-America/Thule, GMT+00:00-GMT-Africa/Banjul, GMT+00:00-GMT-Africa/Conakry,
        GMT-04:00-AST-America/Guadeloupe, GMT+01:00-WAT-Africa/Malabo, GMT+02:00-EET-Europe/Athens,
        GMT-02:00-GST-Atlantic/South_Georgia, GMT-06:00-CST-America/Guatemala, GMT+10:00-ChST-Pacific/Guam,
        GMT+00:00-GMT-Africa/Bissau, GMT-04:00-GYT-America/Guyana, GMT+08:00-HKT-Asia/Hong_Kong,
        GMT-06:00-CST-America/Tegucigalpa, GMT+01:00-CET-Europe/Zagreb, GMT-05:00-EST-America/Port-au-Prince,
        GMT+01:00-CET-Europe/Budapest, GMT+07:00-WIB-Asia/Jakarta, GMT+07:00-WIB-Asia/Pontianak,
        GMT+08:00-WITA-Asia/Makassar, GMT+09:00-WIT-Asia/Jayapura, GMT+00:00-GMT-Europe/Dublin,
        GMT+02:00-IST-Asia/Jerusalem, GMT+00:00-GMT-Europe/Isle_of_Man, GMT+05:30-IST-Asia/Kolkata,
        GMT+06:00-IOT-Indian/Chagos, GMT+03:00-AST-Asia/Baghdad, GMT+03:30-IRST-Asia/Tehran,
        GMT+00:00-GMT-Atlantic/Reykjavik, GMT+01:00-CET-Europe/Rome, GMT+00:00-GMT-Europe/Jersey,
        GMT-05:00-EST-America/Jamaica, GMT+02:00-EET-Asia/Amman, GMT+09:00-JST-Asia/Tokyo, GMT+03:00-EAT-Africa/Nairobi,
        GMT+06:00-+06-Asia/Bishkek, GMT+07:00-ICT-Asia/Phnom_Penh, GMT+12:00-GILT-Pacific/Tarawa,
        GMT+13:00-PHOT-Pacific/Enderbury, GMT+14:00-LINT-Pacific/Kiritimati, GMT+03:00-EAT-Indian/Comoro,
        GMT-04:00-AST-America/St_Kitts, GMT+08:30-KST-Asia/Pyongyang, GMT+09:00-KST-Asia/Seoul,
        GMT+03:00-AST-Asia/Kuwait, GMT-05:00-EST-America/Cayman, GMT+06:00-+06-Asia/Almaty, GMT+06:00-+06-Asia/Qyzylorda,
        GMT+05:00-+05-Asia/Aqtobe, GMT+05:00-+05-Asia/Aqtau, GMT+05:00-+05-Asia/Oral, GMT+07:00-ICT-Asia/Vientiane,
        GMT+02:00-EET-Asia/Beirut, GMT-04:00-AST-America/St_Lucia, GMT+01:00-CET-Europe/Vaduz,
        GMT+05:30-IST-Asia/Colombo, GMT+00:00-GMT-Africa/Monrovia, GMT+02:00-SAST-Africa/Maseru,
        GMT+02:00-EET-Europe/Vilnius, GMT+01:00-CET-Europe/Luxembourg, GMT+02:00-EET-Europe/Riga,
        GMT+02:00-EET-Africa/Tripoli, GMT+00:00-WET-Africa/Casablanca, GMT+01:00-CET-Europe/Monaco,
        GMT+02:00-EET-Europe/Chisinau, GMT+01:00-CET-Europe/Podgorica, GMT-04:00-AST-America/Marigot,
        GMT+03:00-EAT-Indian/Antananarivo, GMT+12:00-MHT-Pacific/Majuro, GMT+12:00-MHT-Pacific/Kwajalein,
        GMT+01:00-CET-Europe/Skopje, GMT+00:00-GMT-Africa/Bamako, GMT+06:30-MMT-Asia/Yangon,
        GMT+08:00-ULAT-Asia/Ulaanbaatar, GMT+07:00-HOVT-Asia/Hovd, GMT+08:00-CHOT-Asia/Choibalsan,
        GMT+08:00-CST-Asia/Macau, GMT+10:00-ChST-Pacific/Saipan, GMT-04:00-AST-America/Martinique,
        GMT+00:00-GMT-Africa/Nouakchott, GMT-04:00-AST-America/Montserrat, GMT+01:00-CET-Europe/Malta,
        GMT+04:00-MUT-Indian/Mauritius, GMT+05:00-MVT-Indian/Maldives, GMT+02:00-CAT-Africa/Blantyre,
        GMT-06:00-CST-America/Mexico_City, GMT-05:00-EST-America/Cancun, GMT-06:00-CST-America/Merida,
        GMT-06:00-CST-America/Monterrey, GMT-06:00-CST-America/Matamoros, GMT-07:00-MST-America/Mazatlan,
        GMT-07:00-MST-America/Chihuahua, GMT-07:00-MST-America/Ojinaga, GMT-07:00-MST-America/Hermosillo,
        GMT-08:00-PST-America/Tijuana, GMT-06:00-CST-America/Bahia_Banderas, GMT+08:00-MYT-Asia/Kuala_Lumpur,
        GMT+08:00-MYT-Asia/Kuching, GMT+02:00-CAT-Africa/Maputo, GMT+02:00-WAST-Africa/Windhoek,
        GMT+11:00-NCT-Pacific/Noumea, GMT+01:00-WAT-Africa/Niamey, GMT+11:00-NFT-Pacific/Norfolk,
        GMT+01:00-WAT-Africa/Lagos, GMT-06:00-CST-America/Managua, GMT+01:00-CET-Europe/Amsterdam,
        GMT+01:00-CET-Europe/Oslo, GMT+05:45-NPT-Asia/Kathmandu, GMT+12:00-NRT-Pacific/Nauru, GMT-11:00-NUT-Pacific/Niue,
        GMT+13:00-NZDT-Pacific/Auckland, GMT+13:45-CHADT-Pacific/Chatham, GMT+04:00-GST-Asia/Muscat,
        GMT-05:00-EST-America/Panama, GMT-05:00-PET-America/Lima, GMT-10:00-TAHT-Pacific/Tahiti,
        GMT-09:30-MART-Pacific/Marquesas, GMT-09:00-GAMT-Pacific/Gambier, GMT+10:00-PGT-Pacific/Port_Moresby,
        GMT+11:00-BST-Pacific/Bougainville, GMT+08:00-PHT-Asia/Manila, GMT+05:00-PKT-Asia/Karachi,
        GMT+01:00-CET-Europe/Warsaw, GMT-03:00-PMST-America/Miquelon, GMT-08:00-PST-Pacific/Pitcairn,
        GMT-04:00-AST-America/Puerto_Rico, GMT+02:00-EET-Asia/Gaza, GMT+02:00-EET-Asia/Hebron,
        GMT+00:00-WET-Europe/Lisbon, GMT+00:00-WET-Atlantic/Madeira, GMT-01:00-AZOT-Atlantic/Azores,
        GMT+09:00-PWT-Pacific/Palau, GMT-03:00-PYST-America/Asuncion, GMT+03:00-AST-Asia/Qatar,
        GMT+04:00-RET-Indian/Reunion, GMT+02:00-EET-Europe/Bucharest, GMT+01:00-CET-Europe/Belgrade,
        GMT+02:00-EET-Europe/Kaliningrad, GMT+03:00-MSK-Europe/Moscow, GMT+03:00-MSK-Europe/Simferopol,
        GMT+03:00-+03-Europe/Volgograd, GMT+03:00-+03-Europe/Kirov, GMT+04:00-+04-Europe/Astrakhan,
        GMT+04:00-+04-Europe/Samara, GMT+04:00-+04-Europe/Ulyanovsk, GMT+05:00-+05-Asia/Yekaterinburg,
        GMT+06:00-+06-Asia/Omsk, GMT+07:00-+07-Asia/Novosibirsk, GMT+07:00-+07-Asia/Barnaul, GMT+07:00-+07-Asia/Tomsk,
        GMT+07:00-+07-Asia/Novokuznetsk, GMT+07:00-+07-Asia/Krasnoyarsk, GMT+08:00-+08-Asia/Irkutsk,
        GMT+09:00-+09-Asia/Chita, GMT+09:00-+09-Asia/Yakutsk, GMT+09:00-+09-Asia/Khandyga,
        GMT+10:00-+10-Asia/Vladivostok, GMT+10:00-+10-Asia/Ust-Nera, GMT+11:00-+11-Asia/Magadan,
        GMT+11:00-+11-Asia/Sakhalin, GMT+11:00-+11-Asia/Srednekolymsk, GMT+12:00-+12-Asia/Kamchatka,
        GMT+12:00-+12-Asia/Anadyr, GMT+02:00-CAT-Africa/Kigali, GMT+03:00-AST-Asia/Riyadh,
        GMT+11:00-SBT-Pacific/Guadalcanal, GMT+04:00-SCT-Indian/Mahe, GMT+03:00-EAT-Africa/Khartoum,
        GMT+01:00-CET-Europe/Stockholm, GMT+08:00-SGT-Asia/Singapore, GMT+00:00-GMT-Atlantic/St_Helena,
        GMT+01:00-CET-Europe/Ljubljana, GMT+01:00-CET-Arctic/Longyearbyen, GMT+01:00-CET-Europe/Bratislava,
        GMT+00:00-GMT-Africa/Freetown, GMT+01:00-CET-Europe/San_Marino, GMT+00:00-GMT-Africa/Dakar,
        GMT+03:00-EAT-Africa/Mogadishu, GMT-03:00-SRT-America/Paramaribo, GMT+03:00-EAT-Africa/Juba,
        GMT+00:00-GMT-Africa/Sao_Tome, GMT-06:00-CST-America/El_Salvador, GMT-04:00-AST-America/Lower_Princes,
        GMT+02:00-EET-Asia/Damascus, GMT+02:00-SAST-Africa/Mbabane, GMT-04:00-AST-America/Grand_Turk,
        GMT+01:00-WAT-Africa/Ndjamena, GMT+05:00-+05-Indian/Kerguelen, GMT+00:00-GMT-Africa/Lome,
        GMT+07:00-ICT-Asia/Bangkok, GMT+05:00-+05-Asia/Dushanbe, GMT+13:00-TKT-Pacific/Fakaofo, GMT+09:00-TLT-Asia/Dili,
        GMT+05:00-+05-Asia/Ashgabat, GMT+01:00-CET-Africa/Tunis, GMT+13:00-TOT-Pacific/Tongatapu,
        GMT+03:00-+03-Europe/Istanbul, GMT-04:00-AST-America/Port_of_Spain, GMT+12:00-TVT-Pacific/Funafuti,
        GMT+08:00-CST-Asia/Taipei, GMT+03:00-EAT-Africa/Dar_es_Salaam, GMT+02:00-EET-Europe/Kiev,
        GMT+02:00-EET-Europe/Uzhgorod, GMT+02:00-EET-Europe/Zaporozhye, GMT+03:00-EAT-Africa/Kampala,
        GMT-10:00-HST-Pacific/Johnston, GMT-11:00-SST-Pacific/Midway, GMT+12:00-WAKT-Pacific/Wake,
        GMT-05:00-EST-America/New_York, GMT-05:00-EST-America/Detroit, GMT-05:00-EST-America/Kentucky/Louisville,
        GMT-05:00-EST-America/Kentucky/Monticello, GMT-05:00-EST-America/Indiana/Indianapolis,
        GMT-05:00-EST-America/Indiana/Vincennes, GMT-05:00-EST-America/Indiana/Winamac,
        GMT-05:00-EST-America/Indiana/Marengo, GMT-05:00-EST-America/Indiana/Petersburg,
        GMT-05:00-EST-America/Indiana/Vevay, GMT-06:00-CST-America/Chicago, GMT-06:00-CST-America/Indiana/Tell_City,
        GMT-06:00-CST-America/Indiana/Knox, GMT-06:00-CST-America/Menominee, GMT-06:00-CST-America/North_Dakota/Center,
        GMT-06:00-CST-America/North_Dakota/New_Salem, GMT-06:00-CST-America/North_Dakota/Beulah,
        GMT-07:00-MST-America/Denver, GMT-07:00-MST-America/Boise, GMT-07:00-MST-America/Phoenix,
        GMT-08:00-PST-America/Los_Angeles, GMT-09:00-AKST-America/Anchorage, GMT-09:00-AKST-America/Juneau,
        GMT-09:00-AKST-America/Sitka, GMT-09:00-AKST-America/Metlakatla, GMT-09:00-AKST-America/Yakutat,
        GMT-09:00-AKST-America/Nome, GMT-10:00-HST-America/Adak, GMT-10:00-HST-Pacific/Honolulu,
        GMT-03:00-UYT-America/Montevideo, GMT+05:00-+05-Asia/Samarkand, GMT+05:00-+05-Asia/Tashkent,
        GMT+01:00-CET-Europe/Vatican, GMT-04:00-AST-America/St_Vincent, GMT-04:00-VET-America/Caracas,
        GMT-04:00-AST-America/Tortola, GMT-04:00-AST-America/St_Thomas, GMT+07:00-ICT-Asia/Ho_Chi_Minh,
        GMT+11:00-VUT-Pacific/Efate, GMT+12:00-WFT-Pacific/Wallis, GMT+14:00-WSDT-Pacific/Apia, GMT+03:00-AST-Asia/Aden,
        GMT+03:00-EAT-Indian/Mayotte, GMT+02:00-SAST-Africa/Johannesburg, GMT+02:00-CAT-Africa/Lusaka,
        GMT+02:00-CAT-Africa/Harare

    grantquotamaxclient(int): The percentage of shared quota to be granted at a time for maxClient. Default value: 10 Minimum
        value = 0 Maximum value = 100

    exclusivequotamaxclient(int): The percentage of maxClient to be given to PEs. Default value: 80 Minimum value = 0 Maximum
        value = 100

    grantquotaspillover(int): The percentage of shared quota to be granted at a time for spillover. Default value: 10 Minimum
        value = 0 Maximum value = 100

    exclusivequotaspillover(int): The percentage of max limit to be given to PEs. Default value: 80 Minimum value = 0 Maximum
        value = 100

    config1(str): Location of the configurations.

    config2(str): Location of the configurations.

    outtype(str): Format to display the difference in configurations. Possible values = cli, xml

    template(bool): File that contains the commands to be compared.

    ignoredevicespecific(bool): Suppress device specific differences.

    weakpassword(bool): Option to list all weak passwords (not adhering to strong password requirements). Takes config file
        as input, if no input specified, running configuration is considered. Command =;gt; query ns config -weakpassword
        / query ns config -weakpassword /nsconfig/ns.conf.

    config(str): configuration File to be used to find weak passwords, if not specified, running config is taken as input.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsconfig <args>

    '''

    result = {}

    payload = {'nsconfig': {}}

    if force:
        payload['nsconfig']['force'] = force

    if level:
        payload['nsconfig']['level'] = level

    if rbaconfig:
        payload['nsconfig']['rbaconfig'] = rbaconfig

    if ipaddress:
        payload['nsconfig']['ipaddress'] = ipaddress

    if netmask:
        payload['nsconfig']['netmask'] = netmask

    if nsvlan:
        payload['nsconfig']['nsvlan'] = nsvlan

    if ifnum:
        payload['nsconfig']['ifnum'] = ifnum

    if tagged:
        payload['nsconfig']['tagged'] = tagged

    if httpport:
        payload['nsconfig']['httpport'] = httpport

    if maxconn:
        payload['nsconfig']['maxconn'] = maxconn

    if maxreq:
        payload['nsconfig']['maxreq'] = maxreq

    if cip:
        payload['nsconfig']['cip'] = cip

    if cipheader:
        payload['nsconfig']['cipheader'] = cipheader

    if cookieversion:
        payload['nsconfig']['cookieversion'] = cookieversion

    if securecookie:
        payload['nsconfig']['securecookie'] = securecookie

    if pmtumin:
        payload['nsconfig']['pmtumin'] = pmtumin

    if pmtutimeout:
        payload['nsconfig']['pmtutimeout'] = pmtutimeout

    if ftpportrange:
        payload['nsconfig']['ftpportrange'] = ftpportrange

    if crportrange:
        payload['nsconfig']['crportrange'] = crportrange

    if timezone:
        payload['nsconfig']['timezone'] = timezone

    if grantquotamaxclient:
        payload['nsconfig']['grantquotamaxclient'] = grantquotamaxclient

    if exclusivequotamaxclient:
        payload['nsconfig']['exclusivequotamaxclient'] = exclusivequotamaxclient

    if grantquotaspillover:
        payload['nsconfig']['grantquotaspillover'] = grantquotaspillover

    if exclusivequotaspillover:
        payload['nsconfig']['exclusivequotaspillover'] = exclusivequotaspillover

    if config1:
        payload['nsconfig']['config1'] = config1

    if config2:
        payload['nsconfig']['config2'] = config2

    if outtype:
        payload['nsconfig']['outtype'] = outtype

    if template:
        payload['nsconfig']['template'] = template

    if ignoredevicespecific:
        payload['nsconfig']['ignoredevicespecific'] = ignoredevicespecific

    if weakpassword:
        payload['nsconfig']['weakpassword'] = weakpassword

    if config:
        payload['nsconfig']['config'] = config

    execution = __proxy__['citrixns.put']('config/nsconfig', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsconsoleloginprompt(promptstring=None, save=False):
    '''
    Update the running configuration for the nsconsoleloginprompt config key.

    promptstring(str): Console login prompt string.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsconsoleloginprompt <args>

    '''

    result = {}

    payload = {'nsconsoleloginprompt': {}}

    if promptstring:
        payload['nsconsoleloginprompt']['promptstring'] = promptstring

    execution = __proxy__['citrixns.put']('config/nsconsoleloginprompt', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsdhcpparams(dhcpclient=None, saveroute=None, save=False):
    '''
    Update the running configuration for the nsdhcpparams config key.

    dhcpclient(str): Enables DHCP client to acquire IP address from the DHCP server in the next boot. When set to OFF,
        disables the DHCP client in the next boot. Default value: OFF Possible values = ON, OFF

    saveroute(str): DHCP acquired routes are saved on the NetScaler appliance. Default value: OFF Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsdhcpparams <args>

    '''

    result = {}

    payload = {'nsdhcpparams': {}}

    if dhcpclient:
        payload['nsdhcpparams']['dhcpclient'] = dhcpclient

    if saveroute:
        payload['nsdhcpparams']['saveroute'] = saveroute

    execution = __proxy__['citrixns.put']('config/nsdhcpparams', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsdiameter(identity=None, realm=None, serverclosepropagation=None, save=False):
    '''
    Update the running configuration for the nsdiameter config key.

    identity(str): DiameterIdentity to be used by NS. DiameterIdentity is used to identify a Diameter node uniquely. Before
        setting up diameter configuration, Netscaler (as a Diameter node) MUST be assigned a unique DiameterIdentity.
        example =;gt; set ns diameter -identity netscaler.com Now whenever Netscaler system needs to use identity in
        diameter messages. It will use netscaler.com as Origin-Host AVP as defined in RFC3588 . Minimum length = 1

    realm(str): Diameter Realm to be used by NS. example =;gt; set ns diameter -realm com Now whenever Netscaler system needs
        to use realm in diameter messages. It will use com as Origin-Realm AVP as defined in RFC3588 . Minimum length =
        1

    serverclosepropagation(str): when a Server connection goes down, whether to close the corresponding client connection if
        there were requests pending on the server. Default value: NO Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsdiameter <args>

    '''

    result = {}

    payload = {'nsdiameter': {}}

    if identity:
        payload['nsdiameter']['identity'] = identity

    if realm:
        payload['nsdiameter']['realm'] = realm

    if serverclosepropagation:
        payload['nsdiameter']['serverclosepropagation'] = serverclosepropagation

    execution = __proxy__['citrixns.put']('config/nsdiameter', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsencryptionkey(name=None, method=None, keyvalue=None, padding=None, iv=None, comment=None, save=False):
    '''
    Update the running configuration for the nsencryptionkey config key.

    name(str): Key name. This follows the same syntax rules as other default syntax expression entity names:  It must begin
        with an alpha character (A-Z or a-z) or an underscore (_).  The rest of the characters must be alpha, numeric
        (0-9) or underscores.  It cannot be re or xp (reserved for regular and XPath expressions).  It cannot be a
        default syntax expression reserved word (e.g. SYS or HTTP).  It cannot be used for an existing default syntax
        expression object (HTTP callout, patset, dataset, stringmap, or named expression). Minimum length = 1

    method(str): Cipher method to be used to encrypt and decrypt content.  NONE - no encryption or decryption is performed
        The output of ENCRYPT() and DECRYPT() is the same as the input.  RC4 - the RC4 stream cipher with a 128 bit (16
        byte) key; RC4 is now considered insecure and should only be used if required by existing applciations.
        DES[-;lt;mode;gt;] - the Data Encryption Standard (DES) block cipher with a 64-bit (8 byte) key, with 56 data
        bits and 8 parity bits. DES is considered less secure than DES3 or AES so it should only be used if required by
        an existing applicastion. The optional mode is described below; DES without a mode is equivalent to DES-CBC.
        DES3[-;lt;mode;gt;] - the Triple Data Encryption Standard (DES) block cipher with a 192-bit (24 byte) key. The
        optional mode is described below; DES3 without a mode is equivalent to DES3-CBC.
        AES;lt;keysize;gt;[-;lt;mode;gt;] - the Advanced Encryption Standard block cipher, available with 128 bit (16
        byte), 192 bit (24 byte), and 256 bit (32 byte) keys. The optional mode is described below; AES;lt;keysize;gt;
        without a mode is equivalent to AES;lt;keysize;gt;-CBC.  For a block cipher, the ;lt;mode;gt; specifies how
        multiple blocks of plaintext are encrypted and how the Initialization Vector (IV) is used. Choices are  CBC
        (Cipher Block Chaining) - Each block of plaintext is XORed with the previous ciphertext block, or IV for the
        first block, before being encrypted. Padding is required if the plaintext is not a multiple of the cipher block
        size.  CFB (Cipher Feedback) - The previous ciphertext block, or the IV for the first block, is encrypted and the
        output is XORed with the current plaintext block to create the current ciphertext block. The 128-bit version of
        CFB is provided. Padding is not required.  OFB (Output Feedback) - A keystream is generated by applying the
        cipher successfully to the IV and XORing the keystream blocks with the plaintext. Padding is not required.  ECB
        (Electronic Codebook) - Each block of plaintext is independently encrypted. An IV is not used. Padding is
        required. This mode is considered less secure than the other modes because the same plaintext always produces the
        same encrypted text and should only be used if required by an existing application. Possible values = NONE, RC4,
        DES3, AES128, AES192, AES256, DES, DES-CBC, DES-CFB, DES-OFB, DES-ECB, DES3-CBC, DES3-CFB, DES3-OFB, DES3-ECB,
        AES128-CBC, AES128-CFB, AES128-OFB, AES128-ECB, AES192-CBC, AES192-CFB, AES192-OFB, AES192-ECB, AES256-CBC,
        AES256-CFB, AES256-OFB, AES256-ECB

    keyvalue(str): The hex-encoded key value. The length is determined by the cipher method:  RC4 - 16 bytes  DES - 8 bytes
        (all modes)  DES3 - 24 bytes (all modes)  AES128 - 16 bytes (all modes)  AES192 - 24 bytes (all modes)  AES256 -
        32 bytes (all modes) Note that the keyValue will be encrypted when it it is saved.

    padding(str): Enables or disables the padding of plaintext to meet the block size requirements of block ciphers:  ON -
        For encryption, PKCS5/7 padding is used, which appends n bytes of value n on the end of the plaintext to bring it
        to the cipher block lnegth. If the plaintext length is alraady a multiple of the block length, an additional
        block with bytes of value block_length will be added. For decryption, ISO 10126 padding is accepted, which
        expects the last byte of the block to be the number of added pad bytes. Note that this accepts PKCS5/7 padding,
        as well as ANSI_X923 padding. Padding ON is the default for the ECB and CBD modes.  OFF - No padding. An Undef
        error will occur with the ECB or CBC modes if the plaintext length is not a multitple of the cipher block size.
        This can be used with the CFB and OFB modes, and with the ECB and CBC modes if the plaintext will always be an
        integral number of blocks, or if custom padding is implemented using a policy extension function. Padding OFf is
        the default for CFB and OFB modes. Default value: DEFAULT Possible values = OFF, ON

    iv(str): The initalization voector (IV) for a block cipher, one block of data used to initialize the encryption. The best
        practice is to not specify an IV, in which case a new random IV will be generated for each encryption. The format
        must be iv_data or keyid_iv_data to include the generated IV in the encrypted data. The IV should only be
        specified if it cannot be included in the encrypted data. The IV length is the cipher block size:  RC4 - not used
        (error if IV is specified)  DES - 8 bytes (all modes)  DES3 - 8 bytes (all modes)  AES128 - 16 bytes (all modes)
        AES192 - 16 bytes (all modes)  AES256 - 16 bytes (all modes).

    comment(str): Comments associated with this encryption key.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsencryptionkey <args>

    '''

    result = {}

    payload = {'nsencryptionkey': {}}

    if name:
        payload['nsencryptionkey']['name'] = name

    if method:
        payload['nsencryptionkey']['method'] = method

    if keyvalue:
        payload['nsencryptionkey']['keyvalue'] = keyvalue

    if padding:
        payload['nsencryptionkey']['padding'] = padding

    if iv:
        payload['nsencryptionkey']['iv'] = iv

    if comment:
        payload['nsencryptionkey']['comment'] = comment

    execution = __proxy__['citrixns.put']('config/nsencryptionkey', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsencryptionparams(method=None, keyvalue=None, save=False):
    '''
    Update the running configuration for the nsencryptionparams config key.

    method(str): Cipher method (and key length) to be used to encrypt and decrypt content. The default value is AES256.
        Possible values = NONE, RC4, DES3, AES128, AES192, AES256, DES, DES-CBC, DES-CFB, DES-OFB, DES-ECB, DES3-CBC,
        DES3-CFB, DES3-OFB, DES3-ECB, AES128-CBC, AES128-CFB, AES128-OFB, AES128-ECB, AES192-CBC, AES192-CFB, AES192-OFB,
        AES192-ECB, AES256-CBC, AES256-CFB, AES256-OFB, AES256-ECB

    keyvalue(str): The base64-encoded key generation number, method, and key value. Note: * Do not include this argument if
        you are changing the encryption method. * To generate a new key value for the current encryption method, specify
        an empty string \\(""\\) as the value of this parameter. The parameter is passed implicitly, with its
        automatically generated value, to the NetScaler packet engines even when it is not included in the command.
        Passing the parameter to the packet engines enables the appliance to save the key value to the configuration file
        and to propagate the key value to the secondary appliance in a high availability setup.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsencryptionparams <args>

    '''

    result = {}

    payload = {'nsencryptionparams': {}}

    if method:
        payload['nsencryptionparams']['method'] = method

    if keyvalue:
        payload['nsencryptionparams']['keyvalue'] = keyvalue

    execution = __proxy__['citrixns.put']('config/nsencryptionparams', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsextension(src=None, name=None, comment=None, overwrite=None, trace=None, tracefunctions=None,
                       tracevariables=None, detail=None, save=False):
    '''
    Update the running configuration for the nsextension config key.

    src(str): Local path to and name of, or URL (protocol, host, path, and file name) for, the file in which to store the
        imported extension. NOTE: The import fails if the object to be imported is on an HTTPS server that requires
        client certificate authentication for access. Minimum length = 1 Maximum length = 2047

    name(str): Name to assign to the extension object on the NetScaler appliance. Minimum length = 1 Maximum length = 31

    comment(str): Any comments to preserve information about the extension object. Maximum length = 128

    overwrite(bool): Overwrites the existing file.

    trace(str): Enables tracing to the NS log file of extension execution:  off - turns off tracing (equivalent to unset ns
        extension ;lt;extension-name;gt; -trace)  calls - traces extension function calls with arguments and function
        returns with the first return value  lines - traces the above plus line numbers for executed extension lines  all
        - traces the above plus local variables changed by executed extension lines Note that the DEBUG log level must be
        enabled to see extension tracing. This can be done by set audit syslogParams -loglevel ALL or -loglevel DEBUG.
        Default value: off Possible values = off, calls, lines, all

    tracefunctions(str): Comma-separated list of extension functions to trace. By default, all extension functions are
        traced. Maximum length = 256

    tracevariables(str): Comma-separated list of variables (in traced extension functions) to trace. By default, all
        variables are traced. Maximum length = 256

    detail(str): Show detail for extension function. Possible values = brief, all

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsextension <args>

    '''

    result = {}

    payload = {'nsextension': {}}

    if src:
        payload['nsextension']['src'] = src

    if name:
        payload['nsextension']['name'] = name

    if comment:
        payload['nsextension']['comment'] = comment

    if overwrite:
        payload['nsextension']['overwrite'] = overwrite

    if trace:
        payload['nsextension']['trace'] = trace

    if tracefunctions:
        payload['nsextension']['tracefunctions'] = tracefunctions

    if tracevariables:
        payload['nsextension']['tracevariables'] = tracevariables

    if detail:
        payload['nsextension']['detail'] = detail

    execution = __proxy__['citrixns.put']('config/nsextension', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nshmackey(name=None, digest=None, keyvalue=None, comment=None, save=False):
    '''
    Update the running configuration for the nshmackey config key.

    name(str): Key name. This follows the same syntax rules as other default syntax expression entity names:  It must begin
        with an alpha character (A-Z or a-z) or an underscore (_).  The rest of the characters must be alpha, numeric
        (0-9) or underscores.  It cannot be re or xp (reserved for regular and XPath expressions).  It cannot be a
        default syntax expression reserved word (e.g. SYS or HTTP).  It cannot be used for an existing default syntax
        expression object (HTTP callout, patset, dataset, stringmap, or named expression). Minimum length = 1

    digest(str): Digest (hash) function to be used in the HMAC computation. Possible values = MD2, MD4, MD5, SHA1, SHA224,
        SHA256, SHA384, SHA512

    keyvalue(str): The hex-encoded key to be used in the HMAC computation. The key can be any length (up to a
        NetScaler-imposed maximum of 255 bytes). If the length is less than the digest block size, it will be zero padded
        up to the block size. If it is greater than the block size, it will be hashed using the digest function to the
        block size. The block size for each digest is:  MD2 - 16 bytes  MD4 - 16 bytes  MD5 - 16 bytes  SHA1 - 20 bytes
        SHA224 - 28 bytes  SHA256 - 32 bytes  SHA384 - 48 bytes  SHA512 - 64 bytes Note that the key will be encrypted
        when it it is saved.

    comment(str): Comments associated with this encryption key.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nshmackey <args>

    '''

    result = {}

    payload = {'nshmackey': {}}

    if name:
        payload['nshmackey']['name'] = name

    if digest:
        payload['nshmackey']['digest'] = digest

    if keyvalue:
        payload['nshmackey']['keyvalue'] = keyvalue

    if comment:
        payload['nshmackey']['comment'] = comment

    execution = __proxy__['citrixns.put']('config/nshmackey', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nshostname(hostname=None, ownernode=None, save=False):
    '''
    Update the running configuration for the nshostname config key.

    hostname(str): Host name for the NetScaler appliance. Minimum length = 1 Maximum length = 255

    ownernode(int): ID of the cluster node for which you are setting the hostname. Can be configured only through the cluster
        IP address. Default value: 255 Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nshostname <args>

    '''

    result = {}

    payload = {'nshostname': {}}

    if hostname:
        payload['nshostname']['hostname'] = hostname

    if ownernode:
        payload['nshostname']['ownernode'] = ownernode

    execution = __proxy__['citrixns.put']('config/nshostname', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nshttpparam(dropinvalreqs=None, markhttp09inval=None, markconnreqinval=None, insnssrvrhdr=None,
                       nssrvrhdr=None, logerrresp=None, conmultiplex=None, maxreusepool=None, save=False):
    '''
    Update the running configuration for the nshttpparam config key.

    dropinvalreqs(str): Drop invalid HTTP requests or responses. Default value: OFF Possible values = ON, OFF

    markhttp09inval(str): Mark HTTP/0.9 requests as invalid. Default value: OFF Possible values = ON, OFF

    markconnreqinval(str): Mark CONNECT requests as invalid. Default value: OFF Possible values = ON, OFF

    insnssrvrhdr(str): Enable or disable NetScaler server header insertion for NetScaler generated HTTP responses. Default
        value: OFF Possible values = ON, OFF

    nssrvrhdr(str): The server header value to be inserted. If no explicit header is specified then NSBUILD.RELEASE is used
        as default server header. Minimum length = 1

    logerrresp(str): Server header value to be inserted. Default value: ON Possible values = ON, OFF

    conmultiplex(str): Reuse server connections for requests from more than one client connections. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    maxreusepool(int): Maximum limit on the number of connections, from the NetScaler to a particular server that are kept in
        the reuse pool. This setting is helpful for optimal memory utilization and for reducing the idle connections to
        the server just after the peak time. Minimum value = 0 Maximum value = 360000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nshttpparam <args>

    '''

    result = {}

    payload = {'nshttpparam': {}}

    if dropinvalreqs:
        payload['nshttpparam']['dropinvalreqs'] = dropinvalreqs

    if markhttp09inval:
        payload['nshttpparam']['markhttp09inval'] = markhttp09inval

    if markconnreqinval:
        payload['nshttpparam']['markconnreqinval'] = markconnreqinval

    if insnssrvrhdr:
        payload['nshttpparam']['insnssrvrhdr'] = insnssrvrhdr

    if nssrvrhdr:
        payload['nshttpparam']['nssrvrhdr'] = nssrvrhdr

    if logerrresp:
        payload['nshttpparam']['logerrresp'] = logerrresp

    if conmultiplex:
        payload['nshttpparam']['conmultiplex'] = conmultiplex

    if maxreusepool:
        payload['nshttpparam']['maxreusepool'] = maxreusepool

    execution = __proxy__['citrixns.put']('config/nshttpparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nshttpprofile(name=None, dropinvalreqs=None, markhttp09inval=None, markconnreqinval=None, cmponpush=None,
                         conmultiplex=None, maxreusepool=None, dropextracrlf=None, incomphdrdelay=None, websocket=None,
                         rtsptunnel=None, reqtimeout=None, adpttimeout=None, reqtimeoutaction=None, dropextradata=None,
                         weblog=None, clientiphdrexpr=None, maxreq=None, persistentetag=None, spdy=None, http2=None,
                         http2direct=None, altsvc=None, reusepooltimeout=None, maxheaderlen=None, minreusepool=None,
                         http2maxheaderlistsize=None, http2maxframesize=None, http2maxconcurrentstreams=None,
                         http2initialwindowsize=None, http2headertablesize=None, http2minseverconn=None,
                         apdexcltresptimethreshold=None, save=False):
    '''
    Update the running configuration for the nshttpprofile config key.

    name(str): Name for an HTTP profile. Must begin with a letter, number, or the underscore \\(_\\) character. Other
        characters allowed, after the first character, are the hyphen \\(-\\), period \\(.\\), hash \\(\\#\\), space \\(
        \\), at \\(@\\), colon \\(:\\), and equal \\(=\\) characters. The name of a HTTP profile cannot be changed after
        it is created.  CLI Users: If the name includes one or more spaces, enclose the name in double or single
        quotation marks \\(for example, "my http profile" or my http profile\\). Minimum length = 1 Maximum length = 127

    dropinvalreqs(str): Drop invalid HTTP requests or responses. Default value: DISABLED Possible values = ENABLED, DISABLED

    markhttp09inval(str): Mark HTTP/0.9 requests as invalid. Default value: DISABLED Possible values = ENABLED, DISABLED

    markconnreqinval(str): Mark CONNECT requests as invalid. Default value: DISABLED Possible values = ENABLED, DISABLED

    cmponpush(str): Start data compression on receiving a TCP packet with PUSH flag set. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    conmultiplex(str): Reuse server connections for requests from more than one client connections. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    maxreusepool(int): Maximum limit on the number of connections, from the NetScaler to a particular server that are kept in
        the reuse pool. This setting is helpful for optimal memory utilization and for reducing the idle connections to
        the server just after the peak time. Zero implies no limit on reuse pool size. If non-zero value is given, it has
        to be greater than or equal to the number of running Packet Engines. Default value: 0 Minimum value = 0 Maximum
        value = 360000

    dropextracrlf(str): Drop any extra CR and LF characters present after the header. Default value: ENABLED Possible values
        = ENABLED, DISABLED

    incomphdrdelay(int): Maximum time to wait, in milliseconds, between incomplete header packets. If the header packets take
        longer to arrive at NetScaler, the connection is silently dropped. Default value: 7000 Minimum value = 1 Maximum
        value = 360000

    websocket(str): HTTP connection to be upgraded to a web socket connection. Once upgraded, NetScaler does not process
        Layer 7 traffic on this connection. Default value: DISABLED Possible values = ENABLED, DISABLED

    rtsptunnel(str): Allow RTSP tunnel in HTTP. Once application/x-rtsp-tunnelled is seen in Accept or Content-Type header,
        NetScaler does not process Layer 7 traffic on this connection. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    reqtimeout(int): Time, in seconds, within which the HTTP request must complete. If the request does not complete within
        this time, the specified request timeout action is executed. Zero disables the timeout. Default value: 0 Minimum
        value = 0 Maximum value = 86400

    adpttimeout(str): Adapts the configured request timeout based on flow conditions. The timeout is increased or decreased
        internally and applied on the flow. Default value: DISABLED Possible values = ENABLED, DISABLED

    reqtimeoutaction(str): Action to take when the HTTP request does not complete within the specified request timeout
        duration. You can configure the following actions: * RESET - Send RST (reset) to client when timeout occurs. *
        DROP - Drop silently when timeout occurs. * Custom responder action - Name of the responder action to trigger
        when timeout occurs, used to send custom message.

    dropextradata(str): Drop any extra data when server sends more data than the specified content-length. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    weblog(str): Enable or disable web logging. Default value: ENABLED Possible values = ENABLED, DISABLED

    clientiphdrexpr(str): Name of the header that contains the real client IP address.

    maxreq(int): Maximum number of requests allowed on a single connection. Zero implies no limit on the number of requests.
        Default value: 0 Minimum value = 0 Maximum value = 65534

    persistentetag(str): Generate the persistent NetScaler specific ETag for the HTTP response with ETag header. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    spdy(str): Enable SPDYv2 or SPDYv3 or both over SSL vserver. SSL will advertise SPDY support either during NPN Handshake
        or when client will advertises SPDY support during ALPN handshake. Both SPDY versions are enabled when this
        parameter is set to ENABLED. Default value: DISABLED Possible values = DISABLED, ENABLED, V2, V3

    http2(str): Choose whether to enable support for HTTP/2. Default value: DISABLED Possible values = ENABLED, DISABLED

    http2direct(str): Choose whether to enable support for Direct HTTP/2. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    altsvc(str): Choose whether to enable support for Alternative Service. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    reusepooltimeout(int): Idle timeout (in seconds) for server connections in re-use pool. Connections in the re-use pool
        are flushed, if they remain idle for the configured timeout. Default value: 0 Minimum value = 0 Maximum value =
        31536000

    maxheaderlen(int): Number of bytes to be queued to look for complete header before returning error. If complete header is
        not obtained after queuing these many bytes, request will be marked as invalid and no L7 processing will be done
        for that TCP connection. Default value: 24820 Minimum value = 2048 Maximum value = 61440

    minreusepool(int): Minimum limit on the number of connections, from the NetScaler to a particular server that are kept in
        the reuse pool. This setting is helpful for optimal memory utilization and for reducing the idle connections to
        the server just after the peak time. Zero implies no limit on reuse pool size. Default value: 0 Minimum value = 0
        Maximum value = 360000

    http2maxheaderlistsize(int): Maximum size of header list that the NetScaler is prepared to accept, in bytes. NOTE: The
        actual plain text header size that the NetScaler accepts is limited by maxHeaderLen. Please change this parameter
        as well when modifying http2MaxHeaderListSize. Default value: 24576 Minimum value = 8192 Maximum value = 65535

    http2maxframesize(int): Maximum size of the frame payload that the NetScaler is willing to receive, in bytes. Default
        value: 16384 Minimum value = 16384 Maximum value = 16777215

    http2maxconcurrentstreams(int): Maximum number of concurrent streams that is allowed per connection. Default value: 100
        Minimum value = 0 Maximum value = 1000

    http2initialwindowsize(int): Initial window size for stream level flow control, in bytes. Default value: 65535 Minimum
        value = 8192 Maximum value = 20971520

    http2headertablesize(int): Maximum size of the header compression table used to decode header blocks, in bytes. Default
        value: 4096 Minimum value = 0 Maximum value = 16384

    http2minseverconn(int): Minimum number of HTTP2 connections established to backend server, on receiving HTTP requests
        from client before multiplexing the streams into the available HTTP/2 connections. Default value: 20 Minimum
        value = 1 Maximum value = 360000

    apdexcltresptimethreshold(int): This option sets the satisfactory threshold (T) for client response time in milliseconds
        to be used for APDEX calculations. This means a transaction responding in less than this threshold is considered
        satisfactory. Transaction responding between T and 4*T is considered tolerable. Any transaction responding in
        more than 4*T time is considered frustrating. Netscaler maintains stats for such tolerable and frustrating
        transcations. And client response time related apdex counters are only updated on a vserver which receives
        clients traffic. Default value: 500 Minimum value = 1 Maximum value = 3600000

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nshttpprofile <args>

    '''

    result = {}

    payload = {'nshttpprofile': {}}

    if name:
        payload['nshttpprofile']['name'] = name

    if dropinvalreqs:
        payload['nshttpprofile']['dropinvalreqs'] = dropinvalreqs

    if markhttp09inval:
        payload['nshttpprofile']['markhttp09inval'] = markhttp09inval

    if markconnreqinval:
        payload['nshttpprofile']['markconnreqinval'] = markconnreqinval

    if cmponpush:
        payload['nshttpprofile']['cmponpush'] = cmponpush

    if conmultiplex:
        payload['nshttpprofile']['conmultiplex'] = conmultiplex

    if maxreusepool:
        payload['nshttpprofile']['maxreusepool'] = maxreusepool

    if dropextracrlf:
        payload['nshttpprofile']['dropextracrlf'] = dropextracrlf

    if incomphdrdelay:
        payload['nshttpprofile']['incomphdrdelay'] = incomphdrdelay

    if websocket:
        payload['nshttpprofile']['websocket'] = websocket

    if rtsptunnel:
        payload['nshttpprofile']['rtsptunnel'] = rtsptunnel

    if reqtimeout:
        payload['nshttpprofile']['reqtimeout'] = reqtimeout

    if adpttimeout:
        payload['nshttpprofile']['adpttimeout'] = adpttimeout

    if reqtimeoutaction:
        payload['nshttpprofile']['reqtimeoutaction'] = reqtimeoutaction

    if dropextradata:
        payload['nshttpprofile']['dropextradata'] = dropextradata

    if weblog:
        payload['nshttpprofile']['weblog'] = weblog

    if clientiphdrexpr:
        payload['nshttpprofile']['clientiphdrexpr'] = clientiphdrexpr

    if maxreq:
        payload['nshttpprofile']['maxreq'] = maxreq

    if persistentetag:
        payload['nshttpprofile']['persistentetag'] = persistentetag

    if spdy:
        payload['nshttpprofile']['spdy'] = spdy

    if http2:
        payload['nshttpprofile']['http2'] = http2

    if http2direct:
        payload['nshttpprofile']['http2direct'] = http2direct

    if altsvc:
        payload['nshttpprofile']['altsvc'] = altsvc

    if reusepooltimeout:
        payload['nshttpprofile']['reusepooltimeout'] = reusepooltimeout

    if maxheaderlen:
        payload['nshttpprofile']['maxheaderlen'] = maxheaderlen

    if minreusepool:
        payload['nshttpprofile']['minreusepool'] = minreusepool

    if http2maxheaderlistsize:
        payload['nshttpprofile']['http2maxheaderlistsize'] = http2maxheaderlistsize

    if http2maxframesize:
        payload['nshttpprofile']['http2maxframesize'] = http2maxframesize

    if http2maxconcurrentstreams:
        payload['nshttpprofile']['http2maxconcurrentstreams'] = http2maxconcurrentstreams

    if http2initialwindowsize:
        payload['nshttpprofile']['http2initialwindowsize'] = http2initialwindowsize

    if http2headertablesize:
        payload['nshttpprofile']['http2headertablesize'] = http2headertablesize

    if http2minseverconn:
        payload['nshttpprofile']['http2minseverconn'] = http2minseverconn

    if apdexcltresptimethreshold:
        payload['nshttpprofile']['apdexcltresptimethreshold'] = apdexcltresptimethreshold

    execution = __proxy__['citrixns.put']('config/nshttpprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsip(ipaddress=None, netmask=None, ns_type=None, arp=None, icmp=None, vserver=None, telnet=None, ftp=None,
                gui=None, ssh=None, snmp=None, mgmtaccess=None, restrictaccess=None, dynamicrouting=None, ospf=None,
                bgp=None, rip=None, hostroute=None, networkroute=None, tag=None, hostrtgw=None, metric=None,
                vserverrhilevel=None, vserverrhimode=None, ospflsatype=None, ospfarea=None, state=None, vrid=None,
                icmpresponse=None, ownernode=None, arpresponse=None, ownerdownresponse=None, td=None, save=False):
    '''
    Update the running configuration for the nsip config key.

    ipaddress(str): IPv4 address to create on the NetScaler appliance. Cannot be changed after the IP address is created.
        Minimum length = 1

    netmask(str): Subnet mask associated with the IP address.

    ns_type(str): Type of the IP address to create on the NetScaler appliance. Cannot be changed after the IP address is
        created. The following are the different types of NetScaler owned IP addresses: * A Subnet IP (SNIP) address is
        used by the NetScaler ADC to communicate with the servers. The NetScaler also uses the subnet IP address when
        generating its own packets, such as packets related to dynamic routing protocols, or to send monitor probes to
        check the health of the servers. * A Virtual IP (VIP) address is the IP address associated with a virtual server.
        It is the IP address to which clients connect. An appliance managing a wide range of traffic may have many VIPs
        configured. Some of the attributes of the VIP address are customized to meet the requirements of the virtual
        server. * A GSLB site IP (GSLBIP) address is associated with a GSLB site. It is not mandatory to specify a GSLBIP
        address when you initially configure the NetScaler appliance. A GSLBIP address is used only when you create a
        GSLB site. * A Cluster IP (CLIP) address is the management address of the cluster. All cluster configurations
        must be performed by accessing the cluster through this IP address. Default value: SNIP Possible values = SNIP,
        VIP, NSIP, GSLBsiteIP, CLIP, LSN

    arp(str): Respond to ARP requests for this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    icmp(str): Respond to ICMP requests for this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    vserver(str): Use this option to set (enable or disable) the virtual server attribute for this IP address. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    telnet(str): Allow Telnet access to this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    ftp(str): Allow File Transfer Protocol (FTP) access to this IP address. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    gui(str): Allow graphical user interface (GUI) access to this IP address. Default value: ENABLED Possible values =
        ENABLED, SECUREONLY, DISABLED

    ssh(str): Allow secure shell (SSH) access to this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    snmp(str): Allow Simple Network Management Protocol (SNMP) access to this IP address. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    mgmtaccess(str): Allow access to management applications on this IP address. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    restrictaccess(str): Block access to nonmanagement applications on this IP. This option is applicable for MIPs, SNIPs,
        and NSIP, and is disabled by default. Nonmanagement applications can run on the underlying NetScaler Free BSD
        operating system. Default value: DISABLED Possible values = ENABLED, DISABLED

    dynamicrouting(str): Allow dynamic routing on this IP address. Specific to Subnet IP (SNIP) address. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    ospf(str): Use this option to enable or disable OSPF on this IP address for the entity. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    bgp(str): Use this option to enable or disable BGP on this IP address for the entity. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    rip(str): Use this option to enable or disable RIP on this IP address for the entity. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    hostroute(str): Option to push the VIP to ZebOS routing table for Kernel route redistribution through dynamic routing
        protocols. Possible values = ENABLED, DISABLED

    networkroute(str): Option to push the SNIP subnet to ZebOS routing table for Kernel route redistribution through dynamic
        routing protocol. Possible values = ENABLED, DISABLED

    tag(int): Tag value for the network/host route associated with this IP. Default value: 0

    hostrtgw(str): IP address of the gateway of the route for this VIP address. Default value: -1

    metric(int): Integer value to add to or subtract from the cost of the route advertised for the VIP address. Minimum value
        = -16777215

    vserverrhilevel(str): Advertise the route for the Virtual IP (VIP) address on the basis of the state of the virtual
        servers associated with that VIP. * NONE - Advertise the route for the VIP address, regardless of the state of
        the virtual servers associated with the address. * ONE VSERVER - Advertise the route for the VIP address if at
        least one of the associated virtual servers is in UP state. * ALL VSERVER - Advertise the route for the VIP
        address if all of the associated virtual servers are in UP state. * VSVR_CNTRLD - Advertise the route for the VIP
        address according to the RHIstate (RHI STATE) parameter setting on all the associated virtual servers of the VIP
        address along with their states.  When Vserver RHI Level (RHI) parameter is set to VSVR_CNTRLD, the following are
        different RHI behaviors for the VIP address on the basis of RHIstate (RHI STATE) settings on the virtual servers
        associated with the VIP address:  * If you set RHI STATE to PASSIVE on all virtual servers, the NetScaler ADC
        always advertises the route for the VIP address.  * If you set RHI STATE to ACTIVE on all virtual servers, the
        NetScaler ADC advertises the route for the VIP address if at least one of the associated virtual servers is in UP
        state.  *If you set RHI STATE to ACTIVE on some and PASSIVE on others, the NetScaler ADC advertises the route for
        the VIP address if at least one of the associated virtual servers, whose RHI STATE set to ACTIVE, is in UP state.
         Default value: ONE_VSERVER Possible values = ONE_VSERVER, ALL_VSERVERS, NONE, VSVR_CNTRLD

    vserverrhimode(str): Advertise the route for the Virtual IP (VIP) address using dynamic routing protocols or using RISE *
        DYNMAIC_ROUTING - Advertise the route for the VIP address using dynamic routing protocols (default) * RISE -
        Advertise the route for the VIP address using RISE. Default value: DYNAMIC_ROUTING Possible values =
        DYNAMIC_ROUTING, RISE

    ospflsatype(str): Type of LSAs to be used by the OSPF protocol, running on the NetScaler appliance, for advertising the
        route for this VIP address. Default value: TYPE5 Possible values = TYPE1, TYPE5

    ospfarea(int): ID of the area in which the type1 link-state advertisements (LSAs) are to be advertised for this virtual
        IP (VIP) address by the OSPF protocol running on the NetScaler appliance. When this parameter is not set, the VIP
        is advertised on all areas. Default value: -1 Minimum value = 0 Maximum value = 4294967294LU

    state(str): Enable or disable the IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    vrid(int): A positive integer that uniquely identifies a VMAC address for binding to this VIP address. This binding is
        used to set up NetScaler appliances in an active-active configuration using VRRP. Minimum value = 1 Maximum value
        = 255

    icmpresponse(str): Respond to ICMP requests for a Virtual IP (VIP) address on the basis of the states of the virtual
        servers associated with that VIP. Available settings function as follows: * NONE - The NetScaler appliance
        responds to any ICMP request for the VIP address, irrespective of the states of the virtual servers associated
        with the address. * ONE VSERVER - The NetScaler appliance responds to any ICMP request for the VIP address if at
        least one of the associated virtual servers is in UP state. * ALL VSERVER - The NetScaler appliance responds to
        any ICMP request for the VIP address if all of the associated virtual servers are in UP state. * VSVR_CNTRLD -
        The behavior depends on the ICMP VSERVER RESPONSE setting on all the associated virtual servers.  The following
        settings can be made for the ICMP VSERVER RESPONSE parameter on a virtual server: * If you set ICMP VSERVER
        RESPONSE to PASSIVE on all virtual servers, NetScaler always responds. * If you set ICMP VSERVER RESPONSE to
        ACTIVE on all virtual servers, NetScaler responds if even one virtual server is UP. * When you set ICMP VSERVER
        RESPONSE to ACTIVE on some and PASSIVE on others, NetScaler responds if even one virtual server set to ACTIVE is
        UP. Default value: 5 Possible values = NONE, ONE_VSERVER, ALL_VSERVERS, VSVR_CNTRLD

    ownernode(int): The owner node in a Cluster for this IP address. Owner node can vary from 0 to 31. If ownernode is not
        specified then the IP is treated as Striped IP. Default value: 255

    arpresponse(str): Respond to ARP requests for a Virtual IP (VIP) address on the basis of the states of the virtual
        servers associated with that VIP. Available settings function as follows:  * NONE - The NetScaler appliance
        responds to any ARP request for the VIP address, irrespective of the states of the virtual servers associated
        with the address. * ONE VSERVER - The NetScaler appliance responds to any ARP request for the VIP address if at
        least one of the associated virtual servers is in UP state. * ALL VSERVER - The NetScaler appliance responds to
        any ARP request for the VIP address if all of the associated virtual servers are in UP state. Default value: 5
        Possible values = NONE, ONE_VSERVER, ALL_VSERVERS

    ownerdownresponse(str): in cluster system, if the owner node is down, whether should it respond to icmp/arp. Default
        value: YES Possible values = YES, NO

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsip <args>

    '''

    result = {}

    payload = {'nsip': {}}

    if ipaddress:
        payload['nsip']['ipaddress'] = ipaddress

    if netmask:
        payload['nsip']['netmask'] = netmask

    if ns_type:
        payload['nsip']['type'] = ns_type

    if arp:
        payload['nsip']['arp'] = arp

    if icmp:
        payload['nsip']['icmp'] = icmp

    if vserver:
        payload['nsip']['vserver'] = vserver

    if telnet:
        payload['nsip']['telnet'] = telnet

    if ftp:
        payload['nsip']['ftp'] = ftp

    if gui:
        payload['nsip']['gui'] = gui

    if ssh:
        payload['nsip']['ssh'] = ssh

    if snmp:
        payload['nsip']['snmp'] = snmp

    if mgmtaccess:
        payload['nsip']['mgmtaccess'] = mgmtaccess

    if restrictaccess:
        payload['nsip']['restrictaccess'] = restrictaccess

    if dynamicrouting:
        payload['nsip']['dynamicrouting'] = dynamicrouting

    if ospf:
        payload['nsip']['ospf'] = ospf

    if bgp:
        payload['nsip']['bgp'] = bgp

    if rip:
        payload['nsip']['rip'] = rip

    if hostroute:
        payload['nsip']['hostroute'] = hostroute

    if networkroute:
        payload['nsip']['networkroute'] = networkroute

    if tag:
        payload['nsip']['tag'] = tag

    if hostrtgw:
        payload['nsip']['hostrtgw'] = hostrtgw

    if metric:
        payload['nsip']['metric'] = metric

    if vserverrhilevel:
        payload['nsip']['vserverrhilevel'] = vserverrhilevel

    if vserverrhimode:
        payload['nsip']['vserverrhimode'] = vserverrhimode

    if ospflsatype:
        payload['nsip']['ospflsatype'] = ospflsatype

    if ospfarea:
        payload['nsip']['ospfarea'] = ospfarea

    if state:
        payload['nsip']['state'] = state

    if vrid:
        payload['nsip']['vrid'] = vrid

    if icmpresponse:
        payload['nsip']['icmpresponse'] = icmpresponse

    if ownernode:
        payload['nsip']['ownernode'] = ownernode

    if arpresponse:
        payload['nsip']['arpresponse'] = arpresponse

    if ownerdownresponse:
        payload['nsip']['ownerdownresponse'] = ownerdownresponse

    if td:
        payload['nsip']['td'] = td

    execution = __proxy__['citrixns.put']('config/nsip', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsip6(ipv6address=None, scope=None, ns_type=None, vlan=None, nd=None, icmp=None, vserver=None, telnet=None,
                 ftp=None, gui=None, ssh=None, snmp=None, mgmtaccess=None, restrictaccess=None, dynamicrouting=None,
                 hostroute=None, networkroute=None, tag=None, ip6hostrtgw=None, metric=None, vserverrhilevel=None,
                 ospf6lsatype=None, ospfarea=None, state=None, ns_map=None, vrid6=None, ownernode=None,
                 ownerdownresponse=None, td=None, save=False):
    '''
    Update the running configuration for the nsip6 config key.

    ipv6address(str): IPv6 address to create on the NetScaler appliance. Minimum length = 1

    scope(str): Scope of the IPv6 address to be created. Cannot be changed after the IP address is created. Default value:
        global Possible values = global, link-local

    ns_type(str): Type of IP address to be created on the NetScaler appliance. Cannot be changed after the IP address is
        created. Default value: SNIP Possible values = NSIP, VIP, SNIP, GSLBsiteIP, ADNSsvcIP, RADIUSListenersvcIP, CLIP

    vlan(int): The VLAN number. Default value: 0 Minimum value = 0 Maximum value = 4094

    nd(str): Respond to Neighbor Discovery (ND) requests for this IP address. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    icmp(str): Respond to ICMP requests for this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    vserver(str): Enable or disable the state of all the virtual servers associated with this VIP6 address. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    telnet(str): Allow Telnet access to this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    ftp(str): Allow File Transfer Protocol (FTP) access to this IP address. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    gui(str): Allow graphical user interface (GUI) access to this IP address. Default value: ENABLED Possible values =
        ENABLED, SECUREONLY, DISABLED

    ssh(str): Allow secure Shell (SSH) access to this IP address. Default value: ENABLED Possible values = ENABLED, DISABLED

    snmp(str): Allow Simple Network Management Protocol (SNMP) access to this IP address. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    mgmtaccess(str): Allow access to management applications on this IP address. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    restrictaccess(str): Block access to nonmanagement applications on this IP address. This option is applicable forMIP6s,
        SNIP6s, and NSIP6s, and is disabled by default. Nonmanagement applications can run on the underlying NetScaler
        Free BSD operating system. Default value: DISABLED Possible values = ENABLED, DISABLED

    dynamicrouting(str): Allow dynamic routing on this IP address. Specific to Subnet IPv6 (SNIP6) address. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    hostroute(str): Option to push the VIP6 to ZebOS routing table for Kernel route redistribution through dynamic routing
        protocols. Possible values = ENABLED, DISABLED

    networkroute(str): Option to push the SNIP6 subnet to ZebOS routing table for Kernel route redistribution through dynamic
        routing protocol. Possible values = ENABLED, DISABLED

    tag(int): Tag value for the network/host route associated with this IP. Default value: 0

    ip6hostrtgw(str): IPv6 address of the gateway for the route. If Gateway is not set, VIP uses :: as the gateway. Default
        value: 0

    metric(int): Integer value to add to or subtract from the cost of the route advertised for the VIP6 address. Minimum
        value = -16777215

    vserverrhilevel(str): Advertise or do not advertise the route for the Virtual IP (VIP6) address on the basis of the state
        of the virtual servers associated with that VIP6. * NONE - Advertise the route for the VIP6 address, irrespective
        of the state of the virtual servers associated with the address. * ONE VSERVER - Advertise the route for the VIP6
        address if at least one of the associated virtual servers is in UP state. * ALL VSERVER - Advertise the route for
        the VIP6 address if all of the associated virtual servers are in UP state. * VSVR_CNTRLD. Advertise the route for
        the VIP address according to the RHIstate (RHI STATE) parameter setting on all the associated virtual servers of
        the VIP address along with their states.  When Vserver RHI Level (RHI) parameter is set to VSVR_CNTRLD, the
        following are different RHI behaviors for the VIP address on the basis of RHIstate (RHI STATE) settings on the
        virtual servers associated with the VIP address:  * If you set RHI STATE to PASSIVE on all virtual servers, the
        NetScaler ADC always advertises the route for the VIP address.  * If you set RHI STATE to ACTIVE on all virtual
        servers, the NetScaler ADC advertises the route for the VIP address if at least one of the associated virtual
        servers is in UP state.  *If you set RHI STATE to ACTIVE on some and PASSIVE on others, the NetScaler ADC
        advertises the route for the VIP address if at least one of the associated virtual servers, whose RHI STATE set
        to ACTIVE, is in UP state. Default value: ONE_VSERVER Possible values = ONE_VSERVER, ALL_VSERVERS, NONE,
        VSVR_CNTRLD

    ospf6lsatype(str): Type of LSAs to be used by the IPv6 OSPF protocol, running on the NetScaler appliance, for advertising
        the route for the VIP6 address. Default value: EXTERNAL Possible values = INTRA_AREA, EXTERNAL

    ospfarea(int): ID of the area in which the Intra-Area-Prefix LSAs are to be advertised for the VIP6 address by the IPv6
        OSPF protocol running on the NetScaler appliance. When ospfArea is not set, VIP6 is advertised on all areas.
        Default value: -1 Minimum value = 0 Maximum value = 4294967294LU

    state(str): Enable or disable the IP address. Default value: ENABLED Possible values = DISABLED, ENABLED

    ns_map(str): Mapped IPV4 address for the IPV6 address.

    vrid6(int): A positive integer that uniquely identifies a VMAC address for binding to this VIP address. This binding is
        used to set up NetScaler appliances in an active-active configuration using VRRP. Minimum value = 1 Maximum value
        = 255

    ownernode(int): ID of the cluster node for which you are adding the IP address. Must be used if you want the IP address
        to be active only on the specific node. Can be configured only through the cluster IP address. Cannot be changed
        after the IP address is created. Default value: 255

    ownerdownresponse(str): in cluster system, if the owner node is down, whether should it respond to icmp/arp. Default
        value: YES Possible values = YES, NO

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsip6 <args>

    '''

    result = {}

    payload = {'nsip6': {}}

    if ipv6address:
        payload['nsip6']['ipv6address'] = ipv6address

    if scope:
        payload['nsip6']['scope'] = scope

    if ns_type:
        payload['nsip6']['type'] = ns_type

    if vlan:
        payload['nsip6']['vlan'] = vlan

    if nd:
        payload['nsip6']['nd'] = nd

    if icmp:
        payload['nsip6']['icmp'] = icmp

    if vserver:
        payload['nsip6']['vserver'] = vserver

    if telnet:
        payload['nsip6']['telnet'] = telnet

    if ftp:
        payload['nsip6']['ftp'] = ftp

    if gui:
        payload['nsip6']['gui'] = gui

    if ssh:
        payload['nsip6']['ssh'] = ssh

    if snmp:
        payload['nsip6']['snmp'] = snmp

    if mgmtaccess:
        payload['nsip6']['mgmtaccess'] = mgmtaccess

    if restrictaccess:
        payload['nsip6']['restrictaccess'] = restrictaccess

    if dynamicrouting:
        payload['nsip6']['dynamicrouting'] = dynamicrouting

    if hostroute:
        payload['nsip6']['hostroute'] = hostroute

    if networkroute:
        payload['nsip6']['networkroute'] = networkroute

    if tag:
        payload['nsip6']['tag'] = tag

    if ip6hostrtgw:
        payload['nsip6']['ip6hostrtgw'] = ip6hostrtgw

    if metric:
        payload['nsip6']['metric'] = metric

    if vserverrhilevel:
        payload['nsip6']['vserverrhilevel'] = vserverrhilevel

    if ospf6lsatype:
        payload['nsip6']['ospf6lsatype'] = ospf6lsatype

    if ospfarea:
        payload['nsip6']['ospfarea'] = ospfarea

    if state:
        payload['nsip6']['state'] = state

    if ns_map:
        payload['nsip6']['map'] = ns_map

    if vrid6:
        payload['nsip6']['vrid6'] = vrid6

    if ownernode:
        payload['nsip6']['ownernode'] = ownernode

    if ownerdownresponse:
        payload['nsip6']['ownerdownresponse'] = ownerdownresponse

    if td:
        payload['nsip6']['td'] = td

    execution = __proxy__['citrixns.put']('config/nsip6', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nslicenseproxyserver(serverip=None, servername=None, port=None, save=False):
    '''
    Update the running configuration for the nslicenseproxyserver config key.

    serverip(str): IP address of the License proxy server. Minimum length = 1

    servername(str): Fully qualified domain name of the License proxy server.

    port(int): License proxy server port.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nslicenseproxyserver <args>

    '''

    result = {}

    payload = {'nslicenseproxyserver': {}}

    if serverip:
        payload['nslicenseproxyserver']['serverip'] = serverip

    if servername:
        payload['nslicenseproxyserver']['servername'] = servername

    if port:
        payload['nslicenseproxyserver']['port'] = port

    execution = __proxy__['citrixns.put']('config/nslicenseproxyserver', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nslicenseserver(licenseserverip=None, servername=None, port=None, nodeid=None, save=False):
    '''
    Update the running configuration for the nslicenseserver config key.

    licenseserverip(str): IP address of the License server. Minimum length = 1

    servername(str): Fully qualified domain name of the License server.

    port(int): License server port.

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nslicenseserver <args>

    '''

    result = {}

    payload = {'nslicenseserver': {}}

    if licenseserverip:
        payload['nslicenseserver']['licenseserverip'] = licenseserverip

    if servername:
        payload['nslicenseserver']['servername'] = servername

    if port:
        payload['nslicenseserver']['port'] = port

    if nodeid:
        payload['nslicenseserver']['nodeid'] = nodeid

    execution = __proxy__['citrixns.put']('config/nslicenseserver', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nslimitidentifier(limitidentifier=None, threshold=None, timeslice=None, mode=None, limittype=None,
                             selectorname=None, maxbandwidth=None, trapsintimeslice=None, save=False):
    '''
    Update the running configuration for the nslimitidentifier config key.

    limitidentifier(str): Name for a rate limit identifier. Must begin with an ASCII letter or underscore (_) character, and
        must consist only of ASCII alphanumeric or underscore characters. Reserved words must not be used.

    threshold(int): Maximum number of requests that are allowed in the given timeslice when requests (mode is set as
        REQUEST_RATE) are tracked per timeslice. When connections (mode is set as CONNECTION) are tracked, it is the
        total number of connections that would be let through. Default value: 1 Minimum value = 1

    timeslice(int): Time interval, in milliseconds, specified in multiples of 10, during which requests are tracked to check
        if they cross the threshold. This argument is needed only when the mode is set to REQUEST_RATE. Default value:
        1000 Minimum value = 10

    mode(str): Defines the type of traffic to be tracked. * REQUEST_RATE - Tracks requests/timeslice. * CONNECTION - Tracks
        active transactions.  Examples  1. To permit 20 requests in 10 ms and 2 traps in 10 ms: add limitidentifier
        limit_req -mode request_rate -limitType smooth -timeslice 1000 -Threshold 2000 -trapsInTimeSlice 200  2. To
        permit 50 requests in 10 ms: set limitidentifier limit_req -mode request_rate -timeslice 1000 -Threshold 5000
        -limitType smooth  3. To permit 1 request in 40 ms: set limitidentifier limit_req -mode request_rate -timeslice
        2000 -Threshold 50 -limitType smooth  4. To permit 1 request in 200 ms and 1 trap in 130 ms: set limitidentifier
        limit_req -mode request_rate -timeslice 1000 -Threshold 5 -limitType smooth -trapsInTimeSlice 8  5. To permit
        5000 requests in 1000 ms and 200 traps in 1000 ms: set limitidentifier limit_req -mode request_rate -timeslice
        1000 -Threshold 5000 -limitType BURSTY. Default value: REQUEST_RATE Possible values = CONNECTION, REQUEST_RATE,
        NONE

    limittype(str): Smooth or bursty request type. * SMOOTH - When you want the permitted number of requests in a given
        interval of time to be spread evenly across the timeslice * BURSTY - When you want the permitted number of
        requests to exhaust the quota anytime within the timeslice. This argument is needed only when the mode is set to
        REQUEST_RATE. Default value: BURSTY Possible values = BURSTY, SMOOTH

    selectorname(str): Name of the rate limit selector. If this argument is NULL, rate limiting will be applied on all
        traffic received by the virtual server or the NetScaler (depending on whether the limit identifier is bound to a
        virtual server or globally) without any filtering. Minimum length = 1

    maxbandwidth(int): Maximum bandwidth permitted, in kbps. Minimum value = 0 Maximum value = 4294967287

    trapsintimeslice(int): Number of traps to be sent in the timeslice configured. A value of 0 indicates that traps are
        disabled. Minimum value = 0 Maximum value = 65535

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nslimitidentifier <args>

    '''

    result = {}

    payload = {'nslimitidentifier': {}}

    if limitidentifier:
        payload['nslimitidentifier']['limitidentifier'] = limitidentifier

    if threshold:
        payload['nslimitidentifier']['threshold'] = threshold

    if timeslice:
        payload['nslimitidentifier']['timeslice'] = timeslice

    if mode:
        payload['nslimitidentifier']['mode'] = mode

    if limittype:
        payload['nslimitidentifier']['limittype'] = limittype

    if selectorname:
        payload['nslimitidentifier']['selectorname'] = selectorname

    if maxbandwidth:
        payload['nslimitidentifier']['maxbandwidth'] = maxbandwidth

    if trapsintimeslice:
        payload['nslimitidentifier']['trapsintimeslice'] = trapsintimeslice

    execution = __proxy__['citrixns.put']('config/nslimitidentifier', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nslimitselector(selectorname=None, rule=None, save=False):
    '''
    Update the running configuration for the nslimitselector config key.

    selectorname(str): .

    rule(list(str)): . Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nslimitselector <args>

    '''

    result = {}

    payload = {'nslimitselector': {}}

    if selectorname:
        payload['nslimitselector']['selectorname'] = selectorname

    if rule:
        payload['nslimitselector']['rule'] = rule

    execution = __proxy__['citrixns.put']('config/nslimitselector', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsparam(httpport=None, maxconn=None, maxreq=None, cip=None, cipheader=None, cookieversion=None,
                   securecookie=None, pmtumin=None, pmtutimeout=None, ftpportrange=None, crportrange=None, timezone=None,
                   grantquotamaxclient=None, exclusivequotamaxclient=None, grantquotaspillover=None,
                   exclusivequotaspillover=None, useproxyport=None, internaluserlogin=None,
                   aftpallowrandomsourceport=None, icaports=None, tcpcip=None, servicepathingressvlan=None,
                   secureicaports=None, save=False):
    '''
    Update the running configuration for the nsparam config key.

    httpport(list(int)): HTTP ports on the web server. This allows the system to perform connection off-load for any client
        request that has a destination port matching one of these configured ports. Minimum value = 1 Maximum value =
        65535

    maxconn(int): Maximum number of connections that will be made from the appliance to the web server(s) attached to it. The
        value entered here is applied globally to all attached servers. Default value: 0 Minimum value = 0 Maximum value
        = 4294967294

    maxreq(int): Maximum number of requests that the system can pass on a particular connection between the appliance and a
        server attached to it. Setting this value to 0 allows an unlimited number of requests to be passed. This value is
        overridden by the maximum number of requests configured on the individual service. Minimum value = 0 Maximum
        value = 65535

    cip(str): Enable or disable the insertion of the actual client IP address into the HTTP header request passed from the
        client to one, some, or all servers attached to the system. The passed address can then be accessed through a
        minor modification to the server. * If the CIP header is specified, it will be used as the client IP header. * If
        the CIP header is not specified, the value that has been set will be used as the client IP header. Possible
        values = ENABLED, DISABLED

    cipheader(str): Text that will be used as the client IP address header. Minimum length = 1

    cookieversion(str): Version of the cookie inserted by the system. Possible values = 0, 1

    securecookie(str): Enable or disable secure flag for persistence cookie. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    pmtumin(int): Minimum path MTU value that NetScaler will process in the ICMP fragmentation needed message. If the ICMP
        message contains a value less than this value, then this value is used instead. Default value: 576 Minimum value
        = 168 Maximum value = 1500

    pmtutimeout(int): Interval, in minutes, for flushing the PMTU entries. Default value: 10 Minimum value = 1 Maximum value
        = 1440

    ftpportrange(str): Minimum and maximum port (port range) that FTP services are allowed to use. Minimum length = 1024
        Maximum length = 64000

    crportrange(str): Port range for cache redirection services. Minimum length = 1 Maximum length = 65535

    timezone(str): Time zone for the NetScaler appliance. Name of the time zone should be specified as argument. Possible
        values = CoordinatedUniversalTime, GMT+01:00-CET-Europe/Andorra, GMT+04:00-GST-Asia/Dubai,
        GMT+04:30-AFT-Asia/Kabul, GMT-04:00-AST-America/Antigua, GMT-04:00-AST-America/Anguilla,
        GMT+01:00-CET-Europe/Tirane, GMT+04:00-+04-Asia/Yerevan, GMT+01:00-WAT-Africa/Luanda,
        GMT+13:00-NZDT-Antarctica/McMurdo, GMT+08:00-+08-Antarctica/Casey, GMT+07:00-+07-Antarctica/Davis,
        GMT+10:00-+10-Antarctica/DumontDUrville, GMT+05:00-+05-Antarctica/Mawson, GMT-03:00-CLST-Antarctica/Palmer,
        GMT-03:00--03-Antarctica/Rothera, GMT+03:00-+03-Antarctica/Syowa, GMT+00:00-+00-Antarctica/Troll,
        GMT+06:00-+06-Antarctica/Vostok, GMT-03:00-ART-America/Argentina/Buenos_Aires,
        GMT-03:00-ART-America/Argentina/Cordoba, GMT-03:00-ART-America/Argentina/Salta,
        GMT-03:00-ART-America/Argentina/Jujuy, GMT-03:00-ART-America/Argentina/Tucuman,
        GMT-03:00-ART-America/Argentina/Catamarca, GMT-03:00-ART-America/Argentina/La_Rioja,
        GMT-03:00-ART-America/Argentina/San_Juan, GMT-03:00-ART-America/Argentina/Mendoza,
        GMT-03:00-ART-America/Argentina/San_Luis, GMT-03:00-ART-America/Argentina/Rio_Gallegos,
        GMT-03:00-ART-America/Argentina/Ushuaia, GMT-11:00-SST-Pacific/Pago_Pago, GMT+01:00-CET-Europe/Vienna,
        GMT+11:00-LHDT-Australia/Lord_Howe, GMT+11:00-MIST-Antarctica/Macquarie, GMT+11:00-AEDT-Australia/Hobart,
        GMT+11:00-AEDT-Australia/Currie, GMT+11:00-AEDT-Australia/Melbourne, GMT+11:00-AEDT-Australia/Sydney,
        GMT+10:30-ACDT-Australia/Broken_Hill, GMT+10:00-AEST-Australia/Brisbane, GMT+10:00-AEST-Australia/Lindeman,
        GMT+10:30-ACDT-Australia/Adelaide, GMT+09:30-ACST-Australia/Darwin, GMT+08:00-AWST-Australia/Perth,
        GMT+08:45-ACWST-Australia/Eucla, GMT-04:00-AST-America/Aruba, GMT+02:00-EET-Europe/Mariehamn,
        GMT+04:00-+04-Asia/Baku, GMT+01:00-CET-Europe/Sarajevo, GMT-04:00-AST-America/Barbados, GMT+06:00-BDT-Asia/Dhaka,
        GMT+01:00-CET-Europe/Brussels, GMT+00:00-GMT-Africa/Ouagadougou, GMT+02:00-EET-Europe/Sofia,
        GMT+03:00-AST-Asia/Bahrain, GMT+02:00-CAT-Africa/Bujumbura, GMT+01:00-WAT-Africa/Porto-Novo,
        GMT-04:00-AST-America/St_Barthelemy, GMT-04:00-AST-Atlantic/Bermuda, GMT+08:00-BNT-Asia/Brunei,
        GMT-04:00-BOT-America/La_Paz, GMT-04:00-AST-America/Kralendijk, GMT-02:00-FNT-America/Noronha,
        GMT-03:00-BRT-America/Belem, GMT-03:00-BRT-America/Fortaleza, GMT-03:00-BRT-America/Recife,
        GMT-03:00-BRT-America/Araguaina, GMT-03:00-BRT-America/Maceio, GMT-03:00-BRT-America/Bahia,
        GMT-03:00-BRT-America/Sao_Paulo, GMT-04:00-AMT-America/Campo_Grande, GMT-04:00-AMT-America/Cuiaba,
        GMT-03:00-BRT-America/Santarem, GMT-04:00-AMT-America/Porto_Velho, GMT-04:00-AMT-America/Boa_Vista,
        GMT-04:00-AMT-America/Manaus, GMT-05:00-ACT-America/Eirunepe, GMT-05:00-ACT-America/Rio_Branco,
        GMT-05:00-EST-America/Nassau, GMT+06:00-BTT-Asia/Thimphu, GMT+02:00-CAT-Africa/Gaborone,
        GMT+03:00-+03-Europe/Minsk, GMT-06:00-CST-America/Belize, GMT-03:30-NST-America/St_Johns,
        GMT-04:00-AST-America/Halifax, GMT-04:00-AST-America/Glace_Bay, GMT-04:00-AST-America/Moncton,
        GMT-04:00-AST-America/Goose_Bay, GMT-04:00-AST-America/Blanc-Sablon, GMT-05:00-EST-America/Toronto,
        GMT-05:00-EST-America/Nipigon, GMT-05:00-EST-America/Thunder_Bay, GMT-05:00-EST-America/Iqaluit,
        GMT-05:00-EST-America/Pangnirtung, GMT-05:00-EST-America/Atikokan, GMT-06:00-CST-America/Winnipeg,
        GMT-06:00-CST-America/Rainy_River, GMT-06:00-CST-America/Resolute, GMT-06:00-CST-America/Rankin_Inlet,
        GMT-06:00-CST-America/Regina, GMT-06:00-CST-America/Swift_Current, GMT-07:00-MST-America/Edmonton,
        GMT-07:00-MST-America/Cambridge_Bay, GMT-07:00-MST-America/Yellowknife, GMT-07:00-MST-America/Inuvik,
        GMT-07:00-MST-America/Creston, GMT-07:00-MST-America/Dawson_Creek, GMT-07:00-MST-America/Fort_Nelson,
        GMT-08:00-PST-America/Vancouver, GMT-08:00-PST-America/Whitehorse, GMT-08:00-PST-America/Dawson,
        GMT+06:30-CCT-Indian/Cocos, GMT+01:00-WAT-Africa/Kinshasa, GMT+02:00-CAT-Africa/Lubumbashi,
        GMT+01:00-WAT-Africa/Bangui, GMT+01:00-WAT-Africa/Brazzaville, GMT+01:00-CET-Europe/Zurich,
        GMT+00:00-GMT-Africa/Abidjan, GMT-10:00-CKT-Pacific/Rarotonga, GMT-03:00-CLST-America/Santiago,
        GMT-05:00-EASST-Pacific/Easter, GMT+01:00-WAT-Africa/Douala, GMT+08:00-CST-Asia/Shanghai,
        GMT+06:00-XJT-Asia/Urumqi, GMT-05:00-COT-America/Bogota, GMT-06:00-CST-America/Costa_Rica,
        GMT-05:00-CST-America/Havana, GMT-01:00-CVT-Atlantic/Cape_Verde, GMT-04:00-AST-America/Curacao,
        GMT+07:00-CXT-Indian/Christmas, GMT+02:00-EET-Asia/Nicosia, GMT+01:00-CET-Europe/Prague,
        GMT+01:00-CET-Europe/Berlin, GMT+01:00-CET-Europe/Busingen, GMT+03:00-EAT-Africa/Djibouti,
        GMT+01:00-CET-Europe/Copenhagen, GMT-04:00-AST-America/Dominica, GMT-04:00-AST-America/Santo_Domingo,
        GMT+01:00-CET-Africa/Algiers, GMT-05:00-ECT-America/Guayaquil, GMT-06:00-GALT-Pacific/Galapagos,
        GMT+02:00-EET-Europe/Tallinn, GMT+02:00-EET-Africa/Cairo, GMT+00:00-WET-Africa/El_Aaiun,
        GMT+03:00-EAT-Africa/Asmara, GMT+01:00-CET-Europe/Madrid, GMT+01:00-CET-Africa/Ceuta,
        GMT+00:00-WET-Atlantic/Canary, GMT+03:00-EAT-Africa/Addis_Ababa, GMT+02:00-EET-Europe/Helsinki,
        GMT+12:00-FJT-Pacific/Fiji, GMT-03:00-FKST-Atlantic/Stanley, GMT+10:00-CHUT-Pacific/Chuuk,
        GMT+11:00-PONT-Pacific/Pohnpei, GMT+11:00-KOST-Pacific/Kosrae, GMT+00:00-WET-Atlantic/Faroe,
        GMT+01:00-CET-Europe/Paris, GMT+01:00-WAT-Africa/Libreville, GMT+00:00-GMT-Europe/London,
        GMT-04:00-AST-America/Grenada, GMT+04:00-+04-Asia/Tbilisi, GMT-03:00-GFT-America/Cayenne,
        GMT+00:00-GMT-Europe/Guernsey, GMT+00:00-GMT-Africa/Accra, GMT+01:00-CET-Europe/Gibraltar,
        GMT-03:00-WGT-America/Godthab, GMT+00:00-GMT-America/Danmarkshavn, GMT-01:00-EGT-America/Scoresbysund,
        GMT-04:00-AST-America/Thule, GMT+00:00-GMT-Africa/Banjul, GMT+00:00-GMT-Africa/Conakry,
        GMT-04:00-AST-America/Guadeloupe, GMT+01:00-WAT-Africa/Malabo, GMT+02:00-EET-Europe/Athens,
        GMT-02:00-GST-Atlantic/South_Georgia, GMT-06:00-CST-America/Guatemala, GMT+10:00-ChST-Pacific/Guam,
        GMT+00:00-GMT-Africa/Bissau, GMT-04:00-GYT-America/Guyana, GMT+08:00-HKT-Asia/Hong_Kong,
        GMT-06:00-CST-America/Tegucigalpa, GMT+01:00-CET-Europe/Zagreb, GMT-05:00-EST-America/Port-au-Prince,
        GMT+01:00-CET-Europe/Budapest, GMT+07:00-WIB-Asia/Jakarta, GMT+07:00-WIB-Asia/Pontianak,
        GMT+08:00-WITA-Asia/Makassar, GMT+09:00-WIT-Asia/Jayapura, GMT+00:00-GMT-Europe/Dublin,
        GMT+02:00-IST-Asia/Jerusalem, GMT+00:00-GMT-Europe/Isle_of_Man, GMT+05:30-IST-Asia/Kolkata,
        GMT+06:00-IOT-Indian/Chagos, GMT+03:00-AST-Asia/Baghdad, GMT+03:30-IRST-Asia/Tehran,
        GMT+00:00-GMT-Atlantic/Reykjavik, GMT+01:00-CET-Europe/Rome, GMT+00:00-GMT-Europe/Jersey,
        GMT-05:00-EST-America/Jamaica, GMT+02:00-EET-Asia/Amman, GMT+09:00-JST-Asia/Tokyo, GMT+03:00-EAT-Africa/Nairobi,
        GMT+06:00-+06-Asia/Bishkek, GMT+07:00-ICT-Asia/Phnom_Penh, GMT+12:00-GILT-Pacific/Tarawa,
        GMT+13:00-PHOT-Pacific/Enderbury, GMT+14:00-LINT-Pacific/Kiritimati, GMT+03:00-EAT-Indian/Comoro,
        GMT-04:00-AST-America/St_Kitts, GMT+08:30-KST-Asia/Pyongyang, GMT+09:00-KST-Asia/Seoul,
        GMT+03:00-AST-Asia/Kuwait, GMT-05:00-EST-America/Cayman, GMT+06:00-+06-Asia/Almaty, GMT+06:00-+06-Asia/Qyzylorda,
        GMT+05:00-+05-Asia/Aqtobe, GMT+05:00-+05-Asia/Aqtau, GMT+05:00-+05-Asia/Oral, GMT+07:00-ICT-Asia/Vientiane,
        GMT+02:00-EET-Asia/Beirut, GMT-04:00-AST-America/St_Lucia, GMT+01:00-CET-Europe/Vaduz,
        GMT+05:30-IST-Asia/Colombo, GMT+00:00-GMT-Africa/Monrovia, GMT+02:00-SAST-Africa/Maseru,
        GMT+02:00-EET-Europe/Vilnius, GMT+01:00-CET-Europe/Luxembourg, GMT+02:00-EET-Europe/Riga,
        GMT+02:00-EET-Africa/Tripoli, GMT+00:00-WET-Africa/Casablanca, GMT+01:00-CET-Europe/Monaco,
        GMT+02:00-EET-Europe/Chisinau, GMT+01:00-CET-Europe/Podgorica, GMT-04:00-AST-America/Marigot,
        GMT+03:00-EAT-Indian/Antananarivo, GMT+12:00-MHT-Pacific/Majuro, GMT+12:00-MHT-Pacific/Kwajalein,
        GMT+01:00-CET-Europe/Skopje, GMT+00:00-GMT-Africa/Bamako, GMT+06:30-MMT-Asia/Yangon,
        GMT+08:00-ULAT-Asia/Ulaanbaatar, GMT+07:00-HOVT-Asia/Hovd, GMT+08:00-CHOT-Asia/Choibalsan,
        GMT+08:00-CST-Asia/Macau, GMT+10:00-ChST-Pacific/Saipan, GMT-04:00-AST-America/Martinique,
        GMT+00:00-GMT-Africa/Nouakchott, GMT-04:00-AST-America/Montserrat, GMT+01:00-CET-Europe/Malta,
        GMT+04:00-MUT-Indian/Mauritius, GMT+05:00-MVT-Indian/Maldives, GMT+02:00-CAT-Africa/Blantyre,
        GMT-06:00-CST-America/Mexico_City, GMT-05:00-EST-America/Cancun, GMT-06:00-CST-America/Merida,
        GMT-06:00-CST-America/Monterrey, GMT-06:00-CST-America/Matamoros, GMT-07:00-MST-America/Mazatlan,
        GMT-07:00-MST-America/Chihuahua, GMT-07:00-MST-America/Ojinaga, GMT-07:00-MST-America/Hermosillo,
        GMT-08:00-PST-America/Tijuana, GMT-06:00-CST-America/Bahia_Banderas, GMT+08:00-MYT-Asia/Kuala_Lumpur,
        GMT+08:00-MYT-Asia/Kuching, GMT+02:00-CAT-Africa/Maputo, GMT+02:00-WAST-Africa/Windhoek,
        GMT+11:00-NCT-Pacific/Noumea, GMT+01:00-WAT-Africa/Niamey, GMT+11:00-NFT-Pacific/Norfolk,
        GMT+01:00-WAT-Africa/Lagos, GMT-06:00-CST-America/Managua, GMT+01:00-CET-Europe/Amsterdam,
        GMT+01:00-CET-Europe/Oslo, GMT+05:45-NPT-Asia/Kathmandu, GMT+12:00-NRT-Pacific/Nauru, GMT-11:00-NUT-Pacific/Niue,
        GMT+13:00-NZDT-Pacific/Auckland, GMT+13:45-CHADT-Pacific/Chatham, GMT+04:00-GST-Asia/Muscat,
        GMT-05:00-EST-America/Panama, GMT-05:00-PET-America/Lima, GMT-10:00-TAHT-Pacific/Tahiti,
        GMT-09:30-MART-Pacific/Marquesas, GMT-09:00-GAMT-Pacific/Gambier, GMT+10:00-PGT-Pacific/Port_Moresby,
        GMT+11:00-BST-Pacific/Bougainville, GMT+08:00-PHT-Asia/Manila, GMT+05:00-PKT-Asia/Karachi,
        GMT+01:00-CET-Europe/Warsaw, GMT-03:00-PMST-America/Miquelon, GMT-08:00-PST-Pacific/Pitcairn,
        GMT-04:00-AST-America/Puerto_Rico, GMT+02:00-EET-Asia/Gaza, GMT+02:00-EET-Asia/Hebron,
        GMT+00:00-WET-Europe/Lisbon, GMT+00:00-WET-Atlantic/Madeira, GMT-01:00-AZOT-Atlantic/Azores,
        GMT+09:00-PWT-Pacific/Palau, GMT-03:00-PYST-America/Asuncion, GMT+03:00-AST-Asia/Qatar,
        GMT+04:00-RET-Indian/Reunion, GMT+02:00-EET-Europe/Bucharest, GMT+01:00-CET-Europe/Belgrade,
        GMT+02:00-EET-Europe/Kaliningrad, GMT+03:00-MSK-Europe/Moscow, GMT+03:00-MSK-Europe/Simferopol,
        GMT+03:00-+03-Europe/Volgograd, GMT+03:00-+03-Europe/Kirov, GMT+04:00-+04-Europe/Astrakhan,
        GMT+04:00-+04-Europe/Samara, GMT+04:00-+04-Europe/Ulyanovsk, GMT+05:00-+05-Asia/Yekaterinburg,
        GMT+06:00-+06-Asia/Omsk, GMT+07:00-+07-Asia/Novosibirsk, GMT+07:00-+07-Asia/Barnaul, GMT+07:00-+07-Asia/Tomsk,
        GMT+07:00-+07-Asia/Novokuznetsk, GMT+07:00-+07-Asia/Krasnoyarsk, GMT+08:00-+08-Asia/Irkutsk,
        GMT+09:00-+09-Asia/Chita, GMT+09:00-+09-Asia/Yakutsk, GMT+09:00-+09-Asia/Khandyga,
        GMT+10:00-+10-Asia/Vladivostok, GMT+10:00-+10-Asia/Ust-Nera, GMT+11:00-+11-Asia/Magadan,
        GMT+11:00-+11-Asia/Sakhalin, GMT+11:00-+11-Asia/Srednekolymsk, GMT+12:00-+12-Asia/Kamchatka,
        GMT+12:00-+12-Asia/Anadyr, GMT+02:00-CAT-Africa/Kigali, GMT+03:00-AST-Asia/Riyadh,
        GMT+11:00-SBT-Pacific/Guadalcanal, GMT+04:00-SCT-Indian/Mahe, GMT+03:00-EAT-Africa/Khartoum,
        GMT+01:00-CET-Europe/Stockholm, GMT+08:00-SGT-Asia/Singapore, GMT+00:00-GMT-Atlantic/St_Helena,
        GMT+01:00-CET-Europe/Ljubljana, GMT+01:00-CET-Arctic/Longyearbyen, GMT+01:00-CET-Europe/Bratislava,
        GMT+00:00-GMT-Africa/Freetown, GMT+01:00-CET-Europe/San_Marino, GMT+00:00-GMT-Africa/Dakar,
        GMT+03:00-EAT-Africa/Mogadishu, GMT-03:00-SRT-America/Paramaribo, GMT+03:00-EAT-Africa/Juba,
        GMT+00:00-GMT-Africa/Sao_Tome, GMT-06:00-CST-America/El_Salvador, GMT-04:00-AST-America/Lower_Princes,
        GMT+02:00-EET-Asia/Damascus, GMT+02:00-SAST-Africa/Mbabane, GMT-04:00-AST-America/Grand_Turk,
        GMT+01:00-WAT-Africa/Ndjamena, GMT+05:00-+05-Indian/Kerguelen, GMT+00:00-GMT-Africa/Lome,
        GMT+07:00-ICT-Asia/Bangkok, GMT+05:00-+05-Asia/Dushanbe, GMT+13:00-TKT-Pacific/Fakaofo, GMT+09:00-TLT-Asia/Dili,
        GMT+05:00-+05-Asia/Ashgabat, GMT+01:00-CET-Africa/Tunis, GMT+13:00-TOT-Pacific/Tongatapu,
        GMT+03:00-+03-Europe/Istanbul, GMT-04:00-AST-America/Port_of_Spain, GMT+12:00-TVT-Pacific/Funafuti,
        GMT+08:00-CST-Asia/Taipei, GMT+03:00-EAT-Africa/Dar_es_Salaam, GMT+02:00-EET-Europe/Kiev,
        GMT+02:00-EET-Europe/Uzhgorod, GMT+02:00-EET-Europe/Zaporozhye, GMT+03:00-EAT-Africa/Kampala,
        GMT-10:00-HST-Pacific/Johnston, GMT-11:00-SST-Pacific/Midway, GMT+12:00-WAKT-Pacific/Wake,
        GMT-05:00-EST-America/New_York, GMT-05:00-EST-America/Detroit, GMT-05:00-EST-America/Kentucky/Louisville,
        GMT-05:00-EST-America/Kentucky/Monticello, GMT-05:00-EST-America/Indiana/Indianapolis,
        GMT-05:00-EST-America/Indiana/Vincennes, GMT-05:00-EST-America/Indiana/Winamac,
        GMT-05:00-EST-America/Indiana/Marengo, GMT-05:00-EST-America/Indiana/Petersburg,
        GMT-05:00-EST-America/Indiana/Vevay, GMT-06:00-CST-America/Chicago, GMT-06:00-CST-America/Indiana/Tell_City,
        GMT-06:00-CST-America/Indiana/Knox, GMT-06:00-CST-America/Menominee, GMT-06:00-CST-America/North_Dakota/Center,
        GMT-06:00-CST-America/North_Dakota/New_Salem, GMT-06:00-CST-America/North_Dakota/Beulah,
        GMT-07:00-MST-America/Denver, GMT-07:00-MST-America/Boise, GMT-07:00-MST-America/Phoenix,
        GMT-08:00-PST-America/Los_Angeles, GMT-09:00-AKST-America/Anchorage, GMT-09:00-AKST-America/Juneau,
        GMT-09:00-AKST-America/Sitka, GMT-09:00-AKST-America/Metlakatla, GMT-09:00-AKST-America/Yakutat,
        GMT-09:00-AKST-America/Nome, GMT-10:00-HST-America/Adak, GMT-10:00-HST-Pacific/Honolulu,
        GMT-03:00-UYT-America/Montevideo, GMT+05:00-+05-Asia/Samarkand, GMT+05:00-+05-Asia/Tashkent,
        GMT+01:00-CET-Europe/Vatican, GMT-04:00-AST-America/St_Vincent, GMT-04:00-VET-America/Caracas,
        GMT-04:00-AST-America/Tortola, GMT-04:00-AST-America/St_Thomas, GMT+07:00-ICT-Asia/Ho_Chi_Minh,
        GMT+11:00-VUT-Pacific/Efate, GMT+12:00-WFT-Pacific/Wallis, GMT+14:00-WSDT-Pacific/Apia, GMT+03:00-AST-Asia/Aden,
        GMT+03:00-EAT-Indian/Mayotte, GMT+02:00-SAST-Africa/Johannesburg, GMT+02:00-CAT-Africa/Lusaka,
        GMT+02:00-CAT-Africa/Harare

    grantquotamaxclient(int): Percentage of shared quota to be granted at a time for maxClient. Default value: 10 Minimum
        value = 0 Maximum value = 100

    exclusivequotamaxclient(int): Percentage of maxClient to be given to PEs. Default value: 80 Minimum value = 0 Maximum
        value = 100

    grantquotaspillover(int): Percentage of shared quota to be granted at a time for spillover. Default value: 10 Minimum
        value = 0 Maximum value = 100

    exclusivequotaspillover(int): Percentage of maximum limit to be given to PEs. Default value: 80 Minimum value = 0 Maximum
        value = 100

    useproxyport(str): Enable/Disable use_proxy_port setting. Default value: ENABLED Possible values = ENABLED, DISABLED

    internaluserlogin(str): Enables/disables the internal user from logging in to the appliance. Before disabling internal
        user login, you must have key-based authentication set up on the appliance. The file name for the key pair must
        be "ns_comm_key". Default value: ENABLED Possible values = ENABLED, DISABLED

    aftpallowrandomsourceport(str): Allow the FTP server to come from a random source port for active FTP data connections.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    icaports(list(int)): The ICA ports on the Web server. This allows the system to perform connection off-load for any
        client request that has a destination port matching one of these configured ports. Minimum value = 1

    tcpcip(str): Enable or disable the insertion of the client TCP/IP header in TCP payload passed from the client to one,
        some, or all servers attached to the system. The passed address can then be accessed through a minor modification
        to the server. Default value: DISABLED Possible values = ENABLED, DISABLED

    servicepathingressvlan(int): VLAN on which the subscriber traffic arrives on the appliance. Minimum value = 1

    secureicaports(list(int)): The Secure ICA ports on the Web server. This allows the system to perform connection off-load
        for any  client request that has a destination port matching one of these configured ports. Minimum value = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsparam <args>

    '''

    result = {}

    payload = {'nsparam': {}}

    if httpport:
        payload['nsparam']['httpport'] = httpport

    if maxconn:
        payload['nsparam']['maxconn'] = maxconn

    if maxreq:
        payload['nsparam']['maxreq'] = maxreq

    if cip:
        payload['nsparam']['cip'] = cip

    if cipheader:
        payload['nsparam']['cipheader'] = cipheader

    if cookieversion:
        payload['nsparam']['cookieversion'] = cookieversion

    if securecookie:
        payload['nsparam']['securecookie'] = securecookie

    if pmtumin:
        payload['nsparam']['pmtumin'] = pmtumin

    if pmtutimeout:
        payload['nsparam']['pmtutimeout'] = pmtutimeout

    if ftpportrange:
        payload['nsparam']['ftpportrange'] = ftpportrange

    if crportrange:
        payload['nsparam']['crportrange'] = crportrange

    if timezone:
        payload['nsparam']['timezone'] = timezone

    if grantquotamaxclient:
        payload['nsparam']['grantquotamaxclient'] = grantquotamaxclient

    if exclusivequotamaxclient:
        payload['nsparam']['exclusivequotamaxclient'] = exclusivequotamaxclient

    if grantquotaspillover:
        payload['nsparam']['grantquotaspillover'] = grantquotaspillover

    if exclusivequotaspillover:
        payload['nsparam']['exclusivequotaspillover'] = exclusivequotaspillover

    if useproxyport:
        payload['nsparam']['useproxyport'] = useproxyport

    if internaluserlogin:
        payload['nsparam']['internaluserlogin'] = internaluserlogin

    if aftpallowrandomsourceport:
        payload['nsparam']['aftpallowrandomsourceport'] = aftpallowrandomsourceport

    if icaports:
        payload['nsparam']['icaports'] = icaports

    if tcpcip:
        payload['nsparam']['tcpcip'] = tcpcip

    if servicepathingressvlan:
        payload['nsparam']['servicepathingressvlan'] = servicepathingressvlan

    if secureicaports:
        payload['nsparam']['secureicaports'] = secureicaports

    execution = __proxy__['citrixns.put']('config/nsparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nspartition(partitionname=None, maxbandwidth=None, minbandwidth=None, maxconn=None, maxmemlimit=None,
                       partitionmac=None, save=False):
    '''
    Update the running configuration for the nspartition config key.

    partitionname(str): Name of the Partition. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Minimum length = 1

    maxbandwidth(int): Maximum bandwidth, in Kbps, that the partition can consume. A zero value indicates the bandwidth is
        unrestricted on the partition and it can consume up to the system limits. Default value: 10240

    minbandwidth(int): Minimum bandwidth, in Kbps, that the partition can consume. A zero value indicates the bandwidth is
        unrestricted on the partition and it can consume up to the system limits. Default value: 10240

    maxconn(int): Maximum number of concurrent connections that can be open in the partition. A zero value indicates no limit
        on number of open connections. Default value: 1024

    maxmemlimit(int): Maximum memory, in megabytes, allocated to the partition. A zero value indicates the memory is
        unlimited on the partition and it can consume up to the system limits. Default value: 10

    partitionmac(str): Special MAC address for the partition which is used for communication over shared vlans in this
        partition. If not specified, the MAC address is auto-generated.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nspartition <args>

    '''

    result = {}

    payload = {'nspartition': {}}

    if partitionname:
        payload['nspartition']['partitionname'] = partitionname

    if maxbandwidth:
        payload['nspartition']['maxbandwidth'] = maxbandwidth

    if minbandwidth:
        payload['nspartition']['minbandwidth'] = minbandwidth

    if maxconn:
        payload['nspartition']['maxconn'] = maxconn

    if maxmemlimit:
        payload['nspartition']['maxmemlimit'] = maxmemlimit

    if partitionmac:
        payload['nspartition']['partitionmac'] = partitionmac

    execution = __proxy__['citrixns.put']('config/nspartition', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nspbr(name=None, action=None, td=None, srcip=None, srcipop=None, srcipval=None, srcport=None, srcportop=None,
                 srcportval=None, destip=None, destipop=None, destipval=None, destport=None, destportop=None,
                 destportval=None, nexthop=None, nexthopval=None, iptunnel=None, iptunnelname=None, vxlanvlanmap=None,
                 srcmac=None, srcmacmask=None, protocol=None, protocolnumber=None, vlan=None, vxlan=None, interface=None,
                 priority=None, msr=None, monitor=None, state=None, ownergroup=None, detail=None, save=False):
    '''
    Update the running configuration for the nspbr config key.

    name(str): Name for the PBR. Must begin with an ASCII alphabetic or underscore \\(_\\) character, and must contain only
        ASCII alphanumeric, underscore, hash \\(\\#\\), period \\(.\\), space, colon \\(:\\), at \\(@\\), equals \\(=\\),
        and hyphen \\(-\\) characters. Cannot be changed after the PBR is created. Minimum length = 1

    action(str): Action to perform on the outgoing IPv4 packets that match the PBR.  Available settings function as follows:
        * ALLOW - The NetScaler appliance sends the packet to the designated next-hop router. * DENY - The NetScaler
        appliance applies the routing table for normal destination-based routing. Possible values = ALLOW, DENY

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    srcip(bool): IP address or range of IP addresses to match against the source IP address of an outgoing IPv4 packet. In
        the command line interface, separate the range with a hyphen. For example: 10.102.29.30-10.102.29.189.

    srcipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcipval(str): IP address or range of IP addresses to match against the source IP address of an outgoing IPv4 packet. In
        the command line interface, separate the range with a hyphen. For example: 10.102.29.30-10.102.29.189.

    srcport(bool): Port number or range of port numbers to match against the source port number of an outgoing IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The destination port
        can be specified only for TCP and UDP protocols.

    srcportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcportval(str): Port number or range of port numbers to match against the source port number of an outgoing IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The destination port
        can be specified only for TCP and UDP protocols. Maximum length = 65535

    destip(bool): IP address or range of IP addresses to match against the destination IP address of an outgoing IPv4 packet.
        In the command line interface, separate the range with a hyphen. For example: 10.102.29.30-10.102.29.189.

    destipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destipval(str): IP address or range of IP addresses to match against the destination IP address of an outgoing IPv4
        packet. In the command line interface, separate the range with a hyphen. For example:
        10.102.29.30-10.102.29.189.

    destport(bool): Port number or range of port numbers to match against the destination port number of an outgoing IPv4
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols.

    destportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destportval(str): Port number or range of port numbers to match against the destination port number of an outgoing IPv4
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols. Maximum length = 65535

    nexthop(bool): IP address of the next hop router or the name of the link load balancing virtual server to which to send
        matching packets if action is set to ALLOW. If you specify a link load balancing (LLB) virtual server, which can
        provide a backup if a next hop link fails, first make sure that the next hops bound to the LLB virtual server are
        actually next hops that are directly connected to the NetScaler appliance. Otherwise, the NetScaler throws an
        error when you attempt to create the PBR. The next hop can be null to represent null routes.

    nexthopval(str): The Next Hop IP address or gateway name.

    iptunnel(bool): The Tunnel name.

    iptunnelname(str): The iptunnel name where packets need to be forwarded upon.

    vxlanvlanmap(str): The vlan to vxlan mapping to be applied for incoming packets over this pbr tunnel.

    srcmac(str): MAC address to match against the source MAC address of an outgoing IPv4 packet.

    srcmacmask(str): Used to define range of Source MAC address. It takes string of 0 and 1, 0s are for exact match and 1s
        for wildcard. For matching first 3 bytes of MAC address, srcMacMask value "000000111111". . Default value:
        "000000000000"

    protocol(str): Protocol, identified by protocol name, to match against the protocol of an outgoing IPv4 packet. Possible
        values = ICMP, IGMP, TCP, EGP, IGP, ARGUS, UDP, RDP, RSVP, EIGRP, L2TP, ISIS

    protocolnumber(int): Protocol, identified by protocol number, to match against the protocol of an outgoing IPv4 packet.
        Minimum value = 1 Maximum value = 255

    vlan(int): ID of the VLAN. The NetScaler appliance compares the PBR only to the outgoing packets on the specified VLAN.
        If you do not specify any interface ID, the appliance compares the PBR to the outgoing packets on all VLANs.
        Minimum value = 1 Maximum value = 4094

    vxlan(int): ID of the VXLAN. The NetScaler appliance compares the PBR only to the outgoing packets on the specified
        VXLAN. If you do not specify any interface ID, the appliance compares the PBR to the outgoing packets on all
        VXLANs. Minimum value = 1 Maximum value = 16777215

    interface(str): ID of an interface. The NetScaler appliance compares the PBR only to the outgoing packets on the
        specified interface. If you do not specify any value, the appliance compares the PBR to the outgoing packets on
        all interfaces.

    priority(int): Priority of the PBR, which determines the order in which it is evaluated relative to the other PBRs. If
        you do not specify priorities while creating PBRs, the PBRs are evaluated in the order in which they are created.
        Minimum value = 1 Maximum value = 81920

    msr(str): Monitor the route specified byte Next Hop parameter. This parameter is not applicable if you specify a link
        load balancing (LLB) virtual server name with the Next Hop parameter. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    monitor(str): The name of the monitor.(Can be only of type ping or ARP ). Minimum length = 1

    state(str): Enable or disable the PBR. After you apply the PBRs, the NetScaler appliance compares outgoing packets to the
        enabled PBRs. Default value: ENABLED Possible values = ENABLED, DISABLED

    ownergroup(str): The owner node group in a Cluster for this pbr rule. If ownernode is not specified then the pbr rule is
        treated as Striped pbr rule. Default value: DEFAULT_NG Minimum length = 1

    detail(bool): To get a detailed view.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nspbr <args>

    '''

    result = {}

    payload = {'nspbr': {}}

    if name:
        payload['nspbr']['name'] = name

    if action:
        payload['nspbr']['action'] = action

    if td:
        payload['nspbr']['td'] = td

    if srcip:
        payload['nspbr']['srcip'] = srcip

    if srcipop:
        payload['nspbr']['srcipop'] = srcipop

    if srcipval:
        payload['nspbr']['srcipval'] = srcipval

    if srcport:
        payload['nspbr']['srcport'] = srcport

    if srcportop:
        payload['nspbr']['srcportop'] = srcportop

    if srcportval:
        payload['nspbr']['srcportval'] = srcportval

    if destip:
        payload['nspbr']['destip'] = destip

    if destipop:
        payload['nspbr']['destipop'] = destipop

    if destipval:
        payload['nspbr']['destipval'] = destipval

    if destport:
        payload['nspbr']['destport'] = destport

    if destportop:
        payload['nspbr']['destportop'] = destportop

    if destportval:
        payload['nspbr']['destportval'] = destportval

    if nexthop:
        payload['nspbr']['nexthop'] = nexthop

    if nexthopval:
        payload['nspbr']['nexthopval'] = nexthopval

    if iptunnel:
        payload['nspbr']['iptunnel'] = iptunnel

    if iptunnelname:
        payload['nspbr']['iptunnelname'] = iptunnelname

    if vxlanvlanmap:
        payload['nspbr']['vxlanvlanmap'] = vxlanvlanmap

    if srcmac:
        payload['nspbr']['srcmac'] = srcmac

    if srcmacmask:
        payload['nspbr']['srcmacmask'] = srcmacmask

    if protocol:
        payload['nspbr']['protocol'] = protocol

    if protocolnumber:
        payload['nspbr']['protocolnumber'] = protocolnumber

    if vlan:
        payload['nspbr']['vlan'] = vlan

    if vxlan:
        payload['nspbr']['vxlan'] = vxlan

    if interface:
        payload['nspbr']['Interface'] = interface

    if priority:
        payload['nspbr']['priority'] = priority

    if msr:
        payload['nspbr']['msr'] = msr

    if monitor:
        payload['nspbr']['monitor'] = monitor

    if state:
        payload['nspbr']['state'] = state

    if ownergroup:
        payload['nspbr']['ownergroup'] = ownergroup

    if detail:
        payload['nspbr']['detail'] = detail

    execution = __proxy__['citrixns.put']('config/nspbr', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nspbr6(name=None, td=None, action=None, srcipv6=None, srcipop=None, srcipv6val=None, srcport=None,
                  srcportop=None, srcportval=None, destipv6=None, destipop=None, destipv6val=None, destport=None,
                  destportop=None, destportval=None, srcmac=None, srcmacmask=None, protocol=None, protocolnumber=None,
                  vlan=None, vxlan=None, interface=None, priority=None, state=None, msr=None, monitor=None, nexthop=None,
                  nexthopval=None, iptunnel=None, vxlanvlanmap=None, nexthopvlan=None, ownergroup=None, detail=None,
                  save=False):
    '''
    Update the running configuration for the nspbr6 config key.

    name(str): Name for the PBR6. Must begin with an ASCII alphabetic or underscore \\(_\\) character, and must contain only
        ASCII alphanumeric, underscore, hash \\(\\#\\), period \\(.\\), space, colon \\(:\\), at \\(@\\), equals \\(=\\),
        and hyphen \\(-\\) characters. Cannot be changed after the PBR6 is created. Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    action(str): Action to perform on the outgoing IPv6 packets that match the PBR6.  Available settings function as follows:
        * ALLOW - The NetScaler appliance sends the packet to the designated next-hop router. * DENY - The NetScaler
        appliance applies the routing table for normal destination-based routing. Possible values = ALLOW, DENY

    srcipv6(bool): IP address or range of IP addresses to match against the source IP address of an outgoing IPv6 packet. In
        the command line interface, separate the range with a hyphen.

    srcipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcipv6val(str): IP address or range of IP addresses to match against the source IP address of an outgoing IPv6 packet.
        In the command line interface, separate the range with a hyphen.

    srcport(bool): Port number or range of port numbers to match against the source port number of an outgoing IPv6 packet.
        In the command line interface, separate the range with a hyphen. For example: 40-90.

    srcportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    srcportval(str): Source port (range). Maximum length = 65535

    destipv6(bool): IP address or range of IP addresses to match against the destination IP address of an outgoing IPv6
        packet. In the command line interface, separate the range with a hyphen.

    destipop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destipv6val(str): IP address or range of IP addresses to match against the destination IP address of an outgoing IPv6
        packet. In the command line interface, separate the range with a hyphen.

    destport(bool): Port number or range of port numbers to match against the destination port number of an outgoing IPv6
        packet. In the command line interface, separate the range with a hyphen. For example: 40-90.  Note: The
        destination port can be specified only for TCP and UDP protocols.

    destportop(str): Either the equals (=) or does not equal (!=) logical operator. Possible values = =, !=, EQ, NEQ

    destportval(str): Destination port (range). Maximum length = 65535

    srcmac(str): MAC address to match against the source MAC address of an outgoing IPv6 packet.

    srcmacmask(str): Used to define range of Source MAC address. It takes string of 0 and 1, 0s are for exact match and 1s
        for wildcard. For matching first 3 bytes of MAC address, srcMacMask value "000000111111". . Default value:
        "000000000000"

    protocol(str): Protocol, identified by protocol name, to match against the protocol of an outgoing IPv6 packet. Possible
        values = ICMPV6, TCP, UDP

    protocolnumber(int): Protocol, identified by protocol number, to match against the protocol of an outgoing IPv6 packet.
        Minimum value = 1 Maximum value = 255

    vlan(int): ID of the VLAN. The NetScaler appliance compares the PBR6 only to the outgoing packets on the specified VLAN.
        If you do not specify an interface ID, the appliance compares the PBR6 to the outgoing packets on all VLANs.
        Minimum value = 1 Maximum value = 4094

    vxlan(int): ID of the VXLAN. The NetScaler appliance compares the PBR6 only to the outgoing packets on the specified
        VXLAN. If you do not specify an interface ID, the appliance compares the PBR6 to the outgoing packets on all
        VXLANs. Minimum value = 1 Maximum value = 16777215

    interface(str): ID of an interface. The NetScaler appliance compares the PBR6 only to the outgoing packets on the
        specified interface. If you do not specify a value, the appliance compares the PBR6 to the outgoing packets on
        all interfaces.

    priority(int): Priority of the PBR6, which determines the order in which it is evaluated relative to the other PBR6s. If
        you do not specify priorities while creating PBR6s, the PBR6s are evaluated in the order in which they are
        created. Minimum value = 1 Maximum value = 81920

    state(str): Enable or disable the PBR6. After you apply the PBR6s, the NetScaler appliance compares outgoing packets to
        the enabled PBR6s. Default value: ENABLED Possible values = ENABLED, DISABLED

    msr(str): Monitor the route specified by the Next Hop parameter. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    monitor(str): The name of the monitor.(Can be only of type ping or ARP ). Minimum length = 1

    nexthop(bool): IP address of the next hop router to which to send matching packets if action is set to ALLOW. This next
        hop should be directly reachable from the appliance.

    nexthopval(str): The Next Hop IPv6 address.

    iptunnel(str): The iptunnel name where packets need to be forwarded upon.

    vxlanvlanmap(str): The vlan to vxlan mapping to be applied for incoming packets over this pbr tunnel.

    nexthopvlan(int): VLAN number to be used for link local nexthop . Minimum value = 1 Maximum value = 4094

    ownergroup(str): The owner node group in a Cluster for this pbr rule. If owner node group is not specified then the pbr
        rule is treated as Striped pbr rule. Default value: DEFAULT_NG Minimum length = 1

    detail(bool): To get a detailed view.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nspbr6 <args>

    '''

    result = {}

    payload = {'nspbr6': {}}

    if name:
        payload['nspbr6']['name'] = name

    if td:
        payload['nspbr6']['td'] = td

    if action:
        payload['nspbr6']['action'] = action

    if srcipv6:
        payload['nspbr6']['srcipv6'] = srcipv6

    if srcipop:
        payload['nspbr6']['srcipop'] = srcipop

    if srcipv6val:
        payload['nspbr6']['srcipv6val'] = srcipv6val

    if srcport:
        payload['nspbr6']['srcport'] = srcport

    if srcportop:
        payload['nspbr6']['srcportop'] = srcportop

    if srcportval:
        payload['nspbr6']['srcportval'] = srcportval

    if destipv6:
        payload['nspbr6']['destipv6'] = destipv6

    if destipop:
        payload['nspbr6']['destipop'] = destipop

    if destipv6val:
        payload['nspbr6']['destipv6val'] = destipv6val

    if destport:
        payload['nspbr6']['destport'] = destport

    if destportop:
        payload['nspbr6']['destportop'] = destportop

    if destportval:
        payload['nspbr6']['destportval'] = destportval

    if srcmac:
        payload['nspbr6']['srcmac'] = srcmac

    if srcmacmask:
        payload['nspbr6']['srcmacmask'] = srcmacmask

    if protocol:
        payload['nspbr6']['protocol'] = protocol

    if protocolnumber:
        payload['nspbr6']['protocolnumber'] = protocolnumber

    if vlan:
        payload['nspbr6']['vlan'] = vlan

    if vxlan:
        payload['nspbr6']['vxlan'] = vxlan

    if interface:
        payload['nspbr6']['Interface'] = interface

    if priority:
        payload['nspbr6']['priority'] = priority

    if state:
        payload['nspbr6']['state'] = state

    if msr:
        payload['nspbr6']['msr'] = msr

    if monitor:
        payload['nspbr6']['monitor'] = monitor

    if nexthop:
        payload['nspbr6']['nexthop'] = nexthop

    if nexthopval:
        payload['nspbr6']['nexthopval'] = nexthopval

    if iptunnel:
        payload['nspbr6']['iptunnel'] = iptunnel

    if vxlanvlanmap:
        payload['nspbr6']['vxlanvlanmap'] = vxlanvlanmap

    if nexthopvlan:
        payload['nspbr6']['nexthopvlan'] = nexthopvlan

    if ownergroup:
        payload['nspbr6']['ownergroup'] = ownergroup

    if detail:
        payload['nspbr6']['detail'] = detail

    execution = __proxy__['citrixns.put']('config/nspbr6', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsratecontrol(tcpthreshold=None, udpthreshold=None, icmpthreshold=None, tcprstthreshold=None, save=False):
    '''
    Update the running configuration for the nsratecontrol config key.

    tcpthreshold(int): Number of SYNs permitted per 10 milliseconds.

    udpthreshold(int): Number of UDP packets permitted per 10 milliseconds.

    icmpthreshold(int): Number of ICMP packets permitted per 10 milliseconds. Default value: 100

    tcprstthreshold(int): The number of TCP RST packets permitted per 10 milli second. zero means rate control is disabled
        and 0xffffffff means every thing is rate controlled. Default value: 100

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsratecontrol <args>

    '''

    result = {}

    payload = {'nsratecontrol': {}}

    if tcpthreshold:
        payload['nsratecontrol']['tcpthreshold'] = tcpthreshold

    if udpthreshold:
        payload['nsratecontrol']['udpthreshold'] = udpthreshold

    if icmpthreshold:
        payload['nsratecontrol']['icmpthreshold'] = icmpthreshold

    if tcprstthreshold:
        payload['nsratecontrol']['tcprstthreshold'] = tcprstthreshold

    execution = __proxy__['citrixns.put']('config/nsratecontrol', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsrpcnode(ipaddress=None, password=None, srcip=None, secure=None, save=False):
    '''
    Update the running configuration for the nsrpcnode config key.

    ipaddress(str): IP address of the node. This has to be in the same subnet as the NSIP address. Minimum length = 1

    password(str): Password to be used in authentication with the peer system node. Minimum length = 1

    srcip(str): Source IP address to be used to communicate with the peer system node. The default value is 0, which means
        that the appliance uses the NSIP address as the source IP address.

    secure(str): State of the channel when talking to the node. Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsrpcnode <args>

    '''

    result = {}

    payload = {'nsrpcnode': {}}

    if ipaddress:
        payload['nsrpcnode']['ipaddress'] = ipaddress

    if password:
        payload['nsrpcnode']['password'] = password

    if srcip:
        payload['nsrpcnode']['srcip'] = srcip

    if secure:
        payload['nsrpcnode']['secure'] = secure

    execution = __proxy__['citrixns.put']('config/nsrpcnode', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsservicefunction(servicefunctionname=None, ingressvlan=None, save=False):
    '''
    Update the running configuration for the nsservicefunction config key.

    servicefunctionname(str): Name of the service function to be created. Leading character must be a number or letter. Other
        characters allowed, after the first character, are @ _ - . (period) : (colon) # and space ( ). Minimum length =
        1

    ingressvlan(int): VLAN ID on which the traffic from service function reaches Netscaler. Minimum value = 1 Maximum value =
        4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsservicefunction <args>

    '''

    result = {}

    payload = {'nsservicefunction': {}}

    if servicefunctionname:
        payload['nsservicefunction']['servicefunctionname'] = servicefunctionname

    if ingressvlan:
        payload['nsservicefunction']['ingressvlan'] = ingressvlan

    execution = __proxy__['citrixns.put']('config/nsservicefunction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsspparams(basethreshold=None, throttle=None, save=False):
    '''
    Update the running configuration for the nsspparams config key.

    basethreshold(int): Maximum number of server connections that can be opened before surge protection is activated. Default
        value: 200 Minimum value = 0 Maximum value = 32767

    throttle(str): Rate at which the system opens connections to the server. Default value: Normal Possible values =
        Aggressive, Normal, Relaxed

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsspparams <args>

    '''

    result = {}

    payload = {'nsspparams': {}}

    if basethreshold:
        payload['nsspparams']['basethreshold'] = basethreshold

    if throttle:
        payload['nsspparams']['throttle'] = throttle

    execution = __proxy__['citrixns.put']('config/nsspparams', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nstcpbufparam(size=None, memlimit=None, save=False):
    '''
    Update the running configuration for the nstcpbufparam config key.

    size(int): TCP buffering size per connection, in kilobytes. Default value: 64 Minimum value = 4 Maximum value = 20480

    memlimit(int): Maximum memory, in megabytes, that can be used for buffering. Default value: 64

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nstcpbufparam <args>

    '''

    result = {}

    payload = {'nstcpbufparam': {}}

    if size:
        payload['nstcpbufparam']['size'] = size

    if memlimit:
        payload['nstcpbufparam']['memlimit'] = memlimit

    execution = __proxy__['citrixns.put']('config/nstcpbufparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nstcpparam(ws=None, wsval=None, sack=None, learnvsvrmss=None, maxburst=None, initialcwnd=None,
                      recvbuffsize=None, delayedack=None, downstaterst=None, nagle=None, limitedpersist=None,
                      oooqsize=None, ackonpush=None, maxpktpermss=None, pktperretx=None, minrto=None, slowstartincr=None,
                      maxdynserverprobes=None, synholdfastgiveup=None, maxsynholdperprobe=None, maxsynhold=None,
                      msslearninterval=None, msslearndelay=None, maxtimewaitconn=None, kaprobeupdatelastactivity=None,
                      maxsynackretx=None, synattackdetection=None, connflushifnomem=None, connflushthres=None,
                      mptcpconcloseonpassivesf=None, mptcpchecksum=None, mptcpsftimeout=None, mptcpsfreplacetimeout=None,
                      mptcpmaxsf=None, mptcpmaxpendingsf=None, mptcppendingjointhreshold=None, mptcprtostoswitchsf=None,
                      mptcpusebackupondss=None, tcpmaxretries=None, mptcpimmediatesfcloseonfin=None,
                      mptcpclosemptcpsessiononlastsfclose=None, tcpfastopencookietimeout=None, autosyncookietimeout=None,
                      save=False):
    '''
    Update the running configuration for the nstcpparam config key.

    ws(str): Enable or disable window scaling. Default value: DISABLED Possible values = ENABLED, DISABLED

    wsval(int): Factor used to calculate the new window size. This argument is needed only when the window scaling is
        enabled. Default value: 4 Minimum value = 0 Maximum value = 14

    sack(str): Enable or disable Selective ACKnowledgement (SACK). Default value: DISABLED Possible values = ENABLED,
        DISABLED

    learnvsvrmss(str): Enable or disable maximum segment size (MSS) learning for virtual servers. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    maxburst(int): Maximum number of TCP segments allowed in a burst. Default value: 6 Minimum value = 1 Maximum value = 255

    initialcwnd(int): Initial maximum upper limit on the number of TCP packets that can be outstanding on the TCP link to the
        server. Default value: 4 Minimum value = 1 Maximum value = 44

    recvbuffsize(int): TCP Receive buffer size. Default value: 8190 Minimum value = 8190 Maximum value = 20971520

    delayedack(int): Timeout for TCP delayed ACK, in milliseconds. Default value: 100 Minimum value = 10 Maximum value = 300

    downstaterst(str): Flag to switch on RST on down services. Default value: DISABLED Possible values = ENABLED, DISABLED

    nagle(str): Enable or disable the Nagle algorithm on TCP connections. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    limitedpersist(str): Limit the number of persist (zero window) probes. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    oooqsize(int): Maximum size of out-of-order packets queue. A value of 0 means no limit. Default value: 64 Minimum value =
        0 Maximum value = 65535

    ackonpush(str): Send immediate positive acknowledgement (ACK) on receipt of TCP packets with PUSH flag. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    maxpktpermss(int): Maximum number of TCP packets allowed per maximum segment size (MSS). Minimum value = 0 Maximum value
        = 1460

    pktperretx(int): Maximum limit on the number of packets that should be retransmitted on receiving a partial ACK. Default
        value: 1 Minimum value = 1 Maximum value = 100

    minrto(int): Minimum retransmission timeout, in milliseconds, specified in 10-millisecond increments (value must yield a
        whole number if divided by 10). Default value: 1000 Minimum value = 10 Maximum value = 64000

    slowstartincr(int): Multiplier that determines the rate at which slow start increases the size of the TCP transmission
        window after each acknowledgement of successful transmission. Default value: 2 Minimum value = 1 Maximum value =
        100

    maxdynserverprobes(int): Maximum number of probes that NetScaler can send out in 10 milliseconds, to dynamically learn a
        service. NetScaler probes for the existence of the origin in case of wildcard virtual server or services. Default
        value: 7 Minimum value = 1 Maximum value = 65535

    synholdfastgiveup(int): Maximum threshold. After crossing this threshold number of outstanding probes for origin, the
        NetScaler reduces the number of connection retries for probe connections. Default value: 1024 Minimum value = 256
        Maximum value = 65535

    maxsynholdperprobe(int): Limit the number of client connections (SYN) waiting for status of single probe. Any new SYN
        packets will be dropped. Default value: 128 Minimum value = 1 Maximum value = 255

    maxsynhold(int): Limit the number of client connections (SYN) waiting for status of probe system wide. Any new SYN
        packets will be dropped. Default value: 16384 Minimum value = 256 Maximum value = 65535

    msslearninterval(int): Duration, in seconds, to sample the Maximum Segment Size (MSS) of the services. The NetScaler
        appliance determines the best MSS to set for the virtual server based on this sampling. The argument to enable
        maximum segment size (MSS) for virtual servers must be enabled. Default value: 180 Minimum value = 1 Maximum
        value = 1048576

    msslearndelay(int): Frequency, in seconds, at which the virtual servers learn the Maximum segment size (MSS) from the
        services. The argument to enable maximum segment size (MSS) for virtual servers must be enabled. Default value:
        3600 Minimum value = 1 Maximum value = 1048576

    maxtimewaitconn(int): Maximum number of connections to hold in the TCP TIME_WAIT state on a packet engine. New
        connections entering TIME_WAIT state are proactively cleaned up. Default value: 7000 Minimum value = 1

    kaprobeupdatelastactivity(str): Update last activity for KA probes. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    maxsynackretx(int): When syncookie is disabled in the TCP profile that is bound to the virtual server or service, and the
        number of TCP SYN+ACK retransmission by NetScaler for that virtual server or service crosses this threshold, the
        NetScaler appliance responds by using the TCP SYN-Cookie mechanism. Default value: 100 Minimum value = 100
        Maximum value = 1048576

    synattackdetection(str): Detect TCP SYN packet flood and send an SNMP trap. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    connflushifnomem(str): Flush an existing connection if no memory can be obtained for new connection.
        HALF_CLOSED_AND_IDLE: Flush a connection that is closed by us but not by peer, or failing that, a connection that
        is past configured idle time. New connection fails if no such connection can be found.  FIFO: If no half-closed
        or idle connection can be found, flush the oldest non-management connection, even if it is active. New connection
        fails if the oldest few connections are management connections.  Note: If you enable this setting, you should
        also consider lowering the zombie timeout and half-close timeout, while setting the NetScaler timeout.  See Also:
        connFlushThres argument below.  Default value: NONE Possible values = NONE, HALFCLOSED_AND_IDLE, FIFO

    connflushthres(int): Flush an existing connection (as configured through -connFlushIfNoMem FIFO) if the system has more
        than specified number of connections, and a new connection is to be established. Note: This value may be rounded
        down to be a whole multiple of the number of packet engines running. Minimum value = 1

    mptcpconcloseonpassivesf(str): Accept DATA_FIN/FAST_CLOSE on passive subflow. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    mptcpchecksum(str): Use MPTCP DSS checksum. Default value: ENABLED Possible values = ENABLED, DISABLED

    mptcpsftimeout(int): The timeout value in seconds for idle mptcp subflows. If this timeout is not set, idle subflows are
        cleared after cltTimeout of vserver. Default value: 0 Minimum value = 0 Maximum value = 31536000

    mptcpsfreplacetimeout(int): The minimum idle time value in seconds for idle mptcp subflows after which the sublow is
        replaced by new incoming subflow if maximum subflow limit is reached. The priority for replacement is given to
        those subflow without any transaction. Default value: 10 Minimum value = 0 Maximum value = 31536000

    mptcpmaxsf(int): Maximum number of subflow connections supported in established state per mptcp connection. Default
        value: 4 Minimum value = 2 Maximum value = 6

    mptcpmaxpendingsf(int): Maximum number of subflow connections supported in pending join state per mptcp connection.
        Default value: 4 Minimum value = 0 Maximum value = 4

    mptcppendingjointhreshold(int): Maximum system level pending join connections allowed. Default value: 0 Minimum value = 0
        Maximum value = 4294967294

    mptcprtostoswitchsf(int): Number of RTOs at subflow level, after which MPCTP should start using other subflow. Default
        value: 2 Minimum value = 1 Maximum value = 6

    mptcpusebackupondss(str): When enabled, if NS receives a DSS on a backup subflow, NS will start using that subflow to
        send data. And if disabled, NS will continue to transmit on current chosen subflow. In case there is some error
        on a subflow (like RTOs/RST etc.) then NS can choose a backup subflow irrespective of this tunable. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    tcpmaxretries(int): Number of RTOs after which a connection should be freed. Default value: 7 Minimum value = 1 Maximum
        value = 7

    mptcpimmediatesfcloseonfin(str): Allow subflows to close immediately on FIN before the DATA_FIN exchange is completed at
        mptcp level. Default value: DISABLED Possible values = ENABLED, DISABLED

    mptcpclosemptcpsessiononlastsfclose(str): Allow to send DATA FIN or FAST CLOSE on mptcp connection while sending FIN or
        RST on the last subflow. Default value: DISABLED Possible values = ENABLED, DISABLED

    tcpfastopencookietimeout(int): Timeout in seconds after which a new TFO Key is computed for generating TFO Cookie. If
        zero, the same key is used always. If timeout is less than 120seconds, NS defaults to 120seconds timeout. Default
        value: 0 Minimum value = 0 Maximum value = 31536000

    autosyncookietimeout(int): Timeout for the server to function in syncookie mode after the synattack. This is valid if TCP
        syncookie is disabled on the profile and server acts in non syncookie mode by default. Default value: 30 Minimum
        value = 7 Maximum value = 65535

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nstcpparam <args>

    '''

    result = {}

    payload = {'nstcpparam': {}}

    if ws:
        payload['nstcpparam']['ws'] = ws

    if wsval:
        payload['nstcpparam']['wsval'] = wsval

    if sack:
        payload['nstcpparam']['sack'] = sack

    if learnvsvrmss:
        payload['nstcpparam']['learnvsvrmss'] = learnvsvrmss

    if maxburst:
        payload['nstcpparam']['maxburst'] = maxburst

    if initialcwnd:
        payload['nstcpparam']['initialcwnd'] = initialcwnd

    if recvbuffsize:
        payload['nstcpparam']['recvbuffsize'] = recvbuffsize

    if delayedack:
        payload['nstcpparam']['delayedack'] = delayedack

    if downstaterst:
        payload['nstcpparam']['downstaterst'] = downstaterst

    if nagle:
        payload['nstcpparam']['nagle'] = nagle

    if limitedpersist:
        payload['nstcpparam']['limitedpersist'] = limitedpersist

    if oooqsize:
        payload['nstcpparam']['oooqsize'] = oooqsize

    if ackonpush:
        payload['nstcpparam']['ackonpush'] = ackonpush

    if maxpktpermss:
        payload['nstcpparam']['maxpktpermss'] = maxpktpermss

    if pktperretx:
        payload['nstcpparam']['pktperretx'] = pktperretx

    if minrto:
        payload['nstcpparam']['minrto'] = minrto

    if slowstartincr:
        payload['nstcpparam']['slowstartincr'] = slowstartincr

    if maxdynserverprobes:
        payload['nstcpparam']['maxdynserverprobes'] = maxdynserverprobes

    if synholdfastgiveup:
        payload['nstcpparam']['synholdfastgiveup'] = synholdfastgiveup

    if maxsynholdperprobe:
        payload['nstcpparam']['maxsynholdperprobe'] = maxsynholdperprobe

    if maxsynhold:
        payload['nstcpparam']['maxsynhold'] = maxsynhold

    if msslearninterval:
        payload['nstcpparam']['msslearninterval'] = msslearninterval

    if msslearndelay:
        payload['nstcpparam']['msslearndelay'] = msslearndelay

    if maxtimewaitconn:
        payload['nstcpparam']['maxtimewaitconn'] = maxtimewaitconn

    if kaprobeupdatelastactivity:
        payload['nstcpparam']['kaprobeupdatelastactivity'] = kaprobeupdatelastactivity

    if maxsynackretx:
        payload['nstcpparam']['maxsynackretx'] = maxsynackretx

    if synattackdetection:
        payload['nstcpparam']['synattackdetection'] = synattackdetection

    if connflushifnomem:
        payload['nstcpparam']['connflushifnomem'] = connflushifnomem

    if connflushthres:
        payload['nstcpparam']['connflushthres'] = connflushthres

    if mptcpconcloseonpassivesf:
        payload['nstcpparam']['mptcpconcloseonpassivesf'] = mptcpconcloseonpassivesf

    if mptcpchecksum:
        payload['nstcpparam']['mptcpchecksum'] = mptcpchecksum

    if mptcpsftimeout:
        payload['nstcpparam']['mptcpsftimeout'] = mptcpsftimeout

    if mptcpsfreplacetimeout:
        payload['nstcpparam']['mptcpsfreplacetimeout'] = mptcpsfreplacetimeout

    if mptcpmaxsf:
        payload['nstcpparam']['mptcpmaxsf'] = mptcpmaxsf

    if mptcpmaxpendingsf:
        payload['nstcpparam']['mptcpmaxpendingsf'] = mptcpmaxpendingsf

    if mptcppendingjointhreshold:
        payload['nstcpparam']['mptcppendingjointhreshold'] = mptcppendingjointhreshold

    if mptcprtostoswitchsf:
        payload['nstcpparam']['mptcprtostoswitchsf'] = mptcprtostoswitchsf

    if mptcpusebackupondss:
        payload['nstcpparam']['mptcpusebackupondss'] = mptcpusebackupondss

    if tcpmaxretries:
        payload['nstcpparam']['tcpmaxretries'] = tcpmaxretries

    if mptcpimmediatesfcloseonfin:
        payload['nstcpparam']['mptcpimmediatesfcloseonfin'] = mptcpimmediatesfcloseonfin

    if mptcpclosemptcpsessiononlastsfclose:
        payload['nstcpparam']['mptcpclosemptcpsessiononlastsfclose'] = mptcpclosemptcpsessiononlastsfclose

    if tcpfastopencookietimeout:
        payload['nstcpparam']['tcpfastopencookietimeout'] = tcpfastopencookietimeout

    if autosyncookietimeout:
        payload['nstcpparam']['autosyncookietimeout'] = autosyncookietimeout

    execution = __proxy__['citrixns.put']('config/nstcpparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nstcpprofile(name=None, ws=None, sack=None, wsval=None, nagle=None, ackonpush=None, mss=None, maxburst=None,
                        initialcwnd=None, delayedack=None, oooqsize=None, maxpktpermss=None, pktperretx=None,
                        minrto=None, slowstartincr=None, buffersize=None, syncookie=None, kaprobeupdatelastactivity=None,
                        flavor=None, dynamicreceivebuffering=None, ka=None, kaconnidletime=None, kamaxprobes=None,
                        kaprobeinterval=None, sendbuffsize=None, mptcp=None, establishclientconn=None,
                        tcpsegoffload=None, rstwindowattenuate=None, rstmaxack=None, spoofsyndrop=None, ecn=None,
                        mptcpdropdataonpreestsf=None, mptcpfastopen=None, mptcpsessiontimeout=None, timestamp=None,
                        dsack=None, ackaggregation=None, frto=None, maxcwnd=None, fack=None, tcpmode=None,
                        tcpfastopen=None, hystart=None, dupackthresh=None, burstratecontrol=None, tcprate=None,
                        rateqmax=None, drophalfclosedconnontimeout=None, dropestconnontimeout=None, save=False):
    '''
    Update the running configuration for the nstcpprofile config key.

    name(str): Name for a TCP profile. Must begin with a letter, number, or the underscore \\(_\\) character. Other
        characters allowed, after the first character, are the hyphen \\(-\\), period \\(.\\), hash \\(\\#\\), space \\(
        \\), at \\(@\\), colon \\(:\\), and equal \\(=\\) characters. The name of a TCP profile cannot be changed after
        it is created.  CLI Users: If the name includes one or more spaces, enclose the name in double or single
        quotation marks \\(for example, "my tcp profile" or my tcp profile\\). Minimum length = 1 Maximum length = 127

    ws(str): Enable or disable window scaling. Default value: DISABLED Possible values = ENABLED, DISABLED

    sack(str): Enable or disable Selective ACKnowledgement (SACK). Default value: DISABLED Possible values = ENABLED,
        DISABLED

    wsval(int): Factor used to calculate the new window size. This argument is needed only when window scaling is enabled.
        Default value: 4 Minimum value = 0 Maximum value = 14

    nagle(str): Enable or disable the Nagle algorithm on TCP connections. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    ackonpush(str): Send immediate positive acknowledgement (ACK) on receipt of TCP packets with PUSH flag. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    mss(int): Maximum number of octets to allow in a TCP data segment. Minimum value = 0 Maximum value = 9176

    maxburst(int): Maximum number of TCP segments allowed in a burst. Default value: 6 Minimum value = 1 Maximum value = 255

    initialcwnd(int): Initial maximum upper limit on the number of TCP packets that can be outstanding on the TCP link to the
        server. Default value: 4 Minimum value = 1 Maximum value = 44

    delayedack(int): Timeout for TCP delayed ACK, in milliseconds. Default value: 100 Minimum value = 10 Maximum value = 300

    oooqsize(int): Maximum size of out-of-order packets queue. A value of 0 means no limit. Default value: 64 Minimum value =
        0 Maximum value = 65535

    maxpktpermss(int): Maximum number of TCP packets allowed per maximum segment size (MSS). Minimum value = 0 Maximum value
        = 1460

    pktperretx(int): Maximum limit on the number of packets that should be retransmitted on receiving a partial ACK. Default
        value: 1 Minimum value = 1 Maximum value = 512

    minrto(int): Minimum retransmission timeout, in milliseconds, specified in 10-millisecond increments (value must yield a
        whole number if divided by 10). Default value: 1000 Minimum value = 10 Maximum value = 64000

    slowstartincr(int): Multiplier that determines the rate at which slow start increases the size of the TCP transmission
        window after each acknowledgement of successful transmission. Default value: 2 Minimum value = 1 Maximum value =
        100

    buffersize(int): TCP buffering size, in bytes. Default value: 8190 Minimum value = 8190 Maximum value = 20971520

    syncookie(str): Enable or disable the SYNCOOKIE mechanism for TCP handshake with clients. Disabling SYNCOOKIE prevents
        SYN attack protection on the NetScaler appliance. Default value: ENABLED Possible values = ENABLED, DISABLED

    kaprobeupdatelastactivity(str): Update last activity for the connection after receiving keep-alive (KA) probes. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    flavor(str): Set TCP congestion control algorithm. Default value: Default Possible values = Default, Westwood, BIC,
        CUBIC, Nile

    dynamicreceivebuffering(str): Enable or disable dynamic receive buffering. When enabled, allows the receive buffer to be
        adjusted dynamically based on memory and network conditions. Note: The buffer size argument must be set for
        dynamic adjustments to take place. Default value: DISABLED Possible values = ENABLED, DISABLED

    ka(str): Send periodic TCP keep-alive (KA) probes to check if peer is still up. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    kaconnidletime(int): Duration, in seconds, for the connection to be idle, before sending a keep-alive (KA) probe. Minimum
        value = 1 Maximum value = 4095

    kamaxprobes(int): Number of keep-alive (KA) probes to be sent when not acknowledged, before assuming the peer to be down.
        Minimum value = 1 Maximum value = 254

    kaprobeinterval(int): Time interval, in seconds, before the next keep-alive (KA) probe, if the peer does not respond.
        Minimum value = 1 Maximum value = 4095

    sendbuffsize(int): TCP Send Buffer Size. Default value: 8190 Minimum value = 8190 Maximum value = 20971520

    mptcp(str): Enable or disable Multipath TCP. Default value: DISABLED Possible values = ENABLED, DISABLED

    establishclientconn(str): Establishing Client Client connection on First data/ Final-ACK / Automatic. Default value:
        AUTOMATIC Possible values = AUTOMATIC, CONN_ESTABLISHED, ON_FIRST_DATA

    tcpsegoffload(str): Offload TCP segmentation to the NIC. If set to AUTOMATIC, TCP segmentation will be offloaded to the
        NIC, if the NIC supports it. Default value: AUTOMATIC Possible values = AUTOMATIC, DISABLED

    rstwindowattenuate(str): Enable or disable RST window attenuation to protect against spoofing. When enabled, will reply
        with corrective ACK when a sequence number is invalid. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    rstmaxack(str): Enable or disable acceptance of RST that is out of window yet echoes highest ACK sequence number. Useful
        only in proxy mode. Default value: DISABLED Possible values = ENABLED, DISABLED

    spoofsyndrop(str): Enable or disable drop of invalid SYN packets to protect against spoofing. When disabled, established
        connections will be reset when a SYN packet is received. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    ecn(str): Enable or disable TCP Explicit Congestion Notification. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    mptcpdropdataonpreestsf(str): Enable or disable silently dropping the data on Pre-Established subflow. When enabled, DSS
        data packets are dropped silently instead of dropping the connection when data is received on pre established
        subflow. Default value: DISABLED Possible values = ENABLED, DISABLED

    mptcpfastopen(str): Enable or disable Multipath TCP fastopen. When enabled, DSS data packets are accepted before
        receiving the third ack of SYN handshake. Default value: DISABLED Possible values = ENABLED, DISABLED

    mptcpsessiontimeout(int): MPTCP session timeout in seconds. If this value is not set, idle MPTCP sessions are flushed
        after vservers client idle timeout. Default value: 0 Minimum value = 0 Maximum value = 86400

    timestamp(str): Enable or Disable TCP Timestamp option (RFC 1323). Default value: DISABLED Possible values = ENABLED,
        DISABLED

    dsack(str): Enable or disable DSACK. Default value: ENABLED Possible values = ENABLED, DISABLED

    ackaggregation(str): Enable or disable ACK Aggregation. Default value: DISABLED Possible values = ENABLED, DISABLED

    frto(str): Enable or disable FRTO (Forward RTO-Recovery). Default value: DISABLED Possible values = ENABLED, DISABLED

    maxcwnd(int): TCP Maximum Congestion Window. Default value: 524288 Minimum value = 8190 Maximum value = 20971520

    fack(str): Enable or disable FACK (Forward ACK). Default value: DISABLED Possible values = ENABLED, DISABLED

    tcpmode(str): TCP Optimization modes TRANSPARENT / ENDPOINT. Default value: TRANSPARENT Possible values = TRANSPARENT,
        ENDPOINT

    tcpfastopen(str): Enable or disable TCP Fastopen. When enabled, NS can receive or send Data in SYN or SYN-ACK packets.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    hystart(str): Enable or disable CUBIC Hystart. Default value: DISABLED Possible values = ENABLED, DISABLED

    dupackthresh(int): TCP dupack threshold. Default value: 3 Minimum value = 1 Maximum value = 15

    burstratecontrol(str): TCP Burst Rate Control DISABLED/FIXED/DYNAMIC. FIXED requires a TCP rate to be set. Default value:
        DISABLED Possible values = DISABLED, FIXED, DYNAMIC

    tcprate(int): TCP connection payload send rate in Kb/s. Default value: 0 Minimum value = 0 Maximum value = 10000000

    rateqmax(int): Maximum connection queue size in bytes, when BurstRateControl is used. Default value: 0 Minimum value = 0
        Maximum value = 1000000000

    drophalfclosedconnontimeout(str): Silently drop tcp half closed connections on idle timeout. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    dropestconnontimeout(str): Silently drop tcp established connections on idle timeout. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nstcpprofile <args>

    '''

    result = {}

    payload = {'nstcpprofile': {}}

    if name:
        payload['nstcpprofile']['name'] = name

    if ws:
        payload['nstcpprofile']['ws'] = ws

    if sack:
        payload['nstcpprofile']['sack'] = sack

    if wsval:
        payload['nstcpprofile']['wsval'] = wsval

    if nagle:
        payload['nstcpprofile']['nagle'] = nagle

    if ackonpush:
        payload['nstcpprofile']['ackonpush'] = ackonpush

    if mss:
        payload['nstcpprofile']['mss'] = mss

    if maxburst:
        payload['nstcpprofile']['maxburst'] = maxburst

    if initialcwnd:
        payload['nstcpprofile']['initialcwnd'] = initialcwnd

    if delayedack:
        payload['nstcpprofile']['delayedack'] = delayedack

    if oooqsize:
        payload['nstcpprofile']['oooqsize'] = oooqsize

    if maxpktpermss:
        payload['nstcpprofile']['maxpktpermss'] = maxpktpermss

    if pktperretx:
        payload['nstcpprofile']['pktperretx'] = pktperretx

    if minrto:
        payload['nstcpprofile']['minrto'] = minrto

    if slowstartincr:
        payload['nstcpprofile']['slowstartincr'] = slowstartincr

    if buffersize:
        payload['nstcpprofile']['buffersize'] = buffersize

    if syncookie:
        payload['nstcpprofile']['syncookie'] = syncookie

    if kaprobeupdatelastactivity:
        payload['nstcpprofile']['kaprobeupdatelastactivity'] = kaprobeupdatelastactivity

    if flavor:
        payload['nstcpprofile']['flavor'] = flavor

    if dynamicreceivebuffering:
        payload['nstcpprofile']['dynamicreceivebuffering'] = dynamicreceivebuffering

    if ka:
        payload['nstcpprofile']['ka'] = ka

    if kaconnidletime:
        payload['nstcpprofile']['kaconnidletime'] = kaconnidletime

    if kamaxprobes:
        payload['nstcpprofile']['kamaxprobes'] = kamaxprobes

    if kaprobeinterval:
        payload['nstcpprofile']['kaprobeinterval'] = kaprobeinterval

    if sendbuffsize:
        payload['nstcpprofile']['sendbuffsize'] = sendbuffsize

    if mptcp:
        payload['nstcpprofile']['mptcp'] = mptcp

    if establishclientconn:
        payload['nstcpprofile']['establishclientconn'] = establishclientconn

    if tcpsegoffload:
        payload['nstcpprofile']['tcpsegoffload'] = tcpsegoffload

    if rstwindowattenuate:
        payload['nstcpprofile']['rstwindowattenuate'] = rstwindowattenuate

    if rstmaxack:
        payload['nstcpprofile']['rstmaxack'] = rstmaxack

    if spoofsyndrop:
        payload['nstcpprofile']['spoofsyndrop'] = spoofsyndrop

    if ecn:
        payload['nstcpprofile']['ecn'] = ecn

    if mptcpdropdataonpreestsf:
        payload['nstcpprofile']['mptcpdropdataonpreestsf'] = mptcpdropdataonpreestsf

    if mptcpfastopen:
        payload['nstcpprofile']['mptcpfastopen'] = mptcpfastopen

    if mptcpsessiontimeout:
        payload['nstcpprofile']['mptcpsessiontimeout'] = mptcpsessiontimeout

    if timestamp:
        payload['nstcpprofile']['timestamp'] = timestamp

    if dsack:
        payload['nstcpprofile']['dsack'] = dsack

    if ackaggregation:
        payload['nstcpprofile']['ackaggregation'] = ackaggregation

    if frto:
        payload['nstcpprofile']['frto'] = frto

    if maxcwnd:
        payload['nstcpprofile']['maxcwnd'] = maxcwnd

    if fack:
        payload['nstcpprofile']['fack'] = fack

    if tcpmode:
        payload['nstcpprofile']['tcpmode'] = tcpmode

    if tcpfastopen:
        payload['nstcpprofile']['tcpfastopen'] = tcpfastopen

    if hystart:
        payload['nstcpprofile']['hystart'] = hystart

    if dupackthresh:
        payload['nstcpprofile']['dupackthresh'] = dupackthresh

    if burstratecontrol:
        payload['nstcpprofile']['burstratecontrol'] = burstratecontrol

    if tcprate:
        payload['nstcpprofile']['tcprate'] = tcprate

    if rateqmax:
        payload['nstcpprofile']['rateqmax'] = rateqmax

    if drophalfclosedconnontimeout:
        payload['nstcpprofile']['drophalfclosedconnontimeout'] = drophalfclosedconnontimeout

    if dropestconnontimeout:
        payload['nstcpprofile']['dropestconnontimeout'] = dropestconnontimeout

    execution = __proxy__['citrixns.put']('config/nstcpprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nstimeout(zombie=None, client=None, server=None, httpclient=None, httpserver=None, tcpclient=None,
                     tcpserver=None, anyclient=None, anyserver=None, anytcpclient=None, anytcpserver=None,
                     halfclose=None, nontcpzombie=None, reducedfintimeout=None, reducedrsttimeout=None,
                     newconnidletimeout=None, save=False):
    '''
    Update the running configuration for the nstimeout config key.

    zombie(int): Interval, in seconds, at which the NetScaler zombie cleanup process must run. This process cleans up
        inactive TCP connections. Default value: 120 Minimum value = 1 Maximum value = 600

    client(int): Client idle timeout (in seconds). If zero, the service-type default value is taken when service is created.
        Default value: 0 Minimum value = 0 Maximum value = 18000

    server(int): Server idle timeout (in seconds). If zero, the service-type default value is taken when service is created.
        Default value: 0 Minimum value = 0 Maximum value = 18000

    httpclient(int): Global idle timeout, in seconds, for client connections of HTTP service type. This value is over ridden
        by the client timeout that is configured on individual entities. Default value: 0 Minimum value = 0 Maximum value
        = 18000

    httpserver(int): Global idle timeout, in seconds, for server connections of HTTP service type. This value is over ridden
        by the server timeout that is configured on individual entities. Default value: 0 Minimum value = 0 Maximum value
        = 18000

    tcpclient(int): Global idle timeout, in seconds, for non-HTTP client connections of TCP service type. This value is over
        ridden by the client timeout that is configured on individual entities. Default value: 0 Minimum value = 0
        Maximum value = 18000

    tcpserver(int): Global idle timeout, in seconds, for non-HTTP server connections of TCP service type. This value is over
        ridden by the server timeout that is configured on entities. Default value: 0 Minimum value = 0 Maximum value =
        18000

    anyclient(int): Global idle timeout, in seconds, for non-TCP client connections. This value is over ridden by the client
        timeout that is configured on individual entities. Default value: 0 Minimum value = 0 Maximum value = 31536000

    anyserver(int): Global idle timeout, in seconds, for non TCP server connections. This value is over ridden by the server
        timeout that is configured on individual entities. Default value: 0 Minimum value = 0 Maximum value = 31536000

    anytcpclient(int): Global idle timeout, in seconds, for TCP client connections. This value takes precedence over entity
        level timeout settings (vserver/service). This is applicable only to transport protocol TCP. Default value: 0
        Minimum value = 0 Maximum value = 31536000

    anytcpserver(int): Global idle timeout, in seconds, for TCP server connections. This value takes precedence over entity
        level timeout settings ( vserver/service). This is applicable only to transport protocol TCP. Default value: 0
        Minimum value = 0 Maximum value = 31536000

    halfclose(int): Idle timeout, in seconds, for connections that are in TCP half-closed state. Default value: 10 Minimum
        value = 1 Maximum value = 600

    nontcpzombie(int): Interval at which the zombie clean-up process for non-TCP connections should run. Inactive IP NAT
        connections will be cleaned up. Default value: 60 Minimum value = 1 Maximum value = 600

    reducedfintimeout(int): Alternative idle timeout, in seconds, for closed TCP NATPCB connections. Default value: 30
        Minimum value = 1 Maximum value = 300

    reducedrsttimeout(int): Timer interval, in seconds, for abruptly terminated TCP NATPCB connections. Default value: 0
        Minimum value = 0 Maximum value = 300

    newconnidletimeout(int): Timer interval, in seconds, for new TCP NATPCB connections on which no data was received.
        Default value: 4 Minimum value = 1 Maximum value = 120

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nstimeout <args>

    '''

    result = {}

    payload = {'nstimeout': {}}

    if zombie:
        payload['nstimeout']['zombie'] = zombie

    if client:
        payload['nstimeout']['client'] = client

    if server:
        payload['nstimeout']['server'] = server

    if httpclient:
        payload['nstimeout']['httpclient'] = httpclient

    if httpserver:
        payload['nstimeout']['httpserver'] = httpserver

    if tcpclient:
        payload['nstimeout']['tcpclient'] = tcpclient

    if tcpserver:
        payload['nstimeout']['tcpserver'] = tcpserver

    if anyclient:
        payload['nstimeout']['anyclient'] = anyclient

    if anyserver:
        payload['nstimeout']['anyserver'] = anyserver

    if anytcpclient:
        payload['nstimeout']['anytcpclient'] = anytcpclient

    if anytcpserver:
        payload['nstimeout']['anytcpserver'] = anytcpserver

    if halfclose:
        payload['nstimeout']['halfclose'] = halfclose

    if nontcpzombie:
        payload['nstimeout']['nontcpzombie'] = nontcpzombie

    if reducedfintimeout:
        payload['nstimeout']['reducedfintimeout'] = reducedfintimeout

    if reducedrsttimeout:
        payload['nstimeout']['reducedrsttimeout'] = reducedrsttimeout

    if newconnidletimeout:
        payload['nstimeout']['newconnidletimeout'] = newconnidletimeout

    execution = __proxy__['citrixns.put']('config/nstimeout', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nstimer(name=None, interval=None, unit=None, comment=None, newname=None, save=False):
    '''
    Update the running configuration for the nstimer config key.

    name(str): Timer name. Minimum length = 1

    interval(int): The frequency at which the policies bound to this timer are invoked. The minimum value is 20 msec. The
        maximum value is 20940 in seconds and 349 in minutes. Default value: 5 Minimum value = 1 Maximum value =
        20940000

    unit(str): Timer interval unit. Default value: SEC Possible values = SEC, MIN

    comment(str): Comments associated with this timer.

    newname(str): The new name of the timer. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nstimer <args>

    '''

    result = {}

    payload = {'nstimer': {}}

    if name:
        payload['nstimer']['name'] = name

    if interval:
        payload['nstimer']['interval'] = interval

    if unit:
        payload['nstimer']['unit'] = unit

    if comment:
        payload['nstimer']['comment'] = comment

    if newname:
        payload['nstimer']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/nstimer', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsvariable(name=None, ns_type=None, scope=None, iffull=None, ifvaluetoobig=None, ifnovalue=None, init=None,
                      expires=None, comment=None, save=False):
    '''
    Update the running configuration for the nsvariable config key.

    name(str): Variable name. This follows the same syntax rules as other default syntax expression entity names:  It must
        begin with an alpha character (A-Z or a-z) or an underscore (_).  The rest of the characters must be alpha,
        numeric (0-9) or underscores.  It cannot be re or xp (reserved for regular and XPath expressions).  It cannot be
        a default syntax expression reserved word (e.g. SYS or HTTP).  It cannot be used for an existing default syntax
        expression object (HTTP callout, patset, dataset, stringmap, or named expression). Minimum length = 1

    ns_type(str): Specification of the variable type; one of the following:  ulong - singleton variable with an unsigned
        64-bit value.  text(value-max-size) - singleton variable with a text string value.
        map(text(key-max-size),ulong,max-entries) - map of text string keys to unsigned 64-bit values.
        map(text(key-max-size),text(value-max-size),max-entries) - map of text string keys to text string values. where
        value-max-size is a positive integer that is the maximum number of bytes in a text string value.  key-max-size is
        a positive integer that is the maximum number of bytes in a text string key.  max-entries is a positive integer
        that is the maximum number of entries in a map variable.  For a global singleton text variable, value-max-size
        ;lt;= 64000.  For a global map with ulong values, key-max-size ;lt;= 64000.  For a global map with text values,
        key-max-size + value-max-size ;lt;= 64000.  max-entries is a positive integer that is the maximum number of
        entries in a map variable. This has a theoretical maximum of 2^64-1, but in actual use will be much smaller,
        considering the memory available for use by the map. Example:  map(text(10),text(20),100) specifies a map of text
        string keys (max size 10 bytes) to text string values (max size 20 bytes), with 100 max entries. Minimum length =
        1

    scope(str): Scope of the variable:  global - (default) one set of values visible across all Packet Engines and, in a
        cluster, all nodes  transaction - one value for each request-response transaction (singleton variables only; no
        expiration). Default value: global Possible values = global, transaction

    iffull(str): Action to perform if an assignment to a map exceeds its configured max-entries:  lru - (default) reuse the
        least recently used entry in the map.  undef - force the assignment to return an undefined (Undef) result to the
        policy executing the assignment. Default value: lru Possible values = undef, lru

    ifvaluetoobig(str): Action to perform if an value is assigned to a text variable that exceeds its configured max-size, or
        if a key is used that exceeds its configured max-size:  truncate - (default) truncate the text string to the
        first max-size bytes and proceed.  undef - force the assignment or expression evaluation to return an undefined
        (Undef) result to the policy executing the assignment or expression. Default value: truncate Possible values =
        undef, truncate

    ifnovalue(str): Action to perform if on a variable reference in an expression if the variable is single-valued and
        uninitialized or if the variable is a map and there is no value for the specified key:  init - (default)
        initialize the single-value variable, or create a map entry for the key and the initial value, using the -init
        value or its default.  undef - force the expression evaluation to return an undefined (Undef) result to the
        policy executing the expression. Default value: init Possible values = undef, init

    init(str): Initialization value for values in this variable. Default: 0 for ulong, NULL for text.

    expires(int): Value expiration in seconds. If the value is not referenced within the expiration period it will be
        deleted. 0 (the default) means no expiration. Minimum value = 0 Maximum value = 31622400

    comment(str): Comments associated with this variable.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsvariable <args>

    '''

    result = {}

    payload = {'nsvariable': {}}

    if name:
        payload['nsvariable']['name'] = name

    if ns_type:
        payload['nsvariable']['type'] = ns_type

    if scope:
        payload['nsvariable']['scope'] = scope

    if iffull:
        payload['nsvariable']['iffull'] = iffull

    if ifvaluetoobig:
        payload['nsvariable']['ifvaluetoobig'] = ifvaluetoobig

    if ifnovalue:
        payload['nsvariable']['ifnovalue'] = ifnovalue

    if init:
        payload['nsvariable']['init'] = init

    if expires:
        payload['nsvariable']['expires'] = expires

    if comment:
        payload['nsvariable']['comment'] = comment

    execution = __proxy__['citrixns.put']('config/nsvariable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsvpxparam(cpuyield=None, save=False):
    '''
    Update the running configuration for the nsvpxparam config key.

    cpuyield(str): This setting applicable in virtual appliances, is to affect the cpu yield(relinquishing the cpu resources)
        in any hypervised environment.  * There are 3 options for the behavior: 1. YES - Allow the Virtual Appliance to
        yield its vCPUs periodically, if there is no data traffic. 2. NO - Virtual Appliance will not yield the vCPU. 3.
        DEFAULT - Restores the default behaviour, according to the license.  * Its behavior in different scenarios: 1. As
        this setting is node specific only, it will not be applicable in Cluster and HA scenarios. 2. This setting is a
        system wide implementation and not granular to vCPUs. 3. No effect on the management PE. Possible values =
        DEFAULT, YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsvpxparam <args>

    '''

    result = {}

    payload = {'nsvpxparam': {}}

    if cpuyield:
        payload['nsvpxparam']['cpuyield'] = cpuyield

    execution = __proxy__['citrixns.put']('config/nsvpxparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsweblogparam(buffersizemb=None, customreqhdrs=None, customrsphdrs=None, save=False):
    '''
    Update the running configuration for the nsweblogparam config key.

    buffersizemb(int): Buffer size, in MB, allocated for log transaction data on the system. The maximum value is limited to
        the memory available on the system. Default value: 16 Minimum value = 1 Maximum value = 4294967294LU

    customreqhdrs(list(str)): Name(s) of HTTP request headers whose values should be exported by the Web Logging feature.
        Minimum length = 1

    customrsphdrs(list(str)): Name(s) of HTTP response headers whose values should be exported by the Web Logging feature.
        Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsweblogparam <args>

    '''

    result = {}

    payload = {'nsweblogparam': {}}

    if buffersizemb:
        payload['nsweblogparam']['buffersizemb'] = buffersizemb

    if customreqhdrs:
        payload['nsweblogparam']['customreqhdrs'] = customreqhdrs

    if customrsphdrs:
        payload['nsweblogparam']['customrsphdrs'] = customrsphdrs

    execution = __proxy__['citrixns.put']('config/nsweblogparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_nsxmlnamespace(prefix=None, namespace=None, description=None, save=False):
    '''
    Update the running configuration for the nsxmlnamespace config key.

    prefix(str): XML prefix. Minimum length = 1

    namespace(str): Expanded namespace for which the XML prefix is provided. Minimum length = 1

    description(str): Description for the prefix. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ns.update_nsxmlnamespace <args>

    '''

    result = {}

    payload = {'nsxmlnamespace': {}}

    if prefix:
        payload['nsxmlnamespace']['prefix'] = prefix

    if namespace:
        payload['nsxmlnamespace']['Namespace'] = namespace

    if description:
        payload['nsxmlnamespace']['description'] = description

    execution = __proxy__['citrixns.put']('config/nsxmlnamespace', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
