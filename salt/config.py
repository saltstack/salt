'''
All salt configuration loading and defaults should be in this module
'''
# Import python modules
import os
import socket
import subprocess
import logging
# Import third party libs
import yaml
# Import salt libs
import salt.crypt

def minion_config(path):
    '''
    Reads in the minion configuration file and sets up special options
    '''
    opts = {'master': 'mcp',
            'master_port': '4506',
            'pki_dir': '/etc/salt/pki',
            'id': socket.getfqdn(),
            'cachedir': '/var/cache/salt',
            'conf_file': path,
            'disable_modules': [],
            'open_mode': False,
            'multiprocessing': False,
            'log_file': '/var/log/salt/master',
            'log_level': 'WARNING',
            'out_level': 'ERROR',
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

    opts['logger'] = master_logger(opts['log_file'],
                                   opts['log_level'],
                                   opts['out_level'])

    return opts

def master_config(path):
    '''
    Reads in the master configuration file and sets up default options
    '''
    opts = {'interface': '0.0.0.0',
            'publish_port': '4505',
            'worker_threads': 5,
            'ret_port': '4506',
            'local_threads': 5,
            'local_port': '4507',
            'keep_jobs': 24,
            'pki_dir': '/etc/salt/pki',
            'cachedir': '/var/cache/salt',
            'conf_file': path,
            'open_mode': False,
            'auto_accept': False,
            'log_file': '/var/log/salt/master',
            'log_level': 'WARNING',
            'out_level': 'ERROR',
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

    opts['logger'] = master_logger(opts['log_file'],
                                   opts['log_level'],
                                   opts['out_level'])

    return opts

def master_logger(log_file, log_level, console_level):
    '''
    Returns a logger fo use with a salt master
    '''
    if not os.path.isdir(os.path.dirname(log_file)):
        os.makedirs(os.path.dirname(log_file))
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    fh_ = logging.FileHandler(log_file)
    fh_.setLevel(getattr(logging, log_level))

    ch_ = logging.StreamHandler()
    ch_.setLevel(getattr(logging, console_level))

    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(fmt)
    ch_.setFormatter(formatter)
    fh_.setFormatter(formatter)
    logger.addHandler(ch_)
    logger.addHandler(fh_)

    return logger

def minion_logger(log_file, log_level, console_level):
    '''
    Returns a logger fo use with a salt minion
    '''
    if not os.path.isdir(os.path.dirname(log_file)):
        os.makedirs(os.path.dirname(log_file))
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    fh_ = logging.FileHandler(log_file)
    fh_.setLevel(getattr(logging, log_level))

    ch_ = logging.StreamHandler()
    ch_.setLevel(getattr(logging, console_level))

    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(fmt)
    ch_.setFormatter(formatter)
    fh_.setFormatter(formatter)
    logger.addHandler(ch_)
    logger.addHandler(fh_)

    return logger

def facter_data():
    '''
    Returns a dict of data about the minion allowing modules to differ
    based on information gathered about the minion.
    So far only facter information is loaded
    '''
    facts = subprocess.Popen('facter',
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]
    facter = {}
    for line in facts.split('\n'):
        if line.count('=>'):
            comps = line.split('=>')
            facter[comps[0].strip()] = comps[1].strip()

    return facter
