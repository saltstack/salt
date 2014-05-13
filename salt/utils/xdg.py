# -*- coding: utf-8 -*-
'''
Create an XDG function to get the config dir
'''
import os


def xdg_config_dir(config_dir=None):
    '''
    Check xdg locations for config files
    '''
    xdg_config = os.getenv('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    xdg_config_directory = os.path.join(xdg_config, 'salt')
    if os.path.isdir(xdg_config_directory):
        return xdg_config_directory
    else:
        if config_dir is None:
            config_dir = '~/.'
        else:
            config_dir = os.path.join('~/.', config_dir)
        return os.path.expanduser(config_dir)
