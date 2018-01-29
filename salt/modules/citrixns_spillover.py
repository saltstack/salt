# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the spillover key.

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

__virtualname__ = 'spillover'


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

    return False, 'The spillover execution module can only be loaded for citrixns proxy minions.'


def add_spilloveraction(name=None, action=None, newname=None, save=False):
    '''
    Add a new spilloveraction to the running configuration.

    name(str): Name of the spillover action.

    action(str): Spillover action. Currently only type SPILLOVER is supported. Possible values = SPILLOVER

    newname(str): New name for the spillover action. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.  Choose a name that can be correlated with the function that the action performs.   The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my action" or my action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' spillover.add_spilloveraction <args>

    '''

    result = {}

    payload = {'spilloveraction': {}}

    if name:
        payload['spilloveraction']['name'] = name

    if action:
        payload['spilloveraction']['action'] = action

    if newname:
        payload['spilloveraction']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/spilloveraction', payload)

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


def add_spilloverpolicy(name=None, rule=None, action=None, comment=None, newname=None, save=False):
    '''
    Add a new spilloverpolicy to the running configuration.

    name(str): Name of the spillover policy.

    rule(str): Expression to be used by the spillover policy.

    action(str): Action for the spillover policy. Action is created using add spillover action command.

    comment(str): Any comments that you might want to associate with the spillover policy.

    newname(str): New name for the spillover policy. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Choose a name that reflects the function that the policy performs.   The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my policy" or my policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' spillover.add_spilloverpolicy <args>

    '''

    result = {}

    payload = {'spilloverpolicy': {}}

    if name:
        payload['spilloverpolicy']['name'] = name

    if rule:
        payload['spilloverpolicy']['rule'] = rule

    if action:
        payload['spilloverpolicy']['action'] = action

    if comment:
        payload['spilloverpolicy']['comment'] = comment

    if newname:
        payload['spilloverpolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/spilloverpolicy', payload)

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


def get_spilloveraction(name=None, action=None, newname=None):
    '''
    Show the running configuration for the spilloveraction config key.

    name(str): Filters results that only match the name field.

    action(str): Filters results that only match the action field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' spillover.get_spilloveraction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if action:
        search_filter.append(['action', action])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/spilloveraction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'spilloveraction')

    return response


def get_spilloverpolicy(name=None, rule=None, action=None, comment=None, newname=None):
    '''
    Show the running configuration for the spilloverpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    comment(str): Filters results that only match the comment field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' spillover.get_spilloverpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    if comment:
        search_filter.append(['comment', comment])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/spilloverpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'spilloverpolicy')

    return response


def get_spilloverpolicy_binding():
    '''
    Show the running configuration for the spilloverpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' spillover.get_spilloverpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/spilloverpolicy_binding'), 'spilloverpolicy_binding')

    return response


def get_spilloverpolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the spilloverpolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' spillover.get_spilloverpolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/spilloverpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'spilloverpolicy_csvserver_binding')

    return response


def get_spilloverpolicy_gslbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the spilloverpolicy_gslbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' spillover.get_spilloverpolicy_gslbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/spilloverpolicy_gslbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'spilloverpolicy_gslbvserver_binding')

    return response


def get_spilloverpolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the spilloverpolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' spillover.get_spilloverpolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/spilloverpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'spilloverpolicy_lbvserver_binding')

    return response


def unset_spilloverpolicy(name=None, rule=None, action=None, comment=None, newname=None, save=False):
    '''
    Unsets values from the spilloverpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    comment(bool): Unsets the comment value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' spillover.unset_spilloverpolicy <args>

    '''

    result = {}

    payload = {'spilloverpolicy': {}}

    if name:
        payload['spilloverpolicy']['name'] = True

    if rule:
        payload['spilloverpolicy']['rule'] = True

    if action:
        payload['spilloverpolicy']['action'] = True

    if comment:
        payload['spilloverpolicy']['comment'] = True

    if newname:
        payload['spilloverpolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/spilloverpolicy?action=unset', payload)

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


def update_spilloverpolicy(name=None, rule=None, action=None, comment=None, newname=None, save=False):
    '''
    Update the running configuration for the spilloverpolicy config key.

    name(str): Name of the spillover policy.

    rule(str): Expression to be used by the spillover policy.

    action(str): Action for the spillover policy. Action is created using add spillover action command.

    comment(str): Any comments that you might want to associate with the spillover policy.

    newname(str): New name for the spillover policy. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Choose a name that reflects the function that the policy performs.   The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my policy" or my policy). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' spillover.update_spilloverpolicy <args>

    '''

    result = {}

    payload = {'spilloverpolicy': {}}

    if name:
        payload['spilloverpolicy']['name'] = name

    if rule:
        payload['spilloverpolicy']['rule'] = rule

    if action:
        payload['spilloverpolicy']['action'] = action

    if comment:
        payload['spilloverpolicy']['comment'] = comment

    if newname:
        payload['spilloverpolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/spilloverpolicy', payload)

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
