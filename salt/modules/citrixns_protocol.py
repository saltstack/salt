# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the protocol key.

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

__virtualname__ = 'protocol'


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

    return False, 'The protocol execution module can only be loaded for citrixns proxy minions.'


def get_protocolhttpband():
    '''
    Show the running configuration for the protocolhttpband config key.

    CLI Example:

    .. code-block:: bash

    salt '*' protocol.get_protocolhttpband

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/protocolhttpband'), 'protocolhttpband')

    return response


def unset_protocolhttpband(reqbandsize=None, respbandsize=None, ns_type=None, nodeid=None, save=False):
    '''
    Unsets values from the protocolhttpband configuration key.

    reqbandsize(bool): Unsets the reqbandsize value.

    respbandsize(bool): Unsets the respbandsize value.

    ns_type(bool): Unsets the ns_type value.

    nodeid(bool): Unsets the nodeid value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' protocol.unset_protocolhttpband <args>

    '''

    result = {}

    payload = {'protocolhttpband': {}}

    if reqbandsize:
        payload['protocolhttpband']['reqbandsize'] = True

    if respbandsize:
        payload['protocolhttpband']['respbandsize'] = True

    if ns_type:
        payload['protocolhttpband']['type'] = True

    if nodeid:
        payload['protocolhttpband']['nodeid'] = True

    execution = __proxy__['citrixns.post']('config/protocolhttpband?action=unset', payload)

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


def update_protocolhttpband(reqbandsize=None, respbandsize=None, ns_type=None, nodeid=None, save=False):
    '''
    Update the running configuration for the protocolhttpband config key.

    reqbandsize(int): Band size, in bytes, for HTTP request band statistics. For example, if you specify a band size of 100
        bytes, statistics will be maintained and displayed for the following size ranges: 0 - 99 bytes 100 - 199 bytes
        200 - 299 bytes and so on. Default value: 100 Minimum value = 50

    respbandsize(int): Band size, in bytes, for HTTP response band statistics. For example, if you specify a band size of 100
        bytes, statistics will be maintained and displayed for the following size ranges: 0 - 99 bytes 100 - 199 bytes
        200 - 299 bytes and so on. Default value: 1024 Minimum value = 50

    ns_type(str): Type of statistics to display. Possible values = REQUEST, RESPONSE

    nodeid(int): Unique number that identifies the cluster node. Minimum value = 0 Maximum value = 31

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' protocol.update_protocolhttpband <args>

    '''

    result = {}

    payload = {'protocolhttpband': {}}

    if reqbandsize:
        payload['protocolhttpband']['reqbandsize'] = reqbandsize

    if respbandsize:
        payload['protocolhttpband']['respbandsize'] = respbandsize

    if ns_type:
        payload['protocolhttpband']['type'] = ns_type

    if nodeid:
        payload['protocolhttpband']['nodeid'] = nodeid

    execution = __proxy__['citrixns.put']('config/protocolhttpband', payload)

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
