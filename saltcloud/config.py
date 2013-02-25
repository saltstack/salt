'''
Manage configuration files in salt-cloud
'''

# Import salt libs
import salt.config


CLOUD_CONFIG_DEFAULTS = {
    'verify_env': True,
    'default_include': 'cloud.d/*.conf',
    # Provider defaults
    'provider': '',
    'location': '',
    # Global defaults
    'ssh_auth': '',
    'keysize': 4096,
    'os': '',
    'script': 'bootstrap-salt',
    'start_action': None,
    'enable_hard_maps': False,
    'delete_sshkeys': False,
    # Logging defaults
    'log_file': '/var/log/salt/cloud',
    'log_level': None,
    'log_level_logfile': None,
    'log_datefmt': salt.config._DFLT_LOG_DATEFMT,
    'log_datefmt_logfile': salt.config._DFLT_LOG_DATEFMT_LOGFILE,
    'log_fmt_console': salt.config._DFLT_LOG_FMT_CONSOLE,
    'log_fmt_logfile': salt.config._DFLT_LOG_FMT_LOGFILE,
    'log_granular_levels': {},
}

VM_CONFIG_DEFAULTS = {
    'default_include': 'profiles.d/*.conf',
}


def cloud_config(path, env_var='SALT_CLOUD_CONFIG', defaults=None):
    '''
    Read in the salt cloud config and return the dict
    '''
    if defaults is None:
        defaults = CLOUD_CONFIG_DEFAULTS

    overrides = salt.config.load_config(path, env_var)
    default_include = overrides.get(
        'default_include', defaults['default_include']
    )
    include = overrides.get('include', [])

    overrides.update(
        salt.config.include_config(default_include, path, verbose=False)
    )
    overrides.update(
        salt.config.include_config(include, path, verbose=True)
    )
    return apply_cloud_config(overrides, defaults)


def apply_cloud_config(overrides, defaults=None):
    if defaults is None:
        defaults = CLOUD_CONFIG_DEFAULTS

    opts = defaults.copy()
    if overrides:
        opts.update(overrides)

    # Migrate old configuration
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


def vm_profiles_config(path, env_var='SALT_CLOUDVM_CONFIG', defaults=None):
    '''
    Read in the salt cloud VM config file
    '''
    if defaults is None:
        defaults = VM_CONFIG_DEFAULTS

    overrides = salt.config.load_config(path, env_var)
    default_include = overrides.get(
        'default_include', defaults['default_include']
    )
    include = overrides.get('include', [])

    overrides.update(
        salt.config.include_config(default_include, path, verbose=False)
    )
    overrides.update(
        salt.config.include_config(include, path, verbose=True)
    )
    return apply_vm_profiles_config(overrides, defaults)


def apply_vm_profiles_config(overrides, defaults=None):
    if defaults is None:
        defaults = VM_CONFIG_DEFAULTS

    opts = defaults.copy()
    if overrides:
        opts.update(overrides)

    vms = []

    for key, val in opts.items():
        if key in ('conf_file', 'include', 'default_include'):
            continue
        val['profile'] = key
        vms.append(val)

    return vms
