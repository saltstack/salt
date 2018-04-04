# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the authorization key.

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

__virtualname__ = 'authorization'


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

    return False, 'The authorization execution module can only be loaded for citrixns proxy minions.'


def add_authorizationpolicy(name=None, rule=None, action=None, newname=None, save=False):
    '''
    Add a new authorizationpolicy to the running configuration.

    name(str): Name for the new authorization policy.  Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the authorization policy is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my authorization policy" or my authorization policy). Minimum
        length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to perform the
        authentication.

    action(str): Action to perform if the policy matches: either allow or deny the request. Minimum length = 1

    newname(str): The new name of the author policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.add_authorizationpolicy <args>

    '''

    result = {}

    payload = {'authorizationpolicy': {}}

    if name:
        payload['authorizationpolicy']['name'] = name

    if rule:
        payload['authorizationpolicy']['rule'] = rule

    if action:
        payload['authorizationpolicy']['action'] = action

    if newname:
        payload['authorizationpolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/authorizationpolicy', payload)

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


def add_authorizationpolicylabel(labelname=None, newname=None, save=False):
    '''
    Add a new authorizationpolicylabel to the running configuration.

    labelname(str): Name for the new authorization policy label.  Must begin with a letter, number, or the underscore
        character (_), and must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at
        (@), equals (=), colon (:), and underscore characters. Cannot be changed after the authorization policy is
        created.  The following requirement applies only to the NetScaler CLI: If the name includes one or more spaces,
        enclose the name in double or single quotation marks (for example, "my authorization policy label" or
        authorization policy label).

    newname(str): The new name of the auth policy label. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.add_authorizationpolicylabel <args>

    '''

    result = {}

    payload = {'authorizationpolicylabel': {}}

    if labelname:
        payload['authorizationpolicylabel']['labelname'] = labelname

    if newname:
        payload['authorizationpolicylabel']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/authorizationpolicylabel', payload)

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


def add_authorizationpolicylabel_authorizationpolicy_binding(priority=None, policyname=None, labelname=None,
                                                             invoke_labelname=None, gotopriorityexpression=None,
                                                             invoke=None, labeltype=None, save=False):
    '''
    Add a new authorizationpolicylabel_authorizationpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    policyname(str): Name of the authorization policy to bind to the policy label.

    labelname(str): Name of the authorization policy label to which to bind the policy.

    invoke_labelname(str): Name of the policy label to invoke if the current policy evaluates to TRUE, the invoke parameter
        is set, and Label Type is set to Policy Label.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): If the current policy evaluates to TRUE, terminate evaluation of policies bound to the current policy
        label, and then either forward the request or response to the specified virtual server or evaluate the specified
        policy label.

    labeltype(str): Type of invocation. Available settings function as follows: * reqvserver - Send the request to the
        specified request virtual server. * resvserver - Send the response to the specified response virtual server. *
        policylabel - Invoke the specified policy label. Possible values = reqvserver, resvserver, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.add_authorizationpolicylabel_authorizationpolicy_binding <args>

    '''

    result = {}

    payload = {'authorizationpolicylabel_authorizationpolicy_binding': {}}

    if priority:
        payload['authorizationpolicylabel_authorizationpolicy_binding']['priority'] = priority

    if policyname:
        payload['authorizationpolicylabel_authorizationpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['authorizationpolicylabel_authorizationpolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['authorizationpolicylabel_authorizationpolicy_binding']['invoke_labelname'] = invoke_labelname

    if gotopriorityexpression:
        payload['authorizationpolicylabel_authorizationpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['authorizationpolicylabel_authorizationpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['authorizationpolicylabel_authorizationpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/authorizationpolicylabel_authorizationpolicy_binding', payload)

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


def get_authorizationaction(name=None):
    '''
    Show the running configuration for the authorizationaction config key.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authorizationaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authorizationaction')

    return response


def get_authorizationpolicy(name=None, rule=None, action=None, newname=None):
    '''
    Show the running configuration for the authorizationpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authorizationpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authorizationpolicy')

    return response


def get_authorizationpolicy_aaagroup_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authorizationpolicy_aaagroup_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationpolicy_aaagroup_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authorizationpolicy_aaagroup_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authorizationpolicy_aaagroup_binding')

    return response


def get_authorizationpolicy_aaauser_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authorizationpolicy_aaauser_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationpolicy_aaauser_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authorizationpolicy_aaauser_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authorizationpolicy_aaauser_binding')

    return response


def get_authorizationpolicy_authorizationpolicylabel_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authorizationpolicy_authorizationpolicylabel_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationpolicy_authorizationpolicylabel_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authorizationpolicy_authorizationpolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authorizationpolicy_authorizationpolicylabel_binding')

    return response


def get_authorizationpolicy_binding():
    '''
    Show the running configuration for the authorizationpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authorizationpolicy_binding'), 'authorizationpolicy_binding')

    return response


def get_authorizationpolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authorizationpolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationpolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authorizationpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authorizationpolicy_csvserver_binding')

    return response


def get_authorizationpolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the authorizationpolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationpolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authorizationpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authorizationpolicy_lbvserver_binding')

    return response


def get_authorizationpolicylabel(labelname=None, newname=None):
    '''
    Show the running configuration for the authorizationpolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationpolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authorizationpolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authorizationpolicylabel')

    return response


def get_authorizationpolicylabel_authorizationpolicy_binding(priority=None, policyname=None, labelname=None,
                                                             invoke_labelname=None, gotopriorityexpression=None,
                                                             invoke=None, labeltype=None):
    '''
    Show the running configuration for the authorizationpolicylabel_authorizationpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationpolicylabel_authorizationpolicy_binding

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
            __proxy__['citrixns.get']('config/authorizationpolicylabel_authorizationpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'authorizationpolicylabel_authorizationpolicy_binding')

    return response


def get_authorizationpolicylabel_binding():
    '''
    Show the running configuration for the authorizationpolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.get_authorizationpolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/authorizationpolicylabel_binding'), 'authorizationpolicylabel_binding')

    return response


def update_authorizationpolicy(name=None, rule=None, action=None, newname=None, save=False):
    '''
    Update the running configuration for the authorizationpolicy config key.

    name(str): Name for the new authorization policy.  Must begin with a letter, number, or the underscore character (_), and
        must contain only letters, numbers, and the hyphen (-), period (.) pound (#), space ( ), at (@), equals (=),
        colon (:), and underscore characters. Cannot be changed after the authorization policy is added.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my authorization policy" or my authorization policy). Minimum
        length = 1

    rule(str): Name of the NetScaler named rule, or a default syntax expression, that the policy uses to perform the
        authentication.

    action(str): Action to perform if the policy matches: either allow or deny the request. Minimum length = 1

    newname(str): The new name of the author policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' authorization.update_authorizationpolicy <args>

    '''

    result = {}

    payload = {'authorizationpolicy': {}}

    if name:
        payload['authorizationpolicy']['name'] = name

    if rule:
        payload['authorizationpolicy']['rule'] = rule

    if action:
        payload['authorizationpolicy']['action'] = action

    if newname:
        payload['authorizationpolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/authorizationpolicy', payload)

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
