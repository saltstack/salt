# -*- coding: utf-8 -*-
'''
Module for managing SNMP service settings on Windows servers.
The Windows feature 'SNMP-Service' must be installed.

'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
from salt.exceptions import SaltInvocationError
import salt.utils

_HKEY = 'HKLM'
_SNMP_KEY = r'SYSTEM\CurrentControlSet\Services\SNMP\Parameters'
_AGENT_KEY = r'{0}\RFC1156Agent'.format(_SNMP_KEY)
_COMMUNITIES_KEY = r'{0}\ValidCommunities'.format(_SNMP_KEY)

_PERMISSION_TYPES = {'None': 1, 'Notify': 2, 'Read Only': 4, 'Read Write': 8,
                     'Read Create': 16}
_SERVICE_TYPES = {'None': 0, 'Physical': 1, 'Datalink and subnetwork': 2, 'Internet': 4,
                  'End-to-end': 8, 'Applications': 64}

_LOG = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'win_snmp'


def __virtual__():
    '''
    Only works on Windows systems.
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def get_agent_service_types():
    '''
    Get the sysServices types that can be configured.

    :return: A list of the service types.
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' win_snmp.get_agent_service_types
    '''
    return list(_SERVICE_TYPES)


def get_permission_types():
    '''
    Get the permission types that can be configured for communities.

    :return: A list of the permission types.
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' win_snmp.get_permission_types
    '''
    return list(_PERMISSION_TYPES)


def get_agent_settings():
    '''
    Determine the value of the SNMP sysContact, sysLocation, and sysServices settings.

    :return: A dictionary of the agent settings.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_snmp.get_agent_settings
    '''
    ret = dict()
    sorted_types = sorted(_SERVICE_TYPES.items(), key=lambda x: (-x[1], x[0]))

    ret['services'] = list()
    ret['contact'] = (__salt__['reg.read_value'](_HKEY, _AGENT_KEY, 'sysContact'))['vdata']
    ret['location'] = (__salt__['reg.read_value'](_HKEY, _AGENT_KEY, 'sysLocation'))['vdata']
    current_bitmask = (__salt__['reg.read_value'](_HKEY, _AGENT_KEY, 'sysServices'))['vdata']

    if current_bitmask == 0:
        ret['services'].append(sorted_types[-1][0])
    else:
        # sorted_types is sorted from greatest to least bitmask.
        for service, bitmask in sorted_types:
            if current_bitmask > 0:
                remaining_bitmask = current_bitmask - bitmask

                if remaining_bitmask >= 0:
                    current_bitmask = remaining_bitmask
                    ret['services'].append(service)
            else:
                break

    ret['services'] = sorted(ret['services'])
    return ret


def set_agent_settings(contact, location, services=None):
    '''
    Manage the SNMP sysContact, sysLocation, and sysServices settings.

    :param str contact: The SNMP contact.
    :param str location: The SNMP location.
    :param str services: A list of selected services. The possible service names can be found
    via win_snmp.get_agent_service_types.

    :return: A boolean representing whether the change succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_snmp.set_agent_settings contact='Contact Name' location='Place' services="['Physical']"
    '''
    if not services:
        services = ['None']

    # Filter services for unique items, and sort them for comparison purposes.
    services = sorted(set(services))

    settings = {'contact': contact, 'location': location, 'services': services}

    current_settings = get_agent_settings()

    if settings == current_settings:
        _LOG.debug('Agent settings already contain the provided values.')
        return True

    # Validate the services.
    for service in services:
        if service not in _SERVICE_TYPES:
            message = ("Invalid service '{0}' specified. Valid services:"
                       ' {1}').format(service, get_agent_service_types())
            raise SaltInvocationError(message)

    if contact != current_settings['contact']:
        __salt__['reg.set_value'](_HKEY, _AGENT_KEY, 'sysContact', contact, 'REG_SZ')

    if location != current_settings['location']:
        __salt__['reg.set_value'](_HKEY, _AGENT_KEY, 'sysLocation', location, 'REG_SZ')

    if set(services) != set(current_settings['services']):
        # Calculate the total value. Produces 0 if an empty list was provided,
        # corresponding to the None _SERVICE_TYPES value.
        vdata = sum(_SERVICE_TYPES[service] for service in services)

        _LOG.debug('Setting sysServices vdata to: %s', vdata)

        __salt__['reg.set_value'](_HKEY, _AGENT_KEY, 'sysServices', vdata, 'REG_DWORD')

    # Get the fields post-change so that we can verify tht all values
    # were modified successfully. Track the ones that weren't.
    new_settings = get_agent_settings()
    failed_settings = dict()

    for setting in settings:
        if settings[setting] != new_settings[setting]:
            failed_settings[setting] = settings[setting]

    if failed_settings:
        _LOG.error('Unable to configure agent settings: %s', failed_settings)
        return False
    _LOG.debug('Agent settings configured successfully: %s', settings.keys())
    return True


def get_auth_traps_enabled():
    '''
    Determine whether the host is configured to send authentication traps.

    :return: A boolean representing whether authentication traps are enabled.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_snmp.get_auth_traps_enabled
    '''
    reg_ret = __salt__['reg.read_value'](_HKEY, _SNMP_KEY, 'EnableAuthenticationTraps')

    if reg_ret['vdata'] == '(value not set)':
        return False
    return bool(reg_ret['vdata'] or 0)


def set_auth_traps_enabled(status=True):
    '''
    Manage the sending of authentication traps.

    :param bool status: The enabled status.

    :return: A boolean representing whether the change succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_snmp.set_auth_traps_enabled status='True'
    '''
    vname = 'EnableAuthenticationTraps'
    current_status = get_auth_traps_enabled()

    if bool(status) == current_status:
        _LOG.debug('%s already contains the provided value.', vname)
        return True

    vdata = int(status)
    __salt__['reg.set_value'](_HKEY, _SNMP_KEY, vname, vdata, 'REG_DWORD')

    new_status = get_auth_traps_enabled()

    if status == new_status:
        _LOG.debug('Setting %s configured successfully: %s', vname, vdata)
        return True
    _LOG.error('Unable to configure %s with value: %s', vname, vdata)
    return False


def get_community_names():
    '''
    Get the current accepted SNMP community names and their permissions.

    :return: A dictionary of community names and permissions.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_snmp.get_community_names
    '''
    ret = dict()
    current_values = __salt__['reg.list_values'](_HKEY, _COMMUNITIES_KEY, include_default=False)

    # The communities are stored as the community name with a numeric permission value. Convert
    # the numeric value to the text equivalent, as present in the Windows SNMP service GUI.
    for current_value in current_values:
        permissions = str()
        for permission_name in _PERMISSION_TYPES:
            if current_value['vdata'] == _PERMISSION_TYPES[permission_name]:
                permissions = permission_name
                break
        ret[current_value['vname']] = permissions

    if not ret:
        _LOG.debug('Unable to find existing communities.')
    return ret


def set_community_names(communities):
    '''
    Manage the SNMP accepted community names and their permissions.

    :param str communities: A dictionary of SNMP community names and permissions.
    The possible permissions can be found via win_snmp.get_permission_types.

    :return: A boolean representing whether the change succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' win_snmp.set_community_names communities="{'TestCommunity': 'Read Only'}'
    '''
    values = dict()

    current_communities = get_community_names()

    if communities == current_communities:
        _LOG.debug('Communities already contain the provided values.')
        return True

    for vname in communities:
        if not communities[vname]:
            communities[vname] = 'None'
        try:
            vdata = _PERMISSION_TYPES[communities[vname]]
        except KeyError:
            message = ("Invalid permission '{0}' specified. Valid permissions:"
                       ' {1}').format(communities[vname], _PERMISSION_TYPES.keys())
            raise SaltInvocationError(message)
        values[vname] = vdata

    # Check current communities.
    for current_vname in current_communities:
        if current_vname in values:
            # Modify existing communities that have a different permission value.
            if current_communities[current_vname] != values[current_vname]:
                __salt__['reg.set_value'](_HKEY, _COMMUNITIES_KEY, current_vname, values[current_vname], 'REG_DWORD')
        else:
            # Remove current communities that weren't provided.
            __salt__['reg.delete_value'](_HKEY, _COMMUNITIES_KEY, current_vname)

    # Create any new communities.
    for vname in values:
        if vname not in current_communities:
            __salt__['reg.set_value'](_HKEY, _COMMUNITIES_KEY, vname, values[vname], 'REG_DWORD')

    # Get the fields post-change so that we can verify tht all values
    # were modified successfully. Track the ones that weren't.
    new_communities = get_community_names()
    failed_communities = dict()

    for new_vname in new_communities:
        if new_vname not in communities:
            failed_communities[new_vname] = None

    for vname in communities:
        if communities[vname] != new_communities[vname]:
            failed_communities[vname] = communities[vname]

    if failed_communities:
        _LOG.error('Unable to configure communities: %s', failed_communities)
        return False
    _LOG.debug('Communities configured successfully: %s', communities.keys())
    return True
