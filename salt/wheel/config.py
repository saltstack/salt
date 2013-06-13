'''
Manage the master configuration file
'''

# Import python libs
import os

# Import third party libs
import yaml

# Import salt libs
import salt.config


def values():
    '''
    Return the raw values of the config file
    '''
    data = salt.config.master_config(__opts__['conf_file'])
    data.pop('aes')
    data.pop('token_dir')
    return data


def apply(key, value):
    '''
    Set a single key

    .. note::

        This will strip comments from your config file
    '''
    path = __opts__['conf_file']
    if os.path.isdir(path):
        path = os.path.join(path, 'master')
    data = values()
    data[key] = value
    with salt.utils.fopen(path, 'w+') as fp_:
        fp_.write(yaml.dump(data, default_flow_style=False))
