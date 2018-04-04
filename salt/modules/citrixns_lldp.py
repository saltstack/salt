# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the lldp key.

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

__virtualname__ = 'lldp'


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

    return False, 'The lldp execution module can only be loaded for citrixns proxy minions.'


def get_lldpneighbors(ifnum=None, nodeid=None):
    '''
    Show the running configuration for the lldpneighbors config key.

    ifnum(str): Filters results that only match the ifnum field.

    nodeid(int): Filters results that only match the nodeid field.

    CLI Example:

    .. code-block:: bash

    salt '*' lldp.get_lldpneighbors

    '''

    search_filter = []

    if ifnum:
        search_filter.append(['ifnum', ifnum])

    if nodeid:
        search_filter.append(['nodeid', nodeid])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lldpneighbors{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'lldpneighbors')

    return response


def get_lldpparam():
    '''
    Show the running configuration for the lldpparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' lldp.get_lldpparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/lldpparam'), 'lldpparam')

    return response


def unset_lldpparam(holdtimetxmult=None, timer=None, mode=None, save=False):
    '''
    Unsets values from the lldpparam configuration key.

    holdtimetxmult(bool): Unsets the holdtimetxmult value.

    timer(bool): Unsets the timer value.

    mode(bool): Unsets the mode value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lldp.unset_lldpparam <args>

    '''

    result = {}

    payload = {'lldpparam': {}}

    if holdtimetxmult:
        payload['lldpparam']['holdtimetxmult'] = True

    if timer:
        payload['lldpparam']['timer'] = True

    if mode:
        payload['lldpparam']['mode'] = True

    execution = __proxy__['citrixns.post']('config/lldpparam?action=unset', payload)

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


def update_lldpparam(holdtimetxmult=None, timer=None, mode=None, save=False):
    '''
    Update the running configuration for the lldpparam config key.

    holdtimetxmult(int): A multiplier for calculating the duration for which the receiving device stores the LLDP information
        in its database before discarding or removing it. The duration is calculated as the holdtimeTxMult (Holdtime
        Multiplier) parameter value multiplied by the timer (Timer) parameter value. Default value: 4 Minimum value = 1
        Maximum value = 20

    timer(int): Interval, in seconds, between LLDP packet data units (LLDPDUs). that the NetScaler ADC sends to a directly
        connected device. Default value: 30 Minimum value = 1 Maximum value = 3000

    mode(str): Global mode of Link Layer Discovery Protocol (LLDP) on the NetScaler ADC. The resultant LLDP mode of an
        interface depends on the LLDP mode configured at the global and the interface levels. Possible values = NONE,
        TRANSMITTER, RECEIVER, TRANSCEIVER

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' lldp.update_lldpparam <args>

    '''

    result = {}

    payload = {'lldpparam': {}}

    if holdtimetxmult:
        payload['lldpparam']['holdtimetxmult'] = holdtimetxmult

    if timer:
        payload['lldpparam']['timer'] = timer

    if mode:
        payload['lldpparam']['mode'] = mode

    execution = __proxy__['citrixns.put']('config/lldpparam', payload)

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
