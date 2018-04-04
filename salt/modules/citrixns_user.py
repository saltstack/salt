# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the user key.

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

__virtualname__ = 'user'


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

    return False, 'The user execution module can only be loaded for citrixns proxy minions.'


def add_userprotocol(name=None, transport=None, extension=None, comment=None, save=False):
    '''
    Add a new userprotocol to the running configuration.

    name(str): Unique name for the user protocol. Not case sensitive. Must begin with an ASCII letter or underscore (_)
        character, and must consist only of ASCII alphanumeric or underscore characters. Minimum length = 1

    transport(str): Transport layers protocol. Possible values = TCP, SSL

    extension(str): Name of the extension to add parsing and runtime handling of the protocol packets.

    comment(str): Any comments associated with the protocol.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' user.add_userprotocol <args>

    '''

    result = {}

    payload = {'userprotocol': {}}

    if name:
        payload['userprotocol']['name'] = name

    if transport:
        payload['userprotocol']['transport'] = transport

    if extension:
        payload['userprotocol']['extension'] = extension

    if comment:
        payload['userprotocol']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/userprotocol', payload)

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


def add_uservserver(name=None, userprotocol=None, ipaddress=None, port=None, defaultlb=None, params=None, comment=None,
                    save=False):
    '''
    Add a new uservserver to the running configuration.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign (=),
        and hyphen (-) characters.  CLI Users: If the name includes one or more spaces, enclose the name in double or
        single quotation marks (for example, "my vserver" or my vserver). . Minimum length = 1

    userprotocol(str): User protocol uesd by the service.

    ipaddress(str): IPv4 or IPv6 address to assign to the virtual server.

    port(int): Port number for the virtual server. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    defaultlb(str): Name of the default Load Balancing virtual server used for load balancing of services. The protocol type
        of default Load Balancing virtual server should be a user type.

    params(str): Any comments associated with the protocol.

    comment(str): Any comments that you might want to associate with the virtual server.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' user.add_uservserver <args>

    '''

    result = {}

    payload = {'uservserver': {}}

    if name:
        payload['uservserver']['name'] = name

    if userprotocol:
        payload['uservserver']['userprotocol'] = userprotocol

    if ipaddress:
        payload['uservserver']['ipaddress'] = ipaddress

    if port:
        payload['uservserver']['port'] = port

    if defaultlb:
        payload['uservserver']['defaultlb'] = defaultlb

    if params:
        payload['uservserver']['Params'] = params

    if comment:
        payload['uservserver']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/uservserver', payload)

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


def get_userprotocol(name=None, transport=None, extension=None, comment=None):
    '''
    Show the running configuration for the userprotocol config key.

    name(str): Filters results that only match the name field.

    transport(str): Filters results that only match the transport field.

    extension(str): Filters results that only match the extension field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' user.get_userprotocol

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if transport:
        search_filter.append(['transport', transport])

    if extension:
        search_filter.append(['extension', extension])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/userprotocol{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'userprotocol')

    return response


def get_uservserver(name=None, userprotocol=None, ipaddress=None, port=None, defaultlb=None, params=None, comment=None):
    '''
    Show the running configuration for the uservserver config key.

    name(str): Filters results that only match the name field.

    userprotocol(str): Filters results that only match the userprotocol field.

    ipaddress(str): Filters results that only match the ipaddress field.

    port(int): Filters results that only match the port field.

    defaultlb(str): Filters results that only match the defaultlb field.

    params(str): Filters results that only match the Params field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' user.get_uservserver

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if userprotocol:
        search_filter.append(['userprotocol', userprotocol])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if port:
        search_filter.append(['port', port])

    if defaultlb:
        search_filter.append(['defaultlb', defaultlb])

    if params:
        search_filter.append(['Params', params])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/uservserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'uservserver')

    return response


def unset_userprotocol(name=None, transport=None, extension=None, comment=None, save=False):
    '''
    Unsets values from the userprotocol configuration key.

    name(bool): Unsets the name value.

    transport(bool): Unsets the transport value.

    extension(bool): Unsets the extension value.

    comment(bool): Unsets the comment value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' user.unset_userprotocol <args>

    '''

    result = {}

    payload = {'userprotocol': {}}

    if name:
        payload['userprotocol']['name'] = True

    if transport:
        payload['userprotocol']['transport'] = True

    if extension:
        payload['userprotocol']['extension'] = True

    if comment:
        payload['userprotocol']['comment'] = True

    execution = __proxy__['citrixns.post']('config/userprotocol?action=unset', payload)

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


def unset_uservserver(name=None, userprotocol=None, ipaddress=None, port=None, defaultlb=None, params=None, comment=None,
                      save=False):
    '''
    Unsets values from the uservserver configuration key.

    name(bool): Unsets the name value.

    userprotocol(bool): Unsets the userprotocol value.

    ipaddress(bool): Unsets the ipaddress value.

    port(bool): Unsets the port value.

    defaultlb(bool): Unsets the defaultlb value.

    params(bool): Unsets the params value.

    comment(bool): Unsets the comment value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' user.unset_uservserver <args>

    '''

    result = {}

    payload = {'uservserver': {}}

    if name:
        payload['uservserver']['name'] = True

    if userprotocol:
        payload['uservserver']['userprotocol'] = True

    if ipaddress:
        payload['uservserver']['ipaddress'] = True

    if port:
        payload['uservserver']['port'] = True

    if defaultlb:
        payload['uservserver']['defaultlb'] = True

    if params:
        payload['uservserver']['Params'] = True

    if comment:
        payload['uservserver']['comment'] = True

    execution = __proxy__['citrixns.post']('config/uservserver?action=unset', payload)

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


def update_userprotocol(name=None, transport=None, extension=None, comment=None, save=False):
    '''
    Update the running configuration for the userprotocol config key.

    name(str): Unique name for the user protocol. Not case sensitive. Must begin with an ASCII letter or underscore (_)
        character, and must consist only of ASCII alphanumeric or underscore characters. Minimum length = 1

    transport(str): Transport layers protocol. Possible values = TCP, SSL

    extension(str): Name of the extension to add parsing and runtime handling of the protocol packets.

    comment(str): Any comments associated with the protocol.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' user.update_userprotocol <args>

    '''

    result = {}

    payload = {'userprotocol': {}}

    if name:
        payload['userprotocol']['name'] = name

    if transport:
        payload['userprotocol']['transport'] = transport

    if extension:
        payload['userprotocol']['extension'] = extension

    if comment:
        payload['userprotocol']['comment'] = comment

    execution = __proxy__['citrixns.put']('config/userprotocol', payload)

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


def update_uservserver(name=None, userprotocol=None, ipaddress=None, port=None, defaultlb=None, params=None,
                       comment=None, save=False):
    '''
    Update the running configuration for the uservserver config key.

    name(str): Name for the virtual server. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign (=),
        and hyphen (-) characters.  CLI Users: If the name includes one or more spaces, enclose the name in double or
        single quotation marks (for example, "my vserver" or my vserver). . Minimum length = 1

    userprotocol(str): User protocol uesd by the service.

    ipaddress(str): IPv4 or IPv6 address to assign to the virtual server.

    port(int): Port number for the virtual server. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    defaultlb(str): Name of the default Load Balancing virtual server used for load balancing of services. The protocol type
        of default Load Balancing virtual server should be a user type.

    params(str): Any comments associated with the protocol.

    comment(str): Any comments that you might want to associate with the virtual server.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' user.update_uservserver <args>

    '''

    result = {}

    payload = {'uservserver': {}}

    if name:
        payload['uservserver']['name'] = name

    if userprotocol:
        payload['uservserver']['userprotocol'] = userprotocol

    if ipaddress:
        payload['uservserver']['ipaddress'] = ipaddress

    if port:
        payload['uservserver']['port'] = port

    if defaultlb:
        payload['uservserver']['defaultlb'] = defaultlb

    if params:
        payload['uservserver']['Params'] = params

    if comment:
        payload['uservserver']['comment'] = comment

    execution = __proxy__['citrixns.put']('config/uservserver', payload)

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
