'''
Manage configuration files in salt-cloud
'''

# Import python libs
import os
import glob
import logging

# Import salt libs
import salt.config
import salt.utils

# Import salt cloud libs
import saltcloud.output
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


def cloud_config(path, env_var='SALT_CLOUD_CONFIG', defaults=None,
                 master_config_path=None, master_config=None,
                 providers_config_path=None, providers_config=None,
                 vm_config_path=None, vm_config=None):
    '''
    Read in the salt cloud config and return the dict
    '''
    # Load the cloud configuration
    try:
        overrides = salt.config.load_config(path, env_var, '/etc/salt/cloud')
    except TypeError:
        log.warning(
            'Salt version is lower than 0.16.0, as such, loading '
            'configuration from the {0!r} environment variable will '
            'fail'.format(env_var)
        )
        overrides = salt.config.load_config(path, env_var)

    if defaults is None:
        defaults = CLOUD_CONFIG_DEFAULTS

    # Load cloud configuration from any default or provided includes
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

    # Grab data from the 4 sources
    # 1st - Master config
    if master_config_path is not None and master_config is not None:
        raise saltcloud.exceptions.SaltCloudConfigError(
            'Only pass `master_config` or `master_config_path`, not both.'
        )
    elif master_config_path is None and master_config is None:
        master_config = salt.config.master_config(
            overrides.get(
                # use the value from the cloud config file
                'master_config',
                # if not found, use the default path
                '/etc/salt/master'
            )
        )
    elif master_config_path is not None and master_config is None:
        master_config = salt.config.master_config(master_config_path)

    # Let's register our double-layer outputter into salt's outputters
    master_config['outputter_dirs'].append(
        os.path.dirname(saltcloud.output.__file__)
    )

    # 2nd - salt-cloud configuration which was loaded before so we could
    # extract the master configuration file if needed.

    # Override master configuration with the salt cloud(current overrides)
    master_config.update(overrides)
    # We now set the overridden master_config as the overrides
    overrides = master_config

    if providers_config_path is not None and providers_config is not None:
        raise saltcloud.exceptions.SaltCloudConfigError(
            'Only pass `providers_config` or `providers_config_path`, '
            'not both.'
        )
    elif providers_config_path is None and providers_config is None:
        providers_config_path = overrides.get(
            # use the value from the cloud config file
            'providers_config',
            # if not found, use the default path
            '/etc/salt/cloud.providers'
        )

    if vm_config_path is not None and vm_config is not None:
        raise saltcloud.exceptions.SaltCloudConfigError(
            'Only pass `vm_config` or `vm_config_path`, not both.'
        )
    elif vm_config_path is None and vm_config is None:
        vm_config_path = overrides.get(
            # use the value from the cloud config file
            'vm_config',
            # if not found, use the default path
            '/etc/salt/cloud.profiles'
        )

    # Apply the salt-cloud configuration
    opts = apply_cloud_config(overrides, defaults)

    # 3rd - Include Cloud Providers
    if 'providers' in opts:
        if providers_config is not None:
            raise saltcloud.exceptions.SaltCloudConfigError(
                'Do not mix the old cloud providers configuration with '
                'the passing a pre-configured providers configuration '
                'dictionary.'
            )

        if providers_config_path is not None:
            providers_confd = os.path.join(
                os.path.dirname(providers_config_path),
                'cloud.providers.d', '*'
            )

            if os.path.isfile(providers_config_path) or \
                    glob.glob(providers_confd):
                raise saltcloud.exceptions.SaltCloudConfigError(
                    'Do not mix the old cloud providers configuration with '
                    'the new one. The providers configuration should now go '
                    'in the file `/etc/salt/cloud.providers` or a separate '
                    '`*.conf` file within `cloud.providers.d/` which is '
                    'relative to `/etc/salt/cloud.providers`.'
                )
        # No exception was raised? It's the old configuration alone
        providers_config = opts['providers']

    elif providers_config_path is not None:
        # Load from configuration file, even if that files does not exist since
        # it will be populated with defaults.
        providers_config = cloud_providers_config(providers_config_path)

    # Let's assign back the computed providers configuration
    opts['providers'] = providers_config

    # 4th - Include VM profiles config
    if vm_config is None:
        # Load profiles configuration from the provided file
        vm_config = vm_profiles_config(vm_config_path, providers_config)
    opts['profiles'] = vm_config

    # Return the final options
    return opts


def apply_cloud_config(overrides, defaults=None):
    if defaults is None:
        defaults = CLOUD_CONFIG_DEFAULTS

    config = defaults.copy()
    if overrides:
        config.update(overrides)

    # If the user defined providers in salt cloud's main configuration file, we
    # need to take care for proper and expected format.
    if 'providers' in config:
        # Keep a copy of the defined providers
        providers = config['providers'].copy()
        # Reset the providers dictionary
        config['providers'] = {}
        # Populate the providers dictionary
        for alias, details in providers.items():
            if isinstance(details, list):
                for detail in details:
                    if 'provider' not in detail:
                        raise saltcloud.exceptions.SaltCloudConfigError(
                            'The cloud provider alias {0!r} has an entry '
                            'missing the required setting \'provider\''.format(
                                alias
                            )
                        )

                    driver = detail['provider']
                    if ':' in driver:
                        # Weird, but...
                        alias, driver = driver.split(':')

                    if alias not in config['providers']:
                        config['providers'][alias] = {}

                    detail['provider'] = '{0}:{1}'.format(alias, driver)
                    config['providers'][alias][driver] = detail
            elif isinstance(details, dict):
                if 'provider' not in details:
                    raise saltcloud.exceptions.SaltCloudConfigError(
                        'The cloud provider alias {0!r} has an entry '
                        'missing the required setting \'provider\''.format(
                            alias
                        )
                    )
                driver = details['provider']
                if ':' in driver:
                    # Weird, but...
                    alias, driver = driver.split(':')
                if alias not in config['providers']:
                    config['providers'][alias] = {}

                details['provider'] = '{0}:{1}'.format(alias, driver)
                config['providers'][alias][driver] = details

    # Migrate old configuration
    config = old_to_new(config)

    return config


def old_to_new(opts):
    providers = (
        'AWS',
        'CLOUDSTACK',
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

        lprovider = provider.lower()
        if provider_config:
            provider_config['provider'] = lprovider
            opts.setdefault('providers', {})
            # provider alias
            opts['providers'][lprovider] = {}
            # provider alias, provider driver
            opts['providers'][lprovider][lprovider] = provider_config
    return opts


def vm_profiles_config(path,
                       providers,
                       env_var='SALT_CLOUDVM_CONFIG',
                       defaults=None):
    '''
    Read in the salt cloud VM config file
    '''
    if defaults is None:
        defaults = VM_CONFIG_DEFAULTS

    try:
        overrides = salt.config.load_config(
            path, env_var, '/etc/salt/cloud.profiles'
        )
    except TypeError:
        log.warning(
            'Salt version is lower than 0.16.0, as such, loading '
            'configuration from the {0!r} environment variable will '
            'fail'.format(env_var)
        )
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
    return apply_vm_profiles_config(providers, overrides, defaults)


def apply_vm_profiles_config(providers, overrides, defaults=None):
    if defaults is None:
        defaults = VM_CONFIG_DEFAULTS

    config = defaults.copy()
    if overrides:
        config.update(overrides)

    vms = {}

    for key, val in config.items():
        if key in ('conf_file', 'include', 'default_include'):
            continue
        if not isinstance(val, dict):
            raise saltcloud.exceptions.SaltCloudConfigError(
                'The VM profiles configuration found in {0[conf_file]!r} is '
                'not in the proper format'.format(config)
            )
        val['profile'] = key
        vms[key] = val

    # Is any VM profile extending data!?
    for profile, details in vms.copy().items():
        if 'extends' not in details:
            if ':' in details['provider']:
                alias, driver = details['provider'].split(':')
                if alias not in providers or driver not in providers[alias]:
                    log.warning(
                        'The profile {0!r} is defining {1[provider]!r} as the '
                        'provider. Since there\'s no valid configuration for '
                        'that provider, the profile will be removed from the '
                        'available listing'.format(profile, details)
                    )
                    vms.pop(profile)
                    continue

                if 'profiles' not in providers[alias][driver]:
                    providers[alias][driver]['profiles'] = {}
                providers[alias][driver]['profiles'][profile] = details

            if details['provider'] not in providers:
                log.warning(
                    'The profile {0!r} is defining {1[provider]!r} as the '
                    'provider. Since there\'s no valid configuration for '
                    'that provider, the profile will be removed from the '
                    'available listing'.format(profile, details)
                )
                vms.pop(profile)
                continue

            driver = providers[details['provider']].keys()[0]
            providers[details['provider']][driver].setdefault(
                'profiles', {}).update({profile: details})
            details['provider'] = '{0[provider]}:{1}'.format(details, driver)
            vms[profile] = details

            continue

        extends = details.pop('extends')
        if extends not in vms:
            log.error(
                'The {0!r} profile is trying to extend data from {1!r} '
                'though {1!r} is not defined in the salt profiles loaded '
                'data. Not extending and removing from listing!'.format(
                    profile, extends
                )
            )
            vms.pop(profile)
            continue

        extended = vms.get(extends).copy()
        extended.pop('profile')
        extended.update(details)

        if ':' not in extended['provider']:
            if extended['provider'] not in providers:
                log.warning(
                    'The profile {0!r} is defining {1[provider]!r} as the '
                    'provider. Since there\'s no valid configuration for '
                    'that provider, the profile will be removed from the '
                    'available listing'.format(profile, extended)
                )
                vms.pop(profile)
                continue

            driver = providers[extended['provider']].keys()[0]
            providers[extended['provider']][driver].setdefault(
                'profiles', {}).update({profile: extended})

            extended['provider'] = '{0[provider]}:{1}'.format(extended, driver)
        else:
            alias, driver = extended['provider'].split(':')
            if alias not in providers or driver not in providers[alias]:
                log.warning(
                    'The profile {0!r} is defining {1[provider]!r} as the '
                    'provider. Since there\'s no valid configuration for '
                    'that provider, the profile will be removed from the '
                    'available listing'.format(profile, extended)
                )
                vms.pop(profile)
                continue

            providers[alias][driver].setdefault('profiles', {}).update(
                {profile: extended}
            )

        # Update the profile's entry with the extended data
        vms[profile] = extended

    return vms


def cloud_providers_config(path,
                           env_var='SALT_CLOUD_PROVIDERS_CONFIG',
                           defaults=None):
    '''
    Read in the salt cloud providers configuration file
    '''
    if defaults is None:
        defaults = PROVIDER_CONFIG_DEFAULTS

    try:
        overrides = salt.config.load_config(
            path, env_var, '/etc/salt/cloud.providers'
        )
    except TypeError:
        log.warning(
            'Salt version is lower than 0.16.0, as such, loading '
            'configuration from the {0!r} environment variable will '
            'fail'.format(env_var)
        )
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

    config = defaults.copy()
    if overrides:
        config.update(overrides)

    # Is the user still using the old format in the new configuration file?!
    for name, settings in config.copy().items():
        if '.' in name:
            log.warn(
                'Please switch to the new providers configuration syntax'
            )

            # Let's help out and migrate the data
            config = old_to_new(config)

            # old_to_new will migrate the old data into the 'providers' key of
            # the config dictionary. Let's map it correctly
            for prov_name, prov_settings in config.pop('providers').items():
                config[prov_name] = prov_settings
            break

    providers = {}
    for key, val in config.items():
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
                handled_providers.add(details['provider'])

        for entry in val:
            if 'provider' not in entry:
                entry['provider'] = '-only-extendable-'

            if key not in providers:
                providers[key] = {}

            provider = entry['provider']
            if provider in providers[key] and provider == '-only-extendable-':
                raise saltcloud.exceptions.SaltCloudConfigError(
                    'There\'s multiple entries under {0!r} which do not set '
                    'a provider setting. This is most likely just a holder '
                    'for data to be extended from, however, there can be '
                    'only one entry which does not define it\'s \'provider\' '
                    'setting.'.format(key)
                )
            elif provider not in providers[key]:
                providers[key][provider] = entry

    # Is any provider extending data!?
    while True:
        keep_looping = False
        for provider_alias, entries in providers.copy().items():

            for driver, details in entries.iteritems():
                # Set a holder for the defined profiles
                providers[provider_alias][driver]['profiles'] = {}

                if 'extends' not in details:
                    continue

                extends = details.pop('extends')

                if ':' in extends:
                    alias, provider = extends.split(':')
                    if alias not in providers:
                        raise saltcloud.exceptions.SaltCloudConfigError(
                            'The {0!r} cloud provider entry in {1!r} is '
                            'trying to extend data from {2!r} though {2!r} '
                            'is not defined in the salt cloud providers '
                            'loaded data.'.format(
                                details['provider'],
                                provider_alias,
                                alias
                            )
                        )

                    if provider not in providers.get(alias):
                        raise saltcloud.exceptions.SaltCloudConfigError(
                            'The {0!r} cloud provider entry in {1!r} is '
                            'trying to extend data from \'{2}:{3}\' though '
                            '{3!r} is not defined in {1!r}'.format(
                                details['provider'],
                                provider_alias,
                                alias,
                                provider
                            )
                        )
                    details['extends'] = '{0}:{1}'.format(alias, provider)
                elif providers.get(extends) and len(providers[extends]) > 1:
                    raise saltcloud.exceptions.SaltCloudConfigError(
                        'The {0!r} cloud provider entry in {1!r} is trying '
                        'to extend from {2!r} which has multiple entries '
                        'and no provider is being specified. Not '
                        'extending!'.format(
                            details['provider'], provider_alias, extends
                        )
                    )
                elif extends not in providers:
                    raise saltcloud.exceptions.SaltCloudConfigError(
                        'The {0!r} cloud provider entry in {1!r} is trying '
                        'to extend data from {2!r} though {2!r} is not '
                        'defined in the salt cloud providers loaded '
                        'data.'.format(
                            details['provider'], provider_alias, extends
                        )
                    )
                else:
                    provider = providers.get(extends)
                    if driver in providers.get(extends):
                        details['extends'] = '{0}:{1}'.format(extends, driver)
                    elif '-only-extendable-' in providers.get(extends):
                        details['extends'] = '{0}:{1}'.format(
                            extends, '-only-extendable-'
                        )
                    else:
                        # We're still not aware of what we're trying to extend
                        # from. Let's try on next iteration
                        details['extends'] = extends
                        keep_looping = True
        if not keep_looping:
            break

    while True:
        # Merge provided extends
        keep_looping = False
        for alias, entries in providers.copy().items():
            for driver, details in entries.iteritems():

                if 'extends' not in details:
                    # Extends resolved or non existing, continue!
                    continue

                if 'extends' in details['extends']:
                    # Since there's a nested extends, resolve this one in the
                    # next iteration
                    keep_looping = True
                    continue

                # Let's get a reference to what we're supposed to extend
                extends = details.pop('extends')
                # Split the setting in (alias, driver)
                ext_alias, ext_driver = extends.split(':')
                # Grab a copy of what should be extended
                extended = providers.get(ext_alias).get(ext_driver).copy()
                # Merge the data to extend with the details
                extended.update(details)
                # Update the providers dictionary with the merged data
                providers[alias][driver] = extended

        if not keep_looping:
            break

    # Now clean up any providers entry that was just used to be a data tree to
    # extend from
    for provider_alias, entries in providers.copy().items():
        for driver, details in entries.copy().iteritems():
            if driver != '-only-extendable-':
                continue

            log.info(
                'There\'s at least one cloud driver details under the {0!r} '
                'cloud provider alias which does not have the required '
                '\'provider\' setting. Was probably just used as a holder '
                'for additional data. Removing it from the available '
                'providers listing'.format(
                    provider_alias
                )
            )
            providers[provider_alias].pop(driver)

        if not providers[provider_alias]:
            providers.pop(provider_alias)

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
            alias, driver = vm_['provider'].split(':')
            if alias in opts['providers'] and \
                    driver in opts['providers'][alias]:
                details = opts['providers'][alias][driver]
                if name in details:
                    if isinstance(value, dict):
                        value.update(details[name].copy())
                    else:
                        value = details[name]
        elif len(opts['providers'].get(vm_['provider'], ())) > 1:
            # The provider is NOT defined as <provider-alias>:<provider-name>
            # and there's more than one entry under the alias.
            # WARN the user!!!!
            log.error(
                'The {0!r} cloud provider definition has more than one '
                'entry. Your VM configuration should be specifying the '
                'provider as \'provider: {0}:<provider-engine>\'. Since '
                'it\'s not, we\'re returning the first definition which '
                'might not be what you intended.'.format(
                    vm_['provider']
                )
            )

        if vm_['provider'] in opts['providers']:
            # There's only one driver defined for this provider. This is safe.
            alias_defs = opts['providers'].get(vm_['provider'])
            provider_driver_defs = alias_defs[alias_defs.keys()[0]]
            if name in provider_driver_defs:
                # The setting name exists in the VM's provider configuration.
                # Return it!
                if isinstance(value, dict):
                    value.update(provider_driver_defs[name].copy())
                else:
                    value = provider_driver_defs[name]

    if name and vm_ and name in vm_:
        # The setting name exists in VM configuration.
        if isinstance(value, dict):
            value.update(vm_[name])
        else:
            value = vm_[name]

    return value


def is_provider_configured(opts, provider, required_keys=()):
    '''
    Check and return the first matching and fully configured cloud provider
    configuration.
    '''
    if ':' in provider:
        alias, driver = provider.split(':')
        if alias not in opts['providers']:
            return False
        if driver not in opts['providers'][alias]:
            return False
        for key in required_keys:
            if opts['providers'][alias][driver].get(key, None) is None:
                # There's at least one require configuration key which is not
                # set.
                log.warn(
                    'The required {0!r} configuration setting is missing on '
                    'the {1!r} driver(under the {2!r} alias)'.format(
                        key, provider, alias
                    )
                )
                return False
        # If we reached this far, there's a properly configured provider,
        # return it!
        return opts['providers'][alias][driver]

    for alias, drivers in opts['providers'].iteritems():
        for driver, provider_details in drivers.iteritems():
            if driver != provider:
                continue

            # If we reached this far, we have a matching provider, let's see if
            # all required configuration keys are present and not None
            skip_provider = False
            for key in required_keys:
                if provider_details.get(key, None) is None:
                    # This provider does not include all necessary keys,
                    # continue to next one
                    log.warn(
                        'The required {0!r} configuration setting is missing '
                        'on the {1!r} driver(under the {2!r} alias)'.format(
                            key, provider, alias
                        )
                    )
                    skip_provider = True
                    break

            if skip_provider:
                continue

            # If we reached this far, the provider included all required keys
            return provider_details

    # If we reached this point, the provider is not configured.
    return False
