# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the basic key.

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

__virtualname__ = 'basic'


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

    return False, 'The basic execution module can only be loaded for citrixns proxy minions.'


def add_location(ipfrom=None, ipto=None, preferredlocation=None, longitude=None, latitude=None, save=False):
    '''
    Add a new location to the running configuration.

    ipfrom(str): First IP address in the range, in dotted decimal notation. Minimum length = 1

    ipto(str): Last IP address in the range, in dotted decimal notation. Minimum length = 1

    preferredlocation(str): String of qualifiers, in dotted notation, describing the geographical location of the IP address
        range. Each qualifier is more specific than the one that precedes it, as in
        continent.country.region.city.isp.organization. For example, "NA.US.CA.San Jose.ATT.citrix".  Note: A qualifier
        that includes a dot (.) or space ( ) must be enclosed in double quotation marks. Minimum length = 1

    longitude(int): Numerical value, in degrees, specifying the longitude of the geographical location of the IP
        address-range.  Note: Longitude and latitude parameters are used for selecting a service with the static
        proximity GSLB method. If they are not specified, selection is based on the qualifiers specified for the
        location. Minimum value = -180 Maximum value = 180

    latitude(int): Numerical value, in degrees, specifying the latitude of the geographical location of the IP address-range.
         Note: Longitude and latitude parameters are used for selecting a service with the static proximity GSLB method.
        If they are not specified, selection is based on the qualifiers specified for the location. Minimum value = -90
        Maximum value = 90

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_location <args>

    '''

    result = {}

    payload = {'location': {}}

    if ipfrom:
        payload['location']['ipfrom'] = ipfrom

    if ipto:
        payload['location']['ipto'] = ipto

    if preferredlocation:
        payload['location']['preferredlocation'] = preferredlocation

    if longitude:
        payload['location']['longitude'] = longitude

    if latitude:
        payload['location']['latitude'] = latitude

    execution = __proxy__['citrixns.post']('config/location', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_locationfile(locationfile=None, format=None, src=None, save=False):
    '''
    Add a new locationfile to the running configuration.

    locationfile(str): Name of the location file, with or without absolute path. If the path is not included, the default
        path (/var/netscaler/locdb) is assumed. In a high availability setup, the static database must be stored in the
        same location on both NetScaler appliances. Minimum length = 1

    format(str): Format of the location file. Required for the NetScaler appliance to identify how to read the location file.
        Default value: netscaler Possible values = netscaler, ip-country, ip-country-isp, ip-country-region-city,
        ip-country-region-city-isp, geoip-country, geoip-region, geoip-city, geoip-country-org, geoip-country-isp,
        geoip-city-isp-org

    src(str): URL \\(protocol, host, path, and file name\\) from where the location file will be imported.  NOTE: The import
        fails if the object to be imported is on an HTTPS server that requires client certificate authentication for
        access. Minimum length = 1 Maximum length = 2047

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_locationfile <args>

    '''

    result = {}

    payload = {'locationfile': {}}

    if locationfile:
        payload['locationfile']['Locationfile'] = locationfile

    if format:
        payload['locationfile']['format'] = format

    if src:
        payload['locationfile']['src'] = src

    execution = __proxy__['citrixns.post']('config/locationfile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_locationfile6(locationfile=None, format=None, src=None, save=False):
    '''
    Add a new locationfile6 to the running configuration.

    locationfile(str): Name of the IPv6 location file, with or without absolute path. If the path is not included, the
        default path (/var/netscaler/locdb) is assumed. In a high availability setup, the static database must be stored
        in the same location on both NetScaler appliances. Minimum length = 1

    format(str): Format of the IPv6 location file. Required for the NetScaler appliance to identify how to read the location
        file. Default value: netscaler6 Possible values = netscaler6, geoip-country6

    src(str): URL \\(protocol, host, path, and file name\\) from where the location file will be imported.  NOTE: The import
        fails if the object to be imported is on an HTTPS server that requires client certificate authentication for
        access. Minimum length = 1 Maximum length = 2047

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_locationfile6 <args>

    '''

    result = {}

    payload = {'locationfile6': {}}

    if locationfile:
        payload['locationfile6']['Locationfile'] = locationfile

    if format:
        payload['locationfile6']['format'] = format

    if src:
        payload['locationfile6']['src'] = src

    execution = __proxy__['citrixns.post']('config/locationfile6', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_radiusnode(nodeprefix=None, radkey=None, save=False):
    '''
    Add a new radiusnode to the running configuration.

    nodeprefix(str): IP address/IP prefix of radius node in CIDR format.

    radkey(str): The key shared between the RADIUS server and clients.  Required for NetScaler appliance to communicate with
        the RADIUS nodes.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_radiusnode <args>

    '''

    result = {}

    payload = {'radiusnode': {}}

    if nodeprefix:
        payload['radiusnode']['nodeprefix'] = nodeprefix

    if radkey:
        payload['radiusnode']['radkey'] = radkey

    execution = __proxy__['citrixns.post']('config/radiusnode', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_server(name=None, ipaddress=None, domain=None, translationip=None, translationmask=None, domainresolveretry=None,
               state=None, ipv6address=None, comment=None, td=None, domainresolvenow=None, delay=None, graceful=None,
               internal=None, newname=None, save=False):
    '''
    Add a new server to the running configuration.

    name(str): Name for the server.  Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Can be changed after the name is created. Minimum length = 1

    ipaddress(str): IPv4 or IPv6 address of the server. If you create an IP address based server, you can specify the name of
        the server, instead of its IP address, when creating a service. Note: If you do not create a server entry, the
        server IP address that you enter when you create a service becomes the name of the server.

    domain(str): Domain name of the server. For a domain based configuration, you must create the server first. Minimum
        length = 1

    translationip(str): IP address used to transform the servers DNS-resolved IP address.

    translationmask(str): The netmask of the translation ip.

    domainresolveretry(int): Time, in seconds, for which the NetScaler appliance must wait, after DNS resolution fails,
        before sending the next DNS query to resolve the domain name. Default value: 5 Minimum value = 5 Maximum value =
        20939

    state(str): Initial state of the server. Default value: ENABLED Possible values = ENABLED, DISABLED

    ipv6address(str): Support IPv6 addressing mode. If you configure a server with the IPv6 addressing mode, you cannot use
        the server in the IPv4 addressing mode. Default value: NO Possible values = YES, NO

    comment(str): Any information about the server.

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    domainresolvenow(bool): Immediately send a DNS query to resolve the servers domain name.

    delay(int): Time, in seconds, after which all the services configured on the server are disabled.

    graceful(str): Shut down gracefully, without accepting any new connections, and disabling each service when all of its
        connections are closed. Default value: NO Possible values = YES, NO

    internal(bool): Display names of the servers that have been created for internal use.

    newname(str): New name for the server. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_server <args>

    '''

    result = {}

    payload = {'server': {}}

    if name:
        payload['server']['name'] = name

    if ipaddress:
        payload['server']['ipaddress'] = ipaddress

    if domain:
        payload['server']['domain'] = domain

    if translationip:
        payload['server']['translationip'] = translationip

    if translationmask:
        payload['server']['translationmask'] = translationmask

    if domainresolveretry:
        payload['server']['domainresolveretry'] = domainresolveretry

    if state:
        payload['server']['state'] = state

    if ipv6address:
        payload['server']['ipv6address'] = ipv6address

    if comment:
        payload['server']['comment'] = comment

    if td:
        payload['server']['td'] = td

    if domainresolvenow:
        payload['server']['domainresolvenow'] = domainresolvenow

    if delay:
        payload['server']['delay'] = delay

    if graceful:
        payload['server']['graceful'] = graceful

    if internal:
        payload['server']['Internal'] = internal

    if newname:
        payload['server']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/server', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_service(name=None, ip=None, servername=None, servicetype=None, port=None, cleartextport=None, cachetype=None,
                maxclient=None, healthmonitor=None, maxreq=None, cacheable=None, cip=None, cipheader=None, usip=None,
                pathmonitor=None, pathmonitorindv=None, useproxyport=None, sc=None, sp=None, rtspsessionidremap=None,
                clttimeout=None, svrtimeout=None, customserverid=None, serverid=None, cka=None, tcpb=None, cmp=None,
                maxbandwidth=None, accessdown=None, monthreshold=None, state=None, downstateflush=None,
                tcpprofilename=None, httpprofilename=None, hashid=None, comment=None, appflowlog=None, netprofile=None,
                td=None, processlocal=None, dnsprofilename=None, monconnectionclose=None, ipaddress=None, weight=None,
                monitor_name_svc=None, riseapbrstatsmsgcode=None, delay=None, graceful=None, internal=None, newname=None,
                save=False):
    '''
    Add a new service to the running configuration.

    name(str): Name for the service. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the service has been created. Minimum length = 1

    ip(str): IP to assign to the service. Minimum length = 1

    servername(str): Name of the server that hosts the service. Minimum length = 1

    servicetype(str): Protocol in which data is exchanged with the service. Possible values = HTTP, FTP, TCP, UDP, SSL,
        SSL_BRIDGE, SSL_TCP, DTLS, NNTP, RPCSVR, DNS, ADNS, SNMP, RTSP, DHCPRA, ANY, SIP_UDP, SIP_TCP, SIP_SSL, DNS_TCP,
        ADNS_TCP, MYSQL, MSSQL, ORACLE, RADIUS, RADIUSListener, RDP, DIAMETER, SSL_DIAMETER, TFTP, SMPP, PPTP, GRE,
        SYSLOGTCP, SYSLOGUDP, FIX, SSL_FIX, USER_TCP, USER_SSL_TCP

    port(int): Port number of the service. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    cleartextport(int): Port to which clear text data must be sent after the appliance decrypts incoming SSL traffic.
        Applicable to transparent SSL services. Minimum value = 1

    cachetype(str): Cache type supported by the cache server. Possible values = TRANSPARENT, REVERSE, FORWARD

    maxclient(int): Maximum number of simultaneous open connections to the service. Minimum value = 0 Maximum value =
        4294967294

    healthmonitor(str): Monitor the health of this service. Available settings function as follows: YES - Send probes to
        check the health of the service. NO - Do not send probes to check the health of the service. With the NO option,
        the appliance shows the service as UP at all times. Default value: YES Possible values = YES, NO

    maxreq(int): Maximum number of requests that can be sent on a persistent connection to the service.  Note: Connection
        requests beyond this value are rejected. Minimum value = 0 Maximum value = 65535

    cacheable(str): Use the transparent cache redirection virtual server to forward requests to the cache server. Note: Do
        not specify this parameter if you set the Cache Type parameter. Default value: NO Possible values = YES, NO

    cip(str): Before forwarding a request to the service, insert an HTTP header with the clients IPv4 or IPv6 address as its
        value. Used if the server needs the clients IP address for security, accounting, or other purposes, and setting
        the Use Source IP parameter is not a viable option. Possible values = ENABLED, DISABLED

    cipheader(str): Name for the HTTP header whose value must be set to the IP address of the client. Used with the Client IP
        parameter. If you set the Client IP parameter, and you do not specify a name for the header, the appliance uses
        the header name specified for the global Client IP Header parameter (the cipHeader parameter in the set ns param
        CLI command or the Client IP Header parameter in the Configure HTTP Parameters dialog box at System ;gt; Settings
        ;gt; Change HTTP parameters). If the global Client IP Header parameter is not specified, the appliance inserts a
        header with the name "client-ip.". Minimum length = 1

    usip(str): Use the clients IP address as the source IP address when initiating a connection to the server. When creating
        a service, if you do not set this parameter, the service inherits the global Use Source IP setting (available in
        the enable ns mode and disable ns mode CLI commands, or in the System ;gt; Settings ;gt; Configure modes ;gt;
        Configure Modes dialog box). However, you can override this setting after you create the service. Possible values
        = YES, NO

    pathmonitor(str): Path monitoring for clustering. Possible values = YES, NO

    pathmonitorindv(str): Individual Path monitoring decisions. Possible values = YES, NO

    useproxyport(str): Use the proxy port as the source port when initiating connections with the server. With the NO
        setting, the client-side connection port is used as the source port for the server-side connection.  Note: This
        parameter is available only when the Use Source IP (USIP) parameter is set to YES. Possible values = YES, NO

    sc(str): State of SureConnect for the service. Default value: OFF Possible values = ON, OFF

    sp(str): Enable surge protection for the service. Possible values = ON, OFF

    rtspsessionidremap(str): Enable RTSP session ID mapping for the service. Default value: OFF Possible values = ON, OFF

    clttimeout(int): Time, in seconds, after which to terminate an idle client connection. Minimum value = 0 Maximum value =
        31536000

    svrtimeout(int): Time, in seconds, after which to terminate an idle server connection. Minimum value = 0 Maximum value =
        31536000

    customserverid(str): Unique identifier for the service. Used when the persistency type for the virtual server is set to
        Custom Server ID. Default value: "None"

    serverid(int): The identifier for the service. This is used when the persistency type is set to Custom Server ID.

    cka(str): Enable client keep-alive for the service. Possible values = YES, NO

    tcpb(str): Enable TCP buffering for the service. Possible values = YES, NO

    cmp(str): Enable compression for the service. Possible values = YES, NO

    maxbandwidth(int): Maximum bandwidth, in Kbps, allocated to the service. Minimum value = 0 Maximum value = 4294967287

    accessdown(str): Use Layer 2 mode to bridge the packets sent to this service if it is marked as DOWN. If the service is
        DOWN, and this parameter is disabled, the packets are dropped. Default value: NO Possible values = YES, NO

    monthreshold(int): Minimum sum of weights of the monitors that are bound to this service. Used to determine whether to
        mark a service as UP or DOWN. Minimum value = 0 Maximum value = 65535

    state(str): Initial state of the service. Default value: ENABLED Possible values = ENABLED, DISABLED

    downstateflush(str): Flush all active transactions associated with a service whose state transitions from UP to DOWN. Do
        not enable this option for applications that must complete their transactions. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    tcpprofilename(str): Name of the TCP profile that contains TCP configuration settings for the service. Minimum length = 1
        Maximum length = 127

    httpprofilename(str): Name of the HTTP profile that contains HTTP configuration settings for the service. Minimum length
        = 1 Maximum length = 127

    hashid(int): A numerical identifier that can be used by hash based load balancing methods. Must be unique for each
        service. Minimum value = 1

    comment(str): Any information about the service.

    appflowlog(str): Enable logging of AppFlow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    netprofile(str): Network profile to use for the service. Minimum length = 1 Maximum length = 127

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    processlocal(str): By turning on this option packets destined to a service in a cluster will not under go any steering.
        Turn this option for single packet request response mode or when the upstream device is performing a proper RSS
        for connection based distribution. Default value: DISABLED Possible values = ENABLED, DISABLED

    dnsprofilename(str): Name of the DNS profile to be associated with the service. DNS profile properties will applied to
        the transactions processed by a service. This parameter is valid only for ADNS and ADNS-TCP services. Minimum
        length = 1 Maximum length = 127

    monconnectionclose(str): Close monitoring connections by sending the service a connection termination message with the
        specified bit set. Default value: NONE Possible values = RESET, FIN

    ipaddress(str): The new IP address of the service.

    weight(int): Weight to assign to the monitor-service binding. When a monitor is UP, the weight assigned to its binding
        with the service determines how much the monitor contributes toward keeping the health of the service above the
        value configured for the Monitor Threshold parameter. Minimum value = 1 Maximum value = 100

    monitor_name_svc(str): Name of the monitor bound to the specified service. Minimum length = 1

    riseapbrstatsmsgcode(int): The code indicating the rise apbr status.

    delay(int): Time, in seconds, allocated to the NetScaler appliance for a graceful shutdown of the service. During this
        period, new requests are sent to the service only for clients who already have persistent sessions on the
        appliance. Requests from new clients are load balanced among other available services. After the delay time
        expires, no requests are sent to the service, and the service is marked as unavailable (OUT OF SERVICE).

    graceful(str): Shut down gracefully, not accepting any new connections, and disabling the service when all of its
        connections are closed. Default value: NO Possible values = YES, NO

    internal(bool): Display only dynamically learned services.

    newname(str): New name for the service. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_service <args>

    '''

    result = {}

    payload = {'service': {}}

    if name:
        payload['service']['name'] = name

    if ip:
        payload['service']['ip'] = ip

    if servername:
        payload['service']['servername'] = servername

    if servicetype:
        payload['service']['servicetype'] = servicetype

    if port:
        payload['service']['port'] = port

    if cleartextport:
        payload['service']['cleartextport'] = cleartextport

    if cachetype:
        payload['service']['cachetype'] = cachetype

    if maxclient:
        payload['service']['maxclient'] = maxclient

    if healthmonitor:
        payload['service']['healthmonitor'] = healthmonitor

    if maxreq:
        payload['service']['maxreq'] = maxreq

    if cacheable:
        payload['service']['cacheable'] = cacheable

    if cip:
        payload['service']['cip'] = cip

    if cipheader:
        payload['service']['cipheader'] = cipheader

    if usip:
        payload['service']['usip'] = usip

    if pathmonitor:
        payload['service']['pathmonitor'] = pathmonitor

    if pathmonitorindv:
        payload['service']['pathmonitorindv'] = pathmonitorindv

    if useproxyport:
        payload['service']['useproxyport'] = useproxyport

    if sc:
        payload['service']['sc'] = sc

    if sp:
        payload['service']['sp'] = sp

    if rtspsessionidremap:
        payload['service']['rtspsessionidremap'] = rtspsessionidremap

    if clttimeout:
        payload['service']['clttimeout'] = clttimeout

    if svrtimeout:
        payload['service']['svrtimeout'] = svrtimeout

    if customserverid:
        payload['service']['customserverid'] = customserverid

    if serverid:
        payload['service']['serverid'] = serverid

    if cka:
        payload['service']['cka'] = cka

    if tcpb:
        payload['service']['tcpb'] = tcpb

    if cmp:
        payload['service']['cmp'] = cmp

    if maxbandwidth:
        payload['service']['maxbandwidth'] = maxbandwidth

    if accessdown:
        payload['service']['accessdown'] = accessdown

    if monthreshold:
        payload['service']['monthreshold'] = monthreshold

    if state:
        payload['service']['state'] = state

    if downstateflush:
        payload['service']['downstateflush'] = downstateflush

    if tcpprofilename:
        payload['service']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['service']['httpprofilename'] = httpprofilename

    if hashid:
        payload['service']['hashid'] = hashid

    if comment:
        payload['service']['comment'] = comment

    if appflowlog:
        payload['service']['appflowlog'] = appflowlog

    if netprofile:
        payload['service']['netprofile'] = netprofile

    if td:
        payload['service']['td'] = td

    if processlocal:
        payload['service']['processlocal'] = processlocal

    if dnsprofilename:
        payload['service']['dnsprofilename'] = dnsprofilename

    if monconnectionclose:
        payload['service']['monconnectionclose'] = monconnectionclose

    if ipaddress:
        payload['service']['ipaddress'] = ipaddress

    if weight:
        payload['service']['weight'] = weight

    if monitor_name_svc:
        payload['service']['monitor_name_svc'] = monitor_name_svc

    if riseapbrstatsmsgcode:
        payload['service']['riseapbrstatsmsgcode'] = riseapbrstatsmsgcode

    if delay:
        payload['service']['delay'] = delay

    if graceful:
        payload['service']['graceful'] = graceful

    if internal:
        payload['service']['Internal'] = internal

    if newname:
        payload['service']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/service', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_service_dospolicy_binding(policyname=None, name=None, save=False):
    '''
    Add a new service_dospolicy_binding to the running configuration.

    policyname(str): The name of the policyname for which this service is bound.

    name(str): Name of the service to which to bind a policy or monitor. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_service_dospolicy_binding <args>

    '''

    result = {}

    payload = {'service_dospolicy_binding': {}}

    if policyname:
        payload['service_dospolicy_binding']['policyname'] = policyname

    if name:
        payload['service_dospolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/service_dospolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_service_lbmonitor_binding(weight=None, name=None, passive=None, monitor_name=None, monstate=None, save=False):
    '''
    Add a new service_lbmonitor_binding to the running configuration.

    weight(int): Weight to assign to the monitor-service binding. When a monitor is UP, the weight assigned to its binding
        with the service determines how much the monitor contributes toward keeping the health of the service above the
        value configured for the Monitor Threshold parameter. Minimum value = 1 Maximum value = 100

    name(str): Name of the service to which to bind a policy or monitor. Minimum length = 1

    passive(bool): Indicates if load monitor is passive. A passive load monitor does not remove service from LB decision when
        threshold is breached.

    monitor_name(str): The monitor Names.

    monstate(str): The configured state (enable/disable) of the monitor on this server. Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_service_lbmonitor_binding <args>

    '''

    result = {}

    payload = {'service_lbmonitor_binding': {}}

    if weight:
        payload['service_lbmonitor_binding']['weight'] = weight

    if name:
        payload['service_lbmonitor_binding']['name'] = name

    if passive:
        payload['service_lbmonitor_binding']['passive'] = passive

    if monitor_name:
        payload['service_lbmonitor_binding']['monitor_name'] = monitor_name

    if monstate:
        payload['service_lbmonitor_binding']['monstate'] = monstate

    execution = __proxy__['citrixns.post']('config/service_lbmonitor_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_service_scpolicy_binding(policyname=None, name=None, save=False):
    '''
    Add a new service_scpolicy_binding to the running configuration.

    policyname(str): The name of the policyname for which this service is bound.

    name(str): Name of the service to which to bind a policy or monitor. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_service_scpolicy_binding <args>

    '''

    result = {}

    payload = {'service_scpolicy_binding': {}}

    if policyname:
        payload['service_scpolicy_binding']['policyname'] = policyname

    if name:
        payload['service_scpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/service_scpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_servicegroup(servicegroupname=None, servicetype=None, cachetype=None, td=None, maxclient=None, maxreq=None,
                     cacheable=None, cip=None, cipheader=None, usip=None, pathmonitor=None, pathmonitorindv=None,
                     useproxyport=None, healthmonitor=None, sc=None, sp=None, rtspsessionidremap=None, clttimeout=None,
                     svrtimeout=None, cka=None, tcpb=None, cmp=None, maxbandwidth=None, monthreshold=None, state=None,
                     downstateflush=None, tcpprofilename=None, httpprofilename=None, comment=None, appflowlog=None,
                     netprofile=None, autoscale=None, memberport=None, monconnectionclose=None, servername=None,
                     port=None, weight=None, customserverid=None, serverid=None, hashid=None, monitor_name_svc=None,
                     dup_weight=None, riseapbrstatsmsgcode=None, delay=None, graceful=None, includemembers=None,
                     newname=None, save=False):
    '''
    Add a new servicegroup to the running configuration.

    servicegroupname(str): Name of the service group. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the name is created. Minimum length = 1

    servicetype(str): Protocol used to exchange data with the service. Possible values = HTTP, FTP, TCP, UDP, SSL,
        SSL_BRIDGE, SSL_TCP, DTLS, NNTP, RPCSVR, DNS, ADNS, SNMP, RTSP, DHCPRA, ANY, SIP_UDP, SIP_TCP, SIP_SSL, DNS_TCP,
        ADNS_TCP, MYSQL, MSSQL, ORACLE, RADIUS, RADIUSListener, RDP, DIAMETER, SSL_DIAMETER, TFTP, SMPP, PPTP, GRE,
        SYSLOGTCP, SYSLOGUDP, FIX, SSL_FIX, USER_TCP, USER_SSL_TCP

    cachetype(str): Cache type supported by the cache server. Possible values = TRANSPARENT, REVERSE, FORWARD

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    maxclient(int): Maximum number of simultaneous open connections for the service group. Minimum value = 0 Maximum value =
        4294967294

    maxreq(int): Maximum number of requests that can be sent on a persistent connection to the service group.  Note:
        Connection requests beyond this value are rejected. Minimum value = 0 Maximum value = 65535

    cacheable(str): Use the transparent cache redirection virtual server to forward the request to the cache server. Note: Do
        not set this parameter if you set the Cache Type. Default value: NO Possible values = YES, NO

    cip(str): Insert the Client IP header in requests forwarded to the service. Possible values = ENABLED, DISABLED

    cipheader(str): Name of the HTTP header whose value must be set to the IP address of the client. Used with the Client IP
        parameter. If client IP insertion is enabled, and the client IP header is not specified, the value of Client IP
        Header parameter or the value set by the set ns config command is used as clients IP header name. Minimum length
        = 1

    usip(str): Use clients IP address as the source IP address when initiating connection to the server. With the NO setting,
        which is the default, a mapped IP (MIP) address or subnet IP (SNIP) address is used as the source IP address to
        initiate server side connections. Possible values = YES, NO

    pathmonitor(str): Path monitoring for clustering. Possible values = YES, NO

    pathmonitorindv(str): Individual Path monitoring decisions. Possible values = YES, NO

    useproxyport(str): Use the proxy port as the source port when initiating connections with the server. With the NO
        setting, the client-side connection port is used as the source port for the server-side connection.  Note: This
        parameter is available only when the Use Source IP (USIP) parameter is set to YES. Possible values = YES, NO

    healthmonitor(str): Monitor the health of this service. Available settings function as follows: YES - Send probes to
        check the health of the service. NO - Do not send probes to check the health of the service. With the NO option,
        the appliance shows the service as UP at all times. Default value: YES Possible values = YES, NO

    sc(str): State of the SureConnect feature for the service group. Default value: OFF Possible values = ON, OFF

    sp(str): Enable surge protection for the service group. Default value: OFF Possible values = ON, OFF

    rtspsessionidremap(str): Enable RTSP session ID mapping for the service group. Default value: OFF Possible values = ON,
        OFF

    clttimeout(int): Time, in seconds, after which to terminate an idle client connection. Minimum value = 0 Maximum value =
        31536000

    svrtimeout(int): Time, in seconds, after which to terminate an idle server connection. Minimum value = 0 Maximum value =
        31536000

    cka(str): Enable client keep-alive for the service group. Possible values = YES, NO

    tcpb(str): Enable TCP buffering for the service group. Possible values = YES, NO

    cmp(str): Enable compression for the specified service. Possible values = YES, NO

    maxbandwidth(int): Maximum bandwidth, in Kbps, allocated for all the services in the service group. Minimum value = 0
        Maximum value = 4294967287

    monthreshold(int): Minimum sum of weights of the monitors that are bound to this service. Used to determine whether to
        mark a service as UP or DOWN. Minimum value = 0 Maximum value = 65535

    state(str): Initial state of the service group. Default value: ENABLED Possible values = ENABLED, DISABLED

    downstateflush(str): Flush all active transactions associated with all the services in the service group whose state
        transitions from UP to DOWN. Do not enable this option for applications that must complete their transactions.
        Default value: ENABLED Possible values = ENABLED, DISABLED

    tcpprofilename(str): Name of the TCP profile that contains TCP configuration settings for the service group. Minimum
        length = 1 Maximum length = 127

    httpprofilename(str): Name of the HTTP profile that contains HTTP configuration settings for the service group. Minimum
        length = 1 Maximum length = 127

    comment(str): Any information about the service group.

    appflowlog(str): Enable logging of AppFlow information for the specified service group. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    netprofile(str): Network profile for the service group. Minimum length = 1 Maximum length = 127

    autoscale(str): Auto scale option for a servicegroup. Default value: DISABLED Possible values = DISABLED, DNS, POLICY

    memberport(int): member port.

    monconnectionclose(str): Close monitoring connections by sending the service a connection termination message with the
        specified bit set. Default value: NONE Possible values = RESET, FIN

    servername(str): Name of the server to which to bind the service group. Minimum length = 1

    port(int): Server port number. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    weight(int): Weight to assign to the servers in the service group. Specifies the capacity of the servers relative to the
        other servers in the load balancing configuration. The higher the weight, the higher the percentage of requests
        sent to the service. Minimum value = 1 Maximum value = 100

    customserverid(str): The identifier for this IP:Port pair. Used when the persistency type is set to Custom Server ID.
        Default value: "None"

    serverid(int): The identifier for the service. This is used when the persistency type is set to Custom Server ID.

    hashid(int): The hash identifier for the service. This must be unique for each service. This parameter is used by hash
        based load balancing methods. Minimum value = 1

    monitor_name_svc(str): Name of the monitor bound to the service group. Used to assign a weight to the monitor. Minimum
        length = 1

    dup_weight(int): weight of the monitor that is bound to servicegroup. Minimum value = 1

    riseapbrstatsmsgcode(int): The code indicating the rise apbr status.

    delay(int): Time, in seconds, allocated for a shutdown of the services in the service group. During this period, new
        requests are sent to the service only for clients who already have persistent sessions on the appliance. Requests
        from new clients are load balanced among other available services. After the delay time expires, no requests are
        sent to the service, and the service is marked as unavailable (OUT OF SERVICE).

    graceful(str): Wait for all existing connections to the service to terminate before shutting down the service. Default
        value: NO Possible values = YES, NO

    includemembers(bool): Display the members of the listed service groups in addition to their settings. Can be specified
        when no service group name is provided in the command. In that case, the details displayed for each service group
        are identical to the details displayed when a service group name is provided, except that bound monitors are not
        displayed.

    newname(str): New name for the service group. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_servicegroup <args>

    '''

    result = {}

    payload = {'servicegroup': {}}

    if servicegroupname:
        payload['servicegroup']['servicegroupname'] = servicegroupname

    if servicetype:
        payload['servicegroup']['servicetype'] = servicetype

    if cachetype:
        payload['servicegroup']['cachetype'] = cachetype

    if td:
        payload['servicegroup']['td'] = td

    if maxclient:
        payload['servicegroup']['maxclient'] = maxclient

    if maxreq:
        payload['servicegroup']['maxreq'] = maxreq

    if cacheable:
        payload['servicegroup']['cacheable'] = cacheable

    if cip:
        payload['servicegroup']['cip'] = cip

    if cipheader:
        payload['servicegroup']['cipheader'] = cipheader

    if usip:
        payload['servicegroup']['usip'] = usip

    if pathmonitor:
        payload['servicegroup']['pathmonitor'] = pathmonitor

    if pathmonitorindv:
        payload['servicegroup']['pathmonitorindv'] = pathmonitorindv

    if useproxyport:
        payload['servicegroup']['useproxyport'] = useproxyport

    if healthmonitor:
        payload['servicegroup']['healthmonitor'] = healthmonitor

    if sc:
        payload['servicegroup']['sc'] = sc

    if sp:
        payload['servicegroup']['sp'] = sp

    if rtspsessionidremap:
        payload['servicegroup']['rtspsessionidremap'] = rtspsessionidremap

    if clttimeout:
        payload['servicegroup']['clttimeout'] = clttimeout

    if svrtimeout:
        payload['servicegroup']['svrtimeout'] = svrtimeout

    if cka:
        payload['servicegroup']['cka'] = cka

    if tcpb:
        payload['servicegroup']['tcpb'] = tcpb

    if cmp:
        payload['servicegroup']['cmp'] = cmp

    if maxbandwidth:
        payload['servicegroup']['maxbandwidth'] = maxbandwidth

    if monthreshold:
        payload['servicegroup']['monthreshold'] = monthreshold

    if state:
        payload['servicegroup']['state'] = state

    if downstateflush:
        payload['servicegroup']['downstateflush'] = downstateflush

    if tcpprofilename:
        payload['servicegroup']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['servicegroup']['httpprofilename'] = httpprofilename

    if comment:
        payload['servicegroup']['comment'] = comment

    if appflowlog:
        payload['servicegroup']['appflowlog'] = appflowlog

    if netprofile:
        payload['servicegroup']['netprofile'] = netprofile

    if autoscale:
        payload['servicegroup']['autoscale'] = autoscale

    if memberport:
        payload['servicegroup']['memberport'] = memberport

    if monconnectionclose:
        payload['servicegroup']['monconnectionclose'] = monconnectionclose

    if servername:
        payload['servicegroup']['servername'] = servername

    if port:
        payload['servicegroup']['port'] = port

    if weight:
        payload['servicegroup']['weight'] = weight

    if customserverid:
        payload['servicegroup']['customserverid'] = customserverid

    if serverid:
        payload['servicegroup']['serverid'] = serverid

    if hashid:
        payload['servicegroup']['hashid'] = hashid

    if monitor_name_svc:
        payload['servicegroup']['monitor_name_svc'] = monitor_name_svc

    if dup_weight:
        payload['servicegroup']['dup_weight'] = dup_weight

    if riseapbrstatsmsgcode:
        payload['servicegroup']['riseapbrstatsmsgcode'] = riseapbrstatsmsgcode

    if delay:
        payload['servicegroup']['delay'] = delay

    if graceful:
        payload['servicegroup']['graceful'] = graceful

    if includemembers:
        payload['servicegroup']['includemembers'] = includemembers

    if newname:
        payload['servicegroup']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/servicegroup', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_servicegroup_lbmonitor_binding(servicegroupname=None, port=None, state=None, hashid=None, serverid=None,
                                       customserverid=None, weight=None, monitor_name=None, passive=None, monstate=None,
                                       save=False):
    '''
    Add a new servicegroup_lbmonitor_binding to the running configuration.

    servicegroupname(str): Name of the service group. Minimum length = 1

    port(int): Port number of the service. Each service must have a unique port number. Range 1 - 65535 * in CLI is
        represented as 65535 in NITRO API

    state(str): Initial state of the service after binding. Default value: ENABLED Possible values = ENABLED, DISABLED

    hashid(int): Unique numerical identifier used by hash based load balancing methods to identify a service. Minimum value =
        1

    serverid(int): The identifier for the service. This is used when the persistency type is set to Custom Server ID.

    customserverid(str): Unique service identifier. Used when the persistency type for the virtual server is set to Custom
        Server ID. Default value: "None"

    weight(int): Weight to assign to the servers in the service group. Specifies the capacity of the servers relative to the
        other servers in the load balancing configuration. The higher the weight, the higher the percentage of requests
        sent to the service. Minimum value = 1 Maximum value = 100

    monitor_name(str): Monitor name.

    passive(bool): Indicates if load monitor is passive. A passive load monitor does not remove service from LB decision when
        threshold is breached.

    monstate(str): Monitor state. Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_servicegroup_lbmonitor_binding <args>

    '''

    result = {}

    payload = {'servicegroup_lbmonitor_binding': {}}

    if servicegroupname:
        payload['servicegroup_lbmonitor_binding']['servicegroupname'] = servicegroupname

    if port:
        payload['servicegroup_lbmonitor_binding']['port'] = port

    if state:
        payload['servicegroup_lbmonitor_binding']['state'] = state

    if hashid:
        payload['servicegroup_lbmonitor_binding']['hashid'] = hashid

    if serverid:
        payload['servicegroup_lbmonitor_binding']['serverid'] = serverid

    if customserverid:
        payload['servicegroup_lbmonitor_binding']['customserverid'] = customserverid

    if weight:
        payload['servicegroup_lbmonitor_binding']['weight'] = weight

    if monitor_name:
        payload['servicegroup_lbmonitor_binding']['monitor_name'] = monitor_name

    if passive:
        payload['servicegroup_lbmonitor_binding']['passive'] = passive

    if monstate:
        payload['servicegroup_lbmonitor_binding']['monstate'] = monstate

    execution = __proxy__['citrixns.post']('config/servicegroup_lbmonitor_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_servicegroup_servicegroupmember_binding(servicegroupname=None, ip=None, port=None, state=None, hashid=None,
                                                serverid=None, servername=None, customserverid=None, weight=None,
                                                save=False):
    '''
    Add a new servicegroup_servicegroupmember_binding to the running configuration.

    servicegroupname(str): Name of the service group. Minimum length = 1

    ip(str): IP Address.

    port(int): Server port number. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    state(str): Initial state of the service group. Default value: ENABLED Possible values = ENABLED, DISABLED

    hashid(int): The hash identifier for the service. This must be unique for each service. This parameter is used by hash
        based load balancing methods. Minimum value = 1

    serverid(int): The identifier for the service. This is used when the persistency type is set to Custom Server ID.

    servername(str): Name of the server to which to bind the service group. Minimum length = 1

    customserverid(str): The identifier for this IP:Port pair. Used when the persistency type is set to Custom Server ID.
        Default value: "None"

    weight(int): Weight to assign to the servers in the service group. Specifies the capacity of the servers relative to the
        other servers in the load balancing configuration. The higher the weight, the higher the percentage of requests
        sent to the service. Minimum value = 1 Maximum value = 100

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.add_servicegroup_servicegroupmember_binding <args>

    '''

    result = {}

    payload = {'servicegroup_servicegroupmember_binding': {}}

    if servicegroupname:
        payload['servicegroup_servicegroupmember_binding']['servicegroupname'] = servicegroupname

    if ip:
        payload['servicegroup_servicegroupmember_binding']['ip'] = ip

    if port:
        payload['servicegroup_servicegroupmember_binding']['port'] = port

    if state:
        payload['servicegroup_servicegroupmember_binding']['state'] = state

    if hashid:
        payload['servicegroup_servicegroupmember_binding']['hashid'] = hashid

    if serverid:
        payload['servicegroup_servicegroupmember_binding']['serverid'] = serverid

    if servername:
        payload['servicegroup_servicegroupmember_binding']['servername'] = servername

    if customserverid:
        payload['servicegroup_servicegroupmember_binding']['customserverid'] = customserverid

    if weight:
        payload['servicegroup_servicegroupmember_binding']['weight'] = weight

    execution = __proxy__['citrixns.post']('config/servicegroup_servicegroupmember_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_reporting(state=None, save=False):
    '''
    Disables a reporting matching the specified filter.

    state(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.disable_reporting state=foo

    '''

    result = {}

    payload = {'reporting': {}}

    if state:
        payload['reporting']['state'] = state
    else:
        result['result'] = 'False'
        result['error'] = 'state value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/reporting?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_server(name=None, save=False):
    '''
    Disables a server matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.disable_server name=foo

    '''

    result = {}

    payload = {'server': {}}

    if name:
        payload['server']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/server?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_service(name=None, save=False):
    '''
    Disables a service matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.disable_service name=foo

    '''

    result = {}

    payload = {'service': {}}

    if name:
        payload['service']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/service?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_servicegroup(servicegroupname=None, save=False):
    '''
    Disables a servicegroup matching the specified filter.

    servicegroupname(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.disable_servicegroup servicegroupname=foo

    '''

    result = {}

    payload = {'servicegroup': {}}

    if servicegroupname:
        payload['servicegroup']['servicegroupname'] = servicegroupname
    else:
        result['result'] = 'False'
        result['error'] = 'servicegroupname value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/servicegroup?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_vserver(name=None, save=False):
    '''
    Disables a vserver matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.disable_vserver name=foo

    '''

    result = {}

    payload = {'vserver': {}}

    if name:
        payload['vserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/vserver?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_reporting(state=None, save=False):
    '''
    Enables a reporting matching the specified filter.

    state(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.enable_reporting state=foo

    '''

    result = {}

    payload = {'reporting': {}}

    if state:
        payload['reporting']['state'] = state
    else:
        result['result'] = 'False'
        result['error'] = 'state value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/reporting?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_server(name=None, save=False):
    '''
    Enables a server matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.enable_server name=foo

    '''

    result = {}

    payload = {'server': {}}

    if name:
        payload['server']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/server?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_service(name=None, save=False):
    '''
    Enables a service matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.enable_service name=foo

    '''

    result = {}

    payload = {'service': {}}

    if name:
        payload['service']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/service?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_servicegroup(servicegroupname=None, save=False):
    '''
    Enables a servicegroup matching the specified filter.

    servicegroupname(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.enable_servicegroup servicegroupname=foo

    '''

    result = {}

    payload = {'servicegroup': {}}

    if servicegroupname:
        payload['servicegroup']['servicegroupname'] = servicegroupname
    else:
        result['result'] = 'False'
        result['error'] = 'servicegroupname value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/servicegroup?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_vserver(name=None, save=False):
    '''
    Enables a vserver matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.enable_vserver name=foo

    '''

    result = {}

    payload = {'vserver': {}}

    if name:
        payload['vserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/vserver?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_extendedmemoryparam():
    '''
    Show the running configuration for the extendedmemoryparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_extendedmemoryparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/extendedmemoryparam'), 'extendedmemoryparam')

    return response


def get_location(ipfrom=None, ipto=None, preferredlocation=None, longitude=None, latitude=None):
    '''
    Show the running configuration for the location config key.

    ipfrom(str): Filters results that only match the ipfrom field.

    ipto(str): Filters results that only match the ipto field.

    preferredlocation(str): Filters results that only match the preferredlocation field.

    longitude(int): Filters results that only match the longitude field.

    latitude(int): Filters results that only match the latitude field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_location

    '''

    search_filter = []

    if ipfrom:
        search_filter.append(['ipfrom', ipfrom])

    if ipto:
        search_filter.append(['ipto', ipto])

    if preferredlocation:
        search_filter.append(['preferredlocation', preferredlocation])

    if longitude:
        search_filter.append(['longitude', longitude])

    if latitude:
        search_filter.append(['latitude', latitude])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/location{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'location')

    return response


def get_locationfile():
    '''
    Show the running configuration for the locationfile config key.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_locationfile

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/locationfile'), 'locationfile')

    return response


def get_locationfile6(locationfile=None, format=None, src=None):
    '''
    Show the running configuration for the locationfile6 config key.

    locationfile(str): Filters results that only match the Locationfile field.

    format(str): Filters results that only match the format field.

    src(str): Filters results that only match the src field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_locationfile6

    '''

    search_filter = []

    if locationfile:
        search_filter.append(['Locationfile', locationfile])

    if format:
        search_filter.append(['format', format])

    if src:
        search_filter.append(['src', src])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/locationfile6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'locationfile6')

    return response


def get_locationparameter():
    '''
    Show the running configuration for the locationparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_locationparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/locationparameter'), 'locationparameter')

    return response


def get_nstrace():
    '''
    Show the running configuration for the nstrace config key.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_nstrace

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/nstrace'), 'nstrace')

    return response


def get_radiusnode(nodeprefix=None, radkey=None):
    '''
    Show the running configuration for the radiusnode config key.

    nodeprefix(str): Filters results that only match the nodeprefix field.

    radkey(str): Filters results that only match the radkey field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_radiusnode

    '''

    search_filter = []

    if nodeprefix:
        search_filter.append(['nodeprefix', nodeprefix])

    if radkey:
        search_filter.append(['radkey', radkey])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/radiusnode{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'radiusnode')

    return response


def get_reporting():
    '''
    Show the running configuration for the reporting config key.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_reporting

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/reporting'), 'reporting')

    return response


def get_server(name=None, ipaddress=None, domain=None, translationip=None, translationmask=None, domainresolveretry=None,
               state=None, ipv6address=None, comment=None, td=None, domainresolvenow=None, delay=None, graceful=None,
               internal=None, newname=None):
    '''
    Show the running configuration for the server config key.

    name(str): Filters results that only match the name field.

    ipaddress(str): Filters results that only match the ipaddress field.

    domain(str): Filters results that only match the domain field.

    translationip(str): Filters results that only match the translationip field.

    translationmask(str): Filters results that only match the translationmask field.

    domainresolveretry(int): Filters results that only match the domainresolveretry field.

    state(str): Filters results that only match the state field.

    ipv6address(str): Filters results that only match the ipv6address field.

    comment(str): Filters results that only match the comment field.

    td(int): Filters results that only match the td field.

    domainresolvenow(bool): Filters results that only match the domainresolvenow field.

    delay(int): Filters results that only match the delay field.

    graceful(str): Filters results that only match the graceful field.

    internal(bool): Filters results that only match the Internal field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_server

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if domain:
        search_filter.append(['domain', domain])

    if translationip:
        search_filter.append(['translationip', translationip])

    if translationmask:
        search_filter.append(['translationmask', translationmask])

    if domainresolveretry:
        search_filter.append(['domainresolveretry', domainresolveretry])

    if state:
        search_filter.append(['state', state])

    if ipv6address:
        search_filter.append(['ipv6address', ipv6address])

    if comment:
        search_filter.append(['comment', comment])

    if td:
        search_filter.append(['td', td])

    if domainresolvenow:
        search_filter.append(['domainresolvenow', domainresolvenow])

    if delay:
        search_filter.append(['delay', delay])

    if graceful:
        search_filter.append(['graceful', graceful])

    if internal:
        search_filter.append(['Internal', internal])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/server{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'server')

    return response


def get_server_binding():
    '''
    Show the running configuration for the server_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_server_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/server_binding'), 'server_binding')

    return response


def get_server_gslbservice_binding(name=None, servicename=None):
    '''
    Show the running configuration for the server_gslbservice_binding config key.

    name(str): Filters results that only match the name field.

    servicename(str): Filters results that only match the servicename field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_server_gslbservice_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if servicename:
        search_filter.append(['servicename', servicename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/server_gslbservice_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'server_gslbservice_binding')

    return response


def get_server_service_binding(name=None, servicename=None):
    '''
    Show the running configuration for the server_service_binding config key.

    name(str): Filters results that only match the name field.

    servicename(str): Filters results that only match the servicename field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_server_service_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if servicename:
        search_filter.append(['servicename', servicename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/server_service_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'server_service_binding')

    return response


def get_server_servicegroup_binding(name=None, servicegroupname=None):
    '''
    Show the running configuration for the server_servicegroup_binding config key.

    name(str): Filters results that only match the name field.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_server_servicegroup_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/server_servicegroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'server_servicegroup_binding')

    return response


def get_service(name=None, ip=None, servername=None, servicetype=None, port=None, cleartextport=None, cachetype=None,
                maxclient=None, healthmonitor=None, maxreq=None, cacheable=None, cip=None, cipheader=None, usip=None,
                pathmonitor=None, pathmonitorindv=None, useproxyport=None, sc=None, sp=None, rtspsessionidremap=None,
                clttimeout=None, svrtimeout=None, customserverid=None, serverid=None, cka=None, tcpb=None, cmp=None,
                maxbandwidth=None, accessdown=None, monthreshold=None, state=None, downstateflush=None,
                tcpprofilename=None, httpprofilename=None, hashid=None, comment=None, appflowlog=None, netprofile=None,
                td=None, processlocal=None, dnsprofilename=None, monconnectionclose=None, ipaddress=None, weight=None,
                monitor_name_svc=None, riseapbrstatsmsgcode=None, delay=None, graceful=None, internal=None,
                newname=None):
    '''
    Show the running configuration for the service config key.

    name(str): Filters results that only match the name field.

    ip(str): Filters results that only match the ip field.

    servername(str): Filters results that only match the servername field.

    servicetype(str): Filters results that only match the servicetype field.

    port(int): Filters results that only match the port field.

    cleartextport(int): Filters results that only match the cleartextport field.

    cachetype(str): Filters results that only match the cachetype field.

    maxclient(int): Filters results that only match the maxclient field.

    healthmonitor(str): Filters results that only match the healthmonitor field.

    maxreq(int): Filters results that only match the maxreq field.

    cacheable(str): Filters results that only match the cacheable field.

    cip(str): Filters results that only match the cip field.

    cipheader(str): Filters results that only match the cipheader field.

    usip(str): Filters results that only match the usip field.

    pathmonitor(str): Filters results that only match the pathmonitor field.

    pathmonitorindv(str): Filters results that only match the pathmonitorindv field.

    useproxyport(str): Filters results that only match the useproxyport field.

    sc(str): Filters results that only match the sc field.

    sp(str): Filters results that only match the sp field.

    rtspsessionidremap(str): Filters results that only match the rtspsessionidremap field.

    clttimeout(int): Filters results that only match the clttimeout field.

    svrtimeout(int): Filters results that only match the svrtimeout field.

    customserverid(str): Filters results that only match the customserverid field.

    serverid(int): Filters results that only match the serverid field.

    cka(str): Filters results that only match the cka field.

    tcpb(str): Filters results that only match the tcpb field.

    cmp(str): Filters results that only match the cmp field.

    maxbandwidth(int): Filters results that only match the maxbandwidth field.

    accessdown(str): Filters results that only match the accessdown field.

    monthreshold(int): Filters results that only match the monthreshold field.

    state(str): Filters results that only match the state field.

    downstateflush(str): Filters results that only match the downstateflush field.

    tcpprofilename(str): Filters results that only match the tcpprofilename field.

    httpprofilename(str): Filters results that only match the httpprofilename field.

    hashid(int): Filters results that only match the hashid field.

    comment(str): Filters results that only match the comment field.

    appflowlog(str): Filters results that only match the appflowlog field.

    netprofile(str): Filters results that only match the netprofile field.

    td(int): Filters results that only match the td field.

    processlocal(str): Filters results that only match the processlocal field.

    dnsprofilename(str): Filters results that only match the dnsprofilename field.

    monconnectionclose(str): Filters results that only match the monconnectionclose field.

    ipaddress(str): Filters results that only match the ipaddress field.

    weight(int): Filters results that only match the weight field.

    monitor_name_svc(str): Filters results that only match the monitor_name_svc field.

    riseapbrstatsmsgcode(int): Filters results that only match the riseapbrstatsmsgcode field.

    delay(int): Filters results that only match the delay field.

    graceful(str): Filters results that only match the graceful field.

    internal(bool): Filters results that only match the Internal field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_service

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ip:
        search_filter.append(['ip', ip])

    if servername:
        search_filter.append(['servername', servername])

    if servicetype:
        search_filter.append(['servicetype', servicetype])

    if port:
        search_filter.append(['port', port])

    if cleartextport:
        search_filter.append(['cleartextport', cleartextport])

    if cachetype:
        search_filter.append(['cachetype', cachetype])

    if maxclient:
        search_filter.append(['maxclient', maxclient])

    if healthmonitor:
        search_filter.append(['healthmonitor', healthmonitor])

    if maxreq:
        search_filter.append(['maxreq', maxreq])

    if cacheable:
        search_filter.append(['cacheable', cacheable])

    if cip:
        search_filter.append(['cip', cip])

    if cipheader:
        search_filter.append(['cipheader', cipheader])

    if usip:
        search_filter.append(['usip', usip])

    if pathmonitor:
        search_filter.append(['pathmonitor', pathmonitor])

    if pathmonitorindv:
        search_filter.append(['pathmonitorindv', pathmonitorindv])

    if useproxyport:
        search_filter.append(['useproxyport', useproxyport])

    if sc:
        search_filter.append(['sc', sc])

    if sp:
        search_filter.append(['sp', sp])

    if rtspsessionidremap:
        search_filter.append(['rtspsessionidremap', rtspsessionidremap])

    if clttimeout:
        search_filter.append(['clttimeout', clttimeout])

    if svrtimeout:
        search_filter.append(['svrtimeout', svrtimeout])

    if customserverid:
        search_filter.append(['customserverid', customserverid])

    if serverid:
        search_filter.append(['serverid', serverid])

    if cka:
        search_filter.append(['cka', cka])

    if tcpb:
        search_filter.append(['tcpb', tcpb])

    if cmp:
        search_filter.append(['cmp', cmp])

    if maxbandwidth:
        search_filter.append(['maxbandwidth', maxbandwidth])

    if accessdown:
        search_filter.append(['accessdown', accessdown])

    if monthreshold:
        search_filter.append(['monthreshold', monthreshold])

    if state:
        search_filter.append(['state', state])

    if downstateflush:
        search_filter.append(['downstateflush', downstateflush])

    if tcpprofilename:
        search_filter.append(['tcpprofilename', tcpprofilename])

    if httpprofilename:
        search_filter.append(['httpprofilename', httpprofilename])

    if hashid:
        search_filter.append(['hashid', hashid])

    if comment:
        search_filter.append(['comment', comment])

    if appflowlog:
        search_filter.append(['appflowlog', appflowlog])

    if netprofile:
        search_filter.append(['netprofile', netprofile])

    if td:
        search_filter.append(['td', td])

    if processlocal:
        search_filter.append(['processlocal', processlocal])

    if dnsprofilename:
        search_filter.append(['dnsprofilename', dnsprofilename])

    if monconnectionclose:
        search_filter.append(['monconnectionclose', monconnectionclose])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if weight:
        search_filter.append(['weight', weight])

    if monitor_name_svc:
        search_filter.append(['monitor_name_svc', monitor_name_svc])

    if riseapbrstatsmsgcode:
        search_filter.append(['riseapbrstatsmsgcode', riseapbrstatsmsgcode])

    if delay:
        search_filter.append(['delay', delay])

    if graceful:
        search_filter.append(['graceful', graceful])

    if internal:
        search_filter.append(['Internal', internal])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/service{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'service')

    return response


def get_service_binding():
    '''
    Show the running configuration for the service_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_service_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/service_binding'), 'service_binding')

    return response


def get_service_dospolicy_binding(policyname=None, name=None):
    '''
    Show the running configuration for the service_dospolicy_binding config key.

    policyname(str): Filters results that only match the policyname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_service_dospolicy_binding

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/service_dospolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'service_dospolicy_binding')

    return response


def get_service_lbmonitor_binding(weight=None, name=None, passive=None, monitor_name=None, monstate=None):
    '''
    Show the running configuration for the service_lbmonitor_binding config key.

    weight(int): Filters results that only match the weight field.

    name(str): Filters results that only match the name field.

    passive(bool): Filters results that only match the passive field.

    monitor_name(str): Filters results that only match the monitor_name field.

    monstate(str): Filters results that only match the monstate field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_service_lbmonitor_binding

    '''

    search_filter = []

    if weight:
        search_filter.append(['weight', weight])

    if name:
        search_filter.append(['name', name])

    if passive:
        search_filter.append(['passive', passive])

    if monitor_name:
        search_filter.append(['monitor_name', monitor_name])

    if monstate:
        search_filter.append(['monstate', monstate])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/service_lbmonitor_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'service_lbmonitor_binding')

    return response


def get_service_scpolicy_binding(policyname=None, name=None):
    '''
    Show the running configuration for the service_scpolicy_binding config key.

    policyname(str): Filters results that only match the policyname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_service_scpolicy_binding

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/service_scpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'service_scpolicy_binding')

    return response


def get_servicegroup(servicegroupname=None, servicetype=None, cachetype=None, td=None, maxclient=None, maxreq=None,
                     cacheable=None, cip=None, cipheader=None, usip=None, pathmonitor=None, pathmonitorindv=None,
                     useproxyport=None, healthmonitor=None, sc=None, sp=None, rtspsessionidremap=None, clttimeout=None,
                     svrtimeout=None, cka=None, tcpb=None, cmp=None, maxbandwidth=None, monthreshold=None, state=None,
                     downstateflush=None, tcpprofilename=None, httpprofilename=None, comment=None, appflowlog=None,
                     netprofile=None, autoscale=None, memberport=None, monconnectionclose=None, servername=None,
                     port=None, weight=None, customserverid=None, serverid=None, hashid=None, monitor_name_svc=None,
                     dup_weight=None, riseapbrstatsmsgcode=None, delay=None, graceful=None, includemembers=None,
                     newname=None):
    '''
    Show the running configuration for the servicegroup config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    servicetype(str): Filters results that only match the servicetype field.

    cachetype(str): Filters results that only match the cachetype field.

    td(int): Filters results that only match the td field.

    maxclient(int): Filters results that only match the maxclient field.

    maxreq(int): Filters results that only match the maxreq field.

    cacheable(str): Filters results that only match the cacheable field.

    cip(str): Filters results that only match the cip field.

    cipheader(str): Filters results that only match the cipheader field.

    usip(str): Filters results that only match the usip field.

    pathmonitor(str): Filters results that only match the pathmonitor field.

    pathmonitorindv(str): Filters results that only match the pathmonitorindv field.

    useproxyport(str): Filters results that only match the useproxyport field.

    healthmonitor(str): Filters results that only match the healthmonitor field.

    sc(str): Filters results that only match the sc field.

    sp(str): Filters results that only match the sp field.

    rtspsessionidremap(str): Filters results that only match the rtspsessionidremap field.

    clttimeout(int): Filters results that only match the clttimeout field.

    svrtimeout(int): Filters results that only match the svrtimeout field.

    cka(str): Filters results that only match the cka field.

    tcpb(str): Filters results that only match the tcpb field.

    cmp(str): Filters results that only match the cmp field.

    maxbandwidth(int): Filters results that only match the maxbandwidth field.

    monthreshold(int): Filters results that only match the monthreshold field.

    state(str): Filters results that only match the state field.

    downstateflush(str): Filters results that only match the downstateflush field.

    tcpprofilename(str): Filters results that only match the tcpprofilename field.

    httpprofilename(str): Filters results that only match the httpprofilename field.

    comment(str): Filters results that only match the comment field.

    appflowlog(str): Filters results that only match the appflowlog field.

    netprofile(str): Filters results that only match the netprofile field.

    autoscale(str): Filters results that only match the autoscale field.

    memberport(int): Filters results that only match the memberport field.

    monconnectionclose(str): Filters results that only match the monconnectionclose field.

    servername(str): Filters results that only match the servername field.

    port(int): Filters results that only match the port field.

    weight(int): Filters results that only match the weight field.

    customserverid(str): Filters results that only match the customserverid field.

    serverid(int): Filters results that only match the serverid field.

    hashid(int): Filters results that only match the hashid field.

    monitor_name_svc(str): Filters results that only match the monitor_name_svc field.

    dup_weight(int): Filters results that only match the dup_weight field.

    riseapbrstatsmsgcode(int): Filters results that only match the riseapbrstatsmsgcode field.

    delay(int): Filters results that only match the delay field.

    graceful(str): Filters results that only match the graceful field.

    includemembers(bool): Filters results that only match the includemembers field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_servicegroup

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if servicetype:
        search_filter.append(['servicetype', servicetype])

    if cachetype:
        search_filter.append(['cachetype', cachetype])

    if td:
        search_filter.append(['td', td])

    if maxclient:
        search_filter.append(['maxclient', maxclient])

    if maxreq:
        search_filter.append(['maxreq', maxreq])

    if cacheable:
        search_filter.append(['cacheable', cacheable])

    if cip:
        search_filter.append(['cip', cip])

    if cipheader:
        search_filter.append(['cipheader', cipheader])

    if usip:
        search_filter.append(['usip', usip])

    if pathmonitor:
        search_filter.append(['pathmonitor', pathmonitor])

    if pathmonitorindv:
        search_filter.append(['pathmonitorindv', pathmonitorindv])

    if useproxyport:
        search_filter.append(['useproxyport', useproxyport])

    if healthmonitor:
        search_filter.append(['healthmonitor', healthmonitor])

    if sc:
        search_filter.append(['sc', sc])

    if sp:
        search_filter.append(['sp', sp])

    if rtspsessionidremap:
        search_filter.append(['rtspsessionidremap', rtspsessionidremap])

    if clttimeout:
        search_filter.append(['clttimeout', clttimeout])

    if svrtimeout:
        search_filter.append(['svrtimeout', svrtimeout])

    if cka:
        search_filter.append(['cka', cka])

    if tcpb:
        search_filter.append(['tcpb', tcpb])

    if cmp:
        search_filter.append(['cmp', cmp])

    if maxbandwidth:
        search_filter.append(['maxbandwidth', maxbandwidth])

    if monthreshold:
        search_filter.append(['monthreshold', monthreshold])

    if state:
        search_filter.append(['state', state])

    if downstateflush:
        search_filter.append(['downstateflush', downstateflush])

    if tcpprofilename:
        search_filter.append(['tcpprofilename', tcpprofilename])

    if httpprofilename:
        search_filter.append(['httpprofilename', httpprofilename])

    if comment:
        search_filter.append(['comment', comment])

    if appflowlog:
        search_filter.append(['appflowlog', appflowlog])

    if netprofile:
        search_filter.append(['netprofile', netprofile])

    if autoscale:
        search_filter.append(['autoscale', autoscale])

    if memberport:
        search_filter.append(['memberport', memberport])

    if monconnectionclose:
        search_filter.append(['monconnectionclose', monconnectionclose])

    if servername:
        search_filter.append(['servername', servername])

    if port:
        search_filter.append(['port', port])

    if weight:
        search_filter.append(['weight', weight])

    if customserverid:
        search_filter.append(['customserverid', customserverid])

    if serverid:
        search_filter.append(['serverid', serverid])

    if hashid:
        search_filter.append(['hashid', hashid])

    if monitor_name_svc:
        search_filter.append(['monitor_name_svc', monitor_name_svc])

    if dup_weight:
        search_filter.append(['dup_weight', dup_weight])

    if riseapbrstatsmsgcode:
        search_filter.append(['riseapbrstatsmsgcode', riseapbrstatsmsgcode])

    if delay:
        search_filter.append(['delay', delay])

    if graceful:
        search_filter.append(['graceful', graceful])

    if includemembers:
        search_filter.append(['includemembers', includemembers])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/servicegroup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'servicegroup')

    return response


def get_servicegroup_binding():
    '''
    Show the running configuration for the servicegroup_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_servicegroup_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/servicegroup_binding'), 'servicegroup_binding')

    return response


def get_servicegroup_lbmonitor_binding(servicegroupname=None, port=None, state=None, hashid=None, serverid=None,
                                       customserverid=None, weight=None, monitor_name=None, passive=None,
                                       monstate=None):
    '''
    Show the running configuration for the servicegroup_lbmonitor_binding config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    port(int): Filters results that only match the port field.

    state(str): Filters results that only match the state field.

    hashid(int): Filters results that only match the hashid field.

    serverid(int): Filters results that only match the serverid field.

    customserverid(str): Filters results that only match the customserverid field.

    weight(int): Filters results that only match the weight field.

    monitor_name(str): Filters results that only match the monitor_name field.

    passive(bool): Filters results that only match the passive field.

    monstate(str): Filters results that only match the monstate field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_servicegroup_lbmonitor_binding

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if port:
        search_filter.append(['port', port])

    if state:
        search_filter.append(['state', state])

    if hashid:
        search_filter.append(['hashid', hashid])

    if serverid:
        search_filter.append(['serverid', serverid])

    if customserverid:
        search_filter.append(['customserverid', customserverid])

    if weight:
        search_filter.append(['weight', weight])

    if monitor_name:
        search_filter.append(['monitor_name', monitor_name])

    if passive:
        search_filter.append(['passive', passive])

    if monstate:
        search_filter.append(['monstate', monstate])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/servicegroup_lbmonitor_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'servicegroup_lbmonitor_binding')

    return response


def get_servicegroup_servicegroupentitymonbindings_binding(servicegroupname=None, servicegroupentname2=None, port=None,
                                                           state=None, hashid=None, serverid=None, customserverid=None,
                                                           weight=None, monitor_name=None, passive=None):
    '''
    Show the running configuration for the servicegroup_servicegroupentitymonbindings_binding config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    servicegroupentname2(str): Filters results that only match the servicegroupentname2 field.

    port(int): Filters results that only match the port field.

    state(str): Filters results that only match the state field.

    hashid(int): Filters results that only match the hashid field.

    serverid(int): Filters results that only match the serverid field.

    customserverid(str): Filters results that only match the customserverid field.

    weight(int): Filters results that only match the weight field.

    monitor_name(str): Filters results that only match the monitor_name field.

    passive(bool): Filters results that only match the passive field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_servicegroup_servicegroupentitymonbindings_binding

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if servicegroupentname2:
        search_filter.append(['servicegroupentname2', servicegroupentname2])

    if port:
        search_filter.append(['port', port])

    if state:
        search_filter.append(['state', state])

    if hashid:
        search_filter.append(['hashid', hashid])

    if serverid:
        search_filter.append(['serverid', serverid])

    if customserverid:
        search_filter.append(['customserverid', customserverid])

    if weight:
        search_filter.append(['weight', weight])

    if monitor_name:
        search_filter.append(['monitor_name', monitor_name])

    if passive:
        search_filter.append(['passive', passive])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/servicegroup_servicegroupentitymonbindings_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'servicegroup_servicegroupentitymonbindings_binding')

    return response


def get_servicegroup_servicegroupmember_binding(servicegroupname=None, ip=None, port=None, state=None, hashid=None,
                                                serverid=None, servername=None, customserverid=None, weight=None):
    '''
    Show the running configuration for the servicegroup_servicegroupmember_binding config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    ip(str): Filters results that only match the ip field.

    port(int): Filters results that only match the port field.

    state(str): Filters results that only match the state field.

    hashid(int): Filters results that only match the hashid field.

    serverid(int): Filters results that only match the serverid field.

    servername(str): Filters results that only match the servername field.

    customserverid(str): Filters results that only match the customserverid field.

    weight(int): Filters results that only match the weight field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_servicegroup_servicegroupmember_binding

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if ip:
        search_filter.append(['ip', ip])

    if port:
        search_filter.append(['port', port])

    if state:
        search_filter.append(['state', state])

    if hashid:
        search_filter.append(['hashid', hashid])

    if serverid:
        search_filter.append(['serverid', serverid])

    if servername:
        search_filter.append(['servername', servername])

    if customserverid:
        search_filter.append(['customserverid', customserverid])

    if weight:
        search_filter.append(['weight', weight])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/servicegroup_servicegroupmember_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'servicegroup_servicegroupmember_binding')

    return response


def get_servicegroupbindings(servicegroupname=None):
    '''
    Show the running configuration for the servicegroupbindings config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_servicegroupbindings

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/servicegroupbindings{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'servicegroupbindings')

    return response


def get_svcbindings(servicename=None):
    '''
    Show the running configuration for the svcbindings config key.

    servicename(str): Filters results that only match the servicename field.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.get_svcbindings

    '''

    search_filter = []

    if servicename:
        search_filter.append(['servicename', servicename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/svcbindings{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'svcbindings')

    return response


def unset_extendedmemoryparam(memlimit=None, save=False):
    '''
    Unsets values from the extendedmemoryparam configuration key.

    memlimit(bool): Unsets the memlimit value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.unset_extendedmemoryparam <args>

    '''

    result = {}

    payload = {'extendedmemoryparam': {}}

    if memlimit:
        payload['extendedmemoryparam']['memlimit'] = True

    execution = __proxy__['citrixns.post']('config/extendedmemoryparam?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_locationparameter(context=None, q1label=None, q2label=None, q3label=None, q4label=None, q5label=None,
                            q6label=None, save=False):
    '''
    Unsets values from the locationparameter configuration key.

    context(bool): Unsets the context value.

    q1label(bool): Unsets the q1label value.

    q2label(bool): Unsets the q2label value.

    q3label(bool): Unsets the q3label value.

    q4label(bool): Unsets the q4label value.

    q5label(bool): Unsets the q5label value.

    q6label(bool): Unsets the q6label value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.unset_locationparameter <args>

    '''

    result = {}

    payload = {'locationparameter': {}}

    if context:
        payload['locationparameter']['context'] = True

    if q1label:
        payload['locationparameter']['q1label'] = True

    if q2label:
        payload['locationparameter']['q2label'] = True

    if q3label:
        payload['locationparameter']['q3label'] = True

    if q4label:
        payload['locationparameter']['q4label'] = True

    if q5label:
        payload['locationparameter']['q5label'] = True

    if q6label:
        payload['locationparameter']['q6label'] = True

    execution = __proxy__['citrixns.post']('config/locationparameter?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_server(name=None, ipaddress=None, domain=None, translationip=None, translationmask=None,
                 domainresolveretry=None, state=None, ipv6address=None, comment=None, td=None, domainresolvenow=None,
                 delay=None, graceful=None, internal=None, newname=None, save=False):
    '''
    Unsets values from the server configuration key.

    name(bool): Unsets the name value.

    ipaddress(bool): Unsets the ipaddress value.

    domain(bool): Unsets the domain value.

    translationip(bool): Unsets the translationip value.

    translationmask(bool): Unsets the translationmask value.

    domainresolveretry(bool): Unsets the domainresolveretry value.

    state(bool): Unsets the state value.

    ipv6address(bool): Unsets the ipv6address value.

    comment(bool): Unsets the comment value.

    td(bool): Unsets the td value.

    domainresolvenow(bool): Unsets the domainresolvenow value.

    delay(bool): Unsets the delay value.

    graceful(bool): Unsets the graceful value.

    internal(bool): Unsets the internal value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.unset_server <args>

    '''

    result = {}

    payload = {'server': {}}

    if name:
        payload['server']['name'] = True

    if ipaddress:
        payload['server']['ipaddress'] = True

    if domain:
        payload['server']['domain'] = True

    if translationip:
        payload['server']['translationip'] = True

    if translationmask:
        payload['server']['translationmask'] = True

    if domainresolveretry:
        payload['server']['domainresolveretry'] = True

    if state:
        payload['server']['state'] = True

    if ipv6address:
        payload['server']['ipv6address'] = True

    if comment:
        payload['server']['comment'] = True

    if td:
        payload['server']['td'] = True

    if domainresolvenow:
        payload['server']['domainresolvenow'] = True

    if delay:
        payload['server']['delay'] = True

    if graceful:
        payload['server']['graceful'] = True

    if internal:
        payload['server']['Internal'] = True

    if newname:
        payload['server']['newname'] = True

    execution = __proxy__['citrixns.post']('config/server?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_service(name=None, ip=None, servername=None, servicetype=None, port=None, cleartextport=None, cachetype=None,
                  maxclient=None, healthmonitor=None, maxreq=None, cacheable=None, cip=None, cipheader=None, usip=None,
                  pathmonitor=None, pathmonitorindv=None, useproxyport=None, sc=None, sp=None, rtspsessionidremap=None,
                  clttimeout=None, svrtimeout=None, customserverid=None, serverid=None, cka=None, tcpb=None, cmp=None,
                  maxbandwidth=None, accessdown=None, monthreshold=None, state=None, downstateflush=None,
                  tcpprofilename=None, httpprofilename=None, hashid=None, comment=None, appflowlog=None, netprofile=None,
                  td=None, processlocal=None, dnsprofilename=None, monconnectionclose=None, ipaddress=None, weight=None,
                  monitor_name_svc=None, riseapbrstatsmsgcode=None, delay=None, graceful=None, internal=None,
                  newname=None, save=False):
    '''
    Unsets values from the service configuration key.

    name(bool): Unsets the name value.

    ip(bool): Unsets the ip value.

    servername(bool): Unsets the servername value.

    servicetype(bool): Unsets the servicetype value.

    port(bool): Unsets the port value.

    cleartextport(bool): Unsets the cleartextport value.

    cachetype(bool): Unsets the cachetype value.

    maxclient(bool): Unsets the maxclient value.

    healthmonitor(bool): Unsets the healthmonitor value.

    maxreq(bool): Unsets the maxreq value.

    cacheable(bool): Unsets the cacheable value.

    cip(bool): Unsets the cip value.

    cipheader(bool): Unsets the cipheader value.

    usip(bool): Unsets the usip value.

    pathmonitor(bool): Unsets the pathmonitor value.

    pathmonitorindv(bool): Unsets the pathmonitorindv value.

    useproxyport(bool): Unsets the useproxyport value.

    sc(bool): Unsets the sc value.

    sp(bool): Unsets the sp value.

    rtspsessionidremap(bool): Unsets the rtspsessionidremap value.

    clttimeout(bool): Unsets the clttimeout value.

    svrtimeout(bool): Unsets the svrtimeout value.

    customserverid(bool): Unsets the customserverid value.

    serverid(bool): Unsets the serverid value.

    cka(bool): Unsets the cka value.

    tcpb(bool): Unsets the tcpb value.

    cmp(bool): Unsets the cmp value.

    maxbandwidth(bool): Unsets the maxbandwidth value.

    accessdown(bool): Unsets the accessdown value.

    monthreshold(bool): Unsets the monthreshold value.

    state(bool): Unsets the state value.

    downstateflush(bool): Unsets the downstateflush value.

    tcpprofilename(bool): Unsets the tcpprofilename value.

    httpprofilename(bool): Unsets the httpprofilename value.

    hashid(bool): Unsets the hashid value.

    comment(bool): Unsets the comment value.

    appflowlog(bool): Unsets the appflowlog value.

    netprofile(bool): Unsets the netprofile value.

    td(bool): Unsets the td value.

    processlocal(bool): Unsets the processlocal value.

    dnsprofilename(bool): Unsets the dnsprofilename value.

    monconnectionclose(bool): Unsets the monconnectionclose value.

    ipaddress(bool): Unsets the ipaddress value.

    weight(bool): Unsets the weight value.

    monitor_name_svc(bool): Unsets the monitor_name_svc value.

    riseapbrstatsmsgcode(bool): Unsets the riseapbrstatsmsgcode value.

    delay(bool): Unsets the delay value.

    graceful(bool): Unsets the graceful value.

    internal(bool): Unsets the internal value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.unset_service <args>

    '''

    result = {}

    payload = {'service': {}}

    if name:
        payload['service']['name'] = True

    if ip:
        payload['service']['ip'] = True

    if servername:
        payload['service']['servername'] = True

    if servicetype:
        payload['service']['servicetype'] = True

    if port:
        payload['service']['port'] = True

    if cleartextport:
        payload['service']['cleartextport'] = True

    if cachetype:
        payload['service']['cachetype'] = True

    if maxclient:
        payload['service']['maxclient'] = True

    if healthmonitor:
        payload['service']['healthmonitor'] = True

    if maxreq:
        payload['service']['maxreq'] = True

    if cacheable:
        payload['service']['cacheable'] = True

    if cip:
        payload['service']['cip'] = True

    if cipheader:
        payload['service']['cipheader'] = True

    if usip:
        payload['service']['usip'] = True

    if pathmonitor:
        payload['service']['pathmonitor'] = True

    if pathmonitorindv:
        payload['service']['pathmonitorindv'] = True

    if useproxyport:
        payload['service']['useproxyport'] = True

    if sc:
        payload['service']['sc'] = True

    if sp:
        payload['service']['sp'] = True

    if rtspsessionidremap:
        payload['service']['rtspsessionidremap'] = True

    if clttimeout:
        payload['service']['clttimeout'] = True

    if svrtimeout:
        payload['service']['svrtimeout'] = True

    if customserverid:
        payload['service']['customserverid'] = True

    if serverid:
        payload['service']['serverid'] = True

    if cka:
        payload['service']['cka'] = True

    if tcpb:
        payload['service']['tcpb'] = True

    if cmp:
        payload['service']['cmp'] = True

    if maxbandwidth:
        payload['service']['maxbandwidth'] = True

    if accessdown:
        payload['service']['accessdown'] = True

    if monthreshold:
        payload['service']['monthreshold'] = True

    if state:
        payload['service']['state'] = True

    if downstateflush:
        payload['service']['downstateflush'] = True

    if tcpprofilename:
        payload['service']['tcpprofilename'] = True

    if httpprofilename:
        payload['service']['httpprofilename'] = True

    if hashid:
        payload['service']['hashid'] = True

    if comment:
        payload['service']['comment'] = True

    if appflowlog:
        payload['service']['appflowlog'] = True

    if netprofile:
        payload['service']['netprofile'] = True

    if td:
        payload['service']['td'] = True

    if processlocal:
        payload['service']['processlocal'] = True

    if dnsprofilename:
        payload['service']['dnsprofilename'] = True

    if monconnectionclose:
        payload['service']['monconnectionclose'] = True

    if ipaddress:
        payload['service']['ipaddress'] = True

    if weight:
        payload['service']['weight'] = True

    if monitor_name_svc:
        payload['service']['monitor_name_svc'] = True

    if riseapbrstatsmsgcode:
        payload['service']['riseapbrstatsmsgcode'] = True

    if delay:
        payload['service']['delay'] = True

    if graceful:
        payload['service']['graceful'] = True

    if internal:
        payload['service']['Internal'] = True

    if newname:
        payload['service']['newname'] = True

    execution = __proxy__['citrixns.post']('config/service?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_servicegroup(servicegroupname=None, servicetype=None, cachetype=None, td=None, maxclient=None, maxreq=None,
                       cacheable=None, cip=None, cipheader=None, usip=None, pathmonitor=None, pathmonitorindv=None,
                       useproxyport=None, healthmonitor=None, sc=None, sp=None, rtspsessionidremap=None, clttimeout=None,
                       svrtimeout=None, cka=None, tcpb=None, cmp=None, maxbandwidth=None, monthreshold=None, state=None,
                       downstateflush=None, tcpprofilename=None, httpprofilename=None, comment=None, appflowlog=None,
                       netprofile=None, autoscale=None, memberport=None, monconnectionclose=None, servername=None,
                       port=None, weight=None, customserverid=None, serverid=None, hashid=None, monitor_name_svc=None,
                       dup_weight=None, riseapbrstatsmsgcode=None, delay=None, graceful=None, includemembers=None,
                       newname=None, save=False):
    '''
    Unsets values from the servicegroup configuration key.

    servicegroupname(bool): Unsets the servicegroupname value.

    servicetype(bool): Unsets the servicetype value.

    cachetype(bool): Unsets the cachetype value.

    td(bool): Unsets the td value.

    maxclient(bool): Unsets the maxclient value.

    maxreq(bool): Unsets the maxreq value.

    cacheable(bool): Unsets the cacheable value.

    cip(bool): Unsets the cip value.

    cipheader(bool): Unsets the cipheader value.

    usip(bool): Unsets the usip value.

    pathmonitor(bool): Unsets the pathmonitor value.

    pathmonitorindv(bool): Unsets the pathmonitorindv value.

    useproxyport(bool): Unsets the useproxyport value.

    healthmonitor(bool): Unsets the healthmonitor value.

    sc(bool): Unsets the sc value.

    sp(bool): Unsets the sp value.

    rtspsessionidremap(bool): Unsets the rtspsessionidremap value.

    clttimeout(bool): Unsets the clttimeout value.

    svrtimeout(bool): Unsets the svrtimeout value.

    cka(bool): Unsets the cka value.

    tcpb(bool): Unsets the tcpb value.

    cmp(bool): Unsets the cmp value.

    maxbandwidth(bool): Unsets the maxbandwidth value.

    monthreshold(bool): Unsets the monthreshold value.

    state(bool): Unsets the state value.

    downstateflush(bool): Unsets the downstateflush value.

    tcpprofilename(bool): Unsets the tcpprofilename value.

    httpprofilename(bool): Unsets the httpprofilename value.

    comment(bool): Unsets the comment value.

    appflowlog(bool): Unsets the appflowlog value.

    netprofile(bool): Unsets the netprofile value.

    autoscale(bool): Unsets the autoscale value.

    memberport(bool): Unsets the memberport value.

    monconnectionclose(bool): Unsets the monconnectionclose value.

    servername(bool): Unsets the servername value.

    port(bool): Unsets the port value.

    weight(bool): Unsets the weight value.

    customserverid(bool): Unsets the customserverid value.

    serverid(bool): Unsets the serverid value.

    hashid(bool): Unsets the hashid value.

    monitor_name_svc(bool): Unsets the monitor_name_svc value.

    dup_weight(bool): Unsets the dup_weight value.

    riseapbrstatsmsgcode(bool): Unsets the riseapbrstatsmsgcode value.

    delay(bool): Unsets the delay value.

    graceful(bool): Unsets the graceful value.

    includemembers(bool): Unsets the includemembers value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.unset_servicegroup <args>

    '''

    result = {}

    payload = {'servicegroup': {}}

    if servicegroupname:
        payload['servicegroup']['servicegroupname'] = True

    if servicetype:
        payload['servicegroup']['servicetype'] = True

    if cachetype:
        payload['servicegroup']['cachetype'] = True

    if td:
        payload['servicegroup']['td'] = True

    if maxclient:
        payload['servicegroup']['maxclient'] = True

    if maxreq:
        payload['servicegroup']['maxreq'] = True

    if cacheable:
        payload['servicegroup']['cacheable'] = True

    if cip:
        payload['servicegroup']['cip'] = True

    if cipheader:
        payload['servicegroup']['cipheader'] = True

    if usip:
        payload['servicegroup']['usip'] = True

    if pathmonitor:
        payload['servicegroup']['pathmonitor'] = True

    if pathmonitorindv:
        payload['servicegroup']['pathmonitorindv'] = True

    if useproxyport:
        payload['servicegroup']['useproxyport'] = True

    if healthmonitor:
        payload['servicegroup']['healthmonitor'] = True

    if sc:
        payload['servicegroup']['sc'] = True

    if sp:
        payload['servicegroup']['sp'] = True

    if rtspsessionidremap:
        payload['servicegroup']['rtspsessionidremap'] = True

    if clttimeout:
        payload['servicegroup']['clttimeout'] = True

    if svrtimeout:
        payload['servicegroup']['svrtimeout'] = True

    if cka:
        payload['servicegroup']['cka'] = True

    if tcpb:
        payload['servicegroup']['tcpb'] = True

    if cmp:
        payload['servicegroup']['cmp'] = True

    if maxbandwidth:
        payload['servicegroup']['maxbandwidth'] = True

    if monthreshold:
        payload['servicegroup']['monthreshold'] = True

    if state:
        payload['servicegroup']['state'] = True

    if downstateflush:
        payload['servicegroup']['downstateflush'] = True

    if tcpprofilename:
        payload['servicegroup']['tcpprofilename'] = True

    if httpprofilename:
        payload['servicegroup']['httpprofilename'] = True

    if comment:
        payload['servicegroup']['comment'] = True

    if appflowlog:
        payload['servicegroup']['appflowlog'] = True

    if netprofile:
        payload['servicegroup']['netprofile'] = True

    if autoscale:
        payload['servicegroup']['autoscale'] = True

    if memberport:
        payload['servicegroup']['memberport'] = True

    if monconnectionclose:
        payload['servicegroup']['monconnectionclose'] = True

    if servername:
        payload['servicegroup']['servername'] = True

    if port:
        payload['servicegroup']['port'] = True

    if weight:
        payload['servicegroup']['weight'] = True

    if customserverid:
        payload['servicegroup']['customserverid'] = True

    if serverid:
        payload['servicegroup']['serverid'] = True

    if hashid:
        payload['servicegroup']['hashid'] = True

    if monitor_name_svc:
        payload['servicegroup']['monitor_name_svc'] = True

    if dup_weight:
        payload['servicegroup']['dup_weight'] = True

    if riseapbrstatsmsgcode:
        payload['servicegroup']['riseapbrstatsmsgcode'] = True

    if delay:
        payload['servicegroup']['delay'] = True

    if graceful:
        payload['servicegroup']['graceful'] = True

    if includemembers:
        payload['servicegroup']['includemembers'] = True

    if newname:
        payload['servicegroup']['newname'] = True

    execution = __proxy__['citrixns.post']('config/servicegroup?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_extendedmemoryparam(memlimit=None, save=False):
    '''
    Update the running configuration for the extendedmemoryparam config key.

    memlimit(int): Amount of NetScaler memory to reserve for the memory used by LSN and Subscriber Session Store feature, in
        multiples of 2MB.  Note: If you later reduce the value of this parameter, the amount of active memory is not
        reduced. Changing the configured memory limit can only increase the amount of active memory.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.update_extendedmemoryparam <args>

    '''

    result = {}

    payload = {'extendedmemoryparam': {}}

    if memlimit:
        payload['extendedmemoryparam']['memlimit'] = memlimit

    execution = __proxy__['citrixns.put']('config/extendedmemoryparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_locationparameter(context=None, q1label=None, q2label=None, q3label=None, q4label=None, q5label=None,
                             q6label=None, save=False):
    '''
    Update the running configuration for the locationparameter config key.

    context(str): Context for describing locations. In geographic context, qualifier labels are assigned by default in the
        following sequence: Continent.Country.Region.City.ISP.Organization. In custom context, the qualifiers labels can
        have any meaning that you designate. Possible values = geographic, custom

    q1label(str): Label specifying the meaning of the first qualifier. Can be specified for custom context only. Minimum
        length = 1

    q2label(str): Label specifying the meaning of the second qualifier. Can be specified for custom context only. Minimum
        length = 1

    q3label(str): Label specifying the meaning of the third qualifier. Can be specified for custom context only. Minimum
        length = 1

    q4label(str): Label specifying the meaning of the fourth qualifier. Can be specified for custom context only. Minimum
        length = 1

    q5label(str): Label specifying the meaning of the fifth qualifier. Can be specified for custom context only. Minimum
        length = 1

    q6label(str): Label specifying the meaning of the sixth qualifier. Can be specified for custom context only. Minimum
        length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.update_locationparameter <args>

    '''

    result = {}

    payload = {'locationparameter': {}}

    if context:
        payload['locationparameter']['context'] = context

    if q1label:
        payload['locationparameter']['q1label'] = q1label

    if q2label:
        payload['locationparameter']['q2label'] = q2label

    if q3label:
        payload['locationparameter']['q3label'] = q3label

    if q4label:
        payload['locationparameter']['q4label'] = q4label

    if q5label:
        payload['locationparameter']['q5label'] = q5label

    if q6label:
        payload['locationparameter']['q6label'] = q6label

    execution = __proxy__['citrixns.put']('config/locationparameter', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_radiusnode(nodeprefix=None, radkey=None, save=False):
    '''
    Update the running configuration for the radiusnode config key.

    nodeprefix(str): IP address/IP prefix of radius node in CIDR format.

    radkey(str): The key shared between the RADIUS server and clients.  Required for NetScaler appliance to communicate with
        the RADIUS nodes.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.update_radiusnode <args>

    '''

    result = {}

    payload = {'radiusnode': {}}

    if nodeprefix:
        payload['radiusnode']['nodeprefix'] = nodeprefix

    if radkey:
        payload['radiusnode']['radkey'] = radkey

    execution = __proxy__['citrixns.put']('config/radiusnode', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_server(name=None, ipaddress=None, domain=None, translationip=None, translationmask=None,
                  domainresolveretry=None, state=None, ipv6address=None, comment=None, td=None, domainresolvenow=None,
                  delay=None, graceful=None, internal=None, newname=None, save=False):
    '''
    Update the running configuration for the server config key.

    name(str): Name for the server.  Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Can be changed after the name is created. Minimum length = 1

    ipaddress(str): IPv4 or IPv6 address of the server. If you create an IP address based server, you can specify the name of
        the server, instead of its IP address, when creating a service. Note: If you do not create a server entry, the
        server IP address that you enter when you create a service becomes the name of the server.

    domain(str): Domain name of the server. For a domain based configuration, you must create the server first. Minimum
        length = 1

    translationip(str): IP address used to transform the servers DNS-resolved IP address.

    translationmask(str): The netmask of the translation ip.

    domainresolveretry(int): Time, in seconds, for which the NetScaler appliance must wait, after DNS resolution fails,
        before sending the next DNS query to resolve the domain name. Default value: 5 Minimum value = 5 Maximum value =
        20939

    state(str): Initial state of the server. Default value: ENABLED Possible values = ENABLED, DISABLED

    ipv6address(str): Support IPv6 addressing mode. If you configure a server with the IPv6 addressing mode, you cannot use
        the server in the IPv4 addressing mode. Default value: NO Possible values = YES, NO

    comment(str): Any information about the server.

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    domainresolvenow(bool): Immediately send a DNS query to resolve the servers domain name.

    delay(int): Time, in seconds, after which all the services configured on the server are disabled.

    graceful(str): Shut down gracefully, without accepting any new connections, and disabling each service when all of its
        connections are closed. Default value: NO Possible values = YES, NO

    internal(bool): Display names of the servers that have been created for internal use.

    newname(str): New name for the server. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.update_server <args>

    '''

    result = {}

    payload = {'server': {}}

    if name:
        payload['server']['name'] = name

    if ipaddress:
        payload['server']['ipaddress'] = ipaddress

    if domain:
        payload['server']['domain'] = domain

    if translationip:
        payload['server']['translationip'] = translationip

    if translationmask:
        payload['server']['translationmask'] = translationmask

    if domainresolveretry:
        payload['server']['domainresolveretry'] = domainresolveretry

    if state:
        payload['server']['state'] = state

    if ipv6address:
        payload['server']['ipv6address'] = ipv6address

    if comment:
        payload['server']['comment'] = comment

    if td:
        payload['server']['td'] = td

    if domainresolvenow:
        payload['server']['domainresolvenow'] = domainresolvenow

    if delay:
        payload['server']['delay'] = delay

    if graceful:
        payload['server']['graceful'] = graceful

    if internal:
        payload['server']['Internal'] = internal

    if newname:
        payload['server']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/server', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_service(name=None, ip=None, servername=None, servicetype=None, port=None, cleartextport=None, cachetype=None,
                   maxclient=None, healthmonitor=None, maxreq=None, cacheable=None, cip=None, cipheader=None, usip=None,
                   pathmonitor=None, pathmonitorindv=None, useproxyport=None, sc=None, sp=None, rtspsessionidremap=None,
                   clttimeout=None, svrtimeout=None, customserverid=None, serverid=None, cka=None, tcpb=None, cmp=None,
                   maxbandwidth=None, accessdown=None, monthreshold=None, state=None, downstateflush=None,
                   tcpprofilename=None, httpprofilename=None, hashid=None, comment=None, appflowlog=None,
                   netprofile=None, td=None, processlocal=None, dnsprofilename=None, monconnectionclose=None,
                   ipaddress=None, weight=None, monitor_name_svc=None, riseapbrstatsmsgcode=None, delay=None,
                   graceful=None, internal=None, newname=None, save=False):
    '''
    Update the running configuration for the service config key.

    name(str): Name for the service. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the service has been created. Minimum length = 1

    ip(str): IP to assign to the service. Minimum length = 1

    servername(str): Name of the server that hosts the service. Minimum length = 1

    servicetype(str): Protocol in which data is exchanged with the service. Possible values = HTTP, FTP, TCP, UDP, SSL,
        SSL_BRIDGE, SSL_TCP, DTLS, NNTP, RPCSVR, DNS, ADNS, SNMP, RTSP, DHCPRA, ANY, SIP_UDP, SIP_TCP, SIP_SSL, DNS_TCP,
        ADNS_TCP, MYSQL, MSSQL, ORACLE, RADIUS, RADIUSListener, RDP, DIAMETER, SSL_DIAMETER, TFTP, SMPP, PPTP, GRE,
        SYSLOGTCP, SYSLOGUDP, FIX, SSL_FIX, USER_TCP, USER_SSL_TCP

    port(int): Port number of the service. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    cleartextport(int): Port to which clear text data must be sent after the appliance decrypts incoming SSL traffic.
        Applicable to transparent SSL services. Minimum value = 1

    cachetype(str): Cache type supported by the cache server. Possible values = TRANSPARENT, REVERSE, FORWARD

    maxclient(int): Maximum number of simultaneous open connections to the service. Minimum value = 0 Maximum value =
        4294967294

    healthmonitor(str): Monitor the health of this service. Available settings function as follows: YES - Send probes to
        check the health of the service. NO - Do not send probes to check the health of the service. With the NO option,
        the appliance shows the service as UP at all times. Default value: YES Possible values = YES, NO

    maxreq(int): Maximum number of requests that can be sent on a persistent connection to the service.  Note: Connection
        requests beyond this value are rejected. Minimum value = 0 Maximum value = 65535

    cacheable(str): Use the transparent cache redirection virtual server to forward requests to the cache server. Note: Do
        not specify this parameter if you set the Cache Type parameter. Default value: NO Possible values = YES, NO

    cip(str): Before forwarding a request to the service, insert an HTTP header with the clients IPv4 or IPv6 address as its
        value. Used if the server needs the clients IP address for security, accounting, or other purposes, and setting
        the Use Source IP parameter is not a viable option. Possible values = ENABLED, DISABLED

    cipheader(str): Name for the HTTP header whose value must be set to the IP address of the client. Used with the Client IP
        parameter. If you set the Client IP parameter, and you do not specify a name for the header, the appliance uses
        the header name specified for the global Client IP Header parameter (the cipHeader parameter in the set ns param
        CLI command or the Client IP Header parameter in the Configure HTTP Parameters dialog box at System ;gt; Settings
        ;gt; Change HTTP parameters). If the global Client IP Header parameter is not specified, the appliance inserts a
        header with the name "client-ip.". Minimum length = 1

    usip(str): Use the clients IP address as the source IP address when initiating a connection to the server. When creating
        a service, if you do not set this parameter, the service inherits the global Use Source IP setting (available in
        the enable ns mode and disable ns mode CLI commands, or in the System ;gt; Settings ;gt; Configure modes ;gt;
        Configure Modes dialog box). However, you can override this setting after you create the service. Possible values
        = YES, NO

    pathmonitor(str): Path monitoring for clustering. Possible values = YES, NO

    pathmonitorindv(str): Individual Path monitoring decisions. Possible values = YES, NO

    useproxyport(str): Use the proxy port as the source port when initiating connections with the server. With the NO
        setting, the client-side connection port is used as the source port for the server-side connection.  Note: This
        parameter is available only when the Use Source IP (USIP) parameter is set to YES. Possible values = YES, NO

    sc(str): State of SureConnect for the service. Default value: OFF Possible values = ON, OFF

    sp(str): Enable surge protection for the service. Possible values = ON, OFF

    rtspsessionidremap(str): Enable RTSP session ID mapping for the service. Default value: OFF Possible values = ON, OFF

    clttimeout(int): Time, in seconds, after which to terminate an idle client connection. Minimum value = 0 Maximum value =
        31536000

    svrtimeout(int): Time, in seconds, after which to terminate an idle server connection. Minimum value = 0 Maximum value =
        31536000

    customserverid(str): Unique identifier for the service. Used when the persistency type for the virtual server is set to
        Custom Server ID. Default value: "None"

    serverid(int): The identifier for the service. This is used when the persistency type is set to Custom Server ID.

    cka(str): Enable client keep-alive for the service. Possible values = YES, NO

    tcpb(str): Enable TCP buffering for the service. Possible values = YES, NO

    cmp(str): Enable compression for the service. Possible values = YES, NO

    maxbandwidth(int): Maximum bandwidth, in Kbps, allocated to the service. Minimum value = 0 Maximum value = 4294967287

    accessdown(str): Use Layer 2 mode to bridge the packets sent to this service if it is marked as DOWN. If the service is
        DOWN, and this parameter is disabled, the packets are dropped. Default value: NO Possible values = YES, NO

    monthreshold(int): Minimum sum of weights of the monitors that are bound to this service. Used to determine whether to
        mark a service as UP or DOWN. Minimum value = 0 Maximum value = 65535

    state(str): Initial state of the service. Default value: ENABLED Possible values = ENABLED, DISABLED

    downstateflush(str): Flush all active transactions associated with a service whose state transitions from UP to DOWN. Do
        not enable this option for applications that must complete their transactions. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    tcpprofilename(str): Name of the TCP profile that contains TCP configuration settings for the service. Minimum length = 1
        Maximum length = 127

    httpprofilename(str): Name of the HTTP profile that contains HTTP configuration settings for the service. Minimum length
        = 1 Maximum length = 127

    hashid(int): A numerical identifier that can be used by hash based load balancing methods. Must be unique for each
        service. Minimum value = 1

    comment(str): Any information about the service.

    appflowlog(str): Enable logging of AppFlow information. Default value: ENABLED Possible values = ENABLED, DISABLED

    netprofile(str): Network profile to use for the service. Minimum length = 1 Maximum length = 127

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    processlocal(str): By turning on this option packets destined to a service in a cluster will not under go any steering.
        Turn this option for single packet request response mode or when the upstream device is performing a proper RSS
        for connection based distribution. Default value: DISABLED Possible values = ENABLED, DISABLED

    dnsprofilename(str): Name of the DNS profile to be associated with the service. DNS profile properties will applied to
        the transactions processed by a service. This parameter is valid only for ADNS and ADNS-TCP services. Minimum
        length = 1 Maximum length = 127

    monconnectionclose(str): Close monitoring connections by sending the service a connection termination message with the
        specified bit set. Default value: NONE Possible values = RESET, FIN

    ipaddress(str): The new IP address of the service.

    weight(int): Weight to assign to the monitor-service binding. When a monitor is UP, the weight assigned to its binding
        with the service determines how much the monitor contributes toward keeping the health of the service above the
        value configured for the Monitor Threshold parameter. Minimum value = 1 Maximum value = 100

    monitor_name_svc(str): Name of the monitor bound to the specified service. Minimum length = 1

    riseapbrstatsmsgcode(int): The code indicating the rise apbr status.

    delay(int): Time, in seconds, allocated to the NetScaler appliance for a graceful shutdown of the service. During this
        period, new requests are sent to the service only for clients who already have persistent sessions on the
        appliance. Requests from new clients are load balanced among other available services. After the delay time
        expires, no requests are sent to the service, and the service is marked as unavailable (OUT OF SERVICE).

    graceful(str): Shut down gracefully, not accepting any new connections, and disabling the service when all of its
        connections are closed. Default value: NO Possible values = YES, NO

    internal(bool): Display only dynamically learned services.

    newname(str): New name for the service. Must begin with an ASCII alphabetic or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.update_service <args>

    '''

    result = {}

    payload = {'service': {}}

    if name:
        payload['service']['name'] = name

    if ip:
        payload['service']['ip'] = ip

    if servername:
        payload['service']['servername'] = servername

    if servicetype:
        payload['service']['servicetype'] = servicetype

    if port:
        payload['service']['port'] = port

    if cleartextport:
        payload['service']['cleartextport'] = cleartextport

    if cachetype:
        payload['service']['cachetype'] = cachetype

    if maxclient:
        payload['service']['maxclient'] = maxclient

    if healthmonitor:
        payload['service']['healthmonitor'] = healthmonitor

    if maxreq:
        payload['service']['maxreq'] = maxreq

    if cacheable:
        payload['service']['cacheable'] = cacheable

    if cip:
        payload['service']['cip'] = cip

    if cipheader:
        payload['service']['cipheader'] = cipheader

    if usip:
        payload['service']['usip'] = usip

    if pathmonitor:
        payload['service']['pathmonitor'] = pathmonitor

    if pathmonitorindv:
        payload['service']['pathmonitorindv'] = pathmonitorindv

    if useproxyport:
        payload['service']['useproxyport'] = useproxyport

    if sc:
        payload['service']['sc'] = sc

    if sp:
        payload['service']['sp'] = sp

    if rtspsessionidremap:
        payload['service']['rtspsessionidremap'] = rtspsessionidremap

    if clttimeout:
        payload['service']['clttimeout'] = clttimeout

    if svrtimeout:
        payload['service']['svrtimeout'] = svrtimeout

    if customserverid:
        payload['service']['customserverid'] = customserverid

    if serverid:
        payload['service']['serverid'] = serverid

    if cka:
        payload['service']['cka'] = cka

    if tcpb:
        payload['service']['tcpb'] = tcpb

    if cmp:
        payload['service']['cmp'] = cmp

    if maxbandwidth:
        payload['service']['maxbandwidth'] = maxbandwidth

    if accessdown:
        payload['service']['accessdown'] = accessdown

    if monthreshold:
        payload['service']['monthreshold'] = monthreshold

    if state:
        payload['service']['state'] = state

    if downstateflush:
        payload['service']['downstateflush'] = downstateflush

    if tcpprofilename:
        payload['service']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['service']['httpprofilename'] = httpprofilename

    if hashid:
        payload['service']['hashid'] = hashid

    if comment:
        payload['service']['comment'] = comment

    if appflowlog:
        payload['service']['appflowlog'] = appflowlog

    if netprofile:
        payload['service']['netprofile'] = netprofile

    if td:
        payload['service']['td'] = td

    if processlocal:
        payload['service']['processlocal'] = processlocal

    if dnsprofilename:
        payload['service']['dnsprofilename'] = dnsprofilename

    if monconnectionclose:
        payload['service']['monconnectionclose'] = monconnectionclose

    if ipaddress:
        payload['service']['ipaddress'] = ipaddress

    if weight:
        payload['service']['weight'] = weight

    if monitor_name_svc:
        payload['service']['monitor_name_svc'] = monitor_name_svc

    if riseapbrstatsmsgcode:
        payload['service']['riseapbrstatsmsgcode'] = riseapbrstatsmsgcode

    if delay:
        payload['service']['delay'] = delay

    if graceful:
        payload['service']['graceful'] = graceful

    if internal:
        payload['service']['Internal'] = internal

    if newname:
        payload['service']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/service', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_servicegroup(servicegroupname=None, servicetype=None, cachetype=None, td=None, maxclient=None, maxreq=None,
                        cacheable=None, cip=None, cipheader=None, usip=None, pathmonitor=None, pathmonitorindv=None,
                        useproxyport=None, healthmonitor=None, sc=None, sp=None, rtspsessionidremap=None,
                        clttimeout=None, svrtimeout=None, cka=None, tcpb=None, cmp=None, maxbandwidth=None,
                        monthreshold=None, state=None, downstateflush=None, tcpprofilename=None, httpprofilename=None,
                        comment=None, appflowlog=None, netprofile=None, autoscale=None, memberport=None,
                        monconnectionclose=None, servername=None, port=None, weight=None, customserverid=None,
                        serverid=None, hashid=None, monitor_name_svc=None, dup_weight=None, riseapbrstatsmsgcode=None,
                        delay=None, graceful=None, includemembers=None, newname=None, save=False):
    '''
    Update the running configuration for the servicegroup config key.

    servicegroupname(str): Name of the service group. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the name is created. Minimum length = 1

    servicetype(str): Protocol used to exchange data with the service. Possible values = HTTP, FTP, TCP, UDP, SSL,
        SSL_BRIDGE, SSL_TCP, DTLS, NNTP, RPCSVR, DNS, ADNS, SNMP, RTSP, DHCPRA, ANY, SIP_UDP, SIP_TCP, SIP_SSL, DNS_TCP,
        ADNS_TCP, MYSQL, MSSQL, ORACLE, RADIUS, RADIUSListener, RDP, DIAMETER, SSL_DIAMETER, TFTP, SMPP, PPTP, GRE,
        SYSLOGTCP, SYSLOGUDP, FIX, SSL_FIX, USER_TCP, USER_SSL_TCP

    cachetype(str): Cache type supported by the cache server. Possible values = TRANSPARENT, REVERSE, FORWARD

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    maxclient(int): Maximum number of simultaneous open connections for the service group. Minimum value = 0 Maximum value =
        4294967294

    maxreq(int): Maximum number of requests that can be sent on a persistent connection to the service group.  Note:
        Connection requests beyond this value are rejected. Minimum value = 0 Maximum value = 65535

    cacheable(str): Use the transparent cache redirection virtual server to forward the request to the cache server. Note: Do
        not set this parameter if you set the Cache Type. Default value: NO Possible values = YES, NO

    cip(str): Insert the Client IP header in requests forwarded to the service. Possible values = ENABLED, DISABLED

    cipheader(str): Name of the HTTP header whose value must be set to the IP address of the client. Used with the Client IP
        parameter. If client IP insertion is enabled, and the client IP header is not specified, the value of Client IP
        Header parameter or the value set by the set ns config command is used as clients IP header name. Minimum length
        = 1

    usip(str): Use clients IP address as the source IP address when initiating connection to the server. With the NO setting,
        which is the default, a mapped IP (MIP) address or subnet IP (SNIP) address is used as the source IP address to
        initiate server side connections. Possible values = YES, NO

    pathmonitor(str): Path monitoring for clustering. Possible values = YES, NO

    pathmonitorindv(str): Individual Path monitoring decisions. Possible values = YES, NO

    useproxyport(str): Use the proxy port as the source port when initiating connections with the server. With the NO
        setting, the client-side connection port is used as the source port for the server-side connection.  Note: This
        parameter is available only when the Use Source IP (USIP) parameter is set to YES. Possible values = YES, NO

    healthmonitor(str): Monitor the health of this service. Available settings function as follows: YES - Send probes to
        check the health of the service. NO - Do not send probes to check the health of the service. With the NO option,
        the appliance shows the service as UP at all times. Default value: YES Possible values = YES, NO

    sc(str): State of the SureConnect feature for the service group. Default value: OFF Possible values = ON, OFF

    sp(str): Enable surge protection for the service group. Default value: OFF Possible values = ON, OFF

    rtspsessionidremap(str): Enable RTSP session ID mapping for the service group. Default value: OFF Possible values = ON,
        OFF

    clttimeout(int): Time, in seconds, after which to terminate an idle client connection. Minimum value = 0 Maximum value =
        31536000

    svrtimeout(int): Time, in seconds, after which to terminate an idle server connection. Minimum value = 0 Maximum value =
        31536000

    cka(str): Enable client keep-alive for the service group. Possible values = YES, NO

    tcpb(str): Enable TCP buffering for the service group. Possible values = YES, NO

    cmp(str): Enable compression for the specified service. Possible values = YES, NO

    maxbandwidth(int): Maximum bandwidth, in Kbps, allocated for all the services in the service group. Minimum value = 0
        Maximum value = 4294967287

    monthreshold(int): Minimum sum of weights of the monitors that are bound to this service. Used to determine whether to
        mark a service as UP or DOWN. Minimum value = 0 Maximum value = 65535

    state(str): Initial state of the service group. Default value: ENABLED Possible values = ENABLED, DISABLED

    downstateflush(str): Flush all active transactions associated with all the services in the service group whose state
        transitions from UP to DOWN. Do not enable this option for applications that must complete their transactions.
        Default value: ENABLED Possible values = ENABLED, DISABLED

    tcpprofilename(str): Name of the TCP profile that contains TCP configuration settings for the service group. Minimum
        length = 1 Maximum length = 127

    httpprofilename(str): Name of the HTTP profile that contains HTTP configuration settings for the service group. Minimum
        length = 1 Maximum length = 127

    comment(str): Any information about the service group.

    appflowlog(str): Enable logging of AppFlow information for the specified service group. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    netprofile(str): Network profile for the service group. Minimum length = 1 Maximum length = 127

    autoscale(str): Auto scale option for a servicegroup. Default value: DISABLED Possible values = DISABLED, DNS, POLICY

    memberport(int): member port.

    monconnectionclose(str): Close monitoring connections by sending the service a connection termination message with the
        specified bit set. Default value: NONE Possible values = RESET, FIN

    servername(str): Name of the server to which to bind the service group. Minimum length = 1

    port(int): Server port number. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    weight(int): Weight to assign to the servers in the service group. Specifies the capacity of the servers relative to the
        other servers in the load balancing configuration. The higher the weight, the higher the percentage of requests
        sent to the service. Minimum value = 1 Maximum value = 100

    customserverid(str): The identifier for this IP:Port pair. Used when the persistency type is set to Custom Server ID.
        Default value: "None"

    serverid(int): The identifier for the service. This is used when the persistency type is set to Custom Server ID.

    hashid(int): The hash identifier for the service. This must be unique for each service. This parameter is used by hash
        based load balancing methods. Minimum value = 1

    monitor_name_svc(str): Name of the monitor bound to the service group. Used to assign a weight to the monitor. Minimum
        length = 1

    dup_weight(int): weight of the monitor that is bound to servicegroup. Minimum value = 1

    riseapbrstatsmsgcode(int): The code indicating the rise apbr status.

    delay(int): Time, in seconds, allocated for a shutdown of the services in the service group. During this period, new
        requests are sent to the service only for clients who already have persistent sessions on the appliance. Requests
        from new clients are load balanced among other available services. After the delay time expires, no requests are
        sent to the service, and the service is marked as unavailable (OUT OF SERVICE).

    graceful(str): Wait for all existing connections to the service to terminate before shutting down the service. Default
        value: NO Possible values = YES, NO

    includemembers(bool): Display the members of the listed service groups in addition to their settings. Can be specified
        when no service group name is provided in the command. In that case, the details displayed for each service group
        are identical to the details displayed when a service group name is provided, except that bound monitors are not
        displayed.

    newname(str): New name for the service group. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.update_servicegroup <args>

    '''

    result = {}

    payload = {'servicegroup': {}}

    if servicegroupname:
        payload['servicegroup']['servicegroupname'] = servicegroupname

    if servicetype:
        payload['servicegroup']['servicetype'] = servicetype

    if cachetype:
        payload['servicegroup']['cachetype'] = cachetype

    if td:
        payload['servicegroup']['td'] = td

    if maxclient:
        payload['servicegroup']['maxclient'] = maxclient

    if maxreq:
        payload['servicegroup']['maxreq'] = maxreq

    if cacheable:
        payload['servicegroup']['cacheable'] = cacheable

    if cip:
        payload['servicegroup']['cip'] = cip

    if cipheader:
        payload['servicegroup']['cipheader'] = cipheader

    if usip:
        payload['servicegroup']['usip'] = usip

    if pathmonitor:
        payload['servicegroup']['pathmonitor'] = pathmonitor

    if pathmonitorindv:
        payload['servicegroup']['pathmonitorindv'] = pathmonitorindv

    if useproxyport:
        payload['servicegroup']['useproxyport'] = useproxyport

    if healthmonitor:
        payload['servicegroup']['healthmonitor'] = healthmonitor

    if sc:
        payload['servicegroup']['sc'] = sc

    if sp:
        payload['servicegroup']['sp'] = sp

    if rtspsessionidremap:
        payload['servicegroup']['rtspsessionidremap'] = rtspsessionidremap

    if clttimeout:
        payload['servicegroup']['clttimeout'] = clttimeout

    if svrtimeout:
        payload['servicegroup']['svrtimeout'] = svrtimeout

    if cka:
        payload['servicegroup']['cka'] = cka

    if tcpb:
        payload['servicegroup']['tcpb'] = tcpb

    if cmp:
        payload['servicegroup']['cmp'] = cmp

    if maxbandwidth:
        payload['servicegroup']['maxbandwidth'] = maxbandwidth

    if monthreshold:
        payload['servicegroup']['monthreshold'] = monthreshold

    if state:
        payload['servicegroup']['state'] = state

    if downstateflush:
        payload['servicegroup']['downstateflush'] = downstateflush

    if tcpprofilename:
        payload['servicegroup']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['servicegroup']['httpprofilename'] = httpprofilename

    if comment:
        payload['servicegroup']['comment'] = comment

    if appflowlog:
        payload['servicegroup']['appflowlog'] = appflowlog

    if netprofile:
        payload['servicegroup']['netprofile'] = netprofile

    if autoscale:
        payload['servicegroup']['autoscale'] = autoscale

    if memberport:
        payload['servicegroup']['memberport'] = memberport

    if monconnectionclose:
        payload['servicegroup']['monconnectionclose'] = monconnectionclose

    if servername:
        payload['servicegroup']['servername'] = servername

    if port:
        payload['servicegroup']['port'] = port

    if weight:
        payload['servicegroup']['weight'] = weight

    if customserverid:
        payload['servicegroup']['customserverid'] = customserverid

    if serverid:
        payload['servicegroup']['serverid'] = serverid

    if hashid:
        payload['servicegroup']['hashid'] = hashid

    if monitor_name_svc:
        payload['servicegroup']['monitor_name_svc'] = monitor_name_svc

    if dup_weight:
        payload['servicegroup']['dup_weight'] = dup_weight

    if riseapbrstatsmsgcode:
        payload['servicegroup']['riseapbrstatsmsgcode'] = riseapbrstatsmsgcode

    if delay:
        payload['servicegroup']['delay'] = delay

    if graceful:
        payload['servicegroup']['graceful'] = graceful

    if includemembers:
        payload['servicegroup']['includemembers'] = includemembers

    if newname:
        payload['servicegroup']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/servicegroup', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_vserver(name=None, backupvserver=None, redirecturl=None, cacheable=None, clttimeout=None, somethod=None,
                   sopersistence=None, sopersistencetimeout=None, sothreshold=None, pushvserver=None, save=False):
    '''
    Update the running configuration for the vserver config key.

    name(str): The name of the virtual server to be removed. Minimum length = 1

    backupvserver(str): The name of the backup virtual server for this virtual server. Minimum length = 1

    redirecturl(str): The URL where traffic is redirected if the virtual server in the system becomes unavailable. Minimum
        length = 1

    cacheable(str): Use this option to specify whether a virtual server (used for load balancing or content switching) routes
        requests to the cache redirection virtual server before sending it to the configured servers. Possible values =
        YES, NO

    clttimeout(int): The timeout value in seconds for idle client connection. Minimum value = 0 Maximum value = 31536000

    somethod(str): The spillover factor. The system will use this value to determine if it should send traffic to the
        backupvserver when the main virtual server reaches the spillover threshold. Possible values = CONNECTION,
        DYNAMICCONNECTION, BANDWIDTH, HEALTH, NONE

    sopersistence(str): The state of the spillover persistence. Default value: DISABLED Possible values = ENABLED, DISABLED

    sopersistencetimeout(int): The spillover persistence entry timeout. Default value: 2 Minimum value = 2 Maximum value =
        1440

    sothreshold(int): The spillver threshold value. Minimum value = 1 Maximum value = 4294967294

    pushvserver(str): The lb vserver of type PUSH/SSL_PUSH to which server pushes the updates received on the client facing
        non-push lb vserver. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' basic.update_vserver <args>

    '''

    result = {}

    payload = {'vserver': {}}

    if name:
        payload['vserver']['name'] = name

    if backupvserver:
        payload['vserver']['backupvserver'] = backupvserver

    if redirecturl:
        payload['vserver']['redirecturl'] = redirecturl

    if cacheable:
        payload['vserver']['cacheable'] = cacheable

    if clttimeout:
        payload['vserver']['clttimeout'] = clttimeout

    if somethod:
        payload['vserver']['somethod'] = somethod

    if sopersistence:
        payload['vserver']['sopersistence'] = sopersistence

    if sopersistencetimeout:
        payload['vserver']['sopersistencetimeout'] = sopersistencetimeout

    if sothreshold:
        payload['vserver']['sothreshold'] = sothreshold

    if pushvserver:
        payload['vserver']['pushvserver'] = pushvserver

    execution = __proxy__['citrixns.put']('config/vserver', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
