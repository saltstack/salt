# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the smpp key.

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

__virtualname__ = 'smpp'


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

    return False, 'The smpp execution module can only be loaded for citrixns proxy minions.'


def add_smppuser(username=None, password=None, save=False):
    '''
    Add a new smppuser to the running configuration.

    username(str): Name of the SMPP user. Must be the same as the user name specified in the SMPP server. Minimum length = 1

    password(str): Password for binding to the SMPP server. Must be the same as the password specified in the SMPP server.
        Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' smpp.add_smppuser <args>

    '''

    result = {}

    payload = {'smppuser': {}}

    if username:
        payload['smppuser']['username'] = username

    if password:
        payload['smppuser']['password'] = password

    execution = __proxy__['citrixns.post']('config/smppuser', payload)

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


def get_smppparam():
    '''
    Show the running configuration for the smppparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' smpp.get_smppparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/smppparam'), 'smppparam')

    return response


def get_smppuser(username=None, password=None):
    '''
    Show the running configuration for the smppuser config key.

    username(str): Filters results that only match the username field.

    password(str): Filters results that only match the password field.

    CLI Example:

    .. code-block:: bash

    salt '*' smpp.get_smppuser

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if password:
        search_filter.append(['password', password])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/smppuser{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'smppuser')

    return response


def unset_smppparam(clientmode=None, msgqueue=None, msgqueuesize=None, addrton=None, addrnpi=None, addrrange=None,
                    save=False):
    '''
    Unsets values from the smppparam configuration key.

    clientmode(bool): Unsets the clientmode value.

    msgqueue(bool): Unsets the msgqueue value.

    msgqueuesize(bool): Unsets the msgqueuesize value.

    addrton(bool): Unsets the addrton value.

    addrnpi(bool): Unsets the addrnpi value.

    addrrange(bool): Unsets the addrrange value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' smpp.unset_smppparam <args>

    '''

    result = {}

    payload = {'smppparam': {}}

    if clientmode:
        payload['smppparam']['clientmode'] = True

    if msgqueue:
        payload['smppparam']['msgqueue'] = True

    if msgqueuesize:
        payload['smppparam']['msgqueuesize'] = True

    if addrton:
        payload['smppparam']['addrton'] = True

    if addrnpi:
        payload['smppparam']['addrnpi'] = True

    if addrrange:
        payload['smppparam']['addrrange'] = True

    execution = __proxy__['citrixns.post']('config/smppparam?action=unset', payload)

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


def update_smppparam(clientmode=None, msgqueue=None, msgqueuesize=None, addrton=None, addrnpi=None, addrrange=None,
                     save=False):
    '''
    Update the running configuration for the smppparam config key.

    clientmode(str): Mode in which the client binds to the ADC. Applicable settings function as follows: * TRANSCEIVER -
        Client can send and receive messages to and from the message center. * TRANSMITTERONLY - Client can only send
        messages. * RECEIVERONLY - Client can only receive messages. Default value: TRANSCEIVER Possible values =
        TRANSCEIVER, TRANSMITTERONLY, RECEIVERONLY

    msgqueue(str): Queue SMPP messages if a client that is capable of receiving the destination address messages is not
        available. Default value: OFF Possible values = ON, OFF

    msgqueuesize(int): Maximum number of SMPP messages that can be queued. After the limit is reached, the NetScaler ADC
        sends a deliver_sm_resp PDU, with an appropriate error message, to the message center. Default value: 10000

    addrton(int): Type of Number, such as an international number or a national number, used in the ESME address sent in the
        bind request. Default value: 0 Minimum value = 0 Maximum value = 256

    addrnpi(int): Numbering Plan Indicator, such as landline, data, or WAP client, used in the ESME address sent in the bind
        request. Default value: 0 Minimum value = 0 Maximum value = 256

    addrrange(str): Set of SME addresses, sent in the bind request, serviced by the ESME. Default value: "\\\\d*"

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' smpp.update_smppparam <args>

    '''

    result = {}

    payload = {'smppparam': {}}

    if clientmode:
        payload['smppparam']['clientmode'] = clientmode

    if msgqueue:
        payload['smppparam']['msgqueue'] = msgqueue

    if msgqueuesize:
        payload['smppparam']['msgqueuesize'] = msgqueuesize

    if addrton:
        payload['smppparam']['addrton'] = addrton

    if addrnpi:
        payload['smppparam']['addrnpi'] = addrnpi

    if addrrange:
        payload['smppparam']['addrrange'] = addrrange

    execution = __proxy__['citrixns.put']('config/smppparam', payload)

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


def update_smppuser(username=None, password=None, save=False):
    '''
    Update the running configuration for the smppuser config key.

    username(str): Name of the SMPP user. Must be the same as the user name specified in the SMPP server. Minimum length = 1

    password(str): Password for binding to the SMPP server. Must be the same as the password specified in the SMPP server.
        Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' smpp.update_smppuser <args>

    '''

    result = {}

    payload = {'smppuser': {}}

    if username:
        payload['smppuser']['username'] = username

    if password:
        payload['smppuser']['password'] = password

    execution = __proxy__['citrixns.put']('config/smppuser', payload)

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
