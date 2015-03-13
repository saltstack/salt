# -*- coding: utf-8 -*-
'''
The networking module for RHEL/Fedora based distros
'''

# Import python libs
import logging
import os.path
import os
import StringIO

# Import third party libs
import jinja2
import jinja2.exceptions

# Import salt libs
import salt.utils
import salt.utils.templates
import salt.utils.validate.net

# Set up logging
log = logging.getLogger(__name__)

# Set up template environment
JINJA = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(salt.utils.templates.TEMPLATE_DIRNAME, 'rh_ip')
    )
)

# Define the module's virtual name
__virtualname__ = 'ip'


def __virtual__():
    '''
    Confine this module to RHEL/Fedora based distros
    '''
    if __grains__['os_family'] == 'RedHat':
        return __virtualname__
    return False


# Setup networking attributes
_ETHTOOL_CONFIG_OPTS = [
    'autoneg', 'speed', 'duplex',
    'rx', 'tx', 'sg', 'tso', 'ufo',
    'gso', 'gro', 'lro'
]
_RH_CONFIG_OPTS = [
    'domain', 'peerdns', 'defroute',
    'mtu', 'static-routes', 'gateway'
]
_RH_CONFIG_BONDING_OPTS = [
    'mode', 'miimon', 'arp_interval',
    'arp_ip_target', 'downdelay', 'updelay',
    'use_carrier', 'lacp_rate', 'hashing-algorithm',
    'max_bonds', 'tx_queues', 'num_grat_arp',
    'num_unsol_na', 'primary', 'primary_reselect',
    'ad_select', 'xmit_hash_policy', 'arp_validate',
    'fail_over_mac', 'all_slaves_active', 'resend_igmp'
]
_RH_NETWORK_SCRIPT_DIR = '/etc/sysconfig/network-scripts'
_RH_NETWORK_FILE = '/etc/sysconfig/network'
_RH_NETWORK_CONF_FILES = '/etc/modprobe.d'
_CONFIG_TRUE = ['yes', 'on', 'true', '1', True]
_CONFIG_FALSE = ['no', 'off', 'false', '0', False]
_IFACE_TYPES = [
    'eth', 'bond', 'alias', 'clone',
    'ipsec', 'dialup', 'bridge', 'slave', 'vlan',
]


def _error_msg_iface(iface, option, expected):
    '''
    Build an appropriate error message from a given option and
    a list of expected values.
    '''
    msg = 'Invalid option -- Interface: {0}, Option: {1}, Expected: [{2}]'
    return msg.format(iface, option, '|'.join(expected))


def _error_msg_routes(iface, option, expected):
    '''
    Build an appropriate error message from a given option and
    a list of expected values.
    '''
    msg = 'Invalid option -- Route interface: {0}, Option: {1}, Expected: [{2}]'
    return msg.format(iface, option, expected)


def _log_default_iface(iface, opt, value):
    msg = 'Using default option -- Interface: {0} Option: {1} Value: {2}'
    log.info(msg.format(iface, opt, value))


def _error_msg_network(option, expected):
    '''
    Build an appropriate error message from a given option and
    a list of expected values.
    '''
    msg = 'Invalid network setting -- Setting: {0}, Expected: [{1}]'
    return msg.format(option, '|'.join(expected))


def _log_default_network(opt, value):
    msg = 'Using existing setting -- Setting: {0} Value: {1}'
    log.info(msg.format(opt, value))


def _parse_rh_config(path):
    rh_config = _read_file(path)
    cv_rh_config = {}
    if rh_config:
        for line in rh_config:
            line = line.strip()
            if len(line) == 0 or line.startswith('!') or line.startswith('#'):
                continue
            pair = [p.rstrip() for p in line.split('=', 1)]
            if len(pair) != 2:
                continue
            name, value = pair
            cv_rh_config[name.upper()] = value

    return cv_rh_config


def _parse_ethtool_opts(opts, iface):
    '''
    Filters given options and outputs valid settings for ETHTOOLS_OPTS
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    '''
    config = {}

    if 'autoneg' in opts:
        if opts['autoneg'] in _CONFIG_TRUE:
            config.update({'autoneg': 'on'})
        elif opts['autoneg'] in _CONFIG_FALSE:
            config.update({'autoneg': 'off'})
        else:
            _raise_error_iface(iface, 'autoneg', _CONFIG_TRUE + _CONFIG_FALSE)

    if 'duplex' in opts:
        valid = ['full', 'half']
        if opts['duplex'] in valid:
            config.update({'duplex': opts['duplex']})
        else:
            _raise_error_iface(iface, 'duplex', valid)

    if 'speed' in opts:
        valid = ['10', '100', '1000', '10000']
        if str(opts['speed']) in valid:
            config.update({'speed': opts['speed']})
        else:
            _raise_error_iface(iface, opts['speed'], valid)

    valid = _CONFIG_TRUE + _CONFIG_FALSE
    for option in ('rx', 'tx', 'sg', 'tso', 'ufo', 'gso', 'gro', 'lro'):
        if option in opts:
            if opts[option] in _CONFIG_TRUE:
                config.update({option: 'on'})
            elif opts[option] in _CONFIG_FALSE:
                config.update({option: 'off'})
            else:
                _raise_error_iface(iface, option, valid)

    return config


def _parse_settings_bond(opts, iface):
    '''
    Filters given options and outputs valid settings for requested
    operation. If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    '''

    bond_def = {
        # 803.ad aggregation selection logic
        # 0 for stable (default)
        # 1 for bandwidth
        # 2 for count
        'ad_select': '0',
        # Max number of transmit queues (default = 16)
        'tx_queues': '16',
        # Link monitoring in milliseconds. Most NICs support this
        'miimon': '100',
        # ARP interval in milliseconds
        'arp_interval': '250',
        # Delay before considering link down in milliseconds (miimon * 2)
        'downdelay': '200',
        # lacp_rate 0: Slow - every 30 seconds
        # lacp_rate 1: Fast - every 1 second
        'lacp_rate': '0',
        # Max bonds for this driver
        'max_bonds': '1',
        # Specifies the time, in milliseconds, to wait before
        # enabling a slave after a link recovery has been
        # detected. Only used with miimon.
        'updelay': '0',
        # Used with miimon.
        # On: driver sends mii
        # Off: ethtool sends mii
        'use_carrier': 'on',
        # Default. Don't change unless you know what you are doing.
        'xmit_hash_policy': 'layer2',
    }

    if opts['mode'] in ['balance-rr', '0']:
        log.info(
            'Device: {0} Bonding Mode: load balancing (round-robin)'.format(
                iface
            )
        )
        return _parse_settings_bond_0(opts, iface, bond_def)
    elif opts['mode'] in ['active-backup', '1']:
        log.info(
            'Device: {0} Bonding Mode: fault-tolerance (active-backup)'.format(
                iface
            )
        )
        return _parse_settings_bond_1(opts, iface, bond_def)
    elif opts['mode'] in ['balance-xor', '2']:
        log.info(
            'Device: {0} Bonding Mode: load balancing (xor)'.format(iface)
        )
        return _parse_settings_bond_2(opts, iface, bond_def)
    elif opts['mode'] in ['broadcast', '3']:
        log.info(
            'Device: {0} Bonding Mode: fault-tolerance (broadcast)'.format(
                iface
            )
        )
        return _parse_settings_bond_3(opts, iface, bond_def)
    elif opts['mode'] in ['802.3ad', '4']:
        log.info(
            'Device: {0} Bonding Mode: IEEE 802.3ad Dynamic link '
            'aggregation'.format(iface)
        )
        return _parse_settings_bond_4(opts, iface, bond_def)
    elif opts['mode'] in ['balance-tlb', '5']:
        log.info(
            'Device: {0} Bonding Mode: transmit load balancing'.format(iface)
        )
        return _parse_settings_bond_5(opts, iface, bond_def)
    elif opts['mode'] in ['balance-alb', '6']:
        log.info(
            'Device: {0} Bonding Mode: adaptive load balancing'.format(iface)
        )
        return _parse_settings_bond_6(opts, iface, bond_def)
    else:
        valid = [
            '0', '1', '2', '3', '4', '5', '6',
            'balance-rr', 'active-backup', 'balance-xor',
            'broadcast', '802.3ad', 'balance-tlb', 'balance-alb'
        ]
        _raise_error_iface(iface, 'mode', valid)


def _parse_settings_bond_0(opts, iface, bond_def):
    '''
    Filters given options and outputs valid settings for bond0.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    '''
    bond = {'mode': '0'}

    # ARP targets in n.n.n.n form
    valid = ['list of ips (up to 16)']
    if 'arp_ip_target' in opts:
        if isinstance(opts['arp_ip_target'], list):
            if 1 <= len(opts['arp_ip_target']) <= 16:
                bond.update({'arp_ip_target': []})
                for ip in opts['arp_ip_target']:  # pylint: disable=C0103
                    bond['arp_ip_target'].append(ip)
            else:
                _raise_error_iface(iface, 'arp_ip_target', valid)
        else:
            _raise_error_iface(iface, 'arp_ip_target', valid)
    else:
        _raise_error_iface(iface, 'arp_ip_target', valid)

    if 'arp_interval' in opts:
        try:
            int(opts['arp_interval'])
            bond.update({'arp_interval': opts['arp_interval']})
        except Exception:
            _raise_error_iface(iface, 'arp_interval', ['integer'])
    else:
        _log_default_iface(iface, 'arp_interval', bond_def['arp_interval'])
        bond.update({'arp_interval': bond_def['arp_interval']})

    return bond


def _parse_settings_bond_1(opts, iface, bond_def):

    '''
    Filters given options and outputs valid settings for bond1.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    '''
    bond = {'mode': '1'}

    for binding in ['miimon', 'downdelay', 'updelay']:
        if binding in opts:
            try:
                int(opts[binding])
                bond.update({binding: opts[binding]})
            except Exception:
                _raise_error_iface(iface, binding, ['integer'])
        else:
            _log_default_iface(iface, binding, bond_def[binding])
            bond.update({binding: bond_def[binding]})

    if 'use_carrier' in opts:
        if opts['use_carrier'] in _CONFIG_TRUE:
            bond.update({'use_carrier': 'on'})
        elif opts['use_carrier'] in _CONFIG_FALSE:
            bond.update({'use_carrier': 'off'})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, 'use_carrier', valid)
    else:
        _log_default_iface(iface, 'use_carrier', bond_def['use_carrier'])
        bond.update({'use_carrier': bond_def['use_carrier']})

    return bond


def _parse_settings_bond_2(opts, iface, bond_def):
    '''
    Filters given options and outputs valid settings for bond2.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    '''

    bond = {'mode': '2'}

    valid = ['list of ips (up to 16)']
    if 'arp_ip_target' in opts:
        if isinstance(opts['arp_ip_target'], list):
            if 1 <= len(opts['arp_ip_target']) <= 16:
                bond.update({'arp_ip_target': []})
                for ip in opts['arp_ip_target']:  # pylint: disable=C0103
                    bond['arp_ip_target'].append(ip)
            else:
                _raise_error_iface(iface, 'arp_ip_target', valid)
        else:
            _raise_error_iface(iface, 'arp_ip_target', valid)
    else:
        _raise_error_iface(iface, 'arp_ip_target', valid)

    if 'arp_interval' in opts:
        try:
            int(opts['arp_interval'])
            bond.update({'arp_interval': opts['arp_interval']})
        except Exception:
            _raise_error_iface(iface, 'arp_interval', ['integer'])
    else:
        _log_default_iface(iface, 'arp_interval', bond_def['arp_interval'])
        bond.update({'arp_interval': bond_def['arp_interval']})

    if 'primary' in opts:
        bond.update({'primary': opts['primary']})

    if 'hashing-algorithm' in opts:
        valid = ['layer2', 'layer2+3', 'layer3+4']
        if opts['hashing-algorithm'] in valid:
            bond.update({'xmit_hash_policy': opts['hashing-algorithm']})
        else:
            _raise_error_iface(iface, 'hashing-algorithm', valid)

    return bond


def _parse_settings_bond_3(opts, iface, bond_def):

    '''
    Filters given options and outputs valid settings for bond3.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    '''
    bond = {'mode': '3'}

    for binding in ['miimon', 'downdelay', 'updelay']:
        if binding in opts:
            try:
                int(opts[binding])
                bond.update({binding: opts[binding]})
            except Exception:
                _raise_error_iface(iface, binding, ['integer'])
        else:
            _log_default_iface(iface, binding, bond_def[binding])
            bond.update({binding: bond_def[binding]})

    if 'use_carrier' in opts:
        if opts['use_carrier'] in _CONFIG_TRUE:
            bond.update({'use_carrier': 'on'})
        elif opts['use_carrier'] in _CONFIG_FALSE:
            bond.update({'use_carrier': 'off'})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, 'use_carrier', valid)
    else:
        _log_default_iface(iface, 'use_carrier', bond_def['use_carrier'])
        bond.update({'use_carrier': bond_def['use_carrier']})

    return bond


def _parse_settings_bond_4(opts, iface, bond_def):
    '''
    Filters given options and outputs valid settings for bond4.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    '''

    bond = {'mode': '4'}

    for binding in ['miimon', 'downdelay', 'updelay', 'lacp_rate', 'ad_select']:
        if binding in opts:
            if binding == 'lacp_rate':
                if opts[binding] == 'fast':
                    opts.update({binding: '1'})
                if opts[binding] == 'slow':
                    opts.update({binding: '0'})
                valid = ['fast', '1', 'slow', '0']
            else:
                valid = ['integer']
            try:
                int(opts[binding])
                bond.update({binding: opts[binding]})
            except Exception:
                _raise_error_iface(iface, binding, valid)
        else:
            _log_default_iface(iface, binding, bond_def[binding])
            bond.update({binding: bond_def[binding]})

    if 'use_carrier' in opts:
        if opts['use_carrier'] in _CONFIG_TRUE:
            bond.update({'use_carrier': 'on'})
        elif opts['use_carrier'] in _CONFIG_FALSE:
            bond.update({'use_carrier': 'off'})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, 'use_carrier', valid)
    else:
        _log_default_iface(iface, 'use_carrier', bond_def['use_carrier'])
        bond.update({'use_carrier': bond_def['use_carrier']})

    if 'hashing-algorithm' in opts:
        valid = ['layer2', 'layer2+3', 'layer3+4']
        if opts['hashing-algorithm'] in valid:
            bond.update({'xmit_hash_policy': opts['hashing-algorithm']})
        else:
            _raise_error_iface(iface, 'hashing-algorithm', valid)

    return bond


def _parse_settings_bond_5(opts, iface, bond_def):

    '''
    Filters given options and outputs valid settings for bond5.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    '''
    bond = {'mode': '5'}

    for binding in ['miimon', 'downdelay', 'updelay']:
        if binding in opts:
            try:
                int(opts[binding])
                bond.update({binding: opts[binding]})
            except Exception:
                _raise_error_iface(iface, binding, ['integer'])
        else:
            _log_default_iface(iface, binding, bond_def[binding])
            bond.update({binding: bond_def[binding]})

    if 'use_carrier' in opts:
        if opts['use_carrier'] in _CONFIG_TRUE:
            bond.update({'use_carrier': 'on'})
        elif opts['use_carrier'] in _CONFIG_FALSE:
            bond.update({'use_carrier': 'off'})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, 'use_carrier', valid)
    else:
        _log_default_iface(iface, 'use_carrier', bond_def['use_carrier'])
        bond.update({'use_carrier': bond_def['use_carrier']})

    return bond


def _parse_settings_bond_6(opts, iface, bond_def):

    '''
    Filters given options and outputs valid settings for bond6.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    '''
    bond = {'mode': '6'}

    for binding in ['miimon', 'downdelay', 'updelay']:
        if binding in opts:
            try:
                int(opts[binding])
                bond.update({binding: opts[binding]})
            except Exception:
                _raise_error_iface(iface, binding, ['integer'])
        else:
            _log_default_iface(iface, binding, bond_def[binding])
            bond.update({binding: bond_def[binding]})

    if 'use_carrier' in opts:
        if opts['use_carrier'] in _CONFIG_TRUE:
            bond.update({'use_carrier': 'on'})
        elif opts['use_carrier'] in _CONFIG_FALSE:
            bond.update({'use_carrier': 'off'})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, 'use_carrier', valid)
    else:
        _log_default_iface(iface, 'use_carrier', bond_def['use_carrier'])
        bond.update({'use_carrier': bond_def['use_carrier']})

    return bond


def _parse_settings_eth(opts, iface_type, enabled, iface):
    '''
    Filters given options and outputs valid settings for a
    network interface.
    '''
    result = {'name': iface}
    if 'proto' in opts:
        valid = ['none', 'bootp', 'dhcp']
        if opts['proto'] in valid:
            result['proto'] = opts['proto']
        else:
            _raise_error_iface(iface, opts['proto'], valid)

    if 'dns' in opts:
        result['dns'] = opts['dns']
        result['peerdns'] = 'yes'

    if 'mtu' in opts:
        try:
            result['mtu'] = int(opts['mtu'])
        except Exception:
            _raise_error_iface(iface, 'mtu', ['integer'])

    if iface_type not in ['bridge']:
        ethtool = _parse_ethtool_opts(opts, iface)
        if ethtool:
            result['ethtool'] = ethtool

    if iface_type == 'slave':
        result['proto'] = 'none'

    if iface_type == 'bond':
        bonding = _parse_settings_bond(opts, iface)
        if bonding:
            result['bonding'] = bonding

    if iface_type not in ['bond', 'vlan', 'bridge']:
        if 'addr' in opts:
            if salt.utils.validate.net.mac(opts['addr']):
                result['addr'] = opts['addr']
            else:
                _raise_error_iface(iface, opts['addr'], ['AA:BB:CC:DD:EE:FF'])
        else:
            # If interface type is slave for bond, not setting hwaddr
            if iface_type != 'slave':
                ifaces = __salt__['network.interfaces']()
                if iface in ifaces and 'hwaddr' in ifaces[iface]:
                    result['addr'] = ifaces[iface]['hwaddr']

    if iface_type == 'bridge':
        result['devtype'] = 'Bridge'
        bypassfirewall = True
        valid = _CONFIG_TRUE + _CONFIG_FALSE
        for opt in ['bypassfirewall']:
            if opt in opts:
                if opts[opt] in _CONFIG_TRUE:
                    bypassfirewall = True
                elif opts[opt] in _CONFIG_FALSE:
                    bypassfirewall = False
                else:
                    _raise_error_iface(iface, opts[opt], valid)
        if bypassfirewall:
            __salt__['sysctl.persist']('net.bridge.bridge-nf-call-ip6tables', '0')
            __salt__['sysctl.persist']('net.bridge.bridge-nf-call-iptables', '0')
            __salt__['sysctl.persist']('net.bridge.bridge-nf-call-arptables', '0')
        else:
            __salt__['sysctl.persist']('net.bridge.bridge-nf-call-ip6tables', '1')
            __salt__['sysctl.persist']('net.bridge.bridge-nf-call-iptables', '1')
            __salt__['sysctl.persist']('net.bridge.bridge-nf-call-arptables', '1')
    else:
        if 'bridge' in opts:
            result['bridge'] = opts['bridge']

    for opt in ['ipaddr', 'master', 'netmask', 'srcaddr', 'delay', 'domain', 'gateway']:
        if opt in opts:
            result[opt] = opts[opt]

    for opt in ['ipv6addr', 'ipv6gateway']:
        if opt in opts:
            result[opt] = opts[opt]

    if 'ipv6_autoconf' in opts:
        result['ipv6_autoconf'] = opts['ipv6_autoconf']

    if 'enable_ipv6' in opts:
        result['enable_ipv6'] = opts['enable_ipv6']

    valid = _CONFIG_TRUE + _CONFIG_FALSE
    for opt in ['onparent', 'peerdns', 'slave', 'vlan', 'defroute', 'stp']:
        if opt in opts:
            if opts[opt] in _CONFIG_TRUE:
                result[opt] = 'yes'
            elif opts[opt] in _CONFIG_FALSE:
                result[opt] = 'no'
            else:
                _raise_error_iface(iface, opts[opt], valid)

    if 'onboot' in opts:
        log.warning(
            'The \'onboot\' option is controlled by the \'enabled\' option. '
            'Interface: {0} Enabled: {1}'.format(iface, enabled)
        )

    if enabled:
        result['onboot'] = 'yes'
    else:
        result['onboot'] = 'no'

    # If the interface is defined then we want to always take
    # control away from non-root users; unless the administrator
    # wants to allow non-root users to control the device.
    if 'userctl' in opts:
        if opts['userctl'] in _CONFIG_TRUE:
            result['userctl'] = 'yes'
        elif opts['userctl'] in _CONFIG_FALSE:
            result['userctl'] = 'no'
        else:
            _raise_error_iface(iface, opts['userctl'], valid)
    else:
        result['userctl'] = 'no'

    return result


def _parse_routes(iface, opts):
    '''
    Filters given options and outputs valid settings for
    the route settings file.
    '''
    # Normalize keys
    opts = dict((k.lower(), v) for (k, v) in opts.iteritems())
    result = {}
    if 'routes' not in opts:
        _raise_error_routes(iface, 'routes', 'List of routes')

    for opt in opts:
        result[opt] = opts[opt]

    return result


def _parse_network_settings(opts, current):
    '''
    Filters given options and outputs valid settings for
    the global network settings file.
    '''
    # Normalize keys
    opts = dict((k.lower(), v) for (k, v) in opts.iteritems())
    current = dict((k.lower(), v) for (k, v) in current.iteritems())
    result = {}

    valid = _CONFIG_TRUE + _CONFIG_FALSE
    if 'enabled' not in opts:
        try:
            opts['networking'] = current['networking']
            _log_default_network('networking', current['networking'])
        except ValueError:
            _raise_error_network('networking', valid)
    else:
        opts['networking'] = opts['enabled']

    if opts['networking'] in valid:
        if opts['networking'] in _CONFIG_TRUE:
            result['networking'] = 'yes'
        elif opts['networking'] in _CONFIG_FALSE:
            result['networking'] = 'no'
    else:
        _raise_error_network('networking', valid)

    if 'hostname' not in opts:
        try:
            opts['hostname'] = current['hostname']
            _log_default_network('hostname', current['hostname'])
        except Exception:
            _raise_error_network('hostname', ['server1.example.com'])

    if opts['hostname']:
        result['hostname'] = opts['hostname']
    else:
        _raise_error_network('hostname', ['server1.example.com'])

    if 'nozeroconf' in opts:
        if opts['nozeroconf'] in valid:
            if opts['nozeroconf'] in _CONFIG_TRUE:
                result['nozeroconf'] = 'true'
            elif opts['nozeroconf'] in _CONFIG_FALSE:
                result['nozeroconf'] = 'false'
        else:
            _raise_error_network('nozeroconf', valid)

    for opt in opts:
        if opt not in ['networking', 'hostname', 'nozeroconf']:
            result[opt] = opts[opt]
    return result


def _raise_error_iface(iface, option, expected):
    '''
    Log and raise an error with a logical formatted message.
    '''
    msg = _error_msg_iface(iface, option, expected)
    log.error(msg)
    raise AttributeError(msg)


def _raise_error_network(option, expected):
    '''
    Log and raise an error with a logical formatted message.
    '''
    msg = _error_msg_network(option, expected)
    log.error(msg)
    raise AttributeError(msg)


def _raise_error_routes(iface, option, expected):
    '''
    Log and raise an error with a logical formatted message.
    '''
    msg = _error_msg_routes(iface, option, expected)
    log.error(msg)
    raise AttributeError(msg)


def _read_file(path):
    '''
    Reads and returns the contents of a file
    '''
    try:
        with salt.utils.fopen(path, 'rb') as contents:
            # without newlines character. http://stackoverflow.com/questions/12330522/reading-a-file-without-newlines
            return contents.read().splitlines()
    except Exception:
        return ''


def _write_file_iface(iface, data, folder, pattern):
    '''
    Writes a file to disk
    '''
    filename = os.path.join(folder, pattern.format(iface))
    if not os.path.exists(folder):
        msg = '{0} cannot be written. {1} does not exist'
        msg = msg.format(filename, folder)
        log.error(msg)
        raise AttributeError(msg)
    fout = salt.utils.fopen(filename, 'w')
    fout.write(data)
    fout.close()


def _write_file_network(data, filename):
    '''
    Writes a file to disk
    '''
    fout = salt.utils.fopen(filename, 'w')
    fout.write(data)
    fout.close()


def _read_temp(data):
    tout = StringIO.StringIO()
    tout.write(data)
    tout.seek(0)
    output = tout.read().splitlines()  # Discard newlines
    tout.close()
    return output


def build_bond(iface, **settings):
    '''
    Create a bond script in /etc/modprobe.d with the passed settings
    and load the bonding kernel module.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_bond bond0 mode=balance-alb
    '''
    rh_major = __grains__['osrelease'][:1]

    opts = _parse_settings_bond(settings, iface)
    try:
        template = JINJA.get_template('conf.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template conf.jinja')
        return ''
    data = template.render({'name': iface, 'bonding': opts})
    _write_file_iface(iface, data, _RH_NETWORK_CONF_FILES, '{0}.conf'.format(iface))
    path = os.path.join(_RH_NETWORK_CONF_FILES, '{0}.conf'.format(iface))
    if rh_major == '5':
        __salt__['cmd.run'](
            'sed -i -e "/^alias\\s{0}.*/d" /etc/modprobe.conf'.format(iface),
            python_shell=False
        )
        __salt__['cmd.run'](
            'sed -i -e "/^options\\s{0}.*/d" /etc/modprobe.conf'.format(iface),
            python_shell=False
        )
        __salt__['file.append']('/etc/modprobe.conf', path)
    __salt__['kmod.load']('bonding')

    if settings['test']:
        return _read_temp(data)

    return _read_file(path)


def build_interface(iface, iface_type, enabled, **settings):
    '''
    Build an interface script for a network interface.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_interface eth0 eth <settings>
    '''
    if __grains__['os'] == 'Fedora':
        rh_major = '6'
    else:
        rh_major = __grains__['osrelease'][:1]

    iface = iface.lower()
    iface_type = iface_type.lower()

    if iface_type not in _IFACE_TYPES:
        _raise_error_iface(iface, iface_type, _IFACE_TYPES)

    if iface_type == 'slave':
        settings['slave'] = 'yes'
        if 'master' not in settings:
            msg = 'master is a required setting for slave interfaces'
            log.error(msg)
            raise AttributeError(msg)

    if iface_type == 'vlan':
        settings['vlan'] = 'yes'

    if iface_type == 'bridge':
        __salt__['pkg.install']('bridge-utils')

    if iface_type in ['eth', 'bond', 'bridge', 'slave', 'vlan']:
        opts = _parse_settings_eth(settings, iface_type, enabled, iface)
        try:
            template = JINJA.get_template('rh{0}_eth.jinja'.format(rh_major))
        except jinja2.exceptions.TemplateNotFound:
            log.error(
                'Could not load template rh{0}_eth.jinja'.format(
                    rh_major
                )
            )
            return ''
        ifcfg = template.render(opts)

    if 'test' in settings and settings['test']:
        return _read_temp(ifcfg)

    _write_file_iface(iface, ifcfg, _RH_NETWORK_SCRIPT_DIR, 'ifcfg-{0}')
    path = os.path.join(_RH_NETWORK_SCRIPT_DIR, 'ifcfg-{0}'.format(iface))

    return _read_file(path)


def build_routes(iface, **settings):
    '''
    Build a route script for a network interface.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_routes eth0 <settings>
    '''

    iface = iface.lower()
    opts = _parse_routes(iface, settings)
    try:
        template = JINJA.get_template('route_eth.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error(
            'Could not load template route_eth.jinja'
        )
        return ''
    routecfg = template.render(routes=opts['routes'])

    if settings['test']:
        return _read_temp(routecfg)

    _write_file_iface(iface, routecfg, _RH_NETWORK_SCRIPT_DIR, 'route-{0}')
    path = os.path.join(_RH_NETWORK_SCRIPT_DIR, 'route-{0}'.format(iface))

    return _read_file(path)


def down(iface, iface_type):
    '''
    Shutdown a network interface

    CLI Example:

    .. code-block:: bash

        salt '*' ip.down eth0
    '''
    # Slave devices are controlled by the master.
    if iface_type not in ['slave']:
        return __salt__['cmd.run']('ifdown {0}'.format(iface))
    return None


def get_bond(iface):
    '''
    Return the content of a bond script

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_bond bond0
    '''
    path = os.path.join(_RH_NETWORK_CONF_FILES, '{0}.conf'.format(iface))
    return _read_file(path)


def get_interface(iface):
    '''
    Return the contents of an interface script

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interface eth0
    '''
    path = os.path.join(_RH_NETWORK_SCRIPT_DIR, 'ifcfg-{0}'.format(iface))
    return _read_file(path)


def up(iface, iface_type):  # pylint: disable=C0103
    '''
    Start up a network interface

    CLI Example:

    .. code-block:: bash

        salt '*' ip.up eth0
    '''
    # Slave devices are controlled by the master.
    if iface_type not in ['slave']:
        return __salt__['cmd.run']('ifup {0}'.format(iface))
    return None


def get_routes(iface):
    '''
    Return the contents of the interface routes script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_routes eth0
    '''
    path = os.path.join(_RH_NETWORK_SCRIPT_DIR, 'route-{0}'.format(iface))
    return _read_file(path)


def get_network_settings():
    '''
    Return the contents of the global network script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_network_settings
    '''
    return _read_file(_RH_NETWORK_FILE)


def apply_network_settings(**settings):
    '''
    Apply global network configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.apply_network_settings
    '''
    if 'require_reboot' not in settings:
        settings['require_reboot'] = False

    if settings['require_reboot'] in _CONFIG_TRUE:
        log.warning(
            'The network state sls is requiring a reboot of the system to '
            'properly apply network configuration.'
        )
        return True
    else:
        return __salt__['service.restart']('network')


def build_network_settings(**settings):
    '''
    Build the global network script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_network_settings <settings>
    '''
    # Read current configuration and store default values
    current_network_settings = _parse_rh_config(_RH_NETWORK_FILE)

    # Build settings
    opts = _parse_network_settings(settings, current_network_settings)
    try:
        template = JINJA.get_template('network.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template network.jinja')
        return ''
    network = template.render(opts)

    if settings['test']:
        return _read_temp(network)

    # Write settings
    _write_file_network(network, _RH_NETWORK_FILE)

    return _read_file(_RH_NETWORK_FILE)
