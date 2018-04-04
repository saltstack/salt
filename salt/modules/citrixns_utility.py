# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the utility key.

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

__virtualname__ = 'utility'


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

    return False, 'The utility execution module can only be loaded for citrixns proxy minions.'


def get_callhome():
    '''
    Show the running configuration for the callhome config key.

    CLI Example:

    .. code-block:: bash

    salt '*' utility.get_callhome

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/callhome'), 'callhome')

    return response


def get_raid():
    '''
    Show the running configuration for the raid config key.

    CLI Example:

    .. code-block:: bash

    salt '*' utility.get_raid

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/raid'), 'raid')

    return response


def get_techsupport():
    '''
    Show the running configuration for the techsupport config key.

    CLI Example:

    .. code-block:: bash

    salt '*' utility.get_techsupport

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/techsupport'), 'techsupport')

    return response


def unset_callhome(emailaddress=None, hbcustominterval=None, proxymode=None, ipaddress=None, proxyauthservice=None,
                   port=None, save=False):
    '''
    Unsets values from the callhome configuration key.

    emailaddress(bool): Unsets the emailaddress value.

    hbcustominterval(bool): Unsets the hbcustominterval value.

    proxymode(bool): Unsets the proxymode value.

    ipaddress(bool): Unsets the ipaddress value.

    proxyauthservice(bool): Unsets the proxyauthservice value.

    port(bool): Unsets the port value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' utility.unset_callhome <args>

    '''

    result = {}

    payload = {'callhome': {}}

    if emailaddress:
        payload['callhome']['emailaddress'] = True

    if hbcustominterval:
        payload['callhome']['hbcustominterval'] = True

    if proxymode:
        payload['callhome']['proxymode'] = True

    if ipaddress:
        payload['callhome']['ipaddress'] = True

    if proxyauthservice:
        payload['callhome']['proxyauthservice'] = True

    if port:
        payload['callhome']['port'] = True

    execution = __proxy__['citrixns.post']('config/callhome?action=unset', payload)

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


def update_callhome(emailaddress=None, hbcustominterval=None, proxymode=None, ipaddress=None, proxyauthservice=None,
                    port=None, save=False):
    '''
    Update the running configuration for the callhome config key.

    emailaddress(str): Email address of the contact administrator. Maximum length = 78

    hbcustominterval(int): Interval (in days) between CallHome heartbeats. Minimum value = 1 Maximum value = 30

    proxymode(str): Enables or disables the proxy mode. The proxy server can be set by either specifying the IP address of
        the server or the name of the service representing the proxy server. Default value: NO Possible values = YES, NO

    ipaddress(str): IP address of the proxy server. Minimum length = 1

    proxyauthservice(str): Name of the service that represents the proxy server. Maximum length = 128

    port(int): HTTP port on the Proxy server. This is a mandatory parameter for both IP address and service name based
        configuration. Minimum value = 1 Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' utility.update_callhome <args>

    '''

    result = {}

    payload = {'callhome': {}}

    if emailaddress:
        payload['callhome']['emailaddress'] = emailaddress

    if hbcustominterval:
        payload['callhome']['hbcustominterval'] = hbcustominterval

    if proxymode:
        payload['callhome']['proxymode'] = proxymode

    if ipaddress:
        payload['callhome']['ipaddress'] = ipaddress

    if proxyauthservice:
        payload['callhome']['proxyauthservice'] = proxyauthservice

    if port:
        payload['callhome']['port'] = port

    execution = __proxy__['citrixns.put']('config/callhome', payload)

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
