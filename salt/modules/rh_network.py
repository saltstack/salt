'''
The networking module for RHEL/Fedora based distros 
'''

import os
import logging

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    '''$
    Confine this module to RHEL/Fedora based distros$
    '''
    dists = ('CentOS', 'Scientific', 'RedHat')
    if __grains__['os'] in dists:
        return 'network'
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
    'use_carrier', 'lacp_rate', 'hashing-algorithm'
]
_RH_NETWORK_SCRIPT_DIR = '/etc/sysconfig/network-scripts'
_CONFIG_TRUE = [ 'yes', 'on', 'true', '1', True]
_CONFIG_FALSE = [ 'no', 'off', 'false', '0', False]
_IFACE_TYPES = ['eth', 'bond', 'alias', 'clone', 'ipsec', 'dialup']

def _generate_if_settings(opts, iftype, iface):
    '''
    Fiters given options and outputs valid settings for requested
    operation. If an option has a value that is not expected, this
    fuction will log what the Interface, Setting and what it was expecting.
    '''
    
    if iftype in ['eth', 'lo', 'br']:
        config = {}
        offload = {}
        
    
        # General Configuration
        if opts.has_key('autoneg'):
            if opts['autoneg'] in _CONFIG_TRUE:
                config.update( {'autoneg':'on'} )
            elif opts['autoneg'] in _CONFIG_FALSE:
                config.update( {'autoneg':'off'} )
            else:
                log.info('Invalid option -- Interface: %s Option: %s. Expecting: [%s]' % (iface, 'autoneg', '|'.join(str(x) for x in _CONFIG_TRUE + _CONFIG_FALSE) ))
        
        if opts.has_key('duplex'):
            if opts['duplex'] in ['full', 'half']:
                config.update( {'duplex':opts['duplex']} )
            else:
                log.info('Invalid option -- Interface: %s Option: %s. Expecting: [full|half]' % (iface, 'duplex'))
                
        if opts.has_key('mtu'):
            try:
                int(opts['mtu'])
                config.update( {'mtu': opts['mtu']} )
            except:
                log.info('Invalid option -- Interface: %s Option: %s. Expecting: [integer]' % (iface, 'mtu'))
                
        if opts.has_key('speed'):
            if opts['speed'] in ['10', '100', '1000']:
                config.update( {'speed':opts['speed']} )
            else:
                log.info('Invalid option -- Interface: %s Option: %s. Expecting: [10|100|1000]' % (iface, 'speed'))
        
        # Offload settings
        for option in ('rx', 'tx', 'sg', 'tso', 'ufo', 'gso', 'gro', 'lro'):
            if opts.has_key(option):
                if opts[option] in _CONFIG_TRUE:
                    offload.update( {option:'on'} )
                elif opts[option] in _CONFIG_FALSE:
                    offload.update( {option:'off'} )
                else:
                    log.info('Invalid option -- Interface: %s Option: %s. Expecting: [%s]' % (iface, option, '|'.join(str(x) for x in _CONFIG_TRUE + _CONFIG_FALSE) ))
                    
        return config, offload
        
    if iftype in ['bond']:
        bond = {}      
        # Bonding settings
        if opts.has_key('mode'):
            bond_def = {
                'miimon':'100', # Link monitoring in milliseconds. Most NICs support this
                'arp_interval':'250',
                'downdelay':'200', # miimon * 2
                'lacp_rate':'0', # 0: Slow - every 30 seconds, 1: Fast - every 1 second
                'max_bonds':'1', # Max bonds for this driver
                'updelay':'0', # Specifies the time, in milliseconds, to wait before enabling a slave after a link recovery has been detected. Only used with miimon.
                'use_carrier':'on', # Used with miimon. On: driver sends mii, Off: ethtool sends mii
                'xmit_hash_policy':'layer2', # Defualt. Don't chnage unless you know what you are doing.
            }
        
            if opts['mode'] in ['balance-rr', '0']:
                bond.update( {'mode':'0'} )
                if opts.has_key('arp_ip_target'):
                    if isinstance(opts['arp_ip_target'], list):
                        if len(opts['arp_ip_target']) >= 1 and len(opts['arp_ip_target']) <= 16:
                            bond.update( {'arp_ip_target':[]} )
                        for ip in opts['arp_ip_target']:
                            bond['arp_ip_target'].append(ip)
                        else:
                            log.info('Invalid option -- Interface: %s Option: %s. Expecting: [list of ips (up to 16)]' % (iface, 'arp_ip_target'))
                    else:
                        log.info('Invalid option -- Interface: %s Option: %s. Expecting: [list of ips (up to 16)]' % (iface, 'arp_ip_target'))
                else:
                    log.info('Missing Required option -- Interface: %s Option: %s. Expecting: [list of ips (up to 16)]' % (iface, 'arp_ip_target'))
                
                if opts.has_key('arp_interval'):
                    try:
                        int(opts['arp_interval'])
                        bond.update( {'arp_interval':opts['arp_interval']} )
                    except:
                        log.info('Invalid option -- Interface: %s Option: %s. Expecting: [integer]' % (iface, 'arp_interval'))
                else:
                    bond.update( {'arp_interval':bond_def['arp_interval']} )
                     
                if bond.has_key('arp_interval') and bond.has_key('arp_ip_target'):
                    pass
                else:
                    bond = {}
        
            elif opts['mode'] in ['active-backup', '1']:
                bond.update( {'mode':'1'} )
                for bo in ['miimon', 'downdelay', 'updelay']:
                    if opts.has_key(bo):
                        try:
                            int(opts[bo])
                            bond.update( {bo:opts[bo]} )
                        except:
                            log.info('Invalid option -- Interface: %s Option: %s. Expecting: [integer]' % (iface, bo))
                            log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, bo, bond_def[bo]))
                            bond.update( {bo:bond_def[bo]} )
                    else:
                        log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, bo, bond_def[bo]))
                        bond.update( {bo:bond_def[bo]} )
                if opts.has_key('use_carrier'):
                    if opts['use_carrier'] in _CONFIG_TRUE:
                        bond.update( {'use_carrier': 'on'} )
                    elif opts['use_carrier'] in _CONFIG_FALSE:
                        bond.update( {'use_carrier': 'off'} )
                    else:
                        log.info('Invalid option -- Interface: %s Option: %s. Expecting: [%s]' % (iface, 'use_carrier', '|'.join(str(x) for x in _CONFIG_TRUE + _CONFIG_FALSE) ))
                        log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, 'use_carrier', bond_def['use_carrier']))
                        bond.update( {'use_carrier': bond_def['use_carrier'] } )
                else:
                    log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, 'use_carrier', bond_def['use_carrier']))
                    bond.update( {'use_carrier': bond_def['use_carrier'] } )    
                            
            elif opts['mode'] in ['balance-xor', '2']:
                bond.update( {'mode':'2'} )
                if opts.has_key('arp_ip_target'):
                    if isinstance(opts['arp_ip_target'], list):
                        if len(opts['arp_ip_target']) >= 1 and len(opts['arp_ip_target']) <= 16:
                            bond.update( {'arp_ip_target':[]} )
                        for ip in opts['arp_ip_target']:
                            bond['arp_ip_target'].append(ip)
                        else:
                            log.info('Invalid option -- Interface: %s Option: %s. Expecting: [list of ips (up to 16)]' % (iface, 'arp_ip_target'))
                    else:
                        log.info('Invalid option -- Interface: %s Option: %s. Expecting: [list of ips (up to 16)]' % (iface, 'arp_ip_target'))
                else:
                    log.info('Missing Required option -- Interface: %s Option: %s. Expecting: [list of ips (up to 16)]' % (iface, 'arp_ip_target'))
                
                if opts.has_key('arp_interval'):
                    try:
                        int(opts['arp_interval'])
                        bond.update( {'arp_interval':opts['arp_interval']} )
                    except:
                        log.info('Invalid option -- Interface: %s Option: %s. Expecting: [integer]' % (iface, 'arp_interval'))
                else:
                    bond.update( {'arp_interval':bond_def['arp_interval']} )
                
                if opts.has_key('primary'):
                    bond.update( {'primary': opts['primary']} )
                
                if opts.has_key('hashing-algorithm'):
                    if opts['hashing-algorithm'] in ['layer2', 'layer3+4']:
                        bond.update( {'xmit_hash_policy':opts['hashing-algorithm']} )
                     
                if bond.has_key('arp_interval') and bond.has_key('arp_ip_target'):
                    pass
                else:
                    bond = {}
                
            elif opts['mode'] in ['broadcast', '3']:
                bond.update( {'mode':'3'} )
                for bo in ['miimon', 'downdelay', 'updelay']:
                    if opts.has_key(bo):
                        try:
                            int(opts[bo])
                            bond.update( {bo:opts[bo]} )
                        except:
                            log.info('Invalid option -- Interface: %s Option: %s. Expecting: [integer]' % (iface, bo))
                            log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, bo, bond_def[bo]))
                            bond.update( {bo:bond_def[bo]} )
                    else:
                        log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, bo, bond_def[bo]))
                        bond.update( {bo:bond_def[bo]} )
                if opts.has_key('use_carrier'):
                    if opts['use_carrier'] in _CONFIG_TRUE:
                        bond.update( {'use_carrier': 'on'} )
                    elif opts['use_carrier'] in _CONFIG_FALSE:
                        bond.update( {'use_carrier': 'off'} )
                    else:
                        log.info('Invalid option -- Interface: %s Option: %s. Expecting: [%s]' % (iface, 'use_carrier', '|'.join(str(x) for x in _CONFIG_TRUE + _CONFIG_FALSE) ))
                        log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, 'use_carrier', bond_def['use_carrier']))
                        bond.update( {'use_carrier': bond_def['use_carrier'] } )
                else:
                    log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, 'use_carrier', bond_def['use_carrier']))
                    bond.update( {'use_carrier': bond_def['use_carrier'] } )    
                
            elif opts['mode'] in ['802.3ad', '4']:
                bond.update( {'mode':'4'} )
                for bo in ['miimon', 'downdelay', 'updelay', 'lacp_rate']:

                    if opts.has_key(bo):
                        if bo == 'lacp_rate':
                            if opts[bo] == 'fast':
                                opts.update( {bo:'1'} )
                            if opts[bo] == 'slow':
                                opts.update( {bo:'0'} )
                        try:
                            int(opts[bo])
                            bond.update( {bo:opts[bo]} )
                        except:
                            log.info('Invalid option -- Interface: %s Option: %s. Expecting: [integer]' % (iface, bo))
                            log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, bo, bond_def[bo]))
                            bond.update( {bo:bond_def[bo]} )
                        
                    else:
                        log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, bo, bond_def[bo]))
                        bond.update( {bo:bond_def[bo]} )
                if opts.has_key('use_carrier'):
                    if opts['use_carrier'] in _CONFIG_TRUE:
                        bond.update( {'use_carrier': 'on'} )
                    elif opts['use_carrier'] in _CONFIG_FALSE:
                        bond.update( {'use_carrier': 'off'} )
                    else:
                        log.info('Invalid option -- Interface: %s Option: %s. Expecting: [%s]' % (iface, 'use_carrier', '|'.join(str(x) for x in _CONFIG_TRUE + _CONFIG_FALSE) ))
                        log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, 'use_carrier', bond_def['use_carrier']))
                        bond.update( {'use_carrier': bond_def['use_carrier'] } )
                else:
                    log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, 'use_carrier', bond_def['use_carrier']))
                    bond.update( {'use_carrier': bond_def['use_carrier'] } )
                
                if opts.has_key('hashing-algorithm'):
                    if opts['hashing-algorithm'] in ['layer2', 'layer3+4']:
                        bond.update( {'xmit_hash_policy':opts['hashing-algorithm']} )
        
            elif opts['mode'] in ['balance-tlb', '5']:
                bond.update( {'mode':'5'} )
                for bo in ['miimon', 'downdelay', 'updelay']:
                    if opts.has_key(bo):
                        try:
                            int(opts[bo])
                            bond.update( {bo:opts[bo]} )
                        except:
                            log.info('Invalid option -- Interface: %s Option: %s. Expecting: [integer]' % (iface, bo))
                            log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, bo, bond_def[bo]))
                            bond.update( {bo:bond_def[bo]} )
                    else:
                        log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, bo, bond_def[bo]))
                        bond.update( {bo:bond_def[bo]} )
                if opts.has_key('use_carrier'):
                    if opts['use_carrier'] in _CONFIG_TRUE:
                        bond.update( {'use_carrier': 'on'} )
                    elif opts['use_carrier'] in _CONFIG_FALSE:
                        bond.update( {'use_carrier': 'off'} )
                    else:
                        log.info('Invalid option -- Interface: %s Option: %s. Expecting: [%s]' % (iface, 'use_carrier', '|'.join(str(x) for x in _CONFIG_TRUE + _CONFIG_FALSE) ))
                        log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, 'use_carrier', bond_def['use_carrier']))
                        bond.update( {'use_carrier': bond_def['use_carrier'] } )
                else:
                    log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, 'use_carrier', bond_def['use_carrier']))
                    bond.update( {'use_carrier': bond_def['use_carrier'] } )    
                
            elif opts['mode'] in ['balance-alb', '6']:
                bond.update( {'mode':'6'} )
                for bo in ['miimon', 'downdelay', 'updelay']:
                    if opts.has_key(bo):
                        try:
                            int(opts[bo])
                            bond.update( {bo:opts[bo]} )
                        except:
                            log.info('Invalid option -- Interface: %s Option: %s. Expecting: [integer]' % (iface, bo))
                            log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, bo, bond_def[bo]))
                            bond.update( {bo:bond_def[bo]} )
                    else:
                        log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, bo, bond_def[bo]))
                        bond.update( {bo:bond_def[bo]} )
                if opts.has_key('use_carrier'):
                    if opts['use_carrier'] in _CONFIG_TRUE:
                        bond.update( {'use_carrier': 'on'} )
                    elif opts['use_carrier'] in _CONFIG_FALSE:
                        bond.update( {'use_carrier': 'off'} )
                    else:
                        log.info('Invalid option -- Interface: %s Option: %s. Expecting: [%s]' % (iface, 'use_carrier', '|'.join(str(x) for x in _CONFIG_TRUE + _CONFIG_FALSE) ))
                        log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, 'use_carrier', bond_def['use_carrier']))
                        bond.update( {'use_carrier': bond_def['use_carrier'] } )
                else:
                    log.info('Setting default option -- Interface: %s Option: %s Value: %s' % (iface, 'use_carrier', bond_def['use_carrier']))
                    bond.update( {'use_carrier': bond_def['use_carrier'] } )    
            else:
                log.info('Invalid option -- Interface: %s Option: %s. Expecting: [0|1|2|3|4|5|6|balance-rr|active-backup|balance-xor|broadcast|802.3ad|balance-tlb|balance-alb]' % (iface, 'mode'))
    
        return bond

def build(iface, ip, type, settings):
    if type in _IFACE_TYPES:
        _generate_if_settings(opts=settings, iftype=type, iface=iface)
        pass
    pass

def _read_file(path):
    '''
    Reads and returns the contents of a file
    '''
    try:
        with open(path, 'rb') as contents:
            return contents.read()
    except:
        return ''

def get(iface):
    filename = join(_RH_NETWORK_SCRIPT_DIR, 'ifcfg-%s' % iface)
    return _read_file(filename)
