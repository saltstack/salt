# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the ipsecalg key.

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

__virtualname__ = 'ipsecalg'


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

    return False, 'The ipsecalg execution module can only be loaded for citrixns proxy minions.'


def add_ipsecalgprofile(name=None, ikesessiontimeout=None, espsessiontimeout=None, espgatetimeout=None,
                        connfailover=None, save=False):
    '''
    Add a new ipsecalgprofile to the running configuration.

    name(str): The name of the ipsec alg profile. Minimum length = 1 Maximum length = 32

    ikesessiontimeout(int): IKE session timeout in minutes. Default value: 60 Minimum value = 1 Maximum value = 1440

    espsessiontimeout(int): ESP session timeout in minutes. Default value: 60 Minimum value = 1 Maximum value = 1440

    espgatetimeout(int): Timeout ESP in seconds as no ESP packets are seen after IKE negotiation. Default value: 60 Minimum
        value = 30 Maximum value = 1200

    connfailover(str): Mode in which the connection failover feature must operate for the IPSec Alg. After a failover,
        established UDP connections and ESP packet flows are kept active and resumed on the secondary appliance.
        Recomended setting is ENABLED. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ipsecalg.add_ipsecalgprofile <args>

    '''

    result = {}

    payload = {'ipsecalgprofile': {}}

    if name:
        payload['ipsecalgprofile']['name'] = name

    if ikesessiontimeout:
        payload['ipsecalgprofile']['ikesessiontimeout'] = ikesessiontimeout

    if espsessiontimeout:
        payload['ipsecalgprofile']['espsessiontimeout'] = espsessiontimeout

    if espgatetimeout:
        payload['ipsecalgprofile']['espgatetimeout'] = espgatetimeout

    if connfailover:
        payload['ipsecalgprofile']['connfailover'] = connfailover

    execution = __proxy__['citrixns.post']('config/ipsecalgprofile', payload)

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


def get_ipsecalgprofile(name=None, ikesessiontimeout=None, espsessiontimeout=None, espgatetimeout=None,
                        connfailover=None):
    '''
    Show the running configuration for the ipsecalgprofile config key.

    name(str): Filters results that only match the name field.

    ikesessiontimeout(int): Filters results that only match the ikesessiontimeout field.

    espsessiontimeout(int): Filters results that only match the espsessiontimeout field.

    espgatetimeout(int): Filters results that only match the espgatetimeout field.

    connfailover(str): Filters results that only match the connfailover field.

    CLI Example:

    .. code-block:: bash

    salt '*' ipsecalg.get_ipsecalgprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ikesessiontimeout:
        search_filter.append(['ikesessiontimeout', ikesessiontimeout])

    if espsessiontimeout:
        search_filter.append(['espsessiontimeout', espsessiontimeout])

    if espgatetimeout:
        search_filter.append(['espgatetimeout', espgatetimeout])

    if connfailover:
        search_filter.append(['connfailover', connfailover])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ipsecalgprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ipsecalgprofile')

    return response


def get_ipsecalgsession(sourceip_alg=None, natip_alg=None, destip_alg=None, sourceip=None, natip=None, destip=None):
    '''
    Show the running configuration for the ipsecalgsession config key.

    sourceip_alg(str): Filters results that only match the sourceip_alg field.

    natip_alg(str): Filters results that only match the natip_alg field.

    destip_alg(str): Filters results that only match the destip_alg field.

    sourceip(str): Filters results that only match the sourceip field.

    natip(str): Filters results that only match the natip field.

    destip(str): Filters results that only match the destip field.

    CLI Example:

    .. code-block:: bash

    salt '*' ipsecalg.get_ipsecalgsession

    '''

    search_filter = []

    if sourceip_alg:
        search_filter.append(['sourceip_alg', sourceip_alg])

    if natip_alg:
        search_filter.append(['natip_alg', natip_alg])

    if destip_alg:
        search_filter.append(['destip_alg', destip_alg])

    if sourceip:
        search_filter.append(['sourceip', sourceip])

    if natip:
        search_filter.append(['natip', natip])

    if destip:
        search_filter.append(['destip', destip])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ipsecalgsession{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ipsecalgsession')

    return response


def unset_ipsecalgprofile(name=None, ikesessiontimeout=None, espsessiontimeout=None, espgatetimeout=None,
                          connfailover=None, save=False):
    '''
    Unsets values from the ipsecalgprofile configuration key.

    name(bool): Unsets the name value.

    ikesessiontimeout(bool): Unsets the ikesessiontimeout value.

    espsessiontimeout(bool): Unsets the espsessiontimeout value.

    espgatetimeout(bool): Unsets the espgatetimeout value.

    connfailover(bool): Unsets the connfailover value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ipsecalg.unset_ipsecalgprofile <args>

    '''

    result = {}

    payload = {'ipsecalgprofile': {}}

    if name:
        payload['ipsecalgprofile']['name'] = True

    if ikesessiontimeout:
        payload['ipsecalgprofile']['ikesessiontimeout'] = True

    if espsessiontimeout:
        payload['ipsecalgprofile']['espsessiontimeout'] = True

    if espgatetimeout:
        payload['ipsecalgprofile']['espgatetimeout'] = True

    if connfailover:
        payload['ipsecalgprofile']['connfailover'] = True

    execution = __proxy__['citrixns.post']('config/ipsecalgprofile?action=unset', payload)

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


def update_ipsecalgprofile(name=None, ikesessiontimeout=None, espsessiontimeout=None, espgatetimeout=None,
                           connfailover=None, save=False):
    '''
    Update the running configuration for the ipsecalgprofile config key.

    name(str): The name of the ipsec alg profile. Minimum length = 1 Maximum length = 32

    ikesessiontimeout(int): IKE session timeout in minutes. Default value: 60 Minimum value = 1 Maximum value = 1440

    espsessiontimeout(int): ESP session timeout in minutes. Default value: 60 Minimum value = 1 Maximum value = 1440

    espgatetimeout(int): Timeout ESP in seconds as no ESP packets are seen after IKE negotiation. Default value: 60 Minimum
        value = 30 Maximum value = 1200

    connfailover(str): Mode in which the connection failover feature must operate for the IPSec Alg. After a failover,
        established UDP connections and ESP packet flows are kept active and resumed on the secondary appliance.
        Recomended setting is ENABLED. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ipsecalg.update_ipsecalgprofile <args>

    '''

    result = {}

    payload = {'ipsecalgprofile': {}}

    if name:
        payload['ipsecalgprofile']['name'] = name

    if ikesessiontimeout:
        payload['ipsecalgprofile']['ikesessiontimeout'] = ikesessiontimeout

    if espsessiontimeout:
        payload['ipsecalgprofile']['espsessiontimeout'] = espsessiontimeout

    if espgatetimeout:
        payload['ipsecalgprofile']['espgatetimeout'] = espgatetimeout

    if connfailover:
        payload['ipsecalgprofile']['connfailover'] = connfailover

    execution = __proxy__['citrixns.put']('config/ipsecalgprofile', payload)

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
