# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the responder key.

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

__virtualname__ = 'responder'


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

    return False, 'The responder execution module can only be loaded for citrixns proxy minions.'


def add_responderaction(name=None, ns_type=None, target=None, htmlpage=None, bypasssafetycheck=None, comment=None,
                        responsestatuscode=None, reasonphrase=None, newname=None, save=False):
    '''
    Add a new responderaction to the running configuration.

    name(str): Name for the responder action. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon (:),
        and underscore characters. Can be changed after the responder policy is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my responder action" or my responder action).

    ns_type(str): Type of responder action. Available settings function as follows: * respondwith ;lt;target;gt; - Respond to
        the request with the expression specified as the target. * respondwithhtmlpage - Respond to the request with the
        uploaded HTML page object specified as the target. * redirect - Redirect the request to the URL specified as the
        target. * sqlresponse_ok - Send an SQL OK response. * sqlresponse_error - Send an SQL ERROR response. Possible
        values = noop, respondwith, redirect, respondwithhtmlpage, sqlresponse_ok, sqlresponse_error

    target(str): Expression specifying what to respond with. Typically a URL for redirect policies or a default-syntax
        expression. In addition to NetScaler default-syntax expressions that refer to information in the request, a
        stringbuilder expression can contain text and HTML, and simple escape codes that define new lines and paragraphs.
        Enclose each stringbuilder expression element (either a NetScaler default-syntax expression or a string) in
        double quotation marks. Use the plus (+) character to join the elements.   Examples: 1) Respondwith expression
        that sends an HTTP 1.1 200 OK response: "HTTP/1.1 200 OK\\r\\n\\r\\n"  2) Redirect expression that redirects user
        to the specified web host and appends the request URL to the redirect. "http://backupsite2.com" + HTTP.REQ.URL
        3) Respondwith expression that sends an HTTP 1.1 404 Not Found response with the request URL included in the
        response: "HTTP/1.1 404 Not Found\\r\\n\\r\\n"+ "HTTP.REQ.URL.HTTP_URL_SAFE" + "does not exist on the web
        server."  The following requirement applies only to the NetScaler CLI: Enclose the entire expression in single
        quotation marks. (NetScaler default expression elements should be included inside the single quotation marks for
        the entire expression, but do not need to be enclosed in double quotation marks.).

    htmlpage(str): For respondwithhtmlpage policies, name of the HTML page object to use as the response. You must first
        import the page object. Minimum length = 1

    bypasssafetycheck(str): Bypass the safety check, allowing potentially unsafe expressions. An unsafe expression in a
        response is one that contains references to request elements that might not be present in all requests. If a
        response refers to a missing request element, an empty string is used instead. Default value: NO Possible values
        = YES, NO

    comment(str): Comment. Any type of information about this responder action.

    responsestatuscode(int): HTTP response status code, for example 200, 302, 404, etc. The default value for the redirect
        action type is 302 and for respondwithhtmlpage is 200. Minimum value = 100 Maximum value = 599

    reasonphrase(str): Expression specifying the reason phrase of the HTTP response. The reason phrase may be a string
        literal with quotes or a PI expression. For example: "Invalid URL: " + HTTP.REQ.URL. Minimum length = 1

    newname(str): New name for the responder action. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my responder
        action" or my responder action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.add_responderaction <args>

    '''

    result = {}

    payload = {'responderaction': {}}

    if name:
        payload['responderaction']['name'] = name

    if ns_type:
        payload['responderaction']['type'] = ns_type

    if target:
        payload['responderaction']['target'] = target

    if htmlpage:
        payload['responderaction']['htmlpage'] = htmlpage

    if bypasssafetycheck:
        payload['responderaction']['bypasssafetycheck'] = bypasssafetycheck

    if comment:
        payload['responderaction']['comment'] = comment

    if responsestatuscode:
        payload['responderaction']['responsestatuscode'] = responsestatuscode

    if reasonphrase:
        payload['responderaction']['reasonphrase'] = reasonphrase

    if newname:
        payload['responderaction']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/responderaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_responderglobal_responderpolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                                gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None,
                                                save=False):
    '''
    Add a new responderglobal_responderpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): Name of the responder policy.

    labelname(str): Name of the policy label to invoke. If the current policy evaluates to TRUE, the invoke parameter is set,
        and Label Type is policylabel.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy
        label, and then forward the request to the specified virtual server or evaluate the specified policy label.

    ns_type(str): Specifies the bind point whose policies you want to display. Available settings function as follows: *
        REQ_OVERRIDE - Request override. Binds the policy to the priority request queue. * REQ_DEFAULT - Binds the policy
        to the default request queue. * OTHERTCP_REQ_OVERRIDE - Binds the policy to the non-HTTP TCP priority request
        queue. * OTHERTCP_REQ_DEFAULT - Binds the policy to the non-HTTP TCP default request queue.. *
        SIPUDP_REQ_OVERRIDE - Binds the policy to the SIP UDP priority response queue.. * SIPUDP_REQ_DEFAULT - Binds the
        policy to the SIP UDP default response queue. * RADIUS_REQ_OVERRIDE - Binds the policy to the RADIUS priority
        response queue.. * RADIUS_REQ_DEFAULT - Binds the policy to the RADIUS default response queue. *
        MSSQL_REQ_OVERRIDE - Binds the policy to the Microsoft SQL priority response queue.. * MSSQL_REQ_DEFAULT - Binds
        the policy to the Microsoft SQL default response queue. * MYSQL_REQ_OVERRIDE - Binds the policy to the MySQL
        priority response queue. * MYSQL_REQ_DEFAULT - Binds the policy to the MySQL default response queue. Possible
        values = REQ_OVERRIDE, REQ_DEFAULT, OVERRIDE, DEFAULT, OTHERTCP_REQ_OVERRIDE, OTHERTCP_REQ_DEFAULT,
        SIPUDP_REQ_OVERRIDE, SIPUDP_REQ_DEFAULT, SIPTCP_REQ_OVERRIDE, SIPTCP_REQ_DEFAULT, MSSQL_REQ_OVERRIDE,
        MSSQL_REQ_DEFAULT, MYSQL_REQ_OVERRIDE, MYSQL_REQ_DEFAULT, NAT_REQ_OVERRIDE, NAT_REQ_DEFAULT,
        DIAMETER_REQ_OVERRIDE, DIAMETER_REQ_DEFAULT, RADIUS_REQ_OVERRIDE, RADIUS_REQ_DEFAULT, DNS_REQ_OVERRIDE,
        DNS_REQ_DEFAULT

    labeltype(str): Type of invocation, Available settings function as follows: * vserver - Forward the request to the
        specified virtual server. * policylabel - Invoke the specified policy label. Possible values = vserver,
        policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.add_responderglobal_responderpolicy_binding <args>

    '''

    result = {}

    payload = {'responderglobal_responderpolicy_binding': {}}

    if priority:
        payload['responderglobal_responderpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['responderglobal_responderpolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['responderglobal_responderpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['responderglobal_responderpolicy_binding']['labelname'] = labelname

    if gotopriorityexpression:
        payload['responderglobal_responderpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['responderglobal_responderpolicy_binding']['invoke'] = invoke

    if ns_type:
        payload['responderglobal_responderpolicy_binding']['type'] = ns_type

    if labeltype:
        payload['responderglobal_responderpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/responderglobal_responderpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_responderpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                        appflowaction=None, newname=None, save=False):
    '''
    Add a new responderpolicy to the running configuration.

    name(str): Name for the responder policy. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Can be changed after the responder policy is added.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my responder policy" or my responder policy).

    rule(str): Default syntax expression that the policy uses to determine whether to respond to the specified request.

    action(str): Name of the responder action to perform if the request matches this responder policy. There are also some
        built-in actions which can be used. These are: * NOOP - Send the request to the protected server instead of
        responding to it. * RESET - Reset the client connection by closing it. The client program, such as a browser,
        will handle this and may inform the user. The client may then resend the request if desired. * DROP - Drop the
        request without sending a response to the user.

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any type of information about this responder policy.

    logaction(str): Name of the messagelog action to use for requests that match this policy.

    appflowaction(str): AppFlow action to invoke for requests that match this policy.

    newname(str): New name for the responder policy. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.   The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my responder
        policy" or my responder policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.add_responderpolicy <args>

    '''

    result = {}

    payload = {'responderpolicy': {}}

    if name:
        payload['responderpolicy']['name'] = name

    if rule:
        payload['responderpolicy']['rule'] = rule

    if action:
        payload['responderpolicy']['action'] = action

    if undefaction:
        payload['responderpolicy']['undefaction'] = undefaction

    if comment:
        payload['responderpolicy']['comment'] = comment

    if logaction:
        payload['responderpolicy']['logaction'] = logaction

    if appflowaction:
        payload['responderpolicy']['appflowaction'] = appflowaction

    if newname:
        payload['responderpolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/responderpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_responderpolicylabel(labelname=None, policylabeltype=None, comment=None, newname=None, save=False):
    '''
    Add a new responderpolicylabel to the running configuration.

    labelname(str): Name for the responder policy label. Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the responder policy label is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my responder policy label" or my responder policy label).

    policylabeltype(str): Type of responses sent by the policies bound to this policy label. Types are: * HTTP - HTTP
        responses.  * OTHERTCP - NON-HTTP TCP responses. * SIP_UDP - SIP responses. * RADIUS - RADIUS responses. * MYSQL
        - SQL responses in MySQL format. * MSSQL - SQL responses in Microsoft SQL format. * NAT - NAT response. Default
        value: HTTP Possible values = HTTP, OTHERTCP, SIP_UDP, SIP_TCP, MYSQL, MSSQL, NAT, DIAMETER, RADIUS, DNS

    comment(str): Any comments to preserve information about this responder policy label.

    newname(str): New name for the responder policy label. Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.add_responderpolicylabel <args>

    '''

    result = {}

    payload = {'responderpolicylabel': {}}

    if labelname:
        payload['responderpolicylabel']['labelname'] = labelname

    if policylabeltype:
        payload['responderpolicylabel']['policylabeltype'] = policylabeltype

    if comment:
        payload['responderpolicylabel']['comment'] = comment

    if newname:
        payload['responderpolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/responderpolicylabel', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_responderpolicylabel_responderpolicy_binding(priority=None, policyname=None, labelname=None,
                                                     invoke_labelname=None, gotopriorityexpression=None, invoke=None,
                                                     labeltype=None, save=False):
    '''
    Add a new responderpolicylabel_responderpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    policyname(str): Name of the responder policy.

    labelname(str): Name of the responder policy label to which to bind the policy.

    invoke_labelname(str): * If labelType is policylabel, name of the policy label to invoke. * If labelType is reqvserver or
        resvserver, name of the virtual server.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy label
        and evaluate the specified policy label.

    labeltype(str): Type of policy label to invoke. Available settings function as follows: * vserver - Invoke an unnamed
        policy label associated with a virtual server. * policylabel - Invoke a user-defined policy label. Possible
        values = vserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.add_responderpolicylabel_responderpolicy_binding <args>

    '''

    result = {}

    payload = {'responderpolicylabel_responderpolicy_binding': {}}

    if priority:
        payload['responderpolicylabel_responderpolicy_binding']['priority'] = priority

    if policyname:
        payload['responderpolicylabel_responderpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['responderpolicylabel_responderpolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['responderpolicylabel_responderpolicy_binding']['invoke_labelname'] = invoke_labelname

    if gotopriorityexpression:
        payload['responderpolicylabel_responderpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['responderpolicylabel_responderpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['responderpolicylabel_responderpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/responderpolicylabel_responderpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_responderaction(name=None, ns_type=None, target=None, htmlpage=None, bypasssafetycheck=None, comment=None,
                        responsestatuscode=None, reasonphrase=None, newname=None):
    '''
    Show the running configuration for the responderaction config key.

    name(str): Filters results that only match the name field.

    ns_type(str): Filters results that only match the type field.

    target(str): Filters results that only match the target field.

    htmlpage(str): Filters results that only match the htmlpage field.

    bypasssafetycheck(str): Filters results that only match the bypasssafetycheck field.

    comment(str): Filters results that only match the comment field.

    responsestatuscode(int): Filters results that only match the responsestatuscode field.

    reasonphrase(str): Filters results that only match the reasonphrase field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ns_type:
        search_filter.append(['type', ns_type])

    if target:
        search_filter.append(['target', target])

    if htmlpage:
        search_filter.append(['htmlpage', htmlpage])

    if bypasssafetycheck:
        search_filter.append(['bypasssafetycheck', bypasssafetycheck])

    if comment:
        search_filter.append(['comment', comment])

    if responsestatuscode:
        search_filter.append(['responsestatuscode', responsestatuscode])

    if reasonphrase:
        search_filter.append(['reasonphrase', reasonphrase])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderaction')

    return response


def get_responderglobal_binding():
    '''
    Show the running configuration for the responderglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderglobal_binding'), 'responderglobal_binding')

    return response


def get_responderglobal_responderpolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                                gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None):
    '''
    Show the running configuration for the responderglobal_responderpolicy_binding config key.

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

    salt '*' responder.get_responderglobal_responderpolicy_binding

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
            __proxy__['citrixns.get']('config/responderglobal_responderpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderglobal_responderpolicy_binding')

    return response


def get_responderhtmlpage():
    '''
    Show the running configuration for the responderhtmlpage config key.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderhtmlpage

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderhtmlpage'), 'responderhtmlpage')

    return response


def get_responderparam():
    '''
    Show the running configuration for the responderparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderparam'), 'responderparam')

    return response


def get_responderpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                        appflowaction=None, newname=None):
    '''
    Show the running configuration for the responderpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    undefaction(str): Filters results that only match the undefaction field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    appflowaction(str): Filters results that only match the appflowaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicy

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

    if logaction:
        search_filter.append(['logaction', logaction])

    if appflowaction:
        search_filter.append(['appflowaction', appflowaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderpolicy')

    return response


def get_responderpolicy_binding():
    '''
    Show the running configuration for the responderpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderpolicy_binding'), 'responderpolicy_binding')

    return response


def get_responderpolicy_crvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the responderpolicy_crvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicy_crvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderpolicy_crvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderpolicy_crvserver_binding')

    return response


def get_responderpolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the responderpolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderpolicy_csvserver_binding')

    return response


def get_responderpolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the responderpolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderpolicy_lbvserver_binding')

    return response


def get_responderpolicy_responderglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the responderpolicy_responderglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicy_responderglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderpolicy_responderglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderpolicy_responderglobal_binding')

    return response


def get_responderpolicy_responderpolicylabel_binding(boundto=None, name=None):
    '''
    Show the running configuration for the responderpolicy_responderpolicylabel_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicy_responderpolicylabel_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderpolicy_responderpolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderpolicy_responderpolicylabel_binding')

    return response


def get_responderpolicylabel(labelname=None, policylabeltype=None, comment=None, newname=None):
    '''
    Show the running configuration for the responderpolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    policylabeltype(str): Filters results that only match the policylabeltype field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if policylabeltype:
        search_filter.append(['policylabeltype', policylabeltype])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderpolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderpolicylabel')

    return response


def get_responderpolicylabel_binding():
    '''
    Show the running configuration for the responderpolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/responderpolicylabel_binding'), 'responderpolicylabel_binding')

    return response


def get_responderpolicylabel_policybinding_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                                   gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the responderpolicylabel_policybinding_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicylabel_policybinding_binding

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
            __proxy__['citrixns.get']('config/responderpolicylabel_policybinding_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderpolicylabel_policybinding_binding')

    return response


def get_responderpolicylabel_responderpolicy_binding(priority=None, policyname=None, labelname=None,
                                                     invoke_labelname=None, gotopriorityexpression=None, invoke=None,
                                                     labeltype=None):
    '''
    Show the running configuration for the responderpolicylabel_responderpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.get_responderpolicylabel_responderpolicy_binding

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
            __proxy__['citrixns.get']('config/responderpolicylabel_responderpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'responderpolicylabel_responderpolicy_binding')

    return response


def unset_responderaction(name=None, ns_type=None, target=None, htmlpage=None, bypasssafetycheck=None, comment=None,
                          responsestatuscode=None, reasonphrase=None, newname=None, save=False):
    '''
    Unsets values from the responderaction configuration key.

    name(bool): Unsets the name value.

    ns_type(bool): Unsets the ns_type value.

    target(bool): Unsets the target value.

    htmlpage(bool): Unsets the htmlpage value.

    bypasssafetycheck(bool): Unsets the bypasssafetycheck value.

    comment(bool): Unsets the comment value.

    responsestatuscode(bool): Unsets the responsestatuscode value.

    reasonphrase(bool): Unsets the reasonphrase value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.unset_responderaction <args>

    '''

    result = {}

    payload = {'responderaction': {}}

    if name:
        payload['responderaction']['name'] = True

    if ns_type:
        payload['responderaction']['type'] = True

    if target:
        payload['responderaction']['target'] = True

    if htmlpage:
        payload['responderaction']['htmlpage'] = True

    if bypasssafetycheck:
        payload['responderaction']['bypasssafetycheck'] = True

    if comment:
        payload['responderaction']['comment'] = True

    if responsestatuscode:
        payload['responderaction']['responsestatuscode'] = True

    if reasonphrase:
        payload['responderaction']['reasonphrase'] = True

    if newname:
        payload['responderaction']['newname'] = True

    execution = __proxy__['citrixns.post']('config/responderaction?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_responderparam(undefaction=None, save=False):
    '''
    Unsets values from the responderparam configuration key.

    undefaction(bool): Unsets the undefaction value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.unset_responderparam <args>

    '''

    result = {}

    payload = {'responderparam': {}}

    if undefaction:
        payload['responderparam']['undefaction'] = True

    execution = __proxy__['citrixns.post']('config/responderparam?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_responderpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                          appflowaction=None, newname=None, save=False):
    '''
    Unsets values from the responderpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    undefaction(bool): Unsets the undefaction value.

    comment(bool): Unsets the comment value.

    logaction(bool): Unsets the logaction value.

    appflowaction(bool): Unsets the appflowaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.unset_responderpolicy <args>

    '''

    result = {}

    payload = {'responderpolicy': {}}

    if name:
        payload['responderpolicy']['name'] = True

    if rule:
        payload['responderpolicy']['rule'] = True

    if action:
        payload['responderpolicy']['action'] = True

    if undefaction:
        payload['responderpolicy']['undefaction'] = True

    if comment:
        payload['responderpolicy']['comment'] = True

    if logaction:
        payload['responderpolicy']['logaction'] = True

    if appflowaction:
        payload['responderpolicy']['appflowaction'] = True

    if newname:
        payload['responderpolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/responderpolicy?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_responderaction(name=None, ns_type=None, target=None, htmlpage=None, bypasssafetycheck=None, comment=None,
                           responsestatuscode=None, reasonphrase=None, newname=None, save=False):
    '''
    Update the running configuration for the responderaction config key.

    name(str): Name for the responder action. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon (:),
        and underscore characters. Can be changed after the responder policy is added.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my responder action" or my responder action).

    ns_type(str): Type of responder action. Available settings function as follows: * respondwith ;lt;target;gt; - Respond to
        the request with the expression specified as the target. * respondwithhtmlpage - Respond to the request with the
        uploaded HTML page object specified as the target. * redirect - Redirect the request to the URL specified as the
        target. * sqlresponse_ok - Send an SQL OK response. * sqlresponse_error - Send an SQL ERROR response. Possible
        values = noop, respondwith, redirect, respondwithhtmlpage, sqlresponse_ok, sqlresponse_error

    target(str): Expression specifying what to respond with. Typically a URL for redirect policies or a default-syntax
        expression. In addition to NetScaler default-syntax expressions that refer to information in the request, a
        stringbuilder expression can contain text and HTML, and simple escape codes that define new lines and paragraphs.
        Enclose each stringbuilder expression element (either a NetScaler default-syntax expression or a string) in
        double quotation marks. Use the plus (+) character to join the elements.   Examples: 1) Respondwith expression
        that sends an HTTP 1.1 200 OK response: "HTTP/1.1 200 OK\\r\\n\\r\\n"  2) Redirect expression that redirects user
        to the specified web host and appends the request URL to the redirect. "http://backupsite2.com" + HTTP.REQ.URL
        3) Respondwith expression that sends an HTTP 1.1 404 Not Found response with the request URL included in the
        response: "HTTP/1.1 404 Not Found\\r\\n\\r\\n"+ "HTTP.REQ.URL.HTTP_URL_SAFE" + "does not exist on the web
        server."  The following requirement applies only to the NetScaler CLI: Enclose the entire expression in single
        quotation marks. (NetScaler default expression elements should be included inside the single quotation marks for
        the entire expression, but do not need to be enclosed in double quotation marks.).

    htmlpage(str): For respondwithhtmlpage policies, name of the HTML page object to use as the response. You must first
        import the page object. Minimum length = 1

    bypasssafetycheck(str): Bypass the safety check, allowing potentially unsafe expressions. An unsafe expression in a
        response is one that contains references to request elements that might not be present in all requests. If a
        response refers to a missing request element, an empty string is used instead. Default value: NO Possible values
        = YES, NO

    comment(str): Comment. Any type of information about this responder action.

    responsestatuscode(int): HTTP response status code, for example 200, 302, 404, etc. The default value for the redirect
        action type is 302 and for respondwithhtmlpage is 200. Minimum value = 100 Maximum value = 599

    reasonphrase(str): Expression specifying the reason phrase of the HTTP response. The reason phrase may be a string
        literal with quotes or a PI expression. For example: "Invalid URL: " + HTTP.REQ.URL. Minimum length = 1

    newname(str): New name for the responder action. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my responder
        action" or my responder action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.update_responderaction <args>

    '''

    result = {}

    payload = {'responderaction': {}}

    if name:
        payload['responderaction']['name'] = name

    if ns_type:
        payload['responderaction']['type'] = ns_type

    if target:
        payload['responderaction']['target'] = target

    if htmlpage:
        payload['responderaction']['htmlpage'] = htmlpage

    if bypasssafetycheck:
        payload['responderaction']['bypasssafetycheck'] = bypasssafetycheck

    if comment:
        payload['responderaction']['comment'] = comment

    if responsestatuscode:
        payload['responderaction']['responsestatuscode'] = responsestatuscode

    if reasonphrase:
        payload['responderaction']['reasonphrase'] = reasonphrase

    if newname:
        payload['responderaction']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/responderaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_responderparam(undefaction=None, save=False):
    '''
    Update the running configuration for the responderparam config key.

    undefaction(str): Action to perform when policy evaluation creates an UNDEF condition. Available settings function as
        follows: * NOOP - Send the request to the protected server. * RESET - Reset the request and notify the users
        browser, so that the user can resend the request. * DROP - Drop the request without sending a response to the
        user. Default value: "NOOP"

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.update_responderparam <args>

    '''

    result = {}

    payload = {'responderparam': {}}

    if undefaction:
        payload['responderparam']['undefaction'] = undefaction

    execution = __proxy__['citrixns.put']('config/responderparam', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_responderpolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None,
                           appflowaction=None, newname=None, save=False):
    '''
    Update the running configuration for the responderpolicy config key.

    name(str): Name for the responder policy. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Can be changed after the responder policy is added.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my responder policy" or my responder policy).

    rule(str): Default syntax expression that the policy uses to determine whether to respond to the specified request.

    action(str): Name of the responder action to perform if the request matches this responder policy. There are also some
        built-in actions which can be used. These are: * NOOP - Send the request to the protected server instead of
        responding to it. * RESET - Reset the client connection by closing it. The client program, such as a browser,
        will handle this and may inform the user. The client may then resend the request if desired. * DROP - Drop the
        request without sending a response to the user.

    undefaction(str): Action to perform if the result of policy evaluation is undefined (UNDEF). An UNDEF event indicates an
        internal error condition. Only the above built-in actions can be used.

    comment(str): Any type of information about this responder policy.

    logaction(str): Name of the messagelog action to use for requests that match this policy.

    appflowaction(str): AppFlow action to invoke for requests that match this policy.

    newname(str): New name for the responder policy. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.   The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, "my responder
        policy" or my responder policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' responder.update_responderpolicy <args>

    '''

    result = {}

    payload = {'responderpolicy': {}}

    if name:
        payload['responderpolicy']['name'] = name

    if rule:
        payload['responderpolicy']['rule'] = rule

    if action:
        payload['responderpolicy']['action'] = action

    if undefaction:
        payload['responderpolicy']['undefaction'] = undefaction

    if comment:
        payload['responderpolicy']['comment'] = comment

    if logaction:
        payload['responderpolicy']['logaction'] = logaction

    if appflowaction:
        payload['responderpolicy']['appflowaction'] = appflowaction

    if newname:
        payload['responderpolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/responderpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
