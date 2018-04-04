# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the transform key.

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

__virtualname__ = 'transform'


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

    return False, 'The transform execution module can only be loaded for citrixns proxy minions.'


def add_transformaction(name=None, profilename=None, priority=None, state=None, requrlfrom=None, requrlinto=None,
                        resurlfrom=None, resurlinto=None, cookiedomainfrom=None, cookiedomaininto=None, comment=None,
                        save=False):
    '''
    Add a new transformaction to the running configuration.

    name(str): Name for the URL transformation action. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the URL Transformation action is added.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, ?my transform action? or ?my transform action). Minimum
        length = 1

    profilename(str): Name of the URL Transformation profile with which to associate this action. Minimum length = 1

    priority(int): Positive integer specifying the priority of the action within the profile. A lower number specifies a
        higher priority. Must be unique within the list of actions bound to the profile. Policies are evaluated in the
        order of their priority numbers, and the first policy that matches is applied. Minimum value = 1 Maximum value =
        2147483647

    state(str): Enable or disable this action. Default value: ENABLED Possible values = ENABLED, DISABLED

    requrlfrom(str): PCRE-format regular expression that describes the request URL pattern to be transformed. Minimum length
        = 1

    requrlinto(str): PCRE-format regular expression that describes the transformation to be performed on URLs that match the
        reqUrlFrom pattern. Minimum length = 1

    resurlfrom(str): PCRE-format regular expression that describes the response URL pattern to be transformed. Minimum length
        = 1

    resurlinto(str): PCRE-format regular expression that describes the transformation to be performed on URLs that match the
        resUrlFrom pattern. Minimum length = 1

    cookiedomainfrom(str): Pattern that matches the domain to be transformed in Set-Cookie headers. Minimum length = 1

    cookiedomaininto(str): PCRE-format regular expression that describes the transformation to be performed on cookie domains
        that match the cookieDomainFrom pattern.  NOTE: The cookie domain to be transformed is extracted from the
        request. Minimum length = 1

    comment(str): Any comments to preserve information about this URL Transformation action.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.add_transformaction <args>

    '''

    result = {}

    payload = {'transformaction': {}}

    if name:
        payload['transformaction']['name'] = name

    if profilename:
        payload['transformaction']['profilename'] = profilename

    if priority:
        payload['transformaction']['priority'] = priority

    if state:
        payload['transformaction']['state'] = state

    if requrlfrom:
        payload['transformaction']['requrlfrom'] = requrlfrom

    if requrlinto:
        payload['transformaction']['requrlinto'] = requrlinto

    if resurlfrom:
        payload['transformaction']['resurlfrom'] = resurlfrom

    if resurlinto:
        payload['transformaction']['resurlinto'] = resurlinto

    if cookiedomainfrom:
        payload['transformaction']['cookiedomainfrom'] = cookiedomainfrom

    if cookiedomaininto:
        payload['transformaction']['cookiedomaininto'] = cookiedomaininto

    if comment:
        payload['transformaction']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/transformaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_transformglobal_transformpolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                                gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None,
                                                save=False):
    '''
    Add a new transformglobal_transformpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): Name of the transform policy.

    labelname(str): Name of the policy label to invoke if the current policy evaluates to TRUE, the invoke parameter is set,
        and the label type is Policy Label.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy
        label, and then forwards the request or response to the specified virtual server or evaluates the specified
        policy label.

    ns_type(str): Specifies the bind point to which to bind the policy. Available settings function as follows: *
        REQ_OVERRIDE. Request override. Binds the policy to the priority request queue. * REQ_DEFAULT. Binds the policy
        to the default request queue. Possible values = REQ_OVERRIDE, REQ_DEFAULT

    labeltype(str): Type of invocation. Available settings function as follows: * reqvserver - Send the request to the
        specified request virtual server. * resvserver - Send the response to the specified response virtual server. *
        policylabel - Invoke the specified policy label. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.add_transformglobal_transformpolicy_binding <args>

    '''

    result = {}

    payload = {'transformglobal_transformpolicy_binding': {}}

    if priority:
        payload['transformglobal_transformpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['transformglobal_transformpolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['transformglobal_transformpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['transformglobal_transformpolicy_binding']['labelname'] = labelname

    if gotopriorityexpression:
        payload['transformglobal_transformpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['transformglobal_transformpolicy_binding']['invoke'] = invoke

    if ns_type:
        payload['transformglobal_transformpolicy_binding']['type'] = ns_type

    if labeltype:
        payload['transformglobal_transformpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/transformglobal_transformpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_transformpolicy(name=None, rule=None, profilename=None, comment=None, logaction=None, newname=None, save=False):
    '''
    Add a new transformpolicy to the running configuration.

    name(str): Name for the URL Transformation policy. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Can be changed after the URL Transformation policy is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, ?my transform policy? or ?my transform policy). Minimum length =
        1

    rule(str): Expression, or name of a named expression, against which to evaluate traffic. Can be written in either default
        or classic syntax. Maximum length of a string literal in the expression is 255 characters. A longer string can be
        split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler CLI: * If the
        expression includes blank spaces, the entire expression must be enclosed in double quotation marks. * If the
        expression itself includes double quotation marks, you must escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    profilename(str): Name of the URL Transformation profile to use to transform requests and responses that match the
        policy. Minimum length = 1

    comment(str): Any comments to preserve information about this URL Transformation policy.

    logaction(str): Log server to use to log connections that match this policy.

    newname(str): New name for the policy. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, ?my transform
        policy? or ?my transform policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.add_transformpolicy <args>

    '''

    result = {}

    payload = {'transformpolicy': {}}

    if name:
        payload['transformpolicy']['name'] = name

    if rule:
        payload['transformpolicy']['rule'] = rule

    if profilename:
        payload['transformpolicy']['profilename'] = profilename

    if comment:
        payload['transformpolicy']['comment'] = comment

    if logaction:
        payload['transformpolicy']['logaction'] = logaction

    if newname:
        payload['transformpolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/transformpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_transformpolicylabel(labelname=None, policylabeltype=None, newname=None, save=False):
    '''
    Add a new transformpolicylabel to the running configuration.

    labelname(str): Name for the policy label. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters. Can be changed after the URL Transformation policy label is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, ?my transform policylabel? or ?my transform policylabel).

    policylabeltype(str): Types of transformations allowed by the policies bound to the label. For URL transformation, always
        http_req (HTTP Request). Possible values = http_req

    newname(str): New name for the policy label. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, ?my transform
        policylabel? or ?my transform policylabel). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.add_transformpolicylabel <args>

    '''

    result = {}

    payload = {'transformpolicylabel': {}}

    if labelname:
        payload['transformpolicylabel']['labelname'] = labelname

    if policylabeltype:
        payload['transformpolicylabel']['policylabeltype'] = policylabeltype

    if newname:
        payload['transformpolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/transformpolicylabel', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_transformpolicylabel_transformpolicy_binding(priority=None, policyname=None, labelname=None,
                                                     invoke_labelname=None, gotopriorityexpression=None, invoke=None,
                                                     labeltype=None, save=False):
    '''
    Add a new transformpolicylabel_transformpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    policyname(str): Name of the URL Transformation policy to bind to the policy label.

    labelname(str): Name of the URL Transformation policy label to which to bind the policy.

    invoke_labelname(str): Name of the policy label.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy
        label, and then forward the request to the specified virtual server or evaluate the specified policy label.

    labeltype(str): Type of invocation. Available settings function as follows: * reqvserver - Forward the request to the
        specified request virtual server. * policylabel - Invoke the specified policy label. Possible values =
        reqvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.add_transformpolicylabel_transformpolicy_binding <args>

    '''

    result = {}

    payload = {'transformpolicylabel_transformpolicy_binding': {}}

    if priority:
        payload['transformpolicylabel_transformpolicy_binding']['priority'] = priority

    if policyname:
        payload['transformpolicylabel_transformpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['transformpolicylabel_transformpolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['transformpolicylabel_transformpolicy_binding']['invoke_labelname'] = invoke_labelname

    if gotopriorityexpression:
        payload['transformpolicylabel_transformpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['transformpolicylabel_transformpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['transformpolicylabel_transformpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/transformpolicylabel_transformpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_transformprofile(name=None, ns_type=None, onlytransformabsurlinbody=None, comment=None, save=False):
    '''
    Add a new transformprofile to the running configuration.

    name(str): Name for the URL transformation profile. Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the URL transformation profile is added.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, ?my transform profile? or ?my transform profile?). Minimum
        length = 1

    ns_type(str): Type of transformation. Always URL for URL Transformation profiles. Possible values = URL

    onlytransformabsurlinbody(str): In the HTTP body, transform only absolute URLs. Relative URLs are ignored. Possible
        values = ON, OFF

    comment(str): Any comments to preserve information about this URL Transformation profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.add_transformprofile <args>

    '''

    result = {}

    payload = {'transformprofile': {}}

    if name:
        payload['transformprofile']['name'] = name

    if ns_type:
        payload['transformprofile']['type'] = ns_type

    if onlytransformabsurlinbody:
        payload['transformprofile']['onlytransformabsurlinbody'] = onlytransformabsurlinbody

    if comment:
        payload['transformprofile']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/transformprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_transformaction(name=None, profilename=None, priority=None, state=None, requrlfrom=None, requrlinto=None,
                        resurlfrom=None, resurlinto=None, cookiedomainfrom=None, cookiedomaininto=None, comment=None):
    '''
    Show the running configuration for the transformaction config key.

    name(str): Filters results that only match the name field.

    profilename(str): Filters results that only match the profilename field.

    priority(int): Filters results that only match the priority field.

    state(str): Filters results that only match the state field.

    requrlfrom(str): Filters results that only match the requrlfrom field.

    requrlinto(str): Filters results that only match the requrlinto field.

    resurlfrom(str): Filters results that only match the resurlfrom field.

    resurlinto(str): Filters results that only match the resurlinto field.

    cookiedomainfrom(str): Filters results that only match the cookiedomainfrom field.

    cookiedomaininto(str): Filters results that only match the cookiedomaininto field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if profilename:
        search_filter.append(['profilename', profilename])

    if priority:
        search_filter.append(['priority', priority])

    if state:
        search_filter.append(['state', state])

    if requrlfrom:
        search_filter.append(['requrlfrom', requrlfrom])

    if requrlinto:
        search_filter.append(['requrlinto', requrlinto])

    if resurlfrom:
        search_filter.append(['resurlfrom', resurlfrom])

    if resurlinto:
        search_filter.append(['resurlinto', resurlinto])

    if cookiedomainfrom:
        search_filter.append(['cookiedomainfrom', cookiedomainfrom])

    if cookiedomaininto:
        search_filter.append(['cookiedomaininto', cookiedomaininto])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformaction')

    return response


def get_transformglobal_binding():
    '''
    Show the running configuration for the transformglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformglobal_binding'), 'transformglobal_binding')

    return response


def get_transformglobal_transformpolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                                gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None):
    '''
    Show the running configuration for the transformglobal_transformpolicy_binding config key.

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

    salt '*' transform.get_transformglobal_transformpolicy_binding

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
            __proxy__['citrixns.get']('config/transformglobal_transformpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformglobal_transformpolicy_binding')

    return response


def get_transformpolicy(name=None, rule=None, profilename=None, comment=None, logaction=None, newname=None):
    '''
    Show the running configuration for the transformpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    profilename(str): Filters results that only match the profilename field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if profilename:
        search_filter.append(['profilename', profilename])

    if comment:
        search_filter.append(['comment', comment])

    if logaction:
        search_filter.append(['logaction', logaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformpolicy')

    return response


def get_transformpolicy_binding():
    '''
    Show the running configuration for the transformpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformpolicy_binding'), 'transformpolicy_binding')

    return response


def get_transformpolicy_csvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the transformpolicy_csvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformpolicy_csvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformpolicy_csvserver_binding')

    return response


def get_transformpolicy_lbvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the transformpolicy_lbvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformpolicy_lbvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformpolicy_lbvserver_binding')

    return response


def get_transformpolicy_transformglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the transformpolicy_transformglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformpolicy_transformglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformpolicy_transformglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformpolicy_transformglobal_binding')

    return response


def get_transformpolicy_transformpolicylabel_binding(name=None, boundto=None):
    '''
    Show the running configuration for the transformpolicy_transformpolicylabel_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformpolicy_transformpolicylabel_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformpolicy_transformpolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformpolicy_transformpolicylabel_binding')

    return response


def get_transformpolicylabel(labelname=None, policylabeltype=None, newname=None):
    '''
    Show the running configuration for the transformpolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    policylabeltype(str): Filters results that only match the policylabeltype field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformpolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if policylabeltype:
        search_filter.append(['policylabeltype', policylabeltype])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformpolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformpolicylabel')

    return response


def get_transformpolicylabel_binding():
    '''
    Show the running configuration for the transformpolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformpolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformpolicylabel_binding'), 'transformpolicylabel_binding')

    return response


def get_transformpolicylabel_policybinding_binding(priority=None, policyname=None, labelname=None, invoke_labelname=None,
                                                   gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the transformpolicylabel_policybinding_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformpolicylabel_policybinding_binding

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
            __proxy__['citrixns.get']('config/transformpolicylabel_policybinding_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformpolicylabel_policybinding_binding')

    return response


def get_transformpolicylabel_transformpolicy_binding(priority=None, policyname=None, labelname=None,
                                                     invoke_labelname=None, gotopriorityexpression=None, invoke=None,
                                                     labeltype=None):
    '''
    Show the running configuration for the transformpolicylabel_transformpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformpolicylabel_transformpolicy_binding

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
            __proxy__['citrixns.get']('config/transformpolicylabel_transformpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformpolicylabel_transformpolicy_binding')

    return response


def get_transformprofile(name=None, ns_type=None, onlytransformabsurlinbody=None, comment=None):
    '''
    Show the running configuration for the transformprofile config key.

    name(str): Filters results that only match the name field.

    ns_type(str): Filters results that only match the type field.

    onlytransformabsurlinbody(str): Filters results that only match the onlytransformabsurlinbody field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ns_type:
        search_filter.append(['type', ns_type])

    if onlytransformabsurlinbody:
        search_filter.append(['onlytransformabsurlinbody', onlytransformabsurlinbody])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformprofile')

    return response


def get_transformprofile_binding():
    '''
    Show the running configuration for the transformprofile_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformprofile_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformprofile_binding'), 'transformprofile_binding')

    return response


def get_transformprofile_transformaction_binding(name=None, actionname=None):
    '''
    Show the running configuration for the transformprofile_transformaction_binding config key.

    name(str): Filters results that only match the name field.

    actionname(str): Filters results that only match the actionname field.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.get_transformprofile_transformaction_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if actionname:
        search_filter.append(['actionname', actionname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/transformprofile_transformaction_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'transformprofile_transformaction_binding')

    return response


def unset_transformaction(name=None, profilename=None, priority=None, state=None, requrlfrom=None, requrlinto=None,
                          resurlfrom=None, resurlinto=None, cookiedomainfrom=None, cookiedomaininto=None, comment=None,
                          save=False):
    '''
    Unsets values from the transformaction configuration key.

    name(bool): Unsets the name value.

    profilename(bool): Unsets the profilename value.

    priority(bool): Unsets the priority value.

    state(bool): Unsets the state value.

    requrlfrom(bool): Unsets the requrlfrom value.

    requrlinto(bool): Unsets the requrlinto value.

    resurlfrom(bool): Unsets the resurlfrom value.

    resurlinto(bool): Unsets the resurlinto value.

    cookiedomainfrom(bool): Unsets the cookiedomainfrom value.

    cookiedomaininto(bool): Unsets the cookiedomaininto value.

    comment(bool): Unsets the comment value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.unset_transformaction <args>

    '''

    result = {}

    payload = {'transformaction': {}}

    if name:
        payload['transformaction']['name'] = True

    if profilename:
        payload['transformaction']['profilename'] = True

    if priority:
        payload['transformaction']['priority'] = True

    if state:
        payload['transformaction']['state'] = True

    if requrlfrom:
        payload['transformaction']['requrlfrom'] = True

    if requrlinto:
        payload['transformaction']['requrlinto'] = True

    if resurlfrom:
        payload['transformaction']['resurlfrom'] = True

    if resurlinto:
        payload['transformaction']['resurlinto'] = True

    if cookiedomainfrom:
        payload['transformaction']['cookiedomainfrom'] = True

    if cookiedomaininto:
        payload['transformaction']['cookiedomaininto'] = True

    if comment:
        payload['transformaction']['comment'] = True

    execution = __proxy__['citrixns.post']('config/transformaction?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_transformpolicy(name=None, rule=None, profilename=None, comment=None, logaction=None, newname=None,
                          save=False):
    '''
    Unsets values from the transformpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    profilename(bool): Unsets the profilename value.

    comment(bool): Unsets the comment value.

    logaction(bool): Unsets the logaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.unset_transformpolicy <args>

    '''

    result = {}

    payload = {'transformpolicy': {}}

    if name:
        payload['transformpolicy']['name'] = True

    if rule:
        payload['transformpolicy']['rule'] = True

    if profilename:
        payload['transformpolicy']['profilename'] = True

    if comment:
        payload['transformpolicy']['comment'] = True

    if logaction:
        payload['transformpolicy']['logaction'] = True

    if newname:
        payload['transformpolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/transformpolicy?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_transformprofile(name=None, ns_type=None, onlytransformabsurlinbody=None, comment=None, save=False):
    '''
    Unsets values from the transformprofile configuration key.

    name(bool): Unsets the name value.

    ns_type(bool): Unsets the ns_type value.

    onlytransformabsurlinbody(bool): Unsets the onlytransformabsurlinbody value.

    comment(bool): Unsets the comment value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.unset_transformprofile <args>

    '''

    result = {}

    payload = {'transformprofile': {}}

    if name:
        payload['transformprofile']['name'] = True

    if ns_type:
        payload['transformprofile']['type'] = True

    if onlytransformabsurlinbody:
        payload['transformprofile']['onlytransformabsurlinbody'] = True

    if comment:
        payload['transformprofile']['comment'] = True

    execution = __proxy__['citrixns.post']('config/transformprofile?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_transformaction(name=None, profilename=None, priority=None, state=None, requrlfrom=None, requrlinto=None,
                           resurlfrom=None, resurlinto=None, cookiedomainfrom=None, cookiedomaininto=None, comment=None,
                           save=False):
    '''
    Update the running configuration for the transformaction config key.

    name(str): Name for the URL transformation action. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the URL Transformation action is added.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, ?my transform action? or ?my transform action). Minimum
        length = 1

    profilename(str): Name of the URL Transformation profile with which to associate this action. Minimum length = 1

    priority(int): Positive integer specifying the priority of the action within the profile. A lower number specifies a
        higher priority. Must be unique within the list of actions bound to the profile. Policies are evaluated in the
        order of their priority numbers, and the first policy that matches is applied. Minimum value = 1 Maximum value =
        2147483647

    state(str): Enable or disable this action. Default value: ENABLED Possible values = ENABLED, DISABLED

    requrlfrom(str): PCRE-format regular expression that describes the request URL pattern to be transformed. Minimum length
        = 1

    requrlinto(str): PCRE-format regular expression that describes the transformation to be performed on URLs that match the
        reqUrlFrom pattern. Minimum length = 1

    resurlfrom(str): PCRE-format regular expression that describes the response URL pattern to be transformed. Minimum length
        = 1

    resurlinto(str): PCRE-format regular expression that describes the transformation to be performed on URLs that match the
        resUrlFrom pattern. Minimum length = 1

    cookiedomainfrom(str): Pattern that matches the domain to be transformed in Set-Cookie headers. Minimum length = 1

    cookiedomaininto(str): PCRE-format regular expression that describes the transformation to be performed on cookie domains
        that match the cookieDomainFrom pattern.  NOTE: The cookie domain to be transformed is extracted from the
        request. Minimum length = 1

    comment(str): Any comments to preserve information about this URL Transformation action.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.update_transformaction <args>

    '''

    result = {}

    payload = {'transformaction': {}}

    if name:
        payload['transformaction']['name'] = name

    if profilename:
        payload['transformaction']['profilename'] = profilename

    if priority:
        payload['transformaction']['priority'] = priority

    if state:
        payload['transformaction']['state'] = state

    if requrlfrom:
        payload['transformaction']['requrlfrom'] = requrlfrom

    if requrlinto:
        payload['transformaction']['requrlinto'] = requrlinto

    if resurlfrom:
        payload['transformaction']['resurlfrom'] = resurlfrom

    if resurlinto:
        payload['transformaction']['resurlinto'] = resurlinto

    if cookiedomainfrom:
        payload['transformaction']['cookiedomainfrom'] = cookiedomainfrom

    if cookiedomaininto:
        payload['transformaction']['cookiedomaininto'] = cookiedomaininto

    if comment:
        payload['transformaction']['comment'] = comment

    execution = __proxy__['citrixns.put']('config/transformaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_transformpolicy(name=None, rule=None, profilename=None, comment=None, logaction=None, newname=None,
                           save=False):
    '''
    Update the running configuration for the transformpolicy config key.

    name(str): Name for the URL Transformation policy. Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Can be changed after the URL Transformation policy is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, ?my transform policy? or ?my transform policy). Minimum length =
        1

    rule(str): Expression, or name of a named expression, against which to evaluate traffic. Can be written in either default
        or classic syntax. Maximum length of a string literal in the expression is 255 characters. A longer string can be
        split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;"  The following requirements apply only to the NetScaler CLI: * If the
        expression includes blank spaces, the entire expression must be enclosed in double quotation marks. * If the
        expression itself includes double quotation marks, you must escape the quotations by using the \\ character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    profilename(str): Name of the URL Transformation profile to use to transform requests and responses that match the
        policy. Minimum length = 1

    comment(str): Any comments to preserve information about this URL Transformation policy.

    logaction(str): Log server to use to log connections that match this policy.

    newname(str): New name for the policy. Must begin with a letter, number, or the underscore character (_), and must
        contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=), colon
        (:), and underscore characters.  The following requirement applies only to the NetScaler CLI: If the name
        includes one or more spaces, enclose the name in double or single quotation marks (for example, ?my transform
        policy? or ?my transform policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.update_transformpolicy <args>

    '''

    result = {}

    payload = {'transformpolicy': {}}

    if name:
        payload['transformpolicy']['name'] = name

    if rule:
        payload['transformpolicy']['rule'] = rule

    if profilename:
        payload['transformpolicy']['profilename'] = profilename

    if comment:
        payload['transformpolicy']['comment'] = comment

    if logaction:
        payload['transformpolicy']['logaction'] = logaction

    if newname:
        payload['transformpolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/transformpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_transformprofile(name=None, ns_type=None, onlytransformabsurlinbody=None, comment=None, save=False):
    '''
    Update the running configuration for the transformprofile config key.

    name(str): Name for the URL transformation profile. Must begin with a letter, number, or the underscore character (_),
        and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the URL transformation profile is added.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, ?my transform profile? or ?my transform profile?). Minimum
        length = 1

    ns_type(str): Type of transformation. Always URL for URL Transformation profiles. Possible values = URL

    onlytransformabsurlinbody(str): In the HTTP body, transform only absolute URLs. Relative URLs are ignored. Possible
        values = ON, OFF

    comment(str): Any comments to preserve information about this URL Transformation profile.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' transform.update_transformprofile <args>

    '''

    result = {}

    payload = {'transformprofile': {}}

    if name:
        payload['transformprofile']['name'] = name

    if ns_type:
        payload['transformprofile']['type'] = ns_type

    if onlytransformabsurlinbody:
        payload['transformprofile']['onlytransformabsurlinbody'] = onlytransformabsurlinbody

    if comment:
        payload['transformprofile']['comment'] = comment

    execution = __proxy__['citrixns.put']('config/transformprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
