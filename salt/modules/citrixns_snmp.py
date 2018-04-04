# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the snmp key.

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

__virtualname__ = 'snmp'


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

    return False, 'The snmp execution module can only be loaded for citrixns proxy minions.'


def add_snmpcommunity(communityname=None, permissions=None, save=False):
    '''
    Add a new snmpcommunity to the running configuration.

    communityname(str): The SNMP community string. Can consist of 1 to 31 characters that include uppercase and lowercase
        letters,numbers and special characters.  The following requirement applies only to the NetScaler CLI: If the
        string includes one or more spaces, enclose the name in double or single quotation marks (for example, "my
        string" or my string). Minimum length = 1

    permissions(str): The SNMP V1 or V2 query-type privilege that you want to associate with this SNMP community. Possible
        values = GET, GET_NEXT, GET_BULK, SET, ALL

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.add_snmpcommunity <args>

    '''

    result = {}

    payload = {'snmpcommunity': {}}

    if communityname:
        payload['snmpcommunity']['communityname'] = communityname

    if permissions:
        payload['snmpcommunity']['permissions'] = permissions

    execution = __proxy__['citrixns.post']('config/snmpcommunity', payload)

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


def add_snmpgroup(name=None, securitylevel=None, readviewname=None, save=False):
    '''
    Add a new snmpgroup to the running configuration.

    name(str): Name for the SNMPv3 group. Can consist of 1 to 31 characters that include uppercase and lowercase letters,
        numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore
        (_) characters. You should choose a name that helps identify the SNMPv3 group.    The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose it in double or single
        quotation marks (for example, "my name" or my name). Minimum length = 1

    securitylevel(str): Security level required for communication between the NetScaler appliance and the SNMPv3 users who
        belong to the group. Specify one of the following options: noAuthNoPriv. Require neither authentication nor
        encryption. authNoPriv. Require authentication but no encryption. authPriv. Require authentication and
        encryption. Note: If you specify authentication, you must specify an encryption algorithm when you assign an
        SNMPv3 user to the group. If you also specify encryption, you must assign both an authentication and an
        encryption algorithm for each group member. Possible values = noAuthNoPriv, authNoPriv, authPriv

    readviewname(str): Name of the configured SNMPv3 view that you want to bind to this SNMPv3 group. An SNMPv3 user bound to
        this group can access the subtrees that are bound to this SNMPv3 view as type INCLUDED, but cannot access the
        ones that are type EXCLUDED. If the NetScaler appliance has multiple SNMPv3 view entries with the same name, all
        such entries are associated with the SNMPv3 group. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.add_snmpgroup <args>

    '''

    result = {}

    payload = {'snmpgroup': {}}

    if name:
        payload['snmpgroup']['name'] = name

    if securitylevel:
        payload['snmpgroup']['securitylevel'] = securitylevel

    if readviewname:
        payload['snmpgroup']['readviewname'] = readviewname

    execution = __proxy__['citrixns.post']('config/snmpgroup', payload)

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


def add_snmpmanager(ipaddress=None, netmask=None, domainresolveretry=None, save=False):
    '''
    Add a new snmpmanager to the running configuration.

    ipaddress(str): IP address of the SNMP manager. Can be an IPv4 or IPv6 address. You can instead specify an IPv4 network
        address or IPv6 network prefix if you want the NetScaler appliance to respond to SNMP queries from any device on
        the specified network. Alternatively, instead of an IPv4 address, you can specify a host name that has been
        assigned to an SNMP manager. If you do so, you must add a DNS name server that resolves the host name of the SNMP
        manager to its IP address.  Note: The NetScaler appliance does not support host names for SNMP managers that have
        IPv6 addresses. Minimum length = 1 Maximum length = 255

    netmask(str): Subnet mask associated with an IPv4 network address. If the IP address specifies the address or host name
        of a specific host, accept the default value of 255.255.255.255.

    domainresolveretry(int): Amount of time, in seconds, for which the NetScaler appliance waits before sending another DNS
        query to resolve the host name of the SNMP manager if the last query failed. This parameter is valid for
        host-name based SNMP managers only. After a query succeeds, the TTL determines the wait time. Minimum value = 5
        Maximum value = 20939

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.add_snmpmanager <args>

    '''

    result = {}

    payload = {'snmpmanager': {}}

    if ipaddress:
        payload['snmpmanager']['ipaddress'] = ipaddress

    if netmask:
        payload['snmpmanager']['netmask'] = netmask

    if domainresolveretry:
        payload['snmpmanager']['domainresolveretry'] = domainresolveretry

    execution = __proxy__['citrixns.post']('config/snmpmanager', payload)

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


def add_snmptrap(trapclass=None, trapdestination=None, version=None, td=None, destport=None, communityname=None,
                 srcip=None, severity=None, allpartitions=None, save=False):
    '''
    Add a new snmptrap to the running configuration.

    trapclass(str): Type of trap messages that the NetScaler appliance sends to the trap listener: Generic or the
        enterprise-specific messages defined in the MIB file. Possible values = generic, specific

    trapdestination(str): IPv4 or the IPv6 address of the trap listener to which the NetScaler appliance is to send SNMP trap
        messages. Minimum length = 1

    version(str): SNMP version, which determines the format of trap messages sent to the trap listener.  This setting must
        match the setting on the trap listener. Otherwise, the listener drops the trap messages. Default value: V2
        Possible values = V1, V2, V3

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    destport(int): UDP port at which the trap listener listens for trap messages. This setting must match the setting on the
        trap listener. Otherwise, the listener drops the trap messages. Default value: 162 Minimum value = 1 Maximum
        value = 65534

    communityname(str): Password (string) sent with the trap messages, so that the trap listener can authenticate them. Can
        include 1 to 31 uppercase or lowercase letters, numbers, and hyphen (-), period (.) pound (#), space ( ), at (@),
        equals (=), colon (:), and underscore (_) characters.  You must specify the same community string on the trap
        listener device. Otherwise, the trap listener drops the trap messages.  The following requirement applies only to
        the NetScaler CLI: If the string includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my string" or my string).

    srcip(str): IPv4 or IPv6 address that the NetScaler appliance inserts as the source IP address in all SNMP trap messages
        that it sends to this trap listener. By default this is the appliances NSIP or NSIP6 address, but you can specify
        an IPv4 MIP or SNIP/SNIP6 address. In cluster setup, the default value is the individual nodes NSIP, but it can
        be set to CLIP or Striped SNIP address. In non default partition, this parameter must be set to the SNIP/SNIP6
        address. Minimum length = 1

    severity(str): Severity level at or above which the NetScaler appliance sends trap messages to this trap listener. The
        severity levels, in increasing order of severity, are Informational, Warning, Minor, Major, Critical. This
        parameter can be set for trap listeners of type SPECIFIC only. The default is to send all levels of trap
        messages.  Important: Trap messages are not assigned severity levels unless you specify severity levels when
        configuring SNMP alarms. Default value: Unknown Possible values = Critical, Major, Minor, Warning, Informational

    allpartitions(str): Send traps of all partitions to this destination. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.add_snmptrap <args>

    '''

    result = {}

    payload = {'snmptrap': {}}

    if trapclass:
        payload['snmptrap']['trapclass'] = trapclass

    if trapdestination:
        payload['snmptrap']['trapdestination'] = trapdestination

    if version:
        payload['snmptrap']['version'] = version

    if td:
        payload['snmptrap']['td'] = td

    if destport:
        payload['snmptrap']['destport'] = destport

    if communityname:
        payload['snmptrap']['communityname'] = communityname

    if srcip:
        payload['snmptrap']['srcip'] = srcip

    if severity:
        payload['snmptrap']['severity'] = severity

    if allpartitions:
        payload['snmptrap']['allpartitions'] = allpartitions

    execution = __proxy__['citrixns.post']('config/snmptrap', payload)

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


def add_snmptrap_snmpuser_binding(trapclass=None, securitylevel=None, username=None, td=None, trapdestination=None,
                                  version=None, save=False):
    '''
    Add a new snmptrap_snmpuser_binding to the running configuration.

    trapclass(str): Type of trap messages that the NetScaler appliance sends to the trap listener: Generic or the
        enterprise-specific messages defined in the MIB file. Possible values = generic, specific

    securitylevel(str): Security level of the SNMPv3 trap. Default value: authNoPriv, Possible values = noAuthNoPriv,
        authNoPriv, authPriv

    username(str): Name of the SNMP user that will send the SNMPv3 traps.

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    trapdestination(str): IPv4 or the IPv6 address of the trap listener to which the NetScaler appliance is to send SNMP trap
        messages. Minimum length = 1

    version(str): SNMP version, which determines the format of trap messages sent to the trap listener. This setting must
        match the setting on the trap listener. Otherwise, the listener drops the trap messages. Default value: V3
        Possible values = V1, V2, V3

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.add_snmptrap_snmpuser_binding <args>

    '''

    result = {}

    payload = {'snmptrap_snmpuser_binding': {}}

    if trapclass:
        payload['snmptrap_snmpuser_binding']['trapclass'] = trapclass

    if securitylevel:
        payload['snmptrap_snmpuser_binding']['securitylevel'] = securitylevel

    if username:
        payload['snmptrap_snmpuser_binding']['username'] = username

    if td:
        payload['snmptrap_snmpuser_binding']['td'] = td

    if trapdestination:
        payload['snmptrap_snmpuser_binding']['trapdestination'] = trapdestination

    if version:
        payload['snmptrap_snmpuser_binding']['version'] = version

    execution = __proxy__['citrixns.post']('config/snmptrap_snmpuser_binding', payload)

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


def add_snmpuser(name=None, group=None, authtype=None, authpasswd=None, privtype=None, privpasswd=None, save=False):
    '''
    Add a new snmpuser to the running configuration.

    name(str): Name for the SNMPv3 user. Can consist of 1 to 31 characters that include uppercase and lowercase letters,
        numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore
        (_) characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose it in double or single quotation marks (for example, "my user" or my user). Minimum length = 1

    group(str): Name of the configured SNMPv3 group to which to bind this SNMPv3 user. The access rights (bound SNMPv3 views)
        and security level set for this group are assigned to this user. Minimum length = 1

    authtype(str): Authentication algorithm used by the NetScaler appliance and the SNMPv3 user for authenticating the
        communication between them. You must specify the same authentication algorithm when you configure the SNMPv3 user
        in the SNMP manager. Possible values = MD5, SHA

    authpasswd(str): Plain-text pass phrase to be used by the authentication algorithm specified by the authType
        (Authentication Type) parameter. Can consist of 1 to 31 characters that include uppercase and lowercase letters,
        numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore
        (_) characters.  The following requirement applies only to the NetScaler CLI: If the pass phrase includes one or
        more spaces, enclose it in double or single quotation marks (for example, "my phrase" or my phrase). Minimum
        length = 8

    privtype(str): Encryption algorithm used by the NetScaler appliance and the SNMPv3 user for encrypting the communication
        between them. You must specify the same encryption algorithm when you configure the SNMPv3 user in the SNMP
        manager. Possible values = DES, AES

    privpasswd(str): Encryption key to be used by the encryption algorithm specified by the privType (Encryption Type)
        parameter. Can consist of 1 to 31 characters that include uppercase and lowercase letters, numbers, and the
        hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore (_) characters.
        The following requirement applies only to the NetScaler CLI: If the key includes one or more spaces, enclose it
        in double or single quotation marks (for example, "my key" or my key). Minimum length = 8

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.add_snmpuser <args>

    '''

    result = {}

    payload = {'snmpuser': {}}

    if name:
        payload['snmpuser']['name'] = name

    if group:
        payload['snmpuser']['group'] = group

    if authtype:
        payload['snmpuser']['authtype'] = authtype

    if authpasswd:
        payload['snmpuser']['authpasswd'] = authpasswd

    if privtype:
        payload['snmpuser']['privtype'] = privtype

    if privpasswd:
        payload['snmpuser']['privpasswd'] = privpasswd

    execution = __proxy__['citrixns.post']('config/snmpuser', payload)

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


def add_snmpview(name=None, subtree=None, ns_type=None, save=False):
    '''
    Add a new snmpview to the running configuration.

    name(str): Name for the SNMPv3 view. Can consist of 1 to 31 characters that include uppercase and lowercase letters,
        numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore
        (_) characters. You should choose a name that helps identify the SNMPv3 view.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose it in double or single quotation
        marks (for example, "my view" or my view). Minimum length = 1

    subtree(str): A particular branch (subtree) of the MIB tree that you want to associate with this SNMPv3 view. You must
        specify the subtree as an SNMP OID. Minimum length = 1

    ns_type(str): Include or exclude the subtree, specified by the subtree parameter, in or from this view. This setting can
        be useful when you have included a subtree, such as A, in an SNMPv3 view and you want to exclude a specific
        subtree of A, such as B, from the SNMPv3 view. Possible values = included, excluded

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.add_snmpview <args>

    '''

    result = {}

    payload = {'snmpview': {}}

    if name:
        payload['snmpview']['name'] = name

    if subtree:
        payload['snmpview']['subtree'] = subtree

    if ns_type:
        payload['snmpview']['type'] = ns_type

    execution = __proxy__['citrixns.post']('config/snmpview', payload)

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


def disable_snmpalarm(trapname=None, save=False):
    '''
    Disables a snmpalarm matching the specified filter.

    trapname(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.disable_snmpalarm trapname=foo

    '''

    result = {}

    payload = {'snmpalarm': {}}

    if trapname:
        payload['snmpalarm']['trapname'] = trapname
    else:
        result['result'] = 'False'
        result['error'] = 'trapname value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/snmpalarm?action=disable', payload)

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


def enable_snmpalarm(trapname=None, save=False):
    '''
    Enables a snmpalarm matching the specified filter.

    trapname(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.enable_snmpalarm trapname=foo

    '''

    result = {}

    payload = {'snmpalarm': {}}

    if trapname:
        payload['snmpalarm']['trapname'] = trapname
    else:
        result['result'] = 'False'
        result['error'] = 'trapname value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/snmpalarm?action=enable', payload)

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


def get_snmpalarm(trapname=None, thresholdvalue=None, normalvalue=None, time=None, state=None, severity=None,
                  logging=None):
    '''
    Show the running configuration for the snmpalarm config key.

    trapname(str): Filters results that only match the trapname field.

    thresholdvalue(int): Filters results that only match the thresholdvalue field.

    normalvalue(int): Filters results that only match the normalvalue field.

    time(int): Filters results that only match the time field.

    state(str): Filters results that only match the state field.

    severity(str): Filters results that only match the severity field.

    logging(str): Filters results that only match the logging field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmpalarm

    '''

    search_filter = []

    if trapname:
        search_filter.append(['trapname', trapname])

    if thresholdvalue:
        search_filter.append(['thresholdvalue', thresholdvalue])

    if normalvalue:
        search_filter.append(['normalvalue', normalvalue])

    if time:
        search_filter.append(['time', time])

    if state:
        search_filter.append(['state', state])

    if severity:
        search_filter.append(['severity', severity])

    if logging:
        search_filter.append(['logging', logging])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmpalarm{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmpalarm')

    return response


def get_snmpcommunity(communityname=None, permissions=None):
    '''
    Show the running configuration for the snmpcommunity config key.

    communityname(str): Filters results that only match the communityname field.

    permissions(str): Filters results that only match the permissions field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmpcommunity

    '''

    search_filter = []

    if communityname:
        search_filter.append(['communityname', communityname])

    if permissions:
        search_filter.append(['permissions', permissions])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmpcommunity{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmpcommunity')

    return response


def get_snmpengineid(engineid=None, ownernode=None):
    '''
    Show the running configuration for the snmpengineid config key.

    engineid(str): Filters results that only match the engineid field.

    ownernode(int): Filters results that only match the ownernode field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmpengineid

    '''

    search_filter = []

    if engineid:
        search_filter.append(['engineid', engineid])

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmpengineid{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmpengineid')

    return response


def get_snmpgroup(name=None, securitylevel=None, readviewname=None):
    '''
    Show the running configuration for the snmpgroup config key.

    name(str): Filters results that only match the name field.

    securitylevel(str): Filters results that only match the securitylevel field.

    readviewname(str): Filters results that only match the readviewname field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmpgroup

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if securitylevel:
        search_filter.append(['securitylevel', securitylevel])

    if readviewname:
        search_filter.append(['readviewname', readviewname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmpgroup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmpgroup')

    return response


def get_snmpmanager(ipaddress=None, netmask=None, domainresolveretry=None):
    '''
    Show the running configuration for the snmpmanager config key.

    ipaddress(str): Filters results that only match the ipaddress field.

    netmask(str): Filters results that only match the netmask field.

    domainresolveretry(int): Filters results that only match the domainresolveretry field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmpmanager

    '''

    search_filter = []

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if netmask:
        search_filter.append(['netmask', netmask])

    if domainresolveretry:
        search_filter.append(['domainresolveretry', domainresolveretry])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmpmanager{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmpmanager')

    return response


def get_snmpmib(contact=None, name=None, location=None, customid=None, ownernode=None):
    '''
    Show the running configuration for the snmpmib config key.

    contact(str): Filters results that only match the contact field.

    name(str): Filters results that only match the name field.

    location(str): Filters results that only match the location field.

    customid(str): Filters results that only match the customid field.

    ownernode(int): Filters results that only match the ownernode field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmpmib

    '''

    search_filter = []

    if contact:
        search_filter.append(['contact', contact])

    if name:
        search_filter.append(['name', name])

    if location:
        search_filter.append(['location', location])

    if customid:
        search_filter.append(['customid', customid])

    if ownernode:
        search_filter.append(['ownernode', ownernode])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmpmib{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmpmib')

    return response


def get_snmpoid(entitytype=None, name=None):
    '''
    Show the running configuration for the snmpoid config key.

    entitytype(str): Filters results that only match the entitytype field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmpoid

    '''

    search_filter = []

    if entitytype:
        search_filter.append(['entitytype', entitytype])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmpoid{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmpoid')

    return response


def get_snmpoption():
    '''
    Show the running configuration for the snmpoption config key.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmpoption

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmpoption'), 'snmpoption')

    return response


def get_snmptrap(trapclass=None, trapdestination=None, version=None, td=None, destport=None, communityname=None,
                 srcip=None, severity=None, allpartitions=None):
    '''
    Show the running configuration for the snmptrap config key.

    trapclass(str): Filters results that only match the trapclass field.

    trapdestination(str): Filters results that only match the trapdestination field.

    version(str): Filters results that only match the version field.

    td(int): Filters results that only match the td field.

    destport(int): Filters results that only match the destport field.

    communityname(str): Filters results that only match the communityname field.

    srcip(str): Filters results that only match the srcip field.

    severity(str): Filters results that only match the severity field.

    allpartitions(str): Filters results that only match the allpartitions field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmptrap

    '''

    search_filter = []

    if trapclass:
        search_filter.append(['trapclass', trapclass])

    if trapdestination:
        search_filter.append(['trapdestination', trapdestination])

    if version:
        search_filter.append(['version', version])

    if td:
        search_filter.append(['td', td])

    if destport:
        search_filter.append(['destport', destport])

    if communityname:
        search_filter.append(['communityname', communityname])

    if srcip:
        search_filter.append(['srcip', srcip])

    if severity:
        search_filter.append(['severity', severity])

    if allpartitions:
        search_filter.append(['allpartitions', allpartitions])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmptrap{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmptrap')

    return response


def get_snmptrap_binding():
    '''
    Show the running configuration for the snmptrap_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmptrap_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmptrap_binding'), 'snmptrap_binding')

    return response


def get_snmptrap_snmpuser_binding(trapclass=None, securitylevel=None, username=None, td=None, trapdestination=None,
                                  version=None):
    '''
    Show the running configuration for the snmptrap_snmpuser_binding config key.

    trapclass(str): Filters results that only match the trapclass field.

    securitylevel(str): Filters results that only match the securitylevel field.

    username(str): Filters results that only match the username field.

    td(int): Filters results that only match the td field.

    trapdestination(str): Filters results that only match the trapdestination field.

    version(str): Filters results that only match the version field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmptrap_snmpuser_binding

    '''

    search_filter = []

    if trapclass:
        search_filter.append(['trapclass', trapclass])

    if securitylevel:
        search_filter.append(['securitylevel', securitylevel])

    if username:
        search_filter.append(['username', username])

    if td:
        search_filter.append(['td', td])

    if trapdestination:
        search_filter.append(['trapdestination', trapdestination])

    if version:
        search_filter.append(['version', version])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmptrap_snmpuser_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmptrap_snmpuser_binding')

    return response


def get_snmpuser(name=None, group=None, authtype=None, authpasswd=None, privtype=None, privpasswd=None):
    '''
    Show the running configuration for the snmpuser config key.

    name(str): Filters results that only match the name field.

    group(str): Filters results that only match the group field.

    authtype(str): Filters results that only match the authtype field.

    authpasswd(str): Filters results that only match the authpasswd field.

    privtype(str): Filters results that only match the privtype field.

    privpasswd(str): Filters results that only match the privpasswd field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmpuser

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if group:
        search_filter.append(['group', group])

    if authtype:
        search_filter.append(['authtype', authtype])

    if authpasswd:
        search_filter.append(['authpasswd', authpasswd])

    if privtype:
        search_filter.append(['privtype', privtype])

    if privpasswd:
        search_filter.append(['privpasswd', privpasswd])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmpuser{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmpuser')

    return response


def get_snmpview(name=None, subtree=None, ns_type=None):
    '''
    Show the running configuration for the snmpview config key.

    name(str): Filters results that only match the name field.

    subtree(str): Filters results that only match the subtree field.

    ns_type(str): Filters results that only match the type field.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.get_snmpview

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if subtree:
        search_filter.append(['subtree', subtree])

    if ns_type:
        search_filter.append(['type', ns_type])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/snmpview{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'snmpview')

    return response


def unset_snmpalarm(trapname=None, thresholdvalue=None, normalvalue=None, time=None, state=None, severity=None,
                    logging=None, save=False):
    '''
    Unsets values from the snmpalarm configuration key.

    trapname(bool): Unsets the trapname value.

    thresholdvalue(bool): Unsets the thresholdvalue value.

    normalvalue(bool): Unsets the normalvalue value.

    time(bool): Unsets the time value.

    state(bool): Unsets the state value.

    severity(bool): Unsets the severity value.

    logging(bool): Unsets the logging value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.unset_snmpalarm <args>

    '''

    result = {}

    payload = {'snmpalarm': {}}

    if trapname:
        payload['snmpalarm']['trapname'] = True

    if thresholdvalue:
        payload['snmpalarm']['thresholdvalue'] = True

    if normalvalue:
        payload['snmpalarm']['normalvalue'] = True

    if time:
        payload['snmpalarm']['time'] = True

    if state:
        payload['snmpalarm']['state'] = True

    if severity:
        payload['snmpalarm']['severity'] = True

    if logging:
        payload['snmpalarm']['logging'] = True

    execution = __proxy__['citrixns.post']('config/snmpalarm?action=unset', payload)

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


def unset_snmpengineid(engineid=None, ownernode=None, save=False):
    '''
    Unsets values from the snmpengineid configuration key.

    engineid(bool): Unsets the engineid value.

    ownernode(bool): Unsets the ownernode value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.unset_snmpengineid <args>

    '''

    result = {}

    payload = {'snmpengineid': {}}

    if engineid:
        payload['snmpengineid']['engineid'] = True

    if ownernode:
        payload['snmpengineid']['ownernode'] = True

    execution = __proxy__['citrixns.post']('config/snmpengineid?action=unset', payload)

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


def unset_snmpmanager(ipaddress=None, netmask=None, domainresolveretry=None, save=False):
    '''
    Unsets values from the snmpmanager configuration key.

    ipaddress(bool): Unsets the ipaddress value.

    netmask(bool): Unsets the netmask value.

    domainresolveretry(bool): Unsets the domainresolveretry value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.unset_snmpmanager <args>

    '''

    result = {}

    payload = {'snmpmanager': {}}

    if ipaddress:
        payload['snmpmanager']['ipaddress'] = True

    if netmask:
        payload['snmpmanager']['netmask'] = True

    if domainresolveretry:
        payload['snmpmanager']['domainresolveretry'] = True

    execution = __proxy__['citrixns.post']('config/snmpmanager?action=unset', payload)

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


def unset_snmpmib(contact=None, name=None, location=None, customid=None, ownernode=None, save=False):
    '''
    Unsets values from the snmpmib configuration key.

    contact(bool): Unsets the contact value.

    name(bool): Unsets the name value.

    location(bool): Unsets the location value.

    customid(bool): Unsets the customid value.

    ownernode(bool): Unsets the ownernode value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.unset_snmpmib <args>

    '''

    result = {}

    payload = {'snmpmib': {}}

    if contact:
        payload['snmpmib']['contact'] = True

    if name:
        payload['snmpmib']['name'] = True

    if location:
        payload['snmpmib']['location'] = True

    if customid:
        payload['snmpmib']['customid'] = True

    if ownernode:
        payload['snmpmib']['ownernode'] = True

    execution = __proxy__['citrixns.post']('config/snmpmib?action=unset', payload)

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


def unset_snmpoption(snmpset=None, snmptraplogging=None, partitionnameintrap=None, snmptraplogginglevel=None,
                     save=False):
    '''
    Unsets values from the snmpoption configuration key.

    snmpset(bool): Unsets the snmpset value.

    snmptraplogging(bool): Unsets the snmptraplogging value.

    partitionnameintrap(bool): Unsets the partitionnameintrap value.

    snmptraplogginglevel(bool): Unsets the snmptraplogginglevel value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.unset_snmpoption <args>

    '''

    result = {}

    payload = {'snmpoption': {}}

    if snmpset:
        payload['snmpoption']['snmpset'] = True

    if snmptraplogging:
        payload['snmpoption']['snmptraplogging'] = True

    if partitionnameintrap:
        payload['snmpoption']['partitionnameintrap'] = True

    if snmptraplogginglevel:
        payload['snmpoption']['snmptraplogginglevel'] = True

    execution = __proxy__['citrixns.post']('config/snmpoption?action=unset', payload)

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


def unset_snmptrap(trapclass=None, trapdestination=None, version=None, td=None, destport=None, communityname=None,
                   srcip=None, severity=None, allpartitions=None, save=False):
    '''
    Unsets values from the snmptrap configuration key.

    trapclass(bool): Unsets the trapclass value.

    trapdestination(bool): Unsets the trapdestination value.

    version(bool): Unsets the version value.

    td(bool): Unsets the td value.

    destport(bool): Unsets the destport value.

    communityname(bool): Unsets the communityname value.

    srcip(bool): Unsets the srcip value.

    severity(bool): Unsets the severity value.

    allpartitions(bool): Unsets the allpartitions value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.unset_snmptrap <args>

    '''

    result = {}

    payload = {'snmptrap': {}}

    if trapclass:
        payload['snmptrap']['trapclass'] = True

    if trapdestination:
        payload['snmptrap']['trapdestination'] = True

    if version:
        payload['snmptrap']['version'] = True

    if td:
        payload['snmptrap']['td'] = True

    if destport:
        payload['snmptrap']['destport'] = True

    if communityname:
        payload['snmptrap']['communityname'] = True

    if srcip:
        payload['snmptrap']['srcip'] = True

    if severity:
        payload['snmptrap']['severity'] = True

    if allpartitions:
        payload['snmptrap']['allpartitions'] = True

    execution = __proxy__['citrixns.post']('config/snmptrap?action=unset', payload)

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


def unset_snmpuser(name=None, group=None, authtype=None, authpasswd=None, privtype=None, privpasswd=None, save=False):
    '''
    Unsets values from the snmpuser configuration key.

    name(bool): Unsets the name value.

    group(bool): Unsets the group value.

    authtype(bool): Unsets the authtype value.

    authpasswd(bool): Unsets the authpasswd value.

    privtype(bool): Unsets the privtype value.

    privpasswd(bool): Unsets the privpasswd value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.unset_snmpuser <args>

    '''

    result = {}

    payload = {'snmpuser': {}}

    if name:
        payload['snmpuser']['name'] = True

    if group:
        payload['snmpuser']['group'] = True

    if authtype:
        payload['snmpuser']['authtype'] = True

    if authpasswd:
        payload['snmpuser']['authpasswd'] = True

    if privtype:
        payload['snmpuser']['privtype'] = True

    if privpasswd:
        payload['snmpuser']['privpasswd'] = True

    execution = __proxy__['citrixns.post']('config/snmpuser?action=unset', payload)

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


def update_snmpalarm(trapname=None, thresholdvalue=None, normalvalue=None, time=None, state=None, severity=None,
                     logging=None, save=False):
    '''
    Update the running configuration for the snmpalarm config key.

    trapname(str): Name of the SNMP alarm. This parameter is required for identifying the SNMP alarm and cannot be modified.
        Possible values = CPU-USAGE, AVERAGE-CPU, MEMORY, MGMT-CPU-USAGE, SYNFLOOD, VSERVER-REQRATE, SERVICE-REQRATE,
        ENTITY-RXRATE, ENTITY-TXRATE, ENTITY-SYNFLOOD, SERVICE-MAXCLIENTS, HA-STATE-CHANGE, ENTITY-STATE, CONFIG-CHANGE,
        CONFIG-SAVE, SERVICEGROUP-MEMBER-REQRATE, SERVICEGROUP-MEMBER-MAXCLIENTS, MONITOR-RTO-THRESHOLD, LOGIN-FAILURE,
        SSL-CERT-EXPIRY, FAN-SPEED-LOW, VOLTAGE-LOW, VOLTAGE-HIGH, TEMPERATURE-HIGH, CPU-TEMPERATURE-HIGH,
        POWER-SUPPLY-FAILURE, DISK-USAGE-HIGH, INTERFACE-THROUGHPUT-LOW, MON_PROBE_FAILED, HA-VERSION-MISMATCH,
        HA-SYNC-FAILURE, HA-NO-HEARTBEATS, HA-BAD-SECONDARY-STATE, INTERFACE-BW-USAGE, RATE-LIMIT-THRESHOLD-EXCEEDED,
        ENTITY-NAME-CHANGE, HA-PROP-FAILURE, IP-CONFLICT, PF-RL-RATE-THRESHOLD, PF-RL-PPS-THRESHOLD,
        PF-RL-RATE-PKTS-DROPPED, PF-RL-PPS-PKTS-DROPPED, APPFW-START-URL, APPFW-DENY-URL, APPFW-VIOLATIONS-TYPE,
        APPFW-REFERER-HEADER, APPFW-CSRF-TAG, APPFW-COOKIE, APPFW-FIELD-CONSISTENCY, APPFW-BUFFER-OVERFLOW,
        APPFW-FIELD-FORMAT, APPFW-SAFE-COMMERCE, APPFW-SAFE-OBJECT, APPFW-SESSION-LIMIT, APPFW-POLICY-HIT, APPFW-XSS,
        APPFW-XML-XSS, APPFW-SQL, APPFW-XML-SQL, APPFW-XML-ATTACHMENT, APPFW-XML-DOS, APPFW-XML-VALIDATION,
        APPFW-XML-WSI, APPFW-XML-SCHEMA-COMPILE, APPFW-XML-SOAP-FAULT, DNSKEY-EXPIRY, HA-LICENSE-MISMATCH,
        SSL-CARD-FAILED, SSL-CARD-NORMAL, WARM-RESTART-EVENT, HARD-DISK-DRIVE-ERRORS, COMPACT-FLASH-ERRORS,
        CALLHOME-UPLOAD-EVENT, 1024KEY-EXCHANGE-RATE, 2048KEY-EXCHANGE-RATE, 4096KEY-EXCHANGE-RATE,
        SSL-CUR-SESSION-INUSE, CLUSTER-NODE-HEALTH, CLUSTER-NODE-QUORUM, CLUSTER-VERSION-MISMATCH, CLUSTER-CCO-CHANGE,
        CLUSTER-OVS-CHANGE, CLUSTER-SYNC-FAILURE, CLUSTER-PROP-FAILURE, HA-STICKY-PRIMARY,
        INBAND-PROTOCOL-VERSION-MISMATCH, SSL-CHIP-REINIT, VRID-STATE-CHANGE, PORT-ALLOC-FAILED, LLDP-REMOTE-CHANGE,
        DUPLICATE-IPV6, PARTITION-CONFIG-EVENT, PARTITION-SWITCHED, LSN-PORTALLOC-FAILED, LSN-PORTQUOTA-EXCEED,
        LSN-SESSIONQUOTA-EXCEED, LSN-MEM-RECOVERY-KICKEDIN, VSERVER-SPILLOVER, PARTITION-RATE-LIMIT,
        POOLED-LICENSE-ONGRACE, POOLED-LICENSE-PARTIAL, CLUSTER-BACKPLANE-HB-MISSING, GSLB-SITE-MEP-FLAP,
        DNS-MAXNEGCACHE-USAGE, DNS-MAXCACHE-USAGE

    thresholdvalue(int): Value for the high threshold. The NetScaler appliance generates an SNMP trap message when the value
        of the attribute associated with the alarm is greater than or equal to the specified high threshold value.
        Minimum value = 1

    normalvalue(int): Value for the normal threshold. A trap message is generated if the value of the respective attribute
        falls to or below this value after exceeding the high threshold. Minimum value = 1

    time(int): Interval, in seconds, at which the NetScaler appliance generates SNMP trap messages when the conditions
        specified in the SNMP alarm are met.Can be specified for the following alarms: SYNFLOOD, HA-VERSION-MISMATCH,
        HA-SYNC-FAILURE, HA-NO-HEARTBEATS,HA-BAD-SECONDARY-STATE, CLUSTER-NODE-HEALTH, CLUSTER-NODE-QUORUM,
        CLUSTER-VERSION-MISMATCH, CLUSTER-BKHB-FAILED, PORT-ALLOC-FAILED, COMPACT-FLASH-ERRORS, HARD-DISK-DRIVE-ERRORS
        and APPFW traps. Default trap time intervals: SYNFLOOD and APPFW traps = 1sec, PORT-ALLOC-FAILED = 3600sec(1
        hour), Other Traps = 86400sec(1 day). Default value: 1

    state(str): Current state of the SNMP alarm. The NetScaler appliance generates trap messages only for SNMP alarms that
        are enabled. Some alarms are enabled by default, but you can disable them. Default value: ENABLED Possible values
        = ENABLED, DISABLED

    severity(str): Severity level assigned to trap messages generated by this alarm. The severity levels are, in increasing
        order of severity, Informational, Warning, Minor, Major, and Critical. This parameter is useful when you want the
        NetScaler appliance to send trap messages to a trap listener on the basis of severity level. Trap messages with a
        severity level lower than the specified level (in the trap listener entry) are not sent. Default value: Unknown
        Possible values = Critical, Major, Minor, Warning, Informational

    logging(str): Logging status of the alarm. When logging is enabled, the NetScaler appliance logs every trap message that
        is generated for this alarm. Default value: ENABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.update_snmpalarm <args>

    '''

    result = {}

    payload = {'snmpalarm': {}}

    if trapname:
        payload['snmpalarm']['trapname'] = trapname

    if thresholdvalue:
        payload['snmpalarm']['thresholdvalue'] = thresholdvalue

    if normalvalue:
        payload['snmpalarm']['normalvalue'] = normalvalue

    if time:
        payload['snmpalarm']['time'] = time

    if state:
        payload['snmpalarm']['state'] = state

    if severity:
        payload['snmpalarm']['severity'] = severity

    if logging:
        payload['snmpalarm']['logging'] = logging

    execution = __proxy__['citrixns.put']('config/snmpalarm', payload)

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


def update_snmpengineid(engineid=None, ownernode=None, save=False):
    '''
    Update the running configuration for the snmpengineid config key.

    engineid(str): A hexadecimal value of at least 10 characters, uniquely identifying the engineid. Minimum length = 10
        Maximum length = 31

    ownernode(int): ID of the cluster node for which you are setting the engineid. Default value: -1 Minimum value = 0
        Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.update_snmpengineid <args>

    '''

    result = {}

    payload = {'snmpengineid': {}}

    if engineid:
        payload['snmpengineid']['engineid'] = engineid

    if ownernode:
        payload['snmpengineid']['ownernode'] = ownernode

    execution = __proxy__['citrixns.put']('config/snmpengineid', payload)

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


def update_snmpgroup(name=None, securitylevel=None, readviewname=None, save=False):
    '''
    Update the running configuration for the snmpgroup config key.

    name(str): Name for the SNMPv3 group. Can consist of 1 to 31 characters that include uppercase and lowercase letters,
        numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore
        (_) characters. You should choose a name that helps identify the SNMPv3 group.    The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose it in double or single
        quotation marks (for example, "my name" or my name). Minimum length = 1

    securitylevel(str): Security level required for communication between the NetScaler appliance and the SNMPv3 users who
        belong to the group. Specify one of the following options: noAuthNoPriv. Require neither authentication nor
        encryption. authNoPriv. Require authentication but no encryption. authPriv. Require authentication and
        encryption. Note: If you specify authentication, you must specify an encryption algorithm when you assign an
        SNMPv3 user to the group. If you also specify encryption, you must assign both an authentication and an
        encryption algorithm for each group member. Possible values = noAuthNoPriv, authNoPriv, authPriv

    readviewname(str): Name of the configured SNMPv3 view that you want to bind to this SNMPv3 group. An SNMPv3 user bound to
        this group can access the subtrees that are bound to this SNMPv3 view as type INCLUDED, but cannot access the
        ones that are type EXCLUDED. If the NetScaler appliance has multiple SNMPv3 view entries with the same name, all
        such entries are associated with the SNMPv3 group. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.update_snmpgroup <args>

    '''

    result = {}

    payload = {'snmpgroup': {}}

    if name:
        payload['snmpgroup']['name'] = name

    if securitylevel:
        payload['snmpgroup']['securitylevel'] = securitylevel

    if readviewname:
        payload['snmpgroup']['readviewname'] = readviewname

    execution = __proxy__['citrixns.put']('config/snmpgroup', payload)

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


def update_snmpmanager(ipaddress=None, netmask=None, domainresolveretry=None, save=False):
    '''
    Update the running configuration for the snmpmanager config key.

    ipaddress(str): IP address of the SNMP manager. Can be an IPv4 or IPv6 address. You can instead specify an IPv4 network
        address or IPv6 network prefix if you want the NetScaler appliance to respond to SNMP queries from any device on
        the specified network. Alternatively, instead of an IPv4 address, you can specify a host name that has been
        assigned to an SNMP manager. If you do so, you must add a DNS name server that resolves the host name of the SNMP
        manager to its IP address.  Note: The NetScaler appliance does not support host names for SNMP managers that have
        IPv6 addresses. Minimum length = 1 Maximum length = 255

    netmask(str): Subnet mask associated with an IPv4 network address. If the IP address specifies the address or host name
        of a specific host, accept the default value of 255.255.255.255.

    domainresolveretry(int): Amount of time, in seconds, for which the NetScaler appliance waits before sending another DNS
        query to resolve the host name of the SNMP manager if the last query failed. This parameter is valid for
        host-name based SNMP managers only. After a query succeeds, the TTL determines the wait time. Minimum value = 5
        Maximum value = 20939

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.update_snmpmanager <args>

    '''

    result = {}

    payload = {'snmpmanager': {}}

    if ipaddress:
        payload['snmpmanager']['ipaddress'] = ipaddress

    if netmask:
        payload['snmpmanager']['netmask'] = netmask

    if domainresolveretry:
        payload['snmpmanager']['domainresolveretry'] = domainresolveretry

    execution = __proxy__['citrixns.put']('config/snmpmanager', payload)

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


def update_snmpmib(contact=None, name=None, location=None, customid=None, ownernode=None, save=False):
    '''
    Update the running configuration for the snmpmib config key.

    contact(str): Name of the administrator for this NetScaler appliance. Along with the name, you can include information on
        how to contact this person, such as a phone number or an email address. Can consist of 1 to 127 characters that
        include uppercase and lowercase letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign
        (@), equals (=), colon (:), and underscore (_) characters.  The following requirement applies only to the
        NetScaler CLI: If the information includes one or more spaces, enclose it in double or single quotation marks
        (for example, "my contact" or my contact). Default value: "WebMaster (default)" Minimum length = 1

    name(str): Name for this NetScaler appliance. Can consist of 1 to 127 characters that include uppercase and lowercase
        letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore (_) characters. You should choose a name that helps identify the NetScaler appliance.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose it in double or
        single quotation marks (for example, "my name" or my name). Default value: "NetScaler" Minimum length = 1

    location(str): Physical location of the NetScaler appliance. For example, you can specify building name, lab number, and
        rack number. Can consist of 1 to 127 characters that include uppercase and lowercase letters, numbers, and the
        hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore (_) characters.
        The following requirement applies only to the NetScaler CLI: If the location includes one or more spaces, enclose
        it in double or single quotation marks (for example, "my location" or my location). Default value: "POP
        (default)" Minimum length = 1

    customid(str): Custom identification number for the NetScaler appliance. Can consist of 1 to 127 characters that include
        uppercase and lowercase letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@),
        equals (=), colon (:), and underscore (_) characters. You should choose a custom identification that helps
        identify the NetScaler appliance.  The following requirement applies only to the NetScaler CLI: If the ID
        includes one or more spaces, enclose it in double or single quotation marks (for example, "my ID" or my ID).
        Default value: "Default" Minimum length = 1

    ownernode(int): ID of the cluster node for which we are setting the mib. This is a mandatory argument to set snmp mib on
        CLIP. Default value: -1 Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.update_snmpmib <args>

    '''

    result = {}

    payload = {'snmpmib': {}}

    if contact:
        payload['snmpmib']['contact'] = contact

    if name:
        payload['snmpmib']['name'] = name

    if location:
        payload['snmpmib']['location'] = location

    if customid:
        payload['snmpmib']['customid'] = customid

    if ownernode:
        payload['snmpmib']['ownernode'] = ownernode

    execution = __proxy__['citrixns.put']('config/snmpmib', payload)

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


def update_snmpoption(snmpset=None, snmptraplogging=None, partitionnameintrap=None, snmptraplogginglevel=None,
                      save=False):
    '''
    Update the running configuration for the snmpoption config key.

    snmpset(str): Accept SNMP SET requests sent to the NetScaler appliance, and allow SNMP managers to write values to MIB
        objects that are configured for write access. Default value: DISABLED Possible values = ENABLED, DISABLED

    snmptraplogging(str): Log any SNMP trap events (for SNMP alarms in which logging is enabled) even if no trap listeners
        are configured. With the default setting, SNMP trap events are logged if at least one trap listener is configured
        on the appliance. Default value: DISABLED Possible values = ENABLED, DISABLED

    partitionnameintrap(str): Send partition name as a varbind in traps. By default the partition names are not sent as a
        varbind. Default value: DISABLED Possible values = ENABLED, DISABLED

    snmptraplogginglevel(str): Audit log level of SNMP trap logs. The default value is INFORMATIONAL. Default value:
        INFORMATIONAL Possible values = EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE, INFORMATIONAL, DEBUG

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.update_snmpoption <args>

    '''

    result = {}

    payload = {'snmpoption': {}}

    if snmpset:
        payload['snmpoption']['snmpset'] = snmpset

    if snmptraplogging:
        payload['snmpoption']['snmptraplogging'] = snmptraplogging

    if partitionnameintrap:
        payload['snmpoption']['partitionnameintrap'] = partitionnameintrap

    if snmptraplogginglevel:
        payload['snmpoption']['snmptraplogginglevel'] = snmptraplogginglevel

    execution = __proxy__['citrixns.put']('config/snmpoption', payload)

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


def update_snmptrap(trapclass=None, trapdestination=None, version=None, td=None, destport=None, communityname=None,
                    srcip=None, severity=None, allpartitions=None, save=False):
    '''
    Update the running configuration for the snmptrap config key.

    trapclass(str): Type of trap messages that the NetScaler appliance sends to the trap listener: Generic or the
        enterprise-specific messages defined in the MIB file. Possible values = generic, specific

    trapdestination(str): IPv4 or the IPv6 address of the trap listener to which the NetScaler appliance is to send SNMP trap
        messages. Minimum length = 1

    version(str): SNMP version, which determines the format of trap messages sent to the trap listener.  This setting must
        match the setting on the trap listener. Otherwise, the listener drops the trap messages. Default value: V2
        Possible values = V1, V2, V3

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    destport(int): UDP port at which the trap listener listens for trap messages. This setting must match the setting on the
        trap listener. Otherwise, the listener drops the trap messages. Default value: 162 Minimum value = 1 Maximum
        value = 65534

    communityname(str): Password (string) sent with the trap messages, so that the trap listener can authenticate them. Can
        include 1 to 31 uppercase or lowercase letters, numbers, and hyphen (-), period (.) pound (#), space ( ), at (@),
        equals (=), colon (:), and underscore (_) characters.  You must specify the same community string on the trap
        listener device. Otherwise, the trap listener drops the trap messages.  The following requirement applies only to
        the NetScaler CLI: If the string includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my string" or my string).

    srcip(str): IPv4 or IPv6 address that the NetScaler appliance inserts as the source IP address in all SNMP trap messages
        that it sends to this trap listener. By default this is the appliances NSIP or NSIP6 address, but you can specify
        an IPv4 MIP or SNIP/SNIP6 address. In cluster setup, the default value is the individual nodes NSIP, but it can
        be set to CLIP or Striped SNIP address. In non default partition, this parameter must be set to the SNIP/SNIP6
        address. Minimum length = 1

    severity(str): Severity level at or above which the NetScaler appliance sends trap messages to this trap listener. The
        severity levels, in increasing order of severity, are Informational, Warning, Minor, Major, Critical. This
        parameter can be set for trap listeners of type SPECIFIC only. The default is to send all levels of trap
        messages.  Important: Trap messages are not assigned severity levels unless you specify severity levels when
        configuring SNMP alarms. Default value: Unknown Possible values = Critical, Major, Minor, Warning, Informational

    allpartitions(str): Send traps of all partitions to this destination. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.update_snmptrap <args>

    '''

    result = {}

    payload = {'snmptrap': {}}

    if trapclass:
        payload['snmptrap']['trapclass'] = trapclass

    if trapdestination:
        payload['snmptrap']['trapdestination'] = trapdestination

    if version:
        payload['snmptrap']['version'] = version

    if td:
        payload['snmptrap']['td'] = td

    if destport:
        payload['snmptrap']['destport'] = destport

    if communityname:
        payload['snmptrap']['communityname'] = communityname

    if srcip:
        payload['snmptrap']['srcip'] = srcip

    if severity:
        payload['snmptrap']['severity'] = severity

    if allpartitions:
        payload['snmptrap']['allpartitions'] = allpartitions

    execution = __proxy__['citrixns.put']('config/snmptrap', payload)

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


def update_snmpuser(name=None, group=None, authtype=None, authpasswd=None, privtype=None, privpasswd=None, save=False):
    '''
    Update the running configuration for the snmpuser config key.

    name(str): Name for the SNMPv3 user. Can consist of 1 to 31 characters that include uppercase and lowercase letters,
        numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore
        (_) characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose it in double or single quotation marks (for example, "my user" or my user). Minimum length = 1

    group(str): Name of the configured SNMPv3 group to which to bind this SNMPv3 user. The access rights (bound SNMPv3 views)
        and security level set for this group are assigned to this user. Minimum length = 1

    authtype(str): Authentication algorithm used by the NetScaler appliance and the SNMPv3 user for authenticating the
        communication between them. You must specify the same authentication algorithm when you configure the SNMPv3 user
        in the SNMP manager. Possible values = MD5, SHA

    authpasswd(str): Plain-text pass phrase to be used by the authentication algorithm specified by the authType
        (Authentication Type) parameter. Can consist of 1 to 31 characters that include uppercase and lowercase letters,
        numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore
        (_) characters.  The following requirement applies only to the NetScaler CLI: If the pass phrase includes one or
        more spaces, enclose it in double or single quotation marks (for example, "my phrase" or my phrase). Minimum
        length = 8

    privtype(str): Encryption algorithm used by the NetScaler appliance and the SNMPv3 user for encrypting the communication
        between them. You must specify the same encryption algorithm when you configure the SNMPv3 user in the SNMP
        manager. Possible values = DES, AES

    privpasswd(str): Encryption key to be used by the encryption algorithm specified by the privType (Encryption Type)
        parameter. Can consist of 1 to 31 characters that include uppercase and lowercase letters, numbers, and the
        hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore (_) characters.
        The following requirement applies only to the NetScaler CLI: If the key includes one or more spaces, enclose it
        in double or single quotation marks (for example, "my key" or my key). Minimum length = 8

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.update_snmpuser <args>

    '''

    result = {}

    payload = {'snmpuser': {}}

    if name:
        payload['snmpuser']['name'] = name

    if group:
        payload['snmpuser']['group'] = group

    if authtype:
        payload['snmpuser']['authtype'] = authtype

    if authpasswd:
        payload['snmpuser']['authpasswd'] = authpasswd

    if privtype:
        payload['snmpuser']['privtype'] = privtype

    if privpasswd:
        payload['snmpuser']['privpasswd'] = privpasswd

    execution = __proxy__['citrixns.put']('config/snmpuser', payload)

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


def update_snmpview(name=None, subtree=None, ns_type=None, save=False):
    '''
    Update the running configuration for the snmpview config key.

    name(str): Name for the SNMPv3 view. Can consist of 1 to 31 characters that include uppercase and lowercase letters,
        numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and underscore
        (_) characters. You should choose a name that helps identify the SNMPv3 view.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose it in double or single quotation
        marks (for example, "my view" or my view). Minimum length = 1

    subtree(str): A particular branch (subtree) of the MIB tree that you want to associate with this SNMPv3 view. You must
        specify the subtree as an SNMP OID. Minimum length = 1

    ns_type(str): Include or exclude the subtree, specified by the subtree parameter, in or from this view. This setting can
        be useful when you have included a subtree, such as A, in an SNMPv3 view and you want to exclude a specific
        subtree of A, such as B, from the SNMPv3 view. Possible values = included, excluded

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' snmp.update_snmpview <args>

    '''

    result = {}

    payload = {'snmpview': {}}

    if name:
        payload['snmpview']['name'] = name

    if subtree:
        payload['snmpview']['subtree'] = subtree

    if ns_type:
        payload['snmpview']['type'] = ns_type

    execution = __proxy__['citrixns.put']('config/snmpview', payload)

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
