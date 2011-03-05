'''
All salt configuration loading and defaults should be in this module
'''
# Import python modules
import os
import sys
import socket
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
            }

    if os.path.isfile(path):
        try:
            opts.update(yaml.load(open(path, 'r')))
        except:
            err = 'The minon configuration file did not parse correctly,'\
                + ' please check your configuration file.\nUsing defaults'
            sys.stderr.write(err + '\n')

    opts['master_uri'] = 'tcp://' + opts['master'] + ':' + opts['master_port']

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
            }

    if os.path.isfile(path):
        try:
            opts.update(yaml.load(open(path, 'r')))
        except:
            err = 'The master configuration file did not parse correctly,'\
                + ' please check your configuration file.\nUsing defaults'
            sys.stderr.write(err + '\n')
    
    opts['aes'] = salt.crypt.Crypticle.generate_key_string()

    return opts
