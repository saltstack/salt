# -*- coding: utf-8 -*-
'''
The networking module for NI Linux Real-Time distro

'''

# Import python libs
from __future__ import absolute_import
import logging
import time

# Import salt libs
import salt.utils
import salt.utils.validate.net
import salt.exceptions

# Import 3rd-party libs
import salt.ext.six as six
try:
    import pyconnman
    HAS_PYCONNMAN = True
except ImportError:
    HAS_PYCONNMAN = False
try:
    import dbus
    HAS_DBUS = True
except ImportError:
    HAS_DBUS = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'ip'

SERVICE_PATH = '/net/connman/service/'
_CONFIG_TRUE = ['yes', 'on', 'true', '1', True]


def __virtual__():
    '''
    Confine this module to NI Linux Real-Time based distros
    '''
    if not HAS_PYCONNMAN:
        return False, 'The python package pyconnman is not installed'
    if not HAS_DBUS:
        return False, 'The python DBus package is not installed'
    if __grains__['os_family'] == 'NILinuxRT':
        try:
            state = _get_state
            if state == 'offline':
                return False, 'Connmand is not running'
        except Exception as exc:
            return False, str(exc)
        return __virtualname__
    return False, 'The nilrt_ip module could not be loaded: unsupported OS family'


def _get_state():
    try:
        state = pyconnman.ConnManager().get_property('State')
    except Exception as exc:
        raise salt.exceptions.CommandExecutionError('Connman daemon error: {0}'.format(exc))
    return state


def _get_technologies():
    strTech = ''
    technologies = pyconnman.ConnManager().get_technologies()
    for path, params in technologies:
        strTech += '{0}\n\tName = {1}\n\tType = {2}\n\tPowered = {3}\n\tConnected = {4}\n'.format(
            path, params['Name'], params['Type'], params['Powered'] == 1, params['Connected'] == 1)
    return strTech


def _add_path(service):
    return '{0}{1}'.format(SERVICE_PATH, service)


def _get_services():
    '''
    Returns a list with all connman services.
    '''
    serviceList = []
    services = pyconnman.ConnManager().get_services()
    for path, params in services:
        serviceList.append(str(path[len(SERVICE_PATH):]))
    return serviceList


def _connected(service):
    '''
    Verify if a connman service is connected
    '''
    state = pyconnman.ConnService(_add_path(service)).get_property('State')
    return state == 'online' or state == 'ready'


def _space_delimited_list(value):
    '''
    validate that a value contains one or more space-delimited values
    '''
    valid, _value, errmsg = False, value, 'space-delimited string'
    try:
        if hasattr(value, '__iter__'):
            valid = True
        else:
            _value = value.split()
            if _value == []:
                raise ValueError
            valid = True
    except AttributeError:
        errmsg = '{0} is not a valid list.\n'.format(value)
    except ValueError:
        errmsg = '{0} is not a valid list.\n'.format(value)
    return (valid, errmsg)


def _validate_ipv4(value):
    '''
    validate ipv4 values
    '''
    if len(value) == 3:
        if not salt.utils.validate.net.ipv4_addr(value[0].strip()):
            return (False, 'Invalid ip address: {0} for ipv4 option'.format(value[0]))
        if not salt.utils.validate.net.netmask(value[1].strip()):
            return (False, 'Invalid netmask: {0} for ipv4 option'.format(value[1]))
        if not salt.utils.validate.net.ipv4_addr(value[2].strip()):
            return (False, 'Invalid gateway: {0} for ipv4 option'.format(value[2]))
    else:
        return (False, 'Invalid value: {0} for ipv4 option'.format(value))
    return (True, '')


def _interface_to_service(iface):
    '''
    returns the coresponding service to given interface if exists, otherwise return None
    '''
    for _service in _get_services():
        service_info = pyconnman.ConnService(_add_path(_service))
        if service_info.get_property('Ethernet')['Interface'] == iface:
            return _service
    return None


def _get_service_info(service):
    '''
    return details about given connman service
    '''
    service_info = pyconnman.ConnService(_add_path(service))
    data = {
        'name': service,
        'wireless': service_info.get_property('Type') == 'wifi',
        'connectionid': str(service_info.get_property('Ethernet')['Interface']),
        'HWAddress': str(service_info.get_property('Ethernet')['Address'])
    }

    state = service_info.get_property('State')
    if state == 'ready' or state == 'online':
        data['up'] = True
        data['ipv4'] = {}
        ipv4 = 'IPv4'
        if service_info.get_property('IPv4')['Method'] == 'manual':
            ipv4 += '.Configuration'
        ipv4Info = service_info.get_property(ipv4)
        for info in ['Method', 'Address', 'Netmask', 'Gateway']:
            try:
                value = ipv4Info[info]
                if info == 'Method':
                    info = 'requestmode'
                    if value == 'dhcp':
                        value = 'dhcp_linklocal'
                    elif value == 'manual':
                        value = 'static'
                data['ipv4'][info.lower()] = str(value)
            except Exception as exc:
                log.warning('Unable to get IPv4 {0} for service {1}\n'.format(info, service))

        ipv6Info = service_info.get_property('IPv6')
        for info in ['Address', 'Prefix', 'Gateway']:
            try:
                value = ipv6Info[info]
                data['ipv6'][info.lower()] = [str(value)]
            except Exception as exc:
                log.warning('Unable to get IPv6 {0} for service {1}\n'.format(info, service))

        domains = []
        for x in service_info.get_property('Domains'):
            domains.append(str(x))
        data['ipv4']['dns'] = domains
    else:
        data['up'] = False

    if 'ipv4' in data:
        data['ipv4']['supportedrequestmodes'] = [
            'static',
            'dhcp_linklocal'
        ]
    return data


def _dict_to_string(dictionary):
    '''
    converts a dictionary object into a list of strings
    '''
    ret = ''
    for key, val in sorted(dictionary.items()):
        if isinstance(val, dict):
            for line in _dict_to_string(val):
                ret += str(key) + '-' + line + '\n'
        elif isinstance(val, list):
            stringList = ''
            for item in val:
                stringList += str(item) + ' '
            ret += str(key) + ': ' + stringList +'\n'
        else:
            ret += str(key) + ': ' + str(val) +'\n'
    return ret.splitlines()


def get_interfaces_details():
    '''
    Get details about all the interfaces on the minion

    :return: information about all connmans interfaces
    :rtype: dictionary

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interfaces_details
    '''
    services = []
    for service in _get_services():
        services.append(_get_service_info(service))
    interfaceList = {'interfaces': services}

    return interfaceList


def up(interface, iface_type=None):
    '''
    Enable the specified interface

    :param str interface: interface label
    :return: True if the service was enabled, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.up interface-label
    '''
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError('Invalid interface name: {0}'.format(interface))
    if not _connected(service):
        service = pyconnman.ConnService(_add_path(service))
        try:
            state = service.connect()
            return state is None
        except Exception as exc:
            raise salt.exceptions.CommandExecutionError('Couldn\'t enable service: {0}\n'.format(service))
    return True


def enable(interface):
    '''
    Enable the specified interface

    :param str interface: interface label
    :return: True if the service was enabled, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.enable interface-label
    '''
    return up(interface)


def down(interface, iface_type=None):
    '''
    Disable the specified interface

    :param str interface: interface label
    :return: True if the service was disabled, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.down interface-label
    '''
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError('Invalid interface name: {0}'.format(interface))
    if _connected(service):
        service = pyconnman.ConnService(_add_path(service))
        try:
            state = service.disconnect()
            return state is None
        except Exception as exc:
            raise salt.exceptions.CommandExecutionError('Couldn\'t disable service: {0}\n'.format(service))
    return True


def disable(interface):
    '''
    Disable the specified interface

    :param str interface: interface label
    :return: True if the service was disabled, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.disable interface-label
    '''
    return down(interface)


def set_dhcp_linklocal_all(interface):
    '''
    Configure specified adapter to use DHCP with linklocal fallback

    :param str interface: interface label
    :return: True if the settings ware applied, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.dhcp_linklocal_all interface-label
    '''
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError('Invalid interface name: {0}'.format(interface))
    service = pyconnman.ConnService(_add_path(service))
    ipv4 = service.get_property('IPv4.Configuration')
    ipv4['Method'] = dbus.String('dhcp', variant_level=1)
    ipv4['Address'] = dbus.String('', variant_level=1)
    ipv4['Netmask'] = dbus.String('', variant_level=1)
    ipv4['Gateway'] = dbus.String('', variant_level=1)
    try:
        service.set_property('IPv4.Configuration', ipv4)
        service.set_property('Domains.Configuration', [''])  # reset domains list
    except Exception as exc:
        raise salt.exceptions.CommandExecutionError('Couldn\'t set dhcp linklocal for service: {0}\nError: {1}\n'.format(service, exc))
    return True


def set_static_all(interface, address, netmask, gateway, domains):
    '''
    Configure specified adapter to use ipv4 manual settings

    :param str interface: interface label
    :param str address: ipv4 address
    :param str netmask: ipv4 netmask
    :param str gateway: ipv4 gateway
    :param str domains: list of domains servers separated by spaces
    :return: True if the settings were applied, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.dhcp_linklocal_all interface-label address netmask gateway domains
    '''
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError('Invalid interface name: {0}'.format(interface))
    validate, msg = _validate_ipv4([address, netmask, gateway])
    if not validate:
        raise salt.exceptions.CommandExecutionError(msg)
    validate, msg = _space_delimited_list(domains)
    if not validate:
        raise salt.exceptions.CommandExecutionError(msg)
    service = pyconnman.ConnService(_add_path(service))
    ipv4 = service.get_property('IPv4.Configuration')
    ipv4['Method'] = dbus.String('manual', variant_level=1)
    ipv4['Address'] = dbus.String('{0}'.format(address), variant_level=1)
    ipv4['Netmask'] = dbus.String('{0}'.format(netmask), variant_level=1)
    ipv4['Gateway'] = dbus.String('{0}'.format(gateway), variant_level=1)
    try:
        service.set_property('IPv4.Configuration', ipv4)
        if not isinstance(domains, list):
            dns = domains.split(' ')
            domains = dns
        service.set_property('Domains.Configuration', [dbus.String('{0}'.format(d)) for d in domains])
    except Exception as exc:
        raise salt.exceptions.CommandExecutionError('Couldn\'t set manual settings for service: {0}\nError: {1}\n'.format(service, exc))
    return True


def get_interface(iface):
    '''
    Returns details about given interface.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interface eth0
    '''
    _interfaces = get_interfaces_details()
    for _interface in _interfaces['interfaces']:
        if _interface['connectionid'] == iface:
            return _dict_to_string(_interface)
    return None


def build_interface(iface, iface_type, enable, **settings):
    '''
    Build an interface script for a network interface.

    CLI Example:
    .. code-block:: bash
        salt '*' ip.build_interface eth0 eth <settings>
    '''
    if iface_type != 'eth':
        raise salt.exceptions.CommandExecutionError('Interface type not supported: {0}:'.format(iface_type))

    if 'proto' not in settings or settings['proto'] == 'dhcp':  # default protocol type used is dhcp
        set_dhcp_linklocal_all(iface)
    elif settings['proto'] != 'static':
        raise salt.exceptions.CommandExecutionError('Protocol type: {0} is not supported'.format(settings['proto']))
    else:
        address = settings['ipaddr']
        netmask = settings['netmask']
        gateway = settings['gateway']
        dns = []
        for key, val in six.iteritems(settings):
            if 'dns' in key or 'domain' in key:
                dns += val
    if enable:
        up(iface)

    return get_interface(iface)


def build_network_settings(**settings):
    '''
    Build the global network script.

    CLI Example:
    .. code-block:: bash
        salt '*' ip.build_network_settings <settings>
    '''
    changes = []
    if 'networking' in settings:
        if settings['networking'] in _CONFIG_TRUE:
            __salt__['service.enable']('connman')
        else:
            __salt__['service.disable']('connman')

    if 'hostname' in settings:
        new_hostname = settings['hostname'].split('.', 1)[0]
        settings['hostname'] = new_hostname
        old_hostname = __salt__['network.get_hostname']
        if new_hostname != old_hostname:
            __salt__['network.mod_hostname'](new_hostname)
            changes.append('hostname={0}'.format(new_hostname))

    return changes


def get_network_settings():
    '''
    Return the contents of the global network script.

    CLI Example:
    .. code-block:: bash
        salt '*' ip.get_network_settings
    '''
    settings = []
    networking = 'no' if _get_state() == 'offline' else "yes"
    settings.append('networking={0}'.format(networking))
    hostname = __salt__['network.get_hostname']
    settings.append('hostname={0}'.format(hostname))
    return settings


def apply_network_settings(**settings):
    '''
    Apply global network configuration.

    CLI Example:
    .. code-block:: bash
        salt '*' ip.apply_network_settings
    '''
    if 'require_reboot' not in settings:
        settings['require_reboot'] = False

    if 'apply_hostname' not in settings:
        settings['apply_hostname'] = False

    hostname_res = True
    if settings['apply_hostname'] in _CONFIG_TRUE:
        if 'hostname' in settings:
            hostname_res = __salt__['network.mod_hostname'](settings['hostname'])
        else:
            log.warning(
                'The network state sls is trying to apply hostname '
                'changes but no hostname is defined.'
            )
            hostname_res = False

    res = True
    if settings['require_reboot'] in _CONFIG_TRUE:
        log.warning(
            'The network state sls is requiring a reboot of the system to '
            'properly apply network configuration.'
        )
        res = True
    else:
        stop = __salt__['service.stop']('connman')
        time.sleep(2)
        res = stop and __salt__['service.start']('connman')

    return hostname_res and res
