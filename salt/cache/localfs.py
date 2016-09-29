# -*- coding: utf-8 -*-
'''
Cache data in filesystem.

.. versionadded:: carbon

Expirations can be set in the relevant config file (``/etc/salt/master`` for
the master, ``/etc/salt/cloud`` for Salt Cloud, etc).
'''
from __future__ import absolute_import
import logging
import os
import os.path
import shutil
import tempfile

from salt.exceptions import SaltCacheError
import salt.utils
import salt.utils.atomicfile

log = logging.getLogger(__name__)


def store(bank, key, data):
    '''
    Store information in a file.
    '''
    base = os.path.join(__opts__['cachedir'], os.path.normpath(bank))
    if not os.path.isdir(base):
        try:
            os.makedirs(base)
        except OSError as exc:
            raise SaltCacheError(
                'The cache directory, {0}, does not exist and could not be '
                'created: {1}'.format(base, exc)
            )

    outfile = os.path.join(base, '{0}.p'.format(key))
    tmpfh, tmpfname = tempfile.mkstemp(dir=base)
    os.close(tmpfh)
    try:
        with salt.utils.fopen(tmpfname, 'w+b') as fh_:
            fh_.write(__context__['serial'].dumps(data))
        # On Windows, os.rename will fail if the destination file exists.
        salt.utils.atomicfile.atomic_rename(tmpfname, outfile)
    except IOError as exc:
        raise SaltCacheError(
            'There was an error writing the cache file, {0}: {1}'.format(
                base, exc
            )
        )


def fetch(bank, key):
    '''
    Fetch information from a file.
    '''
    key_file = os.path.join(__opts__['cachedir'], os.path.normpath(bank), '{0}.p'.format(key))
    if not os.path.isfile(key_file):
        log.debug('Cache file "%s" does not exist', key_file)
        return None
    try:
        with salt.utils.fopen(key_file, 'rb') as fh_:
            return __context__['serial'].load(fh_)
    except IOError as exc:
        raise SaltCacheError(
            'There was an error reading the cache file "{0}": {1}'.format(
                key_file, exc
            )
        )


def updated(bank, key):
    '''
    Return the epoch of the mtime for this cache file
    '''
    key_file = os.path.join(__opts__['cachedir'], os.path.normpath(bank), '{0}.p'.format(key))
    if not os.path.isfile(key_file):
        log.warn('Cache file "%s" does not exist', key_file)
        return None
    try:
        return int(os.path.getmtime(key_file))
    except IOError as exc:
        raise SaltCacheError(
            'There was an error reading the mtime for "{0}": {1}'.format(
                key_file, exc
            )
        )


def flush(bank, key=None):
    '''
    Remove the key from the cache bank with all the key content.
    '''
    try:
        if key is None:
            target = os.path.join(__opts__['cachedir'], os.path.normpath(bank))
            if not os.path.isdir(target):
                return False
            shutil.rmtree(target)
        else:
            target = os.path.join(__opts__['cachedir'], os.path.normpath(bank), '{0}.p'.format(key))
            if not os.path.isfile(target):
                return False
            os.remove(target)
    except OSError as exc:
        raise SaltCacheError(
            'There was an error removing "{0}": {1}'.format(
                target, exc
            )
        )
    return True


def list(bank):
    '''
    Return an iterable object containing all entries stored in the specified bank.
    '''
    base = os.path.join(__opts__['cachedir'], os.path.normpath(bank))
    if not os.path.isdir(base):
        return []
    try:
        return os.listdir(base)
    except OSError as exc:
        raise SaltCacheError(
            'There was an error accessing directory "{0}": {1}'.format(
                base, exc
            )
        )


def contains(bank, key):
    '''
    Checks if the specified bank contains the specified key.
    '''
    if key is None:
        base = os.path.join(__opts__['cachedir'], os.path.normpath(bank))
        return os.path.isdir(base)
    else:
        keyfile = os.path.join(__opts__['cachedir'], os.path.normpath(bank), '{0}.p'.format(key))
        return os.path.isfile(keyfile)
