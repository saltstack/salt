# -*- coding: utf-8 -*-
'''
NAPALM SNMP
===========

Manages SNMP on network devices.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------
- :mod:`NAPALM proxy minion <salt.proxy.napalm>`
- :mod:`NET basic features <salt.modules.napalm_network>`

.. seealso::
    :mod:`SNMP configuration management state <salt.states.netsnmp>`

.. versionadded:: 2016.11.0
'''

from __future__ import absolute_import

import logging
log = logging.getLogger(__file__)

try:
    # will try to import NAPALM
    # https://github.com/napalm-automation/napalm
    # pylint: disable=W0611
    from napalm_base import get_network_driver
    # pylint: enable=W0611
    HAS_NAPALM = True
except ImportError:
    HAS_NAPALM = False

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'snmp'
__proxyenabled__ = ['napalm']
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():

    '''
    NAPALM library must be installed for this module to work.
    Also, the key proxymodule must be set in the __opts___ dictionary.
    '''

    if HAS_NAPALM and 'proxy' in __opts__:
        return __virtualname__
    else:
        return (False, 'The module SNMP (napalm_snmp) cannot be loaded: \
                NAPALM or proxy could not be loaded.')

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def config():

    '''
    Returns the SNMP configuration

    CLI Example:

    .. code-block:: bash

        salt '*' snmp.config
    '''

    return __proxy__['napalm.call'](
        'get_snmp_information',
        **{
        }
    )


def remove_config(chassis_id=None,
                  community=None,
                  contact=None,
                  location=None,
                  test=False,
                  commit=True):

    '''
    Removes a configuration element from the SNMP configuration.

    :param chassis_id: (optional) Chassis ID
    :param community: (optional) A dictionary having the following optional keys:
        * acl (if any policy / ACL need to be set)
        * mode: rw or ro. Default: ro
    :param contact: Contact details
    :param location: Location
    :param test: Dry run? If set as True, will apply the config, discard and return the changes. Default: False
    and will commit the changes on the device.
    :param commit: Commit? (default: True) Sometimes it is not needed to commit the config immediately
        after loading the changes. E.g.: a state loads a couple of parts (add / remove / update)
        and would not be optimal to commit after each operation.
        Also, from the CLI when the user needs to apply the similar changes before committing,
        can specify commit=False and will not discard the config.
    :raise MergeConfigException: If there is an error on the configuration sent.
    :return a dictionary having the following keys:
        * result (bool): if the config was applied successfully. It is `False` only in case of failure. In case
        there are no changes to be applied and successfully performs all operations it is still `True` and so will be
        the `already_configured` flag (example below)
        * comment (str): a message for the user
        * already_configured (bool): flag to check if there were no changes applied
        * diff (str): returns the config changes applied

    CLI Example:

    .. code-block:: bash

        salt '*' snmp.remove_config community='abcd'
    '''

    dic = {
        'template_name': 'delete_snmp_config',
        'test': test,
        'commit': commit
    }

    if chassis_id:
        dic['chassis_id'] = chassis_id
    if community:
        dic['community'] = community
    if contact:
        dic['contact'] = contact
    if location:
        dic['location'] = location

    return __salt__['net.load_template'](**dic)


def update_config(chassis_id=None,
                  community=None,
                  contact=None,
                  location=None,
                  test=False,
                  commit=True):

    '''
    Updates the SNMP configuration.

    :param chassis_id: (optional) Chassis ID
    :param community: (optional) A dictionary having the following optional keys:
        * acl (if any policy / ACL need to be set)
        * mode: rw or ro. Default: ro
    :param contact: Contact details
    :param location: Location
    :param test: Dry run? If set as True, will apply the config, discard and return the changes. Default: False
    and will commit the changes on the device.
    :param commit: Commit? (default: True) Sometimes it is not needed to commit the config immediately
        after loading the changes. E.g.: a state loads a couple of parts (add / remove / update)
        and would not be optimal to commit after each operation.
        Also, from the CLI when the user needs to apply the similar changes before committing,
        can specify commit=False and will not discard the config.
    :raise MergeConfigException: If there is an error on the configuration sent.
    :return a dictionary having the following keys:
        * result (bool): if the config was applied successfully. It is `False` only in case of failure. In case
        there are no changes to be applied and successfully performs all operations it is still `True` and so will be
        the `already_configured` flag (example below)
        * comment (str): a message for the user
        * already_configured (bool): flag to check if there were no changes applied
        * diff (str): returns the config changes applied

    CLI Example:

    .. code-block:: bash

        salt 'edge01.lon01' snmp.update_config location="Greenwich, UK" test=True

    Output example (for the CLI example above):

    .. code-block:: yaml

        edge01.lon01:
            ----------
            already_configured:
                False
            comment:
                Configuration discarded.
            diff:
                [edit snmp]
                -  location "London, UK";
                +  location "Greenwich, UK";
            result:
                True
    '''

    dic = {
        'template_name': 'snmp_config',
        'test': test,
        'commit': commit
    }

    if chassis_id:
        dic['chassis_id'] = chassis_id
    if community:
        dic['community'] = community
    if contact:
        dic['contact'] = contact
    if location:
        dic['location'] = location

    return __salt__['net.load_template'](**dic)
