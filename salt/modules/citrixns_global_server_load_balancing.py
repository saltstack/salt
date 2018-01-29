# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the global-server-load-balancing key.

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

__virtualname__ = 'global_server_load_balancing'


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

    return False, 'The global_server_load_balancing execution module can only be loaded for citrixns proxy minions.'


def add_gslbservice(servicename=None, cnameentry=None, ip=None, servername=None, servicetype=None, port=None,
                    publicip=None, publicport=None, maxclient=None, healthmonitor=None, sitename=None, state=None,
                    cip=None, cipheader=None, sitepersistence=None, cookietimeout=None, siteprefix=None, clttimeout=None,
                    svrtimeout=None, maxbandwidth=None, downstateflush=None, maxaaausers=None, monthreshold=None,
                    hashid=None, comment=None, appflowlog=None, naptrreplacement=None, naptrorder=None,
                    naptrservices=None, naptrdomainttl=None, naptrpreference=None, ipaddress=None, viewname=None,
                    viewip=None, weight=None, monitor_name_svc=None, newname=None, save=False):
    '''
    Add a new gslbservice to the running configuration.

    servicename(str): Name for the GSLB service. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the GSLB service is created.  CLI Users: If the name includes one or
        more spaces, enclose the name in double or single quotation marks (for example, "my gslbsvc" or my gslbsvc).
        Minimum length = 1

    cnameentry(str): Canonical name of the GSLB service. Used in CNAME-based GSLB. Minimum length = 1

    ip(str): IP address for the GSLB service. Should represent a load balancing, content switching, or VPN virtual server on
        the NetScaler appliance, or the IP address of another load balancing device. Minimum length = 1

    servername(str): Name of the server hosting the GSLB service. Minimum length = 1

    servicetype(str): Type of service to create. Default value: NSSVC_SERVICE_UNKNOWN Possible values = HTTP, FTP, TCP, UDP,
        SSL, SSL_BRIDGE, SSL_TCP, NNTP, ANY, SIP_UDP, SIP_TCP, SIP_SSL, RADIUS, RDP, RTSP, MYSQL, MSSQL, ORACLE

    port(int): Port on which the load balancing entity represented by this GSLB service listens. Minimum value = 1 Range 1 -
        65535 * in CLI is represented as 65535 in NITRO API

    publicip(str): The public IP address that a NAT device translates to the GSLB services private IP address. Optional.

    publicport(int): The public port associated with the GSLB services public IP address. The port is mapped to the services
        private port number. Applicable to the local GSLB service. Optional.

    maxclient(int): The maximum number of open connections that the service can support at any given time. A GSLB service
        whose connection count reaches the maximum is not considered when a GSLB decision is made, until the connection
        count drops below the maximum. Minimum value = 0 Maximum value = 4294967294

    healthmonitor(str): Monitor the health of the GSLB service. Default value: YES Possible values = YES, NO

    sitename(str): Name of the GSLB site to which the service belongs. Minimum length = 1

    state(str): Enable or disable the service. Default value: ENABLED Possible values = ENABLED, DISABLED

    cip(str): In the request that is forwarded to the GSLB service, insert a header that stores the clients IP address.
        Client IP header insertion is used in connection-proxy based site persistence. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    cipheader(str): Name for the HTTP header that stores the clients IP address. Used with the Client IP option. If client IP
        header insertion is enabled on the service and a name is not specified for the header, the NetScaler appliance
        uses the name specified by the cipHeader parameter in the set ns param command or, in the GUI, the Client IP
        Header parameter in the Configure HTTP Parameters dialog box. Minimum length = 1

    sitepersistence(str): Use cookie-based site persistence. Applicable only to HTTP and SSL GSLB services. Possible values =
        ConnectionProxy, HTTPRedirect, NONE

    cookietimeout(int): Timeout value, in minutes, for the cookie, when cookie based site persistence is enabled. Minimum
        value = 0 Maximum value = 1440

    siteprefix(str): The sites prefix string. When the service is bound to a GSLB virtual server, a GSLB site domain is
        generated internally for each bound service-domain pair by concatenating the site prefix of the service and the
        name of the domain. If the special string NONE is specified, the site-prefix string is unset. When implementing
        HTTP redirect site persistence, the NetScaler appliance redirects GSLB requests to GSLB services by using their
        site domains.

    clttimeout(int): Idle time, in seconds, after which a client connection is terminated. Applicable if connection proxy
        based site persistence is used. Minimum value = 0 Maximum value = 31536000

    svrtimeout(int): Idle time, in seconds, after which a server connection is terminated. Applicable if connection proxy
        based site persistence is used. Minimum value = 0 Maximum value = 31536000

    maxbandwidth(int): Integer specifying the maximum bandwidth allowed for the service. A GSLB service whose bandwidth
        reaches the maximum is not considered when a GSLB decision is made, until its bandwidth consumption drops below
        the maximum.

    downstateflush(str): Flush all active transactions associated with the GSLB service when its state transitions from UP to
        DOWN. Do not enable this option for services that must complete their transactions. Applicable if connection
        proxy based site persistence is used. Possible values = ENABLED, DISABLED

    maxaaausers(int): Maximum number of SSL VPN users that can be logged on concurrently to the VPN virtual server that is
        represented by this GSLB service. A GSLB service whose user count reaches the maximum is not considered when a
        GSLB decision is made, until the count drops below the maximum. Minimum value = 0 Maximum value = 65535

    monthreshold(int): Monitoring threshold value for the GSLB service. If the sum of the weights of the monitors that are
        bound to this GSLB service and are in the UP state is not equal to or greater than this threshold value, the
        service is marked as DOWN. Minimum value = 0 Maximum value = 65535

    hashid(int): Unique hash identifier for the GSLB service, used by hash based load balancing methods. Minimum value = 1

    comment(str): Any comments that you might want to associate with the GSLB service.

    appflowlog(str): Enable logging appflow flow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    naptrreplacement(str): The replacement domain name for this NAPTR. Maximum length = 255

    naptrorder(int): An integer specifying the order in which the NAPTR records MUST be processed in order to accurately
        represent the ordered list of Rules. The ordering is from lowest to highest. Default value: 1 Minimum value = 1
        Maximum value = 65535

    naptrservices(str): Service Parameters applicable to this delegation path. Maximum length = 255

    naptrdomainttl(int): Modify the TTL of the internally created naptr domain. Default value: 3600 Minimum value = 1

    naptrpreference(int): An integer specifying the preference of this NAPTR among NAPTR records having same order. lower the
        number, higher the preference. Default value: 1 Minimum value = 1 Maximum value = 65535

    ipaddress(str): The new IP address of the service.

    viewname(str): Name of the DNS view of the service. A DNS view is used in global server load balancing (GSLB) to return a
        predetermined IP address to a specific group of clients, which are identified by using a DNS policy. Minimum
        length = 1

    viewip(str): IP address to be used for the given view.

    weight(int): Weight to assign to the monitor-service binding. A larger number specifies a greater weight. Contributes to
        the monitoring threshold, which determines the state of the service. Minimum value = 1 Maximum value = 100

    monitor_name_svc(str): Name of the monitor to bind to the service. Minimum length = 1

    newname(str): New name for the GSLB service. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.add_gslbservice <args>

    '''

    result = {}

    payload = {'gslbservice': {}}

    if servicename:
        payload['gslbservice']['servicename'] = servicename

    if cnameentry:
        payload['gslbservice']['cnameentry'] = cnameentry

    if ip:
        payload['gslbservice']['ip'] = ip

    if servername:
        payload['gslbservice']['servername'] = servername

    if servicetype:
        payload['gslbservice']['servicetype'] = servicetype

    if port:
        payload['gslbservice']['port'] = port

    if publicip:
        payload['gslbservice']['publicip'] = publicip

    if publicport:
        payload['gslbservice']['publicport'] = publicport

    if maxclient:
        payload['gslbservice']['maxclient'] = maxclient

    if healthmonitor:
        payload['gslbservice']['healthmonitor'] = healthmonitor

    if sitename:
        payload['gslbservice']['sitename'] = sitename

    if state:
        payload['gslbservice']['state'] = state

    if cip:
        payload['gslbservice']['cip'] = cip

    if cipheader:
        payload['gslbservice']['cipheader'] = cipheader

    if sitepersistence:
        payload['gslbservice']['sitepersistence'] = sitepersistence

    if cookietimeout:
        payload['gslbservice']['cookietimeout'] = cookietimeout

    if siteprefix:
        payload['gslbservice']['siteprefix'] = siteprefix

    if clttimeout:
        payload['gslbservice']['clttimeout'] = clttimeout

    if svrtimeout:
        payload['gslbservice']['svrtimeout'] = svrtimeout

    if maxbandwidth:
        payload['gslbservice']['maxbandwidth'] = maxbandwidth

    if downstateflush:
        payload['gslbservice']['downstateflush'] = downstateflush

    if maxaaausers:
        payload['gslbservice']['maxaaausers'] = maxaaausers

    if monthreshold:
        payload['gslbservice']['monthreshold'] = monthreshold

    if hashid:
        payload['gslbservice']['hashid'] = hashid

    if comment:
        payload['gslbservice']['comment'] = comment

    if appflowlog:
        payload['gslbservice']['appflowlog'] = appflowlog

    if naptrreplacement:
        payload['gslbservice']['naptrreplacement'] = naptrreplacement

    if naptrorder:
        payload['gslbservice']['naptrorder'] = naptrorder

    if naptrservices:
        payload['gslbservice']['naptrservices'] = naptrservices

    if naptrdomainttl:
        payload['gslbservice']['naptrdomainttl'] = naptrdomainttl

    if naptrpreference:
        payload['gslbservice']['naptrpreference'] = naptrpreference

    if ipaddress:
        payload['gslbservice']['ipaddress'] = ipaddress

    if viewname:
        payload['gslbservice']['viewname'] = viewname

    if viewip:
        payload['gslbservice']['viewip'] = viewip

    if weight:
        payload['gslbservice']['weight'] = weight

    if monitor_name_svc:
        payload['gslbservice']['monitor_name_svc'] = monitor_name_svc

    if newname:
        payload['gslbservice']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/gslbservice', payload)

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


def add_gslbservice_dnsview_binding(viewname=None, servicename=None, viewip=None, save=False):
    '''
    Add a new gslbservice_dnsview_binding to the running configuration.

    viewname(str): Name of the DNS view of the service. A DNS view is used in global server load balancing (GSLB) to return a
        predetermined IP address to a specific group of clients, which are identified by using a DNS policy. Minimum
        length = 1

    servicename(str): Name of the GSLB service. Minimum length = 1

    viewip(str): IP address to be used for the given view.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.add_gslbservice_dnsview_binding <args>

    '''

    result = {}

    payload = {'gslbservice_dnsview_binding': {}}

    if viewname:
        payload['gslbservice_dnsview_binding']['viewname'] = viewname

    if servicename:
        payload['gslbservice_dnsview_binding']['servicename'] = servicename

    if viewip:
        payload['gslbservice_dnsview_binding']['viewip'] = viewip

    execution = __proxy__['citrixns.post']('config/gslbservice_dnsview_binding', payload)

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


def add_gslbservice_lbmonitor_binding(servicename=None, weight=None, monitor_name=None, monstate=None, save=False):
    '''
    Add a new gslbservice_lbmonitor_binding to the running configuration.

    servicename(str): Name of the GSLB service. Minimum length = 1

    weight(int): Weight to assign to the monitor-service binding. A larger number specifies a greater weight. Contributes to
        the monitoring threshold, which determines the state of the service. Minimum value = 1 Maximum value = 100

    monitor_name(str): Monitor name.

    monstate(str): State of the monitor bound to gslb service. Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.add_gslbservice_lbmonitor_binding <args>

    '''

    result = {}

    payload = {'gslbservice_lbmonitor_binding': {}}

    if servicename:
        payload['gslbservice_lbmonitor_binding']['servicename'] = servicename

    if weight:
        payload['gslbservice_lbmonitor_binding']['weight'] = weight

    if monitor_name:
        payload['gslbservice_lbmonitor_binding']['monitor_name'] = monitor_name

    if monstate:
        payload['gslbservice_lbmonitor_binding']['monstate'] = monstate

    execution = __proxy__['citrixns.post']('config/gslbservice_lbmonitor_binding', payload)

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


def add_gslbsite(sitename=None, sitetype=None, siteipaddress=None, publicip=None, metricexchange=None,
                 nwmetricexchange=None, sessionexchange=None, triggermonitor=None, parentsite=None, clip=None,
                 publicclip=None, naptrreplacementsuffix=None, backupparentlist=None, save=False):
    '''
    Add a new gslbsite to the running configuration.

    sitename(str): Name for the GSLB site. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the virtual server is created.  CLI Users: If the name includes
        one or more spaces, enclose the name in double or single quotation marks (for example, "my gslbsite" or my
        gslbsite). Minimum length = 1

    sitetype(str): Type of site to create. If the type is not specified, the appliance automatically detects and sets the
        type on the basis of the IP address being assigned to the site. If the specified site IP address is owned by the
        appliance (for example, a MIP address or SNIP address), the site is a local site. Otherwise, it is a remote site.
        Default value: NONE Possible values = REMOTE, LOCAL

    siteipaddress(str): IP address for the GSLB site. The GSLB site uses this IP address to communicate with other GSLB
        sites. For a local site, use any IP address that is owned by the appliance (for example, a SNIP or MIP address,
        or the IP address of the ADNS service). Minimum length = 1

    publicip(str): Public IP address for the local site. Required only if the appliance is deployed in a private address
        space and the site has a public IP address hosted on an external firewall or a NAT device. Minimum length = 1

    metricexchange(str): Exchange metrics with other sites. Metrics are exchanged by using Metric Exchange Protocol (MEP).
        The appliances in the GSLB setup exchange health information once every second.   If you disable metrics
        exchange, you can use only static load balancing methods (such as round robin, static proximity, or the
        hash-based methods), and if you disable metrics exchange when a dynamic load balancing method (such as least
        connection) is in operation, the appliance falls back to round robin. Also, if you disable metrics exchange, you
        must use a monitor to determine the state of GSLB services. Otherwise, the service is marked as DOWN. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    nwmetricexchange(str): Exchange, with other GSLB sites, network metrics such as round-trip time (RTT), learned from
        communications with various local DNS (LDNS) servers used by clients. RTT information is used in the dynamic RTT
        load balancing method, and is exchanged every 5 seconds. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    sessionexchange(str): Exchange persistent session entries with other GSLB sites every five seconds. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    triggermonitor(str): Specify the conditions under which the GSLB service must be monitored by a monitor, if one is bound.
        Available settings function as follows: * ALWAYS - Monitor the GSLB service at all times. * MEPDOWN - Monitor the
        GSLB service only when the exchange of metrics through the Metrics Exchange Protocol (MEP) is disabled.
        MEPDOWN_SVCDOWN - Monitor the service in either of the following situations:  * The exchange of metrics through
        MEP is disabled. * The exchange of metrics through MEP is enabled but the status of the service, learned through
        metrics exchange, is DOWN. Default value: ALWAYS Possible values = ALWAYS, MEPDOWN, MEPDOWN_SVCDOWN

    parentsite(str): Parent site of the GSLB site, in a parent-child topology.

    clip(str): Cluster IP address. Specify this parameter to connect to the remote cluster site for GSLB auto-sync. Note: The
        cluster IP address is defined when creating the cluster.

    publicclip(str): IP address to be used to globally access the remote cluster when it is deployed behind a NAT. It can be
        same as the normal cluster IP address.

    naptrreplacementsuffix(str): The naptr replacement suffix configured here will be used to construct the naptr replacement
        field in NAPTR record. Minimum length = 1

    backupparentlist(list(str)): The list of backup gslb sites configured in preferred order. Need to be parent gsb sites.
        Default value: "None"

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.add_gslbsite <args>

    '''

    result = {}

    payload = {'gslbsite': {}}

    if sitename:
        payload['gslbsite']['sitename'] = sitename

    if sitetype:
        payload['gslbsite']['sitetype'] = sitetype

    if siteipaddress:
        payload['gslbsite']['siteipaddress'] = siteipaddress

    if publicip:
        payload['gslbsite']['publicip'] = publicip

    if metricexchange:
        payload['gslbsite']['metricexchange'] = metricexchange

    if nwmetricexchange:
        payload['gslbsite']['nwmetricexchange'] = nwmetricexchange

    if sessionexchange:
        payload['gslbsite']['sessionexchange'] = sessionexchange

    if triggermonitor:
        payload['gslbsite']['triggermonitor'] = triggermonitor

    if parentsite:
        payload['gslbsite']['parentsite'] = parentsite

    if clip:
        payload['gslbsite']['clip'] = clip

    if publicclip:
        payload['gslbsite']['publicclip'] = publicclip

    if naptrreplacementsuffix:
        payload['gslbsite']['naptrreplacementsuffix'] = naptrreplacementsuffix

    if backupparentlist:
        payload['gslbsite']['backupparentlist'] = backupparentlist

    execution = __proxy__['citrixns.post']('config/gslbsite', payload)

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


def add_gslbvserver(name=None, servicetype=None, iptype=None, dnsrecordtype=None, lbmethod=None,
                    backupsessiontimeout=None, backuplbmethod=None, netmask=None, v6netmasklen=None, tolerance=None,
                    persistencetype=None, persistenceid=None, persistmask=None, v6persistmasklen=None, timeout=None,
                    edr=None, ecs=None, ecsaddrvalidation=None, mir=None, disableprimaryondown=None, dynamicweight=None,
                    state=None, considereffectivestate=None, comment=None, somethod=None, sopersistence=None,
                    sopersistencetimeout=None, sothreshold=None, sobackupaction=None, appflowlog=None,
                    backupvserver=None, servicename=None, weight=None, domainname=None, ttl=None, backupip=None,
                    cookie_domain=None, cookietimeout=None, sitedomainttl=None, newname=None, save=False):
    '''
    Add a new gslbvserver to the running configuration.

    name(str): Name for the GSLB virtual server. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the virtual server is created.  CLI Users: If the name includes one
        or more spaces, enclose the name in double or single quotation marks (for example, "my vserver" or my vserver).
        Minimum length = 1

    servicetype(str): Protocol used by services bound to the virtual server. Possible values = HTTP, FTP, TCP, UDP, SSL,
        SSL_BRIDGE, SSL_TCP, NNTP, ANY, SIP_UDP, SIP_TCP, SIP_SSL, RADIUS, RDP, RTSP, MYSQL, MSSQL, ORACLE

    iptype(str): The IP type for this GSLB vserver. Default value: IPV4 Possible values = IPV4, IPV6

    dnsrecordtype(str): DNS record type to associate with the GSLB virtual servers domain name. Default value: A Possible
        values = A, AAAA, CNAME, NAPTR

    lbmethod(str): Load balancing method for the GSLB virtual server. Default value: LEASTCONNECTION Possible values =
        ROUNDROBIN, LEASTCONNECTION, LEASTRESPONSETIME, SOURCEIPHASH, LEASTBANDWIDTH, LEASTPACKETS, STATICPROXIMITY, RTT,
        CUSTOMLOAD

    backupsessiontimeout(int): A non zero value enables the feature whose minimum value is 2 minutes. The feature can be
        disabled by setting the value to zero. The created session is in effect for a specific client per domain. Minimum
        value = 0 Maximum value = 1440

    backuplbmethod(str): Backup load balancing method. Becomes operational if the primary load balancing method fails or
        cannot be used. Valid only if the primary method is based on either round-trip time (RTT) or static proximity.
        Possible values = ROUNDROBIN, LEASTCONNECTION, LEASTRESPONSETIME, SOURCEIPHASH, LEASTBANDWIDTH, LEASTPACKETS,
        STATICPROXIMITY, RTT, CUSTOMLOAD

    netmask(str): IPv4 network mask for use in the SOURCEIPHASH load balancing method. Minimum length = 1

    v6netmasklen(int): Number of bits to consider, in an IPv6 source IP address, for creating the hash that is required by
        the SOURCEIPHASH load balancing method. Default value: 128 Minimum value = 1 Maximum value = 128

    tolerance(int): Site selection tolerance, in milliseconds, for implementing the RTT load balancing method. If a sites RTT
        deviates from the lowest RTT by more than the specified tolerance, the site is not considered when the NetScaler
        appliance makes a GSLB decision. The appliance implements the round robin method of global server load balancing
        between sites whose RTT values are within the specified tolerance. If the tolerance is 0 (zero), the appliance
        always sends clients the IP address of the site with the lowest RTT. Minimum value = 0 Maximum value = 100

    persistencetype(str): Use source IP address based persistence for the virtual server.  After the load balancing method
        selects a service for the first packet, the IP address received in response to the DNS query is used for
        subsequent requests from the same client. Possible values = SOURCEIP, NONE

    persistenceid(int): The persistence ID for the GSLB virtual server. The ID is a positive integer that enables GSLB sites
        to identify the GSLB virtual server, and is required if source IP address based or spill over based persistence
        is enabled on the virtual server. Minimum value = 0 Maximum value = 65535

    persistmask(str): The optional IPv4 network mask applied to IPv4 addresses to establish source IP address based
        persistence. Minimum length = 1

    v6persistmasklen(int): Number of bits to consider in an IPv6 source IP address when creating source IP address based
        persistence sessions. Default value: 128 Minimum value = 1 Maximum value = 128

    timeout(int): Idle time, in minutes, after which a persistence entry is cleared. Default value: 2 Minimum value = 2
        Maximum value = 1440

    edr(str): Send clients an empty DNS response when the GSLB virtual server is DOWN. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    ecs(str): If enabled, respond with EDNS Client Subnet (ECS) option in the response for a DNS query with ECS. The ECS
        address will be used for persistence and spillover persistence (if enabled) instead of the LDNS address.
        Persistence mask is ignored if ECS is enabled. Default value: DISABLED Possible values = ENABLED, DISABLED

    ecsaddrvalidation(str): Validate if ECS address is a private or unroutable address and in such cases, use the LDNS IP.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    mir(str): Include multiple IP addresses in the DNS responses sent to clients. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    disableprimaryondown(str): Continue to direct traffic to the backup chain even after the primary GSLB virtual server
        returns to the UP state. Used when spillover is configured for the virtual server. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    dynamicweight(str): Specify if the appliance should consider the service count, service weights, or ignore both when
        using weight-based load balancing methods. The state of the number of services bound to the virtual server help
        the appliance to select the service. Default value: DISABLED Possible values = SERVICECOUNT, SERVICEWEIGHT,
        DISABLED

    state(str): State of the GSLB virtual server. Default value: ENABLED Possible values = ENABLED, DISABLED

    considereffectivestate(str): If the primary state of all bound GSLB services is DOWN, consider the effective states of
        all the GSLB services, obtained through the Metrics Exchange Protocol (MEP), when determining the state of the
        GSLB virtual server. To consider the effective state, set the parameter to STATE_ONLY. To disregard the effective
        state, set the parameter to NONE.   The effective state of a GSLB service is the ability of the corresponding
        virtual server to serve traffic. The effective state of the load balancing virtual server, which is transferred
        to the GSLB service, is UP even if only one virtual server in the backup chain of virtual servers is in the UP
        state. Default value: NONE Possible values = NONE, STATE_ONLY

    comment(str): Any comments that you might want to associate with the GSLB virtual server.

    somethod(str): Type of threshold that, when exceeded, triggers spillover. Available settings function as follows: *
        CONNECTION - Spillover occurs when the number of client connections exceeds the threshold. * DYNAMICCONNECTION -
        Spillover occurs when the number of client connections at the GSLB virtual server exceeds the sum of the maximum
        client (Max Clients) settings for bound GSLB services. Do not specify a spillover threshold for this setting,
        because the threshold is implied by the Max Clients settings of the bound GSLB services. * BANDWIDTH - Spillover
        occurs when the bandwidth consumed by the GSLB virtual servers incoming and outgoing traffic exceeds the
        threshold.  * HEALTH - Spillover occurs when the percentage of weights of the GSLB services that are UP drops
        below the threshold. For example, if services gslbSvc1, gslbSvc2, and gslbSvc3 are bound to a virtual server,
        with weights 1, 2, and 3, and the spillover threshold is 50%, spillover occurs if gslbSvc1 and gslbSvc3 or
        gslbSvc2 and gslbSvc3 transition to DOWN.  * NONE - Spillover does not occur. Possible values = CONNECTION,
        DYNAMICCONNECTION, BANDWIDTH, HEALTH, NONE

    sopersistence(str): If spillover occurs, maintain source IP address based persistence for both primary and backup GSLB
        virtual servers. Default value: DISABLED Possible values = ENABLED, DISABLED

    sopersistencetimeout(int): Timeout for spillover persistence, in minutes. Default value: 2 Minimum value = 2 Maximum
        value = 1440

    sothreshold(int): Threshold at which spillover occurs. Specify an integer for the CONNECTION spillover method, a
        bandwidth value in kilobits per second for the BANDWIDTH method (do not enter the units), or a percentage for the
        HEALTH method (do not enter the percentage symbol). Minimum value = 1 Maximum value = 4294967287

    sobackupaction(str): Action to be performed if spillover is to take effect, but no backup chain to spillover is usable or
        exists. Possible values = DROP, ACCEPT, REDIRECT

    appflowlog(str): Enable logging appflow flow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    backupvserver(str): Name of the backup GSLB virtual server to which the appliance should to forward requests if the
        status of the primary GSLB virtual server is down or exceeds its spillover threshold. Minimum length = 1

    servicename(str): Name of the GSLB service for which to change the weight. Minimum length = 1

    weight(int): Weight to assign to the GSLB service. Minimum value = 1 Maximum value = 100

    domainname(str): Domain name for which to change the time to live (TTL) and/or backup service IP address. Minimum length
        = 1

    ttl(int): Time to live (TTL) for the domain. Minimum value = 1

    backupip(str): The IP address of the backup service for the specified domain name. Used when all the services bound to
        the domain are down, or when the backup chain of virtual servers is down. Minimum length = 1

    cookie_domain(str): The cookie domain for the GSLB site. Used when inserting the GSLB site cookie in the HTTP response.
        Minimum length = 1

    cookietimeout(int): Timeout, in minutes, for the GSLB site cookie. Minimum value = 0 Maximum value = 1440

    sitedomainttl(int): TTL, in seconds, for all internally created site domains (created when a site prefix is configured on
        a GSLB service) that are associated with this virtual server. Minimum value = 1

    newname(str): New name for the GSLB virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.add_gslbvserver <args>

    '''

    result = {}

    payload = {'gslbvserver': {}}

    if name:
        payload['gslbvserver']['name'] = name

    if servicetype:
        payload['gslbvserver']['servicetype'] = servicetype

    if iptype:
        payload['gslbvserver']['iptype'] = iptype

    if dnsrecordtype:
        payload['gslbvserver']['dnsrecordtype'] = dnsrecordtype

    if lbmethod:
        payload['gslbvserver']['lbmethod'] = lbmethod

    if backupsessiontimeout:
        payload['gslbvserver']['backupsessiontimeout'] = backupsessiontimeout

    if backuplbmethod:
        payload['gslbvserver']['backuplbmethod'] = backuplbmethod

    if netmask:
        payload['gslbvserver']['netmask'] = netmask

    if v6netmasklen:
        payload['gslbvserver']['v6netmasklen'] = v6netmasklen

    if tolerance:
        payload['gslbvserver']['tolerance'] = tolerance

    if persistencetype:
        payload['gslbvserver']['persistencetype'] = persistencetype

    if persistenceid:
        payload['gslbvserver']['persistenceid'] = persistenceid

    if persistmask:
        payload['gslbvserver']['persistmask'] = persistmask

    if v6persistmasklen:
        payload['gslbvserver']['v6persistmasklen'] = v6persistmasklen

    if timeout:
        payload['gslbvserver']['timeout'] = timeout

    if edr:
        payload['gslbvserver']['edr'] = edr

    if ecs:
        payload['gslbvserver']['ecs'] = ecs

    if ecsaddrvalidation:
        payload['gslbvserver']['ecsaddrvalidation'] = ecsaddrvalidation

    if mir:
        payload['gslbvserver']['mir'] = mir

    if disableprimaryondown:
        payload['gslbvserver']['disableprimaryondown'] = disableprimaryondown

    if dynamicweight:
        payload['gslbvserver']['dynamicweight'] = dynamicweight

    if state:
        payload['gslbvserver']['state'] = state

    if considereffectivestate:
        payload['gslbvserver']['considereffectivestate'] = considereffectivestate

    if comment:
        payload['gslbvserver']['comment'] = comment

    if somethod:
        payload['gslbvserver']['somethod'] = somethod

    if sopersistence:
        payload['gslbvserver']['sopersistence'] = sopersistence

    if sopersistencetimeout:
        payload['gslbvserver']['sopersistencetimeout'] = sopersistencetimeout

    if sothreshold:
        payload['gslbvserver']['sothreshold'] = sothreshold

    if sobackupaction:
        payload['gslbvserver']['sobackupaction'] = sobackupaction

    if appflowlog:
        payload['gslbvserver']['appflowlog'] = appflowlog

    if backupvserver:
        payload['gslbvserver']['backupvserver'] = backupvserver

    if servicename:
        payload['gslbvserver']['servicename'] = servicename

    if weight:
        payload['gslbvserver']['weight'] = weight

    if domainname:
        payload['gslbvserver']['domainname'] = domainname

    if ttl:
        payload['gslbvserver']['ttl'] = ttl

    if backupip:
        payload['gslbvserver']['backupip'] = backupip

    if cookie_domain:
        payload['gslbvserver']['cookie_domain'] = cookie_domain

    if cookietimeout:
        payload['gslbvserver']['cookietimeout'] = cookietimeout

    if sitedomainttl:
        payload['gslbvserver']['sitedomainttl'] = sitedomainttl

    if newname:
        payload['gslbvserver']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/gslbvserver', payload)

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


def add_gslbvserver_domain_binding(backupipflag=None, cookietimeout=None, backupip=None, name=None, ttl=None,
                                   domainname=None, sitedomainttl=None, cookie_domainflag=None, cookie_domain=None,
                                   save=False):
    '''
    Add a new gslbvserver_domain_binding to the running configuration.

    backupipflag(bool): The IP address of the backup service for the specified domain name. Used when all the services bound
        to the domain are down, or when the backup chain of virtual servers is down.

    cookietimeout(int): Timeout, in minutes, for the GSLB site cookie. Minimum value = 0 Maximum value = 1440

    backupip(str): The IP address of the backup service for the specified domain name. Used when all the services bound to
        the domain are down, or when the backup chain of virtual servers is down. Minimum length = 1

    name(str): Name of the virtual server on which to perform the binding operation. Minimum length = 1

    ttl(int): Time to live (TTL) for the domain. Minimum value = 1

    domainname(str): Domain name for which to change the time to live (TTL) and/or backup service IP address. Minimum length
        = 1

    sitedomainttl(int): TTL, in seconds, for all internally created site domains (created when a site prefix is configured on
        a GSLB service) that are associated with this virtual server. Minimum value = 1

    cookie_domainflag(bool): The cookie domain for the GSLB site. Used when inserting the GSLB site cookie in the HTTP
        response.

    cookie_domain(str): The cookie domain for the GSLB site. Used when inserting the GSLB site cookie in the HTTP response.
        Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.add_gslbvserver_domain_binding <args>

    '''

    result = {}

    payload = {'gslbvserver_domain_binding': {}}

    if backupipflag:
        payload['gslbvserver_domain_binding']['backupipflag'] = backupipflag

    if cookietimeout:
        payload['gslbvserver_domain_binding']['cookietimeout'] = cookietimeout

    if backupip:
        payload['gslbvserver_domain_binding']['backupip'] = backupip

    if name:
        payload['gslbvserver_domain_binding']['name'] = name

    if ttl:
        payload['gslbvserver_domain_binding']['ttl'] = ttl

    if domainname:
        payload['gslbvserver_domain_binding']['domainname'] = domainname

    if sitedomainttl:
        payload['gslbvserver_domain_binding']['sitedomainttl'] = sitedomainttl

    if cookie_domainflag:
        payload['gslbvserver_domain_binding']['cookie_domainflag'] = cookie_domainflag

    if cookie_domain:
        payload['gslbvserver_domain_binding']['cookie_domain'] = cookie_domain

    execution = __proxy__['citrixns.post']('config/gslbvserver_domain_binding', payload)

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


def add_gslbvserver_gslbservice_binding(weight=None, name=None, servicename=None, domainname=None, save=False):
    '''
    Add a new gslbvserver_gslbservice_binding to the running configuration.

    weight(int): Weight to assign to the GSLB service. Minimum value = 1 Maximum value = 100

    name(str): Name of the virtual server on which to perform the binding operation. Minimum length = 1

    servicename(str): Name of the GSLB service for which to change the weight. Minimum length = 1

    domainname(str): Domain name for which to change the time to live (TTL) and/or backup service IP address. Minimum length
        = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.add_gslbvserver_gslbservice_binding <args>

    '''

    result = {}

    payload = {'gslbvserver_gslbservice_binding': {}}

    if weight:
        payload['gslbvserver_gslbservice_binding']['weight'] = weight

    if name:
        payload['gslbvserver_gslbservice_binding']['name'] = name

    if servicename:
        payload['gslbvserver_gslbservice_binding']['servicename'] = servicename

    if domainname:
        payload['gslbvserver_gslbservice_binding']['domainname'] = domainname

    execution = __proxy__['citrixns.post']('config/gslbvserver_gslbservice_binding', payload)

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


def add_gslbvserver_spilloverpolicy_binding(priority=None, gotopriorityexpression=None, policyname=None, name=None,
                                            ns_type=None, save=False):
    '''
    Add a new gslbvserver_spilloverpolicy_binding to the running configuration.

    priority(int): Priority. Minimum value = 1 Maximum value = 2147483647

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE. o If gotoPriorityExpression is not present or if it is equal to END then
        the policy bank evaluation ends here o Else if the gotoPriorityExpression is equal to NEXT then the next policy
        in the priority order is evaluated. o Else gotoPriorityExpression is evaluated. The result of
        gotoPriorityExpression (which has to be a number) is processed as follows: - An UNDEF event is triggered if .
        gotoPriorityExpression cannot be evaluated . gotoPriorityExpression evaluates to number which is smaller than the
        maximum priority in the policy bank but is not same as any policys priority . gotoPriorityExpression evaluates to
        a priority that is smaller than the current policys priority - If the gotoPriorityExpression evaluates to the
        priority of the current policy then the next policy in the priority order is evaluated. - If the
        gotoPriorityExpression evaluates to the priority of a policy further ahead in the list then that policy will be
        evaluated next. This field is applicable only to rewrite and responder policies.

    policyname(str): Name of the policy bound to the GSLB vserver.

    name(str): Name of the virtual server on which to perform the binding operation. Minimum length = 1

    ns_type(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.add_gslbvserver_spilloverpolicy_binding <args>

    '''

    result = {}

    payload = {'gslbvserver_spilloverpolicy_binding': {}}

    if priority:
        payload['gslbvserver_spilloverpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['gslbvserver_spilloverpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policyname:
        payload['gslbvserver_spilloverpolicy_binding']['policyname'] = policyname

    if name:
        payload['gslbvserver_spilloverpolicy_binding']['name'] = name

    if ns_type:
        payload['gslbvserver_spilloverpolicy_binding']['type'] = ns_type

    execution = __proxy__['citrixns.post']('config/gslbvserver_spilloverpolicy_binding', payload)

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


def disable_gslbvserver(name=None, save=False):
    '''
    Disables a gslbvserver matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.disable_gslbvserver name=foo

    '''

    result = {}

    payload = {'gslbvserver': {}}

    if name:
        payload['gslbvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/gslbvserver?action=disable', payload)

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


def enable_gslbvserver(name=None, save=False):
    '''
    Enables a gslbvserver matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.enable_gslbvserver name=foo

    '''

    result = {}

    payload = {'gslbvserver': {}}

    if name:
        payload['gslbvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/gslbvserver?action=enable', payload)

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


def get_gslbdomain(name=None):
    '''
    Show the running configuration for the gslbdomain config key.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbdomain

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbdomain{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbdomain')

    return response


def get_gslbdomain_binding():
    '''
    Show the running configuration for the gslbdomain_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbdomain_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbdomain_binding'), 'gslbdomain_binding')

    return response


def get_gslbdomain_gslbservice_binding(name=None, servicename=None):
    '''
    Show the running configuration for the gslbdomain_gslbservice_binding config key.

    name(str): Filters results that only match the name field.

    servicename(str): Filters results that only match the servicename field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbdomain_gslbservice_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if servicename:
        search_filter.append(['servicename', servicename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbdomain_gslbservice_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbdomain_gslbservice_binding')

    return response


def get_gslbdomain_gslbvserver_binding(name=None, vservername=None):
    '''
    Show the running configuration for the gslbdomain_gslbvserver_binding config key.

    name(str): Filters results that only match the name field.

    vservername(str): Filters results that only match the vservername field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbdomain_gslbvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if vservername:
        search_filter.append(['vservername', vservername])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbdomain_gslbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbdomain_gslbvserver_binding')

    return response


def get_gslbdomain_lbmonitor_binding(name=None, monitorname=None):
    '''
    Show the running configuration for the gslbdomain_lbmonitor_binding config key.

    name(str): Filters results that only match the name field.

    monitorname(str): Filters results that only match the monitorname field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbdomain_lbmonitor_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if monitorname:
        search_filter.append(['monitorname', monitorname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbdomain_lbmonitor_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbdomain_lbmonitor_binding')

    return response


def get_gslbldnsentries(nodeid=None):
    '''
    Show the running configuration for the gslbldnsentries config key.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbldnsentries

    '''

    search_filter = []

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbldnsentries{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbldnsentries')

    return response


def get_gslbparameter():
    '''
    Show the running configuration for the gslbparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbparameter'), 'gslbparameter')

    return response


def get_gslbrunningconfig():
    '''
    Show the running configuration for the gslbrunningconfig config key.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbrunningconfig

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbrunningconfig'), 'gslbrunningconfig')

    return response


def get_gslbservice(servicename=None, cnameentry=None, ip=None, servername=None, servicetype=None, port=None,
                    publicip=None, publicport=None, maxclient=None, healthmonitor=None, sitename=None, state=None,
                    cip=None, cipheader=None, sitepersistence=None, cookietimeout=None, siteprefix=None, clttimeout=None,
                    svrtimeout=None, maxbandwidth=None, downstateflush=None, maxaaausers=None, monthreshold=None,
                    hashid=None, comment=None, appflowlog=None, naptrreplacement=None, naptrorder=None,
                    naptrservices=None, naptrdomainttl=None, naptrpreference=None, ipaddress=None, viewname=None,
                    viewip=None, weight=None, monitor_name_svc=None, newname=None):
    '''
    Show the running configuration for the gslbservice config key.

    servicename(str): Filters results that only match the servicename field.

    cnameentry(str): Filters results that only match the cnameentry field.

    ip(str): Filters results that only match the ip field.

    servername(str): Filters results that only match the servername field.

    servicetype(str): Filters results that only match the servicetype field.

    port(int): Filters results that only match the port field.

    publicip(str): Filters results that only match the publicip field.

    publicport(int): Filters results that only match the publicport field.

    maxclient(int): Filters results that only match the maxclient field.

    healthmonitor(str): Filters results that only match the healthmonitor field.

    sitename(str): Filters results that only match the sitename field.

    state(str): Filters results that only match the state field.

    cip(str): Filters results that only match the cip field.

    cipheader(str): Filters results that only match the cipheader field.

    sitepersistence(str): Filters results that only match the sitepersistence field.

    cookietimeout(int): Filters results that only match the cookietimeout field.

    siteprefix(str): Filters results that only match the siteprefix field.

    clttimeout(int): Filters results that only match the clttimeout field.

    svrtimeout(int): Filters results that only match the svrtimeout field.

    maxbandwidth(int): Filters results that only match the maxbandwidth field.

    downstateflush(str): Filters results that only match the downstateflush field.

    maxaaausers(int): Filters results that only match the maxaaausers field.

    monthreshold(int): Filters results that only match the monthreshold field.

    hashid(int): Filters results that only match the hashid field.

    comment(str): Filters results that only match the comment field.

    appflowlog(str): Filters results that only match the appflowlog field.

    naptrreplacement(str): Filters results that only match the naptrreplacement field.

    naptrorder(int): Filters results that only match the naptrorder field.

    naptrservices(str): Filters results that only match the naptrservices field.

    naptrdomainttl(int): Filters results that only match the naptrdomainttl field.

    naptrpreference(int): Filters results that only match the naptrpreference field.

    ipaddress(str): Filters results that only match the ipaddress field.

    viewname(str): Filters results that only match the viewname field.

    viewip(str): Filters results that only match the viewip field.

    weight(int): Filters results that only match the weight field.

    monitor_name_svc(str): Filters results that only match the monitor_name_svc field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbservice

    '''

    search_filter = []

    if servicename:
        search_filter.append(['servicename', servicename])

    if cnameentry:
        search_filter.append(['cnameentry', cnameentry])

    if ip:
        search_filter.append(['ip', ip])

    if servername:
        search_filter.append(['servername', servername])

    if servicetype:
        search_filter.append(['servicetype', servicetype])

    if port:
        search_filter.append(['port', port])

    if publicip:
        search_filter.append(['publicip', publicip])

    if publicport:
        search_filter.append(['publicport', publicport])

    if maxclient:
        search_filter.append(['maxclient', maxclient])

    if healthmonitor:
        search_filter.append(['healthmonitor', healthmonitor])

    if sitename:
        search_filter.append(['sitename', sitename])

    if state:
        search_filter.append(['state', state])

    if cip:
        search_filter.append(['cip', cip])

    if cipheader:
        search_filter.append(['cipheader', cipheader])

    if sitepersistence:
        search_filter.append(['sitepersistence', sitepersistence])

    if cookietimeout:
        search_filter.append(['cookietimeout', cookietimeout])

    if siteprefix:
        search_filter.append(['siteprefix', siteprefix])

    if clttimeout:
        search_filter.append(['clttimeout', clttimeout])

    if svrtimeout:
        search_filter.append(['svrtimeout', svrtimeout])

    if maxbandwidth:
        search_filter.append(['maxbandwidth', maxbandwidth])

    if downstateflush:
        search_filter.append(['downstateflush', downstateflush])

    if maxaaausers:
        search_filter.append(['maxaaausers', maxaaausers])

    if monthreshold:
        search_filter.append(['monthreshold', monthreshold])

    if hashid:
        search_filter.append(['hashid', hashid])

    if comment:
        search_filter.append(['comment', comment])

    if appflowlog:
        search_filter.append(['appflowlog', appflowlog])

    if naptrreplacement:
        search_filter.append(['naptrreplacement', naptrreplacement])

    if naptrorder:
        search_filter.append(['naptrorder', naptrorder])

    if naptrservices:
        search_filter.append(['naptrservices', naptrservices])

    if naptrdomainttl:
        search_filter.append(['naptrdomainttl', naptrdomainttl])

    if naptrpreference:
        search_filter.append(['naptrpreference', naptrpreference])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if viewname:
        search_filter.append(['viewname', viewname])

    if viewip:
        search_filter.append(['viewip', viewip])

    if weight:
        search_filter.append(['weight', weight])

    if monitor_name_svc:
        search_filter.append(['monitor_name_svc', monitor_name_svc])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbservice{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbservice')

    return response


def get_gslbservice_binding():
    '''
    Show the running configuration for the gslbservice_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbservice_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbservice_binding'), 'gslbservice_binding')

    return response


def get_gslbservice_dnsview_binding(viewname=None, servicename=None, viewip=None):
    '''
    Show the running configuration for the gslbservice_dnsview_binding config key.

    viewname(str): Filters results that only match the viewname field.

    servicename(str): Filters results that only match the servicename field.

    viewip(str): Filters results that only match the viewip field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbservice_dnsview_binding

    '''

    search_filter = []

    if viewname:
        search_filter.append(['viewname', viewname])

    if servicename:
        search_filter.append(['servicename', servicename])

    if viewip:
        search_filter.append(['viewip', viewip])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbservice_dnsview_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbservice_dnsview_binding')

    return response


def get_gslbservice_lbmonitor_binding(servicename=None, weight=None, monitor_name=None, monstate=None):
    '''
    Show the running configuration for the gslbservice_lbmonitor_binding config key.

    servicename(str): Filters results that only match the servicename field.

    weight(int): Filters results that only match the weight field.

    monitor_name(str): Filters results that only match the monitor_name field.

    monstate(str): Filters results that only match the monstate field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbservice_lbmonitor_binding

    '''

    search_filter = []

    if servicename:
        search_filter.append(['servicename', servicename])

    if weight:
        search_filter.append(['weight', weight])

    if monitor_name:
        search_filter.append(['monitor_name', monitor_name])

    if monstate:
        search_filter.append(['monstate', monstate])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbservice_lbmonitor_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbservice_lbmonitor_binding')

    return response


def get_gslbsite(sitename=None, sitetype=None, siteipaddress=None, publicip=None, metricexchange=None,
                 nwmetricexchange=None, sessionexchange=None, triggermonitor=None, parentsite=None, clip=None,
                 publicclip=None, naptrreplacementsuffix=None, backupparentlist=None):
    '''
    Show the running configuration for the gslbsite config key.

    sitename(str): Filters results that only match the sitename field.

    sitetype(str): Filters results that only match the sitetype field.

    siteipaddress(str): Filters results that only match the siteipaddress field.

    publicip(str): Filters results that only match the publicip field.

    metricexchange(str): Filters results that only match the metricexchange field.

    nwmetricexchange(str): Filters results that only match the nwmetricexchange field.

    sessionexchange(str): Filters results that only match the sessionexchange field.

    triggermonitor(str): Filters results that only match the triggermonitor field.

    parentsite(str): Filters results that only match the parentsite field.

    clip(str): Filters results that only match the clip field.

    publicclip(str): Filters results that only match the publicclip field.

    naptrreplacementsuffix(str): Filters results that only match the naptrreplacementsuffix field.

    backupparentlist(list(str)): Filters results that only match the backupparentlist field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbsite

    '''

    search_filter = []

    if sitename:
        search_filter.append(['sitename', sitename])

    if sitetype:
        search_filter.append(['sitetype', sitetype])

    if siteipaddress:
        search_filter.append(['siteipaddress', siteipaddress])

    if publicip:
        search_filter.append(['publicip', publicip])

    if metricexchange:
        search_filter.append(['metricexchange', metricexchange])

    if nwmetricexchange:
        search_filter.append(['nwmetricexchange', nwmetricexchange])

    if sessionexchange:
        search_filter.append(['sessionexchange', sessionexchange])

    if triggermonitor:
        search_filter.append(['triggermonitor', triggermonitor])

    if parentsite:
        search_filter.append(['parentsite', parentsite])

    if clip:
        search_filter.append(['clip', clip])

    if publicclip:
        search_filter.append(['publicclip', publicclip])

    if naptrreplacementsuffix:
        search_filter.append(['naptrreplacementsuffix', naptrreplacementsuffix])

    if backupparentlist:
        search_filter.append(['backupparentlist', backupparentlist])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbsite{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbsite')

    return response


def get_gslbsite_binding():
    '''
    Show the running configuration for the gslbsite_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbsite_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbsite_binding'), 'gslbsite_binding')

    return response


def get_gslbsite_gslbservice_binding(servicename=None, sitename=None):
    '''
    Show the running configuration for the gslbsite_gslbservice_binding config key.

    servicename(str): Filters results that only match the servicename field.

    sitename(str): Filters results that only match the sitename field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbsite_gslbservice_binding

    '''

    search_filter = []

    if servicename:
        search_filter.append(['servicename', servicename])

    if sitename:
        search_filter.append(['sitename', sitename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbsite_gslbservice_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbsite_gslbservice_binding')

    return response


def get_gslbsyncstatus():
    '''
    Show the running configuration for the gslbsyncstatus config key.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbsyncstatus

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbsyncstatus'), 'gslbsyncstatus')

    return response


def get_gslbvserver(name=None, servicetype=None, iptype=None, dnsrecordtype=None, lbmethod=None,
                    backupsessiontimeout=None, backuplbmethod=None, netmask=None, v6netmasklen=None, tolerance=None,
                    persistencetype=None, persistenceid=None, persistmask=None, v6persistmasklen=None, timeout=None,
                    edr=None, ecs=None, ecsaddrvalidation=None, mir=None, disableprimaryondown=None, dynamicweight=None,
                    state=None, considereffectivestate=None, comment=None, somethod=None, sopersistence=None,
                    sopersistencetimeout=None, sothreshold=None, sobackupaction=None, appflowlog=None,
                    backupvserver=None, servicename=None, weight=None, domainname=None, ttl=None, backupip=None,
                    cookie_domain=None, cookietimeout=None, sitedomainttl=None, newname=None):
    '''
    Show the running configuration for the gslbvserver config key.

    name(str): Filters results that only match the name field.

    servicetype(str): Filters results that only match the servicetype field.

    iptype(str): Filters results that only match the iptype field.

    dnsrecordtype(str): Filters results that only match the dnsrecordtype field.

    lbmethod(str): Filters results that only match the lbmethod field.

    backupsessiontimeout(int): Filters results that only match the backupsessiontimeout field.

    backuplbmethod(str): Filters results that only match the backuplbmethod field.

    netmask(str): Filters results that only match the netmask field.

    v6netmasklen(int): Filters results that only match the v6netmasklen field.

    tolerance(int): Filters results that only match the tolerance field.

    persistencetype(str): Filters results that only match the persistencetype field.

    persistenceid(int): Filters results that only match the persistenceid field.

    persistmask(str): Filters results that only match the persistmask field.

    v6persistmasklen(int): Filters results that only match the v6persistmasklen field.

    timeout(int): Filters results that only match the timeout field.

    edr(str): Filters results that only match the edr field.

    ecs(str): Filters results that only match the ecs field.

    ecsaddrvalidation(str): Filters results that only match the ecsaddrvalidation field.

    mir(str): Filters results that only match the mir field.

    disableprimaryondown(str): Filters results that only match the disableprimaryondown field.

    dynamicweight(str): Filters results that only match the dynamicweight field.

    state(str): Filters results that only match the state field.

    considereffectivestate(str): Filters results that only match the considereffectivestate field.

    comment(str): Filters results that only match the comment field.

    somethod(str): Filters results that only match the somethod field.

    sopersistence(str): Filters results that only match the sopersistence field.

    sopersistencetimeout(int): Filters results that only match the sopersistencetimeout field.

    sothreshold(int): Filters results that only match the sothreshold field.

    sobackupaction(str): Filters results that only match the sobackupaction field.

    appflowlog(str): Filters results that only match the appflowlog field.

    backupvserver(str): Filters results that only match the backupvserver field.

    servicename(str): Filters results that only match the servicename field.

    weight(int): Filters results that only match the weight field.

    domainname(str): Filters results that only match the domainname field.

    ttl(int): Filters results that only match the ttl field.

    backupip(str): Filters results that only match the backupip field.

    cookie_domain(str): Filters results that only match the cookie_domain field.

    cookietimeout(int): Filters results that only match the cookietimeout field.

    sitedomainttl(int): Filters results that only match the sitedomainttl field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbvserver

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if servicetype:
        search_filter.append(['servicetype', servicetype])

    if iptype:
        search_filter.append(['iptype', iptype])

    if dnsrecordtype:
        search_filter.append(['dnsrecordtype', dnsrecordtype])

    if lbmethod:
        search_filter.append(['lbmethod', lbmethod])

    if backupsessiontimeout:
        search_filter.append(['backupsessiontimeout', backupsessiontimeout])

    if backuplbmethod:
        search_filter.append(['backuplbmethod', backuplbmethod])

    if netmask:
        search_filter.append(['netmask', netmask])

    if v6netmasklen:
        search_filter.append(['v6netmasklen', v6netmasklen])

    if tolerance:
        search_filter.append(['tolerance', tolerance])

    if persistencetype:
        search_filter.append(['persistencetype', persistencetype])

    if persistenceid:
        search_filter.append(['persistenceid', persistenceid])

    if persistmask:
        search_filter.append(['persistmask', persistmask])

    if v6persistmasklen:
        search_filter.append(['v6persistmasklen', v6persistmasklen])

    if timeout:
        search_filter.append(['timeout', timeout])

    if edr:
        search_filter.append(['edr', edr])

    if ecs:
        search_filter.append(['ecs', ecs])

    if ecsaddrvalidation:
        search_filter.append(['ecsaddrvalidation', ecsaddrvalidation])

    if mir:
        search_filter.append(['mir', mir])

    if disableprimaryondown:
        search_filter.append(['disableprimaryondown', disableprimaryondown])

    if dynamicweight:
        search_filter.append(['dynamicweight', dynamicweight])

    if state:
        search_filter.append(['state', state])

    if considereffectivestate:
        search_filter.append(['considereffectivestate', considereffectivestate])

    if comment:
        search_filter.append(['comment', comment])

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

    if appflowlog:
        search_filter.append(['appflowlog', appflowlog])

    if backupvserver:
        search_filter.append(['backupvserver', backupvserver])

    if servicename:
        search_filter.append(['servicename', servicename])

    if weight:
        search_filter.append(['weight', weight])

    if domainname:
        search_filter.append(['domainname', domainname])

    if ttl:
        search_filter.append(['ttl', ttl])

    if backupip:
        search_filter.append(['backupip', backupip])

    if cookie_domain:
        search_filter.append(['cookie_domain', cookie_domain])

    if cookietimeout:
        search_filter.append(['cookietimeout', cookietimeout])

    if sitedomainttl:
        search_filter.append(['sitedomainttl', sitedomainttl])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbvserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbvserver')

    return response


def get_gslbvserver_binding():
    '''
    Show the running configuration for the gslbvserver_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbvserver_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbvserver_binding'), 'gslbvserver_binding')

    return response


def get_gslbvserver_domain_binding(backupipflag=None, cookietimeout=None, backupip=None, name=None, ttl=None,
                                   domainname=None, sitedomainttl=None, cookie_domainflag=None, cookie_domain=None):
    '''
    Show the running configuration for the gslbvserver_domain_binding config key.

    backupipflag(bool): Filters results that only match the backupipflag field.

    cookietimeout(int): Filters results that only match the cookietimeout field.

    backupip(str): Filters results that only match the backupip field.

    name(str): Filters results that only match the name field.

    ttl(int): Filters results that only match the ttl field.

    domainname(str): Filters results that only match the domainname field.

    sitedomainttl(int): Filters results that only match the sitedomainttl field.

    cookie_domainflag(bool): Filters results that only match the cookie_domainflag field.

    cookie_domain(str): Filters results that only match the cookie_domain field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbvserver_domain_binding

    '''

    search_filter = []

    if backupipflag:
        search_filter.append(['backupipflag', backupipflag])

    if cookietimeout:
        search_filter.append(['cookietimeout', cookietimeout])

    if backupip:
        search_filter.append(['backupip', backupip])

    if name:
        search_filter.append(['name', name])

    if ttl:
        search_filter.append(['ttl', ttl])

    if domainname:
        search_filter.append(['domainname', domainname])

    if sitedomainttl:
        search_filter.append(['sitedomainttl', sitedomainttl])

    if cookie_domainflag:
        search_filter.append(['cookie_domainflag', cookie_domainflag])

    if cookie_domain:
        search_filter.append(['cookie_domain', cookie_domain])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbvserver_domain_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbvserver_domain_binding')

    return response


def get_gslbvserver_gslbservice_binding(weight=None, name=None, servicename=None, domainname=None):
    '''
    Show the running configuration for the gslbvserver_gslbservice_binding config key.

    weight(int): Filters results that only match the weight field.

    name(str): Filters results that only match the name field.

    servicename(str): Filters results that only match the servicename field.

    domainname(str): Filters results that only match the domainname field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbvserver_gslbservice_binding

    '''

    search_filter = []

    if weight:
        search_filter.append(['weight', weight])

    if name:
        search_filter.append(['name', name])

    if servicename:
        search_filter.append(['servicename', servicename])

    if domainname:
        search_filter.append(['domainname', domainname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbvserver_gslbservice_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbvserver_gslbservice_binding')

    return response


def get_gslbvserver_spilloverpolicy_binding(priority=None, gotopriorityexpression=None, policyname=None, name=None,
                                            ns_type=None):
    '''
    Show the running configuration for the gslbvserver_spilloverpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policyname(str): Filters results that only match the policyname field.

    name(str): Filters results that only match the name field.

    ns_type(str): Filters results that only match the type field.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.get_gslbvserver_spilloverpolicy_binding

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

    if ns_type:
        search_filter.append(['type', ns_type])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/gslbvserver_spilloverpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'gslbvserver_spilloverpolicy_binding')

    return response


def unset_gslbparameter(ldnsentrytimeout=None, rtttolerance=None, ldnsmask=None, v6ldnsmasklen=None, ldnsprobeorder=None,
                        dropldnsreq=None, gslbsvcstatedelaytime=None, automaticconfigsync=None, save=False):
    '''
    Unsets values from the gslbparameter configuration key.

    ldnsentrytimeout(bool): Unsets the ldnsentrytimeout value.

    rtttolerance(bool): Unsets the rtttolerance value.

    ldnsmask(bool): Unsets the ldnsmask value.

    v6ldnsmasklen(bool): Unsets the v6ldnsmasklen value.

    ldnsprobeorder(bool): Unsets the ldnsprobeorder value.

    dropldnsreq(bool): Unsets the dropldnsreq value.

    gslbsvcstatedelaytime(bool): Unsets the gslbsvcstatedelaytime value.

    automaticconfigsync(bool): Unsets the automaticconfigsync value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.unset_gslbparameter <args>

    '''

    result = {}

    payload = {'gslbparameter': {}}

    if ldnsentrytimeout:
        payload['gslbparameter']['ldnsentrytimeout'] = True

    if rtttolerance:
        payload['gslbparameter']['rtttolerance'] = True

    if ldnsmask:
        payload['gslbparameter']['ldnsmask'] = True

    if v6ldnsmasklen:
        payload['gslbparameter']['v6ldnsmasklen'] = True

    if ldnsprobeorder:
        payload['gslbparameter']['ldnsprobeorder'] = True

    if dropldnsreq:
        payload['gslbparameter']['dropldnsreq'] = True

    if gslbsvcstatedelaytime:
        payload['gslbparameter']['gslbsvcstatedelaytime'] = True

    if automaticconfigsync:
        payload['gslbparameter']['automaticconfigsync'] = True

    execution = __proxy__['citrixns.post']('config/gslbparameter?action=unset', payload)

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


def unset_gslbservice(servicename=None, cnameentry=None, ip=None, servername=None, servicetype=None, port=None,
                      publicip=None, publicport=None, maxclient=None, healthmonitor=None, sitename=None, state=None,
                      cip=None, cipheader=None, sitepersistence=None, cookietimeout=None, siteprefix=None,
                      clttimeout=None, svrtimeout=None, maxbandwidth=None, downstateflush=None, maxaaausers=None,
                      monthreshold=None, hashid=None, comment=None, appflowlog=None, naptrreplacement=None,
                      naptrorder=None, naptrservices=None, naptrdomainttl=None, naptrpreference=None, ipaddress=None,
                      viewname=None, viewip=None, weight=None, monitor_name_svc=None, newname=None, save=False):
    '''
    Unsets values from the gslbservice configuration key.

    servicename(bool): Unsets the servicename value.

    cnameentry(bool): Unsets the cnameentry value.

    ip(bool): Unsets the ip value.

    servername(bool): Unsets the servername value.

    servicetype(bool): Unsets the servicetype value.

    port(bool): Unsets the port value.

    publicip(bool): Unsets the publicip value.

    publicport(bool): Unsets the publicport value.

    maxclient(bool): Unsets the maxclient value.

    healthmonitor(bool): Unsets the healthmonitor value.

    sitename(bool): Unsets the sitename value.

    state(bool): Unsets the state value.

    cip(bool): Unsets the cip value.

    cipheader(bool): Unsets the cipheader value.

    sitepersistence(bool): Unsets the sitepersistence value.

    cookietimeout(bool): Unsets the cookietimeout value.

    siteprefix(bool): Unsets the siteprefix value.

    clttimeout(bool): Unsets the clttimeout value.

    svrtimeout(bool): Unsets the svrtimeout value.

    maxbandwidth(bool): Unsets the maxbandwidth value.

    downstateflush(bool): Unsets the downstateflush value.

    maxaaausers(bool): Unsets the maxaaausers value.

    monthreshold(bool): Unsets the monthreshold value.

    hashid(bool): Unsets the hashid value.

    comment(bool): Unsets the comment value.

    appflowlog(bool): Unsets the appflowlog value.

    naptrreplacement(bool): Unsets the naptrreplacement value.

    naptrorder(bool): Unsets the naptrorder value.

    naptrservices(bool): Unsets the naptrservices value.

    naptrdomainttl(bool): Unsets the naptrdomainttl value.

    naptrpreference(bool): Unsets the naptrpreference value.

    ipaddress(bool): Unsets the ipaddress value.

    viewname(bool): Unsets the viewname value.

    viewip(bool): Unsets the viewip value.

    weight(bool): Unsets the weight value.

    monitor_name_svc(bool): Unsets the monitor_name_svc value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.unset_gslbservice <args>

    '''

    result = {}

    payload = {'gslbservice': {}}

    if servicename:
        payload['gslbservice']['servicename'] = True

    if cnameentry:
        payload['gslbservice']['cnameentry'] = True

    if ip:
        payload['gslbservice']['ip'] = True

    if servername:
        payload['gslbservice']['servername'] = True

    if servicetype:
        payload['gslbservice']['servicetype'] = True

    if port:
        payload['gslbservice']['port'] = True

    if publicip:
        payload['gslbservice']['publicip'] = True

    if publicport:
        payload['gslbservice']['publicport'] = True

    if maxclient:
        payload['gslbservice']['maxclient'] = True

    if healthmonitor:
        payload['gslbservice']['healthmonitor'] = True

    if sitename:
        payload['gslbservice']['sitename'] = True

    if state:
        payload['gslbservice']['state'] = True

    if cip:
        payload['gslbservice']['cip'] = True

    if cipheader:
        payload['gslbservice']['cipheader'] = True

    if sitepersistence:
        payload['gslbservice']['sitepersistence'] = True

    if cookietimeout:
        payload['gslbservice']['cookietimeout'] = True

    if siteprefix:
        payload['gslbservice']['siteprefix'] = True

    if clttimeout:
        payload['gslbservice']['clttimeout'] = True

    if svrtimeout:
        payload['gslbservice']['svrtimeout'] = True

    if maxbandwidth:
        payload['gslbservice']['maxbandwidth'] = True

    if downstateflush:
        payload['gslbservice']['downstateflush'] = True

    if maxaaausers:
        payload['gslbservice']['maxaaausers'] = True

    if monthreshold:
        payload['gslbservice']['monthreshold'] = True

    if hashid:
        payload['gslbservice']['hashid'] = True

    if comment:
        payload['gslbservice']['comment'] = True

    if appflowlog:
        payload['gslbservice']['appflowlog'] = True

    if naptrreplacement:
        payload['gslbservice']['naptrreplacement'] = True

    if naptrorder:
        payload['gslbservice']['naptrorder'] = True

    if naptrservices:
        payload['gslbservice']['naptrservices'] = True

    if naptrdomainttl:
        payload['gslbservice']['naptrdomainttl'] = True

    if naptrpreference:
        payload['gslbservice']['naptrpreference'] = True

    if ipaddress:
        payload['gslbservice']['ipaddress'] = True

    if viewname:
        payload['gslbservice']['viewname'] = True

    if viewip:
        payload['gslbservice']['viewip'] = True

    if weight:
        payload['gslbservice']['weight'] = True

    if monitor_name_svc:
        payload['gslbservice']['monitor_name_svc'] = True

    if newname:
        payload['gslbservice']['newname'] = True

    execution = __proxy__['citrixns.post']('config/gslbservice?action=unset', payload)

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


def unset_gslbsite(sitename=None, sitetype=None, siteipaddress=None, publicip=None, metricexchange=None,
                   nwmetricexchange=None, sessionexchange=None, triggermonitor=None, parentsite=None, clip=None,
                   publicclip=None, naptrreplacementsuffix=None, backupparentlist=None, save=False):
    '''
    Unsets values from the gslbsite configuration key.

    sitename(bool): Unsets the sitename value.

    sitetype(bool): Unsets the sitetype value.

    siteipaddress(bool): Unsets the siteipaddress value.

    publicip(bool): Unsets the publicip value.

    metricexchange(bool): Unsets the metricexchange value.

    nwmetricexchange(bool): Unsets the nwmetricexchange value.

    sessionexchange(bool): Unsets the sessionexchange value.

    triggermonitor(bool): Unsets the triggermonitor value.

    parentsite(bool): Unsets the parentsite value.

    clip(bool): Unsets the clip value.

    publicclip(bool): Unsets the publicclip value.

    naptrreplacementsuffix(bool): Unsets the naptrreplacementsuffix value.

    backupparentlist(bool): Unsets the backupparentlist value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.unset_gslbsite <args>

    '''

    result = {}

    payload = {'gslbsite': {}}

    if sitename:
        payload['gslbsite']['sitename'] = True

    if sitetype:
        payload['gslbsite']['sitetype'] = True

    if siteipaddress:
        payload['gslbsite']['siteipaddress'] = True

    if publicip:
        payload['gslbsite']['publicip'] = True

    if metricexchange:
        payload['gslbsite']['metricexchange'] = True

    if nwmetricexchange:
        payload['gslbsite']['nwmetricexchange'] = True

    if sessionexchange:
        payload['gslbsite']['sessionexchange'] = True

    if triggermonitor:
        payload['gslbsite']['triggermonitor'] = True

    if parentsite:
        payload['gslbsite']['parentsite'] = True

    if clip:
        payload['gslbsite']['clip'] = True

    if publicclip:
        payload['gslbsite']['publicclip'] = True

    if naptrreplacementsuffix:
        payload['gslbsite']['naptrreplacementsuffix'] = True

    if backupparentlist:
        payload['gslbsite']['backupparentlist'] = True

    execution = __proxy__['citrixns.post']('config/gslbsite?action=unset', payload)

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


def unset_gslbvserver(name=None, servicetype=None, iptype=None, dnsrecordtype=None, lbmethod=None,
                      backupsessiontimeout=None, backuplbmethod=None, netmask=None, v6netmasklen=None, tolerance=None,
                      persistencetype=None, persistenceid=None, persistmask=None, v6persistmasklen=None, timeout=None,
                      edr=None, ecs=None, ecsaddrvalidation=None, mir=None, disableprimaryondown=None,
                      dynamicweight=None, state=None, considereffectivestate=None, comment=None, somethod=None,
                      sopersistence=None, sopersistencetimeout=None, sothreshold=None, sobackupaction=None,
                      appflowlog=None, backupvserver=None, servicename=None, weight=None, domainname=None, ttl=None,
                      backupip=None, cookie_domain=None, cookietimeout=None, sitedomainttl=None, newname=None,
                      save=False):
    '''
    Unsets values from the gslbvserver configuration key.

    name(bool): Unsets the name value.

    servicetype(bool): Unsets the servicetype value.

    iptype(bool): Unsets the iptype value.

    dnsrecordtype(bool): Unsets the dnsrecordtype value.

    lbmethod(bool): Unsets the lbmethod value.

    backupsessiontimeout(bool): Unsets the backupsessiontimeout value.

    backuplbmethod(bool): Unsets the backuplbmethod value.

    netmask(bool): Unsets the netmask value.

    v6netmasklen(bool): Unsets the v6netmasklen value.

    tolerance(bool): Unsets the tolerance value.

    persistencetype(bool): Unsets the persistencetype value.

    persistenceid(bool): Unsets the persistenceid value.

    persistmask(bool): Unsets the persistmask value.

    v6persistmasklen(bool): Unsets the v6persistmasklen value.

    timeout(bool): Unsets the timeout value.

    edr(bool): Unsets the edr value.

    ecs(bool): Unsets the ecs value.

    ecsaddrvalidation(bool): Unsets the ecsaddrvalidation value.

    mir(bool): Unsets the mir value.

    disableprimaryondown(bool): Unsets the disableprimaryondown value.

    dynamicweight(bool): Unsets the dynamicweight value.

    state(bool): Unsets the state value.

    considereffectivestate(bool): Unsets the considereffectivestate value.

    comment(bool): Unsets the comment value.

    somethod(bool): Unsets the somethod value.

    sopersistence(bool): Unsets the sopersistence value.

    sopersistencetimeout(bool): Unsets the sopersistencetimeout value.

    sothreshold(bool): Unsets the sothreshold value.

    sobackupaction(bool): Unsets the sobackupaction value.

    appflowlog(bool): Unsets the appflowlog value.

    backupvserver(bool): Unsets the backupvserver value.

    servicename(bool): Unsets the servicename value.

    weight(bool): Unsets the weight value.

    domainname(bool): Unsets the domainname value.

    ttl(bool): Unsets the ttl value.

    backupip(bool): Unsets the backupip value.

    cookie_domain(bool): Unsets the cookie_domain value.

    cookietimeout(bool): Unsets the cookietimeout value.

    sitedomainttl(bool): Unsets the sitedomainttl value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.unset_gslbvserver <args>

    '''

    result = {}

    payload = {'gslbvserver': {}}

    if name:
        payload['gslbvserver']['name'] = True

    if servicetype:
        payload['gslbvserver']['servicetype'] = True

    if iptype:
        payload['gslbvserver']['iptype'] = True

    if dnsrecordtype:
        payload['gslbvserver']['dnsrecordtype'] = True

    if lbmethod:
        payload['gslbvserver']['lbmethod'] = True

    if backupsessiontimeout:
        payload['gslbvserver']['backupsessiontimeout'] = True

    if backuplbmethod:
        payload['gslbvserver']['backuplbmethod'] = True

    if netmask:
        payload['gslbvserver']['netmask'] = True

    if v6netmasklen:
        payload['gslbvserver']['v6netmasklen'] = True

    if tolerance:
        payload['gslbvserver']['tolerance'] = True

    if persistencetype:
        payload['gslbvserver']['persistencetype'] = True

    if persistenceid:
        payload['gslbvserver']['persistenceid'] = True

    if persistmask:
        payload['gslbvserver']['persistmask'] = True

    if v6persistmasklen:
        payload['gslbvserver']['v6persistmasklen'] = True

    if timeout:
        payload['gslbvserver']['timeout'] = True

    if edr:
        payload['gslbvserver']['edr'] = True

    if ecs:
        payload['gslbvserver']['ecs'] = True

    if ecsaddrvalidation:
        payload['gslbvserver']['ecsaddrvalidation'] = True

    if mir:
        payload['gslbvserver']['mir'] = True

    if disableprimaryondown:
        payload['gslbvserver']['disableprimaryondown'] = True

    if dynamicweight:
        payload['gslbvserver']['dynamicweight'] = True

    if state:
        payload['gslbvserver']['state'] = True

    if considereffectivestate:
        payload['gslbvserver']['considereffectivestate'] = True

    if comment:
        payload['gslbvserver']['comment'] = True

    if somethod:
        payload['gslbvserver']['somethod'] = True

    if sopersistence:
        payload['gslbvserver']['sopersistence'] = True

    if sopersistencetimeout:
        payload['gslbvserver']['sopersistencetimeout'] = True

    if sothreshold:
        payload['gslbvserver']['sothreshold'] = True

    if sobackupaction:
        payload['gslbvserver']['sobackupaction'] = True

    if appflowlog:
        payload['gslbvserver']['appflowlog'] = True

    if backupvserver:
        payload['gslbvserver']['backupvserver'] = True

    if servicename:
        payload['gslbvserver']['servicename'] = True

    if weight:
        payload['gslbvserver']['weight'] = True

    if domainname:
        payload['gslbvserver']['domainname'] = True

    if ttl:
        payload['gslbvserver']['ttl'] = True

    if backupip:
        payload['gslbvserver']['backupip'] = True

    if cookie_domain:
        payload['gslbvserver']['cookie_domain'] = True

    if cookietimeout:
        payload['gslbvserver']['cookietimeout'] = True

    if sitedomainttl:
        payload['gslbvserver']['sitedomainttl'] = True

    if newname:
        payload['gslbvserver']['newname'] = True

    execution = __proxy__['citrixns.post']('config/gslbvserver?action=unset', payload)

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


def update_gslbparameter(ldnsentrytimeout=None, rtttolerance=None, ldnsmask=None, v6ldnsmasklen=None,
                         ldnsprobeorder=None, dropldnsreq=None, gslbsvcstatedelaytime=None, automaticconfigsync=None,
                         save=False):
    '''
    Update the running configuration for the gslbparameter config key.

    ldnsentrytimeout(int): Time, in seconds, after which an inactive LDNS entry is removed. Default value: 180 Minimum value
        = 30 Maximum value = 65534

    rtttolerance(int): Tolerance, in milliseconds, for newly learned round-trip time (RTT) values. If the difference between
        the old RTT value and the newly computed RTT value is less than or equal to the specified tolerance value, the
        LDNS entry in the network metric table is not updated with the new RTT value. Prevents the exchange of metrics
        when variations in RTT values are negligible. Default value: 5 Minimum value = 1 Maximum value = 100

    ldnsmask(str): The IPv4 network mask with which to create LDNS entries. Minimum length = 1

    v6ldnsmasklen(int): Mask for creating LDNS entries for IPv6 source addresses. The mask is defined as the number of
        leading bits to consider, in the source IP address, when creating an LDNS entry. Default value: 128 Minimum value
        = 1 Maximum value = 128

    ldnsprobeorder(list(str)): Order in which monitors should be initiated to calculate RTT. Possible values = PING, DNS,
        TCP

    dropldnsreq(str): Drop LDNS requests if round-trip time (RTT) information is not available. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    gslbsvcstatedelaytime(int): Amount of delay in updating the state of GSLB service to DOWN when MEP goes down.  This
        parameter is applicable only if monitors are not bound to GSLB services. Default value: 0 Minimum value = 0
        Maximum value = 3600

    automaticconfigsync(str): GSLB configuration will be synced automatically to remote gslb sites if enabled. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.update_gslbparameter <args>

    '''

    result = {}

    payload = {'gslbparameter': {}}

    if ldnsentrytimeout:
        payload['gslbparameter']['ldnsentrytimeout'] = ldnsentrytimeout

    if rtttolerance:
        payload['gslbparameter']['rtttolerance'] = rtttolerance

    if ldnsmask:
        payload['gslbparameter']['ldnsmask'] = ldnsmask

    if v6ldnsmasklen:
        payload['gslbparameter']['v6ldnsmasklen'] = v6ldnsmasklen

    if ldnsprobeorder:
        payload['gslbparameter']['ldnsprobeorder'] = ldnsprobeorder

    if dropldnsreq:
        payload['gslbparameter']['dropldnsreq'] = dropldnsreq

    if gslbsvcstatedelaytime:
        payload['gslbparameter']['gslbsvcstatedelaytime'] = gslbsvcstatedelaytime

    if automaticconfigsync:
        payload['gslbparameter']['automaticconfigsync'] = automaticconfigsync

    execution = __proxy__['citrixns.put']('config/gslbparameter', payload)

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


def update_gslbservice(servicename=None, cnameentry=None, ip=None, servername=None, servicetype=None, port=None,
                       publicip=None, publicport=None, maxclient=None, healthmonitor=None, sitename=None, state=None,
                       cip=None, cipheader=None, sitepersistence=None, cookietimeout=None, siteprefix=None,
                       clttimeout=None, svrtimeout=None, maxbandwidth=None, downstateflush=None, maxaaausers=None,
                       monthreshold=None, hashid=None, comment=None, appflowlog=None, naptrreplacement=None,
                       naptrorder=None, naptrservices=None, naptrdomainttl=None, naptrpreference=None, ipaddress=None,
                       viewname=None, viewip=None, weight=None, monitor_name_svc=None, newname=None, save=False):
    '''
    Update the running configuration for the gslbservice config key.

    servicename(str): Name for the GSLB service. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the GSLB service is created.  CLI Users: If the name includes one or
        more spaces, enclose the name in double or single quotation marks (for example, "my gslbsvc" or my gslbsvc).
        Minimum length = 1

    cnameentry(str): Canonical name of the GSLB service. Used in CNAME-based GSLB. Minimum length = 1

    ip(str): IP address for the GSLB service. Should represent a load balancing, content switching, or VPN virtual server on
        the NetScaler appliance, or the IP address of another load balancing device. Minimum length = 1

    servername(str): Name of the server hosting the GSLB service. Minimum length = 1

    servicetype(str): Type of service to create. Default value: NSSVC_SERVICE_UNKNOWN Possible values = HTTP, FTP, TCP, UDP,
        SSL, SSL_BRIDGE, SSL_TCP, NNTP, ANY, SIP_UDP, SIP_TCP, SIP_SSL, RADIUS, RDP, RTSP, MYSQL, MSSQL, ORACLE

    port(int): Port on which the load balancing entity represented by this GSLB service listens. Minimum value = 1 Range 1 -
        65535 * in CLI is represented as 65535 in NITRO API

    publicip(str): The public IP address that a NAT device translates to the GSLB services private IP address. Optional.

    publicport(int): The public port associated with the GSLB services public IP address. The port is mapped to the services
        private port number. Applicable to the local GSLB service. Optional.

    maxclient(int): The maximum number of open connections that the service can support at any given time. A GSLB service
        whose connection count reaches the maximum is not considered when a GSLB decision is made, until the connection
        count drops below the maximum. Minimum value = 0 Maximum value = 4294967294

    healthmonitor(str): Monitor the health of the GSLB service. Default value: YES Possible values = YES, NO

    sitename(str): Name of the GSLB site to which the service belongs. Minimum length = 1

    state(str): Enable or disable the service. Default value: ENABLED Possible values = ENABLED, DISABLED

    cip(str): In the request that is forwarded to the GSLB service, insert a header that stores the clients IP address.
        Client IP header insertion is used in connection-proxy based site persistence. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    cipheader(str): Name for the HTTP header that stores the clients IP address. Used with the Client IP option. If client IP
        header insertion is enabled on the service and a name is not specified for the header, the NetScaler appliance
        uses the name specified by the cipHeader parameter in the set ns param command or, in the GUI, the Client IP
        Header parameter in the Configure HTTP Parameters dialog box. Minimum length = 1

    sitepersistence(str): Use cookie-based site persistence. Applicable only to HTTP and SSL GSLB services. Possible values =
        ConnectionProxy, HTTPRedirect, NONE

    cookietimeout(int): Timeout value, in minutes, for the cookie, when cookie based site persistence is enabled. Minimum
        value = 0 Maximum value = 1440

    siteprefix(str): The sites prefix string. When the service is bound to a GSLB virtual server, a GSLB site domain is
        generated internally for each bound service-domain pair by concatenating the site prefix of the service and the
        name of the domain. If the special string NONE is specified, the site-prefix string is unset. When implementing
        HTTP redirect site persistence, the NetScaler appliance redirects GSLB requests to GSLB services by using their
        site domains.

    clttimeout(int): Idle time, in seconds, after which a client connection is terminated. Applicable if connection proxy
        based site persistence is used. Minimum value = 0 Maximum value = 31536000

    svrtimeout(int): Idle time, in seconds, after which a server connection is terminated. Applicable if connection proxy
        based site persistence is used. Minimum value = 0 Maximum value = 31536000

    maxbandwidth(int): Integer specifying the maximum bandwidth allowed for the service. A GSLB service whose bandwidth
        reaches the maximum is not considered when a GSLB decision is made, until its bandwidth consumption drops below
        the maximum.

    downstateflush(str): Flush all active transactions associated with the GSLB service when its state transitions from UP to
        DOWN. Do not enable this option for services that must complete their transactions. Applicable if connection
        proxy based site persistence is used. Possible values = ENABLED, DISABLED

    maxaaausers(int): Maximum number of SSL VPN users that can be logged on concurrently to the VPN virtual server that is
        represented by this GSLB service. A GSLB service whose user count reaches the maximum is not considered when a
        GSLB decision is made, until the count drops below the maximum. Minimum value = 0 Maximum value = 65535

    monthreshold(int): Monitoring threshold value for the GSLB service. If the sum of the weights of the monitors that are
        bound to this GSLB service and are in the UP state is not equal to or greater than this threshold value, the
        service is marked as DOWN. Minimum value = 0 Maximum value = 65535

    hashid(int): Unique hash identifier for the GSLB service, used by hash based load balancing methods. Minimum value = 1

    comment(str): Any comments that you might want to associate with the GSLB service.

    appflowlog(str): Enable logging appflow flow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    naptrreplacement(str): The replacement domain name for this NAPTR. Maximum length = 255

    naptrorder(int): An integer specifying the order in which the NAPTR records MUST be processed in order to accurately
        represent the ordered list of Rules. The ordering is from lowest to highest. Default value: 1 Minimum value = 1
        Maximum value = 65535

    naptrservices(str): Service Parameters applicable to this delegation path. Maximum length = 255

    naptrdomainttl(int): Modify the TTL of the internally created naptr domain. Default value: 3600 Minimum value = 1

    naptrpreference(int): An integer specifying the preference of this NAPTR among NAPTR records having same order. lower the
        number, higher the preference. Default value: 1 Minimum value = 1 Maximum value = 65535

    ipaddress(str): The new IP address of the service.

    viewname(str): Name of the DNS view of the service. A DNS view is used in global server load balancing (GSLB) to return a
        predetermined IP address to a specific group of clients, which are identified by using a DNS policy. Minimum
        length = 1

    viewip(str): IP address to be used for the given view.

    weight(int): Weight to assign to the monitor-service binding. A larger number specifies a greater weight. Contributes to
        the monitoring threshold, which determines the state of the service. Minimum value = 1 Maximum value = 100

    monitor_name_svc(str): Name of the monitor to bind to the service. Minimum length = 1

    newname(str): New name for the GSLB service. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.update_gslbservice <args>

    '''

    result = {}

    payload = {'gslbservice': {}}

    if servicename:
        payload['gslbservice']['servicename'] = servicename

    if cnameentry:
        payload['gslbservice']['cnameentry'] = cnameentry

    if ip:
        payload['gslbservice']['ip'] = ip

    if servername:
        payload['gslbservice']['servername'] = servername

    if servicetype:
        payload['gslbservice']['servicetype'] = servicetype

    if port:
        payload['gslbservice']['port'] = port

    if publicip:
        payload['gslbservice']['publicip'] = publicip

    if publicport:
        payload['gslbservice']['publicport'] = publicport

    if maxclient:
        payload['gslbservice']['maxclient'] = maxclient

    if healthmonitor:
        payload['gslbservice']['healthmonitor'] = healthmonitor

    if sitename:
        payload['gslbservice']['sitename'] = sitename

    if state:
        payload['gslbservice']['state'] = state

    if cip:
        payload['gslbservice']['cip'] = cip

    if cipheader:
        payload['gslbservice']['cipheader'] = cipheader

    if sitepersistence:
        payload['gslbservice']['sitepersistence'] = sitepersistence

    if cookietimeout:
        payload['gslbservice']['cookietimeout'] = cookietimeout

    if siteprefix:
        payload['gslbservice']['siteprefix'] = siteprefix

    if clttimeout:
        payload['gslbservice']['clttimeout'] = clttimeout

    if svrtimeout:
        payload['gslbservice']['svrtimeout'] = svrtimeout

    if maxbandwidth:
        payload['gslbservice']['maxbandwidth'] = maxbandwidth

    if downstateflush:
        payload['gslbservice']['downstateflush'] = downstateflush

    if maxaaausers:
        payload['gslbservice']['maxaaausers'] = maxaaausers

    if monthreshold:
        payload['gslbservice']['monthreshold'] = monthreshold

    if hashid:
        payload['gslbservice']['hashid'] = hashid

    if comment:
        payload['gslbservice']['comment'] = comment

    if appflowlog:
        payload['gslbservice']['appflowlog'] = appflowlog

    if naptrreplacement:
        payload['gslbservice']['naptrreplacement'] = naptrreplacement

    if naptrorder:
        payload['gslbservice']['naptrorder'] = naptrorder

    if naptrservices:
        payload['gslbservice']['naptrservices'] = naptrservices

    if naptrdomainttl:
        payload['gslbservice']['naptrdomainttl'] = naptrdomainttl

    if naptrpreference:
        payload['gslbservice']['naptrpreference'] = naptrpreference

    if ipaddress:
        payload['gslbservice']['ipaddress'] = ipaddress

    if viewname:
        payload['gslbservice']['viewname'] = viewname

    if viewip:
        payload['gslbservice']['viewip'] = viewip

    if weight:
        payload['gslbservice']['weight'] = weight

    if monitor_name_svc:
        payload['gslbservice']['monitor_name_svc'] = monitor_name_svc

    if newname:
        payload['gslbservice']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/gslbservice', payload)

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


def update_gslbsite(sitename=None, sitetype=None, siteipaddress=None, publicip=None, metricexchange=None,
                    nwmetricexchange=None, sessionexchange=None, triggermonitor=None, parentsite=None, clip=None,
                    publicclip=None, naptrreplacementsuffix=None, backupparentlist=None, save=False):
    '''
    Update the running configuration for the gslbsite config key.

    sitename(str): Name for the GSLB site. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the virtual server is created.  CLI Users: If the name includes
        one or more spaces, enclose the name in double or single quotation marks (for example, "my gslbsite" or my
        gslbsite). Minimum length = 1

    sitetype(str): Type of site to create. If the type is not specified, the appliance automatically detects and sets the
        type on the basis of the IP address being assigned to the site. If the specified site IP address is owned by the
        appliance (for example, a MIP address or SNIP address), the site is a local site. Otherwise, it is a remote site.
        Default value: NONE Possible values = REMOTE, LOCAL

    siteipaddress(str): IP address for the GSLB site. The GSLB site uses this IP address to communicate with other GSLB
        sites. For a local site, use any IP address that is owned by the appliance (for example, a SNIP or MIP address,
        or the IP address of the ADNS service). Minimum length = 1

    publicip(str): Public IP address for the local site. Required only if the appliance is deployed in a private address
        space and the site has a public IP address hosted on an external firewall or a NAT device. Minimum length = 1

    metricexchange(str): Exchange metrics with other sites. Metrics are exchanged by using Metric Exchange Protocol (MEP).
        The appliances in the GSLB setup exchange health information once every second.   If you disable metrics
        exchange, you can use only static load balancing methods (such as round robin, static proximity, or the
        hash-based methods), and if you disable metrics exchange when a dynamic load balancing method (such as least
        connection) is in operation, the appliance falls back to round robin. Also, if you disable metrics exchange, you
        must use a monitor to determine the state of GSLB services. Otherwise, the service is marked as DOWN. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    nwmetricexchange(str): Exchange, with other GSLB sites, network metrics such as round-trip time (RTT), learned from
        communications with various local DNS (LDNS) servers used by clients. RTT information is used in the dynamic RTT
        load balancing method, and is exchanged every 5 seconds. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    sessionexchange(str): Exchange persistent session entries with other GSLB sites every five seconds. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    triggermonitor(str): Specify the conditions under which the GSLB service must be monitored by a monitor, if one is bound.
        Available settings function as follows: * ALWAYS - Monitor the GSLB service at all times. * MEPDOWN - Monitor the
        GSLB service only when the exchange of metrics through the Metrics Exchange Protocol (MEP) is disabled.
        MEPDOWN_SVCDOWN - Monitor the service in either of the following situations:  * The exchange of metrics through
        MEP is disabled. * The exchange of metrics through MEP is enabled but the status of the service, learned through
        metrics exchange, is DOWN. Default value: ALWAYS Possible values = ALWAYS, MEPDOWN, MEPDOWN_SVCDOWN

    parentsite(str): Parent site of the GSLB site, in a parent-child topology.

    clip(str): Cluster IP address. Specify this parameter to connect to the remote cluster site for GSLB auto-sync. Note: The
        cluster IP address is defined when creating the cluster.

    publicclip(str): IP address to be used to globally access the remote cluster when it is deployed behind a NAT. It can be
        same as the normal cluster IP address.

    naptrreplacementsuffix(str): The naptr replacement suffix configured here will be used to construct the naptr replacement
        field in NAPTR record. Minimum length = 1

    backupparentlist(list(str)): The list of backup gslb sites configured in preferred order. Need to be parent gsb sites.
        Default value: "None"

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.update_gslbsite <args>

    '''

    result = {}

    payload = {'gslbsite': {}}

    if sitename:
        payload['gslbsite']['sitename'] = sitename

    if sitetype:
        payload['gslbsite']['sitetype'] = sitetype

    if siteipaddress:
        payload['gslbsite']['siteipaddress'] = siteipaddress

    if publicip:
        payload['gslbsite']['publicip'] = publicip

    if metricexchange:
        payload['gslbsite']['metricexchange'] = metricexchange

    if nwmetricexchange:
        payload['gslbsite']['nwmetricexchange'] = nwmetricexchange

    if sessionexchange:
        payload['gslbsite']['sessionexchange'] = sessionexchange

    if triggermonitor:
        payload['gslbsite']['triggermonitor'] = triggermonitor

    if parentsite:
        payload['gslbsite']['parentsite'] = parentsite

    if clip:
        payload['gslbsite']['clip'] = clip

    if publicclip:
        payload['gslbsite']['publicclip'] = publicclip

    if naptrreplacementsuffix:
        payload['gslbsite']['naptrreplacementsuffix'] = naptrreplacementsuffix

    if backupparentlist:
        payload['gslbsite']['backupparentlist'] = backupparentlist

    execution = __proxy__['citrixns.put']('config/gslbsite', payload)

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


def update_gslbvserver(name=None, servicetype=None, iptype=None, dnsrecordtype=None, lbmethod=None,
                       backupsessiontimeout=None, backuplbmethod=None, netmask=None, v6netmasklen=None, tolerance=None,
                       persistencetype=None, persistenceid=None, persistmask=None, v6persistmasklen=None, timeout=None,
                       edr=None, ecs=None, ecsaddrvalidation=None, mir=None, disableprimaryondown=None,
                       dynamicweight=None, state=None, considereffectivestate=None, comment=None, somethod=None,
                       sopersistence=None, sopersistencetimeout=None, sothreshold=None, sobackupaction=None,
                       appflowlog=None, backupvserver=None, servicename=None, weight=None, domainname=None, ttl=None,
                       backupip=None, cookie_domain=None, cookietimeout=None, sitedomainttl=None, newname=None,
                       save=False):
    '''
    Update the running configuration for the gslbvserver config key.

    name(str): Name for the GSLB virtual server. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the virtual server is created.  CLI Users: If the name includes one
        or more spaces, enclose the name in double or single quotation marks (for example, "my vserver" or my vserver).
        Minimum length = 1

    servicetype(str): Protocol used by services bound to the virtual server. Possible values = HTTP, FTP, TCP, UDP, SSL,
        SSL_BRIDGE, SSL_TCP, NNTP, ANY, SIP_UDP, SIP_TCP, SIP_SSL, RADIUS, RDP, RTSP, MYSQL, MSSQL, ORACLE

    iptype(str): The IP type for this GSLB vserver. Default value: IPV4 Possible values = IPV4, IPV6

    dnsrecordtype(str): DNS record type to associate with the GSLB virtual servers domain name. Default value: A Possible
        values = A, AAAA, CNAME, NAPTR

    lbmethod(str): Load balancing method for the GSLB virtual server. Default value: LEASTCONNECTION Possible values =
        ROUNDROBIN, LEASTCONNECTION, LEASTRESPONSETIME, SOURCEIPHASH, LEASTBANDWIDTH, LEASTPACKETS, STATICPROXIMITY, RTT,
        CUSTOMLOAD

    backupsessiontimeout(int): A non zero value enables the feature whose minimum value is 2 minutes. The feature can be
        disabled by setting the value to zero. The created session is in effect for a specific client per domain. Minimum
        value = 0 Maximum value = 1440

    backuplbmethod(str): Backup load balancing method. Becomes operational if the primary load balancing method fails or
        cannot be used. Valid only if the primary method is based on either round-trip time (RTT) or static proximity.
        Possible values = ROUNDROBIN, LEASTCONNECTION, LEASTRESPONSETIME, SOURCEIPHASH, LEASTBANDWIDTH, LEASTPACKETS,
        STATICPROXIMITY, RTT, CUSTOMLOAD

    netmask(str): IPv4 network mask for use in the SOURCEIPHASH load balancing method. Minimum length = 1

    v6netmasklen(int): Number of bits to consider, in an IPv6 source IP address, for creating the hash that is required by
        the SOURCEIPHASH load balancing method. Default value: 128 Minimum value = 1 Maximum value = 128

    tolerance(int): Site selection tolerance, in milliseconds, for implementing the RTT load balancing method. If a sites RTT
        deviates from the lowest RTT by more than the specified tolerance, the site is not considered when the NetScaler
        appliance makes a GSLB decision. The appliance implements the round robin method of global server load balancing
        between sites whose RTT values are within the specified tolerance. If the tolerance is 0 (zero), the appliance
        always sends clients the IP address of the site with the lowest RTT. Minimum value = 0 Maximum value = 100

    persistencetype(str): Use source IP address based persistence for the virtual server.  After the load balancing method
        selects a service for the first packet, the IP address received in response to the DNS query is used for
        subsequent requests from the same client. Possible values = SOURCEIP, NONE

    persistenceid(int): The persistence ID for the GSLB virtual server. The ID is a positive integer that enables GSLB sites
        to identify the GSLB virtual server, and is required if source IP address based or spill over based persistence
        is enabled on the virtual server. Minimum value = 0 Maximum value = 65535

    persistmask(str): The optional IPv4 network mask applied to IPv4 addresses to establish source IP address based
        persistence. Minimum length = 1

    v6persistmasklen(int): Number of bits to consider in an IPv6 source IP address when creating source IP address based
        persistence sessions. Default value: 128 Minimum value = 1 Maximum value = 128

    timeout(int): Idle time, in minutes, after which a persistence entry is cleared. Default value: 2 Minimum value = 2
        Maximum value = 1440

    edr(str): Send clients an empty DNS response when the GSLB virtual server is DOWN. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    ecs(str): If enabled, respond with EDNS Client Subnet (ECS) option in the response for a DNS query with ECS. The ECS
        address will be used for persistence and spillover persistence (if enabled) instead of the LDNS address.
        Persistence mask is ignored if ECS is enabled. Default value: DISABLED Possible values = ENABLED, DISABLED

    ecsaddrvalidation(str): Validate if ECS address is a private or unroutable address and in such cases, use the LDNS IP.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    mir(str): Include multiple IP addresses in the DNS responses sent to clients. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    disableprimaryondown(str): Continue to direct traffic to the backup chain even after the primary GSLB virtual server
        returns to the UP state. Used when spillover is configured for the virtual server. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    dynamicweight(str): Specify if the appliance should consider the service count, service weights, or ignore both when
        using weight-based load balancing methods. The state of the number of services bound to the virtual server help
        the appliance to select the service. Default value: DISABLED Possible values = SERVICECOUNT, SERVICEWEIGHT,
        DISABLED

    state(str): State of the GSLB virtual server. Default value: ENABLED Possible values = ENABLED, DISABLED

    considereffectivestate(str): If the primary state of all bound GSLB services is DOWN, consider the effective states of
        all the GSLB services, obtained through the Metrics Exchange Protocol (MEP), when determining the state of the
        GSLB virtual server. To consider the effective state, set the parameter to STATE_ONLY. To disregard the effective
        state, set the parameter to NONE.   The effective state of a GSLB service is the ability of the corresponding
        virtual server to serve traffic. The effective state of the load balancing virtual server, which is transferred
        to the GSLB service, is UP even if only one virtual server in the backup chain of virtual servers is in the UP
        state. Default value: NONE Possible values = NONE, STATE_ONLY

    comment(str): Any comments that you might want to associate with the GSLB virtual server.

    somethod(str): Type of threshold that, when exceeded, triggers spillover. Available settings function as follows: *
        CONNECTION - Spillover occurs when the number of client connections exceeds the threshold. * DYNAMICCONNECTION -
        Spillover occurs when the number of client connections at the GSLB virtual server exceeds the sum of the maximum
        client (Max Clients) settings for bound GSLB services. Do not specify a spillover threshold for this setting,
        because the threshold is implied by the Max Clients settings of the bound GSLB services. * BANDWIDTH - Spillover
        occurs when the bandwidth consumed by the GSLB virtual servers incoming and outgoing traffic exceeds the
        threshold.  * HEALTH - Spillover occurs when the percentage of weights of the GSLB services that are UP drops
        below the threshold. For example, if services gslbSvc1, gslbSvc2, and gslbSvc3 are bound to a virtual server,
        with weights 1, 2, and 3, and the spillover threshold is 50%, spillover occurs if gslbSvc1 and gslbSvc3 or
        gslbSvc2 and gslbSvc3 transition to DOWN.  * NONE - Spillover does not occur. Possible values = CONNECTION,
        DYNAMICCONNECTION, BANDWIDTH, HEALTH, NONE

    sopersistence(str): If spillover occurs, maintain source IP address based persistence for both primary and backup GSLB
        virtual servers. Default value: DISABLED Possible values = ENABLED, DISABLED

    sopersistencetimeout(int): Timeout for spillover persistence, in minutes. Default value: 2 Minimum value = 2 Maximum
        value = 1440

    sothreshold(int): Threshold at which spillover occurs. Specify an integer for the CONNECTION spillover method, a
        bandwidth value in kilobits per second for the BANDWIDTH method (do not enter the units), or a percentage for the
        HEALTH method (do not enter the percentage symbol). Minimum value = 1 Maximum value = 4294967287

    sobackupaction(str): Action to be performed if spillover is to take effect, but no backup chain to spillover is usable or
        exists. Possible values = DROP, ACCEPT, REDIRECT

    appflowlog(str): Enable logging appflow flow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    backupvserver(str): Name of the backup GSLB virtual server to which the appliance should to forward requests if the
        status of the primary GSLB virtual server is down or exceeds its spillover threshold. Minimum length = 1

    servicename(str): Name of the GSLB service for which to change the weight. Minimum length = 1

    weight(int): Weight to assign to the GSLB service. Minimum value = 1 Maximum value = 100

    domainname(str): Domain name for which to change the time to live (TTL) and/or backup service IP address. Minimum length
        = 1

    ttl(int): Time to live (TTL) for the domain. Minimum value = 1

    backupip(str): The IP address of the backup service for the specified domain name. Used when all the services bound to
        the domain are down, or when the backup chain of virtual servers is down. Minimum length = 1

    cookie_domain(str): The cookie domain for the GSLB site. Used when inserting the GSLB site cookie in the HTTP response.
        Minimum length = 1

    cookietimeout(int): Timeout, in minutes, for the GSLB site cookie. Minimum value = 0 Maximum value = 1440

    sitedomainttl(int): TTL, in seconds, for all internally created site domains (created when a site prefix is configured on
        a GSLB service) that are associated with this virtual server. Minimum value = 1

    newname(str): New name for the GSLB virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' global_server_load_balancing.update_gslbvserver <args>

    '''

    result = {}

    payload = {'gslbvserver': {}}

    if name:
        payload['gslbvserver']['name'] = name

    if servicetype:
        payload['gslbvserver']['servicetype'] = servicetype

    if iptype:
        payload['gslbvserver']['iptype'] = iptype

    if dnsrecordtype:
        payload['gslbvserver']['dnsrecordtype'] = dnsrecordtype

    if lbmethod:
        payload['gslbvserver']['lbmethod'] = lbmethod

    if backupsessiontimeout:
        payload['gslbvserver']['backupsessiontimeout'] = backupsessiontimeout

    if backuplbmethod:
        payload['gslbvserver']['backuplbmethod'] = backuplbmethod

    if netmask:
        payload['gslbvserver']['netmask'] = netmask

    if v6netmasklen:
        payload['gslbvserver']['v6netmasklen'] = v6netmasklen

    if tolerance:
        payload['gslbvserver']['tolerance'] = tolerance

    if persistencetype:
        payload['gslbvserver']['persistencetype'] = persistencetype

    if persistenceid:
        payload['gslbvserver']['persistenceid'] = persistenceid

    if persistmask:
        payload['gslbvserver']['persistmask'] = persistmask

    if v6persistmasklen:
        payload['gslbvserver']['v6persistmasklen'] = v6persistmasklen

    if timeout:
        payload['gslbvserver']['timeout'] = timeout

    if edr:
        payload['gslbvserver']['edr'] = edr

    if ecs:
        payload['gslbvserver']['ecs'] = ecs

    if ecsaddrvalidation:
        payload['gslbvserver']['ecsaddrvalidation'] = ecsaddrvalidation

    if mir:
        payload['gslbvserver']['mir'] = mir

    if disableprimaryondown:
        payload['gslbvserver']['disableprimaryondown'] = disableprimaryondown

    if dynamicweight:
        payload['gslbvserver']['dynamicweight'] = dynamicweight

    if state:
        payload['gslbvserver']['state'] = state

    if considereffectivestate:
        payload['gslbvserver']['considereffectivestate'] = considereffectivestate

    if comment:
        payload['gslbvserver']['comment'] = comment

    if somethod:
        payload['gslbvserver']['somethod'] = somethod

    if sopersistence:
        payload['gslbvserver']['sopersistence'] = sopersistence

    if sopersistencetimeout:
        payload['gslbvserver']['sopersistencetimeout'] = sopersistencetimeout

    if sothreshold:
        payload['gslbvserver']['sothreshold'] = sothreshold

    if sobackupaction:
        payload['gslbvserver']['sobackupaction'] = sobackupaction

    if appflowlog:
        payload['gslbvserver']['appflowlog'] = appflowlog

    if backupvserver:
        payload['gslbvserver']['backupvserver'] = backupvserver

    if servicename:
        payload['gslbvserver']['servicename'] = servicename

    if weight:
        payload['gslbvserver']['weight'] = weight

    if domainname:
        payload['gslbvserver']['domainname'] = domainname

    if ttl:
        payload['gslbvserver']['ttl'] = ttl

    if backupip:
        payload['gslbvserver']['backupip'] = backupip

    if cookie_domain:
        payload['gslbvserver']['cookie_domain'] = cookie_domain

    if cookietimeout:
        payload['gslbvserver']['cookietimeout'] = cookietimeout

    if sitedomainttl:
        payload['gslbvserver']['sitedomainttl'] = sitedomainttl

    if newname:
        payload['gslbvserver']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/gslbvserver', payload)

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
