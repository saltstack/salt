## -*- coding: utf-8 -*-
'''
The networking module for Debian based distros

References:

* http://www.debian.org/doc/manuals/debian-reference/ch05.en.html
'''

# Import python libs
import functools
import logging
import os.path
import os
import re
import StringIO
import time

# Import third party libs
import jinja2
import jinja2.exceptions

# Import salt libs
import salt.utils
import salt.utils.templates
import salt.utils.validate.net
import salt.utils.odict


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
}

_DEB_CONFIG_PPPOE_OPTS = {
    'user': 'user',
    'password': 'password',
    'provider': 'provider',
    'pppoe_iface': 'pppoe_iface',
    'noipdefault': 'noipdefault',
    'usepeerdns': 'usepeerdns',
    'defaultroute': 'defaultroute',
    'holdoff': 'holdoff',
    'maxfail': 'maxfail',
    'hide-password': 'hide-password',
    'lcp-echo-interval': 'lcp-echo-interval',
    'lcp-echo-failure': 'lcp-echo-failure',
    'connect': 'connect',
    'noauth': 'noauth',
    'persist': 'persist',
    'mtu': 'mtu',
    'noaccomp': 'noaccomp',
}

_DEB_ROUTES_FILE = '/etc/network/routes'
_DEB_NETWORK_FILE = '/etc/network/interfaces'
_DEB_NETWORK_DIR = '/etc/network/interfaces.d'
_DEB_NETWORK_UP_DIR = '/etc/network/if-up.d'
_DEB_NETWORK_DOWN_DIR = '/etc/network/if-down.d'
_DEB_NETWORK_CONF_FILES = '/etc/modprobe.d'
_DEB_NETWORKING_FILE = '/etc/default/networking'
_DEB_HOSTNAME_FILE = '/etc/hostname'
_DEB_RESOLV_FILE = '/etc/resolv.conf'
_DEB_PPP_DIR = '/etc/ppp/peers'

_CONFIG_TRUE = ['yes', 'on', 'true', '1', True]
_CONFIG_FALSE = ['no', 'off', 'false', '0', False]
_IFACE_TYPES = [
    'eth', 'bond', 'alias', 'clone',
    'ipsec', 'dialup', 'bridge', 'slave', 'vlan', 'pppoe',
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
        with salt.utils.flopen(path, 'rb') as contents:
            return contents.readlines()
    except (OSError, IOError):
        return ''


def _parse_resolve():
    '''
    Parse /etc/resolv.conf and return domainname
    '''
    contents = _read_file(_DEB_RESOLV_FILE)
    return contents


def _parse_domainname():
    '''
    Parse /etc/resolv.conf and return domainname
    '''
    contents = _read_file(_DEB_RESOLV_FILE)
    pattern = r'domain\s+(?P<domain_name>\S+)'
    prog = re.compile(pattern)
    for item in contents:
        match = prog.match(item)
        if match:
            return match.group('domain_name')
    return ''


def _parse_hostname():
    '''
    Parse /etc/hostname and return hostname
    '''
    contents = _read_file(_DEB_HOSTNAME_FILE)
    return contents[0].split('\n')[0]


def _parse_current_network_settings():
    '''
    Parse /etc/default/networking and return current configuration
    '''
    opts = salt.utils.odict.OrderedDict()
    opts['networking'] = ''

    if os.path.isfile(_DEB_NETWORKING_FILE):
        with open(_DEB_NETWORKING_FILE) as contents:
            for line in contents:
                if line.startswith('#'):
                    continue
                elif line.startswith('CONFIGURE_INTERFACES'):
                    opts['networking'] = line.split('=', 1)[1].strip()

    hostname = _parse_hostname()
    domainname = _parse_domainname()

    opts['hostname'] = hostname
    opts['domainname'] = domainname
    return opts


# def __validator_func(value):
#    return (valid: True/False, (transformed) value, error message)


def __ipv4_quad(value):
    '''validate an IPv4 address'''
    return (salt.utils.validate.net.ipv4_addr(value), value,
            'dotted IPv4 address')


def __ipv6(value):
    '''validate an IPv6 address'''
    return (salt.utils.validate.net.ipv6_addr(value), value,
            'IPv6 address')


def __mac(value):
    '''validate a mac address'''
    return (salt.utils.validate.net.mac(value), value,
            'MAC address')


def __anything(value):
    return (True, value, None)


def __int(value):
    '''validate an integer'''
    valid, _value = False, value
    try:
        _value = int(value)
        valid = True
    except ValueError:
        pass
    return (valid, _value, 'integer')


def __float(value):
    '''validate a float'''
    valid, _value = False, value
    try:
        _value = float(value)
        valid = True
    except ValueError:
        pass
    return (valid, _value, 'float')


def __ipv4_netmask(value):
    '''validate an IPv4 dotted quad or integer CIDR netmask'''
    valid, errmsg = False, 'dotted quad or integer CIDR (0->32)'
    valid, value, _ = __int(value)
    if not (valid and 0 <= value <= 32):
        valid = salt.utils.validate.net.netmask(value)
    return (valid, value, errmsg)


def __ipv6_netmask(value):
    '''validate an IPv6 integer netmask'''
    valid, errmsg = False, 'IPv6 netmask (0->127)'
    valid, value, _ = __int(value)
    valid = (valid and 0 <= value <= 127)
    return (valid, value, errmsg)


def __within2(value, within=None, errmsg=None, dtype=None):
    '''validate that a value is in ``within`` and optionally a ``dtype``'''
    valid, _value = False, value
    if dtype:
        try:
            _value = dtype(value)  # TODO: this is a bit loose when dtype is a class
            valid = _value in within
        except ValueError:
            pass
    else:
        valid = _value in within
    if errmsg is None:
        if dtype:
            typename = getattr(dtype, '__name__',
                               hasattr(dtype, '__class__')
                               and getattr(dtype.__class__, 'name', dtype))
            errmsg = '{0} within {1!r}'.format(typename, within)
        else:
            errmsg = 'within {0!r}'.format(within)
    return (valid, _value, errmsg)


def __within(within=None, errmsg=None, dtype=None):
    return functools.partial(__within2, within=within,
                             errmsg=errmsg, dtype=dtype)


def __space_delimited_list(value):
    '''validate that a value contains one or more space-delimited values'''
    valid, _value, errmsg = False, value, 'space-delimited string'
    try:
        if hasattr(value, '__iter__'):
            valid = True  # TODO:
        else:
            _value = value.split()
            if _value == []:
                raise ValueError
            valid = True
    except AttributeError:
        pass
    except ValueError:
        pass
    return (valid, _value, errmsg)

SALT_ATTR_TO_DEBIAN_ATTR_MAP = {
    'dns': 'dns-nameservers',
    'hwaddr': 'hwaddress',  # TODO: this limits bootp functionality
    'ipaddr': 'address',
}


DEBIAN_ATTR_TO_SALT_ATTR_MAP = dict(
    (v, k) for (k, v) in SALT_ATTR_TO_DEBIAN_ATTR_MAP.items())

#TODO
DEBIAN_ATTR_TO_SALT_ATTR_MAP['address'] = 'address'
DEBIAN_ATTR_TO_SALT_ATTR_MAP['hwaddress'] = 'hwaddress'

IPV4_VALID_PROTO = ['bootp', 'dhcp', 'static', 'manual', 'loopback']

IPV4_ATTR_MAP = {
    'proto': __within(IPV4_VALID_PROTO, dtype=str),
    # ipv4 static & manual
    'address': __ipv4_quad,
    'netmask': __ipv4_netmask,
    'broadcast': __ipv4_quad,
    'metric':  __int,
    'gateway':  __ipv4_quad,  # supports a colon-delimited list
    'pointtopoint':  __ipv4_quad,
    'hwaddress':  __mac,
    'mtu':  __int,
    'scope': __within(['global', 'link', 'host'], dtype=str),
    # dhcp
    'hostname': __anything,
    'leasehours':  __int,
    'leasetime':  __int,
    'vendor': __anything,
    'client': __anything,
    # bootp
    'bootfile': __anything,
    'server':  __ipv4_quad,
    'hwaddr':  __mac,
    # tunnel
    'mode':  __within(['gre', 'GRE', 'ipip', 'IPIP'], dtype=str),
    'endpoint':  __ipv4_quad,
    'dstaddr':  __ipv4_quad,
    'local':  __ipv4_quad,
    'ttl':  __int,
    # ppp
    'provider': __anything,
    'unit':  __int,
    'options': __anything,
    #
    'dns-nameservers': __space_delimited_list,
    'dns-search': __space_delimited_list,
    #
    'vlan-raw-device': __anything,
    #
    'network': __anything,  # i don't know what this is

    'test': __anything,  # TODO
    'enable_ipv6': __anything,  # TODO
}


IPV6_VALID_PROTO = ['auto', 'loopback', 'static', 'manual',
                    'dhcp', 'v4tunnel', '6to4']

IPV6_ATTR_MAP = {
    'address': __ipv6,
    'netmask': __ipv6_netmask,
    'broadcast': __ipv6,
    'gateway': __ipv6,  # supports a colon-delimited list
    'scope': __within(['global', 'site', 'link', 'host'], dtype=str),
    'proto': __within(IPV6_VALID_PROTO),
    # inet6 auto
    'privext': __within([0, 1, 2], dtype=int),
    'dhcp':  __within([0, 1], dtype=int),
    # inet6 static & manual & dhcp
    'media': __anything,
    'accept_ra':  __within([0, 1], dtype=int),
    'autoconf':  __within([0, 1], dtype=int),
    'preferred-lifetime':  __int,
    'dad-attempts': __int,  # 0 to disable
    'dad-interval': __float,
}


WIRELESS_ATTR_MAP = {
    'wireless-essid': __anything,
    'wireless-mode':  __anything,  # TODO
    'wpa-ap-scan': __within([0, 1, 2], dtype=int),  # TODO
    'wpa-conf': __anything,
    'wpa-driver': __anything,
    'wpa-group': __anything,
    'wpa-key-mgmt': __anything,
    'wpa-pairwise': __anything,
    'wpa-psk': __anything,
    'wpa-proto': __anything,  # partial(__within,
    'wpa-roam': __anything,
    'wpa-ssid': __anything,  # TODO
}

ATTRMAPS = {
    'inet': [IPV4_ATTR_MAP, WIRELESS_ATTR_MAP],
    'inet6': [IPV6_ATTR_MAP, IPV4_ATTR_MAP, WIRELESS_ATTR_MAP]
}


def _validate_interface_option(attr, value, addrfam='inet'):
    '''lookup the validation function for a [addrfam][attr] and
    return the results

    :param attr: attribute name
    :param value: raw setting value
    :param addrfam: address family (inet, inet6,
    '''
    valid, _value, errmsg = False, value, 'Unknown validator'
    attrmaps = ATTRMAPS.get(addrfam, [])
    for attrmap in attrmaps:
        if attr in attrmap:
            validate_func = attrmap[attr]
            (valid, _value, errmsg) = validate_func(value)
            break
    return (valid, _value, errmsg)


def _attrmaps_contain_attr(attr):
    return (
        attr in WIRELESS_ATTR_MAP or
        attr in IPV4_ATTR_MAP or
        attr in IPV6_ATTR_MAP)


def _parse_interfaces(interface_files=None):
    '''
    Parse /etc/network/interfaces and return current configured interfaces
    '''
    if interface_files is None:
        interface_files = []
        # Add this later.
        # if os.path.exists('/etc/network/interfaces.d/'):
        #    interface_files += os.listdir('/etc/network/interfaces.d/')

        if os.path.isfile(_DEB_NETWORK_FILE):
            interface_files.insert(0, _DEB_NETWORK_FILE)

    adapters = salt.utils.odict.OrderedDict()
    method = -1

    for interface_file in interface_files:
        with open(interface_file) as interfaces:
            for line in interfaces:
                # Identify the clauses by the first word of each line.
                # Go to the next line if the current line is a comment
                # or all spaces.
                if line.lstrip().startswith('#') or line.isspace():
                    continue
                # Parse the iface clause
                if line.startswith('iface'):
                    sline = line.split()

                    if len(sline) != 4:
                        msg = 'Interface file malformed: {0}.'
                        msg = msg.format(sline)
                        log.error(msg)
                        raise AttributeError(msg)

                    iface_name = sline[1]
                    addrfam = sline[2]
                    method = sline[3]

                    # Create item in dict, if not already there
                    if iface_name not in adapters:
                        adapters[iface_name] = salt.utils.odict.OrderedDict()

                    # Create item in dict, if not already there
                    if 'data' not in adapters[iface_name]:
                        adapters[iface_name]['data'] = salt.utils.odict.OrderedDict()

                    if addrfam not in adapters[iface_name]['data']:
                        adapters[iface_name]['data'][addrfam] = salt.utils.odict.OrderedDict()

                    iface_dict = adapters[iface_name]['data'][addrfam]

                    iface_dict['addrfam'] = addrfam
                    iface_dict['proto'] = method

                # Parse the detail clauses.
                elif line[0].isspace():
                    sline = line.split()

                    # conf file attr: dns-nameservers
                    # salt states.network attr: dns

                    attr, valuestr = line.rstrip().split(None, 1)
                    if _attrmaps_contain_attr(attr):
                        _attr = DEBIAN_ATTR_TO_SALT_ATTR_MAP.get(attr, attr)
                        if '-' in _attr:
                            attrname = _attr.replace('-', '_')
                        else:
                            attrname = _attr
                        (valid, value, errmsg) = _validate_interface_option(
                            attr, valuestr, addrfam)
                        iface_dict[attrname] = value

                    elif attr in _REV_ETHTOOL_CONFIG_OPTS:
                        if 'ethtool' not in iface_dict:
                            iface_dict['ethtool'] = salt.utils.odict.OrderedDict()
                        iface_dict['ethtool'][attr] = valuestr

                    elif attr.startswith('bond'):
                        opt = attr.split('_', 1)[1]
                        if 'bonding' not in iface_dict:
                            iface_dict['bonding'] = salt.utils.odict.OrderedDict()
                        iface_dict['bonding'][opt] = valuestr

                    elif attr.startswith('bridge'):
                        opt = attr.split('_', 1)[1]
                        if 'bridging' not in iface_dict:
                            iface_dict['bridging'] = salt.utils.odict.OrderedDict()
                        iface_dict['bridging'][opt] = valuestr

                    elif attr in ['up', 'pre-up', 'post-up',
                                  'down', 'pre-down', 'post-down']:
                        cmd = valuestr
                        cmd_key = '{0}_cmds'.format(re.sub('-', '_', attr))
                        if cmd_key not in iface_dict:
                            iface_dict[cmd_key] = []
                        iface_dict[cmd_key].append(cmd)

                elif line.startswith('auto'):
                    for word in line.split()[1:]:
                        if word not in adapters:
                            adapters[word] = salt.utils.odict.OrderedDict()
                        adapters[word]['enabled'] = True

                elif line.startswith('allow-hotplug'):
                    for word in line.split()[1:]:
                        if word not in adapters:
                            adapters[word] = salt.utils.odict.OrderedDict()
                        adapters[word]['hotplug'] = True

    # Return a sorted list of the keys for bond, bridge and ethtool options to
    # ensure a consistent order
    for iface_name in adapters:
        for opt in ['ethtool', 'bonding', 'bridging']:
            if 'inet' in adapters[iface_name]['data']:
                if opt in adapters[iface_name]['data']['inet']:
                    opt_keys = sorted(adapters[iface_name]['data']['inet'][opt].keys())
                    adapters[iface_name]['data']['inet'][opt + '_keys'] = opt_keys

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


def _parse_ethtool_pppoe_opts(opts, iface):
    '''
    Filters given options and outputs valid settings for ETHTOOLS_PPPOE_OPTS
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    '''
    config = {}

    for opt in _DEB_CONFIG_PPPOE_OPTS:
        if opt in opts:
            config[opt] = opts[opt]

    if 'provider' in opts:
        if opts['provider']:
            pass
        else:
            _raise_error_iface(iface, 'provider', _CONFIG_TRUE + _CONFIG_FALSE)

    valid = _CONFIG_TRUE + _CONFIG_FALSE
    for option in ('noipdefault', 'usepeerdns', 'defaultroute', 'hide-password', 'noauth', 'persist', 'noaccomp'):
        if option in opts:
            if opts[option] in _CONFIG_TRUE:
                config.update({option: 'True'})
            elif opts[option] in _CONFIG_FALSE:
                config.update({option: 'False'})
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
        except ValueError:
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
            except ValueError:
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
        except ValueError:
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
            except ValueError:
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
            except ValueError:
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
            except ValueError:
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
            except ValueError:
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


def _parse_bridge_opts(opts, iface):
    '''
    Filters given options and outputs valid settings for BRIDGING_OPTS
    If an option has a value that is not expected, this
    function will log the Interface, Setting and what was expected.
    '''
    config = {}

    if 'ports' in opts:
        config.update({'ports': opts['ports']})

    for opt in ['ageing', 'fd', 'gcint', 'hello', 'maxage']:
        if opt in opts:
            try:
                float(opts[opt])
                config.update({opt: opts[opt]})
            except ValueError:
                _raise_error_iface(iface, opt, ['float'])

    for opt in ['bridgeprio', 'maxwait']:
        if opt in opts:
            if isinstance(opts[opt], int):
                config.update({opt: opts[opt]})
            else:
                _raise_error_iface(iface, opt, ['integer'])

    if 'hw' in opts:
        # match 12 hex digits with either : or - as separators between pairs
        if re.match('[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$',
                    opts['hw'].lower()):
            config.update({'hw': opts['hw']})
        else:
            _raise_error_iface(iface, 'hw', ['valid MAC address'])

    for opt in ['pathcost', 'portprio']:
        if opt in opts:
            try:
                port, cost_or_prio = opts[opt].split()
                int(cost_or_prio)
                config.update({opt: '{0} {1}'.format(port, cost_or_prio)})
            except ValueError:
                _raise_error_iface(iface, opt, ['interface integer'])

    if 'stp' in opts:
        if opts['stp'] in _CONFIG_TRUE:
            config.update({'stp': 'on'})
        elif opts['stp'] in _CONFIG_FALSE:
            config.update({'stp': 'off'})
        else:
            _raise_error_iface(iface, 'stp', _CONFIG_TRUE + _CONFIG_FALSE)

    if 'waitport' in opts:
        if isinstance(opts['waitport'], int):
            config.update({'waitport': opts['waitport']})
        else:
            values = opts['waitport'].split()
            waitport_time = values.pop(0)
            if waitport_time.isdigit() and values:
                config.update({
                    'waitport': '{0} {1}'.format(
                        waitport_time, ' '.join(values)
                    )
                })
            else:
                _raise_error_iface(iface, opt, ['integer [interfaces]'])

    return config


def _parse_settings_eth(opts, iface_type, enabled, iface):
    '''
    Filters given options and outputs valid settings for a
    network interface.
    '''
    adapters = salt.utils.odict.OrderedDict()
    adapters[iface] = salt.utils.odict.OrderedDict()

    adapters[iface]['type'] = iface_type

    adapters[iface]['data'] = salt.utils.odict.OrderedDict()
    iface_data = adapters[iface]['data']
    iface_data['inet'] = salt.utils.odict.OrderedDict()

    if enabled:
        adapters[iface]['enabled'] = True

    iface_data['inet']['addrfam'] = 'inet'

    if iface_type not in ['bridge']:
        tmp_ethtool = _parse_ethtool_opts(opts, iface)
        if tmp_ethtool:
            ethtool = {}
            for item in tmp_ethtool:
                ethtool[_ETHTOOL_CONFIG_OPTS[item]] = tmp_ethtool[item]

            iface_data['inet']['ethtool'] = ethtool
            # return a list of sorted keys to ensure consistent order
            iface_data['inet']['ethtool_keys'] = sorted(ethtool.keys())

    if iface_type == 'bridge':
        bridging = _parse_bridge_opts(opts, iface)
        if bridging:
            iface_data['inet']['bridging'] = bridging
            iface_data['inet']['bridging_keys'] = sorted(bridging.keys())

    elif iface_type == 'bond':
        bonding = _parse_settings_bond(opts, iface)
        if bonding:
            iface_data['inet']['bonding'] = bonding
            iface_data['inet']['bonding']['slaves'] = opts['slaves']
            iface_data['inet']['bonding_keys'] = sorted(bonding.keys())

    elif iface_type == 'slave':
        adapters[iface]['master'] = opts['master']

    elif iface_type == 'vlan':
        iface_data['inet']['vlan_raw_device'] = re.sub(r'\.\d*', '', iface)

    elif iface_type == 'pppoe':
        tmp_ethtool = _parse_ethtool_pppoe_opts(opts, iface)
        if tmp_ethtool:
            for item in tmp_ethtool:
                adapters[iface]['data']['inet'][_DEB_CONFIG_PPPOE_OPTS[item]] = tmp_ethtool[item]

    if 'enable_ipv6' in opts and opts['enable_ipv6']:  # TODO: check yes/no
        # iface_data.append({})
        iface_data['inet6'] = {}
        iface_data['inet6']['addrfam'] = 'inet6'
        iface_data['inet6']['netmask'] = '64'  # defaults to 64

        if 'iface_type' in opts and opts['iface_type'] == 'vlan':
            iface_data['inet6']['vlan_raw_device'] = (
                re.sub(r'\.\d*', '', iface))

    for opt in opts:
        if opt.startswith('ipv6'):
            optname = opt[4:]  # trim off the ipv6
            addrfam = 'inet6'
        else:
            optname = opt
            addrfam = 'inet'

        _optname = SALT_ATTR_TO_DEBIAN_ATTR_MAP.get(optname, optname)
        if _attrmaps_contain_attr(_optname):
            valuestr = opts[opt]

            # default to 'static' if proto is 'none'
            if optname == 'proto' and valuestr == 'none':
                valuestr = 'static'

            (valid, value, errmsg) = _validate_interface_option(
                _optname, valuestr, addrfam=addrfam)

            if not valid:
                _raise_error_iface(iface, '{0!r} {1!r}'.format(opt, valuestr), [errmsg])  # TODO

            # replace dashes with underscores for jinja
            _optname = _optname.replace('-', '_')
            iface_data[addrfam][_optname] = value

    for opt in ['up_cmds', 'pre_up_cmds', 'post_up_cmds',
                'down_cmds', 'pre_down_cmds', 'post_down_cmds']:
        if opt in opts:
            iface_data['inet'][opt] = opts[opt]

    return adapters


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
        except ValueError:
            _raise_error_network('hostname', ['server1.example.com'])

    if opts['hostname']:
        result['hostname'] = opts['hostname']
    else:
        _raise_error_network('hostname', ['server1.example.com'])

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
    with salt.utils.flopen(filename, 'w') as fout:
        fout.write(data)
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
    with salt.utils.flopen(filename, 'w') as fout:
        fout.write(data)

    __salt__['file.set_mode'](filename, '0755')
    return filename


def _write_file_network(data, filename, create=False):
    '''
    Writes a file to disk
    If file does not exist, only create if create
    argument is True
    '''
    if not os.path.exists(filename) and not create:
        msg = '{0} cannot be written. {0} does not exist\
                and create is set to False'
        msg = msg.format(filename)
        log.error(msg)
        raise AttributeError(msg)
    with salt.utils.flopen(filename, 'w') as fout:
        fout.write(data)


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


def _write_file_ifaces(iface, data):
    '''
    Writes a file to disk
    '''
    try:
        template = JINJA.get_template('debian_eth.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template debian_eth.jinja')
        return ''

    # Read /etc/network/interfaces into a dict
    adapters = _parse_interfaces()
    # Apply supplied settings over on-disk settings
    adapters[iface] = data

    ifcfg = ''
    for adapter in adapters:
        if 'type' in adapters[adapter] and adapters[adapter]['type'] == 'slave':
            # Override values so the interfaces file is correct
            adapters[adapter]['enabled'] = False
            adapters[adapter]['data']['inet']['addrfam'] = 'inet'
            adapters[adapter]['data']['inet']['proto'] = 'manual'

        tmp = template.render({'name': adapter, 'data': adapters[adapter]})
        ifcfg = tmp + ifcfg
        if adapter == iface:
            saved_ifcfg = tmp

    filename = _DEB_NETWORK_FILE
    if not os.path.exists(os.path.dirname(filename)):
        msg = '{0} cannot be written.'
        msg = msg.format(os.path.dirname(filename))
        log.error(msg)
        raise AttributeError(msg)
    with salt.utils.flopen(filename, 'w') as fout:
        fout.write(ifcfg)

    # Return as a array so the difflib works
    return saved_ifcfg.split('\n')


def _write_file_ppp_ifaces(iface, data):
    '''
    Writes a file to disk
    '''
    try:
        template = JINJA.get_template('debian_ppp_eth.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template debian_ppp_eth.jinja')
        return ''

    adapters = _parse_interfaces()
    adapters[iface] = data

    ifcfg = ''
    tmp = template.render({'data': adapters[iface]})
    ifcfg = tmp + ifcfg

    filename = _DEB_PPP_DIR + '/' + adapters[iface]['data']['inet']['provider']
    if not os.path.exists(os.path.dirname(filename)):
        msg = '{0} cannot be written.'
        msg = msg.format(os.path.dirname(filename))
        log.error(msg)
        raise AttributeError(msg)
    fout = salt.utils.fopen(filename, 'w')
    fout.write(ifcfg)
    fout.close()

    # Return as a array so the difflib works
    return filename


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

    if 'test' in settings and settings['test']:
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

    elif iface_type == 'vlan':
        settings['vlan'] = 'yes'

    elif iface_type == 'pppoe':
        settings['pppoe'] = 'yes'
        if not __salt__['pkg.version']('ppp'):
            inst = __salt__['pkg.install']('ppp')

    elif iface_type is 'bond':
        if 'slaves' not in settings:
            msg = 'slaves is a required setting for bond interfaces'
            log.error(msg)
            raise AttributeError(msg)

    elif iface_type == 'bridge':
        if 'ports' not in settings:
            msg = 'ports is a required setting for bridge interfaces'
            log.error(msg)
            raise AttributeError(msg)
        __salt__['pkg.install']('bridge-utils')

    if iface_type in ['eth', 'bond', 'bridge', 'slave', 'vlan', 'pppoe']:
        opts = _parse_settings_eth(settings, iface_type, enabled, iface)

    if 'test' in settings and settings['test']:
        return _read_temp_ifaces(iface, opts[iface])

    ifcfg = _write_file_ifaces(iface, opts[iface])

    if iface_type == 'pppoe':
        _write_file_ppp_ifaces(iface, opts[iface])

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

    add_routecfg = template.render(route_type='add', routes=opts['routes'], iface=iface)

    del_routecfg = template.render(route_type='del', routes=opts['routes'], iface=iface)

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


def get_network_settings():
    '''
    Return the contents of the global network script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_network_settings
    '''
    skip_etc_default_networking = (
        __grains__['osfullname'] == 'Ubuntu' and
        int(__grains__['osrelease'].split('.')[0]) >= 12)

    if skip_etc_default_networking:
        settings = {}
        if __salt__['service.available']('networking'):
            if __salt__['service.status']('networking'):
                settings['networking'] = "yes"
            else:
                settings['networking'] = "no"
        else:
            settings['networking'] = "no"

        hostname = _parse_hostname()
        domainname = _parse_domainname()

        settings['hostname'] = hostname
        settings['domainname'] = domainname

    else:
        settings = _parse_current_network_settings()

    try:
        template = JINJA.get_template('display-network.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template display-network.jinja')
        return ''

    network = template.render(settings)
    return _read_temp(network)


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
        stop = __salt__['service.stop']('networking')
        time.sleep(2)
        res = stop and __salt__['service.start']('networking')

    return hostname_res and res


def build_network_settings(**settings):
    '''
    Build the global network script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_network_settings <settings>
    '''
    changes = []

    # Read current configuration and store default values
    current_network_settings = _parse_current_network_settings()

    # Build settings
    opts = _parse_network_settings(settings, current_network_settings)

    # Ubuntu has moved away from /etc/default/networking
    # beginning with the 12.04 release so we disable or enable
    # the networking related services on boot
    skip_etc_default_networking = (
        __grains__['osfullname'] == 'Ubuntu' and
        int(__grains__['osrelease'].split('.')[0]) >= 12)
    if skip_etc_default_networking:
        if opts['networking'] == 'yes':
            service_cmd = 'service.enable'
        else:
            service_cmd = 'service.disable'

        if __salt__['service.available']('NetworkManager'):
            __salt__[service_cmd]('NetworkManager')

        if __salt__['service.available']('networking'):
            __salt__[service_cmd]('networking')
    else:
        try:
            template = JINJA.get_template('network.jinja')
        except jinja2.exceptions.TemplateNotFound:
            log.error('Could not load template network.jinja')
            return ''
        network = template.render(opts)

        if 'test' in settings and settings['test']:
            return _read_temp(network)
        # Write settings
        _write_file_network(network, _DEB_NETWORKING_FILE, True)

    # Write hostname to /etc/hostname
    sline = opts['hostname'].split('.', 1)
    hostname = '{0}\n' . format(sline[0])
    current_domainname = current_network_settings['domainname']

    # Only write the hostname if it has changed
    if not opts['hostname'] == current_network_settings['hostname']:
        # TODO  replace wiht a call to network.mod_hostname instead
        _write_file_network(hostname, _DEB_HOSTNAME_FILE)

    new_domain = False
    if len(sline) > 1:
        new_domainname = sline[1]
        if new_domainname != current_domainname:
            domainname = new_domainname
            opts['domainname'] = new_domainname
            new_domain = True
        else:
            domainname = current_domainname
            opts['domainname'] = domainname
    else:
        domainname = current_domainname
        opts['domainname'] = domainname

    # If the domain changes, then we should write the resolv.conf file.
    if new_domain:
        # Look for existing domain line and update if necessary
        contents = _parse_resolve()
        prog = re.compile(r'domain\s+(?P<domain_name>\S+)')
        new_contents = []
        found_domain = False
        for item in contents:
            match = prog.match(item)
            if match:
                new_contents.append('domain {0}\n' . format(domainname))
                found_domain = True
            else:
                new_contents.append(item)

        # A domain line didn't exist so we'll add one in
        # with the new domainname
        if not found_domain:
            new_contents.insert(0, 'domain {0}\n' . format(domainname))
        new_resolv = ''.join(new_contents)

        # Write /etc/resolv.conf
        _write_file_network(new_resolv, _DEB_RESOLV_FILE)

    #  used for returning the results back
    try:
        template = JINJA.get_template('display-network.jinja')
    except jinja2.exceptions.TemplateNotFound:
        log.error('Could not load template display-network.jinja')
        return ''
    network = template.render(opts)
    changes.extend(_read_temp(network))

    return changes
