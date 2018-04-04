# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the reputation key.

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

__virtualname__ = 'reputation'


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

    return False, 'The reputation execution module can only be loaded for citrixns proxy minions.'


def get_reputationsettings():
    '''
    Show the running configuration for the reputationsettings config key.

    CLI Example:

    .. code-block:: bash

    salt '*' reputation.get_reputationsettings

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/reputationsettings'), 'reputationsettings')

    return response


def unset_reputationsettings(proxyserver=None, proxyport=None, save=False):
    '''
    Unsets values from the reputationsettings configuration key.

    proxyserver(bool): Unsets the proxyserver value.

    proxyport(bool): Unsets the proxyport value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' reputation.unset_reputationsettings <args>

    '''

    result = {}

    payload = {'reputationsettings': {}}

    if proxyserver:
        payload['reputationsettings']['proxyserver'] = True

    if proxyport:
        payload['reputationsettings']['proxyport'] = True

    execution = __proxy__['citrixns.post']('config/reputationsettings?action=unset', payload)

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


def update_reputationsettings(proxyserver=None, proxyport=None, save=False):
    '''
    Update the running configuration for the reputationsettings config key.

    proxyserver(str): Proxy server IP to get Reputation data. Minimum length = 1

    proxyport(int): Proxy server port.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' reputation.update_reputationsettings <args>

    '''

    result = {}

    payload = {'reputationsettings': {}}

    if proxyserver:
        payload['reputationsettings']['proxyserver'] = proxyserver

    if proxyport:
        payload['reputationsettings']['proxyport'] = proxyport

    execution = __proxy__['citrixns.put']('config/reputationsettings', payload)

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
