'''
The networking module for RHEL/Fedora based distros
'''
# Import python libs
import logging
import re
from os.path import exists, join

# import third party libs
import jinja2

# Set up logging
log = logging.getLogger(__name__)

# Set up template environment
env = jinja2.Environment(loader=jinja2.PackageLoader('salt.modules', 'rh_ip'))


def __virtual__():
    '''
    Confine this module to RHEL/Fedora based distros$
    '''
    dists = ('CentOS', 'Scientific', 'RedHat', 'Fedora')
    if __grains__['os'] in dists:
        return 'ip'
    return False

# Setup networking attributes
_ETHTOOL_CONFIG_OPTS = [
    'autoneg', 'speed', 'duplex',
    'rx', 'tx', 'sg', 'tso', 'ufo',
    'gso', 'gro', 'lro'
]
_RH_CONFIG_OPTS = [
    'domain', 'peerdns', 'defaultroute',
    'mtu', 'static-routes'
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
_MAC_REGEX = re.compile('([0-9A-F]{1,2}:){5}[0-9A-F]{1,2}')
_CONFIG_TRUE = ['yes', 'on', 'true', '1', True]
_CONFIG_FALSE = ['no', 'off', 'false', '0', False]
_IFACE_TYPES = [
    'eth', 'bond', 'alias', 'clone',
    'ipsec', 'dialup', 'slave', 'vlan',
]


def _error_msg_iface(iface, option, expected):
    '''
    Build an appropriate error message from a given option and
    a list of expected values.
    '''
    msg = 'Invalid option -- Interface: {0}, Option: {1}, Expected: [{2}]'
    return msg.format(iface, option, '|'.join(expected))


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
            if len(pair) !=2:
                continue
            name, value = pair
            cv_rh_config[name.upper()] = value

    return cv_rh_config 

def _parse_ethtool_opts(opts, iface):
    '''
    Fiters given options and outputs valid settings for ETHTOOLS_OPTS
    If an option has a value that is not expected, this
    fuction will log what the Interface, Setting and what it was
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
    Fiters given options and outputs valid settings for requested
    operation. If an option has a value that is not expected, this
    fuction will log what the Interface, Setting and what it was
    expecting.
    '''

    bond_def = {
        # 803.ad aggregation selection logic
        # 0 for stable (default)
        # 1 for bandwidth
        # 2 for count
        'ad_select' : '0',
        # Max number of transmit queues (default = 16)
        'tx_queues' : '16',
        # Link monitoring in milliseconds. Most NICs support this
        'miimon': '100',
        # arp interval in milliseconds
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
        # Defualt. Don't change unless you know what you are doing.
        'xmit_hash_policy': 'layer2',
    }

    if opts['mode'] in ['balance-rr', '0']:
        log.info('Device: {0} Bonding Mode: load balancing (round-robin)'.format(iface))
        return _parse_settings_bond_0(opts, iface, bond_def)
    elif opts['mode'] in ['active-backup', '1']:
        log.info('Device: {0} Bonding Mode: fault-tolerance (active-backup)'.format(iface))
        return _parse_settings_bond_1(opts, iface, bond_def)
    elif opts['mode'] in ['balance-xor', '2']:
        log.info('Device: {0} Bonding Mode: load balancing (xor)'.format(iface))
        return _parse_settings_bond_2(opts, iface, bond_def)
    elif opts['mode'] in ['broadcast', '3']:
        log.info('Device: {0} Bonding Mode: fault-tolerance (broadcast)'.format(iface))
        return _parse_settings_bond_3(opts, iface, bond_def)
    elif opts['mode'] in ['802.3ad', '4']:
        log.info('Device: {0} Bonding Mode: IEEE 802.3ad Dynamic link aggregation'.format(iface))
        return _parse_settings_bond_4(opts, iface, bond_def)
    elif opts['mode'] in ['balance-tlb', '5']:
        log.info('Device: {0} Bonding Mode: transmit load balancing'.format(iface))
        return _parse_settings_bond_5(opts, iface, bond_def)
    elif opts['mode'] in ['balance-alb', '6']:
        log.info('Device: {0} Bonding Mode: adaptive load balancing'.format(iface))
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
    Fiters given options and outputs valid settings for bond0.
    If an option has a value that is not expected, this
    fuction will log what the Interface, Setting and what it was
    expecting.
    '''
    bond = {'mode': '0'}

    # arp targets in n.n.n.n form
    valid = ['list of ips (up to 16)']
    if 'arp_ip_target' in opts:
        if isinstance(opts['arp_ip_target'], list):
            target_length = len(opts['arp_ip_target'])
            if 1 <= len(opts['arp_ip_target']) <= 16:
                bond.update({'arp_ip_target': []})
                for ip in opts['arp_ip_target']:
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
    Fiters given options and outputs valid settings for bond1.
    If an option has a value that is not expected, this
    fuction will log what the Interface, Setting and what it was
    expecting.
    '''
    bond = {'mode': '1'}

    for bo in ['miimon', 'downdelay', 'updelay']:
        if bo in opts:
            try:
                int(opts[bo])
                bond.update({bo: opts[bo]})
            except Exception:
                _raise_error_iface(iface, bo, ['integer'])
        else:
            _log_default_iface(iface, bo, bond_def[bo])
            bond.update({bo: bond_def[bo]})

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
    Fiters given options and outputs valid settings for bond2.
    If an option has a value that is not expected, this
    fuction will log what the Interface, Setting and what it was
    expecting.
    '''

    bond = {'mode': '2'}

    valid = ['list of ips (up to 16)']
    if 'arp_ip_target' in opts:
        if isinstance(opts['arp_ip_target'], list):
            if 1 <= len(opts['arp_ip_target']) <= 16:
                bond.update({'arp_ip_target': []})
                for ip in opts['arp_ip_target']:
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
    Fiters given options and outputs valid settings for bond3.
    If an option has a value that is not expected, this
    fuction will log what the Interface, Setting and what it was
    expecting.
    '''
    bond = {'mode': '3'}

    for bo in ['miimon', 'downdelay', 'updelay']:
        if bo in opts:
            try:
                int(opts[bo])
                bond.update({bo: opts[bo]})
            except Exception:
                _raise_error_iface(iface, bo, ['interger'])
        else:
            _log_default_iface(iface, bo, bond_def[bo])
            bond.update({bo: bond_def[bo]})

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
    Fiters given options and outputs valid settings for bond4.
    If an option has a value that is not expected, this
    fuction will log what the Interface, Setting and what it was
    expecting.
    '''

    bond = {'mode': '4'}

    for bo in ['miimon', 'downdelay', 'updelay', 'lacp_rate', 'ad_select']:
        if bo in opts:
            if bo == 'lacp_rate':
                if opts[bo] == 'fast':
                    opts.update({bo: '1'})
                if opts[bo] == 'slow':
                    opts.update({bo: '0'})
                valid = ['fast', '1', 'slow', '0']
            else:
                valid = ['integer']
            try:
                int(opts[bo])
                bond.update({bo: opts[bo]})
            except Exception:
                _raise_error_iface(iface, bo, valid)
        else:
            _log_default_iface(iface, bo, bond_def[bo])
            bond.update({bo: bond_def[bo]})

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
    Fiters given options and outputs valid settings for bond5.
    If an option has a value that is not expected, this
    fuction will log what the Interface, Setting and what it was
    expecting.
    '''
    bond = {'mode': '5'}

    for bo in ['miimon', 'downdelay', 'updelay']:
        if bo in opts:
            try:
                int(opts[bo])
                bond.update({bo: opts[bo]})
            except Exception:
                _raise_error_iface(iface, bo, ['integer'])
        else:
            _log_default_iface(iface, bo, bond_def[bo])
            bond.update({bo: bond_def[bo]})

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
    Fiters given options and outputs valid settings for bond6.
    If an option has a value that is not expected, this
    fuction will log what the Interface, Setting and what it was
    expecting.
    '''
    bond = {'mode': '6'}

    for bo in ['miimon', 'downdelay', 'updelay']:
        if bo in opts:
            try:
                int(opts[bo])
                bond.update({bo: opts[bo]})
            except Exception:
                _raise_error_iface(iface, bo, ['integer'])
        else:
            _log_default_iface(iface, bo, bond_def[bo])
            bond.update({bo: bond_def[bo]})

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
    Fiters given options and outputs valid settings for a
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
        result['peernds'] = 'yes'

    ethtool = _parse_ethtool_opts(opts, iface)
    if ethtool:
        result['ethtool'] = ethtool

    if iface_type == 'slave':
        result['proto'] = 'none'

    if iface_type == 'bond':
        bonding = _parse_settings_bond(opts, iface)
        if bonding:
            result['bonding'] = bonding

    if iface_type not in ['bond', 'vlan']:
        if 'addr' in opts:
            if _MAC_REGEX.match(opts['addr']):
                result['addr'] = opts['addr']
            else:
                _raise_error_iface(iface, opts['addr'], ['AA:BB:CC:DD:EE:FF'])
        else:
            ifaces = __salt__['network.interfaces']()
            if iface in ifaces and 'hwaddr' in ifaces[iface]:
                result['addr'] = ifaces[iface]['hwaddr']

    for opt in ['ipaddr', 'master', 'netmask', 'srcaddr']:
        if opt in opts:
            result[opt] = opts[opt]

    valid = _CONFIG_TRUE + _CONFIG_FALSE
    for opt in ['peerdns', 'slave', 'vlan']:
        if opt in opts:
            if opts[opt] in _CONFIG_TRUE:
                result[opt] = 'yes'
            elif opts[opt] in _CONFIG_FALSE:
                result[opt] = 'no'
            else:
                _raise_error_iface(iface, opts[opt], valid)

    if 'onboot' in opts:
        log.warning('''The 'onboot' option is controlled by the 'enabled' option. Interface: {0} Enabled: {1}'''.format(iface, enabled))

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

def _parse_network_settings(opts, current):
    '''
    Filters given options and outputs valid settings for
    the global network settings file.
    '''
    # Normalize keys
    opts = dict((k.lower(), v) for k,v in opts.iteritems())
    current = dict((k.lower(), v) for k,v in current.iteritems())
    result = {}

    valid = _CONFIG_TRUE + _CONFIG_FALSE
    if not 'networking' in opts:
        try:
            opts['networking'] = current['networking']
            _log_default_network('networking', current['networking'])
        except:
            _raise_error_network('networking', valid)

    if opts['networking'] in valid:
        if opts['networking'] in _CONFIG_TRUE:
            result['networking'] = 'yes'
        elif opts['networking'] in _CONFIG_FALSE:
                result['networking'] = 'no'
    else:
        _raise_error_network('networking', valid)

    if not 'hostname' in opts:
        try:
            opts['hostname'] = current['hostname']
            _log_default_network('hostname', current['hostname'])
        except:
            _raise_error_network('hostname', ['server1.example.com'])

    if opts['hostname']:
        result['hostname'] = opts['hostname']
    else:
        _raise_error_network('hostname', ['server1.example.com'])

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


def _read_file(path):
    '''
    Reads and returns the contents of a file
    '''
    try:
        with open(path, 'rb') as contents:
            return contents.readlines()
    except Exception:
        return ''


def _write_file_iface(iface, data, folder, pattern):
    '''
    Writes a file to disk
    '''
    filename = join(folder, pattern.format(iface))
    if not exists(folder):
        msg = '{0} cannot be written. {1} does not exists'
        msg = msg.format(filename, folder)
        log.error(msg)
        raise AttributeError(msg)
    fout = open(filename, 'w')
    fout.write(data)
    fout.close()

def _write_file_network(data, filename):
    '''
    Writes a file to disk
    '''
    fout = open(filename, 'w')
    fout.write(data)
    fout.close()


def build_bond(iface, settings):
    '''
    Create a bond script in /etc/modprobe.d with the passed settings
    and load the bonding kernel module.

    CLI Example::

        salt '*' ip.build_bond bond0 mode=balance-alb
    '''
    rh_major = __grains__['osrelease'][:1]
    rh_minor = __grains__['osrelease'][2:]

    opts = _parse_settings_bond(settings, iface)
    template = env.get_template('conf.jinja')
    data = template.render({'name': iface, 'bonding': opts})
    _write_file_iface(iface, data, _RH_NETWORK_CONF_FILES, '{0}.conf')
    path = join(_RH_NETWORK_CONF_FILES, '{0}.conf'.format(iface))
    if rh_major == '5':
        __salt__['cmd.run']('sed -i -e "/^alias\s{0}.*/d" /etc/modprobe.conf'.format(iface))
        __salt__['cmd.run']('sed -i -e "/^options\s{0}.*/d" /etc/modprobe.conf'.format(iface))
        __salt__['cmd.run']('cat {0} >> /etc/modprobe.conf'.format(path))
    __salt__['kmod.load']('bonding')

    return _read_file(path)


def build_interface(iface, iface_type, enabled, settings):
    '''
    Build an interface script for a network interface.

    CLI Example::

        salt '*' ip.build_interface eth0 eth <settings>
    '''
    rh_major = __grains__['osrelease'][:1]
    rh_minor = __grains__['osrelease'][2:]

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

    if iface_type in ['eth', 'bond', 'slave', 'vlan']:
        opts = _parse_settings_eth(settings, iface_type, enabled, iface)
        template = env.get_template('rh{0}_eth.jinja'.format(rh_major))
        ifcfg = template.render(opts)

    _write_file_iface(iface, ifcfg, _RH_NETWORK_SCRIPT_DIR, 'ifcfg-{0}')
    path = join(_RH_NETWORK_SCRIPT_DIR, 'ifcfg-{0}'.format(iface))
    return _read_file(path)


def down(iface, iface_type, opts):
    '''
    Shutdown a network interface

    CLI Example::

        salt '*' ip.down eth0
    '''
    # Slave devices are controlled by the master.
    if iface_type not in ['slave']:
        return __salt__['cmd.run']('ifdown {0}'.format(iface))
    return None


def get_bond(iface):
    '''
    Return the content of a bond script

    CLI Example::

        salt '*' ip.get_bond bond0
    '''
    path = join(_RH_NETWORK_CONF_FILES, '{0}.conf'.format(iface))
    return _read_file(path)


def get_interface(iface):
    '''
    Return the contents of an interface script

    CLI Example::

        salt '*' ip.get_interface eth0
    '''
    path = join(_RH_NETWORK_SCRIPT_DIR, 'ifcfg-{0}'.format(iface))
    return _read_file(path)


def up(iface, iface_type, opts):
    '''
    Start up a network interface

    CLI Example::

        salt '*' ip.up eth0
    '''
    # Slave devices are controlled by the master.
    if iface_type not in ['slave']:
        return __salt__['cmd.run']('ifup {0}'.format(iface))
    return None


def get_network_settings():
    '''
    Return the contents of the global network script.

    CLI Example::

        salt '*' ip.get_network_settings
    '''
    return _read_file(_RH_NETWORK_FILE)


def apply_network_settings(opts):
    '''
    Apply global network configuration.

    CLI Example::

        salt '*' ip.apply_network_settings
    '''
    if not 'require_reboot' in opts:
        opts['require_reboot'] = False

    if opts['require_reboot'] in _CONFIG_TRUE:
        log.warning('The network state sls is requiring a reboot of the system to properly apply network configuration.')
        return True
    else:
        return __salt__['service.restart']('network')

def build_network_settings(settings):
    '''
    Build the global network script.

    CLI Example::

        salt '*' ip.build_network_settings <settings>
    '''
    # Read current configuration and store default values
    current_network_settings = _parse_rh_config(_RH_NETWORK_FILE)

    # Build settings
    opts = _parse_network_settings(settings,current_network_settings)
    template = env.get_template('network.jinja')
    network = template.render(opts)

    # Wirte settings
    _write_file_network(network, _RH_NETWORK_FILE)

    return _read_file(_RH_NETWORK_FILE)
