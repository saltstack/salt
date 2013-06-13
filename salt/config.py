'''
All salt configuration loading and defaults should be in this module
'''

# Import python libs
import glob
import os
import re
import socket
import logging
import urlparse

# import third party libs
import yaml
try:
    yaml.Loader = yaml.CLoader
    yaml.Dumper = yaml.CDumper
except Exception:
    pass

# Import salt libs
import salt.crypt
import salt.loader
import salt.utils
import salt.utils.network
import salt.pillar

log = logging.getLogger(__name__)

_DFLT_LOG_DATEFMT = '%H:%M:%S'
_DFLT_LOG_DATEFMT_LOGFILE = '%Y-%m-%d %H:%M:%S'
_DFLT_LOG_FMT_CONSOLE = '[%(levelname)-8s] %(message)s'
_DFLT_LOG_FMT_LOGFILE = (
    '%(asctime)s,%(msecs)03.0f [%(name)-17s][%(levelname)-8s] %(message)s'
)

VALID_OPTS = {
    'master': str,
    'master_port': int,
    'master_finger': str,
    'user': str,
    'root_dir': str,
    'pki_dir': str,
    'id': str,
    'cachedir': str,
    'cache_jobs': bool,
    'conf_file': str,
    'sock_dir': str,
    'backup_mode': str,
    'renderer': str,
    'failhard': bool,
    'autoload_dynamic_modules': bool,
    'environment': str,
    'state_top': str,
    'startup_states': str,
    'sls_list': list,
    'top_file': str,
    'file_client': str,
    'file_roots': dict,
    'pillar_roots': dict,
    'hash_type': str,
    'external_nodes': str,
    'disable_modules': list,
    'disable_returners': list,
    'whitelist_modules': list,
    'module_dirs': list,
    'returner_dirs': list,
    'states_dirs': list,
    'render_dirs': list,
    'outputter_dirs': list,
    'providers': dict,
    'clean_dynamic_modules': bool,
    'open_mode': bool,
    'multiprocessing': bool,
    'mine_interval': int,
    'ipc_mode': str,
    'ipv6': bool,
    'file_buffer_size': int,
    'tcp_pub_port': int,
    'tcp_pull_port': int,
    'log_file': str,
    'log_level': bool,
    'log_level_logfile': bool,
    'log_datefmt': str,
    'log_datefmt_logfile': str,
    'log_fmt_console': str,
    'log_fmt_logfile': tuple,
    'log_granular_levels': dict,
    'test': bool,
    'cython_enable': bool,
    'state_verbose': bool,
    'state_output': str,
    'acceptance_wait_time': float,
    'loop_interval': float,
    'dns_check': bool,
    'verify_env': bool,
    'grains': dict,
    'permissive_pki_access': bool,
    'default_include': str,
    'update_url': bool,
    'update_restart_services': list,
    'retry_dns': float,
    'recon_max': float,
    'win_repo_cachefile': str,
    'pidfile': str,
    'range_server': str,
    'tcp_keepalive': bool,
    'tcp_keepalive_idle': float,
    'tcp_keepalive_cnt': float,
    'tcp_keepalive_intvl': float,
    'interface': str,
    'publish_port': int,
    'auth_mode': int,
    'worker_threads': int,
    'ret_port': int,
    'keep_jobs': int,
    'master_roots': dict,
    'gitfs_remotes': list,
    'ext_pillar': list,
    'pillar_version': int,
    'pillar_opts': bool,
    'peer': dict,
    'syndic_master': str,
    'runner_dirs': list,
    'client_acl': dict,
    'client_acl_blacklist': dict,
    'external_auth': dict,
    'token_expire': int,
    'file_ignore_regex': bool,
    'file_ignore_glob': bool,
    'fileserver_backend': list,
    'max_open_files': int,
    'auto_accept': bool,
    'master_tops': bool,
    'order_masters': bool,
    'job_cache': bool,
    'ext_job_cache': str,
    'master_ext_job_cache': str,
    'minion_data_cache': bool,
    'publish_session': int,
    'reactor': list,
    'serial': str,
    'search': str,
    'search_index_interval': int,
    'nodegroups': dict,
    'key_logfile': str,
    'win_repo': str,
    'win_repo_mastercachefile': str,
    'win_gitrepos': list,
}

# default configurations
DEFAULT_MINION_OPTS = {
    'master': 'salt',
    'master_port': '4506',
    'master_finger': '',
    'user': 'root',
    'root_dir': '/',
    'pki_dir': '/etc/salt/pki/minion',
    'id': None,
    'cachedir': '/var/cache/salt/minion',
    'cache_jobs': False,
    'conf_file': '/etc/salt/minion',
    'sock_dir': '/var/run/salt/minion',
    'backup_mode': '',
    'renderer': 'yaml_jinja',
    'failhard': False,
    'autoload_dynamic_modules': True,
    'environment': None,
    'state_top': 'top.sls',
    'startup_states': '',
    'sls_list': [],
    'top_file': '',
    'file_client': 'remote',
    'file_roots': {
        'base': ['/srv/salt'],
    },
    'pillar_roots': {
        'base': ['/srv/pillar'],
    },
    'hash_type': 'md5',
    'external_nodes': '',
    'disable_modules': [],
    'disable_returners': [],
    'whitelist_modules': [],
    'module_dirs': [],
    'returner_dirs': [],
    'states_dirs': [],
    'render_dirs': [],
    'outputter_dirs': [],
    'providers': {},
    'clean_dynamic_modules': True,
    'open_mode': False,
    'multiprocessing': True,
    'mine_interval': 60,
    'ipc_mode': 'ipc',
    'ipv6': False,
    'file_buffer_size': 262144,
    'tcp_pub_port': 4510,
    'tcp_pull_port': 4511,
    'log_file': '/var/log/salt/minion',
    'log_level': None,
    'log_level_logfile': None,
    'log_datefmt': _DFLT_LOG_DATEFMT,
    'log_datefmt_logfile': _DFLT_LOG_DATEFMT_LOGFILE,
    'log_fmt_console': _DFLT_LOG_FMT_CONSOLE,
    'log_fmt_logfile': _DFLT_LOG_FMT_LOGFILE,
    'log_granular_levels': {},
    'test': False,
    'cython_enable': False,
    'state_verbose': True,
    'state_output': 'full',
    'acceptance_wait_time': 10,
    'loop_interval': 1,
    'dns_check': True,
    'verify_env': True,
    'grains': {},
    'permissive_pki_access': False,
    'default_include': 'minion.d/*.conf',
    'update_url': False,
    'update_restart_services': [],
    'retry_dns': 30,
    'recon_max': 5000,
    'win_repo_cachefile': 'salt://win/repo/winrepo.p',
    'pidfile': '/var/run/salt-minion.pid',
    'range_server': 'range:80',
    'tcp_keepalive': True,
    'tcp_keepalive_idle': 300,
    'tcp_keepalive_cnt': -1,
    'tcp_keepalive_intvl': -1,
}

DEFAULT_MASTER_OPTS = {
    'interface': '0.0.0.0',
    'publish_port': '4505',
    'auth_mode': 1,
    'user': 'root',
    'worker_threads': 5,
    'sock_dir': '/var/run/salt/master',
    'ret_port': '4506',
    'timeout': 5,
    'keep_jobs': 24,
    'root_dir': '/',
    'pki_dir': '/etc/salt/pki/master',
    'cachedir': '/var/cache/salt/master',
    'file_roots': {
        'base': ['/srv/salt'],
    },
    'master_roots': {
        'base': ['/srv/salt-master'],
    },
    'pillar_roots': {
        'base': ['/srv/pillar'],
    },
    'gitfs_remotes': [],
    'ext_pillar': [],
    'pillar_version': 2,
    'pillar_opts': True,
    'peer': {},
    'syndic_master': '',
    'runner_dirs': [],
    'outputter_dirs': [],
    'client_acl': {},
    'client_acl_blacklist': {},
    'external_auth': {},
    'token_expire': 43200,
    'file_buffer_size': 1048576,
    'file_ignore_regex': None,
    'file_ignore_glob': None,
    'fileserver_backend': ['roots'],
    'max_open_files': 100000,
    'hash_type': 'md5',
    'conf_file': '/etc/salt/master',
    'open_mode': False,
    'auto_accept': False,
    'renderer': 'yaml_jinja',
    'failhard': False,
    'state_top': 'top.sls',
    'master_tops': {},
    'external_nodes': '',
    'order_masters': False,
    'job_cache': True,
    'ext_job_cache': '',
    'master_ext_job_cache': '',
    'minion_data_cache': True,
    'ipv6': False,
    'log_file': '/var/log/salt/master',
    'log_level': None,
    'log_level_logfile': None,
    'log_datefmt': _DFLT_LOG_DATEFMT,
    'log_datefmt_logfile': _DFLT_LOG_DATEFMT_LOGFILE,
    'log_fmt_console': _DFLT_LOG_FMT_CONSOLE,
    'log_fmt_logfile': _DFLT_LOG_FMT_LOGFILE,
    'log_granular_levels': {},
    'pidfile': '/var/run/salt-master.pid',
    'publish_session': 86400,
    'cluster_masters': [],
    'cluster_mode': 'paranoid',
    'range_server': 'range:80',
    'reactor': [],
    'serial': 'msgpack',
    'state_verbose': True,
    'state_output': 'full',
    'search': '',
    'search_index_interval': 3600,
    'loop_interval': 60,
    'nodegroups': {},
    'cython_enable': False,
    'key_logfile': '/var/log/salt/key',
    'verify_env': True,
    'permissive_pki_access': False,
    'default_include': 'master.d/*.conf',
    'win_repo': '/srv/salt/win/repo',
    'win_repo_mastercachefile': '/srv/salt/win/repo/winrepo.p',
    'win_gitrepos': ['https://github.com/saltstack/salt-winrepo.git'],
}


def _validate_file_roots(opts):
    '''
    If the file_roots option has a key that is None then we will error out,
    just replace it with an empty list
    '''
    if not isinstance(opts['file_roots'], dict):
        log.warning('The file_roots parameter is not properly formatted,'
                    ' using defaults')
        return {'base': ['/srv/salt']}
    for env, dirs in list(opts['file_roots'].items()):
        if not isinstance(dirs, list) and not isinstance(dirs, tuple):
            opts['file_roots'][env] = []
    return opts['file_roots']


def _validate_opts(opts):
    '''
    Check that all of the types of values passed into the config are
    of the right types
    '''
    errors = []
    err = ('Key {0} with value {1} has an invalid type of {2}, a {3} is '
           'required for this value')
    for key, val in opts.items():
        if key in VALID_OPTS:
            if isinstance(VALID_OPTS[key](), list):
                if isinstance(val, VALID_OPTS[key]):
                    continue
                else:
                    errors.append(err.format(key, val, type(val), 'list'))
            if isinstance(VALID_OPTS[key](), dict):
                if isinstance(val, VALID_OPTS[key]):
                    continue
                else:
                    errors.append(err.format(key, val, type(val), 'dict'))
            else:
                try:
                    VALID_OPTS[key](val)
                except ValueError:
                    errors.append(
                        err.format(key, val, type(val), VALID_OPTS[key])
                    )
    for error in errors:
        log.warning(error)
    if errors:
        return False
    return True


def _append_domain(opts):
    '''
    Append a domain to the existing id if it doesn't already exist
    '''
    # Domain already exists
    if opts['id'].endswith(opts['append_domain']):
        return opts['id']
    # Trailing dot should mean an FQDN that is terminated, leave it alone.
    if opts['id'].endswith('.'):
        return opts['id']
    return '{0[id]}.{0[append_domain]}'.format(opts)


def _read_conf_file(path):
    log.debug('Reading configuration from {0}'.format(path))
    with salt.utils.fopen(path, 'r') as conf_file:
        conf_opts = yaml.safe_load(conf_file.read()) or {}
        # allow using numeric ids: convert int to string
        if 'id' in conf_opts:
            conf_opts['id'] = str(conf_opts['id'])
        for key, value in conf_opts.copy().iteritems():
            if isinstance(value, unicode):
                # We do not want unicode settings
                conf_opts[key] = value.encode('utf-8')
        return conf_opts


def load_config(path, env_var):
    '''
    Returns configuration dict from parsing either the file described by
    ``path`` or the environment variable described by ``env_var`` as YAML.
    '''
    if path is None:
        # When the passed path is None, we just want the configuration
        # defaults, not actually loading the whole configuration.
        return {}

    if not path or not os.path.isfile(path):
        path = os.environ.get(env_var, path)
    # If the configuration file is missing, attempt to copy the template,
    # after removing the first header line.
    if not os.path.isfile(path):
        template = '{0}.template'.format(path)
        if os.path.isfile(template):
            import salt.utils  # TODO: Need to re-import, need to find out why
            log.debug('Writing {0} based on {1}'.format(path, template))
            with salt.utils.fopen(path, 'w') as out:
                with salt.utils.fopen(template, 'r') as ifile:
                    ifile.readline()  # skip first line
                    out.write(ifile.read())

    if os.path.isfile(path):
        try:
            opts = _read_conf_file(path)
            opts['conf_file'] = path
            return opts
        except Exception as err:
            import salt.log
            msg = 'Error parsing configuration file: {0} - {1}'
            if salt.log.is_console_configured():
                log.warn(msg.format(path, err))
            else:
                print(msg.format(path, err))
    else:
        log.debug('Missing configuration file: {0}'.format(path))

    return {}


def include_config(include, orig_path, verbose):
    '''
    Parses extra configuration file(s) specified in an include list in the
    main config file.
    '''
    # Protect against empty option
    if not include:
        return {}

    if orig_path is None:
        # When the passed path is None, we just want the configuration
        # defaults, not actually loading the whole configuration.
        return {}

    if isinstance(include, str):
        include = [include]

    configuration = {}
    for path in include:
        # Allow for includes like ~/foo
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(orig_path), path)

        # Catch situation where user typos path in configuration; also warns
        # for empty include directory (which might be by design)
        if len(glob.glob(path)) == 0:
            if verbose:
                log.warn(
                    'Warning parsing configuration file: "include" path/glob '
                    '"{0}" matches no files'.format(path)
                )

        for fn_ in sorted(glob.glob(path)):
            try:
                log.debug('Including configuration from {0}'.format(fn_))
                configuration.update(_read_conf_file(fn_))
            except Exception as err:
                log.warn(
                    'Error parsing configuration file: {0} - {1}'.format(
                        fn_, err
                    )
                )
    return configuration


def prepend_root_dir(opts, path_options):
    '''
    Prepends the options that represent filesystem paths with value of the
    'root_dir' option.
    '''
    root_dir = os.path.abspath(opts['root_dir'])
    for path_option in path_options:
        if path_option in opts:
            if opts[path_option].startswith(opts['root_dir']):
                opts[path_option] = opts[path_option][len(opts['root_dir']):]
            opts[path_option] = salt.utils.path_join(
                root_dir,
                opts[path_option]
            )


def minion_config(path,
                  env_var='SALT_MINION_CONFIG',
                  defaults=None,
                  **kwargs):
    '''
    Reads in the minion configuration file and sets up special options
    '''
    if defaults is None:
        defaults = DEFAULT_MINION_OPTS

    overrides = load_config(path, env_var)
    default_include = overrides.get('default_include',
                                    defaults['default_include'])
    include = overrides.get('include', [])

    overrides.update(include_config(default_include, path, verbose=False))
    overrides.update(include_config(include, path, verbose=True))

    opts = apply_minion_config(overrides, defaults)
    _validate_opts(opts)
    return opts


def get_id():
    '''
    Guess the id of the minion.

    - If socket.getfqdn() returns us something other than localhost, use it
    - Check /etc/hosts for something that isn't localhost that maps to 127.*
    - Look for a routeable / public IP
    - A private IP is better than a loopback IP
    - localhost may be better than killing the minion
    '''

    log.debug('Guessing ID. The id can be explicitly in set {0}'
              .format('/etc/salt/minion'))
    fqdn = socket.getfqdn()
    if 'localhost' != fqdn:
        log.info('Found minion id from getfqdn(): {0}'.format(fqdn))
        return fqdn, False

    # Can /etc/hosts help us?
    try:
        # TODO Add Windows host file support
        with open('/etc/hosts') as f:
            line = f.readline()
            while line:
                names = line.split()
                ip = names.pop(0)
                if ip.startswith('127.'):
                    for name in names:
                        if name != 'localhost':
                            log.info('Found minion id in hosts file: {0}'
                                     .format(name))
                            return name, False
                line = f.readline()
    except Exception:
        pass

    # What IP addresses do we have?
    ip_addresses = [salt.utils.network.IPv4Address(a) for a
                    in salt.utils.network.ip_addrs(include_loopback=True)
                    if not a.startswith('127.')]

    for a in ip_addresses:
        if not a.is_private:
            log.info('Using public ip address for id: {0}'.format(a))
            return str(a), True

    if ip_addresses:
        a = ip_addresses.pop(0)
        log.info('Using private ip address for id: {0}'.format(a))
        return str(a), True

    log.error('No id found, falling back to localhost')
    return 'localhost', False


def apply_minion_config(overrides=None, defaults=None, **kwargs):
    '''
    Returns minion configurations dict.
    '''
    if defaults is None:
        defaults = DEFAULT_MINION_OPTS

    opts = defaults.copy()
    if overrides:
        opts.update(overrides)

    if len(opts['sock_dir']) > len(opts['cachedir']) + 10:
        opts['sock_dir'] = os.path.join(opts['cachedir'], '.salt-unix')

    # No ID provided. Will getfqdn save us?
    using_ip_for_id = False
    if opts['id'] is None:
        opts['id'], using_ip_for_id = get_id()

    # it does not make sense to append a domain to an IP based id
    if not using_ip_for_id and 'append_domain' in opts:
        opts['id'] = _append_domain(opts)

    # Enabling open mode requires that the value be set to True, and
    # nothing else!
    opts['open_mode'] = opts['open_mode'] is True

    # set up the extension_modules location from the cachedir
    opts['extension_modules'] = (
        opts.get('extension_modules') or
        os.path.join(opts['cachedir'], 'extmods')
    )

    # Prepend root_dir to other paths
    prepend_root_dirs = [
        'pki_dir', 'cachedir', 'sock_dir', 'extension_modules', 'pidfile',
    ]

    # These can be set to syslog, so, not actual paths on the system
    for config_key in ('log_file', 'key_logfile'):
        if urlparse.urlparse(opts.get(config_key, '')).scheme == '':
            prepend_root_dirs.append(config_key)

    prepend_root_dir(opts, prepend_root_dirs)
    if '__mine_interval' not in opts.get('schedule', {}):
        if not 'schedule' in opts:
            opts['schedule'] = {}
        opts['schedule'].update({
            '__mine_interval':
            {
                'function': 'mine.update',
                'minutes': opts['mine_interval']
            }
        })
    return opts


def master_config(path, env_var='SALT_MASTER_CONFIG', defaults=None):
    '''
    Reads in the master configuration file and sets up default options
    '''
    if defaults is None:
        defaults = DEFAULT_MASTER_OPTS

    overrides = load_config(path, env_var)
    default_include = overrides.get('default_include',
                                    defaults['default_include'])
    include = overrides.get('include', [])

    overrides.update(include_config(default_include, path, verbose=False))
    overrides.update(include_config(include, path, verbose=True))
    opts = apply_master_config(overrides, defaults)
    _validate_opts(opts)
    # If 'nodegroups:' is uncommented in the master config file, and there are
    # no nodegroups defined, opts['nodegroups'] will be None. Fix this by
    # reverting this value to the default, as if 'nodegroups:' was commented
    # out or not present.
    if opts.get('nodegroups') is None:
        opts['nodegroups'] = DEFAULT_MASTER_OPTS.get('nodegroups', {})
    return opts


def apply_master_config(overrides=None, defaults=None):
    '''
    Returns master configurations dict.
    '''
    if defaults is None:
        defaults = DEFAULT_MASTER_OPTS

    opts = defaults.copy()
    if overrides:
        opts.update(overrides)

    if len(opts['sock_dir']) > len(opts['cachedir']) + 10:
        opts['sock_dir'] = os.path.join(opts['cachedir'], '.salt-unix')

    opts['aes'] = salt.crypt.Crypticle.generate_key_string()

    opts['extension_modules'] = (
        opts.get('extension_modules') or
        os.path.join(opts['cachedir'], 'extmods')
    )
    opts['token_dir'] = os.path.join(opts['cachedir'], 'tokens')

    # Prepend root_dir to other paths
    prepend_root_dirs = [
        'pki_dir', 'cachedir', 'pidfile', 'sock_dir', 'extension_modules',
        'autosign_file', 'token_dir'
    ]

    # These can be set to syslog, so, not actual paths on the system
    for config_key in ('log_file', 'key_logfile'):
        log_setting = opts.get(config_key, '')
        if log_setting is None:
            continue

        if urlparse.urlparse(log_setting).scheme == '':
            prepend_root_dirs.append(config_key)

    prepend_root_dir(opts, prepend_root_dirs)

    # Enabling open mode requires that the value be set to True, and
    # nothing else!
    opts['open_mode'] = opts['open_mode'] is True
    opts['auto_accept'] = opts['auto_accept'] is True
    opts['file_roots'] = _validate_file_roots(opts)

    if opts['file_ignore_regex']:
        # If file_ignore_regex was given, make sure it's wrapped in a list.
        # Only keep valid regex entries for improved performance later on.
        if isinstance(opts['file_ignore_regex'], str):
            ignore_regex = [opts['file_ignore_regex']]
        elif isinstance(opts['file_ignore_regex'], list):
            ignore_regex = opts['file_ignore_regex']

        opts['file_ignore_regex'] = []
        for regex in ignore_regex:
            try:
                # Can't store compiled regex itself in opts (breaks
                # serialization)
                re.compile(regex)
                opts['file_ignore_regex'].append(regex)
            except Exception:
                log.warning(
                    'Unable to parse file_ignore_regex. Skipping: {0}'.format(
                        regex
                    )
                )

    if opts['file_ignore_glob']:
        # If file_ignore_glob was given, make sure it's wrapped in a list.
        if isinstance(opts['file_ignore_glob'], str):
            opts['file_ignore_glob'] = [opts['file_ignore_glob']]

    # Let's make sure `worker_threads` does not drop bellow 3 which has proven
    # to make `salt.modules.publish` not work under the test-suite.
    if opts['worker_threads'] < 3 and opts.get('peer', None):
        log.warning(
            'The \'worker_threads\' setting on {0!r} cannot be lower than 3. '
            'Resetting it to the default value of 3.'.format(
                opts['conf_file']
            )
        )
        opts['worker_threads'] = 3
    return opts


def client_config(path, env_var='SALT_CLIENT_CONFIG', defaults=None):
    '''
    Load in the configuration data needed for the LocalClient. This function
    searches for client specific configurations and adds them to the data from
    the master configuration.
    '''
    if defaults is None:
        defaults = DEFAULT_MASTER_OPTS

    # Get the token file path from the provided defaults. If not found, specify
    # our own, sane, default
    opts = {
        'token_file': defaults.get(
            'token_file',
            os.path.expanduser('~/.salt_token')
        )
    }
    # Update options with the master configuration, either from the provided
    # path, salt's defaults or provided defaults
    opts.update(
        master_config(path, defaults=defaults)
    )
    # Update with the users salt dot file or with the environment variable
    opts.update(
        load_config(
            os.path.expanduser('~/.salt'), env_var
        )
    )
    # Make sure we have a proper and absolute path to the token file
    if 'token_file' in opts:
        opts['token_file'] = os.path.abspath(
            os.path.expanduser(
                opts['token_file']
            )
        )
    # If the token file exists, read and store the contained token
    if os.path.isfile(opts['token_file']):
        with salt.utils.fopen(opts['token_file']) as fp_:
            opts['token'] = fp_.read().strip()
    # Return the client options
    _validate_opts(opts)
    return opts
