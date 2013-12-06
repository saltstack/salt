## -*- coding: utf-8 -*-
'''
The networking module for Debian based distros
'''

# Import python libs
import logging
import os.path
import os
import re
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
        os.path.join(salt.utils.templates.TEMPLATE_DIRNAME, 'debian_ip')
    )
)

# Define the module's virtual name
__virtualname__ = 'ip'

def __virtual__():
    '''
    Confine this module to Debian based distros
    '''
    if __grains__['os_family'] == 'Debian':
        return __virtualname__
    return False

_ETHTOOL_CONFIG_OPTS = {
    'speed': 'link-speed',
    'duplex': 'link-duplex',
    'autoneg': 'ethernet-autoneg',
    'ethernet-port': 'ethernet-port',
    'wol': 'ethernet-wol',
    'driver-message-level': 'driver-message-level',
    'ethernet-pause-rx': 'ethernet-pause-rx',
    'ethernet-pause-tx': 'ethernet-pause-tx',
    'ethernet-pause-autoneg': 'ethernet-pause-autoneg',
    'rx': 'offload-rx',
    'tx': 'offload-tx',
    'sg': 'offload-sg',
    'tso': 'offload-tso',
    'ufo': 'offload-ufo',
    'gso': 'offload-gso',
    'gro': 'offload-gro',
    'lro': 'offload-lro',
    'hardware-irq-coalesce-adaptive-rx': 'hardware-irq-coalesce-adaptive-rx',
    'hardware-irq-coalesce-adaptive-tx': 'hardware-irq-coalesce-adaptive-tx',
    'hardware-irq-coalesce-rx-usecs': 'hardware-irq-coalesce-rx-usecs',
    'hardware-irq-coalesce-rx-frames': 'hardware-irq-coalesce-rx-frames',
    'hardware-dma-ring-rx': 'hardware-dma-ring-rx',
    'hardware-dma-ring-rx-mini': 'hardware-dma-ring-rx-mini',
    'hardware-dma-ring-rx-jumbo': 'hardware-dma-ring-rx-jumbo',
    'hardware-dma-ring-tx': 'hardware-dma-ring-tx',
    'mtu': 'mtu'
}

_REV_ETHTOOL_CONFIG_OPTS = {
    'link-speed': 'speed',
    'link-duplex': 'duplex',
    'ethernet-autoneg': 'autoneg',
    'ethernet-port': 'ethernet-port',
    'ethernet-wol': 'wol',
    'driver-message-level': 'driver-message-level',
    'ethernet-pause-rx': 'ethernet-pause-rx',
    'ethernet-pause-tx': 'ethernet-pause-tx',
    'ethernet-pause-autoneg': 'ethernet-pause-autoneg',
    'offload-rx': 'rx',
    'offload-tx': 'tx',
    'offload-sg': 'sg',
    'offload-tso': 'tso',
    'offload-ufo': 'ufo',
    'offload-gso': 'gso',
    'offload-lro': 'lro',
    'offload-gro': 'gro',
    'hardware-irq-coalesce-adaptive-rx': 'hardware-irq-coalesce-adaptive-rx',
    'hardware-irq-coalesce-adaptive-tx': 'hardware-irq-coalesce-adaptive-tx',
    'hardware-irq-coalesce-rx-usecs': 'hardware-irq-coalesce-rx-usecs',
    'hardware-irq-coalesce-rx-frames': 'hardware-irq-coalesce-rx-frames',
    'hardware-dma-ring-rx': 'hardware-dma-ring-rx',
    'hardware-dma-ring-rx-mini': 'hardware-dma-ring-rx-mini',
    'hardware-dma-ring-rx-jumbo': 'hardware-dma-ring-rx-jumbo',
    'hardware-dma-ring-tx': 'hardware-dma-ring-tx',
    'mtu': 'mtu'
}

_DEB_CONFIG_OPTS = [
    'domain', 'peerdns', 'defroute',
    'mtu', 'static-routes', 'gateway'
]
_DEB_CONFIG_BONDING_OPTS = [
    'mode', 'miimon', 'arp_interval', 'slaves',
    'arp_ip_target', 'downdelay', 'updelay',
    'use_carrier', 'lacp_rate', 'hashing-algorithm',
    'max_bonds', 'tx_queues', 'num_grat_arp',
    'num_unsol_na', 'primary', 'primary_reselect',
    'ad_select', 'xmit_hash_policy', 'arp_validate',
    'fail_over_mac', 'all_slaves_active', 'resend_igmp'
]
_DEB_ROUTES_FILE = '/etc/network/routes'
_DEB_NETWORK_FILE = '/etc/network/interfaces'
_DEB_NETWORK_DIR = '/etc/network/interfaces.d'
_DEB_NETWORK_UP_DIR = '/etc/network/if-up.d'
_DEB_NETWORK_DOWN_DIR = '/etc/network/if-down.d'
_DEB_NETWORK_CONF_FILES = '/etc/modprobe.d'
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


def _raise_error_iface(iface, option, expected):
    '''
    Log and raise an error with a logical formated message.
    '''
    msg = _error_msg_iface(iface, option, expected)
    log.error(msg)
    raise AttributeError(msg)


def _raise_error_network(option, expected):
    '''
    Log and raise an error with a logical formated message.
    '''
    msg = _error_msg_network(option, expected)
    log.error(msg)
    raise AttributeError(msg)


def _raise_error_routes(iface, option, expected):
    '''
    Log and raise an error with a logical formated message.
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
            return contents.readlines()
    except Exception:
        return ''

def _parse_interfaces():
    '''
    Parse /etc/network/interfaces and return current configured interfaces
    '''
    interface_files = []
    # Add this later.
    #if os.path.exists("/etc/network/interfaces.d/"):
    #    interface_files += os.listdir("/etc/network/interfaces.d/")

    if os.path.isfile('/etc/network/interfaces'):
        interface_files.insert(0, '/etc/network/interfaces')

    adapters = {}
    context = -1

    for interface_file in interface_files:

        interfaces = open(interface_file)

        for line in interfaces:
            # Identify the clauses by analyzing the first word of each line.
            # Go to the next line if the current line is a comment.
            if line.startswith('#') == True:
                pass
            else:
                # Parse the iface clause
                if line.startswith('iface'):
                    sline = line.split()

                    if len(sline) != 4:
                        msg = 'Interface file malformed: {0}.'
                        msg = msg.format(sline)
                        log.error(msg)
                        raise AttributeError(msg)

                    iface_name = sline[1]
                    # Create item in dict, if not already there
                    if not adapters.has_key(iface_name):
                        adapters[iface_name] = {}

                    # Create item in dict, if not already there
                    if not adapters[iface_name].has_key('data'):
                        context = 0
                        adapters[iface_name]['data'] = []
                        adapters[iface_name]['data'].append({})
                    else:
                        context += 1
                        adapters[iface_name]['data'].append({})

                    adapters[iface_name]['data'][context]['inet_type'] = sline[2]
                    adapters[iface_name]['data'][context]['proto'] = sline[3]

                if line.isspace() == True:
                    pass
                else:
                    # Parse the detail clauses.
                    if line[0].isspace() == True:
                        sline = line.split()

                        if sline[0] in ['address', 'netmask', 'gateway', 'broadcast', 'network']:
                            adapters[iface_name]['data'][context][sline[0]] = sline[1]

                        if sline[0] == 'vlan-raw-device':
                            adapters[iface_name]['data'][0]['vlan_raw_device'] = sline[1]

                        if sline[0] in _REV_ETHTOOL_CONFIG_OPTS:
                            ethtool_key = sline[0]
                            if not adapters[iface_name]['data'][context].has_key('ethtool'):
                                adapters[iface_name]['data'][context]['ethtool'] = {}
                            adapters[iface_name]['data'][context]['ethtool'][ethtool_key] = sline[1]

                        if sline[0].startswith('bond') == True:
                            opt = sline[0].split('_', 1)[1]
                            sline.pop(0)
                            value = ' '.join(sline)

                            if not adapters[iface_name].has_key('bonding'):
                                adapters[iface_name]['bonding'] = {}
                            adapters[iface_name]['bonding'][opt] = value

                        if sline[0].startswith('bridge') == True:
                            opt = sline[0].split('_', 1)[1]
                            sline.pop(0)
                            value = ' '.join(sline)

                            if not adapters[iface_name]['data'][context].has_key('bridge_options'):
                                adapters[iface_name]['data'][context]['bridge_options'] = {}
                            adapters[iface_name]['data'][context]['bridge_options'][opt] = value

                        if sline[0] in ['up', 'down', 'pre-up', 'post-up', 'pre-down', 'post-down']:
                            ud = sline.pop(0)
                            cmd = ' '.join(sline)
                            cmd_key = '%s_cmds' % (re.sub('-', '_', ud))
                            if not adapters[iface_name]['data'][context].has_key(cmd_key):
                                adapters[iface_name]['data'][context][cmd_key] = []
                            adapters[iface_name]['data'][context][cmd_key].append(cmd)

                if line.startswith('auto'):
                    sline = line.split()
                    for word in sline:
                        if word == 'auto':
                            pass
                        else:
                            if not adapters.has_key(word):
                                adapters[word] = {}
                            adapters[word]['enabled'] = True

                if line.startswith('allow-hotplug'):
                    sline = line.split()
                    for word in sline:
                        if word == 'allow-hotplug':
                            pass
                        else:
                            if not adapters.has_key(word):
                                adapters[word] = {}
                            adapters[word]['hotplug'] = True

    # Return a sorted list of the keys for ethtool options to ensure a consistent order
    for iface_name in adapters:
        if adapters[iface_name]['data'][0].has_key('ethtool'):
            ethtool_keys = sorted(adapters[iface_name]['data'][0]['ethtool'].keys())
            adapters[iface_name]['data'][0]['ethtool_keys'] = ethtool_keys

    return adapters

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

    if 'mtu' in opts:
        try:
            int(opts['mtu'])
            config.update({'mtu': opts['mtu']})
        except Exception:
            _raise_error_iface(iface, 'mtu', ['integer'])

    if 'speed' in opts:
        valid = ['10', '100', '1000']
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
        valid = ['layer2', 'layer3+4']
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
        valid = ['layer2', 'layer3+4']
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
    adapters = {}
    adapters[iface] = []

    adapters[iface] = {}

    adapters[iface]['type'] = iface_type

    adapters[iface]['data'] = []
    adapters[iface]['data'].append({})

    if enabled:
        adapters[iface]['enabled'] = True

    adapters[iface]['data'][0]['inet_type'] = 'inet'

    if iface_type not in ['bridge']:
        tmp_ethtool = _parse_ethtool_opts(opts, iface)
        if tmp_ethtool:
            ethtool = {}
            for item in tmp_ethtool:
                ethtool[_ETHTOOL_CONFIG_OPTS[item]] = tmp_ethtool[item]

            adapters[iface]['data'][0]['ethtool'] = ethtool
            # return a list of sorted keys to ensure consistent order
            adapters[iface]['data'][0]['ethtool_keys'] = sorted(ethtool.keys())

    if iface_type == 'bond':
        bonding = _parse_settings_bond(opts, iface)
        if bonding:
            adapters[iface]['bonding'] = bonding
            adapters[iface]['bonding']['slaves'] = opts['slaves']

    if iface_type == 'slave':
        adapters[iface]['master'] = opts['master']

    if iface_type == 'vlan':
        adapters[iface]['data'][0]['vlan_raw_device'] = re.sub('\.\d*', '', iface) 

    if 'proto' in opts:
        valid = ['bootp', 'dhcp', 'none', 'static', 'manual', 'loopback']
        if opts['proto'] in valid:
            # no 'none' proto for Debian, set to static
            if opts['proto'] == 'none':
                adapters[iface]['data'][0]['proto'] = 'static'
            else:
                adapters[iface]['data'][0]['proto'] = opts['proto']
        else:
            _raise_error_iface(iface, opts['proto'], valid)

    if 'ipaddr' in opts:
        adapters[iface]['data'][0]['address'] = opts['ipaddr']

    for opt in ['netmask', 'network', 'gateway', 'addr']:
        if opt in opts:
            adapters[iface]['data'][0][opt] = opts[opt]

    for opt in ['bridge_ports', 'bridge_stp', 'bridge_waitport', 'bridge_fd']:
        if opt in opts:
            key = opt.split('_')[1]
            if not adapters[iface]['data'][0].has_key('bridge_options'):
                adapters[iface]['data'][0]['bridge_options'] = {}
            adapters[iface]['data'][0]['bridge_options'][key] = opts[opt]

    for opt in ['up_cmds', 'pre_up_cmds', 'post_up_cmds']:
        if opt in opts:
            adapters[iface]['data'][0][opt] = opts[opt]

    for opt in ['down_cmds', 'pre_down_cmds', 'post_down_cmds']:
        if opt in opts:
            adapters[iface]['data'][0][opt] = opts[opt]

    if 'enable_ipv6' in opts and opts['enable_ipv6']:
        adapters[iface]['data'].append({})
        adapters[iface]['data'][1]['inet_type'] = 'inet6'
        adapters[iface]['data'][1]['netmask'] = '64'

        if 'iface_type' in opts and opts['iface_type'] == 'vlan':
            adapters[iface]['data'][1]['vlan_raw_device'] = re.sub('\.\d*', '', iface) 

        if 'ipv6proto' in opts:
            adapters[iface]['data'][1]['proto'] = opts['ipv6proto']

        if 'ipv6addr' in opts:
            adapters[iface]['data'][1]['address'] = opts['ipv6addr']

        if 'ipv6netmask' in opts:
            adapters[iface]['data'][1]['netmask'] = opts['ipv6netmask']

        if 'ipv6gateway' in opts:
            adapters[iface]['data'][1]['gateway'] = opts['ipv6gateway']

    return adapters

def _parse_routes(iface, opts):
    '''
    Filters given options and outputs valid settings for
    the route settings file.
    '''
    # Normalize keys
    opts = dict((k.lower(), v) for (k, v) in opts.iteritems())
    result = {}
    if not 'routes' in opts:
        _raise_error_routes(iface, 'routes', 'List of routes')

    for opt in opts:
        result[opt] = opts[opt]

    return result

def _write_file(iface, data, folder, pattern):
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

    return filename

def _write_file_routes(iface, data, folder, pattern):
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

    __salt__['file.set_mode'](filename, '0755')
    return filename


def _read_temp(data):
    '''
    Return what would be written to disk
    '''
    tout = StringIO.StringIO()
    tout.write(data)
    tout.seek(0)
    output = tout.readlines()
    tout.close()

    return output

def _read_temp_ifaces(iface, data):
    '''
    Return what would be written to disk for interfaces
    '''
    try:
        template = JINJA.get_template('debian_eth.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template debian_eth.jinja')
        return ''

    ifcfg = template.render({'name': iface, 'data': data})
    # Return as a array so the difflib works
    return [item + '\n' for item in ifcfg.split('\n')]


def _write_file_ifaces(iface, data, folder):
    '''
    Writes a file to disk
    '''
    try:
        template = JINJA.get_template('debian_eth.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template debian_eth.jinja')
        return ''

    adapters = _parse_interfaces()
    adapters[iface] = data

    ifcfg = ''
    for adapter in adapters:
        if adapters[adapter].has_key('type') and adapters[adapter]['type'] == 'slave':
            # Override values so the interfaces file is correct
            adapters[adapter]['enabled'] = False
            adapters[adapter]['data'][0]['inet_type'] = 'inet'
            adapters[adapter]['data'][0]['proto'] = 'manual'

        tmp = template.render({'name': adapter, 'data': adapters[adapter]})
        ifcfg += tmp
        if adapter == iface:
            saved_ifcfg = tmp

    filename = _DEB_NETWORK_FILE
    if not os.path.exists(os.path.dirname(filename)):
        msg = '{0} cannot be written.'
        msg = msg.format(os.path.dirname(filename))
        log.error(msg)
        raise AttributeError(msg)
    fout = salt.utils.fopen(filename, 'w')
    fout.write(ifcfg)
    fout.close()

    # Return as a array so the difflib works
    return saved_ifcfg.split('\n')

def build_bond(iface, **settings):
    '''
    Create a bond script in /etc/modprobe.d with the passed settings
    and load the bonding kernel module.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_bond bond0 mode=balance-alb
    '''
    deb_major = __grains__['osrelease'][:1]

    opts = _parse_settings_bond(settings, iface)
    try:
        template = JINJA.get_template('conf.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template conf.jinja')
        return ''
    data = template.render({'name': iface, 'bonding': opts})

    if settings['test']:
        return _read_temp(data)

    _write_file(iface, data, _DEB_NETWORK_CONF_FILES, '{0}.conf'.format(iface))
    path = os.path.join(_DEB_NETWORK_CONF_FILES, '{0}.conf'.format(iface))
    if deb_major == '5':
        __salt__['cmd.run'](
            'sed -i -e "/^alias\\s{0}.*/d" /etc/modprobe.conf'.format(iface)
        )
        __salt__['cmd.run'](
            'sed -i -e "/^options\\s{0}.*/d" /etc/modprobe.conf'.format(iface)
        )
        __salt__['cmd.run']('cat {0} >> /etc/modprobe.conf'.format(path))

    # Load kernel module
    __salt__['kmod.load']('bonding')

    # install ifenslave-2.6
    __salt__['pkg.install']('ifenslave-2.6')

    return _read_file(path)

def build_interface(iface, iface_type, enabled, **settings):
    '''
    Build an interface script for a network interface.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_interface eth0 eth <settings>
    '''

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

    if iface_type is 'bond':
        if 'slaves' not in settings:
            msg = 'slaves is a required setting for bond interfaces'
            log.error(msg)
            raise AttributeError(msg)

    if iface_type == 'bridge':
        if 'bridge_ports' not in settings:
            msg = 'bridge_ports is a required setting for bridge interfaces'
            log.error(msg)
            raise AttributeError(msg)
        __salt__['pkg.install']('bridge-utils')

    if iface_type in ['eth', 'bond', 'bridge', 'slave', 'vlan']:
        opts = _parse_settings_eth(settings, iface_type, enabled, iface)

    if settings['test']:
        return _read_temp_ifaces(iface, opts[iface])

    ifcfg = _write_file_ifaces(iface, opts[iface], _DEB_NETWORK_DIR)

    # ensure lines in list end with newline, so difflib works
    return [item + '\n' for item in ifcfg]

def build_routes(iface, **settings):
    '''
    Add route scripts for a network interface using up commands. 

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_routes eth0 <settings>
    '''

    iface = iface.lower()
    opts = _parse_routes(iface, settings)
    try:
        template = JINJA.get_template('route_eth.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template route_eth.jinja')
        return ''

    add_routecfg = template.render(route_type='add', routes=opts['routes'])

    del_routecfg = template.render(route_type='del', routes=opts['routes'])

    if 'test' in settings and settings['test']:
        return _read_temp(add_routecfg + del_routecfg)

    filename = _write_file_routes(iface, add_routecfg, _DEB_NETWORK_UP_DIR, 'route-{0}')
    results = _read_file(filename)

    filename = _write_file_routes(iface, del_routecfg, _DEB_NETWORK_DOWN_DIR, 'route-{0}')
    results += _read_file(filename)

    return results

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
    path = os.path.join(_DEB_NETWORK_CONF_FILES, '{0}.conf'.format(iface))
    return _read_file(path)


def get_interface(iface):
    '''
    Return the contents of an interface script

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interface eth0
    '''

    adapters = _parse_interfaces()
    if iface in adapters:
        try:
            template = JINJA.get_template('debian_eth.jinja')
        except jinja2.exceptions.TemplateNotFound:
            log.error('Could not load template debian_eth.jinja')
            return ''

        ifcfg = template.render({'name': iface, 'data': adapters[iface]})

        # ensure lines in list end with newline, so difflib works
        return [item + '\n' for item in ifcfg.split('\n')]
    else:
        return []

def up(iface, iface_type):  # pylint: disable=C0104
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

def get_network_settings():
    msg = 'Not implemented yet'
    return msg

def get_routes(iface):
    '''
    Return the routes for the interface

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interface eth0
    '''

    filename = os.path.join(_DEB_NETWORK_UP_DIR, 'route-{0}'.format(iface))
    results = _read_file(filename)

    filename = os.path.join(_DEB_NETWORK_DOWN_DIR, 'route-{0}'.format(iface))
    results += _read_file(filename)

    return results

def apply_network_settings(**settings):
    '''
    Apply global network configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.apply_network_settings
    '''
    if not 'require_reboot' in settings:
        settings['require_reboot'] = False

    if settings['require_reboot'] in _CONFIG_TRUE:
        log.warning(
            'The network state sls is requiring a reboot of the system to '
            'properly apply network configuration.'
        )
        return True
    else:
        return __salt__['service.restart']('networking')

def build_network_settings(**settings):
    msg = 'Not implemented yet'
    return msg

