# -*- coding: utf-8 -*-
'''
A state module to manage Blue Coat SSL Visibility Devices.

:codeauthor: Spencer Ervin <spencer_ervin@hotmail.com>
:maturity:   new
:depends:    none
:platform:   unix


About
=====

This state module was designed to handle connections to a Blue Coat SSL Visibility device. This
module relies on the bluecoat_sslv proxy module to interface with the device.

.. seealso::
    :py:mod:`Bluecoat SSLV Proxy Module <salt.proxy.bluecoat_sslv>`

'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Libs
import salt.exceptions

log = logging.getLogger(__name__)


def __virtual__():
    return 'bluecoat_sslv.get_management_config' in __salt__


def _default_ret(name):
    '''
    Set the default response values.

    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': ''
    }
    return ret


def distinguished_name_list_exists(name, items):
    '''
    Ensures that a distinguished name list exists with the items provided.

    name: The name of the module function to execute.

    name(str): The name of the distinguished names list.

    items(list): A list of items to ensure exist on the distinguished names list.

    SLS Example:

    .. code-block:: yaml

        MyDistinguishedNameList:
          bluecoat_sslv.distinguished_name_list_exists:
            items:
              - cn=test.com
              - cn=othersite.com

    '''
    ret = _default_ret(name)
    req_change = False
    try:
        existing_lists = __salt__['bluecoat_sslv.get_distinguished_name_lists']()
        if name not in existing_lists:
            __salt__['bluecoat_sslv.add_distinguished_name_list'](name)
            req_change = True
        list_members = __salt__['bluecoat_sslv.get_distinguished_name_list'](name)
        for item in items:
            if item not in list_members:
                __salt__['bluecoat_sslv.add_distinguished_name'](name, item)
                req_change = True
        if req_change:
            ret['changes']['before'] = list_members
            ret['changes']['after'] = __salt__['bluecoat_sslv.get_distinguished_name_list'](name)
            ret['comment'] = "Updated distinguished name list."
        else:
            ret['comment'] = "No changes required."
    except salt.exceptions.CommandExecutionError as err:
        ret['result'] = False
        ret['comment'] = err
        log.error(err)
        return ret
    ret['result'] = True
    return ret


def domain_name_list_exists(name, items):
    '''
    Ensures that a domain name list exists with the items provided.

    name: The name of the module function to execute.

    name(str): The name of the domain names list.

    items(list): A list of items to ensure exist on the domain names list.

    SLS Example:

    .. code-block:: yaml

        MyDomainNameList:
          bluecoat_sslv.domain_name_list_exists:
            items:
              - foo.bar.com
              - test.com

    '''
    ret = _default_ret(name)
    req_change = False
    try:
        existing_lists = __salt__['bluecoat_sslv.get_domain_lists']()
        if name not in existing_lists:
            __salt__['bluecoat_sslv.add_domain_name_list'](name)
            req_change = True
        list_members = __salt__['bluecoat_sslv.get_domain_list'](name)
        for item in items:
            if item not in list_members:
                __salt__['bluecoat_sslv.add_domain_name'](name, item)
                req_change = True
        if req_change:
            ret['changes']['before'] = list_members
            ret['changes']['after'] = __salt__['bluecoat_sslv.get_domain_lists'](name)
            ret['comment'] = "Updated domain name list."
        else:
            ret['comment'] = "No changes required."
    except salt.exceptions.CommandExecutionError as err:
        ret['result'] = False
        ret['comment'] = err
        log.error(err)
        return ret
    ret['result'] = True
    return ret


def ip_address_list_exists(name, items):
    '''
    Ensures that an IP address list exists with the items provided.

    name: The name of the module function to execute.

    name(str): The name of the IP address list.

    items(list): A list of items to ensure exist on the IP address list.

    SLS Example:

    .. code-block:: yaml

        MyIPAddressList:
          bluecoat_sslv.ip_address_list_exists:
            items:
              - 10.0.0.0/24
              - 192.168.1.134

    '''
    ret = _default_ret(name)
    req_change = False
    try:
        existing_lists = __salt__['bluecoat_sslv.get_ip_address_lists']()
        if name not in existing_lists:
            __salt__['bluecoat_sslv.add_ip_address_list'](name)
            req_change = True
        list_members = __salt__['bluecoat_sslv.get_ip_address_list'](name)
        for item in items:
            if item not in list_members:
                __salt__['bluecoat_sslv.add_ip_address'](name, item)
                req_change = True
        if req_change:
            ret['changes']['before'] = list_members
            ret['changes']['after'] = __salt__['bluecoat_sslv.get_ip_address_list'](name)
            ret['comment'] = "Updated IP address list."
        else:
            ret['comment'] = "No changes required."
    except salt.exceptions.CommandExecutionError as err:
        ret['result'] = False
        ret['comment'] = err
        log.error(err)
        return ret
    ret['result'] = True
    return ret
