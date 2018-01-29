# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the router key.

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

__virtualname__ = 'router'


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

    return False, 'The router execution module can only be loaded for citrixns proxy minions.'


def add_routerdynamicrouting(commandstring=None, nodeid=None, save=False):
    '''
    Add a new routerdynamicrouting to the running configuration.

    commandstring(str): command to be executed.

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' router.add_routerdynamicrouting <args>

    '''

    result = {}

    payload = {'routerdynamicrouting': {}}

    if commandstring:
        payload['routerdynamicrouting']['commandstring'] = commandstring

    if nodeid:
        payload['routerdynamicrouting']['nodeid'] = nodeid

    execution = __proxy__['citrixns.post']('config/routerdynamicrouting', payload)

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


def get_routerdynamicrouting(commandstring=None, nodeid=None):
    '''
    Show the running configuration for the routerdynamicrouting config key.

    commandstring(str): Filters results that only match the commandstring field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' router.get_routerdynamicrouting

    '''

    search_filter = []

    if commandstring:
        search_filter.append(['commandstring', commandstring])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/routerdynamicrouting{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'routerdynamicrouting')

    return response


def unset_routerdynamicrouting(commandstring=None, nodeid=None, save=False):
    '''
    Unsets values from the routerdynamicrouting configuration key.

    commandstring(bool): Unsets the commandstring value.

    nodeid(bool): Unsets the nodeid value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' router.unset_routerdynamicrouting <args>

    '''

    result = {}

    payload = {'routerdynamicrouting': {}}

    if commandstring:
        payload['routerdynamicrouting']['commandstring'] = True

    if nodeid:
        payload['routerdynamicrouting']['nodeid'] = True

    execution = __proxy__['citrixns.post']('config/routerdynamicrouting?action=unset', payload)

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


def update_routerdynamicrouting(commandstring=None, nodeid=None, save=False):
    '''
    Update the running configuration for the routerdynamicrouting config key.

    commandstring(str): command to be executed.

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' router.update_routerdynamicrouting <args>

    '''

    result = {}

    payload = {'routerdynamicrouting': {}}

    if commandstring:
        payload['routerdynamicrouting']['commandstring'] = commandstring

    if nodeid:
        payload['routerdynamicrouting']['nodeid'] = nodeid

    execution = __proxy__['citrixns.put']('config/routerdynamicrouting', payload)

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
