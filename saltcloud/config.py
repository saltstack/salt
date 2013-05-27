'''
Manage configuration files in salt-cloud
'''

# Import python libs
import os
import logging

# Import salt libs
import salt.config
import salt.utils

# Import salt cloud libs
import saltcloud.exceptions


CLOUD_CONFIG_DEFAULTS = {
    'verify_env': True,
    'default_include': 'cloud.conf.d/*.conf',
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

    # If the user defined providers in salt cloud's main configuration file, we
    # need to take care for proper and expected format.
    if 'providers' in opts:
        for alias, details in opts.copy()['providers'].items():
            if isinstance(details, dict):
                opts['providers'][alias] = [details]

    # Migrate old configuration
    opts = old_to_new(opts)

    return opts


def old_to_new(opts):
    providers = (
        'AWS',
        'DIGITAL_OCEAN',
        'EC2',
        'GOGRID',
        'IBMSCE',
        'JOYENT',
        'LINODE',
        'OPENSTACK',
        'PARALLELS'
        'RACKSPACE',
        'SALTIFY'
    )

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

    vms = {}

    for key, val in opts.items():
        if key in ('conf_file', 'include', 'default_include'):
            continue
        if not isinstance(val, dict):
            raise saltcloud.exceptions.SaltCloudConfigError(
                'The VM profiles configuration found in {0[conf_file]!r} is '
                'not in the proper format'.format(opts)
            )
        val['profile'] = key
        vms[key] = val

    # Is any VM profile extending data!?
    for profile, details in vms.copy().items():
        if 'extends' not in details:
            continue

        extends = details.pop('extends')
        if extends not in vms:
            log.error(
                'The {0!r} profile is trying to extend data from {1!r} '
                'though {1!r} is not defined in the salt profiles loaded '
                'data. Not extending!'.format(
                    profile, extends
                )
            )
            continue

        extended = vms.get(extends).copy()
        extended.pop('profile')
        extended.update(details)

        # Update the profile's entry with the extended data
        vms[profile] = extended

    return vms.values()


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
    '''
    Apply the loaded cloud providers configuration.
    '''
    if defaults is None:
        defaults = PROVIDER_CONFIG_DEFAULTS

    opts = defaults.copy()
    if overrides:
        opts.update(overrides)

    # Is the user still using the old format in the new configuration file?!
    for name, config in opts.copy().items():
        if '.' in name:
            log.warn(
                'Please switch to the new providers configuration syntax'
            )

            # Let's help out and migrate the data
            opts = old_to_new(opts)

            # old_to_new will migrate the old data into the 'providers' key of
            # the opts dictionary. Let's map it correctly
            for name, config in opts.pop('providers').items():
                opts[name] = config

            break

    providers = {}

    for key, val in opts.items():
        if key in ('conf_file', 'include', 'default_include'):
            continue

        if not isinstance(val, (list, tuple)):
            val = [val]
        else:
            # Need to check for duplicate cloud provider entries per "alias" or
            # we won't be able to properly reference it.
            handled_providers = set()
            for details in val:
                if 'provider' not in details:
                    if 'extends' not in details:
                        log.error(
                            'Please check your cloud providers configuration. '
                            'There\'s no \'provider\' nor \'extends\' '
                            'definition. So it\'s pretty useless.'
                        )
                    continue
                if details['provider'] in handled_providers:
                    log.error(
                        'You can only have one entry per cloud provider. For '
                        'example, if you have a cloud provider configuration '
                        'section named, \'production\', you can only have a '
                        'single entry for EC2, Joyent, Openstack, and so '
                        'forth.'
                    )
                    raise saltcloud.exceptions.SaltCloudConfigError(
                        'The cloud provider alias {0!r} has multiple entries '
                        'for the {1[provider]!r} driver.'.format(key, details)
                    )
                handled_providers.add(
                    details['provider']
                )

        providers[key] = val

    # Is any provider extending data!?
    for provider_alias, entries in providers.copy().items():

        for idx, details in enumerate(entries):
            if 'extends' not in details:
                continue

            extends = details.pop('extends')

            if ':' in extends:
                alias, provider = extends.split(':')
                if alias not in providers:
                    log.error(
                        'The {0!r} cloud provider entry in {1!r} is trying '
                        'to extend data from {2!r} though {2!r} is not '
                        'defined in the salt cloud providers loaded '
                        'data.'.format(
                            details['provider'],
                            provider_alias,
                            alias
                        )
                    )
                    continue

                for entry in providers.get(alias):
                    if entry['provider'] == provider:
                        extended = entry.copy()
                        break
                else:
                    log.error(
                        'The {0!r} cloud provider entry in {1!r} is trying '
                        'to extend data from \'{2}:{3}\' though {3!r} is not '
                        'defined in {1!r}'.format(
                            details['provider'],
                            provider_alias,
                            alias,
                            provider
                        )
                    )
            elif providers.get(extends) and len(providers.get(extends)) > 1:
                log.error(
                    'The {0!r} cloud provider entry in {1!r} is trying to '
                    'extend from {2!r} which has multiple entries and no '
                    'provider is being specified. Not extending!'.format(
                        details['provider'], provider_alias, extends
                    )
                )
                continue
            elif extends not in providers:
                log.error(
                    'The {0!r} cloud provider entry in {1!r} is trying to '
                    'extend data from {2!r} though {2!r} is not defined in '
                    'the salt cloud providers loaded data.'.format(
                        details['provider'], provider_alias, extends
                    )
                )
                continue
            else:
                extended = providers.get(extends)[:][0]

            # Update the data to extend with the data to be extended
            extended.update(details)

            # Update the provider's entry with the extended data
            providers[provider_alias][idx] = extended

    return providers


def get_config_value(name, vm_, opts, default=None, search_global=True):
    '''
    Search and return a setting in a known order:

        1. In the virtual machines configuration
        2. In the virtual machine's provider configuration
        3. In the salt cloud configuration if global searching is enabled
        4. Return the provided default
    '''
    # As a last resort, return the default
    value = default

    if search_global is True and opts.get(name, None) is not None:
        # The setting name exists in the cloud(global) configuration
        value = opts[name]

    if vm_ and name:
        if ':' in vm_['provider']:
            # The provider is defined as <provider-alias>:<provider-name>
            alias, provider = vm_['provider'].split(':')
            if alias in opts['providers']:
                for entry in opts['providers'][alias]:
                    if entry['provider'] == provider:
                        if name in entry:
                            if type(value) is dict:
                                value.update(entry[name])
                            else:
                                value = entry[name]
                            break
        elif len(opts['providers'].get(vm_['provider'], ())) > 1:
            # The provider is NOT defined as <provider-alias>:<provider-name>
            # and there's more than one entry under the alias.
            # WARN the user!!!!
            log.error(
                'The {0!r} cloud provider definition has more than one '
                'entries. Your VM configuration should be specifying the '
                'provider as \'provider: {0}:<provider-engine>\'. Since '
                'it\'s not, we\'re returning the first definition which '
                'might not be what you intended.'.format(
                    vm_['provider']
                )
            )

        if name in opts['providers'].get(vm_['provider'], [{}])[0]:
            # The setting name exists in the VM's provider configuration.
            # Return it!
            if type(value) is dict:
                value.update(opts['providers'][vm_['provider']][0][name])
            else:
                value = opts['providers'][vm_['provider']][0][name]

    if name and vm_ and name in vm_:
        # The setting name exists in VM configuration.
        if type(value) is dict:
            value.update(vm_[name])
        else:
            value = vm_[name]

    return value


def is_provider_configured(opts, provider, required_keys=()):
    '''
    Check and return the first matching and fully configured cloud provider
    configuration.
    '''
    for provider_details_list in opts['providers'].values():
        for provider_details in provider_details_list:
            if 'provider' not in provider_details:
                continue

            if provider_details['provider'] != provider:
                continue

            # If we reached this far, we have a matching provider, let's see if
            # all required configuration keys are present and not None
            skip_provider = False
            for key in required_keys:
                if provider_details.get(key, None) is None:
                    # This provider does not include all necessary keys,
                    # continue to next one
                    skip_provider = True
                    break

            if skip_provider:
                continue

            # If we reached this far, the provider included all required keys
            return provider_details

    # If we reached this point, the provider is not configured.
    return False
