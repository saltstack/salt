'''
All salt configuration loading and defaults should be in this module
'''
# Import python modules
import os
import socket
# Import third party libs
import yaml
# Import salt libs
import salt.crypt
import salt.loader

def load_config(opts, path, env_var):
    '''
    Attempts to update ``opts`` dict by parsing either the file described by
    ``path`` or the environment variable described by ``env_var`` as YAML.
    '''

    if not path or not os.path.isfile(path):
        path = os.environ.get(env_var, '')

    if os.path.isfile(path):
        try:
            conf_opts = yaml.load(open(path, 'r'))
            if conf_opts == None:
                # The config file is empty and the yaml.load returned None
                conf_opts = {}
            opts.update(conf_opts)
            opts['conf_file'] = path
        except Exception, e:
            print 'Error parsing configuration file: {0} - {1}'.format(path, e)
    else:
        print 'Missing configuration file: {0}'.format(path)

def prepend_root_dir(opts):
    '''
    Prepends the options that represent filesystem paths with value of the
    'root_dir' option.
    '''
    path_options = ('pki_dir', 'cachedir', 'log_file')
    for path_option in path_options:
        opts[path_option] = os.path.normpath(
                os.sep.join([opts['root_dir'], opts[path_option]]))

def minion_config(path):
    '''
    Reads in the minion configuration file and sets up special options
    '''
    opts = {'master': 'salt',
            'master_port': '4506',
            'root_dir': '/',
            'pki_dir': '/etc/salt/pki',
            'id': socket.getfqdn(),
            'cachedir': '/var/cache/salt',
            'conf_file': path,
            'renderer': 'yaml_jinja',
            'disable_modules': [],
            'disable_returners': [],
            'module_dirs': [],
            'returner_dirs': [],
            'states_dirs': [],
            'render_dirs': [],
            'open_mode': False,
            'multiprocessing': False,
            'log_file': '/var/log/salt/minion',
            'log_level': 'warning',
            'log_granular_levels': {},
            'test': False,
            'cython_enable': True,
            }

    load_config(opts, path, 'SALT_MINION_CONFIG')

    opts['master_uri'] = 'tcp://' + opts['master'] + ':'\
                       + str(opts['master_port'])

    # Enabling open mode requires that the value be set to True, and nothing
    # else!
    if opts['open_mode']:
        if opts['open_mode'] == True:
            opts['open_mode'] = True
        else:
            opts['open_mode'] = False

    opts['grains'] = salt.loader.grains(opts)

    # Prepend root_dir to other paths
    prepend_root_dir(opts)

    return opts

def master_config(path):
    '''
    Reads in the master configuration file and sets up default options
    '''
    opts = {'interface': '0.0.0.0',
            'publish_port': '4505',
            'publish_pull_port': '45055',
            'worker_threads': 5,
            'worker_start_port': '45056',
            'ret_port': '4506',
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
            'state_top': 'top.yml',
            'log_file': '/var/log/salt/master',
            'log_level': 'warning',
            'log_granular_levels': {},
            'cluster_masters': [],
            'cluster_mode': 'paranoid',
            }

    load_config(opts, path, 'SALT_MASTER_CONFIG')

    opts['aes'] = salt.crypt.Crypticle.generate_key_string()

    # Prepend root_dir to other paths
    prepend_root_dir(opts)

    # Enabling open mode requires that the value be set to True, and nothing
    # else!
    if opts['open_mode']:
        if opts['open_mode'] == True:
            opts['open_mode'] = True
        else:
            opts['open_mode'] = False
    if opts['auto_accept']:
        if opts['auto_accept'] == True:
            opts['auto_accept'] = True
        else:
            opts['auto_accept'] = False
    return opts
