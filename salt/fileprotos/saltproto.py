# -*- coding: utf-8 -*-
'''
Salt Client Module Directory
'''
from __future__ import unicode_literals


import logging
log = logging.getLogger(__name__)

__virtualname__ = 'salt'


def __virtual__():
    return __virtualname__


def needscache():
    '''
    Does not need cache setup
    '''
    return False


def get(url, dest, saltenv='base', makedirs=False, cachedir=False, no_cache=False):
    '''
    Get file from salt fileserver
    '''
    result = __salt__['cp.get_file'](url, dest, makedirs, saltenv, cachedir=cachedir)
    if result and dest is None:
        with __utils__['files.fopen'](result, 'rb') as fp_:
            data = fp_.read()
        return data
    return result
