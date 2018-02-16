# -*- coding: utf-8 -*-
'''
The networking module for NI Linux Real-Time distro

'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time
import os

# Import salt libs
import salt.utils.files
import salt.utils.validate.net
import salt.exceptions

# Import 3rd-party libs
from salt.ext import six
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
NIRTCFG_PATH = '/usr/local/natinst/bin/nirtcfg'
_CONFIG_TRUE = ['yes', 'on', 'true', '1', True]


def __virtual__():
    '''
    Confine this module to NI Linux Real-Time based distros
    '''
    if __grains__['os_family'] == 'NILinuxRT':
        if not _is_older_nilrt():
            if not HAS_PYCONNMAN:
                return False, 'The python package pyconnman is not installed'
            if not HAS_DBUS:
                return False, 'The python DBus package is not installed'
            try:
                state = _get_state
                if state == 'offline':
                    return False, 'Connmand is not running'
            except Exception as exc:
                return False, six.text_type(exc)
        return __virtualname__
    return False, 'The nilrt_ip module could not be loaded: unsupported OS family'


def _is_older_nilrt():
    '''
    If this is an older version of NILinuxRT, return True. Otherwise, return False.
    '''
    if os.path.exists('/usr/local/natinst/bin/nisafemodeversion'):
        return True
    return False


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
        serviceList.append(six.text_type(path[len(SERVICE_PATH):]))
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
                data['ipv4'][info.lower()] = six.text_type(value)
            except Exception as exc:
                log.warning('Unable to get IPv4 %s for service %s\n', info, service)

        ipv6Info = service_info.get_property('IPv6')
        for info in ['Address', 'Prefix', 'Gateway']:
            try:
                value = ipv6Info[info]
                data['ipv6'][info.lower()] = [six.text_type(value)]
            except Exception as exc:
                log.warning('Unable to get IPv6 %s for service %s\n', info, service)

        nameservers = []
        for x in service_info.get_property('Nameservers'):
            nameservers.append(six.text_type(x))
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
    dnsList = []
    try:
        with salt.utils.files.fopen('/etc/resolv.conf', 'r+') as dns_info:
            lines = dns_info.readlines()
            for line in lines:
                if 'nameserver' in line:
                    dns = line.split()[1].strip()
                    if dns not in dnsList:
                        dnsList.append(dns)
    except IOError:
        log.warning('Could not get domain\n')
    return dnsList


def _get_requestmode_info(interface):
    '''
    return requestmode for given interface
    '''
    ifacemod = __salt__['cmd.run']('{0} -l'.format(NIRTCFG_PATH)).lower()
    if '[{0}]dhcpenabled=1'.format(interface) in ifacemod:
        if '[{0}]linklocalenabled=1'.format(interface) in ifacemod:
            return 'dhcp_linklocal'
        else:
            return 'dhcp_only'
    elif '[{0}]dhcpenabled=0'.format(interface) in ifacemod:
        if '[{0}]linklocalenabled=1'.format(interface) in ifacemod:
            return 'linklocal_only'
        elif '[{0}]linklocalenabled=0'.format(interface) in ifacemod:
            return 'static'
    else:
        if '[{0}]linklocalenabled=1'.format(interface) in ifacemod:
            return 'linklocal_only'
        elif '[{0}]linklocalenabled=0'.format(interface) in ifacemod:
            return 'static'


def _get_interface_info(interface):
    '''
    return details about given interface
    '''
    iface = __salt__['cmd.run']('ifconfig {0}'.format(interface)).strip().splitlines()
    data = {}
    data['label'] = interface
    data['connectionid'] = interface
    data['up'] = False
    while iface:
        line = iface.pop(0)
        if 'HWaddr' in line:
            data['hwaddr'] = line.split()[4].strip()
        if 'inet addr' in line:
            data['up'] = True
            split_line = line.split()
            address = split_line[1].strip()
            netmask = split_line[3].strip()
            data['ipv4'] = {
                'address': address.split(':')[1].strip(),
                'netmask': netmask.split(':')[1].strip(),
                'gateway': '0.0.0.0'
            }
            data['ipv4']['dns'] = _get_dns_info()
            data['ipv4']['requestmode'] = _get_requestmode_info(interface)
            data['ipv4']['supportedrequestmodes'] = [
                    'dhcp_linklocal',
                    'dhcp_only',
                    'linklocal_only',
                    'static'
                    ]
    iface_gateway_hex = __salt__['cmd.shell']("grep {0} /proc/net/route | awk '{{ if ($2 == '00000000') print $3}}'".format(interface)).strip()
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
            stringList = ''
            for item in val:
                stringList += six.text_type(item) + ' '
            ret += six.text_type(key) + ': ' + stringList +'\n'
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
    if _is_older_nilrt():
        _interfaces = __salt__['cmd.shell']("ifconfig -a | sed 's/[ \t].*//;/^\(lo\|\)$/d'")
        return {'interfaces': list(map(_get_interface_info, _interfaces.splitlines()))}
    return {'interfaces': list(map(_get_service_info, _get_services()))}


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
    if _is_older_nilrt():
        out = __salt__['cmd.run_all']('ip link set {0} up'.format(interface))
        if out['retcode'] != 0:
            raise salt.exceptions.CommandExecutionError('Couldn\'t enable interface {0}. Error: {1}'.format(interface, out['stderr']))
        return True
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
    if _is_older_nilrt():
        out = __salt__['cmd.run_all']('ip link set {0} down'.format(interface))
        if out['retcode'] != 0:
            raise salt.exceptions.CommandExecutionError('Couldn\'t disable interface {0}. Error: {1}'.format(interface, out['stderr']))
        return True
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

        salt '*' ip.set_dhcp_linklocal_all interface-label
    '''
    if _is_older_nilrt():
        if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'dhcpenabled\',value=\'1\''.format(interface))['retcode'] != 0:
            raise salt.exceptions.CommandExecutionError('Couldn\'t set dhcp linklocal  for interface: {0}\nError: could not enable dhcp option\n'.format(interface))
        if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'linklocalenabled\',value=\'1\''.format(interface))['retcode'] != 0:
            raise salt.exceptions.CommandExecutionError('Couldn\'t set dhcp linklocal  for interface: {0}\nError: could not enable linklocal option\n'.format(interface))
        disable(interface)
        enable(interface)
        return True
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
        service.set_property('Nameservers.Configuration', [''])  # reset nameservers list
    except Exception as exc:
        raise salt.exceptions.CommandExecutionError('Couldn\'t set dhcp linklocal for service: {0}\nError: {1}\n'.format(service, exc))
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
    if not _is_older_nilrt():
        raise salt.exceptions.CommandExecutionError('Not supported in this version')
    if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'dhcpenabled\',value=\'1\''.format(interface))['retcode'] != 0:
        raise salt.exceptions.CommandExecutionError('Couldn\'t set dhcp only for interface: {0}\nError: could not enable dhcp option\n'.format(interface))
    if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'linklocalenabled\',value=\'0\''.format(interface))['retcode'] != 0:
        raise salt.exceptions.CommandExecutionError('Couldn\'t set dhcp only for interface: {0}\nError: could not disable linklocal option\n'.format(interface))
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
    if not _is_older_nilrt():
        raise salt.exceptions.CommandExecutionError('Not supported in this version')
    if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'dhcpenabled\',value=\'0\''.format(interface))['retcode'] != 0:
        raise salt.exceptions.CommandExecutionError('Couldn\'t set linklocal only for interface: {0}\nError: could not disable dhcp option\n'.format(interface))
    if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'linklocalenabled\',value=\'1\''.format(interface))['retcode'] != 0:
        raise salt.exceptions.CommandExecutionError('Couldn\'t set set linklocal only for interface: {0}\nError: could not enable linklocal option\n'.format(interface))
    disable(interface)
    enable(interface)
    return True


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
    if _is_older_nilrt():
        if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'dhcpenabled\',value=\'0\''.format(interface))['retcode'] != 0:
            raise salt.exceptions.CommandExecutionError('Couldn\'t set manual settings for interface: {0}\nError: could not disable dhcp option\n'.format(interface))
        if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'linklocalenabled\',value=\'0\''.format(interface))['retcode'] != 0:
            raise salt.exceptions.CommandExecutionError('Couldn\'t set manual settings for interface: {0}\nError: could not disable linklocal option\n'.format(interface))
        if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'IP_Address\',value=\'{1}\''.format(interface, address))['retcode'] != 0:
            raise salt.exceptions.CommandExecutionError('Couldn\'t set manual settings for interface: {0}\nError: could not set static ip\n'.format(interface))
        if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'Subnet_Mask\',value=\'{1}\''.format(interface, netmask))['retcode'] != 0:
            raise salt.exceptions.CommandExecutionError('Couldn\'t set manual settings for interface: {0}\nError: could not set netmask\n'.format(interface))
        if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'Gateway\',value=\'{1}\''.format(interface, gateway))['retcode'] != 0:
            raise salt.exceptions.CommandExecutionError('Couldn\'t set manual settings for interface: {0}\nError: could not set gateway\n'.format(interface))
        if nameservers:
            if __salt__['cmd.run_all'](NIRTCFG_PATH + ' --set section={0},token=\'DNS_Address\',value=\'{1}\''.format(interface, nameservers[0]))['retcode'] != 0:
                raise salt.exceptions.CommandExecutionError('Couldn\'t set manual settings for interface: {0}\nError: could not set dns\n'.format(interface))
        disable(interface)
        enable(interface)
        return True
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError('Invalid interface name: {0}'.format(interface))
    service = pyconnman.ConnService(_add_path(service))
    ipv4 = service.get_property('IPv4.Configuration')
    ipv4['Method'] = dbus.String('manual', variant_level=1)
    ipv4['Address'] = dbus.String('{0}'.format(address), variant_level=1)
    ipv4['Netmask'] = dbus.String('{0}'.format(netmask), variant_level=1)
    ipv4['Gateway'] = dbus.String('{0}'.format(gateway), variant_level=1)
    try:
        service.set_property('IPv4.Configuration', ipv4)
        service.set_property('Nameservers.Configuration', [dbus.String('{0}'.format(d)) for d in nameservers])
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
    if _is_older_nilrt():
        raise salt.exceptions.CommandExecutionError('Not supported in this version.')
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
    if _is_older_nilrt():
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
    if _is_older_nilrt():
        raise salt.exceptions.CommandExecutionError('Not supported in this version.')
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
    if _is_older_nilrt():
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
