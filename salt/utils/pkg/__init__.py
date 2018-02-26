# -*- coding: utf-8 -*-
'''
Common functions for managing package refreshes during states
'''
# Import python libs
from __future__ import absolute_import
import errno
import logging
import os

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)


def rtag(opts):
    '''
    Return the rtag file location. This file is used to ensure that we don't
    refresh more than once (unless explicitly configured to do so).
    '''
    return os.path.join(opts['cachedir'], 'pkg_refresh')


def clear_rtag(opts):
    '''
    Remove the rtag file
    '''
    try:
        os.remove(rtag(opts))
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            # Using __str__() here to get the fully-formatted error message
            # (error number, error message, path)
            log.warning('Encountered error removing rtag: %s', exc.__str__())


def write_rtag(opts):
    '''
    Write the rtag file
    '''
    rtag_file = rtag(opts)
    if not os.path.exists(rtag_file):
        try:
            with salt.utils.fopen(rtag_file, 'w+'):
                pass
        except OSError as exc:
            log.warning('Encountered error writing rtag: %s', exc.__str__())


def check_refresh(opts, refresh=None):
    '''
    Check whether or not a refresh is necessary

    Returns:

    - True if refresh evaluates as True
    - False if refresh is False
    - A boolean if refresh is not False and the rtag file exists
    '''
    return bool(
        salt.utils.is_true(refresh) or
        (os.path.isfile(rtag(opts)) and refresh is not False)
    )
