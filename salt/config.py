'''
All salt configuration loading and defaults should be in this module
'''
# Import python modules
import os
import sys
import socket
import subprocess
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
            'hostname': socket.getfqdn(),
            'cachedir': '/var/cache/salt',
            'disable_modules': [],
            'open_mode': False,
            'log_file': '/var/log/salt/master',
            'log_level': 'DEBUG',
            'out_level': 'ERROR',
            }

    if os.path.isfile(path):
        try:
            opts.update(yaml.load(open(path, 'r')))
        except:
            pass

    opts['master_uri'] = 'tcp://' + opts['master'] + ':' + opts['master_port']
    
    # Enableing open mode requires that the value be set to True, and nothing
    # else!
    if opts['open_mode']:
        if opts['open_mode'] == True:
            opts['open_mode'] = True
        else:
            opts['open_mode'] = False

    opts['facter'] = facter_data()

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
            'pki_dir': '/etc/salt/pki',
            'cachedir': '/var/cache/salt',
            'open_mode': False,
            'log_file': '/var/log/salt/master',
            'log_level': 'DEBUG',
            'out_level': 'ERROR',
            'cluster_masters': [],
            }

    if os.path.isfile(path):
        try:
            opts.update(yaml.load(open(path, 'r')))
        except:
            pass
    
    opts['aes'] = salt.crypt.Crypticle.generate_key_string()

    # Enableing open mode requires that the value be set to True, and nothing
    # else!
    if opts['open_mode']:
        if opts['open_mode'] == True:
            opts['open_mode'] = True
        else:
            opts['open_mode'] = False

    return opts

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
