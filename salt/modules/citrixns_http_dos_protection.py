# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the http-dos-protection key.

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

__virtualname__ = 'http_dos_protection'


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

    return False, 'The http_dos_protection execution module can only be loaded for citrixns proxy minions.'


def add_dospolicy(name=None, qdepth=None, cltdetectrate=None, save=False):
    '''
    Add a new dospolicy to the running configuration.

    name(str): Name for the HTTP DoS protection policy. Must begin with a letter, number, or the underscore character (_).
        Other characters allowed, after the first character, are the hyphen (-), period (.) hash (#), space ( ), at (@),
        equals (=), and colon (:) characters. Minimum length = 1

    qdepth(int): Queue depth. The queue size (the number of outstanding service requests on the system) before DoS protection
        is activated on the service to which the DoS protection policy is bound. Minimum value = 21

    cltdetectrate(int): Client detect rate. Integer representing the percentage of traffic to which the HTTP DoS policy is to
        be applied after the queue depth condition is satisfied. Minimum value = 0 Maximum value = 100

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' http_dos_protection.add_dospolicy <args>

    '''

    result = {}

    payload = {'dospolicy': {}}

    if name:
        payload['dospolicy']['name'] = name

    if qdepth:
        payload['dospolicy']['qdepth'] = qdepth

    if cltdetectrate:
        payload['dospolicy']['cltdetectrate'] = cltdetectrate

    execution = __proxy__['citrixns.post']('config/dospolicy', payload)

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


def get_dospolicy(name=None, qdepth=None, cltdetectrate=None):
    '''
    Show the running configuration for the dospolicy config key.

    name(str): Filters results that only match the name field.

    qdepth(int): Filters results that only match the qdepth field.

    cltdetectrate(int): Filters results that only match the cltdetectrate field.

    CLI Example:

    .. code-block:: bash

    salt '*' http_dos_protection.get_dospolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if qdepth:
        search_filter.append(['qdepth', qdepth])

    if cltdetectrate:
        search_filter.append(['cltdetectrate', cltdetectrate])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dospolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dospolicy')

    return response


def unset_dospolicy(name=None, qdepth=None, cltdetectrate=None, save=False):
    '''
    Unsets values from the dospolicy configuration key.

    name(bool): Unsets the name value.

    qdepth(bool): Unsets the qdepth value.

    cltdetectrate(bool): Unsets the cltdetectrate value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' http_dos_protection.unset_dospolicy <args>

    '''

    result = {}

    payload = {'dospolicy': {}}

    if name:
        payload['dospolicy']['name'] = True

    if qdepth:
        payload['dospolicy']['qdepth'] = True

    if cltdetectrate:
        payload['dospolicy']['cltdetectrate'] = True

    execution = __proxy__['citrixns.post']('config/dospolicy?action=unset', payload)

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


def update_dospolicy(name=None, qdepth=None, cltdetectrate=None, save=False):
    '''
    Update the running configuration for the dospolicy config key.

    name(str): Name for the HTTP DoS protection policy. Must begin with a letter, number, or the underscore character (_).
        Other characters allowed, after the first character, are the hyphen (-), period (.) hash (#), space ( ), at (@),
        equals (=), and colon (:) characters. Minimum length = 1

    qdepth(int): Queue depth. The queue size (the number of outstanding service requests on the system) before DoS protection
        is activated on the service to which the DoS protection policy is bound. Minimum value = 21

    cltdetectrate(int): Client detect rate. Integer representing the percentage of traffic to which the HTTP DoS policy is to
        be applied after the queue depth condition is satisfied. Minimum value = 0 Maximum value = 100

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' http_dos_protection.update_dospolicy <args>

    '''

    result = {}

    payload = {'dospolicy': {}}

    if name:
        payload['dospolicy']['name'] = name

    if qdepth:
        payload['dospolicy']['qdepth'] = qdepth

    if cltdetectrate:
        payload['dospolicy']['cltdetectrate'] = cltdetectrate

    execution = __proxy__['citrixns.put']('config/dospolicy', payload)

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
