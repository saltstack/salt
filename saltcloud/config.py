'''
Manage configuration files in salt-cloud
'''

# Import python libs
import os

# Import salt libs
import salt.config


def cloud_config(path):
    '''
    Read in the salt cloud config and return the dict
    '''
    opts = {# Provider defaults
            'provider': '',
            'location': '',
            # User/Passwords/keys
            'RACKSPACE_key': '',
            'RACKSPACE_user': '',
            'LINODE_apikey': '',
            'EC2_key': '',
            'EC2_user': '',
            # Global defaults
            'ssh_auth': '',
            'keysize': 4096,
            'os': '',
            }

    salt.config.load_config(opts, path, 'SALT_CLOUD_CONFIG')

    if 'include' in opts:
        opts = include_config(opts, path)

    return opts

def vm_config(path):
    '''
    Read in the salt cloud vm config file
    '''
    # No defaults
    opts = {}
    
    salt.config.load_config(opts, path, 'SALT_CLOUDVM_CONFIG')

    if 'include' in opts:
        opts = include_config(opts, path)

    return opts
