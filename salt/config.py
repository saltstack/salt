# -*- coding: utf-8 -*-
'''
All salt configuration loading and defaults should be in this module
'''

from __future__ import absolute_import

# Import python libs
from __future__ import generators
import glob
import os
import re
import logging
from copy import deepcopy
import time
import codecs

# import third party libs
import yaml
try:
    yaml.Loader = yaml.CLoader
    yaml.Dumper = yaml.CDumper
except Exception:
    pass

# Import salt libs
import salt.utils
import salt.utils.network
import salt.syspaths
import salt.utils.validate.path
import salt.utils.xdg
import salt.exceptions
import salt.utils.sdb

from salt.ext.six import string_types, text_type
from salt.ext.six.moves.urllib.parse import urlparse  # pylint: disable=import-error,no-name-in-module

import sys

log = logging.getLogger(__name__)

_DFLT_LOG_DATEFMT = '%H:%M:%S'
_DFLT_LOG_DATEFMT_LOGFILE = '%Y-%m-%d %H:%M:%S'
_DFLT_LOG_FMT_CONSOLE = '[%(levelname)-8s] %(message)s'
_DFLT_LOG_FMT_LOGFILE = (
    '%(asctime)s,%(msecs)03.0f [%(name)-17s][%(levelname)-8s][%(process)d] %(message)s'
)

if salt.utils.is_windows():
    # Since an 'ipc_mode' of 'ipc' will never work on Windows due to lack of
    # support in ZeroMQ, we want the default to be something that has a
    # chance of working.
    _DFLT_IPC_MODE = 'tcp'
    _DFLT_MULTIPROCESSING_MODE = False
else:
    _DFLT_IPC_MODE = 'ipc'
    _DFLT_MULTIPROCESSING_MODE = True

FLO_DIR = os.path.join(
        os.path.dirname(__file__),
        'daemons', 'flo')

VALID_OPTS = {
    'master': str,
    'master_port': int,
    'master_type': str,
    'master_finger': str,
    'master_shuffle': bool,
    'master_alive_interval': int,
    'master_sign_key_name': str,
    'master_sign_pubkey': bool,
    'verify_master_pubkey_sign': bool,
    'always_verify_signature': bool,
    'master_pubkey_signature': str,
    'master_use_pubkey_signature': bool,
    'syndic_finger': str,
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
    'pillarenv': str,
    'state_top': str,
    'startup_states': str,
    'sls_list': list,
    'top_file': str,
    'file_client': str,
    'use_master_when_local': bool,
    'file_roots': dict,
    'pillar_roots': dict,
    'hash_type': str,
    'disable_modules': list,
    'disable_returners': list,
    'whitelist_modules': list,
    'module_dirs': list,
    'returner_dirs': list,
    'states_dirs': list,
    'grains_dirs': list,
    'render_dirs': list,
    'outputter_dirs': list,
    'utils_dirs': list,
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
    'max_event_size': int,
    'test': bool,
    'cython_enable': bool,
    'show_timeout': bool,
    'show_jid': bool,
    'state_verbose': bool,
    'state_output': str,
    'state_auto_order': bool,
    'state_events': bool,
    'acceptance_wait_time': float,
    'acceptance_wait_time_max': float,
    'rejected_retry': bool,
    'loop_interval': float,
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
    'event_return': str,
    'event_return_queue': int,
    'event_return_whitelist': list,
    'event_return_blacklist': list,
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
    'pub_hwm': int,
    'worker_threads': int,
    'ret_port': int,
    'keep_jobs': int,
    'master_roots': dict,
    'gitfs_remotes': list,
    'gitfs_mountpoint': str,
    'gitfs_root': str,
    'gitfs_base': str,
    'gitfs_user': str,
    'gitfs_password': str,
    'gitfs_insecure_auth': bool,
    'gitfs_privkey': str,
    'gitfs_pubkey': str,
    'gitfs_passphrase': str,
    'gitfs_env_whitelist': list,
    'gitfs_env_blacklist': list,
    'hgfs_remotes': list,
    'hgfs_mountpoint': str,
    'hgfs_root': str,
    'hgfs_base': str,
    'hgfs_branch_method': str,
    'hgfs_env_whitelist': list,
    'hgfs_env_blacklist': list,
    'svnfs_remotes': list,
    'svnfs_mountpoint': str,
    'svnfs_root': str,
    'svnfs_trunk': str,
    'svnfs_branches': str,
    'svnfs_tags': str,
    'svnfs_env_whitelist': list,
    'svnfs_env_blacklist': list,
    'minionfs_env': str,
    'minionfs_mountpoint': str,
    'minionfs_whitelist': list,
    'minionfs_blacklist': list,
    'ext_pillar': list,
    'pillar_version': int,
    'pillar_opts': bool,
    'pillar_safe_render_error': bool,
    'pillar_source_merging_strategy': str,
    'ping_on_rotate': bool,
    'peer': dict,
    'preserve_minion_cache': bool,
    'syndic_master': str,
    'runner_dirs': list,
    'client_acl': dict,
    'client_acl_blacklist': dict,
    'sudo_acl': bool,
    'external_auth': dict,
    'token_expire': int,
    'file_recv': bool,
    'file_recv_max_size': int,
    'file_ignore_regex': bool,
    'file_ignore_glob': bool,
    'fileserver_backend': list,
    'fileserver_followsymlinks': bool,
    'fileserver_ignoresymlinks': bool,
    'fileserver_limit_traversal': bool,
    'max_open_files': int,
    'auto_accept': bool,
    'autosign_timeout': int,
    'master_tops': bool,
    'order_masters': bool,
    'job_cache': bool,
    'ext_job_cache': str,
    'master_job_cache': str,
    'minion_data_cache': bool,
    'publish_session': int,
    'reactor': list,
    'reactor_refresh_interval': int,
    'reactor_worker_threads': int,
    'reactor_worker_hwm': int,
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
    'transport': str,
    'enumerate_proxy_minions': bool,
    'gather_job_timeout': int,
    'auth_timeout': int,
    'auth_tries': int,
    'auth_safemode': bool,
    'random_master': bool,
    'random_reauth_delay': int,
    'syndic_event_forward_timeout': float,
    'syndic_max_event_process_time': float,
    'syndic_jid_forward_cache_hwm': int,
    'ssh_passwd': str,
    'ssh_port': str,
    'ssh_sudo': bool,
    'ssh_timeout': float,
    'ssh_user': str,
    'ssh_scan_ports': str,
    'ssh_scan_timeout': float,
    'ioflo_verbose': int,
    'ioflo_period': float,
    'ioflo_realtime': bool,
    'ioflo_console_logdir': str,
    'raet_port': int,
    'raet_alt_port': int,
    'raet_mutable': bool,
    'raet_main': bool,
    'raet_clear_remotes': bool,
    'sqlite_queue_dir': str,
    'queue_dirs': list,
    'ping_interval': int,
    'cli_summary': bool,
    'max_minions': int,
    'username': str,
    'password': str,
    'zmq_filtering': bool,
    'con_cache': bool,
    'rotate_aes_key': bool,
    'cache_sreqs': bool,
    'cmd_safe': bool,
    'sudo_user': str,
}

# default configurations
DEFAULT_MINION_OPTS = {
    'interface': '0.0.0.0',
    'master': 'salt',
    'master_type': 'standard',
    'master_port': '4506',
    'master_finger': '',
    'master_shuffle': False,
    'master_alive_interval': 0,
    'verify_master_pubkey_sign': False,
    'always_verify_signature': False,
    'master_sign_key_name': 'master_sign',
    'syndic_finger': '',
    'user': 'root',
    'root_dir': salt.syspaths.ROOT_DIR,
    'pki_dir': os.path.join(salt.syspaths.CONFIG_DIR, 'pki', 'minion'),
    'id': None,
    'cachedir': os.path.join(salt.syspaths.CACHE_DIR, 'minion'),
    'cache_jobs': False,
    'grains_cache': False,
    'grains_cache_expiration': 300,
    'conf_file': os.path.join(salt.syspaths.CONFIG_DIR, 'minion'),
    'sock_dir': os.path.join(salt.syspaths.SOCK_DIR, 'minion'),
    'backup_mode': '',
    'renderer': 'yaml_jinja',
    'failhard': False,
    'autoload_dynamic_modules': True,
    'environment': None,
    'pillarenv': None,
    'extension_modules': '',
    'state_top': 'top.sls',
    'startup_states': '',
    'sls_list': [],
    'top_file': '',
    'file_client': 'remote',
    'use_master_when_local': False,
    'file_roots': {
        'base': [salt.syspaths.BASE_FILE_ROOTS_DIR],
    },
    'fileserver_limit_traversal': False,
    'file_recv': False,
    'file_recv_max_size': 100,
    'file_ignore_regex': None,
    'file_ignore_glob': None,
    'fileserver_backend': ['roots'],
    'fileserver_followsymlinks': True,
    'fileserver_ignoresymlinks': False,
    'pillar_roots': {
        'base': [salt.syspaths.BASE_PILLAR_ROOTS_DIR],
    },
    'gitfs_remotes': [],
    'gitfs_mountpoint': '',
    'gitfs_root': '',
    'gitfs_base': 'master',
    'gitfs_user': '',
    'gitfs_password': '',
    'gitfs_insecure_auth': False,
    'gitfs_privkey': '',
    'gitfs_pubkey': '',
    'gitfs_passphrase': '',
    'gitfs_env_whitelist': [],
    'gitfs_env_blacklist': [],
    'hash_type': 'md5',
    'disable_modules': [],
    'disable_returners': [],
    'whitelist_modules': [],
    'module_dirs': [],
    'returner_dirs': [],
    'grains_dirs': [],
    'states_dirs': [],
    'render_dirs': [],
    'outputter_dirs': [],
    'utils_dirs': [],
    'providers': {},
    'clean_dynamic_modules': True,
    'open_mode': False,
    'auto_accept': True,
    'autosign_timeout': 120,
    'multiprocessing': _DFLT_MULTIPROCESSING_MODE,
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
    'max_event_size': 1048576,
    'test': False,
    'ext_job_cache': '',
    'cython_enable': False,
    'state_verbose': True,
    'state_output': 'full',
    'state_auto_order': True,
    'state_events': False,
    'state_aggregate': False,
    'acceptance_wait_time': 10,
    'acceptance_wait_time_max': 0,
    'rejected_retry': False,
    'loop_interval': 1,
    'verify_env': True,
    'grains': {},
    'permissive_pki_access': False,
    'default_include': 'minion.d/*.conf',
    'update_url': False,
    'update_restart_services': [],
    'retry_dns': 30,
    'recon_max': 10000,
    'recon_default': 1000,
    'recon_randomize': True,
    'syndic_log_file': os.path.join(salt.syspaths.LOGS_DIR, 'syndic'),
    'syndic_pidfile': os.path.join(salt.syspaths.PIDFILE_DIR, 'salt-syndic.pid'),
    'random_reauth_delay': 10,
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
    'keysize': 2048,
    'transport': 'zeromq',
    'auth_timeout': 60,
    'auth_tries': 7,
    'auth_safemode': False,
    'random_master': False,
    'minion_floscript': os.path.join(FLO_DIR, 'minion.flo'),
    'caller_floscript': os.path.join(FLO_DIR, 'caller.flo'),
    'ioflo_verbose': 0,
    'ioflo_period': 0.1,
    'ioflo_realtime': True,
    'ioflo_console_logdir': '',
    'raet_port': 4510,
    'raet_alt_port': 4511,
    'raet_mutable': False,
    'raet_main': False,
    'raet_clear_remotes': True,
    'ping_interval': 0,
    'username': None,
    'password': None,
    'zmq_filtering': False,
    'zmq_monitor': False,
    'cache_sreqs': True,
    'cmd_safe': True,
    'sudo_user': '',
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
    'file_client': 'local',
    'gitfs_remotes': [],
    'gitfs_mountpoint': '',
    'gitfs_root': '',
    'gitfs_base': 'master',
    'gitfs_user': '',
    'gitfs_password': '',
    'gitfs_insecure_auth': False,
    'gitfs_privkey': '',
    'gitfs_pubkey': '',
    'gitfs_passphrase': '',
    'gitfs_env_whitelist': [],
    'gitfs_env_blacklist': [],
    'hgfs_remotes': [],
    'hgfs_mountpoint': '',
    'hgfs_root': '',
    'hgfs_base': 'default',
    'hgfs_branch_method': 'branches',
    'hgfs_env_whitelist': [],
    'hgfs_env_blacklist': [],
    'show_timeout': True,
    'show_jid': False,
    'svnfs_remotes': [],
    'svnfs_mountpoint': '',
    'svnfs_root': '',
    'svnfs_trunk': 'trunk',
    'svnfs_branches': 'branches',
    'svnfs_tags': 'tags',
    'svnfs_env_whitelist': [],
    'svnfs_env_blacklist': [],
    'max_event_size': 1048576,
    'minionfs_env': 'base',
    'minionfs_mountpoint': '',
    'minionfs_whitelist': [],
    'minionfs_blacklist': [],
    'ext_pillar': [],
    'pillar_version': 2,
    'pillar_opts': False,
    'pillar_safe_render_error': True,
    'pillar_source_merging_strategy': 'smart',
    'ping_on_rotate': False,
    'peer': {},
    'preserve_minion_cache': False,
    'syndic_master': '',
    'runner_dirs': [],
    'outputter_dirs': [],
    'client_acl': {},
    'client_acl_blacklist': {},
    'sudo_acl': False,
    'external_auth': {},
    'token_expire': 43200,
    'extension_modules': os.path.join(salt.syspaths.CACHE_DIR, 'extmods'),
    'file_recv': False,
    'file_recv_max_size': 100,
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
    'order_masters': False,
    'job_cache': True,
    'ext_job_cache': '',
    'master_job_cache': 'local_cache',
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
    'reactor_refresh_interval': 60,
    'reactor_worker_threads': 10,
    'reactor_worker_hwm': 10000,
    'event_return': '',
    'event_return_queue': 0,
    'event_return_whitelist': [],
    'event_return_blacklist': [],
    'serial': 'msgpack',
    'state_verbose': True,
    'state_output': 'full',
    'state_auto_order': True,
    'state_events': False,
    'state_aggregate': False,
    'search': '',
    'search_index_interval': 3600,
    'loop_interval': 60,
    'nodegroups': {},
    'cython_enable': False,
    'enable_gpu_grains': False,
    # XXX: Remove 'key_logfile' support in 2014.1.0
    'key_logfile': os.path.join(salt.syspaths.LOGS_DIR, 'key'),
    'verify_env': True,
    'permissive_pki_access': False,
    'default_include': 'master.d/*.conf',
    'win_repo': os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR, 'win', 'repo'),
    'win_repo_mastercachefile': os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR,
                                             'win', 'repo', 'winrepo.p'),
    'win_gitrepos': ['https://github.com/saltstack/salt-winrepo.git'],
    'syndic_wait': 5,
    'jinja_lstrip_blocks': False,
    'jinja_trim_blocks': False,
    'sign_pub_messages': False,
    'keysize': 2048,
    'transport': 'zeromq',
    'enumerate_proxy_minions': False,
    'gather_job_timeout': 5,
    'syndic_event_forward_timeout': 0.5,
    'syndic_max_event_process_time': 0.5,
    'syndic_jid_forward_cache_hwm': 100,
    'ssh_passwd': '',
    'ssh_port': '22',
    'ssh_sudo': False,
    'ssh_timeout': 60,
    'ssh_user': 'root',
    'ssh_scan_ports': '22',
    'ssh_scan_timeout': 0.01,
    'master_floscript': os.path.join(FLO_DIR, 'master.flo'),
    'worker_floscript': os.path.join(FLO_DIR, 'worker.flo'),
    'maintenance_floscript': os.path.join(FLO_DIR, 'maint.flo'),
    'ioflo_verbose': 0,
    'ioflo_period': 0.01,
    'ioflo_realtime': True,
    'ioflo_console_logdir': '',
    'raet_port': 4506,
    'raet_alt_port': 4511,
    'raet_mutable': False,
    'raet_main': True,
    'raet_clear_remotes': False,
    'sqlite_queue_dir': os.path.join(salt.syspaths.CACHE_DIR, 'master', 'queues'),
    'queue_dirs': [],
    'cli_summary': False,
    'max_minions': 0,
    'master_sign_key_name': 'master_sign',
    'master_sign_pubkey': False,
    'master_pubkey_signature': 'master_pubkey_signature',
    'master_use_pubkey_signature': False,
    'zmq_filtering': False,
    'con_cache': False,
    'rotate_aes_key': True,
    'cache_sreqs': True,
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

DEFAULT_API_OPTS = {
    # ----- Salt master settings overridden by Salt-API --------------------->
    'pidfile': '/var/run/salt-api.pid',
    'logfile': '/var/log/salt/api',
    # <---- Salt master settings overridden by Salt-API ----------------------
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
        return {'base': _expand_glob_path([salt.syspaths.BASE_FILE_ROOTS_DIR])}
    for saltenv, dirs in opts['file_roots'].items():
        if not isinstance(dirs, (list, tuple)):
            opts['file_roots'][saltenv] = []
        opts['file_roots'][saltenv] = _expand_glob_path(opts['file_roots'][saltenv])
    return opts['file_roots']


def _expand_glob_path(file_roots):
    '''
    Applies shell globbing to a set of directories and returns
    the expanded paths
    '''
    unglobbed_path = []
    for path in file_roots:
        if glob.has_magic(path):
            unglobbed_path.extend(glob.glob(path))
        else:
            unglobbed_path.append(path)
    return unglobbed_path


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
    '''
    Read in a config file from a given path and process it into a dictionary
    '''
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
        for key, value in conf_opts.copy().items():
            if isinstance(value, text_type):
                # We do not want unicode settings
                conf_opts[key] = value.encode('utf-8')
        return conf_opts


def _absolute_path(path, relative_to=None):
    '''
    Return an absolute path. In case ``relative_to`` is passed and ``path`` is
    not an absolute path, we try to prepend ``relative_to`` to ``path``and if
    that path exists, return that one
    '''

    if path and os.path.isabs(path):
        return path
    if path and relative_to is not None:
        _abspath = os.path.join(relative_to, path)
        if os.path.isfile(_abspath):
            log.debug(
                'Relative path {0!r} converted to existing absolute path {1!r}'.format(
                    path, _abspath
                )
            )
            return _abspath
    return path


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
        # This is most likely not being used from salt, i.e., could be salt-cloud
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
        # In this case, maintain old behavior
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

    if salt.utils.validate.path.is_readable(path):
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
    root_opt = opts['root_dir'].rstrip(os.sep)
    for path_option in path_options:
        if path_option in opts:
            path = opts[path_option]
            if path == root_opt or path.startswith(root_opt + os.sep):
                path = path[len(root_opt):]
            opts[path_option] = salt.utils.path_join(root_dir, path)


def insert_system_path(opts, paths):
    '''
    Inserts path into python path taking into consideration 'root_dir' option.
    '''
    if isinstance(paths, str):
        paths = [paths]
    for path in paths:
        path_options = {'path': path, 'root_dir': opts['root_dir']}
        prepend_root_dir(path_options, path_options)
        if (os.path.isdir(path_options['path'])
                and path_options['path'] not in sys.path):
            sys.path.insert(0, path_options['path'])


def minion_config(path,
                  env_var='SALT_MINION_CONFIG',
                  defaults=None,
                  cache_minion_id=False):
    '''
    Reads in the minion configuration file and sets up special options

    This is useful for Minion-side operations, such as the
    :py:class:`~salt.client.Caller` class, and manually running the loader
    interface.

    .. code-block:: python

        import salt.client
        minion_opts = salt.config.minion_config('/etc/salt/minion')
    '''
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

    opts = apply_minion_config(overrides, defaults, cache_minion_id=cache_minion_id)
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
        '__role': 'syndic',
        'root_dir': opts.get('root_dir', salt.syspaths.ROOT_DIR),
        'pidfile': opts.get('syndic_pidfile', 'salt-syndic.pid'),
        'log_file': opts.get('syndic_log_file', 'salt-syndic.log'),
        'id': minion_opts['id'],
        'pki_dir': minion_opts['pki_dir'],
        'master': opts['syndic_master'],
        'interface': master_opts['interface'],
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
        'cachedir': master_opts['cachedir'],
    }
    opts.update(syndic_opts)
    # Prepend root_dir to other paths
    prepend_root_dirs = [
        'pki_dir', 'cachedir', 'pidfile', 'sock_dir', 'extension_modules',
        'autosign_file', 'autoreject_file', 'token_dir'
    ]
    for config_key in ('log_file', 'key_logfile'):
        # If this is not a URI and instead a local path
        if urlparse(opts.get(config_key, '')).scheme == '':
            prepend_root_dirs.append(config_key)
    prepend_root_dir(opts, prepend_root_dirs)
    return opts


# ----- Salt Cloud Configuration Functions ---------------------------------->
def apply_sdb(opts, sdb_opts=None):
    '''
    Recurse for sdb:// links for opts
    '''
    if sdb_opts is None:
        sdb_opts = opts
    if isinstance(sdb_opts, string_types) and sdb_opts.startswith('sdb://'):
        return salt.utils.sdb.sdb_get(sdb_opts, opts)
    elif isinstance(sdb_opts, dict):
        for key, value in sdb_opts.items():
            if value is None:
                continue
            sdb_opts[key] = apply_sdb(opts, value)
    elif isinstance(sdb_opts, list):
        for key, value in enumerate(sdb_opts):
            if value is None:
                continue
            sdb_opts[key] = apply_sdb(opts, value)

    return sdb_opts


def cloud_config(path, env_var='SALT_CLOUD_CONFIG', defaults=None,
                 master_config_path=None, master_config=None,
                 providers_config_path=None, providers_config=None,
                 profiles_config_path=None, profiles_config=None):
    '''
    Read in the salt cloud config and return the dict
    '''
    # Load the cloud configuration
    overrides = load_config(
        path,
        env_var,
        os.path.join(salt.syspaths.CONFIG_DIR, 'cloud')
    )
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

    # Convert relative to absolute paths if necessary
    master_config_path = _absolute_path(master_config_path, config_dir)

    if 'providers_config' in overrides and providers_config_path is None:
        # The configuration setting is being specified in the main cloud
        # configuration file
        providers_config_path = overrides['providers_config']
    elif 'providers_config' not in overrides and not providers_config \
            and not providers_config_path:
        providers_config_path = os.path.join(config_dir, 'cloud.providers')

    # Convert relative to absolute paths if necessary
    providers_config_path = _absolute_path(providers_config_path, config_dir)

    if 'profiles_config' in overrides and profiles_config_path is None:
        # The configuration setting is being specified in the main cloud
        # configuration file
        profiles_config_path = overrides['profiles_config']
    elif 'profiles_config' not in overrides and not profiles_config \
            and not profiles_config_path:
        profiles_config_path = os.path.join(config_dir, 'cloud.profiles')

    # Convert relative to absolute paths if necessary
    profiles_config_path = _absolute_path(profiles_config_path, config_dir)

    # Prepare the deploy scripts search path
    deploy_scripts_search_path = overrides.get(
        'deploy_scripts_search_path',
        defaults.get('deploy_scripts_search_path', 'cloud.deploy.d')
    )
    if isinstance(deploy_scripts_search_path, string_types):
        deploy_scripts_search_path = [deploy_scripts_search_path]

    # Check the provided deploy scripts search path removing any non existing
    # entries.
    for idx, entry in enumerate(deploy_scripts_search_path[:]):
        if not os.path.isabs(entry):
            # Let's try if adding the provided path's directory name turns the
            # entry into a proper directory
            entry = os.path.join(os.path.dirname(path), entry)

        if os.path.isdir(entry):
            # Path exists, let's update the entry (its path might have been
            # made absolute)
            deploy_scripts_search_path[idx] = entry
            continue

        # It's not a directory? Remove it from the search path
        deploy_scripts_search_path.pop(idx)

    # Add the built-in scripts directory to the search path (last resort)
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
        raise salt.exceptions.SaltCloudConfigError(
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
        raise salt.exceptions.SaltCloudConfigError(
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
        raise salt.exceptions.SaltCloudConfigError(
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
            raise salt.exceptions.SaltCloudConfigError(
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
                raise salt.exceptions.SaltCloudConfigError(
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

    # recurse opts for sdb configs
    apply_sdb(opts)

    # Return the final options
    return opts


def apply_cloud_config(overrides, defaults=None):
    '''
    Return a cloud config
    '''
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
                        raise salt.exceptions.SaltCloudConfigError(
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
                    raise salt.exceptions.SaltCloudConfigError(
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
        for opt, val in opts.items():
            if provider in opt:
                value = val
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
        if key in ('conf_file', 'include', 'default_include', 'user'):
            continue
        if not isinstance(val, dict):
            raise salt.exceptions.SaltCloudConfigError(
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
                    log.trace(
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
                log.trace(
                    'The profile {0!r} is defining {1[provider]!r} as the '
                    'provider. Since there\'s no valid configuration for '
                    'that provider, the profile will be removed from the '
                    'available listing'.format(profile, details)
                )
                vms.pop(profile)
                continue

            driver = next(iter(list(providers[details['provider']].keys())))
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
                log.trace(
                    'The profile {0!r} is defining {1[provider]!r} as the '
                    'provider. Since there\'s no valid configuration for '
                    'that provider, the profile will be removed from the '
                    'available listing'.format(profile, extended)
                )
                vms.pop(profile)
                continue

            driver = next(iter(list(providers[extended['provider']].keys())))
            providers[extended['provider']][driver].setdefault(
                'profiles', {}).update({profile: extended})

            extended['provider'] = '{0[provider]}:{1}'.format(extended, driver)
        else:
            alias, driver = extended['provider'].split(':')
            if alias not in providers or driver not in providers[alias]:
                log.trace(
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
    ext_count = 0
    for key, val in config.items():
        if key in ('conf_file', 'include', 'default_include', 'user'):
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
                    raise salt.exceptions.SaltCloudConfigError(
                        'The cloud provider alias {0!r} has multiple entries '
                        'for the {1[provider]!r} driver.'.format(key, details)
                    )
                handled_providers.add(details['provider'])

        for entry in val:
            if 'provider' not in entry:
                entry['provider'] = '-only-extendable-{0}'.format(ext_count)
                ext_count += 1

            if key not in providers:
                providers[key] = {}

            provider = entry['provider']
            if provider not in providers[key]:
                providers[key][provider] = entry

    # Is any provider extending data!?
    while True:
        keep_looping = False
        for provider_alias, entries in providers.copy().items():

            for driver, details in entries.items():
                # Set a holder for the defined profiles
                providers[provider_alias][driver]['profiles'] = {}

                if 'extends' not in details:
                    continue

                extends = details.pop('extends')

                if ':' in extends:
                    alias, provider = extends.split(':')
                    if alias not in providers:
                        raise salt.exceptions.SaltCloudConfigError(
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
                        raise salt.exceptions.SaltCloudConfigError(
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
                    # change provider details '-only-extendable-' to extended provider name
                    details['provider'] = provider
                elif providers.get(extends):
                    raise salt.exceptions.SaltCloudConfigError(
                        'The {0!r} cloud provider entry in {1!r} is trying '
                        'to extend from {2!r} and no provider was specified. '
                        'Not extending!'.format(
                            details['provider'], provider_alias, extends
                        )
                    )
                elif extends not in providers:
                    raise salt.exceptions.SaltCloudConfigError(
                        'The {0!r} cloud provider entry in {1!r} is trying '
                        'to extend data from {2!r} though {2!r} is not '
                        'defined in the salt cloud providers loaded '
                        'data.'.format(
                            details['provider'], provider_alias, extends
                        )
                    )
                else:
                    if driver in providers.get(extends):
                        details['extends'] = '{0}:{1}'.format(extends, driver)
                    elif '-only-extendable-' in providers.get(extends):
                        details['extends'] = '{0}:{1}'.format(
                            extends, '-only-extendable-{0}'.format(ext_count)
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
            for driver, details in entries.items():

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
                # Update name of the driver, now that it's populated with extended information
                if driver.startswith('-only-extendable-'):
                    providers[alias][ext_driver] = providers[alias][driver]
                    # Delete driver with old name to maintain dictionary size
                    del providers[alias][driver]

        if not keep_looping:
            break

    # Now clean up any providers entry that was just used to be a data tree to
    # extend from
    for provider_alias, entries in providers.copy().items():
        for driver, details in entries.copy().items():
            if not driver.startswith('-only-extendable-'):
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
            provider_driver_defs = alias_defs[next(iter(list(alias_defs.keys())))]
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
                log.trace(
                    'The required {0!r} configuration setting is missing on '
                    'the {1!r} driver(under the {2!r} alias)'.format(
                        key, provider, alias
                    )
                )
                return False
        # If we reached this far, there's a properly configured provider,
        # return it!
        return opts['providers'][alias][driver]

    for alias, drivers in opts['providers'].items():
        for driver, provider_details in drivers.items():
            if driver != provider:
                continue

            # If we reached this far, we have a matching provider, let's see if
            # all required configuration keys are present and not None
            skip_provider = False
            for key in required_keys:
                if provider_details.get(key, None) is None:
                    # This provider does not include all necessary keys,
                    # continue to next one
                    log.trace(
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


def get_id(opts, cache_minion_id=False):
    '''
    Guess the id of the minion.

    If CONFIG_DIR/minion_id exists, use the cached minion ID from that file.
    If no minion id is configured, use multiple sources to find a FQDN.
    If no FQDN is found you may get an ip address.

    Returns two values: the detected ID, and a boolean value noting whether or
    not an IP address is being used for the ID.
    '''
    if opts['root_dir'] is None:
        root_dir = salt.syspaths.ROOT_DIR
    else:
        root_dir = opts['root_dir']

    config_dir = salt.syspaths.CONFIG_DIR
    if config_dir.startswith(salt.syspaths.ROOT_DIR):
        config_dir = config_dir.split(salt.syspaths.ROOT_DIR, 1)[-1]

    # Check for cached minion ID
    id_cache = os.path.join(root_dir,
                            config_dir.lstrip(os.path.sep),
                            'minion_id')

    if opts.get('minion_id_caching', True):
        try:
            with salt.utils.fopen(id_cache) as idf:
                name = idf.readline().strip()
                if name.startswith(codecs.BOM):  # Remove BOM if exists
                    name = name.replace(codecs.BOM, '', 1)
            if name:
                log.debug('Using cached minion ID from {0}: {1}'.format(id_cache, name))
                return name, False
        except (IOError, OSError):
            pass
    if '__role' in opts and opts.get('__role') == 'minion':
        log.debug('Guessing ID. The id can be explicitly in set {0}'
                  .format(os.path.join(salt.syspaths.CONFIG_DIR, 'minion')))

    newid = salt.utils.network.generate_minion_id()
    if '__role' in opts and opts.get('__role') == 'minion':
        log.info('Found minion id from generate_minion_id(): {0}'.format(newid))
    if cache_minion_id and opts.get('minion_id_caching', True):
        _cache_id(newid, id_cache)
    is_ipv4 = newid.count('.') == 3 and not any(c.isalpha() for c in newid)
    return newid, is_ipv4


def apply_minion_config(overrides=None,
                        defaults=None,
                        cache_minion_id=False):
    '''
    Returns minion configurations dict.
    '''
    if defaults is None:
        defaults = DEFAULT_MINION_OPTS

    opts = defaults.copy()
    opts['__role'] = 'minion'
    if overrides:
        opts.update(overrides)

    if len(opts['sock_dir']) > len(opts['cachedir']) + 10:
        opts['sock_dir'] = os.path.join(opts['cachedir'], '.salt-unix')

    # No ID provided. Will getfqdn save us?
    using_ip_for_id = False
    if opts['id'] is None:
        opts['id'], using_ip_for_id = get_id(
                opts,
                cache_minion_id=cache_minion_id)

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

    # Set up the utils_dirs location from the extension_modules location
    opts['utils_dirs'] = (
        opts.get('utils_dirs') or
        [os.path.join(opts['extension_modules'], 'utils')]
    )

    # Insert all 'utils_dirs' directories to the system path
    insert_system_path(opts, opts['utils_dirs'])

    # Prepend root_dir to other paths
    prepend_root_dirs = [
        'pki_dir', 'cachedir', 'sock_dir', 'extension_modules', 'pidfile',
    ]

    # These can be set to syslog, so, not actual paths on the system
    for config_key in ('log_file', 'key_logfile'):
        if urlparse(opts.get(config_key, '')).scheme == '':
            prepend_root_dirs.append(config_key)

    prepend_root_dir(opts, prepend_root_dirs)

    # if there is no schedule option yet, add an empty scheduler
    if 'schedule' not in opts:
        opts['schedule'] = {}
    return opts


def master_config(path, env_var='SALT_MASTER_CONFIG', defaults=None):
    '''
    Reads in the master configuration file and sets up default options

    This is useful for running the actual master daemon. For running
    Master-side client interfaces that need the master opts see
    :py:func:`salt.client.client_config`.
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
    if opts.get('transport') == 'raet' and 'aes' in opts:
        opts.pop('aes')
    return opts


def apply_master_config(overrides=None, defaults=None):
    '''
    Returns master configurations dict.
    '''
    import salt.crypt
    if defaults is None:
        defaults = DEFAULT_MASTER_OPTS

    opts = defaults.copy()
    opts['__role'] = 'master'
    if overrides:
        opts.update(overrides)

    if len(opts['sock_dir']) > len(opts['cachedir']) + 10:
        opts['sock_dir'] = os.path.join(opts['cachedir'], '.salt-unix')

    opts['extension_modules'] = (
        opts.get('extension_modules') or
        os.path.join(opts['cachedir'], 'extmods')
    )
    opts['token_dir'] = os.path.join(opts['cachedir'], 'tokens')
    opts['syndic_dir'] = os.path.join(opts['cachedir'], 'syndics')

    using_ip_for_id = False
    append_master = False
    if opts.get('id') is None:
        opts['id'], using_ip_for_id = get_id(
                opts,
                cache_minion_id=None)
        append_master = True

    # it does not make sense to append a domain to an IP based id
    if not using_ip_for_id and 'append_domain' in opts:
        opts['id'] = _append_domain(opts)
    if append_master:
        opts['id'] += '_master'

    # Prepend root_dir to other paths
    prepend_root_dirs = [
        'pki_dir', 'cachedir', 'pidfile', 'sock_dir', 'extension_modules',
        'autosign_file', 'autoreject_file', 'token_dir', 'syndic_dir',
        'sqlite_queue_dir'
    ]

    # These can be set to syslog, so, not actual paths on the system
    for config_key in ('log_file', 'key_logfile'):
        log_setting = opts.get(config_key, '')
        if log_setting is None:
            continue

        if urlparse(log_setting).scheme == '':
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

    opts.setdefault('pillar_source_merging_strategy', 'smart')

    return opts


def client_config(path, env_var='SALT_CLIENT_CONFIG', defaults=None):
    '''
    Load Master configuration data

    Usage:

    .. code-block:: python

        import salt.config
        master_opts = salt.config.client_config('/etc/salt/master')

    Returns a dictionary of the Salt Master configuration file with necessary
    options needed to communicate with a locally-running Salt Master daemon.
    This function searches for client specific configurations and adds them to
    the data from the master configuration.

    This is useful for master-side operations like
    :py:class:`~salt.client.LocalClient`.
    '''
    if defaults is None:
        defaults = DEFAULT_MASTER_OPTS

    xdg_dir = salt.utils.xdg.xdg_config_dir()
    if os.path.isdir(xdg_dir):
        client_config_dir = xdg_dir
        saltrc_config_file = 'saltrc'
    else:
        client_config_dir = os.path.expanduser('~')
        saltrc_config_file = '.saltrc'

    # Get the token file path from the provided defaults. If not found, specify
    # our own, sane, default
    opts = {
        'token_file': defaults.get(
            'token_file',
            os.path.join(client_config_dir, 'salt_token')
        )
    }
    # Update options with the master configuration, either from the provided
    # path, salt's defaults or provided defaults
    opts.update(
        master_config(path, defaults=defaults)
    )
    # Update with the users salt dot file or with the environment variable
    saltrc_config = os.path.join(client_config_dir, saltrc_config_file)
    opts.update(
        load_config(
            saltrc_config,
            env_var,
            saltrc_config
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
        # Make sure token is still valid
        expire = opts.get('token_expire', 43200)
        if os.stat(opts['token_file']).st_mtime + expire > time.mktime(time.localtime()):
            with salt.utils.fopen(opts['token_file']) as fp_:
                opts['token'] = fp_.read().strip()
    # On some platforms, like OpenBSD, 0.0.0.0 won't catch a master running on localhost
    if opts['interface'] == '0.0.0.0':
        opts['interface'] = '127.0.0.1'

    # Make sure the master_uri is set
    if 'master_uri' not in opts:
        opts['master_uri'] = 'tcp://{ip}:{port}'.format(
            ip=salt.utils.ip_bracket(opts['interface']),
            port=opts['ret_port']
        )

    # Return the client options
    _validate_opts(opts)
    return opts


def api_config(path):
    '''
    Read in the salt master config file and add additional configs that
    need to be stubbed out for salt-api
    '''
    # Let's grab a copy of salt's master default opts
    defaults = DEFAULT_MASTER_OPTS
    # Let's override them with salt-api's required defaults
    defaults.update(DEFAULT_API_OPTS)

    return client_config(path, defaults=defaults)
