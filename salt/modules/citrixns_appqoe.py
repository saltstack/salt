# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the appqoe key.

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

__virtualname__ = 'appqoe'


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

    return False, 'The appqoe execution module can only be loaded for citrixns proxy minions.'


def add_appqoeaction(name=None, priority=None, respondwith=None, customfile=None, altcontentsvcname=None,
                     altcontentpath=None, polqdepth=None, priqdepth=None, maxconn=None, delay=None,
                     dostrigexpression=None, dosaction=None, tcpprofile=None, save=False):
    '''
    Add a new appqoeaction to the running configuration.

    name(str): Name for the AppQoE action. Must begin with a letter, number, or the underscore symbol (_). Other characters
        allowed, after the first character, are the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), and
        colon (:) characters. This is a mandatory argument.

    priority(str): Priority for queuing the request. If server resources are not available for a request that matches the
        configured rule, this option specifies a priority for queuing the request until the server resources are
        available again. If priority is not configured then Lowest priority will be used to queue the request. Possible
        values = HIGH, MEDIUM, LOW, LOWEST

    respondwith(str): Responder action to be taken when the threshold is reached. Available settings function as follows:
        ACS - Serve content from an alternative content service  Threshold : maxConn or delay  NS - Serve from the
        NetScaler appliance (built-in response)  Threshold : maxConn or delay. Possible values = ACS, NS

    customfile(str): name of the HTML page object to use as the response. Minimum length = 1

    altcontentsvcname(str): Name of the alternative content service to be used in the ACS. Minimum length = 1 Maximum length
        = 127

    altcontentpath(str): Path to the alternative content service to be used in the ACS. Minimum length = 4 Maximum length =
        127

    polqdepth(int): Policy queue depth threshold value. When the policy queue size (number of requests queued for the policy
        binding this action is attached to) increases to the specified polqDepth value, subsequent requests are dropped
        to the lowest priority level. Minimum value = 0 Maximum value = 4294967294

    priqdepth(int): Queue depth threshold value per priorirty level. If the queue size (number of requests in the queue of
        that particular priorirty) on the virtual server to which this policy is bound, increases to the specified qDepth
        value, subsequent requests are dropped to the lowest priority level. Minimum value = 0 Maximum value =
        4294967294

    maxconn(int): Maximum number of concurrent connections that can be open for requests that matches with rule. Minimum
        value = 1 Maximum value = 4294967294

    delay(int): Delay threshold, in microseconds, for requests that match the policys rule. If the delay statistics gathered
        for the matching request exceed the specified delay, configured action triggered for that request, if there is no
        action then requests are dropped to the lowest priority level. Minimum value = 1 Maximum value = 599999999

    dostrigexpression(str): Optional expression to add second level check to trigger DoS actions. Specifically used for
        Analytics based DoS response generation.

    dosaction(str): DoS Action to take when vserver will be considered under DoS attack and corresponding rule matches.
        Mandatory if AppQoE actions are to be used for DoS attack prevention. Possible values = SimpleResponse,
        HICResponse

    tcpprofile(str): Bind TCP Profile based on L2/L3/L7 parameters. Minimum length = 1 Maximum length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.add_appqoeaction <args>

    '''

    result = {}

    payload = {'appqoeaction': {}}

    if name:
        payload['appqoeaction']['name'] = name

    if priority:
        payload['appqoeaction']['priority'] = priority

    if respondwith:
        payload['appqoeaction']['respondwith'] = respondwith

    if customfile:
        payload['appqoeaction']['customfile'] = customfile

    if altcontentsvcname:
        payload['appqoeaction']['altcontentsvcname'] = altcontentsvcname

    if altcontentpath:
        payload['appqoeaction']['altcontentpath'] = altcontentpath

    if polqdepth:
        payload['appqoeaction']['polqdepth'] = polqdepth

    if priqdepth:
        payload['appqoeaction']['priqdepth'] = priqdepth

    if maxconn:
        payload['appqoeaction']['maxconn'] = maxconn

    if delay:
        payload['appqoeaction']['delay'] = delay

    if dostrigexpression:
        payload['appqoeaction']['dostrigexpression'] = dostrigexpression

    if dosaction:
        payload['appqoeaction']['dosaction'] = dosaction

    if tcpprofile:
        payload['appqoeaction']['tcpprofile'] = tcpprofile

    execution = __proxy__['citrixns.post']('config/appqoeaction', payload)

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


def add_appqoepolicy(name=None, rule=None, action=None, save=False):
    '''
    Add a new appqoepolicy to the running configuration.

    name(str): . Minimum length = 1

    rule(str): Expression or name of a named expression, against which the request is evaluated. The policy is applied if the
        rule evaluates to true.

    action(str): Configured AppQoE action to trigger. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.add_appqoepolicy <args>

    '''

    result = {}

    payload = {'appqoepolicy': {}}

    if name:
        payload['appqoepolicy']['name'] = name

    if rule:
        payload['appqoepolicy']['rule'] = rule

    if action:
        payload['appqoepolicy']['action'] = action

    execution = __proxy__['citrixns.post']('config/appqoepolicy', payload)

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


def get_appqoeaction(name=None, priority=None, respondwith=None, customfile=None, altcontentsvcname=None,
                     altcontentpath=None, polqdepth=None, priqdepth=None, maxconn=None, delay=None,
                     dostrigexpression=None, dosaction=None, tcpprofile=None):
    '''
    Show the running configuration for the appqoeaction config key.

    name(str): Filters results that only match the name field.

    priority(str): Filters results that only match the priority field.

    respondwith(str): Filters results that only match the respondwith field.

    customfile(str): Filters results that only match the customfile field.

    altcontentsvcname(str): Filters results that only match the altcontentsvcname field.

    altcontentpath(str): Filters results that only match the altcontentpath field.

    polqdepth(int): Filters results that only match the polqdepth field.

    priqdepth(int): Filters results that only match the priqdepth field.

    maxconn(int): Filters results that only match the maxconn field.

    delay(int): Filters results that only match the delay field.

    dostrigexpression(str): Filters results that only match the dostrigexpression field.

    dosaction(str): Filters results that only match the dosaction field.

    tcpprofile(str): Filters results that only match the tcpprofile field.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.get_appqoeaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if priority:
        search_filter.append(['priority', priority])

    if respondwith:
        search_filter.append(['respondwith', respondwith])

    if customfile:
        search_filter.append(['customfile', customfile])

    if altcontentsvcname:
        search_filter.append(['altcontentsvcname', altcontentsvcname])

    if altcontentpath:
        search_filter.append(['altcontentpath', altcontentpath])

    if polqdepth:
        search_filter.append(['polqdepth', polqdepth])

    if priqdepth:
        search_filter.append(['priqdepth', priqdepth])

    if maxconn:
        search_filter.append(['maxconn', maxconn])

    if delay:
        search_filter.append(['delay', delay])

    if dostrigexpression:
        search_filter.append(['dostrigexpression', dostrigexpression])

    if dosaction:
        search_filter.append(['dosaction', dosaction])

    if tcpprofile:
        search_filter.append(['tcpprofile', tcpprofile])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appqoeaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appqoeaction')

    return response


def get_appqoecustomresp(src=None, name=None):
    '''
    Show the running configuration for the appqoecustomresp config key.

    src(str): Filters results that only match the src field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.get_appqoecustomresp

    '''

    search_filter = []

    if src:
        search_filter.append(['src', src])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appqoecustomresp{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appqoecustomresp')

    return response


def get_appqoeparameter():
    '''
    Show the running configuration for the appqoeparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.get_appqoeparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appqoeparameter'), 'appqoeparameter')

    return response


def get_appqoepolicy(name=None, rule=None, action=None):
    '''
    Show the running configuration for the appqoepolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    action(str): Filters results that only match the action field.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.get_appqoepolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if action:
        search_filter.append(['action', action])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appqoepolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appqoepolicy')

    return response


def get_appqoepolicy_binding():
    '''
    Show the running configuration for the appqoepolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.get_appqoepolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appqoepolicy_binding'), 'appqoepolicy_binding')

    return response


def get_appqoepolicy_lbvserver_binding(name=None, boundto=None):
    '''
    Show the running configuration for the appqoepolicy_lbvserver_binding config key.

    name(str): Filters results that only match the name field.

    boundto(str): Filters results that only match the boundto field.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.get_appqoepolicy_lbvserver_binding

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if boundto:
        search_filter.append(['boundto', boundto])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/appqoepolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'appqoepolicy_lbvserver_binding')

    return response


def unset_appqoeaction(name=None, priority=None, respondwith=None, customfile=None, altcontentsvcname=None,
                       altcontentpath=None, polqdepth=None, priqdepth=None, maxconn=None, delay=None,
                       dostrigexpression=None, dosaction=None, tcpprofile=None, save=False):
    '''
    Unsets values from the appqoeaction configuration key.

    name(bool): Unsets the name value.

    priority(bool): Unsets the priority value.

    respondwith(bool): Unsets the respondwith value.

    customfile(bool): Unsets the customfile value.

    altcontentsvcname(bool): Unsets the altcontentsvcname value.

    altcontentpath(bool): Unsets the altcontentpath value.

    polqdepth(bool): Unsets the polqdepth value.

    priqdepth(bool): Unsets the priqdepth value.

    maxconn(bool): Unsets the maxconn value.

    delay(bool): Unsets the delay value.

    dostrigexpression(bool): Unsets the dostrigexpression value.

    dosaction(bool): Unsets the dosaction value.

    tcpprofile(bool): Unsets the tcpprofile value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.unset_appqoeaction <args>

    '''

    result = {}

    payload = {'appqoeaction': {}}

    if name:
        payload['appqoeaction']['name'] = True

    if priority:
        payload['appqoeaction']['priority'] = True

    if respondwith:
        payload['appqoeaction']['respondwith'] = True

    if customfile:
        payload['appqoeaction']['customfile'] = True

    if altcontentsvcname:
        payload['appqoeaction']['altcontentsvcname'] = True

    if altcontentpath:
        payload['appqoeaction']['altcontentpath'] = True

    if polqdepth:
        payload['appqoeaction']['polqdepth'] = True

    if priqdepth:
        payload['appqoeaction']['priqdepth'] = True

    if maxconn:
        payload['appqoeaction']['maxconn'] = True

    if delay:
        payload['appqoeaction']['delay'] = True

    if dostrigexpression:
        payload['appqoeaction']['dostrigexpression'] = True

    if dosaction:
        payload['appqoeaction']['dosaction'] = True

    if tcpprofile:
        payload['appqoeaction']['tcpprofile'] = True

    execution = __proxy__['citrixns.post']('config/appqoeaction?action=unset', payload)

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


def unset_appqoeparameter(sessionlife=None, avgwaitingclient=None, maxaltrespbandwidth=None, dosattackthresh=None,
                          save=False):
    '''
    Unsets values from the appqoeparameter configuration key.

    sessionlife(bool): Unsets the sessionlife value.

    avgwaitingclient(bool): Unsets the avgwaitingclient value.

    maxaltrespbandwidth(bool): Unsets the maxaltrespbandwidth value.

    dosattackthresh(bool): Unsets the dosattackthresh value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.unset_appqoeparameter <args>

    '''

    result = {}

    payload = {'appqoeparameter': {}}

    if sessionlife:
        payload['appqoeparameter']['sessionlife'] = True

    if avgwaitingclient:
        payload['appqoeparameter']['avgwaitingclient'] = True

    if maxaltrespbandwidth:
        payload['appqoeparameter']['maxaltrespbandwidth'] = True

    if dosattackthresh:
        payload['appqoeparameter']['dosattackthresh'] = True

    execution = __proxy__['citrixns.post']('config/appqoeparameter?action=unset', payload)

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


def update_appqoeaction(name=None, priority=None, respondwith=None, customfile=None, altcontentsvcname=None,
                        altcontentpath=None, polqdepth=None, priqdepth=None, maxconn=None, delay=None,
                        dostrigexpression=None, dosaction=None, tcpprofile=None, save=False):
    '''
    Update the running configuration for the appqoeaction config key.

    name(str): Name for the AppQoE action. Must begin with a letter, number, or the underscore symbol (_). Other characters
        allowed, after the first character, are the hyphen (-), period (.) hash (#), space ( ), at (@), equals (=), and
        colon (:) characters. This is a mandatory argument.

    priority(str): Priority for queuing the request. If server resources are not available for a request that matches the
        configured rule, this option specifies a priority for queuing the request until the server resources are
        available again. If priority is not configured then Lowest priority will be used to queue the request. Possible
        values = HIGH, MEDIUM, LOW, LOWEST

    respondwith(str): Responder action to be taken when the threshold is reached. Available settings function as follows:
        ACS - Serve content from an alternative content service  Threshold : maxConn or delay  NS - Serve from the
        NetScaler appliance (built-in response)  Threshold : maxConn or delay. Possible values = ACS, NS

    customfile(str): name of the HTML page object to use as the response. Minimum length = 1

    altcontentsvcname(str): Name of the alternative content service to be used in the ACS. Minimum length = 1 Maximum length
        = 127

    altcontentpath(str): Path to the alternative content service to be used in the ACS. Minimum length = 4 Maximum length =
        127

    polqdepth(int): Policy queue depth threshold value. When the policy queue size (number of requests queued for the policy
        binding this action is attached to) increases to the specified polqDepth value, subsequent requests are dropped
        to the lowest priority level. Minimum value = 0 Maximum value = 4294967294

    priqdepth(int): Queue depth threshold value per priorirty level. If the queue size (number of requests in the queue of
        that particular priorirty) on the virtual server to which this policy is bound, increases to the specified qDepth
        value, subsequent requests are dropped to the lowest priority level. Minimum value = 0 Maximum value =
        4294967294

    maxconn(int): Maximum number of concurrent connections that can be open for requests that matches with rule. Minimum
        value = 1 Maximum value = 4294967294

    delay(int): Delay threshold, in microseconds, for requests that match the policys rule. If the delay statistics gathered
        for the matching request exceed the specified delay, configured action triggered for that request, if there is no
        action then requests are dropped to the lowest priority level. Minimum value = 1 Maximum value = 599999999

    dostrigexpression(str): Optional expression to add second level check to trigger DoS actions. Specifically used for
        Analytics based DoS response generation.

    dosaction(str): DoS Action to take when vserver will be considered under DoS attack and corresponding rule matches.
        Mandatory if AppQoE actions are to be used for DoS attack prevention. Possible values = SimpleResponse,
        HICResponse

    tcpprofile(str): Bind TCP Profile based on L2/L3/L7 parameters. Minimum length = 1 Maximum length = 127

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.update_appqoeaction <args>

    '''

    result = {}

    payload = {'appqoeaction': {}}

    if name:
        payload['appqoeaction']['name'] = name

    if priority:
        payload['appqoeaction']['priority'] = priority

    if respondwith:
        payload['appqoeaction']['respondwith'] = respondwith

    if customfile:
        payload['appqoeaction']['customfile'] = customfile

    if altcontentsvcname:
        payload['appqoeaction']['altcontentsvcname'] = altcontentsvcname

    if altcontentpath:
        payload['appqoeaction']['altcontentpath'] = altcontentpath

    if polqdepth:
        payload['appqoeaction']['polqdepth'] = polqdepth

    if priqdepth:
        payload['appqoeaction']['priqdepth'] = priqdepth

    if maxconn:
        payload['appqoeaction']['maxconn'] = maxconn

    if delay:
        payload['appqoeaction']['delay'] = delay

    if dostrigexpression:
        payload['appqoeaction']['dostrigexpression'] = dostrigexpression

    if dosaction:
        payload['appqoeaction']['dosaction'] = dosaction

    if tcpprofile:
        payload['appqoeaction']['tcpprofile'] = tcpprofile

    execution = __proxy__['citrixns.put']('config/appqoeaction', payload)

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


def update_appqoeparameter(sessionlife=None, avgwaitingclient=None, maxaltrespbandwidth=None, dosattackthresh=None,
                           save=False):
    '''
    Update the running configuration for the appqoeparameter config key.

    sessionlife(int): Time, in seconds, between the first time and the next time the AppQoE alternative content window is
        displayed. The alternative content window is displayed only once during a session for the same browser accessing
        a configured URL, so this parameter determines the length of a session. Default value: 300 Minimum value = 1
        Maximum value = 4294967294

    avgwaitingclient(int): average number of client connections, that can sit in service waiting queue. Default value:
        1000000 Minimum value = 0 Maximum value = 4294967294

    maxaltrespbandwidth(int): maximum bandwidth which will determine whether to send alternate content response. Default
        value: 100 Minimum value = 1 Maximum value = 4294967294

    dosattackthresh(int): average number of client connection that can queue up on vserver level without triggering DoS
        mitigation module. Default value: 2000 Minimum value = 0 Maximum value = 4294967294

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.update_appqoeparameter <args>

    '''

    result = {}

    payload = {'appqoeparameter': {}}

    if sessionlife:
        payload['appqoeparameter']['sessionlife'] = sessionlife

    if avgwaitingclient:
        payload['appqoeparameter']['avgwaitingclient'] = avgwaitingclient

    if maxaltrespbandwidth:
        payload['appqoeparameter']['maxaltrespbandwidth'] = maxaltrespbandwidth

    if dosattackthresh:
        payload['appqoeparameter']['dosattackthresh'] = dosattackthresh

    execution = __proxy__['citrixns.put']('config/appqoeparameter', payload)

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


def update_appqoepolicy(name=None, rule=None, action=None, save=False):
    '''
    Update the running configuration for the appqoepolicy config key.

    name(str): . Minimum length = 1

    rule(str): Expression or name of a named expression, against which the request is evaluated. The policy is applied if the
        rule evaluates to true.

    action(str): Configured AppQoE action to trigger. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' appqoe.update_appqoepolicy <args>

    '''

    result = {}

    payload = {'appqoepolicy': {}}

    if name:
        payload['appqoepolicy']['name'] = name

    if rule:
        payload['appqoepolicy']['rule'] = rule

    if action:
        payload['appqoepolicy']['action'] = action

    execution = __proxy__['citrixns.put']('config/appqoepolicy', payload)

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
