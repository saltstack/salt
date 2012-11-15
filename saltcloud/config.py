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
    opts = {  # Provider defaults
            'provider': '',
            'location': '',
            # Global defaults
            'ssh_auth': '',
            'keysize': 4096,
            'os': '',
            # Logging defaults
            'log_level': 'info',
            'log_level_logfile': 'info',
            'log_file': '/var/log/salt/cloud'
            }

    salt.config.load_config(opts, path, 'SALT_CLOUD_CONFIG')

    if 'include' in opts:
        opts = salt.config.include_config(opts, path)

    return opts


def vm_config(path):
    '''
    Read in the salt cloud vm config file
    '''
    # No defaults
    opts = {}

    salt.config.load_config(opts, path, 'SALT_CLOUDVM_CONFIG')

    if 'include' in opts:
        opts = salt.config.include_config(opts, path)

    vms = []

    if 'conf_file' in opts:
        opts.pop('conf_file')

    for key, val in opts.items():
        val['profile'] = key
        vms.append(val)

    return vms
