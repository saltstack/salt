'''
All salt configuration loading and defaults should be in this module
'''

# Import python modules
import glob
import os
import socket
import logging
import tempfile

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
import salt.pillar
from salt.exceptions import SaltClientError

log = logging.getLogger(__name__)

__dflt_log_datefmt = '%H:%M:%S'
__dflt_log_fmt_console = '[%(levelname)-8s] %(message)s'
__dflt_log_fmt_logfile = '%(asctime)s,%(msecs)03.0f [%(name)-17s][%(levelname)-8s] %(message)s'

def _validate_file_roots(file_roots):
    '''
    If the file_roots option has a key that is None then we will error out,
    just replace it with an empty list
    '''
    if not isinstance(file_roots, dict):
        log.warning('The file_roots parameter is not properly formatted,'
                    ' using defaults')
        return {'base': ['/srv/salt']}
    for env, dirs in list(file_roots.items()):
        if not isinstance(dirs, list) and not isinstance(dirs, tuple):
            file_roots[env] = []
    return file_roots


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
    return "{0[id]}.{0[append_domain]}".format(opts)


def _read_conf_file(path):
    with open(path, 'r') as conf_file:
        conf_opts = yaml.safe_load(conf_file.read()) or {}
        # allow using numeric ids: convert int to string
        if 'id' in conf_opts:
            conf_opts['id'] = str(conf_opts['id'])
        return conf_opts


def load_config(opts, path, env_var):
    '''
    Attempts to update ``opts`` dict by parsing either the file described by
    ``path`` or the environment variable described by ``env_var`` as YAML.
    '''
    if not path or not os.path.isfile(path):
        path = os.environ.get(env_var, path)
    # If the configuration file is missing, attempt to copy the template,
    # after removing the first header line.
    if not os.path.isfile(path):
        template = '{0}.template'.format(path)
        if os.path.isfile(template):
            with open(path, 'w') as out:
                with open(template, 'r') as f:
                    f.readline()  # skip first line
                    out.write(f.read())

    if os.path.isfile(path):
        try:
            opts.update(_read_conf_file(path))
            opts['conf_file'] = path
        except Exception as e:
            import salt.log
            msg = 'Error parsing configuration file: {0} - {1}'
            if salt.log.is_console_configured():
                log.warn(msg.format(path, e))
            else:
                print msg.format(path, e)
    else:
        log.debug('Missing configuration file: {0}'.format(path))


def include_config(opts, orig_path):
    '''
    Parses extra configuration file(s) specified in an include list in the
    main config file.
    '''
    include = opts.get('include', [])

    # Protect against empty option
    if not include:
        log.warn("Error parsing configuration file: 'include' option is empty")
        return opts
    
    if isinstance(include, str):
        include = [include]

    for path in include:
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(orig_path), path)

        # Catch situation where user typos path in config; also warns for
        # empty include dir (which might be by design)        
        if len(glob.glob(path)) == 0:
            msg = "Warning parsing configuration file: 'include' path/glob '{0}' matches no files"
            log.warn(msg.format(path))

        for fn_ in glob.glob(path):
            try:
                opts.update(_read_conf_file(fn_))
            except Exception as e:
                msg = 'Error parsing configuration file: {0} - {1}'
                log.warn(msg.format(fn_, e))
    return opts


def prepend_root_dir(opts, path_options):
    '''
    Prepends the options that represent filesystem paths with value of the
    'root_dir' option.
    '''
    for path_option in path_options:
        if path_option in opts:
            opts[path_option] = os.path.normpath(
                    os.sep.join([opts['root_dir'], opts[path_option]]))


def minion_config(path):
    '''
    Reads in the minion configuration file and sets up special options
    '''
    opts = {'master': 'salt',
            'master_port': '4506',
            'user': 'root',
            'root_dir': '/',
            'pki_dir': '/etc/salt/pki',
            'id': socket.getfqdn(),
            'cachedir': '/var/cache/salt',
            'cache_jobs': False,
            'conf_file': path,
            'sock_dir': os.path.join(tempfile.gettempdir(), '.salt-unix'),
            'renderer': 'yaml_jinja',
            'failhard': False,
            'autoload_dynamic_modules': True,
            'environment': None,
            'state_top': 'top.sls',
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
            'module_dirs': [],
            'returner_dirs': [],
            'states_dirs': [],
            'render_dirs': [],
            'providers': {},
            'clean_dynamic_modules': True,
            'open_mode': False,
            'multiprocessing': True,
            'sub_timeout': 60,
            'log_file': '/var/log/salt/minion',
            'log_level': 'warning',
            'log_level_logfile': None,
            'log_datefmt': __dflt_log_datefmt,
            'log_fmt_console': __dflt_log_fmt_console,
            'log_fmt_logfile': __dflt_log_fmt_logfile,
            'log_granular_levels': {},
            'test': False,
            'cython_enable': False,
            'state_verbose': False,
            'acceptance_wait_time': 10,
            'dns_check': True,
            'grains': {},
            }

    load_config(opts, path, 'SALT_MINION_CONFIG')

    if 'include' in opts:
        opts = include_config(opts, path)

    if 'append_domain' in opts:
        opts['id'] = _append_domain(opts)

    try:
        opts['master_ip'] = salt.utils.dns_check(opts['master'], True)
    except SaltClientError:
        opts['master_ip'] = '127.0.0.1'

    opts['master_uri'] = 'tcp://{ip}:{port}'.format(ip=opts['master_ip'],
                                                    port=opts['master_port'])

    # Enabling open mode requires that the value be set to True, and
    # nothing else!
    opts['open_mode'] = opts['open_mode'] is True

    # set up the extension_modules location from the cachedir
    opts['extension_modules'] = os.path.join(opts['cachedir'], 'extmods')

    # Prepend root_dir to other paths
    prepend_root_dir(opts, ['pki_dir', 'cachedir', 'log_file', 'sock_dir',
                            'key_logfile', 'extension_modules'])

    opts['grains'] = salt.loader.grains(opts)

    return opts


def master_config(path):
    '''
    Reads in the master configuration file and sets up default options
    '''
    opts = {'interface': '0.0.0.0',
            'publish_port': '4505',
            'user': 'root',
            'worker_threads': 5,
            'sock_dir': os.path.join(tempfile.gettempdir(), '.salt-unix'),
            'ret_port': '4506',
            'timeout': 5,
            'keep_jobs': 24,
            'root_dir': '/',
            'pki_dir': '/etc/salt/pki',
            'cachedir': '/var/cache/salt',
            'file_roots': {
                'base': ['/srv/salt'],
                },
            'master_roots': {
                'base': ['/srv/salt-master'],
                },
            'pillar_roots': {
                'base': ['/srv/pillar'],
                },
            'file_buffer_size': 1048576,
            'hash_type': 'md5',
            'conf_file': path,
            'open_mode': False,
            'auto_accept': False,
            'renderer': 'yaml_jinja',
            'failhard': False,
            'state_top': 'top.sls',
            'external_nodes': '',
            'order_masters': False,
            'job_cache': True,
            'log_file': '/var/log/salt/master',
            'log_level': 'warning',
            'log_level_logfile': None,
            'log_datefmt': __dflt_log_datefmt,
            'log_fmt_console': __dflt_log_fmt_console,
            'log_fmt_logfile': __dflt_log_fmt_logfile,
            'log_granular_levels': {},
            'pidfile': '/var/run/salt-master.pid',
            'cluster_masters': [],
            'cluster_mode': 'paranoid',
            'range_server': 'range:80',
            'serial': 'msgpack',
            'nodegroups': {},
            'cython_enable': False,
            'key_logfile': '/var/log/salt/key.log',
    }

    load_config(opts, path, 'SALT_MASTER_CONFIG')

    if 'include' in opts:
        opts = include_config(opts, path)

    opts['aes'] = salt.crypt.Crypticle.generate_key_string()

    opts['extension_modules'] = os.path.join(opts['cachedir'], 'extmods')
    # Prepend root_dir to other paths
    prepend_root_dir(opts, ['pki_dir', 'cachedir', 'log_file',
                            'sock_dir', 'key_logfile', 'extension_modules'])

    # Enabling open mode requires that the value be set to True, and
    # nothing else!
    opts['open_mode'] = opts['open_mode'] is True
    opts['auto_accept'] = opts['auto_accept'] is True
    opts['file_roots'] = _validate_file_roots(opts['file_roots'])
    return opts
