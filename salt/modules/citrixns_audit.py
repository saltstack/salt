# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the audit key.

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

__virtualname__ = 'audit'


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

    return False, 'The audit execution module can only be loaded for citrixns proxy minions.'


def add_auditmessageaction(name=None, loglevel=None, stringbuilderexpr=None, logtonewnslog=None, bypasssafetycheck=None,
                           save=False):
    '''
    Add a new auditmessageaction to the running configuration.

    name(str): Name of the audit message action. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the message action is added.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my message action" or my message action). Minimum length = 1

    loglevel(str): Audit log level, which specifies the severity level of the log message being generated..  The following
        loglevels are valid:  * EMERGENCY - Events that indicate an immediate crisis on the server. * ALERT - Events that
        might require action. * CRITICAL - Events that indicate an imminent server crisis. * ERROR - Events that indicate
        some type of error. * WARNING - Events that require action in the near future. * NOTICE - Events that the
        administrator should know about. * INFORMATIONAL - All but low-level events. * DEBUG - All events, in extreme
        detail. Possible values = EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE, INFORMATIONAL, DEBUG

    stringbuilderexpr(str): Default-syntax expression that defines the format and content of the log message.

    logtonewnslog(str): Send the message to the new nslog. Possible values = YES, NO

    bypasssafetycheck(str): Bypass the safety check and allow unsafe expressions. Default value: NO Possible values = YES,
        NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.add_auditmessageaction <args>

    '''

    result = {}

    payload = {'auditmessageaction': {}}

    if name:
        payload['auditmessageaction']['name'] = name

    if loglevel:
        payload['auditmessageaction']['loglevel'] = loglevel

    if stringbuilderexpr:
        payload['auditmessageaction']['stringbuilderexpr'] = stringbuilderexpr

    if logtonewnslog:
        payload['auditmessageaction']['logtonewnslog'] = logtonewnslog

    if bypasssafetycheck:
        payload['auditmessageaction']['bypasssafetycheck'] = bypasssafetycheck

    execution = __proxy__['citrixns.post']('config/auditmessageaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_auditnslogaction(name=None, serverip=None, serverdomainname=None, domainresolveretry=None, serverport=None,
                         loglevel=None, dateformat=None, logfacility=None, tcp=None, acl=None, timezone=None,
                         userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None, subscriberlog=None,
                         sslinterception=None, domainresolvenow=None, save=False):
    '''
    Add a new auditnslogaction to the running configuration.

    name(str): Name of the nslog action. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the nslog action is added.  The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my nslog action" or my nslog action). Minimum length = 1

    serverip(str): IP address of the nslog server. Minimum length = 1

    serverdomainname(str): Auditserver name as a FQDN. Mutually exclusive with serverIP. Minimum length = 1 Maximum length =
        255

    domainresolveretry(int): Time, in seconds, for which the NetScaler appliance waits before sending another DNS query to
        resolve the host name of the audit server if the last query failed. Default value: 5 Minimum value = 5 Maximum
        value = 20939

    serverport(int): Port on which the nslog server accepts connections. Minimum value = 1

    loglevel(list(str)): Audit log level, which specifies the types of events to log.  Available settings function as
        follows:  * ALL - All events. * EMERGENCY - Events that indicate an immediate crisis on the server. * ALERT -
        Events that might require action. * CRITICAL - Events that indicate an imminent server crisis. * ERROR - Events
        that indicate some type of error. * WARNING - Events that require action in the near future. * NOTICE - Events
        that the administrator should know about. * INFORMATIONAL - All but low-level events. * DEBUG - All events, in
        extreme detail. * NONE - No events. Possible values = ALL, EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE,
        INFORMATIONAL, DEBUG, NONE

    dateformat(str): Format of dates in the logs. Supported formats are:  * MMDDYYYY - U.S. style month/date/year format. *
        DDMMYYYY - European style date/month/year format. * YYYYMMDD - ISO style year/month/date format. Possible values
        = MMDDYYYY, DDMMYYYY, YYYYMMDD

    logfacility(str): Facility value, as defined in RFC 3164, assigned to the log message.  Log facility values are numbers 0
        to 7 (LOCAL0 through LOCAL7). Each number indicates where a specific message originated from, such as the
        NetScaler appliance itself, the VPN, or external. Possible values = LOCAL0, LOCAL1, LOCAL2, LOCAL3, LOCAL4,
        LOCAL5, LOCAL6, LOCAL7

    tcp(str): Log TCP messages. Possible values = NONE, ALL

    acl(str): Log access control list (ACL) messages. Possible values = ENABLED, DISABLED

    timezone(str): Time zone used for date and timestamps in the logs.  Available settings function as follows:  * GMT_TIME.
        Coordinated Universal Time. * LOCAL_TIME. The servers timezone setting. Possible values = GMT_TIME, LOCAL_TIME

    userdefinedauditlog(str): Log user-configurable log messages to nslog. Setting this parameter to NO causes auditing to
        ignore all user-configured message actions. Setting this parameter to YES causes auditing to log user-configured
        message actions that meet the other logging criteria. Possible values = YES, NO

    appflowexport(str): Export log messages to AppFlow collectors. Appflow collectors are entities to which log messages can
        be sent so that some action can be performed on them. Possible values = ENABLED, DISABLED

    lsn(str): Log the LSN messages. Possible values = ENABLED, DISABLED

    alg(str): Log the ALG messages. Possible values = ENABLED, DISABLED

    subscriberlog(str): Log subscriber session event information. Possible values = ENABLED, DISABLED

    sslinterception(str): Log SSL Interception event information. Possible values = ENABLED, DISABLED

    domainresolvenow(bool): Immediately send a DNS query to resolve the servers domain name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.add_auditnslogaction <args>

    '''

    result = {}

    payload = {'auditnslogaction': {}}

    if name:
        payload['auditnslogaction']['name'] = name

    if serverip:
        payload['auditnslogaction']['serverip'] = serverip

    if serverdomainname:
        payload['auditnslogaction']['serverdomainname'] = serverdomainname

    if domainresolveretry:
        payload['auditnslogaction']['domainresolveretry'] = domainresolveretry

    if serverport:
        payload['auditnslogaction']['serverport'] = serverport

    if loglevel:
        payload['auditnslogaction']['loglevel'] = loglevel

    if dateformat:
        payload['auditnslogaction']['dateformat'] = dateformat

    if logfacility:
        payload['auditnslogaction']['logfacility'] = logfacility

    if tcp:
        payload['auditnslogaction']['tcp'] = tcp

    if acl:
        payload['auditnslogaction']['acl'] = acl

    if timezone:
        payload['auditnslogaction']['timezone'] = timezone

    if userdefinedauditlog:
        payload['auditnslogaction']['userdefinedauditlog'] = userdefinedauditlog

    if appflowexport:
        payload['auditnslogaction']['appflowexport'] = appflowexport

    if lsn:
        payload['auditnslogaction']['lsn'] = lsn

    if alg:
        payload['auditnslogaction']['alg'] = alg

    if subscriberlog:
        payload['auditnslogaction']['subscriberlog'] = subscriberlog

    if sslinterception:
        payload['auditnslogaction']['sslinterception'] = sslinterception

    if domainresolvenow:
        payload['auditnslogaction']['domainresolvenow'] = domainresolvenow

    execution = __proxy__['citrixns.post']('config/auditnslogaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_auditnslogglobal_auditnslogpolicy_binding(priority=None, globalbindtype=None, builtin=None, policyname=None,
                                                  save=False):
    '''
    Add a new auditnslogglobal_auditnslogpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy. Minimum value = 1 Maximum value = 2147483647

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): Name of the audit nslog policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.add_auditnslogglobal_auditnslogpolicy_binding <args>

    '''

    result = {}

    payload = {'auditnslogglobal_auditnslogpolicy_binding': {}}

    if priority:
        payload['auditnslogglobal_auditnslogpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['auditnslogglobal_auditnslogpolicy_binding']['globalbindtype'] = globalbindtype

    if builtin:
        payload['auditnslogglobal_auditnslogpolicy_binding']['builtin'] = builtin

    if policyname:
        payload['auditnslogglobal_auditnslogpolicy_binding']['policyname'] = policyname

    execution = __proxy__['citrixns.post']('config/auditnslogglobal_auditnslogpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_auditnslogpolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new auditnslogpolicy to the running configuration.

    name(str): Name for the policy.  Must begin with a letter, number, or the underscore character (_), and must consist only
        of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the nslog policy is added.  The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my nslog policy" or my nslog policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that defines the messages to be logged to
        the nslog server. Minimum length = 1

    action(str): Nslog server action that is performed when this policy matches. NOTE: An nslog server action must be
        associated with an nslog audit policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.add_auditnslogpolicy <args>

    '''

    result = {}

    payload = {'auditnslogpolicy': {}}

    if name:
        payload['auditnslogpolicy']['name'] = name

    if rule:
        payload['auditnslogpolicy']['rule'] = rule

    if action:
        payload['auditnslogpolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/auditnslogpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_auditsyslogaction(name=None, serverip=None, serverdomainname=None, domainresolveretry=None, lbvservername=None,
                          serverport=None, loglevel=None, dateformat=None, logfacility=None, tcp=None, acl=None,
                          timezone=None, userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None,
                          subscriberlog=None, transport=None, tcpprofilename=None, maxlogdatasizetohold=None, dns=None,
                          netprofile=None, sslinterception=None, domainresolvenow=None, save=False):
    '''
    Add a new auditsyslogaction to the running configuration.

    name(str): Name of the syslog action. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the syslog action is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my syslog action" or my syslog action). Minimum length = 1

    serverip(str): IP address of the syslog server. Minimum length = 1

    serverdomainname(str): SYSLOG server name as a FQDN. Mutually exclusive with serverIP/lbVserverName. Minimum length = 1
        Maximum length = 255

    domainresolveretry(int): Time, in seconds, for which the NetScaler appliance waits before sending another DNS query to
        resolve the host name of the syslog server if the last query failed. Default value: 5 Minimum value = 5 Maximum
        value = 20939

    lbvservername(str): Name of the LB vserver. Mutually exclusive with syslog serverIP/serverName. Minimum length = 1
        Maximum length = 127

    serverport(int): Port on which the syslog server accepts connections. Minimum value = 1

    loglevel(list(str)): Audit log level, which specifies the types of events to log.  Available values function as follows:
        * ALL - All events. * EMERGENCY - Events that indicate an immediate crisis on the server. * ALERT - Events that
        might require action. * CRITICAL - Events that indicate an imminent server crisis. * ERROR - Events that indicate
        some type of error. * WARNING - Events that require action in the near future. * NOTICE - Events that the
        administrator should know about. * INFORMATIONAL - All but low-level events. * DEBUG - All events, in extreme
        detail. * NONE - No events. Possible values = ALL, EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE,
        INFORMATIONAL, DEBUG, NONE

    dateformat(str): Format of dates in the logs. Supported formats are:  * MMDDYYYY. -U.S. style month/date/year format. *
        DDMMYYYY - European style date/month/year format. * YYYYMMDD - ISO style year/month/date format. Possible values
        = MMDDYYYY, DDMMYYYY, YYYYMMDD

    logfacility(str): Facility value, as defined in RFC 3164, assigned to the log message.  Log facility values are numbers 0
        to 7 (LOCAL0 through LOCAL7). Each number indicates where a specific message originated from, such as the
        NetScaler appliance itself, the VPN, or external. Possible values = LOCAL0, LOCAL1, LOCAL2, LOCAL3, LOCAL4,
        LOCAL5, LOCAL6, LOCAL7

    tcp(str): Log TCP messages. Possible values = NONE, ALL

    acl(str): Log access control list (ACL) messages. Possible values = ENABLED, DISABLED

    timezone(str): Time zone used for date and timestamps in the logs.  Supported settings are:  * GMT_TIME. Coordinated
        Universal time. * LOCAL_TIME. Use the servers timezone setting. Possible values = GMT_TIME, LOCAL_TIME

    userdefinedauditlog(str): Log user-configurable log messages to syslog.  Setting this parameter to NO causes auditing to
        ignore all user-configured message actions. Setting this parameter to YES causes auditing to log user-configured
        message actions that meet the other logging criteria. Possible values = YES, NO

    appflowexport(str): Export log messages to AppFlow collectors. Appflow collectors are entities to which log messages can
        be sent so that some action can be performed on them. Possible values = ENABLED, DISABLED

    lsn(str): Log lsn info. Possible values = ENABLED, DISABLED

    alg(str): Log alg info. Possible values = ENABLED, DISABLED

    subscriberlog(str): Log subscriber session event information. Possible values = ENABLED, DISABLED

    transport(str): Transport type used to send auditlogs to syslog server. Default type is UDP. Possible values = TCP, UDP

    tcpprofilename(str): Name of the TCP profile whose settings are to be applied to the audit server info to tune the TCP
        connection parameters. Minimum length = 1 Maximum length = 127

    maxlogdatasizetohold(int): Max size of log data that can be held in NSB chain of server info. Default value: 500 Minimum
        value = 50 Maximum value = 25600

    dns(str): Log DNS related syslog messages. Possible values = ENABLED, DISABLED

    netprofile(str): Name of the network profile. The SNIP configured in the network profile will be used as source IP while
        sending log messages. Minimum length = 1 Maximum length = 127

    sslinterception(str): Log SSL Interception event information. Possible values = ENABLED, DISABLED

    domainresolvenow(bool): Immediately send a DNS query to resolve the servers domain name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.add_auditsyslogaction <args>

    '''

    result = {}

    payload = {'auditsyslogaction': {}}

    if name:
        payload['auditsyslogaction']['name'] = name

    if serverip:
        payload['auditsyslogaction']['serverip'] = serverip

    if serverdomainname:
        payload['auditsyslogaction']['serverdomainname'] = serverdomainname

    if domainresolveretry:
        payload['auditsyslogaction']['domainresolveretry'] = domainresolveretry

    if lbvservername:
        payload['auditsyslogaction']['lbvservername'] = lbvservername

    if serverport:
        payload['auditsyslogaction']['serverport'] = serverport

    if loglevel:
        payload['auditsyslogaction']['loglevel'] = loglevel

    if dateformat:
        payload['auditsyslogaction']['dateformat'] = dateformat

    if logfacility:
        payload['auditsyslogaction']['logfacility'] = logfacility

    if tcp:
        payload['auditsyslogaction']['tcp'] = tcp

    if acl:
        payload['auditsyslogaction']['acl'] = acl

    if timezone:
        payload['auditsyslogaction']['timezone'] = timezone

    if userdefinedauditlog:
        payload['auditsyslogaction']['userdefinedauditlog'] = userdefinedauditlog

    if appflowexport:
        payload['auditsyslogaction']['appflowexport'] = appflowexport

    if lsn:
        payload['auditsyslogaction']['lsn'] = lsn

    if alg:
        payload['auditsyslogaction']['alg'] = alg

    if subscriberlog:
        payload['auditsyslogaction']['subscriberlog'] = subscriberlog

    if transport:
        payload['auditsyslogaction']['transport'] = transport

    if tcpprofilename:
        payload['auditsyslogaction']['tcpprofilename'] = tcpprofilename

    if maxlogdatasizetohold:
        payload['auditsyslogaction']['maxlogdatasizetohold'] = maxlogdatasizetohold

    if dns:
        payload['auditsyslogaction']['dns'] = dns

    if netprofile:
        payload['auditsyslogaction']['netprofile'] = netprofile

    if sslinterception:
        payload['auditsyslogaction']['sslinterception'] = sslinterception

    if domainresolvenow:
        payload['auditsyslogaction']['domainresolvenow'] = domainresolvenow

    execution = __proxy__['citrixns.post']('config/auditsyslogaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_auditsyslogglobal_auditsyslogpolicy_binding(priority=None, globalbindtype=None, builtin=None, policyname=None,
                                                    save=False):
    '''
    Add a new auditsyslogglobal_auditsyslogpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy. Minimum value = 1 Maximum value = 2147483647

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): Name of the audit syslog policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.add_auditsyslogglobal_auditsyslogpolicy_binding <args>

    '''

    result = {}

    payload = {'auditsyslogglobal_auditsyslogpolicy_binding': {}}

    if priority:
        payload['auditsyslogglobal_auditsyslogpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['auditsyslogglobal_auditsyslogpolicy_binding']['globalbindtype'] = globalbindtype

    if builtin:
        payload['auditsyslogglobal_auditsyslogpolicy_binding']['builtin'] = builtin

    if policyname:
        payload['auditsyslogglobal_auditsyslogpolicy_binding']['policyname'] = policyname

    execution = __proxy__['citrixns.post']('config/auditsyslogglobal_auditsyslogpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_auditsyslogpolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new auditsyslogpolicy to the running configuration.

    name(str): Name for the policy.  Must begin with a letter, number, or the underscore character (_), and must consist only
        of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the syslog policy is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my syslog policy" or my syslog policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that defines the messages to be logged to
        the syslog server. Minimum length = 1

    action(str): Syslog server action to perform when this policy matches traffic. NOTE: A syslog server action must be
        associated with a syslog audit policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.add_auditsyslogpolicy <args>

    '''

    result = {}

    payload = {'auditsyslogpolicy': {}}

    if name:
        payload['auditsyslogpolicy']['name'] = name

    if rule:
        payload['auditsyslogpolicy']['rule'] = rule

    if action:
        payload['auditsyslogpolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/auditsyslogpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_auditmessageaction(name=None, loglevel=None, stringbuilderexpr=None, logtonewnslog=None,
                           bypasssafetycheck=None):
    '''
    Show the running configuration for the auditmessageaction config key.

    name(str): Filters results that only match the name field.

    loglevel(str): Filters results that only match the loglevel field.

    stringbuilderexpr(str): Filters results that only match the stringbuilderexpr field.

    logtonewnslog(str): Filters results that only match the logtonewnslog field.

    bypasssafetycheck(str): Filters results that only match the bypasssafetycheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditmessageaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if loglevel:
        search_filter.append(['loglevel', loglevel])

    if stringbuilderexpr:
        search_filter.append(['stringbuilderexpr', stringbuilderexpr])

    if logtonewnslog:
        search_filter.append(['logtonewnslog', logtonewnslog])

    if bypasssafetycheck:
        search_filter.append(['bypasssafetycheck', bypasssafetycheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditmessageaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditmessageaction')

    return response


def get_auditmessages(loglevel=None, numofmesgs=None):
    '''
    Show the running configuration for the auditmessages config key.

    loglevel(list(str)): Filters results that only match the loglevel field.

    numofmesgs(int): Filters results that only match the numofmesgs field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditmessages

    '''

    search_filter = []

    if loglevel:
        search_filter.append(['loglevel', loglevel])

    if numofmesgs:
        search_filter.append(['numofmesgs', numofmesgs])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditmessages{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditmessages')

    return response


def get_auditnslogaction(name=None, serverip=None, serverdomainname=None, domainresolveretry=None, serverport=None,
                         loglevel=None, dateformat=None, logfacility=None, tcp=None, acl=None, timezone=None,
                         userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None, subscriberlog=None,
                         sslinterception=None, domainresolvenow=None):
    '''
    Show the running configuration for the auditnslogaction config key.

    name(str): Filters results that only match the name field.

    serverip(str): Filters results that only match the serverip field.

    serverdomainname(str): Filters results that only match the serverdomainname field.

    domainresolveretry(int): Filters results that only match the domainresolveretry field.

    serverport(int): Filters results that only match the serverport field.

    loglevel(list(str)): Filters results that only match the loglevel field.

    dateformat(str): Filters results that only match the dateformat field.

    logfacility(str): Filters results that only match the logfacility field.

    tcp(str): Filters results that only match the tcp field.

    acl(str): Filters results that only match the acl field.

    timezone(str): Filters results that only match the timezone field.

    userdefinedauditlog(str): Filters results that only match the userdefinedauditlog field.

    appflowexport(str): Filters results that only match the appflowexport field.

    lsn(str): Filters results that only match the lsn field.

    alg(str): Filters results that only match the alg field.

    subscriberlog(str): Filters results that only match the subscriberlog field.

    sslinterception(str): Filters results that only match the sslinterception field.

    domainresolvenow(bool): Filters results that only match the domainresolvenow field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if serverip:
        search_filter.append(['serverip', serverip])

    if serverdomainname:
        search_filter.append(['serverdomainname', serverdomainname])

    if domainresolveretry:
        search_filter.append(['domainresolveretry', domainresolveretry])

    if serverport:
        search_filter.append(['serverport', serverport])

    if loglevel:
        search_filter.append(['loglevel', loglevel])

    if dateformat:
        search_filter.append(['dateformat', dateformat])

    if logfacility:
        search_filter.append(['logfacility', logfacility])

    if tcp:
        search_filter.append(['tcp', tcp])

    if acl:
        search_filter.append(['acl', acl])

    if timezone:
        search_filter.append(['timezone', timezone])

    if userdefinedauditlog:
        search_filter.append(['userdefinedauditlog', userdefinedauditlog])

    if appflowexport:
        search_filter.append(['appflowexport', appflowexport])

    if lsn:
        search_filter.append(['lsn', lsn])

    if alg:
        search_filter.append(['alg', alg])

    if subscriberlog:
        search_filter.append(['subscriberlog', subscriberlog])

    if sslinterception:
        search_filter.append(['sslinterception', sslinterception])

    if domainresolvenow:
        search_filter.append(['domainresolvenow', domainresolvenow])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogaction')

    return response


def get_auditnslogglobal_auditnslogpolicy_binding(priority=None, globalbindtype=None, builtin=None, policyname=None):
    '''
    Show the running configuration for the auditnslogglobal_auditnslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogglobal_auditnslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogglobal_auditnslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogglobal_auditnslogpolicy_binding')

    return response


def get_auditnslogglobal_binding():
    '''
    Show the running configuration for the auditnslogglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogglobal_binding'), 'auditnslogglobal_binding')

    return response


def get_auditnslogparams():
    '''
    Show the running configuration for the auditnslogparams config key.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogparams

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogparams'), 'auditnslogparams')

    return response


def get_auditnslogpolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the auditnslogpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy')

    return response


def get_auditnslogpolicy_aaagroup_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_aaagroup_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_aaagroup_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_aaagroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_aaagroup_binding')

    return response


def get_auditnslogpolicy_aaauser_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_aaauser_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_aaauser_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_aaauser_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_aaauser_binding')

    return response


def get_auditnslogpolicy_appfwglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_appfwglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_appfwglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_appfwglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_appfwglobal_binding')

    return response


def get_auditnslogpolicy_auditnslogglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_auditnslogglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_auditnslogglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_auditnslogglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_auditnslogglobal_binding')

    return response


def get_auditnslogpolicy_authenticationvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_authenticationvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_authenticationvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_authenticationvserver_binding')

    return response


def get_auditnslogpolicy_binding():
    '''
    Show the running configuration for the auditnslogpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_binding'), 'auditnslogpolicy_binding')

    return response


def get_auditnslogpolicy_csvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_csvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_csvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_csvserver_binding')

    return response


def get_auditnslogpolicy_lbvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_lbvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_lbvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_lbvserver_binding')

    return response


def get_auditnslogpolicy_systemglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_systemglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_systemglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_systemglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_systemglobal_binding')

    return response


def get_auditnslogpolicy_tmglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_tmglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_tmglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_tmglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_tmglobal_binding')

    return response


def get_auditnslogpolicy_vpnglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_vpnglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_vpnglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_vpnglobal_binding')

    return response


def get_auditnslogpolicy_vpnvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the auditnslogpolicy_vpnvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditnslogpolicy_vpnvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditnslogpolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditnslogpolicy_vpnvserver_binding')

    return response


def get_auditsyslogaction(name=None, serverip=None, serverdomainname=None, domainresolveretry=None, lbvservername=None,
                          serverport=None, loglevel=None, dateformat=None, logfacility=None, tcp=None, acl=None,
                          timezone=None, userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None,
                          subscriberlog=None, transport=None, tcpprofilename=None, maxlogdatasizetohold=None, dns=None,
                          netprofile=None, sslinterception=None, domainresolvenow=None):
    '''
    Show the running configuration for the auditsyslogaction config key.

    name(str): Filters results that only match the name field.

    serverip(str): Filters results that only match the serverip field.

    serverdomainname(str): Filters results that only match the serverdomainname field.

    domainresolveretry(int): Filters results that only match the domainresolveretry field.

    lbvservername(str): Filters results that only match the lbvservername field.

    serverport(int): Filters results that only match the serverport field.

    loglevel(list(str)): Filters results that only match the loglevel field.

    dateformat(str): Filters results that only match the dateformat field.

    logfacility(str): Filters results that only match the logfacility field.

    tcp(str): Filters results that only match the tcp field.

    acl(str): Filters results that only match the acl field.

    timezone(str): Filters results that only match the timezone field.

    userdefinedauditlog(str): Filters results that only match the userdefinedauditlog field.

    appflowexport(str): Filters results that only match the appflowexport field.

    lsn(str): Filters results that only match the lsn field.

    alg(str): Filters results that only match the alg field.

    subscriberlog(str): Filters results that only match the subscriberlog field.

    transport(str): Filters results that only match the transport field.

    tcpprofilename(str): Filters results that only match the tcpprofilename field.

    maxlogdatasizetohold(int): Filters results that only match the maxlogdatasizetohold field.

    dns(str): Filters results that only match the dns field.

    netprofile(str): Filters results that only match the netprofile field.

    sslinterception(str): Filters results that only match the sslinterception field.

    domainresolvenow(bool): Filters results that only match the domainresolvenow field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if serverip:
        search_filter.append(['serverip', serverip])

    if serverdomainname:
        search_filter.append(['serverdomainname', serverdomainname])

    if domainresolveretry:
        search_filter.append(['domainresolveretry', domainresolveretry])

    if lbvservername:
        search_filter.append(['lbvservername', lbvservername])

    if serverport:
        search_filter.append(['serverport', serverport])

    if loglevel:
        search_filter.append(['loglevel', loglevel])

    if dateformat:
        search_filter.append(['dateformat', dateformat])

    if logfacility:
        search_filter.append(['logfacility', logfacility])

    if tcp:
        search_filter.append(['tcp', tcp])

    if acl:
        search_filter.append(['acl', acl])

    if timezone:
        search_filter.append(['timezone', timezone])

    if userdefinedauditlog:
        search_filter.append(['userdefinedauditlog', userdefinedauditlog])

    if appflowexport:
        search_filter.append(['appflowexport', appflowexport])

    if lsn:
        search_filter.append(['lsn', lsn])

    if alg:
        search_filter.append(['alg', alg])

    if subscriberlog:
        search_filter.append(['subscriberlog', subscriberlog])

    if transport:
        search_filter.append(['transport', transport])

    if tcpprofilename:
        search_filter.append(['tcpprofilename', tcpprofilename])

    if maxlogdatasizetohold:
        search_filter.append(['maxlogdatasizetohold', maxlogdatasizetohold])

    if dns:
        search_filter.append(['dns', dns])

    if netprofile:
        search_filter.append(['netprofile', netprofile])

    if sslinterception:
        search_filter.append(['sslinterception', sslinterception])

    if domainresolvenow:
        search_filter.append(['domainresolvenow', domainresolvenow])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogaction')

    return response


def get_auditsyslogglobal_auditsyslogpolicy_binding(priority=None, globalbindtype=None, builtin=None, policyname=None):
    '''
    Show the running configuration for the auditsyslogglobal_auditsyslogpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogglobal_auditsyslogpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogglobal_auditsyslogpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogglobal_auditsyslogpolicy_binding')

    return response


def get_auditsyslogglobal_binding():
    '''
    Show the running configuration for the auditsyslogglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogglobal_binding'), 'auditsyslogglobal_binding')

    return response


def get_auditsyslogparams():
    '''
    Show the running configuration for the auditsyslogparams config key.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogparams

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogparams'), 'auditsyslogparams')

    return response


def get_auditsyslogpolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the auditsyslogpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy')

    return response


def get_auditsyslogpolicy_aaagroup_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_aaagroup_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_aaagroup_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_aaagroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_aaagroup_binding')

    return response


def get_auditsyslogpolicy_aaauser_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_aaauser_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_aaauser_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_aaauser_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_aaauser_binding')

    return response


def get_auditsyslogpolicy_auditsyslogglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_auditsyslogglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_auditsyslogglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_auditsyslogglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_auditsyslogglobal_binding')

    return response


def get_auditsyslogpolicy_authenticationvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_authenticationvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_authenticationvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_authenticationvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_authenticationvserver_binding')

    return response


def get_auditsyslogpolicy_binding():
    '''
    Show the running configuration for the auditsyslogpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_binding'), 'auditsyslogpolicy_binding')

    return response


def get_auditsyslogpolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_csvserver_binding')

    return response


def get_auditsyslogpolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_lbvserver_binding')

    return response


def get_auditsyslogpolicy_rnatglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_rnatglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_rnatglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_rnatglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_rnatglobal_binding')

    return response


def get_auditsyslogpolicy_systemglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_systemglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_systemglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_systemglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_systemglobal_binding')

    return response


def get_auditsyslogpolicy_tmglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_tmglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_tmglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_tmglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_tmglobal_binding')

    return response


def get_auditsyslogpolicy_vpnglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_vpnglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_vpnglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_vpnglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_vpnglobal_binding')

    return response


def get_auditsyslogpolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the auditsyslogpolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.get_auditsyslogpolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/auditsyslogpolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'auditsyslogpolicy_vpnvserver_binding')

    return response


def unset_auditmessageaction(name=None, loglevel=None, stringbuilderexpr=None, logtonewnslog=None,
                             bypasssafetycheck=None, save=False):
    '''
    Unsets values from the auditmessageaction configuration key.

    name(bool): Unsets the name value.

    loglevel(bool): Unsets the loglevel value.

    stringbuilderexpr(bool): Unsets the stringbuilderexpr value.

    logtonewnslog(bool): Unsets the logtonewnslog value.

    bypasssafetycheck(bool): Unsets the bypasssafetycheck value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.unset_auditmessageaction <args>

    '''

    result = {}

    payload = {'auditmessageaction': {}}

    if name:
        payload['auditmessageaction']['name'] = True

    if loglevel:
        payload['auditmessageaction']['loglevel'] = True

    if stringbuilderexpr:
        payload['auditmessageaction']['stringbuilderexpr'] = True

    if logtonewnslog:
        payload['auditmessageaction']['logtonewnslog'] = True

    if bypasssafetycheck:
        payload['auditmessageaction']['bypasssafetycheck'] = True

    execution = __proxy__['citrixns.post']('config/auditmessageaction?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_auditnslogaction(name=None, serverip=None, serverdomainname=None, domainresolveretry=None, serverport=None,
                           loglevel=None, dateformat=None, logfacility=None, tcp=None, acl=None, timezone=None,
                           userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None, subscriberlog=None,
                           sslinterception=None, domainresolvenow=None, save=False):
    '''
    Unsets values from the auditnslogaction configuration key.

    name(bool): Unsets the name value.

    serverip(bool): Unsets the serverip value.

    serverdomainname(bool): Unsets the serverdomainname value.

    domainresolveretry(bool): Unsets the domainresolveretry value.

    serverport(bool): Unsets the serverport value.

    loglevel(bool): Unsets the loglevel value.

    dateformat(bool): Unsets the dateformat value.

    logfacility(bool): Unsets the logfacility value.

    tcp(bool): Unsets the tcp value.

    acl(bool): Unsets the acl value.

    timezone(bool): Unsets the timezone value.

    userdefinedauditlog(bool): Unsets the userdefinedauditlog value.

    appflowexport(bool): Unsets the appflowexport value.

    lsn(bool): Unsets the lsn value.

    alg(bool): Unsets the alg value.

    subscriberlog(bool): Unsets the subscriberlog value.

    sslinterception(bool): Unsets the sslinterception value.

    domainresolvenow(bool): Unsets the domainresolvenow value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.unset_auditnslogaction <args>

    '''

    result = {}

    payload = {'auditnslogaction': {}}

    if name:
        payload['auditnslogaction']['name'] = True

    if serverip:
        payload['auditnslogaction']['serverip'] = True

    if serverdomainname:
        payload['auditnslogaction']['serverdomainname'] = True

    if domainresolveretry:
        payload['auditnslogaction']['domainresolveretry'] = True

    if serverport:
        payload['auditnslogaction']['serverport'] = True

    if loglevel:
        payload['auditnslogaction']['loglevel'] = True

    if dateformat:
        payload['auditnslogaction']['dateformat'] = True

    if logfacility:
        payload['auditnslogaction']['logfacility'] = True

    if tcp:
        payload['auditnslogaction']['tcp'] = True

    if acl:
        payload['auditnslogaction']['acl'] = True

    if timezone:
        payload['auditnslogaction']['timezone'] = True

    if userdefinedauditlog:
        payload['auditnslogaction']['userdefinedauditlog'] = True

    if appflowexport:
        payload['auditnslogaction']['appflowexport'] = True

    if lsn:
        payload['auditnslogaction']['lsn'] = True

    if alg:
        payload['auditnslogaction']['alg'] = True

    if subscriberlog:
        payload['auditnslogaction']['subscriberlog'] = True

    if sslinterception:
        payload['auditnslogaction']['sslinterception'] = True

    if domainresolvenow:
        payload['auditnslogaction']['domainresolvenow'] = True

    execution = __proxy__['citrixns.post']('config/auditnslogaction?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_auditnslogparams(serverip=None, serverport=None, dateformat=None, loglevel=None, logfacility=None, tcp=None,
                           acl=None, timezone=None, userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None,
                           subscriberlog=None, sslinterception=None, save=False):
    '''
    Unsets values from the auditnslogparams configuration key.

    serverip(bool): Unsets the serverip value.

    serverport(bool): Unsets the serverport value.

    dateformat(bool): Unsets the dateformat value.

    loglevel(bool): Unsets the loglevel value.

    logfacility(bool): Unsets the logfacility value.

    tcp(bool): Unsets the tcp value.

    acl(bool): Unsets the acl value.

    timezone(bool): Unsets the timezone value.

    userdefinedauditlog(bool): Unsets the userdefinedauditlog value.

    appflowexport(bool): Unsets the appflowexport value.

    lsn(bool): Unsets the lsn value.

    alg(bool): Unsets the alg value.

    subscriberlog(bool): Unsets the subscriberlog value.

    sslinterception(bool): Unsets the sslinterception value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.unset_auditnslogparams <args>

    '''

    result = {}

    payload = {'auditnslogparams': {}}

    if serverip:
        payload['auditnslogparams']['serverip'] = True

    if serverport:
        payload['auditnslogparams']['serverport'] = True

    if dateformat:
        payload['auditnslogparams']['dateformat'] = True

    if loglevel:
        payload['auditnslogparams']['loglevel'] = True

    if logfacility:
        payload['auditnslogparams']['logfacility'] = True

    if tcp:
        payload['auditnslogparams']['tcp'] = True

    if acl:
        payload['auditnslogparams']['acl'] = True

    if timezone:
        payload['auditnslogparams']['timezone'] = True

    if userdefinedauditlog:
        payload['auditnslogparams']['userdefinedauditlog'] = True

    if appflowexport:
        payload['auditnslogparams']['appflowexport'] = True

    if lsn:
        payload['auditnslogparams']['lsn'] = True

    if alg:
        payload['auditnslogparams']['alg'] = True

    if subscriberlog:
        payload['auditnslogparams']['subscriberlog'] = True

    if sslinterception:
        payload['auditnslogparams']['sslinterception'] = True

    execution = __proxy__['citrixns.post']('config/auditnslogparams?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_auditsyslogaction(name=None, serverip=None, serverdomainname=None, domainresolveretry=None, lbvservername=None,
                            serverport=None, loglevel=None, dateformat=None, logfacility=None, tcp=None, acl=None,
                            timezone=None, userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None,
                            subscriberlog=None, transport=None, tcpprofilename=None, maxlogdatasizetohold=None, dns=None,
                            netprofile=None, sslinterception=None, domainresolvenow=None, save=False):
    '''
    Unsets values from the auditsyslogaction configuration key.

    name(bool): Unsets the name value.

    serverip(bool): Unsets the serverip value.

    serverdomainname(bool): Unsets the serverdomainname value.

    domainresolveretry(bool): Unsets the domainresolveretry value.

    lbvservername(bool): Unsets the lbvservername value.

    serverport(bool): Unsets the serverport value.

    loglevel(bool): Unsets the loglevel value.

    dateformat(bool): Unsets the dateformat value.

    logfacility(bool): Unsets the logfacility value.

    tcp(bool): Unsets the tcp value.

    acl(bool): Unsets the acl value.

    timezone(bool): Unsets the timezone value.

    userdefinedauditlog(bool): Unsets the userdefinedauditlog value.

    appflowexport(bool): Unsets the appflowexport value.

    lsn(bool): Unsets the lsn value.

    alg(bool): Unsets the alg value.

    subscriberlog(bool): Unsets the subscriberlog value.

    transport(bool): Unsets the transport value.

    tcpprofilename(bool): Unsets the tcpprofilename value.

    maxlogdatasizetohold(bool): Unsets the maxlogdatasizetohold value.

    dns(bool): Unsets the dns value.

    netprofile(bool): Unsets the netprofile value.

    sslinterception(bool): Unsets the sslinterception value.

    domainresolvenow(bool): Unsets the domainresolvenow value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.unset_auditsyslogaction <args>

    '''

    result = {}

    payload = {'auditsyslogaction': {}}

    if name:
        payload['auditsyslogaction']['name'] = True

    if serverip:
        payload['auditsyslogaction']['serverip'] = True

    if serverdomainname:
        payload['auditsyslogaction']['serverdomainname'] = True

    if domainresolveretry:
        payload['auditsyslogaction']['domainresolveretry'] = True

    if lbvservername:
        payload['auditsyslogaction']['lbvservername'] = True

    if serverport:
        payload['auditsyslogaction']['serverport'] = True

    if loglevel:
        payload['auditsyslogaction']['loglevel'] = True

    if dateformat:
        payload['auditsyslogaction']['dateformat'] = True

    if logfacility:
        payload['auditsyslogaction']['logfacility'] = True

    if tcp:
        payload['auditsyslogaction']['tcp'] = True

    if acl:
        payload['auditsyslogaction']['acl'] = True

    if timezone:
        payload['auditsyslogaction']['timezone'] = True

    if userdefinedauditlog:
        payload['auditsyslogaction']['userdefinedauditlog'] = True

    if appflowexport:
        payload['auditsyslogaction']['appflowexport'] = True

    if lsn:
        payload['auditsyslogaction']['lsn'] = True

    if alg:
        payload['auditsyslogaction']['alg'] = True

    if subscriberlog:
        payload['auditsyslogaction']['subscriberlog'] = True

    if transport:
        payload['auditsyslogaction']['transport'] = True

    if tcpprofilename:
        payload['auditsyslogaction']['tcpprofilename'] = True

    if maxlogdatasizetohold:
        payload['auditsyslogaction']['maxlogdatasizetohold'] = True

    if dns:
        payload['auditsyslogaction']['dns'] = True

    if netprofile:
        payload['auditsyslogaction']['netprofile'] = True

    if sslinterception:
        payload['auditsyslogaction']['sslinterception'] = True

    if domainresolvenow:
        payload['auditsyslogaction']['domainresolvenow'] = True

    execution = __proxy__['citrixns.post']('config/auditsyslogaction?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_auditsyslogparams(serverip=None, serverport=None, dateformat=None, loglevel=None, logfacility=None, tcp=None,
                            acl=None, timezone=None, userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None,
                            subscriberlog=None, dns=None, sslinterception=None, save=False):
    '''
    Unsets values from the auditsyslogparams configuration key.

    serverip(bool): Unsets the serverip value.

    serverport(bool): Unsets the serverport value.

    dateformat(bool): Unsets the dateformat value.

    loglevel(bool): Unsets the loglevel value.

    logfacility(bool): Unsets the logfacility value.

    tcp(bool): Unsets the tcp value.

    acl(bool): Unsets the acl value.

    timezone(bool): Unsets the timezone value.

    userdefinedauditlog(bool): Unsets the userdefinedauditlog value.

    appflowexport(bool): Unsets the appflowexport value.

    lsn(bool): Unsets the lsn value.

    alg(bool): Unsets the alg value.

    subscriberlog(bool): Unsets the subscriberlog value.

    dns(bool): Unsets the dns value.

    sslinterception(bool): Unsets the sslinterception value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.unset_auditsyslogparams <args>

    '''

    result = {}

    payload = {'auditsyslogparams': {}}

    if serverip:
        payload['auditsyslogparams']['serverip'] = True

    if serverport:
        payload['auditsyslogparams']['serverport'] = True

    if dateformat:
        payload['auditsyslogparams']['dateformat'] = True

    if loglevel:
        payload['auditsyslogparams']['loglevel'] = True

    if logfacility:
        payload['auditsyslogparams']['logfacility'] = True

    if tcp:
        payload['auditsyslogparams']['tcp'] = True

    if acl:
        payload['auditsyslogparams']['acl'] = True

    if timezone:
        payload['auditsyslogparams']['timezone'] = True

    if userdefinedauditlog:
        payload['auditsyslogparams']['userdefinedauditlog'] = True

    if appflowexport:
        payload['auditsyslogparams']['appflowexport'] = True

    if lsn:
        payload['auditsyslogparams']['lsn'] = True

    if alg:
        payload['auditsyslogparams']['alg'] = True

    if subscriberlog:
        payload['auditsyslogparams']['subscriberlog'] = True

    if dns:
        payload['auditsyslogparams']['dns'] = True

    if sslinterception:
        payload['auditsyslogparams']['sslinterception'] = True

    execution = __proxy__['citrixns.post']('config/auditsyslogparams?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_auditmessageaction(name=None, loglevel=None, stringbuilderexpr=None, logtonewnslog=None,
                              bypasssafetycheck=None, save=False):
    '''
    Update the running configuration for the auditmessageaction config key.

    name(str): Name of the audit message action. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Cannot be changed after the message action is added.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my message action" or my message action). Minimum length = 1

    loglevel(str): Audit log level, which specifies the severity level of the log message being generated..  The following
        loglevels are valid:  * EMERGENCY - Events that indicate an immediate crisis on the server. * ALERT - Events that
        might require action. * CRITICAL - Events that indicate an imminent server crisis. * ERROR - Events that indicate
        some type of error. * WARNING - Events that require action in the near future. * NOTICE - Events that the
        administrator should know about. * INFORMATIONAL - All but low-level events. * DEBUG - All events, in extreme
        detail. Possible values = EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE, INFORMATIONAL, DEBUG

    stringbuilderexpr(str): Default-syntax expression that defines the format and content of the log message.

    logtonewnslog(str): Send the message to the new nslog. Possible values = YES, NO

    bypasssafetycheck(str): Bypass the safety check and allow unsafe expressions. Default value: NO Possible values = YES,
        NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.update_auditmessageaction <args>

    '''

    result = {}

    payload = {'auditmessageaction': {}}

    if name:
        payload['auditmessageaction']['name'] = name

    if loglevel:
        payload['auditmessageaction']['loglevel'] = loglevel

    if stringbuilderexpr:
        payload['auditmessageaction']['stringbuilderexpr'] = stringbuilderexpr

    if logtonewnslog:
        payload['auditmessageaction']['logtonewnslog'] = logtonewnslog

    if bypasssafetycheck:
        payload['auditmessageaction']['bypasssafetycheck'] = bypasssafetycheck

    execution = __proxy__['citrixns.put']('config/auditmessageaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_auditnslogaction(name=None, serverip=None, serverdomainname=None, domainresolveretry=None, serverport=None,
                            loglevel=None, dateformat=None, logfacility=None, tcp=None, acl=None, timezone=None,
                            userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None, subscriberlog=None,
                            sslinterception=None, domainresolvenow=None, save=False):
    '''
    Update the running configuration for the auditnslogaction config key.

    name(str): Name of the nslog action. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the nslog action is added.  The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my nslog action" or my nslog action). Minimum length = 1

    serverip(str): IP address of the nslog server. Minimum length = 1

    serverdomainname(str): Auditserver name as a FQDN. Mutually exclusive with serverIP. Minimum length = 1 Maximum length =
        255

    domainresolveretry(int): Time, in seconds, for which the NetScaler appliance waits before sending another DNS query to
        resolve the host name of the audit server if the last query failed. Default value: 5 Minimum value = 5 Maximum
        value = 20939

    serverport(int): Port on which the nslog server accepts connections. Minimum value = 1

    loglevel(list(str)): Audit log level, which specifies the types of events to log.  Available settings function as
        follows:  * ALL - All events. * EMERGENCY - Events that indicate an immediate crisis on the server. * ALERT -
        Events that might require action. * CRITICAL - Events that indicate an imminent server crisis. * ERROR - Events
        that indicate some type of error. * WARNING - Events that require action in the near future. * NOTICE - Events
        that the administrator should know about. * INFORMATIONAL - All but low-level events. * DEBUG - All events, in
        extreme detail. * NONE - No events. Possible values = ALL, EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE,
        INFORMATIONAL, DEBUG, NONE

    dateformat(str): Format of dates in the logs. Supported formats are:  * MMDDYYYY - U.S. style month/date/year format. *
        DDMMYYYY - European style date/month/year format. * YYYYMMDD - ISO style year/month/date format. Possible values
        = MMDDYYYY, DDMMYYYY, YYYYMMDD

    logfacility(str): Facility value, as defined in RFC 3164, assigned to the log message.  Log facility values are numbers 0
        to 7 (LOCAL0 through LOCAL7). Each number indicates where a specific message originated from, such as the
        NetScaler appliance itself, the VPN, or external. Possible values = LOCAL0, LOCAL1, LOCAL2, LOCAL3, LOCAL4,
        LOCAL5, LOCAL6, LOCAL7

    tcp(str): Log TCP messages. Possible values = NONE, ALL

    acl(str): Log access control list (ACL) messages. Possible values = ENABLED, DISABLED

    timezone(str): Time zone used for date and timestamps in the logs.  Available settings function as follows:  * GMT_TIME.
        Coordinated Universal Time. * LOCAL_TIME. The servers timezone setting. Possible values = GMT_TIME, LOCAL_TIME

    userdefinedauditlog(str): Log user-configurable log messages to nslog. Setting this parameter to NO causes auditing to
        ignore all user-configured message actions. Setting this parameter to YES causes auditing to log user-configured
        message actions that meet the other logging criteria. Possible values = YES, NO

    appflowexport(str): Export log messages to AppFlow collectors. Appflow collectors are entities to which log messages can
        be sent so that some action can be performed on them. Possible values = ENABLED, DISABLED

    lsn(str): Log the LSN messages. Possible values = ENABLED, DISABLED

    alg(str): Log the ALG messages. Possible values = ENABLED, DISABLED

    subscriberlog(str): Log subscriber session event information. Possible values = ENABLED, DISABLED

    sslinterception(str): Log SSL Interception event information. Possible values = ENABLED, DISABLED

    domainresolvenow(bool): Immediately send a DNS query to resolve the servers domain name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.update_auditnslogaction <args>

    '''

    result = {}

    payload = {'auditnslogaction': {}}

    if name:
        payload['auditnslogaction']['name'] = name

    if serverip:
        payload['auditnslogaction']['serverip'] = serverip

    if serverdomainname:
        payload['auditnslogaction']['serverdomainname'] = serverdomainname

    if domainresolveretry:
        payload['auditnslogaction']['domainresolveretry'] = domainresolveretry

    if serverport:
        payload['auditnslogaction']['serverport'] = serverport

    if loglevel:
        payload['auditnslogaction']['loglevel'] = loglevel

    if dateformat:
        payload['auditnslogaction']['dateformat'] = dateformat

    if logfacility:
        payload['auditnslogaction']['logfacility'] = logfacility

    if tcp:
        payload['auditnslogaction']['tcp'] = tcp

    if acl:
        payload['auditnslogaction']['acl'] = acl

    if timezone:
        payload['auditnslogaction']['timezone'] = timezone

    if userdefinedauditlog:
        payload['auditnslogaction']['userdefinedauditlog'] = userdefinedauditlog

    if appflowexport:
        payload['auditnslogaction']['appflowexport'] = appflowexport

    if lsn:
        payload['auditnslogaction']['lsn'] = lsn

    if alg:
        payload['auditnslogaction']['alg'] = alg

    if subscriberlog:
        payload['auditnslogaction']['subscriberlog'] = subscriberlog

    if sslinterception:
        payload['auditnslogaction']['sslinterception'] = sslinterception

    if domainresolvenow:
        payload['auditnslogaction']['domainresolvenow'] = domainresolvenow

    execution = __proxy__['citrixns.put']('config/auditnslogaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_auditnslogparams(serverip=None, serverport=None, dateformat=None, loglevel=None, logfacility=None, tcp=None,
                            acl=None, timezone=None, userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None,
                            subscriberlog=None, sslinterception=None, save=False):
    '''
    Update the running configuration for the auditnslogparams config key.

    serverip(str): IP address of the nslog server. Minimum length = 1

    serverport(int): Port on which the nslog server accepts connections. Minimum value = 1

    dateformat(str): Format of dates in the logs. Supported formats are:  * MMDDYYYY - U.S. style month/date/year format. *
        DDMMYYYY - European style date/month/year format. * YYYYMMDD - ISO style year/month/date format. Possible values
        = MMDDYYYY, DDMMYYYY, YYYYMMDD

    loglevel(list(str)): Types of information to be logged.  Available settings function as follows:  * ALL - All events. *
        EMERGENCY - Events that indicate an immediate crisis on the server. * ALERT - Events that might require action. *
        CRITICAL - Events that indicate an imminent server crisis. * ERROR - Events that indicate some type of error. *
        WARNING - Events that require action in the near future. * NOTICE - Events that the administrator should know
        about. * INFORMATIONAL - All but low-level events. * DEBUG - All events, in extreme detail. * NONE - No events.
        Possible values = ALL, EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE, INFORMATIONAL, DEBUG, NONE

    logfacility(str): Facility value, as defined in RFC 3164, assigned to the log message.  Log facility values are numbers 0
        to 7 (LOCAL0 through LOCAL7). Each number indicates where a specific message originated from, such as the
        NetScaler appliance itself, the VPN, or external. Possible values = LOCAL0, LOCAL1, LOCAL2, LOCAL3, LOCAL4,
        LOCAL5, LOCAL6, LOCAL7

    tcp(str): Configure auditing to log TCP messages. Possible values = NONE, ALL

    acl(str): Configure auditing to log access control list (ACL) messages. Possible values = ENABLED, DISABLED

    timezone(str): Time zone used for date and timestamps in the logs.  Supported settings are:  * GMT_TIME - Coordinated
        Universal Time. * LOCAL_TIME - Use the servers timezone setting. Possible values = GMT_TIME, LOCAL_TIME

    userdefinedauditlog(str): Log user-configurable log messages to nslog. Setting this parameter to NO causes auditing to
        ignore all user-configured message actions. Setting this parameter to YES causes auditing to log user-configured
        message actions that meet the other logging criteria. Possible values = YES, NO

    appflowexport(str): Export log messages to AppFlow collectors. Appflow collectors are entities to which log messages can
        be sent so that some action can be performed on them. Possible values = ENABLED, DISABLED

    lsn(str): Log the LSN messages. Possible values = ENABLED, DISABLED

    alg(str): Log the ALG messages. Possible values = ENABLED, DISABLED

    subscriberlog(str): Log subscriber session event information. Possible values = ENABLED, DISABLED

    sslinterception(str): Log SSL Interception event information. Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.update_auditnslogparams <args>

    '''

    result = {}

    payload = {'auditnslogparams': {}}

    if serverip:
        payload['auditnslogparams']['serverip'] = serverip

    if serverport:
        payload['auditnslogparams']['serverport'] = serverport

    if dateformat:
        payload['auditnslogparams']['dateformat'] = dateformat

    if loglevel:
        payload['auditnslogparams']['loglevel'] = loglevel

    if logfacility:
        payload['auditnslogparams']['logfacility'] = logfacility

    if tcp:
        payload['auditnslogparams']['tcp'] = tcp

    if acl:
        payload['auditnslogparams']['acl'] = acl

    if timezone:
        payload['auditnslogparams']['timezone'] = timezone

    if userdefinedauditlog:
        payload['auditnslogparams']['userdefinedauditlog'] = userdefinedauditlog

    if appflowexport:
        payload['auditnslogparams']['appflowexport'] = appflowexport

    if lsn:
        payload['auditnslogparams']['lsn'] = lsn

    if alg:
        payload['auditnslogparams']['alg'] = alg

    if subscriberlog:
        payload['auditnslogparams']['subscriberlog'] = subscriberlog

    if sslinterception:
        payload['auditnslogparams']['sslinterception'] = sslinterception

    execution = __proxy__['citrixns.put']('config/auditnslogparams', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_auditnslogpolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the auditnslogpolicy config key.

    name(str): Name for the policy.  Must begin with a letter, number, or the underscore character (_), and must consist only
        of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the nslog policy is added.  The following requirement applies only
        to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation
        marks (for example, "my nslog policy" or my nslog policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that defines the messages to be logged to
        the nslog server. Minimum length = 1

    action(str): Nslog server action that is performed when this policy matches. NOTE: An nslog server action must be
        associated with an nslog audit policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.update_auditnslogpolicy <args>

    '''

    result = {}

    payload = {'auditnslogpolicy': {}}

    if name:
        payload['auditnslogpolicy']['name'] = name

    if rule:
        payload['auditnslogpolicy']['rule'] = rule

    if action:
        payload['auditnslogpolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/auditnslogpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_auditsyslogaction(name=None, serverip=None, serverdomainname=None, domainresolveretry=None,
                             lbvservername=None, serverport=None, loglevel=None, dateformat=None, logfacility=None,
                             tcp=None, acl=None, timezone=None, userdefinedauditlog=None, appflowexport=None, lsn=None,
                             alg=None, subscriberlog=None, transport=None, tcpprofilename=None,
                             maxlogdatasizetohold=None, dns=None, netprofile=None, sslinterception=None,
                             domainresolvenow=None, save=False):
    '''
    Update the running configuration for the auditsyslogaction config key.

    name(str): Name of the syslog action. Must begin with a letter, number, or the underscore character (_), and must contain
        only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the syslog action is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my syslog action" or my syslog action). Minimum length = 1

    serverip(str): IP address of the syslog server. Minimum length = 1

    serverdomainname(str): SYSLOG server name as a FQDN. Mutually exclusive with serverIP/lbVserverName. Minimum length = 1
        Maximum length = 255

    domainresolveretry(int): Time, in seconds, for which the NetScaler appliance waits before sending another DNS query to
        resolve the host name of the syslog server if the last query failed. Default value: 5 Minimum value = 5 Maximum
        value = 20939

    lbvservername(str): Name of the LB vserver. Mutually exclusive with syslog serverIP/serverName. Minimum length = 1
        Maximum length = 127

    serverport(int): Port on which the syslog server accepts connections. Minimum value = 1

    loglevel(list(str)): Audit log level, which specifies the types of events to log.  Available values function as follows:
        * ALL - All events. * EMERGENCY - Events that indicate an immediate crisis on the server. * ALERT - Events that
        might require action. * CRITICAL - Events that indicate an imminent server crisis. * ERROR - Events that indicate
        some type of error. * WARNING - Events that require action in the near future. * NOTICE - Events that the
        administrator should know about. * INFORMATIONAL - All but low-level events. * DEBUG - All events, in extreme
        detail. * NONE - No events. Possible values = ALL, EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE,
        INFORMATIONAL, DEBUG, NONE

    dateformat(str): Format of dates in the logs. Supported formats are:  * MMDDYYYY. -U.S. style month/date/year format. *
        DDMMYYYY - European style date/month/year format. * YYYYMMDD - ISO style year/month/date format. Possible values
        = MMDDYYYY, DDMMYYYY, YYYYMMDD

    logfacility(str): Facility value, as defined in RFC 3164, assigned to the log message.  Log facility values are numbers 0
        to 7 (LOCAL0 through LOCAL7). Each number indicates where a specific message originated from, such as the
        NetScaler appliance itself, the VPN, or external. Possible values = LOCAL0, LOCAL1, LOCAL2, LOCAL3, LOCAL4,
        LOCAL5, LOCAL6, LOCAL7

    tcp(str): Log TCP messages. Possible values = NONE, ALL

    acl(str): Log access control list (ACL) messages. Possible values = ENABLED, DISABLED

    timezone(str): Time zone used for date and timestamps in the logs.  Supported settings are:  * GMT_TIME. Coordinated
        Universal time. * LOCAL_TIME. Use the servers timezone setting. Possible values = GMT_TIME, LOCAL_TIME

    userdefinedauditlog(str): Log user-configurable log messages to syslog.  Setting this parameter to NO causes auditing to
        ignore all user-configured message actions. Setting this parameter to YES causes auditing to log user-configured
        message actions that meet the other logging criteria. Possible values = YES, NO

    appflowexport(str): Export log messages to AppFlow collectors. Appflow collectors are entities to which log messages can
        be sent so that some action can be performed on them. Possible values = ENABLED, DISABLED

    lsn(str): Log lsn info. Possible values = ENABLED, DISABLED

    alg(str): Log alg info. Possible values = ENABLED, DISABLED

    subscriberlog(str): Log subscriber session event information. Possible values = ENABLED, DISABLED

    transport(str): Transport type used to send auditlogs to syslog server. Default type is UDP. Possible values = TCP, UDP

    tcpprofilename(str): Name of the TCP profile whose settings are to be applied to the audit server info to tune the TCP
        connection parameters. Minimum length = 1 Maximum length = 127

    maxlogdatasizetohold(int): Max size of log data that can be held in NSB chain of server info. Default value: 500 Minimum
        value = 50 Maximum value = 25600

    dns(str): Log DNS related syslog messages. Possible values = ENABLED, DISABLED

    netprofile(str): Name of the network profile. The SNIP configured in the network profile will be used as source IP while
        sending log messages. Minimum length = 1 Maximum length = 127

    sslinterception(str): Log SSL Interception event information. Possible values = ENABLED, DISABLED

    domainresolvenow(bool): Immediately send a DNS query to resolve the servers domain name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.update_auditsyslogaction <args>

    '''

    result = {}

    payload = {'auditsyslogaction': {}}

    if name:
        payload['auditsyslogaction']['name'] = name

    if serverip:
        payload['auditsyslogaction']['serverip'] = serverip

    if serverdomainname:
        payload['auditsyslogaction']['serverdomainname'] = serverdomainname

    if domainresolveretry:
        payload['auditsyslogaction']['domainresolveretry'] = domainresolveretry

    if lbvservername:
        payload['auditsyslogaction']['lbvservername'] = lbvservername

    if serverport:
        payload['auditsyslogaction']['serverport'] = serverport

    if loglevel:
        payload['auditsyslogaction']['loglevel'] = loglevel

    if dateformat:
        payload['auditsyslogaction']['dateformat'] = dateformat

    if logfacility:
        payload['auditsyslogaction']['logfacility'] = logfacility

    if tcp:
        payload['auditsyslogaction']['tcp'] = tcp

    if acl:
        payload['auditsyslogaction']['acl'] = acl

    if timezone:
        payload['auditsyslogaction']['timezone'] = timezone

    if userdefinedauditlog:
        payload['auditsyslogaction']['userdefinedauditlog'] = userdefinedauditlog

    if appflowexport:
        payload['auditsyslogaction']['appflowexport'] = appflowexport

    if lsn:
        payload['auditsyslogaction']['lsn'] = lsn

    if alg:
        payload['auditsyslogaction']['alg'] = alg

    if subscriberlog:
        payload['auditsyslogaction']['subscriberlog'] = subscriberlog

    if transport:
        payload['auditsyslogaction']['transport'] = transport

    if tcpprofilename:
        payload['auditsyslogaction']['tcpprofilename'] = tcpprofilename

    if maxlogdatasizetohold:
        payload['auditsyslogaction']['maxlogdatasizetohold'] = maxlogdatasizetohold

    if dns:
        payload['auditsyslogaction']['dns'] = dns

    if netprofile:
        payload['auditsyslogaction']['netprofile'] = netprofile

    if sslinterception:
        payload['auditsyslogaction']['sslinterception'] = sslinterception

    if domainresolvenow:
        payload['auditsyslogaction']['domainresolvenow'] = domainresolvenow

    execution = __proxy__['citrixns.put']('config/auditsyslogaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_auditsyslogparams(serverip=None, serverport=None, dateformat=None, loglevel=None, logfacility=None, tcp=None,
                             acl=None, timezone=None, userdefinedauditlog=None, appflowexport=None, lsn=None, alg=None,
                             subscriberlog=None, dns=None, sslinterception=None, save=False):
    '''
    Update the running configuration for the auditsyslogparams config key.

    serverip(str): IP address of the syslog server. Minimum length = 1

    serverport(int): Port on which the syslog server accepts connections. Minimum value = 1

    dateformat(str): Format of dates in the logs. Supported formats are:  * MMDDYYYY - U.S. style month/date/year format. *
        DDMMYYYY. European style -date/month/year format. * YYYYMMDD - ISO style year/month/date format. Possible values
        = MMDDYYYY, DDMMYYYY, YYYYMMDD

    loglevel(list(str)): Types of information to be logged.  Available settings function as follows:  * ALL - All events. *
        EMERGENCY - Events that indicate an immediate crisis on the server. * ALERT - Events that might require action. *
        CRITICAL - Events that indicate an imminent server crisis. * ERROR - Events that indicate some type of error. *
        WARNING - Events that require action in the near future. * NOTICE - Events that the administrator should know
        about. * INFORMATIONAL - All but low-level events. * DEBUG - All events, in extreme detail. * NONE - No events.
        Possible values = ALL, EMERGENCY, ALERT, CRITICAL, ERROR, WARNING, NOTICE, INFORMATIONAL, DEBUG, NONE

    logfacility(str): Facility value, as defined in RFC 3164, assigned to the log message.  Log facility values are numbers 0
        to 7 (LOCAL0 through LOCAL7). Each number indicates where a specific message originated from, such as the
        NetScaler appliance itself, the VPN, or external. Possible values = LOCAL0, LOCAL1, LOCAL2, LOCAL3, LOCAL4,
        LOCAL5, LOCAL6, LOCAL7

    tcp(str): Log TCP messages. Possible values = NONE, ALL

    acl(str): Log access control list (ACL) messages. Possible values = ENABLED, DISABLED

    timezone(str): Time zone used for date and timestamps in the logs.  Available settings function as follows:  * GMT_TIME -
        Coordinated Universal Time. * LOCAL_TIME Use the servers timezone setting. Possible values = GMT_TIME,
        LOCAL_TIME

    userdefinedauditlog(str): Log user-configurable log messages to syslog.  Setting this parameter to NO causes audit to
        ignore all user-configured message actions. Setting this parameter to YES causes audit to log user-configured
        message actions that meet the other logging criteria. Possible values = YES, NO

    appflowexport(str): Export log messages to AppFlow collectors. Appflow collectors are entities to which log messages can
        be sent so that some action can be performed on them. Possible values = ENABLED, DISABLED

    lsn(str): Log the LSN messages. Possible values = ENABLED, DISABLED

    alg(str): Log the ALG messages. Possible values = ENABLED, DISABLED

    subscriberlog(str): Log subscriber session event information. Possible values = ENABLED, DISABLED

    dns(str): Log DNS related syslog messages. Possible values = ENABLED, DISABLED

    sslinterception(str): Log SSL Interceptionn event information. Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.update_auditsyslogparams <args>

    '''

    result = {}

    payload = {'auditsyslogparams': {}}

    if serverip:
        payload['auditsyslogparams']['serverip'] = serverip

    if serverport:
        payload['auditsyslogparams']['serverport'] = serverport

    if dateformat:
        payload['auditsyslogparams']['dateformat'] = dateformat

    if loglevel:
        payload['auditsyslogparams']['loglevel'] = loglevel

    if logfacility:
        payload['auditsyslogparams']['logfacility'] = logfacility

    if tcp:
        payload['auditsyslogparams']['tcp'] = tcp

    if acl:
        payload['auditsyslogparams']['acl'] = acl

    if timezone:
        payload['auditsyslogparams']['timezone'] = timezone

    if userdefinedauditlog:
        payload['auditsyslogparams']['userdefinedauditlog'] = userdefinedauditlog

    if appflowexport:
        payload['auditsyslogparams']['appflowexport'] = appflowexport

    if lsn:
        payload['auditsyslogparams']['lsn'] = lsn

    if alg:
        payload['auditsyslogparams']['alg'] = alg

    if subscriberlog:
        payload['auditsyslogparams']['subscriberlog'] = subscriberlog

    if dns:
        payload['auditsyslogparams']['dns'] = dns

    if sslinterception:
        payload['auditsyslogparams']['sslinterception'] = sslinterception

    execution = __proxy__['citrixns.put']('config/auditsyslogparams', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_auditsyslogpolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the auditsyslogpolicy config key.

    name(str): Name for the policy.  Must begin with a letter, number, or the underscore character (_), and must consist only
        of letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at sign (@), equals (=), colon (:), and
        underscore characters. Cannot be changed after the syslog policy is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my syslog policy" or my syslog policy). Minimum length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that defines the messages to be logged to
        the syslog server. Minimum length = 1

    action(str): Syslog server action to perform when this policy matches traffic. NOTE: A syslog server action must be
        associated with a syslog audit policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' audit.update_auditsyslogpolicy <args>

    '''

    result = {}

    payload = {'auditsyslogpolicy': {}}

    if name:
        payload['auditsyslogpolicy']['name'] = name

    if rule:
        payload['auditsyslogpolicy']['rule'] = rule

    if action:
        payload['auditsyslogpolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/auditsyslogpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
