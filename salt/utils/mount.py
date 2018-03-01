# -*- coding: utf-8 -*-
'''
Common functions for managing mounts
'''

# Import python libs
from __future__ import absolute_import, unicode_literals
import logging
import os

# Import Salt libs
import salt.utils.files
import salt.utils.stringutils
import salt.utils.yaml
import salt.utils.versions

log = logging.getLogger(__name__)


def _read_file(path):
    '''
    Reads and returns the contents of a text file
    '''
    try:
        with salt.utils.files.fopen(path, 'rb') as contents:
            return salt.utils.yaml.safe_load(contents)
    except (OSError, IOError):
        return {}


def get_cache(opts):
    '''
    Return the mount cache file location.
    '''
    return os.path.join(opts['cachedir'], 'mounts')


def read_cache(opts):
    '''
    Write the mount cache file.
    '''
    cache_file = get_cache(opts)
    return _read_file(cache_file)


def write_cache(cache, opts):
    '''
    Write the mount cache file.
    '''
    cache_file = get_cache(opts)

    try:
        _cache = salt.utils.stringutils.to_bytes(
            salt.utils.yaml.safe_dump(cache)
        )
        with salt.utils.files.fopen(cache_file, 'wb+') as fp_:
            fp_.write(_cache)
        return True
    except (IOError, OSError):
        log.error('Failed to cache mounts',
                  exc_info_on_loglevel=logging.DEBUG)
        return False
