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

def minion_config(path):
    '''
    Reads in the minion configuration file and sets up special options
    '''
    opts = {'master': 'salt',
            'master_port': '4506',
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
            'test': False,
            'cython_enable': True,
            }

    if os.path.isfile(path):
        try:
            opts.update(yaml.load(open(path, 'r')))
        except Exception:
            pass

    opts['master_uri'] = 'tcp://' + opts['master'] + ':'\
                       + str(opts['master_port'])

    # Enableing open mode requires that the value be set to True, and nothing
    # else!
    if opts['open_mode']:
        if opts['open_mode'] == True:
            opts['open_mode'] = True
        else:
            opts['open_mode'] = False

    opts['grains'] = salt.loader.grains(opts)

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
            'pki_dir': '/etc/salt/pki',
            'cachedir': '/var/cache/salt',
            'file_root': '/srv/salt',
            'file_buffer_size': 1048576,
            'hash_type': 'md5',
            'conf_file': path,
            'open_mode': False,
            'auto_accept': False,
            'log_file': '/var/log/salt/master',
            'log_level': 'warning',
            'cluster_masters': [],
            'cluster_mode': 'paranoid',
            }

    if os.path.isfile(path):
        try:
            opts.update(yaml.load(open(path, 'r')))
        except Exception:
            pass

    opts['aes'] = salt.crypt.Crypticle.generate_key_string()

    # Enableing open mode requires that the value be set to True, and nothing
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
