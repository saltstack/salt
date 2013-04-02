'''
Manage configuration files in salt-cloud
'''

# Import python libs
import os
import logging

# Import salt libs
import salt.config


CLOUD_CONFIG_DEFAULTS = {
    'verify_env': True,
    'default_include': 'cloud.conf.d/*.conf',
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
    # Custom deploy scripts
    'deploy_scripts_search_path': 'cloud.deploy.d',
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
    'default_include': 'cloud.profiles.d/*.conf',
}

PROVIDER_CONFIG_DEFAULTS = {
    'default_include': 'cloud.providers.d/*.conf',
}


log = logging.getLogger(__name__)


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
    overrides.update(
        salt.config.include_config(default_include, path, verbose=False)
    )
    include = overrides.get('include', [])
    overrides.update(
        salt.config.include_config(include, path, verbose=True)
    )

    # Prepare the deploy scripts search path
    deploy_scripts_search_path = overrides.get(
        'deploy_scripts_search_path',
        defaults.get('deploy_scripts_search_path', 'cloud.deploy.d')
    )
    if isinstance(deploy_scripts_search_path, basestring):
        deploy_scripts_search_path = [deploy_scripts_search_path]

    # Check the provided deploy scripts search path removing any non existing
    # entries.
    for idx, entry in enumerate(deploy_scripts_search_path[:]):
        if not os.path.isabs(entry):
            # Let's try if adding the provided path's directory name turns the
            # entry into a proper directory
            entry = os.path.join(os.path.dirname(path), entry)

        if os.path.isdir(entry):
            # Path exists, let's update the entry(it's path might have been
            # made absolute)
            deploy_scripts_search_path[idx] = entry
            continue

        # It's not a directory? Remove it from the search path
        deploy_scripts_search_path.pop(idx)

    # Add the provided scripts directory to the search path
    deploy_scripts_search_path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), 'deploy'))
    )

    # Let's make the search path a tuple and add it to the overrides.
    overrides.update(
        deploy_scripts_search_path=tuple(deploy_scripts_search_path)
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

    return opts


def old_to_new(opts):
    providers = ('AWS',
                 'EC2',
                 'GOGRID',
                 'IBMSCE',
                 'JOYENT',
                 'LINODE',
                 'OPENSTACK',
                 'RACKSPACE')

    for provider in providers:

        provider_config = {}
        for opt in opts.keys():
            if not opt.startswith(provider):
                continue
            value = opts.pop(opt)
            name = opt.split('.', 1)[1]
            provider_config[name] = value

        if provider_config:
            provider_config['provider'] = provider.lower()
            opts.setdefault('providers', {}).setdefault(
                provider.lower(), []).append(
                    provider_config
                )

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


def cloud_providers_config(path,
                           env_var='SALT_CLOUD_PROVIDERS_CONFIG',
                           defaults=None):
    '''
    Read in the salt cloud providers configuration file
    '''
    if defaults is None:
        defaults = PROVIDER_CONFIG_DEFAULTS

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
    return apply_cloud_providers_config(overrides, defaults)


def apply_cloud_providers_config(overrides, defaults=None):
    if defaults is None:
        defaults = PROVIDER_CONFIG_DEFAULTS

    opts = defaults.copy()
    if overrides:
        opts.update(overrides)

    # Is the user still using the old format in the new configuration file?!
    converted_opts = old_to_new(opts.copy())
    if opts != converted_opts:
        log.warn('Please switch to the new providers configuration syntax')
        opts = converted_opts

    providers = {}

    for key, val in opts.items():
        if key in ('conf_file', 'include', 'default_include'):
            continue
        providers[key] = val

    return providers


def get_config_value(name, vm_, opts, default=None):
    '''
    Search and return a setting in a known order:

        1. In the virtual machines configuration
        2. In the virtual machine's provider configuration
        3. In the salt cloud configuration
        4. Return the provided default
    '''
    if name in vm_:
        # The setting name exists in VM configuration. Return it!
        return vm_[name]

    if name in opts['providers'][vm_['provider']]:
        # The setting name exists in the VM's provider configuration.
        # Return it!
        return opts['providers'][vm_['provider']][name]

    if name in opts:
        # The setting name exists in the cloud(global) configuration
        return opts[name]

    # As a last resort, return the default
    return default
