# -*- coding: utf-8 -*-
'''
Module to provide Blue Coat SSL Visibility compatibility to Salt.

:codeauthor: Spencer Ervin <spencer_ervin@hotmail.com>
:maturity:   new
:depends:    none
:platform:   unix


Configuration
=============

This module accepts connection configuration details either as
parameters, or as configuration settings in pillar as a Salt proxy.
Options passed into opts will be ignored if options are passed into pillar.

.. seealso::
    :py:mod:`Blue Coat SSL Visibility Proxy Module <salt.proxy.bluecoat_sslv>`

About
=====

This execution module was designed to handle connections to a Blue Coat SSL Visibility server.
This module adds support to send connections directly to the device through the rest API.

'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Libs
import salt.utils.platform
import salt.proxy.bluecoat_sslv

log = logging.getLogger(__name__)

__virtualname__ = 'bluecoat_sslv'


def __virtual__():
    '''
    Will load for the bluecoat_sslv proxy minions.
    '''
    try:
        if salt.utils.platform.is_proxy() and \
           __opts__['proxy']['proxytype'] == 'bluecoat_sslv':
            return __virtualname__
    except KeyError:
        pass

    return False, 'The bluecoat_sslv execution module can only be loaded for bluecoat_sslv proxy minions.'


def _validate_change_result(response):
    if response['result'] == "true" or response['result'] is True:
        return True
    return False


def _convert_to_list(response, item_key):
    full_list = []
    for item in response['result'][0]:
        full_list.append(item[item_key])
    return full_list


def _collapse_dict_format(response):
    decoded = {}
    for item in response:
        decoded[item['key']] = item['value']
    return decoded


def add_distinguished_name(list_name, item_name):
    '''
    Adds a distinguished name to a distinguished name list.

    list_name(str): The name of the specific policy distinguished name list to append to.

    item_name(str): The distinguished name to append.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.add_distinguished_name MyDistinguishedList cn=foo.bar.com

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "add_policy_distinguished_names",
               "params": [list_name, {"item_name": item_name}]}

    response = __proxy__['bluecoat_sslv.call'](payload, True)

    return _validate_change_result(response)


def add_distinguished_name_list(list_name):
    '''
    Add a list of policy distinguished names.

    list_name(str): The name of the specific policy distinguished name list to add.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.add_distinguished_name_list MyDistinguishedList

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "add_policy_distinguished_names_list",
               "params": [{"list_name": list_name}]}

    response = __proxy__['bluecoat_sslv.call'](payload, True)

    return _validate_change_result(response)


def add_domain_name(list_name, item_name):
    '''
    Adds a domain name to a domain name list.

    list_name(str): The name of the specific policy domain name list to append to.

    item_name(str): The domain name to append.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.add_domain_name MyDomainName foo.bar.com

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "add_policy_domain_names",
               "params": [list_name, {"item_name": item_name}]}

    response = __proxy__['bluecoat_sslv.call'](payload, True)

    return _validate_change_result(response)


def add_domain_name_list(list_name):
    '''
    Add a list of policy domain names.

    list_name(str): The name of the specific policy domain name list to add.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.add_domain_name_list MyDomainNameList

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "add_policy_domain_names_list",
               "params": [{"list_name": list_name}]}

    response = __proxy__['bluecoat_sslv.call'](payload, True)

    return _validate_change_result(response)


def add_ip_address(list_name, item_name):
    '''
    Add an IP address to an IP address list.

    list_name(str): The name of the specific policy IP address list to append to.

    item_name(str): The IP address to append to the list.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.add_ip_address MyIPAddressList 10.0.0.0/24

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "add_policy_ip_addresses",
               "params": [list_name, {"item_name": item_name}]}

    response = __proxy__['bluecoat_sslv.call'](payload, True)

    return _validate_change_result(response)


def add_ip_address_list(list_name):
    '''
    Retrieves a list of all IP address lists.

    list_name(str): The name of the specific IP address list to add.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.add_ip_address_list MyIPAddressList

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "add_policy_ip_addresses_list",
               "params": [{"list_name": list_name}]}

    response = __proxy__['bluecoat_sslv.call'](payload, True)

    return _validate_change_result(response)


def get_distinguished_name_list(list_name):
    '''
    Retrieves a specific policy distinguished name list.

    list_name(str): The name of the specific policy distinguished name list to retrieve.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_distinguished_name_list MyDistinguishedList

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_policy_distinguished_names",
               "params": [list_name, 0, 256]}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return _convert_to_list(response, 'item_name')


def get_distinguished_name_lists():
    '''
    Retrieves a list of all policy distinguished name lists.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_distinguished_name_lists

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_policy_distinguished_names_list",
               "params": [0, 256]}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return _convert_to_list(response, 'list_name')


def get_domain_list(list_name):
    '''
    Retrieves a specific policy domain name list.

    list_name(str): The name of the specific policy domain name list to retrieve.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_domain_list MyDomainNameList

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_policy_domain_names",
               "params": [list_name, 0, 256]}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return _convert_to_list(response, 'item_name')


def get_domain_lists():
    '''
    Retrieves a list of all policy domain name lists.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_domain_name_lists

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_policy_domain_names_list",
               "params": [0, 256]}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return _convert_to_list(response, 'list_name')


def get_ip_address_list(list_name):
    '''
    Retrieves a specific IP address list.

    list_name(str): The name of the specific policy IP address list to retrieve.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_ip_address_list MyIPAddressList

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_policy_ip_addresses",
               "params": [list_name, 0, 256]}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return _convert_to_list(response, 'item_name')


def get_ip_address_lists():
    '''
    Retrieves a list of all IP address lists.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_ip_address_lists

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_policy_ip_addresses_list",
               "params": [0, 256]}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return _convert_to_list(response, 'list_name')


def get_ipv4_config():
    '''
    Retrieves IPv4 configuration from the device.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_ipv4_config

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_platform_config_ipv4",
               "params": []}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return response['result']


def get_ipv6_config():
    '''
    Retrieves IPv6 configuration from the device.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_ipv6_config

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_platform_config_ipv6",
               "params": []}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return response['result']


def get_management_config():
    '''
    Retrieves management configuration for the device.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_management_config

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_platform_config",
               "params": []}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return response['result']


def get_platform():
    '''
    Retrieves platform information, such as serial number and part number.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_platform

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_platform_information_chassis",
               "params": []}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return _collapse_dict_format(response['result'])


def get_software():
    '''
    Retrieves platform software information, such as software version number.

    CLI Example:

    .. code-block:: bash

        salt '*' bluecoat_sslv.get_software

    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "get_platform_information_sw_rev",
               "params": []}

    response = __proxy__['bluecoat_sslv.call'](payload, False)

    return _collapse_dict_format(response['result'])
