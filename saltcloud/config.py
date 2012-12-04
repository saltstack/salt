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

    opts = old_to_new(opts)
    opts = prov_dict(opts)

    return opts


def old_to_new(opts):
    optskeys = opts.keys()
    providers = ('AWS',
                 'GOGRID',
                 'IBMSCE',
                 'JOYENT',
                 'LINODE',
                 'OPENSTACK',
                 'RACKSPACE')
    for opt in optskeys:
        for provider in providers:
            if opt.startswith(provider):
                if provider.lower() not in opts:
                    opts[provider.lower()] = {}
                comps = opt.split('.')
                opts[provider.lower()][comps[1]] = opts[opt]
    return opts


def prov_dict(opts):
    providers = ('AWS',
                 'GOGRID',
                 'IBMSCE',
                 'JOYENT',
                 'LINODE',
                 'OPENSTACK',
                 'RACKSPACE')
    optskeys = opts.keys()
    opts['providers'] = {}
    for provider in providers:
        lprov = provider.lower()
        opts['providers'][lprov] = {}
        for opt in optskeys:
            if opt == lprov:
                opts['providers'][lprov][lprov] = opts[opt]
            elif type(opts[opt]) is dict and 'provider' in opts[opt]:
                if opts[opt]['provider'] == lprov:
                    opts['providers'][lprov][opt] = opts[opt]
    return opts


def vm_config(path):
    '''
    Read in the salt cloud VM config file
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
