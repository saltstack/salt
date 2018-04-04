# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the wf key.

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

__virtualname__ = 'wf'


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

    return False, 'The wf execution module can only be loaded for citrixns proxy minions.'


def add_wfsite(sitename=None, storefronturl=None, storename=None, html5receiver=None, workspacecontrol=None,
               displayroamingaccounts=None, xframeoptions=None, save=False):
    '''
    Add a new wfsite to the running configuration.

    sitename(str): Name of the WebFront site being created on the NetScaler appliance. Minimum length = 1 Maximum length =
        255

    storefronturl(str): FQDN or IP of Windows StoreFront server where the store is configured. Minimum length = 1 Maximum
        length = 255

    storename(str): Name of the store present in StoreFront. Minimum length = 1 Maximum length = 255

    html5receiver(str): Specifies whether or not to use HTML5 receiver for launching apps for the WF site. Default value:
        FALLBACK Possible values = ALWAYS, FALLBACK, OFF

    workspacecontrol(str): Specifies whether of not to use workspace control for the WF site. Default value: ON Possible
        values = ON, OFF

    displayroamingaccounts(str): Specifies whether or not to display the accounts selection screen during First Time Use of
        Receiver . Default value: ON Possible values = ON, OFF

    xframeoptions(str): The value to be sent in the X-Frame-Options header. WARNING: Setting this option to ALLOW could leave
        the end user vulnerable to Click Jacking attacks. Default value: DENY Possible values = ALLOW, DENY

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' wf.add_wfsite <args>

    '''

    result = {}

    payload = {'wfsite': {}}

    if sitename:
        payload['wfsite']['sitename'] = sitename

    if storefronturl:
        payload['wfsite']['storefronturl'] = storefronturl

    if storename:
        payload['wfsite']['storename'] = storename

    if html5receiver:
        payload['wfsite']['html5receiver'] = html5receiver

    if workspacecontrol:
        payload['wfsite']['workspacecontrol'] = workspacecontrol

    if displayroamingaccounts:
        payload['wfsite']['displayroamingaccounts'] = displayroamingaccounts

    if xframeoptions:
        payload['wfsite']['xframeoptions'] = xframeoptions

    execution = __proxy__['citrixns.post']('config/wfsite', payload)

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


def get_wfpackage():
    '''
    Show the running configuration for the wfpackage config key.

    CLI Example:

    .. code-block:: bash

    salt '*' wf.get_wfpackage

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/wfpackage'), 'wfpackage')

    return response


def get_wfsite(sitename=None, storefronturl=None, storename=None, html5receiver=None, workspacecontrol=None,
               displayroamingaccounts=None, xframeoptions=None):
    '''
    Show the running configuration for the wfsite config key.

    sitename(str): Filters results that only match the sitename field.

    storefronturl(str): Filters results that only match the storefronturl field.

    storename(str): Filters results that only match the storename field.

    html5receiver(str): Filters results that only match the html5receiver field.

    workspacecontrol(str): Filters results that only match the workspacecontrol field.

    displayroamingaccounts(str): Filters results that only match the displayroamingaccounts field.

    xframeoptions(str): Filters results that only match the xframeoptions field.

    CLI Example:

    .. code-block:: bash

    salt '*' wf.get_wfsite

    '''

    search_filter = []

    if sitename:
        search_filter.append(['sitename', sitename])

    if storefronturl:
        search_filter.append(['storefronturl', storefronturl])

    if storename:
        search_filter.append(['storename', storename])

    if html5receiver:
        search_filter.append(['html5receiver', html5receiver])

    if workspacecontrol:
        search_filter.append(['workspacecontrol', workspacecontrol])

    if displayroamingaccounts:
        search_filter.append(['displayroamingaccounts', displayroamingaccounts])

    if xframeoptions:
        search_filter.append(['xframeoptions', xframeoptions])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/wfsite{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'wfsite')

    return response


def update_wfsite(sitename=None, storefronturl=None, storename=None, html5receiver=None, workspacecontrol=None,
                  displayroamingaccounts=None, xframeoptions=None, save=False):
    '''
    Update the running configuration for the wfsite config key.

    sitename(str): Name of the WebFront site being created on the NetScaler appliance. Minimum length = 1 Maximum length =
        255

    storefronturl(str): FQDN or IP of Windows StoreFront server where the store is configured. Minimum length = 1 Maximum
        length = 255

    storename(str): Name of the store present in StoreFront. Minimum length = 1 Maximum length = 255

    html5receiver(str): Specifies whether or not to use HTML5 receiver for launching apps for the WF site. Default value:
        FALLBACK Possible values = ALWAYS, FALLBACK, OFF

    workspacecontrol(str): Specifies whether of not to use workspace control for the WF site. Default value: ON Possible
        values = ON, OFF

    displayroamingaccounts(str): Specifies whether or not to display the accounts selection screen during First Time Use of
        Receiver . Default value: ON Possible values = ON, OFF

    xframeoptions(str): The value to be sent in the X-Frame-Options header. WARNING: Setting this option to ALLOW could leave
        the end user vulnerable to Click Jacking attacks. Default value: DENY Possible values = ALLOW, DENY

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' wf.update_wfsite <args>

    '''

    result = {}

    payload = {'wfsite': {}}

    if sitename:
        payload['wfsite']['sitename'] = sitename

    if storefronturl:
        payload['wfsite']['storefronturl'] = storefronturl

    if storename:
        payload['wfsite']['storename'] = storename

    if html5receiver:
        payload['wfsite']['html5receiver'] = html5receiver

    if workspacecontrol:
        payload['wfsite']['workspacecontrol'] = workspacecontrol

    if displayroamingaccounts:
        payload['wfsite']['displayroamingaccounts'] = displayroamingaccounts

    if xframeoptions:
        payload['wfsite']['xframeoptions'] = xframeoptions

    execution = __proxy__['citrixns.put']('config/wfsite', payload)

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
