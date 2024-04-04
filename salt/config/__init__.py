"""
All salt configuration loading and defaults should be in this module
"""

import codecs
import glob
import logging
import os
import re
import sys
import time
import types
import urllib.parse
from copy import deepcopy

import salt.defaults.exitcodes
import salt.exceptions
import salt.features
import salt.syspaths
import salt.utils.data
import salt.utils.dictupdate
import salt.utils.files
import salt.utils.immutabletypes as immutabletypes
import salt.utils.network
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.user
import salt.utils.validate.path
import salt.utils.versions
import salt.utils.xdg
import salt.utils.yaml
from salt._logging import (
    DFLT_LOG_DATEFMT,
    DFLT_LOG_DATEFMT_LOGFILE,
    DFLT_LOG_FMT_CONSOLE,
    DFLT_LOG_FMT_JID,
    DFLT_LOG_FMT_LOGFILE,
)

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)

_DFLT_REFSPECS = ["+refs/heads/*:refs/remotes/origin/*", "+refs/tags/*:refs/tags/*"]
DEFAULT_INTERVAL = 60
DEFAULT_HASH_TYPE = "sha256"


if salt.utils.platform.is_windows():
    # Since an 'ipc_mode' of 'ipc' will never work on Windows due to lack of
    # support in ZeroMQ, we want the default to be something that has a
    # chance of working.
    _DFLT_IPC_MODE = "tcp"
    _DFLT_FQDNS_GRAINS = False
    _MASTER_TRIES = -1
    # This needs to be SYSTEM in order for salt-master to run as a Service
    # Otherwise, it will not respond to CLI calls
    _MASTER_USER = "SYSTEM"
elif salt.utils.platform.is_proxy():
    _DFLT_IPC_MODE = "ipc"
    _DFLT_FQDNS_GRAINS = False
    _MASTER_TRIES = 1
    _MASTER_USER = salt.utils.user.get_user()
elif salt.utils.platform.is_darwin():
    _DFLT_IPC_MODE = "ipc"
    # fqdn resolution can be very slow on macOS, see issue #62168
    _DFLT_FQDNS_GRAINS = False
    _MASTER_TRIES = 1
    _MASTER_USER = salt.utils.user.get_user()
else:
    _DFLT_IPC_MODE = "ipc"
    _DFLT_FQDNS_GRAINS = False
    _MASTER_TRIES = 1
    _MASTER_USER = salt.utils.user.get_user()


def _gather_buffer_space():
    """
    Gather some system data and then calculate
    buffer space.

    Result is in bytes.
    """
    if HAS_PSUTIL:
        # Oh good, we have psutil. This will be quick.
        total_mem = psutil.virtual_memory().total
    else:
        # Avoid loading core grains unless absolutely required
        import platform

        import salt.grains.core

        # We need to load up ``mem_total`` grain. Let's mimic required OS data.
        os_data = {"kernel": platform.system()}
        grains = salt.grains.core._memdata(os_data)
        total_mem = grains["mem_total"]
    # Return the higher number between 5% of the system memory and 10MiB
    return max([total_mem * 0.05, 10 << 20])


# For the time being this will be a fixed calculation
# TODO: Allow user configuration
_DFLT_IPC_WBUFFER = int(_gather_buffer_space() * 0.5)
# TODO: Reserved for future use
_DFLT_IPC_RBUFFER = int(_gather_buffer_space() * 0.5)

VALID_OPTS = immutabletypes.freeze(
    {
        # The address of the salt master. May be specified as IP address or hostname
        "master": (str, list),
        # The TCP/UDP port of the master to connect to in order to listen to publications
        "master_port": (str, int),
        # The behaviour of the minion when connecting to a master. Can specify 'failover',
        # 'disable', 'distributed', or 'func'. If 'func' is specified, the 'master' option should be
        # set to an exec module function to run to determine the master hostname. If 'disable' is
        # specified the minion will run, but will not try to connect to a master. If 'distributed'
        # is specified the minion will try to deterministically pick a master based on its' id.
        "master_type": str,
        # Specify the format in which the master address will be specified. Can
        # specify 'default' or 'ip_only'. If 'ip_only' is specified, then the
        # master address will not be split into IP and PORT.
        "master_uri_format": str,
        # The following options refer to the Minion only, and they specify
        # the details of the source address / port to be used when connecting to
        # the Master. This is useful when dealing with machines where due to firewall
        # rules you are restricted to use a certain IP/port combination only.
        "source_interface_name": str,
        "source_address": str,
        "source_ret_port": (str, int),
        "source_publish_port": (str, int),
        # The fingerprint of the master key may be specified to increase security. Generate
        # a master fingerprint with `salt-key -F master`
        "master_finger": str,
        # Deprecated in 2019.2.0. Use 'random_master' instead.
        # Do not remove! Keep as an alias for usability.
        "master_shuffle": bool,
        # When in multi-master mode, temporarily remove a master from the list if a connection
        # is interrupted and try another master in the list.
        "master_alive_interval": int,
        # When in multi-master failover mode, fail back to the first master in the list if it's back
        # online.
        "master_failback": bool,
        # When in multi-master mode, and master_failback is enabled ping the top master with this
        # interval.
        "master_failback_interval": int,
        # The name of the signing key-pair
        "master_sign_key_name": str,
        # Sign the master auth-replies with a cryptographic signature of the masters public key.
        "master_sign_pubkey": bool,
        # Enables verification of the master-public-signature returned by the master in auth-replies.
        # Must also set master_sign_pubkey for this to work
        "verify_master_pubkey_sign": bool,
        # If verify_master_pubkey_sign is enabled, the signature is only verified, if the public-key of
        # the master changes. If the signature should always be verified, this can be set to True.
        "always_verify_signature": bool,
        # The name of the file in the masters pki-directory that holds the pre-calculated signature of
        # the masters public-key
        "master_pubkey_signature": str,
        # Instead of computing the signature for each auth-reply, use a pre-calculated signature.
        # The master_pubkey_signature must also be set for this.
        "master_use_pubkey_signature": bool,
        # Enable master stats events to be fired, these events will contain information about
        # what commands the master is processing and what the rates are of the executions
        "master_stats": bool,
        "master_stats_event_iter": int,
        # The key fingerprint of the higher-level master for the syndic to verify it is talking to the
        # intended master
        "syndic_finger": str,
        # The caching mechanism to use for the PKI key store. Can substantially decrease master publish
        # times. Available types:
        # 'maint': Runs on a schedule as a part of the maintenance process.
        # '': Disable the key cache [default]
        "key_cache": str,
        # The user under which the daemon should run
        "user": str,
        # The root directory prepended to these options: pki_dir, cachedir,
        # sock_dir, log_file, autosign_file, autoreject_file, extension_modules,
        # key_logfile, pidfile:
        "root_dir": str,
        # The directory used to store public key data
        "pki_dir": str,
        # A unique identifier for this daemon
        "id": str,
        # When defined we operate this master as a part of a cluster.
        "cluster_id": str,
        # Defines the other masters in the cluster.
        "cluster_peers": list,
        # Use this location instead of pki dir for cluster. This allows users
        # to define where minion keys and the cluster private key will be
        # stored.
        "cluster_pki_dir": str,
        # Use a module function to determine the unique identifier. If this is
        # set and 'id' is not set, it will allow invocation of a module function
        # to determine the value of 'id'. For simple invocations without function
        # arguments, this may be a string that is the function name. For
        # invocations with function arguments, this may be a dictionary with the
        # key being the function name, and the value being an embedded dictionary
        # where each key is a function argument name and each value is the
        # corresponding argument value.
        "id_function": (dict, str),
        # The directory to store all cache files.
        "cachedir": str,
        # Append minion_id to these directories.  Helps with
        # multiple proxies and minions running on the same machine.
        # Allowed elements in the list: pki_dir, cachedir, extension_modules, pidfile
        "append_minionid_config_dirs": list,
        # Flag to cache jobs locally.
        "cache_jobs": bool,
        # The path to the salt configuration file
        "conf_file": str,
        # The directory containing unix sockets for things like the event bus
        "sock_dir": str,
        # The pool size of unix sockets, it is necessary to avoid blocking waiting for zeromq and tcp communications.
        "sock_pool_size": int,
        # Specifies how the file server should backup files, if enabled. The backups
        # live in the cache dir.
        "backup_mode": str,
        # A default renderer for all operations on this host
        "renderer": str,
        # Renderer whitelist. The only renderers from this list are allowed.
        "renderer_whitelist": list,
        # Renderer blacklist. Renderers from this list are disallowed even if specified in whitelist.
        "renderer_blacklist": list,
        # A flag indicating that a highstate run should immediately cease if a failure occurs.
        "failhard": bool,
        # A flag to indicate that highstate runs should force refresh the modules prior to execution
        "autoload_dynamic_modules": bool,
        # Force the minion into a single environment when it fetches files from the master
        "saltenv": (type(None), str),
        # Prevent saltenv from being overridden on the command line
        "lock_saltenv": bool,
        # Force the minion into a single pillar root when it fetches pillar data from the master
        "pillarenv": (type(None), str),
        # Make the pillarenv always match the effective saltenv
        "pillarenv_from_saltenv": bool,
        # Allows a user to provide an alternate name for top.sls
        "state_top": str,
        "state_top_saltenv": (type(None), str),
        # States to run when a minion starts up
        "startup_states": str,
        # List of startup states
        "sls_list": list,
        # Configuration for snapper in the state system
        "snapper_states": bool,
        "snapper_states_config": str,
        # A top file to execute if startup_states == 'top'
        "top_file": str,
        # Location of the files a minion should look for. Set to 'local' to never ask the master.
        "file_client": str,
        "local": bool,
        # When using a local file_client, this parameter is used to allow the client to connect to
        # a master for remote execution.
        "use_master_when_local": bool,
        # A map of saltenvs and fileserver backend locations
        "file_roots": dict,
        # A map of saltenvs and fileserver backend locations
        "pillar_roots": dict,
        # The external pillars permitted to be used on-demand using pillar.ext
        "on_demand_ext_pillar": list,
        # A map of glob paths to be used
        "decrypt_pillar": list,
        # Delimiter to use in path expressions for decrypt_pillar
        "decrypt_pillar_delimiter": str,
        # Default renderer for decrypt_pillar
        "decrypt_pillar_default": str,
        # List of renderers available for decrypt_pillar
        "decrypt_pillar_renderers": list,
        # Treat GPG decryption errors as renderer errors
        "gpg_decrypt_must_succeed": bool,
        # The type of hashing algorithm to use when doing file comparisons
        "hash_type": str,
        # Order of preference for optimized .pyc files (PY3 only)
        "optimization_order": list,
        # Refuse to load these modules
        "disable_modules": list,
        # Refuse to load these returners
        "disable_returners": list,
        # Tell the loader to only load modules in this list
        "whitelist_modules": list,
        # A list of additional directories to search for salt modules in
        "module_dirs": list,
        # A list of additional directories to search for salt returners in
        "returner_dirs": list,
        # A list of additional directories to search for salt states in
        "states_dirs": list,
        # A list of additional directories to search for salt grains in
        "grains_dirs": list,
        # A list of additional directories to search for salt renderers in
        "render_dirs": list,
        # A list of additional directories to search for salt outputters in
        "outputter_dirs": list,
        # A list of additional directories to search for salt utilities in. (Used by the loader
        # to populate __utils__)
        "utils_dirs": list,
        # salt cloud providers
        "providers": dict,
        # First remove all modules during any sync operation
        "clean_dynamic_modules": bool,
        # A flag indicating that a master should accept any minion connection without any authentication
        "open_mode": bool,
        # Whether or not processes should be forked when needed. The alternative is to use threading.
        "multiprocessing": bool,
        # Maximum number of concurrently active processes at any given point in time
        "process_count_max": int,
        # Whether or not the salt minion should run scheduled mine updates
        "mine_enabled": bool,
        # Whether or not scheduled mine updates should be accompanied by a job return for the job cache
        "mine_return_job": bool,
        # The number of minutes between mine updates.
        "mine_interval": int,
        # The ipc strategy. (i.e., sockets versus tcp, etc)
        "ipc_mode": str,
        # Enable ipv6 support for daemons
        "ipv6": (type(None), bool),
        # The chunk size to use when streaming files with the file server
        "file_buffer_size": int,
        # The TCP port on which minion events should be published if ipc_mode is TCP
        "tcp_pub_port": int,
        # The TCP port on which minion events should be pulled if ipc_mode is TCP
        "tcp_pull_port": int,
        # The TCP port on which events for the master should be published if ipc_mode is TCP
        "tcp_master_pub_port": int,
        # The TCP port on which events for the master should be pulled if ipc_mode is TCP
        "tcp_master_pull_port": int,
        # The TCP port on which events for the master should pulled and then republished onto
        # the event bus on the master
        "tcp_master_publish_pull": int,
        # The TCP port for mworkers to connect to on the master
        "tcp_master_workers": int,
        # The file to send logging data to
        "log_file": str,
        # The level of verbosity at which to log
        "log_level": str,
        # The log level to log to a given file
        "log_level_logfile": (type(None), str),
        # The format to construct dates in log files
        "log_datefmt": str,
        # The dateformat for a given logfile
        "log_datefmt_logfile": str,
        # The format for console logs
        "log_fmt_console": str,
        # The format for a given log file
        "log_fmt_logfile": (tuple, str),
        # A dictionary of logging levels
        "log_granular_levels": dict,
        # The maximum number of bytes a single log file may contain before
        # it is rotated. A value of 0 disables this feature.
        # Currently only supported on Windows. On other platforms, use an
        # external tool such as 'logrotate' to manage log files.
        "log_rotate_max_bytes": int,
        # The number of backup files to keep when rotating log files. Only
        # used if log_rotate_max_bytes is greater than 0.
        # Currently only supported on Windows. On other platforms, use an
        # external tool such as 'logrotate' to manage log files.
        "log_rotate_backup_count": int,
        # If an event is above this size, it will be trimmed before putting it on the event bus
        "max_event_size": int,
        # Enable old style events to be sent on minion_startup. Change default to False in 3001 release
        "enable_legacy_startup_events": bool,
        # Always execute states with test=True if this flag is set
        "test": bool,
        # Tell the loader to attempt to import *.pyx cython files if cython is available
        "cython_enable": bool,
        # Whether or not to load grains for FQDNs
        "enable_fqdns_grains": bool,
        # Whether or not to load grains for the GPU
        "enable_gpu_grains": bool,
        # Tell the loader to attempt to import *.zip archives
        "enable_zip_modules": bool,
        # Tell the client to show minions that have timed out
        "show_timeout": bool,
        # Tell the client to display the jid when a job is published
        "show_jid": bool,
        # Ensure that a generated jid is always unique. If this is set, the jid
        # format is different due to an underscore and process id being appended
        # to the jid. WARNING: A change to the jid format may break external
        # applications that depend on the original format.
        "unique_jid": bool,
        # Governs whether state runs will queue or fail to run when a state is already running
        "state_queue": (bool, int),
        # Tells the highstate outputter to show successful states. False will omit successes.
        "state_verbose": bool,
        # Specify the format for state outputs. See highstate outputter for additional details.
        "state_output": str,
        # Tells the highstate outputter to only report diffs of states that changed
        "state_output_diff": bool,
        # Tells the highstate outputter whether profile information will be shown for each state run
        "state_output_profile": bool,
        # Tells the highstate outputter whether success and failure percents will be shown for each state run
        "state_output_pct": bool,
        # Tells the highstate outputter to aggregate information about states which
        # have multiple "names" under the same state ID in the highstate output.
        "state_compress_ids": bool,
        # When true, states run in the order defined in an SLS file, unless requisites re-order them
        "state_auto_order": bool,
        # Fire events as state chunks are processed by the state compiler
        "state_events": bool,
        # The number of seconds a minion should wait before retry when attempting authentication
        "acceptance_wait_time": float,
        # The number of seconds a minion should wait before giving up during authentication
        "acceptance_wait_time_max": float,
        # Retry a connection attempt if the master rejects a minion's public key
        "rejected_retry": bool,
        # The interval in which a daemon's main loop should attempt to perform all necessary tasks
        # for normal operation
        "loop_interval": float,
        # Perform pre-flight verification steps before daemon startup, such as checking configuration
        # files and certain directories.
        "verify_env": bool,
        # The grains dictionary for a minion, containing specific "facts" about the minion
        "grains": dict,
        # Allow a daemon to function even if the key directories are not secured
        "permissive_pki_access": bool,
        # The passphrase of the master's private key
        "key_pass": (type(None), str),
        # The passphrase of the master cluster's private key
        "cluster_key_pass": (type(None), str),
        # The passphrase of the master's private signing key
        "signing_key_pass": (type(None), str),
        # The path to a directory to pull in configuration file includes
        "default_include": str,
        # If a minion is running an esky build of salt, upgrades can be performed using the url
        # defined here. See saltutil.update() for additional information
        "update_url": (bool, str),
        # If using update_url with saltutil.update(), provide a list of services to be restarted
        # post-install
        "update_restart_services": list,
        # The number of seconds to sleep between retrying an attempt to resolve the hostname of a
        # salt master
        "retry_dns": float,
        "retry_dns_count": (type(None), int),
        # In the case when the resolve of the salt master hostname fails, fall back to localhost
        "resolve_dns_fallback": bool,
        # set the zeromq_reconnect_ivl option on the minion.
        # http://lists.zeromq.org/pipermail/zeromq-dev/2011-January/008845.html
        "recon_max": float,
        # If recon_randomize is set, this specifies the lower bound for the randomized period
        "recon_default": float,
        # Tells the minion to choose a bounded, random interval to have zeromq attempt to reconnect
        # in the event of a disconnect event
        "recon_randomize": bool,
        # Configures retry interval, randomized between timer and timer_max if timer_max > 0
        "return_retry_timer": int,
        "return_retry_timer_max": int,
        # Configures amount of return retries
        "return_retry_tries": int,
        # Specify one or more returners in which all events will be sent to. Requires that the returners
        # in question have an event_return(event) function!
        "event_return": (list, str),
        # The number of events to queue up in memory before pushing them down the pipe to an event
        # returner specified by 'event_return'
        "event_return_queue": int,
        # The number of seconds that events can languish in the queue before we flush them.
        # The goal here is to ensure that if the bus is not busy enough to reach a total
        # `event_return_queue` events won't get stale.
        "event_return_queue_max_seconds": int,
        # Only forward events to an event returner if it matches one of the tags in this list
        "event_return_whitelist": list,
        # Events matching a tag in this list should never be sent to an event returner.
        "event_return_blacklist": list,
        # default match type for filtering events tags: startswith, endswith, find, regex, fnmatch
        "event_match_type": str,
        # This pidfile to write out to when a daemon starts
        "pidfile": str,
        # Used with the SECO range master tops system
        "range_server": str,
        # The tcp keepalive interval to set on TCP ports. This setting can be used to tune Salt
        # connectivity issues in messy network environments with misbehaving firewalls
        "tcp_keepalive": bool,
        # Sets zeromq TCP keepalive idle. May be used to tune issues with minion disconnects
        "tcp_keepalive_idle": float,
        # Sets zeromq TCP keepalive count. May be used to tune issues with minion disconnects
        "tcp_keepalive_cnt": float,
        # Sets zeromq TCP keepalive interval. May be used to tune issues with minion disconnects.
        "tcp_keepalive_intvl": float,
        # The network interface for a daemon to bind to
        "interface": str,
        # The port for a salt master to broadcast publications on. This will also be the port minions
        # connect to to listen for publications.
        "publish_port": int,
        # TODO unknown option!
        "auth_mode": int,
        # listen queue size / backlog
        "zmq_backlog": int,
        # Set the zeromq high water mark on the publisher interface.
        # http://api.zeromq.org/3-2:zmq-setsockopt
        "pub_hwm": int,
        # IPC buffer size
        # Refs https://github.com/saltstack/salt/issues/34215
        "ipc_write_buffer": int,
        # various subprocess niceness levels
        "req_server_niceness": (type(None), int),
        "pub_server_niceness": (type(None), int),
        "fileserver_update_niceness": (type(None), int),
        "maintenance_niceness": (type(None), int),
        "mworker_niceness": (type(None), int),
        "mworker_queue_niceness": (type(None), int),
        "event_return_niceness": (type(None), int),
        "event_publisher_niceness": (type(None), int),
        "reactor_niceness": (type(None), int),
        # The number of MWorker processes for a master to startup. This number needs to scale up as
        # the number of connected minions increases.
        "worker_threads": int,
        # The port for the master to listen to returns on. The minion needs to connect to this port
        # to send returns.
        "ret_port": int,
        # The number of hours to keep jobs around in the job cache on the master
        # This option is deprecated by keep_jobs_seconds
        "keep_jobs": int,
        # The number of seconds to keep jobs around in the job cache on the master
        "keep_jobs_seconds": int,
        # If the returner supports `clean_old_jobs`, then at cleanup time,
        # archive the job data before deleting it.
        "archive_jobs": bool,
        # A master-only copy of the file_roots dictionary, used by the state compiler
        "master_roots": dict,
        # Add the proxymodule LazyLoader object to opts.  This breaks many things
        # but this was the default pre 2015.8.2.  This should default to
        # False in 2016.3.0
        "add_proxymodule_to_opts": bool,
        # Merge pillar data into configuration opts.
        # As multiple proxies can run on the same server, we may need different
        # configuration options for each, while there's one single configuration file.
        # The solution is merging the pillar data of each proxy minion into the opts.
        "proxy_merge_pillar_in_opts": bool,
        # Deep merge of pillar data into configuration opts.
        # Evaluated only when `proxy_merge_pillar_in_opts` is True.
        "proxy_deep_merge_pillar_in_opts": bool,
        # The strategy used when merging pillar into opts.
        # Considered only when `proxy_merge_pillar_in_opts` is True.
        "proxy_merge_pillar_in_opts_strategy": str,
        # Allow enabling mine details using pillar data.
        "proxy_mines_pillar": bool,
        # In some particular cases, always alive proxies are not beneficial.
        # This option can be used in those less dynamic environments:
        # the user can request the connection
        # always alive, or init-shutdown per command.
        "proxy_always_alive": bool,
        # Poll the connection state with the proxy minion
        # If enabled, this option requires the function `alive`
        # to be implemented in the proxy module
        "proxy_keep_alive": bool,
        # Frequency of the proxy_keep_alive, in minutes
        "proxy_keep_alive_interval": int,
        # Update intervals
        "roots_update_interval": int,
        "gitfs_update_interval": int,
        "git_pillar_update_interval": int,
        "hgfs_update_interval": int,
        "minionfs_update_interval": int,
        "s3fs_update_interval": int,
        "svnfs_update_interval": int,
        # NOTE: git_pillar_base, git_pillar_fallback, git_pillar_branch,
        # git_pillar_env, and git_pillar_root omitted here because their values
        # could conceivably be loaded as non-string types, which is OK because
        # git_pillar will normalize them to strings. But rather than include all the
        # possible types they could be, we'll just skip type-checking.
        "git_pillar_ssl_verify": bool,
        "git_pillar_global_lock": bool,
        "git_pillar_user": str,
        "git_pillar_password": str,
        "git_pillar_insecure_auth": bool,
        "git_pillar_privkey": str,
        "git_pillar_pubkey": str,
        "git_pillar_passphrase": str,
        "git_pillar_refspecs": list,
        "git_pillar_includes": bool,
        "git_pillar_verify_config": bool,
        # NOTE: gitfs_base, gitfs_fallback, gitfs_mountpoint, and gitfs_root omitted
        # here because their values could conceivably be loaded as non-string types,
        # which is OK because gitfs will normalize them to strings. But rather than
        # include all the possible types they could be, we'll just skip type-checking.
        "gitfs_remotes": list,
        "gitfs_insecure_auth": bool,
        "gitfs_privkey": str,
        "gitfs_pubkey": str,
        "gitfs_passphrase": str,
        "gitfs_saltenv_whitelist": list,
        "gitfs_saltenv_blacklist": list,
        "gitfs_ssl_verify": bool,
        "gitfs_global_lock": bool,
        "gitfs_saltenv": list,
        "gitfs_ref_types": list,
        "gitfs_refspecs": list,
        "gitfs_disable_saltenv_mapping": bool,
        "hgfs_remotes": list,
        "hgfs_mountpoint": str,
        "hgfs_root": str,
        "hgfs_base": str,
        "hgfs_branch_method": str,
        "hgfs_saltenv_whitelist": list,
        "hgfs_saltenv_blacklist": list,
        "svnfs_remotes": list,
        "svnfs_mountpoint": str,
        "svnfs_root": str,
        "svnfs_trunk": str,
        "svnfs_branches": str,
        "svnfs_tags": str,
        "svnfs_saltenv_whitelist": list,
        "svnfs_saltenv_blacklist": list,
        "minionfs_env": str,
        "minionfs_mountpoint": str,
        "minionfs_whitelist": list,
        "minionfs_blacklist": list,
        # Specify a list of external pillar systems to use
        "ext_pillar": list,
        # Reserved for future use to version the pillar structure
        "pillar_version": int,
        # Whether or not a copy of the master opts dict should be rendered into minion pillars
        "pillar_opts": bool,
        # Cache the master pillar to disk to avoid having to pass through the rendering system
        "pillar_cache": bool,
        # Pillar cache TTL, in seconds. Has no effect unless `pillar_cache` is True
        "pillar_cache_ttl": int,
        # Pillar cache backend. Defaults to `disk` which stores caches in the master cache
        "pillar_cache_backend": str,
        # Cache the GPG data to avoid having to pass through the gpg renderer
        "gpg_cache": bool,
        # GPG data cache TTL, in seconds. Has no effect unless `gpg_cache` is True
        "gpg_cache_ttl": int,
        # GPG data cache backend. Defaults to `disk` which stores caches in the master cache
        "gpg_cache_backend": str,
        "pillar_safe_render_error": bool,
        # When creating a pillar, there are several strategies to choose from when
        # encountering duplicate values
        "pillar_source_merging_strategy": str,
        # Recursively merge lists by aggregating them instead of replacing them.
        "pillar_merge_lists": bool,
        # If True, values from included pillar SLS targets will override
        "pillar_includes_override_sls": bool,
        # How to merge multiple top files from multiple salt environments
        # (saltenvs); can be 'merge' or 'same'
        "top_file_merging_strategy": str,
        # The ordering for salt environment merging, when top_file_merging_strategy
        # is set to 'same'
        "env_order": list,
        # The salt environment which provides the default top file when
        # top_file_merging_strategy is set to 'same'; defaults to 'base'
        "default_top": str,
        "ping_on_rotate": bool,
        "peer": dict,
        "preserve_minion_cache": bool,
        "syndic_master": (str, list),
        # The behaviour of the multimaster syndic when connection to a master of masters failed. Can
        # specify 'random' (default) or 'ordered'. If set to 'random' masters will be iterated in random
        # order if 'ordered' the configured order will be used.
        "syndic_failover": str,
        "syndic_forward_all_events": bool,
        "runner_dirs": list,
        "client_acl_verify": bool,
        "publisher_acl": dict,
        "publisher_acl_blacklist": dict,
        "sudo_acl": bool,
        "external_auth": dict,
        "token_expire": int,
        "token_expire_user_override": (bool, dict),
        "file_recv": bool,
        "file_recv_max_size": int,
        "file_ignore_regex": (list, str),
        "file_ignore_glob": (list, str),
        "fileserver_backend": list,
        "fileserver_followsymlinks": bool,
        "fileserver_ignoresymlinks": bool,
        "fileserver_verify_config": bool,
        # Optionally apply '*' permissions to any user. By default '*' is a fallback case that is
        # applied only if the user didn't matched by other matchers.
        "permissive_acl": bool,
        # Optionally enables keeping the calculated user's auth list in the token file.
        "keep_acl_in_token": bool,
        # Auth subsystem module to use to get authorized access list for a user. By default it's the
        # same module used for external authentication.
        "eauth_acl_module": str,
        # Subsystem to use to maintain eauth tokens. By default, tokens are stored on the local
        # filesystem
        "eauth_tokens": str,
        # The number of open files a daemon is allowed to have open. Frequently needs to be increased
        # higher than the system default in order to account for the way zeromq consumes file handles.
        "max_open_files": int,
        # Automatically accept any key provided to the master. Implies that the key will be preserved
        # so that subsequent connections will be authenticated even if this option has later been
        # turned off.
        "auto_accept": bool,
        "autosign_timeout": int,
        # A mapping of external systems that can be used to generate topfile data.
        "master_tops": dict,
        # Whether or not matches from master_tops should be executed before or
        # after those from the top file(s).
        "master_tops_first": bool,
        # A flag that should be set on a top-level master when it is ordering around subordinate masters
        # via the use of a salt syndic
        "order_masters": bool,
        # Whether or not to cache jobs so that they can be examined later on
        "job_cache": bool,
        # Define a returner to be used as an external job caching storage backend
        "ext_job_cache": str,
        # Specify a returner for the master to use as a backend storage system to cache jobs returns
        # that it receives
        "master_job_cache": str,
        # Specify whether the master should store end times for jobs as returns come in
        "job_cache_store_endtime": bool,
        # The minion data cache is a cache of information about the minions stored on the master.
        # This information is primarily the pillar and grains data. The data is cached in the master
        # cachedir under the name of the minion and used to predetermine what minions are expected to
        # reply from executions.
        "minion_data_cache": bool,
        # The number of seconds between AES key rotations on the master
        "publish_session": int,
        # Defines a salt reactor. See https://docs.saltproject.io/en/latest/topics/reactor/
        "reactor": list,
        # The TTL for the cache of the reactor configuration
        "reactor_refresh_interval": int,
        # The number of workers for the runner/wheel in the reactor
        "reactor_worker_threads": int,
        # The queue size for workers in the reactor
        "reactor_worker_hwm": int,
        # Defines engines. See https://docs.saltproject.io/en/latest/topics/engines/
        "engines": list,
        # Whether or not to store runner returns in the job cache
        "runner_returns": bool,
        "serial": str,
        "search": str,
        # A compound target definition.
        # See: https://docs.saltproject.io/en/latest/topics/targeting/nodegroups.html
        "nodegroups": (dict, list),
        # List-only nodegroups for salt-ssh. Each group must be formed as either a
        # comma-separated list, or a YAML list.
        "ssh_list_nodegroups": dict,
        # By default, salt-ssh uses its own specially-generated RSA key to auth
        # against minions. If this is set to True, salt-ssh will look in
        # for a key at ~/.ssh/id_rsa, and fall back to using its own specially-
        # generated RSA key if that file doesn't exist.
        "ssh_use_home_key": bool,
        # The logfile location for salt-key
        "key_logfile": str,
        # The upper bound for the random number of seconds that a minion should
        # delay when starting in up before it connects to a master. This can be
        # used to mitigate a thundering-herd scenario when many minions start up
        # at once and attempt to all connect immediately to the master
        "random_startup_delay": int,
        # The source location for the winrepo sls files
        # (used by win_pkg.py, minion only)
        "winrepo_source_dir": str,
        "winrepo_dir": str,
        "winrepo_dir_ng": str,
        "winrepo_cachefile": str,
        # NOTE: winrepo_branch omitted here because its value could conceivably be
        # loaded as a non-string type, which is OK because winrepo will normalize
        # them to strings. But rather than include all the possible types it could
        # be, we'll just skip type-checking.
        "winrepo_cache_expire_max": int,
        "winrepo_cache_expire_min": int,
        "winrepo_remotes": list,
        "winrepo_remotes_ng": list,
        "winrepo_ssl_verify": bool,
        "winrepo_user": str,
        "winrepo_password": str,
        "winrepo_insecure_auth": bool,
        "winrepo_privkey": str,
        "winrepo_pubkey": str,
        "winrepo_passphrase": str,
        "winrepo_refspecs": list,
        # Set a hard limit for the amount of memory modules can consume on a minion.
        "modules_max_memory": int,
        # Blacklist specific core grains to be filtered
        "grains_blacklist": list,
        # The number of minutes between the minion refreshing its cache of grains
        "grains_refresh_every": int,
        # Enable grains refresh prior to any operation
        "grains_refresh_pre_exec": bool,
        # Use lspci to gather system data for grains on a minion
        "enable_lspci": bool,
        # The number of seconds for the salt client to wait for additional syndics to
        # check in with their lists of expected minions before giving up
        "syndic_wait": int,
        # Override Jinja environment option defaults for all templates except sls templates
        "jinja_env": dict,
        # Set Jinja environment options for sls templates
        "jinja_sls_env": dict,
        # If this is set to True leading spaces and tabs are stripped from the start
        # of a line to a block.
        "jinja_lstrip_blocks": bool,
        # If this is set to True the first newline after a Jinja block is removed
        "jinja_trim_blocks": bool,
        # Cache minion ID to file
        "minion_id_caching": bool,
        # Always generate minion id in lowercase.
        "minion_id_lowercase": bool,
        # Remove either a single domain (foo.org), or all (True) from a generated minion id.
        "minion_id_remove_domain": (str, bool),
        # If set, the master will sign all publications before they are sent out
        "sign_pub_messages": bool,
        # The size of key that should be generated when creating new keys
        "keysize": int,
        # The transport system for this daemon. (i.e. zeromq, tcp, detect, etc)
        "transport": str,
        # The number of seconds to wait when the client is requesting information about running jobs
        "gather_job_timeout": int,
        # The number of seconds to wait before timing out an authentication request
        "auth_timeout": int,
        # The number of attempts to authenticate to a master before giving up
        "auth_tries": int,
        # The number of attempts to connect to a master before giving up.
        # Set this to -1 for unlimited attempts. This allows for a master to have
        # downtime and the minion to reconnect to it later when it comes back up.
        # In 'failover' mode, it is the number of attempts for each set of masters.
        # In this mode, it will cycle through the list of masters for each attempt.
        "master_tries": int,
        # Never give up when trying to authenticate to a master
        "auth_safemode": bool,
        # Selects a random master when starting a minion up in multi-master mode or
        # when starting a minion with salt-call. ``master`` must be a list.
        "random_master": bool,
        # An upper bound for the amount of time for a minion to sleep before attempting to
        # reauth after a restart.
        "random_reauth_delay": int,
        # The number of seconds for a syndic to poll for new messages that need to be forwarded
        "syndic_event_forward_timeout": float,
        # The length that the syndic event queue must hit before events are popped off and forwarded
        "syndic_jid_forward_cache_hwm": int,
        # Salt SSH configuration
        "ssh_passwd": str,
        "ssh_port": str,
        "ssh_sudo": bool,
        "ssh_sudo_user": str,
        "ssh_timeout": float,
        "ssh_user": str,
        "ssh_scan_ports": str,
        "ssh_scan_timeout": float,
        "ssh_identities_only": bool,
        "ssh_log_file": str,
        "ssh_config_file": str,
        "ssh_merge_pillar": bool,
        "ssh_run_pre_flight": bool,
        "cluster_mode": bool,
        "sqlite_queue_dir": str,
        "queue_dirs": list,
        # Instructs the minion to ping its master(s) every n number of minutes. Used
        # primarily as a mitigation technique against minion disconnects.
        "ping_interval": int,
        # Instructs the salt CLI to print a summary of a minion responses before returning
        "cli_summary": bool,
        # The maximum number of minion connections allowed by the master. Can have performance
        # implications in large setups.
        "max_minions": int,
        "username": (type(None), str),
        "password": (type(None), str),
        # Use zmq.SUSCRIBE to limit listening sockets to only process messages bound for them
        "zmq_filtering": bool,
        # Connection caching. Can greatly speed up salt performance.
        "con_cache": bool,
        "rotate_aes_key": bool,
        # Cache ZeroMQ connections. Can greatly improve salt performance.
        "cache_sreqs": bool,
        # Can be set to override the python_shell=False default in the cmd module
        "cmd_safe": bool,
        # Used by salt-api for master requests timeout
        "rest_timeout": int,
        # If set, all minion exec module actions will be rerouted through sudo as this user
        "sudo_user": str,
        # HTTP connection timeout in seconds. Applied for tornado http fetch functions like cp.get_url
        # should be greater than overall download time
        "http_connect_timeout": float,
        # HTTP request timeout in seconds. Applied for tornado http fetch functions like cp.get_url
        # should be greater than overall download time
        "http_request_timeout": float,
        # HTTP request max file content size.
        "http_max_body": int,
        # Delay in seconds before executing bootstrap (Salt Cloud)
        "bootstrap_delay": int,
        # If a proxymodule has a function called 'grains', then call it during
        # regular grains loading and merge the results with the proxy's grains
        # dictionary.  Otherwise it is assumed that the module calls the grains
        # function in a custom way and returns the data elsewhere
        #
        # Default to False for 2016.3 and 2016.11. Switch to True for 2017.7.0
        "proxy_merge_grains_in_module": bool,
        # Command to use to restart salt-minion
        "minion_restart_command": list,
        # Whether or not a minion should send the results of a command back to the master
        # Useful when a returner is the source of truth for a job result
        "pub_ret": bool,
        # HTTP proxy settings. Used in tornado fetch functions, apt-key etc
        "proxy_host": str,
        "proxy_username": str,
        "proxy_password": str,
        "proxy_port": int,
        # Exclude list of hostnames from proxy
        "no_proxy": list,
        # Minion de-dup jid cache max size
        "minion_jid_queue_hwm": int,
        # Minion data cache driver (one of salt.cache.* modules)
        "cache": str,
        # Enables a fast in-memory cache booster and sets the expiration time.
        "memcache_expire_seconds": int,
        # Set a memcache limit in items (bank + key) per cache storage (driver + driver_opts).
        "memcache_max_items": int,
        # Each time a cache storage got full cleanup all the expired items not just the oldest one.
        "memcache_full_cleanup": bool,
        # Enable collecting the memcache stats and log it on `debug` log level.
        "memcache_debug": bool,
        # Thin and minimal Salt extra modules
        "thin_extra_mods": str,
        "min_extra_mods": str,
        # Default returners minion should use. List or comma-delimited string
        "return": (str, list),
        # TLS/SSL connection options. This could be set to a dictionary containing arguments
        # corresponding to python ssl.wrap_socket method. For details see:
        # http://www.tornadoweb.org/en/stable/tcpserver.html#tornado.tcpserver.TCPServer
        # http://docs.python.org/2/library/ssl.html#ssl.wrap_socket
        # Note: to set enum arguments values like `cert_reqs` and `ssl_version` use constant names
        # without ssl module prefix: `CERT_REQUIRED` or `PROTOCOL_SSLv23`.
        "ssl": (dict, bool, type(None)),
        # Controls how a multi-function job returns its data. If this is False,
        # it will return its data using a dictionary with the function name as
        # the key. This is compatible with legacy systems. If this is True, it
        # will return its data using an array in the same order as the input
        # array of functions to execute. This allows for calling the same
        # function multiple times in the same multi-function job.
        "multifunc_ordered": bool,
        # Controls whether beacons are set up before a connection
        # to the master is attempted.
        "beacons_before_connect": bool,
        # Controls whether the scheduler is set up before a connection
        # to the master is attempted.
        "scheduler_before_connect": bool,
        # Whitelist/blacklist specific modules to be synced
        "extmod_whitelist": dict,
        "extmod_blacklist": dict,
        # django auth
        "django_auth_path": str,
        "django_auth_settings": str,
        # Number of times to try to auth with the master on a reconnect with the
        # tcp transport
        "tcp_authentication_retries": int,
        # Backoff interval in seconds for minion reconnect with tcp transport
        "tcp_reconnect_backoff": float,
        # Permit or deny allowing minions to request revoke of its own key
        "allow_minion_key_revoke": bool,
        # File chunk size for salt-cp
        "salt_cp_chunk_size": int,
        # Require that the minion sign messages it posts to the master on the event
        # bus
        "minion_sign_messages": bool,
        # Have master drop messages from minions for which their signatures do
        # not verify
        "drop_messages_signature_fail": bool,
        # Require that payloads from minions have a 'sig' entry
        # (in other words, require that minions have 'minion_sign_messages'
        # turned on)
        "require_minion_sign_messages": bool,
        # The list of config entries to be passed to external pillar function as
        # part of the extra_minion_data param
        # Subconfig entries can be specified by using the ':' notation (e.g. key:subkey)
        "pass_to_ext_pillars": (str, list),
        # SSDP discovery publisher description.
        # Contains publisher configuration and minion mapping.
        # Setting it to False disables discovery
        "discovery": (dict, bool),
        # Scheduler should be a dictionary
        "schedule": dict,
        # Whether to fire auth events
        "auth_events": bool,
        # Whether to fire Minion data cache refresh events
        "minion_data_cache_events": bool,
        # Enable calling ssh minions from the salt master
        "enable_ssh_minions": bool,
        # Thorium saltenv
        "thoriumenv": (type(None), str),
        # Thorium top file location
        "thorium_top": str,
        # Allow raw_shell option when using the ssh
        # client via the Salt API
        "netapi_allow_raw_shell": bool,
        # Enable clients in the Salt API
        "netapi_enable_clients": list,
        "disabled_requisites": (str, list),
        "global_state_conditions": (type(None), dict),
        # Feature flag config
        "features": dict,
        "fips_mode": bool,
        # Feature flag to enable checking if master is connected to a host
        # on a given port
        "detect_remote_minions": bool,
        # The port to be used when checking if a master is connected to a
        # minion
        "remote_minions_port": int,
        # pass renderer: Fetch secrets only for the template variables matching the prefix
        "pass_variable_prefix": str,
        # pass renderer: Whether to error out when unable to fetch a secret
        "pass_strict_fetch": bool,
        # pass renderer: Set GNUPGHOME env for Pass
        "pass_gnupghome": str,
        # pass renderer: Set PASSWORD_STORE_DIR env for Pass
        "pass_dir": str,
        # Maintenence process restart interval
        "maintenance_interval": int,
        # Fileserver process restart interval
        "fileserver_interval": int,
        "request_channel_timeout": int,
        "request_channel_tries": int,
    }
)

# default configurations
DEFAULT_MINION_OPTS = immutabletypes.freeze(
    {
        "interface": "0.0.0.0",
        "master": "salt",
        "master_type": "str",
        "master_uri_format": "default",
        "source_interface_name": "",
        "source_address": "",
        "source_ret_port": 0,
        "source_publish_port": 0,
        "master_port": 4506,
        "master_finger": "",
        "master_shuffle": False,
        "master_alive_interval": 0,
        "master_failback": False,
        "master_failback_interval": 0,
        "verify_master_pubkey_sign": False,
        "sign_pub_messages": False,
        "always_verify_signature": False,
        "master_sign_key_name": "master_sign",
        "syndic_finger": "",
        "user": salt.utils.user.get_user(),
        "root_dir": salt.syspaths.ROOT_DIR,
        "pki_dir": os.path.join(salt.syspaths.LIB_STATE_DIR, "pki", "minion"),
        "id": "",
        "id_function": {},
        "cachedir": os.path.join(salt.syspaths.CACHE_DIR, "minion"),
        "append_minionid_config_dirs": [],
        "cache_jobs": False,
        "grains_blacklist": [],
        "grains_cache": False,
        "grains_cache_expiration": 300,
        "grains_deep_merge": False,
        "conf_file": os.path.join(salt.syspaths.CONFIG_DIR, "minion"),
        "sock_dir": os.path.join(salt.syspaths.SOCK_DIR, "minion"),
        "sock_pool_size": 1,
        "backup_mode": "",
        "renderer": "jinja|yaml",
        "renderer_whitelist": [],
        "renderer_blacklist": [],
        "random_startup_delay": 0,
        "failhard": False,
        "autoload_dynamic_modules": True,
        "saltenv": None,
        "lock_saltenv": False,
        "pillarenv": None,
        "pillarenv_from_saltenv": False,
        "pillar_opts": False,
        "pillar_source_merging_strategy": "smart",
        "pillar_merge_lists": False,
        "pillar_includes_override_sls": False,
        # ``pillar_cache``, ``pillar_cache_ttl``, ``pillar_cache_backend``,
        # ``gpg_cache``, ``gpg_cache_ttl`` and ``gpg_cache_backend``
        # are not used on the minion but are unavoidably in the code path
        "pillar_cache": False,
        "pillar_cache_ttl": 3600,
        "pillar_cache_backend": "disk",
        "request_channel_timeout": 60,
        "request_channel_tries": 3,
        "gpg_cache": False,
        "gpg_cache_ttl": 86400,
        "gpg_cache_backend": "disk",
        "extension_modules": os.path.join(salt.syspaths.CACHE_DIR, "minion", "extmods"),
        "state_top": "top.sls",
        "state_top_saltenv": None,
        "startup_states": "",
        "sls_list": [],
        "start_event_grains": [],
        "top_file": "",
        "thoriumenv": None,
        "thorium_top": "top.sls",
        "thorium_interval": 0.5,
        "thorium_roots": {"base": [salt.syspaths.BASE_THORIUM_ROOTS_DIR]},
        "file_client": "remote",
        "local": False,
        "use_master_when_local": False,
        "file_roots": {
            "base": [salt.syspaths.BASE_FILE_ROOTS_DIR, salt.syspaths.SPM_FORMULA_PATH]
        },
        "top_file_merging_strategy": "merge",
        "env_order": [],
        "default_top": "base",
        "file_recv": False,
        "file_recv_max_size": 100,
        "file_ignore_regex": [],
        "file_ignore_glob": [],
        "fileserver_backend": ["roots"],
        "fileserver_followsymlinks": True,
        "fileserver_ignoresymlinks": False,
        "pillar_roots": {
            "base": [salt.syspaths.BASE_PILLAR_ROOTS_DIR, salt.syspaths.SPM_PILLAR_PATH]
        },
        "on_demand_ext_pillar": ["libvirt", "virtkey"],
        "decrypt_pillar": [],
        "decrypt_pillar_delimiter": ":",
        "decrypt_pillar_default": "gpg",
        "decrypt_pillar_renderers": ["gpg"],
        "gpg_decrypt_must_succeed": True,
        # Update intervals
        "roots_update_interval": DEFAULT_INTERVAL,
        "gitfs_update_interval": DEFAULT_INTERVAL,
        "git_pillar_update_interval": DEFAULT_INTERVAL,
        "hgfs_update_interval": DEFAULT_INTERVAL,
        "minionfs_update_interval": DEFAULT_INTERVAL,
        "s3fs_update_interval": DEFAULT_INTERVAL,
        "svnfs_update_interval": DEFAULT_INTERVAL,
        "git_pillar_base": "master",
        "git_pillar_branch": "master",
        "git_pillar_env": "",
        "git_pillar_fallback": "",
        "git_pillar_root": "",
        "git_pillar_ssl_verify": True,
        "git_pillar_global_lock": True,
        "git_pillar_user": "",
        "git_pillar_password": "",
        "git_pillar_insecure_auth": False,
        "git_pillar_privkey": "",
        "git_pillar_pubkey": "",
        "git_pillar_passphrase": "",
        "git_pillar_refspecs": _DFLT_REFSPECS,
        "git_pillar_includes": True,
        "gitfs_remotes": [],
        "gitfs_mountpoint": "",
        "gitfs_root": "",
        "gitfs_base": "master",
        "gitfs_fallback": "",
        "gitfs_user": "",
        "gitfs_password": "",
        "gitfs_insecure_auth": False,
        "gitfs_privkey": "",
        "gitfs_pubkey": "",
        "gitfs_passphrase": "",
        "gitfs_saltenv_whitelist": [],
        "gitfs_saltenv_blacklist": [],
        "gitfs_global_lock": True,
        "gitfs_ssl_verify": True,
        "gitfs_saltenv": [],
        "gitfs_ref_types": ["branch", "tag", "sha"],
        "gitfs_refspecs": _DFLT_REFSPECS,
        "gitfs_disable_saltenv_mapping": False,
        "unique_jid": False,
        "hash_type": DEFAULT_HASH_TYPE,
        "optimization_order": [0, 1, 2],
        "disable_modules": [],
        "disable_returners": [],
        "whitelist_modules": [],
        "module_dirs": [],
        "returner_dirs": [],
        "grains_dirs": [],
        "states_dirs": [],
        "render_dirs": [],
        "outputter_dirs": [],
        "utils_dirs": [],
        "publisher_acl": {},
        "publisher_acl_blacklist": {},
        "providers": {},
        "clean_dynamic_modules": True,
        "open_mode": False,
        "auto_accept": True,
        "autosign_timeout": 120,
        "multiprocessing": True,
        "process_count_max": -1,
        "mine_enabled": True,
        "mine_return_job": False,
        "mine_interval": 60,
        "ipc_mode": _DFLT_IPC_MODE,
        "ipc_write_buffer": _DFLT_IPC_WBUFFER,
        "ipv6": None,
        "file_buffer_size": 262144,
        "tcp_pub_port": 4510,
        "tcp_pull_port": 4511,
        "tcp_authentication_retries": 5,
        "tcp_reconnect_backoff": 1,
        "log_file": os.path.join(salt.syspaths.LOGS_DIR, "minion"),
        "log_level": "warning",
        "log_level_logfile": None,
        "log_datefmt": DFLT_LOG_DATEFMT,
        "log_datefmt_logfile": DFLT_LOG_DATEFMT_LOGFILE,
        "log_fmt_console": DFLT_LOG_FMT_CONSOLE,
        "log_fmt_logfile": DFLT_LOG_FMT_LOGFILE,
        "log_fmt_jid": DFLT_LOG_FMT_JID,
        "log_granular_levels": {},
        "log_rotate_max_bytes": 0,
        "log_rotate_backup_count": 0,
        "max_event_size": 1048576,
        "enable_legacy_startup_events": True,
        "test": False,
        "ext_job_cache": "",
        "cython_enable": False,
        "enable_fqdns_grains": _DFLT_FQDNS_GRAINS,
        "enable_gpu_grains": True,
        "enable_zip_modules": False,
        "state_verbose": True,
        "state_output": "full",
        "state_output_diff": False,
        "state_output_profile": True,
        "state_auto_order": True,
        "state_events": False,
        "state_aggregate": False,
        "state_queue": False,
        "snapper_states": False,
        "snapper_states_config": "root",
        "acceptance_wait_time": 10,
        "acceptance_wait_time_max": 0,
        "rejected_retry": False,
        "loop_interval": 1,
        "verify_env": True,
        "grains": {},
        "permissive_pki_access": False,
        "default_include": "minion.d/*.conf",
        "update_url": False,
        "update_restart_services": [],
        "retry_dns": 30,
        "retry_dns_count": None,
        "resolve_dns_fallback": True,
        "recon_max": 10000,
        "recon_default": 1000,
        "recon_randomize": True,
        "return_retry_timer": 5,
        "return_retry_timer_max": 10,
        "return_retry_tries": 3,
        "random_reauth_delay": 10,
        "winrepo_source_dir": "salt://win/repo-ng/",
        "winrepo_dir": os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR, "win", "repo"),
        "winrepo_dir_ng": os.path.join(
            salt.syspaths.BASE_FILE_ROOTS_DIR, "win", "repo-ng"
        ),
        "winrepo_cachefile": "winrepo.p",
        "winrepo_cache_expire_max": 604800,
        "winrepo_cache_expire_min": 1800,
        "winrepo_remotes": ["https://github.com/saltstack/salt-winrepo.git"],
        "winrepo_remotes_ng": ["https://github.com/saltstack/salt-winrepo-ng.git"],
        "winrepo_branch": "master",
        "winrepo_fallback": "",
        "winrepo_ssl_verify": True,
        "winrepo_user": "",
        "winrepo_password": "",
        "winrepo_insecure_auth": False,
        "winrepo_privkey": "",
        "winrepo_pubkey": "",
        "winrepo_passphrase": "",
        "winrepo_refspecs": _DFLT_REFSPECS,
        "pidfile": os.path.join(salt.syspaths.PIDFILE_DIR, "salt-minion.pid"),
        "range_server": "range:80",
        "reactor_refresh_interval": 60,
        "reactor_worker_threads": 10,
        "reactor_worker_hwm": 10000,
        "engines": [],
        "tcp_keepalive": True,
        "tcp_keepalive_idle": 300,
        "tcp_keepalive_cnt": -1,
        "tcp_keepalive_intvl": -1,
        "modules_max_memory": -1,
        "grains_refresh_every": 0,
        "minion_id_caching": True,
        "minion_id_lowercase": False,
        "minion_id_remove_domain": False,
        "keysize": 2048,
        "transport": "zeromq",
        "auth_timeout": 5,
        "auth_tries": 7,
        "master_tries": _MASTER_TRIES,
        "master_tops_first": False,
        "auth_safemode": False,
        "random_master": False,
        "cluster_mode": False,
        "restart_on_error": False,
        "ping_interval": 0,
        "username": None,
        "password": None,
        "zmq_filtering": False,
        "zmq_monitor": False,
        "cache_sreqs": True,
        "cmd_safe": True,
        "sudo_user": "",
        "http_connect_timeout": 20.0,  # tornado default - 20 seconds
        "http_request_timeout": 1 * 60 * 60.0,  # 1 hour
        "http_max_body": 100 * 1024 * 1024 * 1024,  # 100GB
        "event_match_type": "startswith",
        "minion_restart_command": [],
        "pub_ret": True,
        "proxy_host": "",
        "proxy_username": "",
        "proxy_password": "",
        "proxy_port": 0,
        "minion_jid_queue_hwm": 100,
        "ssl": None,
        "multifunc_ordered": False,
        "beacons_before_connect": False,
        "scheduler_before_connect": False,
        "cache": "localfs",
        "salt_cp_chunk_size": 65536,
        "extmod_whitelist": {},
        "extmod_blacklist": {},
        "minion_sign_messages": False,
        "discovery": False,
        "schedule": {},
        "ssh_merge_pillar": True,
        "disabled_requisites": [],
        "global_state_conditions": None,
        "reactor_niceness": None,
        "fips_mode": False,
        "features": {},
    }
)

DEFAULT_MASTER_OPTS = immutabletypes.freeze(
    {
        "interface": "0.0.0.0",
        "publish_port": 4505,
        "zmq_backlog": 1000,
        "pub_hwm": 1000,
        "auth_mode": 1,
        "user": _MASTER_USER,
        "worker_threads": 5,
        "sock_dir": os.path.join(salt.syspaths.SOCK_DIR, "master"),
        "sock_pool_size": 1,
        "ret_port": 4506,
        "timeout": 5,
        "keep_jobs": 24,
        "keep_jobs_seconds": 86400,
        "archive_jobs": False,
        "root_dir": salt.syspaths.ROOT_DIR,
        "pki_dir": os.path.join(salt.syspaths.LIB_STATE_DIR, "pki", "master"),
        "key_cache": "",
        "cachedir": os.path.join(salt.syspaths.CACHE_DIR, "master"),
        "file_roots": {
            "base": [salt.syspaths.BASE_FILE_ROOTS_DIR, salt.syspaths.SPM_FORMULA_PATH]
        },
        "master_roots": {"base": [salt.syspaths.BASE_MASTER_ROOTS_DIR]},
        "pillar_roots": {
            "base": [salt.syspaths.BASE_PILLAR_ROOTS_DIR, salt.syspaths.SPM_PILLAR_PATH]
        },
        "on_demand_ext_pillar": ["libvirt", "virtkey"],
        "decrypt_pillar": [],
        "decrypt_pillar_delimiter": ":",
        "decrypt_pillar_default": "gpg",
        "decrypt_pillar_renderers": ["gpg"],
        "gpg_decrypt_must_succeed": True,
        "thoriumenv": None,
        "thorium_top": "top.sls",
        "thorium_interval": 0.5,
        "thorium_roots": {"base": [salt.syspaths.BASE_THORIUM_ROOTS_DIR]},
        "top_file_merging_strategy": "merge",
        "env_order": [],
        "saltenv": None,
        "lock_saltenv": False,
        "pillarenv": None,
        "default_top": "base",
        "file_client": "local",
        "local": True,
        # Update intervals
        "roots_update_interval": DEFAULT_INTERVAL,
        "gitfs_update_interval": DEFAULT_INTERVAL,
        "git_pillar_update_interval": DEFAULT_INTERVAL,
        "hgfs_update_interval": DEFAULT_INTERVAL,
        "minionfs_update_interval": DEFAULT_INTERVAL,
        "s3fs_update_interval": DEFAULT_INTERVAL,
        "svnfs_update_interval": DEFAULT_INTERVAL,
        "git_pillar_base": "master",
        "git_pillar_branch": "master",
        "git_pillar_env": "",
        "git_pillar_fallback": "",
        "git_pillar_root": "",
        "git_pillar_ssl_verify": True,
        "git_pillar_global_lock": True,
        "git_pillar_user": "",
        "git_pillar_password": "",
        "git_pillar_insecure_auth": False,
        "git_pillar_privkey": "",
        "git_pillar_pubkey": "",
        "git_pillar_passphrase": "",
        "git_pillar_refspecs": _DFLT_REFSPECS,
        "git_pillar_includes": True,
        "git_pillar_verify_config": True,
        "gitfs_remotes": [],
        "gitfs_mountpoint": "",
        "gitfs_root": "",
        "gitfs_base": "master",
        "gitfs_fallback": "",
        "gitfs_user": "",
        "gitfs_password": "",
        "gitfs_insecure_auth": False,
        "gitfs_privkey": "",
        "gitfs_pubkey": "",
        "gitfs_passphrase": "",
        "gitfs_saltenv_whitelist": [],
        "gitfs_saltenv_blacklist": [],
        "gitfs_global_lock": True,
        "gitfs_ssl_verify": True,
        "gitfs_saltenv": [],
        "gitfs_ref_types": ["branch", "tag", "sha"],
        "gitfs_refspecs": _DFLT_REFSPECS,
        "gitfs_disable_saltenv_mapping": False,
        "hgfs_remotes": [],
        "hgfs_mountpoint": "",
        "hgfs_root": "",
        "hgfs_base": "default",
        "hgfs_branch_method": "branches",
        "hgfs_saltenv_whitelist": [],
        "hgfs_saltenv_blacklist": [],
        "show_timeout": True,
        "show_jid": False,
        "unique_jid": False,
        "svnfs_remotes": [],
        "svnfs_mountpoint": "",
        "svnfs_root": "",
        "svnfs_trunk": "trunk",
        "svnfs_branches": "branches",
        "svnfs_tags": "tags",
        "svnfs_saltenv_whitelist": [],
        "svnfs_saltenv_blacklist": [],
        "max_event_size": 1048576,
        "master_stats": False,
        "master_stats_event_iter": 60,
        "minionfs_env": "base",
        "minionfs_mountpoint": "",
        "minionfs_whitelist": [],
        "minionfs_blacklist": [],
        "ext_pillar": [],
        "pillar_version": 2,
        "pillar_opts": False,
        "pillar_safe_render_error": True,
        "pillar_source_merging_strategy": "smart",
        "pillar_merge_lists": False,
        "pillar_includes_override_sls": False,
        "pillar_cache": False,
        "pillar_cache_ttl": 3600,
        "pillar_cache_backend": "disk",
        "gpg_cache": False,
        "gpg_cache_ttl": 86400,
        "gpg_cache_backend": "disk",
        "ping_on_rotate": False,
        "peer": {},
        "preserve_minion_cache": False,
        "syndic_master": "masterofmasters",
        "syndic_failover": "random",
        "syndic_forward_all_events": False,
        "syndic_log_file": os.path.join(salt.syspaths.LOGS_DIR, "syndic"),
        "syndic_pidfile": os.path.join(salt.syspaths.PIDFILE_DIR, "salt-syndic.pid"),
        "outputter_dirs": [],
        "runner_dirs": [],
        "utils_dirs": [],
        "client_acl_verify": True,
        "publisher_acl": {},
        "publisher_acl_blacklist": {},
        "sudo_acl": False,
        "external_auth": {},
        "token_expire": 43200,
        "token_expire_user_override": False,
        "permissive_acl": False,
        "keep_acl_in_token": False,
        "eauth_acl_module": "",
        "eauth_tokens": "localfs",
        "extension_modules": os.path.join(salt.syspaths.CACHE_DIR, "master", "extmods"),
        "module_dirs": [],
        "file_recv": False,
        "file_recv_max_size": 100,
        "file_buffer_size": 1048576,
        "file_ignore_regex": [],
        "file_ignore_glob": [],
        "fileserver_backend": ["roots"],
        "fileserver_followsymlinks": True,
        "fileserver_ignoresymlinks": False,
        "fileserver_verify_config": True,
        "max_open_files": 100000,
        "hash_type": DEFAULT_HASH_TYPE,
        "optimization_order": [0, 1, 2],
        "conf_file": os.path.join(salt.syspaths.CONFIG_DIR, "master"),
        "open_mode": False,
        "auto_accept": False,
        "renderer": "jinja|yaml",
        "renderer_whitelist": [],
        "renderer_blacklist": [],
        "failhard": False,
        "state_top": "top.sls",
        "state_top_saltenv": None,
        "master_tops": {},
        "master_tops_first": False,
        "order_masters": False,
        "job_cache": True,
        "ext_job_cache": "",
        "master_job_cache": "local_cache",
        "job_cache_store_endtime": False,
        "minion_data_cache": True,
        "enforce_mine_cache": False,
        "ipc_mode": _DFLT_IPC_MODE,
        "ipc_write_buffer": _DFLT_IPC_WBUFFER,
        # various subprocess niceness levels
        "req_server_niceness": None,
        "pub_server_niceness": None,
        "fileserver_update_niceness": None,
        "mworker_niceness": None,
        "mworker_queue_niceness": None,
        "maintenance_niceness": None,
        "event_return_niceness": None,
        "event_publisher_niceness": None,
        "reactor_niceness": None,
        "ipv6": None,
        "tcp_master_pub_port": 4512,
        "tcp_master_pull_port": 4513,
        "tcp_master_publish_pull": 4514,
        "tcp_master_workers": 4515,
        "log_file": os.path.join(salt.syspaths.LOGS_DIR, "master"),
        "log_level": "warning",
        "log_level_logfile": None,
        "log_datefmt": DFLT_LOG_DATEFMT,
        "log_datefmt_logfile": DFLT_LOG_DATEFMT_LOGFILE,
        "log_fmt_console": DFLT_LOG_FMT_CONSOLE,
        "log_fmt_logfile": DFLT_LOG_FMT_LOGFILE,
        "log_fmt_jid": DFLT_LOG_FMT_JID,
        "log_granular_levels": {},
        "log_rotate_max_bytes": 0,
        "log_rotate_backup_count": 0,
        "pidfile": os.path.join(salt.syspaths.PIDFILE_DIR, "salt-master.pid"),
        "publish_session": 86400,
        "range_server": "range:80",
        "reactor": [],
        "reactor_refresh_interval": 60,
        "reactor_worker_threads": 10,
        "reactor_worker_hwm": 10000,
        "engines": [],
        "event_return": "",
        "event_return_queue": 0,
        "event_return_whitelist": [],
        "event_return_blacklist": [],
        "event_match_type": "startswith",
        "runner_returns": True,
        "serial": "msgpack",
        "test": False,
        "state_verbose": True,
        "state_output": "full",
        "state_output_diff": False,
        "state_output_profile": True,
        "state_auto_order": True,
        "state_events": False,
        "state_aggregate": False,
        "search": "",
        "loop_interval": 60,
        "nodegroups": {},
        "ssh_list_nodegroups": {},
        "ssh_use_home_key": False,
        "cython_enable": False,
        "enable_gpu_grains": False,
        # XXX: Remove 'key_logfile' support in 2014.1.0
        "key_logfile": os.path.join(salt.syspaths.LOGS_DIR, "key"),
        "verify_env": True,
        "permissive_pki_access": False,
        "key_pass": None,
        "cluster_key_pass": None,
        "signing_key_pass": None,
        "default_include": "master.d/*.conf",
        "winrepo_dir": os.path.join(salt.syspaths.BASE_FILE_ROOTS_DIR, "win", "repo"),
        "winrepo_dir_ng": os.path.join(
            salt.syspaths.BASE_FILE_ROOTS_DIR, "win", "repo-ng"
        ),
        "winrepo_cachefile": "winrepo.p",
        "winrepo_remotes": ["https://github.com/saltstack/salt-winrepo.git"],
        "winrepo_remotes_ng": ["https://github.com/saltstack/salt-winrepo-ng.git"],
        "winrepo_branch": "master",
        "winrepo_fallback": "",
        "winrepo_ssl_verify": True,
        "winrepo_user": "",
        "winrepo_password": "",
        "winrepo_insecure_auth": False,
        "winrepo_privkey": "",
        "winrepo_pubkey": "",
        "winrepo_passphrase": "",
        "winrepo_refspecs": _DFLT_REFSPECS,
        "syndic_wait": 5,
        "jinja_env": {},
        "jinja_sls_env": {},
        "jinja_lstrip_blocks": False,
        "jinja_trim_blocks": False,
        "tcp_keepalive": True,
        "tcp_keepalive_idle": 300,
        "tcp_keepalive_cnt": -1,
        "tcp_keepalive_intvl": -1,
        "sign_pub_messages": True,
        "keysize": 2048,
        "transport": "zeromq",
        "gather_job_timeout": 10,
        "syndic_event_forward_timeout": 0.5,
        "syndic_jid_forward_cache_hwm": 100,
        "regen_thin": False,
        "ssh_passwd": "",
        "ssh_priv_passwd": "",
        "ssh_port": "22",
        "ssh_sudo": False,
        "ssh_sudo_user": "",
        "ssh_timeout": 60,
        "ssh_user": "root",
        "ssh_scan_ports": "22",
        "ssh_scan_timeout": 0.01,
        "ssh_identities_only": False,
        "ssh_log_file": os.path.join(salt.syspaths.LOGS_DIR, "ssh"),
        "ssh_config_file": os.path.join(salt.syspaths.HOME_DIR, ".ssh", "config"),
        "cluster_mode": False,
        "sqlite_queue_dir": os.path.join(salt.syspaths.CACHE_DIR, "master", "queues"),
        "queue_dirs": [],
        "cli_summary": False,
        "max_minions": 0,
        "master_sign_key_name": "master_sign",
        "master_sign_pubkey": False,
        "master_pubkey_signature": "master_pubkey_signature",
        "master_use_pubkey_signature": False,
        "zmq_filtering": False,
        "zmq_monitor": False,
        "con_cache": False,
        "rotate_aes_key": True,
        "cache_sreqs": True,
        "dummy_pub": False,
        "http_connect_timeout": 20.0,  # tornado default - 20 seconds
        "http_request_timeout": 1 * 60 * 60.0,  # 1 hour
        "http_max_body": 100 * 1024 * 1024 * 1024,  # 100GB
        "cache": "localfs",
        "memcache_expire_seconds": 0,
        "memcache_max_items": 1024,
        "memcache_full_cleanup": False,
        "memcache_debug": False,
        "thin_extra_mods": "",
        "min_extra_mods": "",
        "ssl": None,
        "extmod_whitelist": {},
        "extmod_blacklist": {},
        "clean_dynamic_modules": True,
        "django_auth_path": "",
        "django_auth_settings": "",
        "allow_minion_key_revoke": True,
        "salt_cp_chunk_size": 98304,
        "require_minion_sign_messages": False,
        "drop_messages_signature_fail": False,
        "discovery": False,
        "schedule": {},
        "auth_events": True,
        "minion_data_cache_events": True,
        "enable_ssh_minions": False,
        "netapi_allow_raw_shell": False,
        "fips_mode": False,
        "detect_remote_minions": False,
        "remote_minions_port": 22,
        "pass_variable_prefix": "",
        "pass_strict_fetch": False,
        "pass_gnupghome": "",
        "pass_dir": "",
        "netapi_enable_clients": [],
        "maintenance_interval": 3600,
        "fileserver_interval": 3600,
        "cluster_id": None,
        "cluster_peers": [],
        "cluster_pki_dir": None,
        "features": {},
    }
)


# ----- Salt Proxy Minion Configuration Defaults ----------------------------------->
# These are merged with DEFAULT_MINION_OPTS since many of them also apply here.
DEFAULT_PROXY_MINION_OPTS = immutabletypes.freeze(
    {
        "conf_file": os.path.join(salt.syspaths.CONFIG_DIR, "proxy"),
        "log_file": os.path.join(salt.syspaths.LOGS_DIR, "proxy"),
        "add_proxymodule_to_opts": False,
        "proxy_merge_grains_in_module": True,
        "extension_modules": os.path.join(salt.syspaths.CACHE_DIR, "proxy", "extmods"),
        "append_minionid_config_dirs": [
            "cachedir",
            "pidfile",
            "default_include",
            "extension_modules",
        ],
        "default_include": "proxy.d/*.conf",
        "proxy_merge_pillar_in_opts": False,
        "proxy_deep_merge_pillar_in_opts": False,
        "proxy_merge_pillar_in_opts_strategy": "smart",
        "proxy_mines_pillar": True,
        # By default, proxies will preserve the connection.
        # If this option is set to False,
        # the connection with the remote dumb device
        # is closed after each command request.
        "proxy_always_alive": True,
        "proxy_keep_alive": True,  # by default will try to keep alive the connection
        "proxy_keep_alive_interval": 1,  # frequency of the proxy keepalive in minutes
        "pki_dir": os.path.join(salt.syspaths.LIB_STATE_DIR, "pki", "proxy"),
        "cachedir": os.path.join(salt.syspaths.CACHE_DIR, "proxy"),
        "sock_dir": os.path.join(salt.syspaths.SOCK_DIR, "proxy"),
        "features": {},
    }
)

# ----- Salt Cloud Configuration Defaults ----------------------------------->
DEFAULT_CLOUD_OPTS = immutabletypes.freeze(
    {
        "verify_env": True,
        "default_include": "cloud.conf.d/*.conf",
        # Global defaults
        "ssh_auth": "",
        "cachedir": os.path.join(salt.syspaths.CACHE_DIR, "cloud"),
        "keysize": 4096,
        "os": "",
        "script": "bootstrap-salt",
        "start_action": None,
        "enable_hard_maps": False,
        "delete_sshkeys": False,
        # Custom deploy scripts
        "deploy_scripts_search_path": "cloud.deploy.d",
        # Logging defaults
        "log_file": os.path.join(salt.syspaths.LOGS_DIR, "cloud"),
        "log_level": "warning",
        "log_level_logfile": None,
        "log_datefmt": DFLT_LOG_DATEFMT,
        "log_datefmt_logfile": DFLT_LOG_DATEFMT_LOGFILE,
        "log_fmt_console": DFLT_LOG_FMT_CONSOLE,
        "log_fmt_logfile": DFLT_LOG_FMT_LOGFILE,
        "log_fmt_jid": DFLT_LOG_FMT_JID,
        "log_granular_levels": {},
        "log_rotate_max_bytes": 0,
        "log_rotate_backup_count": 0,
        "bootstrap_delay": 0,
        "cache": "localfs",
        "features": {},
    }
)

DEFAULT_API_OPTS = immutabletypes.freeze(
    {
        # ----- Salt master settings overridden by Salt-API --------------------->
        "api_pidfile": os.path.join(salt.syspaths.PIDFILE_DIR, "salt-api.pid"),
        "api_logfile": os.path.join(salt.syspaths.LOGS_DIR, "api"),
        "rest_timeout": 300,
        # <---- Salt master settings overridden by Salt-API ----------------------
    }
)

DEFAULT_SPM_OPTS = immutabletypes.freeze(
    {
        # ----- Salt master settings overridden by SPM --------------------->
        "spm_conf_file": os.path.join(salt.syspaths.CONFIG_DIR, "spm"),
        "formula_path": salt.syspaths.SPM_FORMULA_PATH,
        "pillar_path": salt.syspaths.SPM_PILLAR_PATH,
        "reactor_path": salt.syspaths.SPM_REACTOR_PATH,
        "spm_logfile": os.path.join(salt.syspaths.LOGS_DIR, "spm"),
        "spm_default_include": "spm.d/*.conf",
        # spm_repos_config also includes a .d/ directory
        "spm_repos_config": "/etc/salt/spm.repos",
        "spm_cache_dir": os.path.join(salt.syspaths.CACHE_DIR, "spm"),
        "spm_build_dir": os.path.join(salt.syspaths.SRV_ROOT_DIR, "spm_build"),
        "spm_build_exclude": ["CVS", ".hg", ".git", ".svn"],
        "spm_db": os.path.join(salt.syspaths.CACHE_DIR, "spm", "packages.db"),
        "cache": "localfs",
        "spm_repo_dups": "ignore",
        # If set, spm_node_type will be either master or minion, but they should
        # NOT be a default
        "spm_node_type": "",
        "spm_share_dir": os.path.join(salt.syspaths.SHARE_DIR, "spm"),
        # <---- Salt master settings overridden by SPM ----------------------
    }
)

VM_CONFIG_DEFAULTS = immutabletypes.freeze(
    {"default_include": "cloud.profiles.d/*.conf"}
)

PROVIDER_CONFIG_DEFAULTS = immutabletypes.freeze(
    {"default_include": "cloud.providers.d/*.conf"}
)
# <---- Salt Cloud Configuration Defaults ------------------------------------


def _normalize_roots(file_roots):
    """
    Normalize file or pillar roots.
    """
    for saltenv, dirs in file_roots.items():
        normalized_saltenv = str(saltenv)
        if normalized_saltenv != saltenv:
            file_roots[normalized_saltenv] = file_roots.pop(saltenv)
        if not isinstance(dirs, (list, tuple)):
            file_roots[normalized_saltenv] = []
        file_roots[normalized_saltenv] = _expand_glob_path(
            file_roots[normalized_saltenv]
        )
    return file_roots


def _validate_pillar_roots(pillar_roots):
    """
    If the pillar_roots option has a key that is None then we will error out,
    just replace it with an empty list
    """
    if not isinstance(pillar_roots, dict):
        log.warning(
            "The pillar_roots parameter is not properly formatted, using defaults"
        )
        return {"base": _expand_glob_path([salt.syspaths.BASE_PILLAR_ROOTS_DIR])}
    return _normalize_roots(pillar_roots)


def _validate_file_roots(file_roots):
    """
    If the file_roots option has a key that is None then we will error out,
    just replace it with an empty list
    """
    if not isinstance(file_roots, dict):
        log.warning(
            "The file_roots parameter is not properly formatted, using defaults"
        )
        return {"base": _expand_glob_path([salt.syspaths.BASE_FILE_ROOTS_DIR])}
    return _normalize_roots(file_roots)


def _expand_glob_path(file_roots):
    """
    Applies shell globbing to a set of directories and returns
    the expanded paths
    """
    unglobbed_path = []
    for path in file_roots:
        try:
            if glob.has_magic(path):
                unglobbed_path.extend(glob.glob(path))
            else:
                unglobbed_path.append(path)
        except Exception:  # pylint: disable=broad-except
            unglobbed_path.append(path)
    return unglobbed_path


def _validate_opts(opts):
    """
    Check that all of the types of values passed into the config are
    of the right types
    """

    def format_multi_opt(valid_type):
        try:
            num_types = len(valid_type)
        except TypeError:
            # Bare type name won't have a length, return the name of the type
            # passed.
            return valid_type.__name__
        else:

            def get_types(types, type_tuple):
                for item in type_tuple:
                    if isinstance(item, tuple):
                        get_types(types, item)
                    else:
                        try:
                            types.append(item.__name__)
                        except AttributeError:
                            log.warning(
                                "Unable to interpret type %s while validating "
                                "configuration",
                                item,
                            )

            types = []
            get_types(types, valid_type)

            ret = ", ".join(types[:-1])
            ret += " or " + types[-1]
            return ret

    errors = []

    err = (
        "Config option '{}' with value {} has an invalid type of {}, a "
        "{} is required for this option"
    )
    for key, val in opts.items():
        if key in VALID_OPTS:
            if val is None:
                if VALID_OPTS[key] is None:
                    continue
                else:
                    try:
                        if None in VALID_OPTS[key]:
                            continue
                    except TypeError:
                        # VALID_OPTS[key] is not iterable and not None
                        pass

            # int(True) evaluates to 1, int(False) evaluates to 0
            # We want to make sure True and False are only valid for bool
            if val is True or val is False:
                if VALID_OPTS[key] is bool:
                    continue
            elif isinstance(val, VALID_OPTS[key]):
                continue

            # We don't know what data type sdb will return at run-time so we
            # simply cannot check it for correctness here at start-time.
            if isinstance(val, str) and val.startswith("sdb://"):
                continue

            # Non-failing types that don't convert properly
            nf_types = {
                str: [list, tuple, dict],
                list: [dict, str],
                tuple: [dict, str],
                bool: [list, tuple, str, int, float, dict, type(None)],
                int: [bool, float],
                float: [bool],
            }

            # Is this a single type (not a tuple of types)?
            if hasattr(VALID_OPTS[key], "__call__"):
                # This config option has a single defined type
                try:
                    # This will try to evaluate the specified value type
                    VALID_OPTS[key](val)

                    # Since it evaluated properly, let's make sure it's valid
                    # Some value types don't evaluate properly. For example,
                    # running list on a string: `list("test")` will return
                    # a list of individual characters:`['t', 'e', 's', 't']` and
                    # therefore won't fail on evaluation
                    for nf_type in nf_types:
                        if VALID_OPTS[key] is nf_type:
                            # Is it one of the non-failing types that we don't
                            # want for this type
                            if isinstance(val, tuple(nf_types[nf_type])):
                                errors.append(
                                    err.format(
                                        key,
                                        val,
                                        type(val).__name__,
                                        VALID_OPTS[key].__name__,
                                    )
                                )
                except (TypeError, ValueError):
                    errors.append(
                        err.format(
                            key, val, type(val).__name__, VALID_OPTS[key].__name__
                        )
                    )
            else:
                # This config option has multiple defined types (tuple of types)
                if type(val) in VALID_OPTS[key]:
                    continue

                valid = []
                for nf_type in nf_types:
                    try:
                        nf_type(val)

                        if nf_type in VALID_OPTS[key]:
                            nf = nf_types[nf_type]
                            for item in VALID_OPTS[key]:
                                if item in nf:
                                    nf.remove(item)
                            if isinstance(val, tuple(nf)):
                                # Running str on any of the above types will succeed,
                                # however, it will change the value in such a way
                                # that it is invalid.
                                valid.append(False)
                            else:
                                valid.append(True)
                    except (TypeError, ValueError):
                        valid.append(False)
                if True not in valid:
                    errors.append(
                        err.format(
                            key,
                            val,
                            type(val).__name__,
                            format_multi_opt(VALID_OPTS[key]),
                        )
                    )

    # Convert list to comma-delimited string for 'return' config option
    if isinstance(opts.get("return"), list):
        opts["return"] = ",".join(opts["return"])

    for error in errors:
        log.warning(error)
    if errors:
        return False
    return True


def _validate_ssh_minion_opts(opts):
    """
    Ensure we're not using any invalid ssh_minion_opts. We want to make sure
    that the ssh_minion_opts does not override any pillar or fileserver options
    inherited from the master config. To add other items, modify the if
    statement in the for loop below.
    """
    ssh_minion_opts = opts.get("ssh_minion_opts", {})
    if not isinstance(ssh_minion_opts, dict):
        log.error("Invalidly-formatted ssh_minion_opts")
        opts.pop("ssh_minion_opts")

    for opt_name in list(ssh_minion_opts):
        if (
            re.match("^[a-z0-9]+fs_", opt_name, flags=re.IGNORECASE)
            or ("pillar" in opt_name and not "ssh_merge_pillar" == opt_name)
            or opt_name in ("fileserver_backend",)
        ):
            log.warning(
                "'%s' is not a valid ssh_minion_opts parameter, ignoring", opt_name
            )
            ssh_minion_opts.pop(opt_name)


def _append_domain(opts):
    """
    Append a domain to the existing id if it doesn't already exist
    """
    # Domain already exists
    if opts["id"].endswith(opts["append_domain"]):
        return opts["id"]
    # Trailing dot should mean an FQDN that is terminated, leave it alone.
    if opts["id"].endswith("."):
        return opts["id"]
    return "{0[id]}.{0[append_domain]}".format(opts)


def _read_conf_file(path):
    """
    Read in a config file from a given path and process it into a dictionary
    """
    log.debug("Reading configuration from %s", path)
    append_file_suffix_YAMLError = False
    with salt.utils.files.fopen(path, "r") as conf_file:
        try:
            conf_opts = salt.utils.yaml.safe_load(conf_file) or {}
        except salt.utils.yaml.YAMLError as err:
            message = f"Error parsing configuration file: {path} - {err}"
            log.error(message)
            if path.endswith("_schedule.conf"):
                # Create empty dictionary of config options
                conf_opts = {}
                # Rename this file, once closed
                append_file_suffix_YAMLError = True
            else:
                raise salt.exceptions.SaltConfigurationError(message)

    if append_file_suffix_YAMLError:
        message = "Renaming to {}".format(path + "YAMLError")
        log.error(message)
        os.replace(path, path + "YAMLError")

    # only interpret documents as a valid conf, not things like strings,
    # which might have been caused by invalid yaml syntax
    if not isinstance(conf_opts, dict):
        message = (
            "Error parsing configuration file: {} - conf "
            "should be a document, not {}.".format(path, type(conf_opts))
        )
        log.error(message)
        raise salt.exceptions.SaltConfigurationError(message)

    # allow using numeric ids: convert int to string
    if "id" in conf_opts:
        if not isinstance(conf_opts["id"], str):
            conf_opts["id"] = str(conf_opts["id"])
        else:
            conf_opts["id"] = salt.utils.data.decode(conf_opts["id"])
    return conf_opts


def _absolute_path(path, relative_to=None):
    """
    Return an absolute path. In case ``relative_to`` is passed and ``path`` is
    not an absolute path, we try to prepend ``relative_to`` to ``path``and if
    that path exists, return that one
    """

    if path and os.path.isabs(path):
        return path
    if path and relative_to is not None:
        _abspath = os.path.join(relative_to, path)
        if os.path.isfile(_abspath):
            log.debug(
                "Relative path '%s' converted to existing absolute path '%s'",
                path,
                _abspath,
            )
            return _abspath
    return path


def load_config(path, env_var, default_path=None, exit_on_config_errors=True):
    """
    Returns configuration dict from parsing either the file described by
    ``path`` or the environment variable described by ``env_var`` as YAML.
    """
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
            "The function '%s()' defined in '%s' is not yet using the "
            "new 'default_path' argument to `salt.config.load_config()`. "
            "As such, the '%s' environment variable will be ignored",
            previous_frame.function,
            previous_frame.filename,
            env_var,
        )
        # In this case, maintain old behavior
        default_path = DEFAULT_MASTER_OPTS["conf_file"]

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
        template = f"{path}.template"
        if os.path.isfile(template):
            log.debug("Writing %s based on %s", path, template)
            with salt.utils.files.fopen(path, "w") as out:
                with salt.utils.files.fopen(template, "r") as ifile:
                    ifile.readline()  # skip first line
                    out.write(ifile.read())

    opts = {}

    if salt.utils.validate.path.is_readable(path):
        try:
            opts = _read_conf_file(path)
            opts["conf_file"] = path
        except salt.exceptions.SaltConfigurationError as error:
            log.error(error)
            if exit_on_config_errors:
                sys.exit(salt.defaults.exitcodes.EX_GENERIC)
    else:
        log.debug("Missing configuration file: %s", path)

    return opts


def include_config(include, orig_path, verbose, exit_on_config_errors=False):
    """
    Parses extra configuration file(s) specified in an include list in the
    main config file.
    """
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
        glob_matches = glob.glob(path)
        if not glob_matches:
            if verbose:
                log.warning(
                    'Warning parsing configuration file: "include" path/glob '
                    "'%s' matches no files",
                    path,
                )

        for fn_ in sorted(glob_matches):
            log.debug("Including configuration from '%s'", fn_)
            try:
                opts = _read_conf_file(fn_)
            except salt.exceptions.SaltConfigurationError as error:
                log.error(error)
                if exit_on_config_errors:
                    sys.exit(salt.defaults.exitcodes.EX_GENERIC)
                else:
                    # Initialize default config if we wish to skip config errors
                    opts = {}
            schedule = opts.get("schedule", {})
            if schedule and "schedule" in configuration:
                configuration["schedule"].update(schedule)
            include = opts.get("include", [])
            if include:
                opts.update(include_config(include, fn_, verbose))

            salt.utils.dictupdate.update(configuration, opts, True, True)

    return configuration


def prepend_root_dir(opts, path_options):
    """
    Prepends the options that represent filesystem paths with value of the
    'root_dir' option.
    """
    root_dir = os.path.abspath(opts["root_dir"])
    def_root_dir = salt.syspaths.ROOT_DIR.rstrip(os.sep)
    for path_option in path_options:
        if path_option in opts:
            path = opts[path_option]
            tmp_path_def_root_dir = None
            tmp_path_root_dir = None
            # When running testsuite, salt.syspaths.ROOT_DIR is often empty
            if path == def_root_dir or path.startswith(def_root_dir + os.sep):
                # Remove the default root dir prefix
                tmp_path_def_root_dir = path[len(def_root_dir) :]
            if root_dir and (path == root_dir or path.startswith(root_dir + os.sep)):
                # Remove the root dir prefix
                tmp_path_root_dir = path[len(root_dir) :]
            if tmp_path_def_root_dir and not tmp_path_root_dir:
                # Just the default root dir matched
                path = tmp_path_def_root_dir
            elif tmp_path_root_dir and not tmp_path_def_root_dir:
                # Just the root dir matched
                path = tmp_path_root_dir
            elif tmp_path_def_root_dir and tmp_path_root_dir:
                # In this case both the default root dir and the override root
                # dir matched; this means that either
                # def_root_dir is a substring of root_dir or vice versa
                # We must choose the most specific path
                if def_root_dir in root_dir:
                    path = tmp_path_root_dir
                else:
                    path = tmp_path_def_root_dir
            elif salt.utils.platform.is_windows() and not os.path.splitdrive(path)[0]:
                # In windows, os.path.isabs resolves '/' to 'C:\\' or whatever
                # the root drive is.  This elif prevents the next from being
                # hit, so that the root_dir is prefixed in cases where the
                # drive is not prefixed on a config option
                pass
            elif os.path.isabs(path):
                # Absolute path (not default or overridden root_dir)
                # No prepending required
                continue
            # Prepending the root dir
            opts[path_option] = salt.utils.path.join(root_dir, path)


def insert_system_path(opts, paths):
    """
    Inserts path into python path taking into consideration 'root_dir' option.
    """
    if isinstance(paths, str):
        paths = [paths]
    for path in paths:
        path_options = {"path": path, "root_dir": opts["root_dir"]}
        prepend_root_dir(path_options, path_options)
        if os.path.isdir(path_options["path"]) and path_options["path"] not in sys.path:
            sys.path.insert(0, path_options["path"])


def minion_config(
    path,
    env_var="SALT_MINION_CONFIG",
    defaults=None,
    cache_minion_id=False,
    ignore_config_errors=True,
    minion_id=None,
    role="minion",
):
    """
    Reads in the minion configuration file and sets up special options

    This is useful for Minion-side operations, such as the
    :py:class:`~salt.client.Caller` class, and manually running the loader
    interface.

    .. code-block:: python

        import salt.config
        minion_opts = salt.config.minion_config('/etc/salt/minion')
    """
    if defaults is None:
        defaults = DEFAULT_MINION_OPTS.copy()
        if role == "master":
            defaults["default_include"] = DEFAULT_MASTER_OPTS["default_include"]

    if not os.environ.get(env_var, None):
        # No valid setting was given using the configuration variable.
        # Lets see is SALT_CONFIG_DIR is of any use
        salt_config_dir = os.environ.get("SALT_CONFIG_DIR", None)
        if salt_config_dir:
            env_config_file_path = os.path.join(salt_config_dir, "minion")
            if salt_config_dir and os.path.isfile(env_config_file_path):
                # We can get a configuration file using SALT_CONFIG_DIR, let's
                # update the environment with this information
                os.environ[env_var] = env_config_file_path

    overrides = load_config(path, env_var, DEFAULT_MINION_OPTS["conf_file"])
    default_include = overrides.get("default_include", defaults["default_include"])
    include = overrides.get("include", [])

    overrides.update(
        include_config(
            default_include,
            path,
            verbose=False,
            exit_on_config_errors=not ignore_config_errors,
        )
    )
    overrides.update(
        include_config(
            include, path, verbose=True, exit_on_config_errors=not ignore_config_errors
        )
    )

    opts = apply_minion_config(
        overrides, defaults, cache_minion_id=cache_minion_id, minion_id=minion_id
    )
    opts["__role"] = role
    if role != "master":
        apply_sdb(opts)
        _validate_opts(opts)
    salt.features.setup_features(opts)
    return opts


def mminion_config(path, overrides, ignore_config_errors=True):
    opts = minion_config(path, ignore_config_errors=ignore_config_errors, role="master")
    opts.update(overrides)
    apply_sdb(opts)

    _validate_opts(opts)
    opts["grains"] = salt.loader.grains(opts)
    opts["pillar"] = {}
    salt.features.setup_features(opts)
    return opts


def proxy_config(
    path,
    env_var="SALT_PROXY_CONFIG",
    defaults=None,
    cache_minion_id=False,
    ignore_config_errors=True,
    minion_id=None,
):
    """
    Reads in the proxy minion configuration file and sets up special options

    This is useful for Minion-side operations, such as the
    :py:class:`~salt.client.Caller` class, and manually running the loader
    interface.

    .. code-block:: python

        import salt.config
        proxy_opts = salt.config.proxy_config('/etc/salt/proxy')
    """
    if defaults is None:
        defaults = DEFAULT_MINION_OPTS.copy()

    defaults.update(DEFAULT_PROXY_MINION_OPTS)

    if not os.environ.get(env_var, None):
        # No valid setting was given using the configuration variable.
        # Lets see is SALT_CONFIG_DIR is of any use
        salt_config_dir = os.environ.get("SALT_CONFIG_DIR", None)
        if salt_config_dir:
            env_config_file_path = os.path.join(salt_config_dir, "proxy")
            if salt_config_dir and os.path.isfile(env_config_file_path):
                # We can get a configuration file using SALT_CONFIG_DIR, let's
                # update the environment with this information
                os.environ[env_var] = env_config_file_path

    overrides = load_config(path, env_var, DEFAULT_PROXY_MINION_OPTS["conf_file"])
    default_include = overrides.get("default_include", defaults["default_include"])
    include = overrides.get("include", [])

    overrides.update(
        include_config(
            default_include,
            path,
            verbose=False,
            exit_on_config_errors=not ignore_config_errors,
        )
    )
    overrides.update(
        include_config(
            include, path, verbose=True, exit_on_config_errors=not ignore_config_errors
        )
    )

    opts = apply_minion_config(
        overrides, defaults, cache_minion_id=cache_minion_id, minion_id=minion_id
    )

    # Update opts with proxy specific configuration
    # with the updated default_include.
    default_include = opts.get("default_include", defaults["default_include"])
    include = opts.get("include", [])

    overrides.update(
        include_config(
            default_include,
            path,
            verbose=False,
            exit_on_config_errors=not ignore_config_errors,
        )
    )
    overrides.update(
        include_config(
            include, path, verbose=True, exit_on_config_errors=not ignore_config_errors
        )
    )

    opts = apply_minion_config(
        overrides, defaults, cache_minion_id=cache_minion_id, minion_id=minion_id
    )

    apply_sdb(opts)
    _validate_opts(opts)
    salt.features.setup_features(opts)
    return opts


def syndic_config(
    master_config_path,
    minion_config_path,
    master_env_var="SALT_MASTER_CONFIG",
    minion_env_var="SALT_MINION_CONFIG",
    minion_defaults=None,
    master_defaults=None,
):

    if minion_defaults is None:
        minion_defaults = DEFAULT_MINION_OPTS.copy()

    if master_defaults is None:
        master_defaults = DEFAULT_MASTER_OPTS.copy()

    opts = {}
    master_opts = master_config(master_config_path, master_env_var, master_defaults)
    minion_opts = minion_config(minion_config_path, minion_env_var, minion_defaults)
    opts["_minion_conf_file"] = master_opts["conf_file"]
    opts["_master_conf_file"] = minion_opts["conf_file"]
    opts.update(master_opts)
    opts.update(minion_opts)
    syndic_opts = {
        "__role": "syndic",
        "root_dir": opts.get("root_dir", salt.syspaths.ROOT_DIR),
        "pidfile": opts.get("syndic_pidfile", "salt-syndic.pid"),
        "log_file": opts.get("syndic_log_file", "salt-syndic.log"),
        "log_level": master_opts["log_level"],
        "id": minion_opts["id"],
        "pki_dir": minion_opts["pki_dir"],
        "master": opts["syndic_master"],
        "interface": master_opts["interface"],
        "master_port": int(
            opts.get(
                # The user has explicitly defined the syndic master port
                "syndic_master_port",
                opts.get(
                    # No syndic_master_port, grab master_port from opts
                    "master_port",
                    # No master_opts, grab from the provided minion defaults
                    minion_defaults.get(
                        "master_port",
                        # Not on the provided minion defaults, load from the
                        # static minion defaults
                        DEFAULT_MINION_OPTS["master_port"],
                    ),
                ),
            )
        ),
        "user": opts.get("syndic_user", opts["user"]),
        "sock_dir": os.path.join(
            opts["cachedir"], opts.get("syndic_sock_dir", opts["sock_dir"])
        ),
        "sock_pool_size": master_opts["sock_pool_size"],
        "cachedir": master_opts["cachedir"],
    }
    opts.update(syndic_opts)
    # Prepend root_dir to other paths
    prepend_root_dirs = [
        "pki_dir",
        "cachedir",
        "pidfile",
        "sock_dir",
        "extension_modules",
        "autosign_file",
        "autoreject_file",
        "token_dir",
        "autosign_grains_dir",
    ]
    for config_key in ("log_file", "key_logfile", "syndic_log_file"):
        # If this is not a URI and instead a local path
        if urllib.parse.urlparse(opts.get(config_key, "")).scheme == "":
            prepend_root_dirs.append(config_key)
    prepend_root_dir(opts, prepend_root_dirs)
    salt.features.setup_features(opts)
    return opts


def apply_sdb(opts, sdb_opts=None):
    """
    Recurse for sdb:// links for opts
    """
    # Late load of SDB to keep CLI light
    import salt.utils.sdb

    if sdb_opts is None:
        sdb_opts = opts
    if isinstance(sdb_opts, str) and sdb_opts.startswith("sdb://"):
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


# ----- Salt Cloud Configuration Functions ---------------------------------->
def cloud_config(
    path,
    env_var="SALT_CLOUD_CONFIG",
    defaults=None,
    master_config_path=None,
    master_config=None,
    providers_config_path=None,
    providers_config=None,
    profiles_config_path=None,
    profiles_config=None,
):
    """
    Read in the Salt Cloud config and return the dict
    """
    if path:
        config_dir = os.path.dirname(path)
    else:
        config_dir = salt.syspaths.CONFIG_DIR

    # Load the cloud configuration
    overrides = load_config(path, env_var, os.path.join(config_dir, "cloud"))

    if defaults is None:
        defaults = DEFAULT_CLOUD_OPTS.copy()

    # Set defaults early to override Salt Master's default config values later
    defaults.update(overrides)
    overrides = defaults

    # Load cloud configuration from any default or provided includes
    overrides.update(
        salt.config.include_config(overrides["default_include"], path, verbose=False)
    )
    include = overrides.get("include", [])
    overrides.update(salt.config.include_config(include, path, verbose=True))

    # The includes have been evaluated, let's see if master, providers and
    # profiles configuration settings have been included and if not, set the
    # default value
    if "master_config" in overrides and master_config_path is None:
        # The configuration setting is being specified in the main cloud
        # configuration file
        master_config_path = overrides["master_config"]
    elif (
        "master_config" not in overrides
        and not master_config
        and not master_config_path
    ):
        # The configuration setting is not being provided in the main cloud
        # configuration file, and
        master_config_path = os.path.join(config_dir, "master")

    # Convert relative to absolute paths if necessary
    master_config_path = _absolute_path(master_config_path, config_dir)

    if "providers_config" in overrides and providers_config_path is None:
        # The configuration setting is being specified in the main cloud
        # configuration file
        providers_config_path = overrides["providers_config"]
    elif (
        "providers_config" not in overrides
        and not providers_config
        and not providers_config_path
    ):
        providers_config_path = os.path.join(config_dir, "cloud.providers")

    # Convert relative to absolute paths if necessary
    providers_config_path = _absolute_path(providers_config_path, config_dir)

    if "profiles_config" in overrides and profiles_config_path is None:
        # The configuration setting is being specified in the main cloud
        # configuration file
        profiles_config_path = overrides["profiles_config"]
    elif (
        "profiles_config" not in overrides
        and not profiles_config
        and not profiles_config_path
    ):
        profiles_config_path = os.path.join(config_dir, "cloud.profiles")

    # Convert relative to absolute paths if necessary
    profiles_config_path = _absolute_path(profiles_config_path, config_dir)

    # Prepare the deploy scripts search path
    deploy_scripts_search_path = overrides.get(
        "deploy_scripts_search_path",
        defaults.get("deploy_scripts_search_path", "cloud.deploy.d"),
    )
    if isinstance(deploy_scripts_search_path, str):
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
            os.path.join(os.path.dirname(__file__), "..", "cloud", "deploy")
        )
    )

    # Let's make the search path a tuple and add it to the overrides.
    overrides.update(deploy_scripts_search_path=tuple(deploy_scripts_search_path))

    # Grab data from the 4 sources
    # 1st - Master config
    if master_config_path is not None and master_config is not None:
        raise salt.exceptions.SaltCloudConfigError(
            "Only pass `master_config` or `master_config_path`, not both."
        )
    elif master_config_path is None and master_config is None:
        master_config = salt.config.master_config(
            overrides.get(
                # use the value from the cloud config file
                "master_config",
                # if not found, use the default path
                os.path.join(salt.syspaths.CONFIG_DIR, "master"),
            )
        )
    elif master_config_path is not None and master_config is None:
        master_config = salt.config.master_config(master_config_path)

    # cloud config has a separate cachedir
    del master_config["cachedir"]

    # 2nd - salt-cloud configuration which was loaded before so we could
    # extract the master configuration file if needed.

    # Override master configuration with the salt cloud(current overrides)
    master_config.update(overrides)
    # We now set the overridden master_config as the overrides
    overrides = master_config

    if providers_config_path is not None and providers_config is not None:
        raise salt.exceptions.SaltCloudConfigError(
            "Only pass `providers_config` or `providers_config_path`, not both."
        )
    elif providers_config_path is None and providers_config is None:
        providers_config_path = overrides.get(
            # use the value from the cloud config file
            "providers_config",
            # if not found, use the default path
            os.path.join(salt.syspaths.CONFIG_DIR, "cloud.providers"),
        )

    if profiles_config_path is not None and profiles_config is not None:
        raise salt.exceptions.SaltCloudConfigError(
            "Only pass `profiles_config` or `profiles_config_path`, not both."
        )
    elif profiles_config_path is None and profiles_config is None:
        profiles_config_path = overrides.get(
            # use the value from the cloud config file
            "profiles_config",
            # if not found, use the default path
            os.path.join(salt.syspaths.CONFIG_DIR, "cloud.profiles"),
        )

    # Apply the salt-cloud configuration
    opts = apply_cloud_config(overrides, defaults)

    # 3rd - Include Cloud Providers
    if "providers" in opts:
        if providers_config is not None:
            raise salt.exceptions.SaltCloudConfigError(
                "Do not mix the old cloud providers configuration with "
                "the passing a pre-configured providers configuration "
                "dictionary."
            )

        if providers_config_path is not None:
            providers_confd = os.path.join(
                os.path.dirname(providers_config_path), "cloud.providers.d", "*"
            )

            if os.path.isfile(providers_config_path) or glob.glob(providers_confd):
                raise salt.exceptions.SaltCloudConfigError(
                    "Do not mix the old cloud providers configuration with "
                    "the new one. The providers configuration should now go "
                    "in the file `{0}` or a separate `*.conf` file within "
                    "`cloud.providers.d/` which is relative to `{0}`.".format(
                        os.path.join(salt.syspaths.CONFIG_DIR, "cloud.providers")
                    )
                )
        # No exception was raised? It's the old configuration alone
        providers_config = opts["providers"]

    elif providers_config_path is not None:
        # Load from configuration file, even if that files does not exist since
        # it will be populated with defaults.
        providers_config = cloud_providers_config(providers_config_path)

    # Let's assign back the computed providers configuration
    opts["providers"] = providers_config

    # 4th - Include VM profiles config
    if profiles_config is None:
        # Load profiles configuration from the provided file
        profiles_config = vm_profiles_config(profiles_config_path, providers_config)
    opts["profiles"] = profiles_config

    # recurse opts for sdb configs
    apply_sdb(opts)

    # prepend root_dir
    prepend_root_dirs = ["cachedir"]
    if "log_file" in opts and urllib.parse.urlparse(opts["log_file"]).scheme == "":
        prepend_root_dirs.append(opts["log_file"])
    prepend_root_dir(opts, prepend_root_dirs)

    salt.features.setup_features(opts)
    # Return the final options
    return opts


def apply_cloud_config(overrides, defaults=None):
    """
    Return a cloud config
    """
    if defaults is None:
        defaults = DEFAULT_CLOUD_OPTS.copy()

    config = defaults.copy()
    if overrides:
        config.update(overrides)

    # If the user defined providers in salt cloud's main configuration file, we
    # need to take care for proper and expected format.
    if "providers" in config:
        # Keep a copy of the defined providers
        providers = config["providers"].copy()
        # Reset the providers dictionary
        config["providers"] = {}
        # Populate the providers dictionary
        for alias, details in providers.items():
            if isinstance(details, list):
                for detail in details:
                    if "driver" not in detail:
                        raise salt.exceptions.SaltCloudConfigError(
                            "The cloud provider alias '{}' has an entry "
                            "missing the required setting of 'driver'.".format(alias)
                        )

                    driver = detail["driver"]

                    if ":" in driver:
                        # Weird, but...
                        alias, driver = driver.split(":")

                    if alias not in config["providers"]:
                        config["providers"][alias] = {}

                    detail["provider"] = f"{alias}:{driver}"
                    config["providers"][alias][driver] = detail
            elif isinstance(details, dict):
                if "driver" not in details:
                    raise salt.exceptions.SaltCloudConfigError(
                        "The cloud provider alias '{}' has an entry "
                        "missing the required setting of 'driver'".format(alias)
                    )

                driver = details["driver"]

                if ":" in driver:
                    # Weird, but...
                    alias, driver = driver.split(":")
                if alias not in config["providers"]:
                    config["providers"][alias] = {}

                details["provider"] = f"{alias}:{driver}"
                config["providers"][alias][driver] = details

    # Migrate old configuration
    config = old_to_new(config)

    return config


def old_to_new(opts):
    providers = (
        "AWS",
        "CLOUDSTACK",
        "DIGITALOCEAN",
        "EC2",
        "GOGRID",
        "IBMSCE",
        "JOYENT",
        "LINODE",
        "OPENSTACK",
        "PARALLELS",
        "RACKSPACE",
        "SALTIFY",
    )

    for provider in providers:

        provider_config = {}
        for opt, val in opts.items():
            if provider in opt:
                value = val
                name = opt.split(".", 1)[1]
                provider_config[name] = value

        lprovider = provider.lower()
        if provider_config:
            provider_config["provider"] = lprovider
            opts.setdefault("providers", {})
            # provider alias
            opts["providers"][lprovider] = {}
            # provider alias, provider driver
            opts["providers"][lprovider][lprovider] = provider_config
    return opts


def vm_profiles_config(path, providers, env_var="SALT_CLOUDVM_CONFIG", defaults=None):
    """
    Read in the salt cloud VM config file
    """
    if defaults is None:
        defaults = VM_CONFIG_DEFAULTS

    overrides = salt.config.load_config(
        path, env_var, os.path.join(salt.syspaths.CONFIG_DIR, "cloud.profiles")
    )

    default_include = overrides.get("default_include", defaults["default_include"])
    include = overrides.get("include", [])

    overrides.update(salt.config.include_config(default_include, path, verbose=False))
    overrides.update(salt.config.include_config(include, path, verbose=True))
    return apply_vm_profiles_config(providers, overrides, defaults)


def apply_vm_profiles_config(providers, overrides, defaults=None):
    if defaults is None:
        defaults = VM_CONFIG_DEFAULTS

    config = defaults.copy()
    if overrides:
        config.update(overrides)

    vms = {}

    for key, val in config.items():
        if key in ("conf_file", "include", "default_include", "user"):
            continue
        if not isinstance(val, dict):
            raise salt.exceptions.SaltCloudConfigError(
                "The VM profiles configuration found in '{0[conf_file]}' is "
                "not in the proper format".format(config)
            )
        val["profile"] = key
        vms[key] = val

    # Is any VM profile extending data!?
    for profile, details in vms.copy().items():
        if "extends" not in details:
            if ":" in details["provider"]:
                alias, driver = details["provider"].split(":")
                if alias not in providers or driver not in providers[alias]:
                    log.trace(
                        "The profile '%s' is defining '%s' "
                        "as the provider. Since there is no valid "
                        "configuration for that provider, the profile will be "
                        "removed from the available listing",
                        profile,
                        details["provider"],
                    )
                    vms.pop(profile)
                    continue

                if "profiles" not in providers[alias][driver]:
                    providers[alias][driver]["profiles"] = {}
                providers[alias][driver]["profiles"][profile] = details

            if details["provider"] not in providers:
                log.trace(
                    "The profile '%s' is defining '%s' as the "
                    "provider. Since there is no valid configuration for "
                    "that provider, the profile will be removed from the "
                    "available listing",
                    profile,
                    details["provider"],
                )
                vms.pop(profile)
                continue

            driver = next(iter(list(providers[details["provider"]].keys())))
            providers[details["provider"]][driver].setdefault("profiles", {}).update(
                {profile: details}
            )
            details["provider"] = "{0[provider]}:{1}".format(details, driver)
            vms[profile] = details

            continue

        extends = details.pop("extends")
        if extends not in vms:
            log.error(
                "The '%s' profile is trying to extend data from '%s' "
                "though '%s' is not defined in the salt profiles loaded "
                "data. Not extending and removing from listing!",
                profile,
                extends,
                extends,
            )
            vms.pop(profile)
            continue

        extended = deepcopy(vms.get(extends))
        extended.pop("profile")
        # Merge extended configuration with base profile
        extended = salt.utils.dictupdate.update(extended, details)

        if ":" not in extended["provider"]:
            if extended["provider"] not in providers:
                log.trace(
                    "The profile '%s' is defining '%s' as the "
                    "provider. Since there is no valid configuration for "
                    "that provider, the profile will be removed from the "
                    "available listing",
                    profile,
                    extended["provider"],
                )
                vms.pop(profile)
                continue

            driver = next(iter(list(providers[extended["provider"]].keys())))
            providers[extended["provider"]][driver].setdefault("profiles", {}).update(
                {profile: extended}
            )

            extended["provider"] = "{0[provider]}:{1}".format(extended, driver)
        else:
            alias, driver = extended["provider"].split(":")
            if alias not in providers or driver not in providers[alias]:
                log.trace(
                    "The profile '%s' is defining '%s' as "
                    "the provider. Since there is no valid configuration "
                    "for that provider, the profile will be removed from "
                    "the available listing",
                    profile,
                    extended["provider"],
                )
                vms.pop(profile)
                continue

            providers[alias][driver].setdefault("profiles", {}).update(
                {profile: extended}
            )

        # Update the profile's entry with the extended data
        vms[profile] = extended

    return vms


def cloud_providers_config(path, env_var="SALT_CLOUD_PROVIDERS_CONFIG", defaults=None):
    """
    Read in the salt cloud providers configuration file
    """
    if defaults is None:
        defaults = PROVIDER_CONFIG_DEFAULTS

    overrides = salt.config.load_config(
        path, env_var, os.path.join(salt.syspaths.CONFIG_DIR, "cloud.providers")
    )

    default_include = overrides.get("default_include", defaults["default_include"])
    include = overrides.get("include", [])

    overrides.update(salt.config.include_config(default_include, path, verbose=False))
    overrides.update(salt.config.include_config(include, path, verbose=True))
    return apply_cloud_providers_config(overrides, defaults)


def apply_cloud_providers_config(overrides, defaults=None):
    """
    Apply the loaded cloud providers configuration.
    """
    if defaults is None:
        defaults = PROVIDER_CONFIG_DEFAULTS

    config = defaults.copy()
    if overrides:
        config.update(overrides)

    # Is the user still using the old format in the new configuration file?!
    for name, settings in config.copy().items():
        if "." in name:
            log.warning("Please switch to the new providers configuration syntax")

            # Let's help out and migrate the data
            config = old_to_new(config)

            # old_to_new will migrate the old data into the 'providers' key of
            # the config dictionary. Let's map it correctly
            for prov_name, prov_settings in config.pop("providers").items():
                config[prov_name] = prov_settings
            break

    providers = {}
    ext_count = 0
    for key, val in config.items():
        if key in ("conf_file", "include", "default_include", "user"):
            continue

        if not isinstance(val, (list, tuple)):
            val = [val]
        else:
            # Need to check for duplicate cloud provider entries per "alias" or
            # we won't be able to properly reference it.
            handled_providers = set()
            for details in val:
                if "driver" not in details:
                    if "extends" not in details:
                        log.error(
                            "Please check your cloud providers configuration. "
                            "There's no 'driver' nor 'extends' definition "
                            "referenced."
                        )
                    continue

                if details["driver"] in handled_providers:
                    log.error(
                        "You can only have one entry per cloud provider. For "
                        "example, if you have a cloud provider configuration "
                        "section named, 'production', you can only have a "
                        "single entry for EC2, Joyent, Openstack, and so "
                        "forth."
                    )
                    raise salt.exceptions.SaltCloudConfigError(
                        "The cloud provider alias '{0}' has multiple entries "
                        "for the '{1[driver]}' driver.".format(key, details)
                    )
                handled_providers.add(details["driver"])

        for entry in val:

            if "driver" not in entry:
                entry["driver"] = f"-only-extendable-{ext_count}"
                ext_count += 1

            if key not in providers:
                providers[key] = {}

            provider = entry["driver"]
            if provider not in providers[key]:
                providers[key][provider] = entry

    # Is any provider extending data!?
    while True:
        keep_looping = False
        for provider_alias, entries in providers.copy().items():
            for driver, details in entries.items():
                # Set a holder for the defined profiles
                providers[provider_alias][driver]["profiles"] = {}

                if "extends" not in details:
                    continue

                extends = details.pop("extends")

                if ":" in extends:
                    alias, provider = extends.split(":")
                    if alias not in providers:
                        raise salt.exceptions.SaltCloudConfigError(
                            "The '{0}' cloud provider entry in '{1}' is "
                            "trying to extend data from '{2}' though "
                            "'{2}' is not defined in the salt cloud "
                            "providers loaded data.".format(
                                details["driver"], provider_alias, alias
                            )
                        )

                    if provider not in providers.get(alias):
                        raise salt.exceptions.SaltCloudConfigError(
                            "The '{0}' cloud provider entry in '{1}' is "
                            "trying to extend data from '{2}:{3}' though "
                            "'{3}' is not defined in '{1}'".format(
                                details["driver"], provider_alias, alias, provider
                            )
                        )
                    details["extends"] = f"{alias}:{provider}"
                    # change provider details '-only-extendable-' to extended
                    # provider name
                    details["driver"] = provider
                elif providers.get(extends):
                    raise salt.exceptions.SaltCloudConfigError(
                        "The '{}' cloud provider entry in '{}' is "
                        "trying to extend from '{}' and no provider was "
                        "specified. Not extending!".format(
                            details["driver"], provider_alias, extends
                        )
                    )
                elif extends not in providers:
                    raise salt.exceptions.SaltCloudConfigError(
                        "The '{0}' cloud provider entry in '{1}' is "
                        "trying to extend data from '{2}' though '{2}' "
                        "is not defined in the salt cloud providers loaded "
                        "data.".format(details["driver"], provider_alias, extends)
                    )
                else:
                    if driver in providers.get(extends):
                        details["extends"] = f"{extends}:{driver}"
                    elif "-only-extendable-" in providers.get(extends):
                        details["extends"] = "{}:{}".format(
                            extends, f"-only-extendable-{ext_count}"
                        )
                    else:
                        # We're still not aware of what we're trying to extend
                        # from. Let's try on next iteration
                        details["extends"] = extends
                        keep_looping = True
        if not keep_looping:
            break

    while True:
        # Merge provided extends
        keep_looping = False
        for alias, entries in providers.copy().items():
            for driver in list(entries.keys()):
                # Don't use iteritems, because the values of the dictionary will be changed
                details = entries[driver]

                if "extends" not in details:
                    # Extends resolved or non existing, continue!
                    continue

                if "extends" in details["extends"]:
                    # Since there's a nested extends, resolve this one in the
                    # next iteration
                    keep_looping = True
                    continue

                # Let's get a reference to what we're supposed to extend
                extends = details.pop("extends")
                # Split the setting in (alias, driver)
                ext_alias, ext_driver = extends.split(":")
                # Grab a copy of what should be extended
                extended = providers.get(ext_alias).get(ext_driver).copy()
                # Merge the data to extend with the details
                extended = salt.utils.dictupdate.update(extended, details)
                # Update the providers dictionary with the merged data
                providers[alias][driver] = extended
                # Update name of the driver, now that it's populated with extended information
                if driver.startswith("-only-extendable-"):
                    providers[alias][ext_driver] = providers[alias][driver]
                    # Delete driver with old name to maintain dictionary size
                    del providers[alias][driver]

        if not keep_looping:
            break

    # Now clean up any providers entry that was just used to be a data tree to
    # extend from
    for provider_alias, entries in providers.copy().items():
        for driver, details in entries.copy().items():
            if not driver.startswith("-only-extendable-"):
                continue

            log.info(
                "There's at least one cloud driver under the '%s' "
                "cloud provider alias which does not have the required "
                "'driver' setting. Removing it from the available "
                "providers listing.",
                provider_alias,
            )
            providers[provider_alias].pop(driver)

        if not providers[provider_alias]:
            providers.pop(provider_alias)

    return providers


def get_cloud_config_value(name, vm_, opts, default=None, search_global=True):
    """
    Search and return a setting in a known order:

        1. In the virtual machine's configuration
        2. In the virtual machine's profile configuration
        3. In the virtual machine's provider configuration
        4. In the salt cloud configuration if global searching is enabled
        5. Return the provided default
    """

    # As a last resort, return the default
    value = default

    if search_global is True and opts.get(name, None) is not None:
        # The setting name exists in the cloud(global) configuration
        value = deepcopy(opts[name])

    if vm_ and name:
        # Let's get the value from the profile, if present
        if "profile" in vm_ and vm_["profile"] is not None:
            if name in opts["profiles"][vm_["profile"]]:
                if isinstance(value, dict) and isinstance(
                    opts["profiles"][vm_["profile"]][name], dict
                ):
                    value.update(opts["profiles"][vm_["profile"]][name].copy())
                else:
                    value = deepcopy(opts["profiles"][vm_["profile"]][name])

        # Let's get the value from the provider, if present.
        if ":" in vm_["driver"]:
            # The provider is defined as <provider-alias>:<driver-name>
            alias, driver = vm_["driver"].split(":")
            if alias in opts["providers"] and driver in opts["providers"][alias]:
                details = opts["providers"][alias][driver]
                if name in details:
                    if isinstance(value, dict):
                        value.update(details[name].copy())
                    else:
                        value = deepcopy(details[name])
        elif len(opts["providers"].get(vm_["driver"], ())) > 1:
            # The provider is NOT defined as <provider-alias>:<driver-name>
            # and there's more than one entry under the alias.
            # WARN the user!!!!
            log.error(
                "The '%s' cloud provider definition has more than one "
                "entry. Your VM configuration should be specifying the "
                "provider as 'driver: %s:<driver-engine>'. Since "
                "it's not, we're returning the first definition which "
                "might not be what you intended.",
                vm_["driver"],
                vm_["driver"],
            )

        if vm_["driver"] in opts["providers"]:
            # There's only one driver defined for this provider. This is safe.
            alias_defs = opts["providers"].get(vm_["driver"])
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
            value = next(vm_[name], "")
        else:
            if isinstance(value, dict) and isinstance(vm_[name], dict):
                value.update(vm_[name].copy())
            else:
                value = deepcopy(vm_[name])

    return value


def is_provider_configured(
    opts, provider, required_keys=(), log_message=True, aliases=()
):
    """
    Check and return the first matching and fully configured cloud provider
    configuration.
    """
    if ":" in provider:
        alias, driver = provider.split(":")
        if alias not in opts["providers"]:
            return False
        if driver not in opts["providers"][alias]:
            return False
        for key in required_keys:
            if opts["providers"][alias][driver].get(key, None) is None:
                if log_message is True:
                    # There's at least one require configuration key which is not
                    # set.
                    log.warning(
                        "The required '%s' configuration setting is missing "
                        "from the '%s' driver, which is configured under the "
                        "'%s' alias.",
                        key,
                        provider,
                        alias,
                    )
                return False
        # If we reached this far, there's a properly configured provider.
        # Return it!
        return opts["providers"][alias][driver]

    for alias, drivers in opts["providers"].items():
        for driver, provider_details in drivers.items():
            if driver != provider and driver not in aliases:
                continue

            # If we reached this far, we have a matching provider, let's see if
            # all required configuration keys are present and not None.
            skip_provider = False
            for key in required_keys:
                if provider_details.get(key, None) is None:
                    if log_message is True:
                        # This provider does not include all necessary keys,
                        # continue to next one.
                        log.warning(
                            "The required '%s' configuration setting is "
                            "missing from the '%s' driver, which is configured "
                            "under the '%s' alias.",
                            key,
                            provider,
                            alias,
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
    """
    Check if the requested profile contains the minimum required parameters for
    a profile.

    Required parameters include image and provider for all drivers, while some
    drivers also require size keys.

    .. versionadded:: 2015.8.0
    """
    # Standard dict keys required by all drivers.
    required_keys = ["provider"]
    alias, driver = provider.split(":")

    # Most drivers need an image to be specified, but some do not.
    non_image_drivers = [
        "nova",
        "virtualbox",
        "libvirt",
        "softlayer",
        "oneandone",
        "profitbricks",
    ]

    # Most drivers need a size, but some do not.
    non_size_drivers = [
        "opennebula",
        "parallels",
        "proxmox",
        "scaleway",
        "softlayer",
        "softlayer_hw",
        "vmware",
        "vsphere",
        "virtualbox",
        "libvirt",
        "oneandone",
        "profitbricks",
    ]

    provider_key = opts["providers"][alias][driver]
    profile_key = opts["providers"][alias][driver]["profiles"][profile_name]

    # If cloning on Linode, size and image are not necessary.
    # They are obtained from the to-be-cloned VM.
    if driver == "linode" and profile_key.get("clonefrom", False):
        non_image_drivers.append("linode")
        non_size_drivers.append("linode")
    elif driver == "gce" and "sourceImage" in str(vm_.get("ex_disks_gce_struct")):
        non_image_drivers.append("gce")

    # If cloning on VMware, specifying image is not necessary.
    if driver == "vmware" and "image" not in list(profile_key.keys()):
        non_image_drivers.append("vmware")

    if driver not in non_image_drivers:
        required_keys.append("image")
        if driver == "vmware":
            required_keys.append("datastore")
    elif driver in ["linode", "virtualbox"]:
        required_keys.append("clonefrom")
    elif driver == "nova":
        nova_image_keys = [
            "image",
            "block_device_mapping",
            "block_device",
            "boot_volume",
        ]
        if not any([key in provider_key for key in nova_image_keys]) and not any(
            [key in profile_key for key in nova_image_keys]
        ):
            required_keys.extend(nova_image_keys)

    if driver not in non_size_drivers:
        required_keys.append("size")

    # Check if required fields are supplied in the provider config. If they
    # are present, remove it from the required_keys list.
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
                "The required '%s' configuration setting is missing from "
                "the '%s' profile, which is configured under the '%s' alias.",
                item,
                profile_name,
                alias,
            )
            return False

    return True


def check_driver_dependencies(driver, dependencies):
    """
    Check if the driver's dependencies are available.

    .. versionadded:: 2015.8.0

    driver
        The name of the driver.

    dependencies
        The dictionary of dependencies to check.
    """
    ret = True
    for key, value in dependencies.items():
        if value is False:
            log.warning(
                "Missing dependency: '%s'. The %s driver requires "
                "'%s' to be installed.",
                key,
                driver,
                key,
            )
            ret = False

    return ret


# <---- Salt Cloud Configuration Functions -----------------------------------


def _cache_id(minion_id, cache_file):
    """
    Helper function, writes minion id to a cache file.
    """
    path = os.path.dirname(cache_file)
    try:
        if not os.path.isdir(path):
            os.makedirs(path)
    except OSError as exc:
        # Handle race condition where dir is created after os.path.isdir check
        if os.path.isdir(path):
            pass
        else:
            log.error("Failed to create dirs to minion_id file: %s", exc)

    try:
        with salt.utils.files.fopen(cache_file, "w") as idf:
            idf.write(minion_id)
    except OSError as exc:
        log.error("Could not cache minion ID: %s", exc)


def call_id_function(opts):
    """
    Evaluate the function that determines the ID if the 'id_function'
    option is set and return the result
    """
    if opts.get("id"):
        return opts["id"]

    # Import 'salt.loader' here to avoid a circular dependency
    import salt.loader as loader

    if isinstance(opts["id_function"], str):
        mod_fun = opts["id_function"]
        fun_kwargs = {}
    elif isinstance(opts["id_function"], dict):
        mod_fun, fun_kwargs = next(iter(opts["id_function"].items()))
        if fun_kwargs is None:
            fun_kwargs = {}
    else:
        log.error("'id_function' option is neither a string nor a dictionary")
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    # split module and function and try loading the module
    mod, fun = mod_fun.split(".")
    if not opts.get("grains"):
        # Get grains for use by the module
        opts["grains"] = loader.grains(opts)

    try:
        id_mod = loader.raw_mod(opts, mod, fun)
        if not id_mod:
            raise KeyError
        # we take whatever the module returns as the minion ID
        newid = id_mod[mod_fun](**fun_kwargs)
        if not isinstance(newid, str) or not newid:
            log.error(
                'Function %s returned value "%s" of type %s instead of string',
                mod_fun,
                newid,
                type(newid),
            )
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        log.info("Evaluated minion ID from module: %s %s", mod_fun, newid)
        return newid
    except TypeError:
        log.error(
            "Function arguments %s are incorrect for function %s", fun_kwargs, mod_fun
        )
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)
    except KeyError:
        log.error("Failed to load module %s", mod_fun)
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)


def remove_domain_from_fqdn(opts, newid):
    """
    Depending on the values of `minion_id_remove_domain`,
    remove all domains or a single domain from a FQDN, effectivly generating a hostname.
    """
    opt_domain = opts.get("minion_id_remove_domain")
    if opt_domain is True:
        if "." in newid:
            # Remove any domain
            newid, xdomain = newid.split(".", 1)
            log.debug("Removed any domain (%s) from minion id.", xdomain)
    else:
        # Must be string type
        if newid.upper().endswith("." + opt_domain.upper()):
            # Remove single domain
            newid = newid[: -len("." + opt_domain)]
            log.debug("Removed single domain %s from minion id.", opt_domain)
    return newid


def get_id(opts, cache_minion_id=False):
    """
    Guess the id of the minion.

    If CONFIG_DIR/minion_id exists, use the cached minion ID from that file.
    If no minion id is configured, use multiple sources to find a FQDN.
    If no FQDN is found you may get an ip address.

    Returns two values: the detected ID, and a boolean value noting whether or
    not an IP address is being used for the ID.
    """
    if opts["root_dir"] is None:
        root_dir = salt.syspaths.ROOT_DIR
    else:
        root_dir = opts["root_dir"]

    config_dir = salt.syspaths.CONFIG_DIR
    if config_dir.startswith(salt.syspaths.ROOT_DIR):
        config_dir = config_dir.split(salt.syspaths.ROOT_DIR, 1)[-1]

    # Check for cached minion ID
    id_cache = os.path.join(root_dir, config_dir.lstrip(os.path.sep), "minion_id")

    if opts.get("minion_id_caching", True):
        try:
            with salt.utils.files.fopen(id_cache) as idf:
                name = salt.utils.stringutils.to_unicode(idf.readline().strip())
                bname = salt.utils.stringutils.to_bytes(name)
                if bname.startswith(codecs.BOM):  # Remove BOM if exists
                    name = salt.utils.stringutils.to_str(
                        bname.replace(codecs.BOM, "", 1)
                    )
            if name and name != "localhost":
                log.debug("Using cached minion ID from %s: %s", id_cache, name)
                return name, False
        except OSError:
            pass
    if "__role" in opts and opts.get("__role") == "minion":
        log.debug(
            "Guessing ID. The id can be explicitly set in %s",
            os.path.join(salt.syspaths.CONFIG_DIR, "minion"),
        )

    if opts.get("id_function"):
        newid = call_id_function(opts)
    else:
        newid = salt.utils.network.generate_minion_id()

    if opts.get("minion_id_lowercase"):
        newid = newid.lower()
        log.debug("Changed minion id %s to lowercase.", newid)

    # Optionally remove one or many domains in a generated minion id
    if opts.get("minion_id_remove_domain"):
        newid = remove_domain_from_fqdn(opts, newid)

    if "__role" in opts and opts.get("__role") == "minion":
        if opts.get("id_function"):
            log.debug(
                "Found minion id from external function %s: %s",
                opts["id_function"],
                newid,
            )
        else:
            log.debug("Found minion id from generate_minion_id(): %s", newid)
    if cache_minion_id and opts.get("minion_id_caching", True):
        _cache_id(newid, id_cache)
    is_ipv4 = salt.utils.network.is_ipv4(newid)
    return newid, is_ipv4


def _update_ssl_config(opts):
    """
    Resolves string names to integer constant in ssl configuration.
    """
    if opts["ssl"] in (None, False):
        opts["ssl"] = None
        return
    if opts["ssl"] is True:
        opts["ssl"] = {}
        return
    import ssl

    for key, prefix in (("cert_reqs", "CERT_"), ("ssl_version", "PROTOCOL_")):
        val = opts["ssl"].get(key)
        if val is None:
            continue
        if (
            not isinstance(val, str)
            or not val.startswith(prefix)
            or not hasattr(ssl, val)
        ):
            message = "SSL option '{}' must be set to one of the following values: '{}'.".format(
                key,
                "', '".join([val for val in dir(ssl) if val.startswith(prefix)]),
            )
            log.error(message)
            raise salt.exceptions.SaltConfigurationError(message)
        opts["ssl"][key] = getattr(ssl, val)


def _adjust_log_file_override(overrides, default_log_file):
    """
    Adjusts the log_file based on the log_dir override
    """
    if overrides.get("log_dir"):
        # Adjust log_file if a log_dir override is introduced
        if overrides.get("log_file"):
            if not os.path.isabs(overrides["log_file"]):
                # Prepend log_dir if log_file is relative
                overrides["log_file"] = os.path.join(
                    overrides["log_dir"], overrides["log_file"]
                )
        else:
            # Create the log_file override
            overrides["log_file"] = os.path.join(
                overrides["log_dir"], os.path.basename(default_log_file)
            )


def apply_minion_config(
    overrides=None, defaults=None, cache_minion_id=False, minion_id=None
):
    """
    Returns minion configurations dict.
    """
    if defaults is None:
        defaults = DEFAULT_MINION_OPTS.copy()
    if overrides is None:
        overrides = {}

    opts = defaults.copy()
    opts["__role"] = "minion"
    _adjust_log_file_override(overrides, defaults["log_file"])
    if overrides:
        opts.update(overrides)

    if "environment" in opts:
        if opts["saltenv"] is not None:
            log.warning(
                "The 'saltenv' and 'environment' minion config options "
                "cannot both be used. Ignoring 'environment' in favor of "
                "'saltenv'."
            )
            # Set environment to saltenv in case someone's custom module is
            # refrencing __opts__['environment']
            opts["environment"] = opts["saltenv"]
        else:
            log.warning(
                "The 'environment' minion config option has been renamed "
                "to 'saltenv'. Using %s as the 'saltenv' config value.",
                opts["environment"],
            )
            opts["saltenv"] = opts["environment"]

    for idx, val in enumerate(opts["fileserver_backend"]):
        if val in ("git", "hg", "svn", "minion"):
            new_val = val + "fs"
            log.debug(
                "Changed %s to %s in minion opts' fileserver_backend list", val, new_val
            )
            opts["fileserver_backend"][idx] = new_val

    opts["__cli"] = salt.utils.stringutils.to_unicode(
        os.path.basename(salt.utils.path.expand(sys.argv[0]))
    )

    # No ID provided. Will getfqdn save us?
    using_ip_for_id = False
    if not opts.get("id"):
        if minion_id:
            opts["id"] = minion_id
        else:
            opts["id"], using_ip_for_id = get_id(opts, cache_minion_id=cache_minion_id)

    # it does not make sense to append a domain to an IP based id
    if not using_ip_for_id and "append_domain" in opts:
        opts["id"] = _append_domain(opts)

    for directory in opts.get("append_minionid_config_dirs", []):
        if directory in ("pki_dir", "cachedir", "extension_modules"):
            newdirectory = os.path.join(opts[directory], opts["id"])
            opts[directory] = newdirectory
        elif directory == "default_include" and directory in opts:
            include_dir = os.path.dirname(opts[directory])
            new_include_dir = os.path.join(
                include_dir, opts["id"], os.path.basename(opts[directory])
            )
            opts[directory] = new_include_dir

    # pidfile can be in the list of append_minionid_config_dirs, but pidfile
    # is the actual path with the filename, not a directory.
    if "pidfile" in opts.get("append_minionid_config_dirs", []):
        newpath_list = os.path.split(opts["pidfile"])
        opts["pidfile"] = os.path.join(
            newpath_list[0], "salt", opts["id"], newpath_list[1]
        )

    if len(opts["sock_dir"]) > len(opts["cachedir"]) + 10:
        opts["sock_dir"] = os.path.join(opts["cachedir"], ".salt-unix")

    # Enabling open mode requires that the value be set to True, and
    # nothing else!
    opts["open_mode"] = opts["open_mode"] is True
    opts["file_roots"] = _validate_file_roots(opts["file_roots"])
    opts["pillar_roots"] = _validate_pillar_roots(opts["pillar_roots"])
    # Make sure ext_mods gets set if it is an untrue value
    # (here to catch older bad configs)
    opts["extension_modules"] = opts.get("extension_modules") or os.path.join(
        opts["cachedir"], "extmods"
    )
    # Set up the utils_dirs location from the extension_modules location
    opts["utils_dirs"] = opts.get("utils_dirs") or [
        os.path.join(opts["extension_modules"], "utils")
    ]

    # Insert all 'utils_dirs' directories to the system path
    insert_system_path(opts, opts["utils_dirs"])

    # Prepend root_dir to other paths
    prepend_root_dirs = [
        "pki_dir",
        "cachedir",
        "sock_dir",
        "extension_modules",
        "pidfile",
    ]

    # These can be set to syslog, so, not actual paths on the system
    for config_key in ("log_file", "key_logfile"):
        if urllib.parse.urlparse(opts.get(config_key, "")).scheme == "":
            prepend_root_dirs.append(config_key)

    prepend_root_dir(opts, prepend_root_dirs)

    # if there is no beacons option yet, add an empty beacons dict
    if "beacons" not in opts:
        opts["beacons"] = {}

    if overrides.get("ipc_write_buffer", "") == "dynamic":
        opts["ipc_write_buffer"] = _DFLT_IPC_WBUFFER
    if "ipc_write_buffer" not in overrides:
        opts["ipc_write_buffer"] = 0

    # Make sure hash_type is lowercase
    opts["hash_type"] = opts["hash_type"].lower()

    # Check and update TLS/SSL configuration
    _update_ssl_config(opts)
    _update_discovery_config(opts)

    return opts


def _update_discovery_config(opts):
    """
    Update discovery config for all instances.

    :param opts:
    :return:
    """
    if opts.get("discovery") not in (None, False):
        if opts["discovery"] is True:
            opts["discovery"] = {}
        discovery_config = {
            "attempts": 3,
            "pause": 5,
            "port": 4520,
            "match": "any",
            "mapping": {},
        }
        for key in opts["discovery"]:
            if key not in discovery_config:
                raise salt.exceptions.SaltConfigurationError(
                    f"Unknown discovery option: {key}"
                )
        if opts.get("__role") != "minion":
            for key in ["attempts", "pause", "match"]:
                del discovery_config[key]
        opts["discovery"] = salt.utils.dictupdate.update(
            discovery_config, opts["discovery"], True, True
        )


def master_config(
    path, env_var="SALT_MASTER_CONFIG", defaults=None, exit_on_config_errors=False
):
    """
    Reads in the master configuration file and sets up default options

    This is useful for running the actual master daemon. For running
    Master-side client interfaces that need the master opts see
    :py:func:`salt.client.client_config`.
    """
    if defaults is None:
        defaults = DEFAULT_MASTER_OPTS.copy()

    if not os.environ.get(env_var, None):
        # No valid setting was given using the configuration variable.
        # Lets see is SALT_CONFIG_DIR is of any use
        salt_config_dir = os.environ.get("SALT_CONFIG_DIR", None)
        if salt_config_dir:
            env_config_file_path = os.path.join(salt_config_dir, "master")
            if salt_config_dir and os.path.isfile(env_config_file_path):
                # We can get a configuration file using SALT_CONFIG_DIR, let's
                # update the environment with this information
                os.environ[env_var] = env_config_file_path

    overrides = load_config(path, env_var, DEFAULT_MASTER_OPTS["conf_file"])
    default_include = overrides.get("default_include", defaults["default_include"])
    include = overrides.get("include", [])

    overrides.update(
        include_config(
            default_include,
            path,
            verbose=False,
            exit_on_config_errors=exit_on_config_errors,
        )
    )
    overrides.update(
        include_config(
            include, path, verbose=True, exit_on_config_errors=exit_on_config_errors
        )
    )
    opts = apply_master_config(overrides, defaults)
    _validate_ssh_minion_opts(opts)
    _validate_opts(opts)
    # If 'nodegroups:' is uncommented in the master config file, and there are
    # no nodegroups defined, opts['nodegroups'] will be None. Fix this by
    # reverting this value to the default, as if 'nodegroups:' was commented
    # out or not present.
    if opts.get("nodegroups") is None:
        opts["nodegroups"] = DEFAULT_MASTER_OPTS.get("nodegroups", {})
    if salt.utils.data.is_dictlist(opts["nodegroups"]):
        opts["nodegroups"] = salt.utils.data.repack_dictlist(opts["nodegroups"])
    apply_sdb(opts)
    salt.features.setup_features(opts)
    return opts


def apply_master_config(overrides=None, defaults=None):
    """
    Returns master configurations dict.
    """
    if defaults is None:
        defaults = DEFAULT_MASTER_OPTS.copy()
    if overrides is None:
        overrides = {}

    opts = defaults.copy()
    opts["__role"] = "master"

    # Suppress fileserver update in FSChan, for FSClient instances generated
    # during Pillar compilation. The master daemon already handles FS updates
    # in its maintenance thread. Refreshing during Pillar compilation slows
    # down Pillar considerably (even to the point of timeout) when there are
    # many gitfs remotes.
    opts["__fs_update"] = True

    _adjust_log_file_override(overrides, defaults["log_file"])
    if overrides:
        opts.update(overrides)
    # `keep_acl_in_token` will be forced to True when using external authentication
    # for REST API (`rest` is present under `external_auth`). This is because the REST API
    # does not store the password, and can therefore not retroactively fetch the ACL, so
    # the ACL must be stored in the token.
    if "rest" in opts.get("external_auth", {}):
        # Check current value and print out warning
        if opts["keep_acl_in_token"] is False:
            log.warning(
                "The 'rest' external_auth backend requires 'keep_acl_in_token' to be True. "
                "Setting 'keep_acl_in_token' to True."
            )
        opts["keep_acl_in_token"] = True

    opts["__cli"] = salt.utils.stringutils.to_unicode(
        os.path.basename(salt.utils.path.expand(sys.argv[0]))
    )

    if "environment" in opts:
        if opts["saltenv"] is not None:
            log.warning(
                "The 'saltenv' and 'environment' master config options "
                "cannot both be used. Ignoring 'environment' in favor of "
                "'saltenv'."
            )
            # Set environment to saltenv in case someone's custom runner is
            # refrencing __opts__['environment']
            opts["environment"] = opts["saltenv"]
        else:
            log.warning(
                "The 'environment' master config option has been renamed "
                "to 'saltenv'. Using %s as the 'saltenv' config value.",
                opts["environment"],
            )
            opts["saltenv"] = opts["environment"]

    for idx, val in enumerate(opts["fileserver_backend"]):
        if val in ("git", "hg", "svn", "minion"):
            new_val = val + "fs"
            log.debug(
                "Changed %s to %s in master opts' fileserver_backend list", val, new_val
            )
            opts["fileserver_backend"][idx] = new_val

    if len(opts["sock_dir"]) > len(opts["cachedir"]) + 10:
        opts["sock_dir"] = os.path.join(opts["cachedir"], ".salt-unix")

    opts["token_dir"] = os.path.join(opts["cachedir"], "tokens")
    opts["syndic_dir"] = os.path.join(opts["cachedir"], "syndics")
    # Make sure ext_mods gets set if it is an untrue value
    # (here to catch older bad configs)
    opts["extension_modules"] = opts.get("extension_modules") or os.path.join(
        opts["cachedir"], "extmods"
    )
    # Set up the utils_dirs location from the extension_modules location
    opts["utils_dirs"] = opts.get("utils_dirs") or [
        os.path.join(opts["extension_modules"], "utils")
    ]

    # Insert all 'utils_dirs' directories to the system path
    insert_system_path(opts, opts["utils_dirs"])

    if overrides.get("ipc_write_buffer", "") == "dynamic":
        opts["ipc_write_buffer"] = _DFLT_IPC_WBUFFER
    if "ipc_write_buffer" not in overrides:
        opts["ipc_write_buffer"] = 0
    using_ip_for_id = False
    append_master = False
    if not opts.get("id"):
        opts["id"], using_ip_for_id = get_id(opts, cache_minion_id=None)
        append_master = True

    # it does not make sense to append a domain to an IP based id
    if not using_ip_for_id and "append_domain" in opts:
        opts["id"] = _append_domain(opts)
    if append_master:
        opts["id"] += "_master"

    # Prepend root_dir to other paths
    prepend_root_dirs = [
        "pki_dir",
        "cachedir",
        "pidfile",
        "sock_dir",
        "extension_modules",
        "autosign_file",
        "autoreject_file",
        "token_dir",
        "syndic_dir",
        "sqlite_queue_dir",
        "autosign_grains_dir",
    ]

    # These can be set to syslog, so, not actual paths on the system
    for config_key in ("log_file", "key_logfile", "ssh_log_file"):
        log_setting = opts.get(config_key, "")
        if log_setting is None:
            continue

        if urllib.parse.urlparse(log_setting).scheme == "":
            prepend_root_dirs.append(config_key)

    prepend_root_dir(opts, prepend_root_dirs)

    # When a cluster id is defined, make sure the other nessicery bits a
    # defined.
    if "cluster_id" not in opts:
        opts["cluster_id"] = None
    if opts["cluster_id"] is not None:
        if not opts.get("cluster_peers", None):
            log.warning("Cluster id defined without defining cluster peers")
            opts["cluster_peers"] = []
        if not opts.get("cluster_pki_dir", None):
            log.warning(
                "Cluster id defined without defining cluster pki, falling back to pki_dir"
            )
            opts["cluster_pki_dir"] = opts["pki_dir"]
    else:
        if opts.get("cluster_peers", None):
            log.warning("Cluster peers defined without a cluster_id, ignoring.")
            opts["cluster_peers"] = []
        if opts.get("cluster_pki_dir", None):
            log.warning("Cluster pki defined without a cluster_id, ignoring.")
            opts["cluster_pki_dir"] = None

    # Enabling open mode requires that the value be set to True, and
    # nothing else!
    opts["open_mode"] = opts["open_mode"] is True
    opts["auto_accept"] = opts["auto_accept"] is True
    opts["file_roots"] = _validate_file_roots(opts["file_roots"])
    opts["pillar_roots"] = _validate_file_roots(opts["pillar_roots"])

    if opts["file_ignore_regex"]:
        # If file_ignore_regex was given, make sure it's wrapped in a list.
        # Only keep valid regex entries for improved performance later on.
        if isinstance(opts["file_ignore_regex"], str):
            ignore_regex = [opts["file_ignore_regex"]]
        elif isinstance(opts["file_ignore_regex"], list):
            ignore_regex = opts["file_ignore_regex"]

        opts["file_ignore_regex"] = []
        for regex in ignore_regex:
            try:
                # Can't store compiled regex itself in opts (breaks
                # serialization)
                re.compile(regex)
                opts["file_ignore_regex"].append(regex)
            except Exception:  # pylint: disable=broad-except
                log.warning("Unable to parse file_ignore_regex. Skipping: %s", regex)

    if opts["file_ignore_glob"]:
        # If file_ignore_glob was given, make sure it's wrapped in a list.
        if isinstance(opts["file_ignore_glob"], str):
            opts["file_ignore_glob"] = [opts["file_ignore_glob"]]

    # Let's make sure `worker_threads` does not drop below 3 which has proven
    # to make `salt.modules.publish` not work under the test-suite.
    if opts["worker_threads"] < 3 and opts.get("peer", None):
        log.warning(
            "The 'worker_threads' setting in '%s' cannot be lower than "
            "3. Resetting it to the default value of 3.",
            opts["conf_file"],
        )
        opts["worker_threads"] = 3

    opts.setdefault("pillar_source_merging_strategy", "smart")

    # Make sure hash_type is lowercase
    opts["hash_type"] = opts["hash_type"].lower()

    # Check and update TLS/SSL configuration
    _update_ssl_config(opts)
    _update_discovery_config(opts)

    return opts


def client_config(path, env_var="SALT_CLIENT_CONFIG", defaults=None):
    """
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
    """
    if defaults is None:
        defaults = DEFAULT_MASTER_OPTS.copy()

    xdg_dir = salt.utils.xdg.xdg_config_dir()
    if os.path.isdir(xdg_dir):
        client_config_dir = xdg_dir
        saltrc_config_file = "saltrc"
    else:
        client_config_dir = os.path.expanduser("~")
        saltrc_config_file = ".saltrc"

    # Get the token file path from the provided defaults. If not found, specify
    # our own, sane, default
    opts = {
        "token_file": defaults.get(
            "token_file", os.path.join(client_config_dir, "salt_token")
        )
    }
    # Update options with the master configuration, either from the provided
    # path, salt's defaults or provided defaults
    opts.update(master_config(path, defaults=defaults))
    # Update with the users salt dot file or with the environment variable
    saltrc_config = os.path.join(client_config_dir, saltrc_config_file)
    opts.update(load_config(saltrc_config, env_var, saltrc_config))
    # Make sure we have a proper and absolute path to the token file
    if "token_file" in opts:
        opts["token_file"] = os.path.abspath(os.path.expanduser(opts["token_file"]))
    # If the token file exists, read and store the contained token
    if os.path.isfile(opts["token_file"]):
        # Make sure token is still valid
        expire = opts.get("token_expire", 43200)
        if os.stat(opts["token_file"]).st_mtime + expire > time.mktime(
            time.localtime()
        ):
            with salt.utils.files.fopen(opts["token_file"]) as fp_:
                opts["token"] = fp_.read().strip()
    # On some platforms, like OpenBSD, 0.0.0.0 won't catch a master running on localhost
    if opts["interface"] == "0.0.0.0":
        opts["interface"] = "127.0.0.1"
    elif opts["interface"] == "::":
        opts["interface"] = "::1"

    # Make sure the master_uri is set
    if "master_uri" not in opts:
        opts["master_uri"] = "tcp://{ip}:{port}".format(
            ip=salt.utils.network.ip_bracket(opts["interface"]), port=opts["ret_port"]
        )

    # Return the client options
    _validate_opts(opts)
    salt.features.setup_features(opts)
    return opts


def api_config(path):
    """
    Read in the Salt Master config file and add additional configs that
    need to be stubbed out for salt-api
    """
    # Let's grab a copy of salt-api's required defaults
    opts = DEFAULT_API_OPTS.copy()

    # Let's override them with salt's master opts
    opts.update(client_config(path, defaults=DEFAULT_MASTER_OPTS.copy()))

    # Let's set the pidfile and log_file values in opts to api settings
    opts.update(
        {
            "pidfile": opts.get("api_pidfile", DEFAULT_API_OPTS["api_pidfile"]),
            "log_file": opts.get("api_logfile", DEFAULT_API_OPTS["api_logfile"]),
        }
    )

    prepend_root_dir(opts, ["api_pidfile", "api_logfile", "log_file", "pidfile"])
    salt.features.setup_features(opts)
    return opts


def spm_config(path):
    """
    Read in the salt master config file and add additional configs that
    need to be stubbed out for spm

    .. versionadded:: 2015.8.0
    """
    # Let's grab a copy of salt's master default opts
    defaults = DEFAULT_MASTER_OPTS.copy()
    # Let's override them with spm's required defaults
    defaults.update(DEFAULT_SPM_OPTS)

    overrides = load_config(path, "SPM_CONFIG", DEFAULT_SPM_OPTS["spm_conf_file"])
    default_include = overrides.get(
        "spm_default_include", defaults["spm_default_include"]
    )
    include = overrides.get("include", [])

    overrides.update(include_config(default_include, path, verbose=False))
    overrides.update(include_config(include, path, verbose=True))
    defaults = apply_master_config(overrides, defaults)
    defaults = apply_spm_config(overrides, defaults)
    return client_config(path, env_var="SPM_CONFIG", defaults=defaults)


def apply_spm_config(overrides, defaults):
    """
    Returns the spm configurations dict.

    .. versionadded:: 2015.8.1
    """
    opts = defaults.copy()
    _adjust_log_file_override(overrides, defaults["log_file"])
    if overrides:
        opts.update(overrides)

    # Prepend root_dir to other paths
    prepend_root_dirs = [
        "formula_path",
        "pillar_path",
        "reactor_path",
        "spm_cache_dir",
        "spm_build_dir",
    ]

    # These can be set to syslog, so, not actual paths on the system
    for config_key in ("spm_logfile",):
        log_setting = opts.get(config_key, "")
        if log_setting is None:
            continue

        if urllib.parse.urlparse(log_setting).scheme == "":
            prepend_root_dirs.append(config_key)

    prepend_root_dir(opts, prepend_root_dirs)
    return opts
