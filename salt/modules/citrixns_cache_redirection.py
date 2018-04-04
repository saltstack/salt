# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the cache-redirection key.

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

__virtualname__ = 'cache_redirection'


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

    return False, 'The cache_redirection execution module can only be loaded for citrixns proxy minions.'


def add_crpolicy(policyname=None, rule=None, action=None, logaction=None, newname=None, save=False):
    '''
    Add a new crpolicy to the running configuration.

    policyname(str): Name for the cache redirection policy. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters. Cannot be changed after the policy is created. The following
        requirement applies only to the NetScaler CLI:  If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, or name of a named expression, against which traffic is evaluated. Written in the classic syntax.
        Note:Maximum length of a string literal in the expression is 255 characters. A longer string can be split into
        smaller strings of up to 255 characters each, and the smaller strings concatenated with the + operator. For
        example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" + ";lt;string of
        245 characters;gt;" The following requirements apply only to the NetScaler CLI: * If the expression includes one
        or more spaces, enclose the entire expression in double quotation marks. * If the expression itself includes
        double quotation marks, escape the quotations by using the \\ character.  * Alternatively, you can use single
        quotation marks to enclose the rule, in which case you do not have to escape the double quotation marks.

    action(str): Name of the built-in cache redirection action: CACHE/ORIGIN.

    logaction(str): The log action associated with the cache redirection policy.

    newname(str): The new name of the content switching policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crpolicy <args>

    '''

    result = {}

    payload = {'crpolicy': {}}

    if policyname:
        payload['crpolicy']['policyname'] = policyname

    if rule:
        payload['crpolicy']['rule'] = rule

    if action:
        payload['crpolicy']['action'] = action

    if logaction:
        payload['crpolicy']['logaction'] = logaction

    if newname:
        payload['crpolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/crpolicy', payload)

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


def add_crvserver(name=None, td=None, servicetype=None, ipv46=None, port=None, range=None, cachetype=None, redirect=None,
                  onpolicymatch=None, redirecturl=None, clttimeout=None, precedence=None, arp=None, ghost=None,
                  ns_map=None, format=None, via=None, cachevserver=None, dnsvservername=None, destinationvserver=None,
                  domain=None, sopersistencetimeout=None, sothreshold=None, reuse=None, state=None, downstateflush=None,
                  backupvserver=None, disableprimaryondown=None, l2conn=None, backendssl=None, listenpolicy=None,
                  listenpriority=None, tcpprofilename=None, httpprofilename=None, comment=None, srcipexpr=None,
                  originusip=None, useportrange=None, appflowlog=None, netprofile=None, icmpvsrresponse=None,
                  rhistate=None, newname=None, save=False):
    '''
    Add a new crvserver to the running configuration.

    name(str): Name for the cache redirection virtual server. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters. Can be changed after the cache redirection virtual server is
        created. The following requirement applies only to the NetScaler CLI:  If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my server" or my server). Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    servicetype(str): Protocol (type of service) handled by the virtual server. Possible values = HTTP, SSL, NNTP, HDX

    ipv46(str): IPv4 or IPv6 address of the cache redirection virtual server. Usually a public IP address. Clients send
        connection requests to this IP address. Note: For a transparent cache redirection virtual server, use an asterisk
        (*) to specify a wildcard virtual server address.

    port(int): Port number of the virtual server. Default value: 80 Minimum value = 1 Maximum value = 65534

    range(int): Number of consecutive IP addresses, starting with the address specified by the IPAddress parameter, to
        include in a range of addresses assigned to this virtual server. Default value: 1 Minimum value = 1 Maximum value
        = 254

    cachetype(str): Mode of operation for the cache redirection virtual server. Available settings function as follows: *
        TRANSPARENT - Intercept all traffic flowing to the appliance and apply cache redirection policies to determine
        whether content should be served from the cache or from the origin server. * FORWARD - Resolve the hostname of
        the incoming request, by using a DNS server, and forward requests for non-cacheable content to the resolved
        origin servers. Cacheable requests are sent to the configured cache servers. * REVERSE - Configure reverse proxy
        caches for specific origin servers. Incoming traffic directed to the reverse proxy can either be served from a
        cache server or be sent to the origin server with or without modification to the URL. Possible values =
        TRANSPARENT, REVERSE, FORWARD

    redirect(str): Type of cache server to which to redirect HTTP requests. Available settings function as follows: * CACHE -
        Direct all requests to the cache. * POLICY - Apply the cache redirection policy to determine whether the request
        should be directed to the cache or to the origin. * ORIGIN - Direct all requests to the origin server. Default
        value: POLICY Possible values = CACHE, POLICY, ORIGIN

    onpolicymatch(str): Redirect requests that match the policy to either the cache or the origin server, as specified. Note:
        For this option to work, you must set the cache redirection type to POLICY. Default value: ORIGIN Possible values
        = CACHE, ORIGIN

    redirecturl(str): URL of the server to which to redirect traffic if the cache redirection virtual server configured on
        the NetScaler appliance becomes unavailable. Minimum length = 1 Maximum length = 128

    clttimeout(int): Time-out value, in seconds, after which to terminate an idle client connection. Minimum value = 0
        Maximum value = 31536000

    precedence(str): Type of policy (URL or RULE) that takes precedence on the cache redirection virtual server. Applies only
        to cache redirection virtual servers that have both URL and RULE based policies. If you specify URL, URL based
        policies are applied first, in the following order: 1. Domain and exact URL 2. Domain, prefix and suffix 3.
        Domain and suffix 4. Domain and prefix 5. Domain only 6. Exact URL 7. Prefix and suffix 8. Suffix only 9. Prefix
        only 10. Default If you specify RULE, the rule based policies are applied before URL based policies are applied.
        Default value: RULE Possible values = RULE, URL

    arp(str): Use ARP to determine the destination MAC address. Possible values = ON, OFF

    ghost(str): . Possible values = ON, OFF

    ns_map(str): Obsolete. Possible values = ON, OFF

    format(str): . Possible values = ON, OFF

    via(str): Insert a via header in each HTTP request. In the case of a cache miss, the request is redirected from the cache
        server to the origin server. This header indicates whether the request is being sent from a cache server. Default
        value: ON Possible values = ON, OFF

    cachevserver(str): Name of the default cache virtual server to which to redirect requests (the default target of the
        cache redirection virtual server). Minimum length = 1

    dnsvservername(str): Name of the DNS virtual server that resolves domain names arriving at the forward proxy virtual
        server. Note: This parameter applies only to forward proxy virtual servers, not reverse or transparent. Minimum
        length = 1

    destinationvserver(str): Destination virtual server for a transparent or forward proxy cache redirection virtual server.
        Minimum length = 1

    domain(str): Default domain for reverse proxies. Domains are configured to direct an incoming request from a specified
        source domain to a specified target domain. There can be several configured pairs of source and target domains.
        You can select one pair to be the default. If the host header or URL of an incoming request does not include a
        source domain, this option sends the request to the specified target domain. Minimum length = 1

    sopersistencetimeout(int): Time-out, in minutes, for spillover persistence. Minimum value = 2 Maximum value = 24

    sothreshold(int): For CONNECTION (or) DYNAMICCONNECTION spillover, the number of connections above which the virtual
        server enters spillover mode. For BANDWIDTH spillover, the amount of incoming and outgoing traffic (in Kbps)
        before spillover. For HEALTH spillover, the percentage of active services (by weight) below which spillover
        occurs. Minimum value = 1

    reuse(str): Reuse TCP connections to the origin server across client connections. Do not set this parameter unless the
        Service Type parameter is set to HTTP. If you set this parameter to OFF, the possible settings of the Redirect
        parameter function as follows: * CACHE - TCP connections to the cache servers are not reused. * ORIGIN - TCP
        connections to the origin servers are not reused.  * POLICY - TCP connections to the origin servers are not
        reused. If you set the Reuse parameter to ON, connections to origin servers and connections to cache servers are
        reused. Default value: ON Possible values = ON, OFF

    state(str): Initial state of the cache redirection virtual server. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    downstateflush(str): Perform delayed cleanup of connections to this virtual server. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    backupvserver(str): Name of the backup virtual server to which traffic is forwarded if the active server becomes
        unavailable. Minimum length = 1

    disableprimaryondown(str): Continue sending traffic to a backup virtual server even after the primary virtual server
        comes UP from the DOWN state. Default value: DISABLED Possible values = ENABLED, DISABLED

    l2conn(str): Use L2 parameters, such as MAC, VLAN, and channel to identify a connection. Possible values = ON, OFF

    backendssl(str): Decides whether the backend connection made by NS to the origin server will be HTTP or SSL. Applicable
        only for SSL type CR Forward proxy vserver. Default value: DISABLED Possible values = ENABLED, DISABLED

    listenpolicy(str): String specifying the listen policy for the cache redirection virtual server. Can be either an in-line
        expression or the name of a named expression. Default value: "NONE"

    listenpriority(int): Priority of the listen policy specified by the Listen Policy parameter. The lower the number, higher
        the priority. Default value: 101 Minimum value = 0 Maximum value = 100

    tcpprofilename(str): Name of the profile containing TCP configuration information for the cache redirection virtual
        server. Minimum length = 1 Maximum length = 127

    httpprofilename(str): Name of the profile containing HTTP configuration information for cache redirection virtual server.
        Minimum length = 1 Maximum length = 127

    comment(str): Comments associated with this virtual server. Maximum length = 256

    srcipexpr(str): Expression used to extract the source IP addresses from the requests originating from the cache. Can be
        either an in-line expression or the name of a named expression. Minimum length = 1 Maximum length = 1500

    originusip(str): Use the clients IP address as the source IP address in requests sent to the origin server.  Note: You
        can enable this parameter to implement fully transparent CR deployment. Possible values = ON, OFF

    useportrange(str): Use a port number from the port range (set by using the set ns param command, or in the Create Virtual
        Server (Cache Redirection) dialog box) as the source port in the requests sent to the origin server. Default
        value: OFF Possible values = ON, OFF

    appflowlog(str): Enable logging of AppFlow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    netprofile(str): Name of the network profile containing network configurations for the cache redirection virtual server.
        Minimum length = 1 Maximum length = 127

    icmpvsrresponse(str): Criterion for responding to PING requests sent to this virtual server. If ACTIVE, respond only if
        the virtual server is available. If PASSIVE, respond even if the virtual server is not available. Default value:
        PASSIVE Possible values = PASSIVE, ACTIVE

    rhistate(str): A host route is injected according to the setting on the virtual servers  * If set to PASSIVE on all the
        virtual servers that share the IP address, the appliance always injects the hostroute.  * If set to ACTIVE on all
        the virtual servers that share the IP address, the appliance injects even if one virtual server is UP.  * If set
        to ACTIVE on some virtual servers and PASSIVE on the others, the appliance, injects even if one virtual server
        set to ACTIVE is UP. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    newname(str): New name for the cache redirection virtual server. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters. If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my name" or my name). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver <args>

    '''

    result = {}

    payload = {'crvserver': {}}

    if name:
        payload['crvserver']['name'] = name

    if td:
        payload['crvserver']['td'] = td

    if servicetype:
        payload['crvserver']['servicetype'] = servicetype

    if ipv46:
        payload['crvserver']['ipv46'] = ipv46

    if port:
        payload['crvserver']['port'] = port

    if range:
        payload['crvserver']['range'] = range

    if cachetype:
        payload['crvserver']['cachetype'] = cachetype

    if redirect:
        payload['crvserver']['redirect'] = redirect

    if onpolicymatch:
        payload['crvserver']['onpolicymatch'] = onpolicymatch

    if redirecturl:
        payload['crvserver']['redirecturl'] = redirecturl

    if clttimeout:
        payload['crvserver']['clttimeout'] = clttimeout

    if precedence:
        payload['crvserver']['precedence'] = precedence

    if arp:
        payload['crvserver']['arp'] = arp

    if ghost:
        payload['crvserver']['ghost'] = ghost

    if ns_map:
        payload['crvserver']['map'] = ns_map

    if format:
        payload['crvserver']['format'] = format

    if via:
        payload['crvserver']['via'] = via

    if cachevserver:
        payload['crvserver']['cachevserver'] = cachevserver

    if dnsvservername:
        payload['crvserver']['dnsvservername'] = dnsvservername

    if destinationvserver:
        payload['crvserver']['destinationvserver'] = destinationvserver

    if domain:
        payload['crvserver']['domain'] = domain

    if sopersistencetimeout:
        payload['crvserver']['sopersistencetimeout'] = sopersistencetimeout

    if sothreshold:
        payload['crvserver']['sothreshold'] = sothreshold

    if reuse:
        payload['crvserver']['reuse'] = reuse

    if state:
        payload['crvserver']['state'] = state

    if downstateflush:
        payload['crvserver']['downstateflush'] = downstateflush

    if backupvserver:
        payload['crvserver']['backupvserver'] = backupvserver

    if disableprimaryondown:
        payload['crvserver']['disableprimaryondown'] = disableprimaryondown

    if l2conn:
        payload['crvserver']['l2conn'] = l2conn

    if backendssl:
        payload['crvserver']['backendssl'] = backendssl

    if listenpolicy:
        payload['crvserver']['listenpolicy'] = listenpolicy

    if listenpriority:
        payload['crvserver']['listenpriority'] = listenpriority

    if tcpprofilename:
        payload['crvserver']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['crvserver']['httpprofilename'] = httpprofilename

    if comment:
        payload['crvserver']['comment'] = comment

    if srcipexpr:
        payload['crvserver']['srcipexpr'] = srcipexpr

    if originusip:
        payload['crvserver']['originusip'] = originusip

    if useportrange:
        payload['crvserver']['useportrange'] = useportrange

    if appflowlog:
        payload['crvserver']['appflowlog'] = appflowlog

    if netprofile:
        payload['crvserver']['netprofile'] = netprofile

    if icmpvsrresponse:
        payload['crvserver']['icmpvsrresponse'] = icmpvsrresponse

    if rhistate:
        payload['crvserver']['rhistate'] = rhistate

    if newname:
        payload['crvserver']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/crvserver', payload)

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


def add_crvserver_appflowpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                        targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                        save=False):
    '''
    Add a new crvserver_appflowpolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_appflowpolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_appflowpolicy_binding': {}}

    if priority:
        payload['crvserver_appflowpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_appflowpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_appflowpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_appflowpolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_appflowpolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_appflowpolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_appflowpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_appflowpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_appflowpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_appflowpolicy_binding', payload)

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


def add_crvserver_appfwpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                      save=False):
    '''
    Add a new crvserver_appfwpolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_appfwpolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_appfwpolicy_binding': {}}

    if priority:
        payload['crvserver_appfwpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_appfwpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_appfwpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_appfwpolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_appfwpolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_appfwpolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_appfwpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_appfwpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_appfwpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_appfwpolicy_binding', payload)

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


def add_crvserver_appqoepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                       targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                       save=False):
    '''
    Add a new crvserver_appqoepolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_appqoepolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_appqoepolicy_binding': {}}

    if priority:
        payload['crvserver_appqoepolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_appqoepolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_appqoepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_appqoepolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_appqoepolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_appqoepolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_appqoepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_appqoepolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_appqoepolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_appqoepolicy_binding', payload)

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


def add_crvserver_cachepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                      save=False):
    '''
    Add a new crvserver_cachepolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_cachepolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_cachepolicy_binding': {}}

    if priority:
        payload['crvserver_cachepolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_cachepolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_cachepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_cachepolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_cachepolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_cachepolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_cachepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_cachepolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_cachepolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_cachepolicy_binding', payload)

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


def add_crvserver_cmppolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                    save=False):
    '''
    Add a new crvserver_cmppolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_cmppolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_cmppolicy_binding': {}}

    if priority:
        payload['crvserver_cmppolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_cmppolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_cmppolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_cmppolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_cmppolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_cmppolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_cmppolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_cmppolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_cmppolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_cmppolicy_binding', payload)

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


def add_crvserver_crpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                   targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                   save=False):
    '''
    Add a new crvserver_crpolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_crpolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_crpolicy_binding': {}}

    if priority:
        payload['crvserver_crpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_crpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_crpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_crpolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_crpolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_crpolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_crpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_crpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_crpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_crpolicy_binding', payload)

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


def add_crvserver_cspolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                   targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                   save=False):
    '''
    Add a new crvserver_cspolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): The CSW target server names.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_cspolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_cspolicy_binding': {}}

    if priority:
        payload['crvserver_cspolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_cspolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_cspolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_cspolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_cspolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_cspolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_cspolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_cspolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_cspolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_cspolicy_binding', payload)

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


def add_crvserver_feopolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                    save=False):
    '''
    Add a new crvserver_feopolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_feopolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_feopolicy_binding': {}}

    if priority:
        payload['crvserver_feopolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_feopolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_feopolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_feopolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_feopolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_feopolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_feopolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_feopolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_feopolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_feopolicy_binding', payload)

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


def add_crvserver_filterpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                       targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                       save=False):
    '''
    Add a new crvserver_filterpolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

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
        current policys priority number (say, 30) and the highest priority number (say, 100), b ut does not match any
        configured priority number (for example, the expression evaluates to the number 85). This example assumes that
        the priority number incr ements by 10 for every successive policy, and therefore a priority number of 85 does not
        exist in the policy label.

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_filterpolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_filterpolicy_binding': {}}

    if priority:
        payload['crvserver_filterpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_filterpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_filterpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_filterpolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_filterpolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_filterpolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_filterpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_filterpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_filterpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_filterpolicy_binding', payload)

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


def add_crvserver_icapolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                    save=False):
    '''
    Add a new crvserver_icapolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_icapolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_icapolicy_binding': {}}

    if priority:
        payload['crvserver_icapolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_icapolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_icapolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_icapolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_icapolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_icapolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_icapolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_icapolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_icapolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_icapolicy_binding', payload)

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


def add_crvserver_lbvserver_binding(name=None, lbvserver=None, save=False):
    '''
    Add a new crvserver_lbvserver_binding to the running configuration.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    lbvserver(str): The Default target server name. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_lbvserver_binding <args>

    '''

    result = {}

    payload = {'crvserver_lbvserver_binding': {}}

    if name:
        payload['crvserver_lbvserver_binding']['name'] = name

    if lbvserver:
        payload['crvserver_lbvserver_binding']['lbvserver'] = lbvserver

    execution = __proxy__['citrixns.post']('config/crvserver_lbvserver_binding', payload)

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


def add_crvserver_policymap_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                    save=False):
    '''
    Add a new crvserver_policymap_binding to the running configuration.

    priority(int): An unsigned integer that determines the priority of the policy relative to other policies bound to this
        cache redirection virtual server. The lower the value, higher the priority. Note: This option is available only
        when binding content switching, filtering, and compression policies to a cache redirection virtual server.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): The CSW target server names.

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
        current policys priority number (say, 30) and the highest priority number (say, 100), b ut does not match any
        configured priority number (for example, the expression evaluates to the number 85). This example assumes that
        the priority number incr ements by 10 for every successive policy, and therefore a priority number of 85 does not
        exist in the policy label.

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_policymap_binding <args>

    '''

    result = {}

    payload = {'crvserver_policymap_binding': {}}

    if priority:
        payload['crvserver_policymap_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_policymap_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_policymap_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_policymap_binding']['labelname'] = labelname

    if name:
        payload['crvserver_policymap_binding']['name'] = name

    if targetvserver:
        payload['crvserver_policymap_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_policymap_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_policymap_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_policymap_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_policymap_binding', payload)

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


def add_crvserver_responderpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                          save=False):
    '''
    Add a new crvserver_responderpolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): For a rewrite policy, the bind point to which to bind the policy. Note: This parameter applies only to
        rewrite policies, because content switching policies are evaluated only at request time. Possible values =
        REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_responderpolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_responderpolicy_binding': {}}

    if priority:
        payload['crvserver_responderpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_responderpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_responderpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_responderpolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_responderpolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_responderpolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_responderpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_responderpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_responderpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_responderpolicy_binding', payload)

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


def add_crvserver_rewritepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                        targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                        save=False):
    '''
    Add a new crvserver_rewritepolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag.

    labeltype(str): The invocation type. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_rewritepolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_rewritepolicy_binding': {}}

    if priority:
        payload['crvserver_rewritepolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_rewritepolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_rewritepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_rewritepolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_rewritepolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_rewritepolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_rewritepolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_rewritepolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_rewritepolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_rewritepolicy_binding', payload)

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


def add_crvserver_spilloverpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None,
                                          save=False):
    '''
    Add a new crvserver_spilloverpolicy_binding to the running configuration.

    priority(int): The priority for the policy.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE, ICA_REQUEST

    policyname(str): Policies bound to this vserver.

    labelname(str): Name of the label to be invoked.

    name(str): Name of the cache redirection virtual server to which to bind the cache redirection policy. Minimum length =
        1

    targetvserver(str): Name of the virtual server to which content is forwarded. Applicable only if the policy is a map
        policy and the cache redirection virtual server is of type REVERSE. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke a policy label if this policys rule evaluates to TRUE (valid only for default-syntax policies such
        as application firewall, transform, integrated cache, rewrite, responder, and content switching).

    labeltype(str): Type of label to be invoked. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.add_crvserver_spilloverpolicy_binding <args>

    '''

    result = {}

    payload = {'crvserver_spilloverpolicy_binding': {}}

    if priority:
        payload['crvserver_spilloverpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['crvserver_spilloverpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['crvserver_spilloverpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['crvserver_spilloverpolicy_binding']['labelname'] = labelname

    if name:
        payload['crvserver_spilloverpolicy_binding']['name'] = name

    if targetvserver:
        payload['crvserver_spilloverpolicy_binding']['targetvserver'] = targetvserver

    if gotopriorityexpression:
        payload['crvserver_spilloverpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['crvserver_spilloverpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['crvserver_spilloverpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/crvserver_spilloverpolicy_binding', payload)

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


def disable_crvserver(name=None, save=False):
    '''
    Disables a crvserver matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.disable_crvserver name=foo

    '''

    result = {}

    payload = {'crvserver': {}}

    if name:
        payload['crvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/crvserver?action=disable', payload)

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


def enable_crvserver(name=None, save=False):
    '''
    Enables a crvserver matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.enable_crvserver name=foo

    '''

    result = {}

    payload = {'crvserver': {}}

    if name:
        payload['crvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/crvserver?action=enable', payload)

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


def get_craction(name=None):
    '''
    Show the running configuration for the craction config key.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_craction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/craction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'craction')

    return response


def get_crpolicy(policyname=None, rule=None, action=None, logaction=None, newname=None):
    '''
    Show the running configuration for the crpolicy config key.

    policyname(str): Filters results that only match the policyname field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crpolicy

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    if logaction:
        search_filter.append(['logaction', logaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crpolicy')

    return response


def get_crpolicy_binding():
    '''
    Show the running configuration for the crpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crpolicy_binding'), 'crpolicy_binding')

    return response


def get_crpolicy_crvserver_binding(policyname=None, domain=None):
    '''
    Show the running configuration for the crpolicy_crvserver_binding config key.

    policyname(str): Filters results that only match the policyname field.

    domain(str): Filters results that only match the domain field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crpolicy_crvserver_binding

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if domain:
        search_filter.append(['domain', domain])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crpolicy_crvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crpolicy_crvserver_binding')

    return response


def get_crvserver(name=None, td=None, servicetype=None, ipv46=None, port=None, range=None, cachetype=None, redirect=None,
                  onpolicymatch=None, redirecturl=None, clttimeout=None, precedence=None, arp=None, ghost=None,
                  ns_map=None, format=None, via=None, cachevserver=None, dnsvservername=None, destinationvserver=None,
                  domain=None, sopersistencetimeout=None, sothreshold=None, reuse=None, state=None, downstateflush=None,
                  backupvserver=None, disableprimaryondown=None, l2conn=None, backendssl=None, listenpolicy=None,
                  listenpriority=None, tcpprofilename=None, httpprofilename=None, comment=None, srcipexpr=None,
                  originusip=None, useportrange=None, appflowlog=None, netprofile=None, icmpvsrresponse=None,
                  rhistate=None, newname=None):
    '''
    Show the running configuration for the crvserver config key.

    name(str): Filters results that only match the name field.

    td(int): Filters results that only match the td field.

    servicetype(str): Filters results that only match the servicetype field.

    ipv46(str): Filters results that only match the ipv46 field.

    port(int): Filters results that only match the port field.

    range(int): Filters results that only match the range field.

    cachetype(str): Filters results that only match the cachetype field.

    redirect(str): Filters results that only match the redirect field.

    onpolicymatch(str): Filters results that only match the onpolicymatch field.

    redirecturl(str): Filters results that only match the redirecturl field.

    clttimeout(int): Filters results that only match the clttimeout field.

    precedence(str): Filters results that only match the precedence field.

    arp(str): Filters results that only match the arp field.

    ghost(str): Filters results that only match the ghost field.

    ns_map(str): Filters results that only match the map field.

    format(str): Filters results that only match the format field.

    via(str): Filters results that only match the via field.

    cachevserver(str): Filters results that only match the cachevserver field.

    dnsvservername(str): Filters results that only match the dnsvservername field.

    destinationvserver(str): Filters results that only match the destinationvserver field.

    domain(str): Filters results that only match the domain field.

    sopersistencetimeout(int): Filters results that only match the sopersistencetimeout field.

    sothreshold(int): Filters results that only match the sothreshold field.

    reuse(str): Filters results that only match the reuse field.

    state(str): Filters results that only match the state field.

    downstateflush(str): Filters results that only match the downstateflush field.

    backupvserver(str): Filters results that only match the backupvserver field.

    disableprimaryondown(str): Filters results that only match the disableprimaryondown field.

    l2conn(str): Filters results that only match the l2conn field.

    backendssl(str): Filters results that only match the backendssl field.

    listenpolicy(str): Filters results that only match the listenpolicy field.

    listenpriority(int): Filters results that only match the listenpriority field.

    tcpprofilename(str): Filters results that only match the tcpprofilename field.

    httpprofilename(str): Filters results that only match the httpprofilename field.

    comment(str): Filters results that only match the comment field.

    srcipexpr(str): Filters results that only match the srcipexpr field.

    originusip(str): Filters results that only match the originusip field.

    useportrange(str): Filters results that only match the useportrange field.

    appflowlog(str): Filters results that only match the appflowlog field.

    netprofile(str): Filters results that only match the netprofile field.

    icmpvsrresponse(str): Filters results that only match the icmpvsrresponse field.

    rhistate(str): Filters results that only match the rhistate field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver

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

    if port:
        search_filter.append(['port', port])

    if range:
        search_filter.append(['range', range])

    if cachetype:
        search_filter.append(['cachetype', cachetype])

    if redirect:
        search_filter.append(['redirect', redirect])

    if onpolicymatch:
        search_filter.append(['onpolicymatch', onpolicymatch])

    if redirecturl:
        search_filter.append(['redirecturl', redirecturl])

    if clttimeout:
        search_filter.append(['clttimeout', clttimeout])

    if precedence:
        search_filter.append(['precedence', precedence])

    if arp:
        search_filter.append(['arp', arp])

    if ghost:
        search_filter.append(['ghost', ghost])

    if ns_map:
        search_filter.append(['map', ns_map])

    if format:
        search_filter.append(['format', format])

    if via:
        search_filter.append(['via', via])

    if cachevserver:
        search_filter.append(['cachevserver', cachevserver])

    if dnsvservername:
        search_filter.append(['dnsvservername', dnsvservername])

    if destinationvserver:
        search_filter.append(['destinationvserver', destinationvserver])

    if domain:
        search_filter.append(['domain', domain])

    if sopersistencetimeout:
        search_filter.append(['sopersistencetimeout', sopersistencetimeout])

    if sothreshold:
        search_filter.append(['sothreshold', sothreshold])

    if reuse:
        search_filter.append(['reuse', reuse])

    if state:
        search_filter.append(['state', state])

    if downstateflush:
        search_filter.append(['downstateflush', downstateflush])

    if backupvserver:
        search_filter.append(['backupvserver', backupvserver])

    if disableprimaryondown:
        search_filter.append(['disableprimaryondown', disableprimaryondown])

    if l2conn:
        search_filter.append(['l2conn', l2conn])

    if backendssl:
        search_filter.append(['backendssl', backendssl])

    if listenpolicy:
        search_filter.append(['listenpolicy', listenpolicy])

    if listenpriority:
        search_filter.append(['listenpriority', listenpriority])

    if tcpprofilename:
        search_filter.append(['tcpprofilename', tcpprofilename])

    if httpprofilename:
        search_filter.append(['httpprofilename', httpprofilename])

    if comment:
        search_filter.append(['comment', comment])

    if srcipexpr:
        search_filter.append(['srcipexpr', srcipexpr])

    if originusip:
        search_filter.append(['originusip', originusip])

    if useportrange:
        search_filter.append(['useportrange', useportrange])

    if appflowlog:
        search_filter.append(['appflowlog', appflowlog])

    if netprofile:
        search_filter.append(['netprofile', netprofile])

    if icmpvsrresponse:
        search_filter.append(['icmpvsrresponse', icmpvsrresponse])

    if rhistate:
        search_filter.append(['rhistate', rhistate])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver')

    return response


def get_crvserver_appflowpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                        targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_appflowpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_appflowpolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_appflowpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_appflowpolicy_binding')

    return response


def get_crvserver_appfwpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_appfwpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_appfwpolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_appfwpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_appfwpolicy_binding')

    return response


def get_crvserver_appqoepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                       targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_appqoepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_appqoepolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_appqoepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_appqoepolicy_binding')

    return response


def get_crvserver_binding():
    '''
    Show the running configuration for the crvserver_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_binding'), 'crvserver_binding')

    return response


def get_crvserver_cachepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_cachepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_cachepolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_cachepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_cachepolicy_binding')

    return response


def get_crvserver_cmppolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_cmppolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_cmppolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_cmppolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_cmppolicy_binding')

    return response


def get_crvserver_crpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                   targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_crpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_crpolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_crpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_crpolicy_binding')

    return response


def get_crvserver_cspolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                   targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_cspolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_cspolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_cspolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_cspolicy_binding')

    return response


def get_crvserver_feopolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_feopolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_feopolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_feopolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_feopolicy_binding')

    return response


def get_crvserver_filterpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                       targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_filterpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_filterpolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_filterpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_filterpolicy_binding')

    return response


def get_crvserver_icapolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_icapolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_icapolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_icapolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_icapolicy_binding')

    return response


def get_crvserver_lbvserver_binding(name=None, lbvserver=None):
    '''
    Show the running configuration for the crvserver_lbvserver_binding config key.

    name(str): Filters results that only match the name field.

    lbvserver(str): Filters results that only match the lbvserver field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_lbvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if lbvserver:
        search_filter.append(['lbvserver', lbvserver])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_lbvserver_binding')

    return response


def get_crvserver_policymap_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_policymap_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_policymap_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_policymap_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_policymap_binding')

    return response


def get_crvserver_responderpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_responderpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_responderpolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_responderpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_responderpolicy_binding')

    return response


def get_crvserver_rewritepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                        targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_rewritepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_rewritepolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_rewritepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_rewritepolicy_binding')

    return response


def get_crvserver_spilloverpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          targetvserver=None, gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the crvserver_spilloverpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    targetvserver(str): Filters results that only match the targetvserver field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.get_crvserver_spilloverpolicy_binding

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

    if targetvserver:
        search_filter.append(['targetvserver', targetvserver])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/crvserver_spilloverpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'crvserver_spilloverpolicy_binding')

    return response


def unset_crpolicy(policyname=None, rule=None, action=None, logaction=None, newname=None, save=False):
    '''
    Unsets values from the crpolicy configuration key.

    policyname(bool): Unsets the policyname value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    logaction(bool): Unsets the logaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.unset_crpolicy <args>

    '''

    result = {}

    payload = {'crpolicy': {}}

    if policyname:
        payload['crpolicy']['policyname'] = True

    if rule:
        payload['crpolicy']['rule'] = True

    if action:
        payload['crpolicy']['action'] = True

    if logaction:
        payload['crpolicy']['logaction'] = True

    if newname:
        payload['crpolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/crpolicy?action=unset', payload)

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


def unset_crvserver(name=None, td=None, servicetype=None, ipv46=None, port=None, range=None, cachetype=None,
                    redirect=None, onpolicymatch=None, redirecturl=None, clttimeout=None, precedence=None, arp=None,
                    ghost=None, ns_map=None, format=None, via=None, cachevserver=None, dnsvservername=None,
                    destinationvserver=None, domain=None, sopersistencetimeout=None, sothreshold=None, reuse=None,
                    state=None, downstateflush=None, backupvserver=None, disableprimaryondown=None, l2conn=None,
                    backendssl=None, listenpolicy=None, listenpriority=None, tcpprofilename=None, httpprofilename=None,
                    comment=None, srcipexpr=None, originusip=None, useportrange=None, appflowlog=None, netprofile=None,
                    icmpvsrresponse=None, rhistate=None, newname=None, save=False):
    '''
    Unsets values from the crvserver configuration key.

    name(bool): Unsets the name value.

    td(bool): Unsets the td value.

    servicetype(bool): Unsets the servicetype value.

    ipv46(bool): Unsets the ipv46 value.

    port(bool): Unsets the port value.

    range(bool): Unsets the range value.

    cachetype(bool): Unsets the cachetype value.

    redirect(bool): Unsets the redirect value.

    onpolicymatch(bool): Unsets the onpolicymatch value.

    redirecturl(bool): Unsets the redirecturl value.

    clttimeout(bool): Unsets the clttimeout value.

    precedence(bool): Unsets the precedence value.

    arp(bool): Unsets the arp value.

    ghost(bool): Unsets the ghost value.

    ns_map(bool): Unsets the ns_map value.

    format(bool): Unsets the format value.

    via(bool): Unsets the via value.

    cachevserver(bool): Unsets the cachevserver value.

    dnsvservername(bool): Unsets the dnsvservername value.

    destinationvserver(bool): Unsets the destinationvserver value.

    domain(bool): Unsets the domain value.

    sopersistencetimeout(bool): Unsets the sopersistencetimeout value.

    sothreshold(bool): Unsets the sothreshold value.

    reuse(bool): Unsets the reuse value.

    state(bool): Unsets the state value.

    downstateflush(bool): Unsets the downstateflush value.

    backupvserver(bool): Unsets the backupvserver value.

    disableprimaryondown(bool): Unsets the disableprimaryondown value.

    l2conn(bool): Unsets the l2conn value.

    backendssl(bool): Unsets the backendssl value.

    listenpolicy(bool): Unsets the listenpolicy value.

    listenpriority(bool): Unsets the listenpriority value.

    tcpprofilename(bool): Unsets the tcpprofilename value.

    httpprofilename(bool): Unsets the httpprofilename value.

    comment(bool): Unsets the comment value.

    srcipexpr(bool): Unsets the srcipexpr value.

    originusip(bool): Unsets the originusip value.

    useportrange(bool): Unsets the useportrange value.

    appflowlog(bool): Unsets the appflowlog value.

    netprofile(bool): Unsets the netprofile value.

    icmpvsrresponse(bool): Unsets the icmpvsrresponse value.

    rhistate(bool): Unsets the rhistate value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.unset_crvserver <args>

    '''

    result = {}

    payload = {'crvserver': {}}

    if name:
        payload['crvserver']['name'] = True

    if td:
        payload['crvserver']['td'] = True

    if servicetype:
        payload['crvserver']['servicetype'] = True

    if ipv46:
        payload['crvserver']['ipv46'] = True

    if port:
        payload['crvserver']['port'] = True

    if range:
        payload['crvserver']['range'] = True

    if cachetype:
        payload['crvserver']['cachetype'] = True

    if redirect:
        payload['crvserver']['redirect'] = True

    if onpolicymatch:
        payload['crvserver']['onpolicymatch'] = True

    if redirecturl:
        payload['crvserver']['redirecturl'] = True

    if clttimeout:
        payload['crvserver']['clttimeout'] = True

    if precedence:
        payload['crvserver']['precedence'] = True

    if arp:
        payload['crvserver']['arp'] = True

    if ghost:
        payload['crvserver']['ghost'] = True

    if ns_map:
        payload['crvserver']['map'] = True

    if format:
        payload['crvserver']['format'] = True

    if via:
        payload['crvserver']['via'] = True

    if cachevserver:
        payload['crvserver']['cachevserver'] = True

    if dnsvservername:
        payload['crvserver']['dnsvservername'] = True

    if destinationvserver:
        payload['crvserver']['destinationvserver'] = True

    if domain:
        payload['crvserver']['domain'] = True

    if sopersistencetimeout:
        payload['crvserver']['sopersistencetimeout'] = True

    if sothreshold:
        payload['crvserver']['sothreshold'] = True

    if reuse:
        payload['crvserver']['reuse'] = True

    if state:
        payload['crvserver']['state'] = True

    if downstateflush:
        payload['crvserver']['downstateflush'] = True

    if backupvserver:
        payload['crvserver']['backupvserver'] = True

    if disableprimaryondown:
        payload['crvserver']['disableprimaryondown'] = True

    if l2conn:
        payload['crvserver']['l2conn'] = True

    if backendssl:
        payload['crvserver']['backendssl'] = True

    if listenpolicy:
        payload['crvserver']['listenpolicy'] = True

    if listenpriority:
        payload['crvserver']['listenpriority'] = True

    if tcpprofilename:
        payload['crvserver']['tcpprofilename'] = True

    if httpprofilename:
        payload['crvserver']['httpprofilename'] = True

    if comment:
        payload['crvserver']['comment'] = True

    if srcipexpr:
        payload['crvserver']['srcipexpr'] = True

    if originusip:
        payload['crvserver']['originusip'] = True

    if useportrange:
        payload['crvserver']['useportrange'] = True

    if appflowlog:
        payload['crvserver']['appflowlog'] = True

    if netprofile:
        payload['crvserver']['netprofile'] = True

    if icmpvsrresponse:
        payload['crvserver']['icmpvsrresponse'] = True

    if rhistate:
        payload['crvserver']['rhistate'] = True

    if newname:
        payload['crvserver']['newname'] = True

    execution = __proxy__['citrixns.post']('config/crvserver?action=unset', payload)

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


def update_crpolicy(policyname=None, rule=None, action=None, logaction=None, newname=None, save=False):
    '''
    Update the running configuration for the crpolicy config key.

    policyname(str): Name for the cache redirection policy. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters. Cannot be changed after the policy is created. The following
        requirement applies only to the NetScaler CLI:  If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, or name of a named expression, against which traffic is evaluated. Written in the classic syntax.
        Note:Maximum length of a string literal in the expression is 255 characters. A longer string can be split into
        smaller strings of up to 255 characters each, and the smaller strings concatenated with the + operator. For
        example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" + ";lt;string of
        245 characters;gt;" The following requirements apply only to the NetScaler CLI: * If the expression includes one
        or more spaces, enclose the entire expression in double quotation marks. * If the expression itself includes
        double quotation marks, escape the quotations by using the \\ character.  * Alternatively, you can use single
        quotation marks to enclose the rule, in which case you do not have to escape the double quotation marks.

    action(str): Name of the built-in cache redirection action: CACHE/ORIGIN.

    logaction(str): The log action associated with the cache redirection policy.

    newname(str): The new name of the content switching policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.update_crpolicy <args>

    '''

    result = {}

    payload = {'crpolicy': {}}

    if policyname:
        payload['crpolicy']['policyname'] = policyname

    if rule:
        payload['crpolicy']['rule'] = rule

    if action:
        payload['crpolicy']['action'] = action

    if logaction:
        payload['crpolicy']['logaction'] = logaction

    if newname:
        payload['crpolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/crpolicy', payload)

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


def update_crvserver(name=None, td=None, servicetype=None, ipv46=None, port=None, range=None, cachetype=None,
                     redirect=None, onpolicymatch=None, redirecturl=None, clttimeout=None, precedence=None, arp=None,
                     ghost=None, ns_map=None, format=None, via=None, cachevserver=None, dnsvservername=None,
                     destinationvserver=None, domain=None, sopersistencetimeout=None, sothreshold=None, reuse=None,
                     state=None, downstateflush=None, backupvserver=None, disableprimaryondown=None, l2conn=None,
                     backendssl=None, listenpolicy=None, listenpriority=None, tcpprofilename=None, httpprofilename=None,
                     comment=None, srcipexpr=None, originusip=None, useportrange=None, appflowlog=None, netprofile=None,
                     icmpvsrresponse=None, rhistate=None, newname=None, save=False):
    '''
    Update the running configuration for the crvserver config key.

    name(str): Name for the cache redirection virtual server. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters. Can be changed after the cache redirection virtual server is
        created. The following requirement applies only to the NetScaler CLI:  If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my server" or my server). Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    servicetype(str): Protocol (type of service) handled by the virtual server. Possible values = HTTP, SSL, NNTP, HDX

    ipv46(str): IPv4 or IPv6 address of the cache redirection virtual server. Usually a public IP address. Clients send
        connection requests to this IP address. Note: For a transparent cache redirection virtual server, use an asterisk
        (*) to specify a wildcard virtual server address.

    port(int): Port number of the virtual server. Default value: 80 Minimum value = 1 Maximum value = 65534

    range(int): Number of consecutive IP addresses, starting with the address specified by the IPAddress parameter, to
        include in a range of addresses assigned to this virtual server. Default value: 1 Minimum value = 1 Maximum value
        = 254

    cachetype(str): Mode of operation for the cache redirection virtual server. Available settings function as follows: *
        TRANSPARENT - Intercept all traffic flowing to the appliance and apply cache redirection policies to determine
        whether content should be served from the cache or from the origin server. * FORWARD - Resolve the hostname of
        the incoming request, by using a DNS server, and forward requests for non-cacheable content to the resolved
        origin servers. Cacheable requests are sent to the configured cache servers. * REVERSE - Configure reverse proxy
        caches for specific origin servers. Incoming traffic directed to the reverse proxy can either be served from a
        cache server or be sent to the origin server with or without modification to the URL. Possible values =
        TRANSPARENT, REVERSE, FORWARD

    redirect(str): Type of cache server to which to redirect HTTP requests. Available settings function as follows: * CACHE -
        Direct all requests to the cache. * POLICY - Apply the cache redirection policy to determine whether the request
        should be directed to the cache or to the origin. * ORIGIN - Direct all requests to the origin server. Default
        value: POLICY Possible values = CACHE, POLICY, ORIGIN

    onpolicymatch(str): Redirect requests that match the policy to either the cache or the origin server, as specified. Note:
        For this option to work, you must set the cache redirection type to POLICY. Default value: ORIGIN Possible values
        = CACHE, ORIGIN

    redirecturl(str): URL of the server to which to redirect traffic if the cache redirection virtual server configured on
        the NetScaler appliance becomes unavailable. Minimum length = 1 Maximum length = 128

    clttimeout(int): Time-out value, in seconds, after which to terminate an idle client connection. Minimum value = 0
        Maximum value = 31536000

    precedence(str): Type of policy (URL or RULE) that takes precedence on the cache redirection virtual server. Applies only
        to cache redirection virtual servers that have both URL and RULE based policies. If you specify URL, URL based
        policies are applied first, in the following order: 1. Domain and exact URL 2. Domain, prefix and suffix 3.
        Domain and suffix 4. Domain and prefix 5. Domain only 6. Exact URL 7. Prefix and suffix 8. Suffix only 9. Prefix
        only 10. Default If you specify RULE, the rule based policies are applied before URL based policies are applied.
        Default value: RULE Possible values = RULE, URL

    arp(str): Use ARP to determine the destination MAC address. Possible values = ON, OFF

    ghost(str): . Possible values = ON, OFF

    ns_map(str): Obsolete. Possible values = ON, OFF

    format(str): . Possible values = ON, OFF

    via(str): Insert a via header in each HTTP request. In the case of a cache miss, the request is redirected from the cache
        server to the origin server. This header indicates whether the request is being sent from a cache server. Default
        value: ON Possible values = ON, OFF

    cachevserver(str): Name of the default cache virtual server to which to redirect requests (the default target of the
        cache redirection virtual server). Minimum length = 1

    dnsvservername(str): Name of the DNS virtual server that resolves domain names arriving at the forward proxy virtual
        server. Note: This parameter applies only to forward proxy virtual servers, not reverse or transparent. Minimum
        length = 1

    destinationvserver(str): Destination virtual server for a transparent or forward proxy cache redirection virtual server.
        Minimum length = 1

    domain(str): Default domain for reverse proxies. Domains are configured to direct an incoming request from a specified
        source domain to a specified target domain. There can be several configured pairs of source and target domains.
        You can select one pair to be the default. If the host header or URL of an incoming request does not include a
        source domain, this option sends the request to the specified target domain. Minimum length = 1

    sopersistencetimeout(int): Time-out, in minutes, for spillover persistence. Minimum value = 2 Maximum value = 24

    sothreshold(int): For CONNECTION (or) DYNAMICCONNECTION spillover, the number of connections above which the virtual
        server enters spillover mode. For BANDWIDTH spillover, the amount of incoming and outgoing traffic (in Kbps)
        before spillover. For HEALTH spillover, the percentage of active services (by weight) below which spillover
        occurs. Minimum value = 1

    reuse(str): Reuse TCP connections to the origin server across client connections. Do not set this parameter unless the
        Service Type parameter is set to HTTP. If you set this parameter to OFF, the possible settings of the Redirect
        parameter function as follows: * CACHE - TCP connections to the cache servers are not reused. * ORIGIN - TCP
        connections to the origin servers are not reused.  * POLICY - TCP connections to the origin servers are not
        reused. If you set the Reuse parameter to ON, connections to origin servers and connections to cache servers are
        reused. Default value: ON Possible values = ON, OFF

    state(str): Initial state of the cache redirection virtual server. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    downstateflush(str): Perform delayed cleanup of connections to this virtual server. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    backupvserver(str): Name of the backup virtual server to which traffic is forwarded if the active server becomes
        unavailable. Minimum length = 1

    disableprimaryondown(str): Continue sending traffic to a backup virtual server even after the primary virtual server
        comes UP from the DOWN state. Default value: DISABLED Possible values = ENABLED, DISABLED

    l2conn(str): Use L2 parameters, such as MAC, VLAN, and channel to identify a connection. Possible values = ON, OFF

    backendssl(str): Decides whether the backend connection made by NS to the origin server will be HTTP or SSL. Applicable
        only for SSL type CR Forward proxy vserver. Default value: DISABLED Possible values = ENABLED, DISABLED

    listenpolicy(str): String specifying the listen policy for the cache redirection virtual server. Can be either an in-line
        expression or the name of a named expression. Default value: "NONE"

    listenpriority(int): Priority of the listen policy specified by the Listen Policy parameter. The lower the number, higher
        the priority. Default value: 101 Minimum value = 0 Maximum value = 100

    tcpprofilename(str): Name of the profile containing TCP configuration information for the cache redirection virtual
        server. Minimum length = 1 Maximum length = 127

    httpprofilename(str): Name of the profile containing HTTP configuration information for cache redirection virtual server.
        Minimum length = 1 Maximum length = 127

    comment(str): Comments associated with this virtual server. Maximum length = 256

    srcipexpr(str): Expression used to extract the source IP addresses from the requests originating from the cache. Can be
        either an in-line expression or the name of a named expression. Minimum length = 1 Maximum length = 1500

    originusip(str): Use the clients IP address as the source IP address in requests sent to the origin server.  Note: You
        can enable this parameter to implement fully transparent CR deployment. Possible values = ON, OFF

    useportrange(str): Use a port number from the port range (set by using the set ns param command, or in the Create Virtual
        Server (Cache Redirection) dialog box) as the source port in the requests sent to the origin server. Default
        value: OFF Possible values = ON, OFF

    appflowlog(str): Enable logging of AppFlow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    netprofile(str): Name of the network profile containing network configurations for the cache redirection virtual server.
        Minimum length = 1 Maximum length = 127

    icmpvsrresponse(str): Criterion for responding to PING requests sent to this virtual server. If ACTIVE, respond only if
        the virtual server is available. If PASSIVE, respond even if the virtual server is not available. Default value:
        PASSIVE Possible values = PASSIVE, ACTIVE

    rhistate(str): A host route is injected according to the setting on the virtual servers  * If set to PASSIVE on all the
        virtual servers that share the IP address, the appliance always injects the hostroute.  * If set to ACTIVE on all
        the virtual servers that share the IP address, the appliance injects even if one virtual server is UP.  * If set
        to ACTIVE on some virtual servers and PASSIVE on the others, the appliance, injects even if one virtual server
        set to ACTIVE is UP. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    newname(str): New name for the cache redirection virtual server. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign
        (@), equal sign (=), and hyphen (-) characters. If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my name" or my name). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' cache_redirection.update_crvserver <args>

    '''

    result = {}

    payload = {'crvserver': {}}

    if name:
        payload['crvserver']['name'] = name

    if td:
        payload['crvserver']['td'] = td

    if servicetype:
        payload['crvserver']['servicetype'] = servicetype

    if ipv46:
        payload['crvserver']['ipv46'] = ipv46

    if port:
        payload['crvserver']['port'] = port

    if range:
        payload['crvserver']['range'] = range

    if cachetype:
        payload['crvserver']['cachetype'] = cachetype

    if redirect:
        payload['crvserver']['redirect'] = redirect

    if onpolicymatch:
        payload['crvserver']['onpolicymatch'] = onpolicymatch

    if redirecturl:
        payload['crvserver']['redirecturl'] = redirecturl

    if clttimeout:
        payload['crvserver']['clttimeout'] = clttimeout

    if precedence:
        payload['crvserver']['precedence'] = precedence

    if arp:
        payload['crvserver']['arp'] = arp

    if ghost:
        payload['crvserver']['ghost'] = ghost

    if ns_map:
        payload['crvserver']['map'] = ns_map

    if format:
        payload['crvserver']['format'] = format

    if via:
        payload['crvserver']['via'] = via

    if cachevserver:
        payload['crvserver']['cachevserver'] = cachevserver

    if dnsvservername:
        payload['crvserver']['dnsvservername'] = dnsvservername

    if destinationvserver:
        payload['crvserver']['destinationvserver'] = destinationvserver

    if domain:
        payload['crvserver']['domain'] = domain

    if sopersistencetimeout:
        payload['crvserver']['sopersistencetimeout'] = sopersistencetimeout

    if sothreshold:
        payload['crvserver']['sothreshold'] = sothreshold

    if reuse:
        payload['crvserver']['reuse'] = reuse

    if state:
        payload['crvserver']['state'] = state

    if downstateflush:
        payload['crvserver']['downstateflush'] = downstateflush

    if backupvserver:
        payload['crvserver']['backupvserver'] = backupvserver

    if disableprimaryondown:
        payload['crvserver']['disableprimaryondown'] = disableprimaryondown

    if l2conn:
        payload['crvserver']['l2conn'] = l2conn

    if backendssl:
        payload['crvserver']['backendssl'] = backendssl

    if listenpolicy:
        payload['crvserver']['listenpolicy'] = listenpolicy

    if listenpriority:
        payload['crvserver']['listenpriority'] = listenpriority

    if tcpprofilename:
        payload['crvserver']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['crvserver']['httpprofilename'] = httpprofilename

    if comment:
        payload['crvserver']['comment'] = comment

    if srcipexpr:
        payload['crvserver']['srcipexpr'] = srcipexpr

    if originusip:
        payload['crvserver']['originusip'] = originusip

    if useportrange:
        payload['crvserver']['useportrange'] = useportrange

    if appflowlog:
        payload['crvserver']['appflowlog'] = appflowlog

    if netprofile:
        payload['crvserver']['netprofile'] = netprofile

    if icmpvsrresponse:
        payload['crvserver']['icmpvsrresponse'] = icmpvsrresponse

    if rhistate:
        payload['crvserver']['rhistate'] = rhistate

    if newname:
        payload['crvserver']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/crvserver', payload)

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
