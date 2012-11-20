'''
Manage configuration files in salt-cloud
'''

# Import python libs
import os

# Import salt libs
import salt.config

__dflt_log_datefmt = '%Y-%m-%d %H:%M:%S'
__dflt_log_fmt_console = '[%(levelname)-8s] %(message)s'
__dflt_log_fmt_logfile = '%(asctime)s,%(msecs)03.0f [%(name)-17s][%(levelname)-8s] %(message)s'


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
            'start_action': None,
            # Logging defaults
            'log_file': '/var/log/salt/cloud',
            'log_level': None,
            'log_level_logfile': None,
            'log_datefmt': __dflt_log_datefmt,
            'log_fmt_console': __dflt_log_fmt_console,
            'log_fmt_logfile': __dflt_log_fmt_logfile,
            'log_granular_levels': {},
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
