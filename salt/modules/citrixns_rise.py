# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the rise key.

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

__virtualname__ = 'rise'


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

    return False, 'The rise execution module can only be loaded for citrixns proxy minions.'


def get_riseapbrsvc():
    '''
    Show the running configuration for the riseapbrsvc config key.

    CLI Example:

    .. code-block:: bash

    salt '*' rise.get_riseapbrsvc

    '''

    search_filter = []

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/riseapbrsvc{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'riseapbrsvc')

    return response


def get_riseparam():
    '''
    Show the running configuration for the riseparam config key.

    CLI Example:

    .. code-block:: bash

    salt '*' rise.get_riseparam

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/riseparam'), 'riseparam')

    return response


def get_riseprofile(profilename=None):
    '''
    Show the running configuration for the riseprofile config key.

    profilename(str): Filters results that only match the profilename field.

    CLI Example:

    .. code-block:: bash

    salt '*' rise.get_riseprofile

    '''

    search_filter = []

    if profilename:
        search_filter.append(['profilename', profilename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/riseprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'riseprofile')

    return response


def get_riseprofile_binding():
    '''
    Show the running configuration for the riseprofile_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' rise.get_riseprofile_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/riseprofile_binding'), 'riseprofile_binding')

    return response


def get_riseprofile_interface_binding(memberinterface=None, profilename=None):
    '''
    Show the running configuration for the riseprofile_interface_binding config key.

    memberinterface(str): Filters results that only match the memberinterface field.

    profilename(str): Filters results that only match the profilename field.

    CLI Example:

    .. code-block:: bash

    salt '*' rise.get_riseprofile_interface_binding

    '''

    search_filter = []

    if memberinterface:
        search_filter.append(['memberinterface', memberinterface])

    if profilename:
        search_filter.append(['profilename', profilename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/riseprofile_interface_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'riseprofile_interface_binding')

    return response


def get_riserhi():
    '''
    Show the running configuration for the riserhi config key.

    CLI Example:

    .. code-block:: bash

    salt '*' rise.get_riserhi

    '''

    search_filter = []

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/riserhi{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'riserhi')

    return response


def unset_riseparam(directmode=None, indirectmode=None, save=False):
    '''
    Unsets values from the riseparam configuration key.

    directmode(bool): Unsets the directmode value.

    indirectmode(bool): Unsets the indirectmode value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rise.unset_riseparam <args>

    '''

    result = {}

    payload = {'riseparam': {}}

    if directmode:
        payload['riseparam']['directmode'] = True

    if indirectmode:
        payload['riseparam']['indirectmode'] = True

    execution = __proxy__['citrixns.post']('config/riseparam?action=unset', payload)

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


def update_riseparam(directmode=None, indirectmode=None, save=False):
    '''
    Update the running configuration for the riseparam config key.

    directmode(str): RISE Direct attach mode. Default value: ENABLED Possible values = ENABLED, DISABLED

    indirectmode(str): RISE Indirect attach mode. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rise.update_riseparam <args>

    '''

    result = {}

    payload = {'riseparam': {}}

    if directmode:
        payload['riseparam']['directmode'] = directmode

    if indirectmode:
        payload['riseparam']['indirectmode'] = indirectmode

    execution = __proxy__['citrixns.put']('config/riseparam', payload)

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
