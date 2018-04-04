# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the load-balancing key.

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

__virtualname__ = 'load_balancing'


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

    return False, 'The load_balancing execution module can only be loaded for citrixns proxy minions.'


def add_lbgroup(name=None, persistencetype=None, persistencebackup=None, backuppersistencetimeout=None, persistmask=None,
                cookiename=None, v6persistmasklen=None, cookiedomain=None, timeout=None, rule=None,
                usevserverpersistency=None, mastervserver=None, newname=None, save=False):
    '''
    Add a new lbgroup to the running configuration.

    name(str): Name of the load balancing virtual server group. Minimum length = 1

    persistencetype(str): Type of persistence for the group. Available settings function as follows: * SOURCEIP - Create
        persistence sessions based on the client IP. * COOKIEINSERT - Create persistence sessions based on a cookie in
        client requests. The cookie is inserted by a Set-Cookie directive from the server, in its first response to a
        client. * RULE - Create persistence sessions based on a user defined rule. * NONE - Disable persistence for the
        group. Possible values = SOURCEIP, COOKIEINSERT, RULE, NONE

    persistencebackup(str): Type of backup persistence for the group. Possible values = SOURCEIP, NONE

    backuppersistencetimeout(int): Time period, in minutes, for which backup persistence is in effect. Default value: 2
        Minimum value = 2 Maximum value = 1440

    persistmask(str): Persistence mask to apply to source IPv4 addresses when creating source IP based persistence sessions.
        Minimum length = 1

    cookiename(str): Use this parameter to specify the cookie name for COOKIE peristence type. It specifies the name of
        cookie with a maximum of 32 characters. If not specified, cookie name is internally generated.

    v6persistmasklen(int): Persistence mask to apply to source IPv6 addresses when creating source IP based persistence
        sessions. Default value: 128 Minimum value = 1 Maximum value = 128

    cookiedomain(str): Domain attribute for the HTTP cookie. Minimum length = 1

    timeout(int): Time period for which a persistence session is in effect. Default value: 2 Minimum value = 0 Maximum value
        = 1440

    rule(str): Expression, or name of a named expression, against which traffic is evaluated. Written in the classic or
        default syntax. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can
        be split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks. Default value: "None"

    usevserverpersistency(str): . Default value: DISABLED Possible values = ENABLED, DISABLED

    mastervserver(str): .

    newname(str): New name for the load balancing virtual server group. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbgroup <args>

    '''

    result = {}

    payload = {'lbgroup': {}}

    if name:
        payload['lbgroup']['name'] = name

    if persistencetype:
        payload['lbgroup']['persistencetype'] = persistencetype

    if persistencebackup:
        payload['lbgroup']['persistencebackup'] = persistencebackup

    if backuppersistencetimeout:
        payload['lbgroup']['backuppersistencetimeout'] = backuppersistencetimeout

    if persistmask:
        payload['lbgroup']['persistmask'] = persistmask

    if cookiename:
        payload['lbgroup']['cookiename'] = cookiename

    if v6persistmasklen:
        payload['lbgroup']['v6persistmasklen'] = v6persistmasklen

    if cookiedomain:
        payload['lbgroup']['cookiedomain'] = cookiedomain

    if timeout:
        payload['lbgroup']['timeout'] = timeout

    if rule:
        payload['lbgroup']['rule'] = rule

    if usevserverpersistency:
        payload['lbgroup']['usevserverpersistency'] = usevserverpersistency

    if mastervserver:
        payload['lbgroup']['mastervserver'] = mastervserver

    if newname:
        payload['lbgroup']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/lbgroup', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbgroup_lbvserver_binding(name=None, save=False):
    '''
    Add a new lbgroup_lbvserver_binding to the running configuration.

    name(str): Name for the load balancing virtual server group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbgroup_lbvserver_binding <args>

    '''

    result = {}

    payload = {'lbgroup_lbvserver_binding': {}}

    if name:
        payload['lbgroup_lbvserver_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbgroup_lbvserver_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbmetrictable(metrictable=None, metric=None, snmpoid=None, save=False):
    '''
    Add a new lbmetrictable to the running configuration.

    metrictable(str): Name for the metric table. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.   CLI Users: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my metrictable" or my metrictable). Minimum length = 1 Maximum length = 31

    metric(str): Name of the metric for which to change the SNMP OID. Minimum length = 1

    snmpoid(str): New SNMP OID of the metric. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbmetrictable <args>

    '''

    result = {}

    payload = {'lbmetrictable': {}}

    if metrictable:
        payload['lbmetrictable']['metrictable'] = metrictable

    if metric:
        payload['lbmetrictable']['metric'] = metric

    if snmpoid:
        payload['lbmetrictable']['Snmpoid'] = snmpoid

    execution = __proxy__['citrixns.post']('config/lbmetrictable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbmetrictable_metric_binding(metric=None, metrictable=None, snmpoid=None, save=False):
    '''
    Add a new lbmetrictable_metric_binding to the running configuration.

    metric(str): Name of the metric for which to change the SNMP OID. Minimum length = 1

    metrictable(str): Name of the metric table. Minimum length = 1 Maximum length = 31

    snmpoid(str): New SNMP OID of the metric. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbmetrictable_metric_binding <args>

    '''

    result = {}

    payload = {'lbmetrictable_metric_binding': {}}

    if metric:
        payload['lbmetrictable_metric_binding']['metric'] = metric

    if metrictable:
        payload['lbmetrictable_metric_binding']['metrictable'] = metrictable

    if snmpoid:
        payload['lbmetrictable_metric_binding']['Snmpoid'] = snmpoid

    execution = __proxy__['citrixns.post']('config/lbmetrictable_metric_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbmonitor(monitorname=None, ns_type=None, action=None, respcode=None, httprequest=None, rtsprequest=None,
                  customheaders=None, maxforwards=None, sipmethod=None, sipuri=None, sipreguri=None, send=None,
                  recv=None, query=None, querytype=None, scriptname=None, scriptargs=None, dispatcherip=None,
                  dispatcherport=None, username=None, password=None, secondarypassword=None, logonpointname=None,
                  lasversion=None, radkey=None, radnasid=None, radnasip=None, radaccounttype=None, radframedip=None,
                  radapn=None, radmsisdn=None, radaccountsession=None, lrtm=None, deviation=None, units1=None,
                  interval=None, units3=None, resptimeout=None, units4=None, resptimeoutthresh=None, retries=None,
                  failureretries=None, alertretries=None, successretries=None, downtime=None, units2=None, destip=None,
                  destport=None, state=None, reverse=None, transparent=None, iptunnel=None, tos=None, tosid=None,
                  secure=None, validatecred=None, domain=None, ipaddress=None, group=None, filename=None, basedn=None,
                  binddn=None, filter=None, attribute=None, database=None, oraclesid=None, sqlquery=None, evalrule=None,
                  mssqlprotocolversion=None, snmpoid=None, snmpcommunity=None, snmpthreshold=None, snmpversion=None,
                  metrictable=None, application=None, sitepath=None, storename=None, storefrontacctservice=None,
                  hostname=None, netprofile=None, originhost=None, originrealm=None, hostipaddress=None, vendorid=None,
                  productname=None, firmwarerevision=None, authapplicationid=None, acctapplicationid=None,
                  inbandsecurityid=None, supportedvendorids=None, vendorspecificvendorid=None,
                  vendorspecificauthapplicationids=None, vendorspecificacctapplicationids=None, kcdaccount=None,
                  storedb=None, storefrontcheckbackendservices=None, trofscode=None, trofsstring=None, sslprofile=None,
                  metric=None, metricthreshold=None, metricweight=None, servicename=None, servicegroupname=None,
                  save=False):
    '''
    Add a new lbmonitor to the running configuration.

    monitorname(str): Name for the monitor. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.  CLI Users: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my monitor" or my monitor). Minimum length = 1

    ns_type(str): Type of monitor that you want to create. Possible values = PING, TCP, HTTP, TCP-ECV, HTTP-ECV, UDP-ECV,
        DNS, FTP, LDNS-PING, LDNS-TCP, LDNS-DNS, RADIUS, USER, HTTP-INLINE, SIP-UDP, SIP-TCP, LOAD, FTP-EXTENDED, SMTP,
        SNMP, NNTP, MYSQL, MYSQL-ECV, MSSQL-ECV, ORACLE-ECV, LDAP, POP3, CITRIX-XML-SERVICE, CITRIX-WEB-INTERFACE,
        DNS-TCP, RTSP, ARP, CITRIX-AG, CITRIX-AAC-LOGINPAGE, CITRIX-AAC-LAS, CITRIX-XD-DDC, ND6, CITRIX-WI-EXTENDED,
        DIAMETER, RADIUS_ACCOUNTING, STOREFRONT, APPC, SMPP, CITRIX-XNC-ECV, CITRIX-XDM, CITRIX-STA-SERVICE,
        CITRIX-STA-SERVICE-NHOP

    action(str): Action to perform when the response to an inline monitor (a monitor of type HTTP-INLINE) indicates that the
        service is down. A service monitored by an inline monitor is considered DOWN if the response code is not one of
        the codes that have been specified for the Response Code parameter.  Available settings function as follows:  *
        NONE - Do not take any action. However, the show service command and the show lb monitor command indicate the
        total number of responses that were checked and the number of consecutive error responses received after the last
        successful probe. * LOG - Log the event in NSLOG or SYSLOG.  * DOWN - Mark the service as being down, and then do
        not direct any traffic to the service until the configured down time has expired. Persistent connections to the
        service are terminated as soon as the service is marked as DOWN. Also, log the event in NSLOG or SYSLOG. Default
        value: DOWN Possible values = NONE, LOG, DOWN

    respcode(list(str)): Response codes for which to mark the service as UP. For any other response code, the action
        performed depends on the monitor type. HTTP monitors and RADIUS monitors mark the service as DOWN, while
        HTTP-INLINE monitors perform the action indicated by the Action parameter.

    httprequest(str): HTTP request to send to the server (for example, "HEAD /file.html").

    rtsprequest(str): RTSP request to send to the server (for example, "OPTIONS *").

    customheaders(str): Custom header string to include in the monitoring probes.

    maxforwards(int): Maximum number of hops that the SIP request used for monitoring can traverse to reach the server.
        Applicable only to monitors of type SIP-UDP. Default value: 1 Minimum value = 0 Maximum value = 255

    sipmethod(str): SIP method to use for the query. Applicable only to monitors of type SIP-UDP. Possible values = OPTIONS,
        INVITE, REGISTER

    sipuri(str): SIP URI string to send to the service (for example, sip:sip.test). Applicable only to monitors of type
        SIP-UDP. Minimum length = 1

    sipreguri(str): SIP user to be registered. Applicable only if the monitor is of type SIP-UDP and the SIP Method parameter
        is set to REGISTER. Minimum length = 1

    send(str): String to send to the service. Applicable to TCP-ECV, HTTP-ECV, and UDP-ECV monitors.

    recv(str): String expected from the server for the service to be marked as UP. Applicable to TCP-ECV, HTTP-ECV, and
        UDP-ECV monitors.

    query(str): Domain name to resolve as part of monitoring the DNS service (for example, example.com).

    querytype(str): Type of DNS record for which to send monitoring queries. Set to Address for querying A records, AAAA for
        querying AAAA records, and Zone for querying the SOA record. Possible values = Address, Zone, AAAA

    scriptname(str): Path and name of the script to execute. The script must be available on the NetScaler appliance, in the
        /nsconfig/monitors/ directory. Minimum length = 1

    scriptargs(str): String of arguments for the script. The string is copied verbatim into the request.

    dispatcherip(str): IP address of the dispatcher to which to send the probe.

    dispatcherport(int): Port number on which the dispatcher listens for the monitoring probe.

    username(str): User name with which to probe the RADIUS, NNTP, FTP, FTP-EXTENDED, MYSQL, MSSQL, POP3, CITRIX-AG,
        CITRIX-XD-DDC, CITRIX-WI-EXTENDED, CITRIX-XNC or CITRIX-XDM server. Minimum length = 1

    password(str): Password that is required for logging on to the RADIUS, NNTP, FTP, FTP-EXTENDED, MYSQL, MSSQL, POP3,
        CITRIX-AG, CITRIX-XD-DDC, CITRIX-WI-EXTENDED, CITRIX-XNC-ECV or CITRIX-XDM server. Used in conjunction with the
        user name specified for the User Name parameter. Minimum length = 1

    secondarypassword(str): Secondary password that users might have to provide to log on to the Access Gateway server.
        Applicable to CITRIX-AG monitors.

    logonpointname(str): Name of the logon point that is configured for the Citrix Access Gateway Advanced Access Control
        software. Required if you want to monitor the associated login page or Logon Agent. Applicable to CITRIX-AAC-LAS
        and CITRIX-AAC-LOGINPAGE monitors.

    lasversion(str): Version number of the Citrix Advanced Access Control Logon Agent. Required by the CITRIX-AAC-LAS
        monitor.

    radkey(str): Authentication key (shared secret text string) for RADIUS clients and servers to exchange. Applicable to
        monitors of type RADIUS and RADIUS_ACCOUNTING. Minimum length = 1

    radnasid(str): NAS-Identifier to send in the Access-Request packet. Applicable to monitors of type RADIUS. Minimum length
        = 1

    radnasip(str): Network Access Server (NAS) IP address to use as the source IP address when monitoring a RADIUS server.
        Applicable to monitors of type RADIUS and RADIUS_ACCOUNTING.

    radaccounttype(int): Account Type to be used in Account Request Packet. Applicable to monitors of type RADIUS_ACCOUNTING.
        Default value: 1 Minimum value = 0 Maximum value = 15

    radframedip(str): Source ip with which the packet will go out . Applicable to monitors of type RADIUS_ACCOUNTING.

    radapn(str): Called Station Id to be used in Account Request Packet. Applicable to monitors of type RADIUS_ACCOUNTING.
        Minimum length = 1

    radmsisdn(str): Calling Stations Id to be used in Account Request Packet. Applicable to monitors of type
        RADIUS_ACCOUNTING. Minimum length = 1

    radaccountsession(str): Account Session ID to be used in Account Request Packet. Applicable to monitors of type
        RADIUS_ACCOUNTING. Minimum length = 1

    lrtm(str): Calculate the least response times for bound services. If this parameter is not enabled, the appliance does
        not learn the response times of the bound services. Also used for LRTM load balancing. Possible values = ENABLED,
        DISABLED

    deviation(int): Time value added to the learned average response time in dynamic response time monitoring (DRTM). When a
        deviation is specified, the appliance learns the average response time of bound services and adds the deviation
        to the average. The final value is then continually adjusted to accommodate response time variations over time.
        Specified in milliseconds, seconds, or minutes. Minimum value = 0 Maximum value = 20939

    units1(str): Unit of measurement for the Deviation parameter. Cannot be changed after the monitor is created. Default
        value: SEC Possible values = SEC, MSEC, MIN

    interval(int): Time interval between two successive probes. Must be greater than the value of Response Time-out. Default
        value: 5 Minimum value = 1 Maximum value = 20940

    units3(str): monitor interval units. Default value: SEC Possible values = SEC, MSEC, MIN

    resptimeout(int): Amount of time for which the appliance must wait before it marks a probe as FAILED. Must be less than
        the value specified for the Interval parameter.  Note: For UDP-ECV monitors for which a receive string is not
        configured, response timeout does not apply. For UDP-ECV monitors with no receive string, probe failure is
        indicated by an ICMP port unreachable error received from the service. Default value: 2 Minimum value = 1 Maximum
        value = 20939

    units4(str): monitor response timeout units. Default value: SEC Possible values = SEC, MSEC, MIN

    resptimeoutthresh(int): Response time threshold, specified as a percentage of the Response Time-out parameter. If the
        response to a monitor probe has not arrived when the threshold is reached, the appliance generates an SNMP trap
        called monRespTimeoutAboveThresh. After the response time returns to a value below the threshold, the appliance
        generates a monRespTimeoutBelowThresh SNMP trap. For the traps to be generated, the "MONITOR-RTO-THRESHOLD" alarm
        must also be enabled. Minimum value = 0 Maximum value = 100

    retries(int): Maximum number of probes to send to establish the state of a service for which a monitoring probe failed.
        Default value: 3 Minimum value = 1 Maximum value = 127

    failureretries(int): Number of retries that must fail, out of the number specified for the Retries parameter, for a
        service to be marked as DOWN. For example, if the Retries parameter is set to 10 and the Failure Retries
        parameter is set to 6, out of the ten probes sent, at least six probes must fail if the service is to be marked
        as DOWN. The default value of 0 means that all the retries must fail if the service is to be marked as DOWN.
        Minimum value = 0 Maximum value = 32

    alertretries(int): Number of consecutive probe failures after which the appliance generates an SNMP trap called
        monProbeFailed. Minimum value = 0 Maximum value = 32

    successretries(int): Number of consecutive successful probes required to transition a services state from DOWN to UP.
        Default value: 1 Minimum value = 1 Maximum value = 32

    downtime(int): Time duration for which to wait before probing a service that has been marked as DOWN. Expressed in
        milliseconds, seconds, or minutes. Default value: 30 Minimum value = 1 Maximum value = 20939

    units2(str): Unit of measurement for the Down Time parameter. Cannot be changed after the monitor is created. Default
        value: SEC Possible values = SEC, MSEC, MIN

    destip(str): IP address of the service to which to send probes. If the parameter is set to 0, the IP address of the
        server to which the monitor is bound is considered the destination IP address.

    destport(int): TCP or UDP port to which to send the probe. If the parameter is set to 0, the port number of the service
        to which the monitor is bound is considered the destination port. For a monitor of type USER, however, the
        destination port is the port number that is included in the HTTP request sent to the dispatcher. Does not apply
        to monitors of type PING.

    state(str): State of the monitor. The DISABLED setting disables not only the monitor being configured, but all monitors
        of the same type, until the parameter is set to ENABLED. If the monitor is bound to a service, the state of the
        monitor is not taken into account when the state of the service is determined. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    reverse(str): Mark a service as DOWN, instead of UP, when probe criteria are satisfied, and as UP instead of DOWN when
        probe criteria are not satisfied. Default value: NO Possible values = YES, NO

    transparent(str): The monitor is bound to a transparent device such as a firewall or router. The state of a transparent
        device depends on the responsiveness of the services behind it. If a transparent device is being monitored, a
        destination IP address must be specified. The probe is sent to the specified IP address by using the MAC address
        of the transparent device. Default value: NO Possible values = YES, NO

    iptunnel(str): Send the monitoring probe to the service through an IP tunnel. A destination IP address must be specified.
        Default value: NO Possible values = YES, NO

    tos(str): Probe the service by encoding the destination IP address in the IP TOS (6) bits. Possible values = YES, NO

    tosid(int): The TOS ID of the specified destination IP. Applicable only when the TOS parameter is set. Minimum value = 1
        Maximum value = 63

    secure(str): Use a secure SSL connection when monitoring a service. Applicable only to TCP based monitors. The secure
        option cannot be used with a CITRIX-AG monitor, because a CITRIX-AG monitor uses a secure connection by default.
        Default value: NO Possible values = YES, NO

    validatecred(str): Validate the credentials of the Xen Desktop DDC server user. Applicable to monitors of type
        CITRIX-XD-DDC. Default value: NO Possible values = YES, NO

    domain(str): Domain in which the XenDesktop Desktop Delivery Controller (DDC) servers or Web Interface servers are
        present. Required by CITRIX-XD-DDC and CITRIX-WI-EXTENDED monitors for logging on to the DDC servers and Web
        Interface servers, respectively.

    ipaddress(list(str)): Set of IP addresses expected in the monitoring response from the DNS server, if the record type is
        A or AAAA. Applicable to DNS monitors. Minimum length = 1

    group(str): Name of a newsgroup available on the NNTP service that is to be monitored. The appliance periodically
        generates an NNTP query for the name of the newsgroup and evaluates the response. If the newsgroup is found on
        the server, the service is marked as UP. If the newsgroup does not exist or if the search fails, the service is
        marked as DOWN. Applicable to NNTP monitors. Minimum length = 1

    filename(str): Name of a file on the FTP server. The appliance monitors the FTP service by periodically checking the
        existence of the file on the server. Applicable to FTP-EXTENDED monitors. Minimum length = 1

    basedn(str): The base distinguished name of the LDAP service, from where the LDAP server can begin the search for the
        attributes in the monitoring query. Required for LDAP service monitoring. Minimum length = 1

    binddn(str): The distinguished name with which an LDAP monitor can perform the Bind operation on the LDAP server.
        Optional. Applicable to LDAP monitors. Minimum length = 1

    filter(str): Filter criteria for the LDAP query. Optional. Minimum length = 1

    attribute(str): Attribute to evaluate when the LDAP server responds to the query. Success or failure of the monitoring
        probe depends on whether the attribute exists in the response. Optional. Minimum length = 1

    database(str): Name of the database to connect to during authentication. Minimum length = 1

    oraclesid(str): Name of the service identifier that is used to connect to the Oracle database during authentication.
        Minimum length = 1

    sqlquery(str): SQL query for a MYSQL-ECV or MSSQL-ECV monitor. Sent to the database server after the server authenticates
        the connection. Minimum length = 1

    evalrule(str): Default syntax expression that evaluates the database servers response to a MYSQL-ECV or MSSQL-ECV
        monitoring query. Must produce a Boolean result. The result determines the state of the server. If the expression
        returns TRUE, the probe succeeds.  For example, if you want the appliance to evaluate the error message to
        determine the state of the server, use the rule MYSQL.RES.ROW(10) .TEXT_ELEM(2).EQ("MySQL").

    mssqlprotocolversion(str): Version of MSSQL server that is to be monitored. Default value: 70 Possible values = 70, 2000,
        2000SP1, 2005, 2008, 2008R2, 2012, 2014

    snmpoid(str): SNMP OID for SNMP monitors. Minimum length = 1

    snmpcommunity(str): Community name for SNMP monitors. Minimum length = 1

    snmpthreshold(str): Threshold for SNMP monitors. Minimum length = 1

    snmpversion(str): SNMP version to be used for SNMP monitors. Possible values = V1, V2

    metrictable(str): Metric table to which to bind metrics. Minimum length = 1 Maximum length = 99

    application(str): Name of the application used to determine the state of the service. Applicable to monitors of type
        CITRIX-XML-SERVICE. Minimum length = 1

    sitepath(str): URL of the logon page. For monitors of type CITRIX-WEB-INTERFACE, to monitor a dynamic page under the site
        path, terminate the site path with a slash (/). Applicable to CITRIX-WEB-INTERFACE, CITRIX-WI-EXTENDED and
        CITRIX-XDM monitors. Minimum length = 1

    storename(str): Store Name. For monitors of type STOREFRONT, STORENAME is an optional argument defining storefront
        service store name. Applicable to STOREFRONT monitors. Minimum length = 1

    storefrontacctservice(str): Enable/Disable probing for Account Service. Applicable only to Store Front monitors. For
        multi-tenancy configuration users my skip account service. Default value: YES Possible values = YES, NO

    hostname(str): Hostname in the FQDN format (Example: porche.cars.org). Applicable to STOREFRONT monitors. Minimum length
        = 1

    netprofile(str): Name of the network profile. Minimum length = 1 Maximum length = 127

    originhost(str): Origin-Host value for the Capabilities-Exchange-Request (CER) message to use for monitoring Diameter
        servers. Minimum length = 1

    originrealm(str): Origin-Realm value for the Capabilities-Exchange-Request (CER) message to use for monitoring Diameter
        servers. Minimum length = 1

    hostipaddress(str): Host-IP-Address value for the Capabilities-Exchange-Request (CER) message to use for monitoring
        Diameter servers. If Host-IP-Address is not specified, the appliance inserts the mapped IP (MIP) address or
        subnet IP (SNIP) address from which the CER request (the monitoring probe) is sent. Minimum length = 1

    vendorid(int): Vendor-Id value for the Capabilities-Exchange-Request (CER) message to use for monitoring Diameter
        servers.

    productname(str): Product-Name value for the Capabilities-Exchange-Request (CER) message to use for monitoring Diameter
        servers. Minimum length = 1

    firmwarerevision(int): Firmware-Revision value for the Capabilities-Exchange-Request (CER) message to use for monitoring
        Diameter servers.

    authapplicationid(list(int)): List of Auth-Application-Id attribute value pairs (AVPs) for the
        Capabilities-Exchange-Request (CER) message to use for monitoring Diameter servers. A maximum of eight of these
        AVPs are supported in a monitoring CER message. Minimum value = 0 Maximum value = 4294967295

    acctapplicationid(list(int)): List of Acct-Application-Id attribute value pairs (AVPs) for the
        Capabilities-Exchange-Request (CER) message to use for monitoring Diameter servers. A maximum of eight of these
        AVPs are supported in a monitoring message. Minimum value = 0 Maximum value = 4294967295

    inbandsecurityid(str): Inband-Security-Id for the Capabilities-Exchange-Request (CER) message to use for monitoring
        Diameter servers. Possible values = NO_INBAND_SECURITY, TLS

    supportedvendorids(list(int)): List of Supported-Vendor-Id attribute value pairs (AVPs) for the
        Capabilities-Exchange-Request (CER) message to use for monitoring Diameter servers. A maximum eight of these AVPs
        are supported in a monitoring message. Minimum value = 1 Maximum value = 4294967295

    vendorspecificvendorid(int): Vendor-Id to use in the Vendor-Specific-Application-Id grouped attribute-value pair (AVP) in
        the monitoring CER message. To specify Auth-Application-Id or Acct-Application-Id in
        Vendor-Specific-Application-Id, use vendorSpecificAuthApplicationIds or vendorSpecificAcctApplicationIds,
        respectively. Only one Vendor-Id is supported for all the Vendor-Specific-Application-Id AVPs in a CER monitoring
        message. Minimum value = 1

    vendorspecificauthapplicationids(list(int)): List of Vendor-Specific-Auth-Application-Id attribute value pairs (AVPs) for
        the Capabilities-Exchange-Request (CER) message to use for monitoring Diameter servers. A maximum of eight of
        these AVPs are supported in a monitoring message. The specified value is combined with the value of
        vendorSpecificVendorId to obtain the Vendor-Specific-Application-Id AVP in the CER monitoring message. Minimum
        value = 0 Maximum value = 4294967295

    vendorspecificacctapplicationids(list(int)): List of Vendor-Specific-Acct-Application-Id attribute value pairs (AVPs) to
        use for monitoring Diameter servers. A maximum of eight of these AVPs are supported in a monitoring message. The
        specified value is combined with the value of vendorSpecificVendorId to obtain the Vendor-Specific-Application-Id
        AVP in the CER monitoring message. Minimum value = 0 Maximum value = 4294967295

    kcdaccount(str): KCD Account used by MSSQL monitor. Minimum length = 1 Maximum length = 32

    storedb(str): Store the database list populated with the responses to monitor probes. Used in database specific load
        balancing if MSSQL-ECV/MYSQL-ECV monitor is configured. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    storefrontcheckbackendservices(str): This option will enable monitoring of services running on storefront server.
        Storefront services are monitored by probing to a Windows service that runs on the Storefront server and exposes
        details of which storefront services are running. Default value: NO Possible values = YES, NO

    trofscode(int): Code expected when the server is under maintenance.

    trofsstring(str): String expected from the server for the service to be marked as trofs. Applicable to HTTP-ECV/TCP-ECV
        monitors.

    sslprofile(str): SSL Profile associated with the monitor. Minimum length = 1 Maximum length = 127

    metric(str): Metric name in the metric table, whose setting is changed. A value zero disables the metric and it will not
        be used for load calculation. Minimum length = 1 Maximum length = 37

    metricthreshold(int): Threshold to be used for that metric.

    metricweight(int): The weight for the specified service metric with respect to others. Minimum value = 1 Maximum value =
        100

    servicename(str): The name of the service to which the monitor is bound. Minimum length = 1

    servicegroupname(str): The name of the service group to which the monitor is to be bound. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbmonitor <args>

    '''

    result = {}

    payload = {'lbmonitor': {}}

    if monitorname:
        payload['lbmonitor']['monitorname'] = monitorname

    if ns_type:
        payload['lbmonitor']['type'] = ns_type

    if action:
        payload['lbmonitor']['action'] = action

    if respcode:
        payload['lbmonitor']['respcode'] = respcode

    if httprequest:
        payload['lbmonitor']['httprequest'] = httprequest

    if rtsprequest:
        payload['lbmonitor']['rtsprequest'] = rtsprequest

    if customheaders:
        payload['lbmonitor']['customheaders'] = customheaders

    if maxforwards:
        payload['lbmonitor']['maxforwards'] = maxforwards

    if sipmethod:
        payload['lbmonitor']['sipmethod'] = sipmethod

    if sipuri:
        payload['lbmonitor']['sipuri'] = sipuri

    if sipreguri:
        payload['lbmonitor']['sipreguri'] = sipreguri

    if send:
        payload['lbmonitor']['send'] = send

    if recv:
        payload['lbmonitor']['recv'] = recv

    if query:
        payload['lbmonitor']['query'] = query

    if querytype:
        payload['lbmonitor']['querytype'] = querytype

    if scriptname:
        payload['lbmonitor']['scriptname'] = scriptname

    if scriptargs:
        payload['lbmonitor']['scriptargs'] = scriptargs

    if dispatcherip:
        payload['lbmonitor']['dispatcherip'] = dispatcherip

    if dispatcherport:
        payload['lbmonitor']['dispatcherport'] = dispatcherport

    if username:
        payload['lbmonitor']['username'] = username

    if password:
        payload['lbmonitor']['password'] = password

    if secondarypassword:
        payload['lbmonitor']['secondarypassword'] = secondarypassword

    if logonpointname:
        payload['lbmonitor']['logonpointname'] = logonpointname

    if lasversion:
        payload['lbmonitor']['lasversion'] = lasversion

    if radkey:
        payload['lbmonitor']['radkey'] = radkey

    if radnasid:
        payload['lbmonitor']['radnasid'] = radnasid

    if radnasip:
        payload['lbmonitor']['radnasip'] = radnasip

    if radaccounttype:
        payload['lbmonitor']['radaccounttype'] = radaccounttype

    if radframedip:
        payload['lbmonitor']['radframedip'] = radframedip

    if radapn:
        payload['lbmonitor']['radapn'] = radapn

    if radmsisdn:
        payload['lbmonitor']['radmsisdn'] = radmsisdn

    if radaccountsession:
        payload['lbmonitor']['radaccountsession'] = radaccountsession

    if lrtm:
        payload['lbmonitor']['lrtm'] = lrtm

    if deviation:
        payload['lbmonitor']['deviation'] = deviation

    if units1:
        payload['lbmonitor']['units1'] = units1

    if interval:
        payload['lbmonitor']['interval'] = interval

    if units3:
        payload['lbmonitor']['units3'] = units3

    if resptimeout:
        payload['lbmonitor']['resptimeout'] = resptimeout

    if units4:
        payload['lbmonitor']['units4'] = units4

    if resptimeoutthresh:
        payload['lbmonitor']['resptimeoutthresh'] = resptimeoutthresh

    if retries:
        payload['lbmonitor']['retries'] = retries

    if failureretries:
        payload['lbmonitor']['failureretries'] = failureretries

    if alertretries:
        payload['lbmonitor']['alertretries'] = alertretries

    if successretries:
        payload['lbmonitor']['successretries'] = successretries

    if downtime:
        payload['lbmonitor']['downtime'] = downtime

    if units2:
        payload['lbmonitor']['units2'] = units2

    if destip:
        payload['lbmonitor']['destip'] = destip

    if destport:
        payload['lbmonitor']['destport'] = destport

    if state:
        payload['lbmonitor']['state'] = state

    if reverse:
        payload['lbmonitor']['reverse'] = reverse

    if transparent:
        payload['lbmonitor']['transparent'] = transparent

    if iptunnel:
        payload['lbmonitor']['iptunnel'] = iptunnel

    if tos:
        payload['lbmonitor']['tos'] = tos

    if tosid:
        payload['lbmonitor']['tosid'] = tosid

    if secure:
        payload['lbmonitor']['secure'] = secure

    if validatecred:
        payload['lbmonitor']['validatecred'] = validatecred

    if domain:
        payload['lbmonitor']['domain'] = domain

    if ipaddress:
        payload['lbmonitor']['ipaddress'] = ipaddress

    if group:
        payload['lbmonitor']['group'] = group

    if filename:
        payload['lbmonitor']['filename'] = filename

    if basedn:
        payload['lbmonitor']['basedn'] = basedn

    if binddn:
        payload['lbmonitor']['binddn'] = binddn

    if filter:
        payload['lbmonitor']['filter'] = filter

    if attribute:
        payload['lbmonitor']['attribute'] = attribute

    if database:
        payload['lbmonitor']['database'] = database

    if oraclesid:
        payload['lbmonitor']['oraclesid'] = oraclesid

    if sqlquery:
        payload['lbmonitor']['sqlquery'] = sqlquery

    if evalrule:
        payload['lbmonitor']['evalrule'] = evalrule

    if mssqlprotocolversion:
        payload['lbmonitor']['mssqlprotocolversion'] = mssqlprotocolversion

    if snmpoid:
        payload['lbmonitor']['Snmpoid'] = snmpoid

    if snmpcommunity:
        payload['lbmonitor']['snmpcommunity'] = snmpcommunity

    if snmpthreshold:
        payload['lbmonitor']['snmpthreshold'] = snmpthreshold

    if snmpversion:
        payload['lbmonitor']['snmpversion'] = snmpversion

    if metrictable:
        payload['lbmonitor']['metrictable'] = metrictable

    if application:
        payload['lbmonitor']['application'] = application

    if sitepath:
        payload['lbmonitor']['sitepath'] = sitepath

    if storename:
        payload['lbmonitor']['storename'] = storename

    if storefrontacctservice:
        payload['lbmonitor']['storefrontacctservice'] = storefrontacctservice

    if hostname:
        payload['lbmonitor']['hostname'] = hostname

    if netprofile:
        payload['lbmonitor']['netprofile'] = netprofile

    if originhost:
        payload['lbmonitor']['originhost'] = originhost

    if originrealm:
        payload['lbmonitor']['originrealm'] = originrealm

    if hostipaddress:
        payload['lbmonitor']['hostipaddress'] = hostipaddress

    if vendorid:
        payload['lbmonitor']['vendorid'] = vendorid

    if productname:
        payload['lbmonitor']['productname'] = productname

    if firmwarerevision:
        payload['lbmonitor']['firmwarerevision'] = firmwarerevision

    if authapplicationid:
        payload['lbmonitor']['authapplicationid'] = authapplicationid

    if acctapplicationid:
        payload['lbmonitor']['acctapplicationid'] = acctapplicationid

    if inbandsecurityid:
        payload['lbmonitor']['inbandsecurityid'] = inbandsecurityid

    if supportedvendorids:
        payload['lbmonitor']['supportedvendorids'] = supportedvendorids

    if vendorspecificvendorid:
        payload['lbmonitor']['vendorspecificvendorid'] = vendorspecificvendorid

    if vendorspecificauthapplicationids:
        payload['lbmonitor']['vendorspecificauthapplicationids'] = vendorspecificauthapplicationids

    if vendorspecificacctapplicationids:
        payload['lbmonitor']['vendorspecificacctapplicationids'] = vendorspecificacctapplicationids

    if kcdaccount:
        payload['lbmonitor']['kcdaccount'] = kcdaccount

    if storedb:
        payload['lbmonitor']['storedb'] = storedb

    if storefrontcheckbackendservices:
        payload['lbmonitor']['storefrontcheckbackendservices'] = storefrontcheckbackendservices

    if trofscode:
        payload['lbmonitor']['trofscode'] = trofscode

    if trofsstring:
        payload['lbmonitor']['trofsstring'] = trofsstring

    if sslprofile:
        payload['lbmonitor']['sslprofile'] = sslprofile

    if metric:
        payload['lbmonitor']['metric'] = metric

    if metricthreshold:
        payload['lbmonitor']['metricthreshold'] = metricthreshold

    if metricweight:
        payload['lbmonitor']['metricweight'] = metricweight

    if servicename:
        payload['lbmonitor']['servicename'] = servicename

    if servicegroupname:
        payload['lbmonitor']['servicegroupname'] = servicegroupname

    execution = __proxy__['citrixns.post']('config/lbmonitor', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbmonitor_metric_binding(metric=None, metricthreshold=None, metricweight=None, monitorname=None, save=False):
    '''
    Add a new lbmonitor_metric_binding to the running configuration.

    metric(str): Metric name in the metric table, whose setting is changed. A value zero disables the metric and it will not
        be used for load calculation. Minimum length = 1 Maximum length = 37

    metricthreshold(int): Threshold to be used for that metric.

    metricweight(int): The weight for the specified service metric with respect to others. Minimum value = 1 Maximum value =
        100

    monitorname(str): Name of the monitor. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbmonitor_metric_binding <args>

    '''

    result = {}

    payload = {'lbmonitor_metric_binding': {}}

    if metric:
        payload['lbmonitor_metric_binding']['metric'] = metric

    if metricthreshold:
        payload['lbmonitor_metric_binding']['metricthreshold'] = metricthreshold

    if metricweight:
        payload['lbmonitor_metric_binding']['metricweight'] = metricweight

    if monitorname:
        payload['lbmonitor_metric_binding']['monitorname'] = monitorname

    execution = __proxy__['citrixns.post']('config/lbmonitor_metric_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbmonitor_service_binding(servicegroupname=None, dup_state=None, servicename=None, state=None, dup_weight=None,
                                  monitorname=None, weight=None, save=False):
    '''
    Add a new lbmonitor_service_binding to the running configuration.

    servicegroupname(str): Name of the service group. Minimum length = 1

    dup_state(str): State of the monitor. The state setting for a monitor of a given type affects all monitors of that type.
        For example, if an HTTP monitor is enabled, all HTTP monitors on the appliance are (or remain) enabled. If an
        HTTP monitor is disabled, all HTTP monitors on the appliance are disabled. Default value: ENABLED Possible values
        = ENABLED, DISABLED

    servicename(str): Name of the service or service group. Minimum length = 1

    state(str): State of the monitor. The state setting for a monitor of a given type affects all monitors of that type. For
        example, if an HTTP monitor is enabled, all HTTP monitors on the appliance are (or remain) enabled. If an HTTP
        monitor is disabled, all HTTP monitors on the appliance are disabled. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    dup_weight(int): Weight to assign to the binding between the monitor and service. Default value: 1 Minimum value = 1
        Maximum value = 100

    monitorname(str): Name of the monitor. Minimum length = 1

    weight(int): Weight to assign to the binding between the monitor and service. Minimum value = 1 Maximum value = 100

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbmonitor_service_binding <args>

    '''

    result = {}

    payload = {'lbmonitor_service_binding': {}}

    if servicegroupname:
        payload['lbmonitor_service_binding']['servicegroupname'] = servicegroupname

    if dup_state:
        payload['lbmonitor_service_binding']['dup_state'] = dup_state

    if servicename:
        payload['lbmonitor_service_binding']['servicename'] = servicename

    if state:
        payload['lbmonitor_service_binding']['state'] = state

    if dup_weight:
        payload['lbmonitor_service_binding']['dup_weight'] = dup_weight

    if monitorname:
        payload['lbmonitor_service_binding']['monitorname'] = monitorname

    if weight:
        payload['lbmonitor_service_binding']['weight'] = weight

    execution = __proxy__['citrixns.post']('config/lbmonitor_service_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbmonitor_servicegroup_binding(servicegroupname=None, dup_state=None, servicename=None, state=None,
                                       dup_weight=None, monitorname=None, weight=None, save=False):
    '''
    Add a new lbmonitor_servicegroup_binding to the running configuration.

    servicegroupname(str): Name of the service group. Minimum length = 1

    dup_state(str): State of the monitor. The state setting for a monitor of a given type affects all monitors of that type.
        For example, if an HTTP monitor is enabled, all HTTP monitors on the appliance are (or remain) enabled. If an
        HTTP monitor is disabled, all HTTP monitors on the appliance are disabled. Default value: ENABLED Possible values
        = ENABLED, DISABLED

    servicename(str): Name of the service or service group. Minimum length = 1

    state(str): State of the monitor. The state setting for a monitor of a given type affects all monitors of that type. For
        example, if an HTTP monitor is enabled, all HTTP monitors on the appliance are (or remain) enabled. If an HTTP
        monitor is disabled, all HTTP monitors on the appliance are disabled. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    dup_weight(int): Weight to assign to the binding between the monitor and service. Default value: 1 Minimum value = 1
        Maximum value = 100

    monitorname(str): Name of the monitor. Minimum length = 1

    weight(int): Weight to assign to the binding between the monitor and service. Minimum value = 1 Maximum value = 100

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbmonitor_servicegroup_binding <args>

    '''

    result = {}

    payload = {'lbmonitor_servicegroup_binding': {}}

    if servicegroupname:
        payload['lbmonitor_servicegroup_binding']['servicegroupname'] = servicegroupname

    if dup_state:
        payload['lbmonitor_servicegroup_binding']['dup_state'] = dup_state

    if servicename:
        payload['lbmonitor_servicegroup_binding']['servicename'] = servicename

    if state:
        payload['lbmonitor_servicegroup_binding']['state'] = state

    if dup_weight:
        payload['lbmonitor_servicegroup_binding']['dup_weight'] = dup_weight

    if monitorname:
        payload['lbmonitor_servicegroup_binding']['monitorname'] = monitorname

    if weight:
        payload['lbmonitor_servicegroup_binding']['weight'] = weight

    execution = __proxy__['citrixns.post']('config/lbmonitor_servicegroup_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbmonitor_sslcertkey_binding(crlcheck=None, ca=None, certkeyname=None, monitorname=None, ocspcheck=None,
                                     save=False):
    '''
    Add a new lbmonitor_sslcertkey_binding to the running configuration.

    crlcheck(str): The state of the CRL check parameter. (Mandatory/Optional). Possible values = Mandatory, Optional

    ca(bool): The rule for use of CRL corresponding to this CA certificate during client authentication. If crlCheck is set
        to Mandatory, the system will deny all SSL clients if the CRL is missing, expired - NextUpdate date is in the
        past, or is incomplete with remote CRL refresh enabled. If crlCheck is set to optional, the system will allow SSL
        clients in the above error cases.However, in any case if the client certificate is revoked in the CRL, the SSL
        client will be denied access.

    certkeyname(str): The name of the certificate bound to the monitor.

    monitorname(str): Name of the monitor. Minimum length = 1

    ocspcheck(str): The state of the OCSP check parameter. (Mandatory/Optional). Possible values = Mandatory, Optional

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbmonitor_sslcertkey_binding <args>

    '''

    result = {}

    payload = {'lbmonitor_sslcertkey_binding': {}}

    if crlcheck:
        payload['lbmonitor_sslcertkey_binding']['crlcheck'] = crlcheck

    if ca:
        payload['lbmonitor_sslcertkey_binding']['ca'] = ca

    if certkeyname:
        payload['lbmonitor_sslcertkey_binding']['certkeyname'] = certkeyname

    if monitorname:
        payload['lbmonitor_sslcertkey_binding']['monitorname'] = monitorname

    if ocspcheck:
        payload['lbmonitor_sslcertkey_binding']['ocspcheck'] = ocspcheck

    execution = __proxy__['citrixns.post']('config/lbmonitor_sslcertkey_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbprofile(lbprofilename=None, dbslb=None, processlocal=None, httponlycookieflag=None, cookiepassphrase=None,
                  usesecuredpersistencecookie=None, useencryptedpersistencecookie=None, save=False):
    '''
    Add a new lbprofile to the running configuration.

    lbprofilename(str): Name of the LB profile. Minimum length = 1

    dbslb(str): Enable database specific load balancing for MySQL and MSSQL service types. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    processlocal(str): By turning on this option packets destined to a vserver in a cluster will not under go any steering.
        Turn this option for single pa cket request response mode or when the upstream device is performing a proper RSS
        for connection based distribution. Default value: DISABLED Possible values = ENABLED, DISABLED

    httponlycookieflag(str): Include the HttpOnly attribute in persistence cookies. The HttpOnly attribute limits the scope
        of a cookie to HTTP requests and helps mitigate the risk of cross-site scripting attacks. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    cookiepassphrase(str): Use this parameter to specify the passphrase used to generate secured persistence cookie value. It
        specifies the passphrase with a maximum of 31 characters.

    usesecuredpersistencecookie(str): Encode persistence cookie values using SHA2 hash. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    useencryptedpersistencecookie(str): Encode persistence cookie values using SHA2 hash. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbprofile <args>

    '''

    result = {}

    payload = {'lbprofile': {}}

    if lbprofilename:
        payload['lbprofile']['lbprofilename'] = lbprofilename

    if dbslb:
        payload['lbprofile']['dbslb'] = dbslb

    if processlocal:
        payload['lbprofile']['processlocal'] = processlocal

    if httponlycookieflag:
        payload['lbprofile']['httponlycookieflag'] = httponlycookieflag

    if cookiepassphrase:
        payload['lbprofile']['cookiepassphrase'] = cookiepassphrase

    if usesecuredpersistencecookie:
        payload['lbprofile']['usesecuredpersistencecookie'] = usesecuredpersistencecookie

    if useencryptedpersistencecookie:
        payload['lbprofile']['useencryptedpersistencecookie'] = useencryptedpersistencecookie

    execution = __proxy__['citrixns.post']('config/lbprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbroute(network=None, netmask=None, gatewayname=None, td=None, save=False):
    '''
    Add a new lbroute to the running configuration.

    network(str): The IP address of the network to which the route belongs.

    netmask(str): The netmask to which the route belongs.

    gatewayname(str): The name of the route. Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Default value: 0
        Minimum value = 0 Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbroute <args>

    '''

    result = {}

    payload = {'lbroute': {}}

    if network:
        payload['lbroute']['network'] = network

    if netmask:
        payload['lbroute']['netmask'] = netmask

    if gatewayname:
        payload['lbroute']['gatewayname'] = gatewayname

    if td:
        payload['lbroute']['td'] = td

    execution = __proxy__['citrixns.post']('config/lbroute', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbroute6(network=None, gatewayname=None, td=None, save=False):
    '''
    Add a new lbroute6 to the running configuration.

    network(str): The destination network.

    gatewayname(str): The name of the route. Minimum length = 1

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Default value: 0
        Minimum value = 0 Maximum value = 4094

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbroute6 <args>

    '''

    result = {}

    payload = {'lbroute6': {}}

    if network:
        payload['lbroute6']['network'] = network

    if gatewayname:
        payload['lbroute6']['gatewayname'] = gatewayname

    if td:
        payload['lbroute6']['td'] = td

    execution = __proxy__['citrixns.post']('config/lbroute6', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver(name=None, servicetype=None, ipv46=None, ippattern=None, ipmask=None, port=None, range=None,
                  persistencetype=None, timeout=None, persistencebackup=None, backuppersistencetimeout=None,
                  lbmethod=None, hashlength=None, netmask=None, v6netmasklen=None, backuplbmethod=None, cookiename=None,
                  rule=None, listenpolicy=None, listenpriority=None, resrule=None, persistmask=None,
                  v6persistmasklen=None, pq=None, sc=None, rtspnat=None, m=None, tosid=None, datalength=None,
                  dataoffset=None, sessionless=None, trofspersistence=None, state=None, connfailover=None, redirurl=None,
                  cacheable=None, clttimeout=None, somethod=None, sopersistence=None, sopersistencetimeout=None,
                  healththreshold=None, sothreshold=None, sobackupaction=None, redirectportrewrite=None,
                  downstateflush=None, backupvserver=None, disableprimaryondown=None, insertvserveripport=None,
                  vipheader=None, authenticationhost=None, authentication=None, authn401=None, authnvsname=None,
                  push=None, pushvserver=None, pushlabel=None, pushmulticlients=None, tcpprofilename=None,
                  httpprofilename=None, dbprofilename=None, comment=None, l2conn=None, oracleserverversion=None,
                  mssqlserverversion=None, mysqlprotocolversion=None, mysqlserverversion=None, mysqlcharacterset=None,
                  mysqlservercapabilities=None, appflowlog=None, netprofile=None, icmpvsrresponse=None, rhistate=None,
                  newservicerequest=None, newservicerequestunit=None, newservicerequestincrementinterval=None,
                  minautoscalemembers=None, maxautoscalemembers=None, persistavpno=None, skippersistency=None, td=None,
                  authnprofile=None, macmoderetainvlan=None, dbslb=None, dns64=None, bypassaaaa=None,
                  recursionavailable=None, processlocal=None, dnsprofilename=None, lbprofilename=None,
                  redirectfromport=None, httpsredirecturl=None, retainconnectionsoncluster=None, weight=None,
                  servicename=None, redirurlflags=None, newname=None, save=False):
    '''
    Add a new lbvserver to the running configuration.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign (=),
        and hyphen (-) characters. Can be changed after the virtual server is created.  CLI Users: If the name includes
        one or more spaces, enclose the name in double or single quotation marks (for example, "my vserver" or my
        vserver). . Minimum length = 1

    servicetype(str): Protocol used by the service (also called the service type). Possible values = HTTP, FTP, TCP, UDP,
        SSL, SSL_BRIDGE, SSL_TCP, DTLS, NNTP, DNS, DHCPRA, ANY, SIP_UDP, SIP_TCP, SIP_SSL, DNS_TCP, RTSP, PUSH, SSL_PUSH,
        RADIUS, RDP, MYSQL, MSSQL, DIAMETER, SSL_DIAMETER, TFTP, ORACLE, SMPP, SYSLOGTCP, SYSLOGUDP, FIX, SSL_FIX,
        USER_TCP, USER_SSL_TCP

    ipv46(str): IPv4 or IPv6 address to assign to the virtual server.

    ippattern(str): IP address pattern, in dotted decimal notation, for identifying packets to be accepted by the virtual
        server. The IP Mask parameter specifies which part of the destination IP address is matched against the pattern.
        Mutually exclusive with the IP Address parameter.  For example, if the IP pattern assigned to the virtual server
        is 198.51.100.0 and the IP mask is 255.255.240.0 (a forward mask), the first 20 bits in the destination IP
        addresses are matched with the first 20 bits in the pattern. The virtual server accepts requests with IP
        addresses that range from 198.51.96.1 to 198.51.111.254. You can also use a pattern such as 0.0.2.2 and a mask
        such as 0.0.255.255 (a reverse mask). If a destination IP address matches more than one IP pattern, the pattern
        with the longest match is selected, and the associated virtual server processes the request. For example, if
        virtual servers vs1 and vs2 have the same IP pattern, 0.0.100.128, but different IP masks of 0.0.255.255 and
        0.0.224.255, a destination IP address of 198.51.100.128 has the longest match with the IP pattern of vs1. If a
        destination IP address matches two or more virtual servers to the same extent, the request is processed by the
        virtual server whose port number matches the port number in the request.

    ipmask(str): IP mask, in dotted decimal notation, for the IP Pattern parameter. Can have leading or trailing non-zero
        octets (for example, 255.255.240.0 or 0.0.255.255). Accordingly, the mask specifies whether the first n bits or
        the last n bits of the destination IP address in a client request are to be matched with the corresponding bits
        in the IP pattern. The former is called a forward mask. The latter is called a reverse mask.

    port(int): Port number for the virtual server. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    range(int): Number of IP addresses that the appliance must generate and assign to the virtual server. The virtual server
        then functions as a network virtual server, accepting traffic on any of the generated IP addresses. The IP
        addresses are generated automatically, as follows:  * For a range of n, the last octet of the address specified
        by the IP Address parameter increments n-1 times.  * If the last octet exceeds 255, it rolls over to 0 and the
        third octet increments by 1. Note: The Range parameter assigns multiple IP addresses to one virtual server. To
        generate an array of virtual servers, each of which owns only one IP address, use brackets in the IP Address and
        Name parameters to specify the range. For example: add lb vserver my_vserver[1-3] HTTP 192.0.2.[1-3] 80. Default
        value: 1 Minimum value = 1 Maximum value = 254

    persistencetype(str): Type of persistence for the virtual server. Available settings function as follows: * SOURCEIP -
        Connections from the same client IP address belong to the same persistence session. * COOKIEINSERT - Connections
        that have the same HTTP Cookie, inserted by a Set-Cookie directive from a server, belong to the same persistence
        session.  * SSLSESSION - Connections that have the same SSL Session ID belong to the same persistence session. *
        CUSTOMSERVERID - Connections with the same server ID form part of the same session. For this persistence type,
        set the Server ID (CustomServerID) parameter for each service and configure the Rule parameter to identify the
        server ID in a request. * RULE - All connections that match a user defined rule belong to the same persistence
        session.  * URLPASSIVE - Requests that have the same server ID in the URL query belong to the same persistence
        session. The server ID is the hexadecimal representation of the IP address and port of the service to which the
        request must be forwarded. This persistence type requires a rule to identify the server ID in the request.  *
        DESTIP - Connections to the same destination IP address belong to the same persistence session. * SRCIPDESTIP -
        Connections that have the same source IP address and destination IP address belong to the same persistence
        session. * CALLID - Connections that have the same CALL-ID SIP header belong to the same persistence session. *
        RTSPSID - Connections that have the same RTSP Session ID belong to the same persistence session. * FIXSESSION -
        Connections that have the same SenderCompID and TargetCompID values belong to the same persistence session. *
        USERSESSION - Persistence session is created based on the persistence parameter value provided from an extension.
        Possible values = SOURCEIP, COOKIEINSERT, SSLSESSION, RULE, URLPASSIVE, CUSTOMSERVERID, DESTIP, SRCIPDESTIP,
        CALLID, RTSPSID, DIAMETER, FIXSESSION, USERSESSION, NONE

    timeout(int): Time period for which a persistence session is in effect. Default value: 2 Minimum value = 0 Maximum value
        = 1440

    persistencebackup(str): Backup persistence type for the virtual server. Becomes operational if the primary persistence
        mechanism fails. Possible values = SOURCEIP, NONE

    backuppersistencetimeout(int): Time period for which backup persistence is in effect. Default value: 2 Minimum value = 2
        Maximum value = 1440

    lbmethod(str): Load balancing method. The available settings function as follows: * ROUNDROBIN - Distribute requests in
        rotation, regardless of the load. Weights can be assigned to services to enforce weighted round robin
        distribution. * LEASTCONNECTION (default) - Select the service with the fewest connections.  * LEASTRESPONSETIME
        - Select the service with the lowest average response time.  * LEASTBANDWIDTH - Select the service currently
        handling the least traffic. * LEASTPACKETS - Select the service currently serving the lowest number of packets
        per second. * CUSTOMLOAD - Base service selection on the SNMP metrics obtained by custom load monitors. * LRTM -
        Select the service with the lowest response time. Response times are learned through monitoring probes. This
        method also takes the number of active connections into account. Also available are a number of hashing methods,
        in which the appliance extracts a predetermined portion of the request, creates a hash of the portion, and then
        checks whether any previous requests had the same hash value. If it finds a match, it forwards the request to the
        service that served those previous requests. Following are the hashing methods:  * URLHASH - Create a hash of the
        request URL (or part of the URL). * DOMAINHASH - Create a hash of the domain name in the request (or part of the
        domain name). The domain name is taken from either the URL or the Host header. If the domain name appears in both
        locations, the URL is preferred. If the request does not contain a domain name, the load balancing method
        defaults to LEASTCONNECTION. * DESTINATIONIPHASH - Create a hash of the destination IP address in the IP header.
        * SOURCEIPHASH - Create a hash of the source IP address in the IP header.  * TOKEN - Extract a token from the
        request, create a hash of the token, and then select the service to which any previous requests with the same
        token hash value were sent.  * SRCIPDESTIPHASH - Create a hash of the string obtained by concatenating the source
        IP address and destination IP address in the IP header.  * SRCIPSRCPORTHASH - Create a hash of the source IP
        address and source port in the IP header.  * CALLIDHASH - Create a hash of the SIP Call-ID header. * USER_TOKEN -
        Same as TOKEN LB method but token needs to be provided from an extension. Default value: LEASTCONNECTION Possible
        values = ROUNDROBIN, LEASTCONNECTION, LEASTRESPONSETIME, URLHASH, DOMAINHASH, DESTINATIONIPHASH, SOURCEIPHASH,
        SRCIPDESTIPHASH, LEASTBANDWIDTH, LEASTPACKETS, TOKEN, SRCIPSRCPORTHASH, LRTM, CALLIDHASH, CUSTOMLOAD,
        LEASTREQUEST, AUDITLOGHASH, STATICPROXIMITY, USER_TOKEN

    hashlength(int): Number of bytes to consider for the hash value used in the URLHASH and DOMAINHASH load balancing
        methods. Default value: 80 Minimum value = 1 Maximum value = 4096

    netmask(str): IPv4 subnet mask to apply to the destination IP address or source IP address when the load balancing method
        is DESTINATIONIPHASH or SOURCEIPHASH. Minimum length = 1

    v6netmasklen(int): Number of bits to consider in an IPv6 destination or source IP address, for creating the hash that is
        required by the DESTINATIONIPHASH and SOURCEIPHASH load balancing methods. Default value: 128 Minimum value = 1
        Maximum value = 128

    backuplbmethod(str): Backup load balancing method. Becomes operational if the primary load balancing me thod fails or
        cannot be used.  Valid only if the primary method is based on static proximity. Default value: ROUNDROBIN
        Possible values = ROUNDROBIN, LEASTCONNECTION, LEASTRESPONSETIME, SOURCEIPHASH, LEASTBANDWIDTH, LEASTPACKETS,
        CUSTOMLOAD

    cookiename(str): Use this parameter to specify the cookie name for COOKIE peristence type. It specifies the name of
        cookie with a maximum of 32 characters. If not specified, cookie name is internally generated.

    rule(str): Expression, or name of a named expression, against which traffic is evaluated. Written in the classic or
        default syntax. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can
        be split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;" The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks. Default value: "none"

    listenpolicy(str): Default syntax expression identifying traffic accepted by the virtual server. Can be either an
        expression (for example, CLIENT.IP.DST.IN_SUBNET(192.0.2.0/24) or the name of a named expression. In the above
        example, the virtual server accepts all requests whose destination IP address is in the 192.0.2.0/24 subnet.
        Default value: "NONE"

    listenpriority(int): Integer specifying the priority of the listen policy. A higher number specifies a lower priority. If
        a request matches the listen policies of more than one virtual server the virtual server whose listen policy has
        the highest priority (the lowest priority number) accepts the request. Default value: 101 Minimum value = 0
        Maximum value = 101

    resrule(str): Default syntax expression specifying which part of a servers response to use for creating rule based
        persistence sessions (persistence type RULE). Can be either an expression or the name of a named expression.
        Example: HTTP.RES.HEADER("setcookie").VALUE(0).TYPECAST_NVLIST_T(=,;).VALUE("server1"). Default value: "none"

    persistmask(str): Persistence mask for IP based persistence types, for IPv4 virtual servers. Minimum length = 1

    v6persistmasklen(int): Persistence mask for IP based persistence types, for IPv6 virtual servers. Default value: 128
        Minimum value = 1 Maximum value = 128

    pq(str): Use priority queuing on the virtual server. based persistence types, for IPv6 virtual servers. Default value:
        OFF Possible values = ON, OFF

    sc(str): Use SureConnect on the virtual server. Default value: OFF Possible values = ON, OFF

    rtspnat(str): Use network address translation (NAT) for RTSP data connections. Default value: OFF Possible values = ON,
        OFF

    m(str): Redirection mode for load balancing. Available settings function as follows: * IP - Before forwarding a request
        to a server, change the destination IP address to the servers IP address.  * MAC - Before forwarding a request to
        a server, change the destination MAC address to the servers MAC address. The destination IP address is not
        changed. MAC-based redirection mode is used mostly in firewall load balancing deployments.  * IPTUNNEL - Perform
        IP-in-IP encapsulation for client IP packets. In the outer IP headers, set the destination IP address to the IP
        address of the server and the source IP address to the subnet IP (SNIP). The client IP packets are not modified.
        Applicable to both IPv4 and IPv6 packets.  * TOS - Encode the virtual servers TOS ID in the TOS field of the IP
        header.  You can use either the IPTUNNEL or the TOS option to implement Direct Server Return (DSR). Default
        value: IP Possible values = IP, MAC, IPTUNNEL, TOS

    tosid(int): TOS ID of the virtual server. Applicable only when the load balancing redirection mode is set to TOS. Minimum
        value = 1 Maximum value = 63

    datalength(int): Length of the token to be extracted from the data segment of an incoming packet, for use in the token
        method of load balancing. The length of the token, specified in bytes, must not be greater than 24 KB. Applicable
        to virtual servers of type TCP. Minimum value = 1 Maximum value = 100

    dataoffset(int): Offset to be considered when extracting a token from the TCP payload. Applicable to virtual servers, of
        type TCP, using the token method of load balancing. Must be within the first 24 KB of the TCP payload. Minimum
        value = 0 Maximum value = 25400

    sessionless(str): Perform load balancing on a per-packet basis, without establishing sessions. Recommended for load
        balancing of intrusion detection system (IDS) servers and scenarios involving direct server return (DSR), where
        session information is unnecessary. Default value: DISABLED Possible values = ENABLED, DISABLED

    trofspersistence(str): When value is ENABLED, Trofs persistence is honored. When value is DISABLED, Trofs persistence is
        not honored. Default value: ENABLED Possible values = ENABLED, DISABLED

    state(str): State of the load balancing virtual server. Default value: ENABLED Possible values = ENABLED, DISABLED

    connfailover(str): Mode in which the connection failover feature must operate for the virtual server. After a failover,
        established TCP connections and UDP packet flows are kept active and resumed on the secondary appliance. Clients
        remain connected to the same servers. Available settings function as follows: * STATEFUL - The primary appliance
        shares state information with the secondary appliance, in real time, resulting in some runtime processing
        overhead.  * STATELESS - State information is not shared, and the new primary appliance tries to re-create the
        packet flow on the basis of the information contained in the packets it receives.  * DISABLED - Connection
        failover does not occur. Default value: DISABLED Possible values = DISABLED, STATEFUL, STATELESS

    redirurl(str): URL to which to redirect traffic if the virtual server becomes unavailable.  WARNING! Make sure that the
        domain in the URL does not match the domain specified for a content switching policy. If it does, requests are
        continuously redirected to the unavailable virtual server. Minimum length = 1

    cacheable(str): Route cacheable requests to a cache redirection virtual server. The load balancing virtual server can
        forward requests only to a transparent cache redirection virtual server that has an IP address and port
        combination of *:80, so such a cache redirection virtual server must be configured on the appliance. Default
        value: NO Possible values = YES, NO

    clttimeout(int): Idle time, in seconds, after which a client connection is terminated. Minimum value = 0 Maximum value =
        31536000

    somethod(str): Type of threshold that, when exceeded, triggers spillover. Available settings function as follows: *
        CONNECTION - Spillover occurs when the number of client connections exceeds the threshold. * DYNAMICCONNECTION -
        Spillover occurs when the number of client connections at the virtual server exceeds the sum of the maximum
        client (Max Clients) settings for bound services. Do not specify a spillover threshold for this setting, because
        the threshold is implied by the Max Clients settings of bound services. * BANDWIDTH - Spillover occurs when the
        bandwidth consumed by the virtual servers incoming and outgoing traffic exceeds the threshold.  * HEALTH -
        Spillover occurs when the percentage of weights of the services that are UP drops below the threshold. For
        example, if services svc1, svc2, and svc3 are bound to a virtual server, with weights 1, 2, and 3, and the
        spillover threshold is 50%, spillover occurs if svc1 and svc3 or svc2 and svc3 transition to DOWN.  * NONE -
        Spillover does not occur. Possible values = CONNECTION, DYNAMICCONNECTION, BANDWIDTH, HEALTH, NONE

    sopersistence(str): If spillover occurs, maintain source IP address based persistence for both primary and backup virtual
        servers. Default value: DISABLED Possible values = ENABLED, DISABLED

    sopersistencetimeout(int): Timeout for spillover persistence, in minutes. Default value: 2 Minimum value = 2 Maximum
        value = 1440

    healththreshold(int): Threshold in percent of active services below which vserver state is made down. If this threshold
        is 0, vserver state will be up even if one bound service is up. Default value: 0 Minimum value = 0 Maximum value
        = 100

    sothreshold(int): Threshold at which spillover occurs. Specify an integer for the CONNECTION spillover method, a
        bandwidth value in kilobits per second for the BANDWIDTH method (do not enter the units), or a percentage for the
        HEALTH method (do not enter the percentage symbol). Minimum value = 1 Maximum value = 4294967287

    sobackupaction(str): Action to be performed if spillover is to take effect, but no backup chain to spillover is usable or
        exists. Possible values = DROP, ACCEPT, REDIRECT

    redirectportrewrite(str): Rewrite the port and change the protocol to ensure successful HTTP redirects from services.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    downstateflush(str): Flush all active transactions associated with a virtual server whose state transitions from UP to
        DOWN. Do not enable this option for applications that must complete their transactions. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    backupvserver(str): Name of the backup virtual server to which to forward requests if the primary virtual server goes
        DOWN or reaches its spillover threshold. Minimum length = 1

    disableprimaryondown(str): If the primary virtual server goes down, do not allow it to return to primary status until
        manually enabled. Default value: DISABLED Possible values = ENABLED, DISABLED

    insertvserveripport(str): Insert an HTTP header, whose value is the IP address and port number of the virtual server,
        before forwarding a request to the server. The format of the header is ;lt;vipHeader;gt;: ;lt;virtual server IP
        address;gt;_;lt;port number ;gt;, where vipHeader is the name that you specify for the header. If the virtual
        server has an IPv6 address, the address in the header is enclosed in brackets ([ and ]) to separate it from the
        port number. If you have mapped an IPv4 address to a virtual servers IPv6 address, the value of this parameter
        determines which IP address is inserted in the header, as follows: * VIPADDR - Insert the IP address of the
        virtual server in the HTTP header regardless of whether the virtual server has an IPv4 address or an IPv6
        address. A mapped IPv4 address, if configured, is ignored. * V6TOV4MAPPING - Insert the IPv4 address that is
        mapped to the virtual servers IPv6 address. If a mapped IPv4 address is not configured, insert the IPv6 address.
        * OFF - Disable header insertion. Possible values = OFF, VIPADDR, V6TOV4MAPPING

    vipheader(str): Name for the inserted header. The default name is vip-header. Minimum length = 1

    authenticationhost(str): Fully qualified domain name (FQDN) of the authentication virtual server to which the user must
        be redirected for authentication. Make sure that the Authentication parameter is set to ENABLED. Minimum length =
        3 Maximum length = 252

    authentication(str): Enable or disable user authentication. Default value: OFF Possible values = ON, OFF

    authn401(str): Enable or disable user authentication with HTTP 401 responses. Default value: OFF Possible values = ON,
        OFF

    authnvsname(str): Name of an authentication virtual server with which to authenticate users. Minimum length = 1 Maximum
        length = 252

    push(str): Process traffic with the push virtual server that is bound to this load balancing virtual server. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    pushvserver(str): Name of the load balancing virtual server, of type PUSH or SSL_PUSH, to which the server pushes updates
        received on the load balancing virtual server that you are configuring. Minimum length = 1

    pushlabel(str): Expression for extracting a label from the servers response. Can be either an expression or the name of a
        named expression. Default value: "none"

    pushmulticlients(str): Allow multiple Web 2.0 connections from the same client to connect to the virtual server and
        expect updates. Default value: NO Possible values = YES, NO

    tcpprofilename(str): Name of the TCP profile whose settings are to be applied to the virtual server. Minimum length = 1
        Maximum length = 127

    httpprofilename(str): Name of the HTTP profile whose settings are to be applied to the virtual server. Minimum length = 1
        Maximum length = 127

    dbprofilename(str): Name of the DB profile whose settings are to be applied to the virtual server. Minimum length = 1
        Maximum length = 127

    comment(str): Any comments that you might want to associate with the virtual server.

    l2conn(str): Use Layer 2 parameters (channel number, MAC address, and VLAN ID) in addition to the 4-tuple (;lt;source
        IP;gt;:;lt;source port;gt;::;lt;destination IP;gt;:;lt;destination port;gt;) that is used to identify a
        connection. Allows multiple TCP and non-TCP connections with the same 4-tuple to co-exist on the NetScaler
        appliance. Possible values = ON, OFF

    oracleserverversion(str): Oracle server version. Default value: 10G Possible values = 10G, 11G

    mssqlserverversion(str): For a load balancing virtual server of type MSSQL, the Microsoft SQL Server version. Set this
        parameter if you expect some clients to run a version different from the version of the database. This setting
        provides compatibility between the client-side and server-side connections by ensuring that all communication
        conforms to the servers version. Default value: 2008R2 Possible values = 70, 2000, 2000SP1, 2005, 2008, 2008R2,
        2012, 2014

    mysqlprotocolversion(int): MySQL protocol version that the virtual server advertises to clients.

    mysqlserverversion(str): MySQL server version string that the virtual server advertises to clients. Minimum length = 1
        Maximum length = 31

    mysqlcharacterset(int): Character set that the virtual server advertises to clients.

    mysqlservercapabilities(int): Server capabilities that the virtual server advertises to clients.

    appflowlog(str): Apply AppFlow logging to the virtual server. Default value: ENABLED Possible values = ENABLED, DISABLED

    netprofile(str): Name of the network profile to associate with the virtual server. If you set this parameter, the virtual
        server uses only the IP addresses in the network profile as source IP addresses when initiating connections with
        servers. Minimum length = 1 Maximum length = 127

    icmpvsrresponse(str): How the NetScaler appliance responds to ping requests received for an IP address that is common to
        one or more virtual servers. Available settings function as follows: * If set to PASSIVE on all the virtual
        servers that share the IP address, the appliance always responds to the ping requests. * If set to ACTIVE on all
        the virtual servers that share the IP address, the appliance responds to the ping requests if at least one of the
        virtual servers is UP. Otherwise, the appliance does not respond. * If set to ACTIVE on some virtual servers and
        PASSIVE on the others, the appliance responds if at least one virtual server with the ACTIVE setting is UP.
        Otherwise, the appliance does not respond. Note: This parameter is available at the virtual server level. A
        similar parameter, ICMP Response, is available at the IP address level, for IPv4 addresses of type VIP. To set
        that parameter, use the add ip command in the CLI or the Create IP dialog box in the GUI. Default value: PASSIVE
        Possible values = PASSIVE, ACTIVE

    rhistate(str): Route Health Injection (RHI) functionality of the NetSaler appliance for advertising the route of the VIP
        address associated with the virtual server. When Vserver RHI Level (RHI) parameter is set to VSVR_CNTRLD, the
        following are different RHI behaviors for the VIP address on the basis of RHIstate (RHI STATE) settings on the
        virtual servers associated with the VIP address: * If you set RHI STATE to PASSIVE on all virtual servers, the
        NetScaler ADC always advertises the route for the VIP address. * If you set RHI STATE to ACTIVE on all virtual
        servers, the NetScaler ADC advertises the route for the VIP address if at least one of the associated virtual
        servers is in UP state. * If you set RHI STATE to ACTIVE on some and PASSIVE on others, the NetScaler ADC
        advertises the route for the VIP address if at least one of the associated virtual servers, whose RHI STATE set
        to ACTIVE, is in UP state. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    newservicerequest(int): Number of requests, or percentage of the load on existing services, by which to increase the load
        on a new service at each interval in slow-start mode. A non-zero value indicates that slow-start is applicable. A
        zero value indicates that the global RR startup parameter is applied. Changing the value to zero will cause
        services currently in slow start to take the full traffic as determined by the LB method. Subsequently, any new
        services added will use the global RR factor. Default value: 0

    newservicerequestunit(str): Units in which to increment load at each interval in slow-start mode. Default value:
        PER_SECOND Possible values = PER_SECOND, PERCENT

    newservicerequestincrementinterval(int): Interval, in seconds, between successive increments in the load on a new service
        or a service whose state has just changed from DOWN to UP. A value of 0 (zero) specifies manual slow start.
        Default value: 0 Minimum value = 0 Maximum value = 3600

    minautoscalemembers(int): Minimum number of members expected to be present when vserver is used in Autoscale. Default
        value: 0 Minimum value = 0 Maximum value = 5000

    maxautoscalemembers(int): Maximum number of members expected to be present when vserver is used in Autoscale. Default
        value: 0 Minimum value = 0 Maximum value = 5000

    persistavpno(list(int)): Persist AVP number for Diameter Persistency.   In case this AVP is not defined in Base RFC 3588
        and it is nested inside a Grouped AVP,   define a sequence of AVP numbers (max 3) in order of parent to child. So
        say persist AVP number X   is nested inside AVP Y which is nested in Z, then define the list as Z Y X. Minimum
        value = 1

    skippersistency(str): This argument decides the behavior incase the service which is selected from an existing
        persistence session has reached threshold. Default value: None Possible values = Bypass, ReLb, None

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    authnprofile(str): Name of the authentication profile to be used when authentication is turned on.

    macmoderetainvlan(str): This option is used to retain vlan information of incoming packet when macmode is enabled.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    dbslb(str): Enable database specific load balancing for MySQL and MSSQL service types. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    dns64(str): This argument is for enabling/disabling the dns64 on lbvserver. Possible values = ENABLED, DISABLED

    bypassaaaa(str): If this option is enabled while resolving DNS64 query AAAA queries are not sent to back end dns server.
        Default value: NO Possible values = YES, NO

    recursionavailable(str): When set to YES, this option causes the DNS replies from this vserver to have the RA bit turned
        on. Typically one would set this option to YES, when the vserver is load balancing a set of DNS servers
        thatsupport recursive queries. Default value: NO Possible values = YES, NO

    processlocal(str): By turning on this option packets destined to a vserver in a cluster will not under go any steering.
        Turn this option for single packet request response mode or when the upstream device is performing a proper RSS
        for connection based distribution. Default value: DISABLED Possible values = ENABLED, DISABLED

    dnsprofilename(str): Name of the DNS profile to be associated with the VServer. DNS profile properties will be applied to
        the transactions processed by a VServer. This parameter is valid only for DNS and DNS-TCP VServers. Minimum
        length = 1 Maximum length = 127

    lbprofilename(str): Name of the LB profile which is associated to the vserver.

    redirectfromport(int): Port number for the virtual server, from which we absorb the traffic for http redirect. Minimum
        value = 1 Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    httpsredirecturl(str): URL to which to redirect traffic if the traffic is recieved from redirect port.

    retainconnectionsoncluster(str): This option enables you to retain existing connections on a node joining a Cluster
        system or when a node is being configured for passive timeout. By default, this option is disabled. Default
        value: NO Possible values = YES, NO

    weight(int): Weight to assign to the specified service. Minimum value = 1 Maximum value = 100

    servicename(str): Service to bind to the virtual server. Minimum length = 1

    redirurlflags(bool): The redirect URL to be unset.

    newname(str): New name for the virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver <args>

    '''

    result = {}

    payload = {'lbvserver': {}}

    if name:
        payload['lbvserver']['name'] = name

    if servicetype:
        payload['lbvserver']['servicetype'] = servicetype

    if ipv46:
        payload['lbvserver']['ipv46'] = ipv46

    if ippattern:
        payload['lbvserver']['ippattern'] = ippattern

    if ipmask:
        payload['lbvserver']['ipmask'] = ipmask

    if port:
        payload['lbvserver']['port'] = port

    if range:
        payload['lbvserver']['range'] = range

    if persistencetype:
        payload['lbvserver']['persistencetype'] = persistencetype

    if timeout:
        payload['lbvserver']['timeout'] = timeout

    if persistencebackup:
        payload['lbvserver']['persistencebackup'] = persistencebackup

    if backuppersistencetimeout:
        payload['lbvserver']['backuppersistencetimeout'] = backuppersistencetimeout

    if lbmethod:
        payload['lbvserver']['lbmethod'] = lbmethod

    if hashlength:
        payload['lbvserver']['hashlength'] = hashlength

    if netmask:
        payload['lbvserver']['netmask'] = netmask

    if v6netmasklen:
        payload['lbvserver']['v6netmasklen'] = v6netmasklen

    if backuplbmethod:
        payload['lbvserver']['backuplbmethod'] = backuplbmethod

    if cookiename:
        payload['lbvserver']['cookiename'] = cookiename

    if rule:
        payload['lbvserver']['rule'] = rule

    if listenpolicy:
        payload['lbvserver']['listenpolicy'] = listenpolicy

    if listenpriority:
        payload['lbvserver']['listenpriority'] = listenpriority

    if resrule:
        payload['lbvserver']['resrule'] = resrule

    if persistmask:
        payload['lbvserver']['persistmask'] = persistmask

    if v6persistmasklen:
        payload['lbvserver']['v6persistmasklen'] = v6persistmasklen

    if pq:
        payload['lbvserver']['pq'] = pq

    if sc:
        payload['lbvserver']['sc'] = sc

    if rtspnat:
        payload['lbvserver']['rtspnat'] = rtspnat

    if m:
        payload['lbvserver']['m'] = m

    if tosid:
        payload['lbvserver']['tosid'] = tosid

    if datalength:
        payload['lbvserver']['datalength'] = datalength

    if dataoffset:
        payload['lbvserver']['dataoffset'] = dataoffset

    if sessionless:
        payload['lbvserver']['sessionless'] = sessionless

    if trofspersistence:
        payload['lbvserver']['trofspersistence'] = trofspersistence

    if state:
        payload['lbvserver']['state'] = state

    if connfailover:
        payload['lbvserver']['connfailover'] = connfailover

    if redirurl:
        payload['lbvserver']['redirurl'] = redirurl

    if cacheable:
        payload['lbvserver']['cacheable'] = cacheable

    if clttimeout:
        payload['lbvserver']['clttimeout'] = clttimeout

    if somethod:
        payload['lbvserver']['somethod'] = somethod

    if sopersistence:
        payload['lbvserver']['sopersistence'] = sopersistence

    if sopersistencetimeout:
        payload['lbvserver']['sopersistencetimeout'] = sopersistencetimeout

    if healththreshold:
        payload['lbvserver']['healththreshold'] = healththreshold

    if sothreshold:
        payload['lbvserver']['sothreshold'] = sothreshold

    if sobackupaction:
        payload['lbvserver']['sobackupaction'] = sobackupaction

    if redirectportrewrite:
        payload['lbvserver']['redirectportrewrite'] = redirectportrewrite

    if downstateflush:
        payload['lbvserver']['downstateflush'] = downstateflush

    if backupvserver:
        payload['lbvserver']['backupvserver'] = backupvserver

    if disableprimaryondown:
        payload['lbvserver']['disableprimaryondown'] = disableprimaryondown

    if insertvserveripport:
        payload['lbvserver']['insertvserveripport'] = insertvserveripport

    if vipheader:
        payload['lbvserver']['vipheader'] = vipheader

    if authenticationhost:
        payload['lbvserver']['authenticationhost'] = authenticationhost

    if authentication:
        payload['lbvserver']['authentication'] = authentication

    if authn401:
        payload['lbvserver']['authn401'] = authn401

    if authnvsname:
        payload['lbvserver']['authnvsname'] = authnvsname

    if push:
        payload['lbvserver']['push'] = push

    if pushvserver:
        payload['lbvserver']['pushvserver'] = pushvserver

    if pushlabel:
        payload['lbvserver']['pushlabel'] = pushlabel

    if pushmulticlients:
        payload['lbvserver']['pushmulticlients'] = pushmulticlients

    if tcpprofilename:
        payload['lbvserver']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['lbvserver']['httpprofilename'] = httpprofilename

    if dbprofilename:
        payload['lbvserver']['dbprofilename'] = dbprofilename

    if comment:
        payload['lbvserver']['comment'] = comment

    if l2conn:
        payload['lbvserver']['l2conn'] = l2conn

    if oracleserverversion:
        payload['lbvserver']['oracleserverversion'] = oracleserverversion

    if mssqlserverversion:
        payload['lbvserver']['mssqlserverversion'] = mssqlserverversion

    if mysqlprotocolversion:
        payload['lbvserver']['mysqlprotocolversion'] = mysqlprotocolversion

    if mysqlserverversion:
        payload['lbvserver']['mysqlserverversion'] = mysqlserverversion

    if mysqlcharacterset:
        payload['lbvserver']['mysqlcharacterset'] = mysqlcharacterset

    if mysqlservercapabilities:
        payload['lbvserver']['mysqlservercapabilities'] = mysqlservercapabilities

    if appflowlog:
        payload['lbvserver']['appflowlog'] = appflowlog

    if netprofile:
        payload['lbvserver']['netprofile'] = netprofile

    if icmpvsrresponse:
        payload['lbvserver']['icmpvsrresponse'] = icmpvsrresponse

    if rhistate:
        payload['lbvserver']['rhistate'] = rhistate

    if newservicerequest:
        payload['lbvserver']['newservicerequest'] = newservicerequest

    if newservicerequestunit:
        payload['lbvserver']['newservicerequestunit'] = newservicerequestunit

    if newservicerequestincrementinterval:
        payload['lbvserver']['newservicerequestincrementinterval'] = newservicerequestincrementinterval

    if minautoscalemembers:
        payload['lbvserver']['minautoscalemembers'] = minautoscalemembers

    if maxautoscalemembers:
        payload['lbvserver']['maxautoscalemembers'] = maxautoscalemembers

    if persistavpno:
        payload['lbvserver']['persistavpno'] = persistavpno

    if skippersistency:
        payload['lbvserver']['skippersistency'] = skippersistency

    if td:
        payload['lbvserver']['td'] = td

    if authnprofile:
        payload['lbvserver']['authnprofile'] = authnprofile

    if macmoderetainvlan:
        payload['lbvserver']['macmoderetainvlan'] = macmoderetainvlan

    if dbslb:
        payload['lbvserver']['dbslb'] = dbslb

    if dns64:
        payload['lbvserver']['dns64'] = dns64

    if bypassaaaa:
        payload['lbvserver']['bypassaaaa'] = bypassaaaa

    if recursionavailable:
        payload['lbvserver']['recursionavailable'] = recursionavailable

    if processlocal:
        payload['lbvserver']['processlocal'] = processlocal

    if dnsprofilename:
        payload['lbvserver']['dnsprofilename'] = dnsprofilename

    if lbprofilename:
        payload['lbvserver']['lbprofilename'] = lbprofilename

    if redirectfromport:
        payload['lbvserver']['redirectfromport'] = redirectfromport

    if httpsredirecturl:
        payload['lbvserver']['httpsredirecturl'] = httpsredirecturl

    if retainconnectionsoncluster:
        payload['lbvserver']['retainconnectionsoncluster'] = retainconnectionsoncluster

    if weight:
        payload['lbvserver']['weight'] = weight

    if servicename:
        payload['lbvserver']['servicename'] = servicename

    if redirurlflags:
        payload['lbvserver']['redirurlflags'] = redirurlflags

    if newname:
        payload['lbvserver']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/lbvserver', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_appflowpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                        save=False):
    '''
    Add a new lbvserver_appflowpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the label invoked.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_appflowpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_appflowpolicy_binding': {}}

    if priority:
        payload['lbvserver_appflowpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_appflowpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_appflowpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_appflowpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_appflowpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_appflowpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_appfwpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      save=False):
    '''
    Add a new lbvserver_appfwpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the label invoked.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_appfwpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_appfwpolicy_binding': {}}

    if priority:
        payload['lbvserver_appfwpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_appfwpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_appfwpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_appfwpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_appfwpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_appfwpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_appqoepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                       save=False):
    '''
    Add a new lbvserver_appqoepolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_appqoepolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_appqoepolicy_binding': {}}

    if priority:
        payload['lbvserver_appqoepolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_appqoepolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_appqoepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_appqoepolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_appqoepolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_appqoepolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_auditnslogpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                           save=False):
    '''
    Add a new lbvserver_auditnslogpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): Bind point to which to bind the policy. Applicable only to compression, rewrite, and cache policies.
        Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_auditnslogpolicy_binding': {}}

    if priority:
        payload['lbvserver_auditnslogpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_auditnslogpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_auditnslogpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_auditnslogpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_auditnslogpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_auditnslogpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_auditsyslogpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                            save=False):
    '''
    Add a new lbvserver_auditsyslogpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): Bind point to which to bind the policy. Applicable only to compression, rewrite, and cache policies.
        Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_auditsyslogpolicy_binding': {}}

    if priority:
        payload['lbvserver_auditsyslogpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_auditsyslogpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_auditsyslogpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_auditsyslogpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_auditsyslogpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_auditsyslogpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_authorizationpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                              save=False):
    '''
    Add a new lbvserver_authorizationpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the label invoked.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_authorizationpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_authorizationpolicy_binding': {}}

    if priority:
        payload['lbvserver_authorizationpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_authorizationpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_authorizationpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_authorizationpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_authorizationpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_authorizationpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_cachepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      save=False):
    '''
    Add a new lbvserver_cachepolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the label invoked.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_cachepolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_cachepolicy_binding': {}}

    if priority:
        payload['lbvserver_cachepolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_cachepolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_cachepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_cachepolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_cachepolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_cachepolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_capolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                   save=False):
    '''
    Add a new lbvserver_capolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_capolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_capolicy_binding': {}}

    if priority:
        payload['lbvserver_capolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_capolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_capolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_capolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_capolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_capolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_cmppolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    save=False):
    '''
    Add a new lbvserver_cmppolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the label invoked.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_cmppolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_cmppolicy_binding': {}}

    if priority:
        payload['lbvserver_cmppolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_cmppolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_cmppolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_cmppolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_cmppolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_cmppolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_dnspolicy64_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                      save=False):
    '''
    Add a new lbvserver_dnspolicy64_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): Bind point to which to bind the policy. Applicable only to compression, rewrite, and cache policies.
        Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_dnspolicy64_binding <args>

    '''

    result = {}

    payload = {'lbvserver_dnspolicy64_binding': {}}

    if priority:
        payload['lbvserver_dnspolicy64_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_dnspolicy64_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_dnspolicy64_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_dnspolicy64_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_dnspolicy64_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_dnspolicy64_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_feopolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                    save=False):
    '''
    Add a new lbvserver_feopolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_feopolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_feopolicy_binding': {}}

    if priority:
        payload['lbvserver_feopolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_feopolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_feopolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_feopolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_feopolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_feopolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_filterpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                       save=False):
    '''
    Add a new lbvserver_filterpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): Bind point to which to bind the policy. Applicable only to compression, rewrite, and cache policies.
        Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_filterpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_filterpolicy_binding': {}}

    if priority:
        payload['lbvserver_filterpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_filterpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_filterpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_filterpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_filterpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_filterpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_pqpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                   save=False):
    '''
    Add a new lbvserver_pqpolicy_binding to the running configuration.

    priority(int): Integer specifying the policys priority. The lower the priority number, the higher the policys priority.
        Minimum value = 1 Maximum value = 2147483647

    bindpoint(str): Bind point to which to bind the policy. Applicable only to compression, rewrite, and cache policies.
        Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_pqpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_pqpolicy_binding': {}}

    if priority:
        payload['lbvserver_pqpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_pqpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_pqpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_pqpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_pqpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_pqpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_responderpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          save=False):
    '''
    Add a new lbvserver_responderpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): Bind point to which to bind the policy. Applicable only to compression, rewrite, and cache policies.
        Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the label invoked.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_responderpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_responderpolicy_binding': {}}

    if priority:
        payload['lbvserver_responderpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_responderpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_responderpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_responderpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_responderpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_responderpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_rewritepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                        save=False):
    '''
    Add a new lbvserver_rewritepolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the label invoked.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_rewritepolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_rewritepolicy_binding': {}}

    if priority:
        payload['lbvserver_rewritepolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_rewritepolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_rewritepolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_rewritepolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_rewritepolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_rewritepolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_scpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                   save=False):
    '''
    Add a new lbvserver_scpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): Bind point to which to bind the policy. Applicable only to compression, rewrite, and cache policies.
        Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_scpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_scpolicy_binding': {}}

    if priority:
        payload['lbvserver_scpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_scpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_scpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_scpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_scpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_scpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_service_binding(servicegroupname=None, name=None, save=False):
    '''
    Add a new lbvserver_service_binding to the running configuration.

    servicegroupname(str): Name of the service group. Minimum length = 1

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_service_binding <args>

    '''

    result = {}

    payload = {'lbvserver_service_binding': {}}

    if servicegroupname:
        payload['lbvserver_service_binding']['servicegroupname'] = servicegroupname

    if name:
        payload['lbvserver_service_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_service_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_servicegroup_binding(servicegroupname=None, name=None, save=False):
    '''
    Add a new lbvserver_servicegroup_binding to the running configuration.

    servicegroupname(str): The service group name bound to the selected load balancing virtual server.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_servicegroup_binding <args>

    '''

    result = {}

    payload = {'lbvserver_servicegroup_binding': {}}

    if servicegroupname:
        payload['lbvserver_servicegroup_binding']['servicegroupname'] = servicegroupname

    if name:
        payload['lbvserver_servicegroup_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_servicegroup_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_spilloverpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          save=False):
    '''
    Add a new lbvserver_spilloverpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_spilloverpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_spilloverpolicy_binding': {}}

    if priority:
        payload['lbvserver_spilloverpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_spilloverpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_spilloverpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_spilloverpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_spilloverpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_spilloverpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_tmtrafficpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          save=False):
    '''
    Add a new lbvserver_tmtrafficpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): Bind point to which to bind the policy. Applicable only to compression, rewrite, and cache policies.
        Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_tmtrafficpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_tmtrafficpolicy_binding': {}}

    if priority:
        payload['lbvserver_tmtrafficpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_tmtrafficpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_tmtrafficpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_tmtrafficpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_tmtrafficpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_tmtrafficpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_transformpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None,
                                          save=False):
    '''
    Add a new lbvserver_transformpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the label invoked.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_transformpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_transformpolicy_binding': {}}

    if priority:
        payload['lbvserver_transformpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_transformpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_transformpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_transformpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_transformpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_transformpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbvserver_videooptimizationpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None,
                                                  name=None, save=False):
    '''
    Add a new lbvserver_videooptimizationpolicy_binding to the running configuration.

    priority(int): Priority.

    bindpoint(str): The bindpoint to which the policy is bound. Possible values = REQUEST, RESPONSE

    policyname(str): Name of the policy bound to the LB vserver.

    labelname(str): Name of the label invoked.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbvserver_videooptimizationpolicy_binding <args>

    '''

    result = {}

    payload = {'lbvserver_videooptimizationpolicy_binding': {}}

    if priority:
        payload['lbvserver_videooptimizationpolicy_binding']['priority'] = priority

    if bindpoint:
        payload['lbvserver_videooptimizationpolicy_binding']['bindpoint'] = bindpoint

    if policyname:
        payload['lbvserver_videooptimizationpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['lbvserver_videooptimizationpolicy_binding']['labelname'] = labelname

    if name:
        payload['lbvserver_videooptimizationpolicy_binding']['name'] = name

    execution = __proxy__['citrixns.post']('config/lbvserver_videooptimizationpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbwlm(wlmname=None, ipaddress=None, port=None, lbuid=None, katimeout=None, save=False):
    '''
    Add a new lbwlm to the running configuration.

    wlmname(str): The name of the Work Load Manager. Minimum length = 1

    ipaddress(str): The IP address of the WLM.

    port(int): The port of the WLM. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    lbuid(str): The LBUID for the Load Balancer to communicate to the Work Load Manager.

    katimeout(int): The idle time period after which NS would probe the WLM. The value ranges from 1 to 1440 minutes. Default
        value: 2 Minimum value = 0 Maximum value = 1440

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbwlm <args>

    '''

    result = {}

    payload = {'lbwlm': {}}

    if wlmname:
        payload['lbwlm']['wlmname'] = wlmname

    if ipaddress:
        payload['lbwlm']['ipaddress'] = ipaddress

    if port:
        payload['lbwlm']['port'] = port

    if lbuid:
        payload['lbwlm']['lbuid'] = lbuid

    if katimeout:
        payload['lbwlm']['katimeout'] = katimeout

    execution = __proxy__['citrixns.post']('config/lbwlm', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_lbwlm_lbvserver_binding(wlmname=None, vservername=None, save=False):
    '''
    Add a new lbwlm_lbvserver_binding to the running configuration.

    wlmname(str): The name of the Work Load Manager. Minimum length = 1

    vservername(str): Name of the virtual server which is to be bound to the WLM.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.add_lbwlm_lbvserver_binding <args>

    '''

    result = {}

    payload = {'lbwlm_lbvserver_binding': {}}

    if wlmname:
        payload['lbwlm_lbvserver_binding']['wlmname'] = wlmname

    if vservername:
        payload['lbwlm_lbvserver_binding']['vservername'] = vservername

    execution = __proxy__['citrixns.post']('config/lbwlm_lbvserver_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_lbmonitor(monitorname=None, save=False):
    '''
    Disables a lbmonitor matching the specified filter.

    monitorname(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.disable_lbmonitor monitorname=foo

    '''

    result = {}

    payload = {'lbmonitor': {}}

    if monitorname:
        payload['lbmonitor']['monitorname'] = monitorname
    else:
        result['result'] = 'False'
        result['error'] = 'monitorname value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/lbmonitor?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def disable_lbvserver(name=None, save=False):
    '''
    Disables a lbvserver matching the specified filter.

    name(str): Matches the disable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.disable_lbvserver name=foo

    '''

    result = {}

    payload = {'lbvserver': {}}

    if name:
        payload['lbvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/lbvserver?action=disable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_lbmonitor(monitorname=None, save=False):
    '''
    Enables a lbmonitor matching the specified filter.

    monitorname(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.enable_lbmonitor monitorname=foo

    '''

    result = {}

    payload = {'lbmonitor': {}}

    if monitorname:
        payload['lbmonitor']['monitorname'] = monitorname
    else:
        result['result'] = 'False'
        result['error'] = 'monitorname value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/lbmonitor?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_lbvserver(name=None, save=False):
    '''
    Enables a lbvserver matching the specified filter.

    name(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.enable_lbvserver name=foo

    '''

    result = {}

    payload = {'lbvserver': {}}

    if name:
        payload['lbvserver']['name'] = name
    else:
        result['result'] = 'False'
        result['error'] = 'name value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/lbvserver?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_lbgroup(name=None, persistencetype=None, persistencebackup=None, backuppersistencetimeout=None, persistmask=None,
                cookiename=None, v6persistmasklen=None, cookiedomain=None, timeout=None, rule=None,
                usevserverpersistency=None, mastervserver=None, newname=None):
    '''
    Show the running configuration for the lbgroup config key.

    name(str): Filters results that only match the name field.

    persistencetype(str): Filters results that only match the persistencetype field.

    persistencebackup(str): Filters results that only match the persistencebackup field.

    backuppersistencetimeout(int): Filters results that only match the backuppersistencetimeout field.

    persistmask(str): Filters results that only match the persistmask field.

    cookiename(str): Filters results that only match the cookiename field.

    v6persistmasklen(int): Filters results that only match the v6persistmasklen field.

    cookiedomain(str): Filters results that only match the cookiedomain field.

    timeout(int): Filters results that only match the timeout field.

    rule(str): Filters results that only match the rule field.

    usevserverpersistency(str): Filters results that only match the usevserverpersistency field.

    mastervserver(str): Filters results that only match the mastervserver field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbgroup

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if persistencetype:
        search_filter.append(['persistencetype', persistencetype])

    if persistencebackup:
        search_filter.append(['persistencebackup', persistencebackup])

    if backuppersistencetimeout:
        search_filter.append(['backuppersistencetimeout', backuppersistencetimeout])

    if persistmask:
        search_filter.append(['persistmask', persistmask])

    if cookiename:
        search_filter.append(['cookiename', cookiename])

    if v6persistmasklen:
        search_filter.append(['v6persistmasklen', v6persistmasklen])

    if cookiedomain:
        search_filter.append(['cookiedomain', cookiedomain])

    if timeout:
        search_filter.append(['timeout', timeout])

    if rule:
        search_filter.append(['rule', rule])

    if usevserverpersistency:
        search_filter.append(['usevserverpersistency', usevserverpersistency])

    if mastervserver:
        search_filter.append(['mastervserver', mastervserver])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbgroup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbgroup')

    return response


def get_lbgroup_binding():
    '''
    Show the running configuration for the lbgroup_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbgroup_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbgroup_binding'), 'lbgroup_binding')

    return response


def get_lbgroup_lbvserver_binding(name=None):
    '''
    Show the running configuration for the lbgroup_lbvserver_binding config key.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbgroup_lbvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbgroup_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbgroup_lbvserver_binding')

    return response


def get_lbmetrictable(metrictable=None, metric=None, snmpoid=None):
    '''
    Show the running configuration for the lbmetrictable config key.

    metrictable(str): Filters results that only match the metrictable field.

    metric(str): Filters results that only match the metric field.

    snmpoid(str): Filters results that only match the Snmpoid field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmetrictable

    '''

    search_filter = []

    if metrictable:
        search_filter.append(['metrictable', metrictable])

    if metric:
        search_filter.append(['metric', metric])

    if snmpoid:
        search_filter.append(['Snmpoid', snmpoid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmetrictable{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbmetrictable')

    return response


def get_lbmetrictable_binding():
    '''
    Show the running configuration for the lbmetrictable_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmetrictable_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmetrictable_binding'), 'lbmetrictable_binding')

    return response


def get_lbmetrictable_metric_binding(metric=None, metrictable=None, snmpoid=None):
    '''
    Show the running configuration for the lbmetrictable_metric_binding config key.

    metric(str): Filters results that only match the metric field.

    metrictable(str): Filters results that only match the metrictable field.

    snmpoid(str): Filters results that only match the Snmpoid field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmetrictable_metric_binding

    '''

    search_filter = []

    if metric:
        search_filter.append(['metric', metric])

    if metrictable:
        search_filter.append(['metrictable', metrictable])

    if snmpoid:
        search_filter.append(['Snmpoid', snmpoid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmetrictable_metric_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbmetrictable_metric_binding')

    return response


def get_lbmonbindings(monitorname=None):
    '''
    Show the running configuration for the lbmonbindings config key.

    monitorname(str): Filters results that only match the monitorname field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmonbindings

    '''

    search_filter = []

    if monitorname:
        search_filter.append(['monitorname', monitorname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmonbindings{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbmonbindings')

    return response


def get_lbmonbindings_binding():
    '''
    Show the running configuration for the lbmonbindings_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmonbindings_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmonbindings_binding'), 'lbmonbindings_binding')

    return response


def get_lbmonbindings_service_binding(servicename=None, monitorname=None):
    '''
    Show the running configuration for the lbmonbindings_service_binding config key.

    servicename(str): Filters results that only match the servicename field.

    monitorname(str): Filters results that only match the monitorname field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmonbindings_service_binding

    '''

    search_filter = []

    if servicename:
        search_filter.append(['servicename', servicename])

    if monitorname:
        search_filter.append(['monitorname', monitorname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmonbindings_service_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbmonbindings_service_binding')

    return response


def get_lbmonbindings_servicegroup_binding(monitorname=None, servicegroupname=None):
    '''
    Show the running configuration for the lbmonbindings_servicegroup_binding config key.

    monitorname(str): Filters results that only match the monitorname field.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmonbindings_servicegroup_binding

    '''

    search_filter = []

    if monitorname:
        search_filter.append(['monitorname', monitorname])

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmonbindings_servicegroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbmonbindings_servicegroup_binding')

    return response


def get_lbmonitor(monitorname=None, ns_type=None, action=None, respcode=None, httprequest=None, rtsprequest=None,
                  customheaders=None, maxforwards=None, sipmethod=None, sipuri=None, sipreguri=None, send=None,
                  recv=None, query=None, querytype=None, scriptname=None, scriptargs=None, dispatcherip=None,
                  dispatcherport=None, username=None, password=None, secondarypassword=None, logonpointname=None,
                  lasversion=None, radkey=None, radnasid=None, radnasip=None, radaccounttype=None, radframedip=None,
                  radapn=None, radmsisdn=None, radaccountsession=None, lrtm=None, deviation=None, units1=None,
                  interval=None, units3=None, resptimeout=None, units4=None, resptimeoutthresh=None, retries=None,
                  failureretries=None, alertretries=None, successretries=None, downtime=None, units2=None, destip=None,
                  destport=None, state=None, reverse=None, transparent=None, iptunnel=None, tos=None, tosid=None,
                  secure=None, validatecred=None, domain=None, ipaddress=None, group=None, filename=None, basedn=None,
                  binddn=None, filter=None, attribute=None, database=None, oraclesid=None, sqlquery=None, evalrule=None,
                  mssqlprotocolversion=None, snmpoid=None, snmpcommunity=None, snmpthreshold=None, snmpversion=None,
                  metrictable=None, application=None, sitepath=None, storename=None, storefrontacctservice=None,
                  hostname=None, netprofile=None, originhost=None, originrealm=None, hostipaddress=None, vendorid=None,
                  productname=None, firmwarerevision=None, authapplicationid=None, acctapplicationid=None,
                  inbandsecurityid=None, supportedvendorids=None, vendorspecificvendorid=None,
                  vendorspecificauthapplicationids=None, vendorspecificacctapplicationids=None, kcdaccount=None,
                  storedb=None, storefrontcheckbackendservices=None, trofscode=None, trofsstring=None, sslprofile=None,
                  metric=None, metricthreshold=None, metricweight=None, servicename=None, servicegroupname=None):
    '''
    Show the running configuration for the lbmonitor config key.

    monitorname(str): Filters results that only match the monitorname field.

    ns_type(str): Filters results that only match the type field.

    action(str): Filters results that only match the action field.

    respcode(list(str)): Filters results that only match the respcode field.

    httprequest(str): Filters results that only match the httprequest field.

    rtsprequest(str): Filters results that only match the rtsprequest field.

    customheaders(str): Filters results that only match the customheaders field.

    maxforwards(int): Filters results that only match the maxforwards field.

    sipmethod(str): Filters results that only match the sipmethod field.

    sipuri(str): Filters results that only match the sipuri field.

    sipreguri(str): Filters results that only match the sipreguri field.

    send(str): Filters results that only match the send field.

    recv(str): Filters results that only match the recv field.

    query(str): Filters results that only match the query field.

    querytype(str): Filters results that only match the querytype field.

    scriptname(str): Filters results that only match the scriptname field.

    scriptargs(str): Filters results that only match the scriptargs field.

    dispatcherip(str): Filters results that only match the dispatcherip field.

    dispatcherport(int): Filters results that only match the dispatcherport field.

    username(str): Filters results that only match the username field.

    password(str): Filters results that only match the password field.

    secondarypassword(str): Filters results that only match the secondarypassword field.

    logonpointname(str): Filters results that only match the logonpointname field.

    lasversion(str): Filters results that only match the lasversion field.

    radkey(str): Filters results that only match the radkey field.

    radnasid(str): Filters results that only match the radnasid field.

    radnasip(str): Filters results that only match the radnasip field.

    radaccounttype(int): Filters results that only match the radaccounttype field.

    radframedip(str): Filters results that only match the radframedip field.

    radapn(str): Filters results that only match the radapn field.

    radmsisdn(str): Filters results that only match the radmsisdn field.

    radaccountsession(str): Filters results that only match the radaccountsession field.

    lrtm(str): Filters results that only match the lrtm field.

    deviation(int): Filters results that only match the deviation field.

    units1(str): Filters results that only match the units1 field.

    interval(int): Filters results that only match the interval field.

    units3(str): Filters results that only match the units3 field.

    resptimeout(int): Filters results that only match the resptimeout field.

    units4(str): Filters results that only match the units4 field.

    resptimeoutthresh(int): Filters results that only match the resptimeoutthresh field.

    retries(int): Filters results that only match the retries field.

    failureretries(int): Filters results that only match the failureretries field.

    alertretries(int): Filters results that only match the alertretries field.

    successretries(int): Filters results that only match the successretries field.

    downtime(int): Filters results that only match the downtime field.

    units2(str): Filters results that only match the units2 field.

    destip(str): Filters results that only match the destip field.

    destport(int): Filters results that only match the destport field.

    state(str): Filters results that only match the state field.

    reverse(str): Filters results that only match the reverse field.

    transparent(str): Filters results that only match the transparent field.

    iptunnel(str): Filters results that only match the iptunnel field.

    tos(str): Filters results that only match the tos field.

    tosid(int): Filters results that only match the tosid field.

    secure(str): Filters results that only match the secure field.

    validatecred(str): Filters results that only match the validatecred field.

    domain(str): Filters results that only match the domain field.

    ipaddress(list(str)): Filters results that only match the ipaddress field.

    group(str): Filters results that only match the group field.

    filename(str): Filters results that only match the filename field.

    basedn(str): Filters results that only match the basedn field.

    binddn(str): Filters results that only match the binddn field.

    filter(str): Filters results that only match the filter field.

    attribute(str): Filters results that only match the attribute field.

    database(str): Filters results that only match the database field.

    oraclesid(str): Filters results that only match the oraclesid field.

    sqlquery(str): Filters results that only match the sqlquery field.

    evalrule(str): Filters results that only match the evalrule field.

    mssqlprotocolversion(str): Filters results that only match the mssqlprotocolversion field.

    snmpoid(str): Filters results that only match the Snmpoid field.

    snmpcommunity(str): Filters results that only match the snmpcommunity field.

    snmpthreshold(str): Filters results that only match the snmpthreshold field.

    snmpversion(str): Filters results that only match the snmpversion field.

    metrictable(str): Filters results that only match the metrictable field.

    application(str): Filters results that only match the application field.

    sitepath(str): Filters results that only match the sitepath field.

    storename(str): Filters results that only match the storename field.

    storefrontacctservice(str): Filters results that only match the storefrontacctservice field.

    hostname(str): Filters results that only match the hostname field.

    netprofile(str): Filters results that only match the netprofile field.

    originhost(str): Filters results that only match the originhost field.

    originrealm(str): Filters results that only match the originrealm field.

    hostipaddress(str): Filters results that only match the hostipaddress field.

    vendorid(int): Filters results that only match the vendorid field.

    productname(str): Filters results that only match the productname field.

    firmwarerevision(int): Filters results that only match the firmwarerevision field.

    authapplicationid(list(int)): Filters results that only match the authapplicationid field.

    acctapplicationid(list(int)): Filters results that only match the acctapplicationid field.

    inbandsecurityid(str): Filters results that only match the inbandsecurityid field.

    supportedvendorids(list(int)): Filters results that only match the supportedvendorids field.

    vendorspecificvendorid(int): Filters results that only match the vendorspecificvendorid field.

    vendorspecificauthapplicationids(list(int)): Filters results that only match the vendorspecificauthapplicationids field.

    vendorspecificacctapplicationids(list(int)): Filters results that only match the vendorspecificacctapplicationids field.

    kcdaccount(str): Filters results that only match the kcdaccount field.

    storedb(str): Filters results that only match the storedb field.

    storefrontcheckbackendservices(str): Filters results that only match the storefrontcheckbackendservices field.

    trofscode(int): Filters results that only match the trofscode field.

    trofsstring(str): Filters results that only match the trofsstring field.

    sslprofile(str): Filters results that only match the sslprofile field.

    metric(str): Filters results that only match the metric field.

    metricthreshold(int): Filters results that only match the metricthreshold field.

    metricweight(int): Filters results that only match the metricweight field.

    servicename(str): Filters results that only match the servicename field.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmonitor

    '''

    search_filter = []

    if monitorname:
        search_filter.append(['monitorname', monitorname])

    if ns_type:
        search_filter.append(['type', ns_type])

    if action:
        search_filter.append(['action', action])

    if respcode:
        search_filter.append(['respcode', respcode])

    if httprequest:
        search_filter.append(['httprequest', httprequest])

    if rtsprequest:
        search_filter.append(['rtsprequest', rtsprequest])

    if customheaders:
        search_filter.append(['customheaders', customheaders])

    if maxforwards:
        search_filter.append(['maxforwards', maxforwards])

    if sipmethod:
        search_filter.append(['sipmethod', sipmethod])

    if sipuri:
        search_filter.append(['sipuri', sipuri])

    if sipreguri:
        search_filter.append(['sipreguri', sipreguri])

    if send:
        search_filter.append(['send', send])

    if recv:
        search_filter.append(['recv', recv])

    if query:
        search_filter.append(['query', query])

    if querytype:
        search_filter.append(['querytype', querytype])

    if scriptname:
        search_filter.append(['scriptname', scriptname])

    if scriptargs:
        search_filter.append(['scriptargs', scriptargs])

    if dispatcherip:
        search_filter.append(['dispatcherip', dispatcherip])

    if dispatcherport:
        search_filter.append(['dispatcherport', dispatcherport])

    if username:
        search_filter.append(['username', username])

    if password:
        search_filter.append(['password', password])

    if secondarypassword:
        search_filter.append(['secondarypassword', secondarypassword])

    if logonpointname:
        search_filter.append(['logonpointname', logonpointname])

    if lasversion:
        search_filter.append(['lasversion', lasversion])

    if radkey:
        search_filter.append(['radkey', radkey])

    if radnasid:
        search_filter.append(['radnasid', radnasid])

    if radnasip:
        search_filter.append(['radnasip', radnasip])

    if radaccounttype:
        search_filter.append(['radaccounttype', radaccounttype])

    if radframedip:
        search_filter.append(['radframedip', radframedip])

    if radapn:
        search_filter.append(['radapn', radapn])

    if radmsisdn:
        search_filter.append(['radmsisdn', radmsisdn])

    if radaccountsession:
        search_filter.append(['radaccountsession', radaccountsession])

    if lrtm:
        search_filter.append(['lrtm', lrtm])

    if deviation:
        search_filter.append(['deviation', deviation])

    if units1:
        search_filter.append(['units1', units1])

    if interval:
        search_filter.append(['interval', interval])

    if units3:
        search_filter.append(['units3', units3])

    if resptimeout:
        search_filter.append(['resptimeout', resptimeout])

    if units4:
        search_filter.append(['units4', units4])

    if resptimeoutthresh:
        search_filter.append(['resptimeoutthresh', resptimeoutthresh])

    if retries:
        search_filter.append(['retries', retries])

    if failureretries:
        search_filter.append(['failureretries', failureretries])

    if alertretries:
        search_filter.append(['alertretries', alertretries])

    if successretries:
        search_filter.append(['successretries', successretries])

    if downtime:
        search_filter.append(['downtime', downtime])

    if units2:
        search_filter.append(['units2', units2])

    if destip:
        search_filter.append(['destip', destip])

    if destport:
        search_filter.append(['destport', destport])

    if state:
        search_filter.append(['state', state])

    if reverse:
        search_filter.append(['reverse', reverse])

    if transparent:
        search_filter.append(['transparent', transparent])

    if iptunnel:
        search_filter.append(['iptunnel', iptunnel])

    if tos:
        search_filter.append(['tos', tos])

    if tosid:
        search_filter.append(['tosid', tosid])

    if secure:
        search_filter.append(['secure', secure])

    if validatecred:
        search_filter.append(['validatecred', validatecred])

    if domain:
        search_filter.append(['domain', domain])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if group:
        search_filter.append(['group', group])

    if filename:
        search_filter.append(['filename', filename])

    if basedn:
        search_filter.append(['basedn', basedn])

    if binddn:
        search_filter.append(['binddn', binddn])

    if filter:
        search_filter.append(['filter', filter])

    if attribute:
        search_filter.append(['attribute', attribute])

    if database:
        search_filter.append(['database', database])

    if oraclesid:
        search_filter.append(['oraclesid', oraclesid])

    if sqlquery:
        search_filter.append(['sqlquery', sqlquery])

    if evalrule:
        search_filter.append(['evalrule', evalrule])

    if mssqlprotocolversion:
        search_filter.append(['mssqlprotocolversion', mssqlprotocolversion])

    if snmpoid:
        search_filter.append(['Snmpoid', snmpoid])

    if snmpcommunity:
        search_filter.append(['snmpcommunity', snmpcommunity])

    if snmpthreshold:
        search_filter.append(['snmpthreshold', snmpthreshold])

    if snmpversion:
        search_filter.append(['snmpversion', snmpversion])

    if metrictable:
        search_filter.append(['metrictable', metrictable])

    if application:
        search_filter.append(['application', application])

    if sitepath:
        search_filter.append(['sitepath', sitepath])

    if storename:
        search_filter.append(['storename', storename])

    if storefrontacctservice:
        search_filter.append(['storefrontacctservice', storefrontacctservice])

    if hostname:
        search_filter.append(['hostname', hostname])

    if netprofile:
        search_filter.append(['netprofile', netprofile])

    if originhost:
        search_filter.append(['originhost', originhost])

    if originrealm:
        search_filter.append(['originrealm', originrealm])

    if hostipaddress:
        search_filter.append(['hostipaddress', hostipaddress])

    if vendorid:
        search_filter.append(['vendorid', vendorid])

    if productname:
        search_filter.append(['productname', productname])

    if firmwarerevision:
        search_filter.append(['firmwarerevision', firmwarerevision])

    if authapplicationid:
        search_filter.append(['authapplicationid', authapplicationid])

    if acctapplicationid:
        search_filter.append(['acctapplicationid', acctapplicationid])

    if inbandsecurityid:
        search_filter.append(['inbandsecurityid', inbandsecurityid])

    if supportedvendorids:
        search_filter.append(['supportedvendorids', supportedvendorids])

    if vendorspecificvendorid:
        search_filter.append(['vendorspecificvendorid', vendorspecificvendorid])

    if vendorspecificauthapplicationids:
        search_filter.append(['vendorspecificauthapplicationids', vendorspecificauthapplicationids])

    if vendorspecificacctapplicationids:
        search_filter.append(['vendorspecificacctapplicationids', vendorspecificacctapplicationids])

    if kcdaccount:
        search_filter.append(['kcdaccount', kcdaccount])

    if storedb:
        search_filter.append(['storedb', storedb])

    if storefrontcheckbackendservices:
        search_filter.append(['storefrontcheckbackendservices', storefrontcheckbackendservices])

    if trofscode:
        search_filter.append(['trofscode', trofscode])

    if trofsstring:
        search_filter.append(['trofsstring', trofsstring])

    if sslprofile:
        search_filter.append(['sslprofile', sslprofile])

    if metric:
        search_filter.append(['metric', metric])

    if metricthreshold:
        search_filter.append(['metricthreshold', metricthreshold])

    if metricweight:
        search_filter.append(['metricweight', metricweight])

    if servicename:
        search_filter.append(['servicename', servicename])

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmonitor{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbmonitor')

    return response


def get_lbmonitor_binding():
    '''
    Show the running configuration for the lbmonitor_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmonitor_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmonitor_binding'), 'lbmonitor_binding')

    return response


def get_lbmonitor_metric_binding(metric=None, metricthreshold=None, metricweight=None, monitorname=None):
    '''
    Show the running configuration for the lbmonitor_metric_binding config key.

    metric(str): Filters results that only match the metric field.

    metricthreshold(int): Filters results that only match the metricthreshold field.

    metricweight(int): Filters results that only match the metricweight field.

    monitorname(str): Filters results that only match the monitorname field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmonitor_metric_binding

    '''

    search_filter = []

    if metric:
        search_filter.append(['metric', metric])

    if metricthreshold:
        search_filter.append(['metricthreshold', metricthreshold])

    if metricweight:
        search_filter.append(['metricweight', metricweight])

    if monitorname:
        search_filter.append(['monitorname', monitorname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmonitor_metric_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbmonitor_metric_binding')

    return response


def get_lbmonitor_sslcertkey_binding(crlcheck=None, ca=None, certkeyname=None, monitorname=None, ocspcheck=None):
    '''
    Show the running configuration for the lbmonitor_sslcertkey_binding config key.

    crlcheck(str): Filters results that only match the crlcheck field.

    ca(bool): Filters results that only match the ca field.

    certkeyname(str): Filters results that only match the certkeyname field.

    monitorname(str): Filters results that only match the monitorname field.

    ocspcheck(str): Filters results that only match the ocspcheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbmonitor_sslcertkey_binding

    '''

    search_filter = []

    if crlcheck:
        search_filter.append(['crlcheck', crlcheck])

    if ca:
        search_filter.append(['ca', ca])

    if certkeyname:
        search_filter.append(['certkeyname', certkeyname])

    if monitorname:
        search_filter.append(['monitorname', monitorname])

    if ocspcheck:
        search_filter.append(['ocspcheck', ocspcheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbmonitor_sslcertkey_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbmonitor_sslcertkey_binding')

    return response


def get_lbparameter():
    '''
    Show the running configuration for the lbparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbparameter'), 'lbparameter')

    return response


def get_lbpersistentsessions(vserver=None, nodeid=None, persistenceparameter=None):
    '''
    Show the running configuration for the lbpersistentsessions config key.

    vserver(str): Filters results that only match the vserver field.

    nodeid(int): Filters results that only match the nodeid field.

    persistenceparameter(str): Filters results that only match the persistenceparameter field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbpersistentsessions

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    if persistenceparameter:
        search_filter.append(['persistenceparameter', persistenceparameter])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbpersistentsessions{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbpersistentsessions')

    return response


def get_lbprofile(lbprofilename=None, dbslb=None, processlocal=None, httponlycookieflag=None, cookiepassphrase=None,
                  usesecuredpersistencecookie=None, useencryptedpersistencecookie=None):
    '''
    Show the running configuration for the lbprofile config key.

    lbprofilename(str): Filters results that only match the lbprofilename field.

    dbslb(str): Filters results that only match the dbslb field.

    processlocal(str): Filters results that only match the processlocal field.

    httponlycookieflag(str): Filters results that only match the httponlycookieflag field.

    cookiepassphrase(str): Filters results that only match the cookiepassphrase field.

    usesecuredpersistencecookie(str): Filters results that only match the usesecuredpersistencecookie field.

    useencryptedpersistencecookie(str): Filters results that only match the useencryptedpersistencecookie field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbprofile

    '''

    search_filter = []

    if lbprofilename:
        search_filter.append(['lbprofilename', lbprofilename])

    if dbslb:
        search_filter.append(['dbslb', dbslb])

    if processlocal:
        search_filter.append(['processlocal', processlocal])

    if httponlycookieflag:
        search_filter.append(['httponlycookieflag', httponlycookieflag])

    if cookiepassphrase:
        search_filter.append(['cookiepassphrase', cookiepassphrase])

    if usesecuredpersistencecookie:
        search_filter.append(['usesecuredpersistencecookie', usesecuredpersistencecookie])

    if useencryptedpersistencecookie:
        search_filter.append(['useencryptedpersistencecookie', useencryptedpersistencecookie])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbprofile')

    return response


def get_lbroute(network=None, netmask=None, gatewayname=None, td=None):
    '''
    Show the running configuration for the lbroute config key.

    network(str): Filters results that only match the network field.

    netmask(str): Filters results that only match the netmask field.

    gatewayname(str): Filters results that only match the gatewayname field.

    td(int): Filters results that only match the td field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbroute

    '''

    search_filter = []

    if network:
        search_filter.append(['network', network])

    if netmask:
        search_filter.append(['netmask', netmask])

    if gatewayname:
        search_filter.append(['gatewayname', gatewayname])

    if td:
        search_filter.append(['td', td])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbroute{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbroute')

    return response


def get_lbroute6(network=None, gatewayname=None, td=None):
    '''
    Show the running configuration for the lbroute6 config key.

    network(str): Filters results that only match the network field.

    gatewayname(str): Filters results that only match the gatewayname field.

    td(int): Filters results that only match the td field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbroute6

    '''

    search_filter = []

    if network:
        search_filter.append(['network', network])

    if gatewayname:
        search_filter.append(['gatewayname', gatewayname])

    if td:
        search_filter.append(['td', td])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbroute6{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbroute6')

    return response


def get_lbsipparameters():
    '''
    Show the running configuration for the lbsipparameters config key.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbsipparameters

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbsipparameters'), 'lbsipparameters')

    return response


def get_lbvserver(name=None, servicetype=None, ipv46=None, ippattern=None, ipmask=None, port=None, range=None,
                  persistencetype=None, timeout=None, persistencebackup=None, backuppersistencetimeout=None,
                  lbmethod=None, hashlength=None, netmask=None, v6netmasklen=None, backuplbmethod=None, cookiename=None,
                  rule=None, listenpolicy=None, listenpriority=None, resrule=None, persistmask=None,
                  v6persistmasklen=None, pq=None, sc=None, rtspnat=None, m=None, tosid=None, datalength=None,
                  dataoffset=None, sessionless=None, trofspersistence=None, state=None, connfailover=None, redirurl=None,
                  cacheable=None, clttimeout=None, somethod=None, sopersistence=None, sopersistencetimeout=None,
                  healththreshold=None, sothreshold=None, sobackupaction=None, redirectportrewrite=None,
                  downstateflush=None, backupvserver=None, disableprimaryondown=None, insertvserveripport=None,
                  vipheader=None, authenticationhost=None, authentication=None, authn401=None, authnvsname=None,
                  push=None, pushvserver=None, pushlabel=None, pushmulticlients=None, tcpprofilename=None,
                  httpprofilename=None, dbprofilename=None, comment=None, l2conn=None, oracleserverversion=None,
                  mssqlserverversion=None, mysqlprotocolversion=None, mysqlserverversion=None, mysqlcharacterset=None,
                  mysqlservercapabilities=None, appflowlog=None, netprofile=None, icmpvsrresponse=None, rhistate=None,
                  newservicerequest=None, newservicerequestunit=None, newservicerequestincrementinterval=None,
                  minautoscalemembers=None, maxautoscalemembers=None, persistavpno=None, skippersistency=None, td=None,
                  authnprofile=None, macmoderetainvlan=None, dbslb=None, dns64=None, bypassaaaa=None,
                  recursionavailable=None, processlocal=None, dnsprofilename=None, lbprofilename=None,
                  redirectfromport=None, httpsredirecturl=None, retainconnectionsoncluster=None, weight=None,
                  servicename=None, redirurlflags=None, newname=None):
    '''
    Show the running configuration for the lbvserver config key.

    name(str): Filters results that only match the name field.

    servicetype(str): Filters results that only match the servicetype field.

    ipv46(str): Filters results that only match the ipv46 field.

    ippattern(str): Filters results that only match the ippattern field.

    ipmask(str): Filters results that only match the ipmask field.

    port(int): Filters results that only match the port field.

    range(int): Filters results that only match the range field.

    persistencetype(str): Filters results that only match the persistencetype field.

    timeout(int): Filters results that only match the timeout field.

    persistencebackup(str): Filters results that only match the persistencebackup field.

    backuppersistencetimeout(int): Filters results that only match the backuppersistencetimeout field.

    lbmethod(str): Filters results that only match the lbmethod field.

    hashlength(int): Filters results that only match the hashlength field.

    netmask(str): Filters results that only match the netmask field.

    v6netmasklen(int): Filters results that only match the v6netmasklen field.

    backuplbmethod(str): Filters results that only match the backuplbmethod field.

    cookiename(str): Filters results that only match the cookiename field.

    rule(str): Filters results that only match the rule field.

    listenpolicy(str): Filters results that only match the listenpolicy field.

    listenpriority(int): Filters results that only match the listenpriority field.

    resrule(str): Filters results that only match the resrule field.

    persistmask(str): Filters results that only match the persistmask field.

    v6persistmasklen(int): Filters results that only match the v6persistmasklen field.

    pq(str): Filters results that only match the pq field.

    sc(str): Filters results that only match the sc field.

    rtspnat(str): Filters results that only match the rtspnat field.

    m(str): Filters results that only match the m field.

    tosid(int): Filters results that only match the tosid field.

    datalength(int): Filters results that only match the datalength field.

    dataoffset(int): Filters results that only match the dataoffset field.

    sessionless(str): Filters results that only match the sessionless field.

    trofspersistence(str): Filters results that only match the trofspersistence field.

    state(str): Filters results that only match the state field.

    connfailover(str): Filters results that only match the connfailover field.

    redirurl(str): Filters results that only match the redirurl field.

    cacheable(str): Filters results that only match the cacheable field.

    clttimeout(int): Filters results that only match the clttimeout field.

    somethod(str): Filters results that only match the somethod field.

    sopersistence(str): Filters results that only match the sopersistence field.

    sopersistencetimeout(int): Filters results that only match the sopersistencetimeout field.

    healththreshold(int): Filters results that only match the healththreshold field.

    sothreshold(int): Filters results that only match the sothreshold field.

    sobackupaction(str): Filters results that only match the sobackupaction field.

    redirectportrewrite(str): Filters results that only match the redirectportrewrite field.

    downstateflush(str): Filters results that only match the downstateflush field.

    backupvserver(str): Filters results that only match the backupvserver field.

    disableprimaryondown(str): Filters results that only match the disableprimaryondown field.

    insertvserveripport(str): Filters results that only match the insertvserveripport field.

    vipheader(str): Filters results that only match the vipheader field.

    authenticationhost(str): Filters results that only match the authenticationhost field.

    authentication(str): Filters results that only match the authentication field.

    authn401(str): Filters results that only match the authn401 field.

    authnvsname(str): Filters results that only match the authnvsname field.

    push(str): Filters results that only match the push field.

    pushvserver(str): Filters results that only match the pushvserver field.

    pushlabel(str): Filters results that only match the pushlabel field.

    pushmulticlients(str): Filters results that only match the pushmulticlients field.

    tcpprofilename(str): Filters results that only match the tcpprofilename field.

    httpprofilename(str): Filters results that only match the httpprofilename field.

    dbprofilename(str): Filters results that only match the dbprofilename field.

    comment(str): Filters results that only match the comment field.

    l2conn(str): Filters results that only match the l2conn field.

    oracleserverversion(str): Filters results that only match the oracleserverversion field.

    mssqlserverversion(str): Filters results that only match the mssqlserverversion field.

    mysqlprotocolversion(int): Filters results that only match the mysqlprotocolversion field.

    mysqlserverversion(str): Filters results that only match the mysqlserverversion field.

    mysqlcharacterset(int): Filters results that only match the mysqlcharacterset field.

    mysqlservercapabilities(int): Filters results that only match the mysqlservercapabilities field.

    appflowlog(str): Filters results that only match the appflowlog field.

    netprofile(str): Filters results that only match the netprofile field.

    icmpvsrresponse(str): Filters results that only match the icmpvsrresponse field.

    rhistate(str): Filters results that only match the rhistate field.

    newservicerequest(int): Filters results that only match the newservicerequest field.

    newservicerequestunit(str): Filters results that only match the newservicerequestunit field.

    newservicerequestincrementinterval(int): Filters results that only match the newservicerequestincrementinterval field.

    minautoscalemembers(int): Filters results that only match the minautoscalemembers field.

    maxautoscalemembers(int): Filters results that only match the maxautoscalemembers field.

    persistavpno(list(int)): Filters results that only match the persistavpno field.

    skippersistency(str): Filters results that only match the skippersistency field.

    td(int): Filters results that only match the td field.

    authnprofile(str): Filters results that only match the authnprofile field.

    macmoderetainvlan(str): Filters results that only match the macmoderetainvlan field.

    dbslb(str): Filters results that only match the dbslb field.

    dns64(str): Filters results that only match the dns64 field.

    bypassaaaa(str): Filters results that only match the bypassaaaa field.

    recursionavailable(str): Filters results that only match the recursionavailable field.

    processlocal(str): Filters results that only match the processlocal field.

    dnsprofilename(str): Filters results that only match the dnsprofilename field.

    lbprofilename(str): Filters results that only match the lbprofilename field.

    redirectfromport(int): Filters results that only match the redirectfromport field.

    httpsredirecturl(str): Filters results that only match the httpsredirecturl field.

    retainconnectionsoncluster(str): Filters results that only match the retainconnectionsoncluster field.

    weight(int): Filters results that only match the weight field.

    servicename(str): Filters results that only match the servicename field.

    redirurlflags(bool): Filters results that only match the redirurlflags field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if servicetype:
        search_filter.append(['servicetype', servicetype])

    if ipv46:
        search_filter.append(['ipv46', ipv46])

    if ippattern:
        search_filter.append(['ippattern', ippattern])

    if ipmask:
        search_filter.append(['ipmask', ipmask])

    if port:
        search_filter.append(['port', port])

    if range:
        search_filter.append(['range', range])

    if persistencetype:
        search_filter.append(['persistencetype', persistencetype])

    if timeout:
        search_filter.append(['timeout', timeout])

    if persistencebackup:
        search_filter.append(['persistencebackup', persistencebackup])

    if backuppersistencetimeout:
        search_filter.append(['backuppersistencetimeout', backuppersistencetimeout])

    if lbmethod:
        search_filter.append(['lbmethod', lbmethod])

    if hashlength:
        search_filter.append(['hashlength', hashlength])

    if netmask:
        search_filter.append(['netmask', netmask])

    if v6netmasklen:
        search_filter.append(['v6netmasklen', v6netmasklen])

    if backuplbmethod:
        search_filter.append(['backuplbmethod', backuplbmethod])

    if cookiename:
        search_filter.append(['cookiename', cookiename])

    if rule:
        search_filter.append(['rule', rule])

    if listenpolicy:
        search_filter.append(['listenpolicy', listenpolicy])

    if listenpriority:
        search_filter.append(['listenpriority', listenpriority])

    if resrule:
        search_filter.append(['resrule', resrule])

    if persistmask:
        search_filter.append(['persistmask', persistmask])

    if v6persistmasklen:
        search_filter.append(['v6persistmasklen', v6persistmasklen])

    if pq:
        search_filter.append(['pq', pq])

    if sc:
        search_filter.append(['sc', sc])

    if rtspnat:
        search_filter.append(['rtspnat', rtspnat])

    if m:
        search_filter.append(['m', m])

    if tosid:
        search_filter.append(['tosid', tosid])

    if datalength:
        search_filter.append(['datalength', datalength])

    if dataoffset:
        search_filter.append(['dataoffset', dataoffset])

    if sessionless:
        search_filter.append(['sessionless', sessionless])

    if trofspersistence:
        search_filter.append(['trofspersistence', trofspersistence])

    if state:
        search_filter.append(['state', state])

    if connfailover:
        search_filter.append(['connfailover', connfailover])

    if redirurl:
        search_filter.append(['redirurl', redirurl])

    if cacheable:
        search_filter.append(['cacheable', cacheable])

    if clttimeout:
        search_filter.append(['clttimeout', clttimeout])

    if somethod:
        search_filter.append(['somethod', somethod])

    if sopersistence:
        search_filter.append(['sopersistence', sopersistence])

    if sopersistencetimeout:
        search_filter.append(['sopersistencetimeout', sopersistencetimeout])

    if healththreshold:
        search_filter.append(['healththreshold', healththreshold])

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

    if authenticationhost:
        search_filter.append(['authenticationhost', authenticationhost])

    if authentication:
        search_filter.append(['authentication', authentication])

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

    if comment:
        search_filter.append(['comment', comment])

    if l2conn:
        search_filter.append(['l2conn', l2conn])

    if oracleserverversion:
        search_filter.append(['oracleserverversion', oracleserverversion])

    if mssqlserverversion:
        search_filter.append(['mssqlserverversion', mssqlserverversion])

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

    if newservicerequest:
        search_filter.append(['newservicerequest', newservicerequest])

    if newservicerequestunit:
        search_filter.append(['newservicerequestunit', newservicerequestunit])

    if newservicerequestincrementinterval:
        search_filter.append(['newservicerequestincrementinterval', newservicerequestincrementinterval])

    if minautoscalemembers:
        search_filter.append(['minautoscalemembers', minautoscalemembers])

    if maxautoscalemembers:
        search_filter.append(['maxautoscalemembers', maxautoscalemembers])

    if persistavpno:
        search_filter.append(['persistavpno', persistavpno])

    if skippersistency:
        search_filter.append(['skippersistency', skippersistency])

    if td:
        search_filter.append(['td', td])

    if authnprofile:
        search_filter.append(['authnprofile', authnprofile])

    if macmoderetainvlan:
        search_filter.append(['macmoderetainvlan', macmoderetainvlan])

    if dbslb:
        search_filter.append(['dbslb', dbslb])

    if dns64:
        search_filter.append(['dns64', dns64])

    if bypassaaaa:
        search_filter.append(['bypassaaaa', bypassaaaa])

    if recursionavailable:
        search_filter.append(['recursionavailable', recursionavailable])

    if processlocal:
        search_filter.append(['processlocal', processlocal])

    if dnsprofilename:
        search_filter.append(['dnsprofilename', dnsprofilename])

    if lbprofilename:
        search_filter.append(['lbprofilename', lbprofilename])

    if redirectfromport:
        search_filter.append(['redirectfromport', redirectfromport])

    if httpsredirecturl:
        search_filter.append(['httpsredirecturl', httpsredirecturl])

    if retainconnectionsoncluster:
        search_filter.append(['retainconnectionsoncluster', retainconnectionsoncluster])

    if weight:
        search_filter.append(['weight', weight])

    if servicename:
        search_filter.append(['servicename', servicename])

    if redirurlflags:
        search_filter.append(['redirurlflags', redirurlflags])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver')

    return response


def get_lbvserver_appflowpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_appflowpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_appflowpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_appflowpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_appflowpolicy_binding')

    return response


def get_lbvserver_appfwpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_appfwpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_appfwpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_appfwpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_appfwpolicy_binding')

    return response


def get_lbvserver_appqoepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_appqoepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_appqoepolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_appqoepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_appqoepolicy_binding')

    return response


def get_lbvserver_auditnslogpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_auditnslogpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_auditnslogpolicy_binding')

    return response


def get_lbvserver_auditsyslogpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_auditsyslogpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_auditsyslogpolicy_binding')

    return response


def get_lbvserver_authorizationpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None,
                                              name=None):
    '''
    Show the running configuration for the lbvserver_authorizationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_authorizationpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_authorizationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_authorizationpolicy_binding')

    return response


def get_lbvserver_binding():
    '''
    Show the running configuration for the lbvserver_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_binding'), 'lbvserver_binding')

    return response


def get_lbvserver_cachepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_cachepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_cachepolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_cachepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_cachepolicy_binding')

    return response


def get_lbvserver_capolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_capolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_capolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_capolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_capolicy_binding')

    return response


def get_lbvserver_cmppolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_cmppolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_cmppolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_cmppolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_cmppolicy_binding')

    return response


def get_lbvserver_csvserver_binding(priority=None, policyname=None, name=None):
    '''
    Show the running configuration for the lbvserver_csvserver_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_csvserver_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_csvserver_binding')

    return response


def get_lbvserver_dnspolicy64_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_dnspolicy64_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_dnspolicy64_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_dnspolicy64_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_dnspolicy64_binding')

    return response


def get_lbvserver_dospolicy_binding(priority=None, policyname=None, name=None):
    '''
    Show the running configuration for the lbvserver_dospolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_dospolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_dospolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_dospolicy_binding')

    return response


def get_lbvserver_feopolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_feopolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_feopolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_feopolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_feopolicy_binding')

    return response


def get_lbvserver_filterpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_filterpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_filterpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_filterpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_filterpolicy_binding')

    return response


def get_lbvserver_pqpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_pqpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_pqpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_pqpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_pqpolicy_binding')

    return response


def get_lbvserver_responderpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_responderpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_responderpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_responderpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_responderpolicy_binding')

    return response


def get_lbvserver_rewritepolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_rewritepolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_rewritepolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_rewritepolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_rewritepolicy_binding')

    return response


def get_lbvserver_scpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_scpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_scpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_scpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_scpolicy_binding')

    return response


def get_lbvserver_service_binding(servicegroupname=None, name=None):
    '''
    Show the running configuration for the lbvserver_service_binding config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_service_binding

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_service_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_service_binding')

    return response


def get_lbvserver_servicegroup_binding(servicegroupname=None, name=None):
    '''
    Show the running configuration for the lbvserver_servicegroup_binding config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_servicegroup_binding

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_servicegroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_servicegroup_binding')

    return response


def get_lbvserver_servicegroupmember_binding(servicegroupname=None, name=None):
    '''
    Show the running configuration for the lbvserver_servicegroupmember_binding config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_servicegroupmember_binding

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_servicegroupmember_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_servicegroupmember_binding')

    return response


def get_lbvserver_spilloverpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_spilloverpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_spilloverpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_spilloverpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_spilloverpolicy_binding')

    return response


def get_lbvserver_tmtrafficpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_tmtrafficpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_tmtrafficpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_tmtrafficpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_tmtrafficpolicy_binding')

    return response


def get_lbvserver_transformpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None, name=None):
    '''
    Show the running configuration for the lbvserver_transformpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_transformpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_transformpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_transformpolicy_binding')

    return response


def get_lbvserver_videooptimizationpolicy_binding(priority=None, bindpoint=None, policyname=None, labelname=None,
                                                  name=None):
    '''
    Show the running configuration for the lbvserver_videooptimizationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    bindpoint(str): Filters results that only match the bindpoint field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbvserver_videooptimizationpolicy_binding

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

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbvserver_videooptimizationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbvserver_videooptimizationpolicy_binding')

    return response


def get_lbwlm(wlmname=None, ipaddress=None, port=None, lbuid=None, katimeout=None):
    '''
    Show the running configuration for the lbwlm config key.

    wlmname(str): Filters results that only match the wlmname field.

    ipaddress(str): Filters results that only match the ipaddress field.

    port(int): Filters results that only match the port field.

    lbuid(str): Filters results that only match the lbuid field.

    katimeout(int): Filters results that only match the katimeout field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbwlm

    '''

    search_filter = []

    if wlmname:
        search_filter.append(['wlmname', wlmname])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if port:
        search_filter.append(['port', port])

    if lbuid:
        search_filter.append(['lbuid', lbuid])

    if katimeout:
        search_filter.append(['katimeout', katimeout])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbwlm{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbwlm')

    return response


def get_lbwlm_binding():
    '''
    Show the running configuration for the lbwlm_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbwlm_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbwlm_binding'), 'lbwlm_binding')

    return response


def get_lbwlm_lbvserver_binding(wlmname=None, vservername=None):
    '''
    Show the running configuration for the lbwlm_lbvserver_binding config key.

    wlmname(str): Filters results that only match the wlmname field.

    vservername(str): Filters results that only match the vservername field.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.get_lbwlm_lbvserver_binding

    '''

    search_filter = []

    if wlmname:
        search_filter.append(['wlmname', wlmname])

    if vservername:
        search_filter.append(['vservername', vservername])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lbwlm_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lbwlm_lbvserver_binding')

    return response


def unset_lbgroup(name=None, persistencetype=None, persistencebackup=None, backuppersistencetimeout=None,
                  persistmask=None, cookiename=None, v6persistmasklen=None, cookiedomain=None, timeout=None, rule=None,
                  usevserverpersistency=None, mastervserver=None, newname=None, save=False):
    '''
    Unsets values from the lbgroup configuration key.

    name(bool): Unsets the name value.

    persistencetype(bool): Unsets the persistencetype value.

    persistencebackup(bool): Unsets the persistencebackup value.

    backuppersistencetimeout(bool): Unsets the backuppersistencetimeout value.

    persistmask(bool): Unsets the persistmask value.

    cookiename(bool): Unsets the cookiename value.

    v6persistmasklen(bool): Unsets the v6persistmasklen value.

    cookiedomain(bool): Unsets the cookiedomain value.

    timeout(bool): Unsets the timeout value.

    rule(bool): Unsets the rule value.

    usevserverpersistency(bool): Unsets the usevserverpersistency value.

    mastervserver(bool): Unsets the mastervserver value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.unset_lbgroup <args>

    '''

    result = {}

    payload = {'lbgroup': {}}

    if name:
        payload['lbgroup']['name'] = True

    if persistencetype:
        payload['lbgroup']['persistencetype'] = True

    if persistencebackup:
        payload['lbgroup']['persistencebackup'] = True

    if backuppersistencetimeout:
        payload['lbgroup']['backuppersistencetimeout'] = True

    if persistmask:
        payload['lbgroup']['persistmask'] = True

    if cookiename:
        payload['lbgroup']['cookiename'] = True

    if v6persistmasklen:
        payload['lbgroup']['v6persistmasklen'] = True

    if cookiedomain:
        payload['lbgroup']['cookiedomain'] = True

    if timeout:
        payload['lbgroup']['timeout'] = True

    if rule:
        payload['lbgroup']['rule'] = True

    if usevserverpersistency:
        payload['lbgroup']['usevserverpersistency'] = True

    if mastervserver:
        payload['lbgroup']['mastervserver'] = True

    if newname:
        payload['lbgroup']['newname'] = True

    execution = __proxy__['citrixns.post']('config/lbgroup?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_lbmonitor(monitorname=None, ns_type=None, action=None, respcode=None, httprequest=None, rtsprequest=None,
                    customheaders=None, maxforwards=None, sipmethod=None, sipuri=None, sipreguri=None, send=None,
                    recv=None, query=None, querytype=None, scriptname=None, scriptargs=None, dispatcherip=None,
                    dispatcherport=None, username=None, password=None, secondarypassword=None, logonpointname=None,
                    lasversion=None, radkey=None, radnasid=None, radnasip=None, radaccounttype=None, radframedip=None,
                    radapn=None, radmsisdn=None, radaccountsession=None, lrtm=None, deviation=None, units1=None,
                    interval=None, units3=None, resptimeout=None, units4=None, resptimeoutthresh=None, retries=None,
                    failureretries=None, alertretries=None, successretries=None, downtime=None, units2=None, destip=None,
                    destport=None, state=None, reverse=None, transparent=None, iptunnel=None, tos=None, tosid=None,
                    secure=None, validatecred=None, domain=None, ipaddress=None, group=None, filename=None, basedn=None,
                    binddn=None, filter=None, attribute=None, database=None, oraclesid=None, sqlquery=None,
                    evalrule=None, mssqlprotocolversion=None, snmpoid=None, snmpcommunity=None, snmpthreshold=None,
                    snmpversion=None, metrictable=None, application=None, sitepath=None, storename=None,
                    storefrontacctservice=None, hostname=None, netprofile=None, originhost=None, originrealm=None,
                    hostipaddress=None, vendorid=None, productname=None, firmwarerevision=None, authapplicationid=None,
                    acctapplicationid=None, inbandsecurityid=None, supportedvendorids=None, vendorspecificvendorid=None,
                    vendorspecificauthapplicationids=None, vendorspecificacctapplicationids=None, kcdaccount=None,
                    storedb=None, storefrontcheckbackendservices=None, trofscode=None, trofsstring=None, sslprofile=None,
                    metric=None, metricthreshold=None, metricweight=None, servicename=None, servicegroupname=None,
                    save=False):
    '''
    Unsets values from the lbmonitor configuration key.

    monitorname(bool): Unsets the monitorname value.

    ns_type(bool): Unsets the ns_type value.

    action(bool): Unsets the action value.

    respcode(bool): Unsets the respcode value.

    httprequest(bool): Unsets the httprequest value.

    rtsprequest(bool): Unsets the rtsprequest value.

    customheaders(bool): Unsets the customheaders value.

    maxforwards(bool): Unsets the maxforwards value.

    sipmethod(bool): Unsets the sipmethod value.

    sipuri(bool): Unsets the sipuri value.

    sipreguri(bool): Unsets the sipreguri value.

    send(bool): Unsets the send value.

    recv(bool): Unsets the recv value.

    query(bool): Unsets the query value.

    querytype(bool): Unsets the querytype value.

    scriptname(bool): Unsets the scriptname value.

    scriptargs(bool): Unsets the scriptargs value.

    dispatcherip(bool): Unsets the dispatcherip value.

    dispatcherport(bool): Unsets the dispatcherport value.

    username(bool): Unsets the username value.

    password(bool): Unsets the password value.

    secondarypassword(bool): Unsets the secondarypassword value.

    logonpointname(bool): Unsets the logonpointname value.

    lasversion(bool): Unsets the lasversion value.

    radkey(bool): Unsets the radkey value.

    radnasid(bool): Unsets the radnasid value.

    radnasip(bool): Unsets the radnasip value.

    radaccounttype(bool): Unsets the radaccounttype value.

    radframedip(bool): Unsets the radframedip value.

    radapn(bool): Unsets the radapn value.

    radmsisdn(bool): Unsets the radmsisdn value.

    radaccountsession(bool): Unsets the radaccountsession value.

    lrtm(bool): Unsets the lrtm value.

    deviation(bool): Unsets the deviation value.

    units1(bool): Unsets the units1 value.

    interval(bool): Unsets the interval value.

    units3(bool): Unsets the units3 value.

    resptimeout(bool): Unsets the resptimeout value.

    units4(bool): Unsets the units4 value.

    resptimeoutthresh(bool): Unsets the resptimeoutthresh value.

    retries(bool): Unsets the retries value.

    failureretries(bool): Unsets the failureretries value.

    alertretries(bool): Unsets the alertretries value.

    successretries(bool): Unsets the successretries value.

    downtime(bool): Unsets the downtime value.

    units2(bool): Unsets the units2 value.

    destip(bool): Unsets the destip value.

    destport(bool): Unsets the destport value.

    state(bool): Unsets the state value.

    reverse(bool): Unsets the reverse value.

    transparent(bool): Unsets the transparent value.

    iptunnel(bool): Unsets the iptunnel value.

    tos(bool): Unsets the tos value.

    tosid(bool): Unsets the tosid value.

    secure(bool): Unsets the secure value.

    validatecred(bool): Unsets the validatecred value.

    domain(bool): Unsets the domain value.

    ipaddress(bool): Unsets the ipaddress value.

    group(bool): Unsets the group value.

    filename(bool): Unsets the filename value.

    basedn(bool): Unsets the basedn value.

    binddn(bool): Unsets the binddn value.

    filter(bool): Unsets the filter value.

    attribute(bool): Unsets the attribute value.

    database(bool): Unsets the database value.

    oraclesid(bool): Unsets the oraclesid value.

    sqlquery(bool): Unsets the sqlquery value.

    evalrule(bool): Unsets the evalrule value.

    mssqlprotocolversion(bool): Unsets the mssqlprotocolversion value.

    snmpoid(bool): Unsets the snmpoid value.

    snmpcommunity(bool): Unsets the snmpcommunity value.

    snmpthreshold(bool): Unsets the snmpthreshold value.

    snmpversion(bool): Unsets the snmpversion value.

    metrictable(bool): Unsets the metrictable value.

    application(bool): Unsets the application value.

    sitepath(bool): Unsets the sitepath value.

    storename(bool): Unsets the storename value.

    storefrontacctservice(bool): Unsets the storefrontacctservice value.

    hostname(bool): Unsets the hostname value.

    netprofile(bool): Unsets the netprofile value.

    originhost(bool): Unsets the originhost value.

    originrealm(bool): Unsets the originrealm value.

    hostipaddress(bool): Unsets the hostipaddress value.

    vendorid(bool): Unsets the vendorid value.

    productname(bool): Unsets the productname value.

    firmwarerevision(bool): Unsets the firmwarerevision value.

    authapplicationid(bool): Unsets the authapplicationid value.

    acctapplicationid(bool): Unsets the acctapplicationid value.

    inbandsecurityid(bool): Unsets the inbandsecurityid value.

    supportedvendorids(bool): Unsets the supportedvendorids value.

    vendorspecificvendorid(bool): Unsets the vendorspecificvendorid value.

    vendorspecificauthapplicationids(bool): Unsets the vendorspecificauthapplicationids value.

    vendorspecificacctapplicationids(bool): Unsets the vendorspecificacctapplicationids value.

    kcdaccount(bool): Unsets the kcdaccount value.

    storedb(bool): Unsets the storedb value.

    storefrontcheckbackendservices(bool): Unsets the storefrontcheckbackendservices value.

    trofscode(bool): Unsets the trofscode value.

    trofsstring(bool): Unsets the trofsstring value.

    sslprofile(bool): Unsets the sslprofile value.

    metric(bool): Unsets the metric value.

    metricthreshold(bool): Unsets the metricthreshold value.

    metricweight(bool): Unsets the metricweight value.

    servicename(bool): Unsets the servicename value.

    servicegroupname(bool): Unsets the servicegroupname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.unset_lbmonitor <args>

    '''

    result = {}

    payload = {'lbmonitor': {}}

    if monitorname:
        payload['lbmonitor']['monitorname'] = True

    if ns_type:
        payload['lbmonitor']['type'] = True

    if action:
        payload['lbmonitor']['action'] = True

    if respcode:
        payload['lbmonitor']['respcode'] = True

    if httprequest:
        payload['lbmonitor']['httprequest'] = True

    if rtsprequest:
        payload['lbmonitor']['rtsprequest'] = True

    if customheaders:
        payload['lbmonitor']['customheaders'] = True

    if maxforwards:
        payload['lbmonitor']['maxforwards'] = True

    if sipmethod:
        payload['lbmonitor']['sipmethod'] = True

    if sipuri:
        payload['lbmonitor']['sipuri'] = True

    if sipreguri:
        payload['lbmonitor']['sipreguri'] = True

    if send:
        payload['lbmonitor']['send'] = True

    if recv:
        payload['lbmonitor']['recv'] = True

    if query:
        payload['lbmonitor']['query'] = True

    if querytype:
        payload['lbmonitor']['querytype'] = True

    if scriptname:
        payload['lbmonitor']['scriptname'] = True

    if scriptargs:
        payload['lbmonitor']['scriptargs'] = True

    if dispatcherip:
        payload['lbmonitor']['dispatcherip'] = True

    if dispatcherport:
        payload['lbmonitor']['dispatcherport'] = True

    if username:
        payload['lbmonitor']['username'] = True

    if password:
        payload['lbmonitor']['password'] = True

    if secondarypassword:
        payload['lbmonitor']['secondarypassword'] = True

    if logonpointname:
        payload['lbmonitor']['logonpointname'] = True

    if lasversion:
        payload['lbmonitor']['lasversion'] = True

    if radkey:
        payload['lbmonitor']['radkey'] = True

    if radnasid:
        payload['lbmonitor']['radnasid'] = True

    if radnasip:
        payload['lbmonitor']['radnasip'] = True

    if radaccounttype:
        payload['lbmonitor']['radaccounttype'] = True

    if radframedip:
        payload['lbmonitor']['radframedip'] = True

    if radapn:
        payload['lbmonitor']['radapn'] = True

    if radmsisdn:
        payload['lbmonitor']['radmsisdn'] = True

    if radaccountsession:
        payload['lbmonitor']['radaccountsession'] = True

    if lrtm:
        payload['lbmonitor']['lrtm'] = True

    if deviation:
        payload['lbmonitor']['deviation'] = True

    if units1:
        payload['lbmonitor']['units1'] = True

    if interval:
        payload['lbmonitor']['interval'] = True

    if units3:
        payload['lbmonitor']['units3'] = True

    if resptimeout:
        payload['lbmonitor']['resptimeout'] = True

    if units4:
        payload['lbmonitor']['units4'] = True

    if resptimeoutthresh:
        payload['lbmonitor']['resptimeoutthresh'] = True

    if retries:
        payload['lbmonitor']['retries'] = True

    if failureretries:
        payload['lbmonitor']['failureretries'] = True

    if alertretries:
        payload['lbmonitor']['alertretries'] = True

    if successretries:
        payload['lbmonitor']['successretries'] = True

    if downtime:
        payload['lbmonitor']['downtime'] = True

    if units2:
        payload['lbmonitor']['units2'] = True

    if destip:
        payload['lbmonitor']['destip'] = True

    if destport:
        payload['lbmonitor']['destport'] = True

    if state:
        payload['lbmonitor']['state'] = True

    if reverse:
        payload['lbmonitor']['reverse'] = True

    if transparent:
        payload['lbmonitor']['transparent'] = True

    if iptunnel:
        payload['lbmonitor']['iptunnel'] = True

    if tos:
        payload['lbmonitor']['tos'] = True

    if tosid:
        payload['lbmonitor']['tosid'] = True

    if secure:
        payload['lbmonitor']['secure'] = True

    if validatecred:
        payload['lbmonitor']['validatecred'] = True

    if domain:
        payload['lbmonitor']['domain'] = True

    if ipaddress:
        payload['lbmonitor']['ipaddress'] = True

    if group:
        payload['lbmonitor']['group'] = True

    if filename:
        payload['lbmonitor']['filename'] = True

    if basedn:
        payload['lbmonitor']['basedn'] = True

    if binddn:
        payload['lbmonitor']['binddn'] = True

    if filter:
        payload['lbmonitor']['filter'] = True

    if attribute:
        payload['lbmonitor']['attribute'] = True

    if database:
        payload['lbmonitor']['database'] = True

    if oraclesid:
        payload['lbmonitor']['oraclesid'] = True

    if sqlquery:
        payload['lbmonitor']['sqlquery'] = True

    if evalrule:
        payload['lbmonitor']['evalrule'] = True

    if mssqlprotocolversion:
        payload['lbmonitor']['mssqlprotocolversion'] = True

    if snmpoid:
        payload['lbmonitor']['Snmpoid'] = True

    if snmpcommunity:
        payload['lbmonitor']['snmpcommunity'] = True

    if snmpthreshold:
        payload['lbmonitor']['snmpthreshold'] = True

    if snmpversion:
        payload['lbmonitor']['snmpversion'] = True

    if metrictable:
        payload['lbmonitor']['metrictable'] = True

    if application:
        payload['lbmonitor']['application'] = True

    if sitepath:
        payload['lbmonitor']['sitepath'] = True

    if storename:
        payload['lbmonitor']['storename'] = True

    if storefrontacctservice:
        payload['lbmonitor']['storefrontacctservice'] = True

    if hostname:
        payload['lbmonitor']['hostname'] = True

    if netprofile:
        payload['lbmonitor']['netprofile'] = True

    if originhost:
        payload['lbmonitor']['originhost'] = True

    if originrealm:
        payload['lbmonitor']['originrealm'] = True

    if hostipaddress:
        payload['lbmonitor']['hostipaddress'] = True

    if vendorid:
        payload['lbmonitor']['vendorid'] = True

    if productname:
        payload['lbmonitor']['productname'] = True

    if firmwarerevision:
        payload['lbmonitor']['firmwarerevision'] = True

    if authapplicationid:
        payload['lbmonitor']['authapplicationid'] = True

    if acctapplicationid:
        payload['lbmonitor']['acctapplicationid'] = True

    if inbandsecurityid:
        payload['lbmonitor']['inbandsecurityid'] = True

    if supportedvendorids:
        payload['lbmonitor']['supportedvendorids'] = True

    if vendorspecificvendorid:
        payload['lbmonitor']['vendorspecificvendorid'] = True

    if vendorspecificauthapplicationids:
        payload['lbmonitor']['vendorspecificauthapplicationids'] = True

    if vendorspecificacctapplicationids:
        payload['lbmonitor']['vendorspecificacctapplicationids'] = True

    if kcdaccount:
        payload['lbmonitor']['kcdaccount'] = True

    if storedb:
        payload['lbmonitor']['storedb'] = True

    if storefrontcheckbackendservices:
        payload['lbmonitor']['storefrontcheckbackendservices'] = True

    if trofscode:
        payload['lbmonitor']['trofscode'] = True

    if trofsstring:
        payload['lbmonitor']['trofsstring'] = True

    if sslprofile:
        payload['lbmonitor']['sslprofile'] = True

    if metric:
        payload['lbmonitor']['metric'] = True

    if metricthreshold:
        payload['lbmonitor']['metricthreshold'] = True

    if metricweight:
        payload['lbmonitor']['metricweight'] = True

    if servicename:
        payload['lbmonitor']['servicename'] = True

    if servicegroupname:
        payload['lbmonitor']['servicegroupname'] = True

    execution = __proxy__['citrixns.post']('config/lbmonitor?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_lbparameter(httponlycookieflag=None, usesecuredpersistencecookie=None, useencryptedpersistencecookie=None,
                      cookiepassphrase=None, consolidatedlconn=None, useportforhashlb=None, preferdirectroute=None,
                      startuprrfactor=None, monitorskipmaxclient=None, monitorconnectionclose=None,
                      vserverspecificmac=None, allowboundsvcremoval=None, retainservicestate=None, save=False):
    '''
    Unsets values from the lbparameter configuration key.

    httponlycookieflag(bool): Unsets the httponlycookieflag value.

    usesecuredpersistencecookie(bool): Unsets the usesecuredpersistencecookie value.

    useencryptedpersistencecookie(bool): Unsets the useencryptedpersistencecookie value.

    cookiepassphrase(bool): Unsets the cookiepassphrase value.

    consolidatedlconn(bool): Unsets the consolidatedlconn value.

    useportforhashlb(bool): Unsets the useportforhashlb value.

    preferdirectroute(bool): Unsets the preferdirectroute value.

    startuprrfactor(bool): Unsets the startuprrfactor value.

    monitorskipmaxclient(bool): Unsets the monitorskipmaxclient value.

    monitorconnectionclose(bool): Unsets the monitorconnectionclose value.

    vserverspecificmac(bool): Unsets the vserverspecificmac value.

    allowboundsvcremoval(bool): Unsets the allowboundsvcremoval value.

    retainservicestate(bool): Unsets the retainservicestate value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.unset_lbparameter <args>

    '''

    result = {}

    payload = {'lbparameter': {}}

    if httponlycookieflag:
        payload['lbparameter']['httponlycookieflag'] = True

    if usesecuredpersistencecookie:
        payload['lbparameter']['usesecuredpersistencecookie'] = True

    if useencryptedpersistencecookie:
        payload['lbparameter']['useencryptedpersistencecookie'] = True

    if cookiepassphrase:
        payload['lbparameter']['cookiepassphrase'] = True

    if consolidatedlconn:
        payload['lbparameter']['consolidatedlconn'] = True

    if useportforhashlb:
        payload['lbparameter']['useportforhashlb'] = True

    if preferdirectroute:
        payload['lbparameter']['preferdirectroute'] = True

    if startuprrfactor:
        payload['lbparameter']['startuprrfactor'] = True

    if monitorskipmaxclient:
        payload['lbparameter']['monitorskipmaxclient'] = True

    if monitorconnectionclose:
        payload['lbparameter']['monitorconnectionclose'] = True

    if vserverspecificmac:
        payload['lbparameter']['vserverspecificmac'] = True

    if allowboundsvcremoval:
        payload['lbparameter']['allowboundsvcremoval'] = True

    if retainservicestate:
        payload['lbparameter']['retainservicestate'] = True

    execution = __proxy__['citrixns.post']('config/lbparameter?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_lbprofile(lbprofilename=None, dbslb=None, processlocal=None, httponlycookieflag=None, cookiepassphrase=None,
                    usesecuredpersistencecookie=None, useencryptedpersistencecookie=None, save=False):
    '''
    Unsets values from the lbprofile configuration key.

    lbprofilename(bool): Unsets the lbprofilename value.

    dbslb(bool): Unsets the dbslb value.

    processlocal(bool): Unsets the processlocal value.

    httponlycookieflag(bool): Unsets the httponlycookieflag value.

    cookiepassphrase(bool): Unsets the cookiepassphrase value.

    usesecuredpersistencecookie(bool): Unsets the usesecuredpersistencecookie value.

    useencryptedpersistencecookie(bool): Unsets the useencryptedpersistencecookie value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.unset_lbprofile <args>

    '''

    result = {}

    payload = {'lbprofile': {}}

    if lbprofilename:
        payload['lbprofile']['lbprofilename'] = True

    if dbslb:
        payload['lbprofile']['dbslb'] = True

    if processlocal:
        payload['lbprofile']['processlocal'] = True

    if httponlycookieflag:
        payload['lbprofile']['httponlycookieflag'] = True

    if cookiepassphrase:
        payload['lbprofile']['cookiepassphrase'] = True

    if usesecuredpersistencecookie:
        payload['lbprofile']['usesecuredpersistencecookie'] = True

    if useencryptedpersistencecookie:
        payload['lbprofile']['useencryptedpersistencecookie'] = True

    execution = __proxy__['citrixns.post']('config/lbprofile?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_lbsipparameters(rnatsrcport=None, rnatdstport=None, retrydur=None, addrportvip=None, sip503ratethreshold=None,
                          rnatsecuresrcport=None, rnatsecuredstport=None, save=False):
    '''
    Unsets values from the lbsipparameters configuration key.

    rnatsrcport(bool): Unsets the rnatsrcport value.

    rnatdstport(bool): Unsets the rnatdstport value.

    retrydur(bool): Unsets the retrydur value.

    addrportvip(bool): Unsets the addrportvip value.

    sip503ratethreshold(bool): Unsets the sip503ratethreshold value.

    rnatsecuresrcport(bool): Unsets the rnatsecuresrcport value.

    rnatsecuredstport(bool): Unsets the rnatsecuredstport value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.unset_lbsipparameters <args>

    '''

    result = {}

    payload = {'lbsipparameters': {}}

    if rnatsrcport:
        payload['lbsipparameters']['rnatsrcport'] = True

    if rnatdstport:
        payload['lbsipparameters']['rnatdstport'] = True

    if retrydur:
        payload['lbsipparameters']['retrydur'] = True

    if addrportvip:
        payload['lbsipparameters']['addrportvip'] = True

    if sip503ratethreshold:
        payload['lbsipparameters']['sip503ratethreshold'] = True

    if rnatsecuresrcport:
        payload['lbsipparameters']['rnatsecuresrcport'] = True

    if rnatsecuredstport:
        payload['lbsipparameters']['rnatsecuredstport'] = True

    execution = __proxy__['citrixns.post']('config/lbsipparameters?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_lbvserver(name=None, servicetype=None, ipv46=None, ippattern=None, ipmask=None, port=None, range=None,
                    persistencetype=None, timeout=None, persistencebackup=None, backuppersistencetimeout=None,
                    lbmethod=None, hashlength=None, netmask=None, v6netmasklen=None, backuplbmethod=None,
                    cookiename=None, rule=None, listenpolicy=None, listenpriority=None, resrule=None, persistmask=None,
                    v6persistmasklen=None, pq=None, sc=None, rtspnat=None, m=None, tosid=None, datalength=None,
                    dataoffset=None, sessionless=None, trofspersistence=None, state=None, connfailover=None,
                    redirurl=None, cacheable=None, clttimeout=None, somethod=None, sopersistence=None,
                    sopersistencetimeout=None, healththreshold=None, sothreshold=None, sobackupaction=None,
                    redirectportrewrite=None, downstateflush=None, backupvserver=None, disableprimaryondown=None,
                    insertvserveripport=None, vipheader=None, authenticationhost=None, authentication=None,
                    authn401=None, authnvsname=None, push=None, pushvserver=None, pushlabel=None, pushmulticlients=None,
                    tcpprofilename=None, httpprofilename=None, dbprofilename=None, comment=None, l2conn=None,
                    oracleserverversion=None, mssqlserverversion=None, mysqlprotocolversion=None,
                    mysqlserverversion=None, mysqlcharacterset=None, mysqlservercapabilities=None, appflowlog=None,
                    netprofile=None, icmpvsrresponse=None, rhistate=None, newservicerequest=None,
                    newservicerequestunit=None, newservicerequestincrementinterval=None, minautoscalemembers=None,
                    maxautoscalemembers=None, persistavpno=None, skippersistency=None, td=None, authnprofile=None,
                    macmoderetainvlan=None, dbslb=None, dns64=None, bypassaaaa=None, recursionavailable=None,
                    processlocal=None, dnsprofilename=None, lbprofilename=None, redirectfromport=None,
                    httpsredirecturl=None, retainconnectionsoncluster=None, weight=None, servicename=None,
                    redirurlflags=None, newname=None, save=False):
    '''
    Unsets values from the lbvserver configuration key.

    name(bool): Unsets the name value.

    servicetype(bool): Unsets the servicetype value.

    ipv46(bool): Unsets the ipv46 value.

    ippattern(bool): Unsets the ippattern value.

    ipmask(bool): Unsets the ipmask value.

    port(bool): Unsets the port value.

    range(bool): Unsets the range value.

    persistencetype(bool): Unsets the persistencetype value.

    timeout(bool): Unsets the timeout value.

    persistencebackup(bool): Unsets the persistencebackup value.

    backuppersistencetimeout(bool): Unsets the backuppersistencetimeout value.

    lbmethod(bool): Unsets the lbmethod value.

    hashlength(bool): Unsets the hashlength value.

    netmask(bool): Unsets the netmask value.

    v6netmasklen(bool): Unsets the v6netmasklen value.

    backuplbmethod(bool): Unsets the backuplbmethod value.

    cookiename(bool): Unsets the cookiename value.

    rule(bool): Unsets the rule value.

    listenpolicy(bool): Unsets the listenpolicy value.

    listenpriority(bool): Unsets the listenpriority value.

    resrule(bool): Unsets the resrule value.

    persistmask(bool): Unsets the persistmask value.

    v6persistmasklen(bool): Unsets the v6persistmasklen value.

    pq(bool): Unsets the pq value.

    sc(bool): Unsets the sc value.

    rtspnat(bool): Unsets the rtspnat value.

    m(bool): Unsets the m value.

    tosid(bool): Unsets the tosid value.

    datalength(bool): Unsets the datalength value.

    dataoffset(bool): Unsets the dataoffset value.

    sessionless(bool): Unsets the sessionless value.

    trofspersistence(bool): Unsets the trofspersistence value.

    state(bool): Unsets the state value.

    connfailover(bool): Unsets the connfailover value.

    redirurl(bool): Unsets the redirurl value.

    cacheable(bool): Unsets the cacheable value.

    clttimeout(bool): Unsets the clttimeout value.

    somethod(bool): Unsets the somethod value.

    sopersistence(bool): Unsets the sopersistence value.

    sopersistencetimeout(bool): Unsets the sopersistencetimeout value.

    healththreshold(bool): Unsets the healththreshold value.

    sothreshold(bool): Unsets the sothreshold value.

    sobackupaction(bool): Unsets the sobackupaction value.

    redirectportrewrite(bool): Unsets the redirectportrewrite value.

    downstateflush(bool): Unsets the downstateflush value.

    backupvserver(bool): Unsets the backupvserver value.

    disableprimaryondown(bool): Unsets the disableprimaryondown value.

    insertvserveripport(bool): Unsets the insertvserveripport value.

    vipheader(bool): Unsets the vipheader value.

    authenticationhost(bool): Unsets the authenticationhost value.

    authentication(bool): Unsets the authentication value.

    authn401(bool): Unsets the authn401 value.

    authnvsname(bool): Unsets the authnvsname value.

    push(bool): Unsets the push value.

    pushvserver(bool): Unsets the pushvserver value.

    pushlabel(bool): Unsets the pushlabel value.

    pushmulticlients(bool): Unsets the pushmulticlients value.

    tcpprofilename(bool): Unsets the tcpprofilename value.

    httpprofilename(bool): Unsets the httpprofilename value.

    dbprofilename(bool): Unsets the dbprofilename value.

    comment(bool): Unsets the comment value.

    l2conn(bool): Unsets the l2conn value.

    oracleserverversion(bool): Unsets the oracleserverversion value.

    mssqlserverversion(bool): Unsets the mssqlserverversion value.

    mysqlprotocolversion(bool): Unsets the mysqlprotocolversion value.

    mysqlserverversion(bool): Unsets the mysqlserverversion value.

    mysqlcharacterset(bool): Unsets the mysqlcharacterset value.

    mysqlservercapabilities(bool): Unsets the mysqlservercapabilities value.

    appflowlog(bool): Unsets the appflowlog value.

    netprofile(bool): Unsets the netprofile value.

    icmpvsrresponse(bool): Unsets the icmpvsrresponse value.

    rhistate(bool): Unsets the rhistate value.

    newservicerequest(bool): Unsets the newservicerequest value.

    newservicerequestunit(bool): Unsets the newservicerequestunit value.

    newservicerequestincrementinterval(bool): Unsets the newservicerequestincrementinterval value.

    minautoscalemembers(bool): Unsets the minautoscalemembers value.

    maxautoscalemembers(bool): Unsets the maxautoscalemembers value.

    persistavpno(bool): Unsets the persistavpno value.

    skippersistency(bool): Unsets the skippersistency value.

    td(bool): Unsets the td value.

    authnprofile(bool): Unsets the authnprofile value.

    macmoderetainvlan(bool): Unsets the macmoderetainvlan value.

    dbslb(bool): Unsets the dbslb value.

    dns64(bool): Unsets the dns64 value.

    bypassaaaa(bool): Unsets the bypassaaaa value.

    recursionavailable(bool): Unsets the recursionavailable value.

    processlocal(bool): Unsets the processlocal value.

    dnsprofilename(bool): Unsets the dnsprofilename value.

    lbprofilename(bool): Unsets the lbprofilename value.

    redirectfromport(bool): Unsets the redirectfromport value.

    httpsredirecturl(bool): Unsets the httpsredirecturl value.

    retainconnectionsoncluster(bool): Unsets the retainconnectionsoncluster value.

    weight(bool): Unsets the weight value.

    servicename(bool): Unsets the servicename value.

    redirurlflags(bool): Unsets the redirurlflags value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.unset_lbvserver <args>

    '''

    result = {}

    payload = {'lbvserver': {}}

    if name:
        payload['lbvserver']['name'] = True

    if servicetype:
        payload['lbvserver']['servicetype'] = True

    if ipv46:
        payload['lbvserver']['ipv46'] = True

    if ippattern:
        payload['lbvserver']['ippattern'] = True

    if ipmask:
        payload['lbvserver']['ipmask'] = True

    if port:
        payload['lbvserver']['port'] = True

    if range:
        payload['lbvserver']['range'] = True

    if persistencetype:
        payload['lbvserver']['persistencetype'] = True

    if timeout:
        payload['lbvserver']['timeout'] = True

    if persistencebackup:
        payload['lbvserver']['persistencebackup'] = True

    if backuppersistencetimeout:
        payload['lbvserver']['backuppersistencetimeout'] = True

    if lbmethod:
        payload['lbvserver']['lbmethod'] = True

    if hashlength:
        payload['lbvserver']['hashlength'] = True

    if netmask:
        payload['lbvserver']['netmask'] = True

    if v6netmasklen:
        payload['lbvserver']['v6netmasklen'] = True

    if backuplbmethod:
        payload['lbvserver']['backuplbmethod'] = True

    if cookiename:
        payload['lbvserver']['cookiename'] = True

    if rule:
        payload['lbvserver']['rule'] = True

    if listenpolicy:
        payload['lbvserver']['listenpolicy'] = True

    if listenpriority:
        payload['lbvserver']['listenpriority'] = True

    if resrule:
        payload['lbvserver']['resrule'] = True

    if persistmask:
        payload['lbvserver']['persistmask'] = True

    if v6persistmasklen:
        payload['lbvserver']['v6persistmasklen'] = True

    if pq:
        payload['lbvserver']['pq'] = True

    if sc:
        payload['lbvserver']['sc'] = True

    if rtspnat:
        payload['lbvserver']['rtspnat'] = True

    if m:
        payload['lbvserver']['m'] = True

    if tosid:
        payload['lbvserver']['tosid'] = True

    if datalength:
        payload['lbvserver']['datalength'] = True

    if dataoffset:
        payload['lbvserver']['dataoffset'] = True

    if sessionless:
        payload['lbvserver']['sessionless'] = True

    if trofspersistence:
        payload['lbvserver']['trofspersistence'] = True

    if state:
        payload['lbvserver']['state'] = True

    if connfailover:
        payload['lbvserver']['connfailover'] = True

    if redirurl:
        payload['lbvserver']['redirurl'] = True

    if cacheable:
        payload['lbvserver']['cacheable'] = True

    if clttimeout:
        payload['lbvserver']['clttimeout'] = True

    if somethod:
        payload['lbvserver']['somethod'] = True

    if sopersistence:
        payload['lbvserver']['sopersistence'] = True

    if sopersistencetimeout:
        payload['lbvserver']['sopersistencetimeout'] = True

    if healththreshold:
        payload['lbvserver']['healththreshold'] = True

    if sothreshold:
        payload['lbvserver']['sothreshold'] = True

    if sobackupaction:
        payload['lbvserver']['sobackupaction'] = True

    if redirectportrewrite:
        payload['lbvserver']['redirectportrewrite'] = True

    if downstateflush:
        payload['lbvserver']['downstateflush'] = True

    if backupvserver:
        payload['lbvserver']['backupvserver'] = True

    if disableprimaryondown:
        payload['lbvserver']['disableprimaryondown'] = True

    if insertvserveripport:
        payload['lbvserver']['insertvserveripport'] = True

    if vipheader:
        payload['lbvserver']['vipheader'] = True

    if authenticationhost:
        payload['lbvserver']['authenticationhost'] = True

    if authentication:
        payload['lbvserver']['authentication'] = True

    if authn401:
        payload['lbvserver']['authn401'] = True

    if authnvsname:
        payload['lbvserver']['authnvsname'] = True

    if push:
        payload['lbvserver']['push'] = True

    if pushvserver:
        payload['lbvserver']['pushvserver'] = True

    if pushlabel:
        payload['lbvserver']['pushlabel'] = True

    if pushmulticlients:
        payload['lbvserver']['pushmulticlients'] = True

    if tcpprofilename:
        payload['lbvserver']['tcpprofilename'] = True

    if httpprofilename:
        payload['lbvserver']['httpprofilename'] = True

    if dbprofilename:
        payload['lbvserver']['dbprofilename'] = True

    if comment:
        payload['lbvserver']['comment'] = True

    if l2conn:
        payload['lbvserver']['l2conn'] = True

    if oracleserverversion:
        payload['lbvserver']['oracleserverversion'] = True

    if mssqlserverversion:
        payload['lbvserver']['mssqlserverversion'] = True

    if mysqlprotocolversion:
        payload['lbvserver']['mysqlprotocolversion'] = True

    if mysqlserverversion:
        payload['lbvserver']['mysqlserverversion'] = True

    if mysqlcharacterset:
        payload['lbvserver']['mysqlcharacterset'] = True

    if mysqlservercapabilities:
        payload['lbvserver']['mysqlservercapabilities'] = True

    if appflowlog:
        payload['lbvserver']['appflowlog'] = True

    if netprofile:
        payload['lbvserver']['netprofile'] = True

    if icmpvsrresponse:
        payload['lbvserver']['icmpvsrresponse'] = True

    if rhistate:
        payload['lbvserver']['rhistate'] = True

    if newservicerequest:
        payload['lbvserver']['newservicerequest'] = True

    if newservicerequestunit:
        payload['lbvserver']['newservicerequestunit'] = True

    if newservicerequestincrementinterval:
        payload['lbvserver']['newservicerequestincrementinterval'] = True

    if minautoscalemembers:
        payload['lbvserver']['minautoscalemembers'] = True

    if maxautoscalemembers:
        payload['lbvserver']['maxautoscalemembers'] = True

    if persistavpno:
        payload['lbvserver']['persistavpno'] = True

    if skippersistency:
        payload['lbvserver']['skippersistency'] = True

    if td:
        payload['lbvserver']['td'] = True

    if authnprofile:
        payload['lbvserver']['authnprofile'] = True

    if macmoderetainvlan:
        payload['lbvserver']['macmoderetainvlan'] = True

    if dbslb:
        payload['lbvserver']['dbslb'] = True

    if dns64:
        payload['lbvserver']['dns64'] = True

    if bypassaaaa:
        payload['lbvserver']['bypassaaaa'] = True

    if recursionavailable:
        payload['lbvserver']['recursionavailable'] = True

    if processlocal:
        payload['lbvserver']['processlocal'] = True

    if dnsprofilename:
        payload['lbvserver']['dnsprofilename'] = True

    if lbprofilename:
        payload['lbvserver']['lbprofilename'] = True

    if redirectfromport:
        payload['lbvserver']['redirectfromport'] = True

    if httpsredirecturl:
        payload['lbvserver']['httpsredirecturl'] = True

    if retainconnectionsoncluster:
        payload['lbvserver']['retainconnectionsoncluster'] = True

    if weight:
        payload['lbvserver']['weight'] = True

    if servicename:
        payload['lbvserver']['servicename'] = True

    if redirurlflags:
        payload['lbvserver']['redirurlflags'] = True

    if newname:
        payload['lbvserver']['newname'] = True

    execution = __proxy__['citrixns.post']('config/lbvserver?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_lbwlm(wlmname=None, ipaddress=None, port=None, lbuid=None, katimeout=None, save=False):
    '''
    Unsets values from the lbwlm configuration key.

    wlmname(bool): Unsets the wlmname value.

    ipaddress(bool): Unsets the ipaddress value.

    port(bool): Unsets the port value.

    lbuid(bool): Unsets the lbuid value.

    katimeout(bool): Unsets the katimeout value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.unset_lbwlm <args>

    '''

    result = {}

    payload = {'lbwlm': {}}

    if wlmname:
        payload['lbwlm']['wlmname'] = True

    if ipaddress:
        payload['lbwlm']['ipaddress'] = True

    if port:
        payload['lbwlm']['port'] = True

    if lbuid:
        payload['lbwlm']['lbuid'] = True

    if katimeout:
        payload['lbwlm']['katimeout'] = True

    execution = __proxy__['citrixns.post']('config/lbwlm?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_lbgroup(name=None, persistencetype=None, persistencebackup=None, backuppersistencetimeout=None,
                   persistmask=None, cookiename=None, v6persistmasklen=None, cookiedomain=None, timeout=None, rule=None,
                   usevserverpersistency=None, mastervserver=None, newname=None, save=False):
    '''
    Update the running configuration for the lbgroup config key.

    name(str): Name of the load balancing virtual server group. Minimum length = 1

    persistencetype(str): Type of persistence for the group. Available settings function as follows: * SOURCEIP - Create
        persistence sessions based on the client IP. * COOKIEINSERT - Create persistence sessions based on a cookie in
        client requests. The cookie is inserted by a Set-Cookie directive from the server, in its first response to a
        client. * RULE - Create persistence sessions based on a user defined rule. * NONE - Disable persistence for the
        group. Possible values = SOURCEIP, COOKIEINSERT, RULE, NONE

    persistencebackup(str): Type of backup persistence for the group. Possible values = SOURCEIP, NONE

    backuppersistencetimeout(int): Time period, in minutes, for which backup persistence is in effect. Default value: 2
        Minimum value = 2 Maximum value = 1440

    persistmask(str): Persistence mask to apply to source IPv4 addresses when creating source IP based persistence sessions.
        Minimum length = 1

    cookiename(str): Use this parameter to specify the cookie name for COOKIE peristence type. It specifies the name of
        cookie with a maximum of 32 characters. If not specified, cookie name is internally generated.

    v6persistmasklen(int): Persistence mask to apply to source IPv6 addresses when creating source IP based persistence
        sessions. Default value: 128 Minimum value = 1 Maximum value = 128

    cookiedomain(str): Domain attribute for the HTTP cookie. Minimum length = 1

    timeout(int): Time period for which a persistence session is in effect. Default value: 2 Minimum value = 0 Maximum value
        = 1440

    rule(str): Expression, or name of a named expression, against which traffic is evaluated. Written in the classic or
        default syntax. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can
        be split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks. Default value: "None"

    usevserverpersistency(str): . Default value: DISABLED Possible values = ENABLED, DISABLED

    mastervserver(str): .

    newname(str): New name for the load balancing virtual server group. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.update_lbgroup <args>

    '''

    result = {}

    payload = {'lbgroup': {}}

    if name:
        payload['lbgroup']['name'] = name

    if persistencetype:
        payload['lbgroup']['persistencetype'] = persistencetype

    if persistencebackup:
        payload['lbgroup']['persistencebackup'] = persistencebackup

    if backuppersistencetimeout:
        payload['lbgroup']['backuppersistencetimeout'] = backuppersistencetimeout

    if persistmask:
        payload['lbgroup']['persistmask'] = persistmask

    if cookiename:
        payload['lbgroup']['cookiename'] = cookiename

    if v6persistmasklen:
        payload['lbgroup']['v6persistmasklen'] = v6persistmasklen

    if cookiedomain:
        payload['lbgroup']['cookiedomain'] = cookiedomain

    if timeout:
        payload['lbgroup']['timeout'] = timeout

    if rule:
        payload['lbgroup']['rule'] = rule

    if usevserverpersistency:
        payload['lbgroup']['usevserverpersistency'] = usevserverpersistency

    if mastervserver:
        payload['lbgroup']['mastervserver'] = mastervserver

    if newname:
        payload['lbgroup']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/lbgroup', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_lbmetrictable(metrictable=None, metric=None, snmpoid=None, save=False):
    '''
    Update the running configuration for the lbmetrictable config key.

    metrictable(str): Name for the metric table. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.   CLI Users: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my metrictable" or my metrictable). Minimum length = 1 Maximum length = 31

    metric(str): Name of the metric for which to change the SNMP OID. Minimum length = 1

    snmpoid(str): New SNMP OID of the metric. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.update_lbmetrictable <args>

    '''

    result = {}

    payload = {'lbmetrictable': {}}

    if metrictable:
        payload['lbmetrictable']['metrictable'] = metrictable

    if metric:
        payload['lbmetrictable']['metric'] = metric

    if snmpoid:
        payload['lbmetrictable']['Snmpoid'] = snmpoid

    execution = __proxy__['citrixns.put']('config/lbmetrictable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_lbmonitor(monitorname=None, ns_type=None, action=None, respcode=None, httprequest=None, rtsprequest=None,
                     customheaders=None, maxforwards=None, sipmethod=None, sipuri=None, sipreguri=None, send=None,
                     recv=None, query=None, querytype=None, scriptname=None, scriptargs=None, dispatcherip=None,
                     dispatcherport=None, username=None, password=None, secondarypassword=None, logonpointname=None,
                     lasversion=None, radkey=None, radnasid=None, radnasip=None, radaccounttype=None, radframedip=None,
                     radapn=None, radmsisdn=None, radaccountsession=None, lrtm=None, deviation=None, units1=None,
                     interval=None, units3=None, resptimeout=None, units4=None, resptimeoutthresh=None, retries=None,
                     failureretries=None, alertretries=None, successretries=None, downtime=None, units2=None,
                     destip=None, destport=None, state=None, reverse=None, transparent=None, iptunnel=None, tos=None,
                     tosid=None, secure=None, validatecred=None, domain=None, ipaddress=None, group=None, filename=None,
                     basedn=None, binddn=None, filter=None, attribute=None, database=None, oraclesid=None, sqlquery=None,
                     evalrule=None, mssqlprotocolversion=None, snmpoid=None, snmpcommunity=None, snmpthreshold=None,
                     snmpversion=None, metrictable=None, application=None, sitepath=None, storename=None,
                     storefrontacctservice=None, hostname=None, netprofile=None, originhost=None, originrealm=None,
                     hostipaddress=None, vendorid=None, productname=None, firmwarerevision=None, authapplicationid=None,
                     acctapplicationid=None, inbandsecurityid=None, supportedvendorids=None, vendorspecificvendorid=None,
                     vendorspecificauthapplicationids=None, vendorspecificacctapplicationids=None, kcdaccount=None,
                     storedb=None, storefrontcheckbackendservices=None, trofscode=None, trofsstring=None,
                     sslprofile=None, metric=None, metricthreshold=None, metricweight=None, servicename=None,
                     servicegroupname=None, save=False):
    '''
    Update the running configuration for the lbmonitor config key.

    monitorname(str): Name for the monitor. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.  CLI Users: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my monitor" or my monitor). Minimum length = 1

    ns_type(str): Type of monitor that you want to create. Possible values = PING, TCP, HTTP, TCP-ECV, HTTP-ECV, UDP-ECV,
        DNS, FTP, LDNS-PING, LDNS-TCP, LDNS-DNS, RADIUS, USER, HTTP-INLINE, SIP-UDP, SIP-TCP, LOAD, FTP-EXTENDED, SMTP,
        SNMP, NNTP, MYSQL, MYSQL-ECV, MSSQL-ECV, ORACLE-ECV, LDAP, POP3, CITRIX-XML-SERVICE, CITRIX-WEB-INTERFACE,
        DNS-TCP, RTSP, ARP, CITRIX-AG, CITRIX-AAC-LOGINPAGE, CITRIX-AAC-LAS, CITRIX-XD-DDC, ND6, CITRIX-WI-EXTENDED,
        DIAMETER, RADIUS_ACCOUNTING, STOREFRONT, APPC, SMPP, CITRIX-XNC-ECV, CITRIX-XDM, CITRIX-STA-SERVICE,
        CITRIX-STA-SERVICE-NHOP

    action(str): Action to perform when the response to an inline monitor (a monitor of type HTTP-INLINE) indicates that the
        service is down. A service monitored by an inline monitor is considered DOWN if the response code is not one of
        the codes that have been specified for the Response Code parameter.  Available settings function as follows:  *
        NONE - Do not take any action. However, the show service command and the show lb monitor command indicate the
        total number of responses that were checked and the number of consecutive error responses received after the last
        successful probe. * LOG - Log the event in NSLOG or SYSLOG.  * DOWN - Mark the service as being down, and then do
        not direct any traffic to the service until the configured down time has expired. Persistent connections to the
        service are terminated as soon as the service is marked as DOWN. Also, log the event in NSLOG or SYSLOG. Default
        value: DOWN Possible values = NONE, LOG, DOWN

    respcode(list(str)): Response codes for which to mark the service as UP. For any other response code, the action
        performed depends on the monitor type. HTTP monitors and RADIUS monitors mark the service as DOWN, while
        HTTP-INLINE monitors perform the action indicated by the Action parameter.

    httprequest(str): HTTP request to send to the server (for example, "HEAD /file.html").

    rtsprequest(str): RTSP request to send to the server (for example, "OPTIONS *").

    customheaders(str): Custom header string to include in the monitoring probes.

    maxforwards(int): Maximum number of hops that the SIP request used for monitoring can traverse to reach the server.
        Applicable only to monitors of type SIP-UDP. Default value: 1 Minimum value = 0 Maximum value = 255

    sipmethod(str): SIP method to use for the query. Applicable only to monitors of type SIP-UDP. Possible values = OPTIONS,
        INVITE, REGISTER

    sipuri(str): SIP URI string to send to the service (for example, sip:sip.test). Applicable only to monitors of type
        SIP-UDP. Minimum length = 1

    sipreguri(str): SIP user to be registered. Applicable only if the monitor is of type SIP-UDP and the SIP Method parameter
        is set to REGISTER. Minimum length = 1

    send(str): String to send to the service. Applicable to TCP-ECV, HTTP-ECV, and UDP-ECV monitors.

    recv(str): String expected from the server for the service to be marked as UP. Applicable to TCP-ECV, HTTP-ECV, and
        UDP-ECV monitors.

    query(str): Domain name to resolve as part of monitoring the DNS service (for example, example.com).

    querytype(str): Type of DNS record for which to send monitoring queries. Set to Address for querying A records, AAAA for
        querying AAAA records, and Zone for querying the SOA record. Possible values = Address, Zone, AAAA

    scriptname(str): Path and name of the script to execute. The script must be available on the NetScaler appliance, in the
        /nsconfig/monitors/ directory. Minimum length = 1

    scriptargs(str): String of arguments for the script. The string is copied verbatim into the request.

    dispatcherip(str): IP address of the dispatcher to which to send the probe.

    dispatcherport(int): Port number on which the dispatcher listens for the monitoring probe.

    username(str): User name with which to probe the RADIUS, NNTP, FTP, FTP-EXTENDED, MYSQL, MSSQL, POP3, CITRIX-AG,
        CITRIX-XD-DDC, CITRIX-WI-EXTENDED, CITRIX-XNC or CITRIX-XDM server. Minimum length = 1

    password(str): Password that is required for logging on to the RADIUS, NNTP, FTP, FTP-EXTENDED, MYSQL, MSSQL, POP3,
        CITRIX-AG, CITRIX-XD-DDC, CITRIX-WI-EXTENDED, CITRIX-XNC-ECV or CITRIX-XDM server. Used in conjunction with the
        user name specified for the User Name parameter. Minimum length = 1

    secondarypassword(str): Secondary password that users might have to provide to log on to the Access Gateway server.
        Applicable to CITRIX-AG monitors.

    logonpointname(str): Name of the logon point that is configured for the Citrix Access Gateway Advanced Access Control
        software. Required if you want to monitor the associated login page or Logon Agent. Applicable to CITRIX-AAC-LAS
        and CITRIX-AAC-LOGINPAGE monitors.

    lasversion(str): Version number of the Citrix Advanced Access Control Logon Agent. Required by the CITRIX-AAC-LAS
        monitor.

    radkey(str): Authentication key (shared secret text string) for RADIUS clients and servers to exchange. Applicable to
        monitors of type RADIUS and RADIUS_ACCOUNTING. Minimum length = 1

    radnasid(str): NAS-Identifier to send in the Access-Request packet. Applicable to monitors of type RADIUS. Minimum length
        = 1

    radnasip(str): Network Access Server (NAS) IP address to use as the source IP address when monitoring a RADIUS server.
        Applicable to monitors of type RADIUS and RADIUS_ACCOUNTING.

    radaccounttype(int): Account Type to be used in Account Request Packet. Applicable to monitors of type RADIUS_ACCOUNTING.
        Default value: 1 Minimum value = 0 Maximum value = 15

    radframedip(str): Source ip with which the packet will go out . Applicable to monitors of type RADIUS_ACCOUNTING.

    radapn(str): Called Station Id to be used in Account Request Packet. Applicable to monitors of type RADIUS_ACCOUNTING.
        Minimum length = 1

    radmsisdn(str): Calling Stations Id to be used in Account Request Packet. Applicable to monitors of type
        RADIUS_ACCOUNTING. Minimum length = 1

    radaccountsession(str): Account Session ID to be used in Account Request Packet. Applicable to monitors of type
        RADIUS_ACCOUNTING. Minimum length = 1

    lrtm(str): Calculate the least response times for bound services. If this parameter is not enabled, the appliance does
        not learn the response times of the bound services. Also used for LRTM load balancing. Possible values = ENABLED,
        DISABLED

    deviation(int): Time value added to the learned average response time in dynamic response time monitoring (DRTM). When a
        deviation is specified, the appliance learns the average response time of bound services and adds the deviation
        to the average. The final value is then continually adjusted to accommodate response time variations over time.
        Specified in milliseconds, seconds, or minutes. Minimum value = 0 Maximum value = 20939

    units1(str): Unit of measurement for the Deviation parameter. Cannot be changed after the monitor is created. Default
        value: SEC Possible values = SEC, MSEC, MIN

    interval(int): Time interval between two successive probes. Must be greater than the value of Response Time-out. Default
        value: 5 Minimum value = 1 Maximum value = 20940

    units3(str): monitor interval units. Default value: SEC Possible values = SEC, MSEC, MIN

    resptimeout(int): Amount of time for which the appliance must wait before it marks a probe as FAILED. Must be less than
        the value specified for the Interval parameter.  Note: For UDP-ECV monitors for which a receive string is not
        configured, response timeout does not apply. For UDP-ECV monitors with no receive string, probe failure is
        indicated by an ICMP port unreachable error received from the service. Default value: 2 Minimum value = 1 Maximum
        value = 20939

    units4(str): monitor response timeout units. Default value: SEC Possible values = SEC, MSEC, MIN

    resptimeoutthresh(int): Response time threshold, specified as a percentage of the Response Time-out parameter. If the
        response to a monitor probe has not arrived when the threshold is reached, the appliance generates an SNMP trap
        called monRespTimeoutAboveThresh. After the response time returns to a value below the threshold, the appliance
        generates a monRespTimeoutBelowThresh SNMP trap. For the traps to be generated, the "MONITOR-RTO-THRESHOLD" alarm
        must also be enabled. Minimum value = 0 Maximum value = 100

    retries(int): Maximum number of probes to send to establish the state of a service for which a monitoring probe failed.
        Default value: 3 Minimum value = 1 Maximum value = 127

    failureretries(int): Number of retries that must fail, out of the number specified for the Retries parameter, for a
        service to be marked as DOWN. For example, if the Retries parameter is set to 10 and the Failure Retries
        parameter is set to 6, out of the ten probes sent, at least six probes must fail if the service is to be marked
        as DOWN. The default value of 0 means that all the retries must fail if the service is to be marked as DOWN.
        Minimum value = 0 Maximum value = 32

    alertretries(int): Number of consecutive probe failures after which the appliance generates an SNMP trap called
        monProbeFailed. Minimum value = 0 Maximum value = 32

    successretries(int): Number of consecutive successful probes required to transition a services state from DOWN to UP.
        Default value: 1 Minimum value = 1 Maximum value = 32

    downtime(int): Time duration for which to wait before probing a service that has been marked as DOWN. Expressed in
        milliseconds, seconds, or minutes. Default value: 30 Minimum value = 1 Maximum value = 20939

    units2(str): Unit of measurement for the Down Time parameter. Cannot be changed after the monitor is created. Default
        value: SEC Possible values = SEC, MSEC, MIN

    destip(str): IP address of the service to which to send probes. If the parameter is set to 0, the IP address of the
        server to which the monitor is bound is considered the destination IP address.

    destport(int): TCP or UDP port to which to send the probe. If the parameter is set to 0, the port number of the service
        to which the monitor is bound is considered the destination port. For a monitor of type USER, however, the
        destination port is the port number that is included in the HTTP request sent to the dispatcher. Does not apply
        to monitors of type PING.

    state(str): State of the monitor. The DISABLED setting disables not only the monitor being configured, but all monitors
        of the same type, until the parameter is set to ENABLED. If the monitor is bound to a service, the state of the
        monitor is not taken into account when the state of the service is determined. Default value: ENABLED Possible
        values = ENABLED, DISABLED

    reverse(str): Mark a service as DOWN, instead of UP, when probe criteria are satisfied, and as UP instead of DOWN when
        probe criteria are not satisfied. Default value: NO Possible values = YES, NO

    transparent(str): The monitor is bound to a transparent device such as a firewall or router. The state of a transparent
        device depends on the responsiveness of the services behind it. If a transparent device is being monitored, a
        destination IP address must be specified. The probe is sent to the specified IP address by using the MAC address
        of the transparent device. Default value: NO Possible values = YES, NO

    iptunnel(str): Send the monitoring probe to the service through an IP tunnel. A destination IP address must be specified.
        Default value: NO Possible values = YES, NO

    tos(str): Probe the service by encoding the destination IP address in the IP TOS (6) bits. Possible values = YES, NO

    tosid(int): The TOS ID of the specified destination IP. Applicable only when the TOS parameter is set. Minimum value = 1
        Maximum value = 63

    secure(str): Use a secure SSL connection when monitoring a service. Applicable only to TCP based monitors. The secure
        option cannot be used with a CITRIX-AG monitor, because a CITRIX-AG monitor uses a secure connection by default.
        Default value: NO Possible values = YES, NO

    validatecred(str): Validate the credentials of the Xen Desktop DDC server user. Applicable to monitors of type
        CITRIX-XD-DDC. Default value: NO Possible values = YES, NO

    domain(str): Domain in which the XenDesktop Desktop Delivery Controller (DDC) servers or Web Interface servers are
        present. Required by CITRIX-XD-DDC and CITRIX-WI-EXTENDED monitors for logging on to the DDC servers and Web
        Interface servers, respectively.

    ipaddress(list(str)): Set of IP addresses expected in the monitoring response from the DNS server, if the record type is
        A or AAAA. Applicable to DNS monitors. Minimum length = 1

    group(str): Name of a newsgroup available on the NNTP service that is to be monitored. The appliance periodically
        generates an NNTP query for the name of the newsgroup and evaluates the response. If the newsgroup is found on
        the server, the service is marked as UP. If the newsgroup does not exist or if the search fails, the service is
        marked as DOWN. Applicable to NNTP monitors. Minimum length = 1

    filename(str): Name of a file on the FTP server. The appliance monitors the FTP service by periodically checking the
        existence of the file on the server. Applicable to FTP-EXTENDED monitors. Minimum length = 1

    basedn(str): The base distinguished name of the LDAP service, from where the LDAP server can begin the search for the
        attributes in the monitoring query. Required for LDAP service monitoring. Minimum length = 1

    binddn(str): The distinguished name with which an LDAP monitor can perform the Bind operation on the LDAP server.
        Optional. Applicable to LDAP monitors. Minimum length = 1

    filter(str): Filter criteria for the LDAP query. Optional. Minimum length = 1

    attribute(str): Attribute to evaluate when the LDAP server responds to the query. Success or failure of the monitoring
        probe depends on whether the attribute exists in the response. Optional. Minimum length = 1

    database(str): Name of the database to connect to during authentication. Minimum length = 1

    oraclesid(str): Name of the service identifier that is used to connect to the Oracle database during authentication.
        Minimum length = 1

    sqlquery(str): SQL query for a MYSQL-ECV or MSSQL-ECV monitor. Sent to the database server after the server authenticates
        the connection. Minimum length = 1

    evalrule(str): Default syntax expression that evaluates the database servers response to a MYSQL-ECV or MSSQL-ECV
        monitoring query. Must produce a Boolean result. The result determines the state of the server. If the expression
        returns TRUE, the probe succeeds.  For example, if you want the appliance to evaluate the error message to
        determine the state of the server, use the rule MYSQL.RES.ROW(10) .TEXT_ELEM(2).EQ("MySQL").

    mssqlprotocolversion(str): Version of MSSQL server that is to be monitored. Default value: 70 Possible values = 70, 2000,
        2000SP1, 2005, 2008, 2008R2, 2012, 2014

    snmpoid(str): SNMP OID for SNMP monitors. Minimum length = 1

    snmpcommunity(str): Community name for SNMP monitors. Minimum length = 1

    snmpthreshold(str): Threshold for SNMP monitors. Minimum length = 1

    snmpversion(str): SNMP version to be used for SNMP monitors. Possible values = V1, V2

    metrictable(str): Metric table to which to bind metrics. Minimum length = 1 Maximum length = 99

    application(str): Name of the application used to determine the state of the service. Applicable to monitors of type
        CITRIX-XML-SERVICE. Minimum length = 1

    sitepath(str): URL of the logon page. For monitors of type CITRIX-WEB-INTERFACE, to monitor a dynamic page under the site
        path, terminate the site path with a slash (/). Applicable to CITRIX-WEB-INTERFACE, CITRIX-WI-EXTENDED and
        CITRIX-XDM monitors. Minimum length = 1

    storename(str): Store Name. For monitors of type STOREFRONT, STORENAME is an optional argument defining storefront
        service store name. Applicable to STOREFRONT monitors. Minimum length = 1

    storefrontacctservice(str): Enable/Disable probing for Account Service. Applicable only to Store Front monitors. For
        multi-tenancy configuration users my skip account service. Default value: YES Possible values = YES, NO

    hostname(str): Hostname in the FQDN format (Example: porche.cars.org). Applicable to STOREFRONT monitors. Minimum length
        = 1

    netprofile(str): Name of the network profile. Minimum length = 1 Maximum length = 127

    originhost(str): Origin-Host value for the Capabilities-Exchange-Request (CER) message to use for monitoring Diameter
        servers. Minimum length = 1

    originrealm(str): Origin-Realm value for the Capabilities-Exchange-Request (CER) message to use for monitoring Diameter
        servers. Minimum length = 1

    hostipaddress(str): Host-IP-Address value for the Capabilities-Exchange-Request (CER) message to use for monitoring
        Diameter servers. If Host-IP-Address is not specified, the appliance inserts the mapped IP (MIP) address or
        subnet IP (SNIP) address from which the CER request (the monitoring probe) is sent. Minimum length = 1

    vendorid(int): Vendor-Id value for the Capabilities-Exchange-Request (CER) message to use for monitoring Diameter
        servers.

    productname(str): Product-Name value for the Capabilities-Exchange-Request (CER) message to use for monitoring Diameter
        servers. Minimum length = 1

    firmwarerevision(int): Firmware-Revision value for the Capabilities-Exchange-Request (CER) message to use for monitoring
        Diameter servers.

    authapplicationid(list(int)): List of Auth-Application-Id attribute value pairs (AVPs) for the
        Capabilities-Exchange-Request (CER) message to use for monitoring Diameter servers. A maximum of eight of these
        AVPs are supported in a monitoring CER message. Minimum value = 0 Maximum value = 4294967295

    acctapplicationid(list(int)): List of Acct-Application-Id attribute value pairs (AVPs) for the
        Capabilities-Exchange-Request (CER) message to use for monitoring Diameter servers. A maximum of eight of these
        AVPs are supported in a monitoring message. Minimum value = 0 Maximum value = 4294967295

    inbandsecurityid(str): Inband-Security-Id for the Capabilities-Exchange-Request (CER) message to use for monitoring
        Diameter servers. Possible values = NO_INBAND_SECURITY, TLS

    supportedvendorids(list(int)): List of Supported-Vendor-Id attribute value pairs (AVPs) for the
        Capabilities-Exchange-Request (CER) message to use for monitoring Diameter servers. A maximum eight of these AVPs
        are supported in a monitoring message. Minimum value = 1 Maximum value = 4294967295

    vendorspecificvendorid(int): Vendor-Id to use in the Vendor-Specific-Application-Id grouped attribute-value pair (AVP) in
        the monitoring CER message. To specify Auth-Application-Id or Acct-Application-Id in
        Vendor-Specific-Application-Id, use vendorSpecificAuthApplicationIds or vendorSpecificAcctApplicationIds,
        respectively. Only one Vendor-Id is supported for all the Vendor-Specific-Application-Id AVPs in a CER monitoring
        message. Minimum value = 1

    vendorspecificauthapplicationids(list(int)): List of Vendor-Specific-Auth-Application-Id attribute value pairs (AVPs) for
        the Capabilities-Exchange-Request (CER) message to use for monitoring Diameter servers. A maximum of eight of
        these AVPs are supported in a monitoring message. The specified value is combined with the value of
        vendorSpecificVendorId to obtain the Vendor-Specific-Application-Id AVP in the CER monitoring message. Minimum
        value = 0 Maximum value = 4294967295

    vendorspecificacctapplicationids(list(int)): List of Vendor-Specific-Acct-Application-Id attribute value pairs (AVPs) to
        use for monitoring Diameter servers. A maximum of eight of these AVPs are supported in a monitoring message. The
        specified value is combined with the value of vendorSpecificVendorId to obtain the Vendor-Specific-Application-Id
        AVP in the CER monitoring message. Minimum value = 0 Maximum value = 4294967295

    kcdaccount(str): KCD Account used by MSSQL monitor. Minimum length = 1 Maximum length = 32

    storedb(str): Store the database list populated with the responses to monitor probes. Used in database specific load
        balancing if MSSQL-ECV/MYSQL-ECV monitor is configured. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    storefrontcheckbackendservices(str): This option will enable monitoring of services running on storefront server.
        Storefront services are monitored by probing to a Windows service that runs on the Storefront server and exposes
        details of which storefront services are running. Default value: NO Possible values = YES, NO

    trofscode(int): Code expected when the server is under maintenance.

    trofsstring(str): String expected from the server for the service to be marked as trofs. Applicable to HTTP-ECV/TCP-ECV
        monitors.

    sslprofile(str): SSL Profile associated with the monitor. Minimum length = 1 Maximum length = 127

    metric(str): Metric name in the metric table, whose setting is changed. A value zero disables the metric and it will not
        be used for load calculation. Minimum length = 1 Maximum length = 37

    metricthreshold(int): Threshold to be used for that metric.

    metricweight(int): The weight for the specified service metric with respect to others. Minimum value = 1 Maximum value =
        100

    servicename(str): The name of the service to which the monitor is bound. Minimum length = 1

    servicegroupname(str): The name of the service group to which the monitor is to be bound. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.update_lbmonitor <args>

    '''

    result = {}

    payload = {'lbmonitor': {}}

    if monitorname:
        payload['lbmonitor']['monitorname'] = monitorname

    if ns_type:
        payload['lbmonitor']['type'] = ns_type

    if action:
        payload['lbmonitor']['action'] = action

    if respcode:
        payload['lbmonitor']['respcode'] = respcode

    if httprequest:
        payload['lbmonitor']['httprequest'] = httprequest

    if rtsprequest:
        payload['lbmonitor']['rtsprequest'] = rtsprequest

    if customheaders:
        payload['lbmonitor']['customheaders'] = customheaders

    if maxforwards:
        payload['lbmonitor']['maxforwards'] = maxforwards

    if sipmethod:
        payload['lbmonitor']['sipmethod'] = sipmethod

    if sipuri:
        payload['lbmonitor']['sipuri'] = sipuri

    if sipreguri:
        payload['lbmonitor']['sipreguri'] = sipreguri

    if send:
        payload['lbmonitor']['send'] = send

    if recv:
        payload['lbmonitor']['recv'] = recv

    if query:
        payload['lbmonitor']['query'] = query

    if querytype:
        payload['lbmonitor']['querytype'] = querytype

    if scriptname:
        payload['lbmonitor']['scriptname'] = scriptname

    if scriptargs:
        payload['lbmonitor']['scriptargs'] = scriptargs

    if dispatcherip:
        payload['lbmonitor']['dispatcherip'] = dispatcherip

    if dispatcherport:
        payload['lbmonitor']['dispatcherport'] = dispatcherport

    if username:
        payload['lbmonitor']['username'] = username

    if password:
        payload['lbmonitor']['password'] = password

    if secondarypassword:
        payload['lbmonitor']['secondarypassword'] = secondarypassword

    if logonpointname:
        payload['lbmonitor']['logonpointname'] = logonpointname

    if lasversion:
        payload['lbmonitor']['lasversion'] = lasversion

    if radkey:
        payload['lbmonitor']['radkey'] = radkey

    if radnasid:
        payload['lbmonitor']['radnasid'] = radnasid

    if radnasip:
        payload['lbmonitor']['radnasip'] = radnasip

    if radaccounttype:
        payload['lbmonitor']['radaccounttype'] = radaccounttype

    if radframedip:
        payload['lbmonitor']['radframedip'] = radframedip

    if radapn:
        payload['lbmonitor']['radapn'] = radapn

    if radmsisdn:
        payload['lbmonitor']['radmsisdn'] = radmsisdn

    if radaccountsession:
        payload['lbmonitor']['radaccountsession'] = radaccountsession

    if lrtm:
        payload['lbmonitor']['lrtm'] = lrtm

    if deviation:
        payload['lbmonitor']['deviation'] = deviation

    if units1:
        payload['lbmonitor']['units1'] = units1

    if interval:
        payload['lbmonitor']['interval'] = interval

    if units3:
        payload['lbmonitor']['units3'] = units3

    if resptimeout:
        payload['lbmonitor']['resptimeout'] = resptimeout

    if units4:
        payload['lbmonitor']['units4'] = units4

    if resptimeoutthresh:
        payload['lbmonitor']['resptimeoutthresh'] = resptimeoutthresh

    if retries:
        payload['lbmonitor']['retries'] = retries

    if failureretries:
        payload['lbmonitor']['failureretries'] = failureretries

    if alertretries:
        payload['lbmonitor']['alertretries'] = alertretries

    if successretries:
        payload['lbmonitor']['successretries'] = successretries

    if downtime:
        payload['lbmonitor']['downtime'] = downtime

    if units2:
        payload['lbmonitor']['units2'] = units2

    if destip:
        payload['lbmonitor']['destip'] = destip

    if destport:
        payload['lbmonitor']['destport'] = destport

    if state:
        payload['lbmonitor']['state'] = state

    if reverse:
        payload['lbmonitor']['reverse'] = reverse

    if transparent:
        payload['lbmonitor']['transparent'] = transparent

    if iptunnel:
        payload['lbmonitor']['iptunnel'] = iptunnel

    if tos:
        payload['lbmonitor']['tos'] = tos

    if tosid:
        payload['lbmonitor']['tosid'] = tosid

    if secure:
        payload['lbmonitor']['secure'] = secure

    if validatecred:
        payload['lbmonitor']['validatecred'] = validatecred

    if domain:
        payload['lbmonitor']['domain'] = domain

    if ipaddress:
        payload['lbmonitor']['ipaddress'] = ipaddress

    if group:
        payload['lbmonitor']['group'] = group

    if filename:
        payload['lbmonitor']['filename'] = filename

    if basedn:
        payload['lbmonitor']['basedn'] = basedn

    if binddn:
        payload['lbmonitor']['binddn'] = binddn

    if filter:
        payload['lbmonitor']['filter'] = filter

    if attribute:
        payload['lbmonitor']['attribute'] = attribute

    if database:
        payload['lbmonitor']['database'] = database

    if oraclesid:
        payload['lbmonitor']['oraclesid'] = oraclesid

    if sqlquery:
        payload['lbmonitor']['sqlquery'] = sqlquery

    if evalrule:
        payload['lbmonitor']['evalrule'] = evalrule

    if mssqlprotocolversion:
        payload['lbmonitor']['mssqlprotocolversion'] = mssqlprotocolversion

    if snmpoid:
        payload['lbmonitor']['Snmpoid'] = snmpoid

    if snmpcommunity:
        payload['lbmonitor']['snmpcommunity'] = snmpcommunity

    if snmpthreshold:
        payload['lbmonitor']['snmpthreshold'] = snmpthreshold

    if snmpversion:
        payload['lbmonitor']['snmpversion'] = snmpversion

    if metrictable:
        payload['lbmonitor']['metrictable'] = metrictable

    if application:
        payload['lbmonitor']['application'] = application

    if sitepath:
        payload['lbmonitor']['sitepath'] = sitepath

    if storename:
        payload['lbmonitor']['storename'] = storename

    if storefrontacctservice:
        payload['lbmonitor']['storefrontacctservice'] = storefrontacctservice

    if hostname:
        payload['lbmonitor']['hostname'] = hostname

    if netprofile:
        payload['lbmonitor']['netprofile'] = netprofile

    if originhost:
        payload['lbmonitor']['originhost'] = originhost

    if originrealm:
        payload['lbmonitor']['originrealm'] = originrealm

    if hostipaddress:
        payload['lbmonitor']['hostipaddress'] = hostipaddress

    if vendorid:
        payload['lbmonitor']['vendorid'] = vendorid

    if productname:
        payload['lbmonitor']['productname'] = productname

    if firmwarerevision:
        payload['lbmonitor']['firmwarerevision'] = firmwarerevision

    if authapplicationid:
        payload['lbmonitor']['authapplicationid'] = authapplicationid

    if acctapplicationid:
        payload['lbmonitor']['acctapplicationid'] = acctapplicationid

    if inbandsecurityid:
        payload['lbmonitor']['inbandsecurityid'] = inbandsecurityid

    if supportedvendorids:
        payload['lbmonitor']['supportedvendorids'] = supportedvendorids

    if vendorspecificvendorid:
        payload['lbmonitor']['vendorspecificvendorid'] = vendorspecificvendorid

    if vendorspecificauthapplicationids:
        payload['lbmonitor']['vendorspecificauthapplicationids'] = vendorspecificauthapplicationids

    if vendorspecificacctapplicationids:
        payload['lbmonitor']['vendorspecificacctapplicationids'] = vendorspecificacctapplicationids

    if kcdaccount:
        payload['lbmonitor']['kcdaccount'] = kcdaccount

    if storedb:
        payload['lbmonitor']['storedb'] = storedb

    if storefrontcheckbackendservices:
        payload['lbmonitor']['storefrontcheckbackendservices'] = storefrontcheckbackendservices

    if trofscode:
        payload['lbmonitor']['trofscode'] = trofscode

    if trofsstring:
        payload['lbmonitor']['trofsstring'] = trofsstring

    if sslprofile:
        payload['lbmonitor']['sslprofile'] = sslprofile

    if metric:
        payload['lbmonitor']['metric'] = metric

    if metricthreshold:
        payload['lbmonitor']['metricthreshold'] = metricthreshold

    if metricweight:
        payload['lbmonitor']['metricweight'] = metricweight

    if servicename:
        payload['lbmonitor']['servicename'] = servicename

    if servicegroupname:
        payload['lbmonitor']['servicegroupname'] = servicegroupname

    execution = __proxy__['citrixns.put']('config/lbmonitor', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_lbparameter(httponlycookieflag=None, usesecuredpersistencecookie=None, useencryptedpersistencecookie=None,
                       cookiepassphrase=None, consolidatedlconn=None, useportforhashlb=None, preferdirectroute=None,
                       startuprrfactor=None, monitorskipmaxclient=None, monitorconnectionclose=None,
                       vserverspecificmac=None, allowboundsvcremoval=None, retainservicestate=None, save=False):
    '''
    Update the running configuration for the lbparameter config key.

    httponlycookieflag(str): Include the HttpOnly attribute in persistence cookies. The HttpOnly attribute limits the scope
        of a cookie to HTTP requests and helps mitigate the risk of cross-site scripting attacks. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    usesecuredpersistencecookie(str): Encode persistence cookie values using SHA2 hash. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    useencryptedpersistencecookie(str): Encode persistence cookie values using SHA2 hash. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    cookiepassphrase(str): Use this parameter to specify the passphrase used to generate secured persistence cookie value. It
        specifies the passphrase with a maximum of 31 characters.

    consolidatedlconn(str): To find the service with the fewest connections, the virtual server uses the consolidated
        connection statistics from all the packet engines. The NO setting allows consideration of only the number of
        connections on the packet engine that received the new connection. Default value: YES Possible values = YES, NO

    useportforhashlb(str): Include the port number of the service when creating a hash for hash based load balancing methods.
        With the NO setting, only the IP address of the service is considered when creating a hash. Default value: YES
        Possible values = YES, NO

    preferdirectroute(str): Perform route lookup for traffic received by the NetScaler appliance, and forward the traffic
        according to configured routes. Do not set this parameter if you want a wildcard virtual server to direct packets
        received by the appliance to an intermediary device, such as a firewall, even if their destination is directly
        connected to the appliance. Route lookup is performed after the packets have been processed and returned by the
        intermediary device. Default value: YES Possible values = YES, NO

    startuprrfactor(int): Number of requests, per service, for which to apply the round robin load balancing method before
        switching to the configured load balancing method, thus allowing services to ramp up gradually to full load.
        Until the specified number of requests is distributed, the NetScaler appliance is said to be implementing the
        slow start mode (or startup round robin). Implemented for a virtual server when one of the following is true: *
        The virtual server is newly created. * One or more services are newly bound to the virtual server.  * One or more
        services bound to the virtual server are enabled. * The load balancing method is changed. This parameter applies
        to all the load balancing virtual servers configured on the NetScaler appliance, except for those virtual servers
        for which the virtual server-level slow start parameters (New Service Startup Request Rate and Increment
        Interval) are configured. If the global slow start parameter and the slow start parameters for a given virtual
        server are not set, the appliance implements a default slow start for the virtual server, as follows: * For a
        newly configured virtual server, the appliance implements slow start for the first 100 requests received by the
        virtual server. * For an existing virtual server, if one or more services are newly bound or newly enabled, or if
        the load balancing method is changed, the appliance dynamically computes the number of requests for which to
        implement startup round robin. It obtains this number by multiplying the request rate by the number of bound
        services (it includes services that are marked as DOWN). For example, if the current request rate is 20
        requests/s and ten services are bound to the virtual server, the appliance performs startup round robin for 200
        requests. Not applicable to a virtual server for which a hash based load balancing method is configured.

    monitorskipmaxclient(str): When a monitor initiates a connection to a service, do not check to determine whether the
        number of connections to the service has reached the limit specified by the services Max Clients setting. Enables
        monitoring to continue even if the service has reached its connection limit. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    monitorconnectionclose(str): Close monitoring connections by sending the service a connection termination message with
        the specified bit set. Default value: FIN Possible values = RESET, FIN

    vserverspecificmac(str): Allow a MAC-mode virtual server to accept traffic returned by an intermediary device, such as a
        firewall, to which the traffic was previously forwarded by another MAC-mode virtual server. The second virtual
        server can then distribute that traffic across the destination server farm. Also useful when load balancing
        Branch Repeater appliances. Note: The second virtual server can also send the traffic to another set of
        intermediary devices, such as another set of firewalls. If necessary, you can configure multiple MAC-mode virtual
        servers to pass traffic successively through multiple sets of intermediary devices. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    allowboundsvcremoval(str): This is used, to enable/disable the option of svc/svcgroup removal, if it is bound to one or
        more vserver. If it is enabled, the svc/svcgroup can be removed, even if it bound to vservers. If disabled, an
        error will be thrown, when the user tries to remove a svc/svcgroup without unbinding from its vservers. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    retainservicestate(str): This option is used to retain the original state of service or servicegroup member when an
        enable server command is issued. Default value: OFF Possible values = ON, OFF

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.update_lbparameter <args>

    '''

    result = {}

    payload = {'lbparameter': {}}

    if httponlycookieflag:
        payload['lbparameter']['httponlycookieflag'] = httponlycookieflag

    if usesecuredpersistencecookie:
        payload['lbparameter']['usesecuredpersistencecookie'] = usesecuredpersistencecookie

    if useencryptedpersistencecookie:
        payload['lbparameter']['useencryptedpersistencecookie'] = useencryptedpersistencecookie

    if cookiepassphrase:
        payload['lbparameter']['cookiepassphrase'] = cookiepassphrase

    if consolidatedlconn:
        payload['lbparameter']['consolidatedlconn'] = consolidatedlconn

    if useportforhashlb:
        payload['lbparameter']['useportforhashlb'] = useportforhashlb

    if preferdirectroute:
        payload['lbparameter']['preferdirectroute'] = preferdirectroute

    if startuprrfactor:
        payload['lbparameter']['startuprrfactor'] = startuprrfactor

    if monitorskipmaxclient:
        payload['lbparameter']['monitorskipmaxclient'] = monitorskipmaxclient

    if monitorconnectionclose:
        payload['lbparameter']['monitorconnectionclose'] = monitorconnectionclose

    if vserverspecificmac:
        payload['lbparameter']['vserverspecificmac'] = vserverspecificmac

    if allowboundsvcremoval:
        payload['lbparameter']['allowboundsvcremoval'] = allowboundsvcremoval

    if retainservicestate:
        payload['lbparameter']['retainservicestate'] = retainservicestate

    execution = __proxy__['citrixns.put']('config/lbparameter', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_lbprofile(lbprofilename=None, dbslb=None, processlocal=None, httponlycookieflag=None, cookiepassphrase=None,
                     usesecuredpersistencecookie=None, useencryptedpersistencecookie=None, save=False):
    '''
    Update the running configuration for the lbprofile config key.

    lbprofilename(str): Name of the LB profile. Minimum length = 1

    dbslb(str): Enable database specific load balancing for MySQL and MSSQL service types. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    processlocal(str): By turning on this option packets destined to a vserver in a cluster will not under go any steering.
        Turn this option for single pa cket request response mode or when the upstream device is performing a proper RSS
        for connection based distribution. Default value: DISABLED Possible values = ENABLED, DISABLED

    httponlycookieflag(str): Include the HttpOnly attribute in persistence cookies. The HttpOnly attribute limits the scope
        of a cookie to HTTP requests and helps mitigate the risk of cross-site scripting attacks. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    cookiepassphrase(str): Use this parameter to specify the passphrase used to generate secured persistence cookie value. It
        specifies the passphrase with a maximum of 31 characters.

    usesecuredpersistencecookie(str): Encode persistence cookie values using SHA2 hash. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    useencryptedpersistencecookie(str): Encode persistence cookie values using SHA2 hash. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.update_lbprofile <args>

    '''

    result = {}

    payload = {'lbprofile': {}}

    if lbprofilename:
        payload['lbprofile']['lbprofilename'] = lbprofilename

    if dbslb:
        payload['lbprofile']['dbslb'] = dbslb

    if processlocal:
        payload['lbprofile']['processlocal'] = processlocal

    if httponlycookieflag:
        payload['lbprofile']['httponlycookieflag'] = httponlycookieflag

    if cookiepassphrase:
        payload['lbprofile']['cookiepassphrase'] = cookiepassphrase

    if usesecuredpersistencecookie:
        payload['lbprofile']['usesecuredpersistencecookie'] = usesecuredpersistencecookie

    if useencryptedpersistencecookie:
        payload['lbprofile']['useencryptedpersistencecookie'] = useencryptedpersistencecookie

    execution = __proxy__['citrixns.put']('config/lbprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_lbsipparameters(rnatsrcport=None, rnatdstport=None, retrydur=None, addrportvip=None, sip503ratethreshold=None,
                           rnatsecuresrcport=None, rnatsecuredstport=None, save=False):
    '''
    Update the running configuration for the lbsipparameters config key.

    rnatsrcport(int): Port number with which to match the source port in server-initiated SIP traffic. The rport parameter is
        added, without a value, to SIP packets that have a matching source port number, and CALL-ID based persistence is
        implemented for the responses received by the virtual server. Default value: 0

    rnatdstport(int): Port number with which to match the destination port in server-initiated SIP traffic. The rport
        parameter is added, without a value, to SIP packets that have a matching destination port number, and CALL-ID
        based persistence is implemented for the responses received by the virtual server. Default value: 0

    retrydur(int): Time, in seconds, for which a client must wait before initiating a connection after receiving a 503
        Service Unavailable response from the SIP server. The time value is sent in the "Retry-After" header in the 503
        response. Default value: 120 Minimum value = 1

    addrportvip(str): Add the rport parameter to the VIA headers of SIP requests that virtual servers receive from clients or
        servers. Default value: ENABLED Possible values = ENABLED, DISABLED

    sip503ratethreshold(int): Maximum number of 503 Service Unavailable responses to generate, once every 10 milliseconds,
        when a SIP virtual server becomes unavailable. Default value: 100

    rnatsecuresrcport(int): Port number with which to match the source port in server-initiated SIP over SSL traffic. The
        rport parameter is added, without a value, to SIP packets that have a matching source port number, and CALL-ID
        based persistence is implemented for the responses received by the virtual server. Default value: 0 Range 1 -
        65535 * in CLI is represented as 65535 in NITRO API

    rnatsecuredstport(int): Port number with which to match the destination port in server-initiated SIP over SSL traffic.
        The rport parameter is added, without a value, to SIP packets that have a matching destination port number, and
        CALL-ID based persistence is implemented for the responses received by the virtual server. Default value: 0 Range
        1 - 65535 * in CLI is represented as 65535 in NITRO API

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.update_lbsipparameters <args>

    '''

    result = {}

    payload = {'lbsipparameters': {}}

    if rnatsrcport:
        payload['lbsipparameters']['rnatsrcport'] = rnatsrcport

    if rnatdstport:
        payload['lbsipparameters']['rnatdstport'] = rnatdstport

    if retrydur:
        payload['lbsipparameters']['retrydur'] = retrydur

    if addrportvip:
        payload['lbsipparameters']['addrportvip'] = addrportvip

    if sip503ratethreshold:
        payload['lbsipparameters']['sip503ratethreshold'] = sip503ratethreshold

    if rnatsecuresrcport:
        payload['lbsipparameters']['rnatsecuresrcport'] = rnatsecuresrcport

    if rnatsecuredstport:
        payload['lbsipparameters']['rnatsecuredstport'] = rnatsecuredstport

    execution = __proxy__['citrixns.put']('config/lbsipparameters', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_lbvserver(name=None, servicetype=None, ipv46=None, ippattern=None, ipmask=None, port=None, range=None,
                     persistencetype=None, timeout=None, persistencebackup=None, backuppersistencetimeout=None,
                     lbmethod=None, hashlength=None, netmask=None, v6netmasklen=None, backuplbmethod=None,
                     cookiename=None, rule=None, listenpolicy=None, listenpriority=None, resrule=None, persistmask=None,
                     v6persistmasklen=None, pq=None, sc=None, rtspnat=None, m=None, tosid=None, datalength=None,
                     dataoffset=None, sessionless=None, trofspersistence=None, state=None, connfailover=None,
                     redirurl=None, cacheable=None, clttimeout=None, somethod=None, sopersistence=None,
                     sopersistencetimeout=None, healththreshold=None, sothreshold=None, sobackupaction=None,
                     redirectportrewrite=None, downstateflush=None, backupvserver=None, disableprimaryondown=None,
                     insertvserveripport=None, vipheader=None, authenticationhost=None, authentication=None,
                     authn401=None, authnvsname=None, push=None, pushvserver=None, pushlabel=None, pushmulticlients=None,
                     tcpprofilename=None, httpprofilename=None, dbprofilename=None, comment=None, l2conn=None,
                     oracleserverversion=None, mssqlserverversion=None, mysqlprotocolversion=None,
                     mysqlserverversion=None, mysqlcharacterset=None, mysqlservercapabilities=None, appflowlog=None,
                     netprofile=None, icmpvsrresponse=None, rhistate=None, newservicerequest=None,
                     newservicerequestunit=None, newservicerequestincrementinterval=None, minautoscalemembers=None,
                     maxautoscalemembers=None, persistavpno=None, skippersistency=None, td=None, authnprofile=None,
                     macmoderetainvlan=None, dbslb=None, dns64=None, bypassaaaa=None, recursionavailable=None,
                     processlocal=None, dnsprofilename=None, lbprofilename=None, redirectfromport=None,
                     httpsredirecturl=None, retainconnectionsoncluster=None, weight=None, servicename=None,
                     redirurlflags=None, newname=None, save=False):
    '''
    Update the running configuration for the lbvserver config key.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign (=),
        and hyphen (-) characters. Can be changed after the virtual server is created.  CLI Users: If the name includes
        one or more spaces, enclose the name in double or single quotation marks (for example, "my vserver" or my
        vserver). . Minimum length = 1

    servicetype(str): Protocol used by the service (also called the service type). Possible values = HTTP, FTP, TCP, UDP,
        SSL, SSL_BRIDGE, SSL_TCP, DTLS, NNTP, DNS, DHCPRA, ANY, SIP_UDP, SIP_TCP, SIP_SSL, DNS_TCP, RTSP, PUSH, SSL_PUSH,
        RADIUS, RDP, MYSQL, MSSQL, DIAMETER, SSL_DIAMETER, TFTP, ORACLE, SMPP, SYSLOGTCP, SYSLOGUDP, FIX, SSL_FIX,
        USER_TCP, USER_SSL_TCP

    ipv46(str): IPv4 or IPv6 address to assign to the virtual server.

    ippattern(str): IP address pattern, in dotted decimal notation, for identifying packets to be accepted by the virtual
        server. The IP Mask parameter specifies which part of the destination IP address is matched against the pattern.
        Mutually exclusive with the IP Address parameter.  For example, if the IP pattern assigned to the virtual server
        is 198.51.100.0 and the IP mask is 255.255.240.0 (a forward mask), the first 20 bits in the destination IP
        addresses are matched with the first 20 bits in the pattern. The virtual server accepts requests with IP
        addresses that range from 198.51.96.1 to 198.51.111.254. You can also use a pattern such as 0.0.2.2 and a mask
        such as 0.0.255.255 (a reverse mask). If a destination IP address matches more than one IP pattern, the pattern
        with the longest match is selected, and the associated virtual server processes the request. For example, if
        virtual servers vs1 and vs2 have the same IP pattern, 0.0.100.128, but different IP masks of 0.0.255.255 and
        0.0.224.255, a destination IP address of 198.51.100.128 has the longest match with the IP pattern of vs1. If a
        destination IP address matches two or more virtual servers to the same extent, the request is processed by the
        virtual server whose port number matches the port number in the request.

    ipmask(str): IP mask, in dotted decimal notation, for the IP Pattern parameter. Can have leading or trailing non-zero
        octets (for example, 255.255.240.0 or 0.0.255.255). Accordingly, the mask specifies whether the first n bits or
        the last n bits of the destination IP address in a client request are to be matched with the corresponding bits
        in the IP pattern. The former is called a forward mask. The latter is called a reverse mask.

    port(int): Port number for the virtual server. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    range(int): Number of IP addresses that the appliance must generate and assign to the virtual server. The virtual server
        then functions as a network virtual server, accepting traffic on any of the generated IP addresses. The IP
        addresses are generated automatically, as follows:  * For a range of n, the last octet of the address specified
        by the IP Address parameter increments n-1 times.  * If the last octet exceeds 255, it rolls over to 0 and the
        third octet increments by 1. Note: The Range parameter assigns multiple IP addresses to one virtual server. To
        generate an array of virtual servers, each of which owns only one IP address, use brackets in the IP Address and
        Name parameters to specify the range. For example: add lb vserver my_vserver[1-3] HTTP 192.0.2.[1-3] 80. Default
        value: 1 Minimum value = 1 Maximum value = 254

    persistencetype(str): Type of persistence for the virtual server. Available settings function as follows: * SOURCEIP -
        Connections from the same client IP address belong to the same persistence session. * COOKIEINSERT - Connections
        that have the same HTTP Cookie, inserted by a Set-Cookie directive from a server, belong to the same persistence
        session.  * SSLSESSION - Connections that have the same SSL Session ID belong to the same persistence session. *
        CUSTOMSERVERID - Connections with the same server ID form part of the same session. For this persistence type,
        set the Server ID (CustomServerID) parameter for each service and configure the Rule parameter to identify the
        server ID in a request. * RULE - All connections that match a user defined rule belong to the same persistence
        session.  * URLPASSIVE - Requests that have the same server ID in the URL query belong to the same persistence
        session. The server ID is the hexadecimal representation of the IP address and port of the service to which the
        request must be forwarded. This persistence type requires a rule to identify the server ID in the request.  *
        DESTIP - Connections to the same destination IP address belong to the same persistence session. * SRCIPDESTIP -
        Connections that have the same source IP address and destination IP address belong to the same persistence
        session. * CALLID - Connections that have the same CALL-ID SIP header belong to the same persistence session. *
        RTSPSID - Connections that have the same RTSP Session ID belong to the same persistence session. * FIXSESSION -
        Connections that have the same SenderCompID and TargetCompID values belong to the same persistence session. *
        USERSESSION - Persistence session is created based on the persistence parameter value provided from an extension.
        Possible values = SOURCEIP, COOKIEINSERT, SSLSESSION, RULE, URLPASSIVE, CUSTOMSERVERID, DESTIP, SRCIPDESTIP,
        CALLID, RTSPSID, DIAMETER, FIXSESSION, USERSESSION, NONE

    timeout(int): Time period for which a persistence session is in effect. Default value: 2 Minimum value = 0 Maximum value
        = 1440

    persistencebackup(str): Backup persistence type for the virtual server. Becomes operational if the primary persistence
        mechanism fails. Possible values = SOURCEIP, NONE

    backuppersistencetimeout(int): Time period for which backup persistence is in effect. Default value: 2 Minimum value = 2
        Maximum value = 1440

    lbmethod(str): Load balancing method. The available settings function as follows: * ROUNDROBIN - Distribute requests in
        rotation, regardless of the load. Weights can be assigned to services to enforce weighted round robin
        distribution. * LEASTCONNECTION (default) - Select the service with the fewest connections.  * LEASTRESPONSETIME
        - Select the service with the lowest average response time.  * LEASTBANDWIDTH - Select the service currently
        handling the least traffic. * LEASTPACKETS - Select the service currently serving the lowest number of packets
        per second. * CUSTOMLOAD - Base service selection on the SNMP metrics obtained by custom load monitors. * LRTM -
        Select the service with the lowest response time. Response times are learned through monitoring probes. This
        method also takes the number of active connections into account. Also available are a number of hashing methods,
        in which the appliance extracts a predetermined portion of the request, creates a hash of the portion, and then
        checks whether any previous requests had the same hash value. If it finds a match, it forwards the request to the
        service that served those previous requests. Following are the hashing methods:  * URLHASH - Create a hash of the
        request URL (or part of the URL). * DOMAINHASH - Create a hash of the domain name in the request (or part of the
        domain name). The domain name is taken from either the URL or the Host header. If the domain name appears in both
        locations, the URL is preferred. If the request does not contain a domain name, the load balancing method
        defaults to LEASTCONNECTION. * DESTINATIONIPHASH - Create a hash of the destination IP address in the IP header.
        * SOURCEIPHASH - Create a hash of the source IP address in the IP header.  * TOKEN - Extract a token from the
        request, create a hash of the token, and then select the service to which any previous requests with the same
        token hash value were sent.  * SRCIPDESTIPHASH - Create a hash of the string obtained by concatenating the source
        IP address and destination IP address in the IP header.  * SRCIPSRCPORTHASH - Create a hash of the source IP
        address and source port in the IP header.  * CALLIDHASH - Create a hash of the SIP Call-ID header. * USER_TOKEN -
        Same as TOKEN LB method but token needs to be provided from an extension. Default value: LEASTCONNECTION Possible
        values = ROUNDROBIN, LEASTCONNECTION, LEASTRESPONSETIME, URLHASH, DOMAINHASH, DESTINATIONIPHASH, SOURCEIPHASH,
        SRCIPDESTIPHASH, LEASTBANDWIDTH, LEASTPACKETS, TOKEN, SRCIPSRCPORTHASH, LRTM, CALLIDHASH, CUSTOMLOAD,
        LEASTREQUEST, AUDITLOGHASH, STATICPROXIMITY, USER_TOKEN

    hashlength(int): Number of bytes to consider for the hash value used in the URLHASH and DOMAINHASH load balancing
        methods. Default value: 80 Minimum value = 1 Maximum value = 4096

    netmask(str): IPv4 subnet mask to apply to the destination IP address or source IP address when the load balancing method
        is DESTINATIONIPHASH or SOURCEIPHASH. Minimum length = 1

    v6netmasklen(int): Number of bits to consider in an IPv6 destination or source IP address, for creating the hash that is
        required by the DESTINATIONIPHASH and SOURCEIPHASH load balancing methods. Default value: 128 Minimum value = 1
        Maximum value = 128

    backuplbmethod(str): Backup load balancing method. Becomes operational if the primary load balancing me thod fails or
        cannot be used.  Valid only if the primary method is based on static proximity. Default value: ROUNDROBIN
        Possible values = ROUNDROBIN, LEASTCONNECTION, LEASTRESPONSETIME, SOURCEIPHASH, LEASTBANDWIDTH, LEASTPACKETS,
        CUSTOMLOAD

    cookiename(str): Use this parameter to specify the cookie name for COOKIE peristence type. It specifies the name of
        cookie with a maximum of 32 characters. If not specified, cookie name is internally generated.

    rule(str): Expression, or name of a named expression, against which traffic is evaluated. Written in the classic or
        default syntax. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can
        be split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;" The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks. Default value: "none"

    listenpolicy(str): Default syntax expression identifying traffic accepted by the virtual server. Can be either an
        expression (for example, CLIENT.IP.DST.IN_SUBNET(192.0.2.0/24) or the name of a named expression. In the above
        example, the virtual server accepts all requests whose destination IP address is in the 192.0.2.0/24 subnet.
        Default value: "NONE"

    listenpriority(int): Integer specifying the priority of the listen policy. A higher number specifies a lower priority. If
        a request matches the listen policies of more than one virtual server the virtual server whose listen policy has
        the highest priority (the lowest priority number) accepts the request. Default value: 101 Minimum value = 0
        Maximum value = 101

    resrule(str): Default syntax expression specifying which part of a servers response to use for creating rule based
        persistence sessions (persistence type RULE). Can be either an expression or the name of a named expression.
        Example: HTTP.RES.HEADER("setcookie").VALUE(0).TYPECAST_NVLIST_T(=,;).VALUE("server1"). Default value: "none"

    persistmask(str): Persistence mask for IP based persistence types, for IPv4 virtual servers. Minimum length = 1

    v6persistmasklen(int): Persistence mask for IP based persistence types, for IPv6 virtual servers. Default value: 128
        Minimum value = 1 Maximum value = 128

    pq(str): Use priority queuing on the virtual server. based persistence types, for IPv6 virtual servers. Default value:
        OFF Possible values = ON, OFF

    sc(str): Use SureConnect on the virtual server. Default value: OFF Possible values = ON, OFF

    rtspnat(str): Use network address translation (NAT) for RTSP data connections. Default value: OFF Possible values = ON,
        OFF

    m(str): Redirection mode for load balancing. Available settings function as follows: * IP - Before forwarding a request
        to a server, change the destination IP address to the servers IP address.  * MAC - Before forwarding a request to
        a server, change the destination MAC address to the servers MAC address. The destination IP address is not
        changed. MAC-based redirection mode is used mostly in firewall load balancing deployments.  * IPTUNNEL - Perform
        IP-in-IP encapsulation for client IP packets. In the outer IP headers, set the destination IP address to the IP
        address of the server and the source IP address to the subnet IP (SNIP). The client IP packets are not modified.
        Applicable to both IPv4 and IPv6 packets.  * TOS - Encode the virtual servers TOS ID in the TOS field of the IP
        header.  You can use either the IPTUNNEL or the TOS option to implement Direct Server Return (DSR). Default
        value: IP Possible values = IP, MAC, IPTUNNEL, TOS

    tosid(int): TOS ID of the virtual server. Applicable only when the load balancing redirection mode is set to TOS. Minimum
        value = 1 Maximum value = 63

    datalength(int): Length of the token to be extracted from the data segment of an incoming packet, for use in the token
        method of load balancing. The length of the token, specified in bytes, must not be greater than 24 KB. Applicable
        to virtual servers of type TCP. Minimum value = 1 Maximum value = 100

    dataoffset(int): Offset to be considered when extracting a token from the TCP payload. Applicable to virtual servers, of
        type TCP, using the token method of load balancing. Must be within the first 24 KB of the TCP payload. Minimum
        value = 0 Maximum value = 25400

    sessionless(str): Perform load balancing on a per-packet basis, without establishing sessions. Recommended for load
        balancing of intrusion detection system (IDS) servers and scenarios involving direct server return (DSR), where
        session information is unnecessary. Default value: DISABLED Possible values = ENABLED, DISABLED

    trofspersistence(str): When value is ENABLED, Trofs persistence is honored. When value is DISABLED, Trofs persistence is
        not honored. Default value: ENABLED Possible values = ENABLED, DISABLED

    state(str): State of the load balancing virtual server. Default value: ENABLED Possible values = ENABLED, DISABLED

    connfailover(str): Mode in which the connection failover feature must operate for the virtual server. After a failover,
        established TCP connections and UDP packet flows are kept active and resumed on the secondary appliance. Clients
        remain connected to the same servers. Available settings function as follows: * STATEFUL - The primary appliance
        shares state information with the secondary appliance, in real time, resulting in some runtime processing
        overhead.  * STATELESS - State information is not shared, and the new primary appliance tries to re-create the
        packet flow on the basis of the information contained in the packets it receives.  * DISABLED - Connection
        failover does not occur. Default value: DISABLED Possible values = DISABLED, STATEFUL, STATELESS

    redirurl(str): URL to which to redirect traffic if the virtual server becomes unavailable.  WARNING! Make sure that the
        domain in the URL does not match the domain specified for a content switching policy. If it does, requests are
        continuously redirected to the unavailable virtual server. Minimum length = 1

    cacheable(str): Route cacheable requests to a cache redirection virtual server. The load balancing virtual server can
        forward requests only to a transparent cache redirection virtual server that has an IP address and port
        combination of *:80, so such a cache redirection virtual server must be configured on the appliance. Default
        value: NO Possible values = YES, NO

    clttimeout(int): Idle time, in seconds, after which a client connection is terminated. Minimum value = 0 Maximum value =
        31536000

    somethod(str): Type of threshold that, when exceeded, triggers spillover. Available settings function as follows: *
        CONNECTION - Spillover occurs when the number of client connections exceeds the threshold. * DYNAMICCONNECTION -
        Spillover occurs when the number of client connections at the virtual server exceeds the sum of the maximum
        client (Max Clients) settings for bound services. Do not specify a spillover threshold for this setting, because
        the threshold is implied by the Max Clients settings of bound services. * BANDWIDTH - Spillover occurs when the
        bandwidth consumed by the virtual servers incoming and outgoing traffic exceeds the threshold.  * HEALTH -
        Spillover occurs when the percentage of weights of the services that are UP drops below the threshold. For
        example, if services svc1, svc2, and svc3 are bound to a virtual server, with weights 1, 2, and 3, and the
        spillover threshold is 50%, spillover occurs if svc1 and svc3 or svc2 and svc3 transition to DOWN.  * NONE -
        Spillover does not occur. Possible values = CONNECTION, DYNAMICCONNECTION, BANDWIDTH, HEALTH, NONE

    sopersistence(str): If spillover occurs, maintain source IP address based persistence for both primary and backup virtual
        servers. Default value: DISABLED Possible values = ENABLED, DISABLED

    sopersistencetimeout(int): Timeout for spillover persistence, in minutes. Default value: 2 Minimum value = 2 Maximum
        value = 1440

    healththreshold(int): Threshold in percent of active services below which vserver state is made down. If this threshold
        is 0, vserver state will be up even if one bound service is up. Default value: 0 Minimum value = 0 Maximum value
        = 100

    sothreshold(int): Threshold at which spillover occurs. Specify an integer for the CONNECTION spillover method, a
        bandwidth value in kilobits per second for the BANDWIDTH method (do not enter the units), or a percentage for the
        HEALTH method (do not enter the percentage symbol). Minimum value = 1 Maximum value = 4294967287

    sobackupaction(str): Action to be performed if spillover is to take effect, but no backup chain to spillover is usable or
        exists. Possible values = DROP, ACCEPT, REDIRECT

    redirectportrewrite(str): Rewrite the port and change the protocol to ensure successful HTTP redirects from services.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    downstateflush(str): Flush all active transactions associated with a virtual server whose state transitions from UP to
        DOWN. Do not enable this option for applications that must complete their transactions. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    backupvserver(str): Name of the backup virtual server to which to forward requests if the primary virtual server goes
        DOWN or reaches its spillover threshold. Minimum length = 1

    disableprimaryondown(str): If the primary virtual server goes down, do not allow it to return to primary status until
        manually enabled. Default value: DISABLED Possible values = ENABLED, DISABLED

    insertvserveripport(str): Insert an HTTP header, whose value is the IP address and port number of the virtual server,
        before forwarding a request to the server. The format of the header is ;lt;vipHeader;gt;: ;lt;virtual server IP
        address;gt;_;lt;port number ;gt;, where vipHeader is the name that you specify for the header. If the virtual
        server has an IPv6 address, the address in the header is enclosed in brackets ([ and ]) to separate it from the
        port number. If you have mapped an IPv4 address to a virtual servers IPv6 address, the value of this parameter
        determines which IP address is inserted in the header, as follows: * VIPADDR - Insert the IP address of the
        virtual server in the HTTP header regardless of whether the virtual server has an IPv4 address or an IPv6
        address. A mapped IPv4 address, if configured, is ignored. * V6TOV4MAPPING - Insert the IPv4 address that is
        mapped to the virtual servers IPv6 address. If a mapped IPv4 address is not configured, insert the IPv6 address.
        * OFF - Disable header insertion. Possible values = OFF, VIPADDR, V6TOV4MAPPING

    vipheader(str): Name for the inserted header. The default name is vip-header. Minimum length = 1

    authenticationhost(str): Fully qualified domain name (FQDN) of the authentication virtual server to which the user must
        be redirected for authentication. Make sure that the Authentication parameter is set to ENABLED. Minimum length =
        3 Maximum length = 252

    authentication(str): Enable or disable user authentication. Default value: OFF Possible values = ON, OFF

    authn401(str): Enable or disable user authentication with HTTP 401 responses. Default value: OFF Possible values = ON,
        OFF

    authnvsname(str): Name of an authentication virtual server with which to authenticate users. Minimum length = 1 Maximum
        length = 252

    push(str): Process traffic with the push virtual server that is bound to this load balancing virtual server. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    pushvserver(str): Name of the load balancing virtual server, of type PUSH or SSL_PUSH, to which the server pushes updates
        received on the load balancing virtual server that you are configuring. Minimum length = 1

    pushlabel(str): Expression for extracting a label from the servers response. Can be either an expression or the name of a
        named expression. Default value: "none"

    pushmulticlients(str): Allow multiple Web 2.0 connections from the same client to connect to the virtual server and
        expect updates. Default value: NO Possible values = YES, NO

    tcpprofilename(str): Name of the TCP profile whose settings are to be applied to the virtual server. Minimum length = 1
        Maximum length = 127

    httpprofilename(str): Name of the HTTP profile whose settings are to be applied to the virtual server. Minimum length = 1
        Maximum length = 127

    dbprofilename(str): Name of the DB profile whose settings are to be applied to the virtual server. Minimum length = 1
        Maximum length = 127

    comment(str): Any comments that you might want to associate with the virtual server.

    l2conn(str): Use Layer 2 parameters (channel number, MAC address, and VLAN ID) in addition to the 4-tuple (;lt;source
        IP;gt;:;lt;source port;gt;::;lt;destination IP;gt;:;lt;destination port;gt;) that is used to identify a
        connection. Allows multiple TCP and non-TCP connections with the same 4-tuple to co-exist on the NetScaler
        appliance. Possible values = ON, OFF

    oracleserverversion(str): Oracle server version. Default value: 10G Possible values = 10G, 11G

    mssqlserverversion(str): For a load balancing virtual server of type MSSQL, the Microsoft SQL Server version. Set this
        parameter if you expect some clients to run a version different from the version of the database. This setting
        provides compatibility between the client-side and server-side connections by ensuring that all communication
        conforms to the servers version. Default value: 2008R2 Possible values = 70, 2000, 2000SP1, 2005, 2008, 2008R2,
        2012, 2014

    mysqlprotocolversion(int): MySQL protocol version that the virtual server advertises to clients.

    mysqlserverversion(str): MySQL server version string that the virtual server advertises to clients. Minimum length = 1
        Maximum length = 31

    mysqlcharacterset(int): Character set that the virtual server advertises to clients.

    mysqlservercapabilities(int): Server capabilities that the virtual server advertises to clients.

    appflowlog(str): Apply AppFlow logging to the virtual server. Default value: ENABLED Possible values = ENABLED, DISABLED

    netprofile(str): Name of the network profile to associate with the virtual server. If you set this parameter, the virtual
        server uses only the IP addresses in the network profile as source IP addresses when initiating connections with
        servers. Minimum length = 1 Maximum length = 127

    icmpvsrresponse(str): How the NetScaler appliance responds to ping requests received for an IP address that is common to
        one or more virtual servers. Available settings function as follows: * If set to PASSIVE on all the virtual
        servers that share the IP address, the appliance always responds to the ping requests. * If set to ACTIVE on all
        the virtual servers that share the IP address, the appliance responds to the ping requests if at least one of the
        virtual servers is UP. Otherwise, the appliance does not respond. * If set to ACTIVE on some virtual servers and
        PASSIVE on the others, the appliance responds if at least one virtual server with the ACTIVE setting is UP.
        Otherwise, the appliance does not respond. Note: This parameter is available at the virtual server level. A
        similar parameter, ICMP Response, is available at the IP address level, for IPv4 addresses of type VIP. To set
        that parameter, use the add ip command in the CLI or the Create IP dialog box in the GUI. Default value: PASSIVE
        Possible values = PASSIVE, ACTIVE

    rhistate(str): Route Health Injection (RHI) functionality of the NetSaler appliance for advertising the route of the VIP
        address associated with the virtual server. When Vserver RHI Level (RHI) parameter is set to VSVR_CNTRLD, the
        following are different RHI behaviors for the VIP address on the basis of RHIstate (RHI STATE) settings on the
        virtual servers associated with the VIP address: * If you set RHI STATE to PASSIVE on all virtual servers, the
        NetScaler ADC always advertises the route for the VIP address. * If you set RHI STATE to ACTIVE on all virtual
        servers, the NetScaler ADC advertises the route for the VIP address if at least one of the associated virtual
        servers is in UP state. * If you set RHI STATE to ACTIVE on some and PASSIVE on others, the NetScaler ADC
        advertises the route for the VIP address if at least one of the associated virtual servers, whose RHI STATE set
        to ACTIVE, is in UP state. Default value: PASSIVE Possible values = PASSIVE, ACTIVE

    newservicerequest(int): Number of requests, or percentage of the load on existing services, by which to increase the load
        on a new service at each interval in slow-start mode. A non-zero value indicates that slow-start is applicable. A
        zero value indicates that the global RR startup parameter is applied. Changing the value to zero will cause
        services currently in slow start to take the full traffic as determined by the LB method. Subsequently, any new
        services added will use the global RR factor. Default value: 0

    newservicerequestunit(str): Units in which to increment load at each interval in slow-start mode. Default value:
        PER_SECOND Possible values = PER_SECOND, PERCENT

    newservicerequestincrementinterval(int): Interval, in seconds, between successive increments in the load on a new service
        or a service whose state has just changed from DOWN to UP. A value of 0 (zero) specifies manual slow start.
        Default value: 0 Minimum value = 0 Maximum value = 3600

    minautoscalemembers(int): Minimum number of members expected to be present when vserver is used in Autoscale. Default
        value: 0 Minimum value = 0 Maximum value = 5000

    maxautoscalemembers(int): Maximum number of members expected to be present when vserver is used in Autoscale. Default
        value: 0 Minimum value = 0 Maximum value = 5000

    persistavpno(list(int)): Persist AVP number for Diameter Persistency.   In case this AVP is not defined in Base RFC 3588
        and it is nested inside a Grouped AVP,   define a sequence of AVP numbers (max 3) in order of parent to child. So
        say persist AVP number X   is nested inside AVP Y which is nested in Z, then define the list as Z Y X. Minimum
        value = 1

    skippersistency(str): This argument decides the behavior incase the service which is selected from an existing
        persistence session has reached threshold. Default value: None Possible values = Bypass, ReLb, None

    td(int): Integer value that uniquely identifies the traffic domain in which you want to configure the entity. If you do
        not specify an ID, the entity becomes part of the default traffic domain, which has an ID of 0. Minimum value = 0
        Maximum value = 4094

    authnprofile(str): Name of the authentication profile to be used when authentication is turned on.

    macmoderetainvlan(str): This option is used to retain vlan information of incoming packet when macmode is enabled.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    dbslb(str): Enable database specific load balancing for MySQL and MSSQL service types. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    dns64(str): This argument is for enabling/disabling the dns64 on lbvserver. Possible values = ENABLED, DISABLED

    bypassaaaa(str): If this option is enabled while resolving DNS64 query AAAA queries are not sent to back end dns server.
        Default value: NO Possible values = YES, NO

    recursionavailable(str): When set to YES, this option causes the DNS replies from this vserver to have the RA bit turned
        on. Typically one would set this option to YES, when the vserver is load balancing a set of DNS servers
        thatsupport recursive queries. Default value: NO Possible values = YES, NO

    processlocal(str): By turning on this option packets destined to a vserver in a cluster will not under go any steering.
        Turn this option for single packet request response mode or when the upstream device is performing a proper RSS
        for connection based distribution. Default value: DISABLED Possible values = ENABLED, DISABLED

    dnsprofilename(str): Name of the DNS profile to be associated with the VServer. DNS profile properties will be applied to
        the transactions processed by a VServer. This parameter is valid only for DNS and DNS-TCP VServers. Minimum
        length = 1 Maximum length = 127

    lbprofilename(str): Name of the LB profile which is associated to the vserver.

    redirectfromport(int): Port number for the virtual server, from which we absorb the traffic for http redirect. Minimum
        value = 1 Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    httpsredirecturl(str): URL to which to redirect traffic if the traffic is recieved from redirect port.

    retainconnectionsoncluster(str): This option enables you to retain existing connections on a node joining a Cluster
        system or when a node is being configured for passive timeout. By default, this option is disabled. Default
        value: NO Possible values = YES, NO

    weight(int): Weight to assign to the specified service. Minimum value = 1 Maximum value = 100

    servicename(str): Service to bind to the virtual server. Minimum length = 1

    redirurlflags(bool): The redirect URL to be unset.

    newname(str): New name for the virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.update_lbvserver <args>

    '''

    result = {}

    payload = {'lbvserver': {}}

    if name:
        payload['lbvserver']['name'] = name

    if servicetype:
        payload['lbvserver']['servicetype'] = servicetype

    if ipv46:
        payload['lbvserver']['ipv46'] = ipv46

    if ippattern:
        payload['lbvserver']['ippattern'] = ippattern

    if ipmask:
        payload['lbvserver']['ipmask'] = ipmask

    if port:
        payload['lbvserver']['port'] = port

    if range:
        payload['lbvserver']['range'] = range

    if persistencetype:
        payload['lbvserver']['persistencetype'] = persistencetype

    if timeout:
        payload['lbvserver']['timeout'] = timeout

    if persistencebackup:
        payload['lbvserver']['persistencebackup'] = persistencebackup

    if backuppersistencetimeout:
        payload['lbvserver']['backuppersistencetimeout'] = backuppersistencetimeout

    if lbmethod:
        payload['lbvserver']['lbmethod'] = lbmethod

    if hashlength:
        payload['lbvserver']['hashlength'] = hashlength

    if netmask:
        payload['lbvserver']['netmask'] = netmask

    if v6netmasklen:
        payload['lbvserver']['v6netmasklen'] = v6netmasklen

    if backuplbmethod:
        payload['lbvserver']['backuplbmethod'] = backuplbmethod

    if cookiename:
        payload['lbvserver']['cookiename'] = cookiename

    if rule:
        payload['lbvserver']['rule'] = rule

    if listenpolicy:
        payload['lbvserver']['listenpolicy'] = listenpolicy

    if listenpriority:
        payload['lbvserver']['listenpriority'] = listenpriority

    if resrule:
        payload['lbvserver']['resrule'] = resrule

    if persistmask:
        payload['lbvserver']['persistmask'] = persistmask

    if v6persistmasklen:
        payload['lbvserver']['v6persistmasklen'] = v6persistmasklen

    if pq:
        payload['lbvserver']['pq'] = pq

    if sc:
        payload['lbvserver']['sc'] = sc

    if rtspnat:
        payload['lbvserver']['rtspnat'] = rtspnat

    if m:
        payload['lbvserver']['m'] = m

    if tosid:
        payload['lbvserver']['tosid'] = tosid

    if datalength:
        payload['lbvserver']['datalength'] = datalength

    if dataoffset:
        payload['lbvserver']['dataoffset'] = dataoffset

    if sessionless:
        payload['lbvserver']['sessionless'] = sessionless

    if trofspersistence:
        payload['lbvserver']['trofspersistence'] = trofspersistence

    if state:
        payload['lbvserver']['state'] = state

    if connfailover:
        payload['lbvserver']['connfailover'] = connfailover

    if redirurl:
        payload['lbvserver']['redirurl'] = redirurl

    if cacheable:
        payload['lbvserver']['cacheable'] = cacheable

    if clttimeout:
        payload['lbvserver']['clttimeout'] = clttimeout

    if somethod:
        payload['lbvserver']['somethod'] = somethod

    if sopersistence:
        payload['lbvserver']['sopersistence'] = sopersistence

    if sopersistencetimeout:
        payload['lbvserver']['sopersistencetimeout'] = sopersistencetimeout

    if healththreshold:
        payload['lbvserver']['healththreshold'] = healththreshold

    if sothreshold:
        payload['lbvserver']['sothreshold'] = sothreshold

    if sobackupaction:
        payload['lbvserver']['sobackupaction'] = sobackupaction

    if redirectportrewrite:
        payload['lbvserver']['redirectportrewrite'] = redirectportrewrite

    if downstateflush:
        payload['lbvserver']['downstateflush'] = downstateflush

    if backupvserver:
        payload['lbvserver']['backupvserver'] = backupvserver

    if disableprimaryondown:
        payload['lbvserver']['disableprimaryondown'] = disableprimaryondown

    if insertvserveripport:
        payload['lbvserver']['insertvserveripport'] = insertvserveripport

    if vipheader:
        payload['lbvserver']['vipheader'] = vipheader

    if authenticationhost:
        payload['lbvserver']['authenticationhost'] = authenticationhost

    if authentication:
        payload['lbvserver']['authentication'] = authentication

    if authn401:
        payload['lbvserver']['authn401'] = authn401

    if authnvsname:
        payload['lbvserver']['authnvsname'] = authnvsname

    if push:
        payload['lbvserver']['push'] = push

    if pushvserver:
        payload['lbvserver']['pushvserver'] = pushvserver

    if pushlabel:
        payload['lbvserver']['pushlabel'] = pushlabel

    if pushmulticlients:
        payload['lbvserver']['pushmulticlients'] = pushmulticlients

    if tcpprofilename:
        payload['lbvserver']['tcpprofilename'] = tcpprofilename

    if httpprofilename:
        payload['lbvserver']['httpprofilename'] = httpprofilename

    if dbprofilename:
        payload['lbvserver']['dbprofilename'] = dbprofilename

    if comment:
        payload['lbvserver']['comment'] = comment

    if l2conn:
        payload['lbvserver']['l2conn'] = l2conn

    if oracleserverversion:
        payload['lbvserver']['oracleserverversion'] = oracleserverversion

    if mssqlserverversion:
        payload['lbvserver']['mssqlserverversion'] = mssqlserverversion

    if mysqlprotocolversion:
        payload['lbvserver']['mysqlprotocolversion'] = mysqlprotocolversion

    if mysqlserverversion:
        payload['lbvserver']['mysqlserverversion'] = mysqlserverversion

    if mysqlcharacterset:
        payload['lbvserver']['mysqlcharacterset'] = mysqlcharacterset

    if mysqlservercapabilities:
        payload['lbvserver']['mysqlservercapabilities'] = mysqlservercapabilities

    if appflowlog:
        payload['lbvserver']['appflowlog'] = appflowlog

    if netprofile:
        payload['lbvserver']['netprofile'] = netprofile

    if icmpvsrresponse:
        payload['lbvserver']['icmpvsrresponse'] = icmpvsrresponse

    if rhistate:
        payload['lbvserver']['rhistate'] = rhistate

    if newservicerequest:
        payload['lbvserver']['newservicerequest'] = newservicerequest

    if newservicerequestunit:
        payload['lbvserver']['newservicerequestunit'] = newservicerequestunit

    if newservicerequestincrementinterval:
        payload['lbvserver']['newservicerequestincrementinterval'] = newservicerequestincrementinterval

    if minautoscalemembers:
        payload['lbvserver']['minautoscalemembers'] = minautoscalemembers

    if maxautoscalemembers:
        payload['lbvserver']['maxautoscalemembers'] = maxautoscalemembers

    if persistavpno:
        payload['lbvserver']['persistavpno'] = persistavpno

    if skippersistency:
        payload['lbvserver']['skippersistency'] = skippersistency

    if td:
        payload['lbvserver']['td'] = td

    if authnprofile:
        payload['lbvserver']['authnprofile'] = authnprofile

    if macmoderetainvlan:
        payload['lbvserver']['macmoderetainvlan'] = macmoderetainvlan

    if dbslb:
        payload['lbvserver']['dbslb'] = dbslb

    if dns64:
        payload['lbvserver']['dns64'] = dns64

    if bypassaaaa:
        payload['lbvserver']['bypassaaaa'] = bypassaaaa

    if recursionavailable:
        payload['lbvserver']['recursionavailable'] = recursionavailable

    if processlocal:
        payload['lbvserver']['processlocal'] = processlocal

    if dnsprofilename:
        payload['lbvserver']['dnsprofilename'] = dnsprofilename

    if lbprofilename:
        payload['lbvserver']['lbprofilename'] = lbprofilename

    if redirectfromport:
        payload['lbvserver']['redirectfromport'] = redirectfromport

    if httpsredirecturl:
        payload['lbvserver']['httpsredirecturl'] = httpsredirecturl

    if retainconnectionsoncluster:
        payload['lbvserver']['retainconnectionsoncluster'] = retainconnectionsoncluster

    if weight:
        payload['lbvserver']['weight'] = weight

    if servicename:
        payload['lbvserver']['servicename'] = servicename

    if redirurlflags:
        payload['lbvserver']['redirurlflags'] = redirurlflags

    if newname:
        payload['lbvserver']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/lbvserver', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_lbwlm(wlmname=None, ipaddress=None, port=None, lbuid=None, katimeout=None, save=False):
    '''
    Update the running configuration for the lbwlm config key.

    wlmname(str): The name of the Work Load Manager. Minimum length = 1

    ipaddress(str): The IP address of the WLM.

    port(int): The port of the WLM. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    lbuid(str): The LBUID for the Load Balancer to communicate to the Work Load Manager.

    katimeout(int): The idle time period after which NS would probe the WLM. The value ranges from 1 to 1440 minutes. Default
        value: 2 Minimum value = 0 Maximum value = 1440

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' load_balancing.update_lbwlm <args>

    '''

    result = {}

    payload = {'lbwlm': {}}

    if wlmname:
        payload['lbwlm']['wlmname'] = wlmname

    if ipaddress:
        payload['lbwlm']['ipaddress'] = ipaddress

    if port:
        payload['lbwlm']['port'] = port

    if lbuid:
        payload['lbwlm']['lbuid'] = lbuid

    if katimeout:
        payload['lbwlm']['katimeout'] = katimeout

    execution = __proxy__['citrixns.put']('config/lbwlm', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
