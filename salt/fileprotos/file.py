# -*- coding: utf-8 -*-
'''
File Client Module Directory
'''
from __future__ import unicode_literals

# Import Python Library
import os.path

# Import Salt library
from salt.exceptions import CommandExecutionError


def needscache():
    '''
    Does not need cache setup
    '''
    return False


def get(url, dest, **kwargs):
    '''
    Get file from local file system
    '''
    _, url_scheme, url_path = __salt__['cp.get_url_data'](url)
    # Local filesystem
    if not os.path.isabs(url):
        raise CommandExecutionError(
            'Path \'{0}\' is not absolute'.format(url_path)
        )
    if dest is None:
        with __utils__['files.fopen'](url, 'rb') as fp_:
            data = fp_.read()
        return data
    return url_path
