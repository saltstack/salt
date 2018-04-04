# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the content-switching key.

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

__virtualname__ = 'content_switching'


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

    return False, 'The content_switching execution module can only be loaded for citrixns proxy minions.'


def add_csaction(name=None, targetlbvserver=None, targetvserver=None, targetvserverexpr=None, comment=None, newname=None,
                 save=False):
    '''
    Add a new csaction to the running configuration.

    name(str): Name for the content switching action. Must begin with an ASCII alphanumeric or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign
        (=), and hyphen (-) characters. Can be changed after the content switching action is created. The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my action" or my action).

    targetlbvserver(str): Name of the load balancing virtual server to which the content is switched.

    targetvserver(str): Name of the VPN virtual server to which the content is switched.

    targetvserverexpr(str): Information about this content switching action.

    comment(str): Comments associated with this cs action.

    newname(str): New name for the content switching action. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters.  The following requirement applies only to the NetScaler CLI: If
        the name includes one or more spaces, enclose the name in double or single quotation marks (for example, "my
        name" or my name). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csaction <args>

    '''

    result = {}

    payload = {'csaction': {}}

    if name:
        payload['csaction']['name'] = name

    if targetlbvserver:
        payload['csaction']['targetlbvserver'] = targetlbvserver

    if targetvserver:
        payload['csaction']['targetvserver'] = targetvserver

    if targetvserverexpr:
        payload['csaction']['targetvserverexpr'] = targetvserverexpr

    if comment:
        payload['csaction']['comment'] = comment

    if newname:
        payload['csaction']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/csaction', payload)

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


def add_cspolicy(policyname=None, url=None, rule=None, domain=None, action=None, logaction=None, newname=None,
                 save=False):
    '''
    Add a new cspolicy to the running configuration.

    policyname(str): Name for the content switching policy. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters. Cannot be changed after a policy is created. The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my policy" or my policy). Minimum length = 1

    url(str): URL string that is matched with the URL of a request. Can contain a wildcard character. Specify the string
        value in the following format: [[prefix] [*]] [.suffix]. Minimum length = 1 Maximum length = 208

    rule(str): Expression, or name of a named expression, against which traffic is evaluated. Written in the classic or
        default syntax.  Note: Maximum length of a string literal in the expression is 255 characters. A longer string
        can be split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;" The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    domain(str): The domain name. The string value can range to 63 characters. Minimum length = 1

    action(str): Content switching action that names the target load balancing virtual server to which the traffic is
        switched.

    logaction(str): The log action associated with the content switching policy.

    newname(str): The new name of the content switching policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_cspolicy <args>

    '''

    result = {}

    payload = {'cspolicy': {}}

    if policyname:
        payload['cspolicy']['policyname'] = policyname

    if url:
        payload['cspolicy']['url'] = url

    if rule:
        payload['cspolicy']['rule'] = rule

    if domain:
        payload['cspolicy']['domain'] = domain

    if action:
        payload['cspolicy']['action'] = action

    if logaction:
        payload['cspolicy']['logaction'] = logaction

    if newname:
        payload['cspolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/cspolicy', payload)

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


def add_cspolicylabel(labelname=None, cspolicylabeltype=None, newname=None, save=False):
    '''
    Add a new cspolicylabel to the running configuration.

    labelname(str): Name for the policy label. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign (=),
        and hyphen (-) characters.  The label name must be unique within the list of policy labels for content switching.
        The following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my policylabel" or my policylabel).

    cspolicylabeltype(str): Protocol supported by the policy label. All policies bound to the policy label must either match
        the specified protocol or be a subtype of that protocol. Available settings function as follows: * HTTP -
        Supports policies that process HTTP traffic. Used to access unencrypted Web sites. (The default.) * SSL -
        Supports policies that process HTTPS/SSL encrypted traffic. Used to access encrypted Web sites. * TCP - Supports
        policies that process any type of TCP traffic, including HTTP. * SSL_TCP - Supports policies that process
        SSL-encrypted TCP traffic, including SSL. * UDP - Supports policies that process any type of UDP-based traffic,
        including DNS. * DNS - Supports policies that process DNS traffic. * ANY - Supports all types of policies except
        HTTP, SSL, and TCP.  * SIP_UDP - Supports policies that process UDP based Session Initiation Protocol (SIP)
        traffic. SIP initiates, manages, and terminates multimedia communications sessions, and has emerged as the
        standard for Internet telephony (VoIP). * RTSP - Supports policies that process Real Time Streaming Protocol
        (RTSP) traffic. RTSP provides delivery of multimedia and other streaming data, such as audio, video, and other
        types of streamed media. * RADIUS - Supports policies that process Remote Authentication Dial In User Service
        (RADIUS) traffic. RADIUS supports combined authentication, authorization, and auditing services for network
        management. * MYSQL - Supports policies that process MYSQL traffic. * MSSQL - Supports policies that process
        Microsoft SQL traffic. Possible values = HTTP, TCP, RTSP, SSL, SSL_TCP, UDP, DNS, SIP_UDP, SIP_TCP, ANY, RADIUS,
        RDP, MYSQL, MSSQL, ORACLE, DIAMETER, SSL_DIAMETER, FTP, DNS_TCP, SMPP

    newname(str): The new name of the content switching policylabel. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_cspolicylabel <args>

    '''

    result = {}

    payload = {'cspolicylabel': {}}

    if labelname:
        payload['cspolicylabel']['labelname'] = labelname

    if cspolicylabeltype:
        payload['cspolicylabel']['cspolicylabeltype'] = cspolicylabeltype

    if newname:
        payload['cspolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/cspolicylabel', payload)

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


def add_cspolicylabel_cspolicy_binding(priority=None, policyname=None, labelname=None, targetvserver=None,
                                       invoke_labelname=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                       save=False):
    '''
    Add a new cspolicylabel_cspolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    policyname(str): Name of the content switching policy.

    labelname(str): Name of the policy label to which to bind a content switching policy.

    targetvserver(str): Name of the virtual server to which to forward requests that match the policy.

    invoke_labelname(str): Name of the label to invoke if the current policy rule evaluates to TRUE.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): .

    labeltype(str): Type of policy label invocation. Possible values = policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_cspolicylabel_cspolicy_binding <args>

    '''

    result = {}

    payload = {'cspolicylabel_cspolicy_binding': {}}

    if priority:
        payload['cspolicylabel_cspolicy_binding']['priority'] = priority

    if policyname:
        payload['cspolicylabel_cspolicy_binding']['policyname'] = policyname

    if labelname:
        payload['cspolicylabel_cspolicy_binding']['labelname'] = labelname

    if targetvserver:
        payload['cspolicylabel_cspolicy_binding']['targetvserver'] = targetvserver

    if invoke_labelname:
        payload['cspolicylabel_cspolicy_binding']['invoke_labelname'] = invoke_labelname

    if gotopriorityexpression:
        payload['cspolicylabel_cspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['cspolicylabel_cspolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['cspolicylabel_cspolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/cspolicylabel_cspolicy_binding', payload)

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


def add_csvserver(name=None, td=None, servicetype=None, ipv46=None, targettype=None, dnsrecordtype=None,
                  persistenceid=None, ippattern=None, ipmask=None, range=None, port=None, state=None, stateupdate=None,
                  cacheable=None, redirecturl=None, clttimeout=None, precedence=None, casesensitive=None, somethod=None,
                  sopersistence=None, sopersistencetimeout=None, sothreshold=None, sobackupaction=None,
                  redirectportrewrite=None, downstateflush=None, backupvserver=None, disableprimaryondown=None,
                  insertvserveripport=None, vipheader=None, rtspnat=None, authenticationhost=None, authentication=None,
                  listenpolicy=None, listenpriority=None, authn401=None, authnvsname=None, push=None, pushvserver=None,
                  pushlabel=None, pushmulticlients=None, tcpprofilename=None, httpprofilename=None, dbprofilename=None,
                  oracleserverversion=None, comment=None, mssqlserverversion=None, l2conn=None,
                  mysqlprotocolversion=None, mysqlserverversion=None, mysqlcharacterset=None,
                  mysqlservercapabilities=None, appflowlog=None, netprofile=None, icmpvsrresponse=None, rhistate=None,
                  authnprofile=None, dnsprofilename=None, domainname=None, ttl=None, backupip=None, cookiedomain=None,
                  cookietimeout=None, sitedomainttl=None, newname=None, save=False):
    '''
    Add a new csvserver to the running configuration.

    name(str): Name for the content switching virtual server. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters.  Cannot be changed after the CS virtual server is created. The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, my server or my server). Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    servicetype(str): Protocol used by the virtual server. Possible values = HTTP, SSL, TCP, FTP, RTSP, SSL_TCP, UDP, DNS,
        SIP_UDP, SIP_TCP, SIP_SSL, ANY, RADIUS, RDP, MYSQL, MSSQL, DIAMETER, SSL_DIAMETER, DNS_TCP, ORACLE, SMPP

    ipv46(str): IP address of the content switching virtual server. Minimum length = 1

    targettype(str): Virtual server target type. Possible values = GSLB

    dnsrecordtype(str): . Default value: NSGSLB_IPV4 Possible values = A, AAAA, CNAME, NAPTR

    persistenceid(int): . Minimum value = 0 Maximum value = 65535

    ippattern(str): IP address pattern, in dotted decimal notation, for identifying packets to be accepted by the virtual
        server. The IP Mask parameter specifies which part of the destination IP address is matched against the pattern.
        Mutually exclusive with the IP Address parameter.  For example, if the IP pattern assigned to the virtual server
        is 198.51.100.0 and the IP mask is 255.255.240.0 (a forward mask), the first 20 bits in the destination IP
        addresses are matched with the first 20 bits in the pattern. The virtual server accepts requests with IP
        addresses that range from 198.51.96.1 to 198.51.111.254. You can also use a pattern such as 0.0.2.2 and a mask
        such as 0.0.255.255 (a reverse mask). If a destination IP address matches more than one IP pattern, the pattern
        with the longest match is selected, and the associated virtual server processes the request. For example, if the
        virtual servers, vs1 and vs2, have the same IP pattern, 0.0.100.128, but different IP masks of 0.0.255.255 and
        0.0.224.255, a destination IP address of 198.51.100.128 has the longest match with the IP pattern of vs1. If a
        destination IP address matches two or more virtual servers to the same extent, the request is processed by the
        virtual server whose port number matches the port number in the request.

    ipmask(str): IP mask, in dotted decimal notation, for the IP Pattern parameter. Can have leading or trailing non-zero
        octets (for example, 255.255.240.0 or 0.0.255.255). Accordingly, the mask specifies whether the first n bits or
        the last n bits of the destination IP address in a client request are to be matched with the corresponding bits
        in the IP pattern. The former is called a forward mask. The latter is called a reverse mask.

    range(int): Number of consecutive IP addresses, starting with the address specified by the IP Address parameter, to
        include in a range of addresses assigned to this virtual server. Default value: 1 Minimum value = 1 Maximum value
        = 254

    port(int): Port number for content switching virtual server. Minimum value = 1 Range 1 - 65535 * in CLI is represented as
        65535 in NITRO API

    state(str): Initial state of the load balancing virtual server. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    stateupdate(str): Enable state updates for a specific content switching virtual server. By default, the Content Switching
        virtual server is always UP, regardless of the state of the Load Balancing virtual servers bound to it. This
        parameter interacts with the global setting as follows: Global Level | Vserver Level | Result ENABLED ENABLED
        ENABLED ENABLED DISABLED ENABLED DISABLED ENABLED ENABLED DISABLED DISABLED DISABLED If you want to enable state
        updates for only some content switching virtual servers, be sure to disable the state update parameter. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    cacheable(str): Use this option to specify whether a virtual server, used for load balancing or content switching, routes
        requests to the cache redirection virtual server before sending it to the configured servers. Default value: NO
        Possible values = YES, NO

    redirecturl(str): URL to which traffic is redirected if the virtual server becomes unavailable. The service type of the
        virtual server should be either HTTP or SSL. Caution: Make sure that the domain in the URL does not match the
        domain specified for a content switching policy. If it does, requests are continuously redirected to the
        unavailable virtual server. Minimum length = 1

    clttimeout(int): Idle time, in seconds, after which the client connection is terminated. The default values are: 180
        seconds for HTTP/SSL-based services. 9000 seconds for other TCP-based services. 120 seconds for DNS-based
        services. 120 seconds for other UDP-based services. Minimum value = 0 Maximum value = 31536000

    precedence(str): Type of precedence to use for both RULE-based and URL-based policies on the content switching virtual
        server. With the default (RULE) setting, incoming requests are evaluated against the rule-based content switching
        policies. If none of the rules match, the URL in the request is evaluated against the URL-based content switching
        policies. Default value: RULE Possible values = RULE, URL

    casesensitive(str): Consider case in URLs (for policies that use URLs instead of RULES). For example, with the ON
        setting, the URLs /a/1.html and /A/1.HTML are treated differently and can have different targets (set by content
        switching policies). With the OFF setting, /a/1.html and /A/1.HTML are switched to the same target. Default
        value: ON Possible values = ON, OFF

    somethod(str): Type of spillover used to divert traffic to the backup virtual server when the primary virtual server
        reaches the spillover threshold. Connection spillover is based on the number of connections. Bandwidth spillover
        is based on the total Kbps of incoming and outgoing traffic. Possible values = CONNECTION, DYNAMICCONNECTION,
        BANDWIDTH, HEALTH, NONE

    sopersistence(str): Maintain source-IP based persistence on primary and backup virtual servers. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    sopersistencetimeout(int): Time-out value, in minutes, for spillover persistence. Default value: 2 Minimum value = 2
        Maximum value = 1440

    sothreshold(int): Depending on the spillover method, the maximum number of connections or the maximum total bandwidth
        (Kbps) that a virtual server can handle before spillover occurs. Minimum value = 1 Maximum value = 4294967287

    sobackupaction(str): Action to be performed if spillover is to take effect, but no backup chain to spillover is usable or
        exists. Possible values = DROP, ACCEPT, REDIRECT

    redirectportrewrite(str): State of port rewrite while performing HTTP redirect. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    downstateflush(str): Flush all active transactions associated with a virtual server whose state transitions from UP to
        DOWN. Do not enable this option for applications that must complete their transactions. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    backupvserver(str): Name of the backup virtual server that you are configuring. Must begin with an ASCII alphanumeric or
        underscore (_) character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space,
        colon (:), at sign (@), equal sign (=), and hyphen (-) characters. Can be changed after the backup virtual server
        is created. You can assign a different backup virtual server or rename the existing virtual server. The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks. Minimum length = 1

    disableprimaryondown(str): Continue forwarding the traffic to backup virtual server even after the primary server comes
        UP from the DOWN state. Default value: DISABLED Possible values = ENABLED, DISABLED

    insertvserveripport(str): Insert the virtual servers VIP address and port number in the request header. Available values
        function as follows:  VIPADDR - Header contains the vservers IP address and port number without any translation.
        OFF - The virtual IP and port header insertion option is disabled.  V6TOV4MAPPING - Header contains the mapped
        IPv4 address corresponding to the IPv6 address of the vserver and the port number. An IPv6 address can be mapped
        to a user-specified IPv4 address using the set ns ip6 command. Possible values = OFF, VIPADDR, V6TOV4MAPPING

    vipheader(str): Name of virtual server IP and port header, for use with the VServer IP Port Insertion parameter. Minimum
        length = 1

    rtspnat(str): Enable network address translation (NAT) for real-time streaming protocol (RTSP) connections. Default
        value: OFF Possible values = ON, OFF

    authenticationhost(str): FQDN of the authentication virtual server. The service type of the virtual server should be
        either HTTP or SSL. Minimum length = 3 Maximum length = 252

    authentication(str): Authenticate users who request a connection to the content switching virtual server. Default value:
        OFF Possible values = ON, OFF

    listenpolicy(str): String specifying the listen policy for the content switching virtual server. Can be either the name
        of an existing expression or an in-line expression. Default value: "NONE"

    listenpriority(int): Integer specifying the priority of the listen policy. A higher number specifies a lower priority. If
        a request matches the listen policies of more than one virtual server the virtual server whose listen policy has
        the highest priority (the lowest priority number) accepts the request. Default value: 101 Minimum value = 0
        Maximum value = 100

    authn401(str): Enable HTTP 401-response based authentication. Default value: OFF Possible values = ON, OFF

    authnvsname(str): Name of authentication virtual server that authenticates the incoming user requests to this content
        switching virtual server. . Minimum length = 1 Maximum length = 252

    push(str): Process traffic with the push virtual server that is bound to this content switching virtual server (specified
        by the Push VServer parameter). The service type of the push virtual server should be either HTTP or SSL. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    pushvserver(str): Name of the load balancing virtual server, of type PUSH or SSL_PUSH, to which the server pushes updates
        received on the client-facing load balancing virtual server. Minimum length = 1

    pushlabel(str): Expression for extracting the label from the response received from server. This string can be either an
        existing rule name or an inline expression. The service type of the virtual server should be either HTTP or SSL.
        Default value: "none"

    pushmulticlients(str): Allow multiple Web 2.0 connections from the same client to connect to the virtual server and
        expect updates. Default value: NO Possible values = YES, NO

    tcpprofilename(str): Name of the TCP profile containing TCP configuration settings for the virtual server. Minimum length
        = 1 Maximum length = 127

    httpprofilename(str): Name of the HTTP profile containing HTTP configuration settings for the virtual server. The service
        type of the virtual server should be either HTTP or SSL. Minimum length = 1 Maximum length = 127

    dbprofilename(str): Name of the DB profile. Minimum length = 1 Maximum length = 127

    oracleserverversion(str): Oracle server version. Default value: 10G Possible values = 10G, 11G

    comment(str): Information about this virtual server.

    mssqlserverversion(str): The version of the MSSQL server. Default value: 2008R2 Possible values = 70, 2000, 2000SP1,
        2005, 2008, 2008R2, 2012, 2014

    l2conn(str): Use L2 Parameters to identify a connection. Possible values = ON, OFF

    mysqlprotocolversion(int): The protocol version returned by the mysql vserver. Default value: 10

    mysqlserverversion(str): The server version string returned by the mysql vserver. Minimum length = 1 Maximum length = 31

    mysqlcharacterset(int): The character set returned by the mysql vserver. Default value: 8

    mysqlservercapabilities(int): The server capabilities returned by the mysql vserver. Default value: 41613

    appflowlog(str): Enable logging appflow flow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    netprofile(str): The name of the network profile. Minimum length = 1 Maximum length = 127

    icmpvsrresponse(str): Can be active or passive. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    rhistate(str): A host route is injected according to the setting on the virtual servers  * If set to PASSIVE on all the
        virtual servers that share the IP address, the appliance always injects the hostroute.  * If set to ACTIVE on all
        the virtual servers that share the IP address, the appliance injects even if one virtual server is UP.  * If set
        to ACTIVE on some virtual servers and PASSIVE on the others, the appliance, injects even if one virtual server
        set to ACTIVE is UP. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    authnprofile(str): Name of the authentication profile to be used when authentication is turned on.

    dnsprofilename(str): Name of the DNS profile to be associated with the VServer. DNS profile properties will applied to
        the transactions processed by a VServer. This parameter is valid only for DNS and DNS-TCP VServers. Minimum
        length = 1 Maximum length = 127

    domainname(str): Domain name for which to change the time to live (TTL) and/or backup service IP address. Minimum length
        = 1

    ttl(int): . Minimum value = 1

    backupip(str): . Minimum length = 1

    cookiedomain(str): . Minimum length = 1

    cookietimeout(int): . Minimum value = 0 Maximum value = 1440

    sitedomainttl(int): . Minimum value = 1

    newname(str): New name for the virtual server. Must begin with an ASCII alphanumeric or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign
        (=), and hyphen (-) characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my name" or my
        name). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver <args>

    '''

    result = {}

    payload = {'csvserver': {}}

    if name:
        payload['csvserver']['name'] = name

    if td:
        payload['csvserver']['td'] = td

    if servicetype:
        payload['csvserver']['servicetype'] = servicetype

    if ipv46:
        payload['csvserver']['ipv46'] = ipv46

    if targettype:
        payload['csvserver']['targettype'] = targettype

    if dnsrecordtype:
        payload['csvserver']['dnsrecordtype'] = dnsrecordtype

    if persistenceid:
        payload['csvserver']['persistenceid'] = persistenceid

    if ippattern:
        payload['csvserver']['ippattern'] = ippattern

    if ipmask:
        payload['csvserver']['ipmask'] = ipmask

    if range:
        payload['csvserver']['range'] = range

    if port:
        payload['csvserver']['port'] = port

    if state:
        payload['csvserver']['state'] = state

    if stateupdate:
        payload['csvserver']['stateupdate'] = stateupdate

    if cacheable:
        payload['csvserver']['cacheable'] = cacheable

    if redirecturl:
        payload['csvserver']['redirecturl'] = redirecturl

    if clttimeout:
        payload['csvserver']['clttimeout'] = clttimeout

    if precedence:
        payload['csvserver']['precedence'] = precedence

    if casesensitive:
        payload['csvserver']['casesensitive'] = casesensitive

    if somethod:
        payload['csvserver']['somethod'] = somethod

    if sopersistence:
        payload['csvserver']['sopersistence'] = sopersistence

    if sopersistencetimeout:
        payload['csvserver']['sopersistencetimeout'] = sopersistencetimeout

    if sothreshold:
        payload['csvserver']['sothreshold'] = sothreshold

    if sobackupaction:
        payload['csvserver']['sobackupaction'] = sobackupaction

    if redirectportrewrite:
        payload['csvserver']['redirectportrewrite'] = redirectportrewrite

    if downstateflush:
        payload['csvserver']['downstateflush'] = downstateflush

    if backupvserver:
        payload['csvserver']['backupvserver'] = backupvserver

    if disableprimaryondown:
        payload['csvserver']['disableprimaryondown'] = disableprimaryondown

    if insertvserveripport:
        payload['csvserver']['insertvserveripport'] = insertvserveripport

    if vipheader:
        payload['csvserver']['vipheader'] = vipheader

    if rtspnat:
        payload['csvserver']['rtspnat'] = rtspnat

    if authenticationhost:
        payload['csvserver']['authenticationhost'] = authenticationhost

    if authentication:
        payload['csvserver']['authentication'] = authentication

    if listenpolicy:
        payload['csvserver']['listenpolicy'] = listenpolicy

    if listenpriority:
        payload['csvserver']['listenpriority'] = listenpriority

    if authn401:
        payload['csvserver']['authn401'] = authn401

    if authnvsname:
        payload['csvserver']['authnvsname'] = authnvsname

    if push:
        payload['csvserver']['push'] = push

    if pushvserver:
        payload['csvserver']['pushvserver'] = pushvserver

    if pushlabel:
        payload['csvserver']['pushlabel'] = pushlabel

    if pushmulticlients:
        payload['csvserver']['pushmulticlients'] = pushmulticlients

    if tcpprofilename:
        payload['csvserver']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['csvserver']['httpprofilename'] = httpprofilename

    if dbprofilename:
        payload['csvserver']['dbprofilename'] = dbprofilename

    if oracleserverversion:
        payload['csvserver']['oracleserverversion'] = oracleserverversion

    if comment:
        payload['csvserver']['comment'] = comment

    if mssqlserverversion:
        payload['csvserver']['mssqlserverversion'] = mssqlserverversion

    if l2conn:
        payload['csvserver']['l2conn'] = l2conn

    if mysqlprotocolversion:
        payload['csvserver']['mysqlprotocolversion'] = mysqlprotocolversion

    if mysqlserverversion:
        payload['csvserver']['mysqlserverversion'] = mysqlserverversion

    if mysqlcharacterset:
        payload['csvserver']['mysqlcharacterset'] = mysqlcharacterset

    if mysqlservercapabilities:
        payload['csvserver']['mysqlservercapabilities'] = mysqlservercapabilities

    if appflowlog:
        payload['csvserver']['appflowlog'] = appflowlog

    if netprofile:
        payload['csvserver']['netprofile'] = netprofile

    if icmpvsrresponse:
        payload['csvserver']['icmpvsrresponse'] = icmpvsrresponse

    if rhistate:
        payload['csvserver']['rhistate'] = rhistate

    if authnprofile:
        payload['csvserver']['authnprofile'] = authnprofile

    if dnsprofilename:
        payload['csvserver']['dnsprofilename'] = dnsprofilename

    if domainname:
        payload['csvserver']['domainname'] = domainname

    if ttl:
        payload['csvserver']['ttl'] = ttl

    if backupip:
        payload['csvserver']['backupip'] = backupip

    if cookiedomain:
        payload['csvserver']['cookiedomain'] = cookiedomain

    if cookietimeout:
        payload['csvserver']['cookietimeout'] = cookietimeout

    if sitedomainttl:
        payload['csvserver']['sitedomainttl'] = sitedomainttl

    if newname:
        payload['csvserver']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/csvserver', payload)

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


def add_csvserver_appflowpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                        targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                        save=False):
    '''
    Add a new csvserver_appflowpolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_appflowpolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_appflowpolicy_binding': {}}

    if priority:
        payload['csvserver_appflowpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_appflowpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_appflowpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_appflowpolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_appflowpolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_appflowpolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_appflowpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_appflowpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_appflowpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_appflowpolicy_binding', payload)

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


def add_csvserver_appfwpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                      save=False):
    '''
    Add a new csvserver_appfwpolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_appfwpolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_appfwpolicy_binding': {}}

    if priority:
        payload['csvserver_appfwpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_appfwpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_appfwpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_appfwpolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_appfwpolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_appfwpolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_appfwpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_appfwpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_appfwpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_appfwpolicy_binding', payload)

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


def add_csvserver_appqoepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                       targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                       save=False):
    '''
    Add a new csvserver_appqoepolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_appqoepolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_appqoepolicy_binding': {}}

    if priority:
        payload['csvserver_appqoepolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_appqoepolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_appqoepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_appqoepolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_appqoepolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_appqoepolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_appqoepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_appqoepolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_appqoepolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_appqoepolicy_binding', payload)

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


def add_csvserver_auditnslogpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                           gotopriorityexpression=None, targetlbvserver=None, invoke=None,
                                           labeltype=None, save=False):
    '''
    Add a new csvserver_auditnslogpolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    gotopriorityexpression(str): Expression or other value specifying the next policy to be evaluated if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a priority
        number that is numerically higher than the highest numbered priority, policy evaluation ends. An UNDEF event is
        triggered if: * The expression is invalid. * The expression evaluates to a priority number that is numerically
        lower than the current policys priority. * The expression evaluates to a priority number that is between the
        current policys priority number (say, 30) and the highest priority number (say, 100), but does not match any
        configured priority number (for example, the expression evaluates to the number 85). This example assumes that
        the priority number increments by 10 for every successive policy, and therefore a priority number of 85 does not
        exist in the policy label.

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_auditnslogpolicy_binding': {}}

    if priority:
        payload['csvserver_auditnslogpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_auditnslogpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_auditnslogpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_auditnslogpolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_auditnslogpolicy_binding']['name'] = name

    if gotopriorityexpression:
        payload['csvserver_auditnslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if targetlbvserver:
        payload['csvserver_auditnslogpolicy_binding']['targetlbvserver'] = targetlbvserver

    if invoke:
        payload['csvserver_auditnslogpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_auditnslogpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_auditnslogpolicy_binding', payload)

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


def add_csvserver_auditsyslogpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                            gotopriorityexpression=None, targetlbvserver=None, invoke=None,
                                            labeltype=None, save=False):
    '''
    Add a new csvserver_auditsyslogpolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    gotopriorityexpression(str): Expression or other value specifying the next policy to be evaluated if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a priority
        number that is numerically higher than the highest numbered priority, policy evaluation ends. An UNDEF event is
        triggered if: * The expression is invalid. * The expression evaluates to a priority number that is numerically
        lower than the current policys priority. * The expression evaluates to a priority number that is between the
        current policys priority number (say, 30) and the highest priority number (say, 100), but does not match any
        configured priority number (for example, the expression evaluates to the number 85). This example assumes that
        the priority number increments by 10 for every successive policy, and therefore a priority number of 85 does not
        exist in the policy label.

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_auditsyslogpolicy_binding': {}}

    if priority:
        payload['csvserver_auditsyslogpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_auditsyslogpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_auditsyslogpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_auditsyslogpolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_auditsyslogpolicy_binding']['name'] = name

    if gotopriorityexpression:
        payload['csvserver_auditsyslogpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if targetlbvserver:
        payload['csvserver_auditsyslogpolicy_binding']['targetlbvserver'] = targetlbvserver

    if invoke:
        payload['csvserver_auditsyslogpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_auditsyslogpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_auditsyslogpolicy_binding', payload)

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


def add_csvserver_authorizationpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                              targetlbvserver=None, gotopriorityexpression=None, invoke=None,
                                              labeltype=None, save=False):
    '''
    Add a new csvserver_authorizationpolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_authorizationpolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_authorizationpolicy_binding': {}}

    if priority:
        payload['csvserver_authorizationpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_authorizationpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_authorizationpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_authorizationpolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_authorizationpolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_authorizationpolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_authorizationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_authorizationpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_authorizationpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_authorizationpolicy_binding', payload)

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


def add_csvserver_cachepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                      save=False):
    '''
    Add a new csvserver_cachepolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_cachepolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_cachepolicy_binding': {}}

    if priority:
        payload['csvserver_cachepolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_cachepolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_cachepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_cachepolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_cachepolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_cachepolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_cachepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_cachepolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_cachepolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_cachepolicy_binding', payload)

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


def add_csvserver_cmppolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                    save=False):
    '''
    Add a new csvserver_cmppolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_cmppolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_cmppolicy_binding': {}}

    if priority:
        payload['csvserver_cmppolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_cmppolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_cmppolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_cmppolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_cmppolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_cmppolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_cmppolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_cmppolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_cmppolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_cmppolicy_binding', payload)

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


def add_csvserver_cspolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                   gotopriorityexpression=None, targetlbvserver=None, invoke=None, labeltype=None,
                                   save=False):
    '''
    Add a new csvserver_cspolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    targetlbvserver(str): target vserver name.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_cspolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_cspolicy_binding': {}}

    if priority:
        payload['csvserver_cspolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_cspolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_cspolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_cspolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_cspolicy_binding']['name'] = name

    if gotopriorityexpression:
        payload['csvserver_cspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if targetlbvserver:
        payload['csvserver_cspolicy_binding']['targetlbvserver'] = targetlbvserver

    if invoke:
        payload['csvserver_cspolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_cspolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_cspolicy_binding', payload)

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


def add_csvserver_domain_binding(backupip=None, ttl=None, name=None, domainname=None, sitedomainttl=None,
                                 cookiedomain=None, cookietimeout=None, save=False):
    '''
    Add a new csvserver_domain_binding to the running configuration.

    backupip(str): . Minimum length = 1

    ttl(int): . Minimum value = 1

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    domainname(str): Domain name for which to change the time to live (TTL) and/or backup service IP address. Minimum length
        = 1

    sitedomainttl(int): . Minimum value = 1

    cookiedomain(str): . Minimum length = 1

    cookietimeout(int): . Minimum value = 0 Maximum value = 1440

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_domain_binding <args>

    '''

    result = {}

    payload = {'csvserver_domain_binding': {}}

    if backupip:
        payload['csvserver_domain_binding']['backupip'] = backupip

    if ttl:
        payload['csvserver_domain_binding']['ttl'] = ttl

    if name:
        payload['csvserver_domain_binding']['name'] = name

    if domainname:
        payload['csvserver_domain_binding']['domainname'] = domainname

    if sitedomainttl:
        payload['csvserver_domain_binding']['sitedomainttl'] = sitedomainttl

    if cookiedomain:
        payload['csvserver_domain_binding']['cookiedomain'] = cookiedomain

    if cookietimeout:
        payload['csvserver_domain_binding']['cookietimeout'] = cookietimeout

    execution = __proxy__['citrixns.post']('config/csvserver_domain_binding', payload)

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


def add_csvserver_feopolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                    save=False):
    '''
    Add a new csvserver_feopolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_feopolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_feopolicy_binding': {}}

    if priority:
        payload['csvserver_feopolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_feopolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_feopolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_feopolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_feopolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_feopolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_feopolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_feopolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_feopolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_feopolicy_binding', payload)

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


def add_csvserver_filterpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                       gotopriorityexpression=None, targetlbvserver=None, invoke=None, labeltype=None,
                                       save=False):
    '''
    Add a new csvserver_filterpolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    gotopriorityexpression(str): Expression or other value specifying the next policy to be evaluated if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a priority
        number that is numerically higher than the highest numbered priority, policy evaluation ends. An UNDEF event is
        triggered if: * The expression is invalid. * The expression evaluates to a priority number that is numerically
        lower than the current policys priority. * The expression evaluates to a priority number that is between the
        current policys priority number (say, 30) and the highest priority number (say, 100), but does not match any
        configured priority number (for example, the expression evaluates to the number 85). This example assumes that
        the priority number increments by 10 for every successive policy, and therefore a priority number of 85 does not
        exist in the policy label.

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_filterpolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_filterpolicy_binding': {}}

    if priority:
        payload['csvserver_filterpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_filterpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_filterpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_filterpolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_filterpolicy_binding']['name'] = name

    if gotopriorityexpression:
        payload['csvserver_filterpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if targetlbvserver:
        payload['csvserver_filterpolicy_binding']['targetlbvserver'] = targetlbvserver

    if invoke:
        payload['csvserver_filterpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_filterpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_filterpolicy_binding', payload)

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


def add_csvserver_gslbvserver_binding(vserver=None, name=None, save=False):
    '''
    Add a new csvserver_gslbvserver_binding to the running configuration.

    vserver(str): Name of the default gslb or vpn vserver bound to CS vserver of type GSLB/VPN. For Example: bind cs vserver
        cs1 -vserver gslb1 or bind cs vserver cs1 -vserver vpn1. Minimum length = 1

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_gslbvserver_binding <args>

    '''

    result = {}

    payload = {'csvserver_gslbvserver_binding': {}}

    if vserver:
        payload['csvserver_gslbvserver_binding']['vserver'] = vserver

    if name:
        payload['csvserver_gslbvserver_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/csvserver_gslbvserver_binding', payload)

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


def add_csvserver_lbvserver_binding(name=None, targetvserver=None, lbvserver=None, save=False):
    '''
    Add a new csvserver_lbvserver_binding to the running configuration.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetvserver(str): The virtual server name (created with the add lb vserver command) to which content will be switched.
        Minimum length = 1

    lbvserver(str): Name of the default lb vserver bound. Use this param for Default binding only. For Example: bind cs
        vserver cs1 -lbvserver lb1. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_lbvserver_binding <args>

    '''

    result = {}

    payload = {'csvserver_lbvserver_binding': {}}

    if name:
        payload['csvserver_lbvserver_binding']['name'] = name

    if targetvserver:
        payload['csvserver_lbvserver_binding']['targetvserver'] = targetvserver

    if lbvserver:
        payload['csvserver_lbvserver_binding']['lbvserver'] = lbvserver

    execution = __proxy__['citrixns.post']('config/csvserver_lbvserver_binding', payload)

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


def add_csvserver_responderpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                          save=False):
    '''
    Add a new csvserver_responderpolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_responderpolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_responderpolicy_binding': {}}

    if priority:
        payload['csvserver_responderpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_responderpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_responderpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_responderpolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_responderpolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_responderpolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_responderpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_responderpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_responderpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_responderpolicy_binding', payload)

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


def add_csvserver_rewritepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                        targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                        save=False):
    '''
    Add a new csvserver_rewritepolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_rewritepolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_rewritepolicy_binding': {}}

    if priority:
        payload['csvserver_rewritepolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_rewritepolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_rewritepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_rewritepolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_rewritepolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_rewritepolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_rewritepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_rewritepolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_rewritepolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_rewritepolicy_binding', payload)

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


def add_csvserver_spilloverpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                          save=False):
    '''
    Add a new csvserver_spilloverpolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_spilloverpolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_spilloverpolicy_binding': {}}

    if priority:
        payload['csvserver_spilloverpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_spilloverpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_spilloverpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_spilloverpolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_spilloverpolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_spilloverpolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_spilloverpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_spilloverpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_spilloverpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_spilloverpolicy_binding', payload)

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


def add_csvserver_tmtrafficpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          gotopriorityexpression=None, targetlbvserver=None, invoke=None, labeltype=None,
                                          save=False):
    '''
    Add a new csvserver_tmtrafficpolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    gotopriorityexpression(str): Expression or other value specifying the next policy to be evaluated if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a priority
        number that is numerically higher than the highest numbered priority, policy evaluation ends. An UNDEF event is
        triggered if: * The expression is invalid. * The expression evaluates to a priority number that is numerically
        lower than the current policys priority. * The expression evaluates to a priority number that is between the
        current policys priority number (say, 30) and the highest priority number (say, 100), but does not match any
        configured priority number (for example, the expression evaluates to the number 85). This example assumes that
        the priority number increments by 10 for every successive policy, and therefore a priority number of 85 does not
        exist in the policy label.

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_tmtrafficpolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_tmtrafficpolicy_binding': {}}

    if priority:
        payload['csvserver_tmtrafficpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_tmtrafficpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_tmtrafficpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_tmtrafficpolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_tmtrafficpolicy_binding']['name'] = name

    if gotopriorityexpression:
        payload['csvserver_tmtrafficpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if targetlbvserver:
        payload['csvserver_tmtrafficpolicy_binding']['targetlbvserver'] = targetlbvserver

    if invoke:
        payload['csvserver_tmtrafficpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_tmtrafficpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_tmtrafficpolicy_binding', payload)

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


def add_csvserver_transformpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                          save=False):
    '''
    Add a new csvserver_transformpolicy_binding to the running configuration.

    priority(int): Priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    targetlbvserver(str): Name of the Load Balancing virtual server to which the content is switched, if policy rule is
        evaluated to be TRUE. Example: bind cs vs cs1 -policyname pol1 -priority 101 -targetLBVserver lb1 Note: Use this
        parameter only in case of Content Switching policy bind operations to a CS vserver. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_transformpolicy_binding <args>

    '''

    result = {}

    payload = {'csvserver_transformpolicy_binding': {}}

    if priority:
        payload['csvserver_transformpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['csvserver_transformpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['csvserver_transformpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['csvserver_transformpolicy_binding']['labelname'] = labelname

    if name:
        payload['csvserver_transformpolicy_binding']['name'] = name

    if targetlbvserver:
        payload['csvserver_transformpolicy_binding']['targetlbvserver'] = targetlbvserver

    if gotopriorityexpression:
        payload['csvserver_transformpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['csvserver_transformpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['csvserver_transformpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/csvserver_transformpolicy_binding', payload)

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


def add_csvserver_vpnvserver_binding(vserver=None, name=None, save=False):
    '''
    Add a new csvserver_vpnvserver_binding to the running configuration.

    vserver(str): Name of the default gslb or vpn vserver bound to CS vserver of type GSLB/VPN. For Example: bind cs vserver
        cs1 -vserver gslb1 or bind cs vserver cs1 -vserver vpn1. Minimum length = 1

    name(str): Name of the content switching virtual server to which the content switching policy applies. Minimum length =
        1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.add_csvserver_vpnvserver_binding <args>

    '''

    result = {}

    payload = {'csvserver_vpnvserver_binding': {}}

    if vserver:
        payload['csvserver_vpnvserver_binding']['vserver'] = vserver

    if name:
        payload['csvserver_vpnvserver_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/csvserver_vpnvserver_binding', payload)

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


def disable_csvserver(name=None, save=False):
    '''
    Disables a csvserver matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.disable_csvserver name=foo

    '''

    result = {}

    payload = {'csvserver': {}}

    if name:
        payload['csvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/csvserver?action=disable', payload)

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


def enable_csvserver(name=None, save=False):
    '''
    Enables a csvserver matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.enable_csvserver name=foo

    '''

    result = {}

    payload = {'csvserver': {}}

    if name:
        payload['csvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/csvserver?action=enable', payload)

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


def get_csaction(name=None, targetlbvserver=None, targetvserver=None, targetvserverexpr=None, comment=None,
                 newname=None):
    '''
    Show the running configuration for the csaction config key.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    targetvserver(str): Filters results that only match the targetvserver field.

    targetvserverexpr(str): Filters results that only match the targetvserverexpr field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if targetvserverexpr:
        search_filter.append(['targetvserverexpr', targetvserverexpr])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csaction')

    return response


def get_csparameter():
    '''
    Show the running configuration for the csparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csparameter'), 'csparameter')

    return response


def get_cspolicy(policyname=None, url=None, rule=None, domain=None, action=None, logaction=None, newname=None):
    '''
    Show the running configuration for the cspolicy config key.

    policyname(str): Filters results that only match the policyname field.

    url(str): Filters results that only match the url field.

    rule(str): Filters results that only match the rule field.

    domain(str): Filters results that only match the domain field.

    action(str): Filters results that only match the action field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_cspolicy

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if url:
        search_filter.append(['url', url])

    if rule:
        search_filter.append(['rule', rule])

    if domain:
        search_filter.append(['domain', domain])

    if action:
        search_filter.append(['action', action])

    if logaction:
        search_filter.append(['logaction', logaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cspolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cspolicy')

    return response


def get_cspolicy_binding():
    '''
    Show the running configuration for the cspolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_cspolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cspolicy_binding'), 'cspolicy_binding')

    return response


def get_cspolicy_crvserver_binding(policyname=None, domain=None):
    '''
    Show the running configuration for the cspolicy_crvserver_binding config key.

    policyname(str): Filters results that only match the policyname field.

    domain(str): Filters results that only match the domain field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_cspolicy_crvserver_binding

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if domain:
        search_filter.append(['domain', domain])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cspolicy_crvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cspolicy_crvserver_binding')

    return response


def get_cspolicy_cspolicylabel_binding(policyname=None, domain=None):
    '''
    Show the running configuration for the cspolicy_cspolicylabel_binding config key.

    policyname(str): Filters results that only match the policyname field.

    domain(str): Filters results that only match the domain field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_cspolicy_cspolicylabel_binding

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if domain:
        search_filter.append(['domain', domain])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cspolicy_cspolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cspolicy_cspolicylabel_binding')

    return response


def get_cspolicy_csvserver_binding(policyname=None, domain=None):
    '''
    Show the running configuration for the cspolicy_csvserver_binding config key.

    policyname(str): Filters results that only match the policyname field.

    domain(str): Filters results that only match the domain field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_cspolicy_csvserver_binding

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if domain:
        search_filter.append(['domain', domain])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cspolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cspolicy_csvserver_binding')

    return response


def get_cspolicylabel(labelname=None, cspolicylabeltype=None, newname=None):
    '''
    Show the running configuration for the cspolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    cspolicylabeltype(str): Filters results that only match the cspolicylabeltype field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_cspolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if cspolicylabeltype:
        search_filter.append(['cspolicylabeltype', cspolicylabeltype])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cspolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cspolicylabel')

    return response


def get_cspolicylabel_binding():
    '''
    Show the running configuration for the cspolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_cspolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cspolicylabel_binding'), 'cspolicylabel_binding')

    return response


def get_cspolicylabel_cspolicy_binding(priority=None, policyname=None, labelname=None, targetvserver=None,
                                       invoke_labelname=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the cspolicylabel_cspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    targetvserver(str): Filters results that only match the targetvserver field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_cspolicylabel_cspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if invoke_labelname:
        search_filter.append(['invoke_labelname', invoke_labelname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/cspolicylabel_cspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'cspolicylabel_cspolicy_binding')

    return response


def get_csvserver(name=None, td=None, servicetype=None, ipv46=None, targettype=None, dnsrecordtype=None,
                  persistenceid=None, ippattern=None, ipmask=None, range=None, port=None, state=None, stateupdate=None,
                  cacheable=None, redirecturl=None, clttimeout=None, precedence=None, casesensitive=None, somethod=None,
                  sopersistence=None, sopersistencetimeout=None, sothreshold=None, sobackupaction=None,
                  redirectportrewrite=None, downstateflush=None, backupvserver=None, disableprimaryondown=None,
                  insertvserveripport=None, vipheader=None, rtspnat=None, authenticationhost=None, authentication=None,
                  listenpolicy=None, listenpriority=None, authn401=None, authnvsname=None, push=None, pushvserver=None,
                  pushlabel=None, pushmulticlients=None, tcpprofilename=None, httpprofilename=None, dbprofilename=None,
                  oracleserverversion=None, comment=None, mssqlserverversion=None, l2conn=None,
                  mysqlprotocolversion=None, mysqlserverversion=None, mysqlcharacterset=None,
                  mysqlservercapabilities=None, appflowlog=None, netprofile=None, icmpvsrresponse=None, rhistate=None,
                  authnprofile=None, dnsprofilename=None, domainname=None, ttl=None, backupip=None, cookiedomain=None,
                  cookietimeout=None, sitedomainttl=None, newname=None):
    '''
    Show the running configuration for the csvserver config key.

    name(str): Filters results that only match the name field.

    td(int): Filters results that only match the td field.

    servicetype(str): Filters results that only match the servicetype field.

    ipv46(str): Filters results that only match the ipv46 field.

    targettype(str): Filters results that only match the targettype field.

    dnsrecordtype(str): Filters results that only match the dnsrecordtype field.

    persistenceid(int): Filters results that only match the persistenceid field.

    ippattern(str): Filters results that only match the ippattern field.

    ipmask(str): Filters results that only match the ipmask field.

    range(int): Filters results that only match the range field.

    port(int): Filters results that only match the port field.

    state(str): Filters results that only match the state field.

    stateupdate(str): Filters results that only match the stateupdate field.

    cacheable(str): Filters results that only match the cacheable field.

    redirecturl(str): Filters results that only match the redirecturl field.

    clttimeout(int): Filters results that only match the clttimeout field.

    precedence(str): Filters results that only match the precedence field.

    casesensitive(str): Filters results that only match the casesensitive field.

    somethod(str): Filters results that only match the somethod field.

    sopersistence(str): Filters results that only match the sopersistence field.

    sopersistencetimeout(int): Filters results that only match the sopersistencetimeout field.

    sothreshold(int): Filters results that only match the sothreshold field.

    sobackupaction(str): Filters results that only match the sobackupaction field.

    redirectportrewrite(str): Filters results that only match the redirectportrewrite field.

    downstateflush(str): Filters results that only match the downstateflush field.

    backupvserver(str): Filters results that only match the backupvserver field.

    disableprimaryondown(str): Filters results that only match the disableprimaryondown field.

    insertvserveripport(str): Filters results that only match the insertvserveripport field.

    vipheader(str): Filters results that only match the vipheader field.

    rtspnat(str): Filters results that only match the rtspnat field.

    authenticationhost(str): Filters results that only match the authenticationhost field.

    authentication(str): Filters results that only match the authentication field.

    listenpolicy(str): Filters results that only match the listenpolicy field.

    listenpriority(int): Filters results that only match the listenpriority field.

    authn401(str): Filters results that only match the authn401 field.

    authnvsname(str): Filters results that only match the authnvsname field.

    push(str): Filters results that only match the push field.

    pushvserver(str): Filters results that only match the pushvserver field.

    pushlabel(str): Filters results that only match the pushlabel field.

    pushmulticlients(str): Filters results that only match the pushmulticlients field.

    tcpprofilename(str): Filters results that only match the tcpprofilename field.

    httpprofilename(str): Filters results that only match the httpprofilename field.

    dbprofilename(str): Filters results that only match the dbprofilename field.

    oracleserverversion(str): Filters results that only match the oracleserverversion field.

    comment(str): Filters results that only match the comment field.

    mssqlserverversion(str): Filters results that only match the mssqlserverversion field.

    l2conn(str): Filters results that only match the l2conn field.

    mysqlprotocolversion(int): Filters results that only match the mysqlprotocolversion field.

    mysqlserverversion(str): Filters results that only match the mysqlserverversion field.

    mysqlcharacterset(int): Filters results that only match the mysqlcharacterset field.

    mysqlservercapabilities(int): Filters results that only match the mysqlservercapabilities field.

    appflowlog(str): Filters results that only match the appflowlog field.

    netprofile(str): Filters results that only match the netprofile field.

    icmpvsrresponse(str): Filters results that only match the icmpvsrresponse field.

    rhistate(str): Filters results that only match the rhistate field.

    authnprofile(str): Filters results that only match the authnprofile field.

    dnsprofilename(str): Filters results that only match the dnsprofilename field.

    domainname(str): Filters results that only match the domainname field.

    ttl(int): Filters results that only match the ttl field.

    backupip(str): Filters results that only match the backupip field.

    cookiedomain(str): Filters results that only match the cookiedomain field.

    cookietimeout(int): Filters results that only match the cookietimeout field.

    sitedomainttl(int): Filters results that only match the sitedomainttl field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if td:
        search_filter.append(['td', td])

    if servicetype:
        search_filter.append(['servicetype', servicetype])

    if ipv46:
        search_filter.append(['ipv46', ipv46])

    if targettype:
        search_filter.append(['targettype', targettype])

    if dnsrecordtype:
        search_filter.append(['dnsrecordtype', dnsrecordtype])

    if persistenceid:
        search_filter.append(['persistenceid', persistenceid])

    if ippattern:
        search_filter.append(['ippattern', ippattern])

    if ipmask:
        search_filter.append(['ipmask', ipmask])

    if range:
        search_filter.append(['range', range])

    if port:
        search_filter.append(['port', port])

    if state:
        search_filter.append(['state', state])

    if stateupdate:
        search_filter.append(['stateupdate', stateupdate])

    if cacheable:
        search_filter.append(['cacheable', cacheable])

    if redirecturl:
        search_filter.append(['redirecturl', redirecturl])

    if clttimeout:
        search_filter.append(['clttimeout', clttimeout])

    if precedence:
        search_filter.append(['precedence', precedence])

    if casesensitive:
        search_filter.append(['casesensitive', casesensitive])

    if somethod:
        search_filter.append(['somethod', somethod])

    if sopersistence:
        search_filter.append(['sopersistence', sopersistence])

    if sopersistencetimeout:
        search_filter.append(['sopersistencetimeout', sopersistencetimeout])

    if sothreshold:
        search_filter.append(['sothreshold', sothreshold])

    if sobackupaction:
        search_filter.append(['sobackupaction', sobackupaction])

    if redirectportrewrite:
        search_filter.append(['redirectportrewrite', redirectportrewrite])

    if downstateflush:
        search_filter.append(['downstateflush', downstateflush])

    if backupvserver:
        search_filter.append(['backupvserver', backupvserver])

    if disableprimaryondown:
        search_filter.append(['disableprimaryondown', disableprimaryondown])

    if insertvserveripport:
        search_filter.append(['insertvserveripport', insertvserveripport])

    if vipheader:
        search_filter.append(['vipheader', vipheader])

    if rtspnat:
        search_filter.append(['rtspnat', rtspnat])

    if authenticationhost:
        search_filter.append(['authenticationhost', authenticationhost])

    if authentication:
        search_filter.append(['authentication', authentication])

    if listenpolicy:
        search_filter.append(['listenpolicy', listenpolicy])

    if listenpriority:
        search_filter.append(['listenpriority', listenpriority])

    if authn401:
        search_filter.append(['authn401', authn401])

    if authnvsname:
        search_filter.append(['authnvsname', authnvsname])

    if push:
        search_filter.append(['push', push])

    if pushvserver:
        search_filter.append(['pushvserver', pushvserver])

    if pushlabel:
        search_filter.append(['pushlabel', pushlabel])

    if pushmulticlients:
        search_filter.append(['pushmulticlients', pushmulticlients])

    if tcpprofilename:
        search_filter.append(['tcpprofilename', tcpprofilename])

    if httpprofilename:
        search_filter.append(['httpprofilename', httpprofilename])

    if dbprofilename:
        search_filter.append(['dbprofilename', dbprofilename])

    if oracleserverversion:
        search_filter.append(['oracleserverversion', oracleserverversion])

    if comment:
        search_filter.append(['comment', comment])

    if mssqlserverversion:
        search_filter.append(['mssqlserverversion', mssqlserverversion])

    if l2conn:
        search_filter.append(['l2conn', l2conn])

    if mysqlprotocolversion:
        search_filter.append(['mysqlprotocolversion', mysqlprotocolversion])

    if mysqlserverversion:
        search_filter.append(['mysqlserverversion', mysqlserverversion])

    if mysqlcharacterset:
        search_filter.append(['mysqlcharacterset', mysqlcharacterset])

    if mysqlservercapabilities:
        search_filter.append(['mysqlservercapabilities', mysqlservercapabilities])

    if appflowlog:
        search_filter.append(['appflowlog', appflowlog])

    if netprofile:
        search_filter.append(['netprofile', netprofile])

    if icmpvsrresponse:
        search_filter.append(['icmpvsrresponse', icmpvsrresponse])

    if rhistate:
        search_filter.append(['rhistate', rhistate])

    if authnprofile:
        search_filter.append(['authnprofile', authnprofile])

    if dnsprofilename:
        search_filter.append(['dnsprofilename', dnsprofilename])

    if domainname:
        search_filter.append(['domainname', domainname])

    if ttl:
        search_filter.append(['ttl', ttl])

    if backupip:
        search_filter.append(['backupip', backupip])

    if cookiedomain:
        search_filter.append(['cookiedomain', cookiedomain])

    if cookietimeout:
        search_filter.append(['cookietimeout', cookietimeout])

    if sitedomainttl:
        search_filter.append(['sitedomainttl', sitedomainttl])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver')

    return response


def get_csvserver_appflowpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                        targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the csvserver_appflowpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_appflowpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_appflowpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_appflowpolicy_binding')

    return response


def get_csvserver_appfwpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the csvserver_appfwpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_appfwpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_appfwpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_appfwpolicy_binding')

    return response


def get_csvserver_appqoepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                       targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the csvserver_appqoepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_appqoepolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_appqoepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_appqoepolicy_binding')

    return response


def get_csvserver_auditnslogpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                           gotopriorityexpression=None, targetlbvserver=None, invoke=None,
                                           labeltype=None):
    '''
    Show the running configuration for the csvserver_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_auditnslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_auditnslogpolicy_binding')

    return response


def get_csvserver_auditsyslogpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                            gotopriorityexpression=None, targetlbvserver=None, invoke=None,
                                            labeltype=None):
    '''
    Show the running configuration for the csvserver_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_auditsyslogpolicy_binding')

    return response


def get_csvserver_authorizationpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                              targetlbvserver=None, gotopriorityexpression=None, invoke=None,
                                              labeltype=None):
    '''
    Show the running configuration for the csvserver_authorizationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_authorizationpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_authorizationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_authorizationpolicy_binding')

    return response


def get_csvserver_binding():
    '''
    Show the running configuration for the csvserver_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_binding'), 'csvserver_binding')

    return response


def get_csvserver_cachepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the csvserver_cachepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_cachepolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_cachepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_cachepolicy_binding')

    return response


def get_csvserver_cmppolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the csvserver_cmppolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_cmppolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_cmppolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_cmppolicy_binding')

    return response


def get_csvserver_cspolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                   gotopriorityexpression=None, targetlbvserver=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the csvserver_cspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_cspolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_cspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_cspolicy_binding')

    return response


def get_csvserver_domain_binding(backupip=None, ttl=None, name=None, domainname=None, sitedomainttl=None,
                                 cookiedomain=None, cookietimeout=None):
    '''
    Show the running configuration for the csvserver_domain_binding config key.

    backupip(str): Filters results that only match the backupip field.

    ttl(int): Filters results that only match the ttl field.

    name(str): Filters results that only match the name field.

    domainname(str): Filters results that only match the domainname field.

    sitedomainttl(int): Filters results that only match the sitedomainttl field.

    cookiedomain(str): Filters results that only match the cookiedomain field.

    cookietimeout(int): Filters results that only match the cookietimeout field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_domain_binding

    '''

    search_filter = []

    if backupip:
        search_filter.append(['backupip', backupip])

    if ttl:
        search_filter.append(['ttl', ttl])

    if name:
        search_filter.append(['name', name])

    if domainname:
        search_filter.append(['domainname', domainname])

    if sitedomainttl:
        search_filter.append(['sitedomainttl', sitedomainttl])

    if cookiedomain:
        search_filter.append(['cookiedomain', cookiedomain])

    if cookietimeout:
        search_filter.append(['cookietimeout', cookietimeout])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_domain_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_domain_binding')

    return response


def get_csvserver_feopolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the csvserver_feopolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_feopolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_feopolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_feopolicy_binding')

    return response


def get_csvserver_filterpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                       gotopriorityexpression=None, targetlbvserver=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the csvserver_filterpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_filterpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_filterpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_filterpolicy_binding')

    return response


def get_csvserver_gslbvserver_binding(vserver=None, name=None):
    '''
    Show the running configuration for the csvserver_gslbvserver_binding config key.

    vserver(str): Filters results that only match the vserver field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_gslbvserver_binding

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_gslbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_gslbvserver_binding')

    return response


def get_csvserver_lbvserver_binding(name=None, targetvserver=None, lbvserver=None):
    '''
    Show the running configuration for the csvserver_lbvserver_binding config key.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    lbvserver(str): Filters results that only match the lbvserver field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_lbvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if lbvserver:
        search_filter.append(['lbvserver', lbvserver])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_lbvserver_binding')

    return response


def get_csvserver_responderpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          targetlbvserver=None, gotopriorityexpression=None, invoke=None,
                                          labeltype=None):
    '''
    Show the running configuration for the csvserver_responderpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_responderpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_responderpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_responderpolicy_binding')

    return response


def get_csvserver_rewritepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                        targetlbvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the csvserver_rewritepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_rewritepolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_rewritepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_rewritepolicy_binding')

    return response


def get_csvserver_spilloverpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          targetlbvserver=None, gotopriorityexpression=None, invoke=None,
                                          labeltype=None):
    '''
    Show the running configuration for the csvserver_spilloverpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_spilloverpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_spilloverpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_spilloverpolicy_binding')

    return response


def get_csvserver_tmtrafficpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          gotopriorityexpression=None, targetlbvserver=None, invoke=None,
                                          labeltype=None):
    '''
    Show the running configuration for the csvserver_tmtrafficpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_tmtrafficpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_tmtrafficpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_tmtrafficpolicy_binding')

    return response


def get_csvserver_transformpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          targetlbvserver=None, gotopriorityexpression=None, invoke=None,
                                          labeltype=None):
    '''
    Show the running configuration for the csvserver_transformpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetlbvserver(str): Filters results that only match the targetlbvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_transformpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if bindpoint:
        search_filter.append(['bindpoint', bindpoint])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if name:
        search_filter.append(['name', name])

    if targetlbvserver:
        search_filter.append(['targetlbvserver', targetlbvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_transformpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_transformpolicy_binding')

    return response


def get_csvserver_vpnvserver_binding(vserver=None, name=None):
    '''
    Show the running configuration for the csvserver_vpnvserver_binding config key.

    vserver(str): Filters results that only match the vserver field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.get_csvserver_vpnvserver_binding

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/csvserver_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'csvserver_vpnvserver_binding')

    return response


def unset_csaction(name=None, targetlbvserver=None, targetvserver=None, targetvserverexpr=None, comment=None,
                   newname=None, save=False):
    '''
    Unsets values from the csaction configuration key.

    name(bool): Unsets the name value.

    targetlbvserver(bool): Unsets the targetlbvserver value.

    targetvserver(bool): Unsets the targetvserver value.

    targetvserverexpr(bool): Unsets the targetvserverexpr value.

    comment(bool): Unsets the comment value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.unset_csaction <args>

    '''

    result = {}

    payload = {'csaction': {}}

    if name:
        payload['csaction']['name'] = True

    if targetlbvserver:
        payload['csaction']['targetlbvserver'] = True

    if targetvserver:
        payload['csaction']['targetvserver'] = True

    if targetvserverexpr:
        payload['csaction']['targetvserverexpr'] = True

    if comment:
        payload['csaction']['comment'] = True

    if newname:
        payload['csaction']['newname'] = True

    execution = __proxy__['citrixns.post']('config/csaction?action=unset', payload)

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


def unset_csparameter(stateupdate=None, save=False):
    '''
    Unsets values from the csparameter configuration key.

    stateupdate(bool): Unsets the stateupdate value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.unset_csparameter <args>

    '''

    result = {}

    payload = {'csparameter': {}}

    if stateupdate:
        payload['csparameter']['stateupdate'] = True

    execution = __proxy__['citrixns.post']('config/csparameter?action=unset', payload)

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


def unset_cspolicy(policyname=None, url=None, rule=None, domain=None, action=None, logaction=None, newname=None,
                   save=False):
    '''
    Unsets values from the cspolicy configuration key.

    policyname(bool): Unsets the policyname value.

    url(bool): Unsets the url value.

    rule(bool): Unsets the rule value.

    domain(bool): Unsets the domain value.

    action(bool): Unsets the action value.

    logaction(bool): Unsets the logaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.unset_cspolicy <args>

    '''

    result = {}

    payload = {'cspolicy': {}}

    if policyname:
        payload['cspolicy']['policyname'] = True

    if url:
        payload['cspolicy']['url'] = True

    if rule:
        payload['cspolicy']['rule'] = True

    if domain:
        payload['cspolicy']['domain'] = True

    if action:
        payload['cspolicy']['action'] = True

    if logaction:
        payload['cspolicy']['logaction'] = True

    if newname:
        payload['cspolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/cspolicy?action=unset', payload)

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


def unset_csvserver(name=None, td=None, servicetype=None, ipv46=None, targettype=None, dnsrecordtype=None,
                    persistenceid=None, ippattern=None, ipmask=None, range=None, port=None, state=None, stateupdate=None,
                    cacheable=None, redirecturl=None, clttimeout=None, precedence=None, casesensitive=None,
                    somethod=None, sopersistence=None, sopersistencetimeout=None, sothreshold=None, sobackupaction=None,
                    redirectportrewrite=None, downstateflush=None, backupvserver=None, disableprimaryondown=None,
                    insertvserveripport=None, vipheader=None, rtspnat=None, authenticationhost=None, authentication=None,
                    listenpolicy=None, listenpriority=None, authn401=None, authnvsname=None, push=None, pushvserver=None,
                    pushlabel=None, pushmulticlients=None, tcpprofilename=None, httpprofilename=None, dbprofilename=None,
                    oracleserverversion=None, comment=None, mssqlserverversion=None, l2conn=None,
                    mysqlprotocolversion=None, mysqlserverversion=None, mysqlcharacterset=None,
                    mysqlservercapabilities=None, appflowlog=None, netprofile=None, icmpvsrresponse=None, rhistate=None,
                    authnprofile=None, dnsprofilename=None, domainname=None, ttl=None, backupip=None, cookiedomain=None,
                    cookietimeout=None, sitedomainttl=None, newname=None, save=False):
    '''
    Unsets values from the csvserver configuration key.

    name(bool): Unsets the name value.

    td(bool): Unsets the td value.

    servicetype(bool): Unsets the servicetype value.

    ipv46(bool): Unsets the ipv46 value.

    targettype(bool): Unsets the targettype value.

    dnsrecordtype(bool): Unsets the dnsrecordtype value.

    persistenceid(bool): Unsets the persistenceid value.

    ippattern(bool): Unsets the ippattern value.

    ipmask(bool): Unsets the ipmask value.

    range(bool): Unsets the range value.

    port(bool): Unsets the port value.

    state(bool): Unsets the state value.

    stateupdate(bool): Unsets the stateupdate value.

    cacheable(bool): Unsets the cacheable value.

    redirecturl(bool): Unsets the redirecturl value.

    clttimeout(bool): Unsets the clttimeout value.

    precedence(bool): Unsets the precedence value.

    casesensitive(bool): Unsets the casesensitive value.

    somethod(bool): Unsets the somethod value.

    sopersistence(bool): Unsets the sopersistence value.

    sopersistencetimeout(bool): Unsets the sopersistencetimeout value.

    sothreshold(bool): Unsets the sothreshold value.

    sobackupaction(bool): Unsets the sobackupaction value.

    redirectportrewrite(bool): Unsets the redirectportrewrite value.

    downstateflush(bool): Unsets the downstateflush value.

    backupvserver(bool): Unsets the backupvserver value.

    disableprimaryondown(bool): Unsets the disableprimaryondown value.

    insertvserveripport(bool): Unsets the insertvserveripport value.

    vipheader(bool): Unsets the vipheader value.

    rtspnat(bool): Unsets the rtspnat value.

    authenticationhost(bool): Unsets the authenticationhost value.

    authentication(bool): Unsets the authentication value.

    listenpolicy(bool): Unsets the listenpolicy value.

    listenpriority(bool): Unsets the listenpriority value.

    authn401(bool): Unsets the authn401 value.

    authnvsname(bool): Unsets the authnvsname value.

    push(bool): Unsets the push value.

    pushvserver(bool): Unsets the pushvserver value.

    pushlabel(bool): Unsets the pushlabel value.

    pushmulticlients(bool): Unsets the pushmulticlients value.

    tcpprofilename(bool): Unsets the tcpprofilename value.

    httpprofilename(bool): Unsets the httpprofilename value.

    dbprofilename(bool): Unsets the dbprofilename value.

    oracleserverversion(bool): Unsets the oracleserverversion value.

    comment(bool): Unsets the comment value.

    mssqlserverversion(bool): Unsets the mssqlserverversion value.

    l2conn(bool): Unsets the l2conn value.

    mysqlprotocolversion(bool): Unsets the mysqlprotocolversion value.

    mysqlserverversion(bool): Unsets the mysqlserverversion value.

    mysqlcharacterset(bool): Unsets the mysqlcharacterset value.

    mysqlservercapabilities(bool): Unsets the mysqlservercapabilities value.

    appflowlog(bool): Unsets the appflowlog value.

    netprofile(bool): Unsets the netprofile value.

    icmpvsrresponse(bool): Unsets the icmpvsrresponse value.

    rhistate(bool): Unsets the rhistate value.

    authnprofile(bool): Unsets the authnprofile value.

    dnsprofilename(bool): Unsets the dnsprofilename value.

    domainname(bool): Unsets the domainname value.

    ttl(bool): Unsets the ttl value.

    backupip(bool): Unsets the backupip value.

    cookiedomain(bool): Unsets the cookiedomain value.

    cookietimeout(bool): Unsets the cookietimeout value.

    sitedomainttl(bool): Unsets the sitedomainttl value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.unset_csvserver <args>

    '''

    result = {}

    payload = {'csvserver': {}}

    if name:
        payload['csvserver']['name'] = True

    if td:
        payload['csvserver']['td'] = True

    if servicetype:
        payload['csvserver']['servicetype'] = True

    if ipv46:
        payload['csvserver']['ipv46'] = True

    if targettype:
        payload['csvserver']['targettype'] = True

    if dnsrecordtype:
        payload['csvserver']['dnsrecordtype'] = True

    if persistenceid:
        payload['csvserver']['persistenceid'] = True

    if ippattern:
        payload['csvserver']['ippattern'] = True

    if ipmask:
        payload['csvserver']['ipmask'] = True

    if range:
        payload['csvserver']['range'] = True

    if port:
        payload['csvserver']['port'] = True

    if state:
        payload['csvserver']['state'] = True

    if stateupdate:
        payload['csvserver']['stateupdate'] = True

    if cacheable:
        payload['csvserver']['cacheable'] = True

    if redirecturl:
        payload['csvserver']['redirecturl'] = True

    if clttimeout:
        payload['csvserver']['clttimeout'] = True

    if precedence:
        payload['csvserver']['precedence'] = True

    if casesensitive:
        payload['csvserver']['casesensitive'] = True

    if somethod:
        payload['csvserver']['somethod'] = True

    if sopersistence:
        payload['csvserver']['sopersistence'] = True

    if sopersistencetimeout:
        payload['csvserver']['sopersistencetimeout'] = True

    if sothreshold:
        payload['csvserver']['sothreshold'] = True

    if sobackupaction:
        payload['csvserver']['sobackupaction'] = True

    if redirectportrewrite:
        payload['csvserver']['redirectportrewrite'] = True

    if downstateflush:
        payload['csvserver']['downstateflush'] = True

    if backupvserver:
        payload['csvserver']['backupvserver'] = True

    if disableprimaryondown:
        payload['csvserver']['disableprimaryondown'] = True

    if insertvserveripport:
        payload['csvserver']['insertvserveripport'] = True

    if vipheader:
        payload['csvserver']['vipheader'] = True

    if rtspnat:
        payload['csvserver']['rtspnat'] = True

    if authenticationhost:
        payload['csvserver']['authenticationhost'] = True

    if authentication:
        payload['csvserver']['authentication'] = True

    if listenpolicy:
        payload['csvserver']['listenpolicy'] = True

    if listenpriority:
        payload['csvserver']['listenpriority'] = True

    if authn401:
        payload['csvserver']['authn401'] = True

    if authnvsname:
        payload['csvserver']['authnvsname'] = True

    if push:
        payload['csvserver']['push'] = True

    if pushvserver:
        payload['csvserver']['pushvserver'] = True

    if pushlabel:
        payload['csvserver']['pushlabel'] = True

    if pushmulticlients:
        payload['csvserver']['pushmulticlients'] = True

    if tcpprofilename:
        payload['csvserver']['tcpprofilename'] = True

    if httpprofilename:
        payload['csvserver']['httpprofilename'] = True

    if dbprofilename:
        payload['csvserver']['dbprofilename'] = True

    if oracleserverversion:
        payload['csvserver']['oracleserverversion'] = True

    if comment:
        payload['csvserver']['comment'] = True

    if mssqlserverversion:
        payload['csvserver']['mssqlserverversion'] = True

    if l2conn:
        payload['csvserver']['l2conn'] = True

    if mysqlprotocolversion:
        payload['csvserver']['mysqlprotocolversion'] = True

    if mysqlserverversion:
        payload['csvserver']['mysqlserverversion'] = True

    if mysqlcharacterset:
        payload['csvserver']['mysqlcharacterset'] = True

    if mysqlservercapabilities:
        payload['csvserver']['mysqlservercapabilities'] = True

    if appflowlog:
        payload['csvserver']['appflowlog'] = True

    if netprofile:
        payload['csvserver']['netprofile'] = True

    if icmpvsrresponse:
        payload['csvserver']['icmpvsrresponse'] = True

    if rhistate:
        payload['csvserver']['rhistate'] = True

    if authnprofile:
        payload['csvserver']['authnprofile'] = True

    if dnsprofilename:
        payload['csvserver']['dnsprofilename'] = True

    if domainname:
        payload['csvserver']['domainname'] = True

    if ttl:
        payload['csvserver']['ttl'] = True

    if backupip:
        payload['csvserver']['backupip'] = True

    if cookiedomain:
        payload['csvserver']['cookiedomain'] = True

    if cookietimeout:
        payload['csvserver']['cookietimeout'] = True

    if sitedomainttl:
        payload['csvserver']['sitedomainttl'] = True

    if newname:
        payload['csvserver']['newname'] = True

    execution = __proxy__['citrixns.post']('config/csvserver?action=unset', payload)

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


def update_csaction(name=None, targetlbvserver=None, targetvserver=None, targetvserverexpr=None, comment=None,
                    newname=None, save=False):
    '''
    Update the running configuration for the csaction config key.

    name(str): Name for the content switching action. Must begin with an ASCII alphanumeric or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign
        (=), and hyphen (-) characters. Can be changed after the content switching action is created. The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my action" or my action).

    targetlbvserver(str): Name of the load balancing virtual server to which the content is switched.

    targetvserver(str): Name of the VPN virtual server to which the content is switched.

    targetvserverexpr(str): Information about this content switching action.

    comment(str): Comments associated with this cs action.

    newname(str): New name for the content switching action. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters.  The following requirement applies only to the NetScaler CLI: If
        the name includes one or more spaces, enclose the name in double or single quotation marks (for example, "my
        name" or my name). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.update_csaction <args>

    '''

    result = {}

    payload = {'csaction': {}}

    if name:
        payload['csaction']['name'] = name

    if targetlbvserver:
        payload['csaction']['targetlbvserver'] = targetlbvserver

    if targetvserver:
        payload['csaction']['targetvserver'] = targetvserver

    if targetvserverexpr:
        payload['csaction']['targetvserverexpr'] = targetvserverexpr

    if comment:
        payload['csaction']['comment'] = comment

    if newname:
        payload['csaction']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/csaction', payload)

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


def update_csparameter(stateupdate=None, save=False):
    '''
    Update the running configuration for the csparameter config key.

    stateupdate(str): Specifies whether the virtual server checks the attached load balancing server for state information.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.update_csparameter <args>

    '''

    result = {}

    payload = {'csparameter': {}}

    if stateupdate:
        payload['csparameter']['stateupdate'] = stateupdate

    execution = __proxy__['citrixns.put']('config/csparameter', payload)

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


def update_cspolicy(policyname=None, url=None, rule=None, domain=None, action=None, logaction=None, newname=None,
                    save=False):
    '''
    Update the running configuration for the cspolicy config key.

    policyname(str): Name for the content switching policy. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters. Cannot be changed after a policy is created. The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my policy" or my policy). Minimum length = 1

    url(str): URL string that is matched with the URL of a request. Can contain a wildcard character. Specify the string
        value in the following format: [[prefix] [*]] [.suffix]. Minimum length = 1 Maximum length = 208

    rule(str): Expression, or name of a named expression, against which traffic is evaluated. Written in the classic or
        default syntax.  Note: Maximum length of a string literal in the expression is 255 characters. A longer string
        can be split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;" The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    domain(str): The domain name. The string value can range to 63 characters. Minimum length = 1

    action(str): Content switching action that names the target load balancing virtual server to which the traffic is
        switched.

    logaction(str): The log action associated with the content switching policy.

    newname(str): The new name of the content switching policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.update_cspolicy <args>

    '''

    result = {}

    payload = {'cspolicy': {}}

    if policyname:
        payload['cspolicy']['policyname'] = policyname

    if url:
        payload['cspolicy']['url'] = url

    if rule:
        payload['cspolicy']['rule'] = rule

    if domain:
        payload['cspolicy']['domain'] = domain

    if action:
        payload['cspolicy']['action'] = action

    if logaction:
        payload['cspolicy']['logaction'] = logaction

    if newname:
        payload['cspolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/cspolicy', payload)

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


def update_csvserver(name=None, td=None, servicetype=None, ipv46=None, targettype=None, dnsrecordtype=None,
                     persistenceid=None, ippattern=None, ipmask=None, range=None, port=None, state=None,
                     stateupdate=None, cacheable=None, redirecturl=None, clttimeout=None, precedence=None,
                     casesensitive=None, somethod=None, sopersistence=None, sopersistencetimeout=None, sothreshold=None,
                     sobackupaction=None, redirectportrewrite=None, downstateflush=None, backupvserver=None,
                     disableprimaryondown=None, insertvserveripport=None, vipheader=None, rtspnat=None,
                     authenticationhost=None, authentication=None, listenpolicy=None, listenpriority=None, authn401=None,
                     authnvsname=None, push=None, pushvserver=None, pushlabel=None, pushmulticlients=None,
                     tcpprofilename=None, httpprofilename=None, dbprofilename=None, oracleserverversion=None,
                     comment=None, mssqlserverversion=None, l2conn=None, mysqlprotocolversion=None,
                     mysqlserverversion=None, mysqlcharacterset=None, mysqlservercapabilities=None, appflowlog=None,
                     netprofile=None, icmpvsrresponse=None, rhistate=None, authnprofile=None, dnsprofilename=None,
                     domainname=None, ttl=None, backupip=None, cookiedomain=None, cookietimeout=None, sitedomainttl=None,
                     newname=None, save=False):
    '''
    Update the running configuration for the csvserver config key.

    name(str): Name for the content switching virtual server. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters.  Cannot be changed after the CS virtual server is created. The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, my server or my server). Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    servicetype(str): Protocol used by the virtual server. Possible values = HTTP, SSL, TCP, FTP, RTSP, SSL_TCP, UDP, DNS,
        SIP_UDP, SIP_TCP, SIP_SSL, ANY, RADIUS, RDP, MYSQL, MSSQL, DIAMETER, SSL_DIAMETER, DNS_TCP, ORACLE, SMPP

    ipv46(str): IP address of the content switching virtual server. Minimum length = 1

    targettype(str): Virtual server target type. Possible values = GSLB

    dnsrecordtype(str): . Default value: NSGSLB_IPV4 Possible values = A, AAAA, CNAME, NAPTR

    persistenceid(int): . Minimum value = 0 Maximum value = 65535

    ippattern(str): IP address pattern, in dotted decimal notation, for identifying packets to be accepted by the virtual
        server. The IP Mask parameter specifies which part of the destination IP address is matched against the pattern.
        Mutually exclusive with the IP Address parameter.  For example, if the IP pattern assigned to the virtual server
        is 198.51.100.0 and the IP mask is 255.255.240.0 (a forward mask), the first 20 bits in the destination IP
        addresses are matched with the first 20 bits in the pattern. The virtual server accepts requests with IP
        addresses that range from 198.51.96.1 to 198.51.111.254. You can also use a pattern such as 0.0.2.2 and a mask
        such as 0.0.255.255 (a reverse mask). If a destination IP address matches more than one IP pattern, the pattern
        with the longest match is selected, and the associated virtual server processes the request. For example, if the
        virtual servers, vs1 and vs2, have the same IP pattern, 0.0.100.128, but different IP masks of 0.0.255.255 and
        0.0.224.255, a destination IP address of 198.51.100.128 has the longest match with the IP pattern of vs1. If a
        destination IP address matches two or more virtual servers to the same extent, the request is processed by the
        virtual server whose port number matches the port number in the request.

    ipmask(str): IP mask, in dotted decimal notation, for the IP Pattern parameter. Can have leading or trailing non-zero
        octets (for example, 255.255.240.0 or 0.0.255.255). Accordingly, the mask specifies whether the first n bits or
        the last n bits of the destination IP address in a client request are to be matched with the corresponding bits
        in the IP pattern. The former is called a forward mask. The latter is called a reverse mask.

    range(int): Number of consecutive IP addresses, starting with the address specified by the IP Address parameter, to
        include in a range of addresses assigned to this virtual server. Default value: 1 Minimum value = 1 Maximum value
        = 254

    port(int): Port number for content switching virtual server. Minimum value = 1 Range 1 - 65535 * in CLI is represented as
        65535 in NITRO API

    state(str): Initial state of the load balancing virtual server. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    stateupdate(str): Enable state updates for a specific content switching virtual server. By default, the Content Switching
        virtual server is always UP, regardless of the state of the Load Balancing virtual servers bound to it. This
        parameter interacts with the global setting as follows: Global Level | Vserver Level | Result ENABLED ENABLED
        ENABLED ENABLED DISABLED ENABLED DISABLED ENABLED ENABLED DISABLED DISABLED DISABLED If you want to enable state
        updates for only some content switching virtual servers, be sure to disable the state update parameter. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    cacheable(str): Use this option to specify whether a virtual server, used for load balancing or content switching, routes
        requests to the cache redirection virtual server before sending it to the configured servers. Default value: NO
        Possible values = YES, NO

    redirecturl(str): URL to which traffic is redirected if the virtual server becomes unavailable. The service type of the
        virtual server should be either HTTP or SSL. Caution: Make sure that the domain in the URL does not match the
        domain specified for a content switching policy. If it does, requests are continuously redirected to the
        unavailable virtual server. Minimum length = 1

    clttimeout(int): Idle time, in seconds, after which the client connection is terminated. The default values are: 180
        seconds for HTTP/SSL-based services. 9000 seconds for other TCP-based services. 120 seconds for DNS-based
        services. 120 seconds for other UDP-based services. Minimum value = 0 Maximum value = 31536000

    precedence(str): Type of precedence to use for both RULE-based and URL-based policies on the content switching virtual
        server. With the default (RULE) setting, incoming requests are evaluated against the rule-based content switching
        policies. If none of the rules match, the URL in the request is evaluated against the URL-based content switching
        policies. Default value: RULE Possible values = RULE, URL

    casesensitive(str): Consider case in URLs (for policies that use URLs instead of RULES). For example, with the ON
        setting, the URLs /a/1.html and /A/1.HTML are treated differently and can have different targets (set by content
        switching policies). With the OFF setting, /a/1.html and /A/1.HTML are switched to the same target. Default
        value: ON Possible values = ON, OFF

    somethod(str): Type of spillover used to divert traffic to the backup virtual server when the primary virtual server
        reaches the spillover threshold. Connection spillover is based on the number of connections. Bandwidth spillover
        is based on the total Kbps of incoming and outgoing traffic. Possible values = CONNECTION, DYNAMICCONNECTION,
        BANDWIDTH, HEALTH, NONE

    sopersistence(str): Maintain source-IP based persistence on primary and backup virtual servers. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    sopersistencetimeout(int): Time-out value, in minutes, for spillover persistence. Default value: 2 Minimum value = 2
        Maximum value = 1440

    sothreshold(int): Depending on the spillover method, the maximum number of connections or the maximum total bandwidth
        (Kbps) that a virtual server can handle before spillover occurs. Minimum value = 1 Maximum value = 4294967287

    sobackupaction(str): Action to be performed if spillover is to take effect, but no backup chain to spillover is usable or
        exists. Possible values = DROP, ACCEPT, REDIRECT

    redirectportrewrite(str): State of port rewrite while performing HTTP redirect. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    downstateflush(str): Flush all active transactions associated with a virtual server whose state transitions from UP to
        DOWN. Do not enable this option for applications that must complete their transactions. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    backupvserver(str): Name of the backup virtual server that you are configuring. Must begin with an ASCII alphanumeric or
        underscore (_) character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space,
        colon (:), at sign (@), equal sign (=), and hyphen (-) characters. Can be changed after the backup virtual server
        is created. You can assign a different backup virtual server or rename the existing virtual server. The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks. Minimum length = 1

    disableprimaryondown(str): Continue forwarding the traffic to backup virtual server even after the primary server comes
        UP from the DOWN state. Default value: DISABLED Possible values = ENABLED, DISABLED

    insertvserveripport(str): Insert the virtual servers VIP address and port number in the request header. Available values
        function as follows:  VIPADDR - Header contains the vservers IP address and port number without any translation.
        OFF - The virtual IP and port header insertion option is disabled.  V6TOV4MAPPING - Header contains the mapped
        IPv4 address corresponding to the IPv6 address of the vserver and the port number. An IPv6 address can be mapped
        to a user-specified IPv4 address using the set ns ip6 command. Possible values = OFF, VIPADDR, V6TOV4MAPPING

    vipheader(str): Name of virtual server IP and port header, for use with the VServer IP Port Insertion parameter. Minimum
        length = 1

    rtspnat(str): Enable network address translation (NAT) for real-time streaming protocol (RTSP) connections. Default
        value: OFF Possible values = ON, OFF

    authenticationhost(str): FQDN of the authentication virtual server. The service type of the virtual server should be
        either HTTP or SSL. Minimum length = 3 Maximum length = 252

    authentication(str): Authenticate users who request a connection to the content switching virtual server. Default value:
        OFF Possible values = ON, OFF

    listenpolicy(str): String specifying the listen policy for the content switching virtual server. Can be either the name
        of an existing expression or an in-line expression. Default value: "NONE"

    listenpriority(int): Integer specifying the priority of the listen policy. A higher number specifies a lower priority. If
        a request matches the listen policies of more than one virtual server the virtual server whose listen policy has
        the highest priority (the lowest priority number) accepts the request. Default value: 101 Minimum value = 0
        Maximum value = 100

    authn401(str): Enable HTTP 401-response based authentication. Default value: OFF Possible values = ON, OFF

    authnvsname(str): Name of authentication virtual server that authenticates the incoming user requests to this content
        switching virtual server. . Minimum length = 1 Maximum length = 252

    push(str): Process traffic with the push virtual server that is bound to this content switching virtual server (specified
        by the Push VServer parameter). The service type of the push virtual server should be either HTTP or SSL. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    pushvserver(str): Name of the load balancing virtual server, of type PUSH or SSL_PUSH, to which the server pushes updates
        received on the client-facing load balancing virtual server. Minimum length = 1

    pushlabel(str): Expression for extracting the label from the response received from server. This string can be either an
        existing rule name or an inline expression. The service type of the virtual server should be either HTTP or SSL.
        Default value: "none"

    pushmulticlients(str): Allow multiple Web 2.0 connections from the same client to connect to the virtual server and
        expect updates. Default value: NO Possible values = YES, NO

    tcpprofilename(str): Name of the TCP profile containing TCP configuration settings for the virtual server. Minimum length
        = 1 Maximum length = 127

    httpprofilename(str): Name of the HTTP profile containing HTTP configuration settings for the virtual server. The service
        type of the virtual server should be either HTTP or SSL. Minimum length = 1 Maximum length = 127

    dbprofilename(str): Name of the DB profile. Minimum length = 1 Maximum length = 127

    oracleserverversion(str): Oracle server version. Default value: 10G Possible values = 10G, 11G

    comment(str): Information about this virtual server.

    mssqlserverversion(str): The version of the MSSQL server. Default value: 2008R2 Possible values = 70, 2000, 2000SP1,
        2005, 2008, 2008R2, 2012, 2014

    l2conn(str): Use L2 Parameters to identify a connection. Possible values = ON, OFF

    mysqlprotocolversion(int): The protocol version returned by the mysql vserver. Default value: 10

    mysqlserverversion(str): The server version string returned by the mysql vserver. Minimum length = 1 Maximum length = 31

    mysqlcharacterset(int): The character set returned by the mysql vserver. Default value: 8

    mysqlservercapabilities(int): The server capabilities returned by the mysql vserver. Default value: 41613

    appflowlog(str): Enable logging appflow flow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    netprofile(str): The name of the network profile. Minimum length = 1 Maximum length = 127

    icmpvsrresponse(str): Can be active or passive. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    rhistate(str): A host route is injected according to the setting on the virtual servers  * If set to PASSIVE on all the
        virtual servers that share the IP address, the appliance always injects the hostroute.  * If set to ACTIVE on all
        the virtual servers that share the IP address, the appliance injects even if one virtual server is UP.  * If set
        to ACTIVE on some virtual servers and PASSIVE on the others, the appliance, injects even if one virtual server
        set to ACTIVE is UP. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    authnprofile(str): Name of the authentication profile to be used when authentication is turned on.

    dnsprofilename(str): Name of the DNS profile to be associated with the VServer. DNS profile properties will applied to
        the transactions processed by a VServer. This parameter is valid only for DNS and DNS-TCP VServers. Minimum
        length = 1 Maximum length = 127

    domainname(str): Domain name for which to change the time to live (TTL) and/or backup service IP address. Minimum length
        = 1

    ttl(int): . Minimum value = 1

    backupip(str): . Minimum length = 1

    cookiedomain(str): . Minimum length = 1

    cookietimeout(int): . Minimum value = 0 Maximum value = 1440

    sitedomainttl(int): . Minimum value = 1

    newname(str): New name for the virtual server. Must begin with an ASCII alphanumeric or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign
        (=), and hyphen (-) characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my name" or my
        name). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' content_switching.update_csvserver <args>

    '''

    result = {}

    payload = {'csvserver': {}}

    if name:
        payload['csvserver']['name'] = name

    if td:
        payload['csvserver']['td'] = td

    if servicetype:
        payload['csvserver']['servicetype'] = servicetype

    if ipv46:
        payload['csvserver']['ipv46'] = ipv46

    if targettype:
        payload['csvserver']['targettype'] = targettype

    if dnsrecordtype:
        payload['csvserver']['dnsrecordtype'] = dnsrecordtype

    if persistenceid:
        payload['csvserver']['persistenceid'] = persistenceid

    if ippattern:
        payload['csvserver']['ippattern'] = ippattern

    if ipmask:
        payload['csvserver']['ipmask'] = ipmask

    if range:
        payload['csvserver']['range'] = range

    if port:
        payload['csvserver']['port'] = port

    if state:
        payload['csvserver']['state'] = state

    if stateupdate:
        payload['csvserver']['stateupdate'] = stateupdate

    if cacheable:
        payload['csvserver']['cacheable'] = cacheable

    if redirecturl:
        payload['csvserver']['redirecturl'] = redirecturl

    if clttimeout:
        payload['csvserver']['clttimeout'] = clttimeout

    if precedence:
        payload['csvserver']['precedence'] = precedence

    if casesensitive:
        payload['csvserver']['casesensitive'] = casesensitive

    if somethod:
        payload['csvserver']['somethod'] = somethod

    if sopersistence:
        payload['csvserver']['sopersistence'] = sopersistence

    if sopersistencetimeout:
        payload['csvserver']['sopersistencetimeout'] = sopersistencetimeout

    if sothreshold:
        payload['csvserver']['sothreshold'] = sothreshold

    if sobackupaction:
        payload['csvserver']['sobackupaction'] = sobackupaction

    if redirectportrewrite:
        payload['csvserver']['redirectportrewrite'] = redirectportrewrite

    if downstateflush:
        payload['csvserver']['downstateflush'] = downstateflush

    if backupvserver:
        payload['csvserver']['backupvserver'] = backupvserver

    if disableprimaryondown:
        payload['csvserver']['disableprimaryondown'] = disableprimaryondown

    if insertvserveripport:
        payload['csvserver']['insertvserveripport'] = insertvserveripport

    if vipheader:
        payload['csvserver']['vipheader'] = vipheader

    if rtspnat:
        payload['csvserver']['rtspnat'] = rtspnat

    if authenticationhost:
        payload['csvserver']['authenticationhost'] = authenticationhost

    if authentication:
        payload['csvserver']['authentication'] = authentication

    if listenpolicy:
        payload['csvserver']['listenpolicy'] = listenpolicy

    if listenpriority:
        payload['csvserver']['listenpriority'] = listenpriority

    if authn401:
        payload['csvserver']['authn401'] = authn401

    if authnvsname:
        payload['csvserver']['authnvsname'] = authnvsname

    if push:
        payload['csvserver']['push'] = push

    if pushvserver:
        payload['csvserver']['pushvserver'] = pushvserver

    if pushlabel:
        payload['csvserver']['pushlabel'] = pushlabel

    if pushmulticlients:
        payload['csvserver']['pushmulticlients'] = pushmulticlients

    if tcpprofilename:
        payload['csvserver']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['csvserver']['httpprofilename'] = httpprofilename

    if dbprofilename:
        payload['csvserver']['dbprofilename'] = dbprofilename

    if oracleserverversion:
        payload['csvserver']['oracleserverversion'] = oracleserverversion

    if comment:
        payload['csvserver']['comment'] = comment

    if mssqlserverversion:
        payload['csvserver']['mssqlserverversion'] = mssqlserverversion

    if l2conn:
        payload['csvserver']['l2conn'] = l2conn

    if mysqlprotocolversion:
        payload['csvserver']['mysqlprotocolversion'] = mysqlprotocolversion

    if mysqlserverversion:
        payload['csvserver']['mysqlserverversion'] = mysqlserverversion

    if mysqlcharacterset:
        payload['csvserver']['mysqlcharacterset'] = mysqlcharacterset

    if mysqlservercapabilities:
        payload['csvserver']['mysqlservercapabilities'] = mysqlservercapabilities

    if appflowlog:
        payload['csvserver']['appflowlog'] = appflowlog

    if netprofile:
        payload['csvserver']['netprofile'] = netprofile

    if icmpvsrresponse:
        payload['csvserver']['icmpvsrresponse'] = icmpvsrresponse

    if rhistate:
        payload['csvserver']['rhistate'] = rhistate

    if authnprofile:
        payload['csvserver']['authnprofile'] = authnprofile

    if dnsprofilename:
        payload['csvserver']['dnsprofilename'] = dnsprofilename

    if domainname:
        payload['csvserver']['domainname'] = domainname

    if ttl:
        payload['csvserver']['ttl'] = ttl

    if backupip:
        payload['csvserver']['backupip'] = backupip

    if cookiedomain:
        payload['csvserver']['cookiedomain'] = cookiedomain

    if cookietimeout:
        payload['csvserver']['cookietimeout'] = cookietimeout

    if sitedomainttl:
        payload['csvserver']['sitedomainttl'] = sitedomainttl

    if newname:
        payload['csvserver']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/csvserver', payload)

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
