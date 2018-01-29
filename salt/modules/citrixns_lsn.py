# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the lsn key.

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

__virtualname__ = 'lsn'


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

    return False, 'The lsn execution module can only be loaded for citrixns proxy minions.'


def add_lsnappsprofile(appsprofilename=None, transportprotocol=None, ippooling=None, mapping=None, filtering=None,
                       tcpproxy=None, td=None, l2info=None, save=False):
    '''
    Add a new lsnappsprofile to the running configuration.

    appsprofilename(str): Name for the LSN application profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after the LSN application profile is created. The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "lsn application profile1" or lsn application profile1).
        Minimum length = 1 Maximum length = 127

    transportprotocol(str): Name of the protocol for which the parameters of this LSN application profile applies. Possible
        values = TCP, UDP, ICMP

    ippooling(str): NAT IP address allocation options for sessions associated with the same subscriber.  Available options
        function as follows: * Paired - The NetScaler ADC allocates the same NAT IP address for all sessions associated
        with the same subscriber. When all the ports of a NAT IP address are used in LSN sessions (for same or multiple
        subscribers), the NetScaler ADC drops any new connection from the subscriber. * Random - The NetScaler ADC
        allocates random NAT IP addresses, from the pool, for different sessions associated with the same subscriber.
        This parameter is applicable to dynamic NAT allocation only. Default value: RANDOM Possible values = PAIRED,
        RANDOM

    mapping(str): Type of LSN mapping to apply to subsequent packets originating from the same subscriber IP address and
        port.  Consider an example of an LSN mapping that includes the mapping of the subscriber IP:port (X:x), NAT
        IP:port (N:n), and external host IP:port (Y:y).  Available options function as follows:   * ENDPOINT-INDEPENDENT
        - Reuse the LSN mapping for subsequent packets sent from the same subscriber IP address and port (X:x) to any
        external IP address and port.   * ADDRESS-DEPENDENT - Reuse the LSN mapping for subsequent packets sent from the
        same subscriber IP address and port (X:x) to the same external IP address (Y), regardless of the external port.
        * ADDRESS-PORT-DEPENDENT - Reuse the LSN mapping for subsequent packets sent from the same internal IP address
        and port (X:x) to the same external IP address and port (Y:y) while the mapping is still active. Default value:
        ADDRESS-PORT-DEPENDENT Possible values = ENDPOINT-INDEPENDENT, ADDRESS-DEPENDENT, ADDRESS-PORT-DEPENDENT

    filtering(str): Type of filter to apply to packets originating from external hosts.  Consider an example of an LSN
        mapping that includes the mapping of subscriber IP:port (X:x), NAT IP:port (N:n), and external host IP:port
        (Y:y).  Available options function as follows: * ENDPOINT INDEPENDENT - Filters out only packets not destined to
        the subscriber IP address and port X:x, regardless of the external host IP address and port source (Z:z). The
        NetScaler ADC forwards any packets destined to X:x. In other words, sending packets from the subscriber to any
        external IP address is sufficient to allow packets from any external hosts to the subscriber.  * ADDRESS
        DEPENDENT - Filters out packets not destined to subscriber IP address and port X:x. In addition, the ADC filters
        out packets from Y:y destined for the subscriber (X:x) if the client has not previously sent packets to Y:anyport
        (external port independent). In other words, receiving packets from a specific external host requires that the
        subscriber first send packets to that specific external hosts IP address.  * ADDRESS PORT DEPENDENT (the default)
        - Filters out packets not destined to subscriber IP address and port (X:x). In addition, the NetScaler ADC
        filters out packets from Y:y destined for the subscriber (X:x) if the subscriber has not previously sent packets
        to Y:y. In other words, receiving packets from a specific external host requires that the subscriber first send
        packets first to that external IP address and port. Default value: ADDRESS-PORT-DEPENDENT Possible values =
        ENDPOINT-INDEPENDENT, ADDRESS-DEPENDENT, ADDRESS-PORT-DEPENDENT

    tcpproxy(str): Enable TCP proxy, which enables the NetScaler appliance to optimize the TCP traffic by using Layer 4
        features. Default value: DISABLED Possible values = ENABLED, DISABLED

    td(int): ID of the traffic domain through which the NetScaler ADC sends the outbound traffic after performing LSN.   If
        you do not specify an ID, the ADC sends the outbound traffic through the default traffic domain, which has an ID
        of 0. Default value: 65535

    l2info(str): Enable l2info by creating natpcbs for LSN, which enables the NetScaler appliance to use L2CONN/MBF with LSN.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnappsprofile <args>

    '''

    result = {}

    payload = {'lsnappsprofile': {}}

    if appsprofilename:
        payload['lsnappsprofile']['appsprofilename'] = appsprofilename

    if transportprotocol:
        payload['lsnappsprofile']['transportprotocol'] = transportprotocol

    if ippooling:
        payload['lsnappsprofile']['ippooling'] = ippooling

    if mapping:
        payload['lsnappsprofile']['mapping'] = mapping

    if filtering:
        payload['lsnappsprofile']['filtering'] = filtering

    if tcpproxy:
        payload['lsnappsprofile']['tcpproxy'] = tcpproxy

    if td:
        payload['lsnappsprofile']['td'] = td

    if l2info:
        payload['lsnappsprofile']['l2info'] = l2info

    execution = __proxy__['citrixns.post']('config/lsnappsprofile', payload)

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


def add_lsnappsprofile_port_binding(appsprofilename=None, save=False):
    '''
    Add a new lsnappsprofile_port_binding to the running configuration.

    appsprofilename(str): Name for the LSN application profile. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnappsprofile_port_binding <args>

    '''

    result = {}

    payload = {'lsnappsprofile_port_binding': {}}

    if appsprofilename:
        payload['lsnappsprofile_port_binding']['appsprofilename'] = appsprofilename

    execution = __proxy__['citrixns.post']('config/lsnappsprofile_port_binding', payload)

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


def add_lsnclient(clientname=None, save=False):
    '''
    Add a new lsnclient to the running configuration.

    clientname(str): Name for the LSN client entity. Must begin with an ASCII alphanumeric or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the LSN client is created. The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "lsn client1" or lsn client1). . Minimum length = 1 Maximum length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnclient <args>

    '''

    result = {}

    payload = {'lsnclient': {}}

    if clientname:
        payload['lsnclient']['clientname'] = clientname

    execution = __proxy__['citrixns.post']('config/lsnclient', payload)

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


def add_lsnclient_network6_binding(network=None, clientname=None, save=False):
    '''
    Add a new lsnclient_network6_binding to the running configuration.

    network(str): IPv4 address(es) of the LSN subscriber(s) or subscriber network(s) on whose traffic you want the NetScaler
        ADC to perform Large Scale NAT. Minimum length = 1

    clientname(str): Name for the LSN client entity. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnclient_network6_binding <args>

    '''

    result = {}

    payload = {'lsnclient_network6_binding': {}}

    if network:
        payload['lsnclient_network6_binding']['network'] = network

    if clientname:
        payload['lsnclient_network6_binding']['clientname'] = clientname

    execution = __proxy__['citrixns.post']('config/lsnclient_network6_binding', payload)

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


def add_lsnclient_network_binding(network=None, clientname=None, save=False):
    '''
    Add a new lsnclient_network_binding to the running configuration.

    network(str): IPv4 address(es) of the LSN subscriber(s) or subscriber network(s) on whose traffic you want the NetScaler
        ADC to perform Large Scale NAT. Minimum length = 1

    clientname(str): Name for the LSN client entity. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnclient_network_binding <args>

    '''

    result = {}

    payload = {'lsnclient_network_binding': {}}

    if network:
        payload['lsnclient_network_binding']['network'] = network

    if clientname:
        payload['lsnclient_network_binding']['clientname'] = clientname

    execution = __proxy__['citrixns.post']('config/lsnclient_network_binding', payload)

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


def add_lsnclient_nsacl6_binding(clientname=None, save=False):
    '''
    Add a new lsnclient_nsacl6_binding to the running configuration.

    clientname(str): Name for the LSN client entity. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnclient_nsacl6_binding <args>

    '''

    result = {}

    payload = {'lsnclient_nsacl6_binding': {}}

    if clientname:
        payload['lsnclient_nsacl6_binding']['clientname'] = clientname

    execution = __proxy__['citrixns.post']('config/lsnclient_nsacl6_binding', payload)

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


def add_lsnclient_nsacl_binding(clientname=None, save=False):
    '''
    Add a new lsnclient_nsacl_binding to the running configuration.

    clientname(str): Name for the LSN client entity. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnclient_nsacl_binding <args>

    '''

    result = {}

    payload = {'lsnclient_nsacl_binding': {}}

    if clientname:
        payload['lsnclient_nsacl_binding']['clientname'] = clientname

    execution = __proxy__['citrixns.post']('config/lsnclient_nsacl_binding', payload)

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


def add_lsngroup(groupname=None, clientname=None, nattype=None, allocpolicy=None, portblocksize=None, logging=None,
                 sessionlogging=None, sessionsync=None, snmptraplimit=None, ftp=None, pptp=None, sipalg=None,
                 rtspalg=None, ip6profile=None, save=False):
    '''
    Add a new lsngroup to the running configuration.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the LSN group is created. The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "lsn group1" or lsn group1). Minimum length = 1 Maximum length = 127

    clientname(str): Name of the LSN client entity to be associated with the LSN group. You can associate only one LSN client
        entity with an LSN group.You cannot remove this association or replace with another LSN client entity once the
        LSN group is created.

    nattype(str): Type of NAT IP address and port allocation (from the bound LSN pools) for subscribers:  Available options
        function as follows:  * Deterministic - Allocate a NAT IP address and a block of ports to each subscriber (of the
        LSN client bound to the LSN group). The NetScaler ADC sequentially allocates NAT resources to these subscribers.
        The NetScaler ADC assigns the first block of ports (block size determined by the port block size parameter of the
        LSN group) on the beginning NAT IP address to the beginning subscriber IP address. The next range of ports is
        assigned to the next subscriber, and so on, until the NAT address does not have enough ports for the next
        subscriber. In this case, the first port block on the next NAT address is used for the subscriber, and so on.
        Because each subscriber now receives a deterministic NAT IP address and a block of ports, a subscriber can be
        identified without any need for logging. For a connection, a subscriber can be identified based only on the NAT
        IP address and port, and the destination IP address and port. The maximum number of LSN subscribers allowed,
        globally, is 1 million.   * Dynamic - Allocate a random NAT IP address and a port from the LSN NAT pool for a
        subscribers connection. If port block allocation is enabled (in LSN pool) and a port block size is specified (in
        the LSN group), the NetScaler ADC allocates a random NAT IP address and a block of ports for a subscriber when it
        initiates a connection for the first time. The ADC allocates this NAT IP address and a port (from the allocated
        block of ports) for different connections from this subscriber. If all the ports are allocated (for different
        subscribers connections) from the subscribers allocated port block, the ADC allocates a new random port block for
        the subscriber. Default value: DYNAMIC Possible values = DYNAMIC, DETERMINISTIC

    allocpolicy(str): NAT IP and PORT block allocation policy for Deterministic NAT. Supported Policies are, 1:
        PORTS(Default): Port blocks from single NATIP will be allocated to LSN subscribers sequentially. After all blocks
        are exhausted, port blocks from next NATIP will be allocated and so on. 2: IPADDRS: One port block from each
        NATIP will be allocated and once all the NATIPs are over second port block from each NATIP will be allocated and
        so on. To understand better if we assume port blocks of all NAT IPs as two dimensional array, PORTS policy
        follows "row major order" and IPADDRS policy follows "column major order" while allocating port blocks. Example:
        Client IPs: 2.2.2.1, 2.2.2.2 and 2.2.2.3 NAT IPs and PORT Blocks:  4.4.4.1:PB1, PB2, PB3,., PBn 4.4.4.2: PB1,
        PB2, PB3,., PBn PORTS Policy:  2.2.2.1 =;gt; 4.4.4.1:PB1 2.2.2.2 =;gt; 4.4.4.1:PB2 2.2.2.3 =;gt; 4.4.4.1:PB3
        IPADDRS Policy: 2.2.2.1 =;gt; 4.4.4.1:PB1 2.2.2.2 =;gt; 4.4.4.2:PB1 2.2.2.3 =;gt; 4.4.4.1:PB2. Default value:
        PORTS Possible values = PORTS, IPADDRS

    portblocksize(int): Size of the NAT port block to be allocated for each subscriber.  To set this parameter for Dynamic
        NAT, you must enable the port block allocation parameter in the bound LSN pool. For Deterministic NAT, the port
        block allocation parameter is always enabled, and you cannot disable it.  In Dynamic NAT, the NetScaler ADC
        allocates a random NAT port block, from the available NAT port pool of an NAT IP address, for each subscriber.
        For a subscriber, if all the ports are allocated from the subscribers allocated port block, the ADC allocates a
        new random port block for the subscriber.  The default port block size is 256 for Deterministic NAT, and 0 for
        Dynamic NAT. Default value: 0 Minimum value = 256 Maximum value = 65536

    logging(str): Log mapping entries and sessions created or deleted for this LSN group. The NetScaler ADC logs LSN sessions
        for this LSN group only when both logging and session logging parameters are enabled.  The ADC uses its existing
        syslog and audit log framework to log LSN information. You must enable global level LSN logging by enabling the
        LSN parameter in the related NSLOG action and SYLOG action entities. When the Logging parameter is enabled, the
        NetScaler ADC generates log messages related to LSN mappings and LSN sessions of this LSN group. The ADC then
        sends these log messages to servers associated with the NSLOG action and SYSLOG actions entities.   A log message
        for an LSN mapping entry consists of the following information: * NSIP address of the NetScaler ADC * Time stamp
        * Entry type (MAPPING or SESSION) * Whether the LSN mapping entry is created or deleted * Subscribers IP address,
        port, and traffic domain ID * NAT IP address and port * Protocol name * Destination IP address, port, and traffic
        domain ID might be present, depending on the following conditions: ** Destination IP address and port are not
        logged for Endpoint-Independent mapping ** Only Destination IP address (and not port) is logged for
        Address-Dependent mapping ** Destination IP address and port are logged for Address-Port-Dependent mapping.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    sessionlogging(str): Log sessions created or deleted for the LSN group. The NetScaler ADC logs LSN sessions for this LSN
        group only when both logging and session logging parameters are enabled.  A log message for an LSN session
        consists of the following information: * NSIP address of the NetScaler ADC * Time stamp * Entry type (MAPPING or
        SESSION) * Whether the LSN session is created or removed * Subscribers IP address, port, and traffic domain ID *
        NAT IP address and port * Protocol name * Destination IP address, port, and traffic domain ID. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    sessionsync(str): In a high availability (HA) deployment, synchronize information of all LSN sessions related to this LSN
        group with the secondary node. After a failover, established TCP connections and UDP packet flows are kept active
        and resumed on the secondary node (new primary).  For this setting to work, you must enable the global session
        synchronization parameter. Default value: ENABLED Possible values = ENABLED, DISABLED

    snmptraplimit(int): Maximum number of SNMP Trap messages that can be generated for the LSN group in one minute. Default
        value: 100 Minimum value = 0 Maximum value = 10000

    ftp(str): Enable Application Layer Gateway (ALG) for the FTP protocol. For some application-layer protocols, the IP
        addresses and protocol port numbers are usually communicated in the packets payload. When acting as an ALG, the
        NetScaler changes the packets payload to ensure that the protocol continues to work over LSN.   Note: The
        NetScaler ADC also includes ALG for ICMP and TFTP protocols. ALG for the ICMP protocol is enabled by default, and
        there is no provision to disable it. ALG for the TFTP protocol is disabled by default. ALG is enabled
        automatically for an LSN group when you bind a UDP LSN application profile, with endpoint-independent-mapping,
        endpoint-independent filtering, and destination port as 69 (well-known port for TFTP), to the LSN group. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    pptp(str): Enable the PPTP Application Layer Gateway. Default value: DISABLED Possible values = ENABLED, DISABLED

    sipalg(str): Enable the SIP ALG. Default value: DISABLED Possible values = ENABLED, DISABLED

    rtspalg(str): Enable the RTSP ALG. Default value: DISABLED Possible values = ENABLED, DISABLED

    ip6profile(str): Name of the LSN ip6 profile to associate with the specified LSN group. An ip6 profile can be associated
        with a group only during group creation.  By default, no LSN ip6 profile is associated with an LSN group during
        its creation. Only one ip6profile can be associated with a group. Minimum length = 1 Maximum length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsngroup <args>

    '''

    result = {}

    payload = {'lsngroup': {}}

    if groupname:
        payload['lsngroup']['groupname'] = groupname

    if clientname:
        payload['lsngroup']['clientname'] = clientname

    if nattype:
        payload['lsngroup']['nattype'] = nattype

    if allocpolicy:
        payload['lsngroup']['allocpolicy'] = allocpolicy

    if portblocksize:
        payload['lsngroup']['portblocksize'] = portblocksize

    if logging:
        payload['lsngroup']['logging'] = logging

    if sessionlogging:
        payload['lsngroup']['sessionlogging'] = sessionlogging

    if sessionsync:
        payload['lsngroup']['sessionsync'] = sessionsync

    if snmptraplimit:
        payload['lsngroup']['snmptraplimit'] = snmptraplimit

    if ftp:
        payload['lsngroup']['ftp'] = ftp

    if pptp:
        payload['lsngroup']['pptp'] = pptp

    if sipalg:
        payload['lsngroup']['sipalg'] = sipalg

    if rtspalg:
        payload['lsngroup']['rtspalg'] = rtspalg

    if ip6profile:
        payload['lsngroup']['ip6profile'] = ip6profile

    execution = __proxy__['citrixns.post']('config/lsngroup', payload)

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


def add_lsngroup_ipsecalgprofile_binding(ipsecalgprofile=None, groupname=None, save=False):
    '''
    Add a new lsngroup_ipsecalgprofile_binding to the running configuration.

    ipsecalgprofile(str): Name of the IPSec ALG profile to bind to the specified LSN group.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsngroup_ipsecalgprofile_binding <args>

    '''

    result = {}

    payload = {'lsngroup_ipsecalgprofile_binding': {}}

    if ipsecalgprofile:
        payload['lsngroup_ipsecalgprofile_binding']['ipsecalgprofile'] = ipsecalgprofile

    if groupname:
        payload['lsngroup_ipsecalgprofile_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/lsngroup_ipsecalgprofile_binding', payload)

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


def add_lsngroup_lsnappsprofile_binding(appsprofilename=None, groupname=None, save=False):
    '''
    Add a new lsngroup_lsnappsprofile_binding to the running configuration.

    appsprofilename(str): Name of the LSN application profile to bind to the specified LSN group. For each set of destination
        ports, bind a profile for each protocol for which you want to specify settings. By default, one LSN application
        profile with default settings for TCP, UDP, and ICMP protocols for all destination ports is bound to an LSN group
        during its creation. This profile is called a default application profile. When you bind an LSN application
        profile, with a specified set of destination ports, to an LSN group, the bound profile overrides the default LSN
        application profile for that protocol at that set of destination ports.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsngroup_lsnappsprofile_binding <args>

    '''

    result = {}

    payload = {'lsngroup_lsnappsprofile_binding': {}}

    if appsprofilename:
        payload['lsngroup_lsnappsprofile_binding']['appsprofilename'] = appsprofilename

    if groupname:
        payload['lsngroup_lsnappsprofile_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/lsngroup_lsnappsprofile_binding', payload)

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


def add_lsngroup_lsnhttphdrlogprofile_binding(httphdrlogprofilename=None, groupname=None, save=False):
    '''
    Add a new lsngroup_lsnhttphdrlogprofile_binding to the running configuration.

    httphdrlogprofilename(str): The name of the LSN HTTP header logging Profile.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsngroup_lsnhttphdrlogprofile_binding <args>

    '''

    result = {}

    payload = {'lsngroup_lsnhttphdrlogprofile_binding': {}}

    if httphdrlogprofilename:
        payload['lsngroup_lsnhttphdrlogprofile_binding']['httphdrlogprofilename'] = httphdrlogprofilename

    if groupname:
        payload['lsngroup_lsnhttphdrlogprofile_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/lsngroup_lsnhttphdrlogprofile_binding', payload)

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


def add_lsngroup_lsnlogprofile_binding(logprofilename=None, groupname=None, save=False):
    '''
    Add a new lsngroup_lsnlogprofile_binding to the running configuration.

    logprofilename(str): The name of the LSN logging Profile.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsngroup_lsnlogprofile_binding <args>

    '''

    result = {}

    payload = {'lsngroup_lsnlogprofile_binding': {}}

    if logprofilename:
        payload['lsngroup_lsnlogprofile_binding']['logprofilename'] = logprofilename

    if groupname:
        payload['lsngroup_lsnlogprofile_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/lsngroup_lsnlogprofile_binding', payload)

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


def add_lsngroup_lsnpool_binding(poolname=None, groupname=None, save=False):
    '''
    Add a new lsngroup_lsnpool_binding to the running configuration.

    poolname(str): Name of the LSN pool to bind to the specified LSN group. Only LSN Pools and LSN groups with the same NAT
        type settings can be bound together. Multiples LSN pools can be bound to an LSN group. For Deterministic NAT,
        pools bound to an LSN group cannot be bound to other LSN groups. For Dynamic NAT, pools bound to an LSN group can
        be bound to multiple LSN groups.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsngroup_lsnpool_binding <args>

    '''

    result = {}

    payload = {'lsngroup_lsnpool_binding': {}}

    if poolname:
        payload['lsngroup_lsnpool_binding']['poolname'] = poolname

    if groupname:
        payload['lsngroup_lsnpool_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/lsngroup_lsnpool_binding', payload)

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


def add_lsngroup_lsnrtspalgprofile_binding(rtspalgprofilename=None, groupname=None, save=False):
    '''
    Add a new lsngroup_lsnrtspalgprofile_binding to the running configuration.

    rtspalgprofilename(str): The name of the LSN RTSP ALG Profile.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsngroup_lsnrtspalgprofile_binding <args>

    '''

    result = {}

    payload = {'lsngroup_lsnrtspalgprofile_binding': {}}

    if rtspalgprofilename:
        payload['lsngroup_lsnrtspalgprofile_binding']['rtspalgprofilename'] = rtspalgprofilename

    if groupname:
        payload['lsngroup_lsnrtspalgprofile_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/lsngroup_lsnrtspalgprofile_binding', payload)

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


def add_lsngroup_lsnsipalgprofile_binding(sipalgprofilename=None, groupname=None, save=False):
    '''
    Add a new lsngroup_lsnsipalgprofile_binding to the running configuration.

    sipalgprofilename(str): The name of the LSN SIP ALG Profile.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsngroup_lsnsipalgprofile_binding <args>

    '''

    result = {}

    payload = {'lsngroup_lsnsipalgprofile_binding': {}}

    if sipalgprofilename:
        payload['lsngroup_lsnsipalgprofile_binding']['sipalgprofilename'] = sipalgprofilename

    if groupname:
        payload['lsngroup_lsnsipalgprofile_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/lsngroup_lsnsipalgprofile_binding', payload)

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


def add_lsngroup_lsntransportprofile_binding(transportprofilename=None, groupname=None, save=False):
    '''
    Add a new lsngroup_lsntransportprofile_binding to the running configuration.

    transportprofilename(str): Name of the LSN transport profile to bind to the specified LSN group. Bind a profile for each
        protocol for which you want to specify settings. By default, one LSN transport profile with default settings for
        TCP, UDP, and ICMP protocols is bound to an LSN group during its creation. This profile is called a default
        transport. An LSN transport profile that you bind to an LSN group overrides the default LSN transport profile for
        that protocol.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsngroup_lsntransportprofile_binding <args>

    '''

    result = {}

    payload = {'lsngroup_lsntransportprofile_binding': {}}

    if transportprofilename:
        payload['lsngroup_lsntransportprofile_binding']['transportprofilename'] = transportprofilename

    if groupname:
        payload['lsngroup_lsntransportprofile_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/lsngroup_lsntransportprofile_binding', payload)

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


def add_lsngroup_pcpserver_binding(pcpserver=None, groupname=None, save=False):
    '''
    Add a new lsngroup_pcpserver_binding to the running configuration.

    pcpserver(str): Name of the PCP server to be associated with lsn group.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsngroup_pcpserver_binding <args>

    '''

    result = {}

    payload = {'lsngroup_pcpserver_binding': {}}

    if pcpserver:
        payload['lsngroup_pcpserver_binding']['pcpserver'] = pcpserver

    if groupname:
        payload['lsngroup_pcpserver_binding']['groupname'] = groupname

    execution = __proxy__['citrixns.post']('config/lsngroup_pcpserver_binding', payload)

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


def add_lsnhttphdrlogprofile(httphdrlogprofilename=None, logurl=None, logmethod=None, logversion=None, loghost=None,
                             save=False):
    '''
    Add a new lsnhttphdrlogprofile to the running configuration.

    httphdrlogprofilename(str): The name of the HTTP header logging Profile. Minimum length = 1 Maximum length = 127

    logurl(str): URL information is logged if option is enabled. Default value: ENABLED Possible values = ENABLED, DISABLED

    logmethod(str): HTTP method information is logged if option is enabled. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    logversion(str): Version information is logged if option is enabled. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    loghost(str): Host information is logged if option is enabled. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnhttphdrlogprofile <args>

    '''

    result = {}

    payload = {'lsnhttphdrlogprofile': {}}

    if httphdrlogprofilename:
        payload['lsnhttphdrlogprofile']['httphdrlogprofilename'] = httphdrlogprofilename

    if logurl:
        payload['lsnhttphdrlogprofile']['logurl'] = logurl

    if logmethod:
        payload['lsnhttphdrlogprofile']['logmethod'] = logmethod

    if logversion:
        payload['lsnhttphdrlogprofile']['logversion'] = logversion

    if loghost:
        payload['lsnhttphdrlogprofile']['loghost'] = loghost

    execution = __proxy__['citrixns.post']('config/lsnhttphdrlogprofile', payload)

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


def add_lsnip6profile(name=None, ns_type=None, natprefix=None, network6=None, save=False):
    '''
    Add a new lsnip6profile to the running configuration.

    name(str): Name for the LSN ip6 profile. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the LSN ip6 profile is created. The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "lsn ip6 profile1" or lsn ip6 profile1). Minimum length = 1 Maximum length = 127

    ns_type(str): IPv6 translation type for which to set the LSN IP6 profile parameters. Possible values = DS-Lite, NAT64

    natprefix(str): IPv6 address(es) of the LSN subscriber(s) or subscriber network(s) on whose traffic you want the
        NetScaler ADC to perform Large Scale NAT.

    network6(str): IPv6 address of the NetScaler ADC AFTR device.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnip6profile <args>

    '''

    result = {}

    payload = {'lsnip6profile': {}}

    if name:
        payload['lsnip6profile']['name'] = name

    if ns_type:
        payload['lsnip6profile']['type'] = ns_type

    if natprefix:
        payload['lsnip6profile']['natprefix'] = natprefix

    if network6:
        payload['lsnip6profile']['network6'] = network6

    execution = __proxy__['citrixns.post']('config/lsnip6profile', payload)

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


def add_lsnlogprofile(logprofilename=None, logsubscrinfo=None, logcompact=None, save=False):
    '''
    Add a new lsnlogprofile to the running configuration.

    logprofilename(str): The name of the logging Profile. Minimum length = 1 Maximum length = 127

    logsubscrinfo(str): Subscriber ID information is logged if option is enabled. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    logcompact(str): Logs in Compact Logging format if option is enabled. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnlogprofile <args>

    '''

    result = {}

    payload = {'lsnlogprofile': {}}

    if logprofilename:
        payload['lsnlogprofile']['logprofilename'] = logprofilename

    if logsubscrinfo:
        payload['lsnlogprofile']['logsubscrinfo'] = logsubscrinfo

    if logcompact:
        payload['lsnlogprofile']['logcompact'] = logcompact

    execution = __proxy__['citrixns.post']('config/lsnlogprofile', payload)

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


def add_lsnpool(poolname=None, nattype=None, portblockallocation=None, portrealloctimeout=None, maxportrealloctmq=None,
                save=False):
    '''
    Add a new lsnpool to the running configuration.

    poolname(str): Name for the LSN pool. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the LSN pool is created. The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "lsn pool1" or lsn pool1). Minimum length = 1 Maximum length = 127

    nattype(str): Type of NAT IP address and port allocation (from the LSN pools bound to an LSN group) for subscribers (of
        the LSN client entity bound to the LSN group):  Available options function as follows:  * Deterministic -
        Allocate a NAT IP address and a block of ports to each subscriber (of the LSN client bound to the LSN group). The
        NetScaler ADC sequentially allocates NAT resources to these subscribers. The NetScaler ADC assigns the first
        block of ports (block size determined by the port block size parameter of the LSN group) on the beginning NAT IP
        address to the beginning subscriber IP address. The next range of ports is assigned to the next subscriber, and
        so on, until the NAT address does not have enough ports for the next subscriber. In this case, the first port
        block on the next NAT address is used for the subscriber, and so on. Because each subscriber now receives a
        deterministic NAT IP address and a block of ports, a subscriber can be identified without any need for logging.
        For a connection, a subscriber can be identified based only on the NAT IP address and port, and the destination
        IP address and port.   * Dynamic - Allocate a random NAT IP address and a port from the LSN NAT pool for a
        subscribers connection. If port block allocation is enabled (in LSN pool) and a port block size is specified (in
        the LSN group), the NetScaler ADC allocates a random NAT IP address and a block of ports for a subscriber when it
        initiates a connection for the first time. The ADC allocates this NAT IP address and a port (from the allocated
        block of ports) for different connections from this subscriber. If all the ports are allocated (for different
        subscribers connections) from the subscribers allocated port block, the ADC allocates a new random port block for
        the subscriber. Only LSN Pools and LSN groups with the same NAT type settings can be bound together. Multiples
        LSN pools can be bound to an LSN group. A maximum of 16 LSN pools can be bound to an LSN group. . Default value:
        DYNAMIC Possible values = DYNAMIC, DETERMINISTIC

    portblockallocation(str): Allocate a random NAT port block, from the available NAT port pool of an NAT IP address, for
        each subscriber when the NAT allocation is set as Dynamic NAT. For any connection initiated from a subscriber,
        the NetScaler ADC allocates a NAT port from the subscribers allocated NAT port block to create the LSN session.
        You must set the port block size in the bound LSN group. For a subscriber, if all the ports are allocated from
        the subscribers allocated port block, the NetScaler ADC allocates a new random port block for the subscriber.
        For Deterministic NAT, this parameter is enabled by default, and you cannot disable it. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    portrealloctimeout(int): The waiting time, in seconds, between deallocating LSN NAT ports (when an LSN mapping is
        removed) and reallocating them for a new LSN session. This parameter is necessary in order to prevent collisions
        between old and new mappings and sessions. It ensures that all established sessions are broken instead of
        redirected to a different subscriber. This is not applicable for ports used in: * Deterministic NAT *
        Address-Dependent filtering and Address-Port-Dependent filtering * Dynamic NAT with port block allocation In
        these cases, ports are immediately reallocated. Default value: 0 Minimum value = 0 Maximum value = 600

    maxportrealloctmq(int): Maximum number of ports for which the port reallocation timeout applies for each NAT IP address.
        In other words, the maximum deallocated-port queue size for which the reallocation timeout applies for each NAT
        IP address.  When the queue size is full, the next port deallocated is reallocated immediately for a new LSN
        session. Default value: 65536 Minimum value = 0 Maximum value = 65536

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnpool <args>

    '''

    result = {}

    payload = {'lsnpool': {}}

    if poolname:
        payload['lsnpool']['poolname'] = poolname

    if nattype:
        payload['lsnpool']['nattype'] = nattype

    if portblockallocation:
        payload['lsnpool']['portblockallocation'] = portblockallocation

    if portrealloctimeout:
        payload['lsnpool']['portrealloctimeout'] = portrealloctimeout

    if maxportrealloctmq:
        payload['lsnpool']['maxportrealloctmq'] = maxportrealloctmq

    execution = __proxy__['citrixns.post']('config/lsnpool', payload)

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


def add_lsnpool_lsnip_binding(poolname=None, save=False):
    '''
    Add a new lsnpool_lsnip_binding to the running configuration.

    poolname(str): Name for the LSN pool. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnpool_lsnip_binding <args>

    '''

    result = {}

    payload = {'lsnpool_lsnip_binding': {}}

    if poolname:
        payload['lsnpool_lsnip_binding']['poolname'] = poolname

    execution = __proxy__['citrixns.post']('config/lsnpool_lsnip_binding', payload)

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


def add_lsnrtspalgprofile(rtspalgprofilename=None, rtspidletimeout=None, rtspportrange=None, rtsptransportprotocol=None,
                          save=False):
    '''
    Add a new lsnrtspalgprofile to the running configuration.

    rtspalgprofilename(str): The name of the RTSPALG Profile. Minimum length = 1 Maximum length = 127

    rtspidletimeout(int): Idle timeout for the rtsp sessions in seconds. Default value: 120

    rtspportrange(str): port for the RTSP.

    rtsptransportprotocol(str): RTSP ALG Profile transport protocol type. Default value: TCP Possible values = TCP, UDP

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnrtspalgprofile <args>

    '''

    result = {}

    payload = {'lsnrtspalgprofile': {}}

    if rtspalgprofilename:
        payload['lsnrtspalgprofile']['rtspalgprofilename'] = rtspalgprofilename

    if rtspidletimeout:
        payload['lsnrtspalgprofile']['rtspidletimeout'] = rtspidletimeout

    if rtspportrange:
        payload['lsnrtspalgprofile']['rtspportrange'] = rtspportrange

    if rtsptransportprotocol:
        payload['lsnrtspalgprofile']['rtsptransportprotocol'] = rtsptransportprotocol

    execution = __proxy__['citrixns.post']('config/lsnrtspalgprofile', payload)

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


def add_lsnsipalgprofile(sipalgprofilename=None, datasessionidletimeout=None, sipsessiontimeout=None,
                         registrationtimeout=None, sipsrcportrange=None, sipdstportrange=None, openregisterpinhole=None,
                         opencontactpinhole=None, openviapinhole=None, openrecordroutepinhole=None,
                         siptransportprotocol=None, openroutepinhole=None, rport=None, save=False):
    '''
    Add a new lsnsipalgprofile to the running configuration.

    sipalgprofilename(str): The name of the SIPALG Profile. Minimum length = 1 Maximum length = 127

    datasessionidletimeout(int): Idle timeout for the data channel sessions in seconds. Default value: 120

    sipsessiontimeout(int): SIP control channel session timeout in seconds. Default value: 600

    registrationtimeout(int): SIP registration timeout in seconds. Default value: 60

    sipsrcportrange(str): Source port range for SIP_UDP and SIP_TCP.

    sipdstportrange(str): Destination port range for SIP_UDP and SIP_TCP.

    openregisterpinhole(str): ENABLE/DISABLE RegisterPinhole creation. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    opencontactpinhole(str): ENABLE/DISABLE ContactPinhole creation. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    openviapinhole(str): ENABLE/DISABLE ViaPinhole creation. Default value: ENABLED Possible values = ENABLED, DISABLED

    openrecordroutepinhole(str): ENABLE/DISABLE RecordRoutePinhole creation. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    siptransportprotocol(str): SIP ALG Profile transport protocol type. Possible values = TCP, UDP

    openroutepinhole(str): ENABLE/DISABLE RoutePinhole creation. Default value: ENABLED Possible values = ENABLED, DISABLED

    rport(str): ENABLE/DISABLE rport. Default value: ENABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnsipalgprofile <args>

    '''

    result = {}

    payload = {'lsnsipalgprofile': {}}

    if sipalgprofilename:
        payload['lsnsipalgprofile']['sipalgprofilename'] = sipalgprofilename

    if datasessionidletimeout:
        payload['lsnsipalgprofile']['datasessionidletimeout'] = datasessionidletimeout

    if sipsessiontimeout:
        payload['lsnsipalgprofile']['sipsessiontimeout'] = sipsessiontimeout

    if registrationtimeout:
        payload['lsnsipalgprofile']['registrationtimeout'] = registrationtimeout

    if sipsrcportrange:
        payload['lsnsipalgprofile']['sipsrcportrange'] = sipsrcportrange

    if sipdstportrange:
        payload['lsnsipalgprofile']['sipdstportrange'] = sipdstportrange

    if openregisterpinhole:
        payload['lsnsipalgprofile']['openregisterpinhole'] = openregisterpinhole

    if opencontactpinhole:
        payload['lsnsipalgprofile']['opencontactpinhole'] = opencontactpinhole

    if openviapinhole:
        payload['lsnsipalgprofile']['openviapinhole'] = openviapinhole

    if openrecordroutepinhole:
        payload['lsnsipalgprofile']['openrecordroutepinhole'] = openrecordroutepinhole

    if siptransportprotocol:
        payload['lsnsipalgprofile']['siptransportprotocol'] = siptransportprotocol

    if openroutepinhole:
        payload['lsnsipalgprofile']['openroutepinhole'] = openroutepinhole

    if rport:
        payload['lsnsipalgprofile']['rport'] = rport

    execution = __proxy__['citrixns.post']('config/lsnsipalgprofile', payload)

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


def add_lsnstatic(name=None, transportprotocol=None, subscrip=None, subscrport=None, network6=None, td=None, natip=None,
                  natport=None, destip=None, dsttd=None, nattype=None, save=False):
    '''
    Add a new lsnstatic to the running configuration.

    name(str): Name for the LSN static mapping entry. Must begin with an ASCII alphanumeric or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the LSN group is created. The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "lsn static1" or lsn static1). Minimum length = 1 Maximum length = 127

    transportprotocol(str): Protocol for the LSN mapping entry. Possible values = TCP, UDP, ICMP, ALL

    subscrip(str): IPv4(NAT44 ;amp; DS-Lite)/IPv6(NAT64) address of an LSN subscriber for the LSN static mapping entry.

    subscrport(int): Port of the LSN subscriber for the LSN mapping entry. * represents all ports being used. Used in case of
        static wildcard. Minimum value = 0 Maximum value = 65535 Range 1 - 65535 * in CLI is represented as 65535 in
        NITRO API

    network6(str): B4 address in DS-Lite setup. Minimum length = 1

    td(int): ID of the traffic domain to which the subscriber belongs.   If you do not specify an ID, the subscriber is
        assumed to be a part of the default traffic domain. Default value: 0 Minimum value = 0 Maximum value = 4094

    natip(str): IPv4 address, already existing on the NetScaler ADC as type LSN, to be used as NAT IP address for this
        mapping entry.

    natport(int): NAT port for this LSN mapping entry. * represents all ports being used. Used in case of static wildcard.
        Minimum value = 0 Maximum value = 65535 Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    destip(str): Destination IP address for the LSN mapping entry.

    dsttd(int): ID of the traffic domain through which the destination IP address for this LSN mapping entry is reachable
        from the NetScaler ADC.  If you do not specify an ID, the destination IP address is assumed to be reachable
        through the default traffic domain, which has an ID of 0. Default value: 0 Minimum value = 0 Maximum value =
        4094

    nattype(str): Type of sessions to be displayed. Possible values = NAT44, DS-Lite, NAT64

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsnstatic <args>

    '''

    result = {}

    payload = {'lsnstatic': {}}

    if name:
        payload['lsnstatic']['name'] = name

    if transportprotocol:
        payload['lsnstatic']['transportprotocol'] = transportprotocol

    if subscrip:
        payload['lsnstatic']['subscrip'] = subscrip

    if subscrport:
        payload['lsnstatic']['subscrport'] = subscrport

    if network6:
        payload['lsnstatic']['network6'] = network6

    if td:
        payload['lsnstatic']['td'] = td

    if natip:
        payload['lsnstatic']['natip'] = natip

    if natport:
        payload['lsnstatic']['natport'] = natport

    if destip:
        payload['lsnstatic']['destip'] = destip

    if dsttd:
        payload['lsnstatic']['dsttd'] = dsttd

    if nattype:
        payload['lsnstatic']['nattype'] = nattype

    execution = __proxy__['citrixns.post']('config/lsnstatic', payload)

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


def add_lsntransportprofile(transportprofilename=None, transportprotocol=None, sessiontimeout=None, finrsttimeout=None,
                            stuntimeout=None, synidletimeout=None, portquota=None, sessionquota=None,
                            groupsessionlimit=None, portpreserveparity=None, portpreserverange=None, syncheck=None,
                            save=False):
    '''
    Add a new lsntransportprofile to the running configuration.

    transportprofilename(str): Name for the LSN transport profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after the LSN transport profile is created. The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "lsn transport profile1" or lsn transport profile1).
        Minimum length = 1 Maximum length = 127

    transportprotocol(str): Protocol for which to set the LSN transport profile parameters. Possible values = TCP, UDP, ICMP

    sessiontimeout(int): Timeout, in seconds, for an idle LSN session. If an LSN session is idle for a time that exceeds this
        value, the NetScaler ADC removes the session.  This timeout does not apply for a TCP LSN session when a FIN or
        RST message is received from either of the endpoints. . Default value: 120 Minimum value = 60

    finrsttimeout(int): Timeout, in seconds, for a TCP LSN session after a FIN or RST message is received from one of the
        endpoints.  If a TCP LSN session is idle (after the NetScaler ADC receives a FIN or RST message) for a time that
        exceeds this value, the NetScaler ADC removes the session.  Since the LSN feature of the NetScaler ADC does not
        maintain state information of any TCP LSN sessions, this timeout accommodates the transmission of the FIN or RST,
        and ACK messages from the other endpoint so that both endpoints can properly close the connection. Default value:
        30

    stuntimeout(int): STUN protocol timeout. Default value: 600 Minimum value = 120 Maximum value = 1200

    synidletimeout(int): SYN Idle timeout. Default value: 60 Minimum value = 30 Maximum value = 120

    portquota(int): Maximum number of LSN NAT ports to be used at a time by each subscriber for the specified protocol. For
        example, each subscriber can be limited to a maximum of 500 TCP NAT ports. When the LSN NAT mappings for a
        subscriber reach the limit, the NetScaler ADC does not allocate additional NAT ports for that subscriber. Default
        value: 0 Minimum value = 0 Maximum value = 65535

    sessionquota(int): Maximum number of concurrent LSN sessions allowed for each subscriber for the specified protocol.
        When the number of LSN sessions reaches the limit for a subscriber, the NetScaler ADC does not allow the
        subscriber to open additional sessions. Default value: 0 Minimum value = 0 Maximum value = 65535

    groupsessionlimit(int): Maximum number of concurrent LSN sessions(for the specified protocol) allowed for all subscriber
        of a group to which this profile has bound. This limit will get split across the netscalers packet engines and
        rounded down. When the number of LSN sessions reaches the limit for a group in packet engine, the NetScaler ADC
        does not allow the subscriber of that group to open additional sessions through that packet engine. Default
        value: 0

    portpreserveparity(str): Enable port parity between a subscriber port and its mapped LSN NAT port. For example, if a
        subscriber initiates a connection from an odd numbered port, the NetScaler ADC allocates an odd numbered LSN NAT
        port for this connection.  You must set this parameter for proper functioning of protocols that require the
        source port to be even or odd numbered, for example, in peer-to-peer applications that use RTP or RTCP protocol.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    portpreserverange(str): If a subscriber initiates a connection from a well-known port (0-1023), allocate a NAT port from
        the well-known port range (0-1023) for this connection. For example, if a subscriber initiates a connection from
        port 80, the NetScaler ADC can allocate port 100 as the NAT port for this connection.  This parameter applies to
        dynamic NAT without port block allocation. It also applies to Deterministic NAT if the range of ports allocated
        includes well-known ports.  When all the well-known ports of all the available NAT IP addresses are used in
        different subscribers connections (LSN sessions), and a subscriber initiates a connection from a well-known port,
        the NetScaler ADC drops this connection. Default value: DISABLED Possible values = ENABLED, DISABLED

    syncheck(str): Silently drop any non-SYN packets for connections for which there is no LSN-NAT session present on the
        NetScaler ADC.   If you disable this parameter, the NetScaler ADC accepts any non-SYN packets and creates a new
        LSN session entry for this connection.   Following are some reasons for the NetScaler ADC to receive such
        packets:  * LSN session for a connection existed but the NetScaler ADC removed this session because the LSN
        session was idle for a time that exceeded the configured session timeout. * Such packets can be a part of a DoS
        attack. Default value: ENABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.add_lsntransportprofile <args>

    '''

    result = {}

    payload = {'lsntransportprofile': {}}

    if transportprofilename:
        payload['lsntransportprofile']['transportprofilename'] = transportprofilename

    if transportprotocol:
        payload['lsntransportprofile']['transportprotocol'] = transportprotocol

    if sessiontimeout:
        payload['lsntransportprofile']['sessiontimeout'] = sessiontimeout

    if finrsttimeout:
        payload['lsntransportprofile']['finrsttimeout'] = finrsttimeout

    if stuntimeout:
        payload['lsntransportprofile']['stuntimeout'] = stuntimeout

    if synidletimeout:
        payload['lsntransportprofile']['synidletimeout'] = synidletimeout

    if portquota:
        payload['lsntransportprofile']['portquota'] = portquota

    if sessionquota:
        payload['lsntransportprofile']['sessionquota'] = sessionquota

    if groupsessionlimit:
        payload['lsntransportprofile']['groupsessionlimit'] = groupsessionlimit

    if portpreserveparity:
        payload['lsntransportprofile']['portpreserveparity'] = portpreserveparity

    if portpreserverange:
        payload['lsntransportprofile']['portpreserverange'] = portpreserverange

    if syncheck:
        payload['lsntransportprofile']['syncheck'] = syncheck

    execution = __proxy__['citrixns.post']('config/lsntransportprofile', payload)

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


def get_lsnappsprofile(appsprofilename=None, transportprotocol=None, ippooling=None, mapping=None, filtering=None,
                       tcpproxy=None, td=None, l2info=None):
    '''
    Show the running configuration for the lsnappsprofile config key.

    appsprofilename(str): Filters results that only match the appsprofilename field.

    transportprotocol(str): Filters results that only match the transportprotocol field.

    ippooling(str): Filters results that only match the ippooling field.

    mapping(str): Filters results that only match the mapping field.

    filtering(str): Filters results that only match the filtering field.

    tcpproxy(str): Filters results that only match the tcpproxy field.

    td(int): Filters results that only match the td field.

    l2info(str): Filters results that only match the l2info field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnappsprofile

    '''

    search_filter = []

    if appsprofilename:
        search_filter.append(['appsprofilename', appsprofilename])

    if transportprotocol:
        search_filter.append(['transportprotocol', transportprotocol])

    if ippooling:
        search_filter.append(['ippooling', ippooling])

    if mapping:
        search_filter.append(['mapping', mapping])

    if filtering:
        search_filter.append(['filtering', filtering])

    if tcpproxy:
        search_filter.append(['tcpproxy', tcpproxy])

    if td:
        search_filter.append(['td', td])

    if l2info:
        search_filter.append(['l2info', l2info])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnappsprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnappsprofile')

    return response


def get_lsnappsprofile_binding():
    '''
    Show the running configuration for the lsnappsprofile_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnappsprofile_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnappsprofile_binding'), 'lsnappsprofile_binding')

    return response


def get_lsnappsprofile_port_binding(appsprofilename=None):
    '''
    Show the running configuration for the lsnappsprofile_port_binding config key.

    appsprofilename(str): Filters results that only match the appsprofilename field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnappsprofile_port_binding

    '''

    search_filter = []

    if appsprofilename:
        search_filter.append(['appsprofilename', appsprofilename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnappsprofile_port_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnappsprofile_port_binding')

    return response


def get_lsnclient(clientname=None):
    '''
    Show the running configuration for the lsnclient config key.

    clientname(str): Filters results that only match the clientname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnclient

    '''

    search_filter = []

    if clientname:
        search_filter.append(['clientname', clientname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnclient{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnclient')

    return response


def get_lsnclient_binding():
    '''
    Show the running configuration for the lsnclient_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnclient_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnclient_binding'), 'lsnclient_binding')

    return response


def get_lsnclient_network6_binding(network=None, clientname=None):
    '''
    Show the running configuration for the lsnclient_network6_binding config key.

    network(str): Filters results that only match the network field.

    clientname(str): Filters results that only match the clientname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnclient_network6_binding

    '''

    search_filter = []

    if network:
        search_filter.append(['network', network])

    if clientname:
        search_filter.append(['clientname', clientname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnclient_network6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnclient_network6_binding')

    return response


def get_lsnclient_network_binding(network=None, clientname=None):
    '''
    Show the running configuration for the lsnclient_network_binding config key.

    network(str): Filters results that only match the network field.

    clientname(str): Filters results that only match the clientname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnclient_network_binding

    '''

    search_filter = []

    if network:
        search_filter.append(['network', network])

    if clientname:
        search_filter.append(['clientname', clientname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnclient_network_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnclient_network_binding')

    return response


def get_lsnclient_nsacl6_binding(clientname=None):
    '''
    Show the running configuration for the lsnclient_nsacl6_binding config key.

    clientname(str): Filters results that only match the clientname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnclient_nsacl6_binding

    '''

    search_filter = []

    if clientname:
        search_filter.append(['clientname', clientname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnclient_nsacl6_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnclient_nsacl6_binding')

    return response


def get_lsnclient_nsacl_binding(clientname=None):
    '''
    Show the running configuration for the lsnclient_nsacl_binding config key.

    clientname(str): Filters results that only match the clientname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnclient_nsacl_binding

    '''

    search_filter = []

    if clientname:
        search_filter.append(['clientname', clientname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnclient_nsacl_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnclient_nsacl_binding')

    return response


def get_lsndeterministicnat(clientname=None, network6=None, subscrip=None, td=None, natip=None):
    '''
    Show the running configuration for the lsndeterministicnat config key.

    clientname(str): Filters results that only match the clientname field.

    network6(str): Filters results that only match the network6 field.

    subscrip(str): Filters results that only match the subscrip field.

    td(int): Filters results that only match the td field.

    natip(str): Filters results that only match the natip field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsndeterministicnat

    '''

    search_filter = []

    if clientname:
        search_filter.append(['clientname', clientname])

    if network6:
        search_filter.append(['network6', network6])

    if subscrip:
        search_filter.append(['subscrip', subscrip])

    if td:
        search_filter.append(['td', td])

    if natip:
        search_filter.append(['natip', natip])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsndeterministicnat{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsndeterministicnat')

    return response


def get_lsngroup(groupname=None, clientname=None, nattype=None, allocpolicy=None, portblocksize=None, logging=None,
                 sessionlogging=None, sessionsync=None, snmptraplimit=None, ftp=None, pptp=None, sipalg=None,
                 rtspalg=None, ip6profile=None):
    '''
    Show the running configuration for the lsngroup config key.

    groupname(str): Filters results that only match the groupname field.

    clientname(str): Filters results that only match the clientname field.

    nattype(str): Filters results that only match the nattype field.

    allocpolicy(str): Filters results that only match the allocpolicy field.

    portblocksize(int): Filters results that only match the portblocksize field.

    logging(str): Filters results that only match the logging field.

    sessionlogging(str): Filters results that only match the sessionlogging field.

    sessionsync(str): Filters results that only match the sessionsync field.

    snmptraplimit(int): Filters results that only match the snmptraplimit field.

    ftp(str): Filters results that only match the ftp field.

    pptp(str): Filters results that only match the pptp field.

    sipalg(str): Filters results that only match the sipalg field.

    rtspalg(str): Filters results that only match the rtspalg field.

    ip6profile(str): Filters results that only match the ip6profile field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup

    '''

    search_filter = []

    if groupname:
        search_filter.append(['groupname', groupname])

    if clientname:
        search_filter.append(['clientname', clientname])

    if nattype:
        search_filter.append(['nattype', nattype])

    if allocpolicy:
        search_filter.append(['allocpolicy', allocpolicy])

    if portblocksize:
        search_filter.append(['portblocksize', portblocksize])

    if logging:
        search_filter.append(['logging', logging])

    if sessionlogging:
        search_filter.append(['sessionlogging', sessionlogging])

    if sessionsync:
        search_filter.append(['sessionsync', sessionsync])

    if snmptraplimit:
        search_filter.append(['snmptraplimit', snmptraplimit])

    if ftp:
        search_filter.append(['ftp', ftp])

    if pptp:
        search_filter.append(['pptp', pptp])

    if sipalg:
        search_filter.append(['sipalg', sipalg])

    if rtspalg:
        search_filter.append(['rtspalg', rtspalg])

    if ip6profile:
        search_filter.append(['ip6profile', ip6profile])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsngroup')

    return response


def get_lsngroup_binding():
    '''
    Show the running configuration for the lsngroup_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup_binding'), 'lsngroup_binding')

    return response


def get_lsngroup_ipsecalgprofile_binding(ipsecalgprofile=None, groupname=None):
    '''
    Show the running configuration for the lsngroup_ipsecalgprofile_binding config key.

    ipsecalgprofile(str): Filters results that only match the ipsecalgprofile field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup_ipsecalgprofile_binding

    '''

    search_filter = []

    if ipsecalgprofile:
        search_filter.append(['ipsecalgprofile', ipsecalgprofile])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup_ipsecalgprofile_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsngroup_ipsecalgprofile_binding')

    return response


def get_lsngroup_lsnappsprofile_binding(appsprofilename=None, groupname=None):
    '''
    Show the running configuration for the lsngroup_lsnappsprofile_binding config key.

    appsprofilename(str): Filters results that only match the appsprofilename field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup_lsnappsprofile_binding

    '''

    search_filter = []

    if appsprofilename:
        search_filter.append(['appsprofilename', appsprofilename])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup_lsnappsprofile_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsngroup_lsnappsprofile_binding')

    return response


def get_lsngroup_lsnhttphdrlogprofile_binding(httphdrlogprofilename=None, groupname=None):
    '''
    Show the running configuration for the lsngroup_lsnhttphdrlogprofile_binding config key.

    httphdrlogprofilename(str): Filters results that only match the httphdrlogprofilename field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup_lsnhttphdrlogprofile_binding

    '''

    search_filter = []

    if httphdrlogprofilename:
        search_filter.append(['httphdrlogprofilename', httphdrlogprofilename])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup_lsnhttphdrlogprofile_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsngroup_lsnhttphdrlogprofile_binding')

    return response


def get_lsngroup_lsnlogprofile_binding(logprofilename=None, groupname=None):
    '''
    Show the running configuration for the lsngroup_lsnlogprofile_binding config key.

    logprofilename(str): Filters results that only match the logprofilename field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup_lsnlogprofile_binding

    '''

    search_filter = []

    if logprofilename:
        search_filter.append(['logprofilename', logprofilename])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup_lsnlogprofile_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsngroup_lsnlogprofile_binding')

    return response


def get_lsngroup_lsnpool_binding(poolname=None, groupname=None):
    '''
    Show the running configuration for the lsngroup_lsnpool_binding config key.

    poolname(str): Filters results that only match the poolname field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup_lsnpool_binding

    '''

    search_filter = []

    if poolname:
        search_filter.append(['poolname', poolname])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup_lsnpool_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsngroup_lsnpool_binding')

    return response


def get_lsngroup_lsnrtspalgprofile_binding(rtspalgprofilename=None, groupname=None):
    '''
    Show the running configuration for the lsngroup_lsnrtspalgprofile_binding config key.

    rtspalgprofilename(str): Filters results that only match the rtspalgprofilename field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup_lsnrtspalgprofile_binding

    '''

    search_filter = []

    if rtspalgprofilename:
        search_filter.append(['rtspalgprofilename', rtspalgprofilename])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup_lsnrtspalgprofile_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsngroup_lsnrtspalgprofile_binding')

    return response


def get_lsngroup_lsnsipalgprofile_binding(sipalgprofilename=None, groupname=None):
    '''
    Show the running configuration for the lsngroup_lsnsipalgprofile_binding config key.

    sipalgprofilename(str): Filters results that only match the sipalgprofilename field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup_lsnsipalgprofile_binding

    '''

    search_filter = []

    if sipalgprofilename:
        search_filter.append(['sipalgprofilename', sipalgprofilename])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup_lsnsipalgprofile_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsngroup_lsnsipalgprofile_binding')

    return response


def get_lsngroup_lsntransportprofile_binding(transportprofilename=None, groupname=None):
    '''
    Show the running configuration for the lsngroup_lsntransportprofile_binding config key.

    transportprofilename(str): Filters results that only match the transportprofilename field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup_lsntransportprofile_binding

    '''

    search_filter = []

    if transportprofilename:
        search_filter.append(['transportprofilename', transportprofilename])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup_lsntransportprofile_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsngroup_lsntransportprofile_binding')

    return response


def get_lsngroup_pcpserver_binding(pcpserver=None, groupname=None):
    '''
    Show the running configuration for the lsngroup_pcpserver_binding config key.

    pcpserver(str): Filters results that only match the pcpserver field.

    groupname(str): Filters results that only match the groupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsngroup_pcpserver_binding

    '''

    search_filter = []

    if pcpserver:
        search_filter.append(['pcpserver', pcpserver])

    if groupname:
        search_filter.append(['groupname', groupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsngroup_pcpserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsngroup_pcpserver_binding')

    return response


def get_lsnhttphdrlogprofile(httphdrlogprofilename=None, logurl=None, logmethod=None, logversion=None, loghost=None):
    '''
    Show the running configuration for the lsnhttphdrlogprofile config key.

    httphdrlogprofilename(str): Filters results that only match the httphdrlogprofilename field.

    logurl(str): Filters results that only match the logurl field.

    logmethod(str): Filters results that only match the logmethod field.

    logversion(str): Filters results that only match the logversion field.

    loghost(str): Filters results that only match the loghost field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnhttphdrlogprofile

    '''

    search_filter = []

    if httphdrlogprofilename:
        search_filter.append(['httphdrlogprofilename', httphdrlogprofilename])

    if logurl:
        search_filter.append(['logurl', logurl])

    if logmethod:
        search_filter.append(['logmethod', logmethod])

    if logversion:
        search_filter.append(['logversion', logversion])

    if loghost:
        search_filter.append(['loghost', loghost])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnhttphdrlogprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnhttphdrlogprofile')

    return response


def get_lsnip6profile(name=None, ns_type=None, natprefix=None, network6=None):
    '''
    Show the running configuration for the lsnip6profile config key.

    name(str): Filters results that only match the name field.

    ns_type(str): Filters results that only match the type field.

    natprefix(str): Filters results that only match the natprefix field.

    network6(str): Filters results that only match the network6 field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnip6profile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ns_type:
        search_filter.append(['type', ns_type])

    if natprefix:
        search_filter.append(['natprefix', natprefix])

    if network6:
        search_filter.append(['network6', network6])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnip6profile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnip6profile')

    return response


def get_lsnlogprofile(logprofilename=None, logsubscrinfo=None, logcompact=None):
    '''
    Show the running configuration for the lsnlogprofile config key.

    logprofilename(str): Filters results that only match the logprofilename field.

    logsubscrinfo(str): Filters results that only match the logsubscrinfo field.

    logcompact(str): Filters results that only match the logcompact field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnlogprofile

    '''

    search_filter = []

    if logprofilename:
        search_filter.append(['logprofilename', logprofilename])

    if logsubscrinfo:
        search_filter.append(['logsubscrinfo', logsubscrinfo])

    if logcompact:
        search_filter.append(['logcompact', logcompact])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnlogprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnlogprofile')

    return response


def get_lsnparameter():
    '''
    Show the running configuration for the lsnparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnparameter'), 'lsnparameter')

    return response


def get_lsnpool(poolname=None, nattype=None, portblockallocation=None, portrealloctimeout=None, maxportrealloctmq=None):
    '''
    Show the running configuration for the lsnpool config key.

    poolname(str): Filters results that only match the poolname field.

    nattype(str): Filters results that only match the nattype field.

    portblockallocation(str): Filters results that only match the portblockallocation field.

    portrealloctimeout(int): Filters results that only match the portrealloctimeout field.

    maxportrealloctmq(int): Filters results that only match the maxportrealloctmq field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnpool

    '''

    search_filter = []

    if poolname:
        search_filter.append(['poolname', poolname])

    if nattype:
        search_filter.append(['nattype', nattype])

    if portblockallocation:
        search_filter.append(['portblockallocation', portblockallocation])

    if portrealloctimeout:
        search_filter.append(['portrealloctimeout', portrealloctimeout])

    if maxportrealloctmq:
        search_filter.append(['maxportrealloctmq', maxportrealloctmq])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnpool{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnpool')

    return response


def get_lsnpool_binding():
    '''
    Show the running configuration for the lsnpool_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnpool_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnpool_binding'), 'lsnpool_binding')

    return response


def get_lsnpool_lsnip_binding(poolname=None):
    '''
    Show the running configuration for the lsnpool_lsnip_binding config key.

    poolname(str): Filters results that only match the poolname field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnpool_lsnip_binding

    '''

    search_filter = []

    if poolname:
        search_filter.append(['poolname', poolname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnpool_lsnip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnpool_lsnip_binding')

    return response


def get_lsnrtspalgprofile(rtspalgprofilename=None, rtspidletimeout=None, rtspportrange=None,
                          rtsptransportprotocol=None):
    '''
    Show the running configuration for the lsnrtspalgprofile config key.

    rtspalgprofilename(str): Filters results that only match the rtspalgprofilename field.

    rtspidletimeout(int): Filters results that only match the rtspidletimeout field.

    rtspportrange(str): Filters results that only match the rtspportrange field.

    rtsptransportprotocol(str): Filters results that only match the rtsptransportprotocol field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnrtspalgprofile

    '''

    search_filter = []

    if rtspalgprofilename:
        search_filter.append(['rtspalgprofilename', rtspalgprofilename])

    if rtspidletimeout:
        search_filter.append(['rtspidletimeout', rtspidletimeout])

    if rtspportrange:
        search_filter.append(['rtspportrange', rtspportrange])

    if rtsptransportprotocol:
        search_filter.append(['rtsptransportprotocol', rtsptransportprotocol])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnrtspalgprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnrtspalgprofile')

    return response


def get_lsnrtspalgsession(sessionid=None):
    '''
    Show the running configuration for the lsnrtspalgsession config key.

    sessionid(str): Filters results that only match the sessionid field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnrtspalgsession

    '''

    search_filter = []

    if sessionid:
        search_filter.append(['sessionid', sessionid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnrtspalgsession{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnrtspalgsession')

    return response


def get_lsnrtspalgsession_binding():
    '''
    Show the running configuration for the lsnrtspalgsession_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnrtspalgsession_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnrtspalgsession_binding'), 'lsnrtspalgsession_binding')

    return response


def get_lsnrtspalgsession_datachannel_binding(channelip=None, sessionid=None):
    '''
    Show the running configuration for the lsnrtspalgsession_datachannel_binding config key.

    channelip(str): Filters results that only match the channelip field.

    sessionid(str): Filters results that only match the sessionid field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnrtspalgsession_datachannel_binding

    '''

    search_filter = []

    if channelip:
        search_filter.append(['channelip', channelip])

    if sessionid:
        search_filter.append(['sessionid', sessionid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnrtspalgsession_datachannel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnrtspalgsession_datachannel_binding')

    return response


def get_lsnsession(nattype=None, clientname=None, network=None, netmask=None, network6=None, td=None, natip=None,
                   natport2=None):
    '''
    Show the running configuration for the lsnsession config key.

    nattype(str): Filters results that only match the nattype field.

    clientname(str): Filters results that only match the clientname field.

    network(str): Filters results that only match the network field.

    netmask(str): Filters results that only match the netmask field.

    network6(str): Filters results that only match the network6 field.

    td(int): Filters results that only match the td field.

    natip(str): Filters results that only match the natip field.

    natport2(int): Filters results that only match the natport2 field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnsession

    '''

    search_filter = []

    if nattype:
        search_filter.append(['nattype', nattype])

    if clientname:
        search_filter.append(['clientname', clientname])

    if network:
        search_filter.append(['network', network])

    if netmask:
        search_filter.append(['netmask', netmask])

    if network6:
        search_filter.append(['network6', network6])

    if td:
        search_filter.append(['td', td])

    if natip:
        search_filter.append(['natip', natip])

    if natport2:
        search_filter.append(['natport2', natport2])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnsession{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnsession')

    return response


def get_lsnsipalgcall(callid=None):
    '''
    Show the running configuration for the lsnsipalgcall config key.

    callid(str): Filters results that only match the callid field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnsipalgcall

    '''

    search_filter = []

    if callid:
        search_filter.append(['callid', callid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnsipalgcall{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnsipalgcall')

    return response


def get_lsnsipalgcall_binding():
    '''
    Show the running configuration for the lsnsipalgcall_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnsipalgcall_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnsipalgcall_binding'), 'lsnsipalgcall_binding')

    return response


def get_lsnsipalgcall_controlchannel_binding(channelip=None, callid=None):
    '''
    Show the running configuration for the lsnsipalgcall_controlchannel_binding config key.

    channelip(str): Filters results that only match the channelip field.

    callid(str): Filters results that only match the callid field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnsipalgcall_controlchannel_binding

    '''

    search_filter = []

    if channelip:
        search_filter.append(['channelip', channelip])

    if callid:
        search_filter.append(['callid', callid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnsipalgcall_controlchannel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnsipalgcall_controlchannel_binding')

    return response


def get_lsnsipalgcall_datachannel_binding(channelip=None, callid=None):
    '''
    Show the running configuration for the lsnsipalgcall_datachannel_binding config key.

    channelip(str): Filters results that only match the channelip field.

    callid(str): Filters results that only match the callid field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnsipalgcall_datachannel_binding

    '''

    search_filter = []

    if channelip:
        search_filter.append(['channelip', channelip])

    if callid:
        search_filter.append(['callid', callid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnsipalgcall_datachannel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnsipalgcall_datachannel_binding')

    return response


def get_lsnsipalgprofile(sipalgprofilename=None, datasessionidletimeout=None, sipsessiontimeout=None,
                         registrationtimeout=None, sipsrcportrange=None, sipdstportrange=None, openregisterpinhole=None,
                         opencontactpinhole=None, openviapinhole=None, openrecordroutepinhole=None,
                         siptransportprotocol=None, openroutepinhole=None, rport=None):
    '''
    Show the running configuration for the lsnsipalgprofile config key.

    sipalgprofilename(str): Filters results that only match the sipalgprofilename field.

    datasessionidletimeout(int): Filters results that only match the datasessionidletimeout field.

    sipsessiontimeout(int): Filters results that only match the sipsessiontimeout field.

    registrationtimeout(int): Filters results that only match the registrationtimeout field.

    sipsrcportrange(str): Filters results that only match the sipsrcportrange field.

    sipdstportrange(str): Filters results that only match the sipdstportrange field.

    openregisterpinhole(str): Filters results that only match the openregisterpinhole field.

    opencontactpinhole(str): Filters results that only match the opencontactpinhole field.

    openviapinhole(str): Filters results that only match the openviapinhole field.

    openrecordroutepinhole(str): Filters results that only match the openrecordroutepinhole field.

    siptransportprotocol(str): Filters results that only match the siptransportprotocol field.

    openroutepinhole(str): Filters results that only match the openroutepinhole field.

    rport(str): Filters results that only match the rport field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnsipalgprofile

    '''

    search_filter = []

    if sipalgprofilename:
        search_filter.append(['sipalgprofilename', sipalgprofilename])

    if datasessionidletimeout:
        search_filter.append(['datasessionidletimeout', datasessionidletimeout])

    if sipsessiontimeout:
        search_filter.append(['sipsessiontimeout', sipsessiontimeout])

    if registrationtimeout:
        search_filter.append(['registrationtimeout', registrationtimeout])

    if sipsrcportrange:
        search_filter.append(['sipsrcportrange', sipsrcportrange])

    if sipdstportrange:
        search_filter.append(['sipdstportrange', sipdstportrange])

    if openregisterpinhole:
        search_filter.append(['openregisterpinhole', openregisterpinhole])

    if opencontactpinhole:
        search_filter.append(['opencontactpinhole', opencontactpinhole])

    if openviapinhole:
        search_filter.append(['openviapinhole', openviapinhole])

    if openrecordroutepinhole:
        search_filter.append(['openrecordroutepinhole', openrecordroutepinhole])

    if siptransportprotocol:
        search_filter.append(['siptransportprotocol', siptransportprotocol])

    if openroutepinhole:
        search_filter.append(['openroutepinhole', openroutepinhole])

    if rport:
        search_filter.append(['rport', rport])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnsipalgprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnsipalgprofile')

    return response


def get_lsnstatic(name=None, transportprotocol=None, subscrip=None, subscrport=None, network6=None, td=None, natip=None,
                  natport=None, destip=None, dsttd=None, nattype=None):
    '''
    Show the running configuration for the lsnstatic config key.

    name(str): Filters results that only match the name field.

    transportprotocol(str): Filters results that only match the transportprotocol field.

    subscrip(str): Filters results that only match the subscrip field.

    subscrport(int): Filters results that only match the subscrport field.

    network6(str): Filters results that only match the network6 field.

    td(int): Filters results that only match the td field.

    natip(str): Filters results that only match the natip field.

    natport(int): Filters results that only match the natport field.

    destip(str): Filters results that only match the destip field.

    dsttd(int): Filters results that only match the dsttd field.

    nattype(str): Filters results that only match the nattype field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsnstatic

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if transportprotocol:
        search_filter.append(['transportprotocol', transportprotocol])

    if subscrip:
        search_filter.append(['subscrip', subscrip])

    if subscrport:
        search_filter.append(['subscrport', subscrport])

    if network6:
        search_filter.append(['network6', network6])

    if td:
        search_filter.append(['td', td])

    if natip:
        search_filter.append(['natip', natip])

    if natport:
        search_filter.append(['natport', natport])

    if destip:
        search_filter.append(['destip', destip])

    if dsttd:
        search_filter.append(['dsttd', dsttd])

    if nattype:
        search_filter.append(['nattype', nattype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsnstatic{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsnstatic')

    return response


def get_lsntransportprofile(transportprofilename=None, transportprotocol=None, sessiontimeout=None, finrsttimeout=None,
                            stuntimeout=None, synidletimeout=None, portquota=None, sessionquota=None,
                            groupsessionlimit=None, portpreserveparity=None, portpreserverange=None, syncheck=None):
    '''
    Show the running configuration for the lsntransportprofile config key.

    transportprofilename(str): Filters results that only match the transportprofilename field.

    transportprotocol(str): Filters results that only match the transportprotocol field.

    sessiontimeout(int): Filters results that only match the sessiontimeout field.

    finrsttimeout(int): Filters results that only match the finrsttimeout field.

    stuntimeout(int): Filters results that only match the stuntimeout field.

    synidletimeout(int): Filters results that only match the synidletimeout field.

    portquota(int): Filters results that only match the portquota field.

    sessionquota(int): Filters results that only match the sessionquota field.

    groupsessionlimit(int): Filters results that only match the groupsessionlimit field.

    portpreserveparity(str): Filters results that only match the portpreserveparity field.

    portpreserverange(str): Filters results that only match the portpreserverange field.

    syncheck(str): Filters results that only match the syncheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.get_lsntransportprofile

    '''

    search_filter = []

    if transportprofilename:
        search_filter.append(['transportprofilename', transportprofilename])

    if transportprotocol:
        search_filter.append(['transportprotocol', transportprotocol])

    if sessiontimeout:
        search_filter.append(['sessiontimeout', sessiontimeout])

    if finrsttimeout:
        search_filter.append(['finrsttimeout', finrsttimeout])

    if stuntimeout:
        search_filter.append(['stuntimeout', stuntimeout])

    if synidletimeout:
        search_filter.append(['synidletimeout', synidletimeout])

    if portquota:
        search_filter.append(['portquota', portquota])

    if sessionquota:
        search_filter.append(['sessionquota', sessionquota])

    if groupsessionlimit:
        search_filter.append(['groupsessionlimit', groupsessionlimit])

    if portpreserveparity:
        search_filter.append(['portpreserveparity', portpreserveparity])

    if portpreserverange:
        search_filter.append(['portpreserverange', portpreserverange])

    if syncheck:
        search_filter.append(['syncheck', syncheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lsntransportprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lsntransportprofile')

    return response


def unset_lsnappsprofile(appsprofilename=None, transportprotocol=None, ippooling=None, mapping=None, filtering=None,
                         tcpproxy=None, td=None, l2info=None, save=False):
    '''
    Unsets values from the lsnappsprofile configuration key.

    appsprofilename(bool): Unsets the appsprofilename value.

    transportprotocol(bool): Unsets the transportprotocol value.

    ippooling(bool): Unsets the ippooling value.

    mapping(bool): Unsets the mapping value.

    filtering(bool): Unsets the filtering value.

    tcpproxy(bool): Unsets the tcpproxy value.

    td(bool): Unsets the td value.

    l2info(bool): Unsets the l2info value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.unset_lsnappsprofile <args>

    '''

    result = {}

    payload = {'lsnappsprofile': {}}

    if appsprofilename:
        payload['lsnappsprofile']['appsprofilename'] = True

    if transportprotocol:
        payload['lsnappsprofile']['transportprotocol'] = True

    if ippooling:
        payload['lsnappsprofile']['ippooling'] = True

    if mapping:
        payload['lsnappsprofile']['mapping'] = True

    if filtering:
        payload['lsnappsprofile']['filtering'] = True

    if tcpproxy:
        payload['lsnappsprofile']['tcpproxy'] = True

    if td:
        payload['lsnappsprofile']['td'] = True

    if l2info:
        payload['lsnappsprofile']['l2info'] = True

    execution = __proxy__['citrixns.post']('config/lsnappsprofile?action=unset', payload)

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


def unset_lsngroup(groupname=None, clientname=None, nattype=None, allocpolicy=None, portblocksize=None, logging=None,
                   sessionlogging=None, sessionsync=None, snmptraplimit=None, ftp=None, pptp=None, sipalg=None,
                   rtspalg=None, ip6profile=None, save=False):
    '''
    Unsets values from the lsngroup configuration key.

    groupname(bool): Unsets the groupname value.

    clientname(bool): Unsets the clientname value.

    nattype(bool): Unsets the nattype value.

    allocpolicy(bool): Unsets the allocpolicy value.

    portblocksize(bool): Unsets the portblocksize value.

    logging(bool): Unsets the logging value.

    sessionlogging(bool): Unsets the sessionlogging value.

    sessionsync(bool): Unsets the sessionsync value.

    snmptraplimit(bool): Unsets the snmptraplimit value.

    ftp(bool): Unsets the ftp value.

    pptp(bool): Unsets the pptp value.

    sipalg(bool): Unsets the sipalg value.

    rtspalg(bool): Unsets the rtspalg value.

    ip6profile(bool): Unsets the ip6profile value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.unset_lsngroup <args>

    '''

    result = {}

    payload = {'lsngroup': {}}

    if groupname:
        payload['lsngroup']['groupname'] = True

    if clientname:
        payload['lsngroup']['clientname'] = True

    if nattype:
        payload['lsngroup']['nattype'] = True

    if allocpolicy:
        payload['lsngroup']['allocpolicy'] = True

    if portblocksize:
        payload['lsngroup']['portblocksize'] = True

    if logging:
        payload['lsngroup']['logging'] = True

    if sessionlogging:
        payload['lsngroup']['sessionlogging'] = True

    if sessionsync:
        payload['lsngroup']['sessionsync'] = True

    if snmptraplimit:
        payload['lsngroup']['snmptraplimit'] = True

    if ftp:
        payload['lsngroup']['ftp'] = True

    if pptp:
        payload['lsngroup']['pptp'] = True

    if sipalg:
        payload['lsngroup']['sipalg'] = True

    if rtspalg:
        payload['lsngroup']['rtspalg'] = True

    if ip6profile:
        payload['lsngroup']['ip6profile'] = True

    execution = __proxy__['citrixns.post']('config/lsngroup?action=unset', payload)

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


def unset_lsnhttphdrlogprofile(httphdrlogprofilename=None, logurl=None, logmethod=None, logversion=None, loghost=None,
                               save=False):
    '''
    Unsets values from the lsnhttphdrlogprofile configuration key.

    httphdrlogprofilename(bool): Unsets the httphdrlogprofilename value.

    logurl(bool): Unsets the logurl value.

    logmethod(bool): Unsets the logmethod value.

    logversion(bool): Unsets the logversion value.

    loghost(bool): Unsets the loghost value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.unset_lsnhttphdrlogprofile <args>

    '''

    result = {}

    payload = {'lsnhttphdrlogprofile': {}}

    if httphdrlogprofilename:
        payload['lsnhttphdrlogprofile']['httphdrlogprofilename'] = True

    if logurl:
        payload['lsnhttphdrlogprofile']['logurl'] = True

    if logmethod:
        payload['lsnhttphdrlogprofile']['logmethod'] = True

    if logversion:
        payload['lsnhttphdrlogprofile']['logversion'] = True

    if loghost:
        payload['lsnhttphdrlogprofile']['loghost'] = True

    execution = __proxy__['citrixns.post']('config/lsnhttphdrlogprofile?action=unset', payload)

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


def unset_lsnlogprofile(logprofilename=None, logsubscrinfo=None, logcompact=None, save=False):
    '''
    Unsets values from the lsnlogprofile configuration key.

    logprofilename(bool): Unsets the logprofilename value.

    logsubscrinfo(bool): Unsets the logsubscrinfo value.

    logcompact(bool): Unsets the logcompact value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.unset_lsnlogprofile <args>

    '''

    result = {}

    payload = {'lsnlogprofile': {}}

    if logprofilename:
        payload['lsnlogprofile']['logprofilename'] = True

    if logsubscrinfo:
        payload['lsnlogprofile']['logsubscrinfo'] = True

    if logcompact:
        payload['lsnlogprofile']['logcompact'] = True

    execution = __proxy__['citrixns.post']('config/lsnlogprofile?action=unset', payload)

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


def unset_lsnparameter(memlimit=None, sessionsync=None, subscrsessionremoval=None, save=False):
    '''
    Unsets values from the lsnparameter configuration key.

    memlimit(bool): Unsets the memlimit value.

    sessionsync(bool): Unsets the sessionsync value.

    subscrsessionremoval(bool): Unsets the subscrsessionremoval value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.unset_lsnparameter <args>

    '''

    result = {}

    payload = {'lsnparameter': {}}

    if memlimit:
        payload['lsnparameter']['memlimit'] = True

    if sessionsync:
        payload['lsnparameter']['sessionsync'] = True

    if subscrsessionremoval:
        payload['lsnparameter']['subscrsessionremoval'] = True

    execution = __proxy__['citrixns.post']('config/lsnparameter?action=unset', payload)

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


def unset_lsnpool(poolname=None, nattype=None, portblockallocation=None, portrealloctimeout=None, maxportrealloctmq=None,
                  save=False):
    '''
    Unsets values from the lsnpool configuration key.

    poolname(bool): Unsets the poolname value.

    nattype(bool): Unsets the nattype value.

    portblockallocation(bool): Unsets the portblockallocation value.

    portrealloctimeout(bool): Unsets the portrealloctimeout value.

    maxportrealloctmq(bool): Unsets the maxportrealloctmq value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.unset_lsnpool <args>

    '''

    result = {}

    payload = {'lsnpool': {}}

    if poolname:
        payload['lsnpool']['poolname'] = True

    if nattype:
        payload['lsnpool']['nattype'] = True

    if portblockallocation:
        payload['lsnpool']['portblockallocation'] = True

    if portrealloctimeout:
        payload['lsnpool']['portrealloctimeout'] = True

    if maxportrealloctmq:
        payload['lsnpool']['maxportrealloctmq'] = True

    execution = __proxy__['citrixns.post']('config/lsnpool?action=unset', payload)

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


def unset_lsnrtspalgprofile(rtspalgprofilename=None, rtspidletimeout=None, rtspportrange=None,
                            rtsptransportprotocol=None, save=False):
    '''
    Unsets values from the lsnrtspalgprofile configuration key.

    rtspalgprofilename(bool): Unsets the rtspalgprofilename value.

    rtspidletimeout(bool): Unsets the rtspidletimeout value.

    rtspportrange(bool): Unsets the rtspportrange value.

    rtsptransportprotocol(bool): Unsets the rtsptransportprotocol value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.unset_lsnrtspalgprofile <args>

    '''

    result = {}

    payload = {'lsnrtspalgprofile': {}}

    if rtspalgprofilename:
        payload['lsnrtspalgprofile']['rtspalgprofilename'] = True

    if rtspidletimeout:
        payload['lsnrtspalgprofile']['rtspidletimeout'] = True

    if rtspportrange:
        payload['lsnrtspalgprofile']['rtspportrange'] = True

    if rtsptransportprotocol:
        payload['lsnrtspalgprofile']['rtsptransportprotocol'] = True

    execution = __proxy__['citrixns.post']('config/lsnrtspalgprofile?action=unset', payload)

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


def unset_lsnsipalgprofile(sipalgprofilename=None, datasessionidletimeout=None, sipsessiontimeout=None,
                           registrationtimeout=None, sipsrcportrange=None, sipdstportrange=None,
                           openregisterpinhole=None, opencontactpinhole=None, openviapinhole=None,
                           openrecordroutepinhole=None, siptransportprotocol=None, openroutepinhole=None, rport=None,
                           save=False):
    '''
    Unsets values from the lsnsipalgprofile configuration key.

    sipalgprofilename(bool): Unsets the sipalgprofilename value.

    datasessionidletimeout(bool): Unsets the datasessionidletimeout value.

    sipsessiontimeout(bool): Unsets the sipsessiontimeout value.

    registrationtimeout(bool): Unsets the registrationtimeout value.

    sipsrcportrange(bool): Unsets the sipsrcportrange value.

    sipdstportrange(bool): Unsets the sipdstportrange value.

    openregisterpinhole(bool): Unsets the openregisterpinhole value.

    opencontactpinhole(bool): Unsets the opencontactpinhole value.

    openviapinhole(bool): Unsets the openviapinhole value.

    openrecordroutepinhole(bool): Unsets the openrecordroutepinhole value.

    siptransportprotocol(bool): Unsets the siptransportprotocol value.

    openroutepinhole(bool): Unsets the openroutepinhole value.

    rport(bool): Unsets the rport value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.unset_lsnsipalgprofile <args>

    '''

    result = {}

    payload = {'lsnsipalgprofile': {}}

    if sipalgprofilename:
        payload['lsnsipalgprofile']['sipalgprofilename'] = True

    if datasessionidletimeout:
        payload['lsnsipalgprofile']['datasessionidletimeout'] = True

    if sipsessiontimeout:
        payload['lsnsipalgprofile']['sipsessiontimeout'] = True

    if registrationtimeout:
        payload['lsnsipalgprofile']['registrationtimeout'] = True

    if sipsrcportrange:
        payload['lsnsipalgprofile']['sipsrcportrange'] = True

    if sipdstportrange:
        payload['lsnsipalgprofile']['sipdstportrange'] = True

    if openregisterpinhole:
        payload['lsnsipalgprofile']['openregisterpinhole'] = True

    if opencontactpinhole:
        payload['lsnsipalgprofile']['opencontactpinhole'] = True

    if openviapinhole:
        payload['lsnsipalgprofile']['openviapinhole'] = True

    if openrecordroutepinhole:
        payload['lsnsipalgprofile']['openrecordroutepinhole'] = True

    if siptransportprotocol:
        payload['lsnsipalgprofile']['siptransportprotocol'] = True

    if openroutepinhole:
        payload['lsnsipalgprofile']['openroutepinhole'] = True

    if rport:
        payload['lsnsipalgprofile']['rport'] = True

    execution = __proxy__['citrixns.post']('config/lsnsipalgprofile?action=unset', payload)

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


def unset_lsntransportprofile(transportprofilename=None, transportprotocol=None, sessiontimeout=None, finrsttimeout=None,
                              stuntimeout=None, synidletimeout=None, portquota=None, sessionquota=None,
                              groupsessionlimit=None, portpreserveparity=None, portpreserverange=None, syncheck=None,
                              save=False):
    '''
    Unsets values from the lsntransportprofile configuration key.

    transportprofilename(bool): Unsets the transportprofilename value.

    transportprotocol(bool): Unsets the transportprotocol value.

    sessiontimeout(bool): Unsets the sessiontimeout value.

    finrsttimeout(bool): Unsets the finrsttimeout value.

    stuntimeout(bool): Unsets the stuntimeout value.

    synidletimeout(bool): Unsets the synidletimeout value.

    portquota(bool): Unsets the portquota value.

    sessionquota(bool): Unsets the sessionquota value.

    groupsessionlimit(bool): Unsets the groupsessionlimit value.

    portpreserveparity(bool): Unsets the portpreserveparity value.

    portpreserverange(bool): Unsets the portpreserverange value.

    syncheck(bool): Unsets the syncheck value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.unset_lsntransportprofile <args>

    '''

    result = {}

    payload = {'lsntransportprofile': {}}

    if transportprofilename:
        payload['lsntransportprofile']['transportprofilename'] = True

    if transportprotocol:
        payload['lsntransportprofile']['transportprotocol'] = True

    if sessiontimeout:
        payload['lsntransportprofile']['sessiontimeout'] = True

    if finrsttimeout:
        payload['lsntransportprofile']['finrsttimeout'] = True

    if stuntimeout:
        payload['lsntransportprofile']['stuntimeout'] = True

    if synidletimeout:
        payload['lsntransportprofile']['synidletimeout'] = True

    if portquota:
        payload['lsntransportprofile']['portquota'] = True

    if sessionquota:
        payload['lsntransportprofile']['sessionquota'] = True

    if groupsessionlimit:
        payload['lsntransportprofile']['groupsessionlimit'] = True

    if portpreserveparity:
        payload['lsntransportprofile']['portpreserveparity'] = True

    if portpreserverange:
        payload['lsntransportprofile']['portpreserverange'] = True

    if syncheck:
        payload['lsntransportprofile']['syncheck'] = True

    execution = __proxy__['citrixns.post']('config/lsntransportprofile?action=unset', payload)

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


def update_lsnappsprofile(appsprofilename=None, transportprotocol=None, ippooling=None, mapping=None, filtering=None,
                          tcpproxy=None, td=None, l2info=None, save=False):
    '''
    Update the running configuration for the lsnappsprofile config key.

    appsprofilename(str): Name for the LSN application profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after the LSN application profile is created. The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "lsn application profile1" or lsn application profile1).
        Minimum length = 1 Maximum length = 127

    transportprotocol(str): Name of the protocol for which the parameters of this LSN application profile applies. Possible
        values = TCP, UDP, ICMP

    ippooling(str): NAT IP address allocation options for sessions associated with the same subscriber.  Available options
        function as follows: * Paired - The NetScaler ADC allocates the same NAT IP address for all sessions associated
        with the same subscriber. When all the ports of a NAT IP address are used in LSN sessions (for same or multiple
        subscribers), the NetScaler ADC drops any new connection from the subscriber. * Random - The NetScaler ADC
        allocates random NAT IP addresses, from the pool, for different sessions associated with the same subscriber.
        This parameter is applicable to dynamic NAT allocation only. Default value: RANDOM Possible values = PAIRED,
        RANDOM

    mapping(str): Type of LSN mapping to apply to subsequent packets originating from the same subscriber IP address and
        port.  Consider an example of an LSN mapping that includes the mapping of the subscriber IP:port (X:x), NAT
        IP:port (N:n), and external host IP:port (Y:y).  Available options function as follows:   * ENDPOINT-INDEPENDENT
        - Reuse the LSN mapping for subsequent packets sent from the same subscriber IP address and port (X:x) to any
        external IP address and port.   * ADDRESS-DEPENDENT - Reuse the LSN mapping for subsequent packets sent from the
        same subscriber IP address and port (X:x) to the same external IP address (Y), regardless of the external port.
        * ADDRESS-PORT-DEPENDENT - Reuse the LSN mapping for subsequent packets sent from the same internal IP address
        and port (X:x) to the same external IP address and port (Y:y) while the mapping is still active. Default value:
        ADDRESS-PORT-DEPENDENT Possible values = ENDPOINT-INDEPENDENT, ADDRESS-DEPENDENT, ADDRESS-PORT-DEPENDENT

    filtering(str): Type of filter to apply to packets originating from external hosts.  Consider an example of an LSN
        mapping that includes the mapping of subscriber IP:port (X:x), NAT IP:port (N:n), and external host IP:port
        (Y:y).  Available options function as follows: * ENDPOINT INDEPENDENT - Filters out only packets not destined to
        the subscriber IP address and port X:x, regardless of the external host IP address and port source (Z:z). The
        NetScaler ADC forwards any packets destined to X:x. In other words, sending packets from the subscriber to any
        external IP address is sufficient to allow packets from any external hosts to the subscriber.  * ADDRESS
        DEPENDENT - Filters out packets not destined to subscriber IP address and port X:x. In addition, the ADC filters
        out packets from Y:y destined for the subscriber (X:x) if the client has not previously sent packets to Y:anyport
        (external port independent). In other words, receiving packets from a specific external host requires that the
        subscriber first send packets to that specific external hosts IP address.  * ADDRESS PORT DEPENDENT (the default)
        - Filters out packets not destined to subscriber IP address and port (X:x). In addition, the NetScaler ADC
        filters out packets from Y:y destined for the subscriber (X:x) if the subscriber has not previously sent packets
        to Y:y. In other words, receiving packets from a specific external host requires that the subscriber first send
        packets first to that external IP address and port. Default value: ADDRESS-PORT-DEPENDENT Possible values =
        ENDPOINT-INDEPENDENT, ADDRESS-DEPENDENT, ADDRESS-PORT-DEPENDENT

    tcpproxy(str): Enable TCP proxy, which enables the NetScaler appliance to optimize the TCP traffic by using Layer 4
        features. Default value: DISABLED Possible values = ENABLED, DISABLED

    td(int): ID of the traffic domain through which the NetScaler ADC sends the outbound traffic after performing LSN.   If
        you do not specify an ID, the ADC sends the outbound traffic through the default traffic domain, which has an ID
        of 0. Default value: 65535

    l2info(str): Enable l2info by creating natpcbs for LSN, which enables the NetScaler appliance to use L2CONN/MBF with LSN.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.update_lsnappsprofile <args>

    '''

    result = {}

    payload = {'lsnappsprofile': {}}

    if appsprofilename:
        payload['lsnappsprofile']['appsprofilename'] = appsprofilename

    if transportprotocol:
        payload['lsnappsprofile']['transportprotocol'] = transportprotocol

    if ippooling:
        payload['lsnappsprofile']['ippooling'] = ippooling

    if mapping:
        payload['lsnappsprofile']['mapping'] = mapping

    if filtering:
        payload['lsnappsprofile']['filtering'] = filtering

    if tcpproxy:
        payload['lsnappsprofile']['tcpproxy'] = tcpproxy

    if td:
        payload['lsnappsprofile']['td'] = td

    if l2info:
        payload['lsnappsprofile']['l2info'] = l2info

    execution = __proxy__['citrixns.put']('config/lsnappsprofile', payload)

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


def update_lsngroup(groupname=None, clientname=None, nattype=None, allocpolicy=None, portblocksize=None, logging=None,
                    sessionlogging=None, sessionsync=None, snmptraplimit=None, ftp=None, pptp=None, sipalg=None,
                    rtspalg=None, ip6profile=None, save=False):
    '''
    Update the running configuration for the lsngroup config key.

    groupname(str): Name for the LSN group. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the LSN group is created. The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "lsn group1" or lsn group1). Minimum length = 1 Maximum length = 127

    clientname(str): Name of the LSN client entity to be associated with the LSN group. You can associate only one LSN client
        entity with an LSN group.You cannot remove this association or replace with another LSN client entity once the
        LSN group is created.

    nattype(str): Type of NAT IP address and port allocation (from the bound LSN pools) for subscribers:  Available options
        function as follows:  * Deterministic - Allocate a NAT IP address and a block of ports to each subscriber (of the
        LSN client bound to the LSN group). The NetScaler ADC sequentially allocates NAT resources to these subscribers.
        The NetScaler ADC assigns the first block of ports (block size determined by the port block size parameter of the
        LSN group) on the beginning NAT IP address to the beginning subscriber IP address. The next range of ports is
        assigned to the next subscriber, and so on, until the NAT address does not have enough ports for the next
        subscriber. In this case, the first port block on the next NAT address is used for the subscriber, and so on.
        Because each subscriber now receives a deterministic NAT IP address and a block of ports, a subscriber can be
        identified without any need for logging. For a connection, a subscriber can be identified based only on the NAT
        IP address and port, and the destination IP address and port. The maximum number of LSN subscribers allowed,
        globally, is 1 million.   * Dynamic - Allocate a random NAT IP address and a port from the LSN NAT pool for a
        subscribers connection. If port block allocation is enabled (in LSN pool) and a port block size is specified (in
        the LSN group), the NetScaler ADC allocates a random NAT IP address and a block of ports for a subscriber when it
        initiates a connection for the first time. The ADC allocates this NAT IP address and a port (from the allocated
        block of ports) for different connections from this subscriber. If all the ports are allocated (for different
        subscribers connections) from the subscribers allocated port block, the ADC allocates a new random port block for
        the subscriber. Default value: DYNAMIC Possible values = DYNAMIC, DETERMINISTIC

    allocpolicy(str): NAT IP and PORT block allocation policy for Deterministic NAT. Supported Policies are, 1:
        PORTS(Default): Port blocks from single NATIP will be allocated to LSN subscribers sequentially. After all blocks
        are exhausted, port blocks from next NATIP will be allocated and so on. 2: IPADDRS: One port block from each
        NATIP will be allocated and once all the NATIPs are over second port block from each NATIP will be allocated and
        so on. To understand better if we assume port blocks of all NAT IPs as two dimensional array, PORTS policy
        follows "row major order" and IPADDRS policy follows "column major order" while allocating port blocks. Example:
        Client IPs: 2.2.2.1, 2.2.2.2 and 2.2.2.3 NAT IPs and PORT Blocks:  4.4.4.1:PB1, PB2, PB3,., PBn 4.4.4.2: PB1,
        PB2, PB3,., PBn PORTS Policy:  2.2.2.1 =;gt; 4.4.4.1:PB1 2.2.2.2 =;gt; 4.4.4.1:PB2 2.2.2.3 =;gt; 4.4.4.1:PB3
        IPADDRS Policy: 2.2.2.1 =;gt; 4.4.4.1:PB1 2.2.2.2 =;gt; 4.4.4.2:PB1 2.2.2.3 =;gt; 4.4.4.1:PB2. Default value:
        PORTS Possible values = PORTS, IPADDRS

    portblocksize(int): Size of the NAT port block to be allocated for each subscriber.  To set this parameter for Dynamic
        NAT, you must enable the port block allocation parameter in the bound LSN pool. For Deterministic NAT, the port
        block allocation parameter is always enabled, and you cannot disable it.  In Dynamic NAT, the NetScaler ADC
        allocates a random NAT port block, from the available NAT port pool of an NAT IP address, for each subscriber.
        For a subscriber, if all the ports are allocated from the subscribers allocated port block, the ADC allocates a
        new random port block for the subscriber.  The default port block size is 256 for Deterministic NAT, and 0 for
        Dynamic NAT. Default value: 0 Minimum value = 256 Maximum value = 65536

    logging(str): Log mapping entries and sessions created or deleted for this LSN group. The NetScaler ADC logs LSN sessions
        for this LSN group only when both logging and session logging parameters are enabled.  The ADC uses its existing
        syslog and audit log framework to log LSN information. You must enable global level LSN logging by enabling the
        LSN parameter in the related NSLOG action and SYLOG action entities. When the Logging parameter is enabled, the
        NetScaler ADC generates log messages related to LSN mappings and LSN sessions of this LSN group. The ADC then
        sends these log messages to servers associated with the NSLOG action and SYSLOG actions entities.   A log message
        for an LSN mapping entry consists of the following information: * NSIP address of the NetScaler ADC * Time stamp
        * Entry type (MAPPING or SESSION) * Whether the LSN mapping entry is created or deleted * Subscribers IP address,
        port, and traffic domain ID * NAT IP address and port * Protocol name * Destination IP address, port, and traffic
        domain ID might be present, depending on the following conditions: ** Destination IP address and port are not
        logged for Endpoint-Independent mapping ** Only Destination IP address (and not port) is logged for
        Address-Dependent mapping ** Destination IP address and port are logged for Address-Port-Dependent mapping.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    sessionlogging(str): Log sessions created or deleted for the LSN group. The NetScaler ADC logs LSN sessions for this LSN
        group only when both logging and session logging parameters are enabled.  A log message for an LSN session
        consists of the following information: * NSIP address of the NetScaler ADC * Time stamp * Entry type (MAPPING or
        SESSION) * Whether the LSN session is created or removed * Subscribers IP address, port, and traffic domain ID *
        NAT IP address and port * Protocol name * Destination IP address, port, and traffic domain ID. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    sessionsync(str): In a high availability (HA) deployment, synchronize information of all LSN sessions related to this LSN
        group with the secondary node. After a failover, established TCP connections and UDP packet flows are kept active
        and resumed on the secondary node (new primary).  For this setting to work, you must enable the global session
        synchronization parameter. Default value: ENABLED Possible values = ENABLED, DISABLED

    snmptraplimit(int): Maximum number of SNMP Trap messages that can be generated for the LSN group in one minute. Default
        value: 100 Minimum value = 0 Maximum value = 10000

    ftp(str): Enable Application Layer Gateway (ALG) for the FTP protocol. For some application-layer protocols, the IP
        addresses and protocol port numbers are usually communicated in the packets payload. When acting as an ALG, the
        NetScaler changes the packets payload to ensure that the protocol continues to work over LSN.   Note: The
        NetScaler ADC also includes ALG for ICMP and TFTP protocols. ALG for the ICMP protocol is enabled by default, and
        there is no provision to disable it. ALG for the TFTP protocol is disabled by default. ALG is enabled
        automatically for an LSN group when you bind a UDP LSN application profile, with endpoint-independent-mapping,
        endpoint-independent filtering, and destination port as 69 (well-known port for TFTP), to the LSN group. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    pptp(str): Enable the PPTP Application Layer Gateway. Default value: DISABLED Possible values = ENABLED, DISABLED

    sipalg(str): Enable the SIP ALG. Default value: DISABLED Possible values = ENABLED, DISABLED

    rtspalg(str): Enable the RTSP ALG. Default value: DISABLED Possible values = ENABLED, DISABLED

    ip6profile(str): Name of the LSN ip6 profile to associate with the specified LSN group. An ip6 profile can be associated
        with a group only during group creation.  By default, no LSN ip6 profile is associated with an LSN group during
        its creation. Only one ip6profile can be associated with a group. Minimum length = 1 Maximum length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.update_lsngroup <args>

    '''

    result = {}

    payload = {'lsngroup': {}}

    if groupname:
        payload['lsngroup']['groupname'] = groupname

    if clientname:
        payload['lsngroup']['clientname'] = clientname

    if nattype:
        payload['lsngroup']['nattype'] = nattype

    if allocpolicy:
        payload['lsngroup']['allocpolicy'] = allocpolicy

    if portblocksize:
        payload['lsngroup']['portblocksize'] = portblocksize

    if logging:
        payload['lsngroup']['logging'] = logging

    if sessionlogging:
        payload['lsngroup']['sessionlogging'] = sessionlogging

    if sessionsync:
        payload['lsngroup']['sessionsync'] = sessionsync

    if snmptraplimit:
        payload['lsngroup']['snmptraplimit'] = snmptraplimit

    if ftp:
        payload['lsngroup']['ftp'] = ftp

    if pptp:
        payload['lsngroup']['pptp'] = pptp

    if sipalg:
        payload['lsngroup']['sipalg'] = sipalg

    if rtspalg:
        payload['lsngroup']['rtspalg'] = rtspalg

    if ip6profile:
        payload['lsngroup']['ip6profile'] = ip6profile

    execution = __proxy__['citrixns.put']('config/lsngroup', payload)

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


def update_lsnhttphdrlogprofile(httphdrlogprofilename=None, logurl=None, logmethod=None, logversion=None, loghost=None,
                                save=False):
    '''
    Update the running configuration for the lsnhttphdrlogprofile config key.

    httphdrlogprofilename(str): The name of the HTTP header logging Profile. Minimum length = 1 Maximum length = 127

    logurl(str): URL information is logged if option is enabled. Default value: ENABLED Possible values = ENABLED, DISABLED

    logmethod(str): HTTP method information is logged if option is enabled. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    logversion(str): Version information is logged if option is enabled. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    loghost(str): Host information is logged if option is enabled. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.update_lsnhttphdrlogprofile <args>

    '''

    result = {}

    payload = {'lsnhttphdrlogprofile': {}}

    if httphdrlogprofilename:
        payload['lsnhttphdrlogprofile']['httphdrlogprofilename'] = httphdrlogprofilename

    if logurl:
        payload['lsnhttphdrlogprofile']['logurl'] = logurl

    if logmethod:
        payload['lsnhttphdrlogprofile']['logmethod'] = logmethod

    if logversion:
        payload['lsnhttphdrlogprofile']['logversion'] = logversion

    if loghost:
        payload['lsnhttphdrlogprofile']['loghost'] = loghost

    execution = __proxy__['citrixns.put']('config/lsnhttphdrlogprofile', payload)

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


def update_lsnlogprofile(logprofilename=None, logsubscrinfo=None, logcompact=None, save=False):
    '''
    Update the running configuration for the lsnlogprofile config key.

    logprofilename(str): The name of the logging Profile. Minimum length = 1 Maximum length = 127

    logsubscrinfo(str): Subscriber ID information is logged if option is enabled. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    logcompact(str): Logs in Compact Logging format if option is enabled. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.update_lsnlogprofile <args>

    '''

    result = {}

    payload = {'lsnlogprofile': {}}

    if logprofilename:
        payload['lsnlogprofile']['logprofilename'] = logprofilename

    if logsubscrinfo:
        payload['lsnlogprofile']['logsubscrinfo'] = logsubscrinfo

    if logcompact:
        payload['lsnlogprofile']['logcompact'] = logcompact

    execution = __proxy__['citrixns.put']('config/lsnlogprofile', payload)

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


def update_lsnparameter(memlimit=None, sessionsync=None, subscrsessionremoval=None, save=False):
    '''
    Update the running configuration for the lsnparameter config key.

    memlimit(int): Amount of NetScaler memory to reserve for the LSN feature, in multiples of 2MB.  Note: If you later reduce
        the value of this parameter, the amount of active memory is not reduced. Changing the configured memory limit can
        only increase the amount of active memory. This command is deprecated, use set extendedmemoryparam -memlimit
        instead.

    sessionsync(str): Synchronize all LSN sessions with the secondary node in a high availability (HA) deployment (global
        synchronization). After a failover, established TCP connections and UDP packet flows are kept active and resumed
        on the secondary node (new primary).  The global session synchronization parameter and session synchronization
        parameters (group level) of all LSN groups are enabled by default.  For a group, when both the global level and
        the group level LSN session synchronization parameters are enabled, the primary node synchronizes information of
        all LSN sessions related to this LSN group with the secondary node. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    subscrsessionremoval(str): LSN global setting for controlling subscriber aware session removal, when this is enabled,
        when ever the subscriber info is deleted from subscriber database, sessions corresponding to that subscriber will
        be removed. if this setting is disabled, subscriber sessions will be timed out as per the idle time out settings.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.update_lsnparameter <args>

    '''

    result = {}

    payload = {'lsnparameter': {}}

    if memlimit:
        payload['lsnparameter']['memlimit'] = memlimit

    if sessionsync:
        payload['lsnparameter']['sessionsync'] = sessionsync

    if subscrsessionremoval:
        payload['lsnparameter']['subscrsessionremoval'] = subscrsessionremoval

    execution = __proxy__['citrixns.put']('config/lsnparameter', payload)

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


def update_lsnpool(poolname=None, nattype=None, portblockallocation=None, portrealloctimeout=None,
                   maxportrealloctmq=None, save=False):
    '''
    Update the running configuration for the lsnpool config key.

    poolname(str): Name for the LSN pool. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the LSN pool is created. The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "lsn pool1" or lsn pool1). Minimum length = 1 Maximum length = 127

    nattype(str): Type of NAT IP address and port allocation (from the LSN pools bound to an LSN group) for subscribers (of
        the LSN client entity bound to the LSN group):  Available options function as follows:  * Deterministic -
        Allocate a NAT IP address and a block of ports to each subscriber (of the LSN client bound to the LSN group). The
        NetScaler ADC sequentially allocates NAT resources to these subscribers. The NetScaler ADC assigns the first
        block of ports (block size determined by the port block size parameter of the LSN group) on the beginning NAT IP
        address to the beginning subscriber IP address. The next range of ports is assigned to the next subscriber, and
        so on, until the NAT address does not have enough ports for the next subscriber. In this case, the first port
        block on the next NAT address is used for the subscriber, and so on. Because each subscriber now receives a
        deterministic NAT IP address and a block of ports, a subscriber can be identified without any need for logging.
        For a connection, a subscriber can be identified based only on the NAT IP address and port, and the destination
        IP address and port.   * Dynamic - Allocate a random NAT IP address and a port from the LSN NAT pool for a
        subscribers connection. If port block allocation is enabled (in LSN pool) and a port block size is specified (in
        the LSN group), the NetScaler ADC allocates a random NAT IP address and a block of ports for a subscriber when it
        initiates a connection for the first time. The ADC allocates this NAT IP address and a port (from the allocated
        block of ports) for different connections from this subscriber. If all the ports are allocated (for different
        subscribers connections) from the subscribers allocated port block, the ADC allocates a new random port block for
        the subscriber. Only LSN Pools and LSN groups with the same NAT type settings can be bound together. Multiples
        LSN pools can be bound to an LSN group. A maximum of 16 LSN pools can be bound to an LSN group. . Default value:
        DYNAMIC Possible values = DYNAMIC, DETERMINISTIC

    portblockallocation(str): Allocate a random NAT port block, from the available NAT port pool of an NAT IP address, for
        each subscriber when the NAT allocation is set as Dynamic NAT. For any connection initiated from a subscriber,
        the NetScaler ADC allocates a NAT port from the subscribers allocated NAT port block to create the LSN session.
        You must set the port block size in the bound LSN group. For a subscriber, if all the ports are allocated from
        the subscribers allocated port block, the NetScaler ADC allocates a new random port block for the subscriber.
        For Deterministic NAT, this parameter is enabled by default, and you cannot disable it. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    portrealloctimeout(int): The waiting time, in seconds, between deallocating LSN NAT ports (when an LSN mapping is
        removed) and reallocating them for a new LSN session. This parameter is necessary in order to prevent collisions
        between old and new mappings and sessions. It ensures that all established sessions are broken instead of
        redirected to a different subscriber. This is not applicable for ports used in: * Deterministic NAT *
        Address-Dependent filtering and Address-Port-Dependent filtering * Dynamic NAT with port block allocation In
        these cases, ports are immediately reallocated. Default value: 0 Minimum value = 0 Maximum value = 600

    maxportrealloctmq(int): Maximum number of ports for which the port reallocation timeout applies for each NAT IP address.
        In other words, the maximum deallocated-port queue size for which the reallocation timeout applies for each NAT
        IP address.  When the queue size is full, the next port deallocated is reallocated immediately for a new LSN
        session. Default value: 65536 Minimum value = 0 Maximum value = 65536

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.update_lsnpool <args>

    '''

    result = {}

    payload = {'lsnpool': {}}

    if poolname:
        payload['lsnpool']['poolname'] = poolname

    if nattype:
        payload['lsnpool']['nattype'] = nattype

    if portblockallocation:
        payload['lsnpool']['portblockallocation'] = portblockallocation

    if portrealloctimeout:
        payload['lsnpool']['portrealloctimeout'] = portrealloctimeout

    if maxportrealloctmq:
        payload['lsnpool']['maxportrealloctmq'] = maxportrealloctmq

    execution = __proxy__['citrixns.put']('config/lsnpool', payload)

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


def update_lsnrtspalgprofile(rtspalgprofilename=None, rtspidletimeout=None, rtspportrange=None,
                             rtsptransportprotocol=None, save=False):
    '''
    Update the running configuration for the lsnrtspalgprofile config key.

    rtspalgprofilename(str): The name of the RTSPALG Profile. Minimum length = 1 Maximum length = 127

    rtspidletimeout(int): Idle timeout for the rtsp sessions in seconds. Default value: 120

    rtspportrange(str): port for the RTSP.

    rtsptransportprotocol(str): RTSP ALG Profile transport protocol type. Default value: TCP Possible values = TCP, UDP

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.update_lsnrtspalgprofile <args>

    '''

    result = {}

    payload = {'lsnrtspalgprofile': {}}

    if rtspalgprofilename:
        payload['lsnrtspalgprofile']['rtspalgprofilename'] = rtspalgprofilename

    if rtspidletimeout:
        payload['lsnrtspalgprofile']['rtspidletimeout'] = rtspidletimeout

    if rtspportrange:
        payload['lsnrtspalgprofile']['rtspportrange'] = rtspportrange

    if rtsptransportprotocol:
        payload['lsnrtspalgprofile']['rtsptransportprotocol'] = rtsptransportprotocol

    execution = __proxy__['citrixns.put']('config/lsnrtspalgprofile', payload)

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


def update_lsnsipalgprofile(sipalgprofilename=None, datasessionidletimeout=None, sipsessiontimeout=None,
                            registrationtimeout=None, sipsrcportrange=None, sipdstportrange=None,
                            openregisterpinhole=None, opencontactpinhole=None, openviapinhole=None,
                            openrecordroutepinhole=None, siptransportprotocol=None, openroutepinhole=None, rport=None,
                            save=False):
    '''
    Update the running configuration for the lsnsipalgprofile config key.

    sipalgprofilename(str): The name of the SIPALG Profile. Minimum length = 1 Maximum length = 127

    datasessionidletimeout(int): Idle timeout for the data channel sessions in seconds. Default value: 120

    sipsessiontimeout(int): SIP control channel session timeout in seconds. Default value: 600

    registrationtimeout(int): SIP registration timeout in seconds. Default value: 60

    sipsrcportrange(str): Source port range for SIP_UDP and SIP_TCP.

    sipdstportrange(str): Destination port range for SIP_UDP and SIP_TCP.

    openregisterpinhole(str): ENABLE/DISABLE RegisterPinhole creation. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    opencontactpinhole(str): ENABLE/DISABLE ContactPinhole creation. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    openviapinhole(str): ENABLE/DISABLE ViaPinhole creation. Default value: ENABLED Possible values = ENABLED, DISABLED

    openrecordroutepinhole(str): ENABLE/DISABLE RecordRoutePinhole creation. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    siptransportprotocol(str): SIP ALG Profile transport protocol type. Possible values = TCP, UDP

    openroutepinhole(str): ENABLE/DISABLE RoutePinhole creation. Default value: ENABLED Possible values = ENABLED, DISABLED

    rport(str): ENABLE/DISABLE rport. Default value: ENABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.update_lsnsipalgprofile <args>

    '''

    result = {}

    payload = {'lsnsipalgprofile': {}}

    if sipalgprofilename:
        payload['lsnsipalgprofile']['sipalgprofilename'] = sipalgprofilename

    if datasessionidletimeout:
        payload['lsnsipalgprofile']['datasessionidletimeout'] = datasessionidletimeout

    if sipsessiontimeout:
        payload['lsnsipalgprofile']['sipsessiontimeout'] = sipsessiontimeout

    if registrationtimeout:
        payload['lsnsipalgprofile']['registrationtimeout'] = registrationtimeout

    if sipsrcportrange:
        payload['lsnsipalgprofile']['sipsrcportrange'] = sipsrcportrange

    if sipdstportrange:
        payload['lsnsipalgprofile']['sipdstportrange'] = sipdstportrange

    if openregisterpinhole:
        payload['lsnsipalgprofile']['openregisterpinhole'] = openregisterpinhole

    if opencontactpinhole:
        payload['lsnsipalgprofile']['opencontactpinhole'] = opencontactpinhole

    if openviapinhole:
        payload['lsnsipalgprofile']['openviapinhole'] = openviapinhole

    if openrecordroutepinhole:
        payload['lsnsipalgprofile']['openrecordroutepinhole'] = openrecordroutepinhole

    if siptransportprotocol:
        payload['lsnsipalgprofile']['siptransportprotocol'] = siptransportprotocol

    if openroutepinhole:
        payload['lsnsipalgprofile']['openroutepinhole'] = openroutepinhole

    if rport:
        payload['lsnsipalgprofile']['rport'] = rport

    execution = __proxy__['citrixns.put']('config/lsnsipalgprofile', payload)

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


def update_lsntransportprofile(transportprofilename=None, transportprotocol=None, sessiontimeout=None,
                               finrsttimeout=None, stuntimeout=None, synidletimeout=None, portquota=None,
                               sessionquota=None, groupsessionlimit=None, portpreserveparity=None,
                               portpreserverange=None, syncheck=None, save=False):
    '''
    Update the running configuration for the lsntransportprofile config key.

    transportprofilename(str): Name for the LSN transport profile. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after the LSN transport profile is created. The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "lsn transport profile1" or lsn transport profile1).
        Minimum length = 1 Maximum length = 127

    transportprotocol(str): Protocol for which to set the LSN transport profile parameters. Possible values = TCP, UDP, ICMP

    sessiontimeout(int): Timeout, in seconds, for an idle LSN session. If an LSN session is idle for a time that exceeds this
        value, the NetScaler ADC removes the session.  This timeout does not apply for a TCP LSN session when a FIN or
        RST message is received from either of the endpoints. . Default value: 120 Minimum value = 60

    finrsttimeout(int): Timeout, in seconds, for a TCP LSN session after a FIN or RST message is received from one of the
        endpoints.  If a TCP LSN session is idle (after the NetScaler ADC receives a FIN or RST message) for a time that
        exceeds this value, the NetScaler ADC removes the session.  Since the LSN feature of the NetScaler ADC does not
        maintain state information of any TCP LSN sessions, this timeout accommodates the transmission of the FIN or RST,
        and ACK messages from the other endpoint so that both endpoints can properly close the connection. Default value:
        30

    stuntimeout(int): STUN protocol timeout. Default value: 600 Minimum value = 120 Maximum value = 1200

    synidletimeout(int): SYN Idle timeout. Default value: 60 Minimum value = 30 Maximum value = 120

    portquota(int): Maximum number of LSN NAT ports to be used at a time by each subscriber for the specified protocol. For
        example, each subscriber can be limited to a maximum of 500 TCP NAT ports. When the LSN NAT mappings for a
        subscriber reach the limit, the NetScaler ADC does not allocate additional NAT ports for that subscriber. Default
        value: 0 Minimum value = 0 Maximum value = 65535

    sessionquota(int): Maximum number of concurrent LSN sessions allowed for each subscriber for the specified protocol.
        When the number of LSN sessions reaches the limit for a subscriber, the NetScaler ADC does not allow the
        subscriber to open additional sessions. Default value: 0 Minimum value = 0 Maximum value = 65535

    groupsessionlimit(int): Maximum number of concurrent LSN sessions(for the specified protocol) allowed for all subscriber
        of a group to which this profile has bound. This limit will get split across the netscalers packet engines and
        rounded down. When the number of LSN sessions reaches the limit for a group in packet engine, the NetScaler ADC
        does not allow the subscriber of that group to open additional sessions through that packet engine. Default
        value: 0

    portpreserveparity(str): Enable port parity between a subscriber port and its mapped LSN NAT port. For example, if a
        subscriber initiates a connection from an odd numbered port, the NetScaler ADC allocates an odd numbered LSN NAT
        port for this connection.  You must set this parameter for proper functioning of protocols that require the
        source port to be even or odd numbered, for example, in peer-to-peer applications that use RTP or RTCP protocol.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    portpreserverange(str): If a subscriber initiates a connection from a well-known port (0-1023), allocate a NAT port from
        the well-known port range (0-1023) for this connection. For example, if a subscriber initiates a connection from
        port 80, the NetScaler ADC can allocate port 100 as the NAT port for this connection.  This parameter applies to
        dynamic NAT without port block allocation. It also applies to Deterministic NAT if the range of ports allocated
        includes well-known ports.  When all the well-known ports of all the available NAT IP addresses are used in
        different subscribers connections (LSN sessions), and a subscriber initiates a connection from a well-known port,
        the NetScaler ADC drops this connection. Default value: DISABLED Possible values = ENABLED, DISABLED

    syncheck(str): Silently drop any non-SYN packets for connections for which there is no LSN-NAT session present on the
        NetScaler ADC.   If you disable this parameter, the NetScaler ADC accepts any non-SYN packets and creates a new
        LSN session entry for this connection.   Following are some reasons for the NetScaler ADC to receive such
        packets:  * LSN session for a connection existed but the NetScaler ADC removed this session because the LSN
        session was idle for a time that exceeded the configured session timeout. * Such packets can be a part of a DoS
        attack. Default value: ENABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lsn.update_lsntransportprofile <args>

    '''

    result = {}

    payload = {'lsntransportprofile': {}}

    if transportprofilename:
        payload['lsntransportprofile']['transportprofilename'] = transportprofilename

    if transportprotocol:
        payload['lsntransportprofile']['transportprotocol'] = transportprotocol

    if sessiontimeout:
        payload['lsntransportprofile']['sessiontimeout'] = sessiontimeout

    if finrsttimeout:
        payload['lsntransportprofile']['finrsttimeout'] = finrsttimeout

    if stuntimeout:
        payload['lsntransportprofile']['stuntimeout'] = stuntimeout

    if synidletimeout:
        payload['lsntransportprofile']['synidletimeout'] = synidletimeout

    if portquota:
        payload['lsntransportprofile']['portquota'] = portquota

    if sessionquota:
        payload['lsntransportprofile']['sessionquota'] = sessionquota

    if groupsessionlimit:
        payload['lsntransportprofile']['groupsessionlimit'] = groupsessionlimit

    if portpreserveparity:
        payload['lsntransportprofile']['portpreserveparity'] = portpreserveparity

    if portpreserverange:
        payload['lsntransportprofile']['portpreserverange'] = portpreserverange

    if syncheck:
        payload['lsntransportprofile']['syncheck'] = syncheck

    execution = __proxy__['citrixns.put']('config/lsntransportprofile', payload)

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
