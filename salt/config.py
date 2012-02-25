'''
All salt configuration loading and defaults should be in this module
'''

# Import python modules
import glob
import os
import sys
import socket
import logging
import tempfile

# import third party libs
import yaml
try:
    yaml.Loader = yaml.CLoader
    yaml.Dumper = yaml.CDumper
except:
    pass


# Import salt libs
import salt.crypt
import salt.loader
import salt.utils

log = logging.getLogger(__name__)


def _validate_file_roots(file_roots):
    '''
    If the file_roots option has a key that is None then we will error out,
    just replace it with an empty list
    '''
    if not isinstance(file_roots, dict):
        log.warning(('The file_roots parameter is not properly formatted,'
            ' using defaults'))
        return {'base': ['/srv/salt']}
    for env, dirs in file_roots.items():
        if not isinstance(dirs, list) and not isinstance(dirs, tuple):
            file_roots[env] = []
    return file_roots


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
                    f.readline() # skip first line
                    out.write(f.read())

    if os.path.isfile(path):
        try:
            conf_opts = yaml.safe_load(open(path, 'r'))
            if conf_opts is None:
                # The config file is empty and the yaml.load returned None
                conf_opts = {}
            else:
                # allow using numeric ids: convert int to string
                if 'id' in conf_opts:
                    conf_opts['id'] = str(conf_opts['id'])
            opts.update(conf_opts)
            opts['conf_file'] = path
        except Exception, e:
            msg = 'Error parsing configuration file: {0} - {1}'
            log.warn(msg.format(path, e))
    else:
        log.debug('Missing configuration file: {0}'.format(path))


def include_config(opts, orig_path):
    '''
    Parses an extra configuration file specified in an include list in the
    main config file.
    '''
    include = opts.get('include', [])
    if isinstance(include, basestring):
        include = [include]
    for path in include:
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(orig_path), path)
        for fn_ in glob.glob(path):
            try:
                conf_opts = yaml.safe_load(open(fn_, 'r'))
                if conf_opts is None:
                    # The config file is empty and the yaml.load returned None
                    conf_opts = {}
                else:
                    # allow using numeric ids: convert int to string
                    if 'id' in conf_opts:
                        conf_opts['id'] = str(conf_opts['id'])
                opts.update(conf_opts)
            except Exception, e:
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
            'renderer': 'yaml_jinja',
            'failhard': False,
            'autoload_dynamic_modules': True,
            'environment': None,
            'disable_modules': [],
            'disable_returners': [],
            'module_dirs': [],
            'returner_dirs': [],
            'states_dirs': [],
            'render_dirs': [],
            'clean_dynamic_modules': True,
            'open_mode': False,
            'multiprocessing': True,
            'sub_timeout': 60,
            'log_file': '/var/log/salt/minion',
            'log_level': 'warning',
            'log_granular_levels': {},
            'test': False,
            'cython_enable': False,
            'state_verbose': False,
            'acceptance_wait_time': 10,
            }

    load_config(opts, path, 'SALT_MINION_CONFIG')

    if 'include' in opts:
        opts = include_config(opts, path)

    opts['master_ip'] = dns_check(opts['master'])

    opts['master_uri'] = 'tcp://' + opts['master_ip'] + ':'\
                       + str(opts['master_port'])

    # Enabling open mode requires that the value be set to True, and nothing
    # else!
    opts['open_mode'] = opts['open_mode'] is True

    # set up the extension_modules location from the cachedir
    opts['extension_modules'] = os.path.join(opts['cachedir'], 'extmods')

    opts['grains'] = salt.loader.grains(opts)

    # Prepend root_dir to other paths
    prepend_root_dir(opts, ['pki_dir', 'cachedir', 'log_file'])

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
            'log_file': '/var/log/salt/master',
            'log_level': 'warning',
            'log_granular_levels': {},
            'cluster_masters': [],
            'cluster_mode': 'paranoid',
            'serial': 'msgpack',
            'nodegroups': {},
    }

    load_config(opts, path, 'SALT_MASTER_CONFIG')

    if 'include' in opts:
        opts = include_config(opts, path)

    opts['aes'] = salt.crypt.Crypticle.generate_key_string()

    # Prepend root_dir to other paths
    prepend_root_dir(opts, ['pki_dir', 'cachedir', 'log_file', 'sock_dir'])

    # Enabling open mode requires that the value be set to True, and nothing
    # else!
    opts['open_mode'] = opts['open_mode'] is True
    opts['auto_accept'] = opts['auto_accept'] is True
    opts['file_roots'] = _validate_file_roots(opts['file_roots'])
    return opts


def dns_check(addr):
    '''
    Verify that the passed address is valid and return the ipv4 addr if it is
    a hostname
    '''
    try:
        socket.inet_aton(addr)
        # is a valid ip addr
    except socket.error:
        # Not a valid ip addr, check if it is an available hostname
        try:
            addr = socket.gethostbyname(addr)
        except socket.gaierror:
            # Woah, this addr is totally bogus, die!!!
            err = ('The master address {0} could not be validated, please '
                   'check that the specified master in the minion config '
                   'file is correct\n')
            err = err.format(addr)
            sys.stderr.write(err)
            sys.exit(42)
    return addr
