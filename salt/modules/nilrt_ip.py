# -*- coding: utf-8 -*-
'''
The networking module for NI Linux Real-Time distro

'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time
import os
import re

# Import salt libs
import salt.exceptions
import salt.utils.files
import salt.utils.validate.net

# Import 3rd-party libs
# pylint: disable=import-error,redefined-builtin,no-name-in-module
from salt.ext.six.moves import map, range
from salt.ext import six
# pylint: enable=import-error,redefined-builtin,no-name-in-module
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

try:
    import pyiface
    HAS_PYIFACE = True
except ImportError:
    HAS_PYIFACE = False

try:
    import configparser
    HAS_CONFIGPARSER = True
except ImportError:
    HAS_CONFIGPARSER = False

try:
    from requests.structures import CaseInsensitiveDict
    HAS_REQUEST = True
except ImportError:
    HAS_REQUEST = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'ip'

SERVICE_PATH = '/net/connman/service/'
NIRTCFG_PATH = '/usr/local/natinst/bin/nirtcfg'
INI_FILE = '/etc/natinst/share/ni-rt.ini'
_CONFIG_TRUE = ['yes', 'on', 'true', '1', True]
IFF_LOOPBACK = 0x8
IFF_RUNNING = 0x40


def _assume_condition(condition, err):
    '''
    Raise an exception if the condition is false
    '''
    if not condition:
        raise RuntimeError(err)


def __virtual__():
    '''
    Confine this module to NI Linux Real-Time based distros
    '''
    try:
        _assume_condition(HAS_CONFIGPARSER, 'The python package configparser is not installed')
        _assume_condition(HAS_REQUEST, 'The python package request is not installed')
        msg = 'The nilrt_ip module could not be loaded: unsupported OS family'
        _assume_condition(__grains__['os_family'] == 'NILinuxRT', msg)
        _assume_condition(HAS_PYIFACE, 'The python pyiface package is not installed')
        if __grains__['lsb_distrib_id'] != 'nilrt':
            _assume_condition(HAS_PYCONNMAN, 'The python package pyconnman is not installed')
            _assume_condition(HAS_DBUS, 'The python DBus package is not installed')
            _assume_condition(_get_state() != 'offline', 'Connman is not running')
    except RuntimeError as exc:
        return False, str(exc)
    return __virtualname__


def _get_state():
    '''
    Returns the state of connman
    '''
    try:
        return pyconnman.ConnManager().get_property('State')
    except (KeyError, dbus.Exception):
        return 'offline'


def _get_technologies():
    '''
    Returns the technologies of connman
    '''
    tech = ''
    technologies = pyconnman.ConnManager().get_technologies()
    for path, params in technologies:
        tech += '{0}\n\tName = {1}\n\tType = {2}\n\tPowered = {3}\n\tConnected = {4}\n'.format(
            path, params['Name'], params['Type'], params['Powered'] == 1, params['Connected'] == 1)
    return tech


def _get_services():
    '''
    Returns a list with all connman services
    '''
    serv = []
    services = pyconnman.ConnManager().get_services()
    for path, _ in services:
        serv.append(six.text_type(path[len(SERVICE_PATH):]))
    return serv


def _connected(service):
    '''
    Verify if a connman service is connected
    '''
    state = pyconnman.ConnService(os.path.join(SERVICE_PATH, service)).get_property('State')
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
        service_info = pyconnman.ConnService(os.path.join(SERVICE_PATH, _service))
        if service_info.get_property('Ethernet')['Interface'] == iface:
            return _service
    return None


def _get_service_info(service):
    '''
    return details about given connman service
    '''
    service_info = pyconnman.ConnService(os.path.join(SERVICE_PATH, service))
    data = {
        'label': service,
        'wireless': service_info.get_property('Type') == 'wifi',
        'connectionid': six.text_type(service_info.get_property('Ethernet')['Interface']),
        'hwaddr': six.text_type(service_info.get_property('Ethernet')['Address'])
    }

    state = service_info.get_property('State')
    if state == 'ready' or state == 'online':
        data['up'] = True
        data['ipv4'] = {
            'gateway': '0.0.0.0'
        }
        ipv4 = 'IPv4'
        if service_info.get_property('IPv4')['Method'] == 'manual':
            ipv4 += '.Configuration'
        ipv4_info = service_info.get_property(ipv4)
        for info in ['Method', 'Address', 'Netmask', 'Gateway']:
            value = ipv4_info.get(info)
            if value is None:
                log.warning('Unable to get IPv4 %s for service %s\n', info, service)
                continue
            if info == 'Method':
                info = 'requestmode'
                if value == 'dhcp':
                    value = 'dhcp_linklocal'
                elif value == 'manual':
                    value = 'static'
            data['ipv4'][info.lower()] = six.text_type(value)

        ipv6_info = service_info.get_property('IPv6')
        for info in ['Address', 'Prefix', 'Gateway']:
            value = ipv6_info.get(info)
            if value is None:
                log.warning('Unable to get IPv6 %s for service %s\n', info, service)
                continue
            data['ipv6'][info.lower()] = [six.text_type(value)]

        nameservers = []
        for nameserver_prop in service_info.get_property('Nameservers'):
            nameservers.append(six.text_type(nameserver_prop))
        data['ipv4']['dns'] = nameservers
    else:
        data['up'] = False

    if 'ipv4' in data:
        data['ipv4']['supportedrequestmodes'] = [
            'static',
            'dhcp_linklocal'
        ]
    return data


def _get_dns_info():
    '''
    return dns list
    '''
    dns_list = []
    try:
        with salt.utils.files.fopen('/etc/resolv.conf', 'r+') as dns_info:
            lines = dns_info.readlines()
            for line in lines:
                if 'nameserver' in line:
                    dns = line.split()[1].strip()
                    if dns not in dns_list:
                        dns_list.append(dns)
    except IOError:
        log.warning('Could not get domain\n')
    return dns_list


def _remove_quotes(value):
    '''
    :param value:
    :return:
    '''
    # nirtcfg writes values with quotes
    if len(value) > 1 and value[0] == value[-1] == '\"':
        value = value[1:-1]
    return value


def _get_requestmode_info(interface):
    '''
    return requestmode for given interface
    '''
    with salt.utils.files.fopen(INI_FILE, 'r') as config_file:
        config_parser = configparser.RawConfigParser(dict_type=CaseInsensitiveDict)
        config_parser.read_file(config_file)
        link_local_enabled = '' if not config_parser.has_option(interface, 'linklocalenabled') else \
            int(_remove_quotes(config_parser.get(interface, 'linklocalenabled')))
        dhcp_enabled = '' if not config_parser.has_option(interface, 'dhcpenabled') else \
            int(_remove_quotes(config_parser.get(interface, 'dhcpenabled')))

        if dhcp_enabled == 1:
            return 'dhcp_linklocal' if link_local_enabled == 1 else 'dhcp_only'
        else:
            if link_local_enabled == 1:
                return 'linklocal_only'
            if link_local_enabled == 0:
                return 'static'

    # some versions of nirtcfg don't set the dhcpenabled/linklocalenabled variables
    # when selecting "DHCP or Link Local" from MAX, so return it by default to avoid
    # having the requestmode "None" because none of the conditions above matched.
    return 'dhcp_linklocal'


def _get_interface_info(interface):
    '''
    return details about given interface
    '''
    data = {
        'label': interface.name,
        'connectionid': interface.name,
        'up': False,
        'ipv4': {
            'supportedrequestmodes': ['dhcp_linklocal', 'dhcp_only', 'linklocal_only', 'static'],
            'requestmode': _get_requestmode_info(interface.name)
        },
        'hwaddr': interface.hwaddr[:-1]
    }
    if interface.flags & IFF_RUNNING != 0:
        data['up'] = True
        data['ipv4']['address'] = interface.sockaddrToStr(interface.addr)
        data['ipv4']['netmask'] = interface.sockaddrToStr(interface.netmask)
        data['ipv4']['gateway'] = '0.0.0.0'
        data['ipv4']['dns'] = _get_dns_info()
    elif data['ipv4']['requestmode'] == 'static':
        with salt.utils.files.fopen(INI_FILE, 'r') as config_file:
            config_parser = configparser.RawConfigParser(dict_type=CaseInsensitiveDict)
            config_parser.read_file(config_file)
            data['ipv4']['address'] = _remove_quotes(config_parser.get(interface.name, 'IP_Address'))
            data['ipv4']['netmask'] = _remove_quotes(config_parser.get(interface.name, 'Subnet_Mask'))
            data['ipv4']['gateway'] = _remove_quotes(config_parser.get(interface.name, 'Gateway'))
            data['ipv4']['dns'] = [_remove_quotes(config_parser.get(interface.name, 'DNS_Address'))]

    with salt.utils.files.fopen('/proc/net/route', 'r') as route_file:
        pattern = re.compile(r'^%s\t[0]{8}\t([0-9A-Z]{8})' % interface.name, re.MULTILINE)
        match = pattern.search(route_file.read())
        iface_gateway_hex = None if not match else match.group(1)

    if iface_gateway_hex is not None and len(iface_gateway_hex) == 8:
        data['ipv4']['gateway'] = '.'.join([str(int(iface_gateway_hex[i:i+2], 16)) for i in range(6, -1, -2)])
    return data


def _dict_to_string(dictionary):
    '''
    converts a dictionary object into a list of strings
    '''
    ret = ''
    for key, val in sorted(dictionary.items()):
        if isinstance(val, dict):
            for line in _dict_to_string(val):
                ret += six.text_type(key) + '-' + line + '\n'
        elif isinstance(val, list):
            text = ''
            for item in val:
                text += six.text_type(item) + ' '
            ret += six.text_type(key) + ': ' + text +'\n'
        else:
            ret += six.text_type(key) + ': ' + six.text_type(val) +'\n'
    return ret.splitlines()


def get_interfaces_details():
    '''
    Get details about all the interfaces on the minion

    :return: information about all interfaces omitting loopback
    :rtype: dictionary

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interfaces_details
    '''
    if __grains__['lsb_distrib_id'] == 'nilrt':
        _interfaces = [interface for interface in pyiface.getIfaces() if interface.flags & IFF_LOOPBACK == 0]
        return {'interfaces': list(map(_get_interface_info, _interfaces))}
    return {'interfaces': list(map(_get_service_info, _get_services()))}


def up(interface, iface_type=None):  # pylint: disable=invalid-name,unused-argument
    '''
    Enable the specified interface

    :param str interface: interface label
    :return: True if the service was enabled, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.up interface-label
    '''
    if __grains__['lsb_distrib_id'] == 'nilrt':
        out = __salt__['cmd.run_all']('ip link set {0} up'.format(interface))
        if out['retcode'] != 0:
            msg = 'Couldn\'t enable interface {0}. Error: {1}'.format(interface, out['stderr'])
            raise salt.exceptions.CommandExecutionError(msg)
        return True
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError('Invalid interface name: {0}'.format(interface))
    if not _connected(service):
        service = pyconnman.ConnService(os.path.join(SERVICE_PATH, service))
        try:
            state = service.connect()
            return state is None
        except Exception:
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


def down(interface, iface_type=None):  # pylint: disable=unused-argument
    '''
    Disable the specified interface

    :param str interface: interface label
    :return: True if the service was disabled, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.down interface-label
    '''
    if __grains__['lsb_distrib_id'] == 'nilrt':
        out = __salt__['cmd.run_all']('ip link set {0} down'.format(interface))
        if out['retcode'] != 0:
            msg = 'Couldn\'t disable interface {0}. Error: {1}'.format(interface, out['stderr'])
            raise salt.exceptions.CommandExecutionError(msg)
        return True
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError('Invalid interface name: {0}'.format(interface))
    if _connected(service):
        service = pyconnman.ConnService(os.path.join(SERVICE_PATH, service))
        try:
            state = service.disconnect()
            return state is None
        except Exception:
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

        salt '*' ip.set_dhcp_linklocal_all interface-label
    '''
    if __grains__['lsb_distrib_id'] == 'nilrt':
        _persist_config(interface, 'dhcpenabled', '1')
        _persist_config(interface, 'linklocalenabled', '1')
        disable(interface)
        enable(interface)
        return True
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError('Invalid interface name: {0}'.format(interface))
    service = pyconnman.ConnService(os.path.join(SERVICE_PATH, service))
    ipv4 = service.get_property('IPv4.Configuration')
    ipv4['Method'] = dbus.String('dhcp', variant_level=1)
    ipv4['Address'] = dbus.String('', variant_level=1)
    ipv4['Netmask'] = dbus.String('', variant_level=1)
    ipv4['Gateway'] = dbus.String('', variant_level=1)
    try:
        service.set_property('IPv4.Configuration', ipv4)
        service.set_property('Nameservers.Configuration', [''])  # reset nameservers list
    except Exception as exc:
        exc_msg = 'Couldn\'t set dhcp linklocal for service: {0}\nError: {1}\n'.format(service, exc)
        raise salt.exceptions.CommandExecutionError(exc_msg)
    return True


def set_dhcp_only_all(interface):
    '''
    Configure specified adapter to use DHCP only

    :param str interface: interface label
    :return: True if the settings ware applied, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.dhcp_only_all interface-label
    '''
    if not __grains__['lsb_distrib_id'] == 'nilrt':
        raise salt.exceptions.CommandExecutionError('Not supported in this version')
    _persist_config(interface, 'dhcpenabled', '1')
    _persist_config(interface, 'linklocalenabled', '0')
    disable(interface)
    enable(interface)
    return True


def set_linklocal_only_all(interface):
    '''
    Configure specified adapter to use linklocal only

    :param str interface: interface label
    :return: True if the settings ware applied, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.linklocal_only_all interface-label
    '''
    if not __grains__['lsb_distrib_id'] == 'nilrt':
        raise salt.exceptions.CommandExecutionError('Not supported in this version')
    _persist_config(interface, 'dhcpenabled', '0')
    _persist_config(interface, 'linklocalenabled', '1')
    disable(interface)
    enable(interface)
    return True


def _persist_config(section, token, value):
    '''
    Helper function to persist a configuration in the ini file
    '''
    cmd = NIRTCFG_PATH
    cmd += ' --set section={0},token=\'{1}\',value=\'{2}\''.format(section, token, value)
    if __salt__['cmd.run_all'](cmd)['retcode'] != 0:
        exc_msg = 'Couldn\'t set manual settings for interface: {0}\n'.format(section)
        exc_msg += 'Error: could not set {1} to {2}\n'.format(token, value)
        raise salt.exceptions.CommandExecutionError(exc_msg)


def set_static_all(interface, address, netmask, gateway, nameservers):
    '''
    Configure specified adapter to use ipv4 manual settings

    :param str interface: interface label
    :param str address: ipv4 address
    :param str netmask: ipv4 netmask
    :param str gateway: ipv4 gateway
    :param str nameservers: list of nameservers servers separated by spaces
    :return: True if the settings were applied, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.set_static_all interface-label address netmask gateway nameservers
    '''
    validate, msg = _validate_ipv4([address, netmask, gateway])
    if not validate:
        raise salt.exceptions.CommandExecutionError(msg)
    validate, msg = _space_delimited_list(nameservers)
    if not validate:
        raise salt.exceptions.CommandExecutionError(msg)
    if not isinstance(nameservers, list):
        nameservers = nameservers.split(' ')
    if __grains__['lsb_distrib_id'] == 'nilrt':
        _persist_config(interface, 'dhcpenabled', '0')
        _persist_config(interface, 'linklocalenabled', '0')
        _persist_config(interface, 'IP_Address', address)
        _persist_config(interface, 'Subnet_Mask', netmask)
        _persist_config(interface, 'Gateway', gateway)
        if nameservers:
            _persist_config(interface, 'DNS_Address', nameservers[0])
        disable(interface)
        enable(interface)
        return True
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError('Invalid interface name: {0}'.format(interface))
    service = pyconnman.ConnService(os.path.join(SERVICE_PATH, service))
    ipv4 = service.get_property('IPv4.Configuration')
    ipv4['Method'] = dbus.String('manual', variant_level=1)
    ipv4['Address'] = dbus.String('{0}'.format(address), variant_level=1)
    ipv4['Netmask'] = dbus.String('{0}'.format(netmask), variant_level=1)
    ipv4['Gateway'] = dbus.String('{0}'.format(gateway), variant_level=1)
    try:
        service.set_property('IPv4.Configuration', ipv4)
        service.set_property('Nameservers.Configuration', [dbus.String('{0}'.format(d)) for d in nameservers])
    except Exception as exc:
        exc_msg = 'Couldn\'t set manual settings for service: {0}\nError: {1}\n'.format(service, exc)
        raise salt.exceptions.CommandExecutionError(exc_msg)
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


def build_interface(iface, iface_type, enabled, **settings):
    '''
    Build an interface script for a network interface.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_interface eth0 eth <settings>
    '''
    if __grains__['lsb_distrib_id'] == 'nilrt':
        raise salt.exceptions.CommandExecutionError('Not supported in this version.')
    if iface_type != 'eth':
        raise salt.exceptions.CommandExecutionError('Interface type not supported: {0}:'.format(iface_type))

    if 'proto' not in settings or settings['proto'] == 'dhcp':  # default protocol type used is dhcp
        set_dhcp_linklocal_all(iface)
    elif settings['proto'] != 'static':
        exc_msg = 'Protocol type: {0} is not supported'.format(settings['proto'])
        raise salt.exceptions.CommandExecutionError(exc_msg)
    else:
        address = settings['ipaddr']
        netmask = settings['netmask']
        gateway = settings['gateway']
        dns = []
        for key, val in six.iteritems(settings):
            if 'dns' in key or 'domain' in key:
                dns += val
        set_static_all(iface, address, netmask, gateway, dns)

    if enabled:
        up(iface)

    return get_interface(iface)


def build_network_settings(**settings):
    '''
    Build the global network script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_network_settings <settings>
    '''
    if __grains__['lsb_distrib_id'] == 'nilrt':
        raise salt.exceptions.CommandExecutionError('Not supported in this version.')
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
    if __grains__['lsb_distrib_id'] == 'nilrt':
        raise salt.exceptions.CommandExecutionError('Not supported in this version.')
    settings = []
    networking = 'no' if _get_state() == 'offline' else 'yes'
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
    if __grains__['lsb_distrib_id'] == 'nilrt':
        raise salt.exceptions.CommandExecutionError('Not supported in this version.')
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
