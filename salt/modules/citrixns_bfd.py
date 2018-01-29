# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the bfd key.

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

__virtualname__ = 'bfd'


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

    return False, 'The bfd execution module can only be loaded for citrixns proxy minions.'


def get_bfdsession(localip=None, remoteip=None):
    '''
    Show the running configuration for the bfdsession config key.

    localip(str): Filters results that only match the localip field.

    remoteip(str): Filters results that only match the remoteip field.

    CLI Example:

    .. code-block:: bash

    salt '*' bfd.get_bfdsession

    '''

    search_filter = []

    if localip:
        search_filter.append(['localip', localip])

    if remoteip:
        search_filter.append(['remoteip', remoteip])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/bfdsession{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'bfdsession')

    return response
