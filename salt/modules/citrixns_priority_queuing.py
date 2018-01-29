# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the priority-queuing key.

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

__virtualname__ = 'priority_queuing'


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

    return False, 'The priority_queuing execution module can only be loaded for citrixns proxy minions.'


def add_pqpolicy(policyname=None, rule=None, priority=None, weight=None, qdepth=None, polqdepth=None, save=False):
    '''
    Add a new pqpolicy to the running configuration.

    policyname(str): Name for the priority queuing policy. Must begin with a letter, number, or the underscore symbol (_).
        Other characters allowed, after the first character, are the hyphen (-), period (.) hash (#), space ( ), at (@),
        equals (=), and colon (:) characters. Minimum length = 1

    rule(str): Expression or name of a named expression, against which the request is evaluated. The priority queuing policy
        is applied if the rule evaluates to true.  Note: * On the command line interface, if the expression includes
        blank spaces, the entire expression must be enclosed in double quotation marks. * If the expression itself
        includes double quotation marks, you must escape the quotations by using the \\ character.  * Alternatively, you
        can use single quotation marks to enclose the rule, in which case you will not have to escape the double
        quotation marks. * Maximum length of a string literal in the expression is 255 characters. A longer string can be
        split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;".

    priority(int): Priority for queuing the request. If server resources are not available for a request that matches the
        configured rule, this option specifies a priority for queuing the request until the server resources are
        available again. Enter the value of positive_integer as 1, 2 or 3. The highest priority level is 1 and the lowest
        priority value is 3. Minimum value = 1 Maximum value = 3

    weight(int): Weight of the priority. Each priority is assigned a weight according to which it is served when server
        resources are available. The weight for a higher priority request must be set higher than that of a lower
        priority request. To prevent delays for low-priority requests across multiple priority levels, you can configure
        weighted queuing for serving requests. The default weights for the priorities are: * Gold - Priority 1 - Weight 3
        * Silver - Priority 2 - Weight 2 * Bronze - Priority 3 - Weight 1 Specify the weights as 0 through 101. A weight
        of 0 indicates that the particular priority level should be served only when there are no requests in any of the
        priority queues. A weight of 101 specifies a weight of infinity. This means that this priority level is served
        irrespective of the number of clients waiting in other priority queues. Minimum value = 0 Maximum value = 101

    qdepth(int): Queue depth threshold value. When the queue size (number of requests in the queue) on the virtual server to
        which this policy is bound, increases to the specified qDepth value, subsequent requests are dropped to the
        lowest priority level. Default value: 0 Minimum value = 0 Maximum value = 4294967294

    polqdepth(int): Policy queue depth threshold value. When the policy queue size (number of requests in all the queues
        belonging to this policy) increases to the specified polqDepth value, subsequent requests are dropped to the
        lowest priority level. Default value: 0 Minimum value = 0 Maximum value = 4294967294

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' priority_queuing.add_pqpolicy <args>

    '''

    result = {}

    payload = {'pqpolicy': {}}

    if policyname:
        payload['pqpolicy']['policyname'] = policyname

    if rule:
        payload['pqpolicy']['rule'] = rule

    if priority:
        payload['pqpolicy']['priority'] = priority

    if weight:
        payload['pqpolicy']['weight'] = weight

    if qdepth:
        payload['pqpolicy']['qdepth'] = qdepth

    if polqdepth:
        payload['pqpolicy']['polqdepth'] = polqdepth

    execution = __proxy__['citrixns.post']('config/pqpolicy', payload)

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


def get_pqbinding(vservername=None):
    '''
    Show the running configuration for the pqbinding config key.

    vservername(str): Filters results that only match the vservername field.

    CLI Example:

    .. code-block:: bash

    salt '*' priority_queuing.get_pqbinding

    '''

    search_filter = []

    if vservername:
        search_filter.append(['vservername', vservername])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/pqbinding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'pqbinding')

    return response


def get_pqpolicy(policyname=None, rule=None, priority=None, weight=None, qdepth=None, polqdepth=None):
    '''
    Show the running configuration for the pqpolicy config key.

    policyname(str): Filters results that only match the policyname field.

    rule(str): Filters results that only match the rule field.

    priority(int): Filters results that only match the priority field.

    weight(int): Filters results that only match the weight field.

    qdepth(int): Filters results that only match the qdepth field.

    polqdepth(int): Filters results that only match the polqdepth field.

    CLI Example:

    .. code-block:: bash

    salt '*' priority_queuing.get_pqpolicy

    '''

    search_filter = []

    if policyname:
        search_filter.append(['policyname', policyname])

    if rule:
        search_filter.append(['rule', rule])

    if priority:
        search_filter.append(['priority', priority])

    if weight:
        search_filter.append(['weight', weight])

    if qdepth:
        search_filter.append(['qdepth', qdepth])

    if polqdepth:
        search_filter.append(['polqdepth', polqdepth])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/pqpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'pqpolicy')

    return response


def unset_pqpolicy(policyname=None, rule=None, priority=None, weight=None, qdepth=None, polqdepth=None, save=False):
    '''
    Unsets values from the pqpolicy configuration key.

    policyname(bool): Unsets the policyname value.

    rule(bool): Unsets the rule value.

    priority(bool): Unsets the priority value.

    weight(bool): Unsets the weight value.

    qdepth(bool): Unsets the qdepth value.

    polqdepth(bool): Unsets the polqdepth value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' priority_queuing.unset_pqpolicy <args>

    '''

    result = {}

    payload = {'pqpolicy': {}}

    if policyname:
        payload['pqpolicy']['policyname'] = True

    if rule:
        payload['pqpolicy']['rule'] = True

    if priority:
        payload['pqpolicy']['priority'] = True

    if weight:
        payload['pqpolicy']['weight'] = True

    if qdepth:
        payload['pqpolicy']['qdepth'] = True

    if polqdepth:
        payload['pqpolicy']['polqdepth'] = True

    execution = __proxy__['citrixns.post']('config/pqpolicy?action=unset', payload)

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


def update_pqpolicy(policyname=None, rule=None, priority=None, weight=None, qdepth=None, polqdepth=None, save=False):
    '''
    Update the running configuration for the pqpolicy config key.

    policyname(str): Name for the priority queuing policy. Must begin with a letter, number, or the underscore symbol (_).
        Other characters allowed, after the first character, are the hyphen (-), period (.) hash (#), space ( ), at (@),
        equals (=), and colon (:) characters. Minimum length = 1

    rule(str): Expression or name of a named expression, against which the request is evaluated. The priority queuing policy
        is applied if the rule evaluates to true.  Note: * On the command line interface, if the expression includes
        blank spaces, the entire expression must be enclosed in double quotation marks. * If the expression itself
        includes double quotation marks, you must escape the quotations by using the \\ character.  * Alternatively, you
        can use single quotation marks to enclose the rule, in which case you will not have to escape the double
        quotation marks. * Maximum length of a string literal in the expression is 255 characters. A longer string can be
        split into smaller strings of up to 255 characters each, and the smaller strings concatenated with the +
        operator. For example, you can create a 500-character string as follows: ";lt;string of 255 characters;gt;" +
        ";lt;string of 245 characters;gt;".

    priority(int): Priority for queuing the request. If server resources are not available for a request that matches the
        configured rule, this option specifies a priority for queuing the request until the server resources are
        available again. Enter the value of positive_integer as 1, 2 or 3. The highest priority level is 1 and the lowest
        priority value is 3. Minimum value = 1 Maximum value = 3

    weight(int): Weight of the priority. Each priority is assigned a weight according to which it is served when server
        resources are available. The weight for a higher priority request must be set higher than that of a lower
        priority request. To prevent delays for low-priority requests across multiple priority levels, you can configure
        weighted queuing for serving requests. The default weights for the priorities are: * Gold - Priority 1 - Weight 3
        * Silver - Priority 2 - Weight 2 * Bronze - Priority 3 - Weight 1 Specify the weights as 0 through 101. A weight
        of 0 indicates that the particular priority level should be served only when there are no requests in any of the
        priority queues. A weight of 101 specifies a weight of infinity. This means that this priority level is served
        irrespective of the number of clients waiting in other priority queues. Minimum value = 0 Maximum value = 101

    qdepth(int): Queue depth threshold value. When the queue size (number of requests in the queue) on the virtual server to
        which this policy is bound, increases to the specified qDepth value, subsequent requests are dropped to the
        lowest priority level. Default value: 0 Minimum value = 0 Maximum value = 4294967294

    polqdepth(int): Policy queue depth threshold value. When the policy queue size (number of requests in all the queues
        belonging to this policy) increases to the specified polqDepth value, subsequent requests are dropped to the
        lowest priority level. Default value: 0 Minimum value = 0 Maximum value = 4294967294

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' priority_queuing.update_pqpolicy <args>

    '''

    result = {}

    payload = {'pqpolicy': {}}

    if policyname:
        payload['pqpolicy']['policyname'] = policyname

    if rule:
        payload['pqpolicy']['rule'] = rule

    if priority:
        payload['pqpolicy']['priority'] = priority

    if weight:
        payload['pqpolicy']['weight'] = weight

    if qdepth:
        payload['pqpolicy']['qdepth'] = qdepth

    if polqdepth:
        payload['pqpolicy']['polqdepth'] = polqdepth

    execution = __proxy__['citrixns.put']('config/pqpolicy', payload)

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
