'''
Module for configuring DNS Client on Windows systems
'''

# Import python libs
import re

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only works on Windows systems
    '''
    
    if salt.utils.is_windows():
        return 'win_dns_client'
    return False


def get_dns_servers(interface='Local Area Connection'):
    '''
    return a list of the configured dns servers of the specific interface
    '''
    
    out = __salt__['cmd.run']( 'netsh interface ip show dns "{0}"'.format( interface ) )
    return re.findall("(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", out)


def rm_dns(ip, interface='Local Area Connection'):
    '''
    Remove the dns server to the nertwork interface
    '''
    
    return __salt__['cmd.retcode']( 'netsh interface ip delete dns "{0}" {1} validate=no'.format( interface, ip ) ) == 0


def add_dns(ip, interface='Local Area Connection', index=1):
    '''
    Add the dns server to the nertwork interface
    (index starts from 1)
    
    Note: if the interface dns is configured by DHCP all the dns servers will be removed from the
    interface and the requested dns will be the only one
    '''
    
    servers = get_dns_servers(interface)
    
    # Return true if configured
    try:
        if servers[index-1] == ip:
            return True
    except IndexError:
        pass
    
    # If configured in the wrong order delete it
    if ip in servers:
        rm_dns(ip, interface)
    
    retcode = __salt__['cmd.retcode']( 'netsh interface ip add dns "{0}" {1} index={2} validate=no'.format( interface, ip, index ) )
    return retcode == 0


def dns_dhcp(interface='Local Area Connection'):
    '''
    Configure the interface to get it's DNS servers from the DHCP server
    '''
    
    return __salt__['cmd.retcode']( 'netsh interface ip set dns "{0}" source=dhcp'.format( interface ) ) == 0


def get_dns_config(interface='Local Area Connection'):
    '''
    Get the type of dns configuration (dhcp / static)
    '''
    
    out = __salt__['cmd.run']( 'netsh interface ip show dns "{0}"'.format( interface) )
    if re.search('DNS servers configured through DHCP', out):
        return 'dhcp'
    else:
        return 'static'


