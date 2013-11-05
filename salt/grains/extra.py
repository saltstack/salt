# -*- coding: utf-8 -*-
# Import python libs
import os

# Import third party libs
import yaml

# Import salt libs
import salt.utils


def shell():
    '''
    Return the default shell to use on this system
    '''
    # Provides:
    #   shell
    return {'shell': os.environ.get('SHELL', '/bin/sh')}


def config():
    '''
    Return the grains set in the grains file
    '''
    if not 'conf_file' in __opts__:
        return {}
    if os.path.isdir(__opts__['conf_file']):
        gfn = os.path.join(
                __opts__['conf_file'],
                'grains'
                )
    else:
        gfn = os.path.join(
                os.path.dirname(__opts__['conf_file']),
                'grains'
                )
    if os.path.isfile(gfn):
        with salt.utils.fopen(gfn, 'rb') as fp_:
            try:
                return yaml.safe_load(fp_.read())
            except Exception:
                return {}
    return {}
