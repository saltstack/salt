# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the ulfd key.

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

__virtualname__ = 'ulfd'


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

    return False, 'The ulfd execution module can only be loaded for citrixns proxy minions.'


def add_ulfdserver(loggerip=None, save=False):
    '''
    Add a new ulfdserver to the running configuration.

    loggerip(str): IP address of the server where ulfd service is running. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ulfd.add_ulfdserver <args>

    '''

    result = {}

    payload = {'ulfdserver': {}}

    if loggerip:
        payload['ulfdserver']['loggerip'] = loggerip

    execution = __proxy__['citrixns.post']('config/ulfdserver', payload)

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


def get_ulfdserver(loggerip=None):
    '''
    Show the running configuration for the ulfdserver config key.

    loggerip(str): Filters results that only match the loggerip field.

    CLI Example:

    .. code-block:: bash

    salt '*' ulfd.get_ulfdserver

    '''

    search_filter = []

    if loggerip:
        search_filter.append(['loggerip', loggerip])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ulfdserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ulfdserver')

    return response
