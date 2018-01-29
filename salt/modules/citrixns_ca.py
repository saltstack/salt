# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the ca key.

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

__virtualname__ = 'ca'


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

    return False, 'The ca execution module can only be loaded for citrixns proxy minions.'


def add_caaction(name=None, accumressize=None, lbvserver=None, comment=None, ns_type=None, newname=None, save=False):
    '''
    Add a new caaction to the running configuration.

    name(str): Name of the content accelerator action. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.

    accumressize(int): Size of the data, in KB, that the server must respond with. The NetScaler uses this data to compute a
        hash which is then used to lookup within the T2100 appliance.

    lbvserver(str): Name of the load balancing virtual server that has the T2100 appliances as services.

    comment(str): Information about the content accelerator action.

    ns_type(str): Specifies whether the NetScaler must lookup for the response on the T2100 appliance or serve the response
        directly from the server. Possible values = nolookup, lookup, noop

    newname(str): New name for the content accelerator action.  Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Can be changed after the content accelerator policy is added.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my content accelerator action" or my content accelerator
        action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.add_caaction <args>

    '''

    result = {}

    payload = {'caaction': {}}

    if name:
        payload['caaction']['name'] = name

    if accumressize:
        payload['caaction']['accumressize'] = accumressize

    if lbvserver:
        payload['caaction']['lbvserver'] = lbvserver

    if comment:
        payload['caaction']['comment'] = comment

    if ns_type:
        payload['caaction']['type'] = ns_type

    if newname:
        payload['caaction']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/caaction', payload)

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


def add_caglobal_capolicy_binding(priority=None, globalbindtype=None, policyname=None, gotopriorityexpression=None,
                                  ns_type=None, save=False):
    '''
    Add a new caglobal_capolicy_binding to the running configuration.

    priority(int): Specifies the priority of the content accelerator policy.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): Name of the content accelerator policy.

    gotopriorityexpression(str): .

    ns_type(str): . Possible values = REQ_OVERRIDE, REQ_DEFAULT, RES_OVERRIDE, RES_DEFAULT

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.add_caglobal_capolicy_binding <args>

    '''

    result = {}

    payload = {'caglobal_capolicy_binding': {}}

    if priority:
        payload['caglobal_capolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['caglobal_capolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['caglobal_capolicy_binding']['policyname'] = policyname

    if gotopriorityexpression:
        payload['caglobal_capolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if ns_type:
        payload['caglobal_capolicy_binding']['type'] = ns_type

    execution = __proxy__['citrixns.post']('config/caglobal_capolicy_binding', payload)

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


def add_capolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None, newname=None,
                 save=False):
    '''
    Add a new capolicy to the running configuration.

    name(str): Name for the content accelerator policy. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the policy is created.

    rule(str): Expression that determines which requests or responses match the content accelerator policy. When specifying
        the rule in the CLI, the description must be enclosed within double quotes.

    action(str): Name of content accelerator action to be executed when the rule is evaluated to true.

    undefaction(str): .

    comment(str): Information about the content accelerator policy.

    logaction(str): Name of messagelog action to use when a request matches this policy.

    newname(str): New name for the content accelerator policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.add_capolicy <args>

    '''

    result = {}

    payload = {'capolicy': {}}

    if name:
        payload['capolicy']['name'] = name

    if rule:
        payload['capolicy']['rule'] = rule

    if action:
        payload['capolicy']['action'] = action

    if undefaction:
        payload['capolicy']['undefaction'] = undefaction

    if comment:
        payload['capolicy']['comment'] = comment

    if logaction:
        payload['capolicy']['logaction'] = logaction

    if newname:
        payload['capolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/capolicy', payload)

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


def get_caaction(name=None, accumressize=None, lbvserver=None, comment=None, ns_type=None, newname=None):
    '''
    Show the running configuration for the caaction config key.

    name(str): Filters results that only match the name field.

    accumressize(int): Filters results that only match the accumressize field.

    lbvserver(str): Filters results that only match the lbvserver field.

    comment(str): Filters results that only match the comment field.

    ns_type(str): Filters results that only match the type field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.get_caaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if accumressize:
        search_filter.append(['accumressize', accumressize])

    if lbvserver:
        search_filter.append(['lbvserver', lbvserver])

    if comment:
        search_filter.append(['comment', comment])

    if ns_type:
        search_filter.append(['type', ns_type])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/caaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'caaction')

    return response


def get_caglobal_binding():
    '''
    Show the running configuration for the caglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.get_caglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/caglobal_binding'), 'caglobal_binding')

    return response


def get_caglobal_capolicy_binding(priority=None, globalbindtype=None, policyname=None, gotopriorityexpression=None,
                                  ns_type=None):
    '''
    Show the running configuration for the caglobal_capolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    globalbindtype(str): Filters results that only match the globalbindtype field.

    policyname(str): Filters results that only match the policyname field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    ns_type(str): Filters results that only match the type field.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.get_caglobal_capolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if globalbindtype:
        search_filter.append(['globalbindtype', globalbindtype])

    if policyname:
        search_filter.append(['policyname', policyname])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if ns_type:
        search_filter.append(['type', ns_type])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/caglobal_capolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'caglobal_capolicy_binding')

    return response


def get_capolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None, newname=None):
    '''
    Show the running configuration for the capolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    undefaction(str): Filters results that only match the undefaction field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.get_capolicy

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

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/capolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'capolicy')

    return response


def get_capolicy_binding():
    '''
    Show the running configuration for the capolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.get_capolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/capolicy_binding'), 'capolicy_binding')

    return response


def get_capolicy_caglobal_binding(name=None, boundto=None):
    '''
    Show the running configuration for the capolicy_caglobal_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.get_capolicy_caglobal_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/capolicy_caglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'capolicy_caglobal_binding')

    return response


def get_capolicy_csvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the capolicy_csvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.get_capolicy_csvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/capolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'capolicy_csvserver_binding')

    return response


def get_capolicy_lbvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the capolicy_lbvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.get_capolicy_lbvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/capolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'capolicy_lbvserver_binding')

    return response


def unset_caaction(name=None, accumressize=None, lbvserver=None, comment=None, ns_type=None, newname=None, save=False):
    '''
    Unsets values from the caaction configuration key.

    name(bool): Unsets the name value.

    accumressize(bool): Unsets the accumressize value.

    lbvserver(bool): Unsets the lbvserver value.

    comment(bool): Unsets the comment value.

    ns_type(bool): Unsets the ns_type value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.unset_caaction <args>

    '''

    result = {}

    payload = {'caaction': {}}

    if name:
        payload['caaction']['name'] = True

    if accumressize:
        payload['caaction']['accumressize'] = True

    if lbvserver:
        payload['caaction']['lbvserver'] = True

    if comment:
        payload['caaction']['comment'] = True

    if ns_type:
        payload['caaction']['type'] = True

    if newname:
        payload['caaction']['newname'] = True

    execution = __proxy__['citrixns.post']('config/caaction?action=unset', payload)

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


def unset_capolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None, newname=None,
                   save=False):
    '''
    Unsets values from the capolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    undefaction(bool): Unsets the undefaction value.

    comment(bool): Unsets the comment value.

    logaction(bool): Unsets the logaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.unset_capolicy <args>

    '''

    result = {}

    payload = {'capolicy': {}}

    if name:
        payload['capolicy']['name'] = True

    if rule:
        payload['capolicy']['rule'] = True

    if action:
        payload['capolicy']['action'] = True

    if undefaction:
        payload['capolicy']['undefaction'] = True

    if comment:
        payload['capolicy']['comment'] = True

    if logaction:
        payload['capolicy']['logaction'] = True

    if newname:
        payload['capolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/capolicy?action=unset', payload)

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


def update_caaction(name=None, accumressize=None, lbvserver=None, comment=None, ns_type=None, newname=None, save=False):
    '''
    Update the running configuration for the caaction config key.

    name(str): Name of the content accelerator action. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters.

    accumressize(int): Size of the data, in KB, that the server must respond with. The NetScaler uses this data to compute a
        hash which is then used to lookup within the T2100 appliance.

    lbvserver(str): Name of the load balancing virtual server that has the T2100 appliances as services.

    comment(str): Information about the content accelerator action.

    ns_type(str): Specifies whether the NetScaler must lookup for the response on the T2100 appliance or serve the response
        directly from the server. Possible values = nolookup, lookup, noop

    newname(str): New name for the content accelerator action.  Must begin with a letter, number, or the underscore character
        (_), and must contain only letters, numbers, and the hyphen (-), period (.) hash (#), space ( ), at (@), equals
        (=), colon (:), and underscore characters. Can be changed after the content accelerator policy is added.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my content accelerator action" or my content accelerator
        action). Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.update_caaction <args>

    '''

    result = {}

    payload = {'caaction': {}}

    if name:
        payload['caaction']['name'] = name

    if accumressize:
        payload['caaction']['accumressize'] = accumressize

    if lbvserver:
        payload['caaction']['lbvserver'] = lbvserver

    if comment:
        payload['caaction']['comment'] = comment

    if ns_type:
        payload['caaction']['type'] = ns_type

    if newname:
        payload['caaction']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/caaction', payload)

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


def update_capolicy(name=None, rule=None, action=None, undefaction=None, comment=None, logaction=None, newname=None,
                    save=False):
    '''
    Update the running configuration for the capolicy config key.

    name(str): Name for the content accelerator policy. Must begin with an ASCII alphabetic or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Can be changed after the policy is created.

    rule(str): Expression that determines which requests or responses match the content accelerator policy. When specifying
        the rule in the CLI, the description must be enclosed within double quotes.

    action(str): Name of content accelerator action to be executed when the rule is evaluated to true.

    undefaction(str): .

    comment(str): Information about the content accelerator policy.

    logaction(str): Name of messagelog action to use when a request matches this policy.

    newname(str): New name for the content accelerator policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ca.update_capolicy <args>

    '''

    result = {}

    payload = {'capolicy': {}}

    if name:
        payload['capolicy']['name'] = name

    if rule:
        payload['capolicy']['rule'] = rule

    if action:
        payload['capolicy']['action'] = action

    if undefaction:
        payload['capolicy']['undefaction'] = undefaction

    if comment:
        payload['capolicy']['comment'] = comment

    if logaction:
        payload['capolicy']['logaction'] = logaction

    if newname:
        payload['capolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/capolicy', payload)

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
