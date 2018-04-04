# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the appflow key.

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

__virtualname__ = 'appflow'


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

    return False, 'The appflow execution module can only be loaded for citrixns proxy minions.'


def add_appflowaction(name=None, collectors=None, clientsidemeasurements=None, pagetracking=None, webinsight=None,
                      securityinsight=None, videoanalytics=None, distributionalgorithm=None, metricslog=None,
                      transactionlog=None, comment=None, newname=None, save=False):
    '''
    Add a new appflowaction to the running configuration.

    name(str): Name for the action. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my appflow action" or my appflow
        action).

    collectors(list(str)): Name(s) of collector(s) to be associated with the AppFlow action. Minimum length = 1

    clientsidemeasurements(str): On enabling this option, the NetScaler will collect the time required to load and render the
        mainpage on the client. Default value: DISABLED Possible values = ENABLED, DISABLED

    pagetracking(str): On enabling this option, the NetScaler will start tracking the page for waterfall chart by inserting a
        NS_ESNS cookie in the response. Default value: DISABLED Possible values = ENABLED, DISABLED

    webinsight(str): On enabling this option, the netscaler will send the webinsight records to the configured collectors.
        Default value: ENABLED Possible values = ENABLED, DISABLED

    securityinsight(str): On enabling this option, the netscaler will send the security insight records to the configured
        collectors. Default value: DISABLED Possible values = ENABLED, DISABLED

    videoanalytics(str): On enabling this option, the netscaler will send the videoinsight records to the configured
        collectors. Default value: DISABLED Possible values = ENABLED, DISABLED

    distributionalgorithm(str): On enabling this option, the netscaler will distribute records among the collectors. Else,
        all records will be sent to all the collectors. Default value: DISABLED Possible values = ENABLED, DISABLED

    metricslog(bool): If only the stats records are to be exported, turn on this option.

    transactionlog(str): If over stats channel, transactions logs also need to be sent, set this option appropriately. By
        default netscaler sends anomalous transaction logs over metrics channel. This can be changed to ALL or NONE
        transactions. Default value: ANOMALOUS Possible values = ANOMALOUS, NONE, ALL

    comment(str): Any comments about this action. In the CLI, if including spaces between words, enclose the comment in
        quotation marks. (The quotation marks are not required in the configuration utility.). Maximum length = 256

    newname(str): New name for the AppFlow action. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.   The following requirement applies only to the NetScaler CLI: If the name includes one or
        more spaces, enclose the name in double or single quotation marks (for example, "my appflow action" or my appflow
        action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.add_appflowaction <args>

    '''

    result = {}

    payload = {'appflowaction': {}}

    if name:
        payload['appflowaction']['name'] = name

    if collectors:
        payload['appflowaction']['collectors'] = collectors

    if clientsidemeasurements:
        payload['appflowaction']['clientsidemeasurements'] = clientsidemeasurements

    if pagetracking:
        payload['appflowaction']['pagetracking'] = pagetracking

    if webinsight:
        payload['appflowaction']['webinsight'] = webinsight

    if securityinsight:
        payload['appflowaction']['securityinsight'] = securityinsight

    if videoanalytics:
        payload['appflowaction']['videoanalytics'] = videoanalytics

    if distributionalgorithm:
        payload['appflowaction']['distributionalgorithm'] = distributionalgorithm

    if metricslog:
        payload['appflowaction']['metricslog'] = metricslog

    if transactionlog:
        payload['appflowaction']['transactionlog'] = transactionlog

    if comment:
        payload['appflowaction']['comment'] = comment

    if newname:
        payload['appflowaction']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/appflowaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_appflowcollector(name=None, ipaddress=None, port=None, netprofile=None, transport=None, newname=None,
                         save=False):
    '''
    Add a new appflowcollector to the running configuration.

    name(str): Name for the collector. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters.  Only four collectors can be configured.   The following requirement applies only to the NetScaler
        CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for example,
        "my appflow collector" or my appflow collector). Minimum length = 1 Maximum length = 127

    ipaddress(str): IPv4 address of the collector.

    port(int): Port on which the collector listens.

    netprofile(str): Netprofile to associate with the collector. The IP address defined in the profile is used as the source
        IP address for AppFlow traffic for this collector. If you do not set this parameter, the NetScaler IP (NSIP)
        address is used as the source IP address. Maximum length = 128

    transport(str): Type of collector: either logstream or ipfix. Default value: ipfix, Possible values = ipfix, logstream

    newname(str): New name for the collector. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at(@), equals (=), and
        hyphen (-) characters.   The following requirement applies only to the NetScaler CLI: If the name includes one or
        more spaces, enclose the name in double or single quotation marks (for example, "my appflow coll" or my appflow
        coll). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.add_appflowcollector <args>

    '''

    result = {}

    payload = {'appflowcollector': {}}

    if name:
        payload['appflowcollector']['name'] = name

    if ipaddress:
        payload['appflowcollector']['ipaddress'] = ipaddress

    if port:
        payload['appflowcollector']['port'] = port

    if netprofile:
        payload['appflowcollector']['netprofile'] = netprofile

    if transport:
        payload['appflowcollector']['transport'] = transport

    if newname:
        payload['appflowcollector']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/appflowcollector', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_appflowglobal_appflowpolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                            gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None,
                                            save=False):
    '''
    Add a new appflowglobal_appflowpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): Name of the AppFlow policy.

    labelname(str): Name of the label to invoke if the current policy evaluates to TRUE.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke policies bound to a virtual server or a user-defined policy label. After the invoked policies are
        evaluated, the flow returns to the policy with the next priority.

    ns_type(str): Global bind point for which to show detailed information about the policies bound to the bind point.
        Possible values = REQ_OVERRIDE, REQ_DEFAULT, OVERRIDE, DEFAULT, OTHERTCP_REQ_OVERRIDE, OTHERTCP_REQ_DEFAULT,
        MSSQL_REQ_OVERRIDE, MSSQL_REQ_DEFAULT, MYSQL_REQ_OVERRIDE, MYSQL_REQ_DEFAULT, ICA_REQ_OVERRIDE, ICA_REQ_DEFAULT,
        ORACLE_REQ_OVERRIDE, ORACLE_REQ_DEFAULT

    labeltype(str): Type of policy label to invoke. Specify vserver for a policy label associated with a virtual server, or
        policylabel for a user-defined policy label. Possible values = vserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.add_appflowglobal_appflowpolicy_binding <args>

    '''

    result = {}

    payload = {'appflowglobal_appflowpolicy_binding': {}}

    if priority:
        payload['appflowglobal_appflowpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['appflowglobal_appflowpolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['appflowglobal_appflowpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['appflowglobal_appflowpolicy_binding']['labelname'] = labelname

    if gotopriorityexpression:
        payload['appflowglobal_appflowpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['appflowglobal_appflowpolicy_binding']['invoke'] = invoke

    if ns_type:
        payload['appflowglobal_appflowpolicy_binding']['type'] = ns_type

    if labeltype:
        payload['appflowglobal_appflowpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/appflowglobal_appflowpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_appflowpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, newname=None, save=False):
    '''
    Add a new appflowpolicy to the running configuration.

    name(str): Name for the policy. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters.   The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my appflow policy" or my appflow
        policy).

    rule(str): Expression or other value against which the traffic is evaluated. Must be a Boolean, default syntax
        expression. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can be
        split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    action(str): Name of the action to be associated with this policy.

    undefaction(str): Name of the appflow action to be associated with this policy when an undef event occurs.

    comment(str): Any comments about this policy.

    newname(str): New name for the policy. Must begin with an ASCII alphabetic or underscore (_)character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my appflow policy" or my appflow
        policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.add_appflowpolicy <args>

    '''

    result = {}

    payload = {'appflowpolicy': {}}

    if name:
        payload['appflowpolicy']['name'] = name

    if rule:
        payload['appflowpolicy']['rule'] = rule

    if action:
        payload['appflowpolicy']['action'] = action

    if undefaction:
        payload['appflowpolicy']['undefaction'] = undefaction

    if comment:
        payload['appflowpolicy']['comment'] = comment

    if newname:
        payload['appflowpolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/appflowpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_appflowpolicylabel(labelname=None, policylabeltype=None, newname=None, save=False):
    '''
    Add a new appflowpolicylabel to the running configuration.

    labelname(str): Name of the AppFlow policy label. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or
        more spaces, enclose the name in double or single quotation marks (for example, "my appflow policylabel" or my
        appflow policylabel). Minimum length = 1

    policylabeltype(str): Type of traffic evaluated by the policies bound to the policy label. Default value: HTTP Possible
        values = HTTP, OTHERTCP

    newname(str): New name for the policy label. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.     The following requirement applies only to the NetScaler CLI: If the name includes one
        or more spaces, enclose the name in double or single quotation marks (for example, "my appflow policylabel" or my
        appflow policylabel). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.add_appflowpolicylabel <args>

    '''

    result = {}

    payload = {'appflowpolicylabel': {}}

    if labelname:
        payload['appflowpolicylabel']['labelname'] = labelname

    if policylabeltype:
        payload['appflowpolicylabel']['policylabeltype'] = policylabeltype

    if newname:
        payload['appflowpolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/appflowpolicylabel', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_appflowpolicylabel_appflowpolicy_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                                 gotopriorityexpression=None, invoke=None, labeltype=None, save=False):
    '''
    Add a new appflowpolicylabel_appflowpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    policyname(str): Name of the AppFlow policy.

    labelname(str): Name of the policy label to which to bind the policy. Minimum length = 1

    invoke_labelname(str): Name of the label to invoke if the current policy evaluates to TRUE.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke policies bound to a virtual server or a user-defined policy label. After the invoked policies are
        evaluated, the flow returns to the policy with the next priority.

    labeltype(str): Type of policy label to be invoked. Possible values = vserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.add_appflowpolicylabel_appflowpolicy_binding <args>

    '''

    result = {}

    payload = {'appflowpolicylabel_appflowpolicy_binding': {}}

    if priority:
        payload['appflowpolicylabel_appflowpolicy_binding']['priority'] = priority

    if policyname:
        payload['appflowpolicylabel_appflowpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['appflowpolicylabel_appflowpolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['appflowpolicylabel_appflowpolicy_binding']['invoke_labelname'] = invoke_labelname

    if gotopriorityexpression:
        payload['appflowpolicylabel_appflowpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['appflowpolicylabel_appflowpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['appflowpolicylabel_appflowpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/appflowpolicylabel_appflowpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_appflowaction(name=None, collectors=None, clientsidemeasurements=None, pagetracking=None, webinsight=None,
                      securityinsight=None, videoanalytics=None, distributionalgorithm=None, metricslog=None,
                      transactionlog=None, comment=None, newname=None):
    '''
    Show the running configuration for the appflowaction config key.

    name(str): Filters results that only match the name field.

    collectors(list(str)): Filters results that only match the collectors field.

    clientsidemeasurements(str): Filters results that only match the clientsidemeasurements field.

    pagetracking(str): Filters results that only match the pagetracking field.

    webinsight(str): Filters results that only match the webinsight field.

    securityinsight(str): Filters results that only match the securityinsight field.

    videoanalytics(str): Filters results that only match the videoanalytics field.

    distributionalgorithm(str): Filters results that only match the distributionalgorithm field.

    metricslog(bool): Filters results that only match the metricslog field.

    transactionlog(str): Filters results that only match the transactionlog field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if collectors:
        search_filter.append(['collectors', collectors])

    if clientsidemeasurements:
        search_filter.append(['clientsidemeasurements', clientsidemeasurements])

    if pagetracking:
        search_filter.append(['pagetracking', pagetracking])

    if webinsight:
        search_filter.append(['webinsight', webinsight])

    if securityinsight:
        search_filter.append(['securityinsight', securityinsight])

    if videoanalytics:
        search_filter.append(['videoanalytics', videoanalytics])

    if distributionalgorithm:
        search_filter.append(['distributionalgorithm', distributionalgorithm])

    if metricslog:
        search_filter.append(['metricslog', metricslog])

    if transactionlog:
        search_filter.append(['transactionlog', transactionlog])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowaction')

    return response


def get_appflowcollector(name=None, ipaddress=None, port=None, netprofile=None, transport=None, newname=None):
    '''
    Show the running configuration for the appflowcollector config key.

    name(str): Filters results that only match the name field.

    ipaddress(str): Filters results that only match the ipaddress field.

    port(int): Filters results that only match the port field.

    netprofile(str): Filters results that only match the netprofile field.

    transport(str): Filters results that only match the transport field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowcollector

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if port:
        search_filter.append(['port', port])

    if netprofile:
        search_filter.append(['netprofile', netprofile])

    if transport:
        search_filter.append(['transport', transport])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowcollector{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowcollector')

    return response


def get_appflowglobal_appflowpolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                            gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None):
    '''
    Show the running configuration for the appflowglobal_appflowpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    ns_type(str): Filters results that only match the type field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowglobal_appflowpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if ns_type:
        search_filter.append(['type', ns_type])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowglobal_appflowpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowglobal_appflowpolicy_binding')

    return response


def get_appflowglobal_binding():
    '''
    Show the running configuration for the appflowglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowglobal_binding'), 'appflowglobal_binding')

    return response


def get_appflowparam():
    '''
    Show the running configuration for the appflowparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowparam'), 'appflowparam')

    return response


def get_appflowpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, newname=None):
    '''
    Show the running configuration for the appflowpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    undefaction(str): Filters results that only match the undefaction field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    if undefaction:
        search_filter.append(['undefaction', undefaction])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowpolicy')

    return response


def get_appflowpolicy_appflowglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the appflowpolicy_appflowglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowpolicy_appflowglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowpolicy_appflowglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowpolicy_appflowglobal_binding')

    return response


def get_appflowpolicy_appflowpolicylabel_binding(boundto=None, name=None):
    '''
    Show the running configuration for the appflowpolicy_appflowpolicylabel_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowpolicy_appflowpolicylabel_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowpolicy_appflowpolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowpolicy_appflowpolicylabel_binding')

    return response


def get_appflowpolicy_binding():
    '''
    Show the running configuration for the appflowpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowpolicy_binding'), 'appflowpolicy_binding')

    return response


def get_appflowpolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the appflowpolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowpolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowpolicy_csvserver_binding')

    return response


def get_appflowpolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the appflowpolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowpolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowpolicy_lbvserver_binding')

    return response


def get_appflowpolicy_vpnvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the appflowpolicy_vpnvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowpolicy_vpnvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowpolicy_vpnvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowpolicy_vpnvserver_binding')

    return response


def get_appflowpolicylabel(labelname=None, policylabeltype=None, newname=None):
    '''
    Show the running configuration for the appflowpolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    policylabeltype(str): Filters results that only match the policylabeltype field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowpolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if policylabeltype:
        search_filter.append(['policylabeltype', policylabeltype])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowpolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowpolicylabel')

    return response


def get_appflowpolicylabel_appflowpolicy_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                                 gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the appflowpolicylabel_appflowpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowpolicylabel_appflowpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if invoke_labelname:
        search_filter.append(['invoke_labelname', invoke_labelname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowpolicylabel_appflowpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appflowpolicylabel_appflowpolicy_binding')

    return response


def get_appflowpolicylabel_binding():
    '''
    Show the running configuration for the appflowpolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.get_appflowpolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appflowpolicylabel_binding'), 'appflowpolicylabel_binding')

    return response


def unset_appflowaction(name=None, collectors=None, clientsidemeasurements=None, pagetracking=None, webinsight=None,
                        securityinsight=None, videoanalytics=None, distributionalgorithm=None, metricslog=None,
                        transactionlog=None, comment=None, newname=None, save=False):
    '''
    Unsets values from the appflowaction configuration key.

    name(bool): Unsets the name value.

    collectors(bool): Unsets the collectors value.

    clientsidemeasurements(bool): Unsets the clientsidemeasurements value.

    pagetracking(bool): Unsets the pagetracking value.

    webinsight(bool): Unsets the webinsight value.

    securityinsight(bool): Unsets the securityinsight value.

    videoanalytics(bool): Unsets the videoanalytics value.

    distributionalgorithm(bool): Unsets the distributionalgorithm value.

    metricslog(bool): Unsets the metricslog value.

    transactionlog(bool): Unsets the transactionlog value.

    comment(bool): Unsets the comment value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.unset_appflowaction <args>

    '''

    result = {}

    payload = {'appflowaction': {}}

    if name:
        payload['appflowaction']['name'] = True

    if collectors:
        payload['appflowaction']['collectors'] = True

    if clientsidemeasurements:
        payload['appflowaction']['clientsidemeasurements'] = True

    if pagetracking:
        payload['appflowaction']['pagetracking'] = True

    if webinsight:
        payload['appflowaction']['webinsight'] = True

    if securityinsight:
        payload['appflowaction']['securityinsight'] = True

    if videoanalytics:
        payload['appflowaction']['videoanalytics'] = True

    if distributionalgorithm:
        payload['appflowaction']['distributionalgorithm'] = True

    if metricslog:
        payload['appflowaction']['metricslog'] = True

    if transactionlog:
        payload['appflowaction']['transactionlog'] = True

    if comment:
        payload['appflowaction']['comment'] = True

    if newname:
        payload['appflowaction']['newname'] = True

    execution = __proxy__['citrixns.post']('config/appflowaction?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_appflowcollector(name=None, ipaddress=None, port=None, netprofile=None, transport=None, newname=None,
                           save=False):
    '''
    Unsets values from the appflowcollector configuration key.

    name(bool): Unsets the name value.

    ipaddress(bool): Unsets the ipaddress value.

    port(bool): Unsets the port value.

    netprofile(bool): Unsets the netprofile value.

    transport(bool): Unsets the transport value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.unset_appflowcollector <args>

    '''

    result = {}

    payload = {'appflowcollector': {}}

    if name:
        payload['appflowcollector']['name'] = True

    if ipaddress:
        payload['appflowcollector']['ipaddress'] = True

    if port:
        payload['appflowcollector']['port'] = True

    if netprofile:
        payload['appflowcollector']['netprofile'] = True

    if transport:
        payload['appflowcollector']['transport'] = True

    if newname:
        payload['appflowcollector']['newname'] = True

    execution = __proxy__['citrixns.post']('config/appflowcollector?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_appflowparam(templaterefresh=None, appnamerefresh=None, flowrecordinterval=None,
                       securityinsightrecordinterval=None, udppmtu=None, httpurl=None, aaausername=None, httpcookie=None,
                       httpreferer=None, httpmethod=None, httphost=None, httpuseragent=None, clienttrafficonly=None,
                       httpcontenttype=None, httpauthorization=None, httpvia=None, httpxforwardedfor=None,
                       httplocation=None, httpsetcookie=None, httpsetcookie2=None, connectionchaining=None,
                       httpdomain=None, skipcacheredirectionhttptransaction=None, identifiername=None,
                       identifiersessionname=None, observationdomainid=None, observationdomainname=None,
                       subscriberawareness=None, subscriberidobfuscation=None, securityinsighttraffic=None,
                       cacheinsight=None, videoinsight=None, httpquerywithurl=None, urlcategory=None, save=False):
    '''
    Unsets values from the appflowparam configuration key.

    templaterefresh(bool): Unsets the templaterefresh value.

    appnamerefresh(bool): Unsets the appnamerefresh value.

    flowrecordinterval(bool): Unsets the flowrecordinterval value.

    securityinsightrecordinterval(bool): Unsets the securityinsightrecordinterval value.

    udppmtu(bool): Unsets the udppmtu value.

    httpurl(bool): Unsets the httpurl value.

    aaausername(bool): Unsets the aaausername value.

    httpcookie(bool): Unsets the httpcookie value.

    httpreferer(bool): Unsets the httpreferer value.

    httpmethod(bool): Unsets the httpmethod value.

    httphost(bool): Unsets the httphost value.

    httpuseragent(bool): Unsets the httpuseragent value.

    clienttrafficonly(bool): Unsets the clienttrafficonly value.

    httpcontenttype(bool): Unsets the httpcontenttype value.

    httpauthorization(bool): Unsets the httpauthorization value.

    httpvia(bool): Unsets the httpvia value.

    httpxforwardedfor(bool): Unsets the httpxforwardedfor value.

    httplocation(bool): Unsets the httplocation value.

    httpsetcookie(bool): Unsets the httpsetcookie value.

    httpsetcookie2(bool): Unsets the httpsetcookie2 value.

    connectionchaining(bool): Unsets the connectionchaining value.

    httpdomain(bool): Unsets the httpdomain value.

    skipcacheredirectionhttptransaction(bool): Unsets the skipcacheredirectionhttptransaction value.

    identifiername(bool): Unsets the identifiername value.

    identifiersessionname(bool): Unsets the identifiersessionname value.

    observationdomainid(bool): Unsets the observationdomainid value.

    observationdomainname(bool): Unsets the observationdomainname value.

    subscriberawareness(bool): Unsets the subscriberawareness value.

    subscriberidobfuscation(bool): Unsets the subscriberidobfuscation value.

    securityinsighttraffic(bool): Unsets the securityinsighttraffic value.

    cacheinsight(bool): Unsets the cacheinsight value.

    videoinsight(bool): Unsets the videoinsight value.

    httpquerywithurl(bool): Unsets the httpquerywithurl value.

    urlcategory(bool): Unsets the urlcategory value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.unset_appflowparam <args>

    '''

    result = {}

    payload = {'appflowparam': {}}

    if templaterefresh:
        payload['appflowparam']['templaterefresh'] = True

    if appnamerefresh:
        payload['appflowparam']['appnamerefresh'] = True

    if flowrecordinterval:
        payload['appflowparam']['flowrecordinterval'] = True

    if securityinsightrecordinterval:
        payload['appflowparam']['securityinsightrecordinterval'] = True

    if udppmtu:
        payload['appflowparam']['udppmtu'] = True

    if httpurl:
        payload['appflowparam']['httpurl'] = True

    if aaausername:
        payload['appflowparam']['aaausername'] = True

    if httpcookie:
        payload['appflowparam']['httpcookie'] = True

    if httpreferer:
        payload['appflowparam']['httpreferer'] = True

    if httpmethod:
        payload['appflowparam']['httpmethod'] = True

    if httphost:
        payload['appflowparam']['httphost'] = True

    if httpuseragent:
        payload['appflowparam']['httpuseragent'] = True

    if clienttrafficonly:
        payload['appflowparam']['clienttrafficonly'] = True

    if httpcontenttype:
        payload['appflowparam']['httpcontenttype'] = True

    if httpauthorization:
        payload['appflowparam']['httpauthorization'] = True

    if httpvia:
        payload['appflowparam']['httpvia'] = True

    if httpxforwardedfor:
        payload['appflowparam']['httpxforwardedfor'] = True

    if httplocation:
        payload['appflowparam']['httplocation'] = True

    if httpsetcookie:
        payload['appflowparam']['httpsetcookie'] = True

    if httpsetcookie2:
        payload['appflowparam']['httpsetcookie2'] = True

    if connectionchaining:
        payload['appflowparam']['connectionchaining'] = True

    if httpdomain:
        payload['appflowparam']['httpdomain'] = True

    if skipcacheredirectionhttptransaction:
        payload['appflowparam']['skipcacheredirectionhttptransaction'] = True

    if identifiername:
        payload['appflowparam']['identifiername'] = True

    if identifiersessionname:
        payload['appflowparam']['identifiersessionname'] = True

    if observationdomainid:
        payload['appflowparam']['observationdomainid'] = True

    if observationdomainname:
        payload['appflowparam']['observationdomainname'] = True

    if subscriberawareness:
        payload['appflowparam']['subscriberawareness'] = True

    if subscriberidobfuscation:
        payload['appflowparam']['subscriberidobfuscation'] = True

    if securityinsighttraffic:
        payload['appflowparam']['securityinsighttraffic'] = True

    if cacheinsight:
        payload['appflowparam']['cacheinsight'] = True

    if videoinsight:
        payload['appflowparam']['videoinsight'] = True

    if httpquerywithurl:
        payload['appflowparam']['httpquerywithurl'] = True

    if urlcategory:
        payload['appflowparam']['urlcategory'] = True

    execution = __proxy__['citrixns.post']('config/appflowparam?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_appflowpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, newname=None, save=False):
    '''
    Unsets values from the appflowpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    undefaction(bool): Unsets the undefaction value.

    comment(bool): Unsets the comment value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.unset_appflowpolicy <args>

    '''

    result = {}

    payload = {'appflowpolicy': {}}

    if name:
        payload['appflowpolicy']['name'] = True

    if rule:
        payload['appflowpolicy']['rule'] = True

    if action:
        payload['appflowpolicy']['action'] = True

    if undefaction:
        payload['appflowpolicy']['undefaction'] = True

    if comment:
        payload['appflowpolicy']['comment'] = True

    if newname:
        payload['appflowpolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/appflowpolicy?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_appflowaction(name=None, collectors=None, clientsidemeasurements=None, pagetracking=None, webinsight=None,
                         securityinsight=None, videoanalytics=None, distributionalgorithm=None, metricslog=None,
                         transactionlog=None, comment=None, newname=None, save=False):
    '''
    Update the running configuration for the appflowaction config key.

    name(str): Name for the action. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my appflow action" or my appflow
        action).

    collectors(list(str)): Name(s) of collector(s) to be associated with the AppFlow action. Minimum length = 1

    clientsidemeasurements(str): On enabling this option, the NetScaler will collect the time required to load and render the
        mainpage on the client. Default value: DISABLED Possible values = ENABLED, DISABLED

    pagetracking(str): On enabling this option, the NetScaler will start tracking the page for waterfall chart by inserting a
        NS_ESNS cookie in the response. Default value: DISABLED Possible values = ENABLED, DISABLED

    webinsight(str): On enabling this option, the netscaler will send the webinsight records to the configured collectors.
        Default value: ENABLED Possible values = ENABLED, DISABLED

    securityinsight(str): On enabling this option, the netscaler will send the security insight records to the configured
        collectors. Default value: DISABLED Possible values = ENABLED, DISABLED

    videoanalytics(str): On enabling this option, the netscaler will send the videoinsight records to the configured
        collectors. Default value: DISABLED Possible values = ENABLED, DISABLED

    distributionalgorithm(str): On enabling this option, the netscaler will distribute records among the collectors. Else,
        all records will be sent to all the collectors. Default value: DISABLED Possible values = ENABLED, DISABLED

    metricslog(bool): If only the stats records are to be exported, turn on this option.

    transactionlog(str): If over stats channel, transactions logs also need to be sent, set this option appropriately. By
        default netscaler sends anomalous transaction logs over metrics channel. This can be changed to ALL or NONE
        transactions. Default value: ANOMALOUS Possible values = ANOMALOUS, NONE, ALL

    comment(str): Any comments about this action. In the CLI, if including spaces between words, enclose the comment in
        quotation marks. (The quotation marks are not required in the configuration utility.). Maximum length = 256

    newname(str): New name for the AppFlow action. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.   The following requirement applies only to the NetScaler CLI: If the name includes one or
        more spaces, enclose the name in double or single quotation marks (for example, "my appflow action" or my appflow
        action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.update_appflowaction <args>

    '''

    result = {}

    payload = {'appflowaction': {}}

    if name:
        payload['appflowaction']['name'] = name

    if collectors:
        payload['appflowaction']['collectors'] = collectors

    if clientsidemeasurements:
        payload['appflowaction']['clientsidemeasurements'] = clientsidemeasurements

    if pagetracking:
        payload['appflowaction']['pagetracking'] = pagetracking

    if webinsight:
        payload['appflowaction']['webinsight'] = webinsight

    if securityinsight:
        payload['appflowaction']['securityinsight'] = securityinsight

    if videoanalytics:
        payload['appflowaction']['videoanalytics'] = videoanalytics

    if distributionalgorithm:
        payload['appflowaction']['distributionalgorithm'] = distributionalgorithm

    if metricslog:
        payload['appflowaction']['metricslog'] = metricslog

    if transactionlog:
        payload['appflowaction']['transactionlog'] = transactionlog

    if comment:
        payload['appflowaction']['comment'] = comment

    if newname:
        payload['appflowaction']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/appflowaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_appflowcollector(name=None, ipaddress=None, port=None, netprofile=None, transport=None, newname=None,
                            save=False):
    '''
    Update the running configuration for the appflowcollector config key.

    name(str): Name for the collector. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters.  Only four collectors can be configured.   The following requirement applies only to the NetScaler
        CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for example,
        "my appflow collector" or my appflow collector). Minimum length = 1 Maximum length = 127

    ipaddress(str): IPv4 address of the collector.

    port(int): Port on which the collector listens.

    netprofile(str): Netprofile to associate with the collector. The IP address defined in the profile is used as the source
        IP address for AppFlow traffic for this collector. If you do not set this parameter, the NetScaler IP (NSIP)
        address is used as the source IP address. Maximum length = 128

    transport(str): Type of collector: either logstream or ipfix. Default value: ipfix, Possible values = ipfix, logstream

    newname(str): New name for the collector. Must begin with an ASCII alphabetic or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at(@), equals (=), and
        hyphen (-) characters.   The following requirement applies only to the NetScaler CLI: If the name includes one or
        more spaces, enclose the name in double or single quotation marks (for example, "my appflow coll" or my appflow
        coll). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.update_appflowcollector <args>

    '''

    result = {}

    payload = {'appflowcollector': {}}

    if name:
        payload['appflowcollector']['name'] = name

    if ipaddress:
        payload['appflowcollector']['ipaddress'] = ipaddress

    if port:
        payload['appflowcollector']['port'] = port

    if netprofile:
        payload['appflowcollector']['netprofile'] = netprofile

    if transport:
        payload['appflowcollector']['transport'] = transport

    if newname:
        payload['appflowcollector']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/appflowcollector', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_appflowparam(templaterefresh=None, appnamerefresh=None, flowrecordinterval=None,
                        securityinsightrecordinterval=None, udppmtu=None, httpurl=None, aaausername=None,
                        httpcookie=None, httpreferer=None, httpmethod=None, httphost=None, httpuseragent=None,
                        clienttrafficonly=None, httpcontenttype=None, httpauthorization=None, httpvia=None,
                        httpxforwardedfor=None, httplocation=None, httpsetcookie=None, httpsetcookie2=None,
                        connectionchaining=None, httpdomain=None, skipcacheredirectionhttptransaction=None,
                        identifiername=None, identifiersessionname=None, observationdomainid=None,
                        observationdomainname=None, subscriberawareness=None, subscriberidobfuscation=None,
                        securityinsighttraffic=None, cacheinsight=None, videoinsight=None, httpquerywithurl=None,
                        urlcategory=None, save=False):
    '''
    Update the running configuration for the appflowparam config key.

    templaterefresh(int): Refresh interval, in seconds, at which to export the template data. Because data transmission is in
        UDP, the templates must be resent at regular intervals. Default value: 600 Minimum value = 60 Maximum value =
        3600

    appnamerefresh(int): Interval, in seconds, at which to send Appnames to the configured collectors. Appname refers to the
        name of an entity (virtual server, service, or service group) in the NetScaler appliance. Default value: 600
        Minimum value = 60 Maximum value = 3600

    flowrecordinterval(int): Interval, in seconds, at which to send flow records to the configured collectors. Default value:
        60 Minimum value = 60 Maximum value = 3600

    securityinsightrecordinterval(int): Interval, in seconds, at which to send security insight flow records to the
        configured collectors. Default value: 600 Minimum value = 60 Maximum value = 3600

    udppmtu(int): MTU, in bytes, for IPFIX UDP packets. Default value: 1472 Minimum value = 128 Maximum value = 1472

    httpurl(str): Include the http URL that the NetScaler appliance received from the client. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    aaausername(str): Enable AppFlow AAA Username logging. Default value: DISABLED Possible values = ENABLED, DISABLED

    httpcookie(str): Include the cookie that was in the HTTP request the appliance received from the client. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    httpreferer(str): Include the web page that was last visited by the client. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    httpmethod(str): Include the method that was specified in the HTTP request that the appliance received from the client.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    httphost(str): Include the host identified in the HTTP request that the appliance received from the client. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    httpuseragent(str): Include the client application through which the HTTP request was received by the NetScaler
        appliance. Default value: DISABLED Possible values = ENABLED, DISABLED

    clienttrafficonly(str): Generate AppFlow records for only the traffic from the client. Default value: NO Possible values
        = YES, NO

    httpcontenttype(str): Include the HTTP Content-Type header sent from the server to the client to determine the type of
        the content sent. Default value: DISABLED Possible values = ENABLED, DISABLED

    httpauthorization(str): Include the HTTP Authorization header information. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    httpvia(str): Include the httpVia header which contains the IP address of proxy server through which the client accessed
        the server. Default value: DISABLED Possible values = ENABLED, DISABLED

    httpxforwardedfor(str): Include the httpXForwardedFor header, which contains the original IP Address of the client using
        a proxy server to access the server. Default value: DISABLED Possible values = ENABLED, DISABLED

    httplocation(str): Include the HTTP location headers returned from the HTTP responses. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    httpsetcookie(str): Include the Set-cookie header sent from the server to the client in response to a HTTP request.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    httpsetcookie2(str): Include the Set-cookie header sent from the server to the client in response to a HTTP request.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    connectionchaining(str): Enable connection chaining so that the client server flows of a connection are linked. Also the
        connection chain ID is propagated across NetScalers, so that in a multi-hop environment the flows belonging to
        the same logical connection are linked. This id is also logged as part of appflow record. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    httpdomain(str): Include the http domain request to be exported. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    skipcacheredirectionhttptransaction(str): Skip Cache http transaction. This HTTP transaction is specific to Cache
        Redirection module. In Case of Cache Miss there will be another HTTP transaction initiated by the cache server.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    identifiername(str): Include the stream identifier name to be exported. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    identifiersessionname(str): Include the stream identifier session name to be exported. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    observationdomainid(int): An observation domain groups a set of NetScalers based on deployment: cluster, HA etc. A unique
        Observation Domain ID is required to be assigned to each such group. Default value: 0 Minimum value = 1000

    observationdomainname(str): Name of the Observation Domain defined by the observation domain ID. Maximum length = 127

    subscriberawareness(str): Enable this option for logging end user MSISDN in L4/L7 appflow records. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    subscriberidobfuscation(str): Enable this option for obfuscating MSISDN in L4/L7 appflow records. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    securityinsighttraffic(str): Flag to determine whether security insight traffic needs to be exported or not. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    cacheinsight(str): Flag to determine whether cache records need to be exported or not. If this flag is true and IC is
        enabled, cache records are exported instead of L7 HTTP records. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    videoinsight(str): Flag to determine whether video records need to be exported or not. If this flag is true and video
        optimization feature is enabled, video records are exported. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    httpquerywithurl(str): Include the HTTP query segment along with the URL that the NetScaler received from the client.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    urlcategory(str): Include the URL category record. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.update_appflowparam <args>

    '''

    result = {}

    payload = {'appflowparam': {}}

    if templaterefresh:
        payload['appflowparam']['templaterefresh'] = templaterefresh

    if appnamerefresh:
        payload['appflowparam']['appnamerefresh'] = appnamerefresh

    if flowrecordinterval:
        payload['appflowparam']['flowrecordinterval'] = flowrecordinterval

    if securityinsightrecordinterval:
        payload['appflowparam']['securityinsightrecordinterval'] = securityinsightrecordinterval

    if udppmtu:
        payload['appflowparam']['udppmtu'] = udppmtu

    if httpurl:
        payload['appflowparam']['httpurl'] = httpurl

    if aaausername:
        payload['appflowparam']['aaausername'] = aaausername

    if httpcookie:
        payload['appflowparam']['httpcookie'] = httpcookie

    if httpreferer:
        payload['appflowparam']['httpreferer'] = httpreferer

    if httpmethod:
        payload['appflowparam']['httpmethod'] = httpmethod

    if httphost:
        payload['appflowparam']['httphost'] = httphost

    if httpuseragent:
        payload['appflowparam']['httpuseragent'] = httpuseragent

    if clienttrafficonly:
        payload['appflowparam']['clienttrafficonly'] = clienttrafficonly

    if httpcontenttype:
        payload['appflowparam']['httpcontenttype'] = httpcontenttype

    if httpauthorization:
        payload['appflowparam']['httpauthorization'] = httpauthorization

    if httpvia:
        payload['appflowparam']['httpvia'] = httpvia

    if httpxforwardedfor:
        payload['appflowparam']['httpxforwardedfor'] = httpxforwardedfor

    if httplocation:
        payload['appflowparam']['httplocation'] = httplocation

    if httpsetcookie:
        payload['appflowparam']['httpsetcookie'] = httpsetcookie

    if httpsetcookie2:
        payload['appflowparam']['httpsetcookie2'] = httpsetcookie2

    if connectionchaining:
        payload['appflowparam']['connectionchaining'] = connectionchaining

    if httpdomain:
        payload['appflowparam']['httpdomain'] = httpdomain

    if skipcacheredirectionhttptransaction:
        payload['appflowparam']['skipcacheredirectionhttptransaction'] = skipcacheredirectionhttptransaction

    if identifiername:
        payload['appflowparam']['identifiername'] = identifiername

    if identifiersessionname:
        payload['appflowparam']['identifiersessionname'] = identifiersessionname

    if observationdomainid:
        payload['appflowparam']['observationdomainid'] = observationdomainid

    if observationdomainname:
        payload['appflowparam']['observationdomainname'] = observationdomainname

    if subscriberawareness:
        payload['appflowparam']['subscriberawareness'] = subscriberawareness

    if subscriberidobfuscation:
        payload['appflowparam']['subscriberidobfuscation'] = subscriberidobfuscation

    if securityinsighttraffic:
        payload['appflowparam']['securityinsighttraffic'] = securityinsighttraffic

    if cacheinsight:
        payload['appflowparam']['cacheinsight'] = cacheinsight

    if videoinsight:
        payload['appflowparam']['videoinsight'] = videoinsight

    if httpquerywithurl:
        payload['appflowparam']['httpquerywithurl'] = httpquerywithurl

    if urlcategory:
        payload['appflowparam']['urlcategory'] = urlcategory

    execution = __proxy__['citrixns.put']('config/appflowparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_appflowpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, newname=None, save=False):
    '''
    Update the running configuration for the appflowpolicy config key.

    name(str): Name for the policy. Must begin with an ASCII alphabetic or underscore (_) character, and must contain only
        ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters.   The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my appflow policy" or my appflow
        policy).

    rule(str): Expression or other value against which the traffic is evaluated. Must be a Boolean, default syntax
        expression. Note: Maximum length of a string literal in the expression is 255 characters. A longer string can be
        split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler CLI: * If the
        expression includes one or more spaces, enclose the entire expression in double quotation marks. * If the
        expression itself includes double quotation marks, escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    action(str): Name of the action to be associated with this policy.

    undefaction(str): Name of the appflow action to be associated with this policy when an undef event occurs.

    comment(str): Any comments about this policy.

    newname(str): New name for the policy. Must begin with an ASCII alphabetic or underscore (_)character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters.  The following requirement applies only to the NetScaler CLI: If the name includes one or more
        spaces, enclose the name in double or single quotation marks (for example, "my appflow policy" or my appflow
        policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appflow.update_appflowpolicy <args>

    '''

    result = {}

    payload = {'appflowpolicy': {}}

    if name:
        payload['appflowpolicy']['name'] = name

    if rule:
        payload['appflowpolicy']['rule'] = rule

    if action:
        payload['appflowpolicy']['action'] = action

    if undefaction:
        payload['appflowpolicy']['undefaction'] = undefaction

    if comment:
        payload['appflowpolicy']['comment'] = comment

    if newname:
        payload['appflowpolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/appflowpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
