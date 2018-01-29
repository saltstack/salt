# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the autoscale key.

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

__virtualname__ = 'autoscale'


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

    return False, 'The autoscale execution module can only be loaded for citrixns proxy minions.'


def add_autoscaleaction(name=None, ns_type=None, profilename=None, parameters=None, vmdestroygraceperiod=None,
                        quiettime=None, vserver=None, save=False):
    '''
    Add a new autoscaleaction to the running configuration.

    name(str): ActionScale action name. Minimum length = 1

    ns_type(str): The type of action. Possible values = SCALE_UP, SCALE_DOWN

    profilename(str): AutoScale profile name. Minimum length = 1

    parameters(str): Parameters to use in the action. Minimum length = 1

    vmdestroygraceperiod(int): Time in minutes a VM is kept in inactive state before destroying. Default value: 10

    quiettime(int): Time in seconds no other policy is evaluated or action is taken. Default value: 300

    vserver(str): Name of the vserver on which autoscale action has to be taken.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.add_autoscaleaction <args>

    '''

    result = {}

    payload = {'autoscaleaction': {}}

    if name:
        payload['autoscaleaction']['name'] = name

    if ns_type:
        payload['autoscaleaction']['type'] = ns_type

    if profilename:
        payload['autoscaleaction']['profilename'] = profilename

    if parameters:
        payload['autoscaleaction']['parameters'] = parameters

    if vmdestroygraceperiod:
        payload['autoscaleaction']['vmdestroygraceperiod'] = vmdestroygraceperiod

    if quiettime:
        payload['autoscaleaction']['quiettime'] = quiettime

    if vserver:
        payload['autoscaleaction']['vserver'] = vserver

    execution = __proxy__['citrixns.post']('config/autoscaleaction', payload)

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


def add_autoscalepolicy(name=None, rule=None, action=None, comment=None, logaction=None, newname=None, save=False):
    '''
    Add a new autoscalepolicy to the running configuration.

    name(str): The name of the autoscale policy. Minimum length = 1

    rule(str): The rule associated with the policy.

    action(str): The autoscale profile associated with the policy. Minimum length = 1

    comment(str): Comments associated with this autoscale policy.

    logaction(str): The log action associated with the autoscale policy.

    newname(str): The new name of the autoscale policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.add_autoscalepolicy <args>

    '''

    result = {}

    payload = {'autoscalepolicy': {}}

    if name:
        payload['autoscalepolicy']['name'] = name

    if rule:
        payload['autoscalepolicy']['rule'] = rule

    if action:
        payload['autoscalepolicy']['action'] = action

    if comment:
        payload['autoscalepolicy']['comment'] = comment

    if logaction:
        payload['autoscalepolicy']['logaction'] = logaction

    if newname:
        payload['autoscalepolicy']['newname'] = newname

    execution = __proxy__['citrixns.post']('config/autoscalepolicy', payload)

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


def add_autoscaleprofile(name=None, ns_type=None, url=None, apikey=None, sharedsecret=None, save=False):
    '''
    Add a new autoscaleprofile to the running configuration.

    name(str): AutoScale profile name. Minimum length = 1

    ns_type(str): The type of profile. Possible values = CLOUDSTACK

    url(str): URL providing the service. Minimum length = 1

    apikey(str): api key for authentication with service. Minimum length = 1

    sharedsecret(str): shared secret for authentication with service. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.add_autoscaleprofile <args>

    '''

    result = {}

    payload = {'autoscaleprofile': {}}

    if name:
        payload['autoscaleprofile']['name'] = name

    if ns_type:
        payload['autoscaleprofile']['type'] = ns_type

    if url:
        payload['autoscaleprofile']['url'] = url

    if apikey:
        payload['autoscaleprofile']['apikey'] = apikey

    if sharedsecret:
        payload['autoscaleprofile']['sharedsecret'] = sharedsecret

    execution = __proxy__['citrixns.post']('config/autoscaleprofile', payload)

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


def get_autoscaleaction(name=None, ns_type=None, profilename=None, parameters=None, vmdestroygraceperiod=None,
                        quiettime=None, vserver=None):
    '''
    Show the running configuration for the autoscaleaction config key.

    name(str): Filters results that only match the name field.

    ns_type(str): Filters results that only match the type field.

    profilename(str): Filters results that only match the profilename field.

    parameters(str): Filters results that only match the parameters field.

    vmdestroygraceperiod(int): Filters results that only match the vmdestroygraceperiod field.

    quiettime(int): Filters results that only match the quiettime field.

    vserver(str): Filters results that only match the vserver field.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.get_autoscaleaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ns_type:
        search_filter.append(['type', ns_type])

    if profilename:
        search_filter.append(['profilename', profilename])

    if parameters:
        search_filter.append(['parameters', parameters])

    if vmdestroygraceperiod:
        search_filter.append(['vmdestroygraceperiod', vmdestroygraceperiod])

    if quiettime:
        search_filter.append(['quiettime', quiettime])

    if vserver:
        search_filter.append(['vserver', vserver])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/autoscaleaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'autoscaleaction')

    return response


def get_autoscalepolicy(name=None, rule=None, action=None, comment=None, logaction=None, newname=None):
    '''
    Show the running configuration for the autoscalepolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    comment(str): Filters results that only match the comment field.

    logaction(str): Filters results that only match the logaction field.

    newname(str): Filters results that only match the newname field.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.get_autoscalepolicy

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

    if logaction:
        search_filter.append(['logaction', logaction])

    if newname:
        search_filter.append(['newname', newname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/autoscalepolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'autoscalepolicy')

    return response


def get_autoscalepolicy_binding():
    '''
    Show the running configuration for the autoscalepolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.get_autoscalepolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/autoscalepolicy_binding'), 'autoscalepolicy_binding')

    return response


def get_autoscalepolicy_nstimer_binding(boundto=None, name=None):
    '''
    Show the running configuration for the autoscalepolicy_nstimer_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.get_autoscalepolicy_nstimer_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/autoscalepolicy_nstimer_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'autoscalepolicy_nstimer_binding')

    return response


def get_autoscaleprofile(name=None, ns_type=None, url=None, apikey=None, sharedsecret=None):
    '''
    Show the running configuration for the autoscaleprofile config key.

    name(str): Filters results that only match the name field.

    ns_type(str): Filters results that only match the type field.

    url(str): Filters results that only match the url field.

    apikey(str): Filters results that only match the apikey field.

    sharedsecret(str): Filters results that only match the sharedsecret field.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.get_autoscaleprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ns_type:
        search_filter.append(['type', ns_type])

    if url:
        search_filter.append(['url', url])

    if apikey:
        search_filter.append(['apikey', apikey])

    if sharedsecret:
        search_filter.append(['sharedsecret', sharedsecret])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/autoscaleprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'autoscaleprofile')

    return response


def unset_autoscaleaction(name=None, ns_type=None, profilename=None, parameters=None, vmdestroygraceperiod=None,
                          quiettime=None, vserver=None, save=False):
    '''
    Unsets values from the autoscaleaction configuration key.

    name(bool): Unsets the name value.

    ns_type(bool): Unsets the ns_type value.

    profilename(bool): Unsets the profilename value.

    parameters(bool): Unsets the parameters value.

    vmdestroygraceperiod(bool): Unsets the vmdestroygraceperiod value.

    quiettime(bool): Unsets the quiettime value.

    vserver(bool): Unsets the vserver value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.unset_autoscaleaction <args>

    '''

    result = {}

    payload = {'autoscaleaction': {}}

    if name:
        payload['autoscaleaction']['name'] = True

    if ns_type:
        payload['autoscaleaction']['type'] = True

    if profilename:
        payload['autoscaleaction']['profilename'] = True

    if parameters:
        payload['autoscaleaction']['parameters'] = True

    if vmdestroygraceperiod:
        payload['autoscaleaction']['vmdestroygraceperiod'] = True

    if quiettime:
        payload['autoscaleaction']['quiettime'] = True

    if vserver:
        payload['autoscaleaction']['vserver'] = True

    execution = __proxy__['citrixns.post']('config/autoscaleaction?action=unset', payload)

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


def unset_autoscalepolicy(name=None, rule=None, action=None, comment=None, logaction=None, newname=None, save=False):
    '''
    Unsets values from the autoscalepolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    action(bool): Unsets the action value.

    comment(bool): Unsets the comment value.

    logaction(bool): Unsets the logaction value.

    newname(bool): Unsets the newname value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.unset_autoscalepolicy <args>

    '''

    result = {}

    payload = {'autoscalepolicy': {}}

    if name:
        payload['autoscalepolicy']['name'] = True

    if rule:
        payload['autoscalepolicy']['rule'] = True

    if action:
        payload['autoscalepolicy']['action'] = True

    if comment:
        payload['autoscalepolicy']['comment'] = True

    if logaction:
        payload['autoscalepolicy']['logaction'] = True

    if newname:
        payload['autoscalepolicy']['newname'] = True

    execution = __proxy__['citrixns.post']('config/autoscalepolicy?action=unset', payload)

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


def update_autoscaleaction(name=None, ns_type=None, profilename=None, parameters=None, vmdestroygraceperiod=None,
                           quiettime=None, vserver=None, save=False):
    '''
    Update the running configuration for the autoscaleaction config key.

    name(str): ActionScale action name. Minimum length = 1

    ns_type(str): The type of action. Possible values = SCALE_UP, SCALE_DOWN

    profilename(str): AutoScale profile name. Minimum length = 1

    parameters(str): Parameters to use in the action. Minimum length = 1

    vmdestroygraceperiod(int): Time in minutes a VM is kept in inactive state before destroying. Default value: 10

    quiettime(int): Time in seconds no other policy is evaluated or action is taken. Default value: 300

    vserver(str): Name of the vserver on which autoscale action has to be taken.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.update_autoscaleaction <args>

    '''

    result = {}

    payload = {'autoscaleaction': {}}

    if name:
        payload['autoscaleaction']['name'] = name

    if ns_type:
        payload['autoscaleaction']['type'] = ns_type

    if profilename:
        payload['autoscaleaction']['profilename'] = profilename

    if parameters:
        payload['autoscaleaction']['parameters'] = parameters

    if vmdestroygraceperiod:
        payload['autoscaleaction']['vmdestroygraceperiod'] = vmdestroygraceperiod

    if quiettime:
        payload['autoscaleaction']['quiettime'] = quiettime

    if vserver:
        payload['autoscaleaction']['vserver'] = vserver

    execution = __proxy__['citrixns.put']('config/autoscaleaction', payload)

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


def update_autoscalepolicy(name=None, rule=None, action=None, comment=None, logaction=None, newname=None, save=False):
    '''
    Update the running configuration for the autoscalepolicy config key.

    name(str): The name of the autoscale policy. Minimum length = 1

    rule(str): The rule associated with the policy.

    action(str): The autoscale profile associated with the policy. Minimum length = 1

    comment(str): Comments associated with this autoscale policy.

    logaction(str): The log action associated with the autoscale policy.

    newname(str): The new name of the autoscale policy. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.update_autoscalepolicy <args>

    '''

    result = {}

    payload = {'autoscalepolicy': {}}

    if name:
        payload['autoscalepolicy']['name'] = name

    if rule:
        payload['autoscalepolicy']['rule'] = rule

    if action:
        payload['autoscalepolicy']['action'] = action

    if comment:
        payload['autoscalepolicy']['comment'] = comment

    if logaction:
        payload['autoscalepolicy']['logaction'] = logaction

    if newname:
        payload['autoscalepolicy']['newname'] = newname

    execution = __proxy__['citrixns.put']('config/autoscalepolicy', payload)

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


def update_autoscaleprofile(name=None, ns_type=None, url=None, apikey=None, sharedsecret=None, save=False):
    '''
    Update the running configuration for the autoscaleprofile config key.

    name(str): AutoScale profile name. Minimum length = 1

    ns_type(str): The type of profile. Possible values = CLOUDSTACK

    url(str): URL providing the service. Minimum length = 1

    apikey(str): api key for authentication with service. Minimum length = 1

    sharedsecret(str): shared secret for authentication with service. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' autoscale.update_autoscaleprofile <args>

    '''

    result = {}

    payload = {'autoscaleprofile': {}}

    if name:
        payload['autoscaleprofile']['name'] = name

    if ns_type:
        payload['autoscaleprofile']['type'] = ns_type

    if url:
        payload['autoscaleprofile']['url'] = url

    if apikey:
        payload['autoscaleprofile']['apikey'] = apikey

    if sharedsecret:
        payload['autoscaleprofile']['sharedsecret'] = sharedsecret

    execution = __proxy__['citrixns.put']('config/autoscaleprofile', payload)

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
