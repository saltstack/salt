# -*- coding: utf-8 -*-
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
from copy import deepcopy

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
import salt.syspaths

# Import salt cloud libs
import salt.cloud.exceptions

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
    'state_auto_order': bool,
    'state_events': bool,
    'acceptance_wait_time': float,
    'acceptance_wait_time_max': float,
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
    'recon_default': float,
    'recon_randomize': float,
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
    'gitfs_root': str,
    'gitfs_base': str,
    'hgfs_remotes': list,
    'hgfs_root': str,
    'hgfs_branch_method': str,
    'svnfs_remotes': list,
    'svnfs_root': str,
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
    'file_recv': bool,
    'file_ignore_regex': bool,
    'file_ignore_glob': bool,
    'fileserver_backend': list,
    'fileserver_followsymlinks': bool,
    'fileserver_ignoresymlinks': bool,
    'fileserver_limit_traversal': bool,
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
    'modules_max_memory': int,
    'grains_refresh_every': int,
    'enable_lspci': bool,
    'syndic_wait': int,
    'jinja_lstrip_blocks': bool,
    'jinja_trim_blocks': bool,
    'minion_id_caching': bool,
    'sign_pub_messages': bool,
    'keysize': int,
    'salt_transport': str,
}

# default configurations
DEFAULT_MINION_OPTS = {
    'master': 'salt',
    'master_port': '4506',
    'master_finger': '',
    'user': 'root',
    'root_dir': salt.syspaths.ROOT_DIR,
    'pki_dir': os.path.join(salt.syspaths.CONFIG_DIR, 'pki', 'minion'),
    'id': None,
    'cachedir': os.path.join(salt.syspaths.CACHE_DIR, 'minion'),
    'cache_jobs': False,
    'conf_file': os.path.join(salt.syspaths.CONFIG_DIR, 'minion'),
    'sock_dir': os.path.join(salt.syspaths.SOCK_DIR, 'minion'),
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
        'base': [salt.syspaths.BASE_FILE_ROOTS_DIR],
    },
    'fileserver_limit_traversal': False,
    'pillar_roots': {
        'base': [salt.syspaths.BASE_PILLAR_ROOTS_DIR],
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
    'log_file': os.path.join(salt.syspaths.LOGS_DIR, 'minion'),
    'log_level': None,
    'log_level_logfile': None,
    'log_datefmt': _DFLT_LOG_DATEFMT,
    'log_datefmt_logfile': _DFLT_LOG_DATEFMT_LOGFILE,
    'log_fmt_console': _DFLT_LOG_FMT_CONSOLE,
    'log_fmt_logfile': _DFLT_LOG_FMT_LOGFILE,
    'log_granular_levels': {},
    'test': False,
    'ext_job_cache': '',
    'cython_enable': False,
    'state_verbose': True,
    'state_output': 'full',
    'state_auto_order': True,
    'state_events': True,
    'acceptance_wait_time': 10,
    'acceptance_wait_time_max': 0,
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
    'recon_default': 100,
    'recon_randomize': False,
    'win_repo_cachefile': 'salt://win/repo/winrepo.p',
    'pidfile': os.path.join(salt.syspaths.PIDFILE_DIR, 'salt-minion.pid'),
    'range_server': 'range:80',
    'tcp_keepalive': True,
    'tcp_keepalive_idle': 300,
    'tcp_keepalive_cnt': -1,
    'tcp_keepalive_intvl': -1,
    'modules_max_memory': -1,
    'grains_refresh_every': 0,
    'minion_id_caching': True,
    'keysize': 4096,
    'salt_transport': 'zeromq',
}

DEFAULT_MASTER_OPTS = {
    'interface': '0.0.0.0',
    'publish_port': '4505',
    'pub_hwm': 1000,
    'auth_mode': 1,
    'user': 'root',
    'worker_threads': 5,
    'sock_dir': os.path.join(salt.syspaths.SOCK_DIR, 'master'),
    'ret_port': '4506',
    'timeout': 5,
    'keep_jobs': 24,
    'root_dir': salt.syspaths.ROOT_DIR,
    'pki_dir': os.path.join(salt.syspaths.CONFIG_DIR, 'pki', 'master'),
    'cachedir': os.path.join(salt.syspaths.CACHE_DIR, 'master'),
    'file_roots': {
        'base': [salt.syspaths.BASE_FILE_ROOTS_DIR],
    },
    'master_roots': {
        'base': [salt.syspaths.BASE_MASTER_ROOTS_DIR],
    },
    'pillar_roots': {
        'base': [salt.syspaths.BASE_PILLAR_ROOTS_DIR],
    },
    'gitfs_remotes': [],
    'gitfs_root': '',
    'gitfs_base': 'master',
    'hgfs_remotes': [],
    'hgfs_root': '',
    'hgfs_branch_method': 'branches',
    'svnfs_remotes': [],
    'svnfs_root': '',
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
    'file_recv': False,
    'file_buffer_size': 1048576,
    'file_ignore_regex': None,
    'file_ignore_glob': None,
    'fileserver_backend': ['roots'],
    'fileserver_followsymlinks': True,
    'fileserver_ignoresymlinks': False,
    'fileserver_limit_traversal': False,
    'max_open_files': 100000,
    'hash_type': 'md5',
    'conf_file': os.path.join(salt.syspaths.CONFIG_DIR, 'master'),
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
    'enforce_mine_cache': False,
    'ipv6': False,
    'log_file': os.path.join(salt.syspaths.LOGS_DIR, 'master'),
    'log_level': None,
    'log_level_logfile': None,
    'log_datefmt': _DFLT_LOG_DATEFMT,
    'log_datefmt_logfile': _DFLT_LOG_DATEFMT_LOGFILE,
    'log_fmt_console': _DFLT_LOG_FMT_CONSOLE,
    'log_fmt_logfile': _DFLT_LOG_FMT_LOGFILE,
    'log_granular_levels': {},
    'pidfile': os.path.join(salt.syspaths.PIDFILE_DIR, 'salt-master.pid'),
    'publish_session': 86400,
    'cluster_masters': [],
    'cluster_mode': 'paranoid',
    'range_server': 'range:80',
    'reactor': [],
    'serial': 'msgpack',
    'state_verbose': True,
    'state_output': 'full',
    'state_auto_order': True,
    'state_events': True,
    'search': '',
    'search_index_interval': 3600,
    'loop_interval': 60,
    'nodegroups': {},
    'cython_enable': False,
    'enable_gpu_grains': False,
    # XXX: Remove 'key_logfile' support in 0.18.0
    'key_logfile': os.path.join(salt.syspaths.LOGS_DIR, 'key'),
    'verify_env': True,
    'permissive_pki_access': False,
    'default_include': 'master.d/*.conf',
    'win_repo': os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR, 'win', 'repo'),
    'win_repo_mastercachefile': os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR,
                                             'win', 'repo', 'winrepo.p'),
    'win_gitrepos': ['https://github.com/saltstack/salt-winrepo.git'],
    'syndic_wait': 1,
    'jinja_lstrip_blocks': False,
    'jinja_trim_blocks': False,
    'sign_pub_messages': False,
    'keysize': 4096,
    'salt_transport': 'zeromq',
}

# ----- Salt Cloud Configuration Defaults ----------------------------------->
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
    'log_file': os.path.join(salt.syspaths.LOGS_DIR, 'cloud'),
    'log_level': None,
    'log_level_logfile': None,
    'log_datefmt': _DFLT_LOG_DATEFMT,
    'log_datefmt_logfile': _DFLT_LOG_DATEFMT_LOGFILE,
    'log_fmt_console': _DFLT_LOG_FMT_CONSOLE,
    'log_fmt_logfile': _DFLT_LOG_FMT_LOGFILE,
    'log_granular_levels': {},
}

VM_CONFIG_DEFAULTS = {
    'default_include': 'cloud.profiles.d/*.conf',
}

PROVIDER_CONFIG_DEFAULTS = {
    'default_include': 'cloud.providers.d/*.conf',
}
# <---- Salt Cloud Configuration Defaults ------------------------------------


def _validate_file_roots(opts):
    '''
    If the file_roots option has a key that is None then we will error out,
    just replace it with an empty list
    '''
    if not isinstance(opts['file_roots'], dict):
        log.warning('The file_roots parameter is not properly formatted,'
                    ' using defaults')
        return {'base': [salt.syspaths.BASE_FILE_ROOTS_DIR]}
    for saltenv, dirs in list(opts['file_roots'].items()):
        if not isinstance(dirs, list) and not isinstance(dirs, tuple):
            opts['file_roots'][saltenv] = []
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
                except TypeError:
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
        try:
            conf_opts = yaml.safe_load(conf_file.read()) or {}
        except yaml.YAMLError as err:
            log.error(
                'Error parsing configuration file: {0} - {1}'.format(path, err)
            )
            conf_opts = {}
        # only interpret documents as a valid conf, not things like strings,
        # which might have been caused by invalid yaml syntax
        if not isinstance(conf_opts, dict):
            log.error(
                'Error parsing configuration file: {0} - conf should be a '
                'document, not {1}.'.format(path, type(conf_opts))
            )
            conf_opts = {}
        # allow using numeric ids: convert int to string
        if 'id' in conf_opts:
            conf_opts['id'] = str(conf_opts['id'])
        for key, value in conf_opts.copy().iteritems():
            if isinstance(value, unicode):
                # We do not want unicode settings
                conf_opts[key] = value.encode('utf-8')
        return conf_opts


def load_config(path, env_var, default_path=None):
    '''
    Returns configuration dict from parsing either the file described by
    ``path`` or the environment variable described by ``env_var`` as YAML.
    '''
    if path is None:
        # When the passed path is None, we just want the configuration
        # defaults, not actually loading the whole configuration.
        return {}

    if default_path is None:
        # This is most likely not being used from salt, ie, could be salt-cloud
        # or salt-api which have not yet migrated to the new default_path
        # argument. Let's issue a warning message that the environ vars won't
        # work.
        import inspect
        previous_frame = inspect.getframeinfo(inspect.currentframe().f_back)
        log.warning(
            'The function \'{0}()\' defined in {1!r} is not yet using the '
            'new \'default_path\' argument to `salt.config.load_config()`. '
            'As such, the {2!r} environment variable will be ignored'.format(
                previous_frame.function, previous_frame.filename, env_var
            )
        )
        # In this case, maintain old behaviour
        default_path = DEFAULT_MASTER_OPTS['conf_file']

    # Default to the environment variable path, if it exists
    env_path = os.environ.get(env_var, path)
    if not env_path or not os.path.isfile(env_path):
        env_path = path
    # If non-default path from `-c`, use that over the env variable
    if path != default_path:
        env_path = path

    path = env_path

    # If the configuration file is missing, attempt to copy the template,
    # after removing the first header line.
    if not os.path.isfile(path):
        template = '{0}.template'.format(path)
        if os.path.isfile(template):
            log.debug('Writing {0} based on {1}'.format(path, template))
            with salt.utils.fopen(path, 'w') as out:
                with salt.utils.fopen(template, 'r') as ifile:
                    ifile.readline()  # skip first line
                    out.write(ifile.read())

    if os.path.isfile(path):
        opts = _read_conf_file(path)
        opts['conf_file'] = path
        return opts

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
                    '{0!r} matches no files'.format(path)
                )

        for fn_ in sorted(glob.glob(path)):
            log.debug('Including configuration from {0!r}'.format(fn_))
            configuration.update(_read_conf_file(fn_))
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
                  check_dns=None,
                  minion_id=False):
    '''
    Reads in the minion configuration file and sets up special options
    '''
    if check_dns is not None:
        # All use of the `check_dns` arg was removed in `598d715`. The keyword
        # argument was then removed in `9d893e4` and `**kwargs` was then added
        # in `5d60f77` in order not to break backwards compatibility.
        #
        # Showing a deprecation for 0.17.0 and 0.18.0 should be enough for any
        # api calls to be updated in order to stop it's use.
        salt.utils.warn_until(
            'Helium',
            'The functionality behind the \'check_dns\' keyword argument is '
            'no longer required, as such, it became unnecessary and is now '
            'deprecated. \'check_dns\' will be removed in Salt {version}.'
        )
    if defaults is None:
        defaults = DEFAULT_MINION_OPTS

    if not os.environ.get(env_var, None):
        # No valid setting was given using the configuration variable.
        # Lets see is SALT_CONFIG_DIR is of any use
        salt_config_dir = os.environ.get('SALT_CONFIG_DIR', None)
        if salt_config_dir:
            env_config_file_path = os.path.join(salt_config_dir, 'minion')
            if salt_config_dir and os.path.isfile(env_config_file_path):
                # We can get a configuration file using SALT_CONFIG_DIR, let's
                # update the environment with this information
                os.environ[env_var] = env_config_file_path

    overrides = load_config(path, env_var, DEFAULT_MINION_OPTS['conf_file'])
    default_include = overrides.get('default_include',
                                    defaults['default_include'])
    include = overrides.get('include', [])

    overrides.update(include_config(default_include, path, verbose=False))
    overrides.update(include_config(include, path, verbose=True))

    opts = apply_minion_config(overrides, defaults, minion_id=minion_id)
    _validate_opts(opts)
    return opts


def syndic_config(master_config_path,
                  minion_config_path,
                  master_env_var='SALT_MASTER_CONFIG',
                  minion_env_var='SALT_MINION_CONFIG',
                  minion_defaults=None,
                  master_defaults=None):

    if minion_defaults is None:
        minion_defaults = DEFAULT_MINION_OPTS

    if master_defaults is None:
        master_defaults = DEFAULT_MASTER_OPTS

    opts = {}
    master_opts = master_config(
        master_config_path, master_env_var, master_defaults
    )
    minion_opts = minion_config(
        minion_config_path, minion_env_var, minion_defaults
    )
    opts['_minion_conf_file'] = master_opts['conf_file']
    opts['_master_conf_file'] = minion_opts['conf_file']
    opts.update(master_opts)
    opts.update(minion_opts)
    syndic_opts = {
        'root_dir': opts.get('root_dir', salt.syspaths.ROOT_DIR),
        'pidfile': opts.get('syndic_pidfile', 'salt-syndic.pid'),
        'log_file': opts.get('syndic_log_file', 'salt-syndic.log'),
        'id': minion_opts['id'],
        'pki_dir': minion_opts['pki_dir'],
        'master': opts['syndic_master'],
        'master_port': int(
            opts.get(
                # The user has explicitly defined the syndic master port
                'syndic_master_port',
                opts.get(
                    # No syndic_master_port, grab master_port from opts
                    'master_port',
                    # No master_opts, grab from the provided minion defaults
                    minion_defaults.get(
                        'master_port',
                        # Not on the provided minion defaults, load from the
                        # static minion defaults
                        DEFAULT_MINION_OPTS['master_port']
                    )
                )
            )
        ),
        'user': opts.get('syndic_user', opts['user']),
        'sock_dir': os.path.join(
            opts['cachedir'], opts.get('syndic_sock_dir', opts['sock_dir'])
        ),
    }
    opts.update(syndic_opts)
    # Prepend root_dir to other paths
    prepend_root_dirs = [
        'pki_dir', 'cachedir', 'pidfile', 'sock_dir', 'extension_modules',
        'autosign_file', 'autoreject_file', 'token_dir'
    ]
    for config_key in ('log_file', 'key_logfile'):
        if urlparse.urlparse(opts.get(config_key, '')).scheme == '':
            prepend_root_dirs.append(config_key)
    prepend_root_dir(opts, prepend_root_dirs)
    return opts


# ----- Salt Cloud Configuration Functions ---------------------------------->
def cloud_config(path, env_var='SALT_CLOUD_CONFIG', defaults=None,
                 master_config_path=None, master_config=None,
                 providers_config_path=None, providers_config=None,
                 vm_config_path=None, vm_config=None,
                 profiles_config_path=None, profiles_config=None):
    '''
    Read in the salt cloud config and return the dict
    '''
    if vm_config and profiles_config:
        # This is a bad API usage
        raise RuntimeError(
            '`vm_config` and `profiles_config` are mutually exclusive and '
            '`vm_config` is being deprecated in favor of `profiles_config`.'
        )
    elif vm_config:
        salt.utils.warn_until(
            'Helium',
            'The support for `vm_config` has been deprecated and will be '
            'removed in Salt Helium. Please use `profiles_config`.'
        )
        profiles_config = vm_config
        vm_config = None
    if vm_config_path and profiles_config_path:
        # This is a bad API usage
        raise RuntimeError(
            '`vm_config_path` and `profiles_config_path` are mutually '
            'exclusive and `vm_config_path` is being deprecated in favor of '
            '`profiles_config_path`'
        )
    elif vm_config_path:
        salt.utils.warn_until(
            'Helium',
            'The support for `vm_config_path` has been deprecated and will be '
            'removed in Salt Helium. Please use `profiles_config_path`.'
        )
        profiles_config_path = vm_config_path
        vm_config_path = None

    # Load the cloud configuration
    overrides = salt.config.load_config(
        path,
        env_var,
        os.path.join(salt.syspaths.CONFIG_DIR, 'cloud')
    )

    if 'vm_config' in overrides and 'profiles_config' in overrides:
        raise salt.cloud.exceptions.SaltCloudConfigError(
            '`vm_config` and `profiles_config` are mutually exclusive and '
            '`vm_config` is being deprecated in favor of `profiles_config`.'
        )
    elif 'vm_config' in overrides:
        salt.utils.warn_until(
            'Helium',
            'The support for `vm_config` has been deprecated and will be '
            'removed in Salt Helium. Please use `profiles_config`.'
            'Please update the could configuration file(s).'

        )
        overrides['profiles_config'] = overrides.pop('vm_config')

    if path:
        config_dir = os.path.dirname(path)
    else:
        config_dir = salt.syspaths.CONFIG_DIR

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

    # The includes have been evaluated, let's see if master, providers and
    # profiles configuration settings have been included and if not, set the
    # default value
    if 'master_config' in overrides and master_config_path is None:
        # The configuration setting is being specified in the main cloud
        # configuration file
        master_config_path = overrides['master_config']
    elif 'master_config' not in overrides and not master_config \
                                                and not master_config_path:
        # The configuration setting is not being provided in the main cloud
        # configuration file, and
        master_config_path = os.path.join(config_dir, 'master')

    if 'providers_config' in overrides and providers_config_path is None:
        # The configuration setting is being specified in the main cloud
        # configuration file
        providers_config_path = overrides['providers_config']
    elif 'providers_config' not in overrides and not providers_config \
                                                and not providers_config_path:
        providers_config_path = os.path.join(config_dir, 'cloud.providers')

    if 'profiles_config' in overrides and profiles_config_path is None:
        # The configuration setting is being specified in the main cloud
        # configuration file
        profiles_config_path = overrides['profiles_config']
    elif 'profiles_config' not in overrides and not profiles_config \
            and not profiles_config_path:
        profiles_config_path = os.path.join(config_dir, 'cloud.profiles')

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

    # Add the built-in scripts directory to the search path(last resort)
    deploy_scripts_search_path.append(
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                'cloud',
                'deploy'
            )
        )
    )

    # Let's make the search path a tuple and add it to the overrides.
    overrides.update(
        deploy_scripts_search_path=tuple(deploy_scripts_search_path)
    )

    # Grab data from the 4 sources
    # 1st - Master config
    if master_config_path is not None and master_config is not None:
        raise salt.cloud.exceptions.SaltCloudConfigError(
            'Only pass `master_config` or `master_config_path`, not both.'
        )
    elif master_config_path is None and master_config is None:
        master_config = salt.config.master_config(
            overrides.get(
                # use the value from the cloud config file
                'master_config',
                # if not found, use the default path
                os.path.join(salt.syspaths.CONFIG_DIR, 'master')
            )
        )
    elif master_config_path is not None and master_config is None:
        master_config = salt.config.master_config(master_config_path)

    # 2nd - salt-cloud configuration which was loaded before so we could
    # extract the master configuration file if needed.

    # Override master configuration with the salt cloud(current overrides)
    master_config.update(overrides)
    # We now set the overridden master_config as the overrides
    overrides = master_config

    if providers_config_path is not None and providers_config is not None:
        raise salt.cloud.exceptions.SaltCloudConfigError(
            'Only pass `providers_config` or `providers_config_path`, '
            'not both.'
        )
    elif providers_config_path is None and providers_config is None:
        providers_config_path = overrides.get(
            # use the value from the cloud config file
            'providers_config',
            # if not found, use the default path
            os.path.join(salt.syspaths.CONFIG_DIR, 'cloud.providers')
        )

    if profiles_config_path is not None and profiles_config is not None:
        raise salt.cloud.exceptions.SaltCloudConfigError(
            'Only pass `profiles_config` or `profiles_config_path`, not both.'
        )
    elif profiles_config_path is None and profiles_config is None:
        profiles_config_path = overrides.get(
            # use the value from the cloud config file
            'profiles_config',
            # if not found, use the default path
            os.path.join(salt.syspaths.CONFIG_DIR, 'cloud.profiles')
        )

    # Apply the salt-cloud configuration
    opts = apply_cloud_config(overrides, defaults)

    # 3rd - Include Cloud Providers
    if 'providers' in opts:
        if providers_config is not None:
            raise salt.cloud.exceptions.SaltCloudConfigError(
                'Do not mix the old cloud providers configuration with '
                'the passing a pre-configured providers configuration '
                'dictionary.'
            )

        if providers_config_path is not None:
            providers_confd = os.path.join(
                os.path.dirname(providers_config_path),
                'cloud.providers.d', '*'
            )

            if (os.path.isfile(providers_config_path) or
                    glob.glob(providers_confd)):
                raise salt.cloud.exceptions.SaltCloudConfigError(
                    'Do not mix the old cloud providers configuration with '
                    'the new one. The providers configuration should now go '
                    'in the file `{0}` or a separate `*.conf` file within '
                    '`cloud.providers.d/` which is relative to `{0}`.'.format(
                        os.path.join(salt.syspaths.CONFIG_DIR, 'cloud.providers')
                    )
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
    if profiles_config is None:
        # Load profiles configuration from the provided file
        profiles_config = vm_profiles_config(profiles_config_path,
                                             providers_config)
    opts['profiles'] = profiles_config

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
                        raise salt.cloud.exceptions.SaltCloudConfigError(
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
                    raise salt.cloud.exceptions.SaltCloudConfigError(
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

    overrides = salt.config.load_config(
        path, env_var, os.path.join(salt.syspaths.CONFIG_DIR, 'cloud.profiles')
    )

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
            raise salt.cloud.exceptions.SaltCloudConfigError(
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

    overrides = salt.config.load_config(
        path, env_var, os.path.join(salt.syspaths.CONFIG_DIR, 'cloud.providers')
    )

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
                    raise salt.cloud.exceptions.SaltCloudConfigError(
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
                raise salt.cloud.exceptions.SaltCloudConfigError(
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
                        raise salt.cloud.exceptions.SaltCloudConfigError(
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
                        raise salt.cloud.exceptions.SaltCloudConfigError(
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
                    raise salt.cloud.exceptions.SaltCloudConfigError(
                        'The {0!r} cloud provider entry in {1!r} is trying '
                        'to extend from {2!r} which has multiple entries '
                        'and no provider is being specified. Not '
                        'extending!'.format(
                            details['provider'], provider_alias, extends
                        )
                    )
                elif extends not in providers:
                    raise salt.cloud.exceptions.SaltCloudConfigError(
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


def get_cloud_config_value(name, vm_, opts, default=None, search_global=True):
    '''
    Search and return a setting in a known order:

        1. In the virtual machine's configuration
        2. In the virtual machine's profile configuration
        3. In the virtual machine's provider configuration
        4. In the salt cloud configuration if global searching is enabled
        5. Return the provided default
    '''

    # As a last resort, return the default
    value = default

    if search_global is True and opts.get(name, None) is not None:
        # The setting name exists in the cloud(global) configuration
        value = deepcopy(opts[name])

    if vm_ and name:
        # Let's get the value from the profile, if present
        if 'profile' in vm_ and vm_['profile'] is not None:
            if name in opts['profiles'][vm_['profile']]:
                if isinstance(value, dict):
                    value.update(opts['profiles'][vm_['profile']][name].copy())
                else:
                    value = deepcopy(opts['profiles'][vm_['profile']][name])

        # Let's get the value from the provider, if present
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
                        value = deepcopy(details[name])
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
                    value = deepcopy(provider_driver_defs[name])

    if name and vm_ and name in vm_:
        # The setting name exists in VM configuration.
        if isinstance(value, dict):
            value.update(vm_[name].copy())
        else:
            value = deepcopy(vm_[name])

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
# <---- Salt Cloud Configuration Functions -----------------------------------


def _cache_id(minion_id, cache_file):
    '''
    Helper function, writes minion id to a cache file.
    '''
    try:
        with salt.utils.fopen(cache_file, 'w') as idf:
            idf.write(minion_id)
    except (IOError, OSError) as exc:
        log.error('Could not cache minion ID: {0}'.format(exc))


def get_id(root_dir=None, minion_id=False, cache=True):
    '''
    Guess the id of the minion.

    - If CONFIG_DIR/minion_id exists, use the cached minion ID from that file
    - If socket.getfqdn() returns us something other than localhost, use it
    - Check /etc/hostname for a value other than localhost
    - Check /etc/hosts for something that isn't localhost that maps to 127.*
    - Look for a routeable / public IP
    - A private IP is better than a loopback IP
    - localhost may be better than killing the minion

    Any non-ip id will be cached for later use in ``CONFIG_DIR/minion_id``

    Returns two values: the detected ID, and a boolean value noting whether or
    not an IP address is being used for the ID.
    '''
    if root_dir is None:
        root_dir = salt.syspaths.ROOT_DIR

    config_dir = salt.syspaths.CONFIG_DIR
    if config_dir.startswith(salt.syspaths.ROOT_DIR):
        config_dir = config_dir.split(salt.syspaths.ROOT_DIR, 1)[-1]

    # Check for cached minion ID
    id_cache = os.path.join(root_dir,
                            config_dir.lstrip('\\'),
                            'minion_id')

    if cache:
        try:
            with salt.utils.fopen(id_cache) as idf:
                name = idf.read().strip()
            if name:
                log.info('Using cached minion ID: {0}'.format(name))
                return name, False
        except (IOError, OSError):
            pass

    log.debug('Guessing ID. The id can be explicitly in set {0}'
              .format(os.path.join(salt.syspaths.CONFIG_DIR, 'minion')))

    # Check socket.getfqdn()
    fqdn = socket.getfqdn()
    if fqdn != 'localhost':
        log.info('Found minion id from getfqdn(): {0}'.format(fqdn))
        if minion_id and cache:
            _cache_id(fqdn, id_cache)
        return fqdn, False

    # Check /etc/hostname
    try:
        with salt.utils.fopen('/etc/hostname') as hfl:
            name = hfl.read().strip()
        if re.search(r'\s', name):
            log.warning('Whitespace character detected in /etc/hostname. '
                        'This file should not contain any whitespace.')
        else:
            if name != 'localhost':
                if minion_id and cache:
                    _cache_id(name, id_cache)
                return name, False
    except (IOError, OSError):
        pass

    # Can /etc/hosts help us?
    try:
        with salt.utils.fopen('/etc/hosts') as hfl:
            for line in hfl:
                names = line.split()
                ip_ = names.pop(0)
                if ip_.startswith('127.'):
                    for name in names:
                        if name != 'localhost':
                            log.info('Found minion id in hosts file: {0}'
                                     .format(name))
                            if minion_id and cache:
                                _cache_id(name, id_cache)
                            return name, False
    except (IOError, OSError):
        pass

    # Can Windows 'hosts' file help?
    try:
        windir = os.getenv('WINDIR')
        with salt.utils.fopen(windir + r'\system32\drivers\etc\hosts') as hfl:
            for line in hfl:
                # skip commented or blank lines
                if line[0] == '#' or len(line) <= 1:
                    continue
                # process lines looking for '127.' in first column
                try:
                    entry = line.split()
                    if entry[0].startswith('127.'):
                        for name in entry[1:]:  # try each name in the row
                            if name != 'localhost':
                                log.info('Found minion id in hosts file: {0}'
                                         .format(name))
                                if minion_id and cache:
                                    _cache_id(name, id_cache)
                                return name, False
                except IndexError:
                    pass  # could not split line (malformed entry?)
    except (IOError, OSError):
        pass

    # What IP addresses do we have?
    ip_addresses = [salt.utils.network.IPv4Address(addr) for addr
                    in salt.utils.network.ip_addrs(include_loopback=True)
                    if not addr.startswith('127.')]

    for addr in ip_addresses:
        if not addr.is_private:
            log.info('Using public ip address for id: {0}'.format(addr))
            return str(addr), True

    if ip_addresses:
        addr = ip_addresses.pop(0)
        log.info('Using private ip address for id: {0}'.format(addr))
        return str(addr), True

    log.error('No id found, falling back to localhost')
    return 'localhost', False


def apply_minion_config(overrides=None,
                        defaults=None,
                        check_dns=None,
                        minion_id=False):
    '''
    Returns minion configurations dict.
    '''
    if check_dns is not None:
        # All use of the `check_dns` arg was removed in `598d715`. The keyword
        # argument was then removed in `9d893e4` and `**kwargs` was then added
        # in `5d60f77` in order not to break backwards compatibility.
        #
        # Showing a deprecation for 0.17.0 and 0.18.0 should be enough for any
        # api calls to be updated in order to stop it's use.
        salt.utils.warn_until(
            'Helium',
            'The functionality behind the \'check_dns\' keyword argument is '
            'no longer required, as such, it became unnecessary and is now '
            'deprecated. \'check_dns\' will be removed in Salt {version}.'
        )

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
        opts['id'], using_ip_for_id = get_id(
                opts['root_dir'],
                minion_id=minion_id,
                cache=opts.get('minion_id_caching', True))

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
                'minutes': opts['mine_interval'],
                'jid_include': True,
                'maxrunning': 2
            }
        })
    return opts


def master_config(path, env_var='SALT_MASTER_CONFIG', defaults=None):
    '''
    Reads in the master configuration file and sets up default options
    '''
    if defaults is None:
        defaults = DEFAULT_MASTER_OPTS

    if not os.environ.get(env_var, None):
        # No valid setting was given using the configuration variable.
        # Lets see is SALT_CONFIG_DIR is of any use
        salt_config_dir = os.environ.get('SALT_CONFIG_DIR', None)
        if salt_config_dir:
            env_config_file_path = os.path.join(salt_config_dir, 'master')
            if salt_config_dir and os.path.isfile(env_config_file_path):
                # We can get a configuration file using SALT_CONFIG_DIR, let's
                # update the environment with this information
                os.environ[env_var] = env_config_file_path

    overrides = load_config(path, env_var, DEFAULT_MASTER_OPTS['conf_file'])
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
        'autosign_file', 'autoreject_file', 'token_dir'
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
            os.path.expanduser('~/.salt'),
            env_var,
            os.path.expanduser('~/.salt')
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
    # On some platforms, like OpenBSD, 0.0.0.0 won't catch a master running on localhost
    if opts['interface'] == '0.0.0.0':
        opts['interface'] = '127.0.0.1'

    # Make sure the master_uri is set
    if 'master_uri' not in opts:
        opts['master_uri'] = 'tcp://{ip}:{port}'.format(ip=opts['interface'],
                                                        port=opts['ret_port'])
    # Return the client options
    _validate_opts(opts)
    return opts
