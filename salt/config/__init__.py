# -*- coding: utf-8 -*-
'''
All salt configuration loading and defaults should be in this module
'''

from __future__ import absolute_import, generators

# Import python libs
import os
import re
import sys
import glob
import time
import codecs
import logging
from copy import deepcopy
import types

# Import third party libs
import yaml
try:
    yaml.Loader = yaml.CLoader
    yaml.Dumper = yaml.CDumper
except Exception:
    pass

# pylint: disable=import-error,no-name-in-module
import salt.ext.six as six
from salt.ext.six import string_types, text_type
from salt.ext.six.moves.urllib.parse import urlparse
# pylint: enable=import-error,no-name-in-module

# Import salt libs
import salt.utils
import salt.utils.dictupdate
import salt.utils.network
import salt.syspaths
import salt.utils.validate.path
import salt.utils.xdg
import salt.exceptions
import salt.utils.sdb
from salt.utils.locales import sdecode

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
else:
    _DFLT_IPC_MODE = 'ipc'

FLO_DIR = os.path.join(
        os.path.dirname(__file__),
        'daemons', 'flo')

VALID_OPTS = {
    # The address of the salt master. May be specified as IP address or hostname
    'master': str,

    # The TCP/UDP port of the master to connect to in order to listen to publications
    'master_port': int,

    # The behaviour of the minion when connecting to a master. Can specify 'failover',
    # or 'func'. If 'func' is specified, the 'master' option should be set to an exec
    # module function to run to determine the master hostname.
    'master_type': str,

    # Specify the format in which the master address will be specified. Can
    # specify 'default' or 'ip_only'. If 'ip_only' is specified, then the
    # master address will not be split into IP and PORT.
    'master_uri_format': str,

    # The fingerprint of the master key may be specified to increase security. Generate
    # a master fingerprint with `salt-key -F master`
    'master_finger': str,

    # Selects a random master when starting a minion up in multi-master mode
    'master_shuffle': bool,

    # When in multi-master mode, temporarily remove a master from the list if a conenction
    # is interrupted and try another master in the list.
    'master_alive_interval': int,

    # The name of the signing key-pair
    'master_sign_key_name': str,

    # Sign the master auth-replies with a cryptographic signature of the masters public key.
    'master_sign_pubkey': bool,

    # Enables verification of the master-public-signature returned by the master in auth-replies.
    # Must also set master_sign_pubkey for this to work
    'verify_master_pubkey_sign': bool,

    # If verify_master_pubkey_sign is enabled, the signature is only verified, if the public-key of the master changes.
    # If the signature should always be verified, this can be set to True.
    'always_verify_signature': bool,

    # The name of the file in the masters pki-directory that holds the pre-calculated signature of the masters public-key.
    'master_pubkey_signature': str,

    # Instead of computing the signature for each auth-reply, use a pre-calculated signature.
    # The master_pubkey_signature must also be set for this.
    'master_use_pubkey_signature': bool,

    # The key fingerprint of the higher-level master for the syndic to verify it is talking to the intended
    # master
    'syndic_finger': str,

    # The user under which the daemon should run
    'user': str,

    # The root directory prepended to these options: pki_dir, cachedir,
    # sock_dir, log_file, autosign_file, autoreject_file, extension_modules,
    # key_logfile, pidfile:
    'root_dir': str,

    # The directory used to store public key data
    'pki_dir': str,

    # A unique identifier for this daemon
    'id': str,

    # The directory to store all cache files.
    'cachedir': str,

    # Flag to cache jobs locally.
    'cache_jobs': bool,

    # The path to the salt configuration file
    'conf_file': str,

    # The directory containing unix sockets for things like the event bus
    'sock_dir': str,

    # Specifies how the file server should backup files, if enabled. The backups
    # live in the cache dir.
    'backup_mode': str,

    # A default renderer for all operations on this host
    'renderer': str,

    # A flag indicating that a highstate run should immediately cease if a failure occurs.
    'failhard': bool,

    # A flag to indicate that highstate runs should force refresh the modules prior to execution
    'autoload_dynamic_modules': bool,

    # Force the minion into a single environment when it fetches files from the master
    'environment': str,

    # Force the minion into a single pillar root when it fetches pillar data from the master
    'pillarenv': str,

    # Allows a user to provide an alternate name for top.sls
    'state_top': str,

    'state_top_saltenv': str,

    # States to run when a minion starts up
    'startup_states': str,

    # List of startup states
    'sls_list': list,

    # A top file to execute if startup_states == 'top'
    'top_file': str,

    # Location of the files a minion should look for. Set to 'local' to never ask the master.
    'file_client': str,

    # When using a local file_client, this parameter is used to allow the client to connect to
    # a master for remote execution.
    'use_master_when_local': bool,

    # A map of saltenvs and fileserver backend locations
    'file_roots': dict,

    # A map of saltenvs and fileserver backend locations
    'pillar_roots': dict,

    # The type of hashing algorithm to use when doing file comparisons
    'hash_type': str,

    # FIXME Does not appear to be implemented
    'disable_modules': list,

    # FIXME Does not appear to be implemented
    'disable_returners': list,

    # Tell the loader to only load modules in this list
    'whitelist_modules': list,

    # A list of additional directories to search for salt modules in
    'module_dirs': list,

    # A list of additional directories to search for salt returners in
    'returner_dirs': list,

    # A list of additional directories to search for salt states in
    'states_dirs': list,

    # A list of additional directories to search for salt grains in
    'grains_dirs': list,

    # A list of additional directories to search for salt renderers in
    'render_dirs': list,

    # A list of additional directories to search for salt outputters in
    'outputter_dirs': list,

    # A list of additional directories to search for salt utilities in. (Used by the loader
    # to populate __utils__)
    'utils_dirs': list,

    # salt cloud providers
    'providers': dict,

    # First remove all modules during any sync operation
    'clean_dynamic_modules': bool,

    # A flag indicating that a master should accept any minion connection without any authentication
    'open_mode': bool,

    # Whether or not processes should be forked when needed. The alternative is to use threading.
    'multiprocessing': bool,

    # Whether or not the salt minion should run scheduled mine updates
    'mine_enabled': bool,

    # Whether or not scheduled mine updates should be accompanied by a job return for the job cache
    'mine_return_job': bool,

    # Schedule a mine update every n number of seconds
    'mine_interval': int,

    # The ipc strategy. (i.e., sockets versus tcp, etc)
    'ipc_mode': str,

    # Enable ipv6 support for daemons
    'ipv6': bool,

    # The chunk size to use when streaming files with the file server
    'file_buffer_size': int,

    # The TCP port on which minion events should be published if ipc_mode is TCP
    'tcp_pub_port': int,

    # The TCP port on which minion events should be pulled if ipc_mode is TCP
    'tcp_pull_port': int,

    # The TCP port on which events for the master should be pulled if ipc_mode is TCP
    'tcp_master_pub_port': int,

    # The TCP port on which events for the master should be pulled if ipc_mode is TCP
    'tcp_master_pull_port': int,

    # The TCP port on which events for the master should pulled and then republished onto
    # the event bus on the master
    'tcp_master_publish_pull': int,

    # The TCP port for mworkers to connect to on the master
    'tcp_master_workers': int,

    # The file to send logging data to
    'log_file': str,

    # The level of verbosity at which to log
    'log_level': str,

    # The log level to log to a given file
    'log_level_logfile': bool,

    # The format to construct dates in log files
    'log_datefmt': str,

    # The dateformat for a given logfile
    'log_datefmt_logfile': str,

    # The format for console logs
    'log_fmt_console': str,

    # The format for a given log file
    'log_fmt_logfile': tuple,

    # A dictionary of logging levels
    'log_granular_levels': dict,

    # If an event is above this size, it will be trimmed before putting it on the event bus
    'max_event_size': int,

    # Always execute states with test=True if this flag is set
    'test': bool,

    # Tell the loader to attempt to import *.pyx cython files if cython is available
    'cython_enable': bool,

    # Tell the loader to attempt to import *.zip archives
    'enable_zip_modules': bool,

    # Tell the client to show minions that have timed out
    'show_timeout': bool,

    # Tell the client to display the jid when a job is published
    'show_jid': bool,

    # Tells the highstate outputter to show successful states. False will omit successes.
    'state_verbose': bool,

    # Specify the format for state outputs. See highstate outputter for additional details.
    'state_output': str,

    # Tells the highstate outputter to only report diffs of states that changed
    'state_output_diff': bool,

    # When true, states run in the order defined in an SLS file, unless requisites re-order them
    'state_auto_order': bool,

    # Fire events as state chunks are processed by the state compiler
    'state_events': bool,

    # The number of seconds a minion should wait before retry when attempting authentication
    'acceptance_wait_time': float,

    # The number of seconds a minion should wait before giving up during authentication
    'acceptance_wait_time_max': float,

    # Retry a connection attempt if the master rejects a minion's public key
    'rejected_retry': bool,

    # The interval in which a daemon's main loop should attempt to perform all necessary tasks
    # for normal operation
    'loop_interval': float,

    # Perform pre-flight verification steps before daemon startup, such as checking configuration
    # files and certain directories.
    'verify_env': bool,

    # The grains dictionary for a minion, containing specific "facts" about the minion
    'grains': dict,

    # Allow a daemon to function even if the key directories are not secured
    'permissive_pki_access': bool,

    # The path to a directory to pull in configuration file includes
    'default_include': str,

    # If a minion is running an esky build of salt, upgrades can be performed using the url
    # defined here. See saltutil.update() for additional information
    'update_url': bool,

    # If using update_url with saltutil.update(), provide a list of services to be restarted
    # post-install
    'update_restart_services': list,

    # The number of seconds to sleep between retrying an attempt to resolve the hostname of a
    # salt master
    'retry_dns': float,

    # set the zeromq_reconnect_ivl option on the minion.
    # http://lists.zeromq.org/pipermail/zeromq-dev/2011-January/008845.html
    'recon_max': float,

    # If recon_randomize is set, this specifies the lower bound for the randomized period
    'recon_default': float,

    # Tells the minion to choose a bounded, random interval to have zeromq attempt to reconnect
    # in the event of a disconnect event
    'recon_randomize': float,  # FIXME This should really be a bool, according to the implementation

    'return_retry_timer': int,
    'return_retry_timer_max': int,

    # Specify a returner in which all events will be sent to. Requires that the returner in question
    # have an event_return(event) function!
    'event_return': str,

    # The number of events to queue up in memory before pushing them down the pipe to an event returner
    # specified by 'event_return'
    'event_return_queue': int,

    # Only forward events to an event returner if it matches one of the tags in this list
    'event_return_whitelist': list,

    # Events matching a tag in this list should never be sent to an event returner.
    'event_return_blacklist': list,

    # default match type for filtering events tags: startswith, endswith, find, regex, fnmatch
    'event_match_type': str,

    # This pidfile to write out to when a daemon starts
    'pidfile': str,

    # Used with the SECO range master tops system
    'range_server': str,

    # The tcp keepalive interval to set on TCP ports. This setting can be used to tune salt connectivity
    # issues in messy network environments with misbehaving firewalls
    'tcp_keepalive': bool,

    # Sets zeromq TCP keepalive idle. May be used to tune issues with minion disconnects
    'tcp_keepalive_idle': float,

    # Sets zeromq TCP keepalive count. May be used to tune issues with minion disconnects
    'tcp_keepalive_cnt': float,

    # Sets zeromq TCP keepalive interval. May be used to tune issues with minion disconnects.
    'tcp_keepalive_intvl': float,

    # The network interface for a daemon to bind to
    'interface': str,

    # The port for a salt master to broadcast publications on. This will also be the port minions
    # connect to to listen for publications.
    'publish_port': int,

    # TODO unknown option!
    'auth_mode': int,

    # Set the zeromq high water mark on the publisher interface.
    # http://api.zeromq.org/3-2:zmq-setsockopt
    'pub_hwm': int,

    # ZMQ HWM for SaltEvent pub socket
    'salt_event_pub_hwm': int,
    # ZMQ HWM for EventPublisher pub socket
    'event_publisher_pub_hwm': int,

    # The number of MWorker processes for a master to startup. This number needs to scale up as
    # the number of connected minions increases.
    'worker_threads': int,

    # The port for the master to listen to returns on. The minion needs to connect to this port
    # to send returns.
    'ret_port': int,

    # The number of hours to keep jobs around in the job cache on the master
    'keep_jobs': int,

    # A master-only copy of the file_roots dictionary, used by the state compiler
    'master_roots': dict,

    # Add the proxymodule LazyLoader object to opts.  This breaks many things
    # but this was the default pre 2015.8.2.  This should default to
    # False in 2016.3.0
    'add_proxymodule_to_opts': bool,
    'git_pillar_base': str,
    'git_pillar_branch': str,
    'git_pillar_env': str,
    'git_pillar_root': str,
    'git_pillar_ssl_verify': bool,
    'git_pillar_user': str,
    'git_pillar_password': str,
    'git_pillar_insecure_auth': bool,
    'git_pillar_privkey': str,
    'git_pillar_pubkey': str,
    'git_pillar_passphrase': str,
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
    'gitfs_ssl_verify': bool,
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

    # Specify a list of external pillar systems to use
    'ext_pillar': list,

    # Reserved for future use to version the pillar structure
    'pillar_version': int,

    # Whether or not a copy of the master opts dict should be rendered into minion pillars
    'pillar_opts': bool,

    # Cache the master pillar to disk to avoid having to pass through the rendering system
    'pillar_cache': bool,

    # Pillar cache TTL, in seconds. Has no effect unless `pillar_cache` is True
    'pillar_cache_ttl': int,

    # Pillar cache backend. Defaults to `disk` which stores caches in the master cache
    'pillar_cache_backend': str,

    'pillar_safe_render_error': bool,

    # When creating a pillar, there are several strategies to choose from when
    # encountering duplicate values
    'pillar_source_merging_strategy': str,

    # Recursively merge lists by aggregating them instead of replacing them.
    'pillar_merge_lists': bool,

    # How to merge multiple top files from multiple salt environments
    # (saltenvs); can be 'merge' or 'same'
    'top_file_merging_strategy': str,

    # The ordering for salt environment merging, when top_file_merging_strategy
    # is set to 'same'
    'env_order': list,

    # The salt environment which provides the default top file when
    # top_file_merging_strategy is set to 'same'; defaults to 'base'
    'default_top': str,

    'ping_on_rotate': bool,
    'peer': dict,
    'preserve_minion_cache': bool,
    'syndic_master': str,
    'runner_dirs': list,
    'client_acl': dict,
    'client_acl_blacklist': dict,
    'publisher_acl': dict,
    'publisher_acl_blacklist': dict,
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

    # The number of open files a daemon is allowed to have open. Frequently needs to be increased
    # higher than the system default in order to account for the way zeromq consumes file handles.
    'max_open_files': int,

    # Automatically accept any key provided to the master. Implies that the key will be preserved
    # so that subsequent connections will be authenticated even if this option has later been
    # turned off.
    'auto_accept': bool,
    'autosign_timeout': int,

    # A mapping of external systems that can be used to generate topfile data.
    # FIXME Should be dict?
    'master_tops': bool,

    # A flag that should be set on a top-level master when it is ordering around subordinate masters
    # via the use of a salt syndic
    'order_masters': bool,

    # Whether or not to cache jobs so that they can be examined later on
    'job_cache': bool,

    # Define a returner to be used as an external job caching storage backend
    'ext_job_cache': str,

    # Specify a returner for the master to use as a backend storage system to cache jobs returns
    # that it receives
    'master_job_cache': str,

    # Specify whether the master should store end times for jobs as returns come in
    'job_cache_store_endtime': bool,

    # The minion data cache is a cache of information about the minions stored on the master.
    # This information is primarily the pillar and grains data. The data is cached in the master
    # cachedir under the name of the minion and used to predetermine what minions are expected to
    # reply from executions.
    'minion_data_cache': bool,

    # The number of seconds between AES key rotations on the master
    'publish_session': int,

    # Defines a salt reactor. See http://docs.saltstack.com/en/latest/topics/reactor/
    'reactor': list,

    # The TTL for the cache of the reactor configuration
    'reactor_refresh_interval': int,

    # The number of workers for the runner/wheel in the reactor
    'reactor_worker_threads': int,

    # The queue size for workers in the reactor
    'reactor_worker_hwm': int,

    'serial': str,
    'search': str,

    # The update interval, in seconds, for the master maintenance process to update the search
    # index
    'search_index_interval': int,

    # A compound target definition. See: http://docs.saltstack.com/en/latest/topics/targeting/nodegroups.html
    'nodegroups': dict,

    # List-only nodegroups for salt-ssh. Each group must be formed as either a
    # comma-separated list, or a YAML list.
    'ssh_list_nodegroups': dict,

    # The logfile location for salt-key
    'key_logfile': str,

    # The source location for the winrepo sls files
    # (used by win_pkg.py, minion only)
    'winrepo_source_dir': str,

    'winrepo_dir': str,
    'winrepo_dir_ng': str,
    'winrepo_cachefile': str,
    'winrepo_remotes': list,
    'winrepo_remotes_ng': list,
    'winrepo_branch': str,
    'winrepo_ssl_verify': bool,
    'winrepo_user': str,
    'winrepo_password': str,
    'winrepo_insecure_auth': bool,
    'winrepo_privkey': str,
    'winrepo_pubkey': str,
    'winrepo_passphrase': str,

    # Set a hard limit for the amount of memory modules can consume on a minion.
    'modules_max_memory': int,

    # The number of minutes between the minion refreshing its cache of grains
    'grains_refresh_every': int,

    # Use lspci to gather system data for grains on a minion
    'enable_lspci': bool,

    # The number of seconds for the salt client to wait for additional syndics to
    # check in with their lists of expected minions before giving up
    'syndic_wait': int,

    # If this is set to True leading spaces and tabs are stripped from the start
    # of a line to a block.
    'jinja_lstrip_blocks': bool,

    # If this is set to True the first newline after a Jinja block is removed
    'jinja_trim_blocks': bool,

    # FIXME Appears to be unused
    'minion_id_caching': bool,

    # If set, the master will sign all publications before they are sent out
    'sign_pub_messages': bool,

    # The size of key that should be generated when creating new keys
    'keysize': int,

    # The transport system for this daemon. (i.e. zeromq, raet, etc)
    'transport': str,

    # FIXME Appears to be unused
    'enumerate_proxy_minions': bool,

    # The number of seconds to wait when the client is requesting information about running jobs
    'gather_job_timeout': int,

    # The number of seconds to wait before timing out an authentication request
    'auth_timeout': int,

    # The number of attempts to authenticate to a master before giving up
    'auth_tries': int,

    # Never give up when trying to authenticate to a master
    'auth_safemode': bool,

    'random_master': bool,

    # An upper bound for the amount of time for a minion to sleep before attempting to
    # reauth after a restart.
    'random_reauth_delay': int,

    # The number of seconds for a syndic to poll for new messages that need to be forwarded
    'syndic_event_forward_timeout': float,

    # The number of seconds for the syndic to spend polling the event bus
    'syndic_max_event_process_time': float,

    # The length that the syndic event queue must hit before events are popped off and forwarded
    'syndic_jid_forward_cache_hwm': int,

    'ssh_passwd': str,
    'ssh_port': str,
    'ssh_sudo': bool,
    'ssh_timeout': float,
    'ssh_user': str,
    'ssh_scan_ports': str,
    'ssh_scan_timeout': float,
    'ssh_identities_only': bool,

    # Enable ioflo verbose logging. Warning! Very verbose!
    'ioflo_verbose': int,

    'ioflo_period': float,

    # Set ioflo to realtime. Useful only for testing/debugging to simulate many ioflo periods very quickly.
    'ioflo_realtime': bool,

    # Location for ioflo logs
    'ioflo_console_logdir': str,

    # The port to bind to when bringing up a RAET daemon
    'raet_port': int,
    'raet_alt_port': int,
    'raet_mutable': bool,
    'raet_main': bool,
    'raet_clear_remotes': bool,
    'raet_clear_remote_masters': bool,
    'raet_road_bufcnt': int,
    'raet_lane_bufcnt': int,
    'cluster_mode': bool,
    'cluster_masters': list,
    'sqlite_queue_dir': str,

    'queue_dirs': list,

    # Instructs the minion to ping its master(s) ever n number of seconds. Used
    # primarily as a mitigation technique against minion disconnects.
    'ping_interval': int,

    # Instructs the salt CLI to print a summary of a minion responses before returning
    'cli_summary': bool,

    # The maximum number of minion connections allowed by the master. Can have performance
    # implications in large setups.
    'max_minions': int,


    'username': str,
    'password': str,

    # Use zmq.SUSCRIBE to limit listening sockets to only process messages bound for them
    'zmq_filtering': bool,

    # Connection caching. Can greatly speed up salt performance.
    'con_cache': bool,
    'rotate_aes_key': bool,

    # Cache ZeroMQ connections. Can greatly improve salt performance.
    'cache_sreqs': bool,

    # Can be set to override the python_shell=False default in the cmd module
    'cmd_safe': bool,

    # Used strictly for performance testing in RAET.
    'dummy_publisher': bool,

    # Used by salt-api for master requests timeout
    'rest_timeout': int,

    # If set, all minion exec module actions will be rerouted through sudo as this user
    'sudo_user': str,

    # HTTP request timeout in seconds. Applied for tornado http fetch functions like cp.get_url should be greater than
    # overall download time.
    'http_request_timeout': float,

    # HTTP request max file content size.
    'http_max_body': int,

    # Delay in seconds before executing bootstrap (salt cloud)
    'bootstrap_delay': int,
}

# default configurations
DEFAULT_MINION_OPTS = {
    'interface': '0.0.0.0',
    'master': 'salt',
    'master_type': 'str',
    'master_uri_format': 'default',
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
    'id': '',
    'cachedir': os.path.join(salt.syspaths.CACHE_DIR, 'minion'),
    'cache_jobs': False,
    'grains_cache': False,
    'grains_cache_expiration': 300,
    'grains_deep_merge': False,
    'conf_file': os.path.join(salt.syspaths.CONFIG_DIR, 'minion'),
    'sock_dir': os.path.join(salt.syspaths.SOCK_DIR, 'minion'),
    'backup_mode': '',
    'renderer': 'yaml_jinja',
    'failhard': False,
    'autoload_dynamic_modules': True,
    'environment': None,
    'pillarenv': None,
    # `pillar_cache` and `pillar_ttl`
    # are not used on the minion but are unavoidably in the code path
    'pillar_cache': False,
    'pillar_cache_ttl': 3600,
    'pillar_cache_backend': 'disk',
    'extension_modules': os.path.join(salt.syspaths.CACHE_DIR, 'minion', 'extmods'),
    'state_top': 'top.sls',
    'state_top_saltenv': None,
    'startup_states': '',
    'sls_list': [],
    'top_file': '',
    'thorium_interval': 0.5,
    'thorium_roots': {
        'base': [salt.syspaths.BASE_THORIUM_ROOTS_DIR],
        },
    'file_client': 'remote',
    'use_master_when_local': False,
    'file_roots': {
        'base': [salt.syspaths.BASE_FILE_ROOTS_DIR,
                 salt.syspaths.SPM_FORMULA_PATH]
    },
    'top_file_merging_strategy': 'merge',
    'env_order': [],
    'default_top': 'base',
    'fileserver_limit_traversal': False,
    'file_recv': False,
    'file_recv_max_size': 100,
    'file_ignore_regex': None,
    'file_ignore_glob': None,
    'fileserver_backend': ['roots'],
    'fileserver_followsymlinks': True,
    'fileserver_ignoresymlinks': False,
    'pillar_roots': {
        'base': [salt.syspaths.BASE_PILLAR_ROOTS_DIR,
                 salt.syspaths.SPM_PILLAR_PATH]
    },
    'git_pillar_base': 'master',
    'git_pillar_branch': 'master',
    'git_pillar_env': '',
    'git_pillar_root': '',
    'git_pillar_ssl_verify': False,
    'git_pillar_user': '',
    'git_pillar_password': '',
    'git_pillar_insecure_auth': False,
    'git_pillar_privkey': '',
    'git_pillar_pubkey': '',
    'git_pillar_passphrase': '',
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
    'gitfs_ssl_verify': False,
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
    'multiprocessing': True,
    'mine_enabled': True,
    'mine_return_job': False,
    'mine_interval': 60,
    'ipc_mode': _DFLT_IPC_MODE,
    'ipv6': False,
    'file_buffer_size': 262144,
    'tcp_pub_port': 4510,
    'tcp_pull_port': 4511,
    'log_file': os.path.join(salt.syspaths.LOGS_DIR, 'minion'),
    'log_level': 'info',
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
    'enable_zip_modules': False,
    'state_verbose': True,
    'state_output': 'full',
    'state_output_diff': False,
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
    'return_retry_timer': 5,
    'return_retry_timer_max': 10,
    'random_reauth_delay': 10,
    'winrepo_source_dir': 'salt://win/repo-ng/',
    'winrepo_dir': os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR, 'win', 'repo'),
    'winrepo_dir_ng': os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR, 'win', 'repo-ng'),
    'winrepo_cachefile': 'winrepo.p',
    'winrepo_remotes': ['https://github.com/saltstack/salt-winrepo.git'],
    'winrepo_remotes_ng': ['https://github.com/saltstack/salt-winrepo-ng.git'],
    'winrepo_branch': 'master',
    'winrepo_ssl_verify': False,
    'winrepo_user': '',
    'winrepo_password': '',
    'winrepo_insecure_auth': False,
    'winrepo_privkey': '',
    'winrepo_pubkey': '',
    'winrepo_passphrase': '',
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
    'raet_clear_remote_masters': True,
    'raet_road_bufcnt': 2,
    'raet_lane_bufcnt': 100,
    'cluster_mode': False,
    'cluster_masters': [],
    'restart_on_error': False,
    'ping_interval': 0,
    'username': None,
    'password': None,
    'zmq_filtering': False,
    'zmq_monitor': False,
    'cache_sreqs': True,
    'cmd_safe': True,
    'sudo_user': '',
    'http_request_timeout': 1 * 60 * 60.0,  # 1 hour
    'http_max_body': 100 * 1024 * 1024 * 1024,  # 100GB
    # ZMQ HWM for SaltEvent pub socket - different for minion vs. master
    'salt_event_pub_hwm': 2000,
    # ZMQ HWM for EventPublisher pub socket - different for minion vs. master
    'event_publisher_pub_hwm': 1000,
    'event_match_type': 'startswith',
}

DEFAULT_MASTER_OPTS = {
    'interface': '0.0.0.0',
    'publish_port': '4505',
    'pub_hwm': 1000,
    # ZMQ HWM for SaltEvent pub socket - different for minion vs. master
    'salt_event_pub_hwm': 2000,
    # ZMQ HWM for EventPublisher pub socket - different for minion vs. master
    'event_publisher_pub_hwm': 1000,
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
        'base': [salt.syspaths.BASE_FILE_ROOTS_DIR,
                 salt.syspaths.SPM_FORMULA_PATH]
    },
    'master_roots': {
        'base': [salt.syspaths.BASE_MASTER_ROOTS_DIR],
    },
    'pillar_roots': {
        'base': [salt.syspaths.BASE_PILLAR_ROOTS_DIR,
                 salt.syspaths.SPM_PILLAR_PATH]
    },
    'thorium_interval': 0.5,
    'thorium_roots': {
        'base': [salt.syspaths.BASE_THORIUM_ROOTS_DIR],
        },
    'top_file_merging_strategy': 'merge',
    'env_order': [],
    'environment': None,
    'default_top': 'base',
    'file_client': 'local',
    'git_pillar_base': 'master',
    'git_pillar_branch': 'master',
    'git_pillar_env': '',
    'git_pillar_root': '',
    'git_pillar_ssl_verify': False,
    'git_pillar_user': '',
    'git_pillar_password': '',
    'git_pillar_insecure_auth': False,
    'git_pillar_privkey': '',
    'git_pillar_pubkey': '',
    'git_pillar_passphrase': '',
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
    'gitfs_ssl_verify': False,
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
    'pillar_merge_lists': False,
    'pillar_cache': False,
    'pillar_cache_ttl': 3600,
    'pillar_cache_backend': 'disk',
    'ping_on_rotate': False,
    'peer': {},
    'preserve_minion_cache': False,
    'syndic_master': '',
    'syndic_log_file': os.path.join(salt.syspaths.LOGS_DIR, 'syndic'),
    'syndic_pidfile': os.path.join(salt.syspaths.PIDFILE_DIR, 'salt-syndic.pid'),
    'runner_dirs': [],
    'outputter_dirs': [],
    'client_acl': {},
    'client_acl_blacklist': {},
    'publisher_acl': {},
    'publisher_acl_blacklist': {},
    'sudo_acl': False,
    'external_auth': {},
    'token_expire': 43200,
    'extension_modules': os.path.join(salt.syspaths.CACHE_DIR, 'master', 'extmods'),
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
    'state_top_saltenv': None,
    'master_tops': {},
    'order_masters': False,
    'job_cache': True,
    'ext_job_cache': '',
    'master_job_cache': 'local_cache',
    'job_cache_store_endtime': False,
    'minion_data_cache': True,
    'enforce_mine_cache': False,
    'ipc_mode': _DFLT_IPC_MODE,
    'ipv6': False,
    'tcp_master_pub_port': 4512,
    'tcp_master_pull_port': 4513,
    'tcp_master_publish_pull': 4514,
    'tcp_master_workers': 4515,
    'log_file': os.path.join(salt.syspaths.LOGS_DIR, 'master'),
    'log_level': 'info',
    'log_level_logfile': None,
    'log_datefmt': _DFLT_LOG_DATEFMT,
    'log_datefmt_logfile': _DFLT_LOG_DATEFMT_LOGFILE,
    'log_fmt_console': _DFLT_LOG_FMT_CONSOLE,
    'log_fmt_logfile': _DFLT_LOG_FMT_LOGFILE,
    'log_granular_levels': {},
    'pidfile': os.path.join(salt.syspaths.PIDFILE_DIR, 'salt-master.pid'),
    'publish_session': 86400,
    'range_server': 'range:80',
    'reactor': [],
    'reactor_refresh_interval': 60,
    'reactor_worker_threads': 10,
    'reactor_worker_hwm': 10000,
    'event_return': '',
    'event_return_queue': 0,
    'event_return_whitelist': [],
    'event_return_blacklist': [],
    'event_match_type': 'startswith',
    'serial': 'msgpack',
    'state_verbose': True,
    'state_output': 'full',
    'state_output_diff': False,
    'state_auto_order': True,
    'state_events': False,
    'state_aggregate': False,
    'search': '',
    'search_index_interval': 3600,
    'loop_interval': 60,
    'nodegroups': {},
    'ssh_list_nodegroups': {},
    'cython_enable': False,
    'enable_gpu_grains': False,
    # XXX: Remove 'key_logfile' support in 2014.1.0
    'key_logfile': os.path.join(salt.syspaths.LOGS_DIR, 'key'),
    'verify_env': True,
    'permissive_pki_access': False,
    'default_include': 'master.d/*.conf',
    'winrepo_dir': os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR, 'win', 'repo'),
    'winrepo_dir_ng': os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR, 'win', 'repo-ng'),
    'winrepo_cachefile': 'winrepo.p',
    'winrepo_remotes': ['https://github.com/saltstack/salt-winrepo.git'],
    'winrepo_remotes_ng': ['https://github.com/saltstack/salt-winrepo-ng.git'],
    'winrepo_branch': 'master',
    'winrepo_ssl_verify': False,
    'winrepo_user': '',
    'winrepo_password': '',
    'winrepo_insecure_auth': False,
    'winrepo_privkey': '',
    'winrepo_pubkey': '',
    'winrepo_passphrase': '',
    'syndic_wait': 5,
    'jinja_lstrip_blocks': False,
    'jinja_trim_blocks': False,
    'tcp_keepalive': True,
    'tcp_keepalive_idle': 300,
    'tcp_keepalive_cnt': -1,
    'tcp_keepalive_intvl': -1,
    'sign_pub_messages': False,
    'keysize': 2048,
    'transport': 'zeromq',
    'enumerate_proxy_minions': False,
    'gather_job_timeout': 10,
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
    'ssh_identities_only': False,
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
    'raet_clear_remote_masters': True,
    'raet_road_bufcnt': 2,
    'raet_lane_bufcnt': 100,
    'cluster_mode': False,
    'cluster_masters': [],
    'sqlite_queue_dir': os.path.join(salt.syspaths.CACHE_DIR, 'master', 'queues'),
    'queue_dirs': [],
    'cli_summary': False,
    'max_minions': 0,
    'master_sign_key_name': 'master_sign',
    'master_sign_pubkey': False,
    'master_pubkey_signature': 'master_pubkey_signature',
    'master_use_pubkey_signature': False,
    'zmq_filtering': False,
    'zmq_monitor': False,
    'con_cache': False,
    'rotate_aes_key': True,
    'cache_sreqs': True,
    'dummy_pub': False,
    'http_request_timeout': 1 * 60 * 60.0,  # 1 hour
    'http_max_body': 100 * 1024 * 1024 * 1024,  # 100GB
    'python2_bin': 'python2',
    'python3_bin': 'python3',
}


# ----- Salt Proxy Minion Configuration Defaults ----------------------------------->
# Note that proxies use the same config path as regular minions.  DEFAULT_MINION_OPTS
# is loaded first, then if we are setting up a proxy, the config is overwritten with
# these settings.
DEFAULT_PROXY_MINION_OPTS = {
    'conf_file': os.path.join(salt.syspaths.CONFIG_DIR, 'proxy'),
    'log_file': os.path.join(salt.syspaths.LOGS_DIR, 'proxy'),
    'add_proxymodule_to_opts': True,

    # Default multiprocessing to False since anything that needs
    # salt.vt will have trouble with our forking model.
    # Proxies with non-persistent (mostly REST API) connections
    # can change this back to True
    'multiprocessing': True
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
    'log_level': 'info',
    'log_level_logfile': None,
    'log_datefmt': _DFLT_LOG_DATEFMT,
    'log_datefmt_logfile': _DFLT_LOG_DATEFMT_LOGFILE,
    'log_fmt_console': _DFLT_LOG_FMT_CONSOLE,
    'log_fmt_logfile': _DFLT_LOG_FMT_LOGFILE,
    'log_granular_levels': {},
    'bootstrap_delay': None,
}

DEFAULT_API_OPTS = {
    # ----- Salt master settings overridden by Salt-API --------------------->
    'pidfile': '/var/run/salt-api.pid',
    'logfile': '/var/log/salt/api',
    'rest_timeout': 300,
    # <---- Salt master settings overridden by Salt-API ----------------------
}

DEFAULT_SPM_OPTS = {
    # ----- Salt master settings overridden by SPM --------------------->
    'conf_file': os.path.join(salt.syspaths.CONFIG_DIR, 'spm'),
    'formula_path': '/srv/spm/salt',
    'pillar_path': '/srv/spm/pillar',
    'reactor_path': '/srv/spm/reactor',
    'spm_logfile': '/var/log/salt/spm',
    'default_include': 'spm.d/*.conf',
    # spm_repos_config also includes a .d/ directory
    'spm_repos_config': '/etc/salt/spm.repos',
    'spm_cache_dir': os.path.join(salt.syspaths.CACHE_DIR, 'spm'),
    'spm_build_dir': '/srv/spm_build',
    'spm_build_exclude': ['CVS', '.hg', '.git', '.svn'],
    'spm_db': os.path.join(salt.syspaths.CACHE_DIR, 'spm', 'packages.db'),
    # <---- Salt master settings overridden by SPM ----------------------
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
    for saltenv, dirs in six.iteritems(opts['file_roots']):
        normalized_saltenv = six.text_type(saltenv)
        if normalized_saltenv != saltenv:
            opts['file_roots'][normalized_saltenv] = \
                opts['file_roots'].pop(saltenv)
        if not isinstance(dirs, (list, tuple)):
            opts['file_roots'][normalized_saltenv] = []
        opts['file_roots'][normalized_saltenv] = \
            _expand_glob_path(opts['file_roots'][normalized_saltenv])
    return opts['file_roots']


def _expand_glob_path(file_roots):
    '''
    Applies shell globbing to a set of directories and returns
    the expanded paths
    '''
    unglobbed_path = []
    for path in file_roots:
        try:
            if glob.has_magic(path):
                unglobbed_path.extend(glob.glob(path))
            else:
                unglobbed_path.append(path)
        except Exception:
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
    for key, val in six.iteritems(opts):
        if key in VALID_OPTS:
            if isinstance(VALID_OPTS[key](), list):
                if isinstance(val, VALID_OPTS[key]):
                    continue
                else:
                    errors.append(
                        err.format(key, val, type(val).__name__, 'list')
                    )
            if isinstance(VALID_OPTS[key](), dict):
                if isinstance(val, VALID_OPTS[key]):
                    continue
                else:
                    errors.append(
                        err.format(key, val, type(val).__name__, 'dict')
                    )
            else:
                try:
                    VALID_OPTS[key](val)
                    if isinstance(val, (list, dict)):
                        # We'll only get here if VALID_OPTS[key] is str or
                        # bool, and the passed value is a list/dict. Attempting
                        # to run int() or float() on a list/dict will raise an
                        # exception, but running str() or bool() on it will
                        # pass despite not being the correct type.
                        errors.append(
                            err.format(
                                key,
                                val,
                                type(val).__name__,
                                VALID_OPTS[key].__name__
                            )
                        )
                except ValueError:
                    errors.append(
                        err.format(key, val, type(val).__name__, VALID_OPTS[key])
                    )
                except TypeError:
                    errors.append(
                        err.format(key, val, type(val).__name__, VALID_OPTS[key])
                    )

    # RAET on Windows uses 'win32file.CreateMailslot()' for IPC. Due to this,
    # sock_dirs must start with '\\.\mailslot\' and not contain any colons.
    # We don't expect the user to know this, so we will fix up their path for
    # them if it isn't compliant.
    if (salt.utils.is_windows() and opts.get('transport') == 'raet' and
             'sock_dir' in opts and
             not opts['sock_dir'].startswith('\\\\.\\mailslot\\')):
        opts['sock_dir'] = (
                '\\\\.\\mailslot\\' + opts['sock_dir'].replace(':', ''))

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
            if not isinstance(conf_opts['id'], six.string_types):
                conf_opts['id'] = str(conf_opts['id'])
            else:
                conf_opts['id'] = sdecode(conf_opts['id'])
        for key, value in six.iteritems(conf_opts.copy()):
            if isinstance(value, text_type) and six.PY2:
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
                'Relative path \'{0}\' converted to existing absolute path '
                '\'{1}\''.format(path, _abspath)
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
            "The function '{0}()' defined in '{1}' is not yet using the "
            "new 'default_path' argument to `salt.config.load_config()`. "
            "As such, the '{2}' environment variable will be ignored".format(
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
                log.warning(
                    'Warning parsing configuration file: "include" path/glob '
                    "'{0}' matches no files".format(path)
                )

        for fn_ in sorted(glob.glob(path)):
            log.debug("Including configuration from '{0}'".format(fn_))
            opts = _read_conf_file(fn_)

            include = opts.get('include', [])
            if include:
                opts.update(include_config(include, fn_, verbose))

            salt.utils.dictupdate.update(configuration, opts)

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

    if path is not None and path.endswith('proxy'):
        defaults.update(DEFAULT_PROXY_MINION_OPTS)

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
        for key, value in six.iteritems(sdb_opts):
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
            # Let's try adding the provided path's directory name turns the
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
                '..',
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
        for alias, details in six.iteritems(providers):
            if isinstance(details, list):
                for detail in details:
                    if 'provider' not in detail and 'driver' not in detail:
                        raise salt.exceptions.SaltCloudConfigError(
                            'The cloud provider alias \'{0}\' has an entry '
                            'missing the required setting of either '
                            '\'provider\' or \'driver\'. Note that '
                            '\'provider\' has been deprecated, so the '
                            '\'driver\' notation should be used.'.format(
                                alias
                            )
                        )
                    elif 'provider' in detail:
                        salt.utils.warn_until(
                            'Nitrogen',
                            'The term \'provider\' is being deprecated in '
                            'favor of \'driver\'. Support for \'provider\' '
                            'will be removed in Salt Nitrogen. Please convert '
                            'your cloud provider configuration files to use '
                            '\'driver\'.'
                        )
                        driver = detail['provider']
                    elif 'driver' in detail:
                        driver = detail['driver']

                    if ':' in driver:
                        # Weird, but...
                        alias, driver = driver.split(':')

                    if alias not in config['providers']:
                        config['providers'][alias] = {}

                    detail['provider'] = '{0}:{1}'.format(alias, driver)
                    config['providers'][alias][driver] = detail
            elif isinstance(details, dict):
                if 'provider' not in details and 'driver' not in details:
                    raise salt.exceptions.SaltCloudConfigError(
                        'The cloud provider alias \'{0}\' has an entry '
                        'missing the required setting of either '
                        '\'provider\' or \'driver\''.format(alias)
                    )
                elif 'provider' in details:
                    salt.utils.warn_until(
                        'Nitrogen',
                        'The term \'provider\' is being deprecated in favor '
                        'of \'driver\' and support for \'provider\' will be '
                        'removed in Salt Nitrogen. Please convert your cloud '
                        'provider  configuration files to use \'driver\'.'
                    )
                    driver = details['provider']
                elif 'driver' in details:
                    driver = details['driver']
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
            # Since using "provider: <provider-engine>" is deprecated, alias provider
            # to use driver: "driver: <provider-engine>"
            if 'provider' in provider_config:
                provider_config['driver'] = provider_config.pop('provider')

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

    for key, val in six.iteritems(config):
        if key in ('conf_file', 'include', 'default_include', 'user'):
            continue
        if not isinstance(val, dict):
            raise salt.exceptions.SaltCloudConfigError(
                'The VM profiles configuration found in \'{0[conf_file]}\' is '
                'not in the proper format'.format(config)
            )
        val['profile'] = key
        vms[key] = val

    # Is any VM profile extending data!?
    for profile, details in six.iteritems(vms.copy()):
        if 'extends' not in details:
            if ':' in details['provider']:
                alias, driver = details['provider'].split(':')
                if alias not in providers or driver not in providers[alias]:
                    log.trace(
                        'The profile \'{0}\' is defining \'{1[provider]}\' '
                        'as the provider. Since there is no valid '
                        'configuration for that provider, the profile will be '
                        'removed from the available listing'.format(
                            profile,
                            details
                        )
                    )
                    vms.pop(profile)
                    continue

                if 'profiles' not in providers[alias][driver]:
                    providers[alias][driver]['profiles'] = {}
                providers[alias][driver]['profiles'][profile] = details

            if details['provider'] not in providers:
                log.trace(
                    'The profile \'{0}\' is defining \'{1[provider]}\' as the '
                    'provider. Since there is no valid configuration for '
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
                'The \'{0}\' profile is trying to extend data from \'{1}\' '
                'though \'{1}\' is not defined in the salt profiles loaded '
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
                    'The profile \'{0}\' is defining \'{1[provider]}\' as the '
                    'provider. Since there is no valid configuration for '
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
                    'The profile \'{0}\' is defining \'{1[provider]}\' as '
                    'the provider. Since there is no valid configuration '
                    'for that provider, the profile will be removed from '
                    'the available listing'.format(profile, extended)
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
    for name, settings in six.iteritems(config.copy()):
        if '.' in name:
            log.warning(
                'Please switch to the new providers configuration syntax'
            )

            # Let's help out and migrate the data
            config = old_to_new(config)

            # old_to_new will migrate the old data into the 'providers' key of
            # the config dictionary. Let's map it correctly
            for prov_name, prov_settings in six.iteritems(config.pop('providers')):
                config[prov_name] = prov_settings
            break

    providers = {}
    ext_count = 0
    for key, val in six.iteritems(config):
        if key in ('conf_file', 'include', 'default_include', 'user'):
            continue

        if not isinstance(val, (list, tuple)):
            val = [val]
        else:
            # Need to check for duplicate cloud provider entries per "alias" or
            # we won't be able to properly reference it.
            handled_providers = set()
            for details in val:
                if 'provider' not in details and 'driver' not in details:
                    if 'extends' not in details:
                        log.error(
                            'Please check your cloud providers configuration. '
                            "There's no 'driver', 'provider', nor 'extends' "
                            'definition referenced.'
                        )
                    continue

                # Since using "provider: <provider-engine>" is deprecated,
                # alias provider to use driver: "driver: <provider-engine>"
                if 'provider' in details:
                    details['driver'] = details.pop('provider')

                if details['driver'] in handled_providers:
                    log.error(
                        'You can only have one entry per cloud provider. For '
                        'example, if you have a cloud provider configuration '
                        'section named, \'production\', you can only have a '
                        'single entry for EC2, Joyent, Openstack, and so '
                        'forth.'
                    )
                    raise salt.exceptions.SaltCloudConfigError(
                        'The cloud provider alias \'{0}\' has multiple entries '
                        'for the \'{1[driver]}\' driver.'.format(key, details)
                    )
                handled_providers.add(details['driver'])

        for entry in val:
            # Since using "provider: <provider-engine>" is deprecated, alias provider
            # to use driver: "driver: <provider-engine>"
            if 'provider' in entry:
                salt.utils.warn_until(
                    'Nitrogen',
                    'The term \'provider\' is being deprecated in favor of '
                    '\'driver\'. Support for \'provider\' will be removed in '
                    'Salt Nitrogen. Please convert your cloud provider '
                    'configuration files to use \'driver\'.'
                )
                entry['driver'] = entry.pop('provider')

            if 'driver' not in entry:
                entry['driver'] = '-only-extendable-{0}'.format(ext_count)
                ext_count += 1

            if key not in providers:
                providers[key] = {}

            provider = entry['driver']
            if provider not in providers[key]:
                providers[key][provider] = entry

    # Is any provider extending data!?
    while True:
        keep_looping = False
        for provider_alias, entries in six.iteritems(providers.copy()):
            for driver, details in six.iteritems(entries):
                # Since using "provider: <provider-engine>" is deprecated,
                # alias provider to use driver: "driver: <provider-engine>"
                if 'provider' in details:
                    details['driver'] = details.pop('provider')

                # Set a holder for the defined profiles
                providers[provider_alias][driver]['profiles'] = {}

                if 'extends' not in details:
                    continue

                extends = details.pop('extends')

                if ':' in extends:
                    alias, provider = extends.split(':')
                    if alias not in providers:
                        raise salt.exceptions.SaltCloudConfigError(
                            'The \'{0}\' cloud provider entry in \'{1}\' is '
                            'trying to extend data from \'{2}\' though '
                            '\'{2}\' is not defined in the salt cloud '
                            'providers loaded data.'.format(
                                details['driver'],
                                provider_alias,
                                alias
                            )
                        )

                    if provider not in providers.get(alias):
                        raise salt.exceptions.SaltCloudConfigError(
                            'The \'{0}\' cloud provider entry in \'{1}\' is '
                            'trying to extend data from \'{2}:{3}\' though '
                            '\'{3}\' is not defined in \'{1}\''.format(
                                details['driver'],
                                provider_alias,
                                alias,
                                provider
                            )
                        )
                    details['extends'] = '{0}:{1}'.format(alias, provider)
                    # change provider details '-only-extendable-' to extended
                    # provider name
                    details['driver'] = provider
                elif providers.get(extends):
                    raise salt.exceptions.SaltCloudConfigError(
                        'The \'{0}\' cloud provider entry in \'{1}\' is '
                        'trying to extend from \'{2}\' and no provider was '
                        'specified. Not extending!'.format(
                            details['driver'], provider_alias, extends
                        )
                    )
                elif extends not in providers:
                    raise salt.exceptions.SaltCloudConfigError(
                        'The \'{0}\' cloud provider entry in \'{1}\' is '
                        'trying to extend data from \'{2}\' though \'{2}\' '
                        'is not defined in the salt cloud providers loaded '
                        'data.'.format(
                            details['driver'], provider_alias, extends
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
        for alias, entries in six.iteritems(providers.copy()):
            for driver, details in six.iteritems(entries):

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
    for provider_alias, entries in six.iteritems(providers.copy()):
        for driver, details in six.iteritems(entries.copy()):
            if not driver.startswith('-only-extendable-'):
                continue

            log.info(
                "There's at least one cloud driver under the '{0}' "
                'cloud provider alias which does not have the required '
                "'driver' setting. Removing it from the available "
                'providers listing.'.format(
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

        # Since using "provider: <provider-engine>" is deprecated, alias provider
        # to use driver: "driver: <provider-engine>"
        if 'provider' in vm_:
            vm_['driver'] = vm_.pop('provider')

        # Let's get the value from the provider, if present.
        if ':' in vm_['driver']:
            # The provider is defined as <provider-alias>:<driver-name>
            alias, driver = vm_['driver'].split(':')
            if alias in opts['providers'] and \
                    driver in opts['providers'][alias]:
                details = opts['providers'][alias][driver]
                if name in details:
                    if isinstance(value, dict):
                        value.update(details[name].copy())
                    else:
                        value = deepcopy(details[name])
        elif len(opts['providers'].get(vm_['driver'], ())) > 1:
            # The provider is NOT defined as <provider-alias>:<driver-name>
            # and there's more than one entry under the alias.
            # WARN the user!!!!
            log.error(
                "The '{0}' cloud provider definition has more than one "
                'entry. Your VM configuration should be specifying the '
                "provider as 'driver: {0}:<driver-engine>'. Since "
                "it's not, we're returning the first definition which "
                'might not be what you intended.'.format(
                    vm_['driver']
                )
            )

        if vm_['driver'] in opts['providers']:
            # There's only one driver defined for this provider. This is safe.
            alias_defs = opts['providers'].get(vm_['driver'])
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
        if isinstance(vm_[name], types.GeneratorType):
            value = next(vm_[name], '')
        else:
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
                log.warning(
                    "The required '{0}' configuration setting is missing "
                    "from the '{1}' driver, which is configured under the "
                    "'{2}' alias.".format(key, provider, alias)
                )
                return False
        # If we reached this far, there's a properly configured provider.
        # Return it!
        return opts['providers'][alias][driver]

    for alias, drivers in six.iteritems(opts['providers']):
        for driver, provider_details in six.iteritems(drivers):
            if driver != provider:
                continue

            # If we reached this far, we have a matching provider, let's see if
            # all required configuration keys are present and not None.
            skip_provider = False
            for key in required_keys:
                if provider_details.get(key, None) is None:
                    # This provider does not include all necessary keys,
                    # continue to next one.
                    log.warning(
                        "The required '{0}' configuration setting is "
                        "missing from the '{1}' driver, which is configured "
                        "under the '{2}' alias.".format(
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


def is_profile_configured(opts, provider, profile_name, vm_=None):
    '''
    Check if the requested profile contains the minimum required parameters for
    a profile.

    Required parameters include image and provider for all drivers, while some
    drivers also require size keys.

    .. versionadded:: 2015.8.0
    '''
    # Standard dict keys required by all drivers.
    required_keys = ['provider']
    alias, driver = provider.split(':')

    # Most drivers need an image to be specified, but some do not.
    non_image_drivers = ['vmware', 'nova', 'virtualbox']

    # Most drivers need a size, but some do not.
    non_size_drivers = ['opennebula', 'parallels', 'proxmox', 'scaleway',
                        'softlayer', 'softlayer_hw', 'vmware', 'vsphere', 'virtualbox']

    provider_key = opts['providers'][alias][driver]
    profile_key = opts['providers'][alias][driver]['profiles'][profile_name]

    # If cloning on Linode, size and image are not necessary.
    # They are obtained from the to-be-cloned VM.
    linode_cloning = False
    if driver == 'linode' and profile_key.get('clonefrom'):
        linode_cloning = True
        non_image_drivers.append('linode')
        non_size_drivers.append('linode')

    if driver not in non_image_drivers:
        required_keys.append('image')
    elif driver in ['vmware', 'virtualbox'] or linode_cloning:
        required_keys.append('clonefrom')
    elif driver == 'nova':
        nova_image_keys = ['image', 'block_device_mapping', 'block_device', 'boot_volume']
        if not any([key in provider_key for key in nova_image_keys]) and not any([key in profile_key for key in nova_image_keys]):
            required_keys.extend(nova_image_keys)

    if driver not in non_size_drivers:
        required_keys.append('size')

    # Check if image and/or size are supplied in the provider config. If either
    # one is present, remove it from the required_keys list.
    for item in list(required_keys):
        if item in provider_key:
            required_keys.remove(item)

    # If a vm_ dict was passed in, use that information to get any other configs
    # that we might have missed thus far, such as a option provided in a map file.
    if vm_:
        for item in list(required_keys):
            if item in vm_:
                required_keys.remove(item)

    # Check for remaining required parameters in the profile config.
    for item in required_keys:
        if profile_key.get(item, None) is None:
            # There's at least one required configuration item which is not set.
            log.error(
                "The required '{0}' configuration setting is missing from "
                "the '{1}' profile, which is configured under the '{2}' "
                'alias.'.format(item, profile_name, alias)
            )
            return False

    return True


def check_driver_dependencies(driver, dependencies):
    '''
    Check if the driver's dependencies are available.

    .. versionadded:: 2015.8.0

    driver
        The name of the driver.

    dependencies
        The dictionary of dependencies to check.
    '''
    ret = True
    for key, value in six.iteritems(dependencies):
        if value is False:
            log.warning(
                "Missing dependency: '{0}'. The {1} driver requires "
                "'{0}' to be installed.".format(
                    key,
                    driver
                )
            )
            ret = False

    return ret

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
                bname = salt.utils.to_bytes(name)
                if bname.startswith(codecs.BOM):  # Remove BOM if exists
                    name = salt.utils.to_str(bname.replace(codecs.BOM, '', 1))
            if name:
                log.debug('Using cached minion ID from {0}: {1}'.format(id_cache, name))
                return name, False
        except (IOError, OSError):
            pass
    if '__role' in opts and opts.get('__role') == 'minion':
        log.debug('Guessing ID. The id can be explicitly set in {0}'
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

    opts['__cli'] = os.path.basename(sys.argv[0])

    if len(opts['sock_dir']) > len(opts['cachedir']) + 10:
        opts['sock_dir'] = os.path.join(opts['cachedir'], '.salt-unix')

    # No ID provided. Will getfqdn save us?
    using_ip_for_id = False
    if not opts.get('id'):
        opts['id'], using_ip_for_id = get_id(
                opts,
                cache_minion_id=cache_minion_id)

    # it does not make sense to append a domain to an IP based id
    if not using_ip_for_id and 'append_domain' in opts:
        opts['id'] = _append_domain(opts)

    # Enabling open mode requires that the value be set to True, and
    # nothing else!
    opts['open_mode'] = opts['open_mode'] is True

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

    # if there is no beacons option yet, add an empty beacons dict
    if 'beacons' not in opts:
        opts['beacons'] = {}

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
    if not opts.get('id'):
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

    # Let's make sure `worker_threads` does not drop below 3 which has proven
    # to make `salt.modules.publish` not work under the test-suite.
    if opts['worker_threads'] < 3 and opts.get('peer', None):
        log.warning(
            "The 'worker_threads' setting on '{0}' cannot be lower than "
            '3. Resetting it to the default value of 3.'.format(
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


def spm_config(path):
    '''
    Read in the salt master config file and add additional configs that
    need to be stubbed out for spm

    .. versionadded:: 2015.8.0
    '''
    # Let's grab a copy of salt's master default opts
    defaults = DEFAULT_MASTER_OPTS
    # Let's override them with spm's required defaults
    defaults.update(DEFAULT_SPM_OPTS)

    overrides = load_config(path, 'SPM_CONFIG', DEFAULT_SPM_OPTS['conf_file'])
    default_include = overrides.get('default_include',
                                    defaults['default_include'])
    include = overrides.get('include', [])

    overrides.update(include_config(default_include, path, verbose=False))
    overrides.update(include_config(include, path, verbose=True))
    defaults = apply_master_config(overrides, defaults)
    defaults = apply_spm_config(overrides, defaults)
    return client_config(path, env_var='SPM_CONFIG', defaults=defaults)


def apply_spm_config(overrides, defaults):
    '''
    Returns the spm configurations dict.

    .. versionadded:: 2015.8.1
    '''
    opts = defaults.copy()
    if overrides:
        opts.update(overrides)

    # Prepend root_dir to other paths
    prepend_root_dirs = [
        'formula_path', 'pillar_path', 'reactor_path',
        'spm_cache_dir', 'spm_build_dir'
    ]

    # These can be set to syslog, so, not actual paths on the system
    for config_key in ('spm_logfile',):
        log_setting = opts.get(config_key, '')
        if log_setting is None:
            continue

        if urlparse(log_setting).scheme == '':
            prepend_root_dirs.append(config_key)

    prepend_root_dir(opts, prepend_root_dirs)
    return opts
