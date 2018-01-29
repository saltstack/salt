# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the tunnel key.

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

__virtualname__ = 'tunnel'


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

    return False, 'The tunnel execution module can only be loaded for citrixns proxy minions.'


def add_tunnelglobal_tunneltrafficpolicy_binding(priority=None, builtin=None, policyname=None, state=None, save=False):
    '''
    Add a new tunnelglobal_tunneltrafficpolicy_binding to the running configuration.

    priority(int): Priority.

    builtin(list(str)): Indicates that a variable is a built-in (SYSTEM INTERNAL) type. Possible values = MODIFIABLE,
        DELETABLE, IMMUTABLE, PARTITION_ALL

    policyname(str): Policy name.

    state(str): Current state of the binding. If the binding is enabled, the policy is active. Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' tunnel.add_tunnelglobal_tunneltrafficpolicy_binding <args>

    '''

    result = {}

    payload = {'tunnelglobal_tunneltrafficpolicy_binding': {}}

    if priority:
        payload['tunnelglobal_tunneltrafficpolicy_binding']['priority'] = priority

    if builtin:
        payload['tunnelglobal_tunneltrafficpolicy_binding']['builtin'] = builtin

    if policyname:
        payload['tunnelglobal_tunneltrafficpolicy_binding']['policyname'] = policyname

    if state:
        payload['tunnelglobal_tunneltrafficpolicy_binding']['state'] = state

    execution = __proxy__['citrixns.post']('config/tunnelglobal_tunneltrafficpolicy_binding', payload)

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


def add_tunneltrafficpolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new tunneltrafficpolicy to the running configuration.

    name(str): Name for the tunnel traffic policy. Must begin with an ASCII alphanumeric or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the policy is created. The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, against which traffic is evaluated. Written in classic or default syntax. Maximum length of a
        string literal in the expression is 255 characters. A longer string can be split into smaller strings of up to
        255 characters each, and the smaller strings concatenated with the + operator. For example, you can create a
        500-character string as follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" The
        following requirements apply only to the NetScaler CLI: * If the expression includes blank spaces, the entire
        expression must be enclosed in double quotation marks. * If the expression itself includes double quotation
        marks, you must escape the quotations by using the \\ character.  * Alternatively, you can use single quotation
        marks to enclose the rule, in which case you do not have to escape the double quotation marks.

    action(str): Name of the built-in compression action to associate with the policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' tunnel.add_tunneltrafficpolicy <args>

    '''

    result = {}

    payload = {'tunneltrafficpolicy': {}}

    if name:
        payload['tunneltrafficpolicy']['name'] = name

    if rule:
        payload['tunneltrafficpolicy']['rule'] = rule

    if action:
        payload['tunneltrafficpolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/tunneltrafficpolicy', payload)

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


def get_tunnelglobal_binding():
    '''
    Show the running configuration for the tunnelglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' tunnel.get_tunnelglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tunnelglobal_binding'), 'tunnelglobal_binding')

    return response


def get_tunnelglobal_tunneltrafficpolicy_binding(priority=None, builtin=None, policyname=None, state=None):
    '''
    Show the running configuration for the tunnelglobal_tunneltrafficpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    builtin(list(str)): Filters results that only match the builtin field.

    policyname(str): Filters results that only match the policyname field.

    state(str): Filters results that only match the state field.

    CLI Example:

    .. code-block:: bash

    salt '*' tunnel.get_tunnelglobal_tunneltrafficpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if builtin:
        search_filter.append(['builtin', builtin])

    if policyname:
        search_filter.append(['policyname', policyname])

    if state:
        search_filter.append(['state', state])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tunnelglobal_tunneltrafficpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tunnelglobal_tunneltrafficpolicy_binding')

    return response


def get_tunneltrafficpolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the tunneltrafficpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' tunnel.get_tunneltrafficpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tunneltrafficpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tunneltrafficpolicy')

    return response


def get_tunneltrafficpolicy_binding():
    '''
    Show the running configuration for the tunneltrafficpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' tunnel.get_tunneltrafficpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tunneltrafficpolicy_binding'), 'tunneltrafficpolicy_binding')

    return response


def get_tunneltrafficpolicy_tunnelglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the tunneltrafficpolicy_tunnelglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' tunnel.get_tunneltrafficpolicy_tunnelglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/tunneltrafficpolicy_tunnelglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'tunneltrafficpolicy_tunnelglobal_binding')

    return response


def unset_tunneltrafficpolicy(name=None, rule=None, action=None, save=False):
    '''
    Unsets values from the tunneltrafficpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' tunnel.unset_tunneltrafficpolicy <args>

    '''

    result = {}

    payload = {'tunneltrafficpolicy': {}}

    if name:
        payload['tunneltrafficpolicy']['name'] = True

    if rule:
        payload['tunneltrafficpolicy']['rule'] = True

    if action:
        payload['tunneltrafficpolicy']['action'] = True

    execution = __proxy__['citrixns.post']('config/tunneltrafficpolicy?action=unset', payload)

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


def update_tunneltrafficpolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the tunneltrafficpolicy config key.

    name(str): Name for the tunnel traffic policy. Must begin with an ASCII alphanumeric or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the policy is created. The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, against which traffic is evaluated. Written in classic or default syntax. Maximum length of a
        string literal in the expression is 255 characters. A longer string can be split into smaller strings of up to
        255 characters each, and the smaller strings concatenated with the + operator. For example, you can create a
        500-character string as follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" The
        following requirements apply only to the NetScaler CLI: * If the expression includes blank spaces, the entire
        expression must be enclosed in double quotation marks. * If the expression itself includes double quotation
        marks, you must escape the quotations by using the \\ character.  * Alternatively, you can use single quotation
        marks to enclose the rule, in which case you do not have to escape the double quotation marks.

    action(str): Name of the built-in compression action to associate with the policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' tunnel.update_tunneltrafficpolicy <args>

    '''

    result = {}

    payload = {'tunneltrafficpolicy': {}}

    if name:
        payload['tunneltrafficpolicy']['name'] = name

    if rule:
        payload['tunneltrafficpolicy']['rule'] = rule

    if action:
        payload['tunneltrafficpolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/tunneltrafficpolicy', payload)

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
