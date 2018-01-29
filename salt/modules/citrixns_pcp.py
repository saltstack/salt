# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the pcp key.

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

__virtualname__ = 'pcp'


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

    return False, 'The pcp execution module can only be loaded for citrixns proxy minions.'


def add_pcpprofile(name=None, mapping=None, peer=None, minmaplife=None, maxmaplife=None, announcemulticount=None,
                   thirdparty=None, save=False):
    '''
    Add a new pcpprofile to the running configuration.

    name(str): Name for the PCP Profile. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore CLI Users: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my pcpProfile" or my pcpProfile).

    mapping(str): This argument is for enabling/disabling the MAP opcode of current PCP Profile. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    peer(str): This argument is for enabling/disabling the PEER opcode of current PCP Profile. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    minmaplife(int): Integer value that identify the minimum mapping lifetime (in seconds) for a pcp profile. default(120s).
        Minimum value = 0 Maximum value = 2147483647

    maxmaplife(int): Integer value that identify the maximum mapping lifetime (in seconds) for a pcp profile. default(86400s
        = 24Hours). Minimum value = 0 Maximum value = 2147483647

    announcemulticount(int): Integer value that identify the number announce message to be send. Default value: 10 Minimum
        value = 0 Maximum value = 65535

    thirdparty(str): This argument is for enabling/disabling the THIRD PARTY opcode of current PCP Profile. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' pcp.add_pcpprofile <args>

    '''

    result = {}

    payload = {'pcpprofile': {}}

    if name:
        payload['pcpprofile']['name'] = name

    if mapping:
        payload['pcpprofile']['mapping'] = mapping

    if peer:
        payload['pcpprofile']['peer'] = peer

    if minmaplife:
        payload['pcpprofile']['minmaplife'] = minmaplife

    if maxmaplife:
        payload['pcpprofile']['maxmaplife'] = maxmaplife

    if announcemulticount:
        payload['pcpprofile']['announcemulticount'] = announcemulticount

    if thirdparty:
        payload['pcpprofile']['thirdparty'] = thirdparty

    execution = __proxy__['citrixns.post']('config/pcpprofile', payload)

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


def add_pcpserver(name=None, ipaddress=None, port=None, pcpprofile=None, save=False):
    '''
    Add a new pcpserver to the running configuration.

    name(str): Name for the PCP server. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore CLI Users: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my pcpServer" or my pcpServer).

    ipaddress(str): The IP address of the PCP server.

    port(int): Port number for the PCP server. Default value: 5351 Range 1 - 65535 * in CLI is represented as 65535 in NITRO
        API

    pcpprofile(str): pcp profile name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' pcp.add_pcpserver <args>

    '''

    result = {}

    payload = {'pcpserver': {}}

    if name:
        payload['pcpserver']['name'] = name

    if ipaddress:
        payload['pcpserver']['ipaddress'] = ipaddress

    if port:
        payload['pcpserver']['port'] = port

    if pcpprofile:
        payload['pcpserver']['pcpprofile'] = pcpprofile

    execution = __proxy__['citrixns.post']('config/pcpserver', payload)

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


def get_pcpmap():
    '''
    Show the running configuration for the pcpmap config key.

    CLI Example:

    .. code-block:: bash

    salt '*' pcp.get_pcpmap

    '''

    search_filter = []

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/pcpmap{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'pcpmap')

    return response


def get_pcpprofile(name=None, mapping=None, peer=None, minmaplife=None, maxmaplife=None, announcemulticount=None,
                   thirdparty=None):
    '''
    Show the running configuration for the pcpprofile config key.

    name(str): Filters results that only match the name field.

    mapping(str): Filters results that only match the mapping field.

    peer(str): Filters results that only match the peer field.

    minmaplife(int): Filters results that only match the minmaplife field.

    maxmaplife(int): Filters results that only match the maxmaplife field.

    announcemulticount(int): Filters results that only match the announcemulticount field.

    thirdparty(str): Filters results that only match the thirdparty field.

    CLI Example:

    .. code-block:: bash

    salt '*' pcp.get_pcpprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if mapping:
        search_filter.append(['mapping', mapping])

    if peer:
        search_filter.append(['peer', peer])

    if minmaplife:
        search_filter.append(['minmaplife', minmaplife])

    if maxmaplife:
        search_filter.append(['maxmaplife', maxmaplife])

    if announcemulticount:
        search_filter.append(['announcemulticount', announcemulticount])

    if thirdparty:
        search_filter.append(['thirdparty', thirdparty])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/pcpprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'pcpprofile')

    return response


def get_pcpserver(name=None, ipaddress=None, port=None, pcpprofile=None):
    '''
    Show the running configuration for the pcpserver config key.

    name(str): Filters results that only match the name field.

    ipaddress(str): Filters results that only match the ipaddress field.

    port(int): Filters results that only match the port field.

    pcpprofile(str): Filters results that only match the pcpprofile field.

    CLI Example:

    .. code-block:: bash

    salt '*' pcp.get_pcpserver

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if ipaddress:
        search_filter.append(['ipaddress', ipaddress])

    if port:
        search_filter.append(['port', port])

    if pcpprofile:
        search_filter.append(['pcpprofile', pcpprofile])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/pcpserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'pcpserver')

    return response


def unset_pcpprofile(name=None, mapping=None, peer=None, minmaplife=None, maxmaplife=None, announcemulticount=None,
                     thirdparty=None, save=False):
    '''
    Unsets values from the pcpprofile configuration key.

    name(bool): Unsets the name value.

    mapping(bool): Unsets the mapping value.

    peer(bool): Unsets the peer value.

    minmaplife(bool): Unsets the minmaplife value.

    maxmaplife(bool): Unsets the maxmaplife value.

    announcemulticount(bool): Unsets the announcemulticount value.

    thirdparty(bool): Unsets the thirdparty value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' pcp.unset_pcpprofile <args>

    '''

    result = {}

    payload = {'pcpprofile': {}}

    if name:
        payload['pcpprofile']['name'] = True

    if mapping:
        payload['pcpprofile']['mapping'] = True

    if peer:
        payload['pcpprofile']['peer'] = True

    if minmaplife:
        payload['pcpprofile']['minmaplife'] = True

    if maxmaplife:
        payload['pcpprofile']['maxmaplife'] = True

    if announcemulticount:
        payload['pcpprofile']['announcemulticount'] = True

    if thirdparty:
        payload['pcpprofile']['thirdparty'] = True

    execution = __proxy__['citrixns.post']('config/pcpprofile?action=unset', payload)

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


def unset_pcpserver(name=None, ipaddress=None, port=None, pcpprofile=None, save=False):
    '''
    Unsets values from the pcpserver configuration key.

    name(bool): Unsets the name value.

    ipaddress(bool): Unsets the ipaddress value.

    port(bool): Unsets the port value.

    pcpprofile(bool): Unsets the pcpprofile value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' pcp.unset_pcpserver <args>

    '''

    result = {}

    payload = {'pcpserver': {}}

    if name:
        payload['pcpserver']['name'] = True

    if ipaddress:
        payload['pcpserver']['ipaddress'] = True

    if port:
        payload['pcpserver']['port'] = True

    if pcpprofile:
        payload['pcpserver']['pcpprofile'] = True

    execution = __proxy__['citrixns.post']('config/pcpserver?action=unset', payload)

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


def update_pcpprofile(name=None, mapping=None, peer=None, minmaplife=None, maxmaplife=None, announcemulticount=None,
                      thirdparty=None, save=False):
    '''
    Update the running configuration for the pcpprofile config key.

    name(str): Name for the PCP Profile. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore CLI Users: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my pcpProfile" or my pcpProfile).

    mapping(str): This argument is for enabling/disabling the MAP opcode of current PCP Profile. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    peer(str): This argument is for enabling/disabling the PEER opcode of current PCP Profile. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    minmaplife(int): Integer value that identify the minimum mapping lifetime (in seconds) for a pcp profile. default(120s).
        Minimum value = 0 Maximum value = 2147483647

    maxmaplife(int): Integer value that identify the maximum mapping lifetime (in seconds) for a pcp profile. default(86400s
        = 24Hours). Minimum value = 0 Maximum value = 2147483647

    announcemulticount(int): Integer value that identify the number announce message to be send. Default value: 10 Minimum
        value = 0 Maximum value = 65535

    thirdparty(str): This argument is for enabling/disabling the THIRD PARTY opcode of current PCP Profile. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' pcp.update_pcpprofile <args>

    '''

    result = {}

    payload = {'pcpprofile': {}}

    if name:
        payload['pcpprofile']['name'] = name

    if mapping:
        payload['pcpprofile']['mapping'] = mapping

    if peer:
        payload['pcpprofile']['peer'] = peer

    if minmaplife:
        payload['pcpprofile']['minmaplife'] = minmaplife

    if maxmaplife:
        payload['pcpprofile']['maxmaplife'] = maxmaplife

    if announcemulticount:
        payload['pcpprofile']['announcemulticount'] = announcemulticount

    if thirdparty:
        payload['pcpprofile']['thirdparty'] = thirdparty

    execution = __proxy__['citrixns.put']('config/pcpprofile', payload)

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


def update_pcpserver(name=None, ipaddress=None, port=None, pcpprofile=None, save=False):
    '''
    Update the running configuration for the pcpserver config key.

    name(str): Name for the PCP server. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore CLI Users: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my pcpServer" or my pcpServer).

    ipaddress(str): The IP address of the PCP server.

    port(int): Port number for the PCP server. Default value: 5351 Range 1 - 65535 * in CLI is represented as 65535 in NITRO
        API

    pcpprofile(str): pcp profile name.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' pcp.update_pcpserver <args>

    '''

    result = {}

    payload = {'pcpserver': {}}

    if name:
        payload['pcpserver']['name'] = name

    if ipaddress:
        payload['pcpserver']['ipaddress'] = ipaddress

    if port:
        payload['pcpserver']['port'] = port

    if pcpprofile:
        payload['pcpserver']['pcpprofile'] = pcpprofile

    execution = __proxy__['citrixns.put']('config/pcpserver', payload)

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
