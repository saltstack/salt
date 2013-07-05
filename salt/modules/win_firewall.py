'''
Module for configuring Windows Firewall
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
        return 'firewall'
    return False


def get_fw_config():
    '''
    Get the status of all the firewall profiles
    '''
    
    profiles = {}
    curr = None
    
    for line in __salt__['cmd.run']( 'netsh advfirewall show allprofiles' ).splitlines():
        if not curr:
            tmp = re.search('(.*) Profile Settings:', line)
            if tmp:
                curr = tmp.group(1)
        elif line.startswith('State'):
            profiles[curr] = line.split()[1] == 'ON'
            curr = None
    
    return profiles


def disable_fw():
    '''
    Disable all the firewall profiles
    '''
    
    return __salt__['cmd.run']( 'netsh advfirewall set allprofiles state off' ) == 'Ok.'


